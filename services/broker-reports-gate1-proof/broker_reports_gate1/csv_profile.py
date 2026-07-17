from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import StringIO
from typing import Any


CSV_SUPPORTED_PROFILE_ID = "broker_reports_csv_supported_profile_v1"
CSV_PARSER_POLICY_VERSION = "broker_reports_csv_parser_policy_v1"

FACTORY_REQUIRED = (
    "CsvSupportedProfileFactory.create is the only production supported-CSV parser entrypoint"
)
FORBIDDEN = (
    "Profilers, normalizers and smoke scripts must not guess a delimiter, silently repair malformed CSV or truncate accepted rows"
)


class CsvSupportedProfileError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CsvSupportedProfileConfig:
    max_input_bytes: int = 5_000_000
    max_rows: int = 10_000
    max_cells: int = 100_000
    max_columns: int = 256
    max_field_characters: int = 32_000
    max_materialized_json_bytes: int = 20_000_000
    supported_delimiters: tuple[str, ...] = (",", ";", "\t", "|")


@dataclass(frozen=True)
class CsvSupportedParseResult:
    rows: list[list[str]]
    encoding: str
    delimiter: str
    rows_total: int
    data_rows_total: int
    blank_rows_total: int
    uneven_rows_total: int
    cells_total: int
    columns_total: int
    materialized_json_bytes: int

    def safe_profile(self) -> dict[str, Any]:
        return {
            "profile_id": CSV_SUPPORTED_PROFILE_ID,
            "parser_policy_version": CSV_PARSER_POLICY_VERSION,
            "support_status": "accepted",
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "header_policy": "first_logical_record_required_section_headers_preserved",
            "empty_row_policy": "preserved_and_deterministically_accounted",
            "uneven_record_policy": "preserve_literal_section_widths_no_padding_or_truncation",
            "quoting_policy": "double_quote_rfc_style_no_backslash_escape",
            "scope_kind": "whole_csv_logical_document",
            "rows_total": self.rows_total,
            "data_rows_total": self.data_rows_total,
            "blank_rows_total": self.blank_rows_total,
            "uneven_rows_total": self.uneven_rows_total,
            "cells_total": self.cells_total,
            "columns_total": self.columns_total,
            "materialized_json_bytes": self.materialized_json_bytes,
            "silent_truncation_allowed": False,
        }


class CsvSupportedProfileFactory:
    def __init__(self, config: CsvSupportedProfileConfig | None = None) -> None:
        self.config = config or CsvSupportedProfileConfig()

    def create(self) -> "CsvSupportedProfileParser":
        if self.config.max_input_bytes <= 0:
            raise CsvSupportedProfileError("csv_profile_input_budget_invalid")
        if self.config.max_rows <= 1:
            raise CsvSupportedProfileError("csv_profile_row_budget_invalid")
        if self.config.max_cells <= 0:
            raise CsvSupportedProfileError("csv_profile_cell_budget_invalid")
        if self.config.max_columns <= 0:
            raise CsvSupportedProfileError("csv_profile_column_budget_invalid")
        if self.config.max_field_characters <= 0:
            raise CsvSupportedProfileError("csv_profile_field_budget_invalid")
        if self.config.max_materialized_json_bytes <= 0:
            raise CsvSupportedProfileError("csv_profile_materialization_budget_invalid")
        if not self.config.supported_delimiters:
            raise CsvSupportedProfileError("csv_profile_delimiters_required")
        return CsvSupportedProfileParser(self.config)


