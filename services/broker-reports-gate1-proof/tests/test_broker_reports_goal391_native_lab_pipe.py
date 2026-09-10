from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "openwebui_actions" / "goal391_mapping_lab_pipe.py"
BUNDLE = ROOT / "openwebui_actions" / "goal391_mapping_lab_pipe_bundled.py"
PRODUCT_MAPPING_RUNTIME = ROOT / "broker_reports_gate1" / "ordinary_trade_mapping_runtime.py"


def _load_source_module():
    spec = importlib.util.spec_from_file_location("goal391_native_lab_pipe", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clear_broker_reports_modules() -> None:
    for name in list(sys.modules):
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
            del sys.modules[name]


def _load_bundle_module():
    _clear_broker_reports_modules()
    spec = importlib.util.spec_from_file_location("goal391_native_lab_bundle", BUNDLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ordinary_user():
    return {"id": "ordinary-test-user", "role": "user"}


def _assessment(node_id: str) -> dict:
    return {
        "expected_status": "COMPLETE",
        "required_table_decisions": [
            {
                "table_node_id": node_id,
                "disposition": "NO_NAMED_CONSUMER",
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
            }
        ],
        "unresolved_table_node_ids": [],
        "forbidden_qualified_mapping_table_node_ids": [node_id],
    }


def _slot(index: int, *, source_case_id: str = "historical-source-case") -> dict:
    document_id = f"document-{index}"
    return {
        "slot_id": f"slot-{index}",
        "historical_source_scope": {
            "case_id": source_case_id,
            "chat_id": None,
            "workspace_model_id": "historical-source-model",
        },
        "source_openwebui_file_id": f"source-file-{index}",
        "canonical_identity": {
            "document_id": document_id,
            "canonical_root_sha256": f"root-{index}",
            "source_sha256": f"source-sha-{index}",
        },
        "target_table_node_ids": [f"table-{index}"],
        "confirmed_understandings": [],
        "frozen_mappings": [],
        "expected_assessment": _assessment(f"table-{index}"),
    }


def _plan(module, *, slots=None) -> str:
    plan = {
        "schema_version": module.SERVER_BOUND_CASE_PLAN_SCHEMA_VERSION,
        "plan_ref": "opaque-plan-ref",
        "plan_digest": "",
        "ordinary_test_user_id": "ordinary-test-user",
        "slots": slots if slots is not None else [_slot(1), _slot(2)],
    }
    digest_input = dict(plan)
    digest_input.pop("plan_digest")
    plan["plan_digest"] = module.Goal391ServerBoundCaseLoader._sha256(digest_input)
    return json.dumps(plan)


def _envelope(slot: dict):
    identity = slot["canonical_identity"]
    return SimpleNamespace(
        document_id=identity["document_id"],
        canonical_version_id="canonical-" + identity["document_id"],
        canonical_root_sha256=identity["canonical_root_sha256"],
        artifact={
            "source": {
                "source_artifact_ref": "source-" + identity["document_id"],
                "source_sha256": identity["source_sha256"],
            },
            "opaque": "not a test Canonical",
        },
    )


def _install_read_owners(monkeypatch, module, slots):
    calls = {"factory": [], "reader": [], "selection": []}
    envelopes = {
        slot["canonical_identity"]["document_id"]: _envelope(slot)
        for slot in slots
    }

    class FakeStoreFactory:
        def __init__(self, config):
            calls["config"] = config

        def create_read_only(self):
            calls["factory"].append("create_read_only")
            return object()

        def create(self):
            raise AssertionError("write-capable ArtifactStore is forbidden")

    class FakeReader:
        def read_envelope(self, manifest_ref, context, *, expected_normalization_run_id):
            slot_id = str(manifest_ref).removeprefix("manifest-")
            document_id = next(
                slot["canonical_identity"]["document_id"]
                for slot in slots
                if slot["slot_id"] == slot_id
            )
            calls["reader"].append(
                (document_id, context, expected_normalization_run_id)
            )
            return envelopes[document_id]

    class FakeReaderFactory:
        def __init__(self, *, store, read_enabled):
            assert store is not None
            assert read_enabled is True

        def create(self):
            return FakeReader()

    monkeypatch.setattr(module, "ArtifactStoreFactory", FakeStoreFactory)
    monkeypatch.setattr(module, "CanonicalReaderFactory", FakeReaderFactory)

    class FakeSelectionIssuer:
        def __init__(self, *, store, reader, resolver):
            assert store is not None and reader is not None and resolver is not None

        def issue_from_source_files(self, *, corpus_id, requests):
            assert corpus_id == "opaque-plan-ref"
            requests = tuple(requests)
            calls["selection"].extend(requests)
            selections = []
            for request in requests:
                source = next(slot for slot in slots if slot["slot_id"] == request.slot_id)
                scope = source["historical_source_scope"]

                def access_context(*, require_source_available, request=request, scope=scope):
                    return module.ArtifactAccessContext(
                        user_id=request.context.user_id,
                        normalization_run_id=f"resolved-run-{request.slot_id}",
                        case_id=scope["case_id"],
                        chat_id=scope["chat_id"],
                        workspace_model_id=scope["workspace_model_id"],
                        allow_private=True,
                        require_source_available=require_source_available,
                    )

                selections.append(
                    SimpleNamespace(
                        slot_id=request.slot_id,
                        manifest_ref=f"manifest-{request.slot_id}",
                        normalization_run_id=f"resolved-run-{request.slot_id}",
                        access_context=access_context,
                    )
                )
            return SimpleNamespace(selections=tuple(selections))

    monkeypatch.setattr(module, "Goal391PrivateSelectionBindingIssuer", FakeSelectionIssuer)
    return calls


def _loader(module, plan: str):
    valves = SimpleNamespace(
        ordinary_test_user_id="ordinary-test-user",
        cases_required_total=2,
        case_control_plan_json=plan,
        artifact_store_path="/safe/artifacts.sqlite3",
        artifact_payload_root="/safe/payloads",
    )
    return module.Goal391ServerBoundCaseLoader(valves=valves)


def test_native_lab_accepts_one_sealed_case_only_when_its_valve_is_one():
    module = _load_source_module()
    slot = _slot(1)
    plan = _plan(module, slots=[slot])
    valves = SimpleNamespace(
        ordinary_test_user_id="ordinary-test-user",
        cases_required_total=1,
        case_control_plan_json=plan,
        artifact_store_path="/safe/artifacts.sqlite3",
        artifact_payload_root="/safe/payloads",
    )
    loaded = module.Goal391ServerBoundCaseLoader(valves=valves)._read_plan()
    assert [item["slot_id"] for item in loaded["slots"]] == ["slot-1"]


def test_server_bound_loader_rejects_human_assessment_outside_selected_tables(
    monkeypatch,
):
    module = _load_source_module()
    slot = _slot(1)
    calls = _install_read_owners(monkeypatch, module, [slot])
    slot["expected_assessment"]["required_table_decisions"][0]["table_node_id"] = (
        "table-not-in-scope"
    )
    slot["expected_assessment"]["forbidden_qualified_mapping_table_node_ids"] = (
        ["table-not-in-scope"]
    )
    plan = json.loads(_plan(module, slots=[slot]))
    digest_material = dict(plan)
    digest_material.pop("plan_digest")
    plan["plan_digest"] = module.Goal391ServerBoundCaseLoader._sha256(
        digest_material
    )
    valves = SimpleNamespace(
        ordinary_test_user_id="ordinary-test-user",
        cases_required_total=1,
        case_control_plan_json=json.dumps(plan),
        artifact_store_path="/safe/artifacts.sqlite3",
        artifact_payload_root="/safe/payloads",
    )
    with pytest.raises(module.Goal391MappingLabPipeError) as exc:
        module.Goal391ServerBoundCaseLoader(valves=valves).load(
            user=_ordinary_user()
        )
    assert exc.value.code == "goal391_lab_control_plan_slot_invalid"
    assert calls["factory"] == []


def test_server_bound_loader_preserves_a_chat_only_source_scope(monkeypatch):
    module = _load_source_module()
    slot = _slot(1, source_case_id=None)
    slot["historical_source_scope"]["chat_id"] = "historical-source-chat"
    calls = _install_read_owners(monkeypatch, module, [slot])
    plan = _plan(module, slots=[slot])
    valves = SimpleNamespace(
        ordinary_test_user_id="ordinary-test-user",
        cases_required_total=1,
        case_control_plan_json=plan,
        artifact_store_path="/safe/artifacts.sqlite3",
        artifact_payload_root="/safe/payloads",
    )
    module.Goal391ServerBoundCaseLoader(valves=valves).load(user=_ordinary_user())
    request = calls["selection"][0]
    assert request.context.case_id is None
    assert request.context.chat_id == "historical-source-chat"


def test_preflight_rejects_a_resealed_plan_that_omits_a_canonical_table(
    monkeypatch,
):
    module = _load_source_module()
    monkeypatch.setattr(module, "validate_canonical_artifact", lambda _value: {"passed": True})
    case = {
        "case_id": "opaque-case",
        "canonical": {
            "nodes": [
                {"node_type": "TABLE", "node_id": "table-1"},
                {"node_type": "TABLE", "node_id": "table-2"},
            ]
        },
        "canonical_binding": {},
        "confirmed_understandings": [],
        "target_table_node_ids": ["table-1"],
        "frozen_mappings": [],
        "user_scope_sha256": "opaque",
        "expected_assessment": _assessment("table-1"),
    }
    pipe = module.Pipe()
    pipe.valves.cases_required_total = 1
    with pytest.raises(module.Goal391MappingLabPipeError) as exc:
        pipe._preflight(cases=[case])
    assert exc.value.code == "goal391_lab_target_table_scope_mismatch"


def test_native_lab_pipe_uses_only_factory_readers_for_server_bound_cases():
    source = SOURCE.read_text(encoding="utf-8")
    assert "import sqlite3" not in source
    assert "SqliteArtifactStoreAdapter" not in source
    assert "ArtifactStoreFactory" in source
    assert "create_read_only()" in source
    assert "CanonicalReaderFactory" in source
    assert "read_envelope" in source
    assert "issue_from_source_files" in source
    assert "RightBank" not in source
    assert "Declaration" not in source
    # The shared structured client owns the native OpenWebUI completion
    # dependency.  The lab must not recreate an identity/provider bridge.
    assert "completion_resolver=" not in source
    assert "generate_chat_completion" not in source
    assert 'source="openwebui_server"' in source
    assert ".create_async().resolve(" in source
    assert "prompt_db_path" not in source
    assert 'source="openwebui_sqlite"' not in source
    assert "grouped_response_v14" in source
    assert "expand_grouped_response" in source
    assert "grouped_mapping_response_format" in source


def test_product_and_lab_use_the_same_strict_mapping_response_contract():
    """The lab cannot accept a provider response the product would reject."""

    product_source = PRODUCT_MAPPING_RUNTIME.read_text(encoding="utf-8")
    lab_source = SOURCE.read_text(encoding="utf-8")
    helper = "require_strict_json_schema_response("

    assert helper in product_source
    assert helper in lab_source
    assert lab_source.index(helper) > lab_source.index("response = await client.extract(")
    assert lab_source.index(helper) < lab_source.index("response_value = (")


def test_server_bound_loader_reads_exact_two_attested_slots_without_writes(monkeypatch):
    module = _load_source_module()
    slots = [
        _slot(1, source_case_id="historical-source-case-1"),
        _slot(2, source_case_id="historical-source-case-2"),
    ]
    calls = _install_read_owners(monkeypatch, module, slots)
    cases = _loader(module, _plan(module, slots=slots)).load(user=_ordinary_user())
    assert calls["factory"] == ["create_read_only"]
    assert calls["config"].mode == "sqlite"
    assert [item[0] for item in calls["reader"]] == ["document-1", "document-2"]
    assert all(item[1].user_id == "ordinary-test-user" for item in calls["reader"])
    assert [item[1].case_id for item in calls["reader"]] == [
        "historical-source-case-1",
        "historical-source-case-2",
    ]
    assert [item.openwebui_file_id for item in calls["selection"]] == [
        "source-file-1",
        "source-file-2",
    ]
    assert [case["case_id"] for case in cases] == ["slot-1", "slot-2"]


def test_server_bound_loader_rejects_wrong_user_before_reading(monkeypatch):
    module = _load_source_module()
    slots = [_slot(1), _slot(2)]
    calls = _install_read_owners(monkeypatch, module, slots)
    with pytest.raises(module.Goal391MappingLabPipeError) as exc:
        _loader(module, _plan(module, slots=slots)).load(
            user={"id": "ordinary-test-user", "role": "admin"}
        )
    assert exc.value.code == "goal391_lab_access_denied"
    assert calls["factory"] == []
    assert calls["reader"] == []


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda plan: plan.update(plan_digest="0" * 64), "goal391_lab_control_plan_digest_invalid"),
        (lambda plan: plan.update(slots=[]), "goal391_lab_control_plan_invalid"),
        (
            lambda plan: plan["slots"][1].update(slot_id=plan["slots"][0]["slot_id"]),
            "goal391_lab_control_plan_duplicate_scope",
        ),
    ],
)
def test_server_bound_loader_rejects_bad_or_duplicate_control_scope_before_store(monkeypatch, mutate, expected):
    module = _load_source_module()
    slots = [_slot(1), _slot(2)]
    calls = _install_read_owners(monkeypatch, module, slots)
    plan = json.loads(_plan(module, slots=slots))
    mutate(plan)
    if expected == "goal391_lab_control_plan_duplicate_scope":
        digest_material = dict(plan)
        digest_material.pop("plan_digest")
        plan["plan_digest"] = module.Goal391ServerBoundCaseLoader._sha256(
            digest_material
        )
    with pytest.raises(module.Goal391MappingLabPipeError) as exc:
        _loader(module, json.dumps(plan)).load(user=_ordinary_user())
    assert exc.value.code == expected
    assert calls["factory"] == []


