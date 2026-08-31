from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest

from broker_reports_gate1.contracts import (
    PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3,
    sha256_json,
)
from broker_reports_gate1.pdf_layout import (
    PdfLayoutParserConfig,
    PdfPlumberLayoutAdapter,
    _sanitize_char,
    _sanitize_word,
    _sanitize_words,
    _source_grid_raster_reason,
)
from broker_reports_gate1.pdf_source_bound_grid import (
    PDF_SOURCE_GRID_POLICY_VERSION,
    PdfSourceBoundGridError,
    _horizontal_boundaries,
    _source_frame_x,
    reconstruct_page_source_grids,
)
from broker_reports_gate1.pdf_table_locator import (
    PdfTableLocatorProjectionConfig,
    PdfTableLocatorProjectionFactory,
)
from broker_reports_gate1.inputs import FileInput
from broker_reports_gate1.normalizer import Gate1Normalizer


TBANK_SHA256 = "25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67"
TBANK_BYTES = 639_417
TBANK_URL = "https://cdn.tbank.ru/static/documents/7b9ccdee-5a02-4ed6-9499-c76082cd8d30.pdf"
FIXTURE = Path(__file__).parent / "fixtures" / "issue317_candidate_c_tbank.safe.json"
RESPONSE_SHA256 = {
    1: "f6fea8282095341b9b8aa919e69ca8f7340ba094d7e7fb422886a4f7eeb49a1d",
    2: "5507726981d1d69f4a1504332ea4b0d939cb264f791d16bf5d82b5c808de8aee",
    3: "f88e5fb33c9480d8c5d0b2f42af453de9f2a98ba341cdb9dea4ed0a8274d9a75",
    4: "65b5aeca8e84381f40241a2460d4419040ba304988ef2186e048e31e72e0642b",
}
PROVIDER_TEXT_SHA256 = {
    1: "64120864b76375b6c45201a3940875a138200b8fd04d51698fe29028f2af0570",
    2: "01d92902f31f9af97fbb23aa1eaf6d6116c3f54e4d89053fc1f844ca2815c72e",
    3: "8a6ebc6dbf4140f39261152dc36573efc9d1b240bd1a55af8b2896961d758b6e",
    4: "bb4fb5fd5c2386aeed39c96ab7322e327ebcabc4b82189e249773817ef47711a",
}
PROVIDER_RESPONSE_HASH = {
    1: "4dd28af0b8a023fcf9cd826cabad49ab6c47859f280bc0539cf8264173d1e5d5",
    2: "19000bf1d0637cf8b7a00df86b009c570e1828fe642e68bec3ab59e30eda4ee7",
    3: "70c3e0e8e66de7582eb44c3b56b4756de8645aca34771b68316d59e98217a47f",
    4: "f7698aac5960f8785c5e8c62e37184d0bebc75d8a04fadd681895e441589bfe5",
}
TBANK_TAGGED_V1_ENVELOPE_SHA256 = (
    "7e59efb204168beaf9303ebf6070af7e1f83c584c172747cdbfd099becbaf155"
)
TBANK_SHAPES = [
    (6, 32),
    (1, 32),
    (1, 32),
    (2, 28),
    (4, 7),
    (4, 7),
    (2, 12),
    (1, 8),
    (1, 7),
    (2, 8),
    (1, 8),
    (1, 6),
    (1, 2),
    (2, 2),
    (21, 2),
]


def _raw_char(text: str, x0: float, mcid=None) -> dict:
    return {
        "text": text,
        "x0": x0,
        "top": 0,
        "x1": x0 + 1,
        "bottom": 1,
        "fontname": "F",
        "size": 10,
        "upright": True,
        "mcid": mcid,
        "tag": "P" if mcid is not None else None,
    }


def _raw_word(chars: list[dict]) -> dict:
    return {
        "text": "".join(item["text"] for item in chars),
        "x0": chars[0]["x0"],
        "top": 0,
        "x1": chars[-1]["x1"],
        "bottom": 1,
        "direction": "ltr",
        "chars": chars,
    }


