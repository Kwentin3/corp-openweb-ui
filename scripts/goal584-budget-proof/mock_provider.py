"""Stdlib-only, synthetic OpenAI-compatible boundary; never a budget authority.

This process has no provider credentials or paid destination. Receipts contain
synthetic request bodies, not Authorization headers. Proof controls are internal
to the disposable network and are deliberately not a public application API.
"""

import argparse
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MODELS = ("goal584-fake-a", "goal584-fake-b")
EMBEDDING_MODEL = "goal584-fake-e"
RESPONSES_MODEL = "goal584-fake-r"
OFFICE_MODEL = "goal584-fake-office"
OFFICE_SERVICE_MODEL = "goal584-fake-office-service"
USAGE_MODELS = ("goal584-fake-usage", "goal584-fake-usage-absent", "goal584-fake-usage-null")
RESPONSES_MAX_OUTPUT_TOKENS = 16
STATE_LOCK = threading.Lock()
REQUESTS = []
CONTROL = {"prompt_tokens": 10, "completion_tokens": 5, "delay_ms": 0, "tool_round": False,
           "admin_mode": False, "title_mode": False}
OPTIONAL_CONTROLS = frozenset({"native_tasks_mode", "response_status", "after_first_chunk_delay_ms"})

CATALOG_REVISION = "d665dc1a6315847fcad6cc2c1264ceb47c06abce"
CATALOG_BACKUP_SHA256 = "329113e5820834dc2a206500db9ec7861a17c74b86fe79601dec05478c06327e"
CATALOG_BACKUP_NAME = "model_prices_and_context_window_backup.json"
CATALOG_MAX_BYTES = 8 * 1024 * 1024
CATALOG_VARIANTS = ("S1", "S2", "invalid", "truncated")


