from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STAGE2 = ROOT / "docs" / "stage2"
REPORTS = ROOT / "docs" / "reports" / "2026-08-04"
SAFE_FILES = (
    STAGE2 / "BROKER_REPORTS_DOC19_FINANCIAL_SUFFICIENCY_RESULTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC19_CROP_CLASS_EFFECT.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC19_CRITICAL_CONTEXT_LOSSES.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC19_CALL_ACCOUNTING.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC19_DECISION.safe.json",
    REPORTS / "BROKER_REPORTS_DOC19_GATE1_TO_GATE3_FINANCIAL_SUFFICIENCY.report.md",
    REPORTS / "BROKER_REPORTS_DOC19_GATE1_TO_GATE3_FINANCIAL_SUFFICIENCY_BRIEF.md",
)
RECEIPT = (
    REPORTS
    / "BROKER_REPORTS_DOC19_GATE1_TO_GATE3_FINANCIAL_SUFFICIENCY.receipt.safe.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_doc19_records_the_required_missing_gate3_contract_stop():
    results = _load(SAFE_FILES[0])
    decision = _load(SAFE_FILES[4])
    receipt = _load(RECEIPT)

    assert results["DOC19_EXPERIMENT"] == "BLOCKED"
    assert results["DOC19_RESULT"] == "BLOCKED_MISSING_GATE3_CONTRACT"
    assert results["metrics_reported"] is False
    assert all(
        arm["cases_evaluated"] == 0
        and arm["financial_fact_recall"] is None
        and arm["financial_fact_precision"] is None
        for arm in results["gate1_artifacts"].values()
    )

    assert decision["existing_gate3_architecture_audited"] is True
    assert decision["existing_gate3_contract_reused"] is False
    assert decision["compatible_existing_gate3_extractor_found"] is False
    assert decision["compatible_existing_gate3_contract_found"] is False
    assert decision["new_financial_fact_contracts_created"] == 0
    assert decision["GATE1_FINANCIAL_SUFFICIENCY"] == "INCONCLUSIVE"
    assert decision["BEST_GATE1_ARTIFACT"] == "NOT_EVALUATED"
    assert decision["CROP_RESEARCH_POLICY"] == "INCONCLUSIVE"
    assert receipt["DOC19_RESULT"] == "BLOCKED_MISSING_GATE3_CONTRACT"


def test_doc19_preserves_all_inputs_without_claiming_an_experiment_freeze():
    results = _load(SAFE_FILES[0])
    crop_effect = _load(SAFE_FILES[1])
    decision = _load(SAFE_FILES[4])

    assert results["tables_total"] == 24
    assert results["gate1_artifact_arms_total"] == 2
    assert results["extraction_cases_total"] == 48
    assert results["verification_cases_total"] == 48
    assert all(
        arm["cases_available"] == 24
        for arm in results["gate1_artifacts"].values()
    )
    assert crop_effect["crop_classes_preserved"] is True
    assert crop_effect["class_counts"] == {
        "CROP_CLEAN": 12,
        "CROP_CLIPPED": 7,
        "CROP_CONTAMINATED": 5,
    }
    assert crop_effect["evaluated_cases_total"] == 0
    assert crop_effect["effect"] == "NOT_EVALUATED"
    assert decision["full_pages_used_as_verification_source"] is False


def test_doc19_call_accounting_is_an_honest_precall_stop():
    accounting = _load(SAFE_FILES[3])

    assert accounting["expected_extraction_calls_total"] == 48
    assert accounting["expected_verifier_calls_total"] == 48
    assert accounting["expected_base_calls_total"] == 96
    assert accounting["started_calls_total"] == 0
    assert accounting["attempts_total"] == 0
    assert accounting["completed_calls_total"] == 0
    assert accounting["failed_calls_total"] == 0
    assert accounting["adjudication_calls_total"] == 0
    assert accounting["retry_total"] == 0
    assert accounting["fallback_total"] == 0
    assert accounting["repair_total"] == 0
    assert accounting["failed_tables_excluded_total"] == 0
    assert accounting["started_calls_accounted"] is True
    assert accounting["all_base_calls_accounted"] is False
    assert accounting["stop_before_first_provider_call"] is True
    assert accounting["stop_reason"] == "BLOCKED_MISSING_GATE3_CONTRACT"


def test_doc19_does_not_relabel_unevaluated_losses_as_zero_loss():
    losses = _load(SAFE_FILES[2])

    assert losses["critical_context_losses"] == []
    assert losses["critical_context_loss_reported"] is False
    assert losses["root_causes_reported"] is False
    assert losses["empty_list_meaning"] == "NOT_EVALUATED"


def test_doc19_receipt_binds_every_published_artifact_and_audited_source():
    receipt = _load(RECEIPT)
    for path in SAFE_FILES:
        relative = path.relative_to(ROOT).as_posix()
        assert receipt["artifact_sha256"][relative] == _sha256(path)

    for relative, expected_hash in receipt["audited_source_sha256"].items():
        assert _sha256(ROOT / relative) == expected_hash


def test_doc19_safe_artifacts_contain_no_private_payload_or_machine_paths():
    forbidden = (
        "data:image/png;base64",
        "local/stage2",
        "C:\\Users",
        "D:\\Users",
        "provider_response_private",
        "parser_text",
        "bbox_normalized",
        "bbox_points",
        "candidate_bbox",
    )
    for path in (*SAFE_FILES, RECEIPT):
        text = path.read_text(encoding="utf-8")
        assert all(token.lower() not in text.lower() for token in forbidden), path.name


def test_doc19_gate3_product_boundary_still_forbids_direct_gate1_input():
    gate3_context = (
        ROOT
        / "services"
        / "broker-reports-gate1-proof"
        / "broker_reports_gate1"
        / "gate3_financial_domain_context.py"
    ).read_text(encoding="utf-8")
    gate3_manifest = (
        ROOT
        / "services"
        / "broker-reports-gate1-proof"
        / "broker_reports_gate1"
        / "gate3_context_manifest.py"
    ).read_text(encoding="utf-8")

    assert "source documents, Gate 1 payloads" in gate3_context
    assert "context_manifest_is_not_gate3_business_logic" in gate3_manifest
    assert "Extractor" not in gate3_context
    assert "Extractor" not in gate3_manifest
