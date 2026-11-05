"""Finite Office wire model over existing loopback HTTP and actual component owners.

Only Office CLI and native file/session HTTP are external IO doubles, reused
from the frozen component suite. No hand-authored export result or render PNG.
"""
import ast
import asyncio
import base64
import copy
import hashlib
import importlib.util
import inspect
import json
import logging
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

import test_office_compatibility as component_owner
import test_responses_provider as http_owner

P = http_owner.P
ROOT = Path(__file__).resolve().parents[2]
BASE = "8d62c6cac67689ada74d838f88383118c543bd5a"
BASE_SHA256 = "762b4f89acce9c06105206514ebfcec39aa58c33058efd40fb952bc861edcc88"


def native_service_request(native, send=None, messages=None):
    """Pinned task -> Functions -> actual ServicePipe -> native router JSON cut.

    Only user/config/model/connection/socket and final HTTP IO are doubled.
    The existing profile extractor owns patch application and converter hashes.
    """
    from collections.abc import Callable
    from datetime import datetime
    from enum import Enum
    from string import punctuation
    from urllib.parse import quote
    source_root = component_owner.NATIVE
    spec = importlib.util.spec_from_file_location("office_service_pipe_fixture", ROOT / "deploy/openwebui-budgets/tests/test_service_pipe.py")
    fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    ns = {"collections": __import__("collections"), "copy": copy, "deepcopy": copy.deepcopy, "Callable": Callable, "JSONCodec": json, "re": __import__("re"),
        "datetime": datetime, "Enum": Enum, "inspect": inspect, "log": logging.getLogger("office-native-service-fixture"),
        "quote": quote, "punctuation": punctuation, "BYPASS_MODEL_ACCESS_CONTROL": False, "BYPASS_ADMIN_ACCESS_CONTROL": False,
        "ENABLE_FORWARD_USER_INFO_HEADERS": False, "USER_GROUPS_PLACEHOLDERS": ("{{USER_GROUPS}}", "{{USER_GROUP_IDS}}")}
    def load(relative, names):
        raw = subprocess.check_output(["git", "-C", str(source_root.parents[1]), "show",
            "6a18585ff4c2e5f6805f682222cfbc46dc669ef8:backend/open_webui/" + relative], env=os.environ | {"GIT_NO_LAZY_FETCH": "1"})
        assert raw.replace(b"\r\n", b"\n") == (source_root / relative).read_bytes().replace(b"\r\n", b"\n")
        nodes = [n for n in ast.parse(raw).body if getattr(n, "name", None) in names or isinstance(n, ast.Assign)
            and any(getattr(t, "id", None) in names for t in n.targets)]
        assert len(nodes) == len(names)
        for node in nodes:
            if hasattr(node, "decorator_list"): node.decorator_list = []
            if getattr(node, "name", None) == "generate_follow_ups": node.args.defaults = []
        exec(compile(ast.Module(body=nodes, type_ignores=[]), relative, "exec", flags=__import__("__future__").annotations.compiler_flag), ns)
    load("utils/misc.py", {"deep_update", "get_content_from_message", "get_last_user_message", "get_last_user_message_item", "get_messages_content"})
    load("utils/task.py", {"get_task_model_id", "prompt_template", "prompt_variables_template", "replace_prompt_variable", "truncate_content",
        "apply_content_filter", "replace_messages_variable", "follow_up_generation_template", "parse_follow_ups"})
    load("utils/payload.py", {"apply_params_to_form_data"})
    load("utils/headers.py", {"custom_headers_require_user_groups", "get_user_groups_for_custom_headers", "get_custom_headers", "parse_custom_headers", "get_headers_and_cookies"})
    load("constants.py", {"TASKS"}); load("config.py", {"DEFAULT_FOLLOW_UP_GENERATION_PROMPT_TEMPLATE"})
    load("routers/tasks.py", {"apply_task_model_params", "get_task_model_generation_config", "generate_follow_ups"})
    load("functions.py", {"generate_function_chat_completion"}); load("utils/chat.py", {"generate_chat_completion"})
    # Extend the existing extractor's return only to inspect its exact router.
    tree = ast.parse(Path(component_owner.__file__).read_bytes())
    extractor = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "deployed_context_owner")
    ret = next(n for n in ast.walk(extractor) if isinstance(n, ast.Return))
    ret.value = ast.Tuple(elts=[ret.value, ast.parse("(mirror / 'routers/openai.py').read_bytes()", mode="eval").body], ctx=ast.Load())
    extraction = dict(component_owner.__dict__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[extractor], type_ignores=[])), "existing-office-extractor", "exec"), extraction)
    functions, router = extraction["deployed_context_owner"]()
    ns.update(functions)
    handlers = [n for n in ast.parse(router).body if isinstance(n, ast.FunctionDef) and n.name in {"openai_reasoning_model_handler", "is_openai_new_model"}]
    route = next(n for n in ast.parse(router).body if isinstance(n, ast.AsyncFunctionDef) and n.name == "generate_chat_completion")
    route.name = "native_openai_wire"; route.decorator_list = []; route.args.defaults = []
    end = next(i for i, n in enumerate(route.body) if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "payload" for t in n.targets)
        and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == "dumps")
    route.body = route.body[:end + 1] + [ast.parse("return capture(payload, headers, metadata)").body[0]]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*handlers, route], type_ignores=[])), "exact-native-router-http-cut", "exec",
        flags=__import__("__future__").annotations.compiler_flag), ns)
    class User(SimpleNamespace):
        def model_dump(self): return vars(self).copy()
    class Params:
        def model_dump(self): return {}
    wires = []
    async def run():
        case = fixture.ServicePipeTests(); await case.asyncSetUp()
        try:
            case.user = User(id=fixture.USER, role="user", name="Synthetic Office actor", email="office@example.invalid", variables={})
            target = {"id": "gpt-6-luna", "owned_by": "openai"}; source = {"id": "gpt-5.4-mini", "owned_by": "openai"}
            case.own_config["target_model_id"] = target["id"]; case.pipe.valves.target_model_id = target["id"]
            case.request.app.state.MODELS = {source["id"]: source, target["id"]: target,
                fixture.extension.FUNCTION_ID: {"id": fixture.extension.FUNCTION_ID, "owned_by": "openai", "pipe": {"type": "pipe"}}}
            case.request.app.state.OPENAI_MODELS = {target["id"]: {"urlIdx": 2}}
            case.models.get_model_by_id.side_effect = lambda model: SimpleNamespace(id=model, base_model_id=None, params=Params())
            case.request.scope = {"method": "POST", "path": "/api/chat/completions"}
            case.request.state = SimpleNamespace(direct=False, internal=False, model_id=source["id"], metadata={
                "user_id": fixture.USER, "chat_id": fixture.CHAT, "model": copy.deepcopy(source), "internal": False,
                "direct": False, "automation_id": None, "chat_context": {"params": {}, "messages": []}})
            case.request.headers = {}; case.request.cookies = {}
            async def connection(index):
                assert index == 2
                return fixture.URL + "/v1", fixture.SECRET, {"prefix_id": "gateway", "api_type": "responses",
                    "headers": {"X-OpenWebUI-User-Id": "{{USER_ID}}", "X-OpenWebUI-Task": "{{TASK}}"}}
            case.connection.side_effect = connection
            class Config:
                @classmethod
                async def get_many(cls, *keys):
                    return {"task.model.default": fixture.extension.FUNCTION_ID, "task.model.external": fixture.extension.FUNCTION_ID,
                        "task.model.params": {"reasoning_effort": None, "custom_params": {"reasoning": {"effort": "none"}}}}
                @classmethod
                async def get(cls, key): return True if key in ("task.follow_up.enable", "openai.enable") else ""
            async def pipeline(request, payload, user, models): return payload
            async def nothing(*args, **kwargs): return None
            async def module(*args, **kwargs): return case.pipe
            ns.update(Config=Config, Models=case.models, UserModel=User, check_model_access=case.access, get_openai_connection=connection,
                strip_provider_model_prefix=fixture.prefix_owner.strip_provider_model_prefix, process_pipeline_inlet_filter=pipeline,
                get_system_oauth_token=nothing, get_function_module_by_id=module, StreamingResponse=type("StreamingResponse", (), {}),
                generate_openai_chat_completion=ns["native_openai_wire"])
            case.modules["open_webui.utils.chat"].generate_chat_completion = ns["generate_chat_completion"]
            def capture(payload, headers, metadata):
                wire = json.loads(payload); carrier = wire.pop("litellm_metadata")
                claims = fixture.protocol.decode_service_call(carrier["owui_budget_provenance"], fixture.SECRET,
                    user_id=fixture.USER, model=target["id"], task="follow_up_generation")
                assert claims["payer_id"] == fixture.PAYER and headers["X-OpenWebUI-Task"] == "follow_up_generation"
                wire["model"] = "goal584-fake-office-service"  # Existing gateway's model alias/HTTP auth leaf.
                wires.append(copy.deepcopy(wire))
                return send(wire) if send else {"choices": [{"message": {"content": "{}"}}]}
            ns["capture"] = capture
            history = messages or [{"role": "user", "content": "Create the agreed Office note."},
                {"role": "assistant", "content": component_owner.P.SOURCE}, {"role": "user", "content": component_owner.P.USER_REQUEST},
                {"role": "assistant", "content": "[Download](/api/v1/files/finite-office-id/content)"}]
            result = await ns["generate_follow_ups"](case.request, {"model": source["id"], "messages": copy.deepcopy(history),
                "message_id": fixture.ANSWER, "chat_id": fixture.CHAT}, case.user)
            return result, wires, ns
        finally: case.doCleanups()
    return asyncio.run(run())


