from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from .managed_document_contracts import compute_document_integrity_sha256
from .managed_document_llm_view_audit_v2 import (
    ManagedDocumentLlmViewV2Auditor,
)


ROW_CHECKLIST_SCHEMA_VERSION = (
    "broker_reports_llm_document_view_row_checklist_v2"
)
ROW_PARITY_SCHEMA_VERSION = "broker_reports_llm_document_view_row_parity_v2"

_DIMENSIONS = (
    "DOCUMENT",
    "SOURCE_CONTEXT",
    "METADATA",
    "BLOCK",
    "NON_TABLE_BLOCK_CONTENT",
    "TABLE_IDENTITY",
    "TABLE_ASSOCIATION",
    "SOURCE_PART",
    "COLUMN",
    "HEADER_PATH",
    "ROW",
    "ENTRY",
    "RELATION",
    "QUALITY",
    "ISSUE",
    "LOSS",
    "SOURCE_POINTER",
)

_STANDARD_METADATA_FIELDS = (
    "document_type",
    "title",
    "issuer",
    "document_date",
    "reporting_period",
    "owner_or_account",
    "language",
    "primary_currency",
)

_INVENTORY_FIELDS = (
    ("document_records_total", "DOCUMENT"),
    ("source_context_records_total", "SOURCE_CONTEXT"),
    ("metadata_fields_total", "METADATA"),
    ("blocks_total", "BLOCK"),
    ("non_table_blocks_total", "NON_TABLE_BLOCK_CONTENT"),
    ("tables_total", "TABLE_IDENTITY"),
    ("table_associations_total", "TABLE_ASSOCIATION"),
    ("source_parts_total", "SOURCE_PART"),
    ("columns_total", "COLUMN"),
    ("header_paths_total", "HEADER_PATH"),
    ("rows_total", "ROW"),
    ("entries_total", "ENTRY"),
    ("relations_total", "RELATION"),
    ("quality_records_total", "QUALITY"),
    ("issues_total", "ISSUE"),
    ("losses_total", "LOSS"),
    ("pointer_bindings_total", "SOURCE_POINTER"),
)


