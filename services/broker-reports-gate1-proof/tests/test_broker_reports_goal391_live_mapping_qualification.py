from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
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
from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_ID,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_COMMAND,
    PROMPT_CONTRACT_ID,
    PROMPT_PLACEHOLDER,
    PROMPT_REQUIRED_TAG,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    OrdinaryTradeMappingManagedPrompt,
    ordinary_trade_mapping_prompt_hash,
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


def _managed_qualification_prompt(
    *, source: str = "openwebui_prompt_history"
) -> OrdinaryTradeMappingManagedPrompt:
    content = f"Hermetic role mapping candidate. {PROMPT_PLACEHOLDER}"
    return OrdinaryTradeMappingManagedPrompt(
        prompt_ref="goal391-hermetic-mapping-prompt",
        command=PROMPT_COMMAND,
        version="goal391-hermetic-v1",
        content=content,
        hash=ordinary_trade_mapping_prompt_hash(content),
        source=source,
        template_id=PROMPT_TEMPLATE_ID,
        template_kind=PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version=INPUT_SCHEMA_VERSION,
        output_schema_id=OUTPUT_SCHEMA_ID,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        tags=(PROMPT_REQUIRED_TAG,),
        safe_metadata={"name": "Goal 391 hermetic qualification candidate"},
    )


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
            mapping_prompt=_managed_qualification_prompt(),
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
        mapping_prompt=_managed_qualification_prompt(),
    ).create()

    with pytest.raises(OrdinaryTradeSemanticMappingLiveQualificationError) as exc:
        runner._resolver._complete_once(
            request=SimpleNamespace(),
            user=SimpleNamespace(id=user_id),
            form_data={"stream": False, "chat_id": "forbidden"},
        )

    assert exc.value.code == "ordinary_trade_mapping_live_chat_persistence_forbidden"


def test_live_bridge_rejects_non_native_prompt_before_completion_boundary(tmp_path):
    _fixture_value, response, user_id = _fixture(tmp_path)
    submitted = []

    def call_once(form_data):
        submitted.append(form_data)
        return _completion_payload(response)

    with pytest.raises(OrdinaryTradeSemanticMappingLiveQualificationError) as exc:
        OrdinaryTradeSemanticMappingLiveQualificationFactory(
            request=SimpleNamespace(),
            authenticated_user_id=user_id,
            call_chat_completions_once=call_once,
            mapping_prompt=_managed_qualification_prompt(source="test"),
        )

    assert exc.value.code == "ordinary_trade_mapping_live_native_prompt_required"
    assert submitted == []


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
            mapping_prompt=_managed_qualification_prompt(),
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
    assert record["actual_table_decision_count"] == 1
    assert record["actual_disposition_counts"] == {"SECURITY_TRADES": 1}
    assert record["actual_no_consumer_kind_counts"] == {}
    assert record["classification_evidence_required_total"] == 0
    assert record["actual_classification_evidence_total"] == 0
    assert record["classification_evidence_matches"] is True
    assert record["complete_without_required_exclusion_path"] is False
    assert record["status_matches"] is True
    assert record["required_decisions_match"] is True
    assert record["unresolved_table_set_match"] is True
    assert record["forbidden_qualified_mapping_clear"] is True


def test_lab_compares_ordered_classification_evidence_by_safe_signature_only() -> None:
    runner = _lab_runner_module()
    node_id = "node_reference"
    expected_evidence = [
        {"context_ref": "context_expected_title", "relation": "TABLE_TITLE"},
        {
            "context_ref": "context_expected_context",
            "relation": "PRECEDING_SAME_CONTAINER",
        },
    ]
    case = {
        "case_id": "reference-case",
        "canonical_binding": {"canonical_root_sha256": "root"},
        "target_table_node_ids": [node_id],
        "expected_assessment": {
            "expected_status": "COMPLETE",
            "required_table_decisions": [
                {
                    "table_node_id": node_id,
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                    "classification_evidence": expected_evidence,
                }
            ],
            "unresolved_table_node_ids": [],
            "forbidden_qualified_mapping_table_node_ids": [],
        },
    }
    outcome = {
        "outcome": {
            "status": "COMPLETE",
            "table_resolutions": [
                {
                    "table_node_id": node_id,
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                    "classification_evidence": [
                        {
                            **expected_evidence[0],
                            "canonical_node_id": "private-node-title",
                        },
                        {
                            **expected_evidence[1],
                            "literal_sha256": "a" * 64,
                        },
                    ],
                }
            ],
            "qualification_receipts": [],
        }
    }

    record = runner._safe_record(case=case, outcome=outcome)

    assert record["outcome"] == "PASS"
    assert record["classification_evidence_required_total"] == 2
    assert record["actual_classification_evidence_total"] == 2
    assert record["classification_evidence_matches"] is True
    assert record["complete_without_required_exclusion_path"] is False
    receipt_json = json.dumps(record)
    for evidence in expected_evidence:
        assert evidence["context_ref"] not in receipt_json
        assert evidence["relation"] not in receipt_json
    assert "private-node-title" not in json.dumps(record)


