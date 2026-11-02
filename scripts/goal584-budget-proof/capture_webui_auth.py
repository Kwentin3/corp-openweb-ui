"""Disposable observation at the documented custom-auth seam; no mutation.

Never install as product configuration. Only the fresh synthetic WebUI fixture
uses this delegate. Record meaningful model inputs without auth/metadata secrets;
leave native authentication and the outer reservation lifecycle unchanged.
"""

from functools import lru_cache
import copy
import json
import os
from pathlib import Path


CAPTURE = Path("/proof-private/webui-gateway-context.private.json")
FIELDS = (
    "model", "messages", "input", "tools", "tool_choice", "functions", "function_call",
    "response_format", "max_tokens", "max_completion_tokens", "max_output_tokens",
    "reasoning_effort", "reasoning", "stream", "stream_options", "temperature", "top_p", "n", "best_of",
    "stop", "seed", "frequency_penalty", "presence_penalty", "parallel_tool_calls", "verbosity",
)


@lru_cache(maxsize=1)
def product_auth():
    # Match the native config-relative loader; it does not add /proof to sys.path.
    from litellm.proxy.types_utils.utils import get_instance_fn

    return get_instance_fn("litellm_auth.gateway_auth", config_file_path=str(Path(__file__).with_name("config.yaml")))


@lru_cache(maxsize=1)
def scope_validator():
    from litellm.proxy.types_utils.utils import get_instance_fn

    return get_instance_fn("provenance.validate_persisted_scope", config_file_path=str(Path(__file__).with_name("config.yaml")))


def save(state):
    descriptor = os.open(CAPTURE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(state, handle, allow_nan=False)
        handle.write("\n")


async def gateway_auth(request, api_key):
    from litellm.proxy import proxy_server
    from litellm.proxy.auth.auth_utils import get_request_route
    from litellm.proxy.common_utils.http_parsing_utils import _read_request_body
    from litellm.proxy.spend_tracking.budget_reservation import estimate_request_max_cost

    body = await _read_request_body(request)
    route = get_request_route(request)
    record = None
    if route in ("/chat/completions", "/v1/chat/completions") and body.get("model") in ("goal584-a", "goal584-b"):
        state = json.loads(CAPTURE.read_text(encoding="utf-8")) if CAPTURE.exists() else {"schema": 1, "requests": []}
        if len(state["requests"]) >= 32:
            raise RuntimeError("Disposable context observation bound exceeded")
        record = {
            "user_id": request.headers.get("X-OpenWebUI-User-Id"),
            "task": request.headers.get("X-OpenWebUI-Task"),
            "body": copy.deepcopy({field: body[field] for field in FIELDS if field in body}),
            "native_estimated_max_cost_usd": estimate_request_max_cost(body, route, proxy_server.llm_router),
            "attestation_present_before": bool((body.get("litellm_metadata") or {}).get("owui_budget_provenance")),
        }
        state["requests"].append(record)
        save(state)
    auth = None
    try:
        auth = await product_auth()(request, api_key)
        return auth
    finally:
        if record is not None:
            after = await _read_request_body(request)
            maps = [value for key in ("metadata", "litellm_metadata")
                    if isinstance((value := after.get(key)), dict)]
            scopes = [(value.get("spend_logs_metadata") or {}).get("owui_budget") for value in maps]
            scopes = [value for value in scopes if value is not None]
            record["provenance_removed_after"] = all("owui_budget_provenance" not in value for value in maps)
            record["body_after_auth"] = copy.deepcopy({field: after[field] for field in FIELDS if field in after})
            if auth is not None:
                # Native preprocessing (after auth) asks supported streaming
                # providers for usage. Record the exact owner's pure patch;
                # do not equate this transport normalization with auth changes.
                from litellm.proxy.common_request_processing import (
                    _model_deployments_support_stream_options, _stream_usage_tracking_updates,
                )
                record["native_stream_usage_patch"] = dict(_stream_usage_tracking_updates(
                    data=after, general_settings=proxy_server.general_settings,
                    route_type="acompletion",
                    supports_stream_options=lambda: _model_deployments_support_stream_options(
                        model=after.get("model"), llm_router=proxy_server.llm_router,
                        team_id=auth.team_id),
                ))
            if scopes:
                record["verified_cost_scope"] = scope_validator()(scopes[0])
            save(state)
