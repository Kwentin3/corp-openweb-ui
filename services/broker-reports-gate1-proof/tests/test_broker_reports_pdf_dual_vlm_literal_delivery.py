from __future__ import annotations

import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
MANIFEST = SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_literal_v1" / "manifest.json"
REPORT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-17"
    / "OPENWEBUI_PDF_TABLE_DUAL_VLM_LITERAL_KEY_VALUE_BENCHMARK.report.md"
)


def test_manifest_freezes_only_predeclared_global_padding_variants() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["rendering_contract"][
        "padding_fraction_per_page_side_variants"
    ] == [0.0, 0.005, 0.01, 0.02, 0.03]
    assert manifest["rendering_contract"]["padding_is_global"] is True
    assert manifest["rendering_contract"]["detected_bbox_immutable"] is True
    assert manifest["execution_policy"]["hidden_retry"] is False
    assert manifest["execution_policy"]["third_llm_arbiter"] is False
    assert manifest["historical_context"]["semantic_type_mapping_allowed"] is False


def test_report_starts_with_required_failed_gates_and_literal_conclusion() -> None:
    report = REPORT.read_text(encoding="utf-8-sig")
    required_prefix = """TABLE_DETECTION_AND_PADDED_CROPPING:
FAILED

GEMINI_LITERAL_TABLE_READING:
FAILED

OPENAI_LITERAL_TABLE_READING:
FAILED

DUAL_VLM_LITERAL_AGREEMENT:
FAILED

LITERAL_SOURCE_EVIDENCE:
FAILED

DUAL_VLM_LITERAL_EXTRACTION_PROMISING_BUT_NOT_READY
"""

    assert report.startswith(required_prefix)
    assert "Selected fixed padding: **none**" in report
    assert "Financial semantic classification remains a separate Gate 3" in report
    assert "The accepted `OPENWEBUI_PDF_TABLE_LITERAL_REFERENCE.v1.json` was **not** fabricated" in report


def test_reference_and_extraction_entrypoints_do_not_accept_human_reference() -> None:
    detection = (
        SERVICE_ROOT / "scripts" / "local_pdf_dual_vlm_literal_detection.py"
    ).read_text(encoding="utf-8")
    extraction = (
        SERVICE_ROOT / "scripts" / "local_pdf_dual_vlm_literal_extract.py"
    ).read_text(encoding="utf-8")

    assert 'add_argument("--reference"' not in detection
    assert 'add_argument("--reference"' not in extraction
    assert '"reference_argument_supported": False' in detection
    assert '"reference_argument_supported": False' in extraction


def test_diff_review_bundle_has_required_filters_states_and_feedback() -> None:
    source = (
        SERVICE_ROOT / "scripts" / "local_pdf_dual_vlm_literal_diff_bundle.py"
    ).read_text(encoding="utf-8")

    for control in (
        "classFilter",
        "categoryFilter",
        "mediumFilter",
        "providerFilter",
        "search",
    ):
        assert f"id='{control}'" in source
    assert "data-medium=" in source
    assert "No disagreements require review" in source
    assert "role='status'" in source
    assert "id='export' disabled" in source
    assert "Decision file exported successfully." in source
    assert ":focus-visible" in source
