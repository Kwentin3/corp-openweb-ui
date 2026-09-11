"""Wire-only contract for a selected cross-table header continuation.

This module deliberately owns neither Canonical interpretation nor financial
roles.  It keeps the new model output isolated until the semantic mapping
owner binds it to the current Canonical and the source-owned sidecar.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping


EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_explicit_header_source_response_v1"
)


class ExplicitHeaderSourceResponseError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def response_schema() -> dict[str, Any]:
    """Return the strict model schema for value-free continuation claims."""

    claim = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "target_table_ref",
            "header_source_table_ref",
            "security_trade_rows",
        ],
        "properties": {
            "target_table_ref": {"type": "string", "minLength": 1},
            "header_source_table_ref": {"type": "string", "minLength": 1},
            "security_trade_rows": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "integer", "minimum": 1},
            },
        },
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ordinary_trade_explicit_header_source_v1",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["schema_version", "claims"],
                "properties": {
                    "schema_version": {
                        "const": EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION
                    },
                    "claims": {"type": "array", "items": claim},
                },
            },
        },
    }


def validate_response(value: Any) -> list[dict[str, Any]]:
    """Validate syntax only; source binding belongs to semantic mapping."""

    value = getattr(value, "content", value)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ExplicitHeaderSourceResponseError(
                "ordinary_trade_explicit_header_source_response_invalid"
            ) from exc
    if (
        not isinstance(value, Mapping)
        or set(value) != {"schema_version", "claims"}
        or value.get("schema_version")
        != EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION
        or not isinstance(value.get("claims"), list)
    ):
        raise ExplicitHeaderSourceResponseError(
            "ordinary_trade_explicit_header_source_response_invalid"
        )
    claims: list[dict[str, Any]] = []
    for claim in value["claims"]:
        if (
            not isinstance(claim, Mapping)
            or set(claim)
            != {
                "target_table_ref",
                "header_source_table_ref",
                "security_trade_rows",
            }
            or any(
                not isinstance(claim.get(key), str) or not claim[key]
                for key in ("target_table_ref", "header_source_table_ref")
            )
            or claim["target_table_ref"] == claim["header_source_table_ref"]
            or not isinstance(claim.get("security_trade_rows"), list)
            or not claim["security_trade_rows"]
            or claim["security_trade_rows"]
            != sorted(set(claim["security_trade_rows"]))
            or any(
                type(row) is not int or row < 1
                for row in claim["security_trade_rows"]
            )
        ):
            raise ExplicitHeaderSourceResponseError(
                "ordinary_trade_explicit_header_source_response_invalid"
            )
        claims.append(copy.deepcopy(dict(claim)))
    if len(claims) != len({item["target_table_ref"] for item in claims}):
        raise ExplicitHeaderSourceResponseError(
            "ordinary_trade_explicit_header_source_response_duplicate_target"
        )
    return claims


__all__ = [
    "EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION",
    "ExplicitHeaderSourceResponseError",
    "response_schema",
    "validate_response",
]
