"""Value-free control contract for the temporary Goal #391 mapping lab.

This module owns the sealed laboratory-plan shape and evaluator-only row
identities.  It does not read a source, infer financial meaning, call a
provider, or persist anything.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


SERVER_BOUND_CASE_PLAN_SCHEMA_VERSION = "goal391_server_bound_case_plan_v2"
_EXPECTED_ASSESSMENT_FIELDS = frozenset(
    {
        "expected_status",
        "required_table_decisions",
        "unresolved_table_node_ids",
        "forbidden_qualified_mapping_table_node_ids",
    }
)
_DECISION_FIELDS = frozenset(
    {"table_node_id", "disposition", "no_consumer_kind"}
)
_NO_NAMED_CONSUMER_KINDS = frozenset(
    {"INSTRUCTIONAL_REFERENCE", "OTHER_NO_NAMED_CONSUMER"}
)
GOAL391_MAPPING_EVALUATOR_VERSION = "goal391_role_mapping_evaluator_v3"
_WHITESPACE = re.compile(r"\s+")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def valid_expected_assessment(
    value: Any,
    *,
    target_table_node_ids: list[str] | tuple[str, ...] | None = None,
) -> bool:
    """Validate a human R&D assertion without interpreting its content."""

    if not isinstance(value, Mapping) or set(value) != _EXPECTED_ASSESSMENT_FIELDS:
        return False
    if not isinstance(value["expected_status"], str) or not value["expected_status"]:
        return False
    decisions = value["required_table_decisions"]
    unresolved = value["unresolved_table_node_ids"]
    forbidden = value["forbidden_qualified_mapping_table_node_ids"]
    if not all(isinstance(items, list) for items in (decisions, unresolved, forbidden)):
        return False
    if any(not isinstance(node_id, str) or not node_id for node_id in unresolved + forbidden):
        return False
    if len(set(unresolved)) != len(unresolved) or len(set(forbidden)) != len(forbidden):
        return False

    decision_ids: list[str] = []
    no_named_consumer_ids: list[str] = []
    for decision in decisions:
        if not isinstance(decision, Mapping) or set(decision) - _DECISION_FIELDS:
            return False
        table_node_id = decision.get("table_node_id")
        disposition = decision.get("disposition")
        if not isinstance(table_node_id, str) or not table_node_id:
            return False
        if not isinstance(disposition, str) or not disposition:
            return False
        no_consumer_kind = decision.get("no_consumer_kind")
        if disposition == "NO_NAMED_CONSUMER":
            if no_consumer_kind not in _NO_NAMED_CONSUMER_KINDS:
                return False
            no_named_consumer_ids.append(table_node_id)
        elif no_consumer_kind is not None:
            return False
        decision_ids.append(table_node_id)
    if len(set(decision_ids)) != len(decision_ids):
        return False
    if not set(no_named_consumer_ids).issubset(forbidden):
        return False

    if target_table_node_ids is not None:
        if (
            not target_table_node_ids
            or any(not isinstance(node_id, str) or not node_id for node_id in target_table_node_ids)
            or len(set(target_table_node_ids)) != len(target_table_node_ids)
        ):
            return False
        target_ids = set(target_table_node_ids)
        if not set(decision_ids + unresolved + forbidden).issubset(target_ids):
            return False
        if set(decision_ids).intersection(unresolved):
            return False
        if set(decision_ids).union(unresolved) != target_ids:
            return False
    return True


def canonical_table_node_ids(canonical: Any) -> tuple[str, ...]:
    """Return the immutable Canonical TABLE scope in physical order."""

    nodes = canonical.get("nodes") if isinstance(canonical, Mapping) else None
    table_node_ids = tuple(
        str(node.get("node_id") or "")
        for node in nodes or []
        if isinstance(node, Mapping)
        and node.get("node_type") == "TABLE"
        and str(node.get("node_id") or "")
    )
    if not table_node_ids or len(set(table_node_ids)) != len(table_node_ids):
        raise ValueError("goal391_mapping_lab_tables_invalid")
    return table_node_ids


def normalize_trade_timestamp_for_identity(value: Any) -> str | None:
    """Normalize only visual date/time separators for evaluator row identity.

    This representation-only helper never changes Canonical, a model response,
    a role or a financial value.  It accepts a wrapped date/time as the same
    identity as its one-line display, and nothing more.
    """

    if not isinstance(value, str):
        return None
    normalized = _WHITESPACE.sub(" ", value.replace(",", " ")).strip()
    return normalized or None


def normalized_trade_row_identity(
    *, instrument_id: Any, timestamp: Any
) -> str | None:
    """Build an evaluator-only row identity without mutating either input."""

    if not isinstance(instrument_id, str) or not instrument_id.strip():
        return None
    normalized_timestamp = normalize_trade_timestamp_for_identity(timestamp)
    if normalized_timestamp is None:
        return None
    return f"{instrument_id.strip().upper()}|{normalized_timestamp}"
