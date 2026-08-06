from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_ROOT = REPO_ROOT / "docs" / "stage2"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-05"

SAFE_NAMES = (
    "BROKER_REPORTS_DOC28_DURABLE_STORAGE_AUDIT.safe.json",
    "BROKER_REPORTS_DOC28_APPROVED_COHORT.safe.json",
    "BROKER_REPORTS_DOC28_DURABLE_BACKFILL.safe.json",
    "BROKER_REPORTS_DOC28_ACTIVE_VERSION_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_NEW_UPLOAD_SHADOW.safe.json",
    "BROKER_REPORTS_DOC28_RESEARCH_CONSUMER_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_WAVE2_SHADOW_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_OBSERVABILITY.safe.json",
    "BROKER_REPORTS_DOC28_RETENTION_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_DECISION.safe.json",
)

REPORT_NAME = "BROKER_REPORTS_DOC28_GATE2_DURABLE_CONTOUR.report.md"
RECEIPT_NAME = (
    "BROKER_REPORTS_DOC28_GATE2_DURABLE_CONTOUR.receipt.safe.json"
)
BRIEF_NAME = "BROKER_REPORTS_DOC28_GATE2_DURABLE_CONTOUR_BRIEF.md"


def _load(name: str) -> dict[str, Any]:
    return json.loads((DOC_ROOT / name).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_integrity(payload: dict[str, Any]) -> None:
    expected = payload.pop("integrity_sha256")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == expected


def test_doc28_safe_artifacts_are_integrity_bound_and_privacy_safe() -> None:
    paths = [DOC_ROOT / name for name in SAFE_NAMES]
    paths.extend(
        REPORT_ROOT / name
        for name in (REPORT_NAME, RECEIPT_NAME, BRIEF_NAME)
    )
    for path in paths:
        serialized = path.read_text(encoding="utf-8").lower()
        assert "c:\\users\\" not in serialized
        assert "d:\\users\\" not in serialized
        assert "case_group_002" not in serialized
        assert not re.search(
            r'"(?:file_?name|source_?path|raw_?text)"\s*:', serialized
        )

    for name in SAFE_NAMES:
        payload = _load(name)
        _assert_integrity(payload)


def test_doc28_deployment_gate_and_source_cohort_are_exact() -> None:
    storage = _load(SAFE_NAMES[0])
    assert storage["status"] == (
        "BLOCKED_DURABLE_BACKEND_NOT_APPROVED_OR_ACCESSIBLE"
    )
    assert storage["deployment_candidate"]["volume"] == "openwebui_data"
    assert storage["deployment_candidate"]["compose_volume_declared"] is True
    assert storage["authorized_runtime"]["runtime_proof_possible"] is False
    assert storage["backup_restore"]["integrity_drill_completed"] is False
    assert storage["durable_store_created"] is False
    assert storage["runtime_mutations"] == 0

    cohort = _load(SAFE_NAMES[1])
    assert cohort["status"] == "FROZEN_SOURCE_ONLY"
    assert cohort["documents_total"] == 16
    assert cohort["format_counts"] == {
        "CSV": 2,
        "HTML": 4,
        "PDF": 8,
        "XLSX": 2,
    }
    assert cohort["durable_versions_available"] == 0
    assert cohort["active_versions_available"] == 0
    assert len({item["document_id_hash"] for item in cohort["documents"]}) == 16
    assert cohort["unique_content_hashes"] == 15
    assert cohort["duplicate_content_documents"] == 1
    assert all(
        set(item)
        == {
            "canonical_version_hash",
            "content_sha256",
            "document_id_hash",
            "format",
            "processing_status",
            "size_class",
        }
        for item in cohort["documents"]
    )


def test_doc28_downstream_work_is_honestly_not_started() -> None:
    backfill = _load(SAFE_NAMES[2])
    active = _load(SAFE_NAMES[3])
    uploads = _load(SAFE_NAMES[4])
    research = _load(SAFE_NAMES[5])
    wave2 = _load(SAFE_NAMES[6])
    observability = _load(SAFE_NAMES[7])
    retention = _load(SAFE_NAMES[8])

    assert backfill["status"] == "NOT_STARTED_STOP_GATE"
    assert backfill["reprocess_required"] is True
    assert backfill["provider_calls"] == backfill["parser_reruns"] == 0
    assert active["status"] == "NOT_STARTED"
    assert active["active_versions"] == active["activation_attempts"] == 0
    assert uploads["status"] == "NOT_STARTED"
    assert uploads["format_support_contract"] == "4/4"
    assert uploads["durable_shadow_write_runs"] == 0
    assert research["status"] == "BLOCKED"
    assert research["migrated"] is False
    assert wave2["consumers_accounted"] == "6/6"
    assert wave2["compatibility_contracts"] == "0/6"
    assert wave2["shadow_runs"] == "0/3"
    assert wave2["consumers_migrated"] == 0
    assert all(value == 0 for value in observability["metrics"].values())
    assert retention["retention_classes_tested"] == "0/8"
    assert retention["rotation_receipts"] == "0/0"


def test_doc28_decision_report_and_receipt_match_blocked_closure() -> None:
    decision = _load(SAFE_NAMES[10])
    assert decision["DOC28_PROGRAM"] == "BLOCKED"
    assert decision["DURABLE_CANONICAL_STORE"] == "BLOCKED"
    assert decision["APPROVED_REAL_COHORT"] == "PARTIAL"
    assert decision["NEW_UPLOAD_DURABLE_SHADOW"] == "NOT_STARTED"
    assert decision["RESEARCH_CONSUMER_MIGRATION"] == "BLOCKED"
    assert decision["WAVE_2_SHADOW"] == "NOT_STARTED"
    assert decision["WAVE_2_MIGRATION_READINESS"] == "BLOCKED"
    assert decision["BACKUP_RESTORE"] == "BLOCKED"
    assert decision["RETENTION_ROTATION"] == "BLOCKED"
    assert decision["PRIMARY_PRODUCT_CUTOVER"] == "NOT_PERFORMED"
    assert decision["LEGACY_HANDOFF"] == "RETAINED"
    assert decision["GATE3"] == "NOT_STARTED"
    assert decision["DURABLE_STORAGE_RUNBOOK"] == "CURRENT_BLOCKED"
    assert decision["BACKUP_RESTORE_RUNBOOK"] == "CURRENT_BLOCKED"
    assert decision["RETENTION_RUNBOOK"] == "CURRENT_BLOCKED"
    assert decision["READ_AUTHORITY_MAP"] == "CURRENT"
    assert decision["CONTRADICTORY_AUTHORITY_DOCS"] == 0

    report_path = REPORT_ROOT / REPORT_NAME
    brief_path = REPORT_ROOT / BRIEF_NAME
    report = report_path.read_text(encoding="utf-8")
    for section in range(1, 16):
        assert f"## {section}." in report
    assert "The full suite was not run for DOC28" in report

    receipt = json.loads(
        (REPORT_ROOT / RECEIPT_NAME).read_text(encoding="utf-8")
    )
    _assert_integrity(receipt)
    assert receipt["status"] == "BLOCKED"
    assert receipt["runtime_mutations"] == 0
    assert receipt["report_sha256"] == _sha(report_path)
    assert receipt["brief_sha256"] == _sha(brief_path)
    for name in SAFE_NAMES:
        path = DOC_ROOT / name
        assert receipt["safe_artifact_sha256"][f"docs/stage2/{name}"] == _sha(
            path
        )
