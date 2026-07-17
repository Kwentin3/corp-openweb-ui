from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

import pdf_dual_vlm_literal_contracts as CONTRACTS  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "local_pdf_dual_vlm_literal_reference_pack_test",
    SCRIPT_DIR / "local_pdf_dual_vlm_literal_reference_pack.py",
)
assert SPEC and SPEC.loader
PACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACK)


def _draft() -> dict[str, object]:
    return {
        "schema_version": CONTRACTS.REFERENCE_SCHEMA_VERSION,
        "benchmark_id": "pdf_dual_vlm_literal_v1",
        "human_reviewed": False,
        "manifest_sha256": "a" * 64,
        "reference_scope": "all_visible_value_bearing_table_entries",
        "semantic_financial_types_present": False,
        "prior_human_review_carry_forward_is_final_review": False,
        "preparation_accounting": {
            "entries_with_prior_human_fact_review": 0,
            "entries_new_to_literal_scope": 1,
        },
        "cases": [
            {
                "case_id": "case_1",
                "document_sha256": "b" * 64,
                "page_number": 1,
                "tables": [
                    {
                        "table_identifier": "case_1:r1",
                        "complete_table_bbox": [0.1, 0.1, 0.9, 0.9],
                        "crop_sha256": "c" * 64,
                        "crop_asset": "assets/case_1--r1.png",
                        "evidence_medium": "text_layer",
                        "another_table_near_crop_boundary": False,
                        "entries": [
                            {
                                "reference_entry_id": "case_1:r1:r2:c2",
                                "row_label_text": "Total assets",
                                "column_header_path": ["2025"],
                                "visible_value_text": "10,500",
                                "row_label_bbox": [0.1, 0.2, 0.4, 0.25],
                                "header_bboxes": [[0.7, 0.1, 0.9, 0.15]],
                                "value_bbox": [0.7, 0.2, 0.9, 0.25],
                                "cell_state": "value",
                                "visibly_empty": False,
                                "spans_multiple_visual_rows": False,
                                "spans_multiple_visual_columns": False,
                                "literal_source_notes": "",
                                "review_status": "pending",
                                "review_provenance": {
                                    "new_literal_review_required": True
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(CONTRACTS.canonical_json_bytes(value))


def test_finalize_rejects_ai_reviewer_and_does_not_create_reference(
    tmp_path: Path,
) -> None:
    draft_path = tmp_path / "draft.json"
    decision_path = tmp_path / "decisions.json"
    output_dir = tmp_path / "sealed"
    _write_json(draft_path, _draft())
    template = PACK._decision_template(_draft(), draft_path)
    template["reviewer"] = {"type": "human", "id": "codex"}
    template["reviewed_at"] = "2026-07-17T12:00:00+03:00"
    template["decisions"][0]["decision"] = "confirmed"
    _write_json(decision_path, template)

    with pytest.raises(
        PACK.LiteralReferencePackError,
        match="literal_reference_human_reviewer_required",
    ):
        PACK.finalize_reference(
            argparse.Namespace(
                draft=str(draft_path),
                decisions=str(decision_path),
                output_dir=str(output_dir),
            )
        )

    assert not (
        output_dir / "OPENWEBUI_PDF_TABLE_LITERAL_REFERENCE.v1.json"
    ).exists()


def test_finalize_seals_complete_human_decisions_with_checksum(tmp_path: Path) -> None:
    draft_path = tmp_path / "draft.json"
    decision_path = tmp_path / "decisions.json"
    output_dir = tmp_path / "sealed"
    draft = _draft()
    _write_json(draft_path, draft)
    decisions = PACK._decision_template(draft, draft_path)
    decisions["reviewer"] = {"type": "human", "id": "roman"}
    decisions["reviewed_at"] = "2026-07-17T12:00:00+03:00"
    decisions["decisions"][0]["decision"] = "confirmed"
    _write_json(decision_path, decisions)

    assert (
        PACK.finalize_reference(
            argparse.Namespace(
                draft=str(draft_path),
                decisions=str(decision_path),
                output_dir=str(output_dir),
            )
        )
        == 0
    )

    reference_path = output_dir / "OPENWEBUI_PDF_TABLE_LITERAL_REFERENCE.v1.json"
    seal_path = output_dir / "OPENWEBUI_PDF_TABLE_LITERAL_REFERENCE.v1.sha256.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    assert reference["human_reviewed"] is True
    assert reference["cases"][0]["tables"][0]["entries"][0]["review_status"] == (
        "confirmed"
    )
    assert seal["reference_sha256"] == PACK.hashlib.sha256(
        reference_path.read_bytes()
    ).hexdigest()
    assert CONTRACTS.validate_reference(reference, require_human_reviewed=True) == []


def test_finalize_requires_one_terminal_decision_per_entry(tmp_path: Path) -> None:
    draft_path = tmp_path / "draft.json"
    decision_path = tmp_path / "decisions.json"
    _write_json(draft_path, _draft())
    decisions = PACK._decision_template(_draft(), draft_path)
    decisions["reviewer"] = {"type": "human", "id": "roman"}
    decisions["reviewed_at"] = "2026-07-17T12:00:00+03:00"
    decisions["decisions"] = []
    _write_json(decision_path, decisions)

    with pytest.raises(
        PACK.LiteralReferencePackError,
        match="literal_reference_decision_coverage_invalid",
    ):
        PACK.finalize_reference(
            argparse.Namespace(
                draft=str(draft_path),
                decisions=str(decision_path),
                output_dir=str(tmp_path / "sealed"),
            )
        )


def test_reference_review_html_explains_bbox_order_and_export_feedback(
    tmp_path: Path,
) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "case_1--r1.png").write_bytes(b"png-fixture")

    review_html = PACK._review_html(_draft(), assets_dir)

    assert "[x0, y0, x1, y1] = [left, top, right, bottom]" in review_html
    assert "never use <code>[top, left, bottom, right]</code>" in review_html
    assert 'role="status"' in review_html
    assert 'id="export" disabled' in review_html
    assert "Decision file exported successfully." in review_html
    assert ":focus-visible" in review_html


def test_finalize_allows_human_exclusion_of_entry_without_locator(
    tmp_path: Path,
) -> None:
    draft_path = tmp_path / "draft.json"
    decision_path = tmp_path / "decisions.json"
    output_dir = tmp_path / "sealed"
    draft = _draft()
    entry = draft["cases"][0]["tables"][0]["entries"][0]
    entry["row_label_bbox"] = None
    entry["value_bbox"] = None
    _write_json(draft_path, draft)
    decisions = PACK._decision_template(draft, draft_path)
    decisions["reviewer"] = {"type": "human", "id": "roman"}
    decisions["reviewed_at"] = "2026-07-17T12:00:00+03:00"
    decisions["decisions"][0]["decision"] = "excluded"
    _write_json(decision_path, decisions)

    assert PACK.finalize_reference(
        argparse.Namespace(
            draft=str(draft_path),
            decisions=str(decision_path),
            output_dir=str(output_dir),
        )
    ) == 0
    reference = json.loads(
        (output_dir / "OPENWEBUI_PDF_TABLE_LITERAL_REFERENCE.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert reference["cases"][0]["tables"][0]["entries"][0][
        "review_status"
    ] == "excluded"
