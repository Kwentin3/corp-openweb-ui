from __future__ import annotations

import base64
import hashlib
import sys
from pathlib import Path

import fitz
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    CANONICAL_TABLE_REGION_POLICY_VERSION,
    CANONICAL_TABLE_REGION_SCHEMA,
    PdfTableRasterError,
    PdfTableRasterFactory,
)


def _contains(
    outer: list[float], inner: list[float], *, tolerance: float = 1.0
) -> bool:
    return (
        outer[0] <= inner[0] + tolerance
        and outer[1] <= inner[1] + tolerance
        and outer[2] >= inner[2] - tolerance
        and outer[3] >= inner[3] - tolerance
    )


def _overlaps(left: list[float], right: list[float]) -> bool:
    return not (
        left[2] <= right[0]
        or right[2] <= left[0]
        or left[3] <= right[1]
        or right[3] <= left[1]
    )


def _insert_row(page: fitz.Page, y: float, label: str, value: str) -> None:
    page.insert_text((22, y), label, fontsize=8)
    page.insert_text((164, y), value, fontsize=8)
    page.draw_line((20, y + 3), (190, y + 3), color=(0, 0, 0), width=0.4)


def _fixture_pdf(
    *, cropbox_offset: bool = False
) -> tuple[bytes, dict[str, list[float]]]:
    document = fitz.open()
    page = document.new_page(width=240, height=340)
    if cropbox_offset:
        page.set_cropbox(fitz.Rect(20, 20, 220, 320))
    page.insert_text((20, 20), "Quarterly results", fontsize=12)
    page.insert_text((92, 39), "Year ended", fontsize=8)
    page.insert_text((92, 50), "2026     2025", fontsize=8)
    page.draw_rect(fitz.Rect(20, 58, 190, 151), color=(0, 0, 0), width=0.8)
    page.insert_text((21, 68), "Description", fontsize=8)
    page.insert_text((160, 68), "Amount", fontsize=8)
    _insert_row(page, 82, "Opening balance", "100")
    _insert_row(page, 101, "Movement", "25")
    _insert_row(page, 120, "Closing total", "125")
    page.insert_text((20, 164), "(1)", fontsize=7)
    page.insert_text((34, 164), "Totals may not foot due to rounding.", fontsize=7)
    page.insert_text((20, 177), "(2)", fontsize=7)
    page.insert_text((34, 177), "Amount is presented in thousands.", fontsize=7)
    page.insert_text((20, 217), "Neighbor table", fontsize=11)
    page.draw_rect(fitz.Rect(20, 228, 190, 258), color=(0, 0, 0), width=0.8)
    page.insert_text((25, 243), "Foreign row", fontsize=8)
    page.insert_text((20, 291), "Issuer footer", fontsize=7)
    page.insert_text((184, 291), "7", fontsize=7)
    regions = {
        "title": [19, 9, 112, 23],
        "multilevel_header": [90, 29, 176, 53],
        "left_edge": [19, 57, 35, 151],
        "right_edge": [160, 57, 191, 151],
        "total": [20, 111, 190, 125],
        "notes": [19, 153, 188, 181],
        "neighbor": [19, 207, 191, 259],
        "footer": [19, 280, 193, 294],
    }
    data = document.tobytes(deflate=True)
    document.close()
    return data, regions


def _render(
    pdf_bytes: bytes,
    *,
    candidate_bbox: list[float],
    candidate_page_bbox: list[float],
    strategy: str = "ruled_lines_v0",
) -> dict:
    return (
        PdfTableRasterFactory()
        .create()
        .render_table_candidate(
            pdf_bytes=pdf_bytes,
            pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            document_ref="fixture-document",
            page_number=1,
            candidate_ref="fixture-candidate",
            candidate_bbox=candidate_bbox,
            candidate_page_bbox=candidate_page_bbox,
            candidate_strategy_ref=strategy,
            detector_contract_version="fixture-detector-v1",
            detector_identity={"kind": "synthetic_contract_fixture"},
            dpi=150,
        )
    )


