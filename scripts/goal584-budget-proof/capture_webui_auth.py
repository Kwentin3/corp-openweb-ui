"""Disposable observation at the documented custom-auth seam; no mutation.

Never install as product configuration. Only the fresh synthetic WebUI fixture
uses this delegate. Record meaningful model inputs without auth/metadata secrets;
leave native authentication and the outer reservation lifecycle unchanged.
"""

from functools import lru_cache
import json
import os
from pathlib import Path


CAPTURE = Path("/proof-private/webui-gateway-context.private.json")
FIELDS = (
    "model", "messages", "input", "tools", "tool_choice", "functions", "function_call",
    "response_format", "max_tokens", "max_completion_tokens", "max_output_tokens",
    "reasoning_effort", "reasoning", "stream", "temperature", "top_p", "n", "best_of",
)


@lru_cache(maxsize=1)
def product_auth():
    # Match the native config-relative loader; it does not add /proof to sys.path.
    from litellm.proxy.types_utils.utils import get_instance_fn

    return get_instance_fn("litellm_auth.gateway_auth", config_file_path=str(Path(__file__).with_name("config.yaml")))


async def gateway_auth(request, api_key):
    from litellm.proxy import proxy_server
    from litellm.proxy.auth.auth_utils import get_request_route
    from litellm.proxy.common_utils.http_parsing_utils import _read_request_body
    from litellm.proxy.spend_tracking.budget_reservation import estimate_request_max_cost

    body = await _read_request_body(request)
    route = get_request_route(request)
    if route in ("/chat/completions", "/v1/chat/completions") and body.get("model") in ("goal584-a", "goal584-b"):
        state = json.loads(CAPTURE.read_text(encoding="utf-8")) if CAPTURE.exists() else {"schema": 1, "requests": []}
        if len(state["requests"]) >= 16:
            raise RuntimeError("Disposable context observation bound exceeded")
        state["requests"].append({
            "user_id": request.headers.get("X-OpenWebUI-User-Id"),
            "task": request.headers.get("X-OpenWebUI-Task"),
            "body": {field: body[field] for field in FIELDS if field in body},
            "native_estimated_max_cost_usd": estimate_request_max_cost(body, route, proxy_server.llm_router),
        })
        descriptor = os.open(CAPTURE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, allow_nan=False)
            handle.write("\n")
    return await product_auth()(request, api_key)
