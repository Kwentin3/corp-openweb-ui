"""Real local HTTP/SSE contract tests for the disposable synthetic provider."""

import importlib.util
import ast
import copy
import json
import hashlib
import logging
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from typing import Final
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


class CatalogHTTPTests(unittest.TestCase):
    """The real owned server; optional cached native source is read-only evidence."""

    @classmethod
    def setUpClass(cls):
        ProviderHTTPTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        ProviderHTTPTests.tearDownClass.__func__(cls)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="goal584-catalog-")
        self.addCleanup(self.temp.cleanup)
        self.corpus_path = Path(self.temp.name) / MOCK.CATALOG_BACKUP_NAME
        self.env = patch.dict(os.environ, {"PROOF_CATALOG_ENABLED": "true",
            "PROOF_CATALOG_CORPUS_PATH": str(self.corpus_path)})
        self.env.start(); self.addCleanup(self.env.stop)
        if hasattr(self.server, "proof_catalog"):
            del self.server.proof_catalog
        self.assertEqual(self.request("/__proof/reset", {})[0], 200)

    def request(self, path, body=None):
        request = Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer synthetic-never-export"})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as e:
            response = e
        with response:
            return response.status, dict(response.headers), response.read()

    def json_request(self, path, body=None):
        status, _, raw = self.request(path, body)
        self.assertEqual(status, 200)
        return json.loads(raw)

    def native_blob(self, name):
        root = Path(os.environ.get("GOAL584_LITELLM_SOURCE",
            Path(__file__).resolve().parents[2] / "local/goal584/litellm/upstream"))
        if not root.is_dir():
            self.skipTest("Read-only d665 native Git cache unavailable; set GOAL584_LITELLM_SOURCE")
        try:
            return subprocess.check_output(["git", "-c", "gc.auto=0", "show", MOCK.CATALOG_REVISION + ":" + name],
                cwd=root, env={**os.environ, "GIT_NO_LAZY_FETCH": "1"}, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            self.skipTest("Exact cached d665 Git blob unavailable; no fetching permitted")

    def install_corpus(self):
        raw = self.native_blob("litellm/" + MOCK.CATALOG_BACKUP_NAME)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), MOCK.CATALOG_BACKUP_SHA256)
        self.corpus_path.write_bytes(raw)
        return raw, json.loads(raw)

    def test_disabled_routes_preserve_normal_shape_and_do_not_discover_package(self):
        for flag in ("", "false", "True", "1"):
            with self.subTest(flag=flag), patch.dict(os.environ, {"PROOF_CATALOG_ENABLED": flag}), \
                    patch.object(MOCK.importlib.util, "find_spec", side_effect=AssertionError("must not discover")):
                for path, body in (("/__proof/catalog", None), ("/__proof/catalog/observations", None),
                                   ("/__proof/catalog/control", {"variant": "S2"}), ("/__proof/catalog/reset", {})):
                    status, _, raw = self.request(path, body)
                    self.assertEqual(status, 404)
                    self.assertEqual(json.loads(raw), {"error": {"message": "Unknown synthetic endpoint"}})
                normal = self.json_request("/__proof/requests")
                self.assertEqual(set(normal), {"synthetic", "requests", "control"})
                self.assertEqual(normal["requests"], [])
                self.assertEqual(normal["control"], MOCK.CONTROL)

    def test_S1_S2_exact_bytes_etag_revisions_and_unrelated_corpus(self):
        raw, corpus = self.install_corpus()
        documents = {}
        for variant in ("S1", "S2", "S1"):
            self.json_request("/__proof/catalog/control", {"variant": variant})
            status, headers, body = self.request("/__proof/catalog")
            self.assertEqual(status, 200)
            content = json.loads(body)
            self.assertGreaterEqual(len(content), 50)
            self.assertGreaterEqual(len(content), len(corpus) * .5)
            self.assertEqual({k: v for k, v in content.items() if k not in MOCK.MODELS}, corpus)
            self.assertEqual(headers["ETag"], '"' + hashlib.sha256(body).hexdigest() + '"')
            if variant in documents:
                self.assertEqual(documents[variant], body)
            documents[variant] = body
        self.assertNotEqual(documents["S1"], documents["S2"])
        s1, s2 = (json.loads(documents[n]) for n in ("S1", "S2"))
        self.assertEqual({k for k in s1 if s1[k] != s2[k]}, {"goal584-fake-a"})
        self.assertEqual(s1["goal584-fake-a"]["input_cost_per_token"], .01)
        self.assertEqual(s2["goal584-fake-a"]["input_cost_per_token"], .02)
        self.assertEqual(s2["goal584-fake-a"]["output_cost_per_token"], .04)
        observed = self.json_request("/__proof/catalog/observations")
        self.assertEqual(observed["request_count"], 3)
        self.assertEqual(observed["requests_by_variant"], {"S1": 2, "S2": 1, "invalid": 0, "truncated": 0})
        self.assertEqual(observed["corpus_sha256"], hashlib.sha256(raw).hexdigest())
        for name, body in documents.items():
            info = observed["documents"][name]
            self.assertEqual(info["native_git_blob"], hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest())
            self.assertEqual(info["bytes"], len(body))
            self.assertEqual(info["sha256"], hashlib.sha256(body).hexdigest())
        self.assertNotIn("synthetic-never-export", json.dumps(observed))
        self.assertNotIn(str(self.corpus_path), json.dumps(observed))
        self.assertEqual(self.corpus_path.read_bytes(), raw)

    def test_controller_is_separate_atomic_bounded_and_resettable(self):
        self.install_corpus()
        before = self.json_request("/__proof/requests")
        self.json_request("/__proof/control", {"tool_round": True})
        for payload in ({}, {"variant": 1}, {"variant": True}, {"variant": "unknown"},
                        {"variant": "S2", "url": "https://example.invalid"}, {"path": "/private"}):
            self.assertEqual(self.request("/__proof/catalog/control", payload)[0], 400)
            self.assertEqual(self.json_request("/__proof/catalog/observations")["variant"], "S1")
        self.json_request("/__proof/catalog/control", {"variant": "S2"})
        self.request("/__proof/catalog")
        self.json_request("/__proof/reset", {})
        self.assertEqual(self.json_request("/__proof/catalog/observations")["variant"], "S2")
        self.assertEqual(self.json_request("/__proof/catalog/observations")["request_count"], 1)
        self.assertEqual(self.json_request("/__proof/requests"), before)
        self.assertEqual(self.request("/__proof/catalog/reset", {"unexpected": True})[0], 400)
        reset = self.json_request("/__proof/catalog/reset", {})
        self.assertEqual((reset["variant"], reset["request_count"]), ("S1", 0))
        self.server.proof_catalog.counts["S1"] = 10000
        self.assertEqual(self.request("/__proof/catalog")[0], 503)

    def test_inference_and_catalog_observations_do_not_cross_count_or_context(self):
        self.install_corpus()
        payload = {"model": "goal584-fake-a", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5}
        first = self.json_request("/v1/chat/completions", payload)
        before = self.json_request("/__proof/requests")
        self.request("/__proof/catalog")
        self.json_request("/__proof/catalog/control", {"variant": "S2"})
        self.request("/__proof/catalog")
        self.assertEqual(self.json_request("/__proof/requests"), before)
        second = self.json_request("/v1/chat/completions", payload)
        rows = self.json_request("/__proof/requests")["requests"]
        self.assertEqual([r["id"] for r in rows], [first["id"], second["id"]])
        self.assertTrue(all(r["body"] == payload and r["usage"] == USAGE for r in rows))
        self.assertEqual(self.json_request("/__proof/catalog/observations")["request_count"], 2)

    def test_corpus_failures_are_closed_and_do_not_export_path_or_body(self):
        for raw in (b'{"private":"synthetic-credential-must-not-leak"}', b"x" * (MOCK.CATALOG_MAX_BYTES + 1)):
            self.corpus_path.write_bytes(raw)
            status, _, body = self.request("/__proof/catalog")
            self.assertEqual(status, 503)
            self.assertEqual(json.loads(body), {"error": {"message": "Synthetic catalog unavailable"}})
        self.assertFalse(hasattr(self.server, "proof_catalog"))
        self.assertEqual(self.json_request("/__proof/requests")["requests"], [])

    def test_default_corpus_uses_top_level_spec_without_importing_package(self):
        self.install_corpus()
        fake_init = self.corpus_path.parent / "__init__.py"
        fake_init.write_text("raise RuntimeError('package must never execute')", encoding="utf8")
        with patch.dict(os.environ, {"PROOF_CATALOG_CORPUS_PATH": ""}), \
                patch.object(MOCK.importlib.util, "find_spec", return_value=SimpleNamespace(origin=str(fake_init))) as find:
            self.assertEqual(self.request("/__proof/catalog")[0], 200)
            find.assert_called_once_with("litellm")

    def test_actual_native_fetch_parser_count_integrity_and_revisions(self):
        try:
            import httpx
        except ImportError:
            self.skipTest("Existing optional httpx unavailable for native classifier replay")
        from dataclasses import dataclass
        _, corpus = self.install_corpus()
        source = self.native_blob("litellm/litellm_core_utils/get_model_cost_map.py")
        self.assertEqual(hashlib.sha256(source).hexdigest(), "66fe0c8a066efebd34cca8815ac23ebf09379b76f7b32525321503ef6d7db679")
        tree = ast.parse(source)
        names = {"_count_model_entries", "git_blob_id", "_classify_fetch_response", "_parse_retry_after_seconds",
                 "ModelCostMapReloaded", "ModelCostMapReloadUnavailable", "_FetchAttemptRetryable"}
        nodes = [n for n in tree.body if getattr(n, "name", None) in names]
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "GetModelCostMap")
        cls.body = [n for n in cls.body if getattr(n, "name", None) in {
            "_check_is_valid_dict", "_check_model_count_not_reduced", "validate_model_cost_map"}]
        nodes.append(cls)
        namespace = {"httpx": httpx, "dataclass": dataclass, "Final": Final, "hashlib": hashlib,
            "_FetchAttemptOutcome": object, "RETRYABLE_FETCH_STATUS_CODES": frozenset({429, 500, 502, 503, 504}),
            "RESERVED_TOP_LEVEL_KEYS": frozenset({"sample_spec", "fallback_generalizations"}),
            "MODEL_COST_MAP_MIN_MODEL_COUNT": 50, "MODEL_COST_MAP_MAX_SHRINK_RATIO": .5,
            "verbose_logger": logging.getLogger("native_catalog_replay")}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "native-cost-map.py", "exec"), namespace)
        count = namespace["_count_model_entries"]; owner = namespace["GetModelCostMap"]
        for variant in MOCK.CATALOG_VARIANTS:
            self.json_request("/__proof/catalog/control", {"variant": variant})
            status, headers, body = self.request("/__proof/catalog")
            outcome = namespace["_classify_fetch_response"](httpx.Response(status, content=body, headers=headers), self.base)
            if variant in ("S1", "S2"):
                self.assertIsInstance(outcome, namespace["ModelCostMapReloaded"])
                self.assertEqual(outcome.revision, MOCK.CatalogFixture.git_blob(body))
                self.assertEqual(outcome.etag, headers["ETag"])
                self.assertTrue(owner.validate_model_cost_map(outcome.model_cost_map, count(corpus)))
                self.assertFalse(owner.validate_model_cost_map(dict(list(outcome.model_cost_map.items())[:49]), count(corpus)))
                self.assertFalse(owner.validate_model_cost_map(dict(list(outcome.model_cost_map.items())[:100]), count(corpus)))
            else:
                self.assertIsInstance(outcome, namespace["ModelCostMapReloadUnavailable"])


