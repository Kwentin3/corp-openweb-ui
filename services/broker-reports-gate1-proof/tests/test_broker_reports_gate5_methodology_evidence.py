from __future__ import annotations

import hashlib
import json
from pathlib import Path

from broker_reports_gate1.gate5_evidence_demand_contract import (
    Gate5EvidenceDemandContractAuthorityFactory,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-14"
AUDIT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_METHODOLOGY_EVIDENCE_G5_46.audit.safe.json"
)
MATRIX_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_METHODOLOGY_EVIDENCE_G5_46.matrix.safe.json"
)
RECEIPT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_METHODOLOGY_EVIDENCE_G5_46.receipt.safe.json"
)
REPORT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_METHODOLOGY_EVIDENCE_G5_46.report.md"
)
CONTRACT_PATH = REPO_ROOT / "docs" / "stage2" / "contracts" / (
    "BROKER_REPORTS_GATE5_METHODOLOGY_DRIVEN_EVIDENCE_DEMAND.v1.md"
)
G545_RECEIPT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY_G5_45.receipt.safe.json"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_bounded_contract_covers_current_methodology_without_ontology_growth() -> None:
    contract = Gate5EvidenceDemandContractAuthorityFactory.create().resolve()
    rows = contract["fact_contracts"]
    recoveries = {
        item["source_fact_request"]["fact_type"]
        for item in rows
        if item["source_fact_request"] is not None
    }

    assert len(rows) == 43
    assert len({item["required_input"] for item in rows}) == 43
    assert recoveries == {
        "PAYER_ORGANIZATION_IDENTITY",
        "PAYER_ORGANIZATION_JURISDICTION",
        "REALIZATION_LOCATION_JURISDICTION",
    }
    assert contract["generic_ontology"] is False
    assert contract["extract_without_named_consumer"] is False


def test_real_audit_classifies_every_active_requirement_and_preserves_terminals() -> None:
    audit = _json(AUDIT_PATH)
    real = audit["real_corpus"]

    assert audit["status"] == "PROVEN_WITH_REAL_FACT_CONTRACT_GAPS_LOCALIZED"
    assert audit["terminals"] == [
        "METHODOLOGY_DRIVEN_EVIDENCE_DEMAND_PROVEN",
        "CANONICAL_FACT_RECOVERY_PROVEN",
        "PREMATURE_GAP_DECLARATION_ELIMINATED",
        "EVIDENCE_AUTHORITY_ROUTING_PROVEN",
        "CROSS_DOMAIN_EVIDENCE_DEMAND_CONSISTENCY_PROVEN",
    ]
    assert [item["id"] for item in audit["black_box_scenarios"]] == list(
        "ABCDEFGHI"
    )
    assert all(item["passed"] is True for item in audit["black_box_scenarios"])
    assert real == {
        "active_evidence_requirements": 50,
        "active_rules": 9,
        "canonical_nodes": 295,
        "canonical_source_atoms": 8243,
        "classification_counts": {
            "ADDITIONAL_DOCUMENT_REQUIRED": 0,
            "EXTERNAL_REFERENCE_FACT_REQUIRED": 4,
            "FACT_AVAILABLE": 4,
            "FACT_RECOVERED_FROM_CANONICAL": 0,
            "METHODOLOGY_UNRESOLVED": 2,
            "SOURCE_DOES_NOT_PROVE_REQUIRED_FACT": 0,
            "SOURCE_FACT_CONTRACT_MISSING": 32,
            "USER_CASE_FACT_REQUIRED": 8,
        },
        "documents": 4,
        "frozen_store_unchanged": True,
        "normalized_facts": 201,
        "provider_calls": 0,
        "recovered_facts": 0,
    }
    assert sum(real["classification_counts"].values()) == 50


def test_safe_matrix_has_named_consumers_and_exact_authority_routes() -> None:
    matrix = _json(MATRIX_PATH)
    rows = matrix["rows"]

    assert len(rows) == 50
    assert all(item["consumers"] for item in rows)
    assert all(
        item["action"]
        in {
            "FACT_AVAILABLE",
            "FACT_RECOVERED_FROM_CANONICAL",
            "SOURCE_DOES_NOT_PROVE_REQUIRED_FACT",
            "SOURCE_FACT_CONTRACT_MISSING",
            "USER_CASE_FACT_REQUIRED",
            "EXTERNAL_REFERENCE_FACT_REQUIRED",
            "ADDITIONAL_DOCUMENT_REQUIRED",
            "METHODOLOGY_UNRESOLVED",
        }
        for item in rows
    )
    assert matrix["classification_counts"] == _json(AUDIT_PATH)["real_corpus"][
        "classification_counts"
    ]
    cbr = next(
        item
        for item in rows
        if item["required_fact"] == "cbr_official_rate_for_currency_and_date"
    )
    residency = next(
        item
        for item in rows
        if item["required_fact"]
        == "authenticated_presence_days_in_rf_for_12_consecutive_month_window"
    )
    assert cbr["preferred_authority"] == "EXTERNAL_REFERENCE"
    assert cbr["canonical_documents_checked"] == 0
    assert residency["preferred_authority"] == "USER_CASE"
    assert residency["canonical_documents_checked"] == 0


