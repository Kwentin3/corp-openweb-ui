"""Component/ASGI contracts; native owners are fakes, not runtime acceptance."""
from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import importlib.util
import io
import json
import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI
from pypdf import PdfWriter
from pydantic import BaseModel, ConfigDict
from starlette.routing import Mount
from starlette.responses import PlainTextResponse


SOURCE = Path(__file__).parents[1] / "luna_pdf_ocr.py"
SPEC = importlib.util.spec_from_file_location("luna_pdf_ocr", SOURCE)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def pdf_bytes(pages=2):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def extracted_pages():
    return {"complete": True, "pages": [
        {"page_number": 1, "text": "Clause 1: amount 10.00; do not change.", "uncertain": []},
        {"page_number": 2, "text": "Table: A | 200; B | 300.", "uncertain": []},
    ]}


def model_response(value=None):
    return {
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(value or extracted_pages())}}],
        "usage": {"input_tokens": 123, "output_tokens": 45, "total_tokens": 168},
    }


def raw_response(value=None):
    return {"status": "completed", "output": [
        {"type": "message", "role": "assistant", "status": "completed", "content": [
            {"type": "output_text", "text": json.dumps(value or extracted_pages())}]}],
        "usage": {"input_tokens": 123, "output_tokens": 45, "total_tokens": 168}}


