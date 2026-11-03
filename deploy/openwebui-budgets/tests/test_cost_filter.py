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

    async def test_wrong_native_model_or_unmanaged_connection_rejected(self):
        self.model["id"] = "other"
        with self.assertRaises(ValueError):
            await self.sign()
        self.model["id"] = MODEL
        self.connection.return_value = ("https://external.invalid/v1", SECRET, {})
        with self.assertRaises(ValueError):
            await self.sign()

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
        self.assertEqual(event["data"]["description"], "Ответ: $0.20 · Чат: $0.60 · на 13:00:00 UTC")
        self.assertEqual(reader.call_args.kwargs["user_id"], USER)
        self.assertEqual(reader.call_args.kwargs["root_answer_id"], ANSWER)
        self.assertEqual(reader.call_args.kwargs["observed_request_ids"], ["provider-one"])
        self.assertEqual(reader.call_args.kwargs["observed_call_ids"], [])

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


if __name__ == "__main__":
    unittest.main()
