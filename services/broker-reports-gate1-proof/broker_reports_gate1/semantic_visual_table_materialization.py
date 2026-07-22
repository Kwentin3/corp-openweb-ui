from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_dual_vlm_canonical_table_contracts import (
    CANONICAL_TABLE_SCHEMA_VERSION,
    validate_table_output,
)
from .pdf_dual_vlm_runtime import (
    PDF_SEMANTIC_VLM_PRIVATE_EVIDENCE_SCHEMA,
    sha256_json,
    validate_pdf_dual_vlm_decision,
)
from .semantic_visual_table_contracts import (
    MAX_SEMANTIC_COLUMNS,
    MAX_SEMANTIC_ROWS,
    SEMANTIC_LOGICAL_TABLE_PROFILE_ID,
    SEMANTIC_VISUAL_TABLE_ORIGIN,
    semantic_table_transcription_boundary_errors,
)
from .semantic_visual_table_projection_contracts import (
    SEMANTIC_VISUAL_TABLE_PROJECTION_VALIDATOR_VERSION,
)
from .table_projection import (
    TABLE_COVERAGE_SCHEMA_VERSION,
    TABLE_PROJECTION_SCHEMA_VERSION,
    TABLE_QUALITY_SCHEMA_VERSION,
    TableProjectionValidator,
)


SEMANTIC_VISUAL_TABLE_ENVELOPE_SCHEMA_VERSION = (
    "broker_reports_semantic_visual_table_envelope_v1"
)
SEMANTIC_LOGICAL_TABLE_SCHEMA_VERSION = "broker_reports_semantic_logical_table_v1"
SEMANTIC_VISUAL_TABLE_MATERIALIZER_VERSION = (
    "semantic_visual_table_materializer_v1"
)

FACTORY_REQUIRED = (
    "SemanticVisualTableMaterializationFactory.create is the only maintained "
    "semantic-response envelope and logical-grid materialization entrypoint"
)
FORBIDDEN = (
    "Callers must not mint semantic table IDs or indexes, pad rows, assign spans, "
    "build Gate 2 projections, or claim physical PDF geometry outside this factory"
)


class SemanticVisualTableMaterializationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SemanticVisualTableMaterializationConfig:
    maximum_rows: int = MAX_SEMANTIC_ROWS
    maximum_columns: int = MAX_SEMANTIC_COLUMNS
    maximum_cells: int = MAX_SEMANTIC_ROWS * MAX_SEMANTIC_COLUMNS


@dataclass(frozen=True)
class SemanticVisualTableMaterializationResult:
    private_envelope: dict[str, Any]
    gate2_projection: dict[str, Any]


class SemanticVisualTableMaterializationFactory:
    def __init__(
        self,
        config: SemanticVisualTableMaterializationConfig | None = None,
    ) -> None:
        self.config = config or SemanticVisualTableMaterializationConfig()

    def create(self) -> "SemanticVisualTableMaterializer":
        if (
            self.config.maximum_rows < 1
            or self.config.maximum_rows > MAX_SEMANTIC_ROWS
            or self.config.maximum_columns < 1
            or self.config.maximum_columns > MAX_SEMANTIC_COLUMNS
            or self.config.maximum_cells < 1
            or self.config.maximum_cells
            > self.config.maximum_rows * self.config.maximum_columns
        ):
            raise SemanticVisualTableMaterializationError(
                "semantic_visual_table_materializer_budget_invalid"
            )
        return SemanticVisualTableMaterializer(self.config)


