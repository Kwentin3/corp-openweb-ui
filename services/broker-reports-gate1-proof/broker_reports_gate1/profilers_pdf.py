from __future__ import annotations

import binascii
import re
import zlib

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
    text_chunks, text_evidence = _extract_text_chunks(content_bytes)
    text = "\n".join(text_chunks)
    text_layer = (
        "yes"
        if text.strip() or text_evidence["text_operator_streams_count"] > 0
        else ("unknown" if pages_count == 0 else "no")
    )
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

    warnings = []
    if any(item["code"] == "raster_requires_ocr_or_review" for item in blockers):
        warnings.append("raster_or_scan_review_required")
    if text_layer == "yes" and not text.strip():
        warnings.append("text_layer_detected_but_text_not_extracted")

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
        "pdf_content_kind": _pdf_content_kind(text_layer=text_layer, image_markers=image_markers),
        "table_likelihood": table_likelihood,
        "image_markers_count": image_markers,
        "text_chunks_count": len(text_chunks),
        "extracted_text_chars": len(text),
        "raw_text_chunks_count": text_evidence["raw_text_chunks_count"],
        "decoded_streams_count": text_evidence["decoded_streams_count"],
        "flate_streams_decoded_count": text_evidence["flate_streams_decoded_count"],
        "flate_stream_decode_failed_count": text_evidence["flate_stream_decode_failed_count"],
        "text_operator_streams_count": text_evidence["text_operator_streams_count"],
        "hex_text_chunks_count": text_evidence["hex_text_chunks_count"],
        "ocr_performed": False,
        "normalized_slice_refs": normalized_slice_refs,
        "warnings": warnings,
        "blocker_refs": [item["blocker_id"] for item in blockers],
    }
    return profile, private_slices, blockers


def _extract_text_chunks(content_bytes: bytes) -> tuple[list[str], dict[str, int]]:
    chunks: list[str] = []
    evidence = {
        "raw_text_chunks_count": 0,
        "decoded_streams_count": 0,
        "flate_streams_decoded_count": 0,
        "flate_stream_decode_failed_count": 0,
        "text_operator_streams_count": 0,
        "hex_text_chunks_count": 0,
    }
    _extend_chunks(chunks, _extract_text_from_pdf_operators(content_bytes, evidence=evidence))
    evidence["raw_text_chunks_count"] = len(chunks)

    for stream_payload, decoded_with_flate in _iter_pdf_stream_payloads(content_bytes):
        evidence["decoded_streams_count"] += 1
        if decoded_with_flate:
            evidence["flate_streams_decoded_count"] += 1
        if _has_text_showing_operator(stream_payload):
            evidence["text_operator_streams_count"] += 1
        _extend_chunks(chunks, _extract_text_from_pdf_operators(stream_payload, evidence=evidence))

    evidence["flate_stream_decode_failed_count"] = getattr(
        _iter_pdf_stream_payloads,
        "last_decode_failures",
        0,
    )
    return chunks, evidence


def _extend_chunks(target: list[str], new_chunks: list[str]) -> None:
    max_chunks = 5000
    max_chars = 100_000
    current_chars = sum(len(chunk) for chunk in target)
    for chunk in new_chunks:
        if len(target) >= max_chunks or current_chars >= max_chars:
            break
        target.append(chunk)
        current_chars += len(chunk)


