from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STAGE2 = REPO / "docs/stage2"
REPORTS = REPO / "docs/reports/2026-08-03"
SELECTION_PATH = STAGE2 / "BROKER_REPORTS_DOC8_SELECTION.safe.json"
INVENTORY_PATH = STAGE2 / "BROKER_REPORTS_DOC8_PARSER_INVENTORY_AND_GOLD.safe.json"
RESULTS_PATH = STAGE2 / "BROKER_REPORTS_DOC8_MULTI_MODEL_STRUCTURE_RESULTS.safe.json"
COMPARISON_PATH = STAGE2 / "BROKER_REPORTS_DOC8_MODEL_COMPARISON.safe.json"
RECEIPT_PATH = REPORTS / "BROKER_REPORTS_DOC8_TERMINAL_RECEIPT.safe.json"
BRIEF_PATH = REPORTS / "BROKER_REPORTS_DOC8_BRIEF.safe.json"
REPORT_PATH = REPORTS / "BROKER_REPORTS_DOC8_MULTI_MODEL_IMAGE_PARSER_CONTEXT_STRUCTURE.report.md"
JSON_PATHS = (
    SELECTION_PATH,
    INVENTORY_PATH,
    RESULTS_PATH,
    COMPARISON_PATH,
    RECEIPT_PATH,
    BRIEF_PATH,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha(payload: dict) -> str:
    material = {key: value for key, value in payload.items() if key != "integrity_sha256"}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_doc8_safe_json_integrity_and_privacy_boundary() -> None:
    forbidden = (
        "private://",
        "raw_output",
        "fragment_private_map",
        "word_ref",
        '"bbox"',
        "local/stage2",
        "\\local\\stage2\\",
        "d:\\users\\",
        "c:\\users\\",
        "visual_gold.sealed.private",
    )
    for path in JSON_PATHS:
        payload = _read(path)
        assert payload["integrity_sha256"] == _canonical_sha(payload)
        assert payload.get("private_values_included") is False
        lowered = path.read_text(encoding="utf-8").lower()
        assert not any(value in lowered for value in forbidden)


def test_doc8_selection_is_the_exact_frozen_12_table_design() -> None:
    selection = _read(SELECTION_PATH)
    assert selection["status"] == "FROZEN_BEFORE_PROVIDER_CALLS"
    assert selection["tables_frozen_total"] == 12
    assert selection["failed_tables_excluded_total"] == 0
    assert selection["selection_integrity_sha256"] == (
        "0484866fc1a5c0263cbe9b04f406cc7fc3f33cef6e59941780a62da3425dfeab"
    )
    assert selection["selected_table_ids"] == [
        "unseen_pdf_03_t01",
        "unseen_pdf_02_t05",
        "unseen_pdf_01_t04",
        "unseen_pdf_06_t25",
        "unseen_pdf_06_t03",
        "unseen_pdf_06_t35",
        "unseen_pdf_06_t27",
        "unseen_pdf_06_t09",
        "unseen_pdf_06_t05",
        "unseen_pdf_01_t01",
        "unseen_pdf_06_t07",
        "unseen_pdf_01_t05",
    ]
    assert [item["stratum"] for item in selection["selected_tables"]] == [
        "simple_two_column",
        "adjacent_table",
        "sparse_financial_statement",
        "group_rows",
        "multi_level_header",
        "wide_table",
        "currency_markers",
        "subtotals_totals",
        "long_text_values",
        "repeated_identical_numbers",
        "schedule_of_investments",
        "multi_page_fragment",
    ]


def test_doc8_parser_inventory_is_structure_neutral_and_coverage_is_explicit() -> None:
    inventory = _read(INVENTORY_PATH)
    assert inventory["status"] == "FROZEN_BEFORE_PROVIDER_CALLS"
    assert inventory["factory_route"] == [
        "FullSourceArtifactFactory.create",
        "FullSourceArtifactBuilder.build",
        "PdfTextLayerParserFactory.create",
        "PdfLayoutUnitBuilder.build",
    ]
    assert inventory["structure_neutrality"] == {
        "doc6_outputs_read_total": 0,
        "parser_rows_exposed_total": 0,
        "parser_columns_exposed_total": 0,
        "geometry_exposed_as_text_total": 0,
        "inventories_with_spatial_order_total": 0,
        "model_inventory_fields": ["id", "text"],
    }
    assert inventory["parser_lexical_coverage"] == {
        "gold_visible_text_fragments_total": 1086,
        "parser_fragments_matched_total": 600,
        "parser_fragments_missing_total": 486,
        "parser_extra_fragments_total": 119,
        "parser_word_ids_total": 627,
        "gold_mapping_resolved_ids_total": 556,
        "gold_mapping_unresolved_ids_total": 61,
        "gold_mapping_extra_ids_total": 10,
    }
    assert len(inventory["per_table"]) == 12
    assert all(item["text"] == "<exact source text redacted>" for item in inventory["safe_inventory_example"])


def test_doc8_models_prompt_and_one_attempt_call_accounting_are_exact() -> None:
    results = _read(RESULTS_PATH)
    models = results["model_discovery"]
    assert {provider: value["model_id"] for provider, value in models.items()} == {
        "openai": "gpt-5.4-2026-03-05",
        "google": "models/gemini-3.1-pro-preview",
        "anthropic": "claude-opus-5",
    }
    assert all(value["models_api_http_status"] == 200 for value in models.values())
    assert results["prompt_sha256"] == "09e74e4abef48aacb4348af07c68e22b30f7506c730feb5286719836c08a853f"

    accounting = results["call_accounting"]
    assert sum(value["calls_total"] for value in accounting.values()) == 72
    for value in accounting.values():
        assert value["calls_total"] == 24
        assert value["calls_by_arm"] == {
            "image_only_id_map": 12,
            "image_plus_parser_text": 12,
        }
        assert value["http_statuses"] == {"200": 24}
        assert value["attempts_total"] == 24
    assert accounting["openai"]["terminal_statuses"] == {"COMPLETED": 24}
    assert accounting["google"]["terminal_statuses"] == {"COMPLETED": 24}
    assert accounting["anthropic"]["terminal_statuses"] == {"COMPLETED": 21, "FAILED": 3}
    assert accounting["anthropic"]["error_types"] == {"EMPTY_OUTPUT": 3}


def test_doc8_six_arms_have_exact_primary_metrics() -> None:
    aggregates = _read(RESULTS_PATH)["aggregates"]
    expected = {
        ("openai", "image_only_id_map"): (21, 179, 260, 0, 286, 321, 4, 0),
        ("openai", "image_plus_parser_text"): (109, 366, 522, 4, 0, 1, 4, 2),
        ("google", "image_only_id_map"): (41, 148, 256, 0, 37, 337, 0, 18),
        ("google", "image_plus_parser_text"): (37, 85, 139, 1, 0, 469, 0, 0),
        ("anthropic", "image_only_id_map"): (52, 138, 241, 0, 82, 356, 0, 0),
        ("anthropic", "image_plus_parser_text"): (117, 376, 556, 4, 0, 0, 0, 0),
    }
    for (provider, arm), values in expected.items():
        actual = aggregates[provider][arm]
        assert actual["gold_rows_total"] == 128
        assert actual["gold_cells_total"] == 384
        assert actual["tokens_expected"] == 556
        assert (
            actual["matched_rows_total"],
            actual["exact_cell_groups_matched"],
            actual["tokens_correctly_placed"],
            actual["complete_table_exact_matches"],
            actual["invented_ids"],
            actual["missing_ids"],
            actual["duplicated_ids"],
            actual["unresolved_ids"],
        ) == values


def test_doc8_paired_answers_best_models_and_threshold_are_fail_closed() -> None:
    results = _read(RESULTS_PATH)
    labels = {
        provider: {question: answer["label"] for question, answer in questions.items()}
        for provider, questions in results["questions"].items()
    }
    assert labels == {
        "openai": {
            "PARSER_TEXT_IMPROVES_ROW_RECOVERY": "TRUE",
            "PARSER_TEXT_IMPROVES_CELL_GROUPING": "TRUE",
            "PARSER_TEXT_REDUCES_MISSING_IDS": "TRUE",
            "PARSER_TEXT_REDUCES_UNRESOLVED_IDS": "INCONCLUSIVE",
        },
        "google": {
            "PARSER_TEXT_IMPROVES_ROW_RECOVERY": "INCONCLUSIVE",
            "PARSER_TEXT_IMPROVES_CELL_GROUPING": "INCONCLUSIVE",
            "PARSER_TEXT_REDUCES_MISSING_IDS": "INCONCLUSIVE",
            "PARSER_TEXT_REDUCES_UNRESOLVED_IDS": "INCONCLUSIVE",
        },
        "anthropic": {
            "PARSER_TEXT_IMPROVES_ROW_RECOVERY": "TRUE",
            "PARSER_TEXT_IMPROVES_CELL_GROUPING": "TRUE",
            "PARSER_TEXT_REDUCES_MISSING_IDS": "TRUE",
            "PARSER_TEXT_REDUCES_UNRESOLVED_IDS": "INCONCLUSIVE",
        },
    }
    assert {
        key: value["winners"] for key, value in results["best_models"].items()
    } == {
        "BEST_MODEL_FOR_ROW_RECOVERY": ["anthropic"],
        "BEST_MODEL_FOR_CELL_GROUPING": ["anthropic"],
        "BEST_MODEL_FOR_TOKEN_CONSERVATION": ["anthropic"],
    }
    assert results["promising_threshold_by_model"] == {
        "openai": False,
        "google": False,
        "anthropic": False,
    }
    assert results["classifications"]["HYBRID_STRUCTURE_RECONCILIATION"] == "NOT_CONFIRMED"


def test_doc8_terminal_receipt_closes_acceptance_without_product_activation() -> None:
    receipt = _read(RECEIPT_PATH)
    assert receipt["status"] == "COMPLETED"
    acceptance = receipt["acceptance"]
    assert acceptance == {
        "TABLES_FROZEN_TOTAL": 12,
        "MODELS_FROZEN_TOTAL": 3,
        "ARMS_TOTAL": 2,
        "EXPECTED_PROVIDER_CALLS_TOTAL": 72,
        "PARSER_INVENTORY_FROZEN": True,
        "FRAGMENT_GOLD_FROZEN_BEFORE_CALLS": True,
        "PROMPT_FROZEN_BEFORE_CALLS": True,
        "MODEL_IDS_FROZEN_BEFORE_CALLS": True,
        "ALL_72_CALLS_ACCOUNTED": True,
        "FAILED_TABLES_EXCLUDED_TOTAL": 0,
        "ALL_OUTPUTS_VALIDATED": True,
        "ALL_METRICS_REPORTED": True,
        "DOC6_CHANGED": False,
        "PRODUCT_INTEGRATION_CREATED": False,
    }
    assert receipt["estimated_cost_usd_total"] == 2.453311


def test_doc8_frozen_factory_sources_and_anchors_remain_current() -> None:
    frozen = _read(RECEIPT_PATH)["frozen_hashes"]["frozen_file_sha256"]
    source_paths = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/full_source.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/pdf_text_layer.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/pdf_layout_units.py",
        "services/broker-reports-gate1-proof/scripts/direct_pdf_experiment_transports.py",
        "services/broker-reports-gate1-proof/scripts/live_no_rag_source_intake_smoke.py",
    )
    for relative in source_paths:
        assert hashlib.sha256((REPO / relative).read_bytes()).hexdigest() == frozen[relative]
    full_source = (REPO / source_paths[0]).read_text(encoding="utf-8")
    parser = (REPO / source_paths[1]).read_text(encoding="utf-8")
    layout = (REPO / source_paths[2]).read_text(encoding="utf-8")
    assert "FullSourceArtifactFactory.create" in full_source
    assert "PdfTextLayerParserFactory.create" in parser
    assert "PdfLayoutUnitBuilder" in layout


def test_doc8_report_has_terminal_facts_and_stop_boundary() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    required = (
        "DOC8_EXPERIMENT = COMPLETED",
        "PARSER_TEXT_IMPROVES_STRUCTURE = MODEL_DEPENDENT",
        "BEST_ROW_MODEL = claude-opus-5",
        "BEST_CELL_GROUPING_MODEL = claude-opus-5",
        "BEST_TOKEN_CONSERVATION_MODEL = claude-opus-5",
        "HYBRID_STRUCTURE_RECONCILIATION = NOT_CONFIRMED",
        "FAILED_TABLES_EXCLUDED_TOTAL = 0",
        "No new pipeline or activation was created.",
    )
    assert all(value in report for value in required)
