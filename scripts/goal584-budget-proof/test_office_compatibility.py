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
from decimal import Decimal
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
    for text in paragraphs[:2]: paragraph(body, text)
    tbl = ET.SubElement(body, WORD + "tbl")
    for row in table:
        tr = ET.SubElement(tbl, WORD + "tr")
        for text in row: paragraph(ET.SubElement(tr, WORD + "tc"), text)
    for text in paragraphs[14:]: paragraph(body, text)
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


def full_capture(component, *, provider=None, encrypted_reasoning=False, expected_instruction=None):
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
    instruction = expected_instruction if expected_instruction is not None else "Preserve explicit instructions; perform the complete Office task."
    owner = {"actor": actor, "key_hash": "a" * 64, "chat_id": chat, "answer_id": answer,
             "wire_model": "goal584-office-wire", "native_specs": component.specs, "exported": exported,
             "png": rendered.content, "native_responses_payload": component.router["convert_to_responses_payload"],
             "expected_instruction": instruction}
    secret = "synthetic-component-secret-with-no-production-use"
    body = {"model": P.MODEL, "messages": [{"role": "system", "content": instruction},
            {"role": "assistant", "content": P.SOURCE}, {"role": "user", "content": P.USER_REQUEST}],
            "tools": [{"type": "function", "function": copy.deepcopy(s)} for s in component.specs],
            "reasoning": {"effort": "low"}, "include": ["reasoning.encrypted_content"], "store": False, "stream": True,
            "parallel_tool_calls": False, "max_completion_tokens": 1024}
    if provider is not None:
        owner["wire_model"] = provider.OFFICE_MODEL
        body.pop("reasoning")
        if not encrypted_reasoning: body.pop("include")
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


def buffered_native_models():
    import office_fixture
    import yaml
    return yaml.safe_load('model_list:\n' + office_fixture.OFFICE_MODELS)['model_list']


def test_buffered_profile_requires_native_primary_flag_and_preserves_service_identity():
    models = buffered_native_models(); original = copy.deepcopy(models)
    profile = P.verify_buffered_provider_profile(models)
    assert P.provider_transport_from_profile() == 'native'
    assert P.provider_transport_from_profile(profile) == 'buffered'
    assert profile['primary']['supports_native_streaming'] is False
    assert profile['service']['supports_native_streaming'] is None
    assert models == original and 'api_key' not in json.dumps(profile)


@pytest.mark.parametrize('mutation', ['missing', 'true', 'integer', 'duplicate', 'provider', 'deployment',
    'mode', 'service_flag', 'service_provider', 'profile_extra', 'profile_missing'])
def test_buffered_profile_rejects_missing_ambiguous_or_drifting_native_configuration(mutation):
    models = buffered_native_models()
    if mutation == 'missing': models[0]['model_info'].pop('supports_native_streaming')
    elif mutation == 'true': models[0]['model_info']['supports_native_streaming'] = True
    elif mutation == 'integer': models[0]['model_info']['supports_native_streaming'] = 0
    elif mutation == 'duplicate': models.append(copy.deepcopy(models[0]))
    elif mutation == 'provider': models[0]['litellm_params']['model'] = 'openai/other'
    elif mutation == 'deployment': models[0]['model_info']['id'] = 'other'
    elif mutation == 'mode': models[0]['model_info']['mode'] = 'chat'
    elif mutation == 'service_flag': models[1]['model_info']['supports_native_streaming'] = False
    elif mutation == 'service_provider': models[1]['litellm_params']['model'] = 'openai/other'
    else:
        profile = P.verify_buffered_provider_profile(models)
        if mutation == 'profile_extra': profile['untrusted_mode'] = True
        else: profile['primary'].pop('supports_native_streaming')
        with pytest.raises(P.ProofError): P.provider_transport_from_profile(profile)
        return
    with pytest.raises(P.ProofError): P.verify_buffered_provider_profile(models)


def test_buffered_full_factory_wire_contract_has_one_exact_transport_delta(component):
    calls, owner = wire_capture(component); original = copy.deepcopy(calls)
    for call in calls: call['provider']['body'].pop('stream')
    assert P.verify_wire_calls(calls, **owner, provider_transport='buffered')
    with pytest.raises(P.ProofError): P.verify_wire_calls(calls, **owner)
    with pytest.raises(P.ProofError): P.verify_wire_calls(original, **owner, provider_transport='buffered')
    for before, after in zip(original, calls):
        expected = copy.deepcopy(before); expected['provider']['body'].pop('stream')
        assert after == expected and after['wire_before_auth']['stream'] is True


@pytest.mark.parametrize('mutation', ['false', 'true', 'integer', 'input', 'tools', 'instruction', 'store', 'model'])
def test_buffered_full_provider_comparison_never_accepts_other_transport_or_context_changes(component, mutation):
    calls, owner = wire_capture(component)
    for call in calls: call['provider']['body'].pop('stream')
    body = calls[0]['provider']['body']
    if mutation in ('false', 'true', 'integer'): body['stream'] = {'false': False, 'true': True, 'integer': 0}[mutation]
    elif mutation == 'input': body['input'].pop()
    elif mutation == 'tools': body['tools'].pop()
    elif mutation == 'instruction': body['instructions'] = 'lost full instruction'
    elif mutation == 'store': body['store'] = True
    else: body['model'] = 'other'
    with pytest.raises(P.ProofError): P.verify_wire_calls(calls, **owner, provider_transport='buffered')


def buffered_saved_case(case):
    call, kwargs = copy.deepcopy((case.call, case.kwargs))
    for item in [*kwargs['first_calls'], call]: item['provider']['body'].pop('stream')
    kwargs['provider_transport'] = 'buffered'
    return SimpleNamespace(call=call, kwargs=kwargs)


