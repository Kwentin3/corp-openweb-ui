#!/usr/bin/env python3
"""Inactive G5.87 exhaustive table-classification contract and validator."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from broker_reports_gate1.gate3_bounded_labeling import (
    GATE3_LABELING_INSTRUCTION_ID,
    GATE3_LABELING_INSTRUCTION_VERSION,
)
from broker_reports_gate1.gate3_financial_label_dictionary import (
    Gate3FinancialLabelDictionaryFactory,
)
from broker_reports_gate1.gate3_financial_role_pack import (
    Gate3FinancialRolePackFactory,
)
from broker_reports_gate1.gate3_role_labeling import (
    FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION,
    GATE3_ROLE_LABELING_INSTRUCTION_ID,
    GATE3_ROLE_LABELING_INSTRUCTION_VERSION,
    Gate3RoleLabelingError,
    Gate3RoleValueResolver,
)


SCHEMA_VERSION = "broker_reports_g587_table_assertions_v1"
INSTRUCTION_ID = "broker-reports-g587-exhaustive-table-classification"
INSTRUCTION_VERSION = "1.0.0"
INSTRUCTION = """\
Ты классифицируешь ровно одну Canonical Markdown table-unit. Это исчерпывающая,
но fail-closed классификация уже перечисленных строк, а не поиск фрагментов.

Верни каждую переданную row_id ровно один раз. Не добавляй и не пропускай строки.
Для каждой строки выбери status:
- CLASSIFIED: строка прямо утверждает один или несколько финансовых фактов из словаря;
- NONE: строка структурная или не утверждает финансовый факт;
- UNMAPPED: строка прямо утверждает финансовый факт, но ни один тип словаря не подходит.

