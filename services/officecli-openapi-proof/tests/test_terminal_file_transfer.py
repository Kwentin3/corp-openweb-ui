import asyncio
from contextlib import asynccontextmanager
import copy
import hashlib
import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from aiohttp import web
import pytest


spec = importlib.util.spec_from_file_location(
    "terminal_file_transfer",
    Path(__file__).parents[3] / "deploy" / "openwebui-tools" / "terminal_file_transfer.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

META = {"chat_id": "chat", "message_id": "answer", "terminal_id": "selected"}
REQUEST = SimpleNamespace(state=SimpleNamespace(token=SimpleNamespace(credentials="native-user-token")))


@asynccontextmanager
async def owners():
    state = {"source": b"source bytes", "terminal": {}, "published": {}, "events": [],
             "uploads": 0, "allow_terminal": True, "corrupt_download": False, "upload_status": 200,
             "transient_reads": {}, "requests": {}}

    async def route(request):
        assert request.headers.get("Authorization") == "Bearer native-user-token"
        assert request.headers.get("X-Session-Id") == "chat"
        path = request.path
        state["requests"][path] = state["requests"].get(path, 0) + 1
        if request.method == "GET" and state["transient_reads"].get(path, 0):
            state["transient_reads"][path] -= 1
            return web.Response(status=503)
        if path == "/api/v1/terminals/":
            return web.json_response([{"id": "selected"}] if state["allow_terminal"] else [])
        if path == "/api/v1/files/source":
            return web.json_response({"id": "source", "filename": "исходник.xlsx", "meta": {"content_type": "application/octet-stream"}})
        if path == "/api/v1/files/foreign":
            return web.Response(status=403)
        if path == "/api/v1/files/source/content":
            return web.Response(body=state["source"])
        if path == "/api/v1/terminals/selected/files/cwd":
            return web.json_response({"cwd": "/home/user"})
        if path == "/api/v1/terminals/selected/files/mkdir":
            return web.json_response(await request.json())
        if path in ("/api/v1/terminals/selected/files/upload", "/api/v1/files/"):
            state["uploads"] += 1
            if state["upload_status"] != 200:
                return web.Response(status=state["upload_status"])
            reader = await request.multipart()
            part = await reader.next()
            assert part.name == "file"
            data = bytes(await part.read())
            name = part.filename
            if "terminals" in path:
                file_path = request.query["directory"] + "/" + name
                assert file_path not in state["terminal"], "staging must not overwrite"
                state["terminal"][file_path] = data
                return web.json_response({"path": file_path, "size": len(data)})
            assert request.query["process"] == "false"
            fid = "result-" + str(state["uploads"])
            state["published"][fid] = data
            return web.json_response({"id": fid, "filename": name, "meta": {"size": len(data)}})
        if path == "/api/v1/terminals/selected/files/view":
            data = state["terminal"].get(request.query["path"])
            return web.Response(body=data, status=200 if data is not None else 404)
        if path.startswith("/api/v1/files/result-") and path.endswith("/content"):
            data = state["published"][path.split("/")[-2]]
            return web.Response(body=b"changed" if state["corrupt_download"] else data)
        return web.Response(status=404)

    app = web.Application(client_max_size=4 * 1024 * 1024)
    app.router.add_route("*", "/{path:.*}", route)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    tool = module.Tools()
    tool.valves.openwebui_base_url = f"http://127.0.0.1:{port}"

    async def emit(event):
        state["events"].append(copy.deepcopy(event))

    try:
        yield tool, state, emit
    finally:
        await runner.cleanup()


def test_native_multipart_staging_and_publication_preserve_sources_and_exact_bytes():
    async def run():
        async with owners() as (tool, state, emit):
            before = state["source"]
            first = await tool.stage_chat_file("source", REQUEST, META)
            second = await tool.stage_chat_file("source", REQUEST, META)
            assert first["path"] != second["path"]
            assert first["path"].endswith("/исходник.xlsx")
            assert first["sha256"] == hashlib.sha256(before).hexdigest()
            state["terminal"]["/home/user/result.xlsx"] = b"new artifact bytes"
            receipt = await tool.publish_terminal_file("/home/user/result.xlsx", REQUEST, META, emit)
            assert receipt["status"] == "published"
            assert state["source"] == before
            assert state["terminal"][first["path"]] == before
            assert state["terminal"]["/home/user/result.xlsx"] == b"new artifact bytes"
            assert state["published"][receipt["result_file_id"]] == b"new artifact bytes"
            assert [x["type"] for x in state["events"]] == ["files", "chat:message:files"]
            assert all(x["data"]["files"][0]["id"] == receipt["result_file_id"] for x in state["events"])
            assert receipt["download_url"] == f"/api/v1/files/{receipt['result_file_id']}/content"
    asyncio.run(run())


@pytest.mark.parametrize("metadata", [{}, {**META, "task": "title_generation"}, {**META, "terminal_id": ""}, {**META, "chat_id": "local:temporary"}])
def test_non_primary_or_missing_native_context_rejected_before_io(metadata):
    async def run():
        async with owners() as (tool, state, _):
            with pytest.raises(ValueError):
                await tool.stage_chat_file("source", REQUEST, metadata)
            assert state["uploads"] == 0
    asyncio.run(run())


@pytest.mark.parametrize("request_chat", ["chat", "foreign-chat"])
def test_096_captured_metadata_uses_original_native_selection_with_chat_binding(request_chat):
    async def run():
        async def body():
            return json.dumps({"chat_id": request_chat, "terminal_id": "selected"}).encode()
        request = SimpleNamespace(state=REQUEST.state, body=body)
        metadata = {k: v for k, v in META.items() if k != "terminal_id"}
        async with owners() as (tool, state, _):
            if request_chat != "chat":
                with pytest.raises(ValueError, match="chat identities differ"):
                    await tool.stage_chat_file("source", request, metadata)
                assert state["uploads"] == 0
            else:
                receipt = await tool.stage_chat_file("source", request, metadata)
                assert receipt["terminal_id"] == "selected"
                assert state["uploads"] == 1
    asyncio.run(run())


def test_native_file_denial_is_not_bypassed_or_uploaded():
    async def run():
        async with owners() as (tool, state, _):
            with pytest.raises(ValueError, match="403"):
                await tool.stage_chat_file("foreign", REQUEST, META)
            assert state["uploads"] == 0
            assert state["requests"]["/api/v1/files/foreign"] == 1
    asyncio.run(run())


def test_disabled_or_foreign_terminal_is_not_used():
    async def run():
        async with owners() as (tool, state, _):
            state["allow_terminal"] = False
            with pytest.raises(ValueError, match="not accessible"):
                await tool.stage_chat_file("source", REQUEST, META)
            assert state["uploads"] == 0
    asyncio.run(run())


def test_bound_stops_before_upload():
    async def run():
        async with owners() as (tool, state, _):
            tool.valves.max_file_mib = 1
            state["source"] = b"x" * (1024 * 1024 + 1)
            with pytest.raises(ValueError, match="transfer bound"):
                await tool.stage_chat_file("source", REQUEST, META)
            assert state["uploads"] == 0
    asyncio.run(run())


def test_failed_write_is_not_retried():
    async def run():
        async with owners() as (tool, state, emit):
            state["terminal"]["/home/user/result.docx"] = b"new file"
            state["upload_status"] = 502
            with pytest.raises(ValueError, match="no further automatic retry"):
                await tool.publish_terminal_file("/home/user/result.docx", REQUEST, META, emit)
            assert state["uploads"] == 1
            assert not state["events"]
    asyncio.run(run())


@pytest.mark.parametrize("route", ["/api/v1/files/source", "/api/v1/files/source/content"])
def test_one_transient_read_failure_recovers_before_a_single_write(route):
    async def run():
        async with owners() as (tool, state, _):
            state["transient_reads"][route] = 1
            result = await tool.stage_chat_file("source", REQUEST, META)
            assert state["terminal"][result["path"]] == state["source"]
            assert state["requests"][route] == 2
            assert state["uploads"] == 1
    asyncio.run(run())


def test_repeated_transient_failure_stops_after_one_retry_without_write():
    async def run():
        async with owners() as (tool, state, _):
            state["transient_reads"]["/api/v1/files/source/content"] = 3
            with pytest.raises(ValueError, match="503"):
                await tool.stage_chat_file("source", REQUEST, META)
            assert state["requests"]["/api/v1/files/source/content"] == 2
            assert state["uploads"] == 0
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["changed_bytes", "attachment_event"])
def test_post_upload_failure_retains_real_result_without_retry_or_false_completion(failure):
    async def run():
        async with owners() as (tool, state, emit):
            state["terminal"]["/home/user/result.pptx"] = b"real artifact"
            state["corrupt_download"] = failure == "changed_bytes"
            async def failing_emit(event):
                raise RuntimeError("event delivery interrupted")
            receipt = await tool.publish_terminal_file("/home/user/result.pptx", REQUEST, META,
                failing_emit if failure == "attachment_event" else emit)
            assert receipt["status"] != "published"
            assert receipt["result_file_id"] in state["published"]
            assert receipt["error"]
            assert state["uploads"] == 1
            assert not state["events"]
    asyncio.run(run())
