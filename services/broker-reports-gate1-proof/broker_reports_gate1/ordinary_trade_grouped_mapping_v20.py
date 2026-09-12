"""V20 wire identity for model-selected Canonical header rows.

V20 changes no PDF or Canonical structure.  It permits the mapping owner to
accept a header row selected from the complete rows already exposed in the
case.  The semantic owner, not this representation adapter, binds that row
and its cells back to Canonical.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .ordinary_trade_grouped_mapping_v18 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV18Error,
    explicit_header_source_claims as _claims_v18,
    expand_grouped_response as _expand_v18,
    grouped_mapping_response_format as _format_v18,
)


ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_grouped_mapping_response_v20"
)


class OrdinaryTradeGroupedMappingV20Error(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeGroupedMappingV20AdapterFactory:
    @staticmethod
    def create() -> "OrdinaryTradeGroupedMappingV20Adapter":
        return OrdinaryTradeGroupedMappingV20Adapter()


class OrdinaryTradeGroupedMappingV20Adapter:
    """Expose V20 without owning header or financial interpretation."""

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

    @property
    def allows_source_bound_position_effect(self) -> bool:
        return True

    @property
    def allows_model_selected_header(self) -> bool:
        return True


def grouped_mapping_response_format(
    *, v13_response_format: Mapping[str, Any]
) -> dict[str, Any]:
    result = _format_v18(v13_response_format=v13_response_format)
    _replace_wire_version(
        result,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
    )
    schema = result.get("json_schema")
    if not isinstance(schema, dict) or not isinstance(schema.get("schema"), dict):
        _fail("ordinary_trade_grouped_mapping_v20_response_format_invalid")
    schema["name"] = "broker_reports_ordinary_trade_grouped_mapping_response_v20"
    return result


def expand_grouped_response(*, response: Any, package: Mapping[str, Any]) -> dict[str, Any]:
    """Validate V20's identity, then reuse the retained V18 wire expansion."""

    value = getattr(response, "content", response)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise OrdinaryTradeGroupedMappingV20Error(
                "ordinary_trade_grouped_mapping_v20_response_invalid"
            ) from exc
    if not isinstance(value, Mapping) or value.get("schema_version") != (
        ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION
    ):
        _fail("ordinary_trade_grouped_mapping_v20_response_invalid")
    v18_value = copy.deepcopy(dict(value))
    _replace_wire_version(
        v18_value,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION,
    )
    try:
        return _expand_v18(response=v18_value, package=package)
    except OrdinaryTradeGroupedMappingV18Error as exc:
        raise OrdinaryTradeGroupedMappingV20Error(
            exc.code.replace("_v18_", "_v20_")
        ) from exc


def explicit_header_source_claims(*, response: Any) -> dict[str, Any]:
    value = getattr(response, "content", response)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise OrdinaryTradeGroupedMappingV20Error(
                "ordinary_trade_grouped_mapping_v20_response_invalid"
            ) from exc
    if not isinstance(value, Mapping) or value.get("schema_version") != (
        ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION
    ):
        _fail("ordinary_trade_grouped_mapping_v20_response_invalid")
    v18_value = copy.deepcopy(dict(value))
    _replace_wire_version(
        v18_value,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION,
    )
    try:
        return _claims_v18(response=v18_value)
    except OrdinaryTradeGroupedMappingV18Error as exc:
        raise OrdinaryTradeGroupedMappingV20Error(
            exc.code.replace("_v18_", "_v20_")
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


def _fail(code: str) -> None:
    raise OrdinaryTradeGroupedMappingV20Error(code)


__all__ = [
    "ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION",
    "OrdinaryTradeGroupedMappingV20Adapter",
    "OrdinaryTradeGroupedMappingV20AdapterFactory",
    "OrdinaryTradeGroupedMappingV20Error",
    "expand_grouped_response",
    "explicit_header_source_claims",
    "grouped_mapping_response_format",
]
