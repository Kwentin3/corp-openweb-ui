from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STAGE2 = REPO / "docs/stage2"
REPORTS = REPO / "docs/reports/2026-08-03"
MANIFEST_PATH = STAGE2 / "BROKER_REPORTS_DOC7_UNSEEN_CORPUS_MANIFEST.safe.json"
RESULTS_PATH = STAGE2 / "BROKER_REPORTS_DOC7_BLIND_GENERALIZATION_RESULTS.safe.json"
COMPARISON_PATH = STAGE2 / "BROKER_REPORTS_DOC7_MARKDOWN_JSON_COMPARISON.safe.json"
RECEIPT_PATH = REPORTS / "BROKER_REPORTS_DOC7_TERMINAL_RECEIPT.safe.json"
BRIEF_PATH = REPORTS / "BROKER_REPORTS_DOC7_BRIEF.safe.json"
REPORT_PATH = REPORTS / "BROKER_REPORTS_DOC7_BLIND_GENERALIZATION_AND_MARKDOWN_JSON.report.md"


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


def test_doc7_safe_json_integrity_and_privacy_boundary() -> None:
    paths = (MANIFEST_PATH, RESULTS_PATH, COMPARISON_PATH, RECEIPT_PATH, BRIEF_PATH)
    forbidden = (
        "private://",
        "private_source_ref",
        "raw_output",
        "source_artifact_ref",
        "local/stage2",
        "\\local\\stage2\\",
        "d:\\users\\",
        "c:\\users\\",
        "visual_gold.sealed.private",
    )
    for path in paths:
        payload = _read(path)
        assert payload["integrity_sha256"] == _canonical_sha(payload)
        assert payload.get("private_values_included") is False
        lowered = path.read_text(encoding="utf-8").lower()
        assert not any(value in lowered for value in forbidden)


def test_doc7_frozen_corpus_and_gold_gates_are_exact() -> None:
    manifest = _read(MANIFEST_PATH)
    assert manifest["status"] == "FROZEN"
    assert manifest["frozen_before_visual_gold"] is True
    assert manifest["frozen_before_doc6_run"] is True
    assert manifest["frozen_before_provider_calls"] is True
    assert manifest["documents_total"] == 6
    assert manifest["publishers_total"] == 5
    assert manifest["pages_total"] == 51
    assert manifest["tables_total"] == 65
    assert manifest["main_corpus_text_layer_only"] is True
    assert manifest["challenge_set_documents_total"] == 0
    assert manifest["failed_documents_excluded_total"] == 0
    assert manifest["known_prior_candidates_excluded_by_byte_match"] == 2
    assert len({item["source_sha256"] for item in manifest["documents"]}) == 6
    assert len({item["public_source_url"] for item in manifest["documents"]}) == 6
    for item in manifest["documents"]:
        assert item["text_layer_status"] == "PRESENT_ON_ALL_PAGES"
        assert all(value == 0 for value in item["unseen_checks"].values())

    gold = _read(RESULTS_PATH)["visual_gold"]
    assert gold == {
        "documents_total": 6,
        "tables_total": 65,
        "logical_rows_total": 649,
        "visible_entries_total": 2062,
        "row_roles": {
            "DATA": 325,
            "GROUP": 104,
            "HEADER": 144,
            "NOTE": 2,
            "SUBTOTAL": 18,
            "TOTAL": 56,
        },
        "continuation_tables_total": 1,
        "unknown_roles_total": 0,
        "integrity_sha256": "b2543e1d85a10ff885e53162d15fed937f92dca35ec210298dd8f06cacd49d90",
    }


def test_doc7_doc6_negative_result_is_not_hidden() -> None:
    doc6 = _read(RESULTS_PATH)["doc6"]
    assert doc6["documents_attempted_total"] == 6
    assert doc6["documents_with_managed_output_total"] == 0
    assert doc6["terminal_failures_total"] == 6
    assert doc6["terminal_failure_types"] == {
        "LogicalRowTableRecoveryError": 2,
        "ManagedPdfDocumentV2Error": 4,
    }
    assert doc6["failed_documents_excluded_total"] == 0
    assert doc6["tables_detected"] == 0
    assert doc6["tables_expected"] == 65
    assert doc6["logical_rows_matched"] == 0
    assert doc6["logical_rows_expected"] == 649
    assert doc6["visible_entries_matched"] == 0
    assert doc6["visible_entries_expected"] == 2062
    assert doc6["unmatched_visible_entries_total"] == 2062
    assert doc6["dropped_values"] == 1472
    assert doc6["missing_continuation"] == 1
    assert doc6["provider_calls_total"] == 0
    assert doc6["visual_gold_used_as_input"] is False
    assert doc6["row_order_interpretation"] == "NOT_MEASURABLE_NO_MATCHED_ROWS"


def test_doc7_paired_arms_have_exact_call_and_input_parity() -> None:
    results = _read(RESULTS_PATH)
    provider = results["provider"]
    assert provider["model_snapshot_requested"] == "gpt-5.4-2026-03-05"
    assert provider["model_snapshots_returned"] == {"gpt-5.4-2026-03-05": 130}
    assert provider["calls_total"] == 130
    assert provider["calls_by_arm"] == {"json": 65, "markdown": 65}
    assert provider["terminal_statuses"] == {"COMPLETED": 130}
    assert provider["http_statuses"] == {"200": 130}
    assert provider["attempts_total"] == 130
    assert provider["input_parity_failures_total"] == 0
    assert provider["truncated_responses_total"] == 0
    assert provider["tools_total"] == 0
    assert provider["retrieval_calls_total"] == 0
    assert provider["web_calls_total"] == 0
    assert provider["store"] is False
    assert provider["retry_attempts_total"] == 0
    assert provider["best_of"] is False
    assert provider["prompt_sha256"] == {
        "json": "c2d4519ce44f943cea9325d714ee8aa6da37323b35b1280b352aa4d99d6009d4",
        "markdown": "1956ee866440cb4ea979d14098e6cf9546e8b9530fc4c35845e23cb120cce0e3",
    }


