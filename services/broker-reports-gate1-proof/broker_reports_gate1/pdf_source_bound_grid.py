from __future__ import annotations

from collections import defaultdict
import statistics
from typing import Any


class PdfSourceBoundGridError(RuntimeError):
    pass


def reconstruct_mcid_grid(
    *,
    chars: list[dict[str, Any]],
    vector_lines: list[dict[str, Any]],
    rects: list[dict[str, Any]],
    region_bbox: list[float],
) -> dict[str, Any]:
    """Reconstruct a tagged PDF grid without interpreting cell text.

    Source horizontal rules own rows.  The first ruled row owns the column
    partition: each of its source MCID groups is one column.  Every tagged
    source character inside the ruled grid must belong to exactly one MCID
    group and that group to exactly one row and column.
    """

    if len(region_bbox) != 4:
        raise PdfSourceBoundGridError("pdf_source_bound_region_invalid")
    left, top, right, bottom = map(float, region_bbox)
    width = right - left
    if width <= 0 or bottom <= top:
        raise PdfSourceBoundGridError("pdf_source_bound_region_invalid")

    horizontal_rules: list[float] = []
    for item in [*vector_lines, *rects]:
        bbox = item.get("bbox") or []
        if len(bbox) != 4:
            continue
        x0, y0, x1, y1 = map(float, bbox)
        if x1 <= left or x0 >= right or y1 < top or y0 > bottom:
            continue
        if min(x1, right) - max(x0, left) < width * 0.7:
            continue
        horizontal_rules.extend((max(top, y0), min(bottom, y1)))
    # PDF generators commonly draw the same rule as a thin filled rectangle
    # plus a centre line.  Treat that stroke as one source boundary.
    y_edges = _dedupe_edges(horizontal_rules, tolerance=2.25)
    if len(y_edges) < 2:
        raise PdfSourceBoundGridError("pdf_source_bound_rows_unproven")

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    covered_ordinals: set[int] = set()
    for char in chars:
        bbox = char.get("bbox") or []
        if len(bbox) != 4 or not _center_inside(bbox, [left, y_edges[0], right, y_edges[-1]]):
            continue
        mcid = char.get("mcid")
        tag = char.get("tag")
        if mcid is None:
            raise PdfSourceBoundGridError("pdf_source_bound_mcid_missing")
        ordinal = int(char["parser_ordinal"])
        if ordinal in covered_ordinals:
            raise PdfSourceBoundGridError("pdf_source_bound_char_partition_ambiguous")
        covered_ordinals.add(ordinal)
        groups[(str(mcid), str(tag or ""))].append(char)
    if not groups:
        raise PdfSourceBoundGridError("pdf_source_bound_mcid_missing")

    group_rows: dict[tuple[str, str], int] = {}
    group_boxes: dict[tuple[str, str], list[float]] = {}
    for key, members in groups.items():
        bbox = _merge([member["bbox"] for member in members])
        member_rows = [
            [
                index
                for index in range(len(y_edges) - 1)
                if _bbox_inside(
                    member["bbox"],
                    [left, y_edges[index], right, y_edges[index + 1]],
                )
                and _center_inside(
                    member["bbox"],
                    [left, y_edges[index], right, y_edges[index + 1]],
                )
            ]
            for member in members
        ]
        if any(len(memberships) != 1 for memberships in member_rows):
            raise PdfSourceBoundGridError("pdf_source_bound_row_partition_ambiguous")
        owned_rows = {memberships[0] for memberships in member_rows}
        if len(owned_rows) != 1:
            raise PdfSourceBoundGridError("pdf_source_bound_row_partition_ambiguous")
        group_rows[key] = next(iter(owned_rows)) + 1
        group_boxes[key] = bbox
        if _has_disconnected_x_members(members):
            raise PdfSourceBoundGridError("pdf_source_bound_column_partition_ambiguous")

    first_row = min(group_rows.values())
    headers = sorted(
        (key for key, row in group_rows.items() if row == first_row),
        key=lambda key: (group_boxes[key][0], group_boxes[key][2], key),
    )
    if len(headers) < 2:
        raise PdfSourceBoundGridError("pdf_source_bound_columns_unproven")
    for previous, current in zip(headers, headers[1:]):
        if group_boxes[previous][2] > group_boxes[current][0] + 0.75:
            raise PdfSourceBoundGridError("pdf_source_bound_header_partition_ambiguous")
    inferred_x_edges = [left]
    for previous, current in zip(headers, headers[1:]):
        inferred_x_edges.append((group_boxes[previous][2] + group_boxes[current][0]) / 2.0)
    inferred_x_edges.append(right)
    x_edges = inferred_x_edges

    group_columns: dict[tuple[str, str], int] = {}
    for key, bbox in group_boxes.items():
        memberships = [index for index in range(len(x_edges) - 1) if _center_inside(bbox, [x_edges[index], y_edges[0], x_edges[index + 1], y_edges[-1]])]
        if len(memberships) != 1:
            raise PdfSourceBoundGridError("pdf_source_bound_column_partition_ambiguous")
        group_columns[key] = memberships[0] + 1

    refined_x_edges = [left]
    for column_index in range(1, len(x_edges) - 1):
        left_boxes = [
            group_boxes[key]
            for key, column in group_columns.items()
            if column == column_index
        ]
        right_boxes = [
            group_boxes[key]
            for key, column in group_columns.items()
            if column == column_index + 1
        ]
        if not left_boxes or not right_boxes:
            raise PdfSourceBoundGridError("pdf_source_bound_column_partition_ambiguous")
        left_extent = max(box[2] for box in left_boxes)
        right_extent = min(box[0] for box in right_boxes)
        if left_extent > right_extent:
            raise PdfSourceBoundGridError("pdf_source_bound_column_partition_ambiguous")
        refined_x_edges.append((left_extent + right_extent) / 2.0)
    refined_x_edges.append(right)
    x_edges = refined_x_edges
    for key, members in groups.items():
        row = group_rows[key] - 1
        column = group_columns[key] - 1
        for member in members:
            bbox_memberships = [
                index
                for index in range(len(x_edges) - 1)
                if _bbox_inside(
                    member["bbox"],
                    [x_edges[index], y_edges[row], x_edges[index + 1], y_edges[row + 1]],
                )
            ]
            center_memberships = [
                index
                for index in range(len(x_edges) - 1)
                if _center_inside(
                    member["bbox"],
                    [x_edges[index], y_edges[row], x_edges[index + 1], y_edges[row + 1]],
                )
            ]
            if bbox_memberships != [column] or center_memberships != [column]:
                raise PdfSourceBoundGridError("pdf_source_bound_char_partition_ambiguous")

    cells = []
    char_partition: list[int] = []
    cell_ordinal = 0
    for row_index in range(len(y_edges) - 1):
        for column_index in range(len(x_edges) - 1):
            cell_ordinal += 1
            keys = sorted(
                (
                    key
                    for key in groups
                    if group_rows[key] == row_index + 1
                    and group_columns[key] == column_index + 1
                ),
                key=lambda key: min(int(item["parser_ordinal"]) for item in groups[key]),
            )
            if len(keys) > 1:
                raise PdfSourceBoundGridError(
                    "pdf_source_bound_cell_group_partition_ambiguous"
                )
            ordinals = [
                int(item["parser_ordinal"])
                for key in keys
                for item in groups[key]
            ]
            char_partition.extend(ordinals)
            cells.append(
                {
                    "cell_ordinal": cell_ordinal,
                    "row_ordinal": row_index + 1,
                    "column_ordinal": column_index + 1,
                    "row_span": 1,
                    "column_span": 1,
                    "bbox": [x_edges[column_index], y_edges[row_index], x_edges[column_index + 1], y_edges[row_index + 1]],
                    "word_parser_ordinals": [],
                    "char_parser_ordinals": ordinals,
                    "mcid_refs": [key[0] for key in keys],
                }
            )
    if sorted(char_partition) != sorted(covered_ordinals) or len(char_partition) != len(set(char_partition)):
        raise PdfSourceBoundGridError("pdf_source_bound_char_coverage_invalid")
    return {
        "table_strategy_ref": "source_mcid_horizontal_rules_v1",
        "table_reconstruction_status": "candidate",
        "geometry_confidence": 1.0,
        "bbox": [left, y_edges[0], right, y_edges[-1]],
        "rows_total": len(y_edges) - 1,
        "columns_total": len(x_edges) - 1,
        "cells_total": len(cells),
        "cell_inventory": cells,
        "contributing_word_parser_ordinals": [],
        "contributing_char_parser_ordinals": sorted(covered_ordinals),
        "ruling_evidence_total": len(y_edges),
        "column_edges_pdf_points": x_edges,
        "reconstruction_reason_codes": [
            "source_tagged_char_partition_exact",
            "source_horizontal_row_boundaries",
            "source_mcid_header_column_partition",
            "empty_grid_slots_preserved",
        ],
    }


