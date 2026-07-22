from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from broker_reports_gate1.gate2_table_packages import Gate2TablePackageFactory
from broker_reports_gate1.pdf_dual_vlm_runtime import (
    PdfDualVlmRuntimeConfig,
    PdfDualVlmRuntimeFactory,
    sha256_json,
)
from broker_reports_gate1.pdf_table_raster import PDF_TABLE_CANDIDATE_SCHEMA
from broker_reports_gate1.semantic_visual_table_materialization import (
    SEMANTIC_LOGICAL_TABLE_SCHEMA_VERSION,
    SEMANTIC_VISUAL_TABLE_ENVELOPE_SCHEMA_VERSION,
    SemanticVisualTableMaterializationConfig,
    SemanticVisualTableMaterializationError,
    SemanticVisualTableMaterializationFactory,
    validate_semantic_visual_table_envelope,
)
from broker_reports_gate1.semantic_visual_table_projection_contracts import (
    validate_semantic_visual_table_projection,
)
from broker_reports_gate1.table_projection import TableProjectionValidator


def test_ragged_semantic_rows_materialize_to_rectangular_logical_grid() -> None:
    runtime = _runtime_result(
        [["Label", "Amount", "Currency"], ["Cash"], [None, "1 000,00", "₽"]]
    )

    result = _materialize(runtime)
    logical = result.private_envelope["logical_table"]

    assert logical["schema_version"] == SEMANTIC_LOGICAL_TABLE_SCHEMA_VERSION
    assert logical["row_count"] == 3
    assert logical["column_count"] == 3
    assert len(logical["cells"]) == 9
    assert all(
        cell["row_span"] == cell["column_span"] == 1
        for cell in logical["cells"]
    )
    assert _logical_cell(logical, 1, 1) == {
        "value": None,
        "empty_origin": "short_row_padding",
    }
    assert _logical_cell(logical, 1, 2) == {
        "value": None,
        "empty_origin": "short_row_padding",
    }
    assert _logical_cell(logical, 2, 0) == {
        "value": None,
        "empty_origin": "semantic_null",
    }
    canonical = logical["canonical_table"]
    assert canonical["cells"][3]["content_state"] == "present"
    assert canonical["cells"][4]["content_state"] == "empty"
    assert canonical["cells"][4]["source_text"] == ""
    assert logical["physical_geometry_claimed"] is False


def test_system_envelope_owns_provenance_provider_and_execution_metadata() -> None:
    runtime = _runtime_result([["Cash", "1 000,00 ₽"]])

    envelope = _materialize(runtime).private_envelope
    execution = runtime.private_decisions[0]["executions"][0]

    assert envelope["schema_version"] == (
        SEMANTIC_VISUAL_TABLE_ENVELOPE_SCHEMA_VERSION
    )
    assert envelope["source_lineage"]["source_ref"] == "document_test"
    assert envelope["source_lineage"]["page_number"] == 2
    assert envelope["source_lineage"]["crop_id"] == "pdftablecandidate_test"
    assert envelope["source_lineage"]["crop_sha256"] == execution["input_hash"]
    metadata = envelope["provider_execution"]
    assert metadata["provider"] == "gemini"
    assert metadata["resolved_model_id"] == "models/gemini-3.5-flash"
    assert metadata["prompt_hash"] == execution["prompt_hash"]
    assert metadata["canonical_schema_hash"] == execution["canonical_schema_hash"]
    assert metadata["request_hash"] == execution["preflight"]["request_hash"]
    assert metadata["response_hash"] == execution["response_hash"]
    assert metadata["usage"] == execution["usage"]
    assert metadata["latency_ms"] == 12
    assert metadata["terminal_provider_status"] == "completed"
    assert metadata["validator_status"] == "passed"
    assert envelope["physical_geometry_claimed"] is False
    assert validate_semantic_visual_table_envelope(envelope) == []


def test_materialization_is_deterministic_for_the_same_private_input() -> None:
    runtime = _runtime_result([["A", "B"], ["C"]])
    materializer = SemanticVisualTableMaterializationFactory().create()

    first = materializer.materialize(
        decision=runtime.private_decisions[0],
        provider_evidence=runtime.private_provider_evidence,
    )
    second = materializer.materialize(
        decision=runtime.private_decisions[0],
        provider_evidence=runtime.private_provider_evidence,
    )

    assert first == second
    assert first.private_envelope["envelope_hash"] == second.private_envelope[
        "envelope_hash"
    ]
    assert first.gate2_projection["table_projection_checksum_ref"] == (
        second.gate2_projection["table_projection_checksum_ref"]
    )


