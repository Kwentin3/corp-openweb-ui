from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import fitz
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.artifact_models import ArtifactAccessContext  # noqa: E402
from broker_reports_gate1.artifact_retention import build_retention_policy  # noqa: E402
from broker_reports_gate1.artifact_store import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.bounded_graph import (  # noqa: E402
    Gate1BoundedGraphConfig,
    Gate1BoundedGraphFactory,
)
from broker_reports_gate1.canonical_artifact import (  # noqa: E402
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
)
from broker_reports_gate1.inputs import FileInput  # noqa: E402
from broker_reports_gate1.gate2_handoff import persist_gate1_result  # noqa: E402
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    Gate2OpenWebUIProviderConnection,
)
from broker_reports_gate1.normalizer import Gate1Normalizer  # noqa: E402
from broker_reports_gate1.pdf_layout import (  # noqa: E402
    PdfLayoutParserConfig,
    PdfPlumberLayoutAdapter,
)
from broker_reports_gate1.pdf_layout_units import (  # noqa: E402
    _materialize_locator_source_bindings,
)
from broker_reports_gate1.pdf_text_layer import (  # noqa: E402
    validate_pdf_source_unit_structure,
)
from broker_reports_gate1.pdf_table_intake_runtime import (  # noqa: E402
    PDF_TABLE_LOCATOR_PAGE_SCHEMA,
    PdfTableIntakeConfig,
    PdfTableIntakeRuntimeFactory,
    table_detection_output_schema,
)
from broker_reports_gate1.pdf_table_locator import (  # noqa: E402
    PDF_TABLE_LOCATOR_COORDINATE_CONTRACT,
    PDF_TABLE_LOCATOR_PROMPT,
)
from broker_reports_gate1.pdf_table_locator_provider import (  # noqa: E402
    PdfTableLocatorProviderConfig,
    PdfTableLocatorProviderFactory,
)
from broker_reports_gate1.table_projection import (  # noqa: E402
    NormalizedTableProjectionFactory,
    TableProjectionValidator,
    _checksum_ref,
)


def _single_page_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=100, height=120)
    for x in (10, 40, 70, 90):
        page.draw_line((x, 25), (x, 95), color=(0, 0, 0), width=1)
    for y in (25, 50, 75, 95):
        page.draw_line((10, y), (90, y), color=(0, 0, 0), width=1)
    page.insert_text((14, 42), "Name")
    page.insert_text((44, 42), "Qty")
    page.insert_text((74, 42), "Sum")
    page.insert_text((14, 67), "AAA")
    page.insert_text((44, 67), "2")
    page.insert_text((74, 67), "10")
    page.insert_text((14, 88), "BBB")
    page.insert_text((44, 88), "3")
    page.insert_text((74, 88), "20")
    data = document.tobytes(deflate=True)
    document.close()
    return data


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
TBANK_FROZEN_LOCATOR_V2 = {
    1: [
        ([264, 18, 544, 939], [236, 20, 252, 480], [264, 18, 333, 939]),
        ([583, 18, 653, 939], [555, 20, 571, 405], [583, 18, 652, 939]),
        ([692, 18, 762, 939], [664, 20, 680, 569], [692, 18, 761, 939]),
        ([824, 18, 940, 939], [796, 20, 812, 386], [825, 18, 915, 939]),
    ],
    2: [
        ([62, 18, 233, 939], [34, 20, 50, 328], [62, 18, 131, 939]),
        ([264, 18, 387, 939], [241, 469, 254, 488], [265, 18, 316, 939]),
        ([427, 18, 520, 939], [399, 20, 415, 259], [427, 18, 479, 939]),
        ([559, 18, 613, 939], [531, 20, 547, 338], [560, 18, 611, 939]),
        ([675, 18, 728, 939], [647, 20, 663, 561], [675, 18, 728, 939]),
        ([767, 18, 858, 939], [739, 20, 755, 207], [768, 18, 819, 939]),
        ([897, 18, 950, 939], [869, 20, 885, 477], [897, 18, 949, 939]),
    ],
    3: [
        ([62, 18, 115, 939], [34, 20, 50, 342], [62, 18, 115, 939]),
        ([155, 18, 208, 939], [126, 20, 143, 245], [155, 18, 207, 939]),
        ([247, 18, 315, 939], [219, 20, 235, 228], [247, 18, 291, 939]),
        ([378, 18, 889, 939], [350, 20, 366, 366], [378, 18, 421, 939]),
    ],
    4: [],
}
TBANK_TRADE_IDS = [
    "5586419352",
    "5586419351",
    "5586419350",
    "5586423274",
    "5586423273",
]


def _public_tbank_control() -> tuple[bytes, str]:
    source = os.environ.get("BROKER_REPORTS_TBANK_CONTROL_PDF")
    if not source:
        controls = list(Path("C:/Users").glob("*/AppData/Local/Temp/1/issue317-tbank-*/tbank-control.pdf"))
        source = str(controls[0]) if controls else None
    assert source, "BROKER_REPORTS_TBANK_CONTROL_PDF must name the pinned public control"
    pdf_bytes = Path(source).read_bytes()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    assert digest == "25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67"
    return pdf_bytes, digest


def _tbank_input(pdf_bytes: bytes) -> FileInput:
    return FileInput(
        private_ref="tbank-control",
        original_filename_private="control.pdf",
        mime_type="application/pdf",
        source_kind="unit_test",
        declared_size_bytes=len(pdf_bytes),
        bytes_provider=lambda: pdf_bytes,
        provider_label="unit_test",
    )


def _complete_tbank_locator_pages() -> list[dict]:
    # These regions and shapes are upstream evidence from visual inspection of
    # the four page PNGs and all 15 crops.  They do not prove an autonomous
    # locator or recovery of table titles outside the supplied boxes.
    return [
        {
            "page_number": page_number,
            "status": "located" if regions else "located_no_tables",
            "regions": [
                {"region_ref": region_ref, "bbox_pdf_points": list(box)}
                for region_ref, box, _shape in regions
            ],
        }
        for page_number, regions in TBANK_VISUALLY_VERIFIED_REGIONS.items()
    ]


