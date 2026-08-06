from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "docs/stage2"
REPORTS = REPO / "docs/reports/2026-08-04"

CONTEXT = STAGE / "BROKER_REPORTS_DOC16_CONTEXT_AUDIT.safe.json"
SOURCE = STAGE / "BROKER_REPORTS_DOC16_SOURCE_TEXT_QUALITY.safe.json"
RELATION = STAGE / "BROKER_REPORTS_DOC16_CONTEXT_RESULT_RELATION.safe.json"
POLICY = STAGE / "BROKER_REPORTS_DOC16_SOURCE_TEXT_POLICY.safe.json"
REPORT = REPORTS / "BROKER_REPORTS_DOC16_SOURCE_TEXT_CONTEXT_AUDIT.report.md"
BRIEF = REPORTS / "BROKER_REPORTS_DOC16_SOURCE_TEXT_CONTEXT_AUDIT_BRIEF.md"
RECEIPT = REPORTS / "BROKER_REPORTS_DOC16_SOURCE_TEXT_CONTEXT_AUDIT.receipt.safe.json"


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


def test_doc16_reconstructs_and_accounts_all_96_arm_b_payloads() -> None:
    context = _read(CONTEXT)
    reconstruction = context["payload_reconstruction"]
    assert context["DOC16_AUDIT"] == "COMPLETED"
    assert reconstruction["payloads_audited_total"] == 96
    assert reconstruction["exact_payloads_accounted_total"] == 96
    assert reconstruction["exact_request_hash_matches_total"] == 94
    assert reconstruction["terminal_transport_failures_with_no_model_visible_payload_total"] == 2
    assert reconstruction["reconstruction_mismatch_slot_ids"] == []
    assert reconstruction["exact_prompt_hash_matches_total"] == 96
    assert reconstruction["exact_image_hash_matches_total"] == 96
    assert reconstruction["source_present_once_total"] == 96
    assert reconstruction["source_utf8_roundtrip_exact_total"] == 96
    assert reconstruction["source_after_end_delimiter_empty_total"] == 96
    assert reconstruction["correct_user_role_total"] == 96
    assert reconstruction["semantic_payload_parity_tables_total"] == 24
    assert len(reconstruction["parity_by_table"]) == 24
    assert all(item["semantic_payload_parity"] is True for item in reconstruction["parity_by_table"].values())


def test_doc16_visually_audits_all_24_crops_without_overstating_cleanliness() -> None:
    context = _read(CONTEXT)
    crop = context["crop_audit"]
    assert crop["tables_audited_total"] == 24
    assert crop["status_counts"] == {"CROP_CLEAN": 12, "CROP_CLIPPED": 7, "CROP_CONTAMINATED": 5}
    assert len(crop["tables"]) == 24
    assert all(item["visually_opened_original_resolution"] is True for item in crop["tables"].values())
    assert all(item["resolution_sufficient_for_visible_content"] is True for item in crop["tables"].values())
    assert all(item["primary_status"] in {"CROP_CLEAN", "CROP_CLIPPED", "CROP_CONTAMINATED", "CROP_AMBIGUOUS"} for item in crop["tables"].values())


def test_doc16_reports_source_coverage_contamination_order_and_splits() -> None:
    source = _read(SOURCE)
    assert source["packages_audited_total"] == 24
    assert len(source["tables"]) == 24
    assert source["summary"]["coverage_below_99_tables_total"] == 12
    assert source["summary"]["packages_with_foreign_fragments_total"] == 16
    assert source["summary"]["packages_with_critical_foreign_values_total"] == 17
    assert source["summary"]["packages_with_critical_duplicates_total"] == 5
    assert source["summary"]["packages_with_ambiguous_value_splits_total"] == 5
    assert source["summary"]["order_status_counts"] == {"ORDER_GOOD": 18, "ORDER_MISLEADING": 1, "ORDER_PARTIAL": 5}
    for item in source["tables"].values():
        assert 0.0 <= item["critical_value_coverage"] <= 1.0
        assert item["visible_critical_values_total"] == item["critical_values_present_in_source_text"] + item["critical_values_missing_from_source_text"]
        assert item["order_status"] in {"ORDER_GOOD", "ORDER_PARTIAL", "ORDER_MISLEADING"}
        assert item["context_classification"] in {
            "CONTEXT_CLEAN", "CONTEXT_CLEAN_BUT_UNHELPFUL", "CONTEXT_INCOMPLETE", "CONTEXT_CONTAMINATED",
            "CONTEXT_MISORDERED", "CONTEXT_CONTRADICTORY", "CONTEXT_OVERLOADED",
        }


