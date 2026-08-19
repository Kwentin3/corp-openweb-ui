#!/usr/bin/env python3
"""Run one frozen, single-attempt LLM metadata proof per real document."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
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
)
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
    Gate3LlmMetadataAdapterFactory,
)
from broker_reports_gate1.gate3_metadata_source_facts import (  # noqa: E402
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
    Gate3MetadataSourceFactRuntimeFactory,
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


PRIVATE_RESULT_NAME = "g561-result.private.json"
SAFE_RESULT_NAME = "g561-result.safe.json"
EXPECTED_CASE_ALIASES = ("pdf_002", "pdf_024", "holdout_a", "holdout_b")
SOURCE_ABSENCE_FACT_TYPES = {
    "PERSON_BIRTH_DATE",
    "TAXPAYER_TAX_IDENTIFIER",
    "PERSON_CITIZENSHIP",
    "DOCUMENT_NUMBER",
}

FACTORY_REQUIRED = (
    "Gate3LlmMetadataAdapterFactory.create and "
    "Gate2StructuredModelClientFactory.create are the only model route"
)
FORBIDDEN = (
    "retry, best-of-N, per-document prompt, output repair, oracle injection into "
    "model context, direct provider request, source mutation or product activation"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-one-clean-attempt-per-document", action="store_true")
    parser.add_argument("--frozen-corpus", type=Path, required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not args.execute_one_clean_attempt_per_document:
        raise SystemExit("explicit_execute_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 600:
        raise SystemExit("timeout_out_of_bounds")

    frozen_path = args.frozen_corpus.resolve()
    output_root = args.private_output_root.resolve()
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise SystemExit("private_output_must_be_outside_repository")
    if output_root.exists():
        raise SystemExit("private_output_root_must_be_new")
    frozen = _read_json(frozen_path)
    _validate_frozen_contract(frozen)
    cases = frozen["cases"]
    provider_profile_id = frozen["provider_profile"]
    model_id = frozen["model_id"]
    gate2_provider_profile(provider_profile_id)

    source_snapshots = {
        item["alias"]: _store_snapshot(Path(item["source_store_root"]).resolve())
        for item in cases
    }
    output_root.mkdir(parents=True)

    env = _read_env(args.env_file.resolve())
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.get(_url(base_url, "/health"), timeout=20).raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    live_user_id = str(_current_user(session, base_url).get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")

    submissions = {"count": 0}
    base_completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def one_attempt_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return base_completion(form_data=form_data, **kwargs)

    model_client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_LLM_METADATA_REQUEST_PROFILE,
            provider_profile_id=provider_profile_id,
            capability_probe=False,
            economy_budget_enforcement=False,
        ),
        user=SimpleNamespace(id=live_user_id),
        request=_request_context(session, base_url),
        completion_resolver=lambda _user_id: (
            one_attempt_completion,
            SimpleNamespace(id=live_user_id),
        ),
    ).create()

    private_cases: list[dict[str, Any]] = []
    safe_cases: list[dict[str, Any]] = []
    for frozen_case in cases:
        alias = frozen_case["alias"]
        source_store = Path(frozen_case["source_store_root"]).resolve()
        working_store = output_root / alias / "working-store"
        working_store.parent.mkdir(parents=True)
        shutil.copytree(source_store, working_store)
        case_result = asyncio.run(
            _run_case(
                frozen_case=frozen_case,
                working_store=working_store,
                model_client=model_client,
                model_id=model_id,
                submissions=submissions,
            )
        )
        private_cases.append(case_result)
        safe_cases.append(_safe_case(case_result))

    source_unchanged = all(
        source_snapshots[item["alias"]]
        == _store_snapshot(Path(item["source_store_root"]).resolve())
        for item in cases
    )
    all_passed = (
        source_unchanged
        and submissions["count"] == len(cases)
        and all(item["case_passed"] for item in private_cases)
    )
    failure_classes = sorted(
        {
            str(item["failure_class"])
            for item in private_cases
            if item.get("failure_class")
        }
    )
    terminal = (
        "LLM_METADATA_ADAPTER_GENERALIZATION_PROVEN"
        if all_passed
        else "LLM_METADATA_ADAPTER_NOT_YET_RELIABLE"
    )
    private_result = {
        "schema_version": "broker_reports_g561_private_result_v1",
        "goal": "G5.61",
        "terminal": terminal,
        "exact_failure_classes": failure_classes,
        "frozen_contract": copy.deepcopy(frozen),
        "provider_submissions_total": submissions["count"],
        "source_stores_unchanged": source_unchanged,
        "cases": private_cases,
    }
    safe_result = {
        "schema_version": "broker_reports_g561_safe_result_v1",
        "goal": "G5.61",
        "terminal": terminal,
        "exact_failure_classes": failure_classes,
        "contract_version": frozen["contract_version"],
        "instruction_version": frozen["instruction_version"],
        "context_policy_version": frozen["context_policy_version"],
        "output_schema_version": frozen["output_schema_version"],
        "provider_profile": provider_profile_id,
        "model_id": model_id,
        "documents": len(cases),
        "provider_submissions_total": submissions["count"],
        "provider_submissions_per_document": (
            1 if submissions["count"] == len(cases) else None
        ),
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "broker_specific_prompts": 0,
        "broker_specific_runtime_branches": 0,
        "fixed_page_or_column_rules": 0,
        "human_language_regex_growth": 0,
        "source_stores_unchanged": source_unchanged,
        "cases": safe_cases,
    }
    _write_json(output_root / PRIVATE_RESULT_NAME, private_result)
    _write_json(output_root / SAFE_RESULT_NAME, safe_result)
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    return 0 if all_passed else 2


async def _run_case(
    *,
    frozen_case: dict[str, Any],
    working_store: Path,
    model_client: Any,
    model_id: str,
    submissions: dict[str, int],
) -> dict[str, Any]:
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=working_store / "artifacts.sqlite3",
            payload_root=working_store / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        **frozen_case["context"],
        allow_private=True,
    )
    document_id = frozen_case["document_id"]
    records = [
        record
        for record in ArtifactResolver(store).catalog_case(context)
        if record.artifact_type == "broker_reports_canonical_artifact_v1"
        and record.document_id == document_id
    ]
    if len(records) != 1:
        raise SystemExit(f"frozen_canonical_record_ambiguous:{frozen_case['alias']}")
    record = records[0]
    artifact = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read(
            record.artifact_id,
            context,
        )
    )
    if (
        record.artifact_id != frozen_case["canonical_artifact_id"]
        or artifact.get("artifact_id") != frozen_case["canonical_version_id"]
        or artifact.get("canonical_root_hash") != frozen_case["canonical_root_sha256"]
    ):
        raise SystemExit(f"frozen_canonical_identity_changed:{frozen_case['alias']}")

    oracle_collection = (
        Gate3MetadataSourceFactRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .collect(context=context)
    )
    oracle_facts = [
        fact
        for fact in oracle_collection["metadata_facts"]
        if fact["source_binding"]["document_id"] == document_id
    ]
    _validate_oracle(frozen_case, oracle_facts)
    before_submissions = submissions["count"]
    attempt = None
    error = None
    try:
        attempt = await Gate3LlmMetadataAdapterFactory(
            store=store,
            read_enabled=True,
            model_client=model_client,
            model_id=model_id,
        ).create(document_id=document_id, context=context)
    except Exception as exc:  # provider boundary evidence must remain inspectable
        error = {
            "type": type(exc).__name__,
            "code": getattr(exc, "code", None),
            "failure_class": getattr(exc, "failure_class", None),
            "message": str(exc),
            "execution_metadata": _jsonable(getattr(exc, "execution_metadata", None)),
            "raw_output": _jsonable(getattr(exc, "raw_output", None)),
        }
    submission_delta = submissions["count"] - before_submissions
    if attempt is None:
        failure_class = (
            (error or {}).get("failure_class")
            or (error or {}).get("code")
            or (error or {}).get("type")
            or "unknown_provider_failure"
        )
        return {
            "alias": frozen_case["alias"],
            "case_passed": False,
            "failure_class": failure_class,
            "provider_submissions": submission_delta,
            "oracle_fact_count": len(oracle_facts),
            "validation_status": "not_reached",
            "error": error,
        }

    validated_facts = (
        attempt.validated_output["metadata_facts"]
        if attempt.validated_output is not None
        else []
    )
    comparison = _compare_facts(
        oracle_facts=oracle_facts,
        candidate_facts=validated_facts,
    )
    source_absence_count = sum(
        fact["fact_type"] in SOURCE_ABSENCE_FACT_TYPES for fact in validated_facts
    )
    case_passed = (
        submission_delta == 1
        and attempt.validation_status == "validated"
        and comparison["semantic_exact"]
        and comparison["oracle_node_provenance_exact"]
        and source_absence_count == 0
        and attempt.metrics["retries"] == 0
        and attempt.metrics["best_of_n"] is False
        and attempt.metrics["manual_output_repair"] is False
    )
    failure_class = None
    if not case_passed:
        if attempt.validation_status != "validated":
            failure_class = attempt.validation_error_code
        elif not comparison["semantic_exact"]:
            failure_class = "semantic_oracle_mismatch"
        elif not comparison["oracle_node_provenance_exact"]:
            failure_class = "oracle_provenance_mismatch"
        elif source_absence_count:
            failure_class = "source_absence_field_invented"
        elif submission_delta != 1:
            failure_class = "provider_submission_count_invalid"
        else:
            failure_class = "single_attempt_contract_invalid"
    return {
        "alias": frozen_case["alias"],
        "case_passed": case_passed,
        "failure_class": failure_class,
        "provider_submissions": submission_delta,
        "oracle_fact_count": len(oracle_facts),
        "validation_status": attempt.validation_status,
        "validation_error_code": attempt.validation_error_code,
        "comparison": comparison,
        "source_absence_facts": source_absence_count,
        "metrics": copy.deepcopy(attempt.metrics),
        "context_package": copy.deepcopy(attempt.context_package),
        "binding_registry": copy.deepcopy(attempt.binding_registry),
        "model_visible_request": copy.deepcopy(attempt.model_visible_request),
        "final_provider_request": copy.deepcopy(attempt.final_provider_request),
        "raw_provider_response": copy.deepcopy(attempt.raw_provider_response),
        "raw_model_output": copy.deepcopy(attempt.raw_model_output),
        "validated_output": copy.deepcopy(attempt.validated_output),
        "oracle_facts": copy.deepcopy(oracle_facts),
        "execution_metadata": _jsonable(attempt.execution_metadata),
    }


def _compare_facts(
    *,
    oracle_facts: list[dict[str, Any]],
    candidate_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    oracle_semantic = _semantic_entries(oracle_facts)
    candidate_semantic = _semantic_entries(candidate_facts)
    oracle_nodes: dict[str, set[str]] = {}
    for fact in oracle_facts:
        key = _semantic_key(fact)
        oracle_nodes.setdefault(key, set()).add(fact["source_binding"]["node_id"])
    provenance_exact = all(
        fact["source_binding"]["node_id"]
        in oracle_nodes.get(_semantic_key(fact), set())
        for fact in candidate_facts
    ) and len(candidate_facts) == len(oracle_facts)
    oracle_types = Counter(fact["fact_type"] for fact in oracle_facts)
    candidate_types = Counter(fact["fact_type"] for fact in candidate_facts)
    return {
        "semantic_exact": candidate_semantic == oracle_semantic,
        "oracle_node_provenance_exact": provenance_exact,
        "missing_facts": len(oracle_semantic - candidate_semantic),
        "invented_facts": len(candidate_semantic - oracle_semantic),
        "oracle_fact_type_counts": dict(sorted(oracle_types.items())),
        "candidate_fact_type_counts": dict(sorted(candidate_types.items())),
        "duplicate_assertions": len(candidate_facts) - len(candidate_semantic),
    }


def _semantic_entries(facts: list[dict[str, Any]]) -> set[str]:
    return {_semantic_key(fact) for fact in facts}


def _semantic_key(fact: dict[str, Any]) -> str:
    return json.dumps(
        (fact["fact_type"], fact["value"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_oracle(
    frozen_case: dict[str, Any],
    oracle_facts: list[dict[str, Any]],
) -> None:
    type_counts = dict(
        sorted(Counter(fact["fact_type"] for fact in oracle_facts).items())
    )
    semantic = sorted(
        ((fact["fact_type"], fact["value"]) for fact in oracle_facts),
        key=_json_sort_key,
    )
    provenance = sorted(
        ((fact["fact_type"], fact["source_binding"]) for fact in oracle_facts),
        key=_json_sort_key,
    )
    if (
        len(oracle_facts) != frozen_case["oracle_fact_count"]
        or type_counts != frozen_case["oracle_fact_type_counts"]
        or _sha256_json(semantic) != frozen_case["oracle_semantic_sha256"]
        or _sha256_json(provenance) != frozen_case["oracle_provenance_sha256"]
    ):
        raise SystemExit(f"frozen_oracle_changed:{frozen_case['alias']}")


def _validate_frozen_contract(frozen: dict[str, Any]) -> None:
    aliases = tuple(item.get("alias") for item in frozen.get("cases") or [])
    if (
        frozen.get("schema_version") != "broker_reports_g561_frozen_corpus_private_v1"
        or frozen.get("frozen_before_code") is not True
        or frozen.get("contract_version") != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or frozen.get("instruction_version") != GATE3_LLM_METADATA_INSTRUCTION_VERSION
        or frozen.get("context_policy_version")
        != GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION
        or frozen.get("output_schema_version")
        != GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION
        or aliases != EXPECTED_CASE_ALIASES
        or any(
            not Path(item.get("source_store_root") or "").is_absolute()
            for item in frozen["cases"]
        )
    ):
        raise SystemExit("frozen_contract_invalid")


def _safe_case(item: dict[str, Any]) -> dict[str, Any]:
    metrics = item.get("metrics") or {}
    comparison = item.get("comparison") or {}
    return {
        "alias": item["alias"],
        "case_passed": item["case_passed"],
        "failure_class": item.get("failure_class"),
        "provider_submissions": item.get("provider_submissions"),
        "validation_status": item.get("validation_status"),
        "validation_error_code": item.get("validation_error_code"),
        "oracle_fact_count": item.get("oracle_fact_count"),
        "candidate_fact_count": metrics.get("validated_facts", 0),
        "semantic_exact": comparison.get("semantic_exact", False),
        "oracle_node_provenance_exact": comparison.get(
            "oracle_node_provenance_exact", False
        ),
        "missing_facts": comparison.get("missing_facts"),
        "invented_facts": comparison.get("invented_facts"),
        "duplicate_assertions": comparison.get("duplicate_assertions"),
        "source_absence_facts": item.get("source_absence_facts"),
        "selected_targets": metrics.get("selected_targets"),
        "rendered_context_chars": metrics.get("rendered_context_chars"),
        "final_model_input_chars": metrics.get("final_model_input_chars"),
        "input_tokens": metrics.get("input_tokens"),
        "output_tokens": metrics.get("output_tokens"),
        "total_tokens": metrics.get("total_tokens"),
        "duration_ms": metrics.get("duration_ms"),
    }


def _store_snapshot(root: Path) -> dict[str, str]:
    if not (root / "artifacts.sqlite3").is_file():
        raise SystemExit(f"source_store_missing:{root}")
    return {
        path.relative_to(root).as_posix(): _sha256_bytes(path.read_bytes())
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return copy.deepcopy(value)
    if hasattr(value, "__dict__"):
        return copy.deepcopy(vars(value))
    return repr(value)


def _json_sort_key(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"json_object_required:{path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
