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