@pytest.fixture(scope="module")
def native():
    source = os.environ.get("GOAL584_NATIVE_SOURCE_ROOT")
    assert source, "Set primary cached WebUI source explicitly for this isolated worktree"
    component_owner.NATIVE = Path(source)
    return component_owner.native.__wrapped__()


@pytest.fixture
def component(monkeypatch, tmp_path, native):
    return component_owner.component.__wrapped__(monkeypatch, tmp_path, native)


@pytest.fixture(scope="module")
def server():
    http_owner.ResponsesHTTPTests.setUpClass()
    try:
        yield
    finally:
        http_owner.ResponsesHTTPTests.tearDownClass()


@pytest.fixture
def boundary(server):
    case = http_owner.ResponsesHTTPTests()
    case.setUp()
    return case


def exchange(boundary, component, stream):
    """Three explicit sends and two actual component operations; no runtime loop."""
    assert len(component.specs) == 14
    body = {"model": P.OFFICE_MODEL, "messages": [
        {"role": "system", "content": "Preserve explicit policy and complete prior answer."},
        {"role": "assistant", "content": component_owner.P.SOURCE},
        {"role": "user", "content": component_owner.P.USER_REQUEST}],
        "tools": [{"type": "function", "function": copy.deepcopy(s)} for s in component.specs],
        "reasoning": {"effort": "low", "summary": "auto"}, "include": ["reasoning.encrypted_content"],
        "parallel_tool_calls": False, "max_completion_tokens": 1024, "store": False, "stream": stream}
    prefix = copy.deepcopy(body["messages"])
    wires, results, outputs = [], [], []

    def send():
        wire = component.router["convert_to_responses_payload"](copy.deepcopy(body))
        status, value = boundary.http("/v1/responses", wire)
        assert status == 200
        if stream:
            events = boundary.events(value)
            for event in events:
                http_owner.TypeAdapter(http_owner.ResponseStreamEvent).validate_python(event)
            result = boundary.native_stream(events)
        else:
            result = value
            http_owner.native_parsers()["convert_responses_result"](copy.deepcopy(result))
        http_owner.Response.model_validate(result)
        row = boundary.terminal(result["id"])
        assert row["body"] == wire and row["response"] == result
        assert result["model"] == P.OFFICE_MODEL and result["usage"] == http_owner.USAGE
        assert row["lifecycle"]["outcome"] == "completed" and row["lifecycle"]["usage_sent"]
        wires.append(wire); results.append(result)
        return result

    def continue_with(result, call, actual_result):
        text, files, embeds = asyncio.run(component.middleware["process_tool_result"](
            None, call["name"], actual_result, "external"))
        assert not embeds
        # Same native typed item representation as the frozen component seam;
        # text/files are returned by the actual native result processor above.
        outputs.extend(copy.deepcopy(result["output"]))
        outputs.append({"type": "function_call_output", "call_id": call["call_id"], "output": [
            {"type": "input_text", "text": text},
            *[{"type": "input_image", "image_url": f["url"]} for f in files]]})
        options = {"reasoning_format": "responses", "flatten_tool_images": False}
        messages = component.router["convert_output_to_messages"](outputs, raw=True, **options)
        body["messages"] = prefix + component.router["process_messages_with_output"](messages, **options)

    first = send()
    export_call = next(item for item in first["output"] if item["type"] == "function_call")
    assert export_call["name"] == next(s["name"] for s in component.specs if s["name"].endswith("export_answer_to_word"))
    assert json.loads(export_call["arguments"]) == component_owner.P.EXPORT_ARGUMENTS
    exported_response = component.client.post("/v1/officecli/documents/export-answer",
        json=json.loads(export_call["arguments"]), headers={"Authorization": "Bearer caller",
            "X-OpenWebUI-Chat-Id": "chat", "X-OpenWebUI-Message-Id": "current"})
    assert exported_response.status_code == 200
    exported = exported_response.json()
    identifier = exported["result_file_id"]
    assert identifier in component.state["files"] and exported["result_file"]["id"] == identifier
    assert exported["source_text_preserved"] and exported["source_content_sha256"] == component_owner.P.SOURCE_SHA256
    continue_with(first, export_call, (exported, {}))

    second = send()
    render_call = next(item for item in second["output"] if item["type"] == "function_call")
    assert render_call["name"] == next(s["name"] for s in component.specs if s["name"].endswith("render_office_file"))
    assert json.loads(render_call["arguments"]) == {"file_id": identifier, "format": "docx", "grid": 2}
    rendered = component.client.post("/v1/officecli/render", json=json.loads(render_call["arguments"]),
        headers={"Authorization": "Bearer caller"})
    assert rendered.status_code == 200 and rendered.headers["content-type"] == "image/png"
    assert component.cli.calls[-1][-2:] == ("--grid", "2")
    image = "data:image/png;base64," + base64.b64encode(rendered.content).decode("ascii")
    continue_with(second, render_call, (image, {}))

    third = send()
    assert not any(item["type"] == "function_call" for item in third["output"])
    final = next(item for item in third["output"] if item["type"] == "message")
    assert "/api/v1/files/" + identifier + "/content" in final["content"][0]["text"]
    paired = next(item for item in wires[2]["input"] if item.get("type") == "function_call_output"
        and item["call_id"] == render_call["call_id"])
    assert paired["output"] == [{"type": "input_text", "text": render_call["name"] + ": Image file read successfully."},
        {"type": "input_image", "image_url": image}]
    for index, wire in enumerate(wires):
        assert wire["instructions"] == prefix[0]["content"]
        assert wire["input"][:len(wires[0]["input"])] == wires[0]["input"]
        assert {k: v for k, v in wire.items() if k != "input"} == {k: v for k, v in wires[0].items() if k != "input"}
        for earlier in results[:index]:
            reasoning = next(item for item in earlier["output"] if item["type"] == "reasoning")
            expected = {k: v for k, v in reasoning.items() if k != "status"}
            assert next(item for item in wire["input"] if item.get("id") == reasoning["id"]) == expected
        assert boundary.terminal(results[index]["id"])["body"] == wire
    assert len(boundary.rows()) == 3 and len({r["id"] for r in boundary.rows()}) == 3
    assert boundary.http("/__proof/requests")[1]["control"] == http_owner.DEFAULT
    return wires, exported, rendered.content


