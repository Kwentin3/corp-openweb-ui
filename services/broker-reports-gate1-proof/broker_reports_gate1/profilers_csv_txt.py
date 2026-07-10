from __future__ import annotations

import csv
from html.parser import HTMLParser
from io import StringIO

from .blockers import parser_failed
from .contracts import profile_id, slice_id


def decode_text_bytes(content_bytes: bytes) -> tuple[str | None, str | None, str | None]:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return content_bytes.decode(encoding), encoding, None
        except UnicodeDecodeError:
            continue
    return None, None, "decode_failed"


def profile_csv(run_id: str, document_id: str, content_bytes: bytes) -> tuple[dict, list[dict], list[dict]]:
    decoded, encoding, error = decode_text_bytes(content_bytes)
    if decoded is None:
        blocker = parser_failed(run_id, document_id, error or "decode_failed")
        return _blocked_profile(document_id, "csv", [blocker["blocker_id"]]), [], [blocker]

    try:
        delimiter = _detect_delimiter(decoded)
        rows = list(csv.reader(StringIO(decoded), delimiter=delimiter))
    except csv.Error as exc:
        blocker = parser_failed(run_id, document_id, f"csv_parse_failed:{exc.__class__.__name__}")
        return _blocked_profile(document_id, "csv", [blocker["blocker_id"]]), [], [blocker]

    columns_count = max((len(row) for row in rows), default=0)
    header_candidate = _looks_like_header(rows)
    current_profile_id = profile_id(document_id)
    slice_rows = rows[:5]
    private_slice = {
        "slice_id": slice_id(document_id, "table_001"),
        "document_id": document_id,
        "profile_id": current_profile_id,
        "slice_type": "table_rows",
        "source_location": {
            "kind": "csv_rows",
            "start_row": 1 if rows else 0,
            "end_row": min(len(rows), 5),
        },
        "location": {
            "kind": "csv_rows",
            "start_row": 1 if rows else 0,
            "end_row": min(len(rows), 5),
        },
        "bounded": True,
        "rows_in_slice": len(slice_rows),
        "rows_count": len(slice_rows),
        "columns_count": columns_count,
        "row_range": [1, len(slice_rows)] if slice_rows else [0, 0],
        "column_policy": "first_detected_columns",
        "cells": slice_rows,
        "rows": slice_rows,
        "truncated": len(rows) > len(slice_rows),
        "parser": "python_stdlib_csv",
        "created_for_gate": "gate1",
    }
    profile = {
        "profile_id": current_profile_id,
        "document_id": document_id,
        "container_format": "csv",
        "parser": "python_stdlib_csv",
        "parser_version": "1",
        "profile_status": "profiled",
        "machine_readable": "yes",
        "machine_readable_table": True,
        "encoding": encoding,
        "delimiter": delimiter,
        "rows_count": len(rows),
        "columns_count": columns_count,
        "header_candidate": header_candidate,
        "slice_truncated": private_slice["truncated"],
        "normalized_slice_refs": [private_slice["slice_id"]],
        "warnings": [] if rows else ["empty_csv"],
        "blocker_refs": [],
    }
    return profile, [private_slice], []


