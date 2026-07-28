#!/usr/bin/env python3
"""Preflight or execute the exact six-call Gate 2 V6 Slim diagnostic."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

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
from broker_reports_gate1.gate2_financial_semantic_v6_model_diagnostic import (  # noqa: E402,E501
    Gate2FinancialSemanticV6SlimDiagnosticFactory,
    financial_semantic_v6_slim_diagnostic_initial_receipt,
    run_financial_semantic_v6_slim_diagnostic,
)
from broker_reports_gate1.gate2_financial_semantic_v6_model_diagnostic_report import (  # noqa: E402,E501
    Gate2FinancialSemanticV6SlimDiagnosticReportFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_stronger_candidate import (  # noqa: E402,E501
    V6_GOAL12_EXACT_MODEL_ID,
    V6_GOAL12_PROVIDER_PROFILE_ID,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _model_client,
    _published_model_ids,
    _request_context,
)
from live_gate2_financial_semantic_v6_one_attempt import (  # noqa: E402
    _fixture,
    _pretty_json,
    _repository_revision,
    _worktree_clean,
    _write_json_atomically,
)
from live_gate2_financial_semantic_v6_two_case_smoke import (  # noqa: E402
    _write_text_atomically,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
)


FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6SlimDiagnosticFactory.create, "
    "Gate2StructuredModelClientFactory.create and "
    "run_financial_semantic_v6_slim_diagnostic are the only GOAL 4 live "
    "route; Gate2FinancialSemanticV6SlimDiagnosticReportFactory is the only "
    "repository-safe report projector"
)
FORBIDDEN = (
    "The script must not run the full benchmark, retry, resume, fallback, "
    "repair, call a provider outside the one six-cell execution, expose raw "
    "provider envelopes or mutate product runtime"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=int, default=240)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument(
        "--execute-six-submission-diagnostic",
        action="store_true",
        help=(
            "Authorize exactly Nano canonical x2, Haiku canonical x2 and "
            "Nano reversed x2."
        ),
    )
    parser.add_argument("--safe-receipt-path")
    parser.add_argument("--report-path")
    args = parser.parse_args()
    execute = bool(args.execute_six_submission_diagnostic)
    if execute and (
        not args.safe_receipt_path or not args.report_path
    ):
        parser.error(
            "execution requires --safe-receipt-path and --report-path"
        )

    safe_path = (
        Path(args.safe_receipt_path).resolve()
        if args.safe_receipt_path
        else None
    )
    report_path = (
        Path(args.report_path).resolve() if args.report_path else None
    )
    if execute:
        _validate_output_path(
            path=safe_path,
            suffix=".receipt.safe.json",
        )
        _validate_output_path(
            path=report_path,
            suffix=".report.md",
        )
        if not _worktree_clean():
            raise ValueError(
                "financial_semantic_v6_slim_diagnostic_worktree_not_clean"
            )

    fixture = _fixture()
    plan = Gate2FinancialSemanticV6SlimDiagnosticFactory().create(
        fixture=fixture,
        repository_revision=_repository_revision(),
    )
    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    published = _published_model_ids(session, base_url)
    required_models = {V6_EXACT_MODEL_ID, V6_GOAL12_EXACT_MODEL_ID}
    missing_models = sorted(required_models - published)
    if missing_models:
        raise ValueError(
            "financial_semantic_v6_slim_diagnostic_model_unpublished"
        )
    preflight = {
        **plan.safe_summary(),
        "live_model_presence": {
            "nano": V6_EXACT_MODEL_ID in published,
            "haiku": V6_GOAL12_EXACT_MODEL_ID in published,
        },
    }
    if not execute:
        print(_pretty_json(preflight), end="")
        return 0

    assert safe_path is not None
    assert report_path is not None
    _write_json_atomically(
        safe_path,
        financial_semantic_v6_slim_diagnostic_initial_receipt(
            plan=plan
        ),
        require_absent=True,
    )
    user = _current_user(session, base_url)
    request_context = _request_context(session, base_url)
    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout,
    )
    clients = {
        V6_PROVIDER_PROFILE_ID: _model_client(
            request_profile=(
                FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
            ),
            provider_profile_id=V6_PROVIDER_PROFILE_ID,
            user_id=str(user["id"]),
            request_context=request_context,
            completion=completion,
        ),
        V6_GOAL12_PROVIDER_PROFILE_ID: _model_client(
            request_profile=(
                FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
            ),
            provider_profile_id=V6_GOAL12_PROVIDER_PROFILE_ID,
            user_id=str(user["id"]),
            request_context=request_context,
            completion=completion,
        ),
    }

    def safe_checkpoint(payload: dict) -> None:
        _write_json_atomically(safe_path, payload)

    receipt = asyncio.run(
        run_financial_semantic_v6_slim_diagnostic(
            plan=plan,
            model_clients=clients,
            safe_checkpoint=safe_checkpoint,
        )
    )
    report = Gate2FinancialSemanticV6SlimDiagnosticReportFactory().render(
        safe_receipt_filename=safe_path.name,
        terminal_receipt=receipt,
    )
    _write_text_atomically(
        report_path,
        report,
        require_absent=True,
    )
    print(_pretty_json(receipt), end="")
    return 0 if receipt["status"] == "passed" else 2


def _validate_output_path(
    *,
    path: Path | None,
    suffix: str,
) -> None:
    reports_root = (REPO_ROOT / "docs" / "reports").resolve()
    try:
        relative = path.relative_to(reports_root) if path else None
    except ValueError as exc:
        raise ValueError(
            "financial_semantic_v6_slim_diagnostic_output_path_invalid"
        ) from exc
    if (
        relative is None
        or len(relative.parts) != 2
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", relative.parts[0])
        is None
        or not path.name.endswith(suffix)
        or not path.parent.is_dir()
        or path.exists()
    ):
        raise ValueError(
            "financial_semantic_v6_slim_diagnostic_output_path_invalid"
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
