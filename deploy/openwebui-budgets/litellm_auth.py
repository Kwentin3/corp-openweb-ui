"""Exact LiteLLM 1.105.1 adapter; mount beside config.yaml and configure
``general_settings.custom_auth: litellm_auth.gateway_auth``.

Boundary: OpenWebUI authenticates USER_ID and expands the native {{TASK}}
connection template into X-OpenWebUI-Task. The distinct server-held gateway
secret authenticates the transport; it does not prove task/chat provenance.
On the shared bearer, TASK must be present: empty TASK selects USER_ID's personal
assignment; nonempty TASK requires a separate signed service-call audience
binding the verified actor, native model, task and payer before assignment lookup.
Native virtual keys cannot authorize a nonempty TASK. Model-less discovery is
unsupported. OWUI_BUDGET_REQUIRE_PROVENANCE=true additionally requires signed
personal scope. The shared provenance module authenticates representation;
this adapter projects native log fields and consumes tokens before downstream reads.

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

from datetime import datetime, timezone
from functools import lru_cache
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
PROVENANCE_FIELD = "owui_budget_provenance"


@lru_cache(maxsize=4)
def _assignment_symbol(name: str):
    from litellm.proxy.types_utils.utils import get_instance_fn

    return get_instance_fn("employee_budget_assignment." + name, config_file_path=__file__)


def __getattr__(name: str):
    if name == "ASSIGNMENT_NAMESPACE":
        return _assignment_symbol(name)
    raise AttributeError(name)


def assignment_alias(user_id: str, model: str) -> str:
    """Compatibility shim; the shared assignment contract owns this representation."""
    return _assignment_symbol("assignment_alias")(user_id, model)


def assignment_metadata(model: str) -> dict[str, str]:
    return _assignment_symbol("assignment_metadata")(model)


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
    return _assignment_symbol("assignment_matches")(record, user_id, model)


def _provenance_required() -> bool:
    value = os.environ.get("OWUI_BUDGET_REQUIRE_PROVENANCE", "false").lower()
    _require(value in ("true", "false"), 503, "Invalid budget provenance configuration")
    return value == "true"


def _metadata_maps(data: dict) -> list[dict]:
    maps = []
    for name in ("metadata", "litellm_metadata"):
        value = data.get(name)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                _require(False, 403, "Invalid budget metadata")
            data[name] = value
        _require(value is None or isinstance(value, dict), 403, "Invalid budget metadata")
        if isinstance(value, dict):
            maps.append(value)
    return maps


def _apply_provenance(request: Request, data: dict, *, shared_gateway: bool,
                      required: bool, secret: str, user_id: str | None,
                      model: str | None, decoder, chain_id: str | None,
                      metadata_slot: str, metadata_session_id: str | None,
                      task: str = "") -> None:
    """Change log-only fields in place; native cached-body setter follows this.

    Both aliases are cleaned because native normalization merges them later.
    Native key/legacy calls never acquire our trusted namespace from client data.
    """
    maps = _metadata_maps(data)
    carrier = data.get("litellm_metadata")
    token = carrier.get(PROVENANCE_FIELD) if isinstance(carrier, dict) else None
    for value in [data, *maps]:
        value.pop(PROVENANCE_FIELD, None)
        value.pop("owui_budget_root", None)
        value.pop("owui_budget", None)
        context = value.get("chat_context")
        if isinstance(context, dict):
            context.pop("owui_budget_root", None)
        spend = value.get("spend_logs_metadata")
        _require(spend is None or isinstance(spend, dict), 403, "Invalid budget spend metadata")
        if isinstance(spend, dict):
            spend.pop("owui_budget", None)
            spend.pop(PROVENANCE_FIELD, None)
            spend.pop("owui_budget_root", None)

    header_metadata = _header(request, "x-litellm-spend-logs-metadata", required=False)
    if header_metadata is not None:
        try:
            header_value = json.loads(header_metadata)
        except ValueError:
            _require(False, 403, "Invalid budget metadata header")
        _require(not isinstance(header_value, dict) or not any(
            key in header_value for key in ("owui_budget", PROVENANCE_FIELD, "owui_budget_root")
        ), 403, "Client budget attribution header is forbidden")

    if not shared_gateway:
        _require(not task, 403, "Native virtual keys cannot authorize service tasks")
        return
    _require(not (required or task) or token is not None, 403, "Signed budget provenance required")
    if token is None:
        return
    try:
        scope_args = {"user_id": user_id, "model": model}
        if task:
            scope_args["task"] = task
        claims = decoder(token, secret, **scope_args)
    except ValueError:
        _require(False, 403, "Invalid signed budget provenance")
    # Header processing runs after custom_auth and would overwrite our fields.
    _require(header_metadata is None and chain_id is None
             and "traceparent" not in request.headers and "baggage" not in request.headers,
             403, "Competing budget correlation headers are forbidden")
    # Native normalization also derives session correlation from metadata.user_id
    # after auth, including on Responses' otherwise provider-owned metadata slot.
    session_id = "owui-service:" + claims["chat_id"] if task else claims["root_chat_id"]
    trace_id = claims["jti"] if task else claims["root_answer_id"]
    _require(metadata_session_id is None or metadata_session_id == session_id,
             403, "Competing budget metadata session is forbidden")
    if task:
        scope = {"schema": 1, "user_id": claims["payer_id"], "actor_id": claims["sub"],
                 "chat_id": claims["chat_id"], "call_id": claims["jti"],
                 "model": claims["model"], "category": "service", "task": claims["task"]}
    else:
        scope = {"schema": 1, "user_id": claims["sub"], "chat_id": claims["chat_id"],
                 "answer_id": claims["answer_id"], "root_chat_id": claims["root_chat_id"],
                 "root_answer_id": claims["root_answer_id"], "model": claims["model"],
                 "call_id": claims["jti"], "category": "personal"}
    # Only the native route-selected logging slot may acquire scope. Responses
    # keeps body.metadata as provider metadata, which must remain independent.
    _require(metadata_slot in ("metadata", "litellm_metadata"), 503,
             "Native budget metadata route is unavailable")
    value = data.setdefault(metadata_slot, {})
    if value is None:
        value = data[metadata_slot] = {}
    value["session_id"] = session_id
    value["trace_id"] = trace_id
    spend = value.get("spend_logs_metadata")
    if spend is None:
        spend = value["spend_logs_metadata"] = {}
    spend["owui_budget"] = scope
    data["litellm_session_id"] = session_id
    data["litellm_trace_id"] = trace_id


async def gateway_auth(request: Request, api_key: str) -> UserAPIKeyAuth:
    """Return stock validated identity before the outer native reservation gate."""
    # Lazy imports preserve the native config-file loader's initialization order.
    import litellm
    from litellm.proxy import proxy_server
    from litellm.proxy._types import LiteLLMRoutes
    from litellm.proxy.auth.auth_utils import get_model_from_request, get_request_route
    from litellm.proxy.auth.auth_checks import get_key_object
    from litellm.proxy.auth.resolvers.store import IdentityStore
    from litellm.proxy.auth.route_checks import RouteChecks
    from litellm.proxy.auth.user_api_key_auth import validate_resolved_virtual_key
    from litellm.proxy.common_utils.http_parsing_utils import _read_request_body, _safe_set_request_parsed_body
    from litellm.proxy.litellm_pre_call_utils import (
        _get_anthropic_session_id_from_metadata, get_chain_id_from_headers, metadata_variable_name_for_route,
    )
    from litellm.proxy.types_utils.utils import get_instance_fn
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
    request_data = await _read_request_body(request)
    shared_gateway = _same_secret(api_key, gateway_secret)
    _require(shared_gateway or not task, 403, "Native virtual keys cannot authorize service tasks")
    user_id = None
    actor_id = None
    model = None

    if shared_gateway:
        _header(request, TASK_HEADER, required=True)
        user_id = _header(request, USER_ID_HEADER, required=True)
        actor_id = user_id
        _require(bool(user_id), 403, "Authenticated OpenWebUI user identity required")
        _require(RouteChecks.is_llm_api_route(route), 403,
                 "Shared budget bearer only supports qualified model inference")
        model = get_model_from_request(
            request_data, route, request_headers=request.headers,
            request_query_params=request.query_params, llm_router=proxy_server.llm_router, request=request,
        )
        _require(isinstance(model, str) and bool(model), 403,
                 "Exactly one explicit native model is required for budget routing")
        _require(request_data.get("model") == model, 403,
                 "Exactly one explicit wire model is required for budget provenance")
        if task:
            _metadata_maps(request_data)
            carrier = request_data.get("litellm_metadata")
            token = carrier.get(PROVENANCE_FIELD) if isinstance(carrier, dict) else None
            try:
                claims = get_instance_fn("provenance.decode_service_call", config_file_path=__file__)(
                    token, gateway_secret, user_id=actor_id, model=model, task=task,
                )
            except ValueError:
                _require(False, 403, "Invalid signed budget provenance")
            user_id = claims["payer_id"]
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

    # Match the native string-to-object normalization before invoking its
    # session extractor; otherwise JSON-string metadata could evade this check.
    _metadata_maps(request_data)
    _apply_provenance(
        request, request_data, shared_gateway=shared_gateway,
        required=_provenance_required(), secret=gateway_secret, user_id=actor_id, model=model,
        # Keep unsigned legacy/native-key paths independent of this optional
        # mount. Strict shared calls fail closed before routing without a token.
        decoder=lambda token, secret, **scope: get_instance_fn(
            "provenance.decode_service_call" if task else "provenance.decode_call", config_file_path=__file__
        )(token, secret, **scope),
        chain_id=get_chain_id_from_headers(dict(request.headers)),
        metadata_slot=metadata_variable_name_for_route(route),
        metadata_session_id=_get_anthropic_session_id_from_metadata(request_data.get("metadata")),
        task=task or "",
    )
    _safe_set_request_parsed_body(request=request, parsed_body=request_data)

    if RouteChecks.is_llm_api_route(route):
        # Native writer-fresh identity observes committed key blocks/settings;
        # peer cache invalidation is best-effort. Validation/reservation remain
        # in their existing native owners below and in the outer auth wrapper.
        identity = await get_key_object(
            hashed_token=key_hash, prisma_client=proxy_server.prisma_client,
            user_api_key_cache=proxy_server.user_api_key_cache,
            parent_otel_span=getattr(request.state, "parent_otel_span", None),
            proxy_logging_obj=proxy_server.proxy_logging_obj, check_db_only=True,
        )
    else:
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
    if shared_gateway:
        _require(auth.user_id == user_id, 403, "Validated native payer does not match its assignment")
    return auth
