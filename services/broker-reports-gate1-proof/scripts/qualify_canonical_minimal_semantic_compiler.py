#!/usr/bin/env python3
"""Research-only benchmark for the smallest Canonical semantic compiler."""

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
import qualify_canonical_typed_broker_registers_benchmark as typed  # noqa: E402


FROZEN_CANONICAL_ROOT_SHA256 = typed.FROZEN_CANONICAL_ROOT_SHA256
EXPECTED_CURRENT_TARGETS = typed.EXPECTED_CURRENT_TARGETS
RUNS = 3
MAPPING_RESPONSE_VERSION = "broker_header_schema_mapping_response_v0"
TABLE_TYPE_RESPONSE_VERSION = "broker_table_type_response_v0"
COLUMN_RESPONSE_VERSION = "broker_column_mapping_response_v0"
RESIDUAL_RESPONSE_VERSION = "broker_closed_residual_response_v0"
TABLE_TYPES = ("SECURITY_TRADES", "CASH_OPERATIONS", "INCOME_PAYMENTS", "UNMAPPED")
NORMALIZED_ROLES = (
    "trade_date",
    "settlement_date",
    "trade_time",
    "event_date",
    "asset_name",
    "security_code",
    "currency",
    "side",
    "quantity",
    "unit_price",
    "gross_amount",
    "amount",
    "accrued_interest",
    "broker_commission",
    "exchange_commission",
    "trade_id",
    "comment",
    "status",
    "venue",
    "description",
    "credit_amount",
    "debit_amount",
    "unmapped",
)
RESIDUAL_CODES = (
    "COMMISSION_ENTRY",
    "TRADE_REGISTER_TOTAL",
    "COUPON_PAYMENT",
    "WITHHOLDING_STATED",
    "NOT_RELEVANT",
    "UNMAPPED",
)
CONTEXT_VARIANTS = ("headers_only", "title_headers", "title_headers_rows")

ROLE_CATALOG = {
    "trade_date": "date when the trade was concluded",
    "settlement_date": "date when the trade settles",
    "trade_time": "time when the trade was concluded",
    "event_date": "date of a non-trade source event",
    "asset_name": "source-authored security or instrument name",
    "security_code": "source-authored security identifier or code",
    "currency": "source-authored currency",
    "side": "purchase or disposal direction field",
    "quantity": "security quantity",
    "unit_price": "price per unit",
    "gross_amount": "source-authored total trade amount",
    "amount": "generic source-authored amount",
    "accrued_interest": "source-authored accrued coupon interest component",
    "broker_commission": "broker commission column attached to the same row",
    "exchange_commission": "exchange commission column attached to the same row",
    "trade_id": "source-authored trade identifier",
    "comment": "source-authored comment",
    "status": "source-authored operation status",
    "venue": "source-authored market or venue",
    "description": "free-text source event description",
    "credit_amount": "credited amount column",
    "debit_amount": "debited amount column",
    "unmapped": "header is present but no catalog role is justified",
}

MAPPING_INSTRUCTION = (
    "Ты выполняешь только schema translation, не извлечение финансовых записей. "
    "Для exact logical_table_id верни table_type и для каждого предоставленного header_ref ровно одну "
    "normalized_role в исходном порядке. Исходные headers не переименовывай и не пересказывай. "
    "Unknown обязан стать unmapped. value_bindings разрешены только для exact literals, которые явно "
    "присутствуют в representative rows; без rows список обязан быть пустым. Не создавай typed records, "
    "не выбирай суммы, не делай налоговых выводов и не добавляй пояснения. Верни только strict JSON."
)
TYPE_INSTRUCTION = (
    "Определи только table_type для exact logical_table_id по предоставленному structural context. "
    "Не mapping columns, не извлечение строк, не финансовые и не налоговые выводы. Если тип не доказан, "
    "верни UNMAPPED. Верни только strict JSON."
)
COLUMN_INSTRUCTION = (
    "Table type уже передан как frozen input. Для каждого header_ref верни ровно одну normalized_role "
    "в исходном порядке. Unknown обязан стать unmapped. value_bindings разрешены только для exact literals "
    "из representative rows. Не меняй table_type, не извлекай records и не делай налоговых выводов. "
    "Верни только strict JSON."
)
RESIDUAL_INSTRUCTION = (
    "Ты решаешь только смысл exact free-text source wording. Для каждого source_record_id верни один или "
    "несколько codes из закрытого каталога в порядке каталога. Date, amount и currency из колонок не "
    "выбирай. asset_span и currency_span копируй verbatim из source_wording только когда этот смысл "
    "действительно находится внутри wording; иначе верни пустую строку. Compound coupon plus withholding "
    "должен дать два codes. Фраза об удержании без отдельной суммы не разрешает придумывать сумму. "
    "Не объединяй похожие observations. Верни только strict JSON."
)


class SemanticCompilerError(RuntimeError):
    pass


def validate_semantic_truth(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "broker_minimal_semantic_compiler_truth_v0"
        or value.get("frozen_canonical_root_sha256") != FROZEN_CANONICAL_ROOT_SHA256
        or value.get("qualified_before_model_execution") is not True
        or value.get("model_output_used_as_truth_hint") is not False
        or not isinstance(value.get("schema_mappings"), list)
        or not isinstance(value.get("residuals"), list)
    ):
        raise SemanticCompilerError("semantic_truth_invalid")
    table_ids = []
    for mapping in value["schema_mappings"]:
        if (
            not isinstance(mapping, dict)
            or set(mapping) != {"logical_table_id", "table_type", "title_ref", "columns"}
            or re.fullmatch(r"g[0-9]{3}", str(mapping.get("logical_table_id") or "")) is None
            or mapping.get("table_type") not in TABLE_TYPES
            or re.fullmatch(r"t[0-9]+", str(mapping.get("title_ref") or "")) is None
            or not isinstance(mapping.get("columns"), list)
            or not mapping["columns"]
        ):
            raise SemanticCompilerError("semantic_truth_mapping_invalid")
        table_ids.append(mapping["logical_table_id"])
        refs = []
        roles = []
        for column in mapping["columns"]:
            if (
                not isinstance(column, dict)
                or set(column) != {"header_ref", "normalized_role"}
                or re.fullmatch(r"t[0-9]+", str(column.get("header_ref") or "")) is None
                or column.get("normalized_role") not in NORMALIZED_ROLES
            ):
                raise SemanticCompilerError("semantic_truth_column_invalid")
            refs.append(column["header_ref"])
            roles.append(column["normalized_role"])
        if len(refs) != len(set(refs)) or len(roles) != len(set(roles)):
            raise SemanticCompilerError("semantic_truth_column_duplicate")
    if len(table_ids) != len(set(table_ids)) or value.get("mapping_benchmark_table_id") not in table_ids:
        raise SemanticCompilerError("semantic_truth_table_invalid")
    residual_ids = []
    for residual in value["residuals"]:
        if (
            not isinstance(residual, dict)
            or set(residual)
            != {
                "source_record_id",
                "wording_ref",
                "expected_codes",
                "expected_asset_span",
                "expected_currency_span",
            }
            or re.fullmatch(r"r[0-9]{3}", str(residual.get("source_record_id") or "")) is None
            or re.fullmatch(r"t[0-9]+", str(residual.get("wording_ref") or "")) is None
            or not isinstance(residual.get("expected_codes"), list)
            or not residual["expected_codes"]
            or any(code not in RESIDUAL_CODES for code in residual["expected_codes"])
            or not isinstance(residual.get("expected_asset_span"), str)
            or not isinstance(residual.get("expected_currency_span"), str)
        ):
            raise SemanticCompilerError("semantic_truth_residual_invalid")
        residual_ids.append(residual["source_record_id"])
    if len(residual_ids) != len(set(residual_ids)):
        raise SemanticCompilerError("semantic_truth_residual_duplicate")
    return copy.deepcopy(value)


