from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from broker_reports_gate1.ordinary_trade_semantic_mapping_live_qualification import (
    GOAL391_MODEL_ID,
    OrdinaryTradeSemanticMappingLiveQualificationError,
    OrdinaryTradeSemanticMappingLiveQualificationFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping_qualification import (
    safe_role_map_sha256,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
from test_broker_reports_goal391_role_mapping_sandbox_corpus import (
    build_frozen_role_mapping_corpus,
)


def _lab_runner_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "qualify_goal391_current_mapping_lab.py"
    )
    spec = importlib.util.spec_from_file_location("goal391_lab_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path):
    _store, context, _document_id, canonical, binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = case_fixtures._complete(table, mapping)
    return {
        "canonical": canonical,
        "canonical_binding": binding,
        "user_scope_sha256": hashlib.sha256(context.user_id.encode()).hexdigest(),
        "expected_verdict": {
            "status": "COMPLETE",
            "qualified_mapping_count": 1,
            "qualification_receipt_count": 1,
            "table_resolution_count": 1,
            "currency_table_count": 0,
            "role_map_sha256": safe_role_map_sha256(response),
        },
        "confirmed_understandings": [],
        "target_table_node_ids": None,
        "frozen_mappings": [],
        "fixture_identity": {"fixture_id": "public-live-bridge-v1"},
    }, response, context.user_id


def _completion_payload(response):
    return {
        "model": GOAL391_MODEL_ID,
        "choices": [{"message": {"content": copy.deepcopy(response)}}],
    }


def test_live_bridge_uses_existing_client_once_and_forbids_chat_persistence(tmp_path):
    fixture, response, user_id = _fixture(tmp_path)
    submitted = []

    def call_once(form_data):
        submitted.append(form_data)
        return _completion_payload(response)

    receipt = asyncio.run(
        OrdinaryTradeSemanticMappingLiveQualificationFactory(
            request=SimpleNamespace(),
            authenticated_user_id=user_id,
            call_chat_completions_once=call_once,
        )
        .create()
        .run(fixture=fixture)
    )

    assert len(submitted) == 1
    assert submitted[0]["model"] == GOAL391_MODEL_ID
    assert submitted[0]["stream"] is False
    assert submitted[0]["response_format"]["json_schema"]["strict"] is True
    assert not {"chat_id", "parent_id", "id", "user_message", "files"}.intersection(
        submitted[0]
    )
    assert receipt["provider_calls_total"] == 1
    assert receipt["transport"] == "openwebui_chat_completions_stateless_injected_v1"
    assert receipt["chat_persistence"] == "forbidden"
    assert receipt["verdict"] == fixture["expected_verdict"]


def test_live_bridge_rejects_a_completion_payload_that_attempts_chat_persistence(tmp_path):
    fixture, response, user_id = _fixture(tmp_path)

    def call_once(_form_data):
        return _completion_payload(response)

    runner = OrdinaryTradeSemanticMappingLiveQualificationFactory(
        request=SimpleNamespace(),
        authenticated_user_id=user_id,
        call_chat_completions_once=call_once,
    ).create()

    with pytest.raises(OrdinaryTradeSemanticMappingLiveQualificationError) as exc:
        runner._resolver._complete_once(
            request=SimpleNamespace(),
            user=SimpleNamespace(id=user_id),
            form_data={"stream": False, "chat_id": "forbidden"},
        )

    assert exc.value.code == "ordinary_trade_mapping_live_chat_persistence_forbidden"


def test_live_bridge_accepts_the_frozen_golden_fixture_without_deriving_expectations():
    golden = build_frozen_role_mapping_corpus()[0]
    assert golden.frozen_fixture is not None
    assert golden.known_strict_response is not None
    submitted = []

    def call_once(form_data):
        submitted.append(form_data)
        return _completion_payload(golden.known_strict_response)

    receipt = asyncio.run(
        OrdinaryTradeSemanticMappingLiveQualificationFactory(
            request=SimpleNamespace(),
            authenticated_user_id="goal391-synthetic-ordinary-user",
            call_chat_completions_once=call_once,
        )
        .create()
        .run(fixture=golden.frozen_fixture)
    )

    assert len(submitted) == 1
    assert receipt["verdict"] == golden.frozen_fixture["expected_verdict"]


def test_safe_role_map_hash_binds_no_consumer_subtype() -> None:
    base = {
        "schema_version": "broker_reports_ordinary_trade_semantic_mapping_response_v6",
        "status": "COMPLETE",
        "table_decisions": [
            {
                "table_ref": "table_1",
                "header_row": 1,
                "disposition": "NO_NAMED_CONSUMER",
                "columns": [],
                "amount_currency_bindings": [],
                "side_values": [],
                "row_dispositions": [],
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                "classification_evidence": {
                    "context_ref": "context_1",
                    "relation": "TABLE_TITLE",
                },
            }
        ],
        "clarification": None,
        "message": "Reference table.",
    }
    changed = copy.deepcopy(base)
    changed["table_decisions"][0]["no_consumer_kind"] = (
        "OTHER_NO_NAMED_CONSUMER"
    )

    assert safe_role_map_sha256(base) != safe_role_map_sha256(changed)


def test_lab_currency_assessment_uses_the_scoped_canonical_table_node() -> None:
    runner = _lab_runner_module()
    node_id = "node_currency_target"
    case = {
        "case_id": "currency-case",
        "canonical_binding": {"canonical_root_sha256": "root"},
        "target_table_node_ids": [node_id],
        "expected_assessment": {
            "expected_status": "CURRENCY_ASSERTION_REQUIRED",
            "required_table_decisions": [
                {"table_node_id": node_id, "disposition": "SECURITY_TRADES"}
            ],
            "unresolved_table_node_ids": [],
            "forbidden_qualified_mapping_table_node_ids": [node_id],
        },
    }
    outcome = {
        "outcome": {
            "status": "CURRENCY_ASSERTION_REQUIRED",
            "currency_mapping_plan": {
                "response": {
                    "table_decisions": [
                        {"table_ref": "table_1", "disposition": "SECURITY_TRADES"}
                    ]
                }
            },
            "qualification_receipts": [],
        }
    }

    record = runner._safe_record(case=case, outcome=outcome)

    assert record["outcome"] == "PASS"
