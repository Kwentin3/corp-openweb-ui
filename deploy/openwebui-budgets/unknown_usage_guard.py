"""Native post-call primitive for unavailable personal Responses/nonstream CC Usage.

Registration/operator-key factory belong to the server composition root. This
module never registers itself, prices a response, changes Usage or owns a ledger.
The native budget gateway must own authenticated scope; a DTO alone is not proof.
"""
from collections.abc import Callable
from importlib.metadata import version
import asyncio
import json
import re

from aiohttp import ClientSession, ClientTimeout
from fastapi import HTTPException
from litellm.integrations.custom_guardrail import CustomGuardrail, log_guardrail_information
from litellm.litellm_core_utils.litellm_logging import Logging
from litellm.proxy._types import UserAPIKeyAuth
from litellm.responses.utils import ResponsesAPIRequestUtils
from litellm.types.guardrails import GuardrailEventHooks
from litellm.types.llms.openai import ResponsesAPIResponse
from litellm.types.utils import ModelResponse

from employee_budget_admin_client import BudgetAdminClient
from employee_budget_assignment import ASSIGNMENT_NAMESPACE, assignment_matches
from provenance import validate_persisted_scope, validate_persisted_service_scope

NAME = "owui_budget_usage"
FAILURE = "Usage unavailable; model key block could not be confirmed."
ROUTES = frozenset({"/responses", "/v1/responses", "/openai/v1/responses"})
CC_ROUTES = frozenset({"/chat/completions", "/v1/chat/completions", "/openai/v1/chat/completions"})


