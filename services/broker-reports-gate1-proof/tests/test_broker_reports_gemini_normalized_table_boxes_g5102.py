from __future__ import annotations

import copy
from pathlib import Path

import pytest

from broker_reports_gate1.gemini_normalized_table_boxes import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA,
    GeminiNormalizedTableBoxError,
    GeminiNormalizedTableBoxProjectionFactory,
    response_schema_copy,
)
from broker_reports_gate1.pdf_hybrid_provider import project_gemini_schema


SERVICE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gemini_normalized_table_boxes.py"
)
HARNESS_PATH = SERVICE_ROOT / "scripts" / "local_gemini_table_boxes_g5102.py"
PACKAGE_INIT = SERVICE_ROOT / "broker_reports_gate1" / "__init__.py"


def _manifest() -> dict[str, object]:
    return {
        "render_scope": "full_page",
        "full_page_identity_verified": True,
        "source_coordinate_space": "pdf_top_left_points",
        "pixel_coordinate_space": "crop_top_left_pixels",
        "lossless": True,
        "silent_resize_performed": False,
        "page_rotation": 0,
        "applied_rotation": 0,
        "actual_page_bbox": [0.0, 0.0, 500.0, 1000.0],
        "rendered_bbox": [0.0, 0.0, 500.0, 1000.0],
        "width": 1000,
        "height": 2000,
        "source_to_pixel_transform": {
            "scale_x": 2.0,
            "scale_y": 2.0,
            "translate_source_x": 0.0,
            "translate_source_y": 0.0,
        },
        "manifest_hash": "synthetic_full_page_manifest",
    }


def test_g5102_schema_uses_documented_box_2d_contract() -> None:
    schema = GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA
    assert set(schema) == {"type", "additionalProperties", "required", "properties"}
    assert schema["required"] == ["tables"]
    table = schema["properties"]["tables"]["items"]
    assert table["required"] == ["box_2d"]
    assert set(table["properties"]) == {"box_2d"}
    box = table["properties"]["box_2d"]
    assert "[ymin, xmin, ymax, xmax]" in box["description"]
    assert box["minItems"] == 4
    assert box["maxItems"] == 4
    assert box["items"] == {"type": "integer", "minimum": 0, "maximum": 1000}
    clone = response_schema_copy()
    assert clone == schema
    assert clone is not schema


def test_g5102_gemini_projection_retains_semantics_and_numeric_bounds() -> None:
    adapted, _ = project_gemini_schema(response_schema_copy())
    box = adapted["properties"]["tables"]["items"]["properties"]["box_2d"]
    assert "[ymin, xmin, ymax, xmax]" in box["description"]
    assert box["minItems"] == 4
    assert box["items"]["type"] == "integer"
    assert box["items"]["minimum"] == 0
    assert box["items"]["maximum"] == 1000


def test_g5102_projects_normalized_full_image_box_to_pdf_points() -> None:
    projection = GeminiNormalizedTableBoxProjectionFactory().create()
    result = projection.project(
        provider_value={"tables": [{"box_2d": [100, 200, 600, 800]}]},
        raster_manifest=_manifest(),
        expected_page_bbox=[0.0, 0.0, 500.0, 1000.0],
    )
    assert result["coordinate_contract"] == (
        "gemini_box_2d_ymin_xmin_ymax_xmax_normalized_0_1000"
    )
    assert result["tables"] == [
        {
            "ordinal": 1,
            "box_2d_normalized": [100, 200, 600, 800],
            "bbox_pdf_points": [100.0, 100.0, 400.0, 600.0],
        }
    ]
    assert result["model_values_used_as_source_literals"] is False
    assert result["table_structure_inferred"] is False
    assert len(result["projection_hash"]) == 64


@pytest.mark.parametrize(
    ("provider_value", "code"),
    [
        ({"tables": [], "extra": True}, "g5102_response_shape_invalid"),
        ({"tables": [{"bbox": [1, 2, 3, 4]}]}, "g5102_table_shape_invalid"),
        ({"tables": [{"box_2d": [1, 2, 3]}]}, "g5102_box_2d_invalid"),
        ({"tables": [{"box_2d": [1.0, 2, 3, 4]}]}, "g5102_box_2d_invalid"),
        ({"tables": [{"box_2d": [-1, 2, 3, 4]}]}, "g5102_box_2d_out_of_range"),
        ({"tables": [{"box_2d": [1, 2, 1, 4]}]}, "g5102_box_2d_order_invalid"),
        (
            {"tables": [{"box_2d": [500, 10, 600, 20]}, {"box_2d": [100, 30, 200, 40]}]},
            "g5102_tables_not_top_to_bottom",
        ),
    ],
)
def test_g5102_rejects_ambiguous_or_out_of_contract_values(
    provider_value: dict[str, object], code: str
) -> None:
    projection = GeminiNormalizedTableBoxProjectionFactory().create()
    with pytest.raises(GeminiNormalizedTableBoxError) as exc_info:
        projection.project(
            provider_value=provider_value,
            raster_manifest=_manifest(),
            expected_page_bbox=[0.0, 0.0, 500.0, 1000.0],
        )
    assert exc_info.value.code == code


def test_g5102_requires_verified_full_page_owner_transform() -> None:
    projection = GeminiNormalizedTableBoxProjectionFactory().create()
    manifest = _manifest()
    manifest["render_scope"] = "crop"
    with pytest.raises(GeminiNormalizedTableBoxError) as exc_info:
        projection.project(
            provider_value={"tables": []},
            raster_manifest=manifest,
            expected_page_bbox=[0.0, 0.0, 500.0, 1000.0],
        )
    assert exc_info.value.code == "g5102_raster_manifest_invalid"

    manifest = _manifest()
    transform = copy.deepcopy(manifest["source_to_pixel_transform"])
    assert isinstance(transform, dict)
    transform["scale_x"] = 1.0
    manifest["source_to_pixel_transform"] = transform
    with pytest.raises(GeminiNormalizedTableBoxError) as exc_info:
        projection.project(
            provider_value={"tables": []},
            raster_manifest=manifest,
            expected_page_bbox=[0.0, 0.0, 500.0, 1000.0],
        )
    assert exc_info.value.code == "g5102_raster_transform_mismatch"


def test_g5102_is_private_research_code_and_not_a_second_runtime() -> None:
    module_source = MODULE_PATH.read_text(encoding="utf-8")
    package_source = PACKAGE_INIT.read_text(encoding="utf-8")
    assert 'RUNTIME_STATUS = "research_only"' in module_source
    assert "requests" not in module_source
    assert "urlopen" not in module_source
    assert "pdfplumber" not in module_source
    assert "GeminiNormalizedTableBoxProjectionFactory" not in package_source
    assert "FACTORY_REQUIRED =" in module_source
    assert "GeminiNormalizedTableBoxProjectionFactory.create" in module_source
    assert "FORBIDDEN =" in module_source
    assert "must not render PDFs" in module_source
    assert FACTORY_REQUIRED.startswith("GeminiNormalizedTableBoxProjectionFactory")
    assert FORBIDDEN.startswith("G5.102 must not render PDFs")


def test_g5102_harness_reuses_factories_and_excludes_grid_and_extraction() -> None:
    source = HARNESS_PATH.read_text(encoding="utf-8")
    assert "PdfTableRasterFactory" in source
    assert "GeminiNormalizedTableBoxProjectionFactory" in source
    assert "_provider" in source
    assert "NativePdfPointNavigationOverlayFactory" not in source
    assert "VisualPdfPlumberTableAdapterFactory" not in source
    assert "explicit_vertical_lines" not in source
    assert "horizontal_strategy" not in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
