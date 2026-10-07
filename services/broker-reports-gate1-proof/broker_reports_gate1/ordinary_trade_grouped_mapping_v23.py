"""V23 wire contract for explicit headerless-table intent.

V23 adds no Canonical or financial meaning.  It makes the model state whether
each ``HEADER_ABSENT`` decision is a standalone source segment or a claimed
continuation.  The semantic owner still validates the claim against Canonical
and the qualified parent mapping.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .ordinary_trade_grouped_mapping_v20 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV20Error,
    explicit_header_source_claims as _claims_v20,
    expand_grouped_response as _expand_v20,
    grouped_mapping_response_format as _format_v20,
)


ORDINARY_TRADE_GROUPED_MAPPING_V23_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_grouped_mapping_response_v23"
)
HEADERLESS_DISPOSITION_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_headerless_disposition_response_v1"
)
_HEADERLESS_DISPOSITION_FIELD = "headerless_disposition"
_HEADERLESS_DISPOSITIONS = {"STANDALONE", "CONTINUATION"}


class OrdinaryTradeGroupedMappingV23Error(RuntimeError):
    """A value-free rejection at the V23 representation boundary."""

    def __init__(self, code: str, *, safe_shape_category: str | None = None) -> None:
        self.code = code
        self.safe_shape_category = safe_shape_category
        super().__init__(code)


class OrdinaryTradeGroupedMappingV23AdapterFactory:
    @staticmethod
    def create() -> "OrdinaryTradeGroupedMappingV23Adapter":
        return OrdinaryTradeGroupedMappingV23Adapter()


class OrdinaryTradeGroupedMappingV23Adapter:
    """Expose V23 while retaining the V20 representation adapter."""

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

    def headerless_dispositions(self, *, response: Any) -> dict[str, Any]:
        return headerless_dispositions(response=response)

    @property
    def requires_headerless_dispositions(self) -> bool:
        return True

    @property
    def allows_source_bound_position_effect(self) -> bool:
        return True

    @property
    def allows_model_selected_header(self) -> bool:
        return True


def grouped_mapping_response_format(
    *, v13_response_format: Mapping[str, Any]
) -> dict[str, Any]:
    """Derive V23 from V20 and require a closed headerless disposition."""

    result = _format_v20(v13_response_format=v13_response_format)
    _replace_wire_version(
        result,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V23_RESPONSE_SCHEMA_VERSION,
    )
    schema = result.get("json_schema")
    root = schema.get("schema") if isinstance(schema, Mapping) else None
    if not isinstance(root, dict):
        _fail("ordinary_trade_grouped_mapping_v23_response_format_invalid")
    schema["name"] = "broker_reports_ordinary_trade_grouped_mapping_response_v23"
    if _add_headerless_disposition(root) != 1:
        _fail("ordinary_trade_grouped_mapping_v23_response_format_invalid")
    return result


def expand_grouped_response(*, response: Any, package: Mapping[str, Any]) -> dict[str, Any]:
    """Validate V23-only fields before delegating the retained V20 expansion."""

    value = _validated_v23_value(response=response)
    v20_value = copy.deepcopy(value)
    for decision in v20_value["table_decisions"]:
        if isinstance(decision, dict):
            decision.pop(_HEADERLESS_DISPOSITION_FIELD, None)
    _replace_wire_version(
        v20_value,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V23_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
    )
    try:
        return _expand_v20(response=v20_value, package=package)
    except OrdinaryTradeGroupedMappingV20Error as exc:
        raise OrdinaryTradeGroupedMappingV23Error(
            exc.code.replace("_v20_", "_v23_"),
            safe_shape_category=getattr(exc, "safe_shape_category", None),
        ) from exc


def explicit_header_source_claims(*, response: Any) -> dict[str, Any]:
    """Delegate existing claim syntax after V23's local wire validation."""

    value = _validated_v23_value(response=response)
    v20_value = copy.deepcopy(value)
    for decision in v20_value["table_decisions"]:
        if isinstance(decision, dict):
            decision.pop(_HEADERLESS_DISPOSITION_FIELD, None)
    _replace_wire_version(
        v20_value,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V23_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
    )
    try:
        return _claims_v20(response=v20_value)
    except OrdinaryTradeGroupedMappingV20Error as exc:
        raise OrdinaryTradeGroupedMappingV23Error(
            exc.code.replace("_v20_", "_v23_"),
            safe_shape_category=getattr(exc, "safe_shape_category", None),
        ) from exc


