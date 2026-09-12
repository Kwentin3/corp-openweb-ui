"""Native-text PDF representation adapter for the single Gate 1 PDF port.

This adapter deliberately extracts only the text layer that is already present
in the uploaded PDF.  It neither renders pages nor calls a provider, and its
output stays representation-only: later Canonical and mapping owners decide
what the literals mean.
"""

from __future__ import annotations

import hashlib
import html
import json
from io import BytesIO

import pdfplumber

from .pdf_document_ai import (
    PdfDocumentExtraction,
    PdfDocumentExtractionError,
    PdfDocumentTableRef,
    PdfSourceContext,
    new_pdf_document_table_ref,
)


PDFPLUMBER_NATIVE_TEXT_ADAPTER_ID = "pdfplumber_native_text_adapter_v3"
PDFPLUMBER_NATIVE_TEXT_CONTRACT_VERSION = "pdfplumber_native_text_v3"
PDF_NATIVE_TEXT_UNUSABLE = "PDF_NATIVE_TEXT_UNUSABLE"


class PdfPlumberNativeTextExtractor:
    """Read embedded text and default table geometry without interpretation."""

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
                page_markdown: list[bytes] = []
                original_text_pages: list[bytes] = []
                table_refs: list[PdfDocumentTableRef] = []
                for page_number, page in enumerate(document.pages, start=1):
                    text = page.extract_text() or ""
                    original_text_pages.append(
                        text.encode("utf-8", errors="strict")
                    )
                    try:
                        tables = page.extract_tables()
                    except Exception as exc:
                        raise PdfDocumentExtractionError(
                            "PDF_NATIVE_TEXT_TABLE_EXTRACTION_FAILED"
                        ) from exc
                    if not isinstance(tables, list):
                        raise PdfDocumentExtractionError(
                            "PDF_NATIVE_TEXT_TABLE_EXTRACTION_FAILED"
                        )
                    anchors: list[str] = []
                    for table_ordinal, table in enumerate(tables, start=1):
                        html_bytes = _serialize_default_table(table)
                        local_ref = new_pdf_document_table_ref()
                        # The source PDF can contain arbitrary Markdown-like
                        # text.  Bind the anchor to a ref minted only after the
                        # PDF is opened, rather than a target it could predict.
                        markdown_target = f"{local_ref}.html"
                        table_refs.append(
                            PdfDocumentTableRef(
                                page_number=page_number,
                                markdown_target=markdown_target,
                                local_ref=local_ref,
                                sha256=hashlib.sha256(html_bytes).hexdigest(),
                                html_bytes=html_bytes,
                            )
                        )
                        anchors.append(
                            f"[native table {table_ordinal}]({markdown_target})"
                        )
                    page_text = "\n\n".join((text, *anchors)) if anchors else text
                    page_markdown.append(page_text.encode("utf-8", errors="strict"))
                pages = tuple(page_markdown)
        except PdfDocumentExtractionError:
            raise
        except Exception as exc:
            raise PdfDocumentExtractionError("PDF_NATIVE_TEXT_EXTRACTION_FAILED") from exc

        if not any(page.strip() for page in original_text_pages):
            raise PdfDocumentExtractionError(PDF_NATIVE_TEXT_UNUSABLE)

        markdown_bytes = b"\n\n".join(pages)
        parameters = (
            ("extraction_mode", "embedded_text_and_default_tables"),
            ("parser", "pdfplumber"),
            ("tables", "extract_tables_default"),
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
            table_refs=tuple(table_refs),
            page_content_dispositions=tuple(
                "markdown_materialized" if page else "provider_empty_page"
                for page in pages
            ),
            safe_technical_summary=(
                ("markdown_bytes", len(markdown_bytes)),
                ("pages_count", len(pages)),
                ("tables_count", len(table_refs)),
            ),
        )


def _serialize_default_table(table: object) -> bytes:
    """Encode one pdfplumber table as neutral, closed HTML.

    PdfPlumber does not establish financial roles or header semantics.  The
    adapter consequently preserves every cell as an escaped ``td`` and lets
    downstream Canonical and semantic owners interpret the representation.
    """

    if not isinstance(table, list) or not table:
        raise PdfDocumentExtractionError("PDF_NATIVE_TEXT_TABLE_SERIALIZATION_FAILED")
    rows: list[str] = []
    for row_ordinal, row in enumerate(table, start=1):
        if not isinstance(row, list) or not row:
            raise PdfDocumentExtractionError(
                "PDF_NATIVE_TEXT_TABLE_SERIALIZATION_FAILED"
            )
        cells: list[str] = []
        for value in row:
            if value is not None and not isinstance(value, str):
                raise PdfDocumentExtractionError(
                    "PDF_NATIVE_TEXT_TABLE_SERIALIZATION_FAILED"
                )
            cells.append(f"<td>{html.escape(value or '', quote=True)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return ("<table><tbody>" + "".join(rows) + "</tbody></table>").encode(
        "utf-8", errors="strict"
    )
