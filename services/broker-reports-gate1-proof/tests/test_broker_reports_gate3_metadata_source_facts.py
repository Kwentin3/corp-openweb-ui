"""G5.59 fail-closed metadata label-to-value table binding."""

from __future__ import annotations

from broker_reports_gate1.gate3_metadata_source_facts import _metadata_facts


def _cell(row: int, column: int, value: str, *, merged: str | None = None) -> dict:
    return {
        "row": row,
        "column": column,
        "displayed_value": value,
        "merged_range": merged,
        "source_refs": [f"cell_{row}_{column}"],
    }


def _facts(*cells: dict) -> list[dict]:
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


def test_supported_labels_bind_only_the_adjacent_value_cell() -> None:
    facts = _facts(
        _cell(1, 1, "Клиент"),
        _cell(1, 2, "Анна Тестова"),
        _cell(2, 1, "Номер счета"),
        _cell(2, 2, "ACCOUNT-9"),
        _cell(3, 1, "За период"),
        _cell(3, 2, "01.01.2025 - 31.12.2025"),
    )

    assert [fact["fact_type"] for fact in facts] == [
        "PARTY_NAME",
        "ACCOUNT_IDENTIFIER",
        "STATEMENT_PERIOD",
    ]
    assert all(
        fact["source_binding"]["binding_kind"] == "adjacent_table_label_value"
        for fact in facts
    )
    assert facts[0]["source_binding"]["label_field_path"] == "content.cells[0]"
    assert facts[0]["source_binding"]["field_path"] == "content.cells[1]"
    assert facts[0]["source_binding"]["source_refs"] == [
        "cell_1_1",
        "cell_1_2",
        "table_source",
    ]


def test_value_shape_never_assigns_a_metadata_type_without_a_supported_label() -> None:
    assert (
        _facts(
            _cell(1, 1, "Периодически"),
            _cell(1, 2, "01.01.2025 - 31.12.2025"),
            _cell(2, 1, "Идентификатор из неизвестного словаря"),
            _cell(2, 2, "ACCOUNT-9"),
        )
        == []
    )


def test_empty_or_missing_side_never_crosses_into_the_next_row() -> None:
    assert (
        _facts(
            _cell(1, 1, "Код клиента"),
            _cell(1, 2, ""),
            _cell(2, 1, ""),
            _cell(2, 2, "CLIENT-17"),
        )
        == []
    )


def test_ambiguous_or_merged_rows_fail_closed() -> None:
    assert (
        _facts(
            _cell(1, 1, "Код клиента"),
            _cell(1, 2, "CLIENT-17"),
            _cell(1, 3, "another candidate"),
            _cell(2, 1, "Номер счета", merged="R2C1:R2C2"),
            _cell(2, 2, "ACCOUNT-9"),
            _cell(3, 1, "Код клиента"),
            _cell(3, 2, "CLIENT-17"),
            _cell(3, 2, "duplicate coordinate"),
        )
        == []
    )


def test_explicit_account_column_preserves_each_value_without_cross_column_binding() -> (
    None
):
    facts = _facts(
        _cell(1, 1, "Account number"),
        _cell(1, 2, "Account holder"),
        _cell(1, 3, "Amount"),
        _cell(2, 1, "ACCOUNT-9"),
        _cell(2, 2, "Customer Name"),
        _cell(2, 3, "100.00"),
    )

    assert [fact["fact_type"] for fact in facts] == ["ACCOUNT_IDENTIFIER"]
    assert facts[0]["source_binding"]["binding_kind"] == (
        "explicit_column_header_values"
    )


def test_label_cell_cannot_supply_the_value_for_an_adjacent_binding() -> None:
    assert _facts(
        _cell(1, 1, "Номер счета: ACCOUNT-OLD"),
        _cell(1, 2, "ACCOUNT-NEW"),
    )[
        0
    ]["value"] == {"kind": "text", "normalized": "ACCOUNT-OLD"}
    assert all(
        fact["source_binding"].get("binding_kind") != "adjacent_table_label_value"
        for fact in _facts(
            _cell(1, 1, "Номер счета: ACCOUNT-OLD"),
            _cell(1, 2, "ACCOUNT-NEW"),
        )
    )
