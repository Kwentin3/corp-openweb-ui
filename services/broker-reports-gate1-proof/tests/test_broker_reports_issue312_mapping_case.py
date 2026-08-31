from __future__ import annotations

import copy
import hashlib
import json
import pytest

from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.gate2_model_contracts import Gate2ProviderExecutionMetadata
from broker_reports_gate1.ordinary_trade_mapping_case import (
    LEGACY_MAPPING_CASE_ARTIFACT_TYPE,
    MAPPING_CASE_ARTIFACT_TYPE,
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


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


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
    outcome["semantic_evidence_sha256"] = "e" * 64
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
    store, context, document_id, canonical, binding, table, _mapping = _unknown_case(
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
        user_scope_sha256=cases.case_binding(
            document_id=document_id, context=context
        )["user_scope_sha256"],
    )
    outcome["semantic_evidence_sha256"] = "e" * 64
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
    store, context, document_id, canonical, binding, table, _mapping = _unknown_case(
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
        user_scope_sha256=cases.case_binding(
            document_id=document_id, context=context
        )["user_scope_sha256"],
    )
    outcome["semantic_evidence_sha256"] = "e" * 64
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


def test_in_progress_v2_case_resumes_as_v3_with_hash_continuity(tmp_path) -> None:
    store, context, document_id, *_rest = _unknown_case(tmp_path)
    cases = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create()
    binding = cases.case_binding(document_id=document_id, context=context)
    legacy_payload = {
        "schema_version": LEGACY_MAPPING_CASE_ARTIFACT_TYPE,
        "case_id": binding["case_id"],
        "revision": 1,
        "predecessor_sha256": None,
        "case_binding": {
            "canonical_binding": copy.deepcopy(binding["canonical_binding"]),
            "user_scope_sha256": binding["user_scope_sha256"],
            "case_binding_sha256": binding["case_binding_sha256"],
        },
        "status": "MAPPING_REQUIRED",
        "message": "Legacy mapping remains in progress.",
        "question": None,
        "pending_candidate": None,
        "confirmed_understandings": [],
        "qualified_mappings": [],
        "qualification_receipts": [],
        "table_resolutions": [],
        "provider_calls_total": 1,
        "model_response_sha256": None,
        "execution_metadata_sha256": None,
        "reason_code": None,
    }
    legacy_payload["integrity_sha256"] = _sha256_json(legacy_payload)
    active = store.get_active_canonical_version(
        context=context, document_id=document_id
    )
    manifest = store.get_record_unchecked(active.manifest_ref)
    assert manifest is not None
    store.put_record(
        ArtifactRecord(
            artifact_id="art_otmapcase_legacy_0001",
            artifact_type=LEGACY_MAPPING_CASE_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref=copy.deepcopy(manifest.source_file_ref),
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=manifest.retention_policy,
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": bool(
                    context.workspace_model_id
                ),
                "ordinary_trade_mapping_case_only": True,
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload_kind="json_file",
            payload=legacy_payload,
        )
    )

    current = cases.current(document_id=document_id, context=context)
    assert current is not None
    assert current[0].artifact_type == LEGACY_MAPPING_CASE_ARTIFACT_TYPE
    assert current[1] == legacy_payload

    successor_record, successor = cases.save_provider_terminal(
        document_id=document_id,
        context=context,
        status="PROVIDER_UNAVAILABLE",
        reason_code="provider_unavailable",
        message="Retry remains possible.",
        provider_calls_total=1,
    )

    assert successor_record.artifact_type == MAPPING_CASE_ARTIFACT_TYPE
    assert successor["schema_version"] == MAPPING_CASE_ARTIFACT_TYPE
    assert successor["revision"] == 2
    assert successor["predecessor_sha256"] == legacy_payload["integrity_sha256"]
    assert successor["provider_calls_total"] == 2
