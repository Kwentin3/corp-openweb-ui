"""Disposable observation at the documented custom-auth seam; no mutation.

Never install as product configuration. Only the fresh synthetic WebUI fixture
uses this delegate. Record meaningful model inputs without auth/provenance secrets;
leave native authentication and the outer reservation lifecycle unchanged.
"""

from functools import lru_cache
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import re
from uuid import UUID, uuid4


CAPTURE = Path("/proof-private/webui-gateway-context.private.json")
MAX_RECORDS = 32
MAX_BYTES = 4 * 1024 * 1024
FIELDS = (
    "model", "messages", "input", "tools", "tool_choice", "functions", "function_call",
    "response_format", "max_tokens", "max_completion_tokens", "max_output_tokens",
    "reasoning_effort", "reasoning", "stream", "stream_options", "temperature", "top_p", "n", "best_of",
    "stop", "seed", "frequency_penalty", "presence_penalty", "parallel_tool_calls", "verbosity",
)
EMBEDDING_FIELDS = ("model", "input", "dimensions", "encoding_format", "user")
RESPONSES_FIELDS = (
    "model", "input", "instructions", "max_output_tokens", "stream", "tools", "tool_choice",
    "parallel_tool_calls", "reasoning", "include", "store", "metadata", "temperature", "top_p", "text",
    "truncation", "user", "previous_response_id", "background",
)
# These belong to native logging/provenance, not the provider model context.
RESPONSES_LOG_FIELDS = frozenset({"litellm_metadata", "litellm_session_id", "litellm_trace_id"})
# Exact aliases in the Office fixture config owners; this disposable observer
# is mounted only on the synthetic stand, never as product authentication.
OFFICE_MODELS = frozenset({"gpt-5.4-mini", "gpt-6-luna", "gpt-6.1-sol", "gpt-6.1-terra"})
CREDENTIAL = re.compile(r"(?:sk-|gw-)[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def responses_route(route):
    return route in ("/responses", "/v1/responses", "/openai/v1/responses")


def responses_projection(body):
    """Copy the complete supported wire context; never silently drop a field.

    The product owner consumes the signed token from litellm_metadata. It is
    excluded here as in the existing observer; a JWT in actual model context
    cannot be both faithfully recorded and kept private, so reject the capture.
    This is observation safety/completeness, not provider input validation.
    """
    if set(body) - set(RESPONSES_FIELDS) - RESPONSES_LOG_FIELDS:
        raise RuntimeError("Unsupported disposable Responses context field")
    value = copy.deepcopy({field: body[field] for field in RESPONSES_FIELDS if field in body})
    raw = json.dumps(value, allow_nan=False)
    if len(raw.encode("utf-8")) > MAX_BYTES:
        raise RuntimeError("Disposable context observation byte bound exceeded")
    if CREDENTIAL.search(raw) or re.search(r'"owui_budget_provenance"\s*:', raw):
        raise RuntimeError("Unsafe disposable Responses model context")
    return value


def embedding_route(route):
    return route in ("/embeddings", "/v1/embeddings") or re.fullmatch(
        r"/(?:engines|openai/deployments)/.+/embeddings", route) is not None


@lru_cache(maxsize=1)
def product_auth():
    # Match the native config-relative loader; it does not add /proof to sys.path.
    from litellm.proxy.types_utils.utils import get_instance_fn

    return get_instance_fn("litellm_auth.gateway_auth", config_file_path=str(Path(__file__).with_name("config.yaml")))


@lru_cache(maxsize=1)
def product_denial_reader():
    # Native config-relative loading creates a module per symbol. Use the exact
    # callback's defining module so its private request marker stays identical.
    return product_auth().__globals__["personal_key_budget_denial"]


@lru_cache(maxsize=3)
def scope_validator(category="personal"):
    from litellm.proxy.types_utils.utils import get_instance_fn

    names = {"personal": "validate_persisted_scope", "service": "validate_persisted_service_scope",
             "rag": "validate_persisted_rag_scope"}
    if category not in names:
        raise RuntimeError("Unknown disposable budget observation category")
    return get_instance_fn("provenance." + names[category], config_file_path=str(Path(__file__).with_name("config.yaml")))


@contextmanager
def capture_lock():
    """Short cross-process file lock; callers do no awaited/native work here."""
    descriptor = os.open(CAPTURE.with_name(CAPTURE.name + ".lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        if os.name == "nt":
            import msvcrt
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _validate(state):
    if (not isinstance(state, dict) or type(state.get("schema")) is not int or state["schema"] != 1
            or not isinstance(state.get("requests"), list) or len(state["requests"]) > MAX_RECORDS
            or not all(isinstance(record, dict) for record in state["requests"])):
        raise RuntimeError("Invalid disposable context observation")


def _read_locked():
    if not CAPTURE.exists():
        return {"schema": 1, "requests": []}
    with CAPTURE.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RuntimeError("Disposable context observation byte bound exceeded")
    try:
        state = json.loads(raw)
    except (ValueError, UnicodeError):
        raise RuntimeError("Invalid disposable context observation") from None
    _validate(state)
    return state


def _write_locked(state):
    _validate(state)
    raw = (json.dumps(state, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise RuntimeError("Disposable context observation byte bound exceeded")
    descriptor = os.open(CAPTURE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        if hasattr(os, "fchmod"):
            os.fchmod(handle.fileno(), 0o600)
        handle.write(raw)


def save(state):
    """Existing phase-reset interface; reset only after in-flight tasks settle."""
    with capture_lock():
        _write_locked(state)


def _append(record):
    record["_observation_id"] = uuid4().hex  # Private producer ID, never caller metadata.
    with capture_lock():
        state = _read_locked()
        if len(state["requests"]) >= MAX_RECORDS:
            raise RuntimeError("Disposable context observation bound exceeded")
        if any(row.get("_observation_id") == record["_observation_id"] for row in state["requests"]):
            raise RuntimeError("Duplicate disposable observation identity")
        state["requests"].append(record)
        _write_locked(state)


def _finish(record):
    with capture_lock():
        state = _read_locked()
        matches = [row for row in state["requests"] if row.get("_observation_id") == record["_observation_id"]]
        if len(matches) != 1:
            raise RuntimeError("Disposable observation identity missing or ambiguous")
        matches[0].update(record)
        _write_locked(state)


async def gateway_auth(request, api_key):
    from litellm.proxy import proxy_server
    from litellm.proxy.auth.auth_utils import get_request_route
    from litellm.proxy.common_utils.http_parsing_utils import _read_request_body
    from litellm.proxy.spend_tracking.budget_reservation import estimate_request_max_cost

    body = await _read_request_body(request)
    route = get_request_route(request)
    record = None
    embedding = embedding_route(route) and body.get("model") == "goal584-e"
    office = responses_route(route) and body.get("model") in OFFICE_MODELS
    responses = responses_route(route) and (body.get("model") == "goal584-r" or office)
    fields = EMBEDDING_FIELDS if embedding else FIELDS
    if embedding or responses or route in ("/chat/completions", "/v1/chat/completions") and body.get("model") in ("goal584-a", "goal584-b"):
        record = {
            "body": responses_projection(body) if responses else copy.deepcopy({field: body[field] for field in fields if field in body}),
            "native_estimated_max_cost_usd": estimate_request_max_cost(body, route, proxy_server.llm_router),
        }
        if embedding or responses:
            record["route"] = route
            if responses:
                record["attestation_present_before"] = bool((body.get("litellm_metadata") or {}).get("owui_budget_provenance"))
        else:
            record.update(user_id=request.headers.get("X-OpenWebUI-User-Id"),
                task=request.headers.get("X-OpenWebUI-Task"),
                attestation_present_before=bool((body.get("litellm_metadata") or {}).get("owui_budget_provenance")))
        _append(record)
    auth = None
    auth_failed = False
    try:
        auth = await product_auth()(request, api_key)
        return auth
    except BaseException as error:
        auth_failed = True
        if record is not None:
            status = getattr(error, "status_code", None)
            status = status if type(status) is int and 400 <= status <= 599 else None
            known = status == 403 and getattr(error, "detail", None) == "Invalid signed budget provenance"
            record["auth_failure"] = {"scope": "custom_auth", "status_code": status,
                                      "code": "invalid_signed_budget_provenance" if known else "unclassified"}
            if responses:
                try:
                    denial = product_denial_reader()(request, error)
                except Exception:
                    denial = None  # Optional observation cannot replace rejection.
                if denial is not None:
                    record['native_budget_denial'] = denial
        raise
    finally:
        try:
            if record is not None:
                after = await _read_request_body(request)
                maps = [value for key in ("metadata", "litellm_metadata")
                        if isinstance((value := after.get(key)), dict)]
                scopes = [value["spend_logs_metadata"].get("owui_budget") for value in maps
                          if isinstance(value.get("spend_logs_metadata"), dict)]
                scopes = [value for value in scopes if value is not None]
                record["provenance_removed_after"] = all("owui_budget_provenance" not in value for value in maps)
                if responses:
                    try:
                        record["body_after_auth"] = responses_projection(after)
                    except (RuntimeError, ValueError, UnicodeError):
                        record["responses_projection_rejected_after_auth"] = True
                        if "auth_failure" not in record:
                            _finish(record)
                            raise
                        # Keep the original product rejection, while explicitly
                        # marking that no complete safe after-context was exported.
                else:
                    record["body_after_auth"] = copy.deepcopy({field: after[field] for field in fields if field in after})
                if auth is not None and (embedding or responses):
                    payer, key_hash = getattr(auth, "user_id", None), getattr(auth, "api_key", None)
                    try:
                        if isinstance(payer, str) and str(UUID(payer)) == payer:
                            record["native_auth_user_id"] = payer
                    except ValueError:
                        pass
                    if isinstance(key_hash, str) and re.fullmatch(r"[0-9a-f]{64}", key_hash):
                        record["native_auth_key_hash"] = key_hash
                    if embedding and scopes:
                        # Key-owned log metadata and native Logging/call-ID setup
                        # occur after custom_auth; syntax is not origin evidence.
                        parsed = [scope_validator("rag")(scope) for scope in scopes]
                        if any(scope != parsed[0] for scope in parsed):
                            raise RuntimeError("Conflicting disposable RAG scope observations")
                        record["unverified_rag_scope"] = parsed[0]
                elif auth is not None:
                    record["native_auth_user_id"] = auth.user_id
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
                # A rejected forged task may leave caller metadata untouched before
                # the product projection runs. Do not label that input as verified.
                if responses and auth is not None and record["attestation_present_before"] and record["provenance_removed_after"]:
                    # Responses metadata is provider-owned. Only the product's
                    # route-selected litellm_metadata slot can supply signed scope.
                    carrier = after.get("litellm_metadata")
                    scope = (carrier.get("spend_logs_metadata") or {}).get("owui_budget") if isinstance(carrier, dict) else None
                    if scope is not None:
                        scope = scope_validator(scope.get("category"))(scope)
                        if (scope.get("user_id") != record.get("native_auth_user_id")
                                or scope.get("model") != after.get("model") or "native_auth_key_hash" not in record):
                            raise RuntimeError("Conflicting disposable Responses scope identity")
                        record["verified_cost_scope"] = scope
                elif not embedding and not responses and scopes and record["attestation_present_before"] and record["provenance_removed_after"]:
                    record["verified_cost_scope"] = scope_validator(scopes[0].get("category"))(scopes[0])
                if office and not auth_failed and "verified_cost_scope" not in record:
                    _finish(record)
                    raise RuntimeError("Incomplete disposable Office scope observation")
                _finish(record)
        except BaseException:
            # Observation must never replace an existing product rejection.
            # After successful auth, an incomplete observation is a hard failure.
            if not auth_failed:
                raise
