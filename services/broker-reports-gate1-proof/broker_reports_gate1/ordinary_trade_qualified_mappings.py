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


QUALIFICATION_SCHEMA_VERSION = "broker_reports_ordinary_trade_mapping_qualification_v2"
CASE_QUALIFICATION_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_case_mapping_qualification_v1"
)
_CONSUMER_CONTRACT = "Gate4FinancialCaseFactV2.amount_currency"
_RELATION_BASES = {
    "EXPLICIT_DENOMINATION_HEADER",
    "REVIEWED_SCHEMA_SCOPE",
}
_REVIEW_DECISION = "ADMITTED_AS_REVIEWED_SCHEMA_INTERPRETATION"
_REVIEWED_EVIDENCE = "EXACT_TITLE_AND_COMPLETE_ORDERED_HEADER_SET"
_EXCLUDED_REVIEW_BASES = [
    "COLUMN_PROXIMITY",
    "ROW_VALUE_EQUALITY",
    "CROSS_TABLE_RECONCILIATION",
    "DOWNSTREAM_RESULT",
    "BROKER_OR_FILENAME_IDENTITY",
]


def _review_record(*, review_id: str, question: str, rationale: str) -> dict[str, Any]:
    return {
        "review_id": review_id,
        "reviewed_evidence": _REVIEWED_EVIDENCE,
        "question": question,
        "decision": _REVIEW_DECISION,
        "rationale": rationale,
        "excluded_bases": copy.deepcopy(_EXCLUDED_REVIEW_BASES),
    }


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
            "evidence_basis": "REVIEWED_SCHEMA_SCOPE",
            "amount_header_literal": "Сумма",
            "currency_header_literal": "Валюта",
            "consumer_contract": _CONSUMER_CONTRACT,
            "review_record": _review_record(
                review_id="sber_trade_sum_currency_review_v1",
                question=(
                    "Does the exact trade-table schema assign the unqualified "
                    "currency column 6 to amount column 10?"
                ),
                rationale=(
                    "The complete ordered schema exposes one unqualified currency "
                    "field and no competing denomination field. Column 10 is the "
                    "row's monetary sum. The relation is admitted as a reviewed "
                    "schema convention, not as direct denomination wording."
                ),
            ),
        },
        {
            "amount_column": 12,
            "currency_column": 6,
            "evidence_basis": "REVIEWED_SCHEMA_SCOPE",
            "amount_header_literal": "Комиссия Брокера",
            "currency_header_literal": "Валюта",
            "consumer_contract": _CONSUMER_CONTRACT,
            "review_record": _review_record(
                review_id="sber_broker_commission_currency_review_v1",
                question=(
                    "Does the exact trade-table schema assign the unqualified "
                    "currency column 6 to broker-commission column 12?"
                ),
                rationale=(
                    "The complete ordered schema exposes one unqualified currency "
                    "field for the trade row and no separate commission currency. "
                    "The relation is admitted as a reviewed schema convention, "
                    "not from position or repeated RUB values."
                ),
            ),
        },
        {
            "amount_column": 13,
            "currency_column": 6,
            "evidence_basis": "REVIEWED_SCHEMA_SCOPE",
            "amount_header_literal": "Комиссия Биржи",
            "currency_header_literal": "Валюта",
            "consumer_contract": _CONSUMER_CONTRACT,
            "review_record": _review_record(
                review_id="sber_exchange_commission_currency_review_v1",
                question=(
                    "Does the exact trade-table schema assign the unqualified "
                    "currency column 6 to exchange-commission column 13?"
                ),
                rationale=(
                    "The complete ordered schema exposes one unqualified currency "
                    "field for the trade row and no separate commission currency. "
                    "The relation is admitted as a reviewed schema convention, "
                    "not from position or repeated RUB values."
                ),
            ),
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
            "evidence_basis": "REVIEWED_SCHEMA_SCOPE",
            "amount_header_literal": "Комиссия Банка за расчет по сделке",
            "currency_header_literal": "Валюта расчетов",
            "consumer_contract": _CONSUMER_CONTRACT,
            "review_record": _review_record(
                review_id="vtb_settlement_commission_currency_review_v1",
                question=(
                    "Does the exact trade-table schema assign settlement-currency "
                    "column 7 to bank settlement-commission column 10?"
                ),
                rationale=(
                    "The complete schema explicitly limits column 5 to price or "
                    "nominal currency and separately names column 7 as settlement "
                    "currency. Column 10 is a settlement charge and exposes no "
                    "independent denomination. The relation is a reviewed schema "
                    "interpretation, not direct wording in the commission header."
                ),
            ),
        },
        {
            "amount_column": 11,
            "currency_column": 7,
            "evidence_basis": "REVIEWED_SCHEMA_SCOPE",
            "amount_header_literal": "Комиссия Банка за заключение сделки",
            "currency_header_literal": "Валюта расчетов",
            "consumer_contract": _CONSUMER_CONTRACT,
            "review_record": _review_record(
                review_id="vtb_trade_commission_currency_review_v1",
                question=(
                    "Does the exact trade-table schema assign settlement-currency "
                    "column 7 to bank trade-commission column 11?"
                ),
                rationale=(
                    "The complete schema explicitly limits column 5 to price or "
                    "nominal currency and separately names column 7 as settlement "
                    "currency. The bank commission is a monetary charge in that "
                    "settlement schema and exposes no independent denomination. "
                    "The relation is a reviewed interpretation, not direct header "
                    "wording."
                ),
            ),
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
        "amount_currency_bindings": copy.deepcopy(spec["amount_currency_bindings"]),
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
        "supporting_decision_scope": ["columns", "side_values"],
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
        "supporting_decision_scope",
        "consumer_contracts",
        "qualification_id",
        "receipt_sha256",
    }
    if (
        set(receipt) != expected_keys
        or receipt.get("schema_version") != QUALIFICATION_SCHEMA_VERSION
        or receipt.get("status") != "QUALIFIED"
        or receipt.get("structural_fingerprint") != mapping["structural_fingerprint"]
        or receipt.get("supporting_decision_scope") != ["columns", "side_values"]
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
            or re.fullmatch(r"[0-9a-f]{64}", decision["response_sha256"]) is None
        ):
            raise RuntimeError("ordinary_trade_mapping_supporting_decision_invalid")
    headers = {item["column"]: item["header_literal"] for item in mapping["columns"]}
    claims = receipt.get("relation_claims")
    if not isinstance(claims, list):
        raise RuntimeError("ordinary_trade_mapping_relation_claim_invalid")
    claimed_bindings: list[dict[str, int]] = []
    review_ids: set[str] = set()
    for claim in claims:
        evidence_basis = (
            claim.get("evidence_basis") if isinstance(claim, dict) else None
        )
        claim_keys = {
            "amount_column",
            "currency_column",
            "evidence_basis",
            "amount_header_literal",
            "currency_header_literal",
            "consumer_contract",
        }
        if evidence_basis == "REVIEWED_SCHEMA_SCOPE":
            claim_keys.add("review_record")
        if (
            not isinstance(claim, dict)
            or set(claim) != claim_keys
            or evidence_basis not in _RELATION_BASES
            or claim.get("consumer_contract") != _CONSUMER_CONTRACT
            or headers.get(claim.get("amount_column"))
            != claim.get("amount_header_literal")
            or headers.get(claim.get("currency_column"))
            != claim.get("currency_header_literal")
        ):
            raise RuntimeError("ordinary_trade_mapping_relation_claim_invalid")
        if evidence_basis == "REVIEWED_SCHEMA_SCOPE":
            review = claim.get("review_record")
            if (
                not isinstance(review, dict)
                or set(review)
                != {
                    "review_id",
                    "reviewed_evidence",
                    "question",
                    "decision",
                    "rationale",
                    "excluded_bases",
                }
                or not isinstance(review.get("review_id"), str)
                or not review["review_id"]
                or review["review_id"] in review_ids
                or review.get("reviewed_evidence") != _REVIEWED_EVIDENCE
                or review.get("decision") != _REVIEW_DECISION
                or not isinstance(review.get("question"), str)
                or not review["question"].strip()
                or not isinstance(review.get("rationale"), str)
                or not review["rationale"].strip()
                or review.get("excluded_bases") != _EXCLUDED_REVIEW_BASES
            ):
                raise RuntimeError("ordinary_trade_mapping_relation_review_invalid")
            review_ids.add(review["review_id"])
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


