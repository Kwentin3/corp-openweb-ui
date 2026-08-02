from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


VIEW_SCHEMA_VERSION = "broker_reports_llm_document_view_v2"
_HEADER = "BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2"
_DOCUMENT_BEGIN = "DOCUMENT_BEGIN"
_DOCUMENT_END = "DOCUMENT_END"
_END = "END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2"

_ROW_ROLES = {
    "TABLE_TITLE",
    "COLUMN_HEADER",
    "GROUP_HEADER",
    "DATA",
    "SUBTOTAL",
    "TOTAL",
    "NOTE",
    "CONTINUATION_HEADER",
    "UNKNOWN",
}
_ENTRY_KINDS = {"LABEL", "VALUE", "UNIT", "MARKER", "NOTE", "UNKNOWN"}
_BINDING_STATUSES = {"BOUND", "NOT_APPLICABLE", "UNKNOWN"}
_SAFE_POINTER_KEYS = {
    "anchor_id",
    "format",
    "source_part_index",
    "page",
    "row_start",
    "row_end",
    "column_start",
    "column_end",
    "ordinal",
}


class ManagedDocumentLlmViewV2AuditError(ValueError):
    """Raised when View v2 bytes or row semantics are invalid."""


@dataclass(frozen=True)
class ParsedManagedDocumentLlmViewV2:
    payload: dict[str, Any]
    canonical_sha256: str