def test_real_tbank_given_complete_locator_regions_preserves_all_15_grids() -> None:
    pdf_bytes, digest = _public_tbank_control()
    normalized = Gate1Normalizer().normalize(
        [_tbank_input(pdf_bytes)],
        pdf_table_locator_pages_by_sha256={digest: _complete_tbank_locator_pages()},
    )
    projections = [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    expected_shapes = [
        shape
        for regions in TBANK_VISUALLY_VERIFIED_REGIONS.values()
        for _region_ref, _box, shape in regions
    ]
    assert len(projections) == 15
    assert [(item["row_count"], item["column_count"]) for item in projections] == (
        expected_shapes
    )
    assert sum(item["row_count"] for item in projections) == 50
    assert sum(item["cell_count"] for item in projections) == 485
    cells = [cell for projection in projections for cell in projection["cells"]]
    assert sum(not cell["empty_cell"] for cell in cells) == 424
    assert sum(cell["empty_cell"] for cell in cells) == 61

    first = projections[0]
    values = {
        item["value_path_ref"]: item["normalized_value"]
        for item in first["private_values"]
    }
    first_column = [
        values[cell["normalized_private_value_path"]]
        for cell in first["cells"]
        if cell["row_ordinal"] > 1 and cell["column_ordinal"] == 1
    ]
    assert first_column == TBANK_TRADE_IDS
    quantities = [
        int(values[cell["normalized_private_value_path"]])
        for cell in first["cells"]
        if cell["row_ordinal"] > 1 and cell["column_ordinal"] == 13
    ]
    assert sum(quantities) == 7
    assert not any(
        item.get("code") == "pdf_table_normalization_incomplete"
        for item in normalized.package["normalization_blockers"]
    )


def _assert_canonical_blocked(normalized, tmp_path: Path, monkeypatch) -> None:
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    monkeypatch.setattr(
        "broker_reports_gate1.canonical_store.shutil.disk_usage",
        lambda _: shutil._ntuple_diskusage(
            10_000_000_000, 1_000_000_000, 9_000_000_000
        ),
    )
    run_id = normalized.package["normalization_run"]["run_id"]
    context = ArtifactAccessContext(
        user_id="u",
        case_id="c",
        chat_id="ch",
        workspace_model_id="broker_reports_ndfl",
        normalization_run_id=run_id,
        allow_private=True,
        require_source_available=True,
    )
    manifest = persist_gate1_result(
        store=store,
        result=normalized,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
    )
    assert "broker_reports_canonical_artifact_v1" not in manifest.artifact_refs_by_type
    assert "broker_reports_canonical_build_failure_v1" in manifest.artifact_refs_by_type


def test_real_tbank_frozen_locator_v2_contract_reaches_all_strict_grids() -> None:
    pdf_bytes, digest = _public_tbank_control()
    provider = FrozenPageDetectorProvider(TBANK_FROZEN_LOCATOR_V2)
    intake = (
        PdfTableIntakeRuntimeFactory(PdfTableIntakeConfig(enabled=True))
        .create_with_provider(provider)
        .run(
            [
                {
                    "document_ref": "tbank-frozen-locator-v2",
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": digest,
                }
            ]
        )
    )
    # Frozen geometry exercises the active contract; it is not a real-call or
    # autonomous-locator acceptance receipt. All page PNGs and table regions
    # were independently inspected before freezing these boxes.
    assert provider.invocations == 4
    assert [len(page["regions"]) for page in intake.private_page_results] == [4, 7, 4, 0]
    assert [page["status"] for page in intake.private_page_results] == [
        "located",
        "located",
        "located",
        "located_no_tables",
    ]
    import pdfminer
    import pdfplumber

    layout = PdfPlumberLayoutAdapter(
        pdfplumber_module=pdfplumber,
        pdfminer_module=pdfminer,
        config=PdfLayoutParserConfig(),
        requested_capability="table_candidates",
    ).parse(pdf_bytes, table_locator_pages=intake.private_page_results)
    title_claims: list[tuple[int, int]] = []
    grid_claims: list[tuple[int, int]] = []
    for page, locator_page in zip(
        layout.pages, intake.private_page_results, strict=True
    ):
        candidates = page["table_candidate_inventory"]
        assert len(candidates) == len(locator_page["regions"])
        page_chars = page["char_inventory"]
        for candidate, region in zip(
            candidates, locator_page["regions"], strict=True
        ):
            title_bbox = region["title_bbox_pdf_points"]
            header_bbox = region["header_bbox_pdf_points"]

            def exact_ordinals(box):
                if box is None:
                    return []
                return [
                    int(char["parser_ordinal"])
                    for char in page_chars
                    if box[0]
                    <= (char["bbox"][0] + char["bbox"][2]) / 2.0
                    <= box[2]
                    and box[1]
                    <= (char["bbox"][1] + char["bbox"][3]) / 2.0
                    <= box[3]
                ]

            title_refs = candidate["source_title_char_parser_ordinals"]
            header_refs = candidate["source_header_char_parser_ordinals"]
            assert title_refs == exact_ordinals(title_bbox)
            assert header_refs == exact_ordinals(header_bbox)
            assert title_refs and len(title_refs) == len(set(title_refs))
            assert header_refs and len(header_refs) == len(set(header_refs))
            own_grid = set(candidate["contributing_char_parser_ordinals"])
            assert set(title_refs).isdisjoint(own_grid)
            assert set(header_refs) <= own_grid
            title_claims.extend(
                (int(page["page_number"]), ordinal) for ordinal in title_refs
            )
            grid_claims.extend(
                (int(page["page_number"]), ordinal) for ordinal in own_grid
            )
    assert len(title_claims) == len(set(title_claims))
    assert len(grid_claims) == len(set(grid_claims))
    assert set(title_claims).isdisjoint(grid_claims)
    normalized = Gate1Normalizer().normalize(
        [_tbank_input(pdf_bytes)],
        pdf_table_locator_pages_by_sha256={digest: intake.private_page_results},
    )
    projections = [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    expected_shapes = [
        shape
        for regions in TBANK_VISUALLY_VERIFIED_REGIONS.values()
        for _region_ref, _box, shape in regions
    ]
    assert [(item["row_count"], item["column_count"]) for item in projections] == expected_shapes
    assert sum(item["row_count"] for item in projections) == 50
    assert sum(item["cell_count"] for item in projections) == 485
    assert all(
        item["projection_status"] == "ready"
        and item["validator_status"] == "passed"
        for item in projections
    )
    units = {
        item["unit_ref"]: item
        for item in normalized.package["private_normalized_source_units"]
    }
    paragraph_word_refs = {
        ref
        for unit in units.values()
        if unit.get("pdf_unit_type") == "pdf_line_cluster_unit"
        for ref in unit.get("layout_word_refs") or []
    }
    paragraph_line_refs = {
        ref
        for unit in units.values()
        if unit.get("pdf_unit_type") == "pdf_line_cluster_unit"
        for ref in unit.get("layout_line_refs") or []
    }
    titles = []
    for projection in projections:
        title = projection["table_title_binding"]
        unit = units[projection["source_unit_ref"]]
        unit_title = unit["table_title_binding"]
        titles.append(title["value"])
        assert "char_refs" not in title
        assert {
            key: value
            for key, value in unit_title.items()
            if key not in {"char_refs", "checksum_ref"}
        } == {
            key: value for key, value in title.items() if key != "checksum_ref"
        }
        assert unit_title["char_refs"] and len(unit_title["char_refs"]) == len(
            set(unit_title["char_refs"])
        )
        assert set(title["word_refs"]).isdisjoint(
            unit["table_contributing_word_refs"]
        )
        assert set(title["word_refs"]).isdisjoint(paragraph_word_refs)
        assert set(title["line_refs"]).isdisjoint(paragraph_line_refs)
        assert projection["bound_header_row_count"] == len(
            projection["header_model"]["header_row_refs"]
        )
        assert projection["header_model"]["source_value_refs"]
        assert projection["header_model"]["source_checksum_ref"]
    assert len(titles) == 15 and all(titles)
    assert "RUB" in titles

    rebuilt = NormalizedTableProjectionFactory().create().build_for_document(
        source_format="pdf",
        payloads=normalized.package["private_normalized_source_payloads"],
        source_units=normalized.package["private_normalized_source_units"],
    )
    assert len(rebuilt.projections) == 15
    assert all(item["validator_status"] == "passed" for item in rebuilt.projections)

    forged_payloads = copy.deepcopy(
        normalized.package["private_normalized_source_payloads"]
    )
    forged_units = copy.deepcopy(
        normalized.package["private_normalized_source_units"]
    )
    forged_unit = next(item for item in forged_units if item.get("table_title_binding"))
    forged_payload = next(
        item
        for item in forged_payloads
        if item["source_payload_ref"] == forged_unit["parent_payload_ref"]
    )
    forged_projection = forged_payload["pdf_text_layer_projection"]
    forged_candidate = next(
        item
        for item in forged_projection["table_candidate_inventory"]
        if item["table_candidate_ref"] == forged_unit["table_candidate_ref"]
    )
    forged_line = next(
        item
        for item in forged_projection["line_inventory"]
        if item["line_ref"] == forged_unit["table_title_binding"]["line_refs"][0]
    )
    forged_line["text"] = "FORGED TITLE"
    forged_binding = copy.deepcopy(forged_unit["table_title_binding"])
    forged_binding["value"] = forged_line["text"]
    forged_binding["char_refs"][0] = "pdfchar-foreign"
    forged_binding["checksum_ref"] = _checksum_ref(
        "pdftitlechk",
        {
            key: value
            for key, value in forged_binding.items()
            if key != "checksum_ref"
        },
    )
    forged_candidate["source_title_binding"] = copy.deepcopy(forged_binding)
    forged_unit["table_title_binding"] = copy.deepcopy(forged_binding)
    forged_result = (
        NormalizedTableProjectionFactory().create().build_for_document(
            source_format="pdf",
            payloads=forged_payloads,
            source_units=forged_units,
        )
    )
    rejected = next(
        item
        for item in forged_result.projections
        if item["source_unit_ref"] == forged_unit["unit_ref"]
    )
    assert rejected["projection_status"] == "blocked"
    assert {
        "pdf_layout_source_unit_checksum_mismatch",
        "pdf_source_unit_parent_payload_invalid",
    } <= set(rejected["reconstruction_reason_codes"])


@pytest.mark.parametrize(
    ("title_ordinals", "line_word_refs", "reason"),
    [
        ([1, 1], ["word-title"], "source_char_binding_invalid"),
        ([99], ["word-title"], "source_char_binding_invalid"),
        ([1], ["word-title"], "title_word_partition_invalid"),
        ([1, 2], ["word-title", "word-grid"], "title_line_partition_invalid"),
        ([1, 2], ["word-title", "word-title"], "title_line_partition_invalid"),
    ],
)
def test_title_binding_partial_word_or_line_fails_closed(
    title_ordinals, line_word_refs, reason
) -> None:
    with pytest.raises(ValueError, match=reason):
        _materialize_locator_source_bindings(
            raw={
                "source_title_char_parser_ordinals": title_ordinals,
                "bound_header_row_count": 0,
            },
            words=[
                {
                    "word_ref": "word-title",
                    "source_char_refs": ["char-1", "char-2"],
                    "source_value_ref": "src-title",
                },
                {
                    "word_ref": "word-grid",
                    "source_char_refs": ["char-3"],
                    "source_value_ref": "src-grid",
                },
            ],
            lines=[
                {
                    "line_ref": "line-title",
                    "word_refs": line_word_refs,
                    "text": "Title",
                }
            ],
            rows=[{"row_ref": "row-1", "row_ordinal": 1, "cell_refs": ["cell-1"]}],
            cells=[{"cell_ref": "cell-1", "word_refs": ["word-grid"]}],
            char_by_ordinal={1: "char-1", 2: "char-2", 3: "char-3"},
            char_text_by_ref={"char-1": "T", "char-2": "i", "char-3": "1"},
        )


def test_real_tbank_wrong_neighbor_title_is_rejected() -> None:
    pdf_bytes, digest = _public_tbank_control()
    wrong_neighbor = copy.deepcopy(TBANK_FROZEN_LOCATOR_V2)
    second_table, _second_title, second_header = wrong_neighbor[1][1]
    wrong_neighbor[1][1] = (
        second_table,
        wrong_neighbor[1][0][1],
        second_header,
    )

    intake = (
        PdfTableIntakeRuntimeFactory(PdfTableIntakeConfig(enabled=True))
        .create_with_provider(FrozenPageDetectorProvider(wrong_neighbor))
        .run(
            [
                {
                    "document_ref": "tbank-wrong-neighbor-title",
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": digest,
                }
            ]
        )
    )

    assert intake.safe_summary["status"] == "failed"
    assert intake.private_page_results[0]["status"] == "failed"
    assert intake.private_page_results[0]["regions"] == []
    assert (
        intake.private_detection_attempts[0]["validation_error_code"]
        == "pdf_table_locator_title_overlap_invalid"
    )


def test_real_tbank_only_table_1_1_with_unresolved_pages_blocks_canonical(
    tmp_path: Path, monkeypatch
) -> None:
    pdf_bytes, digest = _public_tbank_control()
    locator_pages = [
        {
            "page_number": 1,
            "status": "located",
            "regions": [
                {
                    "region_ref": "p1_table_1_1",
                    "bbox_pdf_points": [15.6, 157.4, 789.7, 323.3],
                }
            ],
        },
        {"page_number": 2, "status": "failed", "regions": []},
        {"page_number": 3, "status": "failed", "regions": []},
        {"page_number": 4, "status": "located_no_tables", "regions": []},
    ]
    normalized = Gate1Normalizer().normalize(
        [_tbank_input(pdf_bytes)],
        input_context={"canonical_gate2_write_enabled": True, "canonical_gate2_read_enabled": True},
        pdf_table_locator_pages_by_sha256={digest: locator_pages},
    )
    projections = [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    assert len(projections) == 1
    assert (projections[0]["row_count"], projections[0]["column_count"]) == (6, 32)
    assert any(
        item.get("code") == "pdf_table_normalization_incomplete"
        and item.get("blocks_next_gate") is True
        for item in normalized.package["normalization_blockers"]
    )

    _assert_canonical_blocked(normalized, tmp_path, monkeypatch)


def _header_only_table_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=240, height=100)
    for x in (10, 85, 160, 230):
        page.draw_line((x, 25), (x, 65), color=(0, 0, 0), width=1)
    for y in (25, 65):
        page.draw_line((10, y), (230, y), color=(0, 0, 0), width=1)
    page.insert_text((18, 48), "Date")
    page.insert_text((93, 48), "Asset")
    page.insert_text((168, 48), "Amount")
    data = document.tobytes(deflate=True)
    document.close()
    return data


def _horizontally_framed_header_only_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=240, height=100)
    for y in (25, 65):
        page.draw_line((10, y), (230, y), color=(0, 0, 0), width=1)
    page.insert_text((18, 48), "Date")
    page.insert_text((93, 48), "Asset")
    page.insert_text((168, 48), "Amount")
    data = document.tobytes(deflate=True)
    document.close()
    return data


def _two_table_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((48, 38), "Synthetic Broker Statement", fontsize=15)
    for table_number, title, top, rows in (
        (1, "Transactions", 90, (("ABC purchase", "2", "100.25"), ("XYZ sale", "1", "75.50"))),
        (2, "Cash movements", 360, (("Deposit", "1", "500.00"), ("Fee", "1", "5.00"))),
    ):
        page.insert_text((48, top - 12), f"Table {table_number} - {title}", fontsize=12)
        for x in (48, 255, 390, 547):
            page.draw_line((x, top), (x, top + 102), color=(0, 0, 0), width=1)
        for y in (top, top + 34, top + 68, top + 102):
            page.draw_line((48, y), (547, y), color=(0, 0, 0), width=1)
        values = (("Description", "Quantity", "Amount"), *rows)
        for row_ordinal, row in enumerate(values):
            baseline = top + 24 + row_ordinal * 34
            for x, value in zip((56, 263, 398), row, strict=True):
                page.insert_text((x, baseline), value, fontsize=10)
    page.insert_text((48, 800), "Synthetic fixture. No customer data.", fontsize=8)
    data = document.tobytes(deflate=True)
    document.close()
    return data


def _merged_header_table_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=320, height=180)
    for start, end in (
        ((10, 20), (290, 20)),
        ((80, 40), (290, 40)),
        ((10, 60), (290, 60)),
        ((10, 85), (290, 85)),
        ((10, 110), (290, 110)),
        ((10, 20), (10, 110)),
        ((80, 20), (80, 110)),
        ((140, 40), (140, 110)),
        ((200, 20), (200, 110)),
        ((290, 20), (290, 110)),
    ):
        page.draw_line(start, end, color=(0, 0, 0), width=1)
    for x, y, text in (
        (18, 43, "Identity"),
        (100, 33, "Period values"),
        (225, 33, "Currency"),
        (92, 53, "Start"),
        (150, 53, "End"),
        (220, 53, "Code"),
        (18, 77, "AAA"),
        (92, 77, "10"),
        (150, 77, "20"),
        (220, 77, "RUB"),
        (18, 102, "Total"),
        (92, 102, "10"),
        (150, 102, "20"),
        (220, 102, "RUB"),
    ):
        page.insert_text((x, y), text, fontsize=7)
    data = document.tobytes(deflate=True)
    document.close()
    return data


