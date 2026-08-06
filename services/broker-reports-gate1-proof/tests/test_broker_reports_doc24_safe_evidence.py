from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STAGE2 = REPO / "docs/stage2"
REPORTS = REPO / "docs/reports/2026-08-05"
SAFE_NAMES = [
    "BROKER_REPORTS_DOC24_GATE2_HANDOFF_AUDIT.safe.json",
    "BROKER_REPORTS_DOC24_CANONICAL_DOCUMENT_METRICS.safe.json",
    "BROKER_REPORTS_DOC24_DOCUMENT_ORDER_VALIDATION.safe.json",
    "BROKER_REPORTS_DOC24_LLM_PROJECTION_METRICS.safe.json",
    "BROKER_REPORTS_DOC24_MATERIAL_SUFFICIENCY.safe.json",
    "BROKER_REPORTS_DOC24_CONFLICTS.safe.json",
    "BROKER_REPORTS_DOC24_TRACEABILITY.safe.json",
    "BROKER_REPORTS_DOC24_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC24_DECISION.safe.json",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def integrity(value: dict) -> str:
    material = copy.deepcopy(value)
    material.pop("integrity_sha256", None)
    return hashlib.sha256(
        json.dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def test_doc24_safe_artifacts_are_present_integral_and_privacy_scanned() -> None:
    for name in SAFE_NAMES:
        path = STAGE2 / name
        assert path.is_file(), name
        value = read_json(path)
        assert value["integrity_sha256"] == integrity(value), name
        serialized = path.read_text(encoding="utf-8").lower()
        assert "local/stage2" not in serialized
        assert "source_bbox" not in serialized
        assert '"text":' not in serialized
        assert "c:\\" not in serialized
        assert "d:\\" not in serialized


def test_doc24_atom_order_projection_and_traceability_thresholds() -> None:
    canonical = read_json(
        STAGE2 / "BROKER_REPORTS_DOC24_CANONICAL_DOCUMENT_METRICS.safe.json"
    )
    order = read_json(
        STAGE2 / "BROKER_REPORTS_DOC24_DOCUMENT_ORDER_VALIDATION.safe.json"
    )
    projection = read_json(
        STAGE2 / "BROKER_REPORTS_DOC24_LLM_PROJECTION_METRICS.safe.json"
    )
    traceability = read_json(
        STAGE2 / "BROKER_REPORTS_DOC24_TRACEABILITY.safe.json"
    )
    assert canonical["source_atom_accounting_percent"] == 100.0
    assert canonical["unique_parser_lines_total"] == 34541
    assert canonical["unresolved_atoms_total"] == 0
    assert canonical["duplicate_numeric_tokens_reduction_percent"] >= 90.0
    assert canonical["duplicate_table_line_segments_reduction_percent"] >= 90.0
    assert order["pages_accounted_total"] == order["pages_expected_total"] == 663
    assert order["target_tables_unique_total"] == 24
    assert order["direct_case_insertions_total"] == 48
    assert order["adjacent_context_preserved_cases_total"] == 48
    assert order["multi_table_errors_total"] == 0
    assert order["continuation_errors_total"] == 0
    assert order["insertion_errors_total"] == 0
    assert order["idempotence_failures_total"] == 0
    assert projection["projection_reads_only_canonical_candidate"] is True
    assert projection["raw_or_provider_metadata_dependency"] is False
    assert projection["doc24_projection_larger_than_doc23"] is False
    assert projection["projection_reduction_from_doc22_percent"] >= 40.0
    assert traceability["resolved_source_refs_percent"] == 100.0
    assert traceability["suppressed_atoms_total"] == traceability[
        "suppressed_atoms_with_evidence_total"
    ]


def test_doc24_material_sufficiency_conflicts_and_scope_stop() -> None:
    material = read_json(
        STAGE2 / "BROKER_REPORTS_DOC24_MATERIAL_SUFFICIENCY.safe.json"
    )
    conflicts = read_json(STAGE2 / "BROKER_REPORTS_DOC24_CONFLICTS.safe.json")
    decision = read_json(STAGE2 / "BROKER_REPORTS_DOC24_DECISION.safe.json")
    assert material["cases_total"] == 48
    assert material["failed_cases_excluded"] == 0
    assert material["unsupported_critical_information_loss_total"] == 0
    assert material["provider_metrics"]["google_flash_lite"]["sufficient_total"] == 22
    assert material["provider_metrics"]["anthropic_opus"]["sufficient_total"] == 23
    assert all(
        item["threshold_pass"] for item in material["provider_metrics"].values()
    )
    assert conflicts["hidden_conflicts_total"] == 0
    assert conflicts["conflict_parser_evidence_atoms_total"] == 42
    assert conflicts["ambiguous_parser_evidence_atoms_total"] == 79
    assert decision["doc24_experiment"] == "COMPLETED"
    assert decision["gate2_canonical_document"] == "CONFIRMED"
    assert decision["llm_friendly_projection"] == "CONFIRMED"
    assert decision["material_sufficiency"] == "PRESERVED"
    assert decision["ordering_fidelity"] == "CONFIRMED"
    assert decision["gate2_contract_decision"] == "READY_TO_FORMALIZE"
    assert decision["crop_research_policy"] == "PAUSE"
    assert decision["automated_llm_audit"] == "BLOCKED_EXTERNAL"
    assert decision["product_contract"] is False
    acceptance = decision["acceptance"]
    assert acceptance["product_pipeline_activated"] is False
    assert acceptance["gate1_changed_by_doc24"] is False
    assert acceptance["gate2_product_changed_by_doc24"] is False
    assert acceptance["gate3_created"] is False
    assert acceptance["parser_changed_by_doc24"] is False
    assert acceptance["cropper_changed_by_doc24"] is False
    assert acceptance["vlm_tables_regenerated"] is False
    assert acceptance["provider_calls_started_by_doc24"] is False


def test_doc24_tests_executed_and_report_receipt_match() -> None:
    results = read_json(STAGE2 / "BROKER_REPORTS_DOC24_TEST_RESULTS.safe.json")
    by_name = {item["name"]: item for item in results["runs"]}
    assert by_name["private_behavioral"]["status"] == "PASSED"
    assert by_name["private_behavioral"]["tests"] == 7
    assert by_name["relevant_regression_architecture"]["status"] == "PASSED"
    assert by_name["relevant_regression_architecture"]["tests"] == 79
    assert results["environment"]["shell"] == "PowerShell"
    assert results["environment"]["env_overrides_required"] is False
    assert results["product_handlers_or_routes_modified"] is False

    report = REPORTS / "BROKER_REPORTS_DOC24_GATE2_CANONICAL_DOCUMENT_VALIDATION.report.md"
    brief = REPORTS / "BROKER_REPORTS_DOC24_GATE2_CANONICAL_DOCUMENT_VALIDATION_BRIEF.md"
    receipt_path = REPORTS / "BROKER_REPORTS_DOC24_GATE2_CANONICAL_DOCUMENT_VALIDATION.receipt.safe.json"
    assert report.is_file() and brief.is_file() and receipt_path.is_file()
    receipt = read_json(receipt_path)
    assert receipt["integrity_sha256"] == integrity(receipt)
    assert receipt["product_files_changed_by_doc24"] == 0
    for item in receipt["artifacts"]:
        path = REPO / item["path"]
        assert path.is_file(), item["path"]
        assert path.stat().st_size == item["size_bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
