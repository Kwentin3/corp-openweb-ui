from __future__ import annotations


RUNTIME_STATUS = "proof_only"

import hashlib
import json
import re
import unicodedata
from typing import Any


MANIFEST_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_canonical_table_manifest_v1"
CANONICAL_TABLE_SCHEMA_VERSION = "broker_reports_canonical_table_v1"
TERMINAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_canonical_table_terminal_v1"
TERMINAL_SEAL_SCHEMA_VERSION = (
    "broker_reports_pdf_dual_vlm_canonical_table_terminal_seal_v1"
)
REFERENCE_SCHEMA_VERSION = (
    "broker_reports_pdf_dual_vlm_canonical_table_controlled_reference_v1"
)
SCORE_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_canonical_table_scores_v1"
PROMPT_CONTRACT_VERSION = "dual_vlm_canonical_table_normalizer_v4"
SCHEMA_ADAPTER_BENCHMARK_VERSION = "dual_vlm_canonical_table_schema_equivalence_v1"

GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE = 0.08
CONTENT_STATES = frozenset({"present", "empty", "unreadable"})
FORBIDDEN_CONTRACT_FIELDS = frozenset(
    {
        "bbox",
        "coordinates",
        "source_bbox",
        "provenance",
        "parser_evidence",
        "fact_type",
        "financial_role",
        "currency",
        "unit",
        "value_type",
        "cell_type",
        "header",
        "row_header",
        "column_header",
        "body",
        "total",
        "note",
    }
)

NORMALIZER_PROMPT = """Read exactly one logical table from the supplied immutable table crop.
The crop may include a uniform outer margin and nearby non-table text; ignore material that is
not part of the central detected table. Reconstruct the most faithful stable logical grid that
preserves every visible table cell and repeated horizontal alignment across rows. A logical
column may be sparse: repeated alignment in the same vertical band is evidence of a column even
when most of its cells are empty. Preserve such columns, return their empty cells explicitly,
and do not merge cells across a sparse column merely because it contains content in only a few
rows. Short markers such as currency symbols must remain separate when they occupy their own
consistently aligned vertical band. Transcribe every visible text token inside the logical table
literally and completely. Do not summarize, simplify, deduplicate, relabel, or omit content
because it appears redundant, decorative, structural, or non-financial. Visible numbering rows,
ordinal guide rows, section labels, footnote markers, superscripts, subscripts, repeated labels,
and standalone symbols are table content and must remain at their visible grid positions. Return
every logical cell once at its zero-based top-left grid position. After reconstructing the grid,
set row_count and column_count to its complete dimensions, including every sparse column and
merged cell. Every cell anchor and span must stay inside those declared dimensions. A merged
cell is one cell with row_span and column_span; never repeat it in covered positions. Explicitly
include visually empty cells. Use content_state=present only for legible non-empty source text,
empty only for an existing visibly empty cell, and unreadable only when a cell exists but its
content cannot be read. For empty or unreadable cells, source_text must be the empty string.
Preserve visible source spelling, punctuation, signs, parentheses, separators, and reading
order. Do not calculate, translate, classify, interpret, repair, or infer missing text. Do not
assign header/body/total roles or number/date/currency types. Do not return visual coordinates,
confidence, provenance, parser evidence, diagnostics, or fields outside the schema."""


class CanonicalTableContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonical_table_schema() -> dict[str, Any]:
    cell = _closed_object(
        {
            "row_index": {"type": "integer", "minimum": 0, "maximum": 199},
            "column_index": {"type": "integer", "minimum": 0, "maximum": 199},
            "row_span": {"type": "integer", "minimum": 1, "maximum": 200},
            "column_span": {"type": "integer", "minimum": 1, "maximum": 200},
            "content_state": {"type": "string", "enum": sorted(CONTENT_STATES)},
            "source_text": {"type": "string", "maxLength": 12000},
        }
    )
    return {
        "$id": CANONICAL_TABLE_SCHEMA_VERSION,
        **_closed_object(
            {
                "schema_version": {
                    "type": "string",
                    "enum": [CANONICAL_TABLE_SCHEMA_VERSION],
                },
                "table_id": _identifier_schema(),
                "row_count": {"type": "integer", "minimum": 1, "maximum": 200},
                "column_count": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                },
                "cells": {
                    "type": "array",
                    "items": cell,
                    "minItems": 1,
                    "maxItems": 40000,
                },
            }
        ),
    }


