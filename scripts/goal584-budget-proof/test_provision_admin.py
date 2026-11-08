"""Bounded orchestration rehearsal, not native server/runtime acceptance."""
import ast
import asyncio
import copy
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
from io import StringIO
import os
from pathlib import Path
import stat
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


HERE = Path(__file__).resolve().parent
BUDGETS = HERE.parents[1] / "deploy" / "openwebui-budgets"
sys.path[:0] = [str(HERE), str(BUDGETS)]


def load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


load("employee_budget_assignment", BUDGETS / "assignment.py")
contract = load("employee_budget_admin_contract", BUDGETS / "admin_contract.py")
load("employee_budget_admin_client", BUDGETS / "admin_client.py")
p = load("goal584_provision_admin_under_test", HERE / "provision_admin.py")
import prove_native_budgets as N
IDS = [f"{n:08d}-1111-4111-8111-111111111111" for n in range(1, 7)]


def fixture():
    state = {"admin": {"id": IDS[2]}, "users": [{"id": uid} for uid in IDS[:2]],
             "native_keys": [], "admin_budgetnative_keys": []}
    employees = []
    for i, uid in enumerate(IDS[:3]):
        models = []
        for model in p.MODELS:
            raw = f"sk-synthetic-{i}-{model}"
            record = {"user_id": uid, "model": model, "key": raw,
                      "key_alias": p.assignment_alias(uid, model)}
            state["native_keys" if i < 2 else "admin_budgetnative_keys"].append(record)
            models.append(contract.ModelBudget(model, hashlib.sha256(raw.encode()).hexdigest(),
                          record["key_alias"], Decimal("10" if i < 2 else "500"), Decimal(0),
                          "30d", "2026-12-01T00:00:00Z", False))
        employees.append(contract.EmployeeBudget(uid, Decimal("20" if i < 2 else "1000"),
                          Decimal(0), "30d", "2026-12-01T00:00:00Z", tuple(models)))
    return state, employees