def _extract_text_from_pdf_operators(content_bytes: bytes, *, evidence: dict[str, int]) -> list[str]:
    chunks = []
    for match in re.finditer(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", content_bytes):
        decoded = _decode_pdf_literal(match.group(1))
        if decoded:
            chunks.append(decoded)
    for match in re.finditer(rb"(?<!<)<([0-9A-Fa-f\s]+)>\s*Tj", content_bytes):
        decoded = _decode_pdf_hex(match.group(1))
        if decoded:
            evidence["hex_text_chunks_count"] += 1
            chunks.append(decoded)
    for array_match in re.finditer(rb"\[((?:.|\n){0,5000}?)\]\s*TJ", content_bytes):
        array_payload = array_match.group(1)
        for literal in re.finditer(rb"\(((?:\\.|[^\\)])*)\)", array_payload):
            decoded = _decode_pdf_literal(literal.group(1))
            if decoded:
                chunks.append(decoded)
        for hex_string in re.finditer(rb"(?<!<)<([0-9A-Fa-f\s]+)>", array_payload):
            decoded = _decode_pdf_hex(hex_string.group(1))
            if decoded:
                evidence["hex_text_chunks_count"] += 1
                chunks.append(decoded)
    return chunks


def _iter_pdf_stream_payloads(content_bytes: bytes):
    decode_failures = 0
    for match in re.finditer(rb"<<(?:.|\n){0,4000}?>>\s*stream\r?\n?", content_bytes):
        header = match.group(0)
        start = match.end()
        end = content_bytes.find(b"endstream", start)
        if end < 0:
            continue
        payload = content_bytes[start:end].strip(b"\r\n")
        decoded_with_flate = False
        if b"FlateDecode" in header:
            try:
                payload = _inflate(payload)
                decoded_with_flate = True
            except zlib.error:
                decode_failures += 1
                continue
        yield payload, decoded_with_flate
    _iter_pdf_stream_payloads.last_decode_failures = decode_failures


def _inflate(payload: bytes) -> bytes:
    try:
        return zlib.decompress(payload)
    except zlib.error:
        return zlib.decompress(payload, -15)


def _has_text_showing_operator(payload: bytes) -> bool:
    return b"BT" in payload and (
        b"Tj" in payload
        or b"TJ" in payload
        or re.search(rb"\s['\"]", payload) is not None
    )


def _decode_pdf_literal(value: bytes) -> str:
    value = (
        value.replace(rb"\(", b"(")
        .replace(rb"\)", b")")
        .replace(rb"\\", b"\\")
        .replace(rb"\n", b"\n")
        .replace(rb"\r", b"\r")
        .replace(rb"\t", b"\t")
    )
    if value.startswith((b"\xfe\xff", b"\xff\xfe")):
        for encoding in ("utf-16", "utf-16-be", "utf-16-le"):
            try:
                return _clean_pdf_text(value.decode(encoding)).strip()
            except UnicodeDecodeError:
                continue
    for encoding in ("utf-8", "latin-1"):
        try:
            return _clean_pdf_text(value.decode(encoding)).strip()
        except UnicodeDecodeError:
            continue
    return ""


def _decode_pdf_hex(value: bytes) -> str:
    compact = re.sub(rb"\s+", b"", value)
    if len(compact) % 2:
        return ""
    try:
        raw = binascii.unhexlify(compact)
    except (binascii.Error, ValueError):
        return ""

    encodings = []
    if raw.startswith((b"\xfe\xff", b"\xff\xfe")):
        encodings.extend(["utf-16", "utf-16-be", "utf-16-le"])
    if len(raw) >= 2 and raw[0::2].count(0) >= max(1, len(raw) // 8):
        encodings.append("utf-16-be")
    encodings.extend(["utf-8", "latin-1"])
    for encoding in dict.fromkeys(encodings):
        try:
            decoded = _clean_pdf_text(raw.decode(encoding)).strip()
        except UnicodeDecodeError:
            continue
        if decoded and any(ch.isalnum() for ch in decoded):
            return decoded
    return ""


def _clean_pdf_text(value: str) -> str:
    return "".join(ch if ch.isprintable() or ch.isspace() else " " for ch in value)


def _raster_likelihood(*, text_layer: str, image_markers: int) -> str:
    if text_layer == "yes":
        return "low"
    if image_markers:
        return "high"
    return "medium"


def _pdf_content_kind(*, text_layer: str, image_markers: int) -> str:
    if text_layer == "yes" and image_markers:
        return "mixed_pdf_with_text"
    if text_layer == "yes":
        return "text_layer_pdf"
    if image_markers:
        return "raster_pdf_or_image_only"
    return "pdf_requires_parser_review"


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
