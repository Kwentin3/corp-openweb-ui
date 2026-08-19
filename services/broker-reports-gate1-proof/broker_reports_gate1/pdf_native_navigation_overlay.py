from __future__ import annotations

import base64
import hashlib
import math
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest


NATIVE_NAVIGATION_OVERLAY_SCHEMA = (
    "broker_reports_pdf_native_navigation_overlay_g5101_v1"
)
NATIVE_NAVIGATION_OVERLAY_POLICY = "pdf_native_point_navigation_g5101_v1"
FACTORY_REQUIRED = (
    "NativePdfPointNavigationOverlayFactory.create consumes only a verified "
    "PdfTableRasterFactory.create full-page render"
)
FORBIDDEN = (
    "The overlay must not render source PDFs, resize page pixels, inspect text, "
    "detect tables, add source meaning, or enter product routing"
)


class NativePdfPointNavigationOverlayError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class NativePdfPointNavigationOverlayConfig:
    renderer_version: str = "1.26.5"
    left_margin_pixels: int = 84
    top_margin_pixels: int = 58
    right_margin_pixels: int = 18
    bottom_margin_pixels: int = 18
    minor_interval_points: float = 18.0
    major_interval_points: float = 72.0
    maximum_width: int = 4096
    maximum_height: int = 4096
    maximum_png_bytes: int = 8 * 1024 * 1024


class NativePdfPointNavigationOverlayFactory:
    def __init__(
        self, config: NativePdfPointNavigationOverlayConfig | None = None
    ) -> None:
        self.config = config or NativePdfPointNavigationOverlayConfig()

    def create(self) -> "NativePdfPointNavigationOverlay":
        config = self.config
        if min(
            config.left_margin_pixels,
            config.top_margin_pixels,
            config.right_margin_pixels,
            config.bottom_margin_pixels,
        ) < 0:
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_margin_invalid"
            )
        if (
            not math.isfinite(config.minor_interval_points)
            or not math.isfinite(config.major_interval_points)
            or config.minor_interval_points <= 0
            or config.major_interval_points <= 0
            or config.major_interval_points < config.minor_interval_points
            or not math.isclose(
                config.major_interval_points / config.minor_interval_points,
                round(
                    config.major_interval_points / config.minor_interval_points
                ),
                abs_tol=1e-9,
            )
        ):
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_interval_invalid"
            )
        try:
            import fitz
        except ImportError as exc:
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_dependency_unavailable"
            ) from exc
        if fitz.VersionBind != config.renderer_version:
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_renderer_version_mismatch"
            )
        return NativePdfPointNavigationOverlay(config, fitz)


