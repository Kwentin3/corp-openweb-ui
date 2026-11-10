"""
title: Employee budget administration
author: Corporate Open WebUI
version: 0.1.0
required_open_webui_version: 0.12.2
description: Open a native budget form; apply only the exact stored JSON user turn after confirmation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
import copy
import json
import re
from uuid import UUID

from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from employee_budget_admin_client import BudgetAdminClient
from employee_budget_admin_contract import BudgetAdminError, EmployeeBudgetInspection
import employee_budget_admin_policy as policy
from employee_budget_admin_ui import render_editor
from employee_budget_cost_readback import read_unknown_presence
from employee_budget_webui_model_binding import native_connection


PRESENCE_READ_SECONDS = 5.0


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


@dataclass(frozen=True)
class LoadedDirectory:
    url: str
    identities: dict
    states: dict
    client: BudgetAdminClient
    config: dict
    secrets: dict
    inspections: dict
    labels: dict
    service: dict | None = None
    unknown_presence: dict | None = None

    def configuration(self):
        # Server-only comparison; never project credentials into HTML or context.
        return (self.url, self.config.get("ledger_admin_key"), self.identities,
                self.secrets, self.config.get("default_budget_template"), self.labels)


class Tools:
    class Valves(BaseModel):
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
        key = config.get("ledger_admin_key")
        require(isinstance(url, str) and bool(url) and isinstance(key, str) and bool(key), "invalid_configuration")
        configured = self.valves.managed_model_ids
        require(bool(configured) and len(set(configured)) == len(configured), "invalid_configuration")
        # A request-level base-model override belongs to the currently executing
        # inference route, not an arbitrary management-directory model lookup.
        require(not hasattr(request, "base_model_id"), "unsupported_model_override")
        bindings, labels, secrets = [], {}, {}
        for model_id in configured:
            model = request.app.state.MODELS.get(model_id)
            secret, wire = await native_connection({"model": model_id}, model, request, url, require=require)
            require(wire not in labels, "ambiguous_managed_model")
            labels[wire] = model.get("name") if isinstance(model.get("name"), str) else model_id
            secrets[wire] = secret
            bindings.append((model, wire))
        policy.template_value(config.get("default_budget_template"), labels)
        listing = await Users.get_users(filter={"roles": ["user"]}, skip=0, limit=self.valves.employee_limit + 1)
        employees, count = listing.get("users"), listing.get("total")
        require(isinstance(employees, list) and type(count) is int
                and 0 <= count == len(employees) <= self.valves.employee_limit, "directory_incomplete")
        session = await get_session()
        client = BudgetAdminClient(session, url, key)
        identities, states, inspections = {}, {}, {}
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
            inspection = (await client.inspect_employee(user_id, tuple(allowed)) if allowed else
                          EmployeeBudgetInspection(user_id, (), "conflict", code="no_allowed_models"))
            inspections[user_id] = inspection
            if inspection.kind == "ready":
                states[user_id] = inspection.employee_budget
        service = None
        payer = config.get("service_payer_id")
        if payer:
            payer = canonical_id(payer)
            require(await Users.get_user_by_id(payer) is None, "personal_payer_forbidden")
            budget = await client.read_service(payer)
            policy.monthly(budget)
            service = {"label": "Служебные задачи и RAG", "budget_usd": policy.money(budget.max_budget),
                       "spend_usd": policy.money(budget.spend), "budget_reset_at": budget.budget_reset_at,
                       "remaining_usd": policy.money(budget.max_budget - budget.spend)
                           if budget.max_budget is not None else None}
        unknown_presence = await self._unknown_presence(session, url, key, identities, states)
        return LoadedDirectory(url, identities, states, client, copy.deepcopy(config), secrets, inspections, labels,
                               service, unknown_presence)

    @staticmethod
    async def _unknown_presence(session, url, key, identities, states):
        """Validate the admin directory before the shared presence-only read."""
        for uid, state in states.items():
            allowed = identities[uid]["models"]
            models = [model.model for model in state.models]
            require(state.user_id == uid and len(models) == len(set(models))
                    and set(models) == set(allowed), "invalid_models")

        return await read_unknown_presence(session, base_url=url, admin_key=key, states=states,
                                           timeout_seconds=PRESENCE_READ_SECONDS, max_pages=2)

    @staticmethod
    def _result(data, *, view=None, status="", outcome="success"):
        rows = [policy.public_employee(data.identities[user_id], state,
                    unknown_presence=None if data.unknown_presence is None else data.unknown_presence.get(user_id, {}))
                for user_id, state in data.states.items()]
        rows = policy.filter_view(rows, policy.parse_view("{}") if view is None else view)
        template = data.config.get("default_budget_template")
        pending = [policy.public_pending(data.identities[uid], inspection, template, data.labels)
                   for uid, inspection in data.inspections.items() if inspection.kind != "ready"]
        html = render_editor(rows, as_of=datetime.now(timezone.utc).isoformat(), status=status,
                             template=policy.template_public(template, data.labels), pending=pending, service=data.service)
        return (HTMLResponse(html, headers={"Content-Disposition": "inline", "Cache-Control": "no-store"}),
                {"status": outcome, "message": status or "Budget form opened. Apply its next stored JSON turn with apply_budget_form and no arguments."})

    async def open_budget_form(self, view_json: str = "{}", __request__=None, __user__=None, __metadata__=None):
        """Open current employee budgets. Optional JSON view filters affect display only."""
        await context(__request__, __user__, __metadata__)
        view = policy.parse_view(view_json)
        data = await self._load(__request__)
        await context(__request__, __user__, __metadata__)
        return self._result(data, view=view)

    async def apply_budget_form(self, __request__=None, __user__=None, __metadata__=None, __event_call__=None):
        """Apply the exact stored JSON parent user message; no model-supplied business arguments."""
        user, chat_id, message = await context(__request__, __user__, __metadata__)
        parent_id, text = await stored_plan(chat_id, message, user)
        kind = policy.submission_kind(text)
        if kind != "employee_budget_plan":
            return await self._apply_setup(kind, text, user, chat_id, message, parent_id,
                                           __request__, __user__, __metadata__, __event_call__)
        changes = policy.parse_plan(text)
        async def authorize_source():
            current_user, current_chat, current_message = await context(__request__, __user__, __metadata__)
            require(await stored_plan(current_chat, current_message, current_user) == (parent_id, text)
                    and current_chat == chat_id and current_message["id"] == message["id"], "stale_source")
        data = await self._load(__request__)
        await authorize_source()
        require(all(change.user_id in data.identities for change in changes), "unknown_employee")
        require(all(change.user_id in data.states for change in changes), "employee_not_ready")
        prepared = tuple(policy.prepare_change(change, data.states[change.user_id]) for change in changes)
        confirmation = policy.confirmation_text(prepared, data.identities)
        require(callable(__event_call__), "confirmation_unavailable")
        approved = await __event_call__({"type": "confirmation", "data": {
            "title": "Изменение бюджетов сотрудников", "message": confirmation}})
        # The entire source/authority/directory/state is refreshed after waiting,
        # including on cancellation; a lost admin role must reveal no fresh data.
        try:
            fresh_user, fresh_chat, fresh_message = await context(__request__, __user__, __metadata__)
            require((fresh_user.id, fresh_chat, fresh_message["id"]) == (user.id, chat_id, message["id"]), "stale_context")
            require(await stored_plan(fresh_chat, fresh_message, fresh_user) == (parent_id, text), "stale_source")
            fresh = await self._load(__request__)
            await authorize_source()
            if approved is not True:
                return self._result(fresh, outcome="cancelled",
                                    status="Изменения отменены. Показано текущее состояние.")
            require(fresh.url == data.url and fresh.identities == data.identities, "stale_directory")
            require(all(change.user_id in fresh.states for change in changes), "employee_not_ready")
            fresh_prepared = tuple(policy.prepare_change(change, fresh.states[change.user_id]) for change in changes)
            require(policy.confirmation_text(fresh_prepared, fresh.identities) == confirmation, "stale_confirmation")
            writer = AuthorizedWriter(fresh.client, authorize_source)
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
        data = await self._load(__request__)
        await context(__request__, __user__, __metadata__)
        return self._result(data, status=status, outcome=outcome)

    async def _apply_setup(self, kind, text, user, chat_id, message, parent_id,
                           request, actor, metadata, event_call):
        from open_webui.models.functions import Functions

        async def authorize_source():
            current_user, current_chat, current_message = await context(request, actor, metadata)
            require((current_user.id, current_chat, current_message["id"]) == (user.id, chat_id, message["id"])
                    and await stored_plan(current_chat, current_message, current_user) == (parent_id, text), "stale_source")

        await authorize_source()
        data = await self._load(request)
        await authorize_source()
        template = data.config.get("default_budget_template")
        if kind == "employee_budget_template":
            proposed = policy.parse_template_plan(text, template, data.labels)
            description = ("Шаблон для новых сотрудников. Существующие бюджеты не изменятся.\n\n"
                           + "Было: " + json.dumps(template, ensure_ascii=False, sort_keys=True)
                           + "\n\nСтанет: " + json.dumps(proposed, ensure_ascii=False, sort_keys=True))
            changes = ()
        else:
            changes = policy.parse_initialization(text)
            require(all(change.user_id in data.identities for change in changes), "unknown_employee")
            lines = ["Создание новых месячных бюджетов. Существующие назначения не исправляются.",
                     "Период: календарный месяц (1mo), по часовому поясу и времени сброса владельца учёта."]
            initial_caps = {}
            for change in changes:
                caps = policy.prepare_initialization(change, data.inspections[change.user_id],
                    data.identities[change.user_id], template, data.labels)
                initial_caps[change.user_id] = caps
                lines.append(policy.plain_label(data.identities[change.user_id]["name"]) + " (" + change.user_id + "): нет бюджета → "
                             + policy.money(change.budget_usd) + " USD, доли "
                             + json.dumps({m: policy.money(s) for m, s in change.shares}, ensure_ascii=False))
                lines.append("Создать: 1 личный бюджет и " + str(len(caps)) + " назначений моделей.")
                lines.extend(policy.plain_label(data.labels[model]) + ": нет назначения → " + policy.money(cap) + " USD"
                             for model, cap in caps)
            description = "\n\n".join(lines)
        # Native confirmation is rendered as Markdown; escape all public labels.
        description = policy.markdown_text(description)
        require(callable(event_call), "confirmation_unavailable")
        approved = await event_call({"type": "confirmation", "data": {
            "title": "Шаблон бюджета" if not changes else "Создание бюджетов сотрудников", "message": description}})
        outcome, status = "success", "Изменения применены. Показано текущее состояние."
        try:
            await authorize_source()
            fresh = await self._load(request)
            await authorize_source()
            if approved is not True:
                return self._result(fresh, outcome="cancelled", status="Изменения отменены. Показано текущее состояние.")
            require(fresh.configuration() == data.configuration(), "stale_configuration")

            async def before_write():
                await authorize_source()
                current = await self._load(request)
                await authorize_source()
                require(current.configuration() == data.configuration(), "stale_configuration")

            if kind == "employee_budget_template":
                await before_write()
                # Native Valves is a full replacement, without CAS. Re-read and
                # preserve all existing fields; no multi-owner atomicity claimed.
                config = await Functions.get_function_valves_by_id("employee_budget_cost")
                await authorize_source()
                require(isinstance(config, dict) and config == fresh.config, "stale_configuration")
                config = {**copy.deepcopy(config), "default_budget_template": proposed}
                updated = await Functions.update_function_valves_by_id("employee_budget_cost", config)
                require(updated is not None, "template_write_unconfirmed")
                actual = await Functions.get_function_valves_by_id("employee_budget_cost")
                await authorize_source()
                require(actual == config, "template_write_unconfirmed")
            else:
                require(len(set(fresh.secrets.values())) == 1, "ambiguous_gateway_secret")
                for change in changes:
                    caps = policy.prepare_initialization(change, fresh.inspections[change.user_id],
                        fresh.identities[change.user_id], template, fresh.labels)
                    require(caps == initial_caps[change.user_id], "stale_confirmation")
                    await fresh.client.initialize_employee(change.user_id, caps, change.budget_usd,
                        next(iter(fresh.secrets.values())), before_write=before_write)
        except Exception as error:
            code = error.code if isinstance(error, BudgetAdminError) else "operation_failed"
            code = code if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,64}", code) else "operation_failed"
            outcome = "partial_or_failed"
            status = "Изменения не завершены; часть могла сохраниться. Показано текущее состояние. Код: " + code
        await authorize_source()
        data = await self._load(request)
        await authorize_source()
        return self._result(data, outcome=outcome, status=status)
