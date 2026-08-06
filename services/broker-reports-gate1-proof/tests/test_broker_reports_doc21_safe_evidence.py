from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STAGE2 = ROOT / "docs" / "stage2"
REPORTS = ROOT / "docs" / "reports" / "2026-08-04"
RESULTS = STAGE2 / "BROKER_REPORTS_DOC21_DIRECT_MATERIAL_ADEQUACY_RESULTS.safe.json"
LOSSES = STAGE2 / "BROKER_REPORTS_DOC21_CRITICAL_CONTEXT_LOSSES.safe.json"
CROP = STAGE2 / "BROKER_REPORTS_DOC21_CROP_CLASS_EFFECT.safe.json"
COMPARISON = STAGE2 / "BROKER_REPORTS_DOC21_PROVIDER_COMPARISON.safe.json"
MINIMUM = STAGE2 / "BROKER_REPORTS_DOC21_MINIMUM_CRITICAL_CROP_CONTRACT.safe.json"
DECISION = STAGE2 / "BROKER_REPORTS_DOC21_AUTOMATION_DECISION.safe.json"
ACCOUNTING = STAGE2 / "BROKER_REPORTS_DOC21_CALL_ACCOUNTING.safe.json"
REPORT = REPORTS / "BROKER_REPORTS_DOC21_RESEARCH_FIRST_GATE1_MATERIAL_ADEQUACY_AUDIT.report.md"
BRIEF = REPORTS / "BROKER_REPORTS_DOC21_RESEARCH_FIRST_GATE1_MATERIAL_ADEQUACY_AUDIT_BRIEF.md"
RECEIPT = REPORTS / "BROKER_REPORTS_DOC21_RESEARCH_FIRST_GATE1_MATERIAL_ADEQUACY_AUDIT.receipt.safe.json"
PUBLISHED = (RESULTS, LOSSES, CROP, COMPARISON, MINIMUM, DECISION, ACCOUNTING, REPORT, BRIEF)
JSON_EVIDENCE = (RESULTS, LOSSES, CROP, COMPARISON, MINIMUM, DECISION, ACCOUNTING, RECEIPT)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: dict) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_doc21_safe_json_integrity_is_self_consistent():
    for path in JSON_EVIDENCE:
        value = _load(path)
        expected = value.pop("integrity_sha256")
        assert expected == _canonical_sha256(value), path.name


def test_doc21_reports_all_48_direct_manual_verdicts_without_exclusion():
    results = _load(RESULTS)
    receipt = _load(RECEIPT)
    cases = results["manual_cases"]

    assert results["DIRECT_AGENT_REVIEW_COMPLETED"] is True
    assert results["DIRECT_CASES_TOTAL"] == 48
    assert results["FAILED_CASES_EXCLUDED"] == 0
    assert results["MANUAL_VERDICTS_REPORTED"] is True
    assert len(cases) == 48
    assert len({(row["table_id"], row["gate1_provider"]) for row in cases}) == 48
    assert len({row["table_id"] for row in cases}) == 24
    assert Counter(row["gate1_provider"] for row in cases) == {
        "google_flash_lite": 24,
        "anthropic_opus": 24,
    }
    assert all(
        set(row) == {
            "table_id",
            "gate1_provider",
            "verdict",
            "critical_categories",
            "missing_context",
            "distorted_relations",
            "unsupported_content",
            "reason",
            "crop_class",
        }
        for row in cases
    )
    assert receipt["DIRECT_AGENT_REVIEW_COMPLETED"] is True
    assert receipt["DIRECT_CASES_TOTAL"] == 48


def test_doc21_manual_counts_fail_phase_a_for_both_providers():
    results = _load(RESULTS)
    decision = _load(DECISION)
    expected = {
        "google_flash_lite": {
            "SUFFICIENT": 1,
            "NONCRITICAL_LOSS": 0,
            "CRITICAL_LOSS": 23,
            "AMBIGUOUS": 0,
        },
        "anthropic_opus": {
            "SUFFICIENT": 1,
            "NONCRITICAL_LOSS": 3,
            "CRITICAL_LOSS": 20,
            "AMBIGUOUS": 0,
        },
    }
    for provider, verdict_counts in expected.items():
        row = results["provider_results"][provider]
        assert row["verdict_counts"] == verdict_counts
        assert row["material_cases_total"] < 22
        assert verdict_counts["CRITICAL_LOSS"] > 2
        assert row["phase_b_threshold_met"] is False

    assert results["MANUAL_RESEARCH_VERDICT"] == "NOT_CONFIRMED"
    assert results["DIRECT_MATERIAL_SUFFICIENCY"] == "NOT_CONFIRMED"
    assert results["BEST_GATE1_ARTIFACT"] == "anthropic_opus"
    assert decision["phase_b_eligible"] is False
    assert decision["systematic_period_loss_present"] is True
    assert decision["AUTOMATED_TESTS_STARTED"] is False
    assert decision["qualification_started"] is False
    assert decision["AUTOMATED_AUDIT"] == "NOT_STARTED"


