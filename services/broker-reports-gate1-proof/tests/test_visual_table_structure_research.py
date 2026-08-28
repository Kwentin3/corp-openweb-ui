from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.visual_table_structure_research import (
    FORBIDDEN,
    VISUAL_LOGICAL_COLUMN_PROPOSAL_SCHEMA_VERSION,
    VISUAL_TABLE_STRUCTURE_SCHEMA_VERSION,
    VisualTableStructureError,
    VisualTableStructureProjectionFactory,
    logical_column_proposal_model_view,
    logical_column_proposal_response_schema,
    model_view,
    response_schema,
)


SOURCE_SHA256 = "a" * 64


def _page() -> dict:
    return {
        "page_number": 1,
        "source_sha256": SOURCE_SHA256,
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
                "title_status": "PRESENT",
                "title_boxes_2d": [[40, 40, 90, 400]],
                "header_status": "PRESENT",
                "header_boxes_2d": [[100, 40, 150, 400]],
                "body_status": "HAS_DATA",
            },
            {
                "title_status": "PRESENT",
                "title_boxes_2d": [[40, 540, 90, 900]],
                "header_status": "PRESENT",
                "header_boxes_2d": [[100, 540, 150, 900]],
                "body_status": "HAS_DATA",
            },
        ],
    }


def _logical_column_value() -> dict:
    return {
        "schema_version": VISUAL_LOGICAL_COLUMN_PROPOSAL_SCHEMA_VERSION,
        "source_binding": {
            "source_sha256": SOURCE_SHA256,
            "page_number": 1,
        },
        "table_order": 1,
        "leaf_label_boxes_2d": [
            [100, 40, 150, 150],
            [100, 200, 150, 400],
        ],
    }


def _bound_structure(*, page: dict | None = None) -> dict:
    bound = (
        VisualTableStructureProjectionFactory()
        .create()
        .bind(provider_value=_value(), parser_page=page or _page())
    )
    return bound["tables"][0]


def test_binds_visual_geometry_to_exact_parser_owned_words() -> None:
    result = (
        VisualTableStructureProjectionFactory()
        .create()
        .bind(provider_value=_value(), parser_page=_page())
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


def test_binds_leaf_label_boxes_to_unique_exact_header_words() -> None:
    result = (
        VisualTableStructureProjectionFactory()
        .create()
        .bind_logical_column_proposal(
            provider_value=_logical_column_value(),
            parser_page=_page(),
            bound_structure=_bound_structure(),
        )
    )

    assert [item["header_text"] for item in result["leaf_columns"]] == [
        "Date",
        "Amount",
    ]
    assert [item["logical_column_order"] for item in result["leaf_columns"]] == [1, 2]
    assert result["source_binding"] == {
        "source_sha256": SOURCE_SHA256,
        "page_number": 1,
    }
    assert result["proposal_for"] == "logical_row_owner"
    assert result["model_literals_used_as_source_values"] is False
    assert result["canonical_mutated"] is False


def test_leaf_column_source_word_mutation_changes_bound_identity() -> None:
    projector = VisualTableStructureProjectionFactory().create()
    page_before = _page()
    before = projector.bind_logical_column_proposal(
        provider_value=_logical_column_value(),
        parser_page=page_before,
        bound_structure=_bound_structure(page=page_before),
    )
    page_after = _page()
    page_after["word_inventory"][1]["text"] = "Changed"
    after = projector.bind_logical_column_proposal(
        provider_value=_logical_column_value(),
        parser_page=page_after,
        bound_structure=_bound_structure(page=page_after),
    )

    assert before["leaf_columns"][0]["header_text"] == "Date"
    assert after["leaf_columns"][0]["header_text"] == "Changed"
    assert (
        before["leaf_columns"][0]["header_word_refs"][0]
        != after["leaf_columns"][0]["header_word_refs"][0]
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("source_sha256", "b" * 64), ("page_number", 2)],
)
def test_rejects_leaf_column_source_or_page_misbinding(
    field: str, value: object
) -> None:
    proposal = _logical_column_value()
    proposal["source_binding"][field] = value

    with pytest.raises(VisualTableStructureError) as exc_info:
        (
            VisualTableStructureProjectionFactory()
            .create()
            .bind_logical_column_proposal(
                provider_value=proposal,
                parser_page=_page(),
                bound_structure=_bound_structure(),
            )
        )

    assert exc_info.value.code == "visual_logical_column_source_binding_mismatch"


def test_rejects_leaf_label_boxes_out_of_left_to_right_order() -> None:
    proposal = _logical_column_value()
    proposal["leaf_label_boxes_2d"].reverse()

    with pytest.raises(VisualTableStructureError) as exc_info:
        (
            VisualTableStructureProjectionFactory()
            .create()
            .bind_logical_column_proposal(
                provider_value=proposal,
                parser_page=_page(),
                bound_structure=_bound_structure(),
            )
        )

    assert exc_info.value.code == "visual_logical_column_groups_not_left_to_right"


