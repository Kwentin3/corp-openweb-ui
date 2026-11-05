"""Representative actual-boundary receipts and negative native service mutations."""
import ast
import asyncio
from contextlib import asynccontextmanager
import copy
from decimal import Decimal
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
from employee_budget_admin_contract import EmployeeBudget, ModelBudget


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
    result = {"id": identifier, "model": S.MODELS[0], "choices": [{"message": {
        "role": "assistant", "content": '{"title":"Proof"}'}, "finish_reason": "stop"}],
        "usage": copy.deepcopy(provider["requests"][0]["usage"])}
    return [capture, provider, row, result, payer, actor, chat, key_hash]


def personal_rows(user_ids):
    result = {}
    for uid in user_ids:
        chat, answer, call = [str(uuid4()) for _ in range(3)]
        scope = {"schema": 1, "category": "personal", "user_id": uid, "model": S.MODELS[0], "chat_id": chat,
                 "root_chat_id": chat, "answer_id": answer, "root_answer_id": answer, "call_id": call}
        result[uid] = [{"request_id": "chatcmpl-goal584-" + uuid4().hex, "user": uid, "session_id": chat,
            "model_group": S.MODELS[0], "spend": .2, "status": "success", "prompt_tokens": 10,
            "completion_tokens": 5, "total_tokens": 15, "metadata": {"spend_logs_metadata": {"owui_budget": scope}}}]
    return result


