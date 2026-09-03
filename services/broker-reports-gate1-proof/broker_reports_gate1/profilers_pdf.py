from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .blockers import corrupt_file, encrypted_file
from .contracts import profile_id


PDF_PREFLIGHT_POLICY_VERSION = "broker_reports_pdf_preflight_v1"


def profile_pdf(
    run_id: str,
    document_id: str,
    content_bytes: bytes,
) -> tuple[dict, list[dict], list[dict]]:
    """Validate PDF structure, encryption and page count without extracting content."""
    current_profile_id = profile_id(document_id)
    if not content_bytes.startswith(b"%PDF"):
        blocker = corrupt_file(run_id, document_id, "pdf_header_missing")
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]

    try:
        reader = PdfReader(io.BytesIO(content_bytes), strict=False)
        if reader.is_encrypted:
            blocker = encrypted_file(run_id, document_id)
            return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]
        pages_count = len(reader.pages)
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        blocker = corrupt_file(run_id, document_id, type(exc).__name__)
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]

    if pages_count < 1:
        blocker = corrupt_file(run_id, document_id, "pdf_has_no_pages")
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]

    profile = {
        "profile_id": current_profile_id,
        "document_id": document_id,
        "container_format": "pdf",
        "parser": "pypdf_preflight_only",
        "parser_version": PDF_PREFLIGHT_POLICY_VERSION,
        "profile_status": "preflight_passed",
        "machine_readable": "conditional",
        "machine_readable_table": False,
        "pages_count": pages_count,
        "text_layer": "not_inspected",
        "has_text_layer": None,
        "raster_or_scan_likelihood": "not_inspected",
        "pdf_content_kind": "not_inspected",
        "table_likelihood": "not_inspected",
        "image_markers_count": None,
        "text_chunks_count": 0,
        "extracted_text_chars": 0,
        "ocr_performed": False,
        "content_extraction_performed": False,
        "normalized_slice_refs": [],
        "warnings": [],
        "blocker_refs": [],
    }
    return profile, [], []


def _blocked_profile(document_id: str, blocker_refs: list[str]) -> dict:
    return {
        "profile_id": profile_id(document_id),
        "document_id": document_id,
        "container_format": "pdf",
        "parser": "pypdf_preflight_only",
        "parser_version": PDF_PREFLIGHT_POLICY_VERSION,
        "profile_status": "blocked",
        "machine_readable": "unknown",
        "machine_readable_table": False,
        "pages_count": 0,
        "text_layer": "not_inspected",
        "has_text_layer": None,
        "raster_or_scan_likelihood": "not_inspected",
        "table_likelihood": "not_inspected",
        "ocr_performed": False,
        "content_extraction_performed": False,
        "normalized_slice_refs": [],
        "warnings": ["preflight_failed"],
        "blocker_refs": blocker_refs,
    }