class ManagedDocumentLlmViewV2Auditor:
    """Independent stdlib-only View v2 grammar and semantic auditor."""

    def audit(self, raw: str | bytes) -> ParsedManagedDocumentLlmViewV2:
        text = self._decode(raw)
        cursor = _Cursor(text)
        cursor.marker(_HEADER)
        content_trust = cursor.value("CONTENT_TRUST", str)
        cursor.marker(_DOCUMENT_BEGIN)
        payload: dict[str, Any] = {
            "schema_version": VIEW_SCHEMA_VERSION,
            "content_trust": content_trust,
            "source_format": cursor.value("SOURCE_FORMAT", str),
            "source_parts_total": cursor.value("SOURCE_PARTS_TOTAL", int),
            "document_quality_status": cursor.value(
                "DOCUMENT_QUALITY_STATUS", str
            ),
            "known_losses_total": cursor.value("KNOWN_LOSSES_TOTAL", int),
            "blocking_losses_total": cursor.value(
                "BLOCKING_LOSSES_TOTAL", int
            ),
            "unknown_blocks_total": cursor.value("UNKNOWN_BLOCKS_TOTAL", int),
            "source_context": cursor.value("SOURCE_CONTEXT", dict),
        }

        payload["metadata"] = self._parse_metadata(cursor)
        payload["anchors"] = self._parse_repeated(
            cursor, "ANCHORS_BEGIN", "ANCHOR", "ANCHORS_END"
        )

        cursor.marker("BLOCKS_BEGIN")
        blocks: list[dict[str, Any]] = []
        while cursor.peek() != "BLOCKS_END":
            blocks.append(self._parse_block(cursor))
        cursor.marker("BLOCKS_END")
        payload["blocks"] = blocks

        payload["relations"] = self._parse_repeated(
            cursor, "RELATIONS_BEGIN", "RELATION", "RELATIONS_END"
        )
        payload["quality"] = cursor.value("QUALITY", dict)
        payload["issues"] = self._parse_repeated(
            cursor, "ISSUES_BEGIN", "ISSUE", "ISSUES_END"
        )
        payload["losses"] = self._parse_repeated(
            cursor, "LOSSES_BEGIN", "LOSS", "LOSSES_END"
        )
        cursor.marker(_DOCUMENT_END)
        cursor.marker(_END)
        cursor.require_end()

        self._validate(payload)
        canonical = _canonical_bytes(payload)
        return ParsedManagedDocumentLlmViewV2(
            payload=payload,
            canonical_sha256=hashlib.sha256(canonical).hexdigest(),
        )

    @staticmethod
    def _parse_metadata(cursor: "_Cursor") -> list[dict[str, Any]]:
        cursor.marker("METADATA_BEGIN")
        result: list[dict[str, Any]] = []
        while cursor.peek() != "METADATA_END":
            cursor.marker("METADATA_FIELD_BEGIN")
            result.append(
                {
                    "name": cursor.value("METADATA_NAME", str),
                    "field": cursor.value("METADATA", dict),
                }
            )
            cursor.marker("METADATA_FIELD_END")
        cursor.marker("METADATA_END")
        return result

    @staticmethod
    def _parse_repeated(
        cursor: "_Cursor", begin: str, tag: str, end: str
    ) -> list[dict[str, Any]]:
        cursor.marker(begin)
        result: list[dict[str, Any]] = []
        while cursor.peek() != end:
            result.append(cursor.value(tag, dict))
        cursor.marker(end)
        return result

    def _parse_block(self, cursor: "_Cursor") -> dict[str, Any]:
        cursor.marker("BLOCK_BEGIN")
        block = {
            "ordinal": cursor.value("BLOCK_ORDINAL", int),
            "block_id": cursor.value("BLOCK_ID", str),
            "block_type": cursor.value("BLOCK_TYPE", str),
            "sources": cursor.value("BLOCK_SOURCE", list),
            "restoration": cursor.value("RESTORATION", dict),
            "issue_ids": cursor.value("BLOCK_ISSUE_IDS", list),
        }
        if block["block_type"] == "TABLE":
            block["content"] = self._parse_table(cursor)
        else:
            block["content"] = cursor.value("BLOCK_CONTENT", dict)
        cursor.marker("BLOCK_END")
        return block

    def _parse_table(self, cursor: "_Cursor") -> dict[str, Any]:
        cursor.marker("TABLE_BEGIN")
        table: dict[str, Any] = {
            "table_id": cursor.value("TABLE_ID", str),
            "completeness_status": cursor.value("TABLE_COMPLETENESS", str),
        }

        cursor.marker("SOURCE_PARTS_BEGIN")
        source_parts: list[dict[str, Any]] = []
        while cursor.peek() != "SOURCE_PARTS_END":
            cursor.marker("SOURCE_PART_BEGIN")
            source_parts.append(
                {
                    "ordinal": cursor.value("SOURCE_PART_ORDINAL", int),
                    "source_part_id": cursor.value("SOURCE_PART_ID", str),
                    "page": cursor.value("SOURCE_PART_PAGE", int),
                    "sources": cursor.value("SOURCE_PART_SOURCE", list),
                    "first_row_id": cursor.value(
                        "SOURCE_PART_FIRST_ROW_ID", str
                    ),
                    "last_row_id": cursor.value(
                        "SOURCE_PART_LAST_ROW_ID", str
                    ),
                    "continuation_status": cursor.value(
                        "SOURCE_PART_CONTINUATION", str
                    ),
                    "issue_ids": cursor.value("SOURCE_PART_ISSUE_IDS", list),
                }
            )
            cursor.marker("SOURCE_PART_END")
        cursor.marker("SOURCE_PARTS_END")
        table["source_parts"] = source_parts

        cursor.marker("COLUMNS_BEGIN")
        columns: list[dict[str, Any]] = []
        while cursor.peek() != "COLUMNS_END":
            cursor.marker("COLUMN_BEGIN")
            columns.append(
                {
                    "ordinal": cursor.value("COLUMN_ORDINAL", int),
                    "column_id": cursor.value("COLUMN_ID", str),
                    "header_path": cursor.value("COLUMN_HEADER_PATH", list),
                    "sources": cursor.value("COLUMN_SOURCE", list),
                    "issue_ids": cursor.value("COLUMN_ISSUE_IDS", list),
                }
            )
            cursor.marker("COLUMN_END")
        cursor.marker("COLUMNS_END")
        table["logical_columns"] = columns

        cursor.marker("ROWS_BEGIN")
        rows: list[dict[str, Any]] = []
        while cursor.peek() != "ROWS_END":
            rows.append(self._parse_row(cursor))
        cursor.marker("ROWS_END")
        table["ordered_rows"] = rows
        table["relations"] = cursor.value("TABLE_RELATION_IDS", list)
        table["issues"] = cursor.value("TABLE_ISSUE_IDS", list)
        table["known_gap_ids"] = cursor.value("TABLE_KNOWN_GAP_IDS", list)
        cursor.marker("TABLE_END")
        return table

    @staticmethod
    def _parse_row(cursor: "_Cursor") -> dict[str, Any]:
        cursor.marker("ROW_BEGIN")
        row: dict[str, Any] = {
            "ordinal": cursor.value("ROW_ORDINAL", int),
            "row_id": cursor.value("ROW_ID", str),
            "role": cursor.value("ROW_ROLE", str),
            "role_origin": cursor.value("ROW_ROLE_ORIGIN", str),
            "nesting_level": cursor.value(
                "ROW_NESTING_LEVEL", (int, type(None))
            ),
            "parent_row_id": cursor.value(
                "ROW_PARENT_ID", (str, type(None))
            ),
            "sources": cursor.value("ROW_SOURCE", list),
            "issue_ids": cursor.value("ROW_ISSUE_IDS", list),
        }
        cursor.marker("ENTRIES_BEGIN")
        entries: list[dict[str, Any]] = []
        while cursor.peek() != "ENTRIES_END":
            cursor.marker("ENTRY_BEGIN")
            entries.append(
                {
                    "ordinal": cursor.value("ENTRY_ORDINAL", int),
                    "entry_id": cursor.value("ENTRY_ID", str),
                    "kind": cursor.value("ENTRY_KIND", str),
                    "text": cursor.value("ENTRY_TEXT", (str, type(None))),
                    "origin": cursor.value("ENTRY_ORIGIN", str),
                    "column_binding_status": cursor.value(
                        "ENTRY_COLUMN_BINDING_STATUS", str
                    ),
                    "logical_column_id": cursor.value(
                        "ENTRY_LOGICAL_COLUMN_ID", (str, type(None))
                    ),
                    "covers_logical_column_ids": cursor.value(
                        "ENTRY_COVERS_LOGICAL_COLUMN_IDS", list
                    ),
                    "sources": cursor.value("ENTRY_SOURCE", list),
                    "issue_ids": cursor.value("ENTRY_ISSUE_IDS", list),
                }
            )
            cursor.marker("ENTRY_END")
        cursor.marker("ENTRIES_END")
        row["entries"] = entries
        cursor.marker("ROW_END")
        return row

    def _validate(self, payload: dict[str, Any]) -> None:
        _reject_forbidden_surface(payload)
        if payload["content_trust"] != "UNTRUSTED_SOURCE_DOCUMENT":
            _fail("llm_document_view_v2_content_trust_invalid")
        for key in (
            "source_parts_total",
            "known_losses_total",
            "blocking_losses_total",
            "unknown_blocks_total",
        ):
            if payload[key] < 0:
                _fail("llm_document_view_v2_count_invalid")
        if payload["source_parts_total"] < 1:
            _fail("llm_document_view_v2_source_parts_invalid")
        _validate_source_context(
            payload["source_context"], payload["source_format"]
        )

        _unique(payload["metadata"], "name", "metadata_name")
        anchors = payload["anchors"]
        _unique(anchors, "anchor_id", "anchor")
        anchor_by_id = {item["anchor_id"]: item for item in anchors}
        for pointer in anchors:
            _validate_pointer(pointer)
            if pointer["format"] != payload["source_format"]:
                _fail("llm_document_view_v2_anchor_format_mismatch")
        for item in payload["metadata"]:
            field = item["field"]
            if set(field) != {"status", "origin", "value", "candidates", "sources"}:
                _fail("llm_document_view_v2_metadata_shape_invalid")
            _validate_sources(field["sources"], anchor_by_id)

        blocks = payload["blocks"]
        _unique(blocks, "block_id", "block")
        if [item["ordinal"] for item in blocks] != list(range(len(blocks))):
            _fail("llm_document_view_v2_block_order_invalid")

        _unique(payload["issues"], "issue_id", "issue")
        top_level_issue_ids = {
            issue["issue_id"] for issue in payload["issues"]
        }

        table_ids: set[str] = set()
        row_ids: set[str] = set()
        entry_ids: set[str] = set()
        column_ids: set[str] = set()
        source_part_ids: set[str] = set()
        for block in blocks:
            _validate_sources(block["sources"], anchor_by_id)
            if block["block_type"] == "TABLE":
                self._validate_table(
                    block["content"],
                    anchor_by_id,
                    table_ids,
                    row_ids,
                    entry_ids,
                    column_ids,
                    source_part_ids,
                    source_parts_total=payload["source_parts_total"],
                    top_level_issue_ids=top_level_issue_ids,
                )

        for relation in payload["relations"]:
            _validate_sources(relation.get("sources"), anchor_by_id)
        for issue in payload["issues"]:
            _validate_sources(issue.get("sources"), anchor_by_id)
        for loss in payload["losses"]:
            _validate_sources(loss.get("sources"), anchor_by_id)
        _unique(payload["relations"], "relation_id", "relation")
        _unique(payload["losses"], "loss_id", "loss")
        if payload["known_losses_total"] != len(payload["losses"]):
            _fail("llm_document_view_v2_loss_count_invalid")
        unknown_blocks = sum(
            item["block_type"] == "UNKNOWN" for item in blocks
        )
        if payload["unknown_blocks_total"] != unknown_blocks:
            _fail("llm_document_view_v2_unknown_count_invalid")

    def _validate_table(
        self,
        table: dict[str, Any],
        anchors: dict[str, dict[str, Any]],
        table_ids: set[str],
        document_row_ids: set[str],
        document_entry_ids: set[str],
        document_column_ids: set[str],
        document_source_part_ids: set[str],
        *,
        source_parts_total: int,
        top_level_issue_ids: set[str],
    ) -> None:
        _claim(table["table_id"], table_ids, "table")
        rows = table["ordered_rows"]
        columns = table["logical_columns"]
        parts = table["source_parts"]
        if not rows or not parts:
            _fail("llm_document_view_v2_empty_table_invalid")
        _continuous(rows, "row")
        _continuous(columns, "column")
        _continuous(parts, "source_part")

        rows_by_id: dict[str, dict[str, Any]] = {}
        entries_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for row in rows:
            _claim(row["row_id"], document_row_ids, "row")
            rows_by_id[row["row_id"]] = row
            if row["role"] not in _ROW_ROLES:
                _fail("llm_document_view_v2_row_role_invalid")
            if row["role"] == "UNKNOWN" and not row["issue_ids"]:
                _fail("llm_document_view_v2_unknown_row_issue_missing")
            nesting = row["nesting_level"]
            if nesting is not None and (
                not isinstance(nesting, int)
                or isinstance(nesting, bool)
                or nesting < 0
            ):
                _fail("llm_document_view_v2_row_nesting_invalid")
            if nesting is None and not row["issue_ids"]:
                _fail("llm_document_view_v2_unknown_nesting_issue_missing")
            _validate_sources(row["sources"], anchors)
            if not row["entries"]:
                _fail("llm_document_view_v2_empty_row_invalid")
            _continuous(row["entries"], "entry")
            for entry in row["entries"]:
                _claim(entry["entry_id"], document_entry_ids, "entry")
                entries_by_id[entry["entry_id"]] = (row, entry)
                if entry["kind"] not in _ENTRY_KINDS:
                    _fail("llm_document_view_v2_entry_kind_invalid")
                if entry["column_binding_status"] not in _BINDING_STATUSES:
                    _fail("llm_document_view_v2_entry_binding_invalid")
                if entry["text"] is None and (
                    entry["kind"] != "UNKNOWN" or not entry["issue_ids"]
                ):
                    _fail("llm_document_view_v2_null_entry_invalid")
                _validate_sources(entry["sources"], anchors)

        for row in rows:
            parent_id = row["parent_row_id"]
            if parent_id is None:
                if row["nesting_level"] not in {0, None} and not row[
                    "issue_ids"
                ]:
                    _fail(
                        "llm_document_view_v2_unresolved_parent_issue_missing"
                    )
                continue
            parent = rows_by_id.get(parent_id)
            if parent is None or parent["ordinal"] >= row["ordinal"]:
                _fail("llm_document_view_v2_parent_order_invalid")
            if parent["role"] != "GROUP_HEADER":
                _fail("llm_document_view_v2_parent_role_invalid")
            if (
                parent["nesting_level"] is None
                or row["nesting_level"] != parent["nesting_level"] + 1
            ):
                _fail("llm_document_view_v2_parent_nesting_invalid")

        table_column_ids: list[str] = []
        for column in columns:
            _claim(column["column_id"], document_column_ids, "column")
            table_column_ids.append(column["column_id"])
            _validate_sources(column["sources"], anchors)
            header_row_ordinals: list[int] = []
            for entry_id in column["header_path"]:
                owner = entries_by_id.get(entry_id)
                if owner is None or owner[0]["role"] not in {
                    "COLUMN_HEADER",
                    "CONTINUATION_HEADER",
                }:
                    _fail("llm_document_view_v2_header_path_invalid")
                header_row_ordinals.append(owner[0]["ordinal"])
                header_entry = owner[1]
                if not (
                    header_entry["column_binding_status"] == "BOUND"
                    and (
                        header_entry["logical_column_id"]
                        == column["column_id"]
                        or column["column_id"]
                        in header_entry["covers_logical_column_ids"]
                    )
                ):
                    _fail("llm_document_view_v2_header_path_binding_invalid")
            if header_row_ordinals != sorted(header_row_ordinals):
                _fail("llm_document_view_v2_header_path_order_invalid")
            if not column["header_path"] and not column["issue_ids"]:
                _fail("llm_document_view_v2_header_path_issue_missing")

        column_order = {
            column_id: ordinal
            for ordinal, column_id in enumerate(table_column_ids)
        }
        for row, entry in entries_by_id.values():
            column_id = entry["logical_column_id"]
            binding = entry["column_binding_status"]
            covers = entry["covers_logical_column_ids"]
            if any(
                not isinstance(item, str) or item not in column_order
                for item in covers
            ):
                _fail("llm_document_view_v2_covered_column_invalid")
            if len(covers) != len(set(covers)):
                _fail("llm_document_view_v2_covered_column_duplicate_invalid")
            if covers != sorted(covers, key=column_order.__getitem__):
                _fail("llm_document_view_v2_covered_column_order_invalid")
            if covers and len(covers) < 2:
                _fail("llm_document_view_v2_covered_column_count_invalid")
            if binding == "BOUND":
                if column_id is not None and column_id not in column_order:
                    _fail("llm_document_view_v2_entry_column_invalid")
                if column_id is None and not covers:
                    _fail("llm_document_view_v2_entry_binding_invalid")
                if column_id is not None and covers and column_id != covers[0]:
                    _fail(
                        "llm_document_view_v2_direct_covered_column_invalid"
                    )
                if row["role"] in {"SUBTOTAL", "TOTAL"} and covers and (
                    column_id is None or column_id != covers[0]
                ):
                    _fail("llm_document_view_v2_summary_binding_invalid")
            elif column_id is not None or covers:
                _fail("llm_document_view_v2_unbound_column_invalid")
            if binding == "UNKNOWN":
                if not entry["issue_ids"]:
                    _fail(
                        "llm_document_view_v2_unknown_column_issue_missing"
                    )
                if any(
                    not isinstance(issue_id, str)
                    or issue_id not in top_level_issue_ids
                    for issue_id in entry["issue_ids"]
                ):
                    _fail(
                        "llm_document_view_v2_unknown_column_issue_invalid"
                    )

        expected_first = 0
        previous_page = 0
        row_ordinal = {item["row_id"]: item["ordinal"] for item in rows}
        for part in parts:
            _claim(
                part["source_part_id"],
                document_source_part_ids,
                "source_part",
            )
            _validate_sources(part["sources"], anchors)
            if len(part["sources"]) != 1:
                _fail("llm_document_view_v2_source_part_pointer_invalid")
            pointer = part["sources"][0]
            if (
                not _positive_int(part["page"])
                or part["page"] > source_parts_total
                or (
                    pointer["format"] == "PDF"
                    and pointer.get("page") != part["page"]
                )
            ):
                _fail("llm_document_view_v2_source_part_page_invalid")
            first = row_ordinal.get(part["first_row_id"])
            last = row_ordinal.get(part["last_row_id"])
            if first != expected_first or last is None or first > last:
                _fail("llm_document_view_v2_source_part_row_range_invalid")
            for row in rows[first : last + 1]:
                _require_pointer_page(
                    row["sources"],
                    part["page"],
                    "row_source_part",
                )
                for entry in row["entries"]:
                    _require_pointer_page(
                        entry["sources"],
                        part["page"],
                        "entry_source_part",
                    )
            expected_first = last + 1
            if part["page"] <= previous_page:
                _fail("llm_document_view_v2_source_part_page_order_invalid")
            previous_page = part["page"]
        if expected_first != len(rows):
            _fail("llm_document_view_v2_source_part_tail_invalid")
        statuses = [part["continuation_status"] for part in parts]
        expected = (
            ["SINGLE"]
            if len(parts) == 1
            else ["START", *(["CONTINUATION"] * (len(parts) - 2)), "END"]
        )
        if statuses != expected:
            _fail("llm_document_view_v2_continuation_invalid")

    @staticmethod
    def _decode(raw: str | bytes) -> str:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        except UnicodeDecodeError as exc:
            raise ManagedDocumentLlmViewV2AuditError(
                "llm_document_view_v2_utf8_invalid"
            ) from exc
        if text.startswith("\ufeff"):
            _fail("llm_document_view_v2_bom_forbidden")
        if "\r" in text:
            _fail("llm_document_view_v2_cr_forbidden")
        if not text.endswith("\n") or text.endswith("\n\n"):
            _fail("llm_document_view_v2_final_lf_invalid")
        if "\n\n" in text:
            _fail("llm_document_view_v2_empty_line_forbidden")
        return text