def _borderless_aligned_table_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=320, height=140)
    for y, values in (
        (32, ("Name", "Amount", "Currency")),
        (62, ("AAA", "10", "RUB")),
        (92, ("BBB", "20", "RUB")),
    ):
        for x, value in zip((18, 145, 245), values, strict=True):
            page.insert_text((x, y), value, fontsize=8)
    data = document.tobytes(deflate=True)
    document.close()
    return data


def _borderless_single_data_row_table_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=320, height=110)
    for y, values in (
        (32, ("Name", "Amount", "Currency")),
        (62, ("AAA", "10", "RUB")),
    ):
        for x, value in zip((18, 145, 245), values, strict=True):
            page.insert_text((x, y), value, fontsize=8)
    data = document.tobytes(deflate=True)
    document.close()
    return data


def _two_page_table_pdf(*, second_page_header: bool) -> bytes:
    document = fitz.open()
    first = document.new_page(width=320, height=320)

    def draw_table(page, edges, rows):
        for y in edges:
            page.draw_line((20, y), (300, y), color=(0, 0, 0), width=1)
        for x in (20, 110, 210, 300):
            page.draw_line((x, edges[0]), (x, edges[-1]), color=(0, 0, 0), width=1)
        for row_ordinal, values in enumerate(rows):
            baseline = edges[row_ordinal] + 17
            for x, value in zip((28, 125, 225), values, strict=True):
                page.insert_text((x, baseline), value, fontsize=7)

    draw_table(
        first,
        [220, 245, 270, 294, 318],
        [
            ("Name", "Amount", "Currency"),
            ("AAA", "10", "RUB"),
            ("BBB", "20", "RUB"),
            ("CCC", "30", "RUB"),
        ],
    )
    second = document.new_page(width=320, height=320)
    draw_table(
        second,
        [2, 27, 52, 77],
        (
            [
                ("Name", "Amount", "Currency"),
                ("DDD", "40", "RUB"),
                ("EEE", "50", "RUB"),
            ]
            if second_page_header
            else [
                ("DDD", "40", "RUB"),
                ("EEE", "50", "RUB"),
                ("FFF", "60", "RUB"),
            ]
        ),
    )
    data = document.tobytes(deflate=True)
    document.close()
    return data