def nodes(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from nodes(item)


def test_final_request_retains_actual_pdf_ocr_instructions_and_strict_schema():
    original = pdf_bytes()
    request = MODULE.build_ocr_request(original, "scan.pdf", 2)
    assert request["model"] == "gpt-6-luna"
    serialized = json.dumps(request)
    assert base64.b64encode(original).decode() in serialized
    assert "scan.pdf" in serialized
    # Inspect the real emitted schema, not just a page/token count.
    schema = next(n for n in nodes(request) if n.get("type") == "object" and "pages" in n.get("properties", {}))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"pages", "complete"}
    item = schema["properties"]["pages"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == {"page_number", "text", "uncertain"}
    instruction_text = " ".join(n.get("text", n.get("content", "")) for n in nodes(request)
                                if isinstance(n.get("text", n.get("content", "")), str))
    instruction_text = " ".join(instruction_text.split())
    assert "Transcribe" in instruction_text
    assert "untrusted" in instruction_text
    assert "negations" in instruction_text
    assert "page" in instruction_text.lower()
    assert "table" in instruction_text.lower()
    assert "one column per leaf column" in instruction_text
    assert "Every table row must have the same column count" in instruction_text
    assert "preserve empty cells" in instruction_text
    assert "2" in instruction_text
    assert any(n.get("type") in {"file", "input_file"} for n in nodes(request))
    assert request["text"]["format"]["strict"] is True
    assert request["stream"] is False
    assert request["store"] is False
    assert len(request["messages"]) == 2
    actual = request["messages"][1]["content"][1]["file"]["file_data"]
    assert base64.b64decode(actual.split(",", 1)[1]) == original


def test_complete_response_preserves_page_text_and_safe_usage():
    pages, usage = MODULE.decode_ocr_response(model_response(), 2)
    assert pages == extracted_pages()["pages"]
    assert usage["input_tokens"] == 123
    assert usage["output_tokens"] == 45
    assert usage["total_tokens"] == 168


def test_native_raw_completed_response_preserves_pages_and_usage():
    pages, usage = MODULE.decode_ocr_response(raw_response(), 2)
    assert pages == extracted_pages()["pages"]
    assert usage == {"input_tokens": 123, "output_tokens": 45, "total_tokens": 168}


@pytest.mark.parametrize("defect", ["incomplete", "message_incomplete", "refusal", "missing_status", "tool_output", "multiple_messages"])
def test_raw_native_status_cannot_be_hidden_by_complete_valid_page_json(defect):
    response = raw_response()
    if defect == "incomplete":
        response["status"] = "incomplete"
        response["incomplete_details"] = {"reason": "max_output_tokens"}
    elif defect == "message_incomplete":
        response["output"][0]["status"] = "incomplete"
    elif defect == "refusal":
        response["output"][0]["content"].append({"type": "refusal", "refusal": "Cannot extract."})
    elif defect == "missing_status":
        del response["status"]
    elif defect == "tool_output":
        response["output"].append({"type": "web_search_call", "status": "completed"})
    elif defect == "multiple_messages":
        response["output"].append(copy.deepcopy(response["output"][0]))
    with pytest.raises(ValueError):
        MODULE.decode_ocr_response(response, 2)


@pytest.mark.parametrize("defect", ["incomplete", "failed", "refusal", "truncated", "invalid_json", "missing_page", "duplicate_page", "reordered_page", "blank_page", "unreadable_page", "incomplete_document", "boolean_page", "extra_field", "tool_call", "raw_refusal"])
def test_incomplete_or_unusable_output_is_rejected(defect):
    value = extracted_pages()
    response = model_response(value)
    if defect in {"incomplete", "failed"}:
        response["status"] = defect
        response["incomplete_details"] = {"reason": "max_output_tokens"}
    elif defect == "refusal":
        response["choices"][0]["message"]["refusal"] = "Cannot extract."
    elif defect == "truncated":
        response["choices"][0]["finish_reason"] = "length"
    elif defect == "tool_call":
        response["choices"][0]["message"]["tool_calls"] = [{"id": "unexpected"}]
    elif defect == "raw_refusal":
        response["output"] = [{"type": "message", "content": [{"type": "refusal", "refusal": "Cannot extract."}]}]
    elif defect == "invalid_json":
        response["choices"][0]["message"]["content"] = '{"pages": ['
    else:
        if defect == "missing_page":
            value["pages"].pop()
        elif defect == "duplicate_page":
            value["pages"][1]["page_number"] = 1
        elif defect == "reordered_page":
            value["pages"].reverse()
        elif defect == "blank_page":
            value["pages"][1]["text"] = " \n\t"
        elif defect == "unreadable_page":
            value["pages"][1]["text"] = "[unreadable]"
        elif defect == "incomplete_document":
            value["complete"] = False
        elif defect == "boolean_page":
            value["pages"][0]["page_number"] = True
        elif defect == "extra_field":
            value["pages"][0]["summary"] = "unexpected"
        response = model_response(value)
    with pytest.raises(ValueError):
        MODULE.decode_ocr_response(response, 2)


@pytest.mark.parametrize("api_type,format_key", [("responses", "text"), ("chat_completions", "response_format")])
def test_request_uses_selected_native_api_schema_contract(api_type, format_key):
    request = MODULE.build_ocr_request(pdf_bytes(), "scan.pdf", 2, api_type=api_type)
    assert format_key in request
    assert request["max_completion_tokens"] == 64000
    assert request["metadata"] == {"task": "document_ocr"}
    assert "tools" not in request


@pytest.fixture
def native(monkeypatch, tmp_path):
    """Fake only separately owned native APIs; run actual adapter and ASGI route."""
    def module(name, **attributes):
        for index in range(1, len(name.split("."))):
            parent = ".".join(name.split(".")[:index])
            if parent not in sys.modules:
                package = types.ModuleType(parent)
                package.__path__ = []
                monkeypatch.setitem(sys.modules, parent, package)
        result = types.ModuleType(name)
        result.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, result)

    original = pdf_bytes()
    path = tmp_path / "native-file.pdf"
    path.write_bytes(original)
    user = SimpleNamespace(id="owner", role="user")
    file = SimpleNamespace(id="file-1", user_id=user.id, path=str(path), filename="source.pdf",
                           hash="extracted-text-hash-is-not-the-upload-hash",
                           meta={"content_type": "application/pdf", "file_hash": hashlib.sha256(original).hexdigest()})
    config_values = {"rag.content_extraction_engine": "external", "rag.pdf_extract_images": False,
                     "rag.file.max_size": 20, "rag.pdf_loader_mode": "page"}
    config = SimpleNamespace(get=AsyncMock(return_value="loader-secret"), get_many=AsyncMock(return_value=config_values))
    files = SimpleNamespace(get_file_by_id=AsyncMock(return_value=file))
    users = SimpleNamespace(get_user_by_id=AsyncMock(return_value=user))
    active = SimpleNamespace(id="ocr-function", type="event", is_active=True)
    functions = SimpleNamespace(get_function_by_id=AsyncMock(return_value=active), get_function_valves_by_id=AsyncMock(return_value={}))
    event = MODULE.Event()
    cached = AsyncMock(return_value=(event, None, None))
    provider = AsyncMock(return_value=raw_response())
    completion_provider = AsyncMock(return_value=model_response())
    # Native conversion is a separately owned boundary, audited against installed
    # source outside this portable suite. Assert its exact input and forwarded
    # output without reimplementing that converter in the test.
    projected = {"model": "gpt-6-luna", "input": [{"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": "native converter output sentinel"}]}], "store": False}
    converter = Mock(return_value=projected)

    class ResponsesForm(BaseModel):
        model_config = ConfigDict(extra="allow")
        model: str
        input: list
    access = AsyncMock(return_value=False)
    storage = SimpleNamespace(get_file=Mock(side_effect=lambda value: value))
    loader = SimpleNamespace(aload=AsyncMock(return_value=[SimpleNamespace(page_content="Native DOCX text", metadata={"native": "kept"})]))
    build_loader = Mock(return_value=loader)
    connection = AsyncMock(return_value=("unused-url", "unused-native-key", {"api_type": "responses", "auth_type": "bearer"}))
    module("open_webui.models.config", Config=config)
    module("open_webui.models.files", Files=files)
    module("open_webui.models.users", Users=users)
    module("open_webui.models.functions", Functions=functions)
    module("open_webui.models.models", Models=SimpleNamespace(get_model_by_id=AsyncMock(return_value=None)))
    module("open_webui.storage.provider", Storage=storage)
    module("open_webui.utils.access_control.files", has_access_to_file=access)
    module("open_webui.utils.plugin", get_function_module_from_cache=cached)
    module("open_webui.utils.chat", generate_chat_completion=completion_provider)
    module("open_webui.utils.models", get_all_models=AsyncMock())
    module("open_webui.routers.openai", get_openai_connection=connection, ResponsesForm=ResponsesForm,
           convert_to_responses_payload=converter, responses=provider)
    module("open_webui.retrieval.utils", build_loader_from_config=build_loader)
    module("open_webui.routers.retrieval", RETRIEVAL_CONFIG_KEYS={str(index): key for index, key in enumerate(config_values)})
    app = FastAPI()

    @app.middleware("http")
    async def parent_context(request, call_next):
        request.state.metadata = {"chat_id": "parent-chat", "tools": ["unexpected"]}
        request.state.bypass_filter = True
        return await call_next(request)

    app.state.MODELS = {"gpt-6-luna": {"owned_by": "openai", "info": {"meta": {"capabilities": {"vision": True}}}}}
    app.state.OPENAI_MODELS = {"gpt-6-luna": {"urlIdx": 0}}

    async def spa(scope, receive, send):
        await PlainTextResponse("SPA catch-all", status_code=404)(scope, receive, send)
    app.mount("/", spa, name="spa-static-files")
    asyncio.run(event.event({}, __event_name__="system.startup.completed", __id__=active.id, __app__=app))

    async def request(body=None, headers=None):
        defaults = {"Authorization": "Bearer loader-secret", "X-OCR-File-Id": file.id, "X-OCR-User-Id": user.id}
        defaults.update(headers or {})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://adapter") as client:
            return await client.put(MODULE.ROUTE_PATH + "?parent_chat=private", content=original if body is None else body, headers=defaults)
    return SimpleNamespace(app=app, event=event, request=request, original=original, file=file, user=user,
                           config=config, config_values=config_values, functions=functions, active=active,
                           cached=cached, provider=provider, access=access, storage=storage, files=files,
                           users=users, loader=loader, build_loader=build_loader, connection=connection,
                           converter=converter, projected=projected, completion_provider=completion_provider)