def test_buffered_saved_continuation_keeps_complete_native_factory_context(saved_continuation):
    case = buffered_saved_case(saved_continuation)
    assert P.verify_saved_continuation(case.call, **case.kwargs)
    with pytest.raises(P.ProofError):
        P.verify_saved_continuation(case.call, **{k:v for k,v in case.kwargs.items() if k != 'provider_transport'})
    assert case.kwargs['saved_output'] == saved_continuation.kwargs['saved_output']
    assert case.kwargs['native_saved'] == saved_continuation.kwargs['native_saved']


@pytest.mark.parametrize('mutation', ['lost_opaque', 'truncated_opaque', 'lost_tool', 'wrong_image',
    'prior_source', 'payee', 'parent_chat', 'packet_source'])
def test_buffered_saved_context_reuses_all_original_coherent_loss_guards(saved_continuation, mutation):
    test_saved_continuation_rejects_coherent_context_loss_and_native_auth_packet_drift(
        buffered_saved_case(saved_continuation), mutation)


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


@pytest.fixture(scope="module")
def saved_context_owners():
    from test_office_fixture import native_context_owners
    return native_context_owners()


@pytest.fixture
def continuation_submission_packet():
    # Reuse the existing browser IO fixture's ordinary one-click submission,
    # rather than authoring a second native request-shape fixture here.
    import test_office_browser as browser
    world = browser.ContinuationBrowser(None)
    page = SimpleNamespace(world=world, fields={'#chat-input': P.CONTINUATION_REQUEST}, pending=SimpleNamespace())
    browser.ContinuationLocator(page, '#send-message-button').click()
    response = page.pending.value
    sent, ack = response.request.post_data_json, response.json()
    assert json.loads(response.request.post_data) == sent and json.loads(response.body()) == ack
    options = {'http_status': response.status, 'chat_id': browser.CHAT, 'first_answer_id': browser.ANSWER,
               'prior_message_ids': list(world.before['chat']['history']['messages'])}
    return sent, ack, options


@pytest.mark.parametrize('content,ack_chat', [('text', True), ('blocks', True), ('text', False)])
def test_continuation_submission_shared_owner_accepts_native_text_shapes_and_existing_ack_fallback(continuation_submission_packet, content, ack_chat):
    sent, ack, options = continuation_submission_packet
    if content == 'blocks':
        sent['user_message']['content'] = [{'type': 'text', 'text': P.CONTINUATION_REQUEST[:12]},
                                           {'type': 'text', 'text': P.CONTINUATION_REQUEST[12:]}]
    if not ack_chat: ack.pop('chat_id')
    before = copy.deepcopy((sent, ack, options))
    assert P.verify_continuation_submission(sent, ack, **options) == (sent['user_message']['id'], sent['id'])
    assert (sent, ack, options) == before


@pytest.mark.parametrize('mutation', ['model', 'chat', 'parent', 'stream', 'stream_integer', 'message_ids_missing',
    'message_ids_extra', 'message_model', 'message_answer', 'model_index', 'model_index_bool', 'model_index_float',
    'message_key', 'user_parent', 'user_role', 'user_content', 'user_image', 'user_content_key', 'user_content_type',
    'followup', 'followup_integer', 'task_shape', 'status', 'status_float', 'ack_chat', 'ack_shape', 'sent_shape',
    'user_shape', 'user_old', 'answer_old', 'same_ids', 'user_uppercase', 'user_no_dashes', 'answer_bad_uuid'])
def test_continuation_submission_rejects_coherent_raw_and_parsed_native_field_mutations(continuation_submission_packet, mutation):
    sent, ack, options = continuation_submission_packet
    user = sent['user_message']
    if mutation == 'model': sent['model'] = 'foreign-model'
    elif mutation == 'chat': sent['chat_id'] = str(uuid4())
    elif mutation == 'parent': sent['parent_id'] = str(uuid4())
    elif mutation == 'stream': sent['stream'] = False
    elif mutation == 'stream_integer': sent['stream'] = 1
    elif mutation == 'message_ids_missing': sent.pop('message_ids')
    elif mutation == 'message_ids_extra': sent['message_ids'].append(copy.deepcopy(sent['message_ids'][0]))
    elif mutation == 'message_model': sent['message_ids'][0]['model_id'] = 'foreign-model'
    elif mutation == 'message_answer': sent['message_ids'][0]['message_id'] = str(uuid4())
    elif mutation == 'model_index': sent['message_ids'][0]['modelIdx'] = 1
    elif mutation == 'model_index_bool': sent['message_ids'][0]['modelIdx'] = False
    elif mutation == 'model_index_float': sent['message_ids'][0]['modelIdx'] = 0.0
    elif mutation == 'message_key': sent['message_ids'][0]['extra'] = 'not native'
    elif mutation == 'user_parent': user['parentId'] = str(uuid4())
    elif mutation == 'user_role': user['role'] = 'assistant'
    elif mutation == 'user_content': user['content'] = 'Different next prompt'
    elif mutation == 'user_image': user['content'] = [{'type': 'image_url', 'image_url': 'synthetic'}]
    elif mutation == 'user_content_key': user['content'] = [{'type': 'text', 'text': P.CONTINUATION_REQUEST, 'extra': True}]
    elif mutation == 'user_content_type': user['content'] = {'type': 'text', 'text': P.CONTINUATION_REQUEST}
    elif mutation == 'followup': sent['background_tasks']['follow_up_generation'] = False
    elif mutation == 'followup_integer': sent['background_tasks']['follow_up_generation'] = 1
    elif mutation == 'task_shape': sent['background_tasks'] = []
    elif mutation == 'status': options['http_status'] = 401
    elif mutation == 'status_float': options['http_status'] = 200.0
    elif mutation == 'ack_chat': ack['chat_id'] = str(uuid4())
    elif mutation == 'ack_shape': ack = []
    elif mutation == 'sent_shape': sent = []
    elif mutation == 'user_shape': sent['user_message'] = []
    elif mutation == 'user_old': user['id'] = options['prior_message_ids'][0]
    elif mutation == 'answer_old': sent['id'] = sent['message_ids'][0]['message_id'] = options['prior_message_ids'][0]
    elif mutation == 'same_ids': sent['id'] = sent['message_ids'][0]['message_id'] = user['id']
    elif mutation == 'user_uppercase': user['id'] = 'AAAAAAAA-1111-4111-8111-111111111111'
    elif mutation == 'user_no_dashes': user['id'] = user['id'].replace('-', '')
    else: sent['id'] = sent['message_ids'][0]['message_id'] = 'not-a-native-uuid'
    # The gap is coherent mutation of both retained representations, not a
    # mismatch that a raw/parsed hash or JSON equality check already catches.
    raw, raw_ack = json.dumps(sent), json.dumps(ack)
    parsed, parsed_ack = json.loads(raw), json.loads(raw_ack)
    assert parsed == sent and parsed_ack == ack
    with pytest.raises(P.ProofError): P.verify_continuation_submission(parsed, parsed_ack, **options)