def test_untagged_word_keeps_v1_shape() -> None:
    char = _raw_char("A", 0)
    raw = _raw_word([char])
    assert _sanitize_words([raw], raw_chars=[char]) == [_sanitize_word(raw, 1)]


def test_tagged_input_keeps_established_v1_bytes_when_v3_is_off() -> None:
    char = _raw_char("A", 0, 10)
    assert _sanitize_char(char, 1) == {
        "parser_ordinal": 1,
        "text": "A",
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "fontname": "F",
        "size": 10.0,
        "upright": True,
        "direction": "",
        "duplicate_of_parser_ordinal": None,
    }
    assert _sanitize_words([_raw_word([char])], raw_chars=[char]) == [
        {
            "parser_ordinal": 1,
            "text": "A",
            "bbox": [0.0, 0.0, 1.0, 1.0],
            "direction": "ltr",
            "upright": True,
            "char_parser_ordinals": [],
        }
    ]


def test_tagged_pdfplumber_word_splits_only_contiguous_mcid_runs() -> None:
    chars = [_raw_char("A", 0, 10), _raw_char("B", 1, 11)]
    assert _sanitize_words(
        [_raw_word(chars)], raw_chars=chars, preserve_source_tags=True
    ) == [
        {
            "parser_ordinal": 1,
            "text": "A",
            "bbox": [0.0, 0.0, 1.0, 1.0],
            "direction": "ltr",
            "upright": True,
            "char_parser_ordinals": [1],
            "mcid_refs": ["10"],
        },
        {
            "parser_ordinal": 2,
            "text": "B",
            "bbox": [1.0, 0.0, 2.0, 1.0],
            "direction": "ltr",
            "upright": True,
            "char_parser_ordinals": [2],
            "mcid_refs": ["11"],
        },
    ]


@pytest.mark.parametrize(
    ("chars", "words", "code"),
    [
        (
            [_raw_char("A", 0, 1), _raw_char("B", 1, 2), _raw_char("A", 2, 1)],
            None,
            "pdf_layout_tagged_word_mcid_noncontiguous",
        ),
        (
            [_raw_char("A", 0, 1), _raw_char("B", 1, 2)],
            [],
            "pdf_layout_tagged_word_source_char_unclaimed",
        ),
    ],
)
def test_tagged_word_ambiguous_or_unclaimed_source_fails_closed(
    chars: list[dict], words: list[dict] | None, code: str
) -> None:
    source_words = [_raw_word(chars)] if words is None else words
    with pytest.raises(ValueError, match=code):
        _sanitize_words(
            source_words, raw_chars=chars, preserve_source_tags=True
        )


def test_source_grid_requires_a_source_bound_header() -> None:
    with pytest.raises(
        PdfSourceBoundGridError, match="pdf_source_grid_header_scope_unproven"
    ):
        reconstruct_page_source_grids(
            chars=[],
            words=[],
            vector_lines=[],
            rects=[],
            regions=[{"bbox_pdf_points": [0, 0, 10, 10]}],
            page_bbox=[0, 0, 100, 100],
        )


def _source_char(
    ordinal: int, text: str, bbox: list[float], mcid: int
) -> dict:
    return {
        "parser_ordinal": ordinal,
        "text": text,
        "bbox": bbox,
        "mcid": str(mcid),
    }


def _source_word(char: dict) -> dict:
    return {
        "parser_ordinal": int(char["parser_ordinal"]),
        "text": char["text"],
        "bbox": char["bbox"],
        "char_parser_ordinals": [int(char["parser_ordinal"])],
    }


def _grid_region(
    *, top: float, bottom: float, title_bbox: list[float] | None
) -> dict:
    return {
        "bbox_pdf_points": [0, top, 100, bottom],
        "header_bbox_pdf_points": [0, top, 100, top + 10],
        "title_bbox_pdf_points": title_bbox,
    }


def _grid_rects(top: float, bottom: float) -> list[dict]:
    return [
        {"bbox": [0, top, 100, top + 10]},
        {"bbox": [0, top + 10, 100, bottom]},
    ]


