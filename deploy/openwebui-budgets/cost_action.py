"""
title: Стоимость: детали
author: Corporate Open WebUI
version: 0.1.0
required_open_webui_version: 0.12.2
description: Read a fresh accrued cost snapshot for the selected native answer and chat.

Native Actions owns HTMLResponse embeds and appends them to the answer. Reader
configuration belongs solely to the existing employee_budget_cost Filter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from employee_budget_cost_readback import CostReadError, read_cost_snapshot


FILTER_ID = "employee_budget_cost"
MONTHLY_ID = "employee_budget_monthly_view"
HEIGHT_SCRIPT = """(()=>{const send=()=>parent.postMessage({type:'iframe:height',height:document.documentElement.scrollHeight},'*');new ResizeObserver(send).observe(document.documentElement);addEventListener('load',send);send();})();"""


def require(condition):
    if not condition:
        raise ValueError("Cost details are unavailable for this selection.")


def canonical_id(value):
    try:
        require(isinstance(value, str) and str(UUID(value)) == value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Cost details are unavailable for this selection.") from None
    return value


def escaped(value):
    return escape(str(value), quote=True)


def section(kind, title, total):
    known = total is not None and total.spend is not None
    amount = format(total.spend, "f") if known else "unknown"
    contents = (f'<output data-cost-usd="{escaped(amount)}">{escaped(amount)}</output> USD'
                if known else '<output data-cost-usd="unknown">Сумма неизвестна</output>')
    if known:
        rows = []
        for model in total.models:
            values = {"model": model.model, "calls": model.calls, "prompt_tokens": model.prompt_tokens,
                      "completion_tokens": model.completion_tokens, "total_tokens": model.total_tokens,
                      "spend_usd": format(model.spend, "f")}
            cells = "".join(f'<td data-field="{field}">{escaped(value) if value is not None else "нет данных"}</td>'
                            for field, value in values.items())
            rows.append(f'<tr data-model="{escaped(model.model)}">{cells}</tr>')
        contents += ('<table><thead><tr><th>Модель</th><th>Вызовы</th><th>Вход</th><th>Выход</th>'
                     '<th>Всего токенов</th><th>USD</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>')
    return f'<section data-cost-scope="{kind}"><h2>{title}</h2>{contents}</section>'


def render_monthly(snapshot):
    if snapshot is None:
        return ('<aside data-monthly-budget="unavailable"><h2>Мой месячный бюджет</h2>'
                '<p role="status">Данные месячного бюджета недоступны. '
                'Попробуйте снова открыть «Стоимость: детали».</p></aside>')

    def amount(value, missing="не установлен"):
        return missing if value is None else escaped(value) + " USD"

    native_counters = snapshot.get("expense_observation_scope") == "native_budget_counters"
    expense_column = not native_counters or any(value.get("expense_status") is not None
                                               for value in [snapshot, *snapshot["models"]])

    def expense(value):
        if native_counters and value.get("expense_status") is None:
            return ''
        if value.get("expense_status") == "unknown":
            return '<strong>Расход неизвестен: в истории есть запросы без данных о расходе. Итоговый остаток не подтверждён.</strong>'
        return 'Полнота данных о расходе не подтверждена; итоговый остаток не подтверждён.'

    rows = []
    for model in snapshot["models"]:
        blocked = model["blocked"]
        block = "Заблокирована" if blocked is True else "Не заблокирована" if blocked is False else "Нет данных"
        rows.append('<tr><th scope="row">' + escaped(model.get("label") or model["id"]) + '</th>'
            '<td>' + amount(model["cap_usd"]) + '</td><td>' + amount(model["spend_usd"], "нет данных") + '</td>'
            '<td>' + amount(model["remaining_usd"], "нет лимита") + '</td>'
            '<td>' + escaped(model["budget_duration"]) + '<br>' + escaped(model["budget_reset_at"]) + '</td>'
            '<td>' + block + '</td>' + ('<td>' + expense(model) + '</td>' if expense_column else '') + '</tr>')
    expense_status = expense(snapshot)
    return ('<aside data-monthly-budget="v1"><h2>Мой месячный бюджет</h2>'
            '<p>Снимок на: <time datetime="' + escaped(snapshot["as_of"]) + '">' + escaped(snapshot["as_of"]) + '</time>.</p>'
            '<p>Бюджет: <output data-monthly-field="budget">' + amount(snapshot["budget_usd"]) + '</output> · '
            'Учтённый расход: <output data-monthly-field="spend">' + amount(snapshot["spend_usd"], "нет данных") + '</output> · '
            'Остаток по учтённым расходам: <output data-monthly-field="remaining">'
            + amount(snapshot["remaining_usd"], "нет лимита") + '</output>.</p>'
            '<p>Период: ' + escaped(snapshot["budget_duration"]) + '. Следующее обновление бюджета: '
            + escaped(snapshot["budget_reset_at"]) + '.</p>'
            + ('<p role="status">' + expense_status + '</p>' if expense_status else '')
            + '<p>' + ('Неизвестные расходы не включены в показанные суммы. ' if expense_column else '')
            + 'Остаток не гарантирует допуск следующего запроса.</p>'
            '<table><thead><tr><th>Модель</th><th>Лимит</th><th>Учтённый расход</th><th>Остаток по учёту</th>'
            '<th>Период / следующее обновление</th><th>Блокировка</th>'
            + ('<th>Полнота расхода</th>' if expense_column else '') + '</tr></thead><tbody>'
            + (''.join(rows) or '<tr><td colspan="' + ('7' if expense_column else '6') + '">Модели не назначены.</td></tr>') + '</tbody></table>'
            '<p>Чтобы обновить снимок, снова откройте «Стоимость: детали».</p>'
            '<p>При публикации чата этот снимок бюджета тоже станет доступен читателям.</p></aside>')


async def monthly_snapshot(request, user):
    """Adapt the active monthly owner, never recreate its reads or policy."""
    try:
        from open_webui.models.functions import Functions
        from open_webui.utils.plugin import get_function_module_from_cache

        owner = await Functions.get_function_by_id(MONTHLY_ID)
        require(owner is not None and owner.type == "event" and owner.is_active is True)
        module, _, _ = await get_function_module_from_cache(request, MONTHLY_ID, function=owner)
        response = await module.read_monthly(request, user, None)
        require(response.status_code == 200)
        snapshot = json.loads(response.body)
        require(isinstance(snapshot, dict) and snapshot.get("user_id") == user.id)
        return render_monthly(snapshot)
    except HTTPException as error:
        if error.status_code in (400, 401, 403):
            raise ValueError("Cost details are unavailable for this selection.") from None
        return render_monthly(None)
    except Exception:
        return render_monthly(None)


def render(snapshot, monthly=None):
    as_of = (snapshot.as_of if snapshot is not None else datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = as_of.isoformat()
    content = (section("answer", "Выбранный ответ", snapshot.answer if snapshot else None)
               + section("chat", "Весь чат", snapshot.chat if snapshot else None))
    return ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
            'style-src \'unsafe-inline\'; script-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Стоимость: детали</title><style>body{font:14px system-ui;margin:16px;color:#222;'
            'background:white}main{max-width:100%;overflow:auto}table{border-collapse:collapse;width:100%;'
            'margin-top:12px}td,th{padding:6px;text-align:left;border-bottom:1px solid #ddd;overflow-wrap:anywhere}'
            'section{margin:18px 0}output{font-weight:600}p{line-height:1.5}</style></head><body>'
            '<main data-budget-cost-details="v1"><h1>Стоимость: детали</h1>'
            '<p>Начислено на момент снимка: '
            f'<time datetime="{escaped(stamp)}">{escaped(as_of.strftime("%Y-%m-%d %H:%M:%S UTC"))}</time>.</p>'
            '<p>Это текущие записи журнала, а не окончательная стоимость будущей или фоновой работы. '
            'Чтобы обновить данные, снова откройте действие «Стоимость: детали».</p>'
            + content + (monthly if monthly is not None else render_monthly(None))
            + '</main><script>' + HEIGHT_SCRIPT + '</script></body></html>')


class Action:
    async def action(self, body: dict, __user__=None, __request__=None, __model__=None):
        from open_webui.env import VERSION
        from open_webui.models.chats import Chats
        from open_webui.models.functions import Functions
        from open_webui.models.users import Users
        from open_webui.utils.auth import VERIFIED_USER_ROLES
        from open_webui.utils.session_pool import get_session

        require(VERSION == "0.12.2" and __request__ is not None
                and not getattr(__request__.state, "direct", False))
        require(isinstance(body, dict) and isinstance(__user__, dict))
        user_id = canonical_id(__user__.get("id"))
        chat_id, answer_id = canonical_id(body.get("chat_id")), canonical_id(body.get("id"))
        user = await Users.get_user_by_id(user_id)
        require(user is not None and user.id == user_id and user.role in VERIFIED_USER_ROLES)
        chat = await Chats.get_accessible_chat_by_id(chat_id, user, permission="read")
        require(chat is not None and chat.user_id == user.id)
        message = await Chats.get_message_by_id_and_message_id(chat_id, answer_id)
        require(isinstance(message, dict) and message.get("id") == answer_id
                and message.get("role") == "assistant" and (message.get("user_id") or chat.user_id) == user.id
                and isinstance(__model__, dict) and isinstance(body.get("model"), str)
                and message.get("model") == body["model"] == __model__.get("id"))
        owner = await Functions.get_function_by_id(FILTER_ID)
        require(owner is not None and owner.type == "filter" and owner.is_active is True)
        config = await Functions.get_function_valves_by_id(FILTER_ID) or {}
        snapshot = None
        try:
            snapshot = await read_cost_snapshot(await get_session(), base_url=config.get("ledger_base_url", ""),
                read_key=config.get("ledger_read_key", ""), user_id=user.id, root_chat_id=chat_id,
                root_answer_id=answer_id, wait_seconds=0)
        except CostReadError:
            pass
        if snapshot is not None:
            require(snapshot.user_id == user.id and snapshot.root_chat_id == chat_id
                    and snapshot.root_answer_id == answer_id)
        monthly = await monthly_snapshot(__request__, user)
        current_user = await Users.get_user_by_id(user.id)
        require(current_user is not None and current_user.id == user.id and current_user.role in VERIFIED_USER_ROLES)
        return (HTMLResponse(render(snapshot, monthly), headers={"Content-Disposition": "inline", "Cache-Control": "no-store"}),
                {"status": "success", "message": "Cost snapshot opened. Reopen the action to refresh."})