def test_lab_derives_full_owner_envelope_from_frozen_case_not_manifest() -> None:
    runner = _lab_runner_module()
    node_id = "node_reference"
    owner_envelope = [
        {
            "context_ref": "context_1",
            "relation": "TABLE_TITLE",
            "canonical_node_id": "private-node-title",
            "literal_sha256": "a" * 64,
        },
        {
            "context_ref": "context_2",
            "relation": "PRECEDING_SAME_CONTAINER",
            "canonical_node_id": "private-node-context",
            "literal_sha256": "b" * 64,
        },
    ]
    case = {
        "case_id": "reference-case",
        "canonical_binding": {"canonical_root_sha256": "root"},
        "target_table_node_ids": [node_id],
        "owner_classification_envelopes": {node_id: owner_envelope},
        "expected_assessment": {
            "expected_status": "COMPLETE",
            # A v8 frozen expectation asserts the semantic decision only. It
            # cannot hand-pick model evidence from protected Canonical data.
            "required_table_decisions": [
                {
                    "table_node_id": node_id,
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                }
            ],
            "unresolved_table_node_ids": [],
            "forbidden_qualified_mapping_table_node_ids": [],
        },
    }
    outcome = {
        "outcome": {
            "status": "COMPLETE",
            "table_resolutions": [
                {
                    "table_node_id": node_id,
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                    "classification_evidence": owner_envelope,
                }
            ],
            "qualification_receipts": [],
        }
    }

    record = runner._safe_record(case=case, outcome=outcome)

    assert record["outcome"] == "PASS"
    assert record["owner_classification_envelope_required_total"] == 2
    assert record["actual_owner_classification_envelope_total"] == 2
    assert record["owner_classification_envelope_matches"] is True
    # New v8 manifests contain no model-selected evidence expectations.
    assert record["classification_evidence_required_total"] == 0
    assert record["classification_evidence_matches"] is True
    receipt_json = json.dumps(record)
    for entry in owner_envelope:
        for value in entry.values():
            assert value not in receipt_json


def test_lab_rejects_owner_envelope_that_does_not_match_frozen_canonical() -> None:
    runner = _lab_runner_module()
    node_id = "node_reference"
    owner_envelope = [
        {
            "context_ref": "context_1",
            "relation": "TABLE_TITLE",
            "canonical_node_id": "private-node-title",
            "literal_sha256": "a" * 64,
        }
    ]
    actual_envelope = [
        {
            **owner_envelope[0],
            "literal_sha256": "b" * 64,
        }
    ]
    case = {
        "case_id": "reference-case",
        "canonical_binding": {"canonical_root_sha256": "root"},
        "target_table_node_ids": [node_id],
        "owner_classification_envelopes": {node_id: owner_envelope},
        "expected_assessment": {
            "expected_status": "COMPLETE",
            "required_table_decisions": [
                {
                    "table_node_id": node_id,
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                }
            ],
            "unresolved_table_node_ids": [],
            "forbidden_qualified_mapping_table_node_ids": [],
        },
    }
    outcome = {
        "outcome": {
            "status": "COMPLETE",
            "table_resolutions": [
                {
                    "table_node_id": node_id,
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                    "classification_evidence": actual_envelope,
                }
            ],
            "qualification_receipts": [],
        }
    }

    record = runner._safe_record(case=case, outcome=outcome)

    assert record["outcome"] == "FAIL"
    assert record["owner_classification_envelope_matches"] is False


