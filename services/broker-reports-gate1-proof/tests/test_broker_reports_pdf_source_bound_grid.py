from __future__ import annotations

import os
import hashlib
from pathlib import Path

import pytest

from broker_reports_gate1.pdf_source_bound_grid import (
    PdfSourceBoundGridError,
    reconstruct_mcid_grid,
)
from broker_reports_gate1.pdf_layout import (
    PdfLayoutParserConfig,
    PdfPlumberLayoutAdapter,
    _sanitize_word,
    _sanitize_words,
)


TABLE_SHAPES = [(6, 32)]
TRADE_IDS = ["5586419352", "5586419351", "5586419350", "5586423274", "5586423273"]
TBANK_VISUALLY_VERIFIED_REGIONS = {
    1: [
        ("p1_table_1_1", [15.6, 157.4, 789.7, 323.3], (6, 32)),
        ("p1_table_1_2", [15.6, 347.2, 789.7, 388.2], (1, 32)),
        ("p1_table_1_3", [15.6, 412.1, 789.7, 453.1], (1, 32)),
        ("p1_table_1_4", [15.6, 491.0, 789.7, 559.0], (2, 28)),
    ],
    2: [
        ("p2_cash_balances", [15.6, 37.4, 789.7, 138.5], (4, 7)),
        ("p2_rub_cash_ops", [15.6, 157.5, 789.7, 229.9], (4, 7)),
        ("p2_table_3_1", [15.6, 254.3, 789.7, 309.3], (2, 12)),
        ("p2_table_3_2", [15.6, 333.3, 789.7, 364.3], (1, 8)),
        ("p2_table_3_3", [15.6, 402.2, 789.7, 433.2], (1, 7)),
        ("p2_table_4_1", [15.6, 457.1, 789.7, 510.2], (2, 8)),
        ("p2_table_4_2", [15.6, 534.1, 789.7, 565.1], (1, 8)),
    ],
    3: [
        ("p3_table_4_3", [15.6, 37.4, 789.7, 68.4], (1, 6)),
        ("p3_table_4_4", [15.6, 92.4, 789.7, 123.4], (1, 2)),
        ("p3_table_5", [15.6, 147.3, 789.7, 187.3], (2, 2)),
        ("p3_table_6", [15.6, 225.1, 789.7, 529.1], (21, 2)),
    ],
    4: [],
}


def _raw_char(text: str, x0: float, mcid=None):
    return {"text": text, "x0": x0, "top": 0, "x1": x0 + 1, "bottom": 1, "fontname": "F", "size": 10, "mcid": mcid, "tag": "P" if mcid is not None else None}


def test_non_mcid_and_single_mcid_words_keep_v1_bytes() -> None:
    for chars in ([_raw_char("A", 0)], [_raw_char("A", 0, 7)]):
        raw = {"text": "A", "x0": 0, "top": 0, "x1": 1, "bottom": 1, "chars": chars}
        assert _sanitize_words([raw], raw_chars=chars) == [_sanitize_word(raw, 1)]


def test_contiguous_mcid_runs_split_without_changing_literal_or_order() -> None:
    chars = [_raw_char("A", 0, 7), _raw_char("B", 1, 8)]
    raw = {"text": "AB", "x0": 0, "top": 0, "x1": 2, "bottom": 1, "chars": chars}
    result = _sanitize_words([raw], raw_chars=chars)
    assert [item["text"] for item in result] == ["A", "B"]
    assert [item["mcid_refs"] for item in result] == [["7"], ["8"]]
    assert [item["parser_ordinal"] for item in result] == [1, 2]
    assert [item["bbox"] for item in result] == [[0.0, 0.0, 1.0, 1.0], [1.0, 0.0, 2.0, 1.0]]


def test_crossing_mcid_word_fails_closed() -> None:
    chars = [_raw_char("A", 0, 7), _raw_char("B", 1, 8), _raw_char("C", 2, 7)]
    raw = {"text": "ABC", "x0": 0, "top": 0, "x1": 3, "bottom": 1, "chars": chars}
    with pytest.raises(ValueError, match="mcid_noncontiguous"):
        _sanitize_words([raw], raw_chars=chars)


def test_split_rejects_missing_source_char_and_mutated_literal() -> None:
    chars = [_raw_char("A", 0, 7), _raw_char("B", 1, 8)]
    raw = {"text": "AB", "x0": 0, "top": 0, "x1": 2, "bottom": 1, "chars": chars}
    with pytest.raises(ValueError, match="source_char_missing"):
        _sanitize_words([raw], raw_chars=chars[:1])
    mutated = dict(raw, text="AX")
    with pytest.raises(ValueError, match="literal_mismatch"):
        _sanitize_words([mutated], raw_chars=chars)
    mixed = [_raw_char("A", 0, 7), _raw_char("B", 1)]
    with pytest.raises(ValueError, match="mcid_missing"):
        _sanitize_words([dict(raw, chars=mixed)], raw_chars=mixed)


