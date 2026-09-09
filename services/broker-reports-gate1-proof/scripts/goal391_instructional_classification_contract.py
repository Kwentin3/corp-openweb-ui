"""Strict R&D contract for one Canonical table's instructional meaning.

This module is deliberately not a production owner or a Canonical writer.  It
only makes the managed-Prompt experiment auditable before any integration is
considered.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping


PROMPT_CONTRACT_ID = "broker_reports_instructional_table_classification_prompt_v1"
INPUT_SCHEMA_VERSION = "broker_reports_instructional_table_classification_case_v1"
OUTPUT_SCHEMA_VERSION = "broker_reports_instructional_table_classification_response_v1"
PROMPT_PLACEHOLDER = "{{instructional_table_classification_case_json}}"
_STATUSES = frozenset({"INSTRUCTIONAL_REFERENCE", "NOT_INSTRUCTIONAL", "SPECIALIST_REVIEW_REQUIRED"})


class InstructionalClassificationContractError(ValueError):
    pass


def prompt_hash(content: str) -> str:
    material = content.replace("\r\n", "\n").strip() + "\nprompt_contract:" + PROMPT_CONTRACT_ID + "\ninput_schema:" + INPUT_SCHEMA_VERSION + "\noutput_schema:" + OUTPUT_SCHEMA_VERSION
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def response_format() -> dict[str, Any]:
    evidence = {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["context_ref", "relation"],
            "properties": {
                "context_ref": {"type": "string", "minLength": 1},
                "relation": {"type": "string", "minLength": 1},
            },
        },
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": OUTPUT_SCHEMA_VERSION,
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["schema_version", "classification", "classification_evidence"],
                "properties": {
                    "schema_version": {"const": OUTPUT_SCHEMA_VERSION},
                    "classification": {"enum": sorted(_STATUSES)},
                    "classification_evidence": evidence,
                },
            },
        },
    }


def build_case(*, table: Mapping[str, Any]) -> dict[str, Any]:
    required = {"table_ref", "header_row_choices", "rows", "rows_total", "rows_truncated", "source_context"}
    if set(table) != required or not isinstance(table.get("table_ref"), str) or not table["table_ref"] or not isinstance(table.get("source_context"), list):
        raise InstructionalClassificationContractError("instructional_classification_table_invalid")
    return {"schema_version": INPUT_SCHEMA_VERSION, "table": copy.deepcopy(dict(table))}


def validate_response(*, response: Any, case: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict) or set(response) != {"schema_version", "classification", "classification_evidence"} or response.get("schema_version") != OUTPUT_SCHEMA_VERSION or response.get("classification") not in _STATUSES or not isinstance(response.get("classification_evidence"), list):
        raise InstructionalClassificationContractError("instructional_classification_response_invalid")
    table = case.get("table") if isinstance(case, Mapping) else None
    contexts = table.get("source_context") if isinstance(table, Mapping) else None
    allowed = {(item.get("context_ref"), item.get("relation")) for item in contexts or [] if isinstance(item, dict)}
    evidence = response["classification_evidence"]
    pairs = []
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"context_ref", "relation"} or (item.get("context_ref"), item.get("relation")) not in allowed:
            raise InstructionalClassificationContractError("instructional_classification_evidence_invalid")
        pairs.append((item["context_ref"], item["relation"]))
    if len(set(pairs)) != len(pairs) or ((response["classification"] == "INSTRUCTIONAL_REFERENCE") != bool(pairs)):
        raise InstructionalClassificationContractError("instructional_classification_evidence_coverage_invalid")
    return copy.deepcopy(response)
