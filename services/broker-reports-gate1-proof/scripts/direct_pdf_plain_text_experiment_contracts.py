from __future__ import annotations

import hashlib
import re
from typing import Any

from direct_pdf_experiment_contracts import normalize_cell


EXPERIMENT_VERSION = "broker_reports_direct_pdf_plain_text_experiment_v1"
PROMPT_VERSION = "broker_reports_direct_pdf_plain_text_prompts_v1"
TARGET_PROMPT_VERSION = "broker_reports_direct_pdf_plain_text_target_identity_fix_v2"
TARGET_KEYS = ("1:1", "1:2", "1:3", "2:2", "3:2", "4:1", "4:2", "5:3", "5:4")
REPEAT_TARGET_KEYS = ("1:2", "1:3", "4:1")

_TABLE_START = re.compile(r"^TABLE page=(\d+) order=(\d+)$")
_HEADER_ROWS = re.compile(r"^HEADER_ROWS=(\d+)$")
_NO_TABLE = re.compile(r"^NO_TABLE page=(\d+) order=(\d+)$")
_PAGE = re.compile(r"^PAGE (\d+)$")
_INVENTORY_TABLE = re.compile(r"^TABLE (\d+)$")
_PAGE_REFERENCE = re.compile(r"(?i)(?:\[?PAGE\s+|\bp\.\s*)(\d+)\]?")
_NUMERIC_LIKE = re.compile(r"^[+\-]?[\d\s]+(?:[.,]\d+)?$")


def explanation_prompt() -> str:
    return (
        "Read the complete attached PDF and explain in concise plain text what the document is, its major "
        "sections, the types of financial information present, how the sections relate, which parts appear to "
        "continue tables from earlier pages, and what is uncertain or difficult to read. Every substantive bullet "
        "must begin with one or more exact page references such as [PAGE 2] or [PAGE 3, PAGE 4]. Separate observed "
        "document content from uncertainty. Do not transcribe every cell, calculate tax, create a declaration, or "
        "return JSON. Do not infer facts that are not visible in the PDF. Use only the attached PDF."
    )


def inventory_prompt() -> str:
    return (
        "Inspect the entire attached PDF and independently inventory every visible table. Do not assume an expected "
        "table count. Return only the following plain line-oriented format, with one block per table in page-local "
        "visual order:\n\n"
        "PAGE 1\nTABLE 1\nPURPOSE: concise observed purpose\nROWS_VISIBLE: integer or UNKNOWN\n"
        "COLUMNS_VISIBLE: integer or UNKNOWN\nHEADER_ROWS: integer or UNKNOWN\n"
        "CONTINUES_ON_PAGE: source page number if this is a continuation from an earlier page, otherwise NONE or "
        "UNKNOWN\nUNCERTAINTY: NONE or concise uncertainty\n\n"
        "Repeat PAGE and TABLE blocks as needed. Do not return JSON, Markdown fences, table cells, expected-count "
        "commentary, or a summary outside the blocks. Use only the attached PDF."
    )


