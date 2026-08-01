from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from .managed_document_llm_view_audit import (
    CHECKLIST_SCHEMA_VERSION,
    ManagedDocumentLlmViewAuditor,
)


VIEW_PARITY_SCHEMA_VERSION = "broker_reports_llm_document_view_parity_v1"
_DIMENSIONS = (
    "DOCUMENT_PASSPORT",
    "METADATA",
    "ANCHORS",
    "BLOCK_ORDER",
    "BLOCK_CONTENT",
    "TABLES",
    "UNKNOWNS",
    "VISUALS",
    "RELATIONS",
    "ISSUES",
    "LOSSES",
    "VALUE_HASHES",
    "QUALITY",
)


def build_managed_document_only_checklist(
    managed_document: Mapping[str, Any],
) -> dict[str, Any]:
    """PASS A: inspect only a validated Managed Document value."""

    document = copy.deepcopy(dict(managed_document))
    if document.get("schema_version") != "broker_reports_managed_document_v1":
        raise ValueError("llm_view_managed_checklist_input_invalid")
    projection = _project_managed_document(document)
    return _seal_checklist(
        {
            "schema_version": CHECKLIST_SCHEMA_VERSION,
            "pass": "MANAGED_DOCUMENT_ONLY",
            "document_id": document["document_id"],
            "terminal_status": "PASSED",
            "source_artifact_sha256": hashlib.sha256(
                _canonical_bytes(document)
            ).hexdigest(),
            "content": projection,
            "inventory": _content_inventory(projection),
            "value_hashes": _value_hashes(projection),
            "integrity_policy": "sha256_canonical_json_without_integrity_sha256",
        }
    )


def build_llm_view_only_checklist(view: str | bytes) -> dict[str, Any]:
    """PASS B: inspect only the canonical text view through the auditor."""

    audited = ManagedDocumentLlmViewAuditor().audit(view)
    projection = copy.deepcopy(audited.payload)
    return _seal_checklist(
        {
            "schema_version": CHECKLIST_SCHEMA_VERSION,
            "pass": "LLM_VIEW_ONLY",
            "document_id": projection["document_id"],
            "terminal_status": "PASSED",
            "source_artifact_sha256": audited.view_sha256,
            "content": projection,
            "inventory": _content_inventory(projection),
            "value_hashes": _value_hashes(projection),
            "integrity_policy": "sha256_canonical_json_without_integrity_sha256",
        }
    )


def compare_view_checklists(
    managed_checklist: Mapping[str, Any],
    view_checklist: Mapping[str, Any],
) -> dict[str, Any]:
    """PASS C: compare only two integrity-sealed checklists."""

    left = _require_checklist(managed_checklist, "MANAGED_DOCUMENT_ONLY")
    right = _require_checklist(view_checklist, "LLM_VIEW_ONLY")
    if left["document_id"] != right["document_id"]:
        raise ValueError("llm_view_checklist_document_id_mismatch")

    left_content = left["content"]
    right_content = right["content"]
    comparisons = [
        _comparison("DOCUMENT_PASSPORT", _passport(left_content), _passport(right_content)),
        _comparison("METADATA", left_content["metadata"], right_content["metadata"]),
        _comparison("ANCHORS", left_content["anchors"], right_content["anchors"]),
        _comparison(
            "BLOCK_ORDER", _block_order(left_content), _block_order(right_content)
        ),
        _comparison("BLOCK_CONTENT", left_content["blocks"], right_content["blocks"]),
        _comparison("TABLES", _blocks(left_content, "TABLE"), _blocks(right_content, "TABLE")),
        _comparison(
            "UNKNOWNS", _blocks(left_content, "UNKNOWN"), _blocks(right_content, "UNKNOWN")
        ),
        _comparison("VISUALS", _blocks(left_content, "VISUAL"), _blocks(right_content, "VISUAL")),
        _comparison("RELATIONS", left_content["relations"], right_content["relations"]),
        _comparison("ISSUES", left_content["issues"], right_content["issues"]),
        _comparison("LOSSES", left_content["losses"], right_content["losses"]),
        _comparison("VALUE_HASHES", left["value_hashes"], right["value_hashes"]),
        _comparison("QUALITY", left_content["quality"], right_content["quality"]),
    ]
    if tuple(item["dimension"] for item in comparisons) != _DIMENSIONS:
        raise ValueError("llm_view_parity_dimensions_invalid")
    critical = [item for item in comparisons if item["status"] != "MATCH"]
    comparison: dict[str, Any] = {
        "schema_version": VIEW_PARITY_SCHEMA_VERSION,
        "document_id": left["document_id"],
        "managed_checklist_integrity_sha256": left["integrity_sha256"],
        "view_checklist_integrity_sha256": right["integrity_sha256"],
        "comparisons": comparisons,
        "critical_mismatches_total": len(critical),
        "noncritical_findings_total": 0,
        "full_parity": not critical,
        "critical_categories": [
            _critical_category(item["dimension"], item["status"])
            for item in critical
        ],
        "integrity_policy": "sha256_canonical_json_without_integrity_sha256",
    }
    comparison["integrity_sha256"] = _integrity(comparison)
    return comparison