@pytest.mark.parametrize("stream", [False, True])
def test_actual_three_call_office_continuation_uses_native_dynamic_id_png_and_original_context(boundary, component, stream):
    exchange(boundary, component, stream)


def test_office_specific_bad_continuations_reject_before_physical_arrival(boundary, component):
    wires, exported, png = exchange(boundary, component, True)
    boundary.setUp()
    candidates = []
    def change(index, mutate):
        body = copy.deepcopy(wires[index]); mutate(body); candidates.append(body)
    def result(body, index=0):return [item for item in body["input"] if item.get("type") == "function_call_output"][index]
    def call(body, index=0):return [item for item in body["input"] if item.get("type") == "function_call"][index]
    change(0, lambda b: b["tools"].append(copy.deepcopy(b["tools"][0])))
    change(0, lambda b: b.__setitem__("tools", [t for t in b["tools"] if not t["name"].endswith("export_answer_to_word")]))
    change(0, lambda b: b.__setitem__("max_output_tokens", True))
    change(0, lambda b: b.__setitem__("max_output_tokens", 16))
    change(0, lambda b: b.__setitem__("unexpected", True))
    change(1, lambda b: result(b).__setitem__("call_id", "foreign-call"))
    change(1, lambda b: result(b).__setitem__("output", "{}"))
    change(1, lambda b: result(b).__setitem__("output", json.dumps(exported | {"result_file_id": "foreign-file"})))
    change(1, lambda b: result(b).__setitem__("output", json.dumps(exported | {"download_url": "/foreign"})))
    change(1, lambda b: result(b).__setitem__("output", json.dumps(exported | {"source_text_preserved": False})))
    change(2, lambda b: call(b, 1).__setitem__("arguments", json.dumps({"file_id": "foreign-file", "format": "docx", "grid": 2})))
    change(2, lambda b: call(b, 1).__setitem__("arguments", json.dumps({"file_id": exported["result_file_id"], "format": "docx", "grid": 1})))
    change(2, lambda b: result(b, 1).__setitem__("output", "image lost to text"))
    change(2, lambda b: result(b, 1).__setitem__("output", [None, {}]))
    change(2, lambda b: result(b, 1)["output"][0].__setitem__("text", "foreign tool image"))
    change(2, lambda b: result(b, 1)["output"][1].__setitem__("image_url", "https://foreign/image.png"))
    change(2, lambda b: result(b, 1)["output"][1].__setitem__("image_url", "data:image/png;base64,not-base64"))
    change(2, lambda b: result(b, 1)["output"][1].__setitem__("image_url", "data:image/png;base64," + base64.b64encode(b"not PNG").decode()))
    change(2, lambda b: b["input"].append({"role": "assistant", "content": [{"type": "input_image", "image_url": "foreign"}]}))
    for index, candidate in enumerate(candidates):
        assert boundary.http("/v1/responses", candidate)[0] == 400, index
    assert boundary.rows() == []