@pytest.fixture
def saved_continuation(component, monkeypatch, tmp_path, saved_context_owners):
    """Actual finite factory/native producers, with explicit auth/DB IO fixtures.

    The emitted native_context Python executes unchanged through the existing
    Docker/import leaf doubles. Saved JSON and auth observations here are source
    fixtures; they do not establish runtime DB ancestry or authenticated IO.
    """
    import test_office_fixture as context
    from test_office_provider import P as provider, memory_office_response
    import prove_office_readback as readback
    monkeypatch.setattr(provider, "REQUESTS", [])
    instruction = P.office_instruction((ROOT / "deploy/openwebui-functions/officecli_auto_attach_filter.py").read_bytes())
    artifact, calls, owner = full_capture(component, provider=provider, encrypted_reasoning=True,
                                         expected_instruction=instruction)
    for call in calls: del call["before_budget"], call["after_budget"]
    results = [v for v in calls[-1]["wire_before_auth"]["input"] if v.get("type") == "function_call_output"]
    saved = []
    for index, call in enumerate(calls):
        saved.extend(copy.deepcopy(call["provider"]["response"]["output"]))
        if index < 2:
            result = copy.deepcopy(results[index])
            if isinstance(result["output"], str): result["output"] = [{"type": "input_text", "text": result["output"]}]
            saved.append(result)
    saved = json.loads(json.dumps(saved))
    reasoning = [[v for v in call["provider"]["response"]["output"] if v["type"] == "reasoning"] for call in calls]
    observer = tmp_path / "native-observer"; observer.mkdir()
    with pytest.MonkeyPatch.context() as observed_io:
        world = context.native_context_world(observer, observed_io, saved_context_owners)
        default = world.fixture.native_context(context.BASE, world.receipt, world.revision, reasoning)
        native_saved = world.fixture.native_context(context.BASE, world.receipt, world.revision, reasoning, saved_output=saved)
        native_final = world.fixture.native_context(context.BASE, world.receipt, world.revision, reasoning,
            saved_output=calls[-1]["provider"]["response"]["output"])
        source_sha = P.digest(world.handoff["office_setup"]["openapi"])
        native_payload_bytes = [len(command[-1].encode("ascii")) for command in world.native_commands]
        owner["native_responses_payload"] = readback.native_converter(default, world.handoff)
    assert len(P.verify_wire_calls(calls, **owner)) == 3
    wire = copy.deepcopy(calls[0]["wire_before_auth"])
    wire["input"] += native_saved["saved_output_case"]["native_input"]
    wire["input"].append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": P.CONTINUATION_REQUEST}]})
    answer = str(uuid4()); secret = "synthetic-saved-continuation-signed-scope-secret"
    after = copy.deepcopy(wire)
    after["litellm_metadata"] = {"owui_budget_provenance": provenance.encode_call(secret, user_id=owner["actor"],
        chat_id=owner["chat_id"], answer_id=answer, root_chat_id=owner["chat_id"], root_answer_id=answer, model=P.MODEL)}
    claims = P.verify_budget_boundary(wire, after, decode_call=provenance.decode_call, secret=secret, actor=owner["actor"])
    scope = {**calls[0]["verified_cost_scope"], "answer_id": answer, "root_answer_id": answer, "call_id": claims["jti"]}
    status, _ = memory_office_response({**copy.deepcopy(wire), "model": owner["wire_model"]})
    assert status == [200] and len(provider.REQUESTS) == 4
    physical = copy.deepcopy(provider.REQUESTS[-1])
    physical["lifecycle"] = {k: physical["lifecycle"][k] for k in ("terminal", "outcome")}
    call = {**calls[0], "wire_before_auth": wire, "wire_after_auth": copy.deepcopy(wire),
            "verified_cost_scope": scope, "provider": physical}
    kwargs = {**owner, "answer_id": answer, "first_calls": calls, "saved_output": saved,
              "native_saved": native_saved, "native_final": native_final, "native_source_sha256": source_sha}
    return SimpleNamespace(call=call, kwargs=kwargs, artifact=artifact, native_payload_bytes=native_payload_bytes)


def test_saved_continuation_actual_factory_full_native_join_and_shared_auth_guards(saved_continuation, monkeypatch):
    case = saved_continuation
    original = copy.deepcopy((case.call, case.kwargs))
    real = P.verify_wire_call; observed = []
    def single(call, **kwargs):
        observed.append(call["provider"]["id"])
        return real(call, **kwargs)
    monkeypatch.setattr(P, "verify_wire_call", single)
    assert P.verify_saved_continuation(case.call, **case.kwargs) == {
        case.call["provider"]["id"]: case.call["verified_cost_scope"]}
    assert observed == [v["provider"]["id"] for v in case.kwargs["first_calls"]] + [case.call["provider"]["id"]]
    assert (case.call, case.kwargs) == original
    assert len(case.call["wire_before_auth"]["tools"]) == 14
    assert len(case.kwargs["saved_output"]) == 8 and len(case.call["wire_before_auth"]["input"]) == 11
    assert len([v for v in case.kwargs["saved_output"] if v["type"] == "reasoning"]) == 3
    assert all(size <= 96 * 1024 for size in case.native_payload_bytes)
    assert len(case.native_payload_bytes) == 3


