from __future__ import annotations

import asyncio
import json

import pytest

from broker_reports_gate1.ordinary_trade_grouped_mapping_v20 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV20AdapterFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_runtime import (
    OrdinaryTradeAutomaticMappingRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    OrdinaryTradeProjectionFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_issue312_mapping_runtime as runtime_fixtures
import test_broker_reports_ordinary_trade_production_candidate as candidate_fixtures
import broker_reports_gate1.ordinary_trade_semantic_mapping as semantic_module


def _runtime(*, store, client):
    return OrdinaryTradeAutomaticMappingRuntimeFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        mapping_response_adapter=OrdinaryTradeGroupedMappingV20AdapterFactory.create(),
        **runtime_fixtures._mapping_prompt_dependencies(),
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
    ).create()


def _v20_response(*, table: dict, mapping: dict, policy: dict) -> dict:
    decision = case_fixtures._complete(table, mapping)["table_decisions"][0]
    del decision["row_dispositions"]
    decision["row_policy"] = policy
    return {
        "schema_version": ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
        "status": "COMPLETE",
        "table_decisions": [decision],
        "clarification": None,
        "message": "complete",
        "explicit_header_source_claims": {
            "schema_version": (
                "broker_reports_ordinary_trade_explicit_header_source_response_v1"
            ),
            "claims": [],
        },
    }


def test_v20_full_ordered_columns_complete_and_compile_projection(tmp_path) -> None:
    """A complete V20 column contract reaches the existing projection owner."""

    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v20_response(
        table=table,
        mapping=mapping,
        policy={"default_disposition": "SECURITY_TRADES", "exception_rows": []},
    )
    client = runtime_fixtures.BoundaryModelClient([response])

    result = asyncio.run(
        _runtime(store=store, client=client).resolve(
            document_id=document_id, context=context
        )
    )

    assert result["status"] == "COMPLETE"
    assert result["provider_calls_this_turn"] == 1
    assert len(client.calls) == 1
    projections = OrdinaryTradeProjectionFactory(store=store, read_enabled=True).create()
    projection = projections.compile_and_save(document_id=document_id, context=context)
    assert projection.artifact_type == ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE
    projection_payload = projections.read(
        artifact_id=projection.artifact_id, context=context
    )
    assert projection_payload["runtime_records"]
    assert projection_payload["qualified_table_resolutions"][0]["disposition"] == (
        "SECURITY_TRADES"
    )


