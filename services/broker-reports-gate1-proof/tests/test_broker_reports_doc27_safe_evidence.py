from __future__ import annotations

import hashlib
import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
DOC_ROOT = REPO_ROOT / "docs" / "stage2"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-05"

SAFE_NAMES = (
    "BROKER_REPORTS_DOC27_CONSUMER_INVENTORY.safe.json",
    "BROKER_REPORTS_DOC27_MIGRATION_FREEZE.safe.json",
    "BROKER_REPORTS_DOC27_COMPATIBILITY_CONTRACTS.safe.json",
    "BROKER_REPORTS_DOC27_CONSUMER_SHADOW_RESULTS.safe.json",
    "BROKER_REPORTS_DOC27_WAVE0_RESULTS.safe.json",
    "BROKER_REPORTS_DOC27_WAVE1_RESULTS.safe.json",
    "BROKER_REPORTS_DOC27_ACTIVE_VERSION_SAFETY.safe.json",
    "BROKER_REPORTS_DOC27_OBSERVABILITY.safe.json",
    "BROKER_REPORTS_DOC27_REPOSITORY_HYGIENE.safe.json",
    "BROKER_REPORTS_DOC27_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC27_DECISION.safe.json",
)

REPORT = (
    REPORT_ROOT
    / "BROKER_REPORTS_DOC27_GATE2_CONSUMER_MIGRATION_WAVE0_1.report.md"
)
RECEIPT = (
    REPORT_ROOT
    / "BROKER_REPORTS_DOC27_GATE2_CONSUMER_MIGRATION_WAVE0_1.receipt.safe.json"
)
BRIEF = (
    REPORT_ROOT
    / "BROKER_REPORTS_DOC27_GATE2_CONSUMER_MIGRATION_WAVE0_1_BRIEF.md"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_integrity(payload: dict) -> None:
    expected = payload.pop("integrity_sha256")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == expected


def test_doc27_safe_artifacts_have_valid_integrity_and_privacy_boundary() -> None:
    forbidden = (
        "C:\\Users\\",
        "D:\\Users\\",
        "AppData",
        '"user_id"',
        '"tenant_id"',
        '"raw_provider_payload"',
        '"source_text"',
        '"table_rows"',
    )
    for name in SAFE_NAMES:
        path = DOC_ROOT / name
        rendered = path.read_text(encoding="utf-8")
        assert all(marker not in rendered for marker in forbidden)
        _assert_integrity(_load(path))


def test_doc27_inventory_mappings_and_wave_results_are_exact() -> None:
    inventory = _load(
        DOC_ROOT / "BROKER_REPORTS_DOC27_CONSUMER_INVENTORY.safe.json"
    )
    contracts = _load(
        DOC_ROOT / "BROKER_REPORTS_DOC27_COMPATIBILITY_CONTRACTS.safe.json"
    )
    wave0 = _load(DOC_ROOT / "BROKER_REPORTS_DOC27_WAVE0_RESULTS.safe.json")
    wave1 = _load(DOC_ROOT / "BROKER_REPORTS_DOC27_WAVE1_RESULTS.safe.json")

    assert inventory["legacy_surfaces_total"] == 17
    assert inventory["legacy_surfaces_accounted"] == 17
    assert inventory["unresolved_surfaces"] == 0
    assert len(inventory["surfaces"]) == 17
    assert len(contracts["mappings"]) == 4
    assert contracts["canonical_reader_bypasses"] == 0
    assert contracts["silent_fallback_paths"] == 0
    assert wave0["status"] == "PARTIAL"
    assert wave0["planned_consumers"] == 4
    assert wave0["migrated_consumers"] == 3
    assert wave0["blocked_consumers"] == 1
    assert len(wave0["migration_receipts"]) == 3
    assert wave1["status"] == "NOT_STARTED"
    assert wave1["planned_consumers"] == 0


def test_doc27_safety_observability_hygiene_and_tests_are_honest() -> None:
    active = _load(
        DOC_ROOT / "BROKER_REPORTS_DOC27_ACTIVE_VERSION_SAFETY.safe.json"
    )
    metrics = _load(
        DOC_ROOT / "BROKER_REPORTS_DOC27_OBSERVABILITY.safe.json"
    )
    hygiene = _load(
        DOC_ROOT / "BROKER_REPORTS_DOC27_REPOSITORY_HYGIENE.safe.json"
    )
    tests = _load(DOC_ROOT / "BROKER_REPORTS_DOC27_TEST_RESULTS.safe.json")

    assert active["stale_candidate_rejected"] is True
    assert active["cross_tenant_candidate_rejected"] is True
    assert active["deleted_source_candidate_rejected"] is True
    assert active["rollback_restored_target"] is True
    assert active["actual_migration_cohort_activation"] == "NOT_PERFORMED"
    assert metrics["read_attempts"] == 16
    assert metrics["read_success"] == 12
    assert metrics["read_blocked"] == 4
    assert metrics["observation_runs"] == "3/3"
    assert hygiene["post_doc27"]["preexisting_paths_preserved"] == 243
    assert hygiene["tracked_private_artifacts"] == 0
    assert hygiene["legacy_core_files_deleted"] == 0
    assert hygiene["historical_hashes_rewritten"] == 0
    assert tests["full_service"] == {
        "duration_seconds": 885.178,
        "errors": 11,
        "failures": 7,
        "passed": 2909,
        "skipped": 5,
        "terminal": True,
        "tests": 2932,
        "timeout": False,
    }
    assert tests["full_service_formally_green"] is False
    assert tests["new_unexplained_failures"] == 0
    assert tests["full_suite_retried"] is False


def test_doc27_decision_closure_and_receipt_are_exactly_bound() -> None:
    decision = _load(DOC_ROOT / "BROKER_REPORTS_DOC27_DECISION.safe.json")
    assert decision["DOC27_PROGRAM"] == "PARTIALLY_COMPLETED"
    assert decision["CONSUMER_INVENTORY"] == "FROZEN"
    assert decision["CANONICAL_READ_BOUNDARY"] == "VALIDATED"
    assert decision["WAVE_0_MIGRATION"] == "PARTIAL"
    assert decision["WAVE_1_MIGRATION"] == "NOT_STARTED"
    assert decision["ACTIVE_VERSION_SAFETY"] == "CONFIRMED"
    assert decision["ROLLBACK"] == "CONFIRMED"
    assert decision["WAVE_2_READINESS"] == "BLOCKED"
    assert decision["PRIMARY_PRODUCT_CUTOVER"] == "NOT_PERFORMED"
    assert decision["LEGACY_HANDOFF"] == "RETAINED"
    assert decision["GATE3"] == "NOT_STARTED"

    receipt = _load(RECEIPT)
    _assert_integrity(dict(receipt))
    for relative, expected in receipt["safe_artifact_sha256"].items():
        assert _sha(REPO_ROOT / relative) == expected
    assert _sha(REPORT) == receipt["report_sha256"]
    assert _sha(BRIEF) == receipt["brief_sha256"]

    report = REPORT.read_text(encoding="utf-8")
    assert all(f"## {number}." in report for number in range(1, 16))
    assert "2909 passed" in report
    assert "not reported green" in report
