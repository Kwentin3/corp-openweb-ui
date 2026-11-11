"""
title: Employee budget cost display
author: Corporate Open WebUI
version: 0.1.0
description: Sign native chat or authenticated API attribution; display saved-chat costs from the existing LiteLLM spend owner.
required_open_webui_version: 0.12.2

Mount provenance.py as /app/backend/employee_budget_provenance.py and
cost_readback.py as /app/backend/employee_budget_cost_readback.py. Install this
file with the native Functions API as an active global Filter. Native connection
binding scopes signing to the managed gateway; model attachments remain compatible.
It is mandatory; UserValves changes only future display, never signing/budgets.
"""

from __future__ import annotations

from decimal import Decimal
import logging
import uuid

from pydantic import BaseModel, Field


ROOT_CAPSULE = "owui_budget_root"
ROOT_STATE = "_owui_budget_root"
OBSERVED_IDS = "_owui_budget_observed_provider_ids"
OBSERVED_CALL_IDS = "_owui_budget_observed_call_ids"
UNBOUND_RESPONSE = "_owui_budget_unbound_response"
ISSUED_SCOPE = "_owui_budget_current_scope"
SKIPPED_SCOPE = "_owui_budget_skipped_scope"
API_OPERATION = "_owui_budget_api_operation"
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


def replace_provenance(body, token):
    existing = body.get("litellm_metadata")
    require(existing is None or isinstance(existing, dict), "metadata_type")
    carrier = dict(existing or {})
    carrier.pop("spend_logs_metadata", None)
    carrier["owui_budget_provenance"] = token
    body["litellm_metadata"] = carrier


def money_text(amount):
    if 0 < amount < Decimal("0.00000001"):
        return "<$0.00000001"
    whole, _, fraction = format(amount, ".8f").partition(".")
    fraction = fraction.rstrip("0").ljust(2, "0")
    return "$" + whole + "." + fraction


async def native_answer(chat_id, answer_id, user, *, permission="write"):
    from open_webui.models.chats import Chats

    chat = await Chats.get_accessible_chat_by_id(chat_id, user, permission=permission)
    require(chat is not None, "chat_access")
    message = await Chats.get_message_by_id_and_message_id(chat_id, answer_id)
    require(isinstance(message, dict) and message.get("role") == "assistant"
            and (message.get("user_id") or chat.user_id) == user.id, "answer_owner")
    return message


async def completed_nonstream_call(body, metadata, scope, request):
    from open_webui.models.users import Users

    user_id = canonical_uuid(scope.get("user_id"), "user_id")
    chat_id = canonical_uuid(scope.get("root_chat_id"), "chat_id")
    answer_id = canonical_uuid(scope.get("root_answer_id"), "answer_id")
    require(request is not None and metadata.get("user_id") == user_id
            and body.get("chat_id") == chat_id and body.get("id") == answer_id
            and isinstance(scope.get("model"), str) and bool(scope["model"])
            and body.get("model") == scope["model"], "completed_answer_scope")
    user = await Users.get_user_by_id(user_id)
    require(user is not None and user.id == user_id and user.role in ("user", "admin"), "active_user")
    message = await native_answer(chat_id, answer_id, user)
    require(message.get("id") == answer_id and message.get("model") == scope["model"]
            and message.get("done") is True and message.get("error") is None, "completed_answer")
    return canonical_uuid(scope.get("call_id"), "call_id")