def normalizer_model_view(
    *,
    crop_sha256: str,
    table_id: str,
    image_width: int,
    image_height: int,
) -> dict[str, Any]:
    return {
        "task": NORMALIZER_PROMPT,
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "input_identity": {
            "crop_sha256": crop_sha256,
            "table_id": table_id,
            "image_width": image_width,
            "image_height": image_height,
            "visual_coordinates_available_to_model": False,
        },
        "output_contract": {
            "schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
            "grid_index_origin": 0,
            "merged_cell_representation": "one_top_left_anchor_with_spans",
            "every_grid_slot_covered_exactly_once": True,
            "content_states": sorted(CONTENT_STATES),
            "cell_roles": False,
            "content_types": False,
            "financial_semantics": False,
            "coordinates": False,
        },
    }


def validate_table_output(value: Any, *, table_id: str | None = None) -> list[str]:
    if not isinstance(value, dict):
        return ["canonical_table_not_object"]
    required = {"schema_version", "table_id", "row_count", "column_count", "cells"}
    errors: list[str] = []
    if set(value) != required:
        errors.append("canonical_table_fields_invalid")
    if value.get("schema_version") != CANONICAL_TABLE_SCHEMA_VERSION:
        errors.append("canonical_table_schema_version_invalid")
    if not _identifier(value.get("table_id")):
        errors.append("canonical_table_id_invalid")
    elif table_id is not None and value.get("table_id") != table_id:
        errors.append("canonical_table_id_mismatch")
    rows = value.get("row_count")
    columns = value.get("column_count")
    if not _bounded_int(rows, minimum=1, maximum=200):
        errors.append("canonical_table_row_count_invalid")
    if not _bounded_int(columns, minimum=1, maximum=200):
        errors.append("canonical_table_column_count_invalid")
    cells = value.get("cells")
    if not isinstance(cells, list) or not cells or len(cells) > 40000:
        errors.append("canonical_table_cells_invalid")
        return errors
    if not _bounded_int(rows, minimum=1, maximum=200) or not _bounded_int(
        columns, minimum=1, maximum=200
    ):
        return errors

    coverage: dict[tuple[int, int], int] = {}
    anchors: set[tuple[int, int]] = set()
    for index, cell in enumerate(cells):
        prefix = f"canonical_table_cell_{index}"
        cell_errors = _validate_cell(cell, rows=rows, columns=columns)
        errors.extend(prefix + "_" + item for item in cell_errors)
        if cell_errors:
            continue
        anchor = (cell["row_index"], cell["column_index"])
        if anchor in anchors:
            errors.append(prefix + "_anchor_duplicate")
            continue
        anchors.add(anchor)
        for row in range(cell["row_index"], cell["row_index"] + cell["row_span"]):
            for column in range(
                cell["column_index"], cell["column_index"] + cell["column_span"]
            ):
                slot = (row, column)
                coverage[slot] = coverage.get(slot, 0) + 1

    expected_slots = rows * columns
    if len(coverage) != expected_slots:
        errors.append("canonical_table_grid_has_uncovered_slots")
    if any(count != 1 for count in coverage.values()):
        errors.append("canonical_table_grid_has_overlapping_cells")
    return errors


def canonicalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def canonicalize_table(
    value: dict[str, Any], *, table_id: str | None = None
) -> dict[str, Any]:
    errors = validate_table_output(value, table_id=table_id)
    if errors:
        raise CanonicalTableContractError(errors[0])
    cells = [
        {
            "row_index": cell["row_index"],
            "column_index": cell["column_index"],
            "row_span": cell["row_span"],
            "column_span": cell["column_span"],
            "content_state": cell["content_state"],
            "source_text": canonicalize_text(cell["source_text"]),
        }
        for cell in value["cells"]
    ]
    cells.sort(key=_cell_sort_key)
    return {
        "schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
        "table_id": value["table_id"],
        "row_count": value["row_count"],
        "column_count": value["column_count"],
        "cells": cells,
    }


