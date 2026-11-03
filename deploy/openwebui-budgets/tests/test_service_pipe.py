"""Real Pipe, binding helper and provenance; native external owners are doubled."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import NAMESPACE_URL, uuid5


HERE = Path(__file__).parents[1]


def load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


protocol = load("employee_budget_provenance", HERE / "provenance.py")
load("employee_budget_webui_model_binding", HERE / "webui_model_binding.py")
extension = load("service_pipe_under_test", HERE / "service_pipe.py")
native_ids = HERE.parents[1] / "local/goal584/cost-display/open-webui/backend/open_webui/utils/model_ids.py"
if not native_ids.exists():
    native_ids = Path("/app/backend/open_webui/utils/model_ids.py")
prefix_owner = load("native_model_ids_for_service_test", native_ids) if native_ids.exists() else None
USER, OTHER, CHAT, PAYER = (str(uuid5(NAMESPACE_URL, name)) for name in
                           ("service-actor", "service-other", "service-chat", "service-payer"))
TARGET = "native-title-model"
WIRE = "title-wire-model"
URL = "http://native-proxy.invalid"
SECRET = "synthetic-service-gateway-secret-" * 2
PRIVATE = "synthetic-private-native-error-content"


def module(**values):
    result = ModuleType("native_service_owner_fixture")
    result.__dict__.update(values)
    return result


class ServicePipeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if prefix_owner is None:
            self.skipTest("Exact native model-ID owner missing; native-image proof still required")
        self.user = SimpleNamespace(id=USER, role="user", name="Verified native actor")
        self.other_user = SimpleNamespace(id=OTHER, role="user", name="Other native employee")
        self.actor = {"id": USER, "role": "admin", "name": "untrusted caller snapshot"}
        self.chat = SimpleNamespace(id=CHAT, user_id=USER)
        self.users = SimpleNamespace(get_user_by_id=AsyncMock(side_effect=lambda user_id:
            {USER: self.user, OTHER: self.other_user}.get(user_id)))
        self.chats = SimpleNamespace(get_accessible_chat_by_id=AsyncMock(side_effect=lambda *_args, **_kw: self.chat))
        self.own_config = {"target_model_id": TARGET}
        self.common_config = {"ledger_base_url": URL, "service_payer_id": PAYER,
                              "ledger_admin_key": PRIVATE, "ledger_read_key": PRIVATE}
        async def read_config(function_id):
            self.assertIn(function_id, (extension.FUNCTION_ID, "employee_budget_cost"))
            return copy.deepcopy(self.own_config if function_id == extension.FUNCTION_ID else self.common_config)
        self.functions = SimpleNamespace(get_function_valves_by_id=AsyncMock(side_effect=read_config))
        self.model = {"id": TARGET, "owned_by": "openai", "name": "Native title model"}
        self.record = SimpleNamespace(id=TARGET, base_model_id="gateway." + WIRE)
        self.models = SimpleNamespace(get_model_by_id=AsyncMock(side_effect=lambda _: self.record))
        self.access = AsyncMock()
        self.connection = AsyncMock(return_value=(URL + "/v1", SECRET, {"prefix_id": "gateway"}))
        self.response = {"choices": [{"message": {"role": "assistant", "content": '{"title":"Synthetic title"}'}}]}
        self.dispatch = AsyncMock(return_value=self.response)
        self.request = SimpleNamespace(scope={"method": "POST", "path": extension.TITLE_PATH},
            state=SimpleNamespace(direct=False, internal=False),
            app=SimpleNamespace(state=SimpleNamespace(MODELS={TARGET: self.model},
                OPENAI_MODELS={"gateway." + WIRE: {"urlIdx": 2}})))
        self.task_body = {"model": "original-native-workspace-model", "chat_id": CHAT,
                          "messages": [{"role": "user", "content": "Native saved conversation"}]}
        self.metadata = {"task": extension.TASK, "task_body": self.task_body, "chat_id": CHAT,
                         "native_extra": {"preserve": ["full", "task", "context"]}}
        # This represents the already prepared native task payload. Native
        # functions.py removes metadata before passing the remaining body to Pipe.
        self.body = {"model": extension.FUNCTION_ID, "stream": False,
                     "messages": [{"role": "system", "content": "Native task-model system instruction"},
                                  {"role": "user", "content": "Generate a title from the supplied native conversation."}],
                     "tools": [{"type": "function", "function": {"name": "native_schema_fixture",
                        "parameters": {"type": "object", "properties": {"value": {"type": "string"}},
                                       "required": ["value"], "additionalProperties": False}}}],
                     "tool_choice": "none", "temperature": .2, "max_tokens": 1000,
                     "response_format": {"type": "json_schema", "json_schema": {"name": "title",
                        "strict": True, "schema": {"type": "object", "properties": {"title": {"type": "string"}},
                                                   "required": ["title"], "additionalProperties": False}}},
                     "litellm_metadata": {"native_unrelated": "keep", "owui_budget_provenance": "caller-forged-token"}}
        modules = {name: module() for name in ("open_webui", "open_webui.models", "open_webui.utils", "open_webui.routers")}
        modules.update({"open_webui.env": module(VERSION="0.12.2"),
            "open_webui.models.users": module(Users=self.users),
            "open_webui.models.chats": module(Chats=self.chats),
            "open_webui.models.functions": module(Functions=self.functions),
            "open_webui.models.models": module(Models=self.models),
            "open_webui.routers.openai": module(get_openai_connection=self.connection),
            "open_webui.utils.models": module(check_model_access=self.access),
            "open_webui.utils.model_ids": prefix_owner,
            "open_webui.utils.chat": module(generate_chat_completion=self.dispatch)})
        self.modules = modules
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.pipe = extension.Pipe()
        self.pipe.valves.target_model_id = TARGET

    async def invoke(self, **overrides):
        inputs = {"body": self.body, "__user__": self.actor, "__metadata__": self.metadata,
                  "__request__": self.request, "__task__": extension.TASK, "__task_body__": self.task_body}
        inputs.update(overrides)
        return await self.pipe.pipe(**inputs)

    async def test_prepared_task_context_restored_verbatim_and_only_target_and_signed_capsule_change(self):
        source = copy.deepcopy({**self.body, "metadata": self.metadata})
        original_body, original_metadata = copy.deepcopy(self.body), copy.deepcopy(self.metadata)
        result = await self.invoke()
        self.assertIs(result, self.response)
        self.dispatch.assert_awaited_once()
        self.assertIs(self.dispatch.await_args.args[0], self.request)
        self.assertIs(self.dispatch.await_args.kwargs["user"], self.user)
        delegated = self.dispatch.await_args.args[1]
        token = delegated["litellm_metadata"]["owui_budget_provenance"]
        expected = copy.deepcopy(source)
        expected["model"] = TARGET
        expected["litellm_metadata"]["owui_budget_provenance"] = token
        self.assertEqual(delegated, expected)
        self.assertEqual(self.body, original_body)
        self.assertEqual(self.metadata, original_metadata)
        self.assertIsNot(delegated["messages"], self.body["messages"])
        claims = protocol.decode_service_call(token, SECRET, user_id=USER, model=WIRE, task=extension.TASK)
        self.assertEqual((claims["sub"], claims["payer_id"], claims["chat_id"]), (USER, PAYER, CHAT))
        self.assertTrue(set(claims).isdisjoint({"answer_id", "root_answer_id", "root_chat_id"}))
        self.assertNotIn(SECRET, json.dumps(delegated))
        self.assertNotIn(PRIVATE, json.dumps(delegated))
        self.access.assert_has_awaits([unittest.mock.call(self.user, self.model)] * 2)
        self.connection.assert_has_awaits([unittest.mock.call(2)] * 2)
        self.chats.get_accessible_chat_by_id.assert_awaited_with(CHAT, self.user, permission="write")

    async def test_native_configuration_is_fresh_owner_and_cached_empty_target_is_not_a_default(self):
        self.pipe.valves.target_model_id = ""
        await self.invoke()
        self.assertEqual(self.dispatch.await_args.args[1]["model"], TARGET)
        self.assertEqual(set(self.pipe.Valves.model_fields), {"target_model_id"})
        self.assertGreaterEqual(self.functions.get_function_valves_by_id.await_count, 6)

    async def test_only_actual_native_direct_title_route_and_nonstream_task_are_accepted(self):
        for path, method, task in [("/api/chat/completions", "POST", extension.TASK),
                                   ("/openai/chat/completions", "POST", extension.TASK),
                                   (extension.TITLE_PATH, "GET", extension.TASK),
                                   (extension.TITLE_PATH, "POST", "tags_generation"),
                                   (extension.TITLE_PATH, "POST", None)]:
            self.request.scope = {"path": path, "method": method}
            with self.subTest(path=path, method=method, task=task), self.assertRaises(extension.ServiceTaskError):
                await self.invoke(__task__=task)
        self.request.scope = {"path": extension.TITLE_PATH, "method": "POST"}
        self.body["stream"] = True
        with self.assertRaises(extension.ServiceTaskError):
            await self.invoke()
        self.dispatch.assert_not_awaited()
        self.functions.get_function_valves_by_id.assert_not_awaited()

    async def test_conflicting_or_missing_task_chat_metadata_and_body_model_are_rejected_before_native_reads(self):
        for change in [{"task": "tags_generation"}, {"chat_id": OTHER}, {"user_id": OTHER},
                       {"task_body": {}}, {"direct": True}, {"internal": True}]:
            metadata = {**self.metadata, **change}
            with self.subTest(change=change), self.assertRaises(extension.ServiceTaskError):
                await self.invoke(__metadata__=metadata)
        for task_body in [None, {}, {**self.task_body, "chat_id": "not-a-uuid"}]:
            with self.assertRaises(extension.ServiceTaskError):
                await self.invoke(__task_body__=task_body)
        for change in [{"model": TARGET}, {"metadata": {"task": "forged"}}]:
            with self.assertRaises(extension.ServiceTaskError):
                await self.invoke(body={**self.body, **change})
        self.dispatch.assert_not_awaited()
        self.users.get_user_by_id.assert_not_awaited()

    async def test_current_actor_and_native_own_chat_acl_are_required(self):
        for user, chat in [(None, self.chat), (SimpleNamespace(id=OTHER, role="user"), self.chat),
                           (SimpleNamespace(id=USER, role="pending"), self.chat), (self.user, None),
                           (self.user, SimpleNamespace(id=CHAT, user_id=OTHER)),
                           (self.user, SimpleNamespace(id=OTHER, user_id=USER))]:
            self.users.get_user_by_id.side_effect = lambda user_id: user if user_id == USER else None
            self.chats.get_accessible_chat_by_id.side_effect = lambda *_args, **_kw: chat
            with self.subTest(user_present=user is not None, chat_present=chat is not None), self.assertRaises(extension.ServiceTaskError):
                await self.invoke()
        self.dispatch.assert_not_awaited()

    async def test_direct_internal_override_and_version_drift_are_rejected(self):
        for name in ["direct", "internal", "bypass_filter", "bypass_system_prompt"]:
            setattr(self.request.state, name, True)
            with self.subTest(flag=name), self.assertRaises(extension.ServiceTaskError):
                await self.invoke()
            setattr(self.request.state, name, False)
        self.request.base_model_id = "override"
        with self.assertRaises(extension.ServiceTaskError):
            await self.invoke()
        del self.request.base_model_id
        self.modules["open_webui.env"].VERSION = "0.12.3"
        with self.assertRaises(extension.ServiceTaskError):
            await self.invoke()
        self.dispatch.assert_not_awaited()

    async def test_native_request_state_cannot_override_signed_task_context_during_stock_dispatch(self):
        for inherited in [None, {"task": None}, {"chat_id": OTHER}, {"new_context": "not-in-task"}]:
            self.request.state.metadata = inherited
            with self.subTest(inherited=inherited), self.assertRaises(extension.ServiceTaskError):
                await self.invoke()
        self.dispatch.assert_not_awaited()
        self.request.state.metadata = {"chat_id": CHAT, "native_extra": copy.deepcopy(self.metadata["native_extra"])}
        await self.invoke()
        self.dispatch.assert_awaited_once()

    async def test_unavailable_or_invalid_function_config_never_falls_back_to_personal(self):
        original_own, original_common = copy.deepcopy(self.own_config), copy.deepcopy(self.common_config)
        for own, common in [(None, original_common), (original_own, None), ({}, original_common),
                            ({"target_model_id": "unknown-model"}, original_common),
                            (original_own, {**original_common, "service_payer_id": USER}),
                            (original_own, {**original_common, "service_payer_id": "invalid"}),
                            (original_own, {**original_common, "ledger_base_url": "https://foreign.invalid"})]:
            self.own_config, self.common_config = own, common
            with self.subTest(own_present=own is not None, common_present=common is not None), self.assertRaises(extension.ServiceTaskError):
                await self.invoke()
        self.dispatch.assert_not_awaited()

    async def test_configured_other_employee_cannot_be_used_as_service_payer(self):
        self.common_config["service_payer_id"] = OTHER
        with self.assertRaises(extension.ServiceTaskError) as caught:
            await self.invoke()
        self.assertEqual(caught.exception.code, "personal_payer_forbidden")
        self.users.get_user_by_id.assert_awaited_with(OTHER)
        self.connection.assert_not_awaited()
        self.dispatch.assert_not_awaited()

    async def test_service_payer_directory_lookup_failure_is_not_absence_and_exposes_no_secrets(self):
        def lookup(user_id):
            if user_id == PAYER:
                raise RuntimeError(PRIVATE + SECRET)
            return {USER: self.user, OTHER: self.other_user}.get(user_id)
        self.users.get_user_by_id.side_effect = lookup
        with self.assertRaises(extension.ServiceTaskError) as caught:
            await self.invoke()
        self.assertEqual(caught.exception.code, "native_task_unavailable")
        self.assertNotIn(PRIVATE, str(caught.exception))
        self.assertNotIn(SECRET, str(caught.exception))
        self.users.get_user_by_id.assert_awaited_with(PAYER)
        self.connection.assert_not_awaited()
        self.dispatch.assert_not_awaited()

    async def test_native_acl_or_binding_mismatch_blocks_dispatch(self):
        self.access.side_effect = Exception(PRIVATE)
        with self.assertRaises(extension.ServiceTaskError) as caught:
            await self.invoke()
        self.assertNotIn(PRIVATE, str(caught.exception))
        self.access.side_effect = None
        for connection in [(URL + "/v1", SECRET, {"auth_type": "none"}),
                           (URL + "/v1", SECRET, {"azure": True}),
                           ("https://foreign.invalid", SECRET, {})]:
            self.connection.return_value = connection
            with self.assertRaises(extension.ServiceTaskError):
                await self.invoke()
        self.dispatch.assert_not_awaited()

    async def test_role_revocation_during_final_binding_read_is_rechecked_before_dispatch(self):
        reads = 0
        async def connection(_):
            nonlocal reads
            reads += 1
            if reads == 2:
                self.user = SimpleNamespace(id=USER, role="pending")
            return URL + "/v1", SECRET, {"prefix_id": "gateway"}
        self.connection.side_effect = connection
        with self.assertRaises(extension.ServiceTaskError) as caught:
            await self.invoke()
        self.assertEqual(caught.exception.code, "active_user_required")
        self.dispatch.assert_not_awaited()

    async def test_function_config_gateway_secret_or_model_binding_drift_blocks_dispatch(self):
        for kind in ["payer", "target", "secret", "base_model"]:
            self.common_config["service_payer_id"] = PAYER
            self.own_config["target_model_id"] = TARGET
            self.record.base_model_id = "gateway." + WIRE
            reads = 0
            async def changed(_):
                nonlocal reads
                reads += 1
                if reads == 1:
                    if kind == "payer":
                        self.common_config["service_payer_id"] = OTHER
                    elif kind == "target":
                        self.own_config["target_model_id"] = "changed-target"
                    elif kind == "base_model":
                        self.record.base_model_id = "gateway.changed-wire"
                        self.request.app.state.OPENAI_MODELS["gateway.changed-wire"] = {"urlIdx": 3}
                key = SECRET + "rotated" if kind == "secret" and reads > 1 else SECRET
                return URL + "/v1", key, {"prefix_id": "gateway"}
            self.connection.side_effect = changed
            with self.subTest(kind=kind), self.assertRaises(extension.ServiceTaskError):
                await self.invoke()
        self.dispatch.assert_not_awaited()

    async def test_foreign_chat_or_context_mutation_during_owner_await_is_denied(self):
        original_body, original_meta = copy.deepcopy(self.body), copy.deepcopy(self.metadata)
        for kind in ["foreign_chat", "request_path", "body_context", "metadata_context"]:
            self.body, self.metadata = copy.deepcopy(original_body), copy.deepcopy(original_meta)
            self.task_body = self.metadata["task_body"]
            self.request.scope["path"] = extension.TITLE_PATH
            self.chat = SimpleNamespace(id=CHAT, user_id=USER)
            async def changed(_):
                if kind == "foreign_chat":
                    self.chat = SimpleNamespace(id=CHAT, user_id=OTHER)
                elif kind == "request_path":
                    self.request.scope["path"] = "/api/chat/completions"
                elif kind == "body_context":
                    self.body["messages"][0]["content"] = "changed instructions"
                else:
                    self.metadata["native_extra"] = {"changed": True}
                return URL + "/v1", SECRET, {"prefix_id": "gateway"}
            self.connection.side_effect = changed
            with self.subTest(kind=kind), self.assertRaises(extension.ServiceTaskError):
                await self.invoke()
        self.dispatch.assert_not_awaited()

    async def test_native_failures_expose_only_fixed_safe_error_and_never_retry(self):
        self.dispatch.side_effect = RuntimeError(PRIVATE + SECRET)
        with self.assertRaises(extension.ServiceTaskError) as caught:
            await self.invoke()
        self.assertEqual(caught.exception.code, "native_task_unavailable")
        self.assertNotIn(PRIVATE, str(caught.exception))
        self.assertNotIn(SECRET, str(caught.exception))
        self.dispatch.assert_awaited_once()

    async def test_native_error_response_is_not_exposed_as_success_or_raw_diagnostics(self):
        for response in [{"error": {"message": PRIVATE + SECRET}},
                         SimpleNamespace(status_code=503, body=(PRIVATE + SECRET).encode())]:
            self.dispatch.reset_mock()
            self.dispatch.return_value = response
            with self.subTest(response_type=type(response).__name__), self.assertRaises(extension.ServiceTaskError) as caught:
                await self.invoke()
            self.assertEqual(caught.exception.code, "native_task_failed")
            self.assertNotIn(PRIVATE, str(caught.exception))
            self.assertNotIn(SECRET, str(caught.exception))
            self.dispatch.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