def test_words_cannot_claim_one_page_source_char_twice() -> None:
    chars = [_raw_char("A", 0, 7), _raw_char("B", 1, 8)]
    first = {"text": "AB", "x0": 0, "top": 0, "x1": 2, "bottom": 1, "chars": chars}
    second = {"text": "A", "x0": 0, "top": 0, "x1": 1, "bottom": 1, "chars": chars[:1]}
    with pytest.raises(ValueError, match="duplicate_claim"):
        _sanitize_words([first, second], raw_chars=chars)


def test_nonblank_tagged_page_char_cannot_remain_unclaimed() -> None:
    chars = [_raw_char("A", 0, 7), _raw_char("B", 1, 8)]
    raw = {"text": "A", "x0": 0, "top": 0, "x1": 1, "bottom": 1, "chars": chars[:1]}
    with pytest.raises(ValueError, match="source_char_unclaimed"):
        _sanitize_words([raw], raw_chars=chars)


def _source_table(rows: int, columns: int, *, mcid_start: int = 1):
    chars = []
    ordinal = 0
    mcid = mcid_start
    for row in range(rows):
        for column in range(columns):
            ordinal += 1
            text = f"h{column + 1}" if row == 0 else f"r{row}c{column + 1}"
            if rows == 6 and columns == 32 and row > 0 and column == 0:
                text = TRADE_IDS[row - 1]
            chars.append(
                {
                    "parser_ordinal": ordinal,
                    "text": text,
                    "bbox": [column * 10 + 1, row * 10 + 2, column * 10 + 7, row * 10 + 8],
                    "mcid": mcid,
                    "tag": "P",
                }
            )
            mcid += 1
    lines = [
        {"bbox": [0, row * 10, columns * 10, row * 10], "object_type": "line"}
        for row in range(rows + 1)
    ]
    return chars, lines, [0, 0, columns * 10, rows * 10]


def test_grid_shape_matrix_preserves_rows_cells_and_five_trade_literals() -> None:
    tables = []
    next_mcid = 1
    for rows, columns in TABLE_SHAPES:
        chars, lines, bbox = _source_table(rows, columns, mcid_start=next_mcid)
        next_mcid += rows * columns
        candidate = reconstruct_mcid_grid(
            chars=chars, vector_lines=lines, rects=[], region_bbox=bbox
        )
        tables.append((candidate, chars))

    assert len(tables) == 1
    assert sum(table[0]["rows_total"] for table in tables) == 6
    assert sum(table[0]["cells_total"] for table in tables) == 192
    first, source_chars = tables[0]
    assert (first["rows_total"], first["columns_total"]) == (6, 32)
    by_ordinal = {item["parser_ordinal"]: item["text"] for item in source_chars}
    first_column = [
        by_ordinal[cell["char_parser_ordinals"][0]]
        for cell in first["cell_inventory"]
        if cell["column_ordinal"] == 1 and cell["row_ordinal"] > 1
    ]
    assert first_column == TRADE_IDS
    covered = [
        ordinal
        for cell in first["cell_inventory"]
        for ordinal in cell["char_parser_ordinals"]
    ]
    assert sorted(covered) == list(range(1, 193))


def test_non_mcid_source_cannot_claim_tagged_grid() -> None:
    chars, lines, bbox = _source_table(2, 2)
    for char in chars:
        char["mcid"] = None
    with pytest.raises(PdfSourceBoundGridError, match="mcid_missing"):
        reconstruct_mcid_grid(chars=chars, vector_lines=lines, rects=[], region_bbox=bbox)


def test_overlapping_header_partition_fails_closed() -> None:
    chars, lines, bbox = _source_table(2, 2)
    chars[0]["bbox"] = [1, 2, 16, 8]
    chars[1]["bbox"] = [10, 2, 17, 8]
    with pytest.raises(PdfSourceBoundGridError, match="header_partition_ambiguous"):
        reconstruct_mcid_grid(chars=chars, vector_lines=lines, rects=[], region_bbox=bbox)


def test_empty_cells_are_explicit_and_do_not_break_exact_char_coverage() -> None:
    chars, lines, bbox = _source_table(3, 3)
    chars = [item for item in chars if not (item["text"] == "r1c2")]
    candidate = reconstruct_mcid_grid(chars=chars, vector_lines=lines, rects=[], region_bbox=bbox)
    empty = [
        cell for cell in candidate["cell_inventory"]
        if cell["row_ordinal"] == 2 and cell["column_ordinal"] == 2
    ]
    assert len(empty) == 1
    assert empty[0]["char_parser_ordinals"] == []
    covered = {
        ordinal
        for cell in candidate["cell_inventory"]
        for ordinal in cell["char_parser_ordinals"]
    }
    assert covered == {item["parser_ordinal"] for item in chars}


