"""Frozen exact-schema mappings qualified for ordinary-trade production use.

The entries are selected only by their structural fingerprint. Human-readable
headers and explicit amount-column to currency-column bindings remain part of
the frozen source-semantic authority; broker, year and filename are deliberately
absent from the runtime contract.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from .ordinary_trade_semantic_compiler import (
    compile_schema_mapping,
    structural_fingerprint,
    validate_schema_mapping,
)


FACTORY_REQUIRED = (
    "OrdinaryTradeQualifiedMappingAuthorityFactory.create is the only "
    "production mapping authority entrypoint"
)
FORBIDDEN = (
    "broker, year or filename routing; fuzzy fingerprint reuse; runtime LLM "
    "calls; caller mutation of qualified mappings"
)


QUALIFICATION_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_mapping_qualification_v1"
)
_CONSUMER_CONTRACT = "Gate4FinancialCaseFactV2.amount_currency"
_RELATION_BASES = {"EXPLICIT_DENOMINATION_HEADER", "QUALIFIED_SCHEMA_SCOPE"}


_MAPPING_SPECS: tuple[dict[str, Any], ...] = (
    {
        "title_literal": None,
        "columns": [
            {
                "column": 1,
                "header_literal": "Дата заключения",
                "semantic_role": "trade_date",
            },
            {
                "column": 2,
                "header_literal": "Дата расчетов",
                "semantic_role": "settlement_date",
            },
            {
                "column": 3,
                "header_literal": "Время заключения",
                "semantic_role": "trade_time",
            },
            {
                "column": 4,
                "header_literal": "Наименование ЦБ",
                "semantic_role": "asset_name",
            },
            {"column": 5, "header_literal": "Код ЦБ", "semantic_role": "security_code"},
            {"column": 6, "header_literal": "Валюта", "semantic_role": "currency"},
            {"column": 7, "header_literal": "Вид", "semantic_role": "side"},
            {
                "column": 8,
                "header_literal": "Количество, шт.",
                "semantic_role": "quantity",
            },
            {"column": 9, "header_literal": "Цена²", "semantic_role": "unit_price"},
            {"column": 10, "header_literal": "Сумма", "semantic_role": "gross_amount"},
            {
                "column": 11,
                "header_literal": "НКД⁴",
                "semantic_role": "accrued_interest",
            },
            {
                "column": 12,
                "header_literal": "Комиссия Брокера",
                "semantic_role": "broker_commission",
            },
            {
                "column": 13,
                "header_literal": "Комиссия Биржи",
                "semantic_role": "exchange_commission",
            },
            {
                "column": 14,
                "header_literal": "Номер сделки",
                "semantic_role": "trade_id",
            },
            {"column": 15, "header_literal": "Комментарий", "semantic_role": "comment"},
            {
                "column": 16,
                "header_literal": "Статус сделки⁵",
                "semantic_role": "status",
            },
        ],
        "amount_currency_bindings": [
            {"amount_column": 10, "currency_column": 6},
            {"amount_column": 12, "currency_column": 6},
            {"amount_column": 13, "currency_column": 6},
        ],
        "side_values": [
            {"normalized_value": "DISPOSAL", "source_literal": "Продажа"},
            {"normalized_value": "PURCHASE", "source_literal": "Покупка"},
        ],
        "supporting_decisions": [
            {
                "decision_id": "sber-2024-schema-decision",
                "decision_kind": "SCHEMA_MAPPING",
                "model_id": "models/gemini-3.5-flash",
                "response_sha256": "99eeb7d3fd1d17dcb8c072ea4c4da0ffce2cc31899ea155b55a0177b573fc5ac",
            },
            {
                "decision_id": "sber-2024-side-decision",
                "decision_kind": "SIDE_ENUM",
                "model_id": "models/gemini-3.5-flash",
                "response_sha256": "1e5724738bd1f7eb7859714b53730456ed8b72322c0c6d0884759dd31c8f9a60",
            },
        ],
    },
    {
        "title_literal": "Заключенные в отчетном периоде сделки с ценными бумагами",
        "columns": [
            {
                "column": 1,
                "header_literal": "Наименование ценной бумаги, № гос. Регистрации, ISIN",
                "semantic_role": "asset_name",
            },
            {
                "column": 2,
                "header_literal": "Дата и время заключения сделки",
                "semantic_role": "trade_date",
            },
            {"column": 3, "header_literal": "Вид сделки", "semantic_role": "side"},
            {
                "column": 4,
                "header_literal": "Количество (шт)",
                "semantic_role": "quantity",
            },
            {
                "column": 5,
                "header_literal": "Валюта цены (номинала для облигаций)",
                "semantic_role": "currency",
            },
            {
                "column": 6,
                "header_literal": "Цена (% для облигаций)",
                "semantic_role": "unit_price",
            },
            {
                "column": 7,
                "header_literal": "Валюта расчетов",
                "semantic_role": "currency",
            },
            {
                "column": 8,
                "header_literal": "Сумма сделки в валюте расчетов (с учетом НКД для облигаций)",
                "semantic_role": "gross_amount",
            },
            {
                "column": 9,
                "header_literal": "НКД по сделке в валюте расчетов",
                "semantic_role": "accrued_interest",
            },
            {
                "column": 10,
                "header_literal": "Комиссия Банка за расчет по сделке",
                "semantic_role": "broker_commission",
            },
            {
                "column": 11,
                "header_literal": "Комиссия Банка за заключение сделки",
                "semantic_role": "broker_commission",
            },
            {
                "column": 12,
                "header_literal": "Плановая дата поставки",
                "semantic_role": "settlement_date",
            },
            {
                "column": 13,
                "header_literal": "Плановая дата оплаты",
                "semantic_role": "settlement_date",
            },
            {"column": 14, "header_literal": "№ заявки", "semantic_role": "unmapped"},
            {"column": 15, "header_literal": "№ сделки", "semantic_role": "trade_id"},
            {
                "column": 16,
                "header_literal": "УДС до сделки ³",
                "semantic_role": "unmapped",
            },
            {"column": 17, "header_literal": "Контрагент", "semantic_role": "unmapped"},
            {
                "column": 18,
                "header_literal": "Место заключения сделки",
                "semantic_role": "venue",
            },
            {"column": 19, "header_literal": "Комментарий", "semantic_role": "comment"},
        ],
        "amount_currency_bindings": [
            {"amount_column": 8, "currency_column": 7},
            {"amount_column": 10, "currency_column": 7},
            {"amount_column": 11, "currency_column": 7},
        ],
        "side_values": [
            {"normalized_value": "DISPOSAL", "source_literal": "Продажа"},
            {"normalized_value": "PURCHASE", "source_literal": "Покупка"},
        ],
        "supporting_decisions": [
            {
                "decision_id": "vtb-2024-schema-decision",
                "decision_kind": "SCHEMA_MAPPING",
                "model_id": "models/gemini-3.5-flash",
                "response_sha256": "9e8b00cded1c07f85ae9a9bedd653a510f528e893a5dd5c0f2e0ec192e1d6213",
            },
            {
                "decision_id": "vtb-2024-side-decision",
                "decision_kind": "SIDE_ENUM",
                "model_id": "models/gemini-3.5-flash",
                "response_sha256": "02242277dc0f9dc61a2f0d9cfa49d7e39713810f4f3e983ac2c100a595b74f06",
            },
        ],
    },
)


_RELATION_CLAIMS: tuple[tuple[dict[str, Any], ...], ...] = (
    (
        {
            "amount_column": 10,
            "currency_column": 6,
            "evidence_basis": "QUALIFIED_SCHEMA_SCOPE",
            "amount_header_literal": "Сумма",
            "currency_header_literal": "Валюта",
            "consumer_contract": _CONSUMER_CONTRACT,
        },
        {
            "amount_column": 12,
            "currency_column": 6,
            "evidence_basis": "QUALIFIED_SCHEMA_SCOPE",
            "amount_header_literal": "Комиссия Брокера",
            "currency_header_literal": "Валюта",
            "consumer_contract": _CONSUMER_CONTRACT,
        },
        {
            "amount_column": 13,
            "currency_column": 6,
            "evidence_basis": "QUALIFIED_SCHEMA_SCOPE",
            "amount_header_literal": "Комиссия Биржи",
            "currency_header_literal": "Валюта",
            "consumer_contract": _CONSUMER_CONTRACT,
        },
    ),
    (
        {
            "amount_column": 8,
            "currency_column": 7,
            "evidence_basis": "EXPLICIT_DENOMINATION_HEADER",
            "amount_header_literal": (
                "Сумма сделки в валюте расчетов (с учетом НКД для облигаций)"
            ),
            "currency_header_literal": "Валюта расчетов",
            "consumer_contract": _CONSUMER_CONTRACT,
        },
        {
            "amount_column": 10,
            "currency_column": 7,
            "evidence_basis": "QUALIFIED_SCHEMA_SCOPE",
            "amount_header_literal": "Комиссия Банка за расчет по сделке",
            "currency_header_literal": "Валюта расчетов",
            "consumer_contract": _CONSUMER_CONTRACT,
        },
        {
            "amount_column": 11,
            "currency_column": 7,
            "evidence_basis": "QUALIFIED_SCHEMA_SCOPE",
            "amount_header_literal": "Комиссия Банка за заключение сделки",
            "currency_header_literal": "Валюта расчетов",
            "consumer_contract": _CONSUMER_CONTRACT,
        },
    ),
)


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _semantic_scope(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "columns": copy.deepcopy(spec["columns"]),
        "amount_currency_bindings": copy.deepcopy(
            spec["amount_currency_bindings"]
        ),
        "side_values": copy.deepcopy(spec["side_values"]),
    }


def _freeze_receipt(
    *, spec: dict[str, Any], relation_claims: tuple[dict[str, Any], ...]
) -> dict[str, Any]:
    fingerprint = structural_fingerprint(
        title_literal=spec["title_literal"], columns=spec["columns"]
    )
    material = {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "status": "QUALIFIED",
        "structural_fingerprint": fingerprint,
        "evidence_surface": {
            "title_literal": spec["title_literal"],
            "headers": [
                {
                    "column": item["column"],
                    "literal": item["header_literal"],
                }
                for item in spec["columns"]
            ],
        },
        "semantic_scope_sha256": _sha256_json(_semantic_scope(spec)),
        "relation_claims": copy.deepcopy(list(relation_claims)),
        "supporting_decisions": copy.deepcopy(spec["supporting_decisions"]),
        "consumer_contracts": [_CONSUMER_CONTRACT],
    }
    qualification_id = "otqual_" + _sha256_json(material)[:32]
    receipt = {**material, "qualification_id": qualification_id}
    receipt["receipt_sha256"] = _sha256_json(receipt)
    return receipt


def _compile_qualified_entry(
    *, spec: dict[str, Any], relation_claims: tuple[dict[str, Any], ...]
) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = _freeze_receipt(spec=spec, relation_claims=relation_claims)
    mapping = compile_schema_mapping(
        title_literal=spec["title_literal"],
        headers=[
            {"column": item["column"], "literal": item["header_literal"]}
            for item in spec["columns"]
        ],
        model_columns=[
            {"column": item["column"], "semantic_role": item["semantic_role"]}
            for item in spec["columns"]
        ],
        amount_currency_bindings=spec["amount_currency_bindings"],
        side_values=spec["side_values"],
        qualification_ref={
            "qualification_id": receipt["qualification_id"],
            "receipt_sha256": receipt["receipt_sha256"],
        },
    )
    _validate_qualification(mapping=mapping, receipt=receipt)
    return mapping, receipt


def _validate_qualification(
    *, mapping: dict[str, Any], receipt: dict[str, Any]
) -> None:
    validate_schema_mapping(mapping)
    expected_keys = {
        "schema_version",
        "status",
        "structural_fingerprint",
        "evidence_surface",
        "semantic_scope_sha256",
        "relation_claims",
        "supporting_decisions",
        "consumer_contracts",
        "qualification_id",
        "receipt_sha256",
    }
    if (
        set(receipt) != expected_keys
        or receipt.get("schema_version") != QUALIFICATION_SCHEMA_VERSION
        or receipt.get("status") != "QUALIFIED"
        or receipt.get("structural_fingerprint")
        != mapping["structural_fingerprint"]
        or receipt.get("consumer_contracts") != [_CONSUMER_CONTRACT]
    ):
        raise RuntimeError("ordinary_trade_mapping_qualification_invalid")
    frozen = copy.deepcopy(receipt)
    receipt_sha256 = frozen.pop("receipt_sha256", None)
    if (
        not isinstance(receipt_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", receipt_sha256) is None
        or receipt_sha256 != _sha256_json(frozen)
        or mapping["qualification_ref"]
        != {
            "qualification_id": receipt["qualification_id"],
            "receipt_sha256": receipt_sha256,
        }
    ):
        raise RuntimeError("ordinary_trade_mapping_qualification_hash_invalid")
    id_material = copy.deepcopy(frozen)
    qualification_id = id_material.pop("qualification_id", None)
    if qualification_id != "otqual_" + _sha256_json(id_material)[:32]:
        raise RuntimeError("ordinary_trade_mapping_qualification_identity_invalid")
    evidence_surface = receipt.get("evidence_surface")
    if evidence_surface != {
        "title_literal": mapping["title_literal"],
        "headers": [
            {"column": item["column"], "literal": item["header_literal"]}
            for item in mapping["columns"]
        ],
    }:
        raise RuntimeError("ordinary_trade_mapping_qualification_surface_invalid")
    scope = {
        "columns": mapping["columns"],
        "amount_currency_bindings": mapping["amount_currency_bindings"],
        "side_values": mapping["side_values"],
    }
    if receipt.get("semantic_scope_sha256") != _sha256_json(scope):
        raise RuntimeError("ordinary_trade_mapping_qualification_scope_invalid")
    decisions = receipt.get("supporting_decisions")
    if not isinstance(decisions, list) or not decisions:
        raise RuntimeError("ordinary_trade_mapping_supporting_decision_invalid")
    for decision in decisions:
        if (
            not isinstance(decision, dict)
            or set(decision)
            != {"decision_id", "decision_kind", "model_id", "response_sha256"}
            or decision.get("decision_kind") not in {"SCHEMA_MAPPING", "SIDE_ENUM"}
            or not all(
                isinstance(decision.get(key), str) and decision.get(key)
                for key in decision
            )
            or re.fullmatch(r"[0-9a-f]{64}", decision["response_sha256"])
            is None
        ):
            raise RuntimeError("ordinary_trade_mapping_supporting_decision_invalid")
    headers = {item["column"]: item["header_literal"] for item in mapping["columns"]}
    claims = receipt.get("relation_claims")
    if not isinstance(claims, list):
        raise RuntimeError("ordinary_trade_mapping_relation_claim_invalid")
    claimed_bindings: list[dict[str, int]] = []
    for claim in claims:
        if (
            not isinstance(claim, dict)
            or set(claim)
            != {
                "amount_column",
                "currency_column",
                "evidence_basis",
                "amount_header_literal",
                "currency_header_literal",
                "consumer_contract",
            }
            or claim.get("evidence_basis") not in _RELATION_BASES
            or claim.get("consumer_contract") != _CONSUMER_CONTRACT
            or headers.get(claim.get("amount_column"))
            != claim.get("amount_header_literal")
            or headers.get(claim.get("currency_column"))
            != claim.get("currency_header_literal")
        ):
            raise RuntimeError("ordinary_trade_mapping_relation_claim_invalid")
        claimed_bindings.append(
            {
                "amount_column": claim["amount_column"],
                "currency_column": claim["currency_column"],
            }
        )
    if claimed_bindings != mapping["amount_currency_bindings"]:
        raise RuntimeError("ordinary_trade_mapping_relation_coverage_invalid")


def validate_qualified_mapping(
    *, mapping: dict[str, Any], receipt: dict[str, Any]
) -> None:
    """Verify that executable source semantics have a matching frozen receipt."""

    _validate_qualification(mapping=mapping, receipt=receipt)


_QUALIFIED_ENTRIES = tuple(
    _compile_qualified_entry(spec=spec, relation_claims=claims)
    for spec, claims in zip(_MAPPING_SPECS, _RELATION_CLAIMS, strict=True)
)
_QUALIFIED_MAPPINGS = tuple(item[0] for item in _QUALIFIED_ENTRIES)
_QUALIFICATION_RECEIPTS = tuple(item[1] for item in _QUALIFIED_ENTRIES)


class OrdinaryTradeQualifiedMappingAuthorityFactory:
    @staticmethod
    def create() -> "OrdinaryTradeQualifiedMappingAuthority":
        return OrdinaryTradeQualifiedMappingAuthority()


class OrdinaryTradeQualifiedMappingAuthority:
    def list_mappings(self) -> list[dict[str, Any]]:
        for mapping, receipt in _QUALIFIED_ENTRIES:
            _validate_qualification(mapping=mapping, receipt=receipt)
        return copy.deepcopy(list(_QUALIFIED_MAPPINGS))

    def list_qualification_receipts(self) -> list[dict[str, Any]]:
        for mapping, receipt in _QUALIFIED_ENTRIES:
            _validate_qualification(mapping=mapping, receipt=receipt)
        return copy.deepcopy(list(_QUALIFICATION_RECEIPTS))


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "QUALIFICATION_SCHEMA_VERSION",
    "OrdinaryTradeQualifiedMappingAuthority",
    "OrdinaryTradeQualifiedMappingAuthorityFactory",
    "validate_qualified_mapping",
]