def _grid_chars(start: int, top: float) -> list[dict]:
    return [
        _source_char(start, "A", [10, top + 1, 11, top + 2], start),
        _source_char(start + 1, "B", [60, top + 1, 61, top + 2], start + 1),
        _source_char(start + 2, "1", [10, top + 11, 11, top + 12], start + 2),
        _source_char(start + 3, "2", [60, top + 11, 61, top + 12], start + 3),
    ]


def test_source_grid_rejects_nonnull_title_without_source_binding() -> None:
    chars = _grid_chars(1, 10)
    with pytest.raises(
        PdfSourceBoundGridError,
        match="pdf_source_grid_title_binding_unproven",
    ):
        reconstruct_page_source_grids(
            chars=chars,
            words=[_source_word(char) for char in chars],
            vector_lines=[],
            rects=_grid_rects(10, 30),
            regions=[
                _grid_region(top=10, bottom=30, title_bbox=[0, 2, 100, 8])
            ],
            page_bbox=[0, 0, 100, 100],
        )


def test_source_grid_rejects_title_claimed_by_two_instances() -> None:
    title = _source_char(1, "T", [10, 2, 11, 3], 1)
    first = _grid_chars(2, 10)
    second = _grid_chars(6, 50)
    chars = [title, *first, *second]
    regions = [
        _grid_region(top=10, bottom=30, title_bbox=[0, 0, 100, 8]),
        _grid_region(top=50, bottom=70, title_bbox=[0, 0, 100, 8]),
    ]
    with pytest.raises(
        PdfSourceBoundGridError,
        match="pdf_source_grid_title_owner_ambiguous",
    ):
        reconstruct_page_source_grids(
            chars=chars,
            words=[_source_word(char) for char in chars],
            vector_lines=[],
            rects=[*_grid_rects(10, 30), *_grid_rects(50, 70)],
            regions=regions,
            page_bbox=[0, 0, 100, 100],
        )


def test_source_frame_ignores_shifted_neighbor_rules() -> None:
    aligned = [{"bbox": [0, y, 100, y + 1]} for y in (10, 20)]
    neighbor = [{"bbox": [20, y, 120, y + 1]} for y in (30, 40, 50)]
    assert _source_frame_x(
        hint=[0, 5, 100, 60],
        header=[0, 10, 100, 20],
        vector_lines=[],
        rects=[*aligned, *neighbor],
    ) == (0.0, 100.0)
    assert 30.0 not in _horizontal_boundaries(
        frame_left=0,
        frame_right=100,
        vector_lines=[],
        rects=[*aligned, *neighbor],
    )


class _ImagePage:
    def __init__(self, images: list[dict]) -> None:
        self.images = images


class _UnavailableImagePage:
    @property
    def images(self):
        raise RuntimeError("image inventory unavailable")


@pytest.mark.parametrize(
    ("image", "expected_code"),
    [
        (
            {"srcsize": (2, 2), "x0": 20, "top": 0, "x1": 30, "bottom": 10},
            None,
        ),
        (
            {"srcsize": (2, 2), "x0": 10, "top": 0, "x1": 20, "bottom": 10},
            None,
        ),
        (
            {"srcsize": (2, 2), "x0": 9, "top": 0, "x1": 20, "bottom": 10},
            "pdf_source_grid_raster_image_intersection_unsupported",
        ),
        (
            {
                "srcsize": (2, 2),
                "x0": 1,
                "top": 1,
                "x1": 1.01,
                "bottom": 1.01,
            },
            "pdf_source_grid_raster_image_intersection_unsupported",
        ),
        (
            {"srcsize": (1, 1), "x0": 0, "top": 0, "x1": 10, "bottom": 10},
            None,
        ),
        (
            {"srcsize": [1, 1], "x0": 0, "top": 0, "x1": 10, "bottom": 10},
            None,
        ),
        (
            {"srcsize": (2, 2), "x0": 1, "top": 1, "x1": 1, "bottom": 2},
            "pdf_source_grid_image_bbox_invalid",
        ),
    ],
)
def test_v3_raster_capability_is_exact_and_fail_closed(
    image: dict, expected_code: str | None
) -> None:
    code = _source_grid_raster_reason(
        page=_ImagePage([image]),
        regions=[{"region_ref": "region-1", "bbox_pdf_points": [0, 0, 10, 10]}],
    )
    assert code == expected_code


