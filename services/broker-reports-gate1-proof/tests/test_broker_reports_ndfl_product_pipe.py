from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import threading
from types import ModuleType
from types import SimpleNamespace

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
)
from broker_reports_gate1.gate3_ndfl_workflow import (
    NDFL_WORKFLOW_STABLE_ID,
    NDFL_WORKSPACE_MODEL_STABLE_ID,
    NdflWorkflowError,
)
from broker_reports_gate1.ordinary_trade_declaration_chat_adapter import (
    adapt_current_declaration_request,
    build_public_dialogue_context,
    declaration_change_intent,
    declaration_request_help,
    declaration_request_question,
    declaration_surrogate_preview,
    render_public_dialogue_fallback,
)
from broker_reports_gate1.openwebui_file_bytes import OpenWebUIOwnedFile
from openwebui_actions import broker_reports_gate1_pipe as product_pipe
from openwebui_actions.broker_reports_gate1_pipe import Pipe
from broker_reports_gate1.artifact_retention import build_retention_policy
import test_broker_reports_ordinary_trade_declaration_mvp as declaration_fixtures


class _OwnedFixtureFileResolver:
    def __init__(
        self,
        *,
        user_id: str,
        file_id: str,
        filename: str,
        content_type: str,
        payload: bytes,
    ) -> None:
        self._user_id = user_id
        self._file_id = file_id
        self._filename = filename
        self._content_type = content_type
        self._payload = payload

    async def resolve(self, *, file_id: str, actor_user_id: str) -> OpenWebUIOwnedFile:
        assert (file_id, actor_user_id) == (self._file_id, self._user_id)
        return OpenWebUIOwnedFile(
            file_id=file_id,
            user_id=actor_user_id,
            filename=self._filename,
            content_type=self._content_type,
            payload=self._payload,
            sha256=hashlib.sha256(self._payload).hexdigest(),
        )


def _ready_public_product() -> dict:
    return {
        "status": "DECLARATION_XML_READY",
        "xml_created": True,
        "private_download": {"url": "/private-owner-file"},
        "preparation": {
            "user_actions": [],
            "final_note": {
                "selected_tax_period": "2025",
                "detected_operation_years": ["2025"],
                "profile": {
                    "support": "SUPPORTED",
                    "form_version": "3-НДФЛ, электронный формат 5.20",
                },
                "positions": [],
                "calculated_disposal_fact_ids": ["private-owner-fact"],
                "filing_eligible": True,
            },
        },
    }


def test_native_chat_scope_is_recovered_only_through_owner_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeChats:
        @staticmethod
        async def get_chat_by_id_and_user_id(chat_id: str, user_id: str):
            assert (chat_id, user_id) == ("owned-chat", "user-a")
            return SimpleNamespace(chat={"models": [NDFL_WORKSPACE_MODEL_STABLE_ID]})

    class FakeRequest:
        async def json(self):
            return {"metadata": {"chat_id": "owned-chat"}}

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    chats = ModuleType("open_webui.models.chats")
    chats.Chats = FakeChats
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.chats", chats)

    metadata = asyncio.run(
        Pipe()._server_attested_runtime_metadata(
            request=FakeRequest(),
            metadata={},
            user={"id": "user-a"},
        )
    )

    assert metadata == {
        "chat_id": "owned-chat",
        "model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
    }


def test_completed_host_owned_current_turn_is_replayed_without_reexecution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeChats:
        @staticmethod
        async def get_chat_by_id_and_user_id(chat_id: str, user_id: str):
            assert (chat_id, user_id) == ("owned-chat", "user-a")
            return SimpleNamespace(
                chat={
                    "history": {
                        "currentId": "assistant-current",
                        "messages": {
                            "user-current": {
                                "role": "user",
                                "content": "Изменить дату: 2026-08-25",
                            },
                            "assistant-current": {
                                "role": "assistant",
                                "parentId": "user-current",
                                "model": NDFL_WORKSPACE_MODEL_STABLE_ID,
                                "done": True,
                                "content": "Файл 3-НДФЛ подготовлен.",
                            },
                        },
                    }
                }
            )

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    chats = ModuleType("open_webui.models.chats")
    chats.Chats = FakeChats
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.chats", chats)

    pipe = Pipe()

    async def forbidden_resume(**_kwargs):
        raise AssertionError("completed turn must not re-run domain or presentation owners")

    monkeypatch.setattr(pipe, "_maybe_resume_ndfl_chat_turn", forbidden_resume)
    content = asyncio.run(
        pipe.pipe(
            {
                "messages": [
                    {"role": "user", "content": "Изменить дату: 2026-08-25"}
                ]
            },
            __user__={"id": "user-a"},
            __metadata__={
                "chat_id": "owned-chat",
                "model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
            },
        )
    )

    assert content == "Файл 3-НДФЛ подготовлен."
    assert pipe.last_artifact_manifest == {
        "resumed_case": True,
        "replayed_completed_openwebui_turn": True,
    }
    assert pipe._presentation_llm_calls_total == 0


@pytest.mark.parametrize(
    ("workspace_model", "done", "model", "parent_content"),
    [
        (NDFL_WORKSPACE_MODEL_STABLE_ID, False, NDFL_WORKSPACE_MODEL_STABLE_ID, "Текущий ответ"),
        (NDFL_WORKSPACE_MODEL_STABLE_ID, True, "foreign-model", "Текущий ответ"),
        (NDFL_WORKSPACE_MODEL_STABLE_ID, True, NDFL_WORKSPACE_MODEL_STABLE_ID, "Другой ответ"),
        ("broker_reports_gate1_pipe", True, NDFL_WORKSPACE_MODEL_STABLE_ID, "Текущий ответ"),
    ],
)
def test_completed_turn_replay_rejects_incomplete_foreign_or_misbound_leaf(
    monkeypatch: pytest.MonkeyPatch,
    workspace_model: str,
    done: bool,
    model: str,
    parent_content: str,
) -> None:
    class FakeChats:
        @staticmethod
        async def get_chat_by_id_and_user_id(_chat_id: str, _user_id: str):
            return SimpleNamespace(
                chat={
                    "history": {
                        "currentId": "assistant-current",
                        "messages": {
                            "user-current": {
                                "role": "user",
                                "content": parent_content,
                            },
                            "assistant-current": {
                                "role": "assistant",
                                "parentId": "user-current",
                                "model": model,
                                "done": done,
                                "content": "Старый ответ",
                            },
                        },
                    }
                }
            )

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    chats = ModuleType("open_webui.models.chats")
    chats.Chats = FakeChats
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.chats", chats)

    replay = asyncio.run(
        Pipe()._server_attested_completed_turn_content(
            metadata={"chat_id": "owned-chat", "model_id": workspace_model},
            user={"id": "user-a"},
            interaction_message="Текущий ответ",
        )
    )
    assert replay is None


def test_product_stage_is_disabled_by_default() -> None:
    pipe = Pipe()
    result = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            store=object(),
            context=_context(NDFL_WORKSPACE_MODEL_STABLE_ID),
            artifact_manifest=SimpleNamespace(artifact_refs_by_type={}),
            user={"id": "user"},
            request=object(),
            event_emitter=None,
        )
    )

    assert result == {
        "schema_version": "broker_reports_ndfl_gate3_product_run_v1",
        "enabled": False,
        "status": "disabled",
        "provider_calls_total": 0,
    }


def test_selected_ndfl_workspace_model_reaches_current_route_not_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()
    pipe.valves.require_trigger_phrase = True

    async def current_route(*_args, **_kwargs):
        return {"route": "current_ndfl"}

    monkeypatch.setattr(pipe, "_run_workload", current_route)
    content = asyncio.run(
        pipe.pipe(
            {"messages": [{"role": "user", "content": "current route probe"}]},
            __user__={"id": "user-a"},
            __metadata__={
                "chat_id": "current-route-chat",
                "model_id": "broker-reports-ndfl",
            },
        )
    )

    assert NDFL_WORKSPACE_MODEL_STABLE_ID == "broker-reports-ndfl"
    assert NDFL_WORKSPACE_MODEL_STABLE_ID == NDFL_WORKFLOW_STABLE_ID
    assert content == {"route": "current_ndfl"}


def test_product_stage_rejects_base_pipe_identity_before_provider() -> None:
    pipe = Pipe()
    pipe.valves.ndfl_gate3_enabled = True

    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(
            pipe._maybe_run_ndfl_gate3(
                store=object(),
                context=_context("broker_reports_gate1_pipe"),
                artifact_manifest=SimpleNamespace(artifact_refs_by_type={}),
                user={"id": "user"},
                request=object(),
                event_emitter=None,
            )
        )

    assert failure.value.code == "ndfl_workspace_model_identity_required"


