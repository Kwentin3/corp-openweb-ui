"""
title: OfficeCLI Auto Attach
author: Alpha Soft
version: 0.6.0
required_open_webui_version: 0.9.6
description: Adds the existing OfficeCLI tool server only to explicitly configured Native chat models.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field


OFFICECLI_TOOL_ID = "server:officecli"
OFFICECLI_INSTRUCTION_MARKER = "[officecli-auto-attach-v1]"
OFFICECLI_INSTRUCTION = (
    f"{OFFICECLI_INSTRUCTION_MARKER} OfficeCLI is available for DOCX, XLSX, and PPTX work. "
    "When a user asks to edit an attached DOCX, use the available OfficeCLI guidance and tools; "
    "when they ask to create a new DOCX from the discussion, use the same official guidance and "
    "create tool. For a DOCX table edit, obtain the table-row and table-cell help before applying a batch. "
    "For XLSX work, obtain the official Excel skill and relevant help before applying a batch. "
    "When reporting a calculated XLSX value after creating or editing a workbook, inspect the returned "
    "workbook and report its actual formula value instead of calculating it yourself. "
    "For PPTX work, obtain the official PPTX skill and relevant help before creating or editing a "
    "presentation; inspect an attached presentation before editing it and preserve its existing template "
    "and unaffected slides. When creating a PPTX, use a picture only if the user attached exactly one image "
    "to this chat; then set its source to attachment://image. Never invent a local path, URL, or data URI for "
    "a picture; otherwise create the presentation without one. "
    "For a follow-up OfficeCLI request in the same chat, use the result_file_id from "
    "the most recent successful OfficeCLI batch in the conversation as the source file; do not return to an "
    "older uploaded file. "
    "For an existing PPTX text change, use the official PPTX shape help and the "
    "shape inventory to identify the visible target by its current text and stable shape path; never "
    "guess a generic shape name. Change that existing shape rather than adding a competing overlay, preserve "
    "its geometry, and explicitly remove any superseded shape. After the batch, inspect the returned PPTX "
    "and verify that the requested text is in the intended shape and the replaced text is gone. Do not "
    "report completion until that verification and the execution tool return a result_file_id."
)


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
            default="",
            description="Comma-separated direct model IDs allowed to receive OfficeCLI. Empty means disabled.",
        )
        priority: int = Field(default=0, description="Keep the standard filter order unless an admin has a reason to change it.")

    def __init__(self) -> None:
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict[str, Any],
        __metadata__: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Attach an already-authorized tool server before OpenWebUI resolves tool IDs."""
        metadata = __metadata__ or {}
        valves = getattr(self, "valves", self.Valves())
        target_model_ids = _comma_separated_values(valves.target_model_ids)

        # Fail closed: only named direct chat models in their configured Native mode opt in.
        if not target_model_ids or body.get("model") not in target_model_ids:
            return body
        if metadata.get("task") is not None:
            return body
        if metadata.get("params", {}).get("function_calling") != "native":
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
        if OFFICECLI_TOOL_ID not in tool_ids:
            body["tool_ids"] = [*tool_ids, OFFICECLI_TOOL_ID]

        messages = body.get("messages")
        if isinstance(messages, list):
            _append_instruction(messages)

        return body
