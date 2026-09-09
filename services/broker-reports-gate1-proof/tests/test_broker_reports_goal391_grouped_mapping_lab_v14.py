from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from broker_reports_gate1.goal391_grouped_mapping_lab_v14 import (
    GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION,
    Goal391GroupedMappingLabError,
    expand_grouped_response,
    grouped_mapping_response_format,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)


def _package(*, rows_total: int = 5) -> dict:
    return {
        "phase": "map",
        "case": {
            "tables": [
                {
                    "table_ref": "table_1",
                    "rows": [
                        {
                            "row": row,
                            "cells": [{"column": 1, "literal": f"cell-{row}"}],
                        }
                        for row in range(1, rows_total + 1)
                    ],
                }
            ]
        },
    }


def _trade_decision(*, policy: dict) -> dict:
    return {
        "table_ref": "table_1",
        "header_row": 1,
        "disposition": "SECURITY_TRADES",
        "columns": [],
        "amount_currency_bindings": [],
        "side_values": [],
        "row_policy": policy,
    }


def _response(*, policy: dict) -> dict:
    return {
        "schema_version": GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": "COMPLETE",
        "table_decisions": [_trade_decision(policy=policy)],
        "clarification": None,
        "message": "Structured table scope classified.",
    }


def test_grouped_contract_reuses_v13_except_for_trade_row_policy() -> None:
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    response_format = grouped_mapping_response_format(
        v13_response_format=semantic.mapping_response_format()
    )
    schema = response_format["json_schema"]["schema"]
    value = _response(
        policy={
            "default_disposition": "SECURITY_TRADES",
            "exception_rows": [{"row": 3, "disposition": "NO_NAMED_CONSUMER"}],
        }
    )

    Draft202012Validator(schema).validate(value)
    assert response_format["json_schema"]["name"].endswith("_v14")


def test_grouped_response_expands_default_and_explicit_exceptions() -> None:
    value = expand_grouped_response(
        response=_response(
            policy={
                "default_disposition": "SECURITY_TRADES",
                "exception_rows": [{"row": 3, "disposition": "NO_NAMED_CONSUMER"}],
            }
        ),
        package=_package(),
    )

    assert value["schema_version"] == MAPPING_RESPONSE_SCHEMA_VERSION
    assert value["table_decisions"][0]["row_dispositions"] == [
        {"row": 2, "disposition": "SECURITY_TRADES"},
        {"row": 3, "disposition": "NO_NAMED_CONSUMER"},
        {"row": 4, "disposition": "SECURITY_TRADES"},
        {"row": 5, "disposition": "SECURITY_TRADES"},
    ]
    assert "row_policy" not in value["table_decisions"][0]


@pytest.mark.parametrize(
    "policy",
    [
        {"default_disposition": "NO_NAMED_CONSUMER", "exception_rows": []},
        {
            "default_disposition": "SECURITY_TRADES",
            "exception_rows": [
                {"row": 3, "disposition": "NO_NAMED_CONSUMER"},
                {"row": 3, "disposition": "NO_NAMED_CONSUMER"},
            ],
        },
        {
            "default_disposition": "SECURITY_TRADES",
            "exception_rows": [{"row": 1, "disposition": "NO_NAMED_CONSUMER"}],
        },
        {
            "default_disposition": "SECURITY_TRADES",
            "exception_rows": [{"row": 9, "disposition": "NO_NAMED_CONSUMER"}],
        },
    ],
)
def test_grouped_response_rejects_non_exact_exception_scope(policy: dict) -> None:
    with pytest.raises(Goal391GroupedMappingLabError):
        expand_grouped_response(response=_response(policy=policy), package=_package())


def test_grouped_response_is_sublinear_for_large_uniform_table() -> None:
    package = _package(rows_total=42_000)
    compact = _response(
        policy={"default_disposition": "SECURITY_TRADES", "exception_rows": []}
    )
    expanded = expand_grouped_response(response=compact, package=package)

    assert len(compact["table_decisions"][0]["row_policy"]["exception_rows"]) == 0
    assert len(expanded["table_decisions"][0]["row_dispositions"]) == 41_999