@pytest.mark.parametrize("mutation", ["lost_opaque", "truncated_opaque", "truncated_last_opaque", "coherent_final_native_opaque", "lost_tool", "wrong_image", "prior_source",
    "prior_user", "new_user", "extra_user", "include", "tool_schema", "instructions", "store", "previous_response",
    "auth", "key", "attestation", "unconsumed", "parent_chat", "parent_answer", "old_answer", "payee", "service",
    "nonce", "provider_id", "provider_body", "usage", "lifecycle", "new_tool", "different_file",
    "packet_modules", "packet_source", "packet_schema", "packet_echo", "packet_input", "final_echo", "final_input",
    "packet_reasoning", "packet_specs"])
def test_saved_continuation_rejects_coherent_context_loss_and_native_auth_packet_drift(saved_continuation, mutation):
    call, options = copy.deepcopy((saved_continuation.call, saved_continuation.kwargs))
    wires = (call["wire_before_auth"], call["wire_after_auth"], call["provider"]["body"])
    scope = call["verified_cost_scope"]
    if mutation == "coherent_final_native_opaque":
        values = [options["native_final"]["saved_output_case"]["native_input"],
                  options["native_saved"]["saved_output_case"]["native_input"], *[w["input"] for w in wires]]
        for items in values:
            [v for v in items if v.get("type") == "reasoning"][-1]["encrypted_content"] = "forged native final opaque"
    elif mutation in ("lost_opaque", "truncated_opaque", "truncated_last_opaque", "lost_tool", "wrong_image"):
        # Coherently damage DB output, observed native saved input and all new
        # wires. Agreement between only those observations must never suffice.
        values = [options["saved_output"], options["native_saved"]["saved_output_case"]["input_saved_output"],
                  options["native_saved"]["saved_output_case"]["native_input"], *[w["input"] for w in wires]]
        for items in values:
            if mutation == "lost_opaque": items.remove(next(v for v in items if v.get("type") == "reasoning"))
            elif mutation in ("truncated_opaque", "truncated_last_opaque"):
                [v for v in items if v.get("type") == "reasoning"][0 if mutation == "truncated_opaque" else -1]["encrypted_content"] = "truncated"
            elif mutation == "lost_tool": items.remove(next(v for v in items if v.get("type") == "function_call_output"))
            else:
                next(v for v in P._nodes(items) if v.get("type") == "input_image")["image_url"] = "data:image/png;base64,AA=="
    elif mutation in ("prior_source", "prior_user", "new_user", "extra_user", "include", "tool_schema", "instructions", "store", "previous_response"):
        for wire in wires:
            if mutation == "prior_source": next(v for v in wire["input"] if v.get("role") == "assistant")["content"][0]["text"] = "source omitted"
            elif mutation == "prior_user": next(v for v in wire["input"] if v.get("role") == "user")["content"][0]["text"] = "wrong prior user"
            elif mutation == "new_user": wire["input"][-1]["content"][0]["text"] = "wrong next user"
            elif mutation == "extra_user": wire["input"].append(copy.deepcopy(wire["input"][-1]))
            elif mutation == "include": wire.pop("include")
            elif mutation == "tool_schema": wire["tools"].pop()
            elif mutation == "instructions": wire["instructions"] = "short instruction"
            elif mutation == "store": wire["store"] = True
            else: wire["previous_response_id"] = "resp-stateful"
    elif mutation == "auth": call["auth_user_id"] = str(uuid4())
    elif mutation == "key": call["auth_key_hash"] = "b" * 64
    elif mutation == "attestation": call["attestation_present_before"] = False
    elif mutation == "unconsumed": call["provenance_removed_after"] = False
    elif mutation == "parent_chat": scope["root_chat_id"] = str(uuid4())
    elif mutation == "parent_answer": scope["root_answer_id"] = str(uuid4())
    elif mutation == "old_answer":
        scope["answer_id"] = scope["root_answer_id"] = options["answer_id"] = options["first_calls"][0]["verified_cost_scope"]["answer_id"]
    elif mutation == "payee": scope["user_id"] = str(uuid4())
    elif mutation == "service": scope["category"] = "service"
    elif mutation == "nonce": scope["call_id"] = options["first_calls"][0]["verified_cost_scope"]["call_id"]
    elif mutation == "provider_id": call["provider"]["id"] = call["provider"]["response"]["id"] = options["first_calls"][0]["provider"]["id"]
    elif mutation == "provider_body": call["provider"]["body"]["instructions"] = "provider drift"
    elif mutation == "usage": call["provider"]["response"]["usage"] = {"input_tokens": 0}
    elif mutation == "lifecycle": call["provider"]["lifecycle"]["terminal"] = False
    elif mutation == "new_tool": call["provider"]["response"]["output"].append(copy.deepcopy(options["first_calls"][0]["provider"]["response"]["output"][-1]))
    elif mutation == "different_file": call["provider"]["response"]["output"][-1]["content"][0]["text"] = "[Download](/api/v1/files/foreign/content)"
    elif mutation == "packet_modules": options["native_saved"]["module_sha256"]["utils/misc.py"] = "f" * 64
    elif mutation == "packet_source": options["native_saved"]["source_body_sha256"] = "f" * 64
    elif mutation == "packet_schema": options["native_saved"]["schema"] = True
    elif mutation == "packet_echo": options["native_saved"]["saved_output_case"]["input_saved_output"] = []
    elif mutation == "packet_input": options["native_saved"]["saved_output_case"]["native_input"] = []
    elif mutation == "final_echo": options["native_final"]["saved_output_case"]["input_saved_output"] = []
    elif mutation == "final_input": options["native_final"]["saved_output_case"]["native_input"] = []
    elif mutation == "packet_reasoning": options["native_final"]["reasoning_cases"][0]["native_input"] = []
    else: options["native_final"]["native_specs"].pop()
    with pytest.raises((P.ProofError, KeyError)): P.verify_saved_continuation(call, **options)


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


