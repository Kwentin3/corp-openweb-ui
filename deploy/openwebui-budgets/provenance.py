"""Shared representation contract; native WebUI owns IDs, LiteLLM owns money.

Mount the same file as employee_budget_provenance.py in WebUI and beside the
LiteLLM config as provenance.py. No framework imports, environment reads or
mutable state. Tokens authenticate supplied scope; callers must obtain that
scope from the existing server owners. They are not replay/payment receipts.
"""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import jwt


ISSUER = "corp-openwebui-budget-v1"
CALL_AUDIENCE = "litellm-budget-call-v1"
SERVICE_AUDIENCE = "litellm-budget-service-call-v1"
ROOT_AUDIENCE = "openwebui-budget-root-v1"
CALL_TTL = 300
ROOT_TTL = 86400
_COMMON = {"schema", "iss", "aud", "sub", "jti", "iat", "exp"}
_ROOT_IDS = {"root_chat_id", "root_answer_id"}
_CALL_IDS = {"chat_id", "answer_id", *_ROOT_IDS}
_SERVICE_IDS = {"payer_id", "chat_id"}
SERVICE_TASKS = frozenset({"title_generation", "tags_generation", "follow_up_generation"})


class ProtocolError(ValueError):
    """Safe protocol failure; never includes a token, secret or supplied claim."""


def _check(condition: bool) -> None:
    if not condition:
        raise ProtocolError("Invalid budget provenance")


def _uuid(value: object) -> None:
    _check(isinstance(value, str))
    try:
        _check(str(UUID(value)) == value)
    except (ValueError, TypeError, AttributeError):
        raise ProtocolError("Invalid budget provenance") from None


def _secret(secret: str) -> None:
    _check(isinstance(secret, str) and bool(secret))


def _model(model: object) -> None:
    _check(isinstance(model, str) and 0 < len(model) <= 256
           and model == model.strip() and all(ord(char) >= 32 for char in model))


def _validate(claims: dict, audience: str, limit: int) -> None:
    if audience == SERVICE_AUDIENCE:
        ids, fields = _SERVICE_IDS, {"model", "task"}
    else:
        _check(audience in (CALL_AUDIENCE, ROOT_AUDIENCE))
        ids = _CALL_IDS if audience == CALL_AUDIENCE else _ROOT_IDS
        fields = {"model"} if audience == CALL_AUDIENCE else set()
    expected = _COMMON | ids | fields
    _check(set(claims) == expected)
    _check(type(claims["schema"]) is int and claims["schema"] == 1)
    _check(claims["iss"] == ISSUER and claims["aud"] == audience)
    for field in {"sub", "jti", *ids}:
        _uuid(claims[field])
    _check(type(claims["iat"]) is int and type(claims["exp"]) is int)
    _check(0 <= claims["iat"] < claims["exp"] <= claims["iat"] + limit)
    if audience in (CALL_AUDIENCE, SERVICE_AUDIENCE):
        _model(claims["model"])
    if audience == SERVICE_AUDIENCE:
        _check(type(claims["task"]) is str and claims["task"] in SERVICE_TASKS
               and claims["sub"] != claims["payer_id"])


def validate_persisted_scope(scope: object) -> dict:
    """Validate the log-only representation; this does not authenticate its origin."""
    ids = {"user_id", "chat_id", "answer_id", "root_chat_id", "root_answer_id", "call_id"}
    _check(isinstance(scope, dict) and set(scope) == ids | {"schema", "model", "category"})
    _check(type(scope["schema"]) is int and scope["schema"] == 1 and scope["category"] == "personal")
    for name in ids:
        _uuid(scope[name])
    _model(scope["model"])
    return scope.copy()


def validate_persisted_service_scope(scope: object) -> dict:
    """Separate service event representation; never invent an answer/root ID."""
    ids = {"user_id", "actor_id", "chat_id", "call_id"}
    _check(isinstance(scope, dict) and set(scope) == ids | {"schema", "model", "category", "task"})
    _check(type(scope["schema"]) is int and scope["schema"] == 1 and scope["category"] == "service"
           and type(scope["task"]) is str and scope["task"] in SERVICE_TASKS)
    for name in ids:
        _uuid(scope[name])
    _check(scope["user_id"] != scope["actor_id"])
    _model(scope["model"])
    return scope.copy()


