from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from live_verify_gate2_financial_production_migration import (  # noqa: E402
    FUNCTION_ID,
    GATE1_FUNCTION_ID,
    SOURCE_FUNCTION_ID,
    evaluate,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)


def _scope(*, after: bool):
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    type_counts = (
        {
            "broker_reports_financial_evidence_inputs_v1": 2,
            "broker_reports_gate2_financial_context_v1": 1,
            (
                "broker_reports_gate2_financial_evidence_"
                "production_receipt_v1"
            ): 1,
            (
                "broker_reports_gate2_financial_evidence_"
                "production_run_v1"
            ): 1,
        }
        if after
        else {}
    )
    return {
        "record_hashes": (
            {"existing": "same", "new": "value"}
            if after
            else {"existing": "same"}
        ),
        "new_financial": {
            "type_counts": type_counts,
            "receipt": (
                {
                    "status": "passed",
                    "uncovered_source_refs_total": 0,
                    "unclassified_value_loss_total": 0,
                    "duplicate_interpretations_total": 0,
                    "fallback_total": 0,
                    "repair_attempts_total": 0,
                    "provider_failures_total": 0,
                    "schema_failures_total": 0,
                }
                if after
                else {}
            ),
            "run": (
                {
                    "registry_version": registry.registry_version,
                    "registry_hash": registry.registry_hash,
                    "legacy_read_policy": "dual_read",
                    "write_policy": "new_schema_only",
                    "gate3_fields_total": 0,
                }
                if after
                else {}
            ),
            "context": (
                {"source_scopes_total": 2} if after else {}
            ),
        },
    }


def _runtime():
    return {
        "knowledge_rows": 0,
        "vector_file_count": 0,
        "vector_dir_count": 0,
        "vector_collections_count": 0,
        "vector_size_bytes": 0,
        "file_rows": 1,
        "document_rows": 1,
        "artifactstore_record_count": 10,
    }


def test_evaluate_passes_atomic_new_schema_migration():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    hashes = {
        GATE1_FUNCTION_ID: "gate1",
        SOURCE_FUNCTION_ID: "source",
        FUNCTION_ID: "domain",
    }
    result = evaluate(
        before_scope=_scope(after=False),
        after_scope=_scope(after=True),
        before_runtime=_runtime(),
        after_runtime={
            **_runtime(),
            "artifactstore_record_count": 20,
        },
        before_functions=hashes,
        after_functions=hashes,
        domain_valves={
            "financial_evidence_enabled": True,
            "financial_evidence_registry_version": (
                registry.registry_version
            ),
        },
        chat_content=(
            "Gate 2 structured financial evidence context: completed."
        ),
    )

    assert result["status"] == "passed"
    assert all(result["checks"].values())


def test_evaluate_fails_on_existing_artifact_rewrite_or_vector_delta():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    before = _scope(after=False)
    after = _scope(after=True)
    after["record_hashes"]["existing"] = "changed"
    runtime_after = {**_runtime(), "vector_size_bytes": 1}
    result = evaluate(
        before_scope=before,
        after_scope=after,
        before_runtime=_runtime(),
        after_runtime=runtime_after,
        before_functions={
            GATE1_FUNCTION_ID: "gate1",
            SOURCE_FUNCTION_ID: "source",
            FUNCTION_ID: "old-domain",
        },
        after_functions={
            GATE1_FUNCTION_ID: "gate1",
            SOURCE_FUNCTION_ID: "source",
            FUNCTION_ID: "new-domain",
        },
        domain_valves={
            "financial_evidence_enabled": True,
            "financial_evidence_registry_version": (
                registry.registry_version
            ),
        },
        chat_content=(
            "Gate 2 structured financial evidence context: completed."
        ),
    )

    assert result["status"] == "failed"
    assert result["checks"]["preexisting_artifacts_unchanged"] is False
    assert result["checks"]["knowledge_rag_vector_delta_zero"] is False
