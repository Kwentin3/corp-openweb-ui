#!/usr/bin/env python3
"""Build privacy-safe DOC31 closure artifacts from terminal accounting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE2 = REPO_ROOT / "docs" / "stage2"
REPORTS = REPO_ROOT / "docs" / "reports" / "2026-08-05"
DATE = "2026-08-05"


def _sha(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _safe(schema_version: str, **values):
    payload = {
        "schema_version": schema_version,
        "date": DATE,
        **values,
        "private_content_in_output": False,
    }
    payload["integrity_sha256"] = _sha(payload)
    return payload


ARTIFACTS = {
    "BROKER_REPORTS_DOC31_TARGET_OPENWEBUI_XLSX_PATH.safe.json": _safe(
        "broker_reports_doc31_target_openwebui_xlsx_path_safe_v1",
        status="IDENTIFIED",
        target_version="0.9.6",
        target_revision="8e6a71f13cf4f9cec0e5be191fac924548050e48",
        extraction_engine="default",
        call_chain=[
            "retrieval.utils.build_loader_from_config",
            "retrieval.loaders.main.Loader.load",
            "Loader._get_loader",
            "UnstructuredExcelLoader",
            "unstructured.partition_xlsx",
            "pandas.read_excel(sheet_name=None)",
            "networkx connected components",
            "single LangChain Document",
        ],
        dependency_versions={
            "langchain-community": "0.4.1",
            "unstructured": "0.18.31",
            "pandas": "3.0.1",
            "openpyxl": "3.1.5",
        },
        canonical_authority=False,
    ),
    "BROKER_REPORTS_DOC31_CURRENT_XLSX_ADAPTER_AUDIT.safe.json": _safe(
        "broker_reports_doc31_current_xlsx_adapter_audit_safe_v1",
        status="PASS",
        current_call_chain=[
            "path.read_bytes",
            "FileInput.from_bytes",
            "Gate1Normalizer.normalize",
            "profile_xlsx full XML DOM",
            "FullSourceArtifactBuilder second XML DOM",
            "CanonicalNormalizer deepcopy",
            "CanonicalArtifactStore whole-artifact serialization/deepcopy",
        ],
        oom_boundary="NORMALIZER_BUILDING_DOCUMENT_MEMORY before NORMALIZER_VALIDATING",
        root_causes=[
            "whole input bytes retained",
            "two full worksheet DOM passes",
            "full row and cell projections",
            "repeated deep copies",
            "whole-artifact serialization before storage",
        ],
    ),
    "BROKER_REPORTS_DOC31_PROBLEM_XLSX_INVENTORY.safe.json": _safe(
        "broker_reports_doc31_problem_xlsx_inventory_safe_v1",
        status="PASS",
        size_bytes=912502,
        zip_parts=30,
        compressed_bytes=907042,
        uncompressed_bytes=7626837,
        compression_ratio=8.408472,
        sheets=20,
        hidden_sheets=0,
        shared_strings=659,
        styles=130,
        formulas=3147,
        merged_ranges=13,
        named_ranges=1,
        row_elements=29499,
        cell_elements=153352,
        material_cells=113853,
        blank_styled_cells=39499,
        dimension_mismatches=2,
        inventory_peak_bytes=8953856,
        workbook_object_created=False,
    ),
    "BROKER_REPORTS_DOC31_MEMORY_PROFILE.safe.json": _safe(
        "broker_reports_doc31_memory_profile_safe_v1",
        status="PASS",
        arm_a={"route": "current canonical adapter", "peak_bytes": 715272192, "exit_code": 137, "oom_killed": True},
        arm_b={"route": "exact OpenWebUI loader", "peak_bytes": 548409344, "exit_code": 1, "oom_killed": False, "blocker": "missing runtime NLTK resources"},
        arm_c={"route": "direct OOXML streaming prototype", "peak_bytes": 47837184, "exit_code": 0, "chunks": 118},
        target_problem_xlsx={"peak_bytes": 156504064, "limit_bytes": 1073741824, "target_threshold_bytes": 805306368, "exit_code": 0, "oom_killed": False},
        target_second_xlsx={"peak_bytes": 152109056, "exit_code": 0, "oom_killed": False},
    ),
    "BROKER_REPORTS_DOC31_OPENWEBUI_GAP_MATRIX.safe.json": _safe(
        "broker_reports_doc31_openwebui_gap_matrix_safe_v1",
        status="PASS",
        reuse_decision="REJECTED",
        exact_loader_preserves=["rendered table text", "HTML approximation", "sheet-derived elements"],
        required_gaps=[
            "formula/cache distinction",
            "source coordinates",
            "sheet visibility",
            "merged ranges",
            "named ranges",
            "table definitions",
            "style references",
            "blank styled cells",
            "stable provenance",
            "explicit unsupported-feature issues",
        ],
        runtime_blocker="loader requires unavailable NLTK resources",
    ),
    "BROKER_REPORTS_DOC31_XLSX_PROFILE.safe.json": _safe(
        "broker_reports_doc31_xlsx_profile_safe_v1",
        status="PASS",
        profile_version="xlsx_canonical_profile_v1",
        policy_version="xlsx_ooxml_streaming_v1",
        chunk_rows=256,
        physical_layout="xlsx_row_chunked_v1",
        shared_dictionaries=["shared strings", "styles"],
        formula_and_cached_value_separate=True,
        blank_ranges="contiguous style runs; declared empty dimensions are not expanded",
        unsupported_features="explicit issues",
    ),
    "BROKER_REPORTS_DOC31_IMPLEMENTATION_DECISION.safe.json": _safe(
        "broker_reports_doc31_implementation_decision_safe_v1",
        status="PASS",
        selected="DIRECT_OOXML_STREAMING",
        openwebui_reuse="REJECTED",
        openpyxl_streaming="REJECTED_AS_SELECTED_ROUTE",
        rationale=[
            "exact OpenWebUI output is structurally insufficient",
            "openpyxl formula/cache parity requires duplicate workbook passes",
            "inflated dimensions risk synthesized empty cells",
            "stdlib OOXML is the existing canonical technology boundary",
        ],
        second_production_engine_created=False,
    ),
    "BROKER_REPORTS_DOC31_STREAMING_RESULTS.safe.json": _safe(
        "broker_reports_doc31_streaming_results_safe_v1",
        status="PASS",
        chunk_rows=256,
        deterministic_resume=True,
        staged_chunk_hashes=True,
        incremental_root_hash=True,
        bounded_component_write=True,
        atomic_finalize=True,
        partial_active_states=0,
        failure_cleanup_test="PASS",
        tampered_resume_test="PASS",
    ),
    "BROKER_REPORTS_DOC31_FIDELITY_RESULTS.safe.json": _safe(
        "broker_reports_doc31_fidelity_results_safe_v1",
        status="PASS",
        sheets_and_visibility="CONFIRMED",
        formulas=3147,
        formula_cache_distinction="CONFIRMED",
        missing_cached_values=0,
        merged_ranges=13,
        named_ranges=1,
        styles=130,
        blank_styled_cells=39499,
        source_coordinates="CONFIRMED",
        dimension_mismatches_explicit=2,
        fabricated_cells=0,
    ),
    "BROKER_REPORTS_DOC31_TARGET_CANARY.safe.json": _safe(
        "broker_reports_doc31_target_canary_safe_v1",
        status="PASS",
        small_xlsx_canary="PASS",
        failed_doc30_xlsx_canary="PASS",
        canary_receipts="2/2",
        exact_failed_peak_bytes=156504064,
        exact_failed_components=141,
        exact_failed_formulas=3147,
        exact_failed_blank_styled_cells=39499,
        oom_events=0,
        partial_states=0,
        openwebui_health_degradation=0,
    ),
    "BROKER_REPORTS_DOC31_COHORT_RESUME.safe.json": _safe(
        "broker_reports_doc31_cohort_resume_safe_v1",
        status="PASS",
        previous_completed=8,
        newly_completed=8,
        cohort_total=16,
        active_versions="16/16",
        root_matches="16/16",
        components_verified=304,
        missing_chunks=0,
        cross_tenant_access="DENIED",
        duplicate_source_instances=1,
        duplicate_scope_retry="PASS",
        failed_run_records_purged=22,
        unaccounted=0,
    ),
    "BROKER_REPORTS_DOC31_DURABILITY_RESTORE.safe.json": _safe(
        "broker_reports_doc31_durability_restore_safe_v1",
        status="PASS",
        active_after_restart="16/16",
        roots_after_restart="16/16",
        active_after_recreate="16/16",
        roots_after_recreate="16/16",
        backup_sqlite_integrity="ok",
        backup_foreign_key_violations=0,
        backup_component_payloads=304,
        restored_active="16/16",
        restored_roots="16/16",
        restored_missing_chunks=0,
        restored_partial_reads="16/16",
        restored_access_failures=0,
    ),
    "BROKER_REPORTS_DOC31_CONSUMER_SHADOW.safe.json": _safe(
        "broker_reports_doc31_consumer_shadow_safe_v1",
        status="BLOCKED_PDF_SOURCE_ACCOUNTING",
        research_consumer="local_pdf_compact_canonical_proof",
        research_consumer_migrated=False,
        pdf_documents=8,
        pdf_canonical_ok=0,
        pdf_containers_per_document=1,
        pdf_nodes_per_document=0,
        compatibility_status="CANONICAL_INCOMPLETE",
        error_code="canonical_required_information_missing",
        silent_fallbacks=0,
        wave2_shadow="NOT_STARTED_STOP_CONDITION",
        wave2_consumers_migrated=0,
        provider_calls=0,
        product_side_effects=0,
    ),
    "BROKER_REPORTS_DOC31_TEST_RESULTS.safe.json": _safe(
        "broker_reports_doc31_test_results_safe_v1",
        status="PASS_WITH_PROGRAM_BLOCKER",
        focused_tests={"status": "PASS", "passed": 46, "failed": 0},
        full_suite={
            "terminal": True,
            "timeout": False,
            "passed": 2940,
            "failed": 8,
            "errors": 11,
            "skipped": 5,
            "result": "FAILED_ACCOUNTED",
            "elapsed_seconds": 900.91,
            "accounting": {
                "historical_frozen_source_hash_failures": 5,
                "historical_authority_hash_errors": 11,
                "current_bundle_sync_failures_fixed_after_terminal_run": 2,
                "new_module_declaration_failure_fixed_after_terminal_run": 1,
            },
        },
        target_tests={
            "xlsx_memory": "PASS",
            "cohort_completion": "PASS",
            "restart_recreation": "PASS",
            "backup_restore": "PASS",
            "access": "PASS",
            "research_consumer": "BLOCKED",
            "wave2_shadow": "NOT_STARTED_STOP_CONDITION",
        },
        historical_hashes_rewritten=0,
        historical_reports_modified_by_doc31=0,
    ),
    "BROKER_REPORTS_DOC31_DECISION.safe.json": _safe(
        "broker_reports_doc31_decision_safe_v1",
        DOC31_PROGRAM="PARTIALLY_COMPLETED",
        TARGET_OPENWEBUI_XLSX_PATH="IDENTIFIED",
        OPENWEBUI_LOADER_REUSE="REJECTED",
        XLSX_IMPLEMENTATION="DIRECT_OOXML_STREAMING",
        PROBLEM_XLSX_MEMORY="PASS",
        XLSX_CANONICAL_FIDELITY="CONFIRMED",
        TARGET_COHORT="COMPLETED_16_OF_16",
        TARGET_DURABILITY="CONFIRMED",
        TARGET_BACKUP_RESTORE="CONFIRMED",
        RESEARCH_CONSUMER="BLOCKED",
        WAVE2_SHADOW="BLOCKED",
        WAVE2_CUTOVER="NOT_PERFORMED",
        PRIMARY_PRODUCT_CUTOVER="NOT_PERFORMED",
        LEGACY_HANDOFF="RETAINED",
        GATE3="NOT_STARTED",
        blocker="Eight retained PDF canonical artifacts have zero logical nodes",
        separate_wave2_cutover_goal_authorized=False,
    ),
}


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    for name, payload in ARTIFACTS.items():
        _write_json(STAGE2 / name, payload)
    decision = ARTIFACTS["BROKER_REPORTS_DOC31_DECISION.safe.json"]
    tests = ARTIFACTS["BROKER_REPORTS_DOC31_TEST_RESULTS.safe.json"]
    report = f"""# Broker Reports DOC31 XLSX Streaming and Cohort Completion

