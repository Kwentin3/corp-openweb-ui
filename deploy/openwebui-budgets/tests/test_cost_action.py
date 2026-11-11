"""Action adapter checks using the real reader and a local HTTP ledger boundary."""

import copy
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import NAMESPACE_URL, uuid5

from aiohttp import ClientSession, web
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse


HERE = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load("employee_budget_provenance", HERE / "provenance.py")
reader = load("employee_budget_cost_readback", HERE / "cost_readback.py")
extension = load("cost_action_under_test", HERE / "cost_action.py")
USER, OTHER, CHAT, ANSWER, NEXT = (str(uuid5(NAMESPACE_URL, label)) for label in
                                  ("action-user", "action-other", "action-chat", "action-answer", "action-next"))
MODEL = "goal584-a"
KEY = "synthetic-server-held-reader-key"


def monthly_budget(**changes):
    result = {"user_id": USER, "email": "private@synthetic.invalid", "revision": "private-revision",
        "budget_usd": "20", "spend_usd": "3", "remaining_usd": "17", "budget_duration": "1mo",
        "budget_reset_at": "2026-12-01T00:00:00Z", "as_of": "2026-11-11T12:00:00+00:00",
        "expense_status": "unavailable", "expense_observation_scope": "assignment_history",
        "models": [{"id": MODEL, "label": MODEL, "cap_usd": "20", "spend_usd": "3",
            "remaining_usd": "17", "budget_duration": "1mo", "budget_reset_at": "2026-12-01T00:00:00Z",
            "blocked": False, "expense_status": "unavailable"}]}
    result.update(changes)
    return result


def module(**values):
    result = ModuleType("native_external_state")
    result.__dict__.update(values)
    return result


