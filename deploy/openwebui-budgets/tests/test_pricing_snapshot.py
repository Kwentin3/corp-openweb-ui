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
from typing import Any, Final, TypedDict, cast
import unittest
from unittest.mock import patch
from pydantic import BaseModel, ConfigDict, PrivateAttr, TypeAdapter, ValidationError, field_validator, model_validator
from openai.types.completion_usage import CompletionUsage, CompletionTokensDetails, PromptTokensDetails
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
        # Actual native representations and protected global-router lookup.
        cls.native.update(BaseModel=BaseModel, ConfigDict=ConfigDict, model_validator=model_validator,
                          Any=Any, ClassVar=__import__("typing").ClassVar,
                          Literal=__import__("typing").Literal,
                          datetime=__import__("datetime"), uuid=__import__("uuid"),
                          ModelAccessWindow=Any, LiteLLM_Params=Any)
        # Execute native DTOs and its actual Responses-to-billing normalizer.
        # OpenAI/Pydantic bases are installed dependencies, not domain doubles.
        cls.native.update(PrivateAttr=PrivateAttr, field_validator=field_validator,
                          CompletionUsage=CompletionUsage, CompletionTokensDetails=CompletionTokensDetails,
                          PromptTokensDetails=PromptTokensDetails)
        execute(selected("types/llms/base.py", {"BaseLiteLLMOpenAIResponseObject", "CachedTokensDetails"}), cls.native)
        execute(selected("types/utils.py", {"SafeAttributeModel", "CacheCreationTokenDetails", "ServerToolUse",
                "CompletionTokensDetailsWrapper", "PromptTokensDetailsWrapper", "Usage",
                "text_tokens_without_nested_reasoning"}), cls.native)
        execute(selected("types/llms/openai.py", {"InputTokensDetails", "OutputTokensDetails", "ResponseAPIUsage"}), cls.native)
        for name in ("Usage", "PromptTokensDetailsWrapper", "CompletionTokensDetailsWrapper",
                     "InputTokensDetails", "OutputTokensDetails", "ResponseAPIUsage"):
            cls.native[name].model_rebuild(_types_namespace=cls.native)
        logging_utils = selected("responses/utils.py", {"ResponseAPILoggingUtils"})[0]
        execute(selected("responses/utils.py", {"_output_token_detail"}) + [
            ast.ClassDef(name="ResponseAPILoggingUtils", bases=[], keywords=[], decorator_list=[], body=[
                node for node in logging_utils.body if getattr(node, "name", None) in
                {"_transform_response_api_usage_to_chat_usage", "_is_response_api_usage"}])], cls.native)
        cls.native.update(cast=cast, math=__import__("math"), TypeAdapter=TypeAdapter, ValidationError=ValidationError)
        execute(selected("litellm_core_utils/llm_cost_calc/utils.py", {
            "PromptTokensDetailsResult", "CompletionTokensDetailsResult", "_get_token_detail_value", "_coerce_token_count",
            "parse_prompt_tokens_details", "parse_completion_tokens_details", "_cache_token_counts", "_reasoning_token_count"}), cls.native)
        guardrail_tree = tree("litellm_core_utils/llm_cost_calc/guardrail_cost.py")
        execute(selected("litellm_core_utils/llm_cost_calc/guardrail_cost.py", {"GuardrailCostEntry"}) + [
            node for node in guardrail_tree.body if isinstance(node, ast.AnnAssign)
            and getattr(node.target, "id", None) == "_GUARDRAIL_COST_ENTRY_ADAPTER"] + selected(
                "litellm_core_utils/llm_cost_calc/guardrail_cost.py", {
                    "_billable_entry_cost", "_validated_entry_cost", "guardrail_information_cost", "cost_breakdown_with_guardrail"}), cls.native)
        modules = {}
        for name, values in {
            "litellm.integrations.custom_logger": {"CustomLogger": cls.base},
            "litellm.litellm_core_utils.core_helpers": {"get_litellm_metadata_from_kwargs": cls.native["get_litellm_metadata_from_kwargs"]},
            "litellm.litellm_core_utils.litellm_logging": {"Logging": cls.native["Logging"]},
            "litellm.litellm_core_utils.llm_cost_calc.utils": {key: cls.native[key] for key in
                ("BilledTokenRates", "_cache_token_counts", "_reasoning_token_count")},
            "litellm.litellm_core_utils.llm_cost_calc.guardrail_cost": {"guardrail_information_cost": cls.native["guardrail_information_cost"]},
            "litellm.types.utils": {"Usage": cls.native["Usage"]},
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

    def billing_result(self):
        return SimpleNamespace(usage=self.native["Usage"](prompt_tokens=10, completion_tokens=5, total_tokens=15))

    def responses_usage(self, value=None):
        raw = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
               "input_tokens_details": {"cached_tokens": 6},
               "output_tokens_details": {"reasoning_tokens": 2}} if value is None else value
        return self.native["ResponseAPILoggingUtils"]._transform_response_api_usage_to_chat_usage(raw)

    def run_hooks(self, owner, result=None):
        return asyncio.run(self.native["run_hooks"](owner, owner.dynamic_async_success_callbacks,
                                                   self.billing_result() if result is None else result))

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

    def protected_owner(self, descriptor=None, http_request=None, deployment=None, call_type="acompletion"):
        http_request = http_request or self.http_request("/v1/responses" if call_type in ("responses", "aresponses") else "/v1/chat/completions")
        declaration = self.descriptor() if descriptor is None else descriptor
        deployment = copy.deepcopy(deployment) if deployment is not None else {"model_name": "goal584-a", "litellm_params": {"model": "openai/goal584-fake-a"},
                      "model_info": {"id": "goal584-price-a-v1", "input_cost_per_token": .01,
                                     "output_cost_per_token": .02, self.adapter.DESCRIPTOR_KEY: declaration}}
        router = self.native["Router"]()
        router.model_list = [copy.deepcopy(deployment)]
        router.model_id_to_deployment_index_map = {deployment["model_info"]["id"]: 0}
        router.default_litellm_params = {}
        router.cache = None
        router._get_timeout = lambda **kwargs: 30  # Unrelated timeout lookup only.
        router.get_model_group_info = lambda **kwargs: SimpleNamespace(configurable_clientside_auth_params=None)
        context = self.owner().model_call_details
        request = json.loads(json.dumps({"model": deployment["model_name"], "messages": context["messages"], "tools": context["tools"],
                   "metadata": {"spend_logs_metadata": {}, "model_info": {"id": "forged", self.adapter.DESCRIPTOR_KEY: {"forged": True}}},
                   "model_info": {"id": "forged", self.adapter.DESCRIPTOR_KEY: {"forged": True}}}))
        before = copy.deepcopy(request)
        if call_type in ("responses", "aresponses"):
            request.pop("messages")
            request.pop("tools")
            request.update(input="Hi", max_output_tokens=16, store=False, stream=False)
            before = copy.deepcopy(request)
        self.native["is_request_body_safe"](request, {}, router, deployment["model_name"])
        self.native["_strip_client_pricing_overrides"](request)
        execute([self.request_context_assignment], {
            "data": request, "request": http_request or self.http_request(),
            "_logging_safe_headers": {}, "_TRANSPORT_ONLY_CREDENTIAL_KEYS": frozenset(), "arrival_time": 0,
        })
        with patch.dict(sys.modules, self.native_import_modules):
            self.native["refresh_proxy_server_request_body_snapshot"](request)
        router._update_kwargs_with_deployment(router.model_list[0], request, function_name=call_type)
        params = self.native["get_litellm_params"](**request)
        owner = self.owner()
        owner.call_type = call_type
        owner._test_http_request = http_request
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

    def capture_protected(self, owner, modules, auth=True, auth_object=None, result=None):
        with patch.dict(sys.modules, modules):
            request = owner._test_http_request
            asyncio.run(self.adapter.handler.async_pre_call_hook(auth_object or (self.bind_auth_route(self.Auth(), request) if auth else None), None,
                        {"litellm_logging_obj": owner}, owner.call_type))
            self.run_hooks(owner, result)
        return self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]

    def native_settings(self, configured, database):
        # Load the complete pinned settings owner and its two native dependencies;
        # avoid importing/initializing the LiteLLM SDK during this boundary test.
        package = "litellm.proxy.config_resolvers."
        with patch.dict(sys.modules):
            for leaf in ("_descriptors", "settings_rules", "settings_store"):
                module = ModuleType(package + leaf)
                sys.modules[module.__name__] = module
                exec(compile(source("proxy/config_resolvers/" + leaf + ".py"),
                             "pinned-native-" + leaf, "exec"), module.__dict__)
            store = module.SettingsStore("general_settings")
            store.load_yaml(configured)
            store.apply_db_row("general_settings", database)
            namespace = {"SettingsStore": module.SettingsStore}
            execute(selected("proxy/proxy_server.py", {"_bind_general_settings_store"}), namespace)
            namespace["_bind_general_settings_store"](store)
            self.assertIs(namespace["general_settings"], store)
            self.assertIsInstance(store, Mapping)
            self.assertNotIsInstance(store, dict)
            return store

    def responses_owner(self, version=1, qualifier="text_cache_reasoning", route="/v1/responses", call_type="aresponses"):
        declaration = self.descriptor()
        declaration.update(deployment_id="goal584-usage-v" + str(version), qualified_usage=qualifier)
        cache, reasoning = (.001, .03) if version == 1 else (.009, .09)
        info = {"id": declaration["deployment_id"], "input_cost_per_token": .01,
                "output_cost_per_token": .02, "cache_read_input_token_cost": cache,
                "output_cost_per_reasoning_token": reasoning, self.adapter.DESCRIPTOR_KEY: declaration}
        deployment = {"model_name": "goal584-usage", "litellm_params": {"model": "openai/goal584-fake-usage", "mode": "responses"},
                      "model_info": info}
        values = self.protected_owner(deployment=deployment, call_type=call_type, http_request=self.http_request(route))
        owner = values[0]
        # Native63 cost-owner observations; _custom_pricing_rates is the flat
        # override path and intentionally cannot represent a reasoning tariff.
        rates = self.native["BilledTokenRates"](
            input_cost_per_token=.01, output_cost_per_token=.02,
            cache_read_input_token_cost=cache, cache_read_input_audio_token_cost=cache,
            cache_creation_input_token_cost=.01, cache_creation_input_token_cost_above_1hr=.01,
            output_cost_per_reasoning_token=reasoning)
        owner.set_cost_breakdown(input_cost=.04, output_cost=.06,
                                total_cost=.166 if version == 1 else .334,
                                cost_for_built_in_tools_cost_usd_dollar=0., billed_token_rates=rates,
                                cache_read_cost=.006 if version == 1 else .054,
                                reasoning_cost=.06 if version == 1 else .18)
        return values

    def test_responses_native_usage_four_protected_terms_v1_v2_and_routes(self):
        for version in (1, 2):
            for route in ("/responses", "/v1/responses", "/openai/v1/responses"):
                for call_type in ("responses", "aresponses"):
                    with self.subTest(version=version, route=route, call_type=call_type):
                        owner, router, proxy, modules, _ = self.responses_owner(version, route=route, call_type=call_type)
                        usage = self.responses_usage()
                        self.assertIs(self.responses_usage(usage), usage)
                        self.assertEqual(usage.prompt_tokens_details.cached_tokens, 6)
                        self.assertEqual(usage.completion_tokens_details.reasoning_tokens, 2)
                        before = copy.deepcopy(owner.model_call_details)
                        costs = copy.deepcopy(owner.cost_breakdown)
                        result = SimpleNamespace(usage=usage)
                        observed = self.capture_protected(owner, modules, result=result)
                        self.assertEqual(observed, {"schema": 1, "availability": "available", "descriptor":
                                         router.model_list[0]["model_info"][self.adapter.DESCRIPTOR_KEY]})
                        # No cost, input, result or native row-owner mutation.
                        self.assertEqual(owner.cost_breakdown, costs)
                        self.assertEqual(owner.model_call_details["messages"], before["messages"])
                        self.assertIs(result.usage, usage)
                        row_metadata = self.native["_get_spend_logs_metadata"](self.native["get_litellm_metadata_from_kwargs"](owner.model_call_details))
                        self.assertEqual(row_metadata["spend_logs_metadata"][self.adapter.DESCRIPTOR_SNAPSHOT_KEY], observed)

    def test_flat_rejects_used_cache_reasoning_but_zero_unused_details_are_flat(self):
        for details in ({"prompt_tokens_details": {"cached_tokens": 6}},
                        {"completion_tokens_details": {"reasoning_tokens": 2}}):
            owner, _, _, modules, _ = self.protected_owner()
            result = {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, **details}}
            self.assertEqual(self.capture_protected(owner, modules, result=result), self.unknown_descriptor("usage_categories"))
        owner, _, _, modules, _ = self.protected_owner()
        result = {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
                            "prompt_tokens_details": {"cached_tokens": 0, "audio_tokens": 0},
                            "completion_tokens_details": {"reasoning_tokens": 0}}}
        self.assertEqual(self.capture_protected(owner, modules, result=result)["availability"], "available")

    def test_missing_zero_malformed_native_billing_usage_remains_unconfirmed(self):
        invalid = [None, {}, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                   {"prompt_tokens": 10, "completion_tokens": 5},
                   {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 14}]
        base = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        for value in (True, 10., -1, "10", float("nan")):
            invalid.append({**base, "prompt_tokens": value})
        for value in (True, 6., -1, 11, "6"):
            invalid.append({**base, "prompt_tokens_details": {"cached_tokens": value}})
        invalid += [{**base, "prompt_tokens_details": []}, {**base, "completion_tokens_details": "SECRET"}]
        for usage in invalid:
            with self.subTest(usage=usage):
                owner, _, _, modules, _ = self.responses_owner()
                self.assertEqual(self.capture_protected(owner, modules, result={"usage": usage}),
                                 self.unknown_descriptor("usage_unconfirmed"))
        # Actual native normalization of absent usage is zero, not raw provenance.
        native_zero = self.native["ResponseAPILoggingUtils"]._transform_response_api_usage_to_chat_usage(None)
        owner, _, _, modules, _ = self.responses_owner()
        self.assertEqual(self.capture_protected(owner, modules, result=SimpleNamespace(usage=native_zero)),
                         self.unknown_descriptor("usage_unconfirmed"))

    def test_nontext_categories_and_extra_billing_never_inherit_qualified_terms(self):
        base = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        cases = [{**base, "prompt_tokens_details": {field: 1}} for field in
                 ("audio_tokens", "image_tokens", "video_tokens", "cache_write_tokens", "web_search_requests", "tool_use_tokens")]
        cases += [{**base, "completion_tokens_details": {"audio_tokens": 1}},
                  {**base, "server_tool_use": {"web_search_requests": 1}}, {**base, "unknown_billing": .5}]
        for usage in cases:
            owner, _, _, modules, _ = self.responses_owner()
            self.assertEqual(self.capture_protected(owner, modules, result={"usage": usage}), self.unknown_descriptor("usage_categories"))
        for field, value in (("tool_usage_cost", .1), ("guardrail_cost", .1), ("cache_creation_cost", .1),
                             ("additional_costs", {"SECRET": .1}), ("margin_percent", .1), ("discount_amount", .1)):
            owner, _, _, modules, _ = self.responses_owner()
            owner.cost_breakdown[field] = value
            before = copy.deepcopy(owner.cost_breakdown)
            self.assertEqual(self.capture_protected(owner, modules, result=SimpleNamespace(usage=self.responses_usage())),
                             self.unknown_descriptor("extra_billing"))
            self.assertEqual(owner.cost_breakdown, before)

    def test_native_usage_cost_is_only_monetary_metadata_and_never_prices_tokens(self):
        for cost in (None, 0, 0., .2, 999999):
            for native in (False, True):
                with self.subTest(cost=cost, native=native):
                    owner, router, _, modules, _ = self.protected_owner()
                    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": cost}
                    if native:
                        usage = self.native["Usage"](**usage)
                    result = SimpleNamespace(usage=usage)
                    before = copy.deepcopy(usage)
                    costs = copy.deepcopy(owner.cost_breakdown)
                    observed = self.capture_protected(owner, modules, result=result)
                    self.assertEqual(observed, {"schema": 1, "availability": "available", "descriptor":
                                     router.model_list[0]["model_info"][self.adapter.DESCRIPTOR_KEY]})
                    self.assertEqual(owner.cost_breakdown, costs)
                    self.assertEqual(usage, before)
                    self.assertIs(result.usage, usage)

    def test_invalid_usage_cost_and_other_categories_still_fail_closed(self):
        class NumericSubclass(float):
            pass
        base = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        invalid = [{**base, "cost": cost} for cost in
                   (True, False, -1, -.2, float("nan"), float("inf"), -float("inf"),
                    "private-cost", {}, [], NumericSubclass(.2))]
        invalid += [{**base, "cost": .2, field: value} for field, value in
                    (("unknown_billing", 1), ("response_cost", .2), ("server_tool_use", {"web_search_requests": 1}))]
        invalid += [{**base, "cost": .2, "prompt_tokens_details": {"cached_tokens": 1}},
                    {**base, "cost": .2, "completion_tokens_details": {"reasoning_tokens": 1}},
                    {**base, "cost": .2, "completion_tokens_details": {"audio_tokens": 1}}]
        for usage in invalid:
            with self.subTest(usage=usage):
                owner, _, _, modules, _ = self.protected_owner()
                self.assertEqual(self.capture_protected(owner, modules, result={"usage": usage}),
                                 self.unknown_descriptor("usage_categories"))

    def test_used_rates_must_be_explicit_protected_and_match_native_billing(self):
        for field in ("cache_read_input_token_cost", "output_cost_per_reasoning_token"):
            for value in (None, .8, True):
                owner, router, _, modules, _ = self.responses_owner()
                router.model_list[0]["model_info"][field] = value
                self.assertEqual(self.capture_protected(owner, modules, result=SimpleNamespace(usage=self.responses_usage())),
                                 self.unknown_descriptor("rate_mismatch"))
        owner, router, _, modules, _ = self.responses_owner()
        for field in ("cache_read_input_token_cost", "output_cost_per_reasoning_token"):
            router.model_list[0]["model_info"].pop(field)
        owner.cost_breakdown.pop("cache_read_cost")
        owner.cost_breakdown.pop("reasoning_cost")
        self.assertEqual(self.capture_protected(owner, modules)["availability"], "available")

    def test_inconsistent_category_costs_and_late_usage_do_not_relabel_a_capture(self):
        for field in ("cache_read_cost", "reasoning_cost"):
            owner, _, _, modules, _ = self.protected_owner()
            owner.cost_breakdown[field] = .1
            self.assertEqual(self.capture_protected(owner, modules), self.unknown_descriptor("usage_unconfirmed"))
        owner, _, _, modules, _ = self.responses_owner()
        original = self.capture_protected(owner, modules, result=SimpleNamespace(usage=self.responses_usage()))
        with patch.dict(sys.modules, modules):
            self.run_hooks(owner, {"usage": None})
        self.assertEqual(self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY], original)
        owner, _, _, modules, _ = self.responses_owner()
        original = self.capture_protected(owner, modules, result={"usage": None})
        with patch.dict(sys.modules, modules):
            self.run_hooks(owner, SimpleNamespace(usage=self.responses_usage()))
        self.assertEqual(self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY], original)

    def test_native_normalization_precedes_hook_and_streaming_uses_completed_billing_usage(self):
        helper = next(node for node in self.logging_source.body if getattr(node, "name", None) == "_success_handler_helper_fn")
        body = next(node for node in self.logging_source.body if getattr(node, "name", None) == "_async_success_handler_body")
        normalization = next(node.lineno for node in ast.walk(helper) if isinstance(node, ast.Call)
                             and isinstance(node.func, ast.Attribute) and node.func.attr == "_transform_usage_objects")
        self.assertGreater(normalization, helper.lineno)
        called = [(node.lineno, node.func.attr) for node in ast.walk(body) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        self.assertLess(min(line for line, name in called if name == "_success_handler_helper_fn"),
                        min(line for line, name in called if name == "async_logging_hook"))
        for complete_usage, availability in ((self.billing_result(), "available"), ({"usage": None}, "unknown")):
            owner, _, _, modules, _ = self.protected_owner()
            owner.stream = True
            with patch.dict(sys.modules, modules):
                asyncio.run(self.adapter.handler.async_pre_call_hook(self.bind_auth_route(self.Auth()), None,
                            {"litellm_logging_obj": owner}, "acompletion"))
                self.run_hooks(owner)
                self.assertNotIn(self.adapter.DESCRIPTOR_SNAPSHOT_KEY, self.bucket(owner))
                owner.model_call_details["async_complete_streaming_response"] = complete_usage
                self.run_hooks(owner, {"usage": None})
            self.assertEqual(self.bucket(owner)[self.adapter.DESCRIPTOR_SNAPSHOT_KEY]["availability"], availability)

    def test_responses_qualifier_preserves_auth_router_and_route_family_boundaries(self):
        for mutation, reason in (("anonymous", "eligibility"), ("clientside", "settings"),
                                 ("foreign_selected", "selected_model_info"), ("chat_type", "call_type")):
            owner, _, proxy, modules, _ = self.responses_owner()
            if mutation == "clientside":
                proxy.general_settings["allow_client_side_credentials"] = True
            if mutation == "foreign_selected":
                metadata = self.native["get_litellm_metadata_from_kwargs"](owner.model_call_details)
                metadata["model_info"] = copy.deepcopy(metadata["model_info"])
            if mutation == "chat_type":
                owner.call_type = "acompletion"
            before = copy.deepcopy(owner.model_call_details)
            observed = self.capture_protected(owner, modules, auth=mutation != "anonymous",
                                              result=SimpleNamespace(usage=self.responses_usage()))
            self.assertEqual(observed, self.unknown_descriptor(reason))
            self.assertEqual(self.snapshot(owner)["availability"], "available")
            for key in (self.adapter.SNAPSHOT_KEY, self.adapter.DESCRIPTOR_SNAPSHOT_KEY):
                del self.bucket(owner)[key]
            self.assertEqual(owner.model_call_details, before)

    def test_original_native_private_cache_counts_are_not_erased_by_serialization(self):
        for field, index in (("_cache_read_input_tokens", 0), ("_cache_creation_input_tokens", 2)):
            for qualifier in ("flat_input_output", "text_cache_reasoning"):
                with self.subTest(field=field, qualifier=qualifier):
                    usage = self.native["Usage"](prompt_tokens=10, completion_tokens=5, total_tokens=15, **{field: 2})
                    self.assertNotIn(field, usage.model_dump())
                    self.assertEqual(self.native["_cache_token_counts"](usage)[index], 2)
                    declaration = self.descriptor()
                    declaration["qualified_usage"] = qualifier
                    owner, router, _, modules, _ = self.protected_owner(descriptor=declaration)
                    before_usage = usage.model_dump()
                    before_counts = self.native["_cache_token_counts"](usage)
                    before_cost = copy.deepcopy(owner.cost_breakdown)
                    observed = self.capture_protected(owner, modules, result=SimpleNamespace(usage=usage))
                    # Cache creation is unsupported even when its billed rate/cost
                    # happens to be zero; read needs an explicit protected rate.
                    reason = "rate_mismatch" if field == "_cache_read_input_tokens" and qualifier == "text_cache_reasoning" else "usage_categories"
                    self.assertEqual(observed, self.unknown_descriptor(reason))
                    self.assertEqual(usage.model_dump(), before_usage)
                    self.assertEqual(self.native["_cache_token_counts"](usage), before_counts)
                    self.assertEqual(owner.cost_breakdown, before_cost)
        declaration = self.descriptor()
        declaration["qualified_usage"] = "text_cache_reasoning"
        for protected_rate, available in ((.01, True), (.02, False)):
            owner, router, _, modules, _ = self.protected_owner(descriptor=declaration)
            router.model_list[0]["model_info"]["cache_read_input_token_cost"] = protected_rate
            usage = self.native["Usage"](prompt_tokens=10, completion_tokens=5, total_tokens=15,
                                         _cache_read_input_tokens=2)
            observed = self.capture_protected(owner, modules, result=SimpleNamespace(usage=usage))
            self.assertEqual(observed["availability"], "available" if available else "unknown")
            if not available:
                self.assertEqual(observed["reason"], "rate_mismatch")

    def test_actual_native_guardrail_metadata_fee_enriches_row_copy_not_owner(self):
        for fee, in_spend, expected in ((.1, True, "unknown"), (.1, False, "available"), (0., True, "available")):
            with self.subTest(fee=fee, in_spend=in_spend):
                owner, _, _, modules, _ = self.protected_owner()
                metadata = self.native["get_litellm_metadata_from_kwargs"](owner.model_call_details)
                entries = [{"guardrail_name": "fixed-reviewed-fee", "guardrail_cost": fee,
                            "guardrail_cost_in_spend": in_spend}]
                metadata["standard_logging_guardrail_information"] = entries
                before = copy.deepcopy(owner.cost_breakdown)
                native_fee = self.native["guardrail_information_cost"](entries)
                self.assertEqual(native_fee, fee if in_spend else 0.)
                row_breakdown = self.native["cost_breakdown_with_guardrail"](owner.cost_breakdown, native_fee)
                if native_fee > 0:
                    self.assertIsNot(row_breakdown, owner.cost_breakdown)
                    self.assertEqual(row_breakdown["guardrail_cost"], .1)
                    self.assertNotIn("guardrail_cost", owner.cost_breakdown)
                observed = self.capture_protected(owner, modules)
                self.assertEqual(observed["availability"], expected)
                if expected == "unknown":
                    self.assertEqual(observed["reason"], "extra_billing")
                self.assertEqual(owner.cost_breakdown, before)
                self.assertIs(metadata["standard_logging_guardrail_information"], entries)
        body = selected("litellm_core_utils/litellm_logging.py", {"get_standard_logging_object_payload"})[0]
        calls = {node.func.id for node in ast.walk(body) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertTrue({"guardrail_information_cost", "cost_breakdown_with_guardrail"} <= calls)

    def test_actual_native_settings_store_preserves_config_ownership_and_auth_guard(self):
        key = "allow_client_side_credentials"
        for configured, database, available in (
            ({}, {}, True), ({}, {key: True}, False),
            ({key: False}, {key: True}, True), ({key: True}, {key: False}, False),
        ):
            with self.subTest(configured=configured, database=database):
                owner, router, proxy, modules, before = self.protected_owner()
                settings = self.native_settings(configured, database)
                original = dict(settings)
                proxy.general_settings = settings
                result = self.capture_protected(owner, modules)
                expected = ({"schema": 1, "availability": "available", "descriptor": self.descriptor()}
                            if available else {"schema": 1, "availability": "unknown", "descriptor": None,
                                               "reason": "settings"})
                self.assertEqual(result, expected)
                self.assertEqual(dict(settings), original)
                self.assertEqual(self.bucket(owner)[self.adapter.SNAPSHOT_KEY]["rates"]["input_cost_per_token"], .01)

    def test_settings_objects_outside_native_mapping_contract_still_fail_closed(self):
        for settings in (None, [], SimpleNamespace(allow_client_side_credentials=False)):
            with self.subTest(settings=settings):
                owner, router, proxy, modules, before = self.protected_owner()
                proxy.general_settings = settings
                self.assertEqual(self.capture_protected(owner, modules),
                                 {"schema": 1, "availability": "unknown", "descriptor": None, "reason": "settings"})

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
        owner.model_call_details["async_complete_streaming_response"] = self.billing_result()
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
                    "router", "deployment", "clientside_auth", "protected_id", "declaration", "billed_rates", "rate_mismatch",
                    "usage_unconfirmed", "usage_categories", "extra_billing")
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
            owner.model_call_details["async_complete_streaming_response"] = self.billing_result()
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


    def native_zero_publication(self, raw_usage, *, raw_cost_none=False, free_rates=False, reenter_none=False,
                                mutate=None, audit_descriptor=True, auth=True, context_mutate=None):
        """Actual SDK parser/guard/cost, existing protected owner, native hook/row."""
        import httpx
        import litellm
        from litellm.cost_calculator import completion_cost
        from litellm.integrations.custom_guardrail import CustomGuardrail
        from litellm.litellm_core_utils.litellm_logging import Logging
        from litellm.litellm_core_utils.llm_cost_calc.utils import BilledTokenRates
        from litellm.llms.openai.responses.transformation import OpenAIResponsesAPIConfig
        from litellm.responses.utils import ResponseAPILoggingUtils, ResponsesAPIRequestUtils
        from litellm.types.guardrails import GuardrailEventHooks
        scripts = HERE.parents[3] / 'scripts/goal584-budget-proof'
        sys.path.insert(0, str(scripts))
        from test_unknown_usage_guard import native_responses_origin, SANITIZER
        prototype, router, proxy, modules, _ = self.protected_owner(call_type='aresponses')
        if not audit_descriptor:
            for info in (router.model_list[0]['model_info'], prototype.litellm_params['model_info']):
                info.pop(self.adapter.DESCRIPTOR_KEY)
        if free_rates:
            for info in (router.model_list[0]['model_info'], prototype.litellm_params['model_info']):
                info.update(input_cost_per_token=0., output_cost_per_token=0.)
        data = native_responses_origin({'model': 'gpt-4o', 'stream': False, 'input': 'Hi'})
        owner = data['litellm_logging_obj']
        owner.litellm_params = prototype.litellm_params
        owner.model_call_details['litellm_params'] = owner.litellm_params
        owner._test_http_request = prototype._test_http_request
        metadata = self.native['get_litellm_metadata_from_kwargs'](owner.model_call_details)
        import test_cost_readback as readback
        metadata['spend_logs_metadata']['owui_budget'] = copy.deepcopy(readback.row()['metadata']['spend_logs_metadata']['owui_budget'])
        data['litellm_metadata'] = metadata
        raw = dict(id='resp_native_zero', object='response', created_at=1, model='gpt-4o', status='completed', output=[])
        if raw_usage != 'missing': raw['usage'] = raw_usage
        response = OpenAIResponsesAPIConfig().transform_response_api_response(model='gpt-4o',
            raw_response=httpx.Response(200, json=raw), logging_obj=owner)
        guard_raw = (HERE.parents[1] / 'unknown_usage_guard.py').read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(hashlib.sha256(guard_raw).hexdigest(), '7968f26f84bdba012161c8b4628bc846212e699182a34a7a4719d0bd6fe335d9')
        guard_cls = next(n for n in ast.parse(guard_raw).body if isinstance(n, ast.ClassDef) and n.name == 'UnknownUsageGuard')
        guard_cls.body = [n for n in guard_cls.body if getattr(n, 'name', None) in ('_responses_usage_available', '_record')]
        env = dict(CustomGuardrail=CustomGuardrail, Logging=Logging, ResponsesAPIRequestUtils=ResponsesAPIRequestUtils,
                   json=json, NAME='owui_budget_usage', GuardrailEventHooks=GuardrailEventHooks)
        execute([guard_cls], env)
        guard = env['UnknownUsageGuard'](guardrail_name='owui_budget_usage', event_hook=GuardrailEventHooks.post_call)
        known = guard._responses_usage_available(data, response)
        guard._record(data, 'allow' if known else 'block')
        terms = router.get_deployment(model_id=owner.get_router_model_id()).model_info
        cost = completion_cost(completion_response=response, model='gpt-4o', custom_llm_provider='openai',
            call_type='aresponses', custom_pricing=True, litellm_logging_obj=owner,
            custom_cost_per_token={k: getattr(terms, k) for k in ('input_cost_per_token', 'output_cost_per_token')})
        self.assertEqual(cost, 0)
        owner.model_call_details['response_cost'] = cost
        if raw_cost_none:
            # The actual Logging failure path returns None, even with prior rates.
            old_model, old_params = owner.model, owner.litellm_params
            owner.model = 'unregistered-native-cost-failure'; owner.litellm_params = {}
            owner.model_call_details['litellm_params'] = {}
            failed = response.model_copy(update={'model': owner.model})
            with patch.dict(sys.modules, modules):
                owner.model_call_details['response_cost'] = owner._response_cost_calculator(result=failed)
            owner.model, owner.litellm_params = old_model, old_params
            owner.model_call_details['litellm_params'] = old_params
            self.assertIsNone(owner.model_call_details['response_cost'])
        if mutate: mutate(owner, metadata)
        if context_mutate: context_mutate(owner, metadata, router, proxy)
        normalized = SimpleNamespace(usage=ResponseAPILoggingUtils._transform_response_api_usage_to_chat_usage(response.usage))
        with patch.object(self.adapter, 'Logging', Logging), patch.object(self.adapter, 'BilledTokenRates', BilledTokenRates):
            observed = self.capture_protected(owner, modules, auth=auth, result=normalized)
            if reenter_none:
                self.assertIs(self.snapshot(owner).get('native_zero_confirmed'), True)
                owner.model_call_details['response_cost'] = None
                with patch.dict(sys.modules, modules):
                    self.run_hooks(owner, normalized)
                self.assertNotIn('native_zero_confirmed', self.snapshot(owner))
        # Same pinned native sanitizer, with its complete existing dependency closure.
        with patch.dict(sys.modules, modules), patch.dict(self.native, {'_sanitize_guardrail_information_for_spend_logs': SANITIZER['_sanitize_guardrail_information_for_spend_logs']}):
            clean = self.native['_get_spend_logs_metadata'](metadata,
                guardrail_information=metadata.get('standard_logging_guardrail_information'))
        writer = selected('proxy/spend_tracking/spend_tracking_utils.py', {'get_logging_payload'})[0]
        payload = next(n for n in ast.walk(writer) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'SpendLogsPayload')
        fields = {n.arg: n.value for n in payload.keywords}
        expression = ast.Dict(keys=[ast.Constant('metadata'), ast.Constant('spend')], values=[fields['metadata'], fields['spend']])
        row = eval(compile(ast.fix_missing_locations(ast.Expression(expression)), 'actual-native-zero-row', 'eval'),
                   {'safe_dumps': json.dumps, 'clean_metadata': clean, 'kwargs': owner.model_call_details})
        if self.snapshot(owner).get('native_zero_confirmed') is True:
            api_row = readback.row(spend=row['spend'])
            api_row.update(metadata=json.loads(row['metadata']), prompt_tokens=normalized.usage.prompt_tokens,
                           completion_tokens=normalized.usage.completion_tokens, total_tokens=normalized.usage.total_tokens)
            self.assertEqual(readback.cost._row(api_row, readback.USER, readback.CHAT).spend, 0)
            # Read the actual published row through the existing reader, both
            # current-call coverage and later retained Details/reload semantics.
            async def current_and_retained():
                leaf = SimpleNamespace(requests=[], handler=None, payload=readback.page([api_row]))
                session = readback._MemoryReadSession(leaf)
                arguments = dict(base_url='http://127.0.0.1:18080', read_key='private-read-key',
                    user_id=readback.USER, root_chat_id=readback.CHAT, root_answer_id=readback.ANSWER)
                try:
                    current = await readback.cost.read_cost_snapshot(session, **arguments,
                        observed_call_ids=[readback.CALL])
                    retained = await readback.cost.read_cost_snapshot(session, **arguments)
                    self.assertTrue(current.complete)
                    self.assertEqual((current.answer.spend, current.chat.spend), (0, 0))
                    self.assertEqual(retained.answer, current.answer)
                    self.assertEqual(retained.chat, current.chat)
                finally:
                    await session.close()
            asyncio.run(current_and_retained())
        return self.snapshot(owner), observed, row, known

    def test_actual_native_zero_cost_usage_guard_snapshot_and_row_are_distinct_from_default_zero(self):
        usage = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
        snapshot, descriptor, row, known = self.native_zero_publication(usage)
        self.assertTrue(known); self.assertIs(snapshot.get('native_zero_confirmed'), True)
        self.assertEqual(descriptor['availability'], 'available')
        self.assertEqual(json.loads(row['metadata'])['spend_logs_metadata'][self.adapter.SNAPSHOT_KEY], snapshot)
        self.assertEqual(row['spend'], 0)
        paid_usage = {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15}
        snapshot, descriptor, row, known = self.native_zero_publication(paid_usage, free_rates=True)
        self.assertTrue(known); self.assertIs(snapshot.get('native_zero_confirmed'), True)
        self.assertEqual(descriptor['availability'], 'available'); self.assertEqual(row['spend'], 0)
        for raw_usage, free in ((usage, False), (paid_usage, True)):
            snapshot, descriptor, row, known = self.native_zero_publication(raw_usage,
                free_rates=free, audit_descriptor=False)
            self.assertTrue(known); self.assertIs(snapshot.get('native_zero_confirmed'), True)
            self.assertEqual(descriptor, self.unknown_descriptor('declaration'))
            self.assertEqual(row['spend'], 0)
        for mutation in ('no_auth', 'dev_mode', 'no_router', 'retired', 'alias_copy', 'foreign_metadata',
                         'absent_input_rate', 'absent_output_rate', 'mismatched_rate', 'no_billed_rates', 'wrong_route'):
            def corrupt_context(owner, metadata, router, proxy):
                if mutation == 'dev_mode': proxy.master_key = None
                elif mutation == 'no_router': proxy.llm_router = None
                elif mutation == 'retired': router.model_id_to_deployment_index_map.clear()
                elif mutation == 'alias_copy': owner.litellm_params['model_info'] = copy.deepcopy(owner.litellm_params['model_info'])
                elif mutation == 'foreign_metadata': owner.model_call_details['litellm_params'] = dict(owner.litellm_params)
                elif mutation == 'absent_input_rate': router.model_list[0]['model_info'].pop('input_cost_per_token')
                elif mutation == 'absent_output_rate': router.model_list[0]['model_info'].pop('output_cost_per_token')
                elif mutation == 'mismatched_rate': router.model_list[0]['model_info']['input_cost_per_token'] = .03
                elif mutation == 'no_billed_rates': owner.billed_token_rates = None
                elif mutation == 'wrong_route': owner._test_http_request = self.http_request('/embeddings')
            with self.subTest(native_context=mutation):
                snapshot, _, _, _ = self.native_zero_publication(usage, audit_descriptor=False,
                    auth=mutation != 'no_auth', context_mutate=corrupt_context)
                self.assertNotIn('native_zero_confirmed', snapshot)
        def paid_rates_on_zero(owner, metadata, router, proxy):
            # A native zero scalar cannot make a priced, positive-Usage call free.
            values = {field: getattr(owner.billed_token_rates, field) for field in self.adapter.RATE_FIELDS}
            values.update(input_cost_per_token=.01, output_cost_per_token=.02)
            owner.billed_token_rates = type(owner.billed_token_rates)(**values)
            for info in (router.model_list[0]['model_info'], owner.litellm_params['model_info']):
                info.update(input_cost_per_token=.01, output_cost_per_token=.02)
        snapshot, _, _, _ = self.native_zero_publication(paid_usage, free_rates=True,
            audit_descriptor=False, context_mutate=paid_rates_on_zero)
        self.assertNotIn('native_zero_confirmed', snapshot)
        for mutation in ('not_run', 'duplicate', 'breakdown', 'failure_debug'):
            def corrupt(owner, metadata):
                entries = metadata['standard_logging_guardrail_information']
                if mutation == 'not_run': entries[0]['guardrail_status'] = 'not_run'
                elif mutation == 'duplicate': entries.append(copy.deepcopy(entries[0]))
                elif mutation == 'failure_debug': owner.model_call_details['response_cost_failure_debug_information'] = {}
                else: owner.cost_breakdown['total_cost'] = .01
            snapshot, _, _, _ = self.native_zero_publication(usage, mutate=corrupt, audit_descriptor=False)
            self.assertNotIn('native_zero_confirmed', snapshot)
        for raw in ('missing', None, dict(usage, input_tokens='0')):
            with self.subTest(raw=raw):
                snapshot, _, row, known = self.native_zero_publication(raw, audit_descriptor=False)
                self.assertFalse(known); self.assertNotIn('native_zero_confirmed', snapshot)
                self.assertEqual(row['spend'], 0)
        with self.assertRaises(ValidationError):
            self.native_zero_publication(dict(usage, input_tokens=None), audit_descriptor=False)
        snapshot, _, row, _ = self.native_zero_publication(usage, raw_cost_none=True, audit_descriptor=False)
        self.assertNotIn('native_zero_confirmed', snapshot)
        self.assertIsNone(row['spend'])
        standard = selected('litellm_core_utils/litellm_logging.py', {'get_standard_logging_object_payload'})[0]
        default = next(n.value for n in ast.walk(standard) if isinstance(n, ast.AnnAssign)
                       and getattr(n.target, 'id', None) == 'llm_response_cost')
        scalar = eval(compile(ast.Expression(default), 'native-standard-cost-fallback', 'eval'), {'raw_response_cost': row['spend']})
        self.assertEqual(scalar, 0)
        import test_cost_readback as readback
        projected = readback.row(spend=scalar)
        projected.update(metadata=json.loads(row['metadata']), prompt_tokens=0, completion_tokens=0, total_tokens=0)
        with self.assertRaises(readback.cost.CostReadError):
            readback.cost._row(projected, readback.USER, readback.CHAT)
        snapshot, _, row, _ = self.native_zero_publication(usage, reenter_none=True, audit_descriptor=False)
        self.assertNotIn('native_zero_confirmed', snapshot)
        self.assertIsNone(row['spend'])

    def test_reserved_zero_snapshot_is_cleared_before_owner_or_hook_failure(self):
        forged = {self.adapter.SNAPSHOT_KEY: {'native_zero_confirmed': True}, self.adapter.DESCRIPTOR_SNAPSHOT_KEY: {'availability': 'available'}, 'owui_budget': {'preserved': True}}
        data = {'litellm_metadata': {'spend_logs_metadata': copy.deepcopy(forged)}}
        asyncio.run(self.adapter.handler.async_pre_call_hook(None, None, data, 'aresponses'))
        self.assertEqual(data['litellm_metadata']['spend_logs_metadata'], {'owui_budget': {'preserved': True}})
        owner, _, _, modules, _ = self.protected_owner()
        self.bucket(owner).update(copy.deepcopy(forged))
        with patch.dict(sys.modules, modules):
            asyncio.run(self.adapter.handler.async_pre_call_hook(self.Auth(), None, {'litellm_logging_obj': owner}, owner.call_type))
        self.assertNotIn(self.adapter.SNAPSHOT_KEY, self.bucket(owner))
        self.assertNotIn(self.adapter.DESCRIPTOR_SNAPSHOT_KEY, self.bucket(owner))
        # Callback not run: no retained caller observation survives to native row.
        owner, _, _, modules, _ = self.protected_owner()
        self.bucket(owner).update(copy.deepcopy(forged))
        with patch.dict(sys.modules, modules), patch.object(owner, 'add_dynamic_callback', side_effect=RuntimeError('registration failed')):
            with self.assertRaisesRegex(RuntimeError, '^registration failed$'):
                asyncio.run(self.adapter.handler.async_pre_call_hook(self.Auth(), None, {'litellm_logging_obj': owner}, owner.call_type))
        self.assertNotIn(self.adapter.SNAPSHOT_KEY, self.bucket(owner))
        self.assertNotIn(self.adapter.DESCRIPTOR_SNAPSHOT_KEY, self.bucket(owner))


if __name__ == "__main__":
    unittest.main()