def test_v3_raster_capability_bypasses_no_table_and_types_unavailable() -> None:
    page = _UnavailableImagePage()
    assert _source_grid_raster_reason(page=page, regions=[]) is None
    code = _source_grid_raster_reason(
        page=page,
        regions=[{"region_ref": "region-1", "bbox_pdf_points": [0, 0, 10, 10]}],
    )
    assert code == "pdf_source_grid_image_inventory_unavailable"
    assert _source_grid_raster_reason(
        page=_ImagePage([]),
        regions=[{"region_ref": "region-1", "bbox_pdf_points": [0, 0, 0, 10]}],
    ) == "pdf_source_grid_instance_hint_invalid"


@pytest.mark.parametrize(
    ("image_rect", "srcsize"),
    [
        ((20, 0, 30, 10), (2, 2)),
        ((10, 0, 20, 10), (2, 2)),
        ((0, 0, 10, 10), (1, 1)),
    ],
)
def test_v3_adapter_allows_outside_edge_touch_and_exact_1x1(
    image_rect: tuple[int, int, int, int], srcsize: tuple[int, int]
) -> None:
    import fitz
    import pdfminer
    import pdfplumber

    document = fitz.open()
    page = document.new_page(width=100, height=100)
    pixels = fitz.Pixmap(
        fitz.csRGB,
        fitz.IRect(0, 0, srcsize[0], srcsize[1]),
        False,
    )
    pixels.clear_with(255)
    page.insert_image(fitz.Rect(*image_rect), pixmap=pixels)
    page.insert_text((1, 8), "A B")
    pdf_bytes = document.tobytes()
    document.close()
    result = PdfPlumberLayoutAdapter(
        pdfplumber_module=pdfplumber,
        pdfminer_module=pdfminer,
        config=PdfLayoutParserConfig(),
        requested_capability="table_candidates",
    ).parse(
        pdf_bytes,
        table_locator_pages=[
            {
                "schema_version": PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3,
                "page_number": 1,
                "status": "located",
                "regions": [
                    {
                        "region_ref": "allow-region-1",
                        "bbox_pdf_points": [0, 0, 10, 10],
                        "title_bbox_pdf_points": None,
                        "header_bbox_pdf_points": [0, 0, 10, 10],
                    }
                ],
            }
        ],
    )
    assert "pdf_source_grid_raster_image_intersection_unsupported" not in (
        result.pages[0]["table_reason_codes"]
    )
    assert "pdf_source_grid_image_bbox_invalid" not in (
        result.pages[0]["table_reason_codes"]
    )


def test_intersecting_raster_reaches_existing_gate1_terminal() -> None:
    import fitz

    document = fitz.open()
    page = document.new_page(width=100, height=100)
    pixels = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), False)
    pixels.clear_with(255)
    page.insert_image(fitz.Rect(0, 0, 100, 100), pixmap=pixels)
    page.insert_text((10, 20), "A B")
    pdf_bytes = document.tobytes()
    document.close()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    normalized = Gate1Normalizer().normalize(
        [
            FileInput(
                private_ref="source-grid-raster-terminal",
                original_filename_private="source-grid-raster-terminal.pdf",
                mime_type="application/pdf",
                source_kind="unit_test",
                declared_size_bytes=len(pdf_bytes),
                bytes_provider=lambda: pdf_bytes,
                provider_label="unit_test",
            )
        ],
        pdf_table_locator_pages_by_sha256={
            digest: [
                {
                    "schema_version": PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3,
                    "page_number": 1,
                    "status": "located",
                    "regions": [
                        {
                            "region_ref": "raster-region-1",
                            "bbox_pdf_points": [0, 0, 100, 100],
                            "title_bbox_pdf_points": None,
                            "header_bbox_pdf_points": [0, 0, 100, 20],
                        }
                    ],
                }
            ]
        },
    )
    blocker = next(
        item
        for item in normalized.package["normalization_blockers"]
        if item.get("code") == "pdf_table_normalization_incomplete"
    )
    assert (
        "pdf_source_grid_raster_image_intersection_unsupported"
        in blocker["reason_code"]
    )
    assert blocker["blocks_next_gate"] is True
    assert normalized.package["gate2_handoff"]["gate2_handoff_status"] == "blocked"
    assert "canonical_artifact" not in normalized.package
    assert "financial_facts" not in normalized.package