def mapping_schema(*, table_id: str, header_refs: list[str]) -> dict[str, Any]:
    return _schema_root(
        version=MAPPING_RESPONSE_VERSION,
        item={
            "type": "object",
            "additionalProperties": False,
            "required": ["assertion_id", "table_type", "columns", "value_bindings"],
            "properties": {
                "assertion_id": _assertion_id(table_id),
                "table_type": {"type": "string", "enum": list(TABLE_TYPES)},
                "columns": _columns_schema(header_refs),
                "value_bindings": _value_bindings_schema(),
            },
        },
    )


def table_type_schema(*, table_id: str) -> dict[str, Any]:
    return _schema_root(
        version=TABLE_TYPE_RESPONSE_VERSION,
        item={
            "type": "object",
            "additionalProperties": False,
            "required": ["assertion_id", "table_type"],
            "properties": {
                "assertion_id": _assertion_id(table_id),
                "table_type": {"type": "string", "enum": list(TABLE_TYPES)},
            },
        },
    )


def column_schema(*, table_id: str, header_refs: list[str]) -> dict[str, Any]:
    return _schema_root(
        version=COLUMN_RESPONSE_VERSION,
        item={
            "type": "object",
            "additionalProperties": False,
            "required": ["assertion_id", "columns", "value_bindings"],
            "properties": {
                "assertion_id": _assertion_id(table_id),
                "columns": _columns_schema(header_refs),
                "value_bindings": _value_bindings_schema(),
            },
        },
    )


def residual_schema(source_ids: list[str]) -> dict[str, Any]:
    return _schema_root(
        version=RESIDUAL_RESPONSE_VERSION,
        count=len(source_ids),
        item={
            "type": "object",
            "additionalProperties": False,
            "required": ["assertion_id", "codes", "asset_span", "currency_span"],
            "properties": {
                "assertion_id": {
                    "type": "string",
                    "pattern": r"^r[0-9]{3}$",
                    "description": "Copy one exact source_record_id from the batch.",
                },
                "codes": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 2,
                    "items": {"type": "string", "enum": list(RESIDUAL_CODES)},
                },
                "asset_span": {"type": "string"},
                "currency_span": {"type": "string"},
            },
        },
    )


def _schema_root(*, version: str, item: dict[str, Any], count: int = 1) -> dict[str, Any]:
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


def _assertion_id(table_id: str) -> dict[str, Any]:
    return {
        "type": "string",
        "pattern": r"^g[0-9]{3}$",
        "description": f"Copy exact logical_table_id {table_id} from the batch.",
    }


def _columns_schema(header_refs: list[str]) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": len(header_refs),
        "maxItems": len(header_refs),
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["header_ref", "normalized_role"],
            "properties": {
                "header_ref": {"type": "string", "enum": header_refs},
                "normalized_role": {"type": "string", "enum": list(NORMALIZED_ROLES)},
            },
        },
    }


def _value_bindings_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": 0,
        "maxItems": 4,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["column_role", "source_literal", "normalized_value"],
            "properties": {
                "column_role": {"const": "side"},
                "source_literal": {"type": "string", "minLength": 1},
                "normalized_value": {"type": "string", "enum": ["PURCHASE", "DISPOSAL"]},
            },
        },
    }


def build_contexts(*, chunk: dict[str, Any], source_batch: dict[str, Any], semantic_truth: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping_by_alias = {
        item["target_alias"]: item["canonical_target"]
        for item in chunk["target_mappings"]
    }
    text_by_alias, _ = typed._visible_text_index(
        content=chunk["model_view"]["content"],
        mapping_by_alias=mapping_by_alias,
    )
    mapping = next(
        item
        for item in semantic_truth["schema_mappings"]
        if item["logical_table_id"] == semantic_truth["mapping_benchmark_table_id"]
    )
    rows = [
        row
        for row in source_batch["source_records"]
        if row["source_record_id"] in semantic_truth["representative_source_ids"]
    ]
    headers = copy.deepcopy(rows[0]["header_context"])
    if [item["source_ref"] for item in headers] != [item["header_ref"] for item in mapping["columns"]]:
        raise SemanticCompilerError("mapping_truth_header_mismatch")
    title = text_by_alias.get(mapping["title_ref"])
    if not isinstance(title, str) or not title:
        raise SemanticCompilerError("mapping_title_missing")
    common = {
        "schema_version": "broker_header_schema_mapping_batch_v0",
        "logical_table_id": mapping["logical_table_id"],
        "headers": headers,
    }
    return {
        "headers_only": copy.deepcopy(common),
        "title_headers": {**copy.deepcopy(common), "table_identity": {"source_ref": mapping["title_ref"], "literal": title}},
        "title_headers_rows": {
            **copy.deepcopy(common),
            "table_identity": {"source_ref": mapping["title_ref"], "literal": title},
            "representative_rows": [
                {"source_record_id": row["source_record_id"], "elements": copy.deepcopy(row["elements"])}
                for row in rows
            ],
        },
    }


def validate_mapping_response(raw: Any, *, version: str, table_id: str, header_refs: list[str], allowed_literals: set[str], expect_type: bool) -> dict[str, Any]:
    value = typed._decode(raw)
    if (
        set(value) != {"schema_version", "classifications"}
        or value.get("schema_version") != version
        or not isinstance(value.get("classifications"), list)
        or len(value["classifications"]) != 1
        or value["classifications"][0].get("assertion_id") != table_id
    ):
        raise SemanticCompilerError("mapping_response_contract_invalid")
    item = value["classifications"][0]
    expected_keys = {"assertion_id", "columns", "value_bindings"} | ({"table_type"} if expect_type else set())
    if not isinstance(item, dict) or set(item) != expected_keys:
        raise SemanticCompilerError("mapping_response_contract_invalid")
    columns = item.get("columns")
    bindings = item.get("value_bindings")
    if (
        not isinstance(columns, list)
        or [entry.get("header_ref") for entry in columns if isinstance(entry, dict)] != header_refs
        or not isinstance(bindings, list)
    ):
        raise SemanticCompilerError("mapping_response_accounting_invalid")
    roles = []
    for entry in columns:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"header_ref", "normalized_role"}
            or entry.get("normalized_role") not in NORMALIZED_ROLES
        ):
            raise SemanticCompilerError("mapping_column_invalid")
        roles.append(entry["normalized_role"])
    non_unmapped = [role for role in roles if role != "unmapped"]
    if len(non_unmapped) != len(set(non_unmapped)):
        raise SemanticCompilerError("mapping_role_duplicate")
    meanings = []
    for binding in bindings:
        if (
            not isinstance(binding, dict)
            or set(binding) != {"column_role", "source_literal", "normalized_value"}
            or binding.get("column_role") != "side"
            or binding.get("source_literal") not in allowed_literals
            or binding.get("normalized_value") not in {"PURCHASE", "DISPOSAL"}
        ):
            raise SemanticCompilerError("mapping_value_binding_invalid")
        meanings.append(binding["normalized_value"])
    if len(meanings) != len(set(meanings)):
        raise SemanticCompilerError("mapping_value_binding_duplicate")
    restored = copy.deepcopy(item)
    if expect_type and restored.get("table_type") not in TABLE_TYPES:
        raise SemanticCompilerError("mapping_table_type_invalid")
    return restored


