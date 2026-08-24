from __future__ import annotations

import hashlib
import json
from pathlib import Path

from broker_reports_gate1 import (
    GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
    GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE,
    GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE_SHA256,
    GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthorityFactory,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
AUDIT_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-14"
    / "BROKER_REPORTS_GATE5_DECLARATION_INPUT_CONTRACT_AUDIT_G5_43.audit.safe.json"
)
REPORT_PATH = AUDIT_PATH.with_name(
    "BROKER_REPORTS_GATE5_DECLARATION_INPUT_CONTRACT_AUDIT_G5_43.report.md"
)
RECEIPT_PATH = AUDIT_PATH.with_name(
    "BROKER_REPORTS_GATE5_DECLARATION_INPUT_CONTRACT_AUDIT_G5_43.receipt.safe.json"
)
CURRENT_BUNDLE_RECEIPT_PATH = AUDIT_PATH.with_name(
    "BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY_G5_45.receipt.safe.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_GATE5_EVIDENCE_TAX_METHODOLOGY_BRIDGE.v1.md"
)
AUTHORITIES_PATH = CONTRACT_PATH.with_name(
    "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md"
)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_g543_safe_audit_has_exact_partial_terminal_and_closed_gap_classes() -> None:
    audit = _load_json(AUDIT_PATH)

    assert audit["schema_version"] == (
        "broker_reports_gate5_declaration_input_contract_audit_g5_43_v1"
    )
    assert audit["goal"] == "G5.43"
    assert audit["terminals"] == [
        "EVIDENCE_REQUIREMENTS_CONTRACT_PROVEN",
        "FACT_TO_METHODOLOGY_BRIDGE_PROVEN",
        "DECLARATION_INPUT_CORE_PROVEN",
    ]
    assert audit["full_terminal_claimed"] is False
    assert audit["legal_methodology_gaps"] == [
        "ambiguous_security_disposal_source_classification",
        "partial_acquisition_commission_allocation",
        "non_rub_intermediate_precision_and_rounding",
        "treaty_specific_foreign_tax_credit_limit",
    ]

    assert len(audit["evidence_map"]) == 15
    assert len(audit["methodology_map"]) == 9
    assert len(audit["bridge_matrix"]) == 15
    assert len(audit["gap_register"]) == 14
    assert {row["class"] for row in audit["gap_register"]} <= {
        "SOURCE",
        "INTAKE",
        "CONTRACT",
        "METHODOLOGY",
        "USER/CASE",
    }
    assert len({row["gap_id"] for row in audit["gap_register"]}) == 14

    corpus = audit["corpus"]
    assert corpus["documents"] == 4
    assert corpus["source_present_required_facts_lost"] == 0
    assert corpus["invented_source_facts"] == 0
    assert corpus["invented_relations"] == 0
    assert corpus["provenance_complete"] is True

    replay = audit["preparation_replay"]
    assert replay == {
        "status": "PREPARATION_INCOMPLETE",
        "active_declaration_demands": 9,
        "active_demands_with_methodology_binding": 9,
        "terminal_counts": {
            "MISSING_EVIDENCE": 4,
            "METHODOLOGY_UNRESOLVED": 4,
            "SOURCE_EVIDENCE_INSUFFICIENT": 1,
        },
        "inactive_demands": 16,
        "known_document_facts_reused": 2,
        "unnecessary_user_questions": 0,
        "unresolved_values_without_exact_reason": 0,
        "frozen_store_unchanged": True,
    }

    safety = audit["safety"]
    assert set(safety.values()) == {False}


def test_g543_methodology_resource_and_all_active_demand_bindings_are_pinned() -> None:
    resource_path = PACKAGE_ROOT / GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE
    resource_bytes = resource_path.read_bytes()
    methodology = json.loads(resource_bytes.decode("utf-8"))

    assert methodology["methodology_id"] == GATE5_DECLARATION_INPUT_METHODOLOGY_ID
    assert methodology["methodology_version"] == (
        GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION
    )
    assert hashlib.sha256(resource_bytes).hexdigest() == (
        GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE_SHA256
    )
    assert len(methodology["rules"]) == 13
    category_rule = next(
        row
        for row in methodology["rules"]
        if row["rule_id"] == "declarant-category-fns-order-913-v1"
    )
    assert category_rule["operation"] == "CLASSIFY"
    assert category_rule["output"] == (
        "other_individual_declaring_article_228_income"
    )
    assert category_rule["insufficient_inputs"] == (
        "EXTERNAL_AUTHORITATIVE_FACT_MISSING"
    )
    assert len(methodology["demand_bindings"]) == 9
    assert {row["demand"] for row in methodology["demand_bindings"]} == {
        row["declaration_demand"] for row in _load_json(AUDIT_PATH)["methodology_map"]
    }