def row(user=IDS[2]):
    scope = dict(schema=1, user_id=user, chat_id=IDS[3], answer_id=IDS[4],
                 root_chat_id=IDS[3], root_answer_id=IDS[4], model=p.MODELS[0],
                 call_id=IDS[5], category="personal")
    return {"request_id": "synthetic-provider-id", "user": user, "session_id": IDS[3],
            "metadata": {"spend_logs_metadata": {"owui_budget": scope}},
            "model_group": p.MODELS[0], "spend": .2, "status": "success",
            "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


class ProvisionAdminTests(unittest.TestCase):
    def test_model_grant_readback_accepts_native_regenerated_rows_and_order(self):
        expected = {"id": p.MODELS[0], "name": "Synthetic", "base_model_id": None,
                    "params": {"max_tokens": 5}, "meta": {"toolIds": ["synthetic-tool"]}, "is_active": True,
                    "access_grants": [{"id": "old-native-row", "resource_type": "model", "resource_id": p.MODELS[0],
                        "created_at": 1, "principal_type": "user", "principal_id": IDS[0], "permission": "read"},
                        {"principal_type": "user", "principal_id": IDS[4], "permission": "read"}]}
        actual = copy.deepcopy(expected)
        actual["access_grants"] = [dict(grant, id="new-native-" + str(index), created_at=2,
            resource_type="model", resource_id=p.MODELS[0]) for index, grant in reversed(list(enumerate(expected["access_grants"])))]
        self.assertEqual(p.model_grant_changes(expected, actual), [])
        self.assertNotEqual(actual, expected)
        for field, value in (("name", "Changed"), ("params", {"max_tokens": 9}),
                             ("meta", {"toolIds": []}), ("is_active", False), ("base_model_id", "other")):
            changed = copy.deepcopy(actual)
            changed[field] = value
            with self.subTest(field=field):
                self.assertEqual(p.model_grant_changes(expected, changed), [field])
        for mutation in (lambda grants: grants.pop(),
                         lambda grants: grants.append(copy.deepcopy(grants[0])),
                         lambda grants: grants[0].update(principal_id=IDS[5]),
                         lambda grants: grants[0].update(permission="write"),
                         lambda grants: grants[0].update(principal_type="group")):
            changed = copy.deepcopy(actual)
            mutation(changed["access_grants"])
            self.assertEqual(p.model_grant_changes(expected, changed), ["access_grants"])

    def test_bootstrap_setup_uses_only_webui_identity_and_native_grants(self):
        state, employees = fixture()
        state["admin"].update(token="synthetic-admin")
        state["role_probe_control"] = {"id": IDS[5]}
        baseline = {"users": p.normalize(employees[:2])["users"], "keys": p.normalize(employees[:2])["keys"],
                    "attributed_spend_logs": [{"request_id": "old-native-row"}]}
        calls, models = [], {model: {"id": model, "access_grants": []} for model in p.MODELS}
        class NativeWebUI:
            def ok(self, method, path, **kwargs):
                calls.append((method, path, copy.deepcopy(kwargs)))
                if path == "/api/v1/auths/add":
                    return {"id": IDS[4], "token": "synthetic-new-session", "role": "user"}
                if path == "/api/v1/models/model/update":
                    models[kwargs["body"]["id"]] = copy.deepcopy(kwargs["body"])
                    return models[kwargs["body"]["id"]]
                raise AssertionError("Bootstrap setup attempted an unexpected API")
            def model(self, token, model):
                return copy.deepcopy(models[model])
            def catalog(self, account):
                self.account = account
        async def absent(actual):
            self.assertEqual(actual["bootstrap_fixture"]["employee"]["id"], IDS[4])
            return {"kind": "absent", "user_id": IDS[4], "code": "missing_native_user"}
        with patch.object(p, "snapshot", return_value=baseline), patch.object(p, "write_private") as saved, \
             patch.object(p, "model_body", side_effect=copy.deepcopy), patch.object(p, "bootstrap_inspection", absent):
            p.bootstrap_setup(NativeWebUI(), state, Path("private-state.json"), Path("not-existing-handoff.json"))
        self.assertEqual(len(state["users"]), 2)
        self.assertEqual(len(state["native_keys"]), 4)
        self.assertEqual(state["bootstrap_fixture"]["stage"], "setup_complete")
        self.assertEqual(state["bootstrap_fixture"]["original_staff"], {key: baseline[key] for key in ("users", "keys")})
        self.assertEqual([path for _, path, _ in calls], ["/api/v1/auths/add", *["/api/v1/models/model/update"] * 2])
        for model in models.values():
            self.assertEqual(model["access_grants"], [{"principal_type": "user", "principal_id": IDS[4], "permission": "read"}])
        handoff = saved.call_args_list[-1].args[1]
        self.assertEqual(set(handoff["user"]), {"id", "email", "password"})
        self.assertNotIn("token", str(handoff))

    def test_bootstrap_snapshot_rejects_existing_staff_drift(self):
        state, employees = fixture()
        state["bootstrap_fixture"] = {"stage": "setup_complete", "employee": {"id": IDS[4]},
            "original_staff": p.normalize(employees[:2]), "original_positive_request_ids": []}
        altered = p.normalize([replace(employees[0], max_budget=Decimal(99)), employees[1]])
        with patch.object(p, "snapshot", return_value=altered):
            with self.assertRaises(p.ProofError):
                p.bootstrap_snapshot(None, state)

    def test_filter_credential_install_preserves_complete_native_configuration(self):
        state = {"admin": {"token": "synthetic-admin-session"}, "cost_reader": {"key": "sk-synthetic-reader"}}
        existing = {"ledger_base_url": "http://proxy:4000", "ledger_read_key": "sk-synthetic-reader",
                    "read_wait_seconds": 8.0, "unrelated_native_config": {"preserve": True}}
        calls = []
        class WebUI:
            def ok(self, method, path, **kwargs):
                calls.append((method, path, copy.deepcopy(kwargs)))
                if method == "POST":
                    existing.clear()
                    existing.update(kwargs["body"])
                return copy.deepcopy(existing)
        with patch.object(p, "read_private", return_value={"operator_token": "sk-synthetic-operator"}):
            p.filter_admin_key(WebUI(), state, install=True)
            p.filter_admin_key(WebUI(), state)
        posted = next(kwargs["body"] for method, _, kwargs in calls if method == "POST")
        self.assertEqual(posted["ledger_admin_key"], "sk-synthetic-operator")
        self.assertEqual(posted["ledger_read_key"], "sk-synthetic-reader")
        self.assertEqual(posted["unrelated_native_config"], {"preserve": True})
        self.assertTrue(all("/functions/id/" + p.FILTER_ID + "/valves" in path for _, path, _ in calls))

    def test_filter_credential_readback_rejects_missing_management_key(self):
        state = {"admin": {"token": "synthetic-admin-session"}, "cost_reader": {"key": "sk-synthetic-reader"}}
        class WebUI:
            def ok(self, *args, **kwargs):
                return {"ledger_base_url": "http://proxy:4000", "ledger_read_key": "sk-synthetic-reader",
                        "read_wait_seconds": 8.0}
        with patch.object(p, "read_private", return_value={"operator_token": "sk-synthetic-operator"}):
            with self.assertRaises(p.ProofError):
                p.filter_admin_key(WebUI(), state)

    def role_transition(self, *, fail_probe=False):
        state, employees = fixture()
        state["admin"].update(email="owner@example.invalid", password="synthetic-owner-password", token="owner-admin-session")
        state["role_probe_control"] = {"id": IDS[5], "token": "controller-admin-session"}
        owner = state["admin"]
        tool = {"id": p.TOOL_ID, "user_id": owner["id"], "name": "Synthetic native tool", "content": "class Tools: pass\n",
                "meta": {}, "access_grants": []}
        model = {"id": p.MODEL_ID, "base_model_id": p.MODELS[0], "name": "Synthetic", "meta": {}, "params": {},
                 "access_grants": [], "is_active": True}
        roles, denials = [], []
        class WebUI:
            role = "admin"
            def session(self, account, role):
                actual = self.role if account["id"] == owner["id"] else "admin"
                if actual != role:
                    raise AssertionError("Fresh native role differed")
            def model(self, *args):
                return copy.deepcopy(model)
            def ok(self, method, path, **kwargs):
                if path == "/api/v1/users/default/permissions":
                    return {"workspace": {"tools": False, "tools_import": False}}
                if path == "/api/v1/tools/id/" + p.TOOL_ID:
                    return copy.deepcopy(tool)
                if path == "/api/v1/tools/id/" + p.TOOL_ID + "/valves":
                    if self.role != "user":
                        raise AssertionError("Not probing actual demoted owner")
                    return {"managed_model_ids": list(p.MODELS), "employee_limit": 100}
                if path == "/api/v1/functions/id/" + p.FILTER_ID:
                    return {"user_id": owner["id"]}
                if path == "/api/v1/users/" + owner["id"] + "/update":
                    if kwargs["token"] != "controller-admin-session":
                        raise AssertionError("Role mutation bypassed native control administrator")
                    self.role = kwargs["body"]["role"]
                    roles.append(self.role)
                    return {"id": owner["id"], "role": self.role}
                if path == "/api/v1/auths/signin":
                    if kwargs["body"] != {"email": owner["email"], "password": owner["password"]}:
                        raise AssertionError("Sign-in bypassed native private credentials")
                    return {"id": owner["id"], "role": self.role, "token": "fresh-" + self.role}
                raise AssertionError("Unexpected native route")
        webui = WebUI()
        def deny(actual_webui, method, path, token, *, body=None):
            self.assertIs(actual_webui, webui)
            self.assertEqual(webui.role, "user")
            self.assertEqual(token, "fresh-user")
            denials.append((method, path, body))
            if "/tools/" in path:
                self.assertNotEqual(body["content"], tool["content"])
                if fail_probe:
                    raise p.ProofError("Synthetic unexpected native source-update response")
            return 401
        with patch.object(p, "read_states", return_value=employees), \
             patch.object(p, "staff_profiles", return_value={"model": "stable-hash"}), \
             patch.object(p, "filter_admin_key"), patch.object(p, "installation", return_value={}), \
             patch.object(p, "denied_status", side_effect=deny), patch.object(p, "write_private") as saved:
            if fail_probe:
                with self.assertRaises(p.ProofError):
                    p.role_probe(webui, state, Path("synthetic-private.json"))
            else:
                result = p.role_probe(webui, state, Path("synthetic-private.json"))
                self.assertTrue(result["native_budget_state_unchanged"])
                self.assertTrue(result["tool_valves_secret_free"])
            saved.assert_called_once_with(Path("synthetic-private.json"), state)
        self.assertEqual(roles, ["user", "admin"])
        self.assertEqual(owner["token"], "fresh-admin")
        self.assertEqual(len(denials), 3)

    def test_role_probe_uses_native_demoted_owner_refreshes_login_and_restores(self):
        self.role_transition()

    def test_role_probe_restores_native_admin_when_security_probe_fails(self):
        self.role_transition(fail_probe=True)

    def test_public_projection_separates_staff_and_preserves_unknown(self):
        state, employees = fixture()
        employee = replace(employees[0], max_budget=None)
        public = p.normalize([employee])
        self.assertIsNone(public["users"][0]["max_budget_usd"])
        self.assertEqual(public["keys"][0]["spend_usd"], "0")
        text = str(public)
        self.assertNotIn(state["native_keys"][0]["key"], text)
        self.assertNotIn(employee.models[0].key_hash, text)

    def test_snapshot_accepts_intended_staff_cap_changes(self):
        state, employees = fixture()
        state["admin_fixture"] = {"staff_baseline": p.normalize(employees[:2]), "staff_profiles": {"A": "hash"}}
        changed = [replace(employees[0], max_budget=Decimal(40)), *employees[1:]]
        with patch.object(p, "read_states", return_value=changed), \
             patch.object(p, "positive_logs", return_value=([], 1)), \
             patch.object(p, "native_client"), patch.object(p, "installation", return_value={}), \
             patch.object(p, "staff_profiles", return_value={"A": "hash"}):
            observed = p.snapshot(None, state)
        self.assertEqual(len(observed["users"]), 2)
        self.assertEqual(len(observed["keys"]), 4)
        self.assertEqual(observed["admin_accounting"]["users"][0]["user_id"], IDS[2])
        self.assertFalse(observed["no_change_checks"]["staff_budgets_equal_setup"])
        self.assertTrue(observed["no_change_checks"]["staff_model_profiles_equal_setup"])

    def test_positive_rows_use_shared_real_scope_validator(self):
        state, _ = fixture()
        class Native:
            def logs(self, user):
                return [row()] if user == IDS[2] else []
        rows, count = p.positive_logs(Native(), state)
        self.assertEqual(count, 0)
        self.assertEqual(rows[0]["owui_budget"]["user_id"], IDS[2])
        self.assertNotIn("metadata", rows[0])
        for mutation in (lambda r: r["metadata"]["spend_logs_metadata"]["owui_budget"].update(user_id=IDS[0]),
                         lambda r: r.update(session_id=IDS[0]),
                         lambda r: r.update(model_group=p.MODELS[1]),
                         lambda r: r.update(total_tokens=16),
                         lambda r: r.update(status="failure")):
            bad = row()
            mutation(bad)
            with self.subTest(bad=bad), patch.object(Native, "logs", side_effect=lambda user: [bad] if user == IDS[2] else []):
                with self.assertRaises(p.ProofError):
                    p.positive_logs(Native(), state)

    def test_unknown_zero_rows_are_not_verified_free_projection(self):
        state, _ = fixture()
        class Native:
            def logs(self, user):
                return [{"spend": 0, "status": "failure"}] if user == IDS[2] else []
        self.assertEqual(p.positive_logs(Native(), state), ([], 1))

    def probe(self, wrong_denial=False, *, denial_message=None, denial_type="budget_exceeded", expect_failure=False):
        state, employees = fixture()
        actual, updates, requests = copy.deepcopy(employees), [], []
        b = employees[2].models[1]
        class Client:
            def __init__(self, *args):
                pass
            async def set_model_cap(self, key_hash, cap):
                updates.append((key_hash, cap))
                self.assert_hash(key_hash)
                actual[2] = replace(actual[2], models=tuple(replace(k, max_budget=cap)
                                    if k.key_hash == key_hash else k for k in actual[2].models))
            @staticmethod
            def assert_hash(key_hash):
                if key_hash != b.key_hash:
                    raise AssertionError("Unexpected key mutation")
        class Native:
            def poll(self, label, condition):
                result = condition()
                if result is None:
                    raise AssertionError("Unexpected state drift")
                return result
            def request(self, method, path, **kwargs):
                requests.append((method, path, kwargs))
                return (403 if wrong_denial else p.BUDGET_EXCEEDED_STATUS,
                        {"error": {"type": denial_type, "message": denial_message or N.BUDGET_MODEL_MESSAGE}}, {})
        with patch.object(p, "BudgetAdminClient", Client), \
             patch.object(p, "read_private", return_value={"operator_token": "sk-synthetic-operator"}), \
             patch.object(p, "read_states", side_effect=lambda _: copy.deepcopy(actual)), \
             patch.object(p, "native_client", return_value=Native()):
            if wrong_denial or expect_failure:
                with self.assertRaises(p.ProofError):
                    p.native_probe(state, deny=True)
            else:
                result = p.native_probe(state, deny=True)
                self.assertTrue(result["original_cap_restored_exactly"])
                self.assertEqual(result["budget_message"], denial_message or N.BUDGET_MODEL_MESSAGE)
                self.assertTrue(result["friendly_budget_feedback"])
        self.assertEqual(updates, [(b.key_hash, Decimal(500)), (b.key_hash, Decimal(0)), (b.key_hash, Decimal(500))])
        self.assertEqual(actual, employees)
        self.assertEqual(requests[0][2]["token"], state["admin_budgetnative_keys"][1]["key"])
        self.assertEqual(requests[0][2]["body"]["model"], p.MODELS[1])

    def test_probe_by_hash_restores_cap_and_preserves_all_states(self):
        self.probe()

    def test_probe_restores_original_cap_after_unexpected_denial(self):
        self.probe(wrong_denial=True)

    def test_probe_requires_approved_key_feedback_and_native_error_type(self):
        self.probe(denial_message=N.BUDGET_GENERIC_MESSAGE)
        for message in (N.BUDGET_USER_MESSAGE, "Budget has been exceeded! Key=private", "Ошибка бюджета",
                        N.BUDGET_MODEL_MESSAGE + " sk-private"):
            with self.subTest(message=message):
                self.probe(denial_message=message, expect_failure=True)
        self.probe(denial_type="auth_error", expect_failure=True)


class UnknownAdminProvisionTests(unittest.TestCase):
    """Actual installer/readback/client over reused finite native HTTP leaves."""
    def setUp(self):
        from test_unknown_usage_policy import Wire, Response, P
        self.U, self.Response, self.wire = P, Response, Wire()
        for item in self.wire.models: item['model_info']['supports_native_streaming'] = False
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.private = Path(temp.name) / 'private'; self.private.mkdir(mode=0o700)
        import prove_gateway_auth as private_owner
        if os.name == 'nt':
            self.enterContext(patch.object(private_owner.stat, 'S_IMODE', side_effect=lambda m: 0o700 if stat.S_ISDIR(m) else 0o600))
        self.path, self.handoff = self.private / 'admin.private.json', self.private / 'accounts.private.json'
        operator = self.private / 'operator.private.json'
        p.write_private(operator, {'schema': 1, 'operator_token': self.wire.operator})
        self.enterContext(patch.object(p, 'OPERATOR_STATE', operator))
        self.enterContext(patch.object(sys.modules['provision_webui'], 'OPERATOR_STATE', operator))
        self.enterContext(patch.object(p, 'SOURCE', BUDGETS / 'admin_tools.py'))
        self.enterContext(patch.dict(os.environ, OWUI_BUDGET_GATEWAY_SECRET=self.wire.gateway))
        self.enterContext(patch.object(p, 'ClientSession', self.wire.session))
        self.enterContext(patch.object(N, 'build_opener', return_value=self.wire))
        self.common = {'schema': 1, 'stage': 'setup_complete', 'started_at_utc': '2026-01-01T00:00:00+00:00',
            'admin': {'id': IDS[2], 'token': 'old-admin-session'}, 'users': [
                {'id': uid, 'token': 'old-user-' + uid} for uid in IDS[:2]],
            'native_keys': [{'key': 'sk-old-private-' + str(i)} for i in range(4)],
            'cost_display': {'stage': 'setup_complete'}, 'cost_reader': {'key': self.wire.viewer}}
        self.office = {'stage': 'setup_complete', 'admin': copy.deepcopy(self.common['admin']),
                       'users': [{'id': IDS[3], 'token': 'office-user-session'}]}
        self.unknown = {'stage': 'setup_complete', 'admin': copy.deepcopy(self.common['admin']),
                        'users': [{'id': IDS[4], 'token': 'unknown-user-session'}], 'unknown_gui_setup': {'models': {}}}
        self.new_id, self.new_token = IDS[5], 'new-admin-private-session'
        actors = [self.common['admin'], *self.common['users'], *self.office['users'], *self.unknown['users']]
        self.accounts = {a['token']: (a['id'], 'admin' if a is self.common['admin'] else 'user') for a in actors}
        self.directory = {uid: {'id': uid, 'name': uid, 'email': uid + '@example.invalid', 'role': role, 'info': {}}
                          for uid, role in self.accounts.values()}
        self.workspace = {alias: {'id': alias, 'name': alias, 'base_model_id': None, 'is_active': True,
            'params': {'max_tokens': 16, 'custom_params': {'store': False}}, 'meta': {'filterIds': [p.FILTER_ID]},
            'access_grants': [{'principal_type': 'user', 'principal_id': IDS[4], 'permission': 'read'}],
            'user_id': IDS[2], 'write_access': True} for alias in self.U.ALIASES}
        self.unknown['unknown_gui_setup']['models'] = copy.deepcopy(self.workspace)
        self.valves = {'ledger_base_url': 'http://proxy:4000', 'ledger_read_key': self.wire.viewer,
                       'read_wait_seconds': 8.0, 'default_budget_template': None, 'unrelated': {'keep': True}}
        self.functions = {p.FILTER_ID: {'id': p.FILTER_ID, 'user_id': IDS[2], 'updated_at': 1, 'type': 'filter',
            'content': 'untouched-cost-owner', 'is_active': True, 'meta': {'toggle': False}}}
        self.tools, self.skills, self.calls, self.fault = {}, {}, [], None
        self.webui = p.WebUI(); self.webui.opener = self
        self.loop = asyncio.new_event_loop(); self.addCleanup(self.loop.close)
        async def seed():
            async with self.wire.session(trust_env=False) as session:
                client = p.BudgetAdminClient(session, p.PROXY_URL, self.wire.operator)
                async def guard(): pass
                for actor in [*self.common['users'], *self.office['users'], *self.unknown['users']]:
                    models = self.U.ALIASES if actor['id'] == IDS[4] else (self.U.ALIASES[0],)
                    budget = await client.initialize_employee(actor['id'], tuple((m, Decimal(2)) for m in models),
                        Decimal(2 * len(models)), self.wire.gateway, before_write=guard)
            native = p.native_client(); native.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            return self.U.snapshot(native, budget)
        self.unknown['unknown_gui_verification'] = {'stage': 'verified', 'native': self.loop.run_until_complete(seed())}
        self.before = copy.deepcopy((self.common, self.office, self.unknown, self.wire.users, self.wire.keys))
        self.wire.requests.clear()

    def open(self, request, timeout):
        body = json.loads(request.data) if request.data else None
        status, value = self.handle(request.get_method(), request.full_url, dict(request.header_items()), body)
        return self.Response(status, value)

    def handle(self, method, url, headers, body):
        parsed = urlsplit(url); route = parsed.path
        if route == '/api/version': return 200, {'version': '0.12.2'}
        token = {k.lower(): v for k, v in headers.items()}['authorization'].removeprefix('Bearer ')
        uid, role = self.accounts[token]
        self.calls.append((method, route, copy.deepcopy(body)))
        if self.fault:
            failure = self.fault(method, route, body)
            if failure: return failure
        if route == '/api/v1/auths/': return 200, {'id': uid, 'role': role}
        if route == '/api/v1/auths/add':
            assert body['role'] == 'admin' and role == 'admin'
            self.accounts[self.new_token] = (self.new_id, 'admin')
            self.directory[self.new_id] = {'id': self.new_id, 'name': body['name'], 'email': body['email'], 'role': 'admin', 'info': None}
            return 200, {'id': self.new_id, 'token': self.new_token, 'role': 'admin'}
        if route == '/api/v1/users/all': return 200, {'users': list(self.directory.values()), 'total': len(self.directory)}
        if route == '/api/models':
            return 200, {'data': [{'id': mid, 'info': copy.deepcopy(row)} for mid, row in self.workspace.items()
                if role == 'admin' or ('user', uid, 'read') in p.grant_set(row)]}
        if route == '/api/v1/models/model':
            row = self.workspace.get(parse_qs(parsed.query)['id'][0])
            return (404, {}) if row is None else (200, row) if role == 'admin' else (401, {})
        if route == '/api/v1/models/create':
            assert body['id'] not in self.workspace
            self.workspace[body['id']] = copy.deepcopy(body) | {'user_id': uid, 'write_access': True}
            return 200, self.workspace[body['id']]
        if route == '/api/v1/tools/create':
            assert body['id'] not in self.tools
            self.tools[body['id']] = copy.deepcopy(body) | {'user_id': uid, 'write_access': True,
                'specs': [{'name': 'open_budget_form', 'parameters': {'properties': {'view_json': {'type': 'string', 'default': '{}'}}}},
                          {'name': 'apply_budget_form', 'parameters': {'properties': {}}}]}
            return 200, self.tools[body['id']]
        if route.startswith('/api/v1/tools/id/'):
            if role != 'admin': return 401, {}
            tool = self.tools.get(p.TOOL_ID)
            if tool is None: return 404, {}
            if route.endswith('/valves/update'): tool['valves'] = copy.deepcopy(body); return 200, body
            return 200, tool['valves'] if route.endswith('/valves') else tool
        if route == '/api/v1/skills/create':
            assert body['id'] not in self.skills
            self.skills[body['id']] = copy.deepcopy(body) | {'user_id': uid, 'write_access': True}
            return 200, self.skills[body['id']]
        if route.startswith('/api/v1/skills/id/'):
            return (401, {}) if role != 'admin' else (200, self.skills[p.SKILL_ID]) if p.SKILL_ID in self.skills else (404, {})
        if route == '/api/v1/functions/export':
            return 200, [dict(v, valves=copy.deepcopy(self.valves)) for v in self.functions.values()]
        if route.startswith('/api/v1/functions/id/'):
            if route.endswith('/valves/update'):
                self.valves = copy.deepcopy(body); self.functions[p.FILTER_ID]['updated_at'] = 2
                return 200, body
            return 200, self.valves if route.endswith('/valves') else self.functions[p.FILTER_ID]
        values = {'/openai/config': {'connection': 'preserve'}, '/api/v1/tasks/config': {'native': 'preserve'},
                  '/api/v1/chats/config': {'chat': 'preserve'}, '/api/v1/configs/tool_servers': {'office': 'preserve'}}
        assert method == 'GET' and route in values, (method, route)
        return 200, copy.deepcopy(values[route])

    def setup_admin(self):
        return self.loop.run_until_complete(p.unknown_setup(self.webui, self.common, self.office, self.unknown, self.path, self.handoff))

    def test_real_clients_install_readback_known_only_and_preserve_all_existing_state(self):
        safe = self.setup_admin(); selected = p.read_private(self.path); accounts = p.read_private(self.handoff)
        self.assertEqual(selected['stage'], 'setup_complete')
        self.assertEqual(safe['employee_ids'], [IDS[4]])
        self.assertEqual(accounts['employee_ids'], [IDS[4]])
        self.assertEqual(set(accounts['admin']), {'id', 'email', 'password'})
        self.assertEqual(self.wire.users[self.new_id]['models'], [self.U.ALIASES[0]])
        self.assertEqual(self.wire.users[self.new_id]['max_budget'], 2)
        self.assertEqual(self.tools[p.TOOL_ID]['valves']['managed_model_ids'], list(self.U.ALIASES))
        self.assertEqual(self.workspace[p.MODEL_ID]['base_model_id'], self.U.ALIASES[0])
        self.assertEqual(self.valves['default_budget_template'], None)
        self.assertEqual(self.valves['unrelated'], {'keep': True})
        self.assertEqual(self.valves['ledger_admin_key'], self.wire.operator)
        self.assertEqual((self.common, self.office, self.unknown), self.before[:3])
        self.assertEqual({k: v for k, v in self.wire.users.items() if k != self.new_id}, self.before[3])
        self.assertEqual({k: v for k, v in self.wire.keys.items() if v['user_id'] != self.new_id}, self.before[4])
        self.assertFalse(self.wire.attempts or self.wire.physical)
        self.assertNotIn(self.new_token, json.dumps(safe))
        self.assertNotIn(self.wire.operator, json.dumps(safe))
        p.unknown_snapshot(self.webui, self.common, self.office, self.unknown, selected)

    def test_optin_cli_handoff_and_safe_receipt_use_separate_state_without_legacy_snapshot(self):
        office_path = Path('/proof-private/office-state.private.json')
        unknown_path = Path('/proof-private/unknown-usage-gui-state.private.json')
        actual_read = p.read_private
        def read(path):
            if path == p.STATE: return copy.deepcopy(self.common)
            if path == office_path: return copy.deepcopy(self.office)
            if path == unknown_path: return copy.deepcopy(self.unknown)
            return actual_read(path)
        receipt = self.private / 'setup.safe.json'
        args = ['provision_admin.py', '--phase', 'unknown-setup', '--private-state', str(p.STATE),
            '--office-state', str(office_path), '--unknown-state', str(unknown_path),
            '--admin-unknown-state', str(self.path), '--browser-accounts', str(self.handoff), '--receipt', str(receipt)]
        output = StringIO()
        with patch.object(p, 'UNKNOWN_ADMIN_STATE', self.path), patch.object(p, 'UNKNOWN_ADMIN_ACCOUNTS', self.handoff), \
             patch.object(p, 'read_private', side_effect=read), patch.object(p, 'WebUI', return_value=self.webui), \
             patch.object(p, 'snapshot', side_effect=AssertionError('Legacy snapshot must not run')), \
             patch.object(sys, 'argv', args), redirect_stdout(output):
            self.assertEqual(p.main(), 0, output.getvalue())
        safe = json.loads(output.getvalue())
        self.assertEqual((safe['phase'], safe['stage'], safe['passed']), ('unknown-setup', 'setup_complete', True))
        self.assertEqual(actual_read(receipt), safe)
        self.assertNotIn(self.new_token, output.getvalue())
        self.assertNotIn(self.wire.operator, output.getvalue())
        self.assertEqual((self.common, self.office, self.unknown), self.before[:3])

    def test_legacy_cli_cannot_accept_new_fixture_inputs(self):
        args = ['provision_admin.py', '--phase', 'snapshot', '--private-state', str(p.STATE),
                '--receipt', str(self.private / 'forbidden.safe.json'), '--office-state', '/proof-private/office-state.private.json']
        with patch.object(sys, 'argv', args), redirect_stdout(StringIO()) as output:
            self.assertEqual(p.main(), 1)
        self.assertIn('opt-in only', json.loads(output.getvalue())['failure'])
        self.assertEqual(self.calls, [])

    def test_unverified_or_drifted_unknown_fixture_rejects_before_any_post(self):
        self.unknown['unknown_gui_verification']['stage'] = 'reading_native'
        with self.assertRaises(p.ProofError): self.setup_admin()
        self.assertFalse(any(m == 'POST' for m, _, _ in self.calls))
        self.assertFalse(self.path.exists())

    def test_absent_default_template_remains_absent_after_credential_install(self):
        self.valves.pop('default_budget_template')
        self.setup_admin()
        self.assertNotIn('default_budget_template', self.valves)

    def test_snapshot_retains_service_changes_separately_without_relaxing_personal_preservation(self):
        service_id = '00000007-1111-4111-8111-111111111111'
        async def seed_service():
            async with self.wire.session(trust_env=False) as session:
                client = p.BudgetAdminClient(session, p.PROXY_URL, self.wire.operator)
                async def guard(): pass
                await client.initialize_employee(service_id, ((self.U.ALIASES[0], Decimal(2)),),
                    Decimal(2), self.wire.gateway, before_write=guard)
        self.loop.run_until_complete(seed_service())
        self.valves['service_payer_id'] = service_id
        self.setup_admin(); selected = p.read_private(self.path)
        self.assertNotIn(service_id, selected['initial']['old'])
        self.assertIsNotNone(selected['initial']['service'])
        self.wire.users[service_id]['spend'] = .166  # Raw counter IO change, not financial qualification.
        safe = p.unknown_snapshot(self.webui, self.common, self.office, self.unknown, selected)
        self.assertTrue(safe['service_observed_separately'])
        self.assertEqual(selected['observation']['service']['snapshot']['user']['spend'], .166)
        self.assertEqual(selected['observation']['unknown'], selected['initial']['unknown'])

    def test_existing_resource_or_unproven_absence_rejects_before_writes(self):
        for status in (200, 401, 403, 500):
            self.calls.clear()
            self.fault = lambda method, route, body: (status, {}) if route == '/api/v1/tools/id/' + p.TOOL_ID else None
            with self.subTest(status=status), self.assertRaises(p.ProofError): self.setup_admin()
            self.assertFalse(any(m == 'POST' for m, _, _ in self.calls))

    def test_prior_management_key_or_profile_drift_cannot_be_overwritten(self):
        for kind in ('key', 'profile', 'verified_snapshot'):
            before = copy.deepcopy((self.valves, self.workspace, self.unknown))
            if kind == 'key': self.valves['ledger_admin_key'] = 'sk-another-existing-owner'
            elif kind == 'profile': self.workspace[self.U.ALIASES[0]]['params']['max_tokens'] = 999
            else: self.unknown['unknown_gui_verification']['native']['rows'] = [{'request_id': 'not-current'}]
            with self.subTest(kind=kind), self.assertRaises(p.ProofError): self.setup_admin()
            self.assertFalse(any(m == 'POST' for m, _, _ in self.calls))
            self.valves, self.workspace, self.unknown = before

    def test_partial_install_is_private_failed_nonresumable_without_repair(self):
        self.fault = lambda method, route, body: (500, {}) if route == '/api/v1/skills/create' else None
        with self.assertRaises(p.ProofError): self.setup_admin()
        selected = p.read_private(self.path)
        self.assertEqual(selected['stage'], 'setup_failed')
        self.assertIn(self.new_id, self.wire.users)
        self.assertFalse(self.handoff.exists())
        self.calls.clear()
        with self.assertRaises(p.ProofError): self.setup_admin()
        self.assertEqual(self.calls, [])

    def test_snapshot_rejects_personal_role_acl_and_counter_drift(self):
        self.setup_admin(); selected = p.read_private(self.path)
        for kind in ('role', 'acl', 'counter'):
            before = copy.deepcopy((self.directory, self.workspace, self.wire.users))
            if kind == 'role': self.directory[IDS[4]]['role'] = 'admin'
            elif kind == 'acl': self.workspace[self.U.ALIASES[0]]['access_grants'] = []
            else: self.wire.users[IDS[4]]['spend'] = 1
            with self.subTest(kind=kind), self.assertRaises(p.ProofError):
                p.unknown_snapshot(self.webui, self.common, self.office, self.unknown, selected)
            self.directory, self.workspace, self.wire.users = before


class BudgetFeedbackContractTests(unittest.TestCase):
    def test_native_and_persisted_error_envelopes_preserve_exact_scope(self):
        tree = ast.parse((BUDGETS / "budget_errors.py").read_text(encoding="utf-8"))
        messages = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in {"USER_MESSAGE", "MODEL_MESSAGE", "GENERIC_MESSAGE"}}
        self.assertEqual(messages, {"USER_MESSAGE": N.BUDGET_USER_MESSAGE,
                                    "MODEL_MESSAGE": N.BUDGET_MODEL_MESSAGE,
                                    "GENERIC_MESSAGE": N.BUDGET_GENERIC_MESSAGE})
        for message in (N.BUDGET_MODEL_MESSAGE, N.BUDGET_GENERIC_MESSAGE):
            error = {"error": {"type": "budget_exceeded", "code": "422", "message": message}}
            self.assertEqual(N.expected_budget_message(error, scope="key"), message)
            self.assertEqual(N.expected_budget_message({"content": error}, scope="key"), message)
        self.assertEqual(N.expected_budget_message({"content": N.BUDGET_USER_MESSAGE}, scope="user"),
                         N.BUDGET_USER_MESSAGE)

    def test_ordinary_failures_aliases_and_incidental_text_are_not_budget_denials(self):
        for error in (None, {}, {"content": "Ошибка бюджета"}, {"message": "Network problem"},
                      {"message": "Prefix " + N.BUDGET_USER_MESSAGE},
                      {"message": N.BUDGET_USER_MESSAGE, "private": "owui-budget-v1-hidden"},
                      {"content": {"message": N.BUDGET_MODEL_MESSAGE, "private": "sk-hidden"}}):
            with self.subTest(error=error), self.assertRaises(N.ProofError):
                N.expected_budget_message(error)
        with self.assertRaises(N.ProofError):
            N.expected_budget_message(N.BUDGET_GENERIC_MESSAGE, scope="user")


if __name__ == "__main__":
    unittest.main()
