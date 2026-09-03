from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Protocol, runtime_checkable


PDF_DOCUMENT_EXTRACTION_SCHEMA_VERSION = "broker_reports_pdf_document_extraction_v1"
PDF_DOCUMENT_AI_POLICY_VERSION = "broker_reports_pdf_document_ai_v1"
PDF_DOCUMENT_AI_NOT_CONFIGURED = "PDF_DOCUMENT_AI_NOT_CONFIGURED"
_SAFE_TECHNICAL_SUMMARY_KEYS = {
    "document_bytes",
    "images_count",
    "markdown_bytes",
    "pages_count",
}


@dataclass(frozen=True)
class PdfDocumentImageRef:
    local_ref: str
    sha256: str

    def __post_init__(self) -> None:
        windows_path = PureWindowsPath(self.local_ref)
        posix_path = PurePosixPath(self.local_ref)
        if (
            not self.local_ref
            or "\x00" in self.local_ref
            or "://" in self.local_ref
            or windows_path.drive
            or windows_path.root
            or windows_path.is_absolute()
            or posix_path.is_absolute()
            or ".." in windows_path.parts
            or ".." in posix_path.parts
        ):
            raise ValueError("pdf_document_image_ref_must_be_closed_local")
        _require_sha256(self.sha256, "pdf_document_image_sha256_invalid")


@dataclass(frozen=True)
class PdfDocumentExtraction:
    source_pdf_sha256: str
    page_numbers: tuple[int, ...]
    markdown_bytes: bytes
    markdown_sha256: str
    image_refs: tuple[PdfDocumentImageRef, ...]
    provider_id: str
    model_id: str
    adapter_id: str
    qualification_status: str
    usage_page_count: int
    safe_technical_summary: tuple[tuple[str, int], ...] = ()
    schema_version: str = PDF_DOCUMENT_EXTRACTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_sha256(self.source_pdf_sha256, "pdf_document_source_sha256_invalid")
        _require_sha256(self.markdown_sha256, "pdf_document_markdown_sha256_invalid")
        if hashlib.sha256(self.markdown_bytes).hexdigest() != self.markdown_sha256:
            raise ValueError("pdf_document_markdown_sha256_mismatch")
        try:
            self.markdown_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("pdf_document_markdown_not_utf8") from exc
        if not self.page_numbers or self.page_numbers != tuple(
            range(1, len(self.page_numbers) + 1)
        ):
            raise ValueError("pdf_document_page_order_invalid")
        if self.page_numbers[0] < 1 or self.usage_page_count != len(self.page_numbers):
            raise ValueError("pdf_document_page_count_invalid")
        if not all((self.provider_id, self.model_id, self.adapter_id)):
            raise ValueError("pdf_document_provenance_incomplete")
        if self.qualification_status not in {"offline_fixture", "qualified"}:
            raise ValueError("pdf_document_qualification_status_invalid")
        if len({item.local_ref for item in self.image_refs}) != len(self.image_refs):
            raise ValueError("pdf_document_image_ref_duplicate")
        summary_keys = [key for key, _value in self.safe_technical_summary]
        if len(set(summary_keys)) != len(summary_keys):
            raise ValueError("pdf_document_safe_summary_key_duplicate")
        if not set(summary_keys).issubset(_SAFE_TECHNICAL_SUMMARY_KEYS):
            raise ValueError("pdf_document_safe_summary_key_forbidden")
        summary = dict(self.safe_technical_summary)
        if any(type(value) is not int or value < 0 for value in summary.values()):
            raise ValueError("pdf_document_safe_summary_count_invalid")
        expected_counts = {
            "images_count": len(self.image_refs),
            "markdown_bytes": len(self.markdown_bytes),
            "pages_count": self.usage_page_count,
        }
        if any(
            key in summary and summary[key] != expected
            for key, expected in expected_counts.items()
        ):
            raise ValueError("pdf_document_safe_summary_count_mismatch")


@dataclass(frozen=True)
class PdfSourceContext:
    document_ref: str
    expected_pdf_sha256: str
    preflight_page_count: int

    def __post_init__(self) -> None:
        if not self.document_ref:
            raise ValueError("pdf_document_source_ref_required")
        _require_sha256(
            self.expected_pdf_sha256,
            "pdf_document_expected_source_sha256_invalid",
        )
        if self.preflight_page_count < 1:
            raise ValueError("pdf_document_preflight_page_count_invalid")


class PdfDocumentExtractionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@runtime_checkable
class PdfDocumentExtractor(Protocol):
    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction: ...


class UnconfiguredPdfDocumentExtractor:
    adapter_id = "unconfigured_pdf_document_extractor_v1"

    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        del pdf_bytes, source_context
        raise PdfDocumentExtractionError(PDF_DOCUMENT_AI_NOT_CONFIGURED)


class PdfDocumentExtractorFactory:
    """The sole production composition point for PDF understanding."""

    FACTORY_REQUIRED = "PdfDocumentExtractorFactory.create is the only production PDF Document AI composition point"
    FORBIDDEN = "Automatic provider selection, retry and fallback are forbidden"

    @staticmethod
    def create() -> PdfDocumentExtractor:
        return UnconfiguredPdfDocumentExtractor()


def validate_extraction_source(
    extraction: PdfDocumentExtraction,
    *,
    pdf_bytes: bytes,
    source_context: PdfSourceContext,
) -> None:
    actual_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    if actual_sha256 != source_context.expected_pdf_sha256:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_SOURCE_CUSTODY_MISMATCH")
    if extraction.source_pdf_sha256 != actual_sha256:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_EXTRACTION_SOURCE_MISMATCH")
    if extraction.usage_page_count != source_context.preflight_page_count:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_EXTRACTION_PAGE_COUNT_MISMATCH")


def _require_sha256(value: str, code: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(code)
