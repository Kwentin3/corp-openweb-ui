"""Representation-only v14 adapter for ordinary-trade semantic mapping.

The established semantic mapping contract is v13.  V14 only compresses a
uniform trade-row answer into a declared default plus explicit exceptions.
This module expands that representation back to v13 before the semantic owner
sees it.  It does not interpret Canonical, classify financial meaning, or
persist a mapping outcome.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .ordinary_trade_semantic_mapping import (
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)


ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_grouped_mapping_response_v14"
)


class OrdinaryTradeGroupedMappingV14Error(RuntimeError):
    """A value-free rejection at the grouped response representation boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeGroupedMappingV14AdapterFactory:
    """Create the one representation adapter for the optional v14 contract."""

    @staticmethod
    def create() -> "OrdinaryTradeGroupedMappingV14Adapter":
        return OrdinaryTradeGroupedMappingV14Adapter()


class OrdinaryTradeGroupedMappingV14Adapter:
    """Derive the v14 format and expand a v14 answer to the v13 contract."""

    def mapping_response_format(
        self, *, v13_response_format: Mapping[str, Any]
    ) -> dict[str, Any]:
        return grouped_mapping_response_format(v13_response_format=v13_response_format)

    def expand_to_v13(
        self, *, response: Any, package: Mapping[str, Any]
    ) -> dict[str, Any]:
        return expand_grouped_response(response=response, package=package)


def grouped_mapping_response_format(
    *, v13_response_format: Mapping[str, Any]
) -> dict[str, Any]:
    """Derive the strict v14 schema from the one maintained v13 schema."""

    result = copy.deepcopy(dict(v13_response_format))
    schema = result.get("json_schema")
    if not isinstance(schema, dict) or not isinstance(schema.get("schema"), dict):
        _fail("ordinary_trade_grouped_mapping_v14_response_format_invalid")
    schema["name"] = "broker_reports_ordinary_trade_grouped_mapping_response_v14"
    _replace_version(schema["schema"])
    changed = _replace_trade_row_dispositions(schema["schema"])
    if changed != 2:
        _fail("ordinary_trade_grouped_mapping_v14_response_format_invalid")
    return result