def continuation_financial_fixture(component, monkeypatch):
    """A new fixture phase begins after the original three calls, retaining all rows.

    Existing native decoder, rate validator and signed provenance owners remain
    real. These are component inputs, never a claim of saved DB/GUI origin.
    """
    original_before, primary_after, primary = financial_fixture(component, monkeypatch)
    assert P.verify_finance(original_before, primary_after, **primary) == {
        "physical_calls": 3, "new_raw_rows": 3, "native_spend_delta_usd": ".60"}
    before = copy.deepcopy(primary_after); after = copy.deepcopy(before)
    answer_id, provider_id = str(uuid4()), "resp_" + uuid4().hex
    secret = "synthetic-continuation-secret-with-no-production-use"
    body = {"model": P.MODEL, "messages": [{"role": "user", "content": P.CONTINUATION_REQUEST}]}
    admitted = copy.deepcopy(body)
    admitted["litellm_metadata"] = {"owui_budget_provenance": provenance.encode_call(secret,
        user_id=primary["actor"], chat_id=primary["chat_id"], answer_id=answer_id,
        root_chat_id=primary["chat_id"], root_answer_id=answer_id, model=P.MODEL)}
    claims = P.verify_budget_boundary(body, admitted, decode_call=provenance.decode_call, secret=secret,
        actor=primary["actor"])
    scope = {"schema": 1, "category": "personal", "user_id": primary["actor"], "model": P.MODEL,
        "chat_id": primary["chat_id"], "root_chat_id": primary["chat_id"], "answer_id": answer_id,
        "root_answer_id": answer_id, "call_id": claims["jti"]}
    row = copy.deepcopy(primary_after["rows"][-1])
    row["request_id"] = "resp_" + base64.b64encode(("litellm:custom_llm_provider:openai;model_id:office-deployment;response_id:"
        + provider_id).encode()).decode()
    row["metadata"]["spend_logs_metadata"]["owui_budget"] = copy.deepcopy(scope)
    after["rows"].append(row)
    after["user"]["spend"] = after["key"]["spend"] = .80
    kwargs = {**primary, "answer_id": answer_id, "calls_by_provider": {provider_id: scope}, "expected_calls": 1}
    return before, after, kwargs


def test_continuation_request_is_the_finite_existing_attachment_readback_contract():
    assert P.CONTINUATION_REQUEST == "Keep the attached file and report its native file ID without calling tools."


def test_one_call_finance_reuses_native_owners_after_original_three_without_mutating_inputs(component, monkeypatch):
    before, after, kwargs = continuation_financial_fixture(component, monkeypatch)
    original = copy.deepcopy((before, after, kwargs["calls_by_provider"]))
    assert len(before["rows"]) == 4 and len(after["rows"]) == 5
    assert before["user"]["spend"] == before["key"]["spend"] == .60
    assert P.verify_finance(before, after, **kwargs) == {
        "physical_calls": 1, "new_raw_rows": 1, "native_spend_delta_usd": ".20"}
    assert (before, after, kwargs["calls_by_provider"]) == original
    assert kwargs["answer_id"] != before["rows"][-1]["metadata"]["spend_logs_metadata"]["owui_budget"]["answer_id"]
    nonce = next(iter(kwargs["calls_by_provider"].values()))["call_id"]
    assert nonce not in [r["metadata"]["spend_logs_metadata"]["owui_budget"]["call_id"] for r in before["rows"][1:]]


def test_one_call_selector_keeps_explicit_three_equal_to_original_default(component, monkeypatch):
    before, after, kwargs = financial_fixture(component, monkeypatch)
    assert P.verify_finance(before, after, **kwargs, expected_calls=3) == P.verify_finance(before, after, **kwargs)


@pytest.mark.parametrize("value", [True, False, None, 0, -1, 2, 4, 1.0, 3.0, "1", "3", Decimal(1)])
def test_one_call_selector_rejects_nonfinite_counts_and_boolean_or_coerced_types(value):
    with pytest.raises(P.ProofError, match="office_expected_calls"):
        P.verify_finance({}, {}, calls_by_provider={}, actor=None, key_hash=None, chat_id=None, answer_id=None,
            wire_model=None, deployment_id=None, validate_scope=None, validate_rates=None, decode_response_id=None,
            expected_calls=value)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra_zero", "old_row", "missing_old_row", "old_payer",
    "empty_old_payers", "cap", "period", "counter_user", "counter_key", "nonce", "invalid_nonce", "nonce_map",
    "old_answer", "foreign_chat", "rate", "key", "model", "status", "usage", "usage_bool", "spend", "surplus_fee",
    "decoded_provider", "decoded_deployment", "old_provider", "wrong_expected_count", "missing_provider_map", "extra_provider_map"])
