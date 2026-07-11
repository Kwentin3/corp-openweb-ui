from __future__ import annotations

import copy

from .blockers import privacy_violation
from .clarification import safe_clarification_questions_for_report
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
    document_source_eligibility = package["document_source_eligibility"]
    source_eligibility_summary = package["source_eligibility_summary"]
    gate2_handoff = package["gate2_handoff"]
    issue_ledger = package.get("gate1_issue_ledger") if isinstance(package.get("gate1_issue_ledger"), dict) else {}
    usage_classification = (
        package.get("document_usage_classification")
        if isinstance(package.get("document_usage_classification"), dict)
        else {}
    )
    domain_context_packet = package.get("domain_context_packet") if isinstance(package.get("domain_context_packet"), dict) else {}
    domain_ingestion_summary = package.get("domain_ingestion_summary") if isinstance(package.get("domain_ingestion_summary"), dict) else {}
    passport_summary = package.get("summary_counts", {}).get("document_metadata_passport_counts")
    gap_report = package.get("gate1_metadata_gap_report") if isinstance(package.get("gate1_metadata_gap_report"), dict) else {}
    clarification_questions = safe_clarification_questions_for_report(package)
    full_source_coverage_summary = (
        package.get("full_source_coverage_summary")
        if isinstance(package.get("full_source_coverage_summary"), dict)
        else {}
    )
    table_projection_summary = (
        package.get("table_projection_summary")
        if isinstance(package.get("table_projection_summary"), dict)
        else {}
    )

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
        "document_source_eligibility": document_source_eligibility,
        "source_eligibility_summary": source_eligibility_summary,
        "gate2_handoff": gate2_handoff,
        "gate1_issue_ledger": copy.deepcopy(issue_ledger) if issue_ledger else None,
        "gate1_issue_ledger_summary": copy.deepcopy(issue_ledger.get("summary")) if issue_ledger else None,
        "document_usage_classification": copy.deepcopy(usage_classification) if usage_classification else None,
        "document_usage_classification_summary": copy.deepcopy(usage_classification.get("summary")) if usage_classification else None,
        "domain_context_packet": copy.deepcopy(domain_context_packet) if domain_context_packet else None,
        "domain_context_packet_summary": {
            "domain_ingestion_status": domain_context_packet.get("domain_ingestion_status"),
            "unresolved_issue_summary": copy.deepcopy(domain_context_packet.get("unresolved_issue_summary")),
            "stage_readiness": copy.deepcopy(domain_context_packet.get("stage_readiness")),
            "next_stage_ref_summary": copy.deepcopy(domain_context_packet.get("next_stage_ref_summary")),
            "vector_knowledge_guard": copy.deepcopy(domain_context_packet.get("vector_knowledge_guard")),
        }
        if domain_context_packet
        else None,
        "domain_ingestion_summary": copy.deepcopy(domain_ingestion_summary) if domain_ingestion_summary else None,
        "full_source_coverage_summary": copy.deepcopy(full_source_coverage_summary),
        "table_projection_summary": copy.deepcopy(table_projection_summary),
        "validation_result": validation_result,
        "document_metadata_passport_summary": copy.deepcopy(passport_summary) if passport_summary else None,
        "gate1_metadata_gap_report_summary": copy.deepcopy(gap_report.get("summary")) if gap_report else None,
        "gate1_clarification_request_summary": (
            copy.deepcopy((clarification_questions or {}).get("summary")) if clarification_questions else None
        ),
        "gate1_clarification_questions": copy.deepcopy(clarification_questions),
        "gate1_clarification_resolution_summary": copy.deepcopy(
            package.get("gate1_clarification_resolution_summary")
        )
        if isinstance(package.get("gate1_clarification_resolution_summary"), dict)
        else None,
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
            "private_normalized_source_payloads_count": len(
                package.get("private_normalized_source_payloads", [])
            ),
            "private_normalized_source_payloads_ref": safe_artifact_refs.get(
                "private_normalized_source_payloads_ref"
            ),
            "private_normalized_source_units_count": len(
                package.get("private_normalized_source_units", [])
            ),
            "private_normalized_source_units_ref": safe_artifact_refs.get(
                "private_normalized_source_units_ref"
            ),
            "private_normalized_table_projections_count": len(
                package.get("private_normalized_table_projections", [])
            ),
            "full_source_raw_content_chat_visible": False,
            "chat_visible_raw_slice_content": False,
        },
        "supported_contracts": package["supported_contracts"],
        "recommended_next_step": package["recommended_next_step"],
        "next_step": package["recommended_next_step"],
        "gate2_handoff_status": normalization_run["gate2_handoff_status"],
        "gate2_handoff_mode": normalization_run["gate2_handoff_mode"],
        "gate2_reduced_subset_ready": gate2_handoff.get("handoff_mode") == "reduced_subset_ready_for_gate2",
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
        "gate2_handoff_mode": "gate2_blocked_no_eligible_sources",
        "gate2_reduced_subset_ready": False,
        "safety_flags": safety_flags(),
        "safety_statement": SAFETY_STATEMENT,
    }


def render_chat_content(report: dict) -> str:
    return render_compact_report(report)