def test_pdf_route_returns_native_documents_and_exact_isolated_provider_request(native):
    response = asyncio.run(native.request())
    assert response.status_code == 200, response.text
    docs = response.json()
    assert [doc["page_content"] for doc in docs] == [page["text"] for page in extracted_pages()["pages"]]
    assert [doc["metadata"]["page"] for doc in docs] == [0, 1]
    assert all(doc["metadata"]["ocr_model"] == "gpt-6-luna" for doc in docs)
    args = native.provider.await_args
    nested_request, form = args.args
    assert args.kwargs == {"user": native.user}
    assert nested_request.scope["state"] == {}
    assert nested_request.scope["headers"] == []
    assert nested_request.scope["query_string"] == b""
    expected = MODULE.build_ocr_request(native.original, native.file.filename, 2)
    expected["metadata"]["file_id"] = native.file.id
    native.converter.assert_called_once_with(expected)
    assert form.model_dump(exclude_none=True) == native.projected
    native.completion_provider.assert_not_awaited()
    assert native.file.path and Path(native.file.path).read_bytes() == native.original
    native.build_loader.assert_not_called()


@pytest.mark.parametrize("defect,status", [("wrong_key", 401), ("unknown_user", 403), ("pending_user", 403), ("denied_acl", 403), ("different_bytes", 409)])
def test_security_and_original_byte_binding_fail_before_provider(native, defect, status):
    headers = {}
    body = None
    if defect == "wrong_key":
        headers["Authorization"] = "Bearer incorrect"
    elif defect == "unknown_user":
        native.users.get_user_by_id.return_value = None
    elif defect == "pending_user":
        native.user.role = "pending"
    elif defect == "denied_acl":
        native.file.user_id = "another-owner"
    elif defect == "different_bytes":
        body = native.original + b"changed"
    response = asyncio.run(native.request(body=body, headers=headers))
    assert response.status_code == status
    native.provider.assert_not_awaited()
    native.completion_provider.assert_not_awaited()
    native.build_loader.assert_not_called()


