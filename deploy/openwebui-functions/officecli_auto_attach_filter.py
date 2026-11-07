"""
title: OfficeCLI Auto Attach
author: Alpha Soft
version: 2.2.0-native-office-composition
required_open_webui_version: 0.12.2
description: Adds the existing OfficeCLI tool server only to explicitly configured direct Native chat models.
"""

from __future__ import annotations

from collections.abc import Iterable
import json
import inspect
import re
from typing import Any

from pydantic import BaseModel, Field


OFFICECLI_TOOL_ID = "server:officecli"
CORPORATE_TOOL_IDS = ("corporate_document_delegation", "corporate_template_publication")
WORKFLOW_REQUEST_MARKER = "officecli_native_workflow"
PLAN_REQUIRED_TOOLS = {
    "create_office_document", "create_office_spreadsheet", "create_office_presentation",
    "run_sub_agent", "publish_template",
}
APPLY_TOOLS = {"apply_office_batch", "apply_office_spreadsheet_batch", "apply_office_presentation_batch"}
CONDITIONAL_PLAN_TOOLS = {"stage_chat_file", "publish_terminal_file"}
TERMINAL_TRANSFER_TOOL_ID = "terminal_file_transfer"
ARTIFACT_WORKFLOW_SKILL_ID = "artifact-workflow"
DEFAULT_TERMINAL_ID = "office-linux"
OFFICE_FILE_EXTENSIONS = (".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm")
OFFICECLI_INSTRUCTION_MARKER = "[officecli-native-workflow-v1]"
# Bootstrap defaults only; native Valves own the deployed, qualified model IDs.
# Specialized Workspace/Pipe models stay opt-in by omission.
DEFAULT_TARGET_MODEL_IDS = (
    "claude-opus-5,"
    "claude-sonnet-4-6,"
    "gpt-5.4-mini,"
    "models/gemini-3.5-flash,"
    "models/gemini-3.6-flash,"
    "gpt-5.6-luna,"
    "models/gemini-3.1-flash-lite,"
    "models/gemini-3.5-flash-lite,"
    "gpt-6-luna,"
    "gpt-6-sol,"
    "claude-opus-5-5"
)
OFFICECLI_INSTRUCTION = (
    f"{OFFICECLI_INSTRUCTION_MARKER} OfficeCLI reads/creates/edits DOCX, XLSX, PPTX. "
    "For manual CLI edits, use load_officecli_skill and get_officecli_help for installed syntax. "
    "Execute CLI guide examples through OfficeCLI API tools; Terminal is a separate environment and does not imply an installed OfficeCLI binary. "
    "User source-preservation requirements and tool schemas take precedence over generic guide examples. "
    "Preserve requested fields, notes and checklists; add no filler or unrequested cover/TOC. "
    "For saved notes, use export_answer_to_word with source_note_id to import the full text instead of retyping it into create commands. "
    "Use attached_files/list_chat_files IDs, not citations; explicit file_id for multiple inputs. Reads do not publish. "
    "create/apply save copies and return native attachments. Batches contain edits, not create/open/save/close. "
    "Before claiming readability, render the final DOCX with grid 2 and inspect every page. "
    "For explicit export, deliver after these checks; preserved placeholders and style warnings need no confirmation. "
    "For an attached PPTX template or previous version, edit its copy with apply_office_presentation_batch; blank decks require an independent request. "
    "If invalid, report concrete findings and offer a valid earlier source or copy repair; never silently replace the source. "
    "Before Terminal, check native add/from cloning for template-style slides. "
    "Compare slide objects via query/get and render; Terminal only for a named unsupported operation. Continue from the last successful result_file_id. "
    "Return result_file_id/download_url verbatim, without sandbox: or invented paths."
)


OFFICECLI_PUBLISH_TOOLS = {
    "create_office_document", "export_answer_to_word", "apply_office_batch",
    "create_office_spreadsheet", "apply_office_spreadsheet_batch",
    "create_office_presentation", "apply_office_presentation_batch",
    "publish_terminal_file",
}


