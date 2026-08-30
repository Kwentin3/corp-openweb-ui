from __future__ import annotations

import copy
import hashlib
import inspect
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from broker_reports_gate1 import logical_row_table_recovery as recovery_module
from broker_reports_gate1.logical_row_table_recovery import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    LogicalRowTableFactory,
    LogicalRowTableRecoveryRuntime,
    logical_table_block_id,
)
from broker_reports_gate1.full_source import FullSourceArtifactFactory
from broker_reports_gate1.pdf_table_raster import PdfTableRasterFactory
from broker_reports_gate1.source_bound_table_scope import (
    SOURCE_BOUND_TABLE_SCOPE_PROPOSAL_SCHEMA,
)
from tests.test_broker_reports_pdf_layout_slice2 import _pdf_bytes


SOURCE_CHECKSUM = "a" * 64
PRIVATE_EVIDENCE_REF = "private://doc6-logical-row-proof"


class ProjectionBuilder:
    def __init__(
        self,
        *,
        page_numbers: tuple[int, ...] = (1,),
        ref_prefix: str = "synthetic",
        width: float = 400.0,
        height: float = 800.0,
    ) -> None:
        self.ref_prefix = ref_prefix
        self.pages = [
            {
                "page_ref": f"{ref_prefix}_page_{page_number}",
                "page_number": page_number,
                "layout_page_width": width,
                "layout_page_height": height,
            }
            for page_number in page_numbers
        ]
        self.bboxes: list[dict[str, Any]] = []
        self.words: list[dict[str, Any]] = []
        self.lines: list[dict[str, Any]] = []
        self.blocks: list[dict[str, Any]] = []
        self.vectors: list[dict[str, Any]] = []
        self.rects: list[dict[str, Any]] = []
        self.candidates: list[dict[str, Any]] = []
        self._word_ordinal = 0
        self._line_ordinal = 0
        self._bbox_ordinal = 0

    def add_row(
        self,
        *,
        page_number: int,
        y: float,
        entries: list[tuple[float, str] | tuple[float, str, float]],
        height: float = 8.0,
    ) -> list[str]:
        page_ref = self._page_ref(page_number)
        word_refs = []
        row_bboxes = []
        for raw_entry in entries:
            x, text = raw_entry[0], raw_entry[1]
            width = (
                float(raw_entry[2])
                if len(raw_entry) == 3
                else max(8.0, len(text) * 4.2)
            )
            bbox = [float(x), y, float(x) + width, y + height]
            bbox_ref = self._add_bbox(page_ref=page_ref, bbox=bbox)
            self._word_ordinal += 1
            word_ref = f"{self.ref_prefix}_word_{self._word_ordinal}"
            self.words.append(
                {
                    "word_ref": word_ref,
                    "page_ref": page_ref,
                    "bbox_ref": bbox_ref,
                    "text": text,
                    "parser_ordinal": self._word_ordinal,
                    "geometry_reading_order": self._word_ordinal,
                }
            )
            word_refs.append(word_ref)
            row_bboxes.append(bbox)
        line_bbox = _merge(row_bboxes)
        line_bbox_ref = self._add_bbox(page_ref=page_ref, bbox=line_bbox)
        self._line_ordinal += 1
        self.lines.append(
            {
                "line_ref": f"{self.ref_prefix}_line_{self._line_ordinal}",
                "page_ref": page_ref,
                "bbox_ref": line_bbox_ref,
                "word_refs": word_refs,
                "text": " ".join(item[1] for item in entries),
                "parser_ordinal": self._line_ordinal,
            }
        )
        return word_refs

    def add_candidate(
        self,
        *,
        page_number: int,
        bbox: list[float],
        word_refs: list[str],
        confidence: float = 0.95,
    ) -> str:
        page_ref = self._page_ref(page_number)
        bbox_ref = self._add_bbox(page_ref=page_ref, bbox=bbox)
        candidate_ref = f"{self.ref_prefix}_candidate_{len(self.candidates) + 1}"
        self.candidates.append(
            {
                "table_candidate_ref": candidate_ref,
                "page_ref": page_ref,
                "bbox_ref": bbox_ref,
                "geometry_confidence": confidence,
                "contributing_word_refs": list(word_refs),
                "table_strategy_ref": "synthetic_geometry_evidence",
                "row_inventory": [],
                "cell_inventory": [],
                "semantic_table_truth_claimed": False,
            }
        )
        self.rects.append(
            {
                "object_ref": f"{self.ref_prefix}_rect_{len(self.rects) + 1}",
                "page_ref": page_ref,
                "bbox_ref": bbox_ref,
            }
        )
        return candidate_ref

    def add_vector_line(
        self,
        *,
        page_number: int,
        bbox: list[float],
    ) -> None:
        page_ref = self._page_ref(page_number)
        self.vectors.append(
            {
                "object_ref": f"{self.ref_prefix}_vector_{len(self.vectors) + 1}",
                "page_ref": page_ref,
                "bbox_ref": self._add_bbox(page_ref=page_ref, bbox=bbox),
            }
        )

    def projection(self) -> dict[str, Any]:
        lines_by_page: dict[str, list[str]] = {}
        for line in self.lines:
            lines_by_page.setdefault(str(line["page_ref"]), []).append(
                str(line["line_ref"])
            )
        for page_ref, line_refs in lines_by_page.items():
            bbox = _merge(
                [
                    self._bbox_value(str(line["bbox_ref"]))
                    for line in self.lines
                    if line["page_ref"] == page_ref
                ]
            )
            self.blocks.append(
                {
                    "block_ref": f"{self.ref_prefix}_block_{len(self.blocks) + 1}",
                    "page_ref": page_ref,
                    "bbox_ref": self._add_bbox(page_ref=page_ref, bbox=bbox),
                    "line_refs": line_refs,
                }
            )
        return {
            "schema_version": "pdf_text_layer_projection_v0",
            "page_inventory": self.pages,
            "bbox_inventory": self.bboxes,
            "word_inventory": self.words,
            "line_inventory": self.lines,
            "block_inventory": self.blocks,
            "vector_line_inventory": self.vectors,
            "rect_inventory": self.rects,
            "table_candidate_inventory": self.candidates,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
        }

    def _page_ref(self, page_number: int) -> str:
        matches = [
            str(page["page_ref"])
            for page in self.pages
            if page["page_number"] == page_number
        ]
        if len(matches) != 1:
            raise AssertionError("synthetic_page_missing")
        return matches[0]

    def _add_bbox(self, *, page_ref: str, bbox: list[float]) -> str:
        self._bbox_ordinal += 1
        bbox_ref = f"{self.ref_prefix}_bbox_{self._bbox_ordinal}"
        self.bboxes.append(
            {
                "bbox_ref": bbox_ref,
                "page_ref": page_ref,
                "coordinate_space": "synthetic_top_origin_points",
                "bbox": bbox,
            }
        )
        return bbox_ref

    def _bbox_value(self, bbox_ref: str) -> list[float]:
        matches = [
            list(item["bbox"])
            for item in self.bboxes
            if item["bbox_ref"] == bbox_ref
        ]
        if len(matches) != 1:
            raise AssertionError("synthetic_bbox_missing")
        return matches[0]


def _recover(builder: ProjectionBuilder):
    return LogicalRowTableFactory().create().recover(
        builder.projection(),
        source_checksum_sha256=SOURCE_CHECKSUM,
        private_evidence_ref=PRIVATE_EVIDENCE_REF,
    )


def _mark_two_column_candidate_as_ruled(
    builder: ProjectionBuilder,
    *,
    candidate_ref: str,
    page_number: int,
    row_refs: list[list[str]],
) -> None:
    candidate = next(
        item
        for item in builder.candidates
        if item["table_candidate_ref"] == candidate_ref
    )
    page_ref = builder._page_ref(page_number)
    table_bbox = builder._bbox_value(str(candidate["bbox_ref"]))
    candidate.update(
        table_strategy_ref="ruled_lines_v0",
        columns_total=2,
        rows_total=len(row_refs),
        row_inventory=[
            {
                "row_ref": f"{candidate_ref}_row_{ordinal}",
                "row_ordinal": ordinal,
                "page_ref": page_ref,
            }
            for ordinal in range(1, len(row_refs) + 1)
        ],
    )
    word_by_ref = {str(item["word_ref"]): item for item in builder.words}
    cells = []
    row_bounds = []
    for row_ordinal, refs in enumerate(row_refs, start=1):
        boxes = [
            builder._bbox_value(str(word_by_ref[ref]["bbox_ref"])) for ref in refs
        ]
        top, bottom = min(box[1] for box in boxes) - 2, max(
            box[3] for box in boxes
        ) + 2
        row_bounds.append((top, bottom))
        for column_ordinal, (left, right, ref) in enumerate(
            (
                (table_bbox[0], 180.0, refs[0]),
                (180.0, table_bbox[2], refs[1]),
            ),
            start=1,
        ):
            cells.append(
                {
                    "cell_ref": f"{candidate_ref}_cell_{row_ordinal}_{column_ordinal}",
                    "row_ref": f"{candidate_ref}_row_{row_ordinal}",
                    "page_ref": page_ref,
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "bbox_ref": builder._add_bbox(
                        page_ref=page_ref,
                        bbox=[left, top, right, bottom],
                    ),
                    "word_refs": [ref],
                }
            )
    candidate["cell_inventory"] = cells
    builder.add_vector_line(
        page_number=page_number,
        bbox=[180.0, table_bbox[1], 180.2, table_bbox[3]],
    )
    for y in [row_bounds[0][0], *[bottom for _, bottom in row_bounds]]:
        builder.add_vector_line(
            page_number=page_number,
            bbox=[table_bbox[0], y, table_bbox[2], y + 0.2],
        )


def _table_text(table: dict[str, Any]) -> list[list[str]]:
    return [
        [str(entry["text"]) for entry in row["entries"]]
        for row in table["ordered_rows"]
    ]


def _validate_v2_component_shapes(result) -> None:
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "stage2"
        / "contracts"
        / "BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def validate(definition: str, payload: dict[str, Any]) -> None:
        Draft202012Validator(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$defs": schema["$defs"],
                "$ref": f"#/$defs/{definition}",
            }
        ).validate(payload)

    for table in result.tables:
        validate("tableContent", table)
    for anchor in result.anchors:
        validate("sourceAnchor", anchor)
    for evidence in result.geometry_evidence:
        validate("geometryEvidence", evidence)
    for ownership in result.source_word_ownership:
        validate("sourceWordOwnership", ownership)
    for issue in result.issues:
        validate("issue", issue)


def _adjacent_mirrored_lane_builder(
    *,
    continuation_gap: float = 3.0,
    continuation_shift: float = 0.0,
    symmetric_tail: bool = False,
    value_like_residual: bool = False,
) -> tuple[ProjectionBuilder, list[str], list[str], list[str]]:
    builder = ProjectionBuilder(ref_prefix="adjacent_mirrored")
    residual_refs = builder.add_row(
        page_number=1,
        y=80,
        entries=(
            [(20, "2025", 45), (68, "2026", 32)]
            if value_like_residual
            else [(20, "Shared", 45), (68, "heading", 32)]
        ),
    )
    seed_refs = builder.add_row(
        page_number=1,
        y=96,
        entries=[
            (20, "Left heading", 45),
            (80, "10", 20),
            (220, "Right heading", 45),
            (280, "20", 20),
        ],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 75, 305, 110],
        word_refs=[*residual_refs, *seed_refs],
    )
    candidate = builder.candidates[-1]
    candidate["table_strategy_ref"] = "ruled_lines_v0"
    candidate["columns_total"] = 4
    page_ref = str(builder.pages[0]["page_ref"])
    candidate["row_inventory"] = [
        {
            "row_ref": f"adjacent_mirrored_seed_row_{ordinal}",
            "row_ordinal": ordinal,
            "page_ref": page_ref,
        }
        for ordinal in (1, 2)
    ]

    def cell(
        row: int,
        column: int,
        bbox: list[float],
        word_refs: list[str],
    ) -> dict[str, Any]:
        return {
            "cell_ref": f"adjacent_mirrored_seed_cell_{row}_{column}",
            "row_ref": f"adjacent_mirrored_seed_row_{row}",
            "page_ref": page_ref,
            "row_ordinal": row,
            "column_ordinal": column,
            "bbox_ref": builder._add_bbox(page_ref=page_ref, bbox=bbox),
            "word_refs": word_refs,
        }

    candidate["cell_inventory"] = [
        cell(1, 1, [20, 78, 100, 94], residual_refs),
        cell(2, 1, [20, 94, 65, 110], [seed_refs[0]]),
        cell(2, 2, [80, 94, 100, 110], [seed_refs[1]]),
        cell(2, 3, [220, 94, 265, 110], [seed_refs[2]]),
        cell(2, 4, [280, 94, 300, 110], [seed_refs[3]]),
    ]
    for x in (65, 100, 265):
        builder.add_vector_line(page_number=1, bbox=[x, 75, x + 0.2, 110])
    for y in (78, 94, 110):
        builder.add_vector_line(page_number=1, bbox=[15, y, 305, y + 0.2])

    continuation_refs: list[str] = []
    continuation_y = 110 + continuation_gap
    for offset, values in enumerate(
        (
            ("Left one", "11", "Right one", "21"),
            ("Left two", "12", "Right two", "22"),
        )
    ):
        continuation_refs += builder.add_row(
            page_number=1,
            y=continuation_y + offset * 14,
            entries=[
                (20 + continuation_shift, values[0], 45),
                (80 + continuation_shift, values[1], 20),
                (220 + continuation_shift, values[2], 45),
                (280 + continuation_shift, values[3], 20),
            ],
        )
    tail_refs: list[str] = []
    for offset, (label, value) in enumerate(
        (("Right three", "23"), ("Right four", "24"), ("Right five", "25")),
        2,
    ):
        entries: list[tuple[float, str, float]] = [
            (220 + continuation_shift, label, 45),
            (280 + continuation_shift, value, 20),
        ]
        if symmetric_tail:
            entries = [
                (20 + continuation_shift, f"Left {offset + 1}", 45),
                (80 + continuation_shift, str(10 + offset + 1), 20),
                *entries,
            ]
        tail_refs += builder.add_row(
            page_number=1,
            y=continuation_y + offset * 14,
            entries=entries,
        )
    return builder, residual_refs, seed_refs, [*continuation_refs, *tail_refs]


def test_adjacent_tables_are_separate_and_prose_is_excluded() -> None:
    builder = ProjectionBuilder()
    prose_refs = builder.add_row(
        page_number=1,
        y=20,
        entries=[(20, "This paragraph explains the following schedules.")],
    )
    first_refs = []
    first_refs += builder.add_row(
        page_number=1,
        y=100,
        entries=[(20, "Item"), (200, "Amount")],
    )
    first_refs += builder.add_row(
        page_number=1,
        y=114,
        entries=[(20, "Cash"), (200, "10")],
    )
    first_refs += builder.add_row(
        page_number=1,
        y=128,
        entries=[(20, "Bonds"), (200, "20")],
    )
    second_refs = []
    second_refs += builder.add_row(
        page_number=1,
        y=190,
        entries=[(20, "Category"), (200, "Count")],
    )
    second_refs += builder.add_row(
        page_number=1,
        y=204,
        entries=[(20, "Open"), (200, "3")],
    )
    second_refs += builder.add_row(
        page_number=1,
        y=218,
        entries=[(20, "Closed"), (200, "4")],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 95, 245, 140],
        word_refs=first_refs,
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 185, 245, 230],
        word_refs=second_refs,
    )

    result = _recover(builder)

    assert len(result.tables) == 2
    assert _table_text(result.tables[0])[0] == ["Item", "Amount"]
    assert _table_text(result.tables[1])[0] == ["Category", "Count"]
    assert prose_refs == result.paragraph_owned_word_refs
    table_anchor_refs = {
        anchor["locator"]["source_block_ref"]
        for anchor in result.anchors
        if anchor["locator"]["source_block_ref"].startswith("synthetic_word_")
    }
    assert not table_anchor_refs.intersection(prose_refs)
    assert result.unowned_word_refs == []


def test_terminal_total_followed_by_header_reset_splits_logical_tables() -> None:
    builder = ProjectionBuilder(ref_prefix="terminal_reset")
    first = []
    first += builder.add_row(
        page_number=1,
        y=80,
        entries=[(20, "Item", 45), (200, "Amount", 45)],
    )
    first += builder.add_row(
        page_number=1,
        y=94,
        entries=[(20, "Alpha", 45), (200, "10", 45)],
    )
    first += builder.add_row(
        page_number=1,
        y=108,
        entries=[(20, "Beta", 45), (200, "20", 45)],
    )
    first += builder.add_row(
        page_number=1,
        y=122,
        entries=[(20, "Grand Total", 70), (200, "30", 45)],
    )
    second = builder.add_row(
        page_number=1,
        y=136,
        entries=[(20, "Second schedule", 80)],
    )
    second += builder.add_row(
        page_number=1,
        y=150,
        entries=[(20, "Category", 55), (200, "Count", 45)],
    )
    second += builder.add_row(
        page_number=1,
        y=164,
        entries=[(20, "Open", 45), (200, "3", 45)],
    )
    second += builder.add_row(
        page_number=1,
        y=178,
        entries=[(20, "Closed", 45), (200, "4", 45)],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 75, 250, 190],
        word_refs=[*first, *second],
    )

    result = _recover(builder)

    assert len(result.tables) == 2
    assert _table_text(result.tables[0]) == [
        ["Item", "Amount"],
        ["Alpha", "10"],
        ["Beta", "20"],
        ["Grand Total", "30"],
    ]
    assert _table_text(result.tables[1]) == [
        ["Second schedule"],
        ["Category", "Count"],
        ["Open", "3"],
        ["Closed", "4"],
    ]


def test_sparse_aligned_component_merges_across_bounded_whitespace() -> None:
    builder = ProjectionBuilder(ref_prefix="sparse_merge")
    refs = []
    refs += builder.add_row(
        page_number=1,
        y=80,
        entries=[(20, "Item", 55), (200, "Amount", 45)],
    )
    refs += builder.add_row(
        page_number=1,
        y=94,
        entries=[(20, "Alpha", 45), (200, "10", 45)],
    )
    refs += builder.add_row(
        page_number=1,
        y=150,
        entries=[(20, "Beta", 45), (200, "20", 45)],
    )
    refs += builder.add_row(
        page_number=1,
        y=164,
        entries=[(20, "Gamma", 45), (200, "30", 45)],
    )
    refs += builder.add_row(
        page_number=1,
        y=178,
        entries=[(20, "Grand Total", 70), (200, "60", 45)],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 75, 250, 190],
        word_refs=refs,
    )

    result = _recover(builder)

    assert len(result.tables) == 1
    assert _table_text(result.tables[0]) == [
        ["Item", "Amount"],
        ["Alpha", "10"],
        ["Beta", "20"],
        ["Gamma", "30"],
        ["Grand Total", "60"],
    ]
    assert result.unowned_word_refs == []


def test_repeated_mirrored_side_by_side_lanes_split_without_word_duplication() -> (
    None
):
    builder = ProjectionBuilder(ref_prefix="side_by_side")
    refs = []
    for y, left_label, left_value, right_label, right_value in (
        (80, "Item", "Amount", "Category", "Count"),
        (94, "Alpha", "10", "Open", "3"),
        (108, "Beta", "20", "Closed", "4"),
        (122, "Grand Total", "30", "Grand Total", "7"),
    ):
        refs += builder.add_row(
            page_number=1,
            y=y,
            entries=[
                (20, left_label, 45),
                (100, left_value, 40),
                (240, right_label, 50),
                (330, right_value, 40),
            ],
        )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 75, 375, 135],
        word_refs=refs,
    )

    result = _recover(builder)

    assert len(result.tables) == 2
    assert _table_text(result.tables[0]) == [
        ["Item", "Amount"],
        ["Alpha", "10"],
        ["Beta", "20"],
        ["Grand Total", "30"],
    ]
    assert _table_text(result.tables[1]) == [
        ["Category", "Count"],
        ["Open", "3"],
        ["Closed", "4"],
        ["Grand Total", "7"],
    ]
    assert len(result.source_word_ownership) == len(set(refs))
    assert result.unowned_word_refs == []


@pytest.mark.parametrize(
    (
        "right_lane_start",
        "header_first_width",
        "header_second_x",
        "linearized",
    ),
    [
        (180.0, 60.0, 84.0, True),
        (105.0, 60.0, 84.0, False),
        (180.0, 126.0, 150.0, False),
    ],
)
def test_common_header_mirrored_lane_pairs_linearize_inside_one_table(
    right_lane_start: float,
    header_first_width: float,
    header_second_x: float,
    linearized: bool,
) -> None:
    builder = ProjectionBuilder(ref_prefix="lane_linearization")
    header_words = builder.add_row(
        page_number=1,
        y=80,
        entries=[
            (20, "Primary heading", header_first_width),
            (header_second_x, "Measure", 20),
        ],
    )
    lane_words = builder.add_row(
        page_number=1,
        y=96,
        entries=[
            (20, "Left label", 60),
            (80, "10", 20),
            (right_lane_start, "Right label", 60),
            (right_lane_start + 60, "20", 20),
        ],
    )
    right_edge = right_lane_start + 80
    builder.add_candidate(
        page_number=1,
        bbox=[15, 75, right_edge + 15, 110],
        word_refs=[*header_words, *lane_words],
    )
    candidate = builder.candidates[-1]
    candidate["table_strategy_ref"] = "ruled_lines_v0"
    candidate["columns_total"] = 4
    page_ref = str(builder.pages[0]["page_ref"])
    candidate["row_inventory"] = [
        {
            "row_ref": f"lane_linearization_row_{ordinal}",
            "row_ordinal": ordinal,
            "page_ref": page_ref,
        }
        for ordinal in (1, 2)
    ]

    def cell(
        row: int,
        column: int,
        bbox: list[float],
        word_refs: list[str],
    ) -> dict[str, Any]:
        return {
            "cell_ref": f"lane_linearization_cell_{row}_{column}",
            "row_ref": f"lane_linearization_row_{row}",
            "page_ref": page_ref,
            "row_ordinal": row,
            "column_ordinal": column,
            "bbox_ref": builder._add_bbox(page_ref=page_ref, bbox=bbox),
            "word_refs": word_refs,
        }

    header_right = max(110.0, header_second_x + 20.0)
    candidate["cell_inventory"] = [
        cell(1, 1, [20, 78, header_right, 92], header_words),
        cell(2, 1, [20, 94, 80, 108], [lane_words[0]]),
        cell(2, 2, [80, 94, 100, 108], [lane_words[1]]),
        cell(
            2,
            3,
            [right_lane_start, 94, right_lane_start + 60, 108],
            [lane_words[2]],
        ),
        cell(
            2,
            4,
            [right_lane_start + 60, 94, right_edge, 108],
            [lane_words[3]],
        ),
    ]
    for x in (80, 100, right_lane_start + 60):
        builder.add_vector_line(page_number=1, bbox=[x, 75, x + 0.2, 110])
    for y in (78, 94, 108):
        builder.add_vector_line(
            page_number=1,
            bbox=[15, y, right_edge + 15, y + 0.2],
        )

    result = _recover(builder)
    table = result.tables[0]

    assert len(result.tables) == 1
    if linearized:
        assert _table_text(table) == [
            ["Primary heading", "Measure"],
            ["Left label", "10"],
            ["Right label", "20"],
        ]
        assert len(table["logical_columns"]) == 2
        assert all(
            column["header_path"] for column in table["logical_columns"]
        )
    else:
        assert _table_text(table) == [
            ["Primary heading Measure"],
            ["Left label", "10", "Right label", "20"],
        ]
        assert len(table["logical_columns"]) == 4
    assert len(result.source_word_ownership) == len(
        {*header_words, *lane_words}
    )
    assert result.unowned_word_refs == []


def test_adjacent_mirrored_lanes_reconcile_into_two_exact_owned_tables() -> None:
    builder, residual_refs, seed_refs, continuation_refs = (
        _adjacent_mirrored_lane_builder()
    )

    result = _recover(builder)

    assert len(result.tables) == 2
    assert _table_text(result.tables[0]) == [
        ["Left heading", "10"],
        ["Left one", "11"],
        ["Left two", "12"],
    ]
    assert _table_text(result.tables[1]) == [
        ["Right heading", "20"],
        ["Right one", "21"],
        ["Right two", "22"],
        ["Right three", "23"],
        ["Right four", "24"],
        ["Right five", "25"],
    ]
    issue_code_by_id = {
        issue["issue_id"]: issue["code"] for issue in result.issues
    }
    for table in result.tables:
        assert len(table["logical_columns"]) == 2
        for column in table["logical_columns"]:
            if column["header_path"]:
                assert column["issue_ids"] == []
            else:
                assert column["issue_ids"]
                assert {
                    issue_code_by_id[issue_id]
                    for issue_id in column["issue_ids"]
                } == {"logical_column_header_path_unknown"}
    assert result.paragraph_owned_word_refs == residual_refs
    owned_refs = {
        ownership["source_word_id"]
        for ownership in result.source_word_ownership
    }
    expected_table_refs = {*seed_refs, *continuation_refs}
    assert len(owned_refs) == len(expected_table_refs)
    assert len(result.source_word_ownership) == len(expected_table_refs)
    assert result.unowned_word_refs == []


@pytest.mark.parametrize(
    "case",
    ("symmetric_tail", "large_gap", "incomplete_track_overlap", "value_residual"),
)
def test_adjacent_mirrored_lane_reconciliation_rejects_geometry_near_misses(
    case: str,
) -> None:
    builder, residual_refs, _, _ = _adjacent_mirrored_lane_builder(
        symmetric_tail=case == "symmetric_tail",
        continuation_gap=12.0 if case == "large_gap" else 3.0,
        continuation_shift=30.0 if case == "incomplete_track_overlap" else 0.0,
        value_like_residual=case == "value_residual",
    )

    result = _recover(builder)

    # Without the complete proof the parser seed remains intact; in
    # particular its physical singleton must not be silently discarded.
    assert not set(residual_refs).issubset(result.paragraph_owned_word_refs)
    assert result.unowned_word_refs == []


def test_asymmetric_lane_reconciliation_rejects_crossing_entries() -> None:
    word_ordinal = 0

    def row(y: float, entries: list[tuple[float, float, str]]):
        nonlocal word_ordinal
        bands = []
        words = []
        for x0, x1, value in entries:
            word_ordinal += 1
            word = recovery_module._Word(
                word_ref=f"crossing_word_{word_ordinal}",
                page_ref="crossing_page",
                text=value,
                bbox=(x0, y, x1, y + 8),
                order=word_ordinal,
            )
            words.append(word)
            bands.append(
                recovery_module._EntryBand(
                    words=[word],
                    bbox=word.bbox,
                    text=value,
                    anchor_ids=[],
                )
            )
        return recovery_module._RowBand(
            page_ref="crossing_page",
            bbox=_merge([list(word.bbox) for word in words]),
            words=words,
            entries=bands,
        )

    rows = [
        row(100, [(20, 65, "Left"), (80, 130, "10"), (120, 165, "Right"), (180, 200, "20")]),
        row(114, [(20, 65, "Left"), (80, 130, "11"), (120, 165, "Right"), (180, 200, "21")]),
        row(128, [(120, 165, "Right"), (180, 200, "22")]),
        row(142, [(120, 165, "Right"), (180, 200, "23")]),
        row(156, [(120, 165, "Right"), (180, 200, "24")]),
    ]

    assert (
        recovery_module._strict_asymmetric_continuation_lanes(
            rows,
            config=recovery_module.LogicalRowTableRecoveryConfig(),
        )
        is None
    )


def test_region_partition_guard_rejects_nonexact_word_ownership() -> None:
    word = recovery_module._Word(
        word_ref="duplicate_word",
        page_ref="duplicate_page",
        text="Label",
        bbox=(20, 100, 60, 108),
        order=1,
    )
    entry = recovery_module._EntryBand(
        words=[word],
        bbox=word.bbox,
        text=word.text,
        anchor_ids=[],
    )
    row = recovery_module._RowBand(
        page_ref=word.page_ref,
        bbox=word.bbox,
        words=[word],
        entries=[entry],
    )
    region = recovery_module._Region(
        source_ref="duplicate_region",
        page=recovery_module._Page(
            page_ref=word.page_ref,
            page_number=1,
            width=400,
            height=800,
        ),
        bbox=word.bbox,
        words=[word, word],
        rows=[row],
        confidence=1.0,
        origin="ALIGNED_DISCOVERY",
        object_refs=[],
    )

    assert not recovery_module._region_has_exact_row_word_partition(region)


