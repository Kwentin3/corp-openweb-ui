from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[3]
AUDIT_PATH = REPO / "docs/stage2/BROKER_REPORTS_DOC10_CONTEXT_PACKAGE_AUDIT.safe.json"
RESULTS_PATH = REPO / "docs/stage2/BROKER_REPORTS_DOC10_THREE_ARM_RESULTS.safe.json"
PRICE_PATH = REPO / "docs/stage2/BROKER_REPORTS_DOC10_CONTEXT_PRICE_QUALITY.safe.json"
REPORT_PATH = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC10_LLM_FRIENDLY_CONTEXT_AUDIT.report.md"
RECEIPT_PATH = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC10_LLM_FRIENDLY_CONTEXT_AUDIT.receipt.safe.json"
BRIEF_PATH = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC10_LLM_FRIENDLY_CONTEXT_AUDIT_BRIEF.md"

ARMS = {"DOC9_BASELINE", "ONE_IMAGE_LONG_IDS", "ONE_IMAGE_SHORT_IDS"}
MODELS = {
    "openai_nano": "gpt-5.4-nano-2026-03-17",
    "openai_mini": "gpt-5.4-mini-2026-03-17",
    "google_31_flash_lite": "models/gemini-3.1-flash-lite",
    "google_35_flash_lite": "models/gemini-3.5-flash-lite",
    "anthropic_haiku_45": "claude-haiku-4-5-20251001",
    "anthropic_sonnet_5": "claude-sonnet-5",
}
TABLES = {
    "unseen_pdf_03_t01",
    "unseen_pdf_01_t04",
    "unseen_pdf_06_t03",
    "unseen_pdf_06_t07",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _integrity(value: dict[str, Any]) -> str:
    payload = dict(value)
    payload.pop("integrity_sha256", None)
    return hashlib.sha256(_canonical(payload)).hexdigest()


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


def test_doc10_safe_payload_integrity_and_privacy_boundary() -> None:
    payloads = [_load(path) for path in (AUDIT_PATH, RESULTS_PATH, PRICE_PATH, RECEIPT_PATH)]
    forbidden_keys = {"raw_output", "api_key", "request_body", "response_body", "fragment_private_map", "mapping"}
    for payload in payloads:
        keys = {str(value).lower() for value in _walk(payload) if isinstance(value, str)}
        assert forbidden_keys.isdisjoint(keys)
        for value in keys:
            assert "local/stage2" not in value
            assert ".env" not in value
            assert "authorization: bearer" not in value


def test_doc10_all_twelve_visual_and_fragment_packages_are_audited() -> None:
    audit = _load(AUDIT_PATH)
    assert audit["context_package_audit_completed"] is True
    assert audit["all_12_doc9_packages_audited"] is True
    assert audit["agent_visual_reviewed_original_and_id_map_total"] == 12
    assert len(audit["tables"]) == 12
    assert all(item["visual"]["agent_opened_original_and_id_map"] for item in audit["tables"])
    aggregate = audit["aggregate"]
    assert aggregate["tables_total"] == 12
    assert aggregate["fragments_total"] == sum(item["fragment_inventory"]["fragments_total"] for item in audit["tables"])
    assert aggregate["fragments_total"] == 1039
    assert aggregate["id_label_overlap_pair_total"] > 0
    assert aggregate["id_label_source_text_overlap_label_total"] > 0
    assert aggregate["id_label_table_line_overlap_total"] > 0
    assert aggregate["doc9_context_overloaded"] is True
    assert aggregate["long_ids_average_characters"] == 10.0


def test_doc10_twelve_selected_arm_packages_are_frozen_and_isolated() -> None:
    audit = _load(AUDIT_PATH)
    hashes = audit["doc10_package_hashes"]
    assert set(hashes) == TABLES
    assert all(set(value) == ARMS for value in hashes.values())
    assert len({digest for value in hashes.values() for digest in value.values()}) == 12
    workloads = audit["selected_package_workloads"]
    assert len(workloads) == 12
    assert {(item["gold_table_id"], item["arm"]) for item in workloads} == {(table, arm) for table in TABLES for arm in ARMS}
    assert all(item["image_count"] == (2 if item["arm"] == "DOC9_BASELINE" else 1) for item in workloads)
    for table in TABLES:
        by_arm = {item["arm"]: item for item in workloads if item["gold_table_id"] == table}
        assert by_arm["ONE_IMAGE_LONG_IDS"]["image_bytes"] == by_arm["ONE_IMAGE_SHORT_IDS"]["image_bytes"]
        assert by_arm["ONE_IMAGE_SHORT_IDS"]["inventory_tokens_pre_call_estimate"]["openai_o200k_base"] < by_arm["ONE_IMAGE_LONG_IDS"]["inventory_tokens_pre_call_estimate"]["openai_o200k_base"]


def test_doc10_model_discovery_prices_and_google_replacement_are_explicit() -> None:
    results = _load(RESULTS_PATH)
    assert {key: value["requested_model_id"] for key, value in results["models"].items()} == MODELS
    assert all(value["resolved_model_id"] == value["requested_model_id"] for value in results["models"].values())
    assert all(value["image_support"] is True and value["models_api_http_status"] == 200 for value in results["models"].values())
    assert results["models"]["openai_nano"]["input_usd_per_million"] == 0.2
    assert results["models"]["openai_mini"]["output_usd_per_million"] == 4.5
    assert results["models"]["google_31_flash_lite"]["input_usd_per_million"] == 0.25
    assert results["models"]["google_35_flash_lite"]["output_usd_per_million"] == 2.5
    assert results["models"]["anthropic_haiku_45"]["output_usd_per_million"] == 5.0
    assert results["models"]["anthropic_sonnet_5"]["input_usd_per_million"] == 2.0
    assert "HTTP 404" in results["models"]["google_31_flash_lite"]["doc9_replacement"]


def test_doc10_all_72_calls_have_terminal_observable_accounting() -> None:
    results = _load(RESULTS_PATH)
    assert results["calls_total"] == results["expected_calls_total"] == 72
    assert results["one_attempt_each"] is True
    assert results["retry_total"] == 0
    assert sum(results["terminal_statuses"].values()) == 72
    assert sum(results["http_statuses"].values()) == 72
    assert results["http_statuses"] == {"200": 72}
    per_table = results["per_table"]
    assert len(per_table) == 72
    assert len({(item["gold_table_id"], item["model_key"], item["arm"]) for item in per_table}) == 72
    assert {item["gold_table_id"] for item in per_table} == TABLES
    assert {item["arm"] for item in per_table} == ARMS
    assert {item["model_key"] for item in per_table} == set(MODELS)


def test_doc10_raw_normalized_structure_and_economics_are_separate() -> None:
    results = _load(RESULTS_PATH)
    assert set(results["arm_aggregates"]) == ARMS
    assert len(results["model_arm_aggregates"]) == 18
    for item in results["model_arm_aggregates"].values():
        assert item["tables_total"] == 4
        assert item["normalized_valid_outputs"] >= item["raw_valid_outputs"]
        assert 0 <= item["exact_row_recall"] <= 1
        assert 0 <= item["exact_cell_group_recall"] <= 1
        assert 0 <= item["token_placement_accuracy"] <= 1
        assert item["average_cost_per_table_usd"] >= 0
        assert item["average_latency_seconds"] >= 0
    for item in results["arm_aggregates"].values():
        assert item["tables_total"] == 24
        assert item["normalized_valid_outputs"] >= item["raw_valid_outputs"]
    assert results["arm_aggregates"]["DOC9_BASELINE"]["normalized_valid_outputs"] == 7
    assert results["arm_aggregates"]["ONE_IMAGE_LONG_IDS"]["normalized_valid_outputs"] == 5
    assert results["arm_aggregates"]["ONE_IMAGE_SHORT_IDS"]["normalized_valid_outputs"] == 5


def test_doc10_effects_and_terminal_classifications_have_no_hidden_winner() -> None:
    results = _load(RESULTS_PATH)
    assert results["second_id_image_effect"]["classification"] == "MODEL_DEPENDENT"
    assert results["short_id_effect"]["classification"] == "MODEL_DEPENDENT"
    assert set(results["second_id_image_effect"]["per_model"]) == set(MODELS)
    assert set(results["short_id_effect"]["per_model"]) == set(MODELS)
    classifications = results["classifications"]
    assert classifications == {
        "DOC10_EXPERIMENT": "COMPLETED",
        "SECOND_ID_IMAGE_NEEDED": "MODEL_DEPENDENT",
        "SHORT_IDS_IMPROVE_RESULTS": "MODEL_DEPENDENT",
        "BEST_CONTEXT_PACKAGE": "NO_CLEAR_WINNER",
        "LLM_FRIENDLY_CONTEXT_PROJECTION": "NOT_CONFIRMED",
        "BEST_CHEAP_MODEL": None,
    }
    assert not any(item["llm_friendly_threshold_passed"] for item in results["model_arm_aggregates"].values())
    exact = results["fully_reconstructed_tables"]
    assert len(exact) == 9
    assert {item["gold_table_id"] for item in exact} == {"unseen_pdf_03_t01", "unseen_pdf_01_t04"}
    assert all(item["gold_table_id"] not in {"unseen_pdf_06_t03", "unseen_pdf_06_t07"} for item in exact)


def test_doc10_price_quality_totals_match_results_without_weighted_score() -> None:
    results = _load(RESULTS_PATH)
    price = _load(PRICE_PATH)
    assert price["selection_policy"] == "separate metrics and Pareto dominance; no weighted score"
    assert price["best_context_package"] == "NO_CLEAR_WINNER"
    assert price["best_cheap_model"] is None
    assert len(price["model_arm_price_quality"]) == 18
    assert price["total_experiment_cost_usd"] == pytest.approx(results["total_experiment_cost_usd"], abs=1e-9)
    assert results["total_experiment_cost_usd"] == pytest.approx(sum(item["estimated_cost_usd"] for item in results["per_table"]), abs=1e-9)
    assert price["arm_price_quality"]["ONE_IMAGE_SHORT_IDS"]["estimated_cost_usd_total"] < price["arm_price_quality"]["ONE_IMAGE_LONG_IDS"]["estimated_cost_usd_total"] < price["arm_price_quality"]["DOC9_BASELINE"]["estimated_cost_usd_total"]


def test_doc10_receipt_hashes_sources_and_stop_boundary_are_current() -> None:
    receipt = _load(RECEIPT_PATH)
    assert receipt["calls_total"] == 72
    assert receipt["package_hash_parity"] == "PASSED"
    assert receipt["prompt_changed_during_run"] is False
    assert receipt["parser_changed"] is False
    assert receipt["doc6_changed"] is False
    assert receipt["failed_tables_excluded_total"] == 0
    assert receipt["product_pipeline_implemented"] is False
    assert receipt["model_activated"] is False
    for relative, expected in receipt["safe_artifact_sha256"].items():
        assert _sha(REPO / relative) == expected
    for relative, expected in receipt["frozen_product_source_sha256"].items():
        assert _sha(REPO / relative) == expected
    parser_source = (REPO / "services/broker-reports-gate1-proof/broker_reports_gate1/pdf_text_layer.py").read_text(encoding="utf-8")
    assert "FACTORY_REQUIRED" in parser_source
    assert "FORBIDDEN" in parser_source


def test_doc10_report_and_brief_are_utf8_bom_and_terminal() -> None:
    assert REPORT_PATH.read_bytes().startswith(b"\xef\xbb\xbf")
    assert BRIEF_PATH.read_bytes().startswith(b"\xef\xbb\xbf")
    report = REPORT_PATH.read_text(encoding="utf-8-sig")
    brief = BRIEF_PATH.read_text(encoding="utf-8-sig")
    for marker in (
        "DOC10_EXPERIMENT = COMPLETED",
        "SECOND_ID_IMAGE_NEEDED = MODEL_DEPENDENT",
        "SHORT_IDS_IMPROVE_RESULTS = MODEL_DEPENDENT",
        "BEST_CONTEXT_PACKAGE = NO_CLEAR_WINNER",
        "LLM_FRIENDLY_CONTEXT_PROJECTION = NOT_CONFIRMED",
        "BEST_CHEAP_MODEL = NONE",
        "product pipeline не реализован",
    ):
        assert marker in report
    assert "Product pipeline и activation не выполнялись" in brief
