from __future__ import annotations

import copy
from collections import Counter, defaultdict
from typing import Any

from .contracts import METHODOLOGY_OR_OUTPUT_CLASSES, SOURCE_DOCUMENT_CLASSES, stable_digest
from .document_memory import (
    DOCUMENT_MEMORY_SCHEMA_VERSION,
    SUPPORTED_PROFILE_ASSESSMENT_SCHEMA_VERSION,
    SUPPORTED_PROFILE_SCHEMA_VERSION,
    Gate1DocumentMemoryFactory,
    supported_pilot_profile_v1,
)


ISSUE_LEDGER_SCHEMA_VERSION = "gate1_issue_ledger_v0"
DOCUMENT_USAGE_CLASSIFICATION_SCHEMA_VERSION = "document_usage_classification_v0"
DOMAIN_CONTEXT_PACKET_SCHEMA_VERSION = "domain_context_packet_v0"

DOMAIN_INGESTION_CONTRACTS = [
    SUPPORTED_PROFILE_SCHEMA_VERSION,
    SUPPORTED_PROFILE_ASSESSMENT_SCHEMA_VERSION,
    DOCUMENT_MEMORY_SCHEMA_VERSION,
    ISSUE_LEDGER_SCHEMA_VERSION,
    DOCUMENT_USAGE_CLASSIFICATION_SCHEMA_VERSION,
    DOMAIN_CONTEXT_PACKET_SCHEMA_VERSION,
]

READABILITY_BLOCKERS = {
    "bytes_unavailable",
    "unsupported_format",
    "encrypted_file",
    "corrupt_file",
    "parser_failed",
    "raster_requires_ocr_or_review",
}
CONSOLIDATION_ISSUES = {
    "duplicate_canonical_choice",
    "unclear_document_role",
    "metadata_gap",
    "source_role_policy_uncertainty",
    "outside_scope_confirmation",
    "structural_uncertainty",
}
STAGES = [
    "domain_ingestion",
    "source_fact_extraction",
    "cross_check",
    "consolidation",
    "declaration_support",
]


def apply_domain_ingestion_artifacts(
    package: dict[str, Any], *, copy_package: bool = True
) -> dict[str, Any]:
    """Attach domain artifacts, optionally reusing an exclusively owned graph."""

    updated = copy.deepcopy(package) if copy_package else package
    document_memory_builder = Gate1DocumentMemoryFactory().create()
    supported_profile = supported_pilot_profile_v1()
    supported_profile_assessment = document_memory_builder.assess_supported_profile(
        updated
    )
    updated["gate1_supported_profile"] = supported_profile
    updated["gate1_supported_profile_assessment"] = supported_profile_assessment
    issue_ledger = build_gate1_issue_ledger(updated)
    document_memory_manifest = document_memory_builder.build_manifest(
        updated, supported_profile_assessment, issue_ledger
    )
    usage_classification = build_document_usage_classification(
        updated,
        issue_ledger,
        document_memory_manifest=document_memory_manifest,
    )
    updated["document_memory_manifest"] = document_memory_manifest
    domain_context_packet = build_domain_context_packet(
        updated,
        issue_ledger,
        usage_classification,
        document_memory_manifest=document_memory_manifest,
    )
    summary = _domain_ingestion_summary(issue_ledger, usage_classification, domain_context_packet)

    updated["gate1_issue_ledger"] = issue_ledger
    updated["document_usage_classification"] = usage_classification
    updated["domain_context_packet"] = domain_context_packet
    updated["domain_ingestion_summary"] = summary
    updated.setdefault("summary_counts", {})["domain_ingestion_counts"] = dict(summary.get("counts") or {})
    updated["supported_contracts"] = list(
        dict.fromkeys([*updated.get("supported_contracts", []), *DOMAIN_INGESTION_CONTRACTS])
    )

    run = updated.setdefault("normalization_run", {})
    run["domain_ingestion_status"] = summary["domain_ingestion_status"]
    run["issue_ledger_status"] = summary["issue_ledger_status"]
    run["domain_context_packet_status"] = "ready"
    run["document_memory_status"] = (
        document_memory_manifest.get("summary", {}).get("zero_silent_loss_status")
    )
    run["source_fact_extraction_readiness"] = domain_context_packet["stage_readiness"]["source_fact_extraction"]
    run["consolidation_readiness"] = domain_context_packet["stage_readiness"]["consolidation"]
    run["declaration_support_readiness"] = domain_context_packet["stage_readiness"]["declaration_support"]
    return updated


def build_gate1_issue_ledger(package: dict[str, Any]) -> dict[str, Any]:
    run_id = _run_id(package)
    documents = _documents(package)
    doc_ids = [str(document.get("document_id")) for document in documents if document.get("document_id")]
    issues: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()

    gap_report = _gap_report(package)
    gaps = gap_report.get("gaps") if isinstance(gap_report.get("gaps"), list) else []
    gap_source_refs = {str(gap.get("gap_id") or "") for gap in gaps if isinstance(gap, dict)}
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        issue = _issue_from_gap(run_id, gap, package)
        _append_issue(issues, seen, issue)
    for question in _clarification_questions(package):
        gap_id = str(question.get("gap_id") or "")
        if gap_id and gap_id in gap_source_refs:
            continue
        _append_issue(issues, seen, _issue_from_clarification_question(run_id, question, package))

    blockers_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    run_blockers: list[dict[str, Any]] = []
    for blocker in package.get("normalization_blockers", []):
        if not isinstance(blocker, dict):
            continue
        document_id = str(blocker.get("document_id") or "")
        if document_id:
            blockers_by_doc[document_id].append(blocker)
        else:
            run_blockers.append(blocker)

    for blocker in run_blockers:
        _append_issue(issues, seen, _issue_from_blocker(run_id, blocker, []))
    for document_id in doc_ids:
        for blocker in blockers_by_doc.get(document_id, []):
            _append_issue(issues, seen, _issue_from_blocker(run_id, blocker, [document_id]))

    eligibility_by_doc = {
        str(item.get("document_id") or ""): item
        for item in _eligibility_entries(package)
        if item.get("document_id")
    }
    profile_assessment = _object(package.get("gate1_supported_profile_assessment"))
    profile_issue_entries = (
        profile_assessment.get("entries") or []
        if "full_source_coverage_summary" in package
        and _supported_profile_enforced(package)
        else []
    )
    for assessment in profile_issue_entries:
        if not isinstance(assessment, dict):
            continue
        document_id = str(assessment.get("document_ref") or "")
        if not _profile_assessment_requires_issue(
            assessment, eligibility_by_doc.get(document_id, {})
        ):
            continue
        _append_issue(
            issues,
            seen,
            _issue_from_profile_assessment(run_id, assessment),
        )

    for entry in _eligibility_entries(package):
        if not isinstance(entry, dict):
            continue
        for issue in _issues_from_eligibility(run_id, entry, package):
            _append_issue(issues, seen, issue)

    issues = sorted(issues, key=lambda item: item["issue_id"])
    summary = _issue_summary(issues)
    return {
        "schema_version": ISSUE_LEDGER_SCHEMA_VERSION,
        "issue_ledger_id": f"issueledger_{stable_digest([run_id, len(issues), summary['unresolved_issues_total']], length=16)}",
        "normalization_run_id": run_id,
        "ledger_status": "open" if summary["unresolved_issues_total"] else "closed",
        "entries": issues,
        "summary": summary,
    }


