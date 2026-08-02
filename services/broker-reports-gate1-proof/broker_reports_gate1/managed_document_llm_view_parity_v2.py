from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from .managed_document_llm_view_audit_v2 import ManagedDocumentLlmViewV2Auditor


MANAGED_CHECKLIST_SCHEMA_VERSION = (
    "broker_reports_managed_document_v2_table_checklist_v1"
)
VIEW_CHECKLIST_SCHEMA_VERSION = "broker_reports_llm_view_v2_table_checklist_v1"
COMPARISON_SCHEMA_VERSION = "broker_reports_doc5_1_table_view_parity_v1"


def build_managed_document_v2_only_checklist(
    managed_document: Mapping[str, Any],
) -> dict[str, Any]:
    document = copy.deepcopy(dict(managed_document))
    if document.get("schema_version") != "broker_reports_managed_document_v2":
        raise ValueError("managed_document_v2_checklist_version_invalid")
    tables = _project_tables(document["blocks"])
    result = {
        "schema_version": MANAGED_CHECKLIST_SCHEMA_VERSION,
        "document_id": document["document_id"],
        "tables": tables,
        "tables_total": len(tables),
        "rows_total": sum(len(item["rows"]) for item in tables),
        "cells_total": sum(
            len(row) for item in tables for row in item["rows"]
        ),
        "spans_total": sum(len(item["cell_spans"]) for item in tables),
        "covered_coordinates_total": _covered_total(tables),
    }
    result["integrity_sha256"] = _canonical_sha256(result)
    return result


def build_llm_view_v2_only_checklist(view: str | bytes) -> dict[str, Any]:
    audited = ManagedDocumentLlmViewV2Auditor().audit(view)
    tables = _project_tables(audited.payload["blocks"])
    result = {
        "schema_version": VIEW_CHECKLIST_SCHEMA_VERSION,
        "document_id": audited.payload["document_id"],
        "view_sha256": audited.view_sha256,
        "tables": tables,
        "tables_total": len(tables),
        "rows_total": sum(len(item["rows"]) for item in tables),
        "cells_total": sum(
            len(row) for item in tables for row in item["rows"]
        ),
        "spans_total": audited.spans_total,
        "covered_coordinates_total": audited.covered_coordinates_total,
    }
    result["integrity_sha256"] = _canonical_sha256(result)
    return result


def compare_managed_document_v2_to_view_v2(
    managed_checklist: Mapping[str, Any],
    view_checklist: Mapping[str, Any],
) -> dict[str, Any]:
    left = copy.deepcopy(dict(managed_checklist))
    right = copy.deepcopy(dict(view_checklist))
    _require_integrity(left, MANAGED_CHECKLIST_SCHEMA_VERSION)
    _require_integrity(right, VIEW_CHECKLIST_SCHEMA_VERSION)
    mismatches: list[dict[str, Any]] = []
    if left["document_id"] != right["document_id"]:
        mismatches.append({"kind": "DOCUMENT_ID", "critical": True})
    if left["tables"] != right["tables"]:
        mismatches.extend(_table_mismatches(left["tables"], right["tables"]))
    for field in (
        "tables_total",
        "rows_total",
        "cells_total",
        "spans_total",
        "covered_coordinates_total",
    ):
        if left[field] != right[field]:
            mismatches.append({"kind": field.upper(), "critical": True})
    result = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "document_id": left["document_id"],
        "input_spans_total": left["spans_total"],
        "rendered_spans_total": right["spans_total"],
        "input_covered_coordinates_total": left["covered_coordinates_total"],
        "rendered_covered_coordinates_total": right[
            "covered_coordinates_total"
        ],
        "span_parity_mismatches_total": sum(
            item["kind"] in {"SPANS", "SPANS_TOTAL", "COVERED_COORDINATES_TOTAL"}
            for item in mismatches
        ),
        "critical_mismatches_total": sum(item["critical"] for item in mismatches),
        "mismatches": mismatches,
        "full_parity": not mismatches,
    }
    result["integrity_sha256"] = _canonical_sha256(result)
    return result


def _project_tables(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for block in blocks:
        if block["block_type"] != "TABLE":
            continue
        content = block["content"]
        result.append(
            {
                "block_id": block["block_id"],
                "ordinal": block["ordinal"],
                "table_id": content["table_id"],
                "rows": copy.deepcopy(content["rows"]),
                "header_hierarchy": copy.deepcopy(content["header_hierarchy"]),
                "row_groups": copy.deepcopy(content["row_groups"]),
                "row_markers": copy.deepcopy(content["row_markers"]),
                "units": copy.deepcopy(content["units"]),
                "cell_annotations": copy.deepcopy(content["cell_annotations"]),
                "cell_spans": copy.deepcopy(content["cell_spans"]),
                "continuation_relation_ids": copy.deepcopy(
                    content["continuation_relation_ids"]
                ),
                "known_gap_ids": copy.deepcopy(content["known_gap_ids"]),
            }
        )
    return result


def _table_mismatches(
    left: list[dict[str, Any]], right: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if [item["table_id"] for item in left] != [item["table_id"] for item in right]:
        return [{"kind": "TABLE_ORDER_OR_PRESENCE", "critical": True}]
    for expected, actual in zip(left, right, strict=True):
        for field in expected:
            if expected[field] != actual.get(field):
                findings.append(
                    {
                        "kind": "SPANS" if field == "cell_spans" else field.upper(),
                        "table_id": expected["table_id"],
                        "critical": True,
                    }
                )
    return findings


def _covered_total(tables: list[dict[str, Any]]) -> int:
    return sum(
        annotation["state"] == "COVERED_BY_SPAN"
        for table in tables
        for annotation in table["cell_annotations"]
    )


def _require_integrity(value: dict[str, Any], schema_version: str) -> None:
    if value.get("schema_version") != schema_version:
        raise ValueError("llm_view_v2_checklist_schema_invalid")
    if value.get("integrity_sha256") != _canonical_sha256(value):
        raise ValueError("llm_view_v2_checklist_integrity_invalid")


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    unsigned = copy.deepcopy(dict(value))
    unsigned.pop("integrity_sha256", None)
    raw = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
