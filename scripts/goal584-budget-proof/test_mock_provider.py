"""Real local HTTP/SSE contract tests for the disposable synthetic provider."""

import importlib.util
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
                        {"unknown": True}, {"prompt_tokens": True},
                        {"tool_round": True, "delay_ms": -1}):
            with self.subTest(payload=payload):
                self.assertEqual(self.http("/__proof/control", payload)[0], 400)
                self.assertFalse(self.receipts()["control"]["tool_round"])
        self.assertEqual(self.http("/__proof/control", {"tool_round": True})[0], 200)
        self.chat()
        self.http("/__proof/reset", {})
        self.assertEqual(self.receipts()["control"], {"prompt_tokens": 10, "completion_tokens": 5,
                                                     "delay_ms": 0, "tool_round": False})
        self.assertEqual(self.receipts()["requests"], [])

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
