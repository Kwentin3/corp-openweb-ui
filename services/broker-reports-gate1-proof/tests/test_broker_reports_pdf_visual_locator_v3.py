from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import fitz
import pdfminer
import pdfplumber
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    Gate2OpenWebUIProviderConnection,
)
from broker_reports_gate1.contracts import sha256_json  # noqa: E402
from broker_reports_gate1.pdf_layout import (  # noqa: E402
    PdfLayoutParserConfig,
    PdfPlumberLayoutAdapter,
)
from broker_reports_gate1.pdf_table_intake_runtime import (  # noqa: E402
    PDF_TABLE_DETECTION_ATTEMPT_SCHEMA_V3,
    PDF_TABLE_DETECTION_REQUEST_SCHEMA,
    PDF_TABLE_DETECTION_REQUEST_SCHEMA_V3,
    PDF_TABLE_INTAKE_POLICY_VERSION_V3,
    PDF_TABLE_INTAKE_RUN_SCHEMA_V3,
    PdfTableIntakeConfig,
    PdfTableIntakeRuntime,
    PdfTableIntakeRuntimeFactory,
    table_detection_output_schema,
)
from broker_reports_gate1.pdf_table_locator import (  # noqa: E402
    PDF_TABLE_LOCATOR_OUTPUT_SCHEMA,
    PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3,
    PDF_TABLE_LOCATOR_RESPONSE_SCHEMA_V3,
    PdfTableLocatorError,
    PdfTableLocatorProjectionConfig,
    PdfTableLocatorProjectionFactory,
)
from broker_reports_gate1.pdf_table_locator_provider import (  # noqa: E402
    PdfTableLocatorProviderError,
    PdfTableLocatorProviderFactory,
)


def _two_page_pdf() -> bytes:
    document = fitz.open()
    for page_number in (1, 2):
        page = document.new_page(width=200, height=300)
        if page_number == 1:
            page.insert_text((20, 42), "Transactions", fontsize=10)
            top, bottom = 60, 150
            values = (("Date", "Amount"), ("A", "10"), ("B", "20"))
        else:
            top, bottom = 15, 120
            values = (("C", "30"), ("D", "40"), ("E", "50"))
        for x in (20, 100, 180):
            page.draw_line((x, top), (x, bottom), color=(0, 0, 0), width=1)
        row_height = (bottom - top) / len(values)
        for ordinal in range(len(values) + 1):
            y = top + row_height * ordinal
            page.draw_line((20, y), (180, y), color=(0, 0, 0), width=1)
        for ordinal, row in enumerate(values):
            baseline = top + row_height * ordinal + 18
            page.insert_text((25, baseline), row[0], fontsize=8)
            page.insert_text((110, baseline), row[1], fontsize=8)
    payload = document.tobytes(deflate=True)
    document.close()
    return payload


class RecordingVisualProvider:
    def __init__(self, outputs: list[dict[str, Any]]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def qualify(self) -> dict[str, Any]:
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

    def count_tokens(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("count_tokens", kwargs))
        return {
            "total_tokens": 100,
            "request_hash": "token-request-hash",
            "response_hash": "token-response-hash",
            "within_hard_guard": True,
        }

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("invoke", kwargs))
        page_number = int(kwargs["model_view"]["page_number"])
        return {
            "attempt": {
                "terminal_failure_class": None,
                "provider_profile": "google_gemini",
                "provider_profile_revision": "test-profile-v1",
                "model_requested": "models/gemini-3.5-flash",
                "model_resolved": "models/gemini-3.5-flash",
                "adapter_identity": "test-visual-locator-adapter-v1",
                "request_hash": f"provider-request-{page_number}",
                "hidden_retry": False,
                "provider_failover": False,
            },
            "json_output": self.outputs[page_number - 1],
            "raw_private_response": {"page_number": page_number},
            "response_hash": f"provider-response-{page_number}",
        }