def test_office_does_not_expand_strict_r_profile_or_control_catalog(boundary, component):
    wires, _, _ = exchange(boundary, component, False)
    boundary.setUp()
    body = copy.deepcopy(wires[2]); body["model"] = P.RESPONSES_MODEL
    body["max_output_tokens"] = 16; body["tools"] = body["tools"][:2]
    assert boundary.http("/v1/responses", body)[0] == 400
    assert boundary.http("/v1/models")[1]["data"] == [
        {"id": model, "object": "model", "created": 0, "owned_by": "goal584-proof"} for model in P.MODELS]
    assert boundary.http("/__proof/control", {"office_mode": True})[0] == 400
    assert boundary.http("/__proof/requests")[1] == {"synthetic": True, "requests": [], "control": http_owner.DEFAULT}


def test_native_follow_up_through_service_pipe_responses_and_native_parser(boundary, native):
    results = []
    def send(wire):
        status, response = boundary.http("/v1/responses", wire)
        assert status == 200
        http_owner.Response.model_validate(response)
        row = boundary.terminal(response["id"])
        assert row["body"] == wire and row["response"] == response
        assert row["usage"] == response["usage"] == http_owner.USAGE
        assert row["lifecycle"]["outcome"] == "completed" and row["lifecycle"]["usage_sent"]
        assert response["model"] == P.OFFICE_SERVICE_MODEL and response["max_output_tokens"] is None
        assert [item["type"] for item in response["output"]] == ["message"]
        results.append(response)
        return http_owner.native_parsers()["convert_responses_result"](copy.deepcopy(response))
    def checked_send(wire):
        try: return send(wire)
        except BaseException as error:
            results.append(error); raise
    result, wires, ns = native_service_request(native, checked_send)
    if results and isinstance(results[-1], BaseException): raise results[-1]
    assert len(wires) == len(results) == len(boundary.rows()) == 1
    wire = wires[0]
    assert set(wire) == {"model", "input", "stream", "reasoning"}
    assert wire["reasoning"] == {"effort": "none"} and wire["stream"] is False
    prompt = wire["input"][0]["content"][0]["text"]
    prefix = ns["DEFAULT_FOLLOW_UP_GENERATION_PROMPT_TEMPLATE"].partition("{{MESSAGES:END:5}}")[0]
    assert prompt.startswith(prefix)
    assert "ASSISTANT: " + component_owner.P.SOURCE in prompt
    assert "USER: " + component_owner.P.USER_REQUEST in prompt
    assert prompt.endswith("ASSISTANT: [Download](/api/v1/files/finite-office-id/content)\n</chat_history>")
    suggestions = ns["parse_follow_ups"](result["choices"][0]["message"]["content"])
    assert suggestions == ["Prepare a PDF copy of the document.", "Create an Excel version of the table.",
        "Draft a short email to accompany the file."]


