from __future__ import annotations

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from broker_reports_gate1.gate2_model_clients import Gate2StructuredModelClientFactory
from broker_reports_gate1.gate2_model_contracts import Gate2StructuredModelClientConfig
from broker_reports_gate1.gate2_model_requests import (
    ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
)

from scripts.canonical_financial_role_mapping_research import (
    ResearchMappingError,
    active_role_inventory,
    apply_contract,
    build_table_surface,
    compose_request,
    extract_tables,
    response_schema,
    safe_result,
    score_contract,
    validate_response,
)


def _table(rows: list[list[str]], *, node_id: str = "table-node") -> dict:
    columns = list(range(1, len(rows[0]) + 1))
    return {
        "table_node_id": node_id,
        "columns": columns,
        "rows": [
            {
                "row": row_number,
                "cells": [
                    {"column": column, "literal": literal}
                    for column, literal in zip(columns, values, strict=True)
                ],
            }
            for row_number, values in enumerate(rows, start=1)
        ],
    }


def _trade_table(*, incomplete: bool = False) -> dict:
    second_asset = "" if incomplete else "BBB"
    return _table(
        [
            ["Date", "Operation", "Security", "Qty", "Price", "Amount", "Currency"],
            ["2025-01-15", "Buy", "AAA", "10", "100.00", "1000.00", "USD"],
            ["2025-01-16", "Sell", second_asset, "5", "110.00", "550.00", "USD"],
        ]
    )


def _trade_contract(table: dict, *, include_sell: bool = True) -> dict:
    surface = build_table_surface(table, table_ref="table_1", variant="full_table")
    values = {
        item["literal"]: item["value_ref"]
        for profile in surface["column_profiles"]
        if profile["column_ref"] == "c2"
        for item in profile["categorical_values"]
    }
    categories = [
        {"column_ref": "c2", "value_ref": values["Buy"], "normalized_value": "PURCHASE"}
    ]
    if include_sell:
        categories.append(
            {"column_ref": "c2", "value_ref": values["Sell"], "normalized_value": "DISPOSAL"}
        )
    return {
        "schema_version": "broker_reports_research_table_role_mapping_v1",
        "table_ref": "table_1",
        "table_kind": "ORDINARY_SECURITY_TRADES",
        "header_row": 1,
        "columns": [
            {"column_ref": "c1", "role": "trade_date"},
            {"column_ref": "c2", "role": "side"},
            {"column_ref": "c3", "role": "asset_name"},
            {"column_ref": "c4", "role": "quantity"},
            {"column_ref": "c5", "role": "unit_price"},
            {"column_ref": "c6", "role": "gross_amount"},
            {"column_ref": "c7", "role": "currency"},
        ],
        "amount_currency_bindings": [
            {"amount_column_ref": "c6", "currency_column_ref": "c7"}
        ],
        "categorical_normalizations": categories,
    }


def test_role_inventory_is_reused_from_active_mapping_owner() -> None:
    roles = active_role_inventory()
    assert "trade_date" in roles
    assert "gross_amount" in roles
    assert "unmapped" in roles
    assert len(roles) == len(set(roles))


def test_extract_tables_preserves_every_literal_and_row() -> None:
    canonical = {
        "nodes": [
            {
                "node_type": "TABLE",
                "node_id": "n1",
                "content": {
                    "cells": [
                        {"row": 1, "column": 1, "displayed_value": "Header"},
                        {"row": 2, "column": 1, "displayed_value": "Value"},
                    ]
                },
            }
        ]
    }
    before = copy.deepcopy(canonical)
    tables = extract_tables(canonical)
    assert tables[0]["rows"][1]["cells"][0]["literal"] == "Value"
    assert canonical == before


def test_header_plus_profiles_exposes_all_low_cardinality_values_beyond_64() -> None:
    rows = [["Operation", "Amount"]]
    for repetition in range(5):
        rows.extend([[f"Kind {index}", str(index + repetition)] for index in range(65)])
    table = _table(rows)
    surface = build_table_surface(
        table, table_ref="table_1", variant="header_plus_profiles"
    )
    operation = next(
        item for item in surface["column_profiles"] if item["column_ref"] == "c1"
    )
    assert operation["categorical_values_fully_exposed"] is True
    assert len(operation["categorical_values"]) == 66
    assert surface["rows_total"] == 326


