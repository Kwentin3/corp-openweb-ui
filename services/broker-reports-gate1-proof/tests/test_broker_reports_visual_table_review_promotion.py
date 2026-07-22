from __future__ import annotations

import base64
import copy
import hashlib
import json
from typing import Any

import pytest

from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import (
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    new_artifact_id,
)
from broker_reports_gate1.gate2_table_packages import Gate2TablePackageFactory
from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (
    CANONICAL_TABLE_SCHEMA_VERSION,
    compare_tables,
    sha256_json,
)
from broker_reports_gate1.pdf_table_raster import PDF_TABLE_CANDIDATE_SCHEMA
from broker_reports_gate1.pdf_visual_table_review import (
    VISUAL_REGION_ACCOUNTING_SUBMISSION_SCHEMA_VERSION,
    VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION,
    PdfVisualTableReviewError,
    PdfVisualTableReviewFactory,
    VisualReviewAuthorityContext,
)
from broker_reports_gate1.table_projection import TableProjectionValidator
from broker_reports_gate1.visual_table_review_contracts import (
    VISUAL_REVIEW_CONTRACT_VERSION,
    validate_reviewed_visual_projection,
    validate_visual_review_receipt,
    validate_visual_review_seal,
)


def test_accepted_without_correction_is_sealed_and_gate2_packageable() -> None:
    decision = _decision()
    result = _review(decision, _submission(decision))

    assert validate_visual_review_receipt(result.review_receipt) == []
    assert (
        validate_visual_review_seal(
            result.review_seal,
            receipt=result.review_receipt,
            projection=result.canonical_projection,
        )
        == []
    )
    assert result.review_receipt["decision"] == "accepted_without_correction"
    assert result.review_receipt["canonical_promotion_allowed"] is True
    assert result.review_receipt["provider_consensus_auto_acceptance"] is False
    assert result.review_receipt["local_ocr_evidence_used"] is False
    projection = result.canonical_projection
    assert projection is not None
    assert validate_reviewed_visual_projection(projection)["passed"] is True

    package = Gate2TablePackageFactory().create().build(
        projection=projection,
        case_id="case-review",
        table_projection_artifact_ref="art_reviewed_projection",
    )

    assert package["prompt_contract"]["model_call_performed"] is False
    assert package["privacy_policy_scope"] == "gate2_package_construction_only"
    assert package["privacy_policy"]["ocr_vlm_used"] is False
    assert package["upstream_source_representation"] == {
        "source_representation_kind": "reviewed_visual_canonical_table",
        "review_receipt_id": result.review_receipt["review_receipt_id"],
        "review_receipt_hash": result.review_receipt["receipt_hash"],
        "review_seal_hash": result.review_seal["seal_hash"],
        "review_decision": "accepted_without_correction",
        "reviewer_type": "human_reviewed",
        "source_to_table_accounting": "passed",
        "upstream_visual_vlm_used": True,
        "upstream_page_rendering_used": True,
        "local_ocr_evidence_used": False,
        "provider_consensus_canonical_authority": False,
    }


def test_accepted_with_correction_requires_exact_diff_and_corrected_cell() -> None:
    decision = _decision(openai_value="1,001")
    candidate = _table("pdftable_test", "1,002")
    comparison = compare_tables(decision["proposals"]["openai"], candidate)
    acknowledgements = [
        {
            "difference_sha256": sha256_json(item),
            "reviewer_reason_code": "source_crop_verified_correction",
        }
        for item in comparison["differences"]
    ]
    submission = _submission(
        decision,
        review_decision="accepted_with_correction",
        selected_provider="openai",
        canonical_candidate=candidate,
        correction_acknowledgements=acknowledgements,
        corrected_cells={(1, 1)},
    )

    result = _review(decision, submission)

    assert len(result.review_receipt["corrections"]) == 1
    assert result.review_receipt["corrections"][0]["difference_class"] == (
        "differing_source_text"
    )
    assert result.review_receipt["decision"] == "accepted_with_correction"
    assert result.canonical_projection is not None
    assert validate_reviewed_visual_projection(result.canonical_projection)[
        "passed"
    ]
    package = Gate2TablePackageFactory().create().build(
        projection=result.canonical_projection,
        case_id="case-corrected",
    )
    assert package["upstream_source_representation"]["review_decision"] == (
        "accepted_with_correction"
    )


