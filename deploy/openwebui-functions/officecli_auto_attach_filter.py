"""
title: OfficeCLI Auto Attach
author: Alpha Soft
version: 1.0.0-native-office
required_open_webui_version: 0.9.6
description: Adds the existing OfficeCLI tool server only to explicitly configured direct Native chat models.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field


OFFICECLI_TOOL_ID = "server:officecli"
OFFICECLI_INSTRUCTION_MARKER = "[officecli-auto-attach-v4-native]"
MULTI_XLSX_INSTRUCTION_MARKER = "[officecli-multi-xlsx-v1]"
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
    "models/gemini-3.5-flash-lite,"
    "gpt-6-luna,"
    "gpt-6-sol,"
    "claude-opus-5-5"
)
OFFICECLI_INSTRUCTION = (
    f"{OFFICECLI_INSTRUCTION_MARKER} OfficeCLI is available for DOCX, XLSX, and PPTX work. "
    "For a new file made from text, spreadsheet cells, or basic slide shapes, never call "
    "load_officecli_skill or get_officecli_help. Directly call the matching create operation once per "
    "requested file: DOCX uses create_office_document, XLSX uses create_office_spreadsheet, and PPTX "
    "uses create_office_presentation. Build commands from the request using these valid base shapes. "
    "DOCX paragraph: {\"command\":\"add\",\"parent\":\"/body\",\"type\":\"paragraph\","
    "\"props\":{\"text\":\"Title\"}}. Add one command per requested paragraph. "
    "If markdown is needed, keep it inside props.markdown and use real newline characters, never literal backslash-n text. "
    "XLSX cell: {\"command\":\"set\",\"path\":\"/Sheet1/A1\",\"props\":{\"value\":\"Text\"}}. For requested money, put \"numFmt\":\"#,##0 ₽\" in each price, amount, and total cell props; preserve every requested label such as Итого. Use formulas for requested calculations. Do not add unrequested titles, merged cells, column widths, or styling. "
    "PPTX: add every slide first with {\"command\":\"add\",\"parent\":\"/\",\"type\":\"slide\","
    "\"props\":{\"layout\":\"blank\"}}, then add each basic text shape with flat props such as {\"command\":\"add\",\"parent\":\"/slide[1]\",\"type\":\"shape\",\"props\":{\"text\":\"Title\",\"x\":\"2cm\",\"y\":\"3cm\",\"width\":\"29cm\",\"height\":\"3cm\"}}. For basic shapes, never use nested geometry or font objects. Every requested slide title, subtitle, list item, date, and phrase must appear as visible shape text; do not summarize or omit them. "
    "Do not substitute code, a recipe, or a refusal for the tool call. Finish only after the current "
    "create result contains result_file_id and the native attachment is present; if execution fails, "
    "report the failure. A successful create result is terminal for that file: do not reopen, inspect, apply changes, call help, or recreate it in the same response. Continue creating other requested files and return each resulting native attachment once. Reply with a plain-language sentence naming the files; never echo tool JSON and never leave the final answer empty. "
    "For existing files, obtain explicit file_id values from native attached_files blocks (their opaque url), or list_chat_files when needed; citation numbers are not file IDs. Prefer the latest user upload over earlier copies. Inspect each required source with the matching format operation: inspect_office_document for DOCX and inspect_office_spreadsheet for XLSX use command_payload={\"command\":\"view\",\"mode\":\"annotated\"}; inspect_office_presentation for PPTX uses command_payload={\"command\":\"query\",\"selector\":\"shape\"}. Then use the matching apply batch to edit an existing file, or create to produce a new file from the sources. Do not ask for re-uploading available files. "
    "Load only the format-specific skill or help needed for its exact existing structure, or for a new "
    "table, chart, or picture. Preserve unrelated content and never invent document paths."
)

MULTI_XLSX_INSTRUCTION = (
    f"{MULTI_XLSX_INSTRUCTION_MARKER} For work based on multiple attached Excel files, "
    "use the native attached_files blocks to identify each source: the opaque file url is "
    "its OpenWebUI file_id. Read each required workbook with inspect_office_spreadsheet "
    "and that explicit file_id before deriving the result. A citation number is not a file_id. "
    "Prefer the files in the latest user upload when earlier copies exist; do not ask for "
    "renaming or re-uploading to resolve multiple attachments. If the tags are unavailable, "
    "use the native list_chat_files tool to obtain IDs; never guess an ID. "
    "For a requested new output based on these sources, call create_office_spreadsheet "
    "after reading them; apply_office_spreadsheet_batch edits one existing workbook. "
    "A new workbook starts with Sheet1: rename it with "
    "{\"command\":\"set\",\"path\":\"/Sheet1\",\"props\":{\"name\":\"Jan 26\"}}, "
    "then add another sheet with {\"command\":\"add\",\"parent\":\"/\",\"type\":\"sheet\","
    "\"props\":{\"name\":\"Feb 26\"}}. Every add item requires parent; use the user's requested sheet names. "
    "Preserve all requested data and use formulas for calculations. Only declare success "
    "after result_file_id and its native attachment exist. Do not claim a faithful copy "
    "of source sheets, drawings or styles when you have only read annotated cell data. "
    "Reply with one plain sentence naming the attached file; never invent sandbox or download links."
)


def _has_multiple_xlsx(files: Any) -> bool:
    """Recognize native XLSX references; file access stays with OpenWebUI."""
    if not isinstance(files, list):
        return False
    ids = set()
    for file in files:
        if not isinstance(file, dict) or file.get("type", "file") != "file":
            continue
        name = file.get("name") or ""
        file_id = file.get("id") or file.get("url")
        if isinstance(name, str) and name.lower().endswith(".xlsx") and isinstance(file_id, str) and file_id:
            ids.add(file_id)
    return len(ids) > 1


def _append_multi_xlsx_instruction(messages: list[Any]) -> None:
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system" and isinstance(message.get("content"), str):
            if MULTI_XLSX_INSTRUCTION_MARKER not in message["content"]:
                message["content"] += f"\n\n{MULTI_XLSX_INSTRUCTION}"
            return


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

            if _has_multiple_xlsx(body.get("files")):
                _append_multi_xlsx_instruction(messages)

        return body