def _dedupe_edges(values: list[float], *, tolerance: float) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
        else:
            result[-1] = (result[-1] + value) / 2.0
    return result


def _center_inside(bbox: list[float], container: list[float]) -> bool:
    if len(bbox) != 4 or len(container) != 4:
        return False
    x = (float(bbox[0]) + float(bbox[2])) / 2.0
    y = (float(bbox[1]) + float(bbox[3])) / 2.0
    return container[0] <= x <= container[2] and container[1] <= y <= container[3]


def _bbox_inside(bbox: list[float], container: list[float]) -> bool:
    return (
        len(bbox) == 4
        and len(container) == 4
        and float(container[0]) <= float(bbox[0])
        and float(bbox[2]) <= float(container[2])
        and float(container[1]) <= float(bbox[1])
        and float(bbox[3]) <= float(container[3])
    )


def _merge(boxes: list[list[float]]) -> list[float]:
    return [
        min(float(box[0]) for box in boxes),
        min(float(box[1]) for box in boxes),
        max(float(box[2]) for box in boxes),
        max(float(box[3]) for box in boxes),
    ]


def _has_disconnected_x_members(members: list[dict[str, Any]]) -> bool:
    intervals = sorted(
        (float(item["bbox"][0]), float(item["bbox"][2])) for item in members
    )
    widths = [max(0.0, end - start) for start, end in intervals]
    allowed_gap = max(3.0, (statistics.median(widths) if widths else 1.0) * 1.5)
    covered_end = intervals[0][1]
    for start, end in intervals[1:]:
        if start - covered_end > allowed_gap:
            return True
        covered_end = max(covered_end, end)
    return False
