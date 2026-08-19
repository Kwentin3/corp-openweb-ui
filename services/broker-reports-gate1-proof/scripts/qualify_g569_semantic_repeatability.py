#!/usr/bin/env python3
"""Qualify frozen G5.69 Flash runs without selecting or repairing outputs."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver  # noqa: E402
from broker_reports_gate1.canonical_store import CanonicalReaderFactory  # noqa: E402
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
    Gate3LlmMetadataAdapterError,
    _decode_response,
    _direct_structural_relation,
    _normalized_value,
    validate_metadata_proposal,
)


MODEL_ID = "models/gemini-3.5-flash"

FACTORY_REQUIRED = (
    "validate_metadata_proposal and CanonicalReaderFactory.create are the "
    "only per-run qualification route"
)
FORBIDDEN = (
    "provider calls, result selection, majority vote, output repair, oracle "
    "injection into execution or replacement runs"
)


class G569QualificationError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--flash-result", type=Path, required=True)
    parser.add_argument("--g568-goal-freeze", type=Path, required=True)
    parser.add_argument("--comparison-abort", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    outputs = (args.private_output.resolve(), args.safe_output.resolve())
    if any(output.exists() for output in outputs):
        raise G569QualificationError("g569_qualification_output_must_be_new")
    freeze = _read_json(args.freeze.resolve())
    flash = _read_json(args.flash_result.resolve())
    g568 = _read_json(args.g568_goal_freeze.resolve())
    comparison_abort = _read_json(args.comparison_abort.resolve())
    private, safe = qualify(
        freeze=freeze,
        flash=flash,
        flash_root=args.flash_result.resolve().parent,
        g568=g568,
        comparison_abort=comparison_abort,
    )
    for output, value in zip(outputs, (private, safe), strict=True):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0


def qualify(
    *,
    freeze: dict[str, Any],
    flash: dict[str, Any],
    flash_root: Path,
    g568: dict[str, Any],
    comparison_abort: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_inputs(freeze, flash, g568, comparison_abort)
    flash_case_state = {case["case_id"]: case for case in flash["cases"]}
    private_cases: list[dict[str, Any]] = []
    for frozen_case in freeze["cases"]:
        artifact = _read_canonical(
            store_root=flash_root / frozen_case["case_id"] / "working-store",
            frozen_case=frozen_case,
        )
        case_runs = [
            run
            for run in flash["runs"]
            if run["case_id"] == frozen_case["case_id"]
        ]
        private_cases.append(
            _qualify_case(
                frozen_case=frozen_case,
                result_case=flash_case_state[frozen_case["case_id"]],
                runs=case_runs,
                artifact=artifact,
                known_failure=g568["failing_case"],
            )
        )

    totals_keys = (
        "correct",
        "missed",
        "semantic_extras",
        "wrong_roles",
        "wrong_value_boundary",
        "structural_rejections",
        "invented_literals",
        "invalid_provenance",
        "duplicates",
    )
    totals = {
        key: sum(case["totals"][key] for case in private_cases)
        for key in totals_keys
    }
    safe_cases = [_safe_case(case) for case in private_cases]
    classifications = {case["case_id"]: case["classification"] for case in private_cases}
    usage_keys = ("input_tokens", "output_tokens", "total_tokens", "duration_ms")
    usage = {
        key: sum(int((run.get("metrics") or {}).get(key) or 0) for run in flash["runs"])
        for key in usage_keys
    }
    terminals = [
        "LLM_METADATA_REPEATABILITY_BENCHMARK_COMPLETE",
        "SAME_INPUT_OUTPUT_VARIANCE_MEASURED",
        "NO_BENCHMARK_RESULT_SELECTION",
        "COMPARISON_MODEL_NOT_AVAILABLE_ON_SAME_CONTRACT",
    ]
    if "STOCHASTIC" in classifications.values():
        terminals.append("FLASH_SINGLE_SHOT_STOCHASTIC")
    if "STABLE_WRONG" in classifications.values():
        terminals.append("FLASH_SEMANTIC_FAILURE_STABLE")
    safe = {
        "schema_version": "broker_reports_g569_qualification_safe_v1",
        "goal": "G5.69",
        "status": "REPEATABILITY_COMPLETE_COMPARISON_UNAVAILABLE",
        "terminals": terminals,
        "flash_model_id": MODEL_ID,
        "flash_provider_submissions": flash["provider_submissions"],
        "flash_semantic_results": flash["semantic_results"],
        "flash_transport_failures": flash["transport_failures"],
        "runs_per_case": freeze["runs_per_case_per_model"],
        "same_input_hash_per_case": True,
        "case_classifications": classifications,
        "cases": safe_cases,
        "totals": totals,
        "usage": usage,
        "comparison_model_id": freeze["comparison"]["model_id"],
        "comparison_provider_submissions": 0,
        "comparison_semantic_results": 0,
        "comparison_terminal": comparison_abort["terminal"],
        "optional_full_corpus_authorized": False,
        "historical_g568_result_counted_in_five": False,
        "retries": 0,
        "best_of_n": False,
        "voting": False,
        "manual_output_repair": False,
        "result_selection": False,
        "provider_calls_during_qualification": 0,
        "private_values_committed": False,
    }
    private = {
        **safe,
        "schema_version": "broker_reports_g569_qualification_private_v1",
        "cases": private_cases,
        "comparison_abort": comparison_abort,
    }
    return private, safe


def _qualify_case(
    *,
    frozen_case: dict[str, Any],
    result_case: dict[str, Any],
    runs: list[dict[str, Any]],
    artifact: dict[str, Any],
    known_failure: dict[str, Any],
) -> dict[str, Any]:
    if len(runs) != 5:
        raise G569QualificationError("g569_case_run_count_invalid")
    oracle_keys = Counter(
        _semantic_key(fact["fact_type"], fact["value"])
        for fact in frozen_case["oracle_facts"]
    )
    private_runs = [
        _qualify_run(
            frozen_case=frozen_case,
            result_case=result_case,
            run=run,
            artifact=artifact,
            oracle_keys=oracle_keys,
            known_failure=known_failure,
        )
        for run in runs
    ]
    raw_fingerprints = {run["raw_semantic_fact_set_sha256"] for run in private_runs}
    all_exact = all(run["semantic_exact"] for run in private_runs)
    if len(raw_fingerprints) == 1 and all_exact:
        classification = "STABLE_CORRECT"
    elif len(raw_fingerprints) == 1:
        classification = "STABLE_WRONG"
    else:
        classification = "STOCHASTIC"
    totals_keys = (
        "correct",
        "missed",
        "semantic_extras",
        "wrong_roles",
        "wrong_value_boundary",
        "structural_rejections",
        "invented_literals",
        "invalid_provenance",
        "duplicates",
    )
    totals = {key: sum(run[key] for run in private_runs) for key in totals_keys}
    all_semantic_keys = sorted(
        {
            key
            for run in private_runs
            for key in run["raw_semantic_keys"]
        }
        | set(oracle_keys)
    )
    frequencies = []
    for semantic_key in all_semantic_keys:
        count = sum(semantic_key in run["raw_semantic_keys"] for run in private_runs)
        frequencies.append(
            {
                "semantic_key": semantic_key,
                "semantic_key_sha256": _sha256_json(semantic_key),
                "expected": semantic_key in oracle_keys,
                "runs_present": count,
                "runs_total": 5,
            }
        )
    return {
        "case_id": frozen_case["case_id"],
        "alias": frozen_case["alias"],
        "benchmark_role": frozen_case["benchmark_role"],
        "oracle_fact_count": frozen_case["oracle_fact_count"],
        "model_visible_request_sha256": frozen_case[
            "model_visible_request_sha256"
        ],
        "classification": classification,
        "distinct_raw_semantic_fact_sets": len(raw_fingerprints),
        "all_runs_semantic_exact": all_exact,
        "client_code_account_false_positive_frequency": sum(
            run["known_client_code_account_false_positive"] for run in private_runs
        ),
        "client_code_account_direct_relation_frequency": sum(
            run["known_client_code_account_direct_relation"] for run in private_runs
        ),
        "totals": totals,
        "semantic_frequencies": frequencies,
        "runs": private_runs,
    }


def _qualify_run(
    *,
    frozen_case: dict[str, Any],
    result_case: dict[str, Any],
    run: dict[str, Any],
    artifact: dict[str, Any],
    oracle_keys: Counter,
    known_failure: dict[str, Any],
) -> dict[str, Any]:
    if not run["semantic_result"] or run["transport_failure"]:
        raise G569QualificationError("g569_semantic_run_missing")
    raw_facts = _decode_response(run["raw_model_output"])["facts"]
    registry = result_case["binding_registry"]
    raw_records: list[dict[str, Any]] = []
    accepted_keys: list[str] = []
    failure_codes: list[str] = []
    known_false = False
    known_direct = False
    for raw_fact in raw_facts:
        target = (registry.get("targets") or {}).get(raw_fact.get("source_target_alias"))
        role_target = (registry.get("targets") or {}).get(
            raw_fact.get("role_evidence_target_alias")
        )
        literal = raw_fact.get("source_literal")
        if isinstance(target, dict) and isinstance(literal, str):
            fragments = [
                fragment
                for fragment in target.get("fragments") or []
                if literal in str(fragment.get("literal") or "")
            ]
            if len(fragments) == 1:
                try:
                    value = _normalized_value(
                        fact_type=raw_fact["fact_type"],
                        source_literal=literal,
                        start_literal=raw_fact.get("period_start_literal"),
                        end_literal=raw_fact.get("period_end_literal"),
                        target_content=target["content"],
                    )
                    raw_records.append(
                        {
                            "fact_type": raw_fact["fact_type"],
                            "value": value,
                            "semantic_key": _semantic_key(raw_fact["fact_type"], value),
                            "source_target_alias": raw_fact["source_target_alias"],
                            "role_evidence_target_alias": raw_fact[
                                "role_evidence_target_alias"
                            ],
                        }
                    )
                except Exception:
                    pass
        if (
            frozen_case["case_id"] == "case_f"
            and isinstance(target, dict)
            and target.get("node_id") == known_failure["canonical_node_id"]
            and target.get("fragments", [{}])[0].get("field_path")
            == known_failure["value_field_path"]
            and raw_fact.get("fact_type") == "ACCOUNT_IDENTIFIER"
        ):
            known_false = True
            if isinstance(role_target, dict):
                known_direct = (
                    _direct_structural_relation(
                        value_binding=target,
                        role_binding=role_target,
                    )
                    is not None
                )
        try:
            validated = validate_metadata_proposal(
                raw_model_output={
                    "schema_version": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
                    "facts": [raw_fact],
                },
                artifact=artifact,
                context_package=result_case["context_package"],
                binding_registry=registry,
                model_id=MODEL_ID,
            )
            accepted_keys.extend(
                _semantic_key(fact["fact_type"], fact["value"])
                for fact in validated["metadata_facts"]
            )
        except Gate3LlmMetadataAdapterError as exc:
            failure_codes.append(exc.code)

    raw_keys = Counter(record["semantic_key"] for record in raw_records)
    correct = sum((oracle_keys & raw_keys).values())
    missed = sum((oracle_keys - raw_keys).values())
    extras = sum((raw_keys - oracle_keys).values())
    wrong_roles = sum(
        record["semantic_key"] not in oracle_keys
        and _value_has_other_oracle_role(record["value"], record["fact_type"], frozen_case)
        for record in raw_records
    )
    if known_false:
        wrong_roles += 1
    wrong_boundary = sum(
        record["semantic_key"] not in oracle_keys
        and _is_wrong_value_boundary(record, frozen_case)
        for record in raw_records
    )
    duplicate_count = sum(count - 1 for count in raw_keys.values())
    structural = failure_codes.count("gate3_llm_metadata_role_value_relation_invalid")
    invented = failure_codes.count("gate3_llm_metadata_literal_not_in_target")
    invalid_provenance_codes = {
        "gate3_llm_metadata_target_unknown",
        "gate3_llm_metadata_target_binding_invalid",
        "gate3_llm_metadata_role_target_unknown",
        "gate3_llm_metadata_role_target_binding_invalid",
        "gate3_llm_metadata_literal_binding_ambiguous",
        "gate3_llm_metadata_source_refs_missing",
    }
    invalid_provenance = sum(code in invalid_provenance_codes for code in failure_codes)
    raw_key_list = sorted(raw_keys)
    return {
        "run_ordinal": run["run_ordinal"],
        "validation_status": run["validation_status"],
        "validation_error_code": run["validation_error_code"],
        "raw_facts": len(raw_facts),
        "raw_semantic_keys": raw_key_list,
        "raw_semantic_fact_set_sha256": _sha256_json(raw_key_list),
        "publishable_semantic_fact_set_sha256": _sha256_json(sorted(accepted_keys)),
        "correct": correct,
        "missed": missed,
        "semantic_extras": extras,
        "wrong_roles": wrong_roles,
        "wrong_value_boundary": wrong_boundary,
        "structural_rejections": structural,
        "invented_literals": invented,
        "invalid_provenance": invalid_provenance,
        "duplicates": duplicate_count,
        "semantic_exact": missed == 0 and extras == 0 and duplicate_count == 0,
        "known_client_code_account_false_positive": known_false,
        "known_client_code_account_direct_relation": known_false and known_direct,
        "failure_codes": failure_codes,
        "metrics": run.get("metrics") or {},
    }


def _safe_case(case: dict[str, Any]) -> dict[str, Any]:
    safe_frequencies = [
        {
            "semantic_key_sha256": item["semantic_key_sha256"],
            "fact_type": item["semantic_key"].split("|", 1)[0],
            "expected": item["expected"],
            "runs_present": item["runs_present"],
            "runs_total": item["runs_total"],
        }
        for item in case["semantic_frequencies"]
    ]
    return {
        "case_id": case["case_id"],
        "alias": case["alias"],
        "benchmark_role": case["benchmark_role"],
        "oracle_fact_count": case["oracle_fact_count"],
        "model_visible_request_sha256": case["model_visible_request_sha256"],
        "classification": case["classification"],
        "distinct_raw_semantic_fact_sets": case["distinct_raw_semantic_fact_sets"],
        "all_runs_semantic_exact": case["all_runs_semantic_exact"],
        "client_code_account_false_positive_frequency": case[
            "client_code_account_false_positive_frequency"
        ],
        "client_code_account_direct_relation_frequency": case[
            "client_code_account_direct_relation_frequency"
        ],
        "totals": case["totals"],
        "semantic_frequencies": safe_frequencies,
        "runs": [
            {
                key: run[key]
                for key in (
                    "run_ordinal",
                    "validation_status",
                    "validation_error_code",
                    "raw_facts",
                    "raw_semantic_fact_set_sha256",
                    "publishable_semantic_fact_set_sha256",
                    "correct",
                    "missed",
                    "semantic_extras",
                    "wrong_roles",
                    "wrong_value_boundary",
                    "structural_rejections",
                    "invented_literals",
                    "invalid_provenance",
                    "duplicates",
                    "semantic_exact",
                    "known_client_code_account_false_positive",
                    "known_client_code_account_direct_relation",
                )
            }
            for run in case["runs"]
        ],
    }


def _value_has_other_oracle_role(
    value: Any, fact_type: str, frozen_case: dict[str, Any]
) -> bool:
    key = _value_key(value)
    return any(
        _value_key(fact["value"]) == key and fact["fact_type"] != fact_type
        for fact in frozen_case["oracle_facts"]
    )


def _is_wrong_value_boundary(record: dict[str, Any], frozen_case: dict[str, Any]) -> bool:
    actual_strings = _strings(record["value"])
    for fact in frozen_case["oracle_facts"]:
        if fact["fact_type"] != record["fact_type"]:
            continue
        expected_strings = _strings(fact["value"])
        if expected_strings and all(
            any(expected in actual for actual in actual_strings)
            for expected in expected_strings
        ):
            return True
    return False


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _strings(child)]
    return []


def _semantic_key(fact_type: str, value: Any) -> str:
    return fact_type + "|" + _value_key(value)


def _value_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_canonical(*, store_root: Path, frozen_case: dict[str, Any]) -> dict[str, Any]:
    root = store_root.resolve()
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(**frozen_case["context"], allow_private=True)
    records = [
        record
        for record in ArtifactResolver(store).catalog_case(context)
        if record.artifact_type == "broker_reports_canonical_artifact_v1"
        and record.document_id == frozen_case["document_id"]
    ]
    if len(records) != 1:
        raise G569QualificationError("g569_canonical_ambiguous")
    artifact = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read(records[0].artifact_id, context)
    )
    if (
        artifact.get("artifact_id") != frozen_case["canonical_version_id"]
        or artifact.get("canonical_root_hash") != frozen_case["canonical_root_sha256"]
    ):
        raise G569QualificationError("g569_canonical_changed")
    return artifact


def _validate_inputs(
    freeze: dict[str, Any],
    flash: dict[str, Any],
    g568: dict[str, Any],
    comparison_abort: dict[str, Any],
) -> None:
    if (
        freeze.get("goal") != "G5.69"
        or freeze.get("runs_per_case_per_model") != 5
        or flash.get("model_slot") != "flash"
        or flash.get("provider_submissions") != 10
        or flash.get("semantic_results") != 10
        or flash.get("transport_failures") != 0
        or flash.get("source_stores_unchanged") is not True
        or g568.get("goal") != "G5.68"
        or comparison_abort.get("terminal")
        != "COMPARISON_MODEL_NOT_AVAILABLE_ON_SAME_CONTRACT"
        or comparison_abort.get("provider_submissions") != 0
    ):
        raise G569QualificationError("g569_qualification_input_invalid")
    expected_hashes = {
        case["case_id"]: case["model_visible_request_sha256"]
        for case in freeze["cases"]
    }
    if any(
        run["model_visible_request_sha256"] != expected_hashes[run["case_id"]]
        for run in flash["runs"]
    ):
        raise G569QualificationError("g569_request_hash_drift")


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
        raise G569QualificationError("g569_json_object_required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
