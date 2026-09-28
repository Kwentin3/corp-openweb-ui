"""
title: OfficeCLI Auto Attach
author: Alpha Soft
version: 2.0.1-verified-download-links
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
    "This adapter uses nonresident CLI execution: each create/apply saves before returning, so separate open/save/close calls are unnecessary. "
    "For a produced file, use its returned result_file_id and download_url verbatim; never prepend sandbox: or invent a path."
)


OFFICECLI_PUBLISH_TOOLS = {
    "create_office_document", "apply_office_batch",
    "create_office_spreadsheet", "apply_office_spreadsheet_batch",
    "create_office_presentation", "apply_office_presentation_batch",
}


def _returned_download_urls(output: list[Any]) -> set[str]:
    """Read successful native publication receipts from this assistant turn only."""
    calls = {
        item.get("call_id") for item in output
        if isinstance(item, dict) and item.get("type") == "function_call"
        and item.get("name") in OFFICECLI_PUBLISH_TOOLS
        and item.get("status") == "completed"
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

        messages = body.get("messages")
        if isinstance(messages, list):
            _append_instruction(messages)

        return body