def _project_managed_document(document: dict[str, Any]) -> dict[str, Any]:
    anchors = {item["anchor_id"]: _safe_pointer(item) for item in document["anchors"]}
    metadata = [
        {"name": name, "field": _project_metadata(field, anchors)}
        for name, field in document["metadata"].items()
        if name != "additional"
    ]
    metadata.extend(
        {"name": item["name"], "field": _project_metadata(item, anchors)}
        for item in document["metadata"]["additional"]
    )
    blocks = [_project_block(item, anchors) for item in document["blocks"]]
    relations = [
        {
            "relation_id": item["relation_id"],
            "type": item["relation_type"],
            "status": item["status"],
            "origin": item["origin"],
            "source": item["source"],
            "target": item["target"],
            "evidence": [anchors[value] for value in item["evidence_anchor_ids"]],
            "issue_ids": item["issue_ids"],
        }
        for item in document["relations"]
    ]
    issues = [
        {
            "issue_id": item["issue_id"],
            "code": item["code"],
            "severity": item["severity"],
            "message": item["message"],
            "sources": [anchors[value] for value in item["anchor_ids"]],
            "block_ids": item["block_ids"],
            "relation_ids": item["relation_ids"],
            "recoverability": item["recoverability"],
            "requires_source_reread": item["requires_source_reread"],
        }
        for item in document["quality"]["issue_ledger"]
    ]
    losses = [
        {
            "loss_id": item["loss_id"],
            "context_class": item["context_class"],
            "what_lost": item["what_lost"],
            "where": item["where"],
            "reason": item["reason"],
            "recoverability": item["recoverability"],
            "requires_source_reread": item["requires_source_reread"],
            "blocks_semantic_analysis": item["blocks_semantic_analysis"],
            "accounted": item["accounted"],
            "sources": [anchors[value] for value in item["anchor_ids"]],
            "block_ids": item["block_ids"],
        }
        for item in document["quality"]["loss_ledger"]
    ]
    quality = {
        key: value
        for key, value in document["quality"].items()
        if key not in {"information_class", "issue_ledger", "loss_ledger"}
    }
    return {
        "schema_version": "broker_reports_llm_document_view_v1",
        "content_trust": "UNTRUSTED_SOURCE_DOCUMENT",
        "document_id": document["document_id"],
        "source_format": document["source"]["format"],
        "source_parts_total": document["source"]["source_part_count"],
        "document_quality_status": document["quality"]["status"],
        "known_losses_total": document["quality"]["known_losses_total"],
        "blocking_losses_total": document["quality"]["blocking_losses_total"],
        "unknown_blocks_total": document["quality"]["unknown_blocks_total"],
        "source_context": {
            "mime_type": document["source"]["mime_type"],
            "source_details": document["source"]["source_details"],
        },
        "metadata": metadata,
        "anchors": [anchors[item["anchor_id"]] for item in document["anchors"]],
        "blocks": blocks,
        "relations": relations,
        "quality": quality,
        "issues": issues,
        "losses": losses,
    }


def _project_metadata(
    field: Mapping[str, Any], anchors: Mapping[str, dict[str, Any]]
) -> dict[str, Any]:
    return {
        "status": field["status"],
        "origin": field["origin"],
        "value": field["value"],
        "candidates": field["candidates"],
        "sources": [anchors[item] for item in field["evidence_anchor_ids"]],
    }


def _project_block(
    block: Mapping[str, Any], anchors: Mapping[str, dict[str, Any]]
) -> dict[str, Any]:
    content = copy.deepcopy(dict(block["content"]))
    content.pop("information_class", None)
    if block["block_type"] in {"VISUAL", "UNKNOWN"}:
        private = content.pop("private_artifact")
        content["private_source_available"] = private["status"] == "PRESENT"
    if block["block_type"] == "VISUAL":
        content["caption"] = _project_metadata(content["caption"], anchors)
        content["safe_description"] = _project_metadata(content["safe_description"], anchors)
    if block["block_type"] == "BOUNDARY":
        content["label"] = _project_metadata(content["label"], anchors)
    if block["block_type"] == "TABLE":
        content["title"] = _project_metadata(content["title"], anchors)
    return {
        "block_id": block["block_id"],
        "ordinal": block["ordinal"],
        "block_type": block["block_type"],
        "sources": [anchors[item] for item in block["source_anchor_ids"]],
        "restoration": {
            key: value
            for key, value in block["restoration"].items()
            if key != "information_class"
        },
        "issue_ids": block["issue_ids"],
        "content": content,
    }