def test_rejects_overlapping_leaf_label_boxes() -> None:
    proposal = _logical_column_value()
    proposal["leaf_label_boxes_2d"][0] = [100, 40, 150, 250]

    with pytest.raises(VisualTableStructureError) as exc_info:
        (
            VisualTableStructureProjectionFactory()
            .create()
            .bind_logical_column_proposal(
                provider_value=proposal,
                parser_page=_page(),
                bound_structure=_bound_structure(),
            )
        )

    assert exc_info.value.code == "visual_logical_column_groups_overlap"


def test_preserves_shared_header_word_outside_leaf_labels() -> None:
    page = _page()
    page["word_inventory"].append(
        {"parser_ordinal": 11, "text": "Shared", "bbox": [160, 110, 190, 140]}
    )
    proposal = _logical_column_value()
    result = (
        VisualTableStructureProjectionFactory()
        .create()
        .bind_logical_column_proposal(
            provider_value=proposal,
            parser_page=page,
            bound_structure=_bound_structure(page=page),
        )
    )

    assert [item["header_text"] for item in result["leaf_columns"]] == [
        "Date",
        "Amount",
    ]
    assert len(result["shared_or_non_leaf_header_word_refs"]) == 1


def test_rejects_one_header_word_owned_by_two_touching_leaf_boxes() -> None:
    page = _page()
    page["word_inventory"][2]["bbox"] = [190, 110, 210, 140]
    proposal = _logical_column_value()
    proposal["leaf_label_boxes_2d"] = [
        [100, 40, 150, 200],
        [100, 200, 150, 400],
    ]

    with pytest.raises(VisualTableStructureError) as exc_info:
        (
            VisualTableStructureProjectionFactory()
            .create()
            .bind_logical_column_proposal(
                provider_value=proposal,
                parser_page=page,
                bound_structure=_bound_structure(page=page),
            )
        )

    assert exc_info.value.code == "visual_logical_column_header_word_ownership_invalid"


def test_rejects_leaf_label_box_without_source_word() -> None:
    proposal = _logical_column_value()
    proposal["leaf_label_boxes_2d"] = [
        [100, 40, 150, 150],
        [100, 150, 150, 200],
        [100, 200, 150, 400],
    ]

    with pytest.raises(VisualTableStructureError) as exc_info:
        (
            VisualTableStructureProjectionFactory()
            .create()
            .bind_logical_column_proposal(
                provider_value=proposal,
                parser_page=_page(),
                bound_structure=_bound_structure(),
            )
        )

    assert exc_info.value.code == "visual_logical_column_source_binding_empty"


def test_rejects_stale_bound_header_receipt() -> None:
    structure = _bound_structure()
    structure["header_word_refs"][0] = "forged"

    with pytest.raises(VisualTableStructureError) as exc_info:
        (
            VisualTableStructureProjectionFactory()
            .create()
            .bind_logical_column_proposal(
                provider_value=_logical_column_value(),
                parser_page=_page(),
                bound_structure=structure,
            )
        )

    assert exc_info.value.code == "visual_logical_column_bound_structures_stale"


def test_supports_a_genuine_headerless_table_without_inventing_header_words() -> None:
    value = _value()
    value["tables"] = [value["tables"][0]]
    value["tables"][0]["header_status"] = "ABSENT"
    value["tables"][0]["header_boxes_2d"] = []

    result = (
        VisualTableStructureProjectionFactory()
        .create()
        .bind(provider_value=value, parser_page=_page())
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


def test_rejects_title_geometry_below_header_geometry() -> None:
    value = _value()
    value["tables"][0]["title_boxes_2d"] = [[160, 40, 210, 400]]

    with pytest.raises(VisualTableStructureError) as exc_info:
        VisualTableStructureProjectionFactory().create().bind(
            provider_value=value, parser_page=_page()
        )

    assert exc_info.value.code == "visual_table_structure_title_below_header"


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
    assert "table_box_2d" not in serialized_schema
    assert "header_boxes_2d" in serialized_schema
    assert FORBIDDEN.startswith("research-only")


def test_logical_column_contract_is_source_bound_and_geometry_only() -> None:
    view = logical_column_proposal_model_view(
        case_ref="case_1",
        source_sha256=SOURCE_SHA256,
        page_number=1,
        table_order=1,
    )
    prompt = view["instruction"].lower()
    serialized_schema = repr(logical_column_proposal_response_schema()).lower()

    assert view["source_binding"]["source_sha256"] == SOURCE_SHA256
    assert view["table_order"] == 1
    assert "leaf_label_boxes_2d" in serialized_schema
    assert "source_sha256" in serialized_schema
    assert "header_text" not in serialized_schema
    assert "financial_role" not in serialized_schema
    assert "broker" not in prompt
    assert "t-bank" not in prompt
    assert "merrill" not in prompt


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