def test_doc16_token_accounting_uses_receipts_and_reports_no_truncation() -> None:
    context = _read(CONTEXT)
    token = context["token_audit"]
    assert token["calls_audited_total"] == 96
    assert token["truncation_total"] == 0
    assert token["context_limit_errors_total"] == 0
    assert set(token["by_model"]) == {"openai_mini", "google_flash_lite", "anthropic_haiku", "anthropic_opus"}
    assert sum(item["actual_usage_calls_total"] for item in token["by_model"].values()) == 94
    assert all(item["maximum_output_tokens"] < 8192 for item in token["by_model"].values())
    assert all(item["source_package_incremental_tokens_total"] > 0 for item in token["by_model"].values())
    assert all(item["truncated_total"] == 0 for item in token["by_model"].values())
    assert token["component_method"]["total_input_and_output"] == "actual provider receipt usage when present"


def test_doc16_relation_is_diagnostic_and_policy_holds_stop_boundary() -> None:
    relation = _read(RELATION)
    policy = _read(POLICY)
    assert relation["diagnostic_not_causal"] is True
    assert len(relation["tables"]) == 24
    assert sum(relation["classification_counts"].values()) == 24
    assert policy["fairness_threshold_tables"] == 20
    assert policy["fair_packages_total"] == 5
    assert policy["SOURCE_TEXT_CONTEXT_QUALITY"] == "INSUFFICIENT"
    assert policy["SOURCE_TEXT_HYPOTHESIS_FAIRLY_TESTED"] == "NO"
    assert policy["SOURCE_TEXT_DEFAULT_POLICY"] == "OPTIONAL_OR_INCONCLUSIVE"
    assert policy["dominant_defect"] is None
    assert len(policy["tables"]) == 24
    assert sum(item["fair_test_package"] for item in policy["tables"].values()) == 5
    improvements = {item["problem"]: item for item in policy["improvements"]}
    assert improvements["proven_critical_duplicates"]["evidence"] == {"packages_total": 5}
    assert improvements["proven_critical_duplicates"]["new_provider_calls_required"] == "NO_FOR_CORRECTION_YES_FOR_ANY_FUTURE_RETEST"
    assert improvements["fragment_delimiting"]["recommendation"] == "NO_CHANGE"


def test_doc16_receipt_binds_safe_outputs_and_zero_change_acceptance() -> None:
    receipt = _read(RECEIPT)
    assert receipt["DOC16_AUDIT"] == "COMPLETED"
    acceptance = receipt["acceptance"]
    assert acceptance["DOC15_CONTEXT_PAYLOADS_AUDITED"] == 96
    assert acceptance["DOC15_TABLE_CROPS_AUDITED"] == 24
    assert acceptance["DOC15_SOURCE_TEXT_PACKAGES_AUDITED"] == 24
    for key in (
        "EXACT_MODEL_VISIBLE_PAYLOAD_RECONSTRUCTED", "PROVIDER_PAYLOAD_PARITY_REPORTED", "CROP_QUALITY_REPORTED",
        "SOURCE_TEXT_COVERAGE_REPORTED", "SOURCE_TEXT_CONTAMINATION_REPORTED", "SOURCE_TEXT_ORDER_REPORTED",
        "CONTEXT_TOKEN_LOAD_REPORTED", "TRUNCATION_REPORTED", "TABLE_LEVEL_CONTEXT_CLASSIFICATION_REPORTED",
        "CONTEXT_VS_RESULT_DIAGNOSTIC_REPORTED",
    ):
        assert acceptance[key] is True
    assert acceptance["NEW_PROVIDER_CALLS_TOTAL"] == 0
    assert acceptance["PARSER_CHANGED"] is False
    assert acceptance["DOC6_CHANGED"] is False
    assert acceptance["PRODUCT_PIPELINE_CHANGED"] is False
    assert acceptance["GATE2_IMPLEMENTED"] is False
    by_name = {path.name: path for path in (CONTEXT, SOURCE, RELATION, POLICY, REPORT, BRIEF)}
    for name, expected in receipt["safe_artifact_sha256"].items():
        assert _sha(by_name[name]) == expected
    assert REPORT.read_bytes().startswith(b"\xef\xbb\xbf")
    assert BRIEF.read_bytes().startswith(b"\xef\xbb\xbf")


def test_doc16_public_evidence_contains_no_private_payload_or_exact_diff() -> None:
    json_paths = (CONTEXT, SOURCE, RELATION, POLICY, RECEIPT)
    forbidden_keys = {"request", "response", "raw_output", "provider_response_private", "prompt", "gold", "bbox", "api_key", "foreign_fragment_entries"}
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