def test_raw_and_parsed_provider_evidence_remain_private_and_hash_bound() -> None:
    runtime = _runtime_result([["Name", "(1,234.50)%"]])

    envelope = _materialize(runtime).private_envelope
    evidence = envelope["private_provider_evidence"]

    assert evidence["raw_provider_response"] == {
        "provider_payload": {"candidate": "raw-private"}
    }
    assert evidence["parsed_semantic_response"] == {
        "description": "Visible source table.",
        "rows": [["Name", "(1,234.50)%"]],
    }
    tampered = copy.deepcopy(envelope)
    tampered["private_provider_evidence"]["raw_provider_response"] = {"tampered": True}
    assert "semantic_visual_table_private_evidence_invalid" in (
        validate_semantic_visual_table_envelope(tampered)
    )


def test_semantic_projection_passes_existing_gate2_package_boundary() -> None:
    runtime = _runtime_result([["Item", "Value"], ["Cash", "1,000"]])

    projection = _materialize(runtime).gate2_projection

    assert TableProjectionValidator().validate(projection)["passed"] is True
    assert validate_semantic_visual_table_projection(projection)["passed"] is True
    package = Gate2TablePackageFactory().create().build(
        projection=projection,
        case_id="case-semantic-materialization",
    )
    upstream = package["upstream_source_representation"]
    assert upstream["source_representation_kind"] == (
        "semantic_visual_logical_table"
    )
    assert upstream["semantic_response_contract_passed"] is True
    assert upstream["physical_geometry_claimed"] is False
    assert upstream["provider_consensus_required"] is False
    assert package["source_unit"]["normalized_source_projection"]["cells"] == [
        ["Item", "Value"],
        ["Cash", "1,000"],
    ]


def test_materializer_fails_closed_on_missing_or_tampered_evidence() -> None:
    runtime = _runtime_result([["A"]])
    materializer = SemanticVisualTableMaterializationFactory().create()

    with pytest.raises(
        SemanticVisualTableMaterializationError,
        match="semantic_visual_table_private_evidence_invalid",
    ):
        materializer.materialize(
            decision=runtime.private_decisions[0],
            provider_evidence=[],
        )

    tampered = copy.deepcopy(runtime.private_provider_evidence)
    tampered[0]["parsed_semantic_response"]["rows"] = [["changed"]]
    with pytest.raises(
        SemanticVisualTableMaterializationError,
        match="semantic_visual_table_private_evidence_invalid",
    ):
        materializer.materialize(
            decision=runtime.private_decisions[0],
            provider_evidence=tampered,
        )


def test_factory_budget_and_anti_drift_boundary_are_closed() -> None:
    with pytest.raises(
        SemanticVisualTableMaterializationError,
        match="semantic_visual_table_materializer_budget_invalid",
    ):
        SemanticVisualTableMaterializationFactory(
            SemanticVisualTableMaterializationConfig(maximum_columns=0)
        ).create()

    source = (
        Path(__file__).resolve().parents[1]
        / "broker_reports_gate1"
        / "semantic_visual_table_materialization.py"
    ).read_text(encoding="utf-8")
    assert "SemanticVisualTableMaterializationFactory.create" in source
    assert "physical_geometry_claimed\": False" in source
    assert "model_view" not in source
    assert "provider.invoke" not in source


def _materialize(runtime):
    return SemanticVisualTableMaterializationFactory().create().materialize(
        decision=runtime.private_decisions[0],
        provider_evidence=runtime.private_provider_evidence,
    )


def _logical_cell(
    logical_table: dict[str, Any], row_index: int, column_index: int
) -> dict[str, Any]:
    cell = next(
        item
        for item in logical_table["cells"]
        if item["row_index"] == row_index and item["column_index"] == column_index
    )
    return {"value": cell["value"], "empty_origin": cell["empty_origin"]}


def _runtime_result(rows: list[list[str | None]]):
    runtime = PdfDualVlmRuntimeFactory(
        PdfDualVlmRuntimeConfig(enabled=True)
    ).create_with_providers(gemini=_Provider(rows))
    return runtime.run([_candidate()])