def test_before_after_suppresses_premature_documents_without_marking_them_resolved() -> None:
    before_after = _json(AUDIT_PATH)["before_after_required_actions"]

    assert before_after["before"] == {
        "client_required_actions": 12,
        "closure_type_counts": {"ADDITIONAL_DOCUMENT": 8, "USER_FACT": 4},
    }
    assert before_after["after"] == {
        "client_required_actions": 4,
        "closure_type_counts": {"USER_FACT": 4},
        "routed_external_reference_work": 0,
        "routed_methodology_work": 0,
        "suppressed_premature_document_requests": 8,
    }
    suppressed = [
        item
        for item in before_after["rows"]
        if item["kind"] == "REQUIRED"
        and item["verdict"] == "SUPPRESS_PENDING_FACT_CONTRACT"
    ]
    assert len(suppressed) == 8
    assert all(
        "SOURCE_FACT_CONTRACT_MISSING" in item["evidence_classifications"]
        for item in suppressed
    )
    assert before_after["document_request_before_canonical_or_contract_check"] is False


def test_cross_domain_boundaries_and_four_legal_gaps_are_unchanged() -> None:
    audit = _json(AUDIT_PATH)
    consistency = audit["cross_domain_consistency"]

    assert audit["legal_methodology_gaps_remain"] == [
        "ambiguous_security_disposal_source_classification",
        "partial_acquisition_commission_allocation",
        "non_rub_intermediate_precision_and_rounding",
        "treaty_specific_foreign_tax_credit_limit",
    ]
    assert consistency["canonical_read_via_factory"] is True
    assert consistency["gate4_read_via_factory"] is True
    assert consistency["financial_event_relations_created"] == 0
    assert consistency["reconciliation_performed"] is False
    assert consistency["residency_evidence_boundary_changed"] is False
    assert consistency["commission_selection_contract_changed"] is False
    assert consistency["acquisition_basis_coverage_contract_changed"] is False
    assert consistency["declaration_semantic_model_changed"] is False
    assert consistency["projection_interpretation_added"] is False

    source = (PACKAGE_ROOT / "gate5_methodology_evidence.py").read_text(
        encoding="utf-8"
    )
    demand = (PACKAGE_ROOT / "gate5_evidence_demand.py").read_text(
        encoding="utf-8"
    )
    projection = (PACKAGE_ROOT / "gate5_full_target_xml_projection.py").read_text(
        encoding="utf-8"
    )
    assert "CanonicalReaderFactory(" not in source
    assert "Gate4FinancialCaseRuntimeFactory(" in source
    assert "direct SQL" in source
    assert "source_bytes_read\": False" in demand
    assert "canonical_documents" not in demand
    assert "gate5_evidence_demand" not in projection


def test_contract_report_and_safe_evidence_are_privacy_clean() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert "Status: `SUPERSEDED SUPPORTING EVIDENCE`" in contract
    assert "Classification: `HISTORICAL_ONLY" in contract
    assert "## A–I black-box proof" in report
    assert "G5.46 stops here" in report
    for path in (CONTRACT_PATH, REPORT_PATH, AUDIT_PATH, MATRIX_PATH, RECEIPT_PATH):
        content = path.read_text(encoding="utf-8")
        assert "C:\\Users\\" not in content
        assert "D:\\Users\\" not in content
        assert "private-evidence" not in content
        assert "g540e-private" not in content
        assert "normrun_" not in content


def test_historical_receipt_preserves_g545_boundary_without_claiming_current_hashes() -> None:
    receipt = _json(RECEIPT_PATH)

    assert receipt["result"] == "PROVEN_WITH_REAL_FACT_CONTRACT_GAPS_LOCALIZED"
    assert receipt["frozen_store_unchanged"] is True
    assert receipt["provider_calls"] == 0
    assert receipt["provider_reruns"] == 0
    assert receipt["ingestion_reruns"] == 0
    assert receipt["canonical_mutations"] == 0
    assert receipt["invented_facts"] == 0
    assert receipt["invented_relations"] == 0
    assert receipt["prior_g545_receipt_sha256"] == hashlib.sha256(
        G545_RECEIPT_PATH.read_bytes()
    ).hexdigest()
    assert all(item["bytes"] > 0 and len(item["sha256"]) == 64 for item in receipt["artifacts"])
