from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_dual_vlm_canonical_table_contracts import (
    canonicalize_table,
    compare_tables,
    sha256_json,
    validate_table_output,
)
from .pdf_dual_vlm_runtime import PROVIDER_ORDER, validate_pdf_dual_vlm_decision
from .visual_table_review_contracts import (
    ACCEPTED_REVIEW_DECISIONS,
    REVIEW_DECISIONS,
    REVIEWED_VISUAL_CANONICAL_SCOPE,
    REVIEWED_VISUAL_TABLE_ORIGIN,
    REVIEWER_TYPES,
    VISUAL_REGION_ACCOUNTING_SCHEMA_VERSION,
    VISUAL_REVIEW_CONTRACT_VERSION,
    VISUAL_REVIEW_RECEIPT_SCHEMA_VERSION,
    VISUAL_REVIEW_SEAL_SCHEMA_VERSION,
    VISUAL_REVIEW_VALIDATOR_VERSION,
    projection_integrity_sha256,
    validate_reviewed_visual_projection,
    validate_visual_review_receipt,
    validate_visual_review_seal,
)


VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION = (
    "broker_reports_visual_table_review_submission_v1"
)
VISUAL_REGION_ACCOUNTING_SUBMISSION_SCHEMA_VERSION = (
    "broker_reports_visual_region_cell_accounting_submission_v1"
)

FACTORY_REQUIRED = (
    "PdfVisualTableReviewFactory.create is the only maintained visual proposal "
    "review, seal and canonical-promotion entrypoint"
)
FORBIDDEN = (
    "Callers must not self-assert review authority, derive source accounting from "
    "provider consensus, use local OCR evidence or mint Gate 2 visual projections"
)


class PdfVisualTableReviewError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VisualReviewAuthorityContext:
    authenticated_user_id: str
    reviewer_id: str
    reviewer_type: str
    authority_ref: str


@dataclass(frozen=True)
class PdfVisualTableReviewResult:
    review_receipt: dict[str, Any]
    review_seal: dict[str, Any]
    canonical_projection: dict[str, Any] | None


class PdfVisualTableReviewFactory:
    def create(
        self, *, authority: VisualReviewAuthorityContext
    ) -> "PdfVisualTableReviewService":
        reviewer = _reviewer(authority)
        return PdfVisualTableReviewService(reviewer=reviewer)


