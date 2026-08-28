from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = SERVICE_ROOT / "scripts" / "visual_logical_column_live_research.py"


def _load_cli():
    name = "visual_logical_column_live_research_cli_under_test"
    spec = importlib.util.spec_from_file_location(name, CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CLI = _load_cli()


def test_validates_one_generic_exact_crop_input(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n")
    value = {
        "schema_version": CLI.INPUT_SCHEMA,
        "case_ref": "generic_case_1",
        "pdf_path": str(pdf_path),
        "page_number": 3,
        "table_bbox": [10, 20.5, 300, 400],
        "table_order": 2,
        "visual_structure_provider_value": {"schema_version": "frozen"},
    }

    result = CLI._validated_input(value)

    assert result["pdf_path"] == str(pdf_path.resolve())
    assert result["table_bbox"] == [10.0, 20.5, 300.0, 400.0]
    assert set(result) == set(value)


def test_rejects_extra_product_meaning_in_generic_input(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n")
    value = {
        "schema_version": CLI.INPUT_SCHEMA,
        "case_ref": "generic_case_1",
        "pdf_path": str(pdf_path),
        "page_number": 1,
        "table_bbox": [10, 20, 300, 400],
        "table_order": 1,
        "visual_structure_provider_value": {},
        "financial_roles": ["amount"],
    }

    with pytest.raises(CLI.VisualLogicalColumnLiveError) as exc_info:
        CLI._validated_input(value)

    assert exc_info.value.code == "visual_logical_column_input_invalid"


def test_resolves_full_source_word_refs_and_bboxes_for_one_page() -> None:
    projection = {
        "layout_projection_status": "complete",
        "page_inventory": [
            {
                "page_number": 1,
                "page_ref": "pdfpage_1",
                "layout_projection_status": "complete",
                "layout_page_width": 600.0,
                "layout_page_height": 800.0,
            }
        ],
        "bbox_inventory": [
            {
                "bbox_ref": "pdfbbox_1",
                "page_ref": "pdfpage_1",
                "bbox": [10.0, 20.0, 50.0, 40.0],
            }
        ],
        "word_inventory": [
            {
                "parser_ordinal": 7,
                "text": "Header",
                "word_ref": "pdfword_real_1",
                "page_ref": "pdfpage_1",
                "bbox_ref": "pdfbbox_1",
            }
        ],
    }

    result = CLI._projection_parser_page(
        projection=projection,
        page_number=1,
        source_sha256="a" * 64,
    )

    assert result["source_page_ref"] == "pdfpage_1"
    assert result["word_inventory"] == [
        {
            "parser_ordinal": 7,
            "text": "Header",
            "bbox": [10.0, 20.0, 50.0, 40.0],
            "source_word_ref": "pdfword_real_1",
            "source_bbox": [10.0, 20.0, 50.0, 40.0],
        }
    ]


def test_safe_receipt_has_terminal_counts_hashes_and_no_private_values() -> None:
    freeze = {
        "freeze_sha256": "f" * 64,
        "source_head": "head",
        "case_ref": "case_1",
        "source_sha256": "a" * 64,
        "png_sha256": "b" * 64,
        "prepared_crop_scope": {"crop_identity": {"manifest_hash": "c" * 64}},
    }
    response = {
        "response_hash": "d" * 64,
        "attempt": {"terminal_failure_class": None, "attempt_number": 1},
        "json_output": {"leaf_label_boxes_2d": [[1, 2, 3, 4]]},
        "raw_private_response": {"source": "private"},
    }
    bound = {
        "leaf_columns": [
            {
                "source_word_refs": ["pdfword_real_1"],
                "header_text": "private literal",
            }
        ],
        "shared_or_non_leaf_header_word_refs": [],
    }

    private, safe = CLI._result_documents(
        freeze=freeze,
        qualification={"status": "qualified"},
        response=response,
        bound=bound,
        validation_error=None,
    )

    assert safe["terminal"] == "SOURCE_BOUND"
    assert safe["counts"]["provider_submissions"] == 1
    assert safe["counts"]["leaf_columns_source_bound"] == 1
    assert safe["counts"]["leaf_source_words"] == 1
    assert safe["hashes"]["provider_response_hash"] == "d" * 64
    assert len(safe["receipt_sha256"]) == 64
    assert safe["private_result_sha256"] == private["private_result_sha256"]
    assert "provider_value" not in safe
    assert "bound_projection" not in safe
    assert "raw_private_response" not in safe
    assert private["bound_projection"] == bound


def test_receipt_is_terminal_when_source_binding_fails() -> None:
    freeze = {
        "freeze_sha256": "f" * 64,
        "source_head": "head",
        "case_ref": "case_1",
        "source_sha256": "a" * 64,
        "png_sha256": "b" * 64,
        "prepared_crop_scope": {"crop_identity": {"manifest_hash": "c" * 64}},
    }
    response = {
        "response_hash": "d" * 64,
        "attempt": {"terminal_failure_class": None, "attempt_number": 1},
        "json_output": {"leaf_label_boxes_2d": []},
        "raw_private_response": {},
    }

    _, safe = CLI._result_documents(
        freeze=freeze,
        qualification={"status": "qualified"},
        response=copy.deepcopy(response),
        bound=None,
        validation_error="visual_logical_column_source_binding_empty",
    )

    assert safe["terminal"] == "SOURCE_BINDING_FAILED"
    assert safe["validation_error"] == "visual_logical_column_source_binding_empty"
    assert safe["counts"]["provider_submissions"] == 1
    assert safe["counts"]["leaf_columns_source_bound"] == 0
