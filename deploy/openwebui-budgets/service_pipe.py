"""
title: Employee budget service tasks
author: Corporate Open WebUI
version: 0.1.0
required_open_webui_version: 0.12.2
description: Guarded direct titles and native background tasks with separate source/target authorization.

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

from employee_budget_provenance import SERVICE_TASKS
from employee_budget_webui_model_binding import native_connection, service_configuration


FUNCTION_ID = "employee_budget_service"
TASK = "title_generation"
TITLE_PATH = "/api/v1/tasks/title/completions"
MAIN_PATHS = frozenset({"/api/chat/completions", "/api/v1/chat/completions"})


class ServiceTaskError(ValueError):
    """Fixed safe code; never return native exceptions, URLs or credentials."""

    def __init__(self, code):
        self.code = code
        super().__init__("Service task could not be verified (" + code + ").")


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
    background = scope.get("path") in MAIN_PATHS
    require(scope.get("method") == "POST" and (
        scope.get("path") == TITLE_PATH and task == TASK
        or background and type(task) is str and task in SERVICE_TASKS), "unsupported_task")
    require(not getattr(request.state, "direct", False) and not getattr(request.state, "internal", False)
            and not getattr(request.state, "bypass_filter", False)
            and not getattr(request.state, "bypass_system_prompt", False)
            and not hasattr(request, "base_model_id"), "unsupported_context")
    require(isinstance(actor, dict) and isinstance(task_body, dict) and isinstance(metadata, dict),
            "invalid_context")
    user_id, chat_id = canonical_id(actor.get("id")), canonical_id(task_body.get("chat_id"))
    require(metadata.get("task") == task and metadata.get("task_body") == task_body
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
    if background:
        inherited = getattr(request.state, "metadata", None)
        require(isinstance(inherited, dict) and "task" not in inherited and "task_body" not in inherited
                and inherited.get("user_id") == user_id and inherited.get("chat_id") == chat_id
                and inherited.get("direct") is False and inherited.get("internal") is False
                and inherited.get("automation_id") is None, "invalid_background_context")
        source = inherited.get("model")
        require(isinstance(source, dict) and source.get("owned_by") == "openai"
                and not source.get("pipe") and not source.get("arena")
                and source.get("id") != FUNCTION_ID and task_body.get("model") == source.get("id"),
                "unsupported_background_source_context")
        fields = {"model", "messages", "chat_id"}
        if task == "follow_up_generation":
            fields.add("message_id")
            canonical_id(task_body.get("message_id"))
        require(set(task_body) == fields and isinstance(task_body.get("messages"), list)
                and bool(task_body["messages"]), "invalid_background_context")
        require(metadata == {**inherited, "task": task, "task_body": task_body, "chat_id": chat_id},
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

    own = await Functions.get_function_valves_by_id(FUNCTION_ID)
    require(isinstance(own, dict), "configuration_unavailable")
    target = own.get("target_model_id")
    require(isinstance(target, str) and 0 < len(target) <= 256 and target == target.strip()
            and all(ord(char) >= 32 for char in target), "invalid_configuration")
    url, payer = await service_configuration(user_id, require=require)
    return target, url, payer


@dataclass(frozen=True)
class _Binding:
    configuration: tuple[str, str, str]
    model: dict
    secret: str = field(repr=False)
    wire_model: str
    source_model: dict | None = None


class Pipe:
    class Valves(BaseModel):
        target_model_id: str = Field(default="", description="Existing native OpenAI workspace model for service tasks.")

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
        source = None
        if request.scope.get("path") in MAIN_PATHS:
            require(not model.get("pipe"), "unsupported_background_target_pipe")
            source = copy.deepcopy(request.state.metadata.get("model"))
            require(isinstance(source, dict) and isinstance(source.get("id"), str) and bool(source["id"])
                    and request.app.state.MODELS.get(source["id"]) == source, "unsupported_background_source_cache")
            await check_model_access(user, source)
        await check_model_access(user, model)
        secret, wire = await native_connection({"model": target}, model, request, url, require=require)
        return _Binding(settings, model, secret, wire, source)

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
                and request.app.state.MODELS.get(binding.configuration[0]) == binding.model
                and (binding.source_model is None or (
                    request.state.metadata.get("model") == binding.source_model
                    and request.app.state.MODELS.get(binding.source_model["id"]) == binding.source_model)), "stale_context")
        target, _, payer = binding.configuration
        prepared["model"] = target
        # Native functions.py extracted this exact metadata before calling Pipe.
        # Restore its representation for the stock router/header owner.
        prepared["metadata"] = native_metadata
        carrier = prepared.get("litellm_metadata")
        require(carrier is None or isinstance(carrier, dict), "invalid_metadata")
        carrier = dict(carrier or {})
        carrier["owui_budget_provenance"] = encode_service_call(binding.secret,
            user_id=user_id, payer_id=payer, chat_id=chat_id, model=binding.wire_model, task=task)
        prepared["litellm_metadata"] = carrier
        result = await generate_chat_completion(request, prepared, user=user)
        require(not (isinstance(result, dict) and result.get("error"))
                and getattr(result, "status_code", 200) < 400, "native_task_failed")
        return result
