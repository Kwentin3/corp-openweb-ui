from __future__ import annotations

import ast
import asyncio
import copy
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from broker_reports_gate1 import (
    GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION,
    GATE5_SINGLE_INPUT_HITL_REQUEST_PROFILE,
    GATE5_SINGLE_INPUT_PROPOSAL_SCHEMA_VERSION,
    GATE5_SINGLE_INPUT_QUESTION_RESULT_SCHEMA_VERSION,
    GATE5_SINGLE_INPUT_QUESTION_SCHEMA_VERSION,
    GATE5_SINGLE_INPUT_SUBMISSION_RESULT_SCHEMA_VERSION,
    GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelClientFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5SingleInputHumanLoopRuntime,
    Gate5SingleInputHumanLoopRuntimeFactory,
    Gate5SupplementalFactDiscoveryRuntimeFactory,
    build_retention_policy,
    gate5_single_input_proposal_response_format,
    gate5_single_input_question_response_format,
)
from broker_reports_gate1 import gate5_single_input_human_loop as hitl_module
from broker_reports_gate1.gate5_single_input_human_loop import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
from broker_reports_gate1.gate2_model_requests import Gate2OpenWebUIRequestBuilder
from test_broker_reports_gate4_sql_materialization import _publish_document


MODEL_ID = "gpt-5.6-sol"
DELEGATED_HUMAN_ANSWER = "Покупал за 70 000 рублей"


class SequencedCompletionBoundary:
    def __init__(self, outputs: list[dict[str, Any]]) -> None:
        self._outputs = outputs
        self.calls: list[dict[str, Any]] = []
        self.resolved_user_ids: list[str] = []

    def resolve(self, user_id: str):
        self.resolved_user_ids.append(user_id)
        return self.complete, SimpleNamespace(id=user_id, role="user")

    def complete(
        self,
        *,
        request,
        form_data,
        user,
        bypass_filter=False,
        bypass_system_prompt=False,
    ):
        index = len(self.calls)
        self.calls.append(
            {
                "request": request,
                "form_data": copy.deepcopy(form_data),
                "user": user,
                "bypass_filter": bypass_filter,
                "bypass_system_prompt": bypass_system_prompt,
            }
        )
        return {
            "id": f"g5-hitl-provider-{index + 1}",
            "model": MODEL_ID,
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 20,
                "total_tokens": 60,
            },
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": copy.deepcopy(self._outputs[index])},
                }
            ],
        }


def test_one_human_answer_round_trips_through_strict_model_and_persistence(
    tmp_path: Path,
) -> None:
    config, store, context = _representative_case(tmp_path)
    methodology = _methodology()
    financial_case_before = _financial_case(store=store, context=context)
    assert "acquisition_cost" not in {
        role["role"] for role in financial_case_before[0]["roles"]
    }
    initial = _discovery_runtime(store).check(
        methodology=methodology,
        context=context,
    )
    assert initial["requirements"][0]["status"] == "missing"
    boundary, runtime = _human_runtime(
        store=store,
        context=context,
        outputs=[
            {
                "schema_version": GATE5_SINGLE_INPUT_QUESTION_SCHEMA_VERSION,
                "action": "ask_user",
                "question_text": (
                    "Укажите стоимость приобретения ценной бумаги для текущего "
                    "выбытия, сумму и валюту."
                ),
            },
            {
                "schema_version": GATE5_SINGLE_INPUT_PROPOSAL_SCHEMA_VERSION,
                "action": "propose_fact",
                "amount": "70000.00",
                "currency": "RUB",
            },
        ],
    )
    artifacts_before_question = _supplemental_refs(store, context)

    question = asyncio.run(runtime.ask(methodology=methodology, context=context))

    assert question == {
        "schema_version": GATE5_SINGLE_INPUT_QUESTION_RESULT_SCHEMA_VERSION,
        "status": "awaiting_human",
        "question": {
            "schema_version": GATE5_SINGLE_INPUT_QUESTION_SCHEMA_VERSION,
            "action": "ask_user",
            "question_text": (
                "Укажите стоимость приобретения ценной бумаги для текущего "
                "выбытия, сумму и валюту."
            ),
        },
    }
    assert _supplemental_refs(store, context) == artifacts_before_question

    submitted = asyncio.run(
        runtime.submit(
            methodology=methodology,
            human_answer=DELEGATED_HUMAN_ANSWER,
            context=context,
        )
    )

    assert submitted["schema_version"] == (
        GATE5_SINGLE_INPUT_SUBMISSION_RESULT_SCHEMA_VERSION
    )
    assert submitted["status"] == "accepted"
    assert submitted["proposal"] == {
        "schema_version": GATE5_SINGLE_INPUT_PROPOSAL_SCHEMA_VERSION,
        "action": "propose_fact",
        "amount": "70000.00",
        "currency": "RUB",
    }
    assert submitted["validation"] == {"status": "passed", "errors": []}
    assert submitted["supplemental_fact_ref"].startswith("art_")
    requirement = submitted["requirement_check"]["requirements"][0]
    assert requirement["status"] == "satisfied"
    assert requirement["source"] == {
        "source_kind": "supplemental_fact",
        "supplemental_fact_ref": submitted["supplemental_fact_ref"],
        "value": {
            "kind": "money",
            "amount": "70000.00",
            "currency": "RUB",
        },
        "scope_binding": {
            "scope_kind": "case",
            "case_id": context.case_id,
            "normalization_run_id": context.normalization_run_id,
            "workspace_model_id": context.workspace_model_id,
        },
        "provenance": {
            "source_kind": "user_provided_supplemental",
            "provided_by": "authenticated_user",
            "gate4_derived": False,
            "captured_via": "gate5_supplemental_fact_boundary_v0",
        },
    }
    assert len(_supplemental_refs(store, context)) == 1
    _assert_minimal_model_visible_requests(boundary)

    reopened_store = ArtifactStoreFactory(config).create()
    reopened = _discovery_runtime(reopened_store).check(
        methodology=methodology,
        context=context,
    )
    assert reopened["requirements"][0]["status"] == "satisfied"
    assert reopened["requirements"][0]["source"] == requirement["source"]
    assert _financial_case(store=reopened_store, context=context) == (
        financial_case_before
    )