def _run_v3(provider: RecordingVisualProvider):
    pdf_bytes = _two_page_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    result = (
        PdfTableIntakeRuntimeFactory(
            PdfTableIntakeConfig(enabled=True, visual_locator_v3_enabled=True)
        )
        .create_with_provider(provider)
        .run(
            [
                {
                    "document_ref": "pdfsource_visual_v3",
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": digest,
                }
            ]
        )
    )
    return result


def _table(
    table_box: list[int],
    *,
    title_box: list[int] | None = None,
    header_box: list[int] | None = None,
) -> dict[str, Any]:
    return {
        "table_box_2d": table_box,
        "title_box_2d": title_box,
        "header_box_2d": header_box,
    }


def test_v3_schema_is_locator_only_and_v1_remains_default() -> None:
    assert table_detection_output_schema() == PDF_TABLE_LOCATOR_OUTPUT_SCHEMA
    schema = table_detection_output_schema(visual_locator_v3_enabled=True)

    assert schema["required"] == ["tables", "boundary_from_previous"]
    assert set(schema["properties"]["tables"]["items"]["properties"]) == {
        "table_box_2d",
        "title_box_2d",
        "header_box_2d",
    }
    assert schema["properties"]["tables"]["items"]["additionalProperties"] is False
    serialized = repr(schema).lower()
    for forbidden in ("rows", "cells", "text", "settings", "values"):
        assert forbidden not in serialized


def test_v3_runtime_projects_current_page_boxes_and_carries_previous_image() -> None:
    provider = RecordingVisualProvider(
        [
            {
                "tables": [
                    _table(
                        [200, 100, 500, 900],
                        title_box=[190, 100, 210, 500],
                        header_box=[200, 100, 260, 900],
                    )
                ],
                "boundary_from_previous": {
                    "decision": "NOT_APPLICABLE",
                    "evidence": "FIRST_PAGE",
                },
            },
            {
                "tables": [_table([50, 100, 400, 900])],
                "boundary_from_previous": {
                    "decision": "CONTINUATION",
                    "evidence": "VISUAL_FLOW",
                },
            },
        ]
    )

    result = _run_v3(provider)

    assert result.safe_summary["status"] == "blocked_unsupported_next_stage"
    assert result.safe_summary["gate2_boundary_ready"] is False
    assert result.safe_summary["next_stage_status"] == "blocked_source_grid_v2_required"
    assert result.safe_summary["schema_version"] == PDF_TABLE_INTAKE_RUN_SCHEMA_V3
    assert result.safe_summary["policy_version"] == PDF_TABLE_INTAKE_POLICY_VERSION_V3
    assert result.safe_summary["detector_contract_version"] == PDF_TABLE_LOCATOR_RESPONSE_SCHEMA_V3
    assert [name for name, _ in provider.calls] == [
        "count_tokens",
        "invoke",
        "count_tokens",
        "invoke",
    ]
    first_invoke = provider.calls[1][1]
    second_invoke = provider.calls[3][1]
    assert first_invoke["model_view"]["image_order"] == ["CURRENT"]
    assert first_invoke["model_view"]["schema_version"] == (
        PDF_TABLE_DETECTION_REQUEST_SCHEMA_V3
    )
    assert first_invoke["previous_png_bytes"] is None
    assert first_invoke["previous_png_sha256"] is None
    assert second_invoke["model_view"]["image_order"] == ["PREVIOUS", "CURRENT"]
    assert second_invoke["previous_png_bytes"] == first_invoke["png_bytes"]
    assert second_invoke["previous_png_sha256"] == hashlib.sha256(
        first_invoke["png_bytes"]
    ).hexdigest()

    first_page, second_page = result.private_page_results
    assert first_page["schema_version"] == PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3
    assert first_page["status"] == "located"
    assert first_page["next_stage_status"] == "blocked_source_grid_v2_required"
    assert result.private_detection_attempts[0]["schema_version"] == (
        PDF_TABLE_DETECTION_ATTEMPT_SCHEMA_V3
    )
    assert first_page["boundary_from_previous"] == {
        "decision": "NOT_APPLICABLE",
        "evidence": "FIRST_PAGE",
    }
    first_region = first_page["regions"][0]
    assert first_region["bbox_pdf_points"] == [20.0, 60.0, 180.0, 150.0]
    assert first_region["title_bbox_pdf_points"] == [20.0, 57.0, 100.0, 63.0]
    assert first_region["header_bbox_pdf_points"] == [20.0, 60.0, 180.0, 78.0]
    assert first_region["bbox_semantics"] == (
        "visual_table_instance_region_hint_not_source_grid"
    )
    assert first_region["source_grid_verified"] is False
    assert first_region["title_source_binding_verified"] is False
    assert first_region["header_source_binding_verified"] is False
    assert second_page["boundary_from_previous"] == {
        "decision": "CONTINUATION",
        "evidence": "VISUAL_FLOW",
    }
    assert second_page["regions"][0]["title_bbox_pdf_points"] is None
    assert second_page["regions"][0]["header_bbox_pdf_points"] is None


