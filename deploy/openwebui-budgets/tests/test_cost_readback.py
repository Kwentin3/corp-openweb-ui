"""Contract tests with a real local HTTP boundary; no LiteLLM/provider calls."""

import asyncio
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from uuid import NAMESPACE_URL, uuid5

from aiohttp import ClientSession, web


PROTOCOL_SPEC = importlib.util.spec_from_file_location(
    "employee_budget_provenance", Path(__file__).parents[1] / "provenance.py")
protocol = importlib.util.module_from_spec(PROTOCOL_SPEC)
sys.modules[PROTOCOL_SPEC.name] = protocol
PROTOCOL_SPEC.loader.exec_module(protocol)

SPEC = importlib.util.spec_from_file_location(
    "employee_budget_cost_readback", Path(__file__).parents[1] / "cost_readback.py")
cost = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cost
SPEC.loader.exec_module(cost)

USER, CHAT, ANSWER, CHILD_CHAT, CHILD_ANSWER, OLD_ANSWER, OTHER_ANSWER, CALL, OTHER_USER, OTHER_CHAT = (
    str(uuid5(NAMESPACE_URL, name)) for name in
    ("user-1", "chat-1", "answer-1", "deleted-child", "child-answer", "old-regenerated-answer",
     "another-answer", "native-validated-call-nonce", "other-user", "other-chat"))


def row(request_id="provider-1", *, answer=ANSWER, model="alias-a", spend="0.20",
        chat=CHAT, child=False):
    return {"request_id": request_id, "user": USER, "session_id": chat, "status": "success",
            "spend": spend, "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
            "model": "physical-provider-model", "api_key": "not-returned-by-projection",
            "metadata": {"spend_logs_metadata": {"owui_budget": {
                "schema": 1, "user_id": USER, "chat_id": CHILD_CHAT if child else chat,
                "answer_id": CHILD_ANSWER if child else answer, "root_chat_id": chat,
                "root_answer_id": answer, "model": model,
                "call_id": CALL, "category": "personal"}}}}