def validate_type_response(raw: Any, *, table_id: str) -> dict[str, str]:
    value = typed._decode(raw)
    if (
        set(value) != {"schema_version", "classifications"}
        or value.get("schema_version") != TABLE_TYPE_RESPONSE_VERSION
        or not isinstance(value.get("classifications"), list)
        or len(value["classifications"]) != 1
    ):
        raise SemanticCompilerError("table_type_response_invalid")
    item = value["classifications"][0]
    if (
        not isinstance(item, dict)
        or set(item) != {"assertion_id", "table_type"}
        or item.get("assertion_id") != table_id
        or item.get("table_type") not in TABLE_TYPES
    ):
        raise SemanticCompilerError("table_type_response_invalid")
    return copy.deepcopy(item)


def expected_side_bindings(
    *,
    mapping_truth: dict[str, Any],
    context: dict[str, Any],
    source_truth: dict[str, Any],
) -> list[dict[str, str]]:
    side_header_ref = next(
        item["header_ref"]
        for item in mapping_truth["columns"]
        if item["normalized_role"] == "side"
    )
    side_column = next(
        item["column"]
        for item in context["headers"]
        if item["source_ref"] == side_header_ref
    )
    truth_by_id = {
        item["source_record_id"]: item
        for item in source_truth["source_records"]
    }
    bindings = []
    for row in context["representative_rows"]:
        record_types = {
            record["record_type"]
            for record in truth_by_id[row["source_record_id"]]["expected_records"]
        }
        meanings = {
            "PURCHASE"
            for record_type in record_types
            if record_type == "SECURITY_PURCHASE"
        } | {
            "DISPOSAL"
            for record_type in record_types
            if record_type == "SECURITY_DISPOSAL"
        }
        if len(meanings) != 1:
            raise SemanticCompilerError("side_binding_truth_ambiguous")
        literal = next(
            item["literal"]
            for item in row["elements"]
            if item["column"] == side_column
        )
        bindings.append(
            {
                "column_role": "side",
                "source_literal": literal,
                "normalized_value": meanings.pop(),
            }
        )
    if {item["normalized_value"] for item in bindings} != {"PURCHASE", "DISPOSAL"}:
        raise SemanticCompilerError("side_binding_truth_incomplete")
    return bindings


def score_mapping(
    *,
    mapping: dict[str, Any],
    truth: dict[str, Any],
    expected_value_bindings: list[dict[str, str]],
    expect_value_bindings: bool,
) -> dict[str, Any]:
    expected = {
        "assertion_id": truth["logical_table_id"],
        "table_type": truth["table_type"],
        "columns": truth["columns"],
        "value_bindings": copy.deepcopy(expected_value_bindings) if expect_value_bindings else [],
    }
    actual = copy.deepcopy(mapping)
    actual["value_bindings"] = sorted(actual["value_bindings"], key=lambda item: item["normalized_value"])
    expected["value_bindings"] = sorted(expected["value_bindings"], key=lambda item: item["normalized_value"])
    return {
        "mapping_sha256": typed._stable_sha256(actual),
        "table_type_correct": actual["table_type"] == expected["table_type"],
        "columns_correct": sum(
            left == right for left, right in zip(actual["columns"], expected["columns"], strict=True)
        ),
        "columns_total": len(expected["columns"]),
        "columns_exact": actual["columns"] == expected["columns"],
        "value_bindings_exact": actual["value_bindings"] == expected["value_bindings"],
        "full_mapping_exact": actual == expected,
    }


def build_residual_batch(*, source_batch: dict[str, Any], semantic_truth: dict[str, Any]) -> dict[str, Any]:
    by_id = {item["source_record_id"]: item for item in source_batch["source_records"]}
    mappings = {item["logical_table_id"]: item for item in semantic_truth["schema_mappings"]}
    result = []
    for spec in semantic_truth["residuals"]:
        row = by_id[spec["source_record_id"]]
        literal_by_ref = {item["source_ref"]: item["literal"] for item in row["elements"]}
        wording = literal_by_ref.get(spec["wording_ref"])
        if not isinstance(wording, str) or not wording:
            raise SemanticCompilerError("residual_wording_missing")
        if (
            spec["expected_asset_span"] not in wording
            or spec["expected_currency_span"] not in wording
        ):
            raise SemanticCompilerError("residual_truth_span_invalid")
        result.append(
            {
                "source_record_id": spec["source_record_id"],
                "table_type": mappings[row["logical_table_id"]]["table_type"],
                "source_wording_ref": spec["wording_ref"],
                "source_wording": wording,
            }
        )
    return {"schema_version": "broker_closed_residual_batch_v0", "records": result}


def validate_residual_response(raw: Any, *, residual_batch: dict[str, Any]) -> dict[str, Any]:
    value = typed._decode(raw)
    expected_ids = [item["source_record_id"] for item in residual_batch["records"]]
    if (
        set(value) != {"schema_version", "classifications"}
        or value.get("schema_version") != RESIDUAL_RESPONSE_VERSION
        or not isinstance(value.get("classifications"), list)
        or [item.get("assertion_id") for item in value["classifications"] if isinstance(item, dict)] != expected_ids
    ):
        raise SemanticCompilerError("residual_response_accounting_invalid")
    input_by_id = {item["source_record_id"]: item for item in residual_batch["records"]}
    restored = []
    for item in value["classifications"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"assertion_id", "codes", "asset_span", "currency_span"}
            or not isinstance(item.get("codes"), list)
            or not item["codes"]
            or any(code not in RESIDUAL_CODES for code in item["codes"])
            or len(item["codes"]) != len(set(item["codes"]))
            or not isinstance(item.get("asset_span"), str)
            or not isinstance(item.get("currency_span"), str)
        ):
            raise SemanticCompilerError("residual_response_contract_invalid")
        wording = input_by_id[item["assertion_id"]]["source_wording"]
        if item["asset_span"] not in wording or item["currency_span"] not in wording:
            raise SemanticCompilerError("residual_span_invented")
        if "COUPON_PAYMENT" not in item["codes"] and item["asset_span"]:
            raise SemanticCompilerError("residual_asset_span_unowned")
        catalog_order = [code for code in RESIDUAL_CODES if code in item["codes"]]
        if item["codes"] != catalog_order:
            raise SemanticCompilerError("residual_code_order_invalid")
        table_type = input_by_id[item["assertion_id"]]["table_type"]
        allowed_by_table = {
            "CASH_OPERATIONS": {"COMMISSION_ENTRY", "NOT_RELEVANT", "UNMAPPED"},
            "SECURITY_TRADES": {"TRADE_REGISTER_TOTAL", "NOT_RELEVANT", "UNMAPPED"},
            "INCOME_PAYMENTS": {
                "COUPON_PAYMENT",
                "WITHHOLDING_STATED",
                "NOT_RELEVANT",
                "UNMAPPED",
            },
            "UNMAPPED": {"UNMAPPED"},
        }
        if not set(item["codes"]) <= allowed_by_table[table_type]:
            raise SemanticCompilerError("residual_code_incompatible_with_table")
        if ({"NOT_RELEVANT", "UNMAPPED"} & set(item["codes"])) and len(item["codes"]) != 1:
            raise SemanticCompilerError("residual_terminal_code_mixed")
        restored.append(copy.deepcopy(item))
    return {"schema_version": RESIDUAL_RESPONSE_VERSION, "classifications": restored}


