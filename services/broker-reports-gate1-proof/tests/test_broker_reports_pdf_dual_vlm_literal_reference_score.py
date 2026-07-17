from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

import pdf_dual_vlm_literal_contracts as CONTRACTS  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "local_pdf_dual_vlm_literal_reference_score_test",
    SCRIPT_DIR / "local_pdf_dual_vlm_literal_reference_score.py",
)
assert SPEC and SPEC.loader
SCORER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORER)


def _entry(entry_id: str) -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "row_label_text": "Total assets",
        "column_header_path": ["2025"],
        "visible_value_text": "10,500",
        "row_label_bbox": [0.05, 0.2, 0.4, 0.25],
        "header_bboxes": [[0.7, 0.05, 0.9, 0.1]],
        "value_bbox": [0.7, 0.2, 0.9, 0.25],
        "cell_state": "value",
        "uncertainty_codes": [],
    }


def _reference_entry() -> dict[str, object]:
    value = _entry("case_1:r1:e1")
    value["reference_entry_id"] = value.pop("entry_id")
    value.pop("uncertainty_codes")
    value.update(
        {
            "visibly_empty": False,
            "spans_multiple_visual_rows": False,
            "spans_multiple_visual_columns": False,
            "literal_source_notes": "",
            "review_status": "confirmed",
            "review_provenance": {"literal_contract_reviewed_by_human": True},
        }
    )
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(CONTRACTS.canonical_json_bytes(value))


def test_reference_scorer_uses_sealed_human_truth_after_terminal_execution(
    tmp_path: Path,
) -> None:
    terminal_path = tmp_path / "terminal.json"
    terminal_seal_path = tmp_path / "terminal.seal.json"
    padding_path = tmp_path / "padding.json"
    reference_path = tmp_path / "reference.json"
    reference_seal_path = tmp_path / "reference.seal.json"
    diffs_path = tmp_path / "diffs.json"
    scores_path = tmp_path / "scores.json"
    scored_diffs_path = tmp_path / "scored-diffs.json"
    detection_sha = "d" * 64
    terminal = {
        "benchmark_id": "pdf_dual_vlm_literal_v1",
        "reference_accessed": False,
        "detection_terminal_sha256": detection_sha,
        "diagnostic_invalid_upstream_crop_set": False,
        "crops": [
            {
                "case_id": "case_1",
                "candidate_id": "table_0",
                "padded_crop_bbox": [0.1, 0.1, 0.9, 0.9],
                "diagnostic_only": False,
                "gemini": {
                    "terminal_status": "completed",
                    "json_output": {"entries": [_entry("g1")]},
                },
                "openai": {
                    "terminal_status": "completed",
                    "json_output": {"entries": [_entry("o1")]},
                },
            }
        ],
    }
    _write_json(terminal_path, terminal)
    terminal_sha = hashlib.sha256(terminal_path.read_bytes()).hexdigest()
    _write_json(
        terminal_seal_path,
        {
            "terminal_sha256": terminal_sha,
            "terminal_size_bytes": terminal_path.stat().st_size,
        },
    )
    _write_json(
        padding_path,
        {
            "detection_terminal_sha256": detection_sha,
            "cases": [
                {
                    "case_id": "case_1",
                    "matches": [
                        {
                            "candidate_id": "table_0",
                            "reference_region_id": "r1",
                        }
                    ],
                }
            ],
        },
    )
    reference = {
        "schema_version": CONTRACTS.REFERENCE_SCHEMA_VERSION,
        "human_reviewed": True,
        "cases": [
            {
                "case_id": "case_1",
                "document_sha256": "a" * 64,
                "page_number": 1,
                "tables": [
                    {
                        "table_identifier": "case_1:r1",
                        "complete_table_bbox": [0.1, 0.1, 0.9, 0.9],
                        "evidence_medium": "text_layer",
                        "entries": [_reference_entry()],
                    }
                ],
            }
        ],
    }
    _write_json(reference_path, reference)
    reference_sha = hashlib.sha256(reference_path.read_bytes()).hexdigest()
    _write_json(
        reference_seal_path,
        {
            "schema_version": CONTRACTS.REFERENCE_SEAL_SCHEMA_VERSION,
            "reference_sha256": reference_sha,
            "reference_size_bytes": reference_path.stat().st_size,
            "human_reviewed": True,
        },
    )
    _write_json(
        diffs_path,
        {
            "terminal_sha256": terminal_sha,
            "human_reference_added_during_scoring": False,
            "disagreements": [
                {
                    "diff_id": "diff_1",
                    "case_id": "case_1",
                    "candidate_id": "table_0",
                    "exact_gemini_output": _entry("g1"),
                    "exact_openai_output": _entry("o1"),
                    "human_reference_answer": None,
                    "final_benchmark_disposition": "diagnostic_unscored",
                }
            ],
        },
    )
    terminal_before = terminal_path.read_bytes()
    reference_before = reference_path.read_bytes()

    assert SCORER.run(
        argparse.Namespace(
            terminal=str(terminal_path),
            terminal_seal=str(terminal_seal_path),
            padding_experiment=str(padding_path),
            reference=str(reference_path),
            reference_seal=str(reference_seal_path),
            diffs=str(diffs_path),
            output=str(scores_path),
            scored_diffs_output=str(scored_diffs_path),
        )
    ) == 0

    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    scored_diffs = json.loads(scored_diffs_path.read_text(encoding="utf-8"))
    assert scores["terminal_contract_verified_before_reference_access"] is True
    assert scores["terminal_unchanged_during_scoring"] is True
    assert scores["reference_unchanged_during_scoring"] is True
    assert scores["provider_metrics"]["gemini"]["metrics"] == {
        "canonical_numeric_value_accuracy": 1.0,
        "exact_visible_value_accuracy": 1.0,
        "header_path_accuracy": 1.0,
        "header_value_binding_accuracy": 1.0,
        "literal_entry_precision": 1.0,
        "literal_entry_recall": 1.0,
        "row_label_accuracy": 1.0,
        "row_value_binding_accuracy": 1.0,
        "sign_accuracy": 1.0,
        "source_region_coverage": 1.0,
    }
    assert scored_diffs["human_reference_added_during_scoring"] is True
    assert scored_diffs["disagreements"][0]["human_reference_answer"][0][
        "reference_entry_id"
    ] == "case_1:r1:e1"
    assert terminal_path.read_bytes() == terminal_before
    assert reference_path.read_bytes() == reference_before
