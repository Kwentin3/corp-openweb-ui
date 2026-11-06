"""Real pinned SDK/guardrail/client owners, memory HTTP/config leaves only.

No provider transport, native auth invocation, DB persistence or UI acceptance.
The source-selected sanitizer/control helpers are exact native d665 bodies.
"""
import ast
import asyncio
import copy
from datetime import datetime
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

os.environ.update(LITELLM_LOCAL_MODEL_COST_MAP="True", LITELLM_TELEMETRY="False", DO_NOT_TRACK="1")
HERE = Path(__file__).resolve().parent
BUDGETS = HERE.parents[1] / "deploy/openwebui-budgets"
sys.path[:0] = [str(HERE), str(BUDGETS)]
try:
    sdk_version = version("litellm")
except PackageNotFoundError as error:
    if os.environ.get("GOAL584_REQUIRE_BUFFERED_NATIVE_COMPONENT") == "1":
        raise RuntimeError("Mandatory pinned native SDK is unavailable") from error
    raise unittest.SkipTest("Actual LiteLLM SDK absent; mandatory pinned-native test_unknown_usage_guard run is separate")
if sdk_version != "1.105.1":
    raise RuntimeError("Actual LiteLLM SDK version differs from the mandatory native pin")
# Reuse the existing public native HTTP boundary double; no mock base class/DTO.
from test_native_key_block import Wire
import unknown_usage_guard as G
from employee_budget_assignment import assignment_alias, assignment_metadata
import litellm_auth as auth_owner
from provenance import encode_call, decode_call
from starlette.requests import Request
import litellm
import litellm.integrations.custom_guardrail as native_guardrail
from litellm.constants import REDACTED_BY_LITELM_STRING
from litellm.proxy._types import UserAPIKeyAuth
from litellm.types.llms.openai import ResponseAPIUsage, ResponsesAPIResponse
from litellm.types.utils import PROMPT_CARRYING_GUARDRAIL_FIELDS, CustomPricingLiteLLMParams

NATIVE = Path(litellm.__file__).resolve().parent
PINS = {
    "integrations/custom_guardrail.py": "6ada6442281669b3623a1eca1f1bcb609e458e90e3d54a5273c18527f5cc0d70",
    "types/llms/openai.py": "99ce22ba2bb83dc37d9afb423ef2a6cf919a9cafca834eaad833c4a795088fdd",
    "proxy/_types.py": "2ef3c788ab6267bd3ba8bcaf336712cba9f67d49256bdfeb0a516c5de1525500",
    "types/utils.py": "99105ecf13a3676832c10b352b62c69d03fa608cdfafdafa14bad279738eeaf3",
    "proxy/spend_tracking/spend_tracking_utils.py": "52ce53917cdb6905abfe6dd61f2ffe9640e5198c9e443629177dcc727d24bd17",
    "proxy/litellm_pre_call_utils.py": "8cb60a5bb2e3d521dce4ded40020b02106d821837b0928a8e36c6dbede4b82c8",
    "proxy/utils.py": "f2b56f6e501ee6cfedbf4e9d79a19cee594fb797f1c3d2f2fd80a37faaf6a77f",
    "responses/streaming_iterator.py": "12ba734b722120386d6b4da73aa37724eec57fedbe73bc7ce64e4a8519c5c517",
    "proxy/common_request_processing.py": "4dcc3a41f8179d14ea35d25d9669b89a78063ea162767ba358817d050d2be1d0",
    "litellm_core_utils/litellm_logging.py": "58da82171935240b9280d8c208d383e147e23fb2ad4818de6994934ebf21fe79",
    "router.py": "2bcf70b609d63f231667eace7191a497a5a5179a74741fa5bdb9413d4533fbcd",
    "types/router.py": "f7dac34c660b5df2741c9612a6199a294470ab90b8f0b6daf620db21cf47cf1a",
    "proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py": "3485e5f796c39c1dc7a0b46aaed61b302535c6eb5a8a3e33d54b31675aac7568",
    "llms/openai/responses/guardrail_translation/handler.py": "ce5bddcdf3f726fe928922a9e6d0ace9ee1567c20aaf03534b338573f553e3ee",
}


def tree(relative):
    raw = (NATIVE / relative).read_bytes().replace(b"\r\n", b"\n")
    assert sha256(raw).hexdigest() == PINS[relative], relative
    return ast.parse(raw)


def selected(relative, names, namespace):
    nodes = [n for n in tree(relative).body if getattr(n, "name", None) in names
             or isinstance(n, (ast.Assign, ast.AnnAssign)) and any(getattr(t, "id", None) in names
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
    assert len(nodes) == len(names)
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes],
        type_ignores=[])), "exact-pinned-native-owners", "exec"), namespace)
    return namespace


SANITIZER = selected("proxy/spend_tracking/spend_tracking_utils.py", {
    "_NUMERIC_COMPRESSION_STAT_KEYS", "_numeric_compression_stats_from_guardrail_response",
    "_redact_prompt_fields_in_guardrail_entry", "_sanitize_guardrail_information_for_spend_logs",
    "should_store_prompts_and_responses_in_spend_logs"}, {
        "PROMPT_CARRYING_GUARDRAIL_FIELDS": PROMPT_CARRYING_GUARDRAIL_FIELDS,
        "REDACTED_BY_LITELM_STRING": REDACTED_BY_LITELM_STRING})
