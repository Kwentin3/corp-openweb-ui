from __future__ import annotations

import base64
import hashlib
import math
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import sha256_json


PDF_TABLE_CROP_SCHEMA = "broker_reports_pdf_table_crop_v1"
PDF_TABLE_RASTER_POLICY_VERSION = "pdf_table_raster_policy_v1"
PDF_TABLE_CANDIDATE_SCHEMA = "broker_reports_pdf_table_candidate_v1"
PDF_TABLE_CANDIDATE_RASTER_POLICY_VERSION = "pdf_table_candidate_raster_policy_v1"
FACTORY_REQUIRED = (
    "PdfTableRasterFactory.create is the only table crop renderer entrypoint"
)
FORBIDDEN = (
    "Callers must not silently resize, override global padding per table, "
    "render whole PDFs as candidates, or publish crop bytes"
)


class PdfTableRasterError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfTableRasterConfig:
    renderer: str = "pymupdf"
    renderer_version: str = "1.26.5"
    padding_points: float = 2.0
    horizontal_padding_fraction: float = 0.08
    vertical_padding_fraction: float = 0.08
    maximum_width: int = 4096
    maximum_height: int = 4096
    maximum_pixels: int = 16_000_000
    maximum_png_bytes: int = 8 * 1024 * 1024


class PdfTableRasterFactory:
    def __init__(self, config: PdfTableRasterConfig | None = None) -> None:
        self.config = config or PdfTableRasterConfig()

    def create(self) -> "PdfTableRasterRenderer":
        for value in (
            self.config.horizontal_padding_fraction,
            self.config.vertical_padding_fraction,
        ):
            if not math.isfinite(value) or value < 0 or value > 0.25:
                raise PdfTableRasterError("pdf_table_raster_padding_fraction_invalid")
        try:
            import fitz
        except ImportError as exc:
            raise PdfTableRasterError("pdf_table_raster_dependency_unavailable") from exc
        if fitz.VersionBind != self.config.renderer_version:
            raise PdfTableRasterError("pdf_table_raster_renderer_version_mismatch")
        return PdfTableRasterRenderer(self.config, fitz)