def test_public_pipe_rejects_caller_selected_hidden_declaration_action() -> None:
    pipe = Pipe()
    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(
            pipe.pipe(
                {
                    "broker_reports_declaration_action": {
                        "request_publication_ref": "artifact_" + "a" * 64,
                        "answer": {"kind": "confirmation", "value": True},
                    }
                },
                __user__={"id": "user-a"},
                __metadata__={
                    "chat_id": "case-a",
                    "model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
                },
            )
        )
    assert failure.value.code == "ordinary_trade_declaration_hidden_action_forbidden"


def test_maintained_stage_binds_event_response_to_current_owner_actions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_direct_workspace_fixture(monkeypatch)
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    pipe = Pipe()
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    kwargs = {
        "store": store,
        "context": context,
        "artifact_manifest": SimpleNamespace(artifact_refs_by_type={}),
        "user": {"id": context.user_id},
        "request": object(),
        "event_emitter": None,
        "retention_policy": build_retention_policy(mode="synthetic_dev"),
    }

    first = asyncio.run(pipe._maybe_run_ndfl_gate3(**kwargs))
    assert first["product"]["status"] == "INPUT_REQUIRED"
    assert first["provider_calls_total"] == 0
    while first["product"]["preparation"]["user_actions"]:
        request = first["product"]["preparation"]["user_actions"][0]

        async def event_call(payload, *, answer=_product_chat_answer(request["fact_key"])):
            assert payload["type"] in {"confirmation", "input"}
            return answer

        result = asyncio.run(
                pipe._maybe_run_ndfl_gate3(
                    **kwargs,
                    trusted_interaction_message="показать точный ввод",
                    event_call=event_call,
            )
        )
        assert result["declaration_chat_receipt"]["status"] == "ANSWER_ACCEPTED"
        first = result
    assert result["product"]["status"] == "DECLARATION_XML_READY"
    assert result["product"]["xml_created"] is True
    assert result["declaration_action_receipt"]["fact_created"] is True
    assert result["provider_calls_total"] == 0
    result["product"]["private_download"] = {"url": "/private-owner-file"}
    chat = pipe._standalone_ndfl_chat_content(result)
    assert "Из отчёта: распознаны операции" in chat
    assert "Из отчёта: доход" not in chat
    assert "По проверенному результату: доход 60.00 ₽" in chat
    assert "принятые расходы 43.00 ₽, налоговая база 17.00 ₽" in chat
    assert "исчисленный налог 2 ₽" in chat
    assert "Подтверждено вами" in chat
    assert "Перед подачей" in chat
    assert "не отправлялся в ФНС автоматически" in chat


def test_llm_proposal_creates_no_fact_until_native_confirmation_and_owner_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_direct_workspace_fixture(monkeypatch)
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
        include_store=True,
    )
    pipe = Pipe()
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    kwargs = {
        "store": store,
        "context": context,
        "artifact_manifest": SimpleNamespace(artifact_refs_by_type={}),
        "user": {"id": context.user_id},
        "request": object(),
        "event_emitter": None,
        "retention_policy": build_retention_policy(mode="synthetic_dev"),
    }
    first = asyncio.run(pipe._maybe_run_ndfl_gate3(**kwargs))
    current_ref = first["product"]["preparation"]["user_actions"][0][
        "request_publication_ref"
    ]

    model_calls: list[str] = []

    def completion(**call):
        form_data = call["form_data"]
        turn = json.loads(form_data["messages"][1]["content"])
        user_message = turn["current_user_message"]
        model_calls.append(user_message)
        clarify = user_message == "Не 2025 год"
        visible = (
            "Уточните, пожалуйста, какой год вы подтверждаете."
            if clarify
            else "Я понял ваш ответ как «2025». Подтверждаете эту интерпретацию?"
        )
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "disposition": "CLARIFY" if clarify else "CANDIDATE",
                                "message": visible,
                                "normalized_answer": "" if clarify else "2025",
                                "evidence_quote": "" if clarify else "Беру 2025 год",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda user_id: (completion, type("User", (), {"id": user_id})()),
    )
    negated = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            **kwargs,
            trusted_interaction_message="Не 2025 год",
        )
    )
    assert negated["declaration_chat_receipt"] == {
        "status": "ANSWER_REJECTED",
        "answer_accepted": False,
        "reason_code": "declaration_chat_answer_requires_clarification",
    }
    assert negated["product"]["preparation"]["user_actions"][0][
        "request_publication_ref"
    ] == current_ref

    proposed = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            **kwargs,
            trusted_interaction_message="Беру 2025 год",
        )
    )

    assert proposed["declaration_chat_receipt"] == {
        "status": "ANSWER_CONFIRMATION_REQUIRED",
        "answer_accepted": False,
        "fact_created": False,
        "reason_code": (
            "declaration_chat_interpretation_confirmation_required"
        ),
    }
    assert proposed["product"]["preparation"]["user_actions"][0][
        "request_publication_ref"
    ] == current_ref

    confirmations: list[dict] = []

    async def confirm(payload):
        confirmations.append(payload)
        return True

    confirmed = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            **kwargs,
            trusted_interaction_message="Беру 2025 год",
            event_call=confirm,
        )
    )
    assert confirmed["declaration_chat_receipt"] == {
        "status": "ANSWER_ACCEPTED",
        "answer_accepted": True,
        "fact_created": True,
    }
    assert confirmed["product"]["preparation"]["user_actions"][0][
        "request_publication_ref"
    ] != current_ref
    assert model_calls == ["Не 2025 год", "Беру 2025 год", "Беру 2025 год"]
    assert confirmations[0]["type"] == "confirmation"
    assert "2025" in confirmations[0]["data"]["message"]
    rendered = asyncio.run(
        pipe._render_ndfl_public_dialogue(
            result=confirmed,
            user={"id": context.user_id},
            request=object(),
        )
    )
    assert rendered
    assert model_calls == ["Не 2025 год", "Беру 2025 год", "Беру 2025 год"]
    assert confirmed["public_dialogue"]["presentation_llm_calls_total"] == 3


def test_period_and_profile_mode_are_owner_bound_but_user_presented(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
    )
    first = runtime.run(canonical_artifact_refs=[], context=context)
    period_request = first["product"]["preparation"]["user_actions"][0]

    assert "2025" in declaration_request_question(period_request)
    period_answer = adapt_current_declaration_request(
        message="2022",
        current_requests=[period_request],
    )
    assert period_answer["status"] == "ANSWER_READY"
    assert period_answer["answer"] == {"kind": "code", "value": "2022"}
    runtime.normalize_declaration_action(
        request_publication_ref=period_answer["request_publication_ref"],
        answer=period_answer["answer"],
        context=context,
    )

    mismatch = runtime.run(canonical_artifact_refs=[], context=context)
    mode_request = mismatch["product"]["preparation"]["user_actions"][0]
    question = declaration_request_question(mode_request)
    assert "\u043d\u0435\u0442 \u0442\u043e\u0447\u043d\u043e\u0433\u043e \u043f\u0440\u043e\u0444\u0438\u043b\u044f" in question
    assert "ru_3ndfl_2025_full_target_supplied_case" not in question
    assert "2025" in question
    assert "3-НДФЛ" in question
    assert "5.20" in question
    mode_answer = adapt_current_declaration_request(
        message="\u0422\u043e\u043b\u044c\u043a\u043e \u0430\u043d\u0430\u043b\u0438\u0437",
        current_requests=[mode_request],
    )
    assert mode_answer["status"] == "ANSWER_READY"
    assert mode_answer["answer"] == {"kind": "code", "value": "ANALYSIS_ONLY"}