def test_server_bound_loader_rejects_browser_chat_binding_claim_before_store(monkeypatch):
    module = _load_source_module()
    slots = [_slot(1), _slot(2)]
    calls = _install_read_owners(monkeypatch, module, slots)
    plan = json.loads(_plan(module, slots=slots))
    plan["outer_browser_chat_id"] = "browser-chat"
    digest_material = dict(plan)
    digest_material.pop("plan_digest")
    plan["plan_digest"] = module.Goal391ServerBoundCaseLoader._sha256(
        digest_material
    )
    with pytest.raises(module.Goal391MappingLabPipeError) as exc:
        _loader(module, json.dumps(plan)).load(user=_ordinary_user())
    assert exc.value.code == "goal391_lab_control_plan_invalid"
    assert calls["factory"] == []


def test_server_bound_loader_fails_closed_when_active_canonical_misbinding(monkeypatch):
    module = _load_source_module()
    slots = [_slot(1), _slot(2)]
    _install_read_owners(monkeypatch, module, slots)
    bad = _envelope(slots[0])
    bad.canonical_root_sha256 = "different-root"

    class MismatchReader:
        def read_envelope(self, manifest_ref, _context, *, expected_normalization_run_id):
            assert expected_normalization_run_id
            return bad if manifest_ref == "manifest-slot-1" else _envelope(slots[1])

    class MismatchReaderFactory:
        def __init__(self, *, store, read_enabled):
            assert store is not None and read_enabled is True

        def create(self):
            return MismatchReader()

    monkeypatch.setattr(module, "CanonicalReaderFactory", MismatchReaderFactory)
    with pytest.raises(module.Goal391MappingLabPipeError) as exc:
        _loader(module, _plan(module, slots=slots)).load(user=_ordinary_user())
    assert exc.value.code == "goal391_lab_canonical_binding_mismatch"


