from __future__ import annotations

import copy
import json
from typing import Iterable

from .blockers import privacy_violation
from .contracts import BLOCKER_CODES, GATE2_HANDOFF_MODES, OCR_POLICY_STATUSES, SOURCE_ELIGIBILITY_STATUSES
from .source_provenance import validate_normalized_slice_provenance
from .full_source import SOURCE_PAYLOAD_SCHEMA_VERSION, validate_full_source_unit
from .pdf_text_layer import validate_pdf_text_layer_payload
from .table_projection import TableProjectionValidator


SAFE_REPORT_ALLOWED_KEYS = {
    "schema_version",
    "report_id",
    "normalization_run_id",
    "run_status",
    "trigger_type",
    "entrypoint",
    "normalizer_version",
    "files_total",
    "container_counts",
    "document_class_counts",
    "duplicate_count",
    "blockers_total",
    "summary_counts",
    "file_ref_visibility",
    "input_context",
    "normalization_run",
    "document_inventory",
    "documents",
    "technical_readability_profiles",
    "taxonomy_candidates",
    "normalization_blockers",
    "blockers",
    "document_source_eligibility",
    "source_eligibility_summary",
    "gate2_handoff",
    "gate1_issue_ledger",
    "gate1_issue_ledger_summary",
    "document_usage_classification",
    "document_usage_classification_summary",
    "domain_context_packet",
    "domain_context_packet_summary",
    "domain_ingestion_summary",
    "full_source_coverage_summary",
    "table_projection_summary",
    "validation_result",
    "document_metadata_passport_summary",
    "gate1_metadata_gap_report_summary",
    "gate1_clarification_request_summary",
    "gate1_clarification_questions",
    "gate1_clarification_resolution_summary",
    "case_groups",
    "safe_artifact_refs",
    "private_artifact_summary",
    "supported_contracts",
    "recommended_next_step",
    "next_step",
    "gate2_handoff_status",
    "gate2_handoff_mode",
    "gate2_reduced_subset_ready",
    "safety_flags",
    "safety_statement",
}

FORBIDDEN_FIELD_NAMES = {
    "file_id",
    "filename",
    "original_filename",
    "original_filename_private",
    "private_ref",
    "private_path",
    "path",
    "raw_text",
    "raw_rows",
    "rows",
    "text",
    "content",
    "normalized_table_slice",
    "normalized_text_slice",
}

FALSE_SAFETY_FLAGS = {
    "tax_correctness_claimed",
    "source_fact_extraction_performed",
    "declaration_generated",
    "xlsx_generated",
    "fns_filing_claimed",
    "ocr_performed",
    "customer_docs_loaded_to_knowledge",
}


