from __future__ import annotations

import hashlib
import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Protocol, runtime_checkable


PDF_DOCUMENT_EXTRACTION_SCHEMA_VERSION = "broker_reports_pdf_document_extraction_v2"
PDF_DOCUMENT_AI_POLICY_VERSION = "broker_reports_pdf_document_ai_v2"
PDF_DOCUMENT_AI_NOT_CONFIGURED = "PDF_DOCUMENT_AI_NOT_CONFIGURED"
PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED = (
    "PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED"
)
# Release admission is code-owned. Native OpenWebUI configuration is necessary,
# but it is not evidence that the production route has been qualified.
PDF_DOCUMENT_AI_LIVE_QUALIFIED = False
_SAFE_TECHNICAL_SUMMARY_KEYS = {
    "document_bytes",
    "images_count",
    "markdown_bytes",
    "pages_count",
}


@dataclass(frozen=True)
class PdfDocumentImageRef:
    page_number: int
    markdown_target: str
    local_ref: str
    sha256: str
    media_type: str
    content_bytes: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.page_number) is not int or self.page_number < 1:
            raise ValueError("pdf_document_image_page_number_invalid")
        _require_closed_relative_ref(
            self.markdown_target,
            "pdf_document_image_markdown_target_must_be_closed_relative",
        )
        _require_closed_relative_ref(
            self.local_ref,
            "pdf_document_image_ref_must_be_closed_local",
        )
        _require_sha256(self.sha256, "pdf_document_image_sha256_invalid")
        if self.media_type not in {
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
        }:
            raise ValueError("pdf_document_image_media_type_invalid")
        if type(self.content_bytes) is not bytes or not self.content_bytes:
            raise ValueError("pdf_document_image_bytes_required")
        if hashlib.sha256(self.content_bytes).hexdigest() != self.sha256:
            raise ValueError("pdf_document_image_sha256_mismatch")


def new_pdf_document_image_ref() -> str:
    """Mint an opaque, unpublished ref without choosing a storage backend."""

    return f"pdfimg_{secrets.token_urlsafe(24)}"


def _require_closed_relative_ref(value: str, code: str) -> None:
    if not isinstance(value, str):
        raise ValueError(code)
    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(value)
    if (
        not value
        or value == "."
        or "\x00" in value
        or "://" in value
        or windows_path.drive
        or windows_path.root
        or windows_path.is_absolute()
        or posix_path.is_absolute()
        or ".." in windows_path.parts
        or ".." in posix_path.parts
    ):
        raise ValueError(code)


@dataclass(frozen=True)
class PdfDocumentExtraction:
    source_pdf_sha256: str = field(repr=False)
    page_numbers: tuple[int, ...]
    markdown_bytes: bytes = field(repr=False)
    markdown_sha256: str = field(repr=False)
    image_refs: tuple[PdfDocumentImageRef, ...] = field(repr=False)
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
        if self.qualification_status not in {
            "offline_fixture",
            "qualification_attempt",
            "qualified",
        }:
            raise ValueError("pdf_document_qualification_status_invalid")
        if len({item.local_ref for item in self.image_refs}) != len(self.image_refs):
            raise ValueError("pdf_document_image_ref_duplicate")
        if any(item.page_number not in self.page_numbers for item in self.image_refs):
            raise ValueError("pdf_document_image_page_not_in_document")
        image_pages = tuple(item.page_number for item in self.image_refs)
        if image_pages != tuple(sorted(image_pages)):
            raise ValueError("pdf_document_image_page_order_invalid")
        associations = {
            (item.page_number, item.markdown_target) for item in self.image_refs
        }
        if len(associations) != len(self.image_refs):
            raise ValueError("pdf_document_image_association_duplicate")
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


class RejectedPdfDocumentExtractor:
    """Keep a static configuration failure inside the normal PDF boundary."""

    def __init__(self, code: str) -> None:
        self._code = code

    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        del pdf_bytes, source_context
        raise PdfDocumentExtractionError(self._code)


