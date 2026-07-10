from __future__ import annotations

from .contracts import METHODOLOGY_OR_OUTPUT_CLASSES, SOURCE_DOCUMENT_CLASSES, taxonomy_candidate_id

SUPPORTED_CLASSES = {
    "operations_table",
    "source_broker_report",
    "dividends_report",
    "fees_report",
    "withholding_report",
    "currency_rate_table",
    "calculation_template",
    "tax_base_calculation",
    "explanation_template",
    "official_form",
    "archive_package",
    "image_or_scan_requires_review",
    "unknown_or_needs_review",
    "unsupported",
}


def classify_document(
    *,
    document: dict,
    profile: dict | None,
    private_slices: list[dict],
    blocker_codes: set[str],
    source_policy_context: dict | None = None,
    source_policy_hint: dict | None = None,
) -> dict:
    document_id = document["document_id"]
    container = document["container_format"]
    policy_context = source_policy_context if isinstance(source_policy_context, dict) else {}
    policy_hint = source_policy_hint if isinstance(source_policy_hint, dict) else {}
    candidate = "unknown_or_needs_review"
    confidence = "low"
    reason_codes = [f"container_{container}"]
    source_evidence_candidate = "conditional_after_review"
    methodology_candidate = "no"
    knowledge_after_review = "conditional"
    requires_review = True
    source_role_policy_status = "not_applicable"
    source_role_policy_decision = "not_required"
    source_policy_review_required = False

    slice_text = _slice_text(private_slices)
    hint_role = _source_policy_hint_role(policy_hint)
    hints_allowed = _policy_allows_registry_role_hints(policy_context)
    if policy_hint and not hints_allowed:
        reason_codes.append("safe_registry_role_hint_ignored_policy_missing")
    if "unsupported_format" in blocker_codes:
        candidate = "unsupported"
        confidence = "medium"
        reason_codes.append("unsupported_or_unknown_container")
    elif hints_allowed and hint_role in METHODOLOGY_OR_OUTPUT_CLASSES:
        candidate = hint_role
        confidence = "medium"
        reason_codes.extend(["customer_approved_private_registry_role_hint", "methodology_or_output_role_hint"])
        requires_review = False if not blocker_codes else True
    elif container == "csv" and profile and profile.get("machine_readable_table") is True:
        candidate = "operations_table"
        confidence = "medium"
        reason_codes.extend(["machine_readable_table", "csv_profiled"])
        requires_review = False if not blocker_codes else True
    elif hints_allowed and hint_role in SOURCE_DOCUMENT_CLASSES:
        candidate = hint_role
        confidence = "medium"
        reason_codes.extend(["customer_approved_private_registry_role_hint", "source_role_hint"])
        requires_review = False if not blocker_codes else True
    elif container == "xlsx" and profile and profile.get("formulas_present"):
        candidate = "calculation_template"
        confidence = "medium"
        reason_codes.extend(["xlsx_profiled", "formulas_present"])
        requires_review = False if not blocker_codes else True
    elif container == "xlsx" and profile and profile.get("machine_readable_table") is True:
        candidate = "operations_table"
        confidence = "low"
        reason_codes.extend(["xlsx_profiled", "table_like_ranges"])
    elif container in {"txt", "html_text", "pdf", "docx"} and _has_broker_report_signal(slice_text):
        candidate = _textual_candidate(slice_text)
        confidence = "medium"
        reason_codes.extend([f"{container}_profiled", "broker_report_text_signal"])
        requires_review = False if not blocker_codes else True
    elif container == "zip":
        candidate = "archive_package"
        confidence = "medium"
        reason_codes.append("zip_container_requires_review")
    elif container == "image":
        candidate = "image_or_scan_requires_review"
        confidence = "medium"
        reason_codes.append("image_requires_review")

    if candidate not in SUPPORTED_CLASSES:
        candidate = "unknown_or_needs_review"

    pdf_html_evidence = _has_pdf_html_parse_evidence(
        container=container,
        profile=profile,
        slice_text=slice_text,
        blocker_codes=blocker_codes,
    )
    if _requires_source_policy_review(
        container=container,
        profile=profile,
        candidate=candidate,
        pdf_html_evidence=pdf_html_evidence,
        policy_context=policy_context,
    ):
        if _policy_accepts_pdf_html_source_roles(policy_context):
            source_role_policy_status = "approved"
            source_role_policy_decision = "approved_for_gate2_source_role"
            reason_codes.append("pdf_html_source_role_policy_approved")
        else:
            source_role_policy_status = "context_issue"
            source_role_policy_decision = "carried_forward_for_downstream_issue_context"
            requires_review = True
            reason_codes.extend([
                "pdf_html_source_role_policy_carried_forward",
                "pdf_html_source_role_not_auto_finalized",
            ])
            if container == "pdf":
                reason_codes.append("pdf_text_layer_source_policy_context")
            elif container == "html_text":
                reason_codes.append("html_table_or_text_source_policy_context")

    if candidate in SOURCE_DOCUMENT_CLASSES:
        source_evidence_candidate = (
            "yes_with_issue_context"
            if source_role_policy_status == "context_issue"
            else "yes"
        )
    elif candidate in METHODOLOGY_OR_OUTPUT_CLASSES:
        methodology_candidate = "yes"
        source_evidence_candidate = "no"
        knowledge_after_review = "conditional"

    return {
        "taxonomy_candidate_id": taxonomy_candidate_id(document_id),
        "document_id": document_id,
        "schema_version": "taxonomy_candidates_v0",
        "document_class_candidate": candidate,
        "primary_class": candidate,
        "alternative_classes": [],
        "confidence": confidence,
        "safe_reason_codes": reason_codes,
        "classifier_type": "rules",
        "can_be_source_evidence": source_evidence_candidate,
        "can_be_methodology": methodology_candidate,
        "can_be_loaded_to_knowledge": knowledge_after_review,
        "declaration_relevance": "not_evaluated_in_gate1",
        "source_evidence_candidate": source_evidence_candidate,
        "methodology_candidate": methodology_candidate,
        "knowledge_after_review": knowledge_after_review,
        "requires_review": requires_review,
        "source_role_policy_status": source_role_policy_status,
        "source_role_policy_decision": source_role_policy_decision,
        "source_policy_review_required": source_policy_review_required,
    }


