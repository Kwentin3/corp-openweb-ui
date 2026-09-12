"""V18 strict wire adapter for source-bound opening-short effects.

V18 changes only the model wire: one mapped side literal may carry the
optional, closed ``OPEN_SHORT`` effect.  Semantic admission remains owned by
the ordinary-trade mapping contract; this adapter neither interprets a phrase
nor looks at Canonical values.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .ordinary_trade_grouped_mapping_v17 import (
    OrdinaryTradeGroupedMappingV17Error,
    expand_grouped_response as _expand_v17,
    explicit_header_source_claims as _claims_v17,
    grouped_mapping_response_format as _format_v17,
)


ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_grouped_mapping_response_v17"
)
ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_grouped_mapping_response_v18"
)
_POSITION_EFFECT = "position_effect"
_OPEN_SHORT = "OPEN_SHORT"


class OrdinaryTradeGroupedMappingV18Error(RuntimeError):
    """A value-free rejection at the V18 representation boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeGroupedMappingV18AdapterFactory:
    """Create the one V18 representation adapter."""

    @staticmethod
    def create() -> "OrdinaryTradeGroupedMappingV18Adapter":
        return OrdinaryTradeGroupedMappingV18Adapter()


class OrdinaryTradeGroupedMappingV18Adapter:
    """Expose the strict V18 wire without becoming a semantic owner."""

    def mapping_response_format(
        self, *, v13_response_format: Mapping[str, Any]
    ) -> dict[str, Any]:
        return grouped_mapping_response_format(v13_response_format=v13_response_format)

    def expand_to_v13(
        self, *, response: Any, package: Mapping[str, Any]
    ) -> dict[str, Any]:
        return expand_grouped_response(response=response, package=package)

    def explicit_header_source_claims(self, *, response: Any) -> dict[str, Any]:
        return explicit_header_source_claims(response=response)


def grouped_mapping_response_format(
    *, v13_response_format: Mapping[str, Any]
) -> dict[str, Any]:
    """Derive V18 from V17 and add only an optional closed effect field."""

    result = _format_v17(v13_response_format=v13_response_format)
    schema = result.get("json_schema")
    root = schema.get("schema") if isinstance(schema, dict) else None
    if not isinstance(root, dict):
        _fail("ordinary_trade_grouped_mapping_v18_response_format_invalid")
    _replace_wire_version(
        result,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION,
    )
    schema["name"] = "broker_reports_ordinary_trade_grouped_mapping_response_v18"
    if _add_position_effect_to_side_values(root) != 2:
        _fail("ordinary_trade_grouped_mapping_v18_response_format_invalid")
    return result


def expand_grouped_response(*, response: Any, package: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the V18 root, then retain V17's grouped expansion owner."""

    try:
        return _expand_v17(response=_as_v17(response), package=package)
    except OrdinaryTradeGroupedMappingV17Error as exc:
        raise OrdinaryTradeGroupedMappingV18Error(
            exc.code.replace("_v17_", "_v18_")
        ) from exc


def explicit_header_source_claims(*, response: Any) -> dict[str, Any]:
    """Delegate the independent header-claim validator through V17."""

    try:
        return _claims_v17(response=_as_v17(response))
    except OrdinaryTradeGroupedMappingV17Error as exc:
        raise OrdinaryTradeGroupedMappingV18Error(
            exc.code.replace("_v17_", "_v18_")
        ) from exc


def _as_v17(response: Any) -> dict[str, Any]:
    value = getattr(response, "content", response)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise OrdinaryTradeGroupedMappingV18Error(
                "ordinary_trade_grouped_mapping_v18_response_invalid"
            ) from exc
    required = {
        "schema_version",
        "status",
        "table_decisions",
        "clarification",
        "message",
        "explicit_header_source_claims",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != required
        or value.get("schema_version")
        != ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION
    ):
        _fail("ordinary_trade_grouped_mapping_v18_response_invalid")
    result = copy.deepcopy(dict(value))
    result["schema_version"] = ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION
    return result


def _add_position_effect_to_side_values(value: Any) -> int:
    if isinstance(value, list):
        return sum(_add_position_effect_to_side_values(item) for item in value)
    if not isinstance(value, dict):
        return 0
    changed = 0
    properties = value.get("properties")
    side_values = properties.get("side_values") if isinstance(properties, dict) else None
    items = side_values.get("items") if isinstance(side_values, dict) else None
    item_properties = items.get("properties") if isinstance(items, dict) else None
    required = items.get("required") if isinstance(items, dict) else None
    if (
        isinstance(item_properties, dict)
        and required == ["source_literal", "normalized_value"]
        and _POSITION_EFFECT not in item_properties
    ):
        item_properties[_POSITION_EFFECT] = {"const": _OPEN_SHORT}
        changed += 1
    for item in value.values():
        changed += _add_position_effect_to_side_values(item)
    return changed


def _replace_wire_version(value: Any, *, source: str, target: str) -> None:
    if isinstance(value, dict):
        for key, item in tuple(value.items()):
            if item == source:
                value[key] = target
            else:
                _replace_wire_version(item, source=source, target=target)
    elif isinstance(value, list):
        for item in value:
            _replace_wire_version(item, source=source, target=target)


def _fail(code: str) -> None:
    raise OrdinaryTradeGroupedMappingV18Error(code)


__all__ = [
    "ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION",
    "OrdinaryTradeGroupedMappingV18Adapter",
    "OrdinaryTradeGroupedMappingV18AdapterFactory",
    "OrdinaryTradeGroupedMappingV18Error",
    "expand_grouped_response",
    "explicit_header_source_claims",
    "grouped_mapping_response_format",
]
