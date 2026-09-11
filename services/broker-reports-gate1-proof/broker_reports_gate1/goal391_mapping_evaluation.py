"""Representation-only identities for the private Goal #391 mapping evaluator.

This is deliberately outside Canonical, semantic mapping and Runtime.  It
normalizes only the presentation of an already supplied trade row identity so
the evaluator can compare a wrapped date/time with the same date/time written
on one line.  It never changes a source literal, a model response, a role or a
financial value.
"""

from __future__ import annotations

import re
from typing import Any


GOAL391_MAPPING_EVALUATOR_VERSION = "goal391_role_mapping_evaluator_v3"
_WHITESPACE = re.compile(r"\s+")


def normalize_trade_timestamp_for_identity(value: Any) -> str | None:
    """Return the narrow comparison form of one displayed date/time.

    A comma and Unicode whitespace can both be visual separators between a
    date and a time in the same source cell.  No other character, number, date
    component or timezone semantics is normalized here.
    """

    if not isinstance(value, str):
        return None
    normalized = _WHITESPACE.sub(" ", value.replace(",", " ")).strip()
    return normalized or None


def normalized_trade_row_identity(
    *, instrument_id: Any, timestamp: Any
) -> str | None:
    """Build the evaluator-only identity without mutating either input."""

    if not isinstance(instrument_id, str) or not instrument_id.strip():
        return None
    normalized_timestamp = normalize_trade_timestamp_for_identity(timestamp)
    if normalized_timestamp is None:
        return None
    return f"{instrument_id.strip().upper()}|{normalized_timestamp}"
