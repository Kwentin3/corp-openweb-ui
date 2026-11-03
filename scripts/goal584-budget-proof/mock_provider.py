"""Stdlib-only, synthetic OpenAI-compatible boundary; never a budget authority.

This process has no provider credentials or paid destination. Receipts contain
synthetic request bodies, not Authorization headers. Proof controls are internal
to the disposable network and are deliberately not a public application API.
"""

import argparse
import base64
import copy
import hashlib
import json
import re
import struct
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MODELS = ("goal584-fake-a", "goal584-fake-b")
EMBEDDING_MODEL = "goal584-fake-e"
STATE_LOCK = threading.Lock()
REQUESTS = []
CONTROL = {"prompt_tokens": 10, "completion_tokens": 5, "delay_ms": 0, "tool_round": False,
           "admin_mode": False, "title_mode": False}
OPTIONAL_CONTROLS = frozenset({"native_tasks_mode", "response_status", "after_first_chunk_delay_ms"})


def pending_tool_name(payload, messages):
    """Select only an unambiguous exposed proof Tool for the current user turn."""
    tools = payload.get("tools")
    if not isinstance(tools, list):
        return None
    names = [tool["function"]["name"] for tool in tools
             if isinstance(tool, dict) and tool.get("type") == "function"
             and isinstance(tool.get("function"), dict)
             and isinstance(tool["function"].get("name"), str)
             and tool["function"]["name"].endswith("budget_echo")]
    if len(names) != 1:
        return None
    last_user = next((index for index in range(len(messages) - 1, -1, -1)
                      if messages[index].get("role") == "user"), None)
    if last_user is None or any(message.get("role") == "tool" for message in messages[last_user + 1:]):
        return None
    return names[0]


