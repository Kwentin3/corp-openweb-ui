from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .managed_document_llm_view_audit import ManagedDocumentLlmViewAuditor


VIEW_V2_SCHEMA_VERSION = "broker_reports_llm_document_view_v2"
_V1_HEADER = "BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1"
_V1_END = "END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1"
_V2_HEADER = "BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2"
_V2_END = "END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2"


class ManagedDocumentLlmViewV2AuditError(ValueError):
    """Raised when a span-aware view cannot be read back unambiguously."""


@dataclass(frozen=True)
class ParsedManagedDocumentLlmViewV2:
    payload: dict[str, Any]
    view_sha256: str
    view_bytes: int
    view_characters: int
    view_lines: int
    spans_total: int
    covered_coordinates_total: int


class ManagedDocumentLlmViewV2Auditor:
    """View-only v2 auditor; imports neither renderer nor contract validator."""

    def audit(self, raw: str | bytes) -> ParsedManagedDocumentLlmViewV2:
        text = _decode(raw)
        lines = text[:-1].split("\n")
        if lines[0] != _V2_HEADER or lines[-1] != _V2_END:
            _fail("llm_document_view_v2_marker_invalid")

        table_spans: dict[str, list[dict[str, Any]]] = {}
        current_table: str | None = None
        downgraded: list[str] = []
        for position, line in enumerate(lines):
            if position == 0:
                downgraded.append(_V1_HEADER)
                continue
            if position == len(lines) - 1:
                downgraded.append(_V1_END)
                continue
            tag = line.split(" ", 1)[0]
            if tag == "TABLE_BEGIN":
                if current_table is not None:
                    _fail("llm_document_view_v2_nested_table_invalid")
                current_table = ""
            elif tag == "TABLE_ID":
                if current_table != "":
                    _fail("llm_document_view_v2_table_id_position_invalid")
                table_id = _json_value(line, "TABLE_ID")
                if not isinstance(table_id, str) or table_id in table_spans:
                    _fail("llm_document_view_v2_table_id_invalid")
                current_table = table_id
                table_spans[table_id] = []
            elif tag == "CELL_SPAN":
                if not current_table:
                    _fail("llm_document_view_v2_span_outside_table")
                table_spans[current_table].append(_parse_span(_json_value(line, tag)))
                continue
            elif tag == "TABLE_END":
                if not current_table:
                    _fail("llm_document_view_v2_table_end_invalid")
                current_table = None
            downgraded.append(line)
        if current_table is not None:
            _fail("llm_document_view_v2_table_unclosed")

        base = ManagedDocumentLlmViewAuditor().audit("\n".join(downgraded) + "\n")
        payload = copy.deepcopy(base.payload)
        payload["schema_version"] = VIEW_V2_SCHEMA_VERSION
        tables_seen: set[str] = set()
        spans_total = 0
        covered_total = 0
        for block in payload["blocks"]:
            if block["block_type"] != "TABLE":
                continue
            content = block["content"]
            table_id = content["table_id"]
            spans = table_spans.get(table_id)
            if spans is None:
                _fail("llm_document_view_v2_table_span_inventory_missing")
            content["cell_spans"] = spans
            span_count, covered_count = _validate_table(content)
            spans_total += span_count
            covered_total += covered_count
            tables_seen.add(table_id)
        if tables_seen != set(table_spans):
            _fail("llm_document_view_v2_orphan_span_table")

        return ParsedManagedDocumentLlmViewV2(
            payload=payload,
            view_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            view_bytes=len(text.encode("utf-8")),
            view_characters=len(text),
            view_lines=len(lines),
            spans_total=spans_total,
            covered_coordinates_total=covered_total,
        )


def _parse_span(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "span_id",
        "value_at",
        "covers",
        "origin",
        "sources",
        "issue_ids",
    }:
        _fail("llm_document_view_v2_span_shape_invalid")
    value_at = value["value_at"]
    covers = value["covers"]
    sources = value["sources"]
    if (
        not isinstance(value_at, list)
        or len(value_at) != 2
        or not all(_index(item) for item in value_at)
        or not isinstance(covers, dict)
        or set(covers)
        != {"row_start", "row_end", "column_start", "column_end"}
        or not all(_index(item) for item in covers.values())
        or not isinstance(sources, list)
        or not all(isinstance(item, dict) and isinstance(item.get("anchor_id"), str) for item in sources)
        or not isinstance(value["issue_ids"], list)
    ):
        _fail("llm_document_view_v2_span_shape_invalid")
    return {
        "span_id": value["span_id"],
        "value_row_index": value_at[0],
        "value_column_index": value_at[1],
        "row_start": covers["row_start"],
        "row_end": covers["row_end"],
        "column_start": covers["column_start"],
        "column_end": covers["column_end"],
        "origin": value["origin"],
        "evidence_anchor_ids": [item["anchor_id"] for item in sources],
        "issue_ids": list(value["issue_ids"]),
    }


