from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "local_whole_document_canonical_audit_g595.py"
MANIFEST_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "whole_document_canonical_audit_g595"
    / "manifest.json"
)


def _load_runner():
    spec = importlib.util.spec_from_file_location("g595_runner_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner()


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_freezes_largest_whole_report_before_review() -> None:
    manifest = RUNNER._load_manifest(MANIFEST_PATH)

    assert manifest["selection"] == {
        "criterion": "maximum_declared_page_count_then_document_id_ascending",
        "selected_document_id": "document_04",
        "selected_pdf_sha256": "7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015",
        "pages": 65,
        "fixed_before_g595_comparative_review": True,
    }
    assert manifest["variant_b"]["source"] == "g594_primary_run1_markdown_only"
    assert manifest["scope"]["hybrid_design"] is False


def test_adapter_projects_only_explicit_headings_text_and_tables() -> None:
    markdown = (
        "## Visible heading\n\n"
        "First line\nsecond line\n\n"
        "| A | B |\n| --- | :---: |\n| -1 | 2,5 |\n"
    )

    page = RUNNER.project_markdown_page(7, markdown)

    assert page["status"] == "represented"
    assert [node["type"] for node in page["nodes"]] == ["HEADING", "TEXT", "TABLE"]
    assert page["nodes"][0] == {
        "type": "HEADING",
        "order": 0,
        "level": 2,
        "literal": "Visible heading",
    }
    assert page["nodes"][1]["literal"] == "First line\nsecond line"
    table = page["nodes"][2]
    assert table["column_count"] == 2
    assert [row["role"] for row in table["rows"]] == ["HEADER", "BODY"]
    assert [cell["literal"] for cell in table["rows"][1]["cells"]] == ["-1", "2,5"]
    assert page["capabilities"]["source_coordinates"] is False


def test_ambiguous_or_ragged_markdown_stays_coarse_text() -> None:
    markdown = "A | B\nnot a delimiter\n1 | 2\n\n| H1 | H2 |\n| --- | --- |\n| only one |"

    page = RUNNER.project_markdown_page(1, markdown)

    assert [node["type"] for node in page["nodes"]] == ["TEXT", "TABLE", "TEXT"]
    assert page["nodes"][0]["literal"] == "A | B\nnot a delimiter\n1 | 2"
    assert len(page["nodes"][1]["rows"]) == 1
    assert page["nodes"][1]["rows"][0]["role"] == "HEADER"
    assert page["nodes"][2]["literal"] == "| only one |"


def test_unavailable_page_has_no_simulated_nodes_or_coordinates() -> None:
    page = RUNNER.project_markdown_page(33, None)

    assert page == {
        "page": 33,
        "status": "unavailable",
        "nodes": [],
        "capabilities": {
            "page_identity": True,
            "node_order": True,
            "markdown_line_identity": True,
            "source_coordinates": False,
            "pdf_cell_path": False,
            "glyph_or_word_refs": False,
        },
    }


def test_review_validation_requires_every_page_and_exact_b_availability() -> None:
    manifest = _manifest()
    projection = {
        "schema_version": RUNNER.PROJECTION_SCHEMA,
        "goal": "G5.95",
        "manifest_sha256": RUNNER._sha256_json(manifest),
        "document_id": "document_04",
        "pages": [RUNNER.project_markdown_page(page, "text") for page in range(1, 66)],
        "source_primary_result_sha256": [f"hash-{page}" for page in range(1, 66)],
        "adapter_inputs": ["page_number", "primary_markdown_or_unavailable"],
        "pdf_or_variant_a_used": False,
    }
    projection["pages"][32] = RUNNER.project_markdown_page(33, None)
    review = {
        "schema_version": RUNNER.REVIEW_SCHEMA,
        "manifest_sha256": RUNNER._sha256_json(manifest),
        "original_pdf_only_referee": True,
        "adapter_verdict": "MECHANICAL",
        "architecture_verdict": "measured independently",
        "pages": [_review_page(page, page != 33) for page in range(1, 66)],
    }

    RUNNER._validate_projection(projection, manifest)
    RUNNER._validate_review(review, manifest, projection)

    review["pages"][32]["B"]["page_represented"] = True
    with pytest.raises(RUNNER.G595Error, match="g595_b_availability_review_mismatch"):
        RUNNER._validate_review(review, manifest, projection)


def _review_page(page: int, b_available: bool) -> dict:
    arm = {
        "page_represented": True,
        "tables_represented": 1,
        "body_rows_represented": 2,
        "headers_preserved": 1,
        "changed_literals": 0,
        "lost_text_segments": 0,
        "invented_text_segments": 0,
        "wrong_row_structure": 0,
        "wrong_column_relations": 0,
        "broken_order": 0,
    }
    b = dict(arm)
    b["page_represented"] = b_available
    if not b_available:
        b["tables_represented"] = 0
        b["body_rows_represented"] = 0
        b["headers_preserved"] = 0
    return {
        "page": page,
        "source_truth_reviewed": True,
        "visual": {"tables": 1, "body_rows": 2, "headers": 1},
        "A": arm,
        "B": b,
    }


def test_terminal_keeps_local_column_gain_separate_from_whole_report_result() -> None:
    aggregate = {
        "A": {
            "structural_errors_total": 21,
            "wrong_column_relations": 5,
            "literal_errors_total": 11,
        },
        "B": {
            "structural_errors_total": 61,
            "wrong_column_relations": 0,
            "literal_errors_total": 23,
        },
    }

    terminals = RUNNER._terminal(aggregate, "MECHANICAL")

    assert "MARKDOWN_TO_CANONICAL_THIN_ADAPTER_PROVEN" in terminals
    assert "COLUMN_RELATION_ADVANTAGE_B_CONFIRMED" in terminals
    assert "VISUAL_STRUCTURE_ADVANTAGE_B_CONFIRMED" not in terminals
    assert "G594_SAMPLE_CONCLUSION_NOT_CONFIRMED_WHOLE_DOCUMENT" in terminals
    assert "LITERAL_AUTHORITY_ADVANTAGE_A_CONFIRMED" in terminals
