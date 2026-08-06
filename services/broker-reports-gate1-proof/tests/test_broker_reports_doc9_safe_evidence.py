from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STAGE2 = REPO / "docs/stage2"
REPORTS = REPO / "docs/reports/2026-08-03"
AUDIT_PATH = STAGE2 / "BROKER_REPORTS_DOC9_PARSER_LEXICAL_AUDIT.safe.json"
MATRIX_PATH = STAGE2 / "BROKER_REPORTS_DOC9_MODEL_MATRIX.safe.json"
FRONTIER_PATH = STAGE2 / "BROKER_REPORTS_DOC9_PRICE_QUALITY_FRONTIER.safe.json"
RECEIPT_PATH = REPORTS / "BROKER_REPORTS_DOC9_PARSER_AND_CHEAP_MODEL_BENCHMARK.receipt.safe.json"
REPORT_PATH = REPORTS / "BROKER_REPORTS_DOC9_PARSER_AND_CHEAP_MODEL_BENCHMARK.report.md"
BRIEF_PATH = REPORTS / "BROKER_REPORTS_DOC9_PARSER_AND_CHEAP_MODEL_BENCHMARK_BRIEF.md"
JSON_PATHS = (AUDIT_PATH, MATRIX_PATH, FRONTIER_PATH, RECEIPT_PATH)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha(payload: dict) -> str:
    material = {key: value for key, value in payload.items() if key != "integrity_sha256"}
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_doc9_safe_json_integrity_and_privacy_boundary() -> None:
    forbidden = (
        "private://",
        "raw_output",
        "ledger_entries",
        "fragment_private_map",
        '"bbox"',
        "local/stage2",
        "\\local\\stage2\\",
        "d:\\users\\",
        "c:\\users\\",
        "api_key",
        "billing_identifier",
    )
    for path in JSON_PATHS:
        payload = _read(path)
        assert payload["integrity_sha256"] == _canonical_sha(payload)
        assert payload.get("private_values_included") is False
        lowered = path.read_text(encoding="utf-8").lower()
        assert not any(value in lowered for value in forbidden)


def test_doc9_all_historical_gaps_have_one_proven_classification() -> None:
    audit = _read(AUDIT_PATH)
    assert audit["status"] == "COMPLETED"
    assert audit["doc8_gap_totals"] == {"missing": 486, "extra": 119}
    assert audit["doc8_missing_cause_distribution"] == {
        "CROP_BOUNDARY_ERROR": 8,
        "GOLD_MAPPING_ERROR": 10,
        "PARSER_MERGED_MULTIPLE_VISUAL_TOKENS": 468,
    }
    assert audit["doc8_extra_cause_distribution"] == {
        "DECORATIVE_OR_NONCONTENT_TEXT": 8,
        "GOLD_MAPPING_ERROR": 4,
        "PARSER_MERGED_MULTIPLE_VISUAL_TOKENS": 107,
    }
    assert audit["all_doc8_fragment_gaps_classified"] is True
    assert sum(audit["doc8_missing_cause_distribution"].values()) == 486
    assert sum(audit["doc8_extra_cause_distribution"].values()) == 119


def test_doc9_corrected_lexical_coverage_and_structure_neutrality_are_exact() -> None:
    audit = _read(AUDIT_PATH)
    assert audit["corrected_coverage"] == {
        "visible_normalized_characters_total": 5875,
        "parser_covered_normalized_characters": 5875,
        "truly_missing_normalized_characters": 0,
        "visible_lexical_tokens_total": 1072,
        "parser_covered_lexical_tokens": 1072,
        "truly_missing_lexical_tokens": 0,
        "visible_numeric_values_total": 319,
        "parser_covered_numeric_values": 319,
        "visible_currency_markers_total": 43,
        "parser_covered_currency_markers": 43,
        "visible_dates_total": 16,
        "parser_covered_dates": 16,
        "CRITICAL_NUMERIC_VALUE_COVERAGE": 1.0,
    }
    changes = audit["lexical_only_changes"]
    assert changes["projection_name"] == "Structure-Neutral Lexical Projection v1"
    assert (changes["word_x_tolerance_before"], changes["word_x_tolerance_after"]) == (3.0, 0.5)
    assert changes["row_column_grid_or_reading_order_added"] is False
    assert audit["model_inventory_fields"] == ["id", "text"]
    assert all(value == 0 for key, value in audit["structure_neutrality"].items() if key.endswith("_total"))
    assert audit["structure_neutrality"]["gold_used_as_model_input"] is False


