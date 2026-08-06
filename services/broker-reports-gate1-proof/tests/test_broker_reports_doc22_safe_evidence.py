from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from broker_reports_gate1 import DOC22_SAFE_EVIDENCE_MAPPING


REPO = Path(__file__).resolve().parents[3]
STAGE2 = REPO / "docs/stage2"
REPORTS = REPO / "docs/reports/2026-08-04"
SAFE_FILES = [
    STAGE2 / "BROKER_REPORTS_DOC22_GATE1_HANDOFF_AUDIT.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC22_DIRECT_DOCUMENT_SUFFICIENCY_RESULTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC22_PARSER_CONTEXT_RESCUE.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC22_PROVIDER_COMPARISON.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC22_CROP_CLASS_EFFECT.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC22_CONFLICTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC22_AUTOMATION_ELIGIBILITY.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC22_AUTOMATED_AUDIT_RESULTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC22_CALL_ACCOUNTING.safe.json",
]
REPORT = REPORTS / "BROKER_REPORTS_DOC22_FULL_GATE1_DOCUMENT_PACKAGE_MATERIAL_SUFFICIENCY_AUDIT.report.md"
BRIEF = REPORTS / "BROKER_REPORTS_DOC22_FULL_GATE1_DOCUMENT_PACKAGE_MATERIAL_SUFFICIENCY_AUDIT_BRIEF.md"
RECEIPT = REPORTS / "BROKER_REPORTS_DOC22_FULL_GATE1_DOCUMENT_PACKAGE_MATERIAL_SUFFICIENCY_AUDIT.receipt.safe.json"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def checked(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    integrity = value.pop("integrity_sha256")
    assert integrity == hashlib.sha256(canonical_bytes(value)).hexdigest()
    return value


def test_doc22_safe_json_integrity_and_receipt_hashes() -> None:
    for path in [*SAFE_FILES, RECEIPT]:
        assert path.is_file()
        checked(path)

    receipt = checked(RECEIPT)
    artifacts = {row["file"]: row["sha256"] for row in receipt["artifacts"]}
    for path in [*SAFE_FILES, REPORT, BRIEF]:
        relative = path.relative_to(REPO).as_posix()
        assert artifacts[relative] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_doc22_direct_accounting_and_phase_a_gate() -> None:
    direct = checked(
        STAGE2 / "BROKER_REPORTS_DOC22_DIRECT_DOCUMENT_SUFFICIENCY_RESULTS.safe.json"
    )
    assert direct["tables_total"] == 24
    assert direct["gate1_table_artifacts_per_table"] == 2
    assert direct["direct_cases_total"] == 48
    assert direct["direct_agent_review_completed"] is True
    assert direct["failed_cases_excluded"] == 0
    assert direct["new_provider_calls_phase_a_total"] == 0
    assert len(direct["categories_assessed"]) == 15
    assert len(direct["cases"]) == 48
    assert len({row["table_id"] for row in direct["cases"]}) == 24
    assert direct["provider_metrics"]["google_flash_lite"]["counts"] == {
        "DOCUMENT_SUFFICIENT": 1,
        "RESCUED_BY_DOCUMENT_CONTEXT": 21,
        "DOCUMENT_CRITICAL_LOSS": 0,
        "AMBIGUOUS": 2,
    }
    assert direct["provider_metrics"]["anthropic_opus"]["counts"] == {
        "DOCUMENT_SUFFICIENT": 4,
        "RESCUED_BY_DOCUMENT_CONTEXT": 19,
        "DOCUMENT_CRITICAL_LOSS": 0,
        "AMBIGUOUS": 1,
    }
    assert all(
        metrics["phase_b_eligible"]
        for metrics in direct["provider_metrics"].values()
    )


def test_doc22_handoff_and_shadow_scope_stops() -> None:
    handoff = checked(STAGE2 / "BROKER_REPORTS_DOC22_GATE1_HANDOFF_AUDIT.safe.json")
    assert handoff["gate1_document_handoff_audited"] is True
    assert handoff["finding"]["canonical_document_level_handoff_found"] is False
    assert handoff["finding"]["actual_downstream_handoff"] == (
        f"{DOC22_SAFE_EVIDENCE_MAPPING.legacy_contract_version} reference bundle"
    )
    assert handoff["research_shadow_package_created"] is True
    assert handoff["new_product_handoff_contract_created"] is False
    assert handoff["shadow_documents_total"] == 6
    assert handoff["shadow_tables_total"] == 24
    assert handoff["shadow_cases_total"] == 48
    assert handoff["shadow_construction"] == {
        "existing_parser_order_preserved": True,
        "new_reading_order_algorithm_used": False,
        "new_text_classification_used": False,
        "new_semantic_relations_used": False,
        "corrected_text_used": False,
        "pdf_values_reread_used": False,
    }


def test_doc22_rescue_crop_and_conflict_results() -> None:
    rescue = checked(STAGE2 / "BROKER_REPORTS_DOC22_PARSER_CONTEXT_RESCUE.safe.json")
    assert rescue["parser_context_rescue"] == "SUBSTANTIAL"
    assert rescue["isolated_critical_cases_total"] == 43
    assert rescue["isolated_critical_cases_rescued_total"] == 40
    assert rescue["isolated_critical_cases_ambiguous_total"] == 3
    assert rescue["isolated_critical_cases_document_critical_total"] == 0

    crop = checked(STAGE2 / "BROKER_REPORTS_DOC22_CROP_CLASS_EFFECT.safe.json")
    assert crop["crop_class_counts"] == {
        "CROP_CLEAN": 12,
        "CROP_CLIPPED": 7,
        "CROP_CONTAMINATED": 5,
    }
    assert crop["document_critical_losses_by_crop_class"] == {
        "CROP_CLEAN": 0,
        "CROP_CLIPPED": 0,
        "CROP_CONTAMINATED": 0,
    }
    assert crop["crop_quality_dependency"] is False
    assert crop["crop_research_policy"] == "DEFINE_MINIMUM_DOCUMENT_CONTEXT_CONTRACT"

    conflicts = checked(STAGE2 / "BROKER_REPORTS_DOC22_CONFLICTS.safe.json")
    assert conflicts["conflict_cases_total"] == 5
    assert len(conflicts["ambiguous_cases"]) == 3
    assert conflicts["no_false_rescue_policy_applied"] is True


def test_doc22_automated_audit_is_accounted_but_not_overclaimed() -> None:
    automated = checked(
        STAGE2 / "BROKER_REPORTS_DOC22_AUTOMATED_AUDIT_RESULTS.safe.json"
    )
    assert automated["automated_audit"] == "BLOCKED"
    assert automated["validation_status"] == "NOT_VALIDATED_INCOMPLETE_CORPUS"
    assert automated["exact_adapter_preflight_passed"] is True
    assert automated["requested_model_id"] == "gpt-5.6-sol"
    assert automated["resolved_model_id"] == "gpt-5.6-sol"
    assert automated["qualification_http_status"] == 200
    assert automated["temperature_omitted"] is True
    assert automated["qualification_input_tokens"] < automated["context_window_tokens"]
    assert automated["automated_cases_expected"] == 48
    assert automated["automated_cases_completed"] == 23
    assert automated["automated_cases_failed"] == 25
    assert automated["rate_limited_total"] == 25
    assert automated["all_automated_calls_accounted"] is True
    assert automated["observed_agreement"]["overall"] == "20/23"
    assert automated["observed_agreement"]["ambiguity"] == "0/3"
    assert automated["observed_agreement"][
        "false_safe_total_contract_definition"
    ] == 0
    assert automated["observed_agreement"][
        "direct_ambiguous_to_automated_safe_total"
    ] == 3
    assert automated["agreement_is_corpus_complete"] is False

    calls = checked(STAGE2 / "BROKER_REPORTS_DOC22_CALL_ACCOUNTING.safe.json")
    assert calls["phase_a_new_provider_calls_total"] == 0
    assert calls["phase_b_qualification_generation_calls_total"] == 1
    assert calls["phase_b_automated_starts_total"] == 48
    assert calls["phase_b_automated_attempts_total"] == 48
    assert calls["phase_b_automated_completed_total"] == 23
    assert calls["phase_b_automated_failed_total"] == 25
    assert calls["phase_b_total_generation_calls"] == 49
    assert calls["retry_total"] == 0
    assert calls["fallback_total"] == 0
    assert calls["repair_total"] == 0
    assert calls["slots_accounted_total"] == 48
    assert calls["unaccounted_case_ids"] == []


def test_doc22_report_has_terminal_fields_and_scope_stops() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for marker in (
        "DOC22_RESEARCH = COMPLETED",
        "FULL_GATE1_DOCUMENT_SUFFICIENCY = CONFIRMED",
        "PARSER_CONTEXT_RESCUE = SUBSTANTIAL",
        "AUTOMATED_AUDIT = BLOCKED",
        "CROP_RESEARCH_POLICY = DEFINE_MINIMUM_DOCUMENT_CONTEXT_CONTRACT",
        "GATE1_DOCUMENT_HANDOFF_AUDITED = TRUE",
        "RESEARCH_SHADOW_PACKAGE_CREATED_IF_NEEDED = TRUE",
        "NEW_PRODUCT_HANDOFF_CONTRACT_CREATED = FALSE",
        "DIRECT_CASES_TOTAL = 48",
        "FAILED_CASES_EXCLUDED = 0",
        "EXACT_ADAPTER_PREFLIGHT_PASSED = TRUE",
        "AUTOMATED_CASES_TOTAL = 48",
        "ALL_AUTOMATED_CALLS_ACCOUNTED = TRUE",
        "RETRY_TOTAL = 0",
        "FALSE_SAFE_TOTAL_REPORTED = TRUE",
        "GATE1_CHANGED = FALSE",
        "CROPPER_CHANGED = FALSE",
        "GATE2_CHANGED = FALSE",
        "GATE3_CREATED = FALSE",
        "PRODUCT_PIPELINE_ACTIVATED = FALSE",
    ):
        assert marker in report