class PdfTableRasterRenderer:
    def __init__(self, config: PdfTableRasterConfig, fitz_module: Any) -> None:
        self.config = config
        self.fitz = fitz_module

    def render(
        self,
        *,
        pdf_bytes: bytes,
        pdf_sha256: str,
        document_ref: str,
        page_number: int,
        table_ref: str,
        table_bbox: list[float],
        dpi: int,
        escalation_reason: str | None = None,
    ) -> dict[str, Any]:
        return self._render_pdf_bbox(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref=document_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=table_bbox,
            dpi=dpi,
            padding_x_points=self.config.padding_points,
            padding_y_points=self.config.padding_points,
            escalation_reason=escalation_reason,
            schema_version=PDF_TABLE_CROP_SCHEMA,
            policy_version=PDF_TABLE_RASTER_POLICY_VERSION,
            manifest_extras={"padding_points": self.config.padding_points},
            crop_id_prefix="pdfcrop_",
        )

    def render_detected_region(
        self,
        *,
        pdf_bytes: bytes,
        pdf_sha256: str,
        document_ref: str,
        page_number: int,
        candidate_ref: str,
        detected_bbox_normalized: list[float],
        detector_contract_version: str,
        detector_identity: dict[str, Any],
        dpi: int = 150,
    ) -> dict[str, Any]:
        """Render one validated detector box with global page-relative padding."""

        if len(detected_bbox_normalized) != 4 or not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in detected_bbox_normalized
        ):
            raise PdfTableRasterError("pdf_table_raster_normalized_bbox_invalid")
        x0, y0, x1, y1 = [float(value) for value in detected_bbox_normalized]
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise PdfTableRasterError("pdf_table_raster_normalized_bbox_invalid")
        document = self.fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if page_number < 1 or page_number > len(document):
                raise PdfTableRasterError("pdf_table_raster_page_invalid")
            page_bbox = document[page_number - 1].rect
            table_bbox = [
                page_bbox.x0 + x0 * page_bbox.width,
                page_bbox.y0 + y0 * page_bbox.height,
                page_bbox.x0 + x1 * page_bbox.width,
                page_bbox.y0 + y1 * page_bbox.height,
            ]
            padding_x_points = (
                page_bbox.width * self.config.horizontal_padding_fraction
            )
            padding_y_points = (
                page_bbox.height * self.config.vertical_padding_fraction
            )
            page_points = [round(float(value), 6) for value in page_bbox]
        finally:
            document.close()
        return self._render_pdf_bbox(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref=document_ref,
            page_number=page_number,
            table_ref=candidate_ref,
            table_bbox=table_bbox,
            dpi=dpi,
            padding_x_points=padding_x_points,
            padding_y_points=padding_y_points,
            escalation_reason=None,
            schema_version=PDF_TABLE_CANDIDATE_SCHEMA,
            policy_version=PDF_TABLE_CANDIDATE_RASTER_POLICY_VERSION,
            manifest_extras={
                "candidate_ref": candidate_ref,
                "detected_bbox_normalized": [
                    round(value, 9) for value in detected_bbox_normalized
                ],
                "page_bbox_points": page_points,
                "padding_basis": "page_dimensions_per_side",
                "horizontal_padding_fraction": (
                    self.config.horizontal_padding_fraction
                ),
                "vertical_padding_fraction": self.config.vertical_padding_fraction,
                "padding_x_points": round(padding_x_points, 6),
                "padding_y_points": round(padding_y_points, 6),
                "detector_contract_version": detector_contract_version,
                "detector_identity": detector_identity,
                "downstream_contract": "gate2_raster_candidate",
                "semantic_interpretation_performed": False,
            },
            crop_id_prefix="pdftablecandidate_",
        )

    def _render_pdf_bbox(
        self,
        *,
        pdf_bytes: bytes,
        pdf_sha256: str,
        document_ref: str,
        page_number: int,
        table_ref: str,
        table_bbox: list[float],
        dpi: int,
        padding_x_points: float,
        padding_y_points: float,
        escalation_reason: str | None,
        schema_version: str,
        policy_version: str,
        manifest_extras: dict[str, Any],
        crop_id_prefix: str,
    ) -> dict[str, Any]:
        if hashlib.sha256(pdf_bytes).hexdigest() != pdf_sha256:
            raise PdfTableRasterError("pdf_table_raster_pdf_checksum_mismatch")
        if dpi not in {150, 200}:
            raise PdfTableRasterError("pdf_table_raster_dpi_not_allowed")
        if dpi == 200 and not escalation_reason:
            raise PdfTableRasterError("pdf_table_raster_escalation_reason_missing")
        if len(table_bbox) != 4:
            raise PdfTableRasterError("pdf_table_raster_bbox_invalid")
        document = self.fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if page_number < 1 or page_number > len(document):
                raise PdfTableRasterError("pdf_table_raster_page_invalid")
            page = document[page_number - 1]
            declared = self.fitz.Rect(table_bbox)
            if declared.is_empty or declared.is_infinite:
                raise PdfTableRasterError("pdf_table_raster_bbox_invalid")
            padded = self.fitz.Rect(
                max(page.rect.x0, declared.x0 - padding_x_points),
                max(page.rect.y0, declared.y0 - padding_y_points),
                min(page.rect.x1, declared.x1 + padding_x_points),
                min(page.rect.y1, declared.y1 + padding_y_points),
            )
            if padded.is_empty or padded.is_infinite:
                raise PdfTableRasterError("pdf_table_raster_padded_bbox_invalid")
            pixmap = page.get_pixmap(dpi=dpi, clip=padded, alpha=False)
            width, height = int(pixmap.width), int(pixmap.height)
            if (
                width > self.config.maximum_width
                or height > self.config.maximum_height
                or width * height > self.config.maximum_pixels
            ):
                raise PdfTableRasterError("pdf_table_raster_dimension_budget_exceeded")
            png = pixmap.tobytes("png")
            if len(png) > self.config.maximum_png_bytes:
                raise PdfTableRasterError("pdf_table_raster_encoded_budget_exceeded")
            png_sha256 = hashlib.sha256(png).hexdigest()
            crop_id = crop_id_prefix + stable_digest(
                [pdf_sha256, page_number, table_ref, list(padded), dpi, png_sha256],
                length=24,
            )
            manifest = {
                "schema_version": schema_version,
                "policy_version": policy_version,
                "crop_id": crop_id,
                "document_ref": document_ref,
                "pdf_sha256": pdf_sha256,
                "page_number": page_number,
                "table_ref": table_ref,
                "declared_table_bbox": [round(float(value), 6) for value in declared],
                "rendered_bbox": [round(float(value), 6) for value in padded],
                "source_coordinate_space": "pdf_top_left_points",
                "pixel_coordinate_space": "crop_top_left_pixels",
                "source_to_pixel_transform": {
                    "scale_x": round(width / padded.width, 9),
                    "scale_y": round(height / padded.height, 9),
                    "translate_source_x": round(-padded.x0, 9),
                    "translate_source_y": round(-padded.y0, 9),
                },
                "renderer": self.config.renderer,
                "renderer_version": self.config.renderer_version,
                "page_rotation": int(page.rotation),
                "applied_rotation": 0,
                "dpi": dpi,
                "dpi_revision_reason": escalation_reason or "primary_150_dpi",
                "width": width,
                "height": height,
                "pixels": width * height,
                "png_bytes": len(png),
                "png_sha256": png_sha256,
                "lossless": True,
                "silent_resize_performed": False,
                **manifest_extras,
            }
            manifest["manifest_hash"] = sha256_json(manifest)
            return {
                "manifest": manifest,
                "private_png_base64": base64.b64encode(png).decode("ascii"),
            }
        finally:
            document.close()

    def render_full_page(
        self,
        *,
        pdf_bytes: bytes,
        pdf_sha256: str,
        document_ref: str,
        page_ref: str,
        page_number: int,
        expected_page_bbox: list[float],
        dpi: int,
    ) -> dict[str, Any]:
        """Render one page only after proving its parser/PDF identity.

        The ordinary crop entrypoint remains unchanged.  This narrower helper
        is used by the default-disabled page-proposal shadow route so a VLM
        never sees a page whose source bounds differ from the text-layer page
        it is expected to describe.
        """

        if not isinstance(page_ref, str) or not page_ref:
            raise PdfTableRasterError("pdf_table_raster_page_ref_invalid")
        if hashlib.sha256(pdf_bytes).hexdigest() != pdf_sha256:
            raise PdfTableRasterError("pdf_table_raster_pdf_checksum_mismatch")
        if len(expected_page_bbox) != 4:
            raise PdfTableRasterError("pdf_table_raster_page_bbox_invalid")
        document = self.fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if page_number < 1 or page_number > len(document):
                raise PdfTableRasterError("pdf_table_raster_page_invalid")
            page = document[page_number - 1]
            actual_bbox = [round(float(value), 6) for value in page.rect]
            expected_bbox = [round(float(value), 6) for value in expected_page_bbox]
            if expected_bbox != actual_bbox:
                raise PdfTableRasterError(
                    "pdf_table_raster_full_page_identity_mismatch"
                )
        finally:
            document.close()

        rendered = self.render(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref=document_ref,
            page_number=page_number,
            table_ref="page_scope_"
            + stable_digest([document_ref, page_ref, page_number], length=24),
            table_bbox=actual_bbox,
            dpi=dpi,
        )
        manifest = rendered["manifest"]
        manifest.update(
            {
                "page_ref": page_ref,
                "render_scope": "full_page",
                "actual_page_bbox": actual_bbox,
                "full_page_identity_verified": True,
            }
        )
        manifest.pop("manifest_hash", None)
        manifest["manifest_hash"] = sha256_json(manifest)
        return rendered
