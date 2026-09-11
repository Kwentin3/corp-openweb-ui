from __future__ import annotations

import copy
from dataclasses import replace
from types import SimpleNamespace

from broker_reports_gate1.canonical_finalization import CanonicalFinalizationFactory
from broker_reports_gate1.canonical_artifact import validate_canonical_artifact
from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.ordinary_trade_mapping_case import OrdinaryTradeMappingCaseFactory
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
    _projection_persistence_artifact_id,
)
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


def test_projection_persistence_identity_is_scope_bound_and_retry_safe(tmp_path):
    """One exact case retries idempotently; another chat never overwrites it."""

    store, context, document_id, _canonical, _binding, _table, _mapping = (
        fixtures._unknown_case(tmp_path)
    )
    projection = OrdinaryTradeProjectionFactory(store=store, read_enabled=True).create()

    first = projection.compile_and_save(document_id=document_id, context=context)
    repeated = projection.compile_and_save(document_id=document_id, context=context)
    assert repeated.artifact_id == first.artifact_id

    other_chat_context = replace(context, chat_id="projection-scope-other-chat")
    other_chat = projection.compile_and_save(
        document_id=document_id,
        context=other_chat_context,
    )
    assert other_chat.artifact_id != first.artifact_id
    assert [record.artifact_id for record, _payload in projection.current_case(
        context=other_chat_context
    )] == [other_chat.artifact_id]
    assert projection.read(
        artifact_id=first.artifact_id,
        context=context,
    )["projection_sha256"] == projection.read(
        artifact_id=other_chat.artifact_id,
        context=other_chat_context,
    )["projection_sha256"]

    first_payload = projection.read(artifact_id=first.artifact_id, context=context)
    other_user_artifact_id = _projection_persistence_artifact_id(
        projection_sha256=first_payload["projection_sha256"],
        context=replace(context, user_id="projection-scope-other-user"),
        document_id=document_id,
        source_file_ref=first.source_file_ref,
        retention_policy=first.retention_policy,
        access_policy=first.access_policy,
    )
    assert other_user_artifact_id not in {
        first.artifact_id,
        other_chat.artifact_id,
    }


def test_projection_reader_accepts_legacy_content_only_artifact_id(tmp_path):
    """Changing new-write identity does not strand an already stored v6 payload."""

    store, context, document_id, _canonical, _binding, _table, _mapping = (
        fixtures._unknown_case(tmp_path)
    )
    projection = OrdinaryTradeProjectionFactory(store=store, read_enabled=True).create()
    current = projection.compile_and_save(document_id=document_id, context=context)
    payload = projection.read(artifact_id=current.artifact_id, context=context)
    legacy_id = "art_otproj_" + payload["projection_sha256"][:40]
    store.put_record(
        replace(
            current,
            artifact_id=legacy_id,
            payload=payload,
            payload_ref=None,
        )
    )

    assert projection.read(artifact_id=legacy_id, context=context) == payload


def test_confirmed_user_choice_is_sealed_into_final_canonical_and_reused(
    tmp_path, monkeypatch
):
    # This test owns the sealed user-confirmation transition, not disk-capacity
    # admission. Pin a healthy filesystem boundary so the asserted state
    # transition does not depend on the runner's temporary-volume capacity.
    import broker_reports_gate1.canonical_store as canonical_store

    monkeypatch.setattr(
        canonical_store.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(
            total=20 * 1024 * 1024 * 1024,
            free=10 * 1024 * 1024 * 1024,
        ),
    )
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

    forged = copy.deepcopy(envelope.artifact)
    forged["user_assertions"][0]["provenance_kind"] = "document"
    assert not validate_canonical_artifact(forged)["passed"]
    assert "canonical_user_assertion_invalid" in validate_canonical_artifact(forged)[
        "error_codes"
    ]