def test_one_call_finance_preserves_all_raw_row_scope_rate_history_and_fee_guards(component, monkeypatch, mutation):
    before, after, kwargs = continuation_financial_fixture(component, monkeypatch)
    row = after["rows"][-1]; scope = row["metadata"]["spend_logs_metadata"]["owui_budget"]
    if mutation == "missing": after["rows"].pop()
    elif mutation == "duplicate": after["rows"].append(copy.deepcopy(row))
    elif mutation == "extra_zero": after["rows"].append({"request_id": "unexpected-continuation-zero", "spend": 0})
    elif mutation == "old_row": after["rows"][1]["spend"] = .21
    elif mutation == "missing_old_row": after["rows"].pop(1)
    elif mutation == "old_payer": after["old_payers"]["existing-payer"]["key"]["spend"] = 5
    elif mutation == "empty_old_payers": before["old_payers"] = after["old_payers"] = {}
    elif mutation == "cap": after["key"]["max_budget"] = 11
    elif mutation == "period": after["user"]["budget_reset_at"] = "2027-01-01"
    elif mutation == "counter_user": after["user"]["spend"] = .81
    elif mutation == "counter_key": after["key"]["spend"] = .81
    elif mutation == "nonce": scope["call_id"] = str(uuid4())
    elif mutation == "invalid_nonce": scope["call_id"] = "not-a-native-nonce"
    elif mutation == "nonce_map": next(iter(kwargs["calls_by_provider"].values()))["call_id"] = str(uuid4())
    elif mutation == "old_answer":
        old = before["rows"][-1]["metadata"]["spend_logs_metadata"]["owui_budget"]
        for field in ("answer_id", "root_answer_id"):
            scope[field] = old[field]; next(iter(kwargs["calls_by_provider"].values()))[field] = old[field]
    elif mutation == "foreign_chat": scope["chat_id"] = scope["root_chat_id"] = str(uuid4())
    elif mutation == "rate": row["metadata"]["spend_logs_metadata"]["owui_billed_token_rates"]["rates"]["input_cost_per_token"] = .03
    elif mutation == "key": row["api_key"] = "b" * 64
    elif mutation == "model": row["model_id"] = "foreign-deployment"
    elif mutation == "status": row["status"] = "failure"
    elif mutation == "usage": row["total_tokens"] = 16
    elif mutation == "usage_bool": row["prompt_tokens"] = True
    elif mutation == "spend": row["spend"] = 0
    elif mutation == "surplus_fee": row["spend"] = .21
    elif mutation in ("decoded_provider", "decoded_deployment"):
        model = "foreign-deployment" if mutation == "decoded_deployment" else "office-deployment"
        provider = next(iter(kwargs["calls_by_provider"])) if mutation == "decoded_deployment" else "unobserved-provider"
        row["request_id"] = "resp_" + base64.b64encode(("litellm:custom_llm_provider:openai;model_id:" + model
            + ";response_id:" + provider).encode()).decode()
    elif mutation == "old_provider": row["request_id"] = before["rows"][-1]["request_id"]
    elif mutation == "wrong_expected_count": kwargs["expected_calls"] = 3
    elif mutation == "missing_provider_map": kwargs["calls_by_provider"] = {}
    else: kwargs["calls_by_provider"]["unobserved-provider"] = copy.deepcopy(scope)
    with pytest.raises((P.ProofError, ValueError)):
        P.verify_finance(before, after, **kwargs)


def buffered_financial_fixture(component, monkeypatch, count):
    before, after, kwargs = (continuation_financial_fixture(component, monkeypatch) if count == 1
                             else financial_fixture(component, monkeypatch))
    retained = {row['request_id'] for row in before['rows']}
    for row in after['rows']:
        if row['request_id'] not in retained:
            # Actual native buffered ID/SLP shape, decoded by the pinned SDK.
            row['request_id'] = kwargs['decode_response_id'](row['request_id'])['response_id']
    return before, after, {**kwargs, 'provider_transport': 'buffered'}


@pytest.mark.parametrize('count', [1, 3])
def test_buffered_finance_joins_native_raw_id_to_exact_row_deployment_scope_and_rates(component, monkeypatch, count):
    before, after, kwargs = buffered_financial_fixture(component, monkeypatch, count)
    original = copy.deepcopy((before, after, kwargs['calls_by_provider']))
    assert P.verify_finance(before, after, **kwargs) == {
        'physical_calls': count, 'new_raw_rows': count, 'native_spend_delta_usd': {1: '.20', 3: '.60'}[count]}
    assert (before, after, kwargs['calls_by_provider']) == original
    with pytest.raises(P.ProofError, match='office_row_dispatch_binding'):
        P.verify_finance(before, after, **{**kwargs, 'provider_transport': 'native'})


@pytest.mark.parametrize('count', [1, 3])
@pytest.mark.parametrize('mutation', ['encoded_id', 'partial_provider', 'partial_model', 'model', 'provider',
    'scope', 'scope_map', 'duplicate', 'missing', 'old_row', 'old_payer', 'cap', 'counter', 'usage', 'spend', 'rate'])
def test_buffered_finance_preserves_strict_binding_and_existing_money_guards(component, monkeypatch, count, mutation):
    before, after, kwargs = buffered_financial_fixture(component, monkeypatch, count)
    row = after['rows'][-1]; provider = row['request_id']; deployment = kwargs['deployment_id']
    if mutation in ('encoded_id', 'partial_provider', 'partial_model'):
        native_provider = 'None' if mutation == 'partial_provider' else 'openai'
        native_model = 'None' if mutation == 'partial_model' else deployment
        row['request_id'] = 'resp_' + base64.b64encode(('litellm:custom_llm_provider:' + native_provider
            + ';model_id:' + native_model + ';response_id:' + provider).encode()).decode()
    elif mutation == 'model': row['model_id'] = 'foreign-deployment'
    elif mutation == 'provider': row['request_id'] = 'resp_unobserved_provider'
    elif mutation == 'scope': row['metadata']['spend_logs_metadata']['owui_budget']['call_id'] = str(uuid4())
    elif mutation == 'scope_map': kwargs['calls_by_provider'][provider]['call_id'] = str(uuid4())
    elif mutation == 'duplicate': after['rows'].append(copy.deepcopy(row))
    elif mutation == 'missing': after['rows'].pop()
    elif mutation == 'old_row': after['rows'][0]['spend'] = 1
    elif mutation == 'old_payer': after['old_payers']['existing-payer']['key']['spend'] = 5
    elif mutation == 'cap': after['key']['max_budget'] = 11
    elif mutation == 'counter': after['key']['spend'] += .01
    elif mutation == 'usage': row['total_tokens'] = True
    elif mutation == 'spend': row['spend'] = .21
    else: row['metadata']['spend_logs_metadata']['owui_billed_token_rates']['rates']['input_cost_per_token'] = .03
    with pytest.raises(P.ProofError): P.verify_finance(before, after, **kwargs)