async def native_connection(body, model, request, ledger_base_url, *, allow_other_gateway=False):
    """Check existing owner output; leave transport/model selection to the router."""
    from employee_budget_webui_model_binding import native_connection as bind

    return await bind(body, model, request, ledger_base_url, require=require,
                      allow_other_gateway=allow_other_gateway)


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=1000, description="Run after filters that prepare model context.")
        ledger_base_url: str = Field(default="", description="Existing LiteLLM root URL, without /v1.")
        # Native Functions stores Valves.model_dump() as JSON; SecretStr is not
        # JSON-serializable on that path. This admin-only value is never UserValves.
        ledger_read_key: str = Field(default="", description="Native viewer key restricted to the session spend route.",
                                     json_schema_extra={"format": "password", "writeOnly": True})
        # Functions Valves require the current admin role. Tool Valves also
        # permit their owner after demotion, so a management key cannot live there.
        ledger_admin_key: str = Field(default="", description="Native budget management key; current administrators only.",
                                      json_schema_extra={"format": "password", "writeOnly": True})
        default_budget_template: dict | None = Field(default=None,
            description="Explicit monthly budget/share template for new employees; never rewrites existing budgets.")
        provider_balance_snapshots: dict = Field(default_factory=dict,
            description="Last manually checked provider balances; informational only, never spend or budget state.")
        service_payer_id: str = Field(default="",
            description="Native service budget identity; used only by qualified signed service tasks.")
        read_wait_seconds: float = Field(default=8.0, ge=0, le=10)

    class UserValves(BaseModel):
        enabled: bool = Field(default=True, description="Show newly confirmed response/chat costs. Accounting and limits always apply.")

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = False

    async def request(self, body: dict, __user__: dict = None, __metadata__: dict = None,
                      __request__=None, __model__: dict = None) -> dict:
        from employee_budget_provenance import decode_api_call, decode_call, decode_root, encode_api_call, encode_call, encode_root
        from open_webui.env import VERSION
        from open_webui.models.users import Users

        metadata = __metadata__
        require(isinstance(metadata, dict) and __request__ is not None and isinstance(__user__, dict), "server_context")
        metadata.pop(SKIPPED_SCOPE, None)
        require(isinstance(__model__, dict) and __model__.get("id") == body.get("model"), "model_owner")
        task = metadata.get("task")
        # Task metadata belongs to the native dispatch, never the provider body.
        # An arbitrary task name must not exempt a managed personal call.
        auxiliary = (getattr(__request__.state, "metadata", None) is metadata
                     and isinstance(task, str)
                     and task in {"title_generation", "follow_up_generation", "tags_generation",
                                  "emoji_generation", "query_generation", "image_prompt_generation",
                                  "autocomplete_generation", "function_calling", "moa_response_generation"})
        if __model__.get("owned_by") != "openai" or __model__.get("pipe") or auxiliary:
            metadata[SKIPPED_SCOPE] = True
            metadata.pop(ISSUED_SCOPE, None)
            return body
        binding = await native_connection(body, __model__, __request__, self.valves.ledger_base_url,
                                          allow_other_gateway=True)
        if binding is None:
            metadata[SKIPPED_SCOPE] = True
            metadata.pop(ISSUED_SCOPE, None)
            return body
        require(VERSION == "0.12.2", "unsupported_webui_version")
        require(metadata.get("task") in (None, "", "sub_agent") and not metadata.get("direct")
                and not getattr(__request__.state, "direct", False), "unsupported_task_or_direct")
        user_id = canonical_uuid(__user__.get("id"), "user_id")
        require(metadata.get("user_id") == user_id, "authenticated_user")
        user = await Users.get_user_by_id(user_id)
        require(user is not None and user.role in ("user", "admin"), "active_user")
        # Native API auth owns this principal. An unsaved operation is never a chat.
        if (getattr(__request__.state, "auth_type", None) == "api_key"
                and metadata.get("chat_id") in (None, "") and metadata.get("message_id") in (None, "")):
            require(getattr(getattr(__request__.state, "user", None), "id", None) == user_id
                    and getattr(__request__.state, "metadata", None) is metadata
                    and metadata.get("task") in (None, "")
                    and metadata.get("internal") in (None, False)
                    and getattr(__request__.state, "internal", False) is False
                    and not any(metadata.get(name) for name in (
                        "user_message_id", "assistant_message_id", "automation_id", "session_id")), "api_context")
            operation = getattr(__request__.state, API_OPERATION, None)
            if operation is None:
                operation = str(uuid.uuid4())
                setattr(__request__.state, API_OPERATION, operation)
            operation = canonical_uuid(operation, "api_operation")
            secret, wire_model = binding
            token = encode_api_call(secret, user_id=user_id, operation_id=operation, model=wire_model)
            claims = decode_api_call(token, secret, user_id=user_id, model=wire_model)
            replace_provenance(body, token)
            metadata[ISSUED_SCOPE] = {"category": "api", "user_id": user_id,
                "operation_id": operation, "call_id": claims["jti"], "model": wire_model}
            return body
        chat_id = canonical_uuid(metadata.get("chat_id"), "chat_id")
        answer_id = canonical_uuid(metadata.get("message_id"), "answer_id")
        message = await native_answer(chat_id, answer_id, user)
        if metadata.get("task") != "sub_agent":
            require(message.get("model") == body.get("model"), "answer_model")
        secret, wire_model = binding

        context = metadata.get("chat_context")
        require(isinstance(context, dict), "chat_context")
        if metadata.get("task") == "sub_agent":
            capsule = context.get(ROOT_CAPSULE)
            require(isinstance(capsule, str) and bool(capsule)
                    and getattr(__request__.state, ROOT_STATE, None) == capsule
                    and getattr(__request__.state, "metadata", None) is metadata,
                    "delegated_parent")
            root = decode_root(capsule, secret)
            require(root["sub"] == user_id and root["root_chat_id"] == chat_id
                    and root["root_answer_id"] == answer_id, "delegated_parent")
            # The community Tool copies the parent request. Restore the native
            # worker Model record default instead of inheriting its parent's base.
            if hasattr(__request__, "base_model_id"):
                delattr(__request__, "base_model_id")
                secret, wire_model = await native_connection(body, __model__, __request__, self.valves.ledger_base_url)
                require(decode_root(capsule, secret) == root, "delegated_connection")
            root_chat_id, root_answer_id = chat_id, answer_id
        elif metadata.get("internal") is True:
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
            setattr(__request__.state, ROOT_STATE, context[ROOT_CAPSULE])

        # Replace client-carried scope. Existing model messages/tools/params stay untouched.
        token = encode_call(secret, user_id=user_id,
            chat_id=chat_id, answer_id=answer_id, root_chat_id=root_chat_id,
            root_answer_id=root_answer_id, model=wire_model)
        claims = decode_call(token, secret, user_id=user_id, model=wire_model)
        replace_provenance(body, token)
        metadata[ISSUED_SCOPE] = {"user_id": user_id, "root_chat_id": root_chat_id,
                                  "root_answer_id": root_answer_id, "call_id": claims["jti"],
                                  "model": body["model"], "nonstream": body.get("stream") is False}
        return body

    async def stream(self, event: dict, __metadata__: dict = None) -> dict:
        metadata = __metadata__
        if (not isinstance(metadata, dict) or metadata.get(SKIPPED_SCOPE) is True or ISSUED_SCOPE not in metadata
                or isinstance(metadata[ISSUED_SCOPE], dict) and metadata[ISSUED_SCOPE].get("category") == "api"):
            return event
        identifier = None
        if event.get("object") == "chat.completion.chunk":
            identifier = event.get("id")
        elif str(event.get("type", "")).startswith("response."):
            response = event.get("response")
            if not isinstance(response, dict) or "id" not in response:
                return event
            identifier = response["id"]
            try:
                require(isinstance(identifier, str) and 0 < len(identifier) <= 1024
                        and not any(char.isspace() for char in identifier), "response_id")
                scope = metadata[ISSUED_SCOPE]
                call_id = canonical_uuid(scope.get("call_id") if isinstance(scope, dict) else None, "call_id")
            except ValueError:
                metadata[UNBOUND_RESPONSE] = True
                return event
            # Native Responses encrypts advertised IDs after detaching logging's
            # copy. Only this dispatch's server-issued nonce binds its ledger row.
            observed = metadata.setdefault(OBSERVED_CALL_IDS, [])
            if not isinstance(observed, list) or len(observed) >= 1000 and call_id not in observed:
                metadata[UNBOUND_RESPONSE] = True
            elif call_id not in observed:
                observed.append(call_id)
            return event
        if isinstance(identifier, str) and 0 < len(identifier) <= 1024 and not any(char.isspace() for char in identifier):
            observed = metadata.setdefault(OBSERVED_IDS, [])
            if identifier not in observed:
                require(len(observed) < 1000, "observed_call_bound")
                observed.append(identifier)
        return event

    async def outlet(self, body: dict, __user__: dict = None, __metadata__: dict = None,
                     __request__=None, __event_emitter__=None, __model__: dict = None) -> dict:
        if not display_enabled(__user__) or not __event_emitter__:
            return body
        metadata = __metadata__ or {}
        if metadata.get(SKIPPED_SCOPE) is True:
            return body
        if metadata.get("task") not in (None, "") or metadata.get("internal") is True:
            return body
        scope = metadata.get(ISSUED_SCOPE)
        if isinstance(scope, dict) and scope.get("category") == "api":
            return body
        # Native chat_completed builds fresh server metadata on its separate
        # outlet request. Classify that model again without inventing a scope.
        if scope is None and __request__ is not None and isinstance(__model__, dict) \
                and __model__.get("id") == body.get("model"):
            if __model__.get("owned_by") != "openai" or __model__.get("pipe"):
                return body
            try:
                if await native_connection(body, __model__, __request__, self.valves.ledger_base_url,
                                            allow_other_gateway=True) is None:
                    return body
            except Exception:
                # An unverifiable managed route retains the existing optional
                # unavailable feedback, without failing a completed answer.
                pass
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
                observed_call_ids = metadata.get(OBSERVED_CALL_IDS, [])
                if scope.get("nonstream") is True:
                    try:
                        call_id = await completed_nonstream_call(body, metadata, scope, __request__)
                        require(isinstance(observed_call_ids, list), "observed_calls")
                        # A native saved terminal outlet confirms this logical call,
                        # not a physical provider dispatch or a settled expense.
                        observed_call_ids = [*observed_call_ids, call_id]
                    except Exception:
                        # Optional display must not fail the completed answer when
                        # its current native access/terminal state cannot be read.
                        raise CostReadError("completed_answer_unverified") from None
                snapshot = await read_cost_snapshot(await get_session(),
                    base_url=self.valves.ledger_base_url,
                    read_key=self.valves.ledger_read_key,
                    user_id=scope["user_id"], root_chat_id=scope["root_chat_id"],
                    root_answer_id=scope["root_answer_id"],
                    observed_request_ids=metadata.get(OBSERVED_IDS, []),
                    observed_call_ids=observed_call_ids,
                    wait_seconds=self.valves.read_wait_seconds)
                if snapshot.answer.spend is not None and snapshot.chat.spend is not None:
                    description = f"Ответ: {money_text(snapshot.answer.spend)} · Чат: {money_text(snapshot.chat.spend)}"
                    description += " · на " + snapshot.as_of.strftime("%H:%M:%S UTC")
                    description += " · начислено на сейчас"
                    if snapshot.pending or metadata.get(UNBOUND_RESPONSE) is True:
                        description += ", учёт обновляется"
            except CostReadError as error:
                log.warning("Budget cost readback unavailable: %s", error.code)
                if error.code in ("usage_unavailable", "accounting_unavailable"):
                    description = "Расход неизвестен. Обратитесь к администратору."
        await __event_emitter__({"type": "status", "data": {
            "action": "employee_budget_cost", "description": description, "done": True,
        }})
        return body
