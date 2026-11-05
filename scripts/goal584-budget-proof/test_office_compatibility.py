"""Source/component qualification only; all CLI/native HTTP/provider IO is doubled.

Execute with the existing provenance venv; no native app import, Docker, build,
provider, network, production or paid call. The actual Office app/client and
pinned pure WebUI serialization/result owners run unchanged.
"""
from __future__ import annotations
import ast
import asyncio
import base64
import copy
from contextlib import redirect_stdout
import hashlib
from hashlib import sha256
import json
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from typing import Any, TypedDict
from uuid import uuid4
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
OFFICE = ROOT / "services/officecli-openapi-proof"
sys.path[:0] = [str(OFFICE), str(OFFICE / "tests"), str(ROOT / "deploy/openwebui-budgets")]
import httpx
from fastapi.testclient import TestClient
from starlette.responses import HTMLResponse
import pytest
from PIL import Image
from io import BytesIO, StringIO

import prove_office_compatibility as P
import build_office_profile as builder
import provenance
import prove_pricing_snapshots as snapshots
from officecli_openapi_proof.app import create_app
from officecli_openapi_proof.config import Settings
from officecli_openapi_proof.docx_text import WORD
from officecli_openapi_proof.officecli import OfficeCliFailure
from officecli_openapi_proof.openwebui_client import HttpOpenWebUiClient
from test_guidance_routes import RecordingOfficeCli, office_output
from test_prepared_text import native_history

NATIVE = ROOT / "local/goal584/cost-display/open-webui/backend/open_webui"
LLM = ROOT / "local/goal584/litellm/upstream"
LLM_PIN = "d665dc1a6315847fcad6cc2c1264ceb47c06abce"


def native_owner(relative, names, namespace=None):
    raw = (NATIVE / relative).read_bytes().replace(b"\r\n", b"\n")
    if relative in ("routers/openai.py", "utils/middleware.py") and sha256(raw).hexdigest() != P.WEBUI_MODULES[relative]:
        # Reproduce the EXISTING accepted runtime Dockerfile stages in scratch.
        # No new overlay and no cache/source mutation; final deployed SHA gates it.
        with TemporaryDirectory(prefix="goal584-existing-office-profile-") as directory:
            mirror = Path(directory)
            for name in ("utils/misc.py", "utils/middleware.py", "routers/openai.py"):
                target = mirror / name; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((NATIVE / name).read_bytes().replace(b"\r\n", b"\n"))
            for name, entry in (("tool-context-v0.12.2", "apply_context.py"), ("provider-context-v0.12.2", "apply_capture.py")):
                owner_path = ROOT / "deploy/openwebui-patches" / name / entry
                spec = importlib.util.spec_from_file_location("office_existing_" + name, owner_path)
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                module.apply(mirror)
            raw = (mirror / relative).read_bytes()
    assert sha256(raw).hexdigest() == P.WEBUI_MODULES[relative]
    namespace = {"copy": copy, "json": json, "JSONCodec": json, "re": re, "Any": Any,
                 "HTMLResponse": HTMLResponse, "log": SimpleNamespace(debug=lambda *args: None), **(namespace or {})}
    tree = ast.parse(raw)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names
             or isinstance(n, (ast.Assign, ast.AnnAssign)) and any(isinstance(t, ast.Name) and t.id in names
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(NATIVE / relative), "exec"), namespace)
    return namespace


def deployed_context_owner():
    # Reuse the existing profile's own test extractor and exact appliers. This
    # qualifies only pure source semantics, not availability of the image.
    with TemporaryDirectory(prefix="goal584-profile-source-") as directory:
        mirror = Path(directory)
        for name in ("utils/misc.py", "utils/middleware.py", "routers/openai.py"):
            target = mirror / name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((NATIVE / name).read_bytes().replace(b"\r\n", b"\n"))
        modules = {}
        for key, folder, entry in (("apply_context", "tool-context-v0.12.2", "apply_context.py"),
                                   ("apply_capture", "provider-context-v0.12.2", "apply_capture.py")):
            path = ROOT / "deploy/openwebui-patches" / folder / entry
            spec = importlib.util.spec_from_file_location("office_profile_" + key, path)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.apply(mirror); modules[key] = module
        for name in ("utils/middleware.py", "routers/openai.py"):
            assert sha256((mirror / name).read_bytes()).hexdigest() == P.WEBUI_MODULES[name]
        assert sha256((mirror / "utils/misc.py").read_bytes()).hexdigest() == modules["apply_context"].PATCHED["utils/misc.py"]
        path = ROOT / "deploy/openwebui-patches/tool-context-v0.12.2/verify_context.py"
        spec = importlib.util.spec_from_file_location("office_existing_verify_context", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"apply_context": modules["apply_context"]}): spec.loader.exec_module(module)
        return module.load_functions(mirror)


@pytest.fixture(scope="module")
def native():
    tools = native_owner("utils/tools.py", {"OPENAPI_HTTP_METHODS", "resolve_schema", "convert_openapi_to_tool_payload",
                                          "clean_properties", "clean_openai_tool_schema"})
    router = deployed_context_owner()
    middleware = native_owner("utils/middleware.py", {"BASE64_IMAGE_DATA_URI_RE", "extract_base64_images", "process_tool_result"})
    return tools, router, middleware


def document(path, paragraphs=P.PARAGRAPHS, table=P.TABLE):
    root = ET.Element(WORD + "document"); body = ET.SubElement(root, WORD + "body")
    def paragraph(parent, text):
        p = ET.SubElement(parent, WORD + "p")
        ET.SubElement(ET.SubElement(p, WORD + "r"), WORD + "t").text = text
    for text in paragraphs[:3]: paragraph(body, text)
    tbl = ET.SubElement(body, WORD + "tbl")
    for row in table:
        tr = ET.SubElement(tbl, WORD + "tr")
        for text in row: paragraph(ET.SubElement(tr, WORD + "tc"), text)
    for text in paragraphs[15:]: paragraph(body, text)
    with ZipFile(path, "w") as out: out.writestr("word/document.xml", ET.tostring(root))


class CliIO(RecordingOfficeCli):
    """Only the external CLI boundary is doubled; not a native Office result."""
    def run(self, *args, input_text=None):
        if args[0] in ("batch", "create"):
            self.calls.append(args); self.inputs.append(input_text)
            if args[0] == "batch":
                assert json.loads(input_text) == [{"command": "add", "parent": "/body", "type": "markdown", "props": {"markdown": P.SOURCE}}]
            document(Path(args[1]))
            return office_output(*args, payload={"success": True})
        if args[0] == "view" and "screenshot" in args:
            self.calls.append(args); self.inputs.append(input_text)
            assert args[-2:] == ("--grid", "2")
            Image.new("RGB", (3, 2), "white").save(args[args.index("-o") + 1], format="PNG")
            return office_output(*args, payload={"success": True})
        return super().run(*args, input_text=input_text)


