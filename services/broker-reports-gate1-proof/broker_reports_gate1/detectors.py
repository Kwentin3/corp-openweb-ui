from __future__ import annotations

from pathlib import Path
from typing import Any


def extension_from_name(filename: Any, mime_type: str) -> str:
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix:
        return suffix.lstrip(".")
    mime = str(mime_type or "").lower()
    if mime == "text/csv":
        return "csv"
    if mime.startswith("text/plain"):
        return "txt"
    if mime.startswith("text/html"):
        return "html"
    if mime == "application/pdf":
        return "pdf"
    if "spreadsheetml.sheet" in mime:
        return "xlsx"
    if mime in {"application/zip", "application/x-zip-compressed"}:
        return "zip"
    return ""


def detect_container(
    *,
    extension: str,
    mime_type: str,
    content_bytes: bytes | None,
) -> dict[str, str]:
    ext = str(extension or "").lower().lstrip(".")
    mime = str(mime_type or "").lower()
    if content_bytes:
        magic = content_bytes[:16]
        if magic.startswith(b"%PDF-"):
            return {"container_format": "pdf", "confidence": "high", "basis": "magic_pdf"}
        if (
            magic.startswith(b"PK\x03\x04")
            or magic.startswith(b"PK\x05\x06")
            or magic.startswith(b"PK\x07\x08")
        ):
            if ext == "xlsx" or "spreadsheetml.sheet" in mime:
                return {"container_format": "xlsx", "confidence": "high", "basis": "magic_zip_xlsx_extension"}
            if ext == "docx" or "wordprocessingml.document" in mime:
                return {"container_format": "docx", "confidence": "high", "basis": "magic_zip_docx_extension"}
            return {"container_format": "zip", "confidence": "high", "basis": "magic_zip"}
        if magic.startswith(b"\x89PNG\r\n\x1a\n") or magic.startswith(b"\xff\xd8\xff"):
            return {"container_format": "image", "confidence": "high", "basis": "image_magic"}
        if magic[:4] in {b"II*\x00", b"MM\x00*"} or magic.startswith(b"RIFF"):
            return {"container_format": "image", "confidence": "high", "basis": "image_magic"}

    if ext == "pdf" or mime == "application/pdf":
        return {"container_format": "pdf", "confidence": "medium", "basis": "metadata_pdf"}
    if ext == "xlsx" or "spreadsheetml.sheet" in mime:
        return {"container_format": "xlsx", "confidence": "medium", "basis": "metadata_xlsx"}
    if ext == "xls":
        return {"container_format": "xls", "confidence": "medium", "basis": "metadata_xls"}
    if ext == "csv" or mime == "text/csv":
        return {"container_format": "csv", "confidence": "medium", "basis": "metadata_csv"}
    if ext == "html" or mime.startswith("text/html"):
        return {"container_format": "html_text", "confidence": "medium", "basis": "metadata_html_text"}
    if ext == "txt" or mime.startswith("text/plain"):
        return {"container_format": "txt", "confidence": "medium", "basis": "metadata_text"}
    if ext == "docx" or "wordprocessingml.document" in mime:
        return {"container_format": "docx", "confidence": "medium", "basis": "metadata_docx"}
    if ext in {"png", "jpg", "jpeg", "webp", "tif", "tiff"} or mime.startswith("image/"):
        return {"container_format": "image", "confidence": "medium", "basis": "metadata_image"}
    if ext == "zip" or mime in {"application/zip", "application/x-zip-compressed"}:
        return {"container_format": "zip", "confidence": "medium", "basis": "metadata_zip"}
    return {"container_format": "unknown", "confidence": "low", "basis": "unidentified"}


def machine_readable_baseline(container: str) -> str:
    if container in {"csv", "xlsx", "xls"}:
        return "conditional"
    if container in {"txt", "html_text", "zip", "docx"}:
        return "conditional"
    if container == "pdf":
        return "unknown"
    if container in {"image", "unknown"}:
        return "no"
    return "conditional"
