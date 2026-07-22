from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from broker_reports_gate1.pdf_dual_vlm_runtime import (
    DECISION_STATUSES,
    PDF_DUAL_VLM_EXECUTION_SCHEMA,
    PDF_DUAL_VLM_OPENAI_POLICY_VERSION,
    PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION,
    PdfDualVlmRuntimeConfig,
    PdfDualVlmRuntimeError,
    PdfDualVlmRuntimeFactory,
    sha256_json,
    validate_pdf_dual_vlm_decision,
)
from broker_reports_gate1.pdf_table_raster import PDF_TABLE_CANDIDATE_SCHEMA
from broker_reports_gate1.semantic_visual_table_contracts import (
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
    SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
)


def _transcription(value: str = "1,000") -> dict[str, Any]:
    return {
        "description": "Two-column cash table.",
        "rows": [["Item", "Value"], ["Cash", value]],
    }


def _candidate() -> dict[str, Any]:
    png = b"\x89PNG\r\n\x1a\nsynthetic-semantic-vlm-runtime"
    png_hash = hashlib.sha256(png).hexdigest()
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
        "png_sha256": png_hash,
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
    def __init__(
        self,
        name: str,
        *,
        value: str = "1,000",
        failure_class: str | None = None,
        malformed: bool = False,
        raw_text_override: str | None = None,
    ) -> None:
        self.name = name
        self.value = value
        self.failure_class = failure_class
        self.malformed = malformed
        self.raw_text_override = raw_text_override
        self.qualify_calls = 0
        self.count_calls = 0
        self.invoke_calls = 0

    def qualify(self) -> dict[str, Any]:
        self.qualify_calls += 1
        model = (
            "models/gemini-3.5-flash"
            if self.name == "gemini"
            else "gpt-5.4-mini-2026-03-17"
        )
        return {
            "status": "qualified",
            "provider_profile": (
                "google_gemini" if self.name == "gemini" else "openai_gpt"
            ),
            "provider_profile_revision": self.name + "_profile_revision",
            "requested_model_id": model,
            "resolved_model_id": model,
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "http_status": 200,
            "response_hash": hashlib.sha256(self.name.encode()).hexdigest(),
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_retry": False,
            "provider_failover": False,
        }

    def count_tokens(self, **kwargs: Any) -> dict[str, Any]:
        self.count_calls += 1
        schema_hash = sha256_json(kwargs["output_schema"])
        return {
            "total_tokens": 321,
            "input_tokens": 321,
            "http_status": 200,
            "request_hash": "c" * 64,
            "response_hash": "d" * 64,
            "canonical_schema_hash": schema_hash,
            "adapted_schema_hash": "e" * 64,
            "schema_transform_count": 7 if self.name == "gemini" else 0,
            "model_requested": self.qualify()["requested_model_id"],
            "transport_identity": self.name + "_native_count",
            "within_hard_guard": True,
        }

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.invoke_calls += 1
        qualification = self.qualify()
        output: Any = _transcription(self.value)
        if self.malformed:
            output = {"description": "missing rows"}
        attempt = {
            "attempt_number": 1,
            "attempt_lineage": [],
            "provider_profile": qualification["provider_profile"],
            "provider_profile_revision": qualification["provider_profile_revision"],
            "model_requested": qualification["requested_model_id"],
            "model_resolved": qualification["resolved_model_id"],
            "canonical_schema_hash": sha256_json(kwargs["output_schema"]),
            "adapted_schema_hash": "f" * 64,
            "schema_transform_count": 3,
            "usage": {"input_tokens": 321, "output_tokens": 123},
            "duration_ms": 15,
            "finish_reason": "completed",
            "terminal_failure_class": self.failure_class,
        }
        return {
            "attempt": attempt,
            "json_output": None if self.failure_class else output,
            "raw_private_response": {"must_not_escape": True},
            "text": self.raw_text_override
            if self.raw_text_override is not None
            else json.dumps(output, ensure_ascii=False),
            "response_hash": hashlib.sha256(
                (self.name + self.value).encode()
            ).hexdigest(),
        }


def _runtime(
    gemini: _Provider,
    openai: _Provider | None = None,
    *,
    enabled: bool = True,
    openai_policy: str = "disabled",
):
    execution_mode = (
        "diagnostic_control" if openai_policy == "diagnostic_control" else "gemini_master"
    )
    return PdfDualVlmRuntimeFactory(
        PdfDualVlmRuntimeConfig(
            enabled=enabled,
            execution_mode=execution_mode,
            openai_invocation_policy=openai_policy,
        )
    ).create_with_providers(gemini=gemini, openai=openai)


def test_disabled_runtime_performs_no_provider_work() -> None:
    gemini = _Provider("gemini")
    openai = _Provider("openai")

    result = _runtime(gemini, openai, enabled=False).run([_candidate()])

    assert result.safe_summary["status"] == "disabled"
    assert result.private_decisions == []
    assert result.private_provider_evidence == []
    assert gemini.qualify_calls == openai.qualify_calls == 0


