"""Frozen exact-schema mappings qualified for ordinary-trade production use.

The entries are selected only by their structural fingerprint.  Human-readable
headers remain part of the frozen semantic decision evidence; broker, year and
filename are deliberately absent from the runtime contract.
"""

from __future__ import annotations

import copy
from typing import Any


FACTORY_REQUIRED = (
    "OrdinaryTradeQualifiedMappingAuthorityFactory.create is the only "
    "production mapping authority entrypoint"
)
FORBIDDEN = (
    "broker, year or filename routing; fuzzy fingerprint reuse; runtime LLM "
    "calls; caller mutation of qualified mappings"
)


_QUALIFIED_MAPPINGS: tuple[dict[str, Any], ...] = (
    {
        "schema_version": "broker_reports_ordinary_trade_schema_mapping_v1",
        "mapping_id": "otmap_9e514852eecf75f399bb35a602c709fe",
        "structural_fingerprint": (
            "6dbe853eb449c005dcadebaf73fd62277fb24a4ec4cf15147729910a6874d039"
        ),
        "table_type": "SECURITY_TRADES",
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
        "side_values": [
            {"normalized_value": "DISPOSAL", "source_literal": "Продажа"},
            {"normalized_value": "PURCHASE", "source_literal": "Покупка"},
        ],
        "semantic_decisions": [
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
        "schema_version": "broker_reports_ordinary_trade_schema_mapping_v1",
        "mapping_id": "otmap_add25728f9093e9bd28f90e66164aefb",
        "structural_fingerprint": (
            "e1c2f174b3ae84a3eb862a98c1c72e574b53962276b30fdd8082ec7402994a49"
        ),
        "table_type": "SECURITY_TRADES",
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
        "side_values": [
            {"normalized_value": "DISPOSAL", "source_literal": "Продажа"},
            {"normalized_value": "PURCHASE", "source_literal": "Покупка"},
        ],
        "semantic_decisions": [
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


class OrdinaryTradeQualifiedMappingAuthorityFactory:
    @staticmethod
    def create() -> "OrdinaryTradeQualifiedMappingAuthority":
        return OrdinaryTradeQualifiedMappingAuthority()


class OrdinaryTradeQualifiedMappingAuthority:
    def list_mappings(self) -> list[dict[str, Any]]:
        return copy.deepcopy(list(_QUALIFIED_MAPPINGS))


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "OrdinaryTradeQualifiedMappingAuthority",
    "OrdinaryTradeQualifiedMappingAuthorityFactory",
]
