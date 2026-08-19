from __future__ import annotations

import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-14"
CONTRACT_ROOT = REPO_ROOT / "docs" / "stage2" / "contracts"
RECLASSIFICATION = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION_G5_48.reclassification.safe.json"
)
PATH_DIFF = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION_G5_48.path-diff.safe.json"
)
ONE_GAP = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_ONE_GAP_G5_48.receipt.safe.json"
)
RECEIPT = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION_G5_48.receipt.safe.json"
)
REPORT = REPORT_ROOT / (
    "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION_G5_48.report.md"
)
CONTRACT = CONTRACT_ROOT / ("BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION.v1.md")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_g547_preservation_rows_are_reclassified_without_false_source_claims() -> None:
    result = _json(RECLASSIFICATION)

    assert len(result["rows"]) == 32
    assert result["counts"] == {
        "EXISTING_PIPELINE_ROLE_EXTRACTION_GAP": 13,
        "RECOVERY_PATH_BYPASSED_EXISTING_OWNER": 16,
        "UPSTREAM_FACT_CONTRACT_GAP": 3,
    }
    assert result["g547_canonical_preservation_gap_count"] == 29
    assert result["g548_true_canonical_preservation_gap_count"] == 0
    assert (
        result["basis"][
            "canonical_preservation_not_proven_by_document_wide_provider_failure"
        ]
        is True
    )


def test_path_diff_proves_bounded_execution_but_fails_closed_on_recovery() -> None:
    path_diff = _json(PATH_DIFF)
    current = path_diff["current_g548"]

    assert path_diff["legacy_g547"]["input_tokens"] == 667_531
    assert current["source_or_canonical_read_by_gate5"] is False
    assert current["one_gap_provider_calls"] == 2
    assert current["one_gap_input_tokens"] == 61_670
    assert current["one_gap_demanded_annotations"] == 8
    assert current["one_gap_demanded_complete_annotations"] == 0
    assert path_diff["recovery_terminal"] == {
        "BOUNDED_CONTEXT_EXECUTION_PROVEN": True,
        "BOUNDED_CONTEXT_RECOVERY_PROVEN": False,
        "reason": "demanded type re-emitted but no Role-Pack-complete fact",
    }


def test_one_gap_live_receipt_is_bounded_non_mutating_and_no_retry() -> None:
    receipt = _json(ONE_GAP)

    assert receipt["chunk_chars"] == 58_149
    assert receipt["chunk_targets"] == 40
    assert receipt["provider_submissions"] == 2
    assert receipt["retry_count"] == receipt["repair_count"] == 0
    assert receipt["store_unchanged"] is True
    assert receipt["persistence"] == "none"
    assert receipt["demanded_complete_annotations"] == 0


def test_rejected_parallel_runtime_is_absent_from_source_and_bundle() -> None:
    assert not (PACKAGE_ROOT / "gate5_real_semantic_recovery.py").exists()
    source = (PACKAGE_ROOT / "gate4_financial_case_materialization.py").read_text(
        encoding="utf-8"
    )
    bundle = (
        SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
    ).read_text(encoding="utf-8")
    for value in (source, bundle):
        assert "Gate4CanonicalRecoveryProjector" not in value


def test_contract_report_and_safe_evidence_are_privacy_clean() -> None:
    assert "Status: `CURRENT SUPPORTING CONTRACT`" in CONTRACT.read_text(
        encoding="utf-8"
    )
    assert "Status: `PARTIAL_PROOF_FAIL_CLOSED`" in REPORT.read_text(encoding="utf-8")
    for path in (CONTRACT, REPORT, RECLASSIFICATION, PATH_DIFF, ONE_GAP, RECEIPT):
        content = path.read_text(encoding="utf-8")
        for forbidden in (
            "C:\\Users\\",
            "D:\\Users\\",
            "private-evidence",
            "g540e-private",
            "normrun_",
            "brdoc_",
        ):
            assert forbidden not in content


def test_receipt_preserves_historical_artifacts_and_marks_recovery_unproven() -> None:
    receipt = _json(RECEIPT)

    assert receipt["status"] == "PARTIAL_PROOF_FAIL_CLOSED"
    assert receipt["unproven_terminal"] == "BOUNDED_CONTEXT_RECOVERY_PROVEN"
    assert receipt["retry_count"] == receipt["repair_count"] == 0
    assert receipt["store_unchanged"] is True
    for artifact in receipt["artifacts"]:
        assert artifact["bytes"] > 0
        assert len(artifact["sha256"]) == 64
