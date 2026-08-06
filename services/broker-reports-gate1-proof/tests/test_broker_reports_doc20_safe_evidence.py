from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STAGE2 = ROOT / "docs" / "stage2"
REPORTS = ROOT / "docs" / "reports" / "2026-08-04"
SAFE_FILES = (
    STAGE2 / "BROKER_REPORTS_DOC20_MATERIAL_SUFFICIENCY_RESULTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC20_CRITICAL_CONTEXT_LOSSES.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC20_CROP_CLASS_EFFECT.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC20_PROVIDER_COMPARISON.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC20_MINIMUM_GATE1_CONTRACT.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC20_CALL_ACCOUNTING.safe.json",
    REPORTS / "BROKER_REPORTS_DOC20_GATE1_MATERIAL_SUFFICIENCY_AUDIT.report.md",
    REPORTS / "BROKER_REPORTS_DOC20_GATE1_MATERIAL_SUFFICIENCY_AUDIT_BRIEF.md",
)
RECEIPT = (
    REPORTS / "BROKER_REPORTS_DOC20_GATE1_MATERIAL_SUFFICIENCY_AUDIT.receipt.safe.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_doc20_preserves_research_only_and_product_boundaries():
    results = _load(SAFE_FILES[0])
    receipt = _load(RECEIPT)

    assert results["doc20_research_only"] is True
    assert receipt["DOC20_RESEARCH_ONLY"] is True
    assert receipt["GATE3_CONTRACT_CREATED"] is False
    assert receipt["FINANCIAL_FACT_EXTRACTOR_CREATED"] is False
    assert receipt["GATE1_CHANGED"] is False
    assert receipt["CROPPER_CHANGED"] is False
    assert receipt["GATE2_CHANGED"] is False
    assert receipt["GATE3_IMPLEMENTED"] is False
    assert receipt["PRODUCT_PIPELINE_ACTIVATED"] is False


def test_doc20_frozen_corpus_and_verifier_inputs_are_fully_accounted():
    results = _load(SAFE_FILES[0])
    crop = _load(SAFE_FILES[2])
    receipt = _load(RECEIPT)

    assert results["tables_total"] == 24
    assert results["gate1_artifacts_per_table"] == 2
    assert results["audit_cases_total"] == 48
    assert all(
        arm["cases_available"] == 24
        for arm in results["gate1_artifacts"].values()
    )
    assert crop["crop_classes_preserved"] is True
    assert crop["class_counts"] == {
        "CROP_CLEAN": 12,
        "CROP_CLIPPED": 7,
        "CROP_CONTAMINATED": 5,
    }
    assert receipt["FULL_PAGES_USED"] is True
    assert receipt["TARGET_OVERLAYS_USED"] is True
    assert receipt["PROMPT_FROZEN_BEFORE_CALLS"] is True
    assert receipt["SCHEMA_FROZEN_BEFORE_CALLS"] is True
    assert receipt["VERIFIER_FROZEN_BEFORE_CALLS"] is True
    assert receipt["CONTROL_SAMPLE_FROZEN_BEFORE_CALLS"] is True


def test_doc20_records_terminal_provider_incompatibility_without_retry():
    accounting = _load(SAFE_FILES[5])
    results = _load(SAFE_FILES[0])
    receipt = _load(RECEIPT)

    assert accounting["expected_base_calls_total"] == 48
    assert accounting["started_calls_total"] == 48
    assert accounting["attempts_total"] == 48
    assert accounting["accounted_calls_total"] == 48
    assert accounting["completed_content_calls_total"] == 0
    assert accounting["failed_calls_total"] == 48
    assert accounting["http_400_total"] == 48
    assert accounting["structured_output_valid_total"] == 0
    assert accounting["raw_verdicts_total"] == 0
    assert accounting["retry_total"] == 0
    assert accounting["fallback_total"] == 0
    assert accounting["repair_total"] == 0
    assert accounting["failed_cases_excluded_total"] == 0
    assert accounting["all_base_calls_accounted"] is True
    assert accounting["failure_class_counts"] == {
        "FROZEN_ADAPTER_MODEL_PARAMETER_INCOMPATIBILITY": 48
    }
    assert accounting["failure_parameter"] == "temperature"
    assert results["DOC20_EXPERIMENT"] == "BLOCKED"
    assert results["DOC20_RESULT"] == "BLOCKED_VERIFIER_ADAPTER_MODEL_INCOMPATIBILITY"
    assert receipt["calls_accounted"] == "48/48"
    assert receipt["content_verdicts"] == "0/48"


def test_doc20_does_not_invent_content_metrics_or_acceptance():
    results = _load(SAFE_FILES[0])
    losses = _load(SAFE_FILES[1])
    crop = _load(SAFE_FILES[2])
    comparison = _load(SAFE_FILES[3])
    minimum = _load(SAFE_FILES[4])
    receipt = _load(RECEIPT)

    assert results["content_cases_evaluated_total"] == 0
    assert results["metrics_reported"] is False
    assert results["GATE1_MATERIAL_SUFFICIENCY"] == "INCONCLUSIVE"
    assert results["BEST_GATE1_ARTIFACT"] == "NOT_EVALUATED"
    assert results["CROP_RESEARCH_POLICY"] == "INCONCLUSIVE"
    assert all(
        arm["verdict_counts"] is None
        and arm["material_sufficiency_rate"] is None
        and arm["critical_loss_rate"] is None
        for arm in results["gate1_artifacts"].values()
    )
    assert losses["critical_context_losses"] == []
    assert losses["empty_list_meaning"] == "NOT_EVALUATED"
    assert crop["effect"] == "NOT_EVALUATED"
    assert crop["case_specific_crop_rules_created"] == 0
    assert comparison["provider_comparison_reported"] is False
    assert comparison["hidden_weighted_score_created"] is False
    assert minimum["minimum_gate1_contract"] == []
    assert minimum["empty_list_meaning"] == "NOT_EVALUATED"
    assert receipt["ALL_CRITICAL_CASES_ADJUDICATED"] is False
    assert receipt["CONTROL_SAMPLE_ADJUDICATED"] is False
    assert receipt["MATERIAL_SUFFICIENCY_REPORTED"] is False


def test_doc20_receipt_binds_every_published_artifact_and_provider_source():
    receipt = _load(RECEIPT)
    for path in SAFE_FILES:
        relative = path.relative_to(ROOT).as_posix()
        assert receipt["artifact_sha256"][relative] == _sha256(path)
    for relative, expected in receipt["audited_source_sha256"].items():
        assert _sha256(ROOT / relative) == expected


def test_doc20_safe_artifacts_contain_no_private_payload_or_machine_paths():
    forbidden = (
        "data:image/png;base64",
        "local/stage2",
        "C:\\Users",
        "D:\\Users",
        "provider_response_private",
        "raw_private_response",
        "api_key",
        "bbox_points",
        "gate1_json",
    )
    for path in (*SAFE_FILES, RECEIPT):
        text = path.read_text(encoding="utf-8")
        assert all(token.lower() not in text.lower() for token in forbidden), path.name


def test_doc20_existing_provider_factory_anti_drift_anchors_remain_present():
    source = (
        ROOT
        / "services"
        / "broker-reports-gate1-proof"
        / "broker_reports_gate1"
        / "pdf_dual_vlm_fact_providers.py"
    ).read_text(encoding="utf-8")

    assert "PdfDualVlmFactProviderFactory.create_for_openwebui" in source
    assert "must not construct provider payloads" in source
    assert '"temperature": 0' in source
