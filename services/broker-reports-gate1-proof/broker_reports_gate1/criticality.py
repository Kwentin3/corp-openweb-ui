from __future__ import annotations

from collections import Counter
from typing import Any


CRITICALITIES = {"critical", "clarifying", "non_critical"}
BLOCKING_SCOPES = {"gate2_handoff", "source_eligibility", "declaration_model", "audit_only"}
DEPENDENCY_STAGES = {
    "normalization",
    "gate2_handoff",
    "gate2_source_fact_extraction",
    "declaration_model",
    "output_review",
    "audit_only",
}
BLOCKING_REASON_CATEGORIES = {
    "source_scope",
    "duplicate_risk",
    "role_ambiguity",
    "declaration_context",
    "audit_quality",
    "display_metadata",
}
AUTO_RESOLUTION_POLICIES = {
    "none",
    "exact_duplicate_latest_wins",
    "case_context_allows_warning",
    "defer_to_gate2_dates",
}
ASK_POLICIES = {"ask_now", "ask_if_user_available", "defer", "do_not_ask"}
ANSWER_IMPACTS = {
    "unblocks_gate2",
    "improves_confidence",
    "adds_audit_context",
    "specialist_note_only",
}

CRITICAL_METADATA_FIELDS = {
    "report_period_start",
    "report_period_end",
    "tax_year_candidate",
    "document_role",
    "content_kind",
    "role_hypotheses",
}

PERIOD_METADATA_FIELDS = {
    "report_period_start",
    "report_period_end",
    "tax_year_candidate",
}

CLARIFYING_METADATA_FIELDS = {
    "account_or_contract_candidate",
    "broker_name_candidate",
    "client_name_candidate",
    "document_kind_candidate",
}

SOURCE_SCOPE_CONFLICT_FLAGS = {
    "source_role_conflict",
    "document_role_conflict",
    "case_scope_conflict",
    "period_scope_conflict",
    "duplicate_conflict",
}

DISPLAY_METADATA_FIELDS = {
    "document_title_candidate",
    "language_candidate",
    "created_at_candidate",
    "metadata_confirmation",
}


