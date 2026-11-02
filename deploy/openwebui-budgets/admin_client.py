"""Bounded LiteLLM 1.105.1 public management API adapter.

Native user/key state -> public APIs -> server-only DTO -> caller policy/UI.
The caller owns WebUI role/directory/model checks and mutation confirmation.
This client does not create assignments, retry, allocate, reset or store spend.
Mount the shared modules under their employee_budget_* import names in WebUI.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal, DecimalException
import json
import math
import re
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import UUID

from aiohttp import ClientError, ClientSession, ClientTimeout

from employee_budget_assignment import ASSIGNMENT_NAMESPACE, assignment_alias, assignment_matches
from employee_budget_admin_contract import BudgetAdminError, EmployeeBudget, ModelBudget


PAGE_SIZE = 100
MAX_PAGES = 100
MAX_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT = 10.0
READ_TIMEOUT = 20.0


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
        user_id = _user_id(user_id)
        _require(isinstance(models, tuple) and 0 < len(models) <= 100, "invalid_models")
        _require(all(isinstance(model, str) and 0 < len(model) <= 256 and model == model.strip()
                     and all(ord(char) >= 32 for char in model) for model in models), "invalid_models")
        _require(len(set(models)) == len(models), "invalid_models")
        try:
            async with asyncio.timeout(READ_TIMEOUT):
                return await self._read_employee(user_id, models)
        except asyncio.TimeoutError:
            raise BudgetAdminError("native_transport") from None

    async def _read_employee(self, user_id: str, models: tuple[str, ...]) -> EmployeeBudget:
        payload = await self._request("GET", "/user/info", params={"user_id": user_id})
        user = payload.get("user_info")
        _require(isinstance(user, dict) and user.get("user_id") == user_id
                 and user.get("user_role") == "internal_user", "invalid_employee")
        _require({"max_budget", "spend", "budget_duration", "budget_reset_at"} <= user.keys(),
                 "invalid_native_response")
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
                model = aliases.get(row.get("key_alias"))
                namespace = (metadata or {}).get("owui_budget_namespace")
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
        _require(set(selected) == set(models), "missing_assignment")
        return EmployeeBudget(user_id, _cap(user.get("max_budget")), _money(user.get("spend")),
                              _optional_text(user.get("budget_duration")), _optional_text(user.get("budget_reset_at")),
                              tuple(selected[model] for model in models))

    async def set_user_cap(self, user_id: str, cap: Decimal) -> None:
        await self._request("POST", "/user/update", body={"user_id": _user_id(user_id), "max_budget": _wire_cap(cap)})

    async def set_model_cap(self, key_hash: str, cap: Decimal) -> None:
        await self._request("POST", "/key/update", body={"key": _key_hash(key_hash), "max_budget": _wire_cap(cap)})