class PdfVisualTableReviewService:
    def __init__(self, *, reviewer: dict[str, Any]) -> None:
        self.reviewer = copy.deepcopy(reviewer)

    def review(
        self, *, decision: dict[str, Any], submission: dict[str, Any]
    ) -> PdfVisualTableReviewResult:
        _validate_input_decision(decision)
        _validate_submission_shape(submission)
        review_decision = str(submission["review_decision"])
        accepted = review_decision in ACCEPTED_REVIEW_DECISIONS
        selected_provider = submission.get("selected_proposal_provider")
        canonical_candidate: dict[str, Any] | None = None
        corrections: list[dict[str, Any]] = []
        accounting: dict[str, Any] | None = None
        canonical_candidate_hash: str | None = None

        if accepted:
            selected = _selected_proposal(decision, selected_provider)
            raw_candidate = submission.get("canonical_candidate")
            table_id = str(_object(decision.get("source_lineage")).get("candidate_ref"))
            validation_errors = validate_table_output(raw_candidate, table_id=table_id)
            if validation_errors:
                raise PdfVisualTableReviewError(validation_errors[0])
            canonical_candidate = canonicalize_table(raw_candidate, table_id=table_id)
            canonical_candidate_hash = sha256_json(canonical_candidate)
            comparison = compare_tables(selected, canonical_candidate)
            corrections = _validated_corrections(
                review_decision=review_decision,
                comparison=comparison,
                acknowledgements=submission.get("correction_acknowledgements"),
            )
            accounting = _build_accounting(
                lineage=_object(decision.get("source_lineage")),
                candidate=canonical_candidate,
                submission=submission.get("region_cell_accounting"),
                review_decision=review_decision,
                differences=_dicts(comparison.get("differences")),
            )
        else:
            if (
                selected_provider is not None
                or submission.get("canonical_candidate") is not None
                or submission.get("correction_acknowledgements") != []
                or submission.get("region_cell_accounting") is not None
            ):
                raise PdfVisualTableReviewError(
                    "visual_review_nonaccepted_canonical_payload_forbidden"
                )

        _validate_attestations(
            submission.get("attestations"), accepted=accepted
        )
        reason_codes = _reason_codes(submission.get("decision_reason_codes"))
        reviewed_at = str(submission.get("reviewed_at") or "")
        if not _timezone_timestamp(reviewed_at):
            raise PdfVisualTableReviewError("visual_review_timestamp_invalid")
        lineage = copy.deepcopy(_object(decision.get("source_lineage")))
        proposal_hashes = {
            provider: (
                sha256_json(_object(decision.get("proposals")).get(provider))
                if isinstance(_object(decision.get("proposals")).get(provider), dict)
                else None
            )
            for provider in PROVIDER_ORDER
        }
        review_receipt_id = "visualreview_" + stable_digest(
            [
                VISUAL_REVIEW_CONTRACT_VERSION,
                decision.get("decision_hash"),
                self.reviewer,
                reviewed_at,
                review_decision,
                canonical_candidate_hash,
            ],
            length=24,
        )
        projection_ref = (
            "visualtableproj_"
            + stable_digest(
                [review_receipt_id, canonical_candidate_hash], length=24
            )
            if accepted
            else None
        )
        accounting_summary = (
            {
                "crop_sha256": accounting["crop_sha256"],
                "coordinate_space": accounting["coordinate_space"],
                "canonical_cells_total": len(accounting["cell_bindings"]),
                "canonical_cells_accounted": len(accounting["cell_bindings"]),
                "non_table_regions_total": len(accounting["non_table_regions"]),
                "all_canonical_cells_accounted": accounting[
                    "all_canonical_cells_accounted"
                ],
                "source_region_inventory_complete": accounting[
                    "source_region_inventory_complete"
                ],
            }
            if accounting is not None
            else {}
        )
        receipt = {
            "schema_version": VISUAL_REVIEW_RECEIPT_SCHEMA_VERSION,
            "contract_version": VISUAL_REVIEW_CONTRACT_VERSION,
            "validator_version": VISUAL_REVIEW_VALIDATOR_VERSION,
            "review_receipt_id": review_receipt_id,
            "input_decision_id": decision.get("decision_id"),
            "input_decision_hash": decision.get("decision_hash"),
            "source_lineage": lineage,
            "source_lineage_hash": sha256_json(lineage),
            "provider_proposal_hashes": proposal_hashes,
            "reviewer": copy.deepcopy(self.reviewer),
            "reviewed_at": reviewed_at,
            "decision": review_decision,
            "decision_reason_codes": reason_codes,
            "selected_proposal_provider": selected_provider if accepted else None,
            "canonical_candidate_hash": canonical_candidate_hash,
            "corrections": corrections,
            "corrections_hash": sha256_json(corrections),
            "region_cell_accounting_hash": (
                sha256_json(accounting) if accounting is not None else None
            ),
            "region_cell_accounting_summary": accounting_summary,
            "attestations": copy.deepcopy(submission["attestations"]),
            "provider_consensus_auto_acceptance": False,
            "local_ocr_evidence_used": False,
            "canonical_promotion_authority": (
                "factory_bound_explicit_review" if accepted else None
            ),
            "canonical_promotion_allowed": accepted,
            "canonical_projection_ref": projection_ref,
            "seal_status": "sealed",
            "lifecycle_status": "private_ready",
        }
        receipt["receipt_hash"] = sha256_json(receipt)
        receipt_errors = validate_visual_review_receipt(receipt)
        if receipt_errors:
            raise PdfVisualTableReviewError(receipt_errors[0])

        projection = (
            _build_projection(
                candidate=canonical_candidate or {},
                accounting=accounting or {},
                receipt=receipt,
                decision=decision,
            )
            if accepted
            else None
        )
        seal = _seal(receipt=receipt, projection=projection)
        if projection is not None:
            projection["visual_review"]["seal"] = copy.deepcopy(seal)
            projection["canonical_validation"]["review_seal_hash"] = seal[
                "seal_hash"
            ]
            projection["table_projection_checksum_ref"] = _checksum_ref(
                "tableprojchk", _projection_checksum_material(projection)
            )
            validation = validate_reviewed_visual_projection(projection)
            if validation["validator_status"] != "passed":
                raise PdfVisualTableReviewError(validation["reason_codes"][0])
        seal_errors = validate_visual_review_seal(
            seal, receipt=receipt, projection=projection
        )
        if seal_errors:
            raise PdfVisualTableReviewError(seal_errors[0])
        return PdfVisualTableReviewResult(
            review_receipt=receipt,
            review_seal=seal,
            canonical_projection=projection,
        )