def test_doc7_metrics_and_pre_registered_answers_are_exact() -> None:
    results = _read(RESULTS_PATH)
    markdown = results["markdown"]
    structured = results["json"]
    assert (markdown["tables_recalled"], structured["tables_recalled"]) == (65, 65)
    assert (markdown["logical_rows_matched"], structured["logical_rows_matched"]) == (630, 631)
    assert (markdown["visible_entries_matched"], structured["visible_entries_matched"]) == (1819, 1960)
    assert (markdown["wrong_row_associations"], structured["wrong_row_associations"]) == (6, 6)
    assert (markdown["wrong_column_associations"], structured["wrong_column_associations"]) == (30, 43)
    assert (markdown["invented_values"], structured["invented_values"]) == (258, 44)
    assert (markdown["dropped_values"], structured["dropped_values"]) == (280, 47)
    assert (markdown["duplicated_values"], structured["duplicated_values"]) == (0, 0)
    assert markdown["malformed_markdown_tables"] == 15
    assert structured["invalid_json_responses"] == 0
    assert markdown["truncated_responses"] == structured["truncated_responses"] == 0

    questions = _read(COMPARISON_PATH)["questions"]
    assert questions["MARKDOWN_RETAINS_MORE_LOGICAL_ROWS_THAN_JSON"]["label"] == "INCONCLUSIVE"
    assert questions["MARKDOWN_RETAINS_MORE_VISIBLE_VALUES_THAN_JSON"]["label"] == "FALSE"
    assert questions["MARKDOWN_HAS_FEWER_WRONG_ROW_BINDINGS_THAN_JSON"]["label"] == "INCONCLUSIVE"
    assert questions["MARKDOWN_HAS_FEWER_WRONG_COLUMN_BINDINGS_THAN_JSON"]["label"] == "INCONCLUSIVE"


def test_doc7_terminal_classifications_and_acceptance_are_closed() -> None:
    expected = {
        "DOC6_GENERALIZATION": "FAILED",
        "MARKDOWN_VS_JSON": "INCONCLUSIVE",
        "OUTPUT_SCHEMA_PRESSURE": "INCONCLUSIVE",
    }
    receipt = _read(RECEIPT_PATH)
    assert receipt["status"] == "COMPLETED"
    assert receipt["classifications"] == expected
    assert _read(RESULTS_PATH)["classifications"] == expected
    assert _read(COMPARISON_PATH)["final"] == expected
    acceptance = receipt["acceptance"]
    assert acceptance["UNSEEN_CORPUS_FROZEN"] is True
    assert acceptance["UNSEEN_DOCUMENTS_TOTAL"] == 6
    assert acceptance["UNSEEN_TABLES_TOTAL"] == 65
    assert acceptance["VISUAL_GOLD_CREATED_BEFORE_RUN"] is True
    assert acceptance["DOC6_CODE_CHANGED_DURING_RUN"] is False
    assert acceptance["DOC6_BLIND_RUN_COMPLETED"] is True
    assert acceptance["DOC6_DOCUMENTS_WITH_MANAGED_OUTPUT_TOTAL"] == 0
    assert acceptance["DOC6_TERMINAL_FAILURES_TOTAL"] == 6
    assert acceptance["MARKDOWN_ARM_COMPLETED"] is True
    assert acceptance["JSON_ARM_COMPLETED"] is True
    assert acceptance["ALL_CORPUS_DOCUMENTS_REPORTED"] is True
    assert acceptance["FAILED_DOCUMENTS_EXCLUDED_TOTAL"] == 0
    assert acceptance["ALL_MISMATCHES_ACCOUNTED"] is True


def test_doc7_frozen_doc6_hashes_and_factory_anchors_remain_current() -> None:
    receipt = _read(RECEIPT_PATH)
    frozen = receipt["frozen_hashes"]["frozen_file_sha256"]
    doc6_paths = (
        "services/broker-reports-gate1-proof/broker_reports_gate1/logical_row_table_recovery.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/managed_pdf_document_v2.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/managed_document_llm_view_v2.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/managed_document_llm_view_audit_v2.py",
        "docs/stage2/contracts/BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json",
    )
    for relative in doc6_paths:
        assert hashlib.sha256((REPO / relative).read_bytes()).hexdigest() == frozen[relative]
    managed_source = (REPO / doc6_paths[1]).read_text(encoding="utf-8")
    view_source = (REPO / doc6_paths[2]).read_text(encoding="utf-8")
    assert "ManagedPdfDocumentV2Factory.create is the sole inactive PDF" in managed_source
    assert "ManagedDocumentLlmViewV2Factory.create is the sole DOC6 View v2 owner" in view_source


def test_doc7_report_has_required_stop_boundary_and_terminal_facts() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    required = (
        "DOC6_GENERALIZATION = FAILED",
        "MARKDOWN_VS_JSON = INCONCLUSIVE",
        "OUTPUT_SCHEMA_PRESSURE = INCONCLUSIVE",
        "FAILED_DOCUMENTS_EXCLUDED_TOTAL = 0",
        "DOC6_CODE_CHANGED_DURING_RUN = FALSE",
        "No DOC6 fix",
    )
    assert all(value in report for value in required)
