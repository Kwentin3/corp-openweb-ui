from __future__ import annotations

import asyncio

from broker_reports_gate1.ordinary_trade_grouped_mapping_v15 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV15AdapterFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_runtime import (
    OrdinaryTradeAutomaticMappingRuntimeFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_issue312_mapping_runtime as runtime_fixtures


def _runtime(*, store, client):
    return OrdinaryTradeAutomaticMappingRuntimeFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        **runtime_fixtures._mapping_prompt_dependencies(),
        mapping_response_adapter=OrdinaryTradeGroupedMappingV15AdapterFactory.create(),
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
    ).create()


def _grouped_response(*, table: dict, mapping: dict) -> dict:
    response = case_fixtures._complete(table, mapping)
    response["schema_version"] = ORDINARY_TRADE_GROUPED_MAPPING_V15_RESPONSE_SCHEMA_VERSION
    decision = response["table_decisions"][0]
    del decision["row_dispositions"]
    decision["row_policy"] = {
        "default_disposition": "SECURITY_TRADES",
        "exception_rows": [],
    }
    return response


def test_grouped_v15_expands_to_current_semantic_owner(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    client = runtime_fixtures.BoundaryModelClient(
        [_grouped_response(table=table, mapping=mapping)]
    )

    result = asyncio.run(
        _runtime(store=store, client=client).resolve(
            document_id=document_id,
            context=context,
        )
    )

    assert result["status"] == "COMPLETE"
    assert client.calls[0]["response_format"]["json_schema"]["name"].endswith(
        "_v15"
    )
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["status"] == "COMPLETE"


def test_grouped_v15_rejects_a_v14_wire_response(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _grouped_response(table=table, mapping=mapping)
    response["schema_version"] = "broker_reports_ordinary_trade_grouped_mapping_response_v14"
    result = asyncio.run(
        _runtime(
            store=store,
            client=runtime_fixtures.BoundaryModelClient([response]),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
