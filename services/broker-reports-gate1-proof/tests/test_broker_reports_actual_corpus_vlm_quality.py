from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import evaluate_pdf_dual_vlm_actual_corpus as EVALUATION  # noqa: E402


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _entry(index: int, value: str = "1") -> dict:
    return {
        "reference_entry_id": f"entry_{index}",
        "row_label_text": "Metric",
        "column_header_path": ["Value"],
        "visible_value_text": value,
        "row_label_bbox": [0.0, 0.5, 0.4, 1.0],
        "header_bboxes": [[0.5, 0.0, 1.0, 0.5]],
        "value_bbox": [0.5, 0.5, 1.0, 1.0],
        "cell_state": "value",
        "visibly_empty": False,
        "spans_multiple_visual_rows": False,
        "spans_multiple_visual_columns": False,
        "literal_source_notes": "",
        "review_status": "pending",
        "review_provenance": {},
    }


def _table_specs() -> list[tuple[int, int, int]]:
    return [
        (table_index, table_index if table_index < 8 else 7, 1 if table_index < 8 else 2)
        for table_index in range(9)
    ]


def _literal_draft() -> dict:
    cases = []
    for case_index in range(8):
        tables = []
        for table_index, table_case_index, region_index in _table_specs():
            if table_case_index != case_index:
                continue
            tables.append(
                {
                    "table_identifier": f"case_{case_index}:r{region_index}",
                    "complete_table_bbox": [0.0, 0.0, 1.0, 1.0],
                    "crop_asset": f"crop_{table_index}.png",
                    "crop_sha256": _sha(f"crop-{table_index}"),
                    "evidence_medium": "raster",
                    "another_table_near_crop_boundary": False,
                    "entries": [
                        _entry(table_index * 10 + entry_index)
                        for entry_index in range(10 if table_index < 8 else 9)
                    ],
                }
            )
        cases.append(
            {
                "case_id": f"case_{case_index}",
                "document_sha256": _sha(f"document-{case_index}"),
                "page_number": 1,
                "tables": tables,
            }
        )
    return {
        "schema_version": EVALUATION.LITERAL_DRAFT_SCHEMA,
        "benchmark_id": "test_actual_corpus",
        "manifest_sha256": "a" * 64,
        "human_reviewed": False,
        "prior_human_review_carry_forward_is_final_review": False,
        "semantic_financial_types_present": False,
        "reference_scope": "all_visible_value_bearing_table_entries",
        "preparation_accounting": {},
        "cases": cases,
    }


def _run_identity() -> dict:
    value = {
        "schema_version": EVALUATION.RUN_IDENTITY_SCHEMA,
        "status": "completed",
        "source_revision": "b" * 40,
        "terminal_sha256": "c" * 64,
        "manifest_sha256": "d" * 64,
        "detection_terminal_sha256": "e" * 64,
        "reference_accessed": False,
        "provider_output_as_reference_truth": False,
        "provider_consensus_as_reference_truth": False,
        "repeat_count": 2,
        "configured_models": {
            "gemini": EVALUATION.DEFAULT_GEMINI_MODEL,
            "openai": EVALUATION.DEFAULT_OPENAI_MODEL,
        },
        "units": [
            {
                "candidate_ref": f"goal1_case_{case_index}_table_{region_index}",
                "source_sha256": _sha(f"document-{case_index}"),
                "page_number": 1,
                "crop_sha256": _sha(f"evaluated-crop-{table_index}"),
                "crop_manifest_hash": _sha(f"manifest-{table_index}"),
                "dpi": 150,
            }
            for table_index, case_index, region_index in _table_specs()
        ],
        "provider_output_values_included": False,
    }
    value["identity_hash"] = EVALUATION.sha256_json(value)
    return value


