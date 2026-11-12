"""Contract tests with a real local HTTP boundary; no LiteLLM/provider calls."""

import asyncio
import copy
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from urllib.parse import urlsplit
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

if "employee_budget_admin_contract" not in sys.modules:
    CONTRACT_SPEC = importlib.util.spec_from_file_location(
        "employee_budget_admin_contract", Path(__file__).parents[1] / "admin_contract.py")
    contract = importlib.util.module_from_spec(CONTRACT_SPEC)
    sys.modules[CONTRACT_SPEC.name] = contract
    CONTRACT_SPEC.loader.exec_module(contract)
contract = sys.modules["employee_budget_admin_contract"]

USER, CHAT, ANSWER, CHILD_CHAT, CHILD_ANSWER, OLD_ANSWER, OTHER_ANSWER, CALL, OTHER_USER, OTHER_CHAT = (
    str(uuid5(NAMESPACE_URL, name)) for name in
    ("user-1", "chat-1", "answer-1", "deleted-child", "child-answer", "old-regenerated-answer",
     "another-answer", "native-validated-call-nonce", "other-user", "other-chat"))


def row(request_id="provider-1", *, answer=ANSWER, model="alias-a", spend="0.20",
        chat=CHAT, child=False, call_id=CALL):
    return {"request_id": request_id, "user": USER, "session_id": chat, "status": "success",
            "spend": spend, "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
            "model": "physical-provider-model", "api_key": "not-returned-by-projection",
            "metadata": {"spend_logs_metadata": {"owui_budget": {
                "schema": 1, "user_id": USER, "chat_id": CHILD_CHAT if child else chat,
                "answer_id": CHILD_ANSWER if child else answer, "root_chat_id": chat,
                "root_answer_id": answer, "model": model,
                "call_id": call_id, "category": "personal"}}}}


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

    def issued_nonce(self):
        secret = "synthetic-only-gateway-secret-" * 2
        token = protocol.encode_call(secret, user_id=USER, chat_id=CHAT, answer_id=ANSWER,
            root_chat_id=CHAT, root_answer_id=ANSWER, model="alias-a")
        return protocol.decode_call(token, secret, user_id=USER, model="alias-a")["jti"]

    async def test_real_jwt_nonce_covers_responses_row_without_advertised_id_alias(self):
        nonce = self.issued_nonce()
        self.payload = page([row("resp_sdk_model_encoded", call_id=nonce)])
        before = await self.read(observed_request_ids=["resp_security_opaque"])
        self.assertFalse(before.complete)
        self.assertEqual(before.missing_request_ids, ("resp_security_opaque",))
        after = await self.read(observed_call_ids=[nonce])
        self.assertTrue(after.complete)
        self.assertFalse(after.pending)
        self.assertEqual(after.answer.spend, Decimal("0.20"))
        self.assertEqual(after.missing_call_ids, ())
        self.assertEqual(after.missing_request_ids, ())
        self.assertEqual(after.coverage, "observed_calls_only")
        self.assertEqual(before.answer, after.answer)
        self.assertNotIn("resp_security_opaque", repr(after))

    async def test_mixed_request_and_call_coverage_requires_both_sets(self):
        nonce = self.issued_nonce()
        self.payload = page([row("cc-one"), row("resp_sdk_encoded", call_id=nonce)])
        complete = await self.read(observed_request_ids=["cc-one"], observed_call_ids=[nonce])
        self.assertTrue(complete.complete)
        self.assertEqual(complete.coverage, "observed_requests_and_calls_only")
        self.assertEqual(complete.answer.spend, Decimal("0.40"))
        missing_nonce = self.issued_nonce()
        partial = await self.read(observed_request_ids=["cc-missing"], observed_call_ids=[nonce, missing_nonce])
        self.assertTrue(partial.pending)
        self.assertFalse(partial.complete)
        self.assertEqual(partial.missing_request_ids, ("cc-missing",))
        self.assertEqual(partial.missing_call_ids, (missing_nonce,))

    async def test_two_tool_nonces_wait_only_for_actual_durable_rows(self):
        first, second = self.issued_nonce(), self.issued_nonce()
        async def delayed(request):
            rows = [row("encoded-first", call_id=first)]
            if len(self.requests) > 1:
                rows.append(row("encoded-second", call_id=second))
            return web.json_response(page(rows))
        self.handler = delayed
        result = await self.read(observed_call_ids=[first, second], wait_seconds=.5, poll_interval=.01)
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(result.complete)
        self.assertEqual(result.answer.spend, Decimal("0.40"))
        self.assertEqual(result.answer.calls, 2)
        self.assertEqual(result.coverage, "observed_calls_only")

    async def test_call_nonce_missing_or_foreign_answer_remains_unsettled_and_native_zero_is_correlated(self):
        nonce = self.issued_nonce()
        self.payload = page([])
        missing = await self.read(observed_call_ids=[nonce], wait_seconds=.02, poll_interval=.01)
        self.assertTrue(missing.pending)
        self.assertEqual(missing.missing_call_ids, (nonce,))
        self.assertIsNone(missing.answer.spend)
        # Check every matching row, so a map overwrite cannot hide a foreign
        # answer with the same native nonce and a different physical ID.
        self.payload = page([row("wrong-root", answer=OTHER_ANSWER, call_id=nonce), row("right-root", call_id=nonce)])
        with self.assertRaisesRegex(cost.CostReadError, "foreign_answer"):
            await self.read(observed_call_ids=[nonce])
        self.payload = page([row(call_id=nonce, spend="0")])
        self.assertEqual((await self.read(observed_call_ids=[nonce])).answer.spend, Decimal(0))

    async def test_observed_call_collection_is_canonical_and_bounded_before_http(self):
        for value in (CALL, CALL.encode(), None, ["not-a-uuid"], [CALL.upper()], [True], [CALL] * 10001):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaisesRegex(cost.CostReadError, "invalid_scope"):
                    await self.read(observed_call_ids=value)
        self.assertEqual(self.requests, [])

    async def test_call_coverage_does_not_relax_row_identity_or_claim_all_attempts(self):
        nonce = self.issued_nonce()
        self.payload = page([row("same-id", call_id=nonce), row("same-id", call_id=nonce)])
        with self.assertRaisesRegex(cost.CostReadError, "duplicate_request_id"):
            await self.read(observed_call_ids=[nonce])
        # Multiple distinct native rows can share a logical nonce (retry or
        # fallback). This snapshot covers only supplied observed calls, with
        # all actual rows accrued; it does not certify unknown physical work.
        self.payload = page([row("attempt-one", call_id=nonce), row("attempt-two", call_id=nonce)])
        snapshot = await self.read(observed_call_ids=[nonce])
        self.assertTrue(snapshot.complete)
        self.assertEqual(snapshot.coverage, "observed_calls_only")
        self.assertEqual(snapshot.answer.calls, 2)
        self.assertEqual(snapshot.answer.spend, Decimal("0.40"))

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
                     lambda r: r.update(spend=0, prompt_tokens=0, completion_tokens=0, total_tokens=0)]
        for mutate in mutations:
            candidate = row()
            mutate(candidate)
            self.payload = page([candidate])
            with self.subTest(mutation=mutations.index(mutate)):
                with self.assertRaisesRegex(cost.CostReadError, "accounting_unavailable"):
                    await self.read(observed_request_ids={"provider-1"})

    async def test_native_money_does_not_require_or_obey_legacy_usage_guard_witness(self):
        for action in ("block", "block_failed"):
            for spend, status in (("0", "success"), ("0.20", "success"), ("0.20", "failure")):
                candidate = row(spend=spend)
                candidate["status"] = status
                candidate["metadata"]["guardrail_information"] = [{
                    "guardrail_name": "owui_budget_usage", "guardrail_action": action,
                    "violation_categories": ["usage_unavailable"]}]
                self.payload = page([candidate])
                before = copy.deepcopy(self.payload)
                with self.subTest(action=action, spend=spend, status=status):
                    if status == "success":
                        snapshot = await self.read(observed_request_ids={"provider-1"})
                        self.assertEqual(snapshot.answer.spend, Decimal(spend))
                    else:
                        with self.assertRaisesRegex(cost.CostReadError, "^accounting_unavailable$"):
                            await self.read(observed_request_ids={"provider-1"})
                    self.assertEqual(self.payload, before)

    async def test_native_spend_totals_are_independent_of_legacy_guard_status(self):
        unknown = row("unknown", answer=OLD_ANSWER, spend="0.40")
        unknown["metadata"]["guardrail_information"] = [{
            "guardrail_name": "owui_budget_usage", "guardrail_action": "block",
            "violation_categories": ["usage_unavailable"]}]
        for rows in ([row(), unknown], [unknown, row()]):
            self.payload = page(rows)
            snapshot = await self.read(observed_request_ids={"provider-1"})
            self.assertEqual(snapshot.chat.spend, Decimal("0.60"))

    async def test_unknown_telemetry_does_not_hide_foreign_owner_or_signed_scope(self):
        for mutate in (lambda r: r.update(user=OTHER_USER), lambda r: r.update(session_id=OTHER_CHAT),
                       lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].update(user_id=OTHER_USER),
                       lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].update(root_chat_id=OTHER_CHAT)):
            candidate = row()
            candidate["metadata"]["guardrail_information"] = [{
                "guardrail_name": "owui_budget_usage", "guardrail_action": "block_failed",
                "violation_categories": ["usage_unavailable"]}]
            mutate(candidate)
            self.payload = page([candidate])
            with self.assertRaisesRegex(cost.CostReadError, "^foreign_scope$"):
                await self.read()

    async def test_other_native_guardrail_category_is_not_this_usage_marker(self):
        candidate = row()
        candidate["metadata"]["guardrail_information"] = [{
            "guardrail_name": "other_native_guardrail", "guardrail_action": "block",
            "violation_categories": ["usage_unavailable"]}, {
            "guardrail_name": None, "guardrail_status": "success"}, {
            "guardrail_name": "owui_budget_usage", "guardrail_action": "allow", "violation_categories": []}]
        self.payload = page([candidate])
        snapshot = await self.read(observed_request_ids={"provider-1"})
        self.assertTrue(snapshot.complete)
        self.assertEqual(snapshot.answer.spend, Decimal("0.20"))
        candidate["spend"] = "0"
        self.assertEqual((await self.read()).answer.spend, Decimal(0))
        candidate.update(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        with self.assertRaisesRegex(cost.CostReadError, "^accounting_unavailable$"):
            await self.read()

    async def test_legacy_guard_telemetry_does_not_replace_native_spend(self):
        native = {"guardrail_name": "owui_budget_usage", "guardrail_action": "block",
                  "violation_categories": ["usage_unavailable"]}
        variants = [native, [None],
                    [dict(native, violation_categories=None)], [dict(native, violation_categories="usage_unavailable")],
                    [dict(native, violation_categories=[True])], [dict(native, guardrail_action=None)],
                    [dict(native, guardrail_action="unexpected")], [dict(native, guardrail_action="allow")],
                    [dict(native, violation_categories=[])]]
        for telemetry in variants:
            candidate = row()
            candidate["metadata"]["guardrail_information"] = telemetry
            self.payload = page([candidate])
            with self.subTest(telemetry=telemetry):
                self.assertEqual((await self.read()).answer.spend, Decimal("0.20"))

    async def test_positive_native_money_survives_zero_missing_or_invalid_token_telemetry(self):
        for changes in ({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        {"prompt_tokens": None}, {"completion_tokens": True}, {"total_tokens": 14}):
            candidate = row()
            candidate.update(changes)
            self.payload = page([candidate])
            snapshot = await self.read(observed_call_ids=[CALL])
            self.assertEqual((snapshot.answer.spend, snapshot.chat.spend), (Decimal("0.20"), Decimal("0.20")))
            self.assertTrue(snapshot.complete)
            if changes.get("prompt_tokens", 1) is None:
                self.assertIsNone(snapshot.chat.prompt_tokens)
            if changes.get("total_tokens") == 14:
                self.assertIsNone(snapshot.chat.total_tokens)

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


    async def test_native_zero_with_usage_needs_no_guard_and_default_all_zero_stays_unavailable(self):
        candidate = row(spend='0')
        self.payload = page([candidate])
        snapshot = await self.read(observed_call_ids=[CALL])
        self.assertEqual(snapshot.answer.spend, Decimal(0))
        self.assertTrue(snapshot.complete)
        candidate.update(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        with self.assertRaisesRegex(cost.CostReadError, 'accounting_unavailable'):
            await self.read(observed_call_ids=[CALL])


class _MemoryReadSession:
    """Finite aiohttp GET/content IO leaf; never creates a socket/client."""
    def __init__(self, owner): self.owner, self.closed = owner, False

    async def close(self): self.closed = True

    def get(self, url, *, params, headers, allow_redirects, timeout):
        owner = self.owner
        assert allow_redirects is False and 0 < timeout.total <= 60
        assert urlsplit(url).path in (cost.ADMIN_ROUTE, cost.SESSION_ROUTE)
        query = {key: str(value) for key, value in params.items()}
        @asynccontextmanager
        async def response():
            owner.requests.append(("GET", query, headers.get("Authorization")))
            request = SimpleNamespace(query=query, headers=headers)
            try:
                result = await owner.handler(request) if owner.handler else web.json_response(owner.payload)
            except web.HTTPException as error:
                result = error
            async def chunks(size):
                body = result.body or b""
                for offset in range(0, len(body), size): yield body[offset:offset + size]
            yield SimpleNamespace(status=result.status, content=SimpleNamespace(iter_chunked=chunks))
        return response()


ASSIGNMENT = "a" * 64
OBSERVATION_START = datetime(1970, 1, 1, tzinfo=timezone.utc)
OBSERVATION_END = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)


def admin_row(request_id="provider-1", *, unknown=False, action="block"):
    value = row(request_id)
    value.update(api_key=ASSIGNMENT, model_group="alias-a")
    if unknown:
        value["metadata"]["guardrail_information"] = [{"guardrail_name": "owui_budget_usage",
            "guardrail_action": action, "violation_categories": ["usage_unavailable"]}]
    return value


def admin_page(rows, *, number=1, total=None):
    return {**page(rows, number=number, total=total), "total_is_capped": False}


def presence_state(models=("alias-a",)):
    return contract.EmployeeBudget(USER, Decimal(10), Decimal(0), "1mo", "2026-12-01T00:00:00Z",
        tuple(contract.ModelBudget(model, ASSIGNMENT, "native-alias-" + model,
            Decimal(5), Decimal(0), "1mo", "2026-12-01T00:00:00Z", False) for model in models))


class AdminUnknownPresenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests, self.handler = [], None
        self.payload = admin_page([admin_row()])
        self.session = _MemoryReadSession(self)

    async def asyncTearDown(self):
        await self.session.close()

    async def read(self, **kwargs):
        values = dict(base_url="http://native-fixture.invalid", admin_key="synthetic-admin-only-key", user_id=USER,
            model="alias-a", assignment_hash=ASSIGNMENT,
            observation_start=OBSERVATION_START, observation_end=OBSERVATION_END)
        values.update(kwargs)
        return await cost.read_admin_unknown_presence(self.session, **values)

    def assert_unconfirmed(self, result):
        self.assertFalse(result.unknown_confirmed)
        self.assertFalse(result.final)
        self.assertFalse(result.pagination_complete)
        self.assertEqual(result.coverage, "observed_native_rows_only")
        self.assertFalse(hasattr(result, "known_subtotal"))
        self.assertFalse(hasattr(result, "observed_total_spend"))

    async def test_shared_reader_preserves_actual_presence_only_witness_and_native_state(self):
        states = {USER: presence_state()}
        before = copy.deepcopy(states)
        self.payload = admin_page([admin_row(unknown=True)])
        observed = await cost.read_unknown_presence(self.session, base_url="http://native-fixture.invalid",
            admin_key="synthetic-admin-only-key", states=states)
        self.assertEqual(set(observed), {USER})
        self.assertEqual(set(observed[USER]["alias-a"]), {"unknown_confirmed", "as_of"})
        self.assertIs(observed[USER]["alias-a"]["unknown_confirmed"], True)
        query = self.requests[-1][1]
        self.assertEqual(query["api_key"], ASSIGNMENT)
        self.assertEqual(query["start_date"], "1970-01-01 00:00:00")
        self.assertEqual(query["sort_order"], "desc")
        self.payload = admin_page([admin_row()])
        unconfirmed = await cost.read_unknown_presence(self.session, base_url="http://native-fixture.invalid",
            admin_key="synthetic-admin-only-key", states=states)
        self.assertIs(unconfirmed[USER]["alias-a"]["unknown_confirmed"], False)
        self.assertEqual(states, before)
        self.assertFalse(self.session.closed)

    async def test_shared_reader_never_runs_more_than_four_native_reads(self):
        active = peak = 0
        reached, release = asyncio.Event(), asyncio.Event()
        async def serve(request):
            nonlocal active, peak
            active += 1; peak = max(active, peak)
            if active == 4: reached.set()
            try:
                await release.wait()
                return web.json_response(admin_page([]))
            finally:
                active -= 1
        self.handler = serve
        states = {USER: presence_state(tuple("alias-" + str(i) for i in range(6)))}
        task = asyncio.create_task(cost.read_unknown_presence(self.session, base_url="http://native-fixture.invalid",
            admin_key="synthetic-admin-only-key", states=states))
        try:
            await asyncio.wait_for(reached.wait(), 1)
            self.assertEqual(len(self.requests), 4)
        finally:
            release.set()
        observed = await asyncio.wait_for(task, 1)
        self.assertEqual((peak, active, len(self.requests)), (4, 0, 6))
        self.assertEqual(len(observed[USER]), 6)
        self.assertTrue(all(v["unknown_confirmed"] is False for v in observed[USER].values()))

    async def test_shared_deadline_retains_completed_witness_and_awaits_cancelled_reads(self):
        active = 0
        parked = asyncio.Event()
        async def serve(request):
            nonlocal active
            active += 1
            try:
                if request.query["model_group"] == "alias-a":
                    return web.json_response(admin_page([admin_row(unknown=True)]))
                await parked.wait()
            finally:
                active -= 1
        self.handler = serve
        observed = await cost.read_unknown_presence(self.session, base_url="http://native-fixture.invalid",
            admin_key="synthetic-admin-only-key", states={USER: presence_state(("alias-a", "alias-b"))},
            timeout_seconds=.03)
        self.assertEqual(set(observed[USER]), {"alias-a"})
        self.assertIs(observed[USER]["alias-a"]["unknown_confirmed"], True)
        self.assertEqual(active, 0)
        self.assertFalse(self.session.closed)

    async def test_owned_unknown_after_known_and_unbound_audit_needs_no_money_or_usage(self):
        witness = admin_row("unknown", unknown=True)
        witness.update(spend="not-an-amount", total_tokens=True, prompt_tokens=None,
                       completion_tokens=-1, status="opaque-native-status", blocked=False)
        self.payload = admin_page([admin_row("known"), {"request_id": "unbound-native-audit"}, witness])
        before = copy.deepcopy(self.payload)
        result = await self.read()
        self.assertTrue(result.unknown_confirmed)
        self.assertEqual((result.scanned_rows, result.reason), (3, "usage_unavailable"))
        self.assertEqual(self.payload, before)
        self.assertFalse(result.final); self.assertFalse(result.pagination_complete)
        self.assertNotIn(ASSIGNMENT, repr(result))
        self.assertNotIn("synthetic-admin", repr(result))
        self.assertFalse(self.session.closed)

    async def test_foreign_or_invalid_row_identity_never_confirms_a_marker(self):
        mutations = (lambda r:r.update(user=OTHER_USER), lambda r:r.update(api_key="b"*64),
            lambda r:r.update(model_group="other-alias"), lambda r:r.update(model=""),
            lambda r:r.update(request_id=""), lambda r:r.update(session_id=OTHER_CHAT),
            lambda r:r.update(session_id="not-native"),
            lambda r:r["metadata"]["spend_logs_metadata"]["owui_budget"].update(model="other-alias"),
            lambda r:r["metadata"]["spend_logs_metadata"]["owui_budget"].update(user_id=OTHER_USER),
            lambda r:r["metadata"]["spend_logs_metadata"]["owui_budget"].update(root_chat_id=OTHER_CHAT),
            lambda r:r["metadata"]["spend_logs_metadata"]["owui_budget"].update(call_id="unbound"),
            lambda r:r["metadata"]["spend_logs_metadata"]["owui_budget"].update(category="service"),
            lambda r:r.update(metadata={}))
        for mutate in mutations:
            candidate = admin_row(unknown=True); mutate(candidate)
            self.payload = admin_page([candidate])
            with self.subTest(mutate=mutate):
                result = await self.read()
                self.assert_unconfirmed(result)
                self.assertEqual((result.scanned_rows, result.reason), (1, "accounting_unavailable"))

    async def test_valid_witness_survives_capped_missing_and_bad_pagination(self):
        variants = ({"total_is_capped": True}, {"total_is_capped": None}, {"page": True},
                    {"total": "bad"}, {"total_pages": -1}, {"page_size": 999})
        for changes in variants:
            self.payload = {**admin_page([admin_row(unknown=True), None]), **changes}
            self.requests.clear()
            with self.subTest(changes=changes):
                result = await self.read()
                self.assertTrue(result.unknown_confirmed)
                self.assertEqual(result.scanned_rows, 1)  # Later malformed row was never examined.
                self.assertEqual(len(self.requests), 1)
                self.assertFalse(result.pagination_complete)

    async def test_witness_after_bad_row_survives_cap_and_later_transport_failure(self):
        self.payload = {**admin_page([None, admin_row(unknown=True)], total=101),
                        "total_is_capped": True}
        async def handler(request):
            if request.query["page"] != "1":
                return web.Response(status=403, text="PRIVATE_BODY")
            return web.json_response(self.payload)
        self.handler = handler
        result = await self.read()
        self.assertTrue(result.unknown_confirmed)
        self.assertEqual(result.scanned_rows, 2)
        self.assertEqual(len(self.requests), 1)

    async def test_absence_known_zero_and_block_flag_never_prove_known_or_free(self):
        for values in ([], [admin_row()], [dict(admin_row(), spend="0", blocked=True)],
                       [{"request_id": "unsigned-auth-denial", "api_key": ASSIGNMENT, "status": "failure"}]):
            self.payload = admin_page(values)
            with self.subTest(values=values):
                result = await self.read()
                self.assert_unconfirmed(result)
                self.assertEqual(result.scanned_rows, len(values))
                self.assertIn(result.reason, ("not_proven", "accounting_unavailable"))

    async def test_shared_native_marker_classification_stays_strict(self):
        for action in ("block", "block_failed"):
            self.payload = admin_page([admin_row(unknown=True, action=action)])
            self.assertTrue((await self.read()).unknown_confirmed)
        mutations = (
            lambda r:r["metadata"]["guardrail_information"][0].update(guardrail_name="other-native-guardrail"),
            lambda r:r["metadata"]["guardrail_information"][0].update(guardrail_action="allow"),
            lambda r:r["metadata"]["guardrail_information"][0].update(violation_categories=None),
            lambda r:r["metadata"]["guardrail_information"].append(
                {"guardrail_name": "owui_budget_usage", "guardrail_action": "block", "violation_categories": None}))
        for mutate in mutations:
            candidate = admin_row(unknown=True); mutate(candidate)
            self.payload = admin_page([candidate])
            with self.subTest(mutate=mutate): self.assert_unconfirmed(await self.read())

    async def test_exact_native_v2_query_is_explicit_latest_first_observation_not_month(self):
        await self.read()
        self.assertEqual(self.requests, [("GET", {"user_id": USER, "api_key": ASSIGNMENT, "model_group": "alias-a",
            "start_date": "1970-01-01 00:00:00", "end_date": "2026-11-08 12:00:00", "page_size": "100",
            "sort_by": "startTime", "sort_order": "desc", "group_by_session": "false", "page": "1"},
            "Bearer synthetic-admin-only-key")])

    async def test_later_page_witness_survives_prior_unbound_rows_and_large_retained_history(self):
        async def handler(request):
            number = int(request.query["page"])
            values = [{"request_id": f"unbound-{i}"} for i in range(100)] if number == 1 else [
                admin_row("later-unknown", unknown=True)] + [admin_row(f"known-{i}") for i in range(99)]
            return web.json_response(admin_page(values, number=number, total=10001))
        self.handler = handler
        result = await self.read(max_pages=2)
        self.assertTrue(result.unknown_confirmed)
        self.assertEqual(result.scanned_rows, 101)
        self.assertEqual([r[1]["page"] for r in self.requests], ["1", "2"])
        self.assertFalse(result.pagination_complete)

    async def test_page_budget_retention_and_incomplete_scan_leave_presence_unconfirmed(self):
        async def handler(request):
            number = int(request.query["page"])
            return web.json_response(admin_page([admin_row(f"p{number}-{i}") for i in range(100)],
                                                number=number, total=10001))
        self.handler = handler
        result = await self.read(max_pages=2)
        self.assert_unconfirmed(result)
        self.assertEqual((result.scanned_rows, result.reason), (200, "incomplete_pagination"))
        self.assertEqual(len(self.requests), 2)
        self.handler = None
        for payload in (dict(admin_page([admin_row()]), total_is_capped=True),
                        dict(admin_page([admin_row()]), total=2),
                        dict(admin_page([admin_row()]), total_is_capped=None),
                        {"data": None}, admin_page([])):
            self.payload = payload
            with self.subTest(payload=payload): self.assert_unconfirmed(await self.read())

    async def test_data_iteration_is_bounded_even_if_native_page_length_is_bad(self):
        self.payload = admin_page([admin_row(f"known-{i}") for i in range(100)] +
                                  [admin_row("beyond-page-bound", unknown=True)])
        result = await self.read()
        self.assert_unconfirmed(result)
        self.assertEqual(result.scanned_rows, 100)
        self.payload["data"][99] = admin_row("within-bound", unknown=True)
        result = await self.read()
        self.assertTrue(result.unknown_confirmed)
        self.assertEqual(result.scanned_rows, 100)

    async def test_bad_http_json_size_and_partial_deadline_never_confirm_presence(self):
        async def redirect(request): raise web.HTTPFound("http://foreign.invalid")
        async def forbidden(request): return web.Response(status=403, text="synthetic-admin-only-key PRIVATE_BODY")
        async def bad_json(request): return web.Response(body=b"not-json")
        async def oversized(request): return web.Response(body=b"x" * (cost.MAX_PAGE_BYTES+1))
        for handler in (redirect, forbidden, bad_json, oversized):
            self.handler = handler
            with self.subTest(handler=handler):
                result = await self.read()
                self.assert_unconfirmed(result)
                self.assertEqual(result.scanned_rows, 0)
                self.assertNotIn("PRIVATE_BODY", repr(result))
                self.assertNotIn("synthetic-admin", repr(result))
        async def partial(request):
            number = int(request.query["page"])
            if number == 2: await asyncio.sleep(.1)
            return web.json_response(admin_page([admin_row(f"p{i}") for i in range(100)], number=number, total=200))
        self.handler = partial; self.requests.clear()
        result = await self.read(timeout_seconds=.03)
        self.assert_unconfirmed(result)
        self.assertEqual((result.scanned_rows, result.reason), (100, "spend_api_unavailable"))
        self.assertEqual(len(self.requests), 2)

    async def test_invalid_server_inputs_fail_before_http_without_guessing_or_truncating(self):
        cases = ({"observation_start": OBSERVATION_START.replace(tzinfo=None)},
            {"observation_end": OBSERVATION_END.replace(microsecond=1)},
            {"observation_start": OBSERVATION_END},
            {"observation_start": OBSERVATION_START.astimezone(timezone(timedelta(hours=3)))},
            {"assignment_hash": "sk-not-an-assignment-hash"}, {"user_id": "invented"},
            {"model": ""}, {"admin_key": ""}, {"timeout_seconds": float("inf")}, {"max_pages": 0})
        for values in cases:
            self.requests.clear()
            with self.subTest(values=values), self.assertRaises(cost.CostReadError): await self.read(**values)
            self.assertEqual(self.requests, [])

    async def test_historical_presence_is_independent_of_native_money_projection(self):
        self.payload = admin_page([admin_row("known"), admin_row("unknown", unknown=True)])
        self.assertTrue((await self.read()).unknown_confirmed)
        snapshot = await cost.read_cost_snapshot(self.session, base_url="http://native-fixture.invalid", read_key="private-read-key",
            user_id=USER, root_chat_id=CHAT, root_answer_id=ANSWER, observed_request_ids=["known"])
        self.assertEqual(snapshot.chat.spend, Decimal("0.40"))


class AdminOverviewTests(unittest.IsolatedAsyncioTestCase):
    def test_sdk_literal_financial_code_without_prose_or_executing_text(self):
        error = {'llm_provider': 'openai', 'error_message':
                 "RateLimitError: Error code: 429 - {'error': {'code': 'credit_balance_exhausted'}}"}
        self.assertTrue(cost._financial_refusal({'error_information': error}))
        for body in ("{'error': {'message': 'insufficient_quota', 'code': 'rate_limit_exceeded'}}",
                     "__import__('os').system('invalid')", "{'error': {'code': '429'}}"):
            self.assertFalse(cost._financial_refusal({'error_information': {**error, 'error_message': body}}))

    async def asyncSetUp(self):
        self.identity = "a" * 64
        self.info = {"id": self.identity, "owui_billing_account_id": "corporate-provider",
                     "owui_billing_immutable_deployment_id": True,
                     "input_cost_per_token": "0.000001", "output_cost_per_token": "0.000002",
                     "cache_read_input_token_cost": "0.0000001"}
        self.rows, self.requests, self.extra_models = [], [], []
        self.log_payload = None
        self.fail_page = None
        self.source = {"source": "remote", "loaded_at": datetime.now(timezone.utc).isoformat(),
                       "url": "https://private-source.invalid/?token=do-not-project"}
        app = web.Application()
        app.router.add_get("/{tail:.*}", self.serve)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        self.session = ClientSession()

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def serve(self, request):
        self.requests.append((request.path, dict(request.query), request.headers.get("Authorization")))
        if request.path == "/model/info":
            return web.json_response({"data": [{"model_name": "alias-a", "model_info": self.info,
                "litellm_params": {"api_key": "private-upstream-key", "api_base": "https://private.invalid"}}] + self.extra_models})
        if request.path == "/model/cost_map/source":
            return web.json_response(self.source)
        if request.path == cost.ADMIN_ROUTE:
            number = int(request.query["page"])
            if number == self.fail_page:
                return web.Response(status=503)
            return web.json_response(self.log_payload or page(self.rows[(number - 1) * 100:number * 100],
                                                            number=number, total=len(self.rows)))
        return web.Response(status=500)

    def event(self, kind, minute=0, **changes):
        raw = row(f"event-{minute}")
        begin = datetime.now(timezone.utc) - timedelta(hours=1) + timedelta(minutes=minute)
        raw.update(model_id=self.identity, cache_hit="False", startTime=begin.isoformat(),
                   endTime=(begin + timedelta(seconds=1)).isoformat())
        raw["metadata"].update(attempted_fallbacks=0)
        if kind == "financial_refusal":
            raw["status"] = "failure"
            raw["metadata"]["error_information"] = {"llm_provider": "openai", "error_code": "429",
                "error_message": 'RateLimitError: provider - {"error":{"code":"insufficient_quota","message":"private-error"}}'}
        raw.update(changes)
        return raw

    async def read(self, snapshots=None):
        return await cost.read_admin_overview(self.session, base_url=self.base, admin_key="private-admin",
                                             models={"alias-a": "Friendly model"}, configsnapshots=snapshots or {})

    async def test_actual_later_paid_same_route_clears_and_preserves_only_safe_fields(self):
        self.rows = [self.event("success", 2), self.event("financial_refusal")]
        self.rows[0]["metadata"]["spend_logs_metadata"]["owui_billed_token_rates"] = {
            "availability": "available", "rates": {"input_cost_per_token": "0.0000005",
                                                      "output_cost_per_token": "0.000002"}}
        snapshot = {"amount": "12.50", "currency": "EUR", "observed_at": "2026-11-11T10:00:00Z",
                    "actor": USER, "source": "manual", "revision": "stored-revision"}
        result = await self.read({"corporate-provider": snapshot})
        self.assertEqual(result["accounts"][0]["status"], "success")
        self.assertEqual(result["accounts"][0]["balance"]["amount"], "12.50")
        self.assertRegex(result["accounts"][0]["revision"], r"^[0-9a-f]{64}$")
        self.assertEqual(result["prices"][0]["input_per_million"], "1.000000")
        self.assertTrue(result["prices"][0]["changed"])
        self.assertEqual(result["prices"][0]["as_of"], self.source['loaded_at'])
        for secret in ("private-upstream-key", "private-error", "do-not-project", "private-admin", "private.invalid"):
            self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(self.requests[-1][1]["model_id"], self.identity)
        self.assertTrue(all(request[2] == "Bearer private-admin" for request in self.requests))

    async def test_new_price_row_does_not_hide_pre_reload_price_change(self):
        self.source['loaded_at'] = (datetime.now(timezone.utc) - timedelta(minutes=59)).isoformat()
        self.rows = [self.event('success', 2), self.event('success', 0)]
        for row, rate in zip(self.rows, ('0.000001', '0.0000005')):
            row['metadata']['spend_logs_metadata']['owui_billed_token_rates'] = {
                'availability': 'available', 'rates': {
                    'input_cost_per_token': rate, 'output_cost_per_token': '0.000002'}}
        self.assertTrue((await self.read())['prices'][0]['changed'])

    async def test_cached_fallback_wrong_route_and_overlapping_success_never_clear(self):
        for change in ({"cache_hit": "True"}, {"model_id": "other-route"}, {"spend": "0"},
                       {"startTime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}):
            with self.subTest(change=change):
                self.rows = [self.event("success", 2, **change), self.event("financial_refusal")]
                self.assertEqual((await self.read())["accounts"][0]["status"], "financial_refusal")
        for fallback in (1, None, False):
            self.rows = [self.event("success", 2), self.event("financial_refusal")]
            self.rows[0]["metadata"]["attempted_fallbacks"] = fallback
            self.assertEqual((await self.read())["accounts"][0]["status"], "financial_refusal")

    async def test_later_native_paid_success_recovers_independently_of_token_telemetry(self):
        self.rows = [self.event("success", 2, total_tokens=None, prompt_tokens=None, completion_tokens=0),
                     self.event("financial_refusal")]
        self.assertEqual((await self.read())["accounts"][0]["status"], "success")

    async def test_generic_429_native_budget_and_reflected_prompt_are_not_financial_evidence(self):
        for message in ('too many requests', '{"error":{"code":"rate_limit_exceeded"}}',
                        '{"error":{"message":"insufficient_quota"}}',
                        '{"input":{"error":{"code":"insufficient_quota"}}}', 'budget exceeded'):
            self.rows = [self.event("financial_refusal")]
            self.rows[0]["metadata"]["error_information"]["error_message"] = message
            self.assertEqual((await self.read())["accounts"][0]["status"], "unknown")

    async def test_native_payment_required_without_structured_body_and_generic_denials(self):
        # Actual second-run shape: failure + selected deployment + cacheFalse,
        # APIError402 + provider, human-only SDK text and native router suffix.
        for code, expected in (("402", "financial_refusal"), (402, "financial_refusal"),
                               ("429", "unknown"), (429, "unknown"), ("422", "unknown"), (True, "unknown")):
            self.rows = [self.event("financial_refusal")]
            info = self.rows[0]["metadata"]["error_information"]
            info.update(error_class="APIError", error_code=code,
                error_message="litellm.APIError: OpenAIException - Payment Required\n\nLiteLLM: model group 'goal584-b' failed. No fallback was attempted.")
            self.assertEqual((await self.read())["accounts"][0]["status"], expected)
        info.update(error_code="402", llm_provider="")
        self.assertEqual((await self.read())["accounts"][0]["status"], "unknown")

    async def test_sdk_python_error_literal_survives_native_router_suffix(self):
        # Replayed real SDK402 repr + pinned format_no_fallback_group_message.
        suffix = ("\n\nLiteLLM: model group 'goal584-b' failed with the error above and no fallback model group was found "
                  "for it, so the request was not retried on another model. No fallbacks are configured."
                  " Add a fallbacks entry for that model group (Router fallbacks or proxy router_settings.fallbacks)"
                  " to retry on another model.")
        for code, expected in (("payment_required", "financial_refusal"), ("rate_limit_exceeded", "unknown")):
            for tail in ("", suffix):
                self.rows = [self.event("financial_refusal")]
                info = self.rows[0]["metadata"]["error_information"]
                info["error_message"] = ("litellm.APIError: OpenAIException - Error code: 402 - "
                    + repr({"error": {"message": "Controlled synthetic payment required", "type": code, "code": code},
                            "id": "synthetic-response"}) + tail)
                self.assertEqual((await self.read())["accounts"][0]["status"], expected)
        info["error_message"] = "litellm.APIError: {'error': {'code': 'payment_required'}} arbitrary unrelated tail"
        self.assertEqual((await self.read())["accounts"][0]["status"], "unknown")

    async def test_credential_change_and_explicit_mutable_ids_cannot_erase_refusal(self):
        self.info["id"] = self.identity = "explicit-deployment"
        self.info.pop("owui_billing_immutable_deployment_id")
        self.rows = [self.event("success", 2), self.event("financial_refusal")]
        self.assertEqual((await self.read())["accounts"][0]["status"], "financial_refusal")
        self.info["owui_billing_immutable_deployment_id"] = True
        self.assertEqual((await self.read())["accounts"][0]["status"], "success")

    async def test_paid_other_model_recovers_only_explicit_same_protected_account(self):
        second = {**self.info, "id": "b" * 64}
        self.extra_models = [{"model_name": "alias-b", "model_info": second}]
        self.rows = [self.event("success", 2, model_id=second["id"]), self.event("financial_refusal")]
        async def read():
            return await cost.read_admin_overview(self.session, base_url=self.base, admin_key="private-admin",
                models={"alias-a": "First model", "alias-b": "Second model"}, configsnapshots={})
        result = await read()
        self.assertEqual(len(result["accounts"]), 1)
        self.assertEqual(result["accounts"][0]["status"], "success")
        second["owui_billing_account_id"] = "different-account"
        result = await read()
        self.assertEqual(next(a for a in result["accounts"] if a["id"] == "corporate-provider")["status"], "financial_refusal")

    async def test_truncated_or_duplicate_native_scan_never_announces_recovery(self):
        self.rows = [self.event("success", 2)]
        self.log_payload = page(self.rows * 100, total=300)
        result = await self.read()
        self.assertFalse(result["complete"])
        self.assertEqual(result["accounts"][0]["status"], "unknown")
        self.log_payload = None
        self.rows = [self.event("success", index) for index in range(300)]
        result = await self.read()
        self.assertFalse(result["complete"])
        self.assertEqual(result["accounts"][0]["status"], "unknown")
        self.assertEqual([request[1]["page"] for request in self.requests if request[0] == cost.ADMIN_ROUTE][-2:], ["1", "2"])

    async def test_absent_rates_or_financial_rows_remain_unknown(self):
        self.info.pop("input_cost_per_token")
        result = await self.read()
        self.assertIsNone(result["prices"][0]["input_per_million"])
        self.assertFalse(result["prices"][0]["changed"])
        self.assertEqual(result["accounts"][0]["status"], "unknown")
        self.assertIsNone(result["accounts"][0]["balance"])

    async def test_bounded_scan_keeps_observed_refusal_until_qualified_later_success(self):
        refusal = self.event("financial_refusal")
        self.rows = [refusal] + [self.event("success", -index - 1) for index in range(250)]
        result = await self.read()
        self.assertFalse(result["complete"])
        self.assertEqual(result["accounts"][0]["status"], "financial_refusal")
        self.assertEqual(result["accounts"][0]["event_at"], refusal["endTime"])
        self.fail_page = 2
        result = await self.read()
        self.assertFalse(result["complete"])
        self.assertEqual(result["accounts"][0]["status"], "financial_refusal")
        self.assertEqual(result["accounts"][0]["event_at"], refusal["endTime"])
        self.rows.insert(0, self.event("success", 2))
        result = await self.read()
        self.assertFalse(result["complete"])
        self.assertEqual(result["accounts"][0]["status"], "unknown")
        self.assertIsNone(result["accounts"][0]["event_at"])


if __name__ == "__main__":
    unittest.main()
