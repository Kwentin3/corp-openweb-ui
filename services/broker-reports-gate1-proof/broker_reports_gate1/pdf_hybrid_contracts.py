from __future__ import annotations

import hashlib
import json
from typing import Any


PDF_TABLE_CLASSIFICATION_SCHEMA = "broker_reports_pdf_table_classification_v1"
PDF_HYBRID_EVIDENCE_PACKAGE_SCHEMA = "broker_reports_pdf_hybrid_evidence_package_v1"
PDF_HYBRID_BINDING_OUTPUT_SCHEMA = "broker_reports_pdf_hybrid_binding_output_v1"
PDF_PROVIDER_ATTEMPT_SCHEMA = "broker_reports_pdf_provider_attempt_v1"
PDF_TABLE_MATERIALIZATION_SCHEMA = "broker_reports_pdf_table_materialization_result_v1"
PDF_TABLE_VALIDATION_SCHEMA = "broker_reports_pdf_table_validation_v1"
PDF_HYBRID_SHADOW_DECISION_SCHEMA = "broker_reports_pdf_hybrid_shadow_decision_v1"
PDF_HYBRID_PROPOSED_COMPACT_REVISION_SCHEMA = (
    "broker_reports_pdf_hybrid_proposed_compact_revision_v1"
)

BINDING_DECISIONS = {"bound", "ambiguous", "unsupported"}
VALIDATION_RESULTS = {
    "accepted_shadow",
    "blocked",
    "human_review_required",
    "unsupported",
}
ROW_KINDS = {
    "header",
    "column_numbers",
    "data",
    "section",
    "subtotal",
    "total",
    "unknown",
}
FORBIDDEN_BINDING_KEYS = {
    "value",
    "amount",
    "currency_value",
    "tax_value",
    "text",
    "source_value_ref",
    "source_value_refs",
    "word_ref",
    "word_refs",
    "business_fact",
}


class PdfHybridContractError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def hybrid_binding_output_schema() -> dict[str, Any]:
    uncertainty = {"type": "array", "items": {"type": "string"}}
    cell = {"type": "array", "items": {"type": "string"}}
    row = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "row_ordinal": {"type": "integer", "minimum": 1, "maximum": 64},
            "row_kind": {"type": "string", "enum": sorted(ROW_KINDS)},
            "cells": {"type": "array", "items": cell, "maxItems": 24},
        },
        "required": ["row_ordinal", "row_kind", "cells"],
    }
    span = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "start_row": {"type": "integer", "minimum": 1, "maximum": 64},
            "end_row": {"type": "integer", "minimum": 1, "maximum": 64},
            "start_column": {"type": "integer", "minimum": 1, "maximum": 24},
            "end_column": {"type": "integer", "minimum": 1, "maximum": 24},
            "relation": {"type": "string", "enum": ["merged", "spanning_header"]},
        },
        "required": [
            "start_row",
            "end_row",
            "start_column",
            "end_column",
            "relation",
        ],
    }
    header_relation = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "parent_row": {"type": "integer", "minimum": 1, "maximum": 8},
            "parent_column": {"type": "integer", "minimum": 1, "maximum": 24},
            "child_start_column": {"type": "integer", "minimum": 1, "maximum": 24},
            "child_end_column": {"type": "integer", "minimum": 1, "maximum": 24},
        },
        "required": [
            "parent_row",
            "parent_column",
            "child_start_column",
            "child_end_column",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [PDF_HYBRID_BINDING_OUTPUT_SCHEMA],
            },
            "package_id": {"type": "string"},
            "crop_sha256": {"type": "string"},
            "candidate_dictionary_hash": {"type": "string"},
            "decision": {"type": "string", "enum": sorted(BINDING_DECISIONS)},
            "row_count": {"type": "integer", "minimum": 0, "maximum": 64},
            "column_count": {"type": "integer", "minimum": 0, "maximum": 24},
            "header_rows": {
                "type": "array",
                "items": {"type": "integer", "minimum": 1, "maximum": 8},
                "maxItems": 8,
            },
            "header_hierarchy": {
                "type": "array",
                "items": header_relation,
            },
            "rows": {"type": "array", "items": row, "maxItems": 64},
            "spans": {"type": "array", "items": span},
            "uncertainty_codes": uncertainty,
        },
        "required": [
            "schema_version",
            "package_id",
            "crop_sha256",
            "candidate_dictionary_hash",
            "decision",
            "row_count",
            "column_count",
            "header_rows",
            "header_hierarchy",
            "rows",
            "spans",
            "uncertainty_codes",
        ],
    }


def validate_binding_output_shape(value: Any) -> list[str]:
    errors: list[str] = []
    data = value if isinstance(value, dict) else {}
    if not data:
        return ["hybrid_binding_output_not_object"]
    expected_keys = set(hybrid_binding_output_schema()["required"])
    if set(data) != expected_keys:
        errors.append("hybrid_binding_output_keys_invalid")
    forbidden = _recursive_keys(data) & FORBIDDEN_BINDING_KEYS
    if forbidden:
        errors.append("hybrid_binding_free_or_source_value_forbidden")
    if data.get("schema_version") != PDF_HYBRID_BINDING_OUTPUT_SCHEMA:
        errors.append("hybrid_binding_schema_version_invalid")
    if data.get("decision") not in BINDING_DECISIONS:
        errors.append("hybrid_binding_decision_invalid")
    rows = data.get("rows")
    if not isinstance(rows, list):
        return [*errors, "hybrid_binding_rows_invalid"]
    row_count = _integer(data.get("row_count"))
    column_count = _integer(data.get("column_count"))
    if row_count < 0 or row_count > 64 or column_count < 0 or column_count > 24:
        errors.append("hybrid_binding_shape_budget_invalid")
    if data.get("decision") == "bound" and (
        row_count == 0 or column_count == 0 or len(rows) != row_count
    ):
        errors.append("hybrid_binding_rectangular_grid_incomplete")
    positions: set[tuple[int, int]] = set()
    for expected_row, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or set(row) != {"row_ordinal", "row_kind", "cells"}:
            errors.append("hybrid_binding_row_contract_invalid")
            continue
        if row.get("row_ordinal") != expected_row or row.get("row_kind") not in ROW_KINDS:
            errors.append("hybrid_binding_row_identity_invalid")
        cells = row.get("cells")
        if not isinstance(cells, list) or (
            data.get("decision") == "bound" and len(cells) != column_count
        ):
            errors.append("hybrid_binding_row_width_invalid")
            continue
        for expected_column, cell in enumerate(cells, start=1):
            if not isinstance(cell, list) or not all(isinstance(item, str) for item in cell):
                errors.append("hybrid_binding_candidate_ids_invalid")
            positions.add((expected_row, expected_column))
    if data.get("decision") == "bound" and len(positions) != row_count * column_count:
        errors.append("hybrid_binding_silent_missing_empty_cell")
    return sorted(set(errors))


def _recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for item in value.values():
            keys.update(_recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_recursive_keys(item))
    return keys


def _integer(value: Any) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else -1
