#!/usr/bin/env python3
"""Preflight or execute the one permitted exact Nano V5 qualification."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_qualification import (  # noqa: E402
    PROVIDER_PROFILE_ID,
    V5_QUALIFICATION_POLICY_VERSION,
    V5_QUALIFICATION_SCHEMA_VERSION,
    Gate2FinancialSemanticV5QualificationFixtureFactory,
    Gate2FinancialSemanticV5QualificationPreflightFactory,
    qualify_financial_semantic_v5,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _live_qualification_action,
    _model_client,
    _published_model_ids,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
)


DEFAULT_V5_MANIFEST = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v5"
    / "manifest.json"
)
DEFAULT_BASE_MANIFEST = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
SNAPSHOT_AUTHORITY_KEY = (
    b"gate2-v5-qualification-snapshot-authority-key-v1"
)
CONTINUATION_KEY = b"gate2-v5-qualification-continuation-key-v1"
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5QualificationFixtureFactory.create, "
    "Gate2FinancialSemanticV5QualificationPreflightFactory.create, "
    "the configured Gate2 model client factory and "
    "qualify_financial_semantic_v5 are the only live route"
)
FORBIDDEN = (
    "This CLI must not permit an implicit live run, a second receipt path "
    "attempt, repository-local private evidence, fallback, repair, hidden "
    "retry, customer data or technical-case provider calls"
)


class V5QualificationCliError(ValueError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run the zero-provider-call preflight (the safe default).",
    )
    parser.add_argument(
        "--execute-exact-attempt",
        action="store_true",
        help="Consume the single exact Nano V5 qualification attempt.",
    )
    parser.add_argument("--safe-receipt-path")
    parser.add_argument("--private-evidence-dir")
    args = parser.parse_args()
    if args.preflight_only and args.execute_exact_attempt:
        parser.error("choose one mode")
    execute = bool(args.execute_exact_attempt)
    if execute and (
        not args.safe_receipt_path or not args.private_evidence_dir
    ):
        parser.error(
            "live execution requires --safe-receipt-path and "
            "--private-evidence-dir"
        )

    safe_path = (
        Path(args.safe_receipt_path).resolve()
        if args.safe_receipt_path
        else None
    )
    private_dir = (
        Path(args.private_evidence_dir).resolve()
        if args.private_evidence_dir
        else None
    )
    if execute:
        _validate_new_attempt_paths(
            safe_path=safe_path,
            private_dir=private_dir,
        )

    env = _read_env(Path(args.env_file))
    base_url = (
        args.base_url.rstrip("/") if args.base_url else _base_url(env)
    )
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    stage_action = _live_qualification_action(session, base_url)
    stage_action["production_admissions_empty"] = True
    published = _published_model_ids(session, base_url)
    fixture = _fixture()
    repository_revision = _repository_revision()
    preflight = Gate2FinancialSemanticV5QualificationPreflightFactory().create(
        fixture=fixture,
        repository_revision=repository_revision,
        stage_action=stage_action,
        published_model_ids=published,
    )
    if not execute:
        print(_pretty_json(preflight), end="")
        return 0

    if not _worktree_clean():
        raise V5QualificationCliError(
            "financial_semantic_v5_live_worktree_not_clean"
        )
    assert safe_path is not None
    assert private_dir is not None
    private_dir.mkdir(parents=True, exist_ok=False)
    _write_json_atomically(
        safe_path,
        {
            "schema_version": V5_QUALIFICATION_SCHEMA_VERSION,
            "policy_version": V5_QUALIFICATION_POLICY_VERSION,
            "execution_state": "attempt_committed",
            "status": "in_progress",
            "product_gate": None,
            "exact_identity": preflight["exact_identity"],
            "attempt_accounting": {
                "provider_attempts_total": 1,
                "provider_calls_total": 0,
                "hidden_retry_total": 0,
                "fallback_total": 0,
                "repair_total": 0,
            },
            "raw_private_data_in_receipt": False,
        },
        require_absent=True,
    )

    user = _current_user(session, base_url)
    client = _model_client(
        request_profile=FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
        provider_profile_id=PROVIDER_PROFILE_ID,
        user_id=str(user["id"]),
        request_context=_request_context(session, base_url),
        completion=_completion_boundary(
            session=session,
            base_url=base_url,
            timeout=args.timeout,
        ),
    )

    def private_checkpoint(
        case_id: str,
        payload: dict[str, Any],
    ) -> None:
        _write_json_atomically(
            private_dir / f"{case_id}.private.json",
            payload,
            require_absent=True,
        )

    def safe_checkpoint(payload: dict[str, Any]) -> None:
        _write_json_atomically(safe_path, payload)

    receipt = asyncio.run(
        qualify_financial_semantic_v5(
            fixture=fixture,
            model_client=client,
            exact_identity=preflight["exact_identity"],
            private_case_checkpoint=private_checkpoint,
            safe_checkpoint=safe_checkpoint,
        )
    )
    print(_pretty_json(receipt), end="")
    return 0 if receipt["execution_state"] == "terminal" else 2


def _fixture():
    manifest = json.loads(DEFAULT_V5_MANIFEST.read_text(encoding="utf-8"))
    base_manifest = json.loads(
        DEFAULT_BASE_MANIFEST.read_text(encoding="utf-8")
    )
    return Gate2FinancialSemanticV5QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=manifest,
        base_manifest=base_manifest,
    )


def _validate_new_attempt_paths(
    *,
    safe_path: Path | None,
    private_dir: Path | None,
) -> None:
    if (
        safe_path is None
        or private_dir is None
        or not safe_path.name.endswith(".safe.json")
        or safe_path.exists()
        or private_dir.exists()
        or _is_within(private_dir, REPO_ROOT)
    ):
        raise V5QualificationCliError(
            "financial_semantic_v5_attempt_path_invalid_or_consumed"
        )
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    private_dir.parent.mkdir(parents=True, exist_ok=True)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _repository_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _worktree_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return not result.stdout.strip()


def _write_json_atomically(
    path: Path,
    payload: dict[str, Any],
    *,
    require_absent: bool = False,
) -> None:
    if require_absent and path.exists():
        raise V5QualificationCliError(
            "financial_semantic_v5_attempt_already_consumed"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _pretty_json(payload)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _pretty_json(payload: dict[str, Any]) -> str:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
