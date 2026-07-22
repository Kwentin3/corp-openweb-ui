"""Authoritative model-facing contract for semantic visual-table transcription.

This module owns only the response shape presented to a VLM.  Source identity,
provider metadata, indexes, logical empty-cell materialization, hashes,
persistence, and terminal state belong to deterministic application code.
"""

from __future__ import annotations

from typing import Any


SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION = (
    "broker_reports_semantic_table_transcription_v1"
)
SEMANTIC_TABLE_TRANSCRIPTION_ROOT_FIELDS = frozenset({"description", "rows"})
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
