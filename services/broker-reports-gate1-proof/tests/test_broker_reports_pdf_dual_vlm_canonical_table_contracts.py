from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

import pdf_dual_vlm_canonical_table_contracts as CONTRACTS  # noqa: E402
from broker_reports_gate1.pdf_hybrid_provider import (  # noqa: E402
    project_gemini_schema,
)


def _table(table_id: str = "table_1") -> dict[str, object]:
    return {
        "schema_version": CONTRACTS.CANONICAL_TABLE_SCHEMA_VERSION,
        "table_id": table_id,
        "row_count": 2,
        "column_count": 2,
        "cells": [
            {
                "row_index": 0,
                "column_index": 0,
                "row_span": 1,
                "column_span": 2,
                "content_state": "present",
                "source_text": "Summary",
            },
            {
                "row_index": 1,
                "column_index": 0,
                "row_span": 1,
                "column_span": 1,
                "content_state": "empty",
                "source_text": "",
            },
            {
                "row_index": 1,
                "column_index": 1,
                "row_span": 1,
                "column_span": 1,
                "content_state": "present",
                "source_text": "1,000",
            },
        ],
    }


def test_contract_is_neutral_closed_and_has_no_visual_coordinates() -> None:
    schema = CONTRACTS.canonical_table_schema()
    schema_text = CONTRACTS.canonical_json_bytes(schema).decode("utf-8")

    assert set(schema["properties"]) == {
        "schema_version",
        "table_id",
        "row_count",
        "column_count",
        "cells",
    }
    for forbidden in CONTRACTS.FORBIDDEN_CONTRACT_FIELDS:
        assert f'"{forbidden}"' not in schema_text
    assert "content_state" in schema_text
    assert "row_span" in schema_text
    assert "column_span" in schema_text


def test_merged_cell_covers_grid_once_and_empty_is_explicit() -> None:
    table = _table()

    assert CONTRACTS.validate_table_output(table, table_id="table_1") == []

    overlapping = copy.deepcopy(table)
    overlapping["cells"].append(
        {
            "row_index": 0,
            "column_index": 1,
            "row_span": 1,
            "column_span": 1,
            "content_state": "present",
            "source_text": "duplicate",
        }
    )
    errors = CONTRACTS.validate_table_output(overlapping, table_id="table_1")
    assert "canonical_table_grid_has_overlapping_cells" in errors


def test_uncovered_grid_slot_is_a_contract_failure_not_silent_repair() -> None:
    table = _table()
    table["cells"].pop()

    errors = CONTRACTS.validate_table_output(table, table_id="table_1")

    assert "canonical_table_grid_has_uncovered_slots" in errors
    with pytest.raises(
        CONTRACTS.CanonicalTableContractError,
        match="canonical_table_grid_has_uncovered_slots",
    ):
        CONTRACTS.canonicalize_table(table)


@pytest.mark.parametrize("state", ["empty", "unreadable"])
def test_non_present_state_cannot_carry_invented_text(state: str) -> None:
    table = _table()
    table["cells"][1]["content_state"] = state
    table["cells"][1]["source_text"] = "guessed"

    errors = CONTRACTS.validate_table_output(table)

    assert "canonical_table_cell_1_non_present_text_must_be_empty" in errors


def test_canonical_whitespace_is_safe_and_raw_difference_remains_visible() -> None:
    left = _table()
    right = copy.deepcopy(left)
    left["cells"][0]["source_text"] = "Net  income"
    right["cells"][0]["source_text"] = "Net income"

    comparison = CONTRACTS.compare_tables(left, right)

    assert comparison["STRUCTURAL_CONSENSUS"] is True
    assert comparison["CONTENT_CONSENSUS"] is True
    assert comparison["FULL_TABLE_CONSENSUS"] is True
    assert comparison["raw_format_only_difference"] is True
    assert comparison["smallest_difference"]["class"] == "raw_format_only_difference"


def test_diff_reports_smallest_structural_and_content_differences() -> None:
    left = _table()
    right = copy.deepcopy(left)
    right["cells"][2]["source_text"] = "1,250"

    content = CONTRACTS.compare_tables(left, right)

    assert content["STRUCTURAL_CONSENSUS"] is True
    assert content["CONTENT_CONSENSUS"] is False
    assert content["smallest_difference"] == {
        "class": "differing_source_text",
        "cell": [1, 1],
        "left": "1,000",
        "right": "1,250",
        "matching_text_elsewhere": {
            "left_text_in_right_positions": [],
            "right_text_in_left_positions": [],
        },
    }

    structural = copy.deepcopy(right)
    structural["row_count"] = 3
    structural["cells"].extend(
        [
            {
                "row_index": 2,
                "column_index": column,
                "row_span": 1,
                "column_span": 1,
                "content_state": "empty",
                "source_text": "",
            }
            for column in range(2)
        ]
    )
    structure_comparison = CONTRACTS.compare_tables(left, structural)
    assert structure_comparison["STRUCTURAL_CONSENSUS"] is False
    assert structure_comparison["smallest_difference"]["class"] == "different_row_count"


def test_table_accuracy_detects_same_wrong_consensus() -> None:
    reference = _table()
    wrong = copy.deepcopy(reference)
    wrong["cells"][2]["source_text"] = "9,999"

    provider_accuracy = CONTRACTS.table_accuracy(wrong, reference)
    pair = CONTRACTS.compare_tables(wrong, copy.deepcopy(wrong))

    assert provider_accuracy["exact_full_table"] is False
    assert pair["FULL_TABLE_CONSENSUS"] is True


def test_provider_schema_projection_preserves_logical_contract() -> None:
    canonical = CONTRACTS.canonical_table_schema()
    adapted, transform_count = project_gemini_schema(copy.deepcopy(canonical))

    record = CONTRACTS.schema_equivalence_record(canonical, adapted)

    assert transform_count > 0
    assert record["required_field_cardinality_equivalent"] is True
    assert record["enum_meaning_equivalent"] is True
    assert record["nullability_equivalent"] is True
    assert record["logical_contract_equivalent"] is True
    assert record["comparison_unit"] == "model + provider API + schema adapter"
    assert record["causality_established"] is False


def test_model_view_has_same_visual_task_and_no_interpretation() -> None:
    view = CONTRACTS.normalizer_model_view(
        crop_sha256="f" * 64,
        table_id="table_1",
        image_width=1000,
        image_height=700,
    )

    normalized_task = CONTRACTS.canonicalize_text(view["task"])

    assert view["output_contract"]["coordinates"] is False
    assert view["output_contract"]["cell_roles"] is False
    assert view["output_contract"]["content_types"] is False
    assert view["output_contract"]["financial_semantics"] is False
    assert view["prompt_contract_version"] == "dual_vlm_canonical_table_normalizer_v4"
    assert "most faithful stable logical grid" in normalized_task
    assert "A logical column may be sparse" in normalized_task
    assert "do not merge cells across a sparse column" in normalized_task
    assert (
        "set row_count and column_count to its complete dimensions" in normalized_task
    )
    assert "Every cell anchor and span must stay inside" in normalized_task
    assert "Transcribe every visible text token" in normalized_task
    assert (
        "Do not summarize, simplify, deduplicate, relabel, or omit" in normalized_task
    )
    assert "Visible numbering rows" in normalized_task
    assert "footnote markers" in normalized_task
    assert "standalone symbols are table content" in normalized_task
    assert "smallest complete logical grid" not in normalized_task
    assert "Do not calculate" in normalized_task
