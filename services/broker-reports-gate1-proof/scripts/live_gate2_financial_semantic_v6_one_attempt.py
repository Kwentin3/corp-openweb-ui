#!/usr/bin/env python3
"""Authorize and execute the exact Nano V6 qualification run."""

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
from broker_reports_gate1.gate2_financial_semantic_v6_execution_identity import (  # noqa: E402,E501
    V6_PROVIDER_PROFILE_ID,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    V6_QUALIFICATION_POLICY_VERSION,
    Gate2FinancialSemanticV6QualificationFixtureFactory,
    Gate2FinancialSemanticV6QualificationPreflightFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification_run import (  # noqa: E402,E501
    V6_QUALIFICATION_RUN_SCHEMA_VERSION,
    qualify_financial_semantic_v6,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE,
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


DEFAULT_V6_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
)
DEFAULT_BASE_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
SNAPSHOT_AUTHORITY_KEY = b"gate2-v6-qualification-snapshot-authority-key-v1"
CONTINUATION_KEY = b"gate2-v6-qualification-continuation-key-v1"
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6QualificationPreflightFactory.create, the "
    "configured Gate2 model client factory and qualify_financial_semantic_v6 "
    "are the only Goal 11B live route"
)
FORBIDDEN = (
    "This CLI must not permit an implicit or second attempt, repository-local "
    "private evidence, fallback, repair, hidden retry, customer data, "
    "production admission or technical-case provider calls"
)


class V6QualificationOneAttemptCliError(ValueError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument(
        "--execute-exact-attempt",
        action="store_true",
        help=(
            "Authorize the exact Nano V6 run; the model attempt is consumed "
            "only at its first provider transport submission."
        ),
    )
    parser.add_argument("--safe-receipt-path", required=True)
    parser.add_argument("--private-evidence-dir", required=True)
    args = parser.parse_args()
    if not args.execute_exact_attempt:
        parser.error("--execute-exact-attempt is required")

    safe_path = Path(args.safe_receipt_path).resolve()
    private_dir = Path(args.private_evidence_dir).resolve()
    _validate_new_attempt_paths(
        safe_path=safe_path,
        private_dir=private_dir,
    )
    if not _worktree_clean():
        raise V6QualificationOneAttemptCliError(
            "financial_semantic_v6_live_worktree_not_clean"
        )

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    fixture = _fixture()
    preflight = Gate2FinancialSemanticV6QualificationPreflightFactory().create(
        fixture=fixture,
        repository_revision=_repository_revision(),
        stage_action=_live_qualification_action(session, base_url),
        published_model_ids=_published_model_ids(session, base_url),
    )
    private_dir.mkdir(parents=True, exist_ok=False)
    _write_json_atomically(
        safe_path,
        {
            "schema_version": V6_QUALIFICATION_RUN_SCHEMA_VERSION,
            "policy_version": V6_QUALIFICATION_POLICY_VERSION,
            "execution_state": "pretransport_authorized",
            "status": "in_progress",
            "terminal_class": None,
            "failure_class_counts": {},
            "product_gate": None,
            "acceptance": {
                "provider_attempts": "ZERO",
                "hidden_retry": "ZERO",
                "exact_evidence": "PENDING",
                "product_gate": None,
            },
            "exact_identity": preflight["exact_identity"],
            "attempt_accounting": {
                "provider_attempts_total": 0,
                "model_attempts_consumed_total": 0,
                "local_invocations_total": 0,
                "provider_submissions_total": 0,
                "provider_responses_total": 0,
                "semantic_decisions_total": 0,
                "product_admitted_decisions_total": 0,
                "provider_calls_total": 0,
                "hidden_retry_total": 0,
                "fallback_total": 0,
                "repair_total": 0,
            },
            "quality": None,
            "model_metrics_status": "NOT_PUBLISHED",
            "raw_private_data_in_receipt": False,
        },
        require_absent=True,
    )

    user = _current_user(session, base_url)
    client = _model_client(
        request_profile=(
            FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE
        ),
        provider_profile_id=V6_PROVIDER_PROFILE_ID,
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
        qualify_financial_semantic_v6(
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
    manifest = json.loads(DEFAULT_V6_MANIFEST.read_text(encoding="utf-8"))
    base_manifest = json.loads(DEFAULT_BASE_MANIFEST.read_text(encoding="utf-8"))
    return Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=manifest,
        base_manifest=base_manifest,
    )


def _validate_new_attempt_paths(
    *,
    safe_path: Path,
    private_dir: Path,
) -> None:
    if (
        not safe_path.name.endswith(".safe.json")
        or safe_path.exists()
        or private_dir.exists()
        or _is_within(private_dir, REPO_ROOT)
    ):
        raise V6QualificationOneAttemptCliError(
            "financial_semantic_v6_attempt_path_invalid_or_consumed"
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
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    revision = completed.stdout.strip()
    if len(revision) != 40 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise V6QualificationOneAttemptCliError(
            "financial_semantic_v6_repository_revision_invalid"
        )
    return revision


def _worktree_clean() -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    return not completed.stdout.strip()


def _write_json_atomically(
    path: Path,
    payload: dict[str, Any],
    *,
    require_absent: bool = False,
) -> None:
    if require_absent and path.exists():
        raise V6QualificationOneAttemptCliError(
            "financial_semantic_v6_attempt_already_consumed"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(_pretty_json(payload))
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
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "code": str(exc)[:200],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise
