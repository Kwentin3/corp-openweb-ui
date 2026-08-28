from __future__ import annotations

import copy
import pytest

from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.gate2_model_contracts import Gate2ProviderExecutionMetadata
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseError,
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    ANSWER_RESPONSE_SCHEMA_VERSION,
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_ordinary_trade_production_candidate as candidate


def _unknown_case(tmp_path, *, source_header_injection: str | None = None):
    headers = list(candidate._ROWS[0])
    headers[0] = headers[0] + " (новая версия)"
    if source_header_injection is not None:
        headers[8] = source_header_injection
    rows = (tuple(headers), *candidate._ROWS[1:])
    store, context, document_id, mapping = candidate._case(tmp_path, rows=rows)
    envelope = CanonicalReaderFactory(
        store=store, read_enabled=True
    ).create().read_active_envelope(document_id, context)
    table = next(
        item for item in envelope.artifact["nodes"] if item["node_type"] == "TABLE"
    )
    binding = {
        "document_id": envelope.document_id,
        "canonical_version_id": envelope.canonical_version_id,
        "canonical_root_sha256": envelope.canonical_root_sha256,
        "source_artifact_ref": envelope.artifact["source"]["source_artifact_ref"],
        "source_sha256": envelope.artifact["source"]["source_sha256"],
    }
    return store, context, document_id, envelope.artifact, binding, table, mapping


def _metadata() -> Gate2ProviderExecutionMetadata:
    return Gate2ProviderExecutionMetadata(
        provider_id="google",
        provider_profile_id="google_gemini",
        provider_profile_revision="1",
        adapter_id="google_response_schema",
        adapter_version="1",
        requested_model_id="models/gemini-3.5-flash",
        structured_output_mode="openwebui_response_format_json_schema",
        response_format_type="json_schema",
        response_format_schema_mode="strict_json_schema",
    )


def _complete(table, mapping):
    return {
        "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": "COMPLETE",
        "table_decisions": [
            {
                "table_ref": "table_1",
                "header_row": 1,
                "disposition": "SECURITY_TRADES",
                "columns": [
                    {
                        "column": item["column"],
                        "semantic_role": item["semantic_role"],
                    }
                    for item in mapping["columns"]
                ],
                "amount_currency_bindings": copy.deepcopy(
                    mapping["amount_currency_bindings"]
                ),
                "side_values": copy.deepcopy(mapping["side_values"]),
            }
        ],
        "clarification": None,
        "message": "Mapping готов.",
    }


def _column_role_decision(column: int, semantic_role: str) -> dict:
    return {
        "decision_kind": "COLUMN_ROLE",
        "table_ref": "table_1",
        "header_row": 1,
        "column": column,
        "semantic_role": semantic_role,
        "amount_column": None,
        "currency_column": None,
        "source_literal": None,
        "normalized_value": None,
        "disposition": None,
    }


def _gross_candidate_table_decisions(mapping, gross_column: int) -> list[dict]:
    decision = copy.deepcopy(_complete({}, mapping)["table_decisions"][0])
    by_column = {item["column"]: item for item in decision["columns"]}
    prior_gross = next(
        item["column"]
        for item in decision["columns"]
        if item["semantic_role"] == "gross_amount"
    )
    target_role = by_column[gross_column]["semantic_role"]
    by_column[gross_column]["semantic_role"] = "gross_amount"
    by_column[prior_gross]["semantic_role"] = target_role
    currency_column = next(
        item["column"]
        for item in decision["columns"]
        if item["semantic_role"] == "currency"
    )
    monetary_roles = {
        "gross_amount",
        "broker_commission",
        "exchange_commission",
    }
    decision["amount_currency_bindings"] = [
        {"amount_column": item["column"], "currency_column": currency_column}
        for item in decision["columns"]
        if item["semantic_role"] in monetary_roles
    ]
    return [decision]


def _role_override_candidate_table_decisions(
    mapping, column: int, semantic_role: str
) -> list[dict]:
    decision = copy.deepcopy(_complete({}, mapping)["table_decisions"][0])
    next(
        item for item in decision["columns"] if item["column"] == column
    )["semantic_role"] = semantic_role
    currency_columns = [
        item["column"]
        for item in decision["columns"]
        if item["semantic_role"] == "currency"
    ]
    if len(currency_columns) == 1:
        decision["amount_currency_bindings"] = [
            {
                "amount_column": item["column"],
                "currency_column": currency_columns[0],
            }
            for item in decision["columns"]
            if item["semantic_role"]
            in {"gross_amount", "broker_commission", "exchange_commission"}
        ]
    return [decision]