def _review_decisions() -> dict:
    return {
        "schema_version": EVALUATION.REVIEW_DECISIONS_SCHEMA,
        "delegation": {
            "kind": "explicit_user_delegation",
            "delegator_identity": "authenticated_thread_user",
            "delegation_statement_sha256": "f" * 64,
            "delegation_statement_retained": False,
        },
        "reviewer": {
            "kind": "delegated_agent",
            "identity": "OpenAI Codex",
            "reviewed_at": "2026-07-21T15:30:00+03:00",
        },
        "source_review_only": True,
        "provider_outputs_opened": False,
        "provider_consensus_opened": False,
        "customer_acceptance_claimed": False,
        "entries": [
            {
                "case_id": f"case_{case_index}",
                "page_number": 1,
                "table_identifier": f"case_{case_index}:r{region_index}",
                "runtime_candidate_ref": f"goal1_case_{case_index}_table_{region_index}",
                "disposition": (
                    "unsupported_layout"
                    if table_index == 8
                    else "assisted_review_candidate"
                ),
                "layout_characteristics": [
                    "long_form_prose" if table_index == 8 else "simple_grid"
                ],
                "attestations": {
                    key: True for key in EVALUATION.REVIEW_ATTESTATIONS
                },
                "review_note": "source-only review",
            }
            for table_index, case_index, region_index in _table_specs()
        ],
    }


def _proposal(*, extra_numeric: bool = False) -> dict:
    cells = [
        {
            "row_index": 0,
            "column_index": 0,
            "row_span": 1,
            "column_span": 1,
            "content_state": "empty",
            "source_text": "",
        },
        {
            "row_index": 0,
            "column_index": 1,
            "row_span": 1,
            "column_span": 1,
            "content_state": "present",
            "source_text": "Value",
        },
        {
            "row_index": 1,
            "column_index": 0,
            "row_span": 1,
            "column_span": 1,
            "content_state": "present",
            "source_text": "Metric",
        },
        {
            "row_index": 1,
            "column_index": 1,
            "row_span": 1,
            "column_span": 1,
            "content_state": "present",
            "source_text": "1",
        },
    ]
    if extra_numeric:
        cells.append(
            {
                "row_index": 2,
                "column_index": 0,
                "row_span": 1,
                "column_span": 2,
                "content_state": "present",
                "source_text": "999",
            }
        )
    return {
        "schema_version": "broker_reports_canonical_table_v1",
        "table_id": "goal1_case_0_table_0",
        "row_count": 3 if extra_numeric else 2,
        "column_count": 2,
        "cells": cells,
    }


def _execution() -> dict:
    return {
        "terminal_provider_status": "completed",
        "requested_model_id": EVALUATION.DEFAULT_GEMINI_MODEL,
        "resolved_model_id": EVALUATION.DEFAULT_GEMINI_MODEL,
        "input_hash": "a" * 64,
        "crop_sha256": "a" * 64,
        "validator_result": {"status": "passed"},
    }


def test_delegated_reference_is_source_only_and_distinct_from_human_truth(
    tmp_path: Path,
) -> None:
    draft_path = tmp_path / "draft.json"
    decisions_path = tmp_path / "decisions.json"
    identity_path = tmp_path / "identity.json"
    draft_path.write_bytes(EVALUATION.canonical_json_bytes(_literal_draft()))
    decisions_path.write_bytes(
        EVALUATION.canonical_json_bytes(_review_decisions())
    )
    identity_path.write_bytes(EVALUATION.canonical_json_bytes(_run_identity()))

    reference, seal = EVALUATION.finalize_delegated_reference(
        literal_draft_path=draft_path,
        review_decisions_path=decisions_path,
        run_identity_path=identity_path,
        output_dir=tmp_path / "reference",
    )

    assert reference["human_reviewed"] is False
    assert reference["delegated_agent_reviewed"] is True
    assert reference["customer_accepted"] is False
    assert reference["lineage"]["provider_outputs_used"] is False
    assert reference["lineage"]["provider_consensus_used"] is False
    assert seal["human_reviewed"] is False
    assert all(
        entry["review_status"] == "confirmed"
        for table in reference["literal_reference"]["tables"]
        for entry in table["entries"]
    )
    assert all(
        table["source_crop_identity_rebound_after_visual_review"] is True
        and table["evaluated_crop_sha256"] != table["source_draft_crop_sha256"]
        for table in reference["literal_reference"]["tables"]
    )