def test_auxiliary_task_is_terminal_before_user_or_case_loading():
    module = _load_source_module()
    receipt = json.loads(asyncio.run(module.Pipe().pipe({}, __user__=_ordinary_user(), __request__=object(), __task__="title_generation")))
    assert receipt["status"] == "BLOCKED"
    assert receipt["terminal_error"] == "goal391_lab_auxiliary_task_forbidden"
    assert receipt["corpus"]["provider_calls_started_total"] == 0


def test_pipe_requires_request_and_rejects_untrusted_body_before_case_reading():
    module = _load_source_module()
    pipe = module.Pipe()
    pipe.valves.ordinary_test_user_id = "ordinary-test-user"
    missing_request = json.loads(asyncio.run(pipe.pipe({}, __user__=_ordinary_user())))
    body_input = json.loads(asyncio.run(pipe.pipe({"canonical": "untrusted"}, __user__=_ordinary_user(), __request__=object())))
    assert missing_request["terminal_error"] == "goal391_lab_request_required"
    assert body_input["terminal_error"] == "goal391_lab_body_input_forbidden"


@pytest.mark.parametrize("form_data", [{"chat_id": "forbidden"}, {"parent_id": "forbidden"}, {"message_id": "forbidden"}, {"metadata": {"chat_id": "forbidden"}}, {"metadata": {"parent_id": "forbidden"}}])
def test_inner_completion_refuses_all_chat_identifiers(form_data):
    module = _load_source_module()
    with pytest.raises(module.Goal391MappingLabPipeError) as exc:
        module.Pipe._require_stateless_form(form_data)
    assert exc.value.code == "goal391_lab_chat_identifier_forbidden"