def test_native_shared_file_write_access_is_preserved(native):
    native.file.user_id = "another-owner"
    native.access.return_value = True
    response = asyncio.run(native.request())
    assert response.status_code == 200, response.text
    native.access.assert_awaited_once_with(native.file.id, "write", native.user)


def test_nonpdf_uses_native_loader_and_only_request_local_config(native):
    native.file.filename = "source.docx"
    native.file.meta["content_type"] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    before = copy.deepcopy(native.config_values)
    response = asyncio.run(native.request())
    assert response.status_code == 200, response.text
    assert response.json() == [{"page_content": "Native DOCX text", "metadata": {"native": "kept"}}]
    passed = native.build_loader.call_args.args[0]
    assert passed is not native.config_values
    assert passed == {**before, "rag.content_extraction_engine": ""}
    assert native.config_values == before
    assert native.loader.user is native.user
    assert native.loader.metadata == {"file_id": native.file.id, "file_name": "source.docx", "file_content_type": native.file.meta["content_type"]}
    native.loader.aload.assert_awaited_once_with(native.file.filename, native.file.meta["content_type"], native.file.path)
    native.provider.assert_not_awaited()


def test_event_routes_before_spa_and_idempotent_across_startup_and_enable(native):
    async def repeat():
        for name in ["system.startup.completed", "function.enable_started"]:
            await native.event.event({"subject": {"type": "function", "id": native.active.id}},
                                     __event_name__=name, __id__=native.active.id, __app__=native.app)
    asyncio.run(repeat())
    routes = native.app.router.routes
    owned = [route for route in routes if getattr(route, "path", None) == MODULE.ROUTE_PATH]
    assert len(owned) == 1
    assert routes.index(owned[0]) < next(index for index, route in enumerate(routes) if isinstance(route, Mount) and route.path == "")
    assert asyncio.run(native.request()).status_code == 200


def test_disable_removes_only_own_route_and_reenable_restores_it(native):
    async def lifecycle(name, subject_id):
        await native.event.event({"subject": {"type": "function", "id": subject_id}},
                                 __event_name__=name, __id__=native.active.id, __app__=native.app)
    asyncio.run(lifecycle("function.disable_started", "unrelated"))
    assert asyncio.run(native.request()).status_code == 200
    asyncio.run(lifecycle("function.disable_started", native.active.id))
    response = asyncio.run(native.request())
    assert response.status_code == 404 and response.text == "SPA catch-all"
    asyncio.run(lifecycle("function.enable_started", native.active.id))
    assert asyncio.run(native.request()).status_code == 200


@pytest.mark.parametrize("deleted", [False, True])
def test_inactive_or_deleted_function_fails_closed_before_provider(native, deleted):
    if deleted:
        native.functions.get_function_by_id.return_value = None
    else:
        native.active.is_active = False
    response = asyncio.run(native.request())
    assert response.status_code == 503
    native.cached.assert_not_awaited()
    native.provider.assert_not_awaited()


def test_route_uses_current_native_cached_module_after_source_edit(native):
    # The registered endpoint resolves the current module instead of a stale bound handler.
    replacement = SimpleNamespace(Valves=MODULE.Event.Valves, _handle=AsyncMock(return_value=[{"page_content": "new module", "metadata": {}}]))
    native.cached.return_value = (replacement, None, None)
    response = asyncio.run(native.request())
    assert response.status_code == 200
    assert response.json() == [{"page_content": "new module", "metadata": {}}]
    native.provider.assert_not_awaited()


def test_provider_partial_output_surfaces_failure_without_raw_content(native):
    native.provider.return_value = raw_response({"complete": False, "pages": []})
    response = asyncio.run(native.request())
    assert response.status_code == 502
    assert response.json() == {"detail": "PDF OCR failed or returned incomplete content"}


def test_raw_incomplete_with_valid_complete_json_fails_through_actual_adapter_route(native):
    native.provider.return_value = raw_response()
    native.provider.return_value["status"] = "incomplete"
    native.provider.return_value["incomplete_details"] = {"reason": "max_output_tokens"}
    response = asyncio.run(native.request())
    assert response.status_code == 502
    assert response.json() == {"detail": "PDF OCR failed or returned incomplete content"}
    native.completion_provider.assert_not_awaited()


