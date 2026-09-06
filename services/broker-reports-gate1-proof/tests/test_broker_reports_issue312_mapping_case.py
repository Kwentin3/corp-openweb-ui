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
    envelope = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read_active_envelope(document_id, context)
    )
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


def _unknown_two_table_case(tmp_path):
    store, context = candidate.gate4_fixtures._store_context(tmp_path)
    document_id = "ordinary-trade-two-table-mapping-case"
    rows = []
    for suffix in ("one", "two"):
        headers = list(candidate._ROWS[0])
        headers[0] = f"{headers[0]} ({suffix})"
        rows.append((tuple(headers), *candidate._ROWS[1:]))
    candidate.gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_row_sets=tuple(rows),
    )
    envelope = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read_active_envelope(document_id, context)
    )
    binding = {
        "document_id": envelope.document_id,
        "canonical_version_id": envelope.canonical_version_id,
        "canonical_root_sha256": envelope.canonical_root_sha256,
        "source_artifact_ref": envelope.artifact["source"]["source_artifact_ref"],
        "source_sha256": envelope.artifact["source"]["source_sha256"],
    }
    return store, context, document_id, envelope.artifact, binding


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
    cells_by_row = {}
    for cell in (table.get("content") or {}).get("cells") or []:
        cells_by_row.setdefault(cell["row"], []).append(cell)
    trade_rows = (
        [
            row
            for row, cells in sorted(cells_by_row.items())
            if row > 1
            and any(
                str(cell.get("displayed_value") or cell.get("value") or "").strip()
                for cell in cells
            )
        ]
        if cells_by_row
        else list(range(2, len(candidate._ROWS) + 1))
    )
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
                "row_dispositions": [
                    {"row": row, "disposition": "SECURITY_TRADES"}
                    for row in trade_rows
                ],
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


def test_case_mapping_persists_and_feeds_existing_projection_owner(tmp_path) -> None:
    store, context, document_id, canonical, binding, table, mapping = _unknown_case(
        tmp_path
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    actual_scope = cases.case_binding(document_id=document_id, context=context)[
        "user_scope_sha256"
    ]
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
    projection_record = (
        OrdinaryTradeProjectionFactory(store=store, read_enabled=True)
        .create()
        .compile_and_save(document_id=document_id, context=context)
    )
    projection = (
        OrdinaryTradeProjectionFactory(store=store, read_enabled=True)
        .create()
        .read(artifact_id=projection_record.artifact_id, context=context)
    )
    assert {item["disposition"] for item in projection["source_observations"]} == {
        "RUNTIME_READY"
    }
    assert projection["qualified_table_resolutions"][0]["disposition"] == (
        "SECURITY_TRADES"
    )


def test_clarification_changes_state_only_after_explicit_confirmation(tmp_path) -> None:
    store, context, document_id, canonical, binding, table, _mapping = _unknown_case(
        tmp_path
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
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
                },
                {
                    "option_id": "o_runtime_1",
                    "label": "Вторая денежная колонка",
                    "decision": _column_role_decision(10, "gross_amount"),
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
        user_scope_sha256=cases.case_binding(document_id=document_id, context=context)[
            "user_scope_sha256"
        ],
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


def test_exclusion_decisions_remain_complete_and_auditable(tmp_path) -> None:
    store, context, document_id, canonical, binding = _unknown_two_table_case(tmp_path)
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    outcome = semantic.validate_mapping_response(
        response={
            "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
            "status": "COMPLETE",
            "table_decisions": [
                {
                    "table_ref": f"table_{index}",
                    "header_row": 1,
                    "disposition": "NO_NAMED_CONSUMER",
                    "columns": [],
                    "amount_currency_bindings": [],
                    "side_values": [],
                    "row_dispositions": [],
                }
                for index in (1, 2)
            ],
            "clarification": None,
            "message": "Both tables have no named consumer.",
        },
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=_metadata(),
        confirmed_understandings=[],
        user_scope_sha256=cases.case_binding(document_id=document_id, context=context)[
            "user_scope_sha256"
        ],
    )
    assert outcome["status"] == "COMPLETE"
    assert outcome["question"] is None
    record, payload = cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome=outcome,
        provider_calls_total=1,
    )
    assert record.artifact_id
    assert payload["confirmed_understandings"] == []
    assert [item["disposition"] for item in payload["table_resolutions"]] == [
        "NO_NAMED_CONSUMER",
        "NO_NAMED_CONSUMER",
    ]


def test_stale_concurrent_confirmation_fails_closed(tmp_path) -> None:
    store, context, document_id, canonical, binding, table, _mapping = _unknown_case(
        tmp_path
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    question = {
        "question_id": "q_money_role",
        "table_ref": "table_1",
        "question": "Какая колонка содержит общую сумму?",
        "options": [
            {
                "option_id": "o_runtime_1",
                "label": "Первая",
                "decision": _column_role_decision(9, "gross_amount"),
            },
            {
                "option_id": "o_second",
                "label": "Вторая",
                "decision": _column_role_decision(10, "gross_amount"),
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
        user_scope_sha256=cases.case_binding(document_id=document_id, context=context)[
            "user_scope_sha256"
        ],
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
