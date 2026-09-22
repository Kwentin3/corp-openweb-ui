"""
title: OfficeCLI Auto Attach
author: Alpha Soft
version: 0.8.4-compact-context-experiment
required_open_webui_version: 0.9.6
description: Adds the existing OfficeCLI tool server only to explicitly configured direct Native chat models.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field


OFFICECLI_TOOL_ID = "server:officecli"
OFFICECLI_INSTRUCTION_MARKER = "[officecli-auto-attach-v3-compact]"
GEMINI_COMPATIBILITY_MARKER = "[officecli-gemini-compat-v2]"
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
    "models/gemini-3.5-flash-lite"
)
OFFICECLI_INSTRUCTION = (
    f"{OFFICECLI_INSTRUCTION_MARKER} OfficeCLI is available for DOCX, XLSX, and PPTX work. "
    "For a new file made from text, spreadsheet cells, or basic slide shapes, never call "
    "load_officecli_skill or get_officecli_help. Directly call the matching create operation once per "
    "requested file: DOCX uses create_office_document, XLSX uses create_office_spreadsheet, and PPTX "
    "uses create_office_presentation. Build commands from the request using these valid base shapes. "
    "DOCX markdown: {\"command\":\"add\",\"parent\":\"/body\",\"type\":\"markdown\","
    "\"props\":{\"markdown\":\"# Title\\n\\nContent\"}}; keep markdown inside props. "
    "XLSX cell: {\"command\":\"set\",\"path\":\"/Sheet1/A1\",\"props\":{\"value\":\"Text\"}}. For requested money, put \"numFmt\":\"#,##0 ₽\" in each price, amount, and total cell props; preserve every requested label such as Итого. Use formulas for requested calculations. Do not add unrequested titles, merged cells, column widths, or styling. "
    "PPTX: add every slide first with {\"command\":\"add\",\"parent\":\"/\",\"type\":\"slide\","
    "\"props\":{\"layout\":\"blank\"}}, then add each basic text shape with flat props such as {\"command\":\"add\",\"parent\":\"/slide[1]\",\"type\":\"shape\",\"props\":{\"text\":\"Title\",\"x\":\"2cm\",\"y\":\"3cm\",\"width\":\"29cm\",\"height\":\"3cm\"}}. For basic shapes, never use nested geometry or font objects. Every requested slide title, subtitle, list item, date, and phrase must appear as visible shape text; do not summarize or omit them. "
    "Do not substitute code, a recipe, or a refusal for the tool call. Finish only after the current "
    "create result contains result_file_id and the native attachment is present; if execution fails, "
    "report the failure. A successful create result is terminal: do not reopen, inspect, apply changes, call help, or recreate that new file in the same response. Return exactly its one attachment, then reply with one plain-language sentence naming that file; never echo tool JSON and never leave the final answer empty. For a file that was already attached by the user before this response, inspect it first and use the matching apply batch. "
    "Load only the format-specific skill or help needed for its exact existing structure, or for a new "
    "table, chart, or picture. Preserve unrelated content and never invent document paths."
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
            default=DEFAULT_TARGET_MODEL_IDS,
            description=(
                "Comma-separated direct model IDs allowed to receive OfficeCLI. "
                "Empty means disabled; keep specialized Workspace/Pipe models out."
            ),
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
        if OFFICECLI_TOOL_ID not in tool_ids:
            body["tool_ids"] = [*tool_ids, OFFICECLI_TOOL_ID]

        messages = body.get("messages")
        if isinstance(messages, list):
            _append_instruction(messages)

        return body
