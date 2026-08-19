from __future__ import annotations

import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-14"
CONTRACT_PATH = REPO_ROOT / "docs" / "stage2" / "contracts" / (
    "BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY.v1.md"
)
REPORT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY_G5_45.report.md"
)
AUDIT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY_G5_45.audit.safe.json"
)
RECEIPT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY_G5_45.receipt.safe.json"
)
AUTHORITIES_PATH = REPO_ROOT / "docs" / "stage2" / "contracts" / (
    "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md"
)


def test_g545_contract_report_and_audit_are_routed_current_and_privacy_clean() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    report = REPORT_PATH.read_text(encoding="utf-8")
    audit = AUDIT_PATH.read_text(encoding="utf-8")
    receipt = RECEIPT_PATH.read_text(encoding="utf-8")
    authorities = AUTHORITIES_PATH.read_text(encoding="utf-8")

    assert "Status: `CURRENT SUPPORTING CONTRACT`" in contract
    assert "## A–I black-box proof" in report
    assert "DECLARATION_VALUE_TRACEABILITY_PROVEN" in audit
    assert CONTRACT_PATH.name in authorities
    for content in (contract, report, audit, receipt):
        assert "C:" + "\\Users\\" not in content
        assert "D:" + "\\Users\\" not in content
        assert "private-evidence" not in content


def test_g545_safe_audit_proves_exact_inventory_and_real_case_gap_classes() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

    assert audit["status"] == "DECLARATION_MODEL_ASSEMBLY_PROVEN"
    assert audit["consumer_inventory"] == {
        "emitted_value_count": 49,
        "released_semantic_value_count": 44,
        "released_semantic_values_consumed": 44,
        "official_constant_count": 4,
        "target_mechanics_count": 1,
        "unconsumed_released_semantic_value_count": 0,
        "unknown_origin_count": 0,
        "unowned_value_count": 0,
    }
    assert len(audit["adversarial_tests"]) == 9
    assert all(row["passed"] is True for row in audit["adversarial_tests"])
    assert audit["real_corpus_replay"]["terminal_counts"] == {
        "MISSING_EVIDENCE": 4,
        "SOURCE_EVIDENCE_INSUFFICIENT": 1,
        "METHODOLOGY_UNRESOLVED": 4,
    }
    assert audit["real_corpus_replay"]["model_gap_count"] == 0


def test_g545_receipt_preserves_historical_safe_artifact_manifest() -> None:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert receipt["result"] == "DECLARATION_MODEL_ASSEMBLY_PROVEN"
    assert receipt["verification"]["real_corpus_store_unchanged"] is True
    assert receipt["verification"]["provider_calls"] == 0
    for artifact in receipt["artifacts"]:
        assert artifact["bytes"] > 0
        assert len(artifact["sha256"]) == 64
        assert (REPO_ROOT / artifact["path"]).exists()