CONTROLS = selected("proxy/litellm_pre_call_utils.py", {
    "_CLIENT_PRICING_CONTROL_FIELDS", "_CLIENT_PRICING_METADATA_FIELDS", "_strip_client_pricing_overrides",
    "_ALLOW_CLIENT_PRICING_OVERRIDE_METADATA_KEY", "_key_or_team_metadata_flag_is_true",
    "_key_or_team_allows_client_pricing_override"}, {
        "CustomPricingLiteLLMParams": CustomPricingLiteLLMParams,
        "verbose_proxy_logger": SimpleNamespace(debug=lambda *a: None)})


class UnknownUsageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.wire = Wire()
        self.uid = str(uuid4()); self.model = "goal584-a"
        self.raw_key = "sk-synthetic-managed-guard-key"
        self.key_hash = sha256(self.raw_key.encode()).hexdigest()
        self.wire.user = {"user_id": self.uid, "user_role": "internal_user", "models": [self.model],
            "max_budget": 0, "spend": .5, "budget_duration": "1mo", "budget_reset_at": "2099-01-01T00:00:00Z"}
        self.wire.key = {"token": self.key_hash, "user_id": self.uid, "models": [self.model], "team_id": None,
            "key_alias": assignment_alias(self.uid, self.model), "metadata": assignment_metadata(self.model),
            "max_budget": 0, "spend": .5, "budget_duration": "1mo", "budget_reset_at": "2099-01-01T00:00:00Z",
            "blocked": False}
        self.other_keys = []
        original_handle = self.wire.handle
        def catalog(method, url, *args):
            status, payload = original_handle(method, url, *args)
            if url.endswith("/key/list"):
                payload["keys"].extend(copy.deepcopy(self.other_keys))
                payload.update(total_count=len(payload["keys"]), total_pages=int(bool(payload["keys"])))
            return status, payload
        self.wire.handle = catalog
        self.auth = UserAPIKeyAuth(api_key=self.raw_key, user_id=self.uid, models=[self.model],
            key_alias=self.wire.key["key_alias"], metadata=copy.deepcopy(self.wire.key["metadata"]), team_id=None)
        # Native builder stamps these server-only fields after construction.
        self.auth.authenticated_by_custom_auth = True; self.auth.request_route = "/v1/responses"
        self.scope = {"schema": 1, "category": "personal", "user_id": self.uid, "model": self.model,
            **{k: str(uuid4()) for k in ("chat_id", "answer_id", "root_chat_id", "root_answer_id", "call_id")}}
        self.data = {"model": self.model, "stream": False,
            "input": [{"type": "reasoning", "id": "rs_prior", "encrypted_content": "opaque-input"},
                {"type": "function_call_output", "call_id": "call_prior", "output": [
                    {"type": "input_image", "image_url": "data:image/png;base64,c3ludGhldGlj"}]}],
            "litellm_metadata": {"spend_logs_metadata": {"owui_budget": copy.deepcopy(self.scope)},
                "user_api_key_metadata": copy.deepcopy(self.auth.metadata)}}
        self.operator = Mock(return_value=self.wire.operator)
        self.guard = G.UnknownUsageGuard(self.operator, base_url="http://127.0.0.1:4000")
        def session(**kwargs):
            self.assertFalse(kwargs["trust_env"]); self.assertEqual(kwargs["timeout"].total, 10)
            return self.wire.session(trust_env=False)
        self.enterContext(patch.object(G, "ClientSession", session))
        self.before = copy.deepcopy((self.wire.user, self.wire.key))

    def response(self, usage="missing"):
        values = {"id": "opaque-provider-response-not-decoded", "created_at": 1, "model": "provider/opaque-model-id",
            "status": "completed", "output": [
                {"type": "reasoning", "id": "rs_final", "encrypted_content": "opaque-output", "summary": []},
                {"type": "function_call", "call_id": "call_new", "name": "render", "arguments": "{}"},
                {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "private answer"}]}]}
        if usage != "missing": values["usage"] = usage
        return ResponsesAPIResponse(**values)

    async def invoke(self, response):
        return await self.guard.async_post_call_success_hook(data=self.data, user_api_key_dict=self.auth, response=response)

    def entry(self):
        records = self.data["litellm_metadata"]["standard_logging_guardrail_information"]
        self.assertEqual(len(records), 1)
        entry = records[0]; self.assertEqual(entry["guardrail_name"], G.NAME)
        self.assertFalse(any(k in entry for k in ("guardrail_cost", "guardrail_usage", "guardrail_cost_in_spend")))
        self.assertNotIn("private answer", json.dumps(entry)); self.assertNotIn("opaque-output", json.dumps(entry))
        self.assertNotIn(self.wire.operator, json.dumps(entry))
        return entry

    def assert_finance_unchanged(self):
        expected = copy.deepcopy(self.before[1]); expected["blocked"] = True
        self.assertEqual(self.wire.user, self.before[0]); self.assertEqual(self.wire.key, expected)

    async def failed(self, response=None):
        with self.assertRaises(G.HTTPException) as caught:
            await self.invoke(response or self.response())
        self.assertEqual((caught.exception.status_code, caught.exception.detail), (503, G.FAILURE))
        entry = self.entry(); self.assertEqual(entry["guardrail_action"], "block_failed")
        self.assertEqual(entry["violation_categories"], ["usage_unavailable"])
        self.assertEqual(entry["guardrail_status"], "guardrail_failed_to_respond")

    async def test_absent_and_null_usage_confirm_targeted_block_without_response_mutation(self):
        response = self.response(); self.assertIsNone(response.usage)
        original = response.model_dump(); input_before = copy.deepcopy(self.data["input"])
        self.assertIs(await self.invoke(response), response)
        self.assertEqual(response.model_dump(), original); self.assertEqual(self.data["input"], input_before)
        self.assertIsNone(response.usage); self.assert_finance_unchanged()
        self.assertEqual([(m, p) for m, p, *_ in self.wire.requests], [
            ("GET", "/user/info"), ("GET", "/key/list"), ("GET", "/user/info"), ("POST", "/key/block"),
            ("GET", "/user/info"), ("GET", "/key/list"), ("GET", "/user/info")])
        self.assertEqual(self.wire.requests[3][2], {"key": self.key_hash})
        self.operator.assert_called_once_with()
        entry = self.entry(); self.assertEqual(entry["guardrail_action"], "block")
        self.assertEqual(entry["violation_categories"], ["usage_unavailable"])
        self.assertEqual(entry["guardrail_status"], "guardrail_intervened")

    async def test_explicit_null_usage_has_same_unavailable_semantics(self):
        response = self.response(None)
        self.assertIs(await self.invoke(response), response)
        self.assertEqual(self.entry()["guardrail_action"], "block")

    async def test_employee_with_three_real_managed_assignments_blocks_only_target(self):
        for model in ("goal584-b", "goal584-usage-absent"):
            self.wire.user["models"].append(model)
            row = copy.deepcopy(self.wire.key)
            row.update(models=[model], token=sha256(model.encode()).hexdigest(),
                key_alias=assignment_alias(self.uid, model), metadata=assignment_metadata(model))
            self.other_keys.append(row)
        user, others = copy.deepcopy(self.wire.user), copy.deepcopy(self.other_keys)
        response = self.response(); self.assertIs(await self.invoke(response), response)
        self.assertTrue(self.wire.key["blocked"])
        self.assertEqual(self.wire.user, user); self.assertEqual(self.other_keys, others)
        self.assertEqual(self.wire.key["max_budget"], 0); self.assertEqual(self.wire.key["spend"], .5)
        self.assertEqual([(path, body) for method, path, body, *_ in self.wire.requests if method == "POST"],
                         [("/key/block", {"key": self.key_hash})])

    async def test_zero_and_positive_usage_are_known_and_never_touch_operator(self):
        for tokens in (0, 10):
            with self.subTest(tokens=tokens):
                self.data["litellm_metadata"].pop("standard_logging_guardrail_information", None)
                response = self.response(ResponseAPIUsage(input_tokens=tokens, output_tokens=0, total_tokens=tokens))
                before = response.model_dump()
                with patch.object(self.guard, "_process_response", side_effect=AssertionError("raw response autolog")):
                    self.assertIs(await self.invoke(response), response)
                self.assertEqual(response.model_dump(), before)
                entry = self.entry(); self.assertEqual(entry["guardrail_action"], "allow")
                self.assertEqual(entry["violation_categories"], []); self.assertEqual(entry["guardrail_status"], "success")
        self.operator.assert_not_called(); self.assertFalse(self.wire.requests)

    async def test_stream_and_chat_completion_self_record_safe_not_run(self):
        for response, stream in ((self.response(), True), ({"choices": ["private answer"]}, False)):
            self.data["litellm_metadata"].pop("standard_logging_guardrail_information", None)
            self.data["stream"] = stream
            with patch.object(self.guard, "_process_response", side_effect=AssertionError("raw response autolog")):
                self.assertIs(await self.invoke(response), response)
            self.assertEqual(self.entry()["guardrail_status"], "not_run")
        self.operator.assert_not_called(); self.assertFalse(self.wire.requests)

    async def test_service_scope_is_not_personal_policy(self):
        self.scope = {"schema": 1, "category": "service", "user_id": self.uid, "actor_id": str(uuid4()),
            "chat_id": str(uuid4()), "call_id": str(uuid4()), "model": self.model, "task": "follow_up_generation"}
        self.data["litellm_metadata"]["spend_logs_metadata"]["owui_budget"] = self.scope
        response = self.response(); self.assertIs(await self.invoke(response), response)
        self.assertEqual(self.entry()["guardrail_status"], "not_run"); self.operator.assert_not_called()

    async def test_typed_json_cannot_forge_native_authentication_marker(self):
        values = self.auth.model_dump() | {"api_key": self.raw_key,
            "authenticated_by_custom_auth": True, "request_route": "/v1/responses"}
        self.auth = UserAPIKeyAuth.model_validate(values)
        self.assertFalse(self.auth.authenticated_by_custom_auth)
        response = self.response(); self.assertIs(await self.invoke(response), response)
        self.assertEqual(self.entry()["guardrail_status"], "not_run"); self.operator.assert_not_called()

    async def test_real_existing_signed_gateway_projection_replaces_forged_client_scope(self):
        chat, answer = str(uuid4()), str(uuid4())
        token = encode_call(self.wire.gateway, user_id=self.uid, model=self.model,
            chat_id=chat, root_chat_id=chat, answer_id=answer, root_answer_id=answer)
        self.data["litellm_metadata"]["owui_budget_provenance"] = token
        self.data["metadata"] = {"spend_logs_metadata": {"owui_budget": {"forged": True}}}
        auth_owner._apply_provenance(Request({"type": "http", "headers": []}), self.data,
            shared_gateway=True, required=True, secret=self.wire.gateway, user_id=self.uid, model=self.model,
            decoder=decode_call, chain_id=None, metadata_slot="litellm_metadata", metadata_session_id=None)
        actual = self.data["litellm_metadata"]["spend_logs_metadata"]["owui_budget"]
        self.assertEqual((actual["user_id"], actual["chat_id"], actual["answer_id"]), (self.uid, chat, answer))
        self.assertNotIn("owui_budget_provenance", self.data["litellm_metadata"])
        self.assertNotIn("owui_budget", self.data["metadata"]["spend_logs_metadata"])
        response = self.response(); self.assertIs(await self.invoke(response), response)
        self.assertEqual(self.entry()["guardrail_action"], "block")

    async def test_unmanaged_global_callback_records_safe_not_run(self):
        self.auth.metadata = {}
        response = self.response(); self.assertIs(await self.invoke(response), response)
        self.assertEqual(self.entry()["guardrail_status"], "not_run")
        self.assertEqual(self.entry()["violation_categories"], [])
        self.operator.assert_not_called(); self.assertFalse(self.wire.requests)

    async def test_foreign_scope_and_alias_fail_before_operator_http(self):
        self.data["litellm_metadata"]["spend_logs_metadata"]["owui_budget"]["user_id"] = str(uuid4())
        await self.failed(); self.operator.assert_not_called(); self.assertFalse(self.wire.requests)

    async def test_foreign_auth_assignment_fails_before_operator_http(self):
        self.auth.key_alias = assignment_alias(str(uuid4()), self.model)
        await self.failed(); self.assertFalse(self.wire.requests)

    async def test_missing_personal_scope_does_not_claim_block(self):
        self.data["litellm_metadata"]["spend_logs_metadata"].clear()
        await self.failed(); self.assertFalse(self.wire.requests)

    async def test_fresh_native_key_change_prevents_block(self):
        self.wire.key["token"] = "b" * 64
        await self.failed(); self.assertFalse(any(r[0] == "POST" for r in self.wire.requests))

    async def test_foreign_wire_model_is_not_an_alias_for_authenticated_assignment(self):
        self.data["model"] = "other-provider/model"
        await self.failed(); self.assertFalse(self.wire.requests)

    async def test_post_ack_without_fresh_blocked_get_is_not_quarantine(self):
        self.wire.ignored_block = True
        await self.failed(); self.assertFalse(self.wire.key["blocked"])

    async def test_ack_failure_never_retries_or_exposes_native_body(self):
        original = self.wire.handle
        def fail(method, url, *args):
            if url.endswith("/key/block"):
                self.wire.requests.append((method, "/key/block", args[1], args[0], {}))
                return 500, {"secret": self.wire.operator}
            return original(method, url, *args)
        self.wire.handle = fail
        await self.failed(); self.assertEqual(sum(p == "/key/block" for _, p, *_ in self.wire.requests), 1)

    async def test_late_read_failure_records_block_failed_even_after_commit(self):
        original = self.wire.handle
        def fail(method, url, *args):
            if self.wire.key["blocked"] and url.endswith("/user/info"):
                return 503, {"secret": self.wire.operator}
            return original(method, url, *args)
        self.wire.handle = fail
        await self.failed(); self.assertTrue(self.wire.key["blocked"])
        self.assertEqual(self.wire.key["spend"], .5)

    async def test_lazy_operator_failure_has_fixed_safe_error_and_no_mutations(self):
        self.operator.side_effect = RuntimeError(self.wire.operator)
        await self.failed(); self.assertFalse(self.wire.requests)

    async def test_native_key_or_team_pricing_optin_true_is_unsupported(self):
        for key, team in ((True, None), (False, True), (None, True)):
            self.data["litellm_metadata"].pop("standard_logging_guardrail_information", None)
            self.auth.metadata = assignment_metadata(self.model) | {"allow_client_pricing_override": key}
            self.auth.team_metadata = {"allow_client_pricing_override": team}
            self.assertTrue(CONTROLS["_key_or_team_allows_client_pricing_override"](self.auth))
            await self.failed()
        self.assertFalse(self.wire.requests)

    async def test_client_marker_is_stripped_by_native_owner_and_never_authorizes_block(self):
        self.data["litellm_metadata"]["standard_logging_guardrail_information"] = [{
            "guardrail_name": G.NAME, "violation_categories": ["usage_unavailable"], "guardrail_action": "block"}]
        CONTROLS["_strip_client_pricing_overrides"](self.data)
        self.assertNotIn("standard_logging_guardrail_information", self.data["litellm_metadata"])
        response = self.response(); self.assertIs(await self.invoke(response), response)
        self.assertEqual(self.entry()["guardrail_action"], "block"); self.assertTrue(self.wire.requests)

    async def test_marker_survives_real_native_spend_log_prompt_sanitizer_without_fees(self):
        await self.invoke(self.response())
        entry = copy.deepcopy(self.entry()); entry.update(classification={"private": "answer"})
        server = ModuleType("litellm.proxy.proxy_server"); server.general_settings = {"store_prompts_in_spend_logs": False}
        with patch.dict(sys.modules, {"litellm.proxy.proxy_server": server}), patch.dict(os.environ, {"STORE_PROMPTS_IN_SPEND_LOGS": "False"}):
            saved = SANITIZER["_sanitize_guardrail_information_for_spend_logs"]([entry])[0]
        self.assertEqual(saved["guardrail_response"], REDACTED_BY_LITELM_STRING)
        self.assertEqual(saved["classification"], REDACTED_BY_LITELM_STRING)
        self.assertEqual(saved["guardrail_action"], "block"); self.assertEqual(saved["violation_categories"], ["usage_unavailable"])
        self.assertNotIn("guardrail_cost", saved); self.assertNotIn("guardrail_usage", saved)

    async def test_actual_native_metrics_wrapper_keeps_identity_and_single_safe_self_record(self):
        node = copy.deepcopy(next(n for n in ast.walk(tree("proxy/utils.py"))
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "_run_guardrail_with_metrics"))
        node.decorator_list = []  # Execute the native staticmethod body, metrics sink is an IO leaf.
        metrics = Mock()
        env = {"time": time, "ProxyLogging": SimpleNamespace(_emit_guardrail_metrics=metrics)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node],
            type_ignores=[])), "pinned-native-run-guardrail-metrics", "exec"), env)
        response = self.response(ResponseAPIUsage(input_tokens=0, output_tokens=0, total_tokens=0))
        self.assertIs(await env["_run_guardrail_with_metrics"](
            self.guard, self.invoke(response), "post_call", self.data), response)
        self.assertEqual(self.entry()["guardrail_action"], "allow")
        self.assertEqual(metrics.call_args.kwargs["status"], "success")
        self.assertEqual(metrics.call_args.kwargs["guardrail_name"], G.NAME)

    def test_real_native_guardrail_configuration_and_admin_optout_are_preserved(self):
        self.assertIsInstance(self.guard, native_guardrail.CustomGuardrail)
        self.assertTrue(self.guard.default_on); self.assertFalse(self.guard.run_in_parallel)
        self.assertEqual(self.guard.event_hook, G.GuardrailEventHooks.post_call)
        self.operator.assert_not_called()  # Bootstrap can instantiate before the operator exists.
        event = G.GuardrailEventHooks.post_call
        self.assertTrue(self.guard.should_run_guardrail(data=self.data, event_type=event))
        self.data["disable_global_guardrails"] = True  # Raw caller flag is not native admin metadata.
        self.assertTrue(self.guard.should_run_guardrail(data=self.data, event_type=event))
        self.data["litellm_metadata"]["user_api_key_metadata"] = {"opted_out_global_guardrails": [G.NAME]}
        self.assertFalse(self.guard.should_run_guardrail(data=self.data, event_type=event))
        self.data["litellm_metadata"]["user_api_key_metadata"] = {"disable_global_guardrails": True}
        self.assertFalse(self.guard.should_run_guardrail(data=self.data, event_type=event))

    def test_actual_native_types_and_pipeline_source_are_pinned(self):
        for relative in PINS: tree(relative)
        pipeline = next(n for n in ast.walk(tree("proxy/utils.py")) if isinstance(n, ast.AsyncFunctionDef)
                        and n.name == "post_call_success_hook")
        source = ast.unparse(pipeline)
        self.assertIn("callback.should_run_guardrail", source)
        self.assertIn("callback.async_post_call_success_hook", source)
        self.assertIn("_run_guardrail_with_metrics", source)


