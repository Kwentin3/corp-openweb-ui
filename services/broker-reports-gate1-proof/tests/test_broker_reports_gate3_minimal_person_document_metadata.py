"""G5.60 closed-world person and document metadata contract."""

from __future__ import annotations

from broker_reports_gate1.gate3_metadata_source_facts import (
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
    GATE3_MINIMAL_METADATA_FACT_TYPES,
    GATE3_MINIMAL_METADATA_SOURCE_EXAMPLE_STATUS,
    _metadata_facts,
)


def _text_facts(text: str) -> list[dict]:
    return _metadata_facts(
        artifact={
            "nodes": [
                {
                    "node_id": "text_metadata",
                    "node_type": "TEXT",
                    "source_refs": ["text_source"],
                    "content": {"text": text},
                }
            ]
        },
        document_id="brdoc_test",
        canonical_version_id="brcanon_test",
    )


def _cell(row: int, column: int, value: str, *, merged: str | None = None) -> dict:
    return {
        "row": row,
        "column": column,
        "displayed_value": value,
        "merged_range": merged,
        "source_refs": [f"cell_{row}_{column}"],
    }


def _table_facts(*cells: dict) -> list[dict]:
    return _metadata_facts(
        artifact={
            "nodes": [
                {
                    "node_id": "table_metadata",
                    "node_type": "TABLE",
                    "source_refs": ["table_source"],
                    "content": {"cells": list(cells)},
                }
            ]
        },
        document_id="brdoc_test",
        canonical_version_id="brcanon_test",
    )


def test_contract_is_versioned_closed_and_real_source_qualified() -> None:
    assert GATE3_MINIMAL_METADATA_CONTRACT_VERSION == "1.0.0"
    assert GATE3_MINIMAL_METADATA_FACT_TYPES == (
        "PARTY_NAME",
        "PERSON_BIRTH_DATE",
        "TAXPAYER_TAX_IDENTIFIER",
        "PERSON_CITIZENSHIP",
        "DOCUMENT_TYPE",
        "DOCUMENT_NUMBER",
        "DOCUMENT_DATE",
        "STATEMENT_PERIOD",
        "BROKER_LEGAL_NAME",
        "ACCOUNT_IDENTIFIER",
        "ACCOUNT_CONTRACT_IDENTIFIER",
    )
    assert GATE3_MINIMAL_METADATA_SOURCE_EXAMPLE_STATUS == {
        "PARTY_NAME": "REAL_SOURCE_EXAMPLE",
        "PERSON_BIRTH_DATE": "NO_REAL_SOURCE_EXAMPLE",
        "TAXPAYER_TAX_IDENTIFIER": "NO_REAL_SOURCE_EXAMPLE",
        "PERSON_CITIZENSHIP": "NO_REAL_SOURCE_EXAMPLE",
        "DOCUMENT_TYPE": "REAL_SOURCE_EXAMPLE",
        "DOCUMENT_NUMBER": "NO_REAL_SOURCE_EXAMPLE",
        "DOCUMENT_DATE": "REAL_SOURCE_EXAMPLE",
        "STATEMENT_PERIOD": "REAL_SOURCE_EXAMPLE",
        "BROKER_LEGAL_NAME": "REAL_SOURCE_EXAMPLE",
        "ACCOUNT_IDENTIFIER": "REAL_SOURCE_EXAMPLE",
        "ACCOUNT_CONTRACT_IDENTIFIER": "REAL_SOURCE_EXAMPLE",
    }


def test_qualified_explicit_header_text_publishes_only_supported_meanings() -> None:
    facts = _text_facts(
        "\n".join(
            (
                "Отчет брокера",
                "Брокер: Example Broker",
                "Клиент: Анна Тестова",
                "Дата формирования отчета: 31.12.2025",
                "Период: 01.01.2025 - 31.12.2025",
                "Номер счета: ACCOUNT-9",
                "Генеральное соглашение: CONTRACT-7",
            )
        )
    )

    assert {fact["fact_type"] for fact in facts} == {
        "DOCUMENT_TYPE",
        "BROKER_LEGAL_NAME",
        "PARTY_NAME",
        "DOCUMENT_DATE",
        "STATEMENT_PERIOD",
        "ACCOUNT_IDENTIFIER",
        "ACCOUNT_CONTRACT_IDENTIFIER",
    }
    assert len(facts) == 7
    assert all(
        fact["source_binding"]["source_refs"] == ["text_source"] for fact in facts
    )


def test_no_real_source_example_fields_have_no_production_pattern() -> None:
    facts = _text_facts(
        "\n".join(
            (
                "Дата рождения: 01.02.1980",
                "ИНН налогоплательщика: 123456789012",
                "Гражданство: Российская Федерация",
                "Номер документа: PASSPORT-7",
            )
        )
    )

    assert facts == []


