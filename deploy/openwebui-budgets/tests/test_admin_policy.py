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

    async def create_model_assignment(self, user_id, model):
        self.record("create", model, D(0))
        created = contract.ModelBudget(model, "c" * 64, "private-alias-new", D(0), D(0),
                                        "1mo", "2026-12-01T00:00:00Z", False)
        self.state = replace(self.state, models=tuple(created if m.model == model else m for m in self.state.models))
        return created


class PolicyTests(unittest.TestCase):
    def test_balance_plan_is_exact_bounded_signed_snapshot_without_actor_or_source_override(self):
        value = {"schema": 1, "type": "provider_balance_snapshot", "account_id": "gateway-main",
                 "expected_revision": "a" * 64, "amount": "-1.20", "currency": "USD",
                 "observed_at": "2026-11-11T10:00:00Z"}
        self.assertEqual(policy.parse_balance_plan(json.dumps(value)), value)
        self.assertEqual(policy.submission_kind(json.dumps(value)), "provider_balance_snapshot")
        for mutation in ({"amount": 1}, {"amount": "1e3"}, {"amount": "NaN"}, {"amount": "9" * 33},
                         {"currency": "usd"}, {"account_id": "bad/account"}, {"expected_revision": "A" * 64},
                         {"observed_at": "2026-11-11T10:00:00"}, {"actor": USER}, {"source": "api"}):
            with self.subTest(mutation=mutation), self.assertRaises(contract.BudgetAdminError):
                policy.parse_balance_plan(json.dumps(value | mutation))
        with self.assertRaisesRegex(contract.BudgetAdminError, "duplicate_json_field"):
            policy.parse_balance_plan(json.dumps(value).replace('"schema": 1', '"schema": 1, "schema": 1'))

    def test_new_assignment_projects_zero_share_without_claiming_native_cap_spend_or_period(self):
        before = state()
        pending = contract.ModelBudget("new", None, None, None, None, None, None, None, pending=True)
        expanded = replace(before, models=(*before.models, pending))
        public = policy.public_employee({"user_id": USER, "name": "Ada", "email": "a@example.invalid"}, expanded)
        self.assertEqual([m["share_percent"] for m in public["models"]], ["50", "50", "0"])
        self.assertEqual(public["models"][-1], {"id": "new", "label": "new", "pending": True,
            "cap_usd": None, "spend_usd": None, "remaining_usd": None, "budget_duration": None,
            "budget_reset_at": None, "blocked": None, "share_percent": "0"})
        self.assertEqual((public["budget_usd"], public["spend_usd"], public["remaining_usd"]), ("10", "1", "9"))
        self.assertNotEqual(policy.revision(before), policy.revision(expanded))
        with self.assertRaisesRegex(contract.BudgetAdminError, "invalid_pending_assignment"):
            policy.public_employee({"user_id": USER}, replace(expanded, models=(replace(pending, spend=D(0)),)))

    def test_removed_models_do_not_redistribute_remaining_native_shares(self):
        before = state()
        active_subset = replace(before, models=(before.models[0],))
        public = policy.public_employee({"user_id": USER, "name": "Ada", "email": "a@example.invalid"}, active_subset)
        self.assertEqual(public["models"][0]["share_percent"], "")
        self.assertEqual(public["models"][0]["cap_usd"], "5")
        self.assertEqual(public["budget_usd"], "10")

    def test_share_rounding_residual_preserves_native_zero_caps_and_pending_assignments(self):
        base = state()
        before = replace(base, max_budget=D(3), models=tuple(
            replace(base.models[0], model=model, max_budget=cap)
            for model, cap in (("a", D(1)), ("b", D(1)), ("c", D(1)), ("z", D(0)))))
        pending = contract.ModelBudget("zz", None, None, None, None, None, None, None, pending=True)
        before = replace(before, models=(*before.models, pending))
        original_revision = policy.revision(before)
        public = policy.public_employee({"user_id": USER, "name": "Ada", "email": "a@example.invalid"}, before)
        shares = {model["id"]: D(model["share_percent"]) for model in public["models"]}
        self.assertEqual(shares, {"a": D("33.3333"), "b": D("33.3333"), "c": D("33.3334"),
                                  "z": D(0), "zz": D(0)})
        self.assertEqual(sum(shares.values()), 100)
        self.assertEqual(policy.revision(before), original_revision)
        change = prepared(before, "3", {model: str(share) for model, share in shares.items()})
        self.assertEqual(dict(change.new_caps)["z"], 0)
        self.assertEqual(dict(change.new_caps)["zz"], 0)

    def test_presence_projection_maps_only_true_to_unknown_without_changing_native_values(self):
        before = state()
        identity = {'user_id': USER, 'name': 'Ada', 'email': 'ada@example.invalid', 'models': ('a', 'b')}
        original = policy.public_employee(identity, before)
        observations = {'a': {'unknown_confirmed': True, 'as_of': '2026-11-08T10:00:00+00:00'},
                        'b': {'unknown_confirmed': False, 'as_of': '2026-11-08T10:00:01+00:00'}}
        public = policy.public_employee(identity, before, unknown_presence=observations)
        self.assertEqual(public['expense_status'], 'unknown')
        self.assertEqual(public['expense_as_of'], observations['a']['as_of'])
        self.assertEqual([m['expense_status'] for m in public['models']], ['unknown', 'unavailable'])
        self.assertEqual({k: v for k, v in public.items() if not k.startswith('expense_') and k != 'models'},
                         {k: v for k, v in original.items() if k != 'models'})
        for new, old in zip(public['models'], original['models']):
            self.assertEqual({k: v for k, v in new.items() if not k.startswith('expense_')}, old)
        self.assertNotIn('known_subtotal_usd', public)
        for private in ('a'*64, 'private-alias', 'unknown_confirmed', 'scanned_rows', 'pagination_complete'):
            self.assertNotIn(private, json.dumps(public))
        self.assertEqual(policy.public_employee(identity, before, unknown_presence=None), original)

    def test_presence_missing_false_or_bad_primitive_is_unavailable_never_known_zero(self):
        identity = {'user_id': USER, 'name': 'Ada', 'email': 'ada@example.invalid', 'models': ('a', 'b')}
        for values in ({}, {'a': {'unknown_confirmed': False, 'as_of': 'source-time'}},
                       {'a': {'unknown_confirmed': 1, 'as_of': 'source-time'}},
                       {'a': {'unknown_confirmed': True, 'as_of': None}},
                       {'a': {'unknown_confirmed': True, 'as_of': 'source-time', 'raw': 'not allowed'}}):
            with self.subTest(values=values):
                public = policy.public_employee(identity, state(), unknown_presence=values)
                self.assertEqual(public['expense_status'], 'unavailable')
                self.assertEqual([m['expense_status'] for m in public['models']], ['unavailable', 'unavailable'])
                self.assertEqual(public['spend_usd'], '1')
                self.assertEqual(public['remaining_usd'], '9')

    def test_presence_extra_model_or_mismatched_allowed_set_cannot_enter_projection(self):
        identity = {'user_id': USER, 'name': 'Ada', 'email': 'ada@example.invalid', 'models': ('a', 'b')}
        with self.assertRaisesRegex(contract.BudgetAdminError, 'invalid_expense_observations'):
            policy.public_employee(identity, state(), unknown_presence={'foreign': {'unknown_confirmed': True, 'as_of': 'x'}})
        for models in (('a',), ('a', 'b', 'foreign'), ('a', 'a')):
            with self.subTest(models=models), self.assertRaisesRegex(contract.BudgetAdminError, 'invalid_models'):
                policy.public_employee(identity | {'models': models}, state(), unknown_presence={})

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

    def test_public_projection_preserves_native_block_tristate_and_revision(self):
        identity = {"user_id": USER, "name": "Ada", "email": "ada@example.invalid"}
        before = state()
        revisions = set()
        for blocked in (True, False, None):
            observed = replace(before, models=(before.models[1], replace(before.models[0], blocked=blocked)))
            row = policy.public_employee(identity, observed)
            self.assertEqual([model["id"] for model in row["models"]], ["a", "b"])
            self.assertIs(row["models"][0]["blocked"], blocked)
            self.assertIs(row["models"][1]["blocked"], False)
            self.assertEqual(row["revision"], policy.revision(observed))
            revisions.add(row["revision"])
            self.assertEqual([(model["cap_usd"], model["spend_usd"], model["share_percent"])
                              for model in row["models"]], [("5", "0.4", "50"), ("5", "0.6", "50")])
        self.assertEqual(len(revisions), 3)
        self.assertIs(before.models[0].blocked, False)

    def test_public_projection_keeps_native_periods_and_scalar_remaining(self):
        before = state()
        identity = {"user_id": USER, "name": "Ada", "email": "ada@example.invalid"}
        for cap, spend, expected in ((D("0"), D("0"), "0"), (D("1"), D("2"), "-1"),
                                     (None, D("2"), None)):
            with self.subTest(cap=cap, spend=spend):
                model = replace(before.models[0], max_budget=cap, spend=spend,
                                budget_duration="30d", budget_reset_at="2027-02-03T04:05:06Z")
                observed = replace(before, max_budget=cap, spend=spend, models=(model,))
                row = policy.public_employee(identity, observed)
                self.assertEqual((row["budget_duration"], row["budget_reset_at"]),
                                 (observed.budget_duration, observed.budget_reset_at))
                self.assertEqual(row["remaining_usd"], expected)
                self.assertEqual((row["models"][0]["budget_duration"], row["models"][0]["budget_reset_at"]),
                                 (model.budget_duration, model.budget_reset_at))
                self.assertEqual(row["models"][0]["remaining_usd"], expected)

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


