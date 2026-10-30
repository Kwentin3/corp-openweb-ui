"""HTTP seam checks; native OpenWebUI ACL/runtime acceptance is a separate gate."""

import asyncio
from contextlib import asynccontextmanager
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from aiohttp import web
import pytest


spec = importlib.util.spec_from_file_location(
    "corporate_templates", Path(__file__).parents[3] / "deploy/openwebui-tools/corporate_templates.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

META = {"chat_id": "chat", "message_id": "answer"}
REQUEST = SimpleNamespace(state=SimpleNamespace(token=SimpleNamespace(credentials="author-token")))
READ = {"principal_type": "group", "principal_id": "employees", "permission": "read"}
WRITE = {**READ, "permission": "write"}
KB = "/api/v1/knowledge/library"
SKILL = "/api/v1/skills/id/report-template"


@asynccontextmanager
async def owners():
    state = {
        "skill": {"id": "report-template", "name": "Report template", "description": "Agreed instructions",
                  "content": "Fill the agreed fields and preserve the layout.", "meta": {"description": "Keep me"},
                  "is_active": True, "write_access": True, "version_id": "version-1", "access_grants": []},
        "knowledge": {"id": "library", "write_access": True,
                      "access_grants": [{"id": "grant-read", **READ}, {"id": "grant-write", **WRITE}]},
        "source": {"id": "original", "filename": "agreed.docx", "path": "native-storage/original.docx", "data": {}},
        "original_bytes": b"original bytes never pass through this publication adapter",
        "files": [{"path": "SKILL.md", "encoding": None, "size": 51}],
        "linked": False, "requests": [], "writes": [], "strip_grants": False,
        "process_status": 200, "update_status": 200, "deny_file": False,
        "hide_membership_after_update": False, "grant_drift_after_update": False,
        "extra_binary_after_update": False, "page_size": 30, "collisions": 0,
        "summary_version": None,
    }

    async def route(request):
        assert request.headers.get("Authorization") == "Bearer author-token"
        state["requests"].append((request.method, request.path))
        if request.method == "POST":
            state["writes"].append((request.path, await request.json()))
        if request.path == KB:
            return web.json_response(state["knowledge"])
        if request.path == SKILL:
            return web.json_response(state["skill"])
        if request.path == SKILL + "/files":
            return web.json_response({"version_id": state["summary_version"] or state["skill"]["version_id"],
                                      "files": state["files"]})
        if request.path == "/api/v1/files/original":
            return web.Response(status=403) if state["deny_file"] else web.json_response(state["source"])
        if request.path == KB + "/files":
            # Match the pinned native route: query means filename, never ID.
            assert request.query["query"] == state["source"]["filename"]
            entries = [{"id": f"different-{i}", "filename": "agreed.docx"} for i in range(state["collisions"])]
            if state["linked"]:
                entries.append({"id": "original", "filename": "agreed.docx"})
            offset = (int(request.query["page"]) - 1) * state["page_size"]
            return web.json_response({"items": entries[offset:offset + state["page_size"]], "total": len(entries)})
        if request.path == "/api/v1/retrieval/process/file":
            assert state["writes"][-1][1] == {"file_id": "original"}
            if state["process_status"] != 200:
                return web.Response(status=state["process_status"])
            state["source"]["data"] = {"content": "Native extraction of saved original"}
            return web.json_response({"status": True})
        if request.path == KB + "/file/add":
            assert state["writes"][-1][1] == {"file_id": "original"}
            assert state["source"]["data"].get("content") is not None
            state["linked"] = True
            return web.json_response({**state["knowledge"], "files": [{"id": "original"}]})
        if request.path == SKILL + "/update":
            data = state["writes"][-1][1]
            assert data["expected_version_id"] == "version-1"
            assert data["access_grants"] == [READ]
            assert "files" not in data and "data" not in data
            if state["update_status"] != 200:
                return web.Response(status=state["update_status"])
            state["skill"].update({**data, "version_id": "version-2"})
            # Native grant readback contains generated IDs/resource metadata.
            state["skill"]["access_grants"] = [] if state["strip_grants"] else [{"id": "saved-grant", **READ}]
            if state["hide_membership_after_update"]:
                state["linked"] = False
            if state["grant_drift_after_update"]:
                state["knowledge"]["access_grants"] = []
            if state["extra_binary_after_update"]:
                state["files"].append({"path": "original.docx", "encoding": "base64", "size": 50})
            return web.json_response(state["skill"])
        return web.Response(status=404)

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", route)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    tool = module.Tools()
    tool.valves.openwebui_base_url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
    tool.valves.knowledge_id = "library"
    try:
        yield tool, state
    finally:
        await runner.cleanup()


def test_publication_links_same_original_and_saves_only_instructions_and_native_read_grants():
    async def run():
        async with owners() as (tool, state):
            original = copy.deepcopy(state["source"])
            binary = state["original_bytes"]
            receipt = await tool.publish_template("report-template", "original", REQUEST, META)
            assert receipt["status"] == "published", receipt
            assert receipt["source_file_id"] == "original"
            assert receipt["access_grants"] == [READ]
            assert receipt["download_url"] == "/api/v1/files/original/content"
            assert state["linked"]
            assert state["source"]["id"] == original["id"] and state["source"]["path"] == original["path"]
            assert state["original_bytes"] == binary
            assert state["skill"]["content"].startswith("Fill the agreed fields")
            assert "Original native File ID: `original`" in state["skill"]["content"]
            assert state["skill"]["meta"] == {"description": "Keep me"}
            assert [path for path, _ in state["writes"]] == [
                "/api/v1/retrieval/process/file", KB + "/file/add", SKILL + "/update",
            ]
            assert state["files"] == [{"path": "SKILL.md", "encoding": None, "size": 51}]
            before = len(state["writes"])
            repeated = await tool.publish_template("report-template", "original", REQUEST, META)
            assert repeated["status"] == "published", repeated
            assert len(state["writes"]) == before
    asyncio.run(run())


@pytest.mark.parametrize("change", ["no_knowledge_write", "no_skill_write", "binary_skill", "stale_summary",
                                          "foreign_file", "missing_original", "not_docx", "different_reference"])
def test_native_preflight_failures_do_not_mutate_any_owner(change):
    async def run():
        async with owners() as (tool, state):
            if change == "no_knowledge_write":
                state["knowledge"]["write_access"] = False
            elif change == "no_skill_write":
                state["skill"]["write_access"] = False
            elif change == "binary_skill":
                state["files"].append({"path": "original.docx", "encoding": "base64"})
            elif change == "stale_summary":
                # A second GET observes a different version from detail.
                state["summary_version"] = "version-2"
            elif change == "foreign_file":
                state["deny_file"] = True
            elif change == "missing_original":
                state["source"]["path"] = None
            elif change == "not_docx":
                state["source"]["filename"] = "template.pdf"
            elif change == "different_reference":
                state["skill"]["content"] += "\n## Original template\nOther source"
            receipt = await tool.publish_template("report-template", "original", REQUEST, META)
            assert receipt["status"] == "blocked", receipt
            assert state["writes"] == [] and not state["linked"]
    asyncio.run(run())


@pytest.mark.parametrize("change, step", [
    ("process_status", "process_file"), ("update_status", "update_skill"),
    ("strip_grants", "readback"), ("hide_membership_after_update", "readback"),
    ("grant_drift_after_update", "readback"), ("extra_binary_after_update", "readback"),
])
def test_failures_after_mutation_are_explicit_partial_results_without_write_retry(change, step):
    async def run():
        async with owners() as (tool, state):
            state[change] = 503 if change == "process_status" else 409 if change == "update_status" else True
            receipt = await tool.publish_template("report-template", "original", REQUEST, META)
            assert receipt["status"] == "partial", receipt
            assert receipt["attempted_step"] == step
            assert receipt["error"] and "Inspect native" in receipt["next_action"]
            paths = [path for path, _ in state["writes"]]
            assert len(paths) == len(set(paths)), "mutations must not be retried automatically"
            if step == "process_file":
                assert not state["linked"] and "link_original" not in receipt["completed_steps"]
            elif step == "update_skill":
                assert state["linked"] and state["skill"]["version_id"] == "version-1"
            assert "author-token" not in str(receipt)
    asyncio.run(run())


def test_membership_checks_exact_ids_across_filename_collision_pages():
    async def run():
        async with owners() as (tool, state):
            state.update(linked=True, collisions=3, page_size=2)
            state["source"]["data"] = {"content": "Already processed"}
            receipt = await tool.publish_template("report-template", "original", REQUEST, META)
            assert receipt["status"] == "published", receipt
            assert [path for path, _ in state["writes"]] == [SKILL + "/update"]
    asyncio.run(run())


@pytest.mark.parametrize("metadata,native_request", [(None, REQUEST), ({**META, "task": "title_generation"}, REQUEST), (META, None)])
def test_missing_native_context_or_auxiliary_task_never_contacts_owners(metadata, native_request):
    async def run():
        async with owners() as (tool, state):
            with pytest.raises(ValueError):
                await tool.publish_template("report-template", "original", native_request, metadata)
            assert state["requests"] == []
    asyncio.run(run())
