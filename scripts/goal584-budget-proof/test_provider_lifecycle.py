"""Actual loopback HTTP/SSE lifecycle controls; no proxy or external inference."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener


SPEC = importlib.util.spec_from_file_location("provider_lifecycle_under_test", Path(__file__).with_name("mock_provider.py"))
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
DEFAULT = {"prompt_tokens": 10, "completion_tokens": 5, "delay_ms": 0, "tool_round": False,
           "admin_mode": False, "title_mode": False}
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
TOOLS = [{"type": "function", "function": {"name": "fixture_budget_echo", "parameters": {"type": "object", "properties": {}}}}]


class LifecycleHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), P.Handler)
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        if cls.thread.is_alive():
            raise AssertionError("Owned lifecycle HTTP server remained alive")

    def http(self, path, body=None):
        request = Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                          headers={"Content-Type": "application/json", "Authorization": "Bearer synthetic-not-recorded"})
        try:
            result = build_opener(ProxyHandler({})).open(request, timeout=5)
        except HTTPError as error:
            result = error
        with result:
            raw = result.read().decode()
            return result.status, raw if result.headers.get_content_type() == "text/event-stream" else json.loads(raw)

    def setUp(self):
        self.assertEqual(self.http("/__proof/reset", {})[0], 200)

    def controls(self, value):
        status, actual = self.http("/__proof/control", value)
        self.assertEqual(status, 200)
        return actual

    def payload(self, stream=False):
        return {"model": P.MODELS[0], "messages": [{"role": "user", "content": "Hi"}], "stream": stream, "tools": TOOLS}

    def wait_row(self, predicate, *, identifier=None):
        deadline = time.monotonic() + 4
        while True:
            _, data = self.http("/__proof/requests")
            self.assertNotIn("synthetic-not-recorded", json.dumps(data))
            rows = [row for row in data["requests"] if identifier is None or row["id"] == identifier]
            if rows and predicate(rows[0]["lifecycle"]):
                self.assertEqual(len(rows), 1)
                return rows[0]
            if time.monotonic() >= deadline:
                self.fail("Observable provider lifecycle condition was not reached")
            threading.Event().wait(.005)

    def raw_request(self):
        sock = socket.create_connection(("127.0.0.1", self.server.server_port), timeout=5)
        body = json.dumps(self.payload(stream=True)).encode()
        headers = ("POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                   "Content-Type: application/json\r\nConnection: close\r\nContent-Length: " + str(len(body)) + "\r\n\r\n")
        sock.sendall(headers.encode() + body)
        return sock

    def disconnect(self, sock, reader=None):
        # Actual peer reset makes the next server write fail deterministically;
        # closing a client future alone is not server-side cancellation proof.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("hh" if os.name == "nt" else "ii", 1, 0))
        if reader is not None:
            reader.close()
        sock.close()

    def test_default_json_tool_and_title_outputs_and_usage_are_unchanged(self):
        for mode in ({}, {"tool_round": True}, {"title_mode": True, "tool_round": True}):
            self.http("/__proof/reset", {})
            if mode:
                self.controls(mode)
            status, result = self.http("/v1/chat/completions", self.payload())
            self.assertEqual(status, 200)
            self.assertEqual(result["usage"], USAGE)
            message = result["choices"][0]["message"]
            if mode.get("title_mode"):
                self.assertEqual(json.loads(message["content"]), {"title": "Proof"})
            elif mode.get("tool_round"):
                self.assertEqual(message["tool_calls"][0]["function"]["name"], "fixture_budget_echo")
            else:
                self.assertEqual(message, {"role": "assistant", "content": "Proof"})
            row = self.wait_row(lambda stage: stage["terminal"], identifier=result["id"])
            self.assertEqual(row["usage"], USAGE)
            self.assertEqual(row["lifecycle"]["outcome"], "completed")
            self.assertTrue(row["lifecycle"]["usage_sent"])
            self.assertEqual(row["lifecycle"]["chunks_sent"], 0)

    def test_controlled_500_has_no_output_or_usage_and_uses_arrival_control_snapshot(self):
        self.controls({"response_status": 500, "delay_ms": 400})
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.http, "/v1/chat/completions", self.payload())
            started = self.wait_row(lambda stage: stage["stage"] == "before_headers_delay" and not stage["terminal"])
            self.assertFalse(pending.done())
            self.assertFalse(started["lifecycle"]["headers_sent"])
            self.controls({"response_status": 200})
            status, result = pending.result(timeout=4)
        self.assertEqual(status, 500)
        self.assertEqual(result["id"], started["id"])
        self.assertEqual(result["error"]["code"], "proof_provider_500")
        self.assertNotIn("choices", result)
        self.assertNotIn("usage", result)
        terminal = self.wait_row(lambda stage: stage["terminal"], identifier=result["id"])
        self.assertIsNone(terminal["usage"])
        self.assertEqual(terminal["lifecycle"]["outcome"], "controlled_error")
        self.assertFalse(terminal["lifecycle"]["usage_sent"])
        self.assertEqual(terminal["lifecycle"]["chunks_sent"], 0)

    def test_first_sse_chunk_is_visible_while_completion_is_held_then_terminates(self):
        self.controls({"after_first_chunk_delay_ms": 700})
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.http, "/v1/chat/completions", self.payload(stream=True))
            paused = self.wait_row(lambda stage: stage["stage"] == "after_first_chunk_delay" and not stage["terminal"])
            self.assertFalse(pending.done())
            self.assertTrue(paused["lifecycle"]["headers_sent"])
            self.assertEqual(paused["lifecycle"]["chunks_sent"], 1)
            self.assertFalse(paused["lifecycle"]["usage_sent"])
            status, result = pending.result(timeout=4)
        self.assertEqual(status, 200)
        lines = [line[6:] for line in result.splitlines() if line.startswith("data: ")]
        self.assertEqual(lines[-1], "[DONE]")
        chunks = [json.loads(line) for line in lines[:-1]]
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0]["id"], paused["id"])
        self.assertEqual(chunks[0]["choices"][0]["delta"]["content"], "Proof")
        self.assertEqual(chunks[-1]["usage"], USAGE)
        terminal = self.wait_row(lambda stage: stage["terminal"], identifier=paused["id"])
        self.assertEqual((terminal["lifecycle"]["outcome"], terminal["lifecycle"]["chunks_sent"]), ("completed", 3))
        self.assertTrue(terminal["lifecycle"]["usage_sent"])

    def test_actual_disconnect_before_headers_is_terminal_without_emitted_usage(self):
        self.controls({"delay_ms": 600})
        sock = self.raw_request()
        try:
            started = self.wait_row(lambda stage: stage["stage"] == "before_headers_delay" and not stage["terminal"])
            self.assertFalse(started["lifecycle"]["headers_sent"])
            self.disconnect(sock)
        finally:
            sock.close()
        terminal = self.wait_row(lambda stage: stage["terminal"], identifier=started["id"])
        self.assertEqual(terminal["lifecycle"]["outcome"], "client_disconnected")
        self.assertEqual(terminal["lifecycle"]["chunks_sent"], 0)
        self.assertFalse(terminal["lifecycle"]["usage_sent"])

    def test_actual_disconnect_after_first_sse_chunk_retains_partial_marker(self):
        self.controls({"after_first_chunk_delay_ms": 700})
        sock, reader = self.raw_request(), None
        try:
            reader = sock.makefile("rb")
            self.assertIn(b"200", reader.readline())
            for _ in range(32):
                line = reader.readline(8192)
                self.assertTrue(line, "SSE connection ended before the header boundary")
                if line in (b"\r\n", b"\n"):
                    break
            else:
                self.fail("SSE header bound exceeded")
            first = reader.readline(8192)
            self.assertTrue(first.startswith(b"data: "))
            identifier = json.loads(first[6:])["id"]
            paused = self.wait_row(lambda stage: stage["stage"] == "after_first_chunk_delay" and not stage["terminal"], identifier=identifier)
            self.assertEqual(paused["lifecycle"]["chunks_sent"], 1)
            self.disconnect(sock, reader)
        finally:
            if reader is not None:
                reader.close()
            sock.close()
        terminal = self.wait_row(lambda stage: stage["terminal"], identifier=identifier)
        self.assertEqual(terminal["lifecycle"]["outcome"], "client_disconnected")
        self.assertEqual(terminal["lifecycle"]["chunks_sent"], 1)
        self.assertFalse(terminal["lifecycle"]["usage_sent"])
        self.assertGreaterEqual(terminal["lifecycle"]["terminal_monotonic"], terminal["lifecycle"]["started_monotonic"])

    def test_invalid_controls_are_atomic_and_reset_retains_exact_legacy_defaults(self):
        for value in ({"response_status": value} for value in (True, 0, 400, 503, "500", 500.0)):
            self.assertEqual(self.http("/__proof/control", value)[0], 400)
        for value in ({"after_first_chunk_delay_ms": value} for value in (True, -1, 10001, "1", 1.5)):
            self.assertEqual(self.http("/__proof/control", value)[0], 400)
        self.assertEqual(self.http("/__proof/control", {"response_status": 500, "after_first_chunk_delay_ms": -1})[0], 400)
        self.assertEqual(self.http("/__proof/requests")[1]["control"], DEFAULT)
        self.controls({"response_status": 500, "after_first_chunk_delay_ms": 10000})
        self.assertEqual(self.http("/__proof/reset", {})[0], 200)
        self.assertEqual(self.http("/__proof/requests")[1], {"synthetic": True, "requests": [], "control": DEFAULT})

    def test_native_task_union_is_json_format_only_and_title_mode_keeps_precedence(self):
        self.controls({"native_tasks_mode": True})
        ordinary = self.payload()
        status, primary = self.http("/v1/chat/completions", ordinary)
        self.assertEqual((status, primary["choices"][0]["message"]["content"]), (200, "Proof"))
        task = self.payload()
        task["response_format"] = {"type": "json_object"}
        status, result = self.http("/v1/chat/completions", task)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(result["choices"][0]["message"]["content"]),
                         {"title": "Proof", "tags": ["Proof"], "follow_ups": ["Proof"]})
        row = self.wait_row(lambda stage: stage["terminal"], identifier=result["id"])
        self.assertEqual(row["response"], result)
        self.assertEqual(row["usage"], USAGE)
        self.controls({"title_mode": True})
        _, title = self.http("/v1/chat/completions", task)
        self.assertEqual(title["choices"][0]["message"]["content"], '{"title":"Proof"}')
        self.assertEqual(self.wait_row(lambda stage: stage["terminal"], identifier=title["id"])["response"], title)

    def test_response_receipt_exists_only_after_a_successful_nonstream_write_and_new_mode_is_optional(self):
        self.controls({"native_tasks_mode": True, "delay_ms": 200})
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.http, "/v1/chat/completions", self.payload())
            row = self.wait_row(lambda stage: stage["stage"] == "before_headers_delay")
            self.assertNotIn("response", row)
            _, result = pending.result(timeout=4)
        self.assertEqual(self.wait_row(lambda stage: stage["terminal"], identifier=result["id"])["response"], result)
        self.controls({"response_status": 500, "delay_ms": 0})
        _, failed = self.http("/v1/chat/completions", self.payload())
        self.assertNotIn("response", self.wait_row(lambda stage: stage["terminal"], identifier=failed["id"]))
        for value in (0, 1, "true", [], {}):
            self.assertEqual(self.http("/__proof/control", {"native_tasks_mode": value})[0], 400)
        self.assertEqual(self.http("/__proof/reset", {})[0], 200)
        self.assertEqual(self.http("/__proof/requests")[1]["control"], DEFAULT)

    def test_optional_null_removal_restores_exact_presence_and_keeps_all_completed_requests(self):
        for optional in ({}, {"native_tasks_mode": False, "response_status": 200, "after_first_chunk_delay_ms": 0}):
            self.controls({**DEFAULT, **{key: None for key in P.OPTIONAL_CONTROLS}, **optional})
            original = self.http("/__proof/requests")[1]["control"]
            _, response = self.http("/v1/chat/completions", self.payload())
            self.wait_row(lambda stage: stage["terminal"], identifier=response["id"])
            receipts = self.http("/__proof/requests")[1]["requests"]
            self.controls({"native_tasks_mode": True, "delay_ms": 1500, "response_status": 500,
                           "after_first_chunk_delay_ms": 10000})
            self.controls({**original, **{key: None for key in P.OPTIONAL_CONTROLS if key not in original}})
            actual = self.http("/__proof/requests")[1]
            self.assertEqual(actual["control"], original)
            self.assertEqual(actual["requests"], receipts)

    def test_optional_deletion_is_atomic_and_null_cannot_remove_mandatory_or_unknown_controls(self):
        self.controls({"native_tasks_mode": True, "response_status": 500})
        original = self.http("/__proof/requests")[1]
        for key in (*DEFAULT, "unknown"):
            self.assertEqual(self.http("/__proof/control", {"native_tasks_mode": None, key: None})[0], 400)
            self.assertEqual(self.http("/__proof/requests")[1], original)


if __name__ == "__main__":
    unittest.main()
