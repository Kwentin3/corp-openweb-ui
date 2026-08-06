from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE = REPO_ROOT / "docs" / "stage2"
REPORTS = REPO_ROOT / "docs" / "reports" / "2026-08-05"
SAFE_NAMES = (
    "BROKER_REPORTS_DOC30_SSH_RECOVERY.safe.json",
    "BROKER_REPORTS_DOC30_HOST_TRIAGE.safe.json",
    "BROKER_REPORTS_DOC30_INCIDENT_ACCOUNTING.safe.json",
    "BROKER_REPORTS_DOC30_DATABASE_INTEGRITY.safe.json",
    "BROKER_REPORTS_DOC30_RECOVERY_DECISION.safe.json",
    "BROKER_REPORTS_DOC30_RESOURCE_LIMITS.safe.json",
    "BROKER_REPORTS_DOC30_CANARY_RESULTS.safe.json",
    "BROKER_REPORTS_DOC30_TARGET_BACKFILL.safe.json",
    "BROKER_REPORTS_DOC30_RESTART_DURABILITY.safe.json",
    "BROKER_REPORTS_DOC30_BACKUP_RESTORE.safe.json",
    "BROKER_REPORTS_DOC30_RESEARCH_CONSUMER.safe.json",
    "BROKER_REPORTS_DOC30_WAVE2_SHADOW.safe.json",
    "BROKER_REPORTS_DOC30_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC30_DECISION.safe.json",
)


def _load(name: str) -> dict:
    return json.loads((STAGE / name).read_text(encoding="utf-8"))


def test_doc30_safe_artifact_set_is_complete_and_private_free() -> None:
    assert len(SAFE_NAMES) == 14
    forbidden = ("root@", "identityfile", "/opt/", "/app/", "c:\\", "d:\\")
    ipv4 = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
    for name in SAFE_NAMES:
        path = STAGE / name
        assert path.is_file()
        payload = _load(name)
        assert payload["schema_version"].startswith("broker_reports_doc30_")
        rendered = path.read_text(encoding="utf-8").lower()
        assert not any(marker in rendered for marker in forbidden)
        assert ipv4.search(rendered) is None
        assert payload["private_content_in_output"] is False


def test_doc30_recovery_and_incident_accounting_are_exact() -> None:
    ssh = _load("BROKER_REPORTS_DOC30_SSH_RECOVERY.safe.json")
    assert ssh["documented_ssh_route_found"] is True
    assert ssh["ssh_credentials_requested_from_user"] is False
    assert ssh["probe_policy"]["attempts"] == 3
    assert ssh["probe_policy"]["operator_authorized_retries"] == 1
    assert ssh["probe_policy"]["successful_attempts"] == 1
    assert ssh["probe_result"].startswith("SSH_RESPONSIVE_AT_")
    assert ssh["remote_commands_executed"] == "BOUNDED_RECOVERY_AND_DOC30_WORK"
    assert ssh["stop_condition_triggered"] is False

    incident = _load("BROKER_REPORTS_DOC30_INCIDENT_ACCOUNTING.safe.json")
    assert incident["old_monolithic_job_retried"] is False
    assert incident["confirmed_root_cause"] is True
    assert incident["doc29_canonical_versions_written"] == 0
    assert incident["doc29_payload_files_written"] == 0


def test_doc30_integrity_and_retain_decision_are_evidence_bound() -> None:
    integrity = _load("BROKER_REPORTS_DOC30_DATABASE_INTEGRITY.safe.json")
    assert integrity["broker_sqlite_integrity"] == "PASS"
    assert integrity["broker_sqlite_foreign_key_violations"] == 0
    assert integrity["stt_sqlite_integrity"] == "PASS"
    assert integrity["stt_sqlite_foreign_key_violations"] == 0
    assert integrity["stt_artifact_records"] == 103
    assert integrity["current_doc30_active_versions"] == 8
    assert integrity["unclassified_partial_state"] == 0
    assert integrity["integrity_claim_from_historical_prechange_backup"] is False

    recovery = _load("BROKER_REPORTS_DOC30_RECOVERY_DECISION.safe.json")
    assert recovery["recovery_decision"] == "RETAIN"
    assert recovery["recovery_action"] == "RETAIN"
    assert recovery["stt_data_restored_or_deleted"] is False


def test_doc30_backfill_is_partial_and_cutovers_remain_closed() -> None:
    limits = _load("BROKER_REPORTS_DOC30_RESOURCE_LIMITS.safe.json")
    assert limits["monolithic_16_document_job"] == "DISALLOWED"
    assert limits["concurrency"] == 1
    assert limits["batch_size_documents"] == 1
    assert limits["resource_limits_frozen_before_run"] is True
    assert limits["cgroup_limits_verified"] is True
    assert limits["memory_limit_bytes"] == 1073741824

    canary = _load("BROKER_REPORTS_DOC30_CANARY_RESULTS.safe.json")
    assert canary["canary_receipts"] == "2/2"
    assert canary["partial_canary_versions"] == 0

    backfill = _load("BROKER_REPORTS_DOC30_TARGET_BACKFILL.safe.json")
    assert backfill["status"] == "PARTIAL_STOPPED_ON_OOM"
    assert backfill["cohort_attempted"] == 9
    assert backfill["cohort_completed"] == 8
    assert backfill["cohort_failed"] == 1
    assert backfill["cohort_pending"] == 7
    assert backfill["cohort_unaccounted"] == 0
    assert backfill["unclassified_partial_state"] == 0
    assert backfill["old_monolithic_job_retried"] is False

    decision = _load("BROKER_REPORTS_DOC30_DECISION.safe.json")
    assert decision["DOC30_PROGRAM"] == "PARTIALLY_COMPLETED"
    assert decision["TARGET_HOST_RECOVERY"] == "CONFIRMED"
    assert decision["DOC29_INCIDENT_STATE"] == "ACCOUNTED"
    assert decision["RECOVERY_ACTION"] == "RETAIN"
    assert decision["RESOURCE_BOUNDED_BACKFILL"] == "PARTIAL"
    assert decision["WAVE2_CUTOVER"] == "NOT_PERFORMED"
    assert decision["PRIMARY_PRODUCT_CUTOVER"] == "NOT_PERFORMED"
    assert decision["LEGACY_HANDOFF"] == "RETAINED"
    assert decision["GATE3"] == "NOT_STARTED"


def test_doc30_closure_is_exactly_partial() -> None:
    report = REPORTS / "BROKER_REPORTS_DOC30_TARGET_RECOVERY_AND_DURABLE_BACKFILL.report.md"
    brief = REPORTS / "BROKER_REPORTS_DOC30_TARGET_RECOVERY_AND_DURABLE_BACKFILL_BRIEF.md"
    receipt = REPORTS / "BROKER_REPORTS_DOC30_TARGET_RECOVERY_AND_DURABLE_BACKFILL.receipt.safe.json"
    for path in (report, brief, receipt):
        assert path.is_file()
    report_text = report.read_text(encoding="utf-8")
    assert "DOC30_PROGRAM = PARTIALLY_COMPLETED" in report_text
    assert "A separate Wave 2 cutover GOAL is not authorized" in report_text
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert receipt_payload["status"] == "PARTIALLY_COMPLETED"
    assert receipt_payload["ssh_attempts"] == 3
    assert receipt_payload["cohort_completed"] == 8
    assert receipt_payload["cohort_failed"] == 1
    assert receipt_payload["cohort_pending"] == 7
    assert receipt_payload["historical_doc29_modified"] is False
    assert receipt_payload["wave2_cutover_goal_authorized"] is False
