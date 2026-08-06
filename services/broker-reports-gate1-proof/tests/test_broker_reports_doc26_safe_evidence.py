from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_ROOT = REPO_ROOT / "docs" / "stage2"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-05"

EVIDENCE_NAMES = (
    "BROKER_REPORTS_DOC26_DOCUMENTATION_AUDIT.safe.json",
    "BROKER_REPORTS_DOC26_REPOSITORY_INVENTORY.safe.json",
    "BROKER_REPORTS_DOC26_STORAGE_LIFECYCLE.safe.json",
    "BROKER_REPORTS_DOC26_PDF_PRODUCT_REGRESSION.safe.json",
    "BROKER_REPORTS_DOC26_MULTIFORMAT_REGRESSION.safe.json",
    "BROKER_REPORTS_DOC26_SHADOW_RUN.safe.json",
    "BROKER_REPORTS_DOC26_CONSUMER_MIGRATION_PLAN.safe.json",
    "BROKER_REPORTS_DOC26_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC26_DECISION.safe.json",
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    integrity = payload.pop("integrity_sha256")
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == integrity
    payload["integrity_sha256"] = integrity
    return payload


def test_01_all_doc26_safe_evidence_is_present_and_integrity_sealed() -> None:
    for name in EVIDENCE_NAMES:
        assert _load(DOC_ROOT / name)


def test_02_documentation_and_repository_acceptance() -> None:
    documentation = _load(DOC_ROOT / EVIDENCE_NAMES[0])
    assert documentation["status"] == "PASSED"
    assert documentation["active_documents_audited_percent"] == 100
    assert documentation["contradictory_gate_definitions"] == 0
    assert documentation["canonical_artifact_gate_assignment"] == "GATE2"
    assert documentation["historical_evidence_modified"] == 0
    inventory = _load(DOC_ROOT / EVIDENCE_NAMES[1])
    assert inventory["status"] == "PASSED"
    assert inventory["baseline"]["dirty_paths"] == 216
    assert len(inventory["preexisting_changes"]) == 216
    assert inventory["post_doc26_snapshot"]["preexisting_paths_preserved"] == 216
    assert inventory["post_doc26_snapshot"]["doc26_clean_to_dirty_paths"] == 27
    assert inventory["post_doc26_snapshot"]["dirty_paths"] == 243
    assert inventory["unclassified_relevant_files"] == 0
    assert inventory["tracked_private_artifacts"] == 0
    assert inventory["tracked_raw_provider_payloads"] == 0
    assert inventory["legacy_deletion_performed"] is False
    assert all(item["classification"] != "UNRESOLVED" for item in inventory["preexisting_changes"])


def test_03_storage_pdf_multiformat_and_shadow_acceptance() -> None:
    storage = _load(DOC_ROOT / EVIDENCE_NAMES[2])
    for key in (
        "cross_run_versioning",
        "immutable_version_publish",
        "chunked_storage",
        "small_document_single_payload",
        "partial_container_read",
        "partial_table_read",
        "atomic_activation",
        "failed_activation_preserves_old_active",
        "rollback",
        "retention_receipts",
    ):
        assert storage[key] == "PASS"
    assert storage["cross_tenant_unauthorized_accesses_admitted"] == 0
    assert storage["orphan_chunks_after_purge"] == 0

    pdf = _load(DOC_ROOT / EVIDENCE_NAMES[3])
    assert pdf["status"] == "PASSED"
    assert pdf["provider_calls"] == 0
    assert pdf["cropper_reruns"] == 0
    assert pdf["research_product_unexplained_differences"] == 0
    assert {arm["pages_accounted"] for arm in pdf["arms"]} == {663}
    assert {arm["parser_lines_accounted"] for arm in pdf["arms"]} == {34541}
    assert {arm["target_tables_inserted"] for arm in pdf["arms"]} == {24}

    multiformat = _load(DOC_ROOT / EVIDENCE_NAMES[4])
    assert multiformat["status"] == "PASSED"
    assert multiformat["supported_formats"] == "4/4"
    assert multiformat["three_run_hash_stability_percent"] == 100
    assert multiformat["cross_format_financial_fields_added"] == 0

    shadow = _load(DOC_ROOT / EVIDENCE_NAMES[5])
    assert shadow["status"] == "PASSED"
    assert shadow["accounting"]["documents_attempted"] == 16
    assert shadow["accounting"]["documents_unaccounted"] == 0
    assert shadow["canonical_regressions"] == 0
    assert shadow["unresolved_comparisons"] == 0
    assert shadow["canonical_product_reads_enabled"] is False
    assert shadow["private_actual_corpus_attempts"] == 1


def test_04_consumer_test_and_decision_acceptance() -> None:
    migration = _load(DOC_ROOT / EVIDENCE_NAMES[6])
    assert migration["status"] == "READY"
    assert migration["legacy_consumers"] == 17
    assert len(migration["consumers"]) == 17
    assert migration["unresolved_consumers"] == 0
    assert migration["consumers_migrated_in_doc26"] == 0
    for consumer in migration["consumers"]:
        assert consumer["required_canonical_reads"]
        assert consumer["rollback_behavior"]
        assert consumer["legacy_deletion_condition"]

    tests = _load(DOC_ROOT / EVIDENCE_NAMES[7])
    assert tests["focused_doc26_tests"]["status"] == "PASSED"
    assert tests["architecture_tests"] == "PASS"
    assert tests["new_unexplained_failures"] == 0
    assert tests["full_suite"]["terminal"] is True
    assert tests["full_suite"]["timeout"] is False
    assert tests["full_suite"]["failed"] == 6
    assert tests["full_suite"]["errors"] == 11
    assert tests["historical_hashes_updated_for_green"] is False

    decision = _load(DOC_ROOT / EVIDENCE_NAMES[8])
    assert decision["doc26_program"] == "COMPLETED"
    assert decision["gate2_shadow_readiness"] == "READY"
    assert decision["product_cutover"] == "NOT_PERFORMED"
    assert decision["gate3"] == "NOT_STARTED"
    assert decision["legacy_files_deleted"] == 0


def test_05_closure_receipt_binds_all_safe_evidence() -> None:
    receipt = _load(
        REPORT_ROOT
        / "BROKER_REPORTS_DOC26_GATE2_SHADOW_READINESS.receipt.safe.json"
    )
    assert receipt["status"] == "COMPLETED"
    assert receipt["decision"] == "GATE2_SHADOW_READINESS_READY"
    assert len(receipt["evidence"]) == 9
    for item in receipt["evidence"]:
        path = REPO_ROOT / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