class CatalogFixture:
    """Opt-in native fetch data, independent of physical inference observations."""

    def __init__(self):
        override = os.environ.get("PROOF_CATALOG_CORPUS_PATH")
        if override:
            source = Path(override)
        else:
            # Top-level spec discovery does not execute LiteLLM's __init__/fetch.
            spec = importlib.util.find_spec("litellm")
            if spec is None or spec.origin is None:
                raise ValueError("Pinned synthetic catalog corpus unavailable")
            source = Path(spec.origin).parent / CATALOG_BACKUP_NAME
        if source.name != CATALOG_BACKUP_NAME or source.is_symlink() or not source.is_file():
            raise ValueError("Invalid synthetic catalog corpus")
        with source.open("rb") as handle:
            raw = handle.read(CATALOG_MAX_BYTES + 1)
        if len(raw) > CATALOG_MAX_BYTES or hashlib.sha256(raw).hexdigest() != CATALOG_BACKUP_SHA256:
            raise ValueError("Pinned synthetic catalog corpus differs")
        corpus = json.loads(raw)
        if not isinstance(corpus, dict) or len(corpus) < 50 or not all(isinstance(v, dict) for v in corpus.values()):
            raise ValueError("Invalid synthetic catalog corpus")
        self.backup_blob = self.git_blob(raw)
        self.backup_count = len(corpus)
        self.documents = {}
        for variant in ("S1", "S2"):
            content = copy.deepcopy(corpus)
            for model in MODELS:
                raised = variant == "S2" and model == "goal584-fake-a"
                content[model] = {"litellm_provider": "openai", "mode": "chat",
                    "max_input_tokens": 10, "max_output_tokens": 5, "max_tokens": 15,
                    "input_cost_per_token": .02 if raised else .01,
                    "output_cost_per_token": .04 if raised else .02}
            self.documents[variant] = json.dumps(content, sort_keys=True, separators=(",", ":"),
                                                  ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.documents.update(invalid=b"[]", truncated=b'{"goal584-fake-a":')
        if any(len(body) > CATALOG_MAX_BYTES for body in self.documents.values()):
            raise ValueError("Synthetic catalog exceeds bound")
        self.reset()

    @staticmethod
    def git_blob(body):
        return hashlib.sha1(b"blob %d\0" % len(body) + body, usedforsecurity=False).hexdigest()

    def reset(self):
        self.variant = "S1"
        self.counts = dict.fromkeys(CATALOG_VARIANTS, 0)

    def observation(self):
        return {"synthetic": True, "variant": self.variant, "native_revision": CATALOG_REVISION,
            "corpus_sha256": CATALOG_BACKUP_SHA256, "corpus_git_blob": self.backup_blob,
            "corpus_entry_count": self.backup_count, "request_count": sum(self.counts.values()),
            "requests_by_variant": dict(self.counts),
            "documents": {name: {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                "native_git_blob": self.git_blob(body), "etag": '"' + hashlib.sha256(body).hexdigest() + '"'}
                for name, body in self.documents.items()}}


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


def responses_input(payload):
    """Bounded stateless text/Tool profile, not a general Responses emulator."""
    allowed = {"model", "input", "instructions", "max_output_tokens", "stream", "tools", "tool_choice",
        "parallel_tool_calls", "reasoning", "include", "store", "metadata", "temperature", "top_p", "text",
        "truncation", "user", "previous_response_id", "background"}
    values = payload.get("input")
    if isinstance(values, str):
        values = [{"type": "message", "role": "user", "content": values}]
    if (set(payload) - allowed or not isinstance(values, list) or not 0 < len(values) <= 128
            or not all(isinstance(item, dict) for item in values)
            or payload.get("max_output_tokens", RESPONSES_MAX_OUTPUT_TOKENS) != RESPONSES_MAX_OUTPUT_TOKENS
            or type(payload.get("max_output_tokens", RESPONSES_MAX_OUTPUT_TOKENS)) is not int
            or type(payload.get("stream", False)) is not bool
            or payload.get("previous_response_id") is not None or payload.get("background", False) is not False
            or payload.get("store", False) is not False or payload.get("tool_choice", "auto") not in ("auto", "none")):
        raise ValueError("Unsupported bounded synthetic Responses request")
    if "instructions" in payload and not isinstance(payload["instructions"], str):
        raise ValueError("Invalid synthetic Responses instructions")
    if "reasoning" in payload and not isinstance(payload["reasoning"], dict):
        raise ValueError("Invalid synthetic Responses reasoning")
    if "metadata" in payload and not isinstance(payload["metadata"], dict):
        raise ValueError("Invalid synthetic Responses metadata")
    if (type(payload.get("parallel_tool_calls", True)) is not bool
            or payload.get("truncation", "disabled") != "disabled"
            or payload.get("text", {"format": {"type": "text"}}) != {"format": {"type": "text"}}
            or ("user" in payload and not isinstance(payload["user"], str))):
        raise ValueError("Unsupported synthetic Responses options")
    include = payload.get("include", [])
    if not isinstance(include, list) or any(value != "reasoning.encrypted_content" for value in include):
        raise ValueError("Unsupported synthetic Responses include")
    tools = payload.get("tools", [])
    if not isinstance(tools, list) or len(tools) > 8 or not all(isinstance(tool, dict) and tool.get("type") == "function"
            and isinstance(tool.get("name"), str) and isinstance(tool.get("parameters"), dict) for tool in tools):
        raise ValueError("Invalid synthetic Responses function tools")
    for item in values:
        kind = item.get("type", "message")
        if kind == "message":
            content = item.get("content")
            if (item.get("role") not in ("user", "assistant", "system", "developer") or not (
                    isinstance(content, str) and content or isinstance(content, list) and content and all(
                        isinstance(part, dict) and part.get("type") in ("input_text", "output_text")
                        and isinstance(part.get("text"), str) for part in content))):
                raise ValueError("Invalid synthetic Responses text input")
        elif kind == "function_call":
            if not (isinstance(item.get("call_id"), str) and item["call_id"] and isinstance(item.get("name"), str)
                    and isinstance(item.get("arguments"), str)):
                raise ValueError("Invalid synthetic Responses function call")
        elif kind == "function_call_output":
            if not (isinstance(item.get("call_id"), str) and item["call_id"] and isinstance(item.get("output"), str)
                    and any(call.get("type") == "function_call" and call.get("call_id") == item["call_id"] for call in values)):
                raise ValueError("Unpaired synthetic Responses function output")
        elif kind == "reasoning":
            if not (isinstance(item.get("id"), str) and isinstance(item.get("summary"), list)
                    and ("encrypted_content" not in item or isinstance(item["encrypted_content"], str))):
                raise ValueError("Invalid synthetic Responses reasoning input")
        else:
            raise ValueError("Unsupported synthetic Responses input item")
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 131072:
        raise ValueError("Synthetic Responses request exceeds bound")
    return values


def responses_tool(payload, values, control):
    if not control["tool_round"] or payload.get("tool_choice") == "none":
        return None
    names = [tool["name"] for tool in payload.get("tools", []) if tool["name"].endswith("budget_echo")]
    if len(names) != 1:
        return None
    last_user = next((index for index in range(len(values) - 1, -1, -1) if values[index].get("role") == "user"), None)
    if last_user is None or any(item.get("type") == "function_call_output" for item in values[last_user + 1:]):
        return None
    return names[0]


def office_service_responses_input(payload):
    """Finite native default follow-up task, with its complete pinned instructions.

    This validates fixture input, not task authentication; ServicePipe owns that.
    Native task generation has no tools, explicit output cap or store field.
    """
    values = responses_input(payload)
    if (set(payload) != {"model", "input", "stream", "reasoning"} or payload["stream"] is not False
            or payload["reasoning"] != {"effort": "none"} or len(values) != 1
            or set(values[0]) != {"type", "role", "content"} or values[0]["type"] != "message"
            or values[0]["role"] != "user" or not isinstance(values[0]["content"], list)
            or len(values[0]["content"]) != 1 or set(values[0]["content"][0]) != {"type", "text"}
            or values[0]["content"][0]["type"] != "input_text"):
        raise ValueError("Invalid finite Office service task")
    prompt = values[0]["content"][0]["text"]
    prefix, marker, history = prompt.partition("<chat_history>\n")
    # DEFAULT_FOLLOW_UP_GENERATION_PROMPT_TEMPLATE at WebUI 6a18585f; no
    # shortened paraphrase can silently replace task instructions in this stand.
    if (not marker or hashlib.sha256((prefix + marker).encode()).hexdigest()
            != "afa89f53427f1a50004c47e96f5f5c1f6e72f3b8187a4b617a05860105d83499"
            or not history.endswith("\n</chat_history>") or not history.startswith("USER: ")
            or "\nASSISTANT: " not in history):
        raise ValueError("Invalid finite Office follow-up context")
    return values


def office_responses_input(payload):
    """Finite Office representation adapter; the original R profile stays strict."""
    tools = payload.get("tools")
    values = payload.get("input")
    if (not isinstance(tools, list) or not 2 <= len(tools) <= 64
            or not all(isinstance(tool, dict) and tool.get("type") == "function"
                and isinstance(tool.get("name"), str) and isinstance(tool.get("parameters"), dict) for tool in tools)
            or len({tool["name"] for tool in tools}) != len(tools)
            or not isinstance(values, list) or not all(isinstance(item, dict) for item in values)
            or type(payload.get("max_output_tokens")) is not int or payload["max_output_tokens"] != 1024
            or payload.get("tool_choice", "auto") != "auto"
            or payload.get("parallel_tool_calls", False) is not False
            or len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 1_048_576):
        raise ValueError("Invalid finite Office Responses profile")
    # Validate every original tool above and every typed result below, then use
    # the existing envelope/text/reasoning validator on a bounded representation.
    # Nothing from this validation copy replaces the captured original payload.
    checked = copy.deepcopy(payload)
    checked["max_output_tokens"] = RESPONSES_MAX_OUTPUT_TOKENS
    checked["tools"] = []
    for item in checked["input"]:
        if item.get("type") == "function_call_output" and isinstance(item.get("output"), list):
            parts = item["output"]
            if not (len(parts) == 2 and all(isinstance(part, dict) for part in parts) and parts[0].get("type") == "input_text"
                    and isinstance(parts[0].get("text"), str)
                    and set(parts[1]) == {"type", "image_url"} and parts[1]["type"] == "input_image"
                    and isinstance(parts[1]["image_url"], str)):
                raise ValueError("Invalid finite Office typed output")
            item["output"] = "Office typed result validated separately"
    responses_input(checked)
    return values


def office_responses_step(payload, values):
    """Synthetic export -> render -> final choice, using only current Tool outputs."""
    names = []
    for suffix in ("export_answer_to_word", "render_office_file"):
        found = [tool["name"] for tool in payload["tools"] if tool["name"].endswith(suffix)]
        if len(found) != 1:
            raise ValueError("Office Tool discovery is ambiguous")
        names.append(found[0])
    last_user = next((i for i in range(len(values) - 1, -1, -1) if values[i].get("role") == "user"), None)
    if last_user is None:
        raise ValueError("Office user turn is missing")
    tail = [item for item in values[last_user + 1:] if item.get("type") != "reasoning"]
    if len(tail) not in (0, 2, 4):
        raise ValueError("Incomplete finite Office Tool continuation")
    export_args = {"output_name": "goal584-office.docx", "source_message": "previous_assistant", "commands": []}
    if not tail:
        return names[0], export_args, None
    for index in range(0, len(tail), 2):
        call, result = tail[index:index + 2]
        if (call.get("type") != "function_call" or call.get("name") != names[index // 2]
                or result.get("type") != "function_call_output" or result.get("call_id") != call.get("call_id")
                or index and call["call_id"] == tail[0]["call_id"]):
            raise ValueError("Unpaired finite Office Tool result")
    if json.loads(tail[0]["arguments"]) != export_args or not isinstance(tail[1]["output"], str):
        raise ValueError("Invalid finite Office export continuation")
    exported = json.loads(tail[1]["output"])
    file_id = exported.get("result_file_id") if isinstance(exported, dict) else None
    if (not isinstance(file_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,128}", file_id)
            or not isinstance(exported.get("result_file"), dict) or exported["result_file"].get("id") != file_id
            or exported.get("download_url") != "/api/v1/files/" + file_id + "/content"
            or exported.get("source_text_preserved") is not True):
        raise ValueError("Native Office export result is missing")
    render_args = {"file_id": file_id, "format": "docx", "grid": 2}
    if len(tail) == 2:
        return names[1], render_args, None
    parts = tail[3]["output"]
    if (json.loads(tail[2]["arguments"]) != render_args or not isinstance(parts, list) or len(parts) != 2
            or parts[0] != {"type": "input_text", "text": names[1] + ": Image file read successfully."}
            or parts[1].get("type") != "input_image" or not isinstance(parts[1].get("image_url"), str)
            or not parts[1]["image_url"].startswith("data:image/png;base64,")):
        raise ValueError("Native Office render continuation is missing")
    png = base64.b64decode(parts[1]["image_url"].split(",", 1)[1], validate=True)
    if len(png) < 24 or not png.startswith(b"\x89PNG\r\n\x1a\n") or png[12:16] != b"IHDR":
        raise ValueError("Native Office PNG is missing")
    return None, None, file_id


def pricing_usage_input(payload, values):
    """One finite nonstreaming Hi; the original wire is never rewritten."""
    if (payload.get("stream", False) is not False or payload.get("tools", []) != []
            or payload.get("reasoning") or payload.get("include")
            or payload.get("max_output_tokens") != RESPONSES_MAX_OUTPUT_TOKENS
            or len(values) != 1 or values[0].get("role") != "user"
            or values[0].get("type", "message") != "message"
            or set(values[0]) - {"type", "role", "content"}
            or values[0].get("content") not in ("Hi", [{"type": "input_text", "text": "Hi"}])):
        raise ValueError("Invalid finite pricing usage request")


def responses_events(result):
    """Native Responses SSE event names/shapes; no Chat [DONE] sentinel."""
    initial = {**copy.deepcopy(result), "status": "in_progress", "output": [], "usage": None}
    events = [{"type": "response.created", "response": initial},
              {"type": "response.in_progress", "response": copy.deepcopy(initial)}]
    for index, item in enumerate(result["output"]):
        start = {**copy.deepcopy(item), "status": "in_progress"}
        if item["type"] == "message":
            start["content"] = []
        elif item["type"] == "function_call":
            start["arguments"] = ""
        events.append({"type": "response.output_item.added", "output_index": index, "item": start})
        identity = {"item_id": item["id"], "output_index": index}
        if item["type"] == "message":
            part = item["content"][0]
            events.extend([
                {"type": "response.content_part.added", **identity, "content_index": 0,
                 "part": {"type": "output_text", "text": "", "annotations": []}},
                {"type": "response.output_text.delta", **identity, "content_index": 0, "delta": part["text"], "logprobs": []},
                {"type": "response.output_text.done", **identity, "content_index": 0, "text": part["text"], "logprobs": []},
                {"type": "response.content_part.done", **identity, "content_index": 0, "part": part},
            ])
        elif item["type"] == "function_call":
            events.extend([
                {"type": "response.function_call_arguments.delta", **identity, "delta": item["arguments"]},
                {"type": "response.function_call_arguments.done", **identity, "name": item["name"], "arguments": item["arguments"]},
            ])
        events.append({"type": "response.output_item.done", "output_index": index, "item": copy.deepcopy(item)})
    events.append({"type": "response.completed", "response": copy.deepcopy(result)})
    return [{**event, "sequence_number": index} for index, event in enumerate(events)]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *args):
        # Do not log bearer keys, prompts, or arbitrary paths.
        pass

    def catalog(self, payload=None):
        if os.environ.get("PROOF_CATALOG_ENABLED") != "true":
            return self.send_json(404, {"error": {"message": "Unknown synthetic endpoint"}})
        try:
            with STATE_LOCK:
                fixture = getattr(self.server, "proof_catalog", None)
                if fixture is None:
                    fixture = CatalogFixture()
                    self.server.proof_catalog = fixture
                if self.command == "POST":
                    if self.path == "/__proof/catalog/reset" and payload == {}:
                        fixture.reset()
                    elif (self.path == "/__proof/catalog/control" and set(payload) == {"variant"}
                          and isinstance(payload["variant"], str) and payload["variant"] in CATALOG_VARIANTS):
                        fixture.variant = payload["variant"]
                    else:
                        return self.send_json(400, {"error": {"message": "Invalid synthetic catalog control"}})
                if self.path == "/__proof/catalog":
                    if sum(fixture.counts.values()) >= 10000:
                        return self.send_json(503, {"error": {"message": "Synthetic catalog request bound"}})
                    body = fixture.documents[fixture.variant]
                    fixture.counts[fixture.variant] += 1
                else:
                    result = fixture.observation()
            if self.path != "/__proof/catalog":
                return self.send_json(200, result)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("ETag", '"' + hashlib.sha256(body).hexdigest() + '"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
        except (OSError, ValueError, ImportError):
            self.send_json(503, {"error": {"message": "Synthetic catalog unavailable"}})

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

    def begin_record(self, payload, *, embedding=False, responses=False):
        with STATE_LOCK:
            control = dict(CONTROL)
            usage = ({"prompt_tokens": 10, "total_tokens": 10} if embedding else {
                "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}} if responses else {
                "prompt_tokens": control["prompt_tokens"], "completion_tokens": control["completion_tokens"],
                "total_tokens": control["prompt_tokens"] + control["completion_tokens"]})
            record = {"id": ("embedding-observation-goal584-" if embedding else "resp_goal584_" if responses else "chatcmpl-goal584-") + uuid.uuid4().hex,
                "created": int(time.time()), "body": payload, "usage": usage,
                "lifecycle": {"started": True, "stage": "started", "started_monotonic": time.monotonic(),
                    "headers_sent": False, "chunks_sent": 0, "usage_sent": False, "terminal": False, "outcome": None,
                    "response_status": control.get("response_status", 200), "delay_ms": control["delay_ms"],
                    "after_first_chunk_delay_ms": control.get("after_first_chunk_delay_ms", 0)}}
            if embedding:
                # Not sent to the client: native embedding IDs have another owner.
                record.update(route="/v1/embeddings", id_kind="provider_observation_only")
            elif responses:
                record.update(route="/v1/responses", id_kind="provider_response")
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

    def serve_responses(self, payload):
        usage_profile = payload.get("model") in USAGE_MODELS
        office = payload.get("model") == OFFICE_MODEL
        office_service = payload.get("model") == OFFICE_SERVICE_MODEL
        if not office_service and not office and not usage_profile and payload.get("model") != RESPONSES_MODEL:
            return self.send_json(404, {"error": {"message": "Unknown synthetic model", "code": "model_not_found"}})
        try:
            values = office_service_responses_input(payload) if office_service else office_responses_input(payload) if office else responses_input(payload)
            selection = office_responses_step(payload, values) if office else None
            if usage_profile:
                pricing_usage_input(payload, values)
        except (ValueError, UnicodeError):
            return self.send_json(400, {"error": {"message": "Invalid bounded synthetic Responses request"}})
        control, record = self.begin_record(payload, responses=True)
        if usage_profile and control.get("response_status") != 500:
            with STATE_LOCK:
                record["usage"] = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                    "input_tokens_details": {"cached_tokens": 6},
                    "output_tokens_details": {"reasoning_tokens": 2}} if payload["model"] == USAGE_MODELS[0] else None
        if self.controlled_failure(control, record):
            return
        name = selection[0] if office else responses_tool(payload, values, control)
        output = []
        if not office_service and (payload.get("reasoning") or "reasoning.encrypted_content" in payload.get("include", [])):
            output.append({"id": "rs_" + uuid.uuid4().hex, "type": "reasoning", "status": "completed",
                "summary": [{"type": "summary_text", "text": "Synthetic fixture reasoning summary"}],
                "encrypted_content": "synthetic-opaque-reasoning-not-provider-cryptography"})
        if name:
            output.append({"id": "fc_" + uuid.uuid4().hex, "type": "function_call", "status": "completed",
                "call_id": "call-goal584-" + uuid.uuid4().hex, "name": name,
                "arguments": json.dumps(selection[1], separators=(",", ":")) if office else "{}"})
        else:
            output.append({"id": "msg_" + uuid.uuid4().hex, "type": "message", "status": "completed", "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps({"follow_ups": ["Prepare a PDF copy of the document.",
                    "Create an Excel version of the table.", "Draft a short email to accompany the file."]}) if office_service else "[Download](/api/v1/files/" + selection[2] + "/content)" if office else "Proof", "annotations": []}]})
        result = {"id": record["id"], "object": "response", "created_at": record["created"], "status": "completed",
            "error": None, "incomplete_details": None, "instructions": payload.get("instructions"),
            "model": OFFICE_SERVICE_MODEL if office_service else OFFICE_MODEL if office else payload["model"] if usage_profile else RESPONSES_MODEL, "output": output, "usage": record["usage"],
            "max_output_tokens": None if office_service else 1024 if office else RESPONSES_MAX_OUTPUT_TOKENS, "parallel_tool_calls": payload.get("parallel_tool_calls", True),
            "tool_choice": payload.get("tool_choice", "auto"), "tools": copy.deepcopy(payload.get("tools", [])),
            "reasoning": None if office_service else copy.deepcopy(payload.get("reasoning")), "store": False, "previous_response_id": None,
            "metadata": copy.deepcopy(payload.get("metadata", {})), "temperature": payload.get("temperature", 1.0),
            "top_p": payload.get("top_p", 1.0), "text": copy.deepcopy(payload.get("text", {"format": {"type": "text"}})),
            "truncation": payload.get("truncation", "disabled"), "user": payload.get("user")}
        if usage_profile and payload["model"] == USAGE_MODELS[1]:
            del result["usage"]
        try:
            if payload.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.mark(record, stage="headers_sent", headers_sent=True)
                for index, event in enumerate(responses_events(result)):
                    self.wfile.write(("event: " + event["type"] + "\ndata: " + json.dumps(event, separators=(",", ":")) + "\n\n").encode())
                    self.wfile.flush()
                    self.mark(record, stage="streaming", chunks_sent=index + 1, usage_sent=event["type"] == "response.completed")
                    if index == 0 and control.get("after_first_chunk_delay_ms", 0):
                        self.mark(record, stage="after_first_chunk_delay")
                        time.sleep(control["after_first_chunk_delay_ms"] / 1000)
            else:
                self.send_json(200, result, record=record)
            with STATE_LOCK:
                record["response"] = copy.deepcopy(result)
            self.mark(record, stage="completed", terminal=True, outcome="completed",
                      usage_sent=record["usage"] is not None if usage_profile else True)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.mark(record, stage="client_disconnected", terminal=True, outcome="client_disconnected")

    def do_GET(self):
        if self.path in ("/__proof/catalog", "/__proof/catalog/observations"):
            return self.catalog()
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
        if self.path in ("/__proof/catalog/control", "/__proof/catalog/reset"):
            return self.catalog(payload)
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
        if self.path == "/v1/responses":
            return self.serve_responses(payload)
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