class SemanticVisualTableMaterializer:
    def __init__(self, config: SemanticVisualTableMaterializationConfig) -> None:
        self.config = config

    def materialize(
        self,
        *,
        decision: dict[str, Any],
        provider_evidence: list[dict[str, Any]],
    ) -> SemanticVisualTableMaterializationResult:
        decision_errors = validate_pdf_dual_vlm_decision(decision)
        if decision_errors:
            raise SemanticVisualTableMaterializationError(decision_errors[0])
        decision_validator = _object(decision.get("deterministic_validator"))
        if (
            decision.get("status") != "semantic_transcription_valid"
            or decision_validator.get("selected_provider_contract_valid") is not True
            or decision_validator.get("semantic_response_contract_passed") is not True
            or decision.get("provider_merge") is not False
            or decision.get("canonical_table") is not None
        ):
            raise SemanticVisualTableMaterializationError(
                "semantic_visual_table_decision_not_materializable"
            )

        transcription = decision.get("semantic_transcription")
        boundary_errors = semantic_table_transcription_boundary_errors(transcription)
        if boundary_errors:
            raise SemanticVisualTableMaterializationError(boundary_errors[0])
        rows = copy.deepcopy(transcription["rows"])
        column_count = max(len(row) for row in rows)
        if (
            len(rows) > self.config.maximum_rows
            or column_count > self.config.maximum_columns
            or len(rows) * column_count > self.config.maximum_cells
        ):
            raise SemanticVisualTableMaterializationError(
                "semantic_visual_table_materializer_budget_exceeded"
            )

        selected_provider = str(decision.get("selected_provider") or "")
        executions = [
            item
            for item in decision.get("executions") or []
            if isinstance(item, dict) and item.get("provider") == selected_provider
        ]
        if len(executions) != 1:
            raise SemanticVisualTableMaterializationError(
                "semantic_visual_table_selected_execution_invalid"
            )
        selected_execution = executions[0]
        selected_evidence = _selected_private_evidence(
            decision=decision,
            execution=selected_execution,
            provider_evidence=provider_evidence,
        )

        lineage = copy.deepcopy(decision.get("source_lineage") or {})
        table_id = "semanticlogicaltable_" + stable_digest(
            [
                SEMANTIC_LOGICAL_TABLE_SCHEMA_VERSION,
                lineage.get("crop_sha256"),
                sha256_json(transcription),
            ],
            length=24,
        )
        logical_table = _logical_table(
            table_id=table_id,
            rows=rows,
            column_count=column_count,
        )
        envelope_id = "semanticenvelope_" + stable_digest(
            [
                SEMANTIC_VISUAL_TABLE_ENVELOPE_SCHEMA_VERSION,
                decision.get("decision_id"),
                selected_execution.get("execution_hash"),
                logical_table["materialization_hash"],
            ],
            length=24,
        )
        envelope = {
            "schema_version": SEMANTIC_VISUAL_TABLE_ENVELOPE_SCHEMA_VERSION,
            "envelope_id": envelope_id,
            "origin": SEMANTIC_VISUAL_TABLE_ORIGIN,
            "decision_id": decision["decision_id"],
            "table_id": table_id,
            "source_lineage": lineage,
            "provider_execution": _provider_execution_metadata(selected_execution),
            "semantic_transcription": copy.deepcopy(transcription),
            "logical_table": logical_table,
            "private_provider_evidence": copy.deepcopy(selected_evidence),
            "validator_status": "passed",
            "physical_geometry_claimed": False,
        }
        envelope["envelope_hash"] = sha256_json(envelope)
        envelope_errors = validate_semantic_visual_table_envelope(envelope)
        if envelope_errors:
            raise SemanticVisualTableMaterializationError(envelope_errors[0])

        projection = _gate2_projection(envelope)
        projection_validation = TableProjectionValidator().validate(projection)
        if projection_validation["validator_status"] != "passed":
            raise SemanticVisualTableMaterializationError(
                projection_validation["errors"][0]["code"]
            )
        projection["validator_status"] = "passed"
        projection["validator_reason_codes"] = []
        return SemanticVisualTableMaterializationResult(
            private_envelope=envelope,
            gate2_projection=projection,
        )


