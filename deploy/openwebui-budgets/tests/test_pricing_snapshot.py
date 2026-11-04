"""Pinned native AST boundary checks; not installed-image/DB acceptance."""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Callable, Sequence, Mapping
import copy
from dataclasses import FrozenInstanceError, dataclass, fields
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
import subprocess
from types import MappingProxyType, ModuleType, SimpleNamespace
from typing import Any, Final, TypedDict
import unittest
from unittest.mock import patch
from pydantic import BaseModel, ConfigDict, model_validator
from starlette.requests import Request


HERE = Path(__file__).resolve()
SOURCE_ROOT = Path(os.environ.get("GOAL584_LITELLM_SOURCE_ROOT", HERE.parents[3] / "local/goal584/litellm/upstream"))
PIN = "d665dc1a6315847fcad6cc2c1264ceb47c06abce"


@lru_cache(maxsize=16)
def source(relative):
    extra = os.environ.get("GOAL584_LITELLM_BATCH_UTILS_SOURCE")
    if relative == "router_utils/batch_utils.py" and extra:
        data = Path(extra).read_bytes()
        if (hashlib.sha256(data).hexdigest() != "44df8a0e5c918730bc44c2f07c053ce82e39efde6b62619853ac8a3175deee9a"
                or hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()
                != "386a2135239a74a0867e657552519c0e742e478f"):
            raise AssertionError("Additional pinned native source changed")
        return data.decode("utf-8")
    return subprocess.check_output(
        ["git", "-c", "gc.auto=0", "show", PIN + ":litellm/" + relative],
        cwd=SOURCE_ROOT, env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
    ).decode("utf-8")


