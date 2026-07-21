from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .gate1_public_contracts import (
    REVIEWED_VISUAL_TABLE_ORIGIN,
    TableProjectionValidator,
    validate_reviewed_visual_projection,
)
from .gate2_source_fact_contracts import PACKAGE_SCHEMA_VERSION


FACTORY_REQUIRED = (
    "Gate2TablePackageFactory.create is the only production normalized-table "
    "Gate 2 package entrypoint"
)
FORBIDDEN = (
    "Gate 1 table projection code must not build or validate Gate 2 semantic packages"
)


@dataclass(frozen=True)
class Gate2TablePackageConfig:
    max_rows_per_package: int = 250


class Gate2TablePackageFactory:
    def __init__(self, config: Gate2TablePackageConfig | None = None) -> None:
        self.config = config or Gate2TablePackageConfig()

    def create(self) -> "Gate2TablePackageBuilder":
        if self.config.max_rows_per_package <= 0:
            raise ValueError("gate2_table_package_row_budget_invalid")
        return Gate2TablePackageBuilder(self.config)


class Gate2TablePackageBuilder:
    def __init__(self, config: Gate2TablePackageConfig) -> None:
        self.config = config
        self.validator = TableProjectionValidator()

    def build(
        self,
        *,
        projection: dict[str, Any],
        case_id: str | None,
        issue_refs: list[str] | None = None,
        table_projection_artifact_ref: str | None = None,
    ) -> dict[str, Any]:
        validation = self.validator.validate(projection)
        if validation["validator_status"] != "passed":
            raise ValueError("gate2_table_projection_invalid")
        if projection.get("projection_status") != "ready":
            raise ValueError("gate2_table_projection_not_ready")
        if str(projection.get("reconstruction_quality") or "") not in {
            "high",
            "medium",
        }:
            raise ValueError("gate2_table_projection_quality_not_eligible")
        if projection.get("source_format") == "pdf" and (
            projection.get("canonical_table_scope")
            != "ready_validated_projection_only"
            or _object(projection.get("canonical_validation")).get(
                "validator_status"
            )
            != "passed"
        ):
            raise ValueError("gate2_pdf_canonical_table_not_validated")
        reviewed_visual = (
            projection.get("source_format") == "pdf"
            and projection.get("table_origin") == REVIEWED_VISUAL_TABLE_ORIGIN
        )
        if projection.get("source_format") == "pdf":
            if reviewed_visual:
                visual_validation = validate_reviewed_visual_projection(projection)
                if visual_validation["validator_status"] != "passed":
                    raise ValueError("gate2_reviewed_visual_projection_invalid")
            elif not projection.get("canonical_profile_id"):
                raise ValueError("gate2_pdf_canonical_boundary_unsupported")
        coverage = _object(projection.get("coverage"))
        if (
            coverage.get("coverage_status") != "complete"
            or _strings(coverage.get("duplicate_accounted_refs"))
            or _strings(coverage.get("unaccounted_refs"))
        ):
            raise ValueError("gate2_table_projection_coverage_not_eligible")
        rows = _dicts(projection.get("rows"))
        if len(rows) > self.config.max_rows_per_package:
            raise ValueError("gate2_table_package_row_budget_exceeded")
        values_by_path = {
            str(item.get("value_path_ref") or ""): str(
                item.get("normalized_value") or ""
            )
            for item in _dicts(projection.get("private_values"))
        }
        cells_by_ref = {
            str(item.get("cell_ref") or ""): item
            for item in _dicts(projection.get("cells"))
        }
        headers = _object(projection.get("header_model"))
        labels_by_column = {
            str(item.get("column_ref") or ""): str(
                item.get("normalized_label") or "unknown"
            )
            for item in _dicts(headers.get("column_labels"))
        }
        model_rows = []
        for row in rows:
            model_cells = []
            for cell_ref in _strings(row.get("cell_refs")):
                cell = cells_by_ref[cell_ref]
                model_cells.append(
                    {
                        "cell_ref": cell_ref,
                        "column_ref": cell.get("column_ref"),
                        "header_label": labels_by_column.get(
                            str(cell.get("column_ref") or ""), "unknown"
                        ),
                        "source_value_ref": next(
                            iter(_strings(cell.get("source_value_refs"))), None
                        ),
                        "source_value_refs": _strings(cell.get("source_value_refs")),
                        "value": values_by_path.get(
                            str(cell.get("normalized_private_value_path") or ""),
                            "",
                        ),
                        "value_kind_hints": _strings(cell.get("value_kind_hints")),
                    }
                )
            model_rows.append(
                {
                    "row_ref": row.get("row_ref"),
                    "row_role": row.get("row_role"),
                    "cells": model_cells,
                }
            )
        selected_refs = [str(item.get("row_ref") or "") for item in rows]
        no_fact = [
            {
                "source_ref": item.get("row_ref"),
                "reason_code": (
                    "repeated_header"
                    if item.get("row_role") == "repeated_header_row"
                    else item.get("row_role")
                ),
            }
            for item in rows
            if item.get("row_role")
            in {"header_row", "repeated_header_row", "blank_row", "layout_row"}
        ]
        no_fact_refs = {str(item["source_ref"]) for item in no_fact}
        fact_candidate_refs = [ref for ref in selected_refs if ref not in no_fact_refs]
        package_id = "tablepkg_" + stable_digest(
            [
                projection.get("table_projection_id"),
                selected_refs,
                issue_refs or [],
                self.config.max_rows_per_package,
            ],
            length=24,
        )
        source_unit = {
            "unit_id": "tableunit_"
            + stable_digest(
                [package_id, projection.get("table_projection_id")], length=24
            ),
            "unit_kind": "table_row_window",
            "slice_ref": projection.get("table_projection_id"),
            "table_projection_id": projection.get("table_projection_id"),
            "canonical_table_id": projection.get("canonical_table_id"),
            "logical_table_id": projection.get("logical_table_id"),
            "canonical_profile_id": projection.get("canonical_profile_id"),
            "canonical_table_scope": projection.get("canonical_table_scope"),
            "continuation": copy.deepcopy(
                _object(projection.get("canonical_contract")).get("continuation")
                or {}
            ),
            "table_projection_artifact_ref": table_projection_artifact_ref,
            "private_slice_artifact_ref": table_projection_artifact_ref,
            "table_ref": projection.get("table_ref"),
            "source_format": projection.get("source_format"),
            "source_input_mode": "normalized_table_projection",
            "parser_ref": projection.get("parser_ref"),
            "source_checksum_ref": projection.get("source_checksum_ref"),
            "slice_payload_checksum_ref": projection.get(
                "table_projection_checksum_ref"
            ),
            "source_unit_checksum_ref": projection.get("source_unit_checksum_ref"),
            "coverage_ref": _object(projection.get("coverage")).get("coverage_ref"),
            "source_slice_truncated": False,
            "parent_source_slice_truncated": False,
            "parent_remainder_status": "not_applicable_parent_complete",
            "normalized_header_descriptors": copy.deepcopy(
                headers.get("column_labels") or []
            ),
            "row_refs": selected_refs,
            "row_provenance": copy.deepcopy(rows),
            "cell_refs": _strings(projection.get("cell_refs")),
            "cell_value_refs": _strings(projection.get("cell_value_refs")),
            "cell_provenance": copy.deepcopy(projection.get("cells") or []),
            "source_value_refs": _strings(projection.get("source_value_refs")),
            "source_value_index": copy.deepcopy(
                projection.get("source_value_index") or []
            ),
            "private_values": copy.deepcopy(projection.get("private_values") or []),
            "normalized_source_projection": {
                "cells": [
                    [cell.get("value") for cell in row.get("cells") or []]
                    for row in model_rows
                ]
            },
            "model_source_projection": {
                "schema_version": "gate2_model_source_projection_v0",
                "rows": model_rows,
            },
            "table_quality": copy.deepcopy(projection.get("quality") or {}),
            "table_candidate_status": projection.get("table_candidate_status"),
            "table_fallback_metadata": copy.deepcopy(projection.get("geometry") or {}),
            "semantic_table_truth_claimed": False,
            "upstream_source_representation": (
                _reviewed_visual_handoff(projection) if reviewed_visual else None
            ),
        }
        package = {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "package_mode": "gate2_normalized_table_projection_no_model_call",
            "package_id": package_id,
            "extraction_run_id": "tableextractrun_"
            + stable_digest([package_id, "no_model"], length=24),
            "normalization_run_id": projection.get("normalization_run_id"),
            "case_id": case_id,
            "document_ref": projection.get("source_document_ref"),
            "source_unit": source_unit,
            "allowed_evidence_refs": sorted(
                {
                    projection.get("table_projection_id"),
                    projection.get("table_ref"),
                    *selected_refs,
                    *_strings(projection.get("cell_refs")),
                    *_strings(projection.get("source_value_refs")),
                    *_strings(
                        _object(projection.get("coverage")).get(
                            "fallback_text_refs"
                        )
                    ),
                }
                - {None, ""}
            ),
            "allowed_source_value_refs": _strings(
                projection.get("source_value_refs")
            ),
            "issue_context": [
                {"issue_ref": ref, "scope": "table_projection"}
                for ref in sorted(set(issue_refs or []))
            ],
            "allowed_issue_refs": sorted(set(issue_refs or [])),
            "coverage_expectation": {
                "coverage_ref": _object(projection.get("coverage")).get(
                    "coverage_ref"
                ),
                "selected_source_refs": selected_refs,
                "ignorable_header_refs": [
                    str(item["source_ref"])
                    for item in no_fact
                    if item["reason_code"] in {"header_row", "repeated_header"}
                ],
                "ignorable_blank_refs": [
                    str(item["source_ref"])
                    for item in no_fact
                    if item["reason_code"] == "blank_row"
                ],
                "layout_candidate_refs": [
                    str(item["source_ref"])
                    for item in no_fact
                    if item["reason_code"] == "layout_row"
                ],
                "mandatory_no_fact_results": no_fact,
                "fact_candidate_refs": fact_candidate_refs,
                "required_accounting_total": len(selected_refs),
                "coverage_policy_id": "gate2_normalized_table_projection_coverage_v0",
            },
            "prompt_contract": {
                "model_call_performed": False,
                "model_must_classify_rows_not_reconstruct_table": True,
                "whole_pdf_or_page_included": False,
                "source_facts_persisted": False,
            },
            "expansion_readiness": {
                "limited_primary_expansion_ready": True,
                "reason": "complete_bounded_table_projection",
            },
            "privacy_policy": {
                "raw_filenames_in_package": False,
                "raw_file_ids_in_package": False,
                "private_paths_in_package": False,
                "chat_text_in_package": False,
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "ocr_vlm_used": False,
                "page_rendering_used_for_extraction": False,
            },
            "privacy_policy_scope": "gate2_package_construction_only",
            "upstream_source_representation": (
                _reviewed_visual_handoff(projection) if reviewed_visual else None
            ),
        }
        validate_gate2_table_package(package, projection)
        return package