def test_candidate_free_alignment_recovers_table_but_not_surrounding_prose() -> None:
    builder = ProjectionBuilder(ref_prefix="alignment")
    prose_refs = builder.add_row(
        page_number=1,
        y=25,
        entries=[(15, "Narrative before the schedule")],
    )
    table_refs = []
    table_refs += builder.add_row(
        page_number=1,
        y=100,
        entries=[(20, "Item", 40), (200, "Amount", 40)],
    )
    table_refs += builder.add_row(
        page_number=1,
        y=114,
        entries=[(20, "Cash", 40), (200, "10", 40)],
    )
    table_refs += builder.add_row(
        page_number=1,
        y=128,
        entries=[(20, "Bonds", 40), (200, "20", 40)],
    )
    table_refs += builder.add_row(
        page_number=1,
        y=142,
        entries=[(20, "Grand Total", 40), (200, "30", 40)],
    )

    result = _recover(builder)

    assert len(result.tables) == 1
    assert result.diagnostics["aligned_regions_total"] == 1
    assert result.paragraph_owned_word_refs == prose_refs
    assert {
        item["source_word_id"] for item in result.source_word_ownership
    } == {
        recovery_module._identifier("source_word", [word_ref])
        for word_ref in table_refs
    }


def test_core_envelope_keeps_title_and_header_but_rejects_adjacent_prose() -> None:
    builder = ProjectionBuilder(ref_prefix="core_envelope")
    before = builder.add_row(
        page_number=1,
        y=62,
        entries=[(20, "This sentence introduces a separate discussion.", 210)],
    )
    title = builder.add_row(
        page_number=1,
        y=76,
        entries=[(20, "Account balances", 55)],
    )
    group = builder.add_row(
        page_number=1,
        y=90,
        entries=[(20, "Asset group", 45)],
    )
    header = builder.add_row(
        page_number=1,
        y=104,
        entries=[(35, "Item", 65), (200, "Amount", 45)],
    )
    data = []
    data += builder.add_row(
        page_number=1,
        y=118,
        entries=[(35, "Cash", 45), (200, "10", 45)],
    )
    data += builder.add_row(
        page_number=1,
        y=132,
        entries=[(35, "Bonds", 45), (200, "20", 45)],
    )
    data += builder.add_row(
        page_number=1,
        y=146,
        entries=[(35, "Grand Total", 45), (200, "30", 45)],
    )
    after = builder.add_row(
        page_number=1,
        y=160,
        entries=[(20, "Outside table note", 110)],
    )

    result = _recover(builder)

    assert len(result.tables) == 1
    assert _table_text(result.tables[0]) == [
        ["Account balances"],
        ["Asset group"],
        ["Item", "Amount"],
        ["Cash", "10"],
        ["Bonds", "20"],
        ["Grand Total", "30"],
    ]
    assert set(result.paragraph_owned_word_refs) == {*before, *after}
    assert len(result.source_word_ownership) == len(
        {*title, *group, *header, *data}
    )


@pytest.mark.parametrize(
    ("text", "bbox", "covered_ordinals", "expected"),
    [
        (
            "One two three four five six seven eight nine ten",
            (80.0, 80.0, 185.0, 88.0),
            None,
            True,
        ),
        (
            "One two three four five six seven eight nine ten",
            (20.0, 80.0, 60.0, 88.0),
            [0, 1],
            True,
        ),
        (
            "One two three four five six seven eight",
            (20.0, 80.0, 60.0, 88.0),
            None,
            True,
        ),
        (
            "One two three four five six seven eight nine",
            (20.0, 80.0, 60.0, 88.0),
            None,
            False,
        ),
        (
            "One two three four five six seven eight",
            (48.0, 80.0, 68.0, 88.0),
            None,
            False,
        ),
        (
            "One two three four five six seven eight.",
            (20.0, 80.0, 60.0, 88.0),
            None,
            False,
        ),
    ],
)
def test_leading_singleton_requires_center_span_or_compact_label(
    text: str,
    bbox: tuple[float, float, float, float],
    covered_ordinals: list[int] | None,
    expected: bool,
) -> None:
    ordinal = 0

    def make_row(
        y: float,
        entries: list[tuple[tuple[float, float, float, float], str]],
        *,
        first_entry_ordinals: list[int] | None = None,
    ):
        nonlocal ordinal
        entry_bands = []
        words = []
        for index, (entry_bbox, value) in enumerate(entries):
            ordinal += 1
            word = recovery_module._Word(
                word_ref=f"leading_envelope_word_{ordinal}",
                page_ref="leading_envelope_page",
                text=value,
                bbox=entry_bbox,
                order=ordinal,
            )
            words.append(word)
            entry_bands.append(
                recovery_module._EntryBand(
                    words=[word],
                    bbox=entry_bbox,
                    text=value,
                    anchor_ids=[],
                    geometry_column_ordinals=(
                        first_entry_ordinals if index == 0 else None
                    ),
                )
            )
        return recovery_module._RowBand(
            page_ref="leading_envelope_page",
            bbox=tuple(_merge([list(word.bbox) for word in words])),
            words=words,
            entries=entry_bands,
        )

    candidate = make_row(
        80,
        [(bbox, text)],
        first_entry_ordinals=covered_ordinals,
    )
    core_rows = [
        make_row(
            y,
            [
                ((20.0, y, 65.0, y + 8.0), label),
                ((200.0, y, 245.0, y + 8.0), value),
            ],
        )
        for y, label, value in (
            (100.0, "Alpha", "10"),
            (114.0, "Beta", "20"),
            (128.0, "Gamma", "30"),
        )
    ]

    assert (
        recovery_module._row_belongs_to_core_envelope(
            candidate,
            core_rows=core_rows,
            direction="LEADING",
            config=recovery_module.LogicalRowTableRecoveryConfig(),
        )
        is expected
    )


def _boundary_bracket_builder(
    case: str = "positive",
) -> tuple[ProjectionBuilder, list[str], list[str]]:
    builder = ProjectionBuilder(ref_prefix=f"boundary_bracket_{case}")
    bracket_refs: list[str] = []
    main_refs: list[str] = []
    leading_x = 100 if case == "ambiguous_target" else 20
    if case != "missing_leading":
        leading_rows = (
            [(48, "One two three four five six seven eight nine", 20)]
            if case == "leading_envelope_fail"
            else [
                (leading_x, "Schedule overview", 80),
                (leading_x, "Balances section", 70),
                (leading_x, "Detail group", 60),
            ]
        )
        start_y = 88 if case == "leading_envelope_fail" else 64
        for offset, entry in enumerate(leading_rows):
            bracket_refs += builder.add_row(
                page_number=1,
                y=start_y + offset * 12,
                entries=[entry],
            )

    def add_main(label_x: float, prefix: str) -> list[str]:
        refs: list[str] = []
        for y, label, value in (
            (100, f"{prefix} item", "Amount"),
            (114, f"{prefix} alpha", "10"),
            (128, f"{prefix} beta", "20"),
            (142, f"{prefix} gamma", "30"),
        ):
            refs += builder.add_row(
                page_number=1,
                y=y,
                entries=[(label_x, label, 45), (200, value, 30)],
            )
        builder.add_candidate(
            page_number=1,
            bbox=[label_x - 5, 95, 235, 152],
            word_refs=refs,
        )
        # The candidate helper adds a synthetic rectangle around the crop.  It
        # is not a source separator; remove it so only the dedicated separator
        # case exercises the hard vector/rectangle boundary rejection.
        builder.rects.pop()
        return refs

    main_refs += add_main(20, "Main")
    if case == "ambiguous_target":
        main_refs += add_main(100, "Second")

    if case != "missing_trailing":
        trailing_y = 165 if case == "gap_over_one_height" else 154
        trailing_label = "Closing line" if case == "nonterminal_tail" else "Total"
        trailing_value_x = 150 if case == "value_track_mismatch" else 200
        bracket_refs += builder.add_row(
            page_number=1,
            y=trailing_y,
            entries=[(20, trailing_label, 90), (trailing_value_x, "60", 30)],
        )
    if case == "separator":
        builder.add_vector_line(page_number=1, bbox=[15, 152, 235, 152.2])
    return builder, bracket_refs, main_refs


def test_unique_boundary_bracket_attaches_with_exact_ownership() -> None:
    builder, bracket_refs, main_refs = _boundary_bracket_builder()

    result = _recover(builder)

    assert len(result.tables) == 1
    assert _table_text(result.tables[0]) == [
        ["Schedule overview"],
        ["Balances section"],
        ["Detail group"],
        ["Main item", "Amount"],
        ["Main alpha", "10"],
        ["Main beta", "20"],
        ["Main gamma", "30"],
        ["Total", "60"],
    ]
    assert len(result.tables[0]["logical_columns"]) == 2
    assert result.paragraph_owned_word_refs == []
    expected_refs = {*bracket_refs, *main_refs}
    assert len(result.source_word_ownership) == len(expected_refs)
    assert result.unowned_word_refs == []


@pytest.mark.parametrize(
    "case",
    (
        "missing_leading",
        "missing_trailing",
        "gap_over_one_height",
        "separator",
        "nonterminal_tail",
        "value_track_mismatch",
        "ambiguous_target",
        "leading_envelope_fail",
    ),
)
def test_boundary_bracket_rejects_incomplete_or_ambiguous_proof(case: str) -> None:
    builder, bracket_refs, _ = _boundary_bracket_builder(case)

    result = _recover(builder)

    assert set(bracket_refs).issubset(result.paragraph_owned_word_refs)
    assert result.unowned_word_refs == []


def test_boundary_bracket_rejects_ownership_overlap() -> None:
    shared = recovery_module._Word(
        word_ref="boundary_overlap_word",
        page_ref="boundary_overlap_page",
        text="Shared",
        bbox=(20, 80, 60, 88),
        order=1,
    )
    entry = recovery_module._EntryBand(
        words=[shared],
        bbox=shared.bbox,
        text=shared.text,
        anchor_ids=[],
    )
    row = recovery_module._RowBand(
        page_ref=shared.page_ref,
        bbox=shared.bbox,
        words=[shared],
        entries=[entry],
    )
    region = recovery_module._Region(
        source_ref="boundary_overlap_region",
        page=recovery_module._Page(
            page_ref=shared.page_ref,
            page_number=1,
            width=400,
            height=800,
        ),
        bbox=shared.bbox,
        words=[shared],
        rows=[row],
        confidence=1.0,
        origin="PARSER_CANDIDATE",
        object_refs=[],
    )

    assert (
        recovery_module._rebuild_with_boundary_bracket(
            region,
            leading_rows=[row],
            trailing_row=row,
            object_bboxes=[],
        )
        is None
    )


def _leading_header_stack_builder(
    case: str = "positive",
) -> tuple[ProjectionBuilder, list[str], list[str]]:
    builder = ProjectionBuilder(ref_prefix=f"leading_header_stack_{case}")
    header_refs: list[str] = []
    main_refs: list[str] = []

    def add_main(label_x: float = 20, prefix: str = "Main") -> list[str]:
        refs: list[str] = []
        for y, label, value in (
            (100, f"{prefix} item", "Amount"),
            (114, f"{prefix} alpha", "10"),
            (128, f"{prefix} beta", "20"),
            (142, f"{prefix} gamma", "30"),
        ):
            refs += builder.add_row(
                page_number=1,
                y=y,
                entries=[(label_x, label, 60), (200, value, 30)],
            )
        builder.add_candidate(
            page_number=1,
            bbox=[label_x - 5, 95, 235, 152],
            word_refs=refs,
        )
        builder.rects.pop()
        return refs

    def broad_header(y: float, words: int = 3) -> list[str]:
        width = (210 - (words - 1) * 2) / words
        return builder.add_row(
            page_number=1,
            y=y,
            entries=[
                (20 + ordinal * (width + 2), f"Header{ordinal}", width)
                for ordinal in range(words)
            ],
        )

    if case == "source_order_inversion":
        main_refs += add_main()

    if case == "single_row":
        header_refs += broad_header(90, words=2)
    elif case == "verbose":
        header_refs += broad_header(72, words=5)
        header_refs += builder.add_row(
            page_number=1,
            y=90,
            entries=[(200, "Right", 30)],
        )
    elif case == "value_row":
        header_refs += broad_header(72, words=2)
        header_refs += builder.add_row(
            page_number=1,
            y=90,
            entries=[(200, "2025", 30)],
        )
    elif case == "core_row":
        header_refs += broad_header(72, words=2)
        header_refs += builder.add_row(
            page_number=1,
            y=90,
            entries=[
                (20, "Left", 35),
                (110, "Middle", 45),
                (200, "Right", 35),
            ],
        )
    elif case == "outer_gap_over_one_height":
        header_refs += broad_header(60, words=2)
        header_refs += builder.add_row(
            page_number=1,
            y=82,
            entries=[(200, "Right", 30)],
        )
    elif case == "internal_gap_over_limit":
        header_refs += broad_header(54, words=2)
        header_refs += builder.add_row(
            page_number=1,
            y=90,
            entries=[(200, "Right", 30)],
        )
    elif case == "unsupported_entry":
        header_refs += broad_header(72, words=2)
        header_refs += builder.add_row(
            page_number=1,
            y=90,
            entries=[(330, "Outside", 35)],
        )
    elif case == "one_track_only":
        header_refs += builder.add_row(
            page_number=1,
            y=76,
            entries=[(200, "Upper", 30)],
        )
        header_refs += builder.add_row(
            page_number=1,
            y=90,
            entries=[(200, "Lower", 30)],
        )
    else:
        header_refs += broad_header(60)
        header_refs += builder.add_row(
            page_number=1,
            y=72,
            entries=[
                (
                    20,
                    "Left",
                    140 if case == "ambiguous_target" else 60,
                ),
                (200, "Right", 30),
            ],
        )
        header_refs += builder.add_row(
            page_number=1,
            y=90 if case == "outer_separator" else 92,
            entries=[(200, "Final", 14), (216, "header", 14)],
        )

    if case != "source_order_inversion":
        main_refs += add_main()
    if case == "ambiguous_target":
        main_refs += add_main(label_x=100, prefix="Second")
    if case == "outer_separator":
        builder.add_vector_line(page_number=1, bbox=[15, 99, 235, 99.2])
    elif case == "positive":
        builder.add_vector_line(page_number=1, bbox=[15, 70, 235, 70.2])
    return builder, header_refs, main_refs


def test_unique_leading_header_stack_attaches_physical_rows_unchanged() -> None:
    builder, header_refs, main_refs = _leading_header_stack_builder()

    result = _recover(builder)

    assert len(result.tables) == 1
    assert _table_text(result.tables[0]) == [
        ["Header0 Header1 Header2"],
        ["Left", "Right"],
        ["Final header"],
        ["Main item", "Amount"],
        ["Main alpha", "10"],
        ["Main beta", "20"],
        ["Main gamma", "30"],
    ]
    assert len(result.tables[0]["logical_columns"]) == 2
    assert result.paragraph_owned_word_refs == []
    assert len(result.source_word_ownership) == len(
        {*header_refs, *main_refs}
    )
    assert result.unowned_word_refs == []


@pytest.mark.parametrize(
    "case",
    (
        "single_row",
        "verbose",
        "value_row",
        "core_row",
        "outer_gap_over_one_height",
        "internal_gap_over_limit",
        "outer_separator",
        "unsupported_entry",
        "one_track_only",
        "source_order_inversion",
        "ambiguous_target",
    ),
)
def test_leading_header_stack_rejects_incomplete_or_ambiguous_proof(
    case: str,
) -> None:
    builder, header_refs, _ = _leading_header_stack_builder(case)

    result = _recover(builder)

    assert set(header_refs).issubset(result.paragraph_owned_word_refs)
    assert result.unowned_word_refs == []


def test_leading_header_stack_rejects_ownership_overlap() -> None:
    shared = recovery_module._Word(
        word_ref="leading_header_overlap_word",
        page_ref="leading_header_overlap_page",
        text="Shared",
        bbox=(20, 80, 60, 88),
        order=1,
    )
    entry = recovery_module._EntryBand(
        words=[shared],
        bbox=shared.bbox,
        text=shared.text,
        anchor_ids=[],
    )
    row = recovery_module._RowBand(
        page_ref=shared.page_ref,
        bbox=shared.bbox,
        words=[shared],
        entries=[entry],
    )
    region = recovery_module._Region(
        source_ref="leading_header_overlap_region",
        page=recovery_module._Page(
            page_ref=shared.page_ref,
            page_number=1,
            width=400,
            height=800,
        ),
        bbox=shared.bbox,
        words=[shared],
        rows=[row],
        confidence=1.0,
        origin="PARSER_CANDIDATE",
        object_refs=[],
    )

    assert (
        recovery_module._rebuild_with_leading_header_stack(
            region,
            leading_rows=[row],
            object_bboxes=[],
        )
        is None
    )


def test_sparse_nested_multilevel_groups_and_totals_are_row_first() -> None:
    builder = ProjectionBuilder(ref_prefix="nested")
    refs = []
    refs += builder.add_row(
        page_number=1,
        y=50,
        entries=[(10, "Item"), (200, "Amount"), (300, "Rate")],
    )
    refs += builder.add_row(page_number=1, y=64, entries=[(10, "Assets")])
    refs += builder.add_row(page_number=1, y=78, entries=[(25, "Cash")])
    refs += builder.add_row(
        page_number=1,
        y=92,
        entries=[(40, "Checking"), (200, "100"), (300, "1")],
    )
    refs += builder.add_row(
        page_number=1,
        y=106,
        entries=[(40, "Savings"), (200, "200"), (300, "2")],
    )
    refs += builder.add_row(
        page_number=1,
        y=120,
        entries=[(40, "Other"), (200, "5")],
    )
    refs += builder.add_row(
        page_number=1,
        y=134,
        entries=[(25, "Subtotal Cash"), (200, "305")],
    )
    refs += builder.add_row(
        page_number=1,
        y=148,
        entries=[(10, "Grand Total"), (200, "305")],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[5, 45, 340, 160],
        word_refs=refs,
    )

    result = _recover(builder)
    table = result.tables[0]
    rows = table["ordered_rows"]

    assert [row["role"] for row in rows] == [
        "COLUMN_HEADER",
        "GROUP_HEADER",
        "GROUP_HEADER",
        "DATA",
        "DATA",
        "DATA",
        "SUBTOTAL",
        "TOTAL",
    ]
    assets, cash, checking, savings, other, subtotal = rows[1:7]
    assert assets["nesting_level"] == 0
    assert cash["nesting_level"] == 1
    assert cash["parent_row_id"] == assets["row_id"]
    assert checking["nesting_level"] == 2
    assert checking["parent_row_id"] == cash["row_id"]
    assert savings["parent_row_id"] == cash["row_id"]
    assert other["parent_row_id"] == cash["row_id"]
    assert subtotal["parent_row_id"] == assets["row_id"]
    assert _table_text(table)[5] == ["Other", "5"]
    assert all("rows" not in table or key == "ordered_rows" for key in table)
    assert len(table["logical_columns"]) == 2
    assert result.unowned_word_refs == []
    _validate_v2_component_shapes(result)

def test_cross_page_continuation_preserves_repeated_header_and_source_parts() -> None:
    builder = ProjectionBuilder(
        page_numbers=(1, 2),
        ref_prefix="continuation",
    )
    page_one_refs = []
    page_one_refs += builder.add_row(
        page_number=1,
        y=760,
        entries=[(20, "Item", 50), (200, "Amount", 50)],
    )
    page_one_refs += builder.add_row(
        page_number=1,
        y=774,
        entries=[(20, "Cash", 50), (200, "10", 50)],
    )
    page_one_refs += builder.add_row(
        page_number=1,
        y=788,
        entries=[(20, "Bonds", 50), (200, "20", 50)],
    )
    page_two_refs = []
    page_two_refs += builder.add_row(
        page_number=2,
        y=8,
        entries=[(20, "Item", 50), (200, "Amount", 50)],
    )
    page_two_refs += builder.add_row(
        page_number=2,
        y=22,
        entries=[(20, "Funds", 50), (200, "30", 50)],
    )
    page_two_refs += builder.add_row(
        page_number=2,
        y=36,
        entries=[(20, "Grand Total", 50), (200, "60", 50)],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 755, 260, 800],
        word_refs=page_one_refs,
    )
    builder.add_candidate(
        page_number=2,
        bbox=[15, 0, 260, 50],
        word_refs=page_two_refs,
    )

    result = _recover(builder)
    table = result.tables[0]

    assert len(result.tables) == 1
    assert [part["continuation_status"] for part in table["source_parts"]] == [
        "START",
        "END",
    ]
    assert table["ordered_rows"][3]["role"] == "CONTINUATION_HEADER"
    assert table["source_parts"][1]["continuation_evidence_ids"]
    assert [row["ordinal"] for row in table["ordered_rows"]] == list(range(6))
    assert result.diagnostics["continued_tables_total"] == 1
    _validate_v2_component_shapes(result)


def test_continuation_header_literal_keeps_punctuation_distinct() -> None:
    builder = ProjectionBuilder(
        page_numbers=(1, 2),
        ref_prefix="continuation_literal_punctuation",
    )
    page_one_refs = []
    page_one_refs += builder.add_row(
        page_number=1,
        y=760,
        entries=[(20, "Price, USD", 70), (200, "Amount", 50)],
    )
    page_one_refs += builder.add_row(
        page_number=1,
        y=776,
        entries=[(20, "Cash", 50), (200, "10", 50)],
    )
    page_one_refs += builder.add_row(
        page_number=1,
        y=792,
        entries=[(20, "Bonds", 50), (200, "20", 50)],
    )
    page_two_refs = []
    page_two_refs += builder.add_row(
        page_number=2,
        y=8,
        entries=[(20, "Price USD", 70), (200, "Amount", 50)],
    )
    page_two_refs += builder.add_row(
        page_number=2,
        y=24,
        entries=[(20, "Funds", 50), (200, "30", 50)],
    )
    page_two_refs += builder.add_row(
        page_number=2,
        y=40,
        entries=[(20, "Shares", 50), (200, "40", 50)],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 755, 260, 805],
        word_refs=page_one_refs,
    )
    builder.add_candidate(
        page_number=2,
        bbox=[15, 0, 260, 55],
        word_refs=page_two_refs,
    )

    result = _recover(builder)

    assert len(result.tables) == 2
    assert [
        table["ordered_rows"][0]["entries"][0]["text"]
        for table in result.tables
    ] == ["Price, USD", "Price USD"]
    assert not any(
        row["role"] == "CONTINUATION_HEADER"
        for table in result.tables
        for row in table["ordered_rows"]
    )
    assert result.unowned_word_refs == []


def _continuation_test_region(
    *,
    ref_prefix: str,
    page_number: int,
    row_ys: list[float],
    header: bool,
    title: str | None = None,
) -> recovery_module._Region:
    rows: list[list[list[tuple[float, float, str]]]] = []
    if title is not None:
        rows.append([[(20.0, 170.0, title)]])
    if header:
        rows.append(
            [[(20.0, 70.0, "Item")], [(200.0, 250.0, "Amount")]]
        )
    while len(rows) < len(row_ys):
        ordinal = len(rows) + 1
        rows.append(
            [
                [(20.0, 70.0, f"Item {ordinal}")],
                [(200.0, 250.0, str(ordinal))],
            ]
        )
    region = _internal_microtrack_region(
        rows,
        ref_prefix=ref_prefix,
        row_ys=row_ys,
    )
    region.page = replace(region.page, page_number=page_number)
    if title is not None:
        region.rows[0].external_title = True
    return region


def _continuation_groups(
    *regions: recovery_module._Region,
) -> list[list[recovery_module._Region]]:
    return recovery_module._group_continuations(
        list(regions),
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )


def _materialize_continuation_group(
    regions: list[recovery_module._Region],
) -> tuple[dict[str, Any], recovery_module._RecoveryState]:
    state = recovery_module._RecoveryState(
        source_checksum_sha256=SOURCE_CHECKSUM,
        private_evidence_ref=PRIVATE_EVIDENCE_REF,
        bbox_by_ref={},
    )
    table = recovery_module._materialize_logical_table(
        regions,
        state=state,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )
    return table, state


def test_headerless_next_page_joins_unique_predecessor() -> None:
    left = _continuation_test_region(
        ref_prefix="headerless_left",
        page_number=1,
        row_ys=[760.0, 774.0, 790.0],
        header=True,
    )
    right = _continuation_test_region(
        ref_prefix="headerless_right",
        page_number=2,
        row_ys=[4.0, 18.0, 32.0],
        header=False,
    )

    groups = _continuation_groups(left, right)
    table, state = _materialize_continuation_group(groups[0])

    assert len(groups) == 1
    assert [part["page"] for part in table["source_parts"]] == [1, 2]
    assert [part["continuation_status"] for part in table["source_parts"]] == [
        "START",
        "END",
    ]
    assert set(state.word_ref_by_source_word_id.values()) == {
        word.word_ref for region in (left, right) for word in region.words
    }


def test_distinct_title_breaks_same_grid_with_repeated_header() -> None:
    left = _continuation_test_region(
        ref_prefix="distinct_title_left",
        page_number=1,
        row_ys=[742.0, 758.0, 774.0, 790.0],
        header=True,
        title="Open position transfers",
    )
    right = _continuation_test_region(
        ref_prefix="distinct_title_right",
        page_number=2,
        row_ys=[0.0, 16.0, 30.0, 44.0],
        header=True,
        title="Completed position transfers",
    )

    groups = _continuation_groups(left, right)
    materialized = [_materialize_continuation_group(group) for group in groups]

    assert len(groups) == 2
    assert [
        table["ordered_rows"][0]["entries"][0]["text"]
        for table, _ in materialized
    ] == ["Open position transfers", "Completed position transfers"]
    for region, (table, state) in zip((left, right), materialized):
        assert table["ordered_rows"][0]["role"] == "TABLE_TITLE"
        assert table["ordered_rows"][1]["role"] == "COLUMN_HEADER"
        bound_refs = set(state.word_ref_by_source_word_id.values())
        assert {word.word_ref for word in region.rows[0].words} <= bound_refs
        assert {word.word_ref for word in region.rows[1].words} <= bound_refs


def test_full_path_detected_titles_break_same_grid_repeated_header() -> None:
    builder = ProjectionBuilder(
        page_numbers=(1, 2),
        ref_prefix="full_path_distinct_titles",
    )
    all_refs = []
    candidates = []
    for page_number, title, ys, labels in (
        (1, "Open position transfers", (742, 758, 774, 790), ("Cash", "Bonds")),
        (
            2,
            "Completed position transfers",
            (0, 16, 30, 44),
            ("Funds", "Shares"),
        ),
    ):
        all_refs += builder.add_row(
            page_number=page_number,
            y=ys[0],
            entries=[(20, title, 170)],
        )
        table_rows = [
            builder.add_row(
                page_number=page_number,
                y=ys[1],
                entries=[(20, "Item", 50), (200, "Amount", 50)],
            ),
            builder.add_row(
                page_number=page_number,
                y=ys[2],
                entries=[(20, labels[0], 50), (200, "10", 50)],
            ),
            builder.add_row(
                page_number=page_number,
                y=ys[3],
                entries=[(20, labels[1], 50), (200, "20", 50)],
            ),
        ]
        table_refs = [ref for row in table_rows for ref in row]
        all_refs += table_refs
        candidate_ref = builder.add_candidate(
            page_number=page_number,
            bbox=[15, 754, 260, 800] if page_number == 1 else [15, 12, 260, 56],
            word_refs=table_refs,
        )
        _mark_two_column_candidate_as_ruled(
            builder,
            candidate_ref=candidate_ref,
            page_number=page_number,
            row_refs=table_rows,
        )
        candidates.append(candidate_ref)

    result = _recover(builder)

    assert len(result.tables) == 2
    assert [
        table["ordered_rows"][0]["entries"][0]["text"]
        for table in result.tables
    ] == ["Open position transfers", "Completed position transfers"]
    assert all(
        table["ordered_rows"][0]["role"] == "TABLE_TITLE"
        and table["ordered_rows"][1]["role"] == "COLUMN_HEADER"
        for table in result.tables
    )
    assert len(result.source_word_ownership) == len(all_refs)
    assert result.paragraph_owned_word_refs == []
    assert result.unowned_word_refs == []
    assert len(candidates) == 2