def tree(relative):
    return ast.parse(source(relative))


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
        if not SOURCE_ROOT.exists() and "GOAL584_LITELLM_SOURCE_ROOT" not in os.environ:
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
        methods = {"add_dynamic_callback", "_with_dynamic_callback", "get_combined_callback_list", "set_cost_breakdown",
                   "get_router_model_id"}
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
        shadow = ModuleType("litellm.integrations.shadow_eval_logger")
        shadow.GuardrailRequestSnapshot = object  # Unused guardrails_applied=False branch.
        cls.native_import_modules = {**modules, "litellm.integrations.shadow_eval_logger": shadow}

        # Actual native representations and protected global-router lookup.
        cls.native.update(BaseModel=BaseModel, ConfigDict=ConfigDict, model_validator=model_validator,
                          Any=Any, ClassVar=__import__("typing").ClassVar,
                          Literal=__import__("typing").Literal,
                          datetime=__import__("datetime"), uuid=__import__("uuid"),
                          ModelAccessWindow=Any, LiteLLM_Params=Any)
        execute(selected("types/utils.py", {"CustomPricingLiteLLMParams", "MirroredPricingParams"}), cls.native)
        execute(selected("types/router.py", {"_as_utc", "ModelInfo"}), cls.native)
        cls.native["ModelInfo"].model_rebuild(_types_namespace=cls.native)
        cls.native["SPECIAL_MODEL_INFO_PARAMS"] = tuple(cls.native["MirroredPricingParams"].model_fields)
        execute(selected("types/router.py", {"Deployment"}), cls.native)
        router = selected("router.py", {"Router"})[0]
        names = {"get_deployment", "_update_kwargs_with_deployment", "_merge_tools_from_deployment",
                 "_forwarded_alias_marker_keys_the_deployment_sets", "_update_kwargs_with_default_litellm_params"}
        execute([ast.ClassDef(name="Router", bases=[], keywords=[], decorator_list=[],
                    body=[node for node in router.body if getattr(node, "name", None) in names])], cls.native)
        cls.native.update(
            _ALIAS_MARKER_FORWARDED_PARAMS_KWARG="_alias_marker_forwarded_params",
            is_clientside_credential=lambda **kwargs: False,
            refund_stale_reservation_before_retry=lambda *args: None,
            deployment_has_io_token_limits=lambda deployment: False,
            set_io_token_rate_limit_request_kwargs=lambda *args, **kwargs: None,
            ROUTING_REQUEST_TAGS_METADATA_KEY="routing_request_tags",
            _get_tags_from_request_kwargs=lambda *args, **kwargs: (),
        )
        execute(selected("router_utils/batch_utils.py", {"_get_router_metadata_variable_name"}), cls.native)
        cls.native.update(infer_openai_data_residency=lambda *args: None, normalize_drop_params=lambda value: value)
        params_tree = tree("litellm_core_utils/get_litellm_params.py")
        constants = {"AWS_CREDENTIAL_KWARGS_KEYS", "PROVIDER_AFFINITY_HEADER_KWARG_KEY", "OPTIONAL_KWARGS_KEYS"}
        execute([node for node in params_tree.body if isinstance(node, ast.AnnAssign)
                 and getattr(node.target, "id", None) in constants]
                + selected("litellm_core_utils/get_litellm_params.py",
                           {"get_litellm_params", "_get_base_model_from_litellm_call_metadata"}), cls.native)
        cls.native.update(provider_list=[], litellm=SimpleNamespace(ROUTER_MAX_FALLBACKS=5),
                          Mapping=Mapping, _build_banned_observability_params=lambda: frozenset())
        auth = tree("proxy/auth/auth_utils.py")
        constants = {"_NESTED_CONFIG_KEYS", "_NESTED_METADATA_KEYS", "_BANNED_REQUEST_BODY_PARAMS", "_FALLBACK_FIELDS"}
        execute([node for node in auth.body if isinstance(node, ast.AnnAssign)
                 and getattr(node.target, "id", None) in constants], cls.native)
        execute(selected("proxy/auth/auth_utils.py", {
            "_is_param_allowed", "_allow_model_level_clientside_configurable_parameters", "_check_banned_params",
            "_coerce_metadata_to_dict", "is_request_body_safe", "_iter_fallback_field_values",
            "iter_request_fallback_targets", "_iter_fallback_targets"}), cls.native)
        cls.native.update(_CLIENT_PRICING_CONTROL_FIELDS=frozenset(cls.native["CustomPricingLiteLLMParams"].model_fields),
                          _CLIENT_PRICING_METADATA_FIELDS=frozenset({"model_info", "standard_logging_guardrail_information"}))
        execute(selected("proxy/litellm_pre_call_utils.py", {"_strip_client_pricing_overrides"}), cls.native)
        cls.native.update(_TRANSPORT_ONLY_CREDENTIAL_KEYS=frozenset(), _CALLBACK_CREDENTIAL_KEYS=frozenset())
        execute(selected("proxy/litellm_pre_call_utils.py", {"refresh_proxy_server_request_body_snapshot"}), cls.native)
        setup = selected("proxy/litellm_pre_call_utils.py", {"add_litellm_data_to_request"})[0]
        cls.request_context_assignment = next(node for node in ast.walk(setup) if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "proxy_server_request" for target in node.targets))
        # Constructor/type boundary only; actual builder return AST invokes it
        # with native kwargs, so an anonymous native object is not a None stub.
        cls.Auth = type("UserAPIKeyAuth", (), {"__init__": lambda self, **values: self.__dict__.update(values)})
        execute(selected("proxy/auth/user_api_key_auth.py", {"is_no_auth_dev_mode"}), cls.native)
        builder = selected("proxy/auth/user_api_key_auth.py", {"_user_api_key_auth_builder"})[0]
        cls.no_auth_branch = next(node for node in ast.walk(builder) if isinstance(node, ast.If)
                                  and ast.unparse(node.test) == "master_key is None")
        wrapper = ast.parse("def native_no_auth_return(master_key, api_key, parent_otel_span):\n    pass").body[0]
        wrapper.body = [cls.no_auth_branch]
        cls.native.update(UserAPIKeyAuth=cls.Auth, LitellmUserRoles=SimpleNamespace(INTERNAL_USER="internal_user"))
        execute([wrapper], cls.native)
        cls.native["lru_cache"] = lru_cache
        execute(selected("proxy/auth/auth_utils.py", {"get_request_route", "normalize_request_route"}), cls.native)
        auth_wrapper = selected("proxy/auth/user_api_key_auth.py", {"user_api_key_auth"})[0]
        cls.auth_route_assignment = next(node for node in ast.walk(auth_wrapper) if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Attribute) and target.attr == "request_route" for target in node.targets))
        cls.native["LitellmUserRoles"].INTERNAL_USER_VIEW_ONLY = "internal_user_view_only"
        cls.native["LiteLLMRoutes"] = SimpleNamespace(public_routes=SimpleNamespace(value=[]))
        execute(selected("proxy/auth/user_api_key_auth.py", {
            "_normalize_public_auth_route", "_route_requires_auth_despite_public"}), cls.native)
        execute(selected("proxy/auth/auth_utils.py", {"route_in_additonal_public_routes"}), cls.native)
        checks = selected("proxy/auth/route_checks.py", {"RouteChecks"})[0]
        execute([ast.ClassDef(name="RouteChecks", bases=[], keywords=[], decorator_list=[], body=[
            node for node in checks.body if getattr(node, "name", None) == "route_matches_wildcard_pattern"] )], cls.native)
        branch = next(node for node in ast.walk(builder) if isinstance(node, ast.If)
                      and "route_in_additonal_public_routes" in ast.unparse(node.test))
        wrapper = ast.parse("def native_public_auth_return(route, general_settings):\n    pass").body[0]
        wrapper.body = [branch]
        execute([wrapper], cls.native)

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

    def descriptor(self):
        return {"schema": 1, "deployment_id": "goal584-price-a-v1", "currency": "USD",
                "source_ref": "fixture:agreed-v1", "source_url": "https://example.invalid/agreed-v1",
                "source_checked_at_utc": "2026-11-03T12:00:00Z",
                "declared_effective_from_utc": "2026-11-03T12:00:00Z",
                "declared_effective_until_utc": None, "activation_ref": "fixture-release-v1",
                "qualified_usage": "flat_input_output"}

    @staticmethod
    def unknown_descriptor(reason):
        return {"schema": 1, "availability": "unknown", "descriptor": None, "reason": reason}

    @staticmethod
    def http_request(path="/v1/chat/completions", host=b"proxy:4000"):
        return Request({"type": "http", "method": "POST", "scheme": "http", "path": path,
                        "root_path": "", "query_string": b"", "server": ("127.0.0.1", 4000),
                        "headers": [(b"host", host)]})

    def bind_auth_route(self, identity, request=None):
        route = self.native["get_request_route"](request or self.http_request())
        execute([self.auth_route_assignment], {"user_api_key_auth_obj": identity, "route": route,
                                              "normalize_request_route": self.native["normalize_request_route"]})
        return identity

    def protected_owner(self, descriptor=None, http_request=None):
        declaration = self.descriptor() if descriptor is None else descriptor
        deployment = {"model_name": "goal584-a", "litellm_params": {"model": "openai/goal584-fake-a"},
                      "model_info": {"id": "goal584-price-a-v1", "input_cost_per_token": .01,
                                     "output_cost_per_token": .02, self.adapter.DESCRIPTOR_KEY: declaration}}
        router = self.native["Router"]()
        router.model_list = [copy.deepcopy(deployment)]
        router.model_id_to_deployment_index_map = {"goal584-price-a-v1": 0}
        router.default_litellm_params = {}
        router.cache = None
        router._get_timeout = lambda **kwargs: 30  # Unrelated timeout lookup only.
        router.get_model_group_info = lambda **kwargs: SimpleNamespace(configurable_clientside_auth_params=None)
        context = self.owner().model_call_details
        request = json.loads(json.dumps({"model": "goal584-a", "messages": context["messages"], "tools": context["tools"],
                   "metadata": {"spend_logs_metadata": {}, "model_info": {"id": "forged", self.adapter.DESCRIPTOR_KEY: {"forged": True}}},
                   "model_info": {"id": "forged", self.adapter.DESCRIPTOR_KEY: {"forged": True}}}))
        before = copy.deepcopy(request)
        self.native["is_request_body_safe"](request, {}, router, "goal584-a")
        self.native["_strip_client_pricing_overrides"](request)
        execute([self.request_context_assignment], {
            "data": request, "request": http_request or self.http_request(),
            "_logging_safe_headers": {}, "_TRANSPORT_ONLY_CREDENTIAL_KEYS": frozenset(), "arrival_time": 0,
        })
        with patch.dict(sys.modules, self.native_import_modules):
            self.native["refresh_proxy_server_request_body_snapshot"](request)
        router._update_kwargs_with_deployment(router.model_list[0], request, function_name="acompletion")
        params = self.native["get_litellm_params"](**request)
        owner = self.owner()
        owner.litellm_params = params
        owner.model_call_details["litellm_params"] = params
        self.price(owner, .01)
        proxy = ModuleType("litellm.proxy")
        proxy.proxy_server = ModuleType("litellm.proxy.proxy_server")
        proxy.proxy_server.llm_router = router
        proxy.proxy_server.general_settings = {}
        proxy.proxy_server.master_key = "fixture-protected-master"
        proxy.proxy_server.user_custom_auth = None
        proxy.proxy_server.premium_user = False
        types_module = ModuleType("litellm.proxy._types")
        types_module.UserAPIKeyAuth = self.Auth
        auth_module = ModuleType("litellm.proxy.auth.user_api_key_auth")
        auth_module.is_no_auth_dev_mode = self.native["is_no_auth_dev_mode"]
        utils_module = ModuleType("litellm.proxy.auth.auth_utils")
        utils_module.route_in_additonal_public_routes = self.native["route_in_additonal_public_routes"]
        checks_module = ModuleType("litellm.proxy.auth.route_checks")
        checks_module.RouteChecks = self.native["RouteChecks"]
        modules = {"litellm.proxy": proxy, "litellm.proxy._types": types_module,
                   "litellm.proxy.proxy_server": proxy.proxy_server,
                   "litellm.proxy.auth.user_api_key_auth": auth_module,
                   "litellm.proxy.auth.auth_utils": utils_module,
                   "litellm.proxy.auth.route_checks": checks_module}
        return owner, router, proxy.proxy_server, modules, before

    def capture_protected(self, owner, modules, auth=True, auth_object=None):
        with patch.dict(sys.modules, modules):
            asyncio.run(self.adapter.handler.async_pre_call_hook(auth_object or (self.bind_auth_route(self.Auth()) if auth else None), None,
                        {"litellm_logging_obj": owner}, "acompletion"))
            self.run_hooks(owner)
        return self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]

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
        del self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]
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

    def test_protected_native_lookup_overwrites_json_collision_and_persists_same_row(self):
        owner, router, _, modules, caller = self.protected_owner()
        self.assertEqual(caller["metadata"]["model_info"]["id"], "forged")
        params = owner.litellm_params
        self.assertIs(params["model_info"], params["metadata"]["model_info"])
        self.assertEqual(owner.get_router_model_id(), "goal584-price-a-v1")
        self.assertIsInstance(router.get_deployment(model_id="goal584-price-a-v1"), self.native["Deployment"])
        before = copy.deepcopy(owner.model_call_details)
        snapshot = self.capture_protected(owner, modules)
        self.assertEqual(snapshot, {"schema": 1, "availability": "available", "descriptor": self.descriptor()})
        writer = selected("proxy/spend_tracking/spend_tracking_utils.py", {"get_logging_payload"})[0]
        model_id = next(node for node in writer.body if isinstance(node, ast.AnnAssign)
                        and getattr(node.target, "id", None) == "_model_id")
        payload = next(node for node in ast.walk(writer) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == "SpendLogsPayload")
        values = {keyword.arg: keyword.value for keyword in payload.keywords}
        metadata = self.native["get_litellm_metadata_from_kwargs"](owner.model_call_details)
        scope = {"metadata": metadata, "standard_logging_payload": None, "Final": Final}
        execute([model_id], scope)
        scope.update(safe_dumps=json.dumps, clean_metadata=self.native["_get_spend_logs_metadata"](metadata),
                     kwargs=owner.model_call_details)
        expression = ast.Expression(ast.Dict(keys=[ast.Constant(key) for key in ("model_id", "metadata", "spend")],
                    values=[values[key] for key in ("model_id", "metadata", "spend")]))
        row = eval(compile(ast.fix_missing_locations(expression), "actual_native_spend_row", "eval"), scope)
        self.assertEqual(row["model_id"], owner.get_router_model_id())
        self.assertEqual(json.loads(row["metadata"])["spend_logs_metadata"][self.adapter.DESCRIPTOR_SNAPSHOT_KEY], snapshot)
        self.assertEqual(row["spend"], .2)
        for key in (self.adapter.SNAPSHOT_KEY, self.adapter.DESCRIPTOR_SNAPSHOT_KEY):
            del self.bucket(owner)[key]
        self.assertEqual(owner.model_call_details, before)  # Instructions/history/tool results/tools and money unchanged.

    def test_native_default_auth_rejects_user_router_before_custom_auth(self):
        owner, router, proxy, modules, _ = self.protected_owner()
        payload = {"model": "goal584-a", "user_config": {"model_list": [{"model_info": {"id": "forged"}}]}}
        with self.assertRaisesRegex(ValueError, "user_config is not allowed"):
            self.native["is_request_body_safe"](payload, {}, router, "goal584-a")
        self.assertTrue(self.native["is_request_body_safe"](payload, {"allow_client_side_credentials": True}, router, "goal584-a"))
        proxy.general_settings["allow_client_side_credentials"] = True
        self.assertEqual(self.capture_protected(owner, modules)["availability"], "unknown")
        owner, router, _, modules, _ = self.protected_owner()
        router.get_model_group_info = lambda **kwargs: SimpleNamespace(configurable_clientside_auth_params=["user_config"])
        self.assertTrue(self.native["is_request_body_safe"](payload, {}, router, "goal584-a"))
        router.model_list[0]["litellm_params"]["configurable_clientside_auth_params"] = ["user_config"]
        self.assertEqual(self.capture_protected(owner, modules)["availability"], "unknown")
        builder = selected("proxy/auth/user_api_key_auth.py", {"_user_api_key_auth_builder"})[0]
        calls = [node for node in ast.walk(builder) if isinstance(node, ast.Call)]
        pre = min(node.lineno for node in calls if isinstance(node.func, ast.Name) and node.func.id == "pre_db_read_auth_checks")
        custom = min(node.lineno for node in calls if isinstance(node.func, ast.Name) and node.func.id == "user_custom_auth")
        self.assertLess(pre, custom)

    def test_unsupported_native_contexts_remain_unknown_with_rates_independent(self):
        mutations = {"no_auth": "eligibility", "no_router": "router", "retired": "deployment",
                     "alias_copy": "selected_model_info", "foreign_id": "deployment", "no_context": "request_body",
                     "user_config": "request_body", "per_model_optin": "clientside_auth",
                     "different_selected_descriptor": "declaration", "wrong_call_type": "call_type", "lookup_error": "deployment"}
        for mutation, reason in mutations.items():
            with self.subTest(mutation=mutation):
                owner, router, proxy, modules, _ = self.protected_owner()
                if mutation == "no_router": proxy.llm_router = None
                if mutation == "retired": router.model_id_to_deployment_index_map.clear()
                if mutation == "alias_copy": owner.litellm_params["model_info"] = copy.deepcopy(owner.litellm_params["model_info"])
                if mutation == "foreign_id": owner.litellm_params["metadata"]["model_info"]["id"] = "foreign-id"
                if mutation == "no_context": owner.litellm_params.pop("proxy_server_request")
                if mutation == "user_config": owner.litellm_params["proxy_server_request"]["body"]["user_config"] = {}
                if mutation == "per_model_optin": router.model_list[0]["litellm_params"]["configurable_clientside_auth_params"] = ["user_config"]
                if mutation == "different_selected_descriptor":
                    changed = copy.deepcopy(owner.litellm_params["model_info"][self.adapter.DESCRIPTOR_KEY])
                    changed["source_ref"] = "caller:changed"
                    owner.litellm_params["model_info"][self.adapter.DESCRIPTOR_KEY] = changed
                if mutation == "wrong_call_type": owner.call_type = "aresponses"
                if mutation == "lookup_error":
                    def failed(**kwargs): raise RuntimeError("private synthetic error must not escape")
                    router.get_deployment = failed
                snapshot = self.capture_protected(owner, modules, auth=mutation != "no_auth")
                self.assertEqual(snapshot, self.unknown_descriptor(reason))
                self.assertEqual(self.snapshot(owner)["availability"], "available")

    def test_native_rates_must_match_protected_explicit_flat_fields(self):
        for value in (.03, float("nan"), float("inf"), True, None, -1, 10**1000):
            owner, router, _, modules, _ = self.protected_owner()
            router.model_list[0]["model_info"]["input_cost_per_token"] = value
            self.assertEqual(self.capture_protected(owner, modules)["availability"], "unknown")
        owner, _, _, modules, _ = self.protected_owner()
        self.price(owner, .02)
        self.assertEqual(self.capture_protected(owner, modules), self.unknown_descriptor("rate_mismatch"))

    def test_unknown_reason_vocabulary_is_one_literal_closed_tuple(self):
        node = next(node for node in ast.parse(Path(self.adapter.__file__).read_bytes()).body
                    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                    and target.id == "DESCRIPTOR_UNKNOWN_REASONS" for target in node.targets))
        expected = ("eligibility", "call_type", "request_body", "selected_model_info", "model_id", "settings",
                    "router", "deployment", "clientside_auth", "protected_id", "declaration", "billed_rates", "rate_mismatch")
        self.assertEqual(ast.literal_eval(node.value), expected)
        self.assertEqual(self.adapter.DESCRIPTOR_UNKNOWN_REASONS, expected)
        self.assertEqual(len(set(expected)), len(expected))

    def test_unknown_reason_identifies_model_settings_and_protected_guard(self):
        for mutation, reason in (("missing_id", "model_id"), ("settings", "settings"),
                                 ("protected_id", "protected_id"), ("rate", "rate_mismatch")):
            with self.subTest(mutation=mutation):
                owner, router, proxy, modules, _ = self.protected_owner()
                if mutation == "missing_id": owner.litellm_params["model_info"].pop("id")
                if mutation == "settings": proxy.general_settings["allow_client_side_credentials"] = True
                if mutation == "protected_id": router.model_list[0]["model_info"]["id"] = "foreign-protected-id"
                if mutation == "rate": self.price(owner, .02)
                self.assertEqual(self.capture_protected(owner, modules), self.unknown_descriptor(reason))
                self.assertEqual(self.snapshot(owner)["availability"], "available")

    def test_unknown_reason_keeps_only_fixed_stage_when_secret_exception_occurs(self):
        secret = "private https://user:password@example.invalid/price?token=secret sk-" + "x" * 32
        class ExplodingDict(dict):
            def get(self, *args, **kwargs):
                raise RuntimeError(secret)
        for mutation, reason in (("request_body", "request_body"), ("settings", "settings"),
                                 ("deployment", "deployment"), ("declaration", "declaration"),
                                 ("rate_mismatch", "rate_mismatch")):
            with self.subTest(mutation=mutation):
                owner, router, proxy, modules, _ = self.protected_owner()
                if mutation == "request_body": owner.litellm_params["proxy_server_request"] = ExplodingDict()
                if mutation == "settings": proxy.general_settings = ExplodingDict()
                if mutation == "deployment":
                    def failed(**kwargs): raise RuntimeError(secret)
                    router.get_deployment = failed
                if mutation == "declaration":
                    owner.litellm_params["model_info"][self.adapter.DESCRIPTOR_KEY]["source_url"] = secret
                if mutation == "rate_mismatch":
                    # Native rates are a frozen dataclass. Its real field access
                    # raises here; the descriptor guard must suppress all text.
                    def failed_rate(value, name):
                        if name == "input_cost_per_token": raise RuntimeError(secret)
                        return object.__getattribute__(value, name)
                    with patch.object(self.native["BilledTokenRates"], "__getattribute__", failed_rate), \
                            patch.dict(sys.modules, modules):
                        observed = self.adapter._capture_descriptor(owner, owner.litellm_params,
                            self.native["get_litellm_metadata_from_kwargs"](owner.model_call_details), True, "/v1/chat/completions")
                else:
                    observed = self.capture_protected(owner, modules)
                self.assertEqual(observed, self.unknown_descriptor(reason))
                serialized = json.dumps(observed, allow_nan=False)
                for forbidden in (secret, "password", "token=", "sk-", "RuntimeError", "example.invalid"):
                    self.assertNotIn(forbidden, serialized)

    def test_descriptor_is_strict_primitive_and_never_exports_credentials(self):
        changes = [("schema", True), ("schema", 2), ("qualified_usage", "all_prices"),
                   ("source_checked_at_utc", "2026-11-03T12:00:00"),
                   ("source_checked_at_utc", "2026-02-30T12:00:00Z"),
                   ("declared_effective_until_utc", "2026-11-03T11:59:59Z"),
                   ("source_ref", {"not": "primitive"}), ("currency", "US"),
                   ("deployment_id", "different"), ("source_ref", "sk-" + "x" * 32)]
        urls = ("https://user:password@example.invalid/price", "https://example.invalid/price?token=secret",
                "https://example.invalid/price#secret", "file:///private/price", "https://example.invalid:bad/price",
                "https://example.invalid/" + "sk-" + "x" * 32, "https://example.invalid/\nprice")
        for field, value in [*changes, *[("source_url", value) for value in urls]]:
            with self.subTest(field=field, value_type=type(value).__name__):
                descriptor = self.descriptor(); descriptor[field] = value
                owner, _, _, modules, _ = self.protected_owner(descriptor)
                observed = self.capture_protected(owner, modules)
                self.assertEqual(observed, self.unknown_descriptor("declaration"))
                json.dumps(observed, allow_nan=False)
        owner, _, _, modules, _ = self.protected_owner({**self.descriptor(), "private_extra": "secret"})
        self.assertEqual(self.capture_protected(owner, modules)["availability"], "unknown")

    def test_descriptor_capture_is_frozen_and_deep_copied(self):
        owner, router, _, modules, _ = self.protected_owner()
        frozen = copy.deepcopy(self.capture_protected(owner, modules))
        self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]["descriptor"]["source_ref"] = "consumer:changed"
        router.model_list[0]["model_info"][self.adapter.DESCRIPTOR_KEY]["source_ref"] = "server:later"
        owner.litellm_params["model_info"][self.adapter.DESCRIPTOR_KEY]["source_ref"] = "selected:later"
        self.assertEqual(self.capture_protected(owner, modules), frozen)

    def test_unknown_is_frozen_and_unqualified_programmatic_alias_is_not_trusted(self):
        owner, _, proxy, modules, _ = self.protected_owner()
        selected = owner.litellm_params["model_info"]
        # Programmatic code can manufacture these aliases and an agreeing ID.
        owner.litellm_params["metadata"]["model_info"] = selected
        self.assertIs(owner.litellm_params["model_info"], selected)
        self.assertEqual(owner.get_router_model_id(), selected["id"])
        self.assertEqual(self.capture_protected(owner, modules, auth=False)["availability"], "unknown")
        self.assertEqual(self.capture_protected(owner, modules, auth=True)["availability"], "unknown")

    def test_protected_stream_descriptor_waits_for_native_complete(self):
        owner, _, _, modules, _ = self.protected_owner()
        owner.stream = True
        with patch.dict(sys.modules, modules):
            asyncio.run(self.adapter.handler.async_pre_call_hook(self.bind_auth_route(self.Auth()), None,
                        {"litellm_logging_obj": owner}, "acompletion"))
            self.run_hooks(owner)
            self.assertNotIn(self.adapter.DESCRIPTOR_SNAPSHOT_KEY, self.bucket(owner))
            owner.model_call_details["async_complete_streaming_response"] = object()
            self.run_hooks(owner)
            self.assertEqual(self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]["availability"], "available")

    def test_actual_native_slot_selector_and_both_metadata_bucket_transports(self):
        select = self.native["_get_router_metadata_variable_name"]
        self.assertEqual(select("acompletion"), "metadata")
        self.assertEqual(select("_ageneric_api_call_with_fallbacks"), "litellm_metadata")
        for bucket in ("metadata", "litellm_metadata"):
            owner, _, _, modules, _ = self.protected_owner()
            if bucket == "litellm_metadata":
                owner.litellm_params[bucket] = owner.litellm_params.pop("metadata")
            self.assertEqual(self.capture_protected(owner, modules)["availability"], "available")
            self.assertIs(self.native["get_litellm_metadata_from_kwargs"](owner.model_call_details), owner.litellm_params[bucket])

    def test_descriptor_unknown_never_drops_valid_rates_or_preserves_client_snapshot(self):
        for mutation, reason in (("missing_declaration", "declaration"), ("no_used_rates", "billed_rates"),
                                 ("auth_qualification_error", "eligibility")):
            owner, router, _, modules, _ = self.protected_owner()
            self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY] = {"private": "client-injected"}
            if mutation == "missing_declaration": router.model_list[0]["model_info"].pop(self.adapter.DESCRIPTOR_KEY)
            if mutation == "no_used_rates": owner.billed_token_rates = None
            if mutation == "auth_qualification_error": modules["litellm.proxy._types"].UserAPIKeyAuth = object()
            observed = self.capture_protected(owner, modules)
            self.assertEqual(observed, self.unknown_descriptor(reason))
            self.assertEqual(self.snapshot(owner)["availability"], "unknown" if mutation == "no_used_rates" else "available")

    def test_two_qualified_request_snapshots_do_not_share_descriptor_state(self):
        first, _, _, first_modules, _ = self.protected_owner()
        second, router, _, second_modules, _ = self.protected_owner()
        selected = second.litellm_params["model_info"]
        selected["id"] = "goal584-price-a-v2"
        selected[self.adapter.DESCRIPTOR_KEY]["deployment_id"] = "goal584-price-a-v2"
        selected[self.adapter.DESCRIPTOR_KEY]["source_ref"] = "fixture:agreed-v2"
        router.model_list[0]["model_info"]["id"] = "goal584-price-a-v2"
        router.model_id_to_deployment_index_map = {"goal584-price-a-v2": 0}
        observed_second = self.capture_protected(second, second_modules)
        observed_first = self.capture_protected(first, first_modules)
        self.assertEqual(observed_first["descriptor"]["deployment_id"], "goal584-price-a-v1")
        self.assertEqual(observed_second["descriptor"]["deployment_id"], "goal584-price-a-v2")
        observed_first["descriptor"]["source_ref"] = "consumer:changed"
        self.assertEqual(observed_second["descriptor"]["source_ref"], "fixture:agreed-v2")

    def test_actual_native_anonymous_return_is_unknown_without_changing_context_or_money(self):
        self.assertEqual(self.no_auth_branch.lineno, 1871)
        for api_key in (None, "caller-supplied-string"):
            with self.subTest(api_key_present=api_key is not None):
                owner, _, proxy, modules, _ = self.protected_owner()
                proxy.master_key = None
                anonymous = self.native["native_no_auth_return"](None, api_key, None)
                self.bind_auth_route(anonymous)
                self.assertIsInstance(anonymous, self.Auth)
                self.assertEqual(anonymous.user_role, "internal_user")
                before = copy.deepcopy(owner.model_call_details)
                with patch.dict(sys.modules, modules):
                    asyncio.run(self.adapter.handler.async_pre_call_hook(anonymous, None,
                                {"litellm_logging_obj": owner}, "acompletion"))
                    self.run_hooks(owner)
                self.assertEqual(self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY],
                                 self.unknown_descriptor("eligibility"))
                self.assertEqual(self.snapshot(owner)["availability"], "available")
                self.assertEqual(owner.model_call_details["response_cost"], .2)
                for key in (self.adapter.SNAPSHOT_KEY, self.adapter.DESCRIPTOR_SNAPSHOT_KEY):
                    del self.bucket(owner)[key]
                self.assertEqual(owner.model_call_details, before)

    def test_no_auth_mode_is_frozen_before_first_logging_and_never_upgraded(self):
        owner, _, proxy, modules, _ = self.protected_owner()
        proxy.master_key = None
        anonymous = self.native["native_no_auth_return"](None, None, None)
        self.bind_auth_route(anonymous)
        with patch.dict(sys.modules, modules):
            asyncio.run(self.adapter.handler.async_pre_call_hook(anonymous, None,
                        {"litellm_logging_obj": owner}, "acompletion"))
            # Configuration changes after the prehook cannot authenticate the
            # already admitted anonymous request retroactively.
            proxy.master_key = "newly-configured-master"
            proxy.user_custom_auth = lambda **kwargs: self.Auth()
            self.run_hooks(owner)
            self.assertEqual(self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]["availability"], "unknown")
            asyncio.run(self.adapter.handler.async_pre_call_hook(self.bind_auth_route(self.Auth()), None,
                        {"litellm_logging_obj": owner}, "acompletion"))
            self.run_hooks(owner)
            self.assertEqual(len(owner.dynamic_async_success_callbacks), 1)
            self.assertEqual(self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]["availability"], "unknown")
        self.assertEqual(self.snapshot(owner)["availability"], "available")

    def test_native_auth_mode_seam_preserves_configured_custom_auth_before_dev_fallback(self):
        classify = self.native["is_no_auth_dev_mode"]
        self.assertTrue(classify(None, {}))
        self.assertFalse(classify("configured-master", {}))
        for flag in ("enable_jwt_auth", "enable_oauth2_auth", "enable_oauth2_proxy_auth"):
            self.assertFalse(classify(None, {flag: True}))
        owner, _, proxy, modules, _ = self.protected_owner()
        proxy.master_key = None

        async def custom_auth(**kwargs):
            return self.Auth(authenticated_by_custom_auth=True)
        proxy.user_custom_auth = custom_auth
        identity = self.Auth()
        builder = selected("proxy/auth/user_api_key_auth.py", {"_user_api_key_auth_builder"})[0]
        mark = next(node for node in ast.walk(builder) if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Attribute) and target.attr == "authenticated_by_custom_auth"
                            for target in node.targets))
        execute([mark], {"validated": identity})
        self.bind_auth_route(identity)
        self.assertEqual(self.capture_protected(owner, modules, auth_object=identity)["availability"], "available")
        self.assertEqual(self.snapshot(owner)["availability"], "available")
        builder = selected("proxy/auth/user_api_key_auth.py", {"_user_api_key_auth_builder"})[0]
        custom_line = min(node.lineno for node in ast.walk(builder) if isinstance(node, ast.Call)
                          and isinstance(node.func, ast.Name) and node.func.id == "user_custom_auth")
        self.assertLess(custom_line, self.no_auth_branch.lineno)
        owner, _, proxy, modules, _ = self.protected_owner()
        proxy.master_key = None
        proxy.user_custom_auth = custom_auth
        anonymous = self.native["native_no_auth_return"](None, None, None)
        self.bind_auth_route(anonymous)
        self.assertEqual(self.capture_protected(owner, modules, auth_object=anonymous)["availability"], "unknown")

    def test_native_public_inference_return_is_unknown_with_master_present(self):
        for public_route in ("/v1/chat/completions", "/v1/chat/*"):
            with self.subTest(public_route=public_route):
                owner, _, proxy, modules, _ = self.protected_owner()
                proxy.premium_user = True
                proxy.general_settings["public_routes"] = [public_route]
                before = copy.deepcopy(owner.model_call_details)
                with patch.dict(sys.modules, modules):
                    identity = self.native["native_public_auth_return"]("/v1/chat/completions", proxy.general_settings)
                    self.bind_auth_route(identity)
                    self.assertIsInstance(identity, self.Auth)
                    self.assertEqual(identity.user_role, "internal_user_view_only")
                observed = self.capture_protected(owner, modules, auth_object=identity)
                self.assertEqual(observed, self.unknown_descriptor("eligibility"))
                self.assertEqual(self.snapshot(owner)["availability"], "available")
                self.assertEqual(owner.model_call_details["response_cost"], .2)
                for key in (self.adapter.SNAPSHOT_KEY, self.adapter.DESCRIPTOR_SNAPSHOT_KEY):
                    del self.bucket(owner)[key]
                self.assertEqual(owner.model_call_details, before)

    def test_public_mode_is_frozen_but_public_health_does_not_disqualify_private_inference(self):
        owner, _, proxy, modules, _ = self.protected_owner()
        proxy.premium_user = True
        proxy.general_settings["public_routes"] = ["/v1/chat/completions"]
        with patch.dict(sys.modules, modules):
            identity = self.native["native_public_auth_return"]("/v1/chat/completions", proxy.general_settings)
            self.bind_auth_route(identity)
            asyncio.run(self.adapter.handler.async_pre_call_hook(identity, None,
                        {"litellm_logging_obj": owner}, "acompletion"))
            proxy.general_settings["public_routes"] = []
            self.run_hooks(owner)
            self.assertEqual(self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]["availability"], "unknown")
        owner, _, proxy, modules, _ = self.protected_owner()
        proxy.premium_user = True
        proxy.general_settings["public_routes"] = ["/health/*"]
        self.assertEqual(self.capture_protected(owner, modules)["availability"], "available")

    def test_native_auth_route_assignment_preserves_three_qualified_paths(self):
        for path in ("/chat/completions", "/v1/chat/completions", "/openai/v1/chat/completions"):
            with self.subTest(path=path):
                request = self.http_request(path=path)
                identity = self.bind_auth_route(self.Auth(), request)
                self.assertEqual(self.native["get_request_route"](request), path)
                self.assertEqual(identity.request_route, path)
                owner, _, _, modules, _ = self.protected_owner(http_request=request)
                self.assertEqual(self.capture_protected(owner, modules, auth_object=identity)["availability"], "available")

    def test_missing_or_unsupported_auth_route_cannot_be_supplied_by_metadata_or_URL(self):
        for route in (None, "", "/embeddings", "/v1/responses", 7, []):
            with self.subTest(route_type=type(route).__name__):
                owner, _, _, modules, _ = self.protected_owner()
                identity = self.Auth(request_route=route)
                owner.litellm_params["metadata"]["user_api_key_request_route"] = "/v1/chat/completions"
                self.assertEqual(self.capture_protected(owner, modules, auth_object=identity)["availability"], "unknown")
                self.assertEqual(self.snapshot(owner)["availability"], "available")

    def test_real_host_ASGI_mismatch_uses_native_auth_route_and_preserves_context(self):
        request = self.http_request(host=b"localhost/chat/completions?x=1")
        actual_route = self.native["get_request_route"](request)
        self.assertEqual(actual_route, "/v1/chat/completions")
        self.assertEqual(self.adapter.urlsplit(str(request.url)).path, "/chat/completions")
        owner, _, proxy, modules, _ = self.protected_owner(http_request=request)
        proxy.premium_user = True
        proxy.general_settings["public_routes"] = [actual_route]
        owner.litellm_params["metadata"]["user_api_key_request_route"] = "/chat/completions"
        before = copy.deepcopy(owner.model_call_details)
        with patch.dict(sys.modules, modules):
            identity = self.native["native_public_auth_return"](actual_route, proxy.general_settings)
            self.assertEqual(identity.user_role, "internal_user_view_only")
            self.bind_auth_route(identity, request)
            with patch.object(modules["litellm.proxy.auth.auth_utils"], "route_in_additonal_public_routes",
                              wraps=self.native["route_in_additonal_public_routes"]) as check:
                observed = self.capture_protected(owner, modules, auth_object=identity)
                check.assert_called_once_with(current_route=actual_route)
        self.assertEqual(observed, self.unknown_descriptor("eligibility"))
        self.assertEqual(self.snapshot(owner)["availability"], "available")
        self.assertEqual(owner.model_call_details["response_cost"], .2)
        self.assertEqual(owner.litellm_params["proxy_server_request"]["url"], str(request.url))
        for key in (self.adapter.SNAPSHOT_KEY, self.adapter.DESCRIPTOR_SNAPSHOT_KEY):
            del self.bucket(owner)[key]
        self.assertEqual(owner.model_call_details, before)

    def test_native_auth_route_value_is_frozen_before_first_logging(self):
        owner, _, proxy, modules, _ = self.protected_owner()
        proxy.premium_user = True
        proxy.general_settings["public_routes"] = ["/v1/chat/completions"]
        with patch.dict(sys.modules, modules):
            identity = self.native["native_public_auth_return"]("/v1/chat/completions", proxy.general_settings)
            self.bind_auth_route(identity)
            asyncio.run(self.adapter.handler.async_pre_call_hook(identity, None,
                        {"litellm_logging_obj": owner}, "acompletion"))
            identity.request_route = "/chat/completions"
            proxy.general_settings["public_routes"] = []
            self.run_hooks(owner)
            self.assertEqual(owner.dynamic_async_success_callbacks[0]._auth_route, "/v1/chat/completions")
            self.assertEqual(self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]["availability"], "unknown")
        self.assertEqual(self.snapshot(owner)["availability"], "available")


if __name__ == "__main__":
    unittest.main()
