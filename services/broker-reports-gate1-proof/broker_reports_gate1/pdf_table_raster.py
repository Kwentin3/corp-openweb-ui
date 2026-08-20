from __future__ import annotations

import base64
import hashlib
import math
import re
import statistics
from dataclasses import dataclass
from typing import Any

from .contracts import sha256_json, stable_digest


PDF_TABLE_CROP_SCHEMA = "broker_reports_pdf_table_crop_v1"
PDF_TABLE_RASTER_POLICY_VERSION = "pdf_table_raster_policy_v1"
PDF_TABLE_CANDIDATE_SCHEMA = "broker_reports_pdf_table_candidate_v1"
PDF_TABLE_CANDIDATE_RASTER_POLICY_VERSION = "pdf_table_candidate_raster_policy_v4"
CANONICAL_TABLE_REGION_SCHEMA = "broker_reports_canonical_table_region_v1"
CANONICAL_TABLE_REGION_POLICY_VERSION = "canonical_table_region_policy_v3"
FACTORY_REQUIRED = (
    "PdfTableRasterFactory.create is the only table-region resolver and crop "
    "renderer entrypoint"
)
FORBIDDEN = (
    "Callers must not bypass canonical table_region resolution, silently resize, "
    "supply per-table crop exceptions, render whole PDFs as candidates, or publish crop bytes"
)


