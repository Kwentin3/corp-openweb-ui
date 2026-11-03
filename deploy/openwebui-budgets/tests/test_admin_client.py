"""Real local HTTP management boundary; no LiteLLM or provider requests."""

import asyncio
import copy
from dataclasses import asdict, FrozenInstanceError
from decimal import Decimal
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from aiohttp import ClientSession, web


HERE = Path(__file__).parents[1]


def load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


assignment = load("employee_budget_assignment", HERE / "assignment.py")
contract = load("employee_budget_admin_contract", HERE / "admin_contract.py")
client = load("employee_budget_admin_client_test", HERE / "admin_client.py")
USER = "1296bad0-1491-4c19-b7f2-93e57d812864"
OTHER = "cf931dc8-a099-4471-9173-27b1e296bb59"
MODELS = ("goal584-a", "goal584-b")
OPERATOR = "sk-synthetic-native-management-only"
PRIVATE = "sk-synthetic-employee-secret-never-return"
GATEWAY = "sk-synthetic-shared-gateway-secret"
CAPS = ((MODELS[1], Decimal(".30")), (MODELS[0], Decimal(".50")))


def row(model, *, identifier=None):
    return {"token": identifier or hashlib.sha256(model.encode()).hexdigest(), "user_id": USER,
            "team_id": None, "models": [model], "key_alias": assignment.assignment_alias(USER, model),
            "metadata": {**assignment.assignment_metadata(model), "unrelated_native_private_field": PRIVATE},
            "max_budget": "0.40", "spend": "0.20", "budget_duration": "1mo",
            "budget_reset_at": "2026-12-01T00:00:00Z", "blocked": False}


class AdminClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.user = {"user_id": USER, "user_role": "internal_user", "models": list(MODELS),
                     "max_budget": "0.80", "spend": "0.40", "budget_duration": "1mo",
                     "budget_reset_at": "2026-12-01T00:00:00Z", "unrelated_private_field": PRIVATE}
        self.rows = [row(model) for model in MODELS]
        self.requests, self.handler, self.unexpected_hits = [], None, 0
        app = web.Application()
        for path in ("/user/info", "/key/list", "/user/update", "/key/update", "/user/new", "/key/generate"):
            app.router.add_route("*", path, self.serve)
        app.router.add_route("*", "/unexpected", self.unexpected)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        self.session = ClientSession()
        self.admin = client.BudgetAdminClient(self.session, self.base, key=OPERATOR)

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def unexpected(self, request):
        self.unexpected_hits += 1
        return web.json_response({"unexpected": PRIVATE})

    async def serve(self, request):
        body = await request.json() if request.method == "POST" else None
        self.requests.append((request.method, request.path, dict(request.query), body))
        self.assertEqual(request.headers.get("Authorization"), "Bearer " + OPERATOR)
        if self.handler:
            result = await self.handler(request)
            if result is not None:
                return result
        if request.path == "/user/info":
            self.assertEqual(dict(request.query), {"user_id": USER})
            return web.json_response({"user_info": self.user, "keys": [PRIVATE]})
        if request.path == "/key/list":
            self.assertEqual(request.query.get("user_id"), USER)
            self.assertEqual(request.query.get("substring_matching"), "false")
            self.assertEqual(request.query.get("return_full_object"), "true")
            self.assertEqual(request.query.get("include_team_keys"), "false")
            self.assertEqual(request.query.get("include_created_by_keys"), "false")
            page, size = int(request.query["page"]), int(request.query["size"])
            return web.json_response({"keys": self.rows[(page-1)*size:page*size], "current_page": page,
                                      "total_count": len(self.rows), "total_pages": (len(self.rows)+size-1)//size})
        self.assertEqual(request.method, "POST")
        return web.json_response({"updated": True, "native_private_field": PRIVATE})

    async def read(self):
        return await self.admin.read_employee(USER, MODELS)

    async def inspect(self):
        return await self.admin.inspect_employee(USER, MODELS)

    async def missing_user(self, request):
        if request.path == "/user/info":
            return web.json_response({"detail": "User not found", "private": PRIVATE}, status=404)

    async def bootstrap_boundary(self, request):
        """Emulate only public native row effects; return misleading POST data."""
        if request.path == "/user/info":
            if self.user is None:
                return await self.missing_user(request)
            return web.json_response({"user_info": self.user, "teams": [], "keys": [PRIVATE]})
        if request.path == "/user/new":
            body = await request.json()
            self.user = {"user_id": body["user_id"], "user_role": body["user_role"],
                         "models": body["models"], "teams": [], "team_id": None,
                         "max_budget": body["max_budget"], "spend": 0,
                         "budget_duration": body["budget_duration"], "budget_reset_at": "2099-01-01T00:00:00Z"}
            return web.json_response({"user_id": OTHER, "max_budget": 999, "key": PRIVATE})
        if request.path == "/key/generate":
            body = await request.json()
            model = body["models"][0]
            entry = row(model, identifier=hashlib.sha256(body["key"].encode()).hexdigest())
            entry.update({"models": body["models"], "metadata": body["metadata"], "key_alias": body["key_alias"],
                          "max_budget": body["max_budget"], "spend": 0, "blocked": body["blocked"],
                          "budget_duration": body["budget_duration"], "budget_reset_at": self.user["budget_reset_at"],
                          "expires": None, "budget_id": None, "allowed_routes": body["allowed_routes"]})
            self.rows.append(entry)
            return web.json_response({"key": PRIVATE, "max_budget": 999, "token_id": "wrong"})

    def start_absent(self):
        self.user, self.rows, self.handler = None, [], self.bootstrap_boundary

    async def initialize(self, *, before_write=None, gateway_secret=GATEWAY, caps=CAPS, total=Decimal(".80")):
        async def permit():
            pass
        return await self.admin.initialize_employee(USER, caps, total, gateway_secret,
                                                     before_write=before_write or permit)

    async def test_inspection_ready_reuses_exact_read_budget_without_private_data(self):
        expected = await self.read()
        self.requests.clear()
        result = await self.inspect()
        self.assertEqual(result.kind, "ready")
        self.assertEqual(result.user_id, USER)
        self.assertEqual(result.allowed_wire_models, MODELS)
        self.assertEqual(result.employee_budget, expected)
        self.assertIsNone(result.code)
        self.assertNotIn(PRIVATE, repr(asdict(result)))
        self.assertNotIn(OPERATOR, repr(asdict(result)))
        self.assertEqual([entry[:2] for entry in self.requests], [("GET", "/user/info"), ("GET", "/key/list")])
        with self.assertRaises(FrozenInstanceError):
            result.kind = "absent"

    async def test_inspection_absent_needs_user_404_and_complete_exact_empty_keys(self):
        self.handler, self.rows = self.missing_user, []
        result = await self.inspect()
        self.assertEqual(result.kind, "absent")
        self.assertEqual(result.code, "missing_native_user")
        self.assertIsNone(result.employee_budget)
        self.assertEqual([entry[:2] for entry in self.requests], [("GET", "/user/info"), ("GET", "/key/list")])
        self.assertNotIn(PRIVATE, repr(asdict(result)))
        self.requests.clear()
        with self.assertRaises(contract.BudgetAdminError) as caught:
            await self.read()
        self.assertEqual(caught.exception.code, "native_http_404")
        self.assertEqual(len(self.requests), 1)

    async def test_inspection_existing_user_no_keys_or_subset_is_incomplete_never_absent(self):
        for rows in [[], [row(MODELS[0])], [{"token": "c"*64, "user_id": USER,
                                           "key_alias": "other-application", "metadata": {}}]]:
            self.rows = rows
            with self.subTest(key_count=len(rows)):
                result = await self.inspect()
                self.assertEqual(result.kind, "incomplete")
                self.assertEqual(result.code, "missing_assignment")
                self.assertIsNone(result.employee_budget)
                with self.assertRaises(contract.BudgetAdminError) as caught:
                    await self.read()
                self.assertEqual(caught.exception.code, "missing_assignment")

    async def test_inspection_404_with_canonical_or_unrelated_keys_is_orphan_conflict(self):
        self.handler = self.missing_user
        for rows in [[row(MODELS[0])], [{"token": "c"*64, "user_id": USER,
                                         "key_alias": "other-application", "metadata": {}}]]:
            self.rows = rows
            with self.subTest(key_count=len(rows)):
                result = await self.inspect()
                self.assertEqual(result.kind, "conflict")
                self.assertEqual(result.code, "orphan_assignments")
                self.assertIsNone(result.employee_budget)

    async def test_inspection_validates_all_pages_before_ready_or_incomplete(self):
        self.rows = [row(MODELS[0])]
        for number in range(100):
            self.rows.append({"token": hashlib.sha256(str(number).encode()).hexdigest(),
                              "user_id": USER, "key_alias": "other-application", "metadata": {}})
        for missing in [True, False]:
            if not missing:
                self.rows.append(row(MODELS[1]))
            self.requests.clear()
            result = await self.inspect()
            self.assertEqual(result.kind, "incomplete" if missing else "ready")
            self.assertEqual([entry[2]["page"] for entry in self.requests if entry[1] == "/key/list"], ["1", "2"])
        self.rows[-1]["metadata"] = {}
        result = await self.inspect()
        self.assertEqual((result.kind, result.code), ("conflict", "invalid_assignment"))

    async def test_inspection_data_conflicts_never_become_missing_or_zero(self):
        mutations = [({"user_role": "proxy_admin"}, None, "invalid_employee"),
                     ({"user_id": OTHER}, None, "invalid_employee"),
                     ({"spend": None}, [], "invalid_native_amount"),
                     ({"max_budget": "NaN"}, [], "invalid_native_amount"),
                     ({"budget_reset_at": ""}, [], "invalid_native_response")]
        for user_mutation, rows, code in mutations:
            original = self.user.copy()
            self.user.update(user_mutation)
            self.rows = [row(model) for model in MODELS] if rows is None else rows
            with self.subTest(code=code):
                result = await self.inspect()
                self.assertEqual((result.kind, result.code), ("conflict", code))
                self.assertIsNone(result.employee_budget)
            self.user = original
        for mutation, code in [({"team_id": "team"}, "invalid_assignment"),
                               ({"metadata": {}}, "invalid_assignment"),
                               ({"models": [*MODELS]}, "invalid_assignment"),
                               ({"key_alias": []}, "invalid_assignment"),
                               ({"token": PRIVATE}, "invalid_key_hash"),
                               ({"user_id": OTHER}, "foreign_assignment")]:
            self.rows = [row(model) for model in MODELS]
            self.rows[0].update(mutation)
            with self.subTest(code=code):
                result = await self.inspect()
                self.assertEqual((result.kind, result.code), ("conflict", code))
                self.assertIsNone(result.employee_budget)
                self.assertNotIn(PRIVATE, repr(asdict(result)))
        for rows, code in [([row(MODELS[0]), row(MODELS[0])], "duplicate_key"),
                           ([row(MODELS[0]), row(MODELS[0], identifier="a"*64)], "duplicate_assignment"),
                           ([row("unsupported")], "unsupported_assignment")]:
            self.rows = rows
            result = await self.inspect()
            self.assertEqual((result.kind, result.code), ("conflict", code))

    async def test_inspection_auth_db_transport_or_key_404_raise_never_absence(self):
        self.rows = []
        for route in ["/user/info", "/key/list"]:
            for status in [401, 403, 429, 500, 503, 404]:
                if route == "/user/info" and status == 404:
                    continue
                async def failure(request):
                    if request.path == route:
                        return web.Response(status=status, text=PRIVATE)
                    return await self.missing_user(request)
                self.handler = failure
                with self.subTest(route=route, status=status), self.assertRaises(contract.BudgetAdminError) as caught:
                    await self.inspect()
                self.assertEqual(caught.exception.code, "native_http_" + str(status))
                self.assertNotIn(PRIVATE, str(caught.exception))
                self.assertNotIn(OPERATOR, str(caught.exception))
        async def invalid_json(request):
            if request.path == "/key/list":
                return web.Response(text=PRIVATE)
            return await self.missing_user(request)
        self.handler = invalid_json
        with self.assertRaises(contract.BudgetAdminError) as caught:
            await self.inspect()
        self.assertEqual(caught.exception.code, "native_transport")
        async def delayed(request):
            await asyncio.sleep(.1)
            return web.json_response({})
        self.handler = delayed
        with patch.object(client, "READ_TIMEOUT", .02), self.assertRaises(contract.BudgetAdminError) as caught:
            await self.inspect()
        self.assertEqual(caught.exception.code, "native_transport")

    async def test_inspection_absence_does_not_hide_malformed_or_incomplete_key_pages(self):
        for malformed in [{"keys": [], "total_count": 0, "total_pages": 1, "current_page": 1},
                          {"keys": [], "total_count": 1, "total_pages": 1, "current_page": 1},
                          {"keys": [], "total_count": 0, "total_pages": 0, "current_page": True},
                          {"keys": [], "total_count": 10001, "total_pages": 101, "current_page": 1}]:
            async def bad_page(request):
                if request.path == "/key/list":
                    return web.json_response(malformed)
                return await self.missing_user(request)
            self.handler = bad_page
            with self.subTest(payload=malformed), self.assertRaises(contract.BudgetAdminError) as caught:
                await self.inspect()
            self.assertEqual(caught.exception.code, "incomplete_pagination")
        self.rows = [{"token": hashlib.sha256(str(number).encode()).hexdigest(),
                      "user_id": USER, "key_alias": "other", "metadata": {}} for number in range(101)]
        async def changed_page(request):
            if request.path == "/key/list" and request.query["page"] == "2":
                return web.json_response({"keys": self.rows[100:], "total_count": 102,
                                          "total_pages": 2, "current_page": 2})
            return await self.missing_user(request)
        self.handler = changed_page
        with self.assertRaises(contract.BudgetAdminError) as caught:
            await self.inspect()
        self.assertEqual(caught.exception.code, "incomplete_pagination")

    async def test_initialization_creates_explicit_user_and_sorted_deterministic_keys_then_reads_actual_state(self):
        self.start_absent()
        guarded_prefixes = []
        async def guard():
            guarded_prefixes.append(tuple(entry[:2] for entry in self.requests))
        result = await self.initialize(before_write=guard)
        self.assertEqual(result.max_budget, Decimal(".80"))
        self.assertEqual(result.spend, 0)
        self.assertEqual(tuple(entry.model for entry in result.models), tuple(model for model, _ in CAPS))
        posts = [entry for entry in self.requests if entry[0] == "POST"]
        self.assertEqual([entry[1] for entry in posts], ["/user/new", "/key/generate", "/key/generate"])
        self.assertEqual(len(guarded_prefixes), 3)
        for number, prefix in enumerate(guarded_prefixes):
            self.assertEqual(sum(method == "POST" for method, _ in prefix), number)
        self.assertEqual(posts[0][3], {"user_id": USER, "user_role": "internal_user", "models": [model for model, _ in CAPS],
                                     "max_budget": .8, "budget_duration": "1mo", "spend": 0,
                                     "auto_create_key": False, "send_invite_email": False, "teams": []})
        for post, model in zip(posts[1:], sorted(MODELS)):
            body = post[3]
            identity = json.dumps([USER, model], ensure_ascii=True, separators=(",", ":")).encode()
            expected = "sk-" + hmac.new(GATEWAY.encode(), b"employee-budget-bootstrap-key-v1\0" + identity,
                                         hashlib.sha256).hexdigest()
            self.assertEqual(body, {"key": expected, "user_id": USER, "models": [model],
                                    "key_alias": assignment.assignment_alias(USER, model),
                                    "metadata": assignment.assignment_metadata(model),
                                    "max_budget": float(dict(CAPS)[model]), "budget_duration": "1mo", "spend": 0,
                                    "blocked": False, "allowed_routes": ["llm_api_routes"], "duration": None,
                                    "team_id": None, "budget_id": None, "send_invite_email": False})
            actual = next(entry for entry in result.models if entry.model == model)
            self.assertEqual(actual.key_hash, hashlib.sha256(expected.encode()).hexdigest())
            self.assertEqual(actual.max_budget, dict(CAPS)[model])
            self.assertNotIn(expected, repr(asdict(result)))
        self.assertNotIn(GATEWAY, repr(asdict(result)))
        self.assertNotIn(PRIVATE, repr(asdict(result)))
        self.assertEqual((await self.inspect()).kind, "ready")

    async def test_initialization_existing_ready_or_partial_or_orphan_state_does_not_write(self):
        for kind in ["ready", "incomplete", "orphan"]:
            self.requests.clear()
            self.user = {"user_id": USER, "user_role": "internal_user", "max_budget": ".8", "spend": "0",
                         "budget_duration": "1mo", "budget_reset_at": "2099-01-01T00:00:00Z"}
            self.rows = [row(model) for model in MODELS] if kind == "ready" else []
            self.handler = None
            if kind == "orphan":
                self.handler, self.rows = self.missing_user, [row(MODELS[0])]
            with self.subTest(kind=kind), self.assertRaises(contract.BudgetAdminError) as caught:
                await self.initialize()
            self.assertEqual(caught.exception.code, "initialization_requires_absence")
            self.assertTrue(all(entry[0] == "GET" for entry in self.requests))

    async def test_initialization_rechecks_guard_before_every_individual_post_and_stops_with_honest_prefix(self):
        for deny_number in [0, 1, 2]:
            self.start_absent()
            self.requests.clear()
            calls = 0
            async def guard():
                nonlocal calls
                if calls == deny_number:
                    raise contract.BudgetAdminError("admin_revoked")
                calls += 1
            with self.subTest(deny_number=deny_number), self.assertRaises(contract.BudgetAdminError) as caught:
                await self.initialize(before_write=guard)
            self.assertEqual(caught.exception.code, "admin_revoked")
            self.assertEqual(len([entry for entry in self.requests if entry[0] == "POST"]), deny_number)
            self.assertEqual(self.user is None, deny_number == 0)
            self.assertEqual(len(self.rows), max(0, deny_number-1))
            self.assertEqual((await self.inspect()).kind, "absent" if deny_number == 0 else "incomplete")

    async def test_initialization_actual_user_drift_blocks_all_key_creation_even_with_successful_post(self):
        for mutation in [{"max_budget": .9}, {"spend": .1}, {"models": [MODELS[0]]},
                         {"user_role": "proxy_admin"}, {"team_id": "team"}, {"teams": ["team"]},
                         {"budget_duration": "30d"}, {"budget_reset_at": "2000-01-01T00:00:00Z"},
                         {"budget_reset_at": "2099-01-01T00:00:00"}]:
            self.start_absent()
            self.requests.clear()
            async def changed(request):
                response = await self.bootstrap_boundary(request)
                if request.path == "/user/new":
                    self.user.update(mutation)
                return response
            self.handler = changed
            with self.subTest(mutation=mutation), self.assertRaises(contract.BudgetAdminError):
                await self.initialize()
            self.assertEqual([entry[1] for entry in self.requests if entry[0] == "POST"], ["/user/new"])
            self.assertEqual(self.rows, [])

    async def test_initialization_actual_key_drift_blocks_next_key_without_repair(self):
        for mutation in [{"max_budget": .6}, {"spend": .1}, {"token": "a"*64}, {"blocked": True},
                         {"budget_duration": "30d"}, {"budget_reset_at": "2099-02-01T00:00:00Z"},
                         {"expires": "2099-02-01T00:00:00Z"}, {"budget_id": "tier"},
                         {"allowed_routes": []}, {"allowed_routes": ["management_routes"]}]:
            self.start_absent()
            self.requests.clear()
            async def changed(request):
                response = await self.bootstrap_boundary(request)
                if request.path == "/key/generate":
                    self.rows[-1].update(mutation)
                return response
            self.handler = changed
            with self.subTest(mutation=mutation), self.assertRaises(contract.BudgetAdminError) as caught:
                await self.initialize()
            self.assertEqual(caught.exception.code, "initialization_unconfirmed")
            self.assertEqual([entry[1] for entry in self.requests if entry[0] == "POST"], ["/user/new", "/key/generate"])
            self.assertEqual(len(self.rows), 1)

    async def test_initialization_unexpected_or_duplicate_actual_key_rows_fail_closed(self):
        for foreign in [False, True]:
            self.start_absent()
            self.requests.clear()
            async def changed(request):
                response = await self.bootstrap_boundary(request)
                if request.path == "/key/generate":
                    extra = copy.deepcopy(self.rows[-1])
                    extra["token"] = "a"*64
                    if foreign:
                        extra["key_alias"], extra["metadata"] = "other-application", {}
                    self.rows.append(extra)
                return response
            self.handler = changed
            with self.subTest(foreign=foreign), self.assertRaises(contract.BudgetAdminError):
                await self.initialize()
            self.assertEqual([entry[1] for entry in self.requests if entry[0] == "POST"], ["/user/new", "/key/generate"])
            self.assertEqual(len(self.rows), 2)

    async def test_initialization_native_failure_is_safe_and_has_no_automatic_retry(self):
        for failed_route, status in [("/user/new", 409), ("/key/generate", 400), ("/key/generate", 503)]:
            self.start_absent()
            self.requests.clear()
            async def failed(request):
                if request.path == failed_route:
                    return web.Response(status=status, text=PRIVATE)
                return await self.bootstrap_boundary(request)
            self.handler = failed
            with self.subTest(route=failed_route, status=status), self.assertRaises(contract.BudgetAdminError) as caught:
                await self.initialize()
            self.assertEqual(caught.exception.code, "native_http_" + str(status))
            self.assertNotIn(PRIVATE, str(caught.exception))
            self.assertNotIn(GATEWAY, str(caught.exception))
            self.assertEqual(len([entry for entry in self.requests if entry[1] == failed_route]), 1)
            self.assertEqual(self.user is None, failed_route == "/user/new")
            self.assertEqual(self.rows, [])

    async def test_initialization_final_ready_read_still_verifies_actual_user_cap(self):
        self.start_absent()
        async def changed(request):
            if request.path == "/user/info" and len(self.rows) == 2:
                self.user["max_budget"] = .9
            return await self.bootstrap_boundary(request)
        self.handler = changed
        with self.assertRaises(contract.BudgetAdminError) as caught:
            await self.initialize()
        self.assertEqual(caught.exception.code, "initialization_unconfirmed")
        self.assertEqual(len([entry for entry in self.requests if entry[0] == "POST"]), 3)
        self.assertEqual(len(self.rows), 2)

    async def test_initialization_rejects_precision_or_invalid_configuration_before_network(self):
        for kwargs in [{"total": Decimal(".8000000000000000000001")},
                       {"caps": ((MODELS[0], Decimal(".50000000000000000001")),)},
                       {"gateway_secret": ""}, {"caps": ()},
                       {"caps": ((MODELS[0], Decimal(".4")), (MODELS[0], Decimal(".4")))}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(contract.BudgetAdminError):
                await self.initialize(**kwargs)
        self.assertEqual(self.requests, [])

    async def test_typed_native_read_discards_private_fields_and_preserves_decimal_none(self):
        self.rows[0]["max_budget"] = None
        self.rows[0]["blocked"] = None
        self.rows[1]["metadata"] = json.dumps(self.rows[1]["metadata"])
        dto = await self.read()
        self.assertIsInstance(dto, contract.EmployeeBudget)
        self.assertEqual(dto.spend, Decimal("0.40"))
        self.assertEqual(tuple(entry.model for entry in dto.models), MODELS)
        self.assertIsNone(dto.models[0].max_budget)
        self.assertIsNone(dto.models[0].blocked)
        self.assertEqual(dto.models[1].max_budget, Decimal("0.40"))
        self.assertNotIn(PRIVATE, repr(asdict(dto)))
        self.assertEqual(len(self.requests), 2)

    async def test_all_pages_native_hashes_and_unrelated_keys_have_one_read_owner(self):
        for number in range(101):
            self.rows.append({"token": hashlib.sha256(str(number).encode()).hexdigest(),
                              "user_id": USER, "key_alias": "other-application", "metadata": {}})
        dto = await self.read()
        self.assertEqual(len(dto.models), 2)
        self.assertEqual([entry[2]["page"] for entry in self.requests if entry[1] == "/key/list"], ["1", "2"])

    async def test_cap_posts_use_hash_and_only_max_budget_including_zero(self):
        key_hash = self.rows[0]["token"]
        await self.admin.set_user_cap(USER, Decimal("1.20"))
        await self.admin.set_model_cap(key_hash, Decimal("0"))
        self.assertEqual(self.requests, [("POST", "/user/update", {}, {"user_id": USER, "max_budget": 1.2}),
                                         ("POST", "/key/update", {}, {"key": key_hash, "max_budget": 0.0})])

    async def test_foreign_user_or_role_fails_before_key_enumeration(self):
        for mutation in [{"user_id": OTHER}, {"user_role": "proxy_admin"}]:
            with self.subTest(mutation=mutation):
                self.requests.clear()
                original = self.user.copy()
                self.user.update(mutation)
                with self.assertRaises(contract.BudgetAdminError) as caught:
                    await self.read()
                self.assertEqual(caught.exception.code, "invalid_employee")
                self.assertEqual(len(self.requests), 1)
                self.user = original

    async def test_scope_namespace_models_and_required_field_mutations_fail_closed(self):
        mutations = [{"user_id": OTHER}, {"team_id": "team"}, {"models": [*MODELS]},
                     {"metadata": {}}, {"metadata": {"owui_budget_namespace": assignment.ASSIGNMENT_NAMESPACE,
                                                    "owui_budget_model": "unsupported"}},
                     {"blocked": "false"}, {"token": "sk-raw-employee-secret"}, {"spend": "NaN"}]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                original = copy.deepcopy(self.rows)
                self.rows[0].update(mutation)
                with self.assertRaises(contract.BudgetAdminError):
                    await self.read()
                self.rows = original
        self.rows[0].pop("max_budget")
        with self.assertRaises(contract.BudgetAdminError):
            await self.read()

    async def test_duplicate_hash_duplicate_assignment_and_missing_assignment_rejected(self):
        original = copy.deepcopy(self.rows)
        for rows, code in [([*original, copy.deepcopy(original[0])], "duplicate_key"),
                           ([*original, row(MODELS[0], identifier="a"*64)], "duplicate_assignment"),
                           ([original[0]], "missing_assignment")]:
            self.rows = rows
            with self.subTest(code=code), self.assertRaises(contract.BudgetAdminError) as caught:
                await self.read()
            self.assertEqual(caught.exception.code, code)

    async def test_unsupported_canonical_namespace_model_rejected(self):
        self.rows.append(row("not-in-the-caller-models"))
        with self.assertRaises(contract.BudgetAdminError) as caught:
            await self.read()
        self.assertEqual(caught.exception.code, "unsupported_assignment")

    async def test_pagination_missing_changed_or_duplicate_pages_rejected(self):
        for malformed in [{"keys": self.rows, "total_count": 3, "total_pages": 1, "current_page": 1},
                          {"keys": self.rows, "total_count": 2, "total_pages": 1, "current_page": True},
                          {"keys": [], "total_count": 10001, "total_pages": 101, "current_page": 1}]:
            async def override(request):
                return web.json_response(malformed) if request.path == "/key/list" else None
            self.handler = override
            with self.subTest(payload_keys=list(malformed)), self.assertRaises(contract.BudgetAdminError):
                await self.read()
        self.handler = None
        for number in range(100):
            self.rows.append({"token": hashlib.sha256(str(number).encode()).hexdigest(), "user_id": USER,
                              "key_alias": "other", "metadata": {}})
        async def changed(request):
            if request.path == "/key/list" and request.query["page"] == "2":
                return web.json_response({"keys": self.rows[100:], "total_count": 103, "total_pages": 2, "current_page": 2})
        self.handler = changed
        with self.assertRaises(contract.BudgetAdminError) as caught:
            await self.read()
        self.assertEqual(caught.exception.code, "incomplete_pagination")
        async def repeated(request):
            if request.path == "/key/list" and request.query["page"] == "2":
                return web.json_response({"keys": self.rows[:2], "total_count": 102,
                                          "total_pages": 2, "current_page": 2})
        self.handler = repeated
        with self.assertRaises(contract.BudgetAdminError) as caught:
            await self.read()
        self.assertEqual(caught.exception.code, "duplicate_key")

    async def test_http_error_redirect_and_invalid_json_never_expose_bodies_or_follow(self):
        for response, code in [(web.Response(status=403, text=PRIVATE), "native_http_403"),
                               (web.Response(status=302, headers={"Location": self.base + "/unexpected"}, text=PRIVATE), "native_http_302"),
                               (web.Response(status=200, text=PRIVATE), "native_transport")]:
            async def override(request): return response
            self.handler = override
            with self.subTest(code=code), self.assertRaises(contract.BudgetAdminError) as caught:
                await self.read()
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn(PRIVATE, str(caught.exception))
            self.assertNotIn(OPERATOR, str(caught.exception))
        self.assertEqual(self.unexpected_hits, 0)

    async def test_response_and_timeout_bounds_are_real_http_boundaries(self):
        async def huge(request): return web.json_response({"padding": "x" * 4096})
        self.handler = huge
        with patch.object(client, "MAX_BYTES", 1024), self.assertRaises(contract.BudgetAdminError) as caught:
            await self.read()
        self.assertEqual(caught.exception.code, "native_response_too_large")
        async def delayed(request):
            await asyncio.sleep(.1)
            return web.json_response({"unused": True})
        self.handler = delayed
        with patch.object(client, "REQUEST_TIMEOUT", .02), self.assertRaises(contract.BudgetAdminError) as caught:
            await self.read()
        self.assertEqual(caught.exception.code, "native_transport")

    async def test_invalid_inputs_fail_without_network_or_implicit_rounding_policy(self):
        for base in [None, "ftp://example.com", "http://user:password@example.com", "http://127.0.0.1:bad"]:
            with self.subTest(base_type=type(base).__name__), self.assertRaises(contract.BudgetAdminError):
                client.BudgetAdminClient(self.session, base, key=OPERATOR)
        for value in [Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("1e999"), Decimal("1e-999"), .4]:
            with self.subTest(value_type=type(value).__name__), self.assertRaises(contract.BudgetAdminError):
                await self.admin.set_user_cap(USER, value)
        for value in ["sk-raw-secret", "A"*64, "short"]:
            with self.assertRaises(contract.BudgetAdminError):
                await self.admin.set_model_cap(value, Decimal("1"))
        with self.assertRaises(contract.BudgetAdminError):
            await self.admin.read_employee(USER, (MODELS[0], MODELS[0]))
        with self.assertRaises(contract.BudgetAdminError):
            await self.admin.read_employee("not-a-uuid", MODELS)
        for user_id, models in [("not-a-uuid", MODELS), (USER, (MODELS[0], MODELS[0])),
                                (USER, []), (USER, ())]:
            with self.assertRaises(contract.BudgetAdminError):
                await self.admin.inspect_employee(user_id, models)
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
