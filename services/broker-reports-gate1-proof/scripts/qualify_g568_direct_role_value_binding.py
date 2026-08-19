#!/usr/bin/env python3
"""Offline G5.68 proof for atomic evidence addresses and direct relations."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
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
    GATE3_LLM_METADATA_BINDING_REGISTRY_SCHEMA_VERSION,
    GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
    GATE3_LLM_METADATA_CONTEXT_SCHEMA_VERSION,
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    _direct_structural_relation,
    build_metadata_context_package,
)
from broker_reports_gate1.gate3_metadata_source_facts import (  # noqa: E402
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
)


EXPECTED_ALIASES = ("pdf_002", "pdf_024", "holdout_a", "holdout_b")
EXPECTED_COUNTS = {"pdf_002": 9, "pdf_024": 6, "holdout_a": 3, "holdout_b": 6}


class G568QualificationError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-frozen", type=Path, required=True)
    parser.add_argument("--development-oracle", type=Path, required=True)
    parser.add_argument("--current-freeze", type=Path, required=True)
    parser.add_argument("--current-oracle", type=Path, required=True)
    parser.add_argument("--goal-freeze", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()

    outputs = (args.private_output.resolve(), args.safe_output.resolve())
    if any(output.exists() for output in outputs):
        raise G568QualificationError("g568_output_must_not_exist")
    development = _read_json(args.development_frozen.resolve())
    development_oracle = _read_json(args.development_oracle.resolve())
    current = _read_json(args.current_freeze.resolve())
    current_oracle = _read_json(args.current_oracle.resolve())
    goal_freeze = _read_json(args.goal_freeze.resolve())

    private, safe = qualify(
        development=development,
        development_oracle=development_oracle,
        current=current,
        current_oracle=current_oracle,
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
    development: dict[str, Any],
    development_oracle: dict[str, Any],
    current: dict[str, Any],
    current_oracle: dict[str, Any],
    goal_freeze: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_frozen_inputs(
        development=development,
        development_oracle=development_oracle,
        current=current,
        current_oracle=current_oracle,
        goal_freeze=goal_freeze,
    )
    oracle_by_alias = {case["alias"]: case for case in development_oracle["cases"]}
    private_cases: list[dict[str, Any]] = []
    failing_artifact: dict[str, Any] | None = None
    failing_registry: dict[str, Any] | None = None
    for frozen_case in development["cases"]:
        artifact = _read_canonical(
            store_root=Path(frozen_case["source_store_root"]),
            context=frozen_case["context"],
            document_id=frozen_case["document_id"],
        )
        if (
            artifact.get("artifact_id") != frozen_case["canonical_version_id"]
            or artifact.get("canonical_root_hash")
            != frozen_case["canonical_root_sha256"]
        ):
            raise G568QualificationError("g568_development_canonical_changed")
        package, registry = build_metadata_context_package(
            artifact=artifact,
            document_id=frozen_case["document_id"],
            canonical_version_id=artifact["artifact_id"],
        )
        private_cases.append(
            _qualify_facts(
                alias=frozen_case["alias"],
                facts=oracle_by_alias[frozen_case["alias"]]["facts"],
                package=package,
                registry=registry,
                development=True,
            )
        )
        if frozen_case["alias"] == goal_freeze["failing_case"]["alias"]:
            failing_artifact = artifact
            failing_registry = registry

    current_artifact = _read_canonical(
        store_root=Path(current["source_store_root"]),
        context=current["context"],
        document_id=current["document_id"],
        require_source_available=True,
    )
    if (
        current_artifact.get("artifact_id") != current["canonical_version_id"]
        or current_artifact.get("canonical_root_hash")
        != current["canonical_root_sha256"]
    ):
        raise G568QualificationError("g568_current_canonical_changed")
    current_package, current_registry = build_metadata_context_package(
        artifact=current_artifact,
        document_id=current["document_id"],
        canonical_version_id=current_artifact["artifact_id"],
    )
    current_case = _qualify_facts(
        alias=current["alias"],
        facts=current_oracle["facts"],
        package=current_package,
        registry=current_registry,
        development=False,
    )
    if failing_artifact is None or failing_registry is None:
        raise G568QualificationError("g568_failing_case_missing")
    false_binding = _qualify_known_false_binding(
        artifact=failing_artifact,
        registry=failing_registry,
        frozen=goal_freeze["failing_case"],
    )

    development_visible = sum(case["visible"] for case in private_cases)
    development_ambiguity = sum(case["physical_ambiguity"] for case in private_cases)
    if (
        development_visible != 24
        or development_ambiguity != 0
        or current_case["visible"] != 5
        or current_case["physical_ambiguity"] != 0
        or false_binding["remote_same_table_relation"] is not None
        or false_binding["local_label_relation"] != "SAME_TABLE_ROW"
    ):
        raise G568QualificationError("g568_offline_proof_incomplete")

    terminals = [
        "DIRECT_ROLE_VALUE_SOURCE_BINDING_OFFLINE_PROVEN",
        "DEVELOPMENT_ORACLE_VISIBILITY_24_OF_24",
        "CURRENT_UNSEEN_ORACLE_VISIBILITY_5_OF_5",
        "PHYSICAL_AMBIGUITY_ZERO",
        "COMPOSITE_ROLE_EVIDENCE_OVERREACH_REMOVED",
        "ONE_CLEAN_FIVE_DOCUMENT_REPLAY_AUTHORIZED",
    ]
    safe_cases = [
        {
            "alias": case["alias"],
            "oracle_facts": case["oracle_facts"],
            "visible": case["visible"],
            "physical_ambiguity": case["physical_ambiguity"],
            "selected_targets": case["selected_targets"],
        }
        for case in private_cases
    ]
    safe = {
        "schema_version": "broker_reports_g568_offline_safe_v1",
        "goal": "G5.68",
        "terminals": terminals,
        "provider_calls": 0,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "context_schema_version": GATE3_LLM_METADATA_CONTEXT_SCHEMA_VERSION,
        "binding_registry_schema_version": (
            GATE3_LLM_METADATA_BINDING_REGISTRY_SCHEMA_VERSION
        ),
        "development_cases": safe_cases,
        "development_visibility": development_visible,
        "current_visibility": current_case["visible"],
        "physical_ambiguity": development_ambiguity
        + current_case["physical_ambiguity"],
        "false_wide_binding_is_direct": False,
        "local_same_row_binding_is_direct": True,
        "semantic_hints": 0,
        "broker_specific_rules": 0,
        "private_values_committed": False,
    }
    private = {
        **safe,
        "schema_version": "broker_reports_g568_offline_private_v1",
        "development_cases": private_cases,
        "current_case": current_case,
        "known_false_binding": false_binding,
    }
    return private, safe


def _qualify_facts(
    *,
    alias: str,
    facts: list[dict[str, Any]],
    package: dict[str, Any],
    registry: dict[str, Any],
    development: bool,
) -> dict[str, Any]:
    qualified: list[dict[str, Any]] = []
    for fact in facts:
        binding = fact["canonical_binding"] if development else fact
        field_path = binding["field_path"]
        literal = binding["literal"] if development else binding["source_literal"]
        aliases = _aliases_for_fragment(
            registry=registry,
            node_id=binding["node_id"],
            field_path=field_path,
            literal=literal,
        )
        qualified.append(
            {
                "fact_type": fact["fact_type"],
                "field_path": field_path,
                "aliases": aliases,
                "visible": len(aliases) == 1,
            }
        )
    expected = EXPECTED_COUNTS[alias] if development else 5
    return {
        "alias": alias,
        "oracle_facts": expected,
        "visible": sum(item["visible"] for item in qualified),
        "physical_ambiguity": sum(len(item["aliases"]) != 1 for item in qualified),
        "selected_targets": package["metrics"]["selected_targets"],
        "qualified_facts": qualified,
    }


def _qualify_known_false_binding(
    *,
    artifact: dict[str, Any],
    registry: dict[str, Any],
    frozen: dict[str, Any],
) -> dict[str, Any]:
    value_alias = _one_alias(
        registry,
        frozen["canonical_node_id"],
        frozen["value_field_path"],
    )
    local_alias = _one_alias(
        registry,
        frozen["canonical_node_id"],
        frozen["direct_local_label_field_path"],
    )
    value = registry["targets"][value_alias]
    local = registry["targets"][local_alias]
    value_row = value["structural_address"]["row"]
    remote_aliases = [
        alias
        for alias, target in registry["targets"].items()
        if target.get("node_id") == frozen["canonical_node_id"]
        and target.get("structural_address", {}).get("kind") == "table_cell"
        and target["structural_address"].get("row") != value_row
    ]
    if not remote_aliases:
        raise G568QualificationError("g568_remote_same_table_address_missing")
    remote_relations = [
        _direct_structural_relation(
            value_binding=value,
            role_binding=registry["targets"][alias],
        )
        for alias in remote_aliases
    ]
    if any(relation is not None for relation in remote_relations):
        raise G568QualificationError("g568_same_table_overreach_retained")
    return {
        "canonical_version_id": artifact["artifact_id"],
        "node_id": frozen["canonical_node_id"],
        "value_alias": value_alias,
        "local_label_alias": local_alias,
        "remote_same_table_addresses": len(remote_aliases),
        "remote_same_table_relation": None,
        "local_label_relation": _direct_structural_relation(
            value_binding=value,
            role_binding=local,
        ),
    }


def _one_alias(registry: dict[str, Any], node_id: str, field_path: str) -> str:
    aliases = _aliases_for_fragment(
        registry=registry,
        node_id=node_id,
        field_path=field_path,
        literal=None,
    )
    if len(aliases) != 1:
        raise G568QualificationError("g568_exact_address_not_unique")
    return aliases[0]


def _aliases_for_fragment(
    *,
    registry: dict[str, Any],
    node_id: str,
    field_path: str,
    literal: str | None,
) -> list[str]:
    expected = re.sub(r"\.(?:displayed_value|value)$", "", field_path)
    return sorted(
        alias
        for alias, target in registry["targets"].items()
        if target.get("node_id") == node_id
        and len(target.get("fragments") or []) == 1
        and re.sub(
            r"\.(?:displayed_value|value)$",
            "",
            target["fragments"][0].get("field_path") or "",
        )
        == expected
        and (
            literal is None
            or literal in str(target["fragments"][0].get("literal") or "")
        )
    )


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
        raise G568QualificationError("g568_canonical_record_ambiguous")
    return (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read(records[0].artifact_id, access)
    )


def _validate_frozen_inputs(
    *,
    development: dict[str, Any],
    development_oracle: dict[str, Any],
    current: dict[str, Any],
    current_oracle: dict[str, Any],
    goal_freeze: dict[str, Any],
) -> None:
    if (
        tuple(case.get("alias") for case in development.get("cases") or [])
        != EXPECTED_ALIASES
        or tuple(case.get("alias") for case in development_oracle.get("cases") or [])
        != EXPECTED_ALIASES
        or development_oracle.get("source_truth_fact_count") != 24
        or current.get("expected_source_present_fact_count") != 5
        or current_oracle.get("source_present_supported_facts") != 5
        or goal_freeze.get("goal") != "G5.68"
        or GATE3_MINIMAL_METADATA_CONTRACT_VERSION != "1.0.0"
        or GATE3_LLM_METADATA_INSTRUCTION_VERSION != "1.2.0"
        or GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION
        != "broker_reports_metadata_context_policy_v4"
    ):
        raise G568QualificationError("g568_frozen_input_changed")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G568QualificationError("g568_json_object_required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
