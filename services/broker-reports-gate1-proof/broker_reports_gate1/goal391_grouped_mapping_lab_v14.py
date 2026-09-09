"""Goal #391 lab-only compact response contract for semantic table mapping.

The production v13 contract asks the model to repeat one disposition for every
source row.  This R&D adapter changes *only* that response representation:
the model supplies an all-trades default plus explicit non-trade exceptions.
The adapter expands the compact answer back to the immutable v13 contract and
lets the existing semantic owner perform its normal exact coverage validation.

It owns neither Canonical interpretation nor a second mapping route.  It is
intentionally usable only by the isolated qualification Pipe.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .ordinary_trade_mapping_prompt import (
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_COMMAND as _PROMPT_COMMAND,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_REQUIRED_TAG as _PROMPT_REQUIRED_TAG,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_ID as _PROMPT_TEMPLATE_ID,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_KIND as _PROMPT_TEMPLATE_KIND,
    GOAL391_GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION as _RESPONSE_SCHEMA_VERSION,
)
from .ordinary_trade_semantic_mapping import (
    MAPPING_RESPONSE_SCHEMA_VERSION,
)


GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION = (
    _RESPONSE_SCHEMA_VERSION
)
# Re-export the shared native Prompt identities for the isolated lab composer.
GROUPED_MAPPING_LAB_PROMPT_COMMAND = _PROMPT_COMMAND
GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_ID = _PROMPT_TEMPLATE_ID
GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_KIND = (
    _PROMPT_TEMPLATE_KIND
)
GROUPED_MAPPING_LAB_PROMPT_REQUIRED_TAG = (
    _PROMPT_REQUIRED_TAG
)


class Goal391GroupedMappingLabError(RuntimeError):
    """A value-free rejection at the isolated v14 response boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def grouped_mapping_response_format(*, v13_response_format: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the v14 strict schema from the single existing v13 schema.

    The derivation prevents a second hand-maintained copy of all table roles,
    instructional branches and safe terminals.  Only the trade-row answer is
    replaced: one default plus a short, explicit exception list.
    """

    result = copy.deepcopy(dict(v13_response_format))
    schema = result.get("json_schema")
    if not isinstance(schema, dict) or not isinstance(schema.get("schema"), dict):
        _fail("goal391_grouped_mapping_lab_response_format_invalid")
    schema["name"] = "goal391_grouped_ordinary_trade_mapping_response_v14"
    _replace_version(schema["schema"])
    changed = _replace_trade_row_dispositions(schema["schema"])
    if changed != 2:
        _fail("goal391_grouped_mapping_lab_response_format_invalid")
    return result


def expand_grouped_response(*, response: Any, package: Mapping[str, Any]) -> dict[str, Any]:
    """Expand compact v14 trade policies into an exact v13 model response.

    This performs no financial classification.  A source row is either covered
    by the model's declared default or by its own listed exception; every
    resulting v13 row disposition is then revalidated by the established
    semantic owner.
    """

    value = _response_value(response)
    required = {
        "schema_version",
        "status",
        "table_decisions",
        "clarification",
        "message",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("schema_version") != GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION
        or not isinstance(value.get("table_decisions"), list)
    ):
        _fail("goal391_grouped_mapping_lab_response_invalid")
    rows_by_ref = _rows_by_table_ref(package)
    expanded = copy.deepcopy(value)
    expanded["schema_version"] = MAPPING_RESPONSE_SCHEMA_VERSION
    decisions: list[dict[str, Any]] = []
    for item in value["table_decisions"]:
        if not isinstance(item, dict):
            _fail("goal391_grouped_mapping_lab_response_invalid")
        decision = copy.deepcopy(item)
        disposition = decision.get("disposition")
        if disposition not in {"SECURITY_TRADES", "SECURITY_TRADES_INCOMPLETE"}:
            decisions.append(decision)
            continue
        table_ref = decision.get("table_ref")
        header_row = decision.get("header_row")
        if not isinstance(table_ref, str) or not isinstance(header_row, int):
            _fail("goal391_grouped_mapping_lab_response_invalid")
        policy = decision.pop("row_policy", None)
        expected_rows = [
            row["row"]
            for row in rows_by_ref.get(table_ref, [])
            if row["row"] > header_row and row["cells"]
        ]
        if not expected_rows:
            _fail("goal391_grouped_mapping_lab_row_scope_invalid")
        exceptions = _validated_exceptions(policy=policy, expected_rows=expected_rows)
        decision["row_dispositions"] = [
            {
                "row": row,
                "disposition": exceptions.get(row, "SECURITY_TRADES"),
            }
            for row in expected_rows
        ]
        decisions.append(decision)
    expanded["table_decisions"] = decisions
    return expanded


def _replace_version(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _replace_version(item)
        return
    if not isinstance(value, dict):
        return
    for key, item in tuple(value.items()):
        if item == MAPPING_RESPONSE_SCHEMA_VERSION:
            value[key] = GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION
        else:
            _replace_version(item)


def _replace_trade_row_dispositions(value: Any) -> int:
    if isinstance(value, list):
        return sum(_replace_trade_row_dispositions(item) for item in value)
    if not isinstance(value, dict):
        return 0
    changed = 0
    properties = value.get("properties")
    disposition = properties.get("disposition") if isinstance(properties, dict) else None
    if (
        isinstance(disposition, dict)
        and disposition.get("const") in {"SECURITY_TRADES", "SECURITY_TRADES_INCOMPLETE"}
        and isinstance(value.get("required"), list)
        and "row_dispositions" in value["required"]
    ):
        value["required"] = [
            "row_policy" if item == "row_dispositions" else item
            for item in value["required"]
        ]
        properties.pop("row_dispositions", None)
        properties["row_policy"] = _row_policy_schema()
        changed += 1
    for item in value.values():
        changed += _replace_trade_row_dispositions(item)
    return changed


def _row_policy_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["default_disposition", "exception_rows"],
        "properties": {
            "default_disposition": {"const": "SECURITY_TRADES"},
            "exception_rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["row", "disposition"],
                    "properties": {
                        "row": {"type": "integer", "minimum": 1},
                        "disposition": {"const": "NO_NAMED_CONSUMER"},
                    },
                },
            },
        },
    }


def _response_value(response: Any) -> Any:
    value = getattr(response, "content", response)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            _fail("goal391_grouped_mapping_lab_response_invalid")
    return copy.deepcopy(value)


def _rows_by_table_ref(package: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    case = package.get("case") if isinstance(package, Mapping) else None
    tables = case.get("tables") if isinstance(case, Mapping) else None
    if not isinstance(tables, list):
        _fail("goal391_grouped_mapping_lab_package_invalid")
    result: dict[str, list[dict[str, Any]]] = {}
    for table in tables:
        if not isinstance(table, Mapping):
            _fail("goal391_grouped_mapping_lab_package_invalid")
        table_ref = table.get("table_ref")
        rows = table.get("rows")
        if (
            not isinstance(table_ref, str)
            or not table_ref
            or table_ref in result
            or not isinstance(rows, list)
        ):
            _fail("goal391_grouped_mapping_lab_package_invalid")
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            if (
                not isinstance(row, Mapping)
                or not isinstance(row.get("row"), int)
                or row["row"] < 1
                or not isinstance(row.get("cells"), list)
            ):
                _fail("goal391_grouped_mapping_lab_package_invalid")
            normalized_rows.append(
                {"row": row["row"], "cells": copy.deepcopy(row["cells"])}
            )
        if [item["row"] for item in normalized_rows] != sorted(
            {item["row"] for item in normalized_rows}
        ):
            _fail("goal391_grouped_mapping_lab_package_invalid")
        result[table_ref] = normalized_rows
    return result


def _validated_exceptions(*, policy: Any, expected_rows: list[int]) -> dict[int, str]:
    if (
        not isinstance(policy, Mapping)
        or set(policy) != {"default_disposition", "exception_rows"}
        or policy.get("default_disposition") != "SECURITY_TRADES"
        or not isinstance(policy.get("exception_rows"), list)
    ):
        _fail("goal391_grouped_mapping_lab_row_policy_invalid")
    exceptions: dict[int, str] = {}
    rows: list[int] = []
    for item in policy["exception_rows"]:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"row", "disposition"}
            or not isinstance(item.get("row"), int)
            or item.get("disposition") != "NO_NAMED_CONSUMER"
        ):
            _fail("goal391_grouped_mapping_lab_row_policy_invalid")
        row = item["row"]
        rows.append(row)
        exceptions[row] = "NO_NAMED_CONSUMER"
    if rows != sorted(set(rows)) or not set(rows) <= set(expected_rows):
        _fail("goal391_grouped_mapping_lab_row_policy_invalid")
    return exceptions


def _fail(code: str) -> None:
    raise Goal391GroupedMappingLabError(code)


__all__ = [
    "GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION",
    "GROUPED_MAPPING_LAB_PROMPT_COMMAND",
    "GROUPED_MAPPING_LAB_PROMPT_REQUIRED_TAG",
    "GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_ID",
    "GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_KIND",
    "Goal391GroupedMappingLabError",
    "expand_grouped_response",
    "grouped_mapping_response_format",
]