@pytest.mark.parametrize("review_decision", ["rejected", "unresolved", "unsupported"])
def test_nonaccepted_review_is_sealed_but_never_canonical(
    review_decision: str,
) -> None:
    decision = _decision()
    submission = _submission(decision, review_decision=review_decision)

    result = _review(decision, submission)

    assert result.review_receipt["canonical_promotion_allowed"] is False
    assert result.review_receipt["lifecycle_status"] == "private_ready"
    assert result.canonical_projection is None
    assert (
        validate_visual_review_seal(
            result.review_seal,
            receipt=result.review_receipt,
            projection=None,
        )
        == []
    )
    with pytest.raises((AttributeError, TypeError, ValueError)):
        Gate2TablePackageFactory().create().build(
            projection=result.canonical_projection,  # type: ignore[arg-type]
            case_id="case-rejected",
        )


def test_provider_consensus_cannot_create_canonical_without_review_factory() -> None:
    decision = _decision()

    assert decision["comparison"]["FULL_TABLE_CONSENSUS"] is True
    assert decision["canonical_table"] is None
    assert decision["provider_proposal_canonical_authority"] is False
    assert decision["review_required"] is True

    with pytest.raises(
        PdfVisualTableReviewError, match="visual_review_human_authority_invalid"
    ):
        PdfVisualTableReviewFactory().create(
            authority=VisualReviewAuthorityContext(
                authenticated_user_id="authenticated-user",
                reviewer_id="forged-reviewer",
                reviewer_type="human_reviewed",
                authority_ref="server_authenticated_user",
            )
        )


def test_mutation_invalidates_seal_and_gate2_handoff() -> None:
    result = _review(_decision(), _submission(_decision()))
    projection = copy.deepcopy(result.canonical_projection)
    assert projection is not None
    projection["private_values"][0]["normalized_value"] = "mutated"

    validation = validate_reviewed_visual_projection(projection)

    assert validation["passed"] is False
    assert "visual_review_seal_binding_invalid" in validation["reason_codes"]
    with pytest.raises(ValueError, match="gate2_table_projection_invalid"):
        Gate2TablePackageFactory().create().build(
            projection=projection,
            case_id="case-tampered",
        )


def test_incomplete_accounting_and_local_ocr_attestation_fail_closed() -> None:
    decision = _decision()
    incomplete = _submission(decision)
    incomplete["region_cell_accounting"]["cell_bindings"].pop()
    with pytest.raises(
        PdfVisualTableReviewError, match="visual_region_cell_coverage_invalid"
    ):
        _review(decision, incomplete)

    local_ocr = _submission(decision)
    local_ocr["attestations"]["local_ocr_evidence_used"] = True
    with pytest.raises(
        PdfVisualTableReviewError, match="visual_review_attestations_fail_closed"
    ):
        _review(decision, local_ocr)


def test_receipt_and_proposal_lineage_tamper_fail_closed() -> None:
    decision = _decision()
    result = _review(decision, _submission(decision))
    receipt = copy.deepcopy(result.review_receipt)
    receipt["source_lineage"]["page_number"] = 99
    assert "visual_review_source_lineage_hash_invalid" in (
        validate_visual_review_receipt(receipt)
    )

    proposal_tamper = copy.deepcopy(decision)
    proposal_tamper["proposals"]["gemini"]["cells"][0]["source_text"] = "tampered"
    material = copy.deepcopy(proposal_tamper)
    material.pop("decision_hash")
    proposal_tamper["decision_hash"] = sha256_json(material)
    with pytest.raises(
        PdfVisualTableReviewError,
        match="visual_review_provider_proposal_lineage_invalid",
    ):
        _review(proposal_tamper, _submission(proposal_tamper))


def test_generic_self_asserted_pdf_projection_cannot_bypass_review_boundary() -> None:
    result = _review(_decision(), _submission(_decision()))
    forged = copy.deepcopy(result.canonical_projection)
    assert forged is not None
    forged["table_origin"] = "provider_consensus_self_asserted"
    forged["visual_review"] = {}
    forged["canonical_validation"] = {"validator_status": "passed"}
    forged["table_projection_checksum_ref"] = _projection_checksum(forged)

    assert TableProjectionValidator().validate(forged)["passed"] is True
    with pytest.raises(
        ValueError, match="gate2_pdf_canonical_boundary_unsupported"
    ):
        Gate2TablePackageFactory().create().build(
            projection=forged,
            case_id="case-forged",
        )