def _slice_text(private_slices: list[dict]) -> str:
    parts = []
    for item in private_slices:
        if item.get("text"):
            parts.append(str(item.get("text")))
        for row in item.get("cells") or item.get("rows") or []:
            if isinstance(row, list):
                parts.append(" ".join(str(cell or "") for cell in row))
    return "\n".join(parts).lower()


def _has_broker_report_signal(text: str) -> bool:
    compact = " ".join(text.lower().split())
    strong_signals = {
        "broker",
        "account",
        "synthetic broker",
        "interactive brokers",
        "ibkr",
        "activity statement",
        "brokerage statement",
        "portfolio analyst",
        "trade confirmation",
    }
    if any(signal in compact for signal in strong_signals):
        return True
    table_source_signals = {
        "dividend",
        "withholding",
        "commission",
        "fee",
        "fees",
        "currency",
        "forex",
        "realized",
        "transaction",
        "transactions",
        "symbol",
        "isin",
        "cusip",
        "quantity",
        "proceeds",
        "basis",
    }
    return sum(1 for signal in table_source_signals if signal in compact) >= 2


def _textual_candidate(text: str) -> str:
    if "dividend" in text:
        return "dividends_report"
    if "fee" in text or "commission" in text:
        return "fees_report"
    if "withholding" in text:
        return "withholding_report"
    if "official form" in text:
        return "official_form"
    if "template" in text:
        return "explanation_template"
    return "source_broker_report"


def _source_policy_hint_role(source_policy_hint: dict) -> str:
    value = source_policy_hint.get("document_role_candidate")
    return str(value or "")


def _policy_allows_registry_role_hints(source_policy_context: dict) -> bool:
    explicit = source_policy_context.get("explicit") is True
    mode = str(source_policy_context.get("mode") or "")
    hints_allowed = source_policy_context.get("source_registry_role_hints_allowed")
    return (
        explicit
        and mode in {"customer_approved_private_registry", "customer_approved_test"}
        and hints_allowed is not False
    )


def _policy_accepts_pdf_html_source_roles(source_policy_context: dict) -> bool:
    if source_policy_context.get("explicit") is not True:
        return False
    if source_policy_context.get("accept_pdf_html_source_roles") is True:
        return True
    return str(source_policy_context.get("pdf_html_source_policy") or "") in {
        "approved",
        "accepted",
        "approve_safe_registry_roles",
        "accepted_safe_registry_roles",
    }


def _requires_source_policy_review(
    *,
    container: str,
    profile: dict | None,
    candidate: str,
    pdf_html_evidence: bool,
    policy_context: dict,
) -> bool:
    if container not in {"pdf", "html_text"}:
        return False
    if not pdf_html_evidence:
        return False
    if candidate in METHODOLOGY_OR_OUTPUT_CLASSES or candidate in {"unsupported", "image_or_scan_requires_review"}:
        return False
    if candidate in SOURCE_DOCUMENT_CLASSES or candidate == "unknown_or_needs_review":
        return True
    return profile is not None and bool(policy_context or profile)


def _has_pdf_html_parse_evidence(
    *,
    container: str,
    profile: dict | None,
    slice_text: str,
    blocker_codes: set[str],
) -> bool:
    if "raster_requires_ocr_or_review" in blocker_codes:
        return False
    if container == "pdf":
        if not profile:
            return False
        return (
            profile.get("has_text_layer") is True
            or profile.get("text_layer") == "yes"
            or str(profile.get("pdf_content_kind") or "") in {"text_layer_pdf", "mixed_pdf_with_text"}
        )
    if container == "html_text":
        if profile and (
            profile.get("machine_readable_table") is True
            or int(profile.get("html_table_count") or 0) > 0
            or profile.get("clean_text_available") is True
        ):
            return True
        return bool(slice_text.strip())
    return False
