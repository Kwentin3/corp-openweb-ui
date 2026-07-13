from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .pdf_hybrid_contracts import (
    PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
    sha256_json,
    validate_binding_output_shape,
)


PDF_CSV_DIALECT_SCHEMA = "broker_reports_real_table_csv_dialect_v1"
PDF_CSV_TOPOLOGY_SCHEMA = "broker_reports_real_table_csv_topology_sidecar_v1"
PDF_CSV_EXPERIMENT_VERSION = "broker_reports_real_table_csv_vs_json_experiment_v1"
PDF_CSV_ENVELOPE_PREFIX = "CSV/1\n"
PDF_CSV_ENVELOPE_SEPARATOR = "\nSIDECAR/1\n"
PDF_CSV_ENVELOPE_SUFFIX = "\nEND/1"
FACTORY_REQUIRED = (
    "PdfCsvExperimentFactory.create is the only CSV parse, binding, topology, and comparison entrypoint"
)
FORBIDDEN = (
    "CSV experiment callers must not silently repair quoting, row width, candidate ids, topology, or source values"
)

_CANDIDATE_ID = re.compile(r"^[0-9a-z]+$")
_UNCERTAINTY_CODE = re.compile(r"^[a-z0-9_]{1,64}$")
_NUMERIC_LIKE = re.compile(r"^[+\-]?[\d\s]+(?:[.,]\d+)?$")
_FORBIDDEN_SIDECAR_KEYS = {
    "rows",
    "cells",
    "grid",
    "candidate",
    "candidates",
    "dictionary",
    "source_value",
    "source_value_ref",
    "word_ref",
}


class PdfCsvExperimentError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfCsvDialectConfig:
    schema_version: str = PDF_CSV_DIALECT_SCHEMA
    delimiter: str = ","
    quote_character: str = '"'
    candidate_separator: str = "+"
    newline: str = "\n"
    encoding: str = "utf-8"
    maximum_output_bytes: int = 512 * 1024
    maximum_topology_bytes: int = 4096


class PdfCsvExperimentFactory:
    def __init__(self, config: PdfCsvDialectConfig | None = None) -> None:
        self.config = config or PdfCsvDialectConfig()

    def create(self) -> "PdfCsvExperimentRuntime":
        if self.config.schema_version != PDF_CSV_DIALECT_SCHEMA:
            raise PdfCsvExperimentError("pdf_csv_dialect_version_invalid")
        if (
            self.config.delimiter != ","
            or self.config.quote_character != '"'
            or self.config.candidate_separator != "+"
            or self.config.newline != "\n"
            or self.config.encoding.lower() != "utf-8"
        ):
            raise PdfCsvExperimentError("pdf_csv_dialect_configuration_invalid")
        return PdfCsvExperimentRuntime(self.config)