def test_canonical_region_includes_complete_table_and_notes_but_excludes_neighbors():
    pdf_bytes, regions = _fixture_pdf()
    first = _render(
        pdf_bytes,
        candidate_bbox=[20, 58, 190, 151],
        candidate_page_bbox=[0, 0, 240, 340],
    )
    second = _render(
        pdf_bytes,
        candidate_bbox=[20, 58, 190, 151],
        candidate_page_bbox=[0, 0, 240, 340],
    )
    manifest = first["manifest"]
    region = manifest["table_region"]
    assert first == second
    assert region["schema_version"] == CANONICAL_TABLE_REGION_SCHEMA
    assert region["policy_version"] == CANONICAL_TABLE_REGION_POLICY_VERSION
    assert region["status"] == "CROP_CLEAN"
    for name in (
        "title",
        "multilevel_header",
        "left_edge",
        "right_edge",
        "total",
        "notes",
    ):
        assert _contains(region["resolved_bbox"], regions[name]), name
    for name in ("neighbor", "footer"):
        assert not _overlaps(region["resolved_bbox"], regions[name]), name
    assert manifest["rendered_bbox"] == region["resolved_bbox"]
    assert (
        hashlib.sha256(base64.b64decode(first["private_png_base64"])).hexdigest()
        == manifest["png_sha256"]
    )


def test_adjacent_table_and_rounding_edge_do_not_enter_region():
    document = fitz.open()
    page = document.new_page(width=200, height=220)
    page.insert_text((10.2, 20.1), "Wide table", fontsize=10)
    page.draw_rect(fitz.Rect(0.2, 40.1, 98.8, 140.4), color=(0, 0, 0), width=0.5)
    page.insert_text((1.0, 55), "Left edge", fontsize=8)
    page.insert_text((74, 55), "99", fontsize=8)
    page.draw_rect(fitz.Rect(105, 40, 199.7, 140), color=(0, 0, 0), width=0.5)
    page.insert_text((110, 55), "Adjacent", fontsize=8)
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[0.2, 40.1, 98.8, 140.4],
        candidate_page_bbox=[0, 0, 200, 220],
    )
    bbox = rendered["manifest"]["table_region"]["resolved_bbox"]
    assert _contains(bbox, [0.2, 19.0, 98.8, 140.4])
    assert bbox[2] < 105


def test_header_expansion_does_not_cross_separate_ruled_table_boundary():
    document = fitz.open()
    page = document.new_page(width=220, height=220)
    page.draw_rect(fitz.Rect(20, 20, 200, 45), color=(0, 0, 0), width=0.7)
    page.insert_text((94, 36), "N/A", fontsize=8)
    page.draw_rect(fitz.Rect(20, 50, 200, 150), color=(0, 0, 0), width=0.7)
    page.insert_text((24, 64), "Primary table", fontsize=8)
    page.insert_text((24, 84), "First row", fontsize=8)
    page.insert_text((170, 84), "10", fontsize=8)
    page.insert_text((24, 124), "Total", fontsize=8)
    page.insert_text((170, 124), "10", fontsize=8)
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 50, 200, 150],
        candidate_page_bbox=[0, 0, 220, 220],
    )
    region = rendered["manifest"]["table_region"]
    assert region["resolved_bbox"][1] >= 48
    assert "separate_ruled_region_excluded" in region["reason_codes"]


def test_standard_statement_title_crosses_its_own_header_rule():
    document = fitz.open()
    page = document.new_page(width=260, height=260)
    page.insert_text(
        (46, 35), "CONSOLIDATED STATEMENTS OF INCOME", fontsize=10
    )
    page.insert_text(
        (35, 51),
        "(In millions of dollars, except for share and per share amounts)",
        fontsize=6,
    )
    page.draw_line((150, 66), (235, 66), color=(0, 0, 0), width=0.7)
    page.insert_text((168, 78), "Year Ended", fontsize=8)
    page.insert_text((178, 91), "2025 2024", fontsize=8)
    for index in range(5):
        _insert_row(page, 114 + index * 22, f"Statement row {index}", str(index))
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 98, 240, 211],
        candidate_page_bbox=[0, 0, 260, 260],
        strategy="aligned_text_v0",
    )
    region = rendered["manifest"]["table_region"]
    assert _contains(region["resolved_bbox"], [46, 24, 235, 38])
    assert _contains(region["resolved_bbox"], [35, 43, 235, 54])
    assert "table_header_or_title_attached" in region["reason_codes"]