def gap_criticality_policy(
    *,
    gap_type: str,
    missing_metadata_fields: list[str] | None = None,
    conflict_flags: list[str] | None = None,
    reason_codes: list[str] | None = None,
    period_scope_basis: dict[str, Any] | None = None,
    refinement_enabled: bool,
) -> dict[str, Any]:
    if not refinement_enabled:
        if gap_type == "outside_scope_confirmation":
            return _policy(
                criticality="non_critical",
                blocking_scope="audit_only",
                blocks_gate2=False,
                resolution_required=False,
                can_proceed_with_warning=True,
                ask_policy="defer",
                answer_impact="adds_audit_context",
                priority="low",
                severity="optional",
                reason_codes=["legacy_outside_scope_confirmation_optional"],
                safe_explanation="The document is already excluded from Gate 2; confirmation is audit-only.",
            )
        return _policy(
            criticality="critical",
            blocking_scope="gate2_handoff",
            blocks_gate2=True,
            resolution_required=True,
            can_proceed_with_warning=False,
            ask_policy="ask_now",
            answer_impact="unblocks_gate2",
            priority="high",
            severity="blocking",
            reason_codes=["legacy_metadata_gap_blocks_gate2"],
            safe_explanation="Legacy mode treats this metadata gap as blocking for Gate 2.",
        )

    fields = {str(item) for item in missing_metadata_fields or [] if item}
    conflicts = {str(item) for item in conflict_flags or [] if item}
    reasons = {str(item) for item in reason_codes or [] if item}
    period_basis = period_scope_basis or _period_scope_basis_from_reason_codes(reasons)

    if gap_type == "duplicate_canonical_choice":
        return _policy(
            criticality="critical",
            blocking_scope="gate2_handoff",
            dependency_stage="gate2_handoff",
            blocking_reason_category="duplicate_risk",
            auto_resolution_policy="none",
            blocks_gate2=True,
            resolution_required=True,
            can_proceed_with_warning=False,
            ask_policy="ask_now",
            answer_impact="unblocks_gate2",
            priority="high",
            severity="blocking",
            reason_codes=["semantic_duplicate_requires_user_choice", "duplicate_can_double_count_source_facts"],
            safe_explanation="A single canonical source document is required so duplicate facts are not handed to Gate 2.",
        )
    if gap_type == "missing_period":
        period_classification = _period_gap_classification(period_basis)
        if period_classification == "non_critical":
            return _policy(
                criticality="non_critical",
                blocking_scope="declaration_model",
                dependency_stage="declaration_model",
                blocking_reason_category="declaration_context",
                auto_resolution_policy="case_context_allows_warning",
                blocks_gate2=False,
                resolution_required=False,
                can_proceed_with_warning=True,
                ask_policy="defer",
                answer_impact="adds_audit_context",
                priority="low",
                severity="optional",
                reason_codes=sorted(
                    set(period_basis.get("reason_codes") or [])
                    | {"period_deferred_to_declaration_context", "document_period_missing_but_not_blocking"}
                ),
                safe_explanation=(
                    "The document/report period is useful for declaration or output review, but existing "
                    "case/source scope is enough for Gate 2 handoff."
                ),
            )
        if period_classification == "clarifying":
            auto_policy = (
                "defer_to_gate2_dates"
                if period_basis.get("operation_date_evidence_available") is True
                else "case_context_allows_warning"
            )
            dependency_stage = (
                "gate2_source_fact_extraction"
                if period_basis.get("operation_date_evidence_available") is True
                else "declaration_model"
            )
            return _policy(
                criticality="clarifying",
                blocking_scope="declaration_model",
                dependency_stage=dependency_stage,
                blocking_reason_category="declaration_context",
                auto_resolution_policy=auto_policy,
                blocks_gate2=False,
                resolution_required=False,
                can_proceed_with_warning=True,
                ask_policy="ask_if_user_available",
                answer_impact="improves_confidence",
                priority="medium",
                severity="important",
                reason_codes=sorted(
                    set(period_basis.get("reason_codes") or [])
                    | {"document_period_missing_but_not_blocking"}
                ),
                safe_explanation=(
                    "The document/report period should be clarified, but Gate 2 can receive safe source "
                    "references because deterministic case scope or later operation-date validation exists."
                ),
            )
        return _policy(
            criticality="critical",
            blocking_scope="gate2_handoff",
            dependency_stage="gate2_handoff",
            blocking_reason_category="source_scope",
            auto_resolution_policy="none",
            blocks_gate2=True,
            resolution_required=True,
            can_proceed_with_warning=False,
            ask_policy="ask_now",
            answer_impact="unblocks_gate2",
            priority="high",
            severity="blocking",
            reason_codes=["period_required_for_gate2_scope"],
            safe_explanation="The report period is required before safe Gate 2 source handoff can start.",
        )
    if gap_type == "unclear_document_role":
        return _policy(
            criticality="critical",
            blocking_scope="source_eligibility",
            dependency_stage="normalization",
            blocking_reason_category="role_ambiguity",
            auto_resolution_policy="none",
            blocks_gate2=True,
            resolution_required=True,
            can_proceed_with_warning=False,
            ask_policy="ask_now",
            answer_impact="unblocks_gate2",
            priority="high",
            severity="blocking",
            reason_codes=["document_role_required_before_source_eligibility"],
            safe_explanation="The document role is required before source eligibility can be decided safely.",
        )
    if gap_type == "missing_account_or_contract":
        return _policy(
            criticality="clarifying",
            blocking_scope="declaration_model",
            dependency_stage="declaration_model",
            blocking_reason_category="declaration_context",
            auto_resolution_policy="none",
            blocks_gate2=False,
            resolution_required=False,
            can_proceed_with_warning=True,
            ask_policy="ask_if_user_available",
            answer_impact="improves_confidence",
            priority="medium",
            severity="important",
            reason_codes=["account_contract_improves_audit_not_gate2_source_fact_readiness"],
            safe_explanation=(
                "The account or contract improves audit and declaration context, but does not block Gate 2 "
                "when source-role evidence is sufficient."
            ),
        )
    if gap_type == "missing_broker_client_metadata":
        return _policy(
            criticality="clarifying",
            blocking_scope="audit_only",
            dependency_stage="audit_only",
            blocking_reason_category="audit_quality",
            auto_resolution_policy="none",
            blocks_gate2=False,
            resolution_required=False,
            can_proceed_with_warning=True,
            ask_policy="ask_if_user_available",
            answer_impact="improves_confidence",
            priority="medium",
            severity="important",
            reason_codes=["broker_client_metadata_improves_audit_quality"],
            safe_explanation=(
                "Broker, client, or document-kind metadata improves audit quality, but does not block Gate 2 "
                "when source-role evidence is sufficient."
            ),
        )
    if gap_type == "outside_scope_confirmation":
        ask_policy = "ask_if_user_available" if "outside_scope_confirmation_required" in reasons else "do_not_ask"
        return _policy(
            criticality="non_critical",
            blocking_scope="audit_only",
            dependency_stage="audit_only",
            blocking_reason_category="audit_quality",
            auto_resolution_policy="none",
            blocks_gate2=False,
            resolution_required=False,
            can_proceed_with_warning=True,
            ask_policy=ask_policy,
            answer_impact="specialist_note_only",
            priority="low",
            severity="optional",
            reason_codes=["outside_scope_document_excluded_from_gate2"],
            safe_explanation=(
                "The document is outside the case scope and excluded from Gate 2; ask only when explicit "
                "confirmation was requested."
            ),
        )
    if gap_type == "other_metadata_conflict":
        if conflicts & SOURCE_SCOPE_CONFLICT_FLAGS:
            return _policy(
                criticality="critical",
                blocking_scope="gate2_handoff",
                dependency_stage="gate2_handoff",
                blocking_reason_category="source_scope",
                auto_resolution_policy="none",
                blocks_gate2=True,
                resolution_required=True,
                can_proceed_with_warning=False,
                ask_policy="ask_now",
                answer_impact="unblocks_gate2",
                priority="high",
                severity="blocking",
                reason_codes=["source_scope_metadata_conflict_blocks_gate2"],
                safe_explanation="This metadata conflict can change source scope or duplicate handling before Gate 2 handoff.",
            )
        if fields & {"broker_name_candidate", "client_name_candidate", "account_or_contract_candidate"}:
            return _policy(
                criticality="clarifying",
                blocking_scope="declaration_model",
                dependency_stage="declaration_model",
                blocking_reason_category="declaration_context",
                auto_resolution_policy="none",
                blocks_gate2=False,
                resolution_required=False,
                can_proceed_with_warning=True,
                ask_policy="ask_if_user_available",
                answer_impact="improves_confidence",
                priority="medium",
                severity="important",
                reason_codes=["broker_client_account_confidence_improvement"],
                safe_explanation="This metadata improves broker/client/account confidence, but does not block Gate 2 source handoff.",
            )
        if fields == {"metadata_confirmation"} and not conflicts:
            return _policy(
                criticality="non_critical",
                blocking_scope="audit_only",
                dependency_stage="audit_only",
                blocking_reason_category="display_metadata",
                auto_resolution_policy="none",
                blocks_gate2=False,
                resolution_required=False,
                can_proceed_with_warning=True,
                ask_policy="defer",
                answer_impact="adds_audit_context",
                priority="low",
                severity="optional",
                reason_codes=["metadata_confirmation_deferred"],
                safe_explanation="General metadata confirmation can be deferred when no critical gap remains.",
            )
        if fields and fields <= DISPLAY_METADATA_FIELDS and not conflicts:
            return _policy(
                criticality="non_critical",
                blocking_scope="audit_only",
                dependency_stage="audit_only",
                blocking_reason_category="display_metadata",
                auto_resolution_policy="none",
                blocks_gate2=False,
                resolution_required=False,
                can_proceed_with_warning=True,
                ask_policy="defer",
                answer_impact="adds_audit_context",
                priority="low",
                severity="optional",
                reason_codes=["display_metadata_deferred"],
                safe_explanation="Display metadata can be deferred because it does not change Gate 2 source eligibility.",
            )
        return _policy(
            criticality="clarifying",
            blocking_scope="audit_only",
            dependency_stage="audit_only",
            blocking_reason_category="audit_quality",
            auto_resolution_policy="none",
            blocks_gate2=False,
            resolution_required=False,
            can_proceed_with_warning=True,
            ask_policy="ask_if_user_available",
            answer_impact="adds_audit_context",
            priority="medium",
            severity="important",
            reason_codes=["metadata_conflict_requires_audit_note_not_gate2_blocker"],
            safe_explanation="A metadata conflict needs an audit note, but does not let the LLM decide Gate 2 blocking.",
        )
    return _policy(
        criticality="clarifying",
        blocking_scope="audit_only",
        dependency_stage="audit_only",
        blocking_reason_category="audit_quality",
        auto_resolution_policy="none",
        blocks_gate2=False,
        resolution_required=False,
        can_proceed_with_warning=True,
        ask_policy="ask_if_user_available",
        answer_impact="adds_audit_context",
        priority="medium",
        severity="important",
        reason_codes=["metadata_gap_default_clarifying"],
        safe_explanation="The clarification is useful for audit quality, but is not a standalone Gate 2 blocker.",
    )


