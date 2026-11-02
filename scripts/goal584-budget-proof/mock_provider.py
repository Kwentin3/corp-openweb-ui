"""Stdlib-only, synthetic OpenAI-compatible boundary; never a budget authority.

This process has no provider credentials or paid destination. Receipts contain
synthetic request bodies, not Authorization headers. Proof controls are internal
to the disposable network and are deliberately not a public application API.
"""

import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MODELS = ("goal584-fake-a", "goal584-fake-b")
STATE_LOCK = threading.Lock()
REQUESTS = []
CONTROL = {"prompt_tokens": 10, "completion_tokens": 5, "delay_ms": 0, "tool_round": False}


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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *args):
        # Do not log bearer keys, prompts, or arbitrary paths.
        pass

    def send_json(self, status, payload):
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 1_048_576:
            raise ValueError("A bounded JSON object is required")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object")
        return payload

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
                result = {"synthetic": True, "requests": list(REQUESTS), "control": dict(CONTROL)}
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
                CONTROL.update(prompt_tokens=10, completion_tokens=5, delay_ms=0, tool_round=False)
            return self.send_json(200, {"ok": True})
        if self.path == "/__proof/control":
            limits = {"prompt_tokens": (0, 10000), "completion_tokens": (0, 10000), "delay_ms": (0, 10000)}
            if not payload or any(
                (type(value) is not bool if key == "tool_round" else
                 key not in limits or type(value) is not int or not limits[key][0] <= value <= limits[key][1])
                for key, value in payload.items()
            ):
                return self.send_json(400, {"error": {"message": "Invalid proof control"}})
            with STATE_LOCK:
                CONTROL.update(payload)
                result = dict(CONTROL)
            return self.send_json(200, result)
        if self.path != "/v1/chat/completions":
            return self.send_json(404, {"error": {"message": "Unknown synthetic endpoint"}})
        model = payload.get("model")
        if model not in MODELS:
            return self.send_json(404, {"error": {"message": "Unknown synthetic model", "code": "model_not_found"}})
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages or not all(isinstance(message, dict) for message in messages):
            return self.send_json(400, {"error": {"message": "messages must be a non-empty object list"}})
        call_id = "chatcmpl-goal584-" + uuid.uuid4().hex
        created = int(time.time())
        with STATE_LOCK:
            control = dict(CONTROL)
            REQUESTS.append({"id": call_id, "created": created, "body": payload, "usage": {
                "prompt_tokens": control["prompt_tokens"], "completion_tokens": control["completion_tokens"],
                "total_tokens": control["prompt_tokens"] + control["completion_tokens"],
            }})
        if control["delay_ms"]:
            time.sleep(control["delay_ms"] / 1000)
        usage = {"prompt_tokens": control["prompt_tokens"], "completion_tokens": control["completion_tokens"],
                 "total_tokens": control["prompt_tokens"] + control["completion_tokens"]}
        tool_name = pending_tool_name(payload, messages) if control["tool_round"] else None
        tool_call = {"id": "call-goal584-" + uuid.uuid4().hex, "type": "function",
                     "function": {"name": tool_name, "arguments": "{}"}} if tool_name else None
        message = {"role": "assistant", "content": None, "tool_calls": [tool_call]} if tool_call else {
            "role": "assistant", "content": "Proof"}
        finish_reason = "tool_calls" if tool_call else "stop"
        result = {"id": call_id, "object": "chat.completion", "created": created, "model": model,
                  "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
                  "usage": usage}
        if not payload.get("stream"):
            return self.send_json(200, result)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        base = {"id": call_id, "object": "chat.completion.chunk", "created": created, "model": model}
        delta = {"role": "assistant", "content": None, "tool_calls": [{"index": 0, **tool_call}]} if tool_call else {
            "role": "assistant", "content": "Proof"}
        chunks = [
            {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
            {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]},
            {**base, "choices": [], "usage": usage},
        ]
        try:
            for chunk in chunks:
                self.wfile.write(("data: " + json.dumps(chunk, separators=(",", ":")) + "\n\n").encode("utf-8"))
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with ThreadingHTTPServer((args.host, args.port), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