def test_surfaces_have_distinct_and_bounded_meaning() -> None:
    table = _trade_table()
    header = build_table_surface(table, table_ref="table_1", variant="header_only")
    profile = build_table_surface(
        table, table_ref="table_1", variant="header_plus_profiles"
    )
    full = build_table_surface(table, table_ref="table_1", variant="full_table")
    assert "column_profiles" not in header
    assert "all_rows" not in profile
    assert len(full["all_rows"]) == len(table["rows"])
    assert len({header["surface_sha256"], profile["surface_sha256"], full["surface_sha256"]}) == 3


def test_response_schema_is_closed_and_dynamic() -> None:
    schema = response_schema(table=_trade_table(), table_ref="table_1")
    assert schema["additionalProperties"] is False
    assert schema["properties"]["table_ref"] == {"type": "string", "const": "table_1"}
    assert schema["properties"]["columns"]["minItems"] == 7
    assert schema["properties"]["columns"]["maxItems"] == 7


def test_complete_contract_accounts_every_row_and_binds_currency() -> None:
    table = _trade_table()
    contract = _trade_contract(table)
    application = apply_contract(table=table, contract=contract, table_ref="table_1")
    assert application["terminal"] == "COMPLETE"
    assert application["rows_accounted"] == application["rows_total"] == 3
    assert application["row_status_counts"] == {
        "OBSERVATION": 2,
        "STRUCTURAL_HEADER": 1,
    }
    assert len(application["observations"]) == 2
    gross = next(
        binding
        for binding in application["observations"][0]["bindings"]
        if binding["role"] == "gross_amount"
    )
    assert gross["currency_column"] == 7


def test_unknown_categorical_value_fails_closed_without_losing_row() -> None:
    table = _trade_table()
    contract = _trade_contract(table, include_sell=False)
    application = apply_contract(table=table, contract=contract, table_ref="table_1")
    assert application["terminal"] == "RELEVANT_UNMAPPED"
    assert application["rows_accounted"] == 3
    assert application["row_status_counts"] == {
        "OBSERVATION": 1,
        "RELEVANT_UNMAPPED": 1,
        "STRUCTURAL_HEADER": 1,
    }


def test_incomplete_financial_row_fails_closed_regardless_of_missing_role_count() -> None:
    table = _trade_table(incomplete=True)
    contract = _trade_contract(table)
    application = apply_contract(table=table, contract=contract, table_ref="table_1")
    assert application["terminal"] == "RELEVANT_UNMAPPED"
    assert application["relevant_unmapped"] == 1
    assert application["rows_accounted"] == 3


def test_unsupported_financial_table_has_explicit_terminal_and_zero_observations() -> None:
    table = _table(
        [
            ["Payment date", "Security", "Dividend", "Tax", "Currency"],
            ["2025-01-15", "GAZP", "1000.00", "130.00", "RUB"],
        ]
    )
    contract = {
        "schema_version": "broker_reports_research_table_role_mapping_v1",
        "table_ref": "table_1",
        "table_kind": "OTHER_FINANCIAL_EVENTS",
        "header_row": 1,
        "columns": [
            {"column_ref": "c1", "role": "trade_date"},
            {"column_ref": "c2", "role": "asset_name"},
            {"column_ref": "c3", "role": "unmapped"},
            {"column_ref": "c4", "role": "unmapped"},
            {"column_ref": "c5", "role": "currency"},
        ],
        "amount_currency_bindings": [],
        "categorical_normalizations": [],
    }
    application = apply_contract(table=table, contract=contract, table_ref="table_1")
    assert application["terminal"] == "EXPLICIT_UNSUPPORTED"
    assert application["row_status_counts"] == {
        "EXPLICIT_UNSUPPORTED": 1,
        "STRUCTURAL_HEADER": 1,
    }
    assert application["observations"] == []


