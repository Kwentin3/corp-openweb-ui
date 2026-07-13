from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_compact_canonical import (
    PDF_COMPACT_CANONICAL_SCHEMA_VERSION,
    PdfCompactCanonicalError,
    PdfCompactCanonicalValidator,
    compact_source_evidence,
    compact_table_cells,
    compact_table_rows,
)
from .table_projection import (
    TABLE_PROJECTION_SCHEMA_VERSION,
    TableProjectionValidator,
)


PDF_COMPACT_GATE2_MAPPING_SCHEMA_VERSION = "broker_reports_pdf_compact_gate2_mapping_v1"

FACTORY_REQUIRED = (
    "PdfCompactGate2AdapterFactory.create is the only compact-to-v0 mapping entrypoint"
)
FORBIDDEN = (
    "The compact adapter is migration proof only; production Gate 2 selection must not use it "
    "until a later approved goal changes the authoritative input path"
)


@dataclass(frozen=True)
class PdfCompactGate2AdapterConfig:
    target_schema_version: str = TABLE_PROJECTION_SCHEMA_VERSION


class PdfCompactGate2AdapterFactory:
    def __init__(self, config: PdfCompactGate2AdapterConfig | None = None) -> None:
        self.config = config or PdfCompactGate2AdapterConfig()

    def create(self) -> "PdfCompactGate2Adapter":
        if self.config.target_schema_version != TABLE_PROJECTION_SCHEMA_VERSION:
            raise PdfCompactCanonicalError("pdf_compact_adapter_target_schema_invalid")
        return PdfCompactGate2Adapter(self.config)