def compare_tables(
    left_raw: dict[str, Any], right_raw: dict[str, Any]
) -> dict[str, Any]:
    left = canonicalize_table(left_raw)
    right = canonicalize_table(right_raw)
    left_cells = _cell_map(left)
    right_cells = _cell_map(right)
    structural = _structure_signature(left) == _structure_signature(right)
    content = structural and all(
        left_cells[key]["source_text"] == right_cells[key]["source_text"]
        for key in left_cells
    )
    full = structural and content
    diffs = _table_diffs(left_raw, right_raw, left, right)
    return {
        "STRUCTURAL_CONSENSUS": structural,
        "CONTENT_CONSENSUS": content,
        "FULL_TABLE_CONSENSUS": full,
        "canonical_left_sha256": sha256_json(left),
        "canonical_right_sha256": sha256_json(right),
        "raw_format_only_difference": full and left_raw != right_raw,
        "smallest_difference": diffs[0] if diffs else None,
        "differences": diffs,
    }


def table_accuracy(
    provider_raw: dict[str, Any], reference_raw: dict[str, Any]
) -> dict[str, Any]:
    provider = canonicalize_table(provider_raw)
    reference = canonicalize_table(reference_raw)
    provider_cells = _cell_map(provider)
    reference_cells = _cell_map(reference)
    provider_keys = set(provider_cells)
    reference_keys = set(reference_cells)
    common = provider_keys & reference_keys
    correct_structure_cells = sum(
        _cell_structure(provider_cells[key]) == _cell_structure(reference_cells[key])
        for key in common
    )
    correct_content_cells = sum(
        provider_cells[key]["content_state"] == reference_cells[key]["content_state"]
        and provider_cells[key]["source_text"] == reference_cells[key]["source_text"]
        for key in common
    )
    comparison = compare_tables(provider_raw, reference_raw)
    return {
        "exact_full_table": comparison["FULL_TABLE_CONSENSUS"],
        "exact_structure": comparison["STRUCTURAL_CONSENSUS"],
        "reference_cell_count": len(reference_cells),
        "provider_cell_count": len(provider_cells),
        "correct_structure_cell_count": correct_structure_cells,
        "correct_content_cell_count": correct_content_cells,
        "cell_content_accuracy": _ratio(correct_content_cells, len(reference_cells)),
        "missing_cell_count": len(reference_keys - provider_keys),
        "extra_cell_count": len(provider_keys - reference_keys),
        "smallest_difference": comparison["smallest_difference"],
    }


def schema_equivalence_record(
    canonical_schema: dict[str, Any], adapted_schema: dict[str, Any]
) -> dict[str, Any]:
    removed: list[str] = []
    transformed: list[str] = []
    weakened: list[str] = []
    _compare_schema_nodes(
        canonical_schema,
        adapted_schema,
        path="$",
        removed=removed,
        transformed=transformed,
        weakened=weakened,
    )
    required_equal = _required_paths(canonical_schema) == _required_paths(
        adapted_schema
    )
    enums_equal = _enum_paths(canonical_schema) == _enum_paths(adapted_schema)
    nullable_equal = _nullable_paths(canonical_schema) == _nullable_paths(
        adapted_schema
    )
    return {
        "schema_adapter_benchmark_version": SCHEMA_ADAPTER_BENCHMARK_VERSION,
        "canonical_schema_sha256": sha256_json(canonical_schema),
        "adapted_schema_sha256": sha256_json(adapted_schema),
        "removed_keywords": sorted(removed),
        "transformed_keywords": sorted(transformed),
        "weakened_keywords": sorted(weakened),
        "required_field_cardinality_equivalent": required_equal,
        "enum_meaning_equivalent": enums_equal,
        "nullability_equivalent": nullable_equal,
        "logical_contract_equivalent": required_equal
        and enums_equal
        and nullable_equal,
        "comparison_unit": "model + provider API + schema adapter",
        "isolated_model_comparison_claimed": False,
        "causality_established": False,
    }