def test_structurally_compound_trade_table_stops_explicitly() -> None:
    table = _table(
        [
            ["Trade Date", "Description", "Type Quantity Price", "Amount"],
            ["2025-01-15", "AAA", "Purchase 10 100.00", "1000.00"],
        ]
    )
    contract = {
        "schema_version": "broker_reports_research_table_role_mapping_v1",
        "table_ref": "table_1",
        "table_kind": "STRUCTURALLY_INCOMPATIBLE",
        "header_row": 1,
        "columns": [
            {"column_ref": "c1", "role": "trade_date"},
            {"column_ref": "c2", "role": "asset_name"},
            {"column_ref": "c3", "role": "unmapped"},
            {"column_ref": "c4", "role": "gross_amount"},
        ],
        "amount_currency_bindings": [],
        "categorical_normalizations": [],
    }
    application = apply_contract(table=table, contract=contract, table_ref="table_1")
    assert application["terminal"] == "EXPLICIT_UNSUPPORTED"
    assert application["row_status_counts"] == {
        "EXPLICIT_UNSUPPORTED": 1,
        "STRUCTURAL_HEADER": 1,
    }


def test_amount_currency_binding_is_required_only_for_executable_trade() -> None:
    table = _trade_table()
    missing = _trade_contract(table)
    missing["amount_currency_bindings"] = []
    with pytest.raises(ResearchMappingError) as exc:
        validate_response(raw_response=missing, table=table, table_ref="table_1")
    assert exc.value.code == "research_response_currency_binding_invalid"


def test_duplicate_or_reordered_columns_are_rejected() -> None:
    table = _trade_table()
    duplicate = _trade_contract(table)
    duplicate["columns"][1] = copy.deepcopy(duplicate["columns"][0])
    with pytest.raises(ResearchMappingError) as exc:
        validate_response(raw_response=duplicate, table=table, table_ref="table_1")
    assert exc.value.code == "research_response_column_coverage_invalid"


def test_request_contains_no_model_permission_to_create_rows_or_facts() -> None:
    request = compose_request(
        table=_trade_table(), table_ref="table_1", variant="header_plus_profiles"
    )
    instruction = request["messages"][0]["content"]
    assert "Do not label individual rows" in instruction
    assert "create financial facts" in instruction
    assert [item["role"] for item in request["messages"]] == ["system", "user"]
    assert request["response_format"]["json_schema"]["strict"] is True


def test_request_crosses_the_owned_provider_seam_exactly_once() -> None:
    table = _trade_table()
    request = compose_request(
        table=table, table_ref="table_1", variant="header_plus_profiles"
    )
    response = _trade_contract(table)
    captured: list[dict] = []

    def complete(*, form_data, **_kwargs):
        captured.append(copy.deepcopy(form_data))
        return {
            "id": "research-local-seam-response",
            "model": "models/gemini-3.5-flash",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(response, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
        }

    user = SimpleNamespace(id="research-user")
    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
            provider_profile_id="google_gemini",
        ),
        user=user,
        request=SimpleNamespace(),
        completion_resolver=lambda _user_id: (complete, user),
    ).create()
    result = asyncio.run(
        client.extract(
            prompt=SimpleNamespace(
                content=request["messages"][0]["content"],
                prompt_ref="research:local-seam",
                hash="research-local-seam-prompt-hash",
            ),
            package=json.loads(request["messages"][1]["content"]),
            model_id="models/gemini-3.5-flash",
            response_format=request["response_format"],
        )
    )

    assert len(captured) == 1
    assert json.loads(result.content) == response


def test_scoring_and_safe_projection_are_observable_not_snapshot_only() -> None:
    table = _trade_table()
    reference = _trade_contract(table)
    candidate = copy.deepcopy(reference)
    score = score_contract(candidate=candidate, reference=reference)
    application = apply_contract(table=table, contract=candidate, table_ref="table_1")
    request = compose_request(
        table=table, table_ref="table_1", variant="header_plus_profiles"
    )
    safe = safe_result(
        table=table,
        surface_variant="header_plus_profiles",
        request=request,
        contract=candidate,
        application=application,
        metrics={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )
    assert score["contract_exact"] is True
    assert score["amount_currency_bindings_exact"] is True
    assert safe["terminal"] == "COMPLETE"
    assert safe["rows_accounted"] == 3
    assert safe["private_values_committed"] is False
    assert "observations" in safe and safe["observations"] == 2
