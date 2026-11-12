"""
title: My budget and chat cost
author: Corporate Open WebUI
version: 0.1.0
required_open_webui_version: 0.12.2
description: Read my current native monthly budget or the accrued cost of this chat.
"""

from __future__ import annotations

import json
from uuid import UUID

from employee_budget_cost_readback import read_cost_snapshot


FILTER_ID = "employee_budget_cost"
MONTHLY_ID = "employee_budget_monthly_view"


def require(condition):
    if not condition:
        raise ValueError("Budget data is unavailable in this context.")


def canonical_id(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    require(valid)
    return value


async def context(request, actor, metadata, task):
    """Bind self-only reads to native caller identity and an owned current chat."""
    from open_webui.env import VERSION
    from open_webui.models.chats import Chats
    from open_webui.models.users import Users
    from open_webui.utils.auth import VERIFIED_USER_ROLES

    require(VERSION == "0.12.2" and request is not None
            and isinstance(actor, dict) and isinstance(metadata, dict))
    require(not task and metadata.get("task") in (None, "")
            and not metadata.get("internal") and not metadata.get("direct")
            and not getattr(request.state, "direct", False)
            and not getattr(request.state, "internal", False))
    user_id = canonical_id(actor.get("id"))
    require(metadata.get("user_id") == user_id)
    user = await Users.get_user_by_id(user_id)
    require(user is not None and user.id == user_id and user.role in VERIFIED_USER_ROLES)
    chat_id = canonical_id(metadata.get("chat_id"))
    chat = await Chats.get_accessible_chat_by_id(chat_id, user, permission="read")
    require(chat is not None and chat.user_id == user.id)
    return user, chat_id


def unavailable(scope):
    return json.dumps({"status": "unavailable", "scope": scope, "spend_usd": None})


def select(source, fields):
    """Representation-only allowlist; missing source values stay unknown."""
    return {field: source.get(field) for field in fields}


class Tools:
    async def my_budget(self, __request__=None, __user__=None, __metadata__=None, __task__=None) -> str:
        """Read my current monthly budget, accounted spend, remaining balance, and model breakdown.

        Uses only the current native budget period, not arbitrary past dates.
        Null means unavailable or no configured limit; never infer zero from it.
        Accounted remaining balance does not guarantee admission of a future request.
        """
        try:
            from open_webui.models.functions import Functions
            from open_webui.utils.plugin import get_function_module_from_cache

            user, chat_id = await context(__request__, __user__, __metadata__, __task__)
            owner = await Functions.get_function_by_id(MONTHLY_ID)
            require(owner is not None and owner.type == "event" and owner.is_active is True)
            module, _, _ = await get_function_module_from_cache(__request__, MONTHLY_ID, function=owner)
            response = await module.read_monthly(__request__, user, None)
            require(response.status_code == 200)
            snapshot = json.loads(response.body)
            require(isinstance(snapshot, dict) and snapshot.get("user_id") == user.id
                    and isinstance(snapshot.get("models"), list))
            fields = ("budget_usd", "spend_usd", "remaining_usd", "budget_duration", "budget_reset_at",
                      "as_of", "expense_status", "expense_as_of", "expense_observation_scope")
            result = select(snapshot, fields)
            model_fields = ("cap_usd", "spend_usd", "remaining_usd", "budget_duration", "budget_reset_at",
                            "blocked", "pending", "expense_status", "expense_as_of")
            result["models"] = [{"model": model.get("label") or model["id"], **select(model, model_fields)}
                                for model in snapshot["models"]]
            fresh_user, fresh_chat = await context(__request__, __user__, __metadata__, __task__)
            require(fresh_user.id == user.id and fresh_chat == chat_id)
            return json.dumps({"status": "available", "scope": "current_month", "currency": "USD", **result})
        except Exception:
            return unavailable("current_month")

    async def current_chat_cost(self, __request__=None, __user__=None, __metadata__=None, __task__=None) -> str:
        """Read accrued USD cost and model breakdown for this owned current chat.

        This is a fresh ledger snapshot, not the final cost of ongoing or future work.
        Missing or unavailable accounting is unknown, never zero. Do not infer complete history.
        """
        try:
            from open_webui.models.functions import Functions
            from open_webui.utils.session_pool import get_session

            user, chat_id = await context(__request__, __user__, __metadata__, __task__)
            answer_id = canonical_id(__metadata__.get("message_id"))
            owner = await Functions.get_function_by_id(FILTER_ID)
            require(owner is not None and owner.type == "filter" and owner.is_active is True)
            config = await Functions.get_function_valves_by_id(FILTER_ID)
            require(isinstance(config, dict))
            snapshot = await read_cost_snapshot(await get_session(), base_url=config.get("ledger_base_url", ""),
                read_key=config.get("ledger_read_key", ""), user_id=user.id, root_chat_id=chat_id,
                root_answer_id=answer_id, wait_seconds=0)
            require(snapshot.user_id == user.id and snapshot.root_chat_id == chat_id
                    and snapshot.root_answer_id == answer_id)
            fresh_user, fresh_chat = await context(__request__, __user__, __metadata__, __task__)
            require(fresh_user.id == user.id and fresh_chat == chat_id)
            total = snapshot.chat
            return json.dumps({"status": "available" if total.spend is not None else "unknown",
                "scope": "current_chat", "currency": snapshot.currency, "as_of": snapshot.as_of.isoformat(),
                "spend_usd": format(total.spend, "f") if total.spend is not None else None,
                "models": [{"model": model.model, "spend_usd": format(model.spend, "f"), "calls": model.calls}
                           for model in total.models],
                "coverage": "accrued_native_ledger_rows", "final": False})
        except Exception:
            return unavailable("current_chat")
