"""Native-owner boundary unit checks; real WebUI/browser proof is still required."""

import ast
import copy
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import NAMESPACE_URL, uuid5


HERE = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


protocol = load("employee_budget_provenance", HERE / "provenance.py")
if "employee_budget_webui_model_binding" not in sys.modules:
    load("employee_budget_webui_model_binding", HERE / "webui_model_binding.py")
extension = load("cost_filter_under_test", HERE / "cost_filter.py")
native_root = Path(os.environ.get("GOAL584_NATIVE_SOURCE_ROOT", str(
    HERE.parents[1] / "local/goal584/cost-display/open-webui/backend/open_webui")))
native_ids = native_root / "utils/model_ids.py"
if not native_ids.exists():
    native_ids = Path("/app/backend/open_webui/utils/model_ids.py")
prefix_owner = load("native_model_ids_for_cost_test", native_ids) if native_ids.exists() else None
USER, OTHER, CHAT, ANSWER, CHILD_CHAT, CHILD_ANSWER, NEXT_ANSWER = (
    str(uuid5(NAMESPACE_URL, name)) for name in
    ("user", "other", "chat", "answer", "child-chat", "child-answer", "next-answer"))
SECRET = "synthetic-only-test-gateway-secret-" * 2
MODEL = "goal584-a"


def module(**values):
    result = ModuleType("native_owner_fixture")
    result.__dict__.update(values)
    return result


def native_functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError("Required native outlet boundary missing")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec",
                 flags=__import__("__future__").annotations.compiler_flag), namespace)


class CostFilterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if prefix_owner is None:
            self.skipTest("Exact native model-ID helper missing; actual-image proof remains required")
        self.user = SimpleNamespace(id=USER, role="user")
        self.actor = {"id": USER}
        self.model = {"id": MODEL, "owned_by": "openai"}
        self.metadata = {"user_id": USER, "chat_id": CHAT, "message_id": ANSWER,
                         "chat_context": {"messages": [], "params": {}}, "internal": False}
        self.request = SimpleNamespace(state=SimpleNamespace(internal=False),
            app=SimpleNamespace(state=SimpleNamespace(OPENAI_MODELS={MODEL: {"urlIdx": 0}})))
        self.messages = {(CHAT, ANSWER): {"id": ANSWER, "role": "assistant", "model": MODEL},
                         (CHAT, NEXT_ANSWER): {"id": NEXT_ANSWER, "role": "assistant", "model": MODEL},
                         (CHILD_CHAT, CHILD_ANSWER): {"id": CHILD_ANSWER, "role": "assistant", "model": MODEL}}
        self.chats = SimpleNamespace(get_accessible_chat_by_id=AsyncMock(return_value=SimpleNamespace(user_id=USER)),
            get_message_by_id_and_message_id=AsyncMock(side_effect=lambda chat, answer: self.messages.get((chat, answer))))
        self.models = SimpleNamespace(get_model_by_id=AsyncMock(return_value=SimpleNamespace(base_model_id=None)))
        self.connection = AsyncMock(return_value=("http://proxy:4000/v1", SECRET, {}))
        modules = {name: module() for name in ("open_webui", "open_webui.models", "open_webui.routers", "open_webui.utils")}
        modules.update({"open_webui.models.users": module(Users=SimpleNamespace(get_user_by_id=AsyncMock(return_value=self.user))),
            "open_webui.env": module(VERSION="0.12.2"),
            "open_webui.models.chats": module(Chats=self.chats),
            "open_webui.models.models": module(Models=self.models),
            "open_webui.routers.openai": module(get_openai_connection=self.connection),
            "open_webui.utils.model_ids": prefix_owner})
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.filter = extension.Filter()
        self.filter.valves.ledger_base_url = "http://proxy:4000"

    def body(self):
        return {"model": MODEL, "messages": [{"role": "system", "content": "Keep context"},
                {"role": "user", "content": "Hi"}], "tools": [{"type": "function", "function": {"name": "fixture"}}],
                "stream": True, "max_tokens": 5}

    async def sign(self, body=None):
        return await self.filter.request(self.body() if body is None else body,
            __user__=self.actor, __metadata__=self.metadata, __request__=self.request, __model__=self.model)

    def api_context(self):
        self.metadata.update(chat_id="", message_id=None)
        self.request.state.auth_type = "api_key"
        self.request.state.user = self.user
        self.request.state.metadata = self.metadata

    async def test_api_signs_shared_account_preserves_complete_input_and_never_displays_chat_cost(self):
        self.api_context()
        operations, nonces = [], []
        for streaming in (False, True):
            body = self.body()
            body.update(stream=streaming, temperature=0.2, tool_choice="auto")
            body["messages"] = [
                {"role": "system", "content": "Keep original system instruction"},
                {"role": "developer", "content": "Keep developer priority"},
                {"role": "user", "content": "Previous question"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "tool_prior", "type": "function", "function": {"name": "fixture", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "tool_prior", "content": '{"result":"actual prior output"}'},
                {"role": "user", "content": [{"type": "text", "text": "Use prior result"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,c3ludGhldGlj"}}]},
            ]
            body["metadata"] = {"chat_id": OTHER, "category": "service"}
            body["litellm_metadata"] = {"unrelated": "keep", "owui_budget_provenance": "forged",
                "spend_logs_metadata": {"owui_budget": {"user_id": OTHER}}}
            expected = copy.deepcopy(body)
            signed = await self.sign(body)
            token = signed["litellm_metadata"]["owui_budget_provenance"]
            expected["litellm_metadata"] = {"unrelated": "keep", "owui_budget_provenance": token}
            self.assertEqual(signed, expected)
            claims = protocol.decode_api_call(token, SECRET, user_id=USER, model=MODEL)
            operations.append(claims["operation_id"])
            nonces.append(claims["jti"])
            with self.assertRaises(protocol.ProtocolError):
                protocol.decode_call(token, SECRET, user_id=USER, model=MODEL)
            self.assertEqual(self.metadata["chat_id"], "")
            self.assertIsNone(self.metadata["message_id"])
            self.assertNotIn(extension.ROOT_CAPSULE, self.metadata["chat_context"])
            event = {"object": "chat.completion.chunk", "id": "provider-real-id"}
            self.assertIs(await self.filter.stream(event, __metadata__=self.metadata), event)
            emitter = AsyncMock()
            self.assertIs(await self.filter.outlet(signed, __user__=self.actor, __metadata__=self.metadata,
                __request__=self.request, __event_emitter__=emitter, __model__=self.model), signed)
            emitter.assert_not_called()
        self.assertEqual(operations[0], operations[1])
        self.assertNotEqual(nonces[0], nonces[1])
        self.chats.get_accessible_chat_by_id.assert_not_called()
        self.chats.get_message_by_id_and_message_id.assert_not_called()
        previous = operations[-1]
        self.request.state = SimpleNamespace(internal=False, auth_type="api_key", user=self.user, metadata=self.metadata)
        claims = protocol.decode_api_call((await self.sign())["litellm_metadata"]["owui_budget_provenance"],
            SECRET, user_id=USER, model=MODEL)
        self.assertNotEqual(previous, claims["operation_id"])

    async def test_api_signing_requires_native_auth_identity_metadata_and_no_partial_chat_or_task(self):
        self.api_context()
        native = self.request.state
        cases = [(native, "auth_type", "jwt"), (native, "user", SimpleNamespace(id=OTHER)),
            (native, "metadata", dict(self.metadata)), (native, "internal", True),
            (native, "direct", True), (native, extension.API_OPERATION, "not-a-uuid")]
        for target, name, value in cases:
            with self.subTest(field=name), patch.object(target, name, value, create=True):
                with self.assertRaises(ValueError):
                    await self.sign()
        for changes in ({"chat_id": CHAT}, {"message_id": ANSWER}, {"task": "sub_agent"},
                        {"internal": True}, {"assistant_message_id": ANSWER}, {"session_id": "session"}):
            with self.subTest(changes=changes), patch.dict(self.metadata, changes):
                with self.assertRaises(ValueError):
                    await self.sign()

    async def test_api_key_saved_chat_keeps_existing_owner_validation(self):
        self.request.state.auth_type = "api_key"
        self.request.state.user = self.user
        self.request.state.metadata = self.metadata
        self.chats.get_accessible_chat_by_id.return_value = None
        body = self.body()
        body["litellm_metadata"] = {"owui_budget_provenance": protocol.encode_api_call(
            SECRET, user_id=USER, operation_id=CHAT, model=MODEL), "category": "api"}
        with self.assertRaises(ValueError):
            await self.sign(body)
        self.chats.get_accessible_chat_by_id.assert_awaited_once()

    async def test_signed_actual_scope_replaces_caller_and_preserves_model_context(self):
        self.filter.valves.ledger_admin_key = "synthetic-management-not-forwarded"
        body = self.body()
        original = copy.deepcopy(body)
        body["metadata"] = {"chat_id": "caller-forgery"}
        body["litellm_metadata"] = {"owui_budget_provenance": "caller-token",
                                    "spend_logs_metadata": {"owui_budget": {"user_id": OTHER}}}
        signed = await self.sign(body)
        for field, value in original.items():
            self.assertEqual(signed[field], value)
        claims = protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"], SECRET, user_id=USER, model=MODEL)
        self.assertEqual((claims["chat_id"], claims["answer_id"], claims["root_chat_id"], claims["root_answer_id"]),
                         (CHAT, ANSWER, CHAT, ANSWER))
        self.assertNotIn("spend_logs_metadata", signed["litellm_metadata"])
        root = protocol.decode_root(self.metadata["chat_context"][extension.ROOT_CAPSULE], SECRET)
        self.assertEqual(root["root_answer_id"], ANSWER)
        self.assertEqual(self.metadata[extension.ISSUED_SCOPE]["call_id"], claims["jti"])
        self.assertEqual(self.metadata["chat_context"]["messages"], [])
        self.assertNotIn(self.filter.valves.ledger_admin_key, json.dumps(signed))
        self.assertNotIn(self.filter.valves.ledger_admin_key, json.dumps(self.metadata))

    async def test_display_disabled_does_not_disable_signing(self):
        self.actor["valves"] = self.filter.UserValves(enabled=False)
        signed = await self.sign()
        self.assertIn("owui_budget_provenance", signed["litellm_metadata"])
        emitter = AsyncMock()
        body = {"messages": [{"role": "assistant", "content": "unchanged"}]}
        self.assertIs(await self.filter.outlet(body, __user__=self.actor,
            __metadata__=self.metadata, __event_emitter__=emitter), body)
        emitter.assert_not_called()

    async def test_foreign_user_or_chat_rejected_before_signing(self):
        self.metadata["user_id"] = OTHER
        with self.assertRaises(ValueError):
            await self.sign()
        self.metadata["user_id"] = USER
        self.chats.get_accessible_chat_by_id.return_value = None
        with self.assertRaises(ValueError):
            await self.sign()

    async def test_existing_native_base_link_and_prefix_helper_define_wire_model(self):
        self.models.get_model_by_id.return_value = SimpleNamespace(base_model_id="gateway.goal584-a")
        self.request.app.state.OPENAI_MODELS = {"gateway.goal584-a": {"urlIdx": 2}}
        self.connection.return_value = ("http://proxy:4000/v1", SECRET, {"prefix_id": "gateway"})
        signed = await self.sign()
        self.connection.assert_awaited_once_with(2)
        protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"], SECRET, user_id=USER, model=MODEL)

    async def test_wrong_native_model_rejected_and_unmanaged_connection_passes_unchanged(self):
        self.model["id"] = "other"
        with self.assertRaises(ValueError):
            await self.sign()
        self.model["id"] = MODEL
        self.connection.return_value = ("https://external.invalid/v1", SECRET, {})
        body = self.body()
        before = copy.deepcopy(body)
        self.metadata[extension.ISSUED_SCOPE] = {"foreign": "stale"}
        self.assertIs(await self.sign(body), body)
        self.assertEqual(body, before)
        self.assertTrue(self.metadata[extension.SKIPPED_SCOPE])
        self.assertNotIn(extension.ISSUED_SCOPE, self.metadata)
        emitter = AsyncMock()
        event = {"object": "chat.completion.chunk", "id": "unmanaged-answer"}
        self.assertIs(await self.filter.stream(event, __metadata__=self.metadata), event)
        self.assertIs(await self.filter.outlet(body, __metadata__=self.metadata,
            __user__=self.actor, __event_emitter__=emitter), body)
        emitter.assert_not_called()

    async def test_global_scope_skips_native_nonopenai_and_pipe_routes_without_changing_context(self):
        for model in ({"id": MODEL, "owned_by": "ollama"},
                      {"id": MODEL, "owned_by": "openai", "pipe": {"id": "native-pipe"}}):
            self.model = model
            body = self.body()
            before = copy.deepcopy(body)
            with self.subTest(model=model):
                self.assertIs(await self.sign(body), body)
                self.assertEqual(body, before)
                self.assertTrue(self.metadata[extension.SKIPPED_SCOPE])
        self.connection.assert_not_awaited()
        self.chats.get_accessible_chat_by_id.assert_not_awaited()

    async def test_native_separate_chat_completed_outlet_reclassifies_foreign_without_status_or_history_changes(self):
        path = native_root / "utils/chat.py"
        if not path.exists():
            self.skipTest("Exact native chat_completed missing")
        self.request.app.state.MODELS = {MODEL: self.model}
        emitter = AsyncMock()
        seen = []
        async def dispatch(**kwargs):
            params = kwargs["extra_params"]
            seen.append(params)
            return await self.filter.outlet(kwargs["form_data"], __user__=params["__user__"],
                __metadata__=params["__metadata__"], __request__=params["__request__"],
                __event_emitter__=params["__event_emitter__"], __model__=params["__model__"]), {}
        native = {"Request": object, "Any": object, "UserModel": type("NativeUser", (), {}),
                  "get_all_models": AsyncMock(),
                  "process_pipeline_outlet_filter": AsyncMock(side_effect=lambda request, body, user, models: body),
                  "get_event_emitter": AsyncMock(return_value=emitter), "get_event_call": AsyncMock(),
                  "get_filter_functions": AsyncMock(return_value=[SimpleNamespace(id="employee_budget_cost")]),
                  "process_filter_functions": dispatch}
        native_functions(path, {"chat_completed"}, native)
        body = {"id": ANSWER, "chat_id": CHAT, "session_id": "native-session", "model": MODEL,
                "messages": [{"role": "assistant", "content": "Preserved native answer."}]}
        before = copy.deepcopy(body)
        for url, skipped in (("https://external.invalid/v1", True), ("http://proxy:4000/v1", False)):
            emitter.reset_mock()
            self.connection.return_value = (url, SECRET, {})
            result = await native["chat_completed"](self.request, body, self.user)
            self.assertIs(result, body)
            self.assertEqual(result, before)
            self.assertNotIn(extension.SKIPPED_SCOPE, seen[-1]["__metadata__"])
            self.assertNotIn(extension.ISSUED_SCOPE, seen[-1]["__metadata__"])
            self.assertIs(seen[-1]["__model__"], self.model)
            if skipped:
                emitter.assert_not_called()
            else:
                self.assertIn("ещё не подтверждена", emitter.call_args.args[0]["data"]["description"])

    async def test_global_scope_auxiliary_task_skip_requires_authoritative_server_metadata(self):
        self.metadata["task"] = "title_generation"
        body = self.body()
        before = copy.deepcopy(body)
        with self.assertRaisesRegex(ValueError, "unsupported_task_or_direct"):
            await self.sign(body)
        self.assertEqual(body, before)
        self.request.state.metadata = self.metadata
        self.assertIs(await self.sign(body), body)
        self.assertEqual(body, before)
        self.assertTrue(self.metadata[extension.SKIPPED_SCOPE])
        self.assertNotIn("litellm_metadata", body)

    async def test_global_scope_missing_managed_native_binding_and_invalid_managed_auth_fail_closed(self):
        self.request.app.state.OPENAI_MODELS = {}
        with self.assertRaisesRegex(ValueError, "native_connection"):
            await self.sign()
        self.request.app.state.OPENAI_MODELS = {MODEL: {"urlIdx": 0}}
        self.connection.return_value = ("http://proxy:4000/v1", SECRET, {"auth_type": "oauth"})
        with self.assertRaisesRegex(ValueError, "gateway_configuration"):
            await self.sign()
        self.assertNotIn(extension.SKIPPED_SCOPE, self.metadata)

    async def test_native_global_selection_covers_new_model_once_and_preserves_prepared_primary_and_worker_context(self):
        selector = native_root / "utils/filter.py"
        if not selector.exists():
            self.skipTest("Exact native global Filter selector missing")
        native = {}
        native_functions(selector, {"get_model_filter_ids"}, native)
        select = native["get_model_filter_ids"]
        active = [("employee_budget_cost", True)]
        self.assertEqual(select({"id": "new-model"}, active), ["employee_budget_cost"])
        self.assertEqual(select({"id": MODEL, "info": {"meta": {"filterIds": ["employee_budget_cost"]}}},
                                active), ["employee_budget_cost"])
        for delegated in (False, True):
            with self.subTest(delegated=delegated):
                if delegated:
                    body, _, _ = await self.community_worker(inherited_base="gpt-6.1-sol")
                else:
                    body = self.body()
                body["messages"] = [
                    {"role": "system", "content": "Native model preset: retain source citations."},
                    {"role": "user", "content": "Inspect the attached source."},
                    {"role": "assistant", "content": None, "tool_calls": [{"id": "read-source", "type": "function",
                        "function": {"name": "read_source", "arguments": '{"file_id":"fixture-source"}'}}]},
                    {"role": "tool", "tool_call_id": "read-source", "content": "Source paragraph: exact evidence."}]
                body["tools"] = [{"type": "function", "function": {"name": "read_source", "parameters": {
                    "type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]}}}]
                body["temperature"] = .2
                body["instructions"] = "Retain all prepared instructions."
                before = copy.deepcopy(body)
                context_before = copy.deepcopy(self.metadata["chat_context"])
                signed = await self.sign(body)
                self.assertEqual({k: v for k, v in signed.items() if k != "litellm_metadata"}, before)
                self.assertEqual({k: v for k, v in self.metadata["chat_context"].items() if k != extension.ROOT_CAPSULE},
                                 {k: v for k, v in context_before.items() if k != extension.ROOT_CAPSULE})
                self.assertNotIn(extension.SKIPPED_SCOPE, json.dumps(signed))
                claims = protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"], SECRET,
                    user_id=USER, model="gpt-6.1-terra" if delegated else MODEL)
                self.assertEqual((claims["root_chat_id"], claims["root_answer_id"]), (CHAT, ANSWER))

    async def test_internal_child_requires_server_flag_and_signed_root_capsule(self):
        capsule = protocol.encode_root(SECRET, user_id=USER, root_chat_id=CHAT, root_answer_id=ANSWER)
        self.metadata.update(chat_id=CHILD_CHAT, message_id=CHILD_ANSWER, internal=True)
        self.metadata["chat_context"][extension.ROOT_CAPSULE] = capsule
        with self.assertRaises(ValueError):
            await self.sign()
        self.request.state.internal = True
        signed = await self.sign()
        claims = protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"], SECRET, user_id=USER, model=MODEL)
        self.assertEqual((claims["chat_id"], claims["answer_id"]), (CHILD_CHAT, CHILD_ANSWER))
        self.assertEqual((claims["root_chat_id"], claims["root_answer_id"]), (CHAT, ANSWER))
        self.metadata["chat_context"][extension.ROOT_CAPSULE] = "imported-fake-root"
        # Reader tests also load the real module under its deployed alias.
        # Assert the class used by the Filter's native import, not an old load.
        with self.assertRaises(sys.modules["employee_budget_provenance"].ProtocolError):
            await self.sign()

    async def community_worker(self, *, parent="gpt-6.1-sol", parent_base=None, inherited_base=None):
        """Server-context fixture; the exact cached Tool has a separate source replay."""
        worker = "corporate-office-worker"
        self.metadata = {"user_id": USER, "chat_id": CHAT, "message_id": ANSWER,
                         "chat_context": {"messages": [], "params": {}}, "internal": False}
        self.request = SimpleNamespace(state=SimpleNamespace(internal=False),
            app=SimpleNamespace(state=SimpleNamespace(OPENAI_MODELS={
                "gpt-6.1-sol": {"urlIdx": 0}, "gpt-6.1-terra": {"urlIdx": 1}})))
        if inherited_base is not None:
            self.request.base_model_id = inherited_base
        self.models.get_model_by_id.side_effect = lambda model: (
            SimpleNamespace(base_model_id="gpt-6.1-terra") if model == worker
            else SimpleNamespace(base_model_id=parent_base) if parent_base else None)
        self.messages[(CHAT, ANSWER)] = {"id": ANSWER, "role": "assistant", "model": parent}
        self.model = {"id": parent, "owned_by": "openai"}
        self.connection.reset_mock()
        self.connection.side_effect = None
        self.connection.return_value = ("http://proxy:4000/v1", SECRET, {})
        parent_body = self.body();parent_body["model"] = parent
        await self.sign(parent_body)
        parent_request, parent_metadata = self.request, self.metadata
        self.metadata = copy.deepcopy(parent_metadata)
        self.metadata["task"] = "sub_agent"
        self.request = copy.copy(parent_request)
        self.request.state = copy.copy(parent_request.state)
        self.request.state.metadata = self.metadata
        self.model = {"id": worker, "owned_by": "openai"}
        body = self.body();body.update(model=worker, stream=False)
        return body, parent_request, parent_metadata

    async def test_community_worker_uses_native_model_default_and_keeps_parent_context(self):
        for parent, base, inherited in (("gpt-6.1-sol", None, None),
                ("corporate-documents", "gpt-6.1-terra", "gpt-6.1-terra"),
                ("corporate-documents", "gpt-6.1-sol", "gpt-6.1-sol")):
            with self.subTest(parent=parent, inherited=inherited):
                body, parent_request, parent_metadata = await self.community_worker(
                    parent=parent, parent_base=base, inherited_base=inherited)
                before, parent_before = copy.deepcopy(body), copy.deepcopy(parent_metadata)
                signed = await self.sign(body)
                self.assertEqual({k: v for k, v in signed.items() if k != "litellm_metadata"}, before)
                self.assertEqual(parent_metadata, parent_before)
                self.assertEqual(self.metadata["task"], "sub_agent")
                self.assertFalse(hasattr(self.request, "base_model_id"))
                self.assertEqual(getattr(parent_request, "base_model_id", None), inherited)
                claims = protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"], SECRET,
                                              user_id=USER, model="gpt-6.1-terra")
                self.assertEqual((claims["chat_id"], claims["answer_id"], claims["root_chat_id"], claims["root_answer_id"]),
                                 (CHAT, ANSWER, CHAT, ANSWER))
                self.assertNotEqual(claims["jti"], parent_metadata[extension.ISSUED_SCOPE]["call_id"])
                self.assertEqual(self.connection.await_args_list[-1].args, (1,))
                self.assertNotIn(extension.ROOT_STATE, json.dumps(signed))

    async def test_community_worker_each_real_request_gets_its_own_personal_nonce(self):
        body, _, _ = await self.community_worker(inherited_base="gpt-6.1-sol")
        first = await self.sign(copy.deepcopy(body))
        second = await self.sign(copy.deepcopy(body))
        scopes = [protocol.decode_call(value["litellm_metadata"]["owui_budget_provenance"], SECRET,
                                      user_id=USER, model="gpt-6.1-terra") for value in (first, second)]
        self.assertNotEqual(scopes[0]["jti"], scopes[1]["jti"])
        self.assertTrue(all(scope["root_answer_id"] == ANSWER for scope in scopes))
        self.assertTrue(all("payer_id" not in scope and "task" not in scope for scope in scopes))

    async def test_community_worker_rejects_spoofed_parent_before_route_or_token_change(self):
        for case in ("no_state", "state_mismatch", "forged_root", "foreign_user", "foreign_root", "expired_root",
                     "wrong_metadata_object", "foreign_answer_owner", "wrong_worker", "unknown_task", "direct"):
            with self.subTest(case=case):
                body, parent_request, _ = await self.community_worker(inherited_base="gpt-6.1-sol")
                if case == "no_state":delattr(self.request.state, extension.ROOT_STATE)
                elif case == "state_mismatch":setattr(self.request.state, extension.ROOT_STATE, "other")
                elif case in ("forged_root", "foreign_user", "foreign_root", "expired_root"):
                    token = "forged" if case == "forged_root" else protocol.encode_root(SECRET,
                        user_id=OTHER if case == "foreign_user" else USER,
                        root_chat_id=OTHER if case == "foreign_root" else CHAT, root_answer_id=ANSWER,
                        now=int(datetime.now(timezone.utc).timestamp()) - 86401 if case == "expired_root" else None)
                    self.metadata["chat_context"][extension.ROOT_CAPSULE] = token
                    setattr(self.request.state, extension.ROOT_STATE, token)
                elif case == "wrong_metadata_object":self.request.state.metadata = copy.deepcopy(self.metadata)
                elif case == "foreign_answer_owner":self.messages[(CHAT, ANSWER)]["user_id"] = OTHER
                elif case == "wrong_worker":self.model["id"] = "another-worker"
                elif case == "unknown_task":self.metadata["task"] = "sub_agent_other"
                elif case == "direct":self.request.state.direct = True
                with self.assertRaises(ValueError):await self.sign(body)
                self.assertEqual(self.request.base_model_id, "gpt-6.1-sol")
                self.assertEqual(parent_request.base_model_id, "gpt-6.1-sol")
                self.assertNotIn("litellm_metadata", body)

    async def test_community_worker_cannot_move_the_signed_parent_to_another_gateway(self):
        body, parent_request, _ = await self.community_worker(inherited_base="gpt-6.1-sol")
        self.connection.side_effect = lambda index: ("http://proxy:4000/v1",
            SECRET if index == 0 else "another-synthetic-gateway-key-" * 2, {})
        with self.assertRaises(ValueError):await self.sign(body)
        self.assertEqual(parent_request.base_model_id, "gpt-6.1-sol")
        self.assertNotIn("litellm_metadata", body)

    async def test_ordinary_request_still_requires_its_saved_answer_model(self):
        body, _, _ = await self.community_worker(inherited_base="gpt-6.1-sol")
        self.metadata["task"] = ""
        with self.assertRaisesRegex(ValueError, "answer_model"):await self.sign(body)
        self.assertEqual(self.request.base_model_id, "gpt-6.1-sol")

    async def test_every_workflow_displays_accrued_snapshot_with_pending_distinction(self):
        await self.sign()
        snapshot = SimpleNamespace(answer=SimpleNamespace(spend=Decimal("0.20")),
            chat=SimpleNamespace(spend=Decimal("0.60")), pending=False,
            as_of=datetime(2026, 11, 2, 13, 0, tzinfo=timezone.utc))
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        for name in (None, "delegate_task", "run_sub_agent", "run_parallel_sub_agents", "future_workflow_tool"):
            for pending in (False, True):
                with self.subTest(tool=name, pending=pending):
                    snapshot.pending = pending
                    message = {"id": ANSWER, "role": "assistant", "content": "Proof"}
                    if name:
                        message["output"] = [{"type": "function_call", "name": name}]
                    body = {"messages": [message]}
                    before, metadata = copy.deepcopy(body), copy.deepcopy(self.metadata)
                    emitter, reader = AsyncMock(), AsyncMock(return_value=snapshot)
                    with patch.object(real_reader, "read_cost_snapshot", reader), patch.dict(sys.modules,
                            {"open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=object()))}):
                        result = await self.filter.outlet(body, __user__=self.actor,
                            __metadata__=self.metadata, __event_emitter__=emitter)
                    expected = "Ответ: $0.20 · Чат: $0.60 · на 13:00:00 UTC · начислено на сейчас"
                    if pending:
                        expected += ", учёт обновляется"
                    self.assertEqual(emitter.call_args.args[0], {"type": "status", "data": {
                        "action": "employee_budget_cost", "description": expected, "done": True}})
                    self.assertIs(result, body)
                    self.assertEqual(body, before)
                    self.assertEqual(self.metadata, metadata)

    async def test_resumed_parent_owns_new_answer_and_ignores_inherited_capsule(self):
        self.metadata["message_id"] = NEXT_ANSWER
        self.metadata["chat_context"][extension.ROOT_CAPSULE] = protocol.encode_root(SECRET,
            user_id=USER, root_chat_id=CHAT, root_answer_id=ANSWER)
        signed = await self.sign()
        claims = protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"], SECRET, user_id=USER, model=MODEL)
        self.assertEqual(claims["root_answer_id"], NEXT_ANSWER)

    async def test_observed_physical_ids_are_request_local_and_do_not_modify_stream(self):
        await self.sign()
        event = {"id": "provider-one", "object": "chat.completion.chunk", "choices": []}
        before = copy.deepcopy(event)
        self.assertIs(await self.filter.stream(event, __metadata__=self.metadata), event)
        await self.filter.stream(event, __metadata__=self.metadata)
        self.assertEqual(event, before)
        self.assertEqual(self.metadata[extension.OBSERVED_IDS], ["provider-one"])
        isolated = {extension.ISSUED_SCOPE: {}}
        await self.filter.stream({"type": "response.created", "response": {"id": "response-two"}}, __metadata__=isolated)
        self.assertNotIn(extension.OBSERVED_IDS, isolated)
        self.assertNotIn(extension.OBSERVED_CALL_IDS, isolated)
        self.assertTrue(isolated[extension.UNBOUND_RESPONSE])
        self.assertEqual(self.metadata[extension.OBSERVED_IDS], ["provider-one"])

    async def test_responses_uses_own_jwt_nonce_and_accumulates_tool_round_with_cc_ids(self):
        self.connection.return_value = ("http://proxy:4000", SECRET, {"api_type": "responses"})
        first_body = self.body()
        first_body["max_tokens"] = 16
        signed = await self.sign(first_body)
        first = protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"], SECRET, user_id=USER, model=MODEL)["jti"]
        event = {"type": "response.created", "response": {"id": "resp_encrypted_first", "call_id": OTHER}, "call_id": OTHER}
        original = copy.deepcopy(event)
        await self.filter.stream(event, __metadata__=self.metadata)
        await self.filter.stream(event, __metadata__=self.metadata)
        self.assertEqual(event, original)
        self.assertEqual(self.metadata[extension.OBSERVED_CALL_IDS], [first])
        self.assertNotIn(extension.OBSERVED_IDS, self.metadata)
        body = self.body()
        body["max_tokens"] = 16
        body["messages"] += [{"role": "assistant", "tool_calls": [{"id": "call_fixture", "type": "function",
            "function": {"name": "fixture", "arguments": "{}"}}]}, {"role": "tool", "tool_call_id": "call_fixture", "content": "synthetic result"}]
        before = copy.deepcopy(body)
        signed = await self.sign(body)
        self.assertEqual({k: v for k, v in signed.items() if k != "litellm_metadata"}, before)
        second = protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"], SECRET, user_id=USER, model=MODEL)["jti"]
        self.assertNotEqual(first, second)
        await self.filter.stream({"type": "response.completed", "response": {"id": "resp_encrypted_second"}}, __metadata__=self.metadata)
        await self.filter.stream({"object": "chat.completion.chunk", "id": "cc-physical"}, __metadata__=self.metadata)
        self.assertEqual(self.metadata[extension.OBSERVED_CALL_IDS], [first, second])
        self.assertEqual(self.metadata[extension.OBSERVED_IDS], ["cc-physical"])
        self.assertNotIn(extension.UNBOUND_RESPONSE, self.metadata)
        snapshot = SimpleNamespace(answer=SimpleNamespace(spend=Decimal("0.40")), chat=SimpleNamespace(spend=Decimal("0.40")),
            pending=False, as_of=datetime(2026, 11, 2, tzinfo=timezone.utc))
        reader = AsyncMock(return_value=snapshot)
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        emitter = AsyncMock()
        with patch.object(real_reader, "read_cost_snapshot", reader), patch.dict(sys.modules,
                {"open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=object()))}):
            await self.filter.outlet({"messages": []}, __user__=self.actor, __metadata__=self.metadata, __event_emitter__=emitter)
        self.assertEqual(reader.call_args.kwargs["observed_call_ids"], [first, second])
        self.assertEqual(reader.call_args.kwargs["observed_request_ids"], ["cc-physical"])
        self.assertNotIn("учёт обновляется", emitter.call_args.args[0]["data"]["description"])

    async def test_unbound_responses_marker_is_safe_and_cannot_make_mixed_display_complete(self):
        await self.sign()
        for marker in (None, "forged", "", {}, 123):
            isolated = {extension.ISSUED_SCOPE: {"call_id": marker}}
            event = {"type": "response.completed", "response": {"id": "resp_opaque", "call_id": ANSWER}}
            self.assertIs(await self.filter.stream(event, __metadata__=isolated), event)
            self.assertTrue(isolated[extension.UNBOUND_RESPONSE])
            self.assertNotIn(extension.OBSERVED_CALL_IDS, isolated)
            self.assertNotIn(extension.OBSERVED_IDS, isolated)
        self.metadata[extension.OBSERVED_IDS] = ["settled-cc"]
        self.metadata[extension.ISSUED_SCOPE].pop("call_id")
        await self.filter.stream({"type": "response.created", "response": {"id": "resp_opaque"}}, __metadata__=self.metadata)
        snapshot = SimpleNamespace(answer=SimpleNamespace(spend=Decimal("0.20")), chat=SimpleNamespace(spend=Decimal("0.20")),
            pending=False, as_of=datetime(2026, 11, 2, tzinfo=timezone.utc))
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        emitter = AsyncMock()
        with patch.object(real_reader, "read_cost_snapshot", AsyncMock(return_value=snapshot)), patch.dict(sys.modules,
                {"open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=object()))}):
            await self.filter.outlet({"messages": []}, __user__=self.actor, __metadata__=self.metadata, __event_emitter__=emitter)
        self.assertIn("учёт обновляется", emitter.call_args.args[0]["data"]["description"])

    async def test_actual_native_detached_logging_id_differs_but_server_nonce_survives(self):
        cache = Path(os.environ.get("GOAL584_LITELLM_SOURCE_ROOT", str(HERE.parents[1] / "local/goal584/litellm/upstream")))
        if not (cache / ".git").exists():
            self.skipTest("Exact cached d665 Git source missing; native-image Responses proof remains required")
        def source(path):
            result = subprocess.run(["git", "-c", "gc.auto=0", "show", "d665dc1a6315847fcad6cc2c1264ceb47c06abce:" + path],
                cwd=cache, env=dict(os.environ, GIT_NO_LAZY_FETCH="1"), capture_output=True, timeout=10)
            if result.returncode:
                self.skipTest("Exact cached d665 method unavailable; no lazy fetch allowed")
            return ast.parse(result.stdout)
        # Pydantic shape adapters only; actual copy and advertised-ID rewrite
        # method bodies are executed unchanged from the pinned cached owner.
        class Response(extension.BaseModel):
            id: str
        class Event(extension.BaseModel):
            response: Response
        env = {"BaseModel": extension.BaseModel, "ResponsesAPIResponse": Response}
        for path, names in (("litellm/responses/streaming_iterator.py", {"_logging_copy", "_detached_shallow_copy"}),
                            ("litellm/proxy/hooks/responses_id_security.py", {"_rewrite_advertised_id"})):
            nodes = [node for node in source(path).body if isinstance(node, ast.FunctionDef) and node.name in names]
            self.assertEqual(len(nodes), len(names))
            exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec",
                         flags=__import__("__future__").annotations.compiler_flag), env)
        event = Event(response=Response(id="resp_sdk_model_encoded"))
        logged = env["_logging_copy"](event)
        env["_rewrite_advertised_id"](event, lambda _: "resp_security_opaque")
        self.assertIsNot(logged.response, event.response)
        self.assertNotEqual(logged.response.id, event.response.id)
        signed = await self.sign()
        nonce = protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"], SECRET, user_id=USER, model=MODEL)["jti"]
        await self.filter.stream({"type": "response.completed", **event.model_dump()}, __metadata__=self.metadata)
        self.assertEqual(self.metadata[extension.OBSERVED_CALL_IDS], [nonce])
        self.assertNotIn(extension.OBSERVED_IDS, self.metadata)

    async def test_native_valves_payload_is_json_serializable_and_visibility_default_on(self):
        self.assertFalse(self.filter.toggle)
        self.assertTrue(self.filter.UserValves().enabled)
        values = self.filter.Valves(ledger_read_key="synthetic-viewer-key",
                                   ledger_admin_key="synthetic-admin-key").model_dump(exclude_unset=True)
        self.assertEqual(json.loads(json.dumps(values)), values)
        self.assertEqual(set(self.filter.UserValves().model_dump()), {"enabled"})
        schema = self.filter.Valves.model_json_schema()["properties"]["ledger_admin_key"]
        self.assertTrue(schema["writeOnly"])
        self.assertEqual(schema["format"], "password")
        self.assertEqual(extension.money_text(Decimal("0.20")), "$0.20")
        self.assertEqual(extension.money_text(Decimal("0.000000001")), "<$0.00000001")

    async def test_outlet_emits_separate_snapshot_without_changing_model_history(self):
        await self.sign()
        self.metadata[extension.OBSERVED_IDS] = ["provider-one"]
        snapshot = SimpleNamespace(answer=SimpleNamespace(spend=Decimal("0.20")),
            chat=SimpleNamespace(spend=Decimal("0.60")), pending=False,
            as_of=datetime(2026, 11, 2, 13, 0, tzinfo=timezone.utc))
        reader = AsyncMock(return_value=snapshot)
        get_session = AsyncMock(return_value=object())
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        body = {"messages": [{"id": ANSWER, "role": "assistant", "content": "Proof"}]}
        original = copy.deepcopy(body)
        emitter = AsyncMock()
        with patch.object(real_reader, "read_cost_snapshot", reader), patch.dict(sys.modules,
                {"open_webui.utils.session_pool": module(get_session=get_session)}):
            result = await self.filter.outlet(body, __user__=self.actor,
                __metadata__=self.metadata, __event_emitter__=emitter)
        self.assertIs(result, body)
        self.assertEqual(result, original)
        event = emitter.call_args.args[0]
        self.assertEqual(event["type"], "status")
        self.assertEqual(event["data"]["description"],
                         "Ответ: $0.20 · Чат: $0.60 · на 13:00:00 UTC · начислено на сейчас")
        self.assertEqual(reader.call_args.args, (get_session.return_value,))
        self.assertEqual(reader.call_args.kwargs, {
            "base_url": self.filter.valves.ledger_base_url,
            "read_key": self.filter.valves.ledger_read_key,
            "user_id": USER, "root_chat_id": CHAT, "root_answer_id": ANSWER,
            "observed_request_ids": ["provider-one"], "observed_call_ids": [],
            "wait_seconds": self.filter.valves.read_wait_seconds})

    async def test_display_scope_mismatch_does_not_query_foreign_costs(self):
        await self.sign()
        self.metadata[extension.ISSUED_SCOPE]["user_id"] = OTHER
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        reader = AsyncMock()
        emitter = AsyncMock()
        body = {"messages": [{"id": ANSWER, "role": "assistant", "content": "Proof"}]}
        with patch.object(real_reader, "read_cost_snapshot", reader), patch.dict(sys.modules,
                {"open_webui.utils.session_pool": module(get_session=AsyncMock())}):
            self.assertIs(await self.filter.outlet(body, __user__=self.actor,
                __metadata__=self.metadata, __event_emitter__=emitter), body)
        reader.assert_not_called()
        self.assertNotIn("$", emitter.call_args.args[0]["data"]["description"])

    async def nonstream_scope(self):
        body = self.body()
        body["stream"] = False
        signed = await self.sign(body)
        nonce = protocol.decode_call(signed["litellm_metadata"]["owui_budget_provenance"],
            SECRET, user_id=USER, model=MODEL)["jti"]
        self.assertNotIn(extension.OBSERVED_CALL_IDS, self.metadata)
        return nonce, {"model": MODEL, "id": ANSWER, "chat_id": CHAT,
                       "messages": [{"id": ANSWER, "role": "assistant", "content": "Proof"}]}

    async def native_nonstream(self, response, emitter):
        # Execute the exact native success/error handler AND its real outlet
        # projection. Only persistence, filter discovery/dispatch and events are
        # leaves; the handler must save done before the Filter re-reads it.
        if not (native_root / "utils/middleware.py").exists():
            self.skipTest("Exact native middleware missing; actual-image proof remains required")
        self.request.app.state.MODELS = {MODEL: self.model}
        self.user.model_dump = lambda: self.actor.copy()
        async def persist(chat, answer, values):
            self.messages[(chat, answer)].update(copy.deepcopy(values))
        self.chats.upsert_message_to_chat_by_id_and_message_id = AsyncMock(side_effect=persist)
        self.chats.get_messages_map_by_chat_id = AsyncMock(side_effect=lambda chat:
            {answer: copy.deepcopy(value) for (owner, answer), value in self.messages.items() if owner == chat})
        self.chats.get_chat_title_by_id = AsyncMock(return_value="Fixture")
        async def dispatch(**kwargs):
            projected = kwargs["form_data"]
            self.assertNotIn("done", projected["messages"][-1])
            self.assertNotIn("error", projected["messages"][-1])
            return await self.filter.outlet(projected, __user__=self.actor, __metadata__=self.metadata,
                __request__=self.request, __event_emitter__=emitter), {}
        native = {"copy": copy, "Chats": self.chats, "log": extension.log,
            "JSONResponse": type("UnusedJSONResponse", (), {}), "JSONCodec": json,
            "UserModel": SimpleNamespace, "ENABLE_FUNCTIONS": True,
            "get_filter_functions": AsyncMock(return_value=[object()]),
            "get_sorted_filters": lambda *args: [], "process_filter_functions": AsyncMock(side_effect=dispatch),
            "process_pipeline_outlet_filter": AsyncMock(side_effect=lambda request, body, user, models: body),
            "normalize_usage": lambda value: {}, "output_id": lambda prefix: "native-output",
            "publish_chat_finished_event": AsyncMock(), "publish_chat_failed_event": AsyncMock(),
            "background_tasks_handler": AsyncMock(), "ENABLE_API_OUTLET_FILTERS": True}
        chat_ids = load("native_chat_ids_for_cost_test", native_root / "utils/chat_id.py")
        native["is_saved_chat_id"] = chat_ids.is_saved_chat_id
        native_functions(native_root / "utils/misc.py", {"get_message_list", "get_output_text", "get_reasoning_details"}, native)
        native_functions(native_root / "utils/middleware.py", {
            "get_response_data", "build_response_object", "merge_events_into_response",
            "outlet_filter_handler", "non_streaming_chat_response_handler"}, native)
        ctx = {"request": self.request, "user": self.user, "model": self.model, "metadata": self.metadata,
               "events": [], "event_emitter": emitter, "event_caller": None}
        result = await native["non_streaming_chat_response_handler"](response, ctx)
        native["publish_chat_failed_event"].assert_not_awaited()
        return result, native

    async def test_native_nonstream_saved_success_waits_for_its_nonce_and_preserves_answer(self):
        nonce, _ = await self.nonstream_scope()
        self.messages[(CHAT, ANSWER)]["done"] = False
        self.filter.valves.ledger_read_key = "synthetic-viewer-key"
        self.filter.valves.read_wait_seconds = 0.5
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        settled = real_reader._Row("native-spend-row", nonce, ANSWER, MODEL, Decimal("0.20"), 2, 1, 3)
        rows = AsyncMock(side_effect=[[], [settled]])
        reader = AsyncMock(wraps=real_reader.read_cost_snapshot)
        emitter = AsyncMock()
        response = {"choices": [{"message": {"role": "assistant", "content": "Proof"}, "finish_reason": "stop"}]}
        original, metadata = copy.deepcopy(response), copy.deepcopy(self.metadata)
        with patch.object(real_reader, "_rows", rows), patch.object(real_reader, "read_cost_snapshot", reader), \
                patch.dict(sys.modules, {"open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=object()))}):
            result, native = await self.native_nonstream(response, emitter)
        self.assertEqual(result, original)
        self.assertEqual(self.metadata, metadata)
        self.assertTrue(self.messages[(CHAT, ANSWER)]["done"])
        self.assertEqual(self.messages[(CHAT, ANSWER)]["model"], MODEL)
        self.assertEqual(rows.await_count, 2)
        self.assertEqual(reader.call_args.kwargs["observed_call_ids"], [nonce])
        self.assertEqual(reader.call_args.kwargs["observed_request_ids"], [])
        self.assertEqual(reader.call_args.kwargs["wait_seconds"], 0.5)
        descriptions = [call.args[0]["data"]["description"] for call in emitter.call_args_list
                        if call.args[0]["type"] == "status"]
        self.assertEqual(len(descriptions), 1)
        self.assertIn("Ответ: $0.20 · Чат: $0.20", descriptions[0])
        self.assertNotIn("учёт обновляется", descriptions[0])
        native["publish_chat_failed_event"].assert_not_awaited()
        self.chats.get_accessible_chat_by_id.assert_awaited_with(CHAT, self.user, permission="write")

    async def test_native_nonstream_provider_error_finishes_without_success_outlet(self):
        await self.nonstream_scope()
        self.messages[(CHAT, ANSWER)]["done"] = False
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        reader = AsyncMock()
        emitter = AsyncMock()
        with patch.object(real_reader, "read_cost_snapshot", reader):
            result, native = await self.native_nonstream({"error": {"detail": "Fixture error"}}, emitter)
        self.assertEqual(result, {"error": {"detail": "Fixture error"}})
        self.assertTrue(self.messages[(CHAT, ANSWER)]["done"])
        self.assertEqual(self.messages[(CHAT, ANSWER)]["error"], {"content": "Fixture error"})
        native["process_filter_functions"].assert_not_awaited()
        reader.assert_not_awaited()
        self.assertNotIn(extension.OBSERVED_CALL_IDS, self.metadata)

    async def test_native_nonstream_delayed_unavailable_row_emits_warning_after_wait(self):
        await self.nonstream_scope()
        self.messages[(CHAT, ANSWER)]["done"] = False
        self.filter.valves.ledger_read_key = "synthetic-viewer-key"
        self.filter.valves.read_wait_seconds = 0.5
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        rows = AsyncMock(side_effect=[[], real_reader.CostReadError("accounting_unavailable")])
        emitter = AsyncMock()
        response = {"choices": [{"message": {"role": "assistant", "content": "Proof"}}]}
        original, metadata = copy.deepcopy(response), copy.deepcopy(self.metadata)
        with patch.object(real_reader, "_rows", rows), patch.dict(sys.modules,
                {"open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=object()))}):
            result, _ = await self.native_nonstream(response, emitter)
        self.assertEqual(result, original)
        self.assertEqual(self.metadata, metadata)
        self.assertTrue(self.messages[(CHAT, ANSWER)]["done"])
        self.assertEqual(rows.await_count, 2)
        statuses = [call.args[0] for call in emitter.call_args_list if call.args[0]["type"] == "status"]
        self.assertEqual(statuses, [{"type": "status", "data": {"action": "employee_budget_cost",
            "description": "Расход неизвестен. Обратитесь к администратору.", "done": True}}])

    async def test_nonstream_unverified_native_completion_never_adds_nonce_or_reads_cost(self):
        await self.nonstream_scope()
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        baseline = copy.deepcopy(self.metadata)
        saved = {"id": ANSWER, "role": "assistant", "model": MODEL, "done": True}
        for case in ("not_done", "missing_done", "nonboolean_done", "error", "empty_error", "foreign_owner", "foreign_chat_owner", "wrong_role", "wrong_model",
                     "wrong_answer", "denied_acl", "lookup_failed", "inactive_user", "wrong_native_user",
                     "metadata_user", "scope_user", "scope_chat", "scope_answer", "scope_model",
                     "body_model", "body_answer", "body_chat", "bad_nonce", "no_request"):
            with self.subTest(case=case):
                self.metadata = copy.deepcopy(baseline)
                self.messages[(CHAT, ANSWER)] = copy.deepcopy(saved)
                body = {"model": MODEL, "id": ANSWER, "chat_id": CHAT,
                        "messages": [{"id": ANSWER, "role": "assistant", "content": "Proof", "done": True}]}
                self.user.id, self.user.role = USER, "user"
                self.chats.get_accessible_chat_by_id.return_value = SimpleNamespace(user_id=USER)
                self.chats.get_accessible_chat_by_id.side_effect = None
                request = self.request
                if case == "not_done": self.messages[(CHAT, ANSWER)]["done"] = False
                elif case == "missing_done": self.messages[(CHAT, ANSWER)].pop("done")
                elif case == "nonboolean_done": self.messages[(CHAT, ANSWER)]["done"] = 1
                elif case in ("error", "empty_error"): self.messages[(CHAT, ANSWER)]["error"] = {"content": "failed"} if case == "error" else {}
                elif case == "foreign_owner": self.messages[(CHAT, ANSWER)]["user_id"] = OTHER
                elif case == "foreign_chat_owner": self.chats.get_accessible_chat_by_id.return_value = SimpleNamespace(user_id=OTHER)
                elif case == "wrong_role": self.messages[(CHAT, ANSWER)]["role"] = "user"
                elif case == "wrong_model": self.messages[(CHAT, ANSWER)]["model"] = "foreign-model"
                elif case == "wrong_answer": self.messages[(CHAT, ANSWER)]["id"] = NEXT_ANSWER
                elif case == "denied_acl": self.chats.get_accessible_chat_by_id.return_value = None
                elif case == "lookup_failed": self.chats.get_accessible_chat_by_id.side_effect = RuntimeError("private DB details")
                elif case == "inactive_user": self.user.role = "pending"
                elif case == "wrong_native_user": self.user.id = OTHER
                elif case == "metadata_user": self.metadata["user_id"] = OTHER
                elif case.startswith("scope_"):
                    key = {"scope_user": "user_id", "scope_chat": "root_chat_id", "scope_answer": "root_answer_id", "scope_model": "model"}[case]
                    self.metadata[extension.ISSUED_SCOPE][key] = OTHER
                elif case.startswith("body_"): body[{"body_model": "model", "body_answer": "id", "body_chat": "chat_id"}[case]] = OTHER
                elif case == "bad_nonce": self.metadata[extension.ISSUED_SCOPE]["call_id"] = "not-a-canonical-nonce"
                elif case == "no_request": request = None
                before, metadata = copy.deepcopy(body), copy.deepcopy(self.metadata)
                emitter, reader = AsyncMock(), AsyncMock()
                with patch.object(real_reader, "read_cost_snapshot", reader), patch.dict(sys.modules,
                        {"open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=object()))}):
                    result = await self.filter.outlet(body, __user__=self.actor, __metadata__=self.metadata,
                        __request__=request, __event_emitter__=emitter)
                self.assertIs(result, body)
                self.assertEqual(body, before)
                self.assertEqual(self.metadata, metadata)
                reader.assert_not_awaited()
                description = emitter.call_args.args[0]["data"]["description"]
                self.assertNotIn("$", description)
                self.assertNotIn("private", description)

    async def test_nonstream_unknown_cost_warning_and_off_remain_optional(self):
        nonce, body = await self.nonstream_scope()
        self.messages[(CHAT, ANSWER)]["done"] = True
        metadata, before = copy.deepcopy(self.metadata), copy.deepcopy(body)
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        reader = AsyncMock(side_effect=real_reader.CostReadError("accounting_unavailable"))
        emitter = AsyncMock()
        with patch.object(real_reader, "read_cost_snapshot", reader), patch.dict(sys.modules,
                {"open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=object()))}):
            result = await self.filter.outlet(body, __user__=self.actor, __metadata__=self.metadata,
                __request__=self.request, __event_emitter__=emitter)
        self.assertIs(result, body)
        self.assertEqual(reader.call_args.kwargs["observed_call_ids"], [nonce])
        self.assertEqual(emitter.call_args.args[0]["data"]["description"], "Расход неизвестен. Обратитесь к администратору.")
        self.actor["valves"] = self.filter.UserValves(enabled=False)
        self.chats.get_accessible_chat_by_id.reset_mock()
        reader.reset_mock(); emitter.reset_mock()
        with patch.object(real_reader, "read_cost_snapshot", reader):
            self.assertIs(await self.filter.outlet(body, __user__=self.actor, __metadata__=self.metadata,
                __request__=self.request, __event_emitter__=emitter), body)
        reader.assert_not_awaited()
        emitter.assert_not_awaited()
        self.chats.get_accessible_chat_by_id.assert_not_awaited()
        self.assertEqual(body, before)
        self.assertEqual(self.metadata, metadata)

    async def test_native_money_and_accounting_failure_preserve_history_without_fake_zero(self):
        await self.sign()
        real_reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
        body = {"messages": [{"id": ANSWER, "role": "assistant", "content": "Proof",
                              "output": [{"type": "function_call_output", "output": "unchanged tool result"}]}]}
        original, metadata = copy.deepcopy(body), copy.deepcopy(self.metadata)
        self.filter.valves.ledger_read_key = "synthetic-viewer-key"
        self.filter.valves.read_wait_seconds = 0
        call_id = self.metadata[extension.ISSUED_SCOPE]["call_id"]
        native_row = real_reader._row({"request_id": "native-cost-row", "user": USER, "session_id": CHAT,
            "status": "success", "spend": ".20", "prompt_tokens": None, "completion_tokens": 0, "total_tokens": None,
            "metadata": {"spend_logs_metadata": {"owui_budget": {"schema": 1, "user_id": USER,
                "chat_id": CHAT, "answer_id": ANSWER, "root_chat_id": CHAT, "root_answer_id": ANSWER,
                "call_id": call_id, "model": MODEL, "category": "personal"}},
                "guardrail_information": [{"guardrail_name": "owui_budget_usage", "guardrail_action": "block",
                    "violation_categories": ["usage_unavailable"]}]}}, USER, CHAT)
        for rows in ([native_row], []):
            emitter = AsyncMock()
            with patch.object(real_reader, "_rows", AsyncMock(return_value=rows)), patch.dict(sys.modules,
                    {"open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=object()))}):
                result = await self.filter.outlet(body, __user__=self.actor,
                    __metadata__=self.metadata, __event_emitter__=emitter)
            self.assertIs(result, body)
            self.assertEqual(body, original)
            self.assertEqual(self.metadata, metadata)
            description = emitter.call_args.args[0]["data"]["description"]
            if rows:
                self.assertIn("Ответ: $0.20 · Чат: $0.20", description)
            else:
                self.assertNotIn("$", description)
        for code in ("accounting_unavailable", "spend_api_unavailable"):
            reader = AsyncMock(side_effect=real_reader.CostReadError(code))
            emitter = AsyncMock()
            with patch.object(real_reader, "read_cost_snapshot", reader), patch.dict(sys.modules,
                    {"open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=object()))}):
                result = await self.filter.outlet(body, __user__=self.actor,
                    __metadata__=self.metadata, __event_emitter__=emitter)
            self.assertIs(result, body)
            self.assertEqual(body, original)
            self.assertEqual(self.metadata, metadata)
            event = emitter.call_args.args[0]
            expected = ("Стоимость ещё не подтверждена журналом учёта. Учёт и лимиты действуют."
                        if code == "spend_api_unavailable" else "Расход неизвестен. Обратитесь к администратору.")
            self.assertEqual(event, {"type": "status", "data": {
                "action": "employee_budget_cost", "description": expected, "done": True}})
            self.assertNotIn("$", event["data"]["description"])
            self.assertNotIn("блок", event["data"]["description"].lower())
        self.actor["valves"] = self.filter.UserValves(enabled=False)
        emitter = AsyncMock()
        reader = AsyncMock(side_effect=real_reader.CostReadError("accounting_unavailable"))
        with patch.object(real_reader, "read_cost_snapshot", reader):
            self.assertIs(await self.filter.outlet(body, __user__=self.actor,
                __metadata__=self.metadata, __event_emitter__=emitter), body)
        reader.assert_not_called()
        emitter.assert_not_called()
        self.assertFalse(self.actor["valves"].enabled)
        self.assertEqual(body, original)
        self.assertEqual(self.metadata, metadata)


if __name__ == "__main__":
    unittest.main()