def _safe_pointer(anchor: Mapping[str, Any]) -> dict[str, Any]:
    locator = anchor["locator"]
    result: dict[str, Any] = {
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
            result[key] = locator[key]
    return result


def _content_inventory(content: dict[str, Any]) -> dict[str, Any]:
    block_counts = Counter(item["block_type"] for item in content["blocks"])
    tables = _blocks(content, "TABLE")
    return {
        "metadata_total": len(content["metadata"]),
        "anchors_total": len(content["anchors"]),
        "blocks_total": len(content["blocks"]),
        "block_types": dict(sorted(block_counts.items())),
        "tables_total": len(tables),
        "table_rows_total": sum(len(item["content"]["rows"]) for item in tables),
        "table_cells_total": sum(
            len(row) for item in tables for row in item["content"]["rows"]
        ),
        "unknown_blocks_total": block_counts["UNKNOWN"],
        "visual_blocks_total": block_counts["VISUAL"],
        "relations_total": len(content["relations"]),
        "issues_total": len(content["issues"]),
        "losses_total": len(content["losses"]),
        "full_content_sha256": _hash(content),
    }


def _value_hashes(content: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, str]] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key in sorted(value):
                visit(value[key], f"{path}/{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}/{index}")
        elif isinstance(value, (str, int, float, bool)) or value is None:
            entries.append({"path": path, "value_sha256": _hash(value)})
        else:  # pragma: no cover - JSON contract closes scalar types.
            raise ValueError("llm_view_checklist_value_type_invalid")

    visit(content, "")
    return {
        "entries_total": len(entries),
        "entries": entries,
        "ordered_values_sha256": _hash(entries),
        "unordered_values_sha256": _hash(
            sorted(item["value_sha256"] for item in entries)
        ),
    }


def _comparison(dimension: str, left: Any, right: Any) -> dict[str, Any]:
    if left == right:
        status = "MATCH"
    elif dimension == "BLOCK_ORDER":
        left_ids = [item["block_id"] for item in left]
        right_ids = [item["block_id"] for item in right]
        if sorted(left_ids) == sorted(right_ids):
            status = "WRONG_ORDER"
        elif len(left_ids) > len(right_ids):
            status = "MISSING_IN_VIEW"
        elif len(left_ids) < len(right_ids):
            status = "EXTRA_IN_VIEW"
        else:
            status = "WRONG_VALUE"
    elif dimension == "RELATIONS":
        status = "WRONG_RELATION"
    elif dimension == "ANCHORS":
        status = "WRONG_POINTER"
    elif dimension in {"DOCUMENT_PASSPORT", "METADATA", "QUALITY"}:
        status = "WRONG_STATUS"
    else:
        status = "WRONG_VALUE"
    return {
        "dimension": dimension,
        "status": status,
        "managed_sha256": _hash(left),
        "view_sha256": _hash(right),
    }


def _critical_category(dimension: str, status: str) -> str:
    mapping = {
        "BLOCK_ORDER": "WRONG_BLOCK_ORDER",
        "TABLES": "CHANGED_TABLE_VALUE",
        "UNKNOWNS": "MISSING_UNKNOWN_BLOCK",
        "VISUALS": "MISSING_VISUAL_BLOCK",
        "RELATIONS": "MISSING_RELATION",
        "ISSUES": "MISSING_ISSUE",
        "LOSSES": "MISSING_KNOWN_LOSS",
        "QUALITY": "QUALITY_STATUS_CHANGED",
        "DOCUMENT_PASSPORT": "QUALITY_STATUS_CHANGED",
    }
    if status == "EXTRA_IN_VIEW":
        return "EXTRA_SOURCE_CONTENT"
    return mapping.get(dimension, "CHANGED_TEXT")


def _passport(content: dict[str, Any]) -> dict[str, Any]:
    return {
        key: content[key]
        for key in (
            "schema_version",
            "content_trust",
            "document_id",
            "source_format",
            "source_parts_total",
            "document_quality_status",
            "known_losses_total",
            "blocking_losses_total",
            "unknown_blocks_total",
            "source_context",
        )
    }


def _block_order(content: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "block_id": item["block_id"],
            "ordinal": item["ordinal"],
            "block_type": item["block_type"],
        }
        for item in content["blocks"]
    ]


def _blocks(content: dict[str, Any], block_type: str) -> list[dict[str, Any]]:
    return [item for item in content["blocks"] if item["block_type"] == block_type]


def _seal_checklist(checklist: dict[str, Any]) -> dict[str, Any]:
    checklist["integrity_sha256"] = _integrity(checklist)
    return checklist


def _require_checklist(
    value: Mapping[str, Any], expected_pass: str
) -> dict[str, Any]:
    checklist = copy.deepcopy(dict(value))
    if (
        checklist.get("schema_version") != CHECKLIST_SCHEMA_VERSION
        or checklist.get("pass") != expected_pass
        or checklist.get("terminal_status") != "PASSED"
        or checklist.get("integrity_sha256") != _integrity(checklist)
    ):
        raise ValueError("llm_view_checklist_invalid")
    return checklist


def _integrity(value: Mapping[str, Any]) -> str:
    unsigned = copy.deepcopy(dict(value))
    unsigned.pop("integrity_sha256", None)
    return hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