def test_v3_zero_tables_is_valid_but_still_not_a_grid_handoff() -> None:
    provider = RecordingVisualProvider(
        [
            {
                "tables": [],
                "boundary_from_previous": {
                    "decision": "NOT_APPLICABLE",
                    "evidence": "FIRST_PAGE",
                },
            },
            {
                "tables": [],
                "boundary_from_previous": {
                    "decision": "NOT_APPLICABLE",
                    "evidence": "NO_TABLE_PAIR",
                },
            },
        ]
    )

    result = _run_v3(provider)

    assert result.safe_summary["status"] == "blocked_unsupported_next_stage"
    assert result.safe_summary["next_stage_status"] == "not_required"
    assert result.safe_summary["candidates_total"] == 0
    assert all(page["regions"] == [] for page in result.private_page_results)
    assert all(page["status"] == "located_no_tables" for page in result.private_page_results)
    assert all(page["next_stage_status"] == "not_required" for page in result.private_page_results)
    assert result.private_page_results[1]["boundary_from_previous"] == {
        "decision": "NOT_APPLICABLE",
        "evidence": "NO_TABLE_PAIR",
    }


def test_v3_invalid_header_coordinates_fail_closed_without_a_region() -> None:
    provider = RecordingVisualProvider(
        [
            {
                "tables": [
                    _table(
                        [200, 100, 500, 900],
                        header_box=[100, 100, 260, 1001],
                    )
                ],
                "boundary_from_previous": {
                    "decision": "NOT_APPLICABLE",
                    "evidence": "FIRST_PAGE",
                },
            }
        ]
    )
    pdf_bytes = fitz.open()
    page = pdf_bytes.new_page(width=200, height=300)
    page.insert_text((20, 20), "page")
    payload = pdf_bytes.tobytes()
    pdf_bytes.close()
    digest = hashlib.sha256(payload).hexdigest()

    result = (
        PdfTableIntakeRuntimeFactory(
            PdfTableIntakeConfig(enabled=True, visual_locator_v3_enabled=True)
        )
        .create_with_provider(provider)
        .run(
            [
                {
                    "document_ref": "pdfsource_invalid_header",
                    "pdf_bytes": payload,
                    "pdf_sha256": digest,
                }
            ]
        )
    )

    assert result.safe_summary["status"] == "failed"
    assert result.private_page_results[0]["regions"] == []
    assert result.private_detection_attempts[0]["validation_error_code"] == (
        "pdf_table_locator_box_out_of_range"
    )