def test_non_filing_surrogate_is_visible_in_standalone_chat(tmp_path: Path) -> None:
    runtime, context, _providers = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
    )
    period_request = runtime.run(canonical_artifact_refs=[], context=context)[
        "product"
    ]["preparation"]["user_actions"][0]
    runtime.normalize_declaration_action(
        request_publication_ref=period_request["request_publication_ref"],
        answer={"kind": "code", "value": "2022"},
        context=context,
    )
    mode_request = runtime.run(canonical_artifact_refs=[], context=context)[
        "product"
    ]["preparation"]["user_actions"][0]
    runtime.normalize_declaration_action(
        request_publication_ref=mode_request["request_publication_ref"],
        answer={"kind": "code", "value": "SURROGATE_DRAFT"},
        context=context,
    )

    result = runtime.run(canonical_artifact_refs=[], context=context)
    chat = Pipe()._standalone_ndfl_chat_content(result)

    assert result["product"]["status"] == "NON_FILING_SURROGATE_READY"
    assert "ru_3ndfl_2025_full_target_supplied_case" not in chat
    assert "2022" in chat
    assert "2025" in chat
    assert "5.20" in chat
    assert "не подлежит подаче" in chat
    assert "XML и файл для скачивания не созданы" in chat
    assert "owner" not in chat.lower()
    assert "fact_key" not in chat
    assert "REQUIRES_OWNER" not in chat
    assert "[Скачать XML]" not in chat

    tampered = copy.deepcopy(
        result["product"]["preparation"]["surrogate_preview"]
    )
    tampered["profile_tax_period"] = "2024"
    rejected = declaration_surrogate_preview(tampered)
    assert "данные не прошли проверку" in rejected
    assert "ru_3ndfl_2025_full_target_supplied_case" not in rejected


def test_non_filing_surrogate_reaches_the_ordinary_pipe_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_direct_workspace_fixture(monkeypatch)
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
        include_store=True,
    )
    pipe = Pipe()
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    kwargs = {
        "store": store,
        "context": context,
        "artifact_manifest": SimpleNamespace(artifact_refs_by_type={}),
        "user": {"id": context.user_id},
        "request": object(),
        "event_emitter": None,
        "retention_policy": build_retention_policy(mode="synthetic_dev"),
    }

    first = asyncio.run(pipe._maybe_run_ndfl_gate3(**kwargs))
    assert first["product"]["status"] == "INPUT_REQUIRED"

    async def select_period(_payload):
        return "2022"

    mismatch = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            **kwargs,
            trusted_interaction_message="показать точный ввод",
            event_call=select_period,
        )
    )
    assert mismatch["declaration_chat_receipt"]["status"] == "ANSWER_ACCEPTED"
    assert mismatch["product"]["status"] == "INPUT_REQUIRED"

    async def select_surrogate(_payload):
        return "Неподаваемый черновик"

    surrogate = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            **kwargs,
            trusted_interaction_message="показать точный ввод",
            event_call=select_surrogate,
        )
    )
    chat = pipe._standalone_ndfl_chat_content(surrogate)

    assert surrogate["declaration_chat_receipt"]["status"] == "ANSWER_ACCEPTED"
    assert surrogate["product"]["status"] == "NON_FILING_SURROGATE_READY"
    assert "ru_3ndfl_2025_full_target_supplied_case" not in chat
    assert "не подлежит подаче" in chat
    assert "owner" not in chat.lower()
    assert surrogate["product"]["xml_created"] is False
    assert surrogate["declaration"] is None
    assert surrogate["provider_calls_total"] == 0


def test_public_pipe_file_turn_renders_current_non_filing_surrogate(
    tmp_path: Path,
) -> None:
    fixture = Path(__file__).parent / "fixtures/issue306_supported_ordinary_trade.csv"
    payload = fixture.read_bytes()
    pipe = Pipe(
        _file_bytes_resolver=_OwnedFixtureFileResolver(
            user_id="surrogate-maintained-user",
            file_id="surrogate-maintained-file-turn",
            filename=fixture.name,
            content_type="text/csv",
            payload=payload,
        )
    )
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    pipe.valves.artifact_store_path = str(tmp_path / "artifacts.sqlite3")
    pipe.valves.artifact_payload_root = str(tmp_path / "payloads")
    pipe.valves.workload_store_path = str(tmp_path / "workloads.sqlite3")
    pipe.valves.workload_temp_root = str(tmp_path / "workload-temp")
    pipe.valves.artifact_retention_mode = "synthetic_dev"
    file_ref = {
        "type": "file",
        "file": {
            "id": "surrogate-maintained-file-turn",
            "filename": fixture.name,
            "mime_type": "text/csv",
        },
    }
    metadata = {
        "chat_id": "surrogate-maintained-case",
        "case_id": "surrogate-maintained-case",
        "model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
    }
    user = {"id": "surrogate-maintained-user", "email": "", "name": ""}
    public_events = []

    def public_turn(message: str, *, files=None, event_response=None) -> str:
        async def event_call(_payload):
            return event_response

        async def event_emitter(payload):
            public_events.append(payload)

        message_record = {"role": "user", "content": message}
        if files:
            message_record["files"] = files
        return asyncio.run(
            pipe.pipe(
                {"messages": [message_record]},
                __user__=user,
                __metadata__=metadata,
                __event_call__=event_call,
                __event_emitter__=event_emitter,
            )
        )

    public_turn("Initial file processing", files=[file_ref])
    first = pipe.last_artifact_manifest["ndfl_gate3"]
    assert first["product"]["status"] == "INPUT_REQUIRED"

    public_turn("2022")
    mismatch = pipe.last_artifact_manifest["ndfl_gate3"]
    assert mismatch["product"]["status"] == "INPUT_REQUIRED"

    public_turn(
        "\u041d\u0435\u043f\u043e\u0434\u0430\u0432\u0430\u0435\u043c\u044b\u0439 \u0447\u0435\u0440\u043d\u043e\u0432\u0438\u043a"
    )
    selected = pipe.last_artifact_manifest["ndfl_gate3"]
    assert selected["product"]["status"] == "NON_FILING_SURROGATE_READY"
    assert pipe.last_artifact_manifest["resumed_case"] is True

    chat = public_turn("Repeat file processing", files=[file_ref])
    maintained = pipe.last_artifact_manifest["ndfl_gate3"]

    assert maintained["product"]["status"] == "NON_FILING_SURROGATE_READY"
    assert pipe.last_artifact_manifest.get("resumed_case") is None
    assert "ru_3ndfl_2025_full_target_supplied_case" not in chat
    assert "\u043d\u0435 \u043f\u043e\u0434\u043b\u0435\u0436\u0438\u0442 \u043f\u043e\u0434\u0430\u0447\u0435" in chat
    assert "owner" not in chat.lower()
    assert "fact_key" not in chat
    assert "[\u0421\u043a\u0430\u0447\u0430\u0442\u044c XML]" not in chat
    assert maintained["product"]["xml_created"] is False
    assert maintained["declaration"] is None
    assert maintained["provider_calls_total"] == 0

    public_turn("Изменить налоговый период: 2025")
    supported = pipe.last_artifact_manifest["ndfl_gate3"]
    supported_profile = supported["product"]["preparation"]["period_profile"]
    assert supported_profile["selected_tax_period"] == "2025"
    assert supported_profile["profile_support"] == "SUPPORTED"
    assert all(
        item["fact_key"] != "profile_mismatch_mode"
        for item in supported["product"]["preparation"]["user_actions"]
    )

    public_turn("Изменить налоговый период: 2022")
    returned = pipe.last_artifact_manifest["ndfl_gate3"]
    returned_profile = returned["product"]["preparation"]["period_profile"]
    assert returned["product"]["status"] == "INPUT_REQUIRED"
    assert returned_profile["selected_tax_period"] == "2022"
    assert returned_profile["profile_mismatch_mode"] is None
    assert returned["product"]["preparation"]["user_actions"][0]["fact_key"] == (
        "profile_mismatch_mode"
    )

    rendered_events = json.dumps(public_events, ensure_ascii=False)
    assert "Проверяю загруженный файл" in rendered_events
    for hidden in (
        "Gate 1",
        "Gate 2",
        "Gate 3",
        "Gate 5",
        "brjob_",
        "normalization_run_id",
    ):
        assert hidden not in rendered_events