class PdfDocumentExtractorFactory:
    """The sole production composition point for PDF understanding."""

    FACTORY_REQUIRED = "PdfDocumentExtractorFactory.create is the only production PDF Document AI composition point"
    FORBIDDEN = "Automatic provider selection, retry and fallback are forbidden"

    @staticmethod
    def create(
        *,
        server_request: Any = None,
        image_root: Path | None = None,
        qualification_permit: Any = None,
    ) -> PdfDocumentExtractor:
        del image_root  # Compatibility-only; ArtifactStore owns image persistence.
        if server_request is None:
            return UnconfiguredPdfDocumentExtractor()
        try:
            engine = str(
                server_request.app.state.config.CONTENT_EXTRACTION_ENGINE or ""
            ).lower()
        except (AttributeError, TypeError):
            return UnconfiguredPdfDocumentExtractor()
        if engine != "mistral_ocr":
            return UnconfiguredPdfDocumentExtractor()
        if not PDF_DOCUMENT_AI_LIVE_QUALIFIED and qualification_permit is None:
            return RejectedPdfDocumentExtractor(
                PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED
            )
        if not PDF_DOCUMENT_AI_LIVE_QUALIFIED:
            return _QualificationPdfDocumentExtractor(
                server_request=server_request,
                permit=qualification_permit,
            )
        from .mistral_pdf_document_ai import create_from_openwebui_request

        try:
            configured = create_from_openwebui_request(
                server_request=server_request,
            )
        except PdfDocumentExtractionError as exc:
            return RejectedPdfDocumentExtractor(exc.code)
        return configured or UnconfiguredPdfDocumentExtractor()


class _QualificationPdfDocumentExtractor:
    """Defer native config/key access until the exact public digest is admitted."""

    def __init__(self, *, server_request: Any, permit: Any) -> None:
        self._server_request = server_request
        self._permit = permit

    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        observed_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        admits = getattr(self._permit, "admits", None)
        if not callable(admits) or admits(observed_sha256) is not True:
            raise PdfDocumentExtractionError(
                "PDF_DOCUMENT_AI_QUALIFICATION_FIXTURE_FORBIDDEN"
            )
        from .mistral_pdf_document_ai import create_from_openwebui_request

        configured = create_from_openwebui_request(
            server_request=self._server_request,
            qualification_status="qualification_attempt",
        )
        if configured is None:
            raise PdfDocumentExtractionError(PDF_DOCUMENT_AI_NOT_CONFIGURED)
        return configured.extract(pdf_bytes, source_context)


def is_terminal_pdf_document_ai_request(
    documents: Iterable[Mapping[str, object]],
    blockers: Iterable[Mapping[str, object]],
) -> bool:
    """Return whether every processable document stopped at the PDF boundary."""

    document_list = tuple(documents)
    pdf_document_refs = {
        str(document.get("document_id") or "")
        for document in document_list
        if document.get("container_format") == "pdf" and document.get("document_id")
    }
    blocked_document_refs = {
        str(blocker.get("document_id") or "")
        for blocker in blockers
        if (
            blocker.get("code")
            in {
                PDF_DOCUMENT_AI_NOT_CONFIGURED,
                PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED,
            }
            or (
                blocker.get("code") == "parser_failed"
                and str(
                    blocker.get("reason_code") or blocker.get("reason") or ""
                ).startswith("PDF_DOCUMENT_")
            )
        )
        and str(blocker.get("document_id") or "") in pdf_document_refs
    }
    if not blocked_document_refs:
        return False
    processable_document_refs = {
        str(document.get("document_id") or "")
        for document in document_list
        if document.get("container_format") != "zip" and document.get("document_id")
    }
    return bool(processable_document_refs) and processable_document_refs.issubset(
        blocked_document_refs
    )


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