def _reviewer(authority: VisualReviewAuthorityContext) -> dict[str, Any]:
    values = {
        "authenticated_user_id": str(authority.authenticated_user_id or "").strip(),
        "reviewer_id": str(authority.reviewer_id or "").strip(),
        "reviewer_type": str(authority.reviewer_type or "").strip(),
        "authority_ref": str(authority.authority_ref or "").strip(),
    }
    if (
        values["reviewer_type"] not in REVIEWER_TYPES
        or not values["authenticated_user_id"]
        or not values["reviewer_id"]
        or not values["authority_ref"]
    ):
        raise PdfVisualTableReviewError("visual_review_authority_invalid")
    if values["reviewer_type"] == "human_reviewed" and (
        values["authenticated_user_id"] != values["reviewer_id"]
        or values["authority_ref"] != "server_authenticated_user"
    ):
        raise PdfVisualTableReviewError("visual_review_human_authority_invalid")
    if values["reviewer_type"] == "delegated_agent_reviewed" and (
        values["authenticated_user_id"] == values["reviewer_id"]
        or values["authority_ref"] == "server_authenticated_user"
    ):
        raise PdfVisualTableReviewError("visual_review_delegated_authority_invalid")
    return {
        "reviewer_id": values["reviewer_id"],
        "reviewer_type": values["reviewer_type"],
        "authenticated_user_id": values["authenticated_user_id"],
        "authority_ref": values["authority_ref"],
        "authority_source": "factory_bound_server_context",
    }


def _validate_input_decision(decision: Any) -> None:
    errors = validate_pdf_dual_vlm_decision(decision)
    if errors:
        raise PdfVisualTableReviewError(errors[0])
    lineage = _object(decision.get("source_lineage"))
    if (
        not lineage
        or decision.get("input_hash") != lineage.get("crop_sha256")
        or not _is_sha256(lineage.get("source_sha256"))
        or not _is_sha256(lineage.get("crop_sha256"))
        or lineage.get("whole_document_available") is not False
        or lineage.get("declared_scope") != "one_table_crop"
    ):
        raise PdfVisualTableReviewError("visual_review_input_lineage_invalid")
    proposals = _object(decision.get("proposals"))
    if set(proposals) != set(PROVIDER_ORDER):
        raise PdfVisualTableReviewError("visual_review_provider_proposals_invalid")
    executions = {
        str(item.get("provider") or ""): item
        for item in _dicts(decision.get("executions"))
    }
    for provider in PROVIDER_ORDER:
        proposal = proposals.get(provider)
        if proposal is None:
            continue
        errors = validate_table_output(proposal, table_id=lineage.get("candidate_ref"))
        execution = _object(executions.get(provider))
        if (
            errors
            or execution.get("input_hash") != lineage.get("crop_sha256")
            or _object(execution.get("validator_result")).get(
                "canonical_proposal_hash"
            )
            != sha256_json(canonicalize_table(proposal))
        ):
            raise PdfVisualTableReviewError(
                "visual_review_provider_proposal_lineage_invalid"
            )


def _validate_submission_shape(submission: Any) -> None:
    required = {
        "schema_version",
        "reviewed_at",
        "review_decision",
        "decision_reason_codes",
        "selected_proposal_provider",
        "canonical_candidate",
        "correction_acknowledgements",
        "region_cell_accounting",
        "attestations",
    }
    if not isinstance(submission, dict) or set(submission) != required:
        raise PdfVisualTableReviewError("visual_review_submission_fields_invalid")
    if (
        submission.get("schema_version") != VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION
        or submission.get("review_decision") not in REVIEW_DECISIONS
    ):
        raise PdfVisualTableReviewError("visual_review_submission_invalid")
    if not isinstance(submission.get("correction_acknowledgements"), list):
        raise PdfVisualTableReviewError("visual_review_corrections_invalid")