class StaticDetectorProvider:
    def __init__(
        self,
        boxes: list[list[int]],
        *,
        malformed: bool = False,
        tables: list[dict] | None = None,
    ) -> None:
        self.boxes = boxes
        self.malformed = malformed
        self.tables = copy.deepcopy(tables)
        self.invocations = 0

    def qualify(self):
        return {
            "status": "qualified",
            "provider_profile": "google_gemini",
            "provider_profile_revision": "test-profile-v1",
            "requested_model_id": "models/gemini-3.5-flash",
            "resolved_model_id": "models/gemini-3.5-flash",
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "response_hash": "qualification-response-hash",
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_retry": False,
            "provider_failover": False,
        }

    def count_tokens(self, **kwargs):
        return {
            "total_tokens": 100,
            "request_hash": "token-request-hash",
            "response_hash": "token-response-hash",
            "within_hard_guard": True,
        }

    def invoke(self, **kwargs):
        self.invocations += 1
        value = {
            "tables": self.tables
            if self.tables is not None
            else [
                {
                    "table_box_2d": box,
                    "title_box_2d": None,
                    "header_box_2d": None,
                }
                for box in self.boxes
            ]
        }
        if self.malformed:
            value["semantic_summary"] = "forbidden"
        return {
            "attempt": {
                "terminal_failure_class": None,
                "provider_profile": "google_gemini",
                "provider_profile_revision": "test-profile-v1",
                "model_requested": "models/gemini-3.5-flash",
                "model_resolved": "models/gemini-3.5-flash",
                "adapter_identity": "test-detector-adapter-v1",
                "request_hash": "provider-request-hash",
                "hidden_retry": False,
                "provider_failover": False,
            },
            "json_output": value,
            "raw_private_response": {"test": True},
            "response_hash": "provider-response-hash",
        }


class FrozenPageDetectorProvider(StaticDetectorProvider):
    def __init__(self, pages: dict[int, list[tuple[list[int], list[int], list[int]]]]):
        super().__init__([])
        self.pages = copy.deepcopy(pages)

    def invoke(self, **kwargs):
        page_number = self.invocations + 1
        self.tables = [
            {
                "table_box_2d": table,
                "title_box_2d": title,
                "header_box_2d": header,
            }
            for table, title, header in self.pages[page_number]
        ]
        return super().invoke(**kwargs)


class _LocatorHttpResponse:
    def __init__(self, payload: dict) -> None:
        self.status = 200
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int) -> bytes:
        return self.payload


class _LocatorHttpTransport:
    def __init__(self) -> None:
        self.requests = []

    def __call__(self, request, timeout: int):
        assert timeout == 240
        self.requests.append(request)
        if request.full_url.endswith(":countTokens"):
            return _LocatorHttpResponse({"totalTokens": 17})
        assert request.full_url.endswith(":generateContent")
        return _LocatorHttpResponse(
            {
                "modelVersion": "gemini-3.5-flash",
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": '{"tables":[]}'}]},
                    }
                ],
            }
        )


def _run_intake(provider: StaticDetectorProvider):
    pdf_bytes = _single_page_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    result = (
        PdfTableIntakeRuntimeFactory(PdfTableIntakeConfig(enabled=True))
        .create_with_provider(provider)
        .run(
            [
                {
                    "document_ref": "pdfsource_test",
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": digest,
                }
            ]
        )
    )
    return pdf_bytes, digest, result


def _legacy_locator_pages(result) -> list[dict]:
    pages = copy.deepcopy(result.private_page_results)
    for page in pages:
        page["schema_version"] = "broker_reports_pdf_table_locator_page_v1"
        page.pop("source_binding_policy", None)
        for region in page.get("regions") or []:
            region.pop("detector_contract_version", None)
            region.pop("source_binding_policy", None)
    return pages


def test_locator_prompt_is_native_coordinates_and_locator_only() -> None:
    model_view = (
        PdfTableIntakeRuntimeFactory(PdfTableIntakeConfig(enabled=True))
        .create_with_provider(StaticDetectorProvider([]))
        ._model_view(request_id="request-1", page_number=1)
    )
    assert model_view["task"] == PDF_TABLE_LOCATOR_PROMPT
    assert "[ymin, xmin, ymax, xmax]" in model_view["task"]
    assert "Never use one table_box_2d" in model_view["task"]
    assert "header-only tables" in model_view["task"]
    assert "explanatory tables" in model_view["task"]
    assert "Do not transcribe text" in model_view["task"]