def test_standard_financial_statement_note_is_attached_without_numeric_marker():
    document = fitz.open()
    page = document.new_page(width=220, height=220)
    page.draw_rect(fitz.Rect(20, 40, 200, 130), color=(0, 0, 0), width=0.7)
    page.insert_text((24, 58), "Statement table", fontsize=8)
    page.insert_text((24, 82), "First row", fontsize=8)
    page.insert_text((170, 82), "10", fontsize=8)
    page.insert_text((24, 118), "Total", fontsize=8)
    page.insert_text((170, 118), "10", fontsize=8)
    page.insert_text(
        (20, 145),
        "See accompanying notes to the financial statements.",
        fontsize=7,
    )
    page.insert_text((20, 196), "Issuer footer", fontsize=7)
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 40, 200, 130],
        candidate_page_bbox=[0, 0, 220, 220],
    )
    bbox = rendered["manifest"]["table_region"]["resolved_bbox"]
    assert _contains(bbox, [20, 137, 200, 148])
    assert bbox[3] < 190


def test_standard_note_intersecting_candidate_edge_survives_component_gap():
    document = fitz.open()
    page = document.new_page(width=280, height=320)
    page.insert_text((20, 35), "CONSOLIDATED BALANCE SHEETS", fontsize=10)
    for index in range(4):
        _insert_row(page, 70 + index * 20, f"Balance row {index}", str(index))
    page.insert_text(
        (35, 205),
        "The accompanying notes are an integral part of these financial statements.",
        fontsize=7,
    )
    page.insert_text((130, 292), "48", fontsize=7)
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 55, 260, 208],
        candidate_page_bbox=[0, 0, 280, 320],
        strategy="aligned_text_v0",
    )
    region = rendered["manifest"]["table_region"]
    assert _contains(region["resolved_bbox"], [35, 196, 255, 208])
    assert region["resolved_bbox"][3] < 285
    assert "attached_notes_included" in region["reason_codes"]


def test_note_continuation_stops_before_foreign_prose_block():
    document = fitz.open()
    page = document.new_page(width=240, height=300)
    page.draw_rect(fitz.Rect(20, 40, 220, 150), color=(0, 0, 0), width=0.7)
    _insert_row(page, 70, "Revenue", "100")
    _insert_row(page, 115, "Total", "100")
    page.insert_text((20, 164), "(1)", fontsize=7)
    page.insert_text((34, 164), "Amounts are presented in millions", fontsize=7)
    page.insert_text(
        (20, 182),
        "Management discusses market conditions and operating trends below.",
        fontsize=7,
    )
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 40, 220, 150],
        candidate_page_bbox=[0, 0, 240, 300],
        strategy="aligned_text_v0",
    )
    bbox = rendered["manifest"]["table_region"]["resolved_bbox"]
    assert _contains(bbox, [20, 157, 215, 167])
    assert bbox[3] < 180


def test_aligned_rows_in_separate_text_blocks_are_not_trimmed_as_prose():
    document = fitz.open()
    page = document.new_page(width=300, height=420)
    page.insert_text((20, 24), "Statement of operations", fontsize=11)
    for index in range(14):
        y = 55 + index * 20
        page.insert_text(
            (20, y),
            f"Long financial statement line item number {index}",
            fontsize=7,
        )
        page.insert_text((250, y), str(100 + index), fontsize=7)
    page.insert_text((20, 347), "See notes to financial statements.", fontsize=7)
    page.insert_text((145, 395), "81", fontsize=7)
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 42, 280, 400],
        candidate_page_bbox=[0, 0, 300, 420],
        strategy="aligned_text_v0",
    )
    region = rendered["manifest"]["table_region"]
    assert _contains(region["resolved_bbox"], [20, 48, 270, 318])
    assert region["resolved_bbox"][3] < 390
    assert "foreign_prose_barrier_trimmed" not in region["reason_codes"]
    assert "page_footer_excluded" in region["reason_codes"]