def test_current_foreign_tax_consumer_requires_article_232_document_role() -> None:
    methodology = Gate5TrustedMethodologyAuthorityFactory.create().resolve(
        {
            "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
            "methodology_id": GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
            "methodology_version": GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
        }
    )["methodology"]
    rule = next(
        row
        for row in methodology["rules"]
        if row["rule_id"] == "foreign-tax-credit-articles-214-232-v3"
    )

    assert rule["required_inputs"] == [
        "resident_status",
        "foreign_income_kind_amount_and_year",
        "foreign_tax_amount_and_payment_date",
        "foreign_tax_authority_or_withholding_source_document",
        "withholding_document_issuer_role_and_monthly_income_tax_details",
        "required_translation",
        "applicable_tax_treaty",
    ]
    assert rule["insufficient_inputs"] == "EXTERNAL_AUTHORITATIVE_FACT_MISSING"
    assert "issuer is the income payment source" in rule["deterministic_rule"]
    assert "foreign withholding alone is not a credit" in rule["deterministic_rule"]
    serialized = json.dumps(rule, sort_keys=True)
    assert "adjustment, refund and reversal observations remain separate" in serialized
    assert "reviewed netting rule" in serialized


def test_g543_contract_report_and_authority_routing_preserve_the_scope_stop() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    report = REPORT_PATH.read_text(encoding="utf-8")
    authorities = AUTHORITIES_PATH.read_text(encoding="utf-8")

    assert "Status: `CURRENT SUPPORTING CONTRACT`" in contract
    assert "Gate5TrustedMethodologyAuthorityFactory.create" in contract
    assert "It must not claim `TAX_METHODOLOGY_CONTRACT_PROVEN`" in contract
    assert "## 1. Evidence Map" in report
    assert "## 2. Methodology Map" in report
    assert "## 3. Bridge Matrix" in report
    assert "## 4. Gap Register" in report
    assert "`TAX_METHODOLOGY_CONTRACT_PROVEN`" in report
    assert "не заявлены" in report
    assert "normalization нет LLM tax reasoning" in report
    assert CONTRACT_PATH.name in authorities

    combined = contract + report + AUDIT_PATH.read_text(encoding="utf-8")
    assert "C:\\Users\\" not in combined
    assert "D:\\Users\\" not in combined
    assert "private-evidence" not in combined


def test_g543_receipt_hashes_only_safe_artifacts_and_preserves_scope_stop() -> None:
    receipt = _load_json(RECEIPT_PATH)

    assert receipt["result"] == "PARTIAL_TERMINAL_ACCEPTED"
    assert receipt["full_terminal_claimed"] is False
    assert receipt["real_corpus_replay"]["terminal_counts"] == {
        "MISSING_EVIDENCE": 4,
        "METHODOLOGY_UNRESOLVED": 4,
        "SOURCE_EVIDENCE_INSUFFICIENT": 1,
    }
    for artifact in receipt["artifacts"]:
        if artifact["path"].endswith(
            "BROKER_REPORTS_GATE5_EVIDENCE_TAX_METHODOLOGY_BRIDGE.v1.md"
        ):
            # The receipt preserves the exact G5.43 revision. The maintained
            # owner is intentionally additive and now carries the G5.90 legal
            # interpretation stop without rewriting the historical receipt.
            assert artifact == {
                "path": (
                    "docs/stage2/contracts/"
                    "BROKER_REPORTS_GATE5_EVIDENCE_TAX_METHODOLOGY_BRIDGE.v1.md"
                ),
                "bytes": 6176,
                "sha256": (
                    "61d83043133d6d4d02b82058a87ff53faafd9a7ddb88905a0d3d69bdaac429bb"
                ),
            }
            current_contract = CONTRACT_PATH.read_text(encoding="utf-8")
            assert "FOREIGN_TAX_ADJUSTMENT_METHODOLOGY_GAP_LOCALIZED" in (
                current_contract
            )
            assert "METHODOLOGY_LEGAL_INTERPRETATION_REVIEW_REQUIRED" in (
                current_contract
            )
            continue
        if artifact["path"].endswith("broker_reports_gate1_pipe_bundled.py"):
            # This is a historical generated projection, not an immutable G5.43
            # authority. G5.45 intentionally rebuilds it and owns the current hash.
            assert artifact["sha256"] == (
                "f5db4efdfa9c69a2e5d1319b2260805b3690fc7b019d8ad6fa1a7ac7e571fc3d"
            )
            continue
        path = REPO_ROOT / artifact["path"]
        content = path.read_bytes()
        if path.suffix in {".json", ".md", ".py"}:
            content = content.replace(b"\r\n", b"\n")
        assert len(content) == artifact["bytes"]
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]

    later_receipt = _load_json(CURRENT_BUNDLE_RECEIPT_PATH)
    later_bundle = next(
        item
        for item in later_receipt["artifacts"]
        if item["path"].endswith("broker_reports_gate1_pipe_bundled.py")
    )
    # Both receipts are immutable historical evidence. G5.50 legitimately
    # rebuilds the bundle, so neither receipt is a current-file manifest.
    assert later_bundle["bytes"] > 0
    assert len(later_bundle["sha256"]) == 64
    assert later_bundle["sha256"] != receipt["artifacts"][-1]["sha256"]

    assert set(receipt["safety"].values()) == {False}
    raw = RECEIPT_PATH.read_text(encoding="utf-8")
    assert "C:\\Users\\" not in raw
    assert "D:\\Users\\" not in raw
