"""Representative actual-boundary receipts and negative native service mutations."""
import ast
import asyncio
from contextlib import asynccontextmanager
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

HERE = Path(__file__).resolve().parent
BUDGETS = HERE.parents[1] / "deploy/openwebui-budgets"
sys.path[:0] = [str(HERE), str(BUDGETS)]
for name, filename in (("employee_budget_assignment", "assignment.py"),
                       ("employee_budget_admin_contract", "admin_contract.py"),
                       ("employee_budget_admin_client", "admin_client.py")):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, BUDGETS / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
import prove_service_tasks as S


def packet():
    payer, actor, chat, call = [str(uuid4()) for _ in range(4)]
    scope = {"schema": 1, "user_id": payer, "actor_id": actor, "chat_id": chat, "call_id": call,
             "model": S.MODELS[0], "task": S.TASK, "category": "service"}
    body = {"model": S.MODELS[0], "messages": [{"role": "system", "content": "Native target instruction"},
             {"role": "user", "content": "Generate title for the saved user input: Hi"}], "stream": False,
            "max_tokens": 5, "temperature": 0, "response_format": {"type": "json_object"},
            "tools": [{"type": "function", "function": {"name": "native_target_schema", "parameters": {
                "type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}}}],
            "tool_choice": "none"}
    baseline = {"user_id": actor, "task": S.TASK, "body": body, "body_after_auth": copy.deepcopy(body),
                "attestation_present_before": False, "provenance_removed_after": True}
    signed = {**copy.deepcopy(baseline), "attestation_present_before": True, "native_auth_user_id": payer,
              "verified_cost_scope": scope, "native_stream_usage_patch": {}}
    raw_unknown = {**copy.deepcopy(baseline), "task": "tags_generation"}
    capture = {"requests": [baseline, signed, copy.deepcopy(baseline), raw_unknown]}
    identifier, key_hash = "chatcmpl-goal584-" + uuid4().hex, "a" * 64
    row = {"request_id": identifier, "user": payer, "api_key": key_hash, "model_group": S.MODELS[0],
           "session_id": "owui-service:" + chat, "status": "success", "spend": .2,
           "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
           "metadata": {"spend_logs_metadata": {"owui_budget": scope}}}
    provider = {"synthetic": True, "requests": [{"id": identifier, "body": {**copy.deepcopy(body), "model": "goal584-fake-a"},
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}]}
    provider["requests"][0]["body"].pop("stream")
    result = {"id": identifier, "choices": [{"message": {"role": "assistant", "content": '{"title":"Proof"}'}}]}
    return [capture, provider, row, result, payer, actor, chat, key_hash]


class ServiceProofTests(unittest.TestCase):
    def test_pinned_native_openai_handler_extracts_nonstream_flag_before_dispatch(self):
        path = HERE.parents[1] / "local/goal584/native-openai-handler.py"
        if not path.exists():
            self.skipTest("Pinned native OpenAI handler source unavailable")
        source = path.read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),
                         "e6d25eea6d0a12d16f781ea175982830ab7eaa945ca32b4c5b424580d84f8831")
        owner = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef)
                     and n.name == "OpenAIChatCompletion")
        method = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "completion")
        assignments = []
        for node in ast.walk(method):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id in (
                        "inference_params", "stream_options", "stream") and isinstance(node.value, ast.Call) \
                        and isinstance(node.value.func, ast.Attribute) and node.value.func.attr in ("copy", "pop"):
                    assignments.append((node.lineno, ast.Assign(targets=targets, value=node.value)))
        self.assertEqual(len(assignments), 3)
        code = compile(ast.fix_missing_locations(ast.Module(body=[n for _, n in sorted(assignments)],
                                                           type_ignores=[])), "native-openai-transport", "exec")
        original = copy.deepcopy(packet()[0]["requests"][1]["body"])
        namespace = {"optional_params": original}
        exec(code, namespace)
        self.assertIs(namespace["stream"], False)
        self.assertNotIn("stream", namespace["inference_params"])
        self.assertEqual(namespace["inference_params"], {k: v for k, v in original.items() if k != "stream"})
        self.assertIs(original["stream"], False)

    def test_native_admission_replay_proves_saved_chat_409_and_stateless_request(self):
        root = HERE.parents[1] / "local/goal584/cost-display/open-webui/backend/open_webui"
        if not (root / "main.py").exists():
            self.skipTest("Pinned native main source unavailable; runtime guard still required")
        owner = next(node for node in ast.parse((root / "main.py").read_text(encoding="utf-8")).body
                     if isinstance(node, ast.AsyncFunctionDef) and node.name == "chat_completion")
        nodes = list(ast.walk(owner))
        message_assignment = next(node for node in nodes if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "pop" and node.value.args and isinstance(node.value.args[0], ast.Constant)
            and node.value.args[0].value == "message_ids")
        message_if = next(node for node in nodes if isinstance(node, ast.If) and isinstance(node.test, ast.Call)
            and isinstance(node.test.func, ast.Name) and node.test.func.id == "isinstance"
            and isinstance(node.test.args[0], ast.Name) and node.test.args[0].id == "message_ids"
            and node.lineno > message_assignment.lineno)
        chat_assignment = next(node for node in nodes if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "chat_id" for target in node.targets)
            and isinstance(node.value, ast.BoolOp) and isinstance(node.value.values[0], ast.Call)
            and isinstance(node.value.values[0].func, ast.Attribute) and node.value.values[0].func.attr == "pop")
        admission = compile(ast.fix_missing_locations(ast.Module(body=[message_assignment, message_if, chat_assignment],
                                                                type_ignores=[])), "native-main-admission", "exec")
        source = {"model": S.MODELS[0], "chat_id": str(uuid4()), "messages": [{"role": "user", "content": "Hi"}]}
        original = {**S.ordinary_pipe_request(source), "chat_id": source["chat_id"]}
        old = {"form_data": original, "model_id": S.FUNCTION_ID}
        exec(admission, old)
        self.assertEqual(old["message_ids"], [{"model_id": S.FUNCTION_ID, "message_id": None}])
        self.assertEqual(old["chat_id"], source["chat_id"])
        tree = ast.parse((root / "models/chats.py").read_text(encoding="utf-8"))
        insertion = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "insert_chat_turn")
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        native = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[future, insertion], type_ignores=[])),
                     "native-insert-chat-turn", "exec"), native)
        @asynccontextmanager
        async def transaction(_chat_id):
            yield None, SimpleNamespace(chat={"history": {"messages": {}, "currentId": None}})
        async def accessible(*args, **kwargs):
            return True
        fake = SimpleNamespace(get_accessible_chat_by_id=accessible, _chat_transaction=transaction)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(native["insert_chat_turn"](fake, old["chat_id"], SimpleNamespace(id=str(uuid4())), {}, old["message_ids"]))
        self.assertEqual((caught.exception.status_code, caught.exception.detail),
                         (409, "Message already exists or has an invalid ID."))
        fixed = S.ordinary_pipe_request(source)
        self.assertEqual(fixed["metadata"], {"task": S.TASK})
        self.assertFalse(any(fixed["background_tasks"].values()))
        self.assertTrue(set(fixed).isdisjoint({"chat_id", "id", "session_id", "user_message", "parent_id"}))
        new = {"form_data": fixed, "model_id": S.FUNCTION_ID}
        exec(admission, new)
        self.assertEqual(new["chat_id"], "")
        spec = importlib.util.spec_from_file_location("native_chat_id_for_service_negative", root / "utils/chat_id.py")
        chat_ids = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(chat_ids)
        self.assertFalse(chat_ids.is_saved_chat_id(new["chat_id"]))

    def test_negative_diagnostics_bind_response_without_echoing_secrets_or_accepting_wrong_guard(self):
        secret = "sk-" + "s" * 32
        body = {"detail": "Message already exists or has an invalid ID.", "private": secret}
        observed = S.negative_diagnostic("ordinary_selected_pipe", 409, body, "unsupported_task")
        self.assertEqual(observed["observed_known_codes"], ["invalid_message_id"])
        self.assertFalse(observed["guard_verified"])
        self.assertEqual(len(observed["response_sha256"]), 64)
        self.assertNotIn(secret, json.dumps(observed))
        self.assertNotIn(body["detail"], json.dumps(observed))
        with self.assertRaises(S.ProofError):
            S.denied(409, body, "unsupported_task")
        for status in (400, 503):
            with self.assertRaises(S.ProofError):
                S.unsigned_denied(status, {"error": {"message": "native database unavailable"}})

    def test_native_workspace_model_registration_has_actor_grant_and_preserves_other_models(self):
        admin, actor = str(uuid4()), str(uuid4())
        state = {"admin": {"id": admin, "token": "native-admin"}, "users": [{"id": actor}], "service_fixture": {}}
        ordinary = {model: {"id": model, "base_model_id": None, "name": model, "params": {"max_tokens": 5},
                    "meta": {"capabilities": {"builtin_tools": True}}, "is_active": True, "access_grants": []}
                    for model in S.MODELS}
        class WebUI:
            def __init__(self, mutation=None):
                self.rows = copy.deepcopy(ordinary)
                self.mutation, self.posted = mutation, None
            def session(self, account, role):
                self.role = role
            def ok(self, method, path, **kwargs):
                if (method, path) != ("POST", "/api/v1/models/create") or self.role != "admin":
                    raise AssertionError("Wrong native model owner/API")
                self.posted = copy.deepcopy(kwargs["body"])
                result = copy.deepcopy(self.posted)
                result.update(user_id=admin)
                result["meta"].update(profile_image_url=None, description=None)
                result["access_grants"] = [dict(grant, id=str(uuid4()), resource_type="model",
                    resource_id=S.FUNCTION_ID, created_at=1234) for grant in result["access_grants"]]
                self.rows[S.FUNCTION_ID] = copy.deepcopy(result)
                if self.mutation:
                    self.mutation(self.rows)
                return result
            def model(self, token, model):
                return copy.deepcopy(self.rows[model])
        native = WebUI()
        S.register_pipe_model(native, state)
        self.assertEqual(native.posted["params"], {})
        self.assertIsNone(native.posted["base_model_id"])
        self.assertEqual(native.posted["meta"], {"capabilities": {"builtin_tools": False}, "filterIds": [], "toolIds": [], "skillIds": []})
        self.assertEqual(native.posted["access_grants"], [{"principal_type": "user", "principal_id": actor, "permission": "read"}])
        self.assertTrue(state["service_fixture"]["ordinary_model_profiles_unchanged"])
        self.assertEqual({model: native.rows[model] for model in S.MODELS}, ordinary)
        for mutation in (lambda rows: rows[S.FUNCTION_ID].update(params={"system": "unexpected"}),
                         lambda rows: rows[S.FUNCTION_ID]["meta"].update(filterIds=["unexpected"]),
                         lambda rows: rows[S.FUNCTION_ID]["access_grants"][0].update(principal_id=str(uuid4())),
                         lambda rows: rows[S.FUNCTION_ID]["access_grants"].append(copy.deepcopy(rows[S.FUNCTION_ID]["access_grants"][0])),
                         lambda rows: rows[S.MODELS[0]].update(params={"max_tokens": 1000})):
            with self.assertRaises(S.ProofError):
                S.register_pipe_model(WebUI(mutation), copy.deepcopy(state))

    def test_unsigned_denial_requires_exact_native_status_and_signature_reason(self):
        failure = {"error": {"message": S.UNSIGNED_REASON, "code": 403}}
        self.assertEqual(S.unsigned_denied(403, failure), {"http_status": 403,
            "native_guard": "invalid_signed_budget_provenance", "message": S.UNSIGNED_REASON})
        for status, value in ((401, failure), (400, failure), (500, failure), (503, failure),
                              (403, {"error": {"message": "database unavailable"}}),
                              (503, {"error": {"message": "database unavailable"}})):
            with self.subTest(status=status), self.assertRaises(S.ProofError):
                S.unsigned_denied(status, value)

    def test_actual_native_baseline_signed_input_and_single_provider_payer_row(self):
        result = S.verify_context(*packet())
        self.assertEqual(result["scope"]["category"], "service")
        self.assertNotIn("answer_id", result["scope"])
        self.assertEqual(result["native_semantic_body"]["tools"][0]["function"]["name"], "native_target_schema")
        self.assertEqual(result["native_nonstream_transport"], {"gateway_stream": False, "provider_stream_present": False})

    def reject(self, mutate):
        values = packet()
        mutate(values)
        with self.assertRaises((AssertionError, S.ProofError, ValueError, KeyError)):
            S.verify_context(*values)

    def test_reject_lost_changed_or_extra_native_context_at_real_comparison_seams(self):
        self.reject(lambda data: data[1]["requests"][0]["body"].update(stream=True))
        self.reject(lambda data: data[1]["requests"][0]["body"].update(stream=False))
        self.reject(lambda data: data[0]["requests"][1]["body"]["messages"][0].update(content="lost target instruction"))
        self.reject(lambda data: data[0]["requests"][1]["body_after_auth"].pop("tools"))
        self.reject(lambda data: data[1]["requests"][0]["body"].update(max_tokens=1000))
        self.reject(lambda data: data[1]["requests"][0]["body"]["tools"][0]["function"]["parameters"].update(required=[]))
        self.reject(lambda data: data[1]["requests"][0]["body"].update(metadata={"private": True}))
        self.reject(lambda data: data[0]["requests"].append(copy.deepcopy(data[0]["requests"][0])))
        self.reject(lambda data: data[1]["requests"].append(copy.deepcopy(data[1]["requests"][0])))

    def test_reject_actor_payer_session_key_scope_and_actual_cost_mutations(self):
        for field, value in (("user", str(uuid4())), ("api_key", "b" * 64), ("session_id", str(uuid4())),
                             ("spend", .4), ("completion_tokens", 6), ("request_id", "other-provider-id")):
            self.reject(lambda data, field=field, value=value: data[2].update({field: value}))
        self.reject(lambda data: data[0]["requests"][1].update(native_auth_user_id=data[5]))
        self.reject(lambda data: data[0]["requests"][0].update(native_auth_user_id=data[4]))
        self.reject(lambda data: data[0]["requests"][3].update(task=S.TASK))
        self.reject(lambda data: data[2]["metadata"]["spend_logs_metadata"]["owui_budget"].update(answer_id=str(uuid4())))
        self.reject(lambda data: data[3]["choices"][0]["message"].update(content="not a JSON title"))

    def test_secret_guard_checks_actual_values_and_signed_or_native_key_shapes(self):
        for value, known in (({"body": "private-known"}, ["private-known"]),
                             ({"body": "sk-" + "a" * 32}, []), ({"body": "eyJaaa.bbb.ccc"}, [])):
            with self.subTest(value=value), self.assertRaises(S.ProofError):
                S.no_secrets(value, known)
        self.assertEqual(S.no_secrets({"usage": 15}), {"usage": 15})

    def test_task_config_preserves_all_native_fields_and_pins_same_generation_parameters(self):
        original = {"TASK_MODEL": "old", "TASK_MODEL_EXTERNAL": "old", "TASK_MODEL_PARAMS": {},
                    "ENABLE_TITLE_GENERATION": False, "TITLE_GENERATION_PROMPT_TEMPLATE": "native configured prompt",
                    "native_unrelated": {"preserve": True}, **{flag: False for flag in S.TASK_FLAGS}}
        current = copy.deepcopy(original)
        class WebUI:
            def session(self, account, role):
                if role != "admin":
                    raise AssertionError("Missing native admin role")
            def ok(self, method, path, **kwargs):
                if method == "POST":
                    current.clear()
                    current.update(copy.deepcopy(kwargs["body"]))
                return copy.deepcopy(current)
        webui, admin = WebUI(), {"token": "synthetic-native-admin"}
        baseline = S.task_config(webui, admin, original, S.MODELS[0])
        signed = S.task_config(webui, admin, original, S.FUNCTION_ID)
        self.assertEqual({key: value for key, value in baseline.items() if key not in ("TASK_MODEL", "TASK_MODEL_EXTERNAL")},
                         {key: value for key, value in signed.items() if key not in ("TASK_MODEL", "TASK_MODEL_EXTERNAL")})
        self.assertEqual(signed["TASK_MODEL_PARAMS"], S.PARAMS)
        self.assertEqual(signed["TITLE_GENERATION_PROMPT_TEMPLATE"], original["TITLE_GENERATION_PROMPT_TEMPLATE"])
        self.assertTrue(signed["ENABLE_TITLE_GENERATION"])
        self.assertFalse(any(signed[flag] for flag in S.TASK_FLAGS if flag != "ENABLE_TITLE_GENERATION"))
        self.assertEqual(original["TASK_MODEL"], "old")

    def test_owned_source_uses_persisted_exact_fixture_actor_and_message(self):
        actor, chat, message = [str(uuid4()) for _ in range(3)]
        saved = {"id": chat, "user_id": actor, "chat": {"history": {"messages": {
            message: {"id": message, "role": "user", "user_id": actor, "content": "Hi"}}}}}
        def read(_webui, method, path, token, body=None):
            self.assertEqual((method, token), ("GET", "synthetic-actor-session"))
            return (200, [{"id": chat}]) if "/list?" in path else (200, copy.deepcopy(saved))
        with patch.object(S, "response", side_effect=read):
            source, observed_id = S.owned_source(None, {"id": actor, "token": "synthetic-actor-session"})
            self.assertEqual(source, {"model": S.MODELS[0], "chat_id": chat, "messages": [{"role": "user", "content": "Hi"}]})
            self.assertEqual(observed_id, message)
            saved["user_id"] = str(uuid4())
            with self.assertRaises(S.ProofError):
                S.owned_source(None, {"id": actor, "token": "synthetic-actor-session"})

    def failed_title_phase(self, *, negative=False):
        actor, payer, chat, foreign = [str(uuid4()) for _ in range(4)]
        state = {"admin": {"id": str(uuid4()), "token": "admin"},
                 "users": [{"id": actor, "token": "actor"}, {"id": str(uuid4()), "token": "foreign"}]}
        original = {"TASK_MODEL": "original-model", "TASK_MODEL_EXTERNAL": "original-external",
                    "TASK_MODEL_PARAMS": {"temperature": .7}, "ENABLE_TITLE_GENERATION": False,
                    "TITLE_GENERATION_PROMPT_TEMPLATE": "original-prompt", **{flag: False for flag in S.TASK_FLAGS}}
        current, writes = copy.deepcopy(original), []
        class WebUI:
            def session(self, *args):
                pass
            def ok(self, method, path, **kwargs):
                if method == "POST":
                    writes.append(copy.deepcopy(kwargs["body"]))
                    current.clear()
                    current.update(copy.deepcopy(kwargs["body"]))
                return copy.deepcopy(current)
        def install(_webui, actual_state, _path):
            actual_state["service_fixture"] = {"stage": "setup_complete", "pipe_sha256": "native-source-hash"}
            return payer
        async def budgets(_state, payer_id=None):
            return [SimpleNamespace(user_id=actor)], SimpleNamespace(spend=0, max_budget=20) if payer_id else None
        def owned(_webui, account):
            return {"model": S.MODELS[0], "chat_id": chat if account["id"] == actor else foreign,
                    "messages": [{"role": "user", "content": "Hi"}]}, str(uuid4())
        replies = [(403, {"error": {"message": S.UNSIGNED_REASON}}),
                   (200, {"id": "synthetic-service-response"}) if negative else (400, {"error": {"type": "native-service-failure"}}),
                   (409, {"detail": "Message already exists or has an invalid ID."})]
        positive = False
        def respond(*args, **kwargs):
            nonlocal positive
            result = replies.pop(0)
            positive = positive or result[0] == 200
            return result
        def observe_provider(*args, **kwargs):
            return {"requests": [{"id": "synthetic-service-response"}] if positive else []}
        partial = {}
        with patch.object(S, "owned_source", side_effect=owned), patch.object(S, "budgets", budgets), \
             patch.object(S, "native_client", return_value=SimpleNamespace(logs=lambda _user: [])), \
             patch.object(S, "install", side_effect=install), patch.object(S, "write_private"), \
             patch.object(S, "provider", side_effect=observe_provider), patch.object(S, "save_capture"), \
             patch.object(S, "captured", return_value={"requests": [{}]}), \
             patch.object(S, "response", side_effect=respond):
            with self.assertRaisesRegex(S.ProofError, "intended native guard" if negative else "Signed native service title failed"):
                S.run(WebUI(), state, SimpleNamespace(private_state=Path("synthetic-private-state.json")), partial)
        self.assertEqual(current, original)
        self.assertEqual([body["TASK_MODEL"] for body in writes], [S.MODELS[0], S.FUNCTION_ID, "original-model"])
        self.assertTrue(state["service_fixture"]["task_config_restored"])
        self.assertTrue(partial["baseline_observation"]["guard_verified"])
        return partial

    def test_failed_actual_title_phase_restores_entire_original_task_config(self):
        partial = self.failed_title_phase()
        self.assertEqual(partial["stage"], "unsigned_baseline_verified")

    def test_failed_negative_preserves_prior_title_and_safe_case_before_assertion(self):
        partial = self.failed_title_phase(negative=True)
        self.assertEqual(partial["stage"], "negative_observed")
        self.assertEqual(partial["positive_title_provider_ids"], ["synthetic-service-response"])
        self.assertEqual(partial["current_negative_case"], "ordinary_selected_pipe")
        observed = partial["negatives"][0]
        self.assertEqual((observed["http_status"], observed["expected_guard"], observed["observed_known_codes"]),
                         (409, "unsupported_task", ["invalid_message_id"]))
        self.assertFalse(observed["guard_verified"])
        self.assertTrue(observed["provider_ids_unchanged"])


if __name__ == "__main__":
    unittest.main()