@pytest.mark.parametrize("malformation", ["omit", "duplicate", "reorder", "invent"])
def test_v20_malformed_columns_stay_terminal_and_never_project(
    tmp_path, malformation: str
) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v20_response(
        table=table,
        mapping=mapping,
        policy={"default_disposition": "SECURITY_TRADES", "exception_rows": []},
    )
    columns = response["table_decisions"][0]["columns"]
    if malformation == "omit":
        columns.pop()
    elif malformation == "duplicate":
        columns[-1] = dict(columns[0])
    elif malformation == "reorder":
        columns.reverse()
    else:
        columns[0] = {**columns[0], "column": 987654321}

    result = asyncio.run(
        _runtime(
            store=store,
            client=runtime_fixtures.BoundaryModelClient([response]),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["reason_code"] == "ordinary_trade_semantic_mapping_columns_invalid"
    assert store.list_by_type(
        context.normalization_run_id,
        ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    ) == []


def test_mapping_output_invalid_public_state_has_only_closed_failure_reason(
    tmp_path,
) -> None:
    """The user-facing state may diagnose a class, never private mapping data."""

    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v20_response(
        table=table,
        mapping=mapping,
        policy={"default_disposition": "SECURITY_TRADES", "exception_rows": []},
    )
    response["message"] = "provider-private-value-987654321"
    response["table_decisions"][0]["columns"][0] = {
        **response["table_decisions"][0]["columns"][0],
        "column": 987654321,
    }

    result = asyncio.run(
        _runtime(
            store=store,
            client=runtime_fixtures.BoundaryModelClient([response]),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    public = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().public_state(document_id=document_id, context=context)
    assert public is not None
    assert public["mapping_failure_reason"] == "mapping_columns_invalid"
    exposed = json.dumps(public, ensure_ascii=False, sort_keys=True)
    assert "ordinary_trade_semantic_mapping_columns_invalid" not in exposed
    assert "provider-private-value-987654321" not in exposed
    assert "987654321" not in exposed


def test_mapping_output_invalid_public_state_uses_generic_closed_fallback(
    tmp_path,
) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    cases.save_provider_terminal(
        document_id=document_id,
        context=context,
        status="MAPPING_OUTPUT_INVALID",
        reason_code="provider-message-with-value-987654321",
        message="private terminal message",
        provider_calls_total=0,
    )

    public = cases.public_state(document_id=document_id, context=context)
    assert public is not None
    assert public["mapping_failure_reason"] == "mapping_output_invalid"
    exposed = json.dumps(public, ensure_ascii=False, sort_keys=True)
    assert "provider-message-with-value-987654321" not in exposed
    assert "987654321" not in exposed


@pytest.mark.parametrize(
    ("policy", "category"),
    [
        (
            {"default_disposition": "NO_NAMED_CONSUMER", "exception_rows": []},
            "policy_object_invalid",
        ),
        (
            {
                "default_disposition": "SECURITY_TRADES",
                "exception_rows": [
                    {"row": 987654321, "disposition": "SECURITY_TRADES"}
                ],
            },
            "exception_item_invalid",
        ),
        (
            {
                "default_disposition": "SECURITY_TRADES",
                "exception_rows": [
                    {"row": 3, "disposition": "NO_NAMED_CONSUMER"},
                    {"row": 3, "disposition": "NO_NAMED_CONSUMER"},
                ],
            },
            "exception_rows_not_strictly_ordered",
        ),
        (
            {
                "default_disposition": "SECURITY_TRADES",
                "exception_rows": [
                    {"row": 987654321, "disposition": "NO_NAMED_CONSUMER"}
                ],
            },
            "exception_row_outside_data_rows",
        ),
    ],
)
def test_v20_persists_only_closed_row_policy_shape_category_and_stays_fail_closed(
    tmp_path, policy: dict, category: str
) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v20_response(table=table, mapping=mapping, policy=policy)

    result = asyncio.run(
        _runtime(
            store=store,
            client=runtime_fixtures.BoundaryModelClient([response]),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["reason_code"] == (
        "ordinary_trade_grouped_mapping_v20_row_policy_invalid:" + category
    )
    # The durable mapping case has control state only: no rejected source row,
    # provider message, or model response is retained for this diagnostic.
    persisted = json.dumps(saved, ensure_ascii=False, sort_keys=True)
    assert "987654321" not in persisted
    assert response["message"] not in persisted
    assert store.list_by_type(
        context.normalization_run_id,
        ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    ) == []


def test_v20_batch_receipt_keeps_only_safe_row_policy_category(
    tmp_path, monkeypatch
) -> None:
    store, context, document_id, canonical, _binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    tables = [node for node in canonical["nodes"] if node["node_type"] == "TABLE"]
    monkeypatch.setattr(
        semantic_module,
        "_MAX_CELLS_TOTAL",
        max(len(table["content"]["cells"]) for table in tables),
    )
    responses = []
    for table in tables:
        headers = tuple(
            cell["displayed_value"]
            for cell in sorted(table["content"]["cells"], key=lambda cell: cell["column"])
            if cell["row"] == 1
        )
        responses.append(
            _v20_response(
                table=table,
                mapping=candidate_fixtures._mapping_from_headers(headers),
                policy={
                    "default_disposition": "SECURITY_TRADES",
                    "exception_rows": [
                        {"row": 987654321, "disposition": "NO_NAMED_CONSUMER"}
                    ],
                },
            )
        )
    client = runtime_fixtures.BoundaryModelClient(responses)
    runtime = runtime_fixtures._runtime(store, client)
    runtime._mapping_response_adapter = OrdinaryTradeGroupedMappingV20AdapterFactory.create()

    result = asyncio.run(runtime.resolve(document_id=document_id, context=context))

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    assert len(client.calls) == 1
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["reason_code"] == (
        "ordinary_trade_grouped_mapping_v20_row_policy_invalid:"
        "exception_row_outside_data_rows"
    )
    assert "987654321" not in json.dumps(saved, ensure_ascii=False, sort_keys=True)
    assert store.list_by_type(
        context.normalization_run_id,
        ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    ) == []
