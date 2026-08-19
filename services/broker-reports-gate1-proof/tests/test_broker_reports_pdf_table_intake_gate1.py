from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.inputs import FileInput  # noqa: E402
from broker_reports_gate1.normalizer import Gate1Normalizer  # noqa: E402
from broker_reports_gate1.pdf_table_intake_runtime import (  # noqa: E402
    PdfTableIntakeConfig,
    PdfTableIntakeRuntimeFactory,
)
from broker_reports_gate1.pdf_table_locator import (  # noqa: E402
    PDF_TABLE_LOCATOR_COORDINATE_CONTRACT,
    PDF_TABLE_LOCATOR_PROMPT,
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