def test_default_valid_gemini_is_selected_without_any_openai_work() -> None:
    gemini = _Provider("gemini")
    openai = _Provider("openai")

    result = _runtime(gemini, openai).run([_candidate()])
    decision = result.private_decisions[0]

    assert decision["status"] == "semantic_transcription_valid"
    assert decision["selected_provider"] == "gemini"
    assert decision["semantic_transcription"] == _transcription()
    assert decision["proposals"] == {"gemini": _transcription()}
    assert decision["comparison"] is None
    assert decision["review_required"] is False
    assert decision["provider_merge"] is False
    assert decision["openai_fallback_used"] is False
    assert [item["provider"] for item in decision["executions"]] == ["gemini"]
    assert gemini.invoke_calls == 1
    assert openai.qualify_calls == openai.count_calls == openai.invoke_calls == 0
    assert result.safe_summary["semantic_transcriptions_valid"] == 1
    assert result.safe_summary["canonical_tables_published"] == 0
    evidence = result.private_provider_evidence
    assert len(evidence) == 1
    assert evidence[0]["decision_id"] == decision["decision_id"]
    assert evidence[0]["execution_hash"] == decision["executions"][0][
        "execution_hash"
    ]
    assert evidence[0]["raw_provider_response"] == {"must_not_escape": True}
    assert evidence[0]["parsed_semantic_response"] == _transcription()
    assert "raw_provider_response" not in result.safe_summary
    assert "raw_provider_response" not in decision


def test_explicit_openai_fallback_keeps_provider_identity_and_never_merges() -> None:
    gemini = _Provider("gemini", malformed=True)
    openai = _Provider("openai", value="1,001")

    result = _runtime(
        gemini,
        openai,
        openai_policy="fallback_on_gemini_terminal_failure",
    ).run([_candidate()])
    decision = result.private_decisions[0]

    assert decision["status"] == "semantic_transcription_valid"
    assert decision["selected_provider"] == "openai"
    assert decision["semantic_transcription"] == _transcription("1,001")
    assert decision["proposals"] == {
        "gemini": None,
        "openai": _transcription("1,001"),
    }
    assert decision["openai_invocation_role"] == "fallback"
    assert decision["openai_fallback_used"] is True
    assert decision["provider_merge"] is False
    assert decision["executions"][0]["terminal_provider_status"] == (
        "semantic_schema_violation"
    )
    assert decision["executions"][1]["provider"] == "openai"
    assert decision["executions"][1]["invocation_role"] == "fallback"
    assert result.safe_summary["openai_fallbacks"] == 1
    assert [item["provider"] for item in result.private_provider_evidence] == [
        "gemini",
        "openai",
    ]


def test_diagnostic_control_cannot_overwrite_valid_gemini() -> None:
    result = _runtime(
        _Provider("gemini", value="1,000"),
        _Provider("openai", value="9,999"),
        openai_policy="diagnostic_control",
    ).run([_candidate()])
    decision = result.private_decisions[0]

    assert decision["status"] == "semantic_transcription_valid"
    assert decision["selected_provider"] == "gemini"
    assert decision["semantic_transcription"] == _transcription("1,000")
    assert decision["proposals"]["openai"] == _transcription("9,999")
    assert decision["comparison"] is None
    assert decision["openai_invocation_role"] == "control"
    assert decision["openai_fallback_used"] is False
    assert decision["provider_merge"] is False
    assert result.safe_summary["openai_control_calls"] == 1


def test_failed_control_does_not_invalidate_valid_gemini() -> None:
    result = _runtime(
        _Provider("gemini"),
        _Provider("openai", failure_class="provider_refusal"),
        openai_policy="diagnostic_control",
    ).run([_candidate()])
    decision = result.private_decisions[0]

    assert decision["status"] == "semantic_transcription_valid"
    assert decision["selected_provider"] == "gemini"
    assert decision["proposals"]["openai"] is None
    assert "openai_diagnostic_control_provider_refusal" in decision["reason_codes"]


def test_execution_record_preserves_lineage_and_content_only_contract() -> None:
    result = _runtime(_Provider("gemini")).run([_candidate()])
    execution = result.private_decisions[0]["executions"][0]

    assert execution["schema_version"] == PDF_DUAL_VLM_EXECUTION_SCHEMA
    assert execution["source_ref"] == "document_test"
    assert execution["source_sha256"] == "a" * 64
    assert execution["page_number"] == 2
    assert execution["input_hash"] == execution["crop_sha256"]
    assert execution["provider"] == "gemini"
    assert execution["invocation_role"] == "master"
    assert execution["requested_model_id"] == execution["resolved_model_id"]
    assert execution["prompt_id"] == "pdf_semantic_visual_table_transcription"
    assert execution["prompt_version"] == SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION
    assert execution["output_schema_version"] == (
        SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION
    )
    assert len(execution["prompt_hash"]) == 64
    assert len(execution["canonical_schema_hash"]) == 64
    assert len(execution["provider_adapted_schema_hash"]) == 64
    assert execution["attempt_number"] == 1
    assert execution["attempt_lineage"] == []
    assert execution["deadline_policy"] == "per_native_request_no_retry"
    assert execution["validator_result"]["status"] == "passed"
    assert execution["hidden_retry"] is False
    assert execution["provider_failover"] is False
    assert execution["provider_switch"] is False
    assert execution["whole_document_uploaded"] is False
    assert "raw_private_response" not in execution
    assert "text" not in execution