Для CLASSIFIED верни все и только прямо утверждённые в этой строке assertions.
Описание объекта или дохода внутри строки не меняет смысл явно указанного события.
Не выводи литералы, суммы, даты, валюты, canonical refs или пояснения. Для каждого
assertion разрешены только financial_type и role-to-cell_id bindings. cell_id обязан
принадлежать той же строке. Используй только типы словаря и роли Role Pack. Если
роль нельзя безопасно связать с одной cell_id этой строки, не выводи её. NONE и
UNMAPPED всегда имеют пустой assertions. Верни только JSON заданной схемы.
"""


class G587ContractError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateJsonKeyError(ValueError):
    pass


def table_rows(chunk: dict[str, Any]) -> list[dict[str, Any]]:
    """Restore the backend-owned row/cell alias inventory from one table chunk."""

    if chunk.get("structural_kind") not in {"whole_table", "table_row_range"}:
        raise G587ContractError("g587_table_chunk_required")
    mappings = chunk.get("target_mappings")
    if not isinstance(mappings, list) or not mappings:
        raise G587ContractError("g587_target_mappings_required")
    rows: dict[tuple[str, int], dict[str, Any]] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict) or set(mapping) != {
            "target_alias",
            "canonical_target",
        }:
            raise G587ContractError("g587_target_mapping_invalid")
        alias = mapping["target_alias"]
        target = mapping["canonical_target"]
        if not isinstance(alias, str) or not isinstance(target, dict):
            raise G587ContractError("g587_target_mapping_invalid")
        kind = target.get("kind")
        if kind not in {"table_row", "table_cell"}:
            continue
        node_id = target.get("node_id")
        row = target.get("row")
        if not isinstance(node_id, str) or not isinstance(row, int):
            raise G587ContractError("g587_table_target_invalid")
        key = (node_id, row)
        item = rows.setdefault(
            key,
            {
                "row_id": None,
                "row_target": {"kind": "table_row", "node_id": node_id, "row": row},
                "cells": [],
            },
        )
        if kind == "table_row":
            if item["row_id"] is not None:
                raise G587ContractError("g587_duplicate_row_alias")
            item["row_id"] = alias
        else:
            item["cells"].append(
                {
                    "cell_id": alias,
                    "target": copy.deepcopy(target),
                    "column": target.get("column"),
                }
            )
    ordered = sorted(
        rows.values(),
        key=lambda item: (item["row_target"]["node_id"], item["row_target"]["row"]),
    )
    if not ordered or any(item["row_id"] is None for item in ordered):
        raise G587ContractError("g587_row_alias_missing")
    aliases = [item["row_id"] for item in ordered]
    cell_aliases = [cell["cell_id"] for item in ordered for cell in item["cells"]]
    if len(set(aliases)) != len(aliases) or len(set(cell_aliases)) != len(cell_aliases):
        raise G587ContractError("g587_alias_not_unique")
    return ordered


def response_schema(
    rows: list[dict[str, Any]], labels: list[str], roles: list[str]
) -> dict[str, Any]:
    row_ids = [item["row_id"] for item in rows]
    cell_ids = [cell["cell_id"] for item in rows for cell in item["cells"]]
    if not row_ids or not cell_ids or not labels or not roles:
        raise G587ContractError("g587_schema_domain_empty")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {
            "annotation": {
                "type": "object",
                "additionalProperties": False,
                "required": ["target_alias"],
                "properties": {
                    "target_alias": {
                        "type": "string",
                        "pattern": "^t[0-9]{3,}$",
                        "description": (
                            "Exact bare alias value shown in the document: for "
                            "[t123], return t123. The value itself must contain only "
                            "t followed by digits; do not include brackets, Markdown, "
                            "prefixes, or explanations. This unused definition preserves "
                            "the canonical Gate 3 transport alias projection."
                        ),
                    }
                },
            }
        },
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "rows"],
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "rows": {
                "type": "array",
                "minItems": len(row_ids),
                "maxItems": len(row_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["row_id", "status", "assertions"],
                    "properties": {
                        "row_id": {"type": "string", "enum": row_ids},
                        "status": {
                            "type": "string",
                            "enum": ["CLASSIFIED", "NONE", "UNMAPPED"],
                        },
                        "assertions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["financial_type", "roles"],
                                "properties": {
                                    "financial_type": {
                                        "type": "string",
                                        "enum": labels,
                                    },
                                    "roles": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "required": ["role", "cell_id"],
                                            "properties": {
                                                "role": {
                                                    "type": "string",
                                                    "enum": roles,
                                                },
                                                "cell_id": {
                                                    "type": "string",
                                                    "enum": cell_ids,
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def compose_request(chunk: dict[str, Any]) -> dict[str, Any]:
    rows = table_rows(chunk)
    dictionary_owner = Gate3FinancialLabelDictionaryFactory.create()
    dictionary = dictionary_owner.load_published()
    role_owner = Gate3FinancialRolePackFactory.create()
    role_pack = role_owner.load_published()
    labels = [item["label_id"] for item in dictionary["labels"]]
    roles = [item["role_id"] for item in role_pack["roles"]]
    schema = response_schema(rows, labels, roles)
    ontology = (
        dictionary_owner.render_model_markdown()
        + "\n"
        + role_owner.render_model_markdown()
    )
    return {
        "messages": [
            {"role": "system", "content": INSTRUCTION},
            {"role": "user", "content": ontology},
            {"role": "user", "content": chunk["model_view"]["content"]},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "g587_table_assertions",
                "strict": True,
                "schema": schema,
            },
        },
    }


def validate_and_map(
    *,
    raw_model_output: Any,
    chunk: dict[str, Any],
    canonical_artifact: dict[str, Any],
    model_id: str,
) -> dict[str, Any]:
    """Fail closed, restore aliases, and map to the current typed V2 shape."""

    response = _decode(raw_model_output)
    if (
        set(response) != {"schema_version", "rows"}
        or response.get("schema_version") != SCHEMA_VERSION
        or not isinstance(response.get("rows"), list)
    ):
        raise G587ContractError("g587_response_contract_invalid")
    inventory = table_rows(chunk)
    by_row = {item["row_id"]: item for item in inventory}
    expected_ids = list(by_row)
    response_ids: list[str] = []
    for row in response["rows"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"row_id", "status", "assertions"}
            or not isinstance(row.get("row_id"), str)
        ):
            raise G587ContractError("g587_response_row_invalid")
        response_ids.append(row["row_id"])
    if any(row_id not in by_row for row_id in response_ids):
        raise G587ContractError("g587_response_row_unknown")
    if len(set(response_ids)) != len(response_ids):
        raise G587ContractError("g587_response_row_duplicate")
    if set(response_ids) != set(expected_ids):
        raise G587ContractError("g587_response_row_missing")

    dictionary = Gate3FinancialLabelDictionaryFactory.create().load_published()
    role_pack = Gate3FinancialRolePackFactory.create().load_published()
    labels = {item["label_id"] for item in dictionary["labels"]}
    profiles = {item["financial_label"]: item for item in role_pack["profiles"]}
    all_cells = {cell["cell_id"] for item in inventory for cell in item["cells"]}
    target_by_cell = {
        cell["cell_id"]: cell["target"] for item in inventory for cell in item["cells"]
    }
    resolver = Gate3RoleValueResolver(canonical_artifact=canonical_artifact)
    annotations: list[dict[str, Any]] = []
    annotation_row_ids: list[str] = []
    rejected_bindings: list[dict[str, str]] = []
    statuses: dict[str, str] = {}
    for response_row in response["rows"]:
        row_id = response_row["row_id"]
        status = response_row.get("status")
        assertions = response_row.get("assertions")
        if status not in {"CLASSIFIED", "NONE", "UNMAPPED"} or not isinstance(
            assertions, list
        ):
            raise G587ContractError("g587_response_row_invalid")
        if (status == "CLASSIFIED") != bool(assertions):
            raise G587ContractError("g587_response_status_cardinality_invalid")
        statuses[row_id] = status
        seen_labels: set[str] = set()
        allowed_cells = {cell["cell_id"] for cell in by_row[row_id]["cells"]}
        for assertion in assertions:
            if (
                not isinstance(assertion, dict)
                or set(assertion) != {"financial_type", "roles"}
                or not isinstance(assertion.get("roles"), list)
            ):
                raise G587ContractError("g587_assertion_invalid")
            label = assertion.get("financial_type")
            if label not in labels:
                raise G587ContractError("g587_financial_type_unknown")
            if label in seen_labels:
                raise G587ContractError("g587_assertion_duplicate")
            seen_labels.add(label)
            profile = profiles[label]
            allowed_roles = [*profile["required_roles"], *profile["optional_roles"]]
            bindings: dict[str, dict[str, Any]] = {}
            for binding in assertion["roles"]:
                if not isinstance(binding, dict) or set(binding) != {"role", "cell_id"}:
                    raise G587ContractError("g587_role_binding_invalid")
                role = binding.get("role")
                cell_id = binding.get("cell_id")
                if role not in allowed_roles or role in bindings:
                    raise G587ContractError("g587_role_not_allowed")
                if cell_id not in all_cells:
                    raise G587ContractError("g587_cell_unknown")
                if cell_id not in allowed_cells:
                    raise G587ContractError("g587_cell_cross_row")
                restored = {
                    "role": role,
                    "status": "bound",
                    "target": copy.deepcopy(target_by_cell[cell_id]),
                }
                try:
                    resolver.resolve(restored)
                except Gate3RoleLabelingError as exc:
                    rejected_bindings.append(
                        {
                            "row_id": row_id,
                            "financial_type": label,
                            "role": role,
                            "cell_id": cell_id,
                            "error_code": exc.code,
                        }
                    )
                    restored = {"role": role, "status": "missing"}
                bindings[role] = restored
            annotations.append(
                {
                    "target": copy.deepcopy(by_row[row_id]["row_target"]),
                    "financial_label": label,
                    "roles": [
                        copy.deepcopy(
                            bindings.get(role, {"role": role, "status": "missing"})
                        )
                        for role in allowed_roles
                    ],
                }
            )
            annotation_row_ids.append(row_id)
    mapped = {
        "schema_version": FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION,
        "canonical_binding": copy.deepcopy(chunk["canonical_binding"]),
        "dictionary_identity": {
            "dictionary_id": dictionary["dictionary_id"],
            "semantic_version": dictionary["semantic_version"],
        },
        "role_pack_identity": {
            "role_pack_id": role_pack["role_pack_id"],
            "semantic_version": role_pack["semantic_version"],
        },
        "instruction_identity": {
            "instruction_id": GATE3_LABELING_INSTRUCTION_ID,
            "semantic_version": GATE3_LABELING_INSTRUCTION_VERSION,
        },
        "role_instruction_identity": {
            "instruction_id": GATE3_ROLE_LABELING_INSTRUCTION_ID,
            "semantic_version": GATE3_ROLE_LABELING_INSTRUCTION_VERSION,
        },
        "model_identity": {"model_id": model_id},
        "annotations": annotations,
        "validation_status": "validated",
    }
    return {
        "schema_version": "broker_reports_g587_validated_table_result_v1",
        "chunk_ordinal": chunk["ordinal"],
        "row_statuses": statuses,
        "annotation_row_ids": annotation_row_ids,
        "rejected_bindings": rejected_bindings,
        "mapped_financial_annotations_v2": mapped,
        "metrics": {
            "rows_expected": len(expected_ids),
            "rows_returned": len(response_ids),
            "rows_classified": sum(
                value == "CLASSIFIED" for value in statuses.values()
            ),
            "rows_none": sum(value == "NONE" for value in statuses.values()),
            "rows_unmapped": sum(value == "UNMAPPED" for value in statuses.values()),
            "assertions": len(annotations),
            "role_bindings_rejected": len(rejected_bindings),
        },
    }


def stable_sha256(value: Any) -> str:
    raw = (
        value.encode("utf-8")
        if isinstance(value, str)
        else json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )
    return hashlib.sha256(raw).hexdigest()


def _decode(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        raise G587ContractError("g587_response_contract_invalid")
    try:
        result = json.loads(
            value, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise G587ContractError("g587_response_contract_invalid") from exc
    if not isinstance(result, dict):
        raise G587ContractError("g587_response_contract_invalid")
    return result


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(value)


__all__ = [
    "G587ContractError",
    "INSTRUCTION",
    "INSTRUCTION_ID",
    "INSTRUCTION_VERSION",
    "SCHEMA_VERSION",
    "compose_request",
    "response_schema",
    "stable_sha256",
    "table_rows",
    "validate_and_map",
]
