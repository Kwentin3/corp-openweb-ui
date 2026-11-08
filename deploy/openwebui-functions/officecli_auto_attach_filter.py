"""
title: OfficeCLI Auto Attach
author: Alpha Soft
version: 2.2.5-native-seen-layout-check
required_open_webui_version: 0.12.2
description: Adds the existing OfficeCLI tool server only to explicitly configured direct Native chat models.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
import base64
import json
import inspect
from html import escape
from types import SimpleNamespace
import re
from typing import Any

from pydantic import BaseModel, Field


OFFICECLI_TOOL_ID = "server:officecli"
CORPORATE_TOOL_IDS = ("corporate_document_delegation", "corporate_template_publication")
CORPORATE_DELEGATION_DESCRIPTION = (
    "Fill a copy of a published corporate DOCX template original confirmed by a fully read native Skill. "
    "Include that Skill ID, its Original native File ID and all confirmed facts in prompt. "
    "Ordinary uploaded Office forms use direct OfficeCLI tools. This is not general task delegation."
)
CORPORATE_DELEGATION_PROMPT_DESCRIPTION = (
    "The fully read published template Skill ID, its confirmed Original native File ID, "
    "all collected facts and the bounded filling task. Do not delegate an unrelated ordinary uploaded form."
)
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
DOCX_LAYOUT_SET_PROPERTIES = {
    "size", "spaceBefore", "spaceAfter", "marginTop", "marginBottom", "marginLeft", "marginRight",
    "cantSplit", "header", "keepNext", "pageBreakBefore", "padding",
}
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
    "Use load_officecli_skill and get_officecli_help for installed syntax. "
    "Execute CLI guide examples through OfficeCLI API tools; Terminal is a separate environment and does not imply an installed OfficeCLI binary. "
    "For saved notes, use export_answer_to_word with source_note_id to import the full text instead of retyping it into create commands. "
    "Use attached_files/list_chat_files IDs, not citations; explicit file_id for multiple inputs. Reads do not publish. "
    "create/apply save copies and return native attachments. Batches contain edits, not create/open/save/close. "
    "The native artifact-workflow Skill owns planning, source preservation, verification, fallback and delivery."
)


OFFICECLI_PUBLISH_TOOLS = {
    "create_office_document", "export_answer_to_word", "apply_office_batch",
    "create_office_spreadsheet", "apply_office_spreadsheet_batch",
    "create_office_presentation", "apply_office_presentation_batch",
    "publish_terminal_file",
}


def _scope_corporate_delegation_schema(body: dict, tools: dict) -> None:
    """Adapt this composition's resolved schema, not shared community Tool specs."""
    for key, tool in list(tools.items()):
        spec = tool.get("spec", {})
        if (tool.get("tool_id") != "corporate_document_delegation"
                or spec.get("name") != "run_sub_agent" or tool.get("direct")):
            continue

        def scoped(original):
            result = deepcopy(original)
            result["description"] = CORPORATE_DELEGATION_DESCRIPTION
            prompt = result.get("parameters", {}).get("properties", {}).get("prompt")
            if isinstance(prompt, dict):
                prompt["description"] = CORPORATE_DELEGATION_PROMPT_DESCRIPTION
            return result

        # Native request tools and provider schemas can share the factory spec.
        # Keep the original object/callable intact for other requests/owners.
        tools[key] = {**tool, "spec": scoped(spec)}
        unique_name = not any(other_key != key and other.get("spec", {}).get("name") == spec["name"]
                              for other_key, other in tools.items())
        if isinstance(body.get("tools"), list):
            schemas = []
            for schema in body["tools"]:
                provider_spec = schema.get("function", schema)
                if provider_spec is spec or (unique_name and provider_spec.get("name") == spec["name"]):
                    schema = ({**schema, "function": scoped(provider_spec)}
                              if "function" in schema else scoped(schema))
                schemas.append(schema)
            body["tools"] = schemas


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


