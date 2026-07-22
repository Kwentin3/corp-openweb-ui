from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from broker_reports_gate1.semantic_visual_table_validator import (
    DESCRIPTION_TOKEN_BUDGET,
    SEMANTIC_VISUAL_TABLE_VALIDATOR_VERSION,
    SemanticVisualTableValidatorConfig,
    SemanticVisualTableValidatorFactory,
    count_description_tokens,
    unchanged_semantic_response,
    validate_semantic_visual_table_response,
)


def _valid() -> dict[str, object]:
    return {
        "description": "Visible grouped source table.",
        "rows": [["Name", "Amount"], ["Cash", "(1 234,50) ₽"], [None, "5%"]],
    }


def test_valid_json_and_semantic_shape_pass_without_truth_claims() -> None:
    value = _valid()
    raw = " \n" + json.dumps(value, ensure_ascii=False) + "\t"

    result = validate_semantic_visual_table_response(
        value,
        raw_json_text=raw,
        require_raw_json=True,
    )

    assert result["validator_version"] == SEMANTIC_VISUAL_TABLE_VALIDATOR_VERSION
    assert result["semantic_response_contract_passed"] is True
    assert result["error_codes"] == []
    assert result["row_count"] == 3
    assert result["maximum_column_count"] == 2
    assert result["cell_count"] == 6
    assert result["hidden_repair_performed"] is False
    assert result["geometric_validation_performed"] is False
    assert result["human_review_required"] is False
    assert result["source_content_correctness_claimed"] is False
    assert result["financial_correctness_claimed"] is False


def test_description_budget_is_deterministic_and_enforced() -> None:
    within = _valid()
    within["description"] = " ".join(["word"] * DESCRIPTION_TOKEN_BUDGET)
    over = copy.deepcopy(within)
    over["description"] += " extra"

    assert count_description_tokens(within["description"]) == 120
    assert validate_semantic_visual_table_response(within)[
        "semantic_response_contract_passed"
    ]
    result = validate_semantic_visual_table_response(over)
    assert result["description_token_count"] == 121
    assert result["error_codes"] == [
        "semantic_table_transcription_description_budget_exceeded"
    ]


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda value: value.update({"table_id": "model_metadata"}),
            "semantic_table_transcription_fields_invalid",
        ),
        (
            lambda value: value.update({"rows": []}),
            "semantic_table_transcription_rows_invalid",
        ),
        (
            lambda value: value.update({"rows": ["not-a-row"]}),
            "semantic_table_transcription_row_0_invalid",
        ),
        (
            lambda value: value.update({"rows": [[{"nested": "object"}]]}),
            "semantic_table_transcription_cell_0_0_nested_value_forbidden",
        ),
        (
            lambda value: value.update({"rows": [[["nested", "array"]]]}),
            "semantic_table_transcription_cell_0_0_nested_value_forbidden",
        ),
        (
            lambda value: value.update({"rows": [[123]]}),
            "semantic_table_transcription_cell_0_0_type_invalid",
        ),
        (
            lambda value: value.update({"rows": [[True]]}),
            "semantic_table_transcription_cell_0_0_type_invalid",
        ),
    ],
)
def test_exact_shape_and_cell_types_are_strict(mutator, expected: str) -> None:
    value = _valid()
    mutator(value)

    result = validate_semantic_visual_table_response(value)

    assert result["semantic_response_contract_passed"] is False
    assert expected in result["error_codes"]


def test_row_column_and_cell_text_bounds_are_enforced() -> None:
    validator = SemanticVisualTableValidatorFactory(
        SemanticVisualTableValidatorConfig(
            maximum_rows=2,
            maximum_columns=2,
            maximum_cell_characters=4,
        )
    ).create()
    value = {
        "description": "Bounded table.",
        "rows": [["12345", "b", "c"], ["d"], ["e"]],
    }

    result = validator.validate(value)

    assert "semantic_table_transcription_row_budget_exceeded" in result[
        "error_codes"
    ]

    value["rows"] = value["rows"][:2]
    result = validator.validate(value)
    assert "semantic_table_transcription_row_0_column_budget_exceeded" in result[
        "error_codes"
    ]
    assert "semantic_table_transcription_cell_0_0_text_budget_exceeded" in result[
        "error_codes"
    ]


@pytest.mark.parametrize(
    "raw",
    [
        '{"description":"x","rows":[["y"]]} explanation',
        'explanation {"description":"x","rows":[["y"]]}',
        '```json\n{"description":"x","rows":[["y"]]}\n```',
        '{"description":"x","rows":[["y"]] /* comment */}',
    ],
)
def test_explanation_or_markup_outside_json_is_rejected(raw: str) -> None:
    result = validate_semantic_visual_table_response(
        {"description": "x", "rows": [["y"]]},
        raw_json_text=raw,
        require_raw_json=True,
    )

    assert "semantic_table_transcription_raw_json_invalid" in result["error_codes"]


def test_raw_json_must_bind_exactly_to_the_parsed_object() -> None:
    value = _valid()
    different = copy.deepcopy(value)
    different["rows"] = [["changed"]]

    result = validate_semantic_visual_table_response(
        value,
        raw_json_text=json.dumps(different),
        require_raw_json=True,
    )

    assert result["error_codes"] == [
        "semantic_table_transcription_raw_json_binding_invalid"
    ]


def test_validator_performs_no_hidden_repair_or_geometric_validation() -> None:
    value = _valid()
    copied = unchanged_semantic_response(value)

    assert copied == value
    assert copied is not value
    assert copied["rows"] is not value["rows"]
    source = (
        Path(__file__).resolve().parents[1]
        / "broker_reports_gate1"
        / "semantic_visual_table_validator.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "row_span",
        "column_span",
        "bounding_box",
        "bbox",
        "human_review_receipt",
        "financial_role",
    ):
        assert forbidden not in source


def test_validator_factory_rejects_relaxed_global_budgets() -> None:
    with pytest.raises(
        ValueError,
        match="semantic_visual_table_validator_budget_invalid",
    ):
        SemanticVisualTableValidatorFactory(
            SemanticVisualTableValidatorConfig(description_token_budget=121)
        ).create()
