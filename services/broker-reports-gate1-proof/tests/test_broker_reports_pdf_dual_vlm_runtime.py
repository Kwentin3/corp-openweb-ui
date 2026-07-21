from __future__ import annotations

import base64
import copy
import hashlib
from typing import Any

import pytest

from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (
    CANONICAL_TABLE_SCHEMA_VERSION,
    sha256_json,
)
from broker_reports_gate1.pdf_dual_vlm_runtime import (
    DECISION_STATUSES,
    PDF_DUAL_VLM_EXECUTION_SCHEMA,
    PdfDualVlmRuntimeConfig,
    PdfDualVlmRuntimeError,
    PdfDualVlmRuntimeFactory,
    validate_pdf_dual_vlm_decision,
)
from broker_reports_gate1.pdf_table_raster import PDF_TABLE_CANDIDATE_SCHEMA


def _table(table_id: str, value: str = "1,000") -> dict[str, Any]:
    return {
        "schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
        "table_id": table_id,
        "row_count": 2,
        "column_count": 2,
        "cells": [
            {
                "row_index": 0,
                "column_index": 0,
                "row_span": 1,
                "column_span": 1,
                "content_state": "present",
                "source_text": "Item",
            },
            {
                "row_index": 0,
                "column_index": 1,
                "row_span": 1,
                "column_span": 1,
                "content_state": "present",
                "source_text": "Value",
            },
            {
                "row_index": 1,
                "column_index": 0,
                "row_span": 1,
                "column_span": 1,
                "content_state": "present",
                "source_text": "Cash",
            },
            {
                "row_index": 1,
                "column_index": 1,
                "row_span": 1,
                "column_span": 1,
                "content_state": "present",
                "source_text": value,
            },
        ],
    }


def _candidate() -> dict[str, Any]:
    png = b"\x89PNG\r\n\x1a\nsynthetic-dual-vlm-runtime"
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
        "detector_contract_version": ("broker_reports_pdf_table_detection_response_v2"),
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
    ) -> None:
        self.name = name
        self.value = value
        self.failure_class = failure_class
        self.malformed = malformed
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
            "adapted_schema_hash": ("e" * 64 if self.name == "gemini" else schema_hash),
            "schema_transform_count": 7 if self.name == "gemini" else 0,
            "model_requested": self.qualify()["requested_model_id"],
            "transport_identity": self.name + "_native_count",
            "within_hard_guard": True,
        }

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.invoke_calls += 1
        qualification = self.qualify()
        table_id = kwargs["model_view"]["input_identity"]["table_id"]
        output: Any = _table(table_id, self.value)
        if self.malformed:
            output = {"schema_version": CANONICAL_TABLE_SCHEMA_VERSION}
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
            "text": "must not escape",
            "response_hash": hashlib.sha256(
                (self.name + self.value).encode()
            ).hexdigest(),
        }


def _runtime(gemini: _Provider, openai: _Provider, *, enabled: bool = True):
    return PdfDualVlmRuntimeFactory(
        PdfDualVlmRuntimeConfig(enabled=enabled)
    ).create_with_providers(gemini=gemini, openai=openai)


def test_disabled_runtime_performs_no_provider_work() -> None:
    gemini = _Provider("gemini")
    openai = _Provider("openai")

    result = _runtime(gemini, openai, enabled=False).run([_candidate()])

    assert result.safe_summary["status"] == "disabled"
    assert result.private_decisions == []
    assert gemini.qualify_calls == openai.qualify_calls == 0


def test_full_provider_agreement_remains_review_only_without_source_accounting() -> (
    None
):
    result = _runtime(_Provider("gemini"), _Provider("openai")).run([_candidate()])
    decision = result.private_decisions[0]

    assert decision["status"] == "proposal_requires_review"
    assert decision["comparison"]["FULL_TABLE_CONSENSUS"] is True
    assert decision["canonical_table"] is None
    assert decision["provider_proposal_canonical_authority"] is False
    assert decision["deterministic_validator"] == {
        "validator_version": "pdf_dual_vlm_deterministic_validator_v1",
        "provider_contracts_valid": True,
        "same_bounded_input_for_all_providers": True,
        "source_to_table_accounting": "unavailable",
        "canonical_promotion_allowed": False,
    }
    assert "source_to_table_accounting_unavailable" in decision["reason_codes"]
    assert result.safe_summary["canonical_tables_published"] == 0
    assert result.safe_summary["whole_document_provider_uploads"] == 0


