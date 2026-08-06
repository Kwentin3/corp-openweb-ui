from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE2 = REPO_ROOT / "docs" / "stage2"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-05"
SAFE_NAMES = {
    "BROKER_REPORTS_DOC31_TARGET_OPENWEBUI_XLSX_PATH.safe.json",
    "BROKER_REPORTS_DOC31_CURRENT_XLSX_ADAPTER_AUDIT.safe.json",
    "BROKER_REPORTS_DOC31_PROBLEM_XLSX_INVENTORY.safe.json",
    "BROKER_REPORTS_DOC31_MEMORY_PROFILE.safe.json",
    "BROKER_REPORTS_DOC31_OPENWEBUI_GAP_MATRIX.safe.json",
    "BROKER_REPORTS_DOC31_XLSX_PROFILE.safe.json",
    "BROKER_REPORTS_DOC31_IMPLEMENTATION_DECISION.safe.json",
    "BROKER_REPORTS_DOC31_STREAMING_RESULTS.safe.json",
    "BROKER_REPORTS_DOC31_FIDELITY_RESULTS.safe.json",
    "BROKER_REPORTS_DOC31_TARGET_CANARY.safe.json",
    "BROKER_REPORTS_DOC31_COHORT_RESUME.safe.json",
    "BROKER_REPORTS_DOC31_DURABILITY_RESTORE.safe.json",
    "BROKER_REPORTS_DOC31_CONSUMER_SHADOW.safe.json",
    "BROKER_REPORTS_DOC31_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC31_DECISION.safe.json",
}


def _load(name: str):
    return json.loads((STAGE2 / name).read_text(encoding="utf-8"))


def _integrity(payload):
    supplied = payload.pop("integrity_sha256")
    actual = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload["integrity_sha256"] = supplied
    return supplied == actual


def test_doc31_safe_artifacts_are_complete_sealed_and_private_free():
    actual = {path.name for path in STAGE2.glob("BROKER_REPORTS_DOC31_*.safe.json")}
    assert actual == SAFE_NAMES
    forbidden = ("178.72.", "root@", "/opt/", "absolute_path", "private_registry")
    for name in SAFE_NAMES:
        payload = _load(name)
        assert _integrity(payload)
        assert payload["private_content_in_output"] is False
        rendered = json.dumps(payload, ensure_ascii=False).lower()
        assert not any(value.lower() in rendered for value in forbidden)


def test_doc31_decision_keeps_scope_stops_explicit():
    decision = _load("BROKER_REPORTS_DOC31_DECISION.safe.json")
    assert decision["DOC31_PROGRAM"] == "PARTIALLY_COMPLETED"
    assert decision["TARGET_COHORT"] == "COMPLETED_16_OF_16"
    assert decision["TARGET_DURABILITY"] == "CONFIRMED"
    assert decision["TARGET_BACKUP_RESTORE"] == "CONFIRMED"
    assert decision["RESEARCH_CONSUMER"] == "BLOCKED"
    assert decision["WAVE2_SHADOW"] == "BLOCKED"
    assert decision["WAVE2_CUTOVER"] == "NOT_PERFORMED"
    assert decision["PRIMARY_PRODUCT_CUTOVER"] == "NOT_PERFORMED"
    assert decision["LEGACY_HANDOFF"] == "RETAINED"
    assert decision["GATE3"] == "NOT_STARTED"
    assert decision["separate_wave2_cutover_goal_authorized"] is False


def test_doc31_terminal_test_accounting_is_honest():
    tests = _load("BROKER_REPORTS_DOC31_TEST_RESULTS.safe.json")
    assert tests["focused_tests"] == {"status": "PASS", "passed": 46, "failed": 0}
    assert tests["full_suite"]["terminal"] is True
    assert tests["full_suite"]["timeout"] is False
    assert tests["full_suite"]["passed"] == 2940
    assert tests["full_suite"]["failed"] == 8
    assert tests["full_suite"]["errors"] == 11
    assert tests["full_suite"]["result"] == "FAILED_ACCOUNTED"
    assert tests["historical_hashes_rewritten"] == 0
    assert tests["historical_reports_modified_by_doc31"] == 0


def test_doc31_closure_files_exist_and_do_not_authorize_wave2():
    report = REPORT_ROOT / "BROKER_REPORTS_DOC31_XLSX_STREAMING_AND_COHORT_COMPLETION.report.md"
    receipt = REPORT_ROOT / "BROKER_REPORTS_DOC31_XLSX_STREAMING_AND_COHORT_COMPLETION.receipt.safe.json"
    brief = REPORT_ROOT / "BROKER_REPORTS_DOC31_XLSX_STREAMING_AND_COHORT_COMPLETION_BRIEF.md"
    assert report.is_file() and receipt.is_file() and brief.is_file()
    assert "separate Wave 2 cutover goal is not authorized" in report.read_text(encoding="utf-8")
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert _integrity(receipt_payload)
    assert receipt_payload["wave2_cutover_goal_authorized"] is False