def test_doc21_preserves_doc16_crop_classes_and_reports_their_effect():
    crop = _load(CROP)

    assert crop["crop_classes_preserved"] is True
    assert crop["crop_class_effect_reported"] is True
    assert crop["class_counts"] == {
        "CROP_CLEAN": 12,
        "CROP_CLIPPED": 7,
        "CROP_CONTAMINATED": 5,
    }
    assert crop["results"]["CROP_CLEAN"]["google_flash_lite"]["verdict_counts"] == {
        "SUFFICIENT": 1,
        "NONCRITICAL_LOSS": 0,
        "CRITICAL_LOSS": 11,
        "AMBIGUOUS": 0,
    }
    assert crop["results"]["CROP_CLEAN"]["anthropic_opus"]["verdict_counts"] == {
        "SUFFICIENT": 1,
        "NONCRITICAL_LOSS": 1,
        "CRITICAL_LOSS": 10,
        "AMBIGUOUS": 0,
    }
    assert all(
        crop["results"]["CROP_CLIPPED"][provider]["verdict_counts"]["CRITICAL_LOSS"] == 7
        for provider in ("google_flash_lite", "anthropic_opus")
    )
    assert crop["finding"] == "DOC16_GEOMETRY_CLASS_IS_NOT_A_MATERIAL_ADEQUACY_GUARANTEE"
    assert crop["case_specific_crop_rules_created"] == 0


def test_doc21_stops_before_phase_b_and_makes_no_provider_calls():
    accounting = _load(ACCOUNTING)
    receipt = _load(RECEIPT)

    assert accounting["phase_a_existing_gate1_artifacts_reviewed"] == 48
    assert accounting["phase_a_new_provider_calls_total"] == 0
    assert accounting["phase_b_eligible"] is False
    assert accounting["phase_b_qualification_calls_total"] == 0
    assert accounting["phase_b_automated_calls_total"] == 0
    assert accounting["NEW_PROVIDER_CALLS_TOTAL"] == 0
    assert accounting["retry_total"] == 0
    assert accounting["fallback_total"] == 0
    assert accounting["repair_total"] == 0
    assert accounting["failed_cases_excluded_total"] == 0
    assert receipt["NEW_PROVIDER_CALLS_TOTAL"] == 0
    assert receipt["AUTOMATED_AUDIT"] == "NOT_STARTED"


def test_doc21_defines_only_general_minimum_crop_requirements():
    minimum = _load(MINIMUM)
    elements = {
        row["element"] for row in minimum["minimum_critical_crop_contract"]
    }

    assert minimum["contract_kind"] == "RESEARCH_REQUIREMENTS_NOT_PRODUCT_SCHEMA"
    assert elements == {
        "TABLE_IDENTITY_AND_SCOPE",
        "PERIOD_BASIS_AND_COLUMN_BINDING",
        "CURRENCY_UNIT_AND_SCALE",
        "COMPLETE_RELATIONAL_BOUNDARY",
        "MATERIAL_QUALIFIERS",
    }
    assert minimum["case_specific_crop_rules_created"] == 0
    assert minimum["financial_ontology_created"] is False
    assert minimum["gate3_contract_created"] is False


def test_doc21_preserves_research_and_product_boundaries():
    results = _load(RESULTS)
    receipt = _load(RECEIPT)

    assert results["doc21_research_only"] is True
    assert receipt["DOC21_RESEARCH"] == "COMPLETED"
    assert receipt["GATE1_CHANGED"] is False
    assert receipt["CROPPER_CHANGED"] is False
    assert receipt["GATE2_CHANGED"] is False
    assert receipt["GATE3_CREATED"] is False
    assert receipt["PRODUCT_PIPELINE_ACTIVATED"] is False
    assert receipt["FINANCIAL_FACT_EXTRACTOR_CREATED"] is False
    assert receipt["FINANCIAL_ONTOLOGY_CREATED"] is False


def test_doc21_receipt_binds_every_published_artifact():
    receipt = _load(RECEIPT)
    for path in PUBLISHED:
        relative = path.relative_to(ROOT).as_posix()
        assert receipt["artifact_sha256"][relative] == _sha256(path)


def test_doc21_safe_artifacts_contain_no_private_payload_or_machine_paths():
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
    for path in (*PUBLISHED, RECEIPT):
        text = path.read_text(encoding="utf-8")
        assert all(token.lower() not in text.lower() for token in forbidden), path.name
