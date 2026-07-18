from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any


PDF_VISUAL_MEMORY_PROFILE_ID = "broker_reports_pdf_visual_page_fallback_v1"
PYMUPDF_PINNED_VERSION = "1.26.5"

FACTORY_REQUIRED = (
    "PdfVisualMemoryFactory.create is the only production whole-page visual "
    "fallback renderer entrypoint"
)
FORBIDDEN = (
    "Callers must not treat rendered pages as OCR text or canonical financial tables"
)


class PdfVisualMemoryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PdfVisualMemoryConfig:
    dpi: int = 144
    max_pages: int = 64
    max_pixels_per_page: int = 30_000_000
    max_png_bytes_per_page: int = 10_000_000
    max_png_bytes_per_document: int = 75_000_000
    expected_pymupdf_version: str = PYMUPDF_PINNED_VERSION


@dataclass(frozen=True)
class PdfVisualPage:
    page_number: int
    width_pixels: int
    height_pixels: int
    png_sha256: str
    private_png_base64: str


class PdfVisualMemoryFactory:
    def __init__(self, config: PdfVisualMemoryConfig | None = None) -> None:
        self.config = config or PdfVisualMemoryConfig()

    def create(self) -> "PdfVisualMemoryRenderer":
        for value, code in (
            (self.config.dpi, "pdf_visual_dpi_invalid"),
            (self.config.max_pages, "pdf_visual_page_budget_invalid"),
            (self.config.max_pixels_per_page, "pdf_visual_pixel_budget_invalid"),
            (
                self.config.max_png_bytes_per_page,
                "pdf_visual_page_byte_budget_invalid",
            ),
            (
                self.config.max_png_bytes_per_document,
                "pdf_visual_document_byte_budget_invalid",
            ),
        ):
            if value <= 0:
                raise ValueError(code)
        return PdfVisualMemoryRenderer(self.config)


class PdfVisualMemoryRenderer:
    def __init__(self, config: PdfVisualMemoryConfig) -> None:
        self.config = config

    def render_pages(
        self, *, content_bytes: bytes, page_numbers: list[int]
    ) -> list[PdfVisualPage]:
        requested = sorted(set(int(value) for value in page_numbers if int(value) > 0))
        if len(requested) > self.config.max_pages:
            raise PdfVisualMemoryError("pdf_visual_page_budget_exceeded")
        try:
            import fitz
        except ImportError as exc:
            raise PdfVisualMemoryError("pdf_visual_renderer_unavailable") from exc
        if str(fitz.VersionBind) != self.config.expected_pymupdf_version:
            raise PdfVisualMemoryError("pdf_visual_renderer_version_mismatch")
        try:
            document = fitz.open(stream=content_bytes, filetype="pdf")
        except Exception as exc:
            raise PdfVisualMemoryError("pdf_visual_document_open_failed") from exc
        pages: list[PdfVisualPage] = []
        total_bytes = 0
        try:
            for page_number in requested:
                if page_number > len(document):
                    raise PdfVisualMemoryError("pdf_visual_page_out_of_range")
                page = document.load_page(page_number - 1)
                pixmap = page.get_pixmap(dpi=self.config.dpi, alpha=False)
                pixels = int(pixmap.width) * int(pixmap.height)
                if pixels > self.config.max_pixels_per_page:
                    raise PdfVisualMemoryError("pdf_visual_pixel_budget_exceeded")
                png_bytes = pixmap.tobytes("png")
                if len(png_bytes) > self.config.max_png_bytes_per_page:
                    raise PdfVisualMemoryError("pdf_visual_page_byte_budget_exceeded")
                total_bytes += len(png_bytes)
                if total_bytes > self.config.max_png_bytes_per_document:
                    raise PdfVisualMemoryError(
                        "pdf_visual_document_byte_budget_exceeded"
                    )
                pages.append(
                    PdfVisualPage(
                        page_number=page_number,
                        width_pixels=int(pixmap.width),
                        height_pixels=int(pixmap.height),
                        png_sha256=hashlib.sha256(png_bytes).hexdigest(),
                        private_png_base64=base64.b64encode(png_bytes).decode("ascii"),
                    )
                )
        finally:
            document.close()
        return pages
