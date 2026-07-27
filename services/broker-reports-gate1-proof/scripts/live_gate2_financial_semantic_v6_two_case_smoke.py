#!/usr/bin/env python3
"""Preflight or execute one exact-candidate two-case V6 provider smoke."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
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

from broker_reports_gate1.gate2_financial_semantic_v6_execution_identity import (  # noqa: E402,E501
    V6_EXACT_MODEL_ID,
    V6_PROVIDER_PROFILE_ID,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationPreflightFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification_run import (  # noqa: E402,E501
    financial_semantic_v6_provider_smoke_initial_receipt,
    smoke_financial_semantic_v6,
)
from broker_reports_gate1.gate2_financial_semantic_v6_smoke_report import (  # noqa: E402,E501
    Gate2FinancialSemanticV6TransparentSmokeReportFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_stronger_candidate import (  # noqa: E402,E501
    V6_GOAL12_EXACT_MODEL_ID,
    V6_GOAL12_PROVIDER_PROFILE_ID,
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
from live_gate2_financial_semantic_v6_one_attempt import (  # noqa: E402
    _fixture,
    _is_within,
    _pretty_json,
    _read_json,
    _repository_revision,
    _validate_new_attempt_paths,
    _worktree_clean,
    _write_json_atomically,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
)


FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6QualificationPreflightFactory.create, "
    "Gate2StructuredModelClientFactory.create and "
    "smoke_financial_semantic_v6 are the only two-case V6 smoke route; "
    "Gate2FinancialSemanticV6TransparentSmokeReportFactory is the only "
    "repository-safe report projector"
)
FORBIDDEN = (
    "The V6 provider smoke must not run more or different cases, qualify a "
    "model, publish precision or recall, retry, fallback, repair, call "
    "technical cases, write private evidence inside Git or admit production"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=int, default=240)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument(
        "--execute-two-case-smoke",
        action="store_true",
        help="Authorize exactly one typed and one unclassified submission.",
    )
    mode.add_argument(
        "--resume-two-case-smoke",
        action="store_true",
        help="Submit only the case missing from a validated one-case checkpoint.",
    )
    parser.add_argument(
        "--candidate",
        choices=("nano", "stronger-haiku"),
        required=True,
    )
    parser.add_argument("--safe-receipt-path")
    parser.add_argument("--private-evidence-dir")
    parser.add_argument("--transparent-report-path")
    parser.add_argument("--interrupted-receipt-path")
    args = parser.parse_args()
    fresh_execute = bool(args.execute_two_case_smoke)
    resume_execute = bool(args.resume_two_case_smoke)
    execute = fresh_execute or resume_execute
    if execute and (
        not args.safe_receipt_path
        or not args.private_evidence_dir
        or not args.transparent_report_path
    ):
        parser.error(
            "execution requires --safe-receipt-path, "
            "--private-evidence-dir and --transparent-report-path"
        )
    if resume_execute and not args.interrupted_receipt_path:
        parser.error("resume requires --interrupted-receipt-path")
    exact_model_id, provider_profile_id = _candidate_identity(args.candidate)
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
    report_path = (
        Path(args.transparent_report_path).resolve()
        if args.transparent_report_path
        else None
    )
    interrupted_path = (
        Path(args.interrupted_receipt_path).resolve()
        if args.interrupted_receipt_path
        else None
    )
    if fresh_execute:
        _validate_new_attempt_paths(
            safe_path=safe_path,
            private_dir=private_dir,
        )
        _validate_transparent_report_path(report_path)
    elif resume_execute:
        _validate_resume_attempt_paths(
            safe_path=safe_path,
            private_dir=private_dir,
            report_path=report_path,
            interrupted_path=interrupted_path,
        )
    if execute and not _worktree_clean():
        raise ValueError("financial_semantic_v6_smoke_worktree_not_clean")

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
        exact_model_id=exact_model_id,
        provider_profile_id=provider_profile_id,
    )
    if not execute:
        print(_pretty_json(preflight), end="")
        return 0

    assert safe_path is not None
    assert private_dir is not None
    assert report_path is not None
    resume_receipt: dict[str, Any] | None = None
    resume_private_evidence: dict[str, dict[str, Any]] | None = None
    run_exact_identity = preflight["exact_identity"]
    if fresh_execute:
        private_dir.mkdir(parents=True, exist_ok=False)
        _write_json_atomically(
            safe_path,
            financial_semantic_v6_provider_smoke_initial_receipt(
                exact_identity=run_exact_identity,
            ),
            require_absent=True,
        )
    else:
        assert interrupted_path is not None
        resume_receipt = _read_json(safe_path)
        interrupted_receipt = _read_json(interrupted_path)
        if interrupted_receipt != resume_receipt:
            raise ValueError(
                "financial_semantic_v6_smoke_interrupted_receipt_mismatch"
            )
        resume_private_evidence = _read_resume_private_evidence(private_dir)
        _validate_resume_preflight(
            resume_receipt=resume_receipt,
            current_exact_identity=preflight["exact_identity"],
        )
        run_exact_identity = resume_receipt["exact_identity"]

    user = _current_user(session, base_url)
    client = _model_client(
        request_profile=(
            FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE
        ),
        provider_profile_id=provider_profile_id,
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

    transparent_cases: dict[str, dict[str, Any]] = {}

    def transparent_case_checkpoint(
        case_id: str,
        payload: dict[str, Any],
    ) -> None:
        if case_id in transparent_cases:
            raise ValueError(
                "financial_semantic_v6_transparent_case_already_written"
            )
        transparent_cases[case_id] = payload

    receipt = asyncio.run(
        smoke_financial_semantic_v6(
            fixture=fixture,
            model_client=client,
            exact_identity=run_exact_identity,
            private_case_checkpoint=private_checkpoint,
            safe_checkpoint=safe_checkpoint,
            transparent_case_checkpoint=transparent_case_checkpoint,
            resume_receipt=resume_receipt,
            resume_private_evidence=resume_private_evidence,
        )
    )
    report = Gate2FinancialSemanticV6TransparentSmokeReportFactory().render_report(
        exact_model_id=exact_model_id,
        safe_receipt_filename=safe_path.name,
        terminal_receipt=receipt,
        case_evidence=list(transparent_cases.values()),
        interrupted_receipt_filename=(
            interrupted_path.name if interrupted_path is not None else None
        ),
    )
    _write_text_atomically(report_path, report, require_absent=True)
    print(_pretty_json(receipt), end="")
    return 0 if receipt["status"] == "passed" else 2


def _candidate_identity(candidate: str) -> tuple[str, str]:
    if candidate == "nano":
        return V6_EXACT_MODEL_ID, V6_PROVIDER_PROFILE_ID
    if candidate == "stronger-haiku":
        return V6_GOAL12_EXACT_MODEL_ID, V6_GOAL12_PROVIDER_PROFILE_ID
    raise ValueError("financial_semantic_v6_smoke_candidate_invalid")


def _validate_resume_attempt_paths(
    *,
    safe_path: Path | None,
    private_dir: Path | None,
    report_path: Path | None,
    interrupted_path: Path | None,
) -> None:
    if (
        safe_path is None
        or private_dir is None
        or interrupted_path is None
        or not safe_path.is_file()
        or not safe_path.name.endswith(".safe.json")
        or not private_dir.is_dir()
        or _is_within(private_dir, REPO_ROOT)
        or not interrupted_path.is_file()
        or interrupted_path.parent != safe_path.parent
        or not interrupted_path.name.endswith(".safe.json")
    ):
        raise ValueError(
            "financial_semantic_v6_smoke_resume_path_invalid"
        )
    _validate_transparent_report_path(report_path)


def _read_resume_private_evidence(
    private_dir: Path,
) -> dict[str, dict[str, Any]]:
    paths = list(private_dir.glob("*.private.json"))
    if len(paths) != 1:
        raise ValueError(
            "financial_semantic_v6_smoke_resume_private_evidence_invalid"
        )
    evidence = _read_json(paths[0])
    case_id = str(evidence.get("case_id") or "")
    if paths[0].name != f"{case_id}.private.json":
        raise ValueError(
            "financial_semantic_v6_smoke_resume_private_evidence_invalid"
        )
    return {case_id: evidence}


def _validate_resume_preflight(
    *,
    resume_receipt: dict[str, Any],
    current_exact_identity: dict[str, Any],
) -> None:
    previous = json.loads(json.dumps(resume_receipt.get("exact_identity")))
    current = json.loads(json.dumps(current_exact_identity))
    for value in (previous, current):
        if not isinstance(value, dict):
            raise ValueError(
                "financial_semantic_v6_smoke_resume_identity_invalid"
            )
        value.pop("identity_hash", None)
        value.pop("repository_revision", None)
    if previous != current:
        raise ValueError(
            "financial_semantic_v6_smoke_resume_authority_drift"
        )


def _validate_transparent_report_path(report_path: Path | None) -> None:
    reports_root = (REPO_ROOT / "docs" / "reports").resolve()
    try:
        relative = report_path.relative_to(reports_root) if report_path else None
    except ValueError as exc:
        raise ValueError(
            "financial_semantic_v6_transparent_report_path_invalid"
        ) from exc
    if (
        relative is None
        or len(relative.parts) != 2
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", relative.parts[0]) is None
        or not report_path.name.endswith(".report.md")
        or report_path.exists()
    ):
        raise ValueError(
            "financial_semantic_v6_transparent_report_path_invalid"
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)


def _write_text_atomically(
    path: Path,
    value: str,
    *,
    require_absent: bool = False,
) -> None:
    if require_absent and path.exists():
        raise ValueError(
            "financial_semantic_v6_transparent_report_already_written"
        )
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


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