def profile_txt(
    run_id: str,
    document_id: str,
    content_bytes: bytes,
    *,
    container_format: str = "txt",
    text_subtype: str = "plain_text",
) -> tuple[dict, list[dict], list[dict]]:
    decoded, encoding, error = decode_text_bytes(content_bytes)
    if decoded is None:
        blocker = parser_failed(run_id, document_id, error or "decode_failed")
        return _blocked_profile(document_id, container_format, [blocker["blocker_id"]]), [], [blocker]

    table_candidate = False
    table_rows: list[list[str]] = []
    html_table_count = 0
    html_table_columns_max = 0
    clean_text = decoded
    if text_subtype == "html_text":
        extractor = _HtmlTextExtractor()
        extractor.feed(decoded)
        clean_text = extractor.clean_text()
        table_candidate = extractor.table_candidate
        table_rows = extractor.table_rows
        html_table_count = extractor.table_count
        html_table_columns_max = extractor.max_cells_in_row

    lines = clean_text.splitlines()
    nonblank_sections = 0
    in_section = False
    for line in lines:
        if line.strip():
            if not in_section:
                nonblank_sections += 1
            in_section = True
        else:
            in_section = False

    snippet_lines = lines[:20]
    snippet_source = "\n".join(snippet_lines)
    snippet = snippet_source[:2000]
    current_profile_id = profile_id(document_id)
    private_slice = {
        "slice_id": slice_id(document_id, "text_001"),
        "document_id": document_id,
        "profile_id": current_profile_id,
        "slice_type": "text_excerpt",
        "source_location": {
            "kind": "text_lines",
            "start_line": 1 if lines else 0,
            "end_line": min(len(lines), len(snippet_lines)),
        },
        "location": {
            "kind": "text_lines",
            "start_line": 1 if lines else 0,
            "end_line": min(len(lines), len(snippet_lines)),
        },
        "bounded": True,
        "characters_in_slice": len(snippet),
        "chars_count": len(snippet),
        "truncated": len(snippet_source) > len(snippet) or len(lines) > len(snippet_lines),
        "parser": "python_html_text_decode" if text_subtype == "html_text" else "python_text_decode",
        "created_for_gate": "gate1",
        "text": snippet,
    }
    private_slices = [private_slice]
    normalized_slice_refs = [private_slice["slice_id"]]
    if table_rows:
        slice_rows = table_rows[:10]
        table_slice = {
            "slice_id": slice_id(document_id, "html_table_001"),
            "document_id": document_id,
            "profile_id": current_profile_id,
            "slice_type": "table_rows",
            "source_location": {
                "kind": "html_table_rows",
                "start_row": 1,
                "end_row": len(slice_rows),
            },
            "location": {
                "kind": "html_table_rows",
                "start_row": 1,
                "end_row": len(slice_rows),
            },
            "bounded": True,
            "rows_in_slice": len(slice_rows),
            "rows_count": len(slice_rows),
            "columns_count": max((len(row) for row in slice_rows), default=0),
            "row_range": [1, len(slice_rows)],
            "column_policy": "html_first_detected_table_cells",
            "cells": slice_rows,
            "rows": slice_rows,
            "truncated": len(table_rows) > len(slice_rows),
            "parser": "python_html_table_decode",
            "created_for_gate": "gate1",
        }
        private_slices.append(table_slice)
        normalized_slice_refs.append(table_slice["slice_id"])

    profile = {
        "profile_id": current_profile_id,
        "document_id": document_id,
        "container_format": container_format,
        "parser": "python_html_text_decode" if text_subtype == "html_text" else "python_text_decode",
        "parser_version": "1",
        "profile_status": "profiled",
        "machine_readable": "conditional",
        "machine_readable_table": bool(table_rows),
        "text_subtype": text_subtype,
        "encoding": encoding,
        "line_count": len(lines),
        "section_count": nonblank_sections,
        "clean_text_available": bool(clean_text.strip()),
        "table_candidate": table_candidate,
        "html_table_count": html_table_count,
        "html_table_rows_count": len(table_rows),
        "html_table_columns_max": html_table_columns_max,
        "slice_truncated": any(item.get("truncated") for item in private_slices),
        "normalized_slice_refs": normalized_slice_refs,
        "warnings": [] if clean_text else ["empty_text"],
        "blocker_refs": [],
    }
    return profile, private_slices, []


def _detect_delimiter(decoded: str) -> str:
    sample = decoded[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        candidates = [",", ";", "\t", "|"]
        return max(candidates, key=lambda item: sample.count(item))


def _looks_like_header(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    first = rows[0]
    if not first:
        return False
    text_cells = sum(1 for cell in first if any(ch.isalpha() for ch in cell))
    numeric_cells = sum(1 for cell in first if _is_number(cell))
    return text_cells > 0 and numeric_cells == 0


def _is_number(value: str) -> bool:
    try:
        float(str(value).strip())
    except ValueError:
        return False
    return True


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0
        self._table_depth = 0
        self._in_row = False
        self._current_row: list[str] = []
        self._current_cell: list[str] | None = None
        self.table_candidate = False
        self.table_count = 0
        self.table_rows: list[list[str]] = []
        self.max_cells_in_row = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
        if tag == "table":
            self._table_depth += 1
            self.table_count += 1
            self.table_candidate = True
        if tag == "tr" and self._table_depth:
            self._in_row = True
            self._current_row = []
        if tag in {"td", "th"} and self._in_row:
            self._current_cell = []
        if tag in {"br", "p", "div", "tr", "td", "th", "li", "section", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "table":
            self._table_depth = max(0, self._table_depth - 1)
        if tag in {"td", "th"} and self._current_cell is not None:
            cell = " ".join(" ".join(self._current_cell).split())
            self._current_row.append(cell)
            self._current_cell = None
        if tag == "tr" and self._in_row:
            row = [cell for cell in self._current_row if cell]
            if row:
                self.table_rows.append(row)
                self.max_cells_in_row = max(self.max_cells_in_row, len(row))
            self._current_row = []
            self._current_cell = None
            self._in_row = False
        if tag in {"p", "div", "tr", "td", "th", "li", "section", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._parts.append(text)
            if self._table_depth:
                self.table_candidate = True
            if self._current_cell is not None:
                self._current_cell.append(text)

    def clean_text(self) -> str:
        lines = []
        for line in "\n".join(self._parts).splitlines():
            stripped = " ".join(line.split())
            if stripped:
                lines.append(stripped)
        return "\n".join(lines)


def _blocked_profile(document_id: str, container: str, blocker_refs: list[str]) -> dict:
    return {
        "profile_id": profile_id(document_id),
        "document_id": document_id,
        "container_format": container,
        "parser": "python_text_decode" if container in {"txt", "html_text"} else "python_stdlib_csv",
        "parser_version": "1",
        "profile_status": "blocked",
        "machine_readable": "unknown",
        "machine_readable_table": False,
        "normalized_slice_refs": [],
        "warnings": ["parser_failed"],
        "blocker_refs": blocker_refs,
    }