@pytest.mark.parametrize(
    ("fixture_name", "expected_status", "visible_markers"),
    [
        (
            "issue310_open_long_ordinary_trade.csv",
            "OPEN_POSITION_RETAINED",
            ("открытая длинная позиция", "в налоговую базу не включена"),
        ),
        (
            "issue310_sale_only_ordinary_trade.csv",
            "PREPARATION_INCOMPLETE",
            ("историю позиции", "Добавьте отчёт с предшествующими операциями"),
        ),
    ],
)
def test_public_file_turn_explains_non_filing_position_routes(
    tmp_path: Path,
    fixture_name: str,
    expected_status: str,
    visible_markers: tuple[str, ...],
) -> None:
    fixture = Path(__file__).parent / "fixtures" / fixture_name
    payload = fixture.read_bytes()
    pipe = Pipe(
        _file_bytes_resolver=_OwnedFixtureFileResolver(
            user_id="issue310-position-user",
            file_id="issue310-" + fixture.stem,
            filename=fixture.name,
            content_type="text/csv",
            payload=payload,
        )
    )
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    pipe.valves.artifact_store_path = str(tmp_path / "artifacts.sqlite3")
    pipe.valves.artifact_payload_root = str(tmp_path / "payloads")
    pipe.valves.workload_store_path = str(tmp_path / "workloads.sqlite3")
    pipe.valves.workload_temp_root = str(tmp_path / "workload-temp")
    pipe.valves.artifact_retention_mode = "synthetic_dev"
    file_ref = {
        "type": "file",
        "file": {
            "id": "issue310-" + fixture.stem,
            "filename": fixture.name,
            "mime_type": "text/csv",
        },
    }

    first_content = asyncio.run(
        pipe.pipe(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Подготовь 3-НДФЛ по этому отчёту.",
                        "files": [file_ref],
                    }
                ]
            },
            __user__={"id": "issue310-position-user", "email": "", "name": ""},
            __metadata__={
                "chat_id": "issue310-" + fixture.stem,
                "case_id": "issue310-" + fixture.stem,
                "model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
            },
        )
    )
    assert pipe.last_artifact_manifest["ndfl_gate3"]["product"]["status"] == (
        "INPUT_REQUIRED"
    )
    assert "За какой налоговый период" in first_content
    content = asyncio.run(
        pipe.pipe(
            {"messages": [{"role": "user", "content": "2025"}]},
            __user__={"id": "issue310-position-user", "email": "", "name": ""},
            __metadata__={
                "chat_id": "issue310-" + fixture.stem,
                "case_id": "issue310-" + fixture.stem,
                "model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
            },
        )
    )
    result = pipe.last_artifact_manifest["ndfl_gate3"]

    assert result["product"]["status"] == expected_status
    for marker in visible_markers:
        assert marker in content
    assert "XML не создан" in content
    assert "[Скачать XML]" not in content
    assert result["product"]["xml_created"] is False
    assert result["declaration"] is None
    for hidden in (
        "OPEN_POSITION_RETAINED",
        "PREPARATION_INCOMPLETE",
        "gate5_source_fact_acquisition_evidence_horizon_unproven",
        "fact_key",
        "reason codes",
    ):
        assert hidden not in content


def test_ready_summary_never_promotes_unreconciled_xml_values() -> None:
    declaration = {
        "semantic_reconciliation": {
            "status": "failed",
            "representation_proof": {
                "status": "extracted",
                "values": {
                    "income_group": {
                        "total_income": "999999.00",
                        "accepted_expenses": "888888.00",
                        "tax_base": "111111.00",
                        "calculated_tax": "14444",
                        "tax_payable": "14444",
                    }
                },
            },
        }
    }

    context = build_public_dialogue_context(
        product=_ready_public_product(),
        declaration=declaration,
    )
    summary = render_public_dialogue_fallback(context)

    assert "999999" not in summary
    assert "888888" not in summary
    assert "Из отчёта: распознаны операции" in summary
    assert "По проверенному результату" not in summary


def test_ready_summary_keeps_residency_evidence_separate_from_methodology_result() -> None:
    summary = render_public_dialogue_fallback(
        build_public_dialogue_context(
            product=_ready_public_product(),
            declaration={},
        )
    )

    methodology_marker = "Определено по методике:"
    user_marker = "Подтверждено вами:"
    assert methodology_marker in summary
    methodology = summary.split(methodology_marker, 1)[1]
    user_attested = summary.split(user_marker, 1)[1].split(
        methodology_marker, 1
    )[0]

    assert "налоговый статус и суммы" in methodology
    assert "подтверждено методикой" not in methodology.lower()
    assert "статус резидента" not in user_attested.lower()
    assert "только ответы, которые приняты текущим вопросом" in user_attested
    assert "расходов" not in user_attested


def test_human_fact_wait_releases_source_workload_lease_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_direct_workspace_fixture(monkeypatch)
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    pipe = Pipe()
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    kwargs = {
        "store": store,
        "context": context,
        "artifact_manifest": SimpleNamespace(artifact_refs_by_type={}),
        "user": {"id": context.user_id},
        "request": object(),
        "event_emitter": None,
        "retention_policy": build_retention_policy(mode="synthetic_dev"),
    }
    first = asyncio.run(pipe._maybe_run_ndfl_gate3(**kwargs))
    current = first["product"]["preparation"]["user_actions"][0]
    session = SimpleNamespace(terminal=False)
    pipe._active_workload_session = session

    def finalize() -> None:
        assert session.terminal is False
        session.terminal = True

    monkeypatch.setattr(pipe, "_finalize_workload_publication", finalize)

    async def event_call(payload):
        assert session.terminal is True
        assert payload["type"] in {"confirmation", "input"}
        return _product_chat_answer(current["fact_key"])

    result = asyncio.run(
            pipe._maybe_run_ndfl_gate3(
                **kwargs,
                trusted_interaction_message="показать точный ввод",
                event_call=event_call,
        )
    )

    assert result["declaration_chat_receipt"]["status"] == "ANSWER_ACCEPTED"
    assert result["provider_calls_total"] == 0


def test_current_owner_code_request_uses_only_human_readable_presentation() -> None:
    request = {
        "request_publication_ref": "gap-request-publication-current",
        "closure_type": "USER_FACT",
        "fact_key": "filing_instance_identity",
        "question": "Choose initial filing or correction for the 2025 declaration.",
        "answer_contract": {
            "kind": "code",
            "allowed": ["INITIAL", "CORRECTION"],
        },
    }

    assert declaration_request_question(request) == (
        "Выберите вид декларации за 2025 год."
    )
    help_text = declaration_request_help(request)
    assert help_text == (
        "Допустимые ответы: Первичная декларация; Корректирующая декларация."
    )
    assert "INITIAL" not in help_text
    assert adapt_current_declaration_request(
        message="Первичная декларация", current_requests=[request]
    ) == {
        "schema_version": "broker_reports_ordinary_trade_declaration_chat_action_v1",
        "status": "ANSWER_READY",
        "request_publication_ref": "gap-request-publication-current",
        "answer": {"kind": "code", "value": "INITIAL"},
    }
    assert adapt_current_declaration_request(
        message="INITIAL", current_requests=[request]
    )["status"] == "ANSWER_REJECTED"


def test_tax_period_change_intent_accepts_only_a_visible_four_digit_year() -> None:
    assert declaration_change_intent("Изменить налоговый период") == {
        "schema_version": "broker_reports_ordinary_trade_declaration_chat_action_v1",
        "status": "CHANGE_REQUESTED",
        "fact_key": "selected_tax_period",
        "answer": None,
    }
    assert declaration_change_intent("Изменить налоговый период: 2022") == {
        "schema_version": "broker_reports_ordinary_trade_declaration_chat_action_v1",
        "status": "CHANGE_ANSWER_READY",
        "fact_key": "selected_tax_period",
        "answer": {"kind": "code", "value": "2022"},
        "reason_code": None,
    }
    rejected = declaration_change_intent("Изменить налоговый период: 0000")
    assert rejected["status"] == "ANSWER_REJECTED"
    assert rejected["fact_key"] == "selected_tax_period"


def test_new_owner_code_without_exact_label_coverage_fails_closed() -> None:
    request = {
        "request_publication_ref": "gap-request-publication-current",
        "closure_type": "USER_FACT",
        "fact_key": "filing_instance_identity",
        "question": "owner question must not leak",
        "answer_contract": {
            "kind": "code",
            "allowed": ["INITIAL", "CORRECTION", "NEW_OWNER_CODE"],
        },
    }

    assert declaration_request_question(request) == (
        "Ответ на этот запрос временно недоступен."
    )
    assert "NEW_OWNER_CODE" not in declaration_request_help(request)
    result = adapt_current_declaration_request(
        message="Первичная декларация", current_requests=[request]
    )
    assert result == {
        "schema_version": "broker_reports_ordinary_trade_declaration_chat_action_v1",
        "status": "OWNER_REQUEST_INVALID",
        "reason_code": "declaration_chat_presentation_contract_invalid",
    }


def test_unknown_owner_fact_key_fails_closed_without_raw_vocabulary() -> None:
    request = {
        "request_publication_ref": "gap-request-publication-current",
        "closure_type": "USER_FACT",
        "fact_key": "future_owner_fact",
        "question": "RAW OWNER QUESTION",
        "answer_contract": {"kind": "code", "allowed": ["RAW_UNKNOWN"]},
    }

    question = declaration_request_question(request)
    help_text = declaration_request_help(request)
    assert question == "Ответ на этот запрос временно недоступен."
    assert help_text == "Ответ на этот запрос временно недоступен."
    assert "RAW OWNER QUESTION" not in question
    assert "RAW_UNKNOWN" not in help_text
    assert adapt_current_declaration_request(
        message="RAW_UNKNOWN", current_requests=[request]
    ) == {
        "schema_version": "broker_reports_ordinary_trade_declaration_chat_action_v1",
        "status": "OWNER_REQUEST_INVALID",
        "reason_code": "declaration_chat_presentation_contract_invalid",
    }


