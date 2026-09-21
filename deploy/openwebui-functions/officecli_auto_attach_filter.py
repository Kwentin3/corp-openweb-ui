"""
title: OfficeCLI Auto Attach
author: Alpha Soft
version: 0.7.3
required_open_webui_version: 0.9.6
description: Adds the existing OfficeCLI tool server only to explicitly configured direct Native chat models.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field


OFFICECLI_TOOL_ID = "server:officecli"
OFFICECLI_INSTRUCTION_MARKER = "[officecli-auto-attach-v2]"
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
    "For a new file, route by format: DOCX uses create_office_document, XLSX uses "
    "create_office_spreadsheet, and PPTX uses create_office_presentation. Call the operation; do not "
    "call load_officecli_skill or get_officecli_help first when a minimal new file can use the "
    "known-valid shapes below; reserve guidance calls for non-trivial structures. Do not "
    "substitute code or a recipe. Do not claim that a file was created unless the execution response "
    "contains result_file_id and the native attachment is present. If execution fails, report that "
    "failure instead of describing the intended file as complete. A successful OfficeCLI tool result "
    "returned during the current response is the receipt for the current execution, not evidence of an "
    "older test file. When every requested create operation returns result_file_id, state that creation "
    "succeeded and identify the attached files. "
    "When a user asks to edit an attached DOCX, use the available OfficeCLI guidance and tools; "
    "when they ask to create a minimal new DOCX from the discussion, immediately call the native "
    "create_office_document operation with output_name ending in .docx and this known-valid command "
    "shape: {\"command\":\"add\",\"parent\":\"/body\",\"type\":\"markdown\","
    "\"props\":{\"markdown\":\"# Title\\n\\nContent\"}}. "
    "Do not answer with a bash script, Python code, or a textual recipe in place of that operation. "
    "For a DOCX table edit, obtain the table-row and table-cell help before applying a batch. "
    "Treat the attached document as a fixed form unless the user explicitly asks to change its structure: "
    "use only paths that the inspection actually reports, never invent a /tbl[N]/tr[R] or /tc[C] path, "
    "never add rows to make a requested answer fit, and preserve headings, question labels, and unaffected cells. "
    "If the inspection does not expose a place for an answer, ask the user rather than guessing. "
    "For a new XLSX, call create_office_spreadsheet. A new workbook already contains Sheet1; address "
    "cells as /Sheet1/A1 (for example, {\"command\":\"set\",\"path\":\"/Sheet1/A1\","
    "\"props\":{\"value\":\"Example\"}}), never as /sheet[Sheet1]/cell[A1]. For an attached XLSX, "
    "inspect it and use apply_office_spreadsheet_batch. Obtain the official Excel skill and relevant "
    "help before any non-trivial batch. "
    "When reporting a calculated XLSX value after creating or editing a workbook, inspect the returned "
    "workbook and report its actual formula value instead of calculating it yourself. "
    "For a new PPTX, call create_office_presentation and add each slide at parent / before its content "
    "(first {\"command\":\"add\",\"parent\":\"/\",\"type\":\"slide\","
    "\"props\":{\"layout\":\"blank\"}}, then {\"command\":\"add\","
    "\"parent\":\"/slide[1]\",\"type\":\"shape\",\"props\":{\"text\":\"Example\","
    "\"x\":\"2cm\",\"y\":\"7cm\",\"width\":\"29cm\",\"height\":\"3cm\","
    "\"font\":\"Calibri\",\"size\":\"36\",\"bold\":\"true\","
    "\"align\":\"center\",\"color\":\"000000\"}}). "
    "Never use /presentation as the parent. For an attached "
    "PPTX, inspect it and use apply_office_presentation_batch. Obtain the official PPTX skill and "
    "relevant help before creating a non-trivial structure or editing a "
    "presentation; inspect an attached presentation before editing it and preserve its existing template "
    "and unaffected slides. If a new presentation contains a table, chart, or picture, obtain the matching "
    "pptx table, pptx chart, or pptx picture help before its create batch. For a PPTX table, use the exact "
    "official table-add data contract from that help to seed its cells; do not send guessed rNcN cell keys "
    "in a later table set command. In a new multi-slide PPTX batch, add every requested slide at the document "
    "root before adding content to that slide; do not address /slide[N] until its add command is earlier in the "
    "same batch. When creating a PPTX, use a picture only if the user attached exactly one image "
    "to this chat; then set its source to attachment://image. Never invent a local path, URL, or data URI for "
    "a picture; otherwise create the presentation without one. "
    "For a follow-up OfficeCLI request in the same chat, use the result_file_id from "
    "the most recent successful OfficeCLI batch in the conversation as the source file; do not return to an "
    "older uploaded file. OfficeCLI remains available for that follow-up: do not claim that its tools are "
    "unavailable and do not ask the user to re-upload the existing Office document; obtain guidance and "
    "execute the relevant batch instead. "
    "For an existing PPTX text change, use the official PPTX shape help and the "
    "shape inventory to identify the visible target by its current text and stable shape path; never "
    "guess a generic shape name. Change that existing shape rather than adding a competing overlay, preserve "
    "its geometry, and explicitly remove any superseded shape. After the batch, inspect the returned PPTX "
    "and verify that the requested text is in the intended shape and the replaced text is gone. Do not "
    "report completion until that verification and the execution tool return a result_file_id."
)
GEMINI_COMPATIBILITY_INSTRUCTION = (
    f"{GEMINI_COMPATIBILITY_MARKER} For Gemini direct models, do not call load_officecli_skill "
    "before creating a new file: use the format-specific create operation in the routing contract "
    "directly. For a DOCX commands argument, "
    "use this known-valid minimal OfficeCLI batch shape and adapt only the markdown text: "
    "[{\"command\":\"add\",\"parent\":\"/body\",\"type\":\"markdown\","
    "\"props\":{\"markdown\":\"# Invitation\\n\\n[content]\"}}]. "
    "Each create operation runs the official OfficeCLI create, batch, and validate steps and attaches "
    "the resulting file."
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


def _append_gemini_compatibility_instruction(messages: list[Any]) -> None:
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system" and isinstance(message.get("content"), str):
            if GEMINI_COMPATIBILITY_MARKER not in message["content"]:
                message["content"] = f"{message['content'].rstrip()}\n\n{GEMINI_COMPATIBILITY_INSTRUCTION}"
            return


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
            if body.get("model", "").startswith("models/gemini-"):
                _append_gemini_compatibility_instruction(messages)

        return body
