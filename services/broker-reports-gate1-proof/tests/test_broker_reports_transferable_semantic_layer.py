from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import qualify_transferable_broker_semantic_layer as layer  # noqa: E402


def _context() -> dict:
    roles = [
        "asset_name",
        "trade_date",
        "side",
        "quantity",
        "currency",
        "unit_price",
        "currency",
        "gross_amount",
        "broker_commission",
        "broker_commission",
        "trade_id",
    ]
    return {
        "logical_table_id": "g001",
        "table_identity": {"source_ref": "h_title", "literal": "Trades"},
        "headers": [
            {
                "source_ref": f"h{index}",
                "column": index,
                "literal": f"header {index}",
            }
            for index, _ in enumerate(roles, 1)
        ],
        "roles": roles,
    }


def _mapping(context: dict) -> dict:
    return {
        "logical_table_id": context["logical_table_id"],
        "table_type": "SECURITY_TRADES",
        "columns": [
            {
                "header_ref": header["source_ref"],
                "normalized_role": role,
            }
            for header, role in zip(
                context["headers"], context["roles"], strict=True
            )
        ],
    }


def _cells(context: dict, *, trade_id: str = "event-1") -> dict[int, dict]:
    literals = [
        "Asset",
        "2026-01-01",
        "Buy",
        "2",
        "USD",
        "10",
        "EUR",
        "20",
        "1",
        "2",
        trade_id,
    ]
    return {
        header["column"]: {
            "source_ref": f"c{header['column']}",
            "literal": literal,
        }
        for header, literal in zip(context["headers"], literals, strict=True)
    }


def test_repeated_roles_are_preserved_as_distinct_source_fields() -> None:
    context = _context()

    contract = layer.compile_field_contract(
        context=context,
        mapping=_mapping(context),
    )

    currencies = [
        field for field in contract["fields"] if field["semantic_role"] == "currency"
    ]
    commissions = [
        field
        for field in contract["fields"]
        if field["semantic_role"] == "broker_commission"
    ]
    assert len(currencies) == 2
    assert len(commissions) == 2
    assert len({field["source_field_id"] for field in contract["fields"]}) == len(
        contract["fields"]
    )
    assert layer.compile_field_contract(
        context=copy.deepcopy(context),
        mapping=copy.deepcopy(_mapping(context)),
    ) == contract


def test_header_reorder_fails_closed() -> None:
    context = _context()
    mapping = _mapping(context)
    mapping["columns"] = list(reversed(mapping["columns"]))

    with pytest.raises(
        layer.SemanticLayerQualificationError,
        match="field_contract_header_order",
    ):
        layer.compile_field_contract(context=context, mapping=mapping)


def test_equal_values_do_not_merge_source_observations() -> None:
    context = _context()
    contract = layer.compile_field_contract(
        context=context,
        mapping=_mapping(context),
    )
    cells = _cells(context)

    first = layer._observation(
        canonical_root_sha256="a" * 64,
        field_contract=contract,
        row=3,
        cells=cells,
        disposition="RUNTIME_READY",
        perspective_ref="section-a",
    )
    second = layer._observation(
        canonical_root_sha256="a" * 64,
        field_contract=contract,
        row=4,
        cells=cells,
        disposition="RUNTIME_READY",
        perspective_ref="section-b",
    )

    layer._validate_source_accounting([first, second], 2)
    assert first["observation_id"] != second["observation_id"]
    assert [field["literal"] for field in first["fields"]] == [
        field["literal"] for field in second["fields"]
    ]


def test_runtime_binding_copies_values_and_keeps_both_commissions() -> None:
    context = _context()
    contract = layer.compile_field_contract(
        context=context,
        mapping=_mapping(context),
    )
    observation = layer._observation(
        canonical_root_sha256="b" * 64,
        field_contract=contract,
        row=3,
        cells=_cells(context),
        disposition="RUNTIME_READY",
        perspective_ref="section-a",
    )

    facts = layer.materialize_trade_facts(
        observation=observation,
        field_contract=contract,
        side_by_literal={"Buy": "PURCHASE"},
    )

    assert [fact["record_type"] for fact in facts] == [
        "SECURITY_PURCHASE",
        "TRANSACTION_CHARGE",
        "TRANSACTION_CHARGE",
    ]
    trade_currency = next(
        role for role in facts[0]["roles"] if role["role"] == "currency"
    )
    assert trade_currency["literal_fragment"] == "EUR"
    assert layer._validate_runtime_lineage(
        observations=[observation], facts=facts
    ) == (14, 14)


def test_ambiguous_runtime_relation_fails_closed() -> None:
    context = _context()
    context["headers"][4]["column"] = 9
    contract = layer.compile_field_contract(
        context=context,
        mapping=_mapping(context),
    )
    observation = layer._observation(
        canonical_root_sha256="c" * 64,
        field_contract=contract,
        row=3,
        cells=_cells(context),
        disposition="RUNTIME_READY",
        perspective_ref="section-a",
    )

    with pytest.raises(
        layer.SemanticLayerQualificationError,
        match="runtime_gross_currency_ambiguous",
    ):
        layer.materialize_trade_facts(
            observation=observation,
            field_contract=contract,
            side_by_literal={"Buy": "PURCHASE"},
        )


def test_first_persisted_valid_h3_is_chronological_not_best_of_n() -> None:
    context = _context()
    mapping = _mapping(context)
    raw = json.dumps(
        {
            "schema_version": "saved_h3",
            "classifications": [
                {
                    "assertion_id": mapping["logical_table_id"],
                    "table_type": mapping["table_type"],
                    "columns": mapping["columns"],
                }
            ],
        }
    )
    runs = [
        {"ordinal": 1, "h3": {"raw_model_output": None}},
        {"ordinal": 2, "h3": {"raw_model_output": raw}},
        {"ordinal": 3, "h3": {"raw_model_output": raw}},
    ]

    ordinal, restored = layer.first_persisted_valid_h3(
        private_runs=runs,
        contexts=[context],
    )

    assert ordinal == 2
    assert restored == [mapping]
