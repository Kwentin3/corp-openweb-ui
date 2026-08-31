from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any


class PdfSourceBoundGridError(RuntimeError):
    pass


PDF_SOURCE_GRID_POLICY_VERSION = "pdf_source_grid_policy_v2"
_EDGE_TOLERANCE = 2.25
_BBOX_SLACK = 0.4


def reconstruct_page_source_grids(
    *,
    chars: list[dict[str, Any]],
    words: list[dict[str, Any]],
    vector_lines: list[dict[str, Any]],
    rects: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    page_bbox: list[float],
) -> list[dict[str, Any]]:
    """Build exact source grids inside locator-owned visual instances.

    The locator owns table identity and title/header association.  This helper
    only refines the physical frame and partitions source PDF objects.  It is
    deliberately not a factory or an alternate runtime entrypoint.
    """

    if len(page_bbox) != 4:
        raise PdfSourceBoundGridError("pdf_source_grid_page_bbox_invalid")
    candidates = [
        _reconstruct_region(
            chars=chars,
            words=words,
            vector_lines=vector_lines,
            rects=rects,
            region=region,
            sibling_regions=regions,
            page_bbox=page_bbox,
        )
        for region in regions
    ]
    claimed_grid_chars: set[int] = set()
    claimed_title_chars: set[int] = set()
    claimed_words: set[int] = set()
    for index, candidate in enumerate(candidates):
        bbox = candidate["bbox"]
        if any(
            _overlap_area(bbox, other["bbox"]) > 0.0 for other in candidates[:index]
        ):
            raise PdfSourceBoundGridError("pdf_source_grid_scope_overlap")
        char_claims = set(candidate["contributing_char_parser_ordinals"])
        title_claims = set(candidate["title_char_parser_ordinals"])
        word_claims = set(candidate["contributing_word_parser_ordinals"])
        if (
            title_claims & (claimed_grid_chars | claimed_title_chars)
            or char_claims & claimed_title_chars
        ):
            raise PdfSourceBoundGridError("pdf_source_grid_title_owner_ambiguous")
        if claimed_grid_chars & char_claims or claimed_words & word_claims:
            raise PdfSourceBoundGridError("pdf_source_grid_page_owner_ambiguous")
        claimed_grid_chars.update(char_claims)
        claimed_title_chars.update(title_claims)
        claimed_words.update(word_claims)
    return candidates


