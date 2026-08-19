#!/usr/bin/env python3
"""Revalidate a frozen G5.61 raw provider result without another model call."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver  # noqa: E402
from broker_reports_gate1.canonical_store import CanonicalReaderFactory  # noqa: E402
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    Gate3LlmMetadataAdapterError,
    validate_metadata_proposal,
)
from live_g561_llm_metadata_generalization import (  # noqa: E402
    SOURCE_ABSENCE_FACT_TYPES,
    _compare_facts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-private-result", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    source_path = args.frozen_private_result.resolve()
    private_output = args.private_output.resolve()
    safe_output = args.safe_output.resolve()
    if private_output.exists() or safe_output.exists():
        raise SystemExit("revalidation_output_must_be_new")
    frozen_result = _read_json(source_path)
    if (
        frozen_result.get("schema_version") != "broker_reports_g561_private_result_v1"
        or frozen_result.get("provider_submissions_total") != 4
        or len(frozen_result.get("cases") or []) != 4
    ):
        raise SystemExit("frozen_private_result_invalid")

    private_cases: list[dict[str, Any]] = []
    safe_cases: list[dict[str, Any]] = []
    root = source_path.parent
    for case, frozen_case in zip(
        frozen_result["cases"],
        frozen_result["frozen_contract"]["cases"],
        strict=True,
    ):
        alias = case["alias"]
        if alias != frozen_case["alias"]:
            raise SystemExit("frozen_case_order_changed")
        store_root = root / alias / "working-store"
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=store_root / "artifacts.sqlite3",
                payload_root=store_root / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(
            **frozen_case["context"],
            allow_private=True,
        )
        records = [
            record
            for record in ArtifactResolver(store).catalog_case(context)
            if record.artifact_type == "broker_reports_canonical_artifact_v1"
            and record.document_id == frozen_case["document_id"]
        ]
        if len(records) != 1:
            raise SystemExit(f"canonical_record_ambiguous:{alias}")
        artifact = (
            CanonicalReaderFactory(
                store=store,
                read_enabled=True,
            )
            .create()
            .read(records[0].artifact_id, context)
        )
        validation_error = None
        try:
            validated = validate_metadata_proposal(
                raw_model_output=case["raw_model_output"],
                artifact=artifact,
                context_package=case["context_package"],
                binding_registry=case["binding_registry"],
                model_id=frozen_result["frozen_contract"]["model_id"],
            )
        except Gate3LlmMetadataAdapterError as exc:
            validated = None
            validation_error = exc.code
        facts = validated["metadata_facts"] if validated is not None else []
        comparison = _compare_facts(
            oracle_facts=case["oracle_facts"],
            candidate_facts=facts,
        )
        source_absence_facts = sum(
            fact["fact_type"] in SOURCE_ABSENCE_FACT_TYPES for fact in facts
        )
        passed = (
            validated is not None
            and comparison["semantic_exact"]
            and comparison["oracle_node_provenance_exact"]
            and source_absence_facts == 0
        )
        failure_class = None
        if not passed:
            failure_class = validation_error or (
                "semantic_oracle_mismatch"
                if not comparison["semantic_exact"]
                else "oracle_provenance_mismatch"
            )
        private_cases.append(
            {
                "alias": alias,
                "case_passed": passed,
                "failure_class": failure_class,
                "validation_error_code": validation_error,
                "comparison": comparison,
                "source_absence_facts": source_absence_facts,
                "validated_output": copy.deepcopy(validated),
            }
        )
        safe_cases.append(
            {
                "alias": alias,
                "case_passed": passed,
                "failure_class": failure_class,
                "validation_error_code": validation_error,
                "oracle_fact_count": len(case["oracle_facts"]),
                "candidate_fact_count": len(facts),
                "semantic_exact": comparison["semantic_exact"],
                "oracle_node_provenance_exact": comparison[
                    "oracle_node_provenance_exact"
                ],
                "missing_facts": comparison["missing_facts"],
                "invented_facts": comparison["invented_facts"],
                "duplicate_assertions": comparison["duplicate_assertions"],
                "oracle_fact_type_counts": comparison["oracle_fact_type_counts"],
                "candidate_fact_type_counts": comparison["candidate_fact_type_counts"],
                "source_absence_facts": source_absence_facts,
            }
        )

    terminal = (
        "LLM_METADATA_ADAPTER_GENERALIZATION_PROVEN"
        if all(item["case_passed"] for item in private_cases)
        else "LLM_METADATA_ADAPTER_NOT_YET_RELIABLE"
    )
    exact_failures = sorted(
        {item["failure_class"] for item in private_cases if item["failure_class"]}
    )
    private = {
        "schema_version": "broker_reports_g561_revalidation_private_v1",
        "terminal": terminal,
        "exact_failure_classes": exact_failures,
        "frozen_provider_result": str(source_path),
        "original_provider_submissions": 4,
        "provider_calls_during_revalidation": 0,
        "raw_model_output_repaired": False,
        "cases": private_cases,
    }
    safe = {
        "schema_version": "broker_reports_g561_revalidation_safe_v1",
        "goal": "G5.61",
        "terminal": terminal,
        "exact_failure_classes": exact_failures,
        "original_provider_submissions": 4,
        "provider_calls_during_revalidation": 0,
        "raw_model_output_repaired": False,
        "cases": safe_cases,
    }
    _write_json(private_output, private)
    _write_json(safe_output, safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if terminal == "LLM_METADATA_ADAPTER_GENERALIZATION_PROVEN" else 2


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("json_object_required")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