def page(rows, *, number=1, total=None):
    total = len(rows) if total is None else total
    return {"data": rows, "page": number, "page_size": 100,
            "total": total, "total_pages": (total + 99) // 100}


class CostReadbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        self.unexpected_hits = 0
        self.payload = page([row()])
        self.handler = None
        app = web.Application()
        app.router.add_route("*", cost.SESSION_ROUTE, self.serve)
        app.router.add_route("*", "/unexpected", self.unexpected)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        self.session = ClientSession()

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def unexpected(self, request):
        self.unexpected_hits += 1
        return web.Response(status=500)

    async def serve(self, request):
        self.requests.append((request.method, dict(request.query), request.headers.get("Authorization")))
        if self.handler:
            return await self.handler(request)
        return web.json_response(self.payload)

    async def read(self, **kwargs):
        return await cost.read_cost_snapshot(
            self.session, base_url=self.base, read_key="private-read-key", user_id=USER,
            root_chat_id=CHAT, root_answer_id=ANSWER, **kwargs)

    async def test_sum_native_spend_across_models_branches_and_deleted_child(self):
        self.payload = page([row(), row("p2", answer=OLD_ANSWER, model="alias-b", spend="0.10"),
                             row("p3", child=True, spend="0.03")])
        snapshot = await self.read(observed_request_ids={"provider-1", "p3"})
        self.assertEqual(snapshot.answer.spend, Decimal("0.23"))
        self.assertEqual(snapshot.chat.spend, Decimal("0.33"))
        self.assertEqual((snapshot.answer.calls, snapshot.chat.calls), (2, 3))
        self.assertEqual((snapshot.chat.prompt_tokens, snapshot.chat.completion_tokens,
                          snapshot.chat.total_tokens), (30, 15, 45))
        self.assertEqual([(m.model, m.spend) for m in snapshot.chat.models],
                         [("alias-a", Decimal("0.23")), ("alias-b", Decimal("0.10"))])
        self.assertTrue(snapshot.complete)
        self.assertFalse(snapshot.pending)
        self.assertEqual(snapshot.coverage, "observed_requests_only")
        self.assertEqual(self.requests, [("GET", {"session_id": CHAT, "page": "1", "page_size": "100"},
                                          "Bearer private-read-key")])
        self.assertNotIn("not-returned", repr(snapshot))

    async def test_empty_or_unobserved_rows_never_verify_zero_or_complete(self):
        self.payload = page([])
        empty = await self.read()
        self.assertIsNone(empty.answer.spend)
        self.assertIsNone(empty.chat.spend)
        self.assertTrue(empty.pending)
        self.assertFalse(empty.complete)
        self.payload = page([row()])
        accrued = await self.read()
        self.assertEqual(accrued.chat.spend, Decimal("0.20"))
        self.assertTrue(accrued.pending)
        missing = await self.read(observed_request_ids={"missing"})
        self.assertEqual(missing.missing_request_ids, ("missing",))
        self.assertFalse(missing.complete)

    async def test_condition_poll_waits_for_observed_durable_row(self):
        async def delayed(request):
            return web.json_response(page([] if len(self.requests) == 1 else [row()]))
        self.handler = delayed
        snapshot = await self.read(observed_request_ids={"provider-1"}, wait_seconds=.5, poll_interval=.01)
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(snapshot.complete)
        self.assertEqual(snapshot.answer.spend, Decimal("0.20"))

    async def test_pending_wait_is_bounded(self):
        self.payload = page([])
        snapshot = await self.read(observed_request_ids={"missing"}, wait_seconds=.03,
                                   poll_interval=.01, timeout_seconds=.1)
        self.assertTrue(snapshot.pending)
        self.assertEqual(snapshot.missing_request_ids, ("missing",))

    async def test_exact_pagination_over_100_rows(self):
        rows = [row(f"p{i}", spend="0.01") for i in range(101)]
        async def paginate(request):
            number = int(request.query["page"])
            return web.json_response(page(rows[(number-1)*100:number*100], number=number, total=101))
        self.handler = paginate
        snapshot = await self.read(observed_request_ids={"p100"})
        self.assertEqual(snapshot.chat.spend, Decimal("1.01"))
        self.assertEqual(snapshot.chat.calls, 101)
        self.assertEqual([r[1]["page"] for r in self.requests], ["1", "2"])

    async def test_scope_and_usage_mutations_fail_closed(self):
        mutations = [
            ("foreign_scope", lambda r: r.update(user=OTHER_USER)),
            ("foreign_scope", lambda r: r.update(session_id=OTHER_CHAT)),
            ("foreign_scope", lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].update(user_id=OTHER_USER)),
            ("foreign_scope", lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].update(root_chat_id=OTHER_CHAT)),
            ("invalid_attribution", lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].update(category="service")),
            ("invalid_attribution", lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].update(schema=True)),
            ("invalid_attribution", lambda r: r.update(metadata="unhydrated-or-malformed")),
            ("invalid_attribution", lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].pop("call_id")),
            ("invalid_attribution", lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].update(call_id="not-a-uuid")),
            ("invalid_attribution", lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].update(unexpected="shape-drift")),
            ("invalid_usage", lambda r: r.pop("prompt_tokens")),
            ("invalid_usage", lambda r: r.update(completion_tokens=True)),
            ("invalid_usage", lambda r: r.update(total_tokens=14)),
            ("invalid_spend", lambda r: r.update(spend="NaN")),
            ("invalid_spend", lambda r: r.update(spend="Infinity")),
            ("invalid_spend", lambda r: r.update(spend="-0.01")),
            ("invalid_spend", lambda r: r.pop("spend")),
        ]
        for code, mutate in mutations:
            with self.subTest(code=code, mutation=mutations.index((code, mutate))):
                mutated = row()
                mutate(mutated)
                self.payload = page([mutated])
                with self.assertRaises(cost.CostReadError) as ctx:
                    await self.read()
                self.assertEqual(str(ctx.exception), code)

    async def test_failure_unknown_and_default_zero_are_not_verified_free(self):
        mutations = [lambda r: r.update(status="failure"), lambda r: r.pop("status"),
                     lambda r: r["metadata"].update(status="failure"),
                     lambda r: r["metadata"].update(error_information={"error": "private-provider-detail"}),
                     lambda r: r["metadata"].update(response_cost_failure_debug_info={"detail": "private"}),
                     lambda r: r.update(spend=0),
                     lambda r: r.update(prompt_tokens=0, completion_tokens=0, total_tokens=0)]
        for mutate in mutations:
            candidate = row()
            mutate(candidate)
            self.payload = page([candidate])
            with self.subTest(mutation=mutations.index(mutate)):
                with self.assertRaisesRegex(cost.CostReadError, "accounting_unavailable"):
                    await self.read(observed_request_ids={"provider-1"})

    async def test_required_id_on_wrong_answer_is_not_settled(self):
        self.payload = page([row(answer=OTHER_ANSWER)])
        with self.assertRaisesRegex(cost.CostReadError, "foreign_answer"):
            await self.read(observed_request_ids={"provider-1"})

    async def test_duplicate_physical_ids_are_rejected(self):
        self.payload = page([row(), row()])
        with self.assertRaisesRegex(cost.CostReadError, "duplicate_request_id"):
            await self.read()

    async def test_incomplete_capped_and_changed_counts_rejected(self):
        variants = [dict(page([row()]), total_is_capped=True),
                    page([row()], total=2), dict(page([row()]), total_pages=2),
                    dict(page([row()]), page=True), page([], total=10001)]
        for payload in variants:
            self.payload = payload
            with self.subTest(payload=payload), self.assertRaises(cost.CostReadError):
                await self.read()
        async def changing(request):
            number = int(request.query["page"])
            return web.json_response(page([row(f"p{i}") for i in range(100)] if number == 1 else [],
                                          number=number, total=101 if number == 1 else 100))
        self.handler = changing
        with self.assertRaisesRegex(cost.CostReadError, "incomplete_pagination"):
            await self.read()

    async def test_http_redirect_error_body_and_timeout_are_safe(self):
        async def redirect(request):
            raise web.HTTPFound("/unexpected")
        self.handler = redirect
        with self.assertRaisesRegex(cost.CostReadError, "spend_api_unavailable"):
            await self.read()
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.unexpected_hits, 0)
        async def error(request):
            return web.Response(status=403, text="private-read-key internal-secret")
        self.handler = error
        with self.assertRaises(cost.CostReadError) as ctx:
            await self.read()
        self.assertNotIn("private-read-key", str(ctx.exception))
        async def slow(request):
            await asyncio.sleep(.05)
            return web.json_response(page([row()]))
        self.handler = slow
        with self.assertRaisesRegex(cost.CostReadError, "spend_api_unavailable"):
            await self.read(timeout_seconds=.01)

    async def test_count_then_insert_race_restarts_scan_and_confirms_actual_row(self):
        async def publication(request):
            return web.json_response(page([row()], total=0 if len(self.requests) == 1 else 1))
        self.handler = publication
        with self.assertLogs(cost.log, level="INFO") as logged:
            snapshot = await self.read(observed_request_ids={"provider-1"}, wait_seconds=.2, poll_interval=.005)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(snapshot.answer.spend, Decimal(".20"))
        self.assertEqual(snapshot.answer.calls, 1)
        self.assertTrue(snapshot.complete)
        self.assertFalse(snapshot.pending)
        self.assertEqual(logged.output, ["INFO:employee_budget_cost_readback:Budget cost snapshot scan restarted: page_length_changed"])

    async def test_count_drift_discards_every_page_before_starting_again(self):
        values = [row(f"p{i}") for i in range(102)]
        async def publication(request):
            number = int(request.query["page"])
            total = 101 if len(self.requests) == 1 else 102
            return web.json_response(page(values[:100] if number == 1 else values[100:], number=number, total=total))
        self.handler = publication
        snapshot = await self.read(observed_request_ids={"p101"}, wait_seconds=.2, poll_interval=.005)
        self.assertEqual([request[1]["page"] for request in self.requests], ["1", "2", "1", "2"])
        self.assertEqual(snapshot.answer.calls, 102)
        self.assertEqual(snapshot.answer.spend, Decimal("20.40"))
        self.assertTrue(snapshot.complete)

    async def test_persistent_length_mismatch_remains_an_error_at_the_bound(self):
        self.payload = page([row()], total=0)
        with self.assertRaisesRegex(cost.CostReadError, "incomplete_pagination"):
            # Real HTTP scheduling can consume the former 30ms wait before
            # any retry; keep enough time to observe retries and the same error.
            await self.read(observed_request_ids={"provider-1"}, timeout_seconds=.5,
                            wait_seconds=.2, poll_interval=.005)
        self.assertGreater(len(self.requests), 1)
        self.assertTrue(all(request[1]["page"] == "1" for request in self.requests))

    async def test_wait_does_not_retry_capped_malformed_duplicate_or_foreign_data(self):
        foreign = row()
        foreign["user"] = OTHER_USER
        variants = [dict(page([row()]), total_is_capped=True), page([], total=10001),
                    dict(page([row()]), page=True), page([row(), row()]), page([foreign])]
        for payload in variants:
            self.requests.clear()
            self.payload = payload
            with self.subTest(payload=payload), self.assertRaises(cost.CostReadError):
                await self.read(observed_request_ids={"provider-1"}, wait_seconds=.2, poll_interval=.005)
            self.assertEqual(len(self.requests), 1)

    async def test_valid_pending_scan_and_discarded_scan_are_not_merged(self):
        async def publication(request):
            number = len(self.requests)
            return web.json_response(page([]) if number == 1 else page([row()], total=0 if number == 2 else 1))
        self.handler = publication
        snapshot = await self.read(observed_request_ids={"provider-1"}, wait_seconds=.2, poll_interval=.005)
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(snapshot.answer.spend, Decimal(".20"))
        self.assertEqual(snapshot.answer.calls, 1)
        self.assertTrue(snapshot.complete)

    async def test_partial_scan_cannot_become_a_snapshot_on_operation_timeout(self):
        async def publication(request):
            number = int(request.query["page"])
            if number == 2:
                await asyncio.sleep(.1)
            return web.json_response(page([row(f"p{i}") for i in range(100)] if number == 1 else [row("p100")],
                                          number=number, total=101))
        self.handler = publication
        with self.assertRaisesRegex(cost.CostReadError, "spend_api_unavailable"):
            await self.read(observed_request_ids={"p100"}, timeout_seconds=.03,
                            wait_seconds=.03, poll_interval=.005)

    async def test_total_deadline_keeps_valid_pending_snapshot(self):
        async def stalls_after_first_scan(request):
            if len(self.requests) > 1:
                await asyncio.sleep(.5)
            return web.json_response(page([]))
        self.handler = stalls_after_first_scan
        snapshot = await self.read(observed_request_ids={"missing"}, timeout_seconds=.3,
                                   wait_seconds=.3, poll_interval=.005)
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(snapshot.pending)
        self.assertFalse(snapshot.complete)
        self.assertIsNone(snapshot.chat.spend)

    async def test_json_decimal_and_size_boundary(self):
        async def decimal_json(request):
            return web.Response(text=json.dumps(page([row()])).replace('"0.20"', '0.1234567890123456789'),
                                content_type="application/json")
        self.handler = decimal_json
        snapshot = await self.read(observed_request_ids={"provider-1"})
        self.assertEqual(snapshot.answer.spend, Decimal("0.1234567890123456789"))
        async def oversized(request):
            return web.Response(body=b"x" * (cost.MAX_PAGE_BYTES + 1))
        self.handler = oversized
        with self.assertRaisesRegex(cost.CostReadError, "response_too_large"):
            await self.read()

    async def test_decimal_sum_does_not_silently_drop_small_charge(self):
        self.payload = page([row(spend="1e30"), row("p2", spend="0.01")])
        snapshot = await self.read(observed_request_ids={"provider-1"})
        self.assertEqual(snapshot.chat.spend, Decimal("1000000000000000000000000000000.01"))
        self.payload = page([row(spend="1e10000"), row("p2", spend="1e-10000")])
        with self.assertRaisesRegex(cost.CostReadError, "invalid_spend"):
            await self.read()


if __name__ == "__main__":
    unittest.main()