class PdfTableRasterError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        crop_status: str = "CROP_BLOCKED",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.crop_status = crop_status
        self.details = details or {}
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
    canonical_outer_margin_points: float = 2.0
    canonical_header_search_points: float = 108.0
    canonical_component_gap_points: float = 40.0
    canonical_note_search_fraction: float = 0.25


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
        for value, minimum, maximum, code in (
            (
                self.config.canonical_outer_margin_points,
                0.0,
                12.0,
                "pdf_table_raster_canonical_outer_margin_invalid",
            ),
            (
                self.config.canonical_header_search_points,
                12.0,
                144.0,
                "pdf_table_raster_canonical_header_search_invalid",
            ),
            (
                self.config.canonical_component_gap_points,
                18.0,
                96.0,
                "pdf_table_raster_canonical_component_gap_invalid",
            ),
            (
                self.config.canonical_note_search_fraction,
                0.0,
                0.4,
                "pdf_table_raster_canonical_note_search_invalid",
            ),
        ):
            if not math.isfinite(value) or value < minimum or value > maximum:
                raise PdfTableRasterError(code)
        try:
            import fitz
        except ImportError as exc:
            raise PdfTableRasterError(
                "pdf_table_raster_dependency_unavailable"
            ) from exc
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

    def render_table_candidate(
        self,
        *,
        pdf_bytes: bytes,
        pdf_sha256: str,
        document_ref: str,
        page_number: int,
        candidate_ref: str,
        candidate_bbox: list[float],
        candidate_page_bbox: list[float],
        candidate_strategy_ref: str,
        detector_contract_version: str,
        detector_identity: dict[str, Any],
        dpi: int = 150,
        detected_bbox_normalized: list[float] | None = None,
    ) -> dict[str, Any]:
        """Resolve and render the one canonical region for a table candidate.

        The resolved ``table_region`` is shared provenance for the image crop,
        future source-text selection, and diagnostics.  Ambiguous or blocked
        geometry terminates before crop bytes are created.
        """

        table_region = self.resolve_table_region(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            page_number=page_number,
            candidate_bbox=candidate_bbox,
            candidate_page_bbox=candidate_page_bbox,
            candidate_strategy_ref=candidate_strategy_ref,
        )
        if table_region["status"] != "CROP_CLEAN":
            code = (
                "pdf_table_raster_crop_ambiguous"
                if table_region["status"] == "CROP_AMBIGUOUS"
                else "pdf_table_raster_crop_blocked"
            )
            raise PdfTableRasterError(
                code,
                crop_status=table_region["status"],
                details={"table_region": table_region},
            )
        manifest_extras = {
            "candidate_ref": candidate_ref,
            "source_candidate_bbox": copy_numbers(candidate_bbox),
            "source_candidate_page_bbox": copy_numbers(candidate_page_bbox),
            "candidate_strategy_ref": candidate_strategy_ref,
            "padding_basis": "canonical_table_region",
            "horizontal_padding_fraction": 0.0,
            "vertical_padding_fraction": 0.0,
            "padding_x_points": 0.0,
            "padding_y_points": 0.0,
            "legacy_padding_configuration": {
                "horizontal_fraction": self.config.horizontal_padding_fraction,
                "vertical_fraction": self.config.vertical_padding_fraction,
                "applied": False,
            },
            "detector_contract_version": detector_contract_version,
            "detector_identity": detector_identity,
            "downstream_contract": "gate2_raster_candidate",
            "semantic_interpretation_performed": False,
            "table_region": table_region,
        }
        if detected_bbox_normalized is not None:
            manifest_extras["detected_bbox_normalized"] = [
                round(float(value), 9) for value in detected_bbox_normalized
            ]
        return self._render_pdf_bbox(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref=document_ref,
            page_number=page_number,
            table_ref=candidate_ref,
            table_bbox=table_region["resolved_bbox"],
            dpi=dpi,
            padding_x_points=0.0,
            padding_y_points=0.0,
            escalation_reason=None,
            schema_version=PDF_TABLE_CANDIDATE_SCHEMA,
            policy_version=PDF_TABLE_CANDIDATE_RASTER_POLICY_VERSION,
            manifest_extras=manifest_extras,
            crop_id_prefix="pdftablecandidate_",
        )

    def resolve_table_region(
        self,
        *,
        pdf_bytes: bytes,
        pdf_sha256: str,
        page_number: int,
        candidate_bbox: list[float],
        candidate_page_bbox: list[float],
        candidate_strategy_ref: str,
    ) -> dict[str, Any]:
        if hashlib.sha256(pdf_bytes).hexdigest() != pdf_sha256:
            raise PdfTableRasterError("pdf_table_raster_pdf_checksum_mismatch")
        _require_bbox(candidate_bbox, "pdf_table_raster_candidate_bbox_invalid")
        _require_bbox(
            candidate_page_bbox, "pdf_table_raster_candidate_page_bbox_invalid"
        )
        document = self.fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if page_number < 1 or page_number > len(document):
                raise PdfTableRasterError("pdf_table_raster_page_invalid")
            page = document[page_number - 1]
            page_rect = [float(value) for value in page.rect]
            transformed, coordinate_transform = _candidate_to_page_coordinates(
                fitz_module=self.fitz,
                page=page,
                candidate_bbox=candidate_bbox,
                candidate_page_bbox=candidate_page_bbox,
            )
            clamped = _clamp_bbox(transformed, page_rect)
            if _bbox_area(clamped) <= 0:
                return _region_contract(
                    status="CROP_BLOCKED",
                    source_candidate_bbox=candidate_bbox,
                    source_candidate_page_bbox=candidate_page_bbox,
                    transformed_candidate_bbox=transformed,
                    resolved_bbox=None,
                    coordinate_transform=coordinate_transform,
                    reason_codes=["canonical_candidate_outside_page"],
                    diagnostics={},
                )
            lines = _page_lines(page)
            candidate_lines = [
                line
                for line in lines
                if _horizontal_overlap_fraction(line["bbox"], clamped) >= 0.12
                and _vertical_centers_overlap(line["bbox"], clamped)
            ]
            if not candidate_lines:
                return _region_contract(
                    status="CROP_BLOCKED",
                    source_candidate_bbox=candidate_bbox,
                    source_candidate_page_bbox=candidate_page_bbox,
                    transformed_candidate_bbox=transformed,
                    resolved_bbox=None,
                    coordinate_transform=coordinate_transform,
                    reason_codes=["canonical_candidate_has_no_text_geometry"],
                    diagnostics={"page_rotation": int(page.rotation)},
                )
            components = _vertical_components(
                candidate_lines,
                minimum_gap=self.config.canonical_component_gap_points,
            )
            scored = sorted(
                (
                    {
                        "lines": component,
                        "score": _component_score(component),
                        "bbox": _merge_bboxes([line["bbox"] for line in component]),
                    }
                    for component in components
                ),
                key=lambda item: (-item["score"], item["bbox"][1]),
            )
            reason_codes = ["candidate_coordinate_space_verified"]
            if len(scored) > 1:
                first, second = scored[0], scored[1]
                if (
                    first["score"] >= 8
                    and second["score"] >= 8
                    and second["score"] / first["score"] >= 0.9
                ):
                    return _region_contract(
                        status="CROP_AMBIGUOUS",
                        source_candidate_bbox=candidate_bbox,
                        source_candidate_page_bbox=candidate_page_bbox,
                        transformed_candidate_bbox=transformed,
                        resolved_bbox=None,
                        coordinate_transform=coordinate_transform,
                        reason_codes=["canonical_multiple_equal_table_components"],
                        diagnostics={
                            "component_count": len(scored),
                            "component_scores": [
                                round(float(item["score"]), 6) for item in scored
                            ],
                        },
                    )
                reason_codes.append("detached_candidate_components_trimmed")
            selected = scored[0]
            selected_index = next(
                index
                for index, component in enumerate(components)
                if component is selected["lines"]
            )
            region = list(clamped)
            if selected_index > 0:
                previous_bbox = _merge_bboxes(
                    [line["bbox"] for line in components[selected_index - 1]]
                )
                region[1] = max(
                    region[1],
                    max(
                        previous_bbox[3],
                        selected["bbox"][1]
                        - self.config.canonical_component_gap_points * 0.8,
                    ),
                )
            if selected_index + 1 < len(components):
                next_bbox = _merge_bboxes(
                    [line["bbox"] for line in components[selected_index + 1]]
                )
                region[3] = min(
                    region[3],
                    min(
                        next_bbox[1],
                        selected["bbox"][3]
                        + self.config.canonical_component_gap_points * 0.8,
                    ),
                )

            region, paragraph_trimmed = _trim_prose_barrier(
                region=region,
                lines=lines,
                candidate_strategy_ref=candidate_strategy_ref,
                page_height=page_rect[3] - page_rect[1],
            )
            if paragraph_trimmed:
                reason_codes.append("foreign_prose_barrier_trimmed")
            region, header_lines, ruled_neighbor_excluded = _expand_header(
                region=region,
                candidate_bbox=clamped,
                lines=lines,
                drawings=page.get_drawings(),
                search_points=self.config.canonical_header_search_points,
            )
            if header_lines:
                reason_codes.append("table_header_or_title_attached")
            if ruled_neighbor_excluded:
                reason_codes.append("separate_ruled_region_excluded")
            region, body_tail_lines = _expand_body_tail(
                region=region,
                candidate_bbox=clamped,
                lines=lines,
                page_height=page_rect[3] - page_rect[1],
            )
            if body_tail_lines:
                reason_codes.append("table_body_tail_attached")
            region, note_lines = _expand_notes(
                region=region,
                candidate_bbox=clamped,
                lines=lines,
                page_height=page_rect[3] - page_rect[1],
                search_fraction=self.config.canonical_note_search_fraction,
            )
            if note_lines:
                reason_codes.append("attached_notes_included")

            related_lines = [
                line
                for line in lines
                if _vertical_centers_overlap(line["bbox"], region)
                and _horizontal_overlap_fraction(line["bbox"], clamped) >= 0.08
            ]
            margin = self.config.canonical_outer_margin_points
            if related_lines:
                related_bbox = _merge_bboxes([line["bbox"] for line in related_lines])
                region[0] = min(region[0], related_bbox[0])
                region[1] = min(region[1], related_bbox[1])
                region[2] = max(region[2], related_bbox[2])
                region[3] = max(region[3], related_bbox[3])
            region = _clamp_bbox(
                [
                    region[0] - margin,
                    region[1] - margin,
                    region[2] + margin,
                    region[3] + margin,
                ],
                page_rect,
            )
            region, page_header_trimmed = _trim_page_header(
                region=region,
                candidate_bbox=clamped,
                lines=lines,
                page_bbox=page_rect,
            )
            if page_header_trimmed:
                reason_codes.append("page_header_excluded")
            region, page_footer_trimmed = _trim_page_footer(
                region=region,
                lines=lines,
                page_bbox=page_rect,
            )
            if page_footer_trimmed:
                reason_codes.append("page_footer_excluded")
            if _bbox_area(region) <= 0:
                return _region_contract(
                    status="CROP_BLOCKED",
                    source_candidate_bbox=candidate_bbox,
                    source_candidate_page_bbox=candidate_page_bbox,
                    transformed_candidate_bbox=transformed,
                    resolved_bbox=None,
                    coordinate_transform=coordinate_transform,
                    reason_codes=["canonical_resolved_region_empty"],
                    diagnostics={},
                )
            reason_codes.append("canonical_region_structurally_isolated")
            return _region_contract(
                status="CROP_CLEAN",
                source_candidate_bbox=candidate_bbox,
                source_candidate_page_bbox=candidate_page_bbox,
                transformed_candidate_bbox=transformed,
                resolved_bbox=region,
                coordinate_transform=coordinate_transform,
                reason_codes=reason_codes,
                diagnostics={
                    "page_rotation": int(page.rotation),
                    "candidate_lines_total": len(candidate_lines),
                    "component_count": len(components),
                    "selected_component_score": round(float(selected["score"]), 6),
                    "header_lines_attached": header_lines,
                    "ruled_neighbor_excluded": ruled_neighbor_excluded,
                    "body_tail_lines_attached": body_tail_lines,
                    "note_lines_attached": note_lines,
                    "page_header_trimmed": page_header_trimmed,
                    "page_footer_trimmed": page_footer_trimmed,
                    "full_page_render_count": 0,
                },
            )
        finally:
            document.close()

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
        """Compatibility entrypoint delegating to canonical table-region resolution."""

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
            page_points = [round(float(value), 6) for value in page_bbox]
        finally:
            document.close()
        return self.render_table_candidate(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref=document_ref,
            page_number=page_number,
            candidate_ref=candidate_ref,
            candidate_bbox=table_bbox,
            candidate_page_bbox=page_points,
            candidate_strategy_ref="vlm_outer_bbox_v2",
            detector_contract_version=detector_contract_version,
            detector_identity=detector_identity,
            dpi=dpi,
            detected_bbox_normalized=detected_bbox_normalized,
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


_NOTE_MARKER = re.compile(
    r"^(?:\((?:\d{1,2}|[a-z])\)|(?:\d{1,2}|[a-z])[.)]|[*†‡]|notes?:?)$",
    re.IGNORECASE,
)
_NUMBER_TOKEN = re.compile(r"(?:\d|[$%])")


def copy_numbers(value: list[float]) -> list[float]:
    return [round(float(item), 6) for item in value]


def _require_bbox(value: Any, code: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or not all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in value
        )
        or float(value[2]) <= float(value[0])
        or float(value[3]) <= float(value[1])
    ):
        raise PdfTableRasterError(code)