def test_known_identity_with_misbound_code_contract_fails_closed() -> None:
    request = {
        "request_publication_ref": "gap-request-publication-current",
        "closure_type": "USER_FACT",
        "fact_key": "taxpayer_identity",
        "question": "RAW OWNER QUESTION",
        "answer_contract": {"kind": "code", "allowed": ["RAW_UNKNOWN"]},
    }

    assert declaration_request_question(request) == (
        "Ответ на этот запрос временно недоступен."
    )
    assert "RAW_UNKNOWN" not in declaration_request_help(request)
    assert adapt_current_declaration_request(
        message="RAW_UNKNOWN", current_requests=[request]
    ) == {
        "schema_version": "broker_reports_ordinary_trade_declaration_chat_action_v1",
        "status": "OWNER_REQUEST_INVALID",
        "reason_code": "declaration_chat_presentation_contract_invalid",
    }


def test_known_code_request_with_misbound_text_contract_fails_closed() -> None:
    request = {
        "request_publication_ref": "gap-request-publication-current",
        "closure_type": "USER_FACT",
        "fact_key": "filing_instance_identity",
        "question": "RAW OWNER QUESTION",
        "answer_contract": {
            "kind": "text",
            "allowed": ["INITIAL", "CORRECTION"],
        },
    }

    assert declaration_request_question(request) == (
        "Ответ на этот запрос временно недоступен."
    )
    assert adapt_current_declaration_request(
        message="RAW_ARBITRARY", current_requests=[request]
    ) == {
        "schema_version": "broker_reports_ordinary_trade_declaration_chat_action_v1",
        "status": "OWNER_REQUEST_INVALID",
        "reason_code": "declaration_chat_presentation_contract_invalid",
    }


def test_direct_ndfl_source_blocker_hides_internal_owner_diagnostics() -> None:
    content = Pipe._ndfl_source_user_content(None)

    assert "Расчёт остановлен" in content
    assert "XML не создан" in content
    assert "handoff" not in content
    assert "normrun" not in content
    assert "artifact" not in content.lower()


def test_safe_stop_proof_requires_the_exact_owner_reason_not_generic_stop_text() -> None:
    expected = "gate5_source_fact_acquisition_evidence_horizon_unproven"
    product = {
        "status": "PREPARATION_INCOMPLETE",
        "terminal": expected,
        "gate5": {"blocker_reason_codes": [expected]},
        "preparation": {
            "gap_closure": {
                "user_facing_required_actions": [],
                "internal_owner_required_actions": [{"reason_code": expected}],
            }
        },
    }

    accepted = render_public_dialogue_fallback(
        build_public_dialogue_context(product=product)
    )
    wrong = copy.deepcopy(product)
    wrong["terminal"] = "ordinary_trade_generic_stop"
    wrong["gate5"]["blocker_reason_codes"] = ["ordinary_trade_generic_stop"]
    wrong["preparation"]["gap_closure"]["internal_owner_required_actions"] = [
        {"reason_code": "ordinary_trade_generic_stop"}
    ]
    rejected = render_public_dialogue_fallback(
        build_public_dialogue_context(product=wrong)
    )

    assert "историю позиции" in accepted
    assert "Добавьте отчёт с предшествующими операциями" in accepted
    assert "нельзя достоверно завершить" in rejected
    for hidden in (
        expected,
        "ordinary_trade_generic_stop",
        "Exact status",
        "terminal",
        "reason codes",
    ):
        assert hidden not in accepted
        assert hidden not in rejected


def test_case_note_translates_owner_state_without_internal_vocabulary() -> None:
    product = {
        "preparation": {
            "final_note": {
                "source_completeness_status": "COMPLETE_FOR_OBSERVED_SECURITY_FACTS",
                "position_evaluation_status": "EVALUATED_FROM_SOURCE_FACTS",
                "selected_tax_period": "2025",
                "detected_operation_years": [2024, 2025],
                "profile": {"support": "SUPPORTED", "form_version": "5.20"},
                "positions": [
                    {
                        "asset": "ASSET-A",
                        "state": "OPEN_LONG_PROVEN",
                        "open_long_quantity": "3",
                        "proven_open_short_quantity": "0",
                    }
                ],
                "calculated_disposal_fact_ids": ["fact-private"],
                "required_checks": ["taxpayer_identity", "budget_oktmo"],
                "filing_eligible": False,
            }
        }
    }

    content = render_public_dialogue_fallback(
        build_public_dialogue_context(product=product)
    )

    assert "В операциях обнаружены годы: 2024, 2025" in content
    assert "открытая длинная позиция, остаток 3" in content
    assert (
        "Доступный профиль декларации: 3-НДФЛ за 2025 год, "
        "электронный формат 5.20"
    ) in content
    assert "XML не создан" in content
    for hidden in (
        "COMPLETE_FOR_OBSERVED_SECURITY_FACTS",
        "EVALUATED_FROM_SOURCE_FACTS",
        "OPEN_LONG_PROVEN",
        "taxpayer_identity",
        "budget_oktmo",
        "fact-private",
        "Case note",
    ):
        assert hidden not in content


def test_direct_ndfl_workload_status_hides_job_identity() -> None:
    emitted = []

    async def emitter(payload):
        emitted.append(payload)

    asyncio.run(
        Pipe()._emit_workload_snapshot(
            emitter,
            {"job_id": "brjob_private", "state": "completed"},
            done=True,
            hide_internal=True,
        )
    )

    assert emitted
    rendered = json.dumps(emitted, ensure_ascii=False)
    assert "Подготовка 3-НДФЛ" in rendered
    assert "brjob_private" not in rendered
    assert "completed" not in rendered


def test_current_turn_file_detection_ignores_persisted_chat_files() -> None:
    historical = {"id": "already-bound-source"}

    assert Pipe._current_turn_has_files(
        {
            "files": [historical],
            "user_message": {"role": "user", "content": "Продолжить"},
        }
    ) is False
    assert Pipe._current_turn_has_files(
        {
            "files": [historical, {"id": "new-source"}],
            "user_message": {
                "role": "user",
                "content": "Проверить новый источник",
                "files": [{"id": "new-source"}],
            },
        }
    ) is True


def test_chat_transport_runs_bind_to_one_current_source_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_direct_workspace_fixture(monkeypatch)
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        include_store=True,
    )
    pipe = Pipe()
    first = pipe._current_declaration_execution_context(
        store=store,
        context=replace(context, normalization_run_id="chat-transport-a"),
    )
    second = pipe._current_declaration_execution_context(
        store=store,
        context=replace(context, normalization_run_id="chat-transport-b"),
    )

    assert first == second
    current = product_pipe.OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().current_case(context=context)
    assert first.normalization_run_id == current[0][0].normalization_run_id
    runtime = product_pipe.OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()
    first_result = runtime.run(canonical_artifact_refs=[], context=first)
    second_result = runtime.run(canonical_artifact_refs=[], context=second)

    assert first_result["product"]["status"] == "DECLARATION_XML_READY"
    assert second_result["product"]["status"] == "DECLARATION_XML_READY"
    assert first_result["declaration"]["xml_bytes"] == second_result["declaration"][
        "xml_bytes"
    ]
    assert first_result["declaration"]["receipt_sha256"] == second_result[
        "declaration"
    ]["receipt_sha256"]