def test_contract_is_versioned_and_delegated_review_stays_explicit() -> None:
    decision = _decision()
    service = PdfVisualTableReviewFactory().create(
        authority=VisualReviewAuthorityContext(
            authenticated_user_id="delegating-user",
            reviewer_id="codex-technical-reviewer",
            reviewer_type="delegated_agent_reviewed",
            authority_ref="delegation_goal2_2026_07_21",
        )
    )
    result = service.review(decision=decision, submission=_submission(decision))

    assert result.review_receipt["contract_version"] == (
        VISUAL_REVIEW_CONTRACT_VERSION
    )
    assert result.review_receipt["reviewer"]["reviewer_type"] == (
        "delegated_agent_reviewed"
    )
    assert result.review_receipt["reviewer"]["authenticated_user_id"] == (
        "delegating-user"
    )


def test_receipt_and_seal_use_existing_private_artifact_lifecycle(tmp_path) -> None:
    result = _review(_decision(), _submission(_decision()))
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    retention = build_retention_policy(mode="api_smoke")

    for artifact_type, payload in (
        ("broker_reports_visual_table_review_receipt_v1", result.review_receipt),
        ("broker_reports_visual_table_review_seal_v1", result.review_seal),
    ):
        record = ArtifactRecord(
            artifact_id=new_artifact_id(),
            artifact_type=artifact_type,
            case_id="case-review",
            chat_id="chat-review",
            user_id="review-user",
            normalization_run_id="visual-review-run",
            document_id="document_test",
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"scope": "case_private", "requires_user_id": True},
            validation_status="validated",
            lifecycle_status=result.review_receipt["lifecycle_status"],
            payload=payload,
            safe_metadata={"decision": result.review_receipt["decision"]},
        )

        stored = store.put_record(record)

        assert stored.lifecycle_status == "private_ready"
        assert store.read_payload(stored) == payload


def _review(decision: dict[str, Any], submission: dict[str, Any]):
    return PdfVisualTableReviewFactory().create(
        authority=VisualReviewAuthorityContext(
            authenticated_user_id="review-user",
            reviewer_id="review-user",
            reviewer_type="human_reviewed",
            authority_ref="server_authenticated_user",
        )
    ).review(decision=decision, submission=submission)


def _submission(
    decision: dict[str, Any],
    *,
    review_decision: str = "accepted_without_correction",
    selected_provider: str = "gemini",
    canonical_candidate: dict[str, Any] | None = None,
    correction_acknowledgements: list[dict[str, Any]] | None = None,
    corrected_cells: set[tuple[int, int]] | None = None,
) -> dict[str, Any]:
    accepted = review_decision.startswith("accepted_")
    if not accepted:
        return {
            "schema_version": VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION,
            "reviewed_at": "2026-07-21T18:00:00+03:00",
            "review_decision": review_decision,
            "decision_reason_codes": [f"review_{review_decision}"],
            "selected_proposal_provider": None,
            "canonical_candidate": None,
            "correction_acknowledgements": [],
            "region_cell_accounting": None,
            "attestations": _attestations(accepted=False),
        }
    candidate = copy.deepcopy(
        canonical_candidate or decision["proposals"][selected_provider]
    )
    lineage = decision["source_lineage"]
    corrected_cells = corrected_cells or set()
    bindings = []
    for cell in candidate["cells"]:
        row = int(cell["row_index"])
        column = int(cell["column_index"])
        x0 = column / candidate["column_count"]
        y0 = row / candidate["row_count"]
        x1 = (column + cell["column_span"]) / candidate["column_count"]
        y1 = (row + cell["row_span"]) / candidate["row_count"]
        bindings.append(
            {
                "row_index": row,
                "column_index": column,
                "bbox_normalized": [x0, y0, x1, y1],
                "observed_content_state": cell["content_state"],
                "observed_text_sha256": hashlib.sha256(
                    cell["source_text"].encode("utf-8")
                ).hexdigest(),
                "review_action": (
                    "corrected" if (row, column) in corrected_cells else "confirmed"
                ),
            }
        )
    return {
        "schema_version": VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION,
        "reviewed_at": "2026-07-21T18:00:00+03:00",
        "review_decision": review_decision,
        "decision_reason_codes": ["source_crop_review_completed"],
        "selected_proposal_provider": selected_provider,
        "canonical_candidate": candidate,
        "correction_acknowledgements": correction_acknowledgements or [],
        "region_cell_accounting": {
            "schema_version": VISUAL_REGION_ACCOUNTING_SUBMISSION_SCHEMA_VERSION,
            "crop_sha256": lineage["crop_sha256"],
            "coordinate_space": "normalized_0_1_top_left",
            "image_width": lineage["image_width"],
            "image_height": lineage["image_height"],
            "cell_bindings": bindings,
            "non_table_regions": [],
            "all_canonical_cells_accounted": True,
            "source_region_inventory_complete": True,
        },
        "attestations": _attestations(accepted=True),
    }