class BufferedNativeUsageTests(unittest.IsolatedAsyncioTestCase):
    """Full SDK callback/iterator/logging component, HTTP/DB/queue leaves.

    Reuses the declared policy-auth input fixture; it does not claim genuine
    gateway admission. GUI proof owns that origin. No proxy import/class shim.
    The existing Linux image must run this group with the mandatory flag.
    """
    @classmethod
    def setUpClass(cls):
        try:
            import litellm.proxy.utils as proxy
            from litellm.proxy import proxy_server
            import litellm.proxy.common_request_processing as common
            from litellm.proxy.common_request_processing import ProxyBaseLLMRequestProcessing
            from litellm.responses.streaming_iterator import BaseResponsesAPIStreamingIterator
            from litellm.llms.openai.responses.transformation import OpenAIResponsesAPIConfig
            from litellm.litellm_core_utils.litellm_logging import Logging
            from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER
        except ImportError as error:
            if os.environ.get("GOAL584_REQUIRE_BUFFERED_NATIVE_COMPONENT") == "1":
                raise RuntimeError("Mandatory full native proxy component is unavailable") from error
            raise unittest.SkipTest("Partial SDK cannot cold-import native proxy; mandatory Linux-image preflight required") from error
        cls.proxy,cls.server,cls.processor=proxy,proxy_server,ProxyBaseLLMRequestProcessing
        cls.common=common
        cls.iterator,cls.config,cls.logging=BaseResponsesAPIStreamingIterator,OpenAIResponsesAPIConfig,Logging
        cls.worker=GLOBAL_LOGGING_WORKER
        for name in PINS: tree(name)

    response=UnknownUsageTests.response
    entry=UnknownUsageTests.entry
    assert_finance_unchanged=UnknownUsageTests.assert_finance_unchanged

    def setUp(self):
        UnknownUsageTests.setUp(self)
        self.data["stream"]=True
        self.router=litellm.Router(model_list=[{"model_name":self.model,
            "litellm_params":{"model":"openai/goal584-fake-office","api_key":"synthetic-component-key",
                "api_base":"http://provider:8000/v1"},
            "model_info":{"id":"buffered-native-component","mode":"responses","supports_native_streaming":False}}])
        self.enterContext(patch.object(litellm,"callbacks",[self.guard]))
        self.enterContext(patch.object(self.server,"llm_router",self.router))
        from litellm.integrations.custom_logger import CustomLogger
        self.successes=[];self.failures=[]
        successes,failures=self.successes,self.failures
        class Sink(CustomLogger):
            async def async_log_success_event(inner,kwargs,response_obj,start_time,end_time):
                successes.append(copy.deepcopy(kwargs["standard_logging_object"]))
            async def async_log_failure_event(inner,kwargs,response_obj,start_time,end_time):
                failures.append(copy.deepcopy(kwargs["standard_logging_object"]))
        sink=Sink()
        self.enterContext(patch.object(litellm,"_async_success_callback",[sink]))
        self.enterContext(patch.object(litellm,"_async_failure_callback",[sink]))
        self.enterContext(patch.object(litellm,"success_callback",[]))
        self.enterContext(patch.object(litellm,"failure_callback",[]))
        self.queue=[];self.queued=asyncio.Event()
        def enqueue(*,async_coroutine):
            self.queue.append(async_coroutine);self.queued.set()
        self.enterContext(patch.object(self.worker,"ensure_initialized_and_enqueue",side_effect=enqueue))
        self.proxy_instance=self.server.proxy_logging_obj
        from litellm.proxy.spend_tracking import budget_reservation
        # Opaque nonempty reservation input, never a fake counter/ledger. The
        # real outer owner calls this IO leaf; cash reconciliation is not run.
        self.reservation={"fixture_reservation":"buffered-native-component"}
        self.auth.budget_reservation=self.reservation
        self.cancel_release=self.enterContext(patch.object(budget_reservation,
            "release_budget_reservation_on_cancel",new_callable=AsyncMock))
        async def close_queue():
            for coroutine in self.queue: coroutine.close()
            self.queue.clear()
        self.addAsyncCleanup(close_queue)

    async def buffered(self,kind="absent"):
        import httpx
        import importlib
        from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
        from litellm.types.router import Deployment
        self.data["litellm_metadata"].pop("standard_logging_guardrail_information",None)
        usage=ResponseAPIUsage(input_tokens=0,output_tokens=0,total_tokens=0) if kind=="zero" else \
              ResponseAPIUsage(input_tokens=10,output_tokens=5,total_tokens=15) if kind in ("known","empty") else None
        raw=self.response(usage).model_dump()
        if kind=="absent":raw.pop("usage",None)
        if kind=="empty":raw["output"]=[]
        owner=importlib.import_module("litellm.llms.custom_httpx.llm_http_handler")
        case=self
        class Leaf(AsyncHTTPHandler):
            async def post(inner,*,url,stream,**kwargs):
                case.assertIs(stream,False)
                body=kwargs.get("json")
                if body is None:body=json.loads(kwargs["data"])
                case.assertNotIn("stream",body)
                case.assertEqual(body["input"],case.data["input"])
                inner.log=kwargs["logging_obj"];inner.calls=getattr(inner,"calls",0)+1
                return httpx.Response(200,json=raw,request=httpx.Request("POST",url))
        leaf=Leaf()
        with patch.object(owner,"get_async_httpx_client",return_value=leaf):
            iterator=await self.router.aresponses(model=self.model,input=copy.deepcopy(self.data["input"]),
                stream=True,litellm_metadata=copy.deepcopy(self.data["litellm_metadata"]))
        self.assertEqual(leaf.calls,1);log=leaf.log
        self.assertIsInstance(iterator,self.iterator)
        self.assertIn("FallbackResponsesStreamWrapper",type(iterator).__qualname__)
        self.assertIsNone(iterator.completed_response)
        self.assertIs(iterator.logging_obj,log)
        self.full_reference=self.config().transform_response_api_response(model="goal584-fake-office",
            raw_response=httpx.Response(200,json=raw),logging_obj=log)
        # This is exactly the native post-call assignment, from the SAME Router.
        deployment=self.router.get_deployment(model_id=self.router.model_list[0]["model_info"]["id"])
        self.assertIsInstance(deployment,Deployment);self.data["deployment"]=deployment
        self.data["litellm_logging_obj"]=log
        self.processor(self.data)._arm_deferred_stream_dispatch(iterator,"aresponses",self.auth,log)
        self.assertFalse(self.common._withheld_provider_output(iterator))
        self.native_events=[];events=self.native_events;original=type(iterator).__anext__
        async def record(instance):
            event=await original(instance)
            if instance is iterator:events.append(event)
            return event
        self.enterContext(patch.object(type(iterator),"__anext__",record))
        return iterator,log

    def pipeline(self,iterator):
        return self.proxy_instance.async_post_call_streaming_iterator_hook(response=iterator,
            user_api_key_dict=self.auth,request_data=self.data)

    def outer(self,iterator):
        return self.processor.async_streaming_data_generator(response=iterator,user_api_key_dict=self.auth,
            request_data=self.data,proxy_logging_obj=self.proxy_instance,
            serialize_chunk=lambda event:event.model_dump_json(),serialize_error=lambda error:"unexpected-error")

    async def flush(self):
        await asyncio.wait_for(self.queued.wait(),2)
        self.assertEqual(len(self.queue),1)
        await self.queue.pop()

    async def finish(self,stream,iterator,log,first=None):
        events=[] if first is None else [first]
        events.extend([event async for event in stream])
        self.assertEqual(len(events),len(self.native_events))
        for observed,native in zip(events,self.native_events):self.assertIs(observed,native)
        await self.flush()
        self.assertTrue(log._deferred_stream_complete_args is None)
        return log.model_call_details["standard_logging_object"]

    async def test_known_and_explicit_zero_preserve_every_native_event_and_single_slp_marker(self):
        for kind in ("known","zero"):
            with self.subTest(kind=kind):
                self.queued.clear();iterator,log=await self.buffered(kind);stream=self.pipeline(iterator)
                first=await anext(stream)
                self.assertEqual(self.entry()["guardrail_action"],"allow")
                payload=await self.finish(stream,iterator,log,first)
                self.assertEqual(len(payload["guardrail_information"]),1)
                self.assertEqual(payload["guardrail_information"][0]["guardrail_action"],"allow")
                self.assertFalse(self.wire.requests);self.operator.assert_not_called()

    async def test_absent_and_null_block_before_first_yield_preserve_full_response_and_one_slp(self):
        for kind in ("absent","null"):
            with self.subTest(kind=kind):
                self.wire.key["blocked"]=False;self.wire.requests.clear();self.queued.clear()
                iterator,log=await self.buffered(kind)
                stream=self.pipeline(iterator);first=await anext(stream)
                self.assertTrue(self.wire.key["blocked"]);self.assertEqual(self.entry()["guardrail_action"],"block")
                self.assertEqual(iterator.completed_response.response.output,self.full_reference.output)
                self.assertTrue(self.data["stream"])
                self.assertTrue(self.common._withheld_provider_output(iterator))
                payload=await self.finish(stream,iterator,log,first)
                self.assertEqual(len(payload["guardrail_information"]),1)
                self.assertEqual(payload["guardrail_information"][0]["guardrail_action"],"block")
                self.assertEqual(sum(p=="/key/block" for _,p,*_ in self.wire.requests),1)
                self.assert_finance_unchanged()

    async def test_native_outer_normal_preserves_events_and_emits_one_success_no_failure(self):
        iterator,log=await self.buffered("known")
        events=[json.loads(event) async for event in self.outer(iterator)]
        self.assertEqual(events,[event.model_dump(mode="json") for event in self.native_events])
        await self.flush()
        self.assertEqual(len(self.successes),1);self.assertFalse(self.failures)
        self.assertEqual(len(self.successes[0]["guardrail_information"]),1)

    async def test_native_outer_close_after_first_event_flushes_full_reply_once(self):
        iterator,log=await self.buffered("known");stream=self.outer(iterator)
        await anext(stream)
        self.assertIsInstance(iterator.completed_response.response,ResponsesAPIResponse);self.assertFalse(self.queue)
        await stream.aclose();await self.flush()
        self.assertEqual(len(self.successes),1);self.assertFalse(self.failures)
        self.assertEqual(len(self.successes[0]["guardrail_information"]),1)
        self.assertFalse(self.wire.requests);self.operator.assert_not_called()
        self.cancel_release.assert_not_awaited()

    async def test_native_outer_unbuffered_pre_event_cancel_keeps_native_reservation_release(self):
        iterator,log=await self.buffered("known");entered=asyncio.Event()
        async def raw():
            entered.set();await asyncio.Event().wait()
            yield None
        stream=self.outer(raw());pending=asyncio.create_task(anext(stream))
        await asyncio.wait_for(entered.wait(),2);pending.cancel()
        with self.assertRaises(asyncio.CancelledError):await pending
        self.cancel_release.assert_awaited_once_with(self.reservation)
        self.assertEqual(self.entry()["guardrail_status"],"not_run")
        self.assertFalse(self.queue);self.assertFalse(self.successes);self.assertFalse(self.failures)

    async def test_unconfirmed_block_native_outer_projects_safe_error_and_one_provider_log(self):
        self.wire.ignored_block=True;iterator,log=await self.buffered();stream=self.outer(iterator)
        errors=[json.loads(event) async for event in stream]
        self.assertEqual(len(errors),1);self.assertEqual(errors[0]["type"],"error")
        self.assertEqual(errors[0]["error"]["message"],G.FAILURE)
        self.assertEqual(errors[0]["error"]["code"],"503")
        await self.flush()
        self.assertEqual(self.entry()["guardrail_action"],"block_failed")
        self.assertFalse(self.failures);self.assertEqual(len(self.successes),1)
        info=self.successes[0]["guardrail_information"]
        self.assertEqual(len(info),1);self.assertEqual(info[0]["guardrail_action"],"block_failed")

    async def test_empty_output_and_reasoning_full_native_response_preserved(self):
        for kind in ("empty","known"):
            self.queued.clear();iterator,log=await self.buffered(kind)
            before=copy.deepcopy(self.data["input"])
            await self.finish(self.pipeline(iterator),iterator,log)
            self.assertEqual(iterator.completed_response.response.output,self.full_reference.output)
            self.assertEqual(self.data["input"],before)
            if kind=="known":
                self.assertEqual(iterator.completed_response.response.output[0].encrypted_content,"opaque-output")
            else:self.assertEqual(iterator.completed_response.response.output,[])

    async def test_undeclared_or_unmanaged_native_router_response_is_not_run(self):
        for variant in ("undeclared","unmanaged"):
            self.queued.clear();iterator,log=await self.buffered()
            if variant=="undeclared":self.data["deployment"].model_info.supports_native_streaming=True
            else:self.auth.metadata={}
            await self.finish(self.pipeline(iterator),iterator,log)
            self.assertEqual(self.entry()["guardrail_status"],"not_run")
            self.assertFalse(self.wire.requests);self.operator.assert_not_called()

    async def test_missing_native_completed_contract_fails_closed_without_answer_or_block_claim(self):
        iterator,log=await self.buffered();original=type(iterator).__anext__
        async def lose_completed(instance):
            try:return await original(instance)
            except StopAsyncIteration:
                # Explicit native readback fault, never a fake response DTO.
                if instance is iterator:instance.completed_response=None
                raise
        with patch.object(type(iterator),"__anext__",lose_completed):
            errors=[json.loads(event) async for event in self.outer(iterator)]
        self.assertEqual(len(errors),1);self.assertEqual(errors[0]["type"],"error")
        self.assertEqual(errors[0]["error"]["message"],G.FAILURE)
        self.assertEqual(self.entry()["guardrail_action"],"block_failed")
        self.assertFalse(self.wire.key["blocked"]);self.assertFalse(self.wire.requests)
        await self.flush();self.assertEqual(len(self.successes),1);self.assertFalse(self.failures)

    async def test_cancel_while_native_router_drain_waits_finishes_source_and_policy(self):
        iterator,log=await self.buffered();original=type(iterator).__anext__
        entered,release=asyncio.Event(),asyncio.Event()
        async def gated(instance):
            if instance is iterator and not entered.is_set():entered.set();await release.wait()
            return await original(instance)
        with patch.object(type(iterator),"__anext__",gated):
            pending=asyncio.create_task(anext(self.outer(iterator)))
            await asyncio.wait_for(entered.wait(),2);pending.cancel()
            turn=asyncio.Event();asyncio.get_running_loop().call_soon(turn.set);await turn.wait()
            self.assertFalse(pending.done());self.assertIsNone(iterator.completed_response)
            self.assertTrue(self.common._withheld_provider_output(iterator));self.assertFalse(self.queue)
            release.set()
            with self.assertRaises(asyncio.CancelledError):await pending
        self.assertTrue(self.wire.key["blocked"]);self.assertEqual(self.entry()["guardrail_action"],"block")
        self.cancel_release.assert_not_awaited();await self.flush()
        self.assertEqual(len(self.successes),1);self.assertFalse(self.failures)

    async def test_unsupported_real_async_stream_passes_through_as_not_run(self):
        original=[{"unqualified_event":1},{"unqualified_event":2}]
        async def raw():
            for event in original:yield event
        self.assertEqual([event async for event in self.pipeline(raw())],original)
        self.assertEqual(self.entry()["guardrail_status"],"not_run")
        self.assertFalse(self.wire.requests);self.operator.assert_not_called()

    async def test_native_optout_and_service_exclusion_keep_existing_policy(self):
        self.data["litellm_metadata"]["user_api_key_metadata"]={"disable_global_guardrails":True}
        iterator,log=await self.buffered();await self.finish(self.pipeline(iterator),iterator,log)
        self.assertNotIn("standard_logging_guardrail_information",self.data["litellm_metadata"])
        self.data["litellm_metadata"]["user_api_key_metadata"]=copy.deepcopy(self.auth.metadata);self.queued.clear()
        self.data["litellm_metadata"]["spend_logs_metadata"]["owui_budget"]={"schema":1,"category":"service",
            "user_id":self.uid,"actor_id":str(uuid4()),"chat_id":str(uuid4()),"call_id":str(uuid4()),
            "model":self.model,"task":"follow_up_generation"}
        iterator,log=await self.buffered();await self.finish(self.pipeline(iterator),iterator,log)
        self.assertEqual(self.entry()["guardrail_status"],"not_run")
        self.assertFalse(self.wire.requests);self.operator.assert_not_called()

    async def test_cancel_while_block_or_readback_waits_finishes_policy_before_cleanup(self):
        for phase in ("block","readback","failed_readback"):
            with self.subTest(phase=phase):
                self.wire.key["blocked"]=False;self.wire.requests.clear();self.queued.clear()
                self.successes.clear();self.failures.clear();iterator,log=await self.buffered()
                entered,release=asyncio.Event(),asyncio.Event();factory=G.ClientSession
                def session(**kwargs):
                    original=factory(**kwargs)
                    class Session:
                        async def __aenter__(inner):await original.__aenter__();return inner
                        async def __aexit__(inner,*args):return await original.__aexit__(*args)
                        def request(inner,method,url,**kw):
                            gated=(phase=="block" and url.endswith("/key/block")) or \
                                (phase in ("readback","failed_readback") and self.wire.key["blocked"] and url.endswith("/user/info"))
                            class Response:
                                async def __aenter__(item):
                                    if gated:entered.set();await release.wait()
                                    if gated and phase=="failed_readback":
                                        raise RuntimeError("controlled HTTP readback IO failure")
                                    item.actual=original.request(method,url,**kw);return await item.actual.__aenter__()
                                async def __aexit__(item,*args):return await item.actual.__aexit__(*args)
                            return Response()
                    return Session()
                with patch.object(G,"ClientSession",session):
                    stream=self.outer(iterator);pending=asyncio.create_task(anext(stream))
                    await asyncio.wait_for(entered.wait(),2);pending.cancel()
                    self.assertTrue(self.common._withheld_provider_output(iterator))
                    turn=asyncio.Event();asyncio.get_running_loop().call_soon(turn.set);await turn.wait()
                    self.assertFalse(pending.done());self.assertIsInstance(iterator.completed_response.response,ResponsesAPIResponse)
                    self.assertFalse(self.queue)
                    release.set()
                    with self.assertRaises(asyncio.CancelledError):await pending
                self.assertTrue(self.wire.key["blocked"])
                await self.flush();self.assertFalse(self.failures);self.assertEqual(len(self.successes),1)
                payload=self.successes[0];action="block_failed" if phase=="failed_readback" else "block"
                self.assertEqual(self.entry()["guardrail_action"],action)
                self.assertEqual(len(payload["guardrail_information"]),1)
                self.assertEqual(payload["guardrail_information"][0]["guardrail_action"],action)
                self.assertIsInstance(iterator.completed_response.response,ResponsesAPIResponse)
                self.cancel_release.assert_not_awaited()
                self.assertEqual(sum(p=="/key/block" for _,p,*_ in self.wire.requests),1)


if __name__ == "__main__":
    unittest.main()