def test_full_path_text_only_header_presence_is_partial_not_silent_boundary() -> None:
    builder = ProjectionBuilder(
        page_numbers=(1, 2),
        ref_prefix="full_path_text_only_continuation",
    )
    first_rows = [
        builder.add_row(
            page_number=1,
            y=760,
            entries=[(20, "Instrument", 70), (200, "Currency", 60)],
        ),
        builder.add_row(
            page_number=1,
            y=774,
            entries=[(20, "Cash", 50), (200, "10", 50)],
        ),
        builder.add_row(
            page_number=1,
            y=790,
            entries=[(20, "Bonds", 50), (200, "20", 50)],
        ),
    ]
    second_rows = [
        builder.add_row(
            page_number=2,
            y=y,
            entries=[(20, instrument, 50), (200, "RUB", 50)],
        )
        for y, instrument in ((4, "LKOH"), (18, "ROSN"), (32, "GAZP"))
    ]
    all_refs = [ref for row in [*first_rows, *second_rows] for ref in row]
    first_candidate_ref = builder.add_candidate(
        page_number=1,
        bbox=[15, 755, 260, 800],
        word_refs=[ref for row in first_rows for ref in row],
    )
    second_candidate_ref = builder.add_candidate(
        page_number=2,
        bbox=[15, 0, 260, 50],
        word_refs=[ref for row in second_rows for ref in row],
    )
    _mark_two_column_candidate_as_ruled(
        builder,
        candidate_ref=first_candidate_ref,
        page_number=1,
        row_refs=first_rows,
    )
    _mark_two_column_candidate_as_ruled(
        builder,
        candidate_ref=second_candidate_ref,
        page_number=2,
        row_refs=second_rows,
    )

    result = _recover(builder)
    issues = [
        issue
        for issue in result.issues
        if issue["code"] == "logical_table_continuation_header_ambiguous"
    ]

    assert len(result.tables) == 2
    assert len(issues) == 1
    affected = next(
        table
        for table in result.tables
        if issues[0]["issue_id"] in table["issues"]
    )
    assert affected["completeness_status"] == "PARTIAL"
    assert affected["source_parts"][0]["page"] == 2
    assert len(result.source_word_ownership) == len(all_refs)
    assert result.paragraph_owned_word_refs == []
    assert result.unowned_word_refs == []


def _source_bound_table_vectors(
    *, y0: int, y1: int, horizontal_ys: tuple[int, ...]
) -> list[str]:
    return [
        *[f"15 {y} m 300 {y} l S" for y in horizontal_ys],
        f"15 {y0} m 15 {y1} l S",
        f"180 {y0} m 180 {y1} l S",
        f"300 {y0} m 300 {y1} l S",
    ]


def _source_bound_case(
    *,
    distinct_second_title: bool = False,
    second_header_labels: tuple[str, str] | None = None,
) -> tuple[bytes, str, dict]:
    first_page = {
        "texts": [
            (25, 55, "Instrument"),
            (200, 55, "Currency"),
            (25, 38, "Cash"),
            (200, 38, "RUB"),
            (25, 22, "Bonds"),
            (200, 22, "RUB"),
        ],
        "vectors": _source_bound_table_vectors(
            y0=15,
            y1=65,
            horizontal_ys=(15, 30, 46, 65),
        ),
    }
    if distinct_second_title:
        second_page = {
            "texts": [
                (25, 310, "Completed position transfers"),
                (25, 288, "Instrument"),
                (200, 288, "Currency"),
                (25, 270, "LKOH"),
                (200, 270, "RUB"),
                (25, 252, "ROSN"),
                (200, 252, "RUB"),
            ],
            "vectors": _source_bound_table_vectors(
                y0=244,
                y1=298,
                horizontal_ys=(244, 262, 280, 298),
            ),
        }
    elif second_header_labels is not None:
        second_page = {
            "texts": [
                (25, 305, second_header_labels[0]),
                (200, 305, second_header_labels[1]),
                (25, 288, "LKOH"),
                (200, 288, "RUB"),
                (25, 271, "ROSN"),
                (200, 271, "RUB"),
            ],
            "vectors": _source_bound_table_vectors(
                y0=260,
                y1=315,
                horizontal_ys=(260, 279, 296, 315),
            ),
        }
    else:
        second_page = {
            "texts": [
                (25, 305, "LKOH"),
                (200, 305, "RUB"),
                (25, 288, "ROSN"),
                (200, 288, "RUB"),
                (25, 271, "GAZP"),
                (200, 271, "RUB"),
            ],
            "vectors": _source_bound_table_vectors(
                y0=260,
                y1=315,
                horizontal_ys=(260, 279, 296, 315),
            ),
        }
    pdf_bytes = _pdf_bytes([first_page, second_page])
    source_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    built = FullSourceArtifactFactory().create().build(
        normalization_run_id="normrun_logical_source_bound",
        document_id="brdoc_logical_source_bound",
        profile_id="techprof_logical_source_bound",
        container_format="pdf",
        content_bytes=pdf_bytes,
        source_checksum_sha256=source_sha256,
    )
    assert built.summary["parser_completeness_status"] == "complete"
    assert built.summary["pdf_layout_projection_status"] == "complete"
    return pdf_bytes, source_sha256, built.payloads[0]


def _source_bound_multirow_header_case(
    *, second_leaf_header: str
) -> tuple[bytes, str, dict]:
    pdf_bytes = _pdf_bytes(
        [
            {
                "texts": [
                    (25, 72, "Trade"),
                    (200, 72, "Settlement"),
                    (25, 55, "Date"),
                    (200, 55, "Date"),
                    (25, 38, "Cash"),
                    (200, 38, "10"),
                    (25, 22, "Bonds"),
                    (200, 22, "20"),
                ],
                "vectors": _source_bound_table_vectors(
                    y0=15,
                    y1=82,
                    horizontal_ys=(15, 30, 46, 63, 82),
                ),
            },
            {
                "texts": [
                    (25, 305, "Trade"),
                    (200, 305, "Settlement"),
                    (25, 288, "Date"),
                    (200, 288, second_leaf_header),
                    (25, 270, "LKOH"),
                    (200, 270, "30"),
                    (25, 252, "ROSN"),
                    (200, 252, "40"),
                ],
                "vectors": _source_bound_table_vectors(
                    y0=244,
                    y1=315,
                    horizontal_ys=(244, 262, 280, 297, 315),
                ),
            },
        ]
    )
    source_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    built = FullSourceArtifactFactory().create().build(
        normalization_run_id="normrun_logical_source_bound_multirow",
        document_id="brdoc_logical_source_bound_multirow",
        profile_id="techprof_logical_source_bound_multirow",
        container_format="pdf",
        content_bytes=pdf_bytes,
        source_checksum_sha256=source_sha256,
    )
    assert built.summary["parser_completeness_status"] == "complete"
    assert built.summary["pdf_layout_projection_status"] == "complete"
    assert built.summary["pdf_table_candidates_total"] == 2
    return pdf_bytes, source_sha256, built.payloads[0]


def _scope_box(projection: dict, refs: list[str]) -> list[int]:
    word_by_ref = {
        str(item["word_ref"]): item for item in projection["word_inventory"]
    }
    bbox_by_ref = {
        str(item["bbox_ref"]): list(item["bbox"])
        for item in projection["bbox_inventory"]
    }
    boxes = [bbox_by_ref[str(word_by_ref[ref]["bbox_ref"])] for ref in refs]
    page = next(
        item
        for item in projection["page_inventory"]
        if item["page_ref"] == word_by_ref[refs[0]]["page_ref"]
    )
    merged = _merge(boxes)
    width = float(page["layout_page_width"])
    height = float(page["layout_page_height"])
    return [
        max(0, math.floor(merged[1] * 1000 / height) - 3),
        max(0, math.floor(merged[0] * 1000 / width) - 3),
        min(1000, math.ceil(merged[3] * 1000 / height) + 3),
        min(1000, math.ceil(merged[2] * 1000 / width) + 3),
    ]


def _scope_request(
    *,
    payload: dict,
    pdf_bytes: bytes,
    source_sha256: str,
    page_number: int,
    title_refs: list[str],
    header_ref_groups: list[list[str]],
    body_refs: list[str],
    body_status: str = "HAS_DATA",
) -> dict:
    projection = payload["pdf_text_layer_projection"]
    page = next(
        item
        for item in projection["page_inventory"]
        if item["page_number"] == page_number
    )
    proposal = {
        "schema_version": SOURCE_BOUND_TABLE_SCOPE_PROPOSAL_SCHEMA,
        "tables": [
            {
                "title_status": "PRESENT" if title_refs else "ABSENT",
                "title_boxes_2d": [_scope_box(projection, title_refs)]
                if title_refs
                else [],
                "header_status": "PRESENT" if header_ref_groups else "ABSENT",
                "header_boxes_2d": [
                    _scope_box(projection, refs) for refs in header_ref_groups
                ],
                "body_status": body_status,
                "body_anchor_boxes_2d": [_scope_box(projection, body_refs)],
            }
        ],
    }
    width = float(page["layout_page_width"])
    height = float(page["layout_page_height"])
    raster = PdfTableRasterFactory().create().render_full_page(
        pdf_bytes=pdf_bytes,
        pdf_sha256=source_sha256,
        document_ref=payload["document_ref"],
        page_ref=page["page_ref"],
        page_number=page_number,
        expected_page_bbox=[0.0, 0.0, width, height],
        dpi=150,
    )
    return {
        "proposal": proposal,
        "page_ref": page["page_ref"],
        "page_number": page_number,
        "raster_manifest": raster["manifest"],
    }


def _page_candidate_refs(payload: dict, page_number: int) -> list[str]:
    projection = payload["pdf_text_layer_projection"]
    page_ref = next(
        item["page_ref"]
        for item in projection["page_inventory"]
        if item["page_number"] == page_number
    )
    candidate = next(
        item
        for item in projection["table_candidate_inventory"]
        if item["page_ref"] == page_ref
    )
    return list(candidate["contributing_word_refs"])


def _same_call_recover(
    payload: dict,
    source_sha256: str,
    requests: tuple[dict, ...],
):
    return LogicalRowTableFactory().create().recover_with_source_bound_scopes(
        full_source_payload=payload,
        source_checksum_sha256=source_sha256,
        private_evidence_ref=PRIVATE_EVIDENCE_REF,
        source_bound_scope_requests=requests,
    )


def _multirow_header_scope_requests(
    *, payload: dict, pdf_bytes: bytes, source_sha256: str
) -> tuple[dict, ...]:
    result = []
    for page_number in (1, 2):
        refs = _page_candidate_refs(payload, page_number)
        assert len(refs) == 8
        result.append(
            _scope_request(
                payload=payload,
                pdf_bytes=pdf_bytes,
                source_sha256=source_sha256,
                page_number=page_number,
                title_refs=[],
                header_ref_groups=[refs[:2], refs[2:4]],
                body_refs=refs[4:],
            )
        )
    return tuple(result)


def test_same_call_exact_multirow_repeated_header_stack_is_continuation() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_multirow_header_case(
        second_leaf_header="Date"
    )

    result = _same_call_recover(
        payload,
        source_sha256,
        _multirow_header_scope_requests(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
        ),
    )

    assert len(result.tables) == 1
    table = result.tables[0]
    assert [row["role"] for row in table["ordered_rows"]] == [
        "COLUMN_HEADER",
        "COLUMN_HEADER",
        "DATA",
        "DATA",
        "CONTINUATION_HEADER",
        "CONTINUATION_HEADER",
        "DATA",
        "DATA",
    ]
    assert [part["continuation_status"] for part in table["source_parts"]] == [
        "START",
        "END",
    ]
    assert result.issues == []
    assert len(result.source_word_ownership) == len(
        payload["pdf_text_layer_projection"]["word_inventory"]
    )
    assert result.unowned_word_refs == []


def test_same_call_multirow_header_difference_stays_independent() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_multirow_header_case(
        second_leaf_header="Currency"
    )

    result = _same_call_recover(
        payload,
        source_sha256,
        _multirow_header_scope_requests(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
        ),
    )

    assert len(result.tables) == 2
    assert [
        [row["role"] for row in table["ordered_rows"]]
        for table in result.tables
    ] == [
        ["COLUMN_HEADER", "COLUMN_HEADER", "DATA", "DATA"],
        ["COLUMN_HEADER", "COLUMN_HEADER", "DATA", "DATA"],
    ]
    assert not any(
        row["role"] == "CONTINUATION_HEADER"
        for table in result.tables
        for row in table["ordered_rows"]
    )
    assert result.issues == []
    assert len(result.source_word_ownership) == len(
        payload["pdf_text_layer_projection"]["word_inventory"]
    )
    assert result.unowned_word_refs == []


def test_same_call_model_only_absent_header_remains_ambiguous() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case()
    first_refs = _page_candidate_refs(payload, 1)
    second_refs = _page_candidate_refs(payload, 2)
    requests = (
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=1,
            title_refs=[],
            header_ref_groups=[first_refs[:2]],
            body_refs=first_refs[2:],
        ),
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=2,
            title_refs=[],
            header_ref_groups=[],
            body_refs=second_refs,
        ),
    )

    result = _same_call_recover(payload, source_sha256, requests)

    assert len(result.tables) == 2
    assert any(table["completeness_status"] == "PARTIAL" for table in result.tables)
    assert any(
        issue["code"] == "logical_table_continuation_header_ambiguous"
        for issue in result.issues
    )
    assert not any(
        part.get("source_bound_header_status") == "ABSENT"
        for table in result.tables
        for part in table["source_parts"]
    )
    assert result.unowned_word_refs == []
    assert "facts" not in result.as_dict()


def test_same_call_exact_title_is_hard_boundary() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case(
        distinct_second_title=True
    )
    projection = payload["pdf_text_layer_projection"]
    first_refs = _page_candidate_refs(payload, 1)
    second_refs = _page_candidate_refs(payload, 2)
    second_page_ref = next(
        item["page_ref"]
        for item in projection["page_inventory"]
        if item["page_number"] == 2
    )
    title_refs = [
        item["word_ref"]
        for item in projection["word_inventory"]
        if item["page_ref"] == second_page_ref
        and item["word_ref"] not in set(second_refs)
    ]
    requests = (
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=1,
            title_refs=[],
            header_ref_groups=[first_refs[:2]],
            body_refs=first_refs[2:],
        ),
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=2,
            title_refs=title_refs,
            header_ref_groups=[second_refs[:2]],
            body_refs=second_refs[2:],
        ),
    )

    result = _same_call_recover(payload, source_sha256, requests)

    assert len(result.tables) == 2
    assert any(
        row["role"] == "TABLE_TITLE"
        and "Completed position transfers" in row["entries"][0]["text"]
        for table in result.tables
        for row in table["ordered_rows"]
    )
    assert result.unowned_word_refs == []


@pytest.mark.parametrize(
    "second_header_labels",
    [
        ("Instrument", "Currency"),
        ("Security", "Market"),
    ],
    ids=["repeated-header", "different-header"],
)
def test_same_call_absent_cannot_erase_visible_header(
    second_header_labels: tuple[str, str],
) -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case(
        second_header_labels=second_header_labels
    )
    first_refs = _page_candidate_refs(payload, 1)
    second_refs = _page_candidate_refs(payload, 2)
    requests = (
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=1,
            title_refs=[],
            header_ref_groups=[first_refs[:2]],
            body_refs=first_refs[2:],
        ),
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=2,
            title_refs=[],
            header_ref_groups=[],
            body_refs=second_refs,
        ),
    )

    result = _same_call_recover(payload, source_sha256, requests)

    assert len(result.tables) == 2
    assert any(table["completeness_status"] == "PARTIAL" for table in result.tables)
    assert any(
        issue["code"] == "logical_table_continuation_header_ambiguous"
        for issue in result.issues
    )
    assert not any(
        part.get("source_bound_header_status") == "ABSENT"
        for table in result.tables
        for part in table["source_parts"]
        if part.get("page") == 2
    )
    assert len(result.source_word_ownership) == len(
        payload["pdf_text_layer_projection"]["word_inventory"]
    )
    assert result.unowned_word_refs == []


def test_same_call_present_requires_leading_header_stack() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case(
        second_header_labels=("Instrument", "Currency")
    )
    first_refs = _page_candidate_refs(payload, 1)
    second_refs = _page_candidate_refs(payload, 2)
    requests = (
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=1,
            title_refs=[],
            header_ref_groups=[first_refs[:2]],
            body_refs=first_refs[2:],
        ),
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=2,
            title_refs=[],
            header_ref_groups=[second_refs[2:4]],
            body_refs=second_refs[4:],
        ),
    )

    result = _same_call_recover(payload, source_sha256, requests)

    assert len(result.tables) == 2
    assert any(table["completeness_status"] == "PARTIAL" for table in result.tables)
    assert any(
        issue["code"] == "source_bound_table_scope_header_presence_conflict"
        for issue in result.issues
    )
    assert not any(
        part.get("source_bound_header_status") == "PRESENT"
        for table in result.tables
        for part in table["source_parts"]
        if part.get("page") == 2
    )
    assert len(result.source_word_ownership) == len(
        payload["pdf_text_layer_projection"]["word_inventory"]
    )
    assert result.unowned_word_refs == []


def test_same_call_partial_scope_blocks_join_and_retains_all_words() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case()
    first_refs = _page_candidate_refs(payload, 1)
    second_refs = _page_candidate_refs(payload, 2)
    requests = (
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=1,
            title_refs=[],
            header_ref_groups=[first_refs[:2]],
            body_refs=first_refs[2:],
        ),
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=2,
            title_refs=[],
            header_ref_groups=[],
            body_refs=second_refs,
            body_status="UNCERTAIN",
        ),
    )

    result = _same_call_recover(payload, source_sha256, requests)

    assert len(result.tables) == 2
    assert any(table["completeness_status"] == "PARTIAL" for table in result.tables)
    assert any(
        issue["code"] == "source_bound_table_scope_uncertain"
        for issue in result.issues
    )
    assert len(result.source_word_ownership) == len(
        payload["pdf_text_layer_projection"]["word_inventory"]
    )
    assert result.unowned_word_refs == []


def test_same_call_overlapping_requests_are_partial_and_do_not_join() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case()
    first_refs = _page_candidate_refs(payload, 1)
    request = _scope_request(
        payload=payload,
        pdf_bytes=pdf_bytes,
        source_sha256=source_sha256,
        page_number=1,
        title_refs=[],
        header_ref_groups=[first_refs[:2]],
        body_refs=first_refs[2:],
    )

    result = _same_call_recover(
        payload,
        source_sha256,
        (request, copy.deepcopy(request)),
    )

    assert len(result.tables) == 2
    assert all(table["completeness_status"] == "PARTIAL" for table in result.tables)
    assert any(
        issue["code"] == "source_bound_table_scope_overlap"
        for issue in result.issues
    )
    assert result.unowned_word_refs == []


def test_public_api_accepts_requests_not_ready_receipts() -> None:
    runtime = LogicalRowTableFactory().create()
    legacy_parameters = inspect.signature(runtime.recover).parameters
    same_call_parameters = inspect.signature(
        runtime.recover_with_source_bound_scopes
    ).parameters

    assert "source_bound_table_scopes" not in legacy_parameters
    assert "source_bound_scope_receipts" not in same_call_parameters
    assert "source_bound_scope_requests" in same_call_parameters
    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="logical_row_source_bound_scope_requests_invalid",
    ):
        runtime.recover_with_source_bound_scopes(
            full_source_payload={},
            source_checksum_sha256=SOURCE_CHECKSUM,
            private_evidence_ref=PRIVATE_EVIDENCE_REF,
            source_bound_scope_requests=({"receipt": object()},),
        )


def test_legacy_recover_contract_and_output_remain_scope_free() -> None:
    builder = ProjectionBuilder(ref_prefix="legacy_scope_free")
    rows = [
        builder.add_row(
            page_number=1,
            y=y,
            entries=[(20, left, 70), (200, right, 60)],
        )
        for y, left, right in (
            (100, "Instrument", "Currency"),
            (116, "LKOH", "RUB"),
            (132, "ROSN", "RUB"),
        )
    ]
    builder.add_candidate(
        page_number=1,
        bbox=[15, 96, 290, 146],
        word_refs=[ref for row in rows for ref in row],
    )

    first = _recover(builder)
    second = _recover(builder)

    assert first.as_dict() == second.as_dict()
    assert "source_bound_scope_receipts_total" not in first.diagnostics
    assert list(inspect.signature(LogicalRowTableRecoveryRuntime.recover).parameters) == [
        "self",
        "pdf_text_layer_projection",
        "source_checksum_sha256",
        "private_evidence_ref",
    ]


def test_three_page_edge_chain_uses_first_fragment_header() -> None:
    first = _continuation_test_region(
        ref_prefix="chain_first",
        page_number=1,
        row_ys=[760.0, 774.0, 790.0],
        header=True,
    )
    middle = _continuation_test_region(
        ref_prefix="chain_middle",
        page_number=2,
        row_ys=[4.0, 24.0, 400.0, 790.0],
        header=False,
    )
    last = _continuation_test_region(
        ref_prefix="chain_last",
        page_number=3,
        row_ys=[4.0, 18.0, 32.0],
        header=False,
    )

    groups = _continuation_groups(first, middle, last)
    table, _ = _materialize_continuation_group(groups[0])

    assert len(groups) == 1
    assert [part["page"] for part in table["source_parts"]] == [1, 2, 3]
    assert [part["continuation_status"] for part in table["source_parts"]] == [
        "START",
        "CONTINUATION",
        "END",
    ]


def test_multiple_predecessors_emit_partial_continuation_terminal() -> None:
    first = _continuation_test_region(
        ref_prefix="ambiguous_first",
        page_number=1,
        row_ys=[760.0, 774.0, 790.0],
        header=True,
    )
    second = _continuation_test_region(
        ref_prefix="ambiguous_second",
        page_number=1,
        row_ys=[760.0, 774.0, 790.0],
        header=True,
    )
    right = _continuation_test_region(
        ref_prefix="ambiguous_right",
        page_number=2,
        row_ys=[4.0, 18.0, 32.0],
        header=False,
    )

    groups = _continuation_groups(first, second, right)
    table, state = _materialize_continuation_group(groups[-1])
    issues = [
        issue
        for issue in state.issues
        if issue["code"] == "logical_table_continuation_ambiguous"
    ]

    assert len(groups) == 3
    assert right.continuation_issue_codes == (
        "logical_table_continuation_ambiguous",
    )
    assert table["completeness_status"] == "PARTIAL"
    assert len(issues) == 1
    assert issues[0]["issue_id"] in table["issues"]


def test_proven_multirow_header_mismatch_does_not_join() -> None:
    def region(
        *,
        ref_prefix: str,
        page_number: int,
        second_header: str,
        row_ys: list[float],
    ) -> recovery_module._Region:
        value = _internal_microtrack_region(
            [
                [[(20.0, 70.0, "Trade")], [(200.0, 250.0, "Settlement")]],
                [[(20.0, 70.0, "Date")], [(200.0, 250.0, second_header)]],
                [[(20.0, 70.0, "1")], [(200.0, 250.0, "2")]],
            ],
            ref_prefix=ref_prefix,
            row_ys=row_ys,
        )
        value.page = replace(value.page, page_number=page_number)
        for header in value.rows[:2]:
            header.role = "COLUMN_HEADER"
        return value

    left = region(
        ref_prefix="multirow_header_left",
        page_number=1,
        second_header="Date",
        row_ys=[760.0, 774.0, 790.0],
    )
    right = region(
        ref_prefix="multirow_header_right",
        page_number=2,
        second_header="Currency",
        row_ys=[4.0, 18.0, 32.0],
    )

    groups = _continuation_groups(left, right)

    assert len(groups) == 2
    assert all(len(group) == 1 for group in groups)


def test_every_table_word_has_one_entry_owner_and_no_paragraph_duplication() -> None:
    builder = ProjectionBuilder(ref_prefix="ownership")
    prose_refs = builder.add_row(
        page_number=1,
        y=20,
        entries=[(15, "Outside table")],
    )
    table_refs = []
    table_refs += builder.add_row(
        page_number=1,
        y=100,
        entries=[(20, "Label"), (200, "Value")],
    )
    table_refs += builder.add_row(
        page_number=1,
        y=114,
        entries=[(20, "A"), (200, "1")],
    )
    table_refs += builder.add_row(
        page_number=1,
        y=128,
        entries=[(20, "B"), (200, "2")],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 95, 240, 140],
        word_refs=table_refs,
    )

    result = _recover(builder)
    owners = result.source_word_ownership
    entry_ids = {
        entry["entry_id"]
        for table in result.tables
        for row in table["ordered_rows"]
        for entry in row["entries"]
    }

    assert len(owners) == len(table_refs)
    assert len({item["source_word_id"] for item in owners}) == len(owners)
    assert {item["owner_entry_id"] for item in owners} == entry_ids
    assert all(item["owner_status"] == "OWNED" for item in owners)
    assert set(result.paragraph_owned_word_refs) == set(prose_refs)
    assert not set(result.paragraph_owned_word_refs).intersection(table_refs)
    assert result.unowned_word_refs == []
    assert result.diagnostics["multiple_word_owners_total"] == 0


def test_optional_columns_use_repeated_left_or_right_edges_not_text_centers() -> None:
    builder = ProjectionBuilder(ref_prefix="edge_columns")
    refs = []
    refs += builder.add_row(
        page_number=1,
        y=100,
        entries=[(20, "Item", 60), (200, "Amount", 40)],
    )
    refs += builder.add_row(
        page_number=1,
        y=114,
        entries=[(20, "A", 12), (232, "1", 8)],
    )
    refs += builder.add_row(
        page_number=1,
        y=128,
        entries=[(20, "A much longer label", 105), (208, "12345", 32)],
    )
    refs += builder.add_row(
        page_number=1,
        y=142,
        entries=[(20, "Medium label", 65), (220, "999", 20)],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 95, 245, 155],
        word_refs=refs,
    )

    result = _recover(builder)
    table = result.tables[0]

    assert len(table["logical_columns"]) == 2
    assert [column["ordinal"] for column in table["logical_columns"]] == [0, 1]
    assert all(column["header_path"] for column in table["logical_columns"])
    assert all(
        entry["column_binding_status"] == "BOUND"
        for row in table["ordered_rows"]
        for entry in row["entries"]
    )


def test_headerless_label_value_rows_infer_two_columns_with_explicit_gap() -> None:
    builder = ProjectionBuilder(ref_prefix="headerless_columns")
    refs = []
    refs += builder.add_row(
        page_number=1,
        y=100,
        entries=[(20, "Cash", 30), (220, "10", 18)],
    )
    refs += builder.add_row(
        page_number=1,
        y=114,
        entries=[(20, "Longer asset label", 95), (206, "2000", 32)],
    )
    refs += builder.add_row(
        page_number=1,
        y=128,
        entries=[(20, "Other", 40), (214, "300", 24)],
    )
    refs += builder.add_row(
        page_number=1,
        y=142,
        entries=[(20, "Grand Total", 70), (198, "2310", 40)],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 95, 245, 155],
        word_refs=refs,
    )

    result = _recover(builder)
    table = result.tables[0]

    assert len(table["logical_columns"]) == 2
    assert all(not column["header_path"] for column in table["logical_columns"])
    assert all(column["issue_ids"] for column in table["logical_columns"])
    assert all(
        entry["column_binding_status"] == "BOUND"
        for row in table["ordered_rows"]
        for entry in row["entries"]
    )
    assert {
        issue["code"] for issue in result.issues
    } >= {"logical_column_header_path_unknown"}


