"""Bounded LiteLLM 1.105.1 public management API adapter.

Native user/key state -> public APIs -> server-only DTO -> caller policy/UI.
The caller owns WebUI role/directory/model checks and mutation confirmation.
Explicit initialization requires absence and a caller guard before every POST;
this client never retries, repairs, allocates, resets or stores spend.
Mount the shared modules under their employee_budget_* import names in WebUI.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, DecimalException
import hashlib
import hmac
import json
import math
import re
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import UUID

from aiohttp import ClientError, ClientSession, ClientTimeout

from employee_budget_assignment import ASSIGNMENT_NAMESPACE, assignment_alias, assignment_matches, assignment_metadata
from employee_budget_admin_contract import BudgetAdminError, EmployeeBudget, EmployeeBudgetInspection, ModelBudget


PAGE_SIZE = 100
MAX_PAGES = 100
MAX_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT = 10.0
READ_TIMEOUT = 20.0

# Only explicit native data validation failures become observations. HTTP,
# transport, response bounds and incomplete enumeration remain raised errors.
INSPECTION_CONFLICTS = frozenset({
    "invalid_employee", "invalid_native_response", "invalid_native_amount", "invalid_key_hash",
    "foreign_assignment", "duplicate_key", "invalid_assignment", "unsupported_assignment",
    "duplicate_assignment",
})


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BudgetAdminError(code)


def _user_id(value: object) -> str:
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    _require(valid, "invalid_user_id")
    return value


def _text(value: object) -> str:
    _require(isinstance(value, str) and 0 < len(value) <= 512 and value == value.strip()
             and all(ord(char) >= 32 for char in value), "invalid_native_response")
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)


def _money(value: object) -> Decimal:
    _require(type(value) in (str, int, float, Decimal) and len(str(value)) <= 128, "invalid_native_amount")
    try:
        result = Decimal(str(value))
    except DecimalException:
        raise BudgetAdminError("invalid_native_amount") from None
    _require(result.is_finite() and result >= 0, "invalid_native_amount")
    return result


def _cap(value: object) -> Decimal | None:
    return None if value is None else _money(value)


def _key_hash(value: object) -> str:
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             "invalid_key_hash")
    return value


def _wire_cap(value: Decimal) -> float:
    _require(isinstance(value, Decimal) and value.is_finite() and value >= 0, "invalid_cap")
    result = float(value)
    _require(math.isfinite(result) and (value == 0 or result > 0), "cap_not_representable")
    return result


def _models(models: tuple[str, ...]) -> tuple[str, ...]:
    _require(isinstance(models, tuple) and 0 < len(models) <= 100, "invalid_models")
    _require(all(isinstance(model, str) and 0 < len(model) <= 256 and model == model.strip()
                 and all(ord(char) >= 32 for char in model) for model in models), "invalid_models")
    _require(len(set(models)) == len(models), "invalid_models")
    return models


def _employee_user(payload: dict, user_id: str) -> dict:
    user = payload.get("user_info")
    _require(isinstance(user, dict) and user.get("user_id") == user_id
             and user.get("user_role") == "internal_user", "invalid_employee")
    _require({"max_budget", "spend", "budget_duration", "budget_reset_at"} <= user.keys(),
             "invalid_native_response")
    return user


def _employee_budget(user: dict, user_id: str, models: tuple[ModelBudget, ...]) -> EmployeeBudget:
    return EmployeeBudget(user_id, _cap(user.get("max_budget")), _money(user.get("spend")),
                          _optional_text(user.get("budget_duration")), _optional_text(user.get("budget_reset_at")),
                          models)


def _initial_cap(value: Decimal) -> float:
    result = _wire_cap(value)
    _require(Decimal(str(result)) == value, "unsupported_amount_precision")
    return result


def _initialization_key(user_id: str, model: str, gateway_secret: str) -> str:
    identity = json.dumps([user_id, model], ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return "sk-" + hmac.new(gateway_secret.encode("utf-8"),
                            b"employee-budget-bootstrap-key-v1\0" + identity, hashlib.sha256).hexdigest()


def _reset_time(value: str | None) -> datetime:
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else None
        valid = result is not None and result.tzinfo is not None and result > datetime.now(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        valid = False
    _require(valid, "initialization_unconfirmed")
    return result


def _initial_user(payload: dict, user_id: str, models: tuple[str, ...], cap: Decimal) -> EmployeeBudget:
    user = _employee_user(payload, user_id)
    budget = _employee_budget(user, user_id, ())
    actual_models = user.get("models")
    _require(isinstance(actual_models, list) and all(isinstance(model, str) for model in actual_models)
             and len(actual_models) == len(models) and set(actual_models) == set(models)
             and user.get("teams") == [] and "team_id" in user and user["team_id"] is None
             and payload.get("teams") == [] and budget.max_budget == cap and budget.spend == 0
             and budget.budget_duration == "1mo", "initialization_unconfirmed")
    _reset_time(budget.budget_reset_at)
    return budget


def _initial_models(selected: dict[str, ModelBudget], count: int, expected: dict[str, tuple[str, Decimal]],
                    reset_at: str) -> None:
    _require(set(selected) == set(expected) and count == len(expected), "initialization_unconfirmed")
    reset = _reset_time(reset_at)
    for model, (key_hash, cap) in expected.items():
        entry = selected[model]
        _require(entry.key_hash == key_hash and entry.max_budget == cap and entry.spend == 0
                 and entry.budget_duration == "1mo" and entry.blocked is False
                 and _reset_time(entry.budget_reset_at) == reset, "initialization_unconfirmed")


class BudgetAdminClient:
    def __init__(self, session: ClientSession, base_url: str, key: str):
        _require(isinstance(base_url, str), "invalid_configuration")
        try:
            parsed = urlsplit(base_url)
            valid = (parsed.scheme in ("http", "https") and bool(parsed.hostname)
                     and parsed.username is None and parsed.password is None
                     and not parsed.query and not parsed.fragment)
            parsed.port  # Reject malformed ports before a request.
        except (ValueError, TypeError):
            valid = False
        _require(valid, "invalid_configuration")
        _require(isinstance(key, str) and key.startswith("sk-")
                 and len(key) > 3 and not any(char.isspace() for char in key),
                 "invalid_configuration")
        self._session, self._base, self._key = session, base_url.rstrip("/"), key

    async def _request(self, method: str, route: str, *, params=None, body=None) -> dict:
        try:
            async with self._session.request(method, self._base + route, params=params, json=body,
                                            headers={"Authorization": "Bearer " + self._key},
                                            allow_redirects=False,
                                            timeout=ClientTimeout(total=REQUEST_TIMEOUT)) as response:
                _require(response.status == 200, "native_http_" + str(response.status))
                raw = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    raw.extend(chunk)
                    _require(len(raw) <= MAX_BYTES, "native_response_too_large")
                payload = json.loads(raw, parse_float=Decimal)
                _require(isinstance(payload, dict), "invalid_native_response")
                return payload
        except BudgetAdminError:
            raise
        except (ClientError, asyncio.TimeoutError, ValueError, UnicodeError, DecimalException):
            raise BudgetAdminError("native_transport") from None

    async def read_employee(self, user_id: str, models: tuple[str, ...]) -> EmployeeBudget:
        user_id, models = _user_id(user_id), _models(models)
        try:
            async with asyncio.timeout(READ_TIMEOUT):
                return await self._read_employee(user_id, models)
        except asyncio.TimeoutError:
            raise BudgetAdminError("native_transport") from None

    async def _read_employee(self, user_id: str, models: tuple[str, ...]) -> EmployeeBudget:
        payload = await self._request("GET", "/user/info", params={"user_id": user_id})
        user = _employee_user(payload, user_id)
        selected, _ = await self._read_assignments(user_id, models)
        _require(set(selected) == set(models), "missing_assignment")
        return _employee_budget(user, user_id, tuple(selected[model] for model in models))

    async def inspect_employee(self, user_id: str, models: tuple[str, ...]) -> EmployeeBudgetInspection:
        """Distinguish absence from ready/incomplete/conflicting native state.

        Unavailable reads raise BudgetAdminError; no observation substitutes
        defaults, authorizes mutation, retries or repairs the native objects.
        """
        user_id, models = _user_id(user_id), _models(models)
        try:
            async with asyncio.timeout(READ_TIMEOUT):
                return await self._inspect_employee(user_id, models)
        except asyncio.TimeoutError:
            raise BudgetAdminError("native_transport") from None
        except BudgetAdminError as error:
            if error.code not in INSPECTION_CONFLICTS:
                raise
            return EmployeeBudgetInspection(user_id, models, "conflict", code=error.code)

    async def _inspect_employee(self, user_id: str, models: tuple[str, ...]) -> EmployeeBudgetInspection:
        try:
            payload = await self._request("GET", "/user/info", params={"user_id": user_id})
        except BudgetAdminError as error:
            if error.code != "native_http_404":
                raise
            _, count = await self._read_assignments(user_id, models)
            if count:
                return EmployeeBudgetInspection(user_id, models, "conflict", code="orphan_assignments")
            return EmployeeBudgetInspection(user_id, models, "absent", code="missing_native_user")
        user = _employee_user(payload, user_id)
        # Validate all user scalar fields even when assignments are missing.
        budget = _employee_budget(user, user_id, ())
        selected, _ = await self._read_assignments(user_id, models)
        if set(selected) != set(models):
            return EmployeeBudgetInspection(user_id, models, "incomplete", code="missing_assignment")
        budget = replace(budget, models=tuple(selected[model] for model in models))
        return EmployeeBudgetInspection(user_id, models, "ready", employee_budget=budget)

    async def _read_assignments(self, user_id: str, models: tuple[str, ...], *,
                                initializing: bool = False) -> tuple[dict[str, ModelBudget], int]:
        aliases = {assignment_alias(user_id, model): model for model in models}
        selected: dict[str, ModelBudget] = {}
        seen: set[str] = set()
        counts = None
        page = 1
        while True:
            payload = await self._request("GET", "/key/list", params={
                "user_id": user_id, "page": page, "size": PAGE_SIZE,
                "return_full_object": "true", "substring_matching": "false",
                "include_team_keys": "false", "include_created_by_keys": "false",
            })
            total, pages, current = payload.get("total_count"), payload.get("total_pages"), payload.get("current_page")
            _require(type(total) is int and 0 <= total <= MAX_PAGES * PAGE_SIZE
                     and type(pages) is int and pages == (total + PAGE_SIZE - 1) // PAGE_SIZE
                     and type(current) is int and current == page, "incomplete_pagination")
            _require(counts is None or counts == (total, pages), "incomplete_pagination")
            counts = (total, pages)
            rows = payload.get("keys")
            _require(isinstance(rows, list) and len(rows) == min(PAGE_SIZE, max(0, total-(page-1)*PAGE_SIZE)),
                     "incomplete_pagination")
            for row in rows:
                _require(isinstance(row, dict) and row.get("user_id") == user_id, "foreign_assignment")
                key_hash = _key_hash(row.get("token"))
                _require(key_hash not in seen, "duplicate_key")
                seen.add(key_hash)
                metadata = row.get("metadata")
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except ValueError:
                        raise BudgetAdminError("invalid_assignment") from None
                _require(metadata is None or isinstance(metadata, dict), "invalid_assignment")
                alias = row.get("key_alias")
                _require(alias is None or isinstance(alias, str), "invalid_assignment")
                model = aliases.get(alias)
                namespace = (metadata or {}).get("owui_budget_namespace")
                if initializing:
                    _require(model is not None and {"expires", "budget_id", "allowed_routes"} <= row.keys()
                             and row["expires"] is None and row["budget_id"] is None
                             and row["allowed_routes"] == ["llm_api_routes"], "initialization_unconfirmed")
                if model is None and namespace != ASSIGNMENT_NAMESPACE:
                    continue  # Other native application keys are not our assignment catalog.
                _require(model is not None, "unsupported_assignment")
                record = SimpleNamespace(user_id=row.get("user_id"), team_id=row.get("team_id"),
                                         models=row.get("models"), key_alias=row.get("key_alias"), metadata=metadata)
                _require(assignment_matches(record, user_id, model), "invalid_assignment")
                _require(model not in selected, "duplicate_assignment")
                _require({"max_budget", "spend", "budget_duration", "budget_reset_at", "blocked"} <= row.keys(),
                         "invalid_native_response")
                blocked = row.get("blocked")
                _require(blocked is None or type(blocked) is bool, "invalid_assignment")
                selected[model] = ModelBudget(model, key_hash, row["key_alias"], _cap(row.get("max_budget")),
                                              _money(row.get("spend")), _optional_text(row.get("budget_duration")),
                                              _optional_text(row.get("budget_reset_at")), blocked)
            if page >= pages:
                break
            page += 1
        _require(len(seen) == counts[0], "incomplete_pagination")
        return selected, len(seen)

    async def initialize_employee(self, user_id: str, models_caps: tuple[tuple[str, Decimal], ...],
                                  total_cap: Decimal, gateway_secret: str, *,
                                  before_write: Callable[[], Awaitable[None]]) -> EmployeeBudget:
        """Create only a fully absent native user and its explicit assignments.

        The caller owns allocation, fresh WebUI authority/config/source guards,
        and user confirmation. The callback must guard every individual POST.
        No retries/repair/rollback; a failure can leave actual partial native
        state, which the caller must inspect and report. Native public APIs do
        not make this sequence an atomic transaction.
        """
        user_id = _user_id(user_id)
        _require(isinstance(models_caps, tuple) and 0 < len(models_caps) <= 100
                 and all(isinstance(entry, tuple) and len(entry) == 2 for entry in models_caps), "invalid_models")
        models = _models(tuple(model for model, _ in models_caps))
        user_cap = _initial_cap(total_cap)
        caps = dict(models_caps)
        wire_caps = {model: _initial_cap(cap) for model, cap in models_caps}
        _require(isinstance(gateway_secret, str) and 0 < len(gateway_secret) <= 4096
                 and not any(char.isspace() for char in gateway_secret), "invalid_configuration")
        _require(callable(before_write), "invalid_configuration")
        observation = await self.inspect_employee(user_id, models)
        _require(observation.kind == "absent", "initialization_requires_absence")
        await before_write()
        await self._request("POST", "/user/new", body={
            "user_id": user_id, "user_role": "internal_user", "models": list(models),
            "max_budget": user_cap, "budget_duration": "1mo", "spend": 0,
            "auto_create_key": False, "send_invite_email": False, "teams": [],
        })
        payload = await self._request("GET", "/user/info", params={"user_id": user_id})
        user = _initial_user(payload, user_id, models, total_cap)
        selected, count = await self._read_assignments(user_id, models, initializing=True)
        expected: dict[str, tuple[str, Decimal]] = {}
        _initial_models(selected, count, expected, user.budget_reset_at)
        for model in sorted(models):
            key = _initialization_key(user_id, model, gateway_secret)
            await before_write()
            await self._request("POST", "/key/generate", body={
                "key": key, "user_id": user_id, "models": [model],
                "key_alias": assignment_alias(user_id, model), "metadata": assignment_metadata(model),
                "max_budget": wire_caps[model], "budget_duration": "1mo", "spend": 0,
                "blocked": False, "allowed_routes": ["llm_api_routes"],
                "duration": None, "team_id": None, "budget_id": None, "send_invite_email": False,
            })
            expected[model] = (hashlib.sha256(key.encode("utf-8")).hexdigest(), caps[model])
            selected, count = await self._read_assignments(user_id, models, initializing=True)
            _initial_models(selected, count, expected, user.budget_reset_at)
        result = await self.read_employee(user_id, models)
        _require(result.max_budget == total_cap and result.spend == 0 and result.budget_duration == "1mo"
                 and _reset_time(result.budget_reset_at) == _reset_time(user.budget_reset_at),
                 "initialization_unconfirmed")
        _initial_models({entry.model: entry for entry in result.models}, len(result.models), expected,
                        user.budget_reset_at)
        return result

    async def set_user_cap(self, user_id: str, cap: Decimal) -> None:
        await self._request("POST", "/user/update", body={"user_id": _user_id(user_id), "max_budget": _wire_cap(cap)})

    async def set_model_cap(self, key_hash: str, cap: Decimal) -> None:
        await self._request("POST", "/key/update", body={"key": _key_hash(key_hash), "max_budget": _wire_cap(cap)})