def validate_artifacts(package: dict) -> dict:
    errors: list[dict] = []
    documents = package.get("document_inventory", {}).get("documents", [])
    profiles = package.get("technical_readability_profiles", [])
    slices = package.get("private_normalized_slices", [])
    source_payloads = package.get("private_normalized_source_payloads", [])
    source_units = package.get("private_normalized_source_units", [])
    table_projections = package.get("private_normalized_table_projections", [])
    taxonomy_candidates = package.get("taxonomy_candidates", [])
    blockers = package.get("normalization_blockers", [])
    eligibility_payload = package.get("document_source_eligibility", {})
    eligibility_entries = eligibility_payload.get("entries", []) if isinstance(eligibility_payload, dict) else []
    gate2_handoff = package.get("gate2_handoff", {}) if isinstance(package.get("gate2_handoff"), dict) else {}
    issue_ledger = package.get("gate1_issue_ledger", {}) if isinstance(package.get("gate1_issue_ledger"), dict) else {}
    issue_entries = issue_ledger.get("entries", []) if isinstance(issue_ledger.get("entries"), list) else []
    usage_classification = (
        package.get("document_usage_classification", {})
        if isinstance(package.get("document_usage_classification"), dict)
        else {}
    )
    usage_entries = usage_classification.get("entries", []) if isinstance(usage_classification.get("entries"), list) else []
    domain_context_packet = package.get("domain_context_packet", {}) if isinstance(package.get("domain_context_packet"), dict) else {}
    passports = package.get("document_metadata_passports", [])
    passport_validation = package.get("document_metadata_passport_validation", {})
    llm_packages = package.get("llm_document_packages", [])
    run_id = package.get("normalization_run", {}).get("run_id")

    blocker_ids = {item.get("blocker_id") for item in blockers}
    profile_by_doc = {item.get("document_id"): item for item in profiles}
    document_by_id = {item.get("document_id"): item for item in documents}
    document_ids = {item.get("document_id") for item in documents}
    taxonomy_doc_ids = {item.get("document_id") for item in taxonomy_candidates}
    eligibility_doc_ids = {item.get("document_id") for item in eligibility_entries if isinstance(item, dict)}
    usage_doc_ids = {item.get("document_ref") for item in usage_entries if isinstance(item, dict)}
    issue_ids = {item.get("issue_id") for item in issue_entries if isinstance(item, dict)}
    passport_doc_ids = {item.get("document_id") for item in passports if isinstance(item, dict)}
    llm_package_doc_ids = {item.get("document_id") for item in llm_packages if isinstance(item, dict)}

    for blocker in blockers:
        if blocker.get("code") not in BLOCKER_CODES:
            errors.append(_error("unsupported_blocker_code", blocker.get("blocker_id")))
        if blocker.get("run_id") != run_id:
            errors.append(_error("blocker_run_ref_mismatch", blocker.get("blocker_id")))

    for document in documents:
        document_id = document.get("document_id")
        refs = document.get("blocker_refs")
        if not isinstance(refs, list):
            errors.append(_error("document_missing_blocker_refs", document_id))
            refs = []
        for ref in refs:
            if ref not in blocker_ids:
                errors.append(_error("document_unknown_blocker_ref", document_id))

        if document.get("bytes_status") == "available" and document.get("container_format") in {
            "csv",
            "txt",
            "html_text",
            "xlsx",
            "pdf",
            "zip",
            "docx",
            "image",
        }:
            if document_id not in profile_by_doc and not refs:
                errors.append(_error("supported_readable_file_has_no_profile_or_blocker", document_id))

        if document_id not in taxonomy_doc_ids:
            errors.append(_error("document_missing_taxonomy_candidate", document_id))
        if document_id not in eligibility_doc_ids:
            errors.append(_error("document_missing_source_eligibility", document_id))
        if usage_entries and document_id not in usage_doc_ids:
            errors.append(_error("document_missing_usage_classification", document_id))
        if passports and document_id not in passport_doc_ids:
            errors.append(_error("document_missing_metadata_passport", document_id))
        if llm_packages and document_id not in llm_package_doc_ids:
            errors.append(_error("document_missing_llm_package", document_id))

    for private_slice in slices:
        slice_document_id = private_slice.get("document_id")
        if not private_slice.get("document_id"):
            errors.append(_error("slice_missing_document_id", private_slice.get("slice_id")))
        if not private_slice.get("profile_id"):
            errors.append(_error("slice_missing_profile_id", private_slice.get("slice_id")))
        if not private_slice.get("source_location"):
            errors.append(_error("slice_missing_source_location", private_slice.get("slice_id")))
        document = document_by_id.get(slice_document_id)
        if document is None:
            errors.append(_error("slice_unknown_document_ref", private_slice.get("slice_id")))
            continue
        provenance_validation = validate_normalized_slice_provenance(
            private_slice=private_slice,
            normalization_run_id=str(run_id or ""),
            document_id=str(slice_document_id or ""),
            source_checksum_sha256=str(document.get("sha256") or ""),
        )
        errors.extend(copy.deepcopy(provenance_validation.get("errors") or []))

    payload_refs = {
        str(item.get("source_payload_ref"))
        for item in source_payloads
        if isinstance(item, dict) and item.get("source_payload_ref")
    }
    for payload in source_payloads:
        if not isinstance(payload, dict):
            errors.append(_error("full_source_payload_not_object", run_id))
            continue
        payload_ref = payload.get("source_payload_ref")
        if payload.get("schema_version") != SOURCE_PAYLOAD_SCHEMA_VERSION:
            errors.append(_error("full_source_payload_schema_mismatch", payload_ref))
        if payload.get("document_ref") not in document_ids:
            errors.append(_error("full_source_payload_unknown_document_ref", payload_ref))
        if payload.get("visibility") != "private_case":
            errors.append(_error("full_source_payload_visibility_invalid", payload_ref))
        if payload.get("knowledge_rag_used") is not False:
            errors.append(_error("full_source_payload_knowledge_guard_failed", payload_ref))
        if payload.get("vectorization_performed") is not False:
            errors.append(_error("full_source_payload_vector_guard_failed", payload_ref))
        if payload.get("container_format") == "pdf":
            pdf_validation = validate_pdf_text_layer_payload(payload)
            errors.extend(copy.deepcopy(pdf_validation.get("errors") or []))

    for unit in source_units:
        if not isinstance(unit, dict):
            errors.append(_error("full_source_unit_not_object", run_id))
            continue
        document_id = str(unit.get("document_id") or "")
        document = document_by_id.get(document_id)
        if document is None:
            errors.append(_error("full_source_unit_unknown_document_ref", unit.get("unit_ref")))
            continue
        if str(unit.get("parent_payload_ref") or "") not in payload_refs:
            errors.append(_error("full_source_unit_parent_payload_missing", unit.get("unit_ref")))
        unit_validation = validate_full_source_unit(
            unit=unit,
            normalization_run_id=str(run_id or ""),
            document_id=document_id,
            source_checksum_sha256=str(document.get("sha256") or ""),
        )
        errors.extend(copy.deepcopy(unit_validation.get("errors") or []))

    source_unit_refs = {
        str(item.get("unit_ref") or "")
        for item in source_units
        if isinstance(item, dict)
    }
    table_validator = TableProjectionValidator()
    for projection in table_projections:
        if not isinstance(projection, dict):
            errors.append(_error("table_projection_not_object", run_id))
            continue
        projection_ref = projection.get("table_projection_id")
        if projection.get("source_document_ref") not in document_ids:
            errors.append(_error("table_projection_unknown_document_ref", projection_ref))
        if str(projection.get("source_unit_ref") or "") not in source_unit_refs:
            errors.append(_error("table_projection_unknown_source_unit_ref", projection_ref))
        projection_validation = table_validator.validate(projection)
        errors.extend(copy.deepcopy(projection_validation.get("errors") or []))

    for taxonomy_candidate in taxonomy_candidates:
        if taxonomy_candidate.get("document_id") not in document_ids:
            errors.append(_error("taxonomy_unknown_document_ref", taxonomy_candidate.get("taxonomy_candidate_id")))

    for entry in eligibility_entries:
        document_id = entry.get("document_id")
        if entry.get("normalization_run_id") != run_id:
            errors.append(_error("eligibility_run_ref_mismatch", document_id))
        if document_id not in document_ids:
            errors.append(_error("eligibility_unknown_document_ref", document_id))
        if entry.get("source_eligibility") not in SOURCE_ELIGIBILITY_STATUSES:
            errors.append(_error("unsupported_source_eligibility", document_id))
        if entry.get("ocr_policy_status") not in OCR_POLICY_STATUSES:
            errors.append(_error("unsupported_ocr_policy_status", document_id))
        refs = entry.get("blocker_refs") or []
        if not isinstance(refs, list):
            errors.append(_error("eligibility_missing_blocker_refs", document_id))
            refs = []
        for ref in refs:
            if ref not in blocker_ids:
                errors.append(_error("eligibility_unknown_blocker_ref", document_id))
        if entry.get("included_in_reduced_subset") and entry.get("can_enter_gate2") is not True:
            errors.append(_error("included_document_cannot_enter_gate2", document_id))
        if entry.get("included_in_reduced_subset") and entry.get("exclusion_is_terminal"):
            errors.append(_error("terminal_document_included_for_gate2", document_id))

    if issue_ledger:
        if issue_ledger.get("schema_version") != "gate1_issue_ledger_v0":
            errors.append(_error("issue_ledger_schema_mismatch", issue_ledger.get("schema_version")))
        if issue_ledger.get("normalization_run_id") != run_id:
            errors.append(_error("issue_ledger_run_ref_mismatch", issue_ledger.get("normalization_run_id")))
        for issue in issue_entries:
            issue_id = issue.get("issue_id")
            if issue.get("normalization_run_id") != run_id:
                errors.append(_error("issue_run_ref_mismatch", issue_id))
            if issue.get("status") not in {"unresolved", "resolved"}:
                errors.append(_error("issue_status_invalid", issue_id))
            for document_ref in issue.get("target_document_refs") or []:
                if document_ref not in document_ids:
                    errors.append(_error("issue_unknown_document_ref", issue_id))

    if usage_classification:
        if usage_classification.get("schema_version") != "document_usage_classification_v0":
            errors.append(_error("usage_classification_schema_mismatch", usage_classification.get("schema_version")))
        if usage_classification.get("normalization_run_id") != run_id:
            errors.append(_error("usage_classification_run_ref_mismatch", usage_classification.get("normalization_run_id")))
        for entry in usage_entries:
            document_ref = entry.get("document_ref")
            if document_ref not in document_ids:
                errors.append(_error("usage_unknown_document_ref", document_ref))
            for issue_ref in entry.get("issue_refs") or []:
                if issue_ref not in issue_ids:
                    errors.append(_error("usage_unknown_issue_ref", issue_ref))
            for issue_ref in entry.get("warning_issue_refs") or []:
                if issue_ref not in issue_ids:
                    errors.append(_error("usage_unknown_warning_issue_ref", issue_ref))

    if domain_context_packet:
        if domain_context_packet.get("schema_version") != "domain_context_packet_v0":
            errors.append(_error("domain_context_packet_schema_mismatch", domain_context_packet.get("schema_version")))
        if domain_context_packet.get("normalization_run_id") != run_id:
            errors.append(_error("domain_context_packet_run_ref_mismatch", domain_context_packet.get("normalization_run_id")))
        for document_ref in domain_context_packet.get("document_refs") or []:
            if document_ref not in document_ids:
                errors.append(_error("domain_packet_unknown_document_ref", document_ref))
        for issue_ref in domain_context_packet.get("unresolved_issue_refs") or []:
            if issue_ref not in issue_ids:
                errors.append(_error("domain_packet_unknown_issue_ref", issue_ref))
        next_stage_refs = domain_context_packet.get("next_stage_refs")
        if isinstance(next_stage_refs, dict):
            for bucket, refs in next_stage_refs.items():
                if not isinstance(refs, list):
                    errors.append(_error("domain_packet_next_stage_bucket_not_list", bucket))
                    continue
                for document_ref in refs:
                    if document_ref not in document_ids:
                        errors.append(_error("domain_packet_next_stage_unknown_document_ref", document_ref))
            source_ready_refs = {
                entry.get("document_ref")
                for entry in usage_entries
                if isinstance(entry, dict)
                and (entry.get("readiness_by_stage") or {}).get("source_fact_extraction") in {"ready", "ready_with_issues"}
            }
            packet_source_ready_refs = set(next_stage_refs.get("source_fact_ready_refs") or [])
            if packet_source_ready_refs != source_ready_refs:
                errors.append(_error("domain_packet_source_ready_refs_mismatch", ",".join(sorted(source_ready_refs ^ packet_source_ready_refs))))
            classified_source_ready_refs = set()
            for bucket in (
                "primary_source_extraction_refs",
                "secondary_source_extraction_refs",
                "audit_reference_refs",
                "duplicate_or_non_primary_refs",
            ):
                classified_source_ready_refs.update(next_stage_refs.get(bucket) or [])
            missing_source_ready_refs = source_ready_refs - classified_source_ready_refs
            if missing_source_ready_refs:
                errors.append(_error("domain_packet_source_ready_ref_not_classified", ",".join(sorted(missing_source_ready_refs))))
            if next_stage_refs.get("dropped_source_ready_refs"):
                errors.append(_error("domain_packet_dropped_source_ready_refs", ",".join(next_stage_refs.get("dropped_source_ready_refs") or [])))
        document_issue_refs = domain_context_packet.get("document_issue_refs")
        if isinstance(document_issue_refs, dict):
            for document_ref, refs in document_issue_refs.items():
                if document_ref not in document_ids:
                    errors.append(_error("domain_packet_issue_map_unknown_document_ref", document_ref))
                if not isinstance(refs, list):
                    errors.append(_error("domain_packet_issue_map_refs_not_list", document_ref))
                    continue
                for issue_ref in refs:
                    if issue_ref not in issue_ids:
                        errors.append(_error("domain_packet_issue_map_unknown_issue_ref", issue_ref))
        private_slice_access = (
            domain_context_packet.get("private_slice_access")
            if isinstance(domain_context_packet.get("private_slice_access"), dict)
            else {}
        )
        if private_slice_access.get("source_unit_schema_version") != "source_unit_provenance_v0":
            errors.append(_error("domain_packet_source_unit_schema_mismatch", run_id))
        if private_slice_access.get("source_value_projection_policy") != "private_payload_path_plus_checksum_v0":
            errors.append(_error("domain_packet_source_value_policy_mismatch", run_id))
        if private_slice_access.get("row_segment_coverage_policy") != "source_unit_coverage_v0":
            errors.append(_error("domain_packet_source_unit_coverage_policy_mismatch", run_id))

    if passports:
        for passport in passports:
            document_id = passport.get("document_id")
            if passport.get("schema_version") != "document_metadata_passport_v0":
                errors.append(_error("passport_schema_mismatch", document_id))
            if passport.get("normalization_run_id") != run_id:
                errors.append(_error("passport_run_ref_mismatch", document_id))
            if document_id not in document_ids:
                errors.append(_error("passport_unknown_document_ref", document_id))
            if passport.get("validator_status") not in {"passed", "failed", "privacy_failed", "pending"}:
                errors.append(_error("passport_validator_status_invalid", document_id))
    if passport_validation:
        if passport_validation.get("schema_version") != "document_metadata_passport_validation_v0":
            errors.append(_error("passport_validation_schema_mismatch", passport_validation.get("schema_version")))
        if passport_validation.get("normalization_run_id") != run_id:
            errors.append(_error("passport_validation_run_ref_mismatch", passport_validation.get("normalization_run_id")))

    for profile in profiles:
        if profile.get("container_format") == "zip":
            has_inventory = bool(profile.get("member_inventory")) or bool(profile.get("member_count"))
            doc_refs = {
                blocker.get("code")
                for blocker in blockers
                if blocker.get("document_id") == profile.get("document_id")
            }
            if not has_inventory and not ({"parser_failed", "unsupported_format", "corrupt_file"} & doc_refs):
                errors.append(_error("zip_missing_inventory_or_blocker", profile.get("document_id")))
        if profile.get("container_format") == "pdf" and profile.get("raster_or_scan_likelihood") in {"medium", "high"}:
            doc_refs = {
                blocker.get("code")
                for blocker in blockers
                if blocker.get("document_id") == profile.get("document_id")
            }
            if "raster_requires_ocr_or_review" not in doc_refs:
                errors.append(_error("raster_pdf_missing_gate2_blocker", profile.get("document_id")))

    gate2_status = package.get("normalization_run", {}).get("gate2_handoff_status")
    gate2_mode = package.get("normalization_run", {}).get("gate2_handoff_mode")
    if gate2_mode not in GATE2_HANDOFF_MODES:
        errors.append(_error("unsupported_gate2_handoff_mode", gate2_mode))
    if gate2_handoff.get("handoff_mode") != gate2_mode:
        errors.append(_error("gate2_handoff_mode_mismatch", gate2_mode))
    included_doc_ids = set(gate2_handoff.get("included_document_ids") or [])
    blocking_docs = {
        blocker.get("document_id")
        for blocker in blockers
        if blocker.get("blocks_gate2") and blocker.get("document_id")
    }
    if blocking_docs & included_doc_ids:
        errors.append(_error("gate2_included_doc_has_terminal_blocker", ",".join(sorted(blocking_docs & included_doc_ids))))
    if gate2_status in {"ready_with_safe_refs", "ready_with_reduced_subset"} and not included_doc_ids:
        errors.append(_error("gate2_ready_without_included_documents", gate2_status))
    if gate2_mode == "reduced_subset_ready_for_gate2" and gate2_handoff.get("reduced_subset_validated") is not True:
        errors.append(_error("reduced_subset_not_validated", gate2_status))
    if gate2_mode != "reduced_subset_ready_for_gate2" and gate2_status == "ready_with_reduced_subset":
        errors.append(_error("reduced_subset_status_mode_mismatch", gate2_mode))

    return _validation_result(errors=errors, privacy_blocker=None)