def expand_grouped_response(*, response: Any, package: Mapping[str, Any]) -> dict[str, Any]:
    """Expand compact v14 policies to an exact v13 model answer.

    A row is covered only by the model-declared default or an explicit listed
    exception.  The existing v13 semantic owner validates the resulting full
    row coverage and all financial meaning afterwards.
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
        or value.get("schema_version")
        != ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION
        or not isinstance(value.get("table_decisions"), list)
    ):
        _fail("ordinary_trade_grouped_mapping_v14_response_invalid")
    # A physical header is Canonical-owned structure, never a model-selected
    # row. Bind its compatible wire echo before row_policy expands row scope.
    value = OrdinaryTradeSemanticMappingFactory.create().bind_source_owned_headers(
        response=value,
        package=package,
    )
    rows_by_ref = _rows_by_table_ref(package)
    expanded = copy.deepcopy(value)
    expanded["schema_version"] = MAPPING_RESPONSE_SCHEMA_VERSION
    decisions: list[dict[str, Any]] = []
    for item in value["table_decisions"]:
        if not isinstance(item, dict):
            _fail("ordinary_trade_grouped_mapping_v14_response_invalid")
        decision = copy.deepcopy(item)
        disposition = decision.get("disposition")
        if disposition not in {"SECURITY_TRADES", "SECURITY_TRADES_INCOMPLETE"}:
            decisions.append(decision)
            continue
        table_ref = decision.get("table_ref")
        header_row = decision.get("header_row")
        if not isinstance(table_ref, str) or not isinstance(header_row, int):
            _fail("ordinary_trade_grouped_mapping_v14_response_invalid")
        policy = decision.pop("row_policy", None)
        policy = _without_source_header_exceptions(
            policy=policy,
            physical_header_row=header_row,
        )
        expected_rows = [
            row["row"]
            for row in rows_by_ref.get(table_ref, [])
            if row["row"] > header_row and row["cells"]
        ]
        if not expected_rows:
            _fail("ordinary_trade_grouped_mapping_v14_row_scope_invalid")
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
            value[key] = ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION
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
            _fail("ordinary_trade_grouped_mapping_v14_response_invalid")
    return copy.deepcopy(value)


def _rows_by_table_ref(package: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    case = package.get("case") if isinstance(package, Mapping) else None
    tables = case.get("tables") if isinstance(case, Mapping) else None
    if not isinstance(tables, list):
        _fail("ordinary_trade_grouped_mapping_v14_package_invalid")
    result: dict[str, list[dict[str, Any]]] = {}
    for table in tables:
        if not isinstance(table, Mapping):
            _fail("ordinary_trade_grouped_mapping_v14_package_invalid")
        table_ref = table.get("table_ref")
        rows = table.get("rows")
        if (
            not isinstance(table_ref, str)
            or not table_ref
            or table_ref in result
            or not isinstance(rows, list)
        ):
            _fail("ordinary_trade_grouped_mapping_v14_package_invalid")
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            if (
                not isinstance(row, Mapping)
                or not isinstance(row.get("row"), int)
                or row["row"] < 1
                or not isinstance(row.get("cells"), list)
            ):
                _fail("ordinary_trade_grouped_mapping_v14_package_invalid")
            normalized_rows.append(
                {"row": row["row"], "cells": copy.deepcopy(row["cells"])}
            )
        if [item["row"] for item in normalized_rows] != sorted(
            {item["row"] for item in normalized_rows}
        ):
            _fail("ordinary_trade_grouped_mapping_v14_package_invalid")
        result[table_ref] = normalized_rows
    return result


def _validated_exceptions(*, policy: Any, expected_rows: list[int]) -> dict[int, str]:
    if (
        not isinstance(policy, Mapping)
        or set(policy) != {"default_disposition", "exception_rows"}
        or policy.get("default_disposition") != "SECURITY_TRADES"
        or not isinstance(policy.get("exception_rows"), list)
    ):
        _fail("ordinary_trade_grouped_mapping_v14_row_policy_invalid")
    exceptions: dict[int, str] = {}
    rows: list[int] = []
    for item in policy["exception_rows"]:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"row", "disposition"}
            or not isinstance(item.get("row"), int)
            or item.get("disposition") != "NO_NAMED_CONSUMER"
        ):
            _fail("ordinary_trade_grouped_mapping_v14_row_policy_invalid")
        row = item["row"]
        rows.append(row)
        exceptions[row] = "NO_NAMED_CONSUMER"
    if rows != sorted(set(rows)) or not set(rows) <= set(expected_rows):
        _fail("ordinary_trade_grouped_mapping_v14_row_policy_invalid")
    return exceptions


def _without_source_header_exceptions(
    *, policy: Any, physical_header_row: int
) -> Any:
    """Discard only compact exceptions that name Canonical-owned header rows.

    A compact row policy is a wire optimisation. The physical header already
    belongs to Canonical and cannot be a financial operation, so a model echo
    that excludes that row must not invalidate the whole table. Malformed
    policies and every row after the header still reach the fail-closed
    validator unchanged.
    """

    if not isinstance(policy, Mapping):
        return policy
    exceptions = policy.get("exception_rows")
    if not isinstance(exceptions, list):
        return policy
    normalized = copy.deepcopy(dict(policy))
    normalized["exception_rows"] = [
        item
        for item in exceptions
        if not (
            isinstance(item, Mapping)
            and isinstance(item.get("row"), int)
            and item["row"] <= physical_header_row
        )
    ]
    return normalized


def _fail(code: str) -> None:
    raise OrdinaryTradeGroupedMappingV14Error(code)


__all__ = [
    "ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION",
    "OrdinaryTradeGroupedMappingV14Adapter",
    "OrdinaryTradeGroupedMappingV14AdapterFactory",
    "OrdinaryTradeGroupedMappingV14Error",
    "expand_grouped_response",
    "grouped_mapping_response_format",
]