def test_real_frozen_moomoo_and_morgan_raster_objects_fail_closed() -> None:
    source = os.environ.get("BROKER_REPORTS_ISSUE317_GEOMETRY_C_DIR")
    if not source:
        pytest.skip("BROKER_REPORTS_ISSUE317_GEOMETRY_C_DIR is required")
    import pdfplumber

    root = Path(source)
    manifest = json.loads(
        (root / "frozen-manifest.private.json").read_text(encoding="utf-8")
    )
    documents = {
        item["document_id"]: item for item in manifest["corpus"]["documents"]
    }
    cases = [
        ("moomoo_annual_2025", 14),
        ("moomoo_midyear_2025", 10),
        *(
            ("morgan_statement_public_slice", page_number)
            for page_number in range(12, 18)
        ),
    ]
    for document_id, page_number in cases:
        with pdfplumber.open(documents[document_id]["source_path"]) as document:
            page = document.pages[page_number - 1]
            wrapper = json.loads(
                (
                    root
                    / "responses"
                    / f"{document_id}__p{page_number:03}.json"
                ).read_text(encoding="utf-8")
            )
            response = wrapper["response"]
            if isinstance(response, str):
                response = json.loads(response)
            regions = []
            for ordinal, table in enumerate(response["tables"], 1):
                ymin, xmin, ymax, xmax = table["table_box_2d"]
                regions.append(
                    {
                        "region_ref": f"{document_id}:{page_number}:{ordinal}",
                        "bbox_pdf_points": [
                            xmin / 1000 * page.width,
                            ymin / 1000 * page.height,
                            xmax / 1000 * page.width,
                            ymax / 1000 * page.height,
                        ],
                    }
                )
            code = _source_grid_raster_reason(
                page=page, regions=regions
            )
        assert code == "pdf_source_grid_raster_image_intersection_unsupported"


def test_source_grid_policy_is_frozen_in_v3_config_identity(monkeypatch) -> None:
    import fitz
    import pdfminer
    import pdfplumber

    import broker_reports_gate1.pdf_layout as pdf_layout

    document = fitz.open()
    document.new_page(width=100, height=100)
    pdf_bytes = document.tobytes()
    document.close()
    config = PdfLayoutParserConfig()
    adapter = PdfPlumberLayoutAdapter(
        pdfplumber_module=pdfplumber,
        pdfminer_module=pdfminer,
        config=config,
        requested_capability="table_candidates",
    )
    v1 = adapter.parse(pdf_bytes)
    locator_pages = [
        {
            "schema_version": PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3,
            "page_number": 1,
            "status": "located_no_tables",
            "regions": [],
        }
    ]
    v3 = adapter.parse(pdf_bytes, table_locator_pages=locator_pages)
    assert v1.parser_config_ref == config.config_ref
    assert v3.parser_config_ref != v1.parser_config_ref
    assert (
        v3.diagnostics["source_grid_policy_version"]
        == PDF_SOURCE_GRID_POLICY_VERSION
    )

    monkeypatch.setattr(
        pdf_layout,
        "PDF_SOURCE_GRID_POLICY_VERSION",
        "pdf_source_grid_policy_mutation_test",
    )
    mutated = adapter.parse(pdf_bytes, table_locator_pages=locator_pages)
    assert mutated.parser_config_ref != v3.parser_config_ref


