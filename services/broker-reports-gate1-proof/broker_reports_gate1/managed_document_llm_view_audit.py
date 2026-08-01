from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


VIEW_SCHEMA_VERSION = "broker_reports_llm_document_view_v1"
CHECKLIST_SCHEMA_VERSION = "broker_reports_llm_document_view_checklist_v1"
_HEADER = "BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1"
_TRUST = "CONTENT_TRUST UNTRUSTED_SOURCE_DOCUMENT"
_END = "END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1"


class ManagedDocumentLlmViewAuditError(ValueError):
    """Raised when a DOC3 view is not unambiguously parseable."""


@dataclass(frozen=True)
class ParsedManagedDocumentLlmView:
    payload: dict[str, Any]
    view_sha256: str
    view_bytes: int
    view_characters: int
    view_lines: int


class ManagedDocumentLlmViewAuditor:
    """Independent view-only parser; it imports neither renderer nor DOC1 owner."""

    def audit(self, raw: str | bytes) -> ParsedManagedDocumentLlmView:
        text = self._decode(raw)
        cursor = _Cursor(text)
        cursor.marker(_HEADER)
        cursor.marker(_TRUST)
        cursor.marker("DOCUMENT_BEGIN")
        document_id = cursor.value("DOCUMENT_ID", str)
        source_format = cursor.value("SOURCE_FORMAT", str)
        source_parts_total = cursor.value("SOURCE_PARTS_TOTAL", int)
        quality_status = cursor.value("DOCUMENT_QUALITY_STATUS", str)
        known_losses_total = cursor.value("KNOWN_LOSSES_TOTAL", int)
        blocking_losses_total = cursor.value("BLOCKING_LOSSES_TOTAL", int)
        unknown_blocks_total = cursor.value("UNKNOWN_BLOCKS_TOTAL", int)
        source_context = cursor.value("SOURCE_CONTEXT", dict)

        cursor.marker("METADATA_BEGIN")
        metadata: list[dict[str, Any]] = []
        while cursor.peek() != "METADATA_SECTION_END":
            name = cursor.value("METADATA", str)
            field = {
                "status": cursor.value("STATUS", str),
                "origin": cursor.value("ORIGIN", str),
                "value": cursor.value("VALUE", (str, type(None))),
                "candidates": cursor.value("CANDIDATES", list),
                "sources": cursor.value("SOURCE", list),
            }
            cursor.marker("METADATA_END")
            metadata.append({"name": name, "field": field})
        cursor.marker("METADATA_SECTION_END")

        cursor.marker("ANCHORS_BEGIN")
        anchors: list[dict[str, Any]] = []
        while cursor.peek() != "ANCHORS_END":
            anchors.append(cursor.value("ANCHOR", dict))
        cursor.marker("ANCHORS_END")

        cursor.marker("BLOCKS_BEGIN")
        blocks: list[dict[str, Any]] = []
        while cursor.peek() != "BLOCKS_END":
            blocks.append(self._parse_block(cursor))
        cursor.marker("BLOCKS_END")

        cursor.marker("RELATIONS_BEGIN")
        relations: list[dict[str, Any]] = []
        while cursor.peek() != "RELATIONS_END":
            relations.append(cursor.value("RELATION", dict))
        cursor.marker("RELATIONS_END")

        quality = cursor.value("QUALITY", dict)
        cursor.marker("ISSUES_BEGIN")
        issues: list[dict[str, Any]] = []
        while cursor.peek() != "ISSUES_END":
            issues.append(cursor.value("ISSUE", dict))
        cursor.marker("ISSUES_END")
        cursor.marker("LOSSES_BEGIN")
        losses: list[dict[str, Any]] = []
        while cursor.peek() != "LOSSES_END":
            losses.append(cursor.value("LOSS", dict))
        cursor.marker("LOSSES_END")
        cursor.marker("DOCUMENT_END")
        cursor.marker(_END)
        cursor.require_end()

        payload = {
            "schema_version": VIEW_SCHEMA_VERSION,
            "content_trust": "UNTRUSTED_SOURCE_DOCUMENT",
            "document_id": document_id,
            "source_format": source_format,
            "source_parts_total": source_parts_total,
            "document_quality_status": quality_status,
            "known_losses_total": known_losses_total,
            "blocking_losses_total": blocking_losses_total,
            "unknown_blocks_total": unknown_blocks_total,
            "source_context": source_context,
            "metadata": metadata,
            "anchors": anchors,
            "blocks": blocks,
            "relations": relations,
            "quality": quality,
            "issues": issues,
            "losses": losses,
        }
        self._validate(payload)
        return ParsedManagedDocumentLlmView(
            payload=payload,
            view_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            view_bytes=len(text.encode("utf-8")),
            view_characters=len(text),
            view_lines=len(cursor.lines),
        )

    def _parse_block(self, cursor: "_Cursor") -> dict[str, Any]:
        cursor.marker("BLOCK_BEGIN")
        ordinal = cursor.value("ORDINAL", int)
        block_id = cursor.value("BLOCK_ID", str)
        block_type = cursor.value("BLOCK_TYPE", str)
        sources = cursor.value("SOURCE", list)
        restoration_status = cursor.value("RESTORATION_STATUS", str)
        structure_origin = cursor.value("STRUCTURE_ORIGIN", str)
        restoration_issue_ids = cursor.value("RESTORATION_ISSUE_IDS", list)
        issue_ids = cursor.value("ISSUE_IDS", list)

        if block_type == "HEADING":
            content = {
                "raw_text": cursor.value("HEADING_TEXT", str),
                "level_status": cursor.value("HEADING_LEVEL_STATUS", str),
                "level": cursor.value("HEADING_LEVEL", (int, type(None))),
            }
        elif block_type == "PARAGRAPH":
            content = {
                "raw_text": cursor.value("TEXT", str),
                "join_events": [],
            }
            while cursor.tag() == "JOIN_EVENT":
                content["join_events"].append(cursor.value("JOIN_EVENT", dict))
        elif block_type == "LIST":
            cursor.marker("LIST_BEGIN")
            items: list[dict[str, Any]] = []
            while cursor.peek() != "LIST_END":
                item_index, item = cursor.indexed_value("ITEM", dict)
                if item.get("ordinal") != item_index:
                    _fail("llm_document_view_list_item_ordinal_mismatch")
                items.append(item)
            cursor.marker("LIST_END")
            content = {"items": items}
        elif block_type == "TABLE":
            content = self._parse_table(cursor)
        elif block_type == "NOTE":
            content = cursor.value("NOTE", dict)
        elif block_type == "VISUAL":
            content = {
                "visual_type": cursor.value("VISUAL_TYPE", str),
                "caption": cursor.value("CAPTION", dict),
                "safe_description": cursor.value("DESCRIPTION", dict),
                "processing_status": cursor.value("PROCESSING_STATUS", str),
                "private_source_available": cursor.value(
                    "PRIVATE_SOURCE_AVAILABLE", bool
                ),
            }
        elif block_type == "BOUNDARY":
            boundary = cursor.value("BOUNDARY", dict)
            if set(boundary) != {"kind", "source_part_index", "label"}:
                _fail("llm_document_view_boundary_shape_invalid")
            content = {
                "boundary_type": boundary["kind"],
                "source_part_index": boundary["source_part_index"],
                "label": boundary["label"],
            }
        elif block_type == "UNKNOWN":
            content = {
                "reason": cursor.value("UNKNOWN_REASON", str),
                "raw_text": cursor.value("RAW_TEXT", (str, type(None))),
                "private_source_available": cursor.value(
                    "PRIVATE_SOURCE_AVAILABLE", bool
                ),
            }
        else:
            _fail("llm_document_view_block_type_invalid")

        cursor.marker("BLOCK_END")
        return {
            "block_id": block_id,
            "ordinal": ordinal,
            "block_type": block_type,
            "sources": sources,
            "restoration": {
                "status": restoration_status,
                "classification_origin": structure_origin,
                "issue_ids": restoration_issue_ids,
            },
            "issue_ids": issue_ids,
            "content": content,
        }

    def _parse_table(self, cursor: "_Cursor") -> dict[str, Any]:
        cursor.marker("TABLE_BEGIN")
        table_id = cursor.value("TABLE_ID", str)
        title = cursor.value("TITLE", dict)
        description = cursor.value("DESCRIPTION", str)
        completeness_status = cursor.value("COMPLETENESS", str)
        rows_total = cursor.value("ROWS_TOTAL", int)
        columns_max_total = cursor.value("COLUMNS_MAX_TOTAL", int)
        header_hierarchy = cursor.value("HEADER_HIERARCHY", dict)
        row_groups = cursor.value("ROW_GROUPS", dict)
        row_markers: list[dict[str, Any]] = []
        while cursor.tag() == "ROW_MARKER":
            row_markers.append(cursor.value("ROW_MARKER", dict))
        units: list[dict[str, Any]] = []
        while cursor.tag() == "UNIT":
            units.append(cursor.value("UNIT", dict))
        rows: list[list[Any]] = []
        while cursor.tag() == "ROW":
            row_index, row = cursor.indexed_value("ROW", list)
            if row_index != len(rows):
                _fail("llm_document_view_table_row_order_invalid")
            rows.append(row)
        annotations: list[dict[str, Any]] = []
        while cursor.tag() == "CELL_STATE":
            annotations.append(cursor.value("CELL_STATE", dict))
        related: list[str] = []
        while cursor.tag() == "RELATED_RELATION":
            related.append(cursor.value("RELATED_RELATION", str))
        continuation: list[str] = []
        while cursor.tag() == "CONTINUATION_RELATION":
            continuation.append(cursor.value("CONTINUATION_RELATION", str))
        gaps: list[str] = []
        while cursor.tag() == "KNOWN_GAP":
            gaps.append(cursor.value("KNOWN_GAP", str))
        cursor.marker("TABLE_END")
        if rows_total != len(rows):
            _fail("llm_document_view_table_row_count_invalid")
        if columns_max_total != max(len(row) for row in rows):
            _fail("llm_document_view_table_column_count_invalid")
        return {
            "table_id": table_id,
            "title": title,
            "description": description,
            "rows": rows,
            "completeness_status": completeness_status,
            "header_hierarchy": header_hierarchy,
            "row_groups": row_groups,
            "row_markers": row_markers,
            "units": units,
            "cell_annotations": annotations,
            "related_relation_ids": related,
            "continuation_relation_ids": continuation,
            "known_gap_ids": gaps,
        }

    def _validate(self, payload: dict[str, Any]) -> None:
        blocks = payload["blocks"]
        if [item["ordinal"] for item in blocks] != list(range(len(blocks))):
            _fail("llm_document_view_block_order_invalid")
        _unique(blocks, "block_id", "block")
        _unique(payload["anchors"], "anchor_id", "anchor")
        _unique(payload["relations"], "relation_id", "relation")
        _unique(payload["issues"], "issue_id", "issue")
        _unique(payload["losses"], "loss_id", "loss")
        if payload["source_parts_total"] < 1:
            _fail("llm_document_view_source_parts_invalid")
        if payload["unknown_blocks_total"] != sum(
            item["block_type"] == "UNKNOWN" for item in blocks
        ):
            _fail("llm_document_view_unknown_count_invalid")
        if payload["known_losses_total"] != len(payload["losses"]):
            _fail("llm_document_view_loss_count_invalid")
        if payload["blocking_losses_total"] != sum(
            bool(item["blocks_semantic_analysis"]) for item in payload["losses"]
        ):
            _fail("llm_document_view_blocking_loss_count_invalid")
        if payload["document_quality_status"] != payload["quality"].get("status"):
            _fail("llm_document_view_quality_status_mismatch")
        if payload["quality"].get("preserved_blocks_total") != len(blocks):
            _fail("llm_document_view_preserved_block_count_invalid")

    @staticmethod
    def _decode(raw: str | bytes) -> str:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        except UnicodeDecodeError as exc:
            raise ManagedDocumentLlmViewAuditError(
                "llm_document_view_utf8_invalid"
            ) from exc
        if not isinstance(text, str) or not text.endswith("\n") or "\r" in text:
            _fail("llm_document_view_line_endings_invalid")
        if text.startswith("\ufeff") or "\x00" in text:
            _fail("llm_document_view_text_encoding_invalid")
        return text


