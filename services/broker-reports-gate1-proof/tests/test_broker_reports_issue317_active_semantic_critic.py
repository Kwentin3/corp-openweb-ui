from __future__ import annotations

import asyncio

from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    CRITIC_RESPONSE_SCHEMA_VERSION,
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_gate4_sql_materialization as gate4_fixtures
from test_broker_reports_issue312_mapping_runtime import BoundaryModelClient


def _column_role_decision(column: int, semantic_role: str) -> dict:
    return {
        "decision_kind": "COLUMN_ROLE",
        "table_ref": "table_1",
        "column": column,
        "semantic_role": semantic_role,
        "amount_column": None,
        "currency_column": None,
        "source_literal": None,
        "normalized_value": None,
        "disposition": None,
    }


def _clarification() -> dict:
    return {
        "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": "CLARIFICATION_REQUIRED",
        "table_decisions": [],
        "clarification": {
            "question_id": "q_trade_date",
            "table_ref": "table_1",
            "question": "Which date is the trade date?",
            "options": [
                {
                    "option_id": "o_conclusion",
                    "label": "Conclusion date",
                    "decision": _column_role_decision(1, "trade_date"),
                },
                {
                    "option_id": "o_settlement",
                    "label": "Settlement date",
                    "decision": _column_role_decision(2, "trade_date"),
                },
            ],
        },
        "message": "The proposal reports two executable alternatives.",
    }


def _critic(verdict: str, reviewed_response: dict) -> dict:
    return {
        "schema_version": CRITIC_RESPONSE_SCHEMA_VERSION,
        "verdict": verdict,
        "reviewed_response": reviewed_response,
        "message": "Independent review used the same Canonical evidence.",
    }


def _disposition_response(disposition: str, *, status: str = "COMPLETE") -> dict:
    return {
        "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": status,
        "table_decisions": [
            {
                "table_ref": "table_1",
                "disposition": disposition,
                "columns": [],
                "amount_currency_bindings": [],
                "side_values": [],
            }
        ],
        "clarification": None,
        "message": "Reviewed table disposition.",
    }


def test_critic_prompt_keeps_retained_charge_scope_narrow() -> None:
    prompt = OrdinaryTradeSemanticMappingFactory.create().critic_prompt().content
    assert "source-stated monetary charge" in prompt
    assert "otherwise complete ordinary security trade row" in prompt
    assert "not income, tax withholding" in prompt
    assert "incomplete or damaged field" in prompt
    assert "unsupported financial operation" in prompt


def _trade_with_retained_response() -> dict:
    roles = (
        "asset_name",
        "trade_date",
        "side",
        "quantity",
        "unit_price",
        "currency",
        "gross_amount",
        "retained_transaction_charge",
        "currency",
    )
    return {
        "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": "COMPLETE",
        "table_decisions": [
            {
                "table_ref": "table_1",
                "disposition": "SECURITY_TRADES",
                "columns": [
                    {"column": column, "semantic_role": role}
                    for column, role in enumerate(roles, start=1)
                ],
                "amount_currency_bindings": [
                    {"amount_column": 7, "currency_column": 6},
                    {"amount_column": 8, "currency_column": 9},
                ],
                "side_values": [
                    {"source_literal": "Buy", "normalized_value": "PURCHASE"}
                ],
            }
        ],
        "clarification": None,
        "message": "Proposed complete ordinary trade mapping.",
    }


def _document_with_rows(tmp_path, rows):
    store, context = gate4_fixtures._store_context(tmp_path)
    document_id = "issue317-critic-document"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=rows,
    )
    canonical_ref = store.get_active_canonical_version(
        context=context, document_id=document_id
    ).manifest_ref
    return store, context, document_id, canonical_ref


def _runtime(store, proposal: dict, critic: dict):
    proposal_client = BoundaryModelClient([proposal])
    critic_client = BoundaryModelClient([critic])
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        mapping_model_client=proposal_client,
        mapping_critic_model_client=critic_client,
        mapping_answer_model_client=BoundaryModelClient([]),
        mapping_model_id="models/gemini-3.5-flash",
        mapping_provider_profile_id="google_gemini",
    ).create()
    return runtime, proposal_client, critic_client


