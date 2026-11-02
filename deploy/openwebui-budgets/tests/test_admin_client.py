"""Real local HTTP management boundary; no LiteLLM or provider requests."""

import asyncio
import copy
from dataclasses import asdict
from decimal import Decimal
import hashlib
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
        for path in ("/user/info", "/key/list", "/user/update", "/key/update"):
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
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
