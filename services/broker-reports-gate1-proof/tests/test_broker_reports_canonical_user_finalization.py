from __future__ import annotations

from broker_reports_gate1.canonical_finalization import CanonicalFinalizationFactory
from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.ordinary_trade_mapping_case import OrdinaryTradeMappingCaseFactory
from broker_reports_gate1.ordinary_trade_projection import OrdinaryTradeProjectionFactory
from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    ANSWER_RESPONSE_SCHEMA_VERSION,
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)
from broker_reports_gate1.artifact_retention import build_retention_policy

import test_broker_reports_issue312_mapping_case as fixtures


def test_confirmed_user_choice_is_sealed_into_final_canonical_and_reused(tmp_path):
    store, context, document_id, canonical, binding, table, mapping = fixtures._unknown_case(
        tmp_path
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    clarification = {
        "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": "CLARIFICATION_REQUIRED",
        "table_decisions": [],
        "clarification": {
            "question_id": "q_final_canonical",
            "table_ref": "table_1",
            "question": "Which column is the gross amount?",
            "options": [
                {
                    "option_id": "o_final_amount",
                    "label": "Column 10 is the gross amount.",
                    "decision": fixtures._column_role_decision(10, "gross_amount"),
                },
                {
                    "option_id": "o_wrong_amount",
                    "label": "Column 9 is the gross amount.",
                    "decision": fixtures._column_role_decision(9, "gross_amount"),
                },
            ],
        },
        "message": "One source meaning needs confirmation.",
    }
    outcome = semantic.validate_mapping_response(
        response=clarification,
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=fixtures._metadata(),
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
    candidate_record, _candidate = cases.save_answer_candidate(
        document_id=document_id,
        context=context,
        interpretation=semantic.validate_answer_response(
            response={
                "schema_version": ANSWER_RESPONSE_SCHEMA_VERSION,
                "status": "CANDIDATE",
                "option_id": "o_choice_1",
                "message": "The first option is correct.",
                "evidence_quote": "first option",
            },
            question=outcome["question"],
            user_message="The first option is correct.",
        ),
        provider_calls_total=1,
    )
    _record, confirmed = cases.confirm_pending_answer(
        document_id=document_id,
        context=context,
        expected_artifact_id=candidate_record.artifact_id,
        accepted=True,
    )
    complete = semantic.validate_mapping_response(
        response=fixtures._complete(table, mapping),
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=fixtures._metadata(),
        confirmed_understandings=confirmed["confirmed_understandings"],
        user_scope_sha256=cases.case_binding(
            document_id=document_id, context=context
        )["user_scope_sha256"],
    )
    cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome=complete,
        provider_calls_total=1,
    )

    final = CanonicalFinalizationFactory(store=store, read_enabled=True).create().finalize(
        document_id=document_id,
        context=context,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    )

    envelope = CanonicalReaderFactory(store=store, read_enabled=True).create().read_active_envelope(
        document_id, context
    )
    assert envelope.canonical_version_id == final["canonical_version_id"]
    assert envelope.artifact["finalization"]["base_canonical_version_id"] == binding[
        "canonical_version_id"
    ]
    assert envelope.artifact["user_assertions"][0]["provenance_kind"] == "user_confirmed"
    assert envelope.artifact["user_assertions"][0]["decision"] == confirmed[
        "confirmed_understandings"
    ][0]["decision"]
    assert cases.current(document_id=document_id, context=context)[1]["status"] == "COMPLETE"

    projection = OrdinaryTradeProjectionFactory(store=store, read_enabled=True).create()
    record = projection.compile_and_save(document_id=document_id, context=context)
    payload = projection.read(artifact_id=record.artifact_id, context=context)
    assert payload["canonical_binding"]["canonical_version_id"] == final[
        "canonical_version_id"
    ]
    assert {item["disposition"] for item in payload["source_observations"]} == {
        "RUNTIME_READY"
    }

    right_bank = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create().run(canonical_artifact_refs=[final["artifact_ref"]], context=context)
    assert right_bank["canonical_version_ids"] == [final["canonical_version_id"]]
    assert right_bank["documents"][0]["canonical_version_id"] == final[
        "canonical_version_id"
    ]
