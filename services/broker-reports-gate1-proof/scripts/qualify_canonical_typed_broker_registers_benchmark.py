#!/usr/bin/env python3
"""Closed research benchmark from frozen Canonical to typed broker registers."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import sqlite3
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
import broker_reports_gate1.gate2_model_clients as model_clients_module  # noqa: E402
from broker_reports_gate1.gate3_ndfl_workflow import (  # noqa: E402
    NDFL_PROVIDER_MODEL_ID,
    NDFL_PROVIDER_PROFILE_ID,
)
from qualify_gate3_minimal_classifier_stand import (  # noqa: E402
    _atomic_write,
    _frozen_context,
    _json_bytes,
    _live_client,
    _plain,
    _read_json,
    _stable_sha256,
    _visible_text_index,
)


FROZEN_CANONICAL_ROOT_SHA256 = (
    "bbf20e4ea5cd706398d459716fdab60812ef48ed6b0cd2d0264a778a77ab079d"
)
EXPECTED_CURRENT_TARGETS = 2236
RUNS = 3
PROJECTION_SCHEMA_VERSION = "broker_source_dialect_v0"
RESPONSE_SCHEMA_VERSION = "broker_typed_projection_response_v0"
MAPPING_SCHEMA_VERSION = "broker_table_mapping_response_v0"
DISPOSITIONS = ("MATERIALIZED", "NOT_RELEVANT", "UNMAPPED", "FAILED")
RECORD_TYPES = (
    "SECURITY_PURCHASE",
    "SECURITY_DISPOSAL",
    "COUPON_INCOME",
    "ACCRUED_COUPON_COMPONENT",
    "TRANSACTION_CHARGE",
    "COMMISSION",
    "COMMISSION_TOTAL",
    "TAX_WITHHELD",
    "TAX_WITHHELD_TOTAL",
)
ROLES = ("date", "asset", "quantity", "unit_price", "amount", "currency")
TABLE_KINDS = ("SECURITY_TRADES", "CASH_OPERATIONS", "COUPON_PAYMENTS", "UNSUPPORTED")
COLUMN_ROLES = (
    "DATE",
    "ASSET",
    "SECURITY_CODE",
    "CURRENCY",
    "SIDE",
    "QUANTITY",
    "UNIT_PRICE",
    "AMOUNT",
    "ACCRUED_COUPON",
    "BROKER_COMMISSION",
    "EXCHANGE_COMMISSION",
    "DESCRIPTION",
    "CREDIT",
    "DEBIT",
)
TERMINALS = {
    "DETERMINISTIC_FIRST_BROKER_ETL_PREFERRED",
    "DIRECT_TYPED_EXTRACTION_PREFERRED",
    "NO_CANDIDATE_PROVIDES_STABLE_RUNTIME_PROJECTION",
    "BROKER_TYPED_PROJECTION_APPROACH_NOT_YET_PROVEN",
}

TYPE_ROLE_CONTRACT = {
    "SECURITY_PURCHASE": ({"date", "asset", "quantity", "amount", "currency"}, {"unit_price"}),
    "SECURITY_DISPOSAL": ({"date", "asset", "quantity", "amount", "currency"}, {"unit_price"}),
    "COUPON_INCOME": ({"date", "amount", "currency"}, {"asset"}),
    "ACCRUED_COUPON_COMPONENT": ({"amount", "currency"}, set()),
    "TRANSACTION_CHARGE": ({"date", "amount", "currency"}, {"asset"}),
    "COMMISSION": ({"amount", "currency"}, {"date", "asset"}),
    "COMMISSION_TOTAL": ({"amount", "currency"}, {"date", "asset"}),
    "TAX_WITHHELD": ({"date", "currency"}, {"amount", "asset"}),
    "TAX_WITHHELD_TOTAL": ({"amount", "currency"}, {"date", "asset"}),
}

DIRECT_INSTRUCTION = (
    "Это закрытый research-only перевод Canonical source rows в BrokerSourceDialect_v0. "
    "Верни ровно одно решение для каждого заранее объявленного source_record_id, в исходном порядке. "
    "Не пропускай строки. Используй только закрытые record_type и disposition. MATERIALIZED требует хотя "
    "бы одну typed запись; остальные disposition требуют пустой typed_records. Каждый role literal_fragment "
    "копируй verbatim из указанного source_ref; claim_refs и role source_ref могут ссылаться только на cells "
    "этой source row. Header context нужен только для понимания колонок. Не вычисляй, не объединяй похожие "
    "операции и не выводи связи. Одна строка может дать несколько source facts. Налоговые выводы запрещены. "
    "Если источник лишь говорит 'Налог удержан' без отдельной суммы, создай TAX_WITHHELD с "
    "withholding_status=STATED_WITHOUT_AMOUNT и без role amount. Верни только strict JSON."
)

MAPPING_INSTRUCTION = (
    "Это table-schema mapping, не извлечение строк. Для каждого logical_table_id верни ровно одно решение "
    "в исходном порядке. Определи только register_kind, привяжи header_ref к column_role и перечисли exact "
    "source literals Покупка/Продажа как side_markers, если они есть. Не классифицируй отдельные строки, "
    "не возвращай records, не придумывай regex/DSL и не делай налоговых выводов. Верни только strict JSON."
)


class TypedRegistersBenchmarkError(RuntimeError):
    pass


def typed_response_schema(source_record_ids: list[str], allowed_refs: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "classifications"],
        "properties": {
            "schema_version": {"const": RESPONSE_SCHEMA_VERSION},
            "classifications": {
                "type": "array",
                "minItems": len(source_record_ids),
                "maxItems": len(source_record_ids),
                "items": {"$ref": "#/$defs/classification"},
            },
        },
        "$defs": {
            "classification": {
                "type": "object",
                "additionalProperties": False,
                "required": ["assertion_id", "disposition", "typed_records"],
                "properties": {
                    "assertion_id": {
                        "type": "string",
                        "pattern": r"^r[0-9]{3}$",
                        "description": "Copy one exact source_record_id from the batch; no brackets or prose.",
                    },
                    "disposition": {"type": "string", "enum": list(DISPOSITIONS)},
                    "typed_records": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": 8,
                        "items": {"$ref": "#/$defs/typedRecord"},
                    },
                },
            },
            "typedRecord": {
                "type": "object",
                "additionalProperties": False,
                "required": ["record_type", "claim_refs", "roles", "withholding_status"],
                "properties": {
                    "record_type": {"type": "string", "enum": list(RECORD_TYPES)},
                    "claim_refs": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 16,
                        "items": {"type": "string", "enum": allowed_refs},
                    },
                    "roles": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "items": {"$ref": "#/$defs/roleBinding"},
                    },
                    "withholding_status": {
                        "type": "string",
                        "enum": ["NOT_APPLICABLE", "PRESENT", "STATED_WITHOUT_AMOUNT"],
                    },
                },
            },
            "roleBinding": {
                "type": "object",
                "additionalProperties": False,
                "required": ["role", "source_ref", "literal_fragment"],
                "properties": {
                    "role": {"type": "string", "enum": list(ROLES)},
                    "source_ref": {"type": "string", "enum": allowed_refs},
                    "literal_fragment": {"type": "string", "minLength": 1},
                },
            },
        },
    }


def mapping_response_schema(table_ids: list[str], allowed_header_refs: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "classifications"],
        "properties": {
            "schema_version": {"const": MAPPING_SCHEMA_VERSION},
            "classifications": {
                "type": "array",
                "minItems": len(table_ids),
                "maxItems": len(table_ids),
                "items": {"$ref": "#/$defs/classification"},
            },
        },
        "$defs": {
            "classification": {
                "type": "object",
                "additionalProperties": False,
                "required": ["assertion_id", "register_kind", "column_bindings", "side_markers"],
                "properties": {
                    "assertion_id": {
                        "type": "string",
                        "pattern": r"^g[0-9]{3}$",
                        "description": "Copy one exact logical_table_id from the batch; no brackets or prose.",
                    },
                    "register_kind": {"type": "string", "enum": list(TABLE_KINDS)},
                    "column_bindings": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": 16,
                        "items": {"$ref": "#/$defs/columnBinding"},
                    },
                    "side_markers": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": 4,
                        "items": {"$ref": "#/$defs/sideMarker"},
                    },
                },
            },
            "columnBinding": {
                "type": "object",
                "additionalProperties": False,
                "required": ["header_ref", "column_role"],
                "properties": {
                    "header_ref": {"type": "string", "enum": allowed_header_refs},
                    "column_role": {"type": "string", "enum": list(COLUMN_ROLES)},
                },
            },
            "sideMarker": {
                "type": "object",
                "additionalProperties": False,
                "required": ["meaning", "literal"],
                "properties": {
                    "meaning": {"type": "string", "enum": ["PURCHASE", "DISPOSAL"]},
                    "literal": {"type": "string", "minLength": 1},
                },
            },
        },
    }


def _model_request(*, instruction: str, contract: dict[str, Any], batch: dict[str, Any], schema: dict[str, Any], name: str) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": _compact_json(contract)},
            {"role": "user", "content": _compact_json({"batch": batch})},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": copy.deepcopy(schema)},
        },
    }


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _validated_truth(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "broker_typed_projection_source_truth_v0"
        or value.get("frozen_canonical_root_sha256") != FROZEN_CANONICAL_ROOT_SHA256
        or value.get("qualified_before_model_execution") is not True
        or value.get("model_output_used_as_truth_hint") is not False
        or not isinstance(value.get("source_records"), list)
        or not value["source_records"]
    ):
        raise TypedRegistersBenchmarkError("source_truth_invalid")
    ids: list[str] = []
    rows: list[str] = []
    for item in value["source_records"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"source_record_id", "row_alias", "logical_table_id", "header_refs", "expected_disposition", "expected_records"}
            or re.fullmatch(r"r[0-9]{3}", str(item.get("source_record_id") or "")) is None
            or re.fullmatch(r"t[0-9]+", str(item.get("row_alias") or "")) is None
            or re.fullmatch(r"g[0-9]{3}", str(item.get("logical_table_id") or "")) is None
            or not isinstance(item.get("header_refs"), list)
            or item.get("expected_disposition") not in DISPOSITIONS
            or not isinstance(item.get("expected_records"), list)
        ):
            raise TypedRegistersBenchmarkError("source_truth_record_invalid")
        if (item["expected_disposition"] == "MATERIALIZED") != bool(item["expected_records"]):
            raise TypedRegistersBenchmarkError("source_truth_disposition_invalid")
        ids.append(item["source_record_id"])
        rows.append(item["row_alias"])
        for record in item["expected_records"]:
            _validate_truth_record(record)
    if len(ids) != len(set(ids)) or len(rows) != len(set(rows)):
        raise TypedRegistersBenchmarkError("source_truth_identity_duplicate")
    return copy.deepcopy(value)


def _validate_truth_record(record: Any) -> None:
    if (
        not isinstance(record, dict)
        or set(record) != {"record_type", "claim_refs", "roles", "withholding_status"}
        or record.get("record_type") not in RECORD_TYPES
        or not isinstance(record.get("claim_refs"), list)
        or not record["claim_refs"]
        or not isinstance(record.get("roles"), list)
        or not record["roles"]
    ):
        raise TypedRegistersBenchmarkError("source_truth_typed_record_invalid")
    for role in record["roles"]:
        if (
            not isinstance(role, dict)
            or set(role) != {"role", "source_ref", "literal_fragment"}
            or role.get("role") not in ROLES
            or not isinstance(role.get("source_ref"), str)
            or not isinstance(role.get("literal_fragment"), str)
            or not role["literal_fragment"]
        ):
            raise TypedRegistersBenchmarkError("source_truth_role_invalid")


def build_batch(*, chunk: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    mapping_by_alias = {item["target_alias"]: item["canonical_target"] for item in chunk["target_mappings"]}
    text_by_alias, row_lines = _visible_text_index(content=chunk["model_view"]["content"], mapping_by_alias=mapping_by_alias)
    records: list[dict[str, Any]] = []
    for spec in truth["source_records"]:
        row_target = mapping_by_alias.get(spec["row_alias"])
        if not isinstance(row_target, dict) or row_target.get("kind") != "table_row":
            raise TypedRegistersBenchmarkError("source_row_missing")
        row_key = (str(row_target["node_id"]), int(row_target["row"]))
        row_aliases = [
            alias
            for alias, target in mapping_by_alias.items()
            if target.get("kind") == "table_cell"
            and target.get("node_id") == row_target["node_id"]
            and target.get("row") == row_target["row"]
        ]
        row_aliases.sort(key=lambda alias: int(mapping_by_alias[alias]["column"]))
        elements = [
            {"source_ref": alias, "column": mapping_by_alias[alias]["column"], "literal": text_by_alias.get(alias, "")}
            for alias in row_aliases
        ]
        headers = []
        for alias in spec["header_refs"]:
            target = mapping_by_alias.get(alias)
            literal = text_by_alias.get(alias)
            if not isinstance(target, dict) or target.get("kind") != "table_cell" or literal is None:
                raise TypedRegistersBenchmarkError("source_header_missing")
            headers.append({"source_ref": alias, "column": target["column"], "literal": literal})
        if row_key not in row_lines or any(not item["literal"] for item in elements if item["source_ref"] in _expected_refs(spec)):
            raise TypedRegistersBenchmarkError("source_row_content_missing")
        records.append(
            {
                "source_record_id": spec["source_record_id"],
                "logical_table_id": spec["logical_table_id"],
                "source_identity": {"canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256, **copy.deepcopy(row_target)},
                "header_context": headers,
                "elements": elements,
                "row_view": row_lines[row_key],
            }
        )
    batch = {"schema_version": "broker_typed_projection_batch_v0", "source_records": records}
    _assert_truth_literals(truth=truth, batch=batch)
    return batch


def _expected_refs(spec: dict[str, Any]) -> set[str]:
    return {
        ref
        for record in spec["expected_records"]
        for ref in [*record["claim_refs"], *(item["source_ref"] for item in record["roles"])]
    }


def _assert_truth_literals(*, truth: dict[str, Any], batch: dict[str, Any]) -> None:
    by_id = {item["source_record_id"]: item for item in batch["source_records"]}
    for spec in truth["source_records"]:
        literals = {item["source_ref"]: item["literal"] for item in by_id[spec["source_record_id"]]["elements"]}
        for record in spec["expected_records"]:
            if not set(record["claim_refs"]) <= set(literals):
                raise TypedRegistersBenchmarkError("source_truth_claim_ref_invalid")
            for role in record["roles"]:
                if role["source_ref"] not in literals or role["literal_fragment"] not in literals[role["source_ref"]]:
                    raise TypedRegistersBenchmarkError("source_truth_literal_not_exact")


def structural_batch(batch: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(batch)


def large_context_batch(*, chunk: dict[str, Any], batch: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "broker_typed_projection_large_context_batch_v0",
        "selected_source_records": [
            {"source_record_id": item["source_record_id"], "source_identity": item["source_identity"]}
            for item in batch["source_records"]
        ],
        "canonical_projection": chunk["model_view"]["content"],
    }


def table_mapping_batch(batch: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for row in batch["source_records"]:
        group = groups.setdefault(
            row["logical_table_id"],
            {
                "logical_table_id": row["logical_table_id"],
                "header_context": copy.deepcopy(row["header_context"]),
                "sample_rows": [],
            },
        )
        if group["header_context"] != row["header_context"]:
            raise TypedRegistersBenchmarkError("logical_table_header_changed")
        if len(group["sample_rows"]) < 3:
            group["sample_rows"].append(
                {
                    "source_record_id": row["source_record_id"],
                    "elements": copy.deepcopy(row["elements"]),
                }
            )
    return {"schema_version": "broker_table_mapping_batch_v0", "logical_tables": list(groups.values())}


def validate_typed_response(raw: Any, *, batch: dict[str, Any]) -> dict[str, Any]:
    value = _decode(raw)
    expected_ids = [item["source_record_id"] for item in batch["source_records"]]
    if (
        set(value) != {"schema_version", "classifications"}
        or value.get("schema_version") != RESPONSE_SCHEMA_VERSION
        or not isinstance(value.get("classifications"), list)
        or [item.get("assertion_id") for item in value["classifications"] if isinstance(item, dict)] != expected_ids
    ):
        raise TypedRegistersBenchmarkError("typed_response_accounting_invalid")
    row_by_id = {item["source_record_id"]: item for item in batch["source_records"]}
    restored: list[dict[str, Any]] = []
    for item in value["classifications"]:
        if not isinstance(item, dict) or set(item) != {"assertion_id", "disposition", "typed_records"}:
            raise TypedRegistersBenchmarkError("typed_response_contract_invalid")
        disposition = item.get("disposition")
        records = item.get("typed_records")
        if (
            disposition not in DISPOSITIONS
            or not isinstance(records, list)
            or (disposition == "MATERIALIZED") != bool(records)
        ):
            raise TypedRegistersBenchmarkError("typed_response_disposition_invalid")
        row = row_by_id[item["assertion_id"]]
        literal_by_ref = {entry["source_ref"]: entry["literal"] for entry in row["elements"]}
        validated_records = [
            _validate_materialized_record(record, literal_by_ref=literal_by_ref, source_record=row)
            for record in records
        ]
        restored.append({"assertion_id": item["assertion_id"], "disposition": disposition, "typed_records": validated_records})
    _assert_source_accounting(restored, input_count=len(expected_ids))
    return {"schema_version": RESPONSE_SCHEMA_VERSION, "classifications": restored}


def _validate_materialized_record(record: Any, *, literal_by_ref: dict[str, str], source_record: dict[str, Any]) -> dict[str, Any]:
    _validate_truth_record(record)
    if len(record["claim_refs"]) != len(set(record["claim_refs"])) or not set(record["claim_refs"]) <= set(literal_by_ref):
        raise TypedRegistersBenchmarkError("typed_record_claim_ref_invalid")
    role_names: list[str] = []
    for role in record["roles"]:
        role_names.append(role["role"])
        if role["source_ref"] not in literal_by_ref or role["literal_fragment"] not in literal_by_ref[role["source_ref"]]:
            raise TypedRegistersBenchmarkError("typed_record_invented_literal")
    if len(role_names) != len(set(role_names)):
        raise TypedRegistersBenchmarkError("typed_record_role_duplicate")
    required, optional = TYPE_ROLE_CONTRACT[record["record_type"]]
    role_set = set(role_names)
    if not required <= role_set or not role_set <= required | optional:
        raise TypedRegistersBenchmarkError("typed_record_role_contract_invalid")
    withholding = record["withholding_status"]
    if record["record_type"] != "TAX_WITHHELD" and withholding != "NOT_APPLICABLE":
        raise TypedRegistersBenchmarkError("typed_record_withholding_status_invalid")
    if record["record_type"] == "TAX_WITHHELD":
        if withholding == "STATED_WITHOUT_AMOUNT" and "amount" in role_set:
            raise TypedRegistersBenchmarkError("typed_record_withholding_amount_invented")
        if withholding == "PRESENT" and "amount" not in role_set:
            raise TypedRegistersBenchmarkError("typed_record_withholding_amount_missing")
        if withholding == "NOT_APPLICABLE":
            raise TypedRegistersBenchmarkError("typed_record_withholding_status_invalid")
    restored = copy.deepcopy(record)
    restored["claim_refs"] = sorted(restored["claim_refs"])
    restored["roles"] = sorted(restored["roles"], key=lambda item: item["role"])
    restored["typed_record_id"] = typed_record_id(source_record=source_record, record=restored)
    return restored


def typed_record_id(*, source_record: dict[str, Any], record: dict[str, Any]) -> str:
    material = {
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "logical_table_id": source_record["logical_table_id"],
        "source_identity": source_record["source_identity"],
        "record_type": record["record_type"],
        "claim_refs": sorted(record["claim_refs"]),
        "role_source_refs": sorted((item["role"], item["source_ref"]) for item in record["roles"]),
    }
    return "bsr_" + _stable_sha256(material)[:32]


def _assert_source_accounting(classifications: list[dict[str, Any]], *, input_count: int) -> None:
    counts = Counter(item["disposition"] for item in classifications)
    if len(classifications) != input_count or sum(counts.values()) != input_count:
        raise TypedRegistersBenchmarkError("source_accounting_invariant_failed")


def validate_mapping_response(raw: Any, *, mapping_batch: dict[str, Any], batch: dict[str, Any]) -> dict[str, Any]:
    value = _decode(raw)
    expected_ids = [item["logical_table_id"] for item in mapping_batch["logical_tables"]]
    if (
        set(value) != {"schema_version", "classifications"}
        or value.get("schema_version") != MAPPING_SCHEMA_VERSION
        or not isinstance(value.get("classifications"), list)
        or [item.get("assertion_id") for item in value["classifications"] if isinstance(item, dict)] != expected_ids
    ):
        raise TypedRegistersBenchmarkError("table_mapping_accounting_invalid")
    header_by_group = {
        item["logical_table_id"]: {entry["source_ref"]: entry for entry in item["header_context"]}
        for item in mapping_batch["logical_tables"]
    }
    all_literals = {
        item["logical_table_id"]: [entry["literal"] for row in batch["source_records"] if row["logical_table_id"] == item["logical_table_id"] for entry in row["elements"]]
        for item in mapping_batch["logical_tables"]
    }
    restored = []
    for item in value["classifications"]:
        if not isinstance(item, dict) or set(item) != {"assertion_id", "register_kind", "column_bindings", "side_markers"}:
            raise TypedRegistersBenchmarkError("table_mapping_contract_invalid")
        group_id = item["assertion_id"]
        bindings = item.get("column_bindings")
        markers = item.get("side_markers")
        if item.get("register_kind") not in TABLE_KINDS or not isinstance(bindings, list) or not isinstance(markers, list):
            raise TypedRegistersBenchmarkError("table_mapping_contract_invalid")
        roles: list[str] = []
        refs: list[str] = []
        for binding in bindings:
            if (
                not isinstance(binding, dict)
                or set(binding) != {"header_ref", "column_role"}
                or binding.get("header_ref") not in header_by_group[group_id]
                or binding.get("column_role") not in COLUMN_ROLES
            ):
                raise TypedRegistersBenchmarkError("table_mapping_column_invalid")
            refs.append(binding["header_ref"])
            roles.append(binding["column_role"])
        if len(refs) != len(set(refs)) or len(roles) != len(set(roles)):
            raise TypedRegistersBenchmarkError("table_mapping_column_duplicate")
        meanings: list[str] = []
        for marker in markers:
            if (
                not isinstance(marker, dict)
                or set(marker) != {"meaning", "literal"}
                or marker.get("meaning") not in {"PURCHASE", "DISPOSAL"}
                or not isinstance(marker.get("literal"), str)
                or marker["literal"] not in all_literals[group_id]
            ):
                raise TypedRegistersBenchmarkError("table_mapping_marker_invalid")
            meanings.append(marker["meaning"])
        if len(meanings) != len(set(meanings)):
            raise TypedRegistersBenchmarkError("table_mapping_marker_duplicate")
        restored.append(copy.deepcopy(item))
    return {"schema_version": MAPPING_SCHEMA_VERSION, "classifications": restored}


def deterministic_materialize(*, batch: dict[str, Any], mapping: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapping_by_group = {item["assertion_id"]: item for item in mapping["classifications"]}
    deterministic: list[dict[str, Any]] = []
    residual: list[dict[str, Any]] = []
    for row in batch["source_records"]:
        table_mapping = mapping_by_group[row["logical_table_id"]]
        if table_mapping["register_kind"] != "SECURITY_TRADES":
            residual.append(copy.deepcopy(row))
            continue
        header_by_ref = {item["source_ref"]: item for item in row["header_context"]}
        column_by_role = {
            item["column_role"]: header_by_ref[item["header_ref"]]["column"]
            for item in table_mapping["column_bindings"]
        }
        required = {"DATE", "ASSET", "CURRENCY", "SIDE", "QUANTITY", "UNIT_PRICE", "AMOUNT", "ACCRUED_COUPON", "BROKER_COMMISSION", "EXCHANGE_COMMISSION"}
        marker_by_literal = {item["literal"]: item["meaning"] for item in table_mapping["side_markers"]}
        if not required <= set(column_by_role) or set(marker_by_literal.values()) != {"PURCHASE", "DISPOSAL"}:
            residual.append(copy.deepcopy(row))
            continue
        cell_by_column = {item["column"]: item for item in row["elements"]}
        if not all(column_by_role[key] in cell_by_column for key in required):
            residual.append(copy.deepcopy(row))
            continue
        side = cell_by_column[column_by_role["SIDE"]]["literal"]
        if side not in marker_by_literal:
            residual.append(copy.deepcopy(row))
            continue
        records = [_trade_record(row=row, cell_by_column=cell_by_column, column_by_role=column_by_role, side=marker_by_literal[side])]
        for component, record_type in (
            ("ACCRUED_COUPON", "ACCRUED_COUPON_COMPONENT"),
            ("BROKER_COMMISSION", "TRANSACTION_CHARGE"),
            ("EXCHANGE_COMMISSION", "TRANSACTION_CHARGE"),
        ):
            cell = cell_by_column[column_by_role[component]]
            if _is_zero_literal(cell["literal"]):
                continue
            roles = [
                _role("amount", cell),
                _role("currency", cell_by_column[column_by_role["CURRENCY"]]),
            ]
            if record_type == "TRANSACTION_CHARGE":
                roles.extend(
                    [
                        _role("date", cell_by_column[column_by_role["DATE"]]),
                        _role("asset", cell_by_column[column_by_role["ASSET"]]),
                    ]
                )
            records.append(
                {
                    "record_type": record_type,
                    "claim_refs": [cell["source_ref"]],
                    "roles": roles,
                    "withholding_status": "NOT_APPLICABLE",
                }
            )
        raw = {
            "schema_version": RESPONSE_SCHEMA_VERSION,
            "classifications": [{"assertion_id": row["source_record_id"], "disposition": "MATERIALIZED", "typed_records": records}],
        }
        one_batch = {"schema_version": batch["schema_version"], "source_records": [row]}
        deterministic.extend(validate_typed_response(raw, batch=one_batch)["classifications"])
    return deterministic, residual


def _trade_record(*, row: dict[str, Any], cell_by_column: dict[int, dict[str, Any]], column_by_role: dict[str, int], side: str) -> dict[str, Any]:
    role_map = {
        "date": "DATE",
        "asset": "ASSET",
        "quantity": "QUANTITY",
        "unit_price": "UNIT_PRICE",
        "amount": "AMOUNT",
        "currency": "CURRENCY",
    }
    side_cell = cell_by_column[column_by_role["SIDE"]]
    return {
        "record_type": "SECURITY_PURCHASE" if side == "PURCHASE" else "SECURITY_DISPOSAL",
        "claim_refs": [side_cell["source_ref"], cell_by_column[column_by_role["AMOUNT"]]["source_ref"]],
        "roles": [_role(role, cell_by_column[column_by_role[column_role]]) for role, column_role in role_map.items()],
        "withholding_status": "NOT_APPLICABLE",
    }


def _role(role: str, cell: dict[str, Any]) -> dict[str, str]:
    return {"role": role, "source_ref": cell["source_ref"], "literal_fragment": cell["literal"]}


def _is_zero_literal(value: str) -> bool:
    normalized = value.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return float(normalized) == 0.0
    except ValueError:
        return False


def merge_deterministic_and_residual(*, batch: dict[str, Any], deterministic: list[dict[str, Any]], residual_projection: dict[str, Any]) -> dict[str, Any]:
    combined = {item["assertion_id"]: copy.deepcopy(item) for item in deterministic}
    combined.update({item["assertion_id"]: copy.deepcopy(item) for item in residual_projection["classifications"]})
    ordered = [combined[item["source_record_id"]] for item in batch["source_records"] if item["source_record_id"] in combined]
    _assert_source_accounting(ordered, input_count=len(batch["source_records"]))
    return {"schema_version": RESPONSE_SCHEMA_VERSION, "classifications": ordered}


def score_projection(*, projection: dict[str, Any], truth: dict[str, Any], batch: dict[str, Any], deterministic_source_ids: set[str], execution: list[dict[str, Any]]) -> dict[str, Any]:
    expected_by_id = {item["source_record_id"]: item for item in truth["source_records"]}
    actual_by_id = {item["assertion_id"]: item for item in projection["classifications"]}
    expected_records = Counter()
    actual_records = Counter()
    dispositions_correct = 0
    for source_id, expected in expected_by_id.items():
        actual = actual_by_id[source_id]
        dispositions_correct += actual["disposition"] == expected["expected_disposition"]
        for record in expected["expected_records"]:
            expected_records[(source_id, _record_signature(record))] += 1
        for record in actual["typed_records"]:
            clean = {key: copy.deepcopy(record[key]) for key in ("record_type", "claim_refs", "roles", "withholding_status")}
            actual_records[(source_id, _record_signature(clean))] += 1
    matched = sum((expected_records & actual_records).values())
    all_record_ids = [record["typed_record_id"] for item in projection["classifications"] for record in item["typed_records"]]
    idempotency = sqlite_idempotency_probe(projection)
    input_count = len(batch["source_records"])
    disposition_counts = Counter(item["disposition"] for item in projection["classifications"])
    return {
        "projection_sha256": _stable_sha256(projection),
        "input_source_records": input_count,
        "source_accounting_total": sum(disposition_counts.values()),
        "source_accounting_exact": sum(disposition_counts.values()) == input_count,
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "dispositions_correct": dispositions_correct,
        "expected_typed_records": sum(expected_records.values()),
        "actual_typed_records": sum(actual_records.values()),
        "exact_typed_records_correct": matched,
        "missing_typed_records": sum((expected_records - actual_records).values()),
        "extra_typed_records": sum((actual_records - expected_records).values()),
        "typed_record_ids_unique": len(all_record_ids) == len(set(all_record_ids)),
        "deterministic_source_records": len(deterministic_source_ids),
        "deterministic_ratio": len(deterministic_source_ids) / input_count,
        "semantic_residual_records": input_count - len(deterministic_source_ids),
        "semantic_residual_rate": (input_count - len(deterministic_source_ids)) / input_count,
        "idempotency": idempotency,
        "provider_calls": sum(item.get("provider_calls", 0) for item in execution),
        "input_tokens": sum(item.get("input_tokens") or 0 for item in execution),
        "output_tokens": sum(item.get("output_tokens") or 0 for item in execution),
        "duration_ms": sum(item.get("duration_ms") or 0 for item in execution),
    }


def _record_signature(record: dict[str, Any]) -> str:
    value = copy.deepcopy(record)
    # Claim refs prove the record's source boundary and are validated above. A
    # model may validly cite all role cells instead of the minimal expected set,
    # so fidelity compares the runtime fields, not that harmless provenance
    # superset choice.
    value.pop("claim_refs", None)
    value["roles"] = sorted(value["roles"], key=lambda item: item["role"])
    return _stable_sha256(value)


def sqlite_idempotency_probe(projection: dict[str, Any]) -> dict[str, Any]:
    records = [record for item in projection["classifications"] for record in item["typed_records"]]
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE typed_registers (typed_record_id TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL)")
        for _ in range(2):
            for record in records:
                connection.execute(
                    "INSERT OR IGNORE INTO typed_registers (typed_record_id, payload_sha256) VALUES (?, ?)",
                    (record["typed_record_id"], _stable_sha256(record)),
                )
        count = connection.execute("SELECT COUNT(*) FROM typed_registers").fetchone()[0]
    return {"first_projection_records": len(records), "after_second_materialization": count, "duplicates_created": count - len(records)}


def current_gate3_baseline(*, current_runs_dir: Path, chunk: dict[str, Any], batch: dict[str, Any], truth: dict[str, Any]) -> list[dict[str, Any]]:
    selected = {
        (row["source_identity"]["node_id"], row["source_identity"]["row"]): row["source_record_id"]
        for row in batch["source_records"]
    }
    expected_types = {
        item["source_record_id"]: Counter(record["record_type"] for record in item["expected_records"])
        for item in truth["source_records"]
    }
    runs = []
    for ordinal in range(1, RUNS + 1):
        raw = _read_json(current_runs_dir / f"run-{ordinal}.private.json")
        observed = {source_id: Counter() for source_id in expected_types}
        role_complete = 0
        for annotation in raw["merged_output"]["annotations"]:
            target = annotation.get("target") or {}
            key = (target.get("node_id"), target.get("row"))
            source_id = selected.get(key)
            if source_id is None or annotation.get("financial_label") not in RECORD_TYPES:
                continue
            observed[source_id][annotation["financial_label"]] += 1
            if all(item.get("status") == "value" for item in annotation.get("roles", [])):
                role_complete += 1
        exact = sum(sum((expected_types[source_id] & observed[source_id]).values()) for source_id in expected_types)
        runs.append(
            {
                "ordinal": ordinal,
                "annotations_total": len(raw["merged_output"]["annotations"]),
                "selected_expected_records": sum(sum(value.values()) for value in expected_types.values()),
                "selected_type_matches": exact,
                "selected_role_complete_annotations": role_complete,
                "selected_mapping_sha256": _stable_sha256({key: dict(value) for key, value in observed.items()}),
            }
        )
    return runs


def summarize_variant(*, name: str, runs: list[dict[str, Any]], expected_records: int, expected_sources: int) -> dict[str, Any]:
    valid = [item for item in runs if item.get("terminal_status") == "validated"]
    hashes = [item["metrics"]["projection_sha256"] for item in valid]
    repeatable = len(valid) == RUNS and len(set(hashes)) == 1
    faithful = len(valid) == RUNS and all(
        item["metrics"]["exact_typed_records_correct"] == expected_records
        and item["metrics"]["missing_typed_records"] == 0
        and item["metrics"]["extra_typed_records"] == 0
        and item["metrics"]["dispositions_correct"] == expected_sources
        for item in valid
    )
    accounting = len(valid) == RUNS and all(item["metrics"]["source_accounting_exact"] for item in valid)
    provenance = len(valid) == RUNS and all(item["metrics"]["typed_record_ids_unique"] for item in valid)
    idempotent = len(valid) == RUNS and all(item["metrics"]["idempotency"]["duplicates_created"] == 0 for item in valid)
    return {
        "variant": name,
        "runs": runs,
        "validated_runs": len(valid),
        "unique_projection_hashes": len(set(hashes)),
        "exact_repeatability": repeatable,
        "source_accounting_exact": accounting,
        "source_fidelity_exact": faithful,
        "provenance_valid": provenance,
        "idempotency_proven": idempotent,
    }


def choose_verdict(variants: dict[str, dict[str, Any]]) -> str:
    qualified = {
        name: value
        for name, value in variants.items()
        if value["exact_repeatability"]
        and value["source_accounting_exact"]
        and value["source_fidelity_exact"]
        and value["provenance_valid"]
        and value["idempotency_proven"]
    }
    if not qualified:
        any_valid = any(value["validated_runs"] for value in variants.values())
        return "BROKER_TYPED_PROJECTION_APPROACH_NOT_YET_PROVEN" if any_valid else "NO_CANDIDATE_PROVIDES_STABLE_RUNTIME_PROJECTION"
    if "B_deterministic_first" in qualified:
        return "DETERMINISTIC_FIRST_BROKER_ETL_PREFERRED"
    return "DIRECT_TYPED_EXTRACTION_PREFERRED"


def _execution_metrics(result: Any, *, provider_calls: int) -> dict[str, Any]:
    metadata = _plain(result.execution_metadata)
    receipt = _plain(result.operational_retry_receipt)
    if provider_calls != 1 or receipt.get("operational_retries") != 0:
        raise TypedRegistersBenchmarkError("provider_retry_forbidden")
    return {
        "provider_calls": provider_calls,
        "input_tokens": metadata.get("input_tokens"),
        "output_tokens": metadata.get("output_tokens"),
        "duration_ms": metadata.get("duration_ms"),
        "execution_metadata": metadata,
        "operational_retry_receipt": receipt,
    }


def _decode(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    if not isinstance(raw, str):
        raise TypedRegistersBenchmarkError("model_response_not_json")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TypedRegistersBenchmarkError("model_response_not_json") from exc
    if not isinstance(value, dict):
        raise TypedRegistersBenchmarkError("model_response_not_object")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_failed_run(*, ordinal: int, exc: Exception, provider_calls: int) -> dict[str, Any]:
    return {"ordinal": ordinal, "terminal_status": "rejected", "error_type": type(exc).__name__, "provider_calls": provider_calls}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-three-runs", action="store_true")
    parser.add_argument("--rescore-existing", action="store_true")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--private-store-root", type=Path, required=True)
    parser.add_argument("--current-runs-dir", type=Path, required=True)
    parser.add_argument("--private-source-truth", type=Path, required=True)
    parser.add_argument("--private-results-dir", type=Path, required=True)
    parser.add_argument("--safe-receipt-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    if args.execute_three_runs == args.rescore_existing:
        raise SystemExit("explicit_execute_flag_required")
    if not 1 <= args.timeout_seconds <= 900:
        raise SystemExit("timeout_out_of_bounds")
    store_root = args.private_store_root.resolve()
    current_runs = args.current_runs_dir.resolve()
    truth_path = args.private_source_truth.resolve()
    results_dir = args.private_results_dir.resolve()
    safe_receipt = args.safe_receipt_path.resolve()
    for private_path in (store_root, current_runs, truth_path, results_dir):
        if _is_within(private_path, REPO_ROOT.resolve()):
            raise SystemExit("private_evidence_must_be_outside_repository")
    if not _is_within(safe_receipt, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if not args.rescore_existing and results_dir.exists() and any(results_dir.iterdir()):
        raise SystemExit("private_results_must_be_new_or_empty")
    results_dir.mkdir(parents=True, exist_ok=True)

    truth_raw = truth_path.read_bytes()
    truth = _validated_truth(json.loads(truth_raw))
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(mode="sqlite", sqlite_path=store_root / "artifacts.sqlite3", payload_root=store_root / "payloads")
    ).create()
    document_id, context = _frozen_context(store_root)
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(document_id=document_id, context=context)
    if (
        len(chunk_set["chunks"]) != 1
        or chunk_set["coverage"]["eligible_targets"] != EXPECTED_CURRENT_TARGETS
        or chunk_set["coverage"]["lost_targets"] != 0
        or chunk_set["coverage"]["duplicated_working_targets"] != 0
    ):
        raise SystemExit("frozen_canonical_seam_changed")
    chunk = chunk_set["chunks"][0]
    batch = build_batch(chunk=chunk, truth=truth)
    source_ids = [item["source_record_id"] for item in batch["source_records"]]
    allowed_refs = sorted({entry["source_ref"] for row in batch["source_records"] for entry in row["elements"]})
    typed_schema = typed_response_schema(source_ids, allowed_refs)
    contract = {
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "record_types": list(RECORD_TYPES),
        "role_contract": {key: {"required": sorted(value[0]), "optional": sorted(value[1])} for key, value in TYPE_ROLE_CONTRACT.items()},
        "dispositions": list(DISPOSITIONS),
        "source_accounting_required": True,
        "tax_methodology_forbidden": True,
    }
    request_a = _model_request(instruction=DIRECT_INSTRUCTION, contract=contract, batch=structural_batch(batch), schema=typed_schema, name=RESPONSE_SCHEMA_VERSION)
    request_c = _model_request(instruction=DIRECT_INSTRUCTION, contract=contract, batch=large_context_batch(chunk=chunk, batch=batch), schema=typed_schema, name=RESPONSE_SCHEMA_VERSION)
    mapping_batch = table_mapping_batch(batch)
    table_ids = [item["logical_table_id"] for item in mapping_batch["logical_tables"]]
    header_refs = sorted({entry["source_ref"] for item in mapping_batch["logical_tables"] for entry in item["header_context"]})
    mapping_schema = mapping_response_schema(table_ids, header_refs)
    request_b_mapping = _model_request(
        instruction=MAPPING_INSTRUCTION,
        contract={"table_kinds": list(TABLE_KINDS), "column_roles": list(COLUMN_ROLES)},
        batch=mapping_batch,
        schema=mapping_schema,
        name=MAPPING_SCHEMA_VERSION,
    )
    plan = {
        "schema_version": "broker_typed_projection_benchmark_plan_v0",
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_truth_sha256": hashlib.sha256(truth_raw).hexdigest(),
        "broker_source_dialect": contract,
        "source_batch": batch,
        "requests": {"A": request_a, "B_mapping": request_b_mapping, "C": request_c},
        "runs": RUNS,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "production_activation": False,
    }
    if args.rescore_existing:
        old_receipt = _read_json(safe_receipt)
        rescored_a = []
        for ordinal in range(1, RUNS + 1):
            private_run = _read_json(results_dir / f"run-{ordinal}.private.json")
            evidence = private_run.get("A_structural_direct")
            if not isinstance(evidence, dict) or not isinstance(evidence.get("projection"), dict):
                rescored_a.append(
                    {"ordinal": ordinal, "terminal_status": "rejected", "error_type": "StoredEvidenceUnavailable", "provider_calls": 0}
                )
                continue
            metrics = score_projection(
                projection=evidence["projection"],
                truth=truth,
                batch=batch,
                deterministic_source_ids=set(),
                execution=evidence["execution"],
            )
            rescored_a.append({"ordinal": ordinal, "terminal_status": "validated", "metrics": metrics})
        variants = copy.deepcopy(old_receipt["variants"])
        variants["A_structural_direct"] = summarize_variant(
            name="A_structural_direct",
            runs=rescored_a,
            expected_records=sum(len(item["expected_records"]) for item in truth["source_records"]),
            expected_sources=len(source_ids),
        )
        terminal = choose_verdict(variants)
        old_receipt.update(
            {
                "status": terminal,
                "terminals": [terminal],
                "variants": variants,
                "offline_rescore": {
                    "provider_calls": 0,
                    "reason": "claim_ref_superset_is_valid_provenance_not_field_fidelity",
                },
            }
        )
        _atomic_write(safe_receipt, _json_bytes(old_receipt))
        print(json.dumps(old_receipt, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    _atomic_write(results_dir / "frozen-plan.private.json", _json_bytes(plan))

    # The shared client has a transport-only retry for production qualification. This
    # process-local override seals this benchmark to exactly one submission per call.
    model_clients_module.GATE3_OPERATIONAL_RETRY_LIMIT = 0
    client, submissions = _live_client(env_file=args.env_file, timeout_seconds=args.timeout_seconds)
    variant_runs: dict[str, list[dict[str, Any]]] = {"A_structural_direct": [], "B_deterministic_first": [], "C_large_context_direct": []}
    private_runs: list[dict[str, Any]] = []
    expected_records = sum(len(item["expected_records"]) for item in truth["source_records"])

    for ordinal in range(1, RUNS + 1):
        run_private: dict[str, Any] = {"ordinal": ordinal}
        for variant, request in (("A_structural_direct", request_a), ("C_large_context_direct", request_c)):
            before = submissions["count"]
            result = None
            try:
                result = asyncio.run(client.label_gate3_once(model_visible_request=request, canonical_schema=typed_schema, model_id=NDFL_PROVIDER_MODEL_ID))
                calls = submissions["count"] - before
                projection = validate_typed_response(result.adapter_extracted_output, batch=batch)
                execution = [_execution_metrics(result, provider_calls=calls)]
                metrics = score_projection(projection=projection, truth=truth, batch=batch, deterministic_source_ids=set(), execution=execution)
                variant_runs[variant].append({"ordinal": ordinal, "terminal_status": "validated", "metrics": metrics})
                run_private[variant] = {"projection": projection, "raw_model_output": copy.deepcopy(result.adapter_extracted_output), "raw_provider_response": copy.deepcopy(result.raw_provider_response), "execution": execution}
            except Exception as exc:  # evidence must preserve terminal rejection
                variant_runs[variant].append(_safe_failed_run(ordinal=ordinal, exc=exc, provider_calls=submissions["count"] - before))
                run_private[variant] = {
                    "rejected": True,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "raw_model_output": (
                        copy.deepcopy(result.adapter_extracted_output)
                        if result is not None
                        else None
                    ),
                    "raw_provider_response": (
                        copy.deepcopy(result.raw_provider_response)
                        if result is not None
                        else None
                    ),
                }

        before_mapping = submissions["count"]
        mapping_result = None
        residual_result = None
        try:
            mapping_result = asyncio.run(client.label_gate3_once(model_visible_request=request_b_mapping, canonical_schema=mapping_schema, model_id=NDFL_PROVIDER_MODEL_ID))
            mapping_calls = submissions["count"] - before_mapping
            mapping = validate_mapping_response(mapping_result.adapter_extracted_output, mapping_batch=mapping_batch, batch=batch)
            mapping_execution = _execution_metrics(mapping_result, provider_calls=mapping_calls)
            deterministic, residual_rows = deterministic_materialize(batch=batch, mapping=mapping)
            residual_batch = {"schema_version": batch["schema_version"], "source_records": residual_rows}
            residual_ids = [item["source_record_id"] for item in residual_rows]
            residual_refs = sorted({entry["source_ref"] for row in residual_rows for entry in row["elements"]})
            residual_schema = typed_response_schema(residual_ids, residual_refs)
            residual_request = _model_request(instruction=DIRECT_INSTRUCTION, contract=contract, batch=residual_batch, schema=residual_schema, name=RESPONSE_SCHEMA_VERSION)
            before_residual = submissions["count"]
            residual_result = asyncio.run(client.label_gate3_once(model_visible_request=residual_request, canonical_schema=residual_schema, model_id=NDFL_PROVIDER_MODEL_ID))
            residual_calls = submissions["count"] - before_residual
            residual_projection = validate_typed_response(residual_result.adapter_extracted_output, batch=residual_batch)
            projection = merge_deterministic_and_residual(batch=batch, deterministic=deterministic, residual_projection=residual_projection)
            execution = [mapping_execution, _execution_metrics(residual_result, provider_calls=residual_calls)]
            deterministic_ids = {item["assertion_id"] for item in deterministic}
            metrics = score_projection(projection=projection, truth=truth, batch=batch, deterministic_source_ids=deterministic_ids, execution=execution)
            variant_runs["B_deterministic_first"].append({"ordinal": ordinal, "terminal_status": "validated", "metrics": metrics})
            run_private["B_deterministic_first"] = {
                "mapping": mapping,
                "deterministic_projection": deterministic,
                "residual_request": residual_request,
                "residual_projection": residual_projection,
                "projection": projection,
                "mapping_raw_model_output": copy.deepcopy(mapping_result.adapter_extracted_output),
                "residual_raw_model_output": copy.deepcopy(residual_result.adapter_extracted_output),
                "mapping_raw_provider_response": copy.deepcopy(mapping_result.raw_provider_response),
                "residual_raw_provider_response": copy.deepcopy(residual_result.raw_provider_response),
                "execution": execution,
            }
        except Exception as exc:
            variant_runs["B_deterministic_first"].append(_safe_failed_run(ordinal=ordinal, exc=exc, provider_calls=submissions["count"] - before_mapping))
            run_private["B_deterministic_first"] = {
                "rejected": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "mapping_raw_model_output": (
                    copy.deepcopy(mapping_result.adapter_extracted_output)
                    if mapping_result is not None
                    else None
                ),
                "mapping_raw_provider_response": (
                    copy.deepcopy(mapping_result.raw_provider_response)
                    if mapping_result is not None
                    else None
                ),
                "residual_raw_model_output": (
                    copy.deepcopy(residual_result.adapter_extracted_output)
                    if residual_result is not None
                    else None
                ),
                "residual_raw_provider_response": (
                    copy.deepcopy(residual_result.raw_provider_response)
                    if residual_result is not None
                    else None
                ),
            }
        _atomic_write(results_dir / f"run-{ordinal}.private.json", _json_bytes(run_private))
        private_runs.append(run_private)

    summaries = {
        name: summarize_variant(name=name, runs=runs, expected_records=expected_records, expected_sources=len(source_ids))
        for name, runs in variant_runs.items()
    }
    terminal = choose_verdict(summaries)
    if terminal not in TERMINALS:
        raise TypedRegistersBenchmarkError("benchmark_terminal_invalid")
    receipt = {
        "schema_version": "broker_typed_projection_benchmark_receipt_v0",
        "status": terminal,
        "terminals": [terminal],
        "research_only": True,
        "production_changed": False,
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_truth_sha256": hashlib.sha256(truth_raw).hexdigest(),
        "source_records": len(source_ids),
        "expected_typed_records": expected_records,
        "logical_tables": len(table_ids),
        "provider_profile_id": NDFL_PROVIDER_PROFILE_ID,
        "model_id": NDFL_PROVIDER_MODEL_ID,
        "runs_per_variant": RUNS,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "variants": summaries,
        "current_gate3_frozen_baseline": current_gate3_baseline(current_runs_dir=current_runs, chunk=chunk, batch=batch, truth=truth),
        "downstream_contract": {
            "source_types_match_current_gate5_consumers": True,
            "security_required_roles": ["date", "asset", "quantity", "amount", "currency"],
            "coupon_required_roles": ["date", "asset", "amount", "currency"],
            "withholding_without_amount_remains_role_incomplete": True,
            "sql_authority": False,
        },
        "private_evidence_dir_sha256": _stable_sha256([_stable_sha256(item) for item in private_runs]),
    }
    _atomic_write(safe_receipt, _json_bytes(receipt))
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