def test_ruled_geometry_merges_wrapped_bands_and_emits_no_empty_entries() -> None:
    builder = ProjectionBuilder(ref_prefix="ruled_rows")
    title_refs = builder.add_row(
        page_number=1,
        y=84,
        entries=[(20, "Schedule title", 90)],
    )
    header = builder.add_row(
        page_number=1,
        y=100,
        entries=[(20, "Item", 45), (200, "Amount", 40)],
    )
    wrapped_top = builder.add_row(
        page_number=1,
        y=114,
        entries=[(20, "Wrapped", 45), (200, "10", 20)],
    )
    wrapped_bottom = builder.add_row(
        page_number=1,
        y=122,
        entries=[(20, "label", 30)],
    )
    wide_groups = builder.add_row(
        page_number=1,
        y=138,
        entries=[(20, "Left", 30), (200, "20", 20)],
    )
    sparse = builder.add_row(
        page_number=1,
        y=152,
        entries=[(20, "Sparse", 40)],
    )
    candidate_refs = [
        *header,
        *wrapped_top,
        *wrapped_bottom,
        *wide_groups,
        *sparse,
    ]
    builder.add_candidate(
        page_number=1,
        bbox=[15, 95, 245, 165],
        word_refs=candidate_refs,
    )
    candidate = builder.candidates[-1]
    candidate["table_strategy_ref"] = "ruled_lines_v0"
    candidate["columns_total"] = 2
    candidate["rows_total"] = 4
    page_ref = str(builder.pages[0]["page_ref"])

    def cell(
        row_ordinal: int,
        column_ordinal: int,
        bbox: list[float],
        word_refs: list[str],
    ) -> dict[str, Any]:
        row_ref = f"ruled_rows_row_{row_ordinal}"
        return {
            "cell_ref": f"ruled_rows_cell_{row_ordinal}_{column_ordinal}",
            "row_ref": row_ref,
            "page_ref": page_ref,
            "row_ordinal": row_ordinal,
            "column_ordinal": column_ordinal,
            "bbox_ref": builder._add_bbox(page_ref=page_ref, bbox=bbox),
            "word_refs": word_refs,
        }

    candidate["row_inventory"] = [
        {
            "row_ref": f"ruled_rows_row_{ordinal}",
            "row_ordinal": ordinal,
            "page_ref": page_ref,
        }
        for ordinal in range(1, 5)
    ]
    candidate["cell_inventory"] = [
        cell(1, 1, [15, 98, 180, 110], [header[0]]),
        cell(1, 2, [180, 98, 245, 110], [header[1]]),
        cell(
            2,
            1,
            [15, 112, 180, 132],
            [wrapped_top[0], wrapped_bottom[0]],
        ),
        cell(2, 2, [180, 112, 245, 132], [wrapped_top[1]]),
        {
            **cell(3, 1, [15, 136, 245, 150], wide_groups),
            "column_span": 2,
        },
        cell(4, 1, [15, 150, 180, 164], sparse),
        cell(4, 2, [180, 150, 245, 164], []),
    ]
    builder.add_vector_line(page_number=1, bbox=[180, 95, 180.2, 165])
    for y in (98, 112, 136, 150, 164):
        builder.add_vector_line(page_number=1, bbox=[15, y, 245, y + 0.2])

    result = _recover(builder)
    table = result.tables[0]

    assert len(table["ordered_rows"]) == 5
    assert table["ordered_rows"][0]["role"] == "TABLE_TITLE"
    assert [
        entry["text"] for entry in table["ordered_rows"][2]["entries"]
    ] == ["Wrapped label", "10"]
    assert [
        entry["text"] for entry in table["ordered_rows"][3]["entries"]
    ] == ["Left", "20"]
    assert [
        entry["text"] for entry in table["ordered_rows"][4]["entries"]
    ] == ["Sparse"]
    assert table["empty_grid_slots"] == [
        {
            "slot_id": table["empty_grid_slots"][0]["slot_id"],
            "source_cell_ref": "ruled_rows_cell_4_2",
            "table_candidate_ref": candidate["table_candidate_ref"],
            "page": 1,
            "page_ref": page_ref,
            "source_row_ordinal": 4,
            "source_column_ordinal": 2,
            "row_span": 1,
            "column_span": 1,
            "bbox_ref": candidate["cell_inventory"][-1]["bbox_ref"],
            "bbox": [180.0, 150.0, 245.0, 164.0],
            "word_refs": [],
            "row_id": table["ordered_rows"][4]["row_id"],
            "logical_column_id": table["logical_columns"][1]["column_id"],
            "table_cell_inventory_checksum_ref": None,
        }
    ]
    assert len(table["logical_columns"]) == 2
    assert len(result.source_word_ownership) == len(
        {*title_refs, *candidate_refs}
    )
    assert result.unowned_word_refs == []
    _validate_v2_component_shapes(result)

    baseline_cells = copy.deepcopy(candidate["cell_inventory"])
    mutations = []

    span_ambiguous = copy.deepcopy(baseline_cells)
    span_ambiguous[-1]["row_span"] = 2
    mutations.append(
        (span_ambiguous, "logical_row_grid_cell_out_of_bounds")
    )

    duplicate_identity = copy.deepcopy(baseline_cells)
    duplicate_identity[-1]["cell_ref"] = duplicate_identity[-2]["cell_ref"]
    mutations.append(
        (duplicate_identity, "logical_row_grid_cell_identity_ambiguous")
    )

    gap = copy.deepcopy([baseline_cells[0], *baseline_cells[2:]])
    mutations.append((gap, "logical_row_grid_cell_inventory_not_closed"))

    out_of_bounds = copy.deepcopy(baseline_cells)
    out_of_bounds[-1]["column_ordinal"] = 3
    mutations.append((out_of_bounds, "logical_row_grid_cell_out_of_bounds"))

    overlap = copy.deepcopy(baseline_cells)
    overlapping_cell = copy.deepcopy(overlap[-1])
    overlapping_cell.update(
        {
            "cell_ref": "ruled_rows_cell_3_2_overlap",
            "row_ref": "ruled_rows_row_3",
            "row_ordinal": 3,
            "column_ordinal": 2,
            "word_refs": [],
        }
    )
    overlap.append(overlapping_cell)
    mutations.append((overlap, "logical_row_grid_cell_span_overlap"))

    word_conflict = copy.deepcopy(baseline_cells)
    word_conflict[-1]["word_refs"] = [sparse[0]]
    mutations.append(
        (
            word_conflict,
            "logical_row_grid_cell_word_ownership_ambiguous",
        )
    )

    for cells, error_code in mutations:
        candidate["cell_inventory"] = cells
        with pytest.raises(
            recovery_module.LogicalRowTableRecoveryError,
            match=error_code,
        ):
            _recover(builder)
    candidate["cell_inventory"] = baseline_cells


def test_ruled_rows_require_dual_axis_grid_topology() -> None:
    builder = ProjectionBuilder(ref_prefix="horizontal_only")
    rows = [
        builder.add_row(
            page_number=1,
            y=y,
            entries=[(20, label, 70), (200, value, 25)],
        )
        for y, label, value in (
            (100, "Item", "Amount"),
            (114, "Alpha", "10"),
            (128, "Beta", "20"),
            (142, "Gamma", "30"),
        )
    ]
    builder.add_candidate(
        page_number=1,
        bbox=[15, 95, 245, 155],
        word_refs=[ref for row in rows for ref in row],
    )
    candidate = builder.candidates[-1]
    candidate["table_strategy_ref"] = "ruled_lines_v0"
    candidate["columns_total"] = 2
    page_ref = str(builder.pages[0]["page_ref"])
    candidate["row_inventory"] = [
        {
            "row_ref": f"horizontal_only_row_{ordinal}",
            "row_ordinal": ordinal,
            "page_ref": page_ref,
        }
        for ordinal in (1, 2)
    ]
    candidate["cell_inventory"] = []
    for row_ordinal, (word_refs, top) in enumerate(zip(rows[:2], (98, 112)), 1):
        for column_ordinal, (left, right, word_ref) in enumerate(
            ((15, 180, word_refs[0]), (180, 245, word_refs[1])),
            1,
        ):
            candidate["cell_inventory"].append(
                {
                    "cell_ref": (
                        f"horizontal_only_cell_{row_ordinal}_{column_ordinal}"
                    ),
                    "row_ref": f"horizontal_only_row_{row_ordinal}",
                    "page_ref": page_ref,
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "bbox_ref": builder._add_bbox(
                        page_ref=page_ref,
                        bbox=[left, top, right, top + 12],
                    ),
                    "word_refs": [word_ref],
                }
            )
    for y in (98, 112, 126, 140, 154):
        builder.add_vector_line(page_number=1, bbox=[15, y, 245, y + 0.2])

    result = _recover(builder)

    assert len(result.tables) == 1
    assert len(result.tables[0]["ordered_rows"]) == 4
    assert [
        row["entries"][0]["text"] for row in result.tables[0]["ordered_rows"]
    ] == ["Item", "Alpha", "Beta", "Gamma"]


@pytest.mark.parametrize(
    ("second_line", "expected_rows", "expected_context"),
    [
        ("title", 4, [("TABLE_TITLE", "Distinct schedule title")]),
        (
            "As of: 2026-01-01",
            5,
            [
                ("TABLE_TITLE", "Distinct schedule"),
                ("NOTE", "As of: 2026-01-01"),
            ],
        ),
    ],
)
def test_long_ruled_table_keeps_distinct_title_above_wide_first_row(
    second_line: str,
    expected_rows: int,
    expected_context: list[tuple[str, str]],
) -> None:
    builder = ProjectionBuilder(ref_prefix="wide_first")
    title_top = builder.add_row(
        page_number=1,
        y=52,
        entries=[(30, "Distinct schedule", 100)],
    )
    title_bottom = builder.add_row(
        page_number=1,
        y=62,
        entries=[(30, second_line, 85)],
    )
    wide_header = builder.add_row(
        page_number=1,
        y=100,
        entries=[(20, "Wide physical header", 110)],
    )
    alpha = builder.add_row(
        page_number=1,
        y=114,
        entries=[(20, "Alpha", 50), (200, "10", 20)],
    )
    beta = builder.add_row(
        page_number=1,
        y=128,
        entries=[(20, "Beta", 50), (200, "20", 20)],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[15, 95, 245, 142],
        word_refs=[*wide_header, *alpha, *beta],
    )
    candidate = builder.candidates[-1]
    candidate["table_strategy_ref"] = "ruled_lines_v0"
    candidate["columns_total"] = 2
    page_ref = str(builder.pages[0]["page_ref"])
    candidate["row_inventory"] = [
        {
            "row_ref": f"wide_first_row_{ordinal}",
            "row_ordinal": ordinal,
            "page_ref": page_ref,
        }
        for ordinal in (1, 2, 3)
    ]
    raw_cells = [
        (1, 1, [15, 98, 245, 110], wide_header),
        (2, 1, [15, 112, 180, 124], [alpha[0]]),
        (2, 2, [180, 112, 245, 124], [alpha[1]]),
        (3, 1, [15, 126, 180, 138], [beta[0]]),
        (3, 2, [180, 126, 245, 138], [beta[1]]),
    ]
    candidate["cell_inventory"] = [
        {
            "cell_ref": f"wide_first_cell_{row}_{column}",
            "row_ref": f"wide_first_row_{row}",
            "page_ref": page_ref,
            "row_ordinal": row,
            "column_ordinal": column,
            "bbox_ref": builder._add_bbox(page_ref=page_ref, bbox=bbox),
            "word_refs": refs,
        }
        for row, column, bbox, refs in raw_cells
    ]
    builder.add_vector_line(page_number=1, bbox=[180, 95, 180.2, 142])
    for y in (98, 112, 126, 140):
        builder.add_vector_line(page_number=1, bbox=[15, y, 245, y + 0.2])

    result = _recover(builder)

    assert len(result.tables) == 1
    assert len(result.tables[0]["ordered_rows"]) == expected_rows
    assert [
        (row["role"], row["entries"][0]["text"])
        for row in result.tables[0]["ordered_rows"][: len(expected_context)]
    ] == expected_context
    assert len(result.source_word_ownership) == len(
        {*title_top, *title_bottom, *wide_header, *alpha, *beta}
    )


def _internal_microtrack_region(
    row_entries: list[list[list[tuple[float, float, str]]]],
    *,
    ref_prefix: str,
    row_ys: list[float] | None = None,
) -> recovery_module._Region:
    page_ref = f"{ref_prefix}_page"
    word_ordinal = 0
    rows = []
    for row_ordinal, entries in enumerate(row_entries):
        y = (
            row_ys[row_ordinal]
            if row_ys is not None
            else 100.0 + row_ordinal * 14.0
        )
        words = []
        entry_bands = []
        for entry_words in entries:
            band_words = []
            for x0, x1, value in entry_words:
                word_ordinal += 1
                word = recovery_module._Word(
                    word_ref=f"{ref_prefix}_word_{word_ordinal}",
                    page_ref=page_ref,
                    text=value,
                    bbox=(x0, y, x1, y + 8.0),
                    order=word_ordinal,
                )
                words.append(word)
                band_words.append(word)
            entry_bands.append(
                recovery_module._EntryBand(
                    words=band_words,
                    bbox=tuple(_merge([list(word.bbox) for word in band_words])),
                    text=" ".join(word.text for word in band_words),
                    anchor_ids=[],
                )
            )
        rows.append(
            recovery_module._RowBand(
                page_ref=page_ref,
                bbox=tuple(_merge([list(word.bbox) for word in words])),
                words=words,
                entries=entry_bands,
            )
        )
    region_words = [word for row in rows for word in row.words]
    return recovery_module._Region(
        source_ref=f"{ref_prefix}_region",
        page=recovery_module._Page(
            page_ref=page_ref,
            page_number=1,
            width=400.0,
            height=800.0,
        ),
        bbox=tuple(_merge([list(row.bbox) for row in rows])),
        words=region_words,
        rows=rows,
        confidence=1.0,
        origin="PARSER_CANDIDATE",
        object_refs=[],
    )


def _split_internal_microtrack(
    region: recovery_module._Region,
) -> list[recovery_module._Region]:
    return recovery_module._split_repeated_microtrack_entries(
        [region],
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )


def _microtrack_positive_rows(
) -> list[list[list[tuple[float, float, str]]]]:
    return [
        [[(20.0, 55.0, "Item")], [(200.0, 221.0, "Rate")]],
        [
            [(20.0, 55.0, "Alpha")],
            [(200.0, 208.0, "$"), (209.0, 221.0, "10")],
        ],
        [
            [(20.0, 55.0, "Beta")],
            [(200.0, 208.0, "$"), (209.0, 221.0, "20")],
        ],
        [[(20.0, 55.0, "Gamma")], [(209.0, 221.0, "30")]],
    ]


def test_repeated_microtrack_split_is_atomic_word_exact_and_snapshot_backed(
) -> None:
    region = _internal_microtrack_region(
        _microtrack_positive_rows(),
        ref_prefix="microtrack_positive",
    )
    original_row_refs = [
        [word.word_ref for word in row.words] for row in region.rows
    ]
    original_entry_counts = [len(row.entries) for row in region.rows]

    split_regions = _split_internal_microtrack(region)
    split = split_regions[0]

    assert len(split_regions) == 1
    assert split is not region
    assert len(split.rows) == len(region.rows)
    assert [len(row.entries) for row in region.rows] == original_entry_counts
    assert [entry.text for entry in split.rows[0].entries] == ["Item", "Rate"]
    assert [entry.text for entry in split.rows[1].entries] == [
        "Alpha",
        "$",
        "10",
    ]
    assert [entry.text for entry in split.rows[2].entries] == [
        "Beta",
        "$",
        "20",
    ]
    assert [entry.text for entry in split.rows[3].entries] == ["Gamma", "30"]
    assert split.origin.endswith("+REPEATED_MICROTRACK")
    assert split.rows[0].column_evidence_entries is None
    assert split.rows[3].column_evidence_entries is None
    for row_index in (1, 2):
        snapshot = split.rows[row_index].column_evidence_entries
        assert isinstance(snapshot, tuple)
        assert [entry.text for entry in snapshot] == [
            split.rows[row_index].entries[0].text,
            f"$ {row_index}0",
        ]
        assert snapshot[1] is not region.rows[row_index].entries[1]
        assert snapshot[1].entry_id is None
        assert snapshot[1].geometry_evidence_id is None
    for row_index, row in enumerate(split.rows):
        entry_refs = [
            word.word_ref for entry in row.entries for word in entry.words
        ]
        assert entry_refs == original_row_refs[row_index]
        assert len(entry_refs) == len(set(entry_refs))
    assert [word.word_ref for word in split.words] == [
        word_ref for refs in original_row_refs for word_ref in refs
    ]
    assert recovery_module._region_has_exact_row_word_partition(split)


def test_generic_column_scope_plan_inherits_exact_snapshot_parent_lane(
) -> None:
    region = _internal_microtrack_region(
        _microtrack_positive_rows(),
        ref_prefix="generic_column_snapshot_lane",
    )
    split = _split_internal_microtrack(region)[0]
    recovery_module._classify_rows(split.rows)

    plan = recovery_module._generic_column_scope_plan(
        rows=split.rows,
        table_id="table_generic_column_snapshot_lane",
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )

    assert plan is not None
    assert len(plan.columns) == 2
    binding_by_entry = {
        id(binding.entry): binding for binding in plan.bindings
    }
    for row_index in (1, 2):
        marker, value = split.rows[row_index].entries[1:]
        marker_binding = binding_by_entry[id(marker)]
        value_binding = binding_by_entry[id(value)]
        assert marker_binding.logical_column_ordinal == 1
        assert value_binding.logical_column_ordinal == 1
        assert marker_binding.covered_column_ordinals == ()
        assert value_binding.covered_column_ordinals == ()
    assert all(
        entry.logical_column_id is None
        and entry.covers_logical_column_ids == []
        and entry.column_binding_status == "NOT_APPLICABLE"
        for row in split.rows
        for entry in row.entries
    )


def test_generic_column_scope_plan_two_row_quorum_is_snapshot_exact_and_atomic(
) -> None:
    source_rows = _microtrack_positive_rows()[1:3]
    split = _split_internal_microtrack(
        _internal_microtrack_region(
            source_rows,
            ref_prefix="generic_column_two_row_quorum",
        )
    )[0]
    recovery_module._classify_rows(split.rows)

    accepted = recovery_module._generic_column_scope_plan(
        rows=split.rows,
        table_id="table_generic_column_two_row_quorum",
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )

    assert accepted is not None
    assert len(accepted.columns) == 2

    broken = copy.deepcopy(split)
    snapshot = list(broken.rows[0].column_evidence_entries or ())
    assert len(snapshot) == 2 and len(snapshot[1].words) == 2
    snapshot[1].words = snapshot[1].words[:-1]
    snapshot[1].bbox = snapshot[1].words[0].bbox
    snapshot[1].text = snapshot[1].words[0].text
    broken.rows[0].column_evidence_entries = tuple(snapshot)

    rejected = recovery_module._generic_column_scope_plan(
        rows=broken.rows,
        table_id="table_generic_column_two_row_quorum_broken",
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )

    assert rejected is None
    assert all(
        entry.logical_column_id is None
        and entry.covers_logical_column_ids == []
        and entry.column_binding_status == "NOT_APPLICABLE"
        for row in broken.rows
        for entry in row.entries
    )


@pytest.mark.parametrize("drift_kind", ["bbox", "text"])
def test_column_scope_plan_rejects_source_drift_before_mutation(
    drift_kind: str,
) -> None:
    split = _split_internal_microtrack(
        _internal_microtrack_region(
            _microtrack_positive_rows(),
            ref_prefix=f"column_scope_plan_{drift_kind}_drift",
        )
    )[0]
    recovery_module._classify_rows(split.rows)
    table_id = f"table_column_scope_plan_{drift_kind}_drift"
    config = recovery_module.LogicalRowTableRecoveryConfig()
    plan = recovery_module._generic_column_scope_plan(
        rows=split.rows,
        table_id=table_id,
        config=config,
    )
    assert plan is not None
    target = split.rows[-1].entries[-1]
    if drift_kind == "bbox":
        target.bbox = (
            target.bbox[0] + 1.0,
            target.bbox[1],
            target.bbox[2] + 1.0,
            target.bbox[3],
        )
    else:
        target.text = f"{target.text} drift"
    before_bindings = [
        (
            entry.logical_column_id,
            list(entry.covers_logical_column_ids),
            entry.column_binding_status,
        )
        for row in split.rows
        for entry in row.entries
    ]
    state = recovery_module._RecoveryState(
        source_checksum_sha256=SOURCE_CHECKSUM,
        private_evidence_ref=PRIVATE_EVIDENCE_REF,
        bbox_by_ref={},
    )

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="column_materialization_scope_plan_invalid",
    ):
        recovery_module._apply_column_scope_plan(
            plan=plan,
            rows=split.rows,
            row_payloads=[],
            table_id=table_id,
            state=state,
            config=config,
        )
    assert [
        (
            entry.logical_column_id,
            list(entry.covers_logical_column_ids),
            entry.column_binding_status,
        )
        for row in split.rows
        for entry in row.entries
    ] == before_bindings
    assert state.anchors == []
    assert state.geometry_evidence == []
    assert state.source_word_ownership == []
    assert state.issues == []


def test_column_scope_plan_rejects_late_payload_drift_atomically() -> None:
    split = _split_internal_microtrack(
        _internal_microtrack_region(
            _microtrack_positive_rows(),
            ref_prefix="column_scope_plan_late_payload_drift",
        )
    )[0]
    recovery_module._classify_rows(split.rows)
    row_payloads = []
    for row_index, row in enumerate(split.rows):
        payload_entries = []
        for entry_index, entry in enumerate(row.entries):
            entry.entry_id = f"entry_payload_{row_index}_{entry_index}"
            entry.anchor_ids = [f"anchor_payload_{row_index}_{entry_index}"]
            payload_entries.append(
                {
                    "entry_id": entry.entry_id,
                    "column_binding_status": "NOT_APPLICABLE",
                    "logical_column_id": None,
                    "covers_logical_column_ids": [],
                }
            )
        row_payloads.append({"entries": payload_entries})
    table_id = "table_column_scope_plan_late_payload_drift"
    config = recovery_module.LogicalRowTableRecoveryConfig()
    plan = recovery_module._generic_column_scope_plan(
        rows=split.rows,
        table_id=table_id,
        config=config,
    )
    assert plan is not None
    row_payloads[-1]["entries"][-1]["entry_id"] = "tampered_late_entry"
    before_payloads = copy.deepcopy(row_payloads)
    before_bindings = [
        (
            entry.logical_column_id,
            list(entry.covers_logical_column_ids),
            entry.column_binding_status,
        )
        for row in split.rows
        for entry in row.entries
    ]
    state = recovery_module._RecoveryState(
        source_checksum_sha256=SOURCE_CHECKSUM,
        private_evidence_ref=PRIVATE_EVIDENCE_REF,
        bbox_by_ref={},
    )

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="column_materialization_scope_plan_invalid",
    ):
        recovery_module._apply_column_scope_plan(
            plan=plan,
            rows=split.rows,
            row_payloads=row_payloads,
            table_id=table_id,
            state=state,
            config=config,
        )
    assert row_payloads == before_payloads
    assert [
        (
            entry.logical_column_id,
            list(entry.covers_logical_column_ids),
            entry.column_binding_status,
        )
        for row in split.rows
        for entry in row.entries
    ] == before_bindings
    assert state.anchors == []
    assert state.geometry_evidence == []
    assert state.source_word_ownership == []
    assert state.issues == []


def test_accounting_label_value_scope_keeps_optional_unit_in_value_lane(
) -> None:
    region = _internal_microtrack_region(
        [
            [
                [(20.0, 70.0, "Alpha")],
                [(200.0, 208.0, "$")],
                [(250.0, 270.0, "10")],
            ],
            [[(30.0, 80.0, "Beta")], [(250.0, 270.0, "20")]],
            [
                [(40.0, 90.0, "Gamma")],
                [(200.0, 208.0, "$")],
                [(250.0, 270.0, "30")],
            ],
            [[(20.0, 80.0, "Grand Total")], [(250.0, 270.0, "60")]],
        ],
        ref_prefix="accounting_label_value_scope",
    )
    recovery_module._classify_rows(region.rows)
    lineage = recovery_module._column_evidence_lineage(region.rows)
    assert lineage is not None

    plan = recovery_module._accounting_label_value_scope_plan(
        rows=region.rows,
        lineage=lineage,
        table_id="table_accounting_label_value_scope",
        width=recovery_module._bbox_width(region.bbox),
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )

    assert plan is not None
    assert len(plan.columns) == 2
    binding_by_entry = {
        id(binding.entry): binding for binding in plan.bindings
    }
    for row in region.rows:
        assert binding_by_entry[id(row.entries[0])].logical_column_ordinal == 0
        assert all(
            binding_by_entry[id(entry)].logical_column_ordinal == 1
            for entry in row.entries[1:]
        )

    drifted = copy.deepcopy(region)
    drifted_bbox = drifted.rows[-1].entries[-1].bbox
    drifted.rows[-1].entries[-1].bbox = (
        310.0,
        drifted_bbox[1],
        330.0,
        drifted_bbox[3],
    )
    drifted_lineage = recovery_module._column_evidence_lineage(drifted.rows)
    assert drifted_lineage is not None
    assert (
        recovery_module._accounting_label_value_scope_plan(
            rows=drifted.rows,
            lineage=drifted_lineage,
            table_id="table_accounting_label_value_scope_drifted",
            width=recovery_module._bbox_width(drifted.bbox),
            config=recovery_module.LogicalRowTableRecoveryConfig(),
        )
        is None
    )


def test_repeated_microtrack_emits_only_child_entries_and_keeps_columns(
) -> None:
    builder = ProjectionBuilder(ref_prefix="microtrack_contract")
    header_refs = builder.add_row(
        page_number=1,
        y=100,
        entries=[(20, "Item", 35), (190, "Rate", 31)],
    )
    alpha_refs = builder.add_row(
        page_number=1,
        y=114,
        entries=[(20, "Alpha", 35), (190, "$", 4), (203, "10", 18)],
    )
    beta_refs = builder.add_row(
        page_number=1,
        y=128,
        entries=[(20, "Beta", 35), (190, "$", 4), (203, "20", 18)],
    )
    gamma_refs = builder.add_row(
        page_number=1,
        y=142,
        entries=[(20, "Gamma", 35), (203, "30", 18)],
    )
    all_refs = [*header_refs, *alpha_refs, *beta_refs, *gamma_refs]
    builder.add_candidate(
        page_number=1,
        bbox=[15, 95, 230, 155],
        word_refs=all_refs,
    )

    result = _recover(builder)
    table = result.tables[0]
    rows = table["ordered_rows"]
    entry_ids = {
        entry["entry_id"] for row in rows for entry in row["entries"]
    }
    owner_by_source_word = {
        owner["source_word_id"]: owner["owner_entry_id"]
        for owner in result.source_word_ownership
    }

    assert len(result.tables) == 1
    assert len(rows) == 4
    assert sum(len(row["entries"]) for row in rows) == 10
    assert _table_text(table) == [
        ["Item", "Rate"],
        ["Alpha", "$", "10"],
        ["Beta", "$", "20"],
        ["Gamma", "30"],
    ]
    assert len(table["logical_columns"]) == 2
    value_column_id = table["logical_columns"][1]["column_id"]
    for row in rows[1:3]:
        marker, value = row["entries"][1:]
        assert marker["kind"] == "MARKER"
        assert marker["column_binding_status"] == "BOUND"
        assert marker["logical_column_id"] == value_column_id
        assert value["column_binding_status"] == "BOUND"
        assert value["logical_column_id"] == value_column_id
    assert len(result.source_word_ownership) == len(all_refs)
    assert set(owner_by_source_word.values()) == entry_ids
    for refs in (alpha_refs[1:], beta_refs[1:]):
        owner_ids = {
            owner_by_source_word[
                recovery_module._identifier("source_word", [word_ref])
            ]
            for word_ref in refs
        }
        assert len(owner_ids) == 2
        assert owner_ids.issubset(entry_ids)
    assert sum(
        evidence["kind"] == "ENTRY_REGION"
        for evidence in result.geometry_evidence
    ) == len(entry_ids)
    assert result.paragraph_owned_word_refs == []
    assert result.unowned_word_refs == []
    _validate_v2_component_shapes(result)