def test_maintained_stage_returns_owner_blocker_without_interactive_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    owner_result = {
        "schema_version": "broker_reports_ordinary_trade_production_run_v1",
        "enabled": True,
        "status": "completed",
        "provider_calls_total": 0,
        "product": {
            "status": "PREPARATION_INCOMPLETE",
            "terminal": "ordinary_trade_declaration_canonical_relevant_unmapped",
            "preparation": {
                "status": "PREPARATION_INCOMPLETE",
                "terminals": [
                    "ordinary_trade_declaration_canonical_relevant_unmapped"
                ],
                "declaration_readiness": {"ready": False},
                "gap_closure": {
                    "user_facing_required_actions": [],
                    "internal_owner_required_actions": [
                        {
                            "reason_code": (
                                "ordinary_trade_declaration_canonical_relevant_unmapped"
                            )
                        }
                    ],
                },
            },
        },
    }

    class Runtime:
        @staticmethod
        def run(**_kwargs):
            return copy.deepcopy(owner_result)

        @staticmethod
        async def run_with_automatic_mapping(**_kwargs):
            return copy.deepcopy(owner_result)

    class Factory:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def create():
            return Runtime()

    monkeypatch.setattr(product_pipe, "OrdinaryTradeProductionRuntimeFactory", Factory)

    async def event_call(_payload):
        raise AssertionError("typed owner blocker must not open a human request")

    result = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            store=object(),
            context=_context(NDFL_WORKSPACE_MODEL_STABLE_ID),
            artifact_manifest=SimpleNamespace(artifact_refs_by_type={}),
            user={"id": "user-a"},
            request=object(),
            event_emitter=None,
            event_call=event_call,
        )
    )

    assert result == owner_result
    assert result["product"]["terminal"] == (
        "ordinary_trade_declaration_canonical_relevant_unmapped"
    )
    assert result["provider_calls_total"] == 0


def test_case_note_explains_that_operation_years_are_not_determined() -> None:
    content = render_public_dialogue_fallback(
        build_public_dialogue_context(
            product={
                "status": "PREPARATION_INCOMPLETE",
                "terminal": "ordinary_trade_canonical_evidence_missing",
                "gate5": {
                    "blocker_reason_codes": [
                        "ordinary_trade_canonical_evidence_missing"
                    ]
                },
            "preparation": {
                "final_note": {
                    "source_completeness_status": "CANONICAL_EVIDENCE_MISSING",
                    "position_evaluation_status": (
                        "NOT_EVALUATED_SOURCE_FACTS_UNAVAILABLE"
                    ),
                    "selected_tax_period": None,
                    "detected_operation_years": [],
                    "profile": {
                        "support": "NOT_EVALUATED_SOURCE_COVERAGE_INCOMPLETE"
                    },
                    "positions": [],
                    "calculated_disposal_fact_ids": [],
                    "required_checks": [
                        "ordinary_trade_canonical_evidence_missing"
                    ],
                    "filing_eligible": False,
                }
                },
            },
        )
    )

    assert "Не удалось получить подтверждённый набор операций" in content
    assert "Рассчитанных закрытых продаж: 0" in content
    assert "CANONICAL_EVIDENCE_MISSING" not in content
    assert "ordinary_trade_canonical_evidence_missing" not in content


def test_plain_chat_answer_is_bound_only_to_the_current_owner_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_direct_workspace_fixture(monkeypatch)
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    pipe = Pipe()
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    kwargs = {
        "store": store,
        "context": context,
        "artifact_manifest": SimpleNamespace(artifact_refs_by_type={}),
        "user": {"id": context.user_id},
        "request": object(),
        "event_emitter": None,
        "retention_policy": build_retention_policy(mode="synthetic_dev"),
    }

    first = asyncio.run(pipe._maybe_run_ndfl_gate3(**kwargs))
    current = first["product"]["preparation"]["user_actions"][0]
    replay = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            **kwargs,
            trusted_interaction_message=_product_chat_answer(current["fact_key"]),
        )
    )

    assert replay["product"]["status"] == "INPUT_REQUIRED"
    assert replay["product"]["preparation"]["user_actions"][0][
        "request_publication_ref"
    ] != current["request_publication_ref"]
    assert replay["declaration_action_receipt"]["fact_created"] is True


def test_public_bundled_pipe_reaches_one_idempotent_private_xml_from_chat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_direct_workspace_fixture(monkeypatch)
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path / "case",
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    maintained_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1.")
    }
    for name in list(maintained_modules):
        sys.modules.pop(name, None)
    bundle_path = (
        Path(__file__).resolve().parents[1]
        / "openwebui_actions"
        / "broker_reports_gate1_pipe_bundled.py"
    )
    spec = importlib.util.spec_from_file_location("issue304_public_bundle", bundle_path)
    assert spec is not None and spec.loader is not None
    bundled = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundled)

    rows = {}
    calls = {"upload": 0, "insert": 0, "delete": 0}

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(file_id):
            return rows.get(file_id)

        @staticmethod
        async def insert_new_file(user_id, form):
            calls["insert"] += 1
            row = SimpleNamespace(**form.__dict__, user_id=user_id)
            rows[form.id] = row
            return row

    class Storage:
        @staticmethod
        def upload_file(stream, name, headers):
            assert headers["OpenWebUI-User-Id"] == context.user_id
            calls["upload"] += 1
            contents = stream.read()
            path = tmp_path / "private" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
            return contents, str(path)

        @staticmethod
        def get_file(path):
            return path

        @staticmethod
        def delete_file(path):
            calls["delete"] += 1
            Path(path).unlink(missing_ok=True)

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    files = ModuleType("open_webui.models.files")
    storage = ModuleType("open_webui.storage")
    provider = ModuleType("open_webui.storage.provider")
    files.FileForm = FileForm
    files.Files = Files
    provider.Storage = Storage
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.files", files)
    monkeypatch.setitem(sys.modules, "open_webui.storage", storage)
    monkeypatch.setitem(sys.modules, "open_webui.storage.provider", provider)

    try:
        pipe = bundled.Pipe()
        pipe.valves.ordinary_trade_candidate_enabled = True
        pipe.valves.canonical_gate2_write_enabled = True
        pipe.valves.canonical_gate2_read_enabled = True
        pipe.valves.artifact_store_path = str(store.sqlite_path)
        pipe.valves.artifact_payload_root = str(store.payload_root)
        pipe.valves.artifact_retention_mode = "synthetic_dev"
        metadata = {
            "chat_id": context.case_id,
            "case_id": context.case_id,
            "model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
        }

        event_payloads = []

        def public_turn(
            message: str,
            *,
            event_response=None,
            user_id: str = context.user_id,
        ) -> str:
            async def event_call(payload):
                event_payloads.append(payload)
                if payload.get("type") == "confirmation" and event_response in {
                    "Да",
                    "Нет",
                }:
                    return event_response == "Да"
                return event_response

            return asyncio.run(
                pipe.pipe(
                    {
                        # Native OpenWebUI retains prior chat attachments here;
                        # only user_message identifies the current turn.
                        "files": [{"id": "persisted-source-context"}],
                        "user_message": {"role": "user", "content": message},
                        "messages": [{"role": "user", "content": message}],
                    },
                    __user__={"id": user_id, "email": "", "name": ""},
                    __metadata__=metadata,
                    __event_call__=event_call,
                )
            )

        first_content = public_turn("Подготовить 3-НДФЛ")
        first = pipe.last_artifact_manifest["ndfl_gate3"]
        assert first["product"]["status"] == "INPUT_REQUIRED"
        assert first["product"]["xml_created"] is False
        assert "request_publication_ref" not in first_content
        assert "Допустимые значения" in first_content or "Ответьте" in first_content

        states = {"INPUT_REQUIRED"}
        last_answer = ""
        while first["product"]["preparation"]["user_actions"]:
            action = first["product"]["preparation"]["user_actions"][0]
            fact_key = action["fact_key"]
            if fact_key == "taxpayer_identity":
                rejected = public_turn(
                    "показать точный ввод",
                    event_response="Изменить: 123456789012; Иванов; Иван; Иванович",
                )
                first = pipe.last_artifact_manifest["ndfl_gate3"]
                assert first["declaration_chat_receipt"]["status"] == "ANSWER_REJECTED"
                assert "не принят" in rejected
                last_answer = (
                    "Изменить: 500100732259; Иванов; Иван; Иванович"
                )
            elif fact_key == "declaration_date":
                rejected = public_turn(
                    "показать точный ввод", event_response="2025-99-99"
                )
                first = pipe.last_artifact_manifest["ndfl_gate3"]
                assert first["declaration_chat_receipt"] == {
                    "status": "ANSWER_REJECTED",
                    "answer_accepted": False,
                    "reason_code": "gate5_gap_declaration_date_invalid",
                }
                assert "не принят" in rejected
                last_answer = "2026-08-24"
            else:
                last_answer = _product_chat_answer(fact_key)
            public_turn("показать точный ввод", event_response=last_answer)
            first = pipe.last_artifact_manifest["ndfl_gate3"]
            states.add(first["product"]["status"])

        assert "DRAFT_READY" in states
        assert first["product"]["status"] == "DECLARATION_XML_READY"
        file_id = first["product"]["private_download"]["file_id"]
        assert calls == {"upload": 1, "insert": 1, "delete": 0}
        assert len(rows) == 1

        repeated_content = public_turn("Продолжить")
        repeated = pipe.last_artifact_manifest["ndfl_gate3"]
        assert repeated["product"]["private_download"]["file_id"] == file_id
        assert calls == {"upload": 1, "insert": 1, "delete": 0}
        assert "/api/v1/files/" + file_id in repeated_content
        assert first["provider_calls_total"] == 0
        assert pipe.last_artifact_manifest["resumed_case"] is True
        serialized_events = json.dumps(event_payloads, ensure_ascii=False)
        assert "request_publication_ref" not in serialized_events
        assert "fact_key" not in serialized_events
        assert "500100732259" not in serialized_events
        assert "••••" in serialized_events
        for hidden_owner_vocabulary in (
            "Choose initial filing",
            "State whether the taxpayer",
            "individual_not_ip_not_private_practice",
            "INITIAL",
            "SELF",
            "PAYMENT",
        ):
            assert hidden_owner_vocabulary not in serialized_events

        change_content = public_turn("Изменить дату")
        changing = pipe.last_artifact_manifest["ndfl_gate3"]
        assert changing["product"]["status"] == "DRAFT_READY"
        assert changing["product"]["xml_created"] is False
        assert changing["product"]["preparation"]["checklist_fact_keys"] == [
            "declaration_date"
        ]
        assert "календарную дату" in change_content
        rejected_change = public_turn(
            "показать точный ввод", event_response="2025-99-99"
        )
        changing = pipe.last_artifact_manifest["ndfl_gate3"]
        assert changing["product"]["status"] == "DRAFT_READY"
        assert changing["declaration_chat_receipt"]["status"] == "ANSWER_REJECTED"
        assert "не принят" in rejected_change
        public_turn("показать точный ввод", event_response="2026-08-25")
        corrected = pipe.last_artifact_manifest["ndfl_gate3"]
        corrected_file_id = corrected["product"]["private_download"]["file_id"]
        assert corrected["product"]["status"] == "DECLARATION_XML_READY"
        assert corrected_file_id != file_id
        assert calls == {"upload": 2, "insert": 2, "delete": 0}
        public_turn("Продолжить")
        assert pipe.last_artifact_manifest["ndfl_gate3"]["product"][
            "private_download"
        ]["file_id"] == corrected_file_id
        assert calls == {"upload": 2, "insert": 2, "delete": 0}
    finally:
        for name in list(sys.modules):
            if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
                sys.modules.pop(name, None)
        sys.modules.update(maintained_modules)