class DelegatedProviderTests(unittest.TestCase):
    """Finite grammar checks; CLI IO replies here are not installed-guide acceptance."""
    @classmethod
    def setUpClass(cls):
        import test_office_compatibility as existing
        source = Path(os.environ.get('GOAL584_NATIVE_SOURCE_ROOT', str(existing.NATIVE)))
        if not (source / 'utils/tools.py').is_file():
            if 'GOAL584_NATIVE_SOURCE_ROOT' in os.environ: raise AssertionError('Selected native source is unavailable')
            raise unittest.SkipTest('New opt-in native source fixture unavailable; no schema substitute')
        with patch.object(existing, 'NATIVE', source):
            owners, _, _ = existing.native.__wrapped__()
        schema = existing.create_app(existing.CliIO()).openapi()
        cls.office_tools = [{'type': 'function', **owners['clean_openai_tool_schema'](s)}
            for s in owners['convert_openapi_to_tool_payload'](schema)]
        assert len(cls.office_tools) == 14
        # Execute the pinned native task implementation; only Chat persistence
        # and event delivery are IO leaves. No second Tasks implementation.
        from pydantic import BaseModel, Field
        from typing import Literal, Optional
        import inspect
        raw = (source / 'tools/builtin.py').read_bytes().replace(b'\r\n', b'\n')
        assert hashlib.sha256(raw).hexdigest() == 'e090238724bb955847f7d14dfa0c27b4d91a413dc0987ae81595bd46b86747f9'
        names = {'TaskItem', 'VALID_TASK_STATUSES', '_task_summary', '_emit_tasks', 'create_tasks', 'update_task'}
        tree = ast.parse(raw)
        nodes = [n for n in tree.body if getattr(n, 'name', None) in names
                 or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
        assert len(nodes) == len(names)
        namespace = {'__name__': __name__, 'BaseModel': BaseModel, 'Field': Field, 'Literal': Literal,
                     'Optional': Optional, 'Request': SimpleNamespace, 'JSONCodec': json, 'log': logging.getLogger(__name__)}
        exec(compile((source / 'utils/chat_id.py').read_text(encoding='utf-8'), 'native-chat-id', 'exec'), namespace)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source / 'tools/builtin.py'), 'exec'), namespace)
        cls.native_tasks = namespace
        # Derive the public schema from the actual function signatures and
        # actual TaskItem schema, rather than inventing a task_id alias.
        cls.task_tools = []
        for name in ('create_tasks', 'update_task'):
            parameters = inspect.signature(namespace[name]).parameters
            public = {k: v for k, v in parameters.items() if not k.startswith('__')}
            assert set(public) == ({'tasks'} if name == 'create_tasks' else {'id', 'status'})
            properties = {'tasks': {'type': 'array', 'items': namespace['TaskItem'].model_json_schema()}} if name == 'create_tasks' else {
                'id': {'type': 'string'}, 'status': {'type': 'string', 'default': public['status'].default}}
            cls.task_tools.append({'type': 'function', 'name': name, 'parameters': {'type': 'object',
                'properties': properties, 'required': [k for k, v in public.items() if v.default is inspect.Parameter.empty]}})

    def setUp(self):
        import provision_webui as provision
        self.source_id = '1296bad0-1491-4c19-b7f2-93e57d812864'
        self.file_id = 'cf931dc8-a099-4471-9173-27b1e296bb59'
        source = provision.delegated_source_docx()
        content = provision.delegated_skill_content(self.source_id, hashlib.sha256(source).hexdigest())
        self.skill = {'id': 'goal584-delegated-' + 'a' * 32, 'name': 'Synthetic Skill', 'content': content, 'next_offset': None, 'files': []}
        self.parent = {'model': MOCK.DELEGATED_PARENT_MODEL, 'max_output_tokens': 12000,
            'tools': [{'type': 'function', 'name': name, 'parameters': {'type': 'object', 'properties': {}}}
                for name in ('view_skill', 'corporate_document_delegation_run_sub_agent')] + copy.deepcopy(self.task_tools),
            'input': [{'type': 'message', 'role': 'system', 'content': self.skill['id']},
                      {'type': 'message', 'role': 'user', 'content': MOCK.DELEGATED_USER_REQUEST}]}
        self.task_rows, self.task_events = [], []

    def step(self, payload):
        before = json.dumps(payload, sort_keys=True)
        result = MOCK.delegated_responses_step(payload, MOCK.delegated_responses_input(payload))
        self.assertEqual(json.dumps(payload, sort_keys=True), before)
        return result

    def append(self, payload, selection, result):
        name, arguments, _ = selection
        identifier = 'call-' + str(sum(v.get('type') == 'function_call' for v in payload['input']))
        payload['input'].extend([{'type': 'function_call', 'call_id': identifier, 'name': name, 'arguments': json.dumps(arguments)},
            {'type': 'function_call_output', 'call_id': identifier, 'output': result if isinstance(result, list) else json.dumps(result)}])

    def parent_packet(self):
        selected = self.step(self.parent)
        self.assertEqual(selected[0], 'create_tasks')
        self.assertEqual(len(selected[1]['tasks']), 2)
        self.assertTrue(all('id' not in task for task in selected[1]['tasks']))
        self.append(self.parent, selected, self.native_task(selected))
        selected = self.step(self.parent)
        self.assertEqual(selected[:2], ('view_skill', {'id': self.skill['id']}))
        self.append(self.parent, selected, self.skill)
        selected = self.step(self.parent)
        packet = json.loads(selected[1]['prompt'])
        self.assertEqual(packet['skill'], {'id': self.skill['id'], 'content': self.skill['content']})
        self.assertEqual(packet['source_file']['id'], self.source_id)
        self.assertNotIn('version_id', packet['skill'])
        return selected, packet

    def native_task(self, selected):
        import asyncio
        name, arguments, _ = selected
        async def save(chat_id, tasks):
            self.assertEqual(chat_id, 'native-parent-chat')
            self.task_rows = copy.deepcopy(tasks)
        async def load(chat_id):
            self.assertEqual(chat_id, 'native-parent-chat')
            return copy.deepcopy(self.task_rows)
        async def emit(event):
            self.task_events.append(copy.deepcopy(event))
        arguments = copy.deepcopy(arguments)
        if name == 'create_tasks':
            arguments['tasks'] = [self.native_tasks['TaskItem'].model_validate(t) for t in arguments['tasks']]
        with patch.dict(self.native_tasks, Chats=SimpleNamespace(update_chat_tasks_by_id=save, get_chat_tasks_by_id=load)):
            result = asyncio.run(self.native_tasks[name](**arguments, __chat_id__='native-parent-chat', __event_emitter__=emit))
        return json.loads(result)

    def worker_history(self):
        _, packet = self.parent_packet()
        payload = {'model': MOCK.DELEGATED_WORKER_MODEL, 'max_output_tokens': 6000, 'stream': False,
            'tools': copy.deepcopy(self.office_tools), 'instructions': 'Actual profile is checked by the native-factory rehearsal.',
            'input': [{'type': 'message', 'role': 'user', 'content': json.dumps(packet)}]}
        guide = 'Deterministic CLI IO leaf only; not the installed Office guide.'
        source_nodes = [{'path': '/body/p[1]', 'text': 'Employee: {{employee}}'},
                        {'path': '/body/p[2]', 'text': 'Case: {{case}}'}]
        filled = [{'path': '/body/p[' + str(i + 1) + ']', 'text': value} for i, value in enumerate((
            'Employee: Ada Example', 'Case: G584-2026', 'FIXED CLAUSE: preserve this sentence.', 'FIXED TABLE'))]
        png = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + b'\x00' * 8
        replies = [
            {'content': guide, 'content_sha256': hashlib.sha256(guide.encode()).hexdigest()},
            {'file_id': self.source_id, 'officecli_result': {'success': True, 'data': {'results': source_nodes}}},
            {'source_file_id': self.source_id, 'source_sha256': packet['source_file']['sha256'], 'source_bytes_preserved': True,
             'result_file_id': self.file_id, 'result_file': {'id': self.file_id}},
            {'file_id': self.file_id, 'officecli_result': {'success': True, 'data': {'results': filled}}},
            [{'type': 'input_text', 'text': 'render_office_file: Image file read successfully.'},
             {'type': 'input_image', 'image_url': 'data:image/png;base64,' + __import__('base64').b64encode(png).decode()}],
        ]
        stages = []
        for reply in replies:
            selected = self.step(payload); stages.append(copy.deepcopy(payload))
            self.append(payload, selected, reply)
        self.assertEqual(self.step(payload), (None, None, self.file_id))
        return payload, stages

    def test_complete_parent_worker_tasks_grammar_and_whole_native_packet(self):
        worker, stages = self.worker_history()
        self.assertEqual(len(stages), 5)
        delegated = self.step(self.parent)
        self.append(self.parent, delegated, {'note': 'native Tool envelope', 'result': '[Download](/api/v1/files/' + self.file_id + '/content)'})
        for task in copy.deepcopy(self.task_rows):
            selected = self.step(self.parent)
            self.assertEqual(selected[:2], ('update_task', {'id': task['id'], 'status': 'completed'}))
            self.append(self.parent, selected, self.native_task(selected))
        self.assertEqual(self.step(self.parent), (None, None, self.file_id))
        self.assertEqual([t['status'] for t in self.task_rows], ['completed', 'completed'])
        self.assertEqual(len(self.task_events), 3)
        self.assertEqual(self.task_events[-1], {'type': 'chat:message:tasks', 'data': {'tasks': self.task_rows}})
        self.assertEqual(len(worker['tools']), 14)
        self.assertFalse({'create_tasks', 'update_task'} & {t['name'] for t in worker['tools']})

    def test_profile_params_and_transport_are_not_shrunk_or_opportunistically_changed(self):
        for field, value in [('max_output_tokens', 1024), ('stream', True), ('stream', False)]:
            payload = copy.deepcopy(self.parent); payload[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): self.step(payload)

    def test_actual_finite_handler_keeps_new_alias_and_output_cap(self):
        import io
        handler = object.__new__(MOCK.Handler); statuses = []
        handler.send_response = statuses.append
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        handler.wfile = io.BytesIO()
        with patch.object(MOCK, 'REQUESTS', []), patch.dict(MOCK.CONTROL, response_status=200):
            handler.serve_responses(copy.deepcopy(self.parent))
        self.assertEqual(statuses, [200])
        result = json.loads(handler.wfile.getvalue())
        self.assertEqual(result['model'], MOCK.DELEGATED_PARENT_MODEL)
        self.assertEqual(result['max_output_tokens'], 12000)
        self.assertEqual(result['output'][0]['name'], 'create_tasks')
        self.assertEqual((result['usage']['input_tokens'], result['usage']['output_tokens']), (10, 5))

    def test_parent_uses_returned_ids_and_requires_native_completion_before_download(self):
        self.parent_packet()
        # Legal task IDs are opaque strings in the native TaskItem contract.
        # This IO fixture makes a hardcoded index fail; native update still runs.
        created = json.loads(self.parent['input'][3]['output'])
        for task, identifier in zip(created['tasks'], ('returned-fill-id', 'returned-check-id')):
            task['id'] = identifier
        self.parent['input'][3]['output'] = json.dumps(created)
        self.task_rows = copy.deepcopy(created['tasks'])
        delegated = self.step(self.parent)
        self.append(self.parent, delegated, {'result': '[Download](/api/v1/files/' + self.file_id + '/content)'})
        first = self.step(self.parent)
        self.assertEqual(first[1], {'id': 'returned-fill-id', 'status': 'completed'})
        before = copy.deepcopy(self.parent)
        self.append(self.parent, first, self.native_task(first))
        second = self.step(self.parent)
        self.assertEqual(second[1], {'id': 'returned-check-id', 'status': 'completed'})
        self.append(self.parent, second, self.native_task(second))
        self.assertEqual(self.step(self.parent), (None, None, self.file_id))
        mutations = [
            (before, lambda p: p['input'][3].update(output='{"error":"Native create failed"}')),
            (before, lambda p: p['input'][3].update(output=p['input'][3]['output'].replace('in_progress', 'completed'))),
            (self.parent, lambda p: p['input'][-2].update(arguments='{"task_id":"returned-check-id","status":"completed"}')),
            (self.parent, lambda p: p['input'][-1].update(output='{"error":"Native update failed"}')),
            (self.parent, lambda p: p['input'][-1].update(output=p['input'][-1]['output'].replace('completed', 'pending'))),
        ]
        for index, (source, mutate) in enumerate(mutations):
            payload = copy.deepcopy(source); mutate(payload)
            with self.subTest(case=index), self.assertRaises(ValueError): self.step(payload)

    def test_native_skill_source_paths_guide_copy_inspection_and_png_mutations_fail(self):
        final, stages = self.worker_history()
        mutations = [
            (stages[0], lambda p: p['input'][0].update(content=p['input'][0]['content'].replace(self.source_id, self.file_id, 1))),
            (stages[1], lambda p: p['input'][-1].update(output='{}')),
            (stages[2], lambda p: p['input'][-1].update(output=p['input'][-1]['output'].replace('/body/p[2]', '/body/p[1]'))),
            (stages[3], lambda p: p['input'][-1].update(output=p['input'][-1]['output'].replace('true', 'false'))),
            (stages[4], lambda p: p['input'][-1].update(output=p['input'][-1]['output'].replace('G584-2026', 'LOST'))),
            (final, lambda p: p['input'][-1]['output'][1].update(image_url='data:image/png;base64,bm90LXBuZw==')),
        ]
        for index, (source, mutate) in enumerate(mutations):
            payload = copy.deepcopy(source); mutate(payload)
            with self.subTest(case=index), self.assertRaises((ValueError, KeyError)): self.step(payload)


if __name__ == "__main__":
    unittest.main()