def _selected_proposal(
    decision: dict[str, Any], selected_provider: Any
) -> dict[str, Any]:
    if selected_provider not in PROVIDER_ORDER:
        raise PdfVisualTableReviewError("visual_review_selected_provider_invalid")
    proposal = _object(decision.get("proposals")).get(selected_provider)
    if not isinstance(proposal, dict):
        raise PdfVisualTableReviewError("visual_review_selected_proposal_unavailable")
    return canonicalize_table(proposal)


def _validated_corrections(
    *,
    review_decision: str,
    comparison: dict[str, Any],
    acknowledgements: Any,
) -> list[dict[str, Any]]:
    differences = _dicts(comparison.get("differences"))
    if review_decision == "accepted_without_correction":
        if comparison.get("FULL_TABLE_CONSENSUS") is not True or acknowledgements != []:
            raise PdfVisualTableReviewError(
                "visual_review_without_correction_candidate_mismatch"
            )
        return []
    if comparison.get("FULL_TABLE_CONSENSUS") is True or not differences:
        raise PdfVisualTableReviewError("visual_review_with_correction_diff_missing")
    acknowledgements = _dicts(acknowledgements)
    if len(acknowledgements) != len(differences):
        raise PdfVisualTableReviewError(
            "visual_review_correction_accounting_incomplete"
        )
    by_hash: dict[str, dict[str, Any]] = {}
    for item in acknowledgements:
        if set(item) != {"difference_sha256", "reviewer_reason_code"}:
            raise PdfVisualTableReviewError("visual_review_correction_invalid")
        difference_hash = str(item.get("difference_sha256") or "")
        reason = str(item.get("reviewer_reason_code") or "")
        if difference_hash in by_hash or not _reason_code(reason):
            raise PdfVisualTableReviewError("visual_review_correction_invalid")
        by_hash[difference_hash] = item
    output = []
    for difference in differences:
        difference_hash = sha256_json(difference)
        acknowledgement = by_hash.get(difference_hash)
        if acknowledgement is None:
            raise PdfVisualTableReviewError(
                "visual_review_correction_accounting_incomplete"
            )
        output.append(
            {
                "difference_sha256": difference_hash,
                "difference_class": difference.get("class"),
                "cell": copy.deepcopy(difference.get("cell")),
                "selected_provider_before_sha256": sha256_json(
                    difference.get("left")
                ),
                "canonical_after_sha256": sha256_json(difference.get("right")),
                "reviewer_reason_code": acknowledgement["reviewer_reason_code"],
            }
        )
    if set(by_hash) != {sha256_json(item) for item in differences}:
        raise PdfVisualTableReviewError("visual_review_correction_unknown_diff")
    return output