@pytest.mark.parametrize(
    "case",
    (
        "one_row",
        "same_row_only",
        "edge_drift",
        "multiple_cut",
        "no_carrier",
        "two_carriers",
        "atomic_number",
        "overlap",
        "ambiguous_cluster",
        "non_atomic_row",
    ),
)
def test_repeated_microtrack_rejects_incomplete_or_ambiguous_proof(
    case: str,
) -> None:
    label = [[(20.0, 55.0, "Label")]]
    pair = [[(200.0, 208.0, "$"), (209.0, 221.0, "10")]]
    rows = [label + pair, label + pair]
    if case == "one_row":
        rows = rows[:1]
    elif case == "same_row_only":
        rows = [
            label
            + pair
            + [[(250.0, 270.0, "USD"), (271.0, 283.0, "20")]]
        ]
    elif case == "edge_drift":
        rows[1] = label + [
            [(214.1, 222.1, "$"), (223.1, 235.1, "20")]
        ]
    elif case == "multiple_cut":
        compound = [
            [
                (200.0, 215.0, "USD"),
                (216.0, 228.0, "10"),
                (229.0, 237.0, "%"),
            ]
        ]
        rows = [label + compound, label + compound]
    elif case == "no_carrier":
        compound = [[(200.0, 215.0, "USD"), (216.0, 236.0, "rate")]]
        numeric = [[(300.0, 312.0, "10")]]
        rows = [label + compound + numeric, label + compound + numeric]
    elif case == "two_carriers":
        compound = [[(200.0, 212.0, "10"), (213.0, 225.0, "20")]]
        rows = [label + compound, label + compound]
    elif case == "atomic_number":
        compound = [[(200.0, 208.0, "1"), (209.0, 225.0, ",234")]]
        rows = [label + compound, label + compound]
    elif case == "overlap":
        compound = [[(200.0, 210.0, "$"), (208.0, 220.0, "10")]]
        rows = [label + compound, label + compound]
    elif case == "ambiguous_cluster":
        rows = [
            label
            + [[(x, x + 8.0, "$"), (x + 9.0, x + 21.0, "10")]]
            for x in (200.0, 211.0, 222.0)
        ]
    region = _internal_microtrack_region(
        rows,
        ref_prefix=f"microtrack_reject_{case}",
    )
    if case == "non_atomic_row":
        region.rows[1].bbox = (
            region.rows[1].bbox[0],
            region.rows[1].bbox[1] - 8.0,
            region.rows[1].bbox[2],
            region.rows[1].bbox[3] + 8.0,
        )
    before = [
        [entry.text for entry in row.entries] for row in region.rows
    ]

    result = _split_internal_microtrack(region)

    assert result == [region]
    assert result[0] is region
    assert [
        [entry.text for entry in row.entries] for row in result[0].rows
    ] == before
    assert all(row.column_evidence_entries is None for row in region.rows)


def test_repeated_microtrack_rejects_source_word_reuse_atomically() -> None:
    region = _internal_microtrack_region(
        [
            [
                [(20.0, 55.0, "Alpha")],
                [(200.0, 208.0, "$"), (209.0, 221.0, "10")],
            ],
            [
                [(20.0, 55.0, "Beta")],
                [(200.0, 208.0, "$"), (209.0, 221.0, "20")],
            ],
        ],
        ref_prefix="microtrack_reuse",
    )
    first_pair = region.rows[0].entries[1].words
    second_pair = region.rows[1].entries[1].words
    replacements = [
        recovery_module._Word(
            word_ref=source.word_ref,
            page_ref=target.page_ref,
            text=target.text,
            bbox=target.bbox,
            order=target.order,
        )
        for source, target in zip(first_pair, second_pair)
    ]
    region.rows[1].entries[1].words = replacements
    region.rows[1].words[1:] = replacements
    region.words = [word for row in region.rows for word in row.words]

    result = _split_internal_microtrack(region)

    assert result == [region]
    assert result[0] is region
    assert all(row.column_evidence_entries is None for row in region.rows)


def _coalesce_internal_region(
    region: recovery_module._Region,
    *,
    objects: list[recovery_module._ObjectGeometry] | None = None,
) -> list[recovery_module._Region]:
    return recovery_module._coalesce_logical_row_fragments(
        [region],
        object_bboxes=list(objects or []),
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )


def _wrapped_label_region() -> recovery_module._Region:
    return _internal_microtrack_region(
        [
            [
                [
                    (20.0, 50.0, "Account"),
                    (51.0, 100.0, "classification"),
                ]
            ],
            [
                [(20.0, 55.0, "continued"), (56.0, 82.0, "label")],
                [(220.0, 245.0, "Rate")],
                [(300.0, 312.0, "10")],
            ],
            [
                [(20.0, 80.0, "Second item")],
                [(220.0, 245.0, "Type")],
                [(300.0, 312.0, "20")],
            ],
            [[(20.0, 70.0, "Third item")], [(300.0, 312.0, "30")]],
        ],
        ref_prefix="row_group_wrapped",
        row_ys=[100.0, 108.0, 122.0, 136.0],
    )


def _leaf_header_region(
    *,
    body_count: int = 3,
    label_xs: list[float] | None = None,
    label_values: bool = False,
    leaf_case: str = "positive",
) -> recovery_module._Region:
    headers = [
        [[(345.0, 355.0, "Top")]],
        [[(145.0, 155.0, "Left")], [(245.0, 255.0, "Middle")]],
        [
            [(145.0, 155.0, "H1")],
            [(245.0, 255.0, "H2")],
            [(345.0, 355.0, "H3")],
        ],
    ]
    header_ys = [100.0, 108.0, 116.0]
    if leaf_case == "equidistant":
        headers[0] = [[(195.0, 205.0, "Middle point")]]
    elif leaf_case == "nonmonotonic":
        headers[0] = [
            [(345.0, 355.0, "Right first"), (145.0, 155.0, "Left second")]
        ]
    elif leaf_case == "nonmax":
        headers = [
            [[(345.0, 355.0, "Band one")]],
            [[(145.0, 155.0, "Band two")]],
            [[(245.0, 255.0, "Band three")]],
            [[(345.0, 355.0, "Band four")]],
            [
                [(145.0, 155.0, "H1")],
                [(245.0, 255.0, "H2")],
                [(345.0, 355.0, "H3")],
            ],
        ]
        header_ys = [100.0, 108.0, 116.0, 124.0, 132.0]
    labels = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"]
    widths = [30.0, 60.0, 90.0, 30.0, 60.0, 90.0]
    starts = label_xs or [20.0] * body_count
    bodies = []
    for index in range(body_count):
        shift = 40.0 if leaf_case == "unstable" else 0.0
        label = str(index + 1) if label_values else labels[index]
        bodies.append(
            [
                [(starts[index], starts[index] + widths[index], label)],
                [(145.0 + shift, 155.0 + shift, str(index * 3 + 1))],
                [(245.0 + shift, 255.0 + shift, str(index * 3 + 2))],
                [(345.0 + shift, 355.0 + shift, str(index * 3 + 3))],
            ]
        )
    first_body_y = header_ys[-1] + 14.0
    body_ys = [first_body_y + index * 14.0 for index in range(body_count)]
    return _internal_microtrack_region(
        [*headers, *bodies],
        ref_prefix=(
            f"row_group_leaf_{leaf_case}_{body_count}_"
            f"{int(label_values)}_{len(set(starts))}"
        ),
        row_ys=[*header_ys, *body_ys],
    )


def _label_stack_region(
    *,
    case: str = "positive",
    rows_total: int = 3,
) -> recovery_module._Region:
    upper = [(20.0, 45.0, "Group"), (46.0, 90.0, "overview")]
    lower_x0 = 24.0 if case == "indent_width" else 20.0
    lower_x2 = 120.0 if case in {"indent_width", "increasing_width"} else 70.0
    lower_text = {
        "capitalization": "Continued",
        "value": "10",
    }.get(case, "continued")
    if case == "terminal":
        upper[-1] = (46.0, 90.0, "overview.")
    if case == "prose":
        upper = [
            (20.0 + index * 25.0, 42.0 + index * 25.0, word)
            for index, word in enumerate(
                ("Long", "prose", "fragment", "with", "too", "many")
            )
        ]
    stack = [[upper], [[(lower_x0, lower_x2, lower_text)]]]
    if rows_total == 3:
        stack.append([[(20.0, 48.0, "final")]])
    row_ys = [100.0, 110.0 if case == "gap" else 108.0]
    if rows_total == 3:
        row_ys.append(row_ys[-1] + 8.0)
    body_y = row_ys[-1] + 14.0
    return _internal_microtrack_region(
        [
            *stack,
            [[(20.0, 90.0, "Body item")], [(300.0, 312.0, "10")]],
        ],
        ref_prefix=f"row_group_stack_{case}_{rows_total}",
        row_ys=[*row_ys, body_y],
    )


def _narrow_header_region() -> recovery_module._Region:
    return _internal_microtrack_region(
        [
            [[(300.0, 320.0, "Right"), (321.0, 350.0, "header")]],
            [[(305.0, 345.0, "detail")]],
            [
                [(20.0, 90.0, "Alpha")],
                [(300.0, 320.0, "Rate")],
                [(330.0, 350.0, "10")],
            ],
            [
                [(20.0, 90.0, "Beta")],
                [(300.0, 320.0, "Type")],
                [(330.0, 350.0, "20")],
            ],
        ],
        ref_prefix="row_group_narrow",
        row_ys=[100.0, 108.0, 122.0, 136.0],
    )


@pytest.mark.parametrize(
    ("kind", "factory", "expected_rows", "expected_entries"),
    [
        ("WRAPPED_LABEL", _wrapped_label_region, 3, 8),
        ("LEAF_HEADER", _leaf_header_region, 4, 15),
        ("GROUP_LABEL_STACK", _label_stack_region, 2, 3),
        ("NARROW_HEADER", _narrow_header_region, 3, 7),
    ],
)
def test_row_coalescence_positive_detectors_commit_exactly(
    kind: str,
    factory: Any,
    expected_rows: int,
    expected_entries: int,
) -> None:
    region = factory()
    source_refs = [word.word_ref for word in region.words]

    result = _coalesce_internal_region(region)
    rebuilt = result[0]
    grouped = [row for row in rebuilt.rows if row.row_coalescence_kind]

    assert result[0] is not region
    assert len(rebuilt.rows) == expected_rows
    assert sum(len(row.entries) for row in rebuilt.rows) == expected_entries
    assert [row.row_coalescence_kind for row in grouped] == [kind]
    assert grouped[0].column_evidence_rows is not None
    assert all(entry.entry_id is None for row in rebuilt.rows for entry in row.entries)
    assert [word.word_ref for word in rebuilt.words] == source_refs
    assert recovery_module._region_has_exact_row_word_partition(rebuilt)
    assert all(
        recovery_module._row_has_exact_entry_word_partition(row)
        for row in rebuilt.rows
    )


@pytest.mark.parametrize(
    "case",
    (
        "capitalization",
        "terminal",
        "indent_width",
        "gap",
        "separator",
        "value",
        "prose",
        "unstable_leaf",
        "equidistant",
        "nonmonotonic",
        "nonmax",
        "overlap",
        "order",
    ),
)
def test_row_coalescence_rejects_predicate_near_misses_atomically(
    case: str,
) -> None:
    objects = []
    if case in {
        "capitalization",
        "terminal",
        "indent_width",
        "gap",
        "separator",
        "value",
        "prose",
        "order",
    }:
        region = _label_stack_region(case=case, rows_total=2)
    else:
        leaf_case = case.removesuffix("_leaf")
        region = _leaf_header_region(leaf_case=leaf_case)
    if case == "separator":
        objects = [
            recovery_module._ObjectGeometry(
                object_ref="row_group_separator",
                page_ref=region.page.page_ref,
                bbox=(region.bbox[0], 108.0, region.bbox[2], 108.2),
                object_kind="vector_line_inventory",
            )
        ]
    if case == "overlap":
        duplicate = copy.deepcopy(region)
        duplicate.source_ref = "row_group_overlap_duplicate"
        result = recovery_module._coalesce_logical_row_fragments(
            [region, duplicate],
            object_bboxes=[],
            config=recovery_module.LogicalRowTableRecoveryConfig(),
        )
        assert all(
            row.row_coalescence_kind is None
            for item in result
            for row in item.rows
        )
        return
    if case == "order":
        target = region.rows[1].words[0]
        replacement = recovery_module._Word(
            word_ref=target.word_ref,
            page_ref=target.page_ref,
            text=target.text,
            bbox=target.bbox,
            order=1,
        )
        region.rows[1].words[0] = replacement
        region.rows[1].entries[0].words[0] = replacement
        region.words = [word for row in region.rows for word in row.words]
    before = [len(row.entries) for row in region.rows]

    result = _coalesce_internal_region(region, objects=objects)

    assert result[0] is region
    assert [len(row.entries) for row in result[0].rows] == before
    assert all(row.row_coalescence_kind is None for row in result[0].rows)


def _materialize_internal_region(
    region: recovery_module._Region,
) -> tuple[dict[str, Any], recovery_module._RecoveryState]:
    state = recovery_module._RecoveryState(
        source_checksum_sha256=SOURCE_CHECKSUM,
        private_evidence_ref=PRIVATE_EVIDENCE_REF,
        bbox_by_ref={},
    )
    table = recovery_module._materialize_logical_table(
        [region],
        state=state,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )
    return table, state


def test_leaf_header_complement_is_body_only_and_has_no_phantom_ids() -> None:
    grouped = _coalesce_internal_region(_leaf_header_region())[0]
    table, state = _materialize_internal_region(grouped)
    columns = table["logical_columns"]
    complement = next(column for column in columns if not column["header_path"])
    body_first_entries = [
        row["entries"][0]
        for row in table["ordered_rows"]
        if row["role"] in {"DATA", "SUBTOTAL", "TOTAL"}
    ]
    issue_by_id = {issue["issue_id"]: issue for issue in state.issues}
    emitted_entry_ids = {
        entry["entry_id"]
        for row in table["ordered_rows"]
        for entry in row["entries"]
    }

    assert len(columns) == 4
    assert {issue_by_id[item]["code"] for item in complement["issue_ids"]} == {
        "logical_column_header_path_unknown"
    }
    assert set(complement["source_anchor_ids"]) == {
        anchor
        for entry in body_first_entries
        for anchor in entry["source_anchor_ids"]
    }
    assert {item["owner_entry_id"] for item in state.source_word_ownership}.issubset(
        emitted_entry_ids
    )
    leaf = next(
        row for row in grouped.rows if row.row_coalescence_kind == "LEAF_HEADER"
    )
    assert leaf.column_evidence_rows is not None
    assert all(
        entry.entry_id is None and entry.geometry_evidence_id is None
        for row in leaf.column_evidence_rows
        for entry in row.entries
    )


@pytest.mark.parametrize(
    "case",
    ("no_lineage", "too_few", "multiple_external", "value_left"),
)
def test_leaf_header_complement_rejects_incomplete_lineage(case: str) -> None:
    if case == "multiple_external":
        source = _leaf_header_region(
            body_count=6,
            label_xs=[20.0, 20.0, 20.0, 70.0, 70.0, 70.0],
        )
    else:
        source = _leaf_header_region(label_values=case == "value_left")
    grouped = _coalesce_internal_region(source)[0]
    leaf = next(
        row for row in grouped.rows if row.row_coalescence_kind == "LEAF_HEADER"
    )
    if case == "no_lineage":
        leaf.row_coalescence_kind = None
    elif case == "too_few":
        grouped.rows = grouped.rows[:3]
        grouped.words = [word for row in grouped.rows for word in row.words]
        grouped.bbox = tuple(_merge([list(row.bbox) for row in grouped.rows]))

    table, _ = _materialize_internal_region(grouped)

    assert all(column["header_path"] for column in table["logical_columns"])


def test_unique_exterior_label_lane_augments_headed_columns_atomically() -> None:
    header = [
        [(150.0, 180.0, "Header A")],
        [(250.0, 280.0, "Header B")],
        [(350.0, 380.0, "Header C")],
    ]

    def body_row(index: int, label_x: float):
        value = index * 3
        return [
            [(label_x, label_x + 50.0, f"Label {index}")],
            [(150.0, 170.0, str(value + 1))],
            [(250.0, 270.0, str(value + 2))],
            [(350.0, 370.0, str(value + 3))],
        ]

    unique = _internal_microtrack_region(
        [
            header,
            *[
                body_row(index, label_x)
                for index, label_x in enumerate((20.0, 30.0, 40.0, 30.0))
            ],
        ],
        ref_prefix="unique_exterior_label_lane",
    )
    table, state = _materialize_internal_region(unique)

    assert len(table["logical_columns"]) == 4
    exterior = table["logical_columns"][0]
    assert exterior["header_path"] == []
    assert exterior["issue_ids"]
    exterior_id = exterior["column_id"]
    assert all(
        row["entries"][0]["logical_column_id"] == exterior_id
        for row in table["ordered_rows"][1:]
    )
    assert len(state.source_word_ownership) == len(unique.words)

    ambiguous = _internal_microtrack_region(
        [
            header,
            *[
                body_row(index, 20.0 if index % 2 == 0 else 100.0)
                for index in range(4)
            ],
        ],
        ref_prefix="ambiguous_exterior_label_lane",
    )
    rejected, _ = _materialize_internal_region(ambiguous)

    assert len(rejected["logical_columns"]) == 3
    assert all(column["header_path"] for column in rejected["logical_columns"])
    assert all(
        row["entries"][0]["column_binding_status"] == "NOT_APPLICABLE"
        for row in rejected["ordered_rows"][1:]
    )


def test_factory_is_generic_and_not_bound_to_ids_pages_or_old_owners() -> None:
    def build(*, page_number: int, prefix: str):
        builder = ProjectionBuilder(
            page_numbers=(page_number,),
            ref_prefix=prefix,
        )
        refs = []
        refs += builder.add_row(
            page_number=page_number,
            y=100,
            entries=[(20, "Name"), (200, "Value")],
        )
        refs += builder.add_row(
            page_number=page_number,
            y=114,
            entries=[(20, "Alpha"), (200, "1")],
        )
        refs += builder.add_row(
            page_number=page_number,
            y=128,
            entries=[(20, "Beta"), (200, "2")],
        )
        builder.add_candidate(
            page_number=page_number,
            bbox=[15, 95, 245, 140],
            word_refs=refs,
        )
        return _recover(builder)

    first = build(page_number=1, prefix="arbitrary_alpha")
    second = build(page_number=17, prefix="unrelated_beta")

    assert _table_text(first.tables[0]) == _table_text(second.tables[0])
    assert [row["role"] for row in first.tables[0]["ordered_rows"]] == [
        row["role"] for row in second.tables[0]["ordered_rows"]
    ]
    assert first.tables[0]["table_id"] != second.tables[0]["table_id"]
    assert logical_table_block_id(first.tables[0]["table_id"]).startswith(
        "block_logical_table_"
    )
    source = inspect.getsource(recovery_module)
    assert "PdfLayoutUnitBuilder" not in source
    assert "BrokerPdfNeutralTableFactory" not in source
    assert "real_pdf_" not in source
    assert "pershing" not in source.casefold()
    assert "fidelity" not in source.casefold()
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
    assert "LogicalRowTableFactory.create" in FACTORY_REQUIRED
    assert "filename" in FORBIDDEN
    assert first.diagnostics["provider_calls"] == 0
    assert first.diagnostics["visual_gold_reads"] == 0
    assert first.diagnostics["pdf_layout_units_consumed"] == 0
    assert first.diagnostics["grid_owner_calls"] == 0


def _merge(bboxes: list[list[float]]) -> list[float]:
    return [
        min(item[0] for item in bboxes),
        min(item[1] for item in bboxes),
        max(item[2] for item in bboxes),
        max(item[3] for item in bboxes),
    ]


def _scope_subregion(
    source: recovery_module._Region,
    *,
    start: int,
    end: int,
    suffix: str,
) -> recovery_module._Region:
    rows = copy.deepcopy(source.rows[start:end])
    words = [word for row in rows for word in row.words]
    return recovery_module._Region(
        source_ref=f"{source.source_ref}_{suffix}",
        page=source.page,
        bbox=tuple(_merge([list(row.bbox) for row in rows])),
        words=words,
        rows=rows,
        confidence=source.confidence,
        origin=source.origin,
        object_refs=[],
    )


def _scope_reconcile(
    regions: list[recovery_module._Region],
    *,
    extra_words: list[recovery_module._Word] | None = None,
    objects: list[recovery_module._ObjectGeometry] | None = None,
) -> list[recovery_module._Region]:
    page_ref = regions[0].page.page_ref
    page_words = [word for region in regions for word in region.words]
    page_words.extend(extra_words or [])
    return recovery_module._reconcile_same_page_table_scopes(
        regions,
        words_by_page={page_ref: page_words},
        object_bboxes=list(objects or []),
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )


def _lexical_scope_region(
    *,
    ref_prefix: str,
    shared_header: bool = False,
    competing_split: bool = False,
) -> recovery_module._Region:
    first_row = (
        [[(20.0, 80.0, "Item")], [(250.0, 280.0, "Amount")]]
        if shared_header
        else [[(20.0, 180.0, "Primary reporting scope:")]]
    )
    rows = [
        first_row,
        [[(20.0, 80.0, "Alpha")], [(250.0, 280.0, "10")]],
        [[(20.0, 80.0, "Beta")], [(250.0, 280.0, "20")]],
        [[(20.0, 80.0, "Total")], [(250.0, 280.0, "30")]],
        [[(20.0, 230.0, "Independent financial scope title:")]],
        [[(20.0, 80.0, "Gamma")], [(250.0, 280.0, "40")]],
        [[(20.0, 80.0, "Total")], [(250.0, 280.0, "40")]],
    ]
    row_ys = [100.0, 114.0, 128.0, 142.0, 167.0, 181.0, 195.0]
    if competing_split:
        rows.extend(
            [
                [[(20.0, 230.0, "Third independent scope title:")]],
                [[(20.0, 80.0, "Delta")], [(250.0, 280.0, "50")]],
                [[(20.0, 80.0, "Total")], [(250.0, 280.0, "50")]],
            ]
        )
        row_ys.extend([220.0, 234.0, 248.0])
    return _internal_microtrack_region(
        rows,
        ref_prefix=ref_prefix,
        row_ys=row_ys,
    )


def _geometry_scope_pair(
    *,
    ref_prefix: str,
    missing_header_scope: bool = False,
    right_title_terminal: bool = False,
    right_track_shift: float = 0.0,
    right_y: float = 171.0,
) -> tuple[recovery_module._Region, recovery_module._Region]:
    reset_text = (
        "Independent regional reporting section:"
        if right_title_terminal
        else "Regional operations group"
    )
    combined = _internal_microtrack_region(
        [
            [[(200.0, 220.0, "Debit"), (240.0, 280.0, "Credit")]],
            [
                [(20.0, 80.0, "Alpha")],
                [(205.0, 220.0, "USD")],
                [(250.0, 280.0, "10")],
            ],
            [
                [(20.0, 80.0, "Beta")],
                [(205.0, 220.0, "USD")],
                [(250.0, 280.0, "20")],
            ],
            [
                [(20.0, 80.0, "Total")],
                [(205.0, 220.0, "USD")],
                [(250.0, 280.0, "30")],
            ],
            [[(20.0, 170.0, reset_text)]],
            [
                [(20.0, 80.0, "Gamma")],
                [(205.0 + right_track_shift, 220.0 + right_track_shift, "USD")],
                [(250.0, 280.0, "40")],
            ],
            [
                [(20.0, 80.0, "Total")],
                [(205.0 + right_track_shift, 220.0 + right_track_shift, "USD")],
                [(250.0, 280.0, "40")],
            ],
        ],
        ref_prefix=ref_prefix,
        row_ys=[100.0, 114.0, 128.0, 142.0, right_y, right_y + 14, right_y + 28],
    )
    left = _scope_subregion(
        combined,
        start=0,
        end=4,
        suffix="left",
    )
    right = _scope_subregion(
        combined,
        start=4,
        end=7,
        suffix="right",
    )
    header = left.rows[0]
    physical_rows = []
    for word in header.words:
        physical_rows.append(
            recovery_module._RowBand(
                page_ref=header.page_ref,
                bbox=word.bbox,
                words=[word],
                entries=[
                    recovery_module._EntryBand(
                        words=[word],
                        bbox=word.bbox,
                        text=word.text,
                        anchor_ids=[],
                    )
                ],
            )
        )
    header.column_evidence_rows = tuple(physical_rows)
    header.row_coalescence_kind = (
        None if missing_header_scope else "NARROW_HEADER"
    )
    return left, right


def _boundary_separator(
    left: recovery_module._Region,
    *,
    width_ratio: float,
    ordinal: int,
    y_offset: float = 0.0,
) -> recovery_module._ObjectGeometry:
    width = recovery_module._bbox_width(left.bbox) * width_ratio
    return recovery_module._ObjectGeometry(
        object_ref=f"scope_separator_{ordinal}",
        page_ref=left.page.page_ref,
        bbox=(
            left.bbox[2] - width,
            left.bbox[3] + y_offset,
            left.bbox[2],
            left.bbox[3] + y_offset + 0.2,
        ),
        object_kind="vector_line_inventory",
    )


def test_same_page_scope_split_closes_only_independent_lexical_scope() -> None:
    source = _lexical_scope_region(ref_prefix="scope_split_close")

    first = _scope_reconcile([source])
    second = _scope_reconcile([copy.deepcopy(source)])

    assert [(len(region.rows), len(region.words)) for region in first] == [
        (4, 7),
        (3, 5),
    ]
    assert [region.source_ref for region in first] == [
        region.source_ref for region in second
    ]
    assert all(region.origin.endswith("+SCOPE_SPLIT") for region in first)
    assert {
        word.word_ref for region in first for word in region.words
    } == {word.word_ref for word in source.words}
    assert all(
        recovery_module._region_has_exact_row_word_partition(region)
        for region in first
    )


def test_same_page_scope_split_continues_under_compatible_header() -> None:
    source = _lexical_scope_region(
        ref_prefix="scope_split_shared_header",
        shared_header=True,
    )

    result = _scope_reconcile([source])

    assert result == [source]
    assert result[0] is source


def test_same_page_scope_merge_is_one_deterministic_single_source_part() -> None:
    left, right = _geometry_scope_pair(ref_prefix="scope_merge_positive")

    first = _scope_reconcile([left, right])
    second = _scope_reconcile([copy.deepcopy(left), copy.deepcopy(right)])

    assert len(first) == 1
    assert len(first[0].rows) == 7
    assert sum(len(row.entries) for row in first[0].rows) == 17
    assert first[0].source_ref == second[0].source_ref
    assert first[0].origin.endswith("+SCOPE_MERGE")
    first_table, first_state = _materialize_internal_region(first[0])
    second_table, _ = _materialize_internal_region(second[0])
    assert first_table == second_table
    assert [part["continuation_status"] for part in first_table["source_parts"]] == [
        "SINGLE"
    ]
    assert first_table["source_parts"][0]["continuation_evidence_ids"] == []
    assert len(first_state.source_word_ownership) == len(first[0].words)
    assert {
        item["owner_entry_id"] for item in first_state.source_word_ownership
    }.issubset(
        {
            entry["entry_id"]
            for row in first_table["ordered_rows"]
            for entry in row["entries"]
        }
    )
    header = first[0].rows[0]
    assert header.column_evidence_rows is not None
    assert all(
        entry.entry_id is None and entry.geometry_evidence_id is None
        for row in header.column_evidence_rows
        for entry in row.entries
    )


@pytest.mark.parametrize(
    ("width_ratio", "expected_regions"),
    ((0.24, 1), (0.35, 2), (0.45, 2)),
)
def test_same_page_scope_merge_classifies_clustered_separator_widths(
    width_ratio: float,
    expected_regions: int,
) -> None:
    left, right = _geometry_scope_pair(
        ref_prefix=f"scope_separator_{width_ratio}",
    )
    objects = [
        _boundary_separator(left, width_ratio=width_ratio, ordinal=1),
        _boundary_separator(
            left,
            width_ratio=width_ratio,
            ordinal=2,
            y_offset=0.6,
        ),
    ]

    result = _scope_reconcile([left, right], objects=objects)

    assert len(result) == expected_regions


@pytest.mark.parametrize(
    "case",
    (
        "missing_header_scope",
        "shifted_tracks",
        "independent_right_header",
        "intervening_word",
        "excessive_gap",
    ),
)
def test_same_page_scope_merge_rejects_boundary_near_misses(case: str) -> None:
    left, right = _geometry_scope_pair(
        ref_prefix=f"scope_merge_reject_{case}",
        missing_header_scope=case == "missing_header_scope",
        right_title_terminal=case == "independent_right_header",
        right_track_shift=25.0 if case == "shifted_tracks" else 0.0,
        right_y=181.0 if case == "excessive_gap" else 171.0,
    )
    extra_words = []
    if case == "intervening_word":
        left_max = max(word.order for word in left.words)
        right_min = min(word.order for word in right.words)
        extra_words.append(
            recovery_module._Word(
                word_ref="scope_merge_unowned_between",
                page_ref=left.page.page_ref,
                text="Intervening",
                bbox=(100.0, left.bbox[3] + 2.0, 150.0, left.bbox[3] + 10.0),
                order=(left_max + right_min) / 2,
            )
        )

    result = _scope_reconcile(
        [left, right],
        extra_words=extra_words,
    )

    assert result == [left, right]
    assert result[0] is left
    assert result[1] is right