def _known_layout_set_batch(params: dict) -> bool:
    commands = params.get("commands")
    return isinstance(commands, list) and bool(commands) and all(
        isinstance(command, dict) and command.get("command") == "set"
        and isinstance(command.get("props"), dict) and bool(command["props"])
        and command["props"].keys() <= DOCX_LAYOUT_SET_PROPERTIES
        and ("header" not in command["props"] or (
            isinstance(command.get("path"), str) and re.search(r"/tr\[[1-9]\d*\]$", command["path"])
            and (isinstance(command["props"]["header"], bool)
                 or command["props"]["header"] in ("true", "false"))))
        for command in commands
    )


def _tool_text_and_image(content: Any) -> tuple[str, bool]:
    if isinstance(content, str):
        return content, False
    if not isinstance(content, list):
        return "", False
    image = False
    for part in content:
        if not isinstance(part, dict) or part.get("type") not in ("input_image", "image_url"):
            continue
        url = part.get("image_url")
        url = url.get("url") if isinstance(url, dict) else url
        if not isinstance(url, str):
            continue
        if url.startswith("data:image/png;base64,"):
            try:
                image |= base64.b64decode(url.split(",", 1)[1][:12], validate=True).startswith(b"\x89PNG\r\n\x1a\n")
            except (ValueError, TypeError):
                pass
    return ("".join(part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") in ("text", "input_text")), image)


def _seen_tool_pairs(messages: Any) -> dict | None:
    """Read native canonical request messages; ambiguous/pending frames are out of scope."""
    if not isinstance(messages, list):
        return None
    calls, results = {}, {}

    def add_call(call_id, name, arguments):
        if not isinstance(call_id, str) or not call_id or call_id in calls:
            raise ValueError
        calls[call_id] = (name, json.loads(arguments) if isinstance(arguments, str) else arguments)

    def add_result(call_id, content, status=None):
        if not isinstance(call_id, str) or not call_id or call_id in results:
            raise ValueError
        results[call_id] = _tool_text_and_image(content) if status in (None, "completed") else ("", False)

    try:
        for message in messages:
            if not isinstance(message, dict):
                return None
            for call in message.get("tool_calls") or []:
                function = call.get("function", {})
                add_call(call.get("id"), function.get("name"), function.get("arguments", "{}"))
            if message.get("role") == "tool":
                add_result(message.get("tool_call_id"), message.get("content"))
            for item in message.get("output") or []:
                if item.get("type") == "function_call":
                    add_call(item.get("call_id"), item.get("name"), item.get("arguments", "{}"))
                elif item.get("type") == "function_call_output":
                    add_result(item.get("call_id"), item.get("output"), item.get("status"))
        if calls.keys() != results.keys():
            return None
        return {call_id: (*call, *results[call_id]) for call_id, call in calls.items()}
    except (ValueError, TypeError, AttributeError):
        return None


def _seen_docx_layout_needs_preview(file_id: str, seen: dict) -> bool:
    """Read only paired receipts already present in this model input, in order."""
    written, rendered, staged, written_hash = False, False, False, None
    for name, args, text, image in seen.values():
        if not isinstance(args, dict):
            return False
        try:
            receipt = json.loads(text)
        except (ValueError, TypeError):
            receipt = {}
        if not isinstance(receipt, dict):
            receipt = {}
        if name in ("apply_office_batch", "create_office_document"):
            native_file = receipt.get("result_file") or {}
            if (isinstance(native_file, dict) and receipt.get("result_file_id") == file_id and native_file.get("id") == file_id
                    and _has_office_file([native_file], {".docx"})):
                written, rendered, staged = True, False, False
                written_hash = receipt.get("result_sha256")
        elif name == "render_office_file" and written and args.get("file_id") == file_id and args.get("format") == "docx" and image:
            rendered, staged = True, False
        elif (name == "stage_chat_file" and rendered and args.get("file_id") == file_id
              and receipt.get("source_file_id") == file_id and receipt.get("source_modified") is False
              and isinstance(receipt.get("path"), str) and written_hash and receipt.get("sha256") == written_hash):
            staged = True
        elif (name == "read_file" and staged and isinstance(args.get("path"), str)
              and args["path"].lower().endswith(".png") and image):
            return False
    return written and rendered


async def _require_seen_docx_preview(params: dict, request_body: dict, metadata: dict, user_id: str) -> None:
    if (not _known_layout_set_batch(params) or metadata.get("tool_approval_resume") == "tools"
            or request_body.get("previous_response_id")):
        return
    seen = _seen_tool_pairs(request_body.get("messages"))
    if not seen:
        return
    from open_webui.models.chats import Chats
    from open_webui.utils.misc import get_message_list
    chat = await Chats.get_chat_by_id_and_user_id(metadata.get("chat_id"), user_id)
    history = (getattr(chat, "chat", None) or {}).get("history", {}).get("messages", {})
    message = history.get(metadata.get("message_id") or metadata.get("assistant_message_id"), {})
    parent_id = message.get("parentId")
    if (message.get("role") != "assistant" or history.get(parent_id, {}).get("role") != "user"
            or (metadata.get("user_message_id") and metadata["user_message_id"] != parent_id)):
        return
    # Native 0.12.2 saves the assistant's parent before generation, but may not
    # persist streaming output. Use ONLY its stable native ancestry to exclude
    # older calls; all current receipts/media come from the seen request above.
    # This also excludes old tools if native compaction reorders them after User.
    previous_ids = set()
    for ancestor in get_message_list(history, parent_id):
        previous_ids.update(call.get("id") for call in ancestor.get("tool_calls") or [])
        previous_ids.update(item.get("call_id") for item in ancestor.get("output") or []
                            if item.get("type") == "function_call")
    current_seen = {call_id: pair for call_id, pair in seen.items() if call_id not in previous_ids}
    if _seen_docx_layout_needs_preview(params.get("file_id"), current_seen):
        raise ValueError("Before another DOCX layout-only repair, stage this same result_file_id, render its copy with LibreOffice/PDF to PNG, and read_file the PNG pages. The image results must be in a later model input before choosing the repair; otherwise return the existing copy with the verification limit.")


def _workflow_context(metadata: dict[str, Any], skill_id: str) -> None:
    if skill_id:
        context = metadata.setdefault("chat_context", {})
        mentioned_ids = context.setdefault("mentioned_skill_ids", [])
        if skill_id not in mentioned_ids:
            context["mentioned_skill_ids"] = [*mentioned_ids, skill_id]
    metadata[WORKFLOW_REQUEST_MARKER] = True


async def _read_native_skill_pin(skill_id: str, version: str, user: dict):
    from open_webui.routers.skills import authorized_skill
    from open_webui.models.skills import get_skill_snapshot

    skill = await authorized_skill(skill_id, SimpleNamespace(**user))
    return skill, await get_skill_snapshot(skill, version)


async def _read_published_templates(metadata: dict, user: dict, direct_write: bool = False) -> list:
    """Resolve read pins through native ACL/snapshots and the publisher's binding."""
    from fastapi import HTTPException

    pins = (metadata.get("chat_context") or {}).get("skill_versions") or {}
    candidates = []
    # This is the existing publisher's exact Original-template binding, not a
    # guessed filename or a File ID mentioned by model prose.
    binding = re.compile(
        r"\n\n## Original template\n\nOriginal native File ID: `([A-Za-z0-9_-]{1,128})`\.\n"
        r"Template Knowledge ID: `[A-Za-z0-9_-]{1,128}`\.\n"
        r"\[Download original DOCX\]\(/api/v1/files/\1/content\)\.\n"
        r"Retrieve this original with the existing OfficeCLI file workflow, make a new copy, "
        r"and fill that copy\. Preserve the original document and its formatting\.\n\Z"
    )
    for skill_id, version in pins.items():
        if skill_id.startswith("terminal:") or not version:
            continue
        try:
            skill, snapshot = await _read_native_skill_pin(skill_id, version, user)
        except HTTPException as error:
            # Ordinary edits do not depend on access to every previously read
            # Skill. Do not bypass ACL to guess a binding from a denied pin.
            if direct_write and error.status_code in (403, 404):
                continue
            raise
        content = snapshot.get("content")
        if isinstance(content, str) and content.count("\n## Original template\n") == 1:
            match = binding.search(content)
            if match:
                if not skill.is_active and not direct_write:
                    raise ValueError("The read template Skill is inactive; read an active published template before delegation.")
                candidates.append((skill_id, snapshot, match.group(1)))
    return candidates


async def _has_native_authoring_pin(metadata: dict, user: dict) -> bool:
    from fastapi import HTTPException

    version = ((metadata.get("chat_context") or {}).get("skill_versions") or {}).get("corporate-template-authoring")
    if not version:
        return False
    try:
        skill, snapshot = await _read_native_skill_pin("corporate-template-authoring", version, user)
    except HTTPException as error:
        if error.status_code in (403, 404):
            return False
        raise
    return skill.is_active and isinstance(snapshot.get("content"), str) and bool(snapshot["content"].strip())


async def _require_corporate_template_route(file_id: Any, metadata: dict, user: dict) -> None:
    if not isinstance(file_id, str):
        return
    # The existing private authoring Skill owns revisions. A profile name or
    # admin role alone does not establish that this invocation is authoring.
    if await _has_native_authoring_pin(metadata, user):
        return
    for skill_id, snapshot, original_file_id in await _read_published_templates(metadata, user, direct_write=True):
        if file_id == original_file_id:
            raise ValueError(
                "Use run_sub_agent with the published Skill ID " + skill_id
                + " and all agreed facts to fill this corporate original. "
                "Direct OfficeCLI edits remain available for ordinary files and filled result copies."
            )


async def _template_handoff_messages(prompt: str, messages: list, metadata: dict, user: dict) -> list:
    """Adapt a read native template to the pinned community Tool's system-tag input."""
    from open_webui.utils.skill_files import skill_overview, format_skill_content

    if not isinstance(prompt, str) or not isinstance(messages, list):
        raise ValueError("Native delegation prompt/messages are required for complete template handoff.")
    candidates = await _read_published_templates(metadata, user)
    if len(candidates) > 1:
        candidates = [(sid, snapshot, original) for sid, snapshot, original in candidates
                      if re.search(r"(?<![A-Za-z0-9_-])" + re.escape(sid) + r"(?![A-Za-z0-9_-])", prompt)]
    if len(candidates) != 1:
        raise ValueError("Read one published template Skill before delegation; if several were read, reference exactly one Skill ID in prompt. "
                         "Use OfficeCLI tools directly for ordinary Office files; this delegation is only for published corporate DOCX templates.")
    skill_id, snapshot, original_file_id = candidates[0]
    content, files = snapshot["content"], (snapshot.get("data") or {}).get("files")
    if (not isinstance(files, list) or len(files) != 1 or files[0].get("path") != "SKILL.md"
            or files[0].get("encoding") or files[0].get("content") != content):
        raise ValueError("Template handoff requires the published text-only SKILL.md snapshot, with no omitted supporting files.")
    overview = skill_overview(content, [], tools_enabled=False)
    if overview.get("next_offset") is not None or overview.get("content") != content:
        raise ValueError("The native Skill formatter cannot transfer the complete template; delegation was not started.")
    formatted = format_skill_content(overview, skill_id, False)
    if formatted != content:
        raise ValueError("Native template instructions are incomplete; delegation was not started.")
    # Community 790de1a copies only SYSTEM tags with a name attribute. Tool
    # results from view_skill are not such tags. Do not alter parent messages.
    tag_pattern = re.compile(r"<skill [^\n]*?name=.*?>\n.*?\n</skill>", re.DOTALL)
    system_text = []
    for message in messages:
        if message.get("role") != "system":
            continue
        value = message.get("content")
        if isinstance(value, str):
            system_text.append(value)
        elif isinstance(value, list):
            system_text.extend(part.get("text", "") for part in value
                               if isinstance(part, dict) and part.get("type") == "text")
    prompt_count = prompt.count(content)
    system_count = sum(text.count(content) for text in system_text)
    tags = [tag for text in system_text for tag in tag_pattern.findall(text)]
    own_tags = [tag for tag in tags if re.search(
        r'\bid=["\']' + re.escape(skill_id) + r'["\']', tag.split(">", 1)[0],
    )]
    if prompt_count + system_count > 1 or len(own_tags) > 1:
        raise ValueError("Duplicate template instructions in delegation context; resolve duplicates before delegation.")
    if own_tags and (content not in own_tags[0] or prompt_count):
        raise ValueError("Conflicting or incomplete template system tag; delegation was not started.")
    if prompt_count == 1:
        return deepcopy(messages)
    if system_count == 1:
        if len(own_tags) != 1 or content not in own_tags[0]:
            raise ValueError("Template text is outside its matching native Skill tag; delegation was not started.")
        return deepcopy(messages)
    tag = f'<skill id="{escape(skill_id, quote=True)}" name="{escape(snapshot["name"], quote=True)}">\n{formatted}\n</skill>'
    return [*deepcopy(messages), {"role": "system", "content": tag}]


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
        _scope_corporate_delegation_schema(body, tools)
        for name, tool in metadata.get("tools", {}).items():
            corporate_handoff = (tool.get("tool_id") == "corporate_document_delegation"
                                 and tool.get("spec", {}).get("name") == "run_sub_agent")
            direct_docx = (tool.get("tool_id") == OFFICECLI_TOOL_ID
                           and tool.get("spec", {}).get("name") == "apply_office_batch")
            if (name not in PLAN_REQUIRED_TOOLS | APPLY_TOOLS | CONDITIONAL_PLAN_TOOLS and not corporate_handoff and not direct_docx) or tool.get("direct"):
                continue
            function = tool.get("callable")
            if not function:
                continue
            already_guarded = getattr(function, "_office_tasks_guard", False)
            if already_guarded and (not direct_docx or not hasattr(function, "_office_guard_original")):
                continue
            original = getattr(function, "_office_guard_original", getattr(function, "__function__", function))
            signature = inspect.signature(original)
            if name == "stage_chat_file" and "__files__" not in signature.parameters:
                parameters = list(signature.parameters.values())
                position = next((i for i, p in enumerate(parameters)
                                 if p.kind is inspect.Parameter.VAR_KEYWORD), len(parameters))
                parameters.insert(position, inspect.Parameter(
                    "__files__", inspect.Parameter.KEYWORD_ONLY, default=None,
                ))
                signature = signature.replace(parameters=parameters)

            def guard(original=original, signature=signature, name=name,
                      corporate_handoff=corporate_handoff, direct_docx=direct_docx, seen_request=body):
                async def guarded(*args, **kwargs):
                    params = dict(signature.bind_partial(*args, **kwargs).arguments)
                    # Native OpenAPI closures expose **kwargs, whereas local
                    # Tools expose named arguments. Both carry the same schema.
                    for key, parameter in signature.parameters.items():
                        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
                            params.update(params.pop(key, {}))
                    fresh_files = params.get("__files__")
                    files = fresh_files if isinstance(fresh_files, list) else metadata.get("files", [])
                    operation = "run_sub_agent" if corporate_handoff else "apply_office_batch" if direct_docx else name
                    if _requires_native_plan(operation, params, files):
                        await _require_active_native_tasks(chat_id, user_id)
                    if direct_docx:
                        await _require_corporate_template_route(
                            params.get("file_id"), params.get("__metadata__") or metadata,
                            params.get("__user__") or __user__,
                        )
                        # This native per-round request dict is the model input,
                        # unlike execute_tool_call's original __messages__. It is
                        # referenced read-only; no receipt ledger or instance state.
                        # Approval/resume augmented and unpaired frames skip only
                        # this new checkpoint; existing Tasks/template guards run.
                        await _require_seen_docx_preview(params, seen_request, metadata, user_id)
                    if corporate_handoff:
                        kwargs["__messages__"] = await _template_handoff_messages(
                            params.get("prompt"), params.get("__messages__"),
                            params.get("__metadata__") or metadata, params.get("__user__") or __user__,
                        )
                    if name == "stage_chat_file" and "__files__" not in inspect.signature(original).parameters:
                        kwargs.pop("__files__", None)
                    result = original(*args, **kwargs)
                    return await result if inspect.isawaitable(result) else result
                # Do not copy native __function__/__extra_params__ with wraps:
                # execute_tool_call must rebind fresh messages/files to THIS guard.
                guarded.__signature__ = signature
                guarded.__name__ = getattr(original, "__name__", name)
                guarded._office_tasks_guard = True
                guarded._office_guard_original = original
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