def criticality_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("criticality") or "unknown") for item in items)
    for key in CRITICALITIES:
        counts.setdefault(key, 0)
    return dict(sorted(counts.items()))


def unresolved_metadata_field_groups(
    *,
    missing_fields: list[str],
    conflict_flags: list[str],
    source_confidence_low: bool,
    review_required_without_fields: bool,
    period_scope_basis: dict[str, Any] | None = None,
    refinement_enabled: bool,
) -> dict[str, set[str]]:
    fields = {str(item) for item in missing_fields if item}
    conflicts = {str(item) for item in conflict_flags if item}
    if not refinement_enabled:
        return {
            "critical": set(fields | conflicts | ({"metadata_confirmation"} if review_required_without_fields else set())),
            "clarifying": set(),
            "non_critical": set(),
        }

    critical = {field for field in fields if field in CRITICAL_METADATA_FIELDS}
    clarifying = {field for field in fields if field in CLARIFYING_METADATA_FIELDS}
    other = fields - critical - clarifying
    period_fields = fields & PERIOD_METADATA_FIELDS
    period_classification = _period_gap_classification(period_scope_basis or {})
    if period_fields and period_classification in {"clarifying", "non_critical"}:
        critical.difference_update(period_fields)
        other.difference_update(period_fields)
        if period_classification == "clarifying":
            clarifying.update(period_fields)
        else:
            other.update(period_fields)
    if source_confidence_low:
        critical.add("document_role")
    if conflicts & SOURCE_SCOPE_CONFLICT_FLAGS:
        critical.update(conflicts & SOURCE_SCOPE_CONFLICT_FLAGS)
    if conflicts - SOURCE_SCOPE_CONFLICT_FLAGS:
        clarifying.update(conflicts - SOURCE_SCOPE_CONFLICT_FLAGS)
    non_critical = set(other)
    if review_required_without_fields and not critical and not clarifying:
        non_critical.add("metadata_confirmation")
    return {
        "critical": critical,
        "clarifying": clarifying,
        "non_critical": non_critical,
    }


