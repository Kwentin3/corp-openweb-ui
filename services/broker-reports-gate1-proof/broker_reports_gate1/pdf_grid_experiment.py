from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .pdf_csv_experiment import PDF_CSV_TOPOLOGY_SCHEMA, PdfCsvExperimentFactory
from .pdf_hybrid_contracts import canonical_json_bytes, sha256_json


PDF_GRID_EXPERIMENT_VERSION = "broker_reports_real_table_grid_representation_experiment_v2"
PDF_COMPACT_GRID_SCHEMA = "broker_reports_candidate_compact_json_grid_v1"
PDF_TOPOLOGY_ONLY_SCHEMA = "broker_reports_topology_only_json_v1"
FACTORY_REQUIRED = (
    "PdfGridExperimentFactory.create is the only compact-grid and topology research entrypoint"
)
FORBIDDEN = (
    "Grid research callers must not repair candidate ownership, dimensions, source order, or topology"
)

_CANDIDATE_CELL = re.compile(r"^[0-9a-z]+(?:\+[0-9a-z]+)*$")


class PdfGridExperimentError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfGridExperimentConfig:
    schema_version: str = PDF_COMPACT_GRID_SCHEMA
    maximum_output_bytes: int = 512 * 1024


class PdfGridExperimentFactory:
    def __init__(self, config: PdfGridExperimentConfig | None = None) -> None:
        self.config = config or PdfGridExperimentConfig()

    def create(self) -> "PdfGridExperimentRuntime":
        if self.config.schema_version != PDF_COMPACT_GRID_SCHEMA:
            raise PdfGridExperimentError("pdf_grid_schema_version_invalid")
        return PdfGridExperimentRuntime(self.config)


