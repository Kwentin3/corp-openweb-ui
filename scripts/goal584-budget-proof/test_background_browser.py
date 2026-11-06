"""Browser-driver contract and restoration rehearsal; no live browser/API calls."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_background_browser as B


def browser_packet():
    calls = [{"chat_id": "chat-" + str(number), "message_id": "answer-" + str(number), "user_id": "actor",
              "model": B.MODEL, "outcome": "success", "native_cost_status": True, "terminal_persisted": True}
             for number in range(2)]
    result = {"physical_calls": 5, "personal_cost_usd": "0.40", "service_cost_usd": "0.60",
              "custom_auth_unsigned_403_count": 3, "full_baseline_service_provider_context_equal": True}
    original={"delay_ms":0,"native_tasks_mode":False}
    verified = {"stage": "events_verified", "actor_id": "actor", "result": result, "after": {"actual_native": "same"},
                "provider_control_observations":{"original":original}}
    for name, call in zip(("baseline_chat", "service_chat"), calls):
        verified[name] = {"chat_id": call["chat_id"], "answer_id": call["message_id"]}
    restored = {"stage": "qualified_automatic_background", "task_config_restored": True,"provider_controls_restored":True}
    return [calls, verified, restored, {"observed_native": verified["after"]},
            {"synthetic": True, "requests": [{}] * 5,"control":copy.deepcopy(original)}, {"schema": 1, "requests": [{}] * 8}]


class BrowserContractTests(unittest.TestCase):
    def test_only_one_native_source_and_all_three_real_background_flags_are_accepted(self):
        sent = {"model": B.MODEL, "user_message": {"role": "user", "content": "Hi", "parentId": None},
                "background_tasks": dict(B.TASKS)}
        self.assertTrue(B.check_submission(sent)["fresh_user_message"])
        for mutate in [lambda s:s.update(model=[B.MODEL, "goal584-b"]),
                       lambda s:s.update(models=[B.MODEL, "goal584-b"]),
                       lambda s:s["background_tasks"].update(title_generation=False),
                       lambda s:s["background_tasks"].update(extra=True),
                       lambda s:s["user_message"].update(parentId="old-turn")]:
            actual=copy.deepcopy(sent);mutate(actual)
            with self.assertRaises(AssertionError):B.check_submission(actual)

    def test_final_browser_result_requires_restoration_same_native_rows_and_exact_attempt_counts(self):
        self.assertEqual(B.verify_browser_result(*browser_packet())["physical_calls"], 5)
        for mutate in [lambda v:v[2].update(task_config_restored=False),
                       lambda v:v[2].update(provider_controls_restored=False),
                       lambda v:v[4]["control"].update(native_tasks_mode=True),
                       lambda v:v[0][1].update(chat_id=v[0][0]["chat_id"]),
                       lambda v:v[0][0].update(user_id="wrong-actor"),
                       lambda v:v[1]["service_chat"].update(answer_id="wrong-answer"),
                       lambda v:v[3].update(observed_native={"actual_native": "changed"}),
                       lambda v:v[4]["requests"].append({}), lambda v:v[5]["requests"].pop()]:
            value=browser_packet();mutate(value)
            with self.assertRaises(AssertionError):B.verify_browser_result(*value)

    def test_browser_start_failure_still_restores_native_config_and_returns_failed_safe_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);private=base/"private";private.mkdir()
            accounts=private/"users.json"
            accounts.write_text(json.dumps({"users": [{"id": str(i), "email": "fixture@example.invalid", "password": "private-pass"}
                                                     for i in range(2)]}), encoding="utf-8")
            output=base/"artifacts"
            phases=[]
            class Fixture:
                def __init__(self,*args):pass
                def phase(self,phase,*args):
                    phases.append(phase)
                    return {"task_config_restored": phase == "restore", "provider_controls_restored":phase == "restore"}
                def provider(self):return {"synthetic": True, "requests": []}
                def context(self):return {"schema": 1, "requests": []}
            arguments=["proof", "--base-url", "http://172.18.0.4:8080", "--accounts", str(accounts),
                       "--env-file", str(private/"proof.env"), "--output", str(output)]
            with patch.object(sys,"argv",arguments), patch.object(B,"BackgroundFixture",Fixture), \
                 patch.object(B,"sync_playwright",side_effect=RuntimeError("private-pass browser startup failed")), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(B.main(),1)
            receipt=json.loads((output/"background-browser.json").read_text(encoding="utf-8"))
            self.assertEqual(phases,["baseline-prepare","restore"])
            self.assertFalse(receipt["passed"])
            self.assertTrue(receipt["task_config_restored"])
            self.assertTrue(receipt["provider_controls_restored"])
            self.assertNotIn("private-pass",json.dumps(receipt))

    def test_provider_restore_failure_keeps_actual_task_restore_status_and_failed_browser_result(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);private=base/"private";private.mkdir()
            accounts=private/"users.json"
            accounts.write_text(json.dumps({"users":[{"id":str(i),"email":"fixture@example.invalid","password":"private-pass"}
                                                     for i in range(2)]}),encoding="utf-8")
            output=base/"artifacts"
            class Fixture:
                def __init__(self,*args):self.last_receipt={}
                def phase(self,phase,*args):
                    self.last_receipt={"phase":phase,"task_config_restored":phase=="restore","provider_controls_restored":False}
                    if phase=="restore":raise AssertionError("Fixed provider restore failure")
                    return self.last_receipt
                def provider(self):return {"synthetic":True,"requests":[]}
                def context(self):return {"schema":1,"requests":[]}
            arguments=["proof","--base-url","http://172.18.0.4:8080","--accounts",str(accounts),
                       "--env-file",str(private/"proof.env"),"--output",str(output)]
            with patch.object(sys,"argv",arguments),patch.object(B,"BackgroundFixture",Fixture), \
                 patch.object(B,"sync_playwright",side_effect=RuntimeError("Fixed startup failure")), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(B.main(),1)
            receipt=json.loads((output/"background-browser.json").read_text(encoding="utf-8"))
            self.assertTrue(receipt["task_config_restored"])
            self.assertFalse(receipt["provider_controls_restored"])
            self.assertFalse(receipt["passed"])
            self.assertIn("restoration_failure",receipt)


if __name__ == "__main__":
    unittest.main()