def test_lab_flags_complete_without_the_required_exclusion_path() -> None:
    runner = _lab_runner_module()
    node_id = "node_reference"
    case = {
        "case_id": "reference-case",
        "canonical_binding": {"canonical_root_sha256": "root"},
        "target_table_node_ids": [node_id],
        "expected_assessment": {
            "expected_status": "COMPLETE",
            "required_table_decisions": [
                {
                    "table_node_id": node_id,
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                    "classification_evidence": [
                        {
                            "context_ref": "context_expected",
                            "relation": "TABLE_TITLE",
                        }
                    ],
                }
            ],
            "unresolved_table_node_ids": [],
            "forbidden_qualified_mapping_table_node_ids": [],
        },
    }
    outcome = {
        "outcome": {
            "status": "COMPLETE",
            "table_resolutions": [
                {"table_node_id": node_id, "disposition": "SECURITY_TRADES"}
            ],
            "qualification_receipts": [],
        }
    }

    record = runner._safe_record(case=case, outcome=outcome)

    assert record["outcome"] == "FAIL"
    assert record["complete_without_required_exclusion_path"] is True
    assert record["classification_evidence_matches"] is False


def test_lab_requires_an_exact_nonempty_unique_evidence_list_in_frozen_expectation() -> None:
    runner = _lab_runner_module()
    valid = {
        "expected_status": "COMPLETE",
        "required_table_decisions": [
            {
                "table_node_id": "node_reference",
                "disposition": "NO_NAMED_CONSUMER",
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                "classification_evidence": [
                    {"context_ref": "context_expected_a", "relation": "TABLE_TITLE"},
                    {
                        "context_ref": "context_expected_b",
                        "relation": "PRECEDING_SAME_CONTAINER",
                    },
                ],
            }
        ],
        "unresolved_table_node_ids": [],
        "forbidden_qualified_mapping_table_node_ids": [],
    }
    runner._validate_expected_assessment(valid)
    for invalid_evidence in (
        {"context_ref": "legacy-singleton", "relation": "TABLE_TITLE"},
        [],
        [
            valid["required_table_decisions"][0]["classification_evidence"][0],
            valid["required_table_decisions"][0]["classification_evidence"][0],
        ],
        [
            {
                **valid["required_table_decisions"][0]["classification_evidence"][0],
                "literal_sha256": "a" * 64,
            }
        ],
    ):
        invalid = copy.deepcopy(valid)
        invalid["required_table_decisions"][0]["classification_evidence"] = (
            invalid_evidence
        )
        with pytest.raises(SystemExit) as exc:
            runner._validate_expected_assessment(invalid)
        assert str(exc.value) == "goal391_expected_assessment_invalid"


def test_lab_v9_requires_frozen_model_selected_evidence_for_an_exclusion() -> None:
    runner = _lab_runner_module()
    assessment = {
        "expected_status": "COMPLETE",
        "required_table_decisions": [
            {
                "table_node_id": "node_reference",
                "disposition": "NO_NAMED_CONSUMER",
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
            }
        ],
        "unresolved_table_node_ids": [],
        "forbidden_qualified_mapping_table_node_ids": [],
    }

    with pytest.raises(SystemExit) as exc:
        runner._validate_expected_assessment(
            assessment, requires_model_selected_evidence=True
        )

    assert str(exc.value) == "goal391_expected_assessment_invalid"


