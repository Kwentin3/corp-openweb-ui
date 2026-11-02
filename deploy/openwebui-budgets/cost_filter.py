"""
title: Employee budget cost display
author: Corporate Open WebUI
version: 0.1.0
description: Sign native chat attribution and display costs from the existing LiteLLM spend owner.
required_open_webui_version: 0.12.2

Mount provenance.py as /app/backend/employee_budget_provenance.py and
cost_readback.py as /app/backend/employee_budget_cost_readback.py. Install this
file with the native Functions API and attach its stable ID to managed models.
It is mandatory; UserValves changes only future display, never signing/budgets.
"""

from __future__ import annotations

from decimal import Decimal
import logging
import uuid

from pydantic import BaseModel, Field


ROOT_CAPSULE = "owui_budget_root"
OBSERVED_IDS = "_owui_budget_observed_provider_ids"
ISSUED_SCOPE = "_owui_budget_current_scope"
log = logging.getLogger(__name__)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError("Budget context could not be verified (" + code + ").")


def canonical_uuid(value, code):
    try:
        parsed = str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Budget context could not be verified (" + code + ").") from None
    require(parsed == value, code)
    return parsed


def display_enabled(user):
    valves = (user or {}).get("valves")
    return valves.get("enabled", True) if isinstance(valves, dict) else getattr(valves, "enabled", True)


def money_text(amount):
    if 0 < amount < Decimal("0.00000001"):
        return "<$0.00000001"
    whole, _, fraction = format(amount, ".8f").partition(".")
    fraction = fraction.rstrip("0").ljust(2, "0")
    return "$" + whole + "." + fraction


def has_delegation(message):
    # The current outlet has no controller-owned durable child-settlement receipt.
    # Keep delegated/background cost a visibly provisional accrued amount.
    return any(isinstance(item, dict) and item.get("type") == "function_call"
               and item.get("name") == "delegate_task" for item in message.get("output", []))


async def native_answer(chat_id, answer_id, user, *, permission="write"):
    from open_webui.models.chats import Chats

    chat = await Chats.get_accessible_chat_by_id(chat_id, user, permission=permission)
    require(chat is not None, "chat_access")
    message = await Chats.get_message_by_id_and_message_id(chat_id, answer_id)
    require(isinstance(message, dict) and message.get("role") == "assistant"
            and (message.get("user_id") or chat.user_id) == user.id, "answer_owner")
    return message