class NativePdfPointNavigationOverlay:
    def __init__(
        self, config: NativePdfPointNavigationOverlayConfig, fitz_module: Any
    ) -> None:
        self.config = config
        self.fitz = fitz_module

    def apply(
        self,
        *,
        page_png_bytes: bytes,
        raster_manifest: dict[str, Any],
        expected_page_bbox: list[float],
    ) -> dict[str, Any]:
        page_bbox = _bbox(expected_page_bbox)
        self._validate_input(
            page_png_bytes=page_png_bytes,
            raster_manifest=raster_manifest,
            expected_page_bbox=page_bbox,
        )
        input_width = int(raster_manifest["width"])
        input_height = int(raster_manifest["height"])
        output_width = (
            self.config.left_margin_pixels
            + input_width
            + self.config.right_margin_pixels
        )
        output_height = (
            self.config.top_margin_pixels
            + input_height
            + self.config.bottom_margin_pixels
        )
        if (
            output_width > self.config.maximum_width
            or output_height > self.config.maximum_height
        ):
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_dimension_budget_exceeded"
            )

        document = self.fitz.open()
        page = document.new_page(width=output_width, height=output_height)
        page_rect = self.fitz.Rect(
            self.config.left_margin_pixels,
            self.config.top_margin_pixels,
            self.config.left_margin_pixels + input_width,
            self.config.top_margin_pixels + input_height,
        )
        page.insert_image(page_rect, stream=page_png_bytes, keep_proportion=False)
        transform = raster_manifest["source_to_pixel_transform"]
        scale_x = float(transform["scale_x"])
        scale_y = float(transform["scale_y"])
        translate_x = float(transform["translate_source_x"])
        translate_y = float(transform["translate_source_y"])
        self._draw_grid(
            page=page,
            page_rect=page_rect,
            page_bbox=page_bbox,
            scale_x=scale_x,
            scale_y=scale_y,
            translate_x=translate_x,
            translate_y=translate_y,
        )
        pixmap = page.get_pixmap(matrix=self.fitz.Identity, alpha=False, annots=False)
        png = pixmap.tobytes("png")
        document.close()
        if len(png) > self.config.maximum_png_bytes:
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_encoded_budget_exceeded"
            )
        png_sha256 = hashlib.sha256(png).hexdigest()
        input_sha256 = hashlib.sha256(page_png_bytes).hexdigest()
        overlay_id = "pdfnativegrid_" + stable_digest(
            [
                input_sha256,
                page_bbox,
                self.config.minor_interval_points,
                self.config.major_interval_points,
                output_width,
                output_height,
                png_sha256,
            ],
            length=24,
        )
        return {
            "manifest": {
                "schema_version": NATIVE_NAVIGATION_OVERLAY_SCHEMA,
                "policy_version": NATIVE_NAVIGATION_OVERLAY_POLICY,
                "overlay_id": overlay_id,
                "input_raster_sha256": input_sha256,
                "input_raster_manifest_hash": raster_manifest.get(
                    "manifest_hash"
                ),
                "output_png_sha256": png_sha256,
                "output_png_bytes": len(png),
                "input_width": input_width,
                "input_height": input_height,
                "output_width": int(pixmap.width),
                "output_height": int(pixmap.height),
                "page_pixel_offset": [
                    self.config.left_margin_pixels,
                    self.config.top_margin_pixels,
                ],
                "native_coordinate_space": "pdfplumber_top_left_points",
                "native_coordinate_bounds": page_bbox,
                "plan_to_pdfplumber_transform": "identity",
                "minor_interval_points": self.config.minor_interval_points,
                "major_interval_points": self.config.major_interval_points,
                "source_page_pixels_resized": False,
                "source_page_pixels_covered_by_labels": False,
                "table_detection_performed": False,
                "source_text_inspected": False,
                "source_meaning_added": False,
                "renderer": "pymupdf_overlay_only",
                "renderer_version": self.fitz.VersionBind,
            },
            "private_png_base64": base64.b64encode(png).decode("ascii"),
        }

    def _validate_input(
        self,
        *,
        page_png_bytes: bytes,
        raster_manifest: dict[str, Any],
        expected_page_bbox: list[float],
    ) -> None:
        if (
            raster_manifest.get("render_scope") != "full_page"
            or raster_manifest.get("full_page_identity_verified") is not True
            or raster_manifest.get("source_coordinate_space")
            != "pdf_top_left_points"
            or raster_manifest.get("lossless") is not True
            or raster_manifest.get("silent_resize_performed") is not False
            or raster_manifest.get("page_rotation") != 0
            or raster_manifest.get("applied_rotation") != 0
        ):
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_raster_contract_invalid"
            )
        if _bbox(raster_manifest.get("actual_page_bbox")) != expected_page_bbox:
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_page_bbox_mismatch"
            )
        if hashlib.sha256(page_png_bytes).hexdigest() != raster_manifest.get(
            "png_sha256"
        ):
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_png_hash_mismatch"
            )
        try:
            pixmap = self.fitz.Pixmap(page_png_bytes)
        except Exception as exc:
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_png_invalid"
            ) from exc
        if (
            int(pixmap.width) != int(raster_manifest.get("width") or 0)
            or int(pixmap.height) != int(raster_manifest.get("height") or 0)
        ):
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_png_dimensions_mismatch"
            )
        transform = raster_manifest.get("source_to_pixel_transform") or {}
        if (
            not _positive_number(transform.get("scale_x"))
            or not _positive_number(transform.get("scale_y"))
            or not _number(transform.get("translate_source_x"))
            or not _number(transform.get("translate_source_y"))
        ):
            raise NativePdfPointNavigationOverlayError(
                "g5101_overlay_source_transform_invalid"
            )

    def _draw_grid(
        self,
        *,
        page: Any,
        page_rect: Any,
        page_bbox: list[float],
        scale_x: float,
        scale_y: float,
        translate_x: float,
        translate_y: float,
    ) -> None:
        x_values = _grid_values(
            page_bbox[0], page_bbox[2], self.config.minor_interval_points
        )
        y_values = _grid_values(
            page_bbox[1], page_bbox[3], self.config.minor_interval_points
        )
        minor = page.new_shape()
        major = page.new_shape()
        for value in x_values:
            pixel = page_rect.x0 + (value + translate_x) * scale_x
            target = (
                major
                if _is_major(
                    value, page_bbox[0], self.config.major_interval_points
                )
                else minor
            )
            target.draw_line(
                self.fitz.Point(pixel, page_rect.y0),
                self.fitz.Point(pixel, page_rect.y1),
            )
        for value in y_values:
            pixel = page_rect.y0 + (value + translate_y) * scale_y
            target = (
                major
                if _is_major(
                    value, page_bbox[1], self.config.major_interval_points
                )
                else minor
            )
            target.draw_line(
                self.fitz.Point(page_rect.x0, pixel),
                self.fitz.Point(page_rect.x1, pixel),
            )
        minor.finish(color=(0.20, 0.45, 0.75), width=0.3, stroke_opacity=0.12)
        minor.commit()
        major.finish(color=(0.05, 0.25, 0.70), width=0.65, stroke_opacity=0.42)
        major.commit()
        page.draw_rect(page_rect, color=(0.05, 0.20, 0.55), width=1.0)

        label_x_values = _grid_values(
            page_bbox[0], page_bbox[2], self.config.major_interval_points
        )
        label_y_values = _grid_values(
            page_bbox[1], page_bbox[3], self.config.major_interval_points
        )
        for value in label_x_values:
            pixel = page_rect.x0 + (value + translate_x) * scale_x
            label = _label(value)
            page.insert_text(
                self.fitz.Point(pixel - len(label) * 2.7, page_rect.y0 - 13),
                label,
                fontsize=9,
                fontname="cour",
                color=(0.65, 0.05, 0.12),
            )
        for value in label_y_values:
            pixel = page_rect.y0 + (value + translate_y) * scale_y
            page.insert_text(
                self.fitz.Point(8, pixel + 3),
                _label(value),
                fontsize=9,
                fontname="cour",
                color=(0.05, 0.25, 0.65),
            )
        page.insert_text(
            self.fitz.Point(page_rect.x0, 18),
            "pdfplumber native points: X ->",
            fontsize=10,
            fontname="cobo",
            color=(0.45, 0.02, 0.08),
        )
        page.insert_text(
            self.fitz.Point(8, 38),
            "TOP",
            fontsize=10,
            fontname="cobo",
            color=(0.02, 0.18, 0.55),
        )


def _bbox(value: Any) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(not _number(item) for item in value)
    ):
        raise NativePdfPointNavigationOverlayError("g5101_overlay_bbox_invalid")
    result = [round(float(item), 6) for item in value]
    if result[2] <= result[0] or result[3] <= result[1]:
        raise NativePdfPointNavigationOverlayError("g5101_overlay_bbox_invalid")
    return result


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _positive_number(value: Any) -> bool:
    return _number(value) and float(value) > 0


def _grid_values(start: float, end: float, interval: float) -> list[float]:
    values = [start]
    cursor = math.ceil((start + 1e-9) / interval) * interval
    while cursor < end - 1e-9:
        if cursor > start + 1e-9:
            values.append(round(cursor, 6))
        cursor += interval
    if not math.isclose(values[-1], end, abs_tol=1e-9):
        values.append(end)
    return values


def _is_major(value: float, origin: float, interval: float) -> bool:
    quotient = (value - origin) / interval
    return math.isclose(quotient, round(quotient), abs_tol=1e-9)


def _label(value: float) -> str:
    return f"{value:.0f}" if math.isclose(value, round(value)) else f"{value:.1f}"
