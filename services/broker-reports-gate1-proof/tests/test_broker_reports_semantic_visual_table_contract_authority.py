from __future__ import annotations

from pathlib import Path

import pytest

from broker_reports_gate1 import architecture_policy
from broker_reports_gate1 import semantic_visual_table_contracts as contracts
from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (
    CANONICAL_TABLE_SCHEMA_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
ARCHITECTURE_DOCUMENT = REPOSITORY_ROOT / architecture_policy.ARCHITECTURE_AUTHORITY
SEMANTIC_CONTRACT_DOCUMENT = (
    REPOSITORY_ROOT
    / "docs/stage2/contracts/BROKER_REPORTS_SEMANTIC_VISUAL_TABLE_TRANSCRIPTION.v1.md"
)


def test_semantic_model_schema_is_closed_and_content_only() -> None:
    schema = contracts.semantic_table_transcription_schema()

    assert schema["$id"] == "broker_reports_semantic_table_transcription_v1"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"description", "rows"}
    assert set(schema["properties"]) == {"description", "rows"}
    assert schema["properties"]["description"] == {
        "type": "string",
        "maxLength": contracts.MAX_SEMANTIC_DESCRIPTION_CHARACTERS,
    }
    assert contracts.DESCRIPTION_TOKEN_BUDGET == 120

    rows = schema["properties"]["rows"]
    assert rows["minItems"] == 1
    assert rows["maxItems"] == contracts.MAX_SEMANTIC_ROWS
    assert rows["items"]["maxItems"] == contracts.MAX_SEMANTIC_COLUMNS
    assert rows["items"]["items"]["anyOf"] == [
        {"type": "string", "maxLength": contracts.MAX_SEMANTIC_CELL_CHARACTERS},
        {"type": "null"},
    ]
    assert _property_names(schema).isdisjoint(contracts.MODEL_FORBIDDEN_FIELDS)


def test_model_view_contains_only_the_semantic_task() -> None:
    model_view = contracts.semantic_table_transcription_model_view()
    task = " ".join(model_view["task"].split())

    assert set(model_view) == {"task"}
    assert model_view["task"] == contracts.SEMANTIC_TABLE_TRANSCRIPTION_PROMPT
    assert "Preserve every source-visible label, amount" in task
    assert "Do not repair, infer, normalize" in task
    assert all(field not in model_view for field in contracts.MODEL_FORBIDDEN_FIELDS)


def test_boundary_parse_is_strict_and_performs_no_repair() -> None:
    source = {
        "description": "Visible grouped balance table.",
        "rows": [["Cash", "1 000,00 ₽"], ["Total", None]],
    }

    parsed = contracts.parse_semantic_table_transcription(source)

    assert parsed == source
    assert parsed is not source
    with pytest.raises(
        contracts.SemanticTableTranscriptionContractError,
        match="semantic_table_transcription_fields_invalid",
    ):
        contracts.parse_semantic_table_transcription(
            {**source, "table_id": "model_generated_forbidden_metadata"}
        )


def test_architecture_policy_makes_semantic_boundary_authoritative() -> None:
    assert architecture_policy.ARCHITECTURE_POLICY_VERSION == (
        "broker_reports_architecture_policy_v2"
    )
    assert architecture_policy.VISUAL_TABLE_MODEL_FACING_CONTRACT == (
        contracts.SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION
    )
    assert architecture_policy.VISUAL_TABLE_MODEL_RESPONSE_FIELDS == frozenset(
        {"description", "rows"}
    )
    assert architecture_policy.VISUAL_TABLE_MASTER_PROVIDER_PROFILE == "google_gemini"
    assert architecture_policy.VISUAL_TABLE_OPENAI_ROLE == (
        "optional_control_or_explicit_fallback"
    )
    assert architecture_policy.VISUAL_TABLE_PROVIDER_CONSENSUS_REQUIRED is False
    assert architecture_policy.VISUAL_TABLE_VLM_PHYSICAL_GEOMETRY_RESPONSIBILITY == 0
    assert architecture_policy.VISUAL_TABLE_MODEL_SYSTEM_METADATA_FIELDS == frozenset()
    assert architecture_policy.VISUAL_TABLE_MARKDOWN_RUNTIME_DEPENDENCY is False
    assert architecture_policy.LOCAL_OCR_PRODUCTION_ALLOWED is False
    assert architecture_policy.VISUAL_TABLE_SYSTEM_ENVELOPE_OWNER == (
        "deterministic_application_code"
    )
    assert architecture_policy.VISUAL_TABLE_FINANCIAL_INTERPRETATION_OWNER == "gate2"
    assert "production visual provider factory" in architecture_policy.FACTORY_REQUIRED
    assert "deterministic semantic validator/materializer" in (
        architecture_policy.FACTORY_REQUIRED
    )
    for marker in (
        "model-generated physical table geometry",
        "model-generated system metadata",
        "mandatory dual-provider consensus",
        "Markdown parser dependencies",
    ):
        assert marker in architecture_policy.FORBIDDEN


def test_legacy_grid_contract_is_preserved_but_not_model_facing_default() -> None:
    assert CANONICAL_TABLE_SCHEMA_VERSION == "broker_reports_canonical_table_v1"
    assert architecture_policy.LEGACY_VISUAL_TABLE_MODEL_CONTRACT == (
        CANONICAL_TABLE_SCHEMA_VERSION
    )
    assert architecture_policy.LEGACY_VISUAL_TABLE_CONTRACT_DISPOSITION == (
        "historical_evidence_and_immutable_artifacts_readable_not_default_model_facing"
    )
    assert architecture_policy.VISUAL_TABLE_MODEL_FACING_CONTRACT != (
        CANONICAL_TABLE_SCHEMA_VERSION
    )


def test_normative_documents_state_goal_zero_invariants() -> None:
    authority = ARCHITECTURE_DOCUMENT.read_text(encoding="utf-8")
    contract = SEMANTIC_CONTRACT_DOCUMENT.read_text(encoding="utf-8")
    authority_text = " ".join(authority.split())
    contract_text = " ".join(contract.split())

    authority_markers = {
        "broker_reports_semantic_table_transcription_v1",
        "Gemini is the master visual-table extractor",
        "OpenAI is an optional control or explicit fallback",
        "Provider agreement is not required for success",
        "Markdown is not a runtime dependency",
        "Physical PDF geometry is not a VLM responsibility",
        "Financial interpretation remains in global Gate 2",
        "broker_reports_canonical_table_v1",
    }
    contract_markers = {
        '"description"',
        '"rows"',
        "120 tokens",
        "Deterministic application code owns",
        "must not contain",
        "Legacy disposition",
    }
    assert sorted(
        marker for marker in authority_markers if marker not in authority_text
    ) == []
    assert sorted(marker for marker in contract_markers if marker not in contract_text) == []


def _property_names(schema: object) -> set[str]:
    names: set[str] = set()
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            names.update(str(name) for name in properties)
        for value in schema.values():
            names.update(_property_names(value))
    elif isinstance(schema, list):
        for value in schema:
            names.update(_property_names(value))
    return names
