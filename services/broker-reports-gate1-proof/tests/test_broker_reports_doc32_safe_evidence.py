from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STAGE2 = REPO / "docs" / "stage2"
REPORTS = REPO / "docs" / "reports" / "2026-08-05"
SAFE_NAMES = (
    "PDF_PIPELINE_TRACE",
    "PDF_BACKFILL_AUDIT",
    "ROOT_CAUSE",
    "PDF_COMPLETENESS_CONTRACT",
    "SOURCE_ATOM_ACCOUNTING",
    "ISOLATED_ROUNDTRIP",
    "LLM_PROJECTION_VALIDATION",
    "PDF_REPUBLICATION",
    "DURABILITY_RESTORE",
    "RESEARCH_CONSUMER",
    "WAVE2_SHADOW",
    "TEST_RESULTS",
    "DECISION",
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_sha(value: dict) -> str:
    clean = dict(value)
    clean.pop("integrity_sha256", None)
    return hashlib.sha256(
        json.dumps(
            clean,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_doc32_safe_artifacts_are_complete_integral_and_private_free() -> None:
    paths = [
        STAGE2 / f"BROKER_REPORTS_DOC32_{name}.safe.json"
        for name in SAFE_NAMES
    ]
    assert len(paths) == 13
    forbidden = (
        "document_id",
        "source_sha256",
        "canonical_version_id",
        "normalization_run_id",
        "openwebui_file_id",
        "generic_projection\"",
        "private.json",
        "/opt/",
        "\\local\\stage2\\broker_reports_private",
    )
    for path in paths:
        assert path.is_file()
        value = _read(path)
        assert value["private_content_in_output"] is False
        assert value["integrity_sha256"] == _json_sha(value)
        text = path.read_text(encoding="utf-8").lower()
        assert all(item.lower() not in text for item in forbidden)


def test_doc32_accounting_republication_projection_and_durability_are_exact() -> None:
    accounting = _read(STAGE2 / "BROKER_REPORTS_DOC32_SOURCE_ATOM_ACCOUNTING.safe.json")
    totals = accounting["totals"]
    assert totals == {
        "components": 76,
        "containers": 225,
        "nodes": 438,
        "parser_lines": 6316,
        "pdfs": 8,
        "ready_table_projections": 9,
        "source_atoms": 27295,
        "source_atoms_accounted": 27295,
        "source_pages": 217,
        "source_units": 245,
        "table_projections": 14,
        "tables": 9,
        "terminal_table_projections": 5,
        "unresolved_source_atoms": 0,
    }
    assert accounting["categories"] == {
        "AMBIGUITY": 0,
        "CONFLICT": 0,
        "EVIDENCE_ONLY": 16,
        "HEADING_OR_NOTE_NODE": 0,
        "PAGE_FURNITURE": 0,
        "PRIMARY_TABLE_NODE": 115,
        "PRIMARY_TEXT_NODE": 27164,
        "SUPPRESSED_PROVED_TABLE_DUPLICATE": 0,
        "UNRESOLVED": 0,
    }
    republication = _read(STAGE2 / "BROKER_REPORTS_DOC32_PDF_REPUBLICATION.safe.json")
    assert republication["pdfs_republished"] == "8/8"
    assert republication["old_versions_preserved"] == "8/8"
    assert republication["failed_attempt_changed_active_pointer"] is False
    projection = _read(STAGE2 / "BROKER_REPORTS_DOC32_LLM_PROJECTION_VALIDATION.safe.json")
    assert projection["projections_created"] == 8
    assert projection["projector_private_evidence_reads"] == 0
    durability = _read(STAGE2 / "BROKER_REPORTS_DOC32_DURABILITY_RESTORE.safe.json")
    assert durability["restart"]["missing_chunks"] == 0
    assert durability["recreation"]["missing_chunks"] == 0
    assert durability["restore"]["missing_chunks"] == 0


def test_doc32_consumer_wave2_tests_and_scope_stop_are_exact() -> None:
    research = _read(STAGE2 / "BROKER_REPORTS_DOC32_RESEARCH_CONSUMER.safe.json")
    assert research["migrated"] is True
    assert research["canonical_regressions"] == 0
    assert research["silent_fallbacks"] == 0
    wave2 = _read(STAGE2 / "BROKER_REPORTS_DOC32_WAVE2_SHADOW.safe.json")
    assert wave2["consumers_total"] == 6
    assert wave2["shadow_runs_per_consumer"] == 3
    assert wave2["canonical_regressions"] == 0
    assert wave2["product_side_effects"] == 0
    assert wave2["consumers_migrated"] == 0
    tests = _read(STAGE2 / "BROKER_REPORTS_DOC32_TEST_RESULTS.safe.json")
    assert tests["full_suite_terminal"]["terminal"] is True
    assert tests["full_suite_terminal"]["timeout"] is False
    assert tests["post_terminal_triage"]["new_unexplained_failures"] == 0
    assert tests["historical_hashes_rewritten"] == 0
    decision = _read(STAGE2 / "BROKER_REPORTS_DOC32_DECISION.safe.json")
    assert decision["doc32_program"] == "COMPLETED"
    assert decision["wave2_cutover"] == "NOT_PERFORMED"
    assert decision["primary_product_cutover"] == "NOT_PERFORMED"
    assert decision["legacy_handoff"] == "RETAINED"
    assert decision["gate3"] == "NOT_STARTED"


def test_doc32_report_brief_and_receipt_are_hash_bound() -> None:
    report = REPORTS / "BROKER_REPORTS_DOC32_PDF_CANONICAL_ROUNDTRIP_REPAIR.report.md"
    brief = REPORTS / "BROKER_REPORTS_DOC32_PDF_CANONICAL_ROUNDTRIP_REPAIR_BRIEF.md"
    receipt_path = REPORTS / "BROKER_REPORTS_DOC32_PDF_CANONICAL_ROUNDTRIP_REPAIR.receipt.safe.json"
    receipt = _read(receipt_path)
    assert receipt["integrity_sha256"] == _json_sha(receipt)
    assert receipt["report_sha256"] == _file_sha(report)
    assert receipt["brief_sha256"] == _file_sha(brief)
    assert receipt["safe_artifacts_total"] == 13
    for name, expected in receipt["safe_artifacts"].items():
        assert _file_sha(STAGE2 / name) == expected
    report_text = report.read_text(encoding="utf-8")
    for number in range(1, 16):
        assert f"## {number}." in report_text
    assert "Gate 3 were not performed" in report_text


def test_doc32_current_contracts_capture_boundaries_without_historical_rewrite() -> None:
    current = [
        STAGE2 / "contracts" / "BROKER_REPORTS_PIPELINE_GATES.v1.md",
        STAGE2 / "contracts" / "BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md",
        STAGE2 / "contracts" / "BROKER_REPORTS_CANONICAL_READER.v1.md",
        STAGE2 / "contracts" / "BROKER_REPORTS_GATE2_MIGRATION_STRATEGY.v1.md",
        STAGE2 / "contracts" / "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md",
        STAGE2 / "operations" / "BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_RUNBOOK.md",
        STAGE2 / "operations" / "BROKER_REPORTS_PDF_CANONICAL_BACKFILL_RUNBOOK.md",
    ]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in current)
    assert "canonical_pdf_completeness_v1" in joined
    assert "Full Evidence" in joined
    assert "private evidence" in joined
    assert "INCOMPLETE_PDF_CANONICAL_VERSION" in joined
    assert "local_pdf_compact_research_output_v2" in joined
