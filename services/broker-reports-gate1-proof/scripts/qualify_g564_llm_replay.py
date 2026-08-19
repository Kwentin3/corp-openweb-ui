#!/usr/bin/env python3
"""Qualify the single G5.64 replay without repairing model output."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
    _decode_response,
    _normalized_value,
)
from broker_reports_gate1.gate3_metadata_source_facts import (  # noqa: E402
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
    GATE3_MINIMAL_METADATA_FACT_TYPES,
)


EXPECTED_ALIASES = ("pdf_002", "pdf_024", "holdout_a", "holdout_b")
EXPECTED_CASE_COUNTS = {
    "pdf_002": (9, 9, 0, 0, 0, 0, 9, 0),
    "pdf_024": (6, 5, 1, 1, 0, 0, 6, 0),
    "holdout_a": (4, 3, 0, 1, 0, 0, 4, 0),
    "holdout_b": (6, 5, 1, 1, 0, 0, 6, 0),
}

FACTORY_REQUIRED = (
    "live_g561_llm_metadata_generalization.py routes the replay through "
    "Gate3LlmMetadataAdapterFactory and the Gate 2 model client factory"
)
FORBIDDEN = (
    "provider calls during qualification, raw output mutation, retry, "
    "best-of-N, semantic repair or oracle injection into model context"
)


class G564ReplayQualificationError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-result", type=Path, required=True)
    parser.add_argument("--g562-oracle", type=Path, required=True)
    parser.add_argument("--binding-proof", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()

    replay = _read_json(args.replay_result.resolve())
    oracle = _read_json(args.g562_oracle.resolve())
    binding = _read_json(args.binding_proof.resolve())
    adjudication = _read_json(args.adjudication.resolve())
    outputs = (args.private_output.resolve(), args.safe_output.resolve())
    for output in outputs:
        if _is_within(output, REPO_ROOT.resolve()):
            raise G564ReplayQualificationError("g564_private_output_inside_repository")
        if output.exists():
            raise G564ReplayQualificationError("g564_output_must_not_exist")

    private_result, safe_result = qualify_replay(
        replay=replay,
        oracle=oracle,
        binding=binding,
        adjudication=adjudication,
    )
    for output, result in zip(outputs, (private_result, safe_result), strict=True):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    return 0


def qualify_replay(
    *,
    replay: dict[str, Any],
    oracle: dict[str, Any],
    binding: dict[str, Any],
    adjudication: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_inputs(
        replay=replay,
        oracle=oracle,
        binding=binding,
        adjudication=adjudication,
    )
    oracle_by_alias = {item["alias"]: item for item in oracle["cases"]}
    adjudication_by_alias = {
        item["alias"]: item for item in adjudication["cases"]
    }
    private_cases = [
        analyze_case(
            replay_case=replay_case,
            oracle_case=oracle_by_alias[replay_case["alias"]],
            adjudication_case=adjudication_by_alias[replay_case["alias"]],
        )
        for replay_case in replay["cases"]
    ]

    total_keys = (
        "raw_facts",
        "unique_candidate_facts",
        "correct_unique",
        "source_present_missed",
        "semantic_extra_unique",
        "raw_repeated_assertions",
        "collapsed_repeated_assertions",
        "published_facts",
        "published_duplicate_assertions",
        "independent_multi_value_facts",
        "ambiguous_literal_facts",
        "invented_literals",
        "invalid_provenance_or_value",
        "unsupported_field_facts",
    )
    totals = {
        key: sum(item[key] for item in private_cases) for key in total_keys
    }
    expected_totals = {
        "raw_facts": 25,
        "unique_candidate_facts": 25,
        "correct_unique": 22,
        "source_present_missed": 2,
        "semantic_extra_unique": 3,
        "raw_repeated_assertions": 0,
        "collapsed_repeated_assertions": 0,
        "published_facts": 25,
        "published_duplicate_assertions": 0,
        "independent_multi_value_facts": 8,
        "ambiguous_literal_facts": 0,
        "invented_literals": 0,
        "invalid_provenance_or_value": 0,
        "unsupported_field_facts": 0,
    }
    if totals != expected_totals:
        raise G564ReplayQualificationError("g564_replay_totals_changed")

    metrics = {
        key: sum(int(item["metrics"].get(key) or 0) for item in private_cases)
        for key in (
            "rendered_context_chars",
            "final_model_input_chars",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "duration_ms",
        )
    }
    classifications = sorted(
        {
            residual["classification"]
            for item in private_cases
            for residual in item["visual_residuals"]
        }
    )
    terminal = [
        "METADATA_STRUCTURAL_SOURCE_BINDING_PROVEN",
        "FROZEN_ORACLE_VISIBILITY_24_OF_24_PRESERVED",
        "REPEATED_ASSERTION_EVIDENCE_MODEL_PROVEN",
        "SAME_FACT_DUPLICATE_PUBLICATION_ZERO",
        "MULTI_VALUE_METADATA_PRESERVED",
        "WHOLE_TABLE_LITERAL_AMBIGUITY_REMOVED",
        "SAME_LLM_ADAPTER_CLEAN_REPLAY_COMPLETED",
        "LLM_METADATA_SEMANTIC_RESULT=RESIDUAL_FAILURES_LOCALIZED",
        "SEMANTIC_TUNING_NOT_AUTHORIZED",
    ]
    private_result = {
        "schema_version": "broker_reports_g564_replay_qualification_private_v1",
        "goal": "G5.64",
        "status": "PARTIAL",
        "terminal": terminal,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "provider_calls": 4,
        "provider_calls_during_qualification": 0,
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "raw_output_repaired": False,
        "cases": private_cases,
        "totals": totals,
        "metrics": metrics,
        "visual_classifications": classifications,
        "validator_accepted_documents": 4,
        "validator_rejected_documents": 0,
    }
    safe_cases = [
        {
            key: item[key]
            for key in (
                "alias",
                "validation_status",
                "validation_error_code",
                "raw_facts",
                "unique_candidate_facts",
                "correct_unique",
                "source_present_missed",
                "semantic_extra_unique",
                "raw_repeated_assertions",
                "collapsed_repeated_assertions",
                "published_facts",
                "published_duplicate_assertions",
                "independent_multi_value_facts",
                "ambiguous_literal_facts",
                "invented_literals",
                "invalid_provenance_or_value",
                "unsupported_field_facts",
                "metrics",
                "visual_classifications",
            )
        }
        for item in private_cases
    ]
    safe_result = {
        "schema_version": "broker_reports_g564_replay_qualification_safe_v1",
        "goal": "G5.64",
        "status": "PARTIAL",
        "terminal": terminal,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "provider_calls": 4,
        "provider_calls_per_document": 1,
        "provider_calls_during_qualification": 0,
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "raw_output_repaired": False,
        "source_stores_unchanged": True,
        "visibility": {"visible": 24, "invisible": 0, "ambiguous": 0},
        "cases": safe_cases,
        "totals": totals,
        "metrics": metrics,
        "validator_accepted_documents": 4,
        "validator_rejected_documents": 0,
        "visual_classifications": classifications,
        "semantic_prompt_tuning": 0,
        "private_values_committed": False,
    }
    return private_result, safe_result


def analyze_case(
    *,
    replay_case: dict[str, Any],
    oracle_case: dict[str, Any],
    adjudication_case: dict[str, Any],
) -> dict[str, Any]:
    alias = replay_case["alias"]
    raw_facts = _decode_response(replay_case["raw_model_output"])["facts"]
    targets = replay_case["binding_registry"]["targets"]
    oracle_keys = {
        _semantic_key(fact["fact_type"], fact["value"])
        for fact in oracle_case["facts"]
    }
    records: list[dict[str, Any]] = []
    invented = 0
    invalid = 0
    unsupported = 0
    for fact in raw_facts:
        fact_type = fact.get("fact_type")
        if fact_type not in GATE3_MINIMAL_METADATA_FACT_TYPES:
            unsupported += 1
            continue
        target = targets.get(fact.get("source_target_alias"))
        literal = fact.get("source_literal")
        if not isinstance(target, dict) or not isinstance(literal, str):
            invalid += 1
            continue
        matches = [
            fragment
            for fragment in target["fragments"]
            if literal in fragment["literal"]
        ]
        if not matches:
            invented += 1
            continue
        try:
            value = _normalized_value(
                fact_type=fact_type,
                source_literal=literal,
                start_literal=fact.get("period_start_literal"),
                end_literal=fact.get("period_end_literal"),
                target_content=target["content"],
            )
        except Exception as exc:
            raise G564ReplayQualificationError(
                f"g564_raw_value_invalid:{alias}:{fact_type}"
            ) from exc
        records.append(
            {
                "fact_type": fact_type,
                "semantic_key": _semantic_key(fact_type, value),
                "source_literal_sha256": hashlib.sha256(
                    literal.encode("utf-8")
                ).hexdigest(),
                "source_target_alias": fact["source_target_alias"],
                "fragment_matches": len(matches),
            }
        )

    candidate_counts = Counter(item["semantic_key"] for item in records)
    candidate_keys = set(candidate_counts)
    correct = candidate_keys & oracle_keys
    missing = oracle_keys - candidate_keys
    extras = candidate_keys - oracle_keys
    raw_repeated = sum(count - 1 for count in candidate_counts.values())
    ambiguous = sum(item["fragment_matches"] != 1 for item in records)
    validated = replay_case.get("validated_output")
    if not isinstance(validated, dict):
        raise G564ReplayQualificationError(f"g564_validated_output_missing:{alias}")
    published = validated["metadata_facts"]
    published_counts = Counter(
        _semantic_key(fact["fact_type"], fact["value"]) for fact in published
    )
    published_duplicates = sum(count - 1 for count in published_counts.values())
    collapsed = validated["coverage"]["collapsed_repeated_assertions"]
    value_counts_by_type = Counter(
        fact["fact_type"] for fact in published
    )
    independent_multi_value = sum(
        count for count in value_counts_by_type.values() if count > 1
    )

    observed = (
        len(raw_facts),
        len(correct),
        len(missing),
        len(extras),
        raw_repeated,
        ambiguous,
        len(published),
        collapsed,
    )
    if observed != EXPECTED_CASE_COUNTS[alias]:
        raise G564ReplayQualificationError(f"g564_case_counts_changed:{alias}")

    residuals = adjudication_case["residuals"]
    record_hash_counts = Counter(item["source_literal_sha256"] for item in records)
    for residual in residuals:
        if record_hash_counts[residual["literal_sha256"]] != residual["occurrences"]:
            raise G564ReplayQualificationError(
                f"g564_visual_residual_not_bound:{alias}"
            )
    exceptional_hashes = {
        item["source_literal_sha256"]
        for item in records
        if item["semantic_key"] in extras or item["fragment_matches"] != 1
    }
    if exceptional_hashes != {item["literal_sha256"] for item in residuals}:
        raise G564ReplayQualificationError(
            f"g564_visual_residual_set_changed:{alias}"
        )

    metrics = {
        key: replay_case["metrics"].get(key)
        for key in (
            "selected_targets",
            "rendered_context_chars",
            "final_model_input_chars",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "duration_ms",
        )
    }
    return {
        "alias": alias,
        "validation_status": replay_case["validation_status"],
        "validation_error_code": replay_case["validation_error_code"],
        "raw_facts": len(raw_facts),
        "unique_candidate_facts": len(candidate_keys),
        "correct_unique": len(correct),
        "source_present_missed": len(missing),
        "semantic_extra_unique": len(extras),
        "raw_repeated_assertions": raw_repeated,
        "collapsed_repeated_assertions": collapsed,
        "published_facts": len(published),
        "published_duplicate_assertions": published_duplicates,
        "independent_multi_value_facts": independent_multi_value,
        "ambiguous_literal_facts": ambiguous,
        "invented_literals": invented,
        "invalid_provenance_or_value": invalid,
        "unsupported_field_facts": unsupported,
        "metrics": metrics,
        "visual_residuals": residuals,
        "visual_classifications": sorted(
            item["classification"] for item in residuals
        ),
    }


def _validate_inputs(
    *,
    replay: dict[str, Any],
    oracle: dict[str, Any],
    binding: dict[str, Any],
    adjudication: dict[str, Any],
) -> None:
    aliases = tuple(item.get("alias") for item in replay.get("cases") or [])
    oracle_aliases = tuple(item.get("alias") for item in oracle.get("cases") or [])
    adjudication_aliases = tuple(
        item.get("alias") for item in adjudication.get("cases") or []
    )
    if not (aliases == oracle_aliases == adjudication_aliases == EXPECTED_ALIASES):
        raise G564ReplayQualificationError("g564_frozen_corpus_changed")
    frozen = replay.get("frozen_contract") or {}
    if (
        replay.get("provider_submissions_total") != 4
        or replay.get("source_stores_unchanged") is not True
        or frozen.get("contract_version") != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or frozen.get("context_policy_version")
        != GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION
        or frozen.get("instruction_version") != "1.0.0"
        or frozen.get("output_schema_version")
        != "broker_reports_llm_metadata_proposal_v1"
        or frozen.get("provider_profile") != "google_gemini"
        or frozen.get("model_id") != "models/gemini-3.5-flash"
        or any(item.get("provider_submissions") != 1 for item in replay["cases"])
        or any(item.get("validation_status") != "validated" for item in replay["cases"])
    ):
        raise G564ReplayQualificationError("g564_clean_replay_contract_invalid")
    if (
        oracle.get("goal") != "G5.62"
        or oracle.get("source_truth_fact_count") != 24
        or oracle.get("canonical_loss_count") != 0
        or binding.get("goal") != "G5.64"
        or binding.get("visible") != 24
        or binding.get("invisible") != 0
        or binding.get("structural_ambiguity") != 0
        or binding.get("whole_table_targets") != 0
        or binding.get("provider_calls") != 0
    ):
        raise G564ReplayQualificationError("g564_authority_or_binding_invalid")
    if (
        adjudication.get("authority")
        != "visual_source_plus_g562_oracle_plus_frozen_raw_output"
        or adjudication.get("output_repaired") is not False
        or adjudication.get("provider_calls_during_adjudication") != 0
    ):
        raise G564ReplayQualificationError("g564_adjudication_invalid")


def _semantic_key(fact_type: str, value: Any) -> tuple[str, str]:
    return fact_type, json.dumps(value, ensure_ascii=False, sort_keys=True)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G564ReplayQualificationError("g564_json_object_required")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
