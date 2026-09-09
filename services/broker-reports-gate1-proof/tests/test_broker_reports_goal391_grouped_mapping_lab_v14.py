from __future__ import annotations

import copy
import hashlib

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
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerError,
)
from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    ordinary_trade_mapping_prompt_hash,
)

import test_broker_reports_issue312_semantic_mapping_contract as v13_contract


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


def test_grouped_prompt_hash_cannot_match_a_v13_pin() -> None:
    content = "Map exactly. {{ordinary_trade_mapping_case_json}}"

    assert ordinary_trade_mapping_prompt_hash(content) != ordinary_trade_mapping_prompt_hash(
        content,
        output_schema_id=GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION,
        output_schema_version=GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION,
    )


def _complete_grouped_trade_response(table: dict, known: dict) -> dict:
    response = v13_contract._complete_response(table, known)
    response["schema_version"] = GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION
    decision = response["table_decisions"][0]
    del decision["row_dispositions"]
    decision["row_policy"] = {
        "default_disposition": "SECURITY_TRADES",
        "exception_rows": [],
    }
    return response


def _validate_complete_grouped_trade_response(
    *, context, canonical, binding, response: dict
) -> dict:
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    package = semantic.build_mapping_package(
        canonical=canonical, confirmed_understandings=[]
    )
    expanded = expand_grouped_response(response=response, package=package)
    return semantic.validate_mapping_response(
        response=expanded,
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=v13_contract._metadata(),
        confirmed_understandings=[],
        user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
    )


def test_grouped_trade_response_preserves_complete_explicit_currency_bindings(tmp_path) -> None:
    context, canonical, binding, table, known = v13_contract._canonical_case(tmp_path)

    result = _validate_complete_grouped_trade_response(
        context=context,
        canonical=canonical,
        binding=binding,
        response=_complete_grouped_trade_response(table, known),
    )

    assert result["status"] == "COMPLETE"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda decision: decision.update(amount_currency_bindings=[]),
        lambda decision: decision.update(
            amount_currency_bindings=decision["amount_currency_bindings"][:-1]
        ),
        lambda decision: decision["amount_currency_bindings"].append(
            copy.deepcopy(decision["amount_currency_bindings"][0])
        ),
        lambda decision: decision["amount_currency_bindings"][0].update(
            currency_column=decision["amount_currency_bindings"][0]["amount_column"]
        ),
    ],
)
def test_grouped_trade_response_rejects_invalid_currency_bindings(tmp_path, mutate) -> None:
    context, canonical, binding, table, known = v13_contract._canonical_case(tmp_path)
    response = _complete_grouped_trade_response(table, known)
    mutate(response["table_decisions"][0])

    with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
        _validate_complete_grouped_trade_response(
            context=context,
            canonical=canonical,
            binding=binding,
            response=response,
        )

    assert exc.value.code == "ordinary_trade_mapping_currency_binding_invalid"
