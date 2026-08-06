from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
AUDIT = REPO / "docs/stage2/BROKER_REPORTS_DOC11_MINIMAL_CONTEXT_AUDIT.safe.json"
RESULTS = REPO / "docs/stage2/BROKER_REPORTS_DOC11_PLAIN_TEXT_RESULTS.safe.json"
REPORT = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC11_MINIMAL_TABLE_CONTEXT.report.md"
RECEIPT = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC11_MINIMAL_TABLE_CONTEXT.receipt.safe.json"
BRIEF = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC11_MINIMAL_TABLE_CONTEXT_BRIEF.md"

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


def test_doc11_safe_payloads_are_integrity_bound_and_private_value_free() -> None:
    payloads = [_load(path) for path in (AUDIT, RESULTS, RECEIPT)]
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


def test_doc11_four_minimal_packages_and_exact_model_catalog_are_frozen() -> None:
    audit = _load(AUDIT)
    assert audit["status"] == "COMPLETED_PRE_CALL_AUDIT"
    assert len(audit["packages"]) == 4
    assert {item["table_id"] for item in audit["packages"]} == {f"doc11_table_{index:02d}" for index in range(1, 5)}
    assert audit["aggregate"]["images_total"] == 4
    assert audit["aggregate"]["ids_exposed_total"] == 0
    assert audit["aggregate"]["parser_structure_fields_exposed_total"] == 0
    assert audit["aggregate"]["doc6_fields_exposed_total"] == 0
    for item in audit["packages"]:
        assert item["image"]["images_total"] == 1
        assert item["image"]["manual_visual_audit"] == "PASSED"
        assert item["parser_text"]["exact_source_multiset"] is True
        assert item["parser_text"]["lexicographically_sorted"] is True
        assert item["parser_text"]["visual_order_exposed"] is False
        assert item["parser_text"]["ids_exposed_total"] == 0
        assert item["parser_text"]["parser_rows_exposed_total"] == 0
        assert item["parser_text"]["parser_columns_exposed_total"] == 0
    assert {key: value["requested_model_id"] for key, value in audit["models"].items()} == MODELS
    assert all(value["availability"] == "AVAILABLE" and value["image_support"] is True for value in audit["models"].values())


def test_doc11_blocked_call_accounting_is_terminal_and_has_no_hidden_retry() -> None:
    results = _load(RESULTS)
    assert results["terminal_status"] == "BLOCKED"
    accounting = results["call_accounting"]
    assert accounting == {
        "slots_total": 16,
        "slots_accounted_total": 16,
        "http_responses_total": 2,
        "interrupted_after_claim_total": 14,
        "terminal_statuses": {"COMPLETED": 2, "INTERRUPTED_AFTER_CLAIM": 14},
        "http_statuses": {"200": 2, "None": 14},
        "retry_total": 0,
        "failed_tables_excluded_total": 0,
    }
    assert len(results["per_call"]) == 16
    assert len({(item["table_id"], item["model_key"]) for item in results["per_call"]}) == 16
    assert sum(item["provider_status"] == "COMPLETED" for item in results["per_call"]) == 2
    assert sum(item["provider_status"] == "INTERRUPTED_AFTER_CLAIM" for item in results["per_call"]) == 14
    assert results["blocker"]["new_authorization_required"] is True
    assert results["decision_eligibility"]["overall_effect_decision_allowed"] is False
    assert results["decision_eligibility"]["complete_four_table_models_total"] == 0


def test_doc11_terminal_classifications_do_not_promote_partial_diagnostics() -> None:
    results = _load(RESULTS)
    assert results["classifications"] == {
        "DOC11": "BLOCKED",
        "PLAIN_TEXT_CONTEXT_REDUCES_OVERLOAD": "INCONCLUSIVE",
        "PLAIN_TEXT_CONTEXT_IMPROVES_STRUCTURE": "INCONCLUSIVE",
        "BEST_CHEAP_MODEL": "NONE",
        "BEST_REFERENCE_MODEL": "NONE",
        "MINIMAL_CONTEXT_PROJECTION": "INCONCLUSIVE",
    }
    assert all(item["decision_eligible"] is False for item in results["per_model"].values())
    assert all(item["promising_cheap_threshold_passed"] is False for item in results["per_model"].values())
    assert results["per_model"]["google_flash_lite"]["provider_completed_total"] == 1
    assert results["per_model"]["google_flash_lite"]["TEXT_CONSERVATION"] == "FAILED"
    assert results["per_model"]["openai_mini"]["provider_completed_total"] == 1
    assert results["per_model"]["anthropic_haiku"]["provider_completed_total"] == 0
    assert results["per_model"]["anthropic_opus"]["provider_completed_total"] == 0


def test_doc11_receipt_binds_safe_outputs_and_unchanged_product_sources() -> None:
    audit = _load(AUDIT)
    results = _load(RESULTS)
    receipt = _load(RECEIPT)
    assert receipt["package_audit_safe_sha256"] == audit["integrity_sha256"]
    assert receipt["results_safe_sha256"] == results["integrity_sha256"]
    assert receipt["DOC11"] == "BLOCKED"
    assert receipt["retry_total"] == 0
    assert receipt["new_authorization_required"] is True
    assert receipt["product_pipeline_changed"] is False
    assert receipt["parser_changed"] is False
    assert receipt["doc6_changed"] is False
    for relative, expected in receipt["frozen_product_source_sha256"].items():
        assert _sha(REPO / relative) == expected
    parser_source = (REPO / "services/broker-reports-gate1-proof/broker_reports_gate1/pdf_text_layer.py").read_text(encoding="utf-8")
    assert "FACTORY_REQUIRED" in parser_source
    assert "FORBIDDEN" in parser_source


def test_doc11_report_and_brief_are_bom_encoded_and_state_the_stop_boundary() -> None:
    assert REPORT.read_bytes().startswith(b"\xef\xbb\xbf")
    assert BRIEF.read_bytes().startswith(b"\xef\xbb\xbf")
    report = REPORT.read_text(encoding="utf-8-sig")
    brief = BRIEF.read_text(encoding="utf-8-sig")
    for marker in (
        "DOC11 BLOCKED",
        "PLAIN_TEXT_CONTEXT_REDUCES_OVERLOAD",
        "PLAIN_TEXT_CONTEXT_IMPROVES_STRUCTURE",
        "MINIMAL_CONTEXT_PROJECTION",
        "14",
        "нового явного разрешения",
        "Product pipeline, parser, DOC6",
    ):
        assert marker in report
    assert "2/16" in brief
    assert "INCONCLUSIVE" in brief