def _validate_table(content: dict[str, Any]) -> tuple[int, int]:
    rows = content["rows"]
    annotations = content["cell_annotations"]
    by_coordinate: dict[tuple[int, int], dict[str, Any]] = {}
    for annotation in annotations:
        if set(annotation) != {
            "row_index",
            "column_index",
            "state",
            "origin",
            "evidence_anchor_ids",
            "issue_ids",
            "span_id",
        }:
            _fail("llm_document_view_v2_cell_state_shape_invalid")
        coordinate = (annotation["row_index"], annotation["column_index"])
        if coordinate in by_coordinate:
            _fail("llm_document_view_v2_cell_state_duplicate")
        by_coordinate[coordinate] = annotation

    span_ids: set[str] = set()
    occupied: set[tuple[int, int]] = set()
    expected_covered: dict[tuple[int, int], str] = {}
    for span in content["cell_spans"]:
        span_id = span["span_id"]
        if not isinstance(span_id, str) or not span_id or span_id in span_ids:
            _fail("llm_document_view_v2_span_id_invalid")
        span_ids.add(span_id)
        row_start, row_end = span["row_start"], span["row_end"]
        column_start, column_end = span["column_start"], span["column_end"]
        value_coordinate = (
            span["value_row_index"],
            span["value_column_index"],
        )
        coordinates = [
            (row, column)
            for row in range(row_start, row_end + 1)
            for column in range(column_start, column_end + 1)
        ]
        if (
            row_start > row_end
            or column_start > column_end
            or len(coordinates) < 2
            or value_coordinate not in coordinates
            or any(row >= len(rows) or column >= len(rows[row]) for row, column in coordinates)
        ):
            _fail("llm_document_view_v2_span_range_invalid")
        if occupied.intersection(coordinates):
            _fail("llm_document_view_v2_span_overlap")
        occupied.update(coordinates)
        for coordinate in coordinates:
            if coordinate != value_coordinate:
                expected_covered[coordinate] = span_id

    actual_covered: dict[tuple[int, int], str] = {}
    for coordinate, annotation in by_coordinate.items():
        state = annotation["state"]
        span_id = annotation["span_id"]
        row, column = coordinate
        if row >= len(rows) or column >= len(rows[row]):
            _fail("llm_document_view_v2_cell_state_range_invalid")
        if state == "COVERED_BY_SPAN":
            if not isinstance(span_id, str) or rows[row][column] is not None:
                _fail("llm_document_view_v2_covered_coordinate_invalid")
            actual_covered[coordinate] = span_id
        elif span_id is not None:
            _fail("llm_document_view_v2_noncovered_span_id_invalid")
    if actual_covered != expected_covered:
        _fail("llm_document_view_v2_span_coverage_mismatch")
    return len(content["cell_spans"]), len(actual_covered)


def _json_value(line: str, tag: str) -> Any:
    prefix = tag + " "
    if not line.startswith(prefix):
        _fail("llm_document_view_v2_record_invalid")
    try:
        return json.loads(line[len(prefix) :], object_pairs_hook=_reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ManagedDocumentLlmViewV2AuditError(
            "llm_document_view_v2_json_invalid"
        ) from exc


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("llm_document_view_v2_duplicate_json_key")
        result[key] = value
    return result


def _decode(raw: str | bytes) -> str:
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    except UnicodeDecodeError as exc:
        raise ManagedDocumentLlmViewV2AuditError(
            "llm_document_view_v2_utf8_invalid"
        ) from exc
    if (
        not isinstance(text, str)
        or not text.endswith("\n")
        or "\r" in text
        or text.startswith("\ufeff")
        or "\x00" in text
    ):
        _fail("llm_document_view_v2_encoding_invalid")
    lines = text[:-1].split("\n")
    if not lines or any(not line for line in lines):
        _fail("llm_document_view_v2_empty_line_invalid")
    return text


def _index(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _fail(code: str) -> None:
    raise ManagedDocumentLlmViewV2AuditError(code)