def test_responses_owner_must_not_return_a_lossy_chat_completion_projection(native):
    native.provider.return_value = {**model_response(), "status": "completed"}
    response = asyncio.run(native.request())
    assert response.status_code == 502
    assert response.json() == {"detail": "PDF OCR failed or returned incomplete content"}
    native.completion_provider.assert_not_awaited()


def test_uncertainty_is_visible_in_native_page_text_and_preserves_source_text(native):
    value = extracted_pages()
    value["pages"][0]["text"] = "Source clause [unreadable] remains literal."
    value["pages"][0]["uncertain"] = ["Page 1, clause 2: amount unclear."]
    native.provider.return_value = raw_response(value)
    response = asyncio.run(native.request())
    assert response.status_code == 200, response.text
    docs = response.json()
    assert docs[0]["page_content"] == (value["pages"][0]["text"] +
        "\n\n[OCR uncertainty, page 1]\nPage 1, clause 2: amount unclear.")
    assert docs[0]["metadata"]["ocr_uncertain"] == value["pages"][0]["uncertain"]
    assert docs[1]["page_content"] == value["pages"][1]["text"]


def test_chat_completions_connection_keeps_native_completion_owner(native):
    native.connection.return_value = ("unused", "unused", {"auth_type": "bearer", "api_type": "chat_completions"})
    response = asyncio.run(native.request())
    assert response.status_code == 200, response.text
    assert [d["page_content"] for d in response.json()] == [p["text"] for p in extracted_pages()["pages"]]
    args = native.completion_provider.await_args
    assert args.args[2] is native.user
    expected = MODULE.build_ocr_request(native.original, native.file.filename, 2, api_type="chat_completions")
    expected["metadata"]["file_id"] = native.file.id
    assert args.args[1] == expected
    assert args.kwargs == {"bypass_filter": False, "bypass_system_prompt": True}
    native.provider.assert_not_awaited()
    native.converter.assert_not_called()


@pytest.mark.parametrize("defect", ["vision_disabled", "wrong_owner", "pipe", "pipeline", "session_auth", "forward_cookies"])
def test_incompatible_model_connection_fails_before_provider(native, defect):
    model = native.app.state.MODELS["gpt-6-luna"]
    if defect == "vision_disabled":
        model["info"]["meta"]["capabilities"]["vision"] = False
    elif defect == "wrong_owner":
        model["owned_by"] = "ollama"
    elif defect in {"pipe", "pipeline"}:
        model[defect] = {"id": "another-handler"}
    elif defect == "session_auth":
        native.connection.return_value = ("unused", "unused", {"auth_type": "session"})
    elif defect == "forward_cookies":
        native.connection.return_value = ("unused", "unused", {"forward_cookies": True})
    response = asyncio.run(native.request())
    assert response.status_code == 503, response.text
    native.provider.assert_not_awaited()


def test_concurrent_request_is_rejected_and_completed_request_releases_admission(native):
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()

        async def provider(*args, **kwargs):
            entered.set()
            await release.wait()
            return raw_response()

        native.provider.side_effect = provider
        first = asyncio.create_task(native.request())
        try:
            async with asyncio.timeout(2):
                await entered.wait()
            second = await native.request()
            assert second.status_code == 429
        finally:
            release.set()
        assert (await first).status_code == 200
        native.provider.side_effect = None
        assert (await native.request()).status_code == 200
        assert native.app.state._luna_pdf_ocr_active[native.active.id] == 0
    asyncio.run(scenario())


def test_timeout_retains_admission_until_native_thread_worker_actually_finishes(native):
    # Cancelling asyncio.to_thread cannot terminate its underlying native worker.
    entered = threading.Event()
    release = threading.Event()

    def storage(path):
        entered.set()
        if not release.wait(5):
            raise RuntimeError("Test did not release native Storage worker")
        return path

    native.storage.get_file.side_effect = storage
    native.functions.get_function_valves_by_id.return_value = {"timeout_seconds": 1}

    async def scenario():
        first = asyncio.create_task(native.request())
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            response = await first
            assert response.status_code == 504
            assert (await native.request()).status_code == 429
        finally:
            release.set()
        async with asyncio.timeout(2):
            while True:
                recovered = await native.request()
                if recovered.status_code != 429:
                    break
                await asyncio.sleep(0)
        assert recovered.status_code == 200, recovered.text
        native.provider.assert_awaited_once()
    asyncio.run(scenario())
