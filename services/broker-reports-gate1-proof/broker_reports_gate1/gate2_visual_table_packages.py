from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .gate2_source_fact_contracts import PACKAGE_SCHEMA_VERSION
from .visual_neutral_tables import validate_visual_neutral_table_result


VISUAL_TABLE_PACKAGE_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_gate2_visual_table_package_validation_v1"
)

FACTORY_REQUIRED = (
    "Gate2VisualTablePackageFactory.create is the only Gate 2 package entrypoint "
    "for accepted visual-neutral tables"
)
FORBIDDEN = (
    "Callers must not rebuild a table from page pixels in Gate 2, accept a "
    "noncanonical visual result, or send a whole page to a model"
)


@dataclass(frozen=True)
class Gate2VisualTablePackageConfig:
    max_rows_per_table: int = 250
    max_cells_per_table: int = 40_000


class Gate2VisualTablePackageFactory:
    def __init__(
        self, config: Gate2VisualTablePackageConfig | None = None
    ) -> None:
        self.config = config or Gate2VisualTablePackageConfig()

    def create(self) -> "Gate2VisualTablePackageBuilder":
        if (
            self.config.max_rows_per_table <= 0
            or self.config.max_cells_per_table <= 0
        ):
            raise ValueError("gate2_visual_table_package_budget_invalid")
        return Gate2VisualTablePackageBuilder(config=self.config)


