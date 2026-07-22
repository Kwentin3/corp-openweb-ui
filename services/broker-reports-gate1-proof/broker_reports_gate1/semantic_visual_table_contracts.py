"""Authoritative model-facing contract for semantic visual-table transcription.

This module owns only the response shape presented to a VLM.  Source identity,
provider metadata, indexes, logical empty-cell materialization, hashes,
persistence, and terminal state belong to deterministic application code.
"""

from __future__ import annotations

import copy
from typing import Any


SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION = (
    "broker_reports_semantic_table_transcription_v1"
)
SEMANTIC_TABLE_TRANSCRIPTION_ROOT_FIELDS = frozenset({"description", "rows"})
SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION = (
    "broker_reports_semantic_table_transcription_prompt_v1"
)
DESCRIPTION_TOKEN_BUDGET = 120
MAX_SEMANTIC_ROWS = 200
MAX_SEMANTIC_COLUMNS = 200
MAX_SEMANTIC_CELL_CHARACTERS = 12_000

MODEL_FORBIDDEN_FIELDS = frozenset(
    {
        "schema_version",
        "table_id",
        "document_id",
        "artifact_id",
        "source_id",
        "page_number",
        "crop_id",
        "crop_sha256",
        "provider",
        "model",
        "prompt_hash",
        "schema_hash",
        "request_hash",
        "response_hash",
        "row_index",
        "column_index",
        "row_span",
        "column_span",
        "bbox",
        "bounding_box",
        "coordinates",
        "row_count",
        "column_count",
        "cell_id",
        "content_state",
    }
)

SEMANTIC_TABLE_TRANSCRIPTION_PROMPT = """Transcribe exactly one logical table from the supplied immutable table crop.
Ignore nearby material that is not part of the central visible table. Return only one JSON
object matching the supplied schema, with exactly description and rows. Description is a short
source-oriented observation with a maximum budget of 120 tokens. It may mention the table
subject, visible sections, ambiguous layout, or unreadable material. It must not calculate,
interpret financially, or repeat the entire table. Rows preserves logical row order. Every row
is an array and every cell is either a string or null. Null means no visible text exists in that
logical position. Preserve every source-visible label, amount, currency sign, parenthesis,
percentage sign, sign, punctuation mark, and separator literally. Keep all values as strings.
Multi-line text inside one logical cell may be collapsed to one space. Use the minimum number of
logical columns needed to preserve label/value relationships. Indentation, visual whitespace,
and decorative bands must not create columns. A section row may contain text in one cell and
null in remaining cells. Do not insert inferred or editorial headers. Do not place explanations
inside cells. Do not return schema, table, document, artifact, page, crop, provider, model,
prompt, hash, index, span, bounding-box, coordinate, physical-grid, cell-identity, or
content-state metadata. Do not return comments outside the JSON object. Do not repair, infer,
normalize, calculate, translate, classify, or assign financial meaning."""


class SemanticTableTranscriptionContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def semantic_table_transcription_schema() -> dict[str, Any]:
    """Return the closed JSON schema for the VLM response boundary."""

    cell = {
        "anyOf": [
            {"type": "string", "maxLength": MAX_SEMANTIC_CELL_CHARACTERS},
            {"type": "null"},
        ]
    }
    row = {
        "type": "array",
        "items": cell,
        "minItems": 1,
        "maxItems": MAX_SEMANTIC_COLUMNS,
    }
    return {
        "$id": SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
        "type": "object",
        "additionalProperties": False,
        "required": sorted(SEMANTIC_TABLE_TRANSCRIPTION_ROOT_FIELDS),
        "properties": {
            "description": {"type": "string"},
            "rows": {
                "type": "array",
                "items": row,
                "minItems": 1,
                "maxItems": MAX_SEMANTIC_ROWS,
            },
        },
    }


def semantic_table_transcription_model_view() -> dict[str, str]:
    """Return the content-only task presented to the existing VLM adapters."""

    return {"task": SEMANTIC_TABLE_TRANSCRIPTION_PROMPT}


def semantic_table_transcription_boundary_errors(value: Any) -> list[str]:
    """Validate the strict response shape needed by the provider boundary.

    The full bounded semantic validator, including description-token accounting,
    remains a separate contract goal. This boundary check performs no repair or
    text normalization.
    """

    if not isinstance(value, dict):
        return ["semantic_table_transcription_not_object"]
    errors: list[str] = []
    if set(value) != SEMANTIC_TABLE_TRANSCRIPTION_ROOT_FIELDS:
        errors.append("semantic_table_transcription_fields_invalid")
    if not isinstance(value.get("description"), str):
        errors.append("semantic_table_transcription_description_invalid")
    rows = value.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_SEMANTIC_ROWS:
        errors.append("semantic_table_transcription_rows_invalid")
        return errors
    for row_index, row in enumerate(rows):
        if (
            not isinstance(row, list)
            or not row
            or len(row) > MAX_SEMANTIC_COLUMNS
        ):
            errors.append(f"semantic_table_transcription_row_{row_index}_invalid")
            continue
        for column_index, cell in enumerate(row):
            if cell is None:
                continue
            if not isinstance(cell, str) or len(cell) > MAX_SEMANTIC_CELL_CHARACTERS:
                errors.append(
                    "semantic_table_transcription_cell_"
                    f"{row_index}_{column_index}_invalid"
                )
    return errors


def parse_semantic_table_transcription(value: Any) -> dict[str, Any]:
    """Return an unchanged private semantic payload or fail without repair."""

    errors = semantic_table_transcription_boundary_errors(value)
    if errors:
        raise SemanticTableTranscriptionContractError(errors[0])
    return copy.deepcopy(value)