def test_safe_receipt_has_no_browser_chat_binding_claim_and_no_inner_chat():
    module = _load_source_module()
    receipt = module.Pipe()._blocked_receipt("goal391_lab_access_denied")
    serialized = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    assert set(receipt) == {"schema_version", "status", "corpus", "constraints", "terminal_error"}
    assert "canonical_root" not in serialized
    assert "source_artifact_ref" not in serialized
    assert "prompt" not in serialized
    assert "content" not in serialized
    assert receipt["constraints"] == {
        "retries": 0, "best_of_n": False, "manual_output_repair": False,
        "inner_provider_chat_id": "forbidden",
        "inner_provider_parent_id": "forbidden", "inner_chat_created": False,
        "artifact_store_mutation": False, "canonical_mutation": False,
        "right_bank_mutation": False, "xml_mutation": False,
    }
    assert "outer_browser_chat" not in receipt["constraints"]


def test_preflight_receipt_is_terminal_and_has_zero_provider_calls():
    module = _load_source_module()
    pipe = module.Pipe()
    receipt = pipe._preflight_receipt([{"case": {}}, {"case": {}}])
    assert receipt["status"] == "PREFLIGHT_READY"
    assert receipt["terminal_error"] is None
    assert receipt["corpus"] == {
        "cases_total": 2,
        "provider_calls_started_total": 0,
        "provider_calls_returned_total": 0,
        "records": [],
    }
    assert receipt["constraints"] == pipe._blocked_receipt("x")["constraints"]


