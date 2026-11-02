"""
title: Employee budget administration
author: Corporate Open WebUI
version: 0.1.0
required_open_webui_version: 0.12.2
description: Open a native budget form; apply only the exact stored JSON user turn after confirmation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from uuid import UUID

from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from employee_budget_admin_client import BudgetAdminClient
from employee_budget_admin_contract import BudgetAdminError
import employee_budget_admin_policy as policy
from employee_budget_admin_ui import render_editor
from employee_budget_webui_model_binding import native_connection


def require(condition, code):
    if not condition:
        raise BudgetAdminError(code)


def canonical_id(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    require(valid, "invalid_context")
    return value


async def context(request, actor, metadata):
    from open_webui.env import VERSION
    from open_webui.models.chats import Chats
    from open_webui.models.users import Users

    require(request is not None and isinstance(actor, dict) and isinstance(metadata, dict), "invalid_context")
    user = await Users.get_user_by_id(canonical_id(actor.get("id")))
    require(user is not None and user.id == actor["id"] and user.role == "admin", "admin_required")
    require(VERSION == "0.12.2" and not getattr(request.state, "direct", False)
            and not getattr(request.state, "internal", False) and not metadata.get("direct")
            and not metadata.get("internal") and metadata.get("task") in (None, ""), "unsupported_context")
    require(metadata.get("user_id") == user.id, "invalid_context")
    chat_id, answer_id = canonical_id(metadata.get("chat_id")), canonical_id(metadata.get("message_id"))
    chat = await Chats.get_accessible_chat_by_id(chat_id, user, permission="write")
    require(chat is not None and chat.user_id == user.id, "chat_access_denied")
    message = await Chats.get_message_by_id_and_message_id(chat_id, answer_id)
    require(isinstance(message, dict) and message.get("id") == answer_id and message.get("role") == "assistant"
            and (message.get("user_id") or chat.user_id) == user.id, "answer_access_denied")
    return user, chat_id, message


async def stored_plan(chat_id, message, user):
    from open_webui.models.chats import Chats

    parent_id = canonical_id(message.get("parentId"))
    parent = await Chats.get_message_by_id_and_message_id(chat_id, parent_id)
    require(isinstance(parent, dict) and parent.get("id") == parent_id and parent.get("role") == "user"
            and parent.get("user_id") == user.id, "source_access_denied")
    return parent_id, parent.get("content")


class AuthorizedWriter:
    """Recheck native authority after awaited reads, before each cap-only POST."""
    def __init__(self, client, authorize):
        self.client, self.authorize = client, authorize

    async def read_employee(self, user_id, models):
        return await self.client.read_employee(user_id, models)

    async def set_user_cap(self, user_id, cap):
        await self.authorize()
        await self.client.set_user_cap(user_id, cap)

    async def set_model_cap(self, key_hash, cap):
        await self.authorize()
        await self.client.set_model_cap(key_hash, cap)


class Tools:
    class Valves(BaseModel):
        operator_key: str = Field(default="", description="Native management key; server-side only.",
                                  json_schema_extra={"format": "password", "writeOnly": True})
        managed_model_ids: list[str] = Field(default_factory=list, max_length=100)
        employee_limit: int = Field(default=100, ge=1, le=100)

    def __init__(self):
        self.valves = self.Valves()

    async def _load(self, request):
        from open_webui.models.functions import Functions
        from open_webui.models.users import Users
        from open_webui.utils.models import check_model_access
        from open_webui.utils.session_pool import get_session

        config = await Functions.get_function_valves_by_id("employee_budget_cost") or {}
        url = config.get("ledger_base_url")
        require(isinstance(url, str) and bool(url) and bool(self.valves.operator_key), "invalid_configuration")
        configured = self.valves.managed_model_ids
        require(bool(configured) and len(set(configured)) == len(configured), "invalid_configuration")
        # A request-level base-model override belongs to the currently executing
        # inference route, not an arbitrary management-directory model lookup.
        require(not hasattr(request, "base_model_id"), "unsupported_model_override")
        bindings, labels = [], {}
        for model_id in configured:
            model = request.app.state.MODELS.get(model_id)
            _, wire = await native_connection({"model": model_id}, model, request, url, require=require)
            require(wire not in labels, "ambiguous_managed_model")
            labels[wire] = model.get("name") if isinstance(model.get("name"), str) else model_id
            bindings.append((model, wire))
        listing = await Users.get_users(filter={"roles": ["user"]}, skip=0, limit=self.valves.employee_limit + 1)
        employees, count = listing.get("users"), listing.get("total")
        require(isinstance(employees, list) and type(count) is int
                and 0 <= count == len(employees) <= self.valves.employee_limit, "directory_incomplete")
        client = BudgetAdminClient(await get_session(), url, self.valves.operator_key)
        identities, states = {}, {}
        for employee in employees:
            user_id = canonical_id(employee.id)
            require(employee.role == "user" and user_id not in identities, "invalid_directory")
            allowed = []
            for model, wire in bindings:
                try:
                    await check_model_access(employee, model)
                except Exception as error:
                    # Pinned0.12.2 uses this exact exception for denied access.
                    # Database/transport failures must not silently remove models.
                    if type(error) is Exception and str(error) == "Model not found":
                        continue
                    raise BudgetAdminError("model_access_unavailable") from None
                allowed.append(wire)
            info = employee.info if isinstance(employee.info, dict) else {}
            department = info.get("department")
            identities[user_id] = {"user_id": user_id, "name": employee.name, "email": employee.email,
                "department": department if isinstance(department, str) else "", "models": tuple(allowed),
                "model_labels": {wire: labels[wire] for wire in allowed}}
            states[user_id] = await client.read_employee(user_id, tuple(allowed))
        return url, identities, states, client

    @staticmethod
    def _result(identities, states, *, view=None, status="", outcome="success"):
        rows = [policy.public_employee(identity, states[user_id]) for user_id, identity in identities.items()]
        rows = policy.filter_view(rows, policy.parse_view("{}") if view is None else view)
        html = render_editor(rows, as_of=datetime.now(timezone.utc).isoformat(), status=status)
        return (HTMLResponse(html, headers={"Content-Disposition": "inline", "Cache-Control": "no-store"}),
                {"status": outcome, "message": status or "Budget form opened. Apply its next stored JSON turn with apply_budget_form and no arguments."})

    async def open_budget_form(self, view_json: str = "{}", __request__=None, __user__=None, __metadata__=None):
        """Open current employee budgets. Optional JSON view filters affect display only."""
        await context(__request__, __user__, __metadata__)
        view = policy.parse_view(view_json)
        _, identities, states, _ = await self._load(__request__)
        await context(__request__, __user__, __metadata__)
        return self._result(identities, states, view=view)

    async def apply_budget_form(self, __request__=None, __user__=None, __metadata__=None, __event_call__=None):
        """Apply the exact stored JSON parent user message; no model-supplied business arguments."""
        user, chat_id, message = await context(__request__, __user__, __metadata__)
        parent_id, text = await stored_plan(chat_id, message, user)
        changes = policy.parse_plan(text)
        async def authorize_source():
            current_user, current_chat, current_message = await context(__request__, __user__, __metadata__)
            require(await stored_plan(current_chat, current_message, current_user) == (parent_id, text)
                    and current_chat == chat_id and current_message["id"] == message["id"], "stale_source")
        url, identities, states, _ = await self._load(__request__)
        await authorize_source()
        require(all(change.user_id in identities for change in changes), "unknown_employee")
        prepared = tuple(policy.prepare_change(change, states[change.user_id]) for change in changes)
        confirmation = policy.confirmation_text(prepared, identities)
        require(callable(__event_call__), "confirmation_unavailable")
        approved = await __event_call__({"type": "confirmation", "data": {
            "title": "Изменение бюджетов сотрудников", "message": confirmation}})
        # The entire source/authority/directory/state is refreshed after waiting,
        # including on cancellation; a lost admin role must reveal no fresh data.
        try:
            fresh_user, fresh_chat, fresh_message = await context(__request__, __user__, __metadata__)
            require((fresh_user.id, fresh_chat, fresh_message["id"]) == (user.id, chat_id, message["id"]), "stale_context")
            require(await stored_plan(fresh_chat, fresh_message, fresh_user) == (parent_id, text), "stale_source")
            fresh_url, fresh_identities, fresh_states, client = await self._load(__request__)
            await authorize_source()
            if approved is not True:
                return self._result(fresh_identities, fresh_states, outcome="cancelled",
                                    status="Изменения отменены. Показано текущее состояние.")
            require(fresh_url == url and fresh_identities == identities, "stale_directory")
            fresh_prepared = tuple(policy.prepare_change(change, fresh_states[change.user_id]) for change in changes)
            require(policy.confirmation_text(fresh_prepared, fresh_identities) == confirmation, "stale_confirmation")
            writer = AuthorizedWriter(client, authorize_source)
            for change in fresh_prepared:
                await policy.apply_prepared(writer, change)
            status = "Изменения применены. Показано текущее состояние."
            outcome = "success"
        except Exception as error:
            # No rollback/retry: native writes may already have committed.
            code = error.code if isinstance(error, BudgetAdminError) else "operation_failed"
            code = code if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,64}", code) else "operation_failed"
            status = "Изменения не завершены; часть могла сохраниться. Показано текущее состояние. Код: " + code
            outcome = "partial_or_failed"
        await context(__request__, __user__, __metadata__)
        _, identities, states, _ = await self._load(__request__)
        await context(__request__, __user__, __metadata__)
        return self._result(identities, states, status=status, outcome=outcome)
