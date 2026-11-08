"""Rehearse separate admin reporting costs against native-shaped artifacts."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
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
              "positive_spend_logs": [{"request_id": "chatcmpl-goal584-" + uuid4().hex, "user_id": uid,
                                       "model_group": "goal584-a", "spend_usd": ".2"}
                                      for uid in ids for _ in range(8 if uid == admin else 1)]}
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
    def snapshots(self, observations, expected_rows):
        with tempfile.TemporaryDirectory() as directory:
            fixture = object.__new__(B.ServiceAdminFixture)
            fixture.sequence, fixture.command, fixture.output = 0, ["native-compose"], Path(directory)
            responses = [subprocess.CompletedProcess([], 0, json.dumps(value), "") for value in observations]
            with patch.object(B.subprocess, "run", side_effect=responses) as run, patch.object(B.time, "sleep"):
                result = fixture.snapshot(expected_rows=expected_rows)
            retained = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(Path(directory).glob("service-admin-native-*.json"))]
            return result, retained, run.call_args_list

    def test_footer_snapshot_waits_for_counter_convergence_with_all_four_histories_retained(self):
        _, complete, *_ = packet()
        pending = copy.deepcopy(complete)
        admin = complete["admin_id"]
        for collection in (pending["personal"]["users"], pending["personal"]["keys"]):
            for row in collection:
                if row["user_id"] == admin and row.get("model", "goal584-a") == "goal584-a": row["spend_usd"] = "1.6"
        result, retained, calls = self.snapshots([pending, complete], len(complete["positive_spend_logs"]))
        self.assertEqual(result, complete)
        self.assertEqual(retained, [pending, complete])
        self.assertEqual({row["user_id"] for row in result["positive_spend_logs"]}, {row["user_id"] for row in complete["personal"]["users"]})
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(0 < call.kwargs["timeout"] <= 60 for call in calls))

    def test_footer_snapshot_waits_for_missing_journal_rows_before_classifying_surplus(self):
        _, complete, *_ = packet()
        pending = copy.deepcopy(complete); pending["positive_spend_logs"].pop()
        result, retained, _ = self.snapshots([pending, complete], len(complete["positive_spend_logs"]))
        self.assertEqual(result, complete); self.assertEqual(len(retained), 2)

    def test_footer_snapshot_does_not_wait_on_surplus_duplicate_or_missing_identity(self):
        _, complete, *_ = packet()
        for mutate in (lambda value: value["personal"]["users"][0].update(spend_usd="3"),
                       lambda value: value["positive_spend_logs"].append(copy.deepcopy(value["positive_spend_logs"][0])),
                       lambda value: value["personal"]["keys"].pop()):
            changed = copy.deepcopy(complete); mutate(changed)
            with self.subTest(mutation=mutate), self.assertRaises(AssertionError):
                self.snapshots([changed], len(complete["positive_spend_logs"]))

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


def unknown_packet():
    actor, admin = str(uuid4()), str(uuid4())
    from verify_admin_calls import literal
    aliases = literal(HERE / "prove_unknown_usage_policy.py", "ALIASES")
    accounts = {"schema": 1, "admin": {"id": admin}, "actor_id": actor, "employee_ids": [actor],
        "model_id": B.MODEL, "tool_id": "employee_budget_admin", "skill_id": "goal584-budget-admin-guide",
        "managed_model_ids": list(aliases)}
    actor_row = {"user_id": actor, "expense_status": "unknown", "spend_usd": ".332", "models": [
        {"id": alias, "spend_usd": ".332" if index == 0 else "0",
         "expense_status": "unavailable" if index == 0 else "unknown"} for index, alias in enumerate(aliases)]}
    def expense(value):
        primary = ("Расход неизвестен." if value["expense_status"] == "unknown" else
                   "Полнота данных о расходе не подтверждена.")
        return primary, primary + " В истории есть запросы без данных о расходе. " + (
            "По данным учёта: " + value["spend_usd"] + " USD. Эта сумма не подтверждает итоговый расход.")
    primary, summary = expense(actor_row)
    visible = {"employee_primary": primary, "employee_summary": summary + " Остаток не подтверждён.", "models": {}}
    keys = {}
    for index, model in enumerate(actor_row["models"]):
        primary, text = expense(model)
        visible["models"][model["id"]] = {"primary": primary, "expense": text,
            "blocked": "Заблокирована" if index else "Не заблокирована"}
        keys[model["id"]] = {"blocked": bool(index)}
    return [accounts, [actor_row], visible, keys]


class UnknownAdminRenderTests(unittest.TestCase):
    def reject(self, mutate):
        values = unknown_packet(); mutate(values)
        with self.assertRaises((AssertionError, ValueError, KeyError)): B.verify_unknown_render(*values)

    def test_unknown_primary_keeps_zero_native_counter_secondary_and_not_final(self):
        values = unknown_packet()
        result = B.verify_unknown_render(*values)
        self.assertTrue(result["employee_unknown_primary"])
        self.assertTrue(result["native_counters_not_final"])
        self.assertFalse(result["known_subtotal_present"])
        self.assertEqual(len(result["unknown_models"]), 2)
        self.assertNotIn("spend_usd", result)

    def test_actual_employee_model_and_source_roster_are_required(self):
        self.reject(lambda v: v[0].update(actor_id=str(uuid4())))
        self.reject(lambda v: v[0].update(employee_ids=[v[0]["admin"]["id"]]))
        self.reject(lambda v: v[0]["managed_model_ids"].reverse())
        self.reject(lambda v: v[1][0]["models"].pop())
        self.reject(lambda v: v[0].update(skill_id="another-skill"))

    def test_unknown_cannot_be_cleared_or_presented_as_confirmed_subtotal(self):
        self.reject(lambda v: v[1][0].update(expense_status="known"))
        self.reject(lambda v: v[1][0]["models"][1].update(expense_status="unavailable"))
        self.reject(lambda v: v[1][0].update(known_subtotal_usd="0"))
        self.reject(lambda v: v[1][0]["models"][1].update(known_subtotal_usd="0"))
        self.reject(lambda v: v[1][0]["models"][0].update(expense_status="known"))

    def test_primary_final_zero_and_missing_counter_caveats_are_rejected(self):
        self.reject(lambda v: v[2].update(employee_primary="0 USD"))
        self.reject(lambda v: v[2].update(employee_summary="Расход неизвестен. По данным учёта: .332 USD."))
        alias = unknown_packet()[0]["managed_model_ids"][1]
        self.reject(lambda v: v[2]["models"][alias].update(expense="Расход неизвестен. По данным учёта: 0 USD."))
        self.reject(lambda v: v[2]["models"][alias].update(primary="0"))

    def test_visible_counter_and_historical_qualification_must_match_saved_row(self):
        self.reject(lambda v: v[2].update(employee_summary=v[2]["employee_summary"].replace(".332", "9")))
        self.reject(lambda v: v[2].update(employee_summary=v[2]["employee_summary"].replace(
            "В истории есть запросы без данных о расходе.", "")))

    def test_block_label_requires_actual_boolean_native_readback(self):
        alias = unknown_packet()[0]["managed_model_ids"][1]
        self.reject(lambda v: v[3][alias].update(blocked=False))
        self.reject(lambda v: v[3][alias].update(blocked="true"))
        self.reject(lambda v: v[2]["models"][alias].update(blocked="Не заблокирована"))


if __name__ == "__main__":
    unittest.main()