@pytest.mark.parametrize(
    ("gemini", "expected"),
    [
        (_Provider("gemini", malformed=True), "malformed_provider_output"),
        (
            _Provider("gemini", failure_class="provider_refusal"),
            "provider_refusal_or_incomplete",
        ),
        (
            _Provider("gemini", failure_class="provider_incomplete"),
            "provider_refusal_or_incomplete",
        ),
        (
            _Provider("gemini", failure_class="timeout_or_transport"),
            "provider_refusal_or_incomplete",
        ),
    ],
)
def test_default_terminal_gemini_failures_do_not_call_openai(
    gemini: _Provider, expected: str
) -> None:
    openai = _Provider("openai")

    result = _runtime(gemini, openai).run([_candidate()])

    assert result.private_decisions[0]["status"] == expected
    assert result.private_decisions[0]["selected_provider"] is None
    assert result.private_decisions[0]["canonical_table"] is None
    assert openai.qualify_calls == openai.count_calls == openai.invoke_calls == 0


def test_runtime_rejects_explanation_outside_json_without_repair() -> None:
    gemini = _Provider(
        "gemini",
        raw_text_override=(
            '{"description":"Two-column cash table.",'
            '"rows":[["Item","Value"],["Cash","1,000"]]} explanation'
        ),
    )

    result = _runtime(gemini).run([_candidate()])
    decision = result.private_decisions[0]

    assert decision["status"] == "malformed_provider_output"
    assert decision["semantic_transcription"] is None
    validator = decision["executions"][0]["validator_result"]
    assert validator["status"] == "failed"
    assert "semantic_table_transcription_raw_json_invalid" in validator[
        "error_codes"
    ]
    assert validator["hidden_repair_performed"] is False


def test_whole_document_or_mutated_crop_is_rejected_before_generation() -> None:
    gemini = _Provider("gemini")
    openai = _Provider("openai")
    candidate = _candidate()
    candidate["pdf_bytes"] = b"forbidden"

    result = _runtime(gemini, openai).run([candidate])

    decision = result.private_decisions[0]
    assert decision["status"] == "unresolved_visual_scope"
    assert decision["executions"] == []
    assert gemini.invoke_calls == openai.invoke_calls == 0


def test_provider_selection_policy_is_closed_and_versioned() -> None:
    with pytest.raises(
        PdfDualVlmRuntimeError,
        match="pdf_dual_vlm_provider_selection_policy_invalid",
    ):
        PdfDualVlmRuntimeFactory(
            PdfDualVlmRuntimeConfig(
                enabled=True,
                provider_selection_policy_version="unversioned",
            )
        )
    with pytest.raises(
        PdfDualVlmRuntimeError,
        match="pdf_dual_vlm_provider_selection_policy_invalid",
    ):
        PdfDualVlmRuntimeFactory(
            PdfDualVlmRuntimeConfig(
                enabled=True,
                openai_invocation_policy="always_compare",
            )
        )

    config = PdfDualVlmRuntimeConfig()
    assert config.provider_selection_policy_version == (
        PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION
    )
    assert config.openai_policy_version == PDF_DUAL_VLM_OPENAI_POLICY_VERSION
    assert config.execution_mode == "gemini_master"
    assert config.openai_invocation_policy == "disabled"
    assert "semantic_transcription_valid" in DECISION_STATUSES


def test_decision_validator_rejects_control_overwrite_and_provider_merge() -> None:
    result = _runtime(
        _Provider("gemini"),
        _Provider("openai", value="9,999"),
        openai_policy="diagnostic_control",
    ).run([_candidate()])
    decision = result.private_decisions[0]
    assert validate_pdf_dual_vlm_decision(decision) == []

    forged = copy.deepcopy(decision)
    forged["selected_provider"] = "openai"
    forged["semantic_transcription"] = copy.deepcopy(forged["proposals"]["openai"])
    forged["provider_merge"] = True
    unhashed = copy.deepcopy(forged)
    unhashed.pop("decision_hash")
    forged["decision_hash"] = sha256_json(unhashed)

    errors = validate_pdf_dual_vlm_decision(forged)
    assert "pdf_dual_vlm_semantic_selection_invalid" in errors
    assert "pdf_dual_vlm_authority_or_transport_invalid" in errors


def test_maintained_runtime_cannot_drift_back_to_geometric_model_contract() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "broker_reports_gate1"
        / "pdf_dual_vlm_runtime.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "pdf_dual_vlm_canonical_table_contracts",
        "normalizer_model_view",
        "validate_table_output",
        "canonicalize_table",
        "compare_tables(",
    ):
        assert forbidden not in source