def test_maintained_gemini_adapter_sends_exact_v2_schema_once() -> None:
    transport = _LocatorHttpTransport()
    adapter = PdfTableLocatorProviderFactory(
        PdfTableLocatorProviderConfig(maximum_counted_input_tokens=1000),
        urlopen_fn=transport,
    ).create_with_connection(
        Gate2OpenWebUIProviderConnection(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key="secret",
        )
    )
    png = b"png"
    png_hash = hashlib.sha256(png).hexdigest()
    schema = table_detection_output_schema()

    counted = adapter.count_tokens(
        model_view={"task": PDF_TABLE_LOCATOR_PROMPT},
        output_schema=schema,
        png_bytes=png,
        crop_sha256=png_hash,
    )
    result = adapter.invoke(
        task_id="locator-v2",
        model_view={"task": PDF_TABLE_LOCATOR_PROMPT},
        output_schema=schema,
        png_bytes=png,
        crop_sha256=png_hash,
        attempt_number=1,
        attempt_lineage=[],
    )

    assert counted["total_tokens"] == 17
    assert result["json_output"] == {"tables": []}
    assert result["attempt"]["finish_reason"] == "STOP"
    assert result["attempt"]["hidden_retry"] is False
    generated_requests = [
        request
        for request in transport.requests
        if request.full_url.endswith(":generateContent")
    ]
    assert len(generated_requests) == 1
    request_body = json.loads(generated_requests[0].data.decode("utf-8"))
    generation = request_body["generationConfig"]
    assert generation["temperature"] == 0
    assert generation["candidateCount"] == 1
    adapted = generation["responseJsonSchema"]
    item = adapted["properties"]["tables"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == {
        "table_box_2d",
        "title_box_2d",
        "header_box_2d",
    }
    assert {branch["type"] for branch in item["properties"]["title_box_2d"]["anyOf"]} == {
        "array",
        "null",
    }
    assert {branch["type"] for branch in item["properties"]["header_box_2d"]["anyOf"]} == {
        "array",
        "null",
    }


def test_runtime_returns_pdf_regions_without_vlm_transcription_crops() -> None:
    provider = StaticDetectorProvider([[150, 100, 850, 900]])
    _, digest, result = _run_intake(provider)

    assert provider.invocations == 1
    assert result.safe_summary["status"] == "completed"
    assert result.safe_summary["candidates_total"] == 1
    assert result.safe_summary["rows_columns_cells_inferred"] is False
    assert result.private_candidates == []
    assert len(result.private_page_results) == 1
    page = result.private_page_results[0]
    assert page["schema_version"] == PDF_TABLE_LOCATOR_PAGE_SCHEMA
    assert page["schema_version"] != "broker_reports_pdf_table_locator_page_v1"
    assert page["status"] == "located"
    assert page["pdf_sha256"] == digest
    assert len(page["regions"]) == 1
    assert page["regions"][0]["box_2d_normalized"] == [150, 100, 850, 900]
    assert page["model_values_used_as_source_literals"] is False
    assert page["pdfplumber_settings_selected_by_model"] is False


def test_v1_injected_region_is_isolated_from_v2_emission() -> None:
    pdf_bytes, _, result = _run_intake(
        StaticDetectorProvider([[150, 100, 850, 900]])
    )

    emitted = result.private_page_results[0]
    legacy = _legacy_locator_pages(result)[0]
    assert emitted["schema_version"] == "broker_reports_pdf_table_locator_page_v2"
    assert emitted["regions"][0]["detector_contract_version"].endswith("_v2")
    assert emitted["source_binding_policy"] == "exact_one_grid_v1"
    assert emitted["regions"][0]["source_binding_policy"] == "exact_one_grid_v1"
    assert legacy["schema_version"] == "broker_reports_pdf_table_locator_page_v1"
    assert "detector_contract_version" not in legacy["regions"][0]
    assert "source_binding_policy" not in legacy
    assert "source_binding_policy" not in legacy["regions"][0]

    import pdfminer
    import pdfplumber

    downgraded = copy.deepcopy(result.private_page_results)
    downgraded[0]["regions"][0].pop("source_binding_policy")
    cross_version = copy.deepcopy(result.private_page_results)
    cross_version[0]["schema_version"] = "broker_reports_pdf_table_locator_page_v1"
    cross_version[0].pop("source_binding_policy")
    both_policies_removed = copy.deepcopy(result.private_page_results)
    both_policies_removed[0].pop("source_binding_policy")
    both_policies_removed[0]["regions"][0].pop("source_binding_policy")
    schema_only_downgraded = copy.deepcopy(result.private_page_results)
    schema_only_downgraded[0]["schema_version"] = (
        "broker_reports_pdf_table_locator_page_v1"
    )
    missing_geometry = copy.deepcopy(result.private_page_results)
    missing_geometry[0]["regions"][0].pop("title_bbox_pdf_points")
    missing_geometry[0]["regions"][0].pop("header_bbox_pdf_points")
    for locator_pages in (
        downgraded,
        cross_version,
        both_policies_removed,
        schema_only_downgraded,
        missing_geometry,
    ):
        parsed = PdfPlumberLayoutAdapter(
            pdfplumber_module=pdfplumber,
            pdfminer_module=pdfminer,
            config=PdfLayoutParserConfig(),
            requested_capability="table_candidates",
        ).parse(pdf_bytes, table_locator_pages=locator_pages)
        assert parsed.pages[0]["table_candidate_inventory"] == []
        assert "pdf_table_locator_contract_version_failed" in parsed.pages[0][
            "table_reason_codes"
        ]


def test_absent_table_page_is_a_valid_negative() -> None:
    _, _, result = _run_intake(StaticDetectorProvider([]))

    assert result.safe_summary["status"] == "completed"
    assert result.safe_summary["candidates_total"] == 0
    assert result.private_page_results[0]["status"] == "located_no_tables"
    assert result.private_page_results[0]["regions"] == []


def test_invalid_locator_output_fails_closed_without_partial_region() -> None:
    _, _, result = _run_intake(
        StaticDetectorProvider([[150, 100, 850, 900]], malformed=True)
    )

    assert result.safe_summary["status"] == "failed"
    assert result.safe_summary["gate2_boundary_ready"] is False
    assert result.private_candidates == []
    assert result.private_page_results[0]["status"] == "failed"
    assert result.private_detection_attempts[0]["terminal_status"] == "rejected"
    assert (
        result.private_detection_attempts[0]["validation_error_code"]
        == "pdf_table_locator_response_shape_invalid"
    )


def test_locator_v2_rejects_legacy_or_extra_table_fields() -> None:
    invalid_tables = [
        {"box_2d": [150, 100, 850, 900]},
        {
            "table_box_2d": [150, 100, 850, 900],
            "title_box_2d": None,
            "header_box_2d": None,
            "content": "forbidden",
        },
    ]
    for table in invalid_tables:
        _, _, result = _run_intake(
            StaticDetectorProvider([], tables=[table])
        )
        assert result.safe_summary["status"] == "failed"
        assert result.private_page_results[0]["status"] == "failed"
        assert (
            result.private_detection_attempts[0]["validation_error_code"]
            == "pdf_table_locator_table_shape_invalid"
        )


def test_locator_v2_projects_table_title_and_header_geometry_only() -> None:
    table = {
        "table_box_2d": [250, 100, 800, 900],
        "title_box_2d": [150, 100, 220, 500],
        "header_box_2d": [250, 100, 400, 900],
    }
    _, _, result = _run_intake(StaticDetectorProvider([], tables=[table]))
    region = result.private_page_results[0]["regions"][0]
    assert region["table_box_2d_normalized"] == table["table_box_2d"]
    assert region["title_box_2d_normalized"] == table["title_box_2d"]
    assert region["header_box_2d_normalized"] == table["header_box_2d"]
    assert region["bbox_pdf_points"]
    assert region["title_bbox_pdf_points"]
    assert region["header_bbox_pdf_points"]
    assert not any(
        key in region for key in ("text", "content", "continuation", "status")
    )


def test_locator_v2_rejects_overlap_and_header_outside_table() -> None:
    invalid_cases = [
        (
            [
                {
                    "table_box_2d": [200, 100, 600, 900],
                    "title_box_2d": None,
                    "header_box_2d": None,
                },
                {
                    "table_box_2d": [500, 100, 800, 900],
                    "title_box_2d": None,
                    "header_box_2d": None,
                },
            ],
            "pdf_table_locator_table_overlap_invalid",
        ),
        (
            [
                {
                    "table_box_2d": [100, 0, 500, 400],
                    "title_box_2d": None,
                    "header_box_2d": None,
                },
                {
                    "table_box_2d": [200, 500, 300, 900],
                    "title_box_2d": None,
                    "header_box_2d": None,
                },
                {
                    "table_box_2d": [400, 0, 600, 400],
                    "title_box_2d": None,
                    "header_box_2d": None,
                },
            ],
            "pdf_table_locator_table_overlap_invalid",
        ),
        (
            [
                {
                    "table_box_2d": [300, 100, 600, 400],
                    "title_box_2d": None,
                    "header_box_2d": None,
                },
                {
                    "table_box_2d": [700, 100, 900, 400],
                    "title_box_2d": [400, 100, 650, 400],
                    "header_box_2d": None,
                },
            ],
            "pdf_table_locator_title_overlap_invalid",
        ),
        (
            [
                {
                    "table_box_2d": [350, 100, 600, 700],
                    "title_box_2d": [100, 100, 300, 700],
                    "header_box_2d": None,
                },
                {
                    "table_box_2d": [650, 300, 900, 900],
                    "title_box_2d": [200, 250, 500, 900],
                    "header_box_2d": None,
                },
            ],
            "pdf_table_locator_title_overlap_invalid",
        ),
        (
            [
                {
                    "table_box_2d": [300, 100, 800, 900],
                    "title_box_2d": None,
                    "header_box_2d": [200, 100, 400, 900],
                }
            ],
            "pdf_table_locator_header_outside_table",
        ),
    ]
    for tables, expected_code in invalid_cases:
        _, _, result = _run_intake(StaticDetectorProvider([], tables=tables))
        assert result.safe_summary["status"] == "failed"
        assert (
            result.private_detection_attempts[0]["validation_error_code"]
            == expected_code
        )


def test_normalizer_uses_locator_region_pdfplumber_structure_and_source_literals() -> None:
    pdf_bytes, digest, intake = _run_intake(
        StaticDetectorProvider([[180, 80, 820, 920]])
    )
    file_input = FileInput(
        private_ref="file-1",
        original_filename_private="table.pdf",
        mime_type="application/pdf",
        source_kind="unit_test",
        declared_size_bytes=len(pdf_bytes),
        bytes_provider=lambda: pdf_bytes,
        provider_label="unit_test",
    )
    normalized = Gate1Normalizer().normalize(
        [file_input],
        pdf_table_locator_pages_by_sha256={digest: _legacy_locator_pages(intake)},
    )
    projections = [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]

    assert len(projections) == 1
    projection = projections[0]
    assert projection["projection_status"] == "ready"
    assert projection["validator_status"] == "passed"
    assert projection["table_origin"] == "vlm_located_pdfplumber_source_bound"
    assert projection["row_count"] == 3
    assert projection["column_count"] == 3
    assert projection["source_value_refs"]
    assert projection["geometry"]["model_values_used_as_source_literals"] is False
    assert projection["geometry"]["pdfplumber_settings_selected_by_model"] is False
    assert not any(
        item.get("code") == "pdf_table_normalization_incomplete"
        for item in normalized.package["normalization_blockers"]
    )


def test_tight_source_bound_regions_persist_independent_of_fallback_lines(
    tmp_path: Path,
) -> None:
    pdf_bytes = _two_table_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    intake = (
        PdfTableIntakeRuntimeFactory(PdfTableIntakeConfig(enabled=True))
        .create_with_provider(
            StaticDetectorProvider(
                [[107, 80, 229, 919], [426, 80, 549, 919]]
            )
        )
        .run(
            [
                {
                    "document_ref": "pdfsource_tight_regions",
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": digest,
                }
            ]
        )
    )
    file_input = FileInput(
        private_ref="file-tight-regions",
        original_filename_private="tight-regions.pdf",
        mime_type="application/pdf",
        source_kind="unit_test",
        declared_size_bytes=len(pdf_bytes),
        bytes_provider=lambda: pdf_bytes,
        provider_label="unit_test",
    )
    normalizer = Gate1Normalizer()
    run_id = normalizer.plan_run_id([file_input])
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="user-1",
        case_id="case-1",
        chat_id="chat-1",
        workspace_model_id="broker-reports",
        normalization_run_id=run_id,
        allow_private=True,
        require_source_available=True,
    )
    graph = Gate1BoundedGraphFactory(
        Gate1BoundedGraphConfig(
            store=store,
            context=context,
            retention_policy=build_retention_policy(
                mode="customer_approved_test", explicit=True
            ),
            source_file_refs=(
                {
                    "provider": "unit_test",
                    "openwebui_file_id": "file-tight-regions",
                    "content_type": "application/pdf",
                    "size_bytes": len(pdf_bytes),
                    "source_deleted": False,
                },
            ),
        )
    ).create(normalization_run_id=run_id)

    normalized = normalizer.normalize(
        [file_input],
        pdf_table_locator_pages_by_sha256={digest: _legacy_locator_pages(intake)},
        bounded_graph=graph,
    )
    table_units = [
        item
        for item in normalized.package["private_normalized_source_units"]
        if item.get("pdf_unit_type") == "pdf_table_candidate_unit"
    ]
    projections = [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]

    assert len(table_units) == 2
    assert all(not validate_pdf_source_unit_structure(item) for item in table_units)
    assert len(projections) == 2
    assert all(item.get("validator_status") == "passed" for item in projections)
    assert all(
        item.get("table_origin") == "vlm_located_pdfplumber_source_bound"
        for item in projections
    )
    assert graph.compact_receipt()["sealed"] is True

    invalid_locator_unit = dict(table_units[0])
    invalid_locator_unit["table_locator_region_ref"] = None
    assert "pdf_table_source_bound_locator_contract_invalid" in {
        item["code"]
        for item in validate_pdf_source_unit_structure(invalid_locator_unit)
    }
    legacy_without_fallback = dict(table_units[0])
    legacy_without_fallback["table_locator_scope_status"] = None
    legacy_without_fallback["table_fallback_text_refs"] = []
    assert "pdf_table_source_unit_fallback_missing" in {
        item["code"]
        for item in validate_pdf_source_unit_structure(legacy_without_fallback)
    }


