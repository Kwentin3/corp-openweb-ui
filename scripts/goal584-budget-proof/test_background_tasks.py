"""Synthetic receipt mutations; no claim of native runtime or inference acceptance."""
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, ProxyHandler, build_opener
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
import prove_background_tasks as P
from prove_native_budgets import TOLERANCE


def identifier():
    return "chatcmpl-goal584-" + uuid4().hex


def packet():
    actor, payer, *others = [str(uuid4()) for _ in range(5)]
    chats = [{"chat_id": str(uuid4()), "answer_id": str(uuid4())} for _ in range(2)]
    chats[1].update(title="Proof", tags=["proof"], follow_ups=["Proof"])
    all_budgets = []
    for index, uid in enumerate([actor, payer, *others]):
        models = [P.MODELS[0]] if uid == payer else list(P.MODELS)
        keys = [{"model": model, "key_hash": format(index * 2 + number + 1, "064x"),
                 "key_alias": "owui-budget-v1-" + format(index * 2 + number + 1, "064x"),
                 "max_budget": "20", "spend": ".20" if uid == payer else "0", "blocked": False,
                 "budget_duration": "1mo", "budget_reset_at": "2026-12-01T00:00:00Z"}
                for number, model in enumerate(models)]
        all_budgets.append({"user_id": uid, "max_budget": "40" if uid != payer else "20",
            "spend": ".20" if uid == payer else "0", "budget_duration": "1mo",
            "budget_reset_at": "2026-12-01T00:00:00Z", "models": keys})
    def scope(task, chat):
        if task == "primary":
            return dict(schema=1, category="personal", user_id=actor, chat_id=chat["chat_id"],
                root_chat_id=chat["chat_id"], answer_id=chat["answer_id"], root_answer_id=chat["answer_id"],
                call_id=str(uuid4()), model=P.MODELS[0])
        return dict(schema=1, category="service", user_id=payer, actor_id=actor, chat_id=chat["chat_id"],
                    call_id=str(uuid4()), model=P.MODELS[0], task=task)
    def row(sc):
        budget = next(item for item in all_budgets if item["user_id"] == sc["user_id"])
        return dict(request_id=identifier(), user_id=sc["user_id"], key_hash=budget["models"][0]["key_hash"],
                    model=P.MODELS[0], session_id=("owui-service:" if sc["category"] == "service" else "") + sc["chat_id"],
                    status="success", spend_usd=".20", usage=copy.deepcopy(P.USAGE), scope=copy.deepcopy(sc))
    historical = row(scope("title_generation", {"chat_id": str(uuid4())}))
    before = dict(budgets=copy.deepcopy(all_budgets), rows=[historical],
                  unqualified_zero_request_ids={budget["user_id"]: [] for budget in all_budgets},
                  models={P.MODELS[0]: {"params": {"max_tokens": 5}}})
    left, right, physical, added = [], [], [], []
    for task in ("primary", *P.TASKS):
        content = "Hi" if task == "primary" else (
            "Native title instruction\n<chat_history>\nUSER: Hi\nASSISTANT:\n</chat_history>" if task == "title_generation"
            else "Native " + task + " instruction: USER: Hi\nASSISTANT: Proof")
        body = {"model": P.MODELS[0], "messages": [{"role": "system", "content": "Native target owner instruction"},
                {"role": "user", "content": content}], "stream": task == "primary", "max_tokens": 5,
                "temperature": 0, "top_p": .8, "tools": [{"type": "function", "function": {
                    "name": "native_owner_schema", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}}}}],
                "tool_choice": "none"}
        if task != "primary":
            body["response_format"] = {"type": "json_object"}
        a = {"user_id": actor, "task": "" if task == "primary" else task, "body": copy.deepcopy(body),
             "body_after_auth": copy.deepcopy(body), "attestation_present_before": task == "primary",
             "provenance_removed_after": True}
        b = copy.deepcopy(a)
        b["attestation_present_before"] = True
        if task != "primary":
            a["auth_failure"] = {"scope": "custom_auth", "status_code": 403, "code": "invalid_signed_budget_provenance"}
        for index, context in enumerate((a, b) if task == "primary" else (b,)):
            sc = scope(task, chats[index] if task == "primary" else chats[1])
            context.update(verified_cost_scope=sc, native_auth_user_id=sc["user_id"],
                           native_stream_usage_patch={"stream_options": {"include_usage": True}} if task == "primary" else {})
            native = row(sc)
            added.append(native)
            wire = {**copy.deepcopy(body), **context["native_stream_usage_patch"], "model": "goal584-fake-a"}
            if task != "primary":
                wire.pop("stream")
            request = {"id": native["request_id"], "body": wire, "usage": copy.deepcopy(P.USAGE),
                       "lifecycle": {"terminal": True, "outcome": "completed", "started_monotonic": 1,
                                     "terminal_monotonic": 5 if task == "primary" else 3}}
            if task != "primary":
                request["response"] = {"id": request["id"], "model": "goal584-fake-a", "usage": copy.deepcopy(P.USAGE),
                    "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(P.UNION)}}]}
            physical.append(request)
        left.append(a)
        right.append(b)
    after = copy.deepcopy(before)
    after["rows"].extend(copy.deepcopy(added))
    for budget in after["budgets"]:
        if budget["user_id"] in (actor, payer):
            budget["spend"] = ".40" if budget["user_id"] == actor else ".80"
            budget["models"][0]["spend"] = budget["spend"]
    return SimpleNamespace(actor=actor, payer=payer, chats=chats, before=before, after=after,
                           left=left, right=right, physical=physical, added=added)


def saved(chat, actor, *, signed):
    uid = str(uuid4())
    return {"id": chat["chat_id"], "user_id": actor, "title": "Proof" if signed else "Hi",
        "meta": {"tags": ["proof"] if signed else []}, "chat": {"history": {"messages": {
            uid: {"id": uid, "role": "user", "content": "Hi", "parentId": None},
            chat["answer_id"]: {"id": chat["answer_id"], "parentId": uid, "role": "assistant", "done": True,
                "model": P.MODELS[0], "content": "Proof", "followUps": ["Proof"] if signed else [],
                "statusHistory": [{"action": "employee_budget_cost", "description": "Ответ: $0.20 · Чат: $0.20"}]},
        }}}}


def float_packet(prior_count, native_before, native_after):
    """Exact .20 historical rows with native binary-Float scalar counters."""
    value=packet()
    for _ in range(prior_count):
        historical=copy.deepcopy(value.added[0])
        historical["request_id"]=identifier()
        chat_id,answer_id=str(uuid4()),str(uuid4())
        historical["scope"].update(chat_id=chat_id,root_chat_id=chat_id,answer_id=answer_id,
                                   root_answer_id=answer_id,call_id=str(uuid4()))
        historical["session_id"]=chat_id
        value.before["rows"].append(historical)
    value.after["rows"]=copy.deepcopy(value.before["rows"]+value.added)
    for snapshot,counter in ((value.before,native_before),(value.after,native_after)):
        budget=next(item for item in snapshot["budgets"] if item["user_id"] == value.actor)
        budget["spend"]=counter
        budget["models"][0]["spend"]=counter
    service=next(item for item in value.after["budgets"] if item["user_id"] == value.payer)
    service["spend"]="0.8000000000000001"
    service["models"][0]["spend"]="0.7999999999999999"
    return value


class ContextTests(unittest.TestCase):
    def verify(self, value):
        return P.verify_context(value.left, value.right, value.physical, value.added, value.actor, value.payer, value.chats)

    def test_full_synthetic_packet_preserves_native_system_tools_params_and_separate_authorities(self):
        value = packet()
        added = P.verify_finance(value.before, value.after, value.actor, value.payer, primary_count=2, service_count=3)
        self.assertEqual({row["request_id"] for row in added}, {row["request_id"] for row in value.added})
        result = self.verify(value)
        self.assertEqual((result["physical_calls"], result["service_cost_usd"], result["total_cost_usd"]), (5, "0.60", "1.00"))
        self.assertEqual(result["initial_title_history"], "USER: Hi\nASSISTANT:")

    def test_context_mutations_cannot_drop_instructions_schema_params_or_provider_fields(self):
        mutations = [lambda v:v.right[1]["body"]["messages"][0].update(content="Changed system"),
                     lambda v:v.right[2]["body"].pop("tools"),
                     lambda v:v.right[1]["body_after_auth"].update(temperature=.5),
                     lambda v:v.physical[-1]["body"].update(top_p=.7),
                     lambda v:v.physical[-1]["body"].update(stream=False),
                     lambda v:v.physical[-1]["body"].update(litellm_metadata={"private": "value"}),
                     lambda v:v.chats[1].update(follow_ups=["Wrong"]),
                     lambda v:v.physical[-1]["response"]["choices"][0]["message"].update(content='{"title":"Wrong"}')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = packet(); mutate(value)
                with self.assertRaises((P.ProofError, ValueError)):
                    self.verify(value)

    def test_native_internal_stream_patch_is_projected_through_the_same_semantic_owner(self):
        value=packet()
        for context in (value.left[0],value.right[0]):
            context["native_stream_usage_patch"]["_litellm_strip_stream_usage"]=True
        self.assertTrue(self.verify(value)["full_baseline_service_provider_context_equal"])
        value.physical[1]["body"]["stream_options"]={"include_usage":False}
        with self.assertRaisesRegex(P.ProofError,"provider full semantic context"):
            self.verify(value)

    def test_wrong_guard_payer_chat_nonce_missing_task_and_native_id_are_rejected(self):
        mutations = [lambda v:v.left[1]["auth_failure"].update(status_code=500),
                     lambda v:v.left[2]["auth_failure"].update(code="unclassified"),
                     lambda v:v.right[1]["verified_cost_scope"].update(actor_id=v.payer),
                     lambda v:v.right[1]["verified_cost_scope"].update(chat_id=v.chats[0]["chat_id"]),
                     lambda v:v.right[2]["verified_cost_scope"].update(call_id=v.right[1]["verified_cost_scope"]["call_id"]),
                     lambda v:v.right[1]["verified_cost_scope"].update(answer_id=str(uuid4())),
                     lambda v:v.right.pop(), lambda v:v.added[-1].update(request_id=identifier())]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = packet(); mutate(value)
                with self.assertRaises((P.ProofError, ValueError)):
                    self.verify(value)

    def test_initial_title_requires_observed_pre_output_history_and_observed_arrival_before_primary_terminal(self):
        for late_history in (False, True):
            value = packet()
            if late_history:
                for context in (value.left[1], value.right[1]):
                    for key in ("body", "body_after_auth"):
                        context[key]["messages"][1]["content"] += "\nNot used"
                for context in (value.left[1], value.right[1]):
                    for key in ("body", "body_after_auth"):
                        context[key]["messages"][1]["content"] = context[key]["messages"][1]["content"].replace("ASSISTANT:", "ASSISTANT: Proof")
                value.physical[2]["body"] = copy.deepcopy(value.right[1]["body"])
                value.physical[2]["body"].update(model="goal584-fake-a")
                value.physical[2]["body"].pop("stream")
            else:
                value.physical[2]["lifecycle"]["started_monotonic"] = 6
            with self.assertRaises(P.ProofError):
                self.verify(value)


class FinanceSavedTests(unittest.TestCase):
    def test_native_row_projection_validates_real_scope_and_exact_native_assignment_session(self):
        value=packet(); projected=value.added[-1]
        budget=SimpleNamespace(user_id=value.payer, models=[SimpleNamespace(model=P.MODELS[0], key_hash=projected["key_hash"])])
        raw={"request_id": projected["request_id"], "user": value.payer, "api_key": projected["key_hash"],
             "model_group": P.MODELS[0], "session_id": projected["session_id"], "status": "success", "spend": .2,
             **P.USAGE, "metadata": json.dumps({"spend_logs_metadata": {"owui_budget": projected["scope"]}})}
        self.assertEqual(P.project_row(raw,budget)["scope"],projected["scope"])
        for mutate in [lambda r:r.update(api_key="wrong-key"), lambda r:r.update(session_id=value.chats[1]["chat_id"]),
                       lambda r:r.update(status="failure"), lambda r:r.update(user=value.actor)]:
            changed=copy.deepcopy(raw);mutate(changed)
            with self.assertRaises(P.ProofError):P.project_row(changed,budget)

    def test_settlement_waits_for_native_counters_after_completed_provider_responses(self):
        value=float_packet(14,"2.8000000000000003","3.2"); lagged=copy.deepcopy(value.after)
        next(b for b in lagged["budgets"] if b["user_id"] == value.payer)["spend"]=".60"
        state={"users": [{"id": value.actor, "token": "synthetic-session"}],
               "service_fixture": {"payer_id": value.payer}, "background_fixture": {"before": value.before}}
        calls=[]
        class Native:
            def poll(self,label,condition):
                self.label=label
                if condition() is not None:raise AssertionError("Unsettled counters accepted")
                result=condition()
                if result is None:raise AssertionError("Settled counters not accepted")
                return result
        def response(webui,method,path,token):
            calls.append((method,path))
            if path.startswith("/api/tasks/chat/"):return 200,{"task_ids":[]}
            return 200,saved(value.chats[1],value.actor,signed=True)
        with patch.object(P,"capture_state",return_value={"requests":value.left+value.right}), \
             patch.object(P,"provider",return_value={"synthetic":True,"requests":value.physical}), \
             patch.object(P,"snapshot",side_effect=[lagged,value.after]) as observe, \
             patch.object(P,"native_client",return_value=Native()), patch.object(P,"response",side_effect=response):
            result=P.observe(object(),state,value.chats[1]["chat_id"],value.chats[1]["answer_id"],signed=True)
        self.assertEqual(observe.call_count,2)
        self.assertEqual(result[-1]["title"],"Proof")
        self.assertTrue(all(method == "GET" for method,path in calls))

    def test_binary_float_counter_rounding_preserves_exact_ledger_and_positive_delta_contract(self):
        for count,before,after in ((14,"2.8000000000000003","3.2"),
                                   (1,".2","0.6000000000000001"),
                                   (1,"0.20000000000000004","0.5999999999999999")):
            with self.subTest(before=before,after=after):
                value=float_packet(count,before,after)
                added=P.verify_finance(value.before,value.after,value.actor,value.payer,primary_count=2,service_count=3)
                self.assertEqual(len(added),5)
                self.assertTrue(all(Decimal(row["spend_usd"]) == Decimal(".20") for row in added))
                self.assertTrue(P.counter_ready(after,before,Decimal(".40")))

    def test_tolerance_does_not_accept_cent_extra_call_or_tiny_unchanged_model_b_mutations(self):
        for field,change in (("user",".01"),("user","-.01"),("user",".20"),("key",".01"),("zero_b","0.00000000000001"),
                             ("other_user","0.00000000000001"),("ledger","0.00000000000001")):
            with self.subTest(field=field,change=change):
                value=float_packet(1,".2","0.6000000000000001")
                actor=next(item for item in value.after["budgets"] if item["user_id"] == value.actor)
                if field == "user":actor["spend"]=str(Decimal(actor["spend"])+Decimal(change))
                elif field == "key":actor["models"][0]["spend"]=str(Decimal(actor["models"][0]["spend"])+Decimal(change))
                elif field == "zero_b":actor["models"][1]["spend"]=change
                elif field == "other_user":next(item for item in value.after["budgets"] if item["user_id"] not in (value.actor,value.payer))["spend"]=change
                else:value.after["rows"][-1]["spend_usd"]=str(Decimal(".20")+Decimal(change))
                with self.assertRaises(P.ProofError):
                    P.verify_finance(value.before,value.after,value.actor,value.payer,primary_count=2,service_count=3)

    def test_settlement_gate_distinguishes_rounding_pending_and_overpayment_without_waiting(self):
        self.assertTrue(P.counter_ready("0.6000000000000001",".2",Decimal(".4")))
        self.assertTrue(P.counter_ready("0.5999999999999999",".2",Decimal(".4")))
        self.assertTrue(P.counter_ready(str(Decimal(".6")+TOLERANCE),".2",Decimal(".4")))
        self.assertTrue(P.counter_ready(str(Decimal(".6")-TOLERANCE),".2",Decimal(".4")))
        self.assertFalse(P.counter_ready(".4",".2",Decimal(".4")))
        for actual,previous,delta in ((".61",".2",Decimal(".4")),(".8",".2",Decimal(".4")),
                                      (str(Decimal(".6")+TOLERANCE*2),".2",Decimal(".4")),
                                      ("0.00000000000001","0",Decimal(0))):
            with self.subTest(actual=actual),self.assertRaises(P.ProofError):
                P.counter_ready(actual,previous,delta)

    def test_pending_counter_does_not_mask_another_counter_exceeding_expected_spend(self):
        value=packet(); lagged=copy.deepcopy(value.after)
        next(item for item in lagged["budgets"] if item["user_id"] == value.actor)["spend"]=".2"
        next(item for item in lagged["budgets"] if item["user_id"] == value.payer)["spend"]=".81"
        # Even while a native ledger row has not arrived, a known excess must
        # fail in the first settlement condition, rather than become pending.
        lagged["rows"].pop()
        state={"users":[{"id":value.actor,"token":"synthetic-session"}],
               "service_fixture":{"payer_id":value.payer},"background_fixture":{"before":value.before}}
        class Native:
            def poll(self,label,condition):return condition()
        with patch.object(P,"capture_state",return_value={"requests":value.left+value.right}), \
             patch.object(P,"provider",return_value={"synthetic":True,"requests":value.physical}), \
             patch.object(P,"snapshot",return_value=lagged) as observed, \
             patch.object(P,"native_client",return_value=Native()), \
             patch.object(P,"response",return_value=(200,{"task_ids":[]})):
            with self.assertRaisesRegex(P.ProofError,"exceeded expected spend"):
                P.observe(object(),state,value.chats[1]["chat_id"],value.chats[1]["answer_id"],signed=True)
        self.assertEqual(observed.call_count,1)

    def test_only_two_personal_and_three_service_rows_change_actual_scalar_counters(self):
        for mutate in [lambda v:v.after["budgets"][0].update(spend=".60"),
                       lambda v:v.after["budgets"][1]["models"][0].update(max_budget="40"),
                       lambda v:v.after["budgets"][1]["models"][0].update(budget_reset_at="2027-01-01T00:00:00Z"),
                       lambda v:v.after["budgets"][0]["models"][1].update(spend=".20"),
                       lambda v:v.after["rows"][0].update(spend_usd=".10"),
                       lambda v:v.after["rows"].pop(0),
                       lambda v:v.after["models"][P.MODELS[0]]["params"].update(max_tokens=6)]:
            with self.subTest(mutation=mutate):
                value=packet();mutate(value)
                with self.assertRaises(P.ProofError):
                    P.verify_finance(value.before, value.after, value.actor, value.payer, primary_count=2, service_count=3)

    def test_native_saved_title_normalized_tag_followup_and_cost_must_all_match(self):
        value = packet()
        for signed, chat in enumerate(value.chats):
            actual = saved(chat, value.actor, signed=bool(signed))
            evidence = P.saved_evidence(actual, value.actor, chat["chat_id"], chat["answer_id"], signed=bool(signed))
            self.assertEqual(evidence["tags"], ["proof"] if signed else [])
        mutations = [lambda c:c.update(title="Wrong"), lambda c:c["meta"].update(tags=["Proof"]),
                     lambda c:c.update(user_id=str(uuid4())),
                     lambda c:c["chat"]["history"]["messages"][value.chats[1]["answer_id"]].update(followUps=[]),
                     lambda c:c["chat"]["history"]["messages"][value.chats[1]["answer_id"]]["statusHistory"][0].update(description="Ответ: $0.80 · Чат: $0.80")]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                actual=saved(value.chats[1], value.actor, signed=True);mutate(actual)
                with self.assertRaises(P.ProofError):
                    P.saved_evidence(actual, value.actor, value.chats[1]["chat_id"], value.chats[1]["answer_id"], signed=True)

    def test_config_changes_only_selectors_between_phases_and_restores_unknown_fields_exactly(self):
        original = {**{flag: False for flag in P.TASK_FLAGS}, "TASK_MODEL": "original",
                    "TASK_MODEL_EXTERNAL": None, "TASK_MODEL_PARAMS": {}, "future_owner_field": {"nested": [1, 2]}}
        current = copy.deepcopy(original)
        class WebUI:
            def session(self, admin, role):
                self.assert_role = role
            def ok(self, method, path, **kwargs):
                nonlocal current
                if method == "POST":current=copy.deepcopy(kwargs["body"])
                return copy.deepcopy(current)
        webui = WebUI()
        state = {"admin": {"token": "synthetic", "id": str(uuid4())}, "users": [{"id": str(uuid4())}],
                 "service_fixture": {"payer_id": str(uuid4())}, "background_fixture": {
                     "original_task_config": copy.deepcopy(original), "original_provider_control": {"delay_ms":0},
                     "stage": "events_verified", "pipe_sha256": "a" * 64}}
        baseline = P.configure(webui, state, P.MODELS[0])
        service = P.configure(webui, state, P.FUNCTION_ID)
        self.assertEqual({key:value for key,value in baseline.items() if key not in ("TASK_MODEL", "TASK_MODEL_EXTERNAL")},
                         {key:value for key,value in service.items() if key not in ("TASK_MODEL", "TASK_MODEL_EXTERNAL")})
        self.assertEqual({flag:current[flag] for flag in P.TASK_FLAGS}, {flag:flag in P.TASK_ENABLES for flag in P.TASK_FLAGS})
        with patch.object(P, "write_private"), patch.object(P,"provider",return_value={"control":{"delay_ms":0}}):
            result=P.run_phase(webui, state, SimpleNamespace(phase="restore", private_state=Path("unused")))
        self.assertEqual(current, original)
        self.assertTrue(result["task_config_restored"])
        self.assertTrue(result["provider_controls_restored"])
        self.assertEqual(result["stage"], "qualified_automatic_background")

    def test_provider_restore_failure_does_not_skip_or_mislabel_successful_native_config_restore(self):
        original={"TASK_MODEL":"original"}
        calls=[]
        class WebUI:
            def session(self,*args):pass
            def ok(self,method,path,**kwargs):
                calls.append((method,path))
                return original
        for failure in ("write", "readback"):
            fixture={"original_task_config":copy.deepcopy(original),"original_provider_control":{"delay_ms":0}}
            with self.subTest(failure=failure):
                with patch.object(P,"provider",side_effect=P.ProofError("Fixed failure") if failure=="write" else None,
                                  return_value={"control":{"delay_ms":1500}}):
                    with self.assertRaisesRegex(P.ProofError,"provider_controls"):
                        P.restore_controls(WebUI(),{"admin":{"token":"synthetic"},"background_fixture":fixture})
                self.assertTrue(fixture["task_config_restored"])
                self.assertFalse(fixture["provider_controls_restored"])
        self.assertEqual(sum(method=="POST" for method,path in calls),2)

    def test_actual_http_provider_restores_exact_controls_and_keeps_receipts_after_native_restore_failure(self):
        import mock_provider as provider_owner
        import prove_service_tasks as service_owner
        server=ThreadingHTTPServer(("127.0.0.1",0),provider_owner.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        class WebUI:
            def session(self,*args):raise P.ProofError("Fixed native restore failure")
        try:
            with patch.object(service_owner,"PROVIDER_URL","http://127.0.0.1:"+str(server.server_port)):
                P.provider("POST","/__proof/reset",{})
                P.provider("POST","/__proof/control",{"response_status":200})
                original=copy.deepcopy(P.provider()["control"])
                body={"model":"goal584-fake-a","messages":[{"role":"user","content":"Hi"}]}
                request=Request(service_owner.PROVIDER_URL+"/v1/chat/completions",data=json.dumps(body).encode(),
                                headers={"Content-Type":"application/json"})
                with build_opener(ProxyHandler({})).open(request,timeout=3) as result:
                    identifier=json.load(result)["id"]
                deadline=time.monotonic()+3
                while True:
                    receipts=P.provider()["requests"]
                    if len(receipts)==1 and receipts[0]["id"]==identifier and receipts[0]["lifecycle"]["terminal"]:break
                    self.assertLess(time.monotonic(),deadline)
                    threading.Event().wait(.005)
                P.provider("POST","/__proof/control",{"native_tasks_mode":True,"delay_ms":1500,
                                                       "after_first_chunk_delay_ms":10000})
                fixture={"original_task_config":{},"original_provider_control":original}
                with self.assertRaisesRegex(P.ProofError,"task_config"):
                    P.restore_controls(WebUI(),{"admin":{"token":"synthetic"},"background_fixture":fixture})
                self.assertFalse(fixture["task_config_restored"])
                self.assertTrue(fixture["provider_controls_restored"])
                after=P.provider()
                self.assertEqual(after["control"],original)
                self.assertEqual(after["requests"],receipts)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