def test_xml_delivery_uses_authenticated_openwebui_private_file_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured = {"uploads": 0, "inserts": 0}
    rows = {}
    xml_bytes = b"<root/>"

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(file_id):
            return rows.get(file_id)

        @staticmethod
        async def insert_new_file(user_id, form):
            captured["inserts"] += 1
            captured["user_id"] = user_id
            captured["form"] = form
            row = SimpleNamespace(**form.__dict__, user_id=user_id)
            rows[form.id] = row
            return row

    class Storage:
        @staticmethod
        def upload_file(stream, name, headers):
            captured["uploads"] += 1
            captured["headers"] = headers
            contents = stream.read()
            path = tmp_path / name
            path.write_bytes(contents)
            return contents, str(path)

        @staticmethod
        def get_file(path):
            return path

        @staticmethod
        def delete_file(path):
            Path(path).unlink(missing_ok=True)

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    files = ModuleType("open_webui.models.files")
    storage = ModuleType("open_webui.storage")
    provider = ModuleType("open_webui.storage.provider")
    files.FileForm = FileForm
    files.Files = Files
    provider.Storage = Storage
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.files", files)
    monkeypatch.setitem(sys.modules, "open_webui.storage", storage)
    monkeypatch.setitem(sys.modules, "open_webui.storage.provider", provider)

    context = ArtifactAccessContext(
        user_id="user-a",
        normalization_run_id="run-a",
        case_id="case-a",
        workspace_model_id=NDFL_WORKSPACE_MODEL_STABLE_ID,
        allow_private=True,
    )
    kwargs = {
        "user": {"id": "user-a", "email": "", "name": ""},
        "context": context,
        "filename": "3-ndfl-2025.xml",
        "xml_bytes": xml_bytes,
        "xml_sha256": __import__("hashlib").sha256(xml_bytes).hexdigest(),
        "receipt_sha256": "a" * 64,
    }
    file_id = asyncio.run(Pipe._publish_ndfl_xml_file(**kwargs))
    repeated = asyncio.run(Pipe._publish_ndfl_xml_file(**kwargs))
    successor_receipt = asyncio.run(
        Pipe._publish_ndfl_xml_file(
            **{**kwargs, "receipt_sha256": "b" * 64},
        )
    )

    assert repeated == file_id
    assert successor_receipt == file_id
    assert captured["uploads"] == 1
    assert captured["inserts"] == 1
    assert captured["user_id"] == "user-a"
    assert captured["headers"]["OpenWebUI-User-Id"] == "user-a"
    assert captured["form"].id == file_id
    assert captured["form"].meta["data"]["private_user_artifact"] is True
    assert captured["form"].meta["data"]["receipt_sha256"] == "a" * 64
    assert re.fullmatch(
        r"[0-9a-f]{64}",
        captured["form"].meta["data"]["publication_identity_sha256"],
    )

    rows[file_id].meta["data"]["receipt_sha256"] = "not-a-receipt"
    with pytest.raises(NdflWorkflowError) as corrupted:
        asyncio.run(
            Pipe._publish_ndfl_xml_file(
                **{**kwargs, "receipt_sha256": "c" * 64},
            )
        )
    assert (
        corrupted.value.code
        == "ordinary_trade_declaration_private_file_reuse_binding_invalid"
    )


def test_concurrent_identical_xml_delivery_keeps_one_valid_owner_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rows = {}
    calls = {"upload": 0, "insert": 0, "delete": 0}
    counter_lock = threading.Lock()
    upload_barrier = threading.Barrier(2)
    xml_bytes = b"<root/>"

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(file_id):
            return rows.get(file_id)

        @staticmethod
        async def insert_new_file(user_id, form):
            calls["insert"] += 1
            if form.id in rows:
                return None
            row = SimpleNamespace(**form.__dict__, user_id=user_id)
            rows[form.id] = row
            return row

    class Storage:
        @staticmethod
        def upload_file(stream, name, _headers):
            contents = stream.read()
            path = tmp_path / name
            path.write_bytes(contents)
            with counter_lock:
                calls["upload"] += 1
            upload_barrier.wait()
            return contents, str(path)

        @staticmethod
        def get_file(path):
            return path

        @staticmethod
        def delete_file(path):
            with counter_lock:
                calls["delete"] += 1
            Path(path).unlink(missing_ok=True)

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    files = ModuleType("open_webui.models.files")
    storage = ModuleType("open_webui.storage")
    provider = ModuleType("open_webui.storage.provider")
    files.FileForm = FileForm
    files.Files = Files
    provider.Storage = Storage
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.files", files)
    monkeypatch.setitem(sys.modules, "open_webui.storage", storage)
    monkeypatch.setitem(sys.modules, "open_webui.storage.provider", provider)
    context = ArtifactAccessContext(
        user_id="user-a",
        normalization_run_id="run-a",
        case_id="case-a",
        workspace_model_id=NDFL_WORKSPACE_MODEL_STABLE_ID,
        allow_private=True,
    )
    kwargs = {
        "user": {"id": "user-a", "email": "", "name": ""},
        "context": context,
        "filename": "3-ndfl-2025.xml",
        "xml_bytes": xml_bytes,
        "xml_sha256": __import__("hashlib").sha256(xml_bytes).hexdigest(),
    }

    async def publish_twice():
        return await asyncio.gather(
            Pipe._publish_ndfl_xml_file(**kwargs, receipt_sha256="c" * 64),
            Pipe._publish_ndfl_xml_file(**kwargs, receipt_sha256="d" * 64),
            return_exceptions=True,
        )

    results = asyncio.run(publish_twice())

    assert all(isinstance(item, str) for item in results), results
    assert results[0] == results[1]
    assert len(rows) == 1
    assert Path(next(iter(rows.values())).path).read_bytes() == xml_bytes
    assert len(list(tmp_path.glob("*"))) == 1
    assert calls == {"upload": 2, "insert": 2, "delete": 1}
    assert (
        asyncio.run(
            Pipe._publish_ndfl_xml_file(**kwargs, receipt_sha256="e" * 64)
        )
        == results[0]
    )
    assert calls == {"upload": 2, "insert": 2, "delete": 1}