def test_rejected_locator_region_preserves_valid_tables_but_blocks_canonical(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pdf_bytes = _two_table_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    intake = (
        PdfTableIntakeRuntimeFactory(PdfTableIntakeConfig(enabled=True))
        .create_with_provider(
            StaticDetectorProvider(
                [
                    [107, 80, 229, 919],
                    [426, 80, 549, 919],
                ]
            )
        )
        .run(
            [
                {
                    "document_ref": "pdfsource_false_locator_region",
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": digest,
                }
            ]
        )
    )
    assert intake.safe_summary["candidates_total"] == 2

    original_find = PdfPlumberLayoutAdapter._find_unbounded_table_candidates
    calls = 0

    def fail_second_region(self, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("native extraction rejected")
        return original_find(self, **kwargs)

    monkeypatch.setattr(
        PdfPlumberLayoutAdapter,
        "_find_unbounded_table_candidates",
        fail_second_region,
    )

    file_input = FileInput(
        private_ref="file-false-locator-region",
        original_filename_private="false-locator-region.pdf",
        mime_type="application/pdf",
        source_kind="unit_test",
        declared_size_bytes=len(pdf_bytes),
        bytes_provider=lambda: pdf_bytes,
        provider_label="unit_test",
    )
    normalized = Gate1Normalizer().normalize(
        [file_input],
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_read_enabled": True,
            "normalizer_version": "false-locator-region-terminal-test-v1",
        },
            pdf_table_locator_pages_by_sha256={digest: _legacy_locator_pages(intake)},
    )
    projections = [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    assert len(projections) == 1
    assert all(
        item.get("projection_status") == "ready"
        and item.get("validator_status") == "passed"
        for item in projections
    )
    assert any(
        item.get("code") == "pdf_table_normalization_incomplete"
        for item in normalized.package["normalization_blockers"]
    )
    page = normalized.package["private_normalized_source_payloads"][0][
        "pdf_text_layer_projection"
    ]["page_inventory"][0]
    assert page["table_locator_regions_total"] == 2
    assert page["table_locator_regions_accepted_total"] == 1
    assert page["table_locator_regions_rejected_total"] == 1
    assert "pdf_table_locator_region_native_extraction_rejected" in (
        page["table_reason_codes"]
    )

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="user-1",
        case_id="case-false-locator-region",
        chat_id="chat-false-locator-region",
        workspace_model_id="broker_reports_ndfl",
        normalization_run_id=normalized.package["normalization_run"]["run_id"],
        allow_private=True,
        require_source_available=True,
    )
    manifest = persist_gate1_result(
        store=store,
        result=normalized,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
    )

    assert "broker_reports_canonical_build_failure_v1" in (
        manifest.artifact_refs_by_type
    )
    assert "broker_reports_canonical_artifact_v1" not in manifest.artifact_refs_by_type


def test_source_bound_header_only_table_is_preserved_as_projection() -> None:
    pdf_bytes = _header_only_table_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    normalized = Gate1Normalizer().normalize(
        [
            FileInput(
                private_ref="header-only-table",
                original_filename_private="header-only-table.pdf",
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
                    "page_number": 1,
                    "status": "located",
                    "regions": [
                        {
                            "region_ref": "header-only-region",
                            "bbox_pdf_points": [9.0, 24.0, 231.0, 66.0],
                            "model_values_used_as_source_literals": False,
                            "pdfplumber_settings_selected_by_model": False,
                        }
                    ],
                }
            ]
        },
    )

    projections = [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    assert len(projections) == 1
    assert projections[0]["row_count"] == 1
    assert projections[0]["column_count"] == 3
    assert projections[0]["projection_status"] == "ready"
    assert not any(
        item.get("code") == "pdf_table_normalization_incomplete"
        for item in normalized.package["normalization_blockers"]
    )


def test_source_bound_horizontally_framed_header_is_preserved() -> None:
    pdf_bytes = _horizontally_framed_header_only_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    normalized = Gate1Normalizer().normalize(
        [
            FileInput(
                private_ref="framed-header",
                original_filename_private="framed-header.pdf",
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
                    "page_number": 1,
                    "status": "located",
                    "regions": [
                        {
                            "region_ref": "framed-header-region",
                            "bbox_pdf_points": [9.0, 24.0, 231.0, 66.0],
                            "model_values_used_as_source_literals": False,
                            "pdfplumber_settings_selected_by_model": False,
                        }
                    ],
                }
            ]
        },
    )

    projections = [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    assert len(projections) == 1
    assert projections[0]["row_count"] == 1
    assert projections[0]["column_count"] == 3
    assert projections[0]["projection_status"] == "ready"
    assert "source_bound_single_band_alignment_fallback" in (
        projections[0]["reconstruction_reason_codes"]
    )
    assert not any(
        item.get("code") == "pdf_table_normalization_incomplete"
        for item in normalized.package["normalization_blockers"]
    )


def test_source_bound_borderless_single_data_row_is_preserved() -> None:
    pdf_bytes = _borderless_single_data_row_table_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    normalized = Gate1Normalizer().normalize(
        [
            FileInput(
                private_ref="single-data-row",
                original_filename_private="single-data-row.pdf",
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
                    "page_number": 1,
                    "status": "located",
                    "regions": [
                        {
                            "region_ref": "single-data-row-region",
                            "bbox_pdf_points": [9.0, 20.0, 311.0, 72.0],
                            "model_values_used_as_source_literals": False,
                            "pdfplumber_settings_selected_by_model": False,
                        }
                    ],
                }
            ]
        },
    )

    projections = [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    assert len(projections) == 1
    assert projections[0]["row_count"] == 2
    assert projections[0]["column_count"] == 3
    assert projections[0]["projection_status"] == "ready"
    assert not any(
        item.get("code") == "pdf_table_normalization_incomplete"
        for item in normalized.package["normalization_blockers"]
    )


def test_borderless_table_compacts_only_empty_parser_axes() -> None:
    pdf_bytes = _borderless_aligned_table_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    normalized = Gate1Normalizer().normalize(
        [
            FileInput(
                private_ref="borderless-grid",
                original_filename_private="borderless-grid.pdf",
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
                    "page_number": 1,
                    "status": "located",
                    "regions": [
                        {
                            "region_ref": "borderless-grid-region",
                            "bbox_pdf_points": [9.0, 15.0, 305.0, 105.0],
                            "model_values_used_as_source_literals": False,
                            "pdfplumber_settings_selected_by_model": False,
                        }
                    ],
                }
            ]
        },
    )
    projection = next(
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    )

    assert projection["projection_status"] == "ready"
    assert projection["row_count"] == 3
    assert projection["column_count"] == 3
    assert projection["cell_count"] == 9
    assert "empty_grid_axes_compacted" in projection["reconstruction_reason_codes"]