def test_doc9_canonical_packages_are_the_exact_doc8_twelve_with_hash_parity() -> None:
    audit = _read(AUDIT_PATH)
    assert audit["canonical_input_packages_total"] == 12
    assert audit["input_package_hash_parity"] == "PASSED"
    assert [item["gold_table_id"] for item in audit["tables"]] == [
        "unseen_pdf_03_t01", "unseen_pdf_02_t05", "unseen_pdf_01_t04", "unseen_pdf_06_t25",
        "unseen_pdf_06_t03", "unseen_pdf_06_t35", "unseen_pdf_06_t27", "unseen_pdf_06_t09",
        "unseen_pdf_06_t05", "unseen_pdf_01_t01", "unseen_pdf_06_t07", "unseen_pdf_01_t05",
    ]
    assert sum(item["canonical_parser_fragments_total"] for item in audit["tables"]) == 1039
    assert sum(item["evaluator_resolved_fragments_total"] for item in audit["tables"]) == 943
    assert sum(item["evaluator_unresolved_fragments_total"] for item in audit["tables"]) == 0
    assert sum(item["visible_non_table_fragments_total"] for item in audit["tables"]) == 96
    assert len({item["canonical_input_package_sha256"] for item in audit["tables"]}) == 12


def test_doc9_six_frozen_models_ids_stability_and_prices_are_exact() -> None:
    models = _read(MATRIX_PATH)["models"]
    expected = {
        "openai_nano": ("gpt-5.4-nano-2026-03-17", "snapshot", 0.20, 1.25),
        "openai_mini": ("gpt-5.4-mini-2026-03-17", "snapshot", 0.75, 4.50),
        "google_25_flash_lite": ("models/gemini-2.5-flash-lite", "stable_concrete_id", 0.10, 0.40),
        "google_35_flash_lite": ("models/gemini-3.5-flash-lite", "stable_concrete_id", 0.30, 2.50),
        "anthropic_haiku_45": ("claude-haiku-4-5-20251001", "dated_snapshot", 1.00, 5.00),
        "anthropic_sonnet_5": ("claude-sonnet-5", "dateless_pinned_snapshot", 2.00, 10.00),
    }
    assert set(models) == set(expected)
    for key, (model_id, stability, input_price, output_price) in expected.items():
        value = models[key]
        assert value["requested_model_id"] == model_id
        assert value["stability"] == stability
        assert value["input_usd_per_million_tokens"] == input_price
        assert value["output_usd_per_million_tokens"] == output_price
        assert value["availability_at_freeze"] == "AVAILABLE"
        assert value["models_api_http_status"] == 200
        assert value["image_input_capability"] is True
        assert value["fallback_used"] is False


def test_doc9_all_72_one_attempt_calls_and_terminal_differences_are_preserved() -> None:
    matrix = _read(MATRIX_PATH)
    assert matrix["calls_total"] == 72
    accounting = matrix["call_accounting"]
    assert all(value["calls_total"] == value["attempts_total"] == 12 for value in accounting.values())
    assert all(value["component_hash_parity_failures_total"] == 0 for value in accounting.values())
    assert accounting["google_25_flash_lite"]["http_statuses"] == {"404": 12}
    assert accounting["google_25_flash_lite"]["terminal_statuses"] == {"FAILED": 12}
    assert accounting["google_35_flash_lite"]["strict_response_shapes"] == {"FENCED_JSON": 12}
    assert accounting["anthropic_haiku_45"]["strict_response_shapes"] == {"FENCED_JSON": 12}
    assert accounting["anthropic_sonnet_5"]["strict_response_shapes"] == {
        "EMPTY_OUTPUT": 3,
        "FENCED_JSON": 4,
        "JSON_PARSE_ERROR": 1,
        "STRICT_JSON_PARSED": 4,
    }


def test_doc9_quality_metrics_reject_every_model_without_hiding_partial_exact_tables() -> None:
    aggregates = _read(MATRIX_PATH)["aggregates"]
    expected = {
        "openai_nano": (0, 12, 17, 710, 54, 1, 27, 4, 0),
        "openai_mini": (1, 11, 11, 717, 40, 12, 71, 62, 1),
        "google_25_flash_lite": (0, 12, 0, 1039, 0, 0, 0, 0, 0),
        "google_35_flash_lite": (0, 12, 0, 1039, 0, 0, 0, 0, 0),
        "anthropic_haiku_45": (0, 12, 0, 1039, 0, 0, 0, 0, 0),
        "anthropic_sonnet_5": (3, 9, 0, 961, 0, 14, 40, 78, 2),
    }
    for key, values in expected.items():
        actual = aggregates[key]
        assert (
            actual["valid_outputs_total"], actual["invalid_outputs_total"], actual["invented_ids"],
            actual["missing_ids"], actual["duplicated_ids"], actual["matched_rows_total"],
            actual["exact_cell_groups_matched"], actual["tokens_correctly_placed"],
            actual["complete_table_exact_matches"],
        ) == values
        assert actual["gold_rows_total"] == 130
        assert actual["gold_cells_total"] == 413
        assert actual["tokens_expected"] == 943
        assert actual["candidate_status"] == "REJECTED_INVALID_OUTPUT"


