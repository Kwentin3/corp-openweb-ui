"""Owned loopback HTTP plus cached native parsers; no proxy/paid inference."""
import ast
import copy
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
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

try:
    from openai.types.responses import Response, ResponseStreamEvent
    from pydantic import TypeAdapter
except ImportError:
    Response = ResponseStreamEvent = TypeAdapter = None


SPEC = importlib.util.spec_from_file_location("responses_provider_under_test", Path(__file__).with_name("mock_provider.py"))
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
REPO = Path(__file__).resolve().parents[2]
NATIVE = Path(os.environ.get("GOAL584_NATIVE_SOURCE_ROOT", str(REPO / "local/goal584/cost-display/open-webui/backend/open_webui")))
HAS_NATIVE = all((NATIVE / path).is_file() for path in ("utils/middleware.py", "routers/openai.py"))
DEFAULT = {"prompt_tokens": 10, "completion_tokens": 5, "delay_ms": 0, "tool_round": False,
           "admin_mode": False, "title_mode": False}
USAGE = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
         "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}
TOOL = {"type": "function", "name": "fixture_budget_echo", "description": "Synthetic local Tool",
        "parameters": {"type": "object", "properties": {}}, "strict": False}


def native_parsers():
    """Execute exact cached pure native functions, not an imitation of parsing."""
    env = {"JSONCodec": SimpleNamespace(dumps=json.dumps)}
    for relative, names in (("utils/middleware.py", {"deep_merge", "handle_responses_streaming_event"}),
                            ("routers/openai.py", {"convert_responses_result"})):
        nodes = [node for node in ast.parse((NATIVE / relative).read_bytes()).body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
        if len(nodes) != len(names):
            raise AssertionError("Exact cached native parser functions unavailable")
        exec(compile(ast.Module(body=nodes, type_ignores=[]), relative, "exec"), env)
    return env


def native_payload(body):
    env = {"JSONCodec": SimpleNamespace(dumps=json.dumps)}
    nodes = [node for node in ast.parse((NATIVE / "routers/openai.py").read_bytes()).body
             if isinstance(node, ast.FunctionDef) and node.name in {"_normalize_stored_item", "convert_to_responses_payload"}
             or isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
             and node.target.id == "RESPONSES_ALLOWED_FIELDS"]
    if len(nodes) != 3:
        raise AssertionError("Exact cached native converter unavailable")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "routers/openai.py", "exec"), env)
    return env["convert_to_responses_payload"](copy.deepcopy(body))