def test_reference_finalization_rejects_provider_output_review(tmp_path: Path) -> None:
    decisions = _review_decisions()
    decisions["provider_outputs_opened"] = True
    draft_path = tmp_path / "draft.json"
    decisions_path = tmp_path / "decisions.json"
    identity_path = tmp_path / "identity.json"
    draft_path.write_bytes(EVALUATION.canonical_json_bytes(_literal_draft()))
    decisions_path.write_bytes(EVALUATION.canonical_json_bytes(decisions))
    identity_path.write_bytes(EVALUATION.canonical_json_bytes(_run_identity()))

    with pytest.raises(
        EVALUATION.ActualCorpusVlmEvaluationError,
        match="actual_corpus_review_decisions_invalid",
    ):
        EVALUATION.finalize_delegated_reference(
            literal_draft_path=draft_path,
            review_decisions_path=decisions_path,
            run_identity_path=identity_path,
            output_dir=tmp_path / "reference",
        )


def test_scoring_separates_contract_value_omission_hallucination_and_structure() -> None:
    exact = EVALUATION.score_proposal(
        proposal=_proposal(),
        execution=_execution(),
        reference_entries=[_entry(0)],
    )
    extra = EVALUATION.score_proposal(
        proposal=_proposal(extra_numeric=True),
        execution=_execution(),
        reference_entries=[_entry(0)],
    )

    assert exact["contract_valid"] is True
    assert exact["exact_literal_value_agreement_rate"] == 1.0
    assert exact["numeric_value_agreement_rate"] == 1.0
    assert exact["row_binding_support_rate"] == 1.0
    assert exact["omission_rate"] == 0.0
    assert exact["numeric_hallucination_rate"] == 0.0
    assert exact["structurally_useful_for_assisted_review"] is True
    assert extra["numeric_hallucination_rate"] == 0.5
    assert extra["structurally_useful_for_assisted_review"] is False


def test_aggregate_measures_real_repeatability_and_keeps_review_required() -> None:
    base = EVALUATION.score_proposal(
        proposal=_proposal(),
        execution=_execution(),
        reference_entries=[_entry(0)],
    )
    samples = []
    for provider in ("gemini", "openai"):
        for repeat in (1, 2):
            item = copy.deepcopy(base)
            item.update(
                {
                    "candidate_ref_hash": "a" * 64,
                    "provider": provider,
                    "repeat_index": repeat,
                    "provider_terminal_status": "completed",
                }
            )
            if provider == "openai" and repeat == 2:
                item["proposal_hash"] = "b" * 64
            samples.append(item)
    decisions = [
        {
            "decision_status": "proposal_requires_review",
            "review_required": True,
            "disagreement_classification": "provider_disagreement",
            "canonical_table_published": False,
            "provider_proposal_canonical_authority": False,
        }
        for _ in range(2)
    ]

    metrics = EVALUATION.aggregate_metrics(
        samples=samples,
        decisions=decisions,
        table_reviews=_review_decisions()["entries"],
        repeat_count=2,
    )

    assert metrics["exact_proposal_repeatability_rate"] == 0.5
    assert metrics["nondeterministic_unit_provider_pairs"] == 1
    assert metrics["provider_disagreement_rate"] == 1.0
    assert metrics["review_rate"] == 1.0
    assert metrics["unsupported_layout_rejection_rate"] == round(1 / 9, 6)
    assert metrics["canonical_tables_published"] == 0


