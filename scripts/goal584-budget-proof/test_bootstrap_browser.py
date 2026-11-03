"""Actual-artifact-shaped bootstrap rehearsal; no browser/native/provider calls."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_bootstrap_browser as B
import verify_bootstrap_calls as V
import mock_provider as P
from verify_admin_calls import PHYSICAL, source_contract


def packet():
    admin, employee, chat = [str(uuid4()) for _ in range(3)]
    skill, intent, results = source_contract()
    template = {"schema": 1, "type": "employee_budget_template", "expected_revision": "a" * 64,
                "budget_usd": "0.8", "shares": {B.MODELS[0]: "100", B.MODELS[1]: "0"}, "budget_duration": "1mo"}
    initialize = {"schema": 1, "type": "employee_budget_initialize", "changes": [{"user_id": employee,
        "expected_revision": "b" * 64, "budget_usd": "0.8", "shares": template["shares"]}]}
    absent = {"kind": "absent", "user_id": employee, "code": "missing_native_user"}
    def state(spend):
        return {"kind": "ready", "user_id": employee, "code": None,
            "users": [{"user_id": employee, "max_budget_usd": "0.8", "spend_usd": spend,
                       "budget_duration": "1mo", "budget_reset_at": "2026-12-01T00:00:00Z"}],
            "keys": [{"user_id": employee, "model": model, "key_alias": "synthetic-" + model,
                      "max_budget_usd": "0.8" if i == 0 else "0", "spend_usd": spend if i == 0 else "0",
                      "budget_duration": "1mo", "budget_reset_at": "2026-12-01T00:00:00Z"}
                     for i, model in enumerate(B.MODELS)]}
    serialize = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    texts = [intent, serialize(template), serialize(initialize), serialize(initialize)]
    browser = {"passed": True, "admin_id": admin, "employee_id": employee, "model_id": "goal584-budget-admin",
        "template_proposal": template, "initialization_proposal": initialize, "calls": [],
        "canceled_native_identity_absent": True, "existing_employee_native_state_unchanged": True,
        "baseline_positive_request_ids": ["old-native"], "native_snapshots": {"before": absent,
            "template": copy.deepcopy(absent), "canceled": copy.deepcopy(absent), "created": state("0"), "final": state(".20")}}
    labels = ("opened", "template_saved", "canceled", "initialized")
    for label, text in zip(labels, texts):
        browser[label] = {"admin_id": admin, "parent_author_id": admin, "model_id": browser["model_id"],
            "chat_id": chat, "assistant_id": str(uuid4()), "parent_user_id": str(uuid4()), "stored_parent_text": text,
            "exact_submitted_and_stored_strings": True, "terminal_persisted": True, "sandbox_same_origin": False}
    provider, context, rows = {"synthetic": True, "requests": []}, {"requests": []}, []
    schemas = [{"type": "function", "function": {"name": name, "description": "Native Tool description",
                "parameters": {"type": "object", "properties": properties}}} for name, properties in (
        ("open_budget_form", {"view_json": {"type": "string", "default": "{}"}}), ("apply_budget_form", {}))]
    def add(owner, model, chat_id, answer, messages, *, completed=True, tools=None):
        scope = {"schema": 1, "user_id": owner, "chat_id": chat_id, "answer_id": answer, "root_chat_id": chat_id,
                 "root_answer_id": answer, "model": model, "call_id": str(uuid4()), "category": "personal"}
        body = {"model": model, "messages": copy.deepcopy(messages), "stream": True, "max_tokens": 5}
        if tools is not None:
            body["tools"] = copy.deepcopy(tools)
        captured = {"user_id": owner, "task": "", "body": body, "body_after_auth": copy.deepcopy(body),
                    "verified_cost_scope": scope, "attestation_present_before": True, "provenance_removed_after": True}
        context["requests"].append(captured)
        if completed:
            captured["native_stream_usage_patch"] = {"stream_options": {"include_usage": True}, "_litellm_strip_stream_usage": True}
            identifier = "bootstrap-rehearsal-" + uuid4().hex
            physical = copy.deepcopy(body)
            physical.update(model=PHYSICAL[model], stream_options={"include_usage": True})
            provider["requests"].append({"id": identifier, "body": physical,
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
            rows.append({"request_id": identifier, "user_id": owner, "session_id": chat_id, "model_group": model,
                         "owui_budget": scope, "spend_usd": ".2", "prompt_tokens": 10,
                         "completion_tokens": 5, "total_tokens": 15})
    history = [{"role": "system", "content": skill}]
    statuses = [results["opened"], results["applied"], results["canceled"], results["applied"]]
    for i, label in enumerate(labels):
        history.append({"role": "user", "content": texts[i]})
        add(admin, B.MODELS[0], chat, browser[label]["assistant_id"], history, tools=schemas)
        call_id = "bootstrap-call-" + uuid4().hex
        history.extend([{"role": "assistant", "tool_calls": [{"id": call_id, "type": "function", "function": {
            "name": "open_budget_form" if i == 0 else "apply_budget_form",
            "arguments": serialize({"view_json": "{}"} if i == 0 else {})}}]},
            {"role": "tool", "tool_call_id": call_id, "content": serialize(statuses[i])}])
        add(admin, B.MODELS[0], chat, browser[label]["assistant_id"], history, tools=schemas)
        history.append({"role": "assistant", "content": "Proof"})
    for model, completed in ((B.MODELS[0], True), (B.MODELS[1], False)):
        chat_id, answer = str(uuid4()), str(uuid4())
        browser["calls"].append({"user_id": employee, "model": model, "chat_id": chat_id, "message_id": answer,
                                 "outcome": "success" if completed else "budget_blocked", "terminal_persisted": True})
        add(employee, model, chat_id, answer, [{"role": "user", "content": "Hi"}], completed=completed)
    previous_staff = [str(uuid4()), str(uuid4())]
    rows.append({"request_id": "old-native", "user_id": previous_staff[0], "model_group": B.MODELS[0], "spend_usd": ".2"})
    native = {"passed": True, "existing_employee_native_state_unchanged": True, "attributed_spend_logs": rows,
              "baseline_positive_request_ids": ["old-native"], "bootstrap": copy.deepcopy(browser["native_snapshots"]["final"]),
              "default_template": {key: template[key] for key in ("budget_usd", "shares", "budget_duration")},
              "employee_function_valves_get_status": 401}
    def counters(owners):
        return {"users": [{"user_id": uid, "spend_usd": str(sum((Decimal(row["spend_usd"]) for row in rows
                                      if row["user_id"] == uid), Decimal(0)))} for uid in owners],
                "keys": [{"user_id": uid, "model": model, "spend_usd": str(sum((Decimal(row["spend_usd"]) for row in rows
                                      if row["user_id"] == uid and row["model_group"] == model), Decimal(0)))}
                         for uid in owners for model in B.MODELS]}
    native.update(counters(previous_staff))
    native["admin_accounting"] = counters([admin])
    return [browser, provider, context, native]


class BootstrapTests(unittest.TestCase):
    def test_native_shaped_phase_is_independent_nine_calls_ten_attempts(self):
        result = V.verify(*packet())
        self.assertTrue(result["passed"])
        self.assertEqual((result["physical_calls"], result["signed_attempts"]), (9, 10))

    def reject(self, mutate):
        data = packet()
        mutate(data)
        with self.assertRaises((AssertionError, KeyError, ValueError)):
            V.verify(*data)

    def test_reject_provider_native_and_identity_corruption(self):
        self.reject(lambda data: data[1]["requests"].pop())
        self.reject(lambda data: data[2]["requests"].pop())
        self.reject(lambda data: data[3]["attributed_spend_logs"].pop())
        self.reject(lambda data: data[3]["attributed_spend_logs"][0].update(user_id=str(uuid4())))
        self.reject(lambda data: data[2]["requests"][0]["verified_cost_scope"].update(root_answer_id=str(uuid4())))
        self.reject(lambda data: data[3]["bootstrap"]["keys"][0].update(max_budget_usd="1"))
        self.reject(lambda data: data[3]["default_template"]["shares"].update({B.MODELS[1]: "1"}))
        self.reject(lambda data: data[3].update(existing_employee_native_state_unchanged=False))
        self.reject(lambda data: data[3].update(employee_function_valves_get_status=200))
        self.reject(lambda data: data[3]["admin_accounting"]["users"][0].update(spend_usd="0"))
        self.reject(lambda data: data[0]["native_snapshots"]["canceled"].update(kind="ready"))

    def test_reject_consistently_forged_model_context(self):
        for replacement in ("truncated", "sk-" + "x" * 32, "<!doctype html><main>form</main>"):
            def mutate(data):
                for key in ("body", "body_after_auth"):
                    data[2]["requests"][0][key]["messages"][0]["content"] = replacement
                data[1]["requests"][0]["body"]["messages"][0]["content"] = replacement
            self.reject(mutate)
        def arguments(data):
            for key in ("body", "body_after_auth"):
                data[2]["requests"][3][key]["messages"][-2]["tool_calls"][0]["function"]["arguments"] = '{"budget_usd":"999"}'
            data[1]["requests"][3]["body"]["messages"][-2]["tool_calls"][0]["function"]["arguments"] = '{"budget_usd":"999"}'
        self.reject(arguments)

    def test_newhire_projection_checks_real_caps_and_calendar(self):
        native = packet()[3]
        uid = native["bootstrap"]["user_id"]
        B.verify_newhire(native, uid, spend=Decimal(".20"))
        for field, value in (("max_budget_usd", ".1"), ("spend_usd", ".4"), ("budget_duration", "30d"),
                             ("budget_reset_at", "2027-01-01T00:00:00Z")):
            changed = copy.deepcopy(native)
            changed["bootstrap"]["keys"][0][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                B.verify_newhire(changed, uid, spend=Decimal(".20"))

    def test_bootstrap_envelope_and_missing_only_plan(self):
        data = {"template": {"revision": "a" * 64}, "pending": [{"user_id": "new-user", "state": "absent",
            "revision": "b" * 64, "models": [{"id": model} for model in B.MODELS]}]}
        html = '<script id="budget-bootstrap-data">' + json.dumps(data) + '</script>'
        self.assertEqual(B.bootstrap_data(html), data)
        self.assertEqual(B.initialize_plan(data, "new-user")["type"], "employee_budget_initialize")
        self.assertEqual(B.template_plan(data)["budget_duration"], "1mo")
        for kind in ("incomplete", "conflict", "ready"):
            data["pending"][0]["state"] = kind
            with self.assertRaises(AssertionError):
                B.initialize_plan(data, "new-user")
        with self.assertRaises(AssertionError):
            B.bootstrap_data(html + html)

    def test_synthetic_provider_routes_new_json_types_with_empty_arguments(self):
        schemas = [{"type": "function", "function": {"name": "employee_budget_admin_" + name}}
                   for name in ("open_budget_form", "apply_budget_form")]
        source = packet()[0]
        for proposal in (source["template_proposal"], source["initialization_proposal"]):
            self.assertEqual(P.pending_admin_tool({"tools": schemas}, [{"role": "user", "content": json.dumps(proposal)}]),
                             ("employee_budget_admin_apply_budget_form", {}))
        self.assertIsNone(P.pending_admin_tool({"tools": schemas}, [{"role": "user", "content": '{"schema":1,"type":"other"}'}]))


if __name__ == "__main__":
    unittest.main()
