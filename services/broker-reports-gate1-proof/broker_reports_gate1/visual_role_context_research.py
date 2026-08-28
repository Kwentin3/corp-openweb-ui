from __future__ import annotations

import copy
import json
import math
import statistics
from typing import Any, Mapping

from .visual_table_structure_research import (
    VisualTableStructureError,
    VisualTableStructureProjection,
    VisualTableStructureProjectionFactory,
)


VISUAL_ROLE_CONTEXT_SCHEMA = "broker_reports_visual_role_context_rd_v1"

FACTORY_REQUIRED = (
    "VisualRoleContextResearchFactory.create is the only research adapter from "
    "source-bound visual header geometry to Canonical column refs"
)
FORBIDDEN = (
    "research-only: no Canonical mutation, model-authored literal, financial "
    "role, source value, fact, continuation inference or product activation"
)


class VisualRoleContextError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class VisualRoleContextResearchFactory:
    def create(self) -> "VisualRoleContextResearch":
        return VisualRoleContextResearch(
            word_projector=VisualTableStructureProjectionFactory().create()
        )


class VisualRoleContextResearch:
    """Representation-only adapter; financial meaning stays in the role mapper."""

    def __init__(self, *, word_projector: VisualTableStructureProjection) -> None:
        self.word_projector = word_projector

    def select_structure(
        self,
        *,
        bound_structures: Mapping[str, Any],
        table_box_2d: list[int],
    ) -> dict[str, Any]:
        table_box = _box(table_box_2d)
        tables = bound_structures.get("tables")
        if not isinstance(tables, list) or not tables:
            raise VisualRoleContextError("visual_role_context_structures_invalid")
        scored: list[tuple[float, int, dict[str, Any]]] = []
        for ordinal, raw in enumerate(tables, 1):
            if not isinstance(raw, dict):
                raise VisualRoleContextError("visual_role_context_structures_invalid")
            header_boxes = [_box(item) for item in raw.get("header_boxes_2d") or []]
            score = sum(_fraction_inside(item, table_box) for item in header_boxes)
            if score > 0:
                scored.append((score, ordinal, raw))
        if not scored:
            raise VisualRoleContextError("visual_role_context_header_not_bound")
        scored.sort(key=lambda item: (-item[0], item[1]))
        if len(scored) > 1 and math.isclose(
            scored[0][0], scored[1][0], rel_tol=0.0, abs_tol=1e-9
        ):
            raise VisualRoleContextError("visual_role_context_header_ambiguous")
        return copy.deepcopy(scored[0][2])

    def build(
        self,
        *,
        parser_page: dict[str, Any],
        table_candidate: Mapping[str, Any],
        bound_structure: Mapping[str, Any],
        expected_column_refs: list[str],
    ) -> dict[str, Any]:
        columns_total = table_candidate.get("columns_total")
        if (
            not isinstance(columns_total, int)
            or columns_total < 1
            or expected_column_refs
            != [f"c{ordinal}" for ordinal in range(1, columns_total + 1)]
        ):
            raise VisualRoleContextError("visual_role_context_column_scope_mismatch")
        header_boxes = bound_structure.get("header_boxes_2d")
        title_boxes = bound_structure.get("title_boxes_2d")
        if (
            bound_structure.get("header_status") != "PRESENT"
            or not isinstance(header_boxes, list)
            or not header_boxes
            or not isinstance(title_boxes, list)
        ):
            raise VisualRoleContextError("visual_role_context_header_unavailable")
        try:
            header_words = self.word_projector.bind_word_inventory(
                parser_page=parser_page,
                boxes_2d=header_boxes,
            )
            title_words = self.word_projector.bind_word_inventory(
                parser_page=parser_page,
                boxes_2d=title_boxes,
            )
        except VisualTableStructureError as exc:
            raise VisualRoleContextError(exc.code) from exc
        if not header_words:
            raise VisualRoleContextError("visual_role_context_header_words_empty")
        source_bounds = _source_column_bounds(table_candidate=table_candidate)
        page_width = _positive_number(parser_page.get("width"))
        bounds = {
            ordinal: (left * 1000.0 / page_width, right * 1000.0 / page_width)
            for ordinal, (left, right) in source_bounds.items()
        }
        words_by_column: dict[int, list[dict[str, Any]]] = {
            ordinal: [] for ordinal in range(1, columns_total + 1)
        }
        unassigned: list[str] = []
        for word in header_words:
            center_x = (word["bbox_2d"][1] + word["bbox_2d"][3]) / 2.0
            owners = [
                ordinal
                for ordinal, (left, right) in bounds.items()
                if left <= center_x <= right
            ]
            if len(owners) != 1:
                unassigned.append(word["word_ref"])
                continue
            words_by_column[owners[0]].append(word)
        labels = []
        for ordinal in range(1, columns_total + 1):
            words = sorted(
                words_by_column[ordinal],
                key=lambda item: (
                    item["bbox_2d"][0],
                    item["bbox_2d"][1],
                    item["parser_ordinal"],
                ),
            )
            labels.append(
                {
                    "column_ref": f"c{ordinal}",
                    "literal": " ".join(item["text"] for item in words).strip(),
                    "word_refs": [item["word_ref"] for item in words],
                }
            )
        return {
            "schema_version": VISUAL_ROLE_CONTEXT_SCHEMA,
            "page_number": parser_page.get("page_number"),
            "title_literal": " ".join(
                item["text"]
                for item in sorted(
                    title_words,
                    key=lambda item: (
                        item["bbox_2d"][0],
                        item["bbox_2d"][1],
                        item["parser_ordinal"],
                    ),
                )
            ).strip(),
            "title_word_refs": [item["word_ref"] for item in title_words],
            "header_boxes_2d": copy.deepcopy(header_boxes),
            "header_labels": labels,
            "unassigned_header_word_refs": sorted(unassigned),
            "source_words_owner": "pdfplumber_word_inventory",
            "table_geometry_owner": "existing_pdf_layout_table_candidate",
            "model_literals_used_as_source_values": False,
            "financial_roles_assigned": False,
            "canonical_mutated": False,
        }

    def build_column_geometry(
        self,
        *,
        table_candidate: Mapping[str, Any],
        expected_column_refs: list[str],
    ) -> dict[str, Any]:
        """Bind existing column refs to source-image horizontal strips."""

        columns_total = table_candidate.get("columns_total")
        if (
            not isinstance(columns_total, int)
            or columns_total < 1
            or expected_column_refs
            != [f"c{ordinal}" for ordinal in range(1, columns_total + 1)]
        ):
            raise VisualRoleContextError("visual_role_context_column_scope_mismatch")
        table_bbox = _source_box_value(table_candidate.get("bbox"))
        bounds = _source_column_bounds(table_candidate=table_candidate)
        table_width = table_bbox[2] - table_bbox[0]
        strips = []
        for ordinal in range(1, columns_total + 1):
            left, right = bounds[ordinal]
            strips.append(
                {
                    "column_ref": f"c{ordinal}",
                    "x_min_1000": round((left - table_bbox[0]) * 1000 / table_width),
                    "x_max_1000": round((right - table_bbox[0]) * 1000 / table_width),
                }
            )
        return {
            "schema_version": "broker_reports_visual_column_geometry_rd_v1",
            "coordinate_contract": "table_crop_x_axis_0_to_1000",
            "columns": strips,
            "table_geometry_owner": "existing_pdf_layout_table_candidate",
            "model_literals_used_as_source_values": False,
            "financial_roles_assigned": False,
            "canonical_mutated": False,
        }


