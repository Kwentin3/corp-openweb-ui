from __future__ import annotations

import re

from .blockers import corrupt_file, encrypted_file, raster_requires_review
from .contracts import profile_id, slice_id


def profile_pdf(run_id: str, document_id: str, content_bytes: bytes) -> tuple[dict, list[dict], list[dict]]:
    current_profile_id = profile_id(document_id)
    blockers = []
    if not content_bytes.startswith(b"%PDF-"):
        blocker = corrupt_file(run_id, document_id, "pdf_header_missing")
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]

    if b"/Encrypt" in content_bytes[:4096] or b"/Encrypt" in content_bytes:
        blocker = encrypted_file(run_id, document_id)
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]

    if b"%%EOF" not in content_bytes[-2048:]:
        blockers.append(corrupt_file(run_id, document_id, "pdf_eof_missing"))

    pages_count = len(re.findall(rb"/Type\s*/Page(?!s)", content_bytes))
    text_chunks = _extract_text_chunks(content_bytes)
    text = "\n".join(text_chunks)
    text_layer = "yes" if text.strip() else ("unknown" if pages_count == 0 else "no")
    image_markers = len(re.findall(rb"/Subtype\s*/Image", content_bytes))
    raster_likelihood = _raster_likelihood(text_layer=text_layer, image_markers=image_markers)
    table_likelihood = _table_likelihood(text)
    private_slices = []
    normalized_slice_refs = []

    if text.strip():
        snippet = text[:2000]
        private_slice = {
            "slice_id": slice_id(document_id, "pdf_text_001"),
            "document_id": document_id,
            "profile_id": current_profile_id,
            "slice_type": "text_excerpt",
            "source_location": {
                "kind": "pdf_pages",
                "page_start": 1,
                "page_end": min(max(pages_count, 1), 3),
            },
            "location": {
                "kind": "pdf_pages",
                "page_start": 1,
                "page_end": min(max(pages_count, 1), 3),
            },
            "bounded": True,
            "characters_in_slice": len(snippet),
            "chars_count": len(snippet),
            "truncated": len(text) > len(snippet),
            "parser": "python_stdlib_pdf_heuristic",
            "created_for_gate": "gate1",
            "text": snippet,
        }
        private_slices.append(private_slice)
        normalized_slice_refs.append(private_slice["slice_id"])

    if pages_count and text_layer != "yes":
        blockers.append(raster_requires_review(run_id, document_id))

    profile = {
        "profile_id": current_profile_id,
        "document_id": document_id,
        "container_format": "pdf",
        "parser": "python_stdlib_pdf_heuristic",
        "parser_version": "1",
        "profile_status": "profiled_with_review" if blockers else "profiled",
        "machine_readable": "conditional" if text_layer == "yes" else "unknown",
        "machine_readable_table": False,
        "pages_count": pages_count,
        "text_layer": text_layer,
        "has_text_layer": text_layer == "yes",
        "raster_or_scan_likelihood": raster_likelihood,
        "table_likelihood": table_likelihood,
        "image_markers_count": image_markers,
        "ocr_performed": False,
        "normalized_slice_refs": normalized_slice_refs,
        "warnings": ["raster_or_scan_review_required"] if any(item["code"] == "raster_requires_ocr_or_review" for item in blockers) else [],
        "blocker_refs": [item["blocker_id"] for item in blockers],
    }
    return profile, private_slices, blockers


def _extract_text_chunks(content_bytes: bytes) -> list[str]:
    chunks = []
    for match in re.finditer(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", content_bytes):
        decoded = _decode_pdf_literal(match.group(1))
        if decoded:
            chunks.append(decoded)
    for array_match in re.finditer(rb"\[((?:.|\n){0,2000}?)\]\s*TJ", content_bytes):
        for literal in re.finditer(rb"\(((?:\\.|[^\\)])*)\)", array_match.group(1)):
            decoded = _decode_pdf_literal(literal.group(1))
            if decoded:
                chunks.append(decoded)
    return chunks[:50]


def _decode_pdf_literal(value: bytes) -> str:
    value = (
        value.replace(rb"\(", b"(")
        .replace(rb"\)", b")")
        .replace(rb"\\", b"\\")
        .replace(rb"\n", b"\n")
        .replace(rb"\r", b"\r")
        .replace(rb"\t", b"\t")
    )
    for encoding in ("utf-8", "latin-1"):
        try:
            return value.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return ""


def _raster_likelihood(*, text_layer: str, image_markers: int) -> str:
    if text_layer == "yes":
        return "low"
    if image_markers:
        return "high"
    return "medium"


def _table_likelihood(text: str) -> str:
    if not text:
        return "unknown"
    lines = [line for line in text.splitlines() if line.strip()]
    tableish = sum(1 for line in lines if "," in line or "\t" in line or len(re.findall(r"\d+", line)) >= 2)
    return "weak" if tableish >= 2 else "none"


def _blocked_profile(document_id: str, blocker_refs: list[str]) -> dict:
    return {
        "profile_id": profile_id(document_id),
        "document_id": document_id,
        "container_format": "pdf",
        "parser": "python_stdlib_pdf_heuristic",
        "parser_version": "1",
        "profile_status": "blocked",
        "machine_readable": "unknown",
        "machine_readable_table": False,
        "pages_count": 0,
        "text_layer": "unknown",
        "has_text_layer": False,
        "raster_or_scan_likelihood": "unknown",
        "table_likelihood": "unknown",
        "ocr_performed": False,
        "normalized_slice_refs": [],
        "warnings": ["parser_failed"],
        "blocker_refs": blocker_refs,
    }