class UnknownUsageGuard(CustomGuardrail):
    records_own_guardrail_information = True
    _cc_stream_owned_elsewhere = False

    def __init__(self, operator_key: Callable[[], str], *, base_url: str):
        if version("litellm") != "1.105.1" or not callable(operator_key):
            raise ValueError("unsupported_usage_guard_configuration")
        super().__init__(guardrail_name=NAME, event_hook=GuardrailEventHooks.post_call,
                         supported_event_hooks=[GuardrailEventHooks.post_call],
                         default_on=True, run_in_parallel=False)
        self._operator_key, self._base_url = operator_key, base_url

    def _record(self, data, action, *, not_run=False):
        unknown = action in ("block", "block_failed")
        status = ("not_run" if not_run else "success" if not unknown else "guardrail_intervened" if action == "block"
                  else "guardrail_failed_to_respond")
        self.add_standard_logging_guardrail_information_to_request_data(
            guardrail_json_response={"outcome": "not_run" if not_run else "usage_unavailable" if unknown else "usage_available"},
            request_data=data, guardrail_status=status, event_type=GuardrailEventHooks.post_call,
            tracing_detail={"violation_categories": ["usage_unavailable"] if unknown else [],
                            "guardrail_action": action})

    @staticmethod
    def _personal_scope(data):
        scopes = []
        for name in ("metadata", "litellm_metadata"):
            metadata = data.get(name)
            if isinstance(metadata, dict):
                spend = metadata.get("spend_logs_metadata")
                if isinstance(spend, dict) and "owui_budget" in spend:
                    scopes.append(spend["owui_budget"])
        if not scopes or any(scope != scopes[0] for scope in scopes):
            raise ValueError("unsupported_usage_guard_scope")
        if isinstance(scopes[0], dict) and scopes[0].get("category") == "service":
            validate_persisted_service_scope(scopes[0])
            return None
        return validate_persisted_scope(scopes[0])

    @log_guardrail_information
    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        # No streaming aggregation, model-ID decoding, or generic DTO inference.
        if not isinstance(data, dict):
            return None  # Native callback contract adopts the original response unchanged.
        if (self._cc_stream_owned_elsewhere and data.get("stream") is True
                and getattr(user_api_key_dict, "request_route", None) in CC_ROUTES):
            return response
        if not isinstance(response, (ResponsesAPIResponse, ModelResponse)) or data.get("stream", False) is not False:
            self._record(data, "allow", not_run=True)
            return response
        return await self._apply_policy(data, user_api_key_dict, response)

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
        from litellm.responses.streaming_iterator import BaseResponsesAPIStreamingIterator
        from litellm.types.router import Deployment

        source = response
        if not isinstance(source, BaseResponsesAPIStreamingIterator):
            from litellm.proxy.utils import _UpstreamStreamBoundary
            source = response._source if type(response) is _UpstreamStreamBoundary else None
        deployment = request_data.get("deployment") if isinstance(request_data, dict) else None
        if (isinstance(deployment, Deployment) and request_data.get("stream") is True
                and getattr(deployment.model_info, "supports_native_streaming", None) is False
                and getattr(deployment.model_info, "mode", None) == "responses"
                and deployment.litellm_params.model.startswith("openai/")
                and deployment.litellm_params.custom_llm_provider in (None, "openai")
                and isinstance(source, BaseResponsesAPIStreamingIterator)):
            # Core selected the full-HTTP profile. Native disconnect settlement
            # must wait for its full log rather than finalize an input estimate.
            source.has_buffered_provider_output = True

            async def drain_and_check():
                # Retain references only; the native Router owns completion and
                # its underlying adapter owns event generation and logging.
                buffered = [item async for item in response]
                full = getattr(getattr(source, "completed_response", None), "response", None)
                try:
                    if not isinstance(full, ResponsesAPIResponse):
                        self._record(request_data, "block_failed")
                        raise HTTPException(status_code=503, detail=FAILURE)
                    await self._apply_policy(request_data, user_api_key_dict, full)
                except HTTPException as error:
                    from litellm.proxy.guardrails.guardrail_hooks.unified_guardrail.unified_guardrail import resolve_endpoint_translation
                    resolved = resolve_endpoint_translation(user_api_key_dict, buffered[0] if buffered else None)
                    if resolved is None or resolved[0] != "aresponses":
                        raise
                    # Native error projection keeps the already-completed
                    # provider log and its block_failed marker as one event.
                    errors = resolved[1].build_stream_error_items(error, responses_so_far=buffered)
                    if errors is None:
                        raise
                    return errors
                return buffered

            policy = asyncio.create_task(drain_and_check())
            try:
                buffered = await asyncio.shield(policy)
            except asyncio.CancelledError:
                await policy
                raise
            for item in buffered:
                yield item
            return
        if (isinstance(request_data, dict)
                and not (self._cc_stream_owned_elsewhere and request_data.get("stream") is True
                         and getattr(user_api_key_dict, "request_route", None) in CC_ROUTES)):
            self._record(request_data, "allow", not_run=True)
        async for event in response:
            yield event

    @staticmethod
    def _cc_usage_available(data, response):
        # The pinned OpenAI SDK normalizes absent/null Usage to null here;
        # ModelResponse instead synthesizes zeros. Only the server's own
        # per-call Logging object can supply this distinction.
        log = data.get("litellm_logging_obj")
        if (not isinstance(log, Logging) or getattr(log, "stream", None) is not False
                or getattr(log, "call_type", None) != "acompletion"
                or not isinstance(data.get("litellm_call_id"), str) or not data["litellm_call_id"]
                or getattr(log, "litellm_call_id", None) != data["litellm_call_id"]):
            return False
        details = getattr(log, "model_call_details", None)
        original = details.get("original_response") if isinstance(details, dict) else None
        if not isinstance(original, str):
            return False
        try:
            original = json.loads(original)
        except (ValueError, TypeError, RecursionError):
            return False
        if (not isinstance(original, dict) or original.get("object") != "chat.completion"
                or not isinstance(response.id, str) or not response.id
                or original.get("id") != response.id or not isinstance(response.model, str) or not response.model
                or original.get("model") != response.model):
            return False
        usage = original.get("usage")
        return (isinstance(usage, dict)
                and all(type(usage.get(key)) is int and usage[key] >= 0
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
                and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"])

    @staticmethod
    def _responses_usage_available(data, response):
        # Native validation can coerce counters, or retain an unvalidated dict.
        # Only the same call's original HTTP response preserves raw presence/types.
        log = data.get("litellm_logging_obj")
        if (not isinstance(log, Logging) or getattr(log, "call_type", None) not in ("responses", "aresponses")
                or not isinstance(data.get("litellm_call_id"), str) or not data["litellm_call_id"]
                or getattr(log, "litellm_call_id", None) != data["litellm_call_id"]):
            return False
        details = getattr(log, "model_call_details", None)
        original = details.get("original_response") if isinstance(details, dict) else None
        if not isinstance(original, str) or not isinstance(response.id, str) or not response.id:
            return False
        try:
            raw = json.loads(original)
            if (not isinstance(raw, dict) or raw.get("object") != "response"
                    or not isinstance(raw.get("id"), str) or not raw["id"]
                    or raw["id"] != ResponsesAPIRequestUtils.decode_previous_response_id_to_original_previous_response_id(response.id)):
                return False
            usage = raw.get("usage")
            fields = ("input_tokens", "output_tokens", "total_tokens")
            return (isinstance(usage, dict)
                    and all(type(usage.get(key)) is int and usage[key] >= 0 for key in fields)
                    and usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]
                    and response.usage is not None
                    and all(response.usage.get(key) == usage[key] for key in fields))
        except (ValueError, TypeError, AttributeError, KeyError, RecursionError):
            return False

    async def _apply_policy(self, data, user_api_key_dict, response):
        cc = isinstance(response, ModelResponse)
        if not cc and self._responses_usage_available(data, response):
            self._record(data, "allow")
            return response
        return await self._apply_personal_policy(
            data, user_api_key_dict, response, cc=cc,
            usage_available=cc and self._cc_usage_available(data, response))

    async def _apply_personal_policy(self, data, user_api_key_dict, response, *, cc, usage_available):
        auth = user_api_key_dict
        if (not isinstance(auth, UserAPIKeyAuth) or auth.authenticated_by_custom_auth is not True
                or auth.request_route not in (CC_ROUTES if cc else ROUTES) or not isinstance(auth.metadata, dict)
                or auth.metadata.get("owui_budget_namespace") != ASSIGNMENT_NAMESPACE):
            self._record(data, "allow", not_run=True)
            return response
        try:
            scope = self._personal_scope(data)
            if scope is None:
                self._record(data, "allow", not_run=True)
                return response
            if usage_available:
                self._record(data, "allow")
                return response
            # Native client-pricing opt-in permits caller-supplied telemetry;
            # this initial contract cannot use those assignments as its origin.
            if any(isinstance(meta, dict) and meta.get("allow_client_pricing_override") is True
                   for meta in (auth.metadata, auth.team_metadata)):
                raise ValueError("unsupported_usage_guard_pricing_opt_in")
            uid, model, key_hash = auth.user_id, scope["model"], auth.api_key
            if (scope["user_id"] != uid or data.get("model") != model
                    or not isinstance(key_hash, str) or re.fullmatch(r"[0-9a-f]{64}", key_hash) is None
                    or not assignment_matches(auth, uid, model)):
                raise ValueError("unsupported_usage_guard_assignment")
            async with ClientSession(trust_env=False, timeout=ClientTimeout(total=10)) as session:
                admin = BudgetAdminClient(session, self._base_url, self._operator_key())
                # This existing public reader validates the complete explicit native
                # user.models catalog. Personal/service eligibility is decided above;
                # a one-model read would reject an employee's other managed keys.
                before = await admin.read_service(uid)
                target = [entry for entry in before.models if entry.model == model and entry.key_hash == key_hash]
                if before.user_id != uid or len(target) != 1:
                    raise ValueError("usage_guard_fresh_assignment_changed")
                await admin.block_model_key(key_hash)
                after = await admin.read_service(uid)
                target = [entry for entry in after.models if entry.model == model and entry.key_hash == key_hash]
                if after.user_id != uid or len(target) != 1 or target[0].blocked is not True:
                    raise ValueError("usage_guard_block_unconfirmed")
            self._record(data, "block")  # Only a confirmed native commit earns this action.
        except Exception:
            self._record(data, "block_failed")
            raise HTTPException(status_code=503, detail=FAILURE) from None
        return response


class ResponsesUsageGuard(UnknownUsageGuard):
    """Opt-in peer for CCStreamUsageGuard; retains the existing Responses iterator."""

    _cc_stream_owned_elsewhere = True
    async_post_call_streaming_iterator_hook = UnknownUsageGuard.async_post_call_streaming_iterator_hook


class CCStreamUsageGuard(UnknownUsageGuard):
    """Opt-in native post-call CC owner; deliberately declares no iterator hook."""

    @staticmethod
    def _stream_attempt(data):
        log = data.get("litellm_logging_obj")
        if (not isinstance(log, Logging) or getattr(log, "stream", None) is not True
                or getattr(log, "call_type", None) != "acompletion"
                or not isinstance(data.get("litellm_call_id"), str) or not data["litellm_call_id"]
                or getattr(log, "litellm_call_id", None) != data["litellm_call_id"]):
            return None
        raw = getattr(log, "_raw_stream_usage", None)
        if (not isinstance(raw, dict) or raw.get("call_id") != log.litellm_call_id
                or (raw.get("stream_id") is not None
                    and (type(raw["stream_id"]) is not int or raw["stream_id"] <= 0))):
            return None
        return log

    @staticmethod
    def _stream_usage_available(data, response):
        log = CCStreamUsageGuard._stream_attempt(data)
        if log is None:
            return False
        details = getattr(log, "model_call_details", None)
        buckets = [data.get("metadata"), data.get("litellm_metadata")]
        if isinstance(details, dict):
            buckets.append(details.get("metadata"))
            params = details.get("litellm_params")
            if isinstance(params, dict):
                buckets.append(params.get("metadata"))
        if any(isinstance(meta, dict) and meta.get("client_disconnected") is True for meta in buckets):
            return False
        raw = log._raw_stream_usage
        if (type(raw.get("stream_id")) is not int or raw["stream_id"] <= 0
                or raw.get("seen") is not True or raw.get("valid") is not True
                or raw.get("invalid") is not False):
            return False
        counts = raw.get("counts")
        usage = getattr(response, "usage", None)
        return (type(counts) is tuple and len(counts) == 3
                and all(type(value) is int and value >= 0 for value in counts)
                and counts[2] == counts[0] + counts[1]
                and usage is not None
                and all(getattr(usage, field, None) == value for field, value in zip(
                    ("prompt_tokens", "completion_tokens", "total_tokens"), counts)))

    @log_guardrail_information
    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        if (not isinstance(data, dict) or data.get("stream") is not True
                or getattr(user_api_key_dict, "request_route", None) not in CC_ROUTES):
            return response
        return await self._apply_personal_policy(
            data, user_api_key_dict, response, cc=True,
            usage_available=isinstance(response, ModelResponse) and self._stream_usage_available(data, response))

    async def async_post_call_failure_hook(
        self, request_data, original_exception, user_api_key_dict, traceback_str=None,
    ):
        if (not isinstance(request_data, dict) or request_data.get("stream") is not True
                or getattr(user_api_key_dict, "request_route", None) not in CC_ROUTES
                or not self.should_run_guardrail(
                    data=request_data, event_type=GuardrailEventHooks.post_call)
                or self._stream_attempt(request_data) is None):
            return None
        # A failed/cancelled transport cannot confirm a completed response,
        # even if its latest observed raw Usage was well formed.
        await self._apply_personal_policy(
            request_data, user_api_key_dict, None, cc=True, usage_available=False)
        return None