def test_provider_payload_orders_previous_before_current_without_hidden_images() -> None:
    adapter = PdfTableLocatorProviderFactory().create_with_connection(
        Gate2OpenWebUIProviderConnection(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key="secret",
        )
    )
    body, _, _, _ = adapter._generate_body(
        model_view={"task": "locator", "image_order": ["PREVIOUS", "CURRENT"]},
        output_schema=table_detection_output_schema(visual_locator_v3_enabled=True),
        png_bytes=b"current-page",
        previous_png_bytes=b"previous-page",
    )

    parts = body["contents"][0]["parts"]
    assert [part.get("text") for part in parts if "text" in part] == [
        '{"image_order":["PREVIOUS","CURRENT"],"task":"locator"}',
        "PREVIOUS full page",
        "CURRENT full page",
    ]
    images = [part["inlineData"]["data"] for part in parts if "inlineData" in part]
    assert len(images) == 2


@pytest.mark.parametrize(
    ("image_order", "previous_png"),
    [
        (["CURRENT"], b"unexpected-previous"),
        (["PREVIOUS", "CURRENT"], None),
        (None, b"undeclared-previous"),
        (["CURRENT", "PREVIOUS"], None),
    ],
)
def test_provider_rejects_image_order_transport_contradictions(
    image_order: list[str] | None, previous_png: bytes | None
) -> None:
    adapter = PdfTableLocatorProviderFactory().create_with_connection(
        Gate2OpenWebUIProviderConnection(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key="secret",
        )
    )
    model_view: dict[str, Any] = {"task": "locator"}
    if image_order is not None:
        model_view["image_order"] = image_order

    with pytest.raises(
        PdfTableLocatorProviderError,
        match="pdf_grid_provider_image_order_mismatch",
    ) as raised:
        adapter._generate_body(
            model_view=model_view,
            output_schema=table_detection_output_schema(
                visual_locator_v3_enabled=True
            ),
            png_bytes=b"current-page",
            previous_png_bytes=previous_png,
        )

    assert raised.value.code == "pdf_grid_provider_image_order_mismatch"


@pytest.mark.parametrize(
    ("provider_value", "expected_code"),
    [
        (
            {
                "tables": [_table([200, 100, 500, 900])],
                "boundary_from_previous": {
                    "decision": "CONTINUATION",
                    "evidence": "VISUAL_FLOW",
                },
            },
            "pdf_table_locator_first_page_boundary_invalid",
        ),
        (
            {
                "tables": [
                    _table([500, 100, 700, 900]),
                    _table([200, 100, 400, 900]),
                ],
                "boundary_from_previous": {
                    "decision": "NOT_APPLICABLE",
                    "evidence": "FIRST_PAGE",
                },
            },
            "pdf_table_locator_boxes_not_ordered",
        ),
        (
            {
                "tables": [
                    _table([200, 100, 500, 900]),
                    _table([200, 100, 500, 900]),
                ],
                "boundary_from_previous": {
                    "decision": "NOT_APPLICABLE",
                    "evidence": "FIRST_PAGE",
                },
            },
            "pdf_table_locator_duplicate_table_box",
        ),
    ],
)
def test_v3_projection_rejects_impossible_boundary_and_unordered_instances(
    provider_value: dict[str, Any], expected_code: str
) -> None:
    projection = PdfTableLocatorProjectionFactory(
        PdfTableLocatorProjectionConfig(visual_contract_v3_enabled=True)
    ).create()
    manifest = {
        "render_scope": "full_page",
        "full_page_identity_verified": True,
        "source_coordinate_space": "pdf_top_left_points",
        "pixel_coordinate_space": "crop_top_left_pixels",
        "lossless": True,
        "silent_resize_performed": False,
        "page_rotation": 0,
        "applied_rotation": 0,
        "actual_page_bbox": [0.0, 0.0, 200.0, 300.0],
        "rendered_bbox": [0.0, 0.0, 200.0, 300.0],
        "width": 400,
        "height": 600,
        "source_to_pixel_transform": {
            "scale_x": 2.0,
            "scale_y": 2.0,
            "translate_source_x": 0.0,
            "translate_source_y": 0.0,
        },
        "manifest_hash": "manifest-test",
    }

    with pytest.raises(PdfTableLocatorError, match=expected_code) as raised:
        projection.project(
            provider_value=provider_value,
            raster_manifest=manifest,
            expected_page_bbox=[0.0, 0.0, 200.0, 300.0],
            has_previous_page=False,
            previous_page_has_tables=False,
        )

    assert raised.value.code == expected_code