def test_same_page_scope_planner_rejects_competing_split_component() -> None:
    source = _lexical_scope_region(
        ref_prefix="scope_competing_split",
        competing_split=True,
    )
    assert recovery_module._same_page_scope_split_indexes(
        source,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    ) == [4, 7]

    result = _scope_reconcile([source])

    assert result == [source]
    assert result[0] is source


def test_same_page_scope_planner_rejects_competing_neighbor() -> None:
    rows = [
        [[(200.0, 220.0, "Debit"), (240.0, 280.0, "Credit")]],
        [
            [(20.0, 80.0, "Alpha")],
            [(205.0, 220.0, "USD")],
            [(250.0, 280.0, "10")],
        ],
        [
            [(20.0, 80.0, "Beta")],
            [(205.0, 220.0, "USD")],
            [(250.0, 280.0, "20")],
        ],
        [
            [(20.0, 80.0, "Total")],
            [(205.0, 220.0, "USD")],
            [(250.0, 280.0, "30")],
        ],
        [[(20.0, 230.0, "Independent financial scope title:")]],
        [
            [(20.0, 80.0, "Gamma")],
            [(205.0, 220.0, "USD")],
            [(250.0, 280.0, "40")],
        ],
        [
            [(20.0, 80.0, "Total")],
            [(205.0, 220.0, "USD")],
            [(250.0, 280.0, "40")],
        ],
        [[(20.0, 170.0, "Regional operations group")]],
        [
            [(20.0, 80.0, "Delta")],
            [(205.0, 220.0, "USD")],
            [(250.0, 280.0, "50")],
        ],
        [
            [(20.0, 80.0, "Total")],
            [(205.0, 220.0, "USD")],
            [(250.0, 280.0, "50")],
        ],
    ]
    combined = _internal_microtrack_region(
        rows,
        ref_prefix="scope_competing_neighbor",
        row_ys=[
            100.0,
            114.0,
            128.0,
            142.0,
            167.0,
            181.0,
            195.0,
            219.0,
            233.0,
            247.0,
        ],
    )
    left = _scope_subregion(
        combined,
        start=0,
        end=7,
        suffix="left",
    )
    right = _scope_subregion(
        combined,
        start=7,
        end=10,
        suffix="right",
    )
    header = left.rows[0]
    header.column_evidence_rows = tuple(
        recovery_module._RowBand(
            page_ref=header.page_ref,
            bbox=word.bbox,
            words=[word],
            entries=[
                recovery_module._EntryBand(
                    words=[word],
                    bbox=word.bbox,
                    text=word.text,
                    anchor_ids=[],
                )
            ],
        )
        for word in header.words
    )
    header.row_coalescence_kind = "NARROW_HEADER"
    config = recovery_module.LogicalRowTableRecoveryConfig()
    assert recovery_module._same_page_scope_split_indexes(
        left,
        config=config,
    ) == [4]
    assert recovery_module._same_page_scope_merge_candidate(
        left,
        right,
        page_words=[*left.words, *right.words],
        owned_refs={word.word_ref for word in [*left.words, *right.words]},
        object_bboxes=[],
        config=config,
    )

    result = _scope_reconcile([left, right])

    assert result == [left, right]
    assert result[0] is left
    assert result[1] is right


def _split_boundary_separator(
    source: recovery_module._Region,
    *,
    width_ratio: float,
    ordinal: int,
    y_offset: float = 0.0,
) -> recovery_module._ObjectGeometry:
    width = recovery_module._bbox_width(source.bbox) * width_ratio
    boundary_y = source.rows[3].bbox[3] + y_offset
    return recovery_module._ObjectGeometry(
        object_ref=f"scope_split_separator_{ordinal}",
        page_ref=source.page.page_ref,
        bbox=(
            source.bbox[2] - width,
            boundary_y,
            source.bbox[2],
            boundary_y + 0.2,
        ),
        object_kind="vector_line_inventory",
    )


@pytest.mark.parametrize(
    ("width_ratio", "expected_regions"),
    ((0.24, 2), (0.35, 1), (0.45, 2)),
)
def test_same_page_scope_split_applies_separator_class_law(
    width_ratio: float,
    expected_regions: int,
) -> None:
    source = _lexical_scope_region(
        ref_prefix=f"scope_split_separator_{width_ratio}",
    )
    separator = _split_boundary_separator(
        source,
        width_ratio=width_ratio,
        ordinal=1,
    )

    result = _scope_reconcile([source], objects=[separator])

    assert len(result) == expected_regions
    if expected_regions == 1:
        assert result[0] is source


def test_scope_separator_lines_over_point_one_height_stay_distinct() -> None:
    left, right = _geometry_scope_pair(
        ref_prefix="scope_separator_distinct_y",
    )
    typical_height = 8.0
    objects = [
        _boundary_separator(left, width_ratio=0.20, ordinal=1),
        _boundary_separator(
            left,
            width_ratio=0.39,
            ordinal=2,
            y_offset=typical_height * 0.15,
        ),
    ]

    classification = recovery_module._classify_scope_boundary_separator(
        page_ref=left.page.page_ref,
        upper_bbox=left.bbox,
        lower_bbox=right.bbox,
        envelope_bbox=tuple(_merge([list(left.bbox), list(right.bbox)])),
        typical_height=typical_height,
        object_bboxes=objects,
    )

    assert classification == recovery_module._SCOPE_SEPARATOR_AMBIGUOUS


def test_scope_separator_full_line_is_not_swallowed_by_local_duplicate() -> None:
    left, right = _geometry_scope_pair(
        ref_prefix="scope_separator_full_local",
    )
    objects = [
        _boundary_separator(left, width_ratio=0.20, ordinal=1),
        _boundary_separator(left, width_ratio=0.45, ordinal=2),
    ]

    classification = recovery_module._classify_scope_boundary_separator(
        page_ref=left.page.page_ref,
        upper_bbox=left.bbox,
        lower_bbox=right.bbox,
        envelope_bbox=tuple(_merge([list(left.bbox), list(right.bbox)])),
        typical_height=8.0,
        object_bboxes=objects,
    )

    assert classification == recovery_module._SCOPE_SEPARATOR_FULL


def _g1_direct_row(
    entry_word_groups: list[list[recovery_module._Word]],
    *,
    ordinals: list[list[int] | None] | None = None,
    external_title: bool = False,
) -> recovery_module._RowBand:
    words = sorted(
        [word for group in entry_word_groups for word in group],
        key=lambda word: word.order,
    )
    entries = []
    for index, group in enumerate(entry_word_groups):
        entries.append(
            recovery_module._EntryBand(
                words=list(group),
                bbox=tuple(_merge([list(word.bbox) for word in group])),
                text=" ".join(word.text for word in group),
                anchor_ids=[],
                geometry_column_ordinals=(
                    None if ordinals is None else ordinals[index]
                ),
            )
        )
    return recovery_module._RowBand(
        page_ref=words[0].page_ref,
        bbox=tuple(_merge([list(word.bbox) for word in words])),
        words=words,
        entries=entries,
        external_title=external_title,
    )


def _g1_replace_word(
    region: recovery_module._Region,
    word_ref: str,
    *,
    text: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    order: int | None = None,
) -> None:
    source = next(word for word in region.words if word.word_ref == word_ref)
    replacement = recovery_module._Word(
        word_ref=source.word_ref,
        page_ref=source.page_ref,
        text=source.text if text is None else text,
        bbox=source.bbox if bbox is None else bbox,
        order=source.order if order is None else order,
    )
    region.words = [
        replacement if word.word_ref == word_ref else word
        for word in region.words
    ]
    for row in region.rows:
        row.words = [
            replacement if word.word_ref == word_ref else word
            for word in row.words
        ]
        for entry in row.entries:
            entry.words = [
                replacement if word.word_ref == word_ref else word
                for word in entry.words
            ]
            entry.bbox = tuple(
                _merge([list(word.bbox) for word in entry.words])
            )
            entry.text = " ".join(word.text for word in entry.words)
        row.bbox = tuple(_merge([list(word.bbox) for word in row.words]))
    region.bbox = tuple(_merge([list(row.bbox) for row in region.rows]))


def _g1_ruled_baseline_fixture(
    *,
    ref_prefix: str = "g1_direct",
) -> tuple[
    recovery_module._Region,
    list[recovery_module._ObjectGeometry],
]:
    baseline = _internal_microtrack_region(
        [
            [[(100.0, 140.0, "Units")]],
            [[(15.0, 245.0, "________________")]],
            [
                [(20.0, 60.0, "Alpha")],
                [(200.0, 208.0, "$"), (209.0, 221.0, "10")],
            ],
            [
                [(20.0, 60.0, "Beta")],
                [(200.0, 208.0, "$"), (209.0, 221.0, "20")],
            ],
            [[(20.0, 60.0, "Gamma")], [(209.0, 221.0, "30")]],
            [[(20.0, 60.0, "Total")], [(209.0, 221.0, "60")]],
            [[(20.0, 100.0, "Member's")]],
            [
                [(20.0, 100.0, "equity")],
                [(209.0, 221.0, "40")],
            ],
        ],
        ref_prefix=ref_prefix,
        row_ys=[100.0, 110.0, 124.0, 138.0, 152.0, 166.0, 180.0, 188.0],
    )
    pseudorule = baseline.rows[1].words[0]
    _g1_replace_word(
        baseline,
        pseudorule.word_ref,
        bbox=(
            pseudorule.bbox[0],
            pseudorule.bbox[1],
            pseudorule.bbox[2],
            pseudorule.bbox[1] + 4.0,
        ),
    )
    source_rows = baseline.rows
    coarse_rows = [
        _g1_direct_row(
            [source_rows[0].entries[0].words],
            external_title=True,
        ),
        _g1_direct_row([source_rows[1].entries[0].words]),
        _g1_direct_row(
            [
                [
                    *source_rows[2].entries[0].words,
                    *source_rows[3].entries[0].words,
                ],
                [
                    *source_rows[2].entries[1].words,
                    *source_rows[3].entries[1].words,
                ],
            ],
            ordinals=[[0], [1]],
        ),
        _g1_direct_row(
            [entry.words for entry in source_rows[4].entries],
            ordinals=[[0], [1]],
        ),
        _g1_direct_row(
            [entry.words for entry in source_rows[5].entries],
            ordinals=[[0], [1]],
        ),
        _g1_direct_row(
            [source_rows[6].entries[0].words],
            ordinals=[[0]],
        ),
        _g1_direct_row(
            [entry.words for entry in source_rows[7].entries],
            ordinals=[[0], [1]],
        ),
    ]
    region = recovery_module._Region(
        source_ref=f"{ref_prefix}_region",
        page=baseline.page,
        bbox=tuple(_merge([list(row.bbox) for row in coarse_rows])),
        words=sorted(baseline.words, key=lambda word: word.order),
        rows=coarse_rows,
        confidence=1.0,
        origin="PARSER_CANDIDATE",
        object_refs=[],
        ruled_column_bands=[(15.0, 180.0), (180.0, 245.0)],
    )
    objects = [
        recovery_module._ObjectGeometry(
            object_ref=f"{ref_prefix}_vertical",
            page_ref=region.page.page_ref,
            bbox=(180.0, 124.0, 180.2, 196.0),
            object_kind="vector_line_inventory",
        ),
        *[
            recovery_module._ObjectGeometry(
                object_ref=f"{ref_prefix}_horizontal_{index}",
                page_ref=region.page.page_ref,
                bbox=(20.0, y, 221.0, y + 0.2),
                object_kind="vector_line_inventory",
            )
            for index, y in enumerate((130.0, 158.0), start=1)
        ],
    ]
    return region, objects


def _g1_plan(
    region: recovery_module._Region,
    objects: list[recovery_module._ObjectGeometry],
) -> recovery_module._RuledBaselineRecoveryPlan | None:
    return recovery_module._ruled_baseline_recovery_plan_for_region(
        region,
        object_bboxes=objects,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )


def _g1_marked_region(
) -> tuple[recovery_module._Region, list[recovery_module._ObjectGeometry]]:
    region, objects = _g1_ruled_baseline_fixture()
    planned = recovery_module._plan_unique_ruled_baseline_recovery(
        [region],
        object_bboxes=objects,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )[0]
    assert recovery_module._region_has_valid_ruled_baseline_plan(planned)
    return planned, objects


def _g1_external_row(
    region: recovery_module._Region,
    *,
    suffix: str,
    y: float,
    order: int,
) -> recovery_module._RowBand:
    word = recovery_module._Word(
        word_ref=f"g1_external_{suffix}",
        page_ref=region.page.page_ref,
        text=suffix,
        bbox=(20.0, y, 90.0, y + 8.0),
        order=order,
    )
    return _g1_direct_row([[word]])


def _g1_bracketed_marked_region(
) -> tuple[recovery_module._Region, list[recovery_module._ObjectGeometry]]:
    planned, objects = _g1_marked_region()
    trailing_order = max(word.order for word in planned.words) + 1
    rebuilt = recovery_module._rebuild_with_boundary_bracket(
        planned,
        leading_rows=[
            _g1_external_row(
                planned,
                suffix="leading",
                y=86.0,
                order=0,
            )
        ],
        trailing_row=_g1_external_row(
            planned,
            suffix="trailing",
            y=204.0,
            order=trailing_order,
        ),
        object_bboxes=objects,
    )
    assert rebuilt is not None
    return rebuilt, objects


def test_g1_ruled_baseline_planner_builds_exact_deterministic_plan() -> None:
    region, objects = _g1_ruled_baseline_fixture()

    plan = _g1_plan(region, objects)
    permuted = copy.deepcopy(region)
    permuted.words.reverse()
    permuted_plan = _g1_plan(permuted, list(reversed(objects)))

    assert plan is not None
    assert permuted_plan == plan
    assert len(plan.output_rows) == 6
    assert sum(len(row.entry_word_ref_groups) for row in plan.output_rows) == 11
    assert plan.released_non_table_word_refs == (
        plan.title_pseudorule_ref_groups[1]
    )
    assert not set(plan.released_non_table_word_refs).intersection(
        word_ref
        for row in plan.output_rows
        for word_ref in row.word_refs
    )
    assert [
        row.row_coalescence_kind
        for row in plan.output_rows
        if row.row_coalescence_kind
    ] == ["TITLE_PSEUDO_RULE", "RULED_WRAPPED_LABEL"]


@pytest.mark.parametrize(
    "case",
    ("clean", "mirrored", "ambiguous", "order", "track"),
)
def test_g1_ruled_baseline_planner_rejects_incomplete_or_ambiguous_proof(
    case: str,
) -> None:
    region, objects = _g1_ruled_baseline_fixture(ref_prefix=f"g1_reject_{case}")
    if case == "clean":
        region.rows = recovery_module._row_bands(
            region.words,
            config=recovery_module.LogicalRowTableRecoveryConfig(),
        )
        for row in region.rows[2:]:
            for entry in row.entries:
                entry.geometry_column_ordinals = recovery_module._word_group_columns(
                    entry.words,
                    column_bands=list(region.ruled_column_bands or []),
                )
    elif case == "mirrored":
        region.mirrored_lane_seed = True
    elif case == "ambiguous":
        duplicate = copy.deepcopy(region)
        duplicate.source_ref += "_duplicate"
        planned = recovery_module._plan_unique_ruled_baseline_recovery(
            [region, duplicate],
            object_bboxes=objects,
            config=recovery_module.LogicalRowTableRecoveryConfig(),
        )
        assert all(item.ruled_baseline_recovery_plan is None for item in planned)
        return
    elif case == "order":
        region.rows[2].words.reverse()
    else:
        target = region.rows[4].entries[-1].words[-1]
        _g1_replace_word(
            region,
            target.word_ref,
            bbox=(233.0, target.bbox[1], 245.0, target.bbox[3]),
        )

    assert _g1_plan(region, objects) is None


@pytest.mark.parametrize(
    "case",
    (
        "pseudorule_alnum",
        "wrapped_uppercase_duplicate",
        "wrapped_numeric_continuation",
        "wrapped_indent",
    ),
)
def test_g1_ruled_baseline_macro_near_misses_fail_closed(case: str) -> None:
    region, objects = _g1_ruled_baseline_fixture(ref_prefix=f"g1_macro_{case}")
    if case == "pseudorule_alnum":
        target = region.rows[1].words[0]
        _g1_replace_word(region, target.word_ref, text="rule")
    elif case == "wrapped_uppercase_duplicate":
        target = region.rows[-1].entries[0].words[0]
        _g1_replace_word(region, target.word_ref, text="Member's")
    elif case == "wrapped_numeric_continuation":
        target = region.rows[-1].entries[0].words[0]
        _g1_replace_word(region, target.word_ref, text="100")
    else:
        target = region.rows[-1].entries[0].words[0]
        _g1_replace_word(
            region,
            target.word_ref,
            bbox=(30.0, target.bbox[1], 110.0, target.bbox[3]),
        )

    assert _g1_plan(region, objects) is None


def test_g1_ruled_baseline_marker_forwards_through_bracket_and_header() -> None:
    bracketed, objects = _g1_bracketed_marked_region()
    bracket_plan = bracketed.ruled_baseline_recovery_plan

    assert bracket_plan is not None
    assert bracket_plan.boundary_bracket_proven is True
    assert bracket_plan.attached_leading_row_ref_groups == (
        ("g1_external_leading",),
    )
    assert bracket_plan.attached_trailing_row_ref_groups == (
        ("g1_external_trailing",),
    )

    rebuilt = recovery_module._rebuild_with_leading_header_stack(
        bracketed,
        leading_rows=[
            _g1_external_row(
                bracketed,
                suffix="header",
                y=72.0,
                order=-1,
            )
        ],
        object_bboxes=objects,
    )

    assert rebuilt is not None
    assert recovery_module._region_has_valid_ruled_baseline_plan(rebuilt)
    forwarded = rebuilt.ruled_baseline_recovery_plan
    assert forwarded is not None and forwarded.boundary_bracket_proven is True
    assert forwarded.attached_leading_row_ref_groups == (
        ("g1_external_header",),
        ("g1_external_leading",),
    )


def test_g1_ruled_baseline_apply_is_exact_idempotent_and_partitioned() -> None:
    bracketed, _ = _g1_bracketed_marked_region()
    source_refs = [word.word_ref for word in bracketed.words]

    applied = recovery_module._apply_planned_ruled_baseline_recovery(
        [bracketed]
    )[0]
    second = recovery_module._apply_planned_ruled_baseline_recovery([applied])[0]
    title = next(
        row for row in applied.rows if row.row_coalescence_kind == "TITLE_PSEUDO_RULE"
    )
    wrapped = next(
        row
        for row in applied.rows
        if row.row_coalescence_kind == "RULED_WRAPPED_LABEL"
    )

    assert second is applied
    assert applied.ruled_baseline_recovery_plan is None
    assert len(applied.rows) == 8
    assert sum(len(row.entries) for row in applied.rows[1:-1]) == 11
    assert applied.released_non_table_word_refs
    assert [word.word_ref for word in applied.words] == [
        word_ref
        for word_ref in source_refs
        if word_ref not in set(applied.released_non_table_word_refs)
    ]
    assert recovery_module._region_has_exact_row_word_partition(applied)
    assert recovery_module._rows_have_strict_source_order(applied.rows)
    assert all(
        recovery_module._row_has_exact_entry_word_partition(row)
        for row in applied.rows
    )
    assert [entry.geometry_column_ordinals for entry in title.entries] == [
        None,
    ]
    assert [entry.geometry_column_ordinals for entry in wrapped.entries] == [
        [0],
        [1],
    ]
    assert title.external_title is True
    assert title.column_evidence_rows is not None
    assert wrapped.column_evidence_rows is not None
    assert all(
        entry.entry_id is None and entry.geometry_evidence_id is None
        for row in (*title.column_evidence_rows, *wrapped.column_evidence_rows)
        for entry in row.entries
    )

    table, state = _materialize_internal_region(copy.deepcopy(applied))
    assert len(table["logical_columns"]) == 2
    assert len(state.source_word_ownership) == len(source_refs) - len(
        applied.released_non_table_word_refs
    )


def test_g1_ruled_baseline_production_order_recovers_microtracks_once() -> None:
    bracketed, objects = _g1_bracketed_marked_region()
    planned = recovery_module._apply_planned_ruled_baseline_recovery(
        [bracketed]
    )[0]
    split = recovery_module._split_repeated_microtrack_entries(
        [copy.deepcopy(planned)],
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )[0]
    coalesced = recovery_module._coalesce_logical_row_fragments(
        [split],
        object_bboxes=objects,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )[0]

    assert sum(len(row.entries) for row in planned.rows[1:-1]) == 11
    assert sum(len(row.entries) for row in split.rows[1:-1]) == 13
    assert sum(len(row.entries) for row in coalesced.rows[1:-1]) == 13
    assert coalesced.released_non_table_word_refs == (
        planned.released_non_table_word_refs
    )


def test_g1_ruled_baseline_apply_clears_invalid_plan_without_partial_rebuild(
) -> None:
    bracketed, _ = _g1_bracketed_marked_region()
    before = [[entry.text for entry in row.entries] for row in bracketed.rows]
    plan = bracketed.ruled_baseline_recovery_plan
    assert plan is not None
    bracketed.ruled_baseline_recovery_plan = recovery_module.replace(
        plan,
        core_word_refs=plan.core_word_refs[:-1],
    )

    result = recovery_module._apply_planned_ruled_baseline_recovery(
        [bracketed]
    )[0]

    assert result.ruled_baseline_recovery_plan is None
    assert [[entry.text for entry in row.entries] for row in result.rows] == before


def _ruled_binding_truth_table_region() -> recovery_module._Region:
    region = _internal_microtrack_region(
        [
            [
                [(20.0, 220.0, "Description group")],
                [(260.0, 300.0, "Amount")],
            ],
            [[(20.0, 220.0, "Assets")]],
            [
                [(40.0, 100.0, "Cash")],
                [(150.0, 170.0, "10")],
                [(260.0, 280.0, "20")],
            ],
            [
                [(40.0, 100.0, "Bonds")],
                [(150.0, 170.0, "30")],
                [(260.0, 280.0, "40")],
            ],
            [
                [(20.0, 220.0, "Subtotal assets")],
                [(260.0, 280.0, "100")],
            ],
            [
                [(20.0, 220.0, "Total assets")],
                [(260.0, 280.0, "100")],
            ],
        ],
        ref_prefix="ruled_binding_truth",
    )
    ordinal_rows = [
        [[0, 1], [2]],
        [[0, 1]],
        [[0], [1], [2]],
        [[0], [1], [2]],
        [[0, 1], [2]],
        [[0, 1], [2]],
    ]
    for row, entry_ordinals in zip(region.rows, ordinal_rows):
        for entry, ordinals in zip(row.entries, entry_ordinals):
            entry.geometry_column_ordinals = ordinals
    region.ruled_column_bands = [
        (10.0, 120.0),
        (120.0, 240.0),
        (240.0, 350.0),
    ]
    return region


def test_ruled_bindings_cover_headers_groups_and_terminal_rows_atomically(
) -> None:
    region = _ruled_binding_truth_table_region()

    table, state = _materialize_internal_region(region)
    column_ids = [column["column_id"] for column in table["logical_columns"]]
    payload_by_text = {
        entry["text"]: entry
        for row in table["ordered_rows"]
        for entry in row["entries"]
    }
    header = payload_by_text["Description group"]
    group = payload_by_text["Assets"]
    subtotal = payload_by_text["Subtotal assets"]
    total = payload_by_text["Total assets"]

    assert [row["role"] for row in table["ordered_rows"]] == [
        "COLUMN_HEADER",
        "GROUP_HEADER",
        "DATA",
        "DATA",
        "SUBTOTAL",
        "TOTAL",
    ]
    assert len(column_ids) == 3
    for cover_only in (header, group):
        assert cover_only["column_binding_status"] == "BOUND"
        assert cover_only["logical_column_id"] is None
        assert cover_only["covers_logical_column_ids"] == column_ids[:2]
    for direct_cover in (subtotal, total):
        assert direct_cover["column_binding_status"] == "BOUND"
        assert direct_cover["logical_column_id"] == column_ids[0]
        assert direct_cover["covers_logical_column_ids"] == column_ids[:2]
        assert direct_cover["logical_column_id"] == (
            direct_cover["covers_logical_column_ids"][0]
        )
    assert all(
        entry["column_binding_status"] == "BOUND"
        for row in table["ordered_rows"]
        for entry in row["entries"]
        if entry["covers_logical_column_ids"]
    )
    assert all(
        not entry["covers_logical_column_ids"]
        or entry["column_binding_status"] != "NOT_APPLICABLE"
        for row in table["ordered_rows"]
        for entry in row["entries"]
    )

    header_id = header["entry_id"]
    group_id = group["entry_id"]
    assert [column["header_path"] for column in table["logical_columns"][:2]] == [
        [header_id],
        [header_id],
    ]
    assert all(
        group_id not in column["header_path"]
        for column in table["logical_columns"]
    )

    evidence_by_id = {
        evidence["geometry_evidence_id"]: evidence
        for evidence in state.geometry_evidence
    }
    for entry in (header, group, subtotal, total):
        assert len(entry["geometry_evidence_ids"]) == 1
        evidence = evidence_by_id[entry["geometry_evidence_ids"][0]]
        assert evidence["kind"] == "ENTRY_REGION"
        assert evidence["source_anchor_ids"] == entry["source_anchor_ids"]
        assert entry["covers_logical_column_ids"] == sorted(
            entry["covers_logical_column_ids"],
            key=column_ids.index,
        )

    for internal_row, payload_row in zip(region.rows, table["ordered_rows"]):
        for internal, payload in zip(internal_row.entries, payload_row["entries"]):
            assert internal.column_binding_status == payload["column_binding_status"]
            assert internal.logical_column_id == payload["logical_column_id"]
            assert internal.covers_logical_column_ids == payload[
                "covers_logical_column_ids"
            ]
    emitted_entry_ids = {
        entry["entry_id"]
        for row in table["ordered_rows"]
        for entry in row["entries"]
    }
    assert len(state.source_word_ownership) == len(region.words)
    assert {
        ownership["owner_entry_id"] for ownership in state.source_word_ownership
    } == emitted_entry_ids

    _validate_v2_component_shapes(
        recovery_module.LogicalRowTableRecoveryResult(
            schema_version="broker_reports_logical_row_table_recovery_v1",
            recovery_policy_version="logical_row_geometry_recovery_policy_v1",
            tables=[table],
            anchors=state.anchors,
            geometry_evidence=state.geometry_evidence,
            source_word_ownership=state.source_word_ownership,
            issues=state.issues,
            paragraph_owned_word_refs=[],
            unowned_word_refs=[],
            diagnostics={},
        )
    )


def test_entry_binding_reset_clears_internal_and_payload_state_together() -> None:
    region = _ruled_binding_truth_table_region()
    table, _ = _materialize_internal_region(region)
    internal = region.rows[-1].entries[0]
    payload = table["ordered_rows"][-1]["entries"][0]

    assert internal.covers_logical_column_ids
    recovery_module._set_entry_column_binding(
        internal,
        payload=payload,
        logical_column_id=None,
        covers_logical_column_ids=(),
    )

    assert internal.logical_column_id is None
    assert internal.covers_logical_column_ids == []
    assert internal.column_binding_status == "NOT_APPLICABLE"
    assert payload["logical_column_id"] is None
    assert payload["covers_logical_column_ids"] == []
    assert payload["column_binding_status"] == "NOT_APPLICABLE"


def _leading_ruled_marker_header_region() -> recovery_module._Region:
    region = _internal_microtrack_region(
        [
            [[(20.0, 180.0, "Report title")]],
            [[(120.0, 340.0, "Measure group")]],
            [
                [(20.0, 90.0, "Item")],
                [(100.0, 170.0, "State")],
                [(180.0, 250.0, "Amount")],
                [(260.0, 330.0, "Rate")],
            ],
            [
                [(20.0, 30.0, "1")],
                [(100.0, 110.0, "2")],
                [(180.0, 190.0, "3")],
                [(260.0, 270.0, "4")],
            ],
            [
                [(20.0, 40.0, "Alpha")],
                [(100.0, 130.0, "open")],
                [(180.0, 200.0, "10")],
                [(260.0, 280.0, "20")],
            ],
            [
                [(20.0, 40.0, "Beta")],
                [(100.0, 135.0, "closed")],
                [(180.0, 200.0, "30")],
                [(260.0, 280.0, "40")],
            ],
        ],
        ref_prefix="leading_ruled_marker",
    )
    region.rows[0].external_title = True
    region.rows[1].row_coalescence_kind = "LEAF_HEADER"
    ordinal_rows = [
        [None],
        [[1, 2, 3]],
        [[0], [1], [2], [3]],
        [[0], [1], [2], [3]],
        [[0], [1], [2], [3]],
        [[0], [1], [2], [3]],
    ]
    for row, entry_ordinals in zip(region.rows, ordinal_rows):
        for entry, ordinals in zip(row.entries, entry_ordinals):
            entry.geometry_column_ordinals = ordinals
    region.ruled_column_bands = [
        (10.0, 90.0),
        (90.0, 170.0),
        (170.0, 250.0),
        (250.0, 350.0),
    ]
    return region


