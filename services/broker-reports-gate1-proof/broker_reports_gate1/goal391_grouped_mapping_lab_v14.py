"""Lab compatibility facade for the shared ordinary-trade v14 adapter.

The v14 representation is now owned by
``ordinary_trade_grouped_mapping_v14``. This module retains only the isolated
qualification Pipe's prompt identities and its historical value-free terminal
codes; it owns no representation logic.
"""

from __future__ import annotations

from typing import Any, Mapping

from .ordinary_trade_grouped_mapping_v14 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV14Error,
    expand_grouped_response as _expand_grouped_response,
    grouped_mapping_response_format as _grouped_mapping_response_format,
)
from .ordinary_trade_mapping_prompt import (
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_COMMAND as _PROMPT_COMMAND,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_REQUIRED_TAG as _PROMPT_REQUIRED_TAG,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_ID as _PROMPT_TEMPLATE_ID,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_KIND as _PROMPT_TEMPLATE_KIND,
    GOAL391_GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION as _PROMPT_RESPONSE_SCHEMA_VERSION,
)


GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION = (
    ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION
)
if GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION != _PROMPT_RESPONSE_SCHEMA_VERSION:
    raise RuntimeError("goal391_grouped_mapping_lab_prompt_contract_invalid")

# Re-export the shared native Prompt identities for the isolated lab composer.
GROUPED_MAPPING_LAB_PROMPT_COMMAND = _PROMPT_COMMAND
GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_ID = _PROMPT_TEMPLATE_ID
GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_KIND = _PROMPT_TEMPLATE_KIND
GROUPED_MAPPING_LAB_PROMPT_REQUIRED_TAG = _PROMPT_REQUIRED_TAG


class Goal391GroupedMappingLabError(RuntimeError):
    """A value-free rejection at the isolated v14 response boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def grouped_mapping_response_format(
    *, v13_response_format: Mapping[str, Any]
) -> dict[str, Any]:
    """Use the shared representation owner with stable lab terminals."""

    try:
        return _grouped_mapping_response_format(
            v13_response_format=v13_response_format
        )
    except OrdinaryTradeGroupedMappingV14Error as exc:
        _raise_lab_error(exc)


def expand_grouped_response(
    *, response: Any, package: Mapping[str, Any]
) -> dict[str, Any]:
    """Use the shared representation owner with stable lab terminals."""

    try:
        return _expand_grouped_response(response=response, package=package)
    except OrdinaryTradeGroupedMappingV14Error as exc:
        _raise_lab_error(exc)


def _raise_lab_error(error: OrdinaryTradeGroupedMappingV14Error) -> None:
    suffix = error.code.removeprefix("ordinary_trade_grouped_mapping_v14_")
    raise Goal391GroupedMappingLabError(
        f"goal391_grouped_mapping_lab_{suffix}"
    ) from error


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