@pytest.mark.parametrize('transport', [None, True, False, 0, [], {}, 'auto', 'both', 'Buffered'])
def test_finance_transport_is_explicit_finite_and_never_inferred_from_rows(transport):
    with pytest.raises(P.ProofError, match='office_provider_transport'):
        P.verify_finance({}, {}, calls_by_provider={}, actor=None, key_hash=None, chat_id=None, answer_id=None,
            wire_model=None, deployment_id=None, validate_scope=None, validate_rates=None, decode_response_id=None,
            provider_transport=transport)


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
        dispatch={'verified_cost_scope': copy.deepcopy(scope), 'auth_user_id': payer, 'auth_key_hash': key_hash,
            'attestation_present_before': True, 'provenance_removed_after': True, 'route': '/responses',
            'provider': {'id': provider_id, 'response': {'id': provider_id}}},
        descriptor=descriptor, validate_scope=provenance.validate_persisted_service_scope,
        validate_rates=snapshots.validate_snapshot, decode_response_id=primary['decode_response_id'])
    return before, after, kwargs


def test_office_service_actual_sdk_scope_and_snapshot_owners_verify_one_separate_payer(component, monkeypatch):
    before, after, kwargs = service_financial_fixture(component, monkeypatch)
    assert kwargs['actor'] != kwargs['payer']
    assert P.verify_service_finance(before, after, **kwargs) == {
        'physical_calls': 1, 'new_raw_rows': 1, 'native_spend_delta_usd': '.20'}


@pytest.mark.parametrize('raw_provider_id', [False, True])
def test_native_opaque_service_log_id_joins_by_signed_nonce_and_observed_dispatch(component, monkeypatch, raw_provider_id):
    before, after, kwargs = service_financial_fixture(component, monkeypatch)
    row = after['rows'][-1]
    row['request_id'] = kwargs['provider_id'] if raw_provider_id else 'native-opaque-' + uuid4().hex
    decoded = kwargs['decode_response_id'](row['request_id'])
    assert decoded['custom_llm_provider'] is None and decoded['model_id'] is None
    assert P.verify_service_finance(before, after, **kwargs) == {
        'physical_calls': 1, 'new_raw_rows': 1, 'native_spend_delta_usd': '.20'}


@pytest.mark.parametrize('field,value', [('custom_llm_provider', 'anthropic'), ('model_id', 'other-deployment'),
    ('response_id', 'resp_unobserved')])
def test_native_encoded_service_id_still_rejects_foreign_provider_deployment_or_response(component, monkeypatch, field, value):
    before, after, kwargs = service_financial_fixture(component, monkeypatch)
    values = dict(custom_llm_provider='openai', model_id=kwargs['deployment_id'], response_id=kwargs['provider_id'])
    values[field] = value
    after['rows'][-1]['request_id'] = 'resp_' + base64.b64encode(('litellm:' + ';'.join(
        k + ':' + v for k, v in values.items())).encode()).decode()
    with pytest.raises(P.ProofError, match='office_service_dispatch_binding'):
        P.verify_service_finance(before, after, **kwargs)


@pytest.mark.parametrize('mutation', ['missing', 'scope', 'payer', 'key', 'attestation', 'consumed', 'route', 'provider', 'response'])
def test_service_log_requires_same_authenticated_provider_dispatch(component, monkeypatch, mutation):
    before, after, kwargs = service_financial_fixture(component, monkeypatch)
    after['rows'][-1]['request_id'] = 'native-opaque-' + uuid4().hex
    dispatch = kwargs['dispatch']
    if mutation == 'missing': kwargs['dispatch'] = None
    elif mutation == 'scope': dispatch['verified_cost_scope']['call_id'] = str(uuid4())
    elif mutation == 'payer': dispatch['auth_user_id'] = kwargs['actor']
    elif mutation == 'key': dispatch['auth_key_hash'] = 'f' * 64
    elif mutation == 'attestation': dispatch['attestation_present_before'] = False
    elif mutation == 'consumed': dispatch['provenance_removed_after'] = False
    elif mutation == 'route': dispatch['route'] = '/chat/completions'
    elif mutation == 'provider': dispatch['provider']['id'] = 'resp_unobserved'
    else: dispatch['provider']['response']['id'] = 'resp_unobserved'
    with pytest.raises(P.ProofError, match='office_service_dispatch_observation'):
        P.verify_service_finance(before, after, **kwargs)


def test_failed_service_binding_retains_actual_sdk_operands_without_raw_row_or_credentials(component, monkeypatch):
    before, after, kwargs = service_financial_fixture(component, monkeypatch)
    row = after['rows'][-1]
    # Exercise the actual native decoder on an unwrapped observed ID. This is
    # diagnostic coverage, not a claim that C67's unexported row had this form.
    row['request_id'] = kwargs['provider_id']
    row['metadata']['spend_logs_metadata']['owui_budget']['call_id'] = str(uuid4())
    row['private_arbitrary_metadata'] = {'token': 'private-financial-inventory'}
    original = copy.deepcopy(after)
    with pytest.raises(P.ProofError, match='office_service_dispatch_binding') as failed:
        P.verify_service_finance(before, after, **kwargs)
    binding = failed.value.office_service_binding
    atoms = failed.value.office_service_binding_atoms
    assert set(atoms) == P.SERVICE_BINDING_ATOMS and all(type(v) is bool for v in atoms.values())
    assert not atoms['scope_equal'] and atoms['row_id_is_raw_provider'] and atoms['row_model_matches_deployment']
    assert not atoms['decoded_provider'] and not atoms['decoded_model'] and atoms['decoded_response']
    assert atoms['opaque_log_id'] and atoms['native_id_binding']
    assert binding['scope'] != binding['verified_scope'] == kwargs['verified_scope']
    assert binding['decoded'] == kwargs['decode_response_id'](row['request_id'])
    assert binding['request_id'] == kwargs['provider_id']
    assert binding['expected']['deployment_id'] == kwargs['deployment_id']
    assert set(binding['row']) == {'user', 'model', 'model_id', 'model_group', 'session_id', 'status'}
    assert 'api_key' not in json.dumps(binding) and kwargs['key_hash'] not in json.dumps(binding)
    assert 'private-financial-inventory' not in json.dumps(binding) and after == original


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


