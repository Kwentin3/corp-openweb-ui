from __future__ import annotations

import copy
import json

import pytest

from broker_reports_gate1.visual_role_context_research import (
    VISUAL_ROLE_CONTEXT_SCHEMA,
    VisualRoleContextError,
    VisualRoleContextResearchFactory,
    compose_visual_role_model_view,
    enrich_role_request,
    project_visual_role_response_schema,
    validate_visual_role_response,
)
from scripts.canonical_financial_role_mapping_research import compose_request


def _page() -> dict:
    return {
        "page_number": 1,
        "width": 100.0,
        "height": 100.0,
        "word_inventory": [
            {"parser_ordinal": 1, "text": "Trades", "bbox": [0, 0, 30, 8]},
            {"parser_ordinal": 2, "text": "Date", "bbox": [0, 10, 45, 20]},
            {"parser_ordinal": 3, "text": "Amount", "bbox": [55, 10, 95, 20]},
            {"parser_ordinal": 4, "text": "01.01", "bbox": [0, 30, 45, 40]},
            {"parser_ordinal": 5, "text": "100", "bbox": [55, 30, 95, 40]},
        ],
    }


def _candidate() -> dict:
    return {
        "columns_total": 2,
        "bbox": [0, 10, 100, 40],
        "cell_inventory": [
            {"column_ordinal": 1, "column_span": 1, "bbox": [0, 10, 50, 20]},
            {"column_ordinal": 2, "column_span": 1, "bbox": [50, 10, 100, 20]},
            {"column_ordinal": 1, "column_span": 1, "bbox": [0, 30, 50, 40]},
            {"column_ordinal": 2, "column_span": 1, "bbox": [50, 30, 100, 40]},
        ],
    }


def _structure() -> dict:
    return {
        "title_status": "PRESENT",
        "title_boxes_2d": [[0, 0, 80, 300]],
        "header_status": "PRESENT",
        "header_boxes_2d": [[100, 0, 200, 1000]],
        "body_status": "HAS_DATA",
    }


def _table() -> dict:
    return {
        "table_node_id": "table-node",
        "columns": [1, 2],
        "rows": [
            {
                "row": 1,
                "cells": [
                    {"column": 1, "literal": "Date"},
                    {"column": 2, "literal": "Amount"},
                ],
            },
            {
                "row": 2,
                "cells": [
                    {"column": 1, "literal": "01.01"},
                    {"column": 2, "literal": "100"},
                ],
            },
        ],
    }


def test_build_binds_exact_parser_words_to_existing_column_refs() -> None:
    result = VisualRoleContextResearchFactory().create().build(
        parser_page=_page(),
        table_candidate=_candidate(),
        bound_structure=_structure(),
        expected_column_refs=["c1", "c2"],
    )

    assert result["schema_version"] == VISUAL_ROLE_CONTEXT_SCHEMA
    assert result["title_literal"] == "Trades"
    assert result["header_labels"] == [
        {
            "column_ref": "c1",
            "literal": "Date",
            "word_refs": [result["header_labels"][0]["word_refs"][0]],
        },
        {
            "column_ref": "c2",
            "literal": "Amount",
            "word_refs": [result["header_labels"][1]["word_refs"][0]],
        },
    ]
    assert result["model_literals_used_as_source_values"] is False
    assert result["financial_roles_assigned"] is False
    assert result["canonical_mutated"] is False


def test_source_word_mutation_changes_context_and_does_not_mutate_inputs() -> None:
    adapter = VisualRoleContextResearchFactory().create()
    page = _page()
    candidate = _candidate()
    structure = _structure()
    originals = copy.deepcopy((page, candidate, structure))
    before = adapter.build(
        parser_page=page,
        table_candidate=candidate,
        bound_structure=structure,
        expected_column_refs=["c1", "c2"],
    )
    page["word_inventory"][1]["text"] = "Changed"
    after = adapter.build(
        parser_page=page,
        table_candidate=candidate,
        bound_structure=structure,
        expected_column_refs=["c1", "c2"],
    )

    assert before["header_labels"][0]["literal"] == "Date"
    assert after["header_labels"][0]["literal"] == "Changed"
    assert before["header_labels"][0]["word_refs"] != after["header_labels"][0]["word_refs"]
    assert candidate == originals[1]
    assert structure == originals[2]
    assert originals[0]["word_inventory"][1]["text"] == "Date"