def _attestations(*, accepted: bool) -> dict[str, bool]:
    return {
        "exact_bounded_crop_reviewed": True,
        "every_canonical_cell_reviewed": accepted,
        "source_regions_accounted": accepted,
        "provider_output_not_reference_truth": True,
        "provider_consensus_not_acceptance_authority": True,
        "local_ocr_evidence_used": False,
    }


def _decision(*, openai_value: str = "1,000") -> dict[str, Any]:
    manifest = _candidate()["manifest"]
    lineage = {
        "declared_scope": "one_table_crop",
        "source_ref": manifest["document_ref"],
        "source_sha256": manifest["pdf_sha256"],
        "page_number": manifest["page_number"],
        "crop_id": manifest["crop_id"],
        "candidate_ref": manifest["candidate_ref"],
        "crop_sha256": manifest["png_sha256"],
        "crop_manifest_hash": manifest["manifest_hash"],
        "declared_table_bbox": copy.deepcopy(manifest["declared_table_bbox"]),
        "rendered_bbox": copy.deepcopy(manifest["rendered_bbox"]),
        "renderer": manifest["renderer"],
        "renderer_version": manifest["renderer_version"],
        "dpi": manifest["dpi"],
        "image_width": manifest["width"],
        "image_height": manifest["height"],
        "whole_document_available": False,
    }
    proposals = {
        "gemini": _table("pdftable_test", "1,000"),
        "openai": _table("pdftable_test", openai_value),
    }
    executions = [
        _legacy_execution(provider, proposals[provider], lineage)
        for provider in ("gemini", "openai")
    ]
    decision = {
        "schema_version": "broker_reports_pdf_dual_vlm_decision_v1",
        "policy_version": "pdf_dual_vlm_runtime_policy_v1",
        "decision_id": "pdfdualvlmdecision_legacyreviewfixture",
        "status": "proposal_requires_review",
        "reason_codes": ["provider_agreement_has_no_canonical_authority"],
        "source_lineage": lineage,
        "input_hash": lineage["crop_sha256"],
        "provider_selection": {
            "policy_version": "pdf_dual_vlm_provider_selection_v1",
            "execution_mode": "dual_provider_comparison",
            "primary_provider": "gemini",
            "primary_model_id": "models/gemini-3.5-flash",
            "review_provider": "openai",
            "review_model_id": "gpt-5.4-mini-2026-03-17",
            "provider_order": ["gemini", "openai"],
            "hidden_retry": False,
            "provider_failover": False,
            "provider_switch": False,
        },
        "executions": executions,
        "proposals": proposals,
        "comparison": compare_tables(proposals["gemini"], proposals["openai"]),
        "deterministic_validator": {
            "validator_version": "pdf_dual_vlm_deterministic_validator_v1",
            "provider_contracts_valid": True,
            "same_bounded_input_for_all_providers": True,
            "source_to_table_accounting": "unavailable",
            "canonical_promotion_allowed": False,
        },
        "canonical_table": None,
        "provider_proposal_canonical_authority": False,
        "review_required": True,
        "hidden_retry": False,
        "provider_failover": False,
        "whole_document_provider_upload": False,
    }
    decision["decision_hash"] = sha256_json(decision)
    return decision