def _reconstruct_region(
    *,
    chars: list[dict[str, Any]],
    words: list[dict[str, Any]],
    vector_lines: list[dict[str, Any]],
    rects: list[dict[str, Any]],
    region: dict[str, Any],
    sibling_regions: list[dict[str, Any]],
    page_bbox: list[float],
) -> dict[str, Any]:
    hint = _valid_bbox(region.get("bbox_pdf_points"))
    header = _valid_bbox(region.get("header_bbox_pdf_points"))
    title = _optional_bbox(region.get("title_bbox_pdf_points"))
    if hint is None:
        raise PdfSourceBoundGridError("pdf_source_grid_instance_hint_invalid")
    if header is None:
        raise PdfSourceBoundGridError("pdf_source_grid_header_scope_unproven")
    if not _inside_page(hint, page_bbox) or not _inside_page(header, page_bbox):
        raise PdfSourceBoundGridError("pdf_source_grid_scope_outside_page")
    if title is not None and not _inside_page(title, page_bbox):
        raise PdfSourceBoundGridError("pdf_source_grid_scope_outside_page")

    frame_left, frame_right = _source_frame_x(
        hint=hint,
        header=header,
        vector_lines=vector_lines,
        rects=rects,
    )
    full_width_rects = [
        item
        for item in rects
        if _matches_frame(item.get("bbox"), frame_left, frame_right)
    ]
    boundary_positions = _horizontal_boundaries(
        frame_left=frame_left,
        frame_right=frame_right,
        vector_lines=vector_lines,
        rects=rects,
    )
    header_chars = [
        char
        for char in chars
        if _center_inside(char.get("bbox"), header)
        and _center_x_inside(char.get("bbox"), frame_left, frame_right)
    ]
    if not header_chars or any(char.get("mcid") is None for char in header_chars):
        raise PdfSourceBoundGridError("pdf_source_grid_header_tags_unproven")
    grid_top = _header_frame_top(
        header=header,
        header_chars=header_chars,
        full_width_rects=full_width_rects,
        boundaries=boundary_positions,
    )
    grid_bottom = _nearest_boundary(float(hint[3]), boundary_positions, tolerance=6.0)
    if grid_bottom is None or grid_bottom <= grid_top:
        raise PdfSourceBoundGridError("pdf_source_grid_bottom_unproven")
    grid_bottom = _extend_adjacent_empty_rows(
        current_bottom=grid_bottom,
        frame_left=frame_left,
        frame_right=frame_right,
        chars=chars,
        full_width_rects=full_width_rects,
        boundaries=boundary_positions,
        region=region,
        sibling_regions=sibling_regions,
    )
    grid_bbox = [frame_left, grid_top, frame_right, grid_bottom]

    if title is not None:
        title_chars = [
            char for char in chars if _center_inside(char.get("bbox"), title)
        ]
        if not title_chars:
            raise PdfSourceBoundGridError("pdf_source_grid_title_binding_unproven")
        if any(
            _center_inside(char.get("bbox"), grid_bbox) for char in title_chars
        ):
            raise PdfSourceBoundGridError("pdf_source_grid_title_owner_ambiguous")
    else:
        title_chars = []

    y_edges = [
        edge
        for edge in _merge_positions([grid_top, grid_bottom, *boundary_positions])
        if grid_top - 0.1 <= edge <= grid_bottom + 0.1
    ]
    if len(y_edges) < 2:
        raise PdfSourceBoundGridError("pdf_source_grid_rows_unproven")

    header_groups = _header_groups(header_chars)
    if len(header_groups) < 2:
        raise PdfSourceBoundGridError("pdf_source_grid_columns_unproven")
    grid_chars = [char for char in chars if _center_inside(char.get("bbox"), grid_bbox)]
    if not grid_chars or any(char.get("mcid") is None for char in grid_chars):
        raise PdfSourceBoundGridError("pdf_source_grid_tagged_source_incomplete")
    x_edges = _whitespace_columns(
        frame_left=frame_left,
        frame_right=frame_right,
        header_groups=header_groups,
        chars=grid_chars,
    )

    cells: list[dict[str, Any]] = []
    owner_by_char: dict[int, int] = {}
    for row_index, (row_top, row_bottom) in enumerate(zip(y_edges, y_edges[1:]), 1):
        for column_index, (column_left, column_right) in enumerate(
            zip(x_edges, x_edges[1:]), 1
        ):
            cell_bbox = [column_left, row_top, column_right, row_bottom]
            ordinals = sorted(
                int(char["parser_ordinal"])
                for char in grid_chars
                if _bbox_inside(char.get("bbox"), cell_bbox, slack=_BBOX_SLACK)
            )
            cell_ordinal = len(cells) + 1
            for ordinal in ordinals:
                if ordinal in owner_by_char:
                    raise PdfSourceBoundGridError(
                        "pdf_source_grid_char_owner_ambiguous"
                    )
                owner_by_char[ordinal] = cell_ordinal
            cells.append(
                {
                    "cell_ordinal": cell_ordinal,
                    "row_ordinal": row_index,
                    "column_ordinal": column_index,
                    "row_span": 1,
                    "column_span": 1,
                    "bbox": cell_bbox,
                    "word_parser_ordinals": [],
                    "char_parser_ordinals": ordinals,
                    "mcid_refs": sorted(
                        {
                            str(char.get("mcid"))
                            for char in grid_chars
                            if int(char["parser_ordinal"]) in set(ordinals)
                        }
                    ),
                }
            )
    expected_chars = {int(char["parser_ordinal"]) for char in grid_chars}
    if set(owner_by_char) != expected_chars:
        raise PdfSourceBoundGridError("pdf_source_grid_char_coverage_invalid")

    word_claims: list[int] = []
    cells_by_ordinal = {int(cell["cell_ordinal"]): cell for cell in cells}
    for word in words:
        word_chars = {int(value) for value in word.get("char_parser_ordinals") or []}
        intersecting = word_chars & expected_chars
        if not intersecting:
            continue
        if intersecting != word_chars:
            raise PdfSourceBoundGridError("pdf_source_grid_word_scope_split")
        owners = {owner_by_char[ordinal] for ordinal in word_chars}
        if len(owners) != 1:
            raise PdfSourceBoundGridError("pdf_source_grid_word_owner_ambiguous")
        word_ordinal = int(word["parser_ordinal"])
        cells_by_ordinal[next(iter(owners))]["word_parser_ordinals"].append(
            word_ordinal
        )
        word_claims.append(word_ordinal)
    nonblank_grid_chars = {
        int(char["parser_ordinal"])
        for char in grid_chars
        if str(char.get("text") or "").strip()
    }
    claimed_word_chars = {
        int(value)
        for word in words
        if int(word.get("parser_ordinal") or 0) in set(word_claims)
        for value in word.get("char_parser_ordinals") or []
    }
    if claimed_word_chars != nonblank_grid_chars:
        raise PdfSourceBoundGridError("pdf_source_grid_word_char_coverage_invalid")

    return {
        "table_strategy_ref": "source_tagged_grid_v1",
        "table_reconstruction_status": "candidate",
        "geometry_confidence": 1.0,
        "bbox": grid_bbox,
        "rows_total": len(y_edges) - 1,
        "columns_total": len(x_edges) - 1,
        "cells_total": len(cells),
        "cell_inventory": cells,
        "contributing_word_parser_ordinals": sorted(word_claims),
        "contributing_char_parser_ordinals": sorted(expected_chars),
        "title_char_parser_ordinals": sorted(
            int(char["parser_ordinal"]) for char in title_chars
        ),
        "ruling_evidence_total": len(y_edges),
        "column_edges_pdf_points": x_edges,
        "source_grid_verified": True,
        "source_grid_policy_version": PDF_SOURCE_GRID_POLICY_VERSION,
        "title_source_binding_verified": title is None or bool(title_chars),
        "header_source_binding_verified": True,
        "reconstruction_reason_codes": [
            "locator_instance_source_frame_refined",
            "source_tagged_char_partition_exact",
            "source_whitespace_column_partition",
            "source_full_width_row_boundaries",
            "source_word_char_conservation_exact",
            "empty_grid_slots_preserved",
        ],
    }


