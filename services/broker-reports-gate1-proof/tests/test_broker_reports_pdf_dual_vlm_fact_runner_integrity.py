from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SERVICE_ROOT / "scripts"
RUNNER_PATH = SCRIPT_DIR / "local_pdf_dual_vlm_fact_benchmark.py"
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location(
        "local_pdf_dual_vlm_fact_benchmark_integrity_test", RUNNER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner()
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"


def test_raster_bytes_manifest_and_bbox_are_bound() -> None:
    payload = _raster_payload(
        pdf_sha256="a" * 64,
        page_number=1,
        bbox=[0.0, 0.0, 100.0, 100.0],
        crop_id="page_crop",
    )

    png, manifest = RUNNER._validated_raster_payload(
        payload,
        expected_pdf_sha256="a" * 64,
        expected_page_number=1,
        expected_bbox=[0.0, 0.0, 100.0, 100.0],
        code_prefix="test_raster",
    )

    assert png == PNG
    assert manifest["png_sha256"] == hashlib.sha256(PNG).hexdigest()

    contract = RUNNER.build_crop_contract(
        document_id="case_1",
        page_image_sha256="c" * 64,
        normalized_bbox=[0.0, 0.0, 1.0, 1.0],
        raster_manifest=manifest,
    )
    RUNNER._validate_crop_contract_binding(
        contract,
        expected_document_id="case_1",
        expected_pdf_sha256="a" * 64,
        expected_page_number=1,
        expected_page_image_sha256="c" * 64,
        expected_normalized_bbox=[0.0, 0.0, 1.0, 1.0],
        expected_source_bbox=[0.0, 0.0, 100.0, 100.0],
        expected_png_bytes=len(PNG),
        expected_png_sha256=hashlib.sha256(PNG).hexdigest(),
        expected_crop_id="page_crop",
        expected_raster_manifest_hash=manifest["manifest_hash"],
    )
    contract_tamper = copy.deepcopy(contract)
    contract_tamper["source_bbox_points"] = [1.0, 0.0, 100.0, 100.0]
    unsigned_contract = copy.deepcopy(contract_tamper)
    unsigned_contract.pop("contract_checksum")
    contract_tamper["contract_checksum"] = RUNNER.sha256_json(unsigned_contract)
    with pytest.raises(RUNNER.BenchmarkError) as contract_error:
        RUNNER._validate_crop_contract_binding(
            contract_tamper,
            expected_document_id="case_1",
            expected_pdf_sha256="a" * 64,
            expected_page_number=1,
            expected_page_image_sha256="c" * 64,
            expected_normalized_bbox=[0.0, 0.0, 1.0, 1.0],
            expected_source_bbox=[0.0, 0.0, 100.0, 100.0],
            expected_png_bytes=len(PNG),
            expected_png_sha256=hashlib.sha256(PNG).hexdigest(),
            expected_crop_id="page_crop",
            expected_raster_manifest_hash=manifest["manifest_hash"],
        )
    assert contract_error.value.code == "dual_vlm_crop_contract_bbox_identity_mismatch"

    hash_tamper = copy.deepcopy(payload)
    hash_tamper["manifest"]["png_sha256"] = "b" * 64
    hash_tamper["manifest"] = _sealed_manifest(hash_tamper["manifest"])
    with pytest.raises(RUNNER.BenchmarkError) as hash_error:
        RUNNER._validated_raster_payload(
            hash_tamper,
            expected_pdf_sha256="a" * 64,
            expected_page_number=1,
            expected_bbox=[0.0, 0.0, 100.0, 100.0],
            code_prefix="test_raster",
        )
    assert hash_error.value.code == "test_raster_png_identity_mismatch"

    bbox_tamper = copy.deepcopy(payload)
    bbox_tamper["manifest"]["declared_table_bbox"] = [1.0, 0.0, 100.0, 100.0]
    bbox_tamper["manifest"] = _sealed_manifest(bbox_tamper["manifest"])
    with pytest.raises(RUNNER.BenchmarkError) as bbox_error:
        RUNNER._validated_raster_payload(
            bbox_tamper,
            expected_pdf_sha256="a" * 64,
            expected_page_number=1,
            expected_bbox=[0.0, 0.0, 100.0, 100.0],
            code_prefix="test_raster",
        )
    assert bbox_error.value.code == "test_raster_bbox_identity_mismatch"


def test_provider_call_accounting_and_provenance_are_terminal(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "run" / "artifacts" / "case_1"
    artifact_dir.mkdir(parents=True)
    provider = _Provider("openai")
    model_view = {"task": "fact"}
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    operation = RUNNER._provider_operation(
        provider=provider,
        task_id="case_1_crop_1_openai",
        kind="openai_crop_financial_fact_extraction",
        model_view=model_view,
        output_schema=schema,
        png_bytes=PNG,
        artifact_dir=artifact_dir,
        artifact_stem="openai",
    )

    assert provider.call_names == ["count_tokens", "invoke"]
    assert operation["call_accounting"] == {
        "count_or_preflight_calls_attempted": 1,
        "count_or_preflight_calls_completed": 1,
        "generate_calls_attempted": 1,
        "generate_calls_completed": 1,
    }
    assert operation["provenance_verified"] is True
    assert operation["provenance_errors"] == []
    assert "failure_code" not in operation
    assert operation["attempt"]["crop_sha256"] == hashlib.sha256(PNG).hexdigest()


def test_retry_violation_and_failed_call_counts_are_not_rewritten(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "run" / "artifacts" / "case_1"
    artifact_dir.mkdir(parents=True)
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    retry = RUNNER._safe_provider_operation(
        provider=_Provider("openai", hidden_retry=True),
        task_id="retry_openai",
        kind="openai_crop_financial_fact_extraction",
        model_view={"task": "fact"},
        output_schema=schema,
        png_bytes=PNG,
        artifact_dir=artifact_dir,
        artifact_stem="retry",
    )
    assert retry["hidden_retry"] is True
    assert retry["attempt"]["hidden_retry"] is True
    assert "dual_vlm_hidden_retry_detected" in retry["provenance_errors"]
    assert retry["call_accounting"]["generate_calls_attempted"] == 1

    count_failure = RUNNER._safe_provider_operation(
        provider=_CountFailureProvider(),
        task_id="count_failure",
        kind="openai_crop_financial_fact_extraction",
        model_view={"task": "fact"},
        output_schema=schema,
        png_bytes=PNG,
        artifact_dir=artifact_dir,
        artifact_stem="count_failure",
    )
    assert count_failure["call_accounting"] == {
        "count_or_preflight_calls_attempted": 1,
        "count_or_preflight_calls_completed": 0,
        "generate_calls_attempted": 0,
        "generate_calls_completed": 0,
    }
    assert count_failure["hidden_retry"] is False

    generate_failure = RUNNER._safe_provider_operation(
        provider=_Provider("openai", raise_on_invoke=True),
        task_id="generate_failure",
        kind="openai_crop_financial_fact_extraction",
        model_view={"task": "fact"},
        output_schema=schema,
        png_bytes=PNG,
        artifact_dir=artifact_dir,
        artifact_stem="generate_failure",
    )
    assert generate_failure["call_accounting"] == {
        "count_or_preflight_calls_attempted": 1,
        "count_or_preflight_calls_completed": 1,
        "generate_calls_attempted": 1,
        "generate_calls_completed": 0,
    }
    assert generate_failure["hidden_retry"] is None
    terminal = {
        "cases": [
            {
                "detection": {},
                "crops": [{"gemini": {}, "openai": {"operation": generate_failure}}],
            }
        ]
    }
    RUNNER._derive_terminal_execution_truth(terminal)
    assert terminal["hidden_retry"] is None
    assert terminal["execution_call_accounting"]["generate_calls_attempted"] == 1


def test_one_crop_failure_preserves_case_and_later_crop(tmp_path: Path) -> None:
    pdf_bytes = b"%PDF-integrity-fixture"
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    detector = _Provider("google", json_output=_detection_output())
    gemini = _Provider("google", terminal_failure_class="parse_failure")
    openai = _Provider("openai", terminal_failure_class="parse_failure")
    renderer = _TwoCropRenderer(pdf_sha256)
    case = {
        "case_id": "case_1",
        "broker": "fixture",
        "category_tags": ["text_layer"],
        "pdf_sha256": pdf_sha256,
        "pdf_bytes": len(pdf_bytes),
        "relative_pdf": "fixture.pdf",
        "page_number": 1,
        "page_bbox_points": [0.0, 0.0, 100.0, 100.0],
        "render_dpi": 150,
    }

    result = RUNNER._run_case(
        case=case,
        pdf_bytes=pdf_bytes,
        parse_result=SimpleNamespace(
            pages=[{"width": 100.0, "height": 100.0, "word_inventory": []}]
        ),
        renderer=renderer,
        detector=detector,
        gemini=gemini,
        openai=openai,
        evidence_verifier=SimpleNamespace(),
        output_dir=tmp_path,
    )

    assert len(result["crops"]) == 2
    assert result["crops"][0]["terminal_status"] == "failed"
    assert result["crops"][0]["failure_code"] == "fixture_first_crop_failure"
    assert result["crops"][1]["terminal_status"] == "provider_contract_invalid"
    assert result["terminal_status"] == "completed_with_crop_failures"
    assert gemini.call_names == ["count_tokens", "invoke"]
    assert openai.call_names == ["count_tokens", "invoke"]
    assert RUNNER._case_terminal_failures(result) == [
        {
            "case_id": "case_1",
            "candidate_index": 1,
            "code": "fixture_first_crop_failure",
        },
        {
            "case_id": "case_1",
            "candidate_index": 2,
            "code": "dual_vlm_provider_terminal_failure",
        },
    ]


class _Provider:
    def __init__(
        self,
        role: str,
        *,
        json_output: dict[str, Any] | None = None,
        hidden_retry: bool = False,
        terminal_failure_class: str | None = None,
        raise_on_invoke: bool = False,
    ) -> None:
        self.role = role
        self.json_output = json_output
        self.hidden_retry = hidden_retry
        self.terminal_failure_class = terminal_failure_class
        self.raise_on_invoke = raise_on_invoke
        self.call_names: list[str] = []

    @property
    def identity(self) -> dict[str, str]:
        if self.role == "openai":
            return {
                "provider": "openai",
                "profile": "openai_gpt",
                "model": "gpt-5.4-mini-2026-03-17",
            }
        return {
            "provider": "google",
            "profile": "google_gemini",
            "model": "models/gemini-3.5-flash",
        }

    def count_tokens(self, **kwargs: Any) -> dict[str, Any]:
        self.call_names.append("count_tokens")
        schema_hash = RUNNER.sha256_json(kwargs["output_schema"])
        return {
            "total_tokens": 10,
            "request_hash": "1" * 64,
            "response_hash": "2" * 64,
            "canonical_schema_hash": schema_hash,
            "adapted_schema_hash": schema_hash,
            "schema_transform_count": 0,
            "model_requested": self.identity["model"],
            "within_hard_guard": True,
        }

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.call_names.append("invoke")
        if self.raise_on_invoke:
            raise RuntimeError("fixture_generate_failure")
        schema_hash = RUNNER.sha256_json(kwargs["output_schema"])
        attempt = {
            "task_id": kwargs["task_id"],
            "attempt_id": f"{kwargs['task_id']}_a1",
            "attempt_number": 1,
            "attempt_lineage": [],
            "provider": self.identity["provider"],
            "provider_profile": self.identity["profile"],
            "model_requested": self.identity["model"],
            "model_resolved": self.identity["model"],
            "adapter_identity": "fixture_adapter_v1",
            "transport_identity": "fixture_transport_v1",
            "request_hash": "3" * 64,
            "crop_sha256": kwargs["crop_sha256"],
            "model_view_hash": RUNNER.sha256_json(kwargs["model_view"]),
            "canonical_schema_hash": schema_hash,
            "adapted_schema_hash": schema_hash,
            "schema_transform_count": 0,
            "terminal_failure_class": self.terminal_failure_class,
            "hidden_retry": self.hidden_retry,
            "provider_failover": False,
            "usage": {"input_tokens": 10, "output_tokens": 1, "total_tokens": 11},
        }
        return {
            "attempt": attempt,
            "raw_private_response": {"fixture": True},
            "json_output": (
                self.json_output if self.terminal_failure_class is None else None
            ),
            "response_bytes": 2,
            "response_hash": "4" * 64,
            "visible_output_bytes": 1,
            "visible_output_hash": "5" * 64,
        }


class _CountFailureProvider:
    def count_tokens(self, **_kwargs: Any) -> dict[str, Any]:
        raise RUNNER.BenchmarkError("fixture_count_failure")

    def invoke(self, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("generation must not run after failed preflight")


class _TwoCropRenderer:
    def __init__(self, pdf_sha256: str) -> None:
        self.pdf_sha256 = pdf_sha256

    def render_full_page(self, **_kwargs: Any) -> dict[str, Any]:
        return _raster_payload(
            pdf_sha256=self.pdf_sha256,
            page_number=1,
            bbox=[0.0, 0.0, 100.0, 100.0],
            crop_id="page_crop",
        )

    def render(self, **kwargs: Any) -> dict[str, Any]:
        if str(kwargs["table_ref"]).endswith("candidate_1"):
            raise RUNNER.BenchmarkError("fixture_first_crop_failure")
        return _raster_payload(
            pdf_sha256=self.pdf_sha256,
            page_number=1,
            bbox=[round(float(item), 6) for item in kwargs["table_bbox"]],
            crop_id="second_crop",
        )


def _detection_output() -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_pdf_dual_vlm_detection_v1",
        "document_id": "case_1",
        "page_number": 1,
        "page_status": "present",
        "candidates": [
            {
                "candidate_id": "candidate_1",
                "bbox": [0.1, 0.1, 0.3, 0.3],
                "state": "present",
                "reason_codes": [],
            },
            {
                "candidate_id": "candidate_2",
                "bbox": [0.6, 0.6, 0.9, 0.9],
                "state": "present",
                "reason_codes": [],
            },
        ],
        "uncertainty_codes": [],
    }


def _raster_payload(
    *, pdf_sha256: str, page_number: int, bbox: list[float], crop_id: str
) -> dict[str, Any]:
    width, height = 1, 1
    source_width = bbox[2] - bbox[0]
    source_height = bbox[3] - bbox[1]
    manifest = {
        "schema_version": "broker_reports_pdf_table_crop_v1",
        "policy_version": "pdf_table_raster_policy_v1",
        "crop_id": crop_id,
        "document_ref": "case_1",
        "pdf_sha256": pdf_sha256,
        "page_number": page_number,
        "table_ref": crop_id,
        "declared_table_bbox": bbox,
        "rendered_bbox": bbox,
        "source_coordinate_space": "pdf_top_left_points",
        "pixel_coordinate_space": "crop_top_left_pixels",
        "source_to_pixel_transform": {
            "scale_x": round(width / source_width, 9),
            "scale_y": round(height / source_height, 9),
            "translate_source_x": round(-bbox[0], 9),
            "translate_source_y": round(-bbox[1], 9),
        },
        "renderer": "pymupdf",
        "renderer_version": "1.26.5",
        "page_rotation": 0,
        "applied_rotation": 0,
        "padding_points": 0,
        "dpi": 150,
        "dpi_revision_reason": "primary_150_dpi",
        "width": width,
        "height": height,
        "pixels": width * height,
        "png_bytes": len(PNG),
        "png_sha256": hashlib.sha256(PNG).hexdigest(),
        "lossless": True,
        "silent_resize_performed": False,
    }
    return {
        "manifest": _sealed_manifest(manifest),
        "private_png_base64": base64.b64encode(PNG).decode("ascii"),
    }


def _sealed_manifest(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    result.pop("manifest_hash", None)
    result["manifest_hash"] = RUNNER.sha256_json(result)
    return result