def test_lab_execute_rejects_a_non_strict_provider_response_before_semantic_validation(
    monkeypatch,
):
    module = _load_source_module()

    class NonStrictClient:
        async def extract(self, **_kwargs):
            return SimpleNamespace(
                structured_output_mode="openwebui_response_format_json_schema",
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
                fallback_used=True,
                repair_attempt_count=0,
                execution_metadata={"provider": "test"},
            )

        @staticmethod
        def qualification_lifecycle_snapshot():
            return {
                "local_invocations_total": 1,
                "provider_submissions_total": 1,
                "provider_responses_total": 1,
            }

    class ClientFactory:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def create():
            return NonStrictClient()

    monkeypatch.setattr(module, "Gate2StructuredModelClientFactory", ClientFactory)
    receipt = asyncio.run(
        module.Pipe()._execute(
            cases=[{"package": {}}],
            prompt=object(),
            request=object(),
            user=_ordinary_user(),
        )
    )

    assert receipt["status"] == "FAILED"
    assert receipt["terminal_error"] == (
        "goal391_lab_ordinary_trade_mapping_strict_output_required"
    )
    assert receipt["corpus"]["provider_calls_started_total"] == 1
    assert receipt["corpus"]["provider_calls_returned_total"] == 1
    assert receipt["corpus"]["records"] == []