def test_isolated_page_number_and_issuer_footer_band_is_excluded():
    document = fitz.open()
    page = document.new_page(width=260, height=340)
    for index in range(12):
        _insert_row(page, 45 + index * 20, f"Statement row {index}", str(index))
    page.insert_text(
        (20, 292), "See accompanying notes to the financial statements.", fontsize=7
    )
    page.insert_text((20, 330), "45", fontsize=7)
    page.insert_text((178, 330), "Issuer Group Inc.", fontsize=7)
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 30, 240, 338],
        candidate_page_bbox=[0, 0, 260, 340],
        strategy="aligned_text_v0",
    )
    region = rendered["manifest"]["table_region"]
    assert _contains(region["resolved_bbox"], [20, 285, 238, 295])
    assert region["resolved_bbox"][3] < 322
    assert "page_footer_excluded" in region["reason_codes"]


def test_narrative_introduction_blocks_a_following_neighbor_table():
    document = fitz.open()
    page = document.new_page(width=300, height=560)
    for index in range(16):
        _insert_row(page, 45 + index * 20, f"Primary row {index}", str(index))
    page.insert_text(
        (20, 382),
        "Management discusses the reporting category and related market conditions.",
        fontsize=7,
    )
    page.insert_text(
        (20, 396),
        "The separate schedule is provided for additional contextual disclosure.",
        fontsize=7,
    )
    page.insert_text(
        (20, 410),
        "Readers should consider that schedule independently from this table.",
        fontsize=7,
    )
    for index in range(4):
        _insert_row(page, 446 + index * 20, f"Neighbor row {index}", str(index))
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 30, 280, 520],
        candidate_page_bbox=[0, 0, 300, 560],
        strategy="aligned_text_v0",
    )
    region = rendered["manifest"]["table_region"]
    assert _contains(region["resolved_bbox"], [20, 38, 190, 348])
    assert region["resolved_bbox"][3] < 382
    assert "foreign_prose_barrier_trimmed" in region["reason_codes"]


def test_header_expansion_walks_multilevel_bands_without_crossing_prose():
    document = fitz.open()
    page = document.new_page(width=260, height=300)
    page.insert_text(
        (20, 20),
        "The following discussion describes unrelated market conditions.",
        fontsize=7,
    )
    page.insert_text((20, 48), "Consolidated Statement", fontsize=12)
    page.insert_text((150, 72), "Year ended", fontsize=8)
    page.insert_text((150, 91), "2026 2025", fontsize=8)
    page.insert_text((20, 111), "Description", fontsize=8)
    page.insert_text((205, 111), "Amount", fontsize=8)
    for index in range(5):
        _insert_row(page, 140 + index * 22, f"Row {index}", str(index))
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 126, 230, 240],
        candidate_page_bbox=[0, 0, 260, 300],
        strategy="aligned_text_v0",
    )
    bbox = rendered["manifest"]["table_region"]["resolved_bbox"]
    assert _contains(bbox, [20, 37, 230, 235])
    assert bbox[1] > 22


def test_cropbox_coordinate_offset_is_applied_once():
    pdf_bytes, regions = _fixture_pdf(cropbox_offset=True)
    rendered = _render(
        pdf_bytes,
        candidate_bbox=[40, 78, 210, 171],
        candidate_page_bbox=[0, 0, 240, 340],
    )
    region = rendered["manifest"]["table_region"]
    assert region["coordinate_transform"]["kind"] == "media_to_cropbox_translation"
    assert region["coordinate_transform"]["translate_x"] == -20.0
    assert region["coordinate_transform"]["translate_y"] == -20.0
    assert _contains(region["resolved_bbox"], regions["left_edge"])
    assert not _overlaps(region["resolved_bbox"], regions["neighbor"])


