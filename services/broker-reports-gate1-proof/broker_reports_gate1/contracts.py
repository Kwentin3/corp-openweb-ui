from __future__ import annotations

import hashlib
from typing import Iterable


SAFE_REPORT_SCHEMA = "broker_reports_chat_visible_normalization_report_v0"
NORMALIZER_VERSION = "gate1_normalized_table_projection_v0"
SAFETY_STATEMENT = (
    "Gate 1 did not calculate tax, extract source facts through LLM, generate "
    "declaration, generate XLS/XLSX or file with FNS."
)

SAFETY_FLAGS = {
    "tax_correctness_claimed": False,
    "source_fact_extraction_performed": False,
    "declaration_generated": False,
    "xlsx_generated": False,
    "fns_filing_claimed": False,
    "ocr_performed": False,
    "customer_docs_loaded_to_knowledge": False,
}

SUPPORTED_CONTRACTS = [
    "normalization_run_v0",
    "document_inventory_v0",
    "technical_readability_profile_v0",
    "private_normalized_slices_v0",
    "private_normalized_table_slice_v0",
    "private_normalized_text_slice_v0",
    "private_normalized_source_payload_v0",
    "private_normalized_source_unit_v0",
    "full_source_coverage_summary_v0",
    "broker_reports_normalized_table_projection_v0",
    "broker_reports_pdf_compact_canonical_document_v1",
    "broker_reports_pdf_normalization_acceptance_v1",
    "broker_reports_pdf_table_classification_v1",
    "broker_reports_pdf_hybrid_evidence_package_v1",
    "broker_reports_pdf_hybrid_binding_output_v1",
    "broker_reports_pdf_provider_attempt_v1",
    "broker_reports_pdf_table_materialization_result_v1",
    "broker_reports_pdf_semantic_header_projection_v1",
    "broker_reports_pdf_semantic_header_private_diagnostic_v1",
    "broker_reports_pdf_table_validation_v1",
    "broker_reports_pdf_hybrid_compact_ledger_v2",
    "broker_reports_pdf_hybrid_row_window_plan_v2",
    "broker_reports_pdf_hybrid_window_evidence_v2",
    "broker_reports_pdf_hybrid_structural_placement_validation_v2",
    "broker_reports_pdf_hybrid_continuation_contract_v2",
    "broker_reports_pdf_hybrid_continuation_validation_v2",
    "broker_reports_pdf_hybrid_repeatability_ledger_v2",
    "broker_reports_pdf_hybrid_shadow_arbitration_v2",
    "broker_reports_table_projection_coverage_v0",
    "broker_reports_table_reconstruction_quality_v0",
    "source_unit_provenance_v0",
    "source_unit_coverage_v0",
    "taxonomy_candidates_v0",
    "normalization_blockers_v0",
    "broker_reports_file_processing_outcome_v1",
    "broker_reports_file_processing_batch_v1",
    "broker_reports_pdf_continuation_discovery_v1",
    "broker_reports_pdf_structural_repair_continuation_result_v1",
    "broker_reports_pdf_continuation_materialization_v1",
    "broker_reports_pdf_vlm_guided_intake_result_v1",
    "broker_reports_pdf_vlm_guided_candidate_intake_result_v1",
    "broker_reports_pdf_vlm_guided_upstream_terminal_v1",
    "broker_reports_pdf_vlm_page_proposal_result_v1",
    "broker_reports_pdf_vlm_region_binding_result_v1",
    "llm_document_package_v0",
    "llm_prompt_snapshot_v0",
    "llm_passport_raw_output_v0",
    "llm_clarification_prompt_snapshot_v0",
    "llm_clarification_raw_output_v0",
    "document_metadata_passport_v0",
    "document_metadata_passport_validation_v0",
    "document_source_eligibility_v0",
    "gate1_metadata_gap_report_v0",
    "gate1_clarification_request_v0",
    "gate1_clarification_resolution_v0",
    "gate1_issue_ledger_v0",
    "document_usage_classification_v0",
    "domain_context_packet_v0",
    SAFE_REPORT_SCHEMA,
    "validation_result_v0",
]

SOURCE_ELIGIBILITY_STATUSES = {
    "accepted_for_gate2",
    "accepted_as_source_candidate_for_gate2",
    "excluded_from_gate2",
    "requires_ocr_before_gate2",
    "duplicate_needs_canonical_choice",
    "unsupported_format",
    "methodology_or_output_artifact",
    "outside_case_scope",
    "metadata_review_required",
    "source_policy_review_required",
    # Legacy status values are accepted for stored older artifacts only. New
    # eligibility v2 decisions should use the explicit values above.
    "requires_manual_review",
    "not_source_document",
    "unknown_role_requires_review",
    "source_role_policy_review_required",
}

