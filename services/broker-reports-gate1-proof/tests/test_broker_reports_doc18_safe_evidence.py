from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STAGE2 = ROOT / "docs" / "stage2"
REPORTS = ROOT / "docs" / "reports" / "2026-08-04"
SAFE_FILES = (
    STAGE2 / "BROKER_REPORTS_DOC18_PAGE_GROUNDING_CORPUS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC18_PAGE_GROUNDING_RESULTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC18_MODEL_COMPARISON.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC18_DOC17_COMPARISON.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC18_CALL_ACCOUNTING.safe.json",
    REPORTS / "BROKER_REPORTS_DOC18_PAGE_LEVEL_VLM_TABLE_REGION_GROUNDING.report.md",
    REPORTS / "BROKER_REPORTS_DOC18_PAGE_LEVEL_VLM_TABLE_REGION_GROUNDING_BRIEF.md",
)
RECEIPT = REPORTS / "BROKER_REPORTS_DOC18_PAGE_LEVEL_VLM_TABLE_REGION_GROUNDING.receipt.safe.json"
MODELS = {
    "gpt-5.4-mini-2026-03-17",
    "models/gemini-3.5-flash-lite",
    "claude-haiku-4-5-20251001",
    "claude-opus-5",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_doc18_frozen_corpus_has_required_generalization_classes():
    corpus = _load(SAFE_FILES[0])
    assert corpus["frozen_before_first_provider_call"] is True
    assert corpus["pages_total"] == 12
    assert corpus["documents_total"] >= 3
    assert corpus["issuers_total"] >= 3
    assert corpus["tables_total"] >= 18
    assert corpus["multi_table_pages_total"] >= 4
    assert corpus["borderless_tables_total"] >= 4
    assert corpus["title_or_caption_tables_total"] >= 4
    assert corpus["attached_note_tables_total"] >= 4
    assert corpus["near_page_boundary_tables_total"] >= 3
    assert corpus["no_table_pages_total"] >= 2
    assert set(corpus["model_ids"]) == MODELS
    assert corpus["mistral_calls_total"] == 0
    assert corpus["qwen_calls_total"] == 0


def test_doc18_call_accounting_is_terminal_and_one_attempt_only():
    accounting = _load(SAFE_FILES[4])
    assert accounting["expected_calls_total"] == 48
    assert accounting["accounted_calls_total"] == 48
    assert accounting["attempts_total"] == 48
    assert accounting["retry_total"] == 0
    assert accounting["fallback_total"] == 0
    assert accounting["best_of_total"] == 0
    assert accounting["repair_total"] == 0
    assert accounting["completed_total"] == 48
    assert accounting["structured_valid_total"] == 47
    assert accounting["failed_total"] == 0
    assert accounting["unaccounted_slots_total"] == 0
    assert set(accounting["by_model"].values()) == {12}
    assert accounting["by_provider"] == {"openai": 12, "google": 12, "anthropic": 24}


def test_doc18_result_preserves_negative_and_doc17_proof_boundaries():
    results = _load(SAFE_FILES[1])
    comparison = _load(SAFE_FILES[3])
    receipt = _load(RECEIPT)
    assert results["experiment"] == "COMPLETED"
    assert results["page_level_vlm_table_grounding"] == "INCONCLUSIVE"
    assert results["doc18_pass"] is False
    assert {item["model_id"] for item in results["models"].values()} == MODELS
    assert all(item["metrics"]["usable_table_crop_rate"] == 0 for item in results["models"].values())
    assert comparison["same_page_overlap_total"] == 6
    assert comparison["doc18_pages_total"] == 12
    assert comparison["full_corpus_comparison_available"] is False
    assert comparison["doc17_rerun"] is False
    assert comparison["doc17_policy_changed"] is False
    assert comparison["conclusion"] == "INCONCLUSIVE_FULL_CORPUS"
    assert receipt["DOC18_EXPERIMENT"] == "COMPLETED"
    assert receipt["PAGE_LEVEL_VLM_TABLE_GROUNDING"] == "INCONCLUSIVE"
    assert receipt["MULTI_PROVIDER_GROUNDING"] == "NOT_CONFIRMED"
    assert receipt["NEXT_STEP"] == "KEEP_DETERMINISTIC_CROPPER_RESEARCH"
    assert receipt["calls_accounted"] == "48/48"
    assert receipt["product_activation"] is False
    assert receipt["gate2_advanced"] is False


def test_doc18_receipt_binds_every_published_artifact():
    receipt = _load(RECEIPT)
    for path in SAFE_FILES:
        relative = path.relative_to(ROOT).as_posix()
        assert receipt["artifact_sha256"][relative] == _sha256(path)


def test_doc18_safe_artifacts_contain_no_private_payload_or_paths():
    forbidden = (
        "data:image/png;base64",
        "local/stage2",
        "C:\\Users",
        "D:\\Users",
        "raw_output",
        "provider_response_private",
        "bbox_normalized",
        "bbox_points",
        "candidate_bbox",
        "parser_text",
        "fragment_id",
    )
    for path in (*SAFE_FILES, RECEIPT):
        text = path.read_text(encoding="utf-8")
        assert all(token.lower() not in text.lower() for token in forbidden), path.name