def validate_semantic_visual_table_envelope(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["semantic_visual_table_envelope_invalid"]
    required = {
        "schema_version",
        "envelope_id",
        "origin",
        "decision_id",
        "table_id",
        "source_lineage",
        "provider_execution",
        "semantic_transcription",
        "logical_table",
        "private_provider_evidence",
        "validator_status",
        "physical_geometry_claimed",
        "envelope_hash",
    }
    errors: list[str] = []
    if set(value) != required:
        errors.append("semantic_visual_table_envelope_fields_invalid")
    if (
        value.get("schema_version")
        != SEMANTIC_VISUAL_TABLE_ENVELOPE_SCHEMA_VERSION
        or value.get("origin") != SEMANTIC_VISUAL_TABLE_ORIGIN
        or value.get("validator_status") != "passed"
        or value.get("physical_geometry_claimed") is not False
    ):
        errors.append("semantic_visual_table_envelope_invalid")
    lineage = _object(value.get("source_lineage"))
    execution = _object(value.get("provider_execution"))
    evidence = _object(value.get("private_provider_evidence"))
    if (
        not _is_sha256(lineage.get("source_sha256"))
        or not _is_sha256(lineage.get("crop_sha256"))
        or execution.get("input_hash") != lineage.get("crop_sha256")
        or execution.get("terminal_provider_status") != "completed"
        or execution.get("validator_status") != "passed"
        or evidence.get("decision_id") != value.get("decision_id")
        or evidence.get("execution_hash") != execution.get("execution_hash")
        or evidence.get("provider") != execution.get("provider")
        or evidence.get("parsed_semantic_response")
        != value.get("semantic_transcription")
        or evidence.get("raw_provider_response") is None
    ):
        errors.append("semantic_visual_table_provenance_invalid")
    if _private_evidence_errors(evidence):
        errors.append("semantic_visual_table_private_evidence_invalid")
    errors.extend(_logical_table_errors(value.get("logical_table")))
    logical = _object(value.get("logical_table"))
    if logical.get("table_id") != value.get("table_id"):
        errors.append("semantic_visual_table_id_binding_invalid")
    unhashed = copy.deepcopy(value)
    actual_hash = unhashed.pop("envelope_hash", None)
    if not _is_sha256(actual_hash) or sha256_json(unhashed) != actual_hash:
        errors.append("semantic_visual_table_envelope_hash_invalid")
    return sorted(set(errors))


def _logical_table(
    *, table_id: str, rows: list[list[Any]], column_count: int
) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    canonical_cells: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        for column_index in range(column_count):
            if column_index >= len(row):
                value = None
                empty_origin = "short_row_padding"
            else:
                value = row[column_index]
                empty_origin = "semantic_null" if value is None else "none"
            cells.append(
                {
                    "cell_id": "semanticcell_"
                    + stable_digest(
                        [table_id, row_index, column_index], length=24
                    ),
                    "row_index": row_index,
                    "column_index": column_index,
                    "row_span": 1,
                    "column_span": 1,
                    "value": value,
                    "empty_origin": empty_origin,
                }
            )
            canonical_cells.append(
                {
                    "row_index": row_index,
                    "column_index": column_index,
                    "row_span": 1,
                    "column_span": 1,
                    "content_state": "empty" if value is None else "present",
                    "source_text": "" if value is None else value,
                }
            )
    canonical_table = {
        "schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
        "table_id": table_id,
        "row_count": len(rows),
        "column_count": column_count,
        "cells": canonical_cells,
    }
    canonical_errors = validate_table_output(canonical_table, table_id=table_id)
    if canonical_errors:
        raise SemanticVisualTableMaterializationError(canonical_errors[0])
    material = {
        "table_id": table_id,
        "row_count": len(rows),
        "column_count": column_count,
        "cells": [
            {
                "row_index": cell["row_index"],
                "column_index": cell["column_index"],
                "value": cell["value"],
                "empty_origin": cell["empty_origin"],
            }
            for cell in cells
        ],
    }
    return {
        "schema_version": SEMANTIC_LOGICAL_TABLE_SCHEMA_VERSION,
        "table_id": table_id,
        "origin": SEMANTIC_VISUAL_TABLE_ORIGIN,
        "physical_geometry_claimed": False,
        "row_count": len(rows),
        "column_count": column_count,
        "cells": cells,
        "canonical_table": canonical_table,
        "materialization_hash": sha256_json(material),
    }


def _logical_table_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["semantic_logical_table_invalid"]
    errors: list[str] = []
    if (
        value.get("schema_version") != SEMANTIC_LOGICAL_TABLE_SCHEMA_VERSION
        or value.get("origin") != SEMANTIC_VISUAL_TABLE_ORIGIN
        or value.get("physical_geometry_claimed") is not False
    ):
        errors.append("semantic_logical_table_invalid")
    cells = [item for item in value.get("cells") or [] if isinstance(item, dict)]
    rows = value.get("row_count")
    columns = value.get("column_count")
    expected = rows * columns if isinstance(rows, int) and isinstance(columns, int) else 0
    coordinates = {
        (item.get("row_index"), item.get("column_index")) for item in cells
    }
    if (
        expected < 1
        or len(cells) != expected
        or len(coordinates) != expected
        or any(
            item.get("row_span") != 1
            or item.get("column_span") != 1
            or item.get("empty_origin")
            not in {"none", "semantic_null", "short_row_padding"}
            for item in cells
        )
    ):
        errors.append("semantic_logical_table_grid_invalid")
    material = {
        "table_id": value.get("table_id"),
        "row_count": rows,
        "column_count": columns,
        "cells": [
            {
                "row_index": item.get("row_index"),
                "column_index": item.get("column_index"),
                "value": item.get("value"),
                "empty_origin": item.get("empty_origin"),
            }
            for item in cells
        ],
    }
    if sha256_json(material) != value.get("materialization_hash"):
        errors.append("semantic_logical_table_materialization_hash_invalid")
    if validate_table_output(
        value.get("canonical_table"), table_id=value.get("table_id")
    ):
        errors.append("semantic_logical_table_canonical_grid_invalid")
    return errors


def _selected_private_evidence(
    *,
    decision: dict[str, Any],
    execution: dict[str, Any],
    provider_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    matches = [
        item
        for item in provider_evidence
        if isinstance(item, dict)
        and item.get("decision_id") == decision.get("decision_id")
        and item.get("execution_hash") == execution.get("execution_hash")
        and item.get("provider") == decision.get("selected_provider")
    ]
    if len(matches) != 1 or _private_evidence_errors(matches[0]):
        raise SemanticVisualTableMaterializationError(
            "semantic_visual_table_private_evidence_invalid"
        )
    if (
        matches[0].get("parsed_semantic_response")
        != decision.get("semantic_transcription")
        or matches[0].get("response_hash") != execution.get("response_hash")
        or matches[0].get("input_hash") != decision.get("input_hash")
        or matches[0].get("raw_provider_response") is None
    ):
        raise SemanticVisualTableMaterializationError(
            "semantic_visual_table_private_evidence_binding_invalid"
        )
    return copy.deepcopy(matches[0])


def _private_evidence_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["semantic_visual_table_private_evidence_invalid"]
    required = {
        "schema_version",
        "decision_id",
        "execution_hash",
        "provider",
        "invocation_role",
        "input_hash",
        "response_hash",
        "terminal_provider_status",
        "raw_provider_response",
        "parsed_semantic_response",
        "evidence_hash",
    }
    errors = []
    if set(value) != required:
        errors.append("semantic_visual_table_private_evidence_fields_invalid")
    unhashed = copy.deepcopy(value)
    actual_hash = unhashed.pop("evidence_hash", None)
    if (
        value.get("schema_version") != PDF_SEMANTIC_VLM_PRIVATE_EVIDENCE_SCHEMA
        or not _is_sha256(value.get("execution_hash"))
        or not _is_sha256(value.get("input_hash"))
        or not _is_sha256(value.get("response_hash"))
        or not _is_sha256(actual_hash)
        or sha256_json(unhashed) != actual_hash
    ):
        errors.append("semantic_visual_table_private_evidence_invalid")
    return errors


def _provider_execution_metadata(execution: dict[str, Any]) -> dict[str, Any]:
    preflight = _object(execution.get("preflight"))
    validator = _object(execution.get("validator_result"))
    return {
        "execution_hash": execution.get("execution_hash"),
        "task_id": execution.get("task_id"),
        "input_hash": execution.get("input_hash"),
        "provider": execution.get("provider"),
        "provider_profile": execution.get("provider_profile"),
        "provider_profile_revision": execution.get("provider_profile_revision"),
        "requested_model_id": execution.get("requested_model_id"),
        "resolved_model_id": execution.get("resolved_model_id"),
        "prompt_id": execution.get("prompt_id"),
        "prompt_version": execution.get("prompt_version"),
        "prompt_hash": execution.get("prompt_hash"),
        "output_schema_version": execution.get("output_schema_version"),
        "canonical_schema_hash": execution.get("canonical_schema_hash"),
        "provider_adapted_schema_hash": execution.get(
            "provider_adapted_schema_hash"
        ),
        "request_hash": preflight.get("request_hash"),
        "response_hash": execution.get("response_hash"),
        "usage": copy.deepcopy(execution.get("usage") or {}),
        "latency_ms": execution.get("latency_ms"),
        "terminal_provider_status": execution.get("terminal_provider_status"),
        "validator_status": validator.get("status"),
        "semantic_transcription_hash": validator.get(
            "semantic_transcription_hash"
        ),
    }


def _gate2_projection(envelope: dict[str, Any]) -> dict[str, Any]:
    logical = envelope["logical_table"]
    lineage = envelope["source_lineage"]
    table_id = logical["table_id"]
    projection_id = "tableproj_" + stable_digest(
        [SEMANTIC_LOGICAL_TABLE_PROFILE_ID, envelope["envelope_hash"]], length=24
    )
    row_refs = [
        "tablerow_" + stable_digest([table_id, row_index], length=24)
        for row_index in range(logical["row_count"])
    ]
    column_refs = [
        "tablecolumn_" + stable_digest([table_id, column_index], length=24)
        for column_index in range(logical["column_count"])
    ]
    cells: list[dict[str, Any]] = []
    private_values: list[dict[str, Any]] = []
    source_value_index: list[dict[str, Any]] = []
    source_value_refs: list[str] = []
    for logical_cell in logical["cells"]:
        row_index = logical_cell["row_index"]
        column_index = logical_cell["column_index"]
        cell_ref = logical_cell["cell_id"]
        value_path_ref = "tablevaluepath_" + stable_digest(
            [table_id, cell_ref, logical_cell["value"]], length=24
        )
        value_checksum_ref = _checksum_ref("valuechk", logical_cell["value"])
        refs: list[str] = []
        if logical_cell["value"] is not None:
            source_value_ref = "semanticsourcevalue_" + stable_digest(
                [table_id, row_index, column_index, value_checksum_ref], length=24
            )
            refs.append(source_value_ref)
            source_value_refs.append(source_value_ref)
            source_value_index.append(
                {
                    "source_value_ref": source_value_ref,
                    "source_object_ref": cell_ref,
                    "cell_ref": cell_ref,
                    "value_checksum_ref": value_checksum_ref,
                    "value_path": {
                        "kind": "table_projection_private_value",
                        "value_path_ref": value_path_ref,
                    },
                }
            )
        private_values.append(
            {
                "value_path_ref": value_path_ref,
                "normalized_value": logical_cell["value"],
                "value_checksum_ref": value_checksum_ref,
                "source_value_refs": refs,
            }
        )
        cells.append(
            {
                "cell_ref": cell_ref,
                "row_ref": row_refs[row_index],
                "column_ref": column_refs[column_index],
                "row_span": 1,
                "column_span": 1,
                "cell_value_ref": "cellval_"
                + stable_digest([table_id, cell_ref, value_checksum_ref], length=24),
                "source_value_refs": refs,
                "normalized_private_value_path": value_path_ref,
                "multi_line_cell": False,
                "wrapped_text_cell": False,
                "ambiguous_cell_boundary": False,
                "split_cell_candidate": False,
                "merged_cell_group_ref": None,
                "confidence": "semantic_contract_only",
                "value_kind_hints": [],
                "reason_codes": [],
                "logical_row_index": row_index,
                "logical_column_index": column_index,
                "empty_origin": logical_cell["empty_origin"],
            }
        )
    rows = [
        {
            "row_ref": row_ref,
            "row_ordinal": row_index,
            "row_role": "unknown_row_role",
            "cell_refs": [
                cell["cell_ref"]
                for cell in cells
                if cell["logical_row_index"] == row_index
            ],
            "reason_codes": ["semantic_role_not_inferred"],
        }
        for row_index, row_ref in enumerate(row_refs)
    ]
    coverage = {
        "schema_version": TABLE_COVERAGE_SCHEMA_VERSION,
        "coverage_ref": "tablecoverage_"
        + stable_digest([projection_id, source_value_refs], length=24),
        "selected_source_refs": source_value_refs,
        "accounted_source_refs": source_value_refs,
        "table_owned_refs": source_value_refs,
        "fallback_text_refs": [],
        "non_table_refs": [],
        "rejected_refs": [],
        "duplicate_accounted_refs": [],
        "unaccounted_refs": [],
        "selected_total": len(source_value_refs),
        "accounted_total": len(source_value_refs),
        "coverage_status": "complete",
        "all_selected_refs_accounted": True,
    }
    quality = {
        "schema_version": TABLE_QUALITY_SCHEMA_VERSION,
        "row_alignment_score": 1.0,
        "column_alignment_score": 1.0,
        "header_confidence": "unknown",
        "cell_boundary_confidence": 1.0,
        "coverage_completeness": 1.0,
        "duplicate_overlap_count": 0,
        "unaccounted_ref_count": 0,
        "fallback_required": False,
        "reconstruction_quality": "medium",
        "quality_scope": "logical_materialization_only_not_content_fidelity",
    }
    projection = {
        "schema_version": TABLE_PROJECTION_SCHEMA_VERSION,
        "table_projection_id": projection_id,
        "table_ref": table_id,
        "logical_table_id": table_id,
        "canonical_table_id": table_id,
        "canonical_profile_id": SEMANTIC_LOGICAL_TABLE_PROFILE_ID,
        "canonical_table_scope": "ready_validated_projection_only",
        "canonical_contract": {
            "profile_id": SEMANTIC_LOGICAL_TABLE_PROFILE_ID,
            "origin": SEMANTIC_VISUAL_TABLE_ORIGIN,
            "physical_geometry_claimed": False,
        },
        "canonical_validation": {
            "validator_version": SEMANTIC_VISUAL_TABLE_PROJECTION_VALIDATOR_VERSION,
            "validator_status": "passed",
            "semantic_response_contract_passed": True,
            "logical_grid_materialized": True,
            "physical_geometry_claimed": False,
        },
        "source_format": "pdf",
        "table_origin": SEMANTIC_VISUAL_TABLE_ORIGIN,
        "source_document_ref": lineage.get("source_ref"),
        "source_unit_ref": lineage.get("candidate_ref"),
        "parent_payload_ref": None,
        "normalization_run_id": envelope["decision_id"],
        "parser_ref": SEMANTIC_VISUAL_TABLE_MATERIALIZER_VERSION,
        "parser_engine": "deterministic_semantic_logical_grid",
        "parser_engine_version": SEMANTIC_VISUAL_TABLE_MATERIALIZER_VERSION,
        "parser_config_ref": SEMANTIC_LOGICAL_TABLE_PROFILE_ID,
        "source_checksum_ref": "srcsum_"
        + stable_digest(
            [lineage.get("source_ref"), lineage.get("source_sha256")], length=24
        ),
        "payload_checksum_ref": lineage.get("crop_sha256"),
        "source_unit_checksum_ref": lineage.get("crop_manifest_hash"),
        "table_projection_checksum_ref": None,
        "visibility": "private_case",
        "storage_backend": "project_artifact_payload",
        "projection_status": "ready",
        "row_refs": row_refs,
        "column_refs": column_refs,
        "cell_refs": [cell["cell_ref"] for cell in cells],
        "cell_value_refs": [cell["cell_value_ref"] for cell in cells],
        "source_value_refs": source_value_refs,
        "row_count": logical["row_count"],
        "column_count": logical["column_count"],
        "cell_count": len(cells),
        "row_order_policy": "semantic_source_order_preserved",
        "column_order_policy": "deterministic_logical_order",
        "table_bbox_ref": None,
        "page_refs": [f"page_{lineage.get('page_number')}"],
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
            "column_labels": [],
            "header_to_column_mapping_status": "not_inferred",
            "pdf_header_candidate": False,
            "semantic_header_truth_claimed": False,
        },
        "coverage": coverage,
        "quality": quality,
        "geometry": {
            "physical_geometry_claimed": False,
            "crop_id": lineage.get("crop_id"),
            "crop_sha256": lineage.get("crop_sha256"),
        },
        "semantic_visual_table": {
            "schema_version": SEMANTIC_VISUAL_TABLE_ENVELOPE_SCHEMA_VERSION,
            "envelope_id": envelope["envelope_id"],
            "envelope_hash": envelope["envelope_hash"],
            "origin": SEMANTIC_VISUAL_TABLE_ORIGIN,
            "provider": envelope["provider_execution"]["provider"],
            "model_id": envelope["provider_execution"]["resolved_model_id"],
            "materialization_hash": logical["materialization_hash"],
            "physical_geometry_claimed": False,
            "model_generated_indexes": 0,
            "model_generated_spans": 0,
        },
        "table_candidate_status": "canonical_table_accepted",
        "reconstruction_strategy": "semantic_rows_deterministic_rectangular_grid",
        "reconstruction_reason_codes": [
            "semantic_contract_passed",
            "physical_geometry_not_claimed",
        ],
        "reconstruction_quality": "medium",
        "semantic_table_truth_claimed": False,
        "source_facts_extracted": False,
        "tax_meaning_inferred": False,
        "knowledge_rag_used": False,
        "vectorization_performed": False,
        "ocr_vlm_used": True,
        "page_rendering_used_for_extraction": True,
    }
    projection["table_projection_checksum_ref"] = _projection_checksum(projection)
    return projection


def _projection_checksum(projection: dict[str, Any]) -> str:
    material = copy.deepcopy(projection)
    material.pop("table_projection_checksum_ref", None)
    material.pop("validator_status", None)
    material.pop("validator_reason_codes", None)
    return _checksum_ref("tableprojchk", material)


def _checksum_ref(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
