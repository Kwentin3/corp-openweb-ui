from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE = REPO_ROOT / "docs" / "stage2"
REPORTS = REPO_ROOT / "docs" / "reports" / "2026-08-05"
SAFE_NAMES = (
    "BROKER_REPORTS_DOC29_INFRA_DOCUMENT_AUDIT.safe.json",
    "BROKER_REPORTS_DOC29_STT_STORAGE_REUSE.safe.json",
    "BROKER_REPORTS_DOC29_OFFICIAL_RESEARCH.safe.json",
    "BROKER_REPORTS_DOC29_DEPLOYMENT_DISCOVERY.safe.json",
    "BROKER_REPORTS_DOC29_STORAGE_DECISION.safe.json",
    "BROKER_REPORTS_DOC29_DURABILITY_RESULTS.safe.json",
    "BROKER_REPORTS_DOC29_BACKUP_RESTORE.safe.json",
    "BROKER_REPORTS_DOC29_CAPACITY_RETENTION.safe.json",
    "BROKER_REPORTS_DOC29_DURABLE_COHORT.safe.json",
    "BROKER_REPORTS_DOC29_RESEARCH_CONSUMER.safe.json",
    "BROKER_REPORTS_DOC29_WAVE2_SHADOW.safe.json",
    "BROKER_REPORTS_DOC29_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC29_DECISION.safe.json",
)


def _load(name: str) -> dict:
    return json.loads((STAGE / name).read_text(encoding="utf-8"))


def test_doc29_safe_artifact_set_is_complete_and_privacy_safe() -> None:
    assert len(SAFE_NAMES) == 13
    forbidden = (
        "root@",
        "private_upload_packages",
        "absolute_path",
        "api_key",
        "customer_case_group_002",
    )
    for name in SAFE_NAMES:
        path = STAGE / name
        assert path.is_file()
        payload = _load(name)
        assert payload["schema_version"].startswith("broker_reports_doc29_")
        rendered = path.read_text(encoding="utf-8").lower()
        assert not any(marker in rendered for marker in forbidden)


def test_doc29_decision_preserves_stop_boundaries() -> None:
    decision = _load("BROKER_REPORTS_DOC29_DECISION.safe.json")
    assert decision["DOC29_PROGRAM"] == "BLOCKED"
    assert decision["STT_INFRASTRUCTURE_REUSE"] == "PARTIAL"
    assert decision["TARGET_DEPLOYMENT"] == "IDENTIFIED"
    assert decision["DURABLE_CANONICAL_STORE"] == "PARTIAL"
    assert decision["BACKUP_RESTORE"] == "NOT_CONFIRMED"
    assert decision["RESEARCH_CONSUMER"] == "BLOCKED"
    assert decision["WAVE2_MIGRATION_READINESS"] == "BLOCKED"
    assert decision["PRIMARY_PRODUCT_CUTOVER"] == "NOT_PERFORMED"
    assert decision["LEGACY_HANDOFF"] == "RETAINED"
    assert decision["GATE3"] == "NOT_STARTED"
    assert decision["next_goal_authorized"] is False


def test_doc29_runtime_accounting_is_honest() -> None:
    cohort = _load("BROKER_REPORTS_DOC29_DURABLE_COHORT.safe.json")
    assert cohort["corpus"]["documents"] == 16
    assert cohort["corpus"]["formats"] == {
        "pdf": 8,
        "html": 4,
        "csv": 2,
        "xlsx": 2,
    }
    assert cohort["isolated_preflight"]["active_versions"] == 16
    assert cohort["isolated_preflight"]["provider_calls"] == 0
    assert cohort["attempt_accounting"]["hidden_reruns"] == 0
    assert cohort["target_active_versions"] == "UNKNOWN_PENDING_HOST_RECOVERY"

    backup = _load("BROKER_REPORTS_DOC29_BACKUP_RESTORE.safe.json")
    assert backup["isolated_drill"]["payload_files"] == 172
    assert backup["isolated_drill"]["missing_chunks"] == 0
    assert backup["target_restore_drill"] == "BLOCKED_BY_HOST_UNRESPONSIVENESS"


def test_doc29_research_and_wave2_do_not_claim_target_cutover() -> None:
    research = _load("BROKER_REPORTS_DOC29_RESEARCH_CONSUMER.safe.json")
    assert research["isolated_durable_shadow"]["status"] == "PASS"
    assert research["isolated_durable_shadow"]["silent_fallbacks"] == 0
    assert research["status"] == "BLOCKED_ON_TARGET"

    wave2 = _load("BROKER_REPORTS_DOC29_WAVE2_SHADOW.safe.json")
    assert wave2["isolated_durable_shadow"]["status"] == "PASS"
    assert wave2["isolated_durable_shadow"]["consumers"] == 6
    assert wave2["isolated_durable_shadow"]["shadow_runs_per_consumer"] == 3
    assert wave2["isolated_durable_shadow"]["consumers_migrated"] == 0
    assert wave2["target_shadow"] == "NOT_RUN_STOP_CONDITION"


def test_doc29_closure_files_exist_and_name_the_blocker() -> None:
    report = REPORTS / "BROKER_REPORTS_DOC29_INFRASTRUCTURE_REUSE_AND_DURABLE_CONTOUR.report.md"
    brief = REPORTS / "BROKER_REPORTS_DOC29_INFRASTRUCTURE_REUSE_AND_DURABLE_CONTOUR_BRIEF.md"
    receipt = REPORTS / "BROKER_REPORTS_DOC29_INFRASTRUCTURE_REUSE_AND_DURABLE_CONTOUR.receipt.safe.json"
    for path in (report, brief, receipt):
        assert path.is_file()
    report_text = report.read_text(encoding="utf-8")
    assert "TARGET_HOST_UNRESPONSIVE_DURING_BOUNDED_BACKFILL" in report_text
    assert "Wave 2 cutover goal is not authorized" in report_text
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert receipt_payload["target_terminal_receipt"] is False
    assert receipt_payload["wave2_cutover_goal_authorized"] is False