class _Cursor:
    def __init__(self, text: str) -> None:
        self._lines = text.removesuffix("\n").split("\n")
        self._index = 0

    def peek(self) -> str:
        if self._index >= len(self._lines):
            _fail("llm_document_view_v2_unexpected_end")
        return self._lines[self._index]

    def marker(self, expected: str) -> None:
        if self.peek() != expected:
            _fail(f"llm_document_view_v2_marker_invalid:{expected}")
        self._index += 1

    def value(self, tag: str, expected_type: Any) -> Any:
        prefix = f"{tag} "
        line = self.peek()
        if not line.startswith(prefix):
            _fail(f"llm_document_view_v2_tag_invalid:{tag}")
        value = _parse_json(line[len(prefix) :])
        if not _matches_type(value, expected_type):
            _fail(f"llm_document_view_v2_value_type_invalid:{tag}")
        self._index += 1
        return value

    def require_end(self) -> None:
        if self._index != len(self._lines):
            _fail("llm_document_view_v2_trailing_content")


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise ManagedDocumentLlmViewV2AuditError(
            "llm_document_view_v2_json_invalid"
        ) from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail("llm_document_view_v2_duplicate_json_key")
        value[key] = item
    return value


def _reject_non_finite_json_constant(_: str) -> None:
    _fail("llm_document_view_v2_non_finite_number_forbidden")