def _candidate_to_page_coordinates(
    *,
    fitz_module: Any,
    page: Any,
    candidate_bbox: list[float],
    candidate_page_bbox: list[float],
) -> tuple[list[float], dict[str, Any]]:
    source_page = fitz_module.Rect(candidate_page_bbox)
    page_rect = fitz_module.Rect(page.rect)
    media_box = fitz_module.Rect(page.mediabox)
    crop_box = fitz_module.Rect(page.cropbox)
    tolerance = 0.05

    def dimensions_match(left: Any, right: Any) -> bool:
        return (
            abs(float(left.width) - float(right.width)) <= tolerance
            and abs(float(left.height) - float(right.height)) <= tolerance
        )

    if dimensions_match(source_page, page_rect):
        translate_x = float(page_rect.x0) - float(source_page.x0)
        translate_y = float(page_rect.y0) - float(source_page.y0)
        kind = (
            "page_coordinate_identity"
            if abs(translate_x) <= tolerance and abs(translate_y) <= tolerance
            else "page_bbox_translation"
        )
    elif dimensions_match(source_page, media_box):
        if int(page.rotation) not in {0, 360}:
            raise PdfTableRasterError(
                "pdf_table_raster_rotated_media_coordinate_unsupported",
                crop_status="CROP_BLOCKED",
            )
        crop_position = page.cropbox_position
        translate_x = (
            float(page_rect.x0) - float(source_page.x0) - float(crop_position.x)
        )
        translate_y = (
            float(page_rect.y0) - float(source_page.y0) - float(crop_position.y)
        )
        kind = "media_to_cropbox_translation"
    elif dimensions_match(source_page, crop_box):
        translate_x = float(page_rect.x0) - float(source_page.x0)
        translate_y = float(page_rect.y0) - float(source_page.y0)
        kind = "cropbox_to_page_translation"
    else:
        raise PdfTableRasterError(
            "pdf_table_raster_candidate_coordinate_space_ambiguous",
            crop_status="CROP_BLOCKED",
            details={
                "candidate_page_bbox": copy_numbers(candidate_page_bbox),
                "page_bbox": copy_numbers(list(page_rect)),
                "media_bbox": copy_numbers(list(media_box)),
                "crop_bbox": copy_numbers(list(crop_box)),
            },
        )
    transformed = [
        float(candidate_bbox[0]) + translate_x,
        float(candidate_bbox[1]) + translate_y,
        float(candidate_bbox[2]) + translate_x,
        float(candidate_bbox[3]) + translate_y,
    ]
    return transformed, {
        "kind": kind,
        "translate_x": round(translate_x, 6),
        "translate_y": round(translate_y, 6),
        "rotation_degrees": int(page.rotation),
    }


