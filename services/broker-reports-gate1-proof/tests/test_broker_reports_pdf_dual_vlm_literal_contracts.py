from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

import pdf_dual_vlm_literal_contracts as CONTRACTS  # noqa: E402
from broker_reports_gate1.pdf_hybrid_provider import (  # noqa: E402
    project_gemini_schema,
)


def _entry(
    entry_id: str,
    *,
    row: str = "Total assets",
    header: list[str] | None = None,
    value: str = "10,500",
    row_bbox: list[float] | None = None,
    value_bbox: list[float] | None = None,
) -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "row_label_text": row,
        "column_header_path": header if header is not None else ["2025"],
        "visible_value_text": value,
        "row_label_bbox": row_bbox or [0.05, 0.2, 0.4, 0.25],
        "header_bboxes": [[0.7, 0.05, 0.9, 0.1]],
        "value_bbox": value_bbox or [0.7, 0.2, 0.9, 0.25],
        "cell_state": "value",
        "uncertainty_codes": [],
    }


def test_literal_schema_has_no_semantic_or_inferred_qualifier_fields() -> None:
    schema_text = CONTRACTS.canonical_json_bytes(
        CONTRACTS.literal_observation_schema()
    ).decode("utf-8")

    for forbidden in CONTRACTS.FORBIDDEN_EXTRACTION_FIELDS:
        assert f'"{forbidden}"' not in schema_text
    assert "row_label_text" in schema_text
    assert "column_header_path" in schema_text
    assert "visible_value_text" in schema_text


def test_bbox_order_is_explicit_in_prompts_schema_and_model_views() -> None:
    required_order = ["x0_left", "y0_top", "x1_right", "y1_bottom"]

    assert "[x0, y0, x1, y1] = [left, top, right, bottom]" in CONTRACTS.DETECTION_PROMPT
    assert "[x0, y0, x1, y1] = [left, top, right, bottom]" in CONTRACTS.EXTRACTION_PROMPT
    assert "Never use [top, left, bottom, right]" in CONTRACTS.DETECTION_PROMPT
    schema_text = CONTRACTS.canonical_json_bytes(CONTRACTS.detection_schema()).decode("utf-8")
    assert "Never [top, left, bottom, right]" in schema_text
    assert CONTRACTS.detection_model_view(
        page_number=1, page_sha256="f" * 64
    )["output_contract"]["bbox_array_order"] == required_order
    assert CONTRACTS.literal_model_view(
        crop_sha256="f" * 64,
        table_identifier="fixture",
        image_width=100,
        image_height=200,
    )["output_contract"]["bbox_array_order"] == required_order


def test_provider_schema_projection_preserves_required_enum_and_nullability() -> None:
    canonical = CONTRACTS.literal_observation_schema()
    adapted, transform_count = project_gemini_schema(copy.deepcopy(canonical))
    record = CONTRACTS.schema_equivalence_record(canonical, adapted)

    assert transform_count > 0
    assert record["required_field_cardinality_equivalent"] is True
    assert record["enum_meaning_equivalent"] is True
    assert record["nullability_equivalent"] is True
    assert record["logical_contract_equivalent"] is True
    assert record["comparison_unit"] == "model + provider API + schema adapter"
    assert record["isolated_model_comparison_claimed"] is False
    assert record["removed_keywords"]


def test_invalid_detection_bbox_is_terminal_and_is_not_repaired() -> None:
    output = {
        "schema_version": CONTRACTS.DETECTION_SCHEMA_VERSION,
        "page_number": 3,
        "candidates": [
            {
                "candidate_id": "table_0",
                "decision": "present",
                "bbox": [0.2, 0.2, 1.1, 0.8],
                "uncertainty_codes": [],
            }
        ],
    }

    assert CONTRACTS.validate_detection_output(output, page_number=3) == [
        "literal_detection_candidate_0_bbox_invalid"
    ]
    with pytest.raises(
        CONTRACTS.LiteralContractError,
        match="literal_padding_detected_bbox_invalid",
    ):
        CONTRACTS.apply_padding_bbox(output["candidates"][0]["bbox"], 0.01)


def test_padding_is_global_predeclared_and_clamped_without_mutating_detection() -> None:
    detected = [0.005, 0.01, 0.98, 0.99]
    original = detected.copy()

    transformed = CONTRACTS.padding_transformation(detected, 0.02)

    assert detected == original
    assert transformed["detected_bbox"] == original
    assert transformed["padded_crop_bbox"] == [0.0, 0.0, 1.0, 1.0]
    assert transformed["clamped_to_page"] == [True, True, False, True]
    with pytest.raises(
        CONTRACTS.LiteralContractError,
        match="literal_padding_variant_not_predeclared",
    ):
        CONTRACTS.apply_padding_bbox(detected, 0.015)


