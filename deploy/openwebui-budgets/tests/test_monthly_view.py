"""Real Event/FastAPI/projection; native auth, DB and ledger IO leaves are doubled.

These component/API checks do not qualify native JWT authentication, ledger
persistence, ordinary-user browser use or deployment.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
from uuid import NAMESPACE_URL, uuid5

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.routing import APIRoute
from starlette.responses import PlainTextResponse
from starlette.routing import Mount


BUDGETS = Path(__file__).resolve().parents[1]
ACTOR, OTHER, ADMIN = (str(uuid5(NAMESPACE_URL, label)) for label in
                       ("monthly-actor", "monthly-other", "monthly-admin"))
FUNCTION_ID = "employee_budget_monthly_view"
KEY = "sk-synthetic-monthly-server-management-key"
BASE_URL = "http://synthetic-ledger.invalid"
RESET = "2099-01-01T00:00:00Z"


def load(monkeypatch, name, filename):
    spec = importlib.util.spec_from_file_location(name, BUDGETS / filename)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def native(monkeypatch):
    def module(name, **values):
        result = ModuleType(name)
        result.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    contract = load(monkeypatch, "employee_budget_admin_contract", "admin_contract.py")
    policy = load(monkeypatch, "employee_budget_admin_policy", "admin_policy.py")
    owner = load(monkeypatch, "monthly_view_under_test", "monthly_view.py")
    users = {uid: SimpleNamespace(id=uid, role=role, name=name, email=name + "@synthetic.invalid",
             info={"department": "R&D", "private_configuration": "must-not-disclose"}) for uid, role, name in
             ((ACTOR, "user", "employee"), (OTHER, "user", "other"), (ADMIN, "admin", "admin"))}
    get_user = AsyncMock(side_effect=lambda uid: copy.deepcopy(users.get(uid)))
    model = contract.ModelBudget("native-a", "a" * 64, "private-native-key-alias", Decimal("10"),
                                 Decimal("3"), "1mo", RESET, False)
    states = {uid: contract.EmployeeBudget(uid, Decimal("10"), Decimal("3"), "1mo", RESET, (model,))
              for uid in users}
    observations = {uid: {} for uid in users}
    read_service = AsyncMock(side_effect=lambda uid: copy.deepcopy(states[uid]))
    read_unknown = AsyncMock(side_effect=lambda session, **kw: {uid: observations[uid] for uid in kw["states"]})
    created_clients = []
    class Reader:
        def __init__(self, session, url, key):
            created_clients.append((session, url, key))
        async def read_service(self, uid):
            return await read_service(uid)

    session = object()
    get_session = AsyncMock(return_value=session)
    function = SimpleNamespace(id=FUNCTION_ID, type="event", is_active=True)
    common = {"ledger_base_url": BASE_URL, "ledger_admin_key": KEY,
              "private_connection_setting": "must-not-disclose"}
    get_valves = AsyncMock(return_value=common)
    event = owner.Event()
    cached = AsyncMock(return_value=(event, None, None))
    async def verified(request: Request):
        uid = request.headers.get("Authorization", "").removeprefix("Bearer ")
        user = copy.deepcopy(users.get(uid))
        if user is None or user.role not in {"user", "admin"}:
            raise HTTPException(401, "Not authenticated")
        return user

    module("employee_budget_admin_client", BudgetAdminClient=Reader)
    module("employee_budget_cost_readback", read_unknown_presence=read_unknown)
    module("open_webui.env", VERSION="0.12.2")
    module("open_webui.models.users", Users=SimpleNamespace(get_user_by_id=get_user))
    module("open_webui.models.functions", Functions=SimpleNamespace(
        get_function_by_id=AsyncMock(return_value=function), get_function_valves_by_id=get_valves))
    module("open_webui.utils.auth", get_verified_user=verified)
    module("open_webui.utils.plugin", get_function_module_from_cache=cached)
    module("open_webui.utils.session_pool", get_session=get_session)
    app = FastAPI()
    async def spa(scope, receive, send):
        await PlainTextResponse("spa", status_code=404)(scope, receive, send)
    app.mount("/", spa)
    asyncio.run(event.event({}, __event_name__="system.startup.completed", __id__=FUNCTION_ID, __app__=app))
    async def request(*, uid=ACTOR, target=None, method="GET", json=None):
        headers = {"Authorization": "Bearer " + uid} if uid is not None else {}
        params = {} if target is None else {"user_id": target}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://monthly.invalid") as client:
            return await client.request(method, owner.ROUTE_PATH, headers=headers, params=params, json=json)
    return SimpleNamespace(owner=owner, event=event, app=app, request=request, users=users, states=states,
        observations=observations, read_service=read_service, read_unknown=read_unknown, get_user=get_user,
        get_valves=get_valves, function=function, cached=cached, created_clients=created_clients,
        session=session, policy=policy, contract=contract, get_session=get_session)


def test_authenticated_self_uses_selected_native_counter_and_private_server_credentials(native):
    response = asyncio.run(native.request())
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["user_id"], data["budget_usd"], data["spend_usd"], data["remaining_usd"]) == (ACTOR, "10", "3", "7")
    assert data["budget_duration"] == "1mo" and data["budget_reset_at"] == RESET
    assert data["models"][0]["budget_duration"] == "1mo"
    assert data["models"][0]["budget_reset_at"] == RESET
    assert data["models"][0]["remaining_usd"] == "7"
    assert data["models"][0]["blocked"] is False
    assert data["expense_status"] == "unavailable"
    assert data["expense_observation_scope"] == "assignment_history"
    assert datetime.fromisoformat(data["as_of"]).utcoffset().total_seconds() == 0
    assert response.headers["Cache-Control"] == "no-store"
    native.read_service.assert_awaited_once_with(ACTOR)
    assert native.created_clients == [(native.session, BASE_URL, KEY)]
    native.get_valves.assert_awaited_once_with("employee_budget_cost")
    assert native.read_unknown.await_args.kwargs["states"].keys() == {ACTOR}
    assert (native.read_unknown.await_args.kwargs["base_url"], native.read_unknown.await_args.kwargs["admin_key"]) == (BASE_URL, KEY)
    for private in (BASE_URL, KEY, "a" * 64, "private-native-key-alias", "must-not-disclose"):
        assert private not in response.text


def test_public_monthly_read_reuses_projection_and_rechecks_native_actor(native):
    actor = copy.deepcopy(native.users[ACTOR])
    response = asyncio.run(native.event.read_monthly(None, actor, None))
    assert json.loads(response.body)["user_id"] == ACTOR
    native.read_service.assert_awaited_once_with(ACTOR)
    native.users[ACTOR].role = "pending"
    native.read_service.reset_mock()
    with pytest.raises(HTTPException) as denied:
        asyncio.run(native.event.read_monthly(None, actor, None))
    assert denied.value.status_code == 403
    native.read_service.assert_not_awaited()


@pytest.mark.parametrize("uid", [None, "pending"])
def test_anonymous_and_unverified_callers_cannot_read(native, uid):
    if uid == "pending":
        native.users[ACTOR].role = "pending"
        uid = ACTOR
    response = asyncio.run(native.request(uid=uid))
    assert response.status_code == 401
    native.read_service.assert_not_awaited()
    native.get_valves.assert_not_awaited()


def test_employee_foreign_target_is_denied_before_backend_or_foreign_user_read(native):
    response = asyncio.run(native.request(target=OTHER, json={"role": "admin", "id": ADMIN}))
    assert response.status_code == 403
    assert response.json() == {"detail": native.owner.DENIED}
    native.read_service.assert_not_awaited()
    native.get_valves.assert_not_awaited()
    assert [call.args[0] for call in native.get_user.await_args_list] == [ACTOR]


def test_admin_selected_target_uses_only_that_employee(native):
    response = asyncio.run(native.request(uid=ADMIN, target=OTHER))
    assert response.status_code == 200
    assert response.json()["user_id"] == OTHER
    assert response.json()["email"] == native.users[OTHER].email
    native.read_service.assert_awaited_once_with(OTHER)
    assert native.read_unknown.await_args.kwargs["states"].keys() == {OTHER}


@pytest.mark.parametrize("change", ["admin_demoted", "actor_disabled", "target_deleted"])
def test_fresh_role_and_target_are_rechecked_before_disclosure(native, change):
    def budget(uid):
        if change == "admin_demoted":native.users[ADMIN].role = "user"
        elif change == "actor_disabled":native.users[ADMIN].role = "pending"
        else:native.users.pop(OTHER)
        return copy.deepcopy(native.states[uid])
    native.read_service.side_effect = budget
    response = asyncio.run(native.request(uid=ADMIN, target=OTHER))
    assert response.status_code == 403
    assert response.json() == {"detail": native.owner.DENIED}
    assert "budget_usd" not in response.text


@pytest.mark.parametrize("cap,spend,remaining", [(Decimal("0"), Decimal("0"), "0"),
    (Decimal("0"), Decimal("3"), "-3"), (None, Decimal("3"), None)])
def test_zero_over_budget_and_nullable_caps_are_native_projections(native, cap, spend, remaining):
    state = native.states[ACTOR]
    model = replace(state.models[0], max_budget=cap, spend=spend, blocked=None)
    native.states[ACTOR] = replace(state, max_budget=cap, spend=spend, models=(model,))
    response = asyncio.run(native.request())
    assert response.status_code == 200
    data = response.json()
    assert data["remaining_usd"] == remaining
    assert data["models"][0]["remaining_usd"] == remaining
    assert data["models"][0]["blocked"] is None


@pytest.mark.parametrize("confirmed,blocked,status", [(True, False, "unknown"), (False, True, "unavailable")])
def test_unknown_history_is_independent_of_native_block_and_monthly_counter(native, confirmed, blocked, status):
    state = native.states[ACTOR]
    native.states[ACTOR] = replace(state, models=(replace(state.models[0], blocked=blocked),))
    native.observations[ACTOR] = {"native-a": {"unknown_confirmed": confirmed, "as_of": "2026-11-10T00:00:00+00:00"}}
    response = asyncio.run(native.request())
    assert response.status_code == 200
    data = response.json()
    assert data["expense_status"] == data["models"][0]["expense_status"] == status
    assert data["models"][0]["blocked"] is blocked
    assert (data["spend_usd"], data["remaining_usd"]) == ("3", "7")
    assert data["expense_observation_scope"] == "assignment_history"


@pytest.mark.parametrize("defect", ["missing_state", "native_http_error", "period", "foreign_state"])
def test_native_read_errors_never_become_zero_or_expose_private_errors(native, defect):
    if defect == "missing_state":native.read_service.side_effect = native.contract.BudgetAdminError("native_http_404")
    elif defect == "native_http_error":native.read_service.side_effect = HTTPException(502, KEY + BASE_URL)
    elif defect == "period":native.states[ACTOR] = replace(native.states[ACTOR], budget_duration="1d")
    else:native.states[ACTOR] = replace(native.states[ACTOR], user_id=OTHER)
    response = asyncio.run(native.request())
    assert response.status_code == 503
    assert response.json() == {"detail": native.owner.UNAVAILABLE}
    assert KEY not in response.text and BASE_URL not in response.text
    assert "budget_usd" not in response.text


def test_only_get_is_a_budget_read_and_inactive_function_fails_closed(native):
    response = asyncio.run(native.request(method="POST", json={"budget_usd": "999"}))
    assert response.status_code in (404, 405)
    native.read_service.assert_not_awaited()
    native.function.is_active = False
    response = asyncio.run(native.request())
    assert response.status_code == 503
    native.read_service.assert_not_awaited()
    native.cached.assert_not_awaited()


def test_event_route_lifecycle_collision_and_native_cache_reload(native):
    path = native.owner.ROUTE_PATH
    routes = lambda: [route for route in native.app.router.routes if getattr(route, "path", None) == path]
    assert len(routes()) == 1
    assert native.app.router.routes.index(routes()[0]) < next(i for i, r in enumerate(native.app.router.routes) if isinstance(r, Mount) and r.path == "")
    asyncio.run(native.event.event({}, __event_name__="system.startup.completed", __id__=FUNCTION_ID, __app__=native.app))
    assert len(routes()) == 1
    class Reloaded(native.owner.Event):
        async def read_monthly(self, *args):
            result = await super().read_monthly(*args)
            result.headers["X-Selected-Function"] = "current-cache"
            return result
    native.cached.return_value = (Reloaded(), None, None)
    response = asyncio.run(native.request())
    assert response.status_code == 200 and response.headers["X-Selected-Function"] == "current-cache"
    asyncio.run(native.event.event({"subject": {"type": "function", "id": FUNCTION_ID}},
        __event_name__="function.disable_started", __id__=FUNCTION_ID, __app__=native.app))
    assert routes() == []
    async def claimed():return None
    native.app.router.routes.insert(0, APIRoute(path, claimed, methods=["GET"], name="other-owner"))
    with pytest.raises(RuntimeError, match="already claimed"):
        asyncio.run(native.event.event({}, __event_name__="system.startup.completed", __id__=FUNCTION_ID, __app__=native.app))