def _page_lines(page: Any) -> list[dict[str, Any]]:
    groups: dict[tuple[int, int], list[tuple[Any, ...]]] = {}
    try:
        words = list(page.get_text("words") or [])
    except Exception as exc:
        raise PdfTableRasterError(
            "pdf_table_raster_page_text_geometry_unavailable"
        ) from exc
    for word in words:
        if len(word) < 8:
            continue
        key = (int(word[5]), int(word[6]))
        groups.setdefault(key, []).append(word)
    lines = []
    for key, values in groups.items():
        ordered = sorted(values, key=lambda item: (float(item[0]), int(item[7])))
        tokens = [str(item[4]) for item in ordered if str(item[4]).strip()]
        if not tokens:
            continue
        bbox = [
            min(float(item[0]) for item in ordered),
            min(float(item[1]) for item in ordered),
            max(float(item[2]) for item in ordered),
            max(float(item[3]) for item in ordered),
        ]
        numeric_tokens = sum(bool(_NUMBER_TOKEN.search(token)) for token in tokens)
        numeric_x_centers = [
            (float(item[0]) + float(item[2])) / 2.0
            for item in ordered
            if _NUMBER_TOKEN.search(str(item[4]))
        ]
        lines.append(
            {
                "line_key": [key[0], key[1]],
                "bbox": bbox,
                "tokens": tokens,
                "word_count": len(tokens),
                "numeric_tokens": numeric_tokens,
                "numeric_x_centers": numeric_x_centers,
                "numeric_fraction": numeric_tokens / len(tokens),
                "first_token": tokens[0],
            }
        )
    return sorted(lines, key=lambda item: (item["bbox"][1], item["bbox"][0]))


def _vertical_components(
    lines: list[dict[str, Any]], *, minimum_gap: float
) -> list[list[dict[str, Any]]]:
    ordered = sorted(lines, key=lambda item: (item["bbox"][1], item["bbox"][0]))
    if not ordered:
        return []
    heights = [max(0.1, line["bbox"][3] - line["bbox"][1]) for line in ordered]
    gap = max(float(minimum_gap), statistics.median(heights) * 3.5)
    components: list[list[dict[str, Any]]] = [[ordered[0]]]
    for line in ordered[1:]:
        previous_bottom = max(item["bbox"][3] for item in components[-1])
        if line["bbox"][1] - previous_bottom > gap:
            components.append([line])
        else:
            components[-1].append(line)
    return components


def _component_score(lines: list[dict[str, Any]]) -> float:
    numeric_tokens = sum(int(line["numeric_tokens"]) for line in lines)
    multi_token_lines = sum(1 for line in lines if int(line["word_count"]) >= 2)
    return float(len(lines) * 2 + numeric_tokens + multi_token_lines * 0.5)


