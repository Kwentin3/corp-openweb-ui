from __future__ import annotations

import ast
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from broker_reports_gate1.visual_pdfplumber_table_plan import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    TERMINAL_EXTRACTED,
    TERMINAL_NO_TABLE,
    VisualPdfPlumberTableAdapterFactory,
    VisualPdfPlumberTablePlanError,
    _image_bbox_to_pdf,
    validate_pdfplumber_table_plan,
)


def _font_resource(writer: PdfWriter):
    return writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )


def _pdf(*, texts: list[tuple[float, float, str]], vectors: list[str] | None = None) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=320, height=320)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): _font_resource(writer)})}
    )
    operators = [
        f"BT /F1 10 Tf {x:g} {y:g} Td ({value}) Tj ET"
        for x, y, value in texts
    ]
    operators.extend(vectors or [])
    stream = DecodedStreamObject()
    stream.set_data("\n".join(operators).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _ruled_pdf() -> bytes:
    return _pdf(
        texts=[
            (30, 260, "Synthetic Table"),
            (30, 220, "Date"),
            (125, 220, "Amount"),
            (225, 220, "Currency"),
            (30, 195, "2026-01-01"),
            (125, 195, "10.00"),
            (225, 195, "USD"),
            (30, 170, "2026-01-02"),
            (125, 170, "20.00"),
            (225, 170, "EUR"),
            (30, 130, "Outside table note"),
        ],
        vectors=[
            "20 155 m 300 155 l S",
            "20 180 m 300 180 l S",
            "20 205 m 300 205 l S",
            "20 230 m 300 230 l S",
            "20 155 m 20 230 l S",
            "110 155 m 110 230 l S",
            "210 155 m 210 230 l S",
            "300 155 m 300 230 l S",
        ],
    )


def _borderless_pdf() -> bytes:
    rows = [
        (250, "Date", "Amount", "Currency"),
        (225, "2026-01-01", "10.00", "USD"),
        (200, "2026-01-02", "20.00", "EUR"),
        (175, "2026-01-03", "30.00", "GBP"),
    ]
    return _pdf(
        texts=[
            value
            for y, left, middle, right in rows
            for value in ((25, y, left), (130, y, middle), (235, y, right))
        ]
    )


def _ruled_plan() -> dict:
    return {
        "tables": [
            {
                "bbox": [19, 89, 301, 166],
                "vertical_strategy": "explicit",
                "explicit_vertical_lines": [20, 110, 210, 300],
                "horizontal_strategy": "lines",
            }
        ]
    }


def test_g5100_plan_is_exact_native_whitelist_and_fails_closed() -> None:
    validate_pdfplumber_table_plan(
        _ruled_plan(), image_width_pixels=320, image_height_pixels=320
    )
    invalid_plans = [
        {"tables": [{**_ruled_plan()["tables"][0], "body_values": ["10.00"]}]},
        {"tables": [{**_ruled_plan()["tables"][0], "snap_tolerance": 2}]},
        {
            "tables": [
                {**_ruled_plan()["tables"][0], "vertical_strategy": "lines"}
            ]
        },
        {
            "tables": [
                {
                    **_ruled_plan()["tables"][0],
                    "explicit_vertical_lines": [20, 210, 110, 300],
                }
            ]
        },
    ]
    for value in invalid_plans:
        with pytest.raises(VisualPdfPlumberTablePlanError):
            validate_pdfplumber_table_plan(
                value, image_width_pixels=320, image_height_pixels=320
            )


def test_g5100_coordinate_transform_is_only_axis_scaling() -> None:
    assert _image_bbox_to_pdf(
        [100, 200, 500, 800],
        image_width_pixels=1000,
        image_height_pixels=1000,
        pdf_width=600,
        pdf_height=800,
    ) == (60.0, 160.0, 300.0, 640.0)


def test_g5100_ruled_native_plan_builds_one_existing_canonical() -> None:
    result = VisualPdfPlumberTableAdapterFactory().create().execute_single_page(
        pdf_bytes=_ruled_pdf(),
        image_width_pixels=320,
        image_height_pixels=320,
        plan=_ruled_plan(),
        document_id="g5100_ruled",
    )
    assert result["terminal"] == TERMINAL_EXTRACTED
    assert [(item["rows_total"], item["columns_total"]) for item in result["native_tables"]] == [(3, 3)]
    assert result["vlm_body_values_used"] == 0
    assert result["invented_source_literals"] == 0
    assert result["canonical"]["schema_version"] == "canonical_artifact_v1"
    assert result["canonical_metrics"] == {
        "canonical_valid": True,
        "canonical_tables": 1,
        "canonical_text_nodes": 1,
        "source_atom_accounting_percent": 100.0,
        "unresolved_source_atoms_total": 0,
        "table_text_duplicate_reduction_percent": 100.0,
        "layout_selected_refs": 19,
        "layout_accounted_refs": 19,
        "layout_duplicate_refs": 0,
        "layout_unaccounted_refs": 0,
        "ready_table_projections": 1,
        "blocked_table_projections": 0,
    }
    projection = result["table_projections"][0]
    assert projection["projection_status"] == "ready"
    assert projection["source_value_refs"]
    assert {item["normalized_value"] for item in projection["private_values"]} >= {
        "Date",
        "10.00",
        "USD",
    }


def test_g5100_borderless_native_text_rows_remain_source_bound() -> None:
    plan = {
        "tables": [
            {
                "bbox": [20, 55, 275, 155],
                "vertical_strategy": "explicit",
                "explicit_vertical_lines": [25, 110, 210, 257],
                "horizontal_strategy": "text",
            }
        ]
    }
    result = VisualPdfPlumberTableAdapterFactory().create().execute_single_page(
        pdf_bytes=_borderless_pdf(),
        image_width_pixels=320,
        image_height_pixels=320,
        plan=plan,
        document_id="g5100_borderless",
    )
    assert result["terminal"] == TERMINAL_EXTRACTED
    assert result["native_tables"][0]["columns_total"] == 3
    assert result["canonical_metrics"]["source_atom_accounting_percent"] == 100.0
    assert result["canonical_metrics"]["layout_duplicate_refs"] == 0
    assert result["canonical_metrics"]["layout_unaccounted_refs"] == 0
    assert result["table_projections"][0]["source_value_refs"]


def test_g5100_empty_plan_preserves_ordinary_page_text() -> None:
    result = VisualPdfPlumberTableAdapterFactory().create().execute_single_page(
        pdf_bytes=_pdf(
            texts=[
                (20, 290, "Synthetic Broker Report"),
                (20, 270, "Account summary for period"),
                (20, 250, "Amount 10.00 USD"),
            ]
        ),
        image_width_pixels=320,
        image_height_pixels=320,
        plan={"tables": []},
        document_id="g5100_prose",
    )
    assert result["terminal"] == TERMINAL_NO_TABLE
    assert result["canonical_metrics"]["canonical_tables"] == 0
    assert result["canonical_metrics"]["canonical_text_nodes"] == 1
    assert result["canonical_metrics"]["source_atom_accounting_percent"] == 100.0


def test_g5100_is_private_factory_path_without_old_repair_imports() -> None:
    assert "Factory.create" in FACTORY_REQUIRED
    assert "breadcrumb" in FORBIDDEN
    source_path = Path(__file__).parents[1] / "broker_reports_gate1" / "visual_pdfplumber_table_plan.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(
        marker in imported
        for imported in imports
        for marker in ("g596", "g597", "g598", "breadcrumb", "visual_table_review")
    )
