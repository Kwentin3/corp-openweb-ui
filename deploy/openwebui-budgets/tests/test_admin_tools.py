"""Native admin adapter checks with real policy/UI/contracts; external owners only mocked."""
import copy
from dataclasses import replace
from decimal import Decimal
import importlib.util
import inspect
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import NAMESPACE_URL, uuid5

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
load("employee_budget_assignment", "assignment.py")
load("employee_budget_admin_client", "admin_client.py")
policy = load("employee_budget_admin_policy", "admin_policy.py")
load("employee_budget_admin_ui", "admin_ui.py")
load("employee_budget_webui_model_binding", "webui_model_binding.py")
extension = load("admin_tools_under_test", "admin_tools.py")
ADMIN, USER, USER2, CHAT, ANSWER, PARENT, OTHER = (str(uuid5(NAMESPACE_URL, name)) for name in
    ("tool-admin", "tool-user", "tool-user2", "tool-chat", "tool-answer", "tool-parent", "tool-other"))
MODELS = ("goal584-a", "goal584-b")
KEY = "sk-synthetic-only-admin-key"
URL = "http://native-proxy.invalid"


def module(**values):
    result = ModuleType("native_external_owner")
    result.__dict__.update(values)
    return result


def state(user_id):
    models = tuple(contract.ModelBudget(m, user_id + "-hash-" + m, "native-alias-" + m,
        Decimal("5"), Decimal(".2"), "30d", "2026-12-01T00:00:00Z", False) for m in MODELS)
    return contract.EmployeeBudget(user_id, Decimal("10"), Decimal(".4"), "30d", "2026-12-01T00:00:00Z", models)


class AdminToolsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.admin = SimpleNamespace(id=ADMIN, role="admin")
        self.employees = [SimpleNamespace(id=USER, role="user", name="Ada", email="ada@example.invalid", info={"department": "R&D"}),
                          SimpleNamespace(id=USER2, role="user", name="Bob", email="bob@example.invalid", info={"department": 123})]
        self.message = {"id": ANSWER, "role": "assistant", "user_id": ADMIN, "parentId": PARENT}
        self.parent = {"id": PARENT, "role": "user", "user_id": ADMIN, "content": ""}
        self.users = SimpleNamespace(get_user_by_id=AsyncMock(side_effect=lambda _: self.admin),
            get_users=AsyncMock(side_effect=lambda **_: {"users": self.employees, "total": len(self.employees)}))
        self.chats = SimpleNamespace(get_accessible_chat_by_id=AsyncMock(return_value=SimpleNamespace(user_id=ADMIN)),
            get_message_by_id_and_message_id=AsyncMock(side_effect=lambda chat, msg:
                self.message if msg == ANSWER else self.parent if msg == PARENT else None))
        self.config = {"ledger_base_url": URL, "ledger_read_key": "existing-viewer-secret", "ledger_admin_key": KEY}
        self.functions = SimpleNamespace(get_function_valves_by_id=AsyncMock(side_effect=lambda _: self.config))
        async def save_config(function_id, value):
            self.assertEqual(function_id, "employee_budget_cost")
            self.config = copy.deepcopy(value)
            return SimpleNamespace(id=function_id)
        self.functions.update_function_valves_by_id = AsyncMock(side_effect=save_config)
        self.denied = set()

        async def access(user, model):
            if (user.id, model["id"]) in self.denied:
                raise Exception("Model not found")
        self.access = AsyncMock(side_effect=access)
        self.connection = AsyncMock(return_value=(URL + "/v1", "existing-gateway-secret", {}))
        self.models = {m: {"id": m, "name": m, "owned_by": "openai"} for m in MODELS}
        self.request = SimpleNamespace(state=SimpleNamespace(direct=False, internal=False),
            app=SimpleNamespace(state=SimpleNamespace(MODELS=self.models,
                OPENAI_MODELS={m: {"urlIdx": index} for index, m in enumerate(MODELS)})))
        self.metadata = {"user_id": ADMIN, "chat_id": CHAT, "message_id": ANSWER, "internal": False}
        self.states = {USER: state(USER), USER2: state(USER2)}
        self.writes, self.reads = [], []

        async def read(user_id, models):
            self.reads.append((user_id, models))
            return replace(self.states[user_id], models=tuple(m for m in self.states[user_id].models if m.model in models))

        async def user_cap(user_id, amount):
            self.writes.append(("user", user_id, amount))
            self.states[user_id] = replace(self.states[user_id], max_budget=amount)

        async def model_cap(key_hash, amount):
            self.writes.append(("model", key_hash, amount))
            for user_id, current in self.states.items():
                self.states[user_id] = replace(current, models=tuple(
                    replace(model, max_budget=amount) if model.key_hash == key_hash else model for model in current.models))

        self.client = SimpleNamespace(read_employee=AsyncMock(side_effect=read),
            set_user_cap=AsyncMock(side_effect=user_cap), set_model_cap=AsyncMock(side_effect=model_cap))
        async def inspect_employee(user_id, models):
            current = await self.client.read_employee(user_id, models)
            return contract.EmployeeBudgetInspection(user_id, models, "ready", current)
        self.client.inspect_employee = AsyncMock(side_effect=inspect_employee)
        self.session = object()
        native = {name: module() for name in ("open_webui", "open_webui.models", "open_webui.routers", "open_webui.utils")}
        native.update({"open_webui.env": module(VERSION="0.12.2"),
            "open_webui.models.users": module(Users=self.users), "open_webui.models.chats": module(Chats=self.chats),
            "open_webui.models.functions": module(Functions=self.functions),
            "open_webui.models.models": module(Models=SimpleNamespace(get_model_by_id=AsyncMock(
                return_value=SimpleNamespace(base_model_id=None)))),
            "open_webui.utils.models": module(check_model_access=self.access),
            "open_webui.routers.openai": module(get_openai_connection=self.connection),
            "open_webui.utils.model_ids": module(strip_provider_model_prefix=lambda value, _: value),
            "open_webui.utils.session_pool": module(get_session=AsyncMock(return_value=self.session))})
        self.native_patch = patch.dict(sys.modules, native)
        self.native_patch.start(); self.addCleanup(self.native_patch.stop)
        self.client_factory = patch.object(extension, "BudgetAdminClient", Mock(return_value=self.client))
        self.factory = self.client_factory.start(); self.addCleanup(self.client_factory.stop)
        self.tools = extension.Tools()
        self.tools.valves.managed_model_ids = list(MODELS)
        self.parent["content"] = self.plan()

    def template_plan(self):
        return json.dumps({"schema": 1, "type": "employee_budget_template",
            "expected_revision": policy.template_revision(self.config.get("default_budget_template"), MODELS),
            "budget_usd": "40", "shares": {MODELS[0]: "100", MODELS[1]: "0"}, "budget_duration": "1mo"})

    def initialization_plan(self):
        return json.dumps({"schema": 1, "type": "employee_budget_initialize", "changes": [{
            "user_id": USER, "expected_revision": policy.absence_revision(USER, MODELS,
                policy.template_revision(self.config.get("default_budget_template"), MODELS)),
            "budget_usd": "40", "shares": {MODELS[0]: "100", MODELS[1]: "0"}}]})

    def absent_employee(self):
        del self.states[USER]
        original = self.client.inspect_employee.side_effect
        async def inspect_employee(user_id, models):
            if user_id == USER and USER not in self.states:
                return contract.EmployeeBudgetInspection(USER, models, "absent", code="missing_native_user")
            return await original(user_id, models)
        self.client.inspect_employee.side_effect = inspect_employee
        async def initialize(user_id, caps, total_cap, secret, *, before_write):
            for kind in ("new_user", "new_model_a", "new_model_b"):
                await before_write()
                self.writes.append((kind, user_id, total_cap))
            initial = state(user_id)
            self.states[user_id] = replace(initial, max_budget=total_cap, spend=Decimal(0),
                models=tuple(replace(m, max_budget=dict(caps)[m.model], spend=Decimal(0)) for m in initial.models))
            return self.states[user_id]
        self.client.initialize_employee = AsyncMock(side_effect=initialize)

    def plan(self, *, target=USER, budget="20"):
        return json.dumps({"schema": 1, "type": "employee_budget_plan", "changes": [{
            "user_id": target, "expected_revision": policy.revision(self.states[USER]),
            "budget_usd": budget, "shares": {MODELS[0]: "75", MODELS[1]: "25"}}]})

    async def open(self, view="{}"):
        return await self.tools.open_budget_form(view, __request__=self.request,
            __user__={"id": ADMIN}, __metadata__=self.metadata)

    async def apply(self, callback):
        return await self.tools.apply_budget_form(__request__=self.request, __user__={"id": ADMIN},
            __metadata__=self.metadata, __event_call__=callback)

    def html(self, result):
        response, context = result
        self.assertEqual(response.headers["content-disposition"], "inline")
        text = response.body.decode()
        for private in (KEY, URL, "existing-gateway-secret", "existing-viewer-secret", USER + "-hash-"):
            self.assertNotIn(private, text)
            self.assertNotIn(private, str(context))
        return text

    async def test_open_uses_native_directory_access_binding_and_existing_url_owner(self):
        self.denied.add((USER2, MODELS[1]))
        text = self.html(await self.open('{"group_by":"department"}'))
        self.assertIn("Ada", text); self.assertIn("Bob", text); self.assertIn("R&amp;D", text)
        self.users.get_users.assert_awaited_with(filter={"roles": ["user"]}, skip=0, limit=101)
        self.assertIn((USER2, (MODELS[0],)), self.reads)
        self.assertEqual(self.access.await_count, 4)
        self.factory.assert_called_with(self.session, URL, KEY)
        self.assertNotIn("ledger_base_url", self.tools.valves.model_dump())
        self.assertEqual(self.writes, [])

    async def test_public_tool_valves_contract_has_no_operator_credential(self):
        fields = {"managed_model_ids", "employee_limit"}
        self.assertEqual(set(self.tools.valves.model_dump()), fields)
        self.assertEqual(set(self.tools.Valves.model_json_schema()["properties"]), fields)
        for output in (self.tools.valves.model_dump(), self.tools.Valves.model_json_schema()):
            self.assertNotIn(KEY, json.dumps(output))
            self.assertNotIn("operator_key", json.dumps(output))
            self.assertNotIn("ledger_admin_key", json.dumps(output))

    async def test_client_reads_fresh_admin_key_from_existing_function_config(self):
        self.html(await self.open())
        self.factory.assert_called_with(self.session, URL, KEY)
        rotated = "sk-synthetic-rotated-admin-key"
        self.config["ledger_admin_key"] = rotated
        result = await self.open()
        self.factory.assert_called_with(self.session, URL, rotated)
        self.assertNotIn(rotated, self.html(result))
        self.assertNotIn(rotated, str(result[1]))
        self.functions.get_function_valves_by_id.assert_has_awaits([
            unittest.mock.call("employee_budget_cost"), unittest.mock.call("employee_budget_cost")])

    async def test_missing_function_admin_key_never_uses_read_key_or_legacy_tool_key(self):
        # A stale loaded object may still carry the old field. Native persisted
        # ToolValves cleanup is the installer's responsibility, not this adapter's.
        self.tools.valves = SimpleNamespace(operator_key=KEY,
            managed_model_ids=list(MODELS), employee_limit=100)
        del self.config["ledger_admin_key"]
        with self.assertRaisesRegex(contract.BudgetAdminError, "invalid_configuration"):
            await self.open()
        self.factory.assert_not_called()
        self.assertEqual(self.reads, [])

    async def test_invalid_function_admin_key_fails_before_client_construction(self):
        for key in (None, "", False, True, 123):
            with self.subTest(key=key):
                self.config["ledger_admin_key"] = key
                with self.assertRaisesRegex(contract.BudgetAdminError, "invalid_configuration"):
                    await self.open()
        self.factory.assert_not_called()
        self.assertEqual(self.reads, [])

    async def test_role_and_context_fail_before_any_directory_or_client_query(self):
        for variant in ("user", "missing_actor", "direct", "aux", "temp", "foreign_assistant"):
            with self.subTest(variant=variant):
                old = (self.admin, self.request.state.direct, copy.deepcopy(self.metadata), copy.deepcopy(self.message))
                if variant == "user": self.admin = SimpleNamespace(id=ADMIN, role="user")
                if variant == "missing_actor": self.admin = None
                if variant == "direct": self.request.state.direct = True
                if variant == "aux": self.metadata["task"] = "title_generation"
                if variant == "temp": self.metadata["chat_id"] = "temporary-chat"
                if variant == "foreign_assistant": self.message["user_id"] = OTHER
                with self.assertRaises(contract.BudgetAdminError): await self.open()
                self.admin, self.request.state.direct, self.metadata, message = old
                self.message.clear(); self.message.update(message)
        self.assertEqual(self.reads, []); self.assertEqual(self.writes, [])
        self.users.get_users.assert_not_awaited(); self.factory.assert_not_called()

    async def test_zero_business_arguments_reads_exact_current_parent_and_confirms_owner_diff(self):
        self.metadata.update(messages=[{"content": self.plan(budget="999")}], budget_usd="999")
        self.assertEqual(list(inspect.signature(extension.Tools.apply_budget_form).parameters),
            ["self", "__request__", "__user__", "__metadata__", "__event_call__"])
        confirm = AsyncMock(return_value=True)
        text = self.html(await self.apply(confirm))
        self.assertEqual(self.states[USER].max_budget, Decimal("20"))
        self.assertEqual([m.max_budget for m in self.states[USER].models], [Decimal("15"), Decimal("5")])
        self.assertIn('value="20"', text)
        request = confirm.call_args.args[0]
        self.assertEqual(request["type"], "confirmation")
        self.assertIn("Ada", request["data"]["message"])
        self.assertIn("20", request["data"]["message"])
        self.assertNotIn("999", request["data"]["message"])
        self.chats.get_message_by_id_and_message_id.assert_any_await(CHAT, PARENT)
        with self.assertRaises(TypeError):
            await self.tools.apply_budget_form(budget_usd="999")

    async def test_raw_confirmation_must_be_literal_true(self):
        for approval in (False, 1, "true", {"confirmed": True}, {"error": "timeout"}):
            result = await self.apply(AsyncMock(return_value=approval))
            self.assertEqual(result[1]["status"], "cancelled")
            text = self.html(result)
            self.assertIn("отменены", text)
        self.assertEqual(self.writes, [])

    async def test_exact_parent_source_required_not_transformed_messages(self):
        for change in ({"role": "assistant"}, {"user_id": OTHER}, {"content": "not JSON"}):
            old = copy.deepcopy(self.parent)
            self.parent.update(change)
            with self.assertRaises(contract.BudgetAdminError): await self.apply(AsyncMock(return_value=True))
            self.parent.clear(); self.parent.update(old)
        self.assertEqual(self.writes, [])

    async def test_stale_revision_source_or_model_access_after_confirmation_cannot_write(self):
        for variant in ("revision", "source", "directory"):
            old_states, old_text = copy.deepcopy(self.states), self.parent["content"]
            async def confirm(_):
                if variant == "revision": self.states[USER] = replace(self.states[USER], max_budget=Decimal("21"))
                if variant == "source": self.parent["content"] = self.plan(budget="999")
                if variant == "directory": self.denied.add((USER, MODELS[1]))
                return True
            result = await self.apply(confirm)
            self.assertEqual(result[1]["status"], "partial_or_failed")
            text = self.html(result)
            self.assertIn("не завершены", text)
            self.assertEqual(self.writes, [])
            self.states, self.parent["content"] = old_states, old_text
            self.denied.clear()

    async def test_admin_role_changed_during_confirmation_blocks_fresh_data_and_writes(self):
        async def confirm(_):
            self.admin.role = "user"
            return True
        with self.assertRaisesRegex(contract.BudgetAdminError, "admin_required"):
            await self.apply(confirm)
        self.assertEqual(len(self.reads), 2)
        self.assertEqual(self.writes, [])

    async def test_admin_role_revoked_during_post_confirmation_http_reads_cannot_write(self):
        read_owner = self.client.read_employee.side_effect
        confirmed = False
        async def confirm(_):
            nonlocal confirmed
            confirmed = True
            return True
        async def read(user_id, models):
            result = await read_owner(user_id, models)
            if confirmed:
                self.admin.role = "user"
            return result
        self.client.read_employee.side_effect = read
        with self.assertRaisesRegex(contract.BudgetAdminError, "admin_required"):
            await self.apply(confirm)
        self.assertEqual(self.writes, [])

    async def test_admin_revoked_during_policy_read_cannot_reach_first_native_post(self):
        read_owner = self.client.read_employee.side_effect
        count = 0
        async def read(user_id, models):
            nonlocal count
            count += 1
            if count == 5:  # two initial + two refreshed directory reads, then policy read
                self.admin.role = "user"
            return await read_owner(user_id, models)
        self.client.read_employee.side_effect = read
        with self.assertRaisesRegex(contract.BudgetAdminError, "admin_required"):
            await self.apply(AsyncMock(return_value=True))
        self.assertEqual(self.writes, [])

    async def test_open_revoked_during_native_reads_does_not_return_private_html(self):
        read_owner = self.client.read_employee.side_effect
        async def read(user_id, models):
            value = await read_owner(user_id, models)
            self.admin.role = "user"
            return value
        self.client.read_employee.side_effect = read
        with self.assertRaisesRegex(contract.BudgetAdminError, "admin_required"):
            await self.open()

    async def test_apply_revoked_during_initial_or_canceled_reads_does_not_disclose(self):
        read_owner = self.client.read_employee.side_effect
        for revoke_at in (1, 3):
            with self.subTest(revoke_at=revoke_at):
                self.admin.role = "admin"
                count = 0
                async def read(user_id, models):
                    nonlocal count
                    count += 1
                    value = await read_owner(user_id, models)
                    if count == revoke_at:
                        self.admin.role = "user"
                    return value
                self.client.read_employee.side_effect = read
                confirmation = AsyncMock(return_value=False)
                with self.assertRaisesRegex(contract.BudgetAdminError, "admin_required"):
                    await self.apply(confirmation)
                if revoke_at == 1:
                    confirmation.assert_not_awaited()
                self.assertEqual(self.writes, [])

    async def test_partial_native_failure_rereads_committed_state_without_rollback_or_retry(self):
        self.client.set_model_cap.side_effect = contract.BudgetAdminError("native_http_503")
        text = self.html(await self.apply(AsyncMock(return_value=True)))
        self.assertEqual(self.states[USER].max_budget, Decimal("20"))
        self.assertEqual([m.max_budget for m in self.states[USER].models], [Decimal("5"), Decimal("5")])
        self.assertEqual(self.writes, [("user", USER, Decimal("20"))])
        self.client.set_model_cap.assert_awaited_once()
        self.assertGreaterEqual(len(self.reads), 5)
        self.assertIn('value="20"', text)
        self.assertIn("native_http_503", text)

    async def test_target_outside_directory_and_truncated_directory_fail_closed(self):
        self.parent["content"] = self.plan(target=OTHER)
        with self.assertRaisesRegex(contract.BudgetAdminError, "unknown_employee"):
            await self.apply(AsyncMock(return_value=True))
        self.tools.valves.employee_limit = 1
        with self.assertRaisesRegex(contract.BudgetAdminError, "directory_incomplete"):
            await self.open()

    async def test_template_save_preserves_private_config_and_personal_budgets(self):
        self.config["unrelated"] = {"keep": "existing-setting"}
        before_config, before_states = copy.deepcopy(self.config), copy.deepcopy(self.states)
        self.parent["content"] = self.template_plan()
        confirmation = AsyncMock(return_value=True)
        result = await self.apply(confirmation)
        self.assertEqual(result[1]["status"], "success")
        self.html(result)
        self.assertEqual({k: v for k, v in self.config.items() if k != "default_budget_template"}, before_config)
        self.assertEqual(self.config["default_budget_template"]["budget_usd"], "40")
        self.assertEqual(self.states, before_states)
        self.assertEqual(self.writes, [])
        self.assertIn("Существующие бюджеты", confirmation.call_args.args[0]["data"]["message"])

    async def test_template_cancel_or_changed_configuration_cannot_write(self):
        self.parent["content"] = self.template_plan()
        before = copy.deepcopy(self.config)
        result = await self.apply(AsyncMock(return_value=False))
        self.assertEqual(result[1]["status"], "cancelled")
        self.assertEqual(self.config, before)
        self.functions.update_function_valves_by_id.assert_not_awaited()
        async def confirm(_):
            self.config["ledger_admin_key"] = "sk-rotated-test-only"
            return True
        result = await self.apply(confirm)
        self.assertEqual(result[1]["status"], "partial_or_failed")
        self.functions.update_function_valves_by_id.assert_not_awaited()
        self.assertIn("stale_configuration", self.html(result))

    async def test_absent_employee_form_and_explicit_creation_keep_existing_budgets(self):
        self.absent_employee()
        before = copy.deepcopy(self.states[USER2])
        text = self.html(await self.open())
        self.assertIn("Бюджет не создан", text)
        self.assertIn("Расход: нет данных", text)
        self.assertNotIn(USER + '-hash-', text)
        self.parent["content"] = self.initialization_plan()
        result = await self.apply(AsyncMock(return_value=False))
        self.assertEqual(result[1]["status"], "cancelled")
        self.assertNotIn(USER, self.states)
        self.client.initialize_employee.assert_not_awaited()
        confirmed = AsyncMock(return_value=True)
        result = await self.apply(confirmed)
        self.assertEqual(result[1]["status"], "success")
        self.assertEqual(self.states[USER].max_budget, Decimal(40))
        self.assertEqual(self.states[USER2], before)
        self.assertEqual([w[0] for w in self.writes], ["new_user", "new_model_a", "new_model_b"])
        financial_diff = confirmed.call_args.args[0]["data"]["message"]
        self.assertIn("1mo", financial_diff)
        self.assertIn("1 личный бюджет и 2 назначений", financial_diff)
        self.assertIn("нет назначения → 40 USD", financial_diff)
        self.assertIn("нет назначения → 0 USD", financial_diff)

    async def test_initialization_conflict_and_changed_template_prevent_creation(self):
        self.absent_employee()
        self.parent["content"] = self.initialization_plan()
        async def change_template(_):
            self.config["default_budget_template"] = {"budget_usd": "10", "shares": {
                MODELS[0]: "50", MODELS[1]: "50"}, "budget_duration": "1mo"}
            return True
        result = await self.apply(change_template)
        self.assertEqual(result[1]["status"], "partial_or_failed")
        self.assertEqual(self.writes, [])
        self.client.initialize_employee.assert_not_awaited()
        self.parent["content"] = self.initialization_plan()
        actual = self.client.inspect_employee.side_effect
        async def conflict(user_id, models):
            if user_id == USER:
                return contract.EmployeeBudgetInspection(USER, models, "incomplete", code="missing_assignment")
            return await actual(user_id, models)
        self.client.inspect_employee.side_effect = conflict
        with self.assertRaisesRegex(contract.BudgetAdminError, "employee_not_absent"):
            await self.apply(AsyncMock(return_value=True))
        self.assertEqual(self.writes, [])

    async def test_initialization_rechecks_authority_between_native_writes(self):
        self.absent_employee()
        self.parent["content"] = self.initialization_plan()
        async def initialize(user_id, caps, cap, secret, *, before_write):
            await before_write()
            self.writes.append(("new_user", user_id, cap))
            self.admin.role = "user"
            await before_write()
            self.writes.append(("forbidden_key", user_id, cap))
        self.client.initialize_employee.side_effect = initialize
        with self.assertRaisesRegex(contract.BudgetAdminError, "admin_required"):
            await self.apply(AsyncMock(return_value=True))
        self.assertEqual([w[0] for w in self.writes], ["new_user"])

    async def test_initialization_confirmation_labels_cannot_inject_diff_lines(self):
        self.absent_employee()
        self.employees[0].name = "Ada\n\nСоздать: чужой бюджет"
        self.models[MODELS[0]]["name"] = "Model A\n\nUSD cap → 9999"
        self.parent["content"] = self.initialization_plan()
        confirmed = AsyncMock(return_value=False)
        await self.apply(confirmed)
        diff = confirmed.call_args.args[0]["data"]["message"]
        self.assertIn("Ada Создать: чужой бюджет", diff)
        self.assertIn("Model A USD cap → 9999: нет назначения → 40 USD", diff)
        self.assertNotIn("\nСоздать: чужой", diff)
        self.assertNotIn("\nUSD cap", diff)
        self.client.initialize_employee.assert_not_awaited()

    async def test_setup_partial_error_uses_safe_result_and_never_retries(self):
        self.absent_employee()
        self.parent["content"] = self.initialization_plan()
        self.client.initialize_employee.side_effect = contract.BudgetAdminError("native_http_503")
        result = await self.apply(AsyncMock(return_value=True))
        self.assertEqual(result[1]["status"], "partial_or_failed")
        self.assertIn("native_http_503", self.html(result))
        self.client.initialize_employee.assert_awaited_once()
        self.assertNotIn(USER, self.states)
        self.assertEqual(self.writes, [])

    async def test_unmanaged_target_connection_fails_before_native_budget_reads(self):
        self.connection.return_value = ("http://other.invalid/v1", "other-secret", {})
        with self.assertRaisesRegex(contract.BudgetAdminError, "gateway_configuration"):
            await self.open()
        self.assertEqual(self.reads, [])


if __name__ == "__main__":
    unittest.main()