def _source_frame_x(
    *,
    hint: list[float],
    header: list[float],
    vector_lines: list[dict[str, Any]],
    rects: list[dict[str, Any]],
) -> tuple[float, float]:
    hint_width = hint[2] - hint[0]
    candidates: list[tuple[float, float]] = []
    vertical_margin = max(12.0, hint[3] - hint[1])
    envelope = [
        hint[0],
        min(hint[1], header[1]) - 3.0,
        hint[2],
        hint[3] + vertical_margin,
    ]
    for item in [*vector_lines, *rects]:
        bbox = _valid_bbox(item.get("bbox"))
        if bbox is None or not _bbox_overlap(bbox, envelope):
            continue
        overlap_width = max(0.0, min(bbox[2], hint[2]) - max(bbox[0], hint[0]))
        if (
            bbox[2] - bbox[0] < hint_width * 0.8
            or overlap_width < hint_width * 0.8
        ):
            continue
        candidates.append((bbox[0], bbox[2]))
    if len(candidates) < 2:
        raise PdfSourceBoundGridError("pdf_source_grid_frame_unproven")
    clusters: list[list[tuple[float, float]]] = []
    for candidate in sorted(candidates):
        target = next(
            (
                cluster
                for cluster in clusters
                if abs(statistics.median(item[0] for item in cluster) - candidate[0])
                <= _EDGE_TOLERANCE
                and abs(
                    statistics.median(item[1] for item in cluster) - candidate[1]
                )
                <= _EDGE_TOLERANCE
            ),
            None,
        )
        if target is None:
            clusters.append([candidate])
        else:
            target.append(candidate)
    eligible = [cluster for cluster in clusters if len(cluster) >= 2]
    if not eligible:
        raise PdfSourceBoundGridError("pdf_source_grid_frame_unproven")
    ranked = sorted(
        eligible,
        key=lambda cluster: (
            abs(statistics.median(item[0] for item in cluster) - hint[0])
            + abs(statistics.median(item[1] for item in cluster) - hint[2]),
            -len(cluster),
        ),
    )
    best_distance = (
        abs(statistics.median(item[0] for item in ranked[0]) - hint[0])
        + abs(statistics.median(item[1] for item in ranked[0]) - hint[2])
    )
    if best_distance > hint_width * 0.1:
        raise PdfSourceBoundGridError("pdf_source_grid_frame_unproven")
    if len(ranked) > 1:
        second_distance = (
            abs(statistics.median(item[0] for item in ranked[1]) - hint[0])
            + abs(statistics.median(item[1] for item in ranked[1]) - hint[2])
        )
        if abs(second_distance - best_distance) <= _EDGE_TOLERANCE:
            raise PdfSourceBoundGridError("pdf_source_grid_frame_ambiguous")
    left = statistics.median(value[0] for value in ranked[0])
    right = statistics.median(value[1] for value in ranked[0])
    if right <= left:
        raise PdfSourceBoundGridError("pdf_source_grid_frame_unproven")
    return float(left), float(right)


