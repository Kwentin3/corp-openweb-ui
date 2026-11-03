"""Real local HTTP/SSE contract tests for the disposable synthetic provider."""

import importlib.util
import ast
import json
from pathlib import Path
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SPEC = importlib.util.spec_from_file_location("goal584_mock_provider_under_test", Path(__file__).with_name("mock_provider.py"))
MOCK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOCK)
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
NAME = "proof_workspace_budget_echo"
TOOLS = [{"type": "function", "function": {"name": NAME, "parameters": {"type": "object", "properties": {}}}}]
OPEN_NAME = "employee_budget_admin_open_budget_form"
APPLY_NAME = "employee_budget_admin_apply_budget_form"
# Native local Tool schema shape after reserved __* parameters are removed.
ADMIN_TOOLS = [
    {"type": "function", "function": {"name": OPEN_NAME, "parameters": {
        "type": "object", "properties": {"view_json": {"type": "string", "default": "{}"}}, "required": []}}},
    {"type": "function", "function": {"name": APPLY_NAME, "parameters": {
        "type": "object", "properties": {}, "required": []}}},
]
PLAN = {"schema": 1, "type": "employee_budget_plan", "changes": [{
    "user_id": "1296bad0-1491-4c19-b7f2-93e57d812864", "expected_revision": "a" * 64,
    "budget_usd": "1.20", "shares": {"goal584-a": "0.5", "goal584-b": "0.5"},
}]}


class ProviderHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MOCK.Handler)
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        if cls.thread.is_alive():
            raise AssertionError("Owned proof HTTP server did not stop")

    def http(self, path, body=None):
        request = Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                          headers={"Content-Type": "application/json", "Authorization": "Bearer synthetic-not-recorded"})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read().decode()
            if response.headers.get_content_type() == "text/event-stream":
                return response.status, raw
            return response.status, json.loads(raw)

    def setUp(self):
        self.assertEqual(self.http("/__proof/reset", {})[0], 200)

    def chat(self, *, stream=False, messages=None, tools=TOOLS, model="goal584-fake-a"):
        payload = {"model": model, "messages": messages or [{"role": "user", "content": "Hi"}], "stream": stream}
        if tools is not None:
            payload["tools"] = tools
        status, result = self.http("/v1/chat/completions", payload)
        self.assertEqual(status, 200)
        if not stream:
            self.assertEqual(result["usage"], USAGE)
            return result, result["choices"][0]["message"], result["choices"][0]["finish_reason"]
        lines = [line[6:] for line in result.splitlines() if line.startswith("data: ")]
        self.assertEqual(lines[-1], "[DONE]")
        chunks = [json.loads(line) for line in lines[:-1]]
        self.assertEqual(len(chunks), 3)
        self.assertEqual({chunk["id"] for chunk in chunks}, {chunks[0]["id"]})
        self.assertTrue(all(chunk["object"] == "chat.completion.chunk" for chunk in chunks))
        self.assertEqual(chunks[-1]["choices"], [])
        self.assertEqual(chunks[-1]["usage"], USAGE)
        self.assertTrue(all("usage" not in chunk for chunk in chunks[:-1]))
        return chunks[0], chunks[0]["choices"][0]["delta"], chunks[1]["choices"][0]["finish_reason"]

    def receipts(self):
        status, result = self.http("/__proof/requests")
        self.assertEqual(status, 200)
        self.assertNotIn("Authorization", json.dumps(result))
        self.assertNotIn("synthetic-not-recorded", json.dumps(result))
        return result

    def test_default_behavior_is_unchanged_for_json_and_sse(self):
        ids = []
        for stream in (False, True):
            result, message, reason = self.chat(stream=stream)
            ids.append(result["id"])
            self.assertEqual(message, {"role": "assistant", "content": "Proof"})
            self.assertEqual(reason, "stop")
        self.assertEqual(len(set(ids)), 2)
        receipt = self.receipts()
        self.assertFalse(receipt["control"]["tool_round"])
        self.assertFalse(receipt["control"]["admin_mode"])
        self.assertEqual([row["id"] for row in receipt["requests"]], ids)
        self.assertTrue(all(row["usage"] == USAGE for row in receipt["requests"]))

    def check_two_rounds(self, stream):
        self.assertEqual(self.http("/__proof/control", {"tool_round": True})[0], 200)
        result, message, reason = self.chat(stream=stream)
        self.assertEqual(reason, "tool_calls")
        self.assertIsNone(message["content"])
        call = dict(message["tool_calls"][0])
        if stream:
            self.assertEqual(call.pop("index"), 0)
        self.assertEqual(call["type"], "function")
        self.assertEqual(call["function"], {"name": NAME, "arguments": "{}"})
        self.assertTrue(call["id"].startswith("call-goal584-"))
        self.assertNotEqual(call["id"], result["id"])
        messages = [{"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": None, "tool_calls": [call]},
                    {"role": "tool", "tool_call_id": call["id"], "content": "proof-tool-result"}]
        final, final_message, final_reason = self.chat(stream=stream, messages=messages)
        self.assertNotEqual(final["id"], result["id"])
        self.assertEqual(final_message, {"role": "assistant", "content": "Proof"})
        self.assertEqual(final_reason, "stop")
        receipt = self.receipts()["requests"]
        self.assertEqual([row["id"] for row in receipt], [result["id"], final["id"]])
        self.assertEqual(receipt[1]["body"]["messages"], messages)
        self.assertTrue(all(row["usage"] == USAGE for row in receipt))

    def test_nonstream_tool_call_then_tool_result_final(self):
        self.check_two_rounds(False)

    def test_sse_tool_call_then_tool_result_final(self):
        self.check_two_rounds(True)

    def test_only_results_after_last_user_finish_the_tool_round(self):
        self.http("/__proof/control", {"tool_round": True})
        history = [{"role": "user", "content": "Old"},
                   {"role": "tool", "tool_call_id": "old-call", "content": "old-result"},
                   {"role": "user", "content": "Hi"}]
        first, _, reason = self.chat(messages=history)
        second, _, second_reason = self.chat(messages=history)
        self.assertEqual((reason, second_reason), ("tool_calls", "tool_calls"))
        self.assertNotEqual(first["choices"][0]["message"]["tool_calls"][0]["id"],
                            second["choices"][0]["message"]["tool_calls"][0]["id"])

    def test_missing_or_ambiguous_tool_names_never_guess(self):
        self.http("/__proof/control", {"tool_round": True})
        for tools in (None, [], TOOLS * 2,
                      TOOLS + [{"type": "function", "function": {"name": "other_budget_echo"}}],
                      [{"type": "function", "function": {"name": "budget_echo_extra"}}],
                      [{"type": "function", "function": {"name": 42}}]):
            with self.subTest(tools=tools):
                _, message, reason = self.chat(tools=tools, model="goal584-fake-b")
                self.assertEqual((message["content"], reason), ("Proof", "stop"))
        _, _, reason = self.chat(tools=TOOLS + [{"type": "function", "function": {"name": "unrelated"}}])
        self.assertEqual(reason, "tool_calls")
        _, _, reason = self.chat(messages=[{"role": "system", "content": "No user yet"}])
        self.assertEqual(reason, "stop")

    def test_control_boolean_validation_and_reset(self):
        for payload in ({}, {"tool_round": 1}, {"tool_round": "true"}, {"tool_round": None},
                        {"admin_mode": 1}, {"admin_mode": "true"}, {"admin_mode": None},
                        {"title_mode": 1}, {"title_mode": "true"}, {"title_mode": None},
                        {"unknown": True}, {"prompt_tokens": True},
                        {"tool_round": True, "delay_ms": -1}):
            with self.subTest(payload=payload):
                self.assertEqual(self.http("/__proof/control", payload)[0], 400)
                self.assertFalse(self.receipts()["control"]["tool_round"])
                self.assertFalse(self.receipts()["control"]["admin_mode"])
        self.assertEqual(self.http("/__proof/control", {"tool_round": True, "admin_mode": True})[0], 200)
        self.chat()
        self.http("/__proof/reset", {})
        self.assertEqual(self.receipts()["control"], {"prompt_tokens": 10, "completion_tokens": 5,
                                                     "delay_ms": 0, "tool_round": False, "admin_mode": False,
                                                     "title_mode": False})
        self.assertEqual(self.receipts()["requests"], [])

    def test_title_mode_returns_one_json_title_with_original_native_usage(self):
        self.http("/__proof/control", {"title_mode": True, "admin_mode": True, "tool_round": True})
        for stream in (False, True):
            with self.subTest(stream=stream):
                _, message, reason = self.chat(stream=stream, messages=[{"role": "user", "content": json.dumps(PLAN)}],
                                                tools=ADMIN_TOOLS)
                self.assertEqual(reason, "stop")
                self.assertEqual(json.loads(message["content"]), {"title": "Proof"})
                self.assertNotIn("tool_calls", message)
        self.assertEqual(len(self.receipts()["requests"]), 2)

    def test_admin_schema_fixture_matches_actual_public_tool_signatures(self):
        source = Path(__file__).resolve().parents[2] / "deploy/openwebui-budgets/admin_tools.py"
        if not source.exists():
            self.skipTest("Admin Tool source not mounted; representative schemas remain explicit")
        tree = ast.parse(source.read_text(encoding="utf-8"))
        owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Tools")
        methods = {node.name: node for node in owner.body if isinstance(node, ast.AsyncFunctionDef)}
        for schema in ADMIN_TOOLS:
            name = schema["function"]["name"].removeprefix("employee_budget_admin_")
            actual = [arg.arg for arg in methods[name].args.args if arg.arg != "self" and not arg.arg.startswith("__")]
            self.assertEqual(set(actual), set(schema["function"]["parameters"]["properties"]))

    def admin_two_rounds(self, text, expected_name, expected_arguments, stream):
        self.http("/__proof/control", {"admin_mode": True})
        first, message, reason = self.chat(stream=stream, messages=[{"role": "user", "content": text}], tools=ADMIN_TOOLS)
        self.assertEqual(reason, "tool_calls")
        call = dict(message["tool_calls"][0])
        if stream:
            self.assertEqual(call.pop("index"), 0)
        self.assertEqual(call["function"]["name"], expected_name)
        self.assertEqual(json.loads(call["function"]["arguments"]), expected_arguments)
        history = [{"role": "user", "content": text},
                   {"role": "assistant", "content": None, "tool_calls": [call]},
                   {"role": "tool", "tool_call_id": call["id"], "content": json.dumps({
                       "status": "success", "message": "Budget form is visible; use apply_budget_form next"})}]
        final, final_message, final_reason = self.chat(stream=stream, messages=history, tools=ADMIN_TOOLS)
        self.assertEqual((final_message, final_reason), ({"role": "assistant", "content": "Proof"}, "stop"))
        self.assertEqual([row["id"] for row in self.receipts()["requests"]], [first["id"], final["id"]])
        self.assertTrue(all(row["usage"] == USAGE for row in self.receipts()["requests"]))

    def test_admin_open_russian_intent_json_and_sse(self):
        for stream, intent in [(False, "Настрой лимиты сотрудников"), (True, "Нужно обновить бюджеты сотрудников")]:
            with self.subTest(stream=stream):
                self.http("/__proof/reset", {})
                self.admin_two_rounds(intent, OPEN_NAME, {"view_json": "{}"}, stream)

    def test_admin_apply_exact_stored_json_never_copies_business_arguments(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                self.http("/__proof/reset", {})
                self.admin_two_rounds(json.dumps(PLAN), APPLY_NAME, {}, stream)

    def test_admin_old_tool_result_does_not_complete_a_new_user_turn(self):
        self.http("/__proof/control", {"admin_mode": True})
        history = [{"role": "user", "content": "Настрой бюджеты"},
                   {"role": "assistant", "content": None, "tool_calls": [{
                       "id": "old-open", "type": "function", "function": {"name": OPEN_NAME, "arguments": '{"view_json":"{}"}'}}]},
                   {"role": "tool", "tool_call_id": "old-open", "content": "Old form opened"},
                   {"role": "assistant", "content": "Proof"},
                   {"role": "user", "content": json.dumps(PLAN)}]
        _, message, reason = self.chat(messages=history, tools=ADMIN_TOOLS)
        self.assertEqual(reason, "tool_calls")
        self.assertEqual(message["tool_calls"][0]["function"], {"name": APPLY_NAME, "arguments": "{}"})
        # A second, later open intent must also ignore both older result turns.
        history.extend([{"role": "tool", "tool_call_id": "old-apply", "content": "Applied"},
                        {"role": "user", "content": "Обнови лимиты"}])
        _, message, reason = self.chat(messages=history, tools=ADMIN_TOOLS)
        self.assertEqual(reason, "tool_calls")
        self.assertEqual(message["tool_calls"][0]["function"]["name"], OPEN_NAME)

    def test_admin_mode_only_routes_available_unambiguous_suffixes(self):
        self.http("/__proof/control", {"admin_mode": True, "tool_round": True})
        for text, tools in [("Настрой лимиты", None), (json.dumps(PLAN), ADMIN_TOOLS[:1]),
                            ("Настрой лимиты", [*ADMIN_TOOLS, ADMIN_TOOLS[0]]),
                            (json.dumps(PLAN), [*ADMIN_TOOLS, ADMIN_TOOLS[1]]),
                            ("Настрой лимиты", TOOLS), ("Hi", [*ADMIN_TOOLS, *TOOLS]),
                            ("Настрой лимиты", [{"type": "function", "function": {"name": OPEN_NAME + "_extra"}}])]:
            with self.subTest(text_kind="json" if text.startswith("{") else "intent"):
                _, message, reason = self.chat(messages=[{"role": "user", "content": text}], tools=tools)
                self.assertEqual((message["content"], reason), ("Proof", "stop"))
        _, message, reason = self.chat(messages=[{"role": "user", "content": "Настроить лимиты"}], tools=[*ADMIN_TOOLS, *TOOLS])
        self.assertEqual(reason, "tool_calls")
        self.assertEqual(message["tool_calls"][0]["function"]["name"], OPEN_NAME)

    def test_admin_plan_marker_must_be_exact_json_not_fences_prose_or_boolean_schema(self):
        self.http("/__proof/control", {"admin_mode": True})
        for text in ["```json\n" + json.dumps(PLAN) + "\n```", "Apply this " + json.dumps(PLAN),
                     json.dumps({**PLAN, "schema": True}), json.dumps({**PLAN, "schema": 1.0}),
                     json.dumps({**PLAN, "type": "another_plan"}), json.dumps([PLAN])]:
            with self.subTest(text_start=text[:10]):
                _, message, reason = self.chat(messages=[{"role": "user", "content": text}], tools=ADMIN_TOOLS)
                self.assertEqual((message["content"], reason), ("Proof", "stop"))
        # A native one-text-part representation retains the exact same JSON content.
        _, message, reason = self.chat(messages=[{"role": "user", "content": [{"type": "text", "text": json.dumps(PLAN)}]}], tools=ADMIN_TOOLS)
        self.assertEqual(reason, "tool_calls")
        self.assertEqual(message["tool_calls"][0]["function"], {"name": APPLY_NAME, "arguments": "{}"})

    def test_admin_mode_off_does_not_route_admin_tools_and_echo_recovers(self):
        _, message, reason = self.chat(messages=[{"role": "user", "content": "Настрой лимиты"}], tools=ADMIN_TOOLS)
        self.assertEqual((message["content"], reason), ("Proof", "stop"))
        self.http("/__proof/control", {"tool_round": True, "admin_mode": True})
        self.http("/__proof/control", {"admin_mode": False})
        _, message, reason = self.chat(tools=[*TOOLS, *ADMIN_TOOLS])
        self.assertEqual(reason, "tool_calls")
        self.assertEqual(message["tool_calls"][0]["function"], {"name": NAME, "arguments": "{}"})

    def test_concurrent_calls_have_distinct_response_and_tool_ids(self):
        self.http("/__proof/control", {"tool_round": True})
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.chat(stream=True), range(2)))
        self.assertEqual(len({result[0]["id"] for result in results}), 2)
        self.assertEqual(len({result[1]["tool_calls"][0]["id"] for result in results}), 2)
        receipts = self.receipts()["requests"]
        self.assertEqual({row["id"] for row in receipts}, {result[0]["id"] for result in results})
        self.assertTrue(all(row["usage"] == USAGE for row in receipts))

    def test_existing_usage_control_bounds_remain_available(self):
        for count in (0, 10000):
            with self.subTest(count=count):
                self.assertEqual(self.http("/__proof/control", {
                    "prompt_tokens": count, "completion_tokens": count})[0], 200)
                for stream in (False, True):
                    status, result = self.http("/v1/chat/completions", {
                        "model": "goal584-fake-a", "messages": [{"role": "user", "content": "Hi"}],
                        "stream": stream})
                    self.assertEqual(status, 200)
                    if stream:
                        events = [json.loads(line[6:]) for line in result.splitlines()
                                  if line.startswith("data: ") and line != "data: [DONE]"]
                        usage, response_id = events[-1]["usage"], events[0]["id"]
                    else:
                        usage, response_id = result["usage"], result["id"]
                    self.assertEqual(usage, {"prompt_tokens": count, "completion_tokens": count,
                                             "total_tokens": count * 2})
                    recorded = self.receipts()["requests"][-1]
                    self.assertEqual((recorded["id"], recorded["usage"]), (response_id, usage))
        for payload in ({"prompt_tokens": -1}, {"completion_tokens": 10001}, {"delay_ms": False}):
            self.assertEqual(self.http("/__proof/control", payload)[0], 400)

    def test_invalid_model_and_messages_do_not_become_provider_receipts(self):
        self.http("/__proof/control", {"tool_round": True})
        for body, expected in (({"model": "unknown", "messages": [{"role": "user"}]}, 404),
                               ({"model": "goal584-fake-a", "messages": []}, 400),
                               ({"model": "goal584-fake-a", "messages": ["Hi"]}, 400)):
            self.assertEqual(self.http("/v1/chat/completions", body)[0], expected)
        self.assertEqual(self.receipts()["requests"], [])


if __name__ == "__main__":
    unittest.main()
