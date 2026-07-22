from __future__ import annotations

import hashlib
import json
from typing import Any

from .semantic_visual_table_contracts import (
    SEMANTIC_LOGICAL_TABLE_PROFILE_ID,
    SEMANTIC_VISUAL_TABLE_ORIGIN,
)


SEMANTIC_VISUAL_TABLE_PROJECTION_VALIDATOR_VERSION = (
    "semantic_visual_table_projection_validator_v1"
)


def validate_semantic_visual_table_projection(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, dict):
        errors.append("semantic_visual_table_projection_invalid")
        value = {}
    metadata = _object(value.get("semantic_visual_table"))
    canonical_validation = _object(value.get("canonical_validation"))
    if (
        value.get("source_format") != "pdf"
        or value.get("table_origin") != SEMANTIC_VISUAL_TABLE_ORIGIN
        or value.get("canonical_profile_id") != SEMANTIC_LOGICAL_TABLE_PROFILE_ID
        or value.get("canonical_table_scope") != "ready_validated_projection_only"
        or value.get("semantic_table_truth_claimed") is not False
        or value.get("ocr_vlm_used") is not True
        or value.get("page_rendering_used_for_extraction") is not True
        or metadata.get("origin") != SEMANTIC_VISUAL_TABLE_ORIGIN
        or metadata.get("physical_geometry_claimed") is not False
        or metadata.get("model_generated_indexes") != 0
        or metadata.get("model_generated_spans") != 0
        or canonical_validation.get("validator_status") != "passed"
        or canonical_validation.get("physical_geometry_claimed") is not False
    ):
        errors.append("semantic_visual_table_projection_invalid")
    cells = [item for item in value.get("cells") or [] if isinstance(item, dict)]
    private_values = {
        str(item.get("value_path_ref") or ""): item.get("normalized_value")
        for item in value.get("private_values") or []
        if isinstance(item, dict)
    }
    materialized_cells = []
    coordinates: set[tuple[int, int]] = set()
    for cell in cells:
        row_index = cell.get("logical_row_index")
        column_index = cell.get("logical_column_index")
        coordinate = (row_index, column_index)
        if (
            not isinstance(row_index, int)
            or isinstance(row_index, bool)
            or not isinstance(column_index, int)
            or isinstance(column_index, bool)
            or coordinate in coordinates
            or cell.get("row_span") != 1
            or cell.get("column_span") != 1
            or cell.get("empty_origin")
            not in {"none", "semantic_null", "short_row_padding"}
        ):
            errors.append("semantic_visual_table_projection_cell_invalid")
            continue
        coordinates.add(coordinate)
        value_path = str(cell.get("normalized_private_value_path") or "")
        materialized_cells.append(
            {
                "row_index": row_index,
                "column_index": column_index,
                "value": private_values.get(value_path),
                "empty_origin": cell.get("empty_origin"),
            }
        )
    expected_count = int(value.get("row_count") or 0) * int(
        value.get("column_count") or 0
    )
    if len(cells) != expected_count or len(coordinates) != expected_count:
        errors.append("semantic_visual_table_projection_grid_incomplete")
    material = {
        "table_id": value.get("logical_table_id"),
        "row_count": value.get("row_count"),
        "column_count": value.get("column_count"),
        "cells": sorted(
            materialized_cells,
            key=lambda item: (item["row_index"], item["column_index"]),
        ),
    }
    if _sha256_json(material) != metadata.get("materialization_hash"):
        errors.append("semantic_visual_table_projection_materialization_hash_invalid")
    return {
        "validator_version": SEMANTIC_VISUAL_TABLE_PROJECTION_VALIDATOR_VERSION,
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "reason_codes": sorted(set(errors)),
    }


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
