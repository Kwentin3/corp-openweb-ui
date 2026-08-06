from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "docs/stage2"
REPORTS = REPO / "docs/reports/2026-08-03"

CORPUS = STAGE / "BROKER_REPORTS_DOC15_HOLDOUT_CORPUS.safe.json"
RESULTS = STAGE / "BROKER_REPORTS_DOC15_PROVIDER_RESULTS.safe.json"
EFFECT = STAGE / "BROKER_REPORTS_DOC15_SOURCE_TEXT_EFFECT.safe.json"
EXIT = STAGE / "BROKER_REPORTS_DOC15_GATE1_EXIT.safe.json"
OPTIMIZATION = STAGE / "BROKER_REPORTS_DOC15_OPTIMIZATION_REVIEW.safe.json"
ACCOUNTING = STAGE / "BROKER_REPORTS_DOC15_CALL_ACCOUNTING.safe.json"
REPORT = REPORTS / "BROKER_REPORTS_DOC15_REAL_REPORTS_HOLDOUT.report.md"
BRIEF = REPORTS / "BROKER_REPORTS_DOC15_REAL_REPORTS_HOLDOUT_BRIEF.md"
RECEIPT = REPORTS / "BROKER_REPORTS_DOC15_REAL_REPORTS_HOLDOUT.receipt.safe.json"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    expected = value["integrity_sha256"]
    actual = hashlib.sha256(_canonical({key: item for key, item in value.items() if key != "integrity_sha256"})).hexdigest()
    assert actual == expected
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk_keys(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def test_doc15_holdout_is_real_frozen_and_nonoverlapping() -> None:
    corpus = _read(CORPUS)
    assert corpus["real_broker_reports_total"] == 6
    assert corpus["brokers_or_issuers_total"] == 6
    assert corpus["holdout_tables_total"] == 24
    assert len({item["source_sha256"] for item in corpus["documents"]}) == 6
    assert len({item["table_id"] for item in corpus["tables"]}) == 24
    assert corpus["overlap_audit"]["current_hash_overlap_total"] == 0
    assert corpus["overlap_audit"]["holdout_nonoverlap_confirmed"] is True
    assert corpus["corpus_frozen_before_calls"] is True
    assert corpus["visual_gold_frozen_before_calls"] is True
    assert corpus["prompt_frozen_before_calls"] is True
    assert corpus["schema_frozen_before_calls"] is True
    assert corpus["thresholds_frozen_before_calls"] is True
    assert corpus["evaluator_frozen_before_calls"] is True


def test_doc15_all_192_slots_are_terminal_and_one_attempt() -> None:
    accounting = _read(ACCOUNTING)
    assert accounting["slots_expected_total"] == 192
    assert accounting["starts_total"] == 192
    assert accounting["slots_accounted_total"] == 192
    assert accounting["provider_completed_total"] == 190
    assert accounting["failed_total"] == 2
    assert accounting["attempts_total"] == 192
    assert accounting["retry_total"] == 0
    assert accounting["fallback_total"] == 0
    assert accounting["best_of_total"] == 0
    assert accounting["repair_total"] == 0
    assert accounting["structured_output_calls_total"] == 192
    assert accounting["unaccounted_slot_ids"] == []
    assert accounting["all_calls_accounted"] is True
    assert accounting["failed_tables_excluded_total"] == 0
    assert accounting["terminal_status_counts"] == {"COMPLETED": 190, "FAILED": 2}
    assert accounting["by_provider"] == {"openai": 48, "google": 48, "anthropic": 96}


def test_doc15_reports_structure_but_does_not_overstate_gate_exit() -> None:
    results = _read(RESULTS)
    gate = _read(EXIT)
    for key in ("openai_mini", "google_flash_lite", "anthropic_haiku"):
        for arm in ("IMAGE_ONLY", "IMAGE_PLUS_SOURCE_TEXT"):
            assert results["per_model_arm"][key][arm]["normalized_json_validity"] == 1.0
    assert results["per_model_arm"]["anthropic_opus"]["IMAGE_ONLY"]["normalized_json_validity"] == 1.0
    assert results["per_model_arm"]["anthropic_opus"]["IMAGE_PLUS_SOURCE_TEXT"]["normalized_json_valid_total"] == 22
    assert all(results["per_model_arm"][key]["IMAGE_PLUS_SOURCE_TEXT"]["provider_pass"] is False for key in results["per_model_arm"])
    assert gate["passed_models"] == []
    assert gate["passed_providers"] == []
    assert gate["cheap_passed_models"] == []
    assert gate["multi_provider_readiness"] is False
    assert gate["GATE1_EXIT"] == "NOT_CONFIRMED"
    assert gate["pipeline_activated"] is False
    assert gate["gate2_started"] is False


def test_doc15_source_text_effect_and_bootstrap_are_explicit() -> None:
    effect = _read(EFFECT)
    assert effect["SOURCE_TEXT_EFFECT"] == "INCONCLUSIVE"
    assert effect["paired_tables_total"] == 24
    assert effect["bootstrap_resamples"] == 10000
    assert effect["hidden_weighted_score_used"] is False
    for model in effect["models"].values():
        assert model["SOURCE_TEXT_EFFECT"] == "INCONCLUSIVE"
        if model["decision_eligible"]:
            assert set(model["paired_bootstrap_24_tables"]) == {
                "critical_value_recall", "unsupported_values", "row_association_accuracy",
                "column_association_accuracy", "header_accuracy", "complete_table_exact_rate",
                "cost_per_table_usd", "latency_per_table_seconds",
            }
        else:
            assert model["paired_bootstrap_24_tables"] == {}


def test_doc15_optimization_review_is_diagnostic_only() -> None:
    optimization = _read(OPTIMIZATION)
    assert optimization["optimization_review_completed"] is True
    assert optimization["optimizations_applied_during_run"] == 0
    assert len(optimization["optimizations"]) >= 6
    assert all(item["decision"] != "APPLIED" for item in optimization["optimizations"])


def test_doc15_receipt_binds_safe_artifacts_and_stop_boundary() -> None:
    receipt = _read(RECEIPT)
    assert receipt["DOC15_EXPERIMENT"] == "COMPLETED"
    assert receipt["SOURCE_TEXT_EFFECT"] == "INCONCLUSIVE"
    assert receipt["PASSED_PROVIDERS"] == []
    assert receipt["GATE1_EXIT"] == "NOT_CONFIRMED"
    acceptance = receipt["acceptance"]
    assert acceptance["ALL_CALLS_ACCOUNTED"] is True
    assert acceptance["RETRY_TOTAL"] == 0
    assert acceptance["FAILED_TABLES_EXCLUDED_TOTAL"] == 0
    assert acceptance["OPTIMIZATIONS_APPLIED_DURING_RUN"] == 0
    assert acceptance["PARSER_PRODUCT_CODE_CHANGED"] is False
    assert acceptance["DOC6_CHANGED"] is False
    assert acceptance["PRODUCT_PIPELINE_CHANGED"] is False
    assert acceptance["GATE2_IMPLEMENTED"] is False
    by_name = {path.name: path for path in (CORPUS, RESULTS, EFFECT, EXIT, OPTIMIZATION, ACCOUNTING, REPORT, BRIEF)}
    for name, expected in receipt["safe_artifact_sha256"].items():
        assert _sha(by_name[name]) == expected
    assert REPORT.read_bytes().startswith(b"\xef\xbb\xbf")
    assert BRIEF.read_bytes().startswith(b"\xef\xbb\xbf")


def test_doc15_public_evidence_contains_no_table_or_provider_payloads() -> None:
    json_paths = (CORPUS, RESULTS, EFFECT, EXIT, OPTIMIZATION, ACCOUNTING, RECEIPT)
    forbidden_keys = {"raw_output", "provider_response_private", "request", "response", "gold", "normalized_output", "bbox", "candidate_bbox", "header", "rows", "title"}
    forbidden_text = ("data:image/png;base64", "local/stage2", "C:\\Users", "D:\\Users", "OPENAI_API_KEYS")
    for path in json_paths:
        value = _read(path)
        assert not forbidden_keys.intersection(_walk_keys(value))
        rendered = path.read_text(encoding="utf-8-sig")
        assert not any(marker.lower() in rendered.lower() for marker in forbidden_text)
    for path in (REPORT, BRIEF):
        rendered = path.read_text(encoding="utf-8-sig")
        assert not re.search(r"[A-Za-z]:\\Users\\", rendered, flags=re.IGNORECASE)
        assert "data:image/png;base64" not in rendered