def _returned_download_urls(output: list[Any]) -> set[str]:
    """Read successful native publication receipts from this assistant turn only."""
    calls = {
        item.get("call_id"): item.get("name") for item in output
        if isinstance(item, dict) and item.get("type") == "function_call"
        and item.get("name") in OFFICECLI_PUBLISH_TOOLS
        and item.get("status") == "completed"
        and isinstance(item.get("call_id"), str) and item["call_id"]
    }
    urls = set()
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "function_call_output":
            continue
        if item.get("call_id") not in calls or item.get("status") != "completed":
            continue
        blocks = item.get("output")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") != "input_text":
                continue
            try:
                receipt = json.loads(block.get("text", ""))
            except (ValueError, TypeError):
                continue
            if not isinstance(receipt, dict):
                continue
            if calls[item["call_id"]] == "publish_terminal_file" and receipt.get("status") != "published":
                continue
            file_id = receipt.get("result_file_id")
            native_file = receipt.get("result_file")
            if not isinstance(file_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,128}", file_id):
                continue
            if not isinstance(native_file, dict) or native_file.get("id") != file_id:
                continue
            url = receipt.get("download_url")
            if url == f"/api/v1/files/{file_id}/content":
                urls.add(url)
    return urls


def _repair_download_links(text: str, urls: set[str]) -> str:
    # Correct only the observed malformed Markdown destination. Do not infer a
    # file from its display name, alter unknown links, or rewrite tool evidence.
    for url in urls:
        text = text.replace(f"](sandbox:{url})", f"]({url})")
    return text