class PdfCompactGate2Adapter:
    def __init__(self, config: PdfCompactGate2AdapterConfig) -> None:
        self.config = config

    def map_table(
        self, *, compact_document: dict[str, Any], table_ref: str
    ) -> dict[str, Any]:
        if not PdfCompactCanonicalValidator().validate(compact_document)["passed"]:
            raise PdfCompactCanonicalError("pdf_compact_adapter_document_invalid")
        matches = [
            item
            for item in _dicts(compact_document.get("tables"))
            if item.get("table_ref") == table_ref
        ]
        if len(matches) != 1:
            raise PdfCompactCanonicalError("pdf_compact_adapter_table_not_unique", table_ref)
        table = matches[0]
        if table.get("status") != "accepted":
            raise PdfCompactCanonicalError("pdf_compact_adapter_table_not_accepted", table_ref)
        compatibility = _object(table.get("projection_compatibility"))
        evidence = {
            str(item.get("source_value_ref") or ""): item
            for item in compact_source_evidence(compact_document)
        }
        table_evidence_refs = sorted(
            {
                str(ref)
                for cell in compact_table_cells(table)
                for ref in cell.get("source_value_refs") or []
            }
        )
        private_values: list[dict[str, Any]] = []
        source_value_index: list[dict[str, Any]] = []
        cells: list[dict[str, Any]] = []
        for cell in compact_table_cells(table):
            cell_ref = str(cell.get("cell_ref") or "")
            cell_path = "tablevaluepath_" + stable_digest(
                [table_ref, cell_ref, cell.get("value_checksum_ref")], length=24
            )
            private_values.append(
                {
                    "value_path_ref": cell_path,
                    "normalized_value": cell.get("text"),
                    "value_checksum_ref": cell.get("value_checksum_ref"),
                    "source_value_refs": list(cell.get("source_value_refs") or []),
                }
            )
            mapped_cell = copy.deepcopy(cell)
            mapped_cell.pop("bbox", None)
            flags = set(mapped_cell.pop("flags", []) or [])
            mapped_cell["cell_value_ref"] = "cellval_" + stable_digest(
                [table_ref, cell_ref, cell.get("value_checksum_ref")], length=24
            )
            mapped_cell["normalized_private_value_path"] = cell_path
            mapped_cell["multi_line_cell"] = "multi_line_cell" in flags
            mapped_cell["wrapped_text_cell"] = "wrapped_text_cell" in flags
            mapped_cell["ambiguous_cell_boundary"] = (
                "ambiguous_cell_boundary" in flags
            )
            mapped_cell["split_cell_candidate"] = "split_cell_candidate" in flags
            mapped_cell["merged_cell_group_ref"] = None
            mapped_cell["confidence"] = "high"
            mapped_cell["value_kind_hints"] = []
            mapped_cell["reason_codes"] = []
            mapped_cell.pop("text", None)
            cells.append(mapped_cell)
            for source_value_ref in cell.get("source_value_refs") or []:
                source_value_ref = str(source_value_ref)
                item = evidence.get(source_value_ref)
                if item is None:
                    raise PdfCompactCanonicalError(
                        "pdf_compact_adapter_source_evidence_missing", source_value_ref
                    )
                word_path = "tablewordvaluepath_" + stable_digest(
                    [table_ref, cell_ref, source_value_ref], length=24
                )
                private_values.append(
                    {
                        "value_path_ref": word_path,
                        "normalized_value": item.get("text"),
                        "value_checksum_ref": item.get("value_checksum_ref"),
                        "source_value_refs": [source_value_ref],
                    }
                )
                source_value_index.append(
                    {
                        "source_value_ref": source_value_ref,
                        "source_object_ref": item.get("source_object_ref"),
                        "cell_ref": cell_ref,
                        "value_checksum_ref": item.get("value_checksum_ref"),
                        "value_path": {
                            "kind": "table_projection_private_value",
                            "value_path_ref": word_path,
                        },
                    }
                )

        mapped: dict[str, Any] = {
            "schema_version": self.config.target_schema_version,
            "table_projection_id": table.get("table_projection_id"),
            "table_ref": table_ref,
            "normalization_run_id": compatibility.get("normalization_run_id"),
            "source_document_ref": compatibility.get("source_document_ref"),
            "source_unit_ref": table.get("source_unit_ref"),
            "parent_payload_ref": table.get("parent_payload_ref"),
            "source_format": compatibility.get("source_format"),
            "table_origin": compatibility.get("table_origin"),
            "source_checksum_ref": compatibility.get("source_checksum_ref"),
            "payload_checksum_ref": compatibility.get("payload_checksum_ref"),
            "source_unit_checksum_ref": table.get("source_unit_checksum_ref"),
            "parser_ref": compatibility.get("parser_ref"),
            "parser_engine": compatibility.get("parser_engine"),
            "parser_engine_version": compatibility.get("parser_engine_version"),
            "parser_config_ref": compatibility.get("parser_config_ref"),
            "table_projection_checksum_ref": None,
            "visibility": "private_case",
            "storage_backend": "project_artifact_payload",
            "projection_status": "ready",
            "row_refs": [
                str(item.get("row_ref") or "") for item in compact_table_rows(table)
            ],
            "column_refs": list(table.get("column_refs") or []),
            "cell_refs": [str(item.get("cell_ref") or "") for item in cells],
            "cell_value_refs": [
                str(item.get("cell_value_ref") or "") for item in cells
            ],
            "source_value_refs": table_evidence_refs,
            "row_count": int(table.get("row_count") or 0),
            "column_count": int(table.get("column_count") or 0),
            "cell_count": int(table.get("cell_count") or 0),
            "row_order_policy": "source_order_preserved",
            "column_order_policy": "source_order_preserved",
            "table_bbox_ref": compatibility.get("table_bbox_ref"),
            "page_refs": list(compatibility.get("page_refs") or []),
            "sheet_refs": [],
            "section_refs": list(compatibility.get("section_refs") or []),
            "rows": [
                {
                    **copy.deepcopy(row),
                    "cell_refs": [
                        str(cell.get("cell_ref") or "")
                        for cell in cells
                        if cell.get("row_ref") == row.get("row_ref")
                    ],
                    "reason_codes": [],
                }
                for row in compact_table_rows(table)
            ],
            "cells": cells,
            "private_values": private_values,
            "source_value_index": source_value_index,
            "header_model": copy.deepcopy(table.get("header_model") or {}),
            "coverage": _mapped_coverage(table, evidence),
            "quality": copy.deepcopy(table.get("quality") or {}),
            "geometry": {
                "geometry_confidence": _object(table.get("geometry_summary")).get(
                    "geometry_confidence"
                ),
                "table_strategy_ref": _object(table.get("geometry_summary")).get(
                    "table_strategy_ref"
                ),
                "contributing_word_refs": [
                    evidence[ref].get("source_object_ref") for ref in table_evidence_refs
                ],
                "contributing_line_refs": [],
                "fallback_text_refs": [],
                "fallback_source_value_refs": [],
                "duplicate_ownership_refs": [],
                "unaccounted_ownership_refs": [],
            },
            "table_candidate_status": "validated_geometry",
            "reconstruction_strategy": table.get("reconstruction_strategy"),
            "reconstruction_reason_codes": list(table.get("reason_codes") or []),
            "reconstruction_quality": table.get("reconstruction_quality"),
            "semantic_table_truth_claimed": False,
            "source_facts_extracted": False,
            "tax_meaning_inferred": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
        }
        mapped["table_projection_checksum_ref"] = _projection_checksum(mapped)
        validation = TableProjectionValidator().validate(mapped)
        if not validation["passed"]:
            raise PdfCompactCanonicalError(
                "pdf_compact_adapter_projection_invalid",
                ",".join(item["code"] for item in validation["errors"][:5]),
            )
        return mapped