def validate_safe_report(
    *,
    safe_report: dict,
    private_markers: Iterable[str],
    run_id: str,
) -> dict:
    errors: list[dict] = []
    unknown_keys = sorted(set(safe_report) - SAFE_REPORT_ALLOWED_KEYS)
    if unknown_keys:
        errors.append(_error("safe_report_unknown_keys", ",".join(unknown_keys)))

    forbidden_paths = _find_forbidden_fields(safe_report)
    for path in forbidden_paths:
        errors.append(_error("safe_report_forbidden_field", path))

    flags = safe_report.get("safety_flags") if isinstance(safe_report.get("safety_flags"), dict) else {}
    for flag in FALSE_SAFETY_FLAGS:
        if flags.get(flag) is not False:
            errors.append(_error("safety_flag_not_false", flag))

    rendered = json.dumps(safe_report, ensure_ascii=False, sort_keys=True)
    leaked = [
        marker
        for marker in private_markers
        if isinstance(marker, str) and len(marker) >= 3 and marker in rendered
    ]
    privacy_blocker = privacy_violation(run_id, "private_marker_detected") if leaked else None
    return _validation_result(errors=errors, privacy_blocker=privacy_blocker)


def merge_validation_results(*results: dict) -> dict:
    errors: list[dict] = []
    privacy_blocker = None
    for result in results:
        errors.extend(copy.deepcopy(result.get("errors") or []))
        if result.get("privacy_blocker"):
            privacy_blocker = result["privacy_blocker"]
    return _validation_result(errors=errors, privacy_blocker=privacy_blocker)


def _validation_result(*, errors: list[dict], privacy_blocker: dict | None) -> dict:
    if privacy_blocker:
        status = "privacy_failed"
    elif errors:
        status = "failed"
    else:
        status = "passed"
    return {
        "schema_version": "validation_result_v0",
        "status": status,
        "passed": status == "passed",
        "errors_count": len(errors),
        "errors": errors,
        "privacy_blocker": privacy_blocker,
    }


def _find_forbidden_fields(value: object, *, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in FORBIDDEN_FIELD_NAMES:
                findings.append(child_path)
            findings.extend(_find_forbidden_fields(child, prefix=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_forbidden_fields(child, prefix=f"{prefix}[{index}]"))
    return findings


def _error(code: str, subject: object) -> dict:
    return {"code": code, "subject": str(subject or "")}
