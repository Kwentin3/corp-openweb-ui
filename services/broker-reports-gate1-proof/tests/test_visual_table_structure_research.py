from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.visual_table_structure_research import (
    FORBIDDEN,
    VISUAL_TABLE_STRUCTURE_SCHEMA_VERSION,
    VisualTableStructureError,
    VisualTableStructureProjectionFactory,
    model_view,
    response_schema,
)


def _page() -> dict:
    return {
        "page_number": 1,
        "width": 1000.0,
        "height": 1000.0,
        "word_inventory": [
            {"parser_ordinal": 1, "text": "Section A", "bbox": [50, 50, 180, 80]},
            {"parser_ordinal": 2, "text": "Date", "bbox": [50, 110, 100, 140]},
            {"parser_ordinal": 3, "text": "Amount", "bbox": [250, 110, 330, 140]},
            {"parser_ordinal": 4, "text": "01.01", "bbox": [50, 170, 100, 200]},
            {"parser_ordinal": 5, "text": "100", "bbox": [250, 170, 280, 200]},
            {"parser_ordinal": 6, "text": "Section B", "bbox": [550, 50, 680, 80]},
            {"parser_ordinal": 7, "text": "Code", "bbox": [550, 110, 600, 140]},
            {"parser_ordinal": 8, "text": "Meaning", "bbox": [750, 110, 830, 140]},
            {"parser_ordinal": 9, "text": "A", "bbox": [550, 170, 570, 200]},
            {"parser_ordinal": 10, "text": "Alpha", "bbox": [750, 170, 800, 200]},
        ],
    }


def _value() -> dict:
    return {
        "schema_version": VISUAL_TABLE_STRUCTURE_SCHEMA_VERSION,
        "tables": [
            {
                "table_order": 1,
                "table_box_2d": [100, 40, 240, 400],
                "title_status": "PRESENT",
                "title_boxes_2d": [[40, 40, 90, 400]],
                "header_status": "PRESENT",
                "header_boxes_2d": [[100, 40, 150, 400]],
                "body_status": "HAS_DATA",
            },
            {
                "table_order": 2,
                "table_box_2d": [100, 540, 240, 900],
                "title_status": "PRESENT",
                "title_boxes_2d": [[40, 540, 90, 900]],
                "header_status": "PRESENT",
                "header_boxes_2d": [[100, 540, 150, 900]],
                "body_status": "HAS_DATA",
            },
        ],
    }


def test_binds_visual_geometry_to_exact_parser_owned_words() -> None:
    result = VisualTableStructureProjectionFactory().create().bind(
        provider_value=_value(), parser_page=_page()
    )

    assert [item["title_text"] for item in result["tables"]] == [
        "Section A",
        "Section B",
    ]
    assert [item["header_text"] for item in result["tables"]] == [
        "Date Amount",
        "Code Meaning",
    ]
    assert result["model_literals_used_as_source_values"] is False
    assert all(item["title_word_refs"] for item in result["tables"])
    assert all(item["header_word_refs"] for item in result["tables"])


def test_source_word_mutation_changes_bound_identity() -> None:
    projector = VisualTableStructureProjectionFactory().create()
    before = projector.bind(provider_value=_value(), parser_page=_page())
    mutated_page = _page()
    mutated_page["word_inventory"][1]["text"] = "Changed"
    after = projector.bind(provider_value=_value(), parser_page=mutated_page)

    assert before["tables"][0]["header_text"] == "Date Amount"
    assert after["tables"][0]["header_text"] == "Changed Amount"
    assert (
        before["tables"][0]["header_word_refs"][0]
        != after["tables"][0]["header_word_refs"][0]
    )


def test_supports_a_genuine_headerless_table_without_inventing_header_words() -> None:
    value = _value()
    value["tables"] = [value["tables"][0]]
    value["tables"][0]["header_status"] = "ABSENT"
    value["tables"][0]["header_boxes_2d"] = []

    result = VisualTableStructureProjectionFactory().create().bind(
        provider_value=value, parser_page=_page()
    )

    assert result["tables"][0]["header_text"] == ""
    assert result["tables"][0]["header_word_refs"] == []


def test_rejects_model_literals_and_unknown_contract_fields() -> None:
    value = _value()
    value["tables"][0]["title_literal"] = "model-authored title"

    with pytest.raises(VisualTableStructureError) as exc_info:
        VisualTableStructureProjectionFactory().create().bind(
            provider_value=value, parser_page=_page()
        )

    assert exc_info.value.code == "visual_table_structure_response_invalid"


def test_rejects_header_box_outside_its_table() -> None:
    value = _value()
    value["tables"][0]["header_boxes_2d"] = [[250, 40, 300, 400]]

    with pytest.raises(VisualTableStructureError) as exc_info:
        VisualTableStructureProjectionFactory().create().bind(
            provider_value=value, parser_page=_page()
        )

    assert exc_info.value.code == "visual_table_structure_header_outside_table"


def test_rejects_presence_contract_mismatch() -> None:
    value = _value()
    value["tables"][0]["title_status"] = "ABSENT"

    with pytest.raises(VisualTableStructureError) as exc_info:
        VisualTableStructureProjectionFactory().create().bind(
            provider_value=value, parser_page=_page()
        )

    assert exc_info.value.code == "visual_table_structure_title_presence_mismatch"


def test_prompt_is_generic_and_output_contract_is_geometry_only() -> None:
    view = model_view(case_ref="case_1")
    prompt = view["instruction"].lower()
    serialized_schema = repr(response_schema()).lower()

    assert "broker" not in prompt
    assert "t-bank" not in prompt
    assert "merrill" not in prompt
    assert "title_text" not in serialized_schema
    assert "header_text" not in serialized_schema
    assert "table_box_2d" in serialized_schema
    assert "header_boxes_2d" in serialized_schema
    assert FORBIDDEN.startswith("research-only")


def test_projection_does_not_mutate_provider_or_parser_inputs() -> None:
    value = _value()
    page = _page()
    original_value = copy.deepcopy(value)
    original_page = copy.deepcopy(page)

    VisualTableStructureProjectionFactory().create().bind(
        provider_value=value, parser_page=page
    )

    assert value == original_value
    assert page == original_page


def test_gemini_schema_projection_keeps_closed_enum_contracts() -> None:
    from broker_reports_gate1.pdf_table_locator_provider import (
        project_gemini_schema,
    )

    projected, _ = project_gemini_schema(response_schema())
    table_properties = projected["properties"]["tables"]["items"]["properties"]

    assert projected["properties"]["schema_version"]["enum"] == [
        VISUAL_TABLE_STRUCTURE_SCHEMA_VERSION
    ]
    assert table_properties["title_status"]["enum"] == ["PRESENT", "ABSENT"]
    assert table_properties["body_status"]["enum"] == [
        "HAS_DATA",
        "EMPTY_TEMPLATE",
        "UNCERTAIN",
    ]