def test_tight_locator_margin_and_merged_grid_survive_into_canonical() -> None:
    pdf_bytes = _merged_header_table_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    original_locator_bbox = [9.5, 19.5, 289.5, 110.5]
    file_input = FileInput(
        private_ref="merged-grid",
        original_filename_private="merged-grid.pdf",
        mime_type="application/pdf",
        source_kind="unit_test",
        declared_size_bytes=len(pdf_bytes),
        bytes_provider=lambda: pdf_bytes,
        provider_label="unit_test",
    )

    normalized = Gate1Normalizer().normalize(
        [file_input],
        pdf_table_locator_pages_by_sha256={
            digest: [
                {
                    "page_number": 1,
                    "status": "located",
                    "regions": [
                        {
                            "region_ref": "merged-grid-region",
                            "bbox_pdf_points": original_locator_bbox,
                            "model_values_used_as_source_literals": False,
                            "pdfplumber_settings_selected_by_model": False,
                        }
                    ],
                }
            ]
        },
    )
    projection = next(
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    )

    assert projection["projection_status"] == "ready"
    assert projection["row_count"] == 4
    assert projection["column_count"] == 4
    assert projection["geometry"]["table_locator_bbox_pdf_points"] == (
        original_locator_bbox
    )
    spans = {
        (item["row_ordinal"], item["column_ordinal"]): (
            item["row_span"],
            item["column_span"],
        )
        for item in projection["cells"]
    }
    assert spans[(1, 1)] == (2, 1)
    assert spans[(1, 2)] == (1, 2)
    assert (2, 1) not in spans
    assert (1, 3) not in spans

    document = normalized.package["document_inventory"]["documents"][0]
    canonical = (
        CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="merged-grid-test-v1")
        )
        .create()
        .build(
            tenant_id="tenant",
            artifact_version=1,
            document=document,
            source_artifact_ref="source-merged-grid",
            source_payloads=normalized.package["private_normalized_source_payloads"],
            source_units=normalized.package["private_normalized_source_units"],
            table_projections=normalized.package[
                "private_normalized_table_projections"
            ],
        )
    )
    table = next(item for item in canonical["nodes"] if item["node_type"] == "TABLE")
    merged_ranges = {
        item["merged_range"]
        for item in table["content"]["cells"]
        if item["merged_range"]
    }
    assert {"R1C1:R2C1", "R1C2:R1C3"} <= merged_ranges