def test_one_mcid_cannot_cross_source_rows_or_disconnected_columns() -> None:
    chars, lines, bbox = _source_table(3, 3)
    chars[6]["mcid"] = chars[0]["mcid"]
    with pytest.raises(PdfSourceBoundGridError, match="row_partition_ambiguous"):
        reconstruct_mcid_grid(chars=chars, vector_lines=lines, rects=[], region_bbox=bbox)
    chars, lines, bbox = _source_table(2, 3)
    chars[2]["mcid"] = chars[0]["mcid"]
    with pytest.raises(PdfSourceBoundGridError, match="column_partition_ambiguous"):
        reconstruct_mcid_grid(chars=chars, vector_lines=lines, rects=[], region_bbox=bbox)


def test_merged_or_empty_header_cannot_collapse_distinct_body_groups() -> None:
    chars, lines, bbox = _source_table(2, 3)
    chars[0]["bbox"] = [1, 2, 8, 8]
    chars[1].update(bbox=[10, 2, 17, 8], mcid=chars[0]["mcid"])
    chars[2]["bbox"] = [21, 2, 28, 8]
    chars[3]["bbox"] = [1, 12, 8, 18]
    chars[4]["bbox"] = [10, 12, 17, 18]
    chars[5]["bbox"] = [21, 12, 28, 18]
    with pytest.raises(PdfSourceBoundGridError, match="cell_group_partition_ambiguous"):
        reconstruct_mcid_grid(chars=chars, vector_lines=lines, rects=[], region_bbox=bbox)


def test_distinct_connected_mcid_groups_cannot_be_silently_merged() -> None:
    chars, lines, bbox = _source_table(2, 2)
    extra = dict(chars[2])
    extra.update(parser_ordinal=5, text="x", bbox=[7.5, 12, 8.5, 18], mcid=99)
    chars.append(extra)
    with pytest.raises(PdfSourceBoundGridError, match="cell_group_partition_ambiguous"):
        reconstruct_mcid_grid(chars=chars, vector_lines=lines, rects=[], region_bbox=bbox)


def test_real_tbank_given_complete_visually_verified_regions_preserves_all_grids() -> None:
    source = os.environ.get("BROKER_REPORTS_TBANK_CONTROL_PDF")
    if not source:
        controls = list(Path("C:/Users").glob("*/AppData/Local/Temp/1/issue317-tbank-*/tbank-control.pdf"))
        source = str(controls[0]) if controls else None
    assert source, "BROKER_REPORTS_TBANK_CONTROL_PDF must name the pinned public control"
    pdf_bytes = Path(source).read_bytes()
    assert hashlib.sha256(pdf_bytes).hexdigest() == "25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67"
    import pdfminer
    import pdfplumber

    # The 15 regions and shapes are independent upstream evidence from visual
    # inspection of page PNGs and table crops.  They do not prove autonomous
    # location or recovery of the table titles outside these boxes.
    locator_pages = [
        {
            "page_number": page,
            "status": "located" if regions else "located_no_tables",
            "regions": [
                {"region_ref": region_ref, "bbox_pdf_points": list(box)}
                for region_ref, box, _shape in regions
            ],
        }
        for page, regions in TBANK_VISUALLY_VERIFIED_REGIONS.items()
    ]
    result = PdfPlumberLayoutAdapter(
        pdfplumber_module=pdfplumber,
        pdfminer_module=pdfminer,
        config=PdfLayoutParserConfig(),
        requested_capability="table_candidates",
    ).parse(pdf_bytes, table_locator_pages=locator_pages)
    tables = [
        (int(page["page_number"]), table)
        for page in result.pages
        for table in page["table_candidate_inventory"]
    ]
    expected_shapes = [
        shape
        for regions in TBANK_VISUALLY_VERIFIED_REGIONS.values()
        for _region_ref, _box, shape in regions
    ]
    assert len(tables) == 15
    assert [
        (table["rows_total"], table["columns_total"])
        for _page, table in tables
    ] == expected_shapes
    assert sum(table["rows_total"] for _page, table in tables) == 50
    assert sum(table["cells_total"] for _page, table in tables) == 485
    cells = [cell for _page, table in tables for cell in table["cell_inventory"]]
    assert sum(bool(cell["char_parser_ordinals"]) for cell in cells) == 424
    assert sum(not cell["char_parser_ordinals"] for cell in cells) == 61
    claims = [
        (page, ordinal)
        for page, table in tables
        for ordinal in table["contributing_char_parser_ordinals"]
    ]
    assert len(claims) == 4709
    assert len(set(claims)) == 4709

    first = tables[0][1]
    page_chars = {
        item["parser_ordinal"]: item["text"] for item in result.pages[0]["char_inventory"]
    }
    actual_trade_ids = [
        "".join(page_chars[ordinal] for ordinal in cell["char_parser_ordinals"])
        for cell in first["cell_inventory"]
        if cell["column_ordinal"] == 1 and cell["row_ordinal"] > 1
    ]
    assert actual_trade_ids == TRADE_IDS
    quantities = [
        int("".join(page_chars[ordinal] for ordinal in cell["char_parser_ordinals"]))
        for cell in first["cell_inventory"]
        if cell["column_ordinal"] == 13 and cell["row_ordinal"] > 1
    ]
    assert sum(quantities) == 7