class PdfCsvExperimentRuntime:
    def __init__(self, config: PdfCsvDialectConfig) -> None:
        self.config = config

    def dialect_contract(self) -> dict[str, Any]:
        return {
            "schema_version": self.config.schema_version,
            "encoding": "UTF-8 without BOM",
            "delimiter": ",",
            "quote_character": '"',
            "quote_escape": 'double quote as "" inside a quoted field',
            "newline": "LF only",
            "literal_line_break": "allowed only inside a correctly quoted field",
            "explicit_empty_cell": "zero-byte field",
            "candidate_cell": "one or more lowercase base36 ids joined by +",
            "fixed_row_width": True,
            "markdown_fences_forbidden": True,
            "trailing_commentary_forbidden": True,
            "silent_repair": False,
            "completion_rule": (
                "provider STOP plus byte-complete strict parse and expected dimensions"
            ),
        }

    def free_csv_prompt(self, *, table_identity: str) -> str:
        return (
            "Read only the attached raster crop as an independent visual transcription. "
            f"The opaque table identity is {table_identity}. Return only the visible table as CSV using "
            "UTF-8, comma delimiter, double-quote escaping, and LF row separators. Preserve every visible "
            "cell exactly: digits, signs, decimal separators, spaces, repeated rows, and explicit empty "
            "positions. Quote fields containing comma, quote, or line break. Do not merge rows, normalize, "
            "repair, summarize, calculate, add row numbers, add Markdown fences, or add commentary. The first "
            "byte must belong to the first CSV field and the final byte must belong to the CSV document."
        )

    def candidate_csv_prompt(
        self,
        *,
        evidence_package: dict[str, Any],
        topology_sidecar: bool,
        continuation: list[Any] | None,
    ) -> str:
        model = evidence_package.get("model_facing") or {}
        window = evidence_package.get("window") or {}
        candidate_records = model.get("c") or []
        row_count = int(window.get("row_count") or 0)
        column_count = int(window.get("column_count") or 0)
        header_depth = int((model.get("h") or [None, 0])[1] or 0)
        row_start = int(window.get("row_start") or 0)
        row_end = int(window.get("row_end") or 0)
        local_header_count = max(
            0,
            min(row_end, header_depth) - row_start + 1,
        )
        identity = {
            "package_id": evidence_package.get("package_id"),
            "crop_sha256": (evidence_package.get("crop_identity") or {}).get(
                "crop_sha256"
            ),
            "candidate_dictionary_hash": evidence_package.get(
                "candidate_dictionary_hash"
            ),
            "row_start": window.get("row_start"),
            "row_end": window.get("row_end"),
            "row_count": row_count,
            "column_count": column_count,
            "shared_header_hash": window.get("shared_header_hash"),
            "global_header_depth": header_depth,
            "continuation": continuation,
        }
        base = (
            "Place the supplied candidate ids into the attached raster table crop. Candidate records are "
            "[id, exact_source_text, mechanical_class, x0, y0, x1, y1]. Output exactly "
            f"{row_count} rows and {column_count} comma-separated fields per row. A non-empty field must contain "
            "only one lowercase base36 id or multiple ids joined by + in source reading order. An empty visual "
            "cell is a zero-byte field. Use every supplied id exactly once. Never output a financial value, "
            "source ref, explanation, Markdown fence, or commentary. Use UTF-8, double-quote escaping, and LF "
            "row separators. Do not split columns or repeat shared headers outside the declared rows.\n"
            "IDENTITY="
            + json.dumps(identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\nCANDIDATES="
            + json.dumps(candidate_records, ensure_ascii=False, separators=(",", ":"))
        )
        if not topology_sidecar:
            return (
                base
                + "\nReturn raw CSV only. The first byte is the first CSV field; byte-complete parsing and "
                "provider STOP are the terminal rule."
            )
        sidecar = {
            "v": PDF_CSV_TOPOLOGY_SCHEMA,
            "d": "b",
            "r": row_count,
            "c": column_count,
            "h": local_header_count,
            "m": [],
            "hh": [],
            "k": continuation,
            "rb": [],
            "cb": [],
            "u": [],
        }
        return (
            base
            + "\nReturn exactly this byte envelope with no other bytes:\nCSV/1\n<raw CSV>\nSIDECAR/1\n"
            + json.dumps(sidecar, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\nEND/1\nUse d=b when bound, d=a when ambiguous, or d=u when unsupported. Fill m with "
            "merged ranges [start_row,end_row,start_col,end_col,m|h], hh with header relations "
            "[parent_row,parent_col,child_start_col,child_end_col], and optional normalized rb/cb. "
            "The sidecar is one JSON line and must not repeat the CSV grid, candidates, dictionary, "
            "source values, or refs."
        )

    def assess_repeatability(
        self,
        observations: list[dict[str, str | None]],
        *,
        required_fields: tuple[str, ...],
    ) -> dict[str, Any]:
        fields = {}
        for field in required_fields:
            values = [str(item[field]) for item in observations if item.get(field)]
            fields[field] = {
                "observations": len(values),
                "unique_hashes": len(set(values)),
                "assessed": len(values) >= 2,
                "match": len(values) >= 2 and len(set(values)) == 1,
                "ever_conflicted": len(set(values)) > 1,
            }
        return {
            "fields": fields,
            "passed": all(item["match"] for item in fields.values()),
            "ever_conflicted": any(
                item["ever_conflicted"] for item in fields.values()
            ),
            "later_agreement_can_clear_conflict": False,
        }

    def parse_free_csv(
        self,
        text: Any,
        *,
        expected_rows: int,
        expected_columns: int,
    ) -> dict[str, Any]:
        parsed = self._parse_csv(
            text,
            expected_rows=expected_rows,
            expected_columns=expected_columns,
        )
        parsed["mode"] = "free_value_csv"
        return parsed

    def parse_candidate_csv(
        self,
        text: Any,
        *,
        expected_rows: int,
        expected_columns: int,
        candidate_ids: list[str],
    ) -> dict[str, Any]:
        parsed = self._parse_csv(
            text,
            expected_rows=expected_rows,
            expected_columns=expected_columns,
        )
        expected = [str(item) for item in candidate_ids]
        expected_set = set(expected)
        if len(expected) != len(expected_set):
            raise PdfCsvExperimentError("pdf_csv_candidate_input_duplicate")
        ownership: list[str] = []
        candidate_grid: list[list[list[str]]] = []
        for row in parsed["rows"]:
            candidate_row = []
            for field in row:
                if field == "":
                    candidate_row.append([])
                    continue
                ids = field.split(self.config.candidate_separator)
                if not ids or any(not _CANDIDATE_ID.fullmatch(item) for item in ids):
                    raise PdfCsvExperimentError("pdf_csv_candidate_cell_grammar_invalid")
                if len(ids) != len(set(ids)):
                    raise PdfCsvExperimentError("pdf_csv_candidate_duplicate_in_cell")
                unknown = [item for item in ids if item not in expected_set]
                if unknown:
                    raise PdfCsvExperimentError("pdf_csv_candidate_id_unknown")
                if ids != sorted(ids, key=expected.index):
                    raise PdfCsvExperimentError("pdf_csv_candidate_source_order_invalid")
                ownership.extend(ids)
                candidate_row.append(ids)
            candidate_grid.append(candidate_row)
        if len(ownership) != len(set(ownership)):
            raise PdfCsvExperimentError("pdf_csv_candidate_ownership_duplicate")
        if set(ownership) != expected_set:
            raise PdfCsvExperimentError("pdf_csv_candidate_ownership_incomplete")
        parsed.update(
            {
                "mode": "candidate_id_csv",
                "candidate_grid": candidate_grid,
                "candidate_ids_used": ownership,
                "candidate_coverage": len(ownership),
                "candidate_coverage_ratio": 1.0,
                "candidate_grid_hash": sha256_json(candidate_grid),
            }
        )
        return parsed

    def parse_candidate_topology_envelope(
        self,
        text: Any,
        *,
        expected_rows: int,
        expected_columns: int,
        candidate_ids: list[str],
        expected_continuation: list[Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not isinstance(text, str):
            raise PdfCsvExperimentError("pdf_csv_output_not_text")
        if not text.startswith(PDF_CSV_ENVELOPE_PREFIX):
            raise PdfCsvExperimentError("pdf_csv_envelope_prefix_missing")
        if not text.endswith(PDF_CSV_ENVELOPE_SUFFIX):
            raise PdfCsvExperimentError("pdf_csv_envelope_terminal_missing")
        body = text[len(PDF_CSV_ENVELOPE_PREFIX) : -len(PDF_CSV_ENVELOPE_SUFFIX)]
        if body.count(PDF_CSV_ENVELOPE_SEPARATOR) != 1:
            raise PdfCsvExperimentError("pdf_csv_envelope_separator_invalid")
        csv_text, topology_text = body.split(PDF_CSV_ENVELOPE_SEPARATOR, 1)
        if "\n" in topology_text or "\r" in topology_text:
            raise PdfCsvExperimentError("pdf_csv_topology_not_single_line")
        if len(topology_text.encode("utf-8")) > self.config.maximum_topology_bytes:
            raise PdfCsvExperimentError("pdf_csv_topology_budget_exceeded")
        parsed = self.parse_candidate_csv(
            csv_text,
            expected_rows=expected_rows,
            expected_columns=expected_columns,
            candidate_ids=candidate_ids,
        )
        topology = self._parse_topology(
            topology_text,
            expected_rows=expected_rows,
            expected_columns=expected_columns,
            expected_continuation=expected_continuation,
        )
        parsed["mode"] = "candidate_id_csv_topology"
        parsed["envelope_bytes"] = len(text.encode("utf-8"))
        parsed["csv_bytes"] = len(csv_text.encode("utf-8"))
        parsed["topology_bytes"] = len(topology_text.encode("utf-8"))
        return parsed, topology

    def binding_from_csv(
        self,
        *,
        evidence_package: dict[str, Any],
        parsed: dict[str, Any],
        topology: dict[str, Any] | None,
        global_header_depth: int,
    ) -> dict[str, Any]:
        window = evidence_package.get("window") or {}
        row_count = int(window.get("row_count") or 0)
        column_count = int(window.get("column_count") or 0)
        grid = parsed.get("candidate_grid")
        if not isinstance(grid, list):
            raise PdfCsvExperimentError("pdf_csv_candidate_grid_missing")
        local_header_count = max(
            0,
            min(int(window.get("row_end") or 0), global_header_depth)
            - int(window.get("row_start") or 0)
            + 1,
        )
        decision = "bound"
        header_count = local_header_count
        spans: list[dict[str, Any]] = []
        hierarchy: list[dict[str, Any]] = []
        uncertainty_codes: list[str] = []
        if topology is not None:
            decision = {"b": "bound", "a": "ambiguous", "u": "unsupported"}[
                topology["d"]
            ]
            header_count = int(topology["h"])
            spans = [
                {
                    "start_row": item[0],
                    "end_row": item[1],
                    "start_column": item[2],
                    "end_column": item[3],
                    "relation": "merged" if item[4] == "m" else "spanning_header",
                }
                for item in topology["m"]
            ]
            hierarchy = [
                {
                    "parent_row": item[0],
                    "parent_column": item[1],
                    "child_start_column": item[2],
                    "child_end_column": item[3],
                }
                for item in topology["hh"]
            ]
            uncertainty_codes = list(topology["u"])
        rows = [
            {
                "row_ordinal": ordinal,
                "row_kind": "header" if ordinal <= header_count else "data",
                "cells": cells,
            }
            for ordinal, cells in enumerate(grid, start=1)
        ]
        binding = {
            "schema_version": PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
            "package_id": evidence_package.get("package_id"),
            "crop_sha256": (evidence_package.get("crop_identity") or {}).get(
                "crop_sha256"
            ),
            "candidate_dictionary_hash": evidence_package.get(
                "candidate_dictionary_hash"
            ),
            "decision": decision,
            "row_count": row_count,
            "column_count": column_count,
            "header_rows": list(range(1, header_count + 1)),
            "header_hierarchy": hierarchy,
            "rows": rows,
            "spans": spans,
            "uncertainty_codes": uncertainty_codes,
        }
        errors = validate_binding_output_shape(binding)
        if errors:
            raise PdfCsvExperimentError(errors[0])
        return binding

    def parser_grid(self, compact_ledger: dict[str, Any]) -> list[list[str]]:
        rows = int(compact_ledger.get("row_count") or 0)
        columns = int(compact_ledger.get("column_count") or 0)
        grid = [[""] * columns for _ in range(rows)]
        dictionary = compact_ledger.get("private_candidate_dictionary") or {}
        ordered = sorted(
            (item for item in dictionary.values() if isinstance(item, dict)),
            key=lambda item: int(item.get("source_order") or 0),
        )
        for item in ordered:
            row = int(item.get("expected_row_ordinal") or 0) - 1
            column = int(item.get("expected_column_ordinal") or 0) - 1
            if 0 <= row < rows and 0 <= column < columns:
                value = str(item.get("exact_source_span") or "")
                grid[row][column] = " ".join(
                    part for part in (grid[row][column], value) if part
                )
        return grid

    def resolved_candidate_grid(
        self,
        parsed: dict[str, Any],
        candidate_dictionary: dict[str, Any],
    ) -> list[list[str]]:
        result = []
        for row in parsed.get("candidate_grid") or []:
            result.append(
                [
                    " ".join(
                        str((candidate_dictionary.get(item) or {}).get("exact_source_span") or "")
                        for item in cell
                    )
                    for cell in row
                ]
            )
        return result

    def compare_views(
        self,
        *,
        free_grid: list[list[str]] | None,
        candidate_grid: list[list[str]] | None,
        parser_grid: list[list[str]],
        reference_grid: list[list[str]],
    ) -> dict[str, Any]:
        result = {
            "parser_vs_reference": _grid_metrics(reference_grid, parser_grid),
            "free_vs_reference": _grid_metrics(reference_grid, free_grid),
            "candidate_vs_reference": _grid_metrics(reference_grid, candidate_grid),
            "free_vs_parser": _grid_metrics(parser_grid, free_grid),
            "candidate_vs_parser": _grid_metrics(parser_grid, candidate_grid),
            "free_vs_candidate": _grid_metrics(candidate_grid, free_grid),
        }
        free = free_grid or []
        candidate = candidate_grid or []
        positions = _positions(reference_grid, parser_grid, free, candidate)
        parser_value_positions: dict[str, list[tuple[int, int]]] = {}
        for row, column in positions:
            value = _normalize(_at(parser_grid, row, column))
            if value:
                parser_value_positions.setdefault(value, []).append((row, column))
        result["distinctions"] = {
            "visible_reference_but_absent_text_layer": sum(
                bool(_normalize(_at(reference_grid, r, c)))
                and _normalize(_at(free, r, c)) == _normalize(_at(reference_grid, r, c))
                and not _normalize(_at(parser_grid, r, c))
                for r, c in positions
            ),
            "parser_present_but_omitted_visually": sum(
                bool(_normalize(_at(parser_grid, r, c)))
                and not _normalize(_at(free, r, c))
                for r, c in positions
            ),
            "candidate_value_wrong_cell": sum(
                bool(_normalize(_at(candidate, r, c)))
                and _normalize(_at(candidate, r, c)) != _normalize(_at(parser_grid, r, c))
                and _normalize(_at(candidate, r, c))
                in parser_value_positions
                for r, c in positions
            ),
            "duplicate_value_ambiguity_positions": sum(
                len(items) for items in parser_value_positions.values() if len(items) > 1
            ),
        }
        return result

    def _parse_csv(
        self,
        text: Any,
        *,
        expected_rows: int,
        expected_columns: int,
    ) -> dict[str, Any]:
        if not isinstance(text, str):
            raise PdfCsvExperimentError("pdf_csv_output_not_text")
        encoded = text.encode("utf-8")
        if not encoded:
            raise PdfCsvExperimentError("pdf_csv_output_empty")
        if len(encoded) > self.config.maximum_output_bytes:
            raise PdfCsvExperimentError("pdf_csv_output_budget_exceeded")
        if text.startswith("\ufeff"):
            raise PdfCsvExperimentError("pdf_csv_bom_forbidden")
        if "\r" in text:
            raise PdfCsvExperimentError("pdf_csv_newline_invalid")
        if "```" in text:
            raise PdfCsvExperimentError("pdf_csv_markdown_fence_forbidden")
        try:
            reader = csv.reader(
                io.StringIO(text, newline=""),
                delimiter=self.config.delimiter,
                quotechar=self.config.quote_character,
                doublequote=True,
                strict=True,
            )
            rows = [list(row) for row in reader]
        except (csv.Error, UnicodeError) as exc:
            raise PdfCsvExperimentError("pdf_csv_malformed_quoting") from exc
        if rows and rows[-1] == []:
            rows.pop()
        if len(rows) != expected_rows:
            raise PdfCsvExperimentError("pdf_csv_row_count_mismatch")
        if expected_columns < 1 or any(len(row) != expected_columns for row in rows):
            raise PdfCsvExperimentError("pdf_csv_column_count_mismatch")
        if any(row == [] for row in rows):
            raise PdfCsvExperimentError("pdf_csv_blank_row_forbidden")
        return {
            "schema_version": self.config.schema_version,
            "rows": rows,
            "row_count": len(rows),
            "column_count": expected_columns,
            "grid_hash": sha256_json(rows),
            "csv_bytes": len(encoded),
            "maximum_row_bytes": max(
                (len(self._serialize_row(row)) for row in rows), default=0
            ),
            "byte_complete_parse": True,
            "silent_repair_performed": False,
        }

    def _parse_topology(
        self,
        text: str,
        *,
        expected_rows: int,
        expected_columns: int,
        expected_continuation: list[Any] | None,
    ) -> dict[str, Any]:
        try:
            value = json.loads(text)
        except ValueError as exc:
            raise PdfCsvExperimentError("pdf_csv_topology_json_invalid") from exc
        if not isinstance(value, dict):
            raise PdfCsvExperimentError("pdf_csv_topology_not_object")
        required = {"v", "d", "r", "c", "h", "m", "hh", "k", "rb", "cb", "u"}
        if set(value) != required:
            raise PdfCsvExperimentError("pdf_csv_topology_keys_invalid")
        if _recursive_keys(value) & _FORBIDDEN_SIDECAR_KEYS:
            raise PdfCsvExperimentError("pdf_csv_topology_grid_or_source_repetition_forbidden")
        if value["v"] != PDF_CSV_TOPOLOGY_SCHEMA:
            raise PdfCsvExperimentError("pdf_csv_topology_version_invalid")
        if value["d"] not in {"b", "a", "u"}:
            raise PdfCsvExperimentError("pdf_csv_topology_decision_invalid")
        if value["r"] != expected_rows or value["c"] != expected_columns:
            raise PdfCsvExperimentError("pdf_csv_topology_shape_mismatch")
        if not _plain_int(value["h"]) or not 0 <= value["h"] <= min(8, expected_rows):
            raise PdfCsvExperimentError("pdf_csv_topology_header_count_invalid")
        _validate_ranges(value["m"], expected_rows, expected_columns)
        _validate_hierarchy(value["hh"], expected_rows, expected_columns)
        if value["k"] != expected_continuation:
            raise PdfCsvExperimentError("pdf_csv_topology_continuation_mismatch")
        _validate_boundaries(value["rb"], expected_rows)
        _validate_boundaries(value["cb"], expected_columns)
        if (
            not isinstance(value["u"], list)
            or len(value["u"]) > 8
            or any(not isinstance(item, str) or not _UNCERTAINTY_CODE.fullmatch(item) for item in value["u"])
        ):
            raise PdfCsvExperimentError("pdf_csv_topology_uncertainty_invalid")
        result = dict(value)
        result["schema_version"] = PDF_CSV_TOPOLOGY_SCHEMA
        result["topology_hash"] = sha256_json(value)
        result["independently_validated"] = True
        result["grid_repeated"] = False
        result["candidate_dictionary_repeated"] = False
        return result

    def _serialize_row(self, row: list[str]) -> bytes:
        stream = io.StringIO(newline="")
        writer = csv.writer(
            stream,
            delimiter=self.config.delimiter,
            quotechar=self.config.quote_character,
            lineterminator=self.config.newline,
            doublequote=True,
        )
        writer.writerow(row)
        return stream.getvalue().encode("utf-8")


def _validate_ranges(value: Any, rows: int, columns: int) -> None:
    if not isinstance(value, list) or len(value) > rows * columns:
        raise PdfCsvExperimentError("pdf_csv_topology_merged_ranges_invalid")
    seen: set[tuple[int, int]] = set()
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != 5
            or not all(_plain_int(part) for part in item[:4])
            or item[4] not in {"m", "h"}
        ):
            raise PdfCsvExperimentError("pdf_csv_topology_merged_range_invalid")
        start_row, end_row, start_column, end_column = item[:4]
        if not (
            1 <= start_row <= end_row <= rows
            and 1 <= start_column <= end_column <= columns
            and (start_row != end_row or start_column != end_column)
        ):
            raise PdfCsvExperimentError("pdf_csv_topology_merged_range_out_of_bounds")
        positions = {
            (row, column)
            for row in range(start_row, end_row + 1)
            for column in range(start_column, end_column + 1)
        }
        if seen & positions:
            raise PdfCsvExperimentError("pdf_csv_topology_merged_range_overlap")
        seen.update(positions)


def _validate_hierarchy(value: Any, rows: int, columns: int) -> None:
    if not isinstance(value, list) or len(value) > rows * columns:
        raise PdfCsvExperimentError("pdf_csv_topology_header_hierarchy_invalid")
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != 4
            or not all(_plain_int(part) for part in item)
            or not (
                1 <= item[0] <= min(rows, 8)
                and 1 <= item[1] <= columns
                and 1 <= item[2] <= item[3] <= columns
            )
        ):
            raise PdfCsvExperimentError("pdf_csv_topology_header_relation_invalid")


def _validate_boundaries(value: Any, segments: int) -> None:
    if not isinstance(value, list):
        raise PdfCsvExperimentError("pdf_csv_topology_boundaries_invalid")
    if not value:
        return
    if len(value) != segments + 1 or any(
        not isinstance(item, (int, float)) or isinstance(item, bool) for item in value
    ):
        raise PdfCsvExperimentError("pdf_csv_topology_boundary_count_invalid")
    numbers = [float(item) for item in value]
    if numbers[0] != 0.0 or numbers[-1] != 1.0 or any(
        right <= left for left, right in zip(numbers, numbers[1:])
    ):
        raise PdfCsvExperimentError("pdf_csv_topology_boundaries_not_normalized")


def _plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _recursive_keys(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        result.update(str(key).lower() for key in value)
        for child in value.values():
            result.update(_recursive_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_recursive_keys(child))
    return result


def _grid_metrics(expected: list[list[str]] | None, actual: list[list[str]] | None) -> dict[str, Any]:
    expected = expected or []
    actual = actual or []
    height = max(len(expected), len(actual))
    width = max(
        max((len(row) for row in expected), default=0),
        max((len(row) for row in actual), default=0),
    )
    pairs = [
        (_normalize(_at(expected, row, column)), _normalize(_at(actual, row, column)))
        for row in range(height)
        for column in range(width)
    ]
    numeric = [pair for pair in pairs if _NUMERIC_LIKE.fullmatch(pair[0])]
    empty = [pair for pair in pairs if not pair[0]]
    return {
        "structure_exact": len(expected) == len(actual)
        and all(len(left) == len(right) for left, right in zip(expected, actual)),
        "expected_rows": len(expected),
        "actual_rows": len(actual),
        "expected_columns": max((len(row) for row in expected), default=0),
        "actual_columns": max((len(row) for row in actual), default=0),
        "cells_exact": sum(left == right for left, right in pairs),
        "cells_total": len(pairs),
        "numeric_exact": sum(left == right for left, right in numeric),
        "numeric_total": len(numeric),
        "empty_exact": sum(left == right for left, right in empty),
        "empty_total": len(empty),
        "hallucinated_nonempty": sum(not left and bool(right) for left, right in pairs),
        "omitted_nonempty": sum(bool(left) and not right for left, right in pairs),
    }


def _positions(*grids: list[list[str]]) -> list[tuple[int, int]]:
    height = max((len(grid) for grid in grids), default=0)
    width = max(
        (max((len(row) for row in grid), default=0) for grid in grids),
        default=0,
    )
    return [(row, column) for row in range(height) for column in range(width)]


def _at(grid: list[list[str]] | None, row: int, column: int) -> str:
    if grid is None or row >= len(grid) or column >= len(grid[row]):
        return ""
    return str(grid[row][column] or "")


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))).strip()


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