def _trim_prose_barrier(
    *,
    region: list[float],
    lines: list[dict[str, Any]],
    candidate_strategy_ref: str,
    page_height: float,
) -> tuple[list[float], bool]:
    if (region[3] - region[1]) < page_height * 0.45:
        return region, False
    vertical_lines = [
        line for line in lines if _vertical_centers_overlap(line["bbox"], region)
    ]
    selected = [
        band
        for band in _horizontal_line_bands(vertical_lines)
        if _horizontal_overlap_fraction(band["bbox"], region) >= 0.2
    ]
    _annotate_table_alignment(selected, region=region)
    if len(selected) < 8:
        return region, False
    note_block_ids = {
        block_id
        for line in selected
        if _is_note_line(line)
        for block_id in line["block_ids"]
    }
    start_at = max(4, int(len(selected) * 0.3))
    for index in range(start_at, len(selected) - 2):
        run = selected[index : index + 3]
        if not all(_is_prose_line(line, region) for line in run):
            continue
        if any(
            block_id in note_block_ids for line in run for block_id in line["block_ids"]
        ):
            continue
        cutoff = run[0]["bbox"][1]
        if index > 0:
            heading = selected[index - 1]
            heading_gap = run[0]["bbox"][1] - heading["bbox"][3]
            if (
                heading_gap <= 22.0
                and int(heading["word_count"]) <= 6
                and float(heading["numeric_fraction"]) == 0.0
            ):
                cutoff = heading["bbox"][1]
        return [region[0], region[1], region[2], max(region[1], cutoff - 1.0)], True
    return region, False


def _is_prose_line(line: dict[str, Any], region: list[float]) -> bool:
    if _is_note_line(line) or line.get("table_alignment_supported") is True:
        return False
    width = line["bbox"][2] - line["bbox"][0]
    region_width = max(1.0, region[2] - region[0])
    return (
        int(line["word_count"]) >= 8
        and float(line["numeric_fraction"]) <= 0.25
        and width / region_width >= 0.45
    )


def _expand_header(
    *,
    region: list[float],
    candidate_bbox: list[float],
    lines: list[dict[str, Any]],
    drawings: list[dict[str, Any]],
    search_points: float,
) -> tuple[list[float], int, bool]:
    candidate_lines = [
        line
        for line in lines
        if line["bbox"][3] <= region[1] + 1.0
        and region[1] - line["bbox"][3] <= search_points
        and _horizontal_overlap_fraction(line["bbox"], candidate_bbox) >= 0.15
    ]
    cursor = region[1]
    included: list[dict[str, Any]] = []
    candidate_width = max(1.0, candidate_bbox[2] - candidate_bbox[0])
    by_block: dict[int, list[dict[str, Any]]] = {}
    for line in lines:
        by_block.setdefault(int(line["line_key"][0]), []).append(line)
    ruled_neighbor_excluded = False
    candidates = _horizontal_line_bands(candidate_lines)
    band_heights = [max(0.1, item["bbox"][3] - item["bbox"][1]) for item in candidates]
    contiguous_gap = (
        max(16.0, statistics.median(band_heights) * 2.0) if band_heights else 16.0
    )
    included_block_ids: set[int] = set()
    for line in sorted(candidates, key=lambda item: item["bbox"][1], reverse=True):
        gap = cursor - line["bbox"][3]
        if gap > 36.0 or len(included) >= 8:
            break
        if _wide_horizontal_rule_between(
            upper_bbox=line["bbox"],
            lower_y=cursor,
            candidate_bbox=candidate_bbox,
            drawings=drawings,
        ) and not _is_financial_statement_title(line):
            ruled_neighbor_excluded = True
            break
        line_width = line["bbox"][2] - line["bbox"][0]
        block_prose_barrier = False
        if float(line["numeric_fraction"]) < 0.2:
            for block_id in line["block_ids"]:
                block = by_block[block_id]
                block_words = sum(int(item["word_count"]) for item in block)
                block_numeric = sum(int(item["numeric_tokens"]) for item in block)
                if (
                    len(block) >= 2
                    and len(block) <= 12
                    and block_words >= 12
                    and block_words / len(block) >= 6
                    and block_numeric / max(1, block_words) < 0.2
                ):
                    block_prose_barrier = True
                    break
        belongs_to_large_block = any(
            len(by_block[block_id]) > 12 for block_id in line["block_ids"]
        )
        line_prose_barrier = (
            not belongs_to_large_block
            and (
                int(line["word_count"]) >= 10
                or (
                    int(line["word_count"]) >= 7
                    and str(line["last_token"]).endswith((".", ":", ";"))
                )
            )
            and line_width / candidate_width >= 0.75
            and float(line["numeric_fraction"]) < 0.2
        )
        contiguous_with_region = gap <= contiguous_gap
        attached_caption_block = contiguous_with_region and all(
            len(by_block[block_id]) <= 2
            or block_id in included_block_ids
            or not included
            for block_id in line["block_ids"]
        )
        standardized_units_caption = _is_financial_statement_units_caption(line)
        if (
            (block_prose_barrier or line_prose_barrier)
            and not attached_caption_block
            and not standardized_units_caption
        ):
            break
        if (
            attached_caption_block
            or standardized_units_caption
            or int(line["word_count"]) <= 10
            or float(line["numeric_fraction"]) > 0
            or line_width / candidate_width < 0.8
        ):
            included.append(line)
            included_block_ids.update(int(value) for value in line["block_ids"])
            cursor = line["bbox"][1]
    if not included:
        return region, 0, ruled_neighbor_excluded
    bbox = _merge_bboxes([line["bbox"] for line in included])
    return (
        [
            min(region[0], bbox[0]),
            min(region[1], bbox[1]),
            max(region[2], bbox[2]),
            region[3],
        ],
        len(included),
        ruled_neighbor_excluded,
    )


