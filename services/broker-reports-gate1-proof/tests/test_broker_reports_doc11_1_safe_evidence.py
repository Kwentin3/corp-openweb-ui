from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "docs/stage2/BROKER_REPORTS_DOC11_1_MINIMAL_CONTEXT_RESULTS.safe.json"
ACCOUNTING = REPO / "docs/stage2/BROKER_REPORTS_DOC11_1_CALL_ACCOUNTING.safe.json"
REPORT = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC11_1_MINIMAL_CONTEXT_RERUN.report.md"
RECEIPT = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC11_1_MINIMAL_CONTEXT_RERUN.receipt.safe.json"
BRIEF = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC11_1_MINIMAL_CONTEXT_RERUN_BRIEF.md"
DOC11_AUDIT = REPO / "docs/stage2/BROKER_REPORTS_DOC11_MINIMAL_CONTEXT_AUDIT.safe.json"

MODELS = {
    "openai_mini": "gpt-5.4-mini-2026-03-17",
    "google_flash_lite": "models/gemini-3.5-flash-lite",
    "anthropic_haiku": "claude-haiku-4-5-20251001",
    "anthropic_opus": "claude-opus-5",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _integrity(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical({key: item for key, item in value.items() if key != "integrity_sha256"})).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    assert value["integrity_sha256"] == _integrity(value), path
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _walk(key)
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def test_doc11_1_safe_artifacts_have_integrity_and_no_private_payloads() -> None:
    payloads = [_load(path) for path in (RESULTS, ACCOUNTING, RECEIPT)]
    forbidden_keys = {
        "raw_output", "api_key", "request_body", "response_body",
        "fragment_private_map", "parser_inventory", "gold_rows",
    }
    for payload in payloads:
        strings = {str(value) for value in _walk(payload) if isinstance(value, str)}
        assert forbidden_keys.isdisjoint({value.lower() for value in strings})
        flattened = "\n".join(strings).lower()
        assert "local/stage2" not in flattened
        assert "authorization: bearer" not in flattened
        assert "48121a290" not in flattened
        assert "73,320,834" not in flattened
        assert "$1.17" not in flattened


def test_doc11_1_uses_exact_doc11_package_hashes_and_models() -> None:
    results = _load(RESULTS)
    doc11 = _load(DOC11_AUDIT)
    assert results["package_hash_verification"] == "PASSED"
    assert results["old_doc11_outputs_in_new_metrics"] is False
    assert results["source_doc11_protocol_sha256"] == doc11["protocol_sha256"]
    expected_hashes = {
        item["table_id"]: item["package_sha256"]
        for item in doc11["packages"]
    }
    actual_hashes = {
        f"doc11_table_{index:02d}": digest
        for index, digest in enumerate(results["source_doc11_package_hashes"].values(), start=1)
    }
    assert set(actual_hashes.values()) == set(expected_hashes.values())
    assert {key: value["requested_model_id"] for key, value in results["models"].items()} == MODELS
    assert all(value["availability"] == "AVAILABLE" for value in results["models"].values())


def test_doc11_1_all_sixteen_fresh_calls_have_confirmed_terminal_receipts() -> None:
    accounting = _load(ACCOUNTING)
    assert accounting["authorized_fresh_calls_total"] == 16
    assert accounting["slots_accounted_total"] == 16
    assert accounting["http_responses_total"] == 16
    assert accounting["interrupted_before_response_total"] == 0
    assert accounting["blocked_model_unavailable_total"] == 0
    assert accounting["retry_total"] == 0
    assert accounting["fallback_total"] == 0
    assert accounting["failed_tables_excluded_total"] == 0
    assert accounting["old_doc11_outputs_in_new_metrics"] is False
    assert accounting["terminal_statuses"] == {"COMPLETED": 16}
    assert accounting["http_statuses"] == {"200": 16}
    assert accounting["unfinished_slots"] == []
    calls = accounting["calls"]
    assert len(calls) == 16
    assert len({item["slot_id"] for item in calls}) == 16
    assert {(item["model_key"], item["table_id"]) for item in calls} == {
        (model, f"doc11_table_{index:02d}") for model in MODELS for index in range(1, 5)
    }
    assert all(item["http_status"] == 200 and item["terminal_status"] == "COMPLETED" for item in calls)
    assert all(item["attempts_total"] == 1 and item["retry_total"] == 0 for item in calls)
    assert all(item["image_count"] == 1 and item["request_started_at"] for item in calls)
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["raw_response_hash"]) for item in calls)
    assert all(item["input_tokens"] > 0 and item["output_tokens"] > 0 for item in calls)


def test_doc11_1_reports_raw_normalized_conservation_structure_and_economics() -> None:
    results = _load(RESULTS)
    expected = {
        "openai_mini": (1, 1, "FAILED", 0.14634146341463414, 0.0916030534351145, 0.25),
        "google_flash_lite": (2, 2, "FAILED", 0.3170731707317073, 0.6106870229007634, 0.25),
        "anthropic_haiku": (0, 0, "FAILED", 0.0, 0.0, 0.0),
        "anthropic_opus": (4, 4, "PASSED", 0.8536585365853658, 0.9541984732824428, 0.5),
    }
    for model, (raw, normalized, conservation, row, cell, exact) in expected.items():
        item = results["per_model"][model]
        assert item["CALLS_COMPLETED"] == "4/4"
        assert item["raw_valid_outputs"] == raw
        assert item["normalized_valid_outputs"] == normalized
        assert item["TEXT_CONSERVATION"] == conservation
        assert item["exact_row_recall"] == pytest.approx(row)
        assert item["exact_cell_recall"] == pytest.approx(cell)
        assert item["complete_table_exact_match_rate"] == exact
        assert item["average_cost_per_table_usd"] > 0
        assert item["average_latency_seconds"] > 0
        assert item["decision_eligible"] is True
    assert results["per_model"]["anthropic_opus"]["invented_occurrences"] == 0
    assert results["per_model"]["anthropic_opus"]["missing_occurrences"] == 0
    assert results["per_model"]["anthropic_opus"]["duplicated_occurrences"] == 0
    assert results["overall_economics"]["estimated_cost_usd_total"] == pytest.approx(0.2321667)