def test_rotated_media_coordinate_candidate_fails_closed():
    document = fitz.open()
    page = document.new_page(width=240, height=340)
    page.insert_text((20, 60), "Rotated table row 100", fontsize=8)
    page.set_rotation(90)
    data = document.tobytes(deflate=True)
    document.close()
    with pytest.raises(PdfTableRasterError) as captured:
        _render(
            data,
            candidate_bbox=[20, 40, 200, 100],
            candidate_page_bbox=[0, 0, 240, 340],
        )
    assert (
        captured.value.code == "pdf_table_raster_rotated_media_coordinate_unsupported"
    )
    assert captured.value.crop_status == "CROP_BLOCKED"


def test_large_vertical_gap_inside_candidate_selects_single_table_component():
    document = fitz.open()
    page = document.new_page(width=220, height=320)
    page.insert_text((20, 18), "Primary table", fontsize=11)
    page.draw_rect(fitz.Rect(20, 40, 200, 120), color=(0, 0, 0), width=0.7)
    _insert_row(page, 65, "Primary row", "1")
    _insert_row(page, 90, "Primary total", "1")
    page.insert_text((20, 190), "Foreign chart data", fontsize=11)
    page.draw_rect(fitz.Rect(20, 210, 200, 275), color=(0, 0, 0), width=0.7)
    page.insert_text((25, 230), "Foreign row 9", fontsize=8)
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 40, 200, 275],
        candidate_page_bbox=[0, 0, 220, 320],
        strategy="aligned_text_v0",
    )
    bbox = rendered["manifest"]["table_region"]["resolved_bbox"]
    assert _contains(bbox, [20, 17, 200, 120])
    assert bbox[3] < 190


def test_ambiguous_equal_components_fail_closed_without_png():
    document = fitz.open()
    page = document.new_page(width=220, height=320)
    for offset, label in ((20, "First table"), (180, "Second table")):
        page.insert_text((20, offset), label, fontsize=11)
        page.draw_rect(
            fitz.Rect(20, offset + 20, 200, offset + 100),
            color=(0, 0, 0),
            width=0.7,
        )
        page.insert_text((25, offset + 45), "Row 1 100", fontsize=8)
        page.insert_text((25, offset + 70), "Total 100", fontsize=8)
    data = document.tobytes(deflate=True)
    document.close()
    with pytest.raises(PdfTableRasterError) as captured:
        _render(
            data,
            candidate_bbox=[20, 0, 200, 300],
            candidate_page_bbox=[0, 0, 220, 320],
            strategy="aligned_text_v0",
        )
    assert captured.value.code == "pdf_table_raster_crop_ambiguous"
    assert captured.value.crop_status == "CROP_AMBIGUOUS"


def test_partial_top_line_is_expanded_to_its_complete_geometry():
    document = fitz.open()
    page = document.new_page(width=240, height=240)
    page.insert_text((20, 52), "Condensed Consolidated Balance Sheets", fontsize=10)
    page.insert_text((20, 76), "Assets", fontsize=8)
    page.insert_text((170, 76), "2025", fontsize=8)
    _insert_row(page, 98, "Cash", "100")
    _insert_row(page, 124, "Total assets", "100")
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 45, 210, 145],
        candidate_page_bbox=[0, 0, 240, 240],
        strategy="aligned_text_v0",
    )
    bbox = rendered["manifest"]["table_region"]["resolved_bbox"]
    assert _contains(bbox, [20, 40, 205, 55])


def test_contiguous_multiline_caption_above_ruled_grid_is_attached():
    document = fitz.open()
    page = document.new_page(width=280, height=300)
    page.insert_text(
        (20, 42),
        "The following table summarizes assets and liabilities measured at",
        fontsize=7,
    )
    page.insert_text((20, 52), "fair value on a recurring basis:", fontsize=7)
    page.draw_rect(fitz.Rect(20, 66, 260, 180), color=(0, 0, 0), width=0.7)
    page.insert_text((22, 82), "Description", fontsize=8)
    page.insert_text((210, 82), "Level 1", fontsize=8)
    _insert_row(page, 108, "Asset", "100")
    _insert_row(page, 146, "Total", "100")
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 66, 260, 180],
        candidate_page_bbox=[0, 0, 280, 300],
    )
    region = rendered["manifest"]["table_region"]
    assert _contains(region["resolved_bbox"], [20, 34, 260, 55])
    assert "table_header_or_title_attached" in region["reason_codes"]


