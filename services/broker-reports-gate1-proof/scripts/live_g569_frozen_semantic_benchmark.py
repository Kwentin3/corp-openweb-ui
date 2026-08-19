#!/usr/bin/env python3
"""Run one frozen G5.69 model phase: 5 independent shots x 2 cases."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver  # noqa: E402
from broker_reports_gate1.canonical_store import CanonicalReaderFactory  # noqa: E402
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_LLM_METADATA_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    Gate2ProviderAdapterFactory,
)
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    Gate3LlmMetadataAdapterFactory,
    build_metadata_context_package,
    compose_metadata_model_visible_request,
    metadata_proposal_response_schema,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _base_url,
    _is_within,
    _read_env,
    _signin,
    _url,
)
from live_g561_llm_metadata_generalization import (  # noqa: E402
    _jsonable,
    _store_snapshot,
)


FACTORY_REQUIRED = (
    "Gate3LlmMetadataAdapterFactory.create and "
    "Gate2StructuredModelClientFactory.create are the only semantic route"
)
FORBIDDEN = (
    "direct provider calls, retry replacement, best-of-N, voting, result "
    "selection, output repair, model-specific prompt or source-store mutation"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-frozen-ten-calls", action="store_true")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--model-slot", choices=("flash", "comparison"), required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    if not args.execute_frozen_ten_calls:
        raise SystemExit("g569_explicit_execution_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 900:
        raise SystemExit("g569_timeout_out_of_bounds")
    output_root = args.private_output_root.resolve()
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise SystemExit("g569_output_inside_repository")
    if output_root.exists():
        raise SystemExit("g569_output_root_must_be_new")
    freeze = _read_json(args.freeze.resolve())
    _validate_freeze(freeze)
    slot = freeze[args.model_slot]
    profile_id = slot["provider_profile"]
    model_id = slot["model_id"]
    profile = gate2_provider_profile(profile_id)

    source_snapshots = {
        case["case_id"]: _store_snapshot(Path(case["source_store_root"]).resolve())
        for case in freeze["cases"]
    }
    output_root.mkdir(parents=True)
    working: dict[str, dict[str, Any]] = {}
    for case in freeze["cases"]:
        case_root = output_root / case["case_id"]
        working_store = case_root / "working-store"
        case_root.mkdir(parents=True)
        shutil.copytree(Path(case["source_store_root"]).resolve(), working_store)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=working_store / "artifacts.sqlite3",
                payload_root=working_store / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(**case["context"], allow_private=True)
        request, package, registry = _preflight_case(
            case=case,
            store=store,
            context=context,
            profile_id=profile_id,
            model_id=model_id,
        )
        working[case["case_id"]] = {
            "store": store,
            "context": context,
            "request": request,
            "context_package": package,
            "binding_registry": registry,
        }

    env = _read_env(args.env_file.resolve())
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.get(_url(base_url, "/health"), timeout=20).raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    live_user_id = str(_current_user(session, base_url).get("id") or "")
    if not live_user_id:
        raise SystemExit("g569_authenticated_user_missing")

    submissions = {"count": 0}
    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def one_shot_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return completion(form_data=form_data, **kwargs)

    model_client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_LLM_METADATA_REQUEST_PROFILE,
            provider_profile_id=profile_id,
            capability_probe=False,
            economy_budget_enforcement=False,
        ),
        user=SimpleNamespace(id=live_user_id),
        request=_request_context(session, base_url),
        completion_resolver=lambda _user_id: (
            one_shot_completion,
            SimpleNamespace(id=live_user_id),
        ),
    ).create()

    journal_path = output_root / "journal.private.jsonl"
    private_runs: list[dict[str, Any]] = []
    safe_runs: list[dict[str, Any]] = []
    for case in freeze["cases"]:
        state = working[case["case_id"]]
        for run_ordinal in range(1, freeze["runs_per_case_per_model"] + 1):
            before = submissions["count"]
            attempt = None
            error = None
            try:
                attempt = asyncio.run(
                    Gate3LlmMetadataAdapterFactory(
                        store=state["store"],
                        read_enabled=True,
                        model_client=model_client,
                        model_id=model_id,
                    ).create(
                        document_id=case["document_id"],
                        context=state["context"],
                    )
                )
            except Exception as exc:  # each scheduled shot must retain its terminal
                error = _error_receipt(exc)
            delta = submissions["count"] - before
            if delta != 1:
                raise SystemExit(
                    f"g569_exactly_one_submission_required:{case['case_id']}:{run_ordinal}:{delta}"
                )
            run = _private_run(
                case=case,
                run_ordinal=run_ordinal,
                attempt=attempt,
                error=error,
                expected_request_sha256=case["model_visible_request_sha256"],
            )
            private_runs.append(run)
            safe_run = _safe_run(run)
            safe_runs.append(safe_run)
            with journal_path.open("a", encoding="utf-8") as journal:
                journal.write(json.dumps(run, ensure_ascii=False) + "\n")

    source_unchanged = all(
        source_snapshots[case["case_id"]]
        == _store_snapshot(Path(case["source_store_root"]).resolve())
        for case in freeze["cases"]
    )
    semantic_results = sum(run["semantic_result"] for run in safe_runs)
    transport_failures = sum(run["transport_failure"] for run in safe_runs)
    expected_calls = len(freeze["cases"]) * freeze["runs_per_case_per_model"]
    execution_complete = submissions["count"] == expected_calls and source_unchanged
    benchmark_complete = execution_complete and transport_failures == 0
    private = {
        "schema_version": "broker_reports_g569_model_phase_private_v1",
        "goal": "G5.69",
        "model_slot": args.model_slot,
        "provider_profile": profile_id,
        "model_id": model_id,
        "freeze_sha256": _sha256_json(freeze),
        "provider_submissions": submissions["count"],
        "scheduled_runs": expected_calls,
        "semantic_results": semantic_results,
        "transport_failures": transport_failures,
        "retries": 0,
        "best_of_n": False,
        "voting": False,
        "manual_output_repair": False,
        "result_selection": False,
        "source_stores_unchanged": source_unchanged,
        "execution_complete": execution_complete,
        "benchmark_phase_complete": benchmark_complete,
        "cases": [
            {
                "case_id": case["case_id"],
                "alias": case["alias"],
                "model_visible_request_sha256": case[
                    "model_visible_request_sha256"
                ],
                "context_package": working[case["case_id"]]["context_package"],
                "binding_registry": working[case["case_id"]]["binding_registry"],
            }
            for case in freeze["cases"]
        ],
        "runs": private_runs,
    }
    safe = {
        "schema_version": "broker_reports_g569_model_phase_safe_v1",
        "goal": "G5.69",
        "terminal": (
            "MODEL_PHASE_COMPLETE"
            if benchmark_complete
            else "MODEL_PHASE_TRANSPORT_INCOMPLETE"
        ),
        "model_slot": args.model_slot,
        "provider_profile": profile_id,
        "model_id": model_id,
        "freeze_sha256": private["freeze_sha256"],
        "provider_submissions": submissions["count"],
        "scheduled_runs": expected_calls,
        "semantic_results": semantic_results,
        "transport_failures": transport_failures,
        "retries": 0,
        "best_of_n": False,
        "voting": False,
        "manual_output_repair": False,
        "result_selection": False,
        "source_stores_unchanged": source_unchanged,
        "execution_complete": execution_complete,
        "benchmark_phase_complete": benchmark_complete,
        "runs": safe_runs,
        "private_values_committed": False,
    }
    _write_json(output_root / "result.private.json", private)
    _write_json(output_root / "result.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if benchmark_complete else 2


def _preflight_case(
    *,
    case: dict[str, Any],
    store: Any,
    context: ArtifactAccessContext,
    profile_id: str,
    model_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    records = [
        record
        for record in ArtifactResolver(store).catalog_case(context)
        if record.artifact_type == "broker_reports_canonical_artifact_v1"
        and record.document_id == case["document_id"]
    ]
    if len(records) != 1:
        raise SystemExit("g569_preflight_canonical_ambiguous")
    artifact = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read(records[0].artifact_id, context)
    )
    if (
        artifact.get("artifact_id") != case["canonical_version_id"]
        or artifact.get("canonical_root_hash") != case["canonical_root_sha256"]
    ):
        raise SystemExit("g569_preflight_canonical_changed")
    package, registry = build_metadata_context_package(
        artifact=artifact,
        document_id=case["document_id"],
        canonical_version_id=artifact["artifact_id"],
    )
    request = compose_metadata_model_visible_request(
        context_package=package,
        response_schema=metadata_proposal_response_schema(),
    )
    if _sha256_json(request) != case["model_visible_request_sha256"]:
        raise SystemExit(f"g569_model_visible_request_drift:{case['case_id']}")
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=GATE3_LLM_METADATA_REQUEST_PROFILE
    ).build_from_sealed_gate3_metadata(
        model_visible_request=request,
        model_id=model_id,
    )
    prepared = Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile(profile_id)
    ).create().prepare_gate3_metadata_form_data(
        form_data=form_data,
        response_format=request["response_format"],
    )
    frozen_preflight = next(
        item
        for item in case["model_preflights"]
        if item["provider_profile"] == profile_id and item["model_id"] == model_id
    )
    if (
        _sha256_json(prepared.form_data)
        != frozen_preflight["prepared_request_sha256"]
        or prepared.canonical_schema_hash
        != frozen_preflight["canonical_schema_sha256"]
        or _sha256_json(prepared.provider_visible_schema)
        != frozen_preflight["provider_visible_schema_sha256"]
    ):
        raise SystemExit(f"g569_prepared_request_drift:{case['case_id']}")
    return request, package, registry


def _private_run(
    *,
    case: dict[str, Any],
    run_ordinal: int,
    attempt: Any,
    error: dict[str, Any] | None,
    expected_request_sha256: str,
) -> dict[str, Any]:
    request_hash = (
        _sha256_json(attempt.model_visible_request) if attempt is not None else None
    )
    if request_hash is not None and request_hash != expected_request_sha256:
        raise SystemExit(
            f"g569_runtime_request_drift:{case['case_id']}:{run_ordinal}"
        )
    return {
        "case_id": case["case_id"],
        "alias": case["alias"],
        "run_ordinal": run_ordinal,
        "semantic_result": attempt is not None,
        "transport_failure": attempt is None,
        "model_visible_request_sha256": request_hash or expected_request_sha256,
        "validation_status": (
            attempt.validation_status if attempt is not None else "not_reached"
        ),
        "validation_error_code": (
            attempt.validation_error_code if attempt is not None else None
        ),
        "final_provider_request_sha256": (
            _sha256_json(attempt.final_provider_request)
            if attempt is not None
            else None
        ),
        "raw_provider_response": (
            _jsonable(attempt.raw_provider_response) if attempt is not None else None
        ),
        "raw_model_output": (
            _jsonable(attempt.raw_model_output) if attempt is not None else None
        ),
        "validated_output": (
            _jsonable(attempt.validated_output) if attempt is not None else None
        ),
        "execution_metadata": (
            _jsonable(attempt.execution_metadata) if attempt is not None else None
        ),
        "metrics": _jsonable(attempt.metrics) if attempt is not None else None,
        "error": error,
    }


def _safe_run(run: dict[str, Any]) -> dict[str, Any]:
    metrics = run.get("metrics") or {}
    error = run.get("error") or {}
    return {
        "case_id": run["case_id"],
        "alias": run["alias"],
        "run_ordinal": run["run_ordinal"],
        "semantic_result": run["semantic_result"],
        "transport_failure": run["transport_failure"],
        "model_visible_request_sha256": run["model_visible_request_sha256"],
        "validation_status": run["validation_status"],
        "validation_error_code": run["validation_error_code"],
        "input_tokens": metrics.get("input_tokens"),
        "output_tokens": metrics.get("output_tokens"),
        "total_tokens": metrics.get("total_tokens"),
        "duration_ms": metrics.get("duration_ms"),
        "error_type": error.get("type"),
        "error_code": error.get("code"),
        "error_failure_class": error.get("failure_class"),
    }


def _error_receipt(exc: Exception) -> dict[str, Any]:
    return {
        "type": type(exc).__name__,
        "code": getattr(exc, "code", None),
        "failure_class": getattr(exc, "failure_class", None),
        "message": str(exc),
        "execution_metadata": _jsonable(getattr(exc, "execution_metadata", None)),
        "raw_output": _jsonable(getattr(exc, "raw_output", None)),
    }


def _validate_freeze(freeze: dict[str, Any]) -> None:
    if (
        freeze.get("schema_version")
        != "broker_reports_g569_benchmark_freeze_private_v1"
        or freeze.get("goal") != "G5.69"
        or freeze.get("frozen_before_semantic_calls") is not True
        or freeze.get("semantic_provider_calls") != 0
        or freeze.get("runs_per_case_per_model") != 5
        or tuple(case.get("case_id") for case in freeze.get("cases") or [])
        != ("case_f", "case_c")
        or freeze.get("temperature_override") is not None
        or freeze.get("seed_override") is not None
        or freeze.get("best_of_models") is not False
        or freeze.get("production_code_changes") != 0
    ):
        raise SystemExit("g569_freeze_invalid")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("g569_json_object_required")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