def _policy(
    *,
    criticality: str,
    blocking_scope: str,
    blocks_gate2: bool,
    resolution_required: bool,
    can_proceed_with_warning: bool,
    ask_policy: str,
    answer_impact: str,
    priority: str,
    severity: str,
    reason_codes: list[str],
    safe_explanation: str,
    dependency_stage: str | None = None,
    blocking_reason_category: str | None = None,
    auto_resolution_policy: str = "none",
) -> dict[str, Any]:
    if dependency_stage not in DEPENDENCY_STAGES:
        dependency_stage = {
            "gate2_handoff": "gate2_handoff",
            "source_eligibility": "normalization",
            "declaration_model": "declaration_model",
            "audit_only": "audit_only",
        }.get(blocking_scope, "audit_only")
    if blocking_reason_category not in BLOCKING_REASON_CATEGORIES:
        blocking_reason_category = "source_scope" if blocks_gate2 else "audit_quality"
    if auto_resolution_policy not in AUTO_RESOLUTION_POLICIES:
        auto_resolution_policy = "none"
    return {
        "criticality": criticality,
        "blocking_scope": blocking_scope,
        "dependency_stage": dependency_stage,
        "blocking_reason_category": blocking_reason_category,
        "auto_resolution_policy": auto_resolution_policy,
        "blocks_gate2": bool(blocks_gate2),
        "resolution_required": bool(resolution_required),
        "can_proceed_with_warning": bool(can_proceed_with_warning),
        "ask_policy": ask_policy,
        "answer_impact": answer_impact,
        "priority": priority,
        "severity": severity,
        "criticality_reason_codes": list(reason_codes),
        "safe_explanation": safe_explanation,
    }


def _period_scope_basis_from_reason_codes(reasons: set[str]) -> dict[str, Any]:
    return {
        "case_tax_year_known": "case_tax_year_provides_scope" in reasons,
        "case_scope_known": "case_context_provides_scope" in reasons,
        "broker_provider_known": "broker_provider_provides_scope" in reasons,
        "operation_date_evidence_available": "source_table_dates_available" in reasons,
        "declaration_or_output_period_only": "period_deferred_to_declaration_context" in reasons,
        "reason_codes": sorted(reasons & {
            "period_required_for_gate2_scope",
            "period_deferred_to_gate2_operation_dates",
            "period_deferred_to_declaration_context",
            "case_tax_year_provides_scope",
            "case_context_provides_scope",
            "broker_provider_provides_scope",
            "source_table_dates_available",
            "document_period_missing_but_not_blocking",
        }),
    }


def _period_gap_classification(period_scope_basis: dict[str, Any]) -> str:
    if period_scope_basis.get("declaration_or_output_period_only") is True:
        return "non_critical"
    if any(
        period_scope_basis.get(key) is True
        for key in (
            "case_tax_year_known",
            "case_scope_known",
            "broker_provider_known",
            "source_role_evidence_available",
            "operation_date_evidence_available",
        )
    ):
        return "clarifying"
    return "critical"
