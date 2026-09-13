"""V17 strict wire envelope for grouped mapping plus header-source claims.

V17 is representation-only.  Its grouped mapping payload is delegated to the
retained V15-to-V14 adapter, while explicit header-source claim syntax remains
owned by the existing wire validator.  No Canonical or financial meaning is
interpreted here.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .ordinary_trade_explicit_header_source_response import (
    EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION,
    ExplicitHeaderSourceResponseError,
    response_schema as explicit_header_source_response_schema,
    validate_response as validate_explicit_header_source_response,
)
from .ordinary_trade_grouped_mapping_v15 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV15Error,
    expand_grouped_response as _expand_v15,
    grouped_mapping_response_format as _format_v15,
)


ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_grouped_mapping_response_v17"
)
_EXPLICIT_HEADER_SOURCE_CLAIMS_FIELD = "explicit_header_source_claims"


class OrdinaryTradeGroupedMappingV17Error(RuntimeError):
    """A value-free rejection at the V17 representation boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeGroupedMappingV17AdapterFactory:
    """Create the one V17 representation adapter."""

    @staticmethod
    def create() -> "OrdinaryTradeGroupedMappingV17Adapter":
        return OrdinaryTradeGroupedMappingV17Adapter()


class OrdinaryTradeGroupedMappingV17Adapter:
    """Expose V17 and keep its two representation outputs separable."""

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
    """Derive a distinct strict V17 root around the retained V15 schema."""

    result = _format_v15(v13_response_format=v13_response_format)
    json_schema = result.get("json_schema")
    root_schema = json_schema.get("schema") if isinstance(json_schema, dict) else None
    if not isinstance(root_schema, dict):
        _fail("ordinary_trade_grouped_mapping_v17_response_format_invalid")
    _replace_wire_version(
        result,
        source=ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION,
        target=ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION,
    )
    json_schema["name"] = "broker_reports_ordinary_trade_grouped_mapping_response_v17"
    required = root_schema.get("required")
    properties = root_schema.get("properties")
    if (
        not isinstance(required, list)
        or _EXPLICIT_HEADER_SOURCE_CLAIMS_FIELD in required
        or not isinstance(properties, dict)
        or _EXPLICIT_HEADER_SOURCE_CLAIMS_FIELD in properties
    ):
        _fail("ordinary_trade_grouped_mapping_v17_response_format_invalid")
    explicit_schema = explicit_header_source_response_schema()
    explicit_json_schema = explicit_schema.get("json_schema")
    explicit_root_schema = (
        explicit_json_schema.get("schema")
        if isinstance(explicit_json_schema, dict)
        else None
    )
    if not isinstance(explicit_root_schema, dict):
        _fail("ordinary_trade_grouped_mapping_v17_response_format_invalid")
    required.append(_EXPLICIT_HEADER_SOURCE_CLAIMS_FIELD)
    properties[_EXPLICIT_HEADER_SOURCE_CLAIMS_FIELD] = copy.deepcopy(explicit_root_schema)
    return result


def expand_grouped_response(
    *,
    response: Any,
    package: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the V17 envelope, then delegate grouped expansion to V15."""

    return _expand_grouped_response(
        response=response,
        package=package,
        allow_source_bound_position_effect=False,
    )


def _expand_grouped_response(
    *,
    response: Any,
    package: Mapping[str, Any],
    allow_source_bound_position_effect: bool,
) -> dict[str, Any]:
    """Private V18 bridge; public V17 expansion always rejects later fields."""

    grouped_response, _claims = _split_response(
        response=response,
        allow_source_bound_position_effect=allow_source_bound_position_effect,
    )
    try:
        return _expand_v15(response=grouped_response, package=package)
    except OrdinaryTradeGroupedMappingV15Error as exc:
        raise OrdinaryTradeGroupedMappingV17Error(
            exc.code.replace("_v15_", "_v17_")
        ) from exc


def explicit_header_source_claims(*, response: Any) -> dict[str, Any]:
    """Return the validator-owned, normalized header-source claim envelope."""

    _grouped_response, claims = _split_response(response=response)
    return claims


def _split_response(
    *, response: Any, allow_source_bound_position_effect: bool = False
) -> tuple[dict[str, Any], dict[str, Any]]:
    value = _response_value(response)
    required = {
        "schema_version",
        "status",
        "table_decisions",
        "clarification",
        "message",
        _EXPLICIT_HEADER_SOURCE_CLAIMS_FIELD,
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("schema_version")
        != ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION
    ):
        _fail("ordinary_trade_grouped_mapping_v17_response_invalid")
    # V17 is immutable.  Its compact envelope must never become a back door
    # for a later semantic feature merely because an older nested schema was
    # permissive while expanding the response.
    if (
        not allow_source_bound_position_effect
        and _contains_position_effect(value["table_decisions"])
    ):
        _fail("ordinary_trade_grouped_mapping_v17_response_invalid")
    claim_response = value[_EXPLICIT_HEADER_SOURCE_CLAIMS_FIELD]
    try:
        claims = validate_explicit_header_source_response(claim_response)
    except ExplicitHeaderSourceResponseError as exc:
        raise OrdinaryTradeGroupedMappingV17Error(exc.code) from exc
    grouped_response = copy.deepcopy(value)
    del grouped_response[_EXPLICIT_HEADER_SOURCE_CLAIMS_FIELD]
    grouped_response["schema_version"] = (
        ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION
    )
    return grouped_response, {
        "schema_version": EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION,
        "claims": claims,
    }


def _contains_position_effect(value: Any) -> bool:
    if isinstance(value, dict):
        return "position_effect" in value or any(
            _contains_position_effect(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_position_effect(item) for item in value)
    return False


def _response_value(response: Any) -> Any:
    value = getattr(response, "content", response)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise OrdinaryTradeGroupedMappingV17Error(
                "ordinary_trade_grouped_mapping_v17_response_invalid"
            ) from exc
    return copy.deepcopy(value)


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
    raise OrdinaryTradeGroupedMappingV17Error(code)


__all__ = [
    "ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION",
    "OrdinaryTradeGroupedMappingV17Adapter",
    "OrdinaryTradeGroupedMappingV17AdapterFactory",
    "OrdinaryTradeGroupedMappingV17Error",
    "expand_grouped_response",
    "explicit_header_source_claims",
    "grouped_mapping_response_format",
]
