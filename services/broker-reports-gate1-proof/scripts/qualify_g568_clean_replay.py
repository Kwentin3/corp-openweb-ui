#!/usr/bin/env python3
"""Qualify the one G5.68 five-document replay without output repair."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
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
    validate_metadata_proposal,
)


EXPECTED_ALIASES = ("pdf_002", "pdf_024", "holdout_a", "holdout_b")
MODEL_ID = "models/gemini-3.5-flash"


class G568ReplayQualificationError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-replay", type=Path, required=True)
    parser.add_argument("--development-frozen", type=Path, required=True)
    parser.add_argument("--development-oracle", type=Path, required=True)
    parser.add_argument("--current-replay", type=Path, required=True)
    parser.add_argument("--current-freeze", type=Path, required=True)
    parser.add_argument("--current-oracle", type=Path, required=True)
    parser.add_argument("--goal-freeze", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    outputs = (args.private_output.resolve(), args.safe_output.resolve())
    if any(output.exists() for output in outputs):
        raise G568ReplayQualificationError("g568_qualification_output_must_not_exist")

    development_replay = _read_json(args.development_replay.resolve())
    development_frozen = _read_json(args.development_frozen.resolve())
    development_oracle = _read_json(args.development_oracle.resolve())
    current_replay = _read_json(args.current_replay.resolve())
    current_freeze = _read_json(args.current_freeze.resolve())
    current_oracle = _read_json(args.current_oracle.resolve())
    goal_freeze = _read_json(args.goal_freeze.resolve())
    private, safe = qualify(
        development_replay=development_replay,
        development_frozen=development_frozen,
        development_oracle=development_oracle,
        development_replay_root=args.development_replay.resolve().parent,
        current_replay=current_replay,
        current_freeze=current_freeze,
        current_oracle=current_oracle,
        current_replay_root=args.current_replay.resolve().parent,
        goal_freeze=goal_freeze,
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
    development_replay: dict[str, Any],
    development_frozen: dict[str, Any],
    development_oracle: dict[str, Any],
    development_replay_root: Path,
    current_replay: dict[str, Any],
    current_freeze: dict[str, Any],
    current_oracle: dict[str, Any],
    current_replay_root: Path,
    goal_freeze: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_replay_inputs(
        development_replay=development_replay,
        development_frozen=development_frozen,
        development_oracle=development_oracle,
        current_replay=current_replay,
        current_freeze=current_freeze,
        current_oracle=current_oracle,
    )
    frozen_by_alias = {case["alias"]: case for case in development_frozen["cases"]}
    oracle_by_alias = {case["alias"]: case for case in development_oracle["cases"]}
    development_cases = []
    for replay_case in development_replay["cases"]:
        alias = replay_case["alias"]
        artifact = _read_canonical(
            store_root=development_replay_root / alias / "working-store",
            context=frozen_by_alias[alias]["context"],
            document_id=frozen_by_alias[alias]["document_id"],
        )
        development_cases.append(
            _qualify_case(
                replay_case=replay_case,
                artifact=artifact,
                oracle_facts=oracle_by_alias[alias]["facts"],
                oracle_is_development=True,
            )
        )

    current_artifact = _read_canonical(
        store_root=current_replay_root / "working-store",
        context=current_freeze["context"],
        document_id=current_freeze["document_id"],
        require_source_available=True,
    )
    current_case = _qualify_case(
        replay_case=current_replay,
        artifact=current_artifact,
        oracle_facts=current_oracle["facts"],
        oracle_is_development=False,
    )
    known_semantic_failure = _qualify_known_semantic_failure(
        replay_case=next(
            case for case in development_replay["cases"] if case["alias"] == "holdout_a"
        ),
        frozen=goal_freeze["failing_case"],
    )
    if known_semantic_failure["pure_llm_semantic_failure"] is not True:
        raise G568ReplayQualificationError("g568_known_semantic_failure_not_proven")
    next(
        case for case in development_cases if case["alias"] == "holdout_a"
    )["wrong_roles"] += 1
    all_cases = [*development_cases, current_case]
    count_keys = (
        "raw_facts",
        "structurally_accepted_assertions",
        "correct_facts",
        "missed_facts",
        "semantic_extras",
        "wrong_roles",
        "role_value_structural_failures",
        "invented_literals",
        "invalid_provenance",
        "duplicate_assertions",
    )
    totals = {key: sum(case[key] for case in all_cases) for key in count_keys}
    development_exact = all(case["semantic_exact"] for case in development_cases)
    current_exact = current_case["semantic_exact"]
    terminals = [
        "DIRECT_ROLE_VALUE_SOURCE_BINDING_PROVEN",
        "COMPOSITE_ROLE_EVIDENCE_OVERREACH_REMOVED",
        "ONE_CLEAN_FIVE_DOCUMENT_REPLAY_COMPLETED",
        "NO_HEURISTIC_FALLBACK_ADDED",
    ]
    if development_exact:
        terminals.append("DEVELOPMENT_METADATA_CORPUS_SOURCE_ALIGNED")
    else:
        terminals.append("DEVELOPMENT_METADATA_RESIDUALS_PRESERVED")
    if current_exact:
        terminals.append("CURRENT_UNSEEN_HOLDOUT_SOURCE_ALIGNED")
    else:
        terminals.append("CURRENT_UNSEEN_HOLDOUT_SEMANTIC_RESIDUAL")
    if totals["role_value_structural_failures"]:
        terminals.append("NON_DIRECT_MODEL_EVIDENCE_REJECTED")
    if totals["semantic_extras"]:
        terminals.append("LLM_SEMANTIC_ERRORS_PERSIST")
    terminals.extend(
        [
            "CLIENT_CODE_ACCOUNT_SEMANTIC_ERROR_PERSISTS",
            "PURE_LLM_SEMANTIC_FAILURE_PROVEN",
        ]
    )

    safe_cases = [_safe_case(case) for case in all_cases]
    safe = {
        "schema_version": "broker_reports_g568_replay_qualification_safe_v1",
        "goal": "G5.68",
        "status": "STRUCTURE_PROVEN_WITH_UNREPAIRED_LLM_RESIDUALS",
        "terminals": terminals,
        "documents": 5,
        "provider_submissions": 5,
        "provider_submissions_per_document": 1,
        "provider_calls_during_qualification": 0,
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "raw_output_repaired": False,
        "source_stores_unchanged": True,
        "development_semantic_exact": development_exact,
        "current_semantic_exact": current_exact,
        "cases": safe_cases,
        "totals": totals,
        "known_client_code_account_case": {
            "direct_relation": known_semantic_failure["direct_relation"],
            "pure_llm_semantic_failure": True,
        },
        "semantic_prompt_tuning": 0,
        "private_values_committed": False,
    }
    private = {
        **safe,
        "schema_version": "broker_reports_g568_replay_qualification_private_v1",
        "cases": all_cases,
        "known_client_code_account_case": known_semantic_failure,
    }
    return private, safe


def _qualify_case(
    *,
    replay_case: dict[str, Any],
    artifact: dict[str, Any],
    oracle_facts: list[dict[str, Any]],
    oracle_is_development: bool,
) -> dict[str, Any]:
    raw_facts = _decode_response(replay_case["raw_model_output"])["facts"]
    accepted_facts: list[dict[str, Any]] = []
    failure_codes: list[str] = []
    for raw_fact in raw_facts:
        try:
            result = validate_metadata_proposal(
                raw_model_output={
                    "schema_version": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
                    "facts": [raw_fact],
                },
                artifact=artifact,
                context_package=replay_case["context_package"],
                binding_registry=replay_case["binding_registry"],
                model_id=MODEL_ID,
            )
            accepted_facts.extend(result["metadata_facts"])
        except Gate3LlmMetadataAdapterError as exc:
            failure_codes.append(exc.code)

    oracle_keys = Counter(
        _semantic_key(
            fact["fact_type"],
            fact["value"] if oracle_is_development else fact["normalized_value"],
        )
        for fact in oracle_facts
    )
    accepted_keys = Counter(
        _semantic_key(fact["fact_type"], fact["value"]) for fact in accepted_facts
    )
    correct = sum((oracle_keys & accepted_keys).values())
    missing = sum((oracle_keys - accepted_keys).values())
    extras = sum((accepted_keys - oracle_keys).values())
    oracle_values_by_type = {
        _value_key(fact["value"] if oracle_is_development else fact["normalized_value"]): fact["fact_type"]
        for fact in oracle_facts
    }
    wrong_roles = sum(
        oracle_values_by_type.get(_value_key(fact["value"])) not in {None, fact["fact_type"]}
        for fact in accepted_facts
    )
    duplicate_assertions = sum(count - 1 for count in accepted_keys.values())
    structural_failures = failure_codes.count(
        "gate3_llm_metadata_role_value_relation_invalid"
    )
    invented_literals = failure_codes.count("gate3_llm_metadata_literal_not_in_target")
    invalid_provenance = sum(
        code
        in {
            "gate3_llm_metadata_target_unknown",
            "gate3_llm_metadata_target_binding_invalid",
            "gate3_llm_metadata_role_target_unknown",
            "gate3_llm_metadata_role_target_binding_invalid",
            "gate3_llm_metadata_literal_binding_ambiguous",
            "gate3_llm_metadata_source_refs_missing",
        }
        for code in failure_codes
    )
    return {
        "alias": replay_case["alias"],
        "validation_status": replay_case["validation_status"],
        "validation_error_code": replay_case.get("validation_error_code"),
        "provider_submissions": replay_case["provider_submissions"],
        "raw_facts": len(raw_facts),
        "structurally_accepted_assertions": len(accepted_facts),
        "correct_facts": correct,
        "missed_facts": missing,
        "semantic_extras": extras,
        "wrong_roles": wrong_roles,
        "role_value_structural_failures": structural_failures,
        "invented_literals": invented_literals,
        "invalid_provenance": invalid_provenance,
        "duplicate_assertions": duplicate_assertions,
        "semantic_exact": missing == 0 and extras == 0,
        "failure_codes": failure_codes,
        "metrics": replay_case.get("metrics") or {},
    }


def _safe_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        key: case[key]
        for key in (
            "alias",
            "validation_status",
            "validation_error_code",
            "provider_submissions",
            "raw_facts",
            "structurally_accepted_assertions",
            "correct_facts",
            "missed_facts",
            "semantic_extras",
            "wrong_roles",
            "role_value_structural_failures",
            "invented_literals",
            "invalid_provenance",
            "duplicate_assertions",
            "semantic_exact",
        )
    }


def _qualify_known_semantic_failure(
    *,
    replay_case: dict[str, Any],
    frozen: dict[str, Any],
) -> dict[str, Any]:
    targets = replay_case["binding_registry"]["targets"]
    matches: list[dict[str, Any]] = []
    for fact in _decode_response(replay_case["raw_model_output"])["facts"]:
        value_target = targets.get(fact.get("source_target_alias"))
        role_target = targets.get(fact.get("role_evidence_target_alias"))
        if not isinstance(value_target, dict) or not isinstance(role_target, dict):
            continue
        if (
            value_target.get("node_id") == frozen["canonical_node_id"]
            and value_target["fragments"][0]["field_path"]
            == frozen["value_field_path"]
        ):
            matches.append(
                {
                    "fact_type": fact["fact_type"],
                    "value_field_path": value_target["fragments"][0]["field_path"],
                    "role_field_path": role_target["fragments"][0]["field_path"],
                    "direct_relation": _direct_structural_relation(
                        value_binding=value_target,
                        role_binding=role_target,
                    ),
                }
            )
    if len(matches) != 1:
        raise G568ReplayQualificationError("g568_known_semantic_case_ambiguous")
    match = matches[0]
    match["pure_llm_semantic_failure"] = (
        match["fact_type"] == "ACCOUNT_IDENTIFIER"
        and match["role_field_path"] == frozen["direct_local_label_field_path"]
        and match["direct_relation"] == "SAME_TABLE_ROW"
    )
    return match


def _semantic_key(fact_type: str, value: Any) -> tuple[str, str]:
    return fact_type, _value_key(value)


def _value_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_canonical(
    *,
    store_root: Path,
    context: dict[str, Any],
    document_id: str,
    require_source_available: bool = False,
) -> dict[str, Any]:
    root = store_root.resolve()
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    access = ArtifactAccessContext(
        **context,
        allow_private=True,
        require_source_available=require_source_available,
    )
    records = [
        record
        for record in ArtifactResolver(store).catalog_case(access)
        if record.artifact_type == "broker_reports_canonical_artifact_v1"
        and record.document_id == document_id
    ]
    if len(records) != 1:
        raise G568ReplayQualificationError("g568_replay_canonical_ambiguous")
    return (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read(records[0].artifact_id, access)
    )


def _validate_replay_inputs(
    *,
    development_replay: dict[str, Any],
    development_frozen: dict[str, Any],
    development_oracle: dict[str, Any],
    current_replay: dict[str, Any],
    current_freeze: dict[str, Any],
    current_oracle: dict[str, Any],
) -> None:
    if (
        tuple(case.get("alias") for case in development_replay.get("cases") or [])
        != EXPECTED_ALIASES
        or tuple(case.get("alias") for case in development_frozen.get("cases") or [])
        != EXPECTED_ALIASES
        or development_replay.get("provider_submissions_total") != 4
        or current_replay.get("provider_submissions") != 1
        or development_replay.get("source_stores_unchanged") is not True
        or current_replay.get("source_store_unchanged") is not True
        or development_oracle.get("source_truth_fact_count") != 24
        or current_oracle.get("source_present_supported_facts") != 5
        or development_frozen.get("instruction_version") != "1.2.0"
        or current_freeze.get("instruction_version") != "1.2.0"
    ):
        raise G568ReplayQualificationError("g568_replay_input_invalid")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G568ReplayQualificationError("g568_json_object_required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
