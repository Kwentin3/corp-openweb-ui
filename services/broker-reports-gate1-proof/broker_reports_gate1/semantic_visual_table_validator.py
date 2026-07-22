from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any

from .semantic_visual_table_contracts import (
    DESCRIPTION_TOKEN_BUDGET,
    MAX_SEMANTIC_CELL_CHARACTERS,
    MAX_SEMANTIC_COLUMNS,
    MAX_SEMANTIC_DESCRIPTION_CHARACTERS,
    MAX_SEMANTIC_ROWS,
    SEMANTIC_TABLE_TRANSCRIPTION_ROOT_FIELDS,
)


SEMANTIC_VISUAL_TABLE_VALIDATOR_VERSION = "semantic_visual_table_validator_v1"
SEMANTIC_VISUAL_TABLE_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_semantic_visual_table_validation_v1"
)
DESCRIPTION_TOKEN_COUNT_POLICY = "unicode_word_or_punctuation_v1"

FACTORY_REQUIRED = (
    "SemanticVisualTableValidatorFactory.create is the only maintained bounded "
    "semantic VLM response validator entrypoint"
)
FORBIDDEN = (
    "The semantic validator must not repair responses, require physical geometry, "
    "claim source-content correctness, infer financial meaning, or require review"
)


@dataclass(frozen=True)
class SemanticVisualTableValidatorConfig:
    description_token_budget: int = DESCRIPTION_TOKEN_BUDGET
    maximum_description_characters: int = MAX_SEMANTIC_DESCRIPTION_CHARACTERS
    maximum_rows: int = MAX_SEMANTIC_ROWS
    maximum_columns: int = MAX_SEMANTIC_COLUMNS
    maximum_cell_characters: int = MAX_SEMANTIC_CELL_CHARACTERS


class SemanticVisualTableValidatorFactory:
    def __init__(
        self, config: SemanticVisualTableValidatorConfig | None = None
    ) -> None:
        self.config = config or SemanticVisualTableValidatorConfig()

    def create(self) -> "SemanticVisualTableValidator":
        if (
            self.config.description_token_budget < 1
            or self.config.description_token_budget > DESCRIPTION_TOKEN_BUDGET
            or self.config.maximum_description_characters < 1
            or self.config.maximum_description_characters
            > MAX_SEMANTIC_DESCRIPTION_CHARACTERS
            or self.config.maximum_rows < 1
            or self.config.maximum_rows > MAX_SEMANTIC_ROWS
            or self.config.maximum_columns < 1
            or self.config.maximum_columns > MAX_SEMANTIC_COLUMNS
            or self.config.maximum_cell_characters < 1
            or self.config.maximum_cell_characters
            > MAX_SEMANTIC_CELL_CHARACTERS
        ):
            raise ValueError("semantic_visual_table_validator_budget_invalid")
        return SemanticVisualTableValidator(self.config)


class SemanticVisualTableValidator:
    def __init__(self, config: SemanticVisualTableValidatorConfig) -> None:
        self.config = config

    def validate(
        self,
        value: Any,
        *,
        raw_json_text: str | None = None,
        require_raw_json: bool = False,
    ) -> dict[str, Any]:
        errors: list[str] = []
        if require_raw_json or raw_json_text is not None:
            errors.extend(_raw_json_errors(raw_json_text, expected=value))
        if not isinstance(value, dict):
            errors.append("semantic_table_transcription_not_object")
            value = {}
        if set(value) != SEMANTIC_TABLE_TRANSCRIPTION_ROOT_FIELDS:
            errors.append("semantic_table_transcription_fields_invalid")

        description = value.get("description")
        description_tokens = 0
        if not isinstance(description, str):
            errors.append("semantic_table_transcription_description_invalid")
        else:
            description_tokens = count_description_tokens(description)
            if (
                len(description) > self.config.maximum_description_characters
                or description_tokens > self.config.description_token_budget
            ):
                errors.append("semantic_table_transcription_description_budget_exceeded")

        rows = value.get("rows")
        row_count = 0
        maximum_column_count = 0
        cell_count = 0
        if not isinstance(rows, list) or not rows:
            errors.append("semantic_table_transcription_rows_invalid")
        elif len(rows) > self.config.maximum_rows:
            errors.append("semantic_table_transcription_row_budget_exceeded")
        else:
            row_count = len(rows)
            for row_index, row in enumerate(rows):
                if not isinstance(row, list) or not row:
                    errors.append(
                        f"semantic_table_transcription_row_{row_index}_invalid"
                    )
                    continue
                maximum_column_count = max(maximum_column_count, len(row))
                cell_count += len(row)
                if len(row) > self.config.maximum_columns:
                    errors.append(
                        f"semantic_table_transcription_row_{row_index}_column_budget_exceeded"
                    )
                for column_index, cell in enumerate(row):
                    if cell is None:
                        continue
                    if isinstance(cell, (dict, list)):
                        errors.append(
                            "semantic_table_transcription_cell_"
                            f"{row_index}_{column_index}_nested_value_forbidden"
                        )
                    elif not isinstance(cell, str):
                        errors.append(
                            "semantic_table_transcription_cell_"
                            f"{row_index}_{column_index}_type_invalid"
                        )
                    elif len(cell) > self.config.maximum_cell_characters:
                        errors.append(
                            "semantic_table_transcription_cell_"
                            f"{row_index}_{column_index}_text_budget_exceeded"
                        )

        errors = sorted(set(errors))
        return {
            "schema_version": SEMANTIC_VISUAL_TABLE_VALIDATION_SCHEMA_VERSION,
            "validator_version": SEMANTIC_VISUAL_TABLE_VALIDATOR_VERSION,
            "validator_status": "passed" if not errors else "failed",
            "semantic_response_contract_passed": not errors,
            "error_codes": errors,
            "description_token_count_policy": DESCRIPTION_TOKEN_COUNT_POLICY,
            "description_token_count": description_tokens,
            "description_token_budget": self.config.description_token_budget,
            "row_count": row_count,
            "maximum_column_count": maximum_column_count,
            "cell_count": cell_count,
            "valid_json_required": True,
            "exact_root_fields_required": True,
            "hidden_repair_performed": False,
            "geometric_validation_performed": False,
            "human_review_required": False,
            "source_content_correctness_claimed": False,
            "financial_correctness_claimed": False,
        }


def validate_semantic_visual_table_response(
    value: Any,
    *,
    raw_json_text: str | None = None,
    require_raw_json: bool = False,
) -> dict[str, Any]:
    return SemanticVisualTableValidatorFactory().create().validate(
        value,
        raw_json_text=raw_json_text,
        require_raw_json=require_raw_json,
    )


def count_description_tokens(value: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", value, flags=re.UNICODE))


def _raw_json_errors(raw_json_text: Any, *, expected: Any) -> list[str]:
    if not isinstance(raw_json_text, str):
        return ["semantic_table_transcription_raw_json_missing"]
    try:
        parsed = json.loads(raw_json_text)
    except (json.JSONDecodeError, RecursionError):
        return ["semantic_table_transcription_raw_json_invalid"]
    if parsed != expected:
        return ["semantic_table_transcription_raw_json_binding_invalid"]
    return []


def unchanged_semantic_response(value: dict[str, Any]) -> dict[str, Any]:
    """Expose the no-repair operation explicitly for anti-drift tests."""

    return copy.deepcopy(value)
