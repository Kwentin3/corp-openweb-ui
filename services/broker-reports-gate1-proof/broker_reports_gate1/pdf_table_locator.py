from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

from .contracts import (
    PDF_TABLE_LOCATOR_PAGE_SCHEMA as PDF_TABLE_LOCATOR_PAGE_SCHEMA,
    PDF_TABLE_LOCATOR_RESPONSE_SCHEMA as PDF_TABLE_LOCATOR_RESPONSE_SCHEMA,
    stable_digest,
)


PDF_TABLE_LOCATOR_PROJECTION_SCHEMA = "broker_reports_pdf_table_locator_projection_v3"
PDF_TABLE_LOCATOR_POLICY_VERSION = "pdf_table_locator_policy_v3"
PDF_TABLE_LOCATOR_COORDINATE_CONTRACT = (
    "gemini_box_2d_ymin_xmin_ymax_xmax_normalized_0_1000"
)
FACTORY_REQUIRED = (
    "PdfTableLocatorProjectionFactory.create is the only product box_2d to "
    "PDF-point projection entrypoint"
)
FORBIDDEN = (
    "The locator must not inspect source text, extract values, infer rows or "
    "columns, choose pdfplumber settings, or publish canonical tables"
)


PDF_TABLE_LOCATOR_PROMPT = """Detect every visible physical table in the CURRENT full-page PDF
image. Return current-page bounding boxes in top-to-bottom order. On page 1 you
receive only CURRENT. On later pages you receive PREVIOUS first and CURRENT
second. Both are unmodified full-page images.

Use Gemini's standard object-detection coordinate convention exactly:
- box_2d is [ymin, xmin, ymax, xmax];
- every coordinate is an integer from 0 to 1000;
- coordinates are normalized relative to the entire input image;
- do not return image pixels or PDF points;
- do not use a different axis order.

Treat each visually independent grid or ruled table section as a separate table
instance. Include every physical table, including header-only tables, tables
with explicit empty rows, and explanatory tables. Never use one table_box_2d
that encloses two distinct grids or titled table sections. Do not split one
continuous grid merely because it contains internal section rows or repeated
headers.

For every CURRENT-page table return exactly these three fields:
- table_box_2d: the tight box around the physical grid;
- title_box_2d: the tight box around its visible title, or null;
- header_box_2d: the tight box around its visible column header, or null.

Do not treat prose, lists, page furniture, illustrative screenshots without a
data grid, or decorative lines as tables. Do not transcribe text, labels,
dates, amounts, rows, columns, or cell values.

Also return exactly one boundary_from_previous object:
- decision is CONTINUATION when the last table on PREVIOUS and first table on
  CURRENT are visibly the same whole table;
- decision is INDEPENDENT when they are visibly different tables;
- decision is AMBIGUOUS when the original pages do not prove either answer;
- decision is NOT_APPLICABLE on page 1 or when either page has no table.
- evidence is FIRST_PAGE, NO_TABLE_PAIR, EXPLICIT_CONTINUATION, VISUAL_FLOW,
  NEW_TABLE, or INSUFFICIENT_EVIDENCE.

Do not use table text as a transcription output. Return no other fields.
"""


PDF_TABLE_LOCATOR_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tables", "boundary_from_previous"],
    "properties": {
        "boundary_from_previous": {
            "type": "object",
            "additionalProperties": False,
            "required": ["decision", "evidence"],
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": [
                        "CONTINUATION",
                        "INDEPENDENT",
                        "AMBIGUOUS",
                        "NOT_APPLICABLE",
                    ],
                },
                "evidence": {
                    "type": "string",
                    "enum": [
                        "FIRST_PAGE",
                        "NO_TABLE_PAIR",
                        "EXPLICIT_CONTINUATION",
                        "VISUAL_FLOW",
                        "NEW_TABLE",
                        "INSUFFICIENT_EVIDENCE",
                    ],
                },
            },
        },
        "tables": {
            "type": "array",
            "maxItems": 32,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["table_box_2d", "title_box_2d", "header_box_2d"],
                "properties": {
                    "table_box_2d": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 1000,
                        },
                    },
                    "title_box_2d": {
                        "anyOf": [
                            {
                                "type": "array",
                                "minItems": 4,
                                "maxItems": 4,
                                "items": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "maximum": 1000,
                                },
                            },
                            {"type": "null"},
                        ]
                    },
                    "header_box_2d": {
                        "anyOf": [
                            {
                                "type": "array",
                                "minItems": 4,
                                "maxItems": 4,
                                "items": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "maximum": 1000,
                                },
                            },
                            {"type": "null"},
                        ]
                    },
                },
            },
        }
    },
}


class PdfTableLocatorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfTableLocatorProjectionConfig:
    coordinate_normalizer: int = 1000
    maximum_tables: int = 32


class PdfTableLocatorProjectionFactory:
    def __init__(
        self, config: PdfTableLocatorProjectionConfig | None = None
    ) -> None:
        self.config = config or PdfTableLocatorProjectionConfig()

    def create(self) -> "PdfTableLocatorProjection":
        if self.config.coordinate_normalizer != 1000:
            raise PdfTableLocatorError("pdf_table_locator_normalizer_invalid")
        if not 1 <= self.config.maximum_tables <= 64:
            raise PdfTableLocatorError("pdf_table_locator_table_budget_invalid")
        return PdfTableLocatorProjection(self.config)


class PdfTableLocatorProjection:
    def __init__(self, config: PdfTableLocatorProjectionConfig) -> None:
        self.config = config

    def project(
        self,
        *,
        provider_value: Any,
        raster_manifest: dict[str, Any],
        expected_page_bbox: list[float],
        has_previous_page: bool,
        previous_page_has_tables: bool,
    ) -> dict[str, Any]:
        page_bbox = _bbox(expected_page_bbox, "pdf_table_locator_page_bbox_invalid")
        transform = self._validated_transform(raster_manifest, page_bbox)
        normalized_tables, boundary = self._validated_provider_value(provider_value)
        self._validate_boundary(
            boundary,
            has_previous_page=has_previous_page,
            previous_page_has_tables=previous_page_has_tables,
            current_page_has_tables=bool(normalized_tables),
        )
        tables = []
        accepted_table_bboxes: list[list[float]] = []
        accepted_title_bboxes: list[list[float]] = []
        for ordinal, table in enumerate(normalized_tables, 1):
            table_box = table["table_box_2d"]
            title_box = table["title_box_2d"]
            header_box = table["header_box_2d"]
            pdf_bbox = self._project_box(table_box, transform)
            title_pdf_bbox = self._project_box(title_box, transform) if title_box else None
            header_pdf_bbox = self._project_box(header_box, transform) if header_box else None
            _inside(pdf_bbox, page_bbox)
            if title_pdf_bbox is not None:
                _inside(title_pdf_bbox, page_bbox)
                title_center_x = (title_pdf_bbox[0] + title_pdf_bbox[2]) / 2.0
                if (
                    _overlap(title_pdf_bbox, pdf_bbox)
                    or title_pdf_bbox[3] > pdf_bbox[1]
                    or not pdf_bbox[0] <= title_center_x <= pdf_bbox[2]
                    or any(
                        _overlap(title_pdf_bbox, other)
                        for other in accepted_table_bboxes
                    )
                    or any(
                        _overlap(title_pdf_bbox, other)
                        for other in accepted_title_bboxes
                    )
                ):
                    raise PdfTableLocatorError("pdf_table_locator_title_overlap_invalid")
            if header_pdf_bbox is not None:
                _inside(header_pdf_bbox, page_bbox)
                if not _contains(pdf_bbox, header_pdf_bbox):
                    raise PdfTableLocatorError("pdf_table_locator_header_outside_table")
            if any(_overlap(pdf_bbox, other) for other in accepted_table_bboxes):
                raise PdfTableLocatorError("pdf_table_locator_table_overlap_invalid")
            if any(_overlap(pdf_bbox, other) for other in accepted_title_bboxes):
                raise PdfTableLocatorError("pdf_table_locator_title_overlap_invalid")
            accepted_table_bboxes.append(pdf_bbox)
            if title_pdf_bbox is not None:
                accepted_title_bboxes.append(title_pdf_bbox)
            tables.append(
                {
                    "region_ref": "pdftableregion_"
                    + stable_digest(
                        [
                            PDF_TABLE_LOCATOR_PROJECTION_SCHEMA,
                            raster_manifest.get("manifest_hash"),
                            ordinal,
                            table_box,
                            title_box,
                            header_box,
                            pdf_bbox,
                        ],
                        length=24,
                    ),
                    "ordinal": ordinal,
                    "box_2d_normalized": list(table_box),
                    "table_box_2d_normalized": list(table_box),
                    "title_box_2d_normalized": list(title_box) if title_box else None,
                    "header_box_2d_normalized": list(header_box) if header_box else None,
                    "bbox_pdf_points": pdf_bbox,
                    "title_bbox_pdf_points": title_pdf_bbox,
                    "header_bbox_pdf_points": header_pdf_bbox,
                }
            )
        return {
            "schema_version": PDF_TABLE_LOCATOR_PROJECTION_SCHEMA,
            "policy_version": PDF_TABLE_LOCATOR_POLICY_VERSION,
            "coordinate_contract": PDF_TABLE_LOCATOR_COORDINATE_CONTRACT,
            "coordinate_normalizer": self.config.coordinate_normalizer,
            "input_raster_manifest_hash": raster_manifest.get("manifest_hash"),
            "page_bbox_pdf_points": page_bbox,
            "tables": tables,
            "boundary_from_previous": copy.deepcopy(boundary),
            "model_values_used_as_source_literals": False,
            "table_structure_inferred": False,
        }

    def _validated_provider_value(
        self, value: Any
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        if not isinstance(value, dict) or set(value) != {
            "tables",
            "boundary_from_previous",
        }:
            raise PdfTableLocatorError("pdf_table_locator_response_shape_invalid")
        tables = value.get("tables")
        if not isinstance(tables, list) or len(tables) > self.config.maximum_tables:
            raise PdfTableLocatorError("pdf_table_locator_tables_invalid")
        normalized: list[dict[str, Any]] = []
        for table in tables:
            if not isinstance(table, dict) or set(table) != {
                "table_box_2d",
                "title_box_2d",
                "header_box_2d",
            }:
                raise PdfTableLocatorError("pdf_table_locator_table_shape_invalid")
            box = self._validated_box(table.get("table_box_2d"), nullable=False)
            title_box = self._validated_box(table.get("title_box_2d"), nullable=True)
            header_box = self._validated_box(table.get("header_box_2d"), nullable=True)
            normalized.append(
                {
                    "table_box_2d": box,
                    "title_box_2d": title_box,
                    "header_box_2d": header_box,
                }
            )
        normalized.sort(key=lambda item: (item["table_box_2d"][0], item["table_box_2d"][1]))
        boundary = value.get("boundary_from_previous")
        if not isinstance(boundary, dict) or set(boundary) != {"decision", "evidence"}:
            raise PdfTableLocatorError("pdf_table_locator_boundary_shape_invalid")
        decision = boundary.get("decision")
        evidence = boundary.get("evidence")
        if decision not in {
            "CONTINUATION", "INDEPENDENT", "AMBIGUOUS", "NOT_APPLICABLE"
        } or evidence not in {
            "FIRST_PAGE", "NO_TABLE_PAIR", "EXPLICIT_CONTINUATION", "VISUAL_FLOW",
            "NEW_TABLE", "INSUFFICIENT_EVIDENCE",
        }:
            raise PdfTableLocatorError("pdf_table_locator_boundary_value_invalid")
        return normalized, {"decision": decision, "evidence": evidence}

    @staticmethod
    def _validate_boundary(
        boundary: dict[str, str],
        *,
        has_previous_page: bool,
        previous_page_has_tables: bool,
        current_page_has_tables: bool,
    ) -> None:
        decision = boundary["decision"]
        evidence = boundary["evidence"]
        if not has_previous_page:
            if (decision, evidence) != ("NOT_APPLICABLE", "FIRST_PAGE"):
                raise PdfTableLocatorError("pdf_table_locator_first_page_boundary_invalid")
            return
        if not previous_page_has_tables or not current_page_has_tables:
            if (decision, evidence) != ("NOT_APPLICABLE", "NO_TABLE_PAIR"):
                raise PdfTableLocatorError("pdf_table_locator_no_pair_boundary_invalid")
            return
        allowed = {
            "CONTINUATION": {"EXPLICIT_CONTINUATION", "VISUAL_FLOW"},
            "INDEPENDENT": {"NEW_TABLE"},
            "AMBIGUOUS": {"INSUFFICIENT_EVIDENCE"},
        }
        if decision not in allowed or evidence not in allowed[decision]:
            raise PdfTableLocatorError("pdf_table_locator_table_pair_boundary_invalid")

    def _validated_box(self, value: Any, *, nullable: bool) -> list[int] | None:
        if value is None and nullable:
            return None
        if (
            not isinstance(value, list)
            or len(value) != 4
            or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
        ):
            raise PdfTableLocatorError("pdf_table_locator_box_invalid")
        ymin, xmin, ymax, xmax = value
        if any(item < 0 or item > self.config.coordinate_normalizer for item in value):
            raise PdfTableLocatorError("pdf_table_locator_box_out_of_range")
        if ymin >= ymax or xmin >= xmax:
            raise PdfTableLocatorError("pdf_table_locator_box_order_invalid")
        return list(value)

    def _project_box(
        self, box: list[int], transform: dict[str, float]
    ) -> list[float]:
        ymin, xmin, ymax, xmax = box
        return [
            round(
                self._source_coordinate(
                    value, pixels, scale, translate
                ),
                6,
            )
            for value, pixels, scale, translate in (
                (xmin, transform["width"], transform["scale_x"], transform["translate_x"]),
                (ymin, transform["height"], transform["scale_y"], transform["translate_y"]),
                (xmax, transform["width"], transform["scale_x"], transform["translate_x"]),
                (ymax, transform["height"], transform["scale_y"], transform["translate_y"]),
            )
        ]

    @staticmethod
    def _validated_transform(
        raster_manifest: dict[str, Any], page_bbox: list[float]
    ) -> dict[str, float]:
        if (
            not isinstance(raster_manifest, dict)
            or raster_manifest.get("render_scope") != "full_page"
            or raster_manifest.get("full_page_identity_verified") is not True
            or raster_manifest.get("source_coordinate_space") != "pdf_top_left_points"
            or raster_manifest.get("pixel_coordinate_space") != "crop_top_left_pixels"
            or raster_manifest.get("lossless") is not True
            or raster_manifest.get("silent_resize_performed") is not False
            or raster_manifest.get("page_rotation") != 0
            or raster_manifest.get("applied_rotation") != 0
        ):
            raise PdfTableLocatorError("pdf_table_locator_raster_manifest_invalid")
        if _bbox(
            raster_manifest.get("actual_page_bbox"),
            "pdf_table_locator_raster_bbox_invalid",
        ) != page_bbox or _bbox(
            raster_manifest.get("rendered_bbox"),
            "pdf_table_locator_rendered_bbox_invalid",
        ) != page_bbox:
            raise PdfTableLocatorError("pdf_table_locator_raster_bbox_mismatch")
        width = _positive(raster_manifest.get("width"))
        height = _positive(raster_manifest.get("height"))
        source_transform = raster_manifest.get("source_to_pixel_transform")
        if not isinstance(source_transform, dict):
            raise PdfTableLocatorError("pdf_table_locator_transform_invalid")
        scale_x = _positive(source_transform.get("scale_x"))
        scale_y = _positive(source_transform.get("scale_y"))
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
            raise PdfTableLocatorError("pdf_table_locator_transform_mismatch")
        return {
            "width": width,
            "height": height,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "translate_x": translate_x,
            "translate_y": translate_y,
        }

    def _source_coordinate(
        self, normalized: int, pixels: float, scale: float, translate: float
    ) -> float:
        return normalized / self.config.coordinate_normalizer * pixels / scale - translate


def output_schema_copy() -> dict[str, Any]:
    return copy.deepcopy(PDF_TABLE_LOCATOR_OUTPUT_SCHEMA)


def _bbox(value: Any, code: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 4:
        raise PdfTableLocatorError(code)
    result = [_number(item) for item in value]
    if result[0] >= result[2] or result[1] >= result[3]:
        raise PdfTableLocatorError(code)
    return [round(item, 6) for item in result]


def _inside(value: list[float], outer: list[float]) -> None:
    epsilon = 1e-6
    if (
        value[0] < outer[0] - epsilon
        or value[1] < outer[1] - epsilon
        or value[2] > outer[2] + epsilon
        or value[3] > outer[3] + epsilon
    ):
        raise PdfTableLocatorError("pdf_table_locator_bbox_outside_page")


def _contains(outer: list[float], inner: list[float]) -> bool:
    return (
        outer[0] <= inner[0] < inner[2] <= outer[2]
        and outer[1] <= inner[1] < inner[3] <= outer[3]
    )


def _overlap(left: list[float], right: list[float]) -> bool:
    return not (
        left[2] <= right[0]
        or right[2] <= left[0]
        or left[3] <= right[1]
        or right[3] <= left[1]
    )


def _number(value: Any) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise PdfTableLocatorError("pdf_table_locator_number_invalid")
    return float(value)


def _positive(value: Any) -> float:
    result = _number(value)
    if result <= 0:
        raise PdfTableLocatorError("pdf_table_locator_number_invalid")
    return result
