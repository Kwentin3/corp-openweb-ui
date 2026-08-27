from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.gate2_model_contracts import Gate2StructuredModelResult
from broker_reports_gate1.ordinary_trade_mapping_runtime import (
    OrdinaryTradeAutomaticMappingRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_projection import OrdinaryTradeProjectionFactory
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    ANSWER_RESPONSE_SCHEMA_VERSION,
    MAPPING_RESPONSE_SCHEMA_VERSION,
)

import test_broker_reports_issue312_mapping_case as case_fixtures


class BoundaryModelClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return Gate2StructuredModelResult(
            content=output,
            execution_metadata=case_fixtures._metadata(),
        )


def _runtime(store, client):
    return OrdinaryTradeAutomaticMappingRuntimeFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
    ).create()


@pytest.mark.asyncio
async def test_one_strict_mapping_call_completes_unknown_schema(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    client = BoundaryModelClient([case_fixtures._complete(table, mapping)])

    result = await _runtime(store, client).resolve(
        document_id=document_id,
        context=context,
    )

    assert result["status"] == "COMPLETE"
    assert result["provider_calls_this_turn"] == 1
    assert len(client.calls) == 1
    assert client.calls[0]["response_format"]["json_schema"]["strict"] is True


@pytest.mark.asyncio
async def test_clarification_answer_confirmation_resumes_same_case(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    question = {
        "question_id": "q_money_role",
        "table_node_id": table["node_id"],
        "question": "Какая колонка содержит общую сумму сделки?",
        "options": [
            {"option_id": "o_first", "label": "Первая денежная колонка"},
            {"option_id": "o_second", "label": "Вторая денежная колонка"},
        ],
    }
    complete = case_fixtures._complete(table, mapping)
    client = BoundaryModelClient(
        [
            {
                "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
                "status": "CLARIFICATION_REQUIRED",
                "table_decisions": [],
                "clarification": question,
                "message": "Нужно уточнить денежные колонки.",
            },
            {
                "schema_version": ANSWER_RESPONSE_SCHEMA_VERSION,
                "status": "CANDIDATE",
                "option_id": "o_second",
                "message": "Я понял: общая сумма во второй колонке.",
                "evidence_quote": "во второй",
            },
            complete,
        ]
    )
    runtime = _runtime(store, client)
    first = await runtime.resolve(document_id=document_id, context=context)
    assert first["status"] == "CLARIFICATION_REQUIRED"

    candidate = await runtime.resolve(
        document_id=document_id,
        context=context,
        user_message="Общая сумма во второй.",
    )
    assert candidate["status"] == "CONFIRMATION_REQUIRED"
    assert candidate["public_state"]["confirmation_message"].startswith("Я понял")

    completed = await runtime.resolve(
        document_id=document_id,
        context=context,
        confirmation=True,
        expected_confirmation_artifact_id=candidate["mapping_case_artifact_id"],
    )
    assert completed["status"] == "COMPLETE"
    assert len(client.calls) == 3
    mapping_package = client.calls[-1]["package"]
    assert mapping_package["case"]["confirmed_understandings"][0]["label"] == (
        "Вторая денежная колонка"
    )


@pytest.mark.asyncio
async def test_provider_failure_and_invalid_output_are_distinct_terminals(
    tmp_path,
) -> None:
    first = case_fixtures._unknown_case(tmp_path / "provider")
    store, context, document_id = first[:3]
    unavailable = await _runtime(
        store, BoundaryModelClient([RuntimeError("network unavailable")])
    ).resolve(document_id=document_id, context=context)
    assert unavailable["status"] == "PROVIDER_UNAVAILABLE"
    assert unavailable["public_state"]["may_resume"] is True

    second = case_fixtures._unknown_case(tmp_path / "invalid")
    store2, context2, document_id2, _canonical, _binding, table2, mapping2 = second
    forged = case_fixtures._complete(table2, mapping2)
    forged["table_decisions"][0]["side_values"] = [
        {"source_literal": "INVENTED", "normalized_value": "PURCHASE"}
    ]
    invalid = await _runtime(
        store2, BoundaryModelClient([copy.deepcopy(forged)])
    ).resolve(document_id=document_id2, context=context2)
    assert invalid["status"] == "MAPPING_OUTPUT_INVALID"
    assert invalid["public_state"]["may_resume"] is False


@pytest.mark.asyncio
async def test_production_composition_maps_unknown_then_publishes_facts(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    mapping_client = BoundaryModelClient([case_fixtures._complete(table, mapping)])
    answer_client = BoundaryModelClient([])
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        mapping_model_client=mapping_client,
        mapping_answer_model_client=answer_client,
        mapping_model_id="models/gemini-3.5-flash",
        mapping_provider_profile_id="google_gemini",
    ).create()
    canonical_ref = store.get_active_canonical_version(
        context=context, document_id=document_id
    ).manifest_ref

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref],
        context=context,
    )

    assert result["semantic_mapping"]["status"] == "COMPLETE"
    assert result["provider_calls_total"] == 1
    assert result["product"]["gate4"]["security_facts_total"] == 2
    assert result["product"]["gate4"]["transaction_charge_facts_total"] == 2
    assert result["product"]["terminal"] != (
        "ordinary_trade_declaration_canonical_relevant_unmapped"
    )
    assert len(mapping_client.calls) == 1
    assert answer_client.calls == []