class ServiceProofTests(unittest.TestCase):
    def test_admin_snapshot_reads_all_four_personal_histories_including_newhire(self):
        staff1, staff2, admin, newhire, payer = [str(uuid4()) for _ in range(5)]
        ids = [staff1, staff2, admin, newhire]
        histories = personal_rows(ids)
        def budget(uid):
            models = S.MODELS[:1] if uid == payer else S.MODELS
            keys = tuple(ModelBudget(model, "a" * 64, "owui-budget-v1-" + "b" * 64, Decimal(10),
                Decimal(".2") if model == S.MODELS[0] else Decimal(0), "1mo", "2026-12-01T00:00:00Z", False)
                for model in models)
            return EmployeeBudget(uid, Decimal(20), Decimal(".2"), "1mo", "2026-12-01T00:00:00Z", keys)
        state = {"users": [{"id": staff1}, {"id": staff2}], "admin": {"id": admin},
            "bootstrap_fixture": {"employee": {"id": newhire}}, "service_fixture": {
                "stage": "qualified_direct_title", "task_config_restored": True, "payer_id": payer}}
        async def budgets(actual, selected):
            self.assertIs(actual, state); self.assertEqual(selected, payer)
            return [budget(uid) for uid in ids], budget(payer)
        observed = []
        def logs(uid):
            observed.append(uid); return histories[uid]
        with patch.object(S, "budgets", budgets), patch.object(S, "native_client", return_value=SimpleNamespace(logs=logs)):
            result = S.admin_snapshot(SimpleNamespace(session=lambda *args: None), state)
        self.assertEqual(set(observed), set(ids)); self.assertEqual(len(observed), 4)
        self.assertEqual({row["user_id"] for row in result["positive_spend_logs"]}, set(ids))
        self.assertEqual(len(result["positive_spend_logs"]), 4)
        self.assertEqual(len(result["personal"]["keys"]), 8)
        self.assertEqual(state["users"], [{"id": staff1}, {"id": staff2}])

    def test_personal_history_evidence_includes_all_four_payers_and_only_native_fixture_ids(self):
        users = [str(uuid4()) for _ in range(4)]
        histories = {uid: ["chatcmpl-goal584-" + uuid4().hex for _ in range(2)] for uid in users}
        actual = S.personal_history_evidence(histories, users)
        self.assertEqual(set(actual), set(users))
        self.assertEqual(actual[users[-1]], sorted(histories[users[-1]]))
        actual[users[0]].clear()
        self.assertEqual(len(histories[users[0]]), 2)
        mutations = [lambda h: h.pop(users[-1]), lambda h: h.update({str(uuid4()): []}),
                     lambda h: h[users[0]].append("Authorization: Bearer eyJaaa.bbb.ccc"),
                     lambda h: h[users[0]].append("sk-" + "x" * 32),
                     lambda h: h[users[0]].append(h[users[0]][0]),
                     lambda h: h.update({users[0]: ["chatcmpl-goal584-" + uuid4().hex] * 1001})]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                changed = copy.deepcopy(histories)
                mutate(changed)
                with self.assertRaises(S.ProofError):
                    S.personal_history_evidence(changed, users)

    def test_native_title_response_evidence_whitelists_actual_result_and_rejects_mutations(self):
        values = packet()
        result = {**values[3], "_hidden_params": {"headers": {"Authorization": "sk-" + "x" * 32}}}
        actual = S.title_response_evidence(result)
        self.assertEqual(actual, values[3])
        self.assertNotIn("Authorization", json.dumps(actual))
        for mutate in (lambda r: r.update(model="goal584-fake-a"), lambda r: r.update(id="sk-" + "x" * 32),
                       lambda r: r["choices"][0]["message"].update(content='{"title":"Wrong"}'),
                       lambda r: r["choices"][0]["message"].update(role="user"),
                       lambda r: r["choices"][0].update(finish_reason="length"),
                       lambda r: r["usage"].update(total_tokens=16)):
            changed = copy.deepcopy(result)
            mutate(changed)
            with self.assertRaises(S.ProofError):
                S.title_response_evidence(changed)
        self.reject(lambda data: data[3].update(id="chatcmpl-goal584-" + uuid4().hex))
        self.reject(lambda data: data[3]["usage"].update(completion_tokens=6))

    def test_native_service_row_evidence_retains_exact_verified_whitelist_without_headers(self):
        values = packet()
        row, payer, actor, chat, key_hash = values[2], *values[4:]
        row.update(key_alias="owui-budget-v1-" + "d" * 64,
                   request_body={"messages": [{"content": "private chat"}]},
                   request_headers={"Authorization": "Bearer sk-" + "x" * 32})
        row["metadata"]["raw_headers"] = {"Authorization": "Bearer eyJaaa.bbb.ccc"}
        for metadata in (row["metadata"], json.dumps(row["metadata"])):
            actual = S.service_row_evidence({**row, "metadata": metadata}, payer, actor, chat, key_hash)
            self.assertEqual(set(actual), {"request_id", "user_id", "api_key_hash", "model_group", "session_id",
                "status", "spend_usd", "usage", "verified_scope", "key_alias"})
            self.assertEqual(actual["api_key_hash"], key_hash)
            self.assertEqual(actual["verified_scope"], values[0]["requests"][1]["verified_cost_scope"])
            self.assertEqual(actual["usage"], {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
            self.assertEqual(actual["spend_usd"], "0.2")
            self.assertNotIn("Authorization", json.dumps(actual))
            self.assertNotIn("private chat", json.dumps(actual))
            self.assertNotIn("metadata", actual)
        actual["verified_scope"]["actor_id"] = "changed"
        self.assertEqual(row["metadata"]["spend_logs_metadata"]["owui_budget"]["actor_id"], actor)

    def test_native_service_row_evidence_rejects_credentials_and_unmatched_native_rows(self):
        for field, value in (("api_key", "sk-" + "x" * 32), ("api_key", "b" * 64),
                             ("user", str(uuid4())), ("spend", .4),
                             ("request_id", "Authorization: Bearer eyJaaa.bbb.ccc"),
                             ("key_alias", "sk-" + "x" * 32)):
            with self.subTest(field=field):
                values = packet()
                values[2][field] = value
                with self.assertRaises(S.ProofError) as caught:
                    S.service_row_evidence(values[2], *values[4:])
                self.assertNotIn(str(value), str(caught.exception))
        values = packet()
        with self.assertRaises(S.ProofError):
            S.service_row_evidence(values[2], *values[4:7], "sk-" + "x" * 32)

    def test_task_config_evidence_hashes_full_native_readback_without_prompt_or_header_export(self):
        secret = "sk-" + "x" * 32
        original = {"TASK_MODEL": "goal584-a", "TASK_MODEL_EXTERNAL": "goal584-a",
                    "TASK_MODEL_PARAMS": {**S.PARAMS, "headers": {"Authorization": secret}},
                    "TITLE_GENERATION_PROMPT_TEMPLATE": "private native title template " + secret,
                    "raw_headers": {"Authorization": "Bearer eyJaaa.bbb.ccc"},
                    **{flag: False for flag in S.TASK_FLAGS}}
        first = S.task_config_evidence(original)
        self.assertEqual(first["task_model_params"]["known_values"], S.PARAMS)
        self.assertNotIn(secret, json.dumps(first))
        self.assertNotIn("Authorization", json.dumps(first))
        self.assertNotIn("private native title template", json.dumps(first))
        self.assertNotIn("raw_headers", first["present_keys"])
        changed = copy.deepcopy(original)
        changed["raw_headers"]["Authorization"] = "changed"
        self.assertNotEqual(first["sha256"], S.task_config_evidence(changed)["sha256"])
        changed = copy.deepcopy(original)
        changed["TITLE_GENERATION_PROMPT_TEMPLATE"] += " changed"
        self.assertNotEqual(first["prompt_sha256"], S.task_config_evidence(changed)["prompt_sha256"])
        self.assertEqual(first, S.task_config_evidence(copy.deepcopy(original)))
        for value in (secret, "Authorization: Bearer eyJaaa.bbb.ccc"):
            with self.assertRaises(S.ProofError):
                S.task_config_evidence({**original, "TASK_MODEL": value})

    def test_persisted_native_observations_survive_later_context_failure_and_restore(self):
        observed, physical, row, result, payer, actor, chat, key_hash = packet()
        admin, foreign, newhire = str(uuid4()), str(uuid4()), str(uuid4())
        state = {"admin": {"id": admin, "token": "native-admin"}, "users": [
            {"id": actor, "token": "native-actor"}, {"id": str(uuid4()), "token": "native-foreign"}],
            "bootstrap_fixture": {"employee": {"id": newhire}}}
        original = {"TASK_MODEL": "original", "TASK_MODEL_EXTERNAL": "original", "TASK_MODEL_PARAMS": {},
                    **{flag: False for flag in S.TASK_FLAGS}}
        current, signed = copy.deepcopy(original), False
        personal_users = [actor, state["users"][1]["id"], admin, newhire]
        histories = personal_rows(personal_users)
        def budget(uid, spend):
            keys = (ModelBudget(S.MODELS[0], key_hash, "owui-budget-v1-" + "d" * 64, Decimal(20),
                                Decimal(spend), "1mo", "2026-12-01T00:00:00Z", False),)
            if uid != payer:
                keys += (ModelBudget(S.MODELS[1], "b" * 64, "owui-budget-v1-" + "e" * 64, Decimal(0),
                                     Decimal(0), "1mo", "2026-12-01T00:00:00Z", False),)
            return EmployeeBudget(uid, Decimal(20), Decimal(spend), "1mo", "2026-12-01T00:00:00Z", keys)
        personal_reads = 0
        async def budgets(_state, payer_id=None):
            nonlocal personal_reads
            if payer_id is None: personal_reads += 1
            personal_spend = "0" if payer_id is None and personal_reads == 1 else ".2"
            return [budget(uid, personal_spend) for uid in personal_users], budget(payer, ".2" if signed else "0") if payer_id else None
        def install(_webui, actual, _path):
            self.assertEqual(personal_reads, 2)
            actual["service_fixture"] = {"stage": "setup_complete", "pipe_sha256": "fixture-source", "key_hash": key_hash}
            return payer
        class WebUI:
            def session(self, *args):
                pass
            def ok(self, method, path, **kwargs):
                if method == "POST":
                    current.clear()
                    current.update(copy.deepcopy(kwargs["body"]))
                return copy.deepcopy(current)
        def owned(_webui, account):
            return {"model": S.MODELS[0], "chat_id": chat if account["id"] == actor else foreign,
                    "messages": [{"role": "user", "content": "Hi"}]}, str(uuid4())
        title_calls = 0
        def response(_webui, method, path, token, body):
            nonlocal signed, title_calls
            if path == S.TITLE_PATH:
                title_calls += 1
                if title_calls == 1:
                    return 403, {"error": {"message": S.UNSIGNED_REASON}}
                if title_calls == 2:
                    signed = True
                    return 200, result
                return 200, {"error": "chat_access_denied"}
            if path == "/api/chat/completions":
                return 200, {"error": "unsupported_task"}
            return 403, {"error": {"message": S.UNSIGNED_REASON}}
        def poll(_name, fn):
            for _ in range(3):
                value = fn()
                if value is not None: return value
            raise AssertionError("Native fixture did not settle")
        native = SimpleNamespace(logs=lambda uid: [row] if signed and uid == payer else histories.get(uid, []), poll=poll)
        receipt = {}
        with patch.object(S, "owned_source", side_effect=owned), patch.object(S, "budgets", budgets), \
             patch.object(S, "install", side_effect=install), patch.object(S, "native_client", return_value=native), \
             patch.object(S, "write_private"), patch.object(S, "save_capture"), \
             patch.object(S, "provider", side_effect=lambda *args, **kwargs: physical if signed else {"requests": []}), \
             patch.object(S, "captured", side_effect=lambda: observed if signed else {"requests": observed["requests"][:1]}), \
             patch.object(S, "response", side_effect=response), \
             patch.object(S, "verify_context", side_effect=S.ProofError("context drift")):
            with self.assertRaisesRegex(S.ProofError, "context drift"):
                S.run(WebUI(), state, SimpleNamespace(private_state=Path("private.json")), receipt)
        self.assertEqual(receipt["native_service_row"]["request_id"], row["request_id"])
        self.assertEqual(len(receipt["personal_baseline_observations"]), 2)
        self.assertEqual(receipt["personal_baseline_observations"][0]["personal"]["users"][0]["spend_usd"], "0")
        self.assertEqual(receipt["personal_baseline_observations"][-1]["personal"], receipt["personal_before"])
        self.assertEqual({r["user_id"] for r in receipt["personal_baseline_observations"][-1]["positive_spend_logs"]}, set(personal_users))
        self.assertEqual(receipt["native_title_response"], result)
        self.assertEqual(set(receipt["personal_ids_before"]), set(personal_users))
        self.assertEqual(receipt["personal_ids_before"], receipt["personal_ids_after"])
        self.assertEqual(receipt["personal_ids_after"][newhire], [histories[newhire][0]["request_id"]])
        self.assertEqual(receipt["personal_before"], receipt["personal_after"])
        self.assertEqual(receipt["service_before"]["users"][0]["spend_usd"], "0")
        self.assertEqual(receipt["service_after"]["users"][0]["spend_usd"], "0.2")
        self.assertEqual(receipt["task_config_observations"]["original"], receipt["task_config_observations"]["restored"])
        self.assertEqual(set(receipt["task_config_observations"]), {"original", "baseline", "service", "restored"})
        self.assertEqual(current, original)

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
                 "users": [{"id": actor, "token": "actor"}, {"id": str(uuid4()), "token": "foreign"}],
                 "bootstrap_fixture": {"employee": {"id": foreign}}}
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
            def budget(uid, cap):
                keys = (ModelBudget(S.MODELS[0], "a" * 64, "owui-budget-v1-" + "d" * 64, Decimal(cap),
                                    Decimal(0), "1mo", "2026-12-01T00:00:00Z", False),)
                if uid != payer:
                    keys += (ModelBudget(S.MODELS[1], "b" * 64, "owui-budget-v1-" + "e" * 64, Decimal(0),
                                         Decimal(0), "1mo", "2026-12-01T00:00:00Z", False),)
                return EmployeeBudget(uid, Decimal(cap), Decimal(0), "1mo", "2026-12-01T00:00:00Z", keys)
            return [budget(uid, 40) for uid in (actor, state["users"][1]["id"], state["admin"]["id"], foreign)], \
                   budget(payer, 20) if payer_id else None
        def owned(_webui, account):
            return {"model": S.MODELS[0], "chat_id": chat if account["id"] == actor else foreign,
                    "messages": [{"role": "user", "content": "Hi"}]}, str(uuid4())
        title = packet()[3]
        title["id"] = "chatcmpl-goal584-" + "f" * 32
        replies = [(403, {"error": {"message": S.UNSIGNED_REASON}}),
                   (200, title) if negative else (400, {"error": {"type": "native-service-failure"}}),
                   (409, {"detail": "Message already exists or has an invalid ID."})]
        positive = False
        def respond(*args, **kwargs):
            nonlocal positive
            result = replies.pop(0)
            positive = positive or result[0] == 200
            return result
        def observe_provider(*args, **kwargs):
            return {"requests": [{"id": title["id"]}] if positive else []}
        partial = {}
        with patch.object(S, "owned_source", side_effect=owned), patch.object(S, "budgets", budgets), \
             patch.object(S, "native_client", return_value=SimpleNamespace(logs=lambda _user: [], poll=lambda _name, fn: fn())), \
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
        self.assertEqual(partial["personal_before"]["users"][0]["user_id"], actor)
        self.assertEqual(partial["service_before"]["users"][0]["spend_usd"], "0")
        self.assertEqual(partial["task_config_observations"]["original"], partial["task_config_observations"]["restored"])
        return partial

    def test_failed_actual_title_phase_restores_entire_original_task_config(self):
        partial = self.failed_title_phase()
        self.assertEqual(partial["stage"], "unsigned_baseline_verified")

    def test_failed_negative_preserves_prior_title_and_safe_case_before_assertion(self):
        partial = self.failed_title_phase(negative=True)
        self.assertEqual(partial["stage"], "negative_observed")
        self.assertEqual(partial["positive_title_provider_ids"], ["chatcmpl-goal584-" + "f" * 32])
        self.assertEqual(partial["current_negative_case"], "ordinary_selected_pipe")
        observed = partial["negatives"][0]
        self.assertEqual((observed["http_status"], observed["expected_guard"], observed["observed_known_codes"]),
                         (409, "unsupported_task", ["invalid_message_id"]))
        self.assertFalse(observed["guard_verified"])
        self.assertTrue(observed["provider_ids_unchanged"])


class ServiceInstallTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_provision_webui import OfficeSetupTests
        cls.fixture = OfficeSetupTests
        OfficeSetupTests.setUpClass.__func__(cls)

    def setUp(self):
        import provision_webui as P
        from io import BytesIO
        from urllib.parse import urlsplit
        self.fixture.setUp(self)
        result, safe = self.fixture.setup_phase(self)
        self.assertEqual(result, 0, safe)
        self.P, self.install_state = P, P.read_private(self.office_path)
        self.original_install_state = copy.deepcopy(self.install_state)
        self.original_rows = copy.deepcopy(self.rows)
        self.original_personal_budget = copy.deepcopy((self.budget_user, self.budget_rows))
        self.payer = "44444444-4444-4444-8444-444444444444"
        self.service_requests, self.service_posts = [], []
        self.service_user, self.service_keys = None, []
        self.drift_after_user_create = None
        self.native_mutation = None
        self.enterContext(patch.object(S, "uuid4", return_value=self.payer))
        self.enterContext(patch.object(S, "OPERATOR_STATE", P.OPERATOR_STATE))
        self.enterContext(patch.object(S, "SOURCE", BUDGETS / "service_pipe.py"))
        transport = S.WebUI().opener
        original_open = transport.open
        owner = self
        class Response(BytesIO):
            headers = {}
            code = 200
            def __init__(self, value): super().__init__(json.dumps(value).encode())
        def service_open(request, timeout):
            method, path = request.get_method(), urlsplit(request.full_url).path
            body = json.loads(request.data) if request.data else None
            self.service_requests.append((method, path, copy.deepcopy(body), request.get_header("Authorization")))
            if method != "POST": return original_open(request, timeout)
            self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-admin-token")
            self.assertEqual(P.read_private(self.office_path)["service_fixture"]["stage"], "installing")
            if path == "/api/v1/functions/create":
                self.assertEqual(body["id"], S.FUNCTION_ID)
                value = copy.deepcopy(body) | {"type": "pipe", "user_id": self.state["admin"]["id"], "is_active": False, "is_global": False}
                self.functions[S.FUNCTION_ID] = value
                self.valves[S.FUNCTION_ID] = {"target_model_id": ""}
            elif path == "/api/v1/models/create":
                self.assertEqual(body["id"], S.FUNCTION_ID)
                value = copy.deepcopy(body) | {"user_id": self.state["admin"]["id"], "write_access": True}
                value["meta"].update(description=None)
                value["access_grants"] = [dict(g, id=str(uuid4()), resource_type="model", resource_id=S.FUNCTION_ID, created_at=1234)
                    for g in body["access_grants"]]
                self.rows[S.FUNCTION_ID] = value
            elif path == "/api/v1/functions/id/" + S.FUNCTION_ID + "/valves/update":
                self.valves[S.FUNCTION_ID] = copy.deepcopy(body); value = body
            elif path == "/api/v1/functions/id/" + S.FUNCTION_ID + "/toggle":
                self.functions[S.FUNCTION_ID]["is_active"] = not self.functions[S.FUNCTION_ID]["is_active"]
                value = self.functions[S.FUNCTION_ID]
            elif path == "/api/v1/functions/id/employee_budget_cost/valves/update":
                self.valves["employee_budget_cost"] = copy.deepcopy(body); value = body
            else: raise AssertionError("Unexpected installer native POST")
            if self.native_mutation: self.native_mutation(path, body)
            return Response(copy.deepcopy(value))
        self.enterContext(patch.object(transport, "open", side_effect=service_open))
        def catalog(payload):
            if S.FUNCTION_ID in self.rows and self.functions[S.FUNCTION_ID]["is_active"]:
                payload["data"].append({"id": S.FUNCTION_ID, "owned_by": "openai", "pipe": {"type": "pipe"}})
            if getattr(self, "target_catalog_mutation", None): self.target_catalog_mutation(payload)
        self.catalog_change = catalog
        async def native_budget_request(client, method, route, *, params=None, body=None):
            self.assertEqual((params or body).get("user_id"), self.payer)
            if method == "POST": self.service_posts.append((route, copy.deepcopy(body)))
            if route == "/user/info":
                if self.service_user is None: raise self.budget_module.BudgetAdminError("native_http_404")
                return {"user_info": self.service_user, "teams": []}
            if route == "/key/list": return {"keys": self.service_keys, "current_page": 1,
                "total_count": len(self.service_keys), "total_pages": int(bool(self.service_keys))}
            if route == "/user/new":
                self.service_user = dict(body, team_id=None, budget_reset_at="2099-01-01T00:00:00Z")
                if self.drift_after_user_create: self.drift_after_user_create()
                return {"user_id": "misleading POST"}
            if route == "/key/generate":
                row = copy.deepcopy(body); key = row.pop("key")
                row.update(token=hashlib.sha256(key.encode()).hexdigest(), expires=None, budget_reset_at="2099-01-01T00:00:00Z")
                self.service_keys.append(row); return {"token": "misleading POST"}
            raise AssertionError("Unexpected service native budget route")
        self.enterContext(patch.object(S.BudgetAdminClient, "_request", native_budget_request))
        self.webui = S.WebUI()

    def install(self, **kwargs):
        return S.install(self.webui, self.install_state, self.office_path, **kwargs)

    def assert_unchanged_context(self):
        self.assertEqual((self.budget_user, self.budget_rows), self.original_personal_budget)
        self.assertEqual(self.tasks, self.inputs["service_baseline"]["task_config"])
        self.assertEqual(self.tasks["TASK_MODEL_PARAMS"]["custom_params"]["reasoning"]["effort"], "none")
        self.assertFalse(any("tasks" in path or "completions" in path or "responses" in path
            for method, path, *_ in self.service_requests))

    def test_default_installer_keeps_existing_target_twenty_cap_and_pipe_model_contract(self):
        self.install_state = copy.deepcopy(self.state)  # Original ordinary A/B fixture, not Office handoff.
        self.assertEqual(self.install(), self.payer)
        self.assertEqual([path for path, _ in self.service_posts], ["/user/new", "/key/generate"])
        self.assertEqual(self.service_posts[0][1]["models"], [S.MODELS[0]])
        self.assertEqual(self.service_posts[0][1]["max_budget"], 20)
        self.assertEqual(self.service_posts[1][1]["models"], [S.MODELS[0]])
        self.assertEqual(self.service_posts[1][1]["max_budget"], 20)
        self.assertEqual(self.valves[S.FUNCTION_ID], {"target_model_id": S.MODELS[0]})
        self.assertNotIn("target_model_id", self.install_state["service_fixture"])
        self.assertEqual(self.rows[S.FUNCTION_ID]["params"], {})
        self.assertIsNone(self.rows[S.FUNCTION_ID]["base_model_id"])
        self.assert_unchanged_context()

    def test_explicit_office_target_and_cap_reuse_actual_initialize_and_install_readbacks(self):
        self.assertEqual(self.install(target_model="gpt-6-luna", cap=Decimal(1000)), self.payer)
        saved = self.P.read_private(self.office_path)
        self.assertEqual(saved["service_fixture"]["stage"], "setup_complete")
        self.assertEqual(saved["service_fixture"]["target_model_id"], "gpt-6-luna")
        self.assertEqual(saved["service_fixture"]["protected_model_profiles"],
            {m: self.original_rows[m] for m in ("gpt-6-luna", "gpt-5.4-mini")})
        self.assertEqual([body["models"] for _, body in self.service_posts], [["gpt-6-luna"]] * 2)
        self.assertTrue(all(body["max_budget"] == 1000 for _, body in self.service_posts))
        self.assertEqual(self.valves[S.FUNCTION_ID], {"target_model_id": "gpt-6-luna"})
        self.assertEqual(self.valves["employee_budget_cost"], {"ledger_base_url": "http://proxy:4000", "service_payer_id": self.payer})
        self.assertEqual(self.rows[S.FUNCTION_ID]["params"], {})
        self.assertIsNone(self.rows[S.FUNCTION_ID]["base_model_id"])
        self.assertEqual(self.rows["gpt-6-luna"]["params"], {})
        self.assertTrue(all(self.rows[m] == value for m, value in self.original_rows.items()))
        self.assert_unchanged_context()

    def test_invalid_target_inputs_stop_before_any_installer_http_or_private_write(self):
        original = self.office_path.read_bytes()
        for target in (None, "", " target", "target\n", S.FUNCTION_ID, "sk-" + "x" * 32):
            with self.subTest(target=target), self.assertRaises(S.ProofError): self.install(target_model=target, cap=Decimal(1000))
            self.assertEqual(self.office_path.read_bytes(), original)
        self.assertFalse(self.service_requests)
        self.assertFalse(self.service_posts)

    def test_cap_validation_stays_with_existing_native_client_without_native_posts(self):
        for cap in (Decimal(-1), Decimal("NaN"), Decimal("0.12345678901234567890123456789")):
            self.install_state = copy.deepcopy(self.original_install_state)
            with self.subTest(cap=cap), self.assertRaises(self.budget_module.BudgetAdminError):
                self.install(target_model="gpt-6-luna", cap=cap)
            self.assertFalse(self.service_posts)
        self.assertNotIn(S.FUNCTION_ID, self.functions)

    def test_stale_prepared_target_or_primary_profile_rejects_before_service_user_creation(self):
        for model in ("gpt-6-luna", "gpt-5.4-mini"):
            self.rows = copy.deepcopy(self.original_rows)
            self.rows[model]["params"]["system"] = "foreign prepared body"
            with self.subTest(model=model), self.assertRaisesRegex(S.ProofError, "Prepared Office"):
                self.install(target_model="gpt-6-luna", cap=Decimal(1000))
        self.assertFalse(self.service_posts)
        self.assertNotIn("service_fixture", self.install_state)

    def test_pipe_or_foreign_or_duplicate_actor_target_rejects_before_mutation(self):
        for mutation in (lambda r: r.update(pipe={"type": "pipe"}), lambda r: r.update(owned_by="ollama")):
            def altered(payload):
                for row in payload["data"]:
                    if row["id"] == "gpt-6-luna": mutation(row)
            self.target_catalog_mutation = altered
            with self.assertRaisesRegex(S.ProofError, "actor-readable direct"):
                self.install(target_model="gpt-6-luna", cap=Decimal(1000))
        self.target_catalog_mutation = lambda p: p["data"].extend(copy.deepcopy([r for r in p["data"] if r["id"] == "gpt-6-luna"]))
        with self.assertRaisesRegex(S.ProofError, "actor-readable direct"):
            self.install(target_model="gpt-6-luna", cap=Decimal(1000))
        self.assertFalse(self.service_posts)

    def test_target_drift_after_user_post_stops_before_key_post_or_payer_binding(self):
        self.drift_after_user_create = lambda: self.rows["gpt-6-luna"]["params"].update(system="changed while initializing")
        with self.assertRaisesRegex(S.ProofError, "changed during installation"):
            self.install(target_model="gpt-6-luna", cap=Decimal(1000))
        self.assertEqual([path for path, _ in self.service_posts], ["/user/new"])
        self.assertFalse(self.service_keys)
        self.assertNotIn("service_payer_id", self.valves["employee_budget_cost"])
        self.assertEqual(self.P.read_private(self.office_path)["service_fixture"]["stage"], "installing")

    def test_actual_workspace_creation_cannot_modify_protected_office_primary(self):
        def change(path, body):
            if path == "/api/v1/models/create": self.rows["gpt-5.4-mini"]["params"]["max_tokens"] = 9
        self.native_mutation = change
        with self.assertRaisesRegex(S.ProofError, "changed ordinary models"):
            self.install(target_model="gpt-6-luna", cap=Decimal(1000))
        self.assertNotIn("service_payer_id", self.valves["employee_budget_cost"])
        self.assertEqual(self.install_state["service_fixture"]["stage"], "installing")

    def test_changed_persisted_pipe_source_fails_existing_native_source_guard(self):
        def change(path, body):
            if path == "/api/v1/functions/create": self.functions[S.FUNCTION_ID]["content"] += "\n# foreign persisted source"
        self.native_mutation = change
        with self.assertRaisesRegex(S.ProofError, "native source/owner/activation"):
            self.install(target_model="gpt-6-luna", cap=Decimal(1000))
        self.assertEqual(self.install_state["service_fixture"]["stage"], "installing")
        self.assert_unchanged_context()


if __name__ == "__main__":
    unittest.main()