class Markers(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.scope = None
        self.totals, self.models, self.times = {}, [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section":
            self.scope = attrs["data-cost-scope"]
        if "data-cost-usd" in attrs:
            self.totals[self.scope] = attrs["data-cost-usd"]
        if "data-model" in attrs:
            self.models.append((self.scope, attrs["data-model"]))
        if tag == "time":
            self.times.append(attrs["datetime"])


def ledger_row(index, *, answer=ANSWER, model=MODEL):
    return {"request_id": "provider-" + str(index), "user": USER, "session_id": CHAT, "status": "success",
            "spend": ".20", "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
            "metadata": {"spend_logs_metadata": {"owui_budget": {
                "schema": 1, "user_id": USER, "chat_id": CHAT, "answer_id": answer,
                "root_chat_id": CHAT, "root_answer_id": answer, "model": model,
                "call_id": str(uuid5(NAMESPACE_URL, "action-call-" + str(index))), "category": "personal"}}}}


class CostActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rows, self.http_calls, self.http_status = [ledger_row(1)], [], 200
        app = web.Application()
        app.router.add_get(reader.SESSION_ROUTE, self.serve)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.url = "http://127.0.0.1:" + str(site._server.sockets[0].getsockname()[1])
        self.session = ClientSession()
        self.user = SimpleNamespace(id=USER, role="user")
        self.users = SimpleNamespace(get_user_by_id=AsyncMock(return_value=self.user))
        self.chat = SimpleNamespace(user_id=USER)
        self.message = {"id": ANSWER, "user_id": USER, "role": "assistant", "model": MODEL,
                        "content": "PRIVATE CHAT TEXT"}
        self.chats = SimpleNamespace(get_accessible_chat_by_id=AsyncMock(return_value=self.chat),
            get_message_by_id_and_message_id=AsyncMock(return_value=self.message))
        self.owner = SimpleNamespace(type="filter", is_active=True)
        self.config = {"ledger_base_url": self.url, "ledger_read_key": KEY, "read_wait_seconds": 8.0}
        self.functions = SimpleNamespace(get_function_by_id=AsyncMock(return_value=self.owner),
            get_function_valves_by_id=AsyncMock(return_value=self.config))
        self.shared_session = AsyncMock(return_value=self.session)
        self.monthly_owner = SimpleNamespace(type="event", is_active=True)
        self.monthly_read = AsyncMock(return_value=JSONResponse(monthly_budget()))
        self.cached = AsyncMock(return_value=(SimpleNamespace(read_monthly=self.monthly_read), None, None))
        self.environment = module(VERSION="0.12.2")
        modules = {name: module() for name in ("open_webui", "open_webui.models", "open_webui.utils")}
        modules.update({"open_webui.env": self.environment,
            "open_webui.models.users": module(Users=self.users), "open_webui.models.chats": module(Chats=self.chats),
            "open_webui.models.functions": module(Functions=self.functions),
            "open_webui.utils.auth": module(VERIFIED_USER_ROLES={"user", "admin"}),
            "open_webui.utils.plugin": module(get_function_module_from_cache=self.cached),
            "open_webui.utils.session_pool": module(get_session=self.shared_session)})
        self.native_patch = patch.dict(sys.modules, modules)
        self.native_patch.start()
        self.addCleanup(self.native_patch.stop)
        self.action = extension.Action()
        self.request = SimpleNamespace(state=SimpleNamespace(direct=False))
        self.body = {"chat_id": CHAT, "id": ANSWER, "model": MODEL, "embeds": ["existing tool embed"]}

    def enable_monthly(self):
        self.functions.get_function_by_id.side_effect = lambda fid: (
            self.owner if fid == extension.FILTER_ID else self.monthly_owner)

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def serve(self, request):
        self.http_calls.append((request.method, dict(request.query), request.headers.get("Authorization")))
        if self.http_status != 200:
            return web.Response(status=self.http_status, text=KEY + self.url + " PRIVATE CHAT TEXT")
        return web.json_response({"data": self.rows, "page": 1, "page_size": 100,
                                  "total": len(self.rows), "total_pages": 1 if self.rows else 0})

    async def click(self, **kwargs):
        response, context = await self.action.action(self.body, __user__={"id": USER},
            __request__=self.request, __model__={"id": MODEL}, **kwargs)
        self.assertIsInstance(response, HTMLResponse)
        self.assertEqual(response.headers["content-disposition"], "inline")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(context["status"], "success")
        return response.body.decode()

    async def test_native_money_is_visible_when_token_statistics_are_unavailable(self):
        self.rows[0].pop("prompt_tokens")
        text = await self.click()
        self.assertEqual(Markers(text).totals, {"answer": "0.20", "chat": "0.20"})
        self.assertIn('data-field="prompt_tokens">нет данных</td>', text)
        self.assertNotIn('data-field="prompt_tokens">0</td>', text)

    async def test_real_reader_config_shared_session_and_native_scope_only(self):
        original = copy.deepcopy(self.body)
        self.body.update(messages=[{"content": "FORGED HTML"}], metadata={"chat_id": OTHER},
                         ledger_read_key="caller-secret", root_answer_id=NEXT)
        text = await self.click()
        self.assertEqual(Markers(text).totals, {"answer": "0.20", "chat": "0.20"})
        self.assertEqual(self.http_calls, [("GET", {"session_id": CHAT, "page": "1", "page_size": "100"},
                                             "Bearer " + KEY)])
        self.functions.get_function_valves_by_id.assert_awaited_once_with("employee_budget_cost")
        self.shared_session.assert_awaited_once_with()
        self.chats.get_accessible_chat_by_id.assert_awaited_once_with(CHAT, self.user, permission="read")
        self.assertEqual(self.body["embeds"], original["embeds"])
        for private in (KEY, self.url, USER, CHAT, ANSWER, NEXT, "PRIVATE CHAT TEXT", "FORGED HTML", "caller-secret"):
            self.assertNotIn(private, text)
        self.assertFalse(hasattr(self.action, "Valves"))

    async def test_each_click_rereads_same_selected_answer_and_full_chat(self):
        self.rows = [ledger_row(1), ledger_row(2)]
        first = await self.click()
        self.rows += [ledger_row(i, answer=NEXT, model="goal584-b") for i in range(3, 7)]
        second = await self.click()
        self.assertEqual(Markers(first).totals, {"answer": "0.40", "chat": "0.40"})
        self.assertEqual(Markers(second).totals, {"answer": "0.40", "chat": "1.20"})
        self.assertEqual(len(self.http_calls), 2)
        self.assertEqual(self.users.get_user_by_id.await_count, 4)
        self.assertEqual(self.functions.get_function_valves_by_id.await_count, 2)
        self.assertEqual(Markers(second).models, [("answer", MODEL), ("chat", MODEL), ("chat", "goal584-b")])
        self.assertIn('data-field="total_tokens">60</td>', second)

    async def test_authority_denials_never_reach_ledger(self):
        variants = ("missing_user", "pending_user", "foreign_chat", "missing_chat", "foreign_message",
                    "missing_message", "user_message", "saved_model", "body_model", "native_model",
                    "inactive_filter", "missing_filter", "direct", "version", "bad_uuid")
        for variant in variants:
            with self.subTest(variant=variant):
                saved = (self.user.role, self.chat.user_id, copy.deepcopy(self.message), self.owner.is_active,
                         self.request.state.direct, self.environment.VERSION, copy.deepcopy(self.body))
                self.users.get_user_by_id.return_value = None if variant == "missing_user" else self.user
                self.chats.get_accessible_chat_by_id.return_value = None if variant == "missing_chat" else self.chat
                self.chats.get_message_by_id_and_message_id.return_value = None if variant == "missing_message" else self.message
                self.functions.get_function_by_id.return_value = None if variant == "missing_filter" else self.owner
                if variant == "pending_user": self.user.role = "pending"
                if variant == "foreign_chat": self.user.role, self.chat.user_id = "admin", OTHER
                if variant == "foreign_message": self.message["user_id"] = OTHER
                if variant == "user_message": self.message["role"] = "user"
                if variant == "saved_model": self.message["model"] = "other"
                if variant == "body_model": self.body["model"] = "other"
                if variant == "inactive_filter": self.owner.is_active = False
                if variant == "direct": self.request.state.direct = True
                if variant == "version": self.environment.VERSION = "0.12.3"
                if variant == "bad_uuid": self.body["chat_id"] = "temp-chat"
                with self.assertRaises(ValueError):
                    await self.action.action(self.body, __user__={"id": USER}, __request__=self.request,
                                             __model__={"id": "other" if variant == "native_model" else MODEL})
                (self.user.role, self.chat.user_id, message, self.owner.is_active,
                 self.request.state.direct, self.environment.VERSION, self.body) = saved
                self.message.clear(); self.message.update(message)
        self.assertEqual(self.http_calls, [])

    async def test_missing_context_rejected(self):
        for user, request in ((None, self.request), ({"id": OTHER}, None), ({"id": "not-a-uuid"}, self.request)):
            with self.assertRaises(ValueError):
                await self.action.action(self.body, __user__=user, __request__=request, __model__={"id": MODEL})
        self.assertEqual(self.http_calls, [])

    async def test_monthly_uses_active_native_cache_public_self_owner_and_refreshes(self):
        self.enable_monthly()
        self.body.update(user_id=OTHER, monthly={"budget_usd": "9000"})
        first = await self.click()
        self.assertIn('data-monthly-field="budget">20 USD</output>', first)
        self.monthly_read.return_value = JSONResponse(monthly_budget(budget_usd="30", remaining_usd="27"))
        second = await self.click()
        self.assertIn('data-monthly-field="budget">30 USD</output>', second)
        self.assertEqual(Markers(second).totals, {"answer": "0.20", "chat": "0.20"})
        self.assertEqual(self.monthly_read.await_count, 2)
        self.monthly_read.assert_awaited_with(self.request, self.user, None)
        self.cached.assert_awaited_with(self.request, extension.MONTHLY_ID, function=self.monthly_owner)
        for private in (USER, OTHER, "private@synthetic.invalid", "private-revision", KEY, self.url, "9000"):
            self.assertNotIn(private, second)
        self.assertNotIn("fetch(", second)
        self.assertIn("При публикации чата этот снимок бюджета тоже станет доступен читателям.", second)

    async def test_monthly_unavailable_never_becomes_zero_or_breaks_existing_cost(self):
        self.enable_monthly()
        for defect in ("missing", "inactive", "wrong_type", "backend", "invalid", "foreign"):
            with self.subTest(defect=defect):
                self.monthly_owner = SimpleNamespace(type="filter" if defect == "wrong_type" else "event",
                    is_active=defect != "inactive") if defect != "missing" else None
                self.monthly_read.reset_mock(side_effect=True)
                self.monthly_read.return_value = JSONResponse(monthly_budget())
                if defect == "backend":self.monthly_read.side_effect = HTTPException(503, KEY + self.url)
                if defect == "invalid":self.monthly_read.return_value = JSONResponse({"user_id": USER})
                if defect == "foreign":self.monthly_read.return_value = JSONResponse(monthly_budget(user_id=OTHER))
                text = await self.click()
                self.assertIn('data-monthly-budget="unavailable"', text)
                self.assertNotIn('data-monthly-field="budget"', text)
                self.assertEqual(Markers(text).totals, {"answer": "0.20", "chat": "0.20"})
                self.assertNotIn(KEY, text)
                self.assertNotIn(self.url, text)
                if defect in ("missing", "inactive", "wrong_type"):
                    self.monthly_read.assert_not_awaited()

    async def test_monthly_authority_denial_and_role_loss_disclose_no_snapshot(self):
        self.enable_monthly()
        for status in (400, 401, 403):
            self.monthly_read.side_effect = HTTPException(status, KEY)
            with self.assertRaisesRegex(ValueError, "Cost details are unavailable"):
                await self.click()
        async def revoke(*args):
            self.user.role = "pending"
            raise HTTPException(503, KEY)
        self.monthly_read.side_effect = revoke
        with self.assertRaisesRegex(ValueError, "Cost details are unavailable"):
            await self.click()

    def test_monthly_render_preserves_zero_null_negative_blocks_and_unknown_without_recalculation(self):
        snapshot = monthly_budget(budget_usd="0", spend_usd="0", remaining_usd="-0.00000000000012300",
                                  expense_status="unknown")
        template = snapshot["models"][0]
        snapshot["models"] = [dict(template, id='wire-<img src=x onerror=alert(1)>', label='<img src=x>',
            cap_usd=None, remaining_usd=None, blocked=True, expense_status="unknown"),
            dict(template, id="zero", label="zero", cap_usd="0", spend_usd="0", remaining_usd="0", blocked=False),
            dict(template, id="unset", label="unset", blocked=None)]
        text = extension.render_monthly(snapshot)
        self.assertIn('data-monthly-field="budget">0 USD</output>', text)
        self.assertIn('data-monthly-field="spend">0 USD</output>', text)
        self.assertIn('-0.00000000000012300 USD', text)
        self.assertIn("не установлен", text)
        self.assertIn("нет лимита", text)
        for state in ("Заблокирована", "Не заблокирована", "Нет данных", "Расход неизвестен", "Полнота данных о расходе не подтверждена"):
            self.assertIn(state, text)
        self.assertIn("1mo", text)
        self.assertIn("2026-12-01T00:00:00Z", text)
        self.assertIn("2026-11-11T12:00:00+00:00", text)
        self.assertNotIn("<img", text)
        self.assertIn("&lt;img", text)
        self.assertIn("Модели не назначены", extension.render_monthly(monthly_budget(models=[])))

    async def test_empty_unavailable_or_unknown_cost_is_not_zero(self):
        self.rows = []
        for status in (200, 503):
            self.http_status = status
            text = await self.click()
            self.assertEqual(Markers(text).totals, {"answer": "unknown", "chat": "unknown"})
            self.assertNotIn('data-cost-usd="0', text)
            for value in (KEY, self.url, "PRIVATE CHAT TEXT"):
                self.assertNotIn(value, text)
        self.http_status, self.rows = 200, [ledger_row(1)]
        self.rows[0]["spend"] = "NaN"
        text = await self.click()
        self.assertEqual(Markers(text).totals["chat"], "unknown")

    def test_real_data_contract_rendering_escaping_decimal_time_and_height_only_script(self):
        model = 'wire-\"><img src=x onerror=alert(1)>'
        part = reader.ModelCost(model, Decimal("0.00000000000012300"), 2, 20, 10, 30)
        total = reader.CostTotal(part.spend, 2, 20, 10, 30, (part,))
        snapshot = reader.CostSnapshot(USER, CHAT, ANSWER, total, total,
            datetime(2026, 11, 2, 12, 30, tzinfo=timezone.utc), True, False, ())
        text = extension.render(snapshot)
        self.assertEqual(Markers(text).totals["answer"], "0.00000000000012300")
        self.assertIn(("answer", model), Markers(text).models)
        self.assertNotIn("<img", text)
        self.assertIn("&quot;&gt;&lt;img", text)
        self.assertEqual(Markers(text).times, ["2026-11-02T12:30:00+00:00"])
        self.assertIn('data-budget-cost-details="v1"', text)
        self.assertIn("default-src 'none'", text)
        self.assertIn("iframe:height", text)
        self.assertIn("ResizeObserver", text)
        self.assertNotIn("fetch(", text)
        self.assertNotIn("<form", text)
        self.assertNotIn("<script src", text)


if __name__ == "__main__":
    unittest.main()