def test_crop_relative_bbox_projection_preserves_xyxy_order() -> None:
    projected = CONTRACTS.project_crop_relative_bbox_to_page_normalized(
        [0.1, 0.2, 0.8, 0.9], [0.2, 0.3, 0.7, 0.8]
    )

    assert projected == [0.25, 0.4, 0.6, 0.75]


@pytest.mark.parametrize(
    ("visible", "numeric", "sign", "status"),
    [
        ("1,000", "1000", "positive", "parsed"),
        ("(1,000)", "-1000", "negative", "parsed"),
        ("1 000,50", "1000.5", "positive", "parsed"),
        ("—", None, "not_applicable", "empty_marker"),
        ("USD in thousands", None, "unknown", "non_numeric"),
    ],
)
def test_numeric_parsing_is_mechanical_and_preserves_raw_text(
    visible: str, numeric: str | None, sign: str, status: str
) -> None:
    entry = _entry("g1", value=visible)

    canonical = CONTRACTS.canonicalize_entry(entry)

    assert canonical["visible_value_text_raw"] == visible
    assert canonical["parsed_numeric_value"] == numeric
    assert canonical["parsed_sign"] == sign
    assert canonical["numeric_parse_status"] == status


def test_repeated_numeric_values_align_by_source_regions_not_value_only() -> None:
    gemini = [
        _entry(
            "g_top",
            row="Assets",
            value="10,000",
            row_bbox=[0.05, 0.2, 0.4, 0.25],
            value_bbox=[0.7, 0.2, 0.9, 0.25],
        ),
        _entry(
            "g_bottom",
            row="Liabilities",
            value="10,000",
            row_bbox=[0.05, 0.7, 0.4, 0.75],
            value_bbox=[0.7, 0.7, 0.9, 0.75],
        ),
    ]
    openai = [
        _entry(
            "o_bottom",
            row="Liabilities",
            value="10,000",
            row_bbox=[0.05, 0.7, 0.4, 0.75],
            value_bbox=[0.7, 0.7, 0.9, 0.75],
        ),
        _entry(
            "o_top",
            row="Assets",
            value="10,000",
            row_bbox=[0.05, 0.2, 0.4, 0.25],
            value_bbox=[0.7, 0.2, 0.9, 0.25],
        ),
    ]

    alignment = CONTRACTS.match_entries(gemini, openai)

    pairs = {
        (item["gemini_entry_id"], item["openai_entry_id"])
        for item in alignment["matches"]
    }
    assert pairs == {("g_top", "o_top"), ("g_bottom", "o_bottom")}
    assert all(
        item["matching_signals"]["numeric_value_only_match_used"] is False
        for item in alignment["matches"]
    )


def test_diff_engine_emits_smallest_field_level_value_difference() -> None:
    gemini = [_entry("g1", value="10,500")]
    openai = [_entry("o1", value="10,800")]

    result = CONTRACTS.build_literal_diffs(
        gemini_entries=gemini, openai_entries=openai
    )

    classes = [item["class"] for item in result["disagreements"]]
    assert "visible_value_text_mismatch" in classes
    assert "parsed_numeric_value_mismatch" in classes
    value_diff = next(
        item
        for item in result["disagreements"]
        if item["class"] == "visible_value_text_mismatch"
    )
    assert value_diff["minimal_difference"] == {
        "gemini": "10,500",
        "openai": "10,800",
    }
    assert "model_conflict" not in CONTRACTS.canonical_json_bytes(result).decode(
        "utf-8"
    )


def test_safe_canonicalization_keeps_raw_format_difference_visible() -> None:
    gemini = [_entry("g1", row="Net  income")]
    openai = [_entry("o1", row="Net income")]

    result = CONTRACTS.build_literal_diffs(
        gemini_entries=gemini, openai_entries=openai
    )

    assert result["disagreement_count"] == 0
    assert result["compact_agreements"][0]["status"] == (
        "canonical_match_with_raw_format_difference"
    )


def test_auto_acceptance_requires_unique_independent_parser_binding() -> None:
    gemini = _entry("g1")
    openai = _entry("o1")

    assert (
        CONTRACTS.automatically_acceptable(
            gemini_entry=gemini,
            openai_entry=openai,
            alignment_unique=True,
            parser_evidence_status="parser_literal_verified",
            parser_binding_unique=True,
        )
        is True
    )
    assert (
        CONTRACTS.automatically_acceptable(
            gemini_entry=gemini,
            openai_entry=openai,
            alignment_unique=True,
            parser_evidence_status="parser_value_verified_binding_ambiguous",
            parser_binding_unique=False,
        )
        is False
    )


def test_model_view_contains_no_reference_or_other_provider_data() -> None:
    view = CONTRACTS.literal_model_view(
        crop_sha256="a" * 64,
        table_identifier="table_0",
        image_width=1000,
        image_height=500,
    )
    text = CONTRACTS.canonical_json_bytes(view).decode("utf-8").lower()

    assert "human_reference" not in text
    assert "gemini output" not in text
    assert "openai output" not in text
    assert "financial_semantic_classification\":false" in text