def headerless_dispositions(*, response: Any) -> dict[str, Any]:
    """Return the closed V23 declaration without interpreting Canonical."""

    value = _validated_v23_value(response=response)
    return {
        "schema_version": HEADERLESS_DISPOSITION_RESPONSE_SCHEMA_VERSION,
        "dispositions": [
            {
                "table_ref": decision["table_ref"],
                _HEADERLESS_DISPOSITION_FIELD: decision[_HEADERLESS_DISPOSITION_FIELD],
            }
            for decision in value["table_decisions"]
            if isinstance(decision, Mapping)
            and decision.get("disposition") == "HEADER_ABSENT"
        ],
    }


def _validated_v23_value(*, response: Any) -> dict[str, Any]:
    value = getattr(response, "content", response)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise OrdinaryTradeGroupedMappingV23Error(
                "ordinary_trade_grouped_mapping_v23_response_invalid"
            ) from exc
    if (
        not isinstance(value, Mapping)
        or value.get("schema_version")
        != ORDINARY_TRADE_GROUPED_MAPPING_V23_RESPONSE_SCHEMA_VERSION
        or not isinstance(value.get("table_decisions"), list)
    ):
        _fail("ordinary_trade_grouped_mapping_v23_response_invalid")
    for decision in value["table_decisions"]:
        if not isinstance(decision, Mapping):
            _fail("ordinary_trade_grouped_mapping_v23_response_invalid")
        disposition = decision.get("disposition")
        headerless_disposition = decision.get(_HEADERLESS_DISPOSITION_FIELD)
        if disposition == "HEADER_ABSENT":
            if (
                not isinstance(decision.get("table_ref"), str)
                or not decision["table_ref"]
                or headerless_disposition not in _HEADERLESS_DISPOSITIONS
            ):
                _fail("ordinary_trade_grouped_mapping_v23_response_invalid")
        elif _HEADERLESS_DISPOSITION_FIELD in decision:
            _fail("ordinary_trade_grouped_mapping_v23_response_invalid")
    return copy.deepcopy(dict(value))


def _add_headerless_disposition(value: Any) -> int:
    if isinstance(value, list):
        return sum(_add_headerless_disposition(item) for item in value)
    if not isinstance(value, dict):
        return 0
    properties = value.get("properties")
    required = value.get("required")
    if (
        isinstance(properties, dict)
        and isinstance(required, list)
        and properties.get("disposition") == {"const": "HEADER_ABSENT"}
    ):
        if _HEADERLESS_DISPOSITION_FIELD in properties:
            return 0
        properties[_HEADERLESS_DISPOSITION_FIELD] = {
            "enum": sorted(_HEADERLESS_DISPOSITIONS)
        }
        required.append(_HEADERLESS_DISPOSITION_FIELD)
        return 1
    return sum(_add_headerless_disposition(item) for item in value.values())


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
    raise OrdinaryTradeGroupedMappingV23Error(code)


__all__ = [
    "HEADERLESS_DISPOSITION_RESPONSE_SCHEMA_VERSION",
    "ORDINARY_TRADE_GROUPED_MAPPING_V23_RESPONSE_SCHEMA_VERSION",
    "OrdinaryTradeGroupedMappingV23Adapter",
    "OrdinaryTradeGroupedMappingV23AdapterFactory",
    "OrdinaryTradeGroupedMappingV23Error",
    "expand_grouped_response",
    "explicit_header_source_claims",
    "grouped_mapping_response_format",
    "headerless_dispositions",
]
