from __future__ import annotations

import asyncio

from broker_reports_gate1.ordinary_trade_grouped_mapping_v14 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV14AdapterFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_runtime import (
    OrdinaryTradeAutomaticMappingRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_issue312_mapping_runtime as runtime_fixtures


def _runtime(*, store, client, mapping_response_adapter=None):
    return OrdinaryTradeAutomaticMappingRuntimeFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        **runtime_fixtures._mapping_prompt_dependencies(),
        mapping_response_adapter=mapping_response_adapter,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
    ).create()


def _grouped_response(*, table: dict, mapping: dict) -> dict:
    response = case_fixtures._complete(table, mapping)
    response["schema_version"] = (
        ORDINARY_TRADE_GROUPED_MAPPING_V14_RESPONSE_SCHEMA_VERSION
    )
    decision = response["table_decisions"][0]
    del decision["row_dispositions"]
    decision["row_policy"] = {
        "default_disposition": "SECURITY_TRADES",
        "exception_rows": [],
    }
    return response


def test_grouped_v14_reaches_existing_v13_semantic_owner(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    client = runtime_fixtures.BoundaryModelClient(
        [_grouped_response(table=table, mapping=mapping)]
    )

    result = asyncio.run(
        _runtime(
            store=store,
            client=client,
            mapping_response_adapter=(
                OrdinaryTradeGroupedMappingV14AdapterFactory.create()
            ),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "COMPLETE"
    assert result["provider_calls_this_turn"] == 1
    assert len(client.calls) == 1
    assert client.calls[0]["response_format"]["json_schema"]["name"].endswith(
        "_v14"
    )
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["status"] == "COMPLETE"


def test_grouped_v14_binds_header_before_row_policy_expansion(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _grouped_response(table=table, mapping=mapping)
    response["table_decisions"][0]["header_row"] = 2
    client = runtime_fixtures.BoundaryModelClient([response])

    result = asyncio.run(
        _runtime(
            store=store,
            client=client,
            mapping_response_adapter=(
                OrdinaryTradeGroupedMappingV14AdapterFactory.create()
            ),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "COMPLETE"
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    resolution = saved["table_resolutions"][0]
    assert resolution["header_row"] == 1
    assert resolution["security_trade_rows"][0] == 2


def test_grouped_v14_discards_only_canonical_header_row_exception(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _grouped_response(table=table, mapping=mapping)
    response["table_decisions"][0]["row_policy"]["exception_rows"] = [
        {"row": 1, "disposition": "NO_NAMED_CONSUMER"},
    ]
    result = asyncio.run(
        _runtime(
            store=store,
            client=runtime_fixtures.BoundaryModelClient([response]),
            mapping_response_adapter=(
                OrdinaryTradeGroupedMappingV14AdapterFactory.create()
            ),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "COMPLETE"
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["table_resolutions"][0]["security_trade_rows"] == [2, 3]


def test_malformed_grouped_v14_stops_before_projection_or_fact_persistence(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _grouped_response(table=table, mapping=mapping)
    response["table_decisions"][0]["row_policy"]["default_disposition"] = (
        "NO_NAMED_CONSUMER"
    )
    canonical_before = store.get_active_canonical_version(
        context=context, document_id=document_id
    ).manifest_ref
    client = runtime_fixtures.BoundaryModelClient([response])

    result = asyncio.run(
        _runtime(
            store=store,
            client=client,
            mapping_response_adapter=(
                OrdinaryTradeGroupedMappingV14AdapterFactory.create()
            ),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    assert store.get_active_canonical_version(
        context=context, document_id=document_id
    ).manifest_ref == canonical_before
    assert store.list_by_type(
        context.normalization_run_id,
        ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    ) == []
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["status"] == "MAPPING_OUTPUT_INVALID"
    assert saved["reason_code"] == (
        "ordinary_trade_grouped_mapping_v14_row_policy_invalid"
    )
    assert "mapping_outcome" not in saved


def test_default_runtime_keeps_v13_response_contract(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    client = runtime_fixtures.BoundaryModelClient(
        [case_fixtures._complete(table, mapping)]
    )

    result = asyncio.run(
        _runtime(store=store, client=client).resolve(
            document_id=document_id,
            context=context,
        )
    )

    assert result["status"] == "COMPLETE"
    assert client.calls[0]["response_format"] == (
        OrdinaryTradeSemanticMappingFactory.create().mapping_response_format()
    )
