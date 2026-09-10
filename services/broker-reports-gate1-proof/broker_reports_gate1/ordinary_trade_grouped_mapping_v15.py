"""V15 wire identity for the compact ordinary-trade mapping representation.

V15 preserves the existing compact representation while delegating its
value-free expansion to the retained V14 implementation.  Its distinct wire
identity prevents a prompt pinned to the old V14 schema from silently
receiving the newer semantic-mapping v14 surface.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .ordinary_trade_grouped_mapping_v14 import (
    OrdinaryTradeGroupedMappingV14Error,
    expand_grouped_response as _expand_v14,
    grouped_mapping_response_format as _format_v14,
)


ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_grouped_mapping_response_v14"
)
ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_grouped_mapping_response_v15"
)


class OrdinaryTradeGroupedMappingV15Error(RuntimeError):
    """A value-free rejection at the V15 representation boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeGroupedMappingV15AdapterFactory:
    """Create the one V15 representation adapter."""

    @staticmethod
    def create() -> "OrdinaryTradeGroupedMappingV15Adapter":
        return OrdinaryTradeGroupedMappingV15Adapter()


class OrdinaryTradeGroupedMappingV15Adapter:
    """Expose compact V15 and expand it to the maintained semantic owner."""

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
    result = _format_v14(v13_response_format=v13_response_format)
    _replace_wire_version(
        result,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION,
    )
    return result


def expand_grouped_response(*, response: Any, package: Mapping[str, Any]) -> dict[str, Any]:
    value = getattr(response, "content", response)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise OrdinaryTradeGroupedMappingV15Error(
                "ordinary_trade_grouped_mapping_v15_response_invalid"
            ) from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version")
        != ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION
    ):
        raise OrdinaryTradeGroupedMappingV15Error(
            "ordinary_trade_grouped_mapping_v15_response_invalid"
        )
    value = copy.deepcopy(value)
    _replace_wire_version(
        value,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION,
    )
    try:
        return _expand_v14(response=value, package=package)
    except OrdinaryTradeGroupedMappingV14Error as exc:
        raise OrdinaryTradeGroupedMappingV15Error(
            exc.code.replace("_v14_", "_v15_")
        ) from exc


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


__all__ = [
    "ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION",
    "OrdinaryTradeGroupedMappingV15Adapter",
    "OrdinaryTradeGroupedMappingV15AdapterFactory",
    "OrdinaryTradeGroupedMappingV15Error",
    "expand_grouped_response",
    "grouped_mapping_response_format",
]