async def _obvious_ambiguity_is_resolved_without_user_question(tmp_path) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    complete = case_fixtures._complete(table, mapping)
    runtime, proposal_client, critic_client = _runtime(
        store,
        _clarification(),
        _critic("REPLACE", complete),
    )
    canonical_ref = store.get_active_canonical_version(
        context=context, document_id=document_id
    ).manifest_ref

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref], context=context
    )

    assert result["provider_calls_total"] == 2
    assert result["semantic_mapping"]["status"] == "COMPLETE"
    assert result["product"]["gate4"]["security_facts_total"] == 2
    assert len(proposal_client.calls) == len(critic_client.calls) == 1
    assert critic_client.calls[0]["package"]["case"] == (
        proposal_client.calls[0]["package"]["case"]
    )


async def _genuine_ambiguity_asks_once_and_publishes_nothing(tmp_path) -> None:
    store, context, document_id, *_rest = case_fixtures._unknown_case(tmp_path)
    proposal = _clarification()
    runtime, _proposal_client, _critic_client = _runtime(
        store,
        proposal,
        _critic("IRREDUCIBLE_AMBIGUITY", proposal),
    )
    canonical_ref = store.get_active_canonical_version(
        context=context, document_id=document_id
    ).manifest_ref

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref], context=context
    )

    assert result["provider_calls_total"] == 2
    assert result["semantic_mapping"]["status"] == "CLARIFICATION_REQUIRED"
    assert len(result["semantic_mapping"]["public_state"]["question"]["options"]) == 2
    assert result["product"]["gate4"]["facts_total"] == 0
    assert result["product"]["gate5"]["security_tax_input_status"] == (
        "SOURCE_MAPPING_INCOMPLETE"
    )


async def _safe_auxiliary_table_is_excluded_after_review(tmp_path) -> None:
    store, context, _document_id, canonical_ref = _document_with_rows(
        tmp_path,
        (
            ("Report guide", "Explanation"),
            ("Marker 1", "This marker explains how to read the report"),
        ),
    )
    proposal = _disposition_response("NO_NAMED_CONSUMER")
    runtime, _proposal_client, _critic_client = _runtime(
        store, proposal, _critic("APPROVE", proposal)
    )

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref], context=context
    )

    assert result["semantic_mapping"]["status"] == "COMPLETE"
    assert result["provider_calls_total"] == 2
    assert result["product"]["gate4"]["facts_total"] == 0


async def _dividend_table_cannot_be_silently_excluded(tmp_path) -> None:
    store, context, _document_id, canonical_ref = _document_with_rows(
        tmp_path,
        (
            ("Payment date", "Security", "Dividend", "Tax withheld", "Currency"),
            ("15.01.2025", "GAZP", "1000.00", "130.00", "RUB"),
        ),
    )
    proposal = _disposition_response("NO_NAMED_CONSUMER")
    rejected = _disposition_response(
        "UNSUPPORTED_FINANCIAL_MEANING", status="UNSUPPORTED"
    )
    runtime, _proposal_client, _critic_client = _runtime(
        store, proposal, _critic("REJECT_UNSAFE", rejected)
    )

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref], context=context
    )

    assert result["semantic_mapping"]["status"] == "UNSUPPORTED"
    assert result["provider_calls_total"] == 2
    assert result["product"]["gate4"]["facts_total"] == 0


async def _unsupported_amount_cannot_be_laundered_as_retained_charge(
    tmp_path,
) -> None:
    store, context, _document_id, canonical_ref = _document_with_rows(
        tmp_path,
        (
            (
                "Asset",
                "Trade date",
                "Side",
                "Quantity",
                "Unit price",
                "Currency",
                "Gross amount",
                "Tax withheld",
                "Withholding currency",
            ),
            ("ACME", "15.01.2025", "Buy", "10", "100", "RUB", "1000", "130", "RUB"),
        ),
    )
    proposal = _trade_with_retained_response()
    rejected = _disposition_response(
        "UNSUPPORTED_FINANCIAL_MEANING", status="UNSUPPORTED"
    )
    runtime, proposal_client, critic_client = _runtime(
        store,
        proposal,
        _critic("REJECT_UNSAFE", rejected),
    )

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref], context=context
    )

    assert result["semantic_mapping"]["status"] == "UNSUPPORTED"
    assert result["provider_calls_total"] == 2
    assert result["product"]["gate4"]["facts_total"] == 0
    assert critic_client.calls[0]["package"]["proposal"] == proposal
    assert critic_client.calls[0]["package"]["case"] == (
        proposal_client.calls[0]["package"]["case"]
    )