def test_select_structure_uses_known_table_box_and_rejects_tie() -> None:
    adapter = VisualRoleContextResearchFactory().create()
    left = _structure()
    right = copy.deepcopy(left)
    right["title_boxes_2d"] = [[0, 600, 80, 900]]
    right["header_boxes_2d"] = [[100, 600, 200, 1000]]
    bound = {"tables": [left, right]}

    selected = adapter.select_structure(
        bound_structures=bound,
        table_box_2d=[90, 0, 900, 500],
    )
    assert selected == left

    with pytest.raises(VisualRoleContextError) as exc_info:
        adapter.select_structure(
            bound_structures=bound,
            table_box_2d=[90, 0, 900, 1000],
        )
    assert exc_info.value.code == "visual_role_context_header_ambiguous"


def test_rejects_headerless_and_column_scope_mismatch() -> None:
    adapter = VisualRoleContextResearchFactory().create()
    headerless = _structure()
    headerless["header_status"] = "ABSENT"
    headerless["header_boxes_2d"] = []

    with pytest.raises(VisualRoleContextError) as exc_info:
        adapter.build(
            parser_page=_page(),
            table_candidate=_candidate(),
            bound_structure=headerless,
            expected_column_refs=["c1", "c2"],
        )
    assert exc_info.value.code == "visual_role_context_header_unavailable"

    with pytest.raises(VisualRoleContextError) as exc_info:
        adapter.build(
            parser_page=_page(),
            table_candidate=_candidate(),
            bound_structure=_structure(),
            expected_column_refs=["c1"],
        )
    assert exc_info.value.code == "visual_role_context_column_scope_mismatch"


def test_enrichment_changes_only_model_evidence_not_response_contract() -> None:
    baseline = compose_request(
        table=_table(), table_ref="table_1", variant="header_plus_profiles"
    )
    original = copy.deepcopy(baseline)
    context = VisualRoleContextResearchFactory().create().build(
        parser_page=_page(),
        table_candidate=_candidate(),
        bound_structure=_structure(),
        expected_column_refs=["c1", "c2"],
    )

    enriched = enrich_role_request(
        baseline_request=baseline,
        visual_context=context,
    )
    package = json.loads(enriched["messages"][1]["content"])

    assert baseline == original
    assert enriched["response_format"] == baseline["response_format"]
    assert package["case"]["source_bound_visual_context"] == context
    assert package["case"]["table"] == json.loads(
        baseline["messages"][1]["content"]
    )["case"]["table"]


def test_visual_model_view_reuses_mapper_case_and_binds_image_columns() -> None:
    baseline = compose_request(
        table=_table(), table_ref="table_1", variant="header_plus_profiles"
    )
    original = copy.deepcopy(baseline)
    adapter = VisualRoleContextResearchFactory().create()
    geometry = adapter.build_column_geometry(
        table_candidate=_candidate(), expected_column_refs=["c1", "c2"]
    )

    result = compose_visual_role_model_view(
        baseline_request=baseline,
        column_geometry=geometry,
    )

    assert baseline == original
    assert result["case"] == json.loads(baseline["messages"][1]["content"])["case"]
    assert result["column_geometry"]["columns"] == [
        {"column_ref": "c1", "x_min_1000": 0, "x_max_1000": 500},
        {"column_ref": "c2", "x_min_1000": 500, "x_max_1000": 1000},
    ]
    assert "never transcribe" in result["instruction"]


def test_visual_role_schema_removes_only_row_value_normalization() -> None:
    baseline = compose_request(
        table=_table(), table_ref="table_1", variant="header_plus_profiles"
    )["response_format"]["json_schema"]["schema"]
    projected = project_visual_role_response_schema(
        baseline_response_schema=baseline
    )
    response = {
        "schema_version": "broker_reports_research_table_role_mapping_v1",
        "table_ref": "table_1",
        "table_kind": "STRUCTURALLY_INCOMPATIBLE",
        "header_row": 1,
        "columns": [
            {"column_ref": "c1", "role": "unmapped"},
            {"column_ref": "c2", "role": "unmapped"},
        ],
        "amount_currency_bindings": [],
    }

    assert "categorical_normalizations" in baseline["required"]
    assert "categorical_normalizations" not in projected["required"]
    assert validate_visual_role_response(
        raw_response=response, response_schema=projected
    ) == response

    response["columns"].reverse()
    with pytest.raises(VisualRoleContextError) as exc_info:
        validate_visual_role_response(
            raw_response=response, response_schema=projected
        )
    assert exc_info.value.code == "visual_role_context_columns_invalid"