def score_residual(*, response: dict[str, Any], semantic_truth: dict[str, Any]) -> dict[str, Any]:
    expected = {
        item["source_record_id"]: {
            "codes": item["expected_codes"],
            "asset_span": item["expected_asset_span"],
            "currency_span": item["expected_currency_span"],
        }
        for item in semantic_truth["residuals"]
    }
    actual = {
        item["assertion_id"]: {
            "codes": item["codes"],
            "asset_span": item["asset_span"],
            "currency_span": item["currency_span"],
        }
        for item in response["classifications"]
    }
    return {
        "projection_sha256": typed._stable_sha256(actual),
        "records_correct": sum(actual[key] == expected[key] for key in expected),
        "records_total": len(expected),
        "exact": actual == expected,
        "codes_correct": sum(actual[key]["codes"] == expected[key]["codes"] for key in expected),
        "asset_spans_correct": sum(actual[key]["asset_span"] == expected[key]["asset_span"] for key in expected),
        "currency_spans_correct": sum(actual[key]["currency_span"] == expected[key]["currency_span"] for key in expected),
    }


def deterministic_trade_projection(*, source_batch: dict[str, Any], mapping: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selected = [
        item
        for item in source_batch["source_records"]
        if item["source_record_id"] in {"r004", "r005", "r006"}
    ]
    header_column = {item["source_ref"]: item["column"] for item in selected[0]["header_context"]}
    column_by_role = {
        item["normalized_role"]: header_column[item["header_ref"]]
        for item in mapping["columns"]
    }
    side_by_literal = {
        item["source_literal"]: item["normalized_value"]
        for item in mapping["value_bindings"]
    }
    required = {
        "trade_date",
        "asset_name",
        "currency",
        "side",
        "quantity",
        "unit_price",
        "gross_amount",
        "accrued_interest",
        "broker_commission",
        "exchange_commission",
    }
    if not required <= set(column_by_role) or set(side_by_literal.values()) != {"PURCHASE", "DISPOSAL"}:
        raise SemanticCompilerError("deterministic_mapping_incomplete")
    source_events = []
    classifications = []
    for row in selected:
        cells = {item["column"]: item for item in row["elements"]}
        side_cell = cells[column_by_role["side"]]
        if side_cell["literal"] not in side_by_literal:
            raise SemanticCompilerError("deterministic_side_unmapped")
        fields = [
            {
                "field": role,
                "literal": cells[column]["literal"],
                "source_ref": cells[column]["source_ref"],
            }
            for role, column in sorted(column_by_role.items())
        ]
        event = {
            "source_record_id": row["source_record_id"],
            "event_type": "SECURITY_TRADE",
            "side": side_by_literal[side_cell["literal"]],
            "fields": fields,
            "source_identity": copy.deepcopy(row["source_identity"]),
        }
        event["event_id"] = "bse_" + typed._stable_sha256(event)[:32]
        source_events.append(event)
        classifications.append(_expand_trade_event(row=row, event=event))
    return (
        {"schema_version": typed.RESPONSE_SCHEMA_VERSION, "classifications": classifications},
        source_events,
    )


def _expand_trade_event(*, row: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    fields = {item["field"]: item for item in event["fields"]}
    def role(name: str, field: str) -> dict[str, str]:
        item = fields[field]
        return {"role": name, "source_ref": item["source_ref"], "literal_fragment": item["literal"]}
    records = [
        {
            "record_type": "SECURITY_PURCHASE" if event["side"] == "PURCHASE" else "SECURITY_DISPOSAL",
            "claim_refs": [fields["side"]["source_ref"], fields["gross_amount"]["source_ref"]],
            "roles": [
                role("date", "trade_date"),
                role("asset", "asset_name"),
                role("quantity", "quantity"),
                role("unit_price", "unit_price"),
                role("amount", "gross_amount"),
                role("currency", "currency"),
            ],
            "withholding_status": "NOT_APPLICABLE",
        }
    ]
    for field_name, record_type in (
        ("accrued_interest", "ACCRUED_COUPON_COMPONENT"),
        ("broker_commission", "TRANSACTION_CHARGE"),
        ("exchange_commission", "TRANSACTION_CHARGE"),
    ):
        item = fields[field_name]
        if typed._is_zero_literal(item["literal"]):
            continue
        roles = [role("amount", field_name), role("currency", "currency")]
        if record_type == "TRANSACTION_CHARGE":
            roles.extend([role("date", "trade_date"), role("asset", "asset_name")])
        records.append(
            {
                "record_type": record_type,
                "claim_refs": [item["source_ref"]],
                "roles": roles,
                "withholding_status": "NOT_APPLICABLE",
            }
        )
    raw = {
        "schema_version": typed.RESPONSE_SCHEMA_VERSION,
        "classifications": [
            {"assertion_id": row["source_record_id"], "disposition": "MATERIALIZED", "typed_records": records}
        ],
    }
    one = {"schema_version": "broker_typed_projection_batch_v0", "source_records": [row]}
    return typed.validate_typed_response(raw, batch=one)["classifications"][0]


def materialize_residuals(*, response: dict[str, Any], source_batch: dict[str, Any], semantic_truth: dict[str, Any]) -> dict[str, Any]:
    rows = {item["source_record_id"]: item for item in source_batch["source_records"]}
    mappings = {item["logical_table_id"]: item for item in semantic_truth["schema_mappings"]}
    wording_ref = {item["source_record_id"]: item["wording_ref"] for item in semantic_truth["residuals"]}
    classifications = []
    for decision in response["classifications"]:
        row = rows[decision["assertion_id"]]
        cells_by_column = {item["column"]: item for item in row["elements"]}
        header_column = {item["source_ref"]: item["column"] for item in row["header_context"]}
        columns = {
            item["normalized_role"]: header_column[item["header_ref"]]
            for item in mappings[row["logical_table_id"]]["columns"]
        }
        def cell(field: str) -> dict[str, Any]:
            return cells_by_column[columns[field]]
        def role(name: str, field: str) -> dict[str, str]:
            item = cell(field)
            return {"role": name, "source_ref": item["source_ref"], "literal_fragment": item["literal"]}
        records = []
        source_wording_ref = wording_ref[row["source_record_id"]]
        codes = decision["codes"]
        if codes == ["NOT_RELEVANT"] or codes == ["UNMAPPED"]:
            disposition = "NOT_RELEVANT" if codes == ["NOT_RELEVANT"] else "UNMAPPED"
        else:
            disposition = "MATERIALIZED"
            if "COMMISSION_ENTRY" in codes:
                amount_candidates = [cell("credit_amount"), cell("debit_amount")]
                nonzero = [item for item in amount_candidates if not typed._is_zero_literal(item["literal"])]
                if len(nonzero) != 1:
                    raise SemanticCompilerError("residual_commission_amount_ambiguous")
                amount = nonzero[0]
                records.append(
                    {
                        "record_type": "COMMISSION",
                        "claim_refs": [source_wording_ref, amount["source_ref"]],
                        "roles": [
                            role("date", "event_date"),
                            {"role": "amount", "source_ref": amount["source_ref"], "literal_fragment": amount["literal"]},
                            role("currency", "currency"),
                        ],
                        "withholding_status": "NOT_APPLICABLE",
                    }
                )
            if "TRADE_REGISTER_TOTAL" in codes:
                if not decision["currency_span"]:
                    raise SemanticCompilerError("residual_total_currency_missing")
                for field in ("broker_commission", "exchange_commission"):
                    amount = cell(field)
                    if typed._is_zero_literal(amount["literal"]):
                        continue
                    records.append(
                        {
                            "record_type": "COMMISSION_TOTAL",
                            "claim_refs": [amount["source_ref"]],
                            "roles": [
                                {"role": "amount", "source_ref": amount["source_ref"], "literal_fragment": amount["literal"]},
                                {"role": "currency", "source_ref": source_wording_ref, "literal_fragment": decision["currency_span"]},
                            ],
                            "withholding_status": "NOT_APPLICABLE",
                        }
                    )
            if "COUPON_PAYMENT" in codes:
                if not decision["asset_span"]:
                    raise SemanticCompilerError("residual_coupon_asset_missing")
                records.append(
                    {
                        "record_type": "COUPON_INCOME",
                        "claim_refs": [source_wording_ref, cell("amount")["source_ref"]],
                        "roles": [
                            role("date", "event_date"),
                            {"role": "asset", "source_ref": source_wording_ref, "literal_fragment": decision["asset_span"]},
                            role("amount", "amount"),
                            role("currency", "currency"),
                        ],
                        "withholding_status": "NOT_APPLICABLE",
                    }
                )
            if "WITHHOLDING_STATED" in codes:
                records.append(
                    {
                        "record_type": "TAX_WITHHELD",
                        "claim_refs": [source_wording_ref],
                        "roles": [
                            role("date", "event_date"),
                            {"role": "asset", "source_ref": source_wording_ref, "literal_fragment": decision["asset_span"]},
                            role("currency", "currency"),
                        ],
                        "withholding_status": "STATED_WITHOUT_AMOUNT",
                    }
                )
        raw = {
            "schema_version": typed.RESPONSE_SCHEMA_VERSION,
            "classifications": [
                {"assertion_id": row["source_record_id"], "disposition": disposition, "typed_records": records}
            ],
        }
        one = {"schema_version": "broker_typed_projection_batch_v0", "source_records": [row]}
        classifications.extend(typed.validate_typed_response(raw, batch=one)["classifications"])
    return {"schema_version": typed.RESPONSE_SCHEMA_VERSION, "classifications": classifications}


def merge_projection(*, source_batch: dict[str, Any], trade: dict[str, Any], residual: dict[str, Any]) -> dict[str, Any]:
    combined = {
        item["assertion_id"]: copy.deepcopy(item)
        for item in [*trade["classifications"], *residual["classifications"]]
    }
    ordered = [combined[item["source_record_id"]] for item in source_batch["source_records"]]
    typed._assert_source_accounting(ordered, input_count=len(source_batch["source_records"]))
    return {"schema_version": typed.RESPONSE_SCHEMA_VERSION, "classifications": ordered}


def schema_fingerprint(*, mapping: dict[str, Any], title_literal: str, headers: list[dict[str, Any]], continuation_columns: int) -> str:
    material = {
        "table_type": mapping["table_type"],
        "table_identity": title_literal,
        "headers": [
            {"column": item["column"], "literal": item["literal"]}
            for item in headers
        ],
        "column_count": len(headers),
        "continuation_columns": continuation_columns,
    }
    return typed._stable_sha256(material)


def fingerprint_probe(*, mapping: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    headers = context["headers"]
    title = context["table_identity"]["literal"]
    base = schema_fingerprint(mapping=mapping, title_literal=title, headers=headers, continuation_columns=len(headers))
    renamed = copy.deepcopy(headers)
    renamed[0]["literal"] += " changed"
    reordered = copy.deepcopy(headers)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    shortened = copy.deepcopy(headers[:-1])
    changed_context = title + " changed"
    mutations = {
        "renamed_header": schema_fingerprint(mapping=mapping, title_literal=title, headers=renamed, continuation_columns=len(headers)),
        "reordered_headers": schema_fingerprint(mapping=mapping, title_literal=title, headers=reordered, continuation_columns=len(headers)),
        "column_removed": schema_fingerprint(mapping=mapping, title_literal=title, headers=shortened, continuation_columns=len(shortened)),
        "table_identity_changed": schema_fingerprint(mapping=mapping, title_literal=changed_context, headers=headers, continuation_columns=len(headers)),
        "continuation_contract_changed": schema_fingerprint(mapping=mapping, title_literal=title, headers=headers, continuation_columns=len(headers) - 1),
    }
    return {
        "exact_reuse": schema_fingerprint(mapping=mapping, title_literal=title, headers=copy.deepcopy(headers), continuation_columns=len(headers)) == base,
        "mutations_rejected": sum(value != base for value in mutations.values()),
        "mutations_total": len(mutations),
        "fingerprint_sha256": base,
    }


def summarize_runs(runs: list[dict[str, Any]], *, hash_key: str, exact_key: str) -> dict[str, Any]:
    valid = [item for item in runs if item["terminal_status"] == "validated"]
    hashes = [item[hash_key] for item in valid]
    safe_runs = []
    for item in runs:
        safe = {key: copy.deepcopy(value) for key, value in item.items() if key != "execution"}
        execution = item.get("execution")
        if isinstance(execution, dict):
            safe["provider_calls"] = execution.get("provider_calls")
            safe["input_tokens"] = execution.get("input_tokens")
            safe["output_tokens"] = execution.get("output_tokens")
            safe["duration_ms"] = execution.get("duration_ms")
        safe_runs.append(safe)
    return {
        "runs": safe_runs,
        "validated_runs": len(valid),
        "unique_hashes": len(set(hashes)),
        "exact_repeatability": len(valid) == RUNS and len(set(hashes)) == 1,
        "exact_correct": len(valid) == RUNS and all(item[exact_key] for item in valid),
    }


def persisted_execution_accounting(private_runs: list[dict[str, Any]]) -> dict[str, Any]:
    executions = []
    for private_run in private_runs:
        for evidence in private_run.get("mappings", {}).values():
            execution = evidence.get("execution") if isinstance(evidence, dict) else None
            if isinstance(execution, dict):
                executions.append(execution)
            elif isinstance(execution, list):
                executions.extend(item for item in execution if isinstance(item, dict))
        residual = private_run.get("residual")
        if isinstance(residual, dict) and isinstance(residual.get("execution"), dict):
            executions.append(residual["execution"])
    return {
        "provider_calls_total": RUNS * 6,
        "calls_with_persisted_usage": len(executions),
        "calls_without_persisted_usage": RUNS * 6 - len(executions),
        "known_input_tokens_lower_bound": sum(item.get("input_tokens") or 0 for item in executions),
        "known_output_tokens_lower_bound": sum(item.get("output_tokens") or 0 for item in executions),
        "known_duration_ms_lower_bound": sum(item.get("duration_ms") or 0 for item in executions),
        "money_cost_available": False,
    }


def choose_terminal(*, mapping_summary: dict[str, Any], residual_summary: dict[str, Any], final_runs: list[dict[str, Any]], deterministic_control: dict[str, Any]) -> str:
    final_valid = [item for item in final_runs if item["terminal_status"] == "validated"]
    final_repeatable = len(final_valid) == RUNS and len({item["projection_sha256"] for item in final_valid}) == 1
    final_faithful = len(final_valid) == RUNS and all(item["source_fidelity_exact"] for item in final_valid)
    if (
        mapping_summary["exact_repeatability"]
        and mapping_summary["exact_correct"]
        and residual_summary["exact_repeatability"]
        and residual_summary["exact_correct"]
        and final_repeatable
        and final_faithful
        and deterministic_control["source_fidelity_exact"]
    ):
        return "SCHEMA_MAPPING_PLUS_DETERMINISTIC_MATERIALIZATION_PREFERRED"
    if deterministic_control["source_fidelity_exact"] and residual_summary["exact_correct"]:
        return "MINIMAL_SEMANTIC_COMPILER_PROVEN"
    return "NO_STABLE_SEMANTIC_BOUNDARY_FOUND"


def _safe_error(ordinal: int, exc: Exception, calls: int) -> dict[str, Any]:
    return {"ordinal": ordinal, "terminal_status": "rejected", "error_type": type(exc).__name__, "provider_calls": calls}


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
        raise SystemExit("explicit_execute_flag_required")
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
    if not args.rescore_existing and results_dir.exists() and any(results_dir.iterdir()):
        raise SystemExit("private_results_must_be_new_or_empty")
    if args.rescore_existing and not all(
        (results_dir / f"run-{ordinal}.private.json").is_file()
        for ordinal in range(1, RUNS + 1)
    ):
        raise SystemExit("stored_private_runs_missing")
    results_dir.mkdir(parents=True, exist_ok=True)

    source_truth_raw = args.private_source_truth.resolve().read_bytes()
    semantic_truth_raw = args.private_semantic_truth.resolve().read_bytes()
    source_truth = typed._validated_truth(json.loads(source_truth_raw))
    semantic_truth = validate_semantic_truth(json.loads(semantic_truth_raw))
    store_root = args.private_store_root.resolve()
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    document_id, context = typed._frozen_context(store_root)
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=document_id,
        context=context,
    )
    if (
        len(chunk_set["chunks"]) != 1
        or chunk_set["coverage"]["eligible_targets"] != EXPECTED_CURRENT_TARGETS
        or chunk_set["coverage"]["lost_targets"] != 0
        or chunk_set["coverage"]["duplicated_working_targets"] != 0
    ):
        raise SystemExit("frozen_canonical_seam_changed")
    chunk = chunk_set["chunks"][0]
    source_batch = typed.build_batch(chunk=chunk, truth=source_truth)
    contexts = build_contexts(chunk=chunk, source_batch=source_batch, semantic_truth=semantic_truth)
    mapping_truth = next(
        item
        for item in semantic_truth["schema_mappings"]
        if item["logical_table_id"] == semantic_truth["mapping_benchmark_table_id"]
    )
    table_id = mapping_truth["logical_table_id"]
    expected_value_bindings = expected_side_bindings(
        mapping_truth=mapping_truth,
        context=contexts["title_headers_rows"],
        source_truth=source_truth,
    )
    header_refs = [item["header_ref"] for item in mapping_truth["columns"]]
    mapping_schema_value = mapping_schema(table_id=table_id, header_refs=header_refs)
    type_schema_value = table_type_schema(table_id=table_id)
    column_schema_value = column_schema(table_id=table_id, header_refs=header_refs)
    catalog = {"table_types": list(TABLE_TYPES), "normalized_roles": ROLE_CATALOG}
    mapping_requests = {
        variant: typed._model_request(
            instruction=MAPPING_INSTRUCTION,
            contract=catalog,
            batch=context_batch,
            schema=mapping_schema_value,
            name=MAPPING_RESPONSE_VERSION,
        )
        for variant, context_batch in contexts.items()
    }
    type_request = typed._model_request(
        instruction=TYPE_INSTRUCTION,
        contract={"table_types": list(TABLE_TYPES)},
        batch=contexts["title_headers_rows"],
        schema=type_schema_value,
        name=TABLE_TYPE_RESPONSE_VERSION,
    )
    residual_batch = build_residual_batch(source_batch=source_batch, semantic_truth=semantic_truth)
    residual_ids = [item["source_record_id"] for item in residual_batch["records"]]
    residual_schema_value = residual_schema(residual_ids)
    residual_request = typed._model_request(
        instruction=RESIDUAL_INSTRUCTION,
        contract={"codes": list(RESIDUAL_CODES)},
        batch=residual_batch,
        schema=residual_schema_value,
        name=RESIDUAL_RESPONSE_VERSION,
    )
    plan = {
        "schema_version": "broker_minimal_semantic_compiler_plan_v0",
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_truth_sha256": hashlib.sha256(source_truth_raw).hexdigest(),
        "semantic_truth_sha256": hashlib.sha256(semantic_truth_raw).hexdigest(),
        "mapping_contexts": contexts,
        "mapping_requests": mapping_requests,
        "split_type_request": type_request,
        "residual_request": residual_request,
        "runs": RUNS,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "production_activation": False,
    }
    if args.rescore_existing:
        stored_plan = typed._read_json(results_dir / "frozen-plan.private.json")
        if typed._stable_sha256(stored_plan) != typed._stable_sha256(plan):
            raise SystemExit("stored_plan_changed")
        submissions = {"count": 0}
    else:
        typed._atomic_write(results_dir / "frozen-plan.private.json", typed._json_bytes(plan))
        typed.model_clients_module.GATE3_OPERATIONAL_RETRY_LIMIT = 0
        client, submissions = typed._live_client(
            env_file=args.env_file,
            timeout_seconds=args.timeout_seconds,
        )
    mapping_runs = {variant: [] for variant in (*CONTEXT_VARIANTS, "split_type_columns")}
    residual_runs = []
    final_runs = []
    private_runs = []

    if args.rescore_existing:
        for ordinal in range(1, RUNS + 1):
            private_run = typed._read_json(results_dir / f"run-{ordinal}.private.json")
            for variant in (*CONTEXT_VARIANTS, "split_type_columns"):
                evidence = private_run.get("mappings", {}).get(variant)
                if not isinstance(evidence, dict) or not isinstance(evidence.get("mapping"), dict):
                    mapping_runs[variant].append(
                        {
                            "ordinal": ordinal,
                            "terminal_status": "rejected",
                            "error_type": str((evidence or {}).get("error_type") or "StoredEvidenceUnavailable"),
                            "provider_calls": 0,
                        }
                    )
                    continue
                literals = {
                    entry["literal"]
                    for row in contexts["title_headers_rows" if variant == "split_type_columns" else variant].get(
                        "representative_rows", []
                    )
                    for entry in row["elements"]
                }
                try:
                    mapping = validate_mapping_response(
                        {
                            "schema_version": (
                                COLUMN_RESPONSE_VERSION if variant == "split_type_columns" else MAPPING_RESPONSE_VERSION
                            ),
                            "classifications": [
                                (
                                    {key: value for key, value in evidence["mapping"].items() if key != "table_type"}
                                    if variant == "split_type_columns"
                                    else evidence["mapping"]
                                )
                            ],
                        },
                        version=(COLUMN_RESPONSE_VERSION if variant == "split_type_columns" else MAPPING_RESPONSE_VERSION),
                        table_id=table_id,
                        header_refs=header_refs,
                        allowed_literals=literals,
                        expect_type=variant != "split_type_columns",
                    )
                    if variant == "split_type_columns":
                        mapping = {"assertion_id": table_id, "table_type": evidence["mapping"]["table_type"], **mapping}
                    score = score_mapping(
                        mapping=mapping,
                        truth=mapping_truth,
                        expected_value_bindings=expected_value_bindings,
                        expect_value_bindings=variant in {"title_headers_rows", "split_type_columns"},
                    )
                    mapping_runs[variant].append(
                        {"ordinal": ordinal, "terminal_status": "validated", **score, "execution": evidence.get("execution")}
                    )
                except Exception as exc:
                    mapping_runs[variant].append(_safe_error(ordinal, exc, 0))
            residual_evidence = private_run.get("residual")
            try:
                if not isinstance(residual_evidence, dict) or not isinstance(residual_evidence.get("response"), dict):
                    raise SemanticCompilerError("stored_residual_unavailable")
                residual = validate_residual_response(
                    residual_evidence["response"],
                    residual_batch=residual_batch,
                )
                score = score_residual(response=residual, semantic_truth=semantic_truth)
                residual_runs.append(
                    {
                        "ordinal": ordinal,
                        "terminal_status": "validated",
                        **score,
                        "execution": residual_evidence.get("execution"),
                    }
                )
            except Exception as exc:
                residual_runs.append(_safe_error(ordinal, exc, 0))
            private_runs.append(private_run)

    for ordinal in (() if args.rescore_existing else range(1, RUNS + 1)):
        private_run: dict[str, Any] = {"ordinal": ordinal, "mappings": {}}
        for variant in CONTEXT_VARIANTS:
            before = submissions["count"]
            result = None
            try:
                result = asyncio.run(
                    client.label_gate3_once(
                        model_visible_request=mapping_requests[variant],
                        canonical_schema=mapping_schema_value,
                        model_id=NDFL_PROVIDER_MODEL_ID,
                    )
                )
                calls = submissions["count"] - before
                literals = {
                    entry["literal"]
                    for row in contexts[variant].get("representative_rows", [])
                    for entry in row["elements"]
                }
                mapping = validate_mapping_response(
                    result.adapter_extracted_output,
                    version=MAPPING_RESPONSE_VERSION,
                    table_id=table_id,
                    header_refs=header_refs,
                    allowed_literals=literals,
                    expect_type=True,
                )
                score = score_mapping(
                    mapping=mapping,
                    truth=mapping_truth,
                    expected_value_bindings=expected_value_bindings,
                    expect_value_bindings=variant == "title_headers_rows",
                )
                execution = typed._execution_metrics(result, provider_calls=calls)
                run = {"ordinal": ordinal, "terminal_status": "validated", **score, "execution": execution}
                mapping_runs[variant].append(run)
                private_run["mappings"][variant] = {
                    "mapping": mapping,
                    "raw_model_output": copy.deepcopy(result.adapter_extracted_output),
                    "raw_provider_response": copy.deepcopy(result.raw_provider_response),
                    "execution": execution,
                }
            except Exception as exc:
                mapping_runs[variant].append(_safe_error(ordinal, exc, submissions["count"] - before))
                private_run["mappings"][variant] = {
                    "rejected": True,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "raw_model_output": copy.deepcopy(result.adapter_extracted_output) if result is not None else None,
                    "raw_provider_response": copy.deepcopy(result.raw_provider_response) if result is not None else None,
                }

        before_split = submissions["count"]
        type_result = None
        column_result = None
        try:
            type_result = asyncio.run(
                client.label_gate3_once(
                    model_visible_request=type_request,
                    canonical_schema=type_schema_value,
                    model_id=NDFL_PROVIDER_MODEL_ID,
                )
            )
            type_calls = submissions["count"] - before_split
            type_value = validate_type_response(type_result.adapter_extracted_output, table_id=table_id)
            type_execution = typed._execution_metrics(type_result, provider_calls=type_calls)
            column_batch = copy.deepcopy(contexts["title_headers_rows"])
            column_batch["frozen_table_type"] = type_value["table_type"]
            column_request = typed._model_request(
                instruction=COLUMN_INSTRUCTION,
                contract={"normalized_roles": ROLE_CATALOG},
                batch=column_batch,
                schema=column_schema_value,
                name=COLUMN_RESPONSE_VERSION,
            )
            before_columns = submissions["count"]
            column_result = asyncio.run(
                client.label_gate3_once(
                    model_visible_request=column_request,
                    canonical_schema=column_schema_value,
                    model_id=NDFL_PROVIDER_MODEL_ID,
                )
            )
            column_calls = submissions["count"] - before_columns
            literals = {
                entry["literal"]
                for row in contexts["title_headers_rows"]["representative_rows"]
                for entry in row["elements"]
            }
            column_value = validate_mapping_response(
                column_result.adapter_extracted_output,
                version=COLUMN_RESPONSE_VERSION,
                table_id=table_id,
                header_refs=header_refs,
                allowed_literals=literals,
                expect_type=False,
            )
            mapping = {"assertion_id": table_id, "table_type": type_value["table_type"], **column_value}
            score = score_mapping(
                mapping=mapping,
                truth=mapping_truth,
                expected_value_bindings=expected_value_bindings,
                expect_value_bindings=True,
            )
            column_execution = typed._execution_metrics(column_result, provider_calls=column_calls)
            run = {
                "ordinal": ordinal,
                "terminal_status": "validated",
                **score,
                "provider_calls": type_calls + column_calls,
                "input_tokens": (type_execution.get("input_tokens") or 0) + (column_execution.get("input_tokens") or 0),
                "output_tokens": (type_execution.get("output_tokens") or 0) + (column_execution.get("output_tokens") or 0),
            }
            mapping_runs["split_type_columns"].append(run)
            private_run["mappings"]["split_type_columns"] = {
                "mapping": mapping,
                "type_request": type_request,
                "column_request": column_request,
                "type_raw_model_output": copy.deepcopy(type_result.adapter_extracted_output),
                "column_raw_model_output": copy.deepcopy(column_result.adapter_extracted_output),
                "type_raw_provider_response": copy.deepcopy(type_result.raw_provider_response),
                "column_raw_provider_response": copy.deepcopy(column_result.raw_provider_response),
                "execution": [type_execution, column_execution],
            }
        except Exception as exc:
            mapping_runs["split_type_columns"].append(_safe_error(ordinal, exc, submissions["count"] - before_split))
            private_run["mappings"]["split_type_columns"] = {
                "rejected": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "type_raw_model_output": copy.deepcopy(type_result.adapter_extracted_output) if type_result is not None else None,
                "column_raw_model_output": copy.deepcopy(column_result.adapter_extracted_output) if column_result is not None else None,
            }

        before_residual = submissions["count"]
        residual_result = None
        try:
            residual_result = asyncio.run(
                client.label_gate3_once(
                    model_visible_request=residual_request,
                    canonical_schema=residual_schema_value,
                    model_id=NDFL_PROVIDER_MODEL_ID,
                )
            )
            calls = submissions["count"] - before_residual
            residual = validate_residual_response(
                residual_result.adapter_extracted_output,
                residual_batch=residual_batch,
            )
            score = score_residual(response=residual, semantic_truth=semantic_truth)
            execution = typed._execution_metrics(residual_result, provider_calls=calls)
            residual_runs.append({"ordinal": ordinal, "terminal_status": "validated", **score, "execution": execution})
            private_run["residual"] = {
                "response": residual,
                "raw_model_output": copy.deepcopy(residual_result.adapter_extracted_output),
                "raw_provider_response": copy.deepcopy(residual_result.raw_provider_response),
                "execution": execution,
            }
        except Exception as exc:
            residual_runs.append(_safe_error(ordinal, exc, submissions["count"] - before_residual))
            private_run["residual"] = {
                "rejected": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "raw_model_output": copy.deepcopy(residual_result.adapter_extracted_output) if residual_result is not None else None,
                "raw_provider_response": copy.deepcopy(residual_result.raw_provider_response) if residual_result is not None else None,
            }
        typed._atomic_write(results_dir / f"run-{ordinal}.private.json", typed._json_bytes(private_run))
        private_runs.append(private_run)

    mapping_summaries = {
        variant: summarize_runs(runs, hash_key="mapping_sha256", exact_key="full_mapping_exact")
        for variant, runs in mapping_runs.items()
    }
    residual_summary = summarize_runs(
        residual_runs,
        hash_key="projection_sha256",
        exact_key="exact",
    )
    chosen_variant = next(
        (
            variant
            for variant in ("headers_only", "title_headers", "title_headers_rows", "split_type_columns")
            if mapping_summaries[variant]["exact_repeatability"]
            and mapping_summaries[variant]["exact_correct"]
        ),
        None,
    )
    full_mapping_variant = next(
        (
            variant
            for variant in ("title_headers_rows", "split_type_columns")
            if mapping_summaries[variant]["exact_repeatability"] and mapping_summaries[variant]["exact_correct"]
        ),
        None,
    )
    mapping_for_materialization = (
        next(
            private_run["mappings"][full_mapping_variant]["mapping"]
            for private_run in private_runs
            if full_mapping_variant
            and isinstance(private_run["mappings"].get(full_mapping_variant), dict)
            and isinstance(private_run["mappings"][full_mapping_variant].get("mapping"), dict)
        )
        if full_mapping_variant
        else {
            "assertion_id": table_id,
            "table_type": mapping_truth["table_type"],
            "columns": copy.deepcopy(mapping_truth["columns"]),
            "value_bindings": copy.deepcopy(expected_value_bindings),
        }
    )
    trade_projection, source_events = deterministic_trade_projection(
        source_batch=source_batch,
        mapping=mapping_for_materialization,
    )
    trade_truth = {
        **copy.deepcopy(source_truth),
        "source_records": [
            item for item in source_truth["source_records"] if item["source_record_id"] in {"r004", "r005", "r006"}
        ],
    }
    trade_batch = {
        "schema_version": source_batch["schema_version"],
        "source_records": [
            item for item in source_batch["source_records"] if item["source_record_id"] in {"r004", "r005", "r006"}
        ],
    }
    deterministic_control = typed.score_projection(
        projection=trade_projection,
        truth=trade_truth,
        batch=trade_batch,
        deterministic_source_ids={"r004", "r005", "r006"},
        execution=[],
    )
    deterministic_control["source_fidelity_exact"] = (
        deterministic_control["missing_typed_records"] == 0
        and deterministic_control["extra_typed_records"] == 0
        and deterministic_control["dispositions_correct"] == 3
    )

    for ordinal, private_run in enumerate(private_runs, 1):
        evidence = private_run.get("residual")
        residual_run = residual_runs[ordinal - 1]
        if (
            residual_run["terminal_status"] != "validated"
            or not isinstance(evidence, dict)
            or not isinstance(evidence.get("response"), dict)
        ):
            final_runs.append({"ordinal": ordinal, "terminal_status": "rejected", "error_type": "ResidualUnavailable"})
            continue
        residual_projection = materialize_residuals(
            response=evidence["response"],
            source_batch=source_batch,
            semantic_truth=semantic_truth,
        )
        projection = merge_projection(
            source_batch=source_batch,
            trade=trade_projection,
            residual=residual_projection,
        )
        metrics = typed.score_projection(
            projection=projection,
            truth=source_truth,
            batch=source_batch,
            deterministic_source_ids={"r004", "r005", "r006"},
            execution=[],
        )
        faithful = (
            metrics["missing_typed_records"] == 0
            and metrics["extra_typed_records"] == 0
            and metrics["dispositions_correct"] == len(source_batch["source_records"])
        )
        final_runs.append(
            {
                "ordinal": ordinal,
                "terminal_status": "validated",
                "projection_sha256": metrics["projection_sha256"],
                "source_fidelity_exact": faithful,
                "source_accounting_exact": metrics["source_accounting_exact"],
                "expected_typed_records": metrics["expected_typed_records"],
                "actual_typed_records": metrics["actual_typed_records"],
                "exact_typed_records_correct": metrics["exact_typed_records_correct"],
                "idempotency": metrics["idempotency"],
            }
        )
        private_run["final_projection"] = projection
        typed._atomic_write(results_dir / f"run-{ordinal}.private.json", typed._json_bytes(private_run))

    fingerprint = fingerprint_probe(
        mapping=mapping_for_materialization,
        context=contexts["title_headers_rows"],
    )
    chosen_summary = mapping_summaries[full_mapping_variant] if full_mapping_variant else {
        "exact_repeatability": False,
        "exact_correct": False,
    }
    terminal = choose_terminal(
        mapping_summary=chosen_summary,
        residual_summary=residual_summary,
        final_runs=final_runs,
        deterministic_control=deterministic_control,
    )
    expected_role_values = sum(
        len(record["roles"])
        for source in source_truth["source_records"]
        for record in source["expected_records"]
    )
    residual_semantic_decisions = sum(
        len(item["expected_codes"])
        + bool(item["expected_asset_span"])
        + bool(item["expected_currency_span"])
        for item in semantic_truth["residuals"]
    )
    prior = typed._read_json(args.prior_receipt.resolve())
    receipt = {
        "schema_version": "broker_minimal_semantic_compiler_receipt_v0",
        "status": terminal,
        "terminals": [terminal],
        "research_only": True,
        "production_changed": False,
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_records": len(source_batch["source_records"]),
        "logical_tables": len(semantic_truth["schema_mappings"]),
        "provider_profile_id": NDFL_PROVIDER_PROFILE_ID,
        "model_id": NDFL_PROVIDER_MODEL_ID,
        "runs": RUNS,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "offline_rescore": {
            "performed": args.rescore_existing,
            "provider_calls": 0 if args.rescore_existing else None,
            "reason": "enforce table-compatible residual codes after deterministic assembler fail-closed fix",
        },
        "execution_accounting": persisted_execution_accounting(private_runs),
        "mapping_variants": mapping_summaries,
        "minimum_correct_mapping_context": chosen_variant,
        "full_mapping_variant": full_mapping_variant,
        "deterministic_trade_materialization": {
            "source_records": len(source_events),
            "source_shaped_events": len(source_events),
            "expanded_gate5_facts": sum(len(item["typed_records"]) for item in trade_projection["classifications"]),
            "source_fidelity_exact": deterministic_control["source_fidelity_exact"],
            "mapping_source": "model_exact_repeatable" if full_mapping_variant else "manual_frozen_control",
        },
        "dialect_comparison": {
            "fact_centric_records": sum(len(item["typed_records"]) for item in trade_projection["classifications"]),
            "source_shaped_trade_events": len(source_events),
            "both_gate5_sufficient_after_deterministic_adapter": deterministic_control["source_fidelity_exact"],
            "source_shaped_required": False,
            "source_shaped_kiss_preferred": deterministic_control["source_fidelity_exact"],
        },
        "residual": residual_summary,
        "final_projection_runs": final_runs,
        "fingerprint_reuse": fingerprint,
        "semantic_surface_area": {
            "prior_direct_projection_decisions": len(source_batch["source_records"])
            + sum(len(item["expected_records"]) for item in source_truth["source_records"])
            + expected_role_values,
            "schema_column_decisions": sum(len(item["columns"]) for item in semantic_truth["schema_mappings"]),
            "schema_value_decisions": len(expected_value_bindings),
            "residual_semantic_decisions": residual_semantic_decisions,
            "runtime_role_values": expected_role_values,
            "runtime_role_values_bound_by_code": expected_role_values
            - sum(bool(item["expected_asset_span"]) + bool(item["expected_currency_span"]) for item in semantic_truth["residuals"]),
            "selected_source_records_without_row_llm": 3,
            "selected_source_records_with_residual_llm": len(semantic_truth["residuals"]),
        },
        "prior_direct_comparator": {
            "status": prior["status"],
            "structural_direct_exact_repeatability": prior["variants"]["A_structural_direct"]["exact_repeatability"],
            "structural_direct_unique_hashes": prior["variants"]["A_structural_direct"]["unique_projection_hashes"],
            "current_gate3_type_matches": [
                item["selected_type_matches"] for item in prior["current_gate3_frozen_baseline"]
            ],
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
