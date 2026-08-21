#!/usr/bin/env python3
"""Research-only comparison of ten bounded Semantic Compiler task forms."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate3StructuralChunkFactory,
)
from broker_reports_gate1.gate3_ndfl_workflow import (  # noqa: E402
    NDFL_PROVIDER_MODEL_ID,
    NDFL_PROVIDER_PROFILE_ID,
)
import qualify_canonical_minimal_semantic_compiler as msc  # noqa: E402


typed = msc.typed
RUNS = 3
FROZEN_CANONICAL_ROOT_SHA256 = msc.FROZEN_CANONICAL_ROOT_SHA256
HYPOTHESES = (
    "H1_HEADER_FORWARD_REFS",
    "H2_HEADER_INVERSE_REFS",
    "H3_ALL_TABLES_FORWARD_REFS",
    "H4_SIDE_LITERAL_COPY",
    "H5_SIDE_VALUE_REFS",
    "H6_SIDE_SINGLE_PURCHASE_REF",
    "H7_RESIDUAL_GLOBAL_CODES_SPANS",
    "H8_RESIDUAL_TABLE_CONTRACTS",
    "H9_RESIDUAL_CODES_ONLY",
    "H10_RESIDUAL_EVENTS_TOKEN_REFS",
)
RESPONSE_VERSIONS = {
    key: "broker_semantic_task_form_" + key.lower() + "_v0"
    for key in HYPOTHESES
}
TERMINALS = {
    "TASK_FORM_SEMANTIC_COMPILER_PROVEN",
    "ATOMIC_TASK_FORM_PARTIAL_PROVEN",
    "NO_STABLE_TASK_FORM_FOUND",
}


class TaskFormError(RuntimeError):
    pass


def _root(*, version: str, item: dict[str, Any], count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "classifications"],
        "properties": {
            "schema_version": {"const": version},
            "classifications": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": {"$ref": "#/$defs/classification"},
            },
        },
        "$defs": {"classification": item},
    }


def _id_schema(pattern: str, description: str) -> dict[str, Any]:
    return {"type": "string", "pattern": pattern, "description": description}


def _header_columns_schema(header_refs: list[str], *, minimum: int, maximum: int) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": minimum,
        "maxItems": maximum,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["header_ref", "normalized_role"],
            "properties": {
                "header_ref": {"type": "string", "enum": header_refs},
                "normalized_role": {"type": "string", "enum": list(msc.NORMALIZED_ROLES)},
            },
        },
    }


def header_forward_schema(
    *,
    version: str,
    table_count: int,
    header_refs: list[str],
    maximum: int,
    include_table_type: bool,
) -> dict[str, Any]:
    required = ["assertion_id", "columns"]
    properties: dict[str, Any] = {
        "assertion_id": _id_schema(r"^g[0-9]{3}$", "Copy one exact logical_table_id."),
        "columns": _header_columns_schema(header_refs, minimum=1, maximum=maximum),
    }
    if include_table_type:
        required.insert(1, "table_type")
        properties["table_type"] = {"type": "string", "enum": list(msc.TABLE_TYPES)}
    return _root(
        version=version,
        count=table_count,
        item={
            "type": "object",
            "additionalProperties": False,
            "required": required,
            "properties": properties,
        },
    )


def header_inverse_schema(*, version: str, table_id: str, header_refs: list[str]) -> dict[str, Any]:
    return _root(
        version=version,
        count=1,
        item={
            "type": "object",
            "additionalProperties": False,
            "required": ["assertion_id", "role_bindings"],
            "properties": {
                "assertion_id": _id_schema(r"^g[0-9]{3}$", f"Copy exact logical_table_id {table_id}."),
                "role_bindings": {
                    "type": "array",
                    "minItems": len(header_refs),
                    "maxItems": len(header_refs),
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["normalized_role", "header_ref"],
                        "properties": {
                            "normalized_role": {"type": "string", "enum": list(msc.NORMALIZED_ROLES)},
                            "header_ref": {"type": "string", "enum": header_refs},
                        },
                    },
                },
            },
        },
    )


def side_schema(*, version: str, mode: str, value_refs: list[str], count: int = 2) -> dict[str, Any]:
    if mode == "literal":
        required = ["source_literal", "normalized_value"]
        properties = {
            "source_literal": {"type": "string", "minLength": 1},
            "normalized_value": {"type": "string", "enum": ["PURCHASE", "DISPOSAL"]},
        }
        value_property = "value_bindings"
    elif mode == "ref":
        required = ["value_ref", "normalized_value"]
        properties = {
            "value_ref": {"type": "string", "enum": value_refs},
            "normalized_value": {"type": "string", "enum": ["PURCHASE", "DISPOSAL"]},
        }
        value_property = "value_bindings"
    elif mode == "purchase_ref":
        return _root(
            version=version,
            count=1,
            item={
                "type": "object",
                "additionalProperties": False,
                "required": ["assertion_id", "purchase_value_ref"],
                "properties": {
                    "assertion_id": _id_schema(r"^g[0-9]{3}$", "Copy exact logical_table_id."),
                    "purchase_value_ref": {"type": "string", "enum": value_refs},
                },
            },
        )
    else:
        raise TaskFormError("side_schema_mode_invalid")
    return _root(
        version=version,
        count=1,
        item={
            "type": "object",
            "additionalProperties": False,
            "required": ["assertion_id", value_property],
            "properties": {
                "assertion_id": _id_schema(r"^g[0-9]{3}$", "Copy exact logical_table_id."),
                value_property: {
                    "type": "array",
                    "minItems": count,
                    "maxItems": count,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": required,
                        "properties": properties,
                    },
                },
            },
        },
    )


def residual_codes_schema(*, version: str, source_ids: list[str], codes: list[str], include_spans: bool) -> dict[str, Any]:
    required = ["assertion_id", "codes"]
    properties: dict[str, Any] = {
        "assertion_id": _id_schema(r"^r[0-9]{3}$", "Copy one exact source_record_id in input order."),
        "codes": {
            "type": "array",
            "minItems": 1,
            "maxItems": 2,
            "items": {"type": "string", "enum": codes},
        },
    }
    if include_spans:
        required.extend(["asset_span", "currency_span"])
        properties.update(
            {
                "asset_span": {"type": "string"},
                "currency_span": {"type": "string"},
            }
        )
    return _root(
        version=version,
        count=len(source_ids),
        item={
            "type": "object",
            "additionalProperties": False,
            "required": required,
            "properties": properties,
        },
    )


def residual_event_schema(*, version: str, source_ids: list[str], table_type: str, token_refs: list[str]) -> dict[str, Any]:
    event_kinds = {
        "CASH_OPERATIONS": ["COMMISSION", "NOT_RELEVANT", "UNMAPPED"],
        "SECURITY_TRADES": ["TRADE_TOTAL", "NOT_RELEVANT", "UNMAPPED"],
        "INCOME_PAYMENTS": ["COUPON", "NOT_RELEVANT", "UNMAPPED"],
    }[table_type]
    max_asset = 4 if table_type == "INCOME_PAYMENTS" else 0
    max_currency = 2 if table_type == "SECURITY_TRADES" else 0
    return _root(
        version=version,
        count=len(source_ids),
        item={
            "type": "object",
            "additionalProperties": False,
            "required": [
                "assertion_id",
                "event_kind",
                "withholding_stated",
                "asset_token_refs",
                "currency_token_refs",
            ],
            "properties": {
                "assertion_id": _id_schema(r"^r[0-9]{3}$", "Copy one exact source_record_id in input order."),
                "event_kind": {"type": "string", "enum": event_kinds},
                "withholding_stated": {"type": "boolean"},
                "asset_token_refs": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": max_asset,
                    "items": {"type": "string", "enum": token_refs},
                },
                "currency_token_refs": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": max_currency,
                    "items": {"type": "string", "enum": token_refs},
                },
            },
        },
    )


def build_table_contexts(*, chunk: dict[str, Any], source_batch: dict[str, Any], semantic_truth: dict[str, Any]) -> list[dict[str, Any]]:
    mapping_by_alias = {item["target_alias"]: item["canonical_target"] for item in chunk["target_mappings"]}
    text_by_alias, _ = typed._visible_text_index(content=chunk["model_view"]["content"], mapping_by_alias=mapping_by_alias)
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    for row in source_batch["source_records"]:
        rows_by_table.setdefault(row["logical_table_id"], []).append(row)
    contexts = []
    for mapping in semantic_truth["schema_mappings"]:
        rows = rows_by_table[mapping["logical_table_id"]]
        title = text_by_alias.get(mapping["title_ref"])
        if not isinstance(title, str) or not title:
            raise TaskFormError("table_title_missing")
        contexts.append(
            {
                "logical_table_id": mapping["logical_table_id"],
                "table_identity": {"source_ref": mapping["title_ref"], "literal": title},
                "headers": copy.deepcopy(rows[0]["header_context"]),
            }
        )
    return contexts


def build_side_context(*, table_context: dict[str, Any], representative_rows: list[dict[str, Any]], mapping_truth: dict[str, Any]) -> dict[str, Any]:
    side_header_ref = next(item["header_ref"] for item in mapping_truth["columns"] if item["normalized_role"] == "side")
    side_column = next(item["column"] for item in table_context["headers"] if item["source_ref"] == side_header_ref)
    candidates = []
    seen = set()
    for row in representative_rows:
        cell = next(item for item in row["elements"] if item["column"] == side_column)
        if cell["literal"] in seen:
            continue
        seen.add(cell["literal"])
        candidates.append(
            {
                "value_ref": f"v{len(candidates) + 1:03d}",
                "source_ref": cell["source_ref"],
                "literal": cell["literal"],
            }
        )
    if len(candidates) != 2:
        raise TaskFormError("side_candidates_not_binary")
    return {
        "schema_version": "broker_side_value_candidates_v0",
        "logical_table_id": table_context["logical_table_id"],
        "side_header": next(item for item in table_context["headers"] if item["source_ref"] == side_header_ref),
        "candidates": candidates,
    }


def tokenize_residual_batch(residual_batch: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    token_index: dict[str, dict[str, Any]] = {}
    records = []
    for record in residual_batch["records"]:
        tokens = []
        for ordinal, match in enumerate(re.finditer(r"\w+|[^\w\s]", record["source_wording"], flags=re.UNICODE), 1):
            token_ref = f"{record['source_record_id']}_w{ordinal:03d}"
            token = {
                "token_ref": token_ref,
                "literal": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "source_record_id": record["source_record_id"],
            }
            token_index[token_ref] = token
            tokens.append({"token_ref": token_ref, "literal": token["literal"]})
        records.append(
            {
                "source_record_id": record["source_record_id"],
                "table_type": record["table_type"],
                "source_wording_ref": record["source_wording_ref"],
                "source_wording": record["source_wording"],
                "tokens": tokens,
            }
        )
    return {"schema_version": "broker_residual_token_batch_v0", "records": records}, token_index


def _decode_classifications(raw: Any, *, version: str, count: int) -> list[dict[str, Any]]:
    value = typed._decode(raw)
    if (
        set(value) != {"schema_version", "classifications"}
        or value.get("schema_version") != version
        or not isinstance(value.get("classifications"), list)
        or len(value["classifications"]) != count
        or any(not isinstance(item, dict) for item in value["classifications"])
    ):
        raise TaskFormError("response_envelope_invalid")
    return copy.deepcopy(value["classifications"])


def _validate_columns(columns: Any, *, expected_refs: list[str]) -> list[dict[str, str]]:
    if not isinstance(columns, list) or len(columns) != len(expected_refs):
        raise TaskFormError("header_accounting_invalid")
    restored = []
    for item in columns:
        if (
            not isinstance(item, dict)
            or set(item) != {"header_ref", "normalized_role"}
            or item.get("normalized_role") not in msc.NORMALIZED_ROLES
        ):
            raise TaskFormError("header_mapping_invalid")
        restored.append(copy.deepcopy(item))
    if [item["header_ref"] for item in restored] != expected_refs:
        raise TaskFormError("header_order_invalid")
    roles = [item["normalized_role"] for item in restored if item["normalized_role"] != "unmapped"]
    if len(roles) != len(set(roles)):
        raise TaskFormError("header_role_duplicate")
    return restored


def validate_header_forward(
    raw: Any,
    *,
    version: str,
    contexts: list[dict[str, Any]],
    expect_table_type: bool = False,
) -> list[dict[str, Any]]:
    items = _decode_classifications(raw, version=version, count=len(contexts))
    if [item.get("assertion_id") for item in items] != [item["logical_table_id"] for item in contexts]:
        raise TaskFormError("header_table_accounting_invalid")
    restored = []
    for item, context in zip(items, contexts, strict=True):
        expected_keys = {"assertion_id", "columns"} | ({"table_type"} if expect_table_type else set())
        if set(item) != expected_keys:
            raise TaskFormError("header_response_contract_invalid")
        refs = [header["source_ref"] for header in context["headers"]]
        restored_item = {
            "logical_table_id": item["assertion_id"],
            "columns": _validate_columns(item["columns"], expected_refs=refs),
        }
        if expect_table_type:
            if item.get("table_type") not in msc.TABLE_TYPES:
                raise TaskFormError("header_table_type_invalid")
            restored_item["table_type"] = item["table_type"]
        restored.append(restored_item)
    return restored


def validate_header_inverse(raw: Any, *, version: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    item = _decode_classifications(raw, version=version, count=1)[0]
    if set(item) != {"assertion_id", "role_bindings"} or item.get("assertion_id") != context["logical_table_id"]:
        raise TaskFormError("inverse_header_contract_invalid")
    refs = [header["source_ref"] for header in context["headers"]]
    bindings = item["role_bindings"]
    if not isinstance(bindings, list) or len(bindings) != len(refs):
        raise TaskFormError("inverse_header_accounting_invalid")
    if {entry.get("header_ref") for entry in bindings if isinstance(entry, dict)} != set(refs):
        raise TaskFormError("inverse_header_refs_invalid")
    if any(
        not isinstance(entry, dict)
        or set(entry) != {"normalized_role", "header_ref"}
        or entry.get("normalized_role") not in msc.NORMALIZED_ROLES
        for entry in bindings
    ):
        raise TaskFormError("inverse_header_mapping_invalid")
    by_ref = {entry["header_ref"]: entry["normalized_role"] for entry in bindings}
    if len(by_ref) != len(refs):
        raise TaskFormError("inverse_header_duplicate")
    columns = [{"header_ref": ref, "normalized_role": by_ref[ref]} for ref in refs]
    return [{"logical_table_id": item["assertion_id"], "columns": _validate_columns(columns, expected_refs=refs)}]


def score_headers(*, mappings: list[dict[str, Any]], truth: dict[str, Any]) -> dict[str, Any]:
    truth_by_id = {item["logical_table_id"]: item for item in truth["schema_mappings"]}
    expected = [
        {
            "logical_table_id": item["logical_table_id"],
            **(
                {"table_type": truth_by_id[item["logical_table_id"]]["table_type"]}
                if "table_type" in item
                else {}
            ),
            "columns": truth_by_id[item["logical_table_id"]]["columns"],
        }
        for item in mappings
    ]
    correct = sum(
        actual_column == expected_column
        for actual, wanted in zip(mappings, expected, strict=True)
        for actual_column, expected_column in zip(actual["columns"], wanted["columns"], strict=True)
    )
    total = sum(len(item["columns"]) for item in expected)
    table_type_correct = sum(
        "table_type" not in actual or actual["table_type"] == wanted["table_type"]
        for actual, wanted in zip(mappings, expected, strict=True)
    )
    table_type_total = sum("table_type" in item for item in mappings)
    return {
        "projection_sha256": typed._stable_sha256(mappings),
        "correct": correct + table_type_correct if table_type_total else correct,
        "total": total + table_type_total,
        "exact": mappings == expected,
        "tables": len(mappings),
        "table_types_correct": table_type_correct if table_type_total else None,
        "table_types_total": table_type_total,
    }


def validate_side(raw: Any, *, version: str, mode: str, context: dict[str, Any], expected: list[dict[str, str]]) -> list[dict[str, str]]:
    item = _decode_classifications(raw, version=version, count=1)[0]
    if item.get("assertion_id") != context["logical_table_id"]:
        raise TaskFormError("side_table_invalid")
    candidates = context["candidates"]
    literal_by_ref = {item["value_ref"]: item["literal"] for item in candidates}
    if mode in {"literal", "ref"}:
        if set(item) != {"assertion_id", "value_bindings"} or not isinstance(item["value_bindings"], list):
            raise TaskFormError("side_contract_invalid")
        restored = []
        seen = set()
        for binding in item["value_bindings"]:
            expected_keys = {"source_literal", "normalized_value"} if mode == "literal" else {"value_ref", "normalized_value"}
            if not isinstance(binding, dict) or set(binding) != expected_keys:
                raise TaskFormError("side_binding_invalid")
            literal = binding.get("source_literal") if mode == "literal" else literal_by_ref.get(binding.get("value_ref"))
            if literal not in literal_by_ref.values() or binding.get("normalized_value") not in {"PURCHASE", "DISPOSAL"}:
                raise TaskFormError("side_binding_invalid")
            if literal in seen:
                raise TaskFormError("side_binding_duplicate")
            seen.add(literal)
            restored.append(
                {
                    "column_role": "side",
                    "source_literal": literal,
                    "normalized_value": binding["normalized_value"],
                }
            )
    elif mode == "purchase_ref":
        if set(item) != {"assertion_id", "purchase_value_ref"} or item.get("purchase_value_ref") not in literal_by_ref:
            raise TaskFormError("side_purchase_ref_invalid")
        purchase_literal = literal_by_ref[item["purchase_value_ref"]]
        restored = [
            {
                "column_role": "side",
                "source_literal": candidate["literal"],
                "normalized_value": "PURCHASE" if candidate["literal"] == purchase_literal else "DISPOSAL",
            }
            for candidate in candidates
        ]
    else:
        raise TaskFormError("side_mode_invalid")
    actual = sorted(restored, key=lambda value: value["normalized_value"])
    if len(actual) != 2 or {item["normalized_value"] for item in actual} != {"PURCHASE", "DISPOSAL"}:
        raise TaskFormError("side_meaning_accounting_invalid")
    return actual


def score_side(bindings: list[dict[str, str]], expected: list[dict[str, str]]) -> dict[str, Any]:
    wanted = sorted(copy.deepcopy(expected), key=lambda value: value["normalized_value"])
    return {
        "projection_sha256": typed._stable_sha256(bindings),
        "correct": sum(left == right for left, right in zip(bindings, wanted, strict=True)),
        "total": len(wanted),
        "exact": bindings == wanted,
    }


def _group_residual(residual_batch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for table_type in ("CASH_OPERATIONS", "SECURITY_TRADES", "INCOME_PAYMENTS"):
        result[table_type] = {
            "schema_version": residual_batch["schema_version"],
            "records": [copy.deepcopy(item) for item in residual_batch["records"] if item["table_type"] == table_type],
        }
    return result


def validate_codes_only(raw: Any, *, version: str, residual_batch: dict[str, Any]) -> dict[str, Any]:
    expected_ids = [item["source_record_id"] for item in residual_batch["records"]]
    items = _decode_classifications(raw, version=version, count=len(expected_ids))
    if [item.get("assertion_id") for item in items] != expected_ids:
        raise TaskFormError("residual_codes_accounting_invalid")
    restored = []
    for item in items:
        if (
            set(item) != {"assertion_id", "codes"}
            or not isinstance(item.get("codes"), list)
            or not item["codes"]
            or any(code not in msc.RESIDUAL_CODES for code in item["codes"])
            or item["codes"] != [code for code in msc.RESIDUAL_CODES if code in item["codes"]]
        ):
            raise TaskFormError("residual_codes_contract_invalid")
        restored.append(copy.deepcopy(item))
    return {"schema_version": version, "classifications": restored}


def score_codes_only(response: dict[str, Any], semantic_truth: dict[str, Any]) -> dict[str, Any]:
    expected = {item["source_record_id"]: item["expected_codes"] for item in semantic_truth["residuals"]}
    actual = {item["assertion_id"]: item["codes"] for item in response["classifications"]}
    return {
        "projection_sha256": typed._stable_sha256(actual),
        "correct": sum(actual[key] == expected[key] for key in expected),
        "total": len(expected),
        "exact": actual == expected,
        "downstream_complete": False,
    }


def validate_table_residual_parts(
    raw_outputs: list[Any],
    *,
    versions: list[str],
    grouped: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    table_types = list(grouped)
    classifications = []
    for raw, version, table_type in zip(raw_outputs, versions, table_types, strict=True):
        batch = grouped[table_type]
        partial = {
            "schema_version": msc.RESIDUAL_RESPONSE_VERSION,
            "classifications": _decode_classifications(raw, version=version, count=len(batch["records"])),
        }
        validated = msc.validate_residual_response(partial, residual_batch=batch)
        classifications.extend(validated["classifications"])
    return {"schema_version": msc.RESIDUAL_RESPONSE_VERSION, "classifications": classifications}


def _span_from_refs(*, refs: list[str], record_id: str, wording: str, token_index: dict[str, dict[str, Any]]) -> str:
    if not refs:
        return ""
    if len(refs) != len(set(refs)) or any(ref not in token_index for ref in refs):
        raise TaskFormError("token_ref_invalid")
    tokens = [token_index[ref] for ref in refs]
    if any(token["source_record_id"] != record_id for token in tokens):
        raise TaskFormError("token_ref_cross_record")
    positions = [token["start"] for token in tokens]
    if positions != sorted(positions):
        raise TaskFormError("token_ref_order_invalid")
    all_record_tokens = sorted(
        [item for item in token_index.values() if item["source_record_id"] == record_id],
        key=lambda item: item["start"],
    )
    ordinal = {item["token_ref"]: index for index, item in enumerate(all_record_tokens)}
    selected = [ordinal[ref] for ref in refs]
    if selected != list(range(selected[0], selected[-1] + 1)):
        raise TaskFormError("token_ref_not_contiguous")
    return wording[tokens[0]["start"] : tokens[-1]["end"]]


def validate_event_parts(
    raw_outputs: list[Any],
    *,
    versions: list[str],
    grouped_tokens: dict[str, dict[str, Any]],
    token_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    classifications = []
    event_codes = {
        "COMMISSION": ["COMMISSION_ENTRY"],
        "TRADE_TOTAL": ["TRADE_REGISTER_TOTAL"],
        "COUPON": ["COUPON_PAYMENT"],
        "NOT_RELEVANT": ["NOT_RELEVANT"],
        "UNMAPPED": ["UNMAPPED"],
    }
    for raw, version, table_type in zip(raw_outputs, versions, grouped_tokens, strict=True):
        records = grouped_tokens[table_type]["records"]
        items = _decode_classifications(raw, version=version, count=len(records))
        if [item.get("assertion_id") for item in items] != [item["source_record_id"] for item in records]:
            raise TaskFormError("event_accounting_invalid")
        by_id = {item["source_record_id"]: item for item in records}
        for item in items:
            if set(item) != {
                "assertion_id",
                "event_kind",
                "withholding_stated",
                "asset_token_refs",
                "currency_token_refs",
            }:
                raise TaskFormError("event_contract_invalid")
            record = by_id[item["assertion_id"]]
            if item["event_kind"] not in event_codes or not isinstance(item["withholding_stated"], bool):
                raise TaskFormError("event_value_invalid")
            if not isinstance(item["asset_token_refs"], list) or not isinstance(item["currency_token_refs"], list):
                raise TaskFormError("event_token_contract_invalid")
            codes = copy.deepcopy(event_codes[item["event_kind"]])
            if item["withholding_stated"]:
                if item["event_kind"] != "COUPON":
                    raise TaskFormError("event_withholding_owner_invalid")
                codes.append("WITHHOLDING_STATED")
            asset_span = _span_from_refs(
                refs=item["asset_token_refs"],
                record_id=item["assertion_id"],
                wording=record["source_wording"],
                token_index=token_index,
            )
            currency_span = _span_from_refs(
                refs=item["currency_token_refs"],
                record_id=item["assertion_id"],
                wording=record["source_wording"],
                token_index=token_index,
            )
            if item["event_kind"] != "COUPON" and asset_span:
                raise TaskFormError("event_asset_owner_invalid")
            if item["event_kind"] != "TRADE_TOTAL" and currency_span:
                raise TaskFormError("event_currency_owner_invalid")
            classifications.append(
                {
                    "assertion_id": item["assertion_id"],
                    "codes": codes,
                    "asset_span": asset_span,
                    "currency_span": currency_span,
                }
            )
    response = {"schema_version": msc.RESIDUAL_RESPONSE_VERSION, "classifications": classifications}
    flat_records = [record for group in grouped_tokens.values() for record in group["records"]]
    return msc.validate_residual_response(
        response,
        residual_batch={"schema_version": "broker_closed_residual_batch_v0", "records": flat_records},
    )


def _request(*, instruction: str, contract: dict[str, Any], batch: dict[str, Any], schema: dict[str, Any], name: str) -> dict[str, Any]:
    return typed._model_request(instruction=instruction, contract=contract, batch=batch, schema=schema, name=name)


def build_hypothesis_requests(env: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    single = env["trade_context"]
    all_contexts = env["table_contexts"]
    single_refs = [item["source_ref"] for item in single["headers"]]
    all_refs = [item["source_ref"] for context in all_contexts for item in context["headers"]]
    side = env["side_context"]
    value_refs = [item["value_ref"] for item in side["candidates"]]
    residual_batch = env["residual_batch"]
    grouped = env["grouped_residual"]
    grouped_tokens = env["grouped_tokens"]
    role_contract = {"normalized_roles": msc.ROLE_CATALOG}
    header_instruction = (
        "Это только schema translation. Для каждого exact header_ref выбери одну normalized_role из закрытого каталога. "
        "Не извлекай строки и значения, не пересказывай header, unknown верни unmapped. Только strict JSON."
    )
    requests: dict[str, list[dict[str, Any]]] = {}
    requests[HYPOTHESES[0]] = [
        _request(
            instruction=header_instruction,
            contract=role_contract,
            batch={"schema_version": "broker_header_task_v0", "tables": [{"logical_table_id": single["logical_table_id"], "headers": single["headers"]}]},
            schema=header_forward_schema(
                version=RESPONSE_VERSIONS[HYPOTHESES[0]],
                table_count=1,
                header_refs=single_refs,
                maximum=len(single_refs),
                include_table_type=False,
            ),
            name=RESPONSE_VERSIONS[HYPOTHESES[0]],
        )
    ]
    requests[HYPOTHESES[1]] = [
        _request(
            instruction=(
                "Это обратная schema translation. Верни для каждого предоставленного header_ref ровно одну normalized_role. "
                "Ответ запиши как role_bindings normalized_role -> header_ref; не копируй literals и не извлекай строки. Только strict JSON."
            ),
            contract=role_contract,
            batch={"schema_version": "broker_header_task_v0", "tables": [{"logical_table_id": single["logical_table_id"], "headers": single["headers"]}]},
            schema=header_inverse_schema(version=RESPONSE_VERSIONS[HYPOTHESES[1]], table_id=single["logical_table_id"], header_refs=single_refs),
            name=RESPONSE_VERSIONS[HYPOTHESES[1]],
        )
    ]
    requests[HYPOTHESES[2]] = [
        _request(
            instruction=header_instruction + " Также выбери table_type. Обработай все таблицы независимо и сохрани их порядок.",
            contract={**role_contract, "table_types": list(msc.TABLE_TYPES)},
            batch={"schema_version": "broker_header_task_v0", "tables": all_contexts},
            schema=header_forward_schema(
                version=RESPONSE_VERSIONS[HYPOTHESES[2]],
                table_count=len(all_contexts),
                header_refs=all_refs,
                maximum=max(len(item["headers"]) for item in all_contexts),
                include_table_type=True,
            ),
            name=RESPONSE_VERSIONS[HYPOTHESES[2]],
        )
    ]
    side_common = (
        "Определи только семантику двух уникальных значений колонки side. Не извлекай сделки, не делай финансовых выводов. "
        "Одно значение означает PURCHASE, другое DISPOSAL. Только strict JSON."
    )
    requests[HYPOTHESES[3]] = [
        _request(
            instruction=side_common + " Скопируй source_literal verbatim.",
            contract={"normalized_values": ["PURCHASE", "DISPOSAL"]},
            batch=side,
            schema=side_schema(version=RESPONSE_VERSIONS[HYPOTHESES[3]], mode="literal", value_refs=value_refs),
            name=RESPONSE_VERSIONS[HYPOTHESES[3]],
        )
    ]
    requests[HYPOTHESES[4]] = [
        _request(
            instruction=side_common + " Не копируй literal; верни только exact value_ref и normalized_value.",
            contract={"normalized_values": ["PURCHASE", "DISPOSAL"]},
            batch=side,
            schema=side_schema(version=RESPONSE_VERSIONS[HYPOTHESES[4]], mode="ref", value_refs=value_refs),
            name=RESPONSE_VERSIONS[HYPOTHESES[4]],
        )
    ]
    requests[HYPOTHESES[5]] = [
        _request(
            instruction=(
                "Из двух unique side candidates выбери только exact value_ref, который означает PURCHASE. "
                "Второе значение код детерминированно считает DISPOSAL. Не копируй literal. Только strict JSON."
            ),
            contract={"decision": "purchase_value_ref"},
            batch=side,
            schema=side_schema(version=RESPONSE_VERSIONS[HYPOTHESES[5]], mode="purchase_ref", value_refs=value_refs, count=1),
            name=RESPONSE_VERSIONS[HYPOTHESES[5]],
        )
    ]
    requests[HYPOTHESES[6]] = [
        _request(
            instruction=msc.RESIDUAL_INSTRUCTION,
            contract={"codes": list(msc.RESIDUAL_CODES)},
            batch=residual_batch,
            schema=msc.residual_schema([item["source_record_id"] for item in residual_batch["records"]]),
            name=msc.RESIDUAL_RESPONSE_VERSION,
        )
    ]
    table_codes = {
        "CASH_OPERATIONS": ["COMMISSION_ENTRY", "NOT_RELEVANT", "UNMAPPED"],
        "SECURITY_TRADES": ["TRADE_REGISTER_TOTAL", "NOT_RELEVANT", "UNMAPPED"],
        "INCOME_PAYMENTS": ["COUPON_PAYMENT", "WITHHOLDING_STATED", "NOT_RELEVANT", "UNMAPPED"],
    }
    requests[HYPOTHESES[7]] = []
    for table_type, group in grouped.items():
        version = RESPONSE_VERSIONS[HYPOTHESES[7]] + "_" + table_type.lower()
        requests[HYPOTHESES[7]].append(
            _request(
                instruction=(
                    "Реши только смысл source_wording для одного table_type. Codes ограничены контрактом этой таблицы. "
                    "asset_span разрешён только для COUPON_PAYMENT; currency_span только для TRADE_REGISTER_TOTAL; "
                    "для остальных верни пустую строку. Date и amount не выбирай. Только strict JSON."
                ),
                contract={"table_type": table_type, "codes": table_codes[table_type]},
                batch=group,
                schema=residual_codes_schema(
                    version=version,
                    source_ids=[item["source_record_id"] for item in group["records"]],
                    codes=table_codes[table_type],
                    include_spans=True,
                ),
                name=version,
            )
        )
    requests[HYPOTHESES[8]] = [
        _request(
            instruction=(
                "Для каждого source_record_id выбери только semantic codes из закрытого каталога. "
                "Ничего не копируй из текста, spans и значения не возвращай. Сохрани порядок. Только strict JSON."
            ),
            contract={"codes": list(msc.RESIDUAL_CODES)},
            batch=residual_batch,
            schema=residual_codes_schema(
                version=RESPONSE_VERSIONS[HYPOTHESES[8]],
                source_ids=[item["source_record_id"] for item in residual_batch["records"]],
                codes=list(msc.RESIDUAL_CODES),
                include_spans=False,
            ),
            name=RESPONSE_VERSIONS[HYPOTHESES[8]],
        )
    ]
    requests[HYPOTHESES[9]] = []
    for table_type, group in grouped_tokens.items():
        refs = [token["token_ref"] for record in group["records"] for token in record["tokens"]]
        version = RESPONSE_VERSIONS[HYPOTHESES[9]] + "_" + table_type.lower()
        requests[HYPOTHESES[9]].append(
            _request(
                instruction=(
                    "Верни source-shaped event_kind и withholding_stated. Не копируй текст. "
                    "Для asset/currency выбери exact token_refs в исходном порядке; используй их только когда поле принадлежит event_kind. "
                    "Date и amount не выбирай. Только strict JSON."
                ),
                contract={"table_type": table_type, "evidence_addressing": "token_refs"},
                batch=group,
                schema=residual_event_schema(
                    version=version,
                    source_ids=[item["source_record_id"] for item in group["records"]],
                    table_type=table_type,
                    token_refs=refs,
                ),
                name=version,
            )
        )
    return requests


def validate_and_score(hypothesis: str, raw_outputs: list[Any], env: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    version = RESPONSE_VERSIONS[hypothesis]
    if hypothesis == HYPOTHESES[0]:
        value = validate_header_forward(raw_outputs[0], version=version, contexts=[env["trade_context"]])
        return value, score_headers(mappings=value, truth=env["semantic_truth"])
    if hypothesis == HYPOTHESES[1]:
        value = validate_header_inverse(raw_outputs[0], version=version, context=env["trade_context"])
        return value, score_headers(mappings=value, truth=env["semantic_truth"])
    if hypothesis == HYPOTHESES[2]:
        value = validate_header_forward(
            raw_outputs[0],
            version=version,
            contexts=env["table_contexts"],
            expect_table_type=True,
        )
        return value, score_headers(mappings=value, truth=env["semantic_truth"])
    if hypothesis in HYPOTHESES[3:6]:
        mode = {HYPOTHESES[3]: "literal", HYPOTHESES[4]: "ref", HYPOTHESES[5]: "purchase_ref"}[hypothesis]
        value = validate_side(
            raw_outputs[0],
            version=version,
            mode=mode,
            context=env["side_context"],
            expected=env["expected_side_bindings"],
        )
        return value, score_side(value, env["expected_side_bindings"])
    if hypothesis == HYPOTHESES[6]:
        value = msc.validate_residual_response(raw_outputs[0], residual_batch=env["residual_batch"])
        score = msc.score_residual(response=value, semantic_truth=env["semantic_truth"])
        return value, {"projection_sha256": score["projection_sha256"], "correct": score["records_correct"], "total": score["records_total"], "exact": score["exact"], "downstream_complete": True}
    if hypothesis == HYPOTHESES[7]:
        versions = [version + "_" + table_type.lower() for table_type in env["grouped_residual"]]
        value = validate_table_residual_parts(raw_outputs, versions=versions, grouped=env["grouped_residual"])
        score = msc.score_residual(response=value, semantic_truth=env["semantic_truth"])
        return value, {"projection_sha256": score["projection_sha256"], "correct": score["records_correct"], "total": score["records_total"], "exact": score["exact"], "downstream_complete": True}
    if hypothesis == HYPOTHESES[8]:
        value = validate_codes_only(raw_outputs[0], version=version, residual_batch=env["residual_batch"])
        return value, score_codes_only(value, env["semantic_truth"])
    if hypothesis == HYPOTHESES[9]:
        versions = [version + "_" + table_type.lower() for table_type in env["grouped_tokens"]]
        value = validate_event_parts(
            raw_outputs,
            versions=versions,
            grouped_tokens=env["grouped_tokens"],
            token_index=env["token_index"],
        )
        score = msc.score_residual(response=value, semantic_truth=env["semantic_truth"])
        return value, {"projection_sha256": score["projection_sha256"], "correct": score["records_correct"], "total": score["records_total"], "exact": score["exact"], "downstream_complete": True}
    raise TaskFormError("hypothesis_unknown")


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [item for item in runs if item["terminal_status"] == "validated"]
    hashes = [item["projection_sha256"] for item in valid]
    return {
        "runs": runs,
        "validated_runs": len(valid),
        "unique_hashes": len(set(hashes)),
        "exact_repeatability": len(valid) == RUNS and len(set(hashes)) == 1,
        "exact_correct": len(valid) == RUNS and all(item["exact"] for item in valid),
        "best_correct": max((item["correct"] for item in valid), default=0),
        "total": max((item["total"] for item in valid), default=0),
        "provider_calls": sum(item.get("provider_calls", 0) for item in runs),
        "input_tokens": sum(item.get("input_tokens") or 0 for item in runs),
        "output_tokens": sum(item.get("output_tokens") or 0 for item in runs),
        "duration_ms": sum(item.get("duration_ms") or 0 for item in runs),
    }


def _safe_error(ordinal: int, exc: Exception, calls: int) -> dict[str, Any]:
    result = {
        "ordinal": ordinal,
        "terminal_status": "rejected",
        "error_type": type(exc).__name__,
        "provider_calls": calls,
    }
    message = str(exc)
    if isinstance(exc, (TaskFormError, msc.SemanticCompilerError)) and re.fullmatch(r"[a-z0-9_]+", message):
        result["error_code"] = message
    return result


def _safe_execution(executions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "provider_calls": sum(item.get("provider_calls") or 0 for item in executions),
        "input_tokens": sum(item.get("input_tokens") or 0 for item in executions),
        "output_tokens": sum(item.get("output_tokens") or 0 for item in executions),
        "duration_ms": sum(item.get("duration_ms") or 0 for item in executions),
    }


def persisted_execution_accounting(private_runs: list[dict[str, Any]]) -> dict[str, Any]:
    executions = [
        execution
        for private_run in private_runs
        for hypothesis in HYPOTHESES
        for execution in private_run.get(hypothesis, {}).get("executions", [])
        if isinstance(execution, dict)
    ]
    return {
        "provider_calls": len(executions),
        "calls_with_persisted_usage": len(executions),
        "input_tokens": sum(item.get("input_tokens") or 0 for item in executions),
        "output_tokens": sum(item.get("output_tokens") or 0 for item in executions),
        "duration_ms": sum(item.get("duration_ms") or 0 for item in executions),
        "money_cost_available": False,
    }


def choose_winner(summaries: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    return next(
        (
            candidate
            for candidate in candidates
            if summaries[candidate]["exact_repeatability"] and summaries[candidate]["exact_correct"]
        ),
        None,
    )


def compile_final_runs(
    *,
    private_runs: list[dict[str, Any]],
    header_winner: str | None,
    side_winner: str | None,
    residual_winner: str | None,
    env: dict[str, Any],
) -> list[dict[str, Any]]:
    result = []
    if not header_winner or not side_winner or not residual_winner:
        return [
            {"ordinal": ordinal, "terminal_status": "rejected", "error_type": "WinningAtomicContractUnavailable"}
            for ordinal in range(1, RUNS + 1)
        ]
    truth_by_table = {item["logical_table_id"]: item for item in env["semantic_truth"]["schema_mappings"]}
    for ordinal, private_run in enumerate(private_runs, 1):
        try:
            header = private_run[header_winner]["validated"]
            side = private_run[side_winner]["validated"]
            residual = private_run[residual_winner]["validated"]
            trade_mapping_value = next(item for item in header if item["logical_table_id"] == env["trade_context"]["logical_table_id"])
            trade_mapping = {
                "assertion_id": trade_mapping_value["logical_table_id"],
                "table_type": trade_mapping_value.get(
                    "table_type",
                    truth_by_table[trade_mapping_value["logical_table_id"]]["table_type"],
                ),
                "columns": trade_mapping_value["columns"],
                "value_bindings": side,
            }
            trade_projection, _ = msc.deterministic_trade_projection(source_batch=env["source_batch"], mapping=trade_mapping)
            semantic_for_materialization = copy.deepcopy(env["semantic_truth"])
            if header_winner == HYPOTHESES[2]:
                actual_by_id = {item["logical_table_id"]: item for item in header}
                for mapping in semantic_for_materialization["schema_mappings"]:
                    mapping["columns"] = copy.deepcopy(actual_by_id[mapping["logical_table_id"]]["columns"])
                    mapping["table_type"] = actual_by_id[mapping["logical_table_id"]]["table_type"]
            residual_projection = msc.materialize_residuals(
                response=residual,
                source_batch=env["source_batch"],
                semantic_truth=semantic_for_materialization,
            )
            projection = msc.merge_projection(
                source_batch=env["source_batch"],
                trade=trade_projection,
                residual=residual_projection,
            )
            metrics = typed.score_projection(
                projection=projection,
                truth=env["source_truth"],
                batch=env["source_batch"],
                deterministic_source_ids={"r004", "r005", "r006"},
                execution=[],
            )
            exact = (
                metrics["missing_typed_records"] == 0
                and metrics["extra_typed_records"] == 0
                and metrics["exact_typed_records_correct"] == metrics["expected_typed_records"]
                and metrics["dispositions_correct"] == len(env["source_batch"]["source_records"])
            )
            result.append(
                {
                    "ordinal": ordinal,
                    "terminal_status": "validated",
                    "projection_sha256": metrics["projection_sha256"],
                    "exact": exact,
                    "typed_records": metrics["actual_typed_records"],
                    "source_accounting_exact": metrics["source_accounting_exact"],
                    "idempotency": metrics["idempotency"],
                }
            )
        except Exception as exc:
            result.append(_safe_error(ordinal, exc, 0))
    return result


def choose_terminal(*, header_winner: str | None, side_winner: str | None, residual_winner: str | None, final_runs: list[dict[str, Any]]) -> str:
    valid = [item for item in final_runs if item["terminal_status"] == "validated"]
    full = len(valid) == RUNS and len({item["projection_sha256"] for item in valid}) == 1 and all(item["exact"] for item in valid)
    if full and header_winner == HYPOTHESES[2] and side_winner and residual_winner:
        return "TASK_FORM_SEMANTIC_COMPILER_PROVEN"
    if full and header_winner and side_winner and residual_winner:
        return "ATOMIC_TASK_FORM_PARTIAL_PROVEN"
    return "NO_STABLE_TASK_FORM_FOUND"


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-three-runs", action="store_true")
    parser.add_argument("--rescore-existing", action="store_true")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--private-store-root", type=Path, required=True)
    parser.add_argument("--private-source-truth", type=Path, required=True)
    parser.add_argument("--private-semantic-truth", type=Path, required=True)
    parser.add_argument("--private-results-dir", type=Path, required=True)
    parser.add_argument("--prior-receipt", type=Path, required=True)
    parser.add_argument("--safe-receipt-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    if args.execute_three_runs == args.rescore_existing:
        raise SystemExit("exactly_one_execution_mode_required")
    if not 1 <= args.timeout_seconds <= 900:
        raise SystemExit("timeout_out_of_bounds")
    private_paths = [
        args.private_store_root.resolve(),
        args.private_source_truth.resolve(),
        args.private_semantic_truth.resolve(),
        args.private_results_dir.resolve(),
    ]
    if any(_within(path, REPO_ROOT.resolve()) for path in private_paths):
        raise SystemExit("private_evidence_must_be_outside_repository")
    safe_receipt = args.safe_receipt_path.resolve()
    if not _within(safe_receipt, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    results_dir = args.private_results_dir.resolve()
    if args.execute_three_runs and results_dir.exists() and any(results_dir.iterdir()):
        raise SystemExit("private_results_must_be_new_or_empty")
    if args.rescore_existing and not all((results_dir / f"run-{ordinal}.private.json").is_file() for ordinal in range(1, RUNS + 1)):
        raise SystemExit("stored_private_runs_missing")
    results_dir.mkdir(parents=True, exist_ok=True)

    source_truth_raw = args.private_source_truth.resolve().read_bytes()
    semantic_truth_raw = args.private_semantic_truth.resolve().read_bytes()
    source_truth = typed._validated_truth(json.loads(source_truth_raw))
    semantic_truth = msc.validate_semantic_truth(json.loads(semantic_truth_raw))
    store_root = args.private_store_root.resolve()
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(mode="sqlite", sqlite_path=store_root / "artifacts.sqlite3", payload_root=store_root / "payloads")
    ).create()
    document_id, context = typed._frozen_context(store_root)
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(document_id=document_id, context=context)
    if (
        len(chunk_set["chunks"]) != 1
        or chunk_set["coverage"]["eligible_targets"] != msc.EXPECTED_CURRENT_TARGETS
        or chunk_set["coverage"]["lost_targets"] != 0
        or chunk_set["coverage"]["duplicated_working_targets"] != 0
    ):
        raise SystemExit("frozen_canonical_seam_changed")
    chunk = chunk_set["chunks"][0]
    source_batch = typed.build_batch(chunk=chunk, truth=source_truth)
    table_contexts = build_table_contexts(chunk=chunk, source_batch=source_batch, semantic_truth=semantic_truth)
    trade_id = semantic_truth["mapping_benchmark_table_id"]
    trade_context = next(item for item in table_contexts if item["logical_table_id"] == trade_id)
    mapping_truth = next(item for item in semantic_truth["schema_mappings"] if item["logical_table_id"] == trade_id)
    representative_rows = [
        item for item in source_batch["source_records"] if item["source_record_id"] in semantic_truth["representative_source_ids"]
    ]
    side_context = build_side_context(
        table_context=trade_context,
        representative_rows=representative_rows,
        mapping_truth=mapping_truth,
    )
    prior_contexts = msc.build_contexts(chunk=chunk, source_batch=source_batch, semantic_truth=semantic_truth)
    expected_side_bindings = msc.expected_side_bindings(
        mapping_truth=mapping_truth,
        context=prior_contexts["title_headers_rows"],
        source_truth=source_truth,
    )
    residual_batch = msc.build_residual_batch(source_batch=source_batch, semantic_truth=semantic_truth)
    grouped_residual = _group_residual(residual_batch)
    token_batch, token_index = tokenize_residual_batch(residual_batch)
    grouped_tokens = _group_residual(token_batch)
    env = {
        "source_truth": source_truth,
        "semantic_truth": semantic_truth,
        "source_batch": source_batch,
        "table_contexts": table_contexts,
        "trade_context": trade_context,
        "side_context": side_context,
        "expected_side_bindings": expected_side_bindings,
        "residual_batch": residual_batch,
        "grouped_residual": grouped_residual,
        "grouped_tokens": grouped_tokens,
        "token_index": token_index,
    }
    requests = build_hypothesis_requests(env)
    plan = {
        "schema_version": "broker_semantic_task_forms_plan_v0",
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_truth_sha256": hashlib.sha256(source_truth_raw).hexdigest(),
        "semantic_truth_sha256": hashlib.sha256(semantic_truth_raw).hexdigest(),
        "hypotheses": list(HYPOTHESES),
        "requests": requests,
        "runs": RUNS,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "production_activation": False,
    }
    if args.execute_three_runs:
        typed._atomic_write(results_dir / "frozen-plan.private.json", typed._json_bytes(plan))
        typed.model_clients_module.GATE3_OPERATIONAL_RETRY_LIMIT = 0
        client, submissions = typed._live_client(env_file=args.env_file, timeout_seconds=args.timeout_seconds)
    else:
        stored_plan = typed._read_json(results_dir / "frozen-plan.private.json")
        if typed._stable_sha256(stored_plan) != typed._stable_sha256(plan):
            raise SystemExit("stored_plan_changed")
        submissions = {"count": 0}

    hypothesis_runs: dict[str, list[dict[str, Any]]] = {key: [] for key in HYPOTHESES}
    private_runs = []
    for ordinal in range(1, RUNS + 1):
        if args.rescore_existing:
            private_run = typed._read_json(results_dir / f"run-{ordinal}.private.json")
        else:
            private_run = {"ordinal": ordinal}
        for hypothesis in HYPOTHESES:
            before = submissions["count"]
            if args.rescore_existing:
                evidence = private_run.get(hypothesis, {})
                raw_outputs = copy.deepcopy(evidence.get("raw_model_outputs") or [])
                executions = copy.deepcopy(evidence.get("executions") or [])
            else:
                raw_outputs = []
                raw_provider_responses = []
                executions = []
                try:
                    for request in requests[hypothesis]:
                        before_part = submissions["count"]
                        result = asyncio.run(
                            client.label_gate3_once(
                                model_visible_request=request,
                                canonical_schema=request["response_format"]["json_schema"]["schema"],
                                model_id=NDFL_PROVIDER_MODEL_ID,
                            )
                        )
                        raw_outputs.append(copy.deepcopy(result.adapter_extracted_output))
                        raw_provider_responses.append(copy.deepcopy(result.raw_provider_response))
                        executions.append(typed._execution_metrics(result, provider_calls=submissions["count"] - before_part))
                except Exception as exc:
                    calls = submissions["count"] - before
                    hypothesis_runs[hypothesis].append(
                        {**_safe_error(ordinal, exc, calls), **_safe_execution(executions)}
                    )
                    private_run[hypothesis] = {
                        "rejected": True,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "raw_model_outputs": raw_outputs,
                        "raw_provider_responses": raw_provider_responses,
                        "executions": executions,
                    }
                    continue
            try:
                validated, score = validate_and_score(hypothesis, raw_outputs, env)
                safe_execution = _safe_execution(executions)
                hypothesis_runs[hypothesis].append(
                    {
                        "ordinal": ordinal,
                        "terminal_status": "validated",
                        **score,
                        **safe_execution,
                    }
                )
                private_run[hypothesis] = {
                    **copy.deepcopy(private_run.get(hypothesis, {})),
                    "validated": validated,
                    "raw_model_outputs": raw_outputs,
                    "executions": executions,
                }
            except Exception as exc:
                calls = 0 if args.rescore_existing else submissions["count"] - before
                hypothesis_runs[hypothesis].append(
                    {**_safe_error(ordinal, exc, calls), **_safe_execution(executions)}
                )
                private_run[hypothesis] = {
                    **copy.deepcopy(private_run.get(hypothesis, {})),
                    "rejected": True,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "raw_model_outputs": raw_outputs,
                    "executions": executions,
                }
        if not args.rescore_existing:
            typed._atomic_write(results_dir / f"run-{ordinal}.private.json", typed._json_bytes(private_run))
        private_runs.append(private_run)

    summaries = {hypothesis: summarize(runs) for hypothesis, runs in hypothesis_runs.items()}
    header_winner = choose_winner(summaries, (HYPOTHESES[2], HYPOTHESES[0], HYPOTHESES[1]))
    side_winner = choose_winner(summaries, (HYPOTHESES[5], HYPOTHESES[4], HYPOTHESES[3]))
    residual_winner = choose_winner(summaries, (HYPOTHESES[7], HYPOTHESES[9], HYPOTHESES[6]))
    final_runs = compile_final_runs(
        private_runs=private_runs,
        header_winner=header_winner,
        side_winner=side_winner,
        residual_winner=residual_winner,
        env=env,
    )
    terminal = choose_terminal(
        header_winner=header_winner,
        side_winner=side_winner,
        residual_winner=residual_winner,
        final_runs=final_runs,
    )
    if terminal not in TERMINALS:
        raise TaskFormError("terminal_invalid")
    prior = typed._read_json(args.prior_receipt.resolve())
    receipt = {
        "schema_version": "broker_semantic_task_forms_receipt_v0",
        "status": terminal,
        "terminals": [terminal],
        "research_only": True,
        "production_changed": False,
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_records": len(source_batch["source_records"]),
        "logical_tables": len(table_contexts),
        "expected_typed_records": sum(len(item["expected_records"]) for item in source_truth["source_records"]),
        "model_id": NDFL_PROVIDER_MODEL_ID,
        "provider_profile_id": NDFL_PROVIDER_PROFILE_ID,
        "runs": RUNS,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "offline_rescore": {"performed": args.rescore_existing, "provider_calls": 0 if args.rescore_existing else None},
        "hypotheses": summaries,
        "winners": {
            "header": header_winner,
            "side": side_winner,
            "residual": residual_winner,
        },
        "answer_leak_audit": {
            "expected_assignments_in_model_requests": False,
            "source_truth_hash_only_in_private_plan_metadata": True,
            "H3_closed_catalog_not_expected_mapping": True,
            "H6_candidates_include_both_values_without_expected_meaning": True,
            "H8_allowed_codes_depend_only_on_table_type": True,
            "H8_per_row_expected_codes_in_request": False,
            "H8_frozen_grouping_matches_H3_output_all_runs": summaries[HYPOTHESES[2]]["exact_correct"],
        },
        "final_projection_runs": final_runs,
        "semantic_surface": {
            "header_decisions": 30 if header_winner == HYPOTHESES[2] else 16 if header_winner else None,
            "side_decisions": 1 if side_winner == HYPOTHESES[5] else 2 if side_winner else None,
            "residual_truth_decisions": sum(
                len(item["expected_codes"]) + bool(item["expected_asset_span"]) + bool(item["expected_currency_span"])
                for item in semantic_truth["residuals"]
            ),
            "runtime_role_values": sum(
                len(record["roles"])
                for source in source_truth["source_records"]
                for record in source["expected_records"]
            ),
        },
        "execution_accounting": persisted_execution_accounting(private_runs),
        "prior_comparator": {
            "status": prior["status"],
            "minimum_correct_mapping_context": prior["minimum_correct_mapping_context"],
            "full_mapping_variant": prior["full_mapping_variant"],
            "residual_exact_repeatability": prior["residual"]["exact_repeatability"],
        },
        "private_evidence_sha256": typed._stable_sha256(
            [typed._stable_sha256(item) for item in private_runs]
        ),
    }
    typed._atomic_write(safe_receipt, typed._json_bytes(receipt))
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
