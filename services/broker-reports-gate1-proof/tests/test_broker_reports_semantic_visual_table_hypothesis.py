from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from broker_reports_gate1.semantic_visual_table_hypothesis import (
    SEMANTIC_THREE_TABLE_REFERENCE_SCHEMA,
    SemanticThreeTableHypothesisError,
    compare_material_repeatability,
    evaluate_three_table_gate,
    public_score_summary,
    score_semantic_response,
    validate_source_reference,
)
from broker_reports_gate1.pdf_dual_vlm_runtime import sha256_json
from broker_reports_gate1.semantic_visual_table_contracts import (
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT,
    semantic_table_transcription_model_view,
    semantic_table_transcription_schema,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    SERVICE_ROOT / "benchmarks" / "semantic_visual_three_table_v1" / "manifest.json"
)


def _table(table_id: str, crop_character: str) -> dict:
    return {
        "table_id": table_id,
        "crop_sha256": crop_character * 64,
        "rows": [
            {
                "cells": ["Assets", None, None],
                "labels": ["Assets"],
                "amounts": [],
                "markers": [],
            },
            {
                "cells": ["Synthetic lease asset", "$", "(1,234.56)"],
                "labels": ["Synthetic lease asset"],
                "amounts": ["(1,234.56)"],
                "markers": ["$"],
            },
        ],
    }


def _reference() -> dict:
    return {
        "schema_version": SEMANTIC_THREE_TABLE_REFERENCE_SCHEMA,
        "source_only": True,
        "provider_outputs_used": False,
        "provider_agreement_used": False,
        "customer_acceptance_claimed": False,
        "tables": [_table("one", "a"), _table("two", "b"), _table("three", "c")],
    }


def _response() -> dict:
    return {
        "description": "A small source table.",
        "rows": [
            ["Assets", None],
            ["Synthetic lease asset", "$", "(1,234.56)"],
        ],
    }


def test_source_reference_is_source_only_and_role_accounted() -> None:
    value = _reference()
    assert validate_source_reference(value) == value

    invalid = copy.deepcopy(value)
    invalid["tables"][0]["rows"][1]["markers"] = []
    with pytest.raises(SemanticThreeTableHypothesisError) as caught:
        validate_source_reference(invalid)
    assert caught.value.code.endswith("role_accounting_invalid")


def test_perfect_semantic_response_scores_literal_content_without_geometry() -> None:
    response = _response()
    score = score_semantic_response(
        _reference()["tables"][0],
        response,
        raw_json_text=json.dumps(response, ensure_ascii=False),
    )

    assert score["json_parse_success"] is True
    assert score["label_completeness"]["rate"] == 1.0
    assert score["amount_fidelity"]["rate"] == 1.0
    assert score["currency_sign_parenthesis_fidelity"]["rate"] == 1.0
    assert score["currency_sign_parenthesis_fidelity"]["opportunities"] == 2
    assert score["row_value_binding"]["rate"] == 1.0
    assert score["row_order"]["exact"] is True
    assert score["hallucinated_labels"] == []
    assert score["hallucinated_amounts"] == []
    assert score["manual_correction_count"] == 0
    assert score["geometric_metrics_used"] is False
    assert score["physical_grid_coverage_scored"] is False


def test_combined_currency_and_amount_cell_is_literal_semantic_equivalent() -> None:
    response = {
        "description": "A small source table.",
        "rows": [["Assets", None], ["Synthetic lease asset", "$ (1,234.56)"]],
    }
    score = score_semantic_response(
        _reference()["tables"][0],
        response,
        raw_json_text=json.dumps(response),
    )
    assert score["amount_fidelity"]["rate"] == 1.0
    assert score["currency_sign_parenthesis_fidelity"]["rate"] == 1.0
    assert score["row_value_binding"]["rate"] == 1.0
    assert score["hallucinated_amounts"] == []
    assert score["manual_correction_count"] == 0


def test_scorer_detects_omission_hallucination_binding_and_order() -> None:
    response = {
        "description": "Source table.",
        "rows": [
            ["Synthetic lease asset", "$", "9,999"],
            ["Assets"],
            ["Invented label"],
            ["(1,234.56)"],
        ],
    }
    score = score_semantic_response(
        _reference()["tables"][0],
        response,
        raw_json_text=json.dumps(response),
    )

    assert score["amount_fidelity"]["rate"] == 1.0
    assert score["row_value_binding"]["rate"] == 0.0
    assert score["row_order"]["exact"] is False
    assert score["hallucinated_labels"] == ["Invented label"]
    assert score["hallucinated_amounts"] == ["9,999"]
    assert score["manual_correction_count"] > 0


