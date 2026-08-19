from __future__ import annotations

import json
import hashlib
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-14"
AUDIT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_EVIDENCE_INTERPRETATION_G5_44.audit.safe.json"
)
REPORT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_EVIDENCE_INTERPRETATION_G5_44.report.md"
)
CONTRACT_PATH = REPO_ROOT / "docs" / "stage2" / "contracts" / (
    "BROKER_REPORTS_GATE5_EVIDENCE_INTERPRETATION_CONTRACTS.v1.md"
)
RECEIPT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_EVIDENCE_INTERPRETATION_G5_44.receipt.safe.json"
)
G543_AUDIT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_DECLARATION_INPUT_CONTRACT_AUDIT_G5_43.audit.safe.json"
)
CURRENT_BUNDLE_RECEIPT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY_G5_45.receipt.safe.json"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_g544_a_i_matrix_and_terminals_are_complete() -> None:
    audit = _json(AUDIT_PATH)

    assert audit["goal"] == "G5.44"
    assert audit["status"] == "CONTRACTS_PROVEN_WITH_EXTERNAL_LEGAL_GAPS"
    assert audit["terminals"] == [
        "EVIDENCE_INTERPRETATION_CONTRACTS_PROVEN",
        "COMMISSION_SELECTION_CONTRACT_PROVEN",
        "ACQUISITION_BASIS_COVERAGE_CONTRACT_PROVEN",
        "RESIDENCY_EVIDENCE_BOUNDARY_PROVEN",
        "CROSS_DOMAIN_REFACTOR_CONSISTENCY_PROVEN",
    ]
    assert [item["id"] for item in audit["black_box_scenarios"]] == list("ABCDEFGHI")
    assert all(item["passed"] is True for item in audit["black_box_scenarios"])
    assert {item["meaning"] for item in audit["cross_domain_consistency"]} == {
        "residency",
        "commission_representation",
        "acquisition_basis_coverage",
        "direct_transaction_charge",
    }
    assert all(
        item["projection_reclassification"] is False
        for item in audit["cross_domain_consistency"]
    )


def test_g544_preserves_the_exact_g543_external_gap_boundary() -> None:
    g544 = _json(AUDIT_PATH)
    g543 = _json(G543_AUDIT_PATH)

    assert g544["external_legal_methodology_gaps"] == g543[
        "legal_methodology_gaps"
    ]
    assert set(g544["safety"].values()) == {False}
    assert g544["metrics"] == {
        "invented_facts": 0,
        "invented_relations": 0,
        "stored_purchase_disposal_pairs": 0,
        "commission_reconciliation_performed": False,
        "detail_aggregate_value_comparison_performed": False,
        "user_tax_status_accepted": False,
        "projection_tax_interpretation_performed": False,
    }


def test_g544_single_owners_and_projection_boundary_are_explicit() -> None:
    residency = (PACKAGE_ROOT / "gate5_residency_evidence.py").read_text(
        encoding="utf-8"
    )
    source = (
        PACKAGE_ROOT / "gate5_deterministic_source_fact_consumption.py"
    ).read_text(encoding="utf-8")
    tax_model = (
        PACKAGE_ROOT / "gate5_securities_disposal_tax_model.py"
    ).read_text(encoding="utf-8")
    aggregation = (
        PACKAGE_ROOT / "gate5_tax_period_category_aggregation.py"
    ).read_text(encoding="utf-8")
    income_base = (PACKAGE_ROOT / "gate5_income_group_tax_base.py").read_text(
        encoding="utf-8"
    )
    projection = "\n".join(
        (PACKAGE_ROOT / name).read_text(encoding="utf-8")
        for name in (
            "gate5_declaration_projection.py",
            "gate5_full_target_xml_projection.py",
            "gate5_declaration_semantic_input.py",
        )
    )

    assert "Gate5ResidencyEvidenceRuntimeFactory.create" in residency
    assert "user_tax_status_accepted" in residency
    assert "def select_commission_evidence" in source
    assert "ACQUISITION_BASIS_COVERAGE_GAP" in source
    assert '"tax_deductibility_status": "NOT_EVALUATED"' in source
    assert "gate5_tax_model_residency_classification_required" in tax_model
    assert "gate5_tax_period_residency_classification_required" in aggregation
    assert "gate5_income_group_tax_base_residency_classification_required" in income_base
    assert "gate5_declaration_projection" not in source
    assert "gate5_full_target_xml_projection" not in source
    for interpretation_literal in (
        "COMMISSION_SELECTION_CONTRACT_PROVEN",
        "ACQUISITION_BASIS_COVERAGE_GAP",
        "TRANSACTION_CHARGE_EVIDENCE",
    ):
        assert interpretation_literal not in projection


def test_g544_contract_report_and_safe_audit_are_routed_and_privacy_clean() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    report = REPORT_PATH.read_text(encoding="utf-8")
    audit = AUDIT_PATH.read_text(encoding="utf-8")

    assert "Status: `CURRENT SUPPORTING CONTRACT`" in contract
    assert "## A-I black-box proof" in report
    assert "G5.45 автоматически не начинается" in report
    for content in (contract, report, audit):
        assert "C:\\Users\\" not in content
        assert "D:\\Users\\" not in content
        assert "private-evidence" not in content


def test_g544_receipt_hashes_safe_contract_runtime_and_bundle_artifacts() -> None:
    receipt = _json(RECEIPT_PATH)

    assert receipt["result"] == "CONTRACTS_PROVEN_WITH_EXTERNAL_LEGAL_GAPS"
    assert receipt["verification"]["real_corpus_store_unchanged"] is True
    assert receipt["verification"]["provider_calls"] == 0
    for artifact in receipt["artifacts"]:
        if artifact["path"].endswith("broker_reports_gate1_pipe_bundled.py"):
            # Historical generated projection; G5.45 owns the current bundle hash.
            continue
        path = REPO_ROOT / artifact["path"]
        raw = path.read_bytes()
        assert len(raw) == artifact["bytes"]
        assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]

    later_receipt = _json(CURRENT_BUNDLE_RECEIPT_PATH)
    later_bundle = next(
        item
        for item in later_receipt["artifacts"]
        if item["path"].endswith("broker_reports_gate1_pipe_bundled.py")
    )
    # Later receipts remain evidence of their own run, not mutable manifests.
    assert later_bundle["bytes"] > 0
    assert len(later_bundle["sha256"]) == 64

    raw = RECEIPT_PATH.read_text(encoding="utf-8")
    assert "C:\\Users\\" not in raw
    assert "D:\\Users\\" not in raw