def test_safe_record_accepts_valid_selected_instructional_evidence_subset():
    module = _load_source_module()
    expected = {
        "expected_status": "COMPLETE",
        "required_table_decisions": [
            {
                "table_node_id": "instruction-1",
                "disposition": "NO_NAMED_CONSUMER",
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
            },
            {
                "table_node_id": "instruction-2",
                "disposition": "NO_NAMED_CONSUMER",
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
            },
        ],
        "unresolved_table_node_ids": [],
        "forbidden_qualified_mapping_table_node_ids": [
            "instruction-1", "instruction-2"
        ],
    }
    owner_entry = {"context_ref": "context", "relation": "supports"}
    item = {
        "case": {
            "case_id": "opaque-case",
            "canonical_binding": {"canonical_root_sha256": "opaque-root"},
            "target_table_node_ids": ["instruction-1", "instruction-2"],
            "expected_assessment": expected,
        },
        "owner_envelopes": {
            "instruction-1": [owner_entry] * 5,
            "instruction-2": [owner_entry] * 5,
        },
    }
    outcome = {
        "status": "COMPLETE",
        "qualification_receipts": [],
        "table_resolutions": [
            {
                "table_node_id": "instruction-1",
                "disposition": "NO_NAMED_CONSUMER",
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                "classification_evidence": [owner_entry],
            },
            {
                "table_node_id": "instruction-2",
                "disposition": "NO_NAMED_CONSUMER",
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                "classification_evidence": [owner_entry],
            },
        ],
    }

    record = module.Pipe()._safe_record(item=item, outcome=outcome)

    assert record["outcome"] == "PASS"
    assert record["owner_classification_envelope_total"] == 10
    assert record["actual_classification_envelope_total"] == 2


def test_safe_record_rejects_missing_instructional_evidence():
    module = _load_source_module()
    item = {
        "case": {
            "case_id": "opaque-case",
            "canonical_binding": {"canonical_root_sha256": "opaque-root"},
            "target_table_node_ids": ["instruction-1"],
            "expected_assessment": _assessment("instruction-1"),
        },
        "owner_envelopes": {"instruction-1": [{"context_ref": "context"}]},
    }
    outcome = {
        "status": "COMPLETE",
        "qualification_receipts": [],
        "table_resolutions": [
            {
                "table_node_id": "instruction-1",
                "disposition": "NO_NAMED_CONSUMER",
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                "classification_evidence": [],
            }
        ],
    }

    assert module.Pipe()._safe_record(item=item, outcome=outcome)["outcome"] == "FAIL"


def test_safe_record_preserves_currency_assertion_table_decisions():
    module = _load_source_module()
    item = {
        "case": {
            "case_id": "opaque-case",
            "canonical_binding": {"canonical_root_sha256": "opaque-root"},
            "target_table_node_ids": ["table-1"],
            "expected_assessment": {
                "expected_status": "CURRENCY_ASSERTION_REQUIRED",
                "required_table_decisions": [
                    {"table_node_id": "table-1", "disposition": "SECURITY_TRADES"}
                ],
                "unresolved_table_node_ids": [],
                "forbidden_qualified_mapping_table_node_ids": [],
            },
        },
        "owner_envelopes": {},
    }
    outcome = {
        "status": "CURRENCY_ASSERTION_REQUIRED",
        "qualification_receipts": [],
        "table_resolutions": [],
        "currency_mapping_plan": {
            "response": {"table_decisions": [{"disposition": "SECURITY_TRADES"}]}
        },
    }
    assert module.Pipe()._safe_record(item=item, outcome=outcome)["outcome"] == "PASS"