class PdfGridExperimentRuntime:
    def __init__(self, config: PdfGridExperimentConfig) -> None:
        self.config = config
        self.csv_runtime = PdfCsvExperimentFactory().create()

    def compact_model_view(
        self,
        *,
        evidence_package: dict[str, Any],
        continuation: list[Any] | None,
    ) -> dict[str, Any]:
        model = evidence_package.get("model_facing") or {}
        window = evidence_package.get("window") or {}
        candidates = model.get("c") or []
        if not isinstance(candidates, list) or not candidates:
            raise PdfGridExperimentError("pdf_grid_candidate_records_missing")
        return {
            "i": (
                "Place every supplied id exactly once in the raster grid. "
                "Each g cell is empty or ids joined by + in source order. "
                "Do not output source values, topology, or explanations."
            ),
            "x": [
                evidence_package.get("package_id"),
                (evidence_package.get("crop_identity") or {}).get("crop_sha256"),
                evidence_package.get("candidate_dictionary_hash"),
                int(window.get("row_count") or 0),
                int(window.get("column_count") or 0),
                int(window.get("row_start") or 0),
                int(window.get("row_end") or 0),
                continuation,
            ],
            "c": candidates,
        }

    def compact_output_schema(
        self, *, expected_rows: int, expected_columns: int
    ) -> dict[str, Any]:
        if expected_rows < 1 or expected_columns < 1:
            raise PdfGridExperimentError("pdf_grid_dimensions_invalid")
        return {
            "$id": PDF_COMPACT_GRID_SCHEMA,
            "type": "object",
            "additionalProperties": False,
            "required": ["g"],
            "properties": {
                "g": {
                    "type": "array",
                    "minItems": expected_rows,
                    "maxItems": expected_rows,
                    "items": {
                        "type": "array",
                        "minItems": expected_columns,
                        "maxItems": expected_columns,
                        "items": {"type": "string"},
                    },
                }
            },
        }

    def parse_compact_output(
        self,
        value: Any,
        *,
        expected_rows: int,
        expected_columns: int,
        candidate_ids: list[str],
    ) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != {"g"}:
            raise PdfGridExperimentError("pdf_grid_root_contract_invalid")
        encoded = canonical_json_bytes(value)
        if len(encoded) > self.config.maximum_output_bytes:
            raise PdfGridExperimentError("pdf_grid_output_budget_exceeded")
        grid = value.get("g")
        if not isinstance(grid, list) or len(grid) != expected_rows:
            raise PdfGridExperimentError("pdf_grid_row_count_mismatch")
        if any(not isinstance(row, list) or len(row) != expected_columns for row in grid):
            raise PdfGridExperimentError("pdf_grid_column_count_mismatch")
        expected = [str(item) for item in candidate_ids]
        if len(expected) != len(set(expected)):
            raise PdfGridExperimentError("pdf_grid_candidate_input_duplicate")
        expected_set = set(expected)
        ownership: list[str] = []
        candidate_grid: list[list[list[str]]] = []
        for row in grid:
            parsed_row: list[list[str]] = []
            for field in row:
                if not isinstance(field, str):
                    raise PdfGridExperimentError("pdf_grid_cell_not_string")
                if field == "":
                    parsed_row.append([])
                    continue
                if not _CANDIDATE_CELL.fullmatch(field):
                    raise PdfGridExperimentError("pdf_grid_candidate_cell_grammar_invalid")
                ids = field.split("+")
                if len(ids) != len(set(ids)):
                    raise PdfGridExperimentError("pdf_grid_candidate_duplicate_in_cell")
                if any(item not in expected_set for item in ids):
                    raise PdfGridExperimentError("pdf_grid_candidate_id_unknown")
                if ids != sorted(ids, key=expected.index):
                    raise PdfGridExperimentError("pdf_grid_candidate_source_order_invalid")
                ownership.extend(ids)
                parsed_row.append(ids)
            candidate_grid.append(parsed_row)
        if len(ownership) != len(set(ownership)):
            raise PdfGridExperimentError("pdf_grid_candidate_ownership_duplicate")
        if set(ownership) != expected_set:
            raise PdfGridExperimentError("pdf_grid_candidate_ownership_incomplete")
        return {
            "schema_version": PDF_COMPACT_GRID_SCHEMA,
            "mode": "candidate_id_compact_json_grid",
            "candidate_grid": candidate_grid,
            "candidate_ids_used": ownership,
            "candidate_coverage": len(ownership),
            "candidate_coverage_ratio": 1.0,
            "candidate_grid_hash": sha256_json(candidate_grid),
            "grid_hash": sha256_json(grid),
            "row_count": expected_rows,
            "column_count": expected_columns,
            "json_bytes": len(encoded),
            "silent_repair_performed": False,
        }

    def binding_from_compact_grid(
        self,
        *,
        evidence_package: dict[str, Any],
        parsed: dict[str, Any],
        global_header_depth: int,
    ) -> dict[str, Any]:
        return self.csv_runtime.binding_from_csv(
            evidence_package=evidence_package,
            parsed=parsed,
            topology=None,
            global_header_depth=global_header_depth,
        )

    def topology_model_view(
        self,
        *,
        evidence_package: dict[str, Any],
        continuation: list[Any] | None,
    ) -> dict[str, Any]:
        window = evidence_package.get("window") or {}
        model = evidence_package.get("model_facing") or {}
        header_depth = int((model.get("h") or [None, 0])[1] or 0)
        rows = int(window.get("row_count") or 0)
        columns = int(window.get("column_count") or 0)
        return {
            "i": (
                "Inspect only structural ambiguity in the raster. Return topology, never grid cells, "
                "candidate ids, source values, or explanations. Use d=b only when visually supported, "
                "d=a when ambiguous, and d=u when unsupported."
            ),
            "x": [
                evidence_package.get("package_id"),
                (evidence_package.get("crop_identity") or {}).get("crop_sha256"),
                int(window.get("row_count") or 0),
                int(window.get("column_count") or 0),
                header_depth,
                continuation,
            ],
            "t": {
                "v": PDF_CSV_TOPOLOGY_SCHEMA,
                "d": "b",
                "r": rows,
                "c": columns,
                "h": header_depth,
                "m": [],
                "hh": [],
                "k": continuation,
                "rb": [],
                "cb": [],
                "u": [],
            },
        }

    def topology_output_schema(self) -> dict[str, Any]:
        integer_array = {"type": "array", "items": {"type": "integer"}}
        mixed_array = {
            "type": "array",
            "items": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
        }
        number_array = {"type": "array", "items": {"type": "number"}}
        return {
            "$id": PDF_TOPOLOGY_ONLY_SCHEMA,
            "type": "object",
            "additionalProperties": False,
            "required": ["v", "d", "r", "c", "h", "m", "hh", "k", "rb", "cb", "u"],
            "properties": {
                "v": {"type": "string"},
                "d": {"type": "string", "enum": ["b", "a", "u"]},
                "r": {"type": "integer"},
                "c": {"type": "integer"},
                "h": {"type": "integer"},
                "m": {"type": "array", "items": mixed_array},
                "hh": {"type": "array", "items": integer_array},
                "k": {
                    "anyOf": [
                        {"type": "null"},
                        {"type": "array"},
                    ]
                },
                "rb": number_array,
                "cb": number_array,
                "u": {"type": "array", "items": {"type": "string"}},
            },
        }