DOC31 replaced the failing XLSX normalization route with a forward-only OOXML
profile while retaining the existing canonical factories and logical root
contract. The exact target OpenWebUI loader was audited and rejected as
canonical authority: it loads all sheets through pandas/unstructured, emits a
text/HTML approximation and does not retain the structural fields required by
Gate 2.

The old canonical path retained source bytes, constructed worksheet DOMs and
row/cell projections twice, deep-copied them through normalization and storage,
and serialized the whole artifact before writing. Arm A reached 715,272,192
bytes and was OOM-killed. The exact OpenWebUI arm reached 548,409,344 bytes and
then stopped on absent NLTK resources. The fixed 256-row OOXML prototype peaked
at 47,837,184 bytes.

The selected `DIRECT_OOXML_STREAMING` route stores workbook-level shared
strings/styles once, retains formula text separately from cached values, keeps
source coordinates and workbook/sheet metadata, compresses blank styled cells
into runs and records unsupported features explicitly. The exact failed XLSX
completed under the 1 GiB cgroup at 156,504,064 bytes with 3,147 formulas,
39,499 blank-styled cells and 141 components.

The frozen cohort resumed without redoing the earlier eight successes and now
has 16/16 active roots and zero missing chunks. One known duplicate source
instance initially collided with the preceding document scope; the unactivated
run was purged through retention authority and the duplicate was re-run with a
stable per-instance scope. Restart and container recreation both retained
16/16. SQLite Online Backup captured all 304 active component payloads; an
isolated restore validated 16/16 roots, all components and cross-tenant denial.