def _build_accounting(
    *,
    lineage: dict[str, Any],
    candidate: dict[str, Any],
    submission: Any,
    review_decision: str,
    differences: list[dict[str, Any]],
) -> dict[str, Any]:
    required = {
        "schema_version",
        "crop_sha256",
        "coordinate_space",
        "image_width",
        "image_height",
        "cell_bindings",
        "non_table_regions",
        "all_canonical_cells_accounted",
        "source_region_inventory_complete",
    }
    if not isinstance(submission, dict) or set(submission) != required:
        raise PdfVisualTableReviewError("visual_region_accounting_fields_invalid")
    if (
        submission.get("schema_version")
        != VISUAL_REGION_ACCOUNTING_SUBMISSION_SCHEMA_VERSION
        or submission.get("crop_sha256") != lineage.get("crop_sha256")
        or submission.get("coordinate_space") != "normalized_0_1_top_left"
        or submission.get("image_width") != lineage.get("image_width")
        or submission.get("image_height") != lineage.get("image_height")
        or submission.get("all_canonical_cells_accounted") is not True
        or submission.get("source_region_inventory_complete") is not True
    ):
        raise PdfVisualTableReviewError("visual_region_accounting_identity_invalid")
    candidate_cells = {
        (int(item["row_index"]), int(item["column_index"])): item
        for item in candidate["cells"]
    }
    submitted_bindings = _dicts(submission.get("cell_bindings"))
    if len(submitted_bindings) != len(candidate_cells):
        raise PdfVisualTableReviewError("visual_region_cell_coverage_invalid")
    changed_cells = {
        tuple(item["cell"])
        for item in differences
        if isinstance(item.get("cell"), list) and len(item["cell"]) == 2
    }
    bindings_by_key: dict[tuple[int, int], dict[str, Any]] = {}
    for item in submitted_bindings:
        if set(item) != {
            "row_index",
            "column_index",
            "bbox_normalized",
            "observed_content_state",
            "observed_text_sha256",
            "review_action",
        }:
            raise PdfVisualTableReviewError("visual_region_cell_binding_invalid")
        key = (item.get("row_index"), item.get("column_index"))
        cell = candidate_cells.get(key)
        if key in bindings_by_key or cell is None or not _bbox(item.get("bbox_normalized")):
            raise PdfVisualTableReviewError("visual_region_cell_binding_invalid")
        text = str(cell.get("source_text") or "")
        action = item.get("review_action")
        if (
            item.get("observed_content_state") != cell.get("content_state")
            or item.get("observed_text_sha256")
            != hashlib.sha256(text.encode("utf-8")).hexdigest()
            or action not in {"confirmed", "corrected"}
            or (
                review_decision == "accepted_without_correction"
                and action != "confirmed"
            )
            or (
                review_decision == "accepted_with_correction"
                and key in changed_cells
                and action != "corrected"
            )
        ):
            raise PdfVisualTableReviewError(
                "visual_region_cell_observation_invalid"
            )
        bindings_by_key[key] = item
    if set(bindings_by_key) != set(candidate_cells):
        raise PdfVisualTableReviewError("visual_region_cell_coverage_invalid")

    output_bindings = []
    for key, cell in candidate_cells.items():
        item = bindings_by_key[key]
        region_ref = "visualregion_" + stable_digest(
            [lineage["crop_sha256"], key, item["bbox_normalized"]], length=24
        )
        output_bindings.append(
            {
                "region_ref": region_ref,
                "row_index": key[0],
                "column_index": key[1],
                "row_span": cell["row_span"],
                "column_span": cell["column_span"],
                "bbox_normalized": copy.deepcopy(item["bbox_normalized"]),
                "observed_content_state": item["observed_content_state"],
                "observed_text_sha256": item["observed_text_sha256"],
                "review_action": item["review_action"],
            }
        )
    output_non_table = []
    for ordinal, item in enumerate(_dicts(submission.get("non_table_regions"))):
        if set(item) != {"bbox_normalized", "reason_code"} or not _bbox(
            item.get("bbox_normalized")
        ) or not _reason_code(str(item.get("reason_code") or "")):
            raise PdfVisualTableReviewError("visual_non_table_region_invalid")
        output_non_table.append(
            {
                "region_ref": "visualregion_"
                + stable_digest(
                    [
                        lineage["crop_sha256"],
                        "non_table",
                        ordinal,
                        item["bbox_normalized"],
                    ],
                    length=24,
                ),
                "bbox_normalized": copy.deepcopy(item["bbox_normalized"]),
                "reason_code": item["reason_code"],
            }
        )
    table_refs = [item["region_ref"] for item in output_bindings]
    non_table_refs = [item["region_ref"] for item in output_non_table]
    return {
        "schema_version": VISUAL_REGION_ACCOUNTING_SCHEMA_VERSION,
        "crop_sha256": lineage["crop_sha256"],
        "coordinate_space": "normalized_0_1_top_left",
        "image_width": lineage["image_width"],
        "image_height": lineage["image_height"],
        "cell_bindings": output_bindings,
        "non_table_regions": output_non_table,
        "selected_region_refs": [*table_refs, *non_table_refs],
        "table_owned_region_refs": table_refs,
        "non_table_region_refs": non_table_refs,
        "all_canonical_cells_accounted": True,
        "source_region_inventory_complete": True,
    }


