"""Exact LiteLLM 1.105.1 adapter; mount beside config.yaml and configure
``general_settings.custom_auth: litellm_auth.gateway_auth``.

Boundary: OpenWebUI authenticates USER_ID and expands the native {{TASK}}
connection template into X-OpenWebUI-Task. The distinct server-held gateway
secret authenticates the transport; it does not prove task/chat provenance.
Only USER_ID is used for personal-key selection. Empty TASK means ordinary
inference; missing or nonempty TASK is unsupported on that branch.
Model-less discovery and service-task classification are deliberately unresolved.

Assignment state belongs to existing native virtual keys: canonical
assignment_alias(user_id, model), assignment_metadata(model), models=[model],
user_id exact, team_id=None. Provision through native management APIs; duplicate
canonical aliases fail closed. No balances, tariffs, caps, or provider calls live
here. Native IdentityStore -> validate_resolved_virtual_key owns identity and key
policy; the outer native common-check gate owns the sole reservation lifecycle.

Other actual sk- virtual-key secrets use the same native validation. Operator
keys should carry native management/info allowed_routes. Bootstrap them before
enabling this hook. Stock master authentication requires restoring stock config;
this adapter never synthesizes an admin identity or falls back to the master.
The internal symbols below require actual-image qualification on every upgrade.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
import secrets
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from litellm.proxy._types import UserAPIKeyAuth


REQUIRED_VERSION = "1.105.1"
USER_ID_HEADER = "X-OpenWebUI-User-Id"
TASK_HEADER = "X-OpenWebUI-Task"
ASSIGNMENT_NAMESPACE = "user-model-v1"


def assignment_alias(user_id: str, model: str) -> str:
    """Canonical native key alias; this hash is an assignment ID, not a credential."""
    identity = json.dumps([user_id, model], ensure_ascii=True, separators=(",", ":"))
    return "owui-budget-v1-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def assignment_metadata(model: str) -> dict[str, str]:
    return {"owui_budget_namespace": ASSIGNMENT_NAMESPACE, "owui_budget_model": model}


def _require(condition: bool, status: int, detail: str) -> None:
    if not condition:
        raise HTTPException(status_code=status, detail=detail)


def _same_secret(left: str, right: str) -> bool:
    return secrets.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _header(request: Request, name: str, *, required: bool) -> str | None:
    values = request.headers.getlist(name)
    _require(len(values) <= 1 and (not required or len(values) == 1), 403,
             "Missing or ambiguous budget identity/task header")
    return values[0] if values else None


def _assignment_matches(record: object, user_id: str, model: str) -> bool:
    metadata = getattr(record, "metadata", None)
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except ValueError:
            return False
    return (
        getattr(record, "user_id", None) == user_id
        and getattr(record, "team_id", None) is None
        and getattr(record, "models", None) == [model]
        and getattr(record, "key_alias", None) == assignment_alias(user_id, model)
        and isinstance(metadata, Mapping)
        and all(metadata.get(key) == value for key, value in assignment_metadata(model).items())
    )


async def gateway_auth(request: Request, api_key: str) -> UserAPIKeyAuth:
    """Return stock validated identity before the outer native reservation gate."""
    # Lazy imports preserve the native config-file loader's initialization order.
    import litellm
    from litellm.proxy import proxy_server
    from litellm.proxy._types import LiteLLMRoutes
    from litellm.proxy.auth.auth_utils import get_model_from_request, get_request_route
    from litellm.proxy.auth.resolvers.store import IdentityStore
    from litellm.proxy.auth.route_checks import RouteChecks
    from litellm.proxy.auth.user_api_key_auth import validate_resolved_virtual_key
    from litellm.proxy.common_utils.http_parsing_utils import _read_request_body
    from litellm.proxy.db.exception_handler import PrismaDBExceptionHandler
    from litellm.proxy.utils import hash_token
    from litellm.repositories.verification_token_repository import VerificationTokenRepository

    settings = proxy_server.general_settings
    _require(version("litellm") == REQUIRED_VERSION and proxy_server.version == REQUIRED_VERSION,
             503, "Budget adapter requires exact LiteLLM 1.105.1")
    _require(settings.get("custom_auth_run_common_checks") is True,
             503, "Budget adapter requires native common checks")
    _require(not getattr(litellm, "enable_post_custom_auth_checks", False),
             503, "Budget adapter requires a single native validation phase")
    _require(settings.get("disable_budget_reservation") is not True
             and settings.get("fail_closed_budget_enforcement") is True
             and not PrismaDBExceptionHandler.should_allow_request_on_db_unavailable()
             and getattr(litellm, "block_requests_for_models_without_pricing", False) is True,
             503, "Budget adapter requires native fail-closed budget configuration")
    _require(proxy_server.prisma_client is not None, 503, "Budget adapter requires the native database")
    gateway_secret = os.environ.get("OWUI_BUDGET_GATEWAY_SECRET", "")
    master_key = proxy_server.master_key
    _require(bool(gateway_secret) and isinstance(master_key, str) and bool(master_key)
             and not _same_secret(gateway_secret, master_key),
             503, "A distinct budget gateway secret and control-plane master are required")
    _require(isinstance(api_key, str) and bool(api_key), 401, "Native virtual-key authentication required")

    route = get_request_route(request)
    # Reuse the authoritative native definition: custom_auth precedes this stock guard.
    _require(route not in LiteLLMRoutes.master_key_only_routes.value, 403,
             "Master-only routes are unavailable through the budget adapter")
    task = _header(request, TASK_HEADER, required=False)
    _require(task is None or task == "", 403, "Service tasks are not qualified for budget routing")
    request_data = await _read_request_body(request)
    shared_gateway = _same_secret(api_key, gateway_secret)
    user_id = None
    model = None

    if shared_gateway:
        _header(request, TASK_HEADER, required=True)
        user_id = _header(request, USER_ID_HEADER, required=True)
        _require(bool(user_id), 403, "Authenticated OpenWebUI user identity required")
        _require(RouteChecks.is_llm_api_route(route), 403,
                 "Shared budget bearer only supports qualified model inference")
        model = get_model_from_request(
            request_data, route, request_headers=request.headers,
            request_query_params=request.query_params, llm_router=proxy_server.llm_router, request=request,
        )
        _require(isinstance(model, str) and bool(model), 403,
                 "Exactly one explicit native model is required for budget routing")
        candidates = await VerificationTokenRepository(proxy_server.prisma_client).table.find_many(
            take=2, where={"user_id": user_id, "key_alias": assignment_alias(user_id, model)},
        )
        _require(len(candidates) == 1, 403, "Exactly one native user/model assignment is required")
        selected = candidates[0]
        _require(_assignment_matches(selected, user_id, model), 403, "Invalid native user/model assignment")
        key_hash = selected.token
    else:
        _require(not _same_secret(api_key, master_key), 403,
                 "Stock master authentication requires stock proxy configuration")
        _require(api_key.startswith("sk-") and len(api_key) > 3, 401,
                 "An actual native virtual-key secret is required")
        key_hash = hash_token(api_key)

    identity = IdentityStore.key_from_principal(
        await IdentityStore(
            proxy_server.prisma_client, proxy_server.user_api_key_cache,
            parent_otel_span=getattr(request.state, "parent_otel_span", None),
            proxy_logging_obj=proxy_server.proxy_logging_obj,
        ).resolve(hashed_token=key_hash)
    )
    if shared_gateway:
        _require(_assignment_matches(identity, user_id, model), 403,
                 "Resolved native identity does not match its user/model assignment")
    auth = await validate_resolved_virtual_key(
        request=request, request_data=request_data, valid_token=identity,
        api_key=key_hash, route=route,
        start_time=getattr(request.state, "litellm_received_at", None) or datetime.now(timezone.utc),
        parent_otel_span=getattr(request.state, "parent_otel_span", None),
        end_user_id=None, end_user_params={}, _end_user_object=None,
    )
    _require(auth.budget_reservation is None, 503, "Native validation unexpectedly reserved budget")
    return auth