def test_unsupported_metadata_remains_unchanged_in_canonical_input() -> None:
    artifact = {
        "nodes": [
            {
                "node_id": "unsupported_metadata",
                "node_type": "TEXT",
                "source_refs": ["unsupported_source"],
                "content": {
                    "text": "Email: person@example.test\nЯзык документа: русский"
                },
            }
        ]
    }
    before = artifact.copy()
    before["nodes"] = [
        {**artifact["nodes"][0], "content": dict(artifact["nodes"][0]["content"])}
    ]

    facts = _metadata_facts(
        artifact=artifact,
        document_id="brdoc_test",
        canonical_version_id="brcanon_test",
    )

    assert facts == []
    assert artifact == before


def test_operation_date_year_and_unknown_date_label_are_not_document_metadata() -> None:
    assert (
        _text_facts(
            "Дата операции: 31.12.2025\nНалоговый год: 2025\nКонтрольная дата: 01.01.2025"
        )
        == []
    )


def test_unlabelled_person_and_organization_inn_do_not_acquire_person_roles() -> None:
    facts = _text_facts(
        "Анна Тестова\nИНН/КПП брокера: 1234567890 / 123456789\n"
        "ОГРН / ИНН: 1234567890 (INN) / 1234567890123 (OGRN)"
    )

    assert facts == []


def test_document_title_suffix_is_not_guessed_to_be_issuer() -> None:
    facts = _text_facts("Брокерский отчет за период проверки")

    assert [fact["fact_type"] for fact in facts] == ["DOCUMENT_TYPE"]


def test_account_column_preserves_multiplicity_and_semantically_deduplicates() -> None:
    facts = _table_facts(
        _cell(1, 1, "Номер счета"),
        _cell(1, 2, "Владелец счета"),
        _cell(1, 3, "Валюта"),
        _cell(2, 1, "ACCOUNT-1"),
        _cell(2, 2, "Анна Тестова"),
        _cell(2, 3, "RUB"),
        _cell(3, 1, "ACCOUNT-2"),
        _cell(3, 2, "Анна Тестова"),
        _cell(3, 3, "USD"),
        _cell(4, 1, "ACCOUNT-1"),
        _cell(4, 2, "Анна Тестова"),
        _cell(4, 3, "RUB"),
    )

    assert [fact["value"]["normalized"] for fact in facts] == [
        "ACCOUNT-1",
        "ACCOUNT-2",
    ]
    assert all(fact["fact_type"] == "ACCOUNT_IDENTIFIER" for fact in facts)
    assert all(
        fact["source_binding"]["binding_kind"] == "explicit_column_header_values"
        for fact in facts
    )


def test_ambiguous_or_merged_account_columns_fail_closed() -> None:
    assert (
        _table_facts(
            _cell(1, 1, "Номер счета"),
            _cell(1, 2, "Account number"),
            _cell(1, 3, "Amount"),
            _cell(2, 1, "ACCOUNT-1"),
            _cell(2, 2, "ACCOUNT-2"),
            _cell(2, 3, "10"),
        )
        == []
    )
    assert (
        _table_facts(
            _cell(1, 1, "Номер счета", merged="R1C1:R1C2"),
            _cell(1, 2, "Amount"),
            _cell(2, 1, "ACCOUNT-1"),
            _cell(2, 2, "10"),
        )
        == []
    )


def test_citizenship_never_creates_tax_residency() -> None:
    facts = _text_facts(
        "Гражданство: Российская Федерация\nНалоговое резидентство: Россия"
    )

    assert facts == []
    assert all(fact["fact_type"] != "TAX_RESIDENCY" for fact in facts)


def test_transaction_contract_header_is_not_current_document_contract() -> None:
    assert _text_facts("Номер договора // Тип операции // Дата операции") == []


def test_person_name_and_document_date_remain_distinct_typed_facts() -> None:
    facts = _text_facts("Клиент: Анна Тестова\nДата формирования отчета: 2025-12-31")

    assert [(fact["fact_type"], fact["value"]["kind"]) for fact in facts] == [
        ("PARTY_NAME", "text"),
        ("DOCUMENT_DATE", "date"),
    ]


def test_explicit_report_period_accepts_source_timestamps_without_inventing_dates() -> (
    None
):
    facts = _text_facts(
        "Отчет брокера за период\n" "2024-12-31 23:59:59 - 2025-12-31 23:59:59"
    )

    period = next(fact for fact in facts if fact["fact_type"] == "STATEMENT_PERIOD")
    assert period["value"] == {
        "kind": "period",
        "start": "2024-12-31",
        "end": "2025-12-31",
    }