def validate_gate2_table_package(
    package: dict[str, Any], projection: dict[str, Any]
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    package_id = str(package.get("package_id") or "")
    source_unit = _object(package.get("source_unit"))
    coverage = _object(package.get("coverage_expectation"))
    projection_coverage = _object(projection.get("coverage"))
    selected = _strings(coverage.get("selected_source_refs"))
    no_fact_refs = {
        str(item.get("source_ref") or "")
        for item in _dicts(coverage.get("mandatory_no_fact_results"))
    }
    fact_refs = set(_strings(coverage.get("fact_candidate_refs")))
    if str(projection.get("reconstruction_quality") or "") not in {
        "high",
        "medium",
    }:
        errors.append(_error("gate2_table_projection_quality_not_eligible", package_id))
    if projection.get("source_format") == "pdf" and (
        projection.get("canonical_table_scope")
        != "ready_validated_projection_only"
        or _object(projection.get("canonical_validation")).get(
            "validator_status"
        )
        != "passed"
    ):
        errors.append(_error("gate2_pdf_canonical_table_not_validated", package_id))
    reviewed_visual = (
        projection.get("source_format") == "pdf"
        and projection.get("table_origin") == REVIEWED_VISUAL_TABLE_ORIGIN
    )
    if projection.get("source_format") == "pdf":
        if reviewed_visual:
            visual_validation = validate_reviewed_visual_projection(projection)
            if visual_validation["validator_status"] != "passed":
                errors.append(
                    _error("gate2_reviewed_visual_projection_invalid", package_id)
                )
        elif not projection.get("canonical_profile_id"):
            errors.append(
                _error("gate2_pdf_canonical_boundary_unsupported", package_id)
            )
    if (
        projection_coverage.get("coverage_status") != "complete"
        or _strings(projection_coverage.get("duplicate_accounted_refs"))
        or _strings(projection_coverage.get("unaccounted_refs"))
    ):
        errors.append(_error("gate2_table_projection_coverage_not_eligible", package_id))
    if package.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        errors.append(_error("gate2_table_package_schema_mismatch", package_id))
    if source_unit.get("table_projection_id") != projection.get(
        "table_projection_id"
    ):
        errors.append(_error("gate2_table_projection_ref_mismatch", package_id))
    if source_unit.get("unit_kind") != "table_row_window":
        errors.append(_error("gate2_table_unit_kind_invalid", package_id))
    if source_unit.get("semantic_table_truth_claimed") is not False:
        errors.append(_error("gate2_table_semantic_truth_forbidden", package_id))
    if selected != _strings(source_unit.get("row_refs")):
        errors.append(_error("gate2_table_row_refs_mismatch", package_id))
    if no_fact_refs | fact_refs != set(selected) or no_fact_refs & fact_refs:
        errors.append(_error("gate2_table_package_coverage_mismatch", package_id))
    if int(coverage.get("required_accounting_total") or 0) != len(selected):
        errors.append(_error("gate2_table_package_coverage_count_mismatch", package_id))
    if set(_strings(package.get("allowed_source_value_refs"))) != set(
        _strings(projection.get("source_value_refs"))
    ):
        errors.append(_error("gate2_table_source_value_refs_mismatch", package_id))
    if _strings(package.get("allowed_issue_refs")) != sorted(
        str(item.get("issue_ref") or "")
        for item in _dicts(package.get("issue_context"))
    ):
        errors.append(_error("gate2_table_issue_refs_mismatch", package_id))
    prompt = _object(package.get("prompt_contract"))
    if prompt.get("model_call_performed") is not False:
        errors.append(_error("gate2_table_model_call_forbidden", package_id))
    if prompt.get("source_facts_persisted") is not False:
        errors.append(_error("gate2_table_source_fact_persistence_forbidden", package_id))
    privacy = _object(package.get("privacy_policy"))
    if any(value is not False for value in privacy.values()):
        errors.append(_error("gate2_table_privacy_guard_failed", package_id))
    if package.get("privacy_policy_scope") != "gate2_package_construction_only":
        errors.append(_error("gate2_table_privacy_scope_invalid", package_id))
    expected_upstream = _reviewed_visual_handoff(projection) if reviewed_visual else None
    if (
        package.get("upstream_source_representation") != expected_upstream
        or source_unit.get("upstream_source_representation") != expected_upstream
    ):
        errors.append(_error("gate2_table_upstream_provenance_mismatch", package_id))
    result = {
        "schema_version": "broker_reports_gate2_table_package_validation_v0",
        "package_id": package_id,
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors_count": len(errors),
        "errors": errors,
    }
    if errors:
        raise ValueError(errors[0]["code"])
    return result


def _reviewed_visual_handoff(projection: dict[str, Any]) -> dict[str, Any]:
    review = _object(projection.get("visual_review"))
    receipt = _object(review.get("receipt"))
    seal = _object(review.get("seal"))
    return {
        "source_representation_kind": "reviewed_visual_canonical_table",
        "review_receipt_id": receipt.get("review_receipt_id"),
        "review_receipt_hash": receipt.get("receipt_hash"),
        "review_seal_hash": seal.get("seal_hash"),
        "review_decision": receipt.get("decision"),
        "reviewer_type": _object(receipt.get("reviewer")).get("reviewer_type"),
        "source_to_table_accounting": "passed",
        "upstream_visual_vlm_used": True,
        "upstream_page_rendering_used": True,
        "local_ocr_evidence_used": False,
        "provider_consensus_canonical_authority": False,
    }


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value or [] if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _strings(value: Any) -> list[str]:
    return (
        [str(item) for item in value or [] if item is not None and str(item)]
        if isinstance(value, list)
        else []
    )


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}