def test_ambiguous_human_answer_is_rejected_even_if_model_proposes_value(
    tmp_path: Path,
) -> None:
    config, store, context = _representative_case(tmp_path)
    methodology = _methodology()
    boundary, runtime = _human_runtime(
        store=store,
        context=context,
        outputs=[
            {
                "schema_version": GATE5_SINGLE_INPUT_QUESTION_SCHEMA_VERSION,
                "action": "ask_user",
                "question_text": "Укажите одну точную сумму и валюту.",
            },
            {
                "schema_version": GATE5_SINGLE_INPUT_PROPOSAL_SCHEMA_VERSION,
                "action": "propose_fact",
                "amount": "70000.00",
                "currency": "RUB",
            },
        ],
    )
    asyncio.run(runtime.ask(methodology=methodology, context=context))

    rejected = asyncio.run(
        runtime.submit(
            methodology=methodology,
            human_answer="Покупал примерно за 70 000 или 80 000 рублей",
            context=context,
        )
    )

    assert rejected["status"] == "rejected"
    assert rejected["validation"] == {
        "status": "failed",
        "errors": ["human_answer_amount_ambiguous"],
    }
    assert rejected["supplemental_fact_ref"] is None
    assert rejected["requirement_check"]["requirements"][0]["status"] == ("missing")
    reopened_store = ArtifactStoreFactory(config).create()
    assert _supplemental_refs(reopened_store, context) == []
    still_missing = _discovery_runtime(reopened_store).check(
        methodology=methodology,
        context=context,
    )
    assert still_missing["requirements"][0]["status"] == "missing"
    assert len(boundary.calls) == 2


