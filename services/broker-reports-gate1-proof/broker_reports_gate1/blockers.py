from __future__ import annotations

from .contracts import make_blocker


def no_files(run_id: str) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=None,
        code="no_files",
        created_by_step="intake_request",
        safe_message="No uploaded files were visible to Gate 1.",
        review_action="attach_files_and_retry",
    )


def bytes_unavailable(run_id: str, document_id: str, reason: str | None) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="bytes_unavailable",
        created_by_step="byte_access",
        safe_message="Original bytes were unavailable inside the approved Gate 1 boundary.",
        review_action="verify_upload_storage_or_retry",
        reason=reason,
    )


def unsupported_format(run_id: str, document_id: str) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="unsupported_format",
        created_by_step="container_detection",
        safe_message="The document container is not supported by this Gate 1 proof slice.",
        review_action="request_supported_replacement_or_manual_review",
    )


def duplicate_review(run_id: str, document_id: str) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="duplicate_review",
        severity="warning",
        blocks_next_gate=False,
        created_by_step="deduplication",
        safe_message="Duplicate content hash detected; review whether both documents are needed.",
        review_action="review_duplicate",
    )


def parser_failed(run_id: str, document_id: str, reason: str) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="parser_failed",
        created_by_step="technical_profiling",
        safe_message="The technical profiler could not safely parse this document.",
        review_action="manual_review_or_retry_with_supported_file",
        reason=reason,
    )


def corrupt_file(run_id: str, document_id: str, reason: str) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="corrupt_file",
        created_by_step="technical_profiling",
        safe_message="The document appears corrupt or structurally invalid.",
        review_action="request_clean_replacement",
        reason=reason,
    )


def encrypted_file(run_id: str, document_id: str) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="encrypted_file",
        created_by_step="technical_profiling",
        safe_message="The document contains encrypted content and requires review.",
        review_action="request_unencrypted_replacement_or_credential_workflow",
    )


def raster_requires_review(run_id: str, document_id: str) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="raster_requires_ocr_or_review",
        created_by_step="technical_profiling",
        safe_message="The document appears raster-only and requires OCR or manual review.",
        review_action="manual_review_or_future_ocr_gate",
    )


def zip_requires_review(run_id: str, document_id: str) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="zip_requires_review",
        severity="warning",
        blocks_next_gate=False,
        created_by_step="zip_inventory",
        safe_message="ZIP contents were inventoried but require operator review before use.",
        review_action="review_zip_member_inventory",
    )


def unknown_role(run_id: str, document_id: str) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="unknown_role",
        severity="warning",
        blocks_next_gate=False,
        created_by_step="taxonomy",
        safe_message="Document role could not be determined by safe Gate 1 rules.",
        review_action="classify_document_role_manually",
    )


def llm_passport_prompt_unavailable(run_id: str, document_id: str | None, reason: str | None) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="llm_passport_prompt_unavailable",
        severity="warning",
        blocks_next_gate=False,
        created_by_step="document_metadata_passport_prompt_resolver",
        safe_message="Document metadata passport prompt was unavailable or failed contract checks.",
        review_action="fix_managed_prompt_or_continue_without_passport",
        reason=reason,
    )


def llm_passport_model_failed(run_id: str, document_id: str, reason: str | None) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="llm_passport_model_failed",
        severity="warning",
        blocks_next_gate=False,
        created_by_step="document_metadata_passport_model_call",
        safe_message="Document metadata passport model call failed.",
        review_action="retry_passport_stage_or_route_metadata_review",
        reason=reason,
    )


def llm_passport_validation_failed(run_id: str, document_id: str, reason: str | None) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=document_id,
        code="llm_passport_validation_failed",
        severity="warning",
        blocks_next_gate=False,
        created_by_step="document_metadata_passport_validator",
        safe_message="Document metadata passport output did not pass validation.",
        review_action="route_document_to_metadata_review",
        reason=reason,
    )


def privacy_violation(run_id: str, reason: str | None = None) -> dict:
    return make_blocker(
        run_id=run_id,
        document_id=None,
        code="privacy_violation",
        created_by_step="chat_visible_report_validation",
        safe_message="Private marker was detected before chat report publication.",
        review_action="fix_safe_projection",
        reason=reason,
    )