@pytest.mark.parametrize(
    "actual_evidence",
    [
        [
            {"context_ref": "context_a", "relation": "TABLE_TITLE"},
        ],
        [
            {"context_ref": "context_b", "relation": "PRECEDING_SAME_CONTAINER"},
            {"context_ref": "context_a", "relation": "TABLE_TITLE"},
        ],
        [
            {"context_ref": "context_a", "relation": "TABLE_TITLE"},
            {"context_ref": "context_b", "relation": "PRECEDING_SAME_CONTAINER"},
            {"context_ref": "context_c", "relation": "PRECEDING_SIBLING_CONTAINER"},
        ],
        [
            {"context_ref": "context_a", "relation": "TABLE_TITLE"},
            {"context_ref": "context_a", "relation": "TABLE_TITLE"},
        ],
    ],
    ids=["missing", "reordered", "extra", "duplicate"],
)
def test_lab_rejects_non_exact_actual_classification_evidence_list(
    actual_evidence: list[dict[str, str]],
) -> None:
    runner = _lab_runner_module()
    node_id = "node_reference"
    expected_evidence = [
        {"context_ref": "context_a", "relation": "TABLE_TITLE"},
        {"context_ref": "context_b", "relation": "PRECEDING_SAME_CONTAINER"},
    ]
    case = {
        "case_id": "reference-case",
        "canonical_binding": {"canonical_root_sha256": "root"},
        "target_table_node_ids": [node_id],
        "expected_assessment": {
            "expected_status": "COMPLETE",
            "required_table_decisions": [
                {
                    "table_node_id": node_id,
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                    "classification_evidence": expected_evidence,
                }
            ],
            "unresolved_table_node_ids": [],
            "forbidden_qualified_mapping_table_node_ids": [],
        },
    }
    outcome = {
        "outcome": {
            "status": "COMPLETE",
            "table_resolutions": [
                {
                    "table_node_id": node_id,
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                    "classification_evidence": actual_evidence,
                }
            ],
            "qualification_receipts": [],
        }
    }

    record = runner._safe_record(case=case, outcome=outcome)

    assert record["outcome"] == "FAIL"
    assert record["classification_evidence_matches"] is False


def test_lab_passes_the_resolved_managed_prompt_to_its_single_call() -> None:
    runner = _lab_runner_module()
    managed_prompt = _managed_qualification_prompt()
    captured = {}

    class StopAfterCapture(RuntimeError):
        pass

    class Semantic:
        def build_mapping_package(self, **_kwargs):
            return {"phase": "map", "case": {}}

        def mapping_response_format(self):
            return {"type": "json_schema"}

    class Client:
        async def extract(self, **kwargs):
            captured.update(kwargs)
            raise StopAfterCapture()

    with pytest.raises(StopAfterCapture):
        asyncio.run(
            runner._run_case(
                semantic=Semantic(),
                prompt=managed_prompt,
                client=Client(),
                case={
                    "canonical": {},
                    "confirmed_understandings": [],
                    "target_table_node_ids": None,
                },
                progress=lambda *_args: None,
            )
        )

    assert captured["prompt"] is managed_prompt