def _build_projection(
    *,
    candidate: dict[str, Any],
    accounting: dict[str, Any],
    receipt: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    lineage = _object(decision.get("source_lineage"))
    projection_id = str(receipt["canonical_projection_ref"])
    canonical_table_id = "canonicalvisualtable_" + stable_digest(
        [receipt["canonical_candidate_hash"], receipt["receipt_hash"]], length=24
    )
    logical_table_id = "logicalvisualtable_" + stable_digest(
        [lineage["source_sha256"], lineage["page_number"], lineage["candidate_ref"]],
        length=24,
    )
    row_refs = [
        "visualrow_" + stable_digest([projection_id, row], length=24)
        for row in range(candidate["row_count"])
    ]
    column_refs = [
        "visualcol_" + stable_digest([projection_id, column], length=24)
        for column in range(candidate["column_count"])
    ]
    binding_by_key = {
        (item["row_index"], item["column_index"]): item
        for item in accounting["cell_bindings"]
    }
    cells: list[dict[str, Any]] = []
    private_values: list[dict[str, Any]] = []
    source_value_index: list[dict[str, Any]] = []
    for cell in candidate["cells"]:
        key = (cell["row_index"], cell["column_index"])
        binding = binding_by_key[key]
        region_ref = binding["region_ref"]
        source_value_ref = "visualsrcval_" + stable_digest(
            [projection_id, region_ref], length=24
        )
        value_path_ref = "visualvaluepath_" + stable_digest(
            [projection_id, region_ref, source_value_ref], length=24
        )
        value_checksum = _checksum_ref("valuechk", cell["source_text"])
        cell_ref = "visualcell_" + stable_digest(
            [projection_id, key, cell["row_span"], cell["column_span"]], length=24
        )
        private_values.append(
            {
                "value_path_ref": value_path_ref,
                "normalized_value": cell["source_text"],
                "value_checksum_ref": value_checksum,
                "source_value_refs": [source_value_ref],
                "source_object_ref": region_ref,
            }
        )
        source_value_index.append(
            {
                "source_value_ref": source_value_ref,
                "source_object_ref": region_ref,
                "cell_ref": cell_ref,
                "value_path": {
                    "kind": "table_projection_private_value",
                    "value_path_ref": value_path_ref,
                },
                "value_checksum_ref": value_checksum,
            }
        )
        cells.append(
            {
                "cell_ref": cell_ref,
                "row_ref": row_refs[cell["row_index"]],
                "column_ref": column_refs[cell["column_index"]],
                "row_ordinal": cell["row_index"] + 1,
                "column_ordinal": cell["column_index"] + 1,
                "source_value_refs": [source_value_ref],
                "source_object_refs": [region_ref],
                "cell_value_ref": "visualcellval_"
                + stable_digest([cell_ref, value_checksum], length=24),
                "normalized_private_value_path": value_path_ref,
                "value_checksum_ref": value_checksum,
                "value_kind_hints": _value_kind_hints(cell),
                "bbox_ref": region_ref,
                "content_state": cell["content_state"],
                "row_span": cell["row_span"],
                "column_span": cell["column_span"],
                "covered_column_refs": column_refs[
                    cell["column_index"] : cell["column_index"]
                    + cell["column_span"]
                ],
                "merged_cell_group_ref": (
                    "visualmerged_"
                    + stable_digest([projection_id, key], length=20)
                    if cell["row_span"] > 1 or cell["column_span"] > 1
                    else None
                ),
                "split_cell_candidate": False,
                "multi_line_cell": "\n" in cell["source_text"],
                "wrapped_text_cell": False,
                "ambiguous_cell_boundary": False,
                "empty_cell": cell["content_state"] == "empty",
                "confidence": "explicit_review",
                "reason_codes": ["visual_cell_source_region_explicitly_reviewed"],
            }
        )
    cells_by_row: dict[str, list[str]] = {row_ref: [] for row_ref in row_refs}
    for cell in cells:
        cells_by_row[str(cell["row_ref"])].append(str(cell["cell_ref"]))
    rows = [
        {
            "row_ref": row_ref,
            "row_ordinal": ordinal + 1,
            "cell_refs": cells_by_row[row_ref],
            "row_role": "unknown_row_role",
            "row_checksum_ref": _checksum_ref("rowchk", cells_by_row[row_ref]),
            "reason_codes": ["visual_review_preserves_grid_without_semantic_role"],
        }
        for ordinal, row_ref in enumerate(row_refs)
    ]
    source_value_refs = [item["source_value_ref"] for item in source_value_index]
    selected = list(accounting["selected_region_refs"])
    table_owned = list(accounting["table_owned_region_refs"])
    non_table = list(accounting["non_table_region_refs"])
    coverage_ref = "tablecoverage_" + stable_digest(
        [projection_id, selected, table_owned, non_table], length=24
    )
    review_envelope = {
        "receipt": copy.deepcopy(receipt),
        "seal": None,
        "region_cell_accounting": copy.deepcopy(accounting),
    }
    projection = {
        "schema_version": "broker_reports_normalized_table_projection_v0",
        "table_projection_id": projection_id,
        "table_ref": candidate["table_id"],
        "canonical_table_id": canonical_table_id,
        "logical_table_id": logical_table_id,
        "canonical_profile_id": None,
        "canonical_table_scope": REVIEWED_VISUAL_CANONICAL_SCOPE,
        "canonical_contract": {
            "contract_version": VISUAL_REVIEW_CONTRACT_VERSION,
            "continuation": {},
        },
        "source_format": "pdf",
        "table_origin": REVIEWED_VISUAL_TABLE_ORIGIN,
        "source_document_ref": lineage["source_ref"],
        "source_unit_ref": lineage["crop_id"],
        "parent_payload_ref": None,
        "normalization_run_id": "visualreviewrun_"
        + stable_digest([receipt["review_receipt_id"]], length=24),
        "parser_ref": "pdf_dual_vlm_runtime_policy_v1",
        "parser_engine": "dual_provider_visual_proposal_explicit_review",
        "parser_engine_version": VISUAL_REVIEW_CONTRACT_VERSION,
        "parser_config_ref": decision.get("policy_version"),
        "source_checksum_ref": "sourcechk_" + lineage["source_sha256"][:24],
        "payload_checksum_ref": "cropchk_" + lineage["crop_sha256"][:24],
        "source_unit_checksum_ref": "decisionchk_"
        + str(decision["decision_hash"])[:24],
        "table_projection_checksum_ref": None,
        "visibility": "private_case",
        "storage_backend": "project_artifact_payload",
        "projection_status": "ready",
        "row_refs": row_refs,
        "column_refs": column_refs,
        "cell_refs": [item["cell_ref"] for item in cells],
        "cell_value_refs": [item["cell_value_ref"] for item in cells],
        "source_value_refs": source_value_refs,
        "row_count": len(rows),
        "column_count": len(column_refs),
        "cell_count": len(cells),
        "row_order_policy": "reviewed_visual_grid_order_preserved",
        "column_order_policy": "reviewed_visual_grid_order_preserved",
        "table_bbox_ref": copy.deepcopy(lineage.get("declared_table_bbox")),
        "page_refs": [
            "visualpage_"
            + stable_digest(
                [lineage["source_sha256"], lineage["page_number"]], length=24
            )
        ],
        "sheet_refs": [],
        "section_refs": [],
        "rows": rows,
        "cells": cells,
        "private_values": private_values,
        "source_value_index": source_value_index,
        "header_model": {
            "header_row_refs": [],
            "repeated_header_row_refs": [],
            "multi_row_header": False,
            "column_labels": [
                {
                    "header_ref": "visualheader_"
                    + stable_digest([projection_id, column_ref], length=20),
                    "column_ref": column_ref,
                    "cell_ref": None,
                    "source_value_refs": [],
                    "normalized_label": "unknown",
                    "header_confidence": "not_claimed",
                    "mapping_status": "structural_column_only",
                }
                for column_ref in column_refs
            ],
            "header_to_column_mapping_status": "semantic_mapping_not_claimed",
            "pdf_header_candidate": True,
            "semantic_header_truth_claimed": False,
        },
        "coverage": {
            "schema_version": "broker_reports_table_projection_coverage_v0",
            "coverage_ref": coverage_ref,
            "selected_source_refs": selected,
            "accounted_source_refs": [*table_owned, *non_table],
            "table_owned_refs": table_owned,
            "fallback_text_refs": [],
            "non_table_refs": non_table,
            "rejected_refs": [],
            "duplicate_accounted_refs": [],
            "unaccounted_refs": [],
            "coverage_status": "complete",
            "all_selected_refs_accounted": True,
        },
        "quality": {
            "schema_version": "broker_reports_table_reconstruction_quality_v0",
            "row_alignment_score": 1.0,
            "column_alignment_score": 1.0,
            "header_confidence": "not_claimed",
            "cell_boundary_confidence": 1.0,
            "coverage_completeness": 1.0,
            "duplicate_overlap_count": 0,
            "unaccounted_ref_count": 0,
            "fallback_required": False,
            "reconstruction_quality": "medium",
            "quality_authority": "explicit_source_review_not_provider_confidence",
        },
        "table_candidate_status": "canonical_table_accepted",
        "reconstruction_strategy": "dual_vlm_proposal_explicit_visual_review",
        "reconstruction_reason_codes": [
            "source_bound_review_receipt_sealed",
            "visual_region_cell_accounting_complete",
        ],
        "reconstruction_quality": "medium",
        "semantic_table_truth_claimed": False,
        "source_facts_extracted": False,
        "tax_meaning_inferred": False,
        "knowledge_rag_used": False,
        "vectorization_performed": False,
        "ocr_vlm_used": True,
        "page_rendering_used_for_extraction": True,
        "local_ocr_evidence_used": False,
        "provider_consensus_auto_acceptance": False,
        "visual_review": review_envelope,
        "canonical_validation": {
            "validator_version": VISUAL_REVIEW_VALIDATOR_VERSION,
            "validator_status": "passed",
            "review_receipt_id": receipt["review_receipt_id"],
            "review_receipt_hash": receipt["receipt_hash"],
            "review_seal_hash": None,
            "source_to_table_accounting": "passed",
            "review_authority": "passed",
            "mutation_seal": "passed",
            "provider_consensus_canonical_authority": False,
            "local_ocr_evidence_used": False,
        },
    }
    return projection


def _seal(
    *, receipt: dict[str, Any], projection: dict[str, Any] | None
) -> dict[str, Any]:
    lineage = _object(receipt.get("source_lineage"))
    seal = {
        "schema_version": VISUAL_REVIEW_SEAL_SCHEMA_VERSION,
        "contract_version": VISUAL_REVIEW_CONTRACT_VERSION,
        "validator_version": VISUAL_REVIEW_VALIDATOR_VERSION,
        "review_receipt_id": receipt["review_receipt_id"],
        "review_receipt_hash": receipt["receipt_hash"],
        "input_decision_hash": receipt["input_decision_hash"],
        "crop_sha256": lineage["crop_sha256"],
        "canonical_candidate_hash": receipt["canonical_candidate_hash"],
        "canonical_projection_ref": receipt["canonical_projection_ref"],
        "canonical_projection_integrity_sha256": projection_integrity_sha256(
            projection
        ),
        "lifecycle_status": receipt["lifecycle_status"],
        "sealed_at": receipt["reviewed_at"],
        "mutation_policy": "any_receipt_accounting_or_projection_mutation_invalidates_seal",
    }
    seal["seal_hash"] = sha256_json(seal)
    return seal


def _validate_attestations(value: Any, *, accepted: bool) -> None:
    required = {
        "exact_bounded_crop_reviewed",
        "every_canonical_cell_reviewed",
        "source_regions_accounted",
        "provider_output_not_reference_truth",
        "provider_consensus_not_acceptance_authority",
        "local_ocr_evidence_used",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise PdfVisualTableReviewError("visual_review_attestations_invalid")
    if (
        value.get("exact_bounded_crop_reviewed") is not True
        or value.get("provider_output_not_reference_truth") is not True
        or value.get("provider_consensus_not_acceptance_authority") is not True
        or value.get("local_ocr_evidence_used") is not False
        or (
            accepted
            and (
                value.get("every_canonical_cell_reviewed") is not True
                or value.get("source_regions_accounted") is not True
            )
        )
    ):
        raise PdfVisualTableReviewError("visual_review_attestations_fail_closed")


def _reason_codes(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise PdfVisualTableReviewError("visual_review_decision_reasons_invalid")
    reasons = sorted(set(str(item or "") for item in value))
    if any(not _reason_code(item) for item in reasons):
        raise PdfVisualTableReviewError("visual_review_decision_reasons_invalid")
    return reasons


def _reason_code(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{2,95}", value))


def _value_kind_hints(cell: dict[str, Any]) -> list[str]:
    if cell.get("content_state") == "empty":
        return ["blank"]
    if cell.get("content_state") == "unreadable":
        return ["unreadable"]
    return ["untyped_visible_text"]


def _projection_checksum_material(projection: dict[str, Any]) -> dict[str, Any]:
    material = copy.deepcopy(projection)
    material.pop("table_projection_checksum_ref", None)
    material.pop("validator_status", None)
    material.pop("validator_reason_codes", None)
    return material


def _checksum_ref(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical_bytes(value)).hexdigest()[:24]}"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _bbox(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        return False
    x0, y0, x1, y1 = (float(item) for item in value)
    return 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0


def _timezone_timestamp(value: str) -> bool:
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


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
