#!/usr/bin/env python3
"""Prove G5.63 metadata visibility before any provider replay."""

from __future__ import annotations

import argparse
from collections import Counter
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

FACTORY_REQUIRED = (
    "ArtifactResolver.catalog_case, CanonicalReaderFactory.create and "
    "build_metadata_context_package are the only qualification route"
)
FORBIDDEN = (
    "provider calls, oracle-fed selection, source reads, broker wording, "
    "position cutoffs, prompt changes or output repair"
)


class G563VisibilityError(RuntimeError):
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
    private_output = args.private_output.resolve()
    safe_output = args.safe_output.resolve()
    for output in (private_output, safe_output):
        if _is_within(output, REPO_ROOT.resolve()):
            raise G563VisibilityError("g563_private_output_inside_repository")
        if output.exists():
            raise G563VisibilityError("g563_output_must_not_exist")

    private_result, safe_result = qualify_visibility(
        frozen=frozen,
        oracle=oracle,
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


def qualify_visibility(
    *, frozen: dict[str, Any], oracle: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_inputs(frozen=frozen, oracle=oracle)
    oracle_by_alias = {item["alias"]: item for item in oracle["cases"]}
    private_cases: list[dict[str, Any]] = []

    for frozen_case in frozen["cases"]:
        alias = frozen_case["alias"]
        artifact = _read_frozen_canonical(frozen_case)
        # Selection is complete before the oracle is used as a measurement tool.
        package, registry = build_metadata_context_package(
            artifact=artifact,
            document_id=frozen_case["document_id"],
            canonical_version_id=artifact["artifact_id"],
        )
        case_result = qualify_case(
            alias=alias,
            oracle_case=oracle_by_alias[alias],
            package=package,
            registry=registry,
        )
        private_cases.append(case_result)

    total_visible = sum(item["visible"] for item in private_cases)
    total_invisible = sum(item["invisible"] for item in private_cases)
    if total_visible != 24 or total_invisible != 0:
        raise G563VisibilityError("g563_visibility_not_complete")

    private_result = {
        "schema_version": "broker_reports_g563_visibility_private_v1",
        "goal": "G5.63",
        "terminal": [
            "METADATA_CONTEXT_POSITION_INDEPENDENCE_PROVEN",
            "FROZEN_ORACLE_CONTEXT_VISIBILITY_24_OF_24",
            "MAGIC_TEXT_HEAD_CUTOFF_REMOVED",
            "CONTEXT_VISIBILITY_FAILURES_ZERO",
            "LLM_REPLAY_AUTHORIZED_ONCE",
        ],
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "provider_calls": 0,
        "selector_accepts_oracle": False,
        "cases": private_cases,
        "visible": total_visible,
        "invisible": total_invisible,
    }
    safe_cases = [
        {
            "alias": item["alias"],
            "oracle_facts": item["oracle_facts"],
            "visible": item["visible"],
            "invisible": item["invisible"],
            "selected_targets": item["context_metrics"]["selected_targets"],
            "rendered_context_chars": item["context_metrics"][
                "rendered_context_chars"
            ],
            "excluded_large_table_nodes": item["context_metrics"][
                "excluded_large_table_nodes"
            ],
        }
        for item in private_cases
    ]
    safe_result = {
        "schema_version": "broker_reports_g563_visibility_safe_v1",
        "goal": "G5.63",
        "terminal": private_result["terminal"],
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "provider_calls": 0,
        "selector_accepts_oracle": False,
        "frozen_corpus": list(EXPECTED_ALIASES),
        "cases": safe_cases,
        "visible": total_visible,
        "invisible": total_invisible,
        "position_cutoff_applied": False,
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
        aliases = find_visible_target_aliases(
            registry=registry,
            node_id=binding["node_id"],
            literal=binding["literal"],
        )
        if len(aliases) != 1:
            raise G563VisibilityError(
                f"g563_fact_visibility_ambiguous:{alias}:{fact['fact_id']}"
            )
        qualified.append(
            {
                "fact_id": fact["fact_id"],
                "fact_type": fact["fact_type"],
                "canonical_binding": copy.deepcopy(binding),
                "context_target_alias": aliases[0],
                "visibility": "VISIBLE",
            }
        )
    expected = EXPECTED_FACT_COUNTS[alias]
    if len(qualified) != expected:
        raise G563VisibilityError(f"g563_oracle_fact_count_changed:{alias}")
    metrics = package["metrics"]
    if (
        metrics.get("position_cutoff_applied") is not False
        or metrics.get("all_structural_candidates_selected") is not True
        or metrics.get("target_limit_reached") is not False
    ):
        raise G563VisibilityError("g563_position_cutoff_still_active")
    return {
        "alias": alias,
        "oracle_facts": expected,
        "visible": len(qualified),
        "invisible": 0,
        "fact_type_counts": dict(
            sorted(Counter(item["fact_type"] for item in qualified).items())
        ),
        "context_metrics": copy.deepcopy(metrics),
        "qualified_facts": qualified,
    }


def find_visible_target_aliases(
    *, registry: dict[str, Any], node_id: str, literal: str
) -> list[str]:
    return sorted(
        alias
        for alias, target in (registry.get("targets") or {}).items()
        if target.get("node_id") == node_id
        and isinstance(target.get("content"), str)
        and literal in target["content"]
    )


def _validate_inputs(*, frozen: dict[str, Any], oracle: dict[str, Any]) -> None:
    aliases = tuple(item.get("alias") for item in frozen.get("cases") or [])
    oracle_aliases = tuple(item.get("alias") for item in oracle.get("cases") or [])
    if aliases != EXPECTED_ALIASES or oracle_aliases != EXPECTED_ALIASES:
        raise G563VisibilityError("g563_frozen_corpus_changed")
    if not frozen.get("frozen_before_code"):
        raise G563VisibilityError("g563_frozen_contract_invalid")
    if (
        frozen.get("contract_version") != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or frozen.get("context_policy_version")
        != GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION
    ):
        raise G563VisibilityError("g563_frozen_contract_changed")
    if (
        oracle.get("goal") != "G5.62"
        or oracle.get("contract_version") != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or oracle.get("source_truth_fact_count") != 24
        or oracle.get("canonical_loss_count") != 0
        or oracle.get("provider_calls") != 0
    ):
        raise G563VisibilityError("g563_g562_oracle_invalid")


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
        raise G563VisibilityError("g563_canonical_record_ambiguous")
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
        raise G563VisibilityError("g563_frozen_canonical_identity_changed")
    return artifact


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G563VisibilityError("g563_json_object_required")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
