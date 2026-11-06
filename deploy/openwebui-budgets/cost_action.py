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
from uuid import UUID

from fastapi.responses import HTMLResponse
from employee_budget_cost_readback import CostReadError, read_cost_snapshot


FILTER_ID = "employee_budget_cost"
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
            cells = "".join(f'<td data-field="{field}">{escaped(value)}</td>' for field, value in values.items())
            rows.append(f'<tr data-model="{escaped(model.model)}">{cells}</tr>')
        contents += ('<table><thead><tr><th>Модель</th><th>Вызовы</th><th>Вход</th><th>Выход</th>'
                     '<th>Всего токенов</th><th>USD</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>')
    return f'<section data-cost-scope="{kind}"><h2>{title}</h2>{contents}</section>'


def render(snapshot):
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
            + content + '</main><script>' + HEIGHT_SCRIPT + '</script></body></html>')


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
        return (HTMLResponse(render(snapshot), headers={"Content-Disposition": "inline", "Cache-Control": "no-store"}),
                {"status": "success", "message": "Cost snapshot opened. Reopen the action to refresh."})