async def _retained_charge_row_fails_closed(
    tmp_path, *, asset: str, retained_currency: str
) -> None:
    store, context, _document_id, canonical_ref = _document_with_rows(
        tmp_path,
        (
            (
                "Asset",
                "Trade date",
                "Side",
                "Quantity",
                "Unit price",
                "Currency",
                "Gross amount",
                "Retained transaction charge",
                "Retained charge currency",
            ),
            (
                asset,
                "15.01.2025",
                "Buy",
                "10",
                "100",
                "RUB",
                "1000",
                "0.20",
                retained_currency,
            ),
        ),
    )
    proposal = _trade_with_retained_response()
    runtime, _proposal_client, _critic_client = _runtime(
        store,
        proposal,
        _critic("APPROVE", proposal),
    )

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref], context=context
    )

    assert result["semantic_mapping"]["status"] == "MAPPING_OUTPUT_INVALID"
    assert result["documents"][0]["runtime_ready_observations"] == 0
    assert result["documents"][0]["relevant_unmapped_observations"] > 0
    assert result["product"]["status"] == "PREPARATION_INCOMPLETE"
    assert result["product"]["gate4"]["facts_total"] == 0


async def _truncated_no_consumer_evidence_fails_closed(
    tmp_path, *, body_rows: int
) -> None:
    store, context, _document_id, canonical_ref = _document_with_rows(
        tmp_path,
        (
            ("Entry", "Amount"),
            *(
                (f"entry-{index}", str(index))
                for index in range(1, body_rows + 1)
            ),
        ),
    )
    proposal = _disposition_response("NO_NAMED_CONSUMER")
    runtime, proposal_client, _critic_client = _runtime(
        store, proposal, _critic("APPROVE", proposal)
    )

    result = await runtime.run_with_automatic_mapping(
        canonical_artifact_refs=[canonical_ref], context=context
    )

    model_table = proposal_client.calls[0]["package"]["case"]["tables"][0]
    assert model_table["rows_truncated"] is True
    if body_rows > 64:
        assert any(
            column["values_truncated"]
            for column in model_table["column_distinct_values"]
        )
    assert result["semantic_mapping"]["status"] == "MAPPING_OUTPUT_INVALID"
    assert result["provider_calls_total"] == 2
    assert result["product"]["gate4"]["facts_total"] == 0


def test_obvious_ambiguity_is_resolved_without_user_question(tmp_path) -> None:
    asyncio.run(_obvious_ambiguity_is_resolved_without_user_question(tmp_path))


def test_genuine_ambiguity_asks_once_and_publishes_nothing(tmp_path) -> None:
    asyncio.run(_genuine_ambiguity_asks_once_and_publishes_nothing(tmp_path))


def test_safe_auxiliary_table_is_excluded_after_review(tmp_path) -> None:
    asyncio.run(_safe_auxiliary_table_is_excluded_after_review(tmp_path))


def test_dividend_table_cannot_be_silently_excluded(tmp_path) -> None:
    asyncio.run(_dividend_table_cannot_be_silently_excluded(tmp_path))


def test_unsupported_amount_cannot_be_laundered_as_retained_charge(
    tmp_path,
) -> None:
    asyncio.run(_unsupported_amount_cannot_be_laundered_as_retained_charge(tmp_path))


def test_retained_charge_does_not_hide_incomplete_trade_row(tmp_path) -> None:
    asyncio.run(
        _retained_charge_row_fails_closed(
            tmp_path,
            asset=" ",
            retained_currency="RUB",
        )
    )


def test_retained_charge_requires_nonempty_bound_currency_in_each_row(
    tmp_path,
) -> None:
    asyncio.run(
        _retained_charge_row_fails_closed(
            tmp_path,
            asset="ACME",
            retained_currency=" ",
        )
    )


def test_rows_truncated_no_consumer_evidence_fails_closed(tmp_path) -> None:
    asyncio.run(_truncated_no_consumer_evidence_fails_closed(tmp_path, body_rows=25))


def test_values_truncated_no_consumer_evidence_fails_closed(tmp_path) -> None:
    asyncio.run(_truncated_no_consumer_evidence_fails_closed(tmp_path, body_rows=65))