def test_current_layout_rejects_v3_pages_without_legacy_fallback() -> None:
    pdf_bytes = _two_page_pdf()
    locator_pages = [
        {
            "schema_version": PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3,
            "page_number": page_number,
            "status": "located",
            "regions": [
                {
                    "region_ref": f"v3-region-{page_number}",
                    "bbox_pdf_points": [20.0, 15.0, 180.0, 150.0],
                }
            ],
        }
        for page_number in (1, 2)
    ]
    result = PdfPlumberLayoutAdapter(
        pdfplumber_module=pdfplumber,
        pdfminer_module=pdfminer,
        config=PdfLayoutParserConfig(),
        requested_capability="table_candidates",
    ).parse(pdf_bytes, table_locator_pages=locator_pages)

    assert all(page["table_candidate_inventory"] == [] for page in result.pages)
    assert all(page["table_candidate_status"] == "blocked" for page in result.pages)
    assert all(
        page["table_reason_codes"]
        == ["pdf_table_locator_contract_version_unsupported"]
        for page in result.pages
    )


def test_v1_fixed_inputs_match_base_7087303_golden_hashes() -> None:
    adapter = PdfTableLocatorProviderFactory().create_with_connection(
        Gate2OpenWebUIProviderConnection(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key="golden-secret",
        )
    )
    model_view = {
        "schema_version": PDF_TABLE_DETECTION_REQUEST_SCHEMA,
        "request_id": "golden-request",
        "page_number": 1,
        "task": "fixed-v1-locator",
    }
    body, _, _, _ = adapter._generate_body(
        model_view=model_view,
        output_schema=PDF_TABLE_LOCATOR_OUTPUT_SCHEMA,
        png_bytes=b"fixed-v1-png",
    )
    projection = PdfTableLocatorProjectionFactory().create().project(
        provider_value={"tables": [{"box_2d": [100, 200, 600, 800]}]},
        raster_manifest={
            "render_scope": "full_page",
            "full_page_identity_verified": True,
            "source_coordinate_space": "pdf_top_left_points",
            "pixel_coordinate_space": "crop_top_left_pixels",
            "lossless": True,
            "silent_resize_performed": False,
            "page_rotation": 0,
            "applied_rotation": 0,
            "actual_page_bbox": [0.0, 0.0, 200.0, 300.0],
            "rendered_bbox": [0.0, 0.0, 200.0, 300.0],
            "width": 400,
            "height": 600,
            "source_to_pixel_transform": {
                "scale_x": 2.0,
                "scale_y": 2.0,
                "translate_source_x": 0.0,
                "translate_source_y": 0.0,
            },
            "manifest_hash": "golden-manifest",
        },
        expected_page_bbox=[0.0, 0.0, 200.0, 300.0],
    )
    summary = PdfTableIntakeRuntime(
        PdfTableIntakeConfig(enabled=True), None, None, None
    )._summary(
        status="completed",
        documents_total=1,
        pages_total=1,
        candidates_total=1,
        failed_pages=[],
        rejected_regions=[],
        detector_qualification=None,
    )

    assert sha256_json(body) == (
        "a7de25fbf5fdc557bfcdcfad97731161a9686cd112fab37b0972b4de721b5153"
    )
    assert sha256_json(projection) == (
        "06f2823a2289258f55f81fd6952e2f7071f904e8e4a1f56f55392049c3c861a7"
    )
    assert sha256_json(summary) == (
        "e81fefccfec15f0a6c2a451059fb4d4859077b044a5e1ec595894c066ad6f18d"
    )
    assert summary["configuration_hash"] == (
        "b1a90ae20eea71bb1871b484d83c742f78d3af45e50e723bdac3d9401ada0318"
    )