def test_safe_record_requires_the_exact_unresolved_scope():
    module = _load_source_module()
    item = {
        "case": {
            "case_id": "opaque-case",
            "canonical_binding": {"canonical_root_sha256": "opaque-root"},
            "target_table_node_ids": ["table-1"],
            "expected_assessment": {
                "expected_status": "SPECIALIST_REVIEW_REQUIRED",
                "required_table_decisions": [],
                "unresolved_table_node_ids": ["table-1"],
                "forbidden_qualified_mapping_table_node_ids": [],
            },
        },
        "owner_envelopes": {},
    }
    outcome = {
        "status": "SPECIALIST_REVIEW_REQUIRED",
        "qualification_receipts": [],
        "table_resolutions": [],
    }
    assert module.Pipe()._safe_record(item=item, outcome=outcome)["outcome"] == "PASS"
    item["case"]["expected_assessment"]["unresolved_table_node_ids"] = []
    assert module.Pipe()._safe_record(item=item, outcome=outcome)["outcome"] == "FAIL"


def test_unexpected_owner_error_is_reduced_to_one_value_free_terminal_code():
    module = _load_source_module()

    class PrivateProviderFailure(RuntimeError):
        pass

    assert module.Pipe._safe_error_code(PrivateProviderFailure("private source/key/prompt")) == "goal391_lab_internal_failure"


def test_safe_error_code_keeps_only_fixed_contract_identifiers():
    module = _load_source_module()

    assert module.Pipe._safe_error_code(
        module.Goal391GroupedMappingLabError(
            "goal391_grouped_mapping_lab_row_policy_invalid"
        )
    ) == "goal391_lab_goal391_grouped_mapping_lab_row_policy_invalid"
    assert module.Pipe._safe_error_code(
        module.OrdinaryTradeSemanticMappingError(
            "ordinary_trade_semantic_mapping_columns_invalid"
        )
    ) == "goal391_lab_ordinary_trade_semantic_mapping_columns_invalid"
    assert module.Pipe._safe_error_code(
        module.OrdinaryTradeSemanticMappingError(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_fields_invalid",
        )
    ) == "goal391_lab_ordinary_trade_mapping_decision_fields_invalid"
    assert module.Pipe._safe_error_code(
        module.Gate2SourceFactRuntimeError(
            "gate2_model_content_invalid", "private provider/source detail"
        )
    ) == "goal391_lab_gate2_model_content_invalid"
    assert module.Pipe._safe_error_code(
        module.OrdinaryTradeSemanticCompilerError(
            "ordinary_trade_semantic_compiler_mapping_invalid"
        )
    ) == "goal391_lab_ordinary_trade_semantic_compiler_mapping_invalid"


def test_generated_bundle_is_closed_world_and_contains_only_lab_adapter_not_product_flow():
    maintained_modules = {name: module for name, module in sys.modules.items() if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1.")}
    try:
        bundle = _load_bundle_module()
        source = BUNDLE.read_text(encoding="utf-8")
        assert bundle._BUNDLED_PACKAGE_VERSION == "goal391_native_mapping_lab_v1"
        assert "ordinary_trade_semantic_mapping" in bundle._BUNDLED_MODULES
        assert "ordinary_trade_mapping_prompt" in bundle._BUNDLED_MODULES
        assert "goal391_mapping_lab_pipe.py" in source
        assert "Goal391ServerBoundCaseLoader" in source
        assert "SqliteArtifactStoreAdapter" not in source.split("# Begin maintainable source adapter:", 1)[1]
        assert hasattr(bundle.Pipe(), "last_safe_receipt")
    finally:
        _clear_broker_reports_modules()
        sys.modules.update(maintained_modules)