def _legacy_execution(
    provider: str,
    proposal: dict[str, Any],
    lineage: dict[str, Any],
) -> dict[str, Any]:
    model_id = (
        "models/gemini-3.5-flash"
        if provider == "gemini"
        else "gpt-5.4-mini-2026-03-17"
    )
    execution = {
        "schema_version": "broker_reports_pdf_dual_vlm_execution_v1",
        "policy_version": "pdf_dual_vlm_runtime_policy_v1",
        "task_id": f"pdfdualvlm_legacy_{provider}",
        "source_lineage_hash": sha256_json(lineage),
        "source_ref": lineage["source_ref"],
        "source_sha256": lineage["source_sha256"],
        "page_number": lineage["page_number"],
        "crop_id": lineage["crop_id"],
        "crop_sha256": lineage["crop_sha256"],
        "input_hash": lineage["crop_sha256"],
        "provider": provider,
        "provider_profile": "google_gemini" if provider == "gemini" else "openai_gpt",
        "provider_profile_revision": f"{provider}_profile_revision",
        "requested_model_id": model_id,
        "resolved_model_id": model_id,
        "prompt_id": "pdf_dual_vlm_canonical_table_normalizer",
        "prompt_version": "broker_reports_pdf_dual_vlm_prompt_v1",
        "prompt_hash": "a" * 64,
        "model_view_hash": "b" * 64,
        "output_schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
        "canonical_schema_hash": "c" * 64,
        "provider_adapted_schema_hash": "c" * 64,
        "schema_transform_count": 0,
        "maximum_output_tokens": 16_384,
        "maximum_counted_input_tokens": 24_000,
        "transport_timeout_seconds": 240,
        "deadline_policy": "per_native_request_no_retry",
        "operation_started_at": "2026-07-21T12:00:00+00:00",
        "operation_deadline_at": "2026-07-21T12:04:00+00:00",
        "operation_ended_at": "2026-07-21T12:00:01+00:00",
        "attempt_number": 1,
        "attempt_lineage": [],
        "preflight": {},
        "usage": {},
        "latency_ms": 10,
        "terminal_provider_status": "completed",
        "finish_reason": "completed",
        "response_hash": "d" * 64,
        "validator_result": {
            "validator_version": "pdf_dual_vlm_deterministic_validator_v1",
            "status": "passed",
            "error_codes": [],
            "canonical_proposal_hash": sha256_json(proposal),
        },
        "hidden_retry": False,
        "provider_failover": False,
        "provider_switch": False,
        "whole_document_uploaded": False,
    }
    execution["execution_hash"] = sha256_json(execution)
    return execution


def _table(table_id: str, value: str) -> dict[str, Any]:
    texts = ("Item", "Value", "Cash", value)
    return {
        "schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
        "table_id": table_id,
        "row_count": 2,
        "column_count": 2,
        "cells": [
            {
                "row_index": ordinal // 2,
                "column_index": ordinal % 2,
                "row_span": 1,
                "column_span": 1,
                "content_state": "present",
                "source_text": text,
            }
            for ordinal, text in enumerate(texts)
        ],
    }


def _candidate() -> dict[str, Any]:
    png = b"\x89PNG\r\n\x1a\nvisual-review-test"
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
    def __init__(self, name: str, *, value: str) -> None:
        self.name = name
        self.value = value

    def qualify(self) -> dict[str, Any]:
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
        qualification = self.qualify()
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
            "model_requested": qualification["requested_model_id"],
            "transport_identity": self.name + "_native_count",
            "within_hard_guard": True,
        }

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        qualification = self.qualify()
        output = _table(
            kwargs["model_view"]["input_identity"]["table_id"], self.value
        )
        return {
            "attempt": {
                "attempt_number": 1,
                "attempt_lineage": [],
                "provider_profile": qualification["provider_profile"],
                "provider_profile_revision": qualification[
                    "provider_profile_revision"
                ],
                "model_requested": qualification["requested_model_id"],
                "model_resolved": qualification["resolved_model_id"],
                "canonical_schema_hash": sha256_json(kwargs["output_schema"]),
                "adapted_schema_hash": sha256_json(kwargs["output_schema"]),
                "schema_transform_count": 0,
                "usage": {"input_tokens": 321, "output_tokens": 123},
                "duration_ms": 15,
                "finish_reason": "completed",
                "terminal_failure_class": None,
            },
            "json_output": output,
            "response_hash": hashlib.sha256(
                (self.name + self.value).encode()
            ).hexdigest(),
        }


def _projection_checksum(projection: dict[str, Any]) -> str:
    material = copy.deepcopy(projection)
    material.pop("table_projection_checksum_ref", None)
    material.pop("validator_status", None)
    material.pop("validator_reason_codes", None)
    digest = hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return "tableprojchk_" + digest[:24]