class ResponsesHTTPTests(unittest.TestCase):
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
            raise AssertionError("Owned Responses HTTP server remained alive")

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

    def payload(self, **changes):
        return {"model": P.RESPONSES_MODEL, "input": [{"role": "user", "content": [{"type": "input_text", "text": "Hi"}]}],
                "instructions": "Synthetic policy\nSynthetic template", "max_output_tokens": 16,
                "stream": False, "tools": [copy.deepcopy(TOOL)], **changes}

    def rows(self):
        _, result = self.http("/__proof/requests")
        self.assertNotIn("synthetic-not-recorded", json.dumps(result))
        return result["requests"]

    def terminal(self, identifier):
        deadline = time.monotonic() + 4
        while True:
            rows = [row for row in self.rows() if row["id"] == identifier]
            if len(rows) == 1 and rows[0]["lifecycle"]["terminal"]:
                return rows[0]
            if time.monotonic() >= deadline:
                self.fail("Provider terminal lifecycle not observed")
            threading.Event().wait(.005)

    def events(self, raw):
        self.assertNotIn("[DONE]", raw)
        events = []
        for frame in raw.strip().split("\n\n"):
            event_line, data_line = frame.split("\n")
            event = json.loads(data_line.removeprefix("data: "))
            self.assertEqual(event_line, "event: " + event["type"])
            events.append(event)
        self.assertEqual([v["sequence_number"] for v in events], list(range(len(events))))
        self.assertEqual(events[0]["response"]["status"], "in_progress")
        self.assertIsNone(events[0]["response"]["usage"])
        self.assertEqual(events[-1]["type"], "response.completed")
        return events

    def native_stream(self, events):
        owner, output, meta = native_parsers()["handle_responses_streaming_event"], [], None
        for event in events:
            output, update = owner(copy.deepcopy(event), output)
            if update:
                meta = update
        final = events[-1]["response"]
        self.assertEqual(output, final["output"])
        self.assertEqual(meta, {"usage": USAGE, "done": True, "response_id": final["id"]})
        return final

    def stream_result(self, raw):
        return self.events(raw)[-1]["response"]

    def test_json_text_retains_full_synthetic_input_and_uses_existing_history(self):
        payload = self.payload(temperature=.2, top_p=.9, metadata={"synthetic": "independent-provider-metadata"}, user="fixture")
        status, result = self.http("/v1/responses", payload)
        self.assertEqual(status, 200)
        self.assertEqual(result["usage"], USAGE)
        self.assertEqual(result["output"][0]["content"][0]["text"], "Proof")
        self.assertEqual(result["max_output_tokens"], 16)
        self.assertEqual(result["instructions"], payload["instructions"])
        row = self.terminal(result["id"])
        self.assertEqual(row["body"], payload)
        self.assertEqual(row["response"], result)
        self.assertEqual(row["id_kind"], "provider_response")
        self.assertEqual(row["route"], "/v1/responses")
        self.assertEqual(row["lifecycle"]["outcome"], "completed")
        self.assertTrue(row["lifecycle"]["usage_sent"])

    def test_sse_text_has_ordered_events_actual_final_response_and_lifecycle(self):
        status, raw = self.http("/v1/responses", self.payload(stream=True))
        self.assertEqual(status, 200)
        events = self.events(raw)
        final = events[-1]["response"]
        self.assertEqual(next(v["delta"] for v in events if v["type"] == "response.output_text.delta"), "Proof")
        row = self.terminal(final["id"])
        self.assertEqual(row["response"], final)
        self.assertEqual(row["lifecycle"]["chunks_sent"], len(events))

    def test_function_call_and_actual_output_round_json_and_sse(self):
        self.http("/__proof/control", {"tool_round": True})
        for stream in (False, True):
            with self.subTest(stream=stream):
                payload = self.payload(stream=stream)
                status, first = self.http("/v1/responses", payload)
                self.assertEqual(status, 200)
                first = self.stream_result(first) if stream else first
                call = first["output"][0]
                self.assertEqual((call["type"], call["name"], call["arguments"]), ("function_call", TOOL["name"], "{}"))
                followup = {**payload, "input": payload["input"] + [call, {"type": "function_call_output",
                    "call_id": call["call_id"], "output": "synthetic budget_echo result"}]}
                status, final = self.http("/v1/responses", followup)
                self.assertEqual(status, 200)
                final = self.stream_result(final) if stream else final
                self.assertEqual(final["output"][0]["type"], "message")
                self.assertEqual(final["output"][0]["content"][0]["text"], "Proof")
                self.assertEqual(self.terminal(final["id"])["body"], followup)
        self.assertEqual(len(self.rows()), 4)

    def test_old_tool_result_does_not_complete_new_user_turn(self):
        self.http("/__proof/control", {"tool_round": True})
        history = [{"role": "user", "content": "old"}, {"type": "function_call", "call_id": "call_old", "name": TOOL["name"], "arguments": "{}"},
            {"type": "function_call_output", "call_id": "call_old", "output": "old result"}, {"role": "user", "content": "Hi"}]
        status, result = self.http("/v1/responses", self.payload(input=history))
        self.assertEqual(status, 200)
        self.assertEqual(result["output"][0]["type"], "function_call")

    def test_ambiguous_or_disabled_tool_never_guesses(self):
        self.http("/__proof/control", {"tool_round": True})
        for change in ({"tools": []}, {"tools": [TOOL, TOOL]}, {"tool_choice": "none"}):
            self.assertEqual(self.http("/v1/responses", self.payload(**change))[1]["output"][0]["type"], "message")

    def test_opaque_reasoning_is_synthetic_and_survives_wire_roundtrip(self):
        payload = self.payload(stream=True, reasoning={"effort": "low", "summary": "auto"}, include=["reasoning.encrypted_content"])
        status, raw = self.http("/v1/responses", payload)
        self.assertEqual(status, 200)
        result = self.stream_result(raw)
        reasoning = result["output"][0]
        self.assertEqual(reasoning["type"], "reasoning")
        self.assertEqual(reasoning["encrypted_content"], "synthetic-opaque-reasoning-not-provider-cryptography")
        replay = self.payload(input=payload["input"] + result["output"] + [{"role": "user", "content": "Continue"}])
        self.assertEqual(self.http("/v1/responses", replay)[0], 200)
        self.assertEqual(self.rows()[-1]["body"], replay)

    @unittest.skipUnless(HAS_NATIVE, "Cached OWUI source unavailable; set GOAL584_NATIVE_SOURCE_ROOT to backend/open_webui")
    def test_actual_native_converter_prepared_context_arrives_without_rewriting(self):
        prepared = {"model": P.RESPONSES_MODEL, "messages": [
            {"role": "system", "content": "Synthetic policy\nSynthetic template"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_synthetic", "type": "function",
                "function": {"name": TOOL["name"], "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_synthetic", "content": "synthetic budget_echo result"}],
            "tools": [{"type": "function", "function": {key: value for key, value in TOOL.items() if key != "type"}}],
            "reasoning": {"effort": "low", "summary": "auto"}, "max_tokens": 16, "stream": True,
            "stream_options": {"include_usage": True}}
        wire = native_payload(prepared)
        self.assertEqual(wire["instructions"], prepared["messages"][0]["content"])
        self.assertEqual(wire["max_output_tokens"], 16)
        self.assertEqual(wire["input"][-1], {"type": "function_call_output", "call_id": "call_synthetic", "output": "synthetic budget_echo result"})
        self.assertNotIn("messages", wire)
        status, raw = self.http("/v1/responses", wire)
        self.assertEqual(status, 200)
        result = self.native_stream(self.events(raw))
        self.assertEqual(self.terminal(result["id"])["body"], wire)

    @unittest.skipUnless(HAS_NATIVE, "Cached OWUI source unavailable; set GOAL584_NATIVE_SOURCE_ROOT to backend/open_webui")
    def test_cached_native_stream_and_json_owners_parse_actual_text_tool_and_reasoning(self):
        self.http("/__proof/control", {"tool_round": True})
        for change in ({"tools": []}, {}, {"reasoning": {"effort": "low"}, "include": ["reasoning.encrypted_content"]}):
            status, raw = self.http("/v1/responses", self.payload(stream=True, **change))
            self.assertEqual(status, 200)
            result = self.native_stream(self.events(raw))
            native = native_parsers()["convert_responses_result"](result)
            choice = native["choices"][0]
            if change.get("tools") == []:
                self.assertEqual(choice, {"index": 0, "message": {"role": "assistant", "content": "Proof"}, "finish_reason": "stop"})
            else:
                call = next(item for item in result["output"] if item["type"] == "function_call")
                self.assertEqual(choice["finish_reason"], "tool_calls")
                self.assertEqual(choice["message"]["tool_calls"][0]["id"], call["call_id"])

    @unittest.skipUnless(Response is not None, "Optional installed OpenAI/Pydantic schemas unavailable; no dependency is installed by this test")
    def test_installed_sdk_schemas_accept_actual_json_and_sse_text_tool_reasoning(self):
        self.http("/__proof/control", {"tool_round": True})
        for change in ({"tools": []}, {}, {"reasoning": {"effort": "low"}, "include": ["reasoning.encrypted_content"]}):
            status, result = self.http("/v1/responses", self.payload(**change))
            self.assertEqual(status, 200)
            Response.model_validate(result)
            status, raw = self.http("/v1/responses", self.payload(stream=True, **change))
            self.assertEqual(status, 200)
            for event in self.events(raw):
                TypeAdapter(ResponseStreamEvent).validate_python(event)

    def test_peer_disconnect_after_created_never_claims_completed_response_or_usage(self):
        self.http("/__proof/control", {"after_first_chunk_delay_ms": 250})
        payload = json.dumps(self.payload(stream=True)).encode()
        sock = socket.create_connection(("127.0.0.1", self.server.server_port), timeout=5)
        reader = None
        try:
            headers = ("POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n"
                       "Connection: close\r\nContent-Length: " + str(len(payload)) + "\r\n\r\n")
            sock.sendall(headers.encode() + payload)
            reader = sock.makefile("rb")
            while reader.readline() != b"\r\n":
                pass
            self.assertEqual(reader.readline(), b"event: response.created\n")
            event = json.loads(reader.readline().removeprefix(b"data: "))
            self.assertIsNone(event["response"]["usage"])
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("hh" if os.name == "nt" else "ii", 1, 0))
        finally:
            if reader:
                reader.close()
            sock.close()
        row = self.terminal(event["response"]["id"])
        self.assertEqual(row["lifecycle"]["outcome"], "client_disconnected")
        self.assertFalse(row["lifecycle"]["usage_sent"])
        self.assertNotIn("response", row)

    def test_invalid_or_out_of_profile_requests_fail_without_call_record(self):
        invalid = [{"max_output_tokens": v} for v in (5, 17, True, "16")]
        invalid += [{"input": v} for v in (None, "", [], [1], [{"role": "tool", "content": "bad"}],
            [{"type": "function_call_output", "call_id": "orphan", "output": "result"}],
            [{"type": "input_image"}], "\ud800")]
        invalid += [{"previous_response_id": "resp_prior"}, {"store": True}, {"background": True}, {"stream": 1},
            {"tools": [{"type": "web_search"}]}, {"parallel_tool_calls": 1}, {"truncation": "auto"},
            {"unexpected": True}, {"text": {"format": {"type": "json_object"}}}]
        for change in invalid:
            with self.subTest(keys=list(change)):
                self.assertEqual(self.http("/v1/responses", self.payload(**change))[0], 400)
        self.assertEqual(self.http("/v1/responses", self.payload(model=P.MODELS[0]))[0], 404)
        self.assertEqual(self.http("/v1/chat/completions", {"model": P.RESPONSES_MODEL, "messages": [{"role": "user", "content": "Hi"}]})[0], 404)
        self.assertEqual(self.rows(), [])

    def test_existing_controls_delay_and_error_are_arrival_snapshots(self):
        self.http("/__proof/control", {"response_status": 500, "delay_ms": 200})
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.http, "/v1/responses", self.payload())
            deadline = time.monotonic() + 3
            while not (rows := self.rows()) or rows[0]["lifecycle"]["stage"] != "before_headers_delay":
                if time.monotonic() >= deadline:
                    self.fail("Provider arrival not observed")
                threading.Event().wait(.005)
            self.assertFalse(pending.done())
            self.http("/__proof/control", {"response_status": 200, "delay_ms": 0})
            status, result = pending.result(timeout=4)
        self.assertEqual(status, 500)
        row = self.terminal(result["id"])
        self.assertIsNone(row["usage"])
        self.assertNotIn("response", row)
        self.assertEqual(row["lifecycle"]["outcome"], "controlled_error")
        self.assertFalse(row["lifecycle"]["usage_sent"])

    def test_existing_default_catalog_chat_and_embedding_contracts_stay_separate(self):
        self.assertEqual(self.http("/__proof/requests")[1]["control"], DEFAULT)
        self.assertEqual([v["id"] for v in self.http("/v1/models")[1]["data"]], list(P.MODELS))
        self.http("/__proof/control", {"prompt_tokens": 30, "completion_tokens": 20})
        _, chat = self.http("/v1/chat/completions", {"model": P.MODELS[0], "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5})
        self.assertEqual(chat["usage"], {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50})
        _, response = self.http("/v1/responses", self.payload())
        self.assertEqual(response["usage"], USAGE)
        _, embedding = self.http("/v1/embeddings", {"model": P.EMBEDDING_MODEL, "input": "Hi"})
        self.assertEqual(embedding["usage"], {"prompt_tokens": 10, "total_tokens": 10})
        self.assertNotIn("id", embedding)


if __name__ == "__main__":
    unittest.main()