def test_live_runner_uses_default_budget_and_terminal_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.draw_rect(fitz.Rect(30, 30, 270, 170))
    pdf_bytes = document.tobytes(garbage=4, deflate=True)
    document.close()
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    pdf_path = corpus / "actual.pdf"
    pdf_path.write_bytes(pdf_bytes)
    pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = {
        "cases": [
            {
                "case_id": f"case_{index}",
                "relative_pdf": "actual.pdf",
                "pdf_sha256": pdf_sha,
                "page_number": 1,
            }
            for index in range(9)
        ]
    }
    detection = {
        "schema_version": EVALUATION.DETECTION_TERMINAL_SCHEMA,
        "run_status": "completed",
        "reference_accessed": False,
        "reference_argument_supported": False,
        "cases": [
            {
                "case_id": f"case_{index}",
                "document_sha256": pdf_sha,
                "page_number": 1,
                "terminal_status": "completed",
                "candidates": [
                    {
                        "candidate_id": "table_0",
                        "decision": "present",
                        "bbox_contract_valid": True,
                        "terminal_contract_error": None,
                        "detected_bbox": [0.1, 0.1, 0.9, 0.9],
                    }
                ],
            }
            for index in range(9)
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    detection_path = tmp_path / "detection.json"
    seal_path = tmp_path / "detection.sha256.json"
    manifest_path.write_bytes(EVALUATION.canonical_json_bytes(manifest))
    detection_bytes = EVALUATION.canonical_json_bytes(detection)
    detection_path.write_bytes(detection_bytes)
    seal_path.write_bytes(
        EVALUATION.canonical_json_bytes(
            {
                "schema_version": EVALUATION.DETECTION_SEAL_SCHEMA,
                "terminal_sha256": hashlib.sha256(detection_bytes).hexdigest(),
                "terminal_size_bytes": len(detection_bytes),
                "reference_accessed": False,
            }
        )
    )
    monkeypatch.setitem(sys.modules, "actual_corpus_test_config", ModuleType("cfg"))

    call_sizes: list[int] = []

    class Runtime:
        def run(self, candidates: list[dict]) -> SimpleNamespace:
            call_sizes.append(len(candidates))
            decisions = []
            for candidate in candidates:
                manifest_value = candidate["manifest"]
                decisions.append(
                    {
                        "source_lineage": {
                            "candidate_ref": manifest_value["candidate_ref"],
                            "source_sha256": manifest_value["pdf_sha256"],
                            "page_number": manifest_value["page_number"],
                            "crop_sha256": manifest_value["png_sha256"],
                            "crop_manifest_hash": manifest_value["manifest_hash"],
                            "dpi": manifest_value["dpi"],
                        }
                    }
                )
            return SimpleNamespace(
                safe_summary={"status": "completed", "decisions_total": len(decisions)},
                private_decisions=decisions,
            )

    class Factory:
        configs: list = []

        def __init__(self, config: object) -> None:
            self.configs.append(config)

        def create_for_openwebui(self, request: object) -> Runtime:
            assert request.app.state.config.__name__ == "cfg"
            return Runtime()

    terminal, _, identity = EVALUATION.run_actual_corpus(
        manifest_path=manifest_path,
        detection_terminal_path=detection_path,
        detection_seal_path=seal_path,
        corpus_root=corpus,
        output_dir=tmp_path / "run",
        source_revision="a" * 40,
        config_module="actual_corpus_test_config",
        gemini_model=EVALUATION.DEFAULT_GEMINI_MODEL,
        openai_model=EVALUATION.DEFAULT_OPENAI_MODEL,
        repeat_count=2,
        runtime_factory_builder=Factory,
    )

    assert call_sizes == [8, 1, 8, 1]
    assert len(Factory.configs) == 2
    assert all(config.maximum_candidates == 8 for config in Factory.configs)
    assert terminal["status"] == "completed"
    assert terminal["reference_accessed"] is False
    assert len(terminal["decision_records"]) == 18
    assert len(identity["units"]) == 9
    assert identity["provider_output_values_included"] is False


def test_factory_guard_prevents_parallel_provider_path() -> None:
    source = (SCRIPT_DIR / "evaluate_pdf_dual_vlm_actual_corpus.py").read_text(
        encoding="utf-8"
    )

    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
    assert "PdfDualVlmRuntimeFactory" in source
    assert ".create_for_openwebui(request)" in source
    assert "PdfTableRasterFactory" in source
    assert "PdfDualVlmFactProviderFactory" not in source
    assert "create_with_providers" not in source
    assert "urlopen(" not in source