class CsvSupportedProfileParser:
    def __init__(self, config: CsvSupportedProfileConfig) -> None:
        self.config = config

    def parse(self, content_bytes: bytes) -> CsvSupportedParseResult:
        if not content_bytes:
            raise CsvSupportedProfileError("csv_profile_empty_input")
        if len(content_bytes) > self.config.max_input_bytes:
            raise CsvSupportedProfileError("csv_profile_input_byte_budget_exceeded")
        decoded, encoding = _decode_supported_csv(content_bytes)
        if "\x00" in decoded:
            raise CsvSupportedProfileError("csv_profile_nul_character_forbidden")
        delimiter = self._detect_delimiter(decoded)
        try:
            rows = list(
                csv.reader(
                    StringIO(decoded, newline=""),
                    delimiter=delimiter,
                    quotechar='"',
                    doublequote=True,
                    escapechar=None,
                    skipinitialspace=False,
                    strict=True,
                )
            )
        except (csv.Error, UnicodeError):
            raise CsvSupportedProfileError("csv_profile_parse_failed") from None
        if not rows:
            raise CsvSupportedProfileError("csv_profile_header_required")
        if len(rows) > self.config.max_rows:
            raise CsvSupportedProfileError("csv_profile_row_budget_exceeded")

        header = rows[0]
        if len(header) < 2:
            raise CsvSupportedProfileError("csv_profile_header_requires_multiple_columns")
        if len(header) > self.config.max_columns:
            raise CsvSupportedProfileError("csv_profile_column_budget_exceeded")
        normalized_header = [cell.strip() for cell in header]
        if any(not cell for cell in normalized_header):
            raise CsvSupportedProfileError("csv_profile_header_cell_empty")
        if len(set(normalized_header)) != len(normalized_header):
            raise CsvSupportedProfileError("csv_profile_header_duplicate")

        cells_total = 0
        data_rows_total = 0
        blank_rows_total = 0
        uneven_rows_total = 0
        max_columns = len(header)
        for row_ordinal, row in enumerate(rows, start=1):
            cells_total += len(row)
            max_columns = max(max_columns, len(row))
            if len(row) > self.config.max_columns:
                raise CsvSupportedProfileError("csv_profile_column_budget_exceeded")
            if any(len(cell) > self.config.max_field_characters for cell in row):
                raise CsvSupportedProfileError("csv_profile_field_budget_exceeded")
            blank = not row or all(not cell.strip() for cell in row)
            if row_ordinal > 1 and blank:
                blank_rows_total += 1
                continue
            if row_ordinal > 1:
                data_rows_total += 1
                if len(row) != len(header):
                    uneven_rows_total += 1
        if cells_total > self.config.max_cells:
            raise CsvSupportedProfileError("csv_profile_cell_budget_exceeded")
        if data_rows_total == 0:
            raise CsvSupportedProfileError("csv_profile_data_row_required")

        materialized_bytes = len(
            json.dumps(
                {"cells": rows},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if materialized_bytes > self.config.max_materialized_json_bytes:
            raise CsvSupportedProfileError(
                "csv_profile_materialization_budget_exceeded"
            )
        return CsvSupportedParseResult(
            rows=rows,
            encoding=encoding,
            delimiter=delimiter,
            rows_total=len(rows),
            data_rows_total=data_rows_total,
            blank_rows_total=blank_rows_total,
            uneven_rows_total=uneven_rows_total,
            cells_total=cells_total,
            columns_total=max_columns,
            materialized_json_bytes=materialized_bytes,
        )

    def _detect_delimiter(self, decoded: str) -> str:
        sample = decoded[:8192]
        try:
            delimiter = csv.Sniffer().sniff(
                sample, delimiters="".join(self.config.supported_delimiters)
            ).delimiter
        except csv.Error:
            delimiter = self._deterministic_delimiter_fallback(decoded)
        if delimiter not in self.config.supported_delimiters:
            raise CsvSupportedProfileError("csv_profile_delimiter_unsupported")
        return delimiter

    def _deterministic_delimiter_fallback(self, decoded: str) -> str:
        candidates: list[tuple[tuple[int, int, int], str]] = []
        for delimiter in self.config.supported_delimiters:
            try:
                rows = list(
                    csv.reader(
                        StringIO(decoded, newline=""),
                        delimiter=delimiter,
                        quotechar='"',
                        doublequote=True,
                        escapechar=None,
                        skipinitialspace=False,
                        strict=True,
                    )
                )
            except csv.Error:
                continue
            if not rows or len(rows[0]) < 2:
                continue
            header_width = len(rows[0])
            multi_column_rows = sum(1 for row in rows if len(row) > 1)
            exact_width_rows = sum(1 for row in rows if len(row) == header_width)
            delimiter_occurrences = decoded.count(delimiter)
            candidates.append(
                (
                    (multi_column_rows, exact_width_rows, delimiter_occurrences),
                    delimiter,
                )
            )
        if not candidates:
            raise CsvSupportedProfileError("csv_profile_delimiter_ambiguous")
        candidates.sort(reverse=True)
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            raise CsvSupportedProfileError("csv_profile_delimiter_ambiguous")
        return candidates[0][1]


def _decode_supported_csv(content_bytes: bytes) -> tuple[str, str]:
    if content_bytes.startswith(b"\xef\xbb\xbf"):
        try:
            return content_bytes.decode("utf-8-sig"), "utf-8-sig"
        except UnicodeDecodeError:
            raise CsvSupportedProfileError("csv_profile_encoding_unsupported") from None
    try:
        return content_bytes.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return content_bytes.decode("cp1251"), "cp1251"
    except UnicodeDecodeError:
        raise CsvSupportedProfileError("csv_profile_encoding_unsupported") from None
