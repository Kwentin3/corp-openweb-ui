"""Bounded orchestration rehearsal, not native server/runtime acceptance."""
import copy
from dataclasses import replace
from decimal import Decimal
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


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

    def probe(self, wrong_denial=False):
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
                        {"error": {"type": "budget_exceeded", "message": "Key=" + b.key_alias}}, {})
        with patch.object(p, "BudgetAdminClient", Client), \
             patch.object(p, "read_private", return_value={"operator_token": "sk-synthetic-operator"}), \
             patch.object(p, "read_states", side_effect=lambda _: copy.deepcopy(actual)), \
             patch.object(p, "native_client", return_value=Native()):
            if wrong_denial:
                with self.assertRaises(p.ProofError):
                    p.native_probe(state, deny=True)
            else:
                result = p.native_probe(state, deny=True)
                self.assertTrue(result["original_cap_restored_exactly"])
        self.assertEqual(updates, [(b.key_hash, Decimal(500)), (b.key_hash, Decimal(0)), (b.key_hash, Decimal(500))])
        self.assertEqual(actual, employees)
        self.assertEqual(requests[0][2]["token"], state["admin_budgetnative_keys"][1]["key"])
        self.assertEqual(requests[0][2]["body"]["model"], p.MODELS[1])

    def test_probe_by_hash_restores_cap_and_preserves_all_states(self):
        self.probe()

    def test_probe_restores_original_cap_after_unexpected_denial(self):
        self.probe(wrong_denial=True)


if __name__ == "__main__":
    unittest.main()
