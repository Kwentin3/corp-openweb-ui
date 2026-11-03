"""Pinned native AST boundary checks; not installed-image/DB acceptance."""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Callable, Sequence
import copy
from dataclasses import FrozenInstanceError, dataclass, fields
from datetime import datetime, timezone
import importlib.util
import json
import logging
from pathlib import Path
import re
import sys
from types import MappingProxyType, ModuleType
from typing import Final, TypedDict
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve()
UPSTREAM = HERE.parents[3] / "local/goal584/litellm/upstream/litellm"


def tree(relative):
    return ast.parse((UPSTREAM / relative).read_text(encoding="utf-8"))


def selected(relative, names):
    nodes = [node for node in tree(relative).body if getattr(node, "name", None) in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError("Pinned native source contract changed")
    return nodes


def execute(nodes, namespace):
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 "pinned_native_pricing_source", "exec",
                 flags=__import__("__future__").annotations.compiler_flag), namespace)


class PricingSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (UPSTREAM / "litellm_core_utils/litellm_logging.py").exists():
            raise unittest.SkipTest("Pinned native source unavailable; installed-image proof still required")
        cls.base = type("CustomLogger", (), {})  # Only the external integration base is doubled.
        cls.native_module = ModuleType("native_pricing_boundary")
        cls.native = cls.native_module.__dict__
        cls.native.update(dataclass=dataclass, Final=Final, Callable=Callable, Sequence=Sequence,
                          TypedDict=TypedDict, CustomLogger=cls.base, MappingProxyType=MappingProxyType,
                          re=re, verbose_proxy_logger=logging.getLogger(__name__),
                          hash_token=lambda value: "hash:" + value,
                          _NON_SECRET_KEY_ALIASES=frozenset(), CLI_SESSION_KEY_PREFIX="cli",
                          _HASHED_JWT_RE=re.compile(r"hashed-jwt-[a-fA-F0-9]{64}"),
                          is_valid_sha256_hash=lambda value: bool(re.fullmatch(r"[a-fA-F0-9]{64}", value)),
                          should_store_prompts_and_responses_in_spend_logs=lambda: False)
        sys.modules[cls.native_module.__name__] = cls.native_module
        execute(selected("litellm_core_utils/llm_cost_calc/utils.py",
                         {"BilledTokenRates", "_custom_pricing_rates"}), cls.native)
        execute(selected("types/utils.py", {"CostBreakdown"}), cls.native)
        execute(selected("proxy/_types.py", {"SpendLogsMetadata"}), cls.native)
        execute(selected("litellm_core_utils/core_helpers.py",
                         {"get_litellm_metadata_from_kwargs", "add_missing_spend_metadata_to_litellm_metadata"}), cls.native)
        native_logging = selected("litellm_core_utils/litellm_logging.py", {"Logging"})[0]
        cls.logging_source = native_logging
        methods = {"add_dynamic_callback", "_with_dynamic_callback", "get_combined_callback_list", "set_cost_breakdown"}
        extracted = ast.ClassDef(name="Logging", bases=[], keywords=[], decorator_list=[],
                                 body=[node for node in native_logging.body if getattr(node, "name", None) in methods])
        execute([extracted], cls.native)
        spend_tree = tree("proxy/spend_tracking/spend_tracking_utils.py")
        stamped = next(node for node in spend_tree.body if isinstance(node, ast.AnnAssign)
                       and isinstance(node.target, ast.Name) and node.target.id == "_STAMPED_METADATA_KEYS")
        execute([stamped] + selected("proxy/spend_tracking/spend_tracking_utils.py",
                {"_get_spend_logs_metadata", "_is_cli_session_alias", "_is_non_secret_key_value",
                 "_redact_logged_api_key", "_get_vector_store_request_for_spend_logs_payload",
                 "_sanitize_guardrail_information_for_spend_logs"}), cls.native)
        # Execute the exact native async hook loop, including its real error boundary.
        lifecycle = next(node for node in native_logging.body if getattr(node, "name", None) == "_async_success_handler_body")
        hook_loop = next(node for node in lifecycle.body if isinstance(node, ast.For)
                         and any(isinstance(child, ast.Attribute) and child.attr == "async_logging_hook"
                                 for child in ast.walk(node)))
        driver = ast.parse("async def run_hooks(self, callbacks, result):\n    pass\n    return self.model_call_details, result").body[0]
        driver.body[0] = hook_loop
        cls.native.update(CustomGuardrail=type("CustomGuardrail", (), {}),
                          redact_message_input_output_from_custom_logger=lambda **kwargs: kwargs["result"],
                          verbose_logger=logging.getLogger(__name__), traceback=__import__("traceback"))
        execute([driver], cls.native)
        modules = {}
        for name, values in {
            "litellm.integrations.custom_logger": {"CustomLogger": cls.base},
            "litellm.litellm_core_utils.core_helpers": {"get_litellm_metadata_from_kwargs": cls.native["get_litellm_metadata_from_kwargs"]},
            "litellm.litellm_core_utils.litellm_logging": {"Logging": cls.native["Logging"]},
            "litellm.litellm_core_utils.llm_cost_calc.utils": {"BilledTokenRates": cls.native["BilledTokenRates"]},
        }.items():
            module = ModuleType(name)
            module.__dict__.update(values)
            modules[name] = module
        spec = importlib.util.spec_from_file_location("pricing_snapshot_under_test", HERE.parents[1] / "pricing_snapshot.py")
        cls.adapter = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(cls.adapter)

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("native_pricing_boundary", None)

    def owner(self, number=1, stream=False):
        owner = self.native["Logging"]()
        for key in ("dynamic_input_callbacks", "dynamic_success_callbacks", "dynamic_async_success_callbacks",
                    "dynamic_failure_callbacks", "dynamic_async_failure_callbacks"):
            setattr(owner, key, None)
        owner.stream = stream
        owner.call_type = "acompletion"
        owner.billed_token_rates = None
        owner.model_call_details = {
            "litellm_params": {"metadata": {"spend_logs_metadata": {"owui_budget": {"payer": number}}}},
            "response_cost": 0.2 * number,
            "standard_logging_object": {"response_cost": 0.2 * number, "metadata": {"pre_hook": True}},
            "messages": [{"role": "system", "content": "synthetic instruction"},
                         {"role": "user", "content": "private synthetic input"},
                         {"role": "assistant", "tool_calls": [{"id": "call1", "type": "function",
                          "function": {"name": "synthetic", "arguments": "{}"}}]},
                         {"role": "tool", "tool_call_id": "call1", "content": "synthetic source result"}],
            "tools": [{"type": "function", "function": {"name": "synthetic"}}],
        }
        owner._handle_callback_failure = lambda **kwargs: self.fail("Native hook failed")
        return owner

    def bind(self, owner):
        data = {"litellm_logging_obj": owner}
        self.assertIsNone(asyncio.run(self.adapter.handler.async_pre_call_hook(None, None, data, "acompletion")))
        self.assertIs(data["litellm_logging_obj"], owner)

    def price(self, owner, value):
        rates = self.native["_custom_pricing_rates"]({"input_cost_per_token": value, "output_cost_per_token": value * 2})
        owner.set_cost_breakdown(input_cost=.1, output_cost=.1, total_cost=.2,
                                 cost_for_built_in_tools_cost_usd_dollar=0., billed_token_rates=rates)
        return rates

    def run_hooks(self, owner):
        return asyncio.run(self.native["run_hooks"](owner, owner.dynamic_async_success_callbacks, object()))

    def bucket(self, owner):
        return self.native["get_litellm_metadata_from_kwargs"](owner.model_call_details)["spend_logs_metadata"]

    def snapshot(self, owner):
        return self.bucket(owner)[self.adapter.SNAPSHOT_KEY]

    def test_native_fields_are_exact_and_frozen(self):
        self.assertEqual(tuple(field.name for field in fields(self.native["BilledTokenRates"])), self.adapter.RATE_FIELDS)
        rates = self.price(self.owner(), 0.000001)
        self.assertFalse(hasattr(rates, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            rates.input_cost_per_token = 3

    def test_native_hook_then_actual_row_allowlist_preserves_context_and_money(self):
        owner = self.owner()
        self.bind(owner)
        rates = self.price(owner, .000001)
        before = copy.deepcopy(owner.model_call_details)
        mapping, _ = self.run_hooks(owner)
        self.assertIs(mapping, owner.model_call_details)
        snapshot = self.snapshot(owner)
        self.assertEqual(snapshot["rates"], {name: getattr(rates, name) for name in self.adapter.RATE_FIELDS})
        self.assertEqual(snapshot["availability"], "available")
        self.assertEqual(datetime.fromisoformat(snapshot["observed_at_utc"].replace("Z", "+00:00")).tzinfo, timezone.utc)
        self.assertEqual(set(snapshot), {"schema", "availability", "observed_at_utc", "rates"})
        cleaned = self.native["_get_spend_logs_metadata"](self.native["get_litellm_metadata_from_kwargs"](mapping))
        self.assertIs(cleaned["spend_logs_metadata"], self.bucket(owner))
        self.assertEqual(json.loads(json.dumps(cleaned))["spend_logs_metadata"][self.adapter.SNAPSHOT_KEY], snapshot)
        self.assertEqual(self.bucket(owner)["owui_budget"], {"payer": 1})
        del self.bucket(owner)[self.adapter.SNAPSHOT_KEY]
        self.assertEqual(owner.model_call_details, before)

    def test_two_requests_do_not_mix_and_dynamic_registration_is_idempotent(self):
        first, second = self.owner(1), self.owner(2)
        for owner in (first, second):
            self.bind(owner)
            self.bind(owner)
            self.assertEqual(len(owner.dynamic_async_success_callbacks), 1)
        self.price(first, .001)
        self.price(second, .009)
        foreign = second.model_call_details
        asyncio.run(first.dynamic_async_success_callbacks[0].async_logging_hook(foreign, None, "acompletion"))
        self.assertNotIn(self.adapter.SNAPSHOT_KEY, self.bucket(second))
        self.run_hooks(second)
        self.run_hooks(first)
        self.assertEqual(self.snapshot(first)["rates"]["input_cost_per_token"], .001)
        self.assertEqual(self.snapshot(second)["rates"]["input_cost_per_token"], .009)

    def test_native_frozen_rates_survive_changed_price_map_and_later_owner_changes(self):
        owner = self.owner()
        self.bind(owner)
        price_map = {"input_cost_per_token": .001, "output_cost_per_token": .002}
        rates = self.native["_custom_pricing_rates"](price_map)
        owner.set_cost_breakdown(.1, .1, .2, 0., billed_token_rates=rates)
        price_map.update(input_cost_per_token=99., output_cost_per_token=199.)
        self.run_hooks(owner)
        frozen = copy.deepcopy(self.snapshot(owner))
        self.assertEqual(frozen["rates"]["input_cost_per_token"], .001)
        self.price(owner, 88.)
        self.snapshot(owner)["rates"]["input_cost_per_token"] = -1
        self.run_hooks(owner)
        self.assertEqual(self.snapshot(owner), frozen)

    def test_absent_or_untrusted_native_rates_are_explicit_unknown(self):
        for rates in (None, self.native["BilledTokenRates"](*([None] * 7)),
                      {name: 123 for name in self.adapter.RATE_FIELDS}):
            owner = self.owner()
            self.bind(owner)
            owner.billed_token_rates = rates
            self.bucket(owner)[self.adapter.SNAPSHOT_KEY] = {"availability": "spoofed"}
            self.run_hooks(owner)
            self.assertEqual(self.snapshot(owner)["availability"], "unknown")
            self.assertEqual(self.snapshot(owner)["rates"], dict.fromkeys(self.adapter.RATE_FIELDS))

    def test_only_finite_native_primitives_are_copied(self):
        owner = self.owner()
        self.bind(owner)
        owner.billed_token_rates = self.native["BilledTokenRates"](0., .25, float("nan"), float("inf"), True, "1", 10**1000)
        self.run_hooks(owner)
        self.assertEqual(self.snapshot(owner)["availability"], "partial")
        self.assertEqual(list(self.snapshot(owner)["rates"].values()), [0., .25, None, None, None, None, None])
        json.dumps(self.snapshot(owner), allow_nan=False)

    def test_native_metadata_precedence_and_shallow_redaction_copy(self):
        owner = self.owner()
        self.bind(owner)
        self.price(owner, .001)
        params = owner.model_call_details["litellm_params"]
        params["litellm_metadata"] = {"spend_logs_metadata": {"native_selected": True}}
        original = params["metadata"]["spend_logs_metadata"]
        self.run_hooks(owner)
        self.assertNotIn(self.adapter.SNAPSHOT_KEY, original)
        self.assertIn(self.adapter.SNAPSHOT_KEY, params["litellm_metadata"]["spend_logs_metadata"])
        shallow_redacted = {**owner.model_call_details, "standard_logging_object": {"redacted": True}}
        selected_metadata = self.native["get_litellm_metadata_from_kwargs"](shallow_redacted)
        self.assertIs(selected_metadata, params["litellm_metadata"])

    def test_missing_native_objects_or_existing_output_bucket_are_safe(self):
        for data in ({}, {"litellm_logging_obj": {}}, None):
            self.assertIsNone(asyncio.run(self.adapter.handler.async_pre_call_hook(None, None, data, "acompletion")))
        for params in (None, {}, {"metadata": {}}, {"metadata": {"spend_logs_metadata": "invalid"}}):
            owner = self.owner()
            owner.model_call_details["litellm_params"] = params
            self.bind(owner)
            before = copy.deepcopy(owner.model_call_details)
            self.run_hooks(owner)
            self.assertEqual(owner.model_call_details, before)

    def test_stream_capture_waits_for_native_complete_response(self):
        owner = self.owner(stream=True)
        self.bind(owner)
        self.run_hooks(owner)
        self.assertNotIn(self.adapter.SNAPSHOT_KEY, self.bucket(owner))
        self.price(owner, .001)
        owner.model_call_details["async_complete_streaming_response"] = object()
        self.run_hooks(owner)
        self.assertEqual(self.snapshot(owner)["availability"], "available")

    def test_pinned_native_lifecycle_orders_cost_before_hooks_before_tracker(self):
        lifecycle = next(node for node in self.logging_source.body if getattr(node, "name", None) == "_async_success_handler_body")
        calls = [(node.lineno, node.func.attr) for node in ast.walk(lifecycle)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        lines = lambda name: [line for line, attr in calls if attr == name]
        self.assertLess(max(lines("_response_cost_calculator")), min(lines("async_logging_hook")))
        self.assertLess(max(lines("_success_handler_helper_fn")), min(lines("async_logging_hook")))
        self.assertLess(max(lines("async_logging_hook")), min(lines("async_log_success_event")))
        first, second = object(), object()
        owner = self.owner()
        self.assertEqual(owner.get_combined_callback_list([first], [second]), [first, second])

    def test_native_raw_row_reads_live_metadata_and_original_response_cost(self):
        writer = selected("proxy/spend_tracking/spend_tracking_utils.py", {"get_logging_payload"})[0]
        assignments = {node.target.id: node.value for node in ast.walk(writer)
                       if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}
        self.assertEqual(ast.unparse(assignments["metadata"]), "get_litellm_metadata_from_kwargs(kwargs)")
        payload = next(node for node in ast.walk(writer) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == "SpendLogsPayload")
        values = {keyword.arg: keyword.value for keyword in payload.keywords}
        # Execute the actual native row expressions, not a test reconstruction.
        owner = self.owner()
        self.bind(owner)
        self.price(owner, .001)
        self.run_hooks(owner)
        clean = self.native["_get_spend_logs_metadata"](self.native["get_litellm_metadata_from_kwargs"](owner.model_call_details))
        expression = ast.Dict(keys=[ast.Constant("metadata"), ast.Constant("spend")],
                              values=[values["metadata"], values["spend"]])
        row = eval(compile(ast.fix_missing_locations(ast.Expression(expression)), "native_row_projection", "eval"),
                   {"safe_dumps": json.dumps, "clean_metadata": clean, "kwargs": owner.model_call_details})
        self.assertEqual(row["spend"], .2)
        self.assertEqual(json.loads(row["metadata"])["spend_logs_metadata"][self.adapter.SNAPSHOT_KEY], self.snapshot(owner))


if __name__ == "__main__":
    unittest.main()