class BootstrapPolicyTests(unittest.TestCase):
    labels = {"a": "Model A", "b": "Model B"}

    def template_plan(self):
        return {"schema": 1, "type": "employee_budget_template",
                "expected_revision": policy.template_revision(None, self.labels),
                "budget_usd": "40", "shares": {"a": "100", "b": "0"}, "budget_duration": "1mo"}

    def test_template_is_exact_config_and_does_not_encode_personal_state(self):
        value = policy.parse_template_plan(json.dumps(self.template_plan()), None, self.labels)
        self.assertEqual(value, {"budget_usd": "40", "shares": {"a": "100", "b": "0"}, "budget_duration": "1mo"})
        public = policy.template_public(value, self.labels)
        self.assertEqual(public["budget_usd"], "40")
        self.assertEqual(public["shares"][1]["share_percent"], "0")
        self.assertNotEqual(public["revision"], policy.template_revision(None, self.labels))

    def test_existing_template_expands_with_zero_shares_and_preserves_existing_values(self):
        template = policy.parse_template_plan(json.dumps(self.template_plan()), None, self.labels)
        expanded = policy.template_value(template, {**self.labels, "new": "New"})
        self.assertEqual(expanded, {**template, "shares": {"a": "100", "b": "0", "new": "0"}})
        self.assertEqual(template["shares"], {"a": "100", "b": "0"})
        self.assertNotEqual(policy.template_revision(template, self.labels),
                            policy.template_revision(template, {**self.labels, "new": "New"}))
        with self.assertRaisesRegex(contract.BudgetAdminError, "template_models_changed"):
            policy.template_value(template, {"a": "A"})

    def test_template_rejects_stale_unknown_models_precision_and_mixed_operations(self):
        for update in ({"expected_revision": "0" * 64}, {"shares": {"a": "100"}},
                       {"budget_usd": 40}, {"budget_duration": "30d"}, {"changes": []},
                       {"budget_usd": "0.123456789012345678901"}):
            with self.subTest(update=update), self.assertRaises(contract.BudgetAdminError):
                policy.parse_template_plan(json.dumps(self.template_plan() | update), None, self.labels)
        with self.assertRaisesRegex(contract.BudgetAdminError, "duplicate_json_field"):
            policy.parse_template_plan('{"type":"employee_budget_template","type":"employee_budget_plan"}', None, self.labels)

    def test_absent_revision_binds_employee_allowed_models_and_template(self):
        rev = policy.absence_revision(USER, ("a", "b"), policy.template_revision(None, self.labels))
        value = {"schema": 1, "type": "employee_budget_initialize", "changes": [{
            "user_id": USER, "expected_revision": rev, "budget_usd": "40", "shares": {"a": "100", "b": "0"}}]}
        change = policy.parse_initialization(json.dumps(value))[0]
        absent = contract.EmployeeBudgetInspection(USER, ("a", "b"), "absent")
        identity = {"user_id": USER, "models": ("a", "b")}
        self.assertEqual(policy.prepare_initialization(change, absent, identity, None, self.labels),
                         (("a", D(40)), ("b", D(0))))
        for observation in (replace(absent, kind="incomplete"), replace(absent, kind="conflict"),
                            replace(absent, kind="ready", employee_budget=state())):
            with self.assertRaisesRegex(contract.BudgetAdminError, "employee_not_absent"):
                policy.prepare_initialization(change, observation, identity, None, self.labels)
        template = policy.parse_template_plan(json.dumps(self.template_plan()), None, self.labels)
        with self.assertRaisesRegex(contract.BudgetAdminError, "stale_snapshot"):
            policy.prepare_initialization(change, absent, identity, template, self.labels)
        with self.assertRaisesRegex(contract.BudgetAdminError, "stale_snapshot"):
            policy.prepare_initialization(change, absent, identity | {"models": ("a",)}, None, self.labels)

    def test_pending_does_not_renormalize_template_or_imply_zero_spend(self):
        template = policy.parse_template_plan(json.dumps(self.template_plan() | {
            "shares": {"a": "50", "b": "50"}}), None, self.labels)
        identity = {"user_id": USER, "name": "Ada", "email": "a@example.invalid", "models": ("a",)}
        absent = contract.EmployeeBudgetInspection(USER, ("a",), "absent")
        public = policy.public_pending(identity, absent, template, self.labels)
        self.assertIsNone(public["suggested_budget_usd"])
        self.assertIsNone(public["suggested_shares"])
        self.assertNotIn("spend_usd", public)
        matching = policy.public_pending(identity | {"models": ("a", "b")},
            replace(absent, allowed_wire_models=("a", "b")), template, self.labels)
        self.assertEqual(matching["suggested_shares"], {"a": "50", "b": "50"})

    def test_pending_projects_zero_excluded_model_without_changing_global_revision(self):
        models = tuple(f"model-{index}" for index in range(9))
        labels = {model: model for model in (*models, "private")}
        shares = {model: "11.1111" for model in models[:-1]} | {models[-1]: "11.1112"}
        template = {"budget_usd": "20", "shares": shares, "budget_duration": "1mo"}
        identity = {"user_id": USER, "name": "Ada", "email": "a@example.invalid", "models": models}
        absent = contract.EmployeeBudgetInspection(USER, models, "absent")
        public = policy.public_pending(identity, absent, template, labels)
        self.assertEqual(public["suggested_budget_usd"], "20")
        self.assertEqual(public["suggested_shares"], shares)
        self.assertNotIn("private", public["suggested_shares"])
        self.assertEqual(sum(map(D, public["suggested_shares"].values())), D(100))
        self.assertEqual(public["revision"], policy.absence_revision(USER, models,
            policy.template_revision(template, labels)))
        self.assertNotEqual(public["revision"], policy.absence_revision(USER, models,
            policy.template_revision(template, {model: model for model in models})))
        change = policy.parse_initialization(json.dumps({"schema": 1, "type": "employee_budget_initialize",
            "changes": [{"user_id": USER, "expected_revision": public["revision"],
                         "budget_usd": public["suggested_budget_usd"], "shares": public["suggested_shares"]}]}))[0]
        caps = policy.prepare_initialization(change, absent, identity, template, labels)
        self.assertEqual(caps[0][1], D("2.22222"))
        self.assertEqual(caps[-1][1], D("2.22224"))
        self.assertEqual(sum(cap for _, cap in caps), D(20))
        with self.assertRaisesRegex(contract.BudgetAdminError, "stale_snapshot"):
            policy.prepare_initialization(change, absent, identity, template | {"budget_usd": "21"}, labels)
        self.assertNotIn("private", template["shares"])


class MutationTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_model_created_only_on_apply_at_zero_with_existing_state_preserved(self):
        previous = state()
        pending = contract.ModelBudget("new", None, None, None, None, None, None, None, pending=True)
        before = replace(previous, models=(*previous.models, pending))
        client = NativeClient(before)
        change = prepared(before, shares={"a": "50", "b": "50", "new": "0"})
        self.assertEqual(client.writes, [])
        after = await policy.apply_prepared(client, change)
        self.assertEqual(client.writes, [("create", "new", D(0))])
        self.assertEqual(after.models[:2], previous.models)
        self.assertEqual((after.max_budget, after.spend, after.budget_reset_at),
                         (previous.max_budget, previous.spend, previous.budget_reset_at))
        self.assertFalse(after.models[-1].pending)
        self.assertEqual((after.models[-1].max_budget, after.models[-1].spend), (D(0), D(0)))

    async def test_pending_model_created_at_zero_before_confirmed_nonzero_allocation(self):
        previous = state()
        pending = contract.ModelBudget("new", None, None, None, None, None, None, None, pending=True)
        before = replace(previous, models=(*previous.models, pending))
        client = NativeClient(before)
        after = await policy.apply_prepared(client, prepared(before, shares={"a": "40", "b": "40", "new": "20"}))
        self.assertEqual(client.writes, [("model", "a" * 64, D(4)), ("model", "b" * 64, D(4)),
                                         ("create", "new", D(0)), ("model", "c" * 64, D(2))])
        self.assertEqual([m.max_budget for m in after.models], [D(4), D(4), D(2)])
        self.assertEqual([m.key_hash for m in after.models[:2]], [m.key_hash for m in previous.models])

    async def test_cap_change_preserves_each_native_block_state(self):
        for blocked in (True, False, None):
            with self.subTest(blocked=blocked):
                original = state()
                before = replace(original, models=(replace(original.models[0], blocked=blocked), original.models[1]))
                client = NativeClient(before)
                after = await policy.apply_prepared(client, prepared(before, "20"))
                self.assertIs(after.models[0].blocked, blocked)
                self.assertEqual([model.blocked for model in after.models], [model.blocked for model in before.models])
                self.assertEqual(after.spend, before.spend)
                self.assertEqual(after.budget_reset_at, before.budget_reset_at)

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