def transcription_prompt(*, page: int | None = None, order: int | None = None) -> str:
    scope = (
        "Transcribe every visible table in the complete attached PDF in page-local visual order."
        if page is None
        else f"From the complete attached PDF, transcribe only table {order} on page {page}."
    )
    empty = (
        "If no tables exist, return exactly NO_TABLES."
        if page is None
        else f"If that table does not exist, return exactly NO_TABLE page={page} order={order}."
    )
    example_page = page or 1
    example_order = order or 1
    return (
        f"{scope} Return only this minimal line-oriented format:\n\n"
        f"TABLE page={example_page} order={example_order}\nHEADER_ROWS=2\nROW|cell 1|cell 2|cell 3\n"
        "ROW|cell 1|cell 2|cell 3\nEND_TABLE\n\n"
        "Preserve empty cells as empty fields between separators. Preserve every visible row, cell position, digit, "
        "sign, decimal separator, whitespace-separated token, and repeated row. Do not summarize, merge repeated "
        "rows, calculate, normalize, repair, or invent values. Use one ROW line per visible row. Mark an uncertain "
        "cell by prefixing its otherwise exact text with ?UNCERTAIN:. Do not add row numbers unless they are visible "
        "source cells. Do not use JSON, Markdown fences, aligned Markdown tables, or commentary inside or outside "
        f"table blocks. Every table block must end with END_TABLE. {empty} Use only the attached PDF."
    )


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def parse_table_text(text: Any) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return _malformed("empty_response", 0, None, 0)
    significant = [(number, line) for number, line in enumerate(text.splitlines(), 1) if line.strip()]
    if len(significant) == 1 and significant[0][1].strip() == "NO_TABLES":
        return _valid_empty("no_tables")
    if len(significant) == 1:
        match = _NO_TABLE.fullmatch(significant[0][1].strip())
        if match:
            return _valid_empty("target_table_absent", int(match.group(1)), int(match.group(2)))

    tables: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    index = 0
    last_identity: str | None = None
    last_row = 0

    def fail(error: str, line_number: int, trailing: str | None = None) -> dict[str, Any]:
        return _malformed(error, line_number, last_identity, last_row, trailing, tables)

    while index < len(significant):
        line_number, raw = significant[index]
        match = _TABLE_START.fullmatch(raw.strip())
        if not match:
            return fail("table_start_expected", line_number, raw)
        page, order = int(match.group(1)), int(match.group(2))
        identity = (page, order)
        last_identity = f"{page}:{order}"
        last_row = 0
        if page < 1 or order < 1 or identity in seen:
            return fail("table_identity_invalid", line_number, raw)
        seen.add(identity)
        index += 1
        if index >= len(significant):
            return fail("header_rows_missing", line_number)
        header_line_number, header_raw = significant[index]
        header_match = _HEADER_ROWS.fullmatch(header_raw.strip())
        if not header_match:
            return fail("header_rows_invalid", header_line_number, header_raw)
        header_rows = int(header_match.group(1))
        index += 1
        rows: list[list[str]] = []
        width: int | None = None
        ended = False
        while index < len(significant):
            row_line_number, row_raw = significant[index]
            if row_raw.strip() == "END_TABLE":
                ended = True
                index += 1
                break
            if not row_raw.startswith("ROW|"):
                return fail("row_or_end_table_expected", row_line_number, row_raw)
            cells = row_raw[4:].split("|")
            if width is None:
                width = len(cells)
            elif len(cells) != width:
                last_row += 1
                return fail("inconsistent_row_width", row_line_number, row_raw)
            rows.append(cells)
            last_row = len(rows)
            index += 1
        if not ended:
            return fail("end_table_missing", significant[-1][0])
        if header_rows > len(rows):
            return fail("header_rows_exceed_rows", header_line_number)
        tables.append(
            {
                "page": page,
                "order_on_page": order,
                "header_rows": header_rows,
                "row_count": len(rows),
                "column_count": width or 0,
                "rows": [
                    {"row_kind": "header" if ordinal < header_rows else "data", "cells": cells}
                    for ordinal, cells in enumerate(rows)
                ],
            }
        )
    return {
        "parse_status": "valid",
        "validation_error": None,
        "valid_empty": False,
        "tables": tables,
        "last_complete_table": last_identity,
        "last_row_seen": last_row,
        "trailing_content": None,
    }


def parse_inventory_text(text: Any) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return _malformed_inventory("empty_response", 0)
    significant = [(number, line.strip()) for number, line in enumerate(text.splitlines(), 1) if line.strip()]
    tables: list[dict[str, Any]] = []
    current_page: int | None = None
    index = 0
    seen: set[tuple[int, int]] = set()
    fields = (
        "PURPOSE", "ROWS_VISIBLE", "COLUMNS_VISIBLE", "HEADER_ROWS", "CONTINUES_ON_PAGE", "UNCERTAINTY"
    )

    def fail(error: str, line_number: int, trailing: str | None = None) -> dict[str, Any]:
        return _malformed_inventory(error, line_number, trailing, tables)

    while index < len(significant):
        line_number, line = significant[index]
        page_match = _PAGE.fullmatch(line)
        if page_match:
            current_page = int(page_match.group(1))
            if current_page < 1:
                return fail("page_invalid", line_number, line)
            index += 1
            if index >= len(significant):
                return fail("table_missing_after_page", line_number, line)
            line_number, line = significant[index]
        if current_page is None:
            return fail("page_expected", line_number, line)
        table_match = _INVENTORY_TABLE.fullmatch(line)
        if not table_match:
            return fail("table_expected", line_number, line)
        order = int(table_match.group(1))
        identity = (current_page, order)
        if order < 1 or identity in seen:
            return fail("table_identity_invalid", line_number, line)
        seen.add(identity)
        index += 1
        values: dict[str, str] = {}
        for field in fields:
            if index >= len(significant):
                return fail(f"{field.lower()}_missing", line_number)
            field_line_number, field_line = significant[index]
            prefix = field + ":"
            if not field_line.startswith(prefix):
                return fail(f"{field.lower()}_invalid", field_line_number, field_line)
            value = field_line[len(prefix):].strip()
            if not value:
                return fail(f"{field.lower()}_empty", field_line_number, field_line)
            values[field] = value
            index += 1
        try:
            rows = _count_or_unknown(values["ROWS_VISIBLE"])
            columns = _count_or_unknown(values["COLUMNS_VISIBLE"])
            header_rows = _count_or_unknown(values["HEADER_ROWS"])
            continues = _continuation_or_unknown(values["CONTINUES_ON_PAGE"])
        except ValueError as exc:
            return fail(str(exc), line_number)
        tables.append(
            {
                "page": current_page,
                "order_on_page": order,
                "purpose": values["PURPOSE"],
                "rows_visible": rows,
                "columns_visible": columns,
                "header_rows": header_rows,
                "continues_on_page": continues,
                "uncertainty": values["UNCERTAINTY"],
            }
        )
    return {"parse_status": "valid", "validation_error": None, "tables": tables}


