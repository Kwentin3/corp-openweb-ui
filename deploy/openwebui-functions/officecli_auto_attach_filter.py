"""
title: OfficeCLI Auto Attach
author: Alpha Soft
version: 2.1.0-native-terminal-handoff
required_open_webui_version: 0.9.6
description: Adds the existing OfficeCLI tool server only to explicitly configured direct Native chat models.
"""

from __future__ import annotations

from collections.abc import Iterable
import json
import re
from typing import Any

from pydantic import BaseModel, Field


OFFICECLI_TOOL_ID = "server:officecli"
TERMINAL_TRANSFER_TOOL_ID = "terminal_file_transfer"
ARTIFACT_WORKFLOW_SKILL_ID = "artifact-workflow"
DEFAULT_TERMINAL_ID = "office-linux"
OFFICE_FILE_EXTENSIONS = (".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm")
OFFICECLI_INSTRUCTION_MARKER = "[officecli-native-workflow-v1]"
# Keep the production default aligned with the current direct-model catalog.
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
    f"{OFFICECLI_INSTRUCTION_MARKER} OfficeCLI tools are available for reading, creating and editing DOCX, XLSX and PPTX. "
    "The get_officecli_help tool description includes the installed author's workflow for all Office tools. "
    "Use load_officecli_skill for official guides/references and get_officecli_help for command details. "
    "The installed documentation owns the workflow; tool schemas describe the file-transport mapping and its limits. "
    "Native attached_files entries and list_chat_files provide file IDs; text-retrieval citations are not a complete document structure. "
    "Use explicit file_id when multiple inputs are available. Reads do not publish files; create/apply work on copies and return native attachments. "
    "For an attached PPTX template or previous version, edit its copy with apply_office_presentation_batch; create a blank deck only for an explicitly independent presentation. "
    "For added template-style slides, check native OfficeCLI add/from cloning before Terminal. "
    "This adapter uses nonresident CLI execution: each create/apply saves before returning, so separate open/save/close calls are unnecessary. "
    "For a produced file, use its returned result_file_id and download_url verbatim; never prepend sandbox: or invent a path."
)


OFFICECLI_PUBLISH_TOOLS = {
    "create_office_document", "apply_office_batch",
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
            description="Existing native Skill loaded for Office input workflows. Empty disables automatic loading.",
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
        if not target_model_ids or body.get("model") not in target_model_ids:
            return body
        if metadata.get("task") is not None:
            return body

        # OpenWebUI preserves caller-provided OpenAI tools instead of resolving tool_ids.
        # Do not mutate that separate contract or suggest OfficeCLI is active there.
        if body.get("tools") is not None:
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

        if OFFICECLI_TOOL_ID not in tool_ids:
            body["tool_ids"] = [*tool_ids, OFFICECLI_TOOL_ID]

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
