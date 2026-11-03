"""
title: Employee budget service title task
author: Corporate Open WebUI
version: 0.1.0
required_open_webui_version: 0.12.2
description: Guarded direct native title tasks only; automatic background tasks are not qualified.

Install as native Function employee_budget_service only after isolated proof.
Native LiteLLM owns service payer keys/caps/spend; this Pipe only validates the
native task boundary, signs attribution and reuses native chat dispatch once.
Existing employee_budget_cost Function Valves own common service configuration.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from uuid import UUID

from pydantic import BaseModel, Field

from employee_budget_webui_model_binding import native_connection


FUNCTION_ID = "employee_budget_service"
TASK = "title_generation"
TITLE_PATH = "/api/v1/tasks/title/completions"


class ServiceTaskError(ValueError):
    """Fixed safe code; never return native exceptions, URLs or credentials."""

    def __init__(self, code):
        self.code = code
        super().__init__("Service title task could not be verified (" + code + ").")


def require(condition, code):
    if not condition:
        raise ServiceTaskError(code)


def canonical_id(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    require(valid, "invalid_context")
    return value


def native_context(request, actor, task, task_body, metadata):
    from open_webui.env import VERSION

    require(VERSION == "0.12.2" and request is not None, "unsupported_context")
    scope = getattr(request, "scope", {})
    require(scope.get("path") == TITLE_PATH and scope.get("method") == "POST"
            and task == TASK, "unsupported_task")
    require(not getattr(request.state, "direct", False) and not getattr(request.state, "internal", False)
            and not getattr(request.state, "bypass_filter", False)
            and not getattr(request.state, "bypass_system_prompt", False)
            and not hasattr(request, "base_model_id"), "unsupported_context")
    require(isinstance(actor, dict) and isinstance(task_body, dict) and isinstance(metadata, dict),
            "invalid_context")
    user_id, chat_id = canonical_id(actor.get("id")), canonical_id(task_body.get("chat_id"))
    require(metadata.get("task") == TASK and metadata.get("task_body") == task_body
            and metadata.get("chat_id") == chat_id
            and metadata.get("user_id") in (None, user_id)
            and not metadata.get("direct") and not metadata.get("internal"), "invalid_context")
    if hasattr(request.state, "metadata"):
        inherited = request.state.metadata
        # utils.chat merges state metadata over the delegated payload. Reject
        # any override that would change the exact task context after signing.
        require(isinstance(inherited, dict)
                and all(key in metadata and metadata[key] == value for key, value in inherited.items()),
                "conflicting_metadata")
    return user_id, chat_id


async def authorized_actor(user_id, chat_id):
    from open_webui.models.chats import Chats
    from open_webui.models.users import Users

    user = await Users.get_user_by_id(user_id)
    require(user is not None and user.id == user_id and user.role in ("user", "admin"), "active_user_required")
    chat = await Chats.get_accessible_chat_by_id(chat_id, user, permission="write")
    require(chat is not None and chat.id == chat_id and chat.user_id == user_id, "chat_access_denied")
    # The Chat ACL read awaited native state; do not dispatch using an actor
    # that was disabled or replaced while that read was pending.
    user = await Users.get_user_by_id(user_id)
    require(user is not None and user.id == user_id and user.role in ("user", "admin"), "active_user_required")
    return user


async def configuration(user_id):
    from open_webui.models.functions import Functions
    from open_webui.models.users import Users

    own = await Functions.get_function_valves_by_id(FUNCTION_ID)
    common = await Functions.get_function_valves_by_id("employee_budget_cost")
    require(isinstance(own, dict) and isinstance(common, dict), "configuration_unavailable")
    target, url = own.get("target_model_id"), common.get("ledger_base_url")
    require(isinstance(target, str) and 0 < len(target) <= 256 and target == target.strip()
            and all(ord(char) >= 32 for char in target)
            and isinstance(url, str) and bool(url) and url == url.strip(), "invalid_configuration")
    payer = canonical_id(common.get("service_payer_id"))
    require(payer != user_id, "invalid_configuration")
    # Native Users returns None only for an absent primary key; lookup errors
    # propagate. Another WebUI employee must never become the service counter.
    require(await Users.get_user_by_id(payer) is None, "personal_payer_forbidden")
    return target, url, payer


@dataclass(frozen=True)
class _Binding:
    configuration: tuple[str, str, str]
    model: dict
    secret: str = field(repr=False)
    wire_model: str


class Pipe:
    class Valves(BaseModel):
        target_model_id: str = Field(default="", description="Existing native OpenAI workspace model for direct title tasks.")

    def __init__(self):
        self.valves = self.Valves()

    async def _binding(self, request, user_id, chat_id):
        from open_webui.utils.models import check_model_access

        user = await authorized_actor(user_id, chat_id)
        settings = await configuration(user_id)
        target, url, _ = settings
        require(not self.valves.target_model_id or self.valves.target_model_id == target, "stale_configuration")
        model = copy.deepcopy(request.app.state.MODELS.get(target))
        require(isinstance(model, dict) and model.get("id") == target, "model_unavailable")
        await check_model_access(user, model)
        secret, wire = await native_connection({"model": target}, model, request, url, require=require)
        return _Binding(settings, model, secret, wire)

    async def pipe(self, body: dict, __user__: dict = None, __metadata__: dict = None,
                   __request__=None, __task__=None, __task_body__=None):
        try:
            return await self._pipe(body, __user__, __metadata__, __request__, __task__, __task_body__)
        except ServiceTaskError:
            raise
        except Exception:
            raise ServiceTaskError("native_task_unavailable") from None

    async def _pipe(self, body, actor, metadata, request, task, task_body):
        from employee_budget_provenance import encode_service_call
        from open_webui.utils.chat import generate_chat_completion

        user_id, chat_id = native_context(request, actor, task, task_body, metadata)
        require(isinstance(body, dict) and body.get("model") == FUNCTION_ID
                and body.get("stream") is False, "invalid_task_body")
        require("metadata" not in body or body["metadata"] == metadata, "conflicting_metadata")
        prepared = copy.deepcopy(body)
        native_metadata = copy.deepcopy(metadata)
        cached_target = self.valves.target_model_id
        binding = await self._binding(request, user_id, chat_id)
        fresh = await self._binding(request, user_id, chat_id)
        require(fresh == binding and await configuration(user_id) == binding.configuration, "stale_configuration")
        user = await authorized_actor(user_id, chat_id)
        require(native_context(request, actor, task, task_body, metadata) == (user_id, chat_id)
                and body == prepared and metadata == native_metadata
                and self.valves.target_model_id == cached_target
                and request.app.state.MODELS.get(binding.configuration[0]) == binding.model, "stale_context")
        target, _, payer = binding.configuration
        prepared["model"] = target
        # Native functions.py extracted this exact metadata before calling Pipe.
        # Restore its representation for the stock router/header owner.
        prepared["metadata"] = native_metadata
        carrier = prepared.get("litellm_metadata")
        require(carrier is None or isinstance(carrier, dict), "invalid_metadata")
        carrier = dict(carrier or {})
        carrier["owui_budget_provenance"] = encode_service_call(binding.secret,
            user_id=user_id, payer_id=payer, chat_id=chat_id, model=binding.wire_model, task=TASK)
        prepared["litellm_metadata"] = carrier
        result = await generate_chat_completion(request, prepared, user=user)
        require(not (isinstance(result, dict) and result.get("error"))
                and getattr(result, "status_code", 200) < 400, "native_task_failed")
        return result
