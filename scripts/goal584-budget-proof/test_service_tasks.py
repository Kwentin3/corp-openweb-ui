"""Representative actual-boundary receipts and negative native service mutations."""
import copy
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
    result = {"id": identifier, "choices": [{"message": {"role": "assistant", "content": '{"title":"Proof"}'}}]}
    return [capture, provider, row, result, payer, actor, chat, key_hash]


class ServiceProofTests(unittest.TestCase):
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

    def reject(self, mutate):
        values = packet()
        mutate(values)
        with self.assertRaises((AssertionError, S.ProofError, ValueError, KeyError)):
            S.verify_context(*values)

    def test_reject_lost_changed_or_extra_native_context_at_real_comparison_seams(self):
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

    def test_failed_actual_title_phase_restores_entire_original_task_config(self):
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
        with patch.object(S, "owned_source", side_effect=owned), patch.object(S, "budgets", budgets), \
             patch.object(S, "native_client", return_value=SimpleNamespace(logs=lambda _user: [])), \
             patch.object(S, "install", side_effect=install), patch.object(S, "write_private"), \
             patch.object(S, "provider", return_value={"requests": []}), patch.object(S, "save_capture"), \
             patch.object(S, "captured", return_value={"requests": [{}]}), \
             patch.object(S, "response", side_effect=[(403, {"error": {"message": S.UNSIGNED_REASON}}),
                                                     (400, {"error": {"type": "native-service-failure"}})]):
            with self.assertRaisesRegex(S.ProofError, "Signed native service title failed"):
                S.run(WebUI(), state, SimpleNamespace(private_state=Path("synthetic-private-state.json")))
        self.assertEqual(current, original)
        self.assertEqual([body["TASK_MODEL"] for body in writes], [S.MODELS[0], S.FUNCTION_ID, "original-model"])
        self.assertTrue(state["service_fixture"]["task_config_restored"])


if __name__ == "__main__":
    unittest.main()