def enrich_role_request(
    *, baseline_request: Mapping[str, Any], visual_context: Mapping[str, Any]
) -> dict[str, Any]:
    """Add representation evidence while retaining the exact response contract."""

    request = copy.deepcopy(dict(baseline_request))
    messages = request.get("messages")
    if (
        not isinstance(messages, list)
        or len(messages) != 2
        or [item.get("role") for item in messages if isinstance(item, dict)]
        != ["system", "user"]
    ):
        raise VisualRoleContextError("visual_role_context_request_invalid")
    try:
        package = json.loads(messages[1]["content"])
        case = package["case"]
    except (KeyError, TypeError, ValueError) as exc:
        raise VisualRoleContextError("visual_role_context_request_invalid") from exc
    if not isinstance(case, dict) or "source_bound_visual_context" in case:
        raise VisualRoleContextError("visual_role_context_request_invalid")
    if visual_context.get("schema_version") != VISUAL_ROLE_CONTEXT_SCHEMA:
        raise VisualRoleContextError("visual_role_context_invalid")
    case["source_bound_visual_context"] = copy.deepcopy(dict(visual_context))
    messages[0]["content"] += (
        " The optional source_bound_visual_context is a representation-only "
        "projection of exact parser words selected by visual header geometry. "
        "Use its column_ref labels and title as source context, but never repair "
        "or replace row literals. If the supplied physical columns still cannot "
        "express one executable mapping, return STRUCTURALLY_INCOMPATIBLE."
    )
    messages[1]["content"] = json.dumps(
        package,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return request


def compose_visual_role_model_view(
    *, baseline_request: Mapping[str, Any], column_geometry: Mapping[str, Any]
) -> dict[str, Any]:
    """Reuse the text mapper contract while adding one source table image."""

    request = copy.deepcopy(dict(baseline_request))
    messages = request.get("messages")
    if (
        not isinstance(messages, list)
        or len(messages) != 2
        or [item.get("role") for item in messages if isinstance(item, dict)]
        != ["system", "user"]
    ):
        raise VisualRoleContextError("visual_role_context_request_invalid")
    try:
        package = json.loads(messages[1]["content"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VisualRoleContextError("visual_role_context_request_invalid") from exc
    if (
        column_geometry.get("schema_version")
        != "broker_reports_visual_column_geometry_rd_v1"
    ):
        raise VisualRoleContextError("visual_role_context_geometry_invalid")
    return {
        "instruction": (
            messages[0]["content"]
            + " The attached image is the exact source table crop. Use it to "
            "understand the visible title and multi-row header. column_geometry "
            "binds each supplied column_ref to a horizontal image strip. The "
            "Canonical table remains the only source of row values: never "
            "transcribe, repair, join or invent a row value from the image. If "
            "the physical Canonical columns cannot preserve a complete logical "
            "value, return STRUCTURALLY_INCOMPATIBLE."
        ),
        "case": package.get("case"),
        "column_geometry": copy.deepcopy(dict(column_geometry)),
    }


def _source_column_bounds(
    *,
    table_candidate: Mapping[str, Any],
) -> dict[int, tuple[float, float]]:
    cells = table_candidate.get("cell_inventory")
    columns_total = int(table_candidate.get("columns_total") or 0)
    if not isinstance(cells, list):
        raise VisualRoleContextError("visual_role_context_table_geometry_invalid")
    result: dict[int, tuple[float, float]] = {}
    for ordinal in range(1, columns_total + 1):
        candidates = [
            item
            for item in cells
            if isinstance(item, dict)
            and item.get("column_ordinal") == ordinal
            and item.get("column_span") == 1
            and _source_box(item.get("bbox"))
        ]
        if not candidates:
            raise VisualRoleContextError(
                "visual_role_context_column_geometry_unavailable"
            )
        left = statistics.median(float(item["bbox"][0]) for item in candidates)
        right = statistics.median(float(item["bbox"][2]) for item in candidates)
        result[ordinal] = (left, right)
    ordered = [result[item] for item in range(1, columns_total + 1)]
    if any(right <= left for left, right in ordered) or any(
        ordered[index][1] > ordered[index + 1][0] + 0.5
        for index in range(len(ordered) - 1)
    ):
        raise VisualRoleContextError("visual_role_context_column_geometry_ambiguous")
    return result


def _source_box_value(value: Any) -> list[float]:
    if not _source_box(value):
        raise VisualRoleContextError("visual_role_context_table_geometry_invalid")
    return [float(item) for item in value]


def _box(value: Any) -> list[int]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
    ):
        raise VisualRoleContextError("visual_role_context_box_invalid")
    ymin, xmin, ymax, xmax = value
    if (
        ymin < 0
        or xmin < 0
        or ymax > 1000
        or xmax > 1000
        or ymax <= ymin
        or xmax <= xmin
    ):
        raise VisualRoleContextError("visual_role_context_box_invalid")
    return list(value)


def _fraction_inside(inner: list[int], outer: list[int]) -> float:
    height = max(0, min(inner[2], outer[2]) - max(inner[0], outer[0]))
    width = max(0, min(inner[3], outer[3]) - max(inner[1], outer[1]))
    area = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return (height * width) / float(area) if area else 0.0


def _positive_number(value: Any) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise VisualRoleContextError("visual_role_context_page_geometry_invalid")
    return float(value)


def _source_box(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in value
        )
        and float(value[2]) > float(value[0])
        and float(value[3]) > float(value[1])
    )


__all__ = [
    "FORBIDDEN",
    "FACTORY_REQUIRED",
    "VISUAL_ROLE_CONTEXT_SCHEMA",
    "VisualRoleContextError",
    "VisualRoleContextResearchFactory",
    "compose_visual_role_model_view",
    "enrich_role_request",
]
