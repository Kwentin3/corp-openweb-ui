from __future__ import annotations

import copy
from pathlib import Path

import pytest

from broker_reports_gate1 import Gate3FinancialLabelDictionaryFactory
from broker_reports_gate1.gate3_bounded_labeling import (
    GATE3_LABELING_INSTRUCTION_ID,
    GATE3_LABELING_INSTRUCTION_VERSION,
)
from scripts.live_gate3_source_truth_role_mapping import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    _accepted_fact_attempt_from_sidecar,
    _gate4_role_columns,
    _role_only_document_result,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "models/gemini-3.5-flash"


def test_validated_sidecar_reconstructs_only_the_exact_accepted_fact_set() -> None:
    chunk, payload = _chunk_and_payload()

    attempt = _accepted_fact_attempt_from_sidecar(
        base_payload=payload,
        chunk=chunk,
        model_id=MODEL_ID,
    )

    assert attempt.validation_status == "validated"
    assert attempt.metrics == {
        "accepted_facts_total": 2,
        "provider_called": False,
        "source": "immutable_validated_sidecar",
    }
    assert attempt.validated_output == {
        "schema_version": "broker_reports_financial_annotations_v1",
        "canonical_binding": chunk["canonical_binding"],
        "dictionary_identity": payload["dictionary_identity"],
        "instruction_identity": payload["instruction_identity"],
        "model_identity": {"model_id": MODEL_ID},
        "annotations": [
            {
                "target": chunk["target_mappings"][0]["canonical_target"],
                "financial_label": "SECURITY_PURCHASE",
            },
            {
                "target": chunk["target_mappings"][1]["canonical_target"],
                "financial_label": "TRANSACTION_CHARGE",
            },
        ],
        "validation_status": "validated",
    }
    assert all(
        "roles" not in annotation
        for annotation in attempt.validated_output["annotations"]
    )

    result = _role_only_document_result(
        document_id="document",
        chunk_ordinal=1,
        merged_output={"annotations": [{}, {}]},
    )
    assert result["selection_mode"] == "full_document"
    assert result["document_status"] == "complete"
    assert result["metrics"]["financial_labeling_provider_calls"] == 0
    assert result["metrics"]["role_labeling_provider_calls"] == 1
    assert result["metrics"]["annotations_validated"] == 2

    gate4_fact = {
        "roles": [
            {
                "role": "amount",
                "status": "value",
                "source_binding": {"target": {"kind": "table_cell", "column": 16}},
            },
            {
                "role": "currency",
                "status": "value",
                "source_binding": {"target": {"kind": "table_cell", "column": 17}},
            },
        ]
    }
    assert _gate4_role_columns(gate4_fact) == {"amount": 16, "currency": 17}


def test_foreign_accepted_target_fails_closed_before_role_or_persistence() -> None:
    chunk, payload = _chunk_and_payload()
    changed = copy.deepcopy(payload)
    changed["annotations"][0]["target"] = {
        "kind": "table_row",
        "node_id": "foreign_table",
        "row": 2,
    }

    with pytest.raises(SystemExit, match="accepted_fact_base_target_invalid"):
        _accepted_fact_attempt_from_sidecar(
            base_payload=changed,
            chunk=chunk,
            model_id=MODEL_ID,
        )


def test_live_replay_keeps_factory_route_and_forbids_semantic_repair() -> None:
    source = (
        SERVICE_ROOT / "scripts/live_gate3_source_truth_role_mapping.py"
    ).read_text(encoding="utf-8")

    assert "Gate3RoleLabelingFactory.create_from_chunk" in FACTORY_REQUIRED
    assert "Gate3ChunkBatchLabelingFactory.create" in FACTORY_REQUIRED
    assert "Gate3FinancialAnnotationsPersistenceFactory.create" in FACTORY_REQUIRED
    assert "baseline type rediscovery" in FORBIDDEN
    assert "cross-authority merge" in FORBIDDEN
    assert "Gate3RoleLabelingFactory(" in source
    assert ").create_from_chunk(" in source
    assert 'financial_labeling_provider_calls": 0' in source
    assert "manual role replacement" in source
    assert "DELETE FROM" not in source


def _chunk_and_payload() -> tuple[dict, dict]:
    dictionary = Gate3FinancialLabelDictionaryFactory.create().load_published()
    canonical_binding = {
        "document_id": "document",
        "canonical_version_id": "canonical",
    }
    targets = [
        {"kind": "table_row", "node_id": "table", "row": 2},
        {
            "kind": "table_cell",
            "node_id": "table",
            "row": 2,
            "column": 18,
        },
    ]
    chunk = {
        "ordinal": 1,
        "canonical_binding": canonical_binding,
        "model_view": {"media_type": "text/markdown", "content": "source"},
        "target_mappings": [
            {"target_alias": "t001", "canonical_target": targets[0]},
            {"target_alias": "t002", "canonical_target": targets[1]},
        ],
    }
    payload = {
        "schema_version": "broker_reports_financial_annotations_v2",
        "canonical_binding": canonical_binding,
        "dictionary_identity": {
            "dictionary_id": dictionary["dictionary_id"],
            "semantic_version": dictionary["semantic_version"],
        },
        "role_pack_identity": {
            "role_pack_id": "broker-reports-financial-roles",
            "semantic_version": "2.0.0",
        },
        "instruction_identity": {
            "instruction_id": GATE3_LABELING_INSTRUCTION_ID,
            "semantic_version": GATE3_LABELING_INSTRUCTION_VERSION,
        },
        "role_instruction_identity": {
            "instruction_id": "broker-reports-source-bound-role-labeling",
            "semantic_version": "1.1.0",
        },
        "model_identity": {"model_id": MODEL_ID},
        "annotations": [
            {
                "target": targets[0],
                "financial_label": "SECURITY_PURCHASE",
                "roles": [{"role": "date", "status": "missing"}],
            },
            {
                "target": targets[1],
                "financial_label": "TRANSACTION_CHARGE",
                "roles": [{"role": "amount", "status": "missing"}],
            },
        ],
        "validation_status": "validated",
    }
    return chunk, payload