GATE2_HANDOFF_MODES = {
    "full_package_ready_for_gate2",
    "reduced_subset_ready_for_gate2",
    "gate2_blocked_requires_metadata_review",
    "gate2_blocked_requires_policy_review",
    "gate2_blocked_requires_duplicate_resolution",
    "gate2_blocked_requires_ocr",
    "gate2_blocked_no_eligible_sources",
    # Legacy mode accepted for stored older artifacts only. New handoff v2
    # decisions should use a specific blocker mode above.
    "gate2_blocked_requires_review",
}

OCR_POLICY_STATUSES = {
    "disabled",
    "enabled-not-executed",
    "required-before-gate2",
    "manual-review-only",
}

SOURCE_DOCUMENT_CLASSES = {
    "operations_table",
    "source_broker_report",
    "dividends_report",
    "fees_report",
    "withholding_report",
    "currency_rate_table",
}

METHODOLOGY_OR_OUTPUT_CLASSES = {
    "calculation_template",
    "tax_base_calculation",
    "explanation_template",
    "official_form",
}

TERMINAL_GATE2_BLOCKER_CODES = {
    "bytes_unavailable",
    "unsupported_format",
    "encrypted_file",
    "corrupt_file",
    "parser_failed",
}

BLOCKER_CODES = {
    "no_files",
    "bytes_unavailable",
    "unsupported_format",
    "encrypted_file",
    "corrupt_file",
    "parser_failed",
    "raster_requires_ocr_or_review",
    "zip_requires_review",
    "unknown_role",
    "llm_passport_prompt_unavailable",
    "llm_passport_model_failed",
    "llm_passport_validation_failed",
    "privacy_violation",
    "duplicate_review",
}


def stable_digest(parts: Iterable[object], *, length: int = 16) -> str:
    material = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]


def normalization_run_id(input_summaries: list[dict]) -> str:
    material = [
        f"{item.get('private_ref_hash')}:{item.get('extension')}:{item.get('mime_type')}"
        for item in input_summaries
    ]
    return f"normrun_{stable_digest(material)}"


def safe_artifact_refs(run_id: str) -> dict[str, str]:
    suffix = run_id.removeprefix("normrun_")
    return {
        "normalization_run_ref": run_id,
        "document_inventory_ref": f"docinv_{suffix}",
        "technical_readability_profile_ref": f"techprofiles_{suffix}",
        "private_normalized_slices_ref": f"privslices_{suffix}",
        "private_normalized_source_payloads_ref": f"privsrcpayloads_{suffix}",
        "private_normalized_source_units_ref": f"privsrcunits_{suffix}",
        "taxonomy_candidates_ref": f"taxcands_{suffix}",
        "normalization_blockers_ref": f"blockers_{suffix}",
        "document_source_eligibility_ref": f"docelig_{suffix}",
        "document_metadata_passport_ref": f"docpass_{suffix}",
        "gate1_issue_ledger_ref": f"issueledger_{suffix}",
        "document_usage_classification_ref": f"docusage_{suffix}",
        "domain_context_packet_ref": f"domainctx_{suffix}",
        "chat_visible_report_ref": f"normreport_{suffix}",
        "validation_result_ref": f"validation_{suffix}",
    }


def document_id(
    *,
    index: int,
    content_sha256: str | None,
    private_ref_hash: str,
    extension: str,
    mime_type: str,
) -> str:
    digest = content_sha256[:12] if content_sha256 else stable_digest(
        [private_ref_hash, extension, mime_type],
        length=12,
    )
    return f"brdoc_{index:03d}_{digest}"


def profile_id(document_id_value: str) -> str:
    return f"techprof_{document_id_value.removeprefix('brdoc_')}"


def taxonomy_candidate_id(document_id_value: str) -> str:
    return f"taxcand_{document_id_value.removeprefix('brdoc_')}"


def slice_id(document_id_value: str, suffix: str) -> str:
    return f"slice_{document_id_value.removeprefix('brdoc_')}_{suffix}"


def make_blocker(
    *,
    run_id: str,
    document_id: str | None,
    code: str,
    created_by_step: str,
    safe_message: str,
    review_action: str,
    severity: str = "blocking",
    blocks_next_gate: bool = True,
    reason: str | None = None,
) -> dict:
    if code not in BLOCKER_CODES:
        raise ValueError(f"unsupported blocker code: {code}")
    material = [run_id, document_id or "run", code, created_by_step, reason or ""]
    return {
        "blocker_id": f"blocker_{stable_digest(material, length=12)}",
        "run_id": run_id,
        "document_id": document_id,
        "code": code,
        "severity": severity,
        "blocks_gate2": blocks_next_gate,
        "blocks_next_gate": blocks_next_gate,
        "safe_message": safe_message,
        "review_action": review_action,
        "created_by_step": created_by_step,
        "reason_code": reason,
    }


def safety_flags() -> dict[str, bool]:
    return dict(SAFETY_FLAGS)