def test_cross_page_table_segments_get_only_strict_structural_link() -> None:
    def normalize(second_page_header: bool):
        pdf_bytes = _two_page_table_pdf(second_page_header=second_page_header)
        digest = hashlib.sha256(pdf_bytes).hexdigest()
        return Gate1Normalizer().normalize(
            [
                FileInput(
                    private_ref=f"continuation-{second_page_header}",
                    original_filename_private="continuation.pdf",
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
                        "page_number": 1,
                        "status": "located",
                        "regions": [
                            {
                                "region_ref": "continuation-start",
                                "bbox_pdf_points": [19.5, 219.5, 299.5, 318.5],
                                "model_values_used_as_source_literals": False,
                                "pdfplumber_settings_selected_by_model": False,
                            }
                        ],
                    },
                    {
                        "page_number": 2,
                        "status": "located",
                        "regions": [
                            {
                                "region_ref": "continuation-end",
                                "bbox_pdf_points": [19.5, 1.5, 299.5, 77.5],
                                "model_values_used_as_source_literals": False,
                                "pdfplumber_settings_selected_by_model": False,
                            }
                        ],
                    },
                ]
            },
        )

    linked = normalize(False)
    projections = [
        item
        for item in linked.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    assert len(projections) == 2
    assert {item["projection_status"] for item in projections} == {"ready"}
    assert len({item.get("logical_table_id") for item in projections}) == 1
    assert None not in {item.get("logical_table_id") for item in projections}
    assert [item["continuation"]["role"] for item in projections] == [
        "start",
        "end",
    ]
    assert (
        projections[0]["continuation"]["next_table_projection_ref"]
        == projections[1]["table_projection_id"]
    )
    assert (
        projections[1]["continuation"]["previous_table_projection_ref"]
        == projections[0]["table_projection_id"]
    )
    broken_link = copy.deepcopy(projections[0])
    broken_link["continuation"]["next_table_projection_ref"] = None
    assert "pdf_table_continuation_role_refs_invalid" in {
        item["code"]
        for item in TableProjectionValidator().validate(broken_link)["errors"]
    }

    document = linked.package["document_inventory"]["documents"][0]
    canonical = (
        CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="continuation-test-v1")
        )
        .create()
        .build(
            tenant_id="tenant",
            artifact_version=1,
            document=document,
            source_artifact_ref="source-continuation",
            source_payloads=linked.package["private_normalized_source_payloads"],
            source_units=linked.package["private_normalized_source_units"],
            table_projections=projections,
        )
    )
    tables = [item for item in canonical["nodes"] if item["node_type"] == "TABLE"]
    assert len(tables) == 2
    assert {item["content"]["metadata"]["logical_table_id"] for item in tables} == {
        projections[0]["logical_table_id"]
    }

    independently_headed = normalize(True)
    independent_projections = [
        item
        for item in independently_headed.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    assert len(independent_projections) == 2
    assert all("logical_table_id" not in item for item in independent_projections)
    assert all("continuation" not in item for item in independent_projections)


def test_missing_or_failed_locator_page_blocks_table_normalization() -> None:
    pdf_bytes = _single_page_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    file_input = FileInput(
        private_ref="file-1",
        original_filename_private="table.pdf",
        mime_type="application/pdf",
        source_kind="unit_test",
        declared_size_bytes=len(pdf_bytes),
        bytes_provider=lambda: pdf_bytes,
        provider_label="unit_test",
    )
    normalized = Gate1Normalizer().normalize(
        [file_input],
        pdf_table_locator_pages_by_sha256={
            digest: [{"page_number": 1, "status": "failed", "regions": []}]
        },
    )

    assert not [
        item
        for item in normalized.package["private_normalized_table_projections"]
        if item.get("source_format") == "pdf"
    ]
    assert any(
        item.get("code") == "pdf_table_normalization_incomplete"
        and item.get("blocks_next_gate") is True
        for item in normalized.package["normalization_blockers"]
    )


def test_incomplete_pdf_table_normalization_cannot_publish_canonical_candidate(
    tmp_path: Path,
) -> None:
    pdf_bytes = _single_page_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    file_input = FileInput(
        private_ref="file-incomplete-table",
        original_filename_private="incomplete-table.pdf",
        mime_type="application/pdf",
        source_kind="unit_test",
        declared_size_bytes=len(pdf_bytes),
        bytes_provider=lambda: pdf_bytes,
        provider_label="unit_test",
    )
    normalized = Gate1Normalizer().normalize(
        [file_input],
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_read_enabled": True,
            "normalizer_version": "canonical-table-contract-test-v1",
        },
        pdf_table_locator_pages_by_sha256={
            digest: [{"page_number": 1, "status": "failed", "regions": []}]
        },
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="user-1",
        case_id="case-incomplete-table",
        chat_id="chat-incomplete-table",
        workspace_model_id="broker-reports-ndfl",
        normalization_run_id=normalized.package["normalization_run"]["run_id"],
        allow_private=True,
        require_source_available=True,
    )

    manifest = persist_gate1_result(
        store=store,
        result=normalized,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
    )

    assert "broker_reports_canonical_artifact_v1" not in manifest.artifact_refs_by_type
    failure_ref = manifest.artifact_refs_by_type[
        "broker_reports_canonical_build_failure_v1"
    ][0]
    failure = store.get_record_unchecked(failure_ref)
    assert failure is not None
    assert failure.safe_metadata == {
        "failure_code": "canonical_pdf_table_normalization_incomplete",
        "canonical_required": True,
        "legacy_fallback_used": False,
        "downstream_status": "blocked",
        "cutover_authorized": False,
    }


def test_coordinate_contract_is_explicitly_recorded() -> None:
    assert (
        PDF_TABLE_LOCATOR_COORDINATE_CONTRACT
        == "gemini_box_2d_ymin_xmin_ymax_xmax_normalized_0_1000"
    )


def test_pipe_and_bundle_builder_use_the_maintained_factory_path() -> None:
    pipe_source = (ROOT / "openwebui_actions/broker_reports_gate1_pipe.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (
        ROOT / "broker_reports_gate1/pdf_table_intake_runtime.py"
    ).read_text(encoding="utf-8")
    bundle_builder = (ROOT / "scripts/build_openwebui_pipe_bundle.py").read_text(
        encoding="utf-8"
    )
    assert "PdfTableIntakeRuntimeFactory(config)" in pipe_source
    assert "pdf_table_locator_pages_by_sha256=locator_pages_by_sha256" in pipe_source
    assert "PdfTableLocatorProjectionFactory" in runtime_source
    assert '"pdf_table_locator"' in bundle_builder