@pytest.mark.asyncio
async def test_known_schema_fast_path_has_zero_semantic_calls(tmp_path) -> None:
    store, context, document_id, _mapping = case_fixtures.candidate._case(tmp_path)
    mapping_client = BoundaryModelClient([])
    answer_client = BoundaryModelClient([])
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        mapping_model_client=mapping_client,
        mapping_answer_model_client=answer_client,
        mapping_model_id="models/gemini-3.5-flash",
        mapping_provider_profile_id="google_gemini",
    ).create()
    canonical_ref = store.get_active_canonical_version(
        context=context, document_id=document_id
    ).manifest_ref

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref],
        context=context,
    )

    assert result["provider_calls_total"] == 0
    assert "semantic_mapping" not in result
    assert mapping_client.calls == []
    assert answer_client.calls == []


@pytest.mark.asyncio
async def test_unfinished_mapping_publishes_no_partial_fact_v2(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, _mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    client = BoundaryModelClient(
        [
            {
                "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
                "status": "CLARIFICATION_REQUIRED",
                "table_decisions": [],
                "clarification": {
                    "question_id": "q_money_role",
                    "table_node_id": table["node_id"],
                    "question": "Какая колонка содержит общую сумму?",
                    "options": [
                        {"option_id": "o_first", "label": "Первая"},
                        {"option_id": "o_second", "label": "Вторая"},
                    ],
                },
                "message": "Нужно одно уточнение.",
            }
        ]
    )
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        mapping_model_client=client,
        mapping_answer_model_client=BoundaryModelClient([]),
        mapping_model_id="models/gemini-3.5-flash",
        mapping_provider_profile_id="google_gemini",
    ).create()
    canonical_ref = store.get_active_canonical_version(
        context=context, document_id=document_id
    ).manifest_ref

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref], context=context
    )

    assert result["semantic_mapping"]["status"] == "CLARIFICATION_REQUIRED"
    assert result["product"]["gate4"]["facts_total"] == 0
    assert result["product"]["status"] == "INPUT_REQUIRED"
    assert result["product"]["gate5"]["security_tax_input_status"] == (
        "SOURCE_MAPPING_INCOMPLETE"
    )


@pytest.mark.asyncio
async def test_no_named_consumer_retains_observations_without_fact_v2(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, _mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    client = BoundaryModelClient(
        [
            {
                "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
                "status": "COMPLETE",
                "table_decisions": [
                    {
                        "table_node_id": table["node_id"],
                        "header_row": 1,
                        "disposition": "NO_NAMED_CONSUMER",
                        "columns": [],
                        "amount_currency_bindings": [],
                        "side_values": [],
                    }
                ],
                "clarification": None,
                "message": "No named downstream consumer for this table.",
            }
        ]
    )
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        mapping_model_client=client,
        mapping_answer_model_client=BoundaryModelClient([]),
        mapping_model_id="models/gemini-3.5-flash",
        mapping_provider_profile_id="google_gemini",
    ).create()
    canonical_ref = store.get_active_canonical_version(
        context=context, document_id=document_id
    ).manifest_ref

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref], context=context
    )

    assert result["semantic_mapping"]["status"] == "COMPLETE"
    assert result["product"]["gate4"]["facts_total"] == 0
    projection = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().current_case(context=context)[0][1]
    observations = projection["source_observations"]
    assert observations
    assert {item["disposition"] for item in observations} == {
        "SOURCE_RETAINED_NO_CONSUMER"
    }
    assert all(item["fields"] for item in observations)