def test_office_service_rejects_foreign_shape_and_damaged_task_context(boundary, native):
    _, wires, _ = native_service_request(native)
    wire = wires[0]
    candidates = []
    def change(mutate):
        body = copy.deepcopy(wire); mutate(body); candidates.append(body)
    for key, value in (("stream", True), ("reasoning", {"effort": "low"}), ("reasoning", {}),
            ("tools", []), ("instructions", "foreign policy"), ("max_output_tokens", 16),
            ("store", False), ("previous_response_id", "foreign"), ("reasoning_effort", "none")):
        change(lambda body, k=key, v=value: body.__setitem__(k, v))
    change(lambda b: b["input"].append(copy.deepcopy(b["input"][0])))
    change(lambda b: b["input"][0].__setitem__("role", "developer"))
    change(lambda b: b["input"][0]["content"][0].__setitem__("text", "Generate follow-ups"))
    text = wire["input"][0]["content"][0]["text"]
    for damaged in (text.replace("Never invent user facts", "Invent user facts"),
            text.replace("\nASSISTANT: ", "\nOTHER: "), text[:-1]):
        change(lambda b, t=damaged: b["input"][0]["content"][0].__setitem__("text", t))
    for index, candidate in enumerate(candidates):
        assert boundary.http("/v1/responses", candidate)[0] == 400, index
    assert boundary.rows() == []
    foreign = copy.deepcopy(wire); foreign["model"] = "foreign-office-service"
    assert boundary.http("/v1/responses", foreign)[0] == 404


