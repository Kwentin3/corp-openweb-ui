"""Native-text PDF representation adapter for the single Gate 1 PDF port.

This adapter deliberately extracts only the text layer that is already present
in the uploaded PDF.  It neither renders pages nor calls a provider, and its
output stays representation-only: later Canonical and mapping owners decide
what the literals mean.
"""

from __future__ import annotations

import hashlib
import json
from io import BytesIO

import pdfplumber

from .pdf_document_ai import (
    PdfDocumentExtraction,
    PdfDocumentExtractionError,
    PdfSourceContext,
)


PDFPLUMBER_NATIVE_TEXT_ADAPTER_ID = "pdfplumber_native_text_adapter_v1"
PDFPLUMBER_NATIVE_TEXT_CONTRACT_VERSION = "pdfplumber_native_text_v1"
PDF_NATIVE_TEXT_UNUSABLE = "PDF_NATIVE_TEXT_UNUSABLE"


class PdfPlumberNativeTextExtractor:
    """Read a usable embedded text layer with pdfplumber defaults only."""

    adapter_id = PDFPLUMBER_NATIVE_TEXT_ADAPTER_ID

    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as document:
                if len(document.pages) != source_context.preflight_page_count:
                    raise PdfDocumentExtractionError("PDF_NATIVE_TEXT_PAGE_COUNT_MISMATCH")
                pages = tuple(
                    (page.extract_text() or "").encode("utf-8")
                    for page in document.pages
                )
        except PdfDocumentExtractionError:
            raise
        except Exception as exc:
            raise PdfDocumentExtractionError("PDF_NATIVE_TEXT_EXTRACTION_FAILED") from exc

        if not any(page.strip() for page in pages):
            raise PdfDocumentExtractionError(PDF_NATIVE_TEXT_UNUSABLE)

        markdown_bytes = b"\n\n".join(pages)
        parameters = (
            ("extraction_mode", "embedded_text_default"),
            ("parser", "pdfplumber"),
        )
        return PdfDocumentExtraction(
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            page_numbers=tuple(range(1, len(pages) + 1)),
            markdown_bytes=markdown_bytes,
            markdown_sha256=hashlib.sha256(markdown_bytes).hexdigest(),
            image_refs=(),
            provider_id="native_pdfplumber",
            requested_model_id="embedded_pdf_text",
            model_id="embedded_pdf_text",
            adapter_id=self.adapter_id,
            request_contract_version=PDFPLUMBER_NATIVE_TEXT_CONTRACT_VERSION,
            request_parameters=parameters,
            request_parameters_sha256=hashlib.sha256(
                json.dumps(
                    dict(parameters),
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            page_markdown_sha256=tuple(
                hashlib.sha256(page).hexdigest() for page in pages
            ),
            qualification_status="qualified",
            usage_page_count=len(pages),
            page_markdown_bytes=pages,
            page_content_dispositions=tuple(
                "markdown_materialized" if page else "provider_empty_page"
                for page in pages
            ),
            safe_technical_summary=(
                ("markdown_bytes", len(markdown_bytes)),
                ("pages_count", len(pages)),
                ("tables_count", 0),
            ),
        )