def _matches_type(value: Any, expected: Any) -> bool:
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(expected, tuple):
        return any(_matches_type(value, item) for item in expected)
    return isinstance(value, expected)


def _validate_pointer(pointer: Any) -> None:
    if not isinstance(pointer, dict):
        _fail("llm_document_view_v2_pointer_type_invalid")
    if not set(pointer) <= _SAFE_POINTER_KEYS:
        _fail("llm_document_view_v2_pointer_field_forbidden")
    required = {"anchor_id", "format", "source_part_index"}
    if not required <= set(pointer):
        _fail("llm_document_view_v2_pointer_required_field_missing")
    if (
        not isinstance(pointer["anchor_id"], str)
        or not isinstance(pointer["format"], str)
        or not _positive_int(pointer["source_part_index"])
    ):
        _fail("llm_document_view_v2_pointer_value_invalid")
    for key in set(pointer) - {"anchor_id", "format"}:
        if not _positive_int(pointer[key], allow_zero=key == "ordinal"):
            _fail("llm_document_view_v2_pointer_value_invalid")
    if pointer["format"] == "PDF" and "page" not in pointer:
        _fail("llm_document_view_v2_pdf_pointer_page_missing")
    if pointer["format"] == "CSV" and not {
        "row_start",
        "row_end",
        "column_start",
        "column_end",
    } <= set(pointer):
        _fail("llm_document_view_v2_csv_pointer_range_missing")
    if pointer["format"] == "HTML" and "ordinal" not in pointer:
        _fail("llm_document_view_v2_html_pointer_ordinal_missing")