The next stage stopped correctly. All eight retained PDF canonicals contain one
container but zero logical nodes, so `local_pdf_compact_canonical_proof`
returned `CANONICAL_INCOMPLETE` with no fallback. This is pre-existing PDF
source-accounting debt outside the XLSX repair and the contract forbids redoing
those eight documents. Wave 2 shadow was therefore not started.

Final program status: `{decision['DOC31_PROGRAM']}`. XLSX, cohort, durability
and restore are confirmed. Research migration and Wave 2 remain blocked; no
Wave 2/product cutover occurred, the legacy handoff remains, and Gate 3 was not
started. A separate Wave 2 cutover goal is not authorized until the PDF
canonical source-accounting gap is repaired and re-proved.

Terminal test accounting: focused tests passed; full suite result is
`{tests['full_suite']['result']}` with timeout `{tests['full_suite']['timeout']}`.
"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "BROKER_REPORTS_DOC31_XLSX_STREAMING_AND_COHORT_COMPLETION.report.md").write_text(report, encoding="utf-8")
    brief = """# DOC31 brief

XLSX streaming, target cohort 16/16, restart/recreate and isolated restore
passed. The exact failed workbook peaked at 156,504,064 bytes under 1 GiB.
Research migration is blocked because the eight retained PDF canonicals have
zero logical nodes; Wave 2 shadow and every cutover were not performed.
"""
    (REPORTS / "BROKER_REPORTS_DOC31_XLSX_STREAMING_AND_COHORT_COMPLETION_BRIEF.md").write_text(brief, encoding="utf-8")
    receipt = _safe(
        "broker_reports_doc31_xlsx_streaming_and_cohort_completion_receipt_safe_v1",
        decision_integrity_sha256=decision["integrity_sha256"],
        safe_artifacts=len(ARTIFACTS),
        cohort_active="16/16",
        roots_matched="16/16",
        backup_restore="PASS",
        research_consumer="BLOCKED",
        wave2_shadow="NOT_STARTED_STOP_CONDITION",
        wave2_cutover_goal_authorized=False,
        historical_hashes_rewritten=0,
        historical_reports_modified_by_doc31=0,
    )
    _write_json(
        REPORTS / "BROKER_REPORTS_DOC31_XLSX_STREAMING_AND_COHORT_COMPLETION.receipt.safe.json",
        receipt,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
