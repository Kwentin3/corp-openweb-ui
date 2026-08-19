from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest


RUNTIME_STATUS = "research_only"
GEMINI_NORMALIZED_TABLE_BOX_SCHEMA_VERSION = (
    "broker_reports_gemini_normalized_table_boxes_g5102_v1"
)
FACTORY_REQUIRED = (
    "GeminiNormalizedTableBoxProjectionFactory.create is the only G5.102 "
    "normalized box_2d to PDF-point projection entrypoint"
)
FORBIDDEN = (
    "G5.102 must not render PDFs, call a provider, inspect source text, infer "
    "table columns, extract values, or enter product routing"
)

GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tables"],
    "properties": {
        "tables": {
            "type": "array",
            "description": (
                "All visible data tables and table continuations in top-to-bottom "
                "order. Return an empty array when none are visible."
            ),
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["box_2d"],
                "properties": {
                    "box_2d": {
                        "type": "array",
                        "description": (
                            "The table bounding box as exactly [ymin, xmin, "
                            "ymax, xmax], using integer coordinates normalized "
                            "from 0 to 1000 relative to the entire input image."
                        ),
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 1000,
                        },
                    }
                },
            },
        }
    },
}


class GeminiNormalizedTableBoxError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class GeminiNormalizedTableBoxProjectionConfig:
    coordinate_normalizer: int = 1000
    maximum_tables: int = 12


class GeminiNormalizedTableBoxProjectionFactory:
    def __init__(
        self, config: GeminiNormalizedTableBoxProjectionConfig | None = None
    ) -> None:
        self.config = config or GeminiNormalizedTableBoxProjectionConfig()

    def create(self) -> "GeminiNormalizedTableBoxProjection":
        if self.config.coordinate_normalizer != 1000:
            raise GeminiNormalizedTableBoxError(
                "g5102_coordinate_normalizer_not_documented"
            )
        if self.config.maximum_tables < 1:
            raise GeminiNormalizedTableBoxError("g5102_maximum_tables_invalid")
        return GeminiNormalizedTableBoxProjection(self.config)