def test_leading_ruled_marker_band_promotes_headers_and_finalizes_kinds() -> None:
    region = _leading_ruled_marker_header_region()

    table, state = _materialize_internal_region(region)
    rows = table["ordered_rows"]
    columns = table["logical_columns"]

    assert [row["role"] for row in rows] == [
        "TABLE_TITLE",
        "COLUMN_HEADER",
        "COLUMN_HEADER",
        "COLUMN_HEADER",
        "DATA",
        "DATA",
    ]
    assert [entry["kind"] for entry in rows[3]["entries"]] == ["MARKER"] * 4
    assert [entry["kind"] for entry in rows[4]["entries"]] == [
        "LABEL",
        "LABEL",
        "VALUE",
        "VALUE",
    ]
    spanner_id = rows[1]["entries"][0]["entry_id"]
    marker_ids = {entry["entry_id"] for entry in rows[3]["entries"]}
    assert spanner_id not in columns[0]["header_path"]
    assert all(spanner_id in column["header_path"] for column in columns[1:])
    assert all(
        marker_ids.isdisjoint(column["header_path"]) for column in columns
    )
    assert table["completeness_status"] == "COMPLETE"
    assert not any(
        issue["code"] == "logical_column_header_path_unknown"
        for issue in state.issues
    )

    first_column = columns[0]
    stale_issue_id = state.add_issue(
        code="logical_column_header_path_unknown",
        message="stale synthetic header uncertainty",
        anchor_ids=first_column["source_anchor_ids"],
        block_ids=[recovery_module.logical_table_block_id(table["table_id"])],
    )
    first_column["issue_ids"].append(stale_issue_id)
    first_geometry = next(
        evidence
        for evidence in state.geometry_evidence
        if evidence["geometry_evidence_id"]
        == first_column["geometry_evidence_ids"][0]
    )
    first_geometry["issue_ids"].append(stale_issue_id)

    assert recovery_module._finalize_column_header_paths(
        rows=region.rows,
        row_payloads=rows,
        logical_columns=columns,
        state=state,
        table_id=table["table_id"],
    ) == []
    assert stale_issue_id not in {
        issue["issue_id"] for issue in state.issues
    }
    assert stale_issue_id not in first_column["issue_ids"]
    assert stale_issue_id not in first_geometry["issue_ids"]


@pytest.mark.parametrize("case", ("gap", "overlap", "late", "external"))
def test_leading_ruled_marker_band_near_misses_fail_closed(case: str) -> None:
    region = _leading_ruled_marker_header_region()
    marker = region.rows[3]
    if case == "gap":
        marker.entries[2].text = "4"
    elif case == "overlap":
        marker.entries[-1].geometry_column_ordinals = [2]
    elif case == "late":
        region.rows[2].entries[-1].text = "10"
    else:
        marker.external_note = True

    recovery_module._classify_rows(region.rows)
    recovery_module._refine_leading_ruled_header_roles(region)

    assert marker.sequential_marker_header is False
    assert marker.role != "COLUMN_HEADER"


def _leading_right_suffix_header_region() -> recovery_module._Region:
    region = _internal_microtrack_region(
        [
            [[(100.0, 250.0, "Measure group")]],
            [
                [(20.0, 70.0, "Alpha")],
                [(100.0, 120.0, "10")],
                [(180.0, 200.0, "20")],
            ],
            [
                [(20.0, 70.0, "Beta")],
                [(100.0, 120.0, "30")],
                [(180.0, 200.0, "40")],
            ],
        ],
        ref_prefix="leading_right_suffix_header",
    )
    for row, groups in zip(
        region.rows,
        ([[1, 2]], [[0], [1], [2]], [[0], [1], [2]]),
    ):
        for entry, ordinals in zip(row.entries, groups):
            entry.geometry_column_ordinals = list(ordinals)
    region.ruled_column_bands = [
        (10.0, 90.0),
        (90.0, 170.0),
        (170.0, 250.0),
    ]
    return region


def test_leading_right_suffix_header_is_promoted_without_a_marker_band() -> None:
    table, _ = _materialize_internal_region(
        _leading_right_suffix_header_region()
    )
    header = table["ordered_rows"][0]

    assert header["role"] == "COLUMN_HEADER"
    assert header["entries"][0]["kind"] == "LABEL"
    assert table["logical_columns"][0]["header_path"] == []
    assert all(
        table["logical_columns"][ordinal]["header_path"]
        == [header["entries"][0]["entry_id"]]
        for ordinal in (1, 2)
    )


@pytest.mark.parametrize(
    "case",
    ("left_prefix", "value", "external", "single_body_support"),
)
def test_leading_right_suffix_header_near_misses_fail_closed(case: str) -> None:
    region = _leading_right_suffix_header_region()
    candidate = region.rows[0]
    if case == "left_prefix":
        candidate.entries[0].geometry_column_ordinals = [0, 1]
    elif case == "value":
        candidate.entries[0].text = "100"
    elif case == "external":
        candidate.external_title = True
    else:
        region.rows[-1].external_note = True

    recovery_module._classify_rows(region.rows)
    plan = recovery_module._plan_leading_header_roles(
        region,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )

    assert plan is None
    assert candidate.role != "COLUMN_HEADER"


@pytest.mark.parametrize("case", ("lane_drift", "value_header"))
def test_inferred_leading_marker_band_plans_before_apply_and_rejects_near_miss(
    case: str,
) -> None:
    region = _leading_ruled_marker_header_region()
    region.ruled_column_bands = None
    for row in region.rows:
        for entry in row.entries:
            entry.geometry_column_ordinals = None
    recovery_module._classify_rows(region.rows)
    marker = region.rows[3]
    assert marker.role == "DATA"

    accepted = recovery_module._plan_leading_header_roles(
        region,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )
    assert accepted is not None
    assert marker.role == "DATA"

    if case == "lane_drift":
        bbox = marker.entries[1].bbox
        marker.entries[1].bbox = (185.0, bbox[1], 195.0, bbox[3])
    else:
        region.rows[2].entries[-1].text = "10"
        recovery_module._classify_rows(region.rows)

    rejected = recovery_module._plan_leading_header_roles(
        region,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )
    assert rejected is None
    assert marker.role != "COLUMN_HEADER"


def test_unit_prefix_marker_requires_right_numeric_same_binding() -> None:
    region = _internal_microtrack_region(
        [
            [
                [(20.0, 60.0, "Item")],
                [(100.0, 108.0, "$")],
                [(115.0, 135.0, "10")],
                [(140.0, 148.0, "%")],
                [(200.0, 208.0, "$")],
            ]
        ],
        ref_prefix="unit_prefix_kind",
    )
    row = region.rows[0]
    row.role = "DATA"
    bindings = ["column_label", "column_value", "column_value", "column_value", "column_unit"]
    payload_entries = []
    for ordinal, (entry, column_id) in enumerate(zip(row.entries, bindings)):
        entry.logical_column_id = column_id
        entry.column_binding_status = "BOUND"
        payload_entries.append(
            {
                "entry_id": f"entry_kind_{ordinal}",
                "ordinal": ordinal,
                "kind": "LABEL",
                "logical_column_id": column_id,
                "covers_logical_column_ids": [],
                "column_binding_status": "BOUND",
            }
        )

    recovery_module._finalize_entry_kinds_after_binding(
        rows=[row],
        row_payloads=[{"entries": payload_entries}],
    )

    assert [entry["kind"] for entry in payload_entries] == [
        "LABEL",
        "MARKER",
        "VALUE",
        "UNIT",
        "UNIT",
    ]


def test_repeated_compact_code_lane_is_value_but_description_stays_label() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 35.0, "AA")], [(70.0, 160.0, "Long item one")], [(210.0, 230.0, "10")]],
            [[(20.0, 35.0, "BB")], [(70.0, 160.0, "Long item two")], [(210.0, 230.0, "20")]],
            [[(20.0, 35.0, "CC")], [(70.0, 170.0, "Long item three")], [(210.0, 230.0, "30")]],
        ],
        ref_prefix="semantic_kind_profile",
    )
    row_payloads = []
    for row_index, row in enumerate(region.rows):
        row.role = "DATA"
        payload_entries = []
        for entry_index, (entry, column_id) in enumerate(
            zip(row.entries, ("column_code", "column_label", "column_amount"))
        ):
            entry.logical_column_id = column_id
            entry.column_binding_status = "BOUND"
            payload_entries.append(
                {
                    "entry_id": f"profile_{row_index}_{entry_index}",
                    "ordinal": entry_index,
                    "kind": "LABEL",
                    "logical_column_id": column_id,
                    "covers_logical_column_ids": [],
                    "column_binding_status": "BOUND",
                }
            )
        row_payloads.append({"entries": payload_entries})

    recovery_module._finalize_entry_kinds_after_binding(
        rows=region.rows,
        row_payloads=row_payloads,
    )

    assert [entry["kind"] for entry in row_payloads[0]["entries"]] == [
        "VALUE",
        "LABEL",
        "VALUE",
    ]


def test_repeated_dedicated_unit_lane_is_not_currency_marker() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 70.0, f"Item {index}")], [(120.0, 140.0, "USD")], [(210.0, 230.0, str(index * 10))]]
            for index in range(1, 4)
        ],
        ref_prefix="dedicated_unit_profile",
    )
    row_payloads = []
    for row_index, row in enumerate(region.rows):
        row.role = "DATA"
        payload_entries = []
        for entry_index, (entry, column_id) in enumerate(
            zip(row.entries, ("column_label", "column_unit", "column_amount"))
        ):
            entry.logical_column_id = column_id
            entry.column_binding_status = "BOUND"
            payload_entries.append(
                {
                    "entry_id": f"unit_profile_{row_index}_{entry_index}",
                    "ordinal": entry_index,
                    "kind": "LABEL",
                    "logical_column_id": column_id,
                    "covers_logical_column_ids": [],
                    "column_binding_status": "BOUND",
                }
            )
        row_payloads.append({"entries": payload_entries})

    recovery_module._finalize_entry_kinds_after_binding(
        rows=region.rows,
        row_payloads=row_payloads,
    )

    assert all(row["entries"][1]["kind"] == "UNIT" for row in row_payloads)


def test_marker_only_column_header_path_is_unknown_and_partial() -> None:
    region = _leading_ruled_marker_header_region()
    region.rows[2].entries[0].text = "a)"

    table, state = _materialize_internal_region(region)
    column = table["logical_columns"][0]
    issue_by_id = {issue["issue_id"]: issue for issue in state.issues}

    assert column["header_path"] == []
    assert table["completeness_status"] == "PARTIAL"
    assert len(column["issue_ids"]) == 1
    assert issue_by_id[column["issue_ids"][0]]["code"] == (
        "logical_column_header_path_unknown"
    )
    assert column["issue_ids"][0] in table["issues"]


def _ordered_semantic_scope_region() -> recovery_module._Region:
    return _internal_microtrack_region(
        [
            [[(20.0, 90.0, "Item")], [(200.0, 250.0, "Amount")]],
            [[(20.0, 90.0, "Assets")]],
            [[(40.0, 100.0, "Cash")], [(200.0, 230.0, "10")]],
            [[(40.0, 100.0, "Bonds")], [(200.0, 230.0, "20")]],
            [[(40.0, 130.0, "Subtotal assets")], [(200.0, 230.0, "30")]],
            [[(20.0, 110.0, "Liabilities")]],
            [[(40.0, 100.0, "Debt")], [(200.0, 230.0, "15")]],
            [[(40.0, 100.0, "Other")], [(200.0, 230.0, "15")]],
            [[(20.0, 120.0, "Grand Total")], [(200.0, 230.0, "60")]],
        ],
        ref_prefix="ordered_semantic_scope",
    )


def test_ordered_semantic_plan_binds_peer_groups_and_closes_total() -> None:
    table, _ = _materialize_internal_region(_ordered_semantic_scope_region())
    rows = table["ordered_rows"]

    assert [row["role"] for row in rows] == [
        "COLUMN_HEADER",
        "GROUP_HEADER",
        "DATA",
        "DATA",
        "SUBTOTAL",
        "GROUP_HEADER",
        "DATA",
        "DATA",
        "TOTAL",
    ]
    first_group = rows[1]
    second_group = rows[5]
    assert all(
        row["parent_row_id"] == first_group["row_id"]
        and row["nesting_level"] == 1
        for row in rows[2:5]
    )
    assert all(
        row["parent_row_id"] == second_group["row_id"]
        and row["nesting_level"] == 1
        for row in rows[6:8]
    )
    assert rows[8]["parent_row_id"] is None
    assert rows[8]["nesting_level"] == 0


def test_structural_dense_rows_and_a_later_group_bound_nested_scope() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Item")], [(200.0, 250.0, "State")]],
            [[(20.0, 90.0, "First group")]],
            [[(40.0, 90.0, "Alpha")], [(200.0, 250.0, "Open")]],
            [[(20.0, 100.0, "Second group")]],
            [[(40.0, 90.0, "Beta")], [(200.0, 250.0, "Closed")]],
            [[(40.0, 90.0, "Gamma")], [(200.0, 250.0, "Open")]],
            [[(20.0, 100.0, "Grand Total")], [(200.0, 230.0, "2")]],
        ],
        ref_prefix="semantic_structural_dense",
    )

    recovery_module._classify_rows(region.rows)
    for index in (2, 4, 5):
        region.rows[index].role = "DATA"
    for index in (1, 3):
        region.rows[index].role = "GROUP_HEADER"
    plan = recovery_module._plan_ordered_row_semantics(
        region.rows,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )

    assert plan.decisions[1].role == "GROUP_HEADER"
    assert plan.decisions[2].parent_ordinal == 1
    assert plan.decisions[3].role == "GROUP_HEADER"
    assert plan.decisions[3].parent_ordinal == 1
    assert all(plan.decisions[index].parent_ordinal == 3 for index in (4, 5))


def test_equal_lane_nested_groups_are_siblings_inside_an_unclosed_root() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Item")], [(200.0, 250.0, "Amount")]],
            [[(20.0, 100.0, "Outer group")]],
            [[(40.0, 80.0, "Outer item")], [(200.0, 230.0, "5")]],
            [[(22.0, 100.0, "Nested group one")]],
            [[(40.0, 80.0, "Alpha")], [(200.0, 230.0, "10")]],
            [[(22.0, 100.0, "Nested group two")]],
            [[(40.0, 80.0, "Beta")], [(200.0, 230.0, "20")]],
            [[(20.0, 80.0, "Total")], [(200.0, 230.0, "35")]],
        ],
        ref_prefix="semantic_equal_lane_nested",
    )

    table, _ = _materialize_internal_region(region)
    rows = table["ordered_rows"]
    root = rows[1]

    assert rows[3]["role"] == "GROUP_HEADER"
    assert rows[3]["nesting_level"] == 1
    assert rows[3]["parent_row_id"] == root["row_id"]
    assert rows[5]["role"] == "GROUP_HEADER"
    assert rows[5]["nesting_level"] == 1
    assert rows[5]["parent_row_id"] == root["row_id"]
    assert rows[7]["role"] == "TOTAL"
    assert rows[7]["nesting_level"] == 1
    assert rows[7]["parent_row_id"] == root["row_id"]


def test_three_dense_rows_to_eof_prove_an_equal_lane_group_boundary() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Item")], [(200.0, 250.0, "Amount")]],
            [[(20.0, 80.0, "Baseline")], [(200.0, 230.0, "5")]],
            [[(20.0, 100.0, "Trailing group")]],
            [[(20.0, 80.0, "Alpha")], [(200.0, 230.0, "10")]],
            [[(20.0, 80.0, "Beta")], [(200.0, 230.0, "20")]],
            [[(20.0, 80.0, "Gamma")], [(200.0, 230.0, "30")]],
        ],
        ref_prefix="semantic_equal_lane_eof_group",
    )

    table, _ = _materialize_internal_region(region)
    rows = table["ordered_rows"]

    assert rows[2]["role"] == "GROUP_HEADER"
    assert all(
        row["parent_row_id"] == rows[2]["row_id"] for row in rows[3:]
    )


def test_weak_terminal_total_stays_total_for_the_only_root_group() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Item")], [(200.0, 250.0, "Amount")]],
            [[(20.0, 100.0, "Only group")]],
            [[(40.0, 80.0, "Alpha")], [(200.0, 230.0, "10")]],
            [[(40.0, 80.0, "Beta")], [(200.0, 230.0, "20")]],
            [[(20.0, 80.0, "Total")], [(200.0, 230.0, "30")]],
        ],
        ref_prefix="semantic_only_group_total",
    )

    table, _ = _materialize_internal_region(region)

    assert table["ordered_rows"][-1]["role"] == "TOTAL"
    assert table["ordered_rows"][-1]["parent_row_id"] == (
        table["ordered_rows"][1]["row_id"]
    )
    assert table["ordered_rows"][-1]["nesting_level"] == 1


def test_terminal_currency_marker_value_row_closes_the_only_group() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Item")], [(200.0, 250.0, "Amount")]],
            [[(20.0, 100.0, "Only group")]],
            [[(40.0, 80.0, "Alpha")], [(200.0, 230.0, "10")]],
            [[(40.0, 80.0, "Beta")], [(200.0, 230.0, "20")]],
            [[(180.0, 190.0, "$")], [(200.0, 230.0, "30")]],
        ],
        ref_prefix="semantic_marker_value_total",
    )

    table, _ = _materialize_internal_region(region)

    assert table["ordered_rows"][-1]["role"] == "TOTAL"
    assert table["ordered_rows"][-1]["parent_row_id"] is None
    assert table["ordered_rows"][-1]["nesting_level"] == 0
    assert [
        entry["logical_column_id"]
        for entry in table["ordered_rows"][-1]["entries"]
    ] == [table["logical_columns"][1]["column_id"]] * 2


def test_one_child_eof_group_candidate_stays_unknown_with_parent_issue() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 90.0, "Item")], [(200.0, 250.0, "Amount")]],
            [[(20.0, 100.0, "Baseline")], [(200.0, 230.0, "10")]],
            [[(20.0, 120.0, "Possible group")]],
            [[(40.0, 100.0, "Only child")], [(200.0, 230.0, "20")]],
        ],
        ref_prefix="ordered_semantic_ambiguous",
    )

    table, state = _materialize_internal_region(region)
    ambiguous, child = table["ordered_rows"][2:4]
    issue_by_id = {issue["issue_id"]: issue for issue in state.issues}

    assert ambiguous["role"] == "UNKNOWN"
    assert child["role"] == "DATA"
    assert child["nesting_level"] == 0
    assert child["parent_row_id"] is None
    assert {issue_by_id[issue_id]["code"] for issue_id in child["issue_ids"]} == {
        "logical_row_parent_unresolved"
    }
    assert table["completeness_status"] == "PARTIAL"


def test_terminal_total_is_a_parent_scope_barrier() -> None:
    region = _ordered_semantic_scope_region()
    trailing = _internal_microtrack_region(
        [[[(20.0, 90.0, "Detached")], [(200.0, 230.0, "5")]]],
        ref_prefix="ordered_semantic_trailing",
    ).rows[0]
    order_offset = max(word.order for word in region.words) + 1
    shifted_words = []
    for ordinal, word in enumerate(trailing.words):
        shifted_words.append(
            recovery_module._Word(
                word_ref=word.word_ref,
                page_ref=word.page_ref,
                text=word.text,
                bbox=(word.bbox[0], 180.0, word.bbox[2], 190.0),
                order=order_offset + ordinal,
            )
        )
    trailing.words = shifted_words
    for entry, word in zip(trailing.entries, shifted_words):
        entry.words = [word]
        entry.bbox = word.bbox
    trailing.bbox = tuple(_merge([list(word.bbox) for word in shifted_words]))
    region.rows.append(trailing)
    region.words.extend(shifted_words)
    region.bbox = tuple(_merge([list(row.bbox) for row in region.rows]))

    table, _ = _materialize_internal_region(region)
    detached = table["ordered_rows"][-1]
    assert detached["role"] == "DATA"
    assert detached["nesting_level"] == 0
    assert detached["parent_row_id"] is None


def test_ordered_semantic_plan_rejects_fingerprint_drift_atomically() -> None:
    region = _ordered_semantic_scope_region()
    recovery_module._classify_rows(region.rows)
    plan = recovery_module._plan_ordered_row_semantics(
        region.rows,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )
    for ordinal, row in enumerate(region.rows):
        row.row_id = f"row_semantic_{ordinal}"
    roles_before = [row.role for row in region.rows]
    region.rows[2].entries[0].text = "Changed after planning"

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="ordered_row_semantic_plan_invalid",
    ):
        recovery_module._apply_ordered_row_semantic_plan(region.rows, plan=plan)

    assert [row.role for row in region.rows] == roles_before
    assert all(row.parent_row_id is None for row in region.rows)


def test_ordered_semantic_plan_rejects_future_parent() -> None:
    region = _ordered_semantic_scope_region()
    recovery_module._classify_rows(region.rows)
    plan = recovery_module._plan_ordered_row_semantics(
        region.rows,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )
    invalid_decision = replace(plan.decisions[2], parent_ordinal=5)
    invalid = replace(
        plan,
        decisions=(
            *plan.decisions[:2],
            invalid_decision,
            *plan.decisions[3:],
        ),
    )
    for ordinal, row in enumerate(region.rows):
        row.row_id = f"row_semantic_future_{ordinal}"

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="ordered_row_semantic_plan_invalid",
    ):
        recovery_module._apply_ordered_row_semantic_plan(region.rows, plan=invalid)


@pytest.mark.parametrize(
    "value",
    ("USD 1,200", "$ 25", "(EUR 30)", "10 to 20"),
)
def test_numeric_classifier_preserves_prefixed_and_ranged_values(value: str) -> None:
    assert recovery_module._looks_numeric(value)


@pytest.mark.parametrize(
    ("right_x", "expected"),
    ((29.8, "FragmentOne"), (31.0, "Fragment One")),
)
def test_source_word_renderer_uses_geometry_for_fragment_spaces(
    right_x: float,
    expected: str,
) -> None:
    words = [
        recovery_module._Word(
            word_ref="fragment_left",
            page_ref="fragment_page",
            text="Fragment",
            bbox=(20.0, 100.0, 30.0, 110.0),
            order=1,
        ),
        recovery_module._Word(
            word_ref="fragment_right",
            page_ref="fragment_page",
            text="One",
            bbox=(right_x, 100.1, right_x + 8.0, 110.1),
            order=2,
        ),
    ]

    rows = recovery_module._row_bands(
        words,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )

    assert len(rows) == 1
    assert len(rows[0].entries) == 1
    assert rows[0].entries[0].text == expected
    assert [word.word_ref for word in rows[0].entries[0].words] == [
        "fragment_left",
        "fragment_right",
    ]


def _unruled_partial_rule_header_region(
) -> tuple[
    recovery_module._Region,
    list[recovery_module._ObjectGeometry],
]:
    suffix = [120.0, 160.0, 200.0, 240.0, 280.0, 320.0]
    region = _internal_microtrack_region(
        [
            [[(210.0, 230.0, "Suffix band")]],
            [[(150.0, 170.0, "Left group")], [(270.0, 290.0, "Right group")]],
            [[(x - 5.0, x + 5.0, f"Field {index}")] for index, x in enumerate(suffix)],
            *[
                [
                    [(20.0, 70.0, f"Item {row_index}")],
                    *[
                        [(x - 5.0, x + 5.0, str(row_index * 10 + index))]
                        for index, x in enumerate(suffix, start=1)
                    ],
                ]
                for row_index in range(1, 4)
            ],
        ],
        ref_prefix="unruled_suffix_header",
        row_ys=[100.0, 114.0, 128.0, 148.0, 162.0, 176.0],
    )
    region.origin += "+LEADING_HEADER_STACK+LOGICAL_ROW_COALESCENCE"
    leaf = region.rows[2]
    physical_rows = []
    for entries in (leaf.entries[:3], leaf.entries[3:]):
        words = [word for entry in entries for word in entry.words]
        physical_rows.append(
            recovery_module._RowBand(
                page_ref=leaf.page_ref,
                bbox=tuple(_merge([list(entry.bbox) for entry in entries])),
                words=words,
                entries=copy.deepcopy(entries),
            )
        )
    leaf.column_evidence_rows = tuple(physical_rows)
    leaf.row_coalescence_kind = "LEAF_HEADER"
    objects = [
        recovery_module._ObjectGeometry(
            object_ref="unruled_root_rule",
            page_ref=region.page.page_ref,
            bbox=(100.0, 111.0, 330.0, 111.2),
            object_kind="vector_line_inventory",
        ),
        recovery_module._ObjectGeometry(
            object_ref="unruled_left_child_rule",
            page_ref=region.page.page_ref,
            bbox=(100.0, 125.0, 220.0, 125.2),
            object_kind="vector_line_inventory",
        ),
        recovery_module._ObjectGeometry(
            object_ref="unruled_right_child_rule",
            page_ref=region.page.page_ref,
            bbox=(220.5, 125.0, 330.0, 125.2),
            object_kind="vector_line_inventory",
        ),
    ]
    return region, objects


def test_unruled_partial_rule_root_materializes_complete_suffix_header_paths(
) -> None:
    region, objects = _unruled_partial_rule_header_region()
    plan = recovery_module._plan_unruled_leading_suffix_headers(
        [region],
        object_bboxes=objects,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )

    recovery_module._apply_unruled_leading_suffix_header_plan(
        [region],
        plan=plan,
        object_bboxes=objects,
    )
    table, _ = _materialize_internal_region(region)

    assert [row["role"] for row in table["ordered_rows"][:3]] == [
        "COLUMN_HEADER",
        "COLUMN_HEADER",
        "COLUMN_HEADER",
    ]
    assert len(table["logical_columns"]) == 7
    assert table["logical_columns"][0]["header_path"] == []
    assert all(
        len(column["header_path"]) == 3
        for column in table["logical_columns"][1:]
    )


def test_narrow_header_lineage_promotes_only_the_proven_suffix_row() -> None:
    region = _internal_microtrack_region(
        [
            [[(300.0, 320.0, "Right"), (321.0, 350.0, "header")]],
            [[(305.0, 345.0, "detail")]],
            *[
                [
                    [(20.0, 90.0, f"Item {index}")],
                    [(300.0, 320.0, "Type")],
                    [(330.0, 350.0, str(index * 10))],
                ]
                for index in range(1, 4)
            ],
        ],
        ref_prefix="unruled_narrow_header",
        row_ys=[100.0, 108.0, 122.0, 136.0, 150.0],
    )
    region = _coalesce_internal_region(region)[0]
    plan = recovery_module._plan_unruled_leading_suffix_headers(
        [region],
        object_bboxes=[],
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )

    recovery_module._apply_unruled_leading_suffix_header_plan(
        [region],
        plan=plan,
        object_bboxes=[],
    )
    table, _ = _materialize_internal_region(region)

    assert len(plan.decisions) == 1
    assert table["ordered_rows"][0]["role"] == "COLUMN_HEADER"
    assert [row["role"] for row in table["ordered_rows"][1:]] == [
        "DATA",
        "DATA",
        "DATA",
    ]


@pytest.mark.parametrize("case", ("full_width", "competing_root", "missing_child"))
def test_unruled_partial_rule_root_rejects_near_misses_atomically(
    case: str,
) -> None:
    region, objects = _unruled_partial_rule_header_region()
    if case == "full_width":
        root = objects[0]
        objects[0] = recovery_module._ObjectGeometry(
            object_ref=root.object_ref,
            page_ref=root.page_ref,
            bbox=(10.0, root.bbox[1], root.bbox[2], root.bbox[3]),
            object_kind=root.object_kind,
        )
    elif case == "competing_root":
        objects.append(
            recovery_module._ObjectGeometry(
                object_ref="unruled_competing_root_rule",
                page_ref=region.page.page_ref,
                bbox=(101.0, 112.0, 329.0, 112.2),
                object_kind="vector_line_inventory",
            )
        )
    else:
        objects.pop()

    plan = recovery_module._plan_unruled_leading_suffix_headers(
        [region],
        object_bboxes=objects,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )
    recovery_module._apply_unruled_leading_suffix_header_plan(
        [region],
        plan=plan,
        object_bboxes=objects,
    )

    assert plan.decisions == ()
    assert not region.rows[0].proven_leading_suffix_header
    assert all(
        entry.proven_header_coverage_bbox is None
        for row in region.rows[:2]
        for entry in row.entries
    )


