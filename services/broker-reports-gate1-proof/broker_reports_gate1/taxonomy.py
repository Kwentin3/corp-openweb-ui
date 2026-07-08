from __future__ import annotations

from .contracts import taxonomy_candidate_id

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
) -> dict:
    document_id = document["document_id"]
    container = document["container_format"]
    candidate = "unknown_or_needs_review"
    confidence = "low"
    reason_codes = [f"container_{container}"]
    source_evidence_candidate = "conditional_after_review"
    methodology_candidate = "no"
    knowledge_after_review = "conditional"
    requires_review = True

    slice_text = _slice_text(private_slices)
    if "unsupported_format" in blocker_codes:
        candidate = "unsupported"
        confidence = "medium"
        reason_codes.append("unsupported_or_unknown_container")
    elif container == "csv" and profile and profile.get("machine_readable_table") is True:
        candidate = "operations_table"
        confidence = "medium"
        reason_codes.extend(["machine_readable_table", "csv_profiled"])
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
    return "broker" in text or "account" in text or "synthetic broker" in text


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