class GeminiNormalizedTableBoxProjection:
    def __init__(self, config: GeminiNormalizedTableBoxProjectionConfig) -> None:
        self.config = config

    def project(
        self,
        *,
        provider_value: Any,
        raster_manifest: dict[str, Any],
        expected_page_bbox: list[float],
    ) -> dict[str, Any]:
        page_bbox = _bbox(expected_page_bbox, "g5102_page_bbox_invalid")
        transform = self._validated_transform(
            raster_manifest=raster_manifest,
            page_bbox=page_bbox,
        )
        normalized_boxes = self._validated_provider_value(provider_value)
        projected = []
        for ordinal, normalized in enumerate(normalized_boxes, 1):
            ymin, xmin, ymax, xmax = normalized
            x0 = self._source_x(
                normalized=xmin,
                width=transform["width"],
                scale=transform["scale_x"],
                translate=transform["translate_x"],
            )
            top = self._source_y(
                normalized=ymin,
                height=transform["height"],
                scale=transform["scale_y"],
                translate=transform["translate_y"],
            )
            x1 = self._source_x(
                normalized=xmax,
                width=transform["width"],
                scale=transform["scale_x"],
                translate=transform["translate_x"],
            )
            bottom = self._source_y(
                normalized=ymax,
                height=transform["height"],
                scale=transform["scale_y"],
                translate=transform["translate_y"],
            )
            native_bbox = [
                round(x0, 6),
                round(top, 6),
                round(x1, 6),
                round(bottom, 6),
            ]
            self._validate_projected_bbox(native_bbox, page_bbox)
            projected.append(
                {
                    "ordinal": ordinal,
                    "box_2d_normalized": list(normalized),
                    "bbox_pdf_points": native_bbox,
                }
            )

        result = {
            "schema_version": GEMINI_NORMALIZED_TABLE_BOX_SCHEMA_VERSION,
            "runtime_status": RUNTIME_STATUS,
            "coordinate_contract": (
                "gemini_box_2d_ymin_xmin_ymax_xmax_normalized_0_1000"
            ),
            "coordinate_normalizer": self.config.coordinate_normalizer,
            "input_raster_manifest_hash": raster_manifest.get("manifest_hash"),
            "page_bbox_pdf_points": page_bbox,
            "tables": projected,
            "model_values_used_as_source_literals": False,
            "table_structure_inferred": False,
        }
        result["projection_hash"] = stable_digest(
            [
                result["schema_version"],
                result["coordinate_contract"],
                result["input_raster_manifest_hash"],
                result["page_bbox_pdf_points"],
                result["tables"],
            ],
            length=64,
        )
        return result

    def _validated_provider_value(self, value: Any) -> list[list[int]]:
        if not isinstance(value, dict) or set(value) != {"tables"}:
            raise GeminiNormalizedTableBoxError("g5102_response_shape_invalid")
        tables = value.get("tables")
        if not isinstance(tables, list) or len(tables) > self.config.maximum_tables:
            raise GeminiNormalizedTableBoxError("g5102_tables_invalid")
        boxes = []
        previous_ymin: int | None = None
        for table in tables:
            if not isinstance(table, dict) or set(table) != {"box_2d"}:
                raise GeminiNormalizedTableBoxError("g5102_table_shape_invalid")
            box = table.get("box_2d")
            if (
                not isinstance(box, list)
                or len(box) != 4
                or any(not isinstance(item, int) or isinstance(item, bool) for item in box)
            ):
                raise GeminiNormalizedTableBoxError("g5102_box_2d_invalid")
            ymin, xmin, ymax, xmax = box
            if any(
                item < 0 or item > self.config.coordinate_normalizer for item in box
            ):
                raise GeminiNormalizedTableBoxError("g5102_box_2d_out_of_range")
            if ymin >= ymax or xmin >= xmax:
                raise GeminiNormalizedTableBoxError("g5102_box_2d_order_invalid")
            if previous_ymin is not None and ymin < previous_ymin:
                raise GeminiNormalizedTableBoxError(
                    "g5102_tables_not_top_to_bottom"
                )
            previous_ymin = ymin
            boxes.append(list(box))
        return boxes

    def _validated_transform(
        self,
        *,
        raster_manifest: dict[str, Any],
        page_bbox: list[float],
    ) -> dict[str, float]:
        if (
            not isinstance(raster_manifest, dict)
            or raster_manifest.get("render_scope") != "full_page"
            or raster_manifest.get("full_page_identity_verified") is not True
            or raster_manifest.get("source_coordinate_space")
            != "pdf_top_left_points"
            or raster_manifest.get("pixel_coordinate_space")
            != "crop_top_left_pixels"
            or raster_manifest.get("lossless") is not True
            or raster_manifest.get("silent_resize_performed") is not False
            or raster_manifest.get("page_rotation") != 0
            or raster_manifest.get("applied_rotation") != 0
        ):
            raise GeminiNormalizedTableBoxError("g5102_raster_manifest_invalid")
        if _bbox(
            raster_manifest.get("actual_page_bbox"),
            "g5102_raster_page_bbox_invalid",
        ) != page_bbox or _bbox(
            raster_manifest.get("rendered_bbox"),
            "g5102_rendered_bbox_invalid",
        ) != page_bbox:
            raise GeminiNormalizedTableBoxError("g5102_raster_page_bbox_mismatch")
        width = _positive_number(raster_manifest.get("width"))
        height = _positive_number(raster_manifest.get("height"))
        source_transform = raster_manifest.get("source_to_pixel_transform")
        if not isinstance(source_transform, dict):
            raise GeminiNormalizedTableBoxError("g5102_raster_transform_invalid")
        scale_x = _positive_number(source_transform.get("scale_x"))
        scale_y = _positive_number(source_transform.get("scale_y"))
        translate_x = _number(source_transform.get("translate_source_x"))
        translate_y = _number(source_transform.get("translate_source_y"))
        expected_scale_x = width / (page_bbox[2] - page_bbox[0])
        expected_scale_y = height / (page_bbox[3] - page_bbox[1])
        if (
            not math.isclose(scale_x, expected_scale_x, rel_tol=0, abs_tol=1e-8)
            or not math.isclose(scale_y, expected_scale_y, rel_tol=0, abs_tol=1e-8)
            or not math.isclose(translate_x, -page_bbox[0], rel_tol=0, abs_tol=1e-8)
            or not math.isclose(translate_y, -page_bbox[1], rel_tol=0, abs_tol=1e-8)
        ):
            raise GeminiNormalizedTableBoxError("g5102_raster_transform_mismatch")
        return {
            "width": width,
            "height": height,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "translate_x": translate_x,
            "translate_y": translate_y,
        }

    def _source_x(
        self, *, normalized: int, width: float, scale: float, translate: float
    ) -> float:
        pixel = normalized / self.config.coordinate_normalizer * width
        return pixel / scale - translate

    def _source_y(
        self, *, normalized: int, height: float, scale: float, translate: float
    ) -> float:
        pixel = normalized / self.config.coordinate_normalizer * height
        return pixel / scale - translate

    @staticmethod
    def _validate_projected_bbox(
        value: list[float], page_bbox: list[float]
    ) -> None:
        x0, top, x1, bottom = value
        if x0 >= x1 or top >= bottom:
            raise GeminiNormalizedTableBoxError("g5102_projected_bbox_invalid")
        epsilon = 1e-6
        if (
            x0 < page_bbox[0] - epsilon
            or top < page_bbox[1] - epsilon
            or x1 > page_bbox[2] + epsilon
            or bottom > page_bbox[3] + epsilon
        ):
            raise GeminiNormalizedTableBoxError(
                "g5102_projected_bbox_outside_page"
            )


def _bbox(value: Any, code: str) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(not _finite_number(item) for item in value)
    ):
        raise GeminiNormalizedTableBoxError(code)
    result = [round(float(item), 6) for item in value]
    if result[0] > result[2] or result[1] > result[3]:
        raise GeminiNormalizedTableBoxError(code)
    if result[0] == result[2] or result[1] == result[3]:
        raise GeminiNormalizedTableBoxError(code)
    return result


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _number(value: Any) -> float:
    if not _finite_number(value):
        raise GeminiNormalizedTableBoxError("g5102_raster_transform_invalid")
    return float(value)


def _positive_number(value: Any) -> float:
    result = _number(value)
    if result <= 0:
        raise GeminiNormalizedTableBoxError("g5102_raster_transform_invalid")
    return result


def response_schema_copy() -> dict[str, Any]:
    return copy.deepcopy(GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA)