def pending_admin_tool(payload, messages):
    """Route synthetic admin turns only; the real Tool owns plan validation.

    No business values become model-supplied apply arguments. Tool results from
    earlier turns cannot complete the current turn, and any result in this turn
    ends its synthetic tool round. Never guess absent or ambiguous tool names.
    """
    last_user = next((index for index in range(len(messages) - 1, -1, -1)
                      if messages[index].get("role") == "user"), None)
    if last_user is None or any(message.get("role") == "tool" for message in messages[last_user + 1:]):
        return None
    text = messages[last_user].get("content")
    if isinstance(text, list) and len(text) == 1 and isinstance(text[0], dict) and text[0].get("type") == "text":
        text = text[0].get("text")
    if not isinstance(text, str) or not 0 < len(text.encode("utf-8")) <= 64 * 1024:
        return None
    try:
        proposal = json.loads(text)
    except ValueError:
        intent = text.casefold()
        if not (re.search(r"\b(?:настро\w*|обнов\w*)\b", intent)
                and re.search(r"\b(?:лимит\w*|бюджет\w*)\b", intent)):
            return None
        suffix, arguments = "open_budget_form", {"view_json": "{}"}
    else:
        if not (isinstance(proposal, dict) and type(proposal.get("schema")) is int
                and proposal["schema"] == 1 and proposal.get("type") in (
                    "employee_budget_plan", "employee_budget_template", "employee_budget_initialize")):
            return None
        suffix, arguments = "apply_budget_form", {}
    tools = payload.get("tools")
    if not isinstance(tools, list):
        return None
    names = [tool["function"]["name"] for tool in tools
             if isinstance(tool, dict) and tool.get("type") == "function"
             and isinstance(tool.get("function"), dict)
             and isinstance(tool["function"].get("name"), str)
             and tool["function"]["name"].endswith(suffix)]
    return (names[0], arguments) if len(names) == 1 else None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *args):
        # Do not log bearer keys, prompts, or arbitrary paths.
        pass

    def mark(self, record, *, stage, terminal=False, outcome=None, **fields):
        with STATE_LOCK:
            record["lifecycle"].update(stage=stage, **fields)
            if terminal:
                record["lifecycle"].update(terminal=True, outcome=outcome,
                                           terminal_monotonic=time.monotonic())

    def send_json(self, status, payload, *, record=None):
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if record is not None:
            self.mark(record, stage="headers_sent", headers_sent=True)
        self.wfile.write(data)
        self.wfile.flush()

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 1_048_576:
            raise ValueError("A bounded JSON object is required")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object")
        return payload

    def begin_record(self, payload, *, embedding=False):
        with STATE_LOCK:
            control = dict(CONTROL)
            usage = ({"prompt_tokens": 10, "total_tokens": 10} if embedding else {
                "prompt_tokens": control["prompt_tokens"], "completion_tokens": control["completion_tokens"],
                "total_tokens": control["prompt_tokens"] + control["completion_tokens"]})
            record = {"id": ("embedding-observation-goal584-" if embedding else "chatcmpl-goal584-") + uuid.uuid4().hex,
                "created": int(time.time()), "body": payload, "usage": usage,
                "lifecycle": {"started": True, "stage": "started", "started_monotonic": time.monotonic(),
                    "headers_sent": False, "chunks_sent": 0, "usage_sent": False, "terminal": False, "outcome": None,
                    "response_status": control.get("response_status", 200), "delay_ms": control["delay_ms"],
                    "after_first_chunk_delay_ms": control.get("after_first_chunk_delay_ms", 0)}}
            if embedding:
                # Not sent to the client: native embedding IDs have another owner.
                record.update(route="/v1/embeddings", id_kind="provider_observation_only")
            if control.get("response_status") == 500:
                record["usage"] = None
            REQUESTS.append(record)
        return control, record

    def controlled_failure(self, control, record, *, embedding=False):
        if control["delay_ms"]:
            self.mark(record, stage="before_headers_delay")
            time.sleep(control["delay_ms"] / 1000)
        if control.get("response_status") != 500:
            return False
        error = {"error": {"message": "Controlled synthetic provider failure",
                 "type": "synthetic_provider_error", "code": "proof_provider_500"}}
        if not embedding:
            error["id"] = record["id"]
        try:
            self.send_json(500, error, record=record)
            self.mark(record, stage="controlled_error", terminal=True, outcome="controlled_error")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.mark(record, stage="client_disconnected", terminal=True, outcome="client_disconnected")
        return True

    def embeddings(self, payload):
        if payload.get("model") != EMBEDDING_MODEL:
            return self.send_json(404, {"error": {"message": "Unknown synthetic model", "code": "model_not_found"}})
        values = payload.get("input")
        values = [values] if isinstance(values, str) else values
        dimensions, encoding = payload.get("dimensions", 3), payload.get("encoding_format", "float")
        try:
            encoded_values = ([value.encode("utf-8") for value in values]
                if isinstance(values, list) and 0 < len(values) <= 128 and all(isinstance(value, str) for value in values) else [])
        except UnicodeEncodeError:
            encoded_values = []
        if not (isinstance(values, list) and 0 < len(values) <= 128
                and len(encoded_values) == len(values) and all(0 < len(value) <= 16384 for value in encoded_values)
                and sum(map(len, encoded_values)) <= 131072
                and type(dimensions) is int and 1 <= dimensions <= 64
                and encoding in ("float", "base64")
                and ("user" not in payload or isinstance(payload["user"], str) and len(payload["user"]) <= 256)):
            return self.send_json(400, {"error": {"message": "Invalid bounded synthetic embedding input"}})
        control, record = self.begin_record(payload, embedding=True)
        if self.controlled_failure(control, record, embedding=True):
            return
        data = []
        for index, value in enumerate(encoded_values):
            seed = hashlib.sha512(value).digest()
            vector = [(seed[i] + 1) / 256 for i in range(dimensions)]
            encoded = base64.b64encode(struct.pack("<" + "f" * dimensions, *vector)).decode("ascii") if encoding == "base64" else vector
            data.append({"object": "embedding", "index": index, "embedding": encoded})
        result = {"object": "list", "data": data, "model": EMBEDDING_MODEL, "usage": record["usage"]}
        try:
            self.send_json(200, result, record=record)
            with STATE_LOCK:
                record["response"] = copy.deepcopy(result)
            self.mark(record, stage="completed", terminal=True, outcome="completed", usage_sent=True)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.mark(record, stage="client_disconnected", terminal=True, outcome="client_disconnected")

    def do_GET(self):
        if self.path == "/healthz":
            return self.send_json(200, {"ok": True, "synthetic": True})
        if self.path == "/v1/models":
            return self.send_json(200, {"object": "list", "data": [
                {"id": model, "object": "model", "created": 0, "owned_by": "goal584-proof"}
                for model in MODELS
            ]})
        if self.path == "/__proof/requests":
            with STATE_LOCK:
                result = {"synthetic": True, "requests": copy.deepcopy(REQUESTS), "control": dict(CONTROL)}
            return self.send_json(200, result)
        self.send_json(404, {"error": {"message": "Unknown synthetic endpoint"}})

    def do_POST(self):
        try:
            payload = self.read_json()
        except (ValueError, UnicodeDecodeError) as error:
            return self.send_json(400, {"error": {"message": str(error)}})
        if self.path == "/__proof/reset":
            with STATE_LOCK:
                REQUESTS.clear()
                CONTROL.clear()
                CONTROL.update(prompt_tokens=10, completion_tokens=5, delay_ms=0, tool_round=False,
                               admin_mode=False, title_mode=False)
            return self.send_json(200, {"ok": True})
        if self.path == "/__proof/control":
            limits = {"prompt_tokens": (0, 10000), "completion_tokens": (0, 10000), "delay_ms": (0, 10000),
                      "after_first_chunk_delay_ms": (0, 10000)}
            if not payload or any(
                (False if key in OPTIONAL_CONTROLS and value is None else
                 type(value) is not bool if key in ("tool_round", "admin_mode", "title_mode", "native_tasks_mode") else
                 type(value) is not int or value not in (200, 500) if key == "response_status" else
                 key not in limits or type(value) is not int or not limits[key][0] <= value <= limits[key][1])
                for key, value in payload.items()
            ):
                return self.send_json(400, {"error": {"message": "Invalid proof control"}})
            with STATE_LOCK:
                for key, value in payload.items():
                    if value is None:
                        CONTROL.pop(key, None)
                    else:
                        CONTROL[key] = value
                result = dict(CONTROL)
            return self.send_json(200, result)
        if self.path == "/v1/embeddings":
            return self.embeddings(payload)
        if self.path != "/v1/chat/completions":
            return self.send_json(404, {"error": {"message": "Unknown synthetic endpoint"}})
        model = payload.get("model")
        if model not in MODELS:
            return self.send_json(404, {"error": {"message": "Unknown synthetic model", "code": "model_not_found"}})
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages or not all(isinstance(message, dict) for message in messages):
            return self.send_json(400, {"error": {"message": "messages must be a non-empty object list"}})
        control, record = self.begin_record(payload)
        call_id, created = record["id"], record["created"]
        if self.controlled_failure(control, record):
            return
        usage = {"prompt_tokens": control["prompt_tokens"], "completion_tokens": control["completion_tokens"],
                 "total_tokens": control["prompt_tokens"] + control["completion_tokens"]}
        native_task = (control.get("native_tasks_mode", False)
                       and payload.get("response_format") == {"type": "json_object"})
        if control["title_mode"] or native_task:
            selection = None
        elif control["admin_mode"]:
            selection = pending_admin_tool(payload, messages)
        else:
            name = pending_tool_name(payload, messages) if control["tool_round"] else None
            selection = (name, {}) if name else None
        tool_name, tool_arguments = selection if selection else (None, None)
        tool_call = {"id": "call-goal584-" + uuid.uuid4().hex, "type": "function",
                     "function": {"name": tool_name, "arguments": json.dumps(tool_arguments, separators=(",", ":"))}} if tool_name else None
        content = ('{"title":"Proof"}' if control["title_mode"] else
                   '{"title":"Proof","tags":["Proof"],"follow_ups":["Proof"]}' if native_task else "Proof")
        message = {"role": "assistant", "content": None, "tool_calls": [tool_call]} if tool_call else {
            "role": "assistant", "content": content}
        finish_reason = "tool_calls" if tool_call else "stop"
        result = {"id": call_id, "object": "chat.completion", "created": created, "model": model,
                  "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
                  "usage": usage}
        if not payload.get("stream"):
            try:
                self.send_json(200, result, record=record)
                # This is the actual successful synthetic wire response, not a
                # reconstructed expected answer or a billing authority.
                with STATE_LOCK:
                    record["response"] = copy.deepcopy(result)
                self.mark(record, stage="completed", terminal=True, outcome="completed", usage_sent=True)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.mark(record, stage="client_disconnected", terminal=True, outcome="client_disconnected")
            return
        base = {"id": call_id, "object": "chat.completion.chunk", "created": created, "model": model}
        delta = {"role": "assistant", "content": None, "tool_calls": [{"index": 0, **tool_call}]} if tool_call else {
            "role": "assistant", "content": message["content"]}
        chunks = [
            {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
            {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]},
            {**base, "choices": [], "usage": usage},
        ]
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.mark(record, stage="headers_sent", headers_sent=True)
            for index, chunk in enumerate(chunks):
                self.wfile.write(("data: " + json.dumps(chunk, separators=(",", ":")) + "\n\n").encode("utf-8"))
                self.wfile.flush()
                self.mark(record, stage="streaming", chunks_sent=index + 1, usage_sent="usage" in chunk)
                if index == 0 and control.get("after_first_chunk_delay_ms", 0):
                    self.mark(record, stage="after_first_chunk_delay")
                    time.sleep(control["after_first_chunk_delay_ms"] / 1000)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.mark(record, stage="completed", terminal=True, outcome="completed")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.mark(record, stage="client_disconnected", terminal=True, outcome="client_disconnected")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with ThreadingHTTPServer((args.host, args.port), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
