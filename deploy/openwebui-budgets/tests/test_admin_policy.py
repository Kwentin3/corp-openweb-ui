"""Exact proposal policy and native cap-only mutation boundary."""
from dataclasses import replace
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).parents[1]


def load(name, filename):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load("employee_budget_admin_contract", "admin_contract.py")
policy = load("employee_budget_admin_policy", "admin_policy.py")
D = Decimal
USER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"


def state():
    return contract.EmployeeBudget(USER, D("10"), D("1"), "30d", "2026-12-01T00:00:00Z", (
        contract.ModelBudget("a", "a" * 64, "private-alias-a", D("5"), D(".4"), "30d", "2026-12-01T00:00:00Z", False),
        contract.ModelBudget("b", "b" * 64, "private-alias-b", D("5"), D(".6"), "30d", "2026-12-01T00:00:00Z", False)))


def plan(before, budget="10", shares=None):
    return json.dumps({"schema": 1, "type": "employee_budget_plan", "changes": [{
        "user_id": before.user_id, "expected_revision": policy.revision(before),
        "budget_usd": budget, "shares": shares or {"a": "50", "b": "50"}}]})


def prepared(before, budget="10", shares=None):
    return policy.prepare_change(policy.parse_plan(plan(before, budget, shares))[0], before)


class NativeClient:
    """External native owner double: only exposed writes may mutate its state."""
    def __init__(self, before, fail_at=None):
        self.state, self.writes, self.fail_at = before, [], fail_at

    async def read_employee(self, user_id, models):
        assert user_id == self.state.user_id
        assert set(models) == {m.model for m in self.state.models}
        return self.state

    def record(self, kind, target, cap):
        self.writes.append((kind, target, cap))
        if len(self.writes) == self.fail_at:
            raise contract.BudgetAdminError("native_unavailable")

    async def set_user_cap(self, user_id, cap):
        self.record("user", user_id, cap)
        self.state = replace(self.state, max_budget=cap)

    async def set_model_cap(self, key_hash, cap):
        self.record("model", key_hash, cap)
        self.state = replace(self.state, models=tuple(
            replace(m, max_budget=cap) if m.key_hash == key_hash else m for m in self.state.models))


class PolicyTests(unittest.TestCase):
    def test_exact_allocation_and_hard_zero(self):
        p = prepared(state(), "0.3", {"a": "33", "b": "67"})
        self.assertEqual(p.new_caps, (("a", D(".099")), ("b", D(".201"))))
        self.assertEqual(prepared(state(), "40", {"a": "100", "b": "0"}).new_caps,
                         (("a", D("40")), ("b", D(0))))
        self.assertEqual(prepared(state(), "0").budget_usd, 0)

    def test_unsafe_precision_is_rejected_without_rounding(self):
        for value in ("10.000000000000000001", "99999999999999999999999999999999"):
            with self.subTest(value=value), self.assertRaisesRegex(contract.BudgetAdminError, "unsupported_amount_precision"):
                prepared(state(), value)

    def test_strict_json_amounts_and_percentages(self):
        for value in (True, 10, "1e2", "NaN", "-1", " 10", "١٠"):
            with self.subTest(value=value), self.assertRaises(contract.BudgetAdminError):
                policy.parse_plan(plan(state(), value))
        for shares in ({"a": "50", "b": "49.9999999999999999999999999999"}, {"a": "101", "b": "0"}):
            with self.subTest(shares=shares), self.assertRaisesRegex(contract.BudgetAdminError, "shares_must_total_100"):
                policy.parse_plan(plan(state(), shares=shares))
        with self.assertRaisesRegex(contract.BudgetAdminError, "duplicate_json_field"):
            policy.parse_plan(plan(state()).replace('"schema": 1', '"schema": 1, "schema": 1'))
        data = json.loads(plan(state()))
        data["changes"].append(data["changes"][0])
        with self.assertRaisesRegex(contract.BudgetAdminError, "invalid_employee"):
            policy.parse_plan(json.dumps(data))

    def test_revision_binds_configuration_but_allows_spend_progress(self):
        before = state()
        spent = replace(before, spend=D("2"), models=(replace(before.models[0], spend=D("1.4")), before.models[1]))
        self.assertEqual(policy.revision(before), policy.revision(spent))
        for changed in (replace(before, max_budget=D("11")), replace(before, budget_reset_at="2027-01-01"),
                        replace(before, models=(replace(before.models[0], blocked=True), before.models[1])),
                        replace(before, models=(replace(before.models[0], key_hash="c" * 64), before.models[1]))):
            self.assertNotEqual(policy.revision(before), policy.revision(changed))
            with self.assertRaisesRegex(contract.BudgetAdminError, "stale_snapshot"):
                policy.prepare_change(policy.parse_plan(plan(before))[0], changed)

    def test_foreign_identity_models_and_period_fail_closed(self):
        before = state()
        change = policy.parse_plan(plan(before))[0]
        with self.assertRaisesRegex(contract.BudgetAdminError, "invalid_employee"):
            policy.prepare_change(change, replace(before, user_id=OTHER))
        with self.assertRaisesRegex(contract.BudgetAdminError, "invalid_models"):
            prepared(before, shares={"a": "50", "foreign": "50"})
        with self.assertRaisesRegex(contract.BudgetAdminError, "unsupported_budget_period"):
            prepared(replace(before, budget_duration="7d"))

    def test_public_projection_hides_management_ids_and_unknown_is_not_zero(self):
        before = state()
        identity = {"user_id": USER, "name": "Ada", "email": "ada@example.invalid"}
        row = policy.public_employee(identity, before)
        text = json.dumps(row)
        self.assertNotIn("private-alias", text)
        self.assertNotIn("a" * 64, text)
        self.assertEqual([m["share_percent"] for m in row["models"]], ["50", "50"])
        unknown = policy.public_employee(identity, replace(before, max_budget=None))
        self.assertIsNone(unknown["budget_usd"])
        self.assertIsNone(unknown["remaining_usd"])
        self.assertEqual([m["share_percent"] for m in unknown["models"]], ["", ""])

    def test_display_filters_cannot_introduce_business_operations(self):
        with self.assertRaisesRegex(contract.BudgetAdminError, "invalid_view"):
            policy.parse_view('{"max_budget":"100"}')
        rows = [{"user_id": USER, "name": "Ada", "budget_usd": "10", "remaining_usd": "2"},
                {"user_id": OTHER, "name": "Bob", "budget_usd": "10", "remaining_usd": "9"}]
        result = policy.filter_view(rows, policy.parse_view('{"remaining_below_percent":"30","sort_by":"remaining"}'))
        self.assertEqual(result, [rows[0]])
        self.assertEqual(rows[1]["remaining_usd"], "9")

    def test_confirmation_treats_directory_names_and_labels_as_plain_text(self):
        identity = {"user_id": USER, "name": '<span style="display:none">**Ada**',
                    "email": "[hide](https://example.invalid)", "model_labels": {"a": "`**model**`"}}
        text = policy.confirmation_text((prepared(state(), "20"),), {USER: identity})
        self.assertNotIn("<span", text)
        self.assertIn("&lt;span", text)
        self.assertIn(r"\*\*Ada\*\*", text)
        self.assertIn(r"\[hide\]\(https://example\.invalid\)", text)
        self.assertIn(r"\`\*\*model\*\*\`", text)
        self.assertIn("10 → 20", text)
        self.assertIn("5 → 10 USD", text)