def validate_persisted_rag_scope(scope: object) -> dict:
    """Validate only the key-owned log tag; native row identity proves origin.

    RAG has no Chat or claimed actor. Consumers must bind the actual native
    payer, canonical key hash and model from the persisted row separately.
    """
    _check(isinstance(scope, dict) and set(scope) == {"schema", "category", "operation"})
    _check(type(scope["schema"]) is int and scope["schema"] == 1
           and type(scope["category"]) is str and scope["category"] == "service"
           and type(scope["operation"]) is str and scope["operation"] == "rag_embedding")
    return scope.copy()


def _encode(secret: str, *, audience: str, limit: int, user_id: str,
            scope: dict, ttl_seconds: int, now: int | None) -> str:
    _secret(secret)
    _check(type(ttl_seconds) is int and 1 <= ttl_seconds <= limit)
    issued = int(time.time()) if now is None else now
    _check(type(issued) is int)
    claims = {"schema": 1, "iss": ISSUER, "aud": audience, "sub": user_id,
              "jti": str(uuid4()), "iat": issued, "exp": issued + ttl_seconds, **scope}
    _validate(claims, audience, limit)
    return jwt.encode(claims, secret, algorithm="HS256")


def _decode(token: str, secret: str, audience: str, limit: int) -> dict:
    _secret(secret)
    _check(isinstance(token, str) and 0 < len(token) <= 4096)
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], issuer=ISSUER,
                            audience=audience, options={"require": sorted(_COMMON),
                                                       "strict_aud": True})
        _validate(claims, audience, limit)
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise ProtocolError("Invalid budget provenance") from None


def encode_call(secret: str, *, user_id: str, chat_id: str, answer_id: str,
                root_chat_id: str, root_answer_id: str, model: str,
                now: int | None = None, ttl_seconds: int = CALL_TTL) -> str:
    return _encode(secret, audience=CALL_AUDIENCE, limit=CALL_TTL, user_id=user_id,
                   scope={"chat_id": chat_id, "answer_id": answer_id,
                          "root_chat_id": root_chat_id, "root_answer_id": root_answer_id,
                          "model": model}, ttl_seconds=ttl_seconds, now=now)


def decode_call(token: str, secret: str, *, user_id: str, model: str) -> dict:
    claims = _decode(token, secret, CALL_AUDIENCE, CALL_TTL)
    _check(claims["sub"] == user_id and claims["model"] == model)
    return claims


def encode_service_call(secret: str, *, user_id: str, payer_id: str, chat_id: str,
                        model: str, task: str, now: int | None = None,
                        ttl_seconds: int = CALL_TTL) -> str:
    return _encode(secret, audience=SERVICE_AUDIENCE, limit=CALL_TTL, user_id=user_id,
                   scope={"payer_id": payer_id, "chat_id": chat_id, "model": model, "task": task},
                   ttl_seconds=ttl_seconds, now=now)


def decode_service_call(token: str, secret: str, *, user_id: str, model: str, task: str) -> dict:
    claims = _decode(token, secret, SERVICE_AUDIENCE, CALL_TTL)
    _check(claims["sub"] == user_id and claims["model"] == model and claims["task"] == task)
    return claims


def encode_root(secret: str, *, user_id: str, root_chat_id: str,
                root_answer_id: str, now: int | None = None,
                ttl_seconds: int = ROOT_TTL) -> str:
    return _encode(secret, audience=ROOT_AUDIENCE, limit=ROOT_TTL, user_id=user_id,
                   scope={"root_chat_id": root_chat_id, "root_answer_id": root_answer_id},
                   ttl_seconds=ttl_seconds, now=now)


def decode_root(token: str, secret: str) -> dict:
    return _decode(token, secret, ROOT_AUDIENCE, ROOT_TTL)
