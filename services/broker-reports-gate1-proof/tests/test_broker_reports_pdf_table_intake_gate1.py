from __future__ import annotations

import copy
import hashlib
import os
import shutil
import sys
from pathlib import Path

import fitz

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
from broker_reports_gate1.normalizer import Gate1Normalizer  # noqa: E402
from broker_reports_gate1.pdf_layout import PdfPlumberLayoutAdapter  # noqa: E402
from broker_reports_gate1.pdf_text_layer import (  # noqa: E402
    validate_pdf_source_unit_structure,
)
from broker_reports_gate1.pdf_table_intake_runtime import (  # noqa: E402
    PdfTableIntakeConfig,
    PdfTableIntakeRuntimeFactory,
)
from broker_reports_gate1.pdf_table_locator import (  # noqa: E402
    PDF_TABLE_LOCATOR_COORDINATE_CONTRACT,
    PDF_TABLE_LOCATOR_PROMPT,
)
from broker_reports_gate1.table_projection import (  # noqa: E402
    TableProjectionValidator,
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

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    monkeypatch.setattr(
        "broker_reports_gate1.canonical_store.shutil.disk_usage",
        lambda _: shutil._ntuple_diskusage(10_000_000_000, 1_000_000_000, 9_000_000_000),
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
    def __init__(self, boxes: list[list[int]], *, malformed: bool = False) -> None:
        self.boxes = boxes
        self.malformed = malformed
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
        value = {"tables": [{"box_2d": box} for box in self.boxes]}
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


def test_locator_prompt_is_native_coordinates_and_locator_only() -> None:
    model_view = (
        PdfTableIntakeRuntimeFactory(PdfTableIntakeConfig(enabled=True))
        .create_with_provider(StaticDetectorProvider([]))
        ._model_view(request_id="request-1", page_number=1)
    )
    assert model_view["task"] == PDF_TABLE_LOCATOR_PROMPT
    assert "[ymin, xmin, ymax, xmax]" in model_view["task"]
    assert "Never use one box that encloses two distinct grids" in model_view["task"]
    assert "no visible data row is not a data table" in model_view["task"]
    assert "verify that at least one such body row is visibly present" in model_view["task"]
    assert "Do not transcribe text" in model_view["task"]


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
    assert page["status"] == "located"
    assert page["pdf_sha256"] == digest
    assert len(page["regions"]) == 1
    assert page["regions"][0]["box_2d_normalized"] == [150, 100, 850, 900]
    assert page["model_values_used_as_source_literals"] is False
    assert page["pdfplumber_settings_selected_by_model"] is False


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
        pdf_table_locator_pages_by_sha256={digest: intake.private_page_results},
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
        pdf_table_locator_pages_by_sha256={digest: intake.private_page_results},
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
        pdf_table_locator_pages_by_sha256={digest: intake.private_page_results},
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