class MutationTests(unittest.IsolatedAsyncioTestCase):
    async def test_lower_model_then_raise_total_then_raise_other_model(self):
        before = state()
        client = NativeClient(before)
        after = await policy.apply_prepared(client, prepared(before, "20", {"a": "90", "b": "10"}))
        self.assertEqual(client.writes, [("model", "b" * 64, D("2")), ("user", USER, D("20")), ("model", "a" * 64, D("18"))])
        self.assertEqual(after.spend, before.spend)
        self.assertEqual(after.budget_reset_at, before.budget_reset_at)
        self.assertEqual([m.spend for m in after.models], [m.spend for m in before.models])

    async def test_lower_personal_total_after_models(self):
        before = state()
        client = NativeClient(before)
        await policy.apply_prepared(client, prepared(before, "1"))
        self.assertEqual([w[0] for w in client.writes], ["model", "model", "user"])

    async def test_stale_native_state_prevents_every_write(self):
        before = state()
        client = NativeClient(replace(before, max_budget=D("20")))
        with self.assertRaisesRegex(contract.BudgetAdminError, "stale_snapshot"):
            await policy.apply_prepared(client, prepared(before))
        self.assertEqual(client.writes, [])

    async def test_partial_failure_preserves_actual_state_and_does_not_rollback_or_retry(self):
        before = state()
        client = NativeClient(before, fail_at=2)
        with self.assertRaisesRegex(contract.BudgetAdminError, "native_unavailable"):
            await policy.apply_prepared(client, prepared(before, "20", {"a": "90", "b": "10"}))
        self.assertEqual(len(client.writes), 2)
        self.assertEqual(client.state.models[1].max_budget, D("2"))
        self.assertEqual(client.state.max_budget, D("10"))

    async def test_nonzero_native_readback_cannot_confirm_zero(self):
        before = state()
        class WrongReadback(NativeClient):
            async def set_model_cap(self, key_hash, cap):
                await super().set_model_cap(key_hash, D(".0000000001") if cap == 0 else cap)
        client = WrongReadback(before)
        with self.assertRaisesRegex(contract.BudgetAdminError, "write_unconfirmed"):
            await policy.apply_prepared(client, prepared(before, "10", {"a": "100", "b": "0"}))


if __name__ == "__main__":
    unittest.main()