def test_factory_and_runtime_keep_model_scope_and_persistence_separate() -> None:
    factory_source = inspect.getsource(Gate5SingleInputHumanLoopRuntimeFactory)
    runtime_source = inspect.getsource(Gate5SingleInputHumanLoopRuntime)
    module_source = inspect.getsource(hitl_module)
    request_builder_source = inspect.getsource(Gate2OpenWebUIRequestBuilder)
    tree = ast.parse(module_source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert "Gate5SingleInputHumanLoopRuntimeFactory.create" in FACTORY_REQUIRED
    assert "Gate2StructuredModelClientFactory.create" in FACTORY_REQUIRED[1]
    assert (
        "Gate5SupplementalFactDiscoveryRuntimeFactory.create" in (FACTORY_REQUIRED[2])
    )
    assert "Gate5SupplementalFactRuntimeFactory.create" in FACTORY_REQUIRED[3]
    assert "LLM-owned scope, fact binding or persistence" in FORBIDDEN
    assert "Gate5SupplementalFactDiscoveryRuntimeFactory(" in factory_source
    assert "Gate5SupplementalFactRuntimeFactory(" in factory_source
    assert "self._model_client.extract(" in runtime_source
    assert "self._supplemental.put(" in runtime_source
    assert "self._discovery.check(" in runtime_source
    assert "GATE5_SINGLE_INPUT_HITL_REQUEST_PROFILE" in request_builder_source
    assert imports == {
        "__future__",
        "copy",
        "hashlib",
        "re",
        "dataclasses",
        "typing",
        "artifact_models",
        "gate2_model_contracts",
        "gate5_supplemental_fact",
        "gate5_supplemental_fact_discovery",
    }
    for forbidden_path in (
        "Gate4FinancialCaseRuntimeFactory",
        "ArtifactResolver",
        "get_record_unchecked",
        "list_by_case_context",
        "sqlite3",
        "requests",
        "httpx",
        "chat_completion",
    ):
        assert forbidden_path not in module_source
    for representative_literal in (
        "SECURITY_DISPOSAL",
        "acquisition_cost",
        "70000.00",
    ):
        assert representative_literal not in module_source
    question_schema = gate5_single_input_question_response_format()
    proposal_schema = gate5_single_input_proposal_response_format()
    assert question_schema["type"] == "json_schema"
    assert question_schema["json_schema"]["strict"] is True
    assert question_schema["json_schema"]["schema"]["additionalProperties"] is False
    assert proposal_schema["type"] == "json_schema"
    assert proposal_schema["json_schema"]["strict"] is True
    assert proposal_schema["json_schema"]["schema"]["additionalProperties"] is False
    proposal_properties = proposal_schema["json_schema"]["schema"]["properties"]
    assert proposal_properties["amount"]["anyOf"][0]["pattern"] == (
        r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$"
    )
    assert proposal_properties["currency"]["anyOf"][0]["pattern"] == (r"^[A-Z]{3}$")


def _assert_minimal_model_visible_requests(
    boundary: SequencedCompletionBoundary,
) -> None:
    assert boundary.resolved_user_ids == ["g5-hitl-user", "g5-hitl-user"]
    assert len(boundary.calls) == 2
    ask_form = boundary.calls[0]["form_data"]
    interpret_form = boundary.calls[1]["form_data"]
    ask_package = json.loads(ask_form["messages"][1]["content"])
    interpret_package = json.loads(interpret_form["messages"][1]["content"])
    missing_input = {
        "financial_type": "SECURITY_DISPOSAL",
        "value_key": "acquisition_cost",
        "value_kind": "money",
        "currency_required": True,
    }
    assert ask_package == {"phase": "ask", "missing_input": missing_input}
    assert interpret_package == {
        "phase": "interpret",
        "missing_input": missing_input,
        "human_answer": DELEGATED_HUMAN_ANSWER,
    }
    assert ask_form["response_format"] == (
        gate5_single_input_question_response_format()
    )
    assert interpret_form["response_format"] == (
        gate5_single_input_proposal_response_format()
    )
    for form in (ask_form, interpret_form):
        assert form["model"] == MODEL_ID
        assert form["stream"] is False
        assert form["metadata"]["broker_reports_gate5"]["knowledge_rag_used"] is False
        assert (
            form["metadata"]["broker_reports_gate5"]["vectorization_performed"] is False
        )
        model_visible = json.dumps(
            {
                "messages": form["messages"],
                "response_format": form["response_format"],
            },
            ensure_ascii=False,
        )
        for forbidden in (
            "g5-hitl-user",
            "g5-hitl-case",
            "g5-hitl-run-1",
            "broker-reports-ndfl",
            "acquisition-cost-required",
            "security-disposal-1",
            "supplemental_fact_ref",
            "scope_binding",
            "provenance",
        ):
            assert forbidden not in model_visible


def _representative_case(
    tmp_path: Path,
) -> tuple[ArtifactStoreConfig, object, ArtifactAccessContext]:
    config = ArtifactStoreConfig(
        mode="sqlite",
        sqlite_path=tmp_path / "artifacts.sqlite3",
        payload_root=tmp_path / "payloads",
    )
    store = ArtifactStoreFactory(config).create()
    context = ArtifactAccessContext(
        user_id="g5-hitl-user",
        normalization_run_id="g5-hitl-run-1",
        case_id="g5-hitl-case",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    _publish_document(
        store=store,
        context=context,
        document_id="gate5-hitl-document",
        financial_types=("SECURITY_DISPOSAL",),
        sidecar_artifact_id="g3-v2-gate5-hitl",
        created_at="2026-08-09T14:00:00+00:00",
    )
    Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    return config, store, context


def _methodology() -> dict[str, Any]:
    return {
        "schema_version": GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION,
        "requirements": [
            {
                "requirement_id": "acquisition-cost-required",
                "financial_type": "SECURITY_DISPOSAL",
                "value_key": "acquisition_cost",
                "subject_ref": "security-disposal-1",
            }
        ],
    }


def _human_runtime(
    *,
    store,
    context: ArtifactAccessContext,
    outputs: list[dict[str, Any]],
) -> tuple[SequencedCompletionBoundary, Gate5SingleInputHumanLoopRuntime]:
    boundary = SequencedCompletionBoundary(outputs)
    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE5_SINGLE_INPUT_HITL_REQUEST_PROFILE,
            provider_profile_id="openai_gpt",
        ),
        user=SimpleNamespace(id=context.user_id, role="user"),
        request=SimpleNamespace(),
        completion_resolver=boundary.resolve,
    ).create()
    runtime = Gate5SingleInputHumanLoopRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        model_client=client,
        model_id=MODEL_ID,
    ).create()
    return boundary, runtime


def _discovery_runtime(store):
    return Gate5SupplementalFactDiscoveryRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _supplemental_refs(store, context: ArtifactAccessContext) -> list[str]:
    return [
        record.artifact_id
        for record in store.list_by_case_context(context)
        if record.artifact_type == GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE
    ]


def _financial_case(*, store, context: ArtifactAccessContext) -> list[dict]:
    return (
        Gate4FinancialCaseRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .list_by_financial_type(
            context=context,
            financial_type="SECURITY_DISPOSAL",
        )
    )
