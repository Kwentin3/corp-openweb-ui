#!/usr/bin/env python3
"""Prove G5.66 line-precise binding before the one allowed holdout replay."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
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
from broker_reports_gate1.canonical_store import CanonicalReaderFactory  # noqa: E402
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    build_metadata_context_package,
)
from broker_reports_gate1.gate3_metadata_source_facts import (  # noqa: E402
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
)


EXPECTED_SOURCE_SHA256 = (
    "79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d"
)
EXPECTED_OLD_AMBIGUOUS = 4

FACTORY_REQUIRED = (
    "CanonicalReaderFactory.create and build_metadata_context_package are the "
    "only source-binding qualification route"
)
FORBIDDEN = (
    "provider calls, oracle-fed packaging, semantic selectors, broker wording, "
    "prompt changes, fixed character windows or output repair"
)


class G566BindingError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--source-truth", type=Path, required=True)
    parser.add_argument("--g565-result", type=Path, required=True)
    parser.add_argument("--canonical-store", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    outputs = (args.private_output.resolve(), args.safe_output.resolve())
    for output in outputs:
        if _is_within(output, REPO_ROOT.resolve()):
            raise G566BindingError("g566_private_output_inside_repository")
        if output.exists():
            raise G566BindingError("g566_output_must_not_exist")

    preparation = _read_json(args.preparation.resolve())
    source_truth = _read_json(args.source_truth.resolve())
    old_result = _read_json(args.g565_result.resolve())
    artifact = _read_active_canonical(
        store_root=args.canonical_store.resolve(),
        preparation=preparation,
    )

    # Packaging is complete before either oracle or old output is inspected.
    package, registry = build_metadata_context_package(
        artifact=artifact,
        document_id=preparation["document_id"],
        canonical_version_id=artifact["artifact_id"],
    )
    private_result, safe_result = qualify_holdout(
        artifact=artifact,
        package=package,
        registry=registry,
        preparation=preparation,
        source_truth=source_truth,
        old_result=old_result,
    )
    for output, result in zip(outputs, (private_result, safe_result), strict=True):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    return 0


def qualify_holdout(
    *,
    artifact: dict[str, Any],
    package: dict[str, Any],
    registry: dict[str, Any],
    preparation: dict[str, Any],
    source_truth: dict[str, Any],
    old_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_frozen_inputs(
        artifact=artifact,
        preparation=preparation,
        source_truth=source_truth,
        old_result=old_result,
    )
    targets = registry.get("targets") or {}
    if not targets or any(
        target.get("region_kind") == "TEXT_LINE"
        and len(target.get("fragments") or []) != 1
        for target in targets.values()
    ):
        raise G566BindingError("g566_text_line_address_invalid")

    oracle_facts: list[dict[str, Any]] = []
    for fact in source_truth["facts"]:
        aliases = _aliases_for_fragment(
            registry=registry,
            node_id=fact["node_id"],
            field_path=fact["field_path"],
            literal=fact["source_literal"],
        )
        if len(aliases) != 1:
            raise G566BindingError("g566_holdout_oracle_binding_not_precise")
        oracle_facts.append(
            {
                "fact_type": fact["fact_type"],
                "source_literal": fact["source_literal"],
                "field_path": fact["field_path"],
                "source_target_alias": aliases[0],
                "visibility": "VISIBLE_AND_PRECISE",
            }
        )

    old_targets = old_result["binding_registry"]["targets"]
    old_response = json.loads(old_result["raw_model_output"])
    old_ambiguous: list[dict[str, Any]] = []
    for proposal in old_response["facts"]:
        old_target = old_targets[proposal["source_target_alias"]]
        matching = [
            fragment
            for fragment in old_target["fragments"]
            if proposal["source_literal"] in fragment["literal"]
        ]
        if len(matching) < 2:
            continue
        occurrences: list[dict[str, str]] = []
        for fragment in matching:
            aliases = _aliases_for_fragment(
                registry=registry,
                node_id=old_target["node_id"],
                field_path=fragment["field_path"],
                literal=proposal["source_literal"],
            )
            if len(aliases) != 1:
                raise G566BindingError("g566_old_ambiguity_not_split")
            occurrences.append(
                {
                    "field_path": fragment["field_path"],
                    "source_target_alias": aliases[0],
                }
            )
        old_ambiguous.append(
            {
                "fact_type": proposal["fact_type"],
                "source_literal": proposal["source_literal"],
                "old_source_target_alias": proposal["source_target_alias"],
                "old_occurrences": len(matching),
                "new_occurrences": occurrences,
            }
        )
    if len(old_ambiguous) != EXPECTED_OLD_AMBIGUOUS:
        raise G566BindingError("g566_old_ambiguous_count_changed")

    metrics = package["metrics"]
    if (
        metrics.get("all_structural_candidates_selected") is not True
        or metrics.get("position_cutoff_applied") is not False
        or metrics.get("target_limit_reached") is not False
    ):
        raise G566BindingError("g566_packaging_cutoff_active")

    terminal = [
        "UNSEEN_HOLDOUT_SOURCE_BINDING_PROVEN",
        "REPEATED_LITERAL_PHYSICAL_AMBIGUITY_ZERO",
        "HOLDOUT_ORACLE_VISIBILITY_5_OF_5",
        "ONE_CLEAN_REPLAY_AUTHORIZED",
    ]
    private_result = {
        "schema_version": "broker_reports_g566_binding_private_v1",
        "goal": "G5.66",
        "terminal": terminal,
        "provider_calls": 0,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "canonical_version_id": artifact["artifact_id"],
        "canonical_root_sha256": artifact["canonical_root_hash"],
        "metadata_contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "selector_accepts_oracle": False,
        "context_metrics": copy.deepcopy(metrics),
        "oracle_facts": oracle_facts,
        "g565_ambiguous_bindings": old_ambiguous,
        "holdout_visibility": len(oracle_facts),
        "physical_binding_ambiguity": 0,
        "semantic_hints": 0,
        "broker_specific_rules": 0,
        "fixed_character_windows": 0,
    }
    safe_result = {
        "schema_version": "broker_reports_g566_binding_safe_v1",
        "goal": "G5.66",
        "terminal": terminal,
        "provider_calls": 0,
        "metadata_contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "selector_accepts_oracle": False,
        "holdout_oracle_facts": len(source_truth["facts"]),
        "holdout_visibility": len(oracle_facts),
        "g565_ambiguous_bindings_qualified": len(old_ambiguous),
        "physical_binding_ambiguity": 0,
        "selected_targets": metrics["selected_targets"],
        "rendered_context_chars": metrics["rendered_context_chars"],
        "semantic_hints": 0,
        "broker_specific_rules": 0,
        "fixed_character_windows": 0,
        "private_values_committed": False,
    }
    return private_result, safe_result


def _aliases_for_fragment(
    *, registry: dict[str, Any], node_id: str, field_path: str, literal: str
) -> list[str]:
    return sorted(
        alias
        for alias, target in (registry.get("targets") or {}).items()
        if target.get("node_id") == node_id
        and sum(
            fragment.get("field_path") == field_path
            and isinstance(fragment.get("literal"), str)
            and literal in fragment["literal"]
            for fragment in target.get("fragments") or []
            if isinstance(fragment, dict)
        )
        == 1
    )


def _validate_frozen_inputs(
    *,
    artifact: dict[str, Any],
    preparation: dict[str, Any],
    source_truth: dict[str, Any],
    old_result: dict[str, Any],
) -> None:
    if (
        preparation.get("source_sha256") != EXPECTED_SOURCE_SHA256
        or source_truth.get("source_sha256") != EXPECTED_SOURCE_SHA256
        or source_truth.get("source_present_supported_facts") != 5
        or source_truth.get("qualified_before_llm_execution") is not True
        or source_truth.get("llm_output_used_as_truth_hint") is not False
        or preparation.get("canonical_artifact_id") != artifact.get("artifact_id")
        or preparation.get("canonical_root_sha256")
        != artifact.get("canonical_root_hash")
        or old_result.get("goal") != "G5.65"
        or old_result.get("provider_submissions") != 1
        or GATE3_MINIMAL_METADATA_CONTRACT_VERSION != "1.0.0"
        or GATE3_LLM_METADATA_INSTRUCTION_VERSION != "1.1.0"
        or GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION
        != "broker_reports_metadata_context_policy_v4"
    ):
        raise G566BindingError("g566_frozen_input_changed")


def _read_active_canonical(
    *, store_root: Path, preparation: dict[str, Any]
) -> dict[str, Any]:
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        **preparation["context"],
        allow_private=True,
        require_source_available=True,
    )
    return CanonicalReaderFactory(store=store, read_enabled=True).create().read_active(
        preparation["document_id"], context
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G566BindingError("g566_json_object_required")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
