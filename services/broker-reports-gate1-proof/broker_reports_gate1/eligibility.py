from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .contracts import (
    METHODOLOGY_OR_OUTPUT_CLASSES,
    OCR_POLICY_STATUSES,
    SOURCE_DOCUMENT_CLASSES,
    SOURCE_ELIGIBILITY_STATUSES,
    TERMINAL_GATE2_BLOCKER_CODES,
    stable_digest,
)
from .criticality import PERIOD_METADATA_FIELDS, unresolved_metadata_field_groups


REVIEW_ELIGIBILITIES = {
    "metadata_review_required",
    "source_policy_review_required",
    "duplicate_needs_canonical_choice",
}

ACCEPTED_ELIGIBILITIES = {
    "accepted_for_gate2",
    "accepted_as_source_candidate_for_gate2",
}

EXCLUDED_ELIGIBILITIES = {
    "excluded_from_gate2",
    "unsupported_format",
    "not_source_document",
    "methodology_or_output_artifact",
    "outside_case_scope",
}


def build_document_source_eligibility(
    *,
    run_id: str,
    documents: list[dict[str, Any]],
    taxonomy_candidates: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    ocr_policy_status: str = "disabled",
    document_metadata_passports: list[dict[str, Any]] | None = None,
    clarification_resolutions: list[dict[str, Any]] | None = None,
    input_context: dict[str, Any] | None = None,
    criticality_refinement_enabled: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if ocr_policy_status not in OCR_POLICY_STATUSES:
        ocr_policy_status = "disabled"

    blockers_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for blocker in blockers:
        document_id = blocker.get("document_id")
        if document_id:
            blockers_by_doc[str(document_id)].append(blocker)

    taxonomy_by_doc = {
        str(candidate.get("document_id")): candidate
        for candidate in taxonomy_candidates
        if candidate.get("document_id")
    }
    passport_by_doc = {
        str(passport.get("document_id")): passport
        for passport in document_metadata_passports or []
        if passport.get("document_id")
    }
    clarification_state = _clarification_resolution_state(clarification_resolutions or [], documents)
    case_scope_basis = _case_scope_basis(input_context or {})
    duplicate_auto_resolution = _exact_duplicate_resolution_state(
        documents=documents,
        taxonomy_by_doc=taxonomy_by_doc,
        passport_by_doc=passport_by_doc,
        refinement_enabled=criticality_refinement_enabled,
    )

    entries = [
        _entry_for_document(
            run_id=run_id,
            document=document,
            taxonomy_candidate=taxonomy_by_doc.get(str(document.get("document_id"))) or {},
            blockers=blockers_by_doc.get(str(document.get("document_id")), []),
            ocr_policy_status=ocr_policy_status,
            metadata_passport=passport_by_doc.get(str(document.get("document_id"))) or {},
            clarification_state=clarification_state,
            duplicate_auto_resolution=duplicate_auto_resolution.get(str(document.get("document_id"))) or {},
            case_scope_basis=case_scope_basis,
            criticality_refinement_enabled=criticality_refinement_enabled,
        )
        for document in documents
    ]
    handoff = _handoff_summary(entries)
    summary = _summary(entries, handoff)
    return (
        {
            "schema_version": "document_source_eligibility_v0",
            "normalization_run_id": run_id,
            "ocr_policy_status": ocr_policy_status,
            "entries": entries,
        },
        summary,
        handoff,
    )


def _entry_for_document(
    *,
    run_id: str,
    document: dict[str, Any],
    taxonomy_candidate: dict[str, Any],
    blockers: list[dict[str, Any]],
    ocr_policy_status: str,
    metadata_passport: dict[str, Any],
    clarification_state: dict[str, Any],
    duplicate_auto_resolution: dict[str, Any],
    case_scope_basis: dict[str, Any],
    criticality_refinement_enabled: bool,
) -> dict[str, Any]:
    document_id = str(document.get("document_id") or "")
    blocker_codes = {str(blocker.get("code") or "") for blocker in blockers}
    blocker_refs = sorted(str(blocker.get("blocker_id")) for blocker in blockers if blocker.get("blocker_id"))
    doc_resolution_state = clarification_state["by_doc"].get(document_id, {})
    resolved_fields = set(doc_resolution_state.get("resolved_fields") or set())
    resolved_question_ids = set(doc_resolution_state.get("question_ids") or set())
    role_resolution = str(doc_resolution_state.get("document_role") or "")
    mark_not_source = bool(doc_resolution_state.get("mark_as_not_source"))
    mark_outside_scope = bool(doc_resolution_state.get("mark_as_outside_scope"))
    canonical_choice_by_group = clarification_state["canonical_by_group"]
    duplicate_group_id = str(document.get("duplicate_group_id") or "")
    canonical_for_group = canonical_choice_by_group.get(duplicate_group_id) if duplicate_group_id else None
    duplicate_resolved_as_canonical = bool(canonical_for_group and canonical_for_group == document_id)
    duplicate_resolved_as_noncanonical = bool(canonical_for_group and canonical_for_group != document_id)
    taxonomy_class = str(taxonomy_candidate.get("document_class_candidate") or "unknown_or_needs_review")
    source_role_policy_status = str(taxonomy_candidate.get("source_role_policy_status") or "not_applicable")
    source_policy_review_required = taxonomy_candidate.get("source_policy_review_required") is True
    taxonomy_reasons = [
        str(item)
        for item in taxonomy_candidate.get("safe_reason_codes", [])
        if item
    ]
    passport_status = str(metadata_passport.get("validator_status") or "not_available")
    passport_content_kind = str(metadata_passport.get("content_kind") or "")
    passport_source_confidence = str(metadata_passport.get("source_candidate_confidence") or "none")
    passport_metadata_confidence = str(metadata_passport.get("metadata_confidence") or "none")
    passport_review_required = metadata_passport.get("review_required") is True
    passport_role_summary = _passport_role_summary(metadata_passport)
    passport_roles = passport_role_summary["roles"]
    passport_source_role_confidence = passport_role_summary["source_role_confidence"]
    passport_source_policy_effects = passport_role_summary["source_policy_effects"]
    passport_has_source_role = bool(
        passport_roles
        & {
            "source_broker_report",
            "source_operations_table",
            "source_dividend_report",
            "source_withholding_report",
            "source_cashflow_report",
        }
    ) or passport_content_kind == "source_report_candidate"
    if role_resolution in {
        "source_broker_report",
        "source_operations_table",
        "source_dividend_report",
        "source_withholding_report",
        "source_cashflow_report",
    }:
        passport_has_source_role = True
        passport_source_role_confidence = _max_confidence(passport_source_role_confidence, "medium")
    passport_methodology_or_output = passport_content_kind in {
        "methodology_or_reference",
        "output_or_calculation_artifact",
    } or bool(passport_roles & {"methodology_or_reference", "calculation_or_output_artifact", "official_form_or_declaration"})
    passport_outside_scope = passport_content_kind == "outside_case_scope" or "outside_case_scope" in passport_roles or mark_outside_scope
    passport_unsupported = passport_content_kind == "unsupported_or_unreadable"
    passport_duplicate = passport_content_kind == "duplicate_candidate" or "duplicate_candidate" in passport_roles
    passport_valid = passport_status == "passed" and str(metadata_passport.get("passport_status") or "") == "validated"
    passport_missing_fields = [
        str(item)
        for item in metadata_passport.get("missing_metadata_fields") or []
        if item and str(item) not in resolved_fields
    ]
    passport_conflict_flags = [
        str(item)
        for item in metadata_passport.get("conflict_flags") or []
        if item and str(item) not in resolved_fields
    ]
    passport_evidence_refs = [str(item) for item in metadata_passport.get("evidence_refs") or [] if item]
    passport_review_still_required = passport_review_required and not resolved_fields
    passport_source_confident = passport_source_confidence in {"medium", "high"} and passport_source_role_confidence in {"medium", "high"}
    period_scope_basis = _period_scope_basis(
        document=document,
        taxonomy_candidate=taxonomy_candidate,
        metadata_passport=metadata_passport,
        case_scope_basis=case_scope_basis,
        passport_has_source_role=passport_has_source_role,
        passport_evidence_refs=passport_evidence_refs,
        period_fields_missing=bool(set(passport_missing_fields) & PERIOD_METADATA_FIELDS),
    )
    unresolved_field_groups = unresolved_metadata_field_groups(
        missing_fields=passport_missing_fields,
        conflict_flags=passport_conflict_flags,
        source_confidence_low=bool(passport_valid and passport_has_source_role and not passport_source_confident),
        review_required_without_fields=bool(passport_review_still_required and not passport_missing_fields and not passport_conflict_flags),
        period_scope_basis=period_scope_basis,
        refinement_enabled=criticality_refinement_enabled,
    )
    unresolved_critical_fields = set(unresolved_field_groups["critical"])
    unresolved_clarifying_fields = set(unresolved_field_groups["clarifying"])
    unresolved_non_critical_fields = set(unresolved_field_groups["non_critical"])
    passport_missing_required = bool(unresolved_critical_fields)
    passport_metadata_confidence_effective = passport_metadata_confidence
    if resolved_fields and passport_metadata_confidence_effective in {"none", "low"}:
        passport_metadata_confidence_effective = "medium"
    source_evidence_available = bool(passport_evidence_refs or resolved_fields)
    passport_metadata_ready = (
        passport_metadata_confidence_effective in {"medium", "high"}
        and not passport_missing_required
        and source_evidence_available
    )
    if (
        criticality_refinement_enabled
        and not passport_missing_required
        and passport_valid
        and passport_has_source_role
        and passport_source_confident
        and source_evidence_available
    ):
        passport_metadata_ready = True
    passport_requires_policy_review = (
        source_policy_review_required
        or source_role_policy_status == "review_required"
        or "requires_policy_review" in passport_source_policy_effects
    )

    source_eligibility = "metadata_review_required"
    reason_codes = set(taxonomy_reasons)
    if period_scope_basis.get("period_fields_missing") is True:
        reason_codes.update(str(item) for item in period_scope_basis.get("reason_codes") or [] if item)
    review_action = "specialist_review_document_role"
    doc_ocr_policy_status = ocr_policy_status
    can_enter_gate2 = False
    included = False
    terminal = False
    specialist_decision = True

    if mark_not_source:
        source_eligibility = "excluded_from_gate2"
        reason_codes.update(["clarification_marked_not_source"])
        review_action = "keep_out_of_gate2_source_subset"
        terminal = True
        specialist_decision = False
    elif duplicate_resolved_as_noncanonical:
        source_eligibility = "excluded_from_gate2"
        reason_codes.update(["clarification_duplicate_not_canonical"])
        review_action = "keep_out_of_gate2_source_subset"
        terminal = True
        specialist_decision = False
    elif duplicate_auto_resolution.get("auto_resolved") is True and duplicate_auto_resolution.get("is_canonical") is not True:
        source_eligibility = "excluded_from_gate2"
        reason_codes.update(
            [
                "exact_duplicate_auto_canonicalized",
                "noncanonical_exact_duplicate_excluded",
                "exact_duplicate_latest_wins",
            ]
        )
        review_action = "keep_out_of_gate2_source_subset"
        terminal = True
        specialist_decision = False
    elif "bytes_unavailable" in blocker_codes:
        source_eligibility = "excluded_from_gate2"
        reason_codes.update(["bytes_unavailable", "source_bytes_not_available"])
        review_action = "verify_byte_access_or_reupload"
        terminal = True
    elif "unsupported_format" in blocker_codes or taxonomy_class == "unsupported":
        source_eligibility = "unsupported_format"
        reason_codes.update(["unsupported_format", taxonomy_class])
        review_action = "request_supported_replacement_or_manual_review"
        terminal = True
    elif blocker_codes & {"encrypted_file", "corrupt_file", "parser_failed"}:
        source_eligibility = "excluded_from_gate2"
        reason_codes.update(sorted(blocker_codes & {"encrypted_file", "corrupt_file", "parser_failed"}))
        review_action = "request_clean_supported_replacement"
        terminal = True
    elif (
        "duplicate_review" in blocker_codes or document.get("duplicate_of_document_id")
    ) and not duplicate_resolved_as_canonical and duplicate_auto_resolution.get("is_canonical") is not True:
        source_eligibility = "duplicate_needs_canonical_choice"
        reason_codes.update(["duplicate_review", "canonical_source_choice_required", "semantic_duplicate_requires_user_choice"])
        review_action = "specialist_choose_canonical_duplicate"
        if "raster_requires_ocr_or_review" in blocker_codes:
            reason_codes.update(["raster_requires_ocr_or_review", "ocr_not_executed_in_gate1"])
            doc_ocr_policy_status = (
                "required-before-gate2"
                if ocr_policy_status in {"disabled", "enabled-not-executed"}
                else ocr_policy_status
            )
    elif "raster_requires_ocr_or_review" in blocker_codes or taxonomy_class == "image_or_scan_requires_review":
        source_eligibility = "requires_ocr_before_gate2"
        reason_codes.update(["raster_requires_ocr_or_review", "ocr_not_executed_in_gate1"])
        review_action = "route_to_future_ocr_gate_or_manual_review"
        doc_ocr_policy_status = (
            "required-before-gate2"
            if ocr_policy_status in {"disabled", "enabled-not-executed"}
            else ocr_policy_status
        )
    elif (
        passport_valid
        and passport_duplicate
        and not duplicate_resolved_as_canonical
        and duplicate_auto_resolution.get("is_canonical") is not True
    ):
        source_eligibility = "duplicate_needs_canonical_choice"
        reason_codes.update(["passport_duplicate_candidate", "canonical_source_choice_required", "semantic_duplicate_requires_user_choice"])
        review_action = "specialist_choose_canonical_duplicate"
    elif passport_valid and passport_methodology_or_output:
        source_eligibility = "methodology_or_output_artifact"
        reason_codes.update(["passport_methodology_or_output_artifact", passport_content_kind])
        review_action = "keep_out_of_gate2_source_subset"
        terminal = True
        specialist_decision = False
    elif passport_valid and passport_outside_scope:
        source_eligibility = "outside_case_scope"
        reason_codes.update(["passport_outside_case_scope"])
        review_action = "keep_out_of_gate2_source_subset"
        terminal = True
        specialist_decision = False
    elif passport_valid and passport_unsupported:
        source_eligibility = "unsupported_format"
        reason_codes.update(["passport_unsupported_or_unreadable"])
        review_action = "request_supported_replacement_or_manual_review"
        terminal = True
    elif passport_valid and passport_has_source_role and not passport_source_confident:
        source_eligibility = "metadata_review_required"
        reason_codes.update(["document_metadata_passport_source_confidence_low", passport_source_confidence, passport_source_role_confidence])
        review_action = "specialist_review_document_metadata_passport"
    elif passport_valid and passport_has_source_role and not passport_metadata_ready:
        source_eligibility = "metadata_review_required"
        reason_codes.update(["document_metadata_passport_incomplete", passport_source_confidence, passport_metadata_confidence])
        if passport_missing_fields:
            reason_codes.add("passport_missing_metadata_fields")
        if passport_conflict_flags:
            reason_codes.add("passport_conflict_flags_present")
        if not passport_evidence_refs:
            reason_codes.add("passport_missing_evidence_refs")
        review_action = "specialist_review_document_metadata_passport"
    elif passport_valid and passport_has_source_role and passport_requires_policy_review:
        if taxonomy_class in SOURCE_DOCUMENT_CLASSES or source_role_policy_status == "approved":
            source_eligibility = "accepted_for_gate2"
            reason_codes.update(["accepted_source_document", "document_metadata_passport_validated"])
            review_action = "enter_gate2_source_fact_extraction_with_issue_context"
        else:
            source_eligibility = "accepted_as_source_candidate_for_gate2"
            reason_codes.update(["accepted_source_candidate", "document_metadata_passport_validated"])
            review_action = "enter_gate2_source_fact_extraction_as_candidate_with_issue_context"
        reason_codes.update(["source_policy_uncertainty_carried_forward", "document_metadata_passport_source_role_supported"])
        can_enter_gate2 = True
        included = True
        specialist_decision = False
    elif passport_valid and passport_has_source_role:
        if taxonomy_class in SOURCE_DOCUMENT_CLASSES or source_role_policy_status == "approved":
            source_eligibility = "accepted_for_gate2"
            reason_codes.update(["accepted_source_document", "document_metadata_passport_validated"])
            review_action = "enter_gate2_source_fact_extraction"
        else:
            source_eligibility = "accepted_as_source_candidate_for_gate2"
            reason_codes.update(["accepted_source_candidate", "document_metadata_passport_validated"])
            review_action = "enter_gate2_source_fact_extraction_as_candidate"
        if source_role_policy_status == "context_issue":
            reason_codes.update([
                "source_policy_uncertainty_carried_forward",
                "document_metadata_passport_source_role_supported",
            ])
            review_action = f"{review_action}_with_issue_context"
        can_enter_gate2 = True
        included = True
        specialist_decision = False
    elif taxonomy_class in METHODOLOGY_OR_OUTPUT_CLASSES:
        source_eligibility = "methodology_or_output_artifact"
        reason_codes.update(["methodology_or_output_artifact", taxonomy_class])
        review_action = "keep_out_of_gate2_source_subset"
        terminal = True
        specialist_decision = False
    elif taxonomy_class == "archive_package":
        source_eligibility = "metadata_review_required"
        reason_codes.update(["archive_package_requires_review"])
        review_action = "specialist_review_archive_members"
    elif source_policy_review_required or source_role_policy_status == "review_required":
        if (
            passport_valid
            and passport_has_source_role
            and passport_source_confidence in {"medium", "high"}
            and passport_metadata_confidence in {"medium", "high"}
            and source_role_policy_status == "approved"
        ):
            source_eligibility = "accepted_for_gate2"
            reason_codes.update(["accepted_source_document", "document_metadata_passport_validated"])
            review_action = "enter_gate2_source_fact_extraction"
            can_enter_gate2 = True
            included = True
            specialist_decision = False
        elif passport_valid and passport_has_source_role and passport_source_confidence in {"medium", "high"}:
            source_eligibility = (
                "accepted_for_gate2"
                if taxonomy_class in SOURCE_DOCUMENT_CLASSES
                else "accepted_as_source_candidate_for_gate2"
            )
            reason_codes.update([
                "source_policy_uncertainty_carried_forward",
                "document_metadata_passport_source_role_supported",
            ])
            review_action = "enter_gate2_source_fact_extraction_with_issue_context"
            can_enter_gate2 = True
            included = True
            specialist_decision = False
        elif passport_valid and passport_missing_required:
            source_eligibility = "metadata_review_required"
            reason_codes.update(["document_metadata_passport_incomplete"])
            review_action = "specialist_review_document_metadata_passport"
        elif taxonomy_class in SOURCE_DOCUMENT_CLASSES and not (blocker_codes & TERMINAL_GATE2_BLOCKER_CODES):
            source_eligibility = "accepted_for_gate2"
            reason_codes.update([taxonomy_class, "source_policy_uncertainty_carried_forward"])
            review_action = "enter_gate2_source_fact_extraction_with_issue_context"
            can_enter_gate2 = True
            included = True
            specialist_decision = False
        else:
            source_eligibility = "metadata_review_required"
            reason_codes.update(["metadata_review_required", "source_policy_uncertainty_carried_forward"])
            review_action = "specialist_review_document_metadata_passport"
    elif taxonomy_class == "unknown_or_needs_review":
        if passport_valid and passport_has_source_role and passport_missing_required:
            source_eligibility = "metadata_review_required"
            reason_codes.update(["document_metadata_passport_incomplete"])
            review_action = "specialist_review_document_metadata_passport"
        elif (
            passport_valid
            and passport_has_source_role
            and passport_source_confidence in {"medium", "high"}
            and passport_metadata_confidence in {"medium", "high"}
        ):
            source_eligibility = "accepted_for_gate2"
            reason_codes.update(["accepted_source_document", "document_metadata_passport_validated"])
            review_action = "enter_gate2_source_fact_extraction"
            can_enter_gate2 = True
            included = True
            specialist_decision = False
        else:
            source_eligibility = "metadata_review_required"
            reason_codes.update(["unknown_role_requires_metadata_review"])
            review_action = "specialist_classify_document_role"
    elif taxonomy_class in SOURCE_DOCUMENT_CLASSES and not (blocker_codes & TERMINAL_GATE2_BLOCKER_CODES):
        source_eligibility = "accepted_for_gate2"
        reason_codes.update(["accepted_source_document", taxonomy_class])
        review_action = "enter_gate2_source_fact_extraction"
        can_enter_gate2 = True
        included = True
        specialist_decision = False
    else:
        source_eligibility = "metadata_review_required"
        reason_codes.update(["metadata_review_required", taxonomy_class])

    can_proceed_with_metadata_warning = bool(
        criticality_refinement_enabled
        and not unresolved_critical_fields
        and (unresolved_clarifying_fields or unresolved_non_critical_fields)
    )
    if criticality_refinement_enabled:
        if duplicate_auto_resolution.get("auto_resolved") is True and duplicate_auto_resolution.get("is_canonical") is True:
            reason_codes.update(["exact_duplicate_auto_canonical_selected", "exact_duplicate_latest_wins"])
        if unresolved_critical_fields:
            reason_codes.add("critical_metadata_gap_blocks_gate2")
        if can_proceed_with_metadata_warning:
            reason_codes.add("metadata_clarification_warning_present")
            if unresolved_clarifying_fields:
                reason_codes.add("metadata_clarifying_fields_unresolved")
            if unresolved_non_critical_fields:
                reason_codes.add("metadata_non_critical_fields_deferred")
            if can_enter_gate2:
                reason_codes.add("nonblocking_metadata_gaps_allowed_with_warning")

    if source_eligibility not in SOURCE_ELIGIBILITY_STATUSES:
        source_eligibility = "metadata_review_required"
        reason_codes.add("eligibility_fallback_metadata_review_required")
        can_enter_gate2 = False
        included = False
        specialist_decision = True

    return {
        "schema_version": "document_source_eligibility_v0",
        "decision_version": "passport_based_source_eligibility_v2",
        "document_id": document_id,
        "normalization_run_id": run_id,
        "source_eligibility": source_eligibility,
        "can_enter_gate2": bool(can_enter_gate2),
        "reason_codes": sorted(code for code in reason_codes if code),
        "blocker_refs": blocker_refs,
        "review_action": review_action,
        "ocr_policy_status": doc_ocr_policy_status,
        "source_role_policy_status": source_role_policy_status,
        "source_policy_review_required": bool(source_policy_review_required),
        "document_metadata_passport_status": passport_status,
        "document_metadata_passport_confidence": {
            "source_candidate_confidence": passport_source_confidence,
            "source_role_confidence": passport_source_role_confidence,
            "metadata_confidence": passport_metadata_confidence,
        },
        "document_metadata_passport_basis": {
            "passport_validated": bool(passport_valid),
            "source_role_hypotheses": len(passport_role_summary["source_roles"]),
            "source_policy_effects": sorted(passport_source_policy_effects),
            "missing_metadata_fields_count": len(passport_missing_fields),
            "conflict_flags_count": len(passport_conflict_flags),
            "evidence_refs_count": len(passport_evidence_refs),
        },
        "duplicate_auto_resolution": dict(duplicate_auto_resolution) if duplicate_auto_resolution else {},
        "clarification_criticality_basis": {
            "criticality_refinement_enabled": bool(criticality_refinement_enabled),
            "unresolved_critical_fields": sorted(unresolved_critical_fields),
            "unresolved_clarifying_fields": sorted(unresolved_clarifying_fields),
            "unresolved_non_critical_fields": sorted(unresolved_non_critical_fields),
            "unresolved_critical_count": len(unresolved_critical_fields),
            "unresolved_clarifying_count": len(unresolved_clarifying_fields),
            "unresolved_non_critical_count": len(unresolved_non_critical_fields),
            "can_proceed_with_warning": bool(can_proceed_with_metadata_warning and can_enter_gate2),
            "source_evidence_available": bool(source_evidence_available),
            "period_scope_basis": dict(period_scope_basis) if period_scope_basis.get("period_fields_missing") else {},
        },
        "clarification_resolution_basis": {
            "usable_resolution_count": len(resolved_question_ids),
            "resolved_fields": sorted(resolved_fields),
            "question_ids": sorted(resolved_question_ids),
            "duplicate_canonical_resolved": bool(canonical_for_group),
            "marked_not_source": bool(mark_not_source),
            "marked_outside_scope": bool(mark_outside_scope),
        },
        "included_in_reduced_subset": bool(included),
        "exclusion_is_terminal": bool(terminal),
        "requires_specialist_decision": bool(specialist_decision),
    }


def _handoff_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    criticality_refinement_enabled = any(
        (entry.get("clarification_criticality_basis") or {}).get("criticality_refinement_enabled") is True
        for entry in entries
    )
    included = [entry["document_id"] for entry in entries if entry.get("included_in_reduced_subset")]
    accepted_candidates = [
        entry["document_id"]
        for entry in entries
        if entry.get("source_eligibility") == "accepted_as_source_candidate_for_gate2"
    ]
    excluded = [
        entry["document_id"]
        for entry in entries
        if entry.get("source_eligibility") in EXCLUDED_ELIGIBILITIES
    ]
    pending_review = [
        entry["document_id"]
        for entry in entries
        if entry.get("source_eligibility") in REVIEW_ELIGIBILITIES
    ]
    ocr_required = [
        entry["document_id"]
        for entry in entries
        if entry.get("source_eligibility") == "requires_ocr_before_gate2"
    ]
    duplicate_review = [
        entry["document_id"]
        for entry in entries
        if entry.get("source_eligibility") == "duplicate_needs_canonical_choice"
    ]
    source_policy_review = [
        entry["document_id"]
        for entry in entries
        if entry.get("source_eligibility") == "source_policy_review_required"
    ]
    metadata_review = [
        entry["document_id"]
        for entry in entries
        if entry.get("source_eligibility") == "metadata_review_required"
    ]
    critical_metadata_review = [
        entry["document_id"]
        for entry in entries
        if entry.get("source_eligibility") == "metadata_review_required"
        and (entry.get("clarification_criticality_basis") or {}).get("unresolved_critical_count", 0)
    ]
    advisory_metadata_review = sorted(set(metadata_review) - set(critical_metadata_review))
    warning_document_ids = [
        entry["document_id"]
        for entry in entries
        if (entry.get("clarification_criticality_basis") or {}).get("can_proceed_with_warning") is True
    ]
    warning_counts = {
        "clarifying": sum(
            int((entry.get("clarification_criticality_basis") or {}).get("unresolved_clarifying_count") or 0)
            for entry in entries
        ),
        "non_critical": sum(
            int((entry.get("clarification_criticality_basis") or {}).get("unresolved_non_critical_count") or 0)
            for entry in entries
        ),
    }
    auto_duplicate_groups = _auto_duplicate_groups(entries)
    auto_duplicate_noncanonical = sorted(
        entry["document_id"]
        for entry in entries
        if (entry.get("duplicate_auto_resolution") or {}).get("auto_resolved") is True
        and (entry.get("duplicate_auto_resolution") or {}).get("is_canonical") is not True
    )
    reduced_subset_validated = bool(included) and all(
        entry.get("can_enter_gate2") is True and entry.get("exclusion_is_terminal") is False
        for entry in entries
        if entry.get("included_in_reduced_subset")
    )

    if criticality_refinement_enabled:
        if ocr_required:
            handoff_mode = "gate2_blocked_requires_ocr"
            gate2_handoff_status = "blocked"
        elif critical_metadata_review:
            handoff_mode = "gate2_blocked_requires_metadata_review"
            gate2_handoff_status = "blocked"
        elif included and len(included) == len(entries):
            handoff_mode = "full_package_ready_for_gate2"
            gate2_handoff_status = "ready_with_safe_refs"
        elif included and reduced_subset_validated:
            handoff_mode = "reduced_subset_ready_for_gate2"
            gate2_handoff_status = "ready_with_reduced_subset"
        elif duplicate_review:
            handoff_mode = "gate2_blocked_requires_duplicate_resolution"
            gate2_handoff_status = "blocked"
        elif source_policy_review:
            handoff_mode = "gate2_blocked_no_eligible_sources"
            gate2_handoff_status = "blocked"
        else:
            handoff_mode = "gate2_blocked_no_eligible_sources"
            gate2_handoff_status = "blocked"
    elif included and len(included) == len(entries):
        handoff_mode = "full_package_ready_for_gate2"
        gate2_handoff_status = "ready_with_safe_refs"
    elif included and reduced_subset_validated:
        handoff_mode = "reduced_subset_ready_for_gate2"
        gate2_handoff_status = "ready_with_reduced_subset"
    elif ocr_required:
        handoff_mode = "gate2_blocked_requires_ocr"
        gate2_handoff_status = "blocked"
    elif metadata_review:
        handoff_mode = "gate2_blocked_requires_metadata_review"
        gate2_handoff_status = "blocked"
    elif source_policy_review:
        handoff_mode = "gate2_blocked_requires_policy_review"
        gate2_handoff_status = "blocked"
    elif duplicate_review:
        handoff_mode = "gate2_blocked_requires_duplicate_resolution"
        gate2_handoff_status = "blocked"
    else:
        handoff_mode = "gate2_blocked_no_eligible_sources"
        gate2_handoff_status = "blocked"

    decision_counts = Counter(str(entry.get("source_eligibility") or "unknown") for entry in entries)
    reason_codes = sorted(
        {
            str(code)
            for entry in entries
            for code in entry.get("reason_codes", [])
            if code
        }
    )
    return {
        "schema_version": "gate2_handoff_decision_v0",
        "decision_version": "passport_based_source_eligibility_v2",
        "criticality_refinement_enabled": bool(criticality_refinement_enabled),
        "handoff_mode": handoff_mode,
        "gate2_handoff_status": gate2_handoff_status,
        "reduced_subset_validated": reduced_subset_validated,
        "included_document_ids": included,
        "accepted_source_candidate_document_ids": accepted_candidates,
        "excluded_document_ids": excluded,
        "pending_review_document_ids": pending_review,
        "source_policy_review_document_ids": source_policy_review,
        "metadata_review_document_ids": metadata_review,
        "critical_metadata_review_document_ids": critical_metadata_review,
        "advisory_metadata_review_document_ids": advisory_metadata_review,
        "ocr_required_document_ids": ocr_required,
        "duplicate_review_document_ids": duplicate_review,
        "auto_resolved_duplicate_document_ids": auto_duplicate_noncanonical,
        "auto_canonical_duplicate_groups": auto_duplicate_groups,
        "warning_document_ids": warning_document_ids,
        "can_proceed_with_warnings": bool(warning_document_ids and gate2_handoff_status != "blocked"),
        "warning_counts": warning_counts,
        "decision_status_counts": dict(sorted(decision_counts.items())),
        "handoff_blocker_counts": {
            "metadata_review_required": len(metadata_review),
            "critical_metadata_review_required": len(critical_metadata_review),
            "advisory_metadata_review_required": len(advisory_metadata_review),
            "source_policy_review_required": len(source_policy_review),
            "duplicate_needs_canonical_choice": len(duplicate_review),
            "auto_resolved_exact_duplicate_groups": len(auto_duplicate_groups),
            "auto_resolved_exact_duplicate_documents": len(auto_duplicate_noncanonical),
            "requires_ocr_before_gate2": len(ocr_required),
            "excluded_from_gate2": len(excluded),
        },
        "reason_codes": reason_codes,
    }


def _summary(entries: list[dict[str, Any]], handoff: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(str(entry.get("source_eligibility") or "unknown") for entry in entries)
    pending_review_total = sum(counts.get(status, 0) for status in REVIEW_ELIGIBILITIES)
    excluded_total = sum(counts.get(status, 0) for status in EXCLUDED_ELIGIBILITIES)
    passport_based_count = sum(
        1
        for entry in entries
        if (entry.get("document_metadata_passport_basis") or {}).get("passport_validated") is True
    )
    warning_counts = dict(handoff.get("warning_counts") or {})
    return {
        "schema_version": "document_source_eligibility_summary_v0",
        "decision_version": "passport_based_source_eligibility_v2",
        "documents_total": len(entries),
        "status_counts": dict(sorted(counts.items())),
        "accepted_for_gate2": counts.get("accepted_for_gate2", 0),
        "accepted_as_source_candidate_for_gate2": counts.get("accepted_as_source_candidate_for_gate2", 0),
        "excluded_from_gate2": excluded_total,
        "ocr_required_before_gate2": counts.get("requires_ocr_before_gate2", 0),
        "pending_review": pending_review_total,
        "source_policy_review": counts.get("source_policy_review_required", 0),
        "source_policy_review_required": counts.get("source_policy_review_required", 0),
        "metadata_review": counts.get("metadata_review_required", 0),
        "metadata_review_required": counts.get("metadata_review_required", 0),
        "duplicate_review": counts.get("duplicate_needs_canonical_choice", 0),
        "duplicate_needs_canonical_choice": counts.get("duplicate_needs_canonical_choice", 0),
        "auto_resolved_exact_duplicate_groups": len(handoff.get("auto_canonical_duplicate_groups") or []),
        "auto_resolved_exact_duplicate_documents": len(handoff.get("auto_resolved_duplicate_document_ids") or []),
        "methodology_or_output_artifact": counts.get("methodology_or_output_artifact", 0),
        "outside_case_scope": counts.get("outside_case_scope", 0),
        "unsupported_format": counts.get("unsupported_format", 0),
        "included_in_reduced_subset": len(handoff.get("included_document_ids", [])),
        "terminal_exclusions": sum(1 for entry in entries if entry.get("exclusion_is_terminal")),
        "requires_specialist_decision": sum(1 for entry in entries if entry.get("requires_specialist_decision")),
        "passport_based_decision_count": passport_based_count,
        "passport_validated_count": passport_based_count,
        "handoff_mode": handoff.get("handoff_mode"),
        "gate2_handoff_status": handoff.get("gate2_handoff_status"),
        "reduced_subset_validated": handoff.get("reduced_subset_validated") is True,
        "handoff_blocker_counts": dict(handoff.get("handoff_blocker_counts") or {}),
        "criticality_refinement_enabled": handoff.get("criticality_refinement_enabled") is True,
        "warning_counts": warning_counts,
        "warning_documents_total": len(handoff.get("warning_document_ids") or []),
        "critical_metadata_review_required": (handoff.get("handoff_blocker_counts") or {}).get("critical_metadata_review_required", 0),
        "can_proceed_with_warnings": handoff.get("can_proceed_with_warnings") is True,
    }


def _exact_duplicate_resolution_state(
    *,
    documents: list[dict[str, Any]],
    taxonomy_by_doc: dict[str, dict[str, Any]],
    passport_by_doc: dict[str, dict[str, Any]],
    refinement_enabled: bool,
) -> dict[str, dict[str, Any]]:
    if not refinement_enabled:
        return {}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        sha256 = str(document.get("sha256") or "")
        if sha256:
            groups[sha256].append(document)

    state: dict[str, dict[str, Any]] = {}
    for sha256, group_documents in groups.items():
        if len(group_documents) < 2:
            continue
        document_ids = [str(document.get("document_id") or "") for document in group_documents]
        if not all(document_ids):
            continue
        passports = [passport_by_doc.get(document_id) or {} for document_id in document_ids]
        if not all(_passport_valid_for_duplicate_basis(passport) for passport in passports):
            continue
        passport_keys = {_passport_duplicate_equivalence_key(passport) for passport in passports}
        taxonomy_keys = {
            _taxonomy_duplicate_equivalence_key(taxonomy_by_doc.get(document_id) or {})
            for document_id in document_ids
        }
        if len(passport_keys) != 1 or len(taxonomy_keys) != 1:
            continue

        canonical = _select_exact_duplicate_canonical(group_documents, passport_by_doc)
        canonical_document_id = str(canonical.get("document_id") or "")
        if not canonical_document_id:
            continue
        duplicate_group_id = _duplicate_group_id_for_exact_group(sha256, group_documents)
        passport_basis_hash = stable_digest(sorted(passport_keys), length=16)
        taxonomy_basis_hash = stable_digest(sorted(taxonomy_keys), length=16)
        selection_basis = _canonical_selection_basis(group_documents, passport_by_doc)
        excluded_ids = sorted(document_id for document_id in document_ids if document_id != canonical_document_id)
        for document_id in document_ids:
            is_canonical = document_id == canonical_document_id
            state[document_id] = {
                "auto_resolved": True,
                "auto_resolution_policy": "exact_duplicate_latest_wins",
                "duplicate_kind": "exact_duplicate",
                "duplicate_group_id": duplicate_group_id,
                "canonical_document_id": canonical_document_id,
                "is_canonical": is_canonical,
                "excluded_document_ids": excluded_ids,
                "reason_codes": [
                    "exact_duplicate_auto_canonicalized",
                    "exact_duplicate_latest_wins",
                    "document_hash_identical",
                    "passport_basis_equivalent",
                    "source_role_status_equivalent",
                ],
                "canonical_selection_basis": selection_basis,
                "passport_basis_hash": passport_basis_hash,
                "source_role_status_basis_hash": taxonomy_basis_hash,
            }
    return state


def _passport_valid_for_duplicate_basis(passport: dict[str, Any]) -> bool:
    return (
        str(passport.get("validator_status") or "") == "passed"
        and str(passport.get("passport_status") or "") == "validated"
    )


def _passport_duplicate_equivalence_key(passport: dict[str, Any]) -> str:
    roles = []
    for item in passport.get("role_hypotheses") or []:
        if not isinstance(item, dict):
            continue
        roles.append(
            (
                str(item.get("role") or ""),
                str(item.get("confidence") or ""),
                str(item.get("source_policy_effect") or ""),
            )
        )
    key = {
        "content_kind": str(passport.get("content_kind") or ""),
        "source_candidate_confidence": str(passport.get("source_candidate_confidence") or ""),
        "metadata_confidence": str(passport.get("metadata_confidence") or ""),
        "report_period_start_set": bool(passport.get("report_period_start")),
        "report_period_end_set": bool(passport.get("report_period_end")),
        "tax_year_candidate_set": bool(passport.get("tax_year_candidate")),
        "missing_metadata_fields": sorted(str(item) for item in passport.get("missing_metadata_fields") or [] if item),
        "conflict_flags": sorted(str(item) for item in passport.get("conflict_flags") or [] if item),
        "review_required": passport.get("review_required") is True,
        "roles": sorted(roles),
    }
    return stable_digest([key], length=24)


def _taxonomy_duplicate_equivalence_key(candidate: dict[str, Any]) -> str:
    key = {
        "document_class_candidate": str(candidate.get("document_class_candidate") or ""),
        "source_role_policy_status": str(candidate.get("source_role_policy_status") or ""),
        "source_policy_review_required": candidate.get("source_policy_review_required") is True,
    }
    return stable_digest([key], length=24)


def _select_exact_duplicate_canonical(
    documents: list[dict[str, Any]],
    passport_by_doc: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return max(
        documents,
        key=lambda document: (
            _document_report_created_at(document, passport_by_doc),
            _document_upload_or_ingest_timestamp(document),
            str(document.get("document_id") or ""),
        ),
    )


def _document_report_created_at(document: dict[str, Any], passport_by_doc: dict[str, dict[str, Any]]) -> str:
    document_id = str(document.get("document_id") or "")
    passport = passport_by_doc.get(document_id) or {}
    return str(
        passport.get("created_at_candidate")
        or document.get("report_created_at")
        or document.get("document_created_at")
        or ""
    )


def _document_upload_or_ingest_timestamp(document: dict[str, Any]) -> str:
    return str(
        document.get("uploaded_at")
        or document.get("ingested_at")
        or document.get("created_at")
        or ""
    )


def _canonical_selection_basis(
    documents: list[dict[str, Any]],
    passport_by_doc: dict[str, dict[str, Any]],
) -> str:
    if any(_document_report_created_at(document, passport_by_doc) for document in documents):
        return "report_created_at_then_upload_then_safe_document_id"
    if any(_document_upload_or_ingest_timestamp(document) for document in documents):
        return "upload_or_ingest_timestamp_then_safe_document_id"
    return "stable_safe_document_id"


def _duplicate_group_id_for_exact_group(sha256: str, documents: list[dict[str, Any]]) -> str:
    for document in documents:
        group_id = str(document.get("duplicate_group_id") or "")
        if group_id:
            return group_id
    return f"dupgrp_{sha256[:12]}"


def _case_scope_basis(input_context: dict[str, Any]) -> dict[str, Any]:
    broker_context = input_context.get("broker_reports_gate1") if isinstance(input_context.get("broker_reports_gate1"), dict) else {}
    source_policy = input_context.get("source_policy") if isinstance(input_context.get("source_policy"), dict) else {}
    tax_year = (
        input_context.get("case_tax_year")
        or input_context.get("tax_year")
        or input_context.get("tax_period_year")
        or broker_context.get("case_tax_year")
        or broker_context.get("tax_year")
        or broker_context.get("tax_period_year")
    )
    case_group_id = (
        input_context.get("case_group_id")
        or broker_context.get("case_group_id")
        or input_context.get("case_id")
        or broker_context.get("case_id")
    )
    broker_provider = (
        input_context.get("broker_provider_candidate")
        or broker_context.get("broker_provider_candidate")
        or source_policy.get("broker_provider_candidate")
    )
    hints = source_policy.get("safe_registry_role_hints") if isinstance(source_policy, dict) else None
    return {
        "case_tax_year_known": bool(tax_year),
        "case_scope_known": bool(case_group_id),
        "broker_provider_known": bool(broker_provider or hints),
        "declaration_or_output_period_only": bool(
            input_context.get("declaration_output_period_only")
            or broker_context.get("declaration_output_period_only")
        ),
    }


def _period_scope_basis(
    *,
    document: dict[str, Any],
    taxonomy_candidate: dict[str, Any],
    metadata_passport: dict[str, Any],
    case_scope_basis: dict[str, Any],
    passport_has_source_role: bool,
    passport_evidence_refs: list[str],
    period_fields_missing: bool,
) -> dict[str, Any]:
    source_role_evidence_available = bool(passport_has_source_role and passport_evidence_refs)
    taxonomy_class = str(taxonomy_candidate.get("document_class_candidate") or "")
    roles = {
        str(item.get("role") or "")
        for item in metadata_passport.get("role_hypotheses") or []
        if isinstance(item, dict)
    }
    operation_date_evidence_available = bool(
        taxonomy_class == "operations_table"
        or "source_operations_table" in roles
        or document.get("machine_readable_table") is True
    )
    basis = {
        "period_fields_missing": bool(period_fields_missing),
        "case_tax_year_known": case_scope_basis.get("case_tax_year_known") is True,
        "case_scope_known": case_scope_basis.get("case_scope_known") is True,
        "broker_provider_known": case_scope_basis.get("broker_provider_known") is True,
        "source_role_evidence_available": source_role_evidence_available,
        "operation_date_evidence_available": operation_date_evidence_available,
        "declaration_or_output_period_only": case_scope_basis.get("declaration_or_output_period_only") is True,
    }
    reason_codes: set[str] = set()
    if basis["case_tax_year_known"]:
        reason_codes.add("case_tax_year_provides_scope")
    if basis["case_scope_known"]:
        reason_codes.add("case_context_provides_scope")
    if basis["broker_provider_known"]:
        reason_codes.add("broker_provider_provides_scope")
    if basis["operation_date_evidence_available"]:
        reason_codes.update(["period_deferred_to_gate2_operation_dates", "source_table_dates_available"])
    if basis["declaration_or_output_period_only"]:
        reason_codes.add("period_deferred_to_declaration_context")
    if period_fields_missing and reason_codes:
        reason_codes.add("document_period_missing_but_not_blocking")
    elif period_fields_missing:
        reason_codes.add("period_required_for_gate2_scope")
    basis["reason_codes"] = sorted(reason_codes)
    return basis


def _auto_duplicate_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for entry in entries:
        resolution = entry.get("duplicate_auto_resolution") or {}
        if resolution.get("auto_resolved") is not True:
            continue
        group_id = str(resolution.get("duplicate_group_id") or "")
        if not group_id or group_id in groups:
            continue
        groups[group_id] = {
            "duplicate_group_id": group_id,
            "canonical_document_id": resolution.get("canonical_document_id"),
            "excluded_document_ids": list(resolution.get("excluded_document_ids") or []),
            "auto_resolution_policy": resolution.get("auto_resolution_policy"),
            "canonical_selection_basis": resolution.get("canonical_selection_basis"),
            "reason_codes": list(resolution.get("reason_codes") or []),
        }
    return [groups[key] for key in sorted(groups)]


def _clarification_resolution_state(
    resolutions: list[dict[str, Any]],
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    by_doc: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "resolved_fields": set(),
            "question_ids": set(),
        }
    )
    doc_to_group = {
        str(document.get("document_id")): str(document.get("duplicate_group_id") or "")
        for document in documents
        if document.get("document_id")
    }
    canonical_by_group: dict[str, str] = {}
    for resolution in resolutions:
        if not isinstance(resolution, dict):
            continue
        if resolution.get("usable_by_source_eligibility_v2") is not True:
            continue
        if resolution.get("validation_status") != "passed":
            continue
        question_id = str(resolution.get("question_id") or "")
        resolved_field = str(resolution.get("resolved_field") or "")
        answer_value = resolution.get("answer_value")
        target_refs = [str(item) for item in resolution.get("target_document_refs") or [] if item]
        if not target_refs and resolution.get("target_document_ref"):
            target_refs = [str(resolution["target_document_ref"])]
        if resolved_field == "canonical_document_ref":
            canonical_ref = str(answer_value or "")
            for document_ref in target_refs:
                group_id = doc_to_group.get(document_ref)
                if group_id and canonical_ref:
                    canonical_by_group[group_id] = canonical_ref
            continue
        for document_ref in target_refs:
            state = by_doc[document_ref]
            if resolved_field:
                state["resolved_fields"].add(resolved_field)
            if question_id:
                state["question_ids"].add(question_id)
            answer_type = str(resolution.get("answer_type") or "")
            if resolved_field == "document_role" and isinstance(answer_value, str):
                value = answer_value.strip()
                if value == "mark_as_not_source":
                    state["mark_as_not_source"] = True
                elif value == "mark_as_outside_scope":
                    state["mark_as_outside_scope"] = True
                elif value:
                    state["document_role"] = value
            if answer_type == "mark_as_not_source" and answer_value is True:
                state["mark_as_not_source"] = True
            if answer_type == "mark_as_outside_scope" and answer_value is True:
                state["mark_as_outside_scope"] = True
    return {"by_doc": by_doc, "canonical_by_group": canonical_by_group}


def _passport_role_summary(metadata_passport: dict[str, Any]) -> dict[str, Any]:
    roles: set[str] = set()
    source_roles: set[str] = set()
    source_policy_effects: set[str] = set()
    best_source_confidence = "none"
    for item in metadata_passport.get("role_hypotheses") or []:
        if not isinstance(item, dict) or not item.get("role"):
            continue
        role = str(item["role"])
        roles.add(role)
        if item.get("source_policy_effect"):
            source_policy_effects.add(str(item["source_policy_effect"]))
        if role in {
            "source_broker_report",
            "source_operations_table",
            "source_dividend_report",
            "source_withholding_report",
            "source_cashflow_report",
        }:
            source_roles.add(role)
            best_source_confidence = _max_confidence(best_source_confidence, str(item.get("confidence") or "none"))
    return {
        "roles": roles,
        "source_roles": source_roles,
        "source_role_confidence": best_source_confidence,
        "source_policy_effects": source_policy_effects,
    }


def _max_confidence(left: str, right: str) -> str:
    rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
    return right if rank.get(right, 0) > rank.get(left, 0) else left
