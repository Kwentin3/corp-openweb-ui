from __future__ import annotations

import ast
import base64
import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from broker_reports_gate1.pdf_native_navigation_overlay import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    NativePdfPointNavigationOverlayError,
    NativePdfPointNavigationOverlayFactory,
    _grid_values,
)
from broker_reports_gate1.pdf_table_raster import (
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from broker_reports_gate1.visual_pdfplumber_table_plan import (
    VisualPdfPlumberTablePlanError,
)
from scripts.local_pdf_native_navigation_g5101 import (
    _execution_plan,
    _region_evidence,
)


def _page_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=320, height=320)
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 10 Tf 20 280 Td (Native navigation control) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _full_page_render() -> tuple[bytes, dict]:
    pdf = _page_pdf()
    digest = hashlib.sha256(pdf).hexdigest()
    value = PdfTableRasterFactory(
        PdfTableRasterConfig(padding_points=0)
    ).create().render_full_page(
        pdf_bytes=pdf,
        pdf_sha256=digest,
        document_ref="g5101_control",
        page_ref="g5101_page_001",
        page_number=1,
        expected_page_bbox=[0.0, 0.0, 320.0, 320.0],
        dpi=150,
    )
    return base64.b64decode(value["private_png_base64"]), value["manifest"]


def test_g5101_overlay_is_deterministic_native_point_navigation() -> None:
    png, raster_manifest = _full_page_render()
    renderer = NativePdfPointNavigationOverlayFactory().create()
    first = renderer.apply(
        page_png_bytes=png,
        raster_manifest=raster_manifest,
        expected_page_bbox=[0.0, 0.0, 320.0, 320.0],
    )
    second = renderer.apply(
        page_png_bytes=png,
        raster_manifest=raster_manifest,
        expected_page_bbox=[0.0, 0.0, 320.0, 320.0],
    )
    assert first == second
    output = base64.b64decode(first["private_png_base64"])
    manifest = first["manifest"]
    assert hashlib.sha256(output).hexdigest() == manifest["output_png_sha256"]
    assert manifest["native_coordinate_space"] == "pdfplumber_top_left_points"
    assert manifest["native_coordinate_bounds"] == [0.0, 0.0, 320.0, 320.0]
    assert manifest["plan_to_pdfplumber_transform"] == "identity"
    assert manifest["source_page_pixels_resized"] is False
    assert manifest["source_page_pixels_covered_by_labels"] is False
    assert manifest["output_width"] == manifest["input_width"] + 102
    assert manifest["output_height"] == manifest["input_height"] + 76


def test_g5101_overlay_rejects_unverified_or_rotated_render() -> None:
    png, raster_manifest = _full_page_render()
    renderer = NativePdfPointNavigationOverlayFactory().create()
    for key, value in (
        ("full_page_identity_verified", False),
        ("render_scope", "crop"),
        ("page_rotation", 90),
    ):
        invalid = {**raster_manifest, key: value}
        with pytest.raises(
            NativePdfPointNavigationOverlayError,
            match="g5101_overlay_raster_contract_invalid",
        ):
            renderer.apply(
                page_png_bytes=png,
                raster_manifest=invalid,
                expected_page_bbox=[0.0, 0.0, 320.0, 320.0],
            )


def test_g5101_overlay_rejects_hash_and_bbox_drift() -> None:
    png, raster_manifest = _full_page_render()
    renderer = NativePdfPointNavigationOverlayFactory().create()
    with pytest.raises(
        NativePdfPointNavigationOverlayError,
        match="g5101_overlay_png_hash_mismatch",
    ):
        renderer.apply(
            page_png_bytes=png + b"drift",
            raster_manifest=raster_manifest,
            expected_page_bbox=[0.0, 0.0, 320.0, 320.0],
        )
    with pytest.raises(
        NativePdfPointNavigationOverlayError,
        match="g5101_overlay_page_bbox_mismatch",
    ):
        renderer.apply(
            page_png_bytes=png,
            raster_manifest=raster_manifest,
            expected_page_bbox=[0.0, 0.0, 300.0, 320.0],
        )


def test_g5101_grid_values_preserve_native_page_boundaries() -> None:
    assert _grid_values(0.0, 100.0, 18.0) == [
        0.0,
        18.0,
        36.0,
        54.0,
        72.0,
        90.0,
        100.0,
    ]


def test_g5101_overlay_is_private_and_does_not_render_source_pdf() -> None:
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not render source PDFs" in FORBIDDEN
    source_path = (
        Path(__file__).parents[1]
        / "broker_reports_gate1"
        / "pdf_native_navigation_overlay.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        marker in module
        for module in imported_modules
        for marker in ("pdf_layout", "pdf_text_layer", "pdf_table_raster")
    )


def test_g5101_plan_has_three_model_fields_and_fixed_native_strategy() -> None:
    value = {
        "tables": [
            {
                "bbox": [20, 80, 300, 180],
                "explicit_vertical_lines": [20, 110, 210, 300],
                "horizontal_strategy": "lines",
            }
        ]
    }
    assert _execution_plan(value, page_width=320, page_height=320) == {
        "tables": [
            {
                "bbox": [20, 80, 300, 180],
                "vertical_strategy": "explicit",
                "explicit_vertical_lines": [20, 110, 210, 300],
                "horizontal_strategy": "lines",
            }
        ]
    }
    with pytest.raises(VisualPdfPlumberTablePlanError):
        _execution_plan(
            {
                "tables": [
                    {
                        **value["tables"][0],
                        "snap_tolerance": 3,
                    }
                ]
            },
            page_width=320,
            page_height=320,
        )


def test_g5101_region_evidence_uses_native_pdf_point_bbox() -> None:
    parser_page = {
        "line_inventory": [
            {"parser_ordinal": 1, "bbox": [20, 20, 100, 30]},
            {"parser_ordinal": 2, "bbox": [20, 40, 100, 50]},
            {"parser_ordinal": 3, "bbox": [20, 60, 100, 70]},
            {"parser_ordinal": 4, "bbox": [20, 100, 100, 110]},
        ]
    }
    evidence = _region_evidence(
        parser_page=parser_page,
        native_plan={
            "tables": [
                {
                    "bbox": [10, 35, 110, 75],
                    "explicit_vertical_lines": [10, 110],
                    "horizontal_strategy": "text",
                }
            ]
        },
        expected_regions=[(2, 3)],
    )
    assert evidence == [
        {
            "plan_ordinal": 1,
            "truth_region_expressible": True,
            "expected_line_ordinal_range": [2, 3],
            "selected_line_ordinals": [2, 3],
            "truth_coverage_percent": 100.0,
            "extraneous_lines_total": 0,
            "exact_region_match": True,
        }
    ]


def test_g5101_harness_uses_factories_without_old_repair_path() -> None:
    source_path = (
        Path(__file__).parents[1]
        / "scripts"
        / "local_pdf_native_navigation_g5101.py"
    )
    source = source_path.read_text(encoding="utf-8")
    for required in (
        "PdfTableRasterFactory(",
        "NativePdfPointNavigationOverlayFactory().create()",
        "VisualPdfPlumberTableAdapterFactory().create()",
        "provider.invoke(",
    ):
        assert required in source
    for forbidden in (
        "local_addressable_visual_breadcrumb_g598",
        "local_native_table_engine_g597",
        "local_vlm_table_layout_contract_g596",
        "snap_tolerance",
        "join_tolerance",
        "intersection_tolerance",
    ):
        assert forbidden not in source