def _horizontal_boundaries(
    *,
    frame_left: float,
    frame_right: float,
    vector_lines: list[dict[str, Any]],
    rects: list[dict[str, Any]],
) -> list[float]:
    required_span = (frame_right - frame_left) * 0.9
    positions: list[float] = []
    for item in vector_lines:
        bbox = _valid_bbox(item.get("bbox"))
        if (
            bbox is None
            or bbox[2] - bbox[0] < required_span
            or not _matches_frame(bbox, frame_left, frame_right)
        ):
            continue
        if bbox[3] - bbox[1] <= 0.5:
            positions.append((bbox[1] + bbox[3]) / 2.0)
    for item in rects:
        bbox = _valid_bbox(item.get("bbox"))
        if (
            bbox is None
            or bbox[2] - bbox[0] < required_span
            or not _matches_frame(bbox, frame_left, frame_right)
        ):
            continue
        positions.extend((bbox[1], bbox[3]))
    return _merge_positions(positions)


def _header_frame_top(
    *,
    header: list[float],
    header_chars: list[dict[str, Any]],
    full_width_rects: list[dict[str, Any]],
    boundaries: list[float],
) -> float:
    char_centers = [
        (float(char["bbox"][1]) + float(char["bbox"][3])) / 2.0 for char in header_chars
    ]
    ranked: list[tuple[int, float, list[float]]] = []
    for item in full_width_rects:
        bbox = _valid_bbox(item.get("bbox"))
        if bbox is None or not _bbox_overlap(bbox, header):
            continue
        coverage = sum(
            bbox[1] - _BBOX_SLACK <= y <= bbox[3] + _BBOX_SLACK for y in char_centers
        )
        ranked.append((coverage, -(bbox[3] - bbox[1]), bbox))
    if ranked:
        best = max(ranked, key=lambda value: (value[0], value[1]))
        if best[0] == len(header_chars):
            return (
                _nearest_boundary(best[2][1], boundaries, tolerance=3.0) or best[2][1]
            )
    edge = _nearest_boundary(header[1], boundaries, tolerance=4.0)
    if edge is None:
        raise PdfSourceBoundGridError("pdf_source_grid_header_frame_unproven")
    if any(y < edge - _BBOX_SLACK for y in char_centers):
        raise PdfSourceBoundGridError("pdf_source_grid_header_frame_unproven")
    return edge


def _extend_adjacent_empty_rows(
    *,
    current_bottom: float,
    frame_left: float,
    frame_right: float,
    chars: list[dict[str, Any]],
    full_width_rects: list[dict[str, Any]],
    boundaries: list[float],
    region: dict[str, Any],
    sibling_regions: list[dict[str, Any]],
) -> float:
    result = current_bottom
    while True:
        choices: list[list[float]] = []
        for item in full_width_rects:
            bbox = _valid_bbox(item.get("bbox"))
            if bbox is None or bbox[3] <= result + _EDGE_TOLERANCE:
                continue
            if abs(bbox[1] - result) > _EDGE_TOLERANCE:
                continue
            if any(
                str(char.get("text") or "").strip()
                and _center_inside(char.get("bbox"), bbox)
                for char in chars
            ):
                continue
            if _intersects_sibling_binding(bbox, region, sibling_regions):
                continue
            choices.append(bbox)
        if not choices:
            return result
        choice = min(choices, key=lambda value: value[3])
        terminal = _nearest_boundary(choice[3], boundaries, tolerance=3.0)
        if terminal is None or terminal <= result:
            return result
        result = terminal


def _intersects_sibling_binding(
    bbox: list[float],
    region: dict[str, Any],
    siblings: list[dict[str, Any]],
) -> bool:
    for sibling in siblings:
        if sibling is region:
            continue
        for field in ("title_bbox_pdf_points", "header_bbox_pdf_points"):
            binding = _optional_bbox(sibling.get(field))
            if binding is not None and _overlap_area(bbox, binding) > 0.0:
                return True
    return False