def test_lab_owner_envelopes_reject_a_required_table_outside_frozen_scope(
    tmp_path,
) -> None:
    runner = _lab_runner_module()
    _store, _context, _document_id, canonical, _binding, table, _mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    table["content"]["title"] = "Reference material"

    with pytest.raises(SystemExit) as exc:
        runner._owner_classification_envelopes(
            canonical=canonical,
            target_table_node_ids=[table["node_id"]],
            required_table_decisions=[
                {
                    "table_node_id": "foreign-table",
                    "disposition": "NO_NAMED_CONSUMER",
                    "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                }
            ],
        )

    assert str(exc.value) == "goal391_owner_classification_envelope_invalid"


def test_lab_preflight_uses_the_frozen_manifest_case_count(tmp_path) -> None:
    """A supplied frozen two-case scope is valid without any provider call."""

    runner = _lab_runner_module()
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    corpus = build_frozen_role_mapping_corpus()[:2]
    candidate = {"candidate": "frozen-candidate"}
    expectations = {
        "schema_version": "broker_reports_role_mapping_lab_disposition_expectations_v3",
        "candidate": candidate,
        "cases": [],
    }
    for index, source_case in enumerate(corpus, start=1):
        snapshot_id = f"snapshot-{index}"
        (corpus_root / f"{snapshot_id}.canonical.json").write_text(
            json.dumps(source_case.canonical), encoding="utf-8"
        )
        expectations["cases"].append(
            {
                "case_id": f"frozen-case-{index}",
                "confirmed_understandings": [],
                "document_id": f"frozen-document-{index}",
                "expected_assessment": {
                    "expected_status": "SPECIALIST_REVIEW_REQUIRED",
                    "required_table_decisions": [],
                    "unresolved_table_node_ids": [],
                    "forbidden_qualified_mapping_table_node_ids": [],
                },
                "fixture_identity": {"fixture_id": f"frozen-fixture-{index}"},
                "frozen_mappings": [],
                "snapshot_id": snapshot_id,
                "target_table_node_ids": None,
                "user_scope_sha256": hashlib.sha256(
                    f"frozen-user-{index}".encode()
                ).hexdigest(),
            }
        )
    expectation_path = tmp_path / "expectations.json"
    expectation_path.write_text(json.dumps(expectations), encoding="utf-8")

    cases = runner._preflight(
        corpus_root=corpus_root,
        expectation_path=expectation_path,
        candidate=candidate,
    )

    assert [case["case_id"] for case in cases] == [
        "frozen-case-1",
        "frozen-case-2",
    ]
    assert runner._preflight_receipt(candidate=candidate, cases=cases)["corpus"][
        "cases_total"
    ] == 2


def test_lab_preflight_rejects_an_empty_frozen_manifest(tmp_path) -> None:
    """Qualification cannot pass without at least one manifest-owned case."""

    runner = _lab_runner_module()
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    expectation_path = tmp_path / "expectations.json"
    candidate = {"candidate": "frozen-candidate"}
    expectation_path.write_text(
        json.dumps(
            {
                "schema_version": "broker_reports_role_mapping_lab_disposition_expectations_v3",
                "candidate": candidate,
                "cases": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        runner._preflight(
            corpus_root=corpus_root,
            expectation_path=expectation_path,
            candidate=candidate,
        )

    assert str(exc.value) == "goal391_expectations_invalid"


def test_lab_requires_the_released_model_from_native_catalog() -> None:
    runner = _lab_runner_module()
    captured = {}

    async def loader(request, *, user):
        captured["request"] = request
        captured["user"] = user
        return [{"id": "models/gemini-3.5-flash"}]

    asyncio.run(
        runner._ensure_server_model_available(
            request="request",
            user="ordinary-user",
            model_id="models/gemini-3.5-flash",
            model_loader=loader,
        )
    )
    assert captured == {"request": "request", "user": "ordinary-user"}


def test_lab_refuses_a_missing_released_model_before_completion() -> None:
    runner = _lab_runner_module()

    async def loader(_request, *, user):
        assert user == "ordinary-user"
        return [{"id": "another-model"}]

    with pytest.raises(SystemExit) as exc:
        asyncio.run(
            runner._ensure_server_model_available(
                request="request",
                user="ordinary-user",
                model_id="models/gemini-3.5-flash",
                model_loader=loader,
            )
        )
    assert str(exc.value) == "goal391_released_model_not_available"


@pytest.mark.parametrize(
    ("user_loader", "model_checker", "expected_stage"),
    [
        (
            lambda: {"users": []},
            None,
            "RUNTIME_CONTEXT_BLOCKED_ORDINARY_USER_UNAVAILABLE",
        ),
        (
            lambda: {"users": [SimpleNamespace(id="ordinary-user", role="user")]},
            lambda **_kwargs: (_ for _ in ()).throw(
                SystemExit("goal391_released_model_not_available")
            ),
            "RUNTIME_CONTEXT_BLOCKED_RELEASED_MODEL_UNAVAILABLE",
        ),
    ],
    ids=["ordinary-user-missing", "released-model-unavailable"],
)
def test_lab_runtime_context_blocks_before_ready_with_zero_provider_calls(
    tmp_path,
    monkeypatch,
    user_loader,
    model_checker,
    expected_stage,
) -> None:
    """A failed native context can never reach the completion boundary."""

    runner = _lab_runner_module()
    original = runner._server_runtime_context
    progress_path = tmp_path / "safe-progress.json"
    completion_factory_reached = []

    async def async_user_loader():
        return user_loader()

    async def available_model(**_kwargs):
        return None

    async def isolated_context(*, ordinary_user_id, progress):
        return await original(
            ordinary_user_id=ordinary_user_id,
            progress=progress,
            user_loader=async_user_loader,
            request_factory=lambda: SimpleNamespace(),
            model_checker=model_checker or available_model,
            chat_loader=lambda _user_id: [],
        )

    class CompletionFactory:
        def __init__(self, **_kwargs):
            completion_factory_reached.append(True)

        def create(self):
            raise AssertionError("completion_boundary_must_not_be_reached")

    monkeypatch.setattr(runner, "_server_runtime_context", isolated_context)
    monkeypatch.setattr(runner, "Gate2StructuredModelClientFactory", CompletionFactory)

    with pytest.raises(SystemExit):
        asyncio.run(
            runner._run_live_qualification(
                semantic=SimpleNamespace(),
                prompt=SimpleNamespace(),
                candidate={"candidate": "safe-test"},
                cases=[],
                ordinary_user_id="ordinary-user",
                progress_path=progress_path,
            )
        )

    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress["state"] == expected_stage
    assert progress["provider_calls_started_total"] == 0
    assert completion_factory_reached == []
    assert set(progress) == {
        "schema_version",
        "state",
        "candidate_sha256",
        "provider_calls_started_total",
    }


def test_lab_runtime_context_progresses_through_native_checks_before_ready(
    tmp_path, monkeypatch
) -> None:
    runner = _lab_runner_module()
    original = runner._server_runtime_context
    progress_path = tmp_path / "safe-progress.json"

    async def user_loader():
        return {"users": [SimpleNamespace(id="ordinary-user", role="user")]}

    async def model_checker(**_kwargs):
        return None

    async def chat_loader(_user_id):
        return []

    async def isolated_context(*, ordinary_user_id, progress):
        return await original(
            ordinary_user_id=ordinary_user_id,
            progress=progress,
            user_loader=user_loader,
            request_factory=lambda: SimpleNamespace(),
            model_checker=model_checker,
            chat_loader=chat_loader,
        )

    monkeypatch.setattr(runner, "_server_runtime_context", isolated_context)

    receipt = asyncio.run(
        runner._run_live_qualification(
            semantic=SimpleNamespace(),
            prompt=SimpleNamespace(),
            candidate={"candidate": "safe-test"},
            cases=[],
            ordinary_user_id="ordinary-user",
            progress_path=progress_path,
        )
    )

    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress["state"] == "READY"
    assert progress["provider_calls_started_total"] == 0
    assert receipt["status"] == "PASSED"
    assert receipt["corpus"]["provider_calls_started_total"] == 0


def test_lab_runtime_context_never_persists_a_raw_system_exit_value(
    tmp_path, monkeypatch
) -> None:
    runner = _lab_runner_module()
    progress_path = tmp_path / "safe-progress.json"
    private_error = "private prompt/source/model response/secret"

    async def blocked_context(**_kwargs):
        raise SystemExit(private_error)

    monkeypatch.setattr(runner, "_server_runtime_context", blocked_context)

    with pytest.raises(SystemExit):
        asyncio.run(
            runner._run_live_qualification(
                semantic=SimpleNamespace(),
                prompt=SimpleNamespace(),
                candidate={"candidate": "safe-test"},
                cases=[],
                ordinary_user_id="ordinary-user",
                progress_path=progress_path,
            )
        )

    serialized = progress_path.read_text(encoding="utf-8")
    progress = json.loads(serialized)
    assert progress["state"] == "RUNTIME_CONTEXT_BLOCKED"
    assert private_error not in serialized
    assert "error" not in progress


def test_lab_resolves_only_an_explicit_release_pinned_prompt(monkeypatch) -> None:
    runner = _lab_runner_module()
    captured = {}
    managed = _managed_qualification_prompt()

    class Resolver:
        def resolve(self, user_context):
            captured["user_context"] = user_context
            return managed

    class Factory:
        def __init__(self, config):
            captured["config"] = config

        def create(self):
            return Resolver()

    monkeypatch.setattr(runner, "OrdinaryTradeMappingPromptResolverFactory", Factory)

    resolved = runner._resolve_mapping_prompt(
        db_path=Path("/private/prompt.db"),
        prompt_id="managed-candidate-id",
        prompt_command="broker_ordinary_trade_semantic_mapping_rnd_v23",
        prompt_version="managed-candidate-version",
        prompt_hash="a" * 64,
        ordinary_user_id="ordinary-user",
    )

    assert resolved is managed
    assert captured["config"].prompt_id == "managed-candidate-id"
    assert captured["config"].command is None
    assert captured["config"].required_command == "broker_ordinary_trade_semantic_mapping_rnd_v23"
    assert captured["config"].release_prompt_version == "managed-candidate-version"
    assert captured["config"].release_prompt_hash == "a" * 64
    assert captured["user_context"].user_id == "ordinary-user"