def _validate_cell(cell: Any, *, rows: int, columns: int) -> list[str]:
    fields = {
        "row_index",
        "column_index",
        "row_span",
        "column_span",
        "content_state",
        "source_text",
    }
    if not isinstance(cell, dict) or set(cell) != fields:
        return ["fields_invalid"]
    errors: list[str] = []
    row = cell.get("row_index")
    column = cell.get("column_index")
    row_span = cell.get("row_span")
    column_span = cell.get("column_span")
    if not _bounded_int(row, minimum=0, maximum=rows - 1):
        errors.append("row_index_invalid")
    if not _bounded_int(column, minimum=0, maximum=columns - 1):
        errors.append("column_index_invalid")
    if not _bounded_int(row_span, minimum=1, maximum=rows):
        errors.append("row_span_invalid")
    if not _bounded_int(column_span, minimum=1, maximum=columns):
        errors.append("column_span_invalid")
    if not errors and (row + row_span > rows or column + column_span > columns):
        errors.append("span_out_of_bounds")
    state = cell.get("content_state")
    text = cell.get("source_text")
    if state not in CONTENT_STATES:
        errors.append("content_state_invalid")
    if not isinstance(text, str) or len(text) > 12000:
        errors.append("source_text_invalid")
    elif state == "present" and not canonicalize_text(text):
        errors.append("present_text_missing")
    elif state in {"empty", "unreadable"} and text != "":
        errors.append("non_present_text_must_be_empty")
    return errors


def _table_diffs(
    left_raw: dict[str, Any],
    right_raw: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    if left["row_count"] != right["row_count"]:
        diffs.append(
            _diff("different_row_count", left["row_count"], right["row_count"])
        )
    if left["column_count"] != right["column_count"]:
        diffs.append(
            _diff("different_column_count", left["column_count"], right["column_count"])
        )
    left_cells = _cell_map(left)
    right_cells = _cell_map(right)
    for key in sorted(set(left_cells) | set(right_cells)):
        if key not in left_cells:
            diffs.append(
                _diff("one_provider_omitted_cell", None, right_cells[key], key)
            )
            continue
        if key not in right_cells:
            diffs.append(
                _diff("one_provider_introduced_extra_cell", left_cells[key], None, key)
            )
            continue
        left_cell = left_cells[key]
        right_cell = right_cells[key]
        if _cell_structure(left_cell) != _cell_structure(right_cell):
            diffs.append(
                _diff(
                    "merged_cell_versus_separate_cells",
                    _cell_structure(left_cell),
                    _cell_structure(right_cell),
                    key,
                )
            )
        if left_cell["content_state"] != right_cell["content_state"]:
            cls = (
                "missing_empty_cell"
                if "empty" in {left_cell["content_state"], right_cell["content_state"]}
                else "content_state_difference"
            )
            diffs.append(
                _diff(cls, left_cell["content_state"], right_cell["content_state"], key)
            )
        if left_cell["source_text"] != right_cell["source_text"]:
            other_left = _text_positions(
                right_cells, left_cell["source_text"], excluding=key
            )
            other_right = _text_positions(
                left_cells, right_cell["source_text"], excluding=key
            )
            cls = (
                "text_assigned_to_different_cell"
                if other_left or other_right
                else "differing_source_text"
            )
            item = _diff(cls, left_cell["source_text"], right_cell["source_text"], key)
            item["matching_text_elsewhere"] = {
                "left_text_in_right_positions": other_left,
                "right_text_in_left_positions": other_right,
            }
            diffs.append(item)
    if not diffs and left_raw != right_raw:
        diffs.append(
            {
                "class": "raw_format_only_difference",
                "cell": None,
                "left": None,
                "right": None,
            }
        )
    return diffs


def _diff(
    cls: str,
    left: Any,
    right: Any,
    cell: tuple[int, int] | None = None,
) -> dict[str, Any]:
    return {
        "class": cls,
        "cell": list(cell) if cell is not None else None,
        "left": left,
        "right": right,
    }


def _structure_signature(table: dict[str, Any]) -> tuple[Any, ...]:
    return (
        table["row_count"],
        table["column_count"],
        tuple(
            (
                cell["row_index"],
                cell["column_index"],
                cell["row_span"],
                cell["column_span"],
                cell["content_state"],
            )
            for cell in table["cells"]
        ),
    )


def _cell_map(table: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    return {(cell["row_index"], cell["column_index"]): cell for cell in table["cells"]}


def _cell_structure(cell: dict[str, Any]) -> tuple[int, int, str]:
    return (cell["row_span"], cell["column_span"], cell["content_state"])


def _cell_sort_key(cell: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        cell["row_index"],
        cell["column_index"],
        cell["row_span"],
        cell["column_span"],
    )


def _text_positions(
    cells: dict[tuple[int, int], dict[str, Any]],
    text: str,
    *,
    excluding: tuple[int, int],
) -> list[list[int]]:
    if not text:
        return []
    return [
        list(key)
        for key, cell in cells.items()
        if key != excluding and cell["source_text"] == text
    ]


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _bounded_int(value: Any, *, minimum: int, maximum: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and minimum <= value <= maximum
    )


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value)
    )