class PdfCompactGate2MappingValidator:
    def validate(
        self,
        *,
        compact_document: dict[str, Any],
        current_projections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        adapter = PdfCompactGate2AdapterFactory().create()
        current_by_ref = {
            str(item.get("table_ref") or ""): item for item in current_projections
        }
        errors: list[dict[str, str]] = []
        compared = 0
        decisions_compared = 0
        blocked_compared = 0
        for table in _dicts(compact_document.get("tables")):
            table_ref = str(table.get("table_ref") or "")
            current = current_by_ref.get(table_ref)
            if current is None:
                errors.append(_error("pdf_compact_mapping_current_projection_missing", table_ref))
                continue
            decisions_compared += 1
            expected_status = (
                "accepted" if current.get("projection_status") == "ready" else "blocked"
            )
            if table.get("status") != expected_status:
                errors.append(_error("pdf_compact_mapping_decision_status_mismatch", table_ref))
            if table.get("table_projection_id") != current.get("table_projection_id"):
                errors.append(_error("pdf_compact_mapping_table_projection_id_mismatch", table_ref))
            if not set(current.get("reconstruction_reason_codes") or []) <= set(
                table.get("reason_codes") or []
            ):
                errors.append(_error("pdf_compact_mapping_reason_codes_mismatch", table_ref))
            if table.get("status") != "accepted":
                blocked_compared += 1
                if compact_table_rows(table) or compact_table_cells(table):
                    errors.append(_error("pdf_compact_mapping_blocked_grid_invented", table_ref))
                continue
            try:
                mapped = adapter.map_table(
                    compact_document=compact_document, table_ref=table_ref
                )
            except PdfCompactCanonicalError as exc:
                errors.append(_error(exc.code, table_ref))
                continue
            compared += 1
            comparisons = {
                "table_projection_id": mapped.get("table_projection_id")
                == current.get("table_projection_id"),
                "table_ref": mapped.get("table_ref") == current.get("table_ref"),
                "row_refs": mapped.get("row_refs") == current.get("row_refs"),
                "column_refs": mapped.get("column_refs") == current.get("column_refs"),
                "cell_refs": mapped.get("cell_refs") == current.get("cell_refs"),
                "source_value_refs": set(mapped.get("source_value_refs") or [])
                == set(current.get("source_value_refs") or []),
                "empty_cells": [item.get("empty_cell") for item in mapped.get("cells") or []]
                == [item.get("empty_cell") for item in current.get("cells") or []],
                "headers": mapped.get("header_model") == current.get("header_model"),
                "status": mapped.get("projection_status") == current.get("projection_status"),
            }
            for name, passed in comparisons.items():
                if not passed:
                    errors.append(_error(f"pdf_compact_mapping_{name}_mismatch", table_ref))
        return {
            "schema_version": PDF_COMPACT_GATE2_MAPPING_SCHEMA_VERSION,
            "passed": not errors,
            "validator_status": "passed" if not errors else "failed",
            "accepted_tables_compared": compared,
            "blocked_tables_compared": blocked_compared,
            "table_decisions_compared": decisions_compared,
            "status_equivalent": not any(
                item["code"] == "pdf_compact_mapping_decision_status_mismatch"
                for item in errors
            ),
            "errors_count": len(errors),
            "errors": errors,
            "production_gate2_selection_changed": False,
        }


def _projection_checksum(projection: dict[str, Any]) -> str:
    material = copy.deepcopy(projection)
    material.pop("table_projection_checksum_ref", None)
    material.pop("validator_status", None)
    material.pop("validator_reason_codes", None)
    digest = hashlib.sha256(
        json.dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()[:24]
    return f"tableprojchk_{digest}"


def _mapped_coverage(
    table: dict[str, Any], evidence: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    compact = _object(table.get("coverage"))
    source_value_refs = {
        str(ref)
            for cell in compact_table_cells(table)
        for ref in cell.get("source_value_refs") or []
    }
    owned = [
        str(evidence[ref].get("source_object_ref") or "")
        for ref in sorted(source_value_refs)
    ]
    return {
        "schema_version": compact.get("schema_version"),
        "coverage_ref": compact.get("coverage_ref"),
        "selected_source_refs": owned,
        "accounted_source_refs": owned,
        "table_owned_refs": owned,
        "fallback_text_refs": [],
        "non_table_refs": [],
        "rejected_refs": [],
        "duplicate_accounted_refs": [],
        "unaccounted_refs": [],
        "selected_total": len(owned),
        "accounted_total": len(owned),
        "coverage_status": "complete",
        "all_selected_refs_accounted": True,
    }


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}
