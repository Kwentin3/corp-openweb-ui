"""
title: Employee monthly budget view
author: Corporate Open WebUI
version: 0.1.0
required_open_webui_version: 0.12.2

description: Authenticated read-only monthly native budget for self or an administrator-selected employee.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.routing import Mount


ROUTE_PATH = "/api/v1/employee-budgets/monthly"
ROUTE_PREFIX = "employee_budget_monthly_view:"
UNAVAILABLE = "Monthly budget view is unavailable"
DENIED = "Budget access denied"


def canonical_id(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise HTTPException(400, "Invalid budget user ID")
    return value


async def authorized_target(caller_id, selected_id):
    from open_webui.models.users import Users

    caller = await Users.get_user_by_id(caller_id)
    if caller is None or caller.id != caller_id or caller.role not in {"user", "admin"}:
        raise HTTPException(403, DENIED)
    target_id = canonical_id(selected_id) if selected_id is not None else caller.id
    if target_id != caller.id and caller.role != "admin":
        raise HTTPException(403, DENIED)
    target = caller if target_id == caller.id else await Users.get_user_by_id(target_id)
    if target is None or target.id != target_id or target.role not in {"user", "admin"}:
        raise HTTPException(403, DENIED)
    return target


class Event:
    async def event(self, event: dict, __event_name__: str = None, __id__: str = None, __app__=None, **kwargs):
        if __app__ is None or not __id__:
            return
        subject = event.get("subject") or {}
        own_event = subject.get("type") == "function" and subject.get("id") == __id__
        route_name = ROUTE_PREFIX + __id__
        if __event_name__ == "system.shutdown.started" or (__event_name__ == "function.disable_started" and own_event):
            __app__.router.routes[:] = [route for route in __app__.router.routes
                if not (isinstance(route, APIRoute) and route.name == route_name)]
            return
        if __event_name__ != "system.startup.completed" and not (__event_name__ == "function.enable_started" and own_event):
            return
        for route in __app__.router.routes:
            if getattr(route, "path", None) == ROUTE_PATH:
                if isinstance(route, APIRoute) and route.name == route_name:
                    return
                raise RuntimeError("Monthly budget route is already claimed")

        from open_webui.utils.auth import get_verified_user

        async def monthly(request: Request, user_id: str | None = None, user=Depends(get_verified_user)):
            try:
                from open_webui.models.functions import Functions
                from open_webui.utils.plugin import get_function_module_from_cache

                function = await Functions.get_function_by_id(__id__)
                if function is None or function.type != "event" or not function.is_active:
                    raise HTTPException(503, UNAVAILABLE)
                module, _, _ = await get_function_module_from_cache(request, __id__, function=function)
                return await module.read_monthly(request, user, user_id)
            except HTTPException as error:
                if (error.status_code, error.detail) in ((400, "Invalid budget user ID"),
                        (403, DENIED), (503, UNAVAILABLE)):
                    raise
                raise HTTPException(503, UNAVAILABLE) from None
            except Exception:
                raise HTTPException(503, UNAVAILABLE) from None

        route = APIRoute(ROUTE_PATH, monthly, methods=["GET"], name=route_name, include_in_schema=False)
        routes = __app__.router.routes
        index = next((i for i, current in enumerate(routes) if isinstance(current, Mount) and current.path == ""), len(routes))
        routes.insert(index, route)

    async def read_monthly(self, request, actor, selected_id=None):
        """Shared readonly public projection for the native GET and self Action."""
        from employee_budget_admin_client import BudgetAdminClient
        from employee_budget_admin_policy import public_employee
        from open_webui.env import VERSION
        from open_webui.models.functions import Functions
        from open_webui.utils.session_pool import get_session

        if VERSION != "0.12.2":
            raise HTTPException(503, UNAVAILABLE)
        caller_id = canonical_id(actor.id)
        target = await authorized_target(caller_id, selected_id)
        common = await Functions.get_function_valves_by_id("employee_budget_cost")
        if not isinstance(common, dict):
            raise HTTPException(503, UNAVAILABLE)
        session = await get_session()
        client = BudgetAdminClient(session, common.get("ledger_base_url"), common.get("ledger_admin_key"))
        state = await client.read_service(target.id)
        if state.user_id != target.id:
            raise HTTPException(503, UNAVAILABLE)
        target = await authorized_target(caller_id, target.id)
        info = target.info if isinstance(target.info, dict) else {}
        department = info.get("department")
        identity = {"user_id": target.id, "name": target.name, "email": target.email,
                    "department": department if isinstance(department, str) else "",
                    "models": tuple(model.model for model in state.models)}
        result = public_employee(identity, state)
        result.update(as_of=datetime.now(timezone.utc).isoformat(), expense_observation_scope="native_budget_counters")
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