def _candidate_c_fixture() -> dict:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "issue317_candidate_c_tbank_safe_fixture_v1"
    assert payload["source_pdf"] == {
        "official_url": TBANK_URL,
        "sha256": TBANK_SHA256,
        "size_bytes": TBANK_BYTES,
    }
    assert [page["page_number"] for page in payload["pages"]] == [1, 2, 3, 4]
    for page in payload["pages"]:
        page_number = int(page["page_number"])
        assert json.loads(page["provider_text"]) == page["provider_output"]
        assert (
            hashlib.sha256(page["provider_text"].encode("utf-8")).hexdigest()
            == PROVIDER_TEXT_SHA256[page_number]
        )
        canonical = json.dumps(
            page["provider_output"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        assert hashlib.sha256(canonical).hexdigest() == RESPONSE_SHA256[page_number]
        assert page["response_sha256"] == RESPONSE_SHA256[page_number]
        assert (
            page["provider_response_hash"]
            == PROVIDER_RESPONSE_HASH[page_number]
        )
    return payload


def _candidate_c_locator_pages(pdfplumber, pdf_path: Path) -> list[dict]:
    pages = []
    projection = PdfTableLocatorProjectionFactory(
        PdfTableLocatorProjectionConfig(visual_contract_v3_enabled=True)
    ).create()
    fixture_pages = {
        int(item["page_number"]): item for item in _candidate_c_fixture()["pages"]
    }
    with pdfplumber.open(pdf_path) as document:
        for page_number, page in enumerate(document.pages, 1):
            provider_output = fixture_pages[page_number]["provider_output"]
            current_v3_value = {
                "tables": [
                    {
                        key: table[key]
                        for key in (
                            "table_box_2d",
                            "title_box_2d",
                            "header_box_2d",
                        )
                    }
                    for table in provider_output["tables"]
                ],
                "boundary_from_previous": provider_output[
                    "boundary_from_previous"
                ],
            }
            assert "rows" not in json.dumps(current_v3_value, sort_keys=True)
            page_bbox = [0.0, 0.0, float(page.width), float(page.height)]
            raster_manifest = {
                "render_scope": "full_page",
                "full_page_identity_verified": True,
                "source_coordinate_space": "pdf_top_left_points",
                "pixel_coordinate_space": "crop_top_left_pixels",
                "lossless": True,
                "silent_resize_performed": False,
                "page_rotation": 0,
                "applied_rotation": 0,
                "actual_page_bbox": page_bbox,
                "rendered_bbox": page_bbox,
                "width": 1000,
                "height": 1000,
                "source_to_pixel_transform": {
                    "scale_x": 1000 / page.width,
                    "scale_y": 1000 / page.height,
                    "translate_source_x": 0.0,
                    "translate_source_y": 0.0,
                },
            }
            raster_manifest["manifest_hash"] = sha256_json(raster_manifest)
            projected = projection.project(
                provider_value=current_v3_value,
                raster_manifest=raster_manifest,
                expected_page_bbox=page_bbox,
                has_previous_page=page_number > 1,
                previous_page_has_tables=bool(
                    fixture_pages[page_number - 1]["provider_output"]["tables"]
                )
                if page_number > 1
                else False,
            )
            pages.append(
                {
                    "schema_version": PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3,
                    "page_number": page_number,
                    "status": (
                        "located" if projected["tables"] else "located_no_tables"
                    ),
                    "regions": projected["tables"],
                }
            )
    return pages


def test_frozen_candidate_c_safe_fixture_hashes_are_exact() -> None:
    payload = _candidate_c_fixture()
    assert [len(page["provider_output"]["tables"]) for page in payload["pages"]] == [
        4,
        7,
        4,
        0,
    ]
    # The original model geometry is intentionally malformed here.  The source
    # path must not consume or silently repair these model-proposed row values.
    assert payload["pages"][0]["provider_output"]["tables"][0]["rows"][1][
        "row_y_band"
    ] == [330, 330, 369, 936]
    assert payload["pages"][2]["provider_output"]["tables"][3]["rows"][2][
        "cell_x_boundaries"
    ] == [18, 256, 938, 445]


def test_real_tbank_frozen_candidate_c_builds_all_15_exact_source_grids() -> None:
    source = os.environ.get("BROKER_REPORTS_TBANK_CONTROL_PDF")
    if not source:
        pytest.skip("BROKER_REPORTS_TBANK_CONTROL_PDF is required for the real proof")
    pdf_path = Path(source)
    pdf_bytes = pdf_path.read_bytes()
    assert len(pdf_bytes) == TBANK_BYTES
    assert hashlib.sha256(pdf_bytes).hexdigest() == TBANK_SHA256

    import pdfminer
    import pdfplumber

    adapter = PdfPlumberLayoutAdapter(
        pdfplumber_module=pdfplumber,
        pdfminer_module=pdfminer,
        config=PdfLayoutParserConfig(),
        requested_capability="table_candidates",
    )
    v1_result = adapter.parse(pdf_bytes)
    v1_envelope = asdict(v1_result)
    for page in v1_envelope["pages"]:
        page.pop("elapsed_milliseconds", None)
    v1_envelope["diagnostics"].pop("elapsed_milliseconds_total", None)
    assert "source_grid_policy_version" not in v1_envelope["diagnostics"]
    assert sha256_json(v1_envelope) == TBANK_TAGGED_V1_ENVELOPE_SHA256

    locator_pages = _candidate_c_locator_pages(pdfplumber, pdf_path)
    result = adapter.parse(
        pdf_bytes,
        table_locator_pages=locator_pages,
    )
    tables = [
        table for page in result.pages for table in page["table_candidate_inventory"]
    ]
    assert result.table_candidate_status == "candidate"
    assert all(not page["table_reason_codes"] for page in result.pages)
    assert [(table["rows_total"], table["columns_total"]) for table in tables] == (
        TBANK_SHAPES
    )
    assert sum(table["rows_total"] for table in tables) == 50
    assert sum(table["cells_total"] for table in tables) == 485
    char_claims = [
        (page["page_number"], ordinal)
        for page in result.pages
        for table in page["table_candidate_inventory"]
        for ordinal in table["contributing_char_parser_ordinals"]
    ]
    assert len(char_claims) == 4709
    assert len(char_claims) == len(set(char_claims))

    page_one_chars = {
        int(item["parser_ordinal"]): str(item["text"])
        for item in result.pages[0]["char_inventory"]
    }
    first = result.pages[0]["table_candidate_inventory"][0]
    trade_ids = [
        "".join(page_one_chars[value] for value in cell["char_parser_ordinals"])
        for cell in first["cell_inventory"]
        if cell["row_ordinal"] > 1 and cell["column_ordinal"] == 1
    ]
    assert trade_ids == [
        "5586419352",
        "5586419351",
        "5586419350",
        "5586423274",
        "5586423273",
    ]
    quantities = [
        int("".join(page_one_chars[value] for value in cell["char_parser_ordinals"]))
        for cell in first["cell_inventory"]
        if cell["row_ordinal"] > 1 and cell["column_ordinal"] == 13
    ]
    assert sum(quantities) == 7

    page_two = result.pages[1]["table_candidate_inventory"]
    assert page_two[0]["bbox"][3] < page_two[1]["bbox"][1]
    assert page_two[1]["title_char_parser_ordinals"]
    assert result.pages[0]["table_candidate_inventory"][3]["rows_total"] == 2
    assert result.pages[3]["table_candidate_inventory"] == []

    blocked_locator_pages = copy.deepcopy(locator_pages)
    blocked_locator_pages[0]["regions"][0]["title_bbox_pdf_points"] = [
        0.0,
        0.0,
        2.0,
        2.0,
    ]
    normalized = Gate1Normalizer().normalize(
        [
            FileInput(
                private_ref="tbank-source-grid-terminal",
                original_filename_private="tbank-source-grid-terminal.pdf",
                mime_type="application/pdf",
                source_kind="unit_test",
                declared_size_bytes=len(pdf_bytes),
                bytes_provider=lambda: pdf_bytes,
                provider_label="unit_test",
            )
        ],
        pdf_table_locator_pages_by_sha256={
            TBANK_SHA256: blocked_locator_pages
        },
    )
    blockers = [
        item
        for item in normalized.package["normalization_blockers"]
        if item.get("code") == "pdf_table_normalization_incomplete"
    ]
    assert len(blockers) == 1
    assert (
        "source_grid_reason_codes=pdf_source_grid_title_binding_unproven"
        in blockers[0]["reason_code"]
    )
    assert blockers[0]["blocks_next_gate"] is True
    assert "canonical_artifact" not in normalized.package
    assert "financial_facts" not in normalized.package
