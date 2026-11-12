"""Native Tool adaptation: real monthly owner and real local HTTP cost reader.

Native user/chat storage and monthly service IO are fixture boundaries. These
checks do not establish tool activation, model selection or browser acceptance.
"""

import asyncio
import copy
import inspect
import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
from uuid import NAMESPACE_URL, uuid5

from aiohttp import ClientSession, web
import pytest

import test_cost_readback as cost_fixtures
from test_monthly_view import ACTOR, OTHER, KEY, BASE_URL, RESET, load, native


CHAT, ANSWER = (str(uuid5(NAMESPACE_URL, label)) for label in ("tool-chat", "tool-answer"))


@pytest.fixture
def tool(native, monkeypatch):
    load(monkeypatch, "employee_budget_provenance", "provenance.py")
    reader = load(monkeypatch, "employee_budget_cost_readback", "cost_readback.py")
    extension = load(monkeypatch, "user_tools_under_test", "user_tools.py")
    chats = SimpleNamespace(get_accessible_chat_by_id=AsyncMock(return_value=SimpleNamespace(user_id=ACTOR)))
    module = ModuleType("open_webui.models.chats")
    module.Chats = chats
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(sys.modules["open_webui.utils.auth"], "VERIFIED_USER_ROLES", {"user", "admin"}, raising=False)
    functions = sys.modules["open_webui.models.functions"].Functions
    functions.get_function_by_id.side_effect = lambda fid: (native.function if fid == extension.MONTHLY_ID
        else SimpleNamespace(type="filter", is_active=True))
    request = SimpleNamespace(state=SimpleNamespace(direct=False, internal=False))
    metadata = {"user_id": ACTOR, "chat_id": CHAT, "message_id": ANSWER}
    return SimpleNamespace(native=native, extension=extension, tools=extension.Tools(), reader=reader,
        chats=chats, request=request, metadata=metadata, functions=functions,
        args={"__request__": request, "__user__": {"id": ACTOR}, "__metadata__": metadata})


def test_monthly_tool_reuses_real_owner_and_projects_only_self_budget(tool):
    text = asyncio.run(tool.tools.my_budget(**tool.args))
    data = json.loads(text)
    assert (data["budget_usd"], data["spend_usd"], data["remaining_usd"]) == ("10", "3", "7")
    assert data["budget_duration"] == "1mo" and data["budget_reset_at"] == RESET
    assert data["expense_observation_scope"] == "native_budget_counters" and data["as_of"]
    assert data["models"][0]["model"] == "native-a" and data["models"][0]["spend_usd"] == "3"
    tool.native.read_service.assert_awaited_once_with(ACTOR)
    for private in (ACTOR, OTHER, KEY, BASE_URL, "@synthetic.invalid", "revision", "a" * 64, "private-native-key-alias"):
        assert private not in text
    for name in ("my_budget", "current_chat_cost"):
        parameters = inspect.signature(getattr(tool.tools, name)).parameters
        assert all(name.startswith("__") for name in parameters)


def test_missing_foreign_auxiliary_and_unverified_contexts_do_not_read(tool):
    for method in (tool.tools.my_budget, tool.tools.current_chat_cost):
        for changes in ({"__user__": None}, {"__metadata__": None},
                {"__metadata__": {**tool.metadata, "user_id": OTHER}},
                {"__metadata__": {**tool.metadata, "chat_id": "local:temporary"}},
                {"__metadata__": {**tool.metadata, "task": "title_generation"}},
                {"__metadata__": {**tool.metadata, "internal": True}}, {"__task__": "title_generation"}):
            assert json.loads(asyncio.run(method(**{**tool.args, **changes})))["status"] == "unavailable"
        tool.chats.get_accessible_chat_by_id.return_value = SimpleNamespace(user_id=OTHER)
        assert json.loads(asyncio.run(method(**tool.args)))["status"] == "unavailable"
        tool.chats.get_accessible_chat_by_id.return_value = SimpleNamespace(user_id=ACTOR)
        tool.native.users[ACTOR].role = "pending"
        assert json.loads(asyncio.run(method(**tool.args)))["status"] == "unavailable"
        tool.native.users[ACTOR].role = "user"
        tool.request.state.internal = True
        assert json.loads(asyncio.run(method(**tool.args)))["status"] == "unavailable"
        tool.request.state.internal = False
    tool.native.read_service.assert_not_awaited()
    tool.native.get_session.assert_not_awaited()


