"""Rehearse separate admin reporting costs against native-shaped artifacts."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_service_admin_browser as B


def packet():
    ids = [str(uuid4()) for _ in range(4)]
    admin, payer, chat, answer, parent = ids[0], *[str(uuid4()) for _ in range(4)]
    reset = "2026-12-01T00:00:00Z"
    users = [{"user_id": uid, "max_budget_usd": "1000" if uid == admin else "20",
              "spend_usd": "1.6" if uid == admin else ".2", "budget_duration": "1mo", "budget_reset_at": reset}
             for uid in ids]
    keys = [{"user_id": uid, "model": model, "key_alias": "fixture-" + uid + model,
             "max_budget_usd": "500" if uid == admin else "10", "spend_usd": "1.6" if uid == admin and model == "goal584-a"
              else ".2" if uid != admin and model == "goal584-a" else "0", "budget_duration": "1mo", "budget_reset_at": reset}
            for uid in ids for model in ("goal584-a", "goal584-b")]
    before = {"passed": True, "admin_id": admin, "service_payer_id": payer, "personal": {"users": users, "keys": keys},
              "service": {"users": [{"user_id": payer, "max_budget_usd": "20", "spend_usd": ".2",
                                     "budget_duration": "1mo", "budget_reset_at": reset}],
                          "keys": [{"user_id": payer, "model": "goal584-a", "key_alias": "service-assignment",
                                    "max_budget_usd": "20", "spend_usd": ".2", "budget_duration": "1mo", "budget_reset_at": reset}]},
              "positive_spend_logs": [{"request_id": "prior-positive-history"}]}
    after = copy.deepcopy(before)
    for collection in (after["personal"]["users"], after["personal"]["keys"]):
        for row in collection:
            if row["user_id"] == admin and row.get("model", "goal584-a") == "goal584-a":
                row["spend_usd"] = "2.0"
    opened = {"admin_id": admin, "parent_author_id": admin, "model_id": B.MODEL, "stored_parent_text": B.INTENT,
              "chat_id": chat, "assistant_id": answer, "parent_user_id": parent,
              "terminal_persisted": True, "exact_submitted_and_stored_strings": True, "sandbox_same_origin": False}
    context, provider = {"requests": []}, {"synthetic": True, "requests": []}
    skill, _, statuses = B.source_contract()
    schemas = [{"type": "function", "function": {"name": name, "description": "Native Tool",
                "parameters": {"type": "object", "properties": properties}}} for name, properties in (
        ("open_budget_form", {"view_json": {"type": "string", "default": "{}"}}), ("apply_budget_form", {}))]
    messages = [{"role": "system", "content": skill}, {"role": "user", "content": B.INTENT}]
    for index in range(2):
        if index:
            messages += [{"role": "assistant", "tool_calls": [{"id": "native-open", "type": "function",
                "function": {"name": "open_budget_form", "arguments": '{"view_json":"{}"}'}}]},
                {"role": "tool", "tool_call_id": "native-open", "content": json.dumps(statuses["opened"])}]
        body = {"model": "goal584-a", "messages": copy.deepcopy(messages), "stream": True, "max_tokens": 5,
                "tools": copy.deepcopy(schemas)}
        scope = {"schema": 1, "user_id": admin, "chat_id": chat, "answer_id": answer, "root_chat_id": chat,
                 "root_answer_id": answer, "model": "goal584-a", "call_id": str(uuid4()), "category": "personal"}
        captured = {"user_id": admin, "task": "", "verified_cost_scope": scope, "body": body,
                    "body_after_auth": copy.deepcopy(body), "attestation_present_before": True,
                    "provenance_removed_after": True, "native_stream_usage_patch": {
                        "stream_options": {"include_usage": True}, "_litellm_strip_stream_usage": True}}
        context["requests"].append(captured)
        request_id = "chatcmpl-goal584-" + uuid4().hex
        provider["requests"].append({"id": request_id, "body": {**copy.deepcopy(body), "model": "goal584-fake-a",
            "stream_options": {"include_usage": True}}, "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        after["positive_spend_logs"].append({"request_id": request_id, "user_id": admin, "model_group": "goal584-a",
            "session_id": chat, "owui_budget": scope, "spend_usd": ".2", "prompt_tokens": 10,
            "completion_tokens": 5, "total_tokens": 15})
    return [before, after, opened, context, provider]


class ServiceAdminViewTests(unittest.TestCase):
    def test_two_admin_calls_are_separate_from_unchanged_service_and_staff(self):
        result = B.verify_view(*packet())
        self.assertEqual(result["admin_reporting_cost_usd"], "0.40")
        self.assertEqual(result["service_spend_usd"], "0.20")
        self.assertTrue(result["reporting_billed_to_admin_personal_identity"])

    def reject(self, mutate):
        values = packet()
        mutate(values)
        with self.assertRaises((AssertionError, ValueError, KeyError)):
            B.verify_view(*values)

    def test_reject_service_or_staff_charge_caps_and_missing_admin_accounting(self):
        self.reject(lambda values: values[1]["service"]["users"][0].update(spend_usd=".4"))
        self.reject(lambda values: values[1]["personal"]["users"][1].update(spend_usd=".4"))
        self.reject(lambda values: values[1]["personal"]["keys"][0].update(max_budget_usd="999"))
        self.reject(lambda values: values[1]["personal"]["users"][0].update(spend_usd="1.6"))
        self.reject(lambda values: values[0]["personal"]["users"].pop())

    def test_reject_extra_provider_calls_or_wrong_identity_and_native_rows(self):
        self.reject(lambda values: values[4]["requests"].pop())
        self.reject(lambda values: values[1]["positive_spend_logs"].append(copy.deepcopy(values[1]["positive_spend_logs"][-1])))
        self.reject(lambda values: values[3]["requests"][0]["verified_cost_scope"].update(category="service"))
        self.reject(lambda values: values[3]["requests"][0]["verified_cost_scope"].update(root_chat_id=str(uuid4())))

    def test_reject_lost_skill_schema_instructions_or_business_arguments(self):
        self.reject(lambda values: values[4]["requests"][1]["body"].pop("tools"))
        def forge(values):
            for slot in ("body", "body_after_auth"):
                values[3]["requests"][1][slot]["messages"][-2]["tool_calls"][0]["function"]["arguments"] = '{"service_payer_id":"forged"}'
            values[4]["requests"][1]["body"]["messages"][-2]["tool_calls"][0]["function"]["arguments"] = '{"service_payer_id":"forged"}'
        self.reject(forge)


if __name__ == "__main__":
    unittest.main()