def test_service_preserves_native_history_selection_and_failure_lifecycle(boundary, native):
    history = [{"role": "user", "content": "FIRST USER"}, {"role": "assistant", "content": "DROPPED"},
        {"role": "user", "content": "RECENT USER"}, {"role": "assistant", "content": "START" + "x" * 2000 + "END"},
        {"role": "user", "content": component_owner.P.USER_REQUEST}, {"role": "assistant", "content": "COMPLETE"}]
    original = copy.deepcopy(history)
    _, wires, _ = native_service_request(native, messages=history)
    assert history == original
    text = wires[0]["input"][0]["content"][0]["text"]
    assert "USER: FIRST USER" in text and "DROPPED" not in text and "USER: RECENT USER" in text
    assert "START" in text and "END" in text and "x" * 1000 not in text
    assert boundary.http("/__proof/control", {"response_status": 500})[0] == 200
    status, response = boundary.http("/v1/responses", wires[0])
    assert status == 500 and response["error"]["code"] == "proof_provider_500"
    row = boundary.rows()[0]; row = boundary.terminal(row["id"])
    assert row["body"] == wires[0] and row["usage"] is None
    assert row["lifecycle"]["outcome"] == "controlled_error" and row["lifecycle"]["usage_sent"] is False


def test_removing_only_office_branch_reproduces_original_provider_ast():
    original = subprocess.check_output(["git", "-c", "gc.auto=0", "show", BASE + ":scripts/goal584-budget-proof/mock_provider.py"],
        cwd=ROOT, env=os.environ | {"GIT_NO_LAZY_FETCH": "1"})
    assert hashlib.sha256(original).hexdigest() == BASE_SHA256
    current = ast.parse(Path(P.__file__).read_bytes())
    class RemoveOffice(ast.NodeTransformer):
        def visit_Assign(self, node):
            if any(isinstance(t, ast.Name) and t.id in {"OFFICE_MODEL", "OFFICE_SERVICE_MODEL", "office", "office_service"} for t in node.targets):return None
            if (any(isinstance(t, ast.Name) and t.id == "selection" for t in node.targets)
                    and isinstance(node.value, ast.IfExp) and isinstance(node.value.test, ast.Name)
                    and node.value.test.id == "office"):return None
            return self.generic_visit(node)
        def visit_FunctionDef(self, node):
            return None if node.name in {"office_responses_input", "office_responses_step", "office_service_responses_input"} else self.generic_visit(node)
        def visit_IfExp(self, node):
            return self.visit(node.orelse) if isinstance(node.test, ast.Name) and node.test.id in {"office", "office_service"} else self.generic_visit(node)
        def visit_BoolOp(self, node):
            node = self.generic_visit(node)
            node.values = [v for v in node.values if not (isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not)
                and isinstance(v.operand, ast.Name) and v.operand.id in {"office", "office_service"})]
            return node.values[0] if len(node.values) == 1 else node
    assert ast.dump(RemoveOffice().visit(current), include_attributes=False) == ast.dump(ast.parse(original), include_attributes=False)