def test_unruled_suffix_header_plan_rejects_geometry_drift_before_mutation() -> None:
    region, objects = _unruled_partial_rule_header_region()
    plan = recovery_module._plan_unruled_leading_suffix_headers(
        [region],
        object_bboxes=objects,
        config=recovery_module.LogicalRowTableRecoveryConfig(),
    )
    root = objects[0]
    objects[0] = recovery_module._ObjectGeometry(
        object_ref=root.object_ref,
        page_ref=root.page_ref,
        bbox=(root.bbox[0] + 1.0, *root.bbox[1:]),
        object_kind=root.object_kind,
    )

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="unruled_leading_suffix_header_plan_invalid",
    ):
        recovery_module._apply_unruled_leading_suffix_header_plan(
            [region],
            plan=plan,
            object_bboxes=objects,
        )

    assert not region.rows[0].proven_leading_suffix_header
    assert all(
        entry.proven_header_coverage_bbox is None
        for row in region.rows[:2]
        for entry in row.entries
    )


def test_g1_release_ledger_closes_global_source_accounting() -> None:
    bracketed, _ = _g1_bracketed_marked_region()
    source_refs = frozenset(word.word_ref for word in bracketed.words)
    applied = recovery_module._apply_planned_ruled_baseline_recovery(
        [bracketed]
    )[0]

    retained_refs, released_refs = recovery_module._source_accounting_scope(
        [applied]
    )
    _, state = _materialize_internal_region(copy.deepcopy(applied))
    owned_refs = frozenset(
        state.word_ref_by_source_word_id[item["source_word_id"]]
        for item in state.source_word_ownership
    )
    paragraph_refs = (source_refs - {*retained_refs, *released_refs}) | (
        released_refs
    )

    assert source_refs == {*retained_refs, *released_refs}
    assert not retained_refs.intersection(released_refs)
    assert owned_refs == retained_refs
    assert paragraph_refs == released_refs
    assert owned_refs | paragraph_refs == source_refs
    assert not owned_refs.intersection(paragraph_refs)


def test_materialization_rejects_orphan_word_before_state_mutation() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Header")], [(200.0, 230.0, "Amount")]],
            [[(20.0, 80.0, "Item")], [(200.0, 230.0, "10")]],
        ],
        ref_prefix="accounting_orphan",
    )
    region.rows[0].entries[-1].words.pop()
    state = recovery_module._RecoveryState(
        source_checksum_sha256=SOURCE_CHECKSUM,
        private_evidence_ref=PRIVATE_EVIDENCE_REF,
        bbox_by_ref={},
    )

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="logical_row_source_accounting_partition_invalid",
    ):
        recovery_module._materialize_logical_table(
            [region],
            state=state,
            config=recovery_module.LogicalRowTableRecoveryConfig(),
        )

    assert state.anchors == []
    assert state.geometry_evidence == []
    assert state.source_word_ownership == []
    assert state.issues == []


def test_materialization_rejects_global_duplicate_before_state_mutation() -> None:
    first = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Header")], [(200.0, 230.0, "Amount")]],
            [[(20.0, 80.0, "Item")], [(200.0, 230.0, "10")]],
        ],
        ref_prefix="accounting_duplicate",
    )
    duplicate = copy.deepcopy(first)
    duplicate.source_ref += "_copy"
    state = recovery_module._RecoveryState(
        source_checksum_sha256=SOURCE_CHECKSUM,
        private_evidence_ref=PRIVATE_EVIDENCE_REF,
        bbox_by_ref={},
    )

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="logical_row_source_accounting_scope_invalid",
    ):
        recovery_module._materialize_logical_table(
            [first, duplicate],
            state=state,
            config=recovery_module.LogicalRowTableRecoveryConfig(),
        )

    assert state.anchors == []
    assert state.geometry_evidence == []
    assert state.source_word_ownership == []
    assert state.issues == []


def test_release_ledger_is_atomic_and_scope_merge_preserves_it() -> None:
    left, right = _geometry_scope_pair(ref_prefix="accounting_release_merge")
    accepted_refs = frozenset(
        word.word_ref for region in (left, right) for word in region.words
    )
    left.rows[0].external_title = True
    right.rows[0].external_title = True

    recovery_module._drop_external_title(left)
    recovery_module._drop_external_title(right)
    retained_refs, released_refs = recovery_module._source_accounting_scope(
        [left, right]
    )
    merged = recovery_module._materialize_scope_merge(
        left,
        right,
        object_bboxes=[],
    )

    assert merged is not None
    merged_retained, merged_released = (
        recovery_module._source_accounting_scope([merged])
    )
    assert accepted_refs == {*retained_refs, *released_refs}
    assert merged_retained == retained_refs
    assert merged_released == released_refs
    assert merged.released_non_table_word_refs == tuple(sorted(released_refs))
    assert (
        recovery_module._materialize_scope_split(
            merged,
            split_index=1,
            object_bboxes=[],
        )
        is None
    )

    invalid = copy.deepcopy(merged)
    invalid.rows[0].external_title = True
    invalid.released_non_table_word_refs = (
        *invalid.released_non_table_word_refs,
        invalid.words[0].word_ref,
    )
    before_rows = list(invalid.rows)
    before_words = list(invalid.words)
    before_released = invalid.released_non_table_word_refs
    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="logical_row_source_accounting_scope_invalid",
    ):
        recovery_module._drop_external_title(invalid)
    assert invalid.rows == before_rows
    assert invalid.words == before_words
    assert invalid.released_non_table_word_refs == before_released


def test_ghost_release_is_rejected_before_grouping_or_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = ProjectionBuilder(ref_prefix="accounting_ghost_release")
    header_refs = builder.add_row(
        page_number=1,
        y=20.0,
        entries=[(20.0, "Item"), (200.0, "Amount")],
    )
    data_refs = builder.add_row(
        page_number=1,
        y=35.0,
        entries=[(20.0, "Alpha"), (200.0, "10")],
    )
    data_refs += builder.add_row(
        page_number=1,
        y=50.0,
        entries=[(20.0, "Beta"), (200.0, "20")],
    )
    builder.add_candidate(
        page_number=1,
        bbox=[10.0, 10.0, 260.0, 70.0],
        word_refs=[*header_refs, *data_refs],
    )
    reconcile = recovery_module._reconcile_same_page_table_scopes

    def inject_ghost_release(*args: Any, **kwargs: Any):
        regions = reconcile(*args, **kwargs)
        assert regions
        regions[0].released_non_table_word_refs = (
            *regions[0].released_non_table_word_refs,
            "ghost_release_ref",
        )
        return regions

    def forbidden_later_phase(*_args: Any, **_kwargs: Any):
        raise AssertionError("source_scope_preflight_was_bypassed")

    monkeypatch.setattr(
        recovery_module,
        "_reconcile_same_page_table_scopes",
        inject_ghost_release,
    )
    monkeypatch.setattr(
        recovery_module,
        "_group_continuations",
        forbidden_later_phase,
    )
    monkeypatch.setattr(
        recovery_module,
        "_materialize_logical_table",
        forbidden_later_phase,
    )

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="logical_row_source_accounting_scope_invalid",
    ):
        _recover(builder)


def _legacy_post_track_binding_fixture(
    row_entries: list[list[list[tuple[float, float, str]]]],
    *,
    track_coordinates: list[float],
    ref_prefix: str,
    tolerance: float = 4.0,
) -> tuple[
    list[recovery_module._RowBand],
    list[dict[str, Any]],
    list[recovery_module._ColumnTrack],
]:
    region = _internal_microtrack_region(
        row_entries,
        ref_prefix=ref_prefix,
    )
    payloads = []
    for row_index, row in enumerate(region.rows):
        row.role = "DATA"
        row.row_id = f"row_{ref_prefix}_{row_index}"
        payload_entries = []
        for entry_index, entry in enumerate(row.entries):
            entry.entry_id = f"entry_{ref_prefix}_{row_index}_{entry_index}"
            payload_entries.append(
                {
                    "entry_id": entry.entry_id,
                    "column_binding_status": "NOT_APPLICABLE",
                    "logical_column_id": None,
                    "covers_logical_column_ids": [],
                }
            )
        payloads.append({"row_id": row.row_id, "entries": payload_entries})
    tracks = [
        recovery_module._ColumnTrack(
            edge="CENTER",
            coordinate=coordinate,
            tolerance=tolerance,
            entries=[],
            row_indexes=set(range(len(region.rows))),
        )
        for coordinate in track_coordinates
    ]
    return region.rows, payloads, tracks


def test_legacy_post_track_plan_binds_repeated_prefix_and_value_siblings(
) -> None:
    rows, payloads, tracks = _legacy_post_track_binding_fixture(
        [
            [
                [(20.0, 50.0, "Alpha")],
                [(194.0, 198.0, "$")],
                [(200.0, 208.0, "10")],
            ],
            [
                [(20.0, 50.0, "Beta")],
                [(194.0, 198.0, "%")],
                [(200.0, 208.0, "20")],
            ],
            [
                [(20.0, 50.0, "Gamma")],
                [(194.0, 198.0, "1)")],
                [(200.0, 208.0, "30")],
            ],
        ],
        track_coordinates=[35.0, 201.0],
        ref_prefix="legacy_compound_lane",
    )

    plan = recovery_module._plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=3,
    )
    compound = {
        (decision.row_index, decision.entry_index, decision.track_ordinal)
        for decision in plan.decisions
        if decision.proof_kind == "REPEATED_PREFIX_VALUE_LANE"
    }

    assert compound == {
        (row_index, entry_index, 1)
        for row_index in range(3)
        for entry_index in (1, 2)
    }

    recovery_module._apply_legacy_post_track_binding_plan(
        rows=rows,
        row_payloads=payloads,
        tracks=tracks,
        column_ids=["column_legacy_label", "column_legacy_value"],
        active_track_ordinals={0, 1},
        plan=plan,
    )

    for row, payload in zip(rows, payloads):
        for entry, entry_payload in zip(row.entries[1:], payload["entries"][1:]):
            assert entry.column_binding_status == "BOUND"
            assert entry.logical_column_id == "column_legacy_value"
            assert entry_payload["column_binding_status"] == "BOUND"
            assert entry_payload["logical_column_id"] == "column_legacy_value"


@pytest.mark.parametrize(
    "case",
    ("single_support", "multiple_covered_tracks", "competing_entry"),
)
def test_legacy_post_track_prefix_value_near_misses_fail_closed(
    case: str,
) -> None:
    rows_total = 1 if case == "single_support" else 2
    row = [
        [(20.0, 50.0, "Label")],
        [(194.0, 198.0, "$")],
        [(200.0, 208.0, "10")],
    ]
    row_entries = [copy.deepcopy(row) for _ in range(rows_total)]
    track_coordinates = [35.0, 201.0]
    if case == "multiple_covered_tracks":
        track_coordinates = [35.0, 196.0, 204.0]
    elif case == "competing_entry":
        for entries in row_entries:
            entries.append([(199.0, 203.0, "40")])
    rows, _, tracks = _legacy_post_track_binding_fixture(
        row_entries,
        track_coordinates=track_coordinates,
        ref_prefix=f"legacy_compound_near_miss_{case}",
    )

    plan = recovery_module._plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=3,
    )

    assert all(
        decision.proof_kind != "REPEATED_PREFIX_VALUE_LANE"
        for decision in plan.decisions
    )


def _legacy_monotonic_complement_fixture(
    *,
    rows_total: int = 3,
    missing_entry_index: int = 2,
    nonmonotonic: bool = False,
) -> tuple[
    list[recovery_module._RowBand],
    list[dict[str, Any]],
    list[recovery_module._ColumnTrack],
]:
    coordinates = [30.0, 90.0, 150.0, 210.0, 270.0]
    row_entries = []
    for row_index in range(rows_total):
        entry_coordinates = list(coordinates)
        entry_coordinates[missing_entry_index] += 12.0
        if nonmonotonic:
            entry_coordinates[1], entry_coordinates[3] = (
                entry_coordinates[3],
                entry_coordinates[1],
            )
        row_entries.append(
            [
                [
                    (
                        coordinate - 4.0,
                        coordinate + 4.0,
                        str((row_index + 1) * 10 + entry_index),
                    )
                ]
                for entry_index, coordinate in enumerate(entry_coordinates)
            ]
        )
    return _legacy_post_track_binding_fixture(
        row_entries,
        track_coordinates=coordinates,
        ref_prefix=(
            "legacy_monotonic_nonmonotonic"
            if nonmonotonic
            else f"legacy_monotonic_{rows_total}_{missing_entry_index}"
        ),
        tolerance=5.0,
    )


def test_legacy_post_track_plan_binds_repeated_monotonic_complement(
) -> None:
    rows, payloads, tracks = _legacy_monotonic_complement_fixture()

    plan = recovery_module._plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=3,
    )

    assert {
        (decision.row_index, decision.entry_index, decision.track_ordinal)
        for decision in plan.decisions
        if decision.proof_kind == "REPEATED_MONOTONIC_COMPLEMENT"
    } == {(row_index, 2, 2) for row_index in range(3)}

    recovery_module._apply_legacy_post_track_binding_plan(
        rows=rows,
        row_payloads=payloads,
        tracks=tracks,
        column_ids=[f"column_legacy_{index}" for index in range(5)],
        active_track_ordinals=set(range(5)),
        plan=plan,
    )

    assert all(
        entry.column_binding_status == "BOUND"
        and entry.logical_column_id is not None
        for row in rows
        for entry in row.entries
    )
    assert all(
        entry["column_binding_status"] == "BOUND"
        and entry["logical_column_id"] is not None
        for payload in payloads
        for entry in payload["entries"]
    )


@pytest.mark.parametrize(
    ("rows_total", "missing_entry_index", "nonmonotonic"),
    ((2, 2, False), (3, 0, False), (3, 2, True)),
)
def test_legacy_post_track_monotonic_complement_near_misses_fail_closed(
    rows_total: int,
    missing_entry_index: int,
    nonmonotonic: bool,
) -> None:
    rows, _, tracks = _legacy_monotonic_complement_fixture(
        rows_total=rows_total,
        missing_entry_index=missing_entry_index,
        nonmonotonic=nonmonotonic,
    )

    plan = recovery_module._plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=3,
    )

    assert all(
        decision.proof_kind != "REPEATED_MONOTONIC_COMPLEMENT"
        for decision in plan.decisions
    )


def test_legacy_post_track_plan_rejects_geometry_drift_before_any_binding(
) -> None:
    rows, payloads, tracks = _legacy_monotonic_complement_fixture()
    plan = recovery_module._plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=3,
    )
    entry = rows[0].entries[2]
    entry.bbox = (
        entry.bbox[0] + 1.0,
        entry.bbox[1],
        entry.bbox[2] + 1.0,
        entry.bbox[3],
    )

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="legacy_post_track_binding_plan_invalid",
    ):
        recovery_module._apply_legacy_post_track_binding_plan(
            rows=rows,
            row_payloads=payloads,
            tracks=tracks,
            column_ids=[f"column_legacy_{index}" for index in range(5)],
            active_track_ordinals=set(range(5)),
            plan=plan,
        )

    assert all(
        entry.column_binding_status == "NOT_APPLICABLE"
        and entry.logical_column_id is None
        and entry.covers_logical_column_ids == []
        for row in rows
        for entry in row.entries
    )
    assert all(
        entry["column_binding_status"] == "NOT_APPLICABLE"
        and entry["logical_column_id"] is None
        and entry["covers_logical_column_ids"] == []
        for payload in payloads
        for entry in payload["entries"]
    )


def test_active_track_plan_collapses_repeated_physical_pairs_into_seven_lanes(
) -> None:
    coordinates = [30.0 + index * 25.0 for index in range(13)]
    row_entries = []
    for row_index in range(2):
        entries = [[(26.0, 50.0, f"Label {row_index}")]]
        for pair_index in range(6):
            prefix_center = coordinates[pair_index * 2 + 1]
            value_center = coordinates[pair_index * 2 + 2]
            entries.append(
                [(prefix_center - 2.0, prefix_center + 2.0, "$")]
            )
            entries.append(
                [
                    (
                        value_center - 4.0,
                        value_center + 4.0,
                        "-" if pair_index == 5 else str(pair_index + 10),
                    )
                ]
            )
        row_entries.append(entries)
    rows, payloads, tracks = _legacy_post_track_binding_fixture(
        row_entries,
        track_coordinates=coordinates,
        ref_prefix="active_row_lane_collapse",
        tolerance=5.0,
    )
    active = set(range(0, 13, 2))
    base_plan = recovery_module._plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=3,
    )
    active_plan = recovery_module._plan_legacy_active_track_bindings(
        rows=rows,
        tracks=tracks,
        active_track_ordinals=active,
        minimum_column_observations=3,
    )

    assert sum(
        decision.proof_kind == "ORDERED_ROW_LANE_COLLAPSE"
        for decision in active_plan.decisions
    ) == 26

    column_ids = [f"column_active_{index}" for index in range(13)]
    recovery_module._apply_legacy_post_track_binding_plan(
        rows=rows,
        row_payloads=payloads,
        tracks=tracks,
        column_ids=column_ids,
        active_track_ordinals=active,
        plan=base_plan,
        active_plan=active_plan,
    )
    recovery_module._finalize_entry_kinds_after_binding(
        rows=rows,
        row_payloads=payloads,
    )

    for payload in payloads:
        assert payload["entries"][0]["logical_column_id"] == column_ids[0]
        for pair_index in range(6):
            target = column_ids[(pair_index + 1) * 2]
            left = payload["entries"][pair_index * 2 + 1]
            right = payload["entries"][pair_index * 2 + 2]
            assert left["logical_column_id"] == target
            assert right["logical_column_id"] == target
            assert left["kind"] == "MARKER"
        assert payload["entries"][-1]["kind"] == "MARKER"


def test_three_parallel_group_closers_remain_peer_subtotals() -> None:
    physical_rows = [
        [[(20.0, 80.0, "Item")], [(200.0, 250.0, "Amount")]],
    ]
    for group_index in range(3):
        physical_rows.extend(
            [
                [[(20.0, 100.0, f"Group {group_index}")]],
                [
                    [(40.0, 100.0, f"Child {group_index}")],
                    [(200.0, 230.0, str(group_index + 1))],
                ],
                [
                    [(40.0, 120.0, "Total line")],
                    [(190.0, 198.0, "$")],
                    [(200.0, 230.0, str(group_index + 1))],
                ],
            ]
        )
    region = _internal_microtrack_region(
        physical_rows,
        ref_prefix="semantic_parallel_peer_subtotals",
    )

    table, _ = _materialize_internal_region(region)
    rows = table["ordered_rows"]

    assert [rows[index]["role"] for index in (3, 6, 9)] == [
        "SUBTOTAL",
        "SUBTOTAL",
        "SUBTOTAL",
    ]


def test_single_column_ruled_group_header_is_not_directly_bound() -> None:
    region = _ruled_binding_truth_table_region()
    region.rows[1].entries[0].geometry_column_ordinals = [0]

    table, _ = _materialize_internal_region(region)
    group_row = next(
        row for row in table["ordered_rows"] if row["role"] == "GROUP_HEADER"
    )
    group = group_row["entries"][0]

    assert len(table["logical_columns"]) == 3
    assert group["column_binding_status"] == "NOT_APPLICABLE"
    assert group["logical_column_id"] is None
    assert group["covers_logical_column_ids"] == []


def test_single_column_hinted_group_header_is_not_directly_bound() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 70.0, "Item")], [(200.0, 240.0, "Amount")]],
            [[(20.0, 90.0, "Assets")]],
            [[(35.0, 85.0, "Cash")], [(200.0, 220.0, "10")]],
            [[(35.0, 85.0, "Bonds")], [(200.0, 220.0, "20")]],
        ],
        ref_prefix="hinted_group_header_guard",
    )
    for row in region.rows:
        for ordinal, entry in enumerate(row.entries):
            entry.geometry_column_ordinals = [ordinal]

    table, _ = _materialize_internal_region(region)
    group_row = next(
        row for row in table["ordered_rows"] if row["role"] == "GROUP_HEADER"
    )
    group = group_row["entries"][0]

    assert len(table["logical_columns"]) == 2
    assert group["column_binding_status"] == "NOT_APPLICABLE"
    assert group["logical_column_id"] is None
    assert group["covers_logical_column_ids"] == []
    assert all(
        entry["column_binding_status"] == "BOUND"
        for row in table["ordered_rows"]
        if row["role"] != "GROUP_HEADER"
        for entry in row["entries"]
    )


def test_detached_leading_context_is_titles_then_parenthetical_note() -> None:
    region = _internal_microtrack_region(
        [
            [[(200.0, 260.0, "ALPHA CONTEXT")]],
            [[(205.0, 265.0, "SECOND CONTEXT")]],
            [[(210.0, 270.0, "PERIOD 2026")]],
            [[(220.0, 275.0, "(Preliminary)")]],
            [[(20.0, 85.0, "Primary group")]],
            [[(40.0, 100.0, "First")], [(200.0, 230.0, "10")]],
            [[(40.0, 100.0, "Second")], [(200.0, 230.0, "20")]],
            [[(20.0, 100.0, "Total")], [(200.0, 230.0, "30")]],
        ],
        ref_prefix="semantic_detached_context",
    )

    table, _ = _materialize_internal_region(region)

    assert [row["role"] for row in table["ordered_rows"][:5]] == [
        "TABLE_TITLE",
        "TABLE_TITLE",
        "TABLE_TITLE",
        "NOTE",
        "GROUP_HEADER",
    ]
    assert all(
        row["nesting_level"] == 0 and row["parent_row_id"] is None
        for row in table["ordered_rows"][:5]
    )


def test_consecutive_equal_lane_groups_without_child_are_root_peers() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Item")], [(200.0, 250.0, "Amount")]],
            [[(20.0, 100.0, "First opener")]],
            [[(20.0, 100.0, "Second opener")]],
            [[(40.0, 90.0, "Only child")], [(200.0, 230.0, "10")]],
            [[(20.0, 100.0, "Total")], [(200.0, 230.0, "10")]],
        ],
        ref_prefix="semantic_equal_lane_empty_opener",
    )

    table, _ = _materialize_internal_region(region)
    first, second, child = table["ordered_rows"][1:4]

    assert first["role"] == second["role"] == "GROUP_HEADER"
    assert first["parent_row_id"] is None
    assert second["parent_row_id"] is None
    assert child["parent_row_id"] == second["row_id"]
    assert child["nesting_level"] == 1


def test_terminal_compound_total_survives_a_completed_peer_group() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Item")], [(200.0, 250.0, "Amount")]],
            [[(20.0, 100.0, "First opener")]],
            [[(20.0, 100.0, "Second opener")]],
            [[(40.0, 90.0, "Only child")], [(200.0, 230.0, "10")]],
            [
                [(40.0, 120.0, "Total line")],
                [(190.0, 198.0, "$")],
                [(200.0, 230.0, "10")],
            ],
        ],
        ref_prefix="semantic_terminal_compound_total",
    )

    table, _ = _materialize_internal_region(region)
    second = table["ordered_rows"][2]
    total = table["ordered_rows"][-1]

    assert total["role"] == "TOTAL"
    assert total["parent_row_id"] == second["row_id"]
    assert total["nesting_level"] == 1


def test_ruled_columns_recover_unhinted_body_entries_from_band_membership() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 80.0, "Item")], [(200.0, 250.0, "Amount")]],
            [[(20.0, 80.0, "Alpha")], [(200.0, 230.0, "10")]],
            [
                [(20.0, 110.0, "Total line")],
                [(190.0, 198.0, "$")],
                [(200.0, 230.0, "10")],
            ],
        ],
        ref_prefix="ruled_unhinted_body",
    )
    region.ruled_column_bands = [(15.0, 150.0), (150.0, 260.0)]
    for entry, ordinal in zip(region.rows[0].entries, (0, 1)):
        entry.geometry_column_ordinals = [ordinal]
    for entry, ordinal in zip(region.rows[1].entries, (0, 1)):
        entry.geometry_column_ordinals = [ordinal]
    for entry in region.rows[2].entries:
        entry.geometry_column_ordinals = None

    table, _ = _materialize_internal_region(region)
    total = table["ordered_rows"][-1]

    assert len(table["logical_columns"]) == 2
    assert [entry["column_binding_status"] for entry in total["entries"]] == [
        "BOUND",
        "BOUND",
        "BOUND",
    ]
    assert total["entries"][0]["logical_column_id"] == (
        table["logical_columns"][0]["column_id"]
    )
    assert all(
        entry["logical_column_id"] == table["logical_columns"][1]["column_id"]
        for entry in total["entries"][1:]
    )


def test_repeated_post_numeric_suffix_is_neutral_unit_evidence() -> None:
    region = _internal_microtrack_region(
        [
            [
                [(20.0, 70.0, "Alpha")],
                [(200.0, 220.0, "10")],
                [(225.0, 250.0, "basis")],
            ],
            [
                [(20.0, 70.0, "Beta")],
                [(200.0, 220.0, "20")],
                [(225.0, 250.0, "scale")],
            ],
        ],
        ref_prefix="structural_unit_suffix",
    )
    payloads = []
    for row_index, row in enumerate(region.rows):
        row.role = "DATA"
        row.row_id = f"unit_suffix_row_{row_index}"
        payload_entries = []
        for entry_index, entry in enumerate(row.entries):
            entry.entry_id = f"unit_suffix_entry_{row_index}_{entry_index}"
            column_id = "column_label" if entry_index == 0 else "column_value"
            entry.logical_column_id = column_id
            entry.column_binding_status = "BOUND"
            payload_entries.append(
                {
                    "entry_id": entry.entry_id,
                    "kind": "LABEL",
                    "column_binding_status": "BOUND",
                    "logical_column_id": column_id,
                    "covers_logical_column_ids": [],
                }
            )
        payloads.append({"row_id": row.row_id, "entries": payload_entries})

    recovery_module._finalize_entry_kinds_after_binding(
        rows=region.rows,
        row_payloads=payloads,
        logical_columns=[
            {"column_id": "column_label", "ordinal": 0},
            {"column_id": "column_value", "ordinal": 1},
        ],
    )

    assert all(payload["entries"][-1]["kind"] == "UNIT" for payload in payloads)


def test_legacy_post_track_plan_rejects_detached_track_geometry_drift() -> None:
    rows, payloads, tracks = _legacy_monotonic_complement_fixture()
    detached = copy.deepcopy(rows[0].entries[0])
    tracks[0].entries = [detached]
    plan = recovery_module._plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=3,
    )
    detached.bbox = (
        detached.bbox[0] + 2.0,
        detached.bbox[1],
        detached.bbox[2] + 2.0,
        detached.bbox[3],
    )

    with pytest.raises(
        recovery_module.LogicalRowTableRecoveryError,
        match="legacy_post_track_binding_plan_invalid",
    ):
        recovery_module._apply_legacy_post_track_binding_plan(
            rows=rows,
            row_payloads=payloads,
            tracks=tracks,
            column_ids=[f"column_legacy_{index}" for index in range(5)],
            active_track_ordinals=set(range(5)),
            plan=plan,
        )
    assert all(
        entry.column_binding_status == "NOT_APPLICABLE"
        for row in rows
        for entry in row.entries
    )


def test_coalesced_entry_uses_source_geometry_at_touching_fragment_seam() -> None:
    region = _internal_microtrack_region(
        [
            [[(20.0, 30.0, "5")]],
            [[(30.0, 38.0, ".4")]],
        ],
        row_ys=[100.0, 100.0],
        ref_prefix="coalesced_touching_fragments",
    )
    refs = tuple(word.word_ref for word in region.words)
    plan = recovery_module._RowCoalescencePlan(
        region_index=0,
        start_index=0,
        end_index=2,
        kind="TEST_FRAGMENT_SEAM",
        entry_word_ref_groups=(refs,),
    )

    row = recovery_module._row_from_coalescence_plan(region.rows, plan=plan)

    assert row is not None
    assert row.entries[0].text == "5.4"