def test_doc9_costs_exact_tables_frontier_and_terminal_classifications_are_closed() -> None:
    matrix = _read(MATRIX_PATH)
    frontier = _read(FRONTIER_PATH)
    costs = {key: value["estimated_cost_usd_total"] for key, value in matrix["aggregates"].items()}
    assert costs == {
        "openai_nano": 0.0192461,
        "openai_mini": 0.06866325,
        "google_25_flash_lite": 0.0,
        "google_35_flash_lite": 0.0681569,
        "anthropic_haiku_45": 0.126318,
        "anthropic_sonnet_5": 0.622168,
    }
    assert frontier["fully_exact_tables"]["openai_mini"] == ["unseen_pdf_01_t05"]
    assert frontier["fully_exact_tables"]["anthropic_sonnet_5"] == ["unseen_pdf_01_t04", "unseen_pdf_02_t05"]
    assert frontier["usable_candidate_pareto_frontier"] == []
    assert set(frontier["raw_mathematical_pareto_frontier"]) == {
        "anthropic_sonnet_5", "google_25_flash_lite", "openai_mini", "openai_nano"
    }
    assert matrix["classifications"] == {
        "DOC9_EXPERIMENT": "COMPLETED",
        "PARSER_LEXICAL_PROJECTION": "SUFFICIENT",
        "BEST_CHEAP_MODEL": None,
        "BEST_PRICE_QUALITY_MODEL": "anthropic_sonnet_5",
        "CHEAPEST_PRIMARY_CANDIDATE": None,
        "BEST_FALLBACK_CANDIDATE": None,
        "CHEAP_MODEL_STRATEGY": "NOT_CONFIRMED",
    }


def test_doc9_terminal_receipt_and_frozen_product_sources_are_current() -> None:
    receipt = _read(RECEIPT_PATH)
    assert receipt["status"] == "COMPLETED"
    assert receipt["acceptance"] == {
        "PARSER_LEXICAL_AUDIT_COMPLETED": True,
        "ALL_DOC8_FRAGMENT_GAPS_CLASSIFIED": True,
        "CANONICAL_INPUT_PACKAGES_TOTAL": 12,
        "INPUT_PACKAGE_HASH_PARITY": "PASSED",
        "PROVIDERS_TOTAL": 3,
        "MODELS_TOTAL": 6,
        "EXPECTED_CALLS_TOTAL": 72,
        "ALL_CALLS_ACCOUNTED": True,
        "FAILED_TABLES_EXCLUDED_TOTAL": 0,
        "PROMPT_CHANGED_DURING_RUN": False,
        "INVENTORY_CHANGED_DURING_RUN": False,
        "DOC6_CHANGED": False,
        "ALL_MODEL_IDS_REPORTED": True,
        "ALL_RESOLVED_MODEL_IDS_REPORTED": True,
        "ALL_COSTS_REPORTED": True,
        "ALL_QUALITY_METRICS_REPORTED": True,
        "PRODUCT_INTEGRATION_CREATED": False,
    }
    assert receipt["estimated_cost_usd_total"] == 0.90455225
    frozen = receipt["frozen_hashes"]["frozen_file_sha256"]
    product_paths = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/full_source.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/pdf_text_layer.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/pdf_layout.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/pdf_layout_units.py",
        "services/broker-reports-gate1-proof/scripts/direct_pdf_experiment_transports.py",
        "services/broker-reports-gate1-proof/scripts/live_no_rag_source_intake_smoke.py",
    )
    for relative in product_paths:
        assert hashlib.sha256((REPO / relative).read_bytes()).hexdigest() == frozen[relative]
    assert "FACTORY_REQUIRED" in (REPO / product_paths[1]).read_text(encoding="utf-8")
    assert "FORBIDDEN" in (REPO / product_paths[1]).read_text(encoding="utf-8")


def test_doc9_report_and_brief_have_terminal_facts_and_stop_boundary() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8-sig")
    brief = BRIEF_PATH.read_text(encoding="utf-8-sig")
    required = (
        "DOC9_EXPERIMENT = COMPLETED",
        "PARSER_LEXICAL_PROJECTION = SUFFICIENT",
        "BEST_CHEAP_MODEL = NONE",
        "CHEAP_MODEL_STRATEGY = NOT_CONFIRMED",
        "ALL_DOC8_FRAGMENT_GAPS_CLASSIFIED = TRUE",
        "FAILED_TABLES_EXCLUDED_TOTAL = 0",
        "No cascade, product route",
    )
    assert all(value in report for value in required)
    assert "DOC6 and product runtime were unchanged" in brief