async def native_connection(body, model, request, ledger_base_url):
    """Check existing owner output; leave transport/model selection to the router."""
    from employee_budget_webui_model_binding import native_connection as bind

    return await bind(body, model, request, ledger_base_url, require=require)


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=1000, description="Run after filters that prepare model context.")
        ledger_base_url: str = Field(default="", description="Existing LiteLLM root URL, without /v1.")
        # Native Functions stores Valves.model_dump() as JSON; SecretStr is not
        # JSON-serializable on that path. This admin-only value is never UserValves.
        ledger_read_key: str = Field(default="", description="Native viewer key restricted to the session spend route.",
                                     json_schema_extra={"format": "password", "writeOnly": True})
        read_wait_seconds: float = Field(default=8.0, ge=0, le=10)

    class UserValves(BaseModel):
        enabled: bool = Field(default=True, description="Show newly confirmed response/chat costs. Accounting and limits always apply.")

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = False

    async def request(self, body: dict, __user__: dict = None, __metadata__: dict = None,
                      __request__=None, __model__: dict = None) -> dict:
        from employee_budget_provenance import decode_root, encode_call, encode_root
        from open_webui.env import VERSION
        from open_webui.models.users import Users

        require(VERSION == "0.12.2", "unsupported_webui_version")
        metadata = __metadata__
        require(isinstance(metadata, dict) and __request__ is not None and isinstance(__user__, dict), "server_context")
        require(metadata.get("task") in (None, "") and not metadata.get("direct")
                and not getattr(__request__.state, "direct", False), "unsupported_task_or_direct")
        user_id = canonical_uuid(__user__.get("id"), "user_id")
        require(metadata.get("user_id") == user_id, "authenticated_user")
        user = await Users.get_user_by_id(user_id)
        require(user is not None and user.role in ("user", "admin"), "active_user")
        chat_id = canonical_uuid(metadata.get("chat_id"), "chat_id")
        answer_id = canonical_uuid(metadata.get("message_id"), "answer_id")
        message = await native_answer(chat_id, answer_id, user)
        require(message.get("model") == body.get("model"), "answer_model")
        secret, wire_model = await native_connection(body, __model__, __request__, self.valves.ledger_base_url)

        context = metadata.get("chat_context")
        require(isinstance(context, dict), "chat_context")
        if metadata.get("internal") is True:
            require(getattr(__request__.state, "internal", False) is True, "internal_request")
            capsule = context.get(ROOT_CAPSULE)
            require(isinstance(capsule, str) and bool(capsule), "parent_capsule")
            root = decode_root(capsule, secret)
            require(root["sub"] == user_id, "parent_user")
            root_chat_id, root_answer_id = root["root_chat_id"], root["root_answer_id"]
            await native_answer(root_chat_id, root_answer_id, user)
        else:
            # A resumed parent/new answer owns new IDs; imported Chat.meta is not authority.
            root_chat_id, root_answer_id = chat_id, answer_id
            context[ROOT_CAPSULE] = encode_root(secret, user_id=user_id,
                root_chat_id=root_chat_id, root_answer_id=root_answer_id)

        # Replace client-carried scope. Existing model messages/tools/params stay untouched.
        existing = body.get("litellm_metadata")
        require(existing is None or isinstance(existing, dict), "metadata_type")
        carrier = dict(existing or {})
        carrier.pop("spend_logs_metadata", None)
        carrier["owui_budget_provenance"] = encode_call(secret, user_id=user_id,
            chat_id=chat_id, answer_id=answer_id, root_chat_id=root_chat_id,
            root_answer_id=root_answer_id, model=wire_model)
        body["litellm_metadata"] = carrier
        metadata[ISSUED_SCOPE] = {"user_id": user_id, "root_chat_id": root_chat_id,
                                  "root_answer_id": root_answer_id}
        return body

    async def stream(self, event: dict, __metadata__: dict = None) -> dict:
        metadata = __metadata__
        if not isinstance(metadata, dict) or ISSUED_SCOPE not in metadata:
            return event
        identifier = None
        if event.get("object") == "chat.completion.chunk":
            identifier = event.get("id")
        elif str(event.get("type", "")).startswith("response."):
            identifier = (event.get("response") or {}).get("id")
        if isinstance(identifier, str) and 0 < len(identifier) <= 1024 and not any(char.isspace() for char in identifier):
            observed = metadata.setdefault(OBSERVED_IDS, [])
            if identifier not in observed:
                require(len(observed) < 1000, "observed_call_bound")
                observed.append(identifier)
        return event

    async def outlet(self, body: dict, __user__: dict = None, __metadata__: dict = None,
                     __request__=None, __event_emitter__=None) -> dict:
        if not display_enabled(__user__) or not __event_emitter__:
            return body
        metadata = __metadata__ or {}
        if metadata.get("task") not in (None, "") or metadata.get("internal") is True:
            return body
        scope = metadata.get(ISSUED_SCOPE)
        description = "Стоимость ещё не подтверждена журналом учёта. Учёт и лимиты действуют."
        if isinstance(scope, dict):
            from employee_budget_cost_readback import CostReadError, read_cost_snapshot
            from open_webui.utils.session_pool import get_session

            if not (scope.get("user_id") == (__user__ or {}).get("id")
                    and scope.get("root_chat_id") == metadata.get("chat_id")
                    and scope.get("root_answer_id") == metadata.get("message_id")):
                # Do not query another scope or turn a completed model answer
                # into a failure because its optional display cannot be verified.
                await __event_emitter__({"type": "status", "data": {
                    "action": "employee_budget_cost", "description": description, "done": True,
                }})
                return body
            try:
                snapshot = await read_cost_snapshot(await get_session(),
                    base_url=self.valves.ledger_base_url,
                    read_key=self.valves.ledger_read_key,
                    user_id=scope["user_id"], root_chat_id=scope["root_chat_id"],
                    root_answer_id=scope["root_answer_id"],
                    observed_request_ids=metadata.get(OBSERVED_IDS, []),
                    wait_seconds=self.valves.read_wait_seconds)
                if snapshot.answer.spend is not None and snapshot.chat.spend is not None:
                    current = next((message for message in body.get("messages", [])
                                    if message.get("id") == scope["root_answer_id"]), {})
                    provisional = snapshot.pending or has_delegation(current)
                    description = f"Ответ: {money_text(snapshot.answer.spend)} · Чат: {money_text(snapshot.chat.spend)}"
                    description += " · на " + snapshot.as_of.strftime("%H:%M:%S UTC")
                    if provisional:
                        description += " · начислено на сейчас, учёт обновляется"
            except CostReadError as error:
                log.warning("Budget cost readback unavailable: %s", error.code)
        await __event_emitter__({"type": "status", "data": {
            "action": "employee_budget_cost", "description": description, "done": True,
        }})
        return body