def _comma_separated_values(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _requires_native_plan(name: str, params: dict[str, Any], files: Any = ()) -> bool:
    if name in PLAN_REQUIRED_TOOLS:
        return True
    if name == "publish_terminal_file":
        return _has_office_file([{"name": params.get("path")}], set(OFFICE_FILE_EXTENSIONS))
    if name == "stage_chat_file":
        file_id = params.get("file_id")
        if not isinstance(file_id, str) or not isinstance(files, list):
            return False
        for item in files:
            if not isinstance(item, dict) or item.get("type", "file") != "file":
                continue
            native_file = item.get("file") if isinstance(item.get("file"), dict) else {}
            if file_id in (item.get("id"), item.get("url"), native_file.get("id")):
                if _has_office_file([item, native_file], set(OFFICE_FILE_EXTENSIONS)):
                    return True
        return False
    if name not in APPLY_TOOLS:
        return False
    commands = params.get("commands")
    # Only a single set on an existing, explicitly addressed object is atomic.
    return not (
        isinstance(commands, list) and len(commands) == 1
        and isinstance(commands[0], dict) and commands[0].get("command") == "set"
        and isinstance(commands[0].get("path"), str)
        and commands[0]["path"].strip() not in ("", "/")
    )


async def _require_active_native_tasks(chat_id: str, user_id: str) -> None:
    from open_webui.models.chats import Chats

    chat = await Chats.get_chat_by_id_and_user_id(chat_id, user_id)
    if chat and any(
        isinstance(task, dict) and task.get("status") in ("pending", "in_progress")
        and isinstance(task.get("content"), str) and task["content"].strip()
        for task in (chat.tasks or [])
    ):
        return
    raise ValueError("Create an active native Tasks plan with create_tasks before this Office operation.")


def _workflow_context(metadata: dict[str, Any], skill_id: str) -> None:
    if skill_id:
        context = metadata.setdefault("chat_context", {})
        mentioned_ids = context.setdefault("mentioned_skill_ids", [])
        if skill_id not in mentioned_ids:
            context["mentioned_skill_ids"] = [*mentioned_ids, skill_id]
    metadata[WORKFLOW_REQUEST_MARKER] = True


def _has_office_file(files: Any, extensions: set[str]) -> bool:
    if not isinstance(files, list):
        return False
    for item in files:
        if not isinstance(item, dict) or item.get("type", "file") != "file":
            continue
        name = item.get("name") or item.get("filename")
        if isinstance(name, str) and any(name.lower().endswith(ext) for ext in extensions):
            return True
    return False


def _has_instruction(messages: Iterable[Any]) -> bool:
    return any(
        isinstance(message, dict)
        and message.get("role") == "system"
        and isinstance(message.get("content"), str)
        and OFFICECLI_INSTRUCTION_MARKER in message["content"]
        for message in messages
    )


def _append_instruction(messages: list[Any]) -> None:
    if _has_instruction(messages):
        return

    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system" and isinstance(message.get("content"), str):
            message["content"] = f"{message['content'].rstrip()}\n\n{OFFICECLI_INSTRUCTION}"
            return

    messages.insert(0, {"role": "system", "content": OFFICECLI_INSTRUCTION})


class Filter:
    class Valves(BaseModel):
        workflow_profile_ids: str = Field(
            default="corporate-documents,corporate-template-author",
            description="Optional presets receiving the shared native workflow without direct OfficeCLI attachment; keep the bounded worker excluded.",
        )
        target_model_ids: str = Field(
            default=DEFAULT_TARGET_MODEL_IDS,
            description=(
                "Comma-separated direct model IDs allowed to receive OfficeCLI. "
                "Empty means disabled; keep specialized Workspace/Pipe models out."
            ),
        )
        priority: int = Field(default=0, description="Keep the standard filter order unless an admin has a reason to change it.")
        no_reasoning_model_ids: str = Field(
            default="gpt-5.6-luna,gpt-6-luna,gpt-6-sol",
            description=(
                "Models whose current Chat Completions provider requires reasoning_effort=none with tools. "
                "Applies whenever OfficeCLI is attached; explicit incompatible reasoning fails visibly."
            ),
        )
        terminal_transfer_tool_id: str = Field(
            default=TERMINAL_TRANSFER_TOOL_ID,
            description="Existing native Tool used only when an Office input file is present. Empty disables handoff.",
        )
        artifact_workflow_skill_id: str = Field(
            default=ARTIFACT_WORKFLOW_SKILL_ID,
            description="Existing native Skill loaded whenever this direct OfficeCLI route attaches. Empty disables automatic loading.",
        )
        default_terminal_id: str = Field(
            default=DEFAULT_TERMINAL_ID,
            description="System Terminal selected for Office inputs when the user did not select another one. Empty disables default selection.",
        )
        terminal_file_extensions: str = Field(
            default=",".join(OFFICE_FILE_EXTENSIONS),
            description="Comma-separated lower-case input extensions that activate the Linux handoff path.",
        )

    def __init__(self) -> None:
        self.valves = self.Valves()

    async def request(
        self, body: dict[str, Any], __metadata__: dict[str, Any] | None = None,
        __user__: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = __metadata__ or {}
        scoped_models = (_comma_separated_values(self.valves.target_model_ids)
                         | _comma_separated_values(self.valves.workflow_profile_ids))
        if (body.get("model") not in scoped_models
                or not metadata.get(WORKFLOW_REQUEST_MARKER) or metadata.get("task") is not None
                or not metadata.get("session_id") or not (__user__ or {}).get("id")):
            return body
        from open_webui.utils.chat_id import is_saved_chat_id
        from open_webui.utils.tools import get_async_tool_function_and_apply_extra_params

        chat_id, user_id = metadata.get("chat_id"), __user__["id"]
        if not is_saved_chat_id(chat_id):
            return body
        tools = metadata.get("tools", {})
        removed_specs = []
        for key, tool in list(tools.items()):
            spec = tool.get("spec", {})
            if (tool.get("tool_id") == "corporate_document_delegation"
                    and spec.get("name") == "run_parallel_sub_agents"):
                removed_specs.append(spec)
                del tools[key]
        if removed_specs and isinstance(body.get("tools"), list):
            remaining_names = {tool.get("spec", {}).get("name") for tool in tools.values()}
            removed_names = {spec["name"] for spec in removed_specs} - remaining_names
            body["tools"] = [schema for schema in body["tools"]
                             if not any(schema.get("function", schema) is spec for spec in removed_specs)
                             and schema.get("function", schema).get("name") not in removed_names]
        for name, tool in metadata.get("tools", {}).items():
            if name not in PLAN_REQUIRED_TOOLS | APPLY_TOOLS | CONDITIONAL_PLAN_TOOLS or tool.get("direct"):
                continue
            function = tool.get("callable")
            if not function or getattr(function, "_office_tasks_guard", False):
                continue
            original = getattr(function, "__function__", function)
            signature = inspect.signature(original)
            if name == "stage_chat_file" and "__files__" not in signature.parameters:
                parameters = list(signature.parameters.values())
                position = next((i for i, p in enumerate(parameters)
                                 if p.kind is inspect.Parameter.VAR_KEYWORD), len(parameters))
                parameters.insert(position, inspect.Parameter(
                    "__files__", inspect.Parameter.KEYWORD_ONLY, default=None,
                ))
                signature = signature.replace(parameters=parameters)

            def guard(original=original, signature=signature, name=name):
                async def guarded(*args, **kwargs):
                    params = dict(signature.bind_partial(*args, **kwargs).arguments)
                    # Native OpenAPI closures expose **kwargs, whereas local
                    # Tools expose named arguments. Both carry the same schema.
                    for key, parameter in signature.parameters.items():
                        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
                            params.update(params.pop(key, {}))
                    fresh_files = params.get("__files__")
                    files = fresh_files if isinstance(fresh_files, list) else metadata.get("files", [])
                    if _requires_native_plan(name, params, files):
                        await _require_active_native_tasks(chat_id, user_id)
                    if name == "stage_chat_file" and "__files__" not in inspect.signature(original).parameters:
                        kwargs.pop("__files__", None)
                    result = original(*args, **kwargs)
                    return await result if inspect.isawaitable(result) else result
                # Do not copy native __function__/__extra_params__ with wraps:
                # execute_tool_call must rebind fresh messages/files to THIS guard.
                guarded.__signature__ = signature
                guarded.__name__ = getattr(original, "__name__", name)
                guarded._office_tasks_guard = True
                return guarded

            tool["callable"] = await get_async_tool_function_and_apply_extra_params(
                guard(), getattr(function, "__extra_params__", {}),
            )
        return body

    async def outlet(
        self,
        body: dict[str, Any],
        __metadata__: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Adapt a proven file URL at the native response boundary, without I/O."""
        if (__metadata__ or {}).get("task") is not None:
            return body
        if body.get("model") not in _comma_separated_values(self.valves.target_model_ids):
            return body
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            return body
        message = messages[-1]
        if not isinstance(message, dict) or message.get("role") != "assistant":
            return body
        if not body.get("id") or message.get("id") != body["id"]:
            return body
        output = message.get("output")
        if not isinstance(output, list):
            return body
        urls = _returned_download_urls(output)
        if not urls:
            return body
        if isinstance(message.get("content"), str):
            message["content"] = _repair_download_links(message["content"], urls)
        # OpenWebUI 0.9.6 reserializes changed output to persisted content; update
        # only assistant prose, retaining original function calls and results.
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message" or item.get("role") != "assistant":
                continue
            for block in item.get("content", []):
                if isinstance(block, dict) and block.get("type") == "output_text" and isinstance(block.get("text"), str):
                    block["text"] = _repair_download_links(block["text"], urls)
        return body

    async def inlet(
        self,
        body: dict[str, Any],
        __metadata__: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Attach an already-authorized tool server before OpenWebUI resolves tool IDs."""
        metadata = __metadata__ if __metadata__ is not None else {}
        valves = getattr(self, "valves", self.Valves())
        target_model_ids = _comma_separated_values(valves.target_model_ids)

        # Fail closed: only named direct chat models opt in.  A normal OpenWebUI
        # chat does not set ``metadata.params.function_calling`` at all; treating
        # its absence as a non-native mode silently removed OfficeCLI from the
        # ordinary product path.
        direct_model = body.get("model") in target_model_ids
        workflow_profile = body.get("model") in _comma_separated_values(valves.workflow_profile_ids)
        if not direct_model and not workflow_profile:
            return body
        if metadata.get("task") is not None:
            return body

        # OpenWebUI preserves caller-provided OpenAI tools instead of resolving tool_ids.
        # Do not mutate that separate contract or suggest OfficeCLI is active there.
        if body.get("tools") is not None:
            return body

        if workflow_profile and not direct_model:
            if __metadata__ is not None:
                _workflow_context(metadata, valves.artifact_workflow_skill_id.strip())
            return body

        tool_ids = body.get("tool_ids")
        if tool_ids is None:
            tool_ids = []
        if not isinstance(tool_ids, list):
            return body

        office_input = _has_office_file(
            body.get("files"),
            {ext.lower() if ext.startswith(".") else f".{ext.lower()}"
             for ext in _comma_separated_values(valves.terminal_file_extensions)},
        )
        skill_ids = body.get("skill_ids")
        if office_input and skill_ids is not None and not isinstance(skill_ids, list):
            return body

        # The same provider restriction applies to every format, including new
        # files with no attachments. Preserve explicit reasoning choices.
        if body.get("model") in _comma_separated_values(valves.no_reasoning_model_ids):
            if body.get("reasoning_effort") not in (None, "none"):
                raise ValueError(
                    "This model's current API cannot combine reasoning with Office tools. "
                    "Select reasoning effort None or a model/API supporting reasoning with tools."
                )
            body["reasoning_effort"] = "none"

        # OpenWebUI 0.9.6 processes params before Filter inlets. Mutate its
        # shared metadata owner, which selects native file context and tool
        # execution later in this request. Do not reconstruct file context.
        if __metadata__ is not None:
            metadata.setdefault("params", {})["function_calling"] = "native"
            workflow_skill_id = valves.artifact_workflow_skill_id.strip()
            if workflow_skill_id:
                # OpenWebUI 0.12.2 resolves this shared context after inlets:
                # its native Skill owner loads the readable active snapshot,
                # rather than only listing a selected skill_ids manifest entry.
                # Activate on creation and follow-ups too; no user mention or
                # duplicate Skill text is added by this version-specific adapter.
                _workflow_context(metadata, workflow_skill_id)
            else:
                metadata[WORKFLOW_REQUEST_MARKER] = True

        body["tool_ids"] = list(tool_ids)
        for tool_id in (OFFICECLI_TOOL_ID, *CORPORATE_TOOL_IDS):
            if tool_id not in body["tool_ids"]:
                body["tool_ids"].append(tool_id)

        if office_input:
            tool_ids = body.get("tool_ids", tool_ids)
            transfer_tool_id = valves.terminal_transfer_tool_id.strip()
            if transfer_tool_id and transfer_tool_id not in tool_ids:
                body["tool_ids"] = [*tool_ids, transfer_tool_id]

            workflow_skill_id = valves.artifact_workflow_skill_id.strip()
            if workflow_skill_id:
                skill_ids = skill_ids or []
                if workflow_skill_id not in skill_ids:
                    body["skill_ids"] = [*skill_ids, workflow_skill_id]

            # Preserve an explicit user/model selection. For the default route,
            # also update the shared pre-0.9.6 metadata snapshot consumed by
            # local Tools; the middleware will later bind the same value into
            # its authoritative replacement metadata.
            if not body.get("terminal_id") and valves.default_terminal_id.strip():
                body["terminal_id"] = valves.default_terminal_id.strip()
                if __metadata__ is not None:
                    metadata["terminal_id"] = body["terminal_id"]

        messages = body.get("messages")
        if isinstance(messages, list):
            _append_instruction(messages)

        return body