def assess_explanation(text: Any, page_count: int) -> dict[str, Any]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    substantive = [line for line in lines if not line.startswith(("#", "```"))]
    invalid_refs = 0
    referenced_lines = 0
    pages: set[int] = set()
    numeric_lines = 0
    for line in substantive:
        refs = [int(value) for value in _PAGE_REFERENCE.findall(line)]
        if refs:
            referenced_lines += 1
            pages.update(value for value in refs if 1 <= value <= page_count)
            invalid_refs += sum(value < 1 or value > page_count for value in refs)
        without_refs = _PAGE_REFERENCE.sub("", line)
        numeric_lines += bool(re.search(r"\d", without_refs))
    return {
        "response_nonempty": bool(str(text or "").strip()),
        "substantive_lines": len(substantive),
        "lines_with_page_reference": referenced_lines,
        "page_reference_coverage": _ratio(referenced_lines, len(substantive)),
        "distinct_valid_pages_referenced": len(pages),
        "invalid_page_references": invalid_refs,
        "lines_with_numeric_statements_excluding_page_labels": numeric_lines,
        "semantic_correctness_requires_independent_review": True,
    }


def assess_inventory(reference: dict[str, dict[str, Any]], parsed: dict[str, Any]) -> dict[str, Any]:
    raw_predicted = {
        f"{table['page']}:{table['order_on_page']}": table for table in parsed.get("tables", [])
    }
    predicted = raw_predicted if parsed.get("parse_status") == "valid" else {}
    reference_keys = set(reference)
    predicted_keys = set(predicted)
    row_exact = column_exact = header_exact = header_total = 0
    raw_row_exact = raw_column_exact = raw_header_exact = 0
    for key, expected in reference.items():
        actual = predicted.get(key)
        raw_actual = raw_predicted.get(key)
        row_exact += bool(actual and actual.get("rows_visible") == len(expected["cells"]))
        raw_row_exact += bool(raw_actual and raw_actual.get("rows_visible") == len(expected["cells"]))
        expected_columns = max((len(row) for row in expected["cells"]), default=0)
        column_exact += bool(actual and actual.get("columns_visible") == expected_columns)
        raw_column_exact += bool(raw_actual and raw_actual.get("columns_visible") == expected_columns)
        if expected.get("header_rows") is not None:
            header_total += 1
            header_exact += bool(actual and actual.get("header_rows") == expected["header_rows"])
            raw_header_exact += bool(raw_actual and raw_actual.get("header_rows") == expected["header_rows"])
    continuation = predicted.get("4:1")
    raw_continuation = raw_predicted.get("4:1")
    return {
        "validation_error": parsed.get("validation_error"),
        "reference_tables": len(reference_keys),
        "returned_tables": len(predicted_keys),
        "matched_tables": len(reference_keys & predicted_keys),
        "missed_tables": len(reference_keys - predicted_keys),
        "false_tables": len(predicted_keys - reference_keys),
        "table_detection_recall": _ratio(len(reference_keys & predicted_keys), len(reference_keys)),
        "exact_row_counts": row_exact,
        "exact_column_counts": column_exact,
        "exact_header_counts": header_exact,
        "header_tables_scored": header_total,
        "continuation_4_1_from_page_3": bool(continuation and continuation.get("continues_on_page") == 3),
        "tables_with_nonempty_purpose": sum(bool(item.get("purpose", "").strip()) for item in predicted.values()),
        "purpose_accuracy_requires_independent_review": True,
        "raw_complete_blocks_before_error": len(raw_predicted),
        "raw_prefix_matched_tables": len(reference_keys & set(raw_predicted)),
        "raw_prefix_false_tables": len(set(raw_predicted) - reference_keys),
        "raw_prefix_exact_row_counts": raw_row_exact,
        "raw_prefix_exact_column_counts": raw_column_exact,
        "raw_prefix_exact_header_counts": raw_header_exact,
        "raw_prefix_continuation_4_1_from_page_3": bool(
            raw_continuation and raw_continuation.get("continues_on_page") == 3
        ),
        "raw_prefix_tables_with_nonempty_purpose": sum(
            bool(item.get("purpose", "").strip()) for item in raw_predicted.values()
        ),
    }