def _header_groups(chars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for char in chars:
        grouped[(str(char.get("mcid")), str(char.get("tag") or ""))].append(char)
    result = []
    for key, members in grouped.items():
        bbox = _merge_bboxes([member["bbox"] for member in members])
        result.append({"key": key, "bbox": bbox, "center": (bbox[0] + bbox[2]) / 2.0})
    result.sort(key=lambda value: (value["center"], value["bbox"][0], value["key"]))
    if any(
        left["center"] >= right["center"] for left, right in zip(result, result[1:])
    ):
        raise PdfSourceBoundGridError("pdf_source_grid_header_partition_ambiguous")
    return result


def _whitespace_columns(
    *,
    frame_left: float,
    frame_right: float,
    header_groups: list[dict[str, Any]],
    chars: list[dict[str, Any]],
) -> list[float]:
    boundaries = [frame_left]
    for left, right in zip(header_groups, header_groups[1:]):
        low = float(left["center"])
        high = float(right["center"])
        occupied = sorted(
            (max(low, float(char["bbox"][0])), min(high, float(char["bbox"][2])))
            for char in chars
            if float(char["bbox"][2]) > low and float(char["bbox"][0]) < high
        )
        merged: list[list[float]] = []
        for start, end in occupied:
            if end <= start:
                continue
            if not merged or start > merged[-1][1] + 0.01:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        gaps: list[tuple[float, float]] = []
        cursor = low
        for start, end in merged:
            if start > cursor:
                gaps.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < high:
            gaps.append((cursor, high))
        if not gaps:
            raise PdfSourceBoundGridError("pdf_source_grid_column_whitespace_unproven")
        gap = max(gaps, key=lambda value: (value[1] - value[0], -value[0]))
        if gap[1] - gap[0] <= 0.01:
            raise PdfSourceBoundGridError("pdf_source_grid_column_whitespace_unproven")
        boundaries.append((gap[0] + gap[1]) / 2.0)
    boundaries.append(frame_right)
    if any(left >= right for left, right in zip(boundaries, boundaries[1:])):
        raise PdfSourceBoundGridError("pdf_source_grid_column_partition_ambiguous")
    return boundaries


def _matches_frame(value: Any, left: float, right: float) -> bool:
    bbox = _valid_bbox(value)
    return bool(
        bbox is not None
        and abs(bbox[0] - left) <= _EDGE_TOLERANCE
        and abs(bbox[2] - right) <= _EDGE_TOLERANCE
    )


def _merge_positions(values: list[float]) -> list[float]:
    groups: list[list[float]] = []
    for value in sorted(float(item) for item in values):
        if not groups or value - groups[-1][-1] > _EDGE_TOLERANCE:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [sum(group) / len(group) for group in groups]


def _nearest_boundary(
    value: float, boundaries: list[float], *, tolerance: float
) -> float | None:
    if not boundaries:
        return None
    nearest = min(boundaries, key=lambda edge: abs(edge - value))
    return nearest if abs(nearest - value) <= tolerance else None


def _valid_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if any(
        not isinstance(item, (int, float)) or isinstance(item, bool) for item in value
    ):
        return None
    result = [float(item) for item in value]
    return result if result[0] < result[2] and result[1] < result[3] else None


def _optional_bbox(value: Any) -> list[float] | None:
    return None if value is None else _valid_bbox(value)


def _inside_page(value: list[float], page: list[float]) -> bool:
    return (
        page[0] <= value[0] < value[2] <= page[2]
        and page[1] <= value[1] < value[3] <= page[3]
    )


def _center_inside(value: Any, container: list[float]) -> bool:
    bbox = _valid_bbox(value)
    if bbox is None:
        return False
    x = (bbox[0] + bbox[2]) / 2.0
    y = (bbox[1] + bbox[3]) / 2.0
    return container[0] <= x <= container[2] and container[1] <= y <= container[3]


def _center_x_inside(value: Any, left: float, right: float) -> bool:
    bbox = _valid_bbox(value)
    return bbox is not None and left <= (bbox[0] + bbox[2]) / 2.0 <= right


def _bbox_inside(value: Any, container: list[float], *, slack: float) -> bool:
    bbox = _valid_bbox(value)
    return bool(
        bbox is not None
        and container[0] - slack <= bbox[0]
        and bbox[2] <= container[2] + slack
        and container[1] - slack <= bbox[1]
        and bbox[3] <= container[3] + slack
    )


def _bbox_overlap(left: list[float], right: list[float]) -> bool:
    return _overlap_area(left, right) > 0.0


def _overlap_area(left: list[float], right: list[float]) -> float:
    width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    return width * height


def _merge_bboxes(values: list[list[float]]) -> list[float]:
    return [
        min(float(value[0]) for value in values),
        min(float(value[1]) for value in values),
        max(float(value[2]) for value in values),
        max(float(value[3]) for value in values),
    ]