def build_document_usage_classification(
    package: dict[str, Any],
    issue_ledger: dict[str, Any],
    *,
    document_memory_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = _run_id(package)
    issues_by_doc = _issues_by_doc(issue_ledger)
    taxonomy_by_doc = {
        str(item.get("document_id")): item
        for item in package.get("taxonomy_candidates", [])
        if isinstance(item, dict) and item.get("document_id")
    }
    eligibility_by_doc = {
        str(item.get("document_id")): item
        for item in _eligibility_entries(package)
        if isinstance(item, dict) and item.get("document_id")
    }
    memory_by_document = {
        str(item.get("source_file_ref") or ""): item
        for item in _object(document_memory_manifest).get("documents") or []
        if isinstance(item, dict) and item.get("source_file_ref")
    }
    entries = []
    for document in _documents(package):
        document_id = str(document.get("document_id") or "")
        taxonomy = taxonomy_by_doc.get(document_id, {})
        eligibility = eligibility_by_doc.get(document_id, {})
        doc_issues = issues_by_doc.get(document_id, [])
        entry = _usage_entry(
            document,
            taxonomy,
            eligibility,
            doc_issues,
            memory_entry=memory_by_document.get(document_id),
        )
        entries.append(entry)
    summary = _usage_summary(entries)
    return {
        "schema_version": DOCUMENT_USAGE_CLASSIFICATION_SCHEMA_VERSION,
        "classification_id": f"docusage_{stable_digest([run_id, len(entries), summary['source_fact_extraction_ready_total']], length=16)}",
        "normalization_run_id": run_id,
        "entries": entries,
        "summary": summary,
    }


def build_domain_context_packet(
    package: dict[str, Any],
    issue_ledger: dict[str, Any],
    usage_classification: dict[str, Any],
    document_memory_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = _run_id(package)
    unresolved_issues = [
        issue
        for issue in issue_ledger.get("entries", [])
        if isinstance(issue, dict) and issue.get("status") != "resolved"
    ]
    unresolved_issue_refs = [str(issue.get("issue_id")) for issue in unresolved_issues if issue.get("issue_id")]
    usage_entries = [
        item
        for item in usage_classification.get("entries", [])
        if isinstance(item, dict)
    ]
    stage_readiness = _stage_readiness(usage_entries, unresolved_issues)
    next_stage_refs = _next_stage_refs(package, usage_entries)
    next_stage_ref_summary = _next_stage_ref_summary(next_stage_refs)
    document_issue_refs = _document_issue_refs(usage_entries)
    refs = _safe_refs(package)
    document_memory = (
        document_memory_manifest
        if isinstance(document_memory_manifest, dict)
        else _object(package.get("document_memory_manifest"))
    )
    return {
        "schema_version": DOMAIN_CONTEXT_PACKET_SCHEMA_VERSION,
        "packet_id": f"domainctx_{stable_digest([run_id, len(usage_entries), len(unresolved_issue_refs)], length=16)}",
        "normalization_run_id": run_id,
        "domain_ingestion_status": "completed_with_unresolved_issues" if unresolved_issue_refs else "completed",
        "document_refs": [str(item.get("document_id")) for item in _documents(package) if item.get("document_id")],
        "artifact_logical_refs": {
            "document_inventory_ref": refs.get("document_inventory_ref"),
            "technical_readability_profile_ref": refs.get("technical_readability_profile_ref"),
            "taxonomy_candidates_ref": refs.get("taxonomy_candidates_ref"),
            "document_metadata_passport_ref": refs.get("document_metadata_passport_ref"),
            "document_source_eligibility_ref": refs.get("document_source_eligibility_ref"),
            "gate1_issue_ledger_ref": refs.get("gate1_issue_ledger_ref"),
            "document_usage_classification_ref": refs.get("document_usage_classification_ref"),
            "document_memory_manifest_ref": refs.get("document_memory_manifest_ref"),
            "domain_context_packet_ref": refs.get("domain_context_packet_ref"),
        },
        "document_memory_boundary": {
            "profile_id": document_memory.get("profile_id"),
            "manifest_schema_version": document_memory.get("schema_version"),
            "manifest_id": document_memory.get("manifest_id"),
            "manifest_integrity_hash": document_memory.get("integrity_hash"),
            "terminal_status_counts": copy.deepcopy(
                _object(document_memory.get("summary")).get("terminal_status_counts")
                or {}
            ),
            "accepted_documents_total": _object(document_memory.get("summary")).get(
                "accepted_documents_total"
            ),
            "gate2_memory_ready_total": _object(document_memory.get("summary")).get(
                "gate2_memory_ready_total"
            ),
            "zero_silent_loss_status": _object(document_memory.get("summary")).get(
                "zero_silent_loss_status"
            ),
            "resolver_required": True,
            "format_specific_parser_required_by_gate2": False,
            "profile_enforcement": (
                "required"
                if _supported_profile_enforced(package)
                else "legacy_compatible_advisory"
            ),
        },
        "issue_ledger_id": issue_ledger.get("issue_ledger_id"),
        "document_usage_classification_id": usage_classification.get("classification_id"),
        "unresolved_issue_refs": unresolved_issue_refs,
        "unresolved_issue_summary": _packet_issue_summary(unresolved_issues),
        "stage_readiness": stage_readiness,
        "usage_summary": copy.deepcopy(usage_classification.get("summary") or {}),
        "next_stage_refs": next_stage_refs,
        "next_stage_ref_summary": next_stage_ref_summary,
        "document_issue_refs": document_issue_refs,
        "known_assumptions": [
            "uploaded_package_is_input_reality",
            "all_readable_documents_are_ingested_before_downstream_readiness_decisions",
            "unresolved_issues_are_carried_forward_by_issue_ref",
            "domain_context_packet_is_canonical_next_stage_context",
            "document_memory_manifest_is_canonical_source_representation_root",
        ],
        "forbidden_assumptions": [
            "do_not_treat_unanswered_questions_as_resolved",
            "do_not_treat_pdf_or_html_source_role_uncertainty_as_gate1_ingestion_blocker",
            "do_not_choose_final_document_use_without_deterministic_stage_policy",
            "do_not_use_reduced_subset_as_the_only_next_stage_context",
            "do_not_load_customer_documents_to_knowledge_or_vector_store",
        ],
        "downstream_llm_instructions": {
            "may_use_safe_refs_only": True,
            "private_payload_access": "resolver_required",
            "must_consume_next_stage_refs": True,
            "must_carry_unresolved_issue_refs": True,
            "must_use_source_unit_refs": True,
            "must_use_original_source_value_refs": True,
            "must_validate_document_memory_manifest": True,
            "must_account_for_selected_row_segment_refs": True,
            "must_not_decide_issue_criticality": True,
            "must_not_mark_issue_resolved_without_resolution_artifact": True,
        },
        "private_slice_access": {
            "available_through_resolver": bool(
                package.get("private_normalized_source_units")
                or package.get("private_normalized_slices")
            ),
            "raw_private_payload_in_packet": False,
            "source_unit_schema_version": "source_unit_provenance_v0",
            "preferred_extraction_source_schema_version": "private_normalized_source_unit_v0",
            "full_source_payload_schema_version": "private_normalized_source_payload_v0",
            "source_input_priority": "full_source_unit_then_legacy_preview",
            "legacy_preview_expansion_ready": False,
            "table_slice_schema_version": "private_normalized_table_slice_v0",
            "text_slice_schema_version": "private_normalized_text_slice_v0",
            "source_value_projection_policy": "private_payload_path_plus_checksum_v0",
            "row_segment_coverage_policy": "source_unit_coverage_v0",
            "dry_run_package_builder": "Gate2InputReadinessFactory.create",
        },
        "vector_knowledge_guard": {
            "customer_docs_loaded_to_knowledge": False,
            "vectorization_performed": False,
            "rag_used_for_gate1": False,
        },
        "created_at": "not_recorded",
    }


def _issue_from_gap(run_id: str, gap: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    gap_type = str(gap.get("gap_type") or "metadata_gap")
    target_refs = [str(item) for item in gap.get("target_document_refs") or [] if item]
    question = _question_for_gap(package, str(gap.get("gap_id") or ""))
    resolution_refs = _resolution_refs_for_question(package, str(question.get("question_id") or ""))
    status = "resolved" if resolution_refs else "unresolved"
    unresolved_reason = None
    if status != "resolved":
        if not question:
            unresolved_reason = "skipped_question"
        elif question.get("ask_policy") in {"defer", "do_not_ask"}:
            unresolved_reason = "skipped_question"
        else:
            unresolved_reason = "awaiting_answer"
    issue_type = _issue_type_for_gap(gap_type)
    return _issue(
        run_id=run_id,
        issue_type=issue_type,
        target_document_refs=target_refs,
        evidence_refs=[
            str(item)
            for item in [gap.get("gap_id"), question.get("question_id")]
            if item
        ]
        + [str(item) for item in gap.get("safe_evidence_refs") or [] if item],
        blocker_refs=[str(item) for item in gap.get("blocker_refs") or [] if item],
        reason_codes=[str(item) for item in gap.get("reason_codes") or [] if item],
        criticality=str(gap.get("criticality") or "clarifying"),
        affected_stage=_affected_stage(issue_type, gap),
        blocked_stages=_blocked_stages_for_issue(issue_type, gap),
        stages_that_may_continue=_continuation_stages_for_issue(issue_type, gap),
        status=status,
        unresolved_reason=unresolved_reason,
        user_was_asked=bool(question),
        answer_supplied=bool(resolution_refs),
        ask_policy=str((question or gap).get("ask_policy") or "not_applicable"),
        resolution_refs=resolution_refs,
        provenance={
            "source_artifact_type": "gate1_metadata_gap_report_v0",
            "source_ref": str(gap.get("gap_id") or ""),
            "deterministic_policy": True,
        },
        safe_explanation=str(gap.get("safe_explanation") or _safe_issue_explanation(issue_type)),
    )


def _issue_from_clarification_question(run_id: str, question: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    gap_type = str(question.get("gap_type") or "metadata_gap")
    target_refs = [str(item) for item in question.get("target_document_refs") or [] if item]
    question_id = str(question.get("question_id") or "")
    resolution_refs = _resolution_refs_for_question(package, question_id)
    status = "resolved" if resolution_refs else "unresolved"
    ask_policy = str(question.get("ask_policy") or "ask_now")
    unresolved_reason = None
    if status != "resolved":
        unresolved_reason = "skipped_question" if ask_policy in {"defer", "do_not_ask"} else "awaiting_answer"
    issue_type = _issue_type_for_gap(gap_type)
    return _issue(
        run_id=run_id,
        issue_type=issue_type,
        target_document_refs=target_refs,
        evidence_refs=[
            str(item)
            for item in [question.get("gap_id"), question_id]
            if item
        ],
        blocker_refs=[],
        reason_codes=[str(item) for item in question.get("reason_codes") or [] if item],
        criticality=str(question.get("criticality") or "clarifying"),
        affected_stage=_affected_stage(issue_type, question),
        blocked_stages=_blocked_stages_for_issue(issue_type, question),
        stages_that_may_continue=_continuation_stages_for_issue(issue_type, question),
        status=status,
        unresolved_reason=unresolved_reason,
        user_was_asked=True,
        answer_supplied=bool(resolution_refs),
        ask_policy=ask_policy,
        resolution_refs=resolution_refs,
        provenance={
            "source_artifact_type": "gate1_clarification_request_v0",
            "source_ref": str(question.get("gap_id") or question_id),
            "deterministic_policy": True,
        },
        safe_explanation=str(question.get("safe_explanation") or _safe_issue_explanation(issue_type)),
    )


def _issue_from_blocker(run_id: str, blocker: dict[str, Any], target_refs: list[str]) -> dict[str, Any]:
    code = str(blocker.get("code") or "unknown_blocker")
    issue_type = _issue_type_for_blocker(code)
    blocked_stages = _blocked_stages_for_blocker(code)
    return _issue(
        run_id=run_id,
        issue_type=issue_type,
        target_document_refs=target_refs,
        evidence_refs=[str(blocker.get("blocker_id"))] if blocker.get("blocker_id") else [],
        blocker_refs=[str(blocker.get("blocker_id"))] if blocker.get("blocker_id") else [],
        reason_codes=[code],
        criticality="critical" if code in READABILITY_BLOCKERS or code == "no_files" else "clarifying",
        affected_stage=blocked_stages[0] if blocked_stages else "consolidation",
        blocked_stages=blocked_stages,
        stages_that_may_continue=_continuation_stages_for_blocker(code),
        status="unresolved",
        unresolved_reason="blocker_open",
        user_was_asked=False,
        answer_supplied=False,
        ask_policy="not_applicable",
        resolution_refs=[],
        provenance={
            "source_artifact_type": "normalization_blockers_v0",
            "source_ref": str(blocker.get("blocker_id") or ""),
            "deterministic_policy": True,
        },
        safe_explanation=str(blocker.get("safe_message") or _safe_issue_explanation(issue_type)),
    )


def _profile_assessment_requires_issue(
    assessment: dict[str, Any], eligibility: dict[str, Any]
) -> bool:
    if assessment.get("terminal_status") == "complete":
        return False
    source_status = str(eligibility.get("source_eligibility") or "")
    return source_status in {
        "accepted_for_gate2",
        "accepted_as_source_candidate_for_gate2",
        "metadata_review_required",
        "duplicate_needs_canonical_choice",
        "source_policy_review_required",
        "requires_manual_review",
        "unknown_role_requires_review",
        "source_role_policy_review_required",
    }


def _issue_from_profile_assessment(
    run_id: str, assessment: dict[str, Any]
) -> dict[str, Any]:
    document_ref = str(assessment.get("document_ref") or "")
    terminal_status = str(assessment.get("terminal_status") or "blocked")
    structural_review = terminal_status == "review_required"
    issue_type = "structural_uncertainty" if structural_review else "readability_blocker"
    blocked_stages = (
        ["consolidation", "declaration_support"]
        if structural_review
        else [
            "source_fact_extraction",
            "cross_check",
            "consolidation",
            "declaration_support",
        ]
    )
    stages_that_may_continue = (
        ["domain_ingestion", "source_fact_extraction", "cross_check"]
        if structural_review
        else ["domain_ingestion"]
    )
    return _issue(
        run_id=run_id,
        issue_type=issue_type,
        target_document_refs=[document_ref] if document_ref else [],
        evidence_refs=[document_ref] if document_ref else [],
        blocker_refs=[],
        reason_codes=[
            str(item) for item in assessment.get("reason_codes") or [] if item
        ]
        or [f"supported_profile_terminal_{terminal_status}"],
        criticality="clarifying" if structural_review else "critical",
        affected_stage=blocked_stages[0],
        blocked_stages=blocked_stages,
        stages_that_may_continue=stages_that_may_continue,
        status="unresolved",
        unresolved_reason="carried_forward" if structural_review else "blocker_open",
        user_was_asked=False,
        answer_supplied=False,
        ask_policy="do_not_ask" if structural_review else "not_applicable",
        resolution_refs=[],
        provenance={
            "source_artifact_type": SUPPORTED_PROFILE_ASSESSMENT_SCHEMA_VERSION,
            "source_ref": f"{document_ref}:{terminal_status}",
            "deterministic_policy": True,
        },
        safe_explanation=(
            "Source memory is available with explicit structural uncertainty."
            if structural_review
            else "The source document is outside the complete supported-profile memory."
        ),
    )


def _issues_from_eligibility(run_id: str, entry: dict[str, Any], package: dict[str, Any]) -> list[dict[str, Any]]:
    document_id = str(entry.get("document_id") or "")
    issues: list[dict[str, Any]] = []
    reason_codes = [str(item) for item in entry.get("reason_codes") or [] if item]
    policy_uncertain = (
        entry.get("source_policy_review_required") is True
        or entry.get("source_eligibility") == "source_policy_review_required"
        or str(entry.get("source_role_policy_status") or "") in {"review_required", "context_issue"}
        or "pdf_html_source_role_policy_carried_forward" in reason_codes
        or "source_policy_uncertainty_carried_forward" in reason_codes
    )
    if policy_uncertain:
        issues.append(
            _issue(
                run_id=run_id,
                issue_type="source_role_policy_uncertainty",
                target_document_refs=[document_id] if document_id else [],
                evidence_refs=[document_id] if document_id else [],
                blocker_refs=[str(item) for item in entry.get("blocker_refs") or [] if item],
                reason_codes=reason_codes or ["source_policy_uncertainty_carried_forward"],
                criticality="clarifying",
                affected_stage="consolidation",
                blocked_stages=["consolidation", "declaration_support"],
                stages_that_may_continue=["domain_ingestion", "source_fact_extraction", "cross_check"],
                status="unresolved",
                unresolved_reason="carried_forward",
                user_was_asked=False,
                answer_supplied=False,
                ask_policy="do_not_ask",
                resolution_refs=[],
                provenance={
                    "source_artifact_type": "document_source_eligibility_v0",
                    "source_ref": document_id,
                    "deterministic_policy": True,
                },
                safe_explanation="PDF/HTML source-role uncertainty is carried forward; it is not a Gate 1 ingestion blocker.",
            )
        )
    if entry.get("source_eligibility") == "duplicate_needs_canonical_choice":
        issues.append(
            _issue(
                run_id=run_id,
                issue_type="duplicate_canonical_choice",
                target_document_refs=_duplicate_targets(document_id, package),
                evidence_refs=[document_id] if document_id else [],
                blocker_refs=[str(item) for item in entry.get("blocker_refs") or [] if item],
                reason_codes=reason_codes or ["semantic_duplicate_requires_user_choice"],
                criticality="critical",
                affected_stage="consolidation",
                blocked_stages=["consolidation", "declaration_support"],
                stages_that_may_continue=["domain_ingestion", "source_fact_extraction", "cross_check"],
                status="unresolved",
                unresolved_reason="carried_forward",
                user_was_asked=False,
                answer_supplied=False,
                ask_policy="ask_now",
                resolution_refs=[],
                provenance={
                    "source_artifact_type": "document_source_eligibility_v0",
                    "source_ref": document_id,
                    "deterministic_policy": True,
                },
                safe_explanation="Duplicate source candidates are ingested, but consolidation needs a canonical choice.",
            )
        )
    return issues


def _usage_entry(
    document: dict[str, Any],
    taxonomy: dict[str, Any],
    eligibility: dict[str, Any],
    doc_issues: list[dict[str, Any]],
    *,
    memory_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document_ref = str(document.get("document_id") or "")
    issue_refs = [str(issue.get("issue_id")) for issue in doc_issues if issue.get("issue_id")]
    issue_types = {str(issue.get("issue_type")) for issue in doc_issues}
    issue_refs_by_stage = _issue_refs_by_stage(doc_issues)
    taxonomy_class = str(taxonomy.get("document_class_candidate") or "unknown_or_needs_review")
    eligibility_status = str(eligibility.get("source_eligibility") or "not_evaluated")
    readable = _document_readable(document)
    memory_status = str(_object(memory_entry).get("gate2_memory_status") or "")
    lineage_only = memory_status == "lineage_only"
    scope_readiness = _object(
        _object(_object(memory_entry).get("source_scope")).get("scope_readiness")
    )
    machine_source_scope_ready = any(
        (
            scope_readiness.get("text_scope") == "ready",
            scope_readiness.get("neutral_structure_scope") == "ready",
            scope_readiness.get("canonical_table_scope")
            == "ready_validated_projection_only",
        )
    )
    visual_review_only = bool(
        memory_entry
        and scope_readiness.get("visual_scope") == "ready"
        and not machine_source_scope_ready
    )
    source_candidate = taxonomy_class in SOURCE_DOCUMENT_CLASSES or eligibility_status in {
        "accepted_for_gate2",
        "accepted_as_source_candidate_for_gate2",
        "metadata_review_required",
        "duplicate_needs_canonical_choice",
        "source_policy_review_required",
    }
    methodology_or_output = taxonomy_class in METHODOLOGY_OR_OUTPUT_CLASSES or eligibility_status == "methodology_or_output_artifact"
    extraction_blocked = bool(issue_types & {"readability_blocker", "no_files"})
    if not readable:
        extraction_blocked = True
    source_ready = bool(
        source_candidate
        and not extraction_blocked
        and not lineage_only
        and not visual_review_only
    )
    source_ready_with_issues = bool(source_ready and issue_refs)
    cross_check_ready = bool(
        readable
        and not extraction_blocked
        and not lineage_only
        and not visual_review_only
    )
    consolidation_blocked = bool(issue_types & CONSOLIDATION_ISSUES)
    declaration_blocked = bool(issue_types & CONSOLIDATION_ISSUES)
    usage_modes = ["ingested"]
    if lineage_only:
        usage_modes.extend(["archive_lineage", "audit_reference"])
    elif visual_review_only:
        usage_modes.extend(["visual_review_candidate", "audit_reference"])
    elif source_ready:
        usage_modes.append("source_extraction_candidate")
    if cross_check_ready:
        usage_modes.append("cross_check_candidate")
    if methodology_or_output:
        usage_modes.append("declaration_support_reference")
    elif source_ready and not consolidation_blocked:
        usage_modes.append("consolidation_candidate")
    if not source_ready and readable and not lineage_only:
        usage_modes.append("audit_reference")

    if lineage_only:
        readiness_by_stage = {
            "domain_ingestion": "completed",
            "source_fact_extraction": "not_applicable_lineage_only",
            "cross_check": "not_applicable_lineage_only",
            "consolidation": "not_applicable_lineage_only",
            "declaration_support": "not_applicable_lineage_only",
        }
    elif visual_review_only:
        readiness_by_stage = {
            "domain_ingestion": "completed",
            "source_fact_extraction": "review_required_visual_consumer",
            "cross_check": "review_required_visual_consumer",
            "consolidation": "review_required_visual_consumer",
            "declaration_support": "review_required_visual_consumer",
        }
    else:
        readiness_by_stage = {
            "domain_ingestion": "completed",
            "source_fact_extraction": _ready_label(
                source_ready, source_ready_with_issues, extraction_blocked
            ),
            "cross_check": _ready_label(
                cross_check_ready,
                bool(cross_check_ready and issue_refs),
                extraction_blocked,
            ),
            "consolidation": (
                "blocked_unresolved_issues"
                if consolidation_blocked
                else ("ready" if source_ready else "not_applicable")
            ),
            "declaration_support": (
                "blocked_unresolved_issues"
                if declaration_blocked
                else ("ready" if readable else "blocked_unreadable")
            ),
        }

    return {
        "document_ref": document_ref,
        "inferred_role": taxonomy_class,
        "source_eligibility_compat_status": eligibility_status,
        "usage_modes": sorted(set(usage_modes)),
        "issue_refs": issue_refs,
        "warning_issue_refs": [
            str(issue.get("issue_id"))
            for issue in doc_issues
            if issue.get("status") != "resolved" and issue.get("issue_id")
        ],
        "issue_refs_by_stage": issue_refs_by_stage,
        "readiness_by_stage": readiness_by_stage,
        "private_payload_access": "resolver_required" if readable else "not_available",
        "raw_private_payload_in_classification": False,
        "deterministic_basis": {
            "container_format": document.get("container_format"),
            "bytes_status": document.get("bytes_status"),
            "machine_readable": document.get("machine_readable"),
            "taxonomy_class": taxonomy_class,
            "source_eligibility": eligibility_status,
            "document_memory_status": memory_status or "not_available",
            "machine_source_scope_ready": machine_source_scope_ready,
            "visual_review_only": visual_review_only,
        },
    }


def _issue(
    *,
    run_id: str,
    issue_type: str,
    target_document_refs: list[str],
    evidence_refs: list[str],
    blocker_refs: list[str],
    reason_codes: list[str],
    criticality: str,
    affected_stage: str,
    blocked_stages: list[str],
    stages_that_may_continue: list[str],
    status: str,
    unresolved_reason: str | None,
    user_was_asked: bool,
    answer_supplied: bool,
    ask_policy: str,
    resolution_refs: list[str],
    provenance: dict[str, Any],
    safe_explanation: str,
) -> dict[str, Any]:
    targets = sorted(set(target_document_refs))
    material = [run_id, issue_type, ",".join(targets), ",".join(sorted(reason_codes)), provenance.get("source_ref")]
    return {
        "schema_version": ISSUE_LEDGER_SCHEMA_VERSION,
        "issue_id": f"issue_{stable_digest(material, length=16)}",
        "normalization_run_id": run_id,
        "issue_type": issue_type,
        "target_document_refs": targets,
        "criticality": criticality if criticality in {"critical", "clarifying", "non_critical"} else "clarifying",
        "affected_stage": affected_stage,
        "blocked_stages": sorted(set(blocked_stages)),
        "stages_that_may_continue": sorted(set(stages_that_may_continue)),
        "status": status,
        "unresolved_reason": unresolved_reason,
        "user_was_asked": bool(user_was_asked),
        "answer_supplied": bool(answer_supplied),
        "ask_policy": ask_policy,
        "resolution_refs": sorted(set(resolution_refs)),
        "evidence_refs": sorted(set(evidence_refs)),
        "blocker_refs": sorted(set(blocker_refs)),
        "reason_codes": sorted(set(reason_codes)),
        "provenance": copy.deepcopy(provenance),
        "created_at": "not_recorded",
        "updated_at": "not_recorded",
        "safe_explanation": safe_explanation,
    }


def _append_issue(
    issues: list[dict[str, Any]],
    seen: set[tuple[str, tuple[str, ...], str]],
    issue: dict[str, Any],
) -> None:
    key = (
        str(issue.get("issue_type") or ""),
        tuple(issue.get("target_document_refs") or []),
        str((issue.get("provenance") or {}).get("source_ref") or ""),
    )
    if key in seen:
        return
    seen.add(key)
    issues.append(issue)


def _issue_summary(issues: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(issue.get("status") or "unknown") for issue in issues)
    type_counts = Counter(str(issue.get("issue_type") or "unknown") for issue in issues)
    criticality_counts = Counter(str(issue.get("criticality") or "unknown") for issue in issues)
    affected_stage_counts = Counter(str(issue.get("affected_stage") or "unknown") for issue in issues)
    skipped_total = sum(
        1
        for issue in issues
        if issue.get("status") != "resolved" and issue.get("unresolved_reason") == "skipped_question"
    )
    awaiting_answer_total = sum(
        1
        for issue in issues
        if issue.get("status") != "resolved" and issue.get("unresolved_reason") == "awaiting_answer"
    )
    return {
        "issues_total": len(issues),
        "unresolved_issues_total": sum(1 for issue in issues if issue.get("status") != "resolved"),
        "resolved_issues_total": status_counts.get("resolved", 0),
        "skipped_unresolved_issues_total": skipped_total,
        "awaiting_answer_unresolved_issues_total": awaiting_answer_total,
        "status_counts": dict(sorted(status_counts.items())),
        "issue_type_counts": dict(sorted(type_counts.items())),
        "criticality_counts": dict(sorted(criticality_counts.items())),
        "affected_stage_counts": dict(sorted(affected_stage_counts.items())),
        "source_fact_extraction_blocking_total": _blocking_count(issues, "source_fact_extraction"),
        "consolidation_blocking_total": _blocking_count(issues, "consolidation"),
        "declaration_support_blocking_total": _blocking_count(issues, "declaration_support"),
    }


def _usage_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    readiness_counts: dict[str, Counter[str]] = defaultdict(Counter)
    mode_counts: Counter[str] = Counter()
    for entry in entries:
        for mode in entry.get("usage_modes") or []:
            mode_counts[str(mode)] += 1
        for stage, readiness in (entry.get("readiness_by_stage") or {}).items():
            readiness_counts[str(stage)][str(readiness)] += 1
    return {
        "documents_total": len(entries),
        "readable_documents_total": sum(1 for entry in entries if entry.get("private_payload_access") == "resolver_required"),
        "source_fact_extraction_ready_total": sum(
            1
            for entry in entries
            if (entry.get("readiness_by_stage") or {}).get("source_fact_extraction") in {"ready", "ready_with_issues"}
        ),
        "source_fact_extraction_blocked_total": sum(
            1
            for entry in entries
            if str((entry.get("readiness_by_stage") or {}).get("source_fact_extraction", "")).startswith("blocked")
        ),
        "usage_mode_counts": dict(sorted(mode_counts.items())),
        "readiness_counts_by_stage": {
            stage: dict(sorted(counter.items()))
            for stage, counter in sorted(readiness_counts.items())
        },
    }


def _domain_ingestion_summary(
    issue_ledger: dict[str, Any],
    usage_classification: dict[str, Any],
    domain_context_packet: dict[str, Any],
) -> dict[str, Any]:
    issue_summary = issue_ledger.get("summary") or {}
    usage_summary = usage_classification.get("summary") or {}
    unresolved_total = int(issue_summary.get("unresolved_issues_total") or 0)
    return {
        "schema_version": "domain_ingestion_summary_v0",
        "domain_ingestion_status": "completed_with_unresolved_issues" if unresolved_total else "completed",
        "issue_ledger_status": issue_ledger.get("ledger_status"),
        "domain_context_packet_status": "ready",
        "counts": {
            "issues_total": int(issue_summary.get("issues_total") or 0),
            "unresolved_issues_total": unresolved_total,
            "skipped_unresolved_issues_total": int(issue_summary.get("skipped_unresolved_issues_total") or 0),
            "awaiting_answer_unresolved_issues_total": int(
                issue_summary.get("awaiting_answer_unresolved_issues_total") or 0
            ),
            "documents_total": int(usage_summary.get("documents_total") or 0),
            "source_fact_extraction_ready_total": int(usage_summary.get("source_fact_extraction_ready_total") or 0),
            "source_fact_extraction_blocked_total": int(usage_summary.get("source_fact_extraction_blocked_total") or 0),
        },
        "stage_readiness": copy.deepcopy(domain_context_packet.get("stage_readiness") or {}),
        "next_stage_ref_summary": copy.deepcopy(domain_context_packet.get("next_stage_ref_summary") or {}),
    }


def _stage_readiness(usage_entries: list[dict[str, Any]], unresolved_issues: list[dict[str, Any]]) -> dict[str, str]:
    stage_values = {
        stage: [str((entry.get("readiness_by_stage") or {}).get(stage) or "not_applicable") for entry in usage_entries]
        for stage in STAGES
    }
    result = {}
    for stage in STAGES:
        values = stage_values.get(stage) or []
        if not values:
            result[stage] = "blocked_no_documents"
        elif any(value in {"ready", "ready_with_issues"} for value in values):
            result[stage] = "ready_with_issue_context" if _stage_has_unresolved_issue(unresolved_issues, stage) else "ready"
        elif any(value.startswith("blocked") for value in values):
            result[stage] = "blocked"
        else:
            result[stage] = "not_applicable"
    return result


def _packet_issue_summary(unresolved_issues: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "unresolved_issues_total": len(unresolved_issues),
        "issue_type_counts": dict(sorted(Counter(str(item.get("issue_type") or "unknown") for item in unresolved_issues).items())),
        "criticality_counts": dict(sorted(Counter(str(item.get("criticality") or "unknown") for item in unresolved_issues).items())),
        "skipped_unresolved_issues_total": sum(1 for item in unresolved_issues if item.get("unresolved_reason") == "skipped_question"),
        "awaiting_answer_unresolved_issues_total": sum(
            1 for item in unresolved_issues if item.get("unresolved_reason") == "awaiting_answer"
        ),
    }


def _next_stage_refs(package: dict[str, Any], usage_entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    eligibility_by_doc = {
        str(item.get("document_id")): item
        for item in _eligibility_entries(package)
        if isinstance(item, dict) and item.get("document_id")
    }
    handoff = package.get("gate2_handoff") if isinstance(package.get("gate2_handoff"), dict) else {}
    primary_refs = {
        str(item)
        for item in handoff.get("included_document_ids") or []
        if item
    }
    if not primary_refs:
        primary_refs = {
            doc_id
            for doc_id, entry in eligibility_by_doc.items()
            if entry.get("included_in_reduced_subset") is True
        }

    source_ready_refs: set[str] = set()
    cross_check_refs: set[str] = set()
    declaration_support_refs: set[str] = set()
    audit_reference_refs: set[str] = set()
    duplicate_or_non_primary_refs: set[str] = set()
    archive_lineage_refs: set[str] = set()
    visual_review_refs: set[str] = set()

    for entry in usage_entries:
        document_ref = str(entry.get("document_ref") or "")
        if not document_ref:
            continue
        readiness = entry.get("readiness_by_stage") if isinstance(entry.get("readiness_by_stage"), dict) else {}
        usage_modes = {str(item) for item in entry.get("usage_modes") or []}
        eligibility = eligibility_by_doc.get(document_ref, {})
        eligibility_status = str(eligibility.get("source_eligibility") or "")
        reason_codes = {str(item) for item in eligibility.get("reason_codes") or []}

        if readiness.get("source_fact_extraction") in {"ready", "ready_with_issues"}:
            source_ready_refs.add(document_ref)
        if readiness.get("cross_check") in {"ready", "ready_with_issues"} or "cross_check_candidate" in usage_modes:
            cross_check_refs.add(document_ref)
        if (
            readiness.get("declaration_support") in {"ready", "ready_with_issues"}
            or "declaration_support_reference" in usage_modes
        ):
            declaration_support_refs.add(document_ref)
        if "audit_reference" in usage_modes or eligibility_status in {"outside_case_scope", "excluded_from_gate2"}:
            audit_reference_refs.add(document_ref)
        if "archive_lineage" in usage_modes:
            archive_lineage_refs.add(document_ref)
        if "visual_review_candidate" in usage_modes:
            visual_review_refs.add(document_ref)
        if eligibility_status == "duplicate_needs_canonical_choice" or "noncanonical_exact_duplicate_excluded" in reason_codes:
            duplicate_or_non_primary_refs.add(document_ref)

    primary_source_extraction_refs = source_ready_refs & primary_refs
    secondary_source_extraction_refs = (
        source_ready_refs
        - primary_source_extraction_refs
        - duplicate_or_non_primary_refs
        - audit_reference_refs
    )
    source_ready_not_primary_refs = source_ready_refs - primary_source_extraction_refs
    covered_source_ready_refs = (
        primary_source_extraction_refs
        | secondary_source_extraction_refs
        | duplicate_or_non_primary_refs
        | audit_reference_refs
    )
    dropped_source_ready_refs = source_ready_refs - covered_source_ready_refs

    return {
        "source_fact_ready_refs": _sorted_refs(source_ready_refs),
        "primary_source_extraction_refs": _sorted_refs(primary_source_extraction_refs),
        "secondary_source_extraction_refs": _sorted_refs(secondary_source_extraction_refs),
        "source_ready_not_primary_refs": _sorted_refs(source_ready_not_primary_refs),
        "cross_check_refs": _sorted_refs(cross_check_refs),
        "declaration_support_refs": _sorted_refs(declaration_support_refs),
        "audit_reference_refs": _sorted_refs(audit_reference_refs),
        "archive_lineage_refs": _sorted_refs(archive_lineage_refs),
        "visual_review_refs": _sorted_refs(visual_review_refs),
        "duplicate_or_non_primary_refs": _sorted_refs(duplicate_or_non_primary_refs),
        "dropped_source_ready_refs": _sorted_refs(dropped_source_ready_refs),
    }


def _next_stage_ref_summary(next_stage_refs: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "source_fact_ready_total": len(next_stage_refs.get("source_fact_ready_refs") or []),
        "primary_source_extraction_total": len(next_stage_refs.get("primary_source_extraction_refs") or []),
        "secondary_source_extraction_total": len(next_stage_refs.get("secondary_source_extraction_refs") or []),
        "source_ready_not_primary_total": len(next_stage_refs.get("source_ready_not_primary_refs") or []),
        "cross_check_total": len(next_stage_refs.get("cross_check_refs") or []),
        "declaration_support_total": len(next_stage_refs.get("declaration_support_refs") or []),
        "audit_reference_total": len(next_stage_refs.get("audit_reference_refs") or []),
        "archive_lineage_total": len(next_stage_refs.get("archive_lineage_refs") or []),
        "visual_review_total": len(next_stage_refs.get("visual_review_refs") or []),
        "duplicate_or_non_primary_total": len(next_stage_refs.get("duplicate_or_non_primary_refs") or []),
        "dropped_source_ready_total": len(next_stage_refs.get("dropped_source_ready_refs") or []),
    }


def _document_issue_refs(usage_entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    refs_by_document = {}
    for entry in usage_entries:
        document_ref = str(entry.get("document_ref") or "")
        issue_refs = [str(item) for item in entry.get("warning_issue_refs") or entry.get("issue_refs") or [] if item]
        if document_ref and issue_refs:
            refs_by_document[document_ref] = sorted(set(issue_refs))
    return dict(sorted(refs_by_document.items()))


def _sorted_refs(values: set[str]) -> list[str]:
    return sorted(item for item in values if item)


def _issue_refs_by_stage(doc_issues: list[dict[str, Any]]) -> dict[str, list[str]]:
    refs_by_stage: dict[str, list[str]] = defaultdict(list)
    for issue in doc_issues:
        issue_id = str(issue.get("issue_id") or "")
        if not issue_id:
            continue
        for stage in issue.get("blocked_stages") or []:
            refs_by_stage[str(stage)].append(issue_id)
    return {stage: sorted(set(refs)) for stage, refs in sorted(refs_by_stage.items())}


def _issues_by_doc(issue_ledger: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issue_ledger.get("entries", []):
        if not isinstance(issue, dict):
            continue
        for document_ref in issue.get("target_document_refs") or []:
            result[str(document_ref)].append(issue)
    return result


def _issue_type_for_gap(gap_type: str) -> str:
    if gap_type == "duplicate_canonical_choice":
        return "duplicate_canonical_choice"
    if gap_type == "unclear_document_role":
        return "unclear_document_role"
    if gap_type == "outside_scope_confirmation":
        return "outside_scope_confirmation"
    return "metadata_gap"


def _issue_type_for_blocker(code: str) -> str:
    if code == "duplicate_review":
        return "duplicate_canonical_choice"
    if code == "unknown_role":
        return "unclear_document_role"
    if code == "no_files":
        return "no_files"
    if code in READABILITY_BLOCKERS or code == "zip_requires_review":
        return "readability_blocker"
    return "normalization_warning"


def _blocked_stages_for_issue(issue_type: str, gap: dict[str, Any]) -> list[str]:
    if issue_type == "readability_blocker":
        return ["source_fact_extraction", "cross_check", "consolidation", "declaration_support"]
    if issue_type in {"duplicate_canonical_choice", "unclear_document_role", "source_role_policy_uncertainty"}:
        return ["consolidation", "declaration_support"]
    dependency_stage = str(gap.get("dependency_stage") or "")
    if dependency_stage == "gate2_source_fact_extraction":
        return ["source_fact_extraction", "consolidation", "declaration_support"]
    if dependency_stage == "gate2_handoff":
        return ["consolidation", "declaration_support"]
    if dependency_stage == "declaration_model":
        return ["declaration_support"]
    if dependency_stage == "audit_only":
        return []
    return ["consolidation", "declaration_support"] if gap.get("blocks_gate2") else ["declaration_support"]


def _blocked_stages_for_blocker(code: str) -> list[str]:
    if code == "duplicate_review":
        return ["consolidation", "declaration_support"]
    if code == "unknown_role":
        return ["consolidation", "declaration_support"]
    if code in READABILITY_BLOCKERS or code == "no_files" or code == "zip_requires_review":
        return ["source_fact_extraction", "cross_check", "consolidation", "declaration_support"]
    return ["declaration_support"]


def _continuation_stages_for_issue(issue_type: str, gap: dict[str, Any]) -> list[str]:
    blocked = set(_blocked_stages_for_issue(issue_type, gap))
    return [stage for stage in STAGES if stage not in blocked]


def _continuation_stages_for_blocker(code: str) -> list[str]:
    blocked = set(_blocked_stages_for_blocker(code))
    return [stage for stage in STAGES if stage not in blocked]


def _affected_stage(issue_type: str, gap: dict[str, Any]) -> str:
    blocked = _blocked_stages_for_issue(issue_type, gap)
    if blocked:
        return blocked[0]
    return str(gap.get("dependency_stage") or "audit_only")


def _safe_issue_explanation(issue_type: str) -> str:
    if issue_type == "source_role_policy_uncertainty":
        return "Source role uncertainty is carried to downstream stages as an issue."
    if issue_type == "duplicate_canonical_choice":
        return "Duplicate candidates are ingested, but consolidation needs canonical selection."
    if issue_type == "readability_blocker":
        return "The document cannot be used for source extraction until readability is restored."
    return "The issue is carried forward with the domain context packet."


def _question_for_gap(package: dict[str, Any], gap_id: str) -> dict[str, Any]:
    request = package.get("gate1_clarification_request")
    if not isinstance(request, dict):
        return {}
    for question in request.get("questions", []):
        if isinstance(question, dict) and str(question.get("gap_id") or "") == gap_id:
            return question
    return {}


def _clarification_questions(package: dict[str, Any]) -> list[dict[str, Any]]:
    request = package.get("gate1_clarification_request")
    if not isinstance(request, dict):
        return []
    questions = request.get("questions")
    return [item for item in questions if isinstance(item, dict)] if isinstance(questions, list) else []


def _resolution_refs_for_question(package: dict[str, Any], question_id: str) -> list[str]:
    refs = []
    if not question_id:
        return refs
    for resolution in package.get("gate1_clarification_resolutions", []):
        if not isinstance(resolution, dict):
            continue
        if str(resolution.get("question_id") or "") != question_id:
            continue
        if resolution.get("validation_status") == "passed" and resolution.get("usable_by_source_eligibility_v2") is True:
            refs.append(str(resolution.get("resolution_id") or question_id))
    return refs


def _duplicate_targets(document_id: str, package: dict[str, Any]) -> list[str]:
    if not document_id:
        return []
    document_by_id = {str(item.get("document_id")): item for item in _documents(package) if item.get("document_id")}
    document = document_by_id.get(document_id, {})
    duplicate_of = str(document.get("duplicate_of_document_id") or "")
    refs = [document_id]
    if duplicate_of:
        refs.insert(0, duplicate_of)
    return refs


def _document_readable(document: dict[str, Any]) -> bool:
    if document.get("bytes_status") != "available":
        return False
    if document.get("read_error_class"):
        return False
    return str(document.get("readable") or "") in {"yes", "conditional"}


def _ready_label(ready: bool, with_issues: bool, blocked: bool) -> str:
    if ready and with_issues:
        return "ready_with_issues"
    if ready:
        return "ready"
    return "blocked_unreadable" if blocked else "not_applicable"


def _stage_has_unresolved_issue(unresolved_issues: list[dict[str, Any]], stage: str) -> bool:
    return any(stage in set(issue.get("blocked_stages") or []) for issue in unresolved_issues)


def _blocking_count(issues: list[dict[str, Any]], stage: str) -> int:
    return sum(1 for issue in issues if stage in set(issue.get("blocked_stages") or []))


def _documents(package: dict[str, Any]) -> list[dict[str, Any]]:
    documents = package.get("document_inventory", {}).get("documents", [])
    return [item for item in documents if isinstance(item, dict)]


def _eligibility_entries(package: dict[str, Any]) -> list[dict[str, Any]]:
    payload = package.get("document_source_eligibility")
    if not isinstance(payload, dict):
        return []
    entries = payload.get("entries")
    return [item for item in entries if isinstance(item, dict)] if isinstance(entries, list) else []


def _gap_report(package: dict[str, Any]) -> dict[str, Any]:
    value = package.get("gate1_metadata_gap_report")
    return value if isinstance(value, dict) else {}


def _safe_refs(package: dict[str, Any]) -> dict[str, Any]:
    value = package.get("safe_artifact_refs")
    return value if isinstance(value, dict) else {}


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _supported_profile_enforced(package: dict[str, Any]) -> bool:
    context = _object(package.get("input_context"))
    if context.get("gate1_supported_profile_enforcement") == "legacy_compatible":
        return False
    return context.get("pdf_layout_slice2_enabled") is not False


def _run_id(package: dict[str, Any]) -> str:
    return str(package.get("normalization_run", {}).get("run_id") or "")