def test_empty_string_is_a_null_semantics_violation_not_a_hallucinated_label() -> None:
    response = {
        "description": "Source table.",
        "rows": [
            ["Assets", ""],
            ["Synthetic lease asset", "$", "(1,234.56)"],
        ],
    }
    score = score_semantic_response(
        _reference()["tables"][0],
        response,
        raw_json_text=json.dumps(response),
    )
    assert score["hallucinated_labels"] == []
    assert score["unexpected_empty_string_count"] == 1
    assert score["manual_correction_count"] == 1


def test_raw_json_must_bind_exactly_without_repair() -> None:
    response = _response()
    different = copy.deepcopy(response)
    different["rows"][1][2] = "(1,234.57)"
    score = score_semantic_response(
        _reference()["tables"][0],
        response,
        raw_json_text=json.dumps(different),
    )
    assert score["json_parse_success"] is False
    assert score["validator_error_codes"] == [
        "semantic_table_transcription_raw_json_binding_invalid"
    ]
    assert score["provider_output_repaired"] is False


def test_material_repeatability_ignores_description_and_null_padding_only() -> None:
    response_a = _response()
    response_b = {
        "description": "Different short observation.",
        "rows": [
            ["Assets", None, None],
            ["Synthetic lease asset", "$", "(1,234.56)", None],
        ],
    }
    repeat = compare_material_repeatability(response_a, response_b)
    assert repeat["materially_identical"] is True
    assert repeat["description_compared"] is False
    assert repeat["null_padding_compared"] is False
    assert repeat["physical_geometry_compared"] is False

    response_b["rows"][1][2] = "(1,234.57)"
    assert compare_material_repeatability(response_a, response_b)[
        "materially_identical"
    ] is False


def test_gate_uses_six_gemini_outputs_and_keeps_openai_non_authoritative() -> None:
    executions = []
    repeats = []
    for index, table in enumerate(_reference()["tables"], start=1):
        response = _response()
        score = score_semantic_response(
            table,
            response,
            raw_json_text=json.dumps(response),
        )
        crop_sha256 = table["crop_sha256"]
        executions.extend(
            [
                {
                    "provider": "gemini",
                    "run": "a",
                    "crop_sha256": crop_sha256,
                    "score": score,
                },
                {
                    "provider": "gemini",
                    "run": "b",
                    "crop_sha256": crop_sha256,
                    "score": score,
                },
                {
                    "provider": "openai",
                    "run": "control",
                    "crop_sha256": crop_sha256,
                    "score": {"json_parse_success": False},
                },
            ]
        )
        repeats.append(compare_material_repeatability(response, response))

    gate = evaluate_three_table_gate(executions, repeats)
    assert gate["status"] == "COMPLETED"
    assert gate["openai_control_is_non_authoritative"] is True
    assert gate["checks"]["geometric_failures_as_metric_zero"] is True

    executions[0]["score"]["amount_fidelity"]["rate"] = 0.0
    failed = evaluate_three_table_gate(executions, repeats)
    assert failed["status"] == "NOT_CLOSED"
    assert "gemini_amount_fidelity_100_percent" in failed["failed_invariants"]


def test_public_summary_removes_literal_differences() -> None:
    response = _response()
    score = score_semantic_response(
        _reference()["tables"][0],
        response,
        raw_json_text=json.dumps(response),
    )
    public = public_score_summary(score)
    serialized = json.dumps(public)
    assert "Synthetic lease asset" not in serialized
    assert "(1,234.56)" not in serialized
    assert public["amount_fidelity"]["rate"] == 1.0


def test_frozen_manifest_binds_three_crops_contract_and_existing_factory() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["frozen_before_provider_execution"] is True
    assert len(manifest["cases"]) == 3
    assert len({case["crop_sha256"] for case in manifest["cases"]}) == 3
    assert manifest["provider_contracts"]["gemini"]["executions"] == 6
    assert manifest["provider_contracts"]["openai"]["executions"] == 3
    assert (
        manifest["execution_policy"]["runtime_factory"]
        == "PdfDualVlmRuntimeFactory.create_for_openwebui"
    )
    assert manifest["execution_policy"]["provider_merge"] is False
    assert manifest["execution_policy"]["provider_repair"] is False
    assert manifest["execution_policy"]["geometric_metrics"] is False

    contract = manifest["semantic_contract"]
    assert contract["schema_sha256"] == sha256_json(
        semantic_table_transcription_schema()
    )
    assert contract["model_view_sha256"] == sha256_json(
        semantic_table_transcription_model_view()
    )
    assert contract["prompt_sha256"] == hashlib.sha256(
        SEMANTIC_TABLE_TRANSCRIPTION_PROMPT.encode("utf-8")
    ).hexdigest()
    for case in manifest["cases"]:
        candidate = copy.deepcopy(case["candidate_manifest"])
        actual_hash = candidate.pop("manifest_hash")
        assert sha256_json(candidate) == actual_hash
        assert case["crop_sha256"] == candidate["png_sha256"]
        assert candidate["renderer"] == "pymupdf"
        assert candidate["renderer_version"] == "1.26.5"
        assert candidate["dpi"] == 150