def test_case_mapping_persists_and_feeds_existing_projection_owner(tmp_path) -> None:
    store, context, document_id, canonical, binding, table, mapping = _unknown_case(
        tmp_path
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    cases = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create()
    actual_scope = cases.case_binding(
        document_id=document_id, context=context
    )["user_scope_sha256"]
    outcome = semantic.validate_mapping_response(
        response=_complete(table, mapping),
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=_metadata(),
        confirmed_understandings=[],
        user_scope_sha256=actual_scope,
    )
    record, payload = cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome=outcome,
        provider_calls_total=1,
    )
    assert record.artifact_id.endswith("_0001")
    assert payload["status"] == "COMPLETE"
    projection_record = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().compile_and_save(document_id=document_id, context=context)
    projection = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().read(artifact_id=projection_record.artifact_id, context=context)
    assert {item["disposition"] for item in projection["source_observations"]} == {
        "RUNTIME_READY"
    }
    assert projection["qualified_table_resolutions"][0]["disposition"] == (
        "SECURITY_TRADES"
    )


def test_clarification_changes_state_only_after_explicit_confirmation(tmp_path) -> None:
    store, context, document_id, canonical, binding, table, mapping = _unknown_case(
        tmp_path
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    cases = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create()
    clarification = {
        "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": "CLARIFICATION_REQUIRED",
        "table_decisions": [],
        "clarification": {
            "question_id": "q_1",
            "table_ref": "table_1",
            "question": "Какая колонка является общей суммой сделки?",
            "options": [
                {
                    "option_id": "o_1",
                    "label": "Первая денежная колонка",
                    "decision": _column_role_decision(9, "gross_amount"),
                    "candidate_table_decisions": _gross_candidate_table_decisions(
                        mapping, 9
                    ),
                },
                {
                    "option_id": "o_runtime_1",
                    "label": "Вторая денежная колонка",
                    "decision": _column_role_decision(10, "gross_amount"),
                    "candidate_table_decisions": _gross_candidate_table_decisions(
                        mapping, 10
                    ),
                },
            ],
        },
        "message": "Нужно уточнить назначение денежной колонки.",
    }
    outcome = semantic.validate_mapping_response(
        response=clarification,
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=_metadata(),
        confirmed_understandings=[],
        user_scope_sha256=cases.case_binding(
            document_id=document_id, context=context
        )["user_scope_sha256"],
    )
    cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome=outcome,
        provider_calls_total=1,
    )
    interpretation = semantic.validate_answer_response(
        response={
            "schema_version": ANSWER_RESPONSE_SCHEMA_VERSION,
            "status": "CANDIDATE",
            "option_id": "o_choice_2",
            "message": "Понял: общая сумма во второй денежной колонке.",
            "evidence_quote": "во второй",
        },
        question=outcome["question"],
        user_message="Общая сумма во второй.",
    )
    candidate_record, candidate_payload = cases.save_answer_candidate(
        document_id=document_id,
        context=context,
        interpretation=interpretation,
        provider_calls_total=1,
    )
    assert candidate_payload["status"] == "CONFIRMATION_REQUIRED"
    assert candidate_payload["confirmed_understandings"] == []
    _record, confirmed = cases.confirm_pending_answer(
        document_id=document_id,
        context=context,
        expected_artifact_id=candidate_record.artifact_id,
        accepted=True,
    )
    assert confirmed["status"] == "MAPPING_REQUIRED"
    assert confirmed["confirmed_understandings"][0]["option_id"] == "o_choice_2"


def test_stale_concurrent_confirmation_fails_closed(tmp_path) -> None:
    store, context, document_id, canonical, binding, table, mapping = _unknown_case(
        tmp_path
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    cases = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create()
    question = {
        "question_id": "q_money_role",
        "table_ref": "table_1",
        "question": "Какая колонка содержит общую сумму?",
        "options": [
            {
                "option_id": "o_runtime_1",
                "label": "Первая",
                "decision": _column_role_decision(9, "gross_amount"),
                "candidate_table_decisions": _gross_candidate_table_decisions(
                    mapping, 9
                ),
            },
            {
                "option_id": "o_second",
                "label": "Вторая",
                "decision": _column_role_decision(10, "gross_amount"),
                "candidate_table_decisions": _gross_candidate_table_decisions(
                    mapping, 10
                ),
            },
        ],
    }
    outcome = semantic.validate_mapping_response(
        response={
            "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
            "status": "CLARIFICATION_REQUIRED",
            "table_decisions": [],
            "clarification": question,
            "message": "Нужно уточнение.",
        },
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=_metadata(),
        confirmed_understandings=[],
        user_scope_sha256=cases.case_binding(
            document_id=document_id, context=context
        )["user_scope_sha256"],
    )
    cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome=outcome,
        provider_calls_total=1,
    )
    _record, candidate_payload = cases.save_answer_candidate(
        document_id=document_id,
        context=context,
        interpretation={
            "schema_version": ANSWER_RESPONSE_SCHEMA_VERSION,
            "status": "CANDIDATE",
            "option_id": "o_choice_1",
            "message": "Первая.",
            "evidence_quote": "первая",
        },
        provider_calls_total=1,
    )
    with pytest.raises(OrdinaryTradeMappingCaseError) as exc:
        cases.confirm_pending_answer(
            document_id=document_id,
            context=context,
            expected_artifact_id="art_stale",
            accepted=True,
        )
    assert exc.value.code == "ordinary_trade_mapping_case_concurrent_answer"
    assert candidate_payload["confirmed_understandings"] == []
