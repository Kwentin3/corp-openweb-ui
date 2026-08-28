from __future__ import annotations

import copy

import pytest

from scripts.canonical_table_pipeline_audit import (
    FORBIDDEN,
    TablePipelineAuditError,
    static_canonical_audit,
    validate_visual_output,
    visual_model_view,
    visual_response_schema,
)


def _table(
    node_id: str,
    *,
    page: int,
    order: int,
    columns: int,
    header: bool,
    logical_table_id: str | None = None,
) -> tuple[dict, dict]:
    container_id = f"page-{page}"
    cells = [
        {
            "row": 1,
            "column": column,
            "displayed_value": f"v{column}",
        }
        for column in range(1, columns + 1)
    ]
    metadata = {}
    if logical_table_id:
        metadata = {
            "logical_table_id": logical_table_id,
            "continuation": {
                "status": "mechanically_linked",
                "semantic_table_truth_claimed": False,
            },
        }
    node = {
        "node_id": node_id,
        "node_type": "TABLE",
        "container_ref": container_id,
        "order": order,
        "content": {
            "header": [f"h{column}" for column in range(1, columns + 1)]
            if header
            else [],
            "cells": cells,
            "metadata": metadata,
        },
    }
    container = {
        "container_id": container_id,
        "metadata": {"page_number": page},
    }
    return node, container


def test_naive_headerless_rule_exposes_false_same_page_merges() -> None:
    first, page = _table("first", page=1, order=1, columns=7, header=True)
    second, _ = _table("second", page=1, order=2, columns=3, header=False)
    third, _ = _table("third", page=1, order=3, columns=9, header=False)
    canonical = {"containers": [page], "nodes": [first, second, third]}

    audit = static_canonical_audit(canonical)

    assert audit["tables_total"] == 3
    assert audit["canonical_header_absent"] == 2
    assert audit["naive_headerless_continuation_candidates"] == 2
    assert audit["naive_same_page_candidates"] == 2
    assert audit["naive_same_column_candidates"] == 0
    assert audit["exact_mechanical_continuation_groups"] == 0


def test_exact_canonical_continuation_is_preserved_without_semantic_claim() -> None:
    first, page1 = _table(
        "first",
        page=1,
        order=1,
        columns=7,
        header=True,
        logical_table_id="logical-1",
    )
    second, page2 = _table(
        "second",
        page=2,
        order=1,
        columns=7,
        header=False,
        logical_table_id="logical-1",
    )
    audit = static_canonical_audit(
        {"containers": [page1, page2], "nodes": [first, second]}
    )

    assert audit["exact_mechanical_continuation_groups"] == 1
    assert audit["exact_mechanical_continuation_nodes"] == 2
    assert audit["exact_groups"] == {"logical-1": ["first", "second"]}
    assert audit["tables"][1]["continuation"]["semantic_table_truth_claimed"] is False


def test_visual_contract_supports_headerless_and_multi_band_tables() -> None:
    schema = visual_response_schema()
    assert schema["properties"]["header_bands"]["type"] == "array"
    assert schema["properties"]["header_bands"].get("minItems") is None
    response = {
        "schema_version": "broker_reports_table_pipeline_visual_audit_v2",
        "document_purpose": "CUSTOMER_BROKER_REPORT",
        "tax_data_scope": "CUSTOMER_TRANSACTION_DATA",
        "table_purpose": "TRANSACTION_DATA",
        "header_bands": [["Trade", "Settlement"], ["Date", "Date"]],
        "columns": ["Trade Date", "Settlement Date"],
        "data_rows": 5,
        "financial_rows": 5,
        "explanation_markers": [],
        "summary": "Two-level transaction header.",
    }
    assert validate_visual_output(response) == response
    headerless = copy.deepcopy(response)
    headerless["header_bands"] = []
    assert validate_visual_output(headerless) == headerless


def test_visual_contract_rejects_unclassified_document_scope() -> None:
    with pytest.raises(TablePipelineAuditError) as exc:
        validate_visual_output(
            {
                "schema_version": "broker_reports_table_pipeline_visual_audit_v2",
                "document_purpose": "CUSTOMER_BROKER_REPORT",
            }
        )
    assert exc.value.code == "table_pipeline_visual_response_invalid"


def test_visual_request_is_generic_and_does_not_publish_facts() -> None:
    view = visual_model_view("case-1")
    instruction = view["instruction"]
    assert "attached pixels" in instruction
    assert "Do not invent" in instruction
    assert "broker or filename routing" in FORBIDDEN
    assert "T-Bank" not in instruction
    assert "Merrill" not in instruction


def test_schema_version_survives_the_shared_gemini_projection() -> None:
    from broker_reports_gate1.pdf_table_locator_provider import project_gemini_schema

    projected, _ = project_gemini_schema(visual_response_schema())
    assert projected["properties"]["schema_version"] == {
        "type": "string",
        "enum": ["broker_reports_table_pipeline_visual_audit_v2"],
    }
