from __future__ import annotations

import copy

from .blockers import privacy_violation
from .compact_report import render_compact_report
from .contracts import SAFE_REPORT_SCHEMA, SAFETY_STATEMENT, safety_flags


def render_safe_report(package: dict) -> dict:
    normalization_run = package["normalization_run"]
    document_inventory = package["document_inventory"]
    blockers = package["normalization_blockers"]
    taxonomy_candidates = package["taxonomy_candidates"]
    validation_result = package.get("validation_result", {})
    summary_counts = package["summary_counts"]
    safe_artifact_refs = package["safe_artifact_refs"]

    report = {
        "schema_version": SAFE_REPORT_SCHEMA,
        "report_id": safe_artifact_refs["chat_visible_report_ref"],
        "normalization_run_id": normalization_run["run_id"],
        "run_status": normalization_run["run_status"],
        "trigger_type": package["trigger_type"],
        "entrypoint": package["entrypoint"],
        "normalizer_version": package["normalizer_version"],
        "files_total": summary_counts["files_total"],
        "container_counts": summary_counts["container_counts"],
        "document_class_counts": summary_counts["document_class_counts"],
        "duplicate_count": summary_counts["duplicate_count"],
        "blockers_total": summary_counts["blockers_total"],
        "summary_counts": summary_counts,
        "file_ref_visibility": "visible" if summary_counts["files_total"] else "not_visible",
        "input_context": package.get("input_context", {}),
        "normalization_run": normalization_run,
        "document_inventory": document_inventory,
        "documents": document_inventory.get("documents", []),
        "technical_readability_profiles": package["technical_readability_profiles"],
        "taxonomy_candidates": taxonomy_candidates,
        "normalization_blockers": blockers,
        "blockers": blockers,
        "validation_result": validation_result,
        "case_groups": [
            {
                "case_group_id": "case_group_synthetic_001",
                "readiness": "blocked" if normalization_run["run_status"] == "failed_safe" else "needs_review",
                "recommended_for_next_proof": True,
            }
        ],
        "safe_artifact_refs": safe_artifact_refs,
        "private_artifact_summary": {
            "private_normalized_slices_count": len(package.get("private_normalized_slices", [])),
            "private_normalized_slices_ref": safe_artifact_refs["private_normalized_slices_ref"],
            "chat_visible_raw_slice_content": False,
        },
        "supported_contracts": package["supported_contracts"],
        "recommended_next_step": package["recommended_next_step"],
        "next_step": package["recommended_next_step"],
        "gate2_handoff_status": normalization_run["gate2_handoff_status"],
        "safety_flags": safety_flags(),
        "safety_statement": SAFETY_STATEMENT,
    }
    return copy.deepcopy(report)


def render_privacy_failed_report(
    *,
    run_id: str,
    files_total: int,
    input_context: dict | None = None,
) -> dict:
    blocker = privacy_violation(run_id, "private_marker_detected")
    return {
        "schema_version": SAFE_REPORT_SCHEMA,
        "normalization_run_id": run_id,
        "run_status": "privacy_failed",
        "trigger_type": "backend_core",
        "entrypoint": "broker_reports_gate1_backend_core",
        "normalizer_version": "gate1_backend_profiling_completion_v1",
        "files_total": files_total,
        "container_counts": {},
        "document_class_counts": {},
        "duplicate_count": 0,
        "blockers_total": 1,
        "summary_counts": {
            "files_total": files_total,
            "container_counts": {},
            "document_class_counts": {},
            "duplicate_count": 0,
            "duplicate_hashes": 0,
            "blockers_total": 1,
        },
        "file_ref_visibility": "visible" if files_total else "not_visible",
        "input_context": input_context or {},
        "normalization_blockers": [blocker],
        "blockers": [blocker],
        "case_groups": [],
        "safe_artifact_refs": {},
        "private_artifact_summary": {
            "private_normalized_slices_count": 0,
            "chat_visible_raw_slice_content": False,
        },
        "recommended_next_step": "fix_safe_projection",
        "next_step": "fix_safe_projection",
        "gate2_handoff_status": "blocked",
        "safety_flags": safety_flags(),
        "safety_statement": SAFETY_STATEMENT,
    }


def render_chat_content(report: dict) -> str:
    return render_compact_report(report)