def build_managed_document_v2_row_checklist(
    managed_document: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal the row surface of an already validated Managed Document v2."""

    document = copy.deepcopy(dict(managed_document))
    if document.get("schema_version") != "broker_reports_managed_document_v2":
        raise ValueError("llm_view_v2_managed_document_schema_invalid")
    if document.get("integrity_sha256") != compute_document_integrity_sha256(
        document
    ):
        raise ValueError("llm_view_v2_managed_document_integrity_invalid")
    return _build_checklist("MANAGED_DOCUMENT_V2", _managed_dimensions(document))


def build_llm_view_v2_row_checklist(view: str | bytes) -> dict[str, Any]:
    """Independently parse View v2 and seal the same row dimensions."""

    parsed = ManagedDocumentLlmViewV2Auditor().audit(view).payload
    return _build_checklist("LLM_DOCUMENT_VIEW_V2", _view_dimensions(parsed))


def compare_row_checklists(
    managed_checklist: Mapping[str, Any],
    view_checklist: Mapping[str, Any],
) -> dict[str, Any]:
    """Checklist-only Pass C; no renderer or Managed Document read occurs."""

    left = _require_checklist(managed_checklist, "MANAGED_DOCUMENT_V2")
    right = _require_checklist(view_checklist, "LLM_DOCUMENT_VIEW_V2")
    comparisons: list[dict[str, Any]] = []
    critical_categories: set[str] = set()
    for dimension in _DIMENSIONS:
        left_dimension = left["dimensions"][dimension]
        right_dimension = right["dimensions"][dimension]
        match = left_dimension == right_dimension
        categories = (
            []
            if match
            else _diagnose_dimension(
                dimension,
                left_dimension["items"],
                right_dimension["items"],
                left_rows=left["dimensions"]["ROW"]["items"],
                right_rows=right["dimensions"]["ROW"]["items"],
            )
        )
        critical_categories.update(categories)
        comparisons.append(
            {
                "dimension": dimension,
                "status": "MATCH" if match else "MISMATCH",
                "managed_items_total": left_dimension["items_total"],
                "view_items_total": right_dimension["items_total"],
                "managed_sha256": left_dimension["sha256"],
                "view_sha256": right_dimension["sha256"],
                "critical_categories": categories,
            }
        )
    result: dict[str, Any] = {
        "schema_version": ROW_PARITY_SCHEMA_VERSION,
        "managed_checklist_integrity_sha256": left["integrity_sha256"],
        "view_checklist_integrity_sha256": right["integrity_sha256"],
        "comparison_dimensions": comparisons,
        "critical_mismatch_categories": sorted(critical_categories),
        "critical_mismatches_total": len(critical_categories),
        "terminal_status": "PASSED" if not critical_categories else "FAILED",
        "integrity_policy": "sha256_canonical_json_without_integrity_sha256",
    }
    result["integrity_sha256"] = _integrity(result)
    return result


# Compatibility with the established Pass A/B/C naming, version-local only.
build_managed_document_only_checklist = build_managed_document_v2_row_checklist
build_llm_view_only_checklist = build_llm_view_v2_row_checklist
compare_view_checklists = compare_row_checklists


def _managed_dimensions(document: dict[str, Any]) -> dict[str, list[Any]]:
    anchors = {
        item["anchor_id"]: _safe_pointer(item) for item in document["anchors"]
    }
    dimensions = _empty_dimensions()
    quality = document["quality"]
    dimensions["DOCUMENT"].append(
        {
            "content_trust": "UNTRUSTED_SOURCE_DOCUMENT",
            "source_format": document["source"]["format"],
            "source_parts_total": document["source"]["source_part_count"],
            "document_quality_status": quality["status"],
            "known_losses_total": quality["known_losses_total"],
            "blocking_losses_total": quality["blocking_losses_total"],
            "unknown_blocks_total": quality["unknown_blocks_total"],
        }
    )
    dimensions["SOURCE_CONTEXT"].append(
        {
            "mime_type": document["source"]["mime_type"],
            "source_details": copy.deepcopy(
                document["source"]["source_details"]
            ),
        }
    )
    for name, field in _managed_metadata_fields(document["metadata"]):
        dimensions["METADATA"].append(
            {
                "name": name,
                "field": _managed_metadata_field(field, anchors),
            }
        )
    _append_common_pointers_from_managed(dimensions, document, anchors)
    for block in document["blocks"]:
        dimensions["BLOCK"].append(
            {
                "block_id": block["block_id"],
                "ordinal": block["ordinal"],
                "block_type": block["block_type"],
                "restoration": _public_control(block["restoration"]),
                "issue_ids": copy.deepcopy(block["issue_ids"]),
            }
        )
        if block["block_type"] != "TABLE":
            dimensions["NON_TABLE_BLOCK_CONTENT"].append(
                {
                    "block_id": block["block_id"],
                    "block_type": block["block_type"],
                    "content": _project_non_table_content(
                        block["block_type"], block["content"], anchors
                    ),
                }
            )
            continue
        table = block["content"]
        table_id = table["table_id"]
        dimensions["TABLE_IDENTITY"].append(
            {
                "block_id": block["block_id"],
                "block_ordinal": block["ordinal"],
                "table_id": table_id,
                "completeness_status": table["completeness_status"],
            }
        )
        dimensions["TABLE_ASSOCIATION"].append(
            {
                "table_id": table_id,
                "relation_ids": copy.deepcopy(table["relations"]),
                "issue_ids": copy.deepcopy(table["issues"]),
                "known_gap_ids": copy.deepcopy(table["known_gap_ids"]),
            }
        )
        for part in table["source_parts"]:
            dimensions["SOURCE_PART"].append(
                {
                    "table_id": table_id,
                    "source_part_id": part["source_part_id"],
                    "ordinal": part["ordinal"],
                    "page": part["page"],
                    "first_row_id": part["first_row_id"],
                    "last_row_id": part["last_row_id"],
                    "continuation_status": part["continuation_status"],
                    "issue_ids": part["issue_ids"],
                }
            )
        for column in table["logical_columns"]:
            dimensions["COLUMN"].append(
                {
                    "table_id": table_id,
                    "column_id": column["column_id"],
                    "ordinal": column["ordinal"],
                    "issue_ids": column["issue_ids"],
                }
            )
            dimensions["HEADER_PATH"].append(
                {
                    "table_id": table_id,
                    "column_id": column["column_id"],
                    "header_path": column["header_path"],
                }
            )
        for row in table["ordered_rows"]:
            dimensions["ROW"].append(_row_item(table_id, row))
            for entry in row["entries"]:
                dimensions["ENTRY"].append(
                    _entry_item(
                        table_id,
                        row["row_id"],
                        entry,
                        _resolve(entry["source_anchor_ids"], anchors),
                    )
                )
    for relation in document["relations"]:
        dimensions["RELATION"].append(
            _managed_relation(relation, anchors)
        )
    dimensions["QUALITY"].append(_public_quality(quality))
    for issue in quality["issue_ledger"]:
        dimensions["ISSUE"].append(
            _managed_ledger_item(issue, anchors)
        )
    for loss in quality["loss_ledger"]:
        dimensions["LOSS"].append(_managed_ledger_item(loss, anchors))
    return dimensions


def _view_dimensions(view: dict[str, Any]) -> dict[str, list[Any]]:
    dimensions = _empty_dimensions()
    dimensions["DOCUMENT"].append(
        {
            key: copy.deepcopy(view[key])
            for key in (
                "content_trust",
                "source_format",
                "source_parts_total",
                "document_quality_status",
                "known_losses_total",
                "blocking_losses_total",
                "unknown_blocks_total",
            )
        }
    )
    dimensions["SOURCE_CONTEXT"].append(
        copy.deepcopy(view["source_context"])
    )
    dimensions["METADATA"].extend(copy.deepcopy(view["metadata"]))
    _append_common_pointers_from_view(dimensions, view)
    for block in view["blocks"]:
        dimensions["BLOCK"].append(
            {
                key: copy.deepcopy(block[key])
                for key in (
                    "block_id",
                    "ordinal",
                    "block_type",
                    "restoration",
                    "issue_ids",
                )
            }
        )
        if block["block_type"] != "TABLE":
            dimensions["NON_TABLE_BLOCK_CONTENT"].append(
                {
                    "block_id": block["block_id"],
                    "block_type": block["block_type"],
                    "content": copy.deepcopy(block["content"]),
                }
            )
            continue
        table = block["content"]
        table_id = table["table_id"]
        dimensions["TABLE_IDENTITY"].append(
            {
                "block_id": block["block_id"],
                "block_ordinal": block["ordinal"],
                "table_id": table_id,
                "completeness_status": table["completeness_status"],
            }
        )
        dimensions["TABLE_ASSOCIATION"].append(
            {
                "table_id": table_id,
                "relation_ids": copy.deepcopy(table["relations"]),
                "issue_ids": copy.deepcopy(table["issues"]),
                "known_gap_ids": copy.deepcopy(table["known_gap_ids"]),
            }
        )
        for part in table["source_parts"]:
            dimensions["SOURCE_PART"].append(
                {
                    key: copy.deepcopy(part[key])
                    for key in (
                        "source_part_id",
                        "ordinal",
                        "page",
                        "first_row_id",
                        "last_row_id",
                        "continuation_status",
                        "issue_ids",
                    )
                }
                | {"table_id": table_id}
            )
        for column in table["logical_columns"]:
            dimensions["COLUMN"].append(
                {
                    "table_id": table_id,
                    "column_id": column["column_id"],
                    "ordinal": column["ordinal"],
                    "issue_ids": column["issue_ids"],
                }
            )
            dimensions["HEADER_PATH"].append(
                {
                    "table_id": table_id,
                    "column_id": column["column_id"],
                    "header_path": column["header_path"],
                }
            )
        for row in table["ordered_rows"]:
            dimensions["ROW"].append(_row_item(table_id, row))
            for entry in row["entries"]:
                dimensions["ENTRY"].append(
                    _entry_item(
                        table_id,
                        row["row_id"],
                        entry,
                        entry["sources"],
                    )
                )
    dimensions["RELATION"].extend(copy.deepcopy(view["relations"]))
    dimensions["QUALITY"].append(copy.deepcopy(view["quality"]))
    dimensions["ISSUE"].extend(copy.deepcopy(view["issues"]))
    dimensions["LOSS"].extend(copy.deepcopy(view["losses"]))
    return dimensions


def _row_item(table_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "table_id": table_id,
        "row_id": row["row_id"],
        "ordinal": row["ordinal"],
        "role": row["role"],
        "role_origin": row["role_origin"],
        "nesting_level": row["nesting_level"],
        "parent_row_id": row["parent_row_id"],
        "issue_ids": copy.deepcopy(row["issue_ids"]),
    }


def _entry_item(
    table_id: str,
    row_id: str,
    entry: Mapping[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "table_id": table_id,
        "row_id": row_id,
        "entry_id": entry["entry_id"],
        "ordinal": entry["ordinal"],
        "kind": entry["kind"],
        "text": entry["text"],
        "origin": entry["origin"],
        "column_binding_status": entry["column_binding_status"],
        "logical_column_id": entry["logical_column_id"],
        "covers_logical_column_ids": copy.deepcopy(
            entry["covers_logical_column_ids"]
        ),
        "sources": copy.deepcopy(sources),
        "issue_ids": copy.deepcopy(entry["issue_ids"]),
    }


def _managed_metadata_fields(
    metadata: Mapping[str, Any],
) -> list[tuple[str, Mapping[str, Any]]]:
    fields = [(name, metadata[name]) for name in _STANDARD_METADATA_FIELDS]
    fields.extend((item["name"], item) for item in metadata["additional"])
    return fields


def _managed_metadata_field(
    field: Mapping[str, Any],
    anchors: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": field["status"],
        "origin": field["origin"],
        "value": copy.deepcopy(field["value"]),
        "candidates": copy.deepcopy(field["candidates"]),
        "sources": _resolve(field["evidence_anchor_ids"], anchors),
    }


def _public_control(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "information_class"
    }


def _project_non_table_content(
    block_type: str,
    raw_content: Mapping[str, Any],
    anchors: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    content = copy.deepcopy(dict(raw_content))
    content.pop("information_class", None)
    if block_type in {"VISUAL", "UNKNOWN"}:
        private = content.pop("private_artifact")
        content["private_source_available"] = private["status"] == "PRESENT"
    if block_type == "VISUAL":
        content["caption"] = _managed_metadata_field(
            content["caption"], anchors
        )
        content["safe_description"] = _managed_metadata_field(
            content["safe_description"], anchors
        )
    elif block_type == "BOUNDARY":
        content["label"] = _managed_metadata_field(content["label"], anchors)
    return content


def _managed_relation(
    relation: Mapping[str, Any],
    anchors: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "relation_id": relation["relation_id"],
        "relation_type": relation["relation_type"],
        "source": copy.deepcopy(relation["source"]),
        "target": copy.deepcopy(relation["target"]),
        "status": relation["status"],
        "origin": relation["origin"],
        "sources": _resolve(relation["evidence_anchor_ids"], anchors),
        "issue_ids": copy.deepcopy(relation["issue_ids"]),
    }


def _public_quality(quality: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in quality.items()
        if key not in {"information_class", "issue_ledger", "loss_ledger"}
    }


def _managed_ledger_item(
    item: Mapping[str, Any],
    anchors: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in item.items()
        if key != "anchor_ids"
    } | {"sources": _resolve(item["anchor_ids"], anchors)}


def _append_common_pointers_from_managed(
    dimensions: dict[str, list[Any]],
    document: dict[str, Any],
    anchors: dict[str, dict[str, Any]],
) -> None:
    pointers = dimensions["SOURCE_POINTER"]
    for anchor in document["anchors"]:
        _pointer_binding(
            pointers,
            "ANCHOR",
            anchor["anchor_id"],
            [anchors[anchor["anchor_id"]]],
        )
    for name, field in _managed_metadata_fields(document["metadata"]):
        _pointer_binding(
            pointers,
            "METADATA",
            name,
            _resolve(field["evidence_anchor_ids"], anchors),
        )
    for block in document["blocks"]:
        block_id = block["block_id"]
        _pointer_binding(
            pointers,
            "BLOCK",
            block_id,
            _resolve(block["source_anchor_ids"], anchors),
        )
        if block["block_type"] != "TABLE":
            continue
        table = block["content"]
        for part in table["source_parts"]:
            _pointer_binding(
                pointers,
                "SOURCE_PART",
                part["source_part_id"],
                [anchors[part["region_anchor_id"]]],
            )
        for column in table["logical_columns"]:
            _pointer_binding(
                pointers,
                "COLUMN",
                column["column_id"],
                _resolve(column["source_anchor_ids"], anchors),
            )
        for row in table["ordered_rows"]:
            _pointer_binding(
                pointers,
                "ROW",
                row["row_id"],
                _resolve(row["source_anchor_ids"], anchors),
            )
            for entry in row["entries"]:
                _pointer_binding(
                    pointers,
                    "ENTRY",
                    entry["entry_id"],
                    _resolve(entry["source_anchor_ids"], anchors),
                )
    for relation in document["relations"]:
        _pointer_binding(
            pointers,
            "RELATION",
            relation["relation_id"],
            _resolve(relation["evidence_anchor_ids"], anchors),
        )
    for issue in document["quality"]["issue_ledger"]:
        _pointer_binding(
            pointers,
            "ISSUE",
            issue["issue_id"],
            _resolve(issue["anchor_ids"], anchors),
        )
    for loss in document["quality"]["loss_ledger"]:
        _pointer_binding(
            pointers,
            "LOSS",
            loss["loss_id"],
            _resolve(loss["anchor_ids"], anchors),
        )


def _append_common_pointers_from_view(
    dimensions: dict[str, list[Any]], view: dict[str, Any]
) -> None:
    pointers = dimensions["SOURCE_POINTER"]
    for anchor in view["anchors"]:
        _pointer_binding(
            pointers, "ANCHOR", anchor["anchor_id"], [anchor]
        )
    for metadata in view["metadata"]:
        _pointer_binding(
            pointers,
            "METADATA",
            metadata["name"],
            metadata["field"]["sources"],
        )
    for block in view["blocks"]:
        _pointer_binding(
            pointers, "BLOCK", block["block_id"], block["sources"]
        )
        if block["block_type"] != "TABLE":
            continue
        table = block["content"]
        for part in table["source_parts"]:
            _pointer_binding(
                pointers, "SOURCE_PART", part["source_part_id"], part["sources"]
            )
        for column in table["logical_columns"]:
            _pointer_binding(
                pointers, "COLUMN", column["column_id"], column["sources"]
            )
        for row in table["ordered_rows"]:
            _pointer_binding(pointers, "ROW", row["row_id"], row["sources"])
            for entry in row["entries"]:
                _pointer_binding(
                    pointers, "ENTRY", entry["entry_id"], entry["sources"]
                )
    for relation in view["relations"]:
        _pointer_binding(
            pointers, "RELATION", relation["relation_id"], relation["sources"]
        )
    for issue in view["issues"]:
        _pointer_binding(
            pointers, "ISSUE", issue["issue_id"], issue["sources"]
        )
    for loss in view["losses"]:
        _pointer_binding(pointers, "LOSS", loss["loss_id"], loss["sources"])


def _pointer_binding(
    target: list[Any], owner_type: str, owner_id: str, sources: list[Any]
) -> None:
    target.append(
        {
            "owner_type": owner_type,
            "owner_id": owner_id,
            "sources": copy.deepcopy(sources),
        }
    )


def _build_checklist(
    pass_name: str, dimensions: dict[str, list[Any]]
) -> dict[str, Any]:
    sealed_dimensions = {
        name: {
            "items_total": len(dimensions[name]),
            "items": dimensions[name],
            "sha256": _hash(dimensions[name]),
        }
        for name in _DIMENSIONS
    }
    checklist: dict[str, Any] = {
        "schema_version": ROW_CHECKLIST_SCHEMA_VERSION,
        "pass": pass_name,
        "terminal_status": "PASSED",
        "dimensions": sealed_dimensions,
        "inventory": {
            name: len(dimensions[dimension])
            for name, dimension in _INVENTORY_FIELDS
        },
        "integrity_policy": "sha256_canonical_json_without_integrity_sha256",
    }
    checklist["integrity_sha256"] = _integrity(checklist)
    return checklist


def _require_checklist(
    value: Mapping[str, Any], expected_pass: str
) -> dict[str, Any]:
    checklist = copy.deepcopy(dict(value))
    if (
        checklist.get("schema_version") != ROW_CHECKLIST_SCHEMA_VERSION
        or checklist.get("pass") != expected_pass
        or checklist.get("terminal_status") != "PASSED"
        or set(checklist.get("dimensions", {})) != set(_DIMENSIONS)
        or checklist.get("integrity_sha256") != _integrity(checklist)
    ):
        raise ValueError("llm_view_v2_row_checklist_invalid")
    for name in _DIMENSIONS:
        dimension = checklist["dimensions"].get(name)
        if (
            not isinstance(dimension, dict)
            or set(dimension) != {"items_total", "items", "sha256"}
            or not isinstance(dimension["items"], list)
            or dimension["items_total"] != len(dimension["items"])
            or dimension["sha256"] != _hash(dimension["items"])
        ):
            raise ValueError("llm_view_v2_row_checklist_invalid")
    expected_inventory = {
        name: checklist["dimensions"][dimension]["items_total"]
        for name, dimension in _INVENTORY_FIELDS
    }
    if checklist.get("inventory") != expected_inventory:
        raise ValueError("llm_view_v2_row_checklist_invalid")
    return checklist


def _diagnose_dimension(
    dimension: str,
    left: list[Any],
    right: list[Any],
    *,
    left_rows: list[Any],
    right_rows: list[Any],
) -> list[str]:
    if dimension == "TABLE_IDENTITY":
        return _diagnose_table_identity(left, right)
    if dimension == "TABLE_ASSOCIATION":
        return _diagnose_table_associations(left, right)
    if dimension == "BLOCK":
        return _diagnose_blocks(left, right)
    if dimension == "NON_TABLE_BLOCK_CONTENT":
        return _diagnose_non_table_content(left, right)
    if dimension == "ROW":
        return _diagnose_rows(left, right)
    if dimension == "ENTRY":
        return _diagnose_entries(left, right, left_rows, right_rows)
    if dimension == "RELATION":
        return _diagnose_relations(left, right)
    if dimension == "HEADER_PATH":
        return ["WRONG_HEADER_BINDING"]
    if dimension == "SOURCE_POINTER":
        return ["WRONG_SOURCE_POINTER"]
    if dimension == "SOURCE_PART":
        return _diagnose_source_parts(left, right)
    if dimension == "COLUMN":
        return ["WRONG_ENTRY_COLUMN_BINDING"]
    return {
        "DOCUMENT": ["WRONG_DOCUMENT_CONTROL"],
        "SOURCE_CONTEXT": ["WRONG_SOURCE_CONTEXT"],
        "METADATA": ["WRONG_METADATA"],
        "QUALITY": ["WRONG_QUALITY"],
        "ISSUE": ["WRONG_ISSUE"],
        "LOSS": ["WRONG_LOSS"],
    }.get(dimension, [f"WRONG_{dimension}"])


def _diagnose_table_identity(
    left: list[Any], right: list[Any]
) -> list[str]:
    categories: set[str] = set()
    left_by_id = {item["table_id"]: item for item in left}
    right_by_id = {item["table_id"]: item for item in right}
    if set(left_by_id) - set(right_by_id):
        categories.add("FALSE_TABLE_MERGE")
    if set(right_by_id) - set(left_by_id):
        categories.add("FALSE_TABLE_SPLIT")
    if [item["table_id"] for item in left] != [
        item["table_id"] for item in right
    ]:
        categories.add("WRONG_TABLE_ORDER")
    for table_id in set(left_by_id) & set(right_by_id):
        if left_by_id[table_id] != right_by_id[table_id]:
            categories.add("WRONG_TABLE_IDENTITY")
    return sorted(categories or {"WRONG_TABLE_IDENTITY"})


def _diagnose_table_associations(
    left: list[Any], right: list[Any]
) -> list[str]:
    categories: set[str] = set()
    left_by_id = {item["table_id"]: item for item in left}
    right_by_id = {item["table_id"]: item for item in right}
    if set(left_by_id) - set(right_by_id):
        categories.add("FALSE_TABLE_MERGE")
    if set(right_by_id) - set(left_by_id):
        categories.add("FALSE_TABLE_SPLIT")
    for table_id in set(left_by_id) & set(right_by_id):
        managed = left_by_id[table_id]
        view = right_by_id[table_id]
        if managed["relation_ids"] != view["relation_ids"]:
            categories.add("WRONG_TABLE_RELATION_BINDING")
        if managed["issue_ids"] != view["issue_ids"]:
            categories.add("WRONG_TABLE_ISSUE_BINDING")
        if managed["known_gap_ids"] != view["known_gap_ids"]:
            categories.add("WRONG_TABLE_GAP_BINDING")
    return sorted(categories or {"WRONG_TABLE_ASSOCIATION"})


def _diagnose_blocks(left: list[Any], right: list[Any]) -> list[str]:
    categories: set[str] = set()
    left_by_id = {item["block_id"]: item for item in left}
    right_by_id = {item["block_id"]: item for item in right}
    if set(left_by_id) - set(right_by_id):
        categories.add("MISSING_BLOCK")
    if set(right_by_id) - set(left_by_id):
        categories.add("EXTRA_BLOCK")
    if [item["block_id"] for item in left] != [
        item["block_id"] for item in right
    ]:
        categories.add("WRONG_BLOCK_ORDER")
    for block_id in set(left_by_id) & set(right_by_id):
        managed = left_by_id[block_id]
        view = right_by_id[block_id]
        if managed["block_type"] != view["block_type"]:
            categories.add("WRONG_BLOCK_TYPE")
        if managed["restoration"] != view["restoration"]:
            categories.add("WRONG_RESTORATION")
        if managed["issue_ids"] != view["issue_ids"]:
            categories.add("WRONG_BLOCK_ISSUE_BINDING")
        if managed["ordinal"] != view["ordinal"]:
            categories.add("WRONG_BLOCK_ORDER")
    return sorted(categories or {"WRONG_BLOCK"})


def _diagnose_non_table_content(
    left: list[Any], right: list[Any]
) -> list[str]:
    categories: set[str] = set()
    left_by_id = {item["block_id"]: item for item in left}
    right_by_id = {item["block_id"]: item for item in right}
    if set(left_by_id) - set(right_by_id):
        categories.add("MISSING_NON_TABLE_BLOCK_CONTENT")
    if set(right_by_id) - set(left_by_id):
        categories.add("EXTRA_NON_TABLE_BLOCK_CONTENT")
    if any(
        left_by_id[block_id] != right_by_id[block_id]
        for block_id in set(left_by_id) & set(right_by_id)
    ):
        categories.add("WRONG_NON_TABLE_BLOCK_CONTENT")
    return sorted(categories or {"WRONG_NON_TABLE_BLOCK_CONTENT"})


def _diagnose_source_parts(
    left: list[Any], right: list[Any]
) -> list[str]:
    categories: set[str] = set()
    left_by_id = {item["source_part_id"]: item for item in left}
    right_by_id = {item["source_part_id"]: item for item in right}
    if set(left_by_id) - set(right_by_id):
        categories.add("MISSING_CONTINUATION")
    if set(right_by_id) - set(left_by_id):
        categories.add("FALSE_CONTINUATION")
    if [item["source_part_id"] for item in left] != [
        item["source_part_id"] for item in right
    ]:
        categories.add("WRONG_TABLE_BOUNDARY")
    boundary_keys = (
        "table_id",
        "ordinal",
        "page",
        "first_row_id",
        "last_row_id",
    )
    for part_id in set(left_by_id) & set(right_by_id):
        managed = left_by_id[part_id]
        view = right_by_id[part_id]
        if any(managed[key] != view[key] for key in boundary_keys):
            categories.add("WRONG_TABLE_BOUNDARY")
        if managed["issue_ids"] != view["issue_ids"]:
            categories.add("WRONG_SOURCE_PART_ISSUE_BINDING")
        expected_status = managed["continuation_status"]
        actual_status = view["continuation_status"]
        if expected_status != actual_status:
            if expected_status != "SINGLE":
                categories.add("MISSING_CONTINUATION")
            if actual_status != "SINGLE":
                categories.add("FALSE_CONTINUATION")
    return sorted(categories or {"WRONG_TABLE_BOUNDARY"})


def _diagnose_rows(left: list[Any], right: list[Any]) -> list[str]:
    categories: set[str] = set()
    left_by_id = {item["row_id"]: item for item in left}
    right_by_id = {item["row_id"]: item for item in right}
    missing_ids = set(left_by_id) - set(right_by_id)
    extra_ids = set(right_by_id) - set(left_by_id)
    if missing_ids:
        categories.add("MISSING_LOGICAL_ROW")
        for row_id in missing_ids:
            _add_summary_binding_category(
                categories, left_by_id[row_id]["role"]
            )
    if extra_ids:
        categories.add("EXTRA_LOGICAL_ROW")
        for row_id in extra_ids:
            _add_summary_binding_category(
                categories, right_by_id[row_id]["role"]
            )
    if [item["row_id"] for item in left] != [item["row_id"] for item in right]:
        categories.add("WRONG_ROW_ORDER")
    for row_id in set(left_by_id) & set(right_by_id):
        managed = left_by_id[row_id]
        view = right_by_id[row_id]
        if managed["table_id"] != view["table_id"]:
            categories.add("WRONG_ROW_TABLE_BINDING")
        if managed["ordinal"] != view["ordinal"]:
            categories.add("WRONG_ROW_ORDER")
        if managed["role"] != view["role"]:
            categories.add("WRONG_ROW_ROLE")
        if managed["parent_row_id"] != view["parent_row_id"]:
            categories.add("WRONG_ROW_PARENT")
        if managed["nesting_level"] != view["nesting_level"]:
            categories.add("WRONG_NESTING_LEVEL")
        if any(
            managed[key] != view[key]
            for key in ("role_origin", "issue_ids")
        ):
            categories.add("WRONG_LOGICAL_ROW")
        if any(
            managed[key] != view[key]
            for key in (
                "table_id",
                "role",
                "parent_row_id",
                "nesting_level",
            )
        ):
            _add_summary_binding_category(categories, managed["role"])
            _add_summary_binding_category(categories, view["role"])
    return sorted(categories or {"WRONG_LOGICAL_ROW"})


def _add_summary_binding_category(
    categories: set[str], role: str
) -> None:
    if role == "SUBTOTAL":
        categories.add("WRONG_SUBTOTAL_BINDING")
    elif role == "TOTAL":
        categories.add("WRONG_TOTAL_BINDING")


def _diagnose_entries(
    left: list[Any],
    right: list[Any],
    left_rows: list[Any],
    right_rows: list[Any],
) -> list[str]:
    categories: set[str] = set()
    left_by_id = {item["entry_id"]: item for item in left}
    right_by_id = {item["entry_id"]: item for item in right}
    left_row_roles = {item["row_id"]: item["role"] for item in left_rows}
    right_row_roles = {item["row_id"]: item["role"] for item in right_rows}
    missing_ids = set(left_by_id) - set(right_by_id)
    extra_ids = set(right_by_id) - set(left_by_id)
    if missing_ids:
        categories.add("DROPPED_SOURCE_VALUE")
    left_values = Counter(_source_value_key(item) for item in left)
    right_values = Counter(_source_value_key(item) for item in right)
    if any(
        right_count > left_values[value_key]
        and left_values[value_key] > 0
        for value_key, right_count in right_values.items()
    ):
        categories.add("DUPLICATED_SOURCE_VALUE")
    if any(
        _source_value_key(right_by_id[entry_id]) not in left_values
        for entry_id in extra_ids
    ):
        categories.add("INVENTED_SOURCE_VALUE")
    if [item["entry_id"] for item in left] != [
        item["entry_id"] for item in right
    ]:
        categories.add("WRONG_ENTRY_ORDER")
    for entry_id in set(left_by_id) & set(right_by_id):
        managed = left_by_id[entry_id]
        view = right_by_id[entry_id]
        if managed["table_id"] != view["table_id"]:
            categories.add("WRONG_ENTRY_ROW_BINDING")
        if managed["row_id"] != view["row_id"]:
            categories.add("WRONG_ENTRY_ROW_BINDING")
        if managed["ordinal"] != view["ordinal"]:
            categories.add("WRONG_ENTRY_ORDER")
        if managed["text"] != view["text"] or managed["kind"] != view["kind"]:
            categories.add("WRONG_ENTRY_VALUE")
        if any(
            managed[key] != view[key]
            for key in (
                "column_binding_status",
                "logical_column_id",
                "covers_logical_column_ids",
            )
        ):
            categories.add("WRONG_ENTRY_COLUMN_BINDING")
            for item, row_roles in (
                (managed, left_row_roles),
                (view, right_row_roles),
            ):
                role = row_roles.get(item["row_id"])
                if role is not None:
                    _add_summary_binding_category(categories, role)
        if managed["sources"] != view["sources"]:
            categories.add("WRONG_SOURCE_POINTER")
        if any(
            managed[key] != view[key] for key in ("origin", "issue_ids")
        ):
            categories.add("WRONG_LOGICAL_ENTRY")
    return sorted(categories or {"WRONG_LOGICAL_ENTRY"})


def _source_value_key(item: Mapping[str, Any]) -> str:
    return _hash([item["text"], item["sources"]])


def _diagnose_relations(left: list[Any], right: list[Any]) -> list[str]:
    categories: set[str] = set()
    left_by_id = {item["relation_id"]: item for item in left}
    right_by_id = {item["relation_id"]: item for item in right}
    if set(left_by_id) - set(right_by_id):
        categories.add("DROPPED_RELATION")
    if set(right_by_id) - set(left_by_id):
        categories.add("INVENTED_RELATION")
    if [item["relation_id"] for item in left] != [
        item["relation_id"] for item in right
    ]:
        categories.add("WRONG_RELATION_ORDER")
    for relation_id in set(left_by_id) & set(right_by_id):
        managed = left_by_id[relation_id]
        view = right_by_id[relation_id]
        if any(managed[key] != view[key] for key in ("source", "target")):
            categories.add("WRONG_RELATION_ENDPOINT")
        if managed["status"] != view["status"]:
            categories.add("WRONG_RELATION_STATUS")
        if any(
            managed[key] != view[key]
            for key in (
                "relation_type",
                "origin",
                "sources",
                "issue_ids",
            )
        ):
            categories.add("WRONG_RELATION")
    return sorted(categories or {"WRONG_RELATION"})


def _empty_dimensions() -> dict[str, list[Any]]:
    return {name: [] for name in _DIMENSIONS}


def _resolve(
    anchor_ids: list[str], anchors: Mapping[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    return [copy.deepcopy(anchors[anchor_id]) for anchor_id in anchor_ids]


def _safe_pointer(anchor: Mapping[str, Any]) -> dict[str, Any]:
    locator = anchor["locator"]
    pointer: dict[str, Any] = {
        "anchor_id": anchor["anchor_id"],
        "format": anchor["source_format"],
        "source_part_index": locator["source_part_index"],
    }
    for key in (
        "page",
        "row_start",
        "row_end",
        "column_start",
        "column_end",
        "ordinal",
    ):
        if locator.get(key) is not None:
            pointer[key] = locator[key]
    return pointer


def _integrity(value: Mapping[str, Any]) -> str:
    unsigned = copy.deepcopy(dict(value))
    unsigned.pop("integrity_sha256", None)
    return _hash(unsigned)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