@pytest.mark.parametrize('atom,expected', [
    ('native_saved_join_match', (False, True, True, True, True)),
    ('native_saved_has_eight_items', (True, False, True, True, True)),
    ('saved_reasoning_matches_provider', (True, True, False, True, True)),
    ('native_reasoning_matches_provider', (True, True, True, False, True)),
    ('provider_has_three_reasoning_items', (False, True, True, True, False)),
])
def test_saved_continuation_history_atoms_report_original_native_predicate_failures(saved_continuation, component, atom, expected):
    call, options = copy.deepcopy((saved_continuation.call, saved_continuation.kwargs))
    saved = options['native_saved']['saved_output_case']; final = options['native_final']['saved_output_case']
    if atom == 'native_saved_join_match':
        final['native_input'][-1]['content'][0]['text'] = 'different native final observation'
    elif atom == 'native_saved_has_eight_items':
        saved['native_input'].pop(); final['native_input'].pop()
    elif atom == 'saved_reasoning_matches_provider':
        # Keep normalized native inputs intact. Raw local/native status equality
        # remains required; diagnostics never turn this difference into a pass.
        for values in (options['saved_output'], saved['input_saved_output']):
            next(v for v in values if v.get('type') == 'reasoning')['status'] = None
    elif atom == 'native_reasoning_matches_provider':
        for values in (saved['native_input'], final['native_input']):
            [v for v in values if v.get('type') == 'reasoning'][-1]['encrypted_content'] = 'different opaque observation'
    else:
        # A genuine native conversion of extra provider reasoning items also
        # changes the full join. Record both failures; do not fake a converter
        # to force logically related predicates to fail independently.
        output = options['first_calls'][-1]['provider']['response']['output']
        extra = copy.deepcopy(next(v for v in output if v.get('type') == 'reasoning'))
        extra['id'] += '-extra'; output.insert(-1, extra)
        raw = options['saved_output']
        assert raw[-1].get('type') == 'message'
        raw[-1] = copy.deepcopy(extra)
        saved['input_saved_output'] = copy.deepcopy(raw); final['input_saved_output'] = copy.deepcopy(output)
        native = component.router; settings = {'reasoning_format': 'responses', 'flatten_tool_images': False}
        for observation in (saved, final):
            messages = native['convert_output_to_messages'](observation['input_saved_output'], raw=True, **settings)
            messages = native['process_messages_with_output'](messages, **settings)
            observation['native_input'] = native['convert_to_responses_payload']({'messages': messages})['input']
        options['native_responses_payload'] = native['convert_to_responses_payload']
        cases = [[v for v in first['provider']['response']['output'] if v.get('type') == 'reasoning']
                 for first in options['first_calls']]
        for packet in (options['native_saved'], options['native_final']):
            packet['reasoning_cases'] = [{'input_reasoning': copy.deepcopy(case), 'native_input':
                native['convert_to_responses_payload']({'messages': [{'role': 'assistant', 'output': case}]})['input']}
                for case in cases]
    if atom == 'native_reasoning_matches_provider':
        # The fixture deliberately shares the saved input with the before-auth
        # wire. Keep both auth projections and the provider body coherent so
        # this control reaches the intended native-history predicate.
        base = options['first_calls'][0]['wire_before_auth']['input']
        question = call['wire_after_auth']['input'][-1]
        for body in (call['wire_before_auth'], call['wire_after_auth'], call['provider']['body']):
            body['input'] = copy.deepcopy(base + saved['native_input'] + [question])
    original = copy.deepcopy((call, options))
    with pytest.raises(P.ProofError, match='^office_saved_provider_history$') as caught:
        P.verify_saved_continuation(call, **options)
    assert P.SAVED_HISTORY_ATOMS == ('native_saved_join_match', 'native_saved_has_eight_items',
        'saved_reasoning_matches_provider', 'native_reasoning_matches_provider', 'provider_has_three_reasoning_items')
    observed = caught.value.office_saved_history_atoms
    assert tuple(observed) == P.SAVED_HISTORY_ATOMS and tuple(observed.values()) == expected, json.dumps(observed, sort_keys=True)
    assert observed[atom] is False and all(type(value) is bool for value in observed.values())
    assert vars(caught.value) == {'office_saved_history_atoms': observed}
    assert (call, options) == original


@pytest.mark.parametrize('failure', ['auth', 'new_user', 'attachment'])
def test_saved_continuation_history_atoms_do_not_attach_to_other_proof_errors(saved_continuation, failure):
    call, options = copy.deepcopy((saved_continuation.call, saved_continuation.kwargs))
    if failure == 'auth': call['auth_user_id'] = str(uuid4())
    elif failure == 'new_user':
        for body in (call['wire_before_auth'], call['wire_after_auth'], call['provider']['body']):
            body['input'][-1]['content'][0]['text'] = 'different next prompt'
    else: call['provider']['response']['output'][-1]['content'][0]['text'] = 'different native file'
    with pytest.raises(P.ProofError) as caught: P.verify_saved_continuation(call, **options)
    assert str(caught.value) != 'office_saved_provider_history'
    assert not hasattr(caught.value, 'office_saved_history_atoms')