class _Cursor:
    def __init__(self, text: str) -> None:
        self.lines = text[:-1].split("\n")
        if not self.lines or any(not line for line in self.lines):
            _fail("llm_document_view_empty_line_invalid")
        self.position = 0

    def peek(self) -> str:
        if self.position >= len(self.lines):
            _fail("llm_document_view_unexpected_end")
        return self.lines[self.position]

    def tag(self) -> str:
        return self.peek().split(" ", 1)[0]

    def marker(self, expected: str) -> None:
        if self.peek() != expected:
            _fail(f"llm_document_view_marker_invalid:{expected}")
        self.position += 1

    def value(self, tag: str, expected_type: Any) -> Any:
        line = self.peek()
        prefix = tag + " "
        if not line.startswith(prefix):
            _fail(f"llm_document_view_value_tag_invalid:{tag}")
        value = _parse_json(line[len(prefix) :])
        if not isinstance(value, expected_type):
            _fail(f"llm_document_view_value_type_invalid:{tag}")
        self.position += 1
        return value

    def indexed_value(self, tag: str, expected_type: Any) -> tuple[int, Any]:
        line = self.peek()
        prefix = tag + " "
        if not line.startswith(prefix):
            _fail(f"llm_document_view_indexed_tag_invalid:{tag}")
        remainder = line[len(prefix) :]
        index_text, separator, json_text = remainder.partition(" ")
        if not separator or not index_text.isdigit():
            _fail(f"llm_document_view_index_invalid:{tag}")
        value = _parse_json(json_text)
        if not isinstance(value, expected_type):
            _fail(f"llm_document_view_indexed_type_invalid:{tag}")
        self.position += 1
        return int(index_text), value

    def require_end(self) -> None:
        if self.position != len(self.lines):
            _fail("llm_document_view_content_after_end")


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ManagedDocumentLlmViewAuditError(
            "llm_document_view_json_value_invalid"
        ) from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("llm_document_view_duplicate_json_key")
        result[key] = value
    return result


def _unique(items: list[dict[str, Any]], key: str, label: str) -> None:
    values = [item.get(key) for item in items]
    if None in values or len(values) != len(set(values)):
        _fail(f"llm_document_view_{label}_id_invalid")


def _fail(code: str) -> None:
    raise ManagedDocumentLlmViewAuditError(code)