def _identifier_schema() -> dict[str, Any]:
    return {"type": "string", "pattern": r"^[A-Za-z0-9_.:-]{1,160}$"}


def _closed_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _compare_schema_nodes(
    canonical: Any,
    adapted: Any,
    *,
    path: str,
    removed: list[str],
    transformed: list[str],
    weakened: list[str],
) -> None:
    if not isinstance(canonical, dict) or not isinstance(adapted, dict):
        if canonical != adapted:
            transformed.append(path)
        return
    for key, value in canonical.items():
        key_path = f"{path}.{key}"
        if key not in adapted:
            removed.append(key_path)
            if key in {"required", "enum", "type"}:
                weakened.append(key_path)
            continue
        other = adapted[key]
        if key == "properties" and isinstance(value, dict) and isinstance(other, dict):
            for name, child in value.items():
                _compare_schema_nodes(
                    child,
                    other.get(name),
                    path=f"{key_path}.{name}",
                    removed=removed,
                    transformed=transformed,
                    weakened=weakened,
                )
        elif key == "items":
            _compare_schema_nodes(
                value,
                other,
                path=key_path,
                removed=removed,
                transformed=transformed,
                weakened=weakened,
            )
        elif value != other:
            transformed.append(key_path)


def _required_paths(schema: Any, path: str = "$") -> set[tuple[str, tuple[str, ...]]]:
    if not isinstance(schema, dict):
        return set()
    found: set[tuple[str, tuple[str, ...]]] = set()
    required = schema.get("required")
    if isinstance(required, list):
        found.add((path, tuple(sorted(str(item) for item in required))))
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, child in properties.items():
            found |= _required_paths(child, f"{path}.properties.{name}")
    found |= _required_paths(schema.get("items"), f"{path}.items")
    return found


def _enum_paths(schema: Any, path: str = "$") -> set[tuple[str, tuple[str, ...]]]:
    if not isinstance(schema, dict):
        return set()
    found: set[tuple[str, tuple[str, ...]]] = set()
    enum = schema.get("enum")
    if isinstance(enum, list):
        found.add((path, tuple(sorted(str(item) for item in enum))))
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, child in properties.items():
            found |= _enum_paths(child, f"{path}.properties.{name}")
    found |= _enum_paths(schema.get("items"), f"{path}.items")
    return found


def _nullable_paths(schema: Any, path: str = "$") -> set[str]:
    if not isinstance(schema, dict):
        return set()
    found = {path} if schema.get("nullable") is True else set()
    value_type = schema.get("type")
    if isinstance(value_type, list) and "null" in value_type:
        found.add(path)
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, child in properties.items():
            found |= _nullable_paths(child, f"{path}.properties.{name}")
    found |= _nullable_paths(schema.get("items"), f"{path}.items")
    return found
