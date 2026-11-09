"""Copy native request-owned billed rates into the native spend-row metadata.

Source candidate for LiteLLM d665dc1a; not enabled by this module alone.
Observed time is a capture time, never a tariff version or effective interval.
The optional descriptor represents protected declared terms, not publication
immutability, source checking, or native effective-interval enforcement.
Qualification concerns categories used by native billing, not whether the
provider reported usage or native code estimated it.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from datetime import datetime, timezone
import math
import re
from urllib.parse import unquote, urlsplit

from litellm.integrations.custom_logger import CustomLogger
from litellm.litellm_core_utils.core_helpers import get_litellm_metadata_from_kwargs
from litellm.litellm_core_utils.litellm_logging import Logging
from litellm.litellm_core_utils.llm_cost_calc.utils import BilledTokenRates, _cache_token_counts, _reasoning_token_count
from litellm.litellm_core_utils.llm_cost_calc.guardrail_cost import guardrail_information_cost
from litellm.types.utils import Usage


SNAPSHOT_KEY = "owui_billed_token_rates"
DESCRIPTOR_KEY = "owui_pricing"
DESCRIPTOR_SNAPSHOT_KEY = "owui_tariff_descriptor"
DESCRIPTOR_UNKNOWN_REASONS = (
    "eligibility", "call_type", "request_body", "selected_model_info", "model_id",
    "settings", "router", "deployment", "clientside_auth", "protected_id",
    "declaration", "billed_rates", "rate_mismatch", "usage_unconfirmed",
    "usage_categories", "extra_billing",
)
DESCRIPTOR_FIELDS = frozenset({
    "schema", "deployment_id", "currency", "source_ref", "source_url",
    "source_checked_at_utc", "declared_effective_from_utc",
    "declared_effective_until_utc", "activation_ref", "qualified_usage",
})
_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_CREDENTIAL = re.compile(r"(?:sk-|gw-)[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
_COMPLETION_ROUTES = frozenset({"/chat/completions", "/v1/chat/completions", "/openai/v1/chat/completions"})
_RESPONSES_ROUTES = frozenset({"/responses", "/v1/responses", "/openai/v1/responses"})
RATE_FIELDS = (
    "input_cost_per_token",
    "output_cost_per_token",
    "cache_read_input_token_cost",
    "cache_read_input_audio_token_cost",
    "cache_creation_input_token_cost",
    "cache_creation_input_token_cost_above_1hr",
    "output_cost_per_reasoning_token",
)


def _utc(value):
    if type(value) is not str or not _UTC.fullmatch(value):
        raise ValueError("Invalid declaration timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _descriptor(value):
    """A strict primitive projection; dates are declarations, not activation."""
    if type(value) is not dict or set(value) != DESCRIPTOR_FIELDS:
        raise ValueError("Invalid declaration schema")
    if type(value["schema"]) is not int or value["schema"] != 1:
        raise ValueError("Unknown declaration schema")
    if type(value["qualified_usage"]) is not str or value["qualified_usage"] not in ("flat_input_output", "text_cache_reasoning"):
        raise ValueError("Unqualified pricing categories")
    for field in ("deployment_id", "source_ref", "activation_ref"):
        text = value[field]
        if type(text) is not str or not _REFERENCE.fullmatch(text) or _CREDENTIAL.search(text):
            raise ValueError("Invalid declaration reference")
    if type(value["currency"]) is not str or not re.fullmatch(r"[A-Z]{3}", value["currency"]):
        raise ValueError("Invalid declared currency")
    _utc(value["source_checked_at_utc"])
    start = _utc(value["declared_effective_from_utc"])
    end = value["declared_effective_until_utc"]
    if end is not None and _utc(end) <= start:
        raise ValueError("Invalid declared interval")
    url = value["source_url"]
    if url is not None:
        if type(url) is not str or len(url) > 512 or any(c.isspace() or ord(c) < 32 for c in url):
            raise ValueError("Invalid source URL")
        parsed = urlsplit(url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or _CREDENTIAL.search(unquote(url))):
            raise ValueError("Credential-bearing or invalid source URL")
        if parsed.port == 0:  # Also validate malformed ports without fetching.
            raise ValueError("Invalid source port")
    return {field: value[field] for field in DESCRIPTOR_FIELDS}


def _billing_categories(result):
    """Project canonical native billing Usage; never infer or price tokens.

    Native Logging normalizes Responses usage before this hook and assembles
    streaming usage before its complete signal. Zero cannot establish a used
    category, including when native normalization replaced absent usage by zero.
    """
    usage = result.get("usage") if isinstance(result, Mapping) else getattr(result, "usage", None)
    # Native billing can consume private Usage counters absent from model_dump.
    # Resolve them on the original owner before taking a primitive projection.
    native_usage = usage if isinstance(usage, Usage) else None
    cache_counts = _cache_token_counts(native_usage) if native_usage is not None else None
    reasoning = _reasoning_token_count(native_usage) if native_usage is not None else None
    if callable(getattr(usage, "model_dump", None)):
        usage = usage.model_dump()
    if not isinstance(usage, Mapping):
        return None, "usage_unconfirmed"
    counts = [usage.get(field) for field in ("prompt_tokens", "completion_tokens", "total_tokens")]
    if (any(type(value) is not int or value < 0 for value in counts)
            or counts[2] == 0 or counts[0] + counts[1] != counts[2]):
        return None, "usage_unconfirmed"
    used = {"cached_tokens": 0, "reasoning_tokens": 0}
    for field, supported, limit in (
        ("prompt_tokens_details", ("text_tokens", "cached_tokens"), counts[0]),
        ("completion_tokens_details", ("text_tokens", "reasoning_tokens"), counts[1]),
    ):
        details = usage.get(field)
        if details is None:
            continue
        if callable(getattr(details, "model_dump", None)):
            details = details.model_dump()
        if not isinstance(details, Mapping):
            return None, "usage_unconfirmed"
        for key, value in details.items():
            if value is None:
                continue
            if type(value) is not int or value < 0 or value > limit:
                return None, "usage_unconfirmed"
            if key not in supported and value != 0:
                return None, "usage_categories"
            if key in used:
                used[key] = value
    # Native Responses streaming stamps this monetary scalar before normalizing
    # Usage. It is not a token category or a source of billed rates.
    cost = usage.get("cost")
    if cost is not None and (type(cost) not in (int, float) or cost < 0
                             or (type(cost) is float and not math.isfinite(cost))):
        return None, "usage_categories"
    core = {"prompt_tokens", "completion_tokens", "total_tokens", "prompt_tokens_details", "completion_tokens_details", "cost"}
    if any(value is not None and not (type(value) in (int, float) and value == 0)
           for key, value in usage.items() if key not in core):
        return None, "usage_categories"
    if native_usage is None:
        # A native assembled response can carry the canonical usage mapping.
        # Its public fields were checked above; native Usage owns their parsing.
        native_usage = Usage(**usage)
        cache_counts = _cache_token_counts(native_usage)
        reasoning = _reasoning_token_count(native_usage)
    cache_read, cached_audio, cache_creation, creation_details = cache_counts
    if (any(type(value) is not int or value < 0 for value in (cache_read, cached_audio, cache_creation, reasoning))
            or cache_read > counts[0] or cached_audio > cache_read or reasoning > counts[1]):
        return None, "usage_unconfirmed"
    if cached_audio or cache_creation or creation_details is not None:
        return None, "usage_categories"
    used.update(cached_tokens=cache_read, reasoning_tokens=reasoning)
    return used, None


def _capture_descriptor(owner, params, metadata, proxy_auth, auth_route, result=None):
    unknown = {"schema": 1, "availability": "unknown", "descriptor": None,
               "reason": DESCRIPTOR_UNKNOWN_REASONS[0]}
    try:
        if not proxy_auth or auth_route not in _COMPLETION_ROUTES | _RESPONSES_ROUTES or getattr(owner, "litellm_params", None) is not params:
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[1]
        call_types = ("completion", "acompletion") if auth_route in _COMPLETION_ROUTES else ("responses", "aresponses")
        if getattr(owner, "call_type", None) not in call_types:
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[2]
        request = params.get("proxy_server_request")
        if (not isinstance(request, dict) or request.get("method") != "POST"
                or not isinstance(request.get("body"), dict)
                or any(field in request["body"] for field in ("user_config", "api_key", "api_base"))):
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[3]
        selected = params.get("model_info")
        # Native Router stamps the same copied dictionary into both locations.
        # This is a structural path check, not a signature or price version.
        if not isinstance(selected, dict) or metadata.get("model_info") is not selected:
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[4]
        native_id = owner.get_router_model_id()
        if not isinstance(native_id, str) or selected.get("id") != native_id:
            return unknown

        # Resolve expected terms only from the existing protected global owner.
        # Lazy import preserves the native callback/config startup order.
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[5]
        from litellm.proxy import proxy_server
        settings = proxy_server.general_settings
        if not isinstance(settings, Mapping) or settings.get("allow_client_side_credentials") not in (None, False):
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[6]
        router = proxy_server.llm_router
        if router is None:
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[7]
        deployment = router.get_deployment(model_id=native_id)
        if deployment is None:
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[8]
        configured = deployment.litellm_params
        optins = configured.get("configurable_clientside_auth_params") if isinstance(configured, dict) else getattr(
            configured, "configurable_clientside_auth_params", None)
        if optins not in (None, []):
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[9]
        protected = deployment.model_info
        if getattr(protected, "id", None) != native_id:
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[10]
        descriptor = _descriptor(getattr(protected, DESCRIPTOR_KEY, None))
        if descriptor["deployment_id"] != native_id or _descriptor(selected.get(DESCRIPTOR_KEY)) != descriptor:
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[11]
        rates = getattr(owner, "billed_token_rates", None)
        if not isinstance(rates, BilledTokenRates):
            return unknown
        unknown["reason"] = DESCRIPTOR_UNKNOWN_REASONS[12]
        for field in ("input_cost_per_token", "output_cost_per_token"):
            declared, billed = getattr(protected, field, None), getattr(rates, field)
            if (type(declared) not in (int, float) or type(billed) not in (int, float)
                    or not math.isfinite(declared) or not math.isfinite(billed)
                    or declared < 0 or billed < 0 or declared != billed):
                return unknown
        unknown["reason"] = "usage_unconfirmed"
        used, reason = _billing_categories(result)
        if reason is not None:
            unknown["reason"] = reason
            return unknown
        unknown["reason"] = "usage_categories"
        if descriptor["qualified_usage"] == "flat_input_output" and any(used.values()):
            return unknown
        unknown["reason"] = "extra_billing"
        if guardrail_information_cost(metadata.get("standard_logging_guardrail_information")) > 0:
            return unknown
        breakdown = getattr(owner, "cost_breakdown", None)
        if not isinstance(breakdown, Mapping):
            return unknown
        for field in ("tool_usage_cost", "guardrail_cost", "cache_creation_cost", "additional_costs",
                      "discount_percent", "discount_amount", "margin_percent", "margin_fixed_amount", "margin_total_amount"):
            value = breakdown.get(field)
            if value is not None and not (type(value) in (int, float) and value == 0) and value != {}:
                return unknown
        unknown["reason"] = "usage_unconfirmed"
        for field, category in (("cache_read_cost", "cached_tokens"), ("reasoning_cost", "reasoning_tokens")):
            value = breakdown.get(field)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)
                                      or value < 0 or (value > 0 and used[category] == 0)):
                return unknown
        unknown["reason"] = "rate_mismatch"
        for category, field in (("cached_tokens", "cache_read_input_token_cost"),
                                ("reasoning_tokens", "output_cost_per_reasoning_token")):
            if used[category] > 0:
                declared, billed = getattr(protected, field, None), getattr(rates, field)
                if (type(declared) not in (int, float) or type(billed) not in (int, float)
                        or not math.isfinite(declared) or not math.isfinite(billed)
                        or declared < 0 or billed < 0 or declared != billed):
                    return unknown
        return {"schema": 1, "availability": "available", "descriptor": descriptor}
    except Exception:
        # Observability must preserve native cost handling and never export a
        # private declaration, URL or exception as diagnostic text.
        return unknown


class _RequestSnapshot(CustomLogger):
    """A dynamic native callback belonging to exactly one Logging object."""

    def __init__(self, owner: Logging, proxy_auth=False, auth_route=None):
        super().__init__()
        self._owner = owner
        self._snapshot = None
        self._proxy_auth = proxy_auth
        self._auth_route = auth_route
        self._descriptor_snapshot = None

    async def async_logging_hook(self, kwargs, result, call_type):
        # Native Logging passes this object to hooks before ProxyTrackCost runs.
        # A foreign mapping must never receive another request's rates.
        if not isinstance(kwargs, dict) or kwargs is not getattr(self._owner, "model_call_details", None):
            return kwargs, result
        if getattr(self._owner, "stream", False) is True and "async_complete_streaming_response" not in kwargs:
            return kwargs, result
        params = kwargs.get("litellm_params")
        if not isinstance(params, dict):
            return kwargs, result
        metadata = get_litellm_metadata_from_kwargs(kwargs)
        # Reject the native helper's ephemeral empty fallback. Only the actual
        # selected native bucket can feed the same row writer.
        if not isinstance(metadata, dict) or not any(
            metadata is params.get(key) for key in ("metadata", "litellm_metadata")
        ):
            return kwargs, result
        spend_metadata = metadata.get("spend_logs_metadata")
        if not isinstance(spend_metadata, dict):
            return kwargs, result
        if self._snapshot is None:
            native_rates = getattr(self._owner, "billed_token_rates", None)
            rates = dict.fromkeys(RATE_FIELDS)
            if isinstance(native_rates, BilledTokenRates):
                for field in RATE_FIELDS:
                    value = getattr(native_rates, field, None)
                    if type(value) in (int, float):
                        try:
                            if math.isfinite(value):
                                rates[field] = value
                        except OverflowError:
                            pass
            present = sum(value is not None for value in rates.values())
            self._snapshot = {
                "schema": 1,
                "availability": "available" if present == len(RATE_FIELDS) else "partial" if present else "unknown",
                "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "rates": rates,
            }
        # Copy the representation so consumers cannot mutate the frozen capture.
        spend_metadata[SNAPSHOT_KEY] = {**self._snapshot, "rates": dict(self._snapshot["rates"])}
        if self._descriptor_snapshot is None:
            billing_result = kwargs["async_complete_streaming_response"] if getattr(self._owner, "stream", False) is True else result
            self._descriptor_snapshot = _capture_descriptor(self._owner, params, metadata, self._proxy_auth, self._auth_route, billing_result)
        spend_metadata[DESCRIPTOR_SNAPSHOT_KEY] = copy.deepcopy(self._descriptor_snapshot)
        return kwargs, result


class PricingSnapshot(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        owner = data.get("litellm_logging_obj") if isinstance(data, dict) else None
        if not isinstance(owner, Logging):
            return None
        callbacks = getattr(owner, "dynamic_async_success_callbacks", None) or ()
        if not any(isinstance(callback, _RequestSnapshot) and callback._owner is owner for callback in callbacks):
            proxy_auth = False
            auth_route = None
            try:
                from litellm.proxy._types import UserAPIKeyAuth
                if isinstance(user_api_key_dict, UserAPIKeyAuth):
                    from litellm.proxy import proxy_server
                    from litellm.proxy.auth.user_api_key_auth import is_no_auth_dev_mode
                    from litellm.proxy.auth.auth_utils import route_in_additonal_public_routes
                    # Native dev mode also returns UserAPIKeyAuth for an anonymous
                    # request. Freeze mode eligibility now, before logging/config
                    # changes. Configured custom auth runs before that fallback.
                    # The native auth wrapper binds this from the ASGI scope.
                    # Snapshot URL paths are Host-derived and cannot authorize.
                    auth_route = getattr(user_api_key_dict, "request_route", None)
                    proxy_auth = type(auth_route) is str and auth_route in _COMPLETION_ROUTES | _RESPONSES_ROUTES and not (
                        route_in_additonal_public_routes(current_route=auth_route)
                    ) and (
                        (callable(getattr(proxy_server, "user_custom_auth", None))
                         and getattr(user_api_key_dict, "authenticated_by_custom_auth", False) is True)
                        or not is_no_auth_dev_mode(proxy_server.master_key, proxy_server.general_settings)
                    )
            except Exception:
                proxy_auth = False
            owner.add_dynamic_callback(_RequestSnapshot(owner, proxy_auth, auth_route))
        return None


handler = PricingSnapshot()
