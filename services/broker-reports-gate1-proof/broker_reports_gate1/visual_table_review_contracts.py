from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any

from .table_projection import TableProjectionValidator


VISUAL_REVIEW_CONTRACT_VERSION = "broker_reports_visual_table_review_contract_v1"
VISUAL_REVIEW_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_visual_table_review_receipt_v1"
)
VISUAL_REVIEW_SEAL_SCHEMA_VERSION = "broker_reports_visual_table_review_seal_v1"
VISUAL_REGION_ACCOUNTING_SCHEMA_VERSION = (
    "broker_reports_visual_region_cell_accounting_v1"
)
VISUAL_REVIEW_VALIDATOR_VERSION = (
    "broker_reports_visual_table_review_validator_v1"
)
REVIEWED_VISUAL_TABLE_ORIGIN = "reviewed_visual_canonical_table"
REVIEWED_VISUAL_CANONICAL_SCOPE = "ready_validated_projection_only"

ACCEPTED_REVIEW_DECISIONS = frozenset(
    {"accepted_without_correction", "accepted_with_correction"}
)
REVIEW_DECISIONS = frozenset(
    {*ACCEPTED_REVIEW_DECISIONS, "rejected", "unresolved", "unsupported"}
)
REVIEWER_TYPES = frozenset({"human_reviewed", "delegated_agent_reviewed"})

FACTORY_REQUIRED = (
    "PdfVisualTableReviewFactory.create is the only maintained writer of visual "
    "review receipts, seals and reviewed canonical projections"
)
FORBIDDEN = (
    "Provider agreement, provider confidence, local OCR evidence or an unsealed "
    "review payload must not promote a visual proposal to canonical"
)