def test_monthly_revocation_and_inactive_owner_never_expose_snapshot(tool):
    async def revoke(uid):
        tool.native.users[ACTOR].role = "pending"
        return copy.deepcopy(tool.native.states[uid])
    tool.native.read_service.side_effect = revoke
    assert json.loads(asyncio.run(tool.tools.my_budget(**tool.args))) == {
        "status": "unavailable", "scope": "current_month", "spend_usd": None}
    tool.native.users[ACTOR].role = "user"
    tool.native.function.is_active = False
    tool.native.read_service.reset_mock()
    assert json.loads(asyncio.run(tool.tools.my_budget(**tool.args)))["status"] == "unavailable"
    tool.native.read_service.assert_not_awaited()


async def ledger(tool, exercise):
    """Existing real reader against one bounded local native GET surface."""
    requests, rows = [], []
    async def serve(request):
        requests.append((request.method, dict(request.query)))
        return web.json_response(cost_fixtures.page(rows))
    app = web.Application()
    app.router.add_get(tool.reader.SESSION_ROUTE, serve)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = "http://127.0.0.1:" + str(site._server.sockets[0].getsockname()[1])
        async with ClientSession() as session:
            tool.native.get_session.return_value = session
            tool.native.get_valves.return_value = {"ledger_base_url": base, "ledger_read_key": KEY}
            await exercise(rows, requests, base)
    finally:
        await runner.cleanup()


def owned_row(index, *, model="native-a", spend="0.20"):
    result = cost_fixtures.row(str(index), answer=ANSWER, chat=CHAT, model=model, spend=spend)
    result["user"] = ACTOR
    result["metadata"]["spend_logs_metadata"]["owui_budget"]["user_id"] = ACTOR
    return result


def test_current_chat_uses_owned_context_and_real_ledger_amounts(tool):
    async def exercise(rows, requests, base):
        rows.extend([owned_row(1), owned_row(2, model="native-b", spend="0.00300")])
        text = await tool.tools.current_chat_cost(**tool.args)
        data = json.loads(text)
        assert data["status"] == "available" and data["spend_usd"] == "0.20300"
        assert [(m["model"], m["spend_usd"]) for m in data["models"]] == [("native-a", "0.20"), ("native-b", "0.00300")]
        assert data["as_of"] and data["final"] is False
        assert data["coverage"] == "accrued_native_ledger_rows"
        assert requests == [("GET", {"session_id": CHAT, "page": "1", "page_size": "100"})]
        for private in (ACTOR, CHAT, ANSWER, KEY, base, "api_key", "request_id", "physical-provider-model"):
            assert private not in text
    asyncio.run(ledger(tool, exercise))


def test_unknown_empty_foreign_and_revoked_chat_reads_never_become_free(tool):
    async def exercise(rows, requests, base):
        data = json.loads(await tool.tools.current_chat_cost(**tool.args))
        assert data["status"] == "unknown" and data["spend_usd"] is None and data["models"] == []
        rows.append(owned_row(1))
        rows[0]["user"] = OTHER
        data = json.loads(await tool.tools.current_chat_cost(**tool.args))
        assert data["status"] == "unavailable" and data["spend_usd"] is None
        rows[:] = [owned_row(1)]
        tool.chats.get_accessible_chat_by_id.side_effect = [SimpleNamespace(user_id=ACTOR), SimpleNamespace(user_id=OTHER)]
        data = json.loads(await tool.tools.current_chat_cost(**tool.args))
        assert data["status"] == "unavailable" and data["spend_usd"] is None
    asyncio.run(ledger(tool, exercise))