def _candidate() -> dict[str, Any]:
    png = b"\x89PNG\r\n\x1a\nsemantic-materialization-test"
    manifest = {
        "schema_version": PDF_TABLE_CANDIDATE_SCHEMA,
        "policy_version": "pdf_table_candidate_raster_policy_v1",
        "crop_id": "pdftablecandidate_test",
        "document_ref": "document_test",
        "pdf_sha256": "a" * 64,
        "page_number": 2,
        "table_ref": "pdftable_test",
        "candidate_ref": "pdftable_test",
        "declared_table_bbox": [10.0, 20.0, 300.0, 200.0],
        "rendered_bbox": [0.0, 0.0, 320.0, 220.0],
        "source_coordinate_space": "pdf_top_left_points",
        "pixel_coordinate_space": "crop_top_left_pixels",
        "source_to_pixel_transform": {
            "scale_x": 1.0,
            "scale_y": 1.0,
            "translate_source_x": 0.0,
            "translate_source_y": 0.0,
        },
        "renderer": "pymupdf",
        "renderer_version": "1.26.5",
        "page_rotation": 0,
        "applied_rotation": 0,
        "dpi": 150,
        "dpi_revision_reason": "primary_150_dpi",
        "width": 640,
        "height": 440,
        "pixels": 281_600,
        "png_bytes": len(png),
        "png_sha256": hashlib.sha256(png).hexdigest(),
        "lossless": True,
        "silent_resize_performed": False,
        "detected_bbox_normalized": [0.1, 0.1, 0.9, 0.9],
        "page_bbox_points": [0.0, 0.0, 612.0, 792.0],
        "padding_basis": "page_dimensions_per_side",
        "horizontal_padding_fraction": 0.08,
        "vertical_padding_fraction": 0.08,
        "padding_x_points": 48.96,
        "padding_y_points": 63.36,
        "detector_contract_version": "broker_reports_pdf_table_detection_response_v2",
        "detector_identity": {"response_hash": "b" * 64},
        "downstream_contract": "gate2_raster_candidate",
        "semantic_interpretation_performed": False,
    }
    manifest["manifest_hash"] = sha256_json(manifest)
    return {
        "manifest": manifest,
        "private_png_base64": base64.b64encode(png).decode("ascii"),
    }


class _Provider:
    def __init__(self, rows: list[list[str | None]]) -> None:
        self.rows = rows

    def qualify(self) -> dict[str, Any]:
        return {
            "status": "qualified",
            "provider_profile": "google_gemini",
            "provider_profile_revision": "gemini_profile_revision",
            "requested_model_id": "models/gemini-3.5-flash",
            "resolved_model_id": "models/gemini-3.5-flash",
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "http_status": 200,
            "response_hash": "1" * 64,
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_retry": False,
            "provider_failover": False,
        }

    def count_tokens(self, **kwargs: Any) -> dict[str, Any]:
        schema_hash = sha256_json(kwargs["output_schema"])
        return {
            "total_tokens": 321,
            "input_tokens": 321,
            "http_status": 200,
            "request_hash": "c" * 64,
            "response_hash": "d" * 64,
            "canonical_schema_hash": schema_hash,
            "adapted_schema_hash": schema_hash,
            "schema_transform_count": 0,
            "model_requested": "models/gemini-3.5-flash",
            "transport_identity": "gemini_native_count",
            "within_hard_guard": True,
        }

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        output = {
            "description": "Visible source table.",
            "rows": copy.deepcopy(self.rows),
        }
        return {
            "attempt": {
                "attempt_number": 1,
                "attempt_lineage": [],
                "provider_profile": "google_gemini",
                "provider_profile_revision": "gemini_profile_revision",
                "model_requested": "models/gemini-3.5-flash",
                "model_resolved": "models/gemini-3.5-flash",
                "canonical_schema_hash": sha256_json(kwargs["output_schema"]),
                "adapted_schema_hash": sha256_json(kwargs["output_schema"]),
                "schema_transform_count": 0,
                "usage": {"input_tokens": 321, "output_tokens": 123},
                "duration_ms": 12,
                "finish_reason": "completed",
                "terminal_failure_class": None,
            },
            "json_output": output,
            "raw_private_response": {
                "provider_payload": {"candidate": "raw-private"}
            },
            "text": json.dumps(output, ensure_ascii=False),
            "response_hash": hashlib.sha256(repr(output).encode()).hexdigest(),
        }