def test_alphabetic_footnote_block_is_attached_and_following_prose_is_excluded():
    document = fitz.open()
    page = document.new_page(width=280, height=320)
    page.draw_rect(fitz.Rect(20, 50, 260, 170), color=(0, 0, 0), width=0.7)
    _insert_row(page, 88, "Asset", "100")
    _insert_row(page, 138, "Total", "100")
    page.insert_text((20, 184), "(a) Includes pledged collateral.", fontsize=7)
    page.insert_text((20, 197), "(b) Includes operating lease liabilities.", fontsize=7)
    page.insert_text(
        (20, 235),
        "Management discusses unrelated market conditions in this paragraph.",
        fontsize=7,
    )
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 50, 260, 170],
        candidate_page_bbox=[0, 0, 280, 320],
    )
    region = rendered["manifest"]["table_region"]
    assert _contains(region["resolved_bbox"], [20, 177, 220, 200])
    assert region["resolved_bbox"][3] < 230
    assert "attached_notes_included" in region["reason_codes"]


def test_repeated_numeric_grid_completes_rows_below_candidate_edge():
    document = fitz.open()
    page = document.new_page(width=280, height=340)
    page.insert_text((20, 30), "Statement of income", fontsize=11)
    page.insert_text((205, 55), "2025", fontsize=8)
    for index in range(7):
        y = 78 + index * 22
        page.insert_text((20, y), f"Statement row {index}", fontsize=8)
        page.insert_text((210, y), str(100 + index), fontsize=8)
    page.insert_text((20, 232), "Total", fontsize=8)
    page.insert_text((210, 232), "721", fontsize=8)
    page.insert_text((20, 252), "(a) Amounts are in millions.", fontsize=7)
    page.insert_text(
        (20, 292),
        "Management discusses unrelated market conditions for 2025.",
        fontsize=7,
    )
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 45, 250, 190],
        candidate_page_bbox=[0, 0, 280, 340],
        strategy="aligned_text_v0",
    )
    region = rendered["manifest"]["table_region"]
    assert _contains(region["resolved_bbox"], [20, 218, 225, 235])
    assert _contains(region["resolved_bbox"], [20, 243, 180, 255])
    assert region["resolved_bbox"][3] < 285
    assert "table_body_tail_attached" in region["reason_codes"]
    assert "attached_notes_included" in region["reason_codes"]


def test_isolated_page_header_is_excluded_without_dropping_table_title():
    document = fitz.open()
    page = document.new_page(width=260, height=340)
    page.insert_text((20, 22), "2025 Annual Report | Example Bancorp", fontsize=7)
    page.insert_text((20, 70), "Consolidated Statements of Cash Flows", fontsize=11)
    page.insert_text((170, 92), "2025 2024", fontsize=8)
    for index in range(8):
        _insert_row(page, 118 + index * 20, f"Cash flow row {index}", str(index))
    data = document.tobytes(deflate=True)
    document.close()
    rendered = _render(
        data,
        candidate_bbox=[20, 12, 240, 290],
        candidate_page_bbox=[0, 0, 260, 340],
        strategy="aligned_text_v0",
    )
    region = rendered["manifest"]["table_region"]
    assert region["resolved_bbox"][1] > 30
    assert _contains(region["resolved_bbox"], [20, 58, 235, 74])
    assert "page_header_excluded" in region["reason_codes"]


def test_implementation_has_no_doc15_identity_or_fixed_coordinate_exceptions():
    source = (ROOT / "broker_reports_gate1" / "pdf_table_raster.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "ACORNS_T",
        "JEFFERIES_T",
        "LPL_T",
        "OPPENHEIMER_T",
        "STONEX_T",
        "TRADEWEB_T",
        "acorns_2025",
        "jefferies_2024",
        "page_number ==",
    ):
        assert forbidden not in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