def validate_visual_review_receipt(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["visual_review_receipt_invalid"]
    required = {
        "schema_version",
        "contract_version",
        "validator_version",
        "review_receipt_id",
        "input_decision_id",
        "input_decision_hash",
        "source_lineage",
        "source_lineage_hash",
        "provider_proposal_hashes",
        "reviewer",
        "reviewed_at",
        "decision",
        "decision_reason_codes",
        "selected_proposal_provider",
        "canonical_candidate_hash",
        "corrections",
        "corrections_hash",
        "region_cell_accounting_hash",
        "region_cell_accounting_summary",
        "attestations",
        "provider_consensus_auto_acceptance",
        "local_ocr_evidence_used",
        "canonical_promotion_authority",
        "canonical_promotion_allowed",
        "canonical_projection_ref",
        "seal_status",
        "lifecycle_status",
        "receipt_hash",
    }
    errors: list[str] = []
    subject = str(value.get("review_receipt_id") or "")
    if set(value) != required:
        errors.append("visual_review_receipt_fields_invalid")
    if (
        value.get("schema_version") != VISUAL_REVIEW_RECEIPT_SCHEMA_VERSION
        or value.get("contract_version") != VISUAL_REVIEW_CONTRACT_VERSION
        or value.get("validator_version") != VISUAL_REVIEW_VALIDATOR_VERSION
        or not subject
    ):
        errors.append("visual_review_receipt_identity_invalid")
    if not _is_sha256(value.get("input_decision_hash")):
        errors.append("visual_review_input_decision_hash_invalid")
    lineage = _object(value.get("source_lineage"))
    errors.extend(_validate_source_lineage(lineage))
    if value.get("source_lineage_hash") != _sha256_json(lineage):
        errors.append("visual_review_source_lineage_hash_invalid")
    proposals = _object(value.get("provider_proposal_hashes"))
    if set(proposals) != {"gemini", "openai"} or any(
        item is not None and not _is_sha256(item) for item in proposals.values()
    ):
        errors.append("visual_review_provider_proposal_hashes_invalid")
    errors.extend(_validate_reviewer(_object(value.get("reviewer"))))
    if not _timezone_timestamp(value.get("reviewed_at")):
        errors.append("visual_review_timestamp_invalid")
    decision = value.get("decision")
    if decision not in REVIEW_DECISIONS:
        errors.append("visual_review_decision_invalid")
    reasons = _strings(value.get("decision_reason_codes"))
    if not reasons or reasons != sorted(set(reasons)):
        errors.append("visual_review_decision_reasons_invalid")
    corrections = _dicts(value.get("corrections"))
    if value.get("corrections_hash") != _sha256_json(corrections):
        errors.append("visual_review_corrections_hash_invalid")
    for correction in corrections:
        if set(correction) != {
            "difference_sha256",
            "difference_class",
            "cell",
            "selected_provider_before_sha256",
            "canonical_after_sha256",
            "reviewer_reason_code",
        } or not _is_sha256(correction.get("difference_sha256")):
            errors.append("visual_review_correction_invalid")
            break
    summary = _object(value.get("region_cell_accounting_summary"))
    if value.get("region_cell_accounting_hash") is not None and not _is_sha256(
        value.get("region_cell_accounting_hash")
    ):
        errors.append("visual_review_accounting_hash_invalid")
    if summary and set(summary) != {
        "crop_sha256",
        "coordinate_space",
        "canonical_cells_total",
        "canonical_cells_accounted",
        "non_table_regions_total",
        "all_canonical_cells_accounted",
        "source_region_inventory_complete",
    }:
        errors.append("visual_review_accounting_summary_invalid")
    attestations = _object(value.get("attestations"))
    if set(attestations) != {
        "exact_bounded_crop_reviewed",
        "every_canonical_cell_reviewed",
        "source_regions_accounted",
        "provider_output_not_reference_truth",
        "provider_consensus_not_acceptance_authority",
        "local_ocr_evidence_used",
    }:
        errors.append("visual_review_attestations_invalid")
    elif (
        attestations.get("exact_bounded_crop_reviewed") is not True
        or attestations.get("provider_output_not_reference_truth") is not True
        or attestations.get("provider_consensus_not_acceptance_authority") is not True
        or attestations.get("local_ocr_evidence_used") is not False
    ):
        errors.append("visual_review_attestations_fail_closed")
    accepted = decision in ACCEPTED_REVIEW_DECISIONS
    if accepted:
        if (
            value.get("selected_proposal_provider") not in {"gemini", "openai"}
            or not _is_sha256(value.get("canonical_candidate_hash"))
            or not _is_sha256(value.get("region_cell_accounting_hash"))
            or not summary
            or summary.get("crop_sha256") != lineage.get("crop_sha256")
            or summary.get("all_canonical_cells_accounted") is not True
            or summary.get("source_region_inventory_complete") is not True
            or attestations.get("every_canonical_cell_reviewed") is not True
            or attestations.get("source_regions_accounted") is not True
            or value.get("canonical_promotion_authority")
            != "factory_bound_explicit_review"
            or value.get("canonical_promotion_allowed") is not True
            or not value.get("canonical_projection_ref")
            or value.get("lifecycle_status") != "private_ready"
        ):
            errors.append("visual_review_accepted_authority_invalid")
        if decision == "accepted_without_correction" and corrections:
            errors.append("visual_review_unexpected_corrections")
        if decision == "accepted_with_correction" and not corrections:
            errors.append("visual_review_required_corrections_missing")
    elif (
        value.get("selected_proposal_provider") is not None
        or value.get("canonical_candidate_hash") is not None
        or corrections
        or value.get("region_cell_accounting_hash") is not None
        or summary
        or value.get("canonical_promotion_authority") is not None
        or value.get("canonical_promotion_allowed") is not False
        or value.get("canonical_projection_ref") is not None
        or value.get("lifecycle_status") != "private_ready"
    ):
        errors.append("visual_review_nonaccepted_canonical_invalid")
    if (
        value.get("provider_consensus_auto_acceptance") is not False
        or value.get("local_ocr_evidence_used") is not False
        or value.get("seal_status") != "sealed"
    ):
        errors.append("visual_review_authority_boundary_invalid")
    material = copy.deepcopy(value)
    actual_hash = material.pop("receipt_hash", None)
    if not _is_sha256(actual_hash) or _sha256_json(material) != actual_hash:
        errors.append("visual_review_receipt_hash_invalid")
    return sorted(set(errors))


def validate_visual_review_seal(
    value: Any,
    *,
    receipt: dict[str, Any],
    projection: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(value, dict):
        return ["visual_review_seal_invalid"]
    required = {
        "schema_version",
        "contract_version",
        "validator_version",
        "review_receipt_id",
        "review_receipt_hash",
        "input_decision_hash",
        "crop_sha256",
        "canonical_candidate_hash",
        "canonical_projection_ref",
        "canonical_projection_integrity_sha256",
        "lifecycle_status",
        "sealed_at",
        "mutation_policy",
        "seal_hash",
    }
    errors: list[str] = []
    if set(value) != required:
        errors.append("visual_review_seal_fields_invalid")
    lineage = _object(receipt.get("source_lineage"))
    expected = {
        "schema_version": VISUAL_REVIEW_SEAL_SCHEMA_VERSION,
        "contract_version": VISUAL_REVIEW_CONTRACT_VERSION,
        "validator_version": VISUAL_REVIEW_VALIDATOR_VERSION,
        "review_receipt_id": receipt.get("review_receipt_id"),
        "review_receipt_hash": receipt.get("receipt_hash"),
        "input_decision_hash": receipt.get("input_decision_hash"),
        "crop_sha256": lineage.get("crop_sha256"),
        "canonical_candidate_hash": receipt.get("canonical_candidate_hash"),
        "canonical_projection_ref": receipt.get("canonical_projection_ref"),
        "canonical_projection_integrity_sha256": (
            projection_integrity_sha256(projection) if projection is not None else None
        ),
        "lifecycle_status": receipt.get("lifecycle_status"),
        "sealed_at": receipt.get("reviewed_at"),
        "mutation_policy": "any_receipt_accounting_or_projection_mutation_invalidates_seal",
    }
    comparable = copy.deepcopy(value)
    actual_hash = comparable.pop("seal_hash", None)
    if comparable != expected:
        errors.append("visual_review_seal_binding_invalid")
    if not _is_sha256(actual_hash) or _sha256_json(expected) != actual_hash:
        errors.append("visual_review_seal_hash_invalid")
    return sorted(set(errors))


def validate_reviewed_visual_projection(value: Any) -> dict[str, Any]:
    projection = value if isinstance(value, dict) else {}
    projection_id = str(projection.get("table_projection_id") or "")
    errors: list[str] = []
    generic = TableProjectionValidator().validate(projection)
    errors.extend(str(item.get("code") or "") for item in generic["errors"])
    if (
        projection.get("source_format") != "pdf"
        or projection.get("table_origin") != REVIEWED_VISUAL_TABLE_ORIGIN
        or projection.get("canonical_table_scope")
        != REVIEWED_VISUAL_CANONICAL_SCOPE
        or projection.get("canonical_profile_id") is not None
        or projection.get("projection_status") != "ready"
        or projection.get("table_candidate_status") != "canonical_table_accepted"
        or projection.get("reconstruction_quality") not in {"medium", "high"}
        or projection.get("semantic_table_truth_claimed") is not False
        or projection.get("ocr_vlm_used") is not True
        or projection.get("page_rendering_used_for_extraction") is not True
        or projection.get("local_ocr_evidence_used") is not False
        or projection.get("provider_consensus_auto_acceptance") is not False
    ):
        errors.append("reviewed_visual_projection_boundary_invalid")
    review = _object(projection.get("visual_review"))
    if set(review) != {"receipt", "seal", "region_cell_accounting"}:
        errors.append("reviewed_visual_projection_review_envelope_invalid")
    receipt = _object(review.get("receipt"))
    seal = _object(review.get("seal"))
    accounting = _object(review.get("region_cell_accounting"))
    errors.extend(validate_visual_review_receipt(receipt))
    errors.extend(validate_visual_region_accounting(accounting, projection=projection))
    if receipt.get("region_cell_accounting_hash") != _sha256_json(accounting):
        errors.append("reviewed_visual_projection_accounting_hash_mismatch")
    if receipt.get("canonical_projection_ref") != projection_id:
        errors.append("reviewed_visual_projection_receipt_ref_mismatch")
    if receipt.get("canonical_candidate_hash") != _canonical_candidate_hash(
        projection
    ):
        errors.append("reviewed_visual_projection_candidate_hash_mismatch")
    lineage = _object(receipt.get("source_lineage"))
    if (
        projection.get("source_document_ref") != lineage.get("source_ref")
        or projection.get("source_checksum_ref")
        != "sourcechk_" + str(lineage.get("source_sha256") or "")[:24]
        or projection.get("payload_checksum_ref")
        != "cropchk_" + str(lineage.get("crop_sha256") or "")[:24]
        or projection.get("table_ref") != lineage.get("candidate_ref")
    ):
        errors.append("reviewed_visual_projection_source_lineage_mismatch")
    canonical_validation = _object(projection.get("canonical_validation"))
    if canonical_validation != {
        "validator_version": VISUAL_REVIEW_VALIDATOR_VERSION,
        "validator_status": "passed",
        "review_receipt_id": receipt.get("review_receipt_id"),
        "review_receipt_hash": receipt.get("receipt_hash"),
        "review_seal_hash": seal.get("seal_hash"),
        "source_to_table_accounting": "passed",
        "review_authority": "passed",
        "mutation_seal": "passed",
        "provider_consensus_canonical_authority": False,
        "local_ocr_evidence_used": False,
    }:
        errors.append("reviewed_visual_projection_canonical_validation_invalid")
    errors.extend(
        validate_visual_review_seal(seal, receipt=receipt, projection=projection)
    )
    errors = sorted(set(item for item in errors if item))
    return {
        "schema_version": "broker_reports_reviewed_visual_projection_validation_v1",
        "table_projection_id": projection_id,
        "validator_version": VISUAL_REVIEW_VALIDATOR_VERSION,
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors_count": len(errors),
        "reason_codes": errors,
    }


def validate_visual_region_accounting(
    value: Any, *, projection: dict[str, Any]
) -> list[str]:
    if not isinstance(value, dict):
        return ["visual_region_accounting_invalid"]
    required = {
        "schema_version",
        "crop_sha256",
        "coordinate_space",
        "image_width",
        "image_height",
        "cell_bindings",
        "non_table_regions",
        "selected_region_refs",
        "table_owned_region_refs",
        "non_table_region_refs",
        "all_canonical_cells_accounted",
        "source_region_inventory_complete",
    }
    errors: list[str] = []
    if set(value) != required:
        errors.append("visual_region_accounting_fields_invalid")
    review = _object(projection.get("visual_review"))
    receipt = _object(review.get("receipt"))
    lineage = _object(receipt.get("source_lineage"))
    if (
        value.get("schema_version") != VISUAL_REGION_ACCOUNTING_SCHEMA_VERSION
        or value.get("crop_sha256") != lineage.get("crop_sha256")
        or value.get("coordinate_space") != "normalized_0_1_top_left"
        or value.get("image_width") != lineage.get("image_width")
        or value.get("image_height") != lineage.get("image_height")
        or value.get("all_canonical_cells_accounted") is not True
        or value.get("source_region_inventory_complete") is not True
    ):
        errors.append("visual_region_accounting_identity_invalid")
    bindings = _dicts(value.get("cell_bindings"))
    non_table = _dicts(value.get("non_table_regions"))
    all_regions = [*bindings, *non_table]
    refs = [str(item.get("region_ref") or "") for item in all_regions]
    if not refs or len(refs) != len(set(refs)) or any(not item for item in refs):
        errors.append("visual_region_accounting_region_refs_invalid")
    for item in all_regions:
        if not _bbox(item.get("bbox_normalized")):
            errors.append("visual_region_accounting_bbox_invalid")
            break
    cells = _dicts(projection.get("cells"))
    private_values = {
        str(item.get("value_path_ref") or ""): item
        for item in _dicts(projection.get("private_values"))
    }
    cells_by_key = {
        (int(item.get("row_ordinal") or 0) - 1, int(item.get("column_ordinal") or 0) - 1): item
        for item in cells
    }
    bindings_by_key: dict[tuple[int, int], dict[str, Any]] = {}
    for binding in bindings:
        if set(binding) != {
            "region_ref",
            "row_index",
            "column_index",
            "row_span",
            "column_span",
            "bbox_normalized",
            "observed_content_state",
            "observed_text_sha256",
            "review_action",
        }:
            errors.append("visual_region_cell_binding_fields_invalid")
            continue
        key = (binding.get("row_index"), binding.get("column_index"))
        if key in bindings_by_key:
            errors.append("visual_region_cell_binding_duplicate")
        bindings_by_key[key] = binding
        cell = cells_by_key.get(key)
        private = private_values.get(
            str(_object(cell).get("normalized_private_value_path") or "")
        )
        text = str(_object(private).get("normalized_value") or "")
        if (
            not cell
            or binding.get("row_span") != cell.get("row_span")
            or binding.get("column_span") != cell.get("column_span")
            or binding.get("observed_content_state") != cell.get("content_state")
            or binding.get("observed_text_sha256")
            != hashlib.sha256(text.encode("utf-8")).hexdigest()
            or binding.get("region_ref")
            not in _strings(cell.get("source_object_refs"))
            or binding.get("region_ref") != cell.get("bbox_ref")
            or binding.get("review_action") not in {"confirmed", "corrected"}
        ):
            errors.append("visual_region_cell_binding_projection_mismatch")
    if set(bindings_by_key) != set(cells_by_key):
        errors.append("visual_region_cell_binding_coverage_invalid")
    for item in non_table:
        if set(item) != {"region_ref", "bbox_normalized", "reason_code"}:
            errors.append("visual_non_table_region_invalid")
    selected = _strings(value.get("selected_region_refs"))
    table_owned = _strings(value.get("table_owned_region_refs"))
    non_table_refs = _strings(value.get("non_table_region_refs"))
    if (
        selected != refs
        or table_owned != [str(item.get("region_ref") or "") for item in bindings]
        or non_table_refs
        != [str(item.get("region_ref") or "") for item in non_table]
        or Counter([*table_owned, *non_table_refs]) != Counter(selected)
    ):
        errors.append("visual_region_accounting_coverage_invalid")
    coverage = _object(projection.get("coverage"))
    if (
        selected != _strings(coverage.get("selected_source_refs"))
        or table_owned != _strings(coverage.get("table_owned_refs"))
        or non_table_refs != _strings(coverage.get("non_table_refs"))
        or coverage.get("coverage_status") != "complete"
    ):
        errors.append("visual_region_accounting_projection_coverage_mismatch")
    return sorted(set(errors))


def projection_integrity_sha256(projection: dict[str, Any] | None) -> str | None:
    if not isinstance(projection, dict):
        return None
    material = copy.deepcopy(projection)
    material.pop("table_projection_checksum_ref", None)
    review = _object(material.get("visual_review"))
    review.pop("seal", None)
    material["visual_review"] = review
    canonical_validation = _object(material.get("canonical_validation"))
    canonical_validation["review_seal_hash"] = None
    material["canonical_validation"] = canonical_validation
    return _sha256_json(material)


def _canonical_candidate_hash(projection: dict[str, Any]) -> str:
    values = {
        str(item.get("value_path_ref") or ""): str(
            item.get("normalized_value") or ""
        )
        for item in _dicts(projection.get("private_values"))
    }
    cells = []
    for item in _dicts(projection.get("cells")):
        cells.append(
            {
                "row_index": int(item.get("row_ordinal") or 0) - 1,
                "column_index": int(item.get("column_ordinal") or 0) - 1,
                "row_span": int(item.get("row_span") or 0),
                "column_span": int(item.get("column_span") or 0),
                "content_state": item.get("content_state"),
                "source_text": values.get(
                    str(item.get("normalized_private_value_path") or ""), ""
                ),
            }
        )
    cells.sort(key=lambda item: (item["row_index"], item["column_index"]))
    table = {
        "schema_version": "broker_reports_canonical_table_v1",
        "table_id": projection.get("table_ref"),
        "row_count": projection.get("row_count"),
        "column_count": projection.get("column_count"),
        "cells": cells,
    }
    return _sha256_json(table)


def _validate_source_lineage(value: dict[str, Any]) -> list[str]:
    required = {
        "declared_scope",
        "source_ref",
        "source_sha256",
        "page_number",
        "crop_id",
        "candidate_ref",
        "crop_sha256",
        "crop_manifest_hash",
        "declared_table_bbox",
        "rendered_bbox",
        "renderer",
        "renderer_version",
        "dpi",
        "image_width",
        "image_height",
        "whole_document_available",
    }
    errors = []
    if set(value) != required:
        errors.append("visual_review_source_lineage_fields_invalid")
    if (
        value.get("declared_scope") != "one_table_crop"
        or value.get("whole_document_available") is not False
        or not value.get("source_ref")
        or not value.get("crop_id")
        or not value.get("candidate_ref")
        or not _is_sha256(value.get("source_sha256"))
        or not _is_sha256(value.get("crop_sha256"))
        or not _is_sha256(value.get("crop_manifest_hash"))
        or not isinstance(value.get("page_number"), int)
        or isinstance(value.get("page_number"), bool)
        or int(value.get("page_number") or 0) < 1
        or not isinstance(value.get("image_width"), int)
        or not isinstance(value.get("image_height"), int)
        or int(value.get("image_width") or 0) < 1
        or int(value.get("image_height") or 0) < 1
    ):
        errors.append("visual_review_source_lineage_invalid")
    return errors


def _validate_reviewer(value: dict[str, Any]) -> list[str]:
    required = {
        "reviewer_id",
        "reviewer_type",
        "authenticated_user_id",
        "authority_ref",
        "authority_source",
    }
    errors = []
    if set(value) != required:
        errors.append("visual_review_reviewer_fields_invalid")
    if (
        value.get("reviewer_type") not in REVIEWER_TYPES
        or not all(
            isinstance(value.get(field), str) and str(value.get(field)).strip()
            for field in (
                "reviewer_id",
                "authenticated_user_id",
                "authority_ref",
            )
        )
        or value.get("authority_source") != "factory_bound_server_context"
    ):
        errors.append("visual_review_reviewer_authority_invalid")
    if value.get("reviewer_type") == "human_reviewed" and (
        value.get("reviewer_id") != value.get("authenticated_user_id")
        or value.get("authority_ref") != "server_authenticated_user"
    ):
        errors.append("visual_review_human_authority_invalid")
    if value.get("reviewer_type") == "delegated_agent_reviewed" and (
        value.get("reviewer_id") == value.get("authenticated_user_id")
        or value.get("authority_ref") == "server_authenticated_user"
    ):
        errors.append("visual_review_delegated_authority_invalid")
    return errors


def _bbox(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        return False
    x0, y0, x1, y1 = (float(item) for item in value)
    return 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0


def _timezone_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _strings(value: Any) -> list[str]:
    return (
        [str(item) for item in value if item is not None and str(item)]
        if isinstance(value, list)
        else []
    )