class Gate2VisualTablePackageBuilder:
    def __init__(self, *, config: Gate2VisualTablePackageConfig) -> None:
        self.config = config

    def build(
        self,
        *,
        visual_result: dict[str, Any],
        visual_result_artifact_ref: str,
        normalization_run_id: str,
        case_id: str | None,
        issue_refs: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        result_errors = validate_visual_neutral_table_result(visual_result)
        if result_errors:
            raise ValueError("gate2_visual_result_invalid")
        if not str(visual_result.get("promotion_state") or "").startswith(
            "canonical_table_accepted_"
        ):
            raise ValueError("gate2_visual_result_not_accepted")
        provider = _object(visual_result.get("provider_accounting"))
        if any(provider.get(key) not in {0, 0.0} for key in ("calls", "retries", "tokens", "cost", "whole_document_uploads")):
            raise ValueError("gate2_visual_result_provider_accounting_nonzero")

        packages = []
        for table in _dicts(visual_result.get("canonical_tables")):
            if int(table.get("row_count") or 0) > self.config.max_rows_per_table:
                raise ValueError("gate2_visual_table_row_budget_exceeded")
            if len(_dicts(table.get("cells"))) > self.config.max_cells_per_table:
                raise ValueError("gate2_visual_table_cell_budget_exceeded")
            package = self._build_table(
                visual_result=visual_result,
                table=table,
                visual_result_artifact_ref=visual_result_artifact_ref,
                normalization_run_id=normalization_run_id,
                case_id=case_id,
                issue_refs=issue_refs or [],
            )
            validate_gate2_visual_table_package(
                package=package,
                visual_result=visual_result,
                table=table,
            )
            packages.append(package)
        if not packages:
            raise ValueError("gate2_visual_result_tables_missing")
        return packages

    def _build_table(
        self,
        *,
        visual_result: dict[str, Any],
        table: dict[str, Any],
        visual_result_artifact_ref: str,
        normalization_run_id: str,
        case_id: str | None,
        issue_refs: list[str],
    ) -> dict[str, Any]:
        table_id = str(table.get("table_id") or "")
        cells = sorted(
            _dicts(table.get("cells")),
            key=lambda item: (
                int(item.get("row_index") or 0),
                int(item.get("column_index") or 0),
            ),
        )
        row_count = int(table.get("row_count") or 0)
        row_roles = _strings(table.get("row_roles"))
        header_rows = {int(value) for value in table.get("header_rows") or []}
        rows: list[dict[str, Any]] = []
        cell_provenance: list[dict[str, Any]] = []
        source_value_index: list[dict[str, Any]] = []
        private_values: list[dict[str, Any]] = []
        model_rows: list[dict[str, Any]] = []
        cell_refs: list[str] = []
        source_value_refs: list[str] = []
        header_labels_by_column: dict[int, str] = {}

        for cell in cells:
            if int(cell.get("row_index") or 0) not in header_rows:
                continue
            label = str(cell.get("source_text") or "") or "unknown"
            start = int(cell.get("column_index") or 0)
            span = int(cell.get("column_span") or 1)
            for column in range(start, start + span):
                header_labels_by_column.setdefault(column, label)

        by_row: dict[int, list[dict[str, Any]]] = {
            row: [] for row in range(row_count)
        }
        for cell in cells:
            by_row[int(cell.get("row_index") or 0)].append(cell)

        for row_index in range(row_count):
            row_ref = "visualrow_" + stable_digest(
                [table_id, row_index], length=24
            )
            row_cell_refs: list[str] = []
            model_cells: list[dict[str, Any]] = []
            for cell in sorted(
                by_row.get(row_index, []),
                key=lambda item: int(item.get("column_index") or 0),
            ):
                column_index = int(cell.get("column_index") or 0)
                cell_ref = "visualcell_" + stable_digest(
                    [
                        table_id,
                        row_index,
                        column_index,
                        cell.get("row_span"),
                        cell.get("column_span"),
                    ],
                    length=24,
                )
                source_value_ref = "visualsrcval_" + stable_digest(
                    [table_id, cell_ref, cell.get("source_text")], length=24
                )
                value_path_ref = "visualvalue_" + stable_digest(
                    [source_value_ref, "private"], length=24
                )
                column_ref = "visualcolumn_" + stable_digest(
                    [table_id, column_index], length=20
                )
                value = str(cell.get("source_text") or "")
                row_cell_refs.append(cell_ref)
                cell_refs.append(cell_ref)
                source_value_refs.append(source_value_ref)
                cell_provenance.append(
                    {
                        "cell_ref": cell_ref,
                        "row_ref": row_ref,
                        "column_ref": column_ref,
                        "row_index": row_index,
                        "column_index": column_index,
                        "row_span": int(cell.get("row_span") or 1),
                        "column_span": int(cell.get("column_span") or 1),
                        "bbox": copy.deepcopy(cell.get("bbox") or []),
                        "ocr_line_refs": _strings(cell.get("ocr_line_refs")),
                        "content_state": cell.get("content_state"),
                        "source_value_refs": [source_value_ref],
                        "normalized_private_value_path": value_path_ref,
                        "value_kind_hints": [],
                    }
                )
                source_value_index.append(
                    {
                        "source_value_ref": source_value_ref,
                        "value_path_ref": value_path_ref,
                        "cell_ref": cell_ref,
                        "source_table_ref": table.get("source_table_ref"),
                        "ocr_line_refs": _strings(cell.get("ocr_line_refs")),
                    }
                )
                private_values.append(
                    {
                        "value_path_ref": value_path_ref,
                        "normalized_value": value,
                    }
                )
                model_cells.append(
                    {
                        "cell_ref": cell_ref,
                        "column_ref": column_ref,
                        "header_label": header_labels_by_column.get(
                            column_index, "unknown"
                        ),
                        "source_value_ref": source_value_ref,
                        "source_value_refs": [source_value_ref],
                        "value": value,
                        "value_kind_hints": [],
                        "row_span": int(cell.get("row_span") or 1),
                        "column_span": int(cell.get("column_span") or 1),
                    }
                )
            role = row_roles[row_index] if row_index < len(row_roles) else "body"
            rows.append(
                {
                    "row_ref": row_ref,
                    "row_index": row_index,
                    "row_role": role,
                    "cell_refs": row_cell_refs,
                }
            )
            model_rows.append(
                {
                    "row_ref": row_ref,
                    "row_role": role,
                    "cells": model_cells,
                }
            )

        selected_refs = [str(row["row_ref"]) for row in rows]
        no_fact = [
            {"source_ref": row["row_ref"], "reason_code": "header_row"}
            for row in rows
            if row["row_role"] == "header"
        ]
        no_fact_refs = {str(item["source_ref"]) for item in no_fact}
        fact_refs = [ref for ref in selected_refs if ref not in no_fact_refs]
        coverage_ref = "visualcoverage_" + stable_digest(
            [table_id, selected_refs, cell_refs, source_value_refs], length=24
        )
        package_id = "visualtablepkg_" + stable_digest(
            [
                visual_result.get("integrity_ref"),
                table.get("table_checksum_ref"),
                visual_result_artifact_ref,
                sorted(set(issue_refs)),
            ],
            length=24,
        )
        source_unit = {
            "unit_id": "visualtableunit_"
            + stable_digest([package_id, table_id], length=24),
            "unit_kind": "table_row_window",
            "slice_ref": visual_result.get("recovery_id"),
            "visual_recovery_id": visual_result.get("recovery_id"),
            "visual_recovery_artifact_ref": visual_result_artifact_ref,
            "canonical_table_id": table_id,
            "table_ref": table.get("source_table_ref"),
            "source_format": "pdf_visual",
            "source_input_mode": "visual_neutral_table",
            "page_number": visual_result.get("page_number"),
            "declared_region_bbox": copy.deepcopy(
                visual_result.get("declared_region_bbox") or []
            ),
            "image_sha256": visual_result.get("image_sha256"),
            "slice_payload_checksum_ref": visual_result.get("integrity_ref"),
            "table_checksum_ref": table.get("table_checksum_ref"),
            "coverage_ref": coverage_ref,
            "continuation": copy.deepcopy(
                visual_result.get("continuation") or {}
            ),
            "source_slice_truncated": False,
            "parent_source_slice_truncated": False,
            "parent_remainder_status": "not_applicable_parent_complete",
            "normalized_header_descriptors": [
                {
                    "column_ref": "visualcolumn_"
                    + stable_digest([table_id, column], length=20),
                    "column_index": column,
                    "normalized_label": header_labels_by_column.get(
                        column, "unknown"
                    ),
                }
                for column in range(int(table.get("column_count") or 0))
            ],
            "row_refs": selected_refs,
            "row_provenance": rows,
            "cell_refs": cell_refs,
            "cell_value_refs": source_value_refs,
            "cell_provenance": cell_provenance,
            "source_value_refs": source_value_refs,
            "source_value_index": source_value_index,
            "private_values": private_values,
            "normalized_source_projection": {
                "cells": [
                    [str(cell.get("value") or "") for cell in row["cells"]]
                    for row in model_rows
                ]
            },
            "model_source_projection": {
                "schema_version": "gate2_model_source_projection_v0",
                "rows": model_rows,
            },
            "table_quality": {
                "promotion_state": visual_result.get("promotion_state"),
                "operator_review_status": visual_result.get(
                    "operator_review_status"
                ),
                "source_to_table_accounting_passed": True,
            },
            "table_candidate_status": "accepted_visual_neutral_table",
            "table_fallback_metadata": {
                "bbox": copy.deepcopy(table.get("bbox") or []),
                "row_boundaries": copy.deepcopy(
                    table.get("row_boundaries") or []
                ),
                "column_boundaries": copy.deepcopy(
                    table.get("column_boundaries") or []
                ),
                "merge_evidence": copy.deepcopy(
                    table.get("merge_evidence") or {}
                ),
            },
            "semantic_table_truth_claimed": False,
        }
        return {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "package_mode": "gate2_visual_neutral_table_no_model_reconstruction",
            "package_id": package_id,
            "extraction_run_id": "visualtableextractrun_"
            + stable_digest([package_id, "source_facts_pending"], length=24),
            "normalization_run_id": normalization_run_id,
            "case_id": case_id,
            "document_ref": visual_result.get("source_document_ref"),
            "source_unit": source_unit,
            "allowed_evidence_refs": sorted(
                {
                    str(visual_result.get("recovery_id") or ""),
                    str(visual_result.get("integrity_ref") or ""),
                    str(table_id),
                    str(table.get("source_table_ref") or ""),
                    str(table.get("table_checksum_ref") or ""),
                    *selected_refs,
                    *cell_refs,
                    *source_value_refs,
                    *(
                        ref
                        for cell in cells
                        for ref in _strings(cell.get("ocr_line_refs"))
                    ),
                }
                - {""}
            ),
            "allowed_source_value_refs": source_value_refs,
            "issue_context": [
                {"issue_ref": ref, "scope": "visual_neutral_table"}
                for ref in sorted(set(issue_refs))
            ],
            "allowed_issue_refs": sorted(set(issue_refs)),
            "coverage_expectation": {
                "coverage_ref": coverage_ref,
                "selected_source_refs": selected_refs,
                "ignorable_header_refs": sorted(no_fact_refs),
                "ignorable_blank_refs": [],
                "layout_candidate_refs": [],
                "mandatory_no_fact_results": no_fact,
                "fact_candidate_refs": fact_refs,
                "required_accounting_total": len(selected_refs),
                "coverage_policy_id": "gate2_visual_neutral_table_coverage_v1",
            },
            "prompt_contract": {
                "model_call_performed": False,
                "model_must_classify_rows_not_reconstruct_table": True,
                "whole_pdf_or_page_included": False,
                "source_facts_persisted": False,
            },
            "expansion_readiness": {
                "limited_primary_expansion_ready": True,
                "reason": "accepted_bounded_visual_neutral_table",
            },
            "privacy_policy": {
                "raw_filenames_in_package": False,
                "raw_file_ids_in_package": False,
                "private_paths_in_package": False,
                "chat_text_in_package": False,
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "external_provider_used": False,
                "whole_page_in_model_context": False,
                "model_canonical_authority": False,
                "local_ocr_used": True,
                "page_rendering_used_for_extraction": True,
            },
        }


def validate_gate2_visual_table_package(
    *,
    package: dict[str, Any],
    visual_result: dict[str, Any],
    table: dict[str, Any],
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    package_id = str(package.get("package_id") or "")
    source_unit = _object(package.get("source_unit"))
    coverage = _object(package.get("coverage_expectation"))
    selected = _strings(coverage.get("selected_source_refs"))
    no_fact = {
        str(item.get("source_ref") or "")
        for item in _dicts(coverage.get("mandatory_no_fact_results"))
    }
    fact_refs = set(_strings(coverage.get("fact_candidate_refs")))
    if validate_visual_neutral_table_result(visual_result):
        errors.append(_error("gate2_visual_result_invalid", package_id))
    if not str(visual_result.get("promotion_state") or "").startswith(
        "canonical_table_accepted_"
    ):
        errors.append(_error("gate2_visual_result_not_accepted", package_id))
    if package.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        errors.append(_error("gate2_visual_table_package_schema_mismatch", package_id))
    if package.get("package_mode") != "gate2_visual_neutral_table_no_model_reconstruction":
        errors.append(_error("gate2_visual_table_package_mode_invalid", package_id))
    if source_unit.get("unit_kind") != "table_row_window":
        errors.append(_error("gate2_visual_table_unit_kind_invalid", package_id))
    if source_unit.get("source_input_mode") != "visual_neutral_table":
        errors.append(_error("gate2_visual_table_source_mode_invalid", package_id))
    if source_unit.get("canonical_table_id") != table.get("table_id"):
        errors.append(_error("gate2_visual_table_identity_mismatch", package_id))
    if source_unit.get("table_checksum_ref") != table.get("table_checksum_ref"):
        errors.append(_error("gate2_visual_table_checksum_mismatch", package_id))
    if source_unit.get("slice_payload_checksum_ref") != visual_result.get(
        "integrity_ref"
    ):
        errors.append(_error("gate2_visual_result_integrity_mismatch", package_id))
    if source_unit.get("semantic_table_truth_claimed") is not False:
        errors.append(_error("gate2_visual_semantic_truth_forbidden", package_id))
    if selected != _strings(source_unit.get("row_refs")):
        errors.append(_error("gate2_visual_table_row_refs_mismatch", package_id))
    if no_fact | fact_refs != set(selected) or no_fact & fact_refs:
        errors.append(_error("gate2_visual_table_coverage_mismatch", package_id))
    if int(coverage.get("required_accounting_total") or 0) != len(selected):
        errors.append(
            _error("gate2_visual_table_coverage_count_mismatch", package_id)
        )
    if set(_strings(package.get("allowed_source_value_refs"))) != set(
        _strings(source_unit.get("source_value_refs"))
    ):
        errors.append(_error("gate2_visual_source_value_refs_mismatch", package_id))
    if _strings(package.get("allowed_issue_refs")) != sorted(
        str(item.get("issue_ref") or "")
        for item in _dicts(package.get("issue_context"))
    ):
        errors.append(_error("gate2_visual_issue_refs_mismatch", package_id))
    prompt = _object(package.get("prompt_contract"))
    if (
        prompt.get("model_call_performed") is not False
        or prompt.get("whole_pdf_or_page_included") is not False
        or prompt.get("source_facts_persisted") is not False
    ):
        errors.append(_error("gate2_visual_prompt_boundary_failed", package_id))
    privacy = _object(package.get("privacy_policy"))
    for key in (
        "raw_filenames_in_package",
        "raw_file_ids_in_package",
        "private_paths_in_package",
        "chat_text_in_package",
        "knowledge_rag_used",
        "vectorization_performed",
        "external_provider_used",
        "whole_page_in_model_context",
        "model_canonical_authority",
    ):
        if privacy.get(key) is not False:
            errors.append(_error("gate2_visual_privacy_guard_failed", key))
    if (
        privacy.get("local_ocr_used") is not True
        or privacy.get("page_rendering_used_for_extraction") is not True
    ):
        errors.append(_error("gate2_visual_method_accounting_invalid", package_id))
    private_values = {
        str(item.get("value_path_ref") or ""): str(
            item.get("normalized_value") or ""
        )
        for item in _dicts(source_unit.get("private_values"))
    }
    for cell in _dicts(source_unit.get("cell_provenance")):
        value = private_values.get(
            str(cell.get("normalized_private_value_path") or "")
        )
        source_cell = next(
            (
                item
                for item in _dicts(table.get("cells"))
                if int(item.get("row_index") or 0) == int(cell.get("row_index") or 0)
                and int(item.get("column_index") or 0)
                == int(cell.get("column_index") or 0)
            ),
            None,
        )
        if source_cell is None or value != str(source_cell.get("source_text") or ""):
            errors.append(
                _error("gate2_visual_cell_value_reproduction_failed", package_id)
            )
            break
    result = {
        "schema_version": VISUAL_TABLE_PACKAGE_VALIDATION_SCHEMA_VERSION,
        "package_id": package_id,
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors_count": len(errors),
        "errors": errors,
    }
    if errors:
        raise ValueError(errors[0]["code"])
    return result


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)]


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)]


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}
