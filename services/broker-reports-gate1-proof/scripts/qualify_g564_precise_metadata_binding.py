#!/usr/bin/env python3
"""Prove G5.64 precise metadata binding before any provider replay."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver  # noqa: E402
from broker_reports_gate1.canonical_store import CanonicalReaderFactory  # noqa: E402
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
    build_metadata_context_package,
)
from broker_reports_gate1.gate3_metadata_source_facts import (  # noqa: E402
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
)


EXPECTED_ALIASES = ("pdf_002", "pdf_024", "holdout_a", "holdout_b")
EXPECTED_FACT_COUNTS = {
    "pdf_002": 9,
    "pdf_024": 6,
    "holdout_a": 3,
    "holdout_b": 6,
}
FROZEN_INPUT_CONTEXT_POLICY_VERSION = "broker_reports_metadata_context_policy_v2"

FACTORY_REQUIRED = (
    "ArtifactResolver.catalog_case, CanonicalReaderFactory.create and "
    "build_metadata_context_package are the only qualification route"
)
FORBIDDEN = (
    "provider calls, oracle-fed selection, source reads, semantic selectors, "
    "broker wording, prompt changes or output repair"
)


class G564BindingError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-corpus", type=Path, required=True)
    parser.add_argument("--g562-oracle", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()

    frozen = _read_json(args.frozen_corpus.resolve())
    oracle = _read_json(args.g562_oracle.resolve())
    outputs = (args.private_output.resolve(), args.safe_output.resolve())
    for output in outputs:
        if _is_within(output, REPO_ROOT.resolve()):
            raise G564BindingError("g564_private_output_inside_repository")
        if output.exists():
            raise G564BindingError("g564_output_must_not_exist")

    private_result, safe_result = qualify_binding(frozen=frozen, oracle=oracle)
    for output, result in zip(outputs, (private_result, safe_result), strict=True):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    return 0


def qualify_binding(
    *, frozen: dict[str, Any], oracle: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_inputs(frozen=frozen, oracle=oracle)
    oracle_by_alias = {item["alias"]: item for item in oracle["cases"]}
    private_cases: list[dict[str, Any]] = []

    for frozen_case in frozen["cases"]:
        artifact = _read_frozen_canonical(frozen_case)
        # Complete structural packaging finishes before oracle measurement starts.
        package, registry = build_metadata_context_package(
            artifact=artifact,
            document_id=frozen_case["document_id"],
            canonical_version_id=artifact["artifact_id"],
        )
        private_cases.append(
            qualify_case(
                alias=frozen_case["alias"],
                oracle_case=oracle_by_alias[frozen_case["alias"]],
                package=package,
                registry=registry,
            )
        )

    visible = sum(item["visible"] for item in private_cases)
    ambiguous = sum(item["structural_ambiguity"] for item in private_cases)
    invisible = sum(item["invisible"] for item in private_cases)
    whole_table_targets = sum(
        item["whole_table_targets"] for item in private_cases
    )
    if visible != 24 or invisible != 0 or ambiguous != 0:
        raise G564BindingError("g564_precise_binding_incomplete")
    if whole_table_targets != 0:
        raise G564BindingError("g564_whole_table_target_retained")

    terminal = [
        "METADATA_STRUCTURAL_SOURCE_BINDING_PROVEN",
        "FROZEN_ORACLE_VISIBILITY_24_OF_24_PRESERVED",
        "WHOLE_TABLE_LITERAL_AMBIGUITY_REMOVED",
        "STRUCTURAL_AMBIGUITY_FOR_ORACLE_FACTS_ZERO",
        "LLM_REPLAY_AUTHORIZED_ONCE",
    ]
    private_result = {
        "schema_version": "broker_reports_g564_binding_private_v1",
        "goal": "G5.64",
        "terminal": terminal,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "input_context_policy_version": FROZEN_INPUT_CONTEXT_POLICY_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "provider_calls": 0,
        "selector_accepts_oracle": False,
        "cases": private_cases,
        "visible": visible,
        "invisible": invisible,
        "structural_ambiguity": ambiguous,
        "whole_table_targets": whole_table_targets,
    }
    safe_cases = [
        {
            "alias": item["alias"],
            "oracle_facts": item["oracle_facts"],
            "visible": item["visible"],
            "invisible": item["invisible"],
            "structural_ambiguity": item["structural_ambiguity"],
            "selected_targets": item["context_metrics"]["selected_targets"],
            "row_header_targets": item["row_header_targets"],
            "whole_table_targets": item["whole_table_targets"],
            "rendered_context_chars": item["context_metrics"][
                "rendered_context_chars"
            ],
        }
        for item in private_cases
    ]
    safe_result = {
        "schema_version": "broker_reports_g564_binding_safe_v1",
        "goal": "G5.64",
        "terminal": terminal,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "provider_calls": 0,
        "selector_accepts_oracle": False,
        "frozen_corpus": list(EXPECTED_ALIASES),
        "cases": safe_cases,
        "visible": visible,
        "invisible": invisible,
        "structural_ambiguity": ambiguous,
        "whole_table_targets": whole_table_targets,
        "semantic_hints": 0,
        "broker_specific_rules": 0,
        "private_values_committed": False,
    }
    return private_result, safe_result


def qualify_case(
    *,
    alias: str,
    oracle_case: dict[str, Any],
    package: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    qualified: list[dict[str, Any]] = []
    for fact in oracle_case["facts"]:
        binding = fact["canonical_binding"]
        aliases = find_structural_target_aliases(
            registry=registry,
            node_id=binding["node_id"],
            field_path=binding["field_path"],
            literal=binding["literal"],
        )
        if len(aliases) != 1:
            raise G564BindingError(
                f"g564_fact_binding_ambiguous:{alias}:{fact['fact_id']}"
            )
        qualified.append(
            {
                "fact_id": fact["fact_id"],
                "fact_type": fact["fact_type"],
                "canonical_binding": copy.deepcopy(binding),
                "context_target_alias": aliases[0],
                "visibility": "VISIBLE_AND_PRECISE",
            }
        )
    expected = EXPECTED_FACT_COUNTS[alias]
    if len(qualified) != expected:
        raise G564BindingError(f"g564_oracle_fact_count_changed:{alias}")
    metrics = package["metrics"]
    if (
        metrics.get("position_cutoff_applied") is not False
        or metrics.get("all_structural_candidates_selected") is not True
        or metrics.get("target_limit_reached") is not False
    ):
        raise G564BindingError("g564_position_cutoff_active")
    targets = list((registry.get("targets") or {}).values())
    row_targets = sum(
        target.get("region_kind") == "SMALL_TABLE_ROW_WITH_HEADER"
        for target in targets
    )
    whole_targets = sum(
        target.get("region_kind") == "SMALL_TABLE" for target in targets
    )
    return {
        "alias": alias,
        "oracle_facts": expected,
        "visible": len(qualified),
        "invisible": 0,
        "structural_ambiguity": 0,
        "fact_type_counts": dict(
            sorted(Counter(item["fact_type"] for item in qualified).items())
        ),
        "context_metrics": copy.deepcopy(metrics),
        "row_header_targets": row_targets,
        "whole_table_targets": whole_targets,
        "qualified_facts": qualified,
    }


def find_structural_target_aliases(
    *,
    registry: dict[str, Any],
    node_id: str,
    field_path: str,
    literal: str,
) -> list[str]:
    expected_path = _binding_field_path(field_path)
    return sorted(
        alias
        for alias, target in (registry.get("targets") or {}).items()
        if target.get("node_id") == node_id
        and sum(
            _binding_field_path(str(fragment.get("field_path") or ""))
            == expected_path
            and isinstance(fragment.get("literal"), str)
            and literal in fragment["literal"]
            for fragment in target.get("fragments") or []
            if isinstance(fragment, dict)
        )
        == 1
    )


def _binding_field_path(value: str) -> str:
    return re.sub(r"\.(?:displayed_value|value)$", "", value)


def _validate_inputs(*, frozen: dict[str, Any], oracle: dict[str, Any]) -> None:
    aliases = tuple(item.get("alias") for item in frozen.get("cases") or [])
    oracle_aliases = tuple(item.get("alias") for item in oracle.get("cases") or [])
    if aliases != EXPECTED_ALIASES or oracle_aliases != EXPECTED_ALIASES:
        raise G564BindingError("g564_frozen_corpus_changed")
    if (
        frozen.get("frozen_before_code") is not True
        or frozen.get("contract_version") != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or frozen.get("context_policy_version")
        != FROZEN_INPUT_CONTEXT_POLICY_VERSION
    ):
        raise G564BindingError("g564_frozen_contract_changed")
    if (
        oracle.get("goal") != "G5.62"
        or oracle.get("contract_version") != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or oracle.get("source_truth_fact_count") != 24
        or oracle.get("canonical_loss_count") != 0
        or oracle.get("provider_calls") != 0
    ):
        raise G564BindingError("g564_g562_oracle_invalid")


def _read_frozen_canonical(frozen_case: dict[str, Any]) -> dict[str, Any]:
    root = Path(frozen_case["source_store_root"]).resolve()
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
        raise G564BindingError("g564_canonical_record_ambiguous")
    record = records[0]
    artifact = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read(record.artifact_id, context)
    )
    if (
        record.artifact_id != frozen_case["canonical_artifact_id"]
        or artifact.get("artifact_id") != frozen_case["canonical_version_id"]
        or artifact.get("canonical_root_hash")
        != frozen_case["canonical_root_sha256"]
    ):
        raise G564BindingError("g564_frozen_canonical_identity_changed")
    return artifact


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G564BindingError("g564_json_object_required")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