def _validate_sources(
    sources: Any, anchors: dict[str, dict[str, Any]]
) -> None:
    if not isinstance(sources, list):
        _fail("llm_document_view_v2_sources_type_invalid")
    seen: set[str] = set()
    for pointer in sources:
        _validate_pointer(pointer)
        anchor_id = pointer["anchor_id"]
        if anchor_id in seen or anchors.get(anchor_id) != pointer:
            _fail("llm_document_view_v2_source_pointer_invalid")
        seen.add(anchor_id)


def _require_pointer_page(
    sources: list[dict[str, Any]], page: int, label: str
) -> None:
    if any(
        pointer["format"] == "PDF" and pointer.get("page") != page
        for pointer in sources
    ):
        _fail(f"llm_document_view_v2_{label}_page_mismatch")


def _validate_source_context(value: Any, source_format: str) -> None:
    if not isinstance(value, dict) or set(value) != {
        "mime_type",
        "source_details",
    }:
        _fail("llm_document_view_v2_source_context_shape_invalid")
    if (
        not isinstance(value["mime_type"], str)
        or not 1 <= len(value["mime_type"]) <= 128
    ):
        _fail("llm_document_view_v2_source_context_mime_invalid")
    details = value["source_details"]
    if not isinstance(details, dict) or details.get("kind") != source_format:
        _fail("llm_document_view_v2_source_details_invalid")
    expected_keys = {
        "PDF": {"kind", "encrypted_status"},
        "HTML": {"kind"},
        "CSV": {"kind", "row_count"},
        "XLSX": {"kind", "sheet_count", "formula_status"},
        "XLS": {"kind", "sheet_count", "formula_status"},
        "UNKNOWN": {"kind", "reason"},
    }.get(source_format)
    if expected_keys is None or set(details) != expected_keys:
        _fail("llm_document_view_v2_source_details_invalid")
    if source_format == "PDF" and details["encrypted_status"] not in {
        "UNKNOWN",
        "NOT_ENCRYPTED",
        "ENCRYPTED_UNLOCKED",
        "ENCRYPTED_BLOCKED",
    }:
        _fail("llm_document_view_v2_source_details_invalid")
    if source_format == "CSV" and not _nonnegative_int(
        details["row_count"]
    ):
        _fail("llm_document_view_v2_source_details_invalid")
    if source_format in {"XLSX", "XLS"} and (
        not _nonnegative_int(details["sheet_count"])
        or details["formula_status"]
        not in {"NONE", "PRESENT", "UNKNOWN", "UNSUPPORTED"}
    ):
        _fail("llm_document_view_v2_source_details_invalid")
    if source_format == "UNKNOWN" and (
        not isinstance(details["reason"], str)
        or not 1 <= len(details["reason"]) <= 512
    ):
        _fail("llm_document_view_v2_source_details_invalid")


