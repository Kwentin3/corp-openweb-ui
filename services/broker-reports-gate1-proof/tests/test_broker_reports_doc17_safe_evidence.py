from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STAGE2 = ROOT / "docs" / "stage2"
REPORTS = ROOT / "docs" / "reports" / "2026-08-04"
PRIVATE = (
    ROOT
    / "local"
    / "stage2"
    / "broker_reports_doc17_canonical_table_crop_2026-08-04"
    / "private"
)

SAFE_FILES = {
    "BROKER_REPORTS_DOC17_CROP_CONTRACT.safe.json": STAGE2
    / "BROKER_REPORTS_DOC17_CROP_CONTRACT.safe.json",
    "BROKER_REPORTS_DOC17_CROP_BASELINE.safe.json": STAGE2
    / "BROKER_REPORTS_DOC17_CROP_BASELINE.safe.json",
    "BROKER_REPORTS_DOC17_CROP_RESULTS.safe.json": STAGE2
    / "BROKER_REPORTS_DOC17_CROP_RESULTS.safe.json",
    "BROKER_REPORTS_DOC17_CROP_HOLDOUT.safe.json": STAGE2
    / "BROKER_REPORTS_DOC17_CROP_HOLDOUT.safe.json",
    "BROKER_REPORTS_DOC17_CROP_PERFORMANCE.safe.json": STAGE2
    / "BROKER_REPORTS_DOC17_CROP_PERFORMANCE.safe.json",
    "BROKER_REPORTS_DOC17_CANONICAL_TABLE_CROP.report.md": REPORTS
    / "BROKER_REPORTS_DOC17_CANONICAL_TABLE_CROP.report.md",
    "BROKER_REPORTS_DOC17_CANONICAL_TABLE_CROP_BRIEF.md": REPORTS
    / "BROKER_REPORTS_DOC17_CANONICAL_TABLE_CROP_BRIEF.md",
}
RECEIPT = REPORTS / "BROKER_REPORTS_DOC17_CANONICAL_TABLE_CROP.receipt.safe.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_doc17_terminal_receipt_reports_blocked_without_lowering_the_gate():
    receipt = _load(RECEIPT)
    assert receipt["DOC17_RESULT"] == "BLOCKED"
    assert receipt["CANONICAL_TABLE_CROP"] == "NOT_READY"
    assert receipt["DOC15_CROP_CLEAN"] == 24
    assert receipt["HOLDOUT_CROP_CLEAN"] == 2
    assert receipt["NEXT_STEP"] == "FURTHER_CROP_RESEARCH_REQUIRED"
    assert receipt["acceptance"]["HOLDOUT_FALSE_CLEAN"] == 10
    assert receipt["acceptance"]["FULL_RELEVANT_TEST_SUITE"] == "NOT_PASSED"
    assert receipt["acceptance"]["PRIVACY_SCAN"] == "PASSED"


def test_doc17_receipt_binds_safe_and_private_evidence():
    receipt = _load(RECEIPT)
    for name, path in SAFE_FILES.items():
        assert receipt["safe_artifact_sha256"][name] == _sha256(path)
    private_files = {
        "doc17_baseline.private.json": PRIVATE
        / "before"
        / "doc17_baseline.private.json",
        "doc17_after_raw.private.json": PRIVATE
        / "after"
        / "doc17_after_raw.private.json",
        "doc17_holdout_v4_run.private.json": PRIVATE
        / "holdout_v4"
        / "run_v4"
        / "doc17_holdout_v4_run.private.json",
        "doc17_root_cause_ledger.private.json": PRIVATE
        / "doc17_root_cause_ledger.private.json",
    }
    for name, path in private_files.items():
        assert receipt["private_artifact_sha256"][name] == _sha256(path)


def test_doc17_safe_evidence_contains_no_private_bytes_or_local_paths():
    forbidden_text = (
        "data:image/png;base64",
        "local/stage2",
        "C:\\Users",
        "D:\\Users",
        "OPENAI_API_KEYS",
    )
    for path in [*SAFE_FILES.values(), RECEIPT]:
        text = path.read_text(encoding="utf-8")
        assert all(value not in text for value in forbidden_text), path.name


def test_doc17_runtime_contains_no_corpus_identity_or_parallel_cropper():
    source = (
        ROOT
        / "services"
        / "broker-reports-gate1-proof"
        / "broker_reports_gate1"
        / "pdf_table_raster.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "H17V4_",
        "ARAMCO_T",
        "CNH_T",
        "KN_T",
        "JEFFERIES_T",
        "STONEX_T",
        "TRADEWEB_T",
        "page_number ==",
    ):
        assert forbidden not in source
    assert 'PDF_TABLE_CANDIDATE_RASTER_POLICY_VERSION = "pdf_table_candidate_raster_policy_v4"' in source
    assert 'CANONICAL_TABLE_REGION_POLICY_VERSION = "canonical_table_region_policy_v3"' in source
    assert "PdfTableRasterFactory.create is the only" in source