def qualify_case_mapping(
    *,
    title_literal: str | None,
    headers: list[dict[str, Any]],
    model_columns: list[dict[str, Any]],
    amount_currency_bindings: list[dict[str, int]],
    side_values: list[dict[str, str]],
    case_scope: dict[str, str],
    model_decision: dict[str, str],
    confirmed_understandings: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Admit one model-proposed mapping only for its authenticated case scope."""

    provisional = compile_schema_mapping(
        title_literal=title_literal,
        headers=headers,
        model_columns=model_columns,
        amount_currency_bindings=amount_currency_bindings,
        side_values=side_values,
        qualification_ref={
            "qualification_id": "otqual_" + "0" * 32,
            "receipt_sha256": "0" * 64,
        },
    )
    semantic_scope = {
        "columns": provisional["columns"],
        "amount_currency_bindings": provisional["amount_currency_bindings"],
        "side_values": provisional["side_values"],
    }
    headers_by_column = {
        item["column"]: item["header_literal"] for item in provisional["columns"]
    }
    material = {
        "schema_version": CASE_QUALIFICATION_SCHEMA_VERSION,
        "status": "QUALIFIED_FOR_CASE",
        "case_scope": copy.deepcopy(case_scope),
        "structural_fingerprint": provisional["structural_fingerprint"],
        "evidence_surface": {
            "title_literal": provisional["title_literal"],
            "headers": copy.deepcopy(headers),
        },
        "semantic_scope_sha256": _sha256_json(semantic_scope),
        "relation_claims": [
            {
                "amount_column": item["amount_column"],
                "currency_column": item["currency_column"],
                "amount_header_literal": headers_by_column[item["amount_column"]],
                "currency_header_literal": headers_by_column[item["currency_column"]],
                "evidence_basis": "MODEL_PROPOSED_CASE_SCOPE",
                "consumer_contract": _CONSUMER_CONTRACT,
            }
            for item in provisional["amount_currency_bindings"]
        ],
        "model_decision": copy.deepcopy(model_decision),
        "confirmed_understandings": copy.deepcopy(confirmed_understandings),
        "consumer_contracts": [_CONSUMER_CONTRACT],
        "global_reuse_allowed": False,
    }
    qualification_id = "otqual_" + _sha256_json(material)[:32]
    receipt = {**material, "qualification_id": qualification_id}
    receipt["receipt_sha256"] = _sha256_json(receipt)
    mapping = compile_schema_mapping(
        title_literal=title_literal,
        headers=headers,
        model_columns=model_columns,
        amount_currency_bindings=amount_currency_bindings,
        side_values=side_values,
        qualification_ref={
            "qualification_id": qualification_id,
            "receipt_sha256": receipt["receipt_sha256"],
        },
    )
    validate_case_qualified_mapping(
        mapping=mapping,
        receipt=receipt,
        expected_case_scope=case_scope,
    )
    return mapping, receipt


def validate_case_qualified_mapping(
    *,
    mapping: dict[str, Any],
    receipt: dict[str, Any],
    expected_case_scope: dict[str, str],
) -> None:
    """Validate case qualification without promoting it to the global registry."""

    validate_schema_mapping(mapping)
    expected_keys = {
        "schema_version",
        "status",
        "case_scope",
        "structural_fingerprint",
        "evidence_surface",
        "semantic_scope_sha256",
        "relation_claims",
        "model_decision",
        "confirmed_understandings",
        "consumer_contracts",
        "global_reuse_allowed",
        "qualification_id",
        "receipt_sha256",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != expected_keys
        or receipt.get("schema_version") != CASE_QUALIFICATION_SCHEMA_VERSION
        or receipt.get("status") != "QUALIFIED_FOR_CASE"
        or receipt.get("case_scope") != expected_case_scope
        or receipt.get("structural_fingerprint")
        != mapping["structural_fingerprint"]
        or receipt.get("consumer_contracts") != [_CONSUMER_CONTRACT]
        or receipt.get("global_reuse_allowed") is not False
    ):
        raise RuntimeError("ordinary_trade_case_mapping_qualification_invalid")
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
        raise RuntimeError("ordinary_trade_case_mapping_qualification_hash_invalid")
    id_material = copy.deepcopy(frozen)
    qualification_id = id_material.pop("qualification_id", None)
    if qualification_id != "otqual_" + _sha256_json(id_material)[:32]:
        raise RuntimeError("ordinary_trade_case_mapping_qualification_identity_invalid")
    expected_surface = {
        "title_literal": mapping["title_literal"],
        "headers": [
            {"column": item["column"], "literal": item["header_literal"]}
            for item in mapping["columns"]
        ],
    }
    if receipt.get("evidence_surface") != expected_surface:
        raise RuntimeError("ordinary_trade_case_mapping_surface_invalid")
    scope = {
        "columns": mapping["columns"],
        "amount_currency_bindings": mapping["amount_currency_bindings"],
        "side_values": mapping["side_values"],
    }
    if receipt.get("semantic_scope_sha256") != _sha256_json(scope):
        raise RuntimeError("ordinary_trade_case_mapping_scope_invalid")
    model_decision = receipt.get("model_decision")
    if (
        not isinstance(model_decision, dict)
        or set(model_decision)
        != {
            "model_id",
            "provider_profile_id",
            "response_sha256",
            "execution_metadata_sha256",
        }
        or not all(isinstance(value, str) and value for value in model_decision.values())
        or any(
            re.fullmatch(r"[0-9a-f]{64}", model_decision[key]) is None
            for key in ("response_sha256", "execution_metadata_sha256")
        )
    ):
        raise RuntimeError("ordinary_trade_case_mapping_model_decision_invalid")
    understandings = receipt.get("confirmed_understandings")
    if not isinstance(understandings, list):
        raise RuntimeError("ordinary_trade_case_mapping_confirmation_invalid")
    for item in understandings:
        if (
            not isinstance(item, dict)
            or set(item) != {"question_id", "option_id", "label_sha256"}
            or not all(isinstance(value, str) and value for value in item.values())
            or re.fullmatch(r"[0-9a-f]{64}", item["label_sha256"]) is None
        ):
            raise RuntimeError("ordinary_trade_case_mapping_confirmation_invalid")
    headers_by_column = {
        item["column"]: item["header_literal"] for item in mapping["columns"]
    }
    expected_claims = [
        {
            "amount_column": item["amount_column"],
            "currency_column": item["currency_column"],
            "amount_header_literal": headers_by_column[item["amount_column"]],
            "currency_header_literal": headers_by_column[item["currency_column"]],
            "evidence_basis": "MODEL_PROPOSED_CASE_SCOPE",
            "consumer_contract": _CONSUMER_CONTRACT,
        }
        for item in mapping["amount_currency_bindings"]
    ]
    if receipt.get("relation_claims") != expected_claims:
        raise RuntimeError("ordinary_trade_case_mapping_relation_coverage_invalid")


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

    def qualify_case_mapping(self, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        return qualify_case_mapping(**kwargs)

    def validate_case_mapping(
        self,
        *,
        mapping: dict[str, Any],
        receipt: dict[str, Any],
        expected_case_scope: dict[str, str],
    ) -> None:
        validate_case_qualified_mapping(
            mapping=mapping,
            receipt=receipt,
            expected_case_scope=expected_case_scope,
        )


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "QUALIFICATION_SCHEMA_VERSION",
    "CASE_QUALIFICATION_SCHEMA_VERSION",
    "OrdinaryTradeQualifiedMappingAuthority",
    "OrdinaryTradeQualifiedMappingAuthorityFactory",
    "validate_qualified_mapping",
    "qualify_case_mapping",
    "validate_case_qualified_mapping",
]