def test_doc11_1_exact_tables_errors_and_threshold_decision_are_explicit() -> None:
    results = _load(RESULTS)
    exact = {(item["table_id"], item["model_key"]) for item in results["fully_reconstructed_tables"]}
    assert exact == {
        ("doc11_table_01", "anthropic_opus"),
        ("doc11_table_02", "anthropic_opus"),
        ("doc11_table_02", "google_flash_lite"),
        ("doc11_table_02", "openai_mini"),
    }
    assert results["per_model"]["openai_mini"]["error_outcomes"] == {
        "EXACT": 1, "ROWS_OR_UNRESOLVED_INVALID": 1, "TEXT_MULTISET_INVALID": 1, "JSON_PARSE_ERROR": 1,
    }
    assert results["per_model"]["google_flash_lite"]["error_outcomes"] == {
        "EXACT": 1, "STRUCTURE_NOT_EXACT": 1, "TEXT_MULTISET_INVALID": 2,
    }
    assert results["per_model"]["anthropic_haiku"]["error_outcomes"] == {
        "CELL_INVALID": 1, "TEXT_MULTISET_INVALID": 3,
    }
    assert results["per_model"]["anthropic_opus"]["error_outcomes"] == {
        "EXACT": 2, "STRUCTURE_NOT_EXACT": 2,
    }
    assert not any(results["per_model"][model]["promising_cheap_threshold_passed"] for model in ("openai_mini", "google_flash_lite", "anthropic_haiku"))


def test_doc11_1_historical_comparison_and_terminal_classifications_are_consistent() -> None:
    results = _load(RESULTS)
    history = results["historical_doc10_comparison"]
    assert history["openai_mini"]["structure_quality_effect"] == "POSITIVE"
    assert history["openai_mini"]["overload_reduced"] is False
    assert history["google_flash_lite"]["structure_quality_effect"] == "POSITIVE"
    assert history["google_flash_lite"]["overload_reduced"] is True
    assert history["anthropic_haiku"]["structure_quality_effect"] == "NO_MEANINGFUL_EFFECT"
    assert history["anthropic_haiku"]["overload_reduced"] is True
    assert history["anthropic_opus"]["historical_doc10_match"] is False
    assert results["classifications"] == {
        "DOC11_1_EXPERIMENT": "COMPLETED",
        "PLAIN_TEXT_CONTEXT_REDUCES_OVERLOAD": "INCONCLUSIVE",
        "PLAIN_TEXT_CONTEXT_IMPROVES_STRUCTURE": "CONFIRMED",
        "BEST_CHEAP_MODEL": "NONE",
        "BEST_REFERENCE_MODEL": "anthropic_opus",
        "MINIMAL_CONTEXT_PROJECTION": "NOT_CONFIRMED",
    }


def test_doc11_1_receipt_binds_outputs_and_unchanged_product_sources() -> None:
    results = _load(RESULTS)
    accounting = _load(ACCOUNTING)
    receipt = _load(RECEIPT)
    assert receipt["results_safe_sha256"] == results["integrity_sha256"]
    assert receipt["call_accounting_safe_sha256"] == accounting["integrity_sha256"]
    assert receipt["authorized_fresh_calls_total"] == receipt["http_responses_total"] == 16
    assert receipt["retry_total"] == receipt["fallback_total"] == 0
    assert receipt["old_doc11_outputs_in_new_metrics"] is False
    assert receipt["parser_changed"] is False
    assert receipt["doc6_changed"] is False
    assert receipt["product_pipeline_changed"] is False
    assert receipt["model_activated"] is False
    for relative, expected in receipt["frozen_product_source_sha256"].items():
        assert _sha(REPO / relative) == expected
    parser_source = (REPO / "services/broker-reports-gate1-proof/broker_reports_gate1/pdf_text_layer.py").read_text(encoding="utf-8")
    assert "FACTORY_REQUIRED" in parser_source
    assert "FORBIDDEN" in parser_source


def test_doc11_1_report_and_brief_are_bom_encoded_and_terminal() -> None:
    assert REPORT.read_bytes().startswith(b"\xef\xbb\xbf")
    assert BRIEF.read_bytes().startswith(b"\xef\xbb\xbf")
    report = REPORT.read_text(encoding="utf-8-sig")
    brief = BRIEF.read_text(encoding="utf-8-sig")
    for marker in (
        "DOC11_1_EXPERIMENT = COMPLETED",
        "PLAIN_TEXT_CONTEXT_REDUCES_OVERLOAD = INCONCLUSIVE",
        "PLAIN_TEXT_CONTEXT_IMPROVES_STRUCTURE = CONFIRMED",
        "BEST_CHEAP_MODEL = NONE",
        "| `BEST_REFERENCE_MODEL` | `anthropic_opus` |",
        "MINIMAL_CONTEXT_PROJECTION = NOT_CONFIRMED",
        "16/16",
        "Parser, DOC6, product pipeline",
    ):
        assert marker in report
    assert "16/16 fresh calls" in brief
    assert "NOT_CONFIRMED" in brief