def test_private_xml_record_failure_removes_partial_storage_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    deleted = []

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(_file_id):
            return None

        @staticmethod
        async def insert_new_file(_user_id, _form):
            return None

    class Storage:
        @staticmethod
        def upload_file(stream, name, _headers):
            contents = stream.read()
            path = tmp_path / name
            path.write_bytes(contents)
            return contents, str(path)

        @staticmethod
        def delete_file(path):
            deleted.append(path)
            Path(path).unlink()

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    files = ModuleType("open_webui.models.files")
    storage = ModuleType("open_webui.storage")
    provider = ModuleType("open_webui.storage.provider")
    files.FileForm = FileForm
    files.Files = Files
    provider.Storage = Storage
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.files", files)
    monkeypatch.setitem(sys.modules, "open_webui.storage", storage)
    monkeypatch.setitem(sys.modules, "open_webui.storage.provider", provider)
    xml_bytes = b"<root/>"
    context = ArtifactAccessContext(
        user_id="user-a",
        normalization_run_id="run-a",
        case_id="case-a",
        workspace_model_id=NDFL_WORKSPACE_MODEL_STABLE_ID,
        allow_private=True,
    )

    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(
            Pipe._publish_ndfl_xml_file(
                user={"id": "user-a"},
                context=context,
                filename="3-ndfl-2025.xml",
                xml_bytes=xml_bytes,
                xml_sha256=__import__("hashlib").sha256(xml_bytes).hexdigest(),
                receipt_sha256="b" * 64,
            )
        )

    assert failure.value.code == "ordinary_trade_declaration_private_file_record_failed"
    assert len(deleted) == 1
    assert not Path(deleted[0]).exists()


def _product_chat_answer(fact_key: str) -> str:
    return {
        "taxpayer_identity": "Подтверждаю",
        "taxpayer_capacity": (
            "Обычное физическое лицо — не ИП и не лицо частной практики"
        ),
        "residency_evidence": (
            "Присутствие: 2025-01-01..2025-07-02; "
            "отсутствие: 2025-07-03..2025-12-31; причины: нет"
        ),
        "ordinary_trade_declaration_zero_scope_confirmed": "Да",
        "filing_instance_identity": "Первичная декларация",
        "declaration_date": "2026-08-24",
        "filing_destination_code": "7705",
        "signer_and_representation": "Подписываю лично",
        "budget_disposition": "Налог к уплате",
        "budget_oktmo": "45382000",
    }[fact_key]


def test_workload_failure_detail_exposes_only_explicit_safe_details() -> None:
    failure = NdflWorkflowError(
        "ndfl_gate3_document_incomplete",
        safe_details={"chunks_rejected": 1},
    )

    assert Pipe._workload_failure_detail(failure) == {"chunks_rejected": 1}
    assert Pipe._workload_failure_detail(RuntimeError("private payload")) is None


def test_human_residual_turn_reuses_one_validated_gate3_artifact() -> None:
    context = _context(NDFL_WORKSPACE_MODEL_STABLE_ID)
    record = SimpleNamespace(
        artifact_id="annotations",
        artifact_type=GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
        user_id=context.user_id,
        normalization_run_id=context.normalization_run_id,
        case_id=context.case_id,
        chat_id=None,
        workspace_model_id=context.workspace_model_id,
        visibility="private_case",
        validation_status="validated",
        lifecycle_status="active",
        purge_status=None,
        expires_at=None,
        source_file_ref={"source_deleted": False},
        payload=None,
        payload_ref=None,
    )
    store = SimpleNamespace(
        list_by_run=lambda run_id: [record] if run_id == "run" else [],
        get_record_unchecked=lambda artifact_id: (
            record if artifact_id == "annotations" else None
        ),
    )

    assert Pipe._persisted_gate3_annotations_artifact_id(
        store=store,
        context=context,
    ) == "annotations"


def test_private_audit_is_exact_external_and_non_overwriting(tmp_path: Path) -> None:
    pipe = Pipe()
    pipe.valves.ndfl_gate3_private_audit_enabled = True
    pipe.valves.ndfl_gate3_private_audit_root = str(tmp_path)
    pipe.valves.ndfl_gate3_private_audit_id = "g3c5_product_test_001"
    envelope = SimpleNamespace(
        artifact={"private": "exact canonical"},
        document_id="document",
        canonical_version_id="version",
        canonical_version_number=1,
        version_status="ACTIVE",
        schema_version="canonical_artifact_v1",
        canonical_root_sha256="a" * 64,
        physical_layout="single_payload",
        component_count=1,
        payload_bytes=100,
    )
    attempt = SimpleNamespace(
        projection={"model_view": {"content": "exact fragment"}},
        dictionary={"labels": [{"meaning": "exact meaning"}]},
        dictionary_managed_binding={"dictionary_identity": {"version": "1"}},
        dictionary_markdown="exact dictionary",
        instruction="exact instruction",
        model_visible_request={"messages": []},
        final_provider_request={"messages": []},
        raw_provider_response={"raw": True},
        raw_model_output={"annotations": []},
        validated_output={"annotations": []},
        validation_status="validated",
        validation_error_code=None,
        execution_metadata={"provider": "test"},
        metrics={"calls": 1},
    )
    role_attempt = SimpleNamespace(
        facts=(),
        role_context={
            "schema_version": "broker_reports_gate3_role_context_v1",
            "accepted_target_aliases": [],
        },
        role_provenance={
            "schema_version": "broker_reports_gate3_role_provenance_v1",
            "facts": [],
        },
        role_pack={"roles": []},
        role_pack_markdown="exact role pack",
        instruction="exact role instruction",
        model_visible_request=None,
        final_provider_request=None,
        raw_provider_response=None,
        raw_model_output=None,
        validated_output={"annotations": []},
        execution_status="skipped_empty",
        validation_error_code=None,
        execution_metadata=None,
        metrics={"provider_called": False},
    )
    outcome = SimpleNamespace(
        chunk={"content": "exact fragment"},
        attempt=attempt,
        role_attempt=role_attempt,
    )
    execution = SimpleNamespace(
        canonical_artifact_ref="manifest",
        activation_receipt=None,
        canonical_before_gate3=envelope,
        canonical_after_gate3=envelope,
        gate3=SimpleNamespace(
            batch_result=SimpleNamespace(
                outcomes=(outcome,),
                merged_output={"annotations": []},
                metrics={
                    "financial_labeling_provider_calls": 1,
                    "role_labeling_provider_calls": 1,
                },
            ),
            annotations_payload={
                "schema_version": "broker_reports_financial_annotations_v2",
                "annotations": [],
            },
            annotations_artifact_id="annotations",
        ),
    )

    receipt = pipe._write_ndfl_private_audit([execution])
    exact_path = tmp_path / "g3c5_product_test_001" / "document_001.exact.json"
    exact = json.loads(exact_path.read_text(encoding="utf-8"))

    assert receipt["status"] == "saved"
    assert pipe._ndfl_provider_calls_total([execution]) == 2
    assert exact["attempts"][0]["projection"]["model_view"]["content"] == (
        "exact fragment"
    )
    assert exact["attempts"][0]["dictionary_markdown"] == "exact dictionary"
    assert exact["attempts"][0]["instruction"] == "exact instruction"
    assert exact["attempts"][0]["raw_model_output"] == {"annotations": []}
    assert exact["attempts"][0]["role_attempt"]["role_pack_markdown"] == (
        "exact role pack"
    )
    assert exact["attempts"][0]["role_attempt"]["role_context"] == {
        "schema_version": "broker_reports_gate3_role_context_v1",
        "accepted_target_aliases": [],
    }
    assert exact["attempts"][0]["role_attempt"]["role_provenance"] == {
        "schema_version": "broker_reports_gate3_role_provenance_v1",
        "facts": [],
    }
    assert exact["financial_annotations_v2"]["annotations"] == []
    with pytest.raises(NdflWorkflowError) as failure:
        pipe._write_ndfl_private_audit([execution])
    assert failure.value.code == "ndfl_private_audit_target_not_new"


def _context(workspace_model_id: str) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="user",
        normalization_run_id="run",
        case_id="case",
        workspace_model_id=workspace_model_id,
        allow_private=True,
    )


def _use_direct_workspace_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    gate4_fixtures = (
        declaration_fixtures.assembly_fixtures.bridge_fixtures.ordinary_fixtures.gate4_fixtures
    )
    original = gate4_fixtures._store_context

    def direct_store_context(root: Path):
        store, context = original(root)
        return store, replace(
            context,
            workspace_model_id=NDFL_WORKSPACE_MODEL_STABLE_ID,
        )

    monkeypatch.setattr(gate4_fixtures, "_store_context", direct_store_context)