@pytest.fixture
def component(monkeypatch, tmp_path, native):
    history = native_history()
    history["chat"]["history"]["messages"]["selected"]["content"] = P.SOURCE
    state = {"files": {}, "events": [], "calls": [], "denied": set(), "history": history}
    def http(method, url, **kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["headers"] == {"Authorization": kwargs["headers"]["Authorization"]}
        auth = kwargs["headers"]["Authorization"]
        state["calls"].append((method, url, auth))
        status, value, content = 200, {}, None
        if auth == "Bearer foreign" or url in state["denied"]: status = 403
        elif url.endswith("/api/v1/auths/"): value = {"id": "caller"}
        elif url.endswith("/api/v1/chats/chat"): value = state["history"]
        elif method == "POST" and "/api/v1/files/?" in url:
            name, handle, content_type = kwargs["files"]["file"]
            identifier = str(uuid4())
            state["files"][identifier] = handle.read()
            value = {"id": identifier, "filename": name, "meta": {"content_type": content_type}}
        elif method == "POST" and url.endswith("/event"):
            state["events"].append(copy.deepcopy(kwargs["json"]))
        elif method == "GET" and "/api/v1/files/" in url:
            identifier = url.split("/files/")[1].split("/")[0]
            content = state["files"][identifier]
        else: raise AssertionError("Unexpected component HTTP operation")
        request = httpx.Request(method, url)
        return httpx.Response(status, request=request, content=content) if content is not None else httpx.Response(status, request=request, json=value)
    monkeypatch.setattr("officecli_openapi_proof.openwebui_client.httpx.request", http)
    cli = CliIO()
    webui = HttpOpenWebUiClient("http://native", 5)
    client = TestClient(create_app(cli, webui, Settings("officecli", 5, "1.0.152", "http://native")))
    # Actual OpenAPI and native schema conversion, not handwritten Office tools.
    openapi = client.get("/openapi.json").json()
    tools, router, middleware = native
    specs = [tools["clean_openai_tool_schema"](s) for s in tools["convert_openapi_to_tool_payload"](openapi)]
    return SimpleNamespace(state=state, cli=cli, webui=webui, client=client, specs=specs, router=router,
                           middleware=middleware, directory=tmp_path)


def export(component, auth="Bearer caller"):
    return component.client.post("/v1/officecli/documents/export-answer", json=P.EXPORT_ARGUMENTS,
        headers={"Authorization": auth, "X-OpenWebUI-Chat-Id": "chat", "X-OpenWebUI-Message-Id": "current"})


def full_capture(component, *, provider=None):
    exported = export(component).json()
    identifier = exported["result_file_id"]
    rendered = component.client.post("/v1/officecli/render", headers={"Authorization": "Bearer caller"},
        json={"file_id": identifier, "format": "docx", "grid": 2})
    assert rendered.status_code == 200 and rendered.headers["cache-control"] == "no-store"
    native = component.directory / "native.docx"; downloaded = component.directory / "browser.docx"
    component.webui.download(identifier, "Bearer caller", native)
    component.webui.download(identifier, "Bearer caller", downloaded)  # HTTP IO double, NOT a browser acceptance.
    artifact = dict(source_message_id="selected", exported=exported, native_file_id=identifier, browser_file_id=identifier,
                    native_path=native, browser_path=downloaded, png=rendered.content)
    actor, chat, answer = (str(uuid4()) for _ in range(3))
    owner = {"actor": actor, "key_hash": "a" * 64, "chat_id": chat, "answer_id": answer,
             "wire_model": "goal584-office-wire", "native_specs": component.specs, "exported": exported,
             "png": rendered.content, "native_responses_payload": component.router["convert_to_responses_payload"],
             "expected_instruction": "Preserve explicit instructions; perform the complete Office task."}
    secret = "synthetic-component-secret-with-no-production-use"
    body = {"model": P.MODEL, "messages": [{"role": "system", "content": "Preserve explicit instructions; perform the complete Office task."},
            {"role": "assistant", "content": P.SOURCE}, {"role": "user", "content": P.USER_REQUEST}],
            "tools": [{"type": "function", "function": copy.deepcopy(s)} for s in component.specs],
            "reasoning": {"effort": "low"}, "include": ["reasoning.encrypted_content"], "store": False, "stream": True,
            "parallel_tool_calls": False, "max_completion_tokens": 1024}
    if provider is not None:
        owner["wire_model"] = provider.OFFICE_MODEL
        body.pop("reasoning"); body.pop("include")
    calls = []; recorded_outputs = []
    prefix = copy.deepcopy(body["messages"])
    for index in range(3):
        before = copy.deepcopy(body); after = copy.deepcopy(body)
        after["litellm_metadata"] = {"owui_budget_provenance": provenance.encode_call(secret, user_id=actor,
            chat_id=chat, answer_id=answer, root_chat_id=chat, root_answer_id=answer, model=P.MODEL)}
        claims = P.verify_budget_boundary(before, after, decode_call=provenance.decode_call, secret=secret, actor=actor)
        scope = {"schema": 1, "category": "personal", "user_id": actor, "chat_id": chat, "answer_id": answer,
                 "root_chat_id": chat, "root_answer_id": answer, "model": P.MODEL, "call_id": claims["jti"]}
        wire = P.responses_projection(component.router["convert_to_responses_payload"](copy.deepcopy(after)))
        response_id, call_id = "resp_" + uuid4().hex, "call_" + uuid4().hex
        if index < 2:
            name = ("export_answer_to_word", "render_office_file")[index]
            args = P.EXPORT_ARGUMENTS if index == 0 else {"file_id": identifier, "format": "docx", "grid": 2}
            output = [{"type": "reasoning", "id": "rs_" + uuid4().hex, "summary": [{"type": "summary_text", "text": "Synthetic reasoning sentinel"}],
                       "encrypted_content": "opaque-original-component-sentinel", "status": "completed"},
                      {"type": "function_call", "call_id": call_id, "name": name, "arguments": json.dumps(args), "status": "completed"}]
        else: output = [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "[Download]( /api/v1/files/" + identifier + "/content)"}]}]
        response = {"id": response_id, "model": owner["wire_model"], "status": "completed", "usage": P.USAGE, "output": output}
        if provider is not None:
            # Run the actual finite provider with only its HTTP transport leaf
            # replaced. No socket/network and no authored provider result.
            handler = object.__new__(provider.Handler); statuses = []
            handler.send_response = statuses.append
            handler.send_header = lambda *args: None; handler.end_headers = lambda: None
            handler.wfile = BytesIO()
            handler.serve_responses({**copy.deepcopy(wire), "model": owner["wire_model"]})
            record = provider.REQUESTS[-1]
            assert statuses == [200] and len(provider.REQUESTS) == index + 1
            assert record["lifecycle"]["terminal"] and record["lifecycle"]["outcome"] == "completed"
            response = copy.deepcopy(record["response"]); output = response["output"]; response_id = response["id"]
            if index < 2: call_id = next(v["call_id"] for v in output if v["type"] == "function_call")
        calls.append({"before_budget": before, "after_budget": after, "wire_before_auth": wire, "wire_after_auth": copy.deepcopy(wire),
            "auth_user_id": actor, "auth_key_hash": owner["key_hash"], "attestation_present_before": True,
            "provenance_removed_after": True, "verified_cost_scope": scope, "route": "/responses",
            "provider": {"id": response_id, "route": "/v1/responses", "body": {**copy.deepcopy(wire), "model": owner["wire_model"]},
                         "usage": P.USAGE, "response": response, "lifecycle": {"terminal": True, "outcome": "completed"}}})
        if index < 2:
            # Execute the pinned native result processor; only Office CLI/HTTP IO was doubled.
            result = (exported, {}) if index == 0 else ("data:image/png;base64," + base64.b64encode(rendered.content).decode(), {})
            text, files, embeds = asyncio.run(component.middleware["process_tool_result"](None, name, result, "external"))
            assert not embeds
            recorded_outputs.extend(copy.deepcopy(output))
            recorded_outputs.append({"type": "function_call_output", "call_id": call_id, "output": [
                {"type": "input_text", "text": text},
                *[{"type": "input_image", "image_url": f["url"]} for f in files]]})
            options = {"reasoning_format": "responses", "flatten_tool_images": False}
            native_messages = component.router["convert_output_to_messages"](recorded_outputs, raw=True, **options)
            # Actual second reconstruction occurs even with compaction disabled.
            native_messages = component.router["process_messages_with_output"](native_messages, **options)
            body["messages"] = prefix + native_messages
    return artifact, calls, owner


