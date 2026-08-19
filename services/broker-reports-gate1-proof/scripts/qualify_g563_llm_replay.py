#!/usr/bin/env python3
"""Qualify the one frozen G5.63 replay without repairing model output."""

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
    "pdf_002": {
        "raw_facts": 24,
        "correct_unique": 9,
        "missing": 0,
        "extra_unique": 1,
        "duplicates": 14,
        "ambiguous": 0,
    },
    "pdf_024": {
        "raw_facts": 6,
        "correct_unique": 5,
        "missing": 1,
        "extra_unique": 1,
        "duplicates": 0,
        "ambiguous": 0,
    },
    "holdout_a": {
        "raw_facts": 4,
        "correct_unique": 3,
        "missing": 0,
        "extra_unique": 1,
        "duplicates": 0,
        "ambiguous": 0,
    },
    "holdout_b": {
        "raw_facts": 6,
        "correct_unique": 5,
        "missing": 1,
        "extra_unique": 1,
        "duplicates": 0,
        "ambiguous": 2,
    },
}

FACTORY_REQUIRED = (
    "The replay must be produced by live_g561_llm_metadata_generalization.py "
    "through Gate3LlmMetadataAdapterFactory and the Gate 2 model client factory"
)
FORBIDDEN = (
    "provider calls during qualification, raw output mutation, validator "
    "weakening, retry, best-of-N or oracle injection into model context"
)