def _reject_forbidden_surface(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = "".join(
                character
                for character in key.casefold()
                if character.isalnum()
            )
            if key != "private_source_available" and any(
                token in normalized
                for token in (
                    "bbox",
                    "checksum",
                    "artifactref",
                    "continuationevidence",
                    "privateartifact",
                    "privatelocator",
                    "geometry",
                    "confidence",
                    "sourceword",
                    "documentid",
                    "coordinate",
                )
            ):
                _fail("llm_document_view_v2_private_field_forbidden")
            _reject_forbidden_surface(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_surface(item)


def _unique(items: list[dict[str, Any]], key: str, label: str) -> None:
    try:
        values = [item[key] for item in items]
    except (KeyError, TypeError) as exc:
        raise ManagedDocumentLlmViewV2AuditError(
            f"llm_document_view_v2_{label}_shape_invalid"
        ) from exc
    if len(values) != len(set(values)):
        _fail(f"llm_document_view_v2_duplicate_{label}")


def _claim(value: str, claimed: set[str], label: str) -> None:
    if value in claimed:
        _fail(f"llm_document_view_v2_duplicate_{label}")
    claimed.add(value)


def _continuous(items: list[dict[str, Any]], label: str) -> None:
    if [item["ordinal"] for item in items] != list(range(len(items))):
        _fail(f"llm_document_view_v2_{label}_order_invalid")


def _positive_int(value: Any, *, allow_zero: bool = False) -> bool:
    minimum = 0 if allow_zero else 1
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _fail(code: str) -> None:
    raise ManagedDocumentLlmViewV2AuditError(code)