def test_fixture_and_live_profile_sources_match(component):
    receipt = json.loads((ROOT / "local/goal584/current-route-compatibility-live-readback.safe.json").read_text(encoding="utf8"))
    assert P.SOURCE == receipt["representative_input"]["prior_source"]
    assert sha256(P.SOURCE.encode()).hexdigest() == P.SOURCE_SHA256
    assert receipt["current_live"]["webui"]["module_sha256"] == P.WEBUI_MODULES
    assert receipt["current_live"]["office"]["module_sha256"] == P.OFFICE_MODULES
    for name, expected in P.OFFICE_MODULES.items():
        assert sha256((OFFICE / "officecli_openapi_proof" / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == expected
    valves = receipt["current_live"]["webui"]["functions"][0]["persisted_valves_allowlist"]
    assert valves == P.VALVES and len(P.TARGETS.split(",")) == 13
    assert {s["name"] for s in component.specs} >= {"export_answer_to_word", "render_office_file"}
    assert "authorization" in next(s for s in component.specs if s["name"] == "export_answer_to_word")["parameters"]["properties"]


def test_actual_office_owners_native_context_and_artifact_assertions(component):
    artifact, calls, owner = full_capture(component)
    assert len(P.verify_calls(calls, **owner)) == 3
    assert set(P.verify_artifacts(**artifact)) == {"docx_sha256", "png_sha256"}
    assert [e["type"] for e in component.state["events"]] == ["files", "chat:message:files"]
    assert all(e["data"]["files"][0]["id"] == artifact["native_file_id"] for e in component.state["events"])
    assert len([v for v in component.cli.calls if v[0] == "batch"]) == 1
    assert P.safe_component_result(lambda: P.verify_calls(calls, **owner))["native_office_accepted"] is False


@pytest.mark.parametrize("mutation", ["budget_source", "auth_instructions", "provider_tools", "reasoning", "prior_source", "result", "image", "file_id", "scope", "duplicate_call", "extra_call"])
def test_context_and_handoff_mutations_fail(component, mutation):
    artifact, calls, owner = full_capture(component)
    if mutation == "budget_source": calls[1]["after_budget"]["messages"][1]["content"] = "summarized source"
    elif mutation == "auth_instructions": calls[1]["wire_after_auth"]["instructions"] = "different instruction"
    elif mutation == "provider_tools": calls[1]["provider"]["body"]["tools"].pop()
    elif mutation == "reasoning": calls[1]["wire_before_auth"].pop("reasoning")
    elif mutation == "prior_source": calls[0]["wire_before_auth"]["input"][0]["content"][0]["text"] = "missing source"
    elif mutation == "result": next(v for v in calls[1]["wire_before_auth"]["input"] if v["type"] == "function_call_output")["output"] = "{}"
    elif mutation == "image":
        for v in P._nodes(calls[2]["wire_before_auth"]):
            if v.get("type") == "input_image": v["image_url"] = "data:image/png;base64,AA=="
    elif mutation == "file_id": owner["exported"]["result_file_id"] = str(uuid4())
    elif mutation == "scope": calls[1]["verified_cost_scope"]["root_answer_id"] = str(uuid4())
    elif mutation == "duplicate_call": calls[1]["provider"]["id"] = calls[0]["provider"]["id"]
    elif mutation == "extra_call": calls.append(copy.deepcopy(calls[-1]))
    with pytest.raises((P.ProofError, ValueError)): P.verify_calls(calls, **owner)


def wire_capture(component):
    """Component-produced wire packet shape for the live-only validator.

    Real native schemas/converters/results run above; CLI/HTTP remain IO doubles.
    Omit component Filter bodies entirely, matching the live observer boundary.
    The current primary profile adds no request reasoning override; opaque
    reasoning returned by the provider still has to survive continuation.
    """
    _, calls, owner = full_capture(component)
    for call in calls:
        del call["before_budget"], call["after_budget"]
        for body in (call["wire_before_auth"], call["wire_after_auth"], call["provider"]["body"]):
            body.pop("reasoning", None); body.pop("include", None)
    return calls, owner


def current_mock_wire_capture(component):
    path = ROOT / "scripts/goal584-budget-proof/mock_provider.py"
    spec = importlib.util.spec_from_file_location("office_literal_no_reasoning_provider", path)
    provider = importlib.util.module_from_spec(spec); spec.loader.exec_module(provider)
    _, calls, owner = full_capture(component, provider=provider)
    for call in calls: del call["before_budget"], call["after_budget"]
    return calls, owner


def test_current_mock_without_reasoning_keeps_only_actual_native_tool_pairs(component):
    calls, owner = current_mock_wire_capture(component)
    original = copy.deepcopy(calls)
    # This native conversion is real, but is not an observation of any returned
    # provider reasoning. It must not invent an empty assistant continuation.
    synthetic = component.router["convert_to_responses_payload"]({"messages": [{"role": "assistant", "output": []}]})["input"]
    assert synthetic and any(v.get("role") == "assistant" for v in synthetic)
    for index, call in enumerate(calls):
        assert "reasoning" not in call["wire_before_auth"] and "include" not in call["wire_before_auth"]
        assert not any(v.get("type") == "reasoning" for v in call["provider"]["response"]["output"])
        if index < 2:
            tail = calls[index + 1]["wire_before_auth"]["input"][len(call["wire_before_auth"]["input"]):]
            assert [v["type"] for v in tail] == ["function_call", "function_call_output"]
    invocations = []
    def native(body):
        invocations.append(body)
        return component.router["convert_to_responses_payload"](body)
    assert P.verify_wire_calls(calls, **(owner | {"native_responses_payload": native}))
    assert invocations == [] and calls == original


@pytest.mark.parametrize("channel", ["instructions", "developer", "system"])
def test_full_pinned_office_instruction_survives_native_reasoning_model_route(component, channel):
    source = (ROOT / "deploy/openwebui-functions/officecli_auto_attach_filter.py").read_bytes()
    instruction = P.office_instruction(source)
    assert P.office_instruction(source.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")) == instruction
    route = native_owner("routers/openai.py", {"is_openai_new_model", "openai_reasoning_model_handler"})
    payload = {"model": P.MODEL, "messages": [{"role": "system", "content": "Existing higher-priority context.\n\n" + instruction}]}
    assert route["is_openai_new_model"](payload["model"])
    native = component.router["convert_to_responses_payload"](route["openai_reasoning_model_handler"](payload))
    assert "instructions" not in native and native["input"][0]["role"] == "developer"
    calls, owner = current_mock_wire_capture(component)
    owner["expected_instruction"] = instruction
    for call in calls:
        for wire in (call["wire_before_auth"], call["wire_after_auth"], call["provider"]["body"]):
            wire.pop("instructions")
            if channel == "instructions": wire["instructions"] = native["input"][0]["content"][0]["text"]
            else:
                item = copy.deepcopy(native["input"][0]); item["role"] = channel
                wire["input"].insert(0, item)
    original = copy.deepcopy(calls)
    assert P.verify_wire_calls(calls, **owner)
    assert calls == original


@pytest.mark.parametrize("mutation", ["missing", "truncated", "marker_only", "changed_tail", "user", "assistant",
    "tool_result", "nested_developer", "wrong_block", "split_blocks", "empty_expected", "source_drift"])
def test_instruction_guard_rejects_coherent_loss_and_untrusted_quotes(component, mutation):
    source = (ROOT / "deploy/openwebui-functions/officecli_auto_attach_filter.py").read_bytes()
    if mutation == "source_drift":
        with pytest.raises(P.ProofError, match="office_instruction_source"): P.office_instruction(source + b"\n")
        return
    instruction = P.office_instruction(source)
    calls, owner = current_mock_wire_capture(component); owner["expected_instruction"] = instruction
    if mutation == "empty_expected": owner["expected_instruction"] = ""
    for call in calls:
        for wire in (call["wire_before_auth"], call["wire_after_auth"], call["provider"]["body"]):
            wire.pop("instructions")
            item = {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": instruction}]}
            if mutation == "missing": item["content"] = []
            elif mutation == "truncated": item["content"][0]["text"] = instruction[:-1]
            elif mutation == "marker_only": item["content"][0]["text"] = instruction.split()[0]
            elif mutation == "changed_tail": item["content"][0]["text"] = instruction[:-8] + "changed."
            elif mutation in ("user", "assistant"): item["role"] = mutation
            elif mutation == "tool_result": item = {"type": "function_call_output", "output": instruction}
            elif mutation == "nested_developer": item = {"type": "message", "role": "user", "content": [item]}
            elif mutation == "wrong_block": item["content"][0]["type"] = "output_text"
            elif mutation == "split_blocks":
                item["content"] = [{"type": "input_text", "text": text} for text in (instruction[:80], instruction[80:])]
            wire["input"].insert(0, item)
    with pytest.raises(P.ProofError, match="office_system_context"): P.verify_wire_calls(calls, **owner)


@pytest.mark.parametrize("reasoning", [False, True])
@pytest.mark.parametrize("extra", [
    {"type": "message", "role": "assistant", "content": []},
    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "foreign"}]},
    {"type": "unknown", "sentinel": "unobserved"}])
def test_coherent_extra_continuation_items_fail_even_when_tool_pair_and_native_reasoning_survive(component, reasoning, extra):
    calls, owner = wire_capture(component) if reasoning else current_mock_wire_capture(component)
    returned = [v for v in calls[0]["provider"]["response"]["output"] if v["type"] == "reasoning"]
    prefix = owner["native_responses_payload"]({"messages": [{"role": "assistant", "output": returned}]})["input"] if returned else []
    position = len(calls[0]["wire_before_auth"]["input"]) + len(prefix)
    # Both auth sides/provider agree, and the third request retains the entire
    # second request. Exact new continuation, not a checksum/history mismatch,
    # must reject this otherwise coherent unobserved item.
    for call in calls[1:]:
        for body in (call["wire_before_auth"], call["wire_after_auth"], call["provider"]["body"]):
            body["input"].insert(position, copy.deepcopy(extra))
    with pytest.raises(P.ProofError, match="office_continuation_items"):
        P.verify_wire_calls(calls, **owner)


def test_live_wire_packet_requires_no_invented_filter_bodies_and_preserves_native_reasoning(component):
    calls, owner = wire_capture(component)
    before = copy.deepcopy(calls)
    by_provider = P.verify_wire_calls(calls, **owner)
    assert by_provider == {c["provider"]["id"]: c["verified_cost_scope"] for c in calls}
    assert calls == before
    assert all("before_budget" not in c and "after_budget" not in c for c in calls)
    assert all("reasoning" not in c["wire_before_auth"] for c in calls)
    assert any(v.get("type") == "reasoning" and v.get("encrypted_content")
               for v in calls[-1]["wire_before_auth"]["input"])
    # The component entrypoint never silently skips its separate proof boundary.
    with pytest.raises(KeyError): P.verify_calls(calls, **owner)


@pytest.mark.parametrize("mutation", ["missing_wire", "malformed_wire", "missing_auth", "no_attestation",
    "unconsumed", "auth_failure", "actor", "key", "route", "model", "scope_root", "scope_payer", "scope_category",
    "scope_call", "missing_provider", "incomplete_response", "provider_usage", "provider_lifecycle", "provider_context",
    "native_schema", "system", "source", "history", "reasoning", "export_result", "image", "final", "duplicate", "extra"])
def test_live_wire_packet_rejects_incomplete_or_drifting_context_and_native_receipts(component, mutation):
    calls, owner = wire_capture(component)
    if mutation == "missing_wire": calls[0].pop("wire_after_auth")
    elif mutation == "malformed_wire": calls[0]["wire_before_auth"] = []
    elif mutation == "missing_auth": calls[0].pop("auth_key_hash")
    elif mutation == "no_attestation": calls[0]["attestation_present_before"] = False
    elif mutation == "unconsumed": calls[0]["provenance_removed_after"] = False
    elif mutation == "auth_failure": calls[0]["auth_failure"] = {"scope": "custom_auth", "status_code": 403}
    elif mutation == "actor": calls[0]["auth_user_id"] = str(uuid4())
    elif mutation == "key": calls[0]["auth_key_hash"] = "b" * 64
    elif mutation == "route": calls[0]["route"] = "/chat/completions"
    elif mutation == "scope_root": calls[0]["verified_cost_scope"]["root_answer_id"] = str(uuid4())
    elif mutation == "scope_payer": calls[0]["verified_cost_scope"]["user_id"] = str(uuid4())
    elif mutation == "scope_category": calls[0]["verified_cost_scope"]["category"] = "service"
    elif mutation == "scope_call": calls[0]["verified_cost_scope"].pop("call_id")
    elif mutation == "missing_provider": calls[0].pop("provider")
    elif mutation == "incomplete_response": calls[0]["provider"]["response"].pop("output")
    elif mutation == "provider_usage": calls[0]["provider"]["response"]["usage"] = {"input_tokens": 0}
    elif mutation == "provider_lifecycle": calls[0]["provider"]["lifecycle"]["terminal"] = False
    elif mutation == "provider_context": calls[0]["provider"]["body"]["instructions"] = "provider drift"
    elif mutation == "final": calls[2]["provider"]["response"]["output"] = []
    elif mutation == "duplicate": calls[1]["verified_cost_scope"]["call_id"] = calls[0]["verified_cost_scope"]["call_id"]
    elif mutation == "extra": calls.append(copy.deepcopy(calls[-1]))
    else:
        # Change both auth projections and the provider body coherently: these
        # must fail the shared source/schema/continuation assertions themselves.
        for index, call in enumerate(calls):
            for body in (call["wire_before_auth"], call["wire_after_auth"], call["provider"]["body"]):
                if mutation == "model": body["model"] = "foreign-model"
                elif mutation == "native_schema":
                    next(v for v in body["tools"] if v["name"] == "export_answer_to_word")["parameters"]["properties"] = {}
                elif mutation == "system": body["instructions"] = ""
                elif mutation == "source":
                    for node in P._nodes(body["input"]):
                        if node.get("text") == P.SOURCE: node["text"] = "summary"
                elif mutation == "history" and index == 1: body["input"].pop(0)
                elif mutation == "reasoning" and index == 1:
                    body["input"] = [v for v in body["input"] if v.get("type") != "reasoning"]
                elif mutation == "export_result" and index:
                    next(v for v in body["input"] if v.get("type") == "function_call_output")["output"] = "{}"
                elif mutation == "image" and index == 2:
                    for node in P._nodes(body["input"]):
                        if node.get("type") == "input_image": node["image_url"] = "data:image/png;base64,AA=="
    with pytest.raises((P.ProofError, ValueError)): P.verify_wire_calls(calls, **owner)


@pytest.mark.parametrize("mutation", ["missing_sentinel", "table_row", "number", "order", "browser_bytes", "browser_id", "native_id", "source_id", "png"])
def test_artifact_mutations_fail(component, mutation):
    artifact, _, _ = full_capture(component)
    if mutation in ("missing_sentinel", "table_row", "number", "order"):
        paragraphs = list(P.PARAGRAPHS); table = P.TABLE
        if mutation == "missing_sentinel": paragraphs[-1] = "truncated"
        elif mutation == "table_row": table = table[:2]
        elif mutation == "number": table = (*table[:2], ("Beta", "3", "2000", "9999"))
        else: paragraphs[0], paragraphs[1] = paragraphs[1], paragraphs[0]
        document(artifact["native_path"], paragraphs, table)
        artifact["browser_path"].write_bytes(artifact["native_path"].read_bytes())
        artifact["exported"]["result_sha256"] = sha256(artifact["native_path"].read_bytes()).hexdigest()
    elif mutation == "browser_bytes": artifact["browser_path"].write_bytes(b"different")
    elif mutation == "browser_id": artifact["browser_file_id"] = str(uuid4())
    elif mutation == "native_id": artifact["native_file_id"] = str(uuid4())
    elif mutation == "source_id": artifact["source_message_id"] = "foreign-source"
    else: artifact["png"] = b"not a PNG"
    with pytest.raises((P.ProofError, OfficeCliFailure)): P.verify_artifacts(**artifact)


@pytest.mark.parametrize("mode", ["foreign_source", "wrong_ancestry", "unfinished_source", "foreign_file"])
def test_native_session_source_and_file_denial_before_cli_or_publication(component, mode):
    before = len(component.cli.calls)
    if mode == "foreign_source": result = export(component, "Bearer foreign")
    elif mode == "foreign_file":
        result = component.client.post("/v1/officecli/render", headers={"Authorization": "Bearer foreign"},
            json={"file_id": str(uuid4()), "format": "docx", "grid": 2})
    else:
        messages = component.state["history"]["chat"]["history"]["messages"]
        if mode == "wrong_ancestry": messages["question"]["parentId"] = "no-native-parent"
        else: messages["selected"]["done"] = False
        result = export(component)
    assert result.status_code in (401, 502)
    assert len(component.cli.calls) == before and not component.state["files"] and not component.state["events"]


def sdk_decoder():
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
    raw = subprocess.check_output(["git", "-C", str(LLM), "show", LLM_PIN + ":litellm/responses/utils.py"], env=env, stderr=subprocess.DEVNULL)
    types = subprocess.check_output(["git", "-C", str(LLM), "show", LLM_PIN + ":litellm/types/responses/main.py"], env=env, stderr=subprocess.DEVNULL)
    n = next(n for c in ast.parse(raw).body if isinstance(c, ast.ClassDef) and c.name == "ResponsesAPIRequestUtils"
             for n in c.body if isinstance(n, ast.FunctionDef) and n.name == "_decode_responses_api_response_id")
    n.decorator_list, n.returns = [], None
    for arg in n.args.args: arg.annotation = None
    t = next(n for n in ast.parse(types).body if isinstance(n, ast.ClassDef) and n.name == "DecodedResponseId")
    namespace = {"base64": base64, "TypedDict": TypedDict, "verbose_logger": SimpleNamespace(debug=lambda *args: None)}
    exec(compile(ast.Module(body=[t, n], type_ignores=[]), "exact-native-sdk-decoder", "exec"), namespace)
    return namespace["_decode_responses_api_response_id"]


def financial_fixture(component, monkeypatch):
    _, calls, owner = full_capture(component)
    by_provider = P.verify_calls(calls, **owner)
    fields = ast.literal_eval(next(n.value for n in ast.parse((ROOT / "deploy/openwebui-budgets/pricing_snapshot.py").read_bytes()).body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RATE_FIELDS" for t in n.targets)))
    # Existing validator imports only the callback's public data representation;
    # LiteLLM application SDK is intentionally not imported in this host test.
    representation = ModuleType("pricing_snapshot"); representation.RATE_FIELDS = fields
    monkeypatch.setitem(sys.modules, "pricing_snapshot", representation)
    key = {"user_id": owner["actor"], "models": [P.MODEL], "key_alias": "synthetic-owner",
           "max_budget": 10, "budget_duration": "30d", "budget_reset_at": "2026-12-01", "spend": 0}
    user = {"user_id": owner["actor"], "user_role": "internal_user", "models": [P.MODEL],
            "max_budget": 10, "budget_duration": "30d", "budget_reset_at": "2026-12-01", "spend": 0}
    before = {"user": user, "key": key, "rows": [{"request_id": "retained-old-zero-row", "spend": 0}],
              "old_payers": {"existing-payer": {"rows": [{"spend": 4}], "user": {"spend": 4}, "key": {"spend": 4}}}}
    after = copy.deepcopy(before)
    for provider_id, scope in by_provider.items():
        request = "resp_" + base64.b64encode(("litellm:custom_llm_provider:openai;model_id:office-deployment;response_id:" + provider_id).encode()).decode()
        rates = {k: None for k in fields}; rates.update(input_cost_per_token=.01, output_cost_per_token=.02)
        after["rows"].append({"request_id": request, "model": "openai/" + owner["wire_model"], "model_group": P.MODEL,
            "model_id": "office-deployment", "status": "success", "user": owner["actor"], "api_key": owner["key_hash"],
            "session_id": owner["chat_id"], "spend": .20, "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
            "metadata": {"spend_logs_metadata": {"owui_budget": copy.deepcopy(scope), "owui_billed_token_rates": {
                "schema": 1, "availability": "partial", "observed_at_utc": "2026-11-04T00:00:00Z", "rates": rates}}}})
    after["user"]["spend"] = after["key"]["spend"] = .60
    kwargs = {k: owner[k] for k in ("actor", "key_hash", "chat_id", "answer_id", "wire_model")}
    kwargs.update(calls_by_provider=by_provider, deployment_id="office-deployment", validate_scope=provenance.validate_persisted_scope,
                  validate_rates=snapshots.validate_snapshot, decode_response_id=sdk_decoder())
    return before, after, kwargs


def test_native_sdk_scope_rates_and_full_raw_financial_contract(component, monkeypatch):
    before, after, kwargs = financial_fixture(component, monkeypatch)
    assert P.verify_finance(before, after, **kwargs) == {"physical_calls": 3, "new_raw_rows": 3, "native_spend_delta_usd": ".60"}


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra_zero", "old_row", "old_payer", "cap", "counter", "nonce", "rate", "key", "model", "usage", "spend", "decoded_provider"])
def test_financial_contract_mutations_fail(component, monkeypatch, mutation):
    before, after, kwargs = financial_fixture(component, monkeypatch)
    row = after["rows"][-1]
    if mutation == "missing": after["rows"].pop()
    elif mutation == "duplicate": after["rows"].append(copy.deepcopy(row))
    elif mutation == "extra_zero": after["rows"].append({"request_id": "unexpected-raw-zero", "spend": 0})
    elif mutation == "old_row": after["rows"][0]["spend"] = 1
    elif mutation == "old_payer": after["old_payers"]["existing-payer"]["user"]["spend"] = 5
    elif mutation == "cap": after["key"]["max_budget"] = 11
    elif mutation == "counter": after["user"]["spend"] = .4
    elif mutation == "nonce": row["metadata"]["spend_logs_metadata"]["owui_budget"]["call_id"] = str(uuid4())
    elif mutation == "rate": row["metadata"]["spend_logs_metadata"]["owui_billed_token_rates"]["rates"]["input_cost_per_token"] = .03
    elif mutation == "key": row["api_key"] = "b" * 64
    elif mutation == "model": row["model_id"] = "foreign-deployment"
    elif mutation == "usage": row["prompt_tokens"] = True
    elif mutation == "spend": row["spend"] = 0
    else: row["request_id"] = "resp_" + base64.b64encode(b"litellm:custom_llm_provider:openai;model_id:office-deployment;response_id:unobserved-provider").decode()
    with pytest.raises(P.ProofError): P.verify_finance(before, after, **kwargs)


def service_financial_fixture(component, monkeypatch):
    before, primary_after, primary = financial_fixture(component, monkeypatch)
    actor, payer, key_hash = primary['actor'], str(uuid4()), 'b' * 64
    for owner in ('user', 'key'):
        before[owner].update(user_id=payer, models=['gpt-6-luna'])
    after = copy.deepcopy(before)
    row = copy.deepcopy(primary_after['rows'][-1])
    provider_id = 'resp_office_service_fixture'
    row.update(request_id='resp_' + base64.b64encode(('litellm:custom_llm_provider:openai;model_id:goal584-office-service;response_id:'
        + provider_id).encode()).decode(), user=payer, api_key=key_hash, model='openai/goal584-fake-office-service',
        model_group='gpt-6-luna', model_id='goal584-office-service', session_id='owui-service:' + primary['chat_id'])
    scope = {'schema': 1, 'category': 'service', 'user_id': payer, 'actor_id': actor,
        'chat_id': primary['chat_id'], 'call_id': str(uuid4()), 'model': 'gpt-6-luna', 'task': 'follow_up_generation'}
    descriptor = {'schema': 1, 'deployment_id': 'goal584-office-service', 'currency': 'USD',
        'source_ref': 'goal584-office-synthetic-v1', 'source_url': 'https://pricing.example.invalid/goal584/office',
        'source_checked_at_utc': '2026-11-05T00:00:00Z', 'declared_effective_from_utc': '2026-11-05T00:00:00Z',
        'declared_effective_until_utc': None, 'activation_ref': 'goal584-office-stand-v1', 'qualified_usage': 'flat_input_output'}
    spend = row['metadata']['spend_logs_metadata']; spend['owui_budget'] = copy.deepcopy(scope)
    snapshot = spend['owui_billed_token_rates']; snapshot['availability'] = 'partial'
    snapshot['rates'] = dict.fromkeys(snapshot['rates'])
    snapshot['rates'].update(input_cost_per_token=.01, output_cost_per_token=.02)
    spend['owui_tariff_descriptor'] = {'schema': 1, 'availability': 'available', 'descriptor': copy.deepcopy(descriptor)}
    after['rows'].append(row)
    after['user']['spend'] = after['key']['spend'] = .20
    kwargs = dict(actor=actor, payer=payer, key_hash=key_hash, chat_id=primary['chat_id'], provider_id=provider_id,
        verified_scope=scope, wire_model='goal584-fake-office-service', deployment_id='goal584-office-service',
        descriptor=descriptor, validate_scope=provenance.validate_persisted_service_scope,
        validate_rates=snapshots.validate_snapshot, decode_response_id=primary['decode_response_id'])
    return before, after, kwargs


def test_office_service_actual_sdk_scope_and_snapshot_owners_verify_one_separate_payer(component, monkeypatch):
    before, after, kwargs = service_financial_fixture(component, monkeypatch)
    assert kwargs['actor'] != kwargs['payer']
    assert P.verify_service_finance(before, after, **kwargs) == {
        'physical_calls': 1, 'new_raw_rows': 1, 'native_spend_delta_usd': '.20'}


@pytest.mark.parametrize('mutation', ['same_payer', 'cap', 'counter', 'missing', 'duplicate', 'extra_zero', 'retained_row',
    'nonce', 'actor', 'task', 'scope_answer', 'key', 'model', 'session', 'usage', 'spend', 'rate', 'partial_rate',
    'source', 'unknown_tariff', 'deployment', 'provider_id'])
def test_office_service_finance_rejects_accounting_scope_source_and_history_drift(component, monkeypatch, mutation):
    before, after, kwargs = service_financial_fixture(component, monkeypatch)
    row = after['rows'][-1]; spend = row['metadata']['spend_logs_metadata']
    if mutation == 'same_payer': kwargs['actor'] = kwargs['payer']
    elif mutation == 'cap': after['key']['max_budget'] = 11
    elif mutation == 'counter': after['user']['spend'] = .60
    elif mutation == 'missing': after['rows'].pop()
    elif mutation == 'duplicate': after['rows'].append(copy.deepcopy(row))
    elif mutation == 'extra_zero': after['rows'].append({'request_id': 'new-zero-row', 'spend': 0})
    elif mutation == 'retained_row': after['rows'][0]['spend'] = 1
    elif mutation == 'nonce': spend['owui_budget']['call_id'] = str(uuid4())
    elif mutation == 'actor': spend['owui_budget']['actor_id'] = kwargs['payer']
    elif mutation == 'task': spend['owui_budget']['task'] = 'title_generation'
    elif mutation == 'scope_answer': spend['owui_budget']['answer_id'] = str(uuid4())
    elif mutation == 'key': row['api_key'] = 'a' * 64
    elif mutation == 'model': row['model_group'] = P.MODEL
    elif mutation == 'session': row['session_id'] = kwargs['chat_id']
    elif mutation == 'usage': row['prompt_tokens'] = True
    elif mutation == 'spend': row['spend'] = .60
    elif mutation == 'rate': spend['owui_billed_token_rates']['rates']['input_cost_per_token'] = .03
    elif mutation == 'partial_rate': spend['owui_billed_token_rates']['rates']['input_cost_per_token'] = None
    elif mutation == 'source': spend['owui_tariff_descriptor']['descriptor']['source_ref'] = 'foreign-source'
    elif mutation == 'unknown_tariff': spend['owui_tariff_descriptor']['availability'] = 'unknown'
    elif mutation == 'deployment': row['model_id'] = 'foreign-deployment'
    else: kwargs['provider_id'] = 'unobserved-provider'
    with pytest.raises((P.ProofError, ValueError)): P.verify_service_finance(before, after, **kwargs)


def test_safe_component_packet_never_exports_private_exception_or_claims_acceptance():
    for error in (RuntimeError("Bearer private JWT body secret"), P.ProofError("Bearer private secret")):
        value = P.safe_component_result(lambda: (_ for _ in ()).throw(error))
        assert value == {"schema": 1, "component_assertions_passed": False, "native_office_accepted": False,
                         "failure_code": "office_component_failure"}
    value = P.safe_component_result(lambda: None)
    assert value["component_assertions_passed"] is True and value["native_office_accepted"] is False


def test_deployed_source_witness_preserves_reasoning_and_bound_image(component):
    artifact, calls, owner = full_capture(component)
    for index in (0, 1):
        reasoning = [v for v in calls[index]["provider"]["response"]["output"] if v["type"] == "reasoning"]
        expected = component.router["convert_to_responses_payload"]({"messages": [{"role": "assistant", "output": reasoning}]})["input"]
        following = calls[index + 1]["wire_before_auth"]["input"]
        assert all(v in following for v in expected)
        assert all(v["summary"] and v["encrypted_content"] == "opaque-original-component-sentinel" for v in expected)
    assert all(v.get("role") != "user" or not any(n.get("type") == "input_image" for n in P._nodes(v))
               for v in calls[2]["wire_before_auth"]["input"])
    assert P.verify_calls(calls, **owner)


@pytest.mark.parametrize("mutation", ["before_source", "after_tool", "unsigned_metadata", "foreign_token"])
def test_existing_signature_owner_and_exact_budget_boundary(component, mutation):
    actor, chat, answer = (str(uuid4()) for _ in range(3)); secret = "component-private-secret"
    before = {"model": P.MODEL, "messages": [{"role": "assistant", "content": P.SOURCE}], "reasoning": {"effort": "low"}}
    after = copy.deepcopy(before)
    after["litellm_metadata"] = {"owui_budget_provenance": provenance.encode_call(secret, user_id=actor,
        chat_id=chat, answer_id=answer, root_chat_id=chat, root_answer_id=answer, model=P.MODEL)}
    if mutation == "before_source": before["messages"][0]["content"] = "different source"
    elif mutation == "after_tool": after["tools"] = []
    elif mutation == "unsigned_metadata": after["litellm_metadata"]["foreign_scope"] = "untrusted"
    else: actor = str(uuid4())
    with pytest.raises((P.ProofError, provenance.ProtocolError)):
        P.verify_budget_boundary(before, after, decode_call=provenance.decode_call, secret=secret, actor=actor)


def exact_profile():
    receipt = json.loads((ROOT / "local/goal584/current-route-compatibility-live-readback.safe.json").read_text(encoding="utf8"))
    w = receipt["current_live"]["webui"]; office = receipt["current_live"]["office"]
    return {"webui_image": P.WEBUI_IMAGE, "office_image": P.OFFICE_IMAGE,
            "webui_modules": w["module_sha256"], "office_modules": office["module_sha256"],
            "office_binary_sha256": office["binary_sha256"], "office_valves": w["functions"][0]["persisted_valves_allowlist"],
            "model": P.MODEL, "active": True, "function_calling": "native", "connection_index": 0, "api_type": "responses",
            "reasoning_settings": w["reasoning_settings"], "session_tool_server": {"id": "officecli", "enabled": True,
                "auth_type": "session", "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}],
                "custom_header_names": ["X-OpenWebUI-Chat-Id", "X-OpenWebUI-Message-Id"], "function_name_filter_list": ""}}


def test_current_profile_assertion(): P.verify_profile(exact_profile())


@pytest.mark.parametrize("mutation", ["stock_image", "stock_router", "binary", "valves", "model", "connection", "session", "compaction"])
def test_current_profile_mutations_fail(mutation):
    profile = copy.deepcopy(exact_profile())
    if mutation == "stock_image": profile["webui_image"] = "stock-v0.12.2-slim"
    elif mutation == "stock_router": profile["webui_modules"]["routers/openai.py"] = "af02463b799a817b307da5d03af25874ca14f477b883e913051b3b797d365955"
    elif mutation == "binary": profile["office_binary_sha256"] = "0" * 64
    elif mutation == "valves": profile["office_valves"]["no_reasoning_model_ids"] += ",gpt-6-luna"
    elif mutation == "model": profile["model"] = "gpt-6-sol"
    elif mutation == "connection": profile["connection_index"] = 1
    elif mutation == "session": profile["session_tool_server"]["auth_type"] = "bearer"
    else: profile["reasoning_settings"]["context_compaction_enabled"] = True
    with pytest.raises(P.ProofError): P.verify_profile(profile)


def frontend_owner(build, package, identity):
    """Run the existing complete-byte verifier; only its absolute IO paths move."""
    path = ROOT / "deploy/openwebui-upgrade-0122/verify_frontend_artifact.py"
    tree = ast.parse(path.read_bytes())
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    paths = {"/app/build": build, "/usr/local/lib/openwebui-media-upload": package}
    namespace = {"hashlib": hashlib, "json": json, "Path": lambda value: paths[value],
        "os": SimpleNamespace(environ={"WEBUI_BUILD_HASH": identity})}
    output = StringIO()
    with redirect_stdout(output): exec(compile(tree, str(path), "exec"), namespace)
    return json.loads(output.getvalue())


@pytest.fixture
def built_candidate(tmp_path):
    """Synthetic boundary DTOs and actual native frontend owner, no build claim."""
    revision = "a" * 40
    inputs = {"source_commit": revision, "upstream_commit": builder.UPSTREAM, "node_image": builder.NODE,
        "node_options": builder.NODE_OPTIONS,
        "runtime_base": (ROOT / "deploy/openwebui-upgrade-0122/runtime.Dockerfile").read_text().splitlines()[0].partition("=")[2],
        "source_archive_sha256": "b" * 64, "git_inputs_sha256": "c" * 64, "frontend_sources_sha256": "d" * 64}
    builder.write(tmp_path / "build-inputs.json", inputs)
    # The supported builder executes on Linux; reproduce its actual LF bytes
    # when the offline unit fixture is generated on Windows.
    path = tmp_path / "build-inputs.json"; path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    identity = builder.sha(tmp_path / "build-inputs.json")
    build = tmp_path / "build"; (build / "_app").mkdir(parents=True)
    builder.write(build / "_app/version.json", {"version": identity})
    (build / "entry.js").write_bytes(b"synthetic complete frontend byte fixture")
    package = tmp_path / "frontend-owner"; package.mkdir()
    builder.write(package / "frontend-files.json", builder.manifest(build))
    front = {"upstream_commit": builder.UPSTREAM, "build_identity": identity, "input_receipt_sha256": identity,
        "source_archive_sha256": inputs["source_archive_sha256"], "frontend_sources_sha256": inputs["frontend_sources_sha256"],
        "build_files_manifest_sha256": builder.sha(package / "frontend-files.json"), "build_files": 2}
    builder.write(package / "frontend-receipt.json", front)
    media = json.loads((ROOT / "deploy/openwebui-patches/media-upload-v0.12.2/manifest.json").read_bytes())
    tool = ast.parse((ROOT / "deploy/openwebui-patches/tool-context-v0.12.2/apply_context.py").read_bytes())
    patched = ast.literal_eval(next(n.value for n in tool.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "PATCHED" for t in n.targets)))
    modules = copy.deepcopy(P.WEBUI_MODULES) | {"utils/misc.py": patched["utils/misc.py"],
        **{n: media["files"]["backend/open_webui/" + n]["candidate_sha256"] for n in ("routers/files.py", "storage/provider.py")}}
    images = {n: {"id": "sha256:" + str(i) * 64,
        "tag": "goal584-office-" + n + ":" + revision[:12] + "-" + identity[:12], "repo_digests": []}
        for i, n in enumerate(("frontend", "webui", "office"), 1)}
    receipt = {"schema": 1, "source_commit": revision, "build_identity": identity, "inputs": inputs, "images": images,
        "webui": {"modules": modules, "build_hash": identity, "version": identity},
        "office": {"modules": copy.deepcopy(P.OFFICE_MODULES), "binary_sha256": P.OFFICE_BINARY_SHA256, "version": "1.0.152"},
        "frontend_manifest_sha256": front["build_files_manifest_sha256"], "native_office_accepted": False}
    running = {n: copy.deepcopy(receipt[n]) | {"image_ref": images[n]["id"], "image_id": images[n]["id"],
        "os": "linux", "architecture": "amd64"} for n in ("webui", "office")}
    running["webui"].update(frontend_receipt=front, frontend_manifest_sha256=front["build_files_manifest_sha256"],
        frontend_result=frontend_owner(build, package, identity))
    profile = {"webui_image": images["webui"]["id"], "office_image": images["office"]["id"],
        "webui_modules": copy.deepcopy(P.WEBUI_MODULES), "office_modules": copy.deepcopy(P.OFFICE_MODULES),
        "office_binary_sha256": P.OFFICE_BINARY_SHA256, "office_valves": copy.deepcopy(P.VALVES), "model": P.MODEL,
        "active": True, "function_calling": "native", "connection_index": 0, "api_type": "responses",
        "session_tool_server": {"id": "officecli", "enabled": True, "auth_type": "session",
            "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}],
            "custom_header_names": ["X-OpenWebUI-Chat-Id", "X-OpenWebUI-Message-Id"], "function_name_filter_list": ""},
        "reasoning_settings": {"context_compaction_enabled": False, "responses_stateful_env": "false",
            "task_model_default": "gpt-6-luna", "task_model_external": "gpt-6-luna",
            "task_model_reasoning_effort": None, "task_custom_reasoning_effort": "none"}}
    return profile, receipt, running, revision, build, package


def test_built_candidate_requires_explicit_independent_inputs_and_keeps_default_ids(built_candidate):
    profile, receipt, running, revision, _, _ = built_candidate
    assert (P.WEBUI_IMAGE, P.OFFICE_IMAGE) == (
        "sha256:6cc2c633a09e325b31c03acf57a5c846e381577e98ab43a993c932c599044139",
        "sha256:df3acf071d04215006950e53738f20065b9174ef49d5f1c18864f061f18d16c3")
    P.verify_profile(profile, build_receipt=receipt, expected_revision=revision, running=running)
    with pytest.raises(P.ProofError): P.verify_profile(profile)
    baseline = copy.deepcopy(profile); baseline.update(webui_image=P.WEBUI_IMAGE, office_image=P.OFFICE_IMAGE)
    P.verify_profile(baseline)
    with pytest.raises(P.ProofError): P.verify_profile(baseline, build_receipt=receipt, expected_revision=revision, running=running)
    for options in ({"build_receipt": receipt}, {"expected_revision": revision}, {"running": running},
                    {"build_receipt": {}, "expected_revision": revision, "running": running}):
        with pytest.raises(P.ProofError): P.verify_profile(profile, **options)


@pytest.mark.parametrize("mutation", ["revision", "receipt_revision", "live_image", "live_ref", "qualification_image", "platform",
    "module", "binary", "frontend_identity", "frontend_result", "frontend_count_type", "frontend_flag", "manifest_join", "missing_office", "valves", "model", "connection", "session", "reasoning"])
def test_built_candidate_binding_and_shared_semantic_mutations_reject(built_candidate, mutation):
    profile, receipt, running, revision, _, _ = built_candidate
    P.verify_profile(profile, build_receipt=receipt, expected_revision=revision, running=running)
    if mutation == "revision": revision = "f" * 40
    elif mutation == "receipt_revision": receipt["source_commit"] = "f" * 40
    elif mutation == "live_image": running["webui"]["image_id"] = "sha256:" + "f" * 64
    elif mutation == "live_ref": running["office"]["image_ref"] = "foreign:mutable-tag"
    elif mutation == "qualification_image": running["office"].update(image_ref="sha256:" + "f" * 64, image_id="sha256:" + "f" * 64)
    elif mutation == "platform": running["office"]["architecture"] = "arm64"
    elif mutation == "module":
        for target in (profile["webui_modules"], receipt["webui"]["modules"], running["webui"]["modules"]): target["routers/openai.py"] = "f" * 64
    elif mutation == "binary":
        profile["office_binary_sha256"] = "f" * 64
        receipt["office"]["binary_sha256"] = running["office"]["binary_sha256"] = "f" * 64
    elif mutation == "frontend_identity":
        receipt["build_identity"] = "f" * 64
        for target in (receipt["webui"], running["webui"]): target.update(build_hash="f" * 64, version="f" * 64)
    elif mutation == "frontend_result": running["webui"]["frontend_result"]["frontend_files"] += 1
    elif mutation == "frontend_count_type": running["webui"]["frontend_result"]["frontend_files"] = 2.0
    elif mutation == "frontend_flag": running["webui"]["frontend_result"] = {"verified": True}
    elif mutation == "manifest_join": running["webui"]["frontend_manifest_sha256"] = "f" * 64
    elif mutation == "missing_office": del receipt["images"]["office"]
    elif mutation == "valves": profile["office_valves"]["priority"] = 1
    elif mutation == "model": profile["model"] = "gpt-6-sol"
    elif mutation == "connection": profile["connection_index"] = 1
    elif mutation == "session": profile["session_tool_server"]["auth_type"] = "bearer"
    else: profile["reasoning_settings"]["context_compaction_enabled"] = True
    # A newly computed surrounding self checksum cannot supersede independent
    # running/source or the shared retained profile semantics.
    receipt["self_checksum"] = P.digest(receipt)
    with pytest.raises(P.ProofError):
        P.verify_profile(profile, build_receipt=receipt, expected_revision=revision, running=running)


def test_rehashed_foreign_frontend_passes_its_own_manifest_but_not_trusted_build_join(built_candidate):
    profile, receipt, running, revision, build, package = built_candidate
    P.verify_profile(profile, build_receipt=receipt, expected_revision=revision, running=running)
    (build / "entry.js").write_bytes(b"foreign frontend bytes")
    builder.write(package / "frontend-files.json", builder.manifest(build))
    front = running["webui"]["frontend_receipt"]
    front["build_files_manifest_sha256"] = builder.sha(package / "frontend-files.json")
    builder.write(package / "frontend-receipt.json", front)
    running["webui"].update(frontend_manifest_sha256=front["build_files_manifest_sha256"],
        frontend_result=frontend_owner(build, package, receipt["build_identity"]))
    assert running["webui"]["frontend_result"]["complete_manifest"] == "verified"
    with pytest.raises(P.ProofError, match="office_build_frontend"):
        P.verify_profile(profile, build_receipt=receipt, expected_revision=revision, running=running)


@pytest.fixture(scope="module")
def service_profile_inputs():
    """Actual native schemas and existing Pipe registration; only API IO doubled."""
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    namespace = {"BaseModel": BaseModel, "ConfigDict": ConfigDict, "Optional": Optional,
        "copy": copy, "require": P.require, "FUNCTION_ID": "employee_budget_service",
        "MODELS": ("gpt-6-luna", P.MODEL)}
    def load(path, names):
        tree = ast.parse(path.read_bytes())
        nodes = [n for n in tree.body if getattr(n, "name", None) in names or isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
        assert len(nodes) == len(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    load(NATIVE / "routers/tasks.py", {"TaskConfigForm"})
    load(NATIVE / "models/functions.py", {"FunctionMeta", "FunctionModel"})
    namespace["FunctionModel"].model_rebuild(_types_namespace=namespace)
    load(ROOT / "scripts/goal584-budget-proof/provision_cost_display.py", {"MODEL_FIELDS", "model_body", "grant_set"})
    load(ROOT / "scripts/goal584-budget-proof/provision_admin.py", {"model_grant_changes"})
    load(ROOT / "scripts/goal584-budget-proof/prove_service_tasks.py", {"register_pipe_model"})
    values = {name: (name in {"ENABLE_TITLE_GENERATION", "ENABLE_FOLLOW_UP_GENERATION"}
        if name.startswith("ENABLE_") else "native-template-" + name)
        for name in namespace["TaskConfigForm"].model_fields}
    values.update(TASK_MODEL="gpt-6-luna", TASK_MODEL_EXTERNAL="gpt-6-luna",
        AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH=300,
        TASK_MODEL_PARAMS={"reasoning_effort": None, "temperature": .17,
            "custom_params": {"reasoning": {"effort": "none"}, "native_extra": {"keep": [1, "all"]}}})
    config = namespace["TaskConfigForm"](**values).model_dump()
    admin, actor = str(uuid4()), str(uuid4())
    # Deliberate full-context preservation sentinels, not a production target
    # snapshot. The deployed target has no custom reasoning override; that
    # nested override belongs only to the native TaskConfig above.
    target = {"id": "gpt-6-luna", "user_id": admin, "write_access": True, "name": "Native service target",
        "base_model_id": "gateway.gpt-6-luna", "is_active": True, "updated_at": 1234, "created_at": 1234,
        "params": {"system": "SERVICE_SYSTEM_SENTINEL", "temperature": .17, "max_tokens": 91,
            "reasoning_effort": None, "custom_params": {"native_extra": {"preserve": ["nested", 1]}}},
        "meta": {"capabilities": {"builtin_tools": False}}, "access_grants": []}
    class NativeApi:
        def __init__(self):
            self.rows = {model: copy.deepcopy(target) | {"id": model} for model in namespace["MODELS"]}
        def session(self, account, role):
            assert account["id"] == admin and role == "admin"
        def ok(self, method, path, *, token, body):
            assert (method, path, token) == ("POST", "/api/v1/models/create", "synthetic-admin")
            result = copy.deepcopy(body) | {"user_id": admin, "write_access": True, "created_at": 1234, "updated_at": 1234}
            result["meta"].update(profile_image_url=None, description=None)
            result["access_grants"] = [dict(g, id=str(uuid4()), resource_type="model",
                resource_id=body["id"], created_at=1234) for g in body["access_grants"]]
            self.rows[body["id"]] = result
            return copy.deepcopy(result)
        def model(self, token, model):
            assert token == "synthetic-admin"
            return copy.deepcopy(self.rows[model])
    api = NativeApi()
    state = {"admin": {"id": admin, "token": "synthetic-admin"}, "users": [{"id": actor}], "service_fixture": {}}
    namespace["register_pipe_model"](api, state)
    source = (ROOT / "deploy/openwebui-budgets/service_pipe.py").read_text(encoding="utf8")
    function = namespace["FunctionModel"](id="employee_budget_service", user_id=admin, name="Service tasks",
        type="pipe", content=source, meta={}, is_active=True, is_global=False, updated_at=1234, created_at=1234).model_dump()
    baseline = {"task_config": config, "target_model": target,
        "target_catalog": {"id": "gpt-6-luna", "owned_by": "openai", "name": "Native service target"}}
    current = copy.deepcopy(baseline)
    current["task_config"].update(TASK_MODEL="employee_budget_service", TASK_MODEL_EXTERNAL="employee_budget_service")
    current.update(function=function, valves={"target_model_id": "gpt-6-luna"},
        workspace_model=api.model("synthetic-admin", "employee_budget_service"))
    return dict(service_tasks=current, service_baseline=baseline, service_source=source)


def service_profile():
    profile = exact_profile()
    profile["reasoning_settings"].update(task_model_default="employee_budget_service", task_model_external="employee_budget_service")
    return profile


def test_service_profile_explicit_readback_preserves_full_native_inputs_and_default(service_profile_inputs):
    options, profile = copy.deepcopy(service_profile_inputs), service_profile()
    before = copy.deepcopy((options, profile))
    P.verify_profile(profile, **options)
    assert (options, profile) == before
    P.verify_profile(exact_profile())
    with pytest.raises(P.ProofError, match="office_profile_reasoning"): P.verify_profile(profile)
    with pytest.raises(P.ProofError, match="office_profile_reasoning"): P.verify_profile(exact_profile(), **options)
    for missing in options:
        incomplete = dict(options); incomplete.pop(missing)
        with pytest.raises(P.ProofError, match="office_service_readback"): P.verify_profile(profile, **incomplete)
    # Existing native owner accepts no pipe key or a null/empty pipe value.
    for value in (None, {}):
        variant = copy.deepcopy(options)
        for name in ("service_tasks", "service_baseline"): variant[name]["target_catalog"]["pipe"] = value
        P.verify_profile(profile, **variant)
    options["service_tasks"]["function"]["content"] = options["service_source"].replace("\n", "\r\n")
    P.verify_profile(profile, **options)


def test_service_profile_uses_nested_task_effort_without_inventing_target_override(service_profile_inputs):
    options = copy.deepcopy(service_profile_inputs)
    for name in ("service_baseline", "service_tasks"):
        params = options[name]["task_config"]["TASK_MODEL_PARAMS"]
        assert params["reasoning_effort"] is None
        assert params["custom_params"]["reasoning"] == {"effort": "none"}
        assert "reasoning_effort" not in params["custom_params"]
        # Match the deployed target's absence of model-level reasoning overrides;
        # full-context sentinels elsewhere remain deliberate test-only values.
        options[name]["target_model"]["params"] = {}
    frozen = copy.deepcopy(options)
    P.verify_profile(service_profile(), **options)
    assert options == frozen


@pytest.mark.parametrize("nested", [None, "none", [], {}, {"effort": None}, {"effort": True},
    {"effort": "low"}, {"reasoning_effort": "none"}])
def test_service_profile_rejects_coherent_wrong_nested_task_shapes(service_profile_inputs, nested):
    options = copy.deepcopy(service_profile_inputs)
    for name in ("service_baseline", "service_tasks"):
        options[name]["task_config"]["TASK_MODEL_PARAMS"]["custom_params"]["reasoning"] = copy.deepcopy(nested)
    with pytest.raises(P.ProofError, match="office_service_task_config"):
        P.verify_profile(service_profile(), **options)


def test_service_profile_rejects_the_withdrawn_coherent_legacy_top_level_premise(service_profile_inputs):
    options = copy.deepcopy(service_profile_inputs)
    for name in ("service_baseline", "service_tasks"):
        params = options[name]["task_config"]["TASK_MODEL_PARAMS"]
        params["custom_params"].pop("reasoning")
        params["custom_params"]["reasoning_effort"] = "none"
        # This satisfied the withdrawn ddf761e0/8e1f4086 predicate, while the
        # current deployed task shape is nested reasoning.effort instead.
        assert params.get("reasoning_effort") is None
        assert params["custom_params"].get("reasoning_effort") == "none"
    with pytest.raises(P.ProofError, match="office_service_task_config"):
        P.verify_profile(service_profile(), **options)


@pytest.mark.parametrize("mutation", ["selector_default", "selector_external", "profile_selector", "baseline_selector",
    "task_params", "task_reasoning", "task_prompt", "task_flag", "target_id", "target_write", "target_active", "target_pipe",
    "target_arena", "target_provider", "target_system", "target_params", "target_base", "target_stale", "catalog_stale",
    "function_source", "function_id", "function_owner", "function_type", "function_inactive", "function_global", "valve_target",
    "workspace_id", "workspace_owner", "workspace_write", "workspace_params", "workspace_system", "workspace_base",
    "workspace_missing_base", "workspace_inactive", "workspace_tools", "workspace_filter", "workspace_skill", "workspace_extra",
    "session", "route", "modules", "valves", "compaction"])
def test_service_profile_rejects_actual_native_readback_mutations(service_profile_inputs, mutation):
    options, profile = copy.deepcopy(service_profile_inputs), service_profile()
    current, baseline = options["service_tasks"], options["service_baseline"]
    config, target, catalog, function, workspace = (current[k] for k in
        ("task_config", "target_model", "target_catalog", "function", "workspace_model"))
    if mutation == "selector_default": config["TASK_MODEL"] = "gpt-6-luna"
    elif mutation == "selector_external": config["TASK_MODEL_EXTERNAL"] = "foreign-pipe"
    elif mutation == "profile_selector": profile["reasoning_settings"]["task_model_external"] = "gpt-6-luna"
    elif mutation == "baseline_selector": baseline["task_config"]["TASK_MODEL"] = "foreign-model"
    elif mutation == "task_params": config["TASK_MODEL_PARAMS"]["custom_params"]["native_extra"]["keep"].pop()
    elif mutation == "task_reasoning":
        for readback in (current, baseline): readback["task_config"]["TASK_MODEL_PARAMS"]["custom_params"]["reasoning"]["effort"] = "low"
    elif mutation == "task_prompt": config["FOLLOW_UP_GENERATION_PROMPT_TEMPLATE"] = "rewritten native history"
    elif mutation == "task_flag": config["ENABLE_FOLLOW_UP_GENERATION"] = False
    elif mutation == "target_id":
        for readback in (current, baseline): readback["target_model"]["id"] = "gpt-5.4-mini"
    elif mutation == "target_write":
        for readback in (current, baseline): readback["target_model"]["write_access"] = False
    elif mutation == "target_active":
        for readback in (current, baseline): readback["target_model"]["is_active"] = False
    elif mutation in ("target_pipe", "target_arena", "target_provider"):
        key, value = {"target_pipe": ("pipe", {"type": "pipe"}), "target_arena": ("arena", True),
            "target_provider": ("owned_by", "ollama")}[mutation]
        for readback in (current, baseline): readback["target_catalog"][key] = value
    elif mutation == "target_system": target["params"]["system"] = "changed target instructions"
    elif mutation == "target_params": target["params"]["custom_params"]["native_extra"]["preserve"].pop()
    elif mutation == "target_base": target["base_model_id"] = "foreign-native-connection"
    elif mutation == "target_stale": target["updated_at"] -= 1
    elif mutation == "catalog_stale": catalog["name"] = "stale target catalog"
    elif mutation.startswith("function_"):
        key, value = {"function_source": ("content", function["content"].replace("class Pipe:", "class StalePipe:")),
            "function_id": ("id", "foreign-pipe"), "function_owner": ("user_id", str(uuid4())),
            "function_type": ("type", "filter"), "function_inactive": ("is_active", False),
            "function_global": ("is_global", True)}[mutation]
        function[key] = value
    elif mutation == "valve_target": current["valves"]["target_model_id"] = P.MODEL
    elif mutation.startswith("workspace_"):
        if mutation == "workspace_missing_base": workspace.pop("base_model_id")
        elif mutation == "workspace_tools": workspace["meta"]["toolIds"] = ["foreign-tool"]
        elif mutation == "workspace_filter": workspace["meta"]["filterIds"] = ["foreign-filter"]
        elif mutation == "workspace_skill": workspace["meta"]["skillIds"] = ["foreign-skill"]
        elif mutation == "workspace_extra": workspace["meta"]["knowledge"] = ["foreign-context"]
        else:
            key, value = {"workspace_id": ("id", "foreign-pipe"), "workspace_owner": ("user_id", str(uuid4())),
                "workspace_write": ("write_access", False), "workspace_params": ("params", {"temperature": .81}),
                "workspace_system": ("params", {"system": "PIPE_SYSTEM_SENTINEL"}),
                "workspace_base": ("base_model_id", "gpt-6-luna"), "workspace_inactive": ("is_active", False)}[mutation]
            workspace[key] = value
    elif mutation == "session": profile["session_tool_server"]["auth_type"] = "bearer"
    elif mutation == "route": profile["api_type"] = "chat_completions"
    elif mutation == "modules": profile["webui_modules"]["routers/openai.py"] = "f" * 64
    elif mutation == "valves": profile["office_valves"]["priority"] = 1
    else: profile["reasoning_settings"]["context_compaction_enabled"] = True
    with pytest.raises(P.ProofError): P.verify_profile(profile, **options)


def test_service_profile_and_actual_build_admission_compose_without_bypassing_either(built_candidate, service_profile_inputs):
    profile, receipt, running, revision, _, _ = built_candidate
    profile["reasoning_settings"].update(task_model_default="employee_budget_service", task_model_external="employee_budget_service")
    options = copy.deepcopy(service_profile_inputs)
    P.verify_profile(profile, build_receipt=receipt, expected_revision=revision, running=running, **options)
    running["office"]["image_id"] = "sha256:" + "f" * 64
    with pytest.raises(P.ProofError, match="office_build_live_image"):
        P.verify_profile(profile, build_receipt=receipt, expected_revision=revision, running=running, **options)