def score_selected_reference(reference: dict[str, dict[str, Any]], parsed: dict[str, Any]) -> dict[str, Any]:
    predicted = (
        {f"{table['page']}:{table['order_on_page']}": table for table in parsed.get("tables", [])}
        if parsed.get("parse_status") == "valid"
        else {}
    )
    cells_exact = cells_total = numeric_exact = numeric_total = 0
    exact_prefix_structures = exact_headers = hallucinated = omitted = 0
    empty_exact = empty_total = 0
    for key, expected in reference.items():
        table = predicted.get(key)
        actual_rows = [row["cells"] for row in table.get("rows", [])] if table else []
        expected_rows = expected["cells"]
        columns = max((len(row) for row in expected_rows), default=0)
        exact_prefix_structures += bool(
            table
            and len(actual_rows) >= len(expected_rows)
            and all(len(row) == columns for row in actual_rows[: len(expected_rows)])
        )
        exact_headers += bool(table and table.get("header_rows") == expected.get("header_rows"))
        for row_ordinal, expected_row in enumerate(expected_rows):
            for column_ordinal in range(columns):
                left = normalize_cell(expected_row[column_ordinal] if column_ordinal < len(expected_row) else "")
                right = normalize_cell(
                    actual_rows[row_ordinal][column_ordinal]
                    if row_ordinal < len(actual_rows) and column_ordinal < len(actual_rows[row_ordinal])
                    else ""
                )
                cells_total += 1
                cells_exact += left == right
                if not left:
                    empty_total += 1
                    empty_exact += not right
                if _numeric(left):
                    numeric_total += 1
                    numeric_exact += left == right
                hallucinated += not left and bool(right)
                omitted += bool(left) and not right
    return {
        "reference_tables": len(reference),
        "matched_tables": len(set(reference) & set(predicted)),
        "exact_selected_prefix_structures": exact_prefix_structures,
        "exact_headers": exact_headers,
        "cells_exact": cells_exact,
        "cells_total": cells_total,
        "cell_accuracy": _ratio(cells_exact, cells_total),
        "numeric_exact": numeric_exact,
        "numeric_total": numeric_total,
        "numeric_accuracy": _ratio(numeric_exact, numeric_total),
        "empty_cells_exact": empty_exact,
        "empty_cells_total": empty_total,
        "empty_cell_accuracy": _ratio(empty_exact, empty_total),
        "hallucinated_nonempty_cells": hallucinated,
        "omitted_nonempty_cells": omitted,
        "additional_rows_outside_selected_draft_scored": False,
    }


def _count_or_unknown(value: str) -> int | None:
    if value == "UNKNOWN":
        return None
    if value.isdigit():
        return int(value)
    raise ValueError("inventory_count_invalid")


def _continuation_or_unknown(value: str) -> int | None:
    if value in {"NONE", "UNKNOWN"}:
        return None
    if value.isdigit() and int(value) > 0:
        return int(value)
    raise ValueError("inventory_continuation_invalid")


def _numeric(value: str) -> bool:
    return bool(value and _NUMERIC_LIKE.fullmatch(value))


def _ratio(left: int, right: int) -> float | None:
    return round(left / right, 6) if right else None


def _valid_empty(reason: str, page: int | None = None, order: int | None = None) -> dict[str, Any]:
    return {
        "parse_status": "valid_empty",
        "validation_error": None,
        "valid_empty": True,
        "empty_reason": reason,
        "requested_page": page,
        "requested_order": order,
        "tables": [],
        "last_complete_table": None,
        "last_row_seen": 0,
        "trailing_content": None,
    }


def _malformed(
    error: str,
    line_number: int,
    identity: str | None,
    row: int,
    trailing: str | None = None,
    tables: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "parse_status": "malformed",
        "validation_error": error,
        "valid_empty": False,
        "tables": list(tables or []),
        "error_line": line_number,
        "last_complete_table": identity,
        "last_row_seen": row,
        "trailing_content": trailing,
    }


def _malformed_inventory(
    error: str,
    line_number: int,
    trailing: str | None = None,
    tables: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "parse_status": "malformed",
        "validation_error": error,
        "tables": list(tables or []),
        "error_line": line_number,
        "trailing_content": trailing,
    }