def test_real_disagreement_is_preserved_and_fails_closed() -> None:
    result = _runtime(
        _Provider("gemini", value="1,000"),
        _Provider("openai", value="1,001"),
    ).run([_candidate()])
    decision = result.private_decisions[0]

    assert decision["status"] == "proposal_requires_review"
    assert decision["comparison"]["FULL_TABLE_CONSENSUS"] is False
    assert decision["comparison"]["smallest_difference"]["class"] == (
        "differing_source_text"
    )
    assert "provider_disagreement" in decision["reason_codes"]
    assert decision["canonical_table"] is None


def test_execution_record_preserves_required_lineage_and_drops_raw_response() -> None:
    result = _runtime(_Provider("gemini"), _Provider("openai")).run([_candidate()])

    for execution in result.private_decisions[0]["executions"]:
        assert execution["schema_version"] == PDF_DUAL_VLM_EXECUTION_SCHEMA
        assert execution["source_ref"] == "document_test"
        assert execution["source_sha256"] == "a" * 64
        assert execution["page_number"] == 2
        assert execution["input_hash"] == execution["crop_sha256"]
        assert execution["requested_model_id"] == execution["resolved_model_id"]
        assert execution["prompt_id"] == ("pdf_dual_vlm_canonical_table_normalizer")
        assert execution["prompt_version"] == ("dual_vlm_canonical_table_normalizer_v4")
        assert len(execution["prompt_hash"]) == 64
        assert len(execution["canonical_schema_hash"]) == 64
        assert len(execution["provider_adapted_schema_hash"]) == 64
        assert execution["maximum_output_tokens"] == 16_384
        assert execution["maximum_counted_input_tokens"] == 24_000
        assert execution["transport_timeout_seconds"] == 240
        assert execution["deadline_policy"] == "per_native_request_no_retry"
        assert execution["attempt_number"] == 1
        assert execution["attempt_lineage"] == []
        assert execution["usage"]["output_tokens"] == 123
        assert execution["latency_ms"] == 15
        assert execution["terminal_provider_status"] == "completed"
        assert len(execution["response_hash"]) == 64
        assert execution["validator_result"]["status"] == "passed"
        assert execution["hidden_retry"] is False
        assert execution["provider_failover"] is False
        assert execution["whole_document_uploaded"] is False
        assert "raw_private_response" not in execution
        assert "text" not in execution


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        (_Provider("openai", malformed=True), "malformed_provider_output"),
        (
            _Provider("openai", failure_class="provider_refusal"),
            "provider_refusal_or_incomplete",
        ),
        (
            _Provider("openai", failure_class="provider_incomplete"),
            "provider_refusal_or_incomplete",
        ),
        (
            _Provider("openai", failure_class="timeout_or_transport"),
            "provider_refusal_or_incomplete",
        ),
    ],
)
def test_terminal_provider_outcomes_are_explicit(
    provider: _Provider, expected: str
) -> None:
    result = _runtime(_Provider("gemini"), provider).run([_candidate()])

    assert result.private_decisions[0]["status"] == expected
    assert result.private_decisions[0]["canonical_table"] is None


def test_whole_document_or_mutated_crop_envelope_is_rejected_before_generation() -> (
    None
):
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

    assert "proposal_validated_and_accepted" in DECISION_STATUSES
    assert "proposal_requires_review" in DECISION_STATUSES
    assert "provider_refusal_or_incomplete" in DECISION_STATUSES


def test_decision_validator_rejects_canonical_promotion_without_source_accounting() -> (
    None
):
    result = _runtime(_Provider("gemini"), _Provider("openai")).run([_candidate()])
    decision = result.private_decisions[0]
    assert validate_pdf_dual_vlm_decision(decision) == []

    forged = copy.deepcopy(decision)
    forged["status"] = "proposal_validated_and_accepted"
    forged["canonical_table"] = copy.deepcopy(forged["proposals"]["gemini"])
    forged["review_required"] = False
    forged["deterministic_validator"]["canonical_promotion_allowed"] = True
    unhashed = copy.deepcopy(forged)
    unhashed.pop("decision_hash")
    forged["decision_hash"] = sha256_json(unhashed)

    assert "pdf_dual_vlm_acceptance_authority_invalid" in (
        validate_pdf_dual_vlm_decision(forged)
    )