def _wide_horizontal_rule_between(
    *,
    upper_bbox: list[float],
    lower_y: float,
    candidate_bbox: list[float],
    drawings: list[dict[str, Any]],
) -> bool:
    """Keep header expansion from crossing a separate ruled table boundary."""

    if lower_y - upper_bbox[3] < 8.0:
        return False

    candidate_width = max(1.0, candidate_bbox[2] - candidate_bbox[0])
    wide_rule_y: list[float] = []
    for drawing in drawings:
        segments: list[tuple[float, float, float]] = []
        rect = drawing.get("rect")
        if rect is not None:
            x0, y0, x1, y1 = (float(value) for value in rect)
            if y1 - y0 <= 1.0:
                segments.append((x0, x1, (y0 + y1) / 2.0))
        for item in drawing.get("items", []):
            if item[0] == "l":
                start, end = item[1], item[2]
                if abs(float(start.y) - float(end.y)) <= 1.0:
                    segments.append(
                        (
                            min(float(start.x), float(end.x)),
                            max(float(start.x), float(end.x)),
                            (float(start.y) + float(end.y)) / 2.0,
                        )
                    )
            elif item[0] == "re":
                item_rect = item[1]
                segments.extend(
                    (
                        (float(item_rect.x0), float(item_rect.x1), float(item_rect.y0)),
                        (float(item_rect.x0), float(item_rect.x1), float(item_rect.y1)),
                    )
                )
        for x0, x1, y in segments:
            if x1 - x0 < candidate_width * 0.45:
                continue
            overlap = max(
                0.0,
                min(x1, candidate_bbox[2]) - max(x0, candidate_bbox[0]),
            )
            if overlap / candidate_width >= 0.45:
                wide_rule_y.append(y)
    center_y = (upper_bbox[1] + upper_bbox[3]) / 2.0
    has_upper_edge = any(upper_bbox[1] - 24.0 <= y <= center_y for y in wide_rule_y)
    has_lower_edge = any(center_y <= y < lower_y - 1.0 for y in wide_rule_y)
    return has_upper_edge and has_lower_edge


