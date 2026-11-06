"""Native exception/handler presentation checks; not an installed-image auth proof."""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Mapping
import copy
import enum
import importlib.util
import logging
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Final
import unittest
from unittest.mock import patch

from fastapi import HTTPException, status


HERE = Path(__file__).resolve()
UPSTREAM = Path(os.environ.get("GOAL584_LITELLM_SOURCE_ROOT", str(
    HERE.parents[3] / "local/goal584/litellm/upstream"))) / "litellm"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_nodes(path, *names):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
             and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError("Native source contract changed")
    return nodes


def execute(nodes, namespace):
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 "pinned_native_budget_error_source", "exec",
                 flags=__import__("__future__").annotations.compiler_flag), namespace)


class BudgetErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (UPSTREAM / "exceptions.py").exists():
            raise unittest.SkipTest("Pinned native exception source unavailable; exact-image proof required")
        cls.native = {"enum": enum, "Final": Final, "Mapping": Mapping,
                      "HTTPException": HTTPException, "status": status}
        cls.litellm = ModuleType("litellm")
        cls.litellm.budget_exceeded_status_code = 422
        cls.native["litellm"] = cls.litellm
        execute(source_nodes(UPSTREAM / "exceptions.py", "RateLimitErrorCategory", "RateLimitType",
                             "BudgetExceededError"), cls.native)
        cls.error_type = cls.native["BudgetExceededError"]
        cls.litellm.BudgetExceededError = cls.error_type
        cls.base = type("CustomLogger", (), {})  # Only the external callback base is doubled.
        logger_module = ModuleType("litellm.integrations.custom_logger")
        logger_module.CustomLogger = cls.base
        cls.module_entries = {"litellm": cls.litellm, "litellm.integrations.custom_logger": logger_module}
        with patch.dict(sys.modules, cls.module_entries):
            cls.adapter = load("budget_errors_under_test", HERE.parents[1] / "budget_errors.py")
        cls.assignment = load("budget_error_assignment_under_test", HERE.parents[1] / "assignment.py")

    def identity(self, **changes):
        fields = dict(user_id="native-user", token="private-hash", team_id=None, models=["wire-model"],
                      key_alias=self.assignment.assignment_alias("native-user", "wire-model"),
                      metadata=self.assignment.assignment_metadata("wire-model"),
                      budget_reservation={"held": 0.2}, spend=0.6)
        return SimpleNamespace(**(fields | changes))

    def error(self, entity="key", **changes):
        fields = dict(current_cost=0.6, max_budget=0.6, message="private alias sk-fragment and amounts",
                      llm_provider="synthetic", entity_type=entity, entity_id="private-hash")
        return self.error_type(**(fields | changes))

    def apply(self, error, identity=None, request=None):
        identity = self.identity() if identity is None else identity
        request = {"messages": [{"role": "user", "content": "private-chat"}]} if request is None else request
        with patch.object(self.adapter, "_assignment_matcher", return_value=self.assignment.assignment_matches):
            result = asyncio.run(self.adapter.handler.async_post_call_failure_hook(
                request_data=request, original_exception=error, user_api_key_dict=identity,
                traceback_str="private traceback"))
        self.assertIsNone(result)

    def native_block_error(self, blocked=True):
        tree = ast.parse((UPSTREAM / "proxy/auth/user_api_key_auth.py").read_text(encoding="utf-8"))
        owner = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                     and node.name == "validate_resolved_virtual_key")
        branch = next(node for node in ast.walk(owner) if isinstance(node, ast.If)
                      and ast.unparse(node.test) == "valid_token.blocked is True")
        namespace = {"valid_token": SimpleNamespace(blocked=blocked)}
        try:
            execute([copy.deepcopy(branch)], namespace)
        except Exception as error:
            self.assertIs(type(error), Exception)
            self.assertEqual(error.args, (self.adapter._NATIVE_BLOCKED_MESSAGE,))
            return error
        return None

    def test_exact_native_blocked_key_decision_only_changes_its_presentation(self):
        for flag in (False, None, 0, 1, "true"):
            self.assertIsNone(self.native_block_error(flag))
        error = self.native_block_error()
        identity = self.identity(blocked=True)
        identity_before = copy.deepcopy(vars(identity))
        reservation = identity.budget_reservation
        before = copy.deepcopy(vars(error))
        request = {"model": "wire-model", "messages": [{"role": "user", "content": "private-chat"}],
                   "metadata": {"payer_id": "spoof"}}
        request_before = copy.deepcopy(request)
        self.apply(error, identity, request)
        self.assertIs(type(error), Exception)
        self.assertEqual(vars(error), before)
        self.assertEqual(error.args, (self.adapter.BLOCKED_MESSAGE,))
        self.assertEqual(vars(identity), identity_before)
        self.assertIs(identity.budget_reservation, reservation)
        self.assertEqual(request, request_before)
        for private in ("/key/", "unblock", "admin.", "private-chat", "wire-model"):
            self.assertNotIn(private, str(error))

    def test_mutates_only_native_presentation_and_preserves_context_and_money(self):
        for entity, expected in (("key", self.adapter.MODEL_MESSAGE), ("user", self.adapter.USER_MESSAGE)):
            error = self.error(entity)
            before = copy.deepcopy(vars(error))
            identity = self.identity()
            reservation = identity.budget_reservation
            identity_before = copy.deepcopy(vars(identity))
            request = {"model": "wire-model", "messages": [{"role": "system", "content": "private-chat"}],
                       "metadata": {"payer_id": "spoof", "category": "service"}, "max_tokens": 5}
            request_before = copy.deepcopy(request)
            with patch.object(logging.getLogger("asyncio"), "disabled", True), self.assertNoLogs(level="DEBUG"):
                self.apply(error, identity, request)
            self.assertEqual(error.message, expected)
            self.assertEqual(str(error), expected)
            self.assertEqual(error.args, (expected,))
            self.assertEqual({k: v for k, v in vars(error).items() if k != "message"},
                             {k: v for k, v in before.items() if k != "message"})
            self.assertIs(type(error), self.error_type)
            self.assertEqual(error.status_code, 422)
            self.assertIs(identity.budget_reservation, reservation)
            self.assertEqual(vars(identity), identity_before)
            self.assertEqual(request, request_before)
            for private in ("private-chat", "private-hash", "wire-model", "sk-fragment", "0.6", "spoof"):
                self.assertNotIn(private, error.message)

    def test_model_label_requires_real_canonical_assignment_and_same_key_entity(self):
        cases = [dict(key_alias="looks-like-a-budget-alias"), dict(metadata={}), dict(team_id="team"),
                 dict(models=["wire-model", "other"]), dict(models=[]), dict(user_id=None),
                 dict(token="other-key"), dict(metadata={"owui_budget_namespace": "forged"})]
        for changes in cases:
            error = self.error()
            self.apply(error, self.identity(**changes))
            self.assertEqual(error.message, self.adapter.GENERIC_MESSAGE)
        error = self.error()
        self.apply(error, SimpleNamespace())  # Builder failure may not carry a resolved identity.
        self.assertEqual(error.message, self.adapter.GENERIC_MESSAGE)

    def test_unsigned_scope_and_category_do_not_choose_message(self):
        for category in ("service", "personal", "forged"):
            data = {"metadata": {"spend_logs_metadata": {"owui_budget": {"category": category}}},
                    "litellm_metadata": {"category": category, "model": "forged"}}
            error = self.error("user")
            self.apply(error, self.identity(), data)
            self.assertEqual(error.message, self.adapter.USER_MESSAGE)
            error = self.error()
            self.apply(error, SimpleNamespace(), data)
            self.assertEqual(error.message, self.adapter.GENERIC_MESSAGE)

    def test_other_native_entities_and_non_native_errors_remain_unchanged(self):
        for error in [self.error("team"), self.error("project"), self.error(None),
                      HTTPException(403, "denied"), ValueError("budget has been exceeded"),
                      ValueError(self.adapter._NATIVE_BLOCKED_MESSAGE),
                      Exception("Key is blocked."), Exception(self.adapter._NATIVE_BLOCKED_MESSAGE + " "),
                      Exception(self.adapter._NATIVE_BLOCKED_MESSAGE, "extra"),
                      SimpleNamespace(entity_type="user", message="not a native exception", args=())]:
            before = copy.deepcopy(vars(error))
            args = getattr(error, "args", None)
            self.apply(error)
            self.assertEqual(vars(error), before)
            self.assertEqual(getattr(error, "args", None), args)

    def test_assignment_loader_uses_shared_owner_and_failure_stays_generic(self):
        utility = ModuleType("litellm.proxy.types_utils.utils")
        calls = []
        def get_instance_fn(name, **kwargs):
            calls.append((name, kwargs))
            return self.assignment.assignment_matches
        utility.get_instance_fn = get_instance_fn
        self.adapter._assignment_matcher.cache_clear()
        error = self.error()
        with patch.dict(sys.modules, {"litellm.proxy.types_utils.utils": utility}):
            asyncio.run(self.adapter.handler.async_post_call_failure_hook({}, error, self.identity()))
        self.assertEqual(error.message, self.adapter.MODEL_MESSAGE)
        self.assertEqual(calls, [("employee_budget_assignment.assignment_matches",
                                 {"config_file_path": self.adapter.__file__})])
        self.adapter._assignment_matcher.cache_clear()
        for failure in (ImportError("private loader detail"), ValueError("private row detail")):
            error = self.error()
            with patch.object(self.adapter, "_assignment_matcher", side_effect=failure):
                asyncio.run(self.adapter.handler.async_post_call_failure_hook({}, error, self.identity()))
            self.assertEqual(error.message, self.adapter.GENERIC_MESSAGE)

    def test_actual_strict_native_reserve_with_remaining_balance_is_not_called_exhausted(self):
        namespace = dict(self.native)
        execute(source_nodes(UPSTREAM / "proxy/_types.py", "Litellm_EntityType", "ProxyErrorTypes", "ProxyException"), namespace)
        execute(source_nodes(UPSTREAM / "types/router.py", "RouterErrors"), namespace)
        execute(source_nodes(UPSTREAM / "proxy/auth/auth_exception_handler.py", "_as_proxy_exception"), namespace)
        source = UPSTREAM / "proxy/spend_tracking/budget_reservation.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        policy = [node for node in tree.body if
                  isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.name in {"_apply_over_budget_reservation_policy", "_raise_counter_budget_exceeded"}
                  or isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                  and node.target.id == "_COUNTER_ENTITY_TYPES"]
        self.assertEqual(len(policy), 3)
        # Only unrelated optional throttling is fixed off. The strict native
        # reservation branch and its native error constructor execute unchanged.
        namespace["_key_reservation_should_release_for_throttle"] = lambda *args: False
        execute(policy, namespace)
        for entity, identity, expected in (("Key", self.identity(), self.adapter.MODEL_MESSAGE),
                                            ("Key", SimpleNamespace(), self.adapter.GENERIC_MESSAGE),
                                            ("User", self.identity(), self.adapter.USER_MESSAGE)):
            counter = SimpleNamespace(max_budget=0.8, entity_type=entity, entity_id="private-hash",
                                      spend_log_entity_id=None, counter_key="spend:synthetic")
            with self.assertRaises(self.error_type) as caught:
                asyncio.run(namespace["_apply_over_budget_reservation_policy"](
                    counter, None, {}, [], reservation_cost=0.7, current_spend=0.9,
                    fail_closed_budget_enforcement=True))
            error = caught.exception
            self.assertAlmostEqual(error.current_cost, 0.2)
            self.assertEqual(error.max_budget, 0.8)
            self.assertLess(error.current_cost, error.max_budget)
            before = copy.deepcopy(vars(error))
            self.apply(error, identity)
            self.assertEqual({k: v for k, v in vars(error).items() if k != "message"},
                             {k: v for k, v in before.items() if k != "message"})
            self.assertEqual(error.args, (expected,))
            response = namespace["_as_proxy_exception"](error).to_dict()
            self.assertEqual(response, {"message": expected, "type": "budget_exceeded", "param": None, "code": "422"})
            self.assertNotIn("исчерпан", response["message"].lower())

    def test_exact_native_dispatch_and_auth_handler_keep_status_and_budget_error_type(self):
        namespace = {**self.native, "CustomLogger": self.base,
                     "EMPTY_MAPPING": {},
                     "verbose_proxy_logger": logging.getLogger("native-budget-error-test")}
        execute(source_nodes(UPSTREAM / "types/router.py", "RouterErrors"), namespace)
        execute(source_nodes(UPSTREAM / "proxy/_types.py", "ProxyErrorTypes", "ProxyException"), namespace)
        execute(source_nodes(UPSTREAM / "proxy/auth/auth_utils.py", "mark_invalid_virtual_key_error"), namespace)
        execute(source_nodes(UPSTREAM / "proxy/auth/model_access_denied.py", "ModelAccessDeniedHTTPException"), namespace)
        # Only the unrelated DB-outage classifier is fixed off. The blocked
        # decision, failure dispatch and auth_error/401 conversion are native.
        namespace["PrismaDBExceptionHandler"] = SimpleNamespace(is_database_service_unavailable_error=lambda e: False)
        execute(source_nodes(UPSTREAM / "proxy/auth/auth_exception_handler.py", "_as_proxy_exception",
                             "_with_client_context"), namespace)
        logging_tree = ast.parse((UPSTREAM / "proxy/utils.py").read_text(encoding="utf-8"))
        owner = next(n for n in logging_tree.body if isinstance(n, ast.ClassDef) and n.name == "ProxyLogging")
        dispatch = copy.deepcopy(next(n for n in owner.body if isinstance(n, ast.AsyncFunctionDef)
                                      and n.name == "post_call_failure_hook"))
        start = next(i for i, n in enumerate(dispatch.body) if isinstance(n, ast.AnnAssign)
                     and isinstance(n.target, ast.Name) and n.target.id == "transformed_exception")
        dispatch.body = dispatch.body[start:]
        execute([dispatch], namespace)
        native_handler = source_nodes(UPSTREAM / "proxy/auth/auth_exception_handler.py",
                                      "UserAPIKeyAuthExceptionHandler")[0]
        handler = copy.deepcopy(next(n for n in native_handler.body if isinstance(n, ast.AsyncFunctionDef)))
        handler.decorator_list = []
        start = next(i for i, n in enumerate(handler.body) if isinstance(n, ast.If))
        # The final else is the actual error path. Execute its callback/conversion
        # tail, excluding DB/telemetry/log construction rather than copying policy.
        error_path = handler.body[start].orelse
        start = next(i for i, n in enumerate(error_path) if isinstance(n, ast.AnnAssign)
                     and isinstance(n.target, ast.Name) and n.target.id == "transformed_exception")
        handler.body = error_path[start:]
        execute([handler], namespace)
        identity = self.identity()
        namespace.update(user_api_key_dict=identity, requester_ip=None, user_agent=None,
                         is_invalid_virtual_key=False, is_quiet_log=False)
        async def dispatch_call(**kwargs):
            namespace["redacted_traceback_str"] = None
            return await namespace["post_call_failure_hook"](None, **kwargs)
        namespace["proxy_logging_obj"] = SimpleNamespace(post_call_failure_hook=dispatch_call)
        self.litellm.callbacks = [self.adapter.handler]
        for entity, expected, resolved in (("key", self.adapter.MODEL_MESSAGE, identity),
                                           ("user", self.adapter.USER_MESSAGE, identity),
                                           ("key", self.adapter.GENERIC_MESSAGE, SimpleNamespace())):
            namespace["user_api_key_dict"] = resolved
            # The native strict reserve can reject R=.7 while spend=.2 and cap=.8.
            # Its presentation must cover that positive-remaining-budget case too.
            for current, maximum in ((0.6, 0.6), (0.2, 0.8)):
                with self.subTest(entity=entity, current=current, maximum=maximum):
                    error = self.error(entity, current_cost=current, max_budget=maximum)
                    before = copy.deepcopy(vars(error))
                    with patch.object(self.adapter, "_assignment_matcher", return_value=self.assignment.assignment_matches):
                        with self.assertRaises(namespace["ProxyException"]) as caught:
                            asyncio.run(namespace["_handle_authentication_error"](
                                e=error, request=None, request_data={"model": "wire-model"}, route="/v1/chat/completions",
                                parent_otel_span=None, api_key="private-key"))
                    response = caught.exception.to_dict()
                    self.assertEqual(response, {"message": expected, "type": "budget_exceeded", "param": None, "code": "422"})
                    self.assertEqual({k: v for k, v in vars(error).items() if k != "message"},
                                     {k: v for k, v in before.items() if k != "message"})
                    self.assertEqual(error.args, (expected,))
                    self.assertNotIn("исчерпан", response["message"].lower())
                    self.assertIn("Недостаточно", response["message"])
        before_response = None
        identity = self.identity(blocked=True)
        namespace["user_api_key_dict"] = identity
        identity_before = copy.deepcopy(vars(identity))
        for callbacks in ([], [self.adapter.handler]):
            self.litellm.callbacks = callbacks
            error = self.native_block_error()
            data = {"model": "wire-model", "messages": [{"role": "user", "content": "private-chat"}]}
            original_data = copy.deepcopy(data)
            with self.assertRaises(namespace["ProxyException"]) as caught:
                asyncio.run(namespace["_handle_authentication_error"](
                    e=error, request=None, request_data=data, route="/v1/chat/completions",
                    parent_otel_span=None, api_key="private-key"))
            response = caught.exception.to_dict()
            self.assertEqual({key: value for key, value in response.items() if key != "message"},
                             {"type": "auth_error", "param": "None", "code": "401"})
            self.assertIs(type(error), Exception)
            self.assertEqual(data, original_data)
            self.assertEqual(vars(identity), identity_before)
            if callbacks:
                self.assertEqual(response["message"], "Authentication Error, " + self.adapter.BLOCKED_MESSAGE)
                self.assertEqual({key: value for key, value in response.items() if key != "message"},
                                 {key: value for key, value in before_response.items() if key != "message"})
                self.assertNotIn("/key/unblock", response["message"])
            else:
                before_response = response
                self.assertEqual(response["message"], "Authentication Error, " + self.adapter._NATIVE_BLOCKED_MESSAGE)


if __name__ == "__main__":
    unittest.main()