class G563ReplayQualificationError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-result", type=Path, required=True)
    parser.add_argument("--g562-oracle", type=Path, required=True)
    parser.add_argument("--visibility-proof", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()

    replay = _read_json(args.replay_result.resolve())
    oracle = _read_json(args.g562_oracle.resolve())
    visibility = _read_json(args.visibility_proof.resolve())
    adjudication = _read_json(args.adjudication.resolve())
    private_output = args.private_output.resolve()
    safe_output = args.safe_output.resolve()
    for output in (private_output, safe_output):
        if _is_within(output, REPO_ROOT.resolve()):
            raise G563ReplayQualificationError("g563_private_output_inside_repository")
        if output.exists():
            raise G563ReplayQualificationError("g563_output_must_not_exist")

    private_result, safe_result = qualify_replay(
        replay=replay,
        oracle=oracle,
        visibility=visibility,
        adjudication=adjudication,
    )
    private_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.parent.mkdir(parents=True, exist_ok=True)
    private_output.write_text(
        json.dumps(private_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    safe_output.write_text(
        json.dumps(safe_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    return 0


def qualify_replay(
    *,
    replay: dict[str, Any],
    oracle: dict[str, Any],
    visibility: dict[str, Any],
    adjudication: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_inputs(
        replay=replay,
        oracle=oracle,
        visibility=visibility,
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

    totals = {
        key: sum(item[key] for item in private_cases)
        for key in (
            "raw_facts",
            "unique_candidate_facts",
            "correct_unique",
            "source_present_missed",
            "semantic_extra_unique",
            "duplicate_semantic_assertions",
            "ambiguous_literal_facts",
            "invented_literals",
            "invalid_provenance_or_value",
            "unsupported_field_facts",
        )
    }
    if totals != {
        "raw_facts": 40,
        "unique_candidate_facts": 26,
        "correct_unique": 22,
        "source_present_missed": 2,
        "semantic_extra_unique": 4,
        "duplicate_semantic_assertions": 14,
        "ambiguous_literal_facts": 2,
        "invented_literals": 0,
        "invalid_provenance_or_value": 0,
        "unsupported_field_facts": 0,
    }:
        raise G563ReplayQualificationError("g563_replay_totals_changed")

    metrics = {
        key: sum(int(item["metrics"].get(key) or 0) for item in replay["cases"])
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
    private_result = {
        "schema_version": "broker_reports_g563_replay_qualification_private_v1",
        "goal": "G5.63",
        "status": "PARTIAL",
        "terminal": [
            "METADATA_CONTEXT_POSITION_INDEPENDENCE_PROVEN",
            "FROZEN_ORACLE_CONTEXT_VISIBILITY_24_OF_24",
            "MAGIC_TEXT_HEAD_CUTOFF_REMOVED",
            "SAME_LLM_ADAPTER_REPLAY_COMPLETED",
            "CONTEXT_VISIBILITY_FAILURES_ZERO",
            "METADATA_CONTEXT_GENERALIZATION_PARTIAL",
            "EXACT_CONTEXT_BINDING_GAP_LOCALIZED",
            "LLM_METADATA_SEMANTIC_RESULT=RESIDUAL_FAILURES_LOCALIZED",
            "LLM_SEMANTIC_TUNING_NOT_AUTHORIZED",
        ],
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
        "validator_accepted_documents": sum(
            item["validation_status"] == "validated" for item in private_cases
        ),
        "validator_rejected_documents": sum(
            item["validation_status"] == "rejected" for item in private_cases
        ),
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
                "duplicate_semantic_assertions",
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
        "schema_version": "broker_reports_g563_replay_qualification_safe_v1",
        "goal": "G5.63",
        "status": "PARTIAL",
        "terminal": private_result["terminal"],
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
        "visibility": {"visible": 24, "invisible": 0},
        "cases": safe_cases,
        "totals": totals,
        "metrics": metrics,
        "validator_accepted_documents": private_result[
            "validator_accepted_documents"
        ],
        "validator_rejected_documents": private_result[
            "validator_rejected_documents"
        ],
        "visual_classifications": classifications,
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
            raise G563ReplayQualificationError(
                f"g563_raw_value_invalid:{alias}:{fact_type}"
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
    duplicate_count = sum(count - 1 for count in candidate_counts.values() if count > 1)
    ambiguous = sum(item["fragment_matches"] != 1 for item in records)

    expected = EXPECTED_CASE_COUNTS[alias]
    observed = {
        "raw_facts": len(raw_facts),
        "correct_unique": len(correct),
        "missing": len(missing),
        "extra_unique": len(extras),
        "duplicates": duplicate_count,
        "ambiguous": ambiguous,
    }
    if observed != expected:
        raise G563ReplayQualificationError(f"g563_case_counts_changed:{alias}")
    if duplicate_count != adjudication_case["duplicate_semantic_assertions"]:
        raise G563ReplayQualificationError(
            f"g563_duplicate_adjudication_changed:{alias}"
        )

    record_hash_counts = Counter(item["source_literal_sha256"] for item in records)
    residuals = adjudication_case["residuals"]
    for residual in residuals:
        if record_hash_counts[residual["literal_sha256"]] != residual["occurrences"]:
            raise G563ReplayQualificationError(
                f"g563_visual_residual_not_bound:{alias}"
            )
    exceptional_hashes = {
        item["source_literal_sha256"]
        for item in records
        if item["semantic_key"] in extras or item["fragment_matches"] != 1
    }
    if exceptional_hashes != {item["literal_sha256"] for item in residuals}:
        raise G563ReplayQualificationError(
            f"g563_visual_residual_set_changed:{alias}"
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
        "duplicate_semantic_assertions": duplicate_count,
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
    visibility: dict[str, Any],
    adjudication: dict[str, Any],
) -> None:
    aliases = tuple(item.get("alias") for item in replay.get("cases") or [])
    oracle_aliases = tuple(item.get("alias") for item in oracle.get("cases") or [])
    adjudication_aliases = tuple(
        item.get("alias") for item in adjudication.get("cases") or []
    )
    if not (aliases == oracle_aliases == adjudication_aliases == EXPECTED_ALIASES):
        raise G563ReplayQualificationError("g563_frozen_corpus_changed")
    if (
        replay.get("provider_submissions_total") != 4
        or replay.get("source_stores_unchanged") is not True
        or replay.get("frozen_contract", {}).get("contract_version")
        != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or replay.get("frozen_contract", {}).get("context_policy_version")
        != GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION
        or any(item.get("provider_submissions") != 1 for item in replay["cases"])
    ):
        raise G563ReplayQualificationError("g563_clean_replay_contract_invalid")
    if (
        oracle.get("goal") != "G5.62"
        or oracle.get("source_truth_fact_count") != 24
        or oracle.get("canonical_loss_count") != 0
        or visibility.get("visible") != 24
        or visibility.get("invisible") != 0
        or visibility.get("provider_calls") != 0
    ):
        raise G563ReplayQualificationError("g563_authority_or_visibility_invalid")
    if (
        adjudication.get("authority")
        != "visual_source_plus_g562_oracle_plus_frozen_raw_output"
        or adjudication.get("output_repaired") is not False
        or adjudication.get("provider_calls_during_adjudication") != 0
    ):
        raise G563ReplayQualificationError("g563_adjudication_invalid")


def _semantic_key(fact_type: str, value: Any) -> tuple[str, str]:
    return (
        fact_type,
        json.dumps(value, ensure_ascii=False, sort_keys=True),
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G563ReplayQualificationError("g563_json_object_required")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