def _horizontal_line_bands(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    for line in sorted(lines, key=lambda item: (item["bbox"][1], item["bbox"][0])):
        center = (line["bbox"][1] + line["bbox"][3]) / 2.0
        target = next(
            (
                group
                for group in reversed(groups)
                if abs(
                    center
                    - statistics.median(
                        (item["bbox"][1] + item["bbox"][3]) / 2.0 for item in group
                    )
                )
                <= 3.0
            ),
            None,
        )
        if target is None:
            groups.append([line])
        else:
            target.append(line)
    result = []
    for group in groups:
        ordered = sorted(group, key=lambda item: item["bbox"][0])
        word_count = sum(int(item["word_count"]) for item in ordered)
        numeric_tokens = sum(int(item["numeric_tokens"]) for item in ordered)
        result.append(
            {
                "bbox": _merge_bboxes([item["bbox"] for item in ordered]),
                "word_count": word_count,
                "numeric_tokens": numeric_tokens,
                "numeric_x_centers": [
                    center
                    for item in ordered
                    for center in item.get("numeric_x_centers", [])
                ],
                "numeric_fraction": numeric_tokens / max(1, word_count),
                "first_token": ordered[0]["first_token"],
                "last_token": ordered[-1]["tokens"][-1],
                "tokens": [
                    token for item in ordered for token in item.get("tokens", [])
                ],
                "block_ids": sorted({int(item["line_key"][0]) for item in ordered}),
            }
        )
    return result


def _annotate_table_alignment(
    bands: list[dict[str, Any]], *, region: list[float]
) -> None:
    """Mark repeated numeric columns without interpreting their values."""

    tolerance = max(6.0, (region[2] - region[0]) * 0.025)
    numeric_column_start = region[0] + (region[2] - region[0]) * 0.55
    band_heights = [max(0.1, band["bbox"][3] - band["bbox"][1]) for band in bands]
    continuity_y = max(24.0, statistics.median(band_heights) * 4.0)
    for index, band in enumerate(bands):
        centers = [
            center
            for center in band.get("numeric_x_centers", [])
            if center >= numeric_column_start
        ]
        band_center_y = (band["bbox"][1] + band["bbox"][3]) / 2.0
        peer_centers = []
        for peer in bands[max(0, index - 4) : index + 5]:
            if peer is band:
                continue
            peer_center_y = (peer["bbox"][1] + peer["bbox"][3]) / 2.0
            if abs(peer_center_y - band_center_y) > continuity_y:
                continue
            peer_centers.extend(
                center
                for center in peer.get("numeric_x_centers", [])
                if center >= numeric_column_start
            )
        matches = sum(
            any(abs(float(center) - float(peer)) <= tolerance for peer in peer_centers)
            for center in centers
        )
        band["table_alignment_match_count"] = matches
        band["table_alignment_supported"] = matches >= 1


def _expand_body_tail(
    *,
    region: list[float],
    candidate_bbox: list[float],
    lines: list[dict[str, Any]],
    page_height: float,
) -> tuple[list[float], int]:
    """Complete contiguous rows that preserve the candidate's numeric grid."""

    relevant = [
        line
        for line in lines
        if line["bbox"][1] <= region[3] + page_height * 0.18
        and line["bbox"][3] >= region[1]
        and _horizontal_overlap_fraction(line["bbox"], candidate_bbox) >= 0.08
    ]
    bands = _horizontal_line_bands(relevant)
    if not bands:
        return region, 0
    _annotate_table_alignment(bands, region=region)
    band_heights = [max(0.1, band["bbox"][3] - band["bbox"][1]) for band in bands]
    maximum_gap = max(18.0, statistics.median(band_heights) * 2.0)
    included_blocks = {
        block_id
        for band in bands
        if _vertical_centers_overlap(band["bbox"], region)
        for block_id in band["block_ids"]
    }
    included: list[dict[str, Any]] = []
    cursor = region[3]
    for band in bands:
        if band["bbox"][1] < region[3] - 1.0:
            continue
        gap = band["bbox"][1] - cursor
        if gap > maximum_gap or len(included) >= 12 or _is_note_line(band):
            break
        aligned_row = (
            band.get("table_alignment_supported") is True
            and int(band["numeric_tokens"]) >= 1
        )
        same_block_continuation = (
            int(band["numeric_tokens"]) == 0
            and any(block_id in included_blocks for block_id in band["block_ids"])
            and gap <= 12.0
        )
        if not aligned_row and not same_block_continuation:
            break
        included.append(band)
        included_blocks.update(int(value) for value in band["block_ids"])
        cursor = max(cursor, band["bbox"][3])
    if not included:
        return region, 0
    bbox = _merge_bboxes([band["bbox"] for band in included])
    return [
        min(region[0], bbox[0]),
        region[1],
        max(region[2], bbox[2]),
        max(region[3], bbox[3]),
    ], len(included)


def _expand_notes(
    *,
    region: list[float],
    candidate_bbox: list[float],
    lines: list[dict[str, Any]],
    page_height: float,
    search_fraction: float,
) -> tuple[list[float], int]:
    below = [
        line
        for line in lines
        if (
            line["bbox"][1] >= region[3] - 1.0
            or (
                _is_note_line(line)
                and line["bbox"][3] >= region[3] - 1.0
            )
        )
        and max(0.0, line["bbox"][1] - region[3])
        <= page_height * search_fraction
        and _horizontal_overlap_fraction(line["bbox"], candidate_bbox) >= 0.08
    ]
    if not below:
        return region, 0
    ordered = sorted(below, key=lambda item: (item["bbox"][1], item["bbox"][0]))
    first = ordered[0]
    first_gap = max(0.0, first["bbox"][1] - region[3])
    note_starts_inside_candidate = first["bbox"][1] <= candidate_bbox[3] + 1.0
    if (
        not _is_note_line(first)
        or (first_gap > 30.0 and not note_starts_inside_candidate)
    ):
        return region, 0
    included = [first]
    included_blocks = {int(first["line_key"][0])}
    cursor = first["bbox"][3]
    for line in ordered[1:]:
        gap = line["bbox"][1] - cursor
        if gap > 24.0:
            break
        block_id = int(line["line_key"][0])
        is_marker = _is_note_line(line)
        if not is_marker and block_id not in included_blocks:
            break
        if gap > 14.0 and not is_marker:
            break
        included.append(line)
        included_blocks.add(block_id)
        cursor = max(cursor, line["bbox"][3])
    bbox = _merge_bboxes([line["bbox"] for line in included])
    return [
        min(region[0], bbox[0]),
        region[1],
        max(region[2], bbox[2]),
        max(region[3], bbox[3]),
    ], len(included)


def _is_note_line(line: dict[str, Any]) -> bool:
    first_token = str(line.get("first_token") or "").strip()
    if _NOTE_MARKER.match(first_token):
        return True
    normalized = " ".join(str(token) for token in line.get("tokens", [])).lower()
    return normalized.startswith(
        (
            "see accompanying notes",
            "see notes to",
            "the accompanying notes are",
        )
    )


def _is_financial_statement_title(line: dict[str, Any]) -> bool:
    """Recognize a compact standardized statement title, independent of issuer."""

    tokens = [str(token) for token in line.get("tokens", [])]
    if not 2 <= len(tokens) <= 12 or int(line.get("numeric_tokens") or 0) != 0:
        return False
    text = " ".join(tokens)
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return False
    uppercase_fraction = sum(character.isupper() for character in letters) / len(letters)
    normalized = " ".join(re.findall(r"[a-z]+", text.lower()))
    standardized_title = (
        " statement " in f" {normalized} "
        or " statements " in f" {normalized} "
        or " balance sheet " in f" {normalized} "
        or " balance sheets " in f" {normalized} "
    )
    return uppercase_fraction >= 0.65 and standardized_title


def _is_financial_statement_units_caption(line: dict[str, Any]) -> bool:
    """Recognize a parenthetical units qualifier attached to a statement title."""

    tokens = [str(token) for token in line.get("tokens", [])]
    if not 3 <= len(tokens) <= 16:
        return False
    normalized = " ".join(tokens).strip().lower()
    return (
        normalized.startswith("(in ")
        and normalized.endswith(")")
        and any(
            unit in normalized
            for unit in (" dollars", " thousands", " millions", " billions")
        )
    )


def _trim_page_header(
    *,
    region: list[float],
    candidate_bbox: list[float],
    lines: list[dict[str, Any]],
    page_bbox: list[float],
) -> tuple[list[float], bool]:
    """Exclude a compact top-of-page band isolated from the table body."""

    page_height = max(1.0, page_bbox[3] - page_bbox[1])
    bands = _horizontal_line_bands(
        [line for line in lines if _vertical_centers_overlap(line["bbox"], region)]
    )
    ordered = sorted(bands, key=lambda item: item["bbox"][1])
    if len(ordered) < 2:
        return region, False
    band_heights = [max(0.1, band["bbox"][3] - band["bbox"][1]) for band in ordered]
    isolated_gap = max(12.0, statistics.median(band_heights) * 1.15)
    for index, band in enumerate(ordered[:-1]):
        following = ordered[index + 1]
        next_gap = following["bbox"][1] - band["bbox"][3]
        just_above_candidate = 0.0 <= candidate_bbox[1] - band["bbox"][3] <= 16.0
        isolated_header_band = (
            band["bbox"][1] <= page_bbox[1] + page_height * 0.08
            and int(band["word_count"]) <= 12
            and int(band["numeric_tokens"]) <= 2
            and not _is_financial_statement_title(band)
            and int(following["numeric_tokens"]) == 0
            and int(following["word_count"]) <= 12
            and next_gap >= isolated_gap
            and not just_above_candidate
        )
        if isolated_header_band:
            return [
                region[0],
                max(region[1], following["bbox"][1] - 0.5),
                region[2],
                region[3],
            ], True
    return region, False


def _trim_page_footer(
    *,
    region: list[float],
    lines: list[dict[str, Any]],
    page_bbox: list[float],
) -> tuple[list[float], bool]:
    """Exclude isolated page-number bands even when a detector reaches the footer."""

    page_height = max(1.0, page_bbox[3] - page_bbox[1])
    page_width = max(1.0, page_bbox[2] - page_bbox[0])
    bands = _horizontal_line_bands(
        [line for line in lines if _vertical_centers_overlap(line["bbox"], region)]
    )
    ordered = sorted(bands, key=lambda item: item["bbox"][1])
    band_heights = [max(0.1, band["bbox"][3] - band["bbox"][1]) for band in ordered]
    isolated_gap = max(
        12.0,
        statistics.median(band_heights) * 1.5 if band_heights else 12.0,
    )
    for index, band in enumerate(ordered):
        width = band["bbox"][2] - band["bbox"][0]
        in_footer_zone = band["bbox"][1] >= page_bbox[1] + page_height * 0.88
        compact_page_number = (
            in_footer_zone
            and int(band["word_count"]) <= 3
            and int(band["numeric_tokens"]) >= 1
            and width / page_width <= 0.12
        )
        previous_gap = (
            band["bbox"][1] - ordered[index - 1]["bbox"][3] if index > 0 else 0.0
        )
        isolated_footer_band = (
            band["bbox"][1] >= page_bbox[1] + page_height * 0.94
            and int(band["word_count"]) <= 7
            and int(band["numeric_tokens"]) <= 2
            and previous_gap >= isolated_gap
        )
        if compact_page_number or isolated_footer_band:
            return [
                region[0],
                region[1],
                region[2],
                min(region[3], band["bbox"][1] - 0.5),
            ], True
    return region, False


def _region_contract(
    *,
    status: str,
    source_candidate_bbox: list[float],
    source_candidate_page_bbox: list[float],
    transformed_candidate_bbox: list[float],
    resolved_bbox: list[float] | None,
    coordinate_transform: dict[str, Any],
    reason_codes: list[str],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": CANONICAL_TABLE_REGION_SCHEMA,
        "policy_version": CANONICAL_TABLE_REGION_POLICY_VERSION,
        "status": status,
        "source_candidate_bbox": copy_numbers(source_candidate_bbox),
        "source_candidate_page_bbox": copy_numbers(source_candidate_page_bbox),
        "transformed_candidate_bbox": copy_numbers(transformed_candidate_bbox),
        "resolved_bbox": (
            copy_numbers(resolved_bbox) if resolved_bbox is not None else None
        ),
        "coordinate_transform": coordinate_transform,
        "reason_codes": sorted(set(reason_codes)),
        "diagnostics": diagnostics,
        "shared_region_consumers": [
            "image_crop",
            "future_source_text",
            "provenance",
            "diagnostics",
        ],
        "per_table_exception_used": False,
        "false_clean_allowed": False,
    }


def _merge_bboxes(values: list[list[float]]) -> list[float]:
    return [
        min(value[0] for value in values),
        min(value[1] for value in values),
        max(value[2] for value in values),
        max(value[3] for value in values),
    ]


def _clamp_bbox(value: list[float], page_bbox: list[float]) -> list[float]:
    return [
        max(float(page_bbox[0]), float(value[0])),
        max(float(page_bbox[1]), float(value[1])),
        min(float(page_bbox[2]), float(value[2])),
        min(float(page_bbox[3]), float(value[3])),
    ]


def _bbox_area(value: list[float]) -> float:
    return max(0.0, value[2] - value[0]) * max(0.0, value[3] - value[1])


def _vertical_centers_overlap(inner: list[float], outer: list[float]) -> bool:
    center = (float(inner[1]) + float(inner[3])) / 2.0
    return float(outer[1]) <= center <= float(outer[3])


def _horizontal_overlap_fraction(left: list[float], right: list[float]) -> float:
    overlap = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    denominator = max(1.0, min(left[2] - left[0], right[2] - right[0]))
    return overlap / denominator
