from __future__ import annotations

import json
import re
from threading import BoundedSemaphore
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, computed_field, field_validator

from .config import Settings, load_settings
from .discovery import ObjectReadPayload, bounded_result, help_arguments, object_arguments
from .officecli import (
    OfficeCliExecutor,
    OfficeCliFailure,
    OfficeCliOutput,
    SubprocessOfficeCliExecutor,
)
from .rendering import RenderOfficeRequest, checked_png
from .openwebui_client import (
    HttpOpenWebUiClient,
    native_file_content_path,
    OpenWebUiAmbiguousAttachment,
    OpenWebUiClient,
    OpenWebUiFailure,
    OpenWebUiUnauthorized,
)


PPTX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
ATTACHED_IMAGE_SOURCE = "attachment://image"
PRESENTATION_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


AUTHOR_WORKFLOW_TRIGGER = (
    "Use the installed official guide from load_officecli_skill and command details from get_officecli_help. "
)


class SkillRequest(BaseModel):
    skill: str | None = Field(default=None, min_length=1, max_length=64,
        description="Omit to discover the installed official skill catalog. Then select its most specific skill name; load one guide per artifact, once, as the authors recommend.")
    path: str | None = Field(default=None, min_length=1, max_length=240,
        description="Optional relative reference file from the loaded skill's manifest, e.g. reference/INDEX.md. The installed CLI owns the files.")

    @field_validator("skill")
    @classmethod
    def skill_is_a_name(cls, value):
        if value is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,63}", value):
            raise ValueError("skill must be a catalog name, not a command or path")
        return value

    @field_validator("path")
    @classmethod
    def reference_is_relative(cls, value):
        if value is not None and (
            not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,239}", value)
            or any(segment in {"", ".", ".."} for segment in value.split("/"))
        ):
            raise ValueError("path must be a relative bundled reference, without traversal")
        return value


class HelpRequest(BaseModel):
    topic: str = Field(default="workflow", min_length=3, max_length=140, description=(
        "workflow returns the installed official MCP tool instructions, unchanged. "
        "Installed CLI discovery: start with docx, xlsx, or pptx for the element catalog; "
        "then FORMAT ELEMENT or FORMAT VERB ELEMENT for exact properties and operations, "
        "e.g. xlsx picture, xlsx remove picture, docx table-cell, pptx chart. "
        "FORMAT is a placeholder for docx, xlsx or pptx, never a literal topic word: "
        "use docx paragraph or docx add markdown. Request one topic per call; do not combine "
        "multiple elements, properties or commands into a single topic. "
        "help lists all commands; FORMAT / lists document-level properties. Bare query/get/view/batch/validate/raw/raw-set returns command usage; FORMAT VERB lists its elements. Request only the needed topic."
    ))

    @field_validator("topic")
    @classmethod
    def official_help_topic(cls, value: str) -> str:
        if value != "workflow":
            help_arguments(value)
        return value


class GuidanceResponse(BaseModel):
    source: str
    command: list[str]
    content: str
    content_sha256: str
    auto_resident_disabled: bool
    diagnostics: str = ""


class InspectCommandPayload(ObjectReadPayload):
    mode: Literal["annotated", "outline", "text", "stats", "issues", "forms", "html"] = "annotated"


class NativeDocxReference(BaseModel):
    file_id: str | None = Field(
        default=None,
        description=(
            "Optional native OpenWebUI DOCX file id. Omit it rather than guessing: "
            "the nearest DOCX attachment in the native message ancestry is used."
        ),
    )

    @field_validator("file_id", mode="before")
    @classmethod
    def only_accept_an_opaque_native_file_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9-]{1,128}", value):
            return value
        raise ValueError(
            "file_id must be omitted or be an opaque native OpenWebUI file id"
        )


class NativeXlsxReference(NativeDocxReference):
    file_id: str | None = Field(
        default=None,
        description=(
            "Optional native OpenWebUI XLSX file id. Omit it rather than guessing: "
            "the nearest XLSX attachment in the native message ancestry is used."
        ),
    )


class NativePptxReference(NativeDocxReference):
    file_id: str | None = Field(
        default=None,
        description=(
            "Optional native OpenWebUI PPTX file id. Omit it rather than guessing: "
            "the nearest PPTX attachment in the native message ancestry is used."
        ),
    )


class InspectOfficeDocumentRequest(NativeDocxReference):
    command_payload: InspectCommandPayload


class InspectSpreadsheetCommandPayload(ObjectReadPayload):
    command: Literal["view", "query", "get", "validate", "raw"] = "view"
    mode: Literal["outline", "text", "annotated", "stats", "issues", "html"] = "outline"
    range: str | None = Field(
        default=None, max_length=160,
        description="For text mode, an explicit sheet-qualified range, e.g. Sheet1!A1:H30. Read only the cells needed for the next decision.",
    )

    @field_validator("range")
    @classmethod
    def bounded_sheet_range(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(
            r"[^\x00-\x1f!]{1,100}![A-Za-z]{1,3}[1-9][0-9]{0,6}(?::[A-Za-z]{1,3}[1-9][0-9]{0,6})?", value
        ):
            raise ValueError("range must be sheet-qualified, for example Sheet1!A1:H30")
        return value


class InspectSpreadsheetRequest(NativeXlsxReference):
    command_payload: InspectSpreadsheetCommandPayload = Field(default_factory=InspectSpreadsheetCommandPayload)


class InspectPresentationCommandPayload(ObjectReadPayload):
    command: Literal["query", "get", "view", "validate", "raw"] = "query"
    mode: Literal["outline", "text", "annotated", "stats", "issues", "html", "svg"] = "outline"
    selector: str | None = Field(default=None, min_length=1, max_length=512, description="Official selector, e.g. shape, picture, chart, table; query returns actual paths.")


class InspectPresentationRequest(NativePptxReference):
    command_payload: InspectPresentationCommandPayload


class ApplyOfficeBatchRequest(NativeDocxReference):
    output_name: str = Field(min_length=6, max_length=120)
    commands: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=64,
        description=(
            "Official OfficeCLI batch items. Each item has a bare verb in command and its "
            "arguments as sibling fields, for example command=set with path and props. The official "
            "CLI help writes the corresponding flag as --prop; that singular JSON spelling is accepted "
            "and translated to props. "
            "Obtain the exact command details from OfficeCLI help before calling."
        ),
    )

    @field_validator("commands")
    @classmethod
    def translate_official_prop_alias(
        cls, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return _translate_official_prop_alias(value)

    @field_validator("output_name")
    @classmethod
    def output_name_is_a_plain_docx_name(cls, value: str) -> str:
        if Path(value).name != value or not value.lower().endswith(".docx"):
            raise ValueError("output_name must be a plain .docx filename")
        return value


class CreateOfficeDocumentRequest(BaseModel):
    output_name: str = Field(min_length=6, max_length=120)
    commands: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=64,
        description=(
            "Official OfficeCLI batch items used to fill a newly created DOCX. Read the installed "
            "OfficeCLI help before choosing non-trivial element types and properties; a minimal markdown "
            "item may be added directly at /body. The official help's --prop "
            "flag may be supplied as prop and is translated to the batch JSON field props."
        ),
    )

    @field_validator("commands")
    @classmethod
    def translate_official_prop_alias(
        cls, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return _translate_official_prop_alias(value)

    @field_validator("output_name")
    @classmethod
    def output_name_is_a_plain_docx_name(cls, value: str) -> str:
        if Path(value).name != value or not value.lower().endswith(".docx"):
            raise ValueError("output_name must be a plain .docx filename")
        return value


class ApplySpreadsheetBatchRequest(NativeXlsxReference):
    output_name: str = Field(min_length=6, max_length=120)
    commands: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=256,
        description=(
            "Up to 256 ordered official OfficeCLI batch items for the current XLSX attachment. "
            "Use this operation for a later conversational edit; do not create a new "
            "workbook when continuing an existing one."
        ),
    )

    @field_validator("commands")
    @classmethod
    def translate_official_prop_alias(
        cls, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return _translate_official_prop_alias(value)

    @field_validator("output_name")
    @classmethod
    def output_name_is_a_plain_xlsx_name(cls, value: str) -> str:
        if Path(value).name != value or not value.lower().endswith(".xlsx"):
            raise ValueError("output_name must be a plain .xlsx filename")
        return value


class CreateSpreadsheetRequest(BaseModel):
    output_name: str = Field(min_length=6, max_length=120)
    commands: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=256,
        description=(
            "Ordered official OfficeCLI batch items (up to 256 per call). "
            "A new XLSX already contains Sheet1. Reuse it by default; when the user "
            "requests a sheet name, rename it using the installed xlsx sheet help. "
            "A failed batch rolls "
            "back all of its operations; use apply_office_spreadsheet_batch, not another "
            "create call, for a later conversational edit."
        ),
    )

    @field_validator("commands")
    @classmethod
    def translate_official_prop_alias(
        cls, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return _translate_official_prop_alias(value)

    @field_validator("output_name")
    @classmethod
    def output_name_is_a_plain_xlsx_name(cls, value: str) -> str:
        if Path(value).name != value or not value.lower().endswith(".xlsx"):
            raise ValueError("output_name must be a plain .xlsx filename")
        return value


class ApplyPresentationBatchRequest(NativePptxReference):
    output_name: str = Field(min_length=6, max_length=120)
    # A polished multi-slide deck commonly has more than 64 operations (slide,
    # text boxes, shapes, table/chart, and notes).  This remains bounded while
    # allowing a complete ordinary presentation in one atomic OfficeCLI batch.
    commands: list[dict[str, Any]] = Field(min_length=1, max_length=256)

    @field_validator("commands")
    @classmethod
    def translate_official_prop_alias(
        cls, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return _normalize_presentation_commands(value)

    @field_validator("output_name")
    @classmethod
    def output_name_is_a_plain_pptx_name(cls, value: str) -> str:
        if Path(value).name != value or not value.lower().endswith(".pptx"):
            raise ValueError("output_name must be a plain .pptx filename")
        return value


class CreatePresentationRequest(BaseModel):
    output_name: str = Field(min_length=6, max_length=120)
    source_intent: Literal["new_independent_presentation"] | None = Field(
        default=None,
        description=(
            "Set only when the user explicitly requests a new presentation independent of "
            "any PPTX attached in this chat. For a template or previous version, use "
            "apply_office_presentation_batch instead."
        ),
    )
    commands: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=256,
        description=(
            "Official OfficeCLI batch items. Consult the installed pptx help for element paths and properties."
        ),
    )

    @field_validator("commands")
    @classmethod
    def translate_official_prop_alias(
        cls, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return _normalize_presentation_commands(value)

    @field_validator("output_name")
    @classmethod
    def output_name_is_a_plain_pptx_name(cls, value: str) -> str:
        if Path(value).name != value or not value.lower().endswith(".pptx"):
            raise ValueError("output_name must be a plain .pptx filename")
        return value


def _translate_official_prop_alias(
    commands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Bridge the official CLI's ``--prop`` spelling to batch JSON's ``props`` field."""
    normalized: list[dict[str, Any]] = []
    for command in commands:
        if "prop" not in command:
            normalized.append(command)
            continue
        if "props" in command:
            raise ValueError("a batch item must specify either prop or props, not both")
        normalized.append(
            {key: value for key, value in command.items() if key != "prop"}
            | {"props": command["prop"]}
        )
    return normalized


def _normalize_presentation_commands(
    commands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep create and apply equally strict about native image references."""
    normalized = _translate_official_prop_alias(commands)
    for command in normalized:
        props = command.get("props")
        if not isinstance(props, dict):
            continue
        source = props.get("src", props.get("path"))
        if source is not None and source != ATTACHED_IMAGE_SOURCE:
            raise ValueError(
                "PPTX picture src must be attachment://image from one native chat image attachment"
            )
    return normalized


class InspectionResponse(BaseModel):
    source: str
    file_id: str
    officecli_result: Any
    officecli_result_sha256: str
    auto_resident_disabled: bool


class ApplyResponse(BaseModel):
    source: str
    source_file_id: str
    result_file_id: str
    result_file: dict[str, Any]
    batch_result: Any
    validation_result: Any
    source_sha256: str
    result_sha256: str
    source_bytes_preserved: bool
    auto_resident_disabled: bool
    bounded_processes_completed: bool

    @computed_field
    @property
    def download_url(self) -> str:
        """Use the same native file route as authorized downloads."""
        return native_file_content_path(self.result_file_id)


class CreateResponse(BaseModel):
    source: str
    result_file_id: str
    result_file: dict[str, Any]
    create_result: Any
    batch_result: Any
    validation_result: Any
    result_sha256: str
    auto_resident_disabled: bool
    bounded_processes_completed: bool

    @computed_field
    @property
    def download_url(self) -> str:
        """Use the same native file route as authorized downloads."""
        return native_file_content_path(self.result_file_id)


def _officecli_json(
    output: OfficeCliOutput, operation: str, *, allow_failed_validation: bool = False
) -> Any:
    try:
        parsed = json.loads(output.text)
    except json.JSONDecodeError as error:
        raise OfficeCliFailure(f"officecli {operation} did not return JSON") from error
    if not isinstance(parsed, dict) or (
        parsed.get("success") is not True
        and not (allow_failed_validation and parsed.get("success") is False)
    ):
        raise OfficeCliFailure(f"officecli {operation} reported failure: {output.text}")
    if output.diagnostics:
        parsed = {**parsed, "adapter_diagnostics": output.diagnostics}
    return parsed


def _invalid_pptx_source_detail(validation: dict[str, Any]) -> dict[str, Any]:
    data = validation.get("data")
    errors = data.get("errors") if isinstance(data, dict) else None
    native_findings = [
        f"{error.get('type', 'Validation')}: {error.get('description', '')}"
        + (f" ({error['part']})" if isinstance(error.get("part"), str) else "")
        for error in errors if isinstance(error, dict)
        and isinstance(error.get("description"), str)
    ] if isinstance(errors, list) else []
    warnings = validation.get("warnings")
    messages = [
        warning.get("message")
        for warning in warnings if isinstance(warning, dict)
        and isinstance(warning.get("message"), str)
    ] if isinstance(warnings, list) else []
    findings = native_findings or [message for message in messages if message.startswith("[")] or messages
    count = data.get("count") if isinstance(data, dict) else None
    summary = f"{count} OfficeCLI validation error(s)" if isinstance(count, int) else (
        messages[0] if messages else str(validation.get("message") or "Validation failed")
    )
    return {
        "code": "PPTX_SOURCE_VALIDATION_FAILED",
        "message": "The selected PPTX already fails OfficeCLI validation before editing. No new file was published.",
        "summary": summary[:500],
        "findings": [message[:500] for message in findings[:8]],
        "findings_total": max(len(findings), count) if isinstance(count, int) else len(findings),
        "options": [
            "Confirm a different valid PPTX from this chat as the base.",
            "Repair a copy of this PPTX, validate it, and then continue editing.",
        ],
    }


def _inspection_result(output: OfficeCliOutput, payload: ObjectReadPayload) -> Any:
    if payload.command == "view" and payload.mode in {"html", "svg"}:
        return {"format": payload.mode, "content": output.text, "adapter_diagnostics": output.diagnostics}
    return _officecli_json(output, payload.command)


def _bearer(authorization: str | None) -> str:
    if (
        not authorization
        or not authorization.startswith("Bearer ")
        or len(authorization) <= len("Bearer ")
    ):
        raise HTTPException(
            status_code=401, detail="a forwarded OpenWebUI bearer session is required"
        )
    return authorization


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, OpenWebUiUnauthorized):
        return HTTPException(
            status_code=401, detail="forwarded OpenWebUI session was rejected"
        )
    if isinstance(error, OpenWebUiAmbiguousAttachment):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=502, detail=str(error))


def _native_chat_message_ids(
    chat_id: str | None, message_id: str | None
) -> tuple[str, str]:
    if not chat_id or not message_id:
        raise HTTPException(
            status_code=400, detail="native chat and message ids are required"
        )
    return chat_id, message_id


def _materialize_presentation_images(
    commands: list[dict[str, Any]],
    workspace: Path,
    openwebui: OpenWebUiClient,
    chat_id: str,
    message_id: str,
    authorization: str,
) -> list[dict[str, Any]]:
    """Replace the documented image marker with one caller-authorized native attachment."""
    prepared: list[dict[str, Any]] = []
    needs_image = False
    for command in commands:
        copied = dict(command)
        props = copied.get("props")
        if isinstance(props, dict) and props.get("src", props.get("path")) == ATTACHED_IMAGE_SOURCE:
            copied_props = dict(props)
            copied_props["src"] = ATTACHED_IMAGE_SOURCE
            copied_props.pop("path", None)
            copied["props"] = copied_props
            needs_image = True
        prepared.append(copied)
    if not needs_image:
        return prepared

    attachment = openwebui.resolve_nearest_image_attachment(chat_id, message_id, authorization)
    suffix = Path(attachment.name).suffix.lower()
    if suffix not in PRESENTATION_IMAGE_SUFFIXES:
        raise OpenWebUiFailure("native image attachment has an unsupported file extension")
    destination = workspace / f"attached-image{suffix}"
    openwebui.download(attachment.file_id, authorization, destination)
    for command in prepared:
        props = command.get("props")
        if isinstance(props, dict) and props.get("src") == ATTACHED_IMAGE_SOURCE:
            props["src"] = str(destination)
    return prepared


def create_app(
    executor: OfficeCliExecutor | None = None,
    openwebui_client: OpenWebUiClient | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    active_settings = settings or load_settings()
    officecli = executor or SubprocessOfficeCliExecutor(active_settings)
    openwebui = openwebui_client or HttpOpenWebUiClient(
        active_settings.openwebui_base_url, active_settings.timeout_seconds
    )
    app = FastAPI(title="OfficeCLI for Open WebUI", version="2.0.0")
    render_slot = BoundedSemaphore(1)

    def official_workflow() -> GuidanceResponse:
        # The installed MCP tools/list owns the always-visible workflow. Detailed
        # skills and command schemas remain lazy, as in the upstream MCP server.
        try:
            output = officecli.run("mcp", input_text=json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}) + "\n")
            reply = next(json.loads(line) for line in output.text.splitlines()
                         if line.strip().startswith("{"))
            official_tool = next(tool for tool in reply["result"]["tools"] if tool["name"] == "officecli")
            content = official_tool["description"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty official tool description")
        except (OfficeCliFailure, ValueError, KeyError, TypeError, StopIteration) as error:
            raise HTTPException(status_code=502, detail="Installed OfficeCLI tool instructions could not be read") from error
        return GuidanceResponse(source=f"officecli v{active_settings.expected_version}",
            command=list(output.command), content=content,
            content_sha256=sha256(content.encode("utf-8")).hexdigest(),
            auto_resident_disabled=output.auto_resident_disabled, diagnostics=output.diagnostics)

    def authenticated_bearer(authorization: str | None) -> str:
        bearer = _bearer(authorization)
        try:
            openwebui.verify_session(bearer)
        except OpenWebUiUnauthorized as error:
            raise _http_error(error) from error
        except OpenWebUiFailure as error:
            raise _http_error(error) from error
        return bearer

    def guidance_response_for(
        authorization: str | None, *arguments: str
    ) -> GuidanceResponse:
        authenticated_bearer(authorization)
        try:
            output = officecli.run(*arguments)
        except OfficeCliFailure as error:
            raise _http_error(error) from error
        return GuidanceResponse(
            source=f"officecli v{active_settings.expected_version}",
            command=list(output.command),
            content=output.text,
            content_sha256=output.content_sha256,
            auto_resident_disabled=output.auto_resident_disabled,
            diagnostics=output.diagnostics,
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "officecli_version": active_settings.expected_version}

    @app.post(
        "/v1/officecli/skills/load",
        response_model=GuidanceResponse,
        operation_id="load_officecli_skill",
        description=(
            "Load the installed author's guides for reading, creating and modifying Word, Excel, or PowerPoint files. "
            "Omit skill for the official catalog; skill selects a guide and its reference manifest; path reads one bundled reference. "
            "The installed guide owns the workflow and delivery rules."
        ),
    )
    def load_officecli_skill(
        request: SkillRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> GuidanceResponse:
        if request.path and not request.skill:
            raise HTTPException(status_code=422, detail="A reference path requires a skill name")
        arguments = ["load_skill"]
        if request.skill:
            arguments.append(request.skill)
        if request.path:
            arguments.extend(["--path", request.path])
        return guidance_response_for(authorization, *arguments)

    @app.post(
        "/v1/officecli/help",
        response_model=GuidanceResponse,
        operation_id="get_officecli_help",
        description=(
            "Discover installed OfficeCLI capabilities for DOCX, XLSX, or PPTX: format catalog, "
            "element details, or verb-specific help. The installed CLI owns the catalog; do not guess "
            "command syntax."
        ),
    )
    def get_officecli_help(
        request: HelpRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> GuidanceResponse:
        if request.topic == "workflow":
            authenticated_bearer(authorization)
            return official_workflow()
        return guidance_response_for(authorization, *help_arguments(request.topic))

    @app.post(
        "/v1/officecli/render", operation_id="render_office_file",
        response_class=Response,
        responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
        description=(
            "Run the installed author's screenshot renderer and return an image to your vision context through native OpenWebUI. "
            "Use grid for a whole DOCX/PPTX contact sheet, or inspect a page/slide. "
            "For DOCX pagination use grid: the installed HTML renderer's single-page-1 shortcut skips pagination and can show false overflow. "
            "Fix confirmed layout problems and re-render as the loaded skill requires. "
            "Without range, XLSX shows its active sheet; use a sheet-qualified range for a targeted view. "
            "The render belongs to the requested file_id; any source.ext label is temporary. "
            "Use the image to verify the original task, then finish that task with its final attachment. "
            "The original file is unchanged. A failed render is not a visual pass; disclose 'not visually verified'."
        ),
    )
    def render_office_file(
        request: RenderOfficeRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        bearer = authenticated_bearer(authorization)
        if request.format == "xlsx" and request.page != 1:
            raise HTTPException(status_code=422, detail="XLSX screenshot covers the active sheet only; page is not a sheet selector")
        if not render_slot.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="A screenshot is already running; retry after it finishes")
        try:
            with TemporaryDirectory(prefix="officecli-render-") as directory:
                source = Path(directory) / f"source.{request.format}"
                output = Path(directory) / "preview.png"
                openwebui.download(request.file_id, bearer, source)
                arguments = ["view", str(source), "screenshot", "-o", str(output)]
                if request.grid is not None:
                    arguments.extend(["--grid", str(request.grid)])
                elif request.format != "xlsx":
                    arguments.extend(["--page", str(request.page)])
                if request.range is not None:
                    arguments.extend(["--range", request.range])
                officecli.run(*arguments)
                if not output.is_file():
                    raise OfficeCliFailure("OfficeCLI did not produce a screenshot; document is not visually verified")
                return Response(checked_png(output.read_bytes()), media_type="image/png",
                    headers={"Cache-Control": "no-store"})
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            raise _http_error(error) from error
        finally:
            render_slot.release()

    @app.post(
        "/v1/officecli/documents/inspect",
        response_model=InspectionResponse,
        operation_id="inspect_office_document",
        description=(
            "Read the single nearest DOCX attachment from the native current-message ancestry and return "
            "official view output, or query/get for native objects. "
            "Query selectors discover actual paths; get reads one path with bounded depth. Follow query pagination. When that message has "
            "multiple DOCX attachments, use an explicit file_id."
        ),
    )
    def inspect_office_document(
        request: InspectOfficeDocumentRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[
            str | None, Header(alias="X-OpenWebUI-Message-Id")
        ] = None,
    ) -> InspectionResponse:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(
            chat_id, message_id
        )
        try:
            source_file_id = (
                request.file_id
                or openwebui.resolve_nearest_docx_attachment(
                    native_chat_id, native_message_id, bearer
                )
            )
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                source = Path(directory) / "source.docx"
                openwebui.download(source_file_id, bearer, source)
                payload = request.command_payload
                annotated_output = officecli.run(*object_arguments(str(source), payload))
                result = _inspection_result(annotated_output, payload)
                auto_resident_disabled = annotated_output.auto_resident_disabled
                result = bounded_result(result, payload)
                result_sha256 = sha256(
                    json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            raise _http_error(error) from error
        return InspectionResponse(
            source=f"officecli v{active_settings.expected_version}",
            file_id=source_file_id,
            officecli_result=result,
            officecli_result_sha256=result_sha256,
            auto_resident_disabled=auto_resident_disabled,
        )

    @app.post(
        "/v1/officecli/spreadsheets/inspect",
        response_model=InspectionResponse,
        operation_id="inspect_office_spreadsheet",
        description=(
            "Inspect XLSX structure first (default outline). Use command=query with selector=picture/chart/etc "
            "to discover actual object paths across ALL sheets; use command=get with path and depth=0 for properties. "
            "Follow query pagination until next_offset is null. Then read only a needed sheet range "
            "with mode=text and range=Sheet1!A1:H30. Use explicit file_id for multiple attachments. "
            "Large results provide continuation offsets; follow pagination to recover complete native output. "
            "Use returned structure and content to answer the user's request."
        ),
    )
    def inspect_office_spreadsheet(
        request: InspectSpreadsheetRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[
            str | None, Header(alias="X-OpenWebUI-Message-Id")
        ] = None,
    ) -> InspectionResponse:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(
            chat_id, message_id
        )
        try:
            source_file_id = (
                request.file_id
                or openwebui.resolve_nearest_xlsx_attachment(
                    native_chat_id, native_message_id, bearer
                )
            )
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                source = Path(directory) / "source.xlsx"
                openwebui.download(source_file_id, bearer, source)
                payload = request.command_payload
                if payload.command == "view":
                    if payload.range and payload.mode != "text":
                        raise HTTPException(status_code=422, detail="range requires mode=text")
                    if payload.mode == "text" and not payload.range:
                        raise HTTPException(status_code=422, detail="text mode requires a sheet-qualified range; use outline first")
                    arguments = object_arguments(str(source), payload)
                    if payload.range:
                        arguments.extend(["--range", payload.range])
                else:
                    if payload.range:
                        raise HTTPException(status_code=422, detail="range is only supported for view")
                    arguments = object_arguments(str(source), payload)
                output = officecli.run(*arguments)
                result = bounded_result(_inspection_result(output, payload), payload)
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            raise _http_error(error) from error
        return InspectionResponse(
            source=f"officecli v{active_settings.expected_version}",
            file_id=source_file_id,
            officecli_result=result,
            officecli_result_sha256=output.content_sha256,
            auto_resident_disabled=output.auto_resident_disabled,
        )

    @app.post(
        "/v1/officecli/documents/apply-batch",
        response_model=ApplyResponse,
        operation_id="apply_office_batch",
        description=AUTHOR_WORKFLOW_TRIGGER + (
            "Complete a requested DOCX edit after inspection: apply official OfficeCLI batch items to "
            "the single nearest native DOCX attachment, validate it, and attach the resulting DOCX to this "
            "assistant message. Omit file_id only when that attachment is unambiguous; otherwise use an "
            "explicit file_id rather than guessing. Execute the edit, then verify the published result."
        ),
    )
    def apply_office_batch(
        request: ApplyOfficeBatchRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[
            str | None, Header(alias="X-OpenWebUI-Message-Id")
        ] = None,
    ) -> ApplyResponse:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(
            chat_id, message_id
        )

        native_file: dict[str, Any] | None = None
        try:
            source_file_id = (
                request.file_id
                or openwebui.resolve_nearest_docx_attachment(
                    native_chat_id, native_message_id, bearer
                )
            )
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                workspace = Path(directory)
                source_path = workspace / "source-input.docx"
                result_path = workspace / "result.docx"
                source_after_path = workspace / "source-after-check.docx"
                openwebui.download(source_file_id, bearer, source_path)
                source_sha256 = sha256(source_path.read_bytes()).hexdigest()
                result_path.write_bytes(source_path.read_bytes())

                batch_output = officecli.run(
                    "batch",
                    str(result_path),
                    "--stop-on-error",
                    "--json",
                    input_text=json.dumps(
                        request.commands, ensure_ascii=False, separators=(",", ":")
                    ),
                )
                batch_result = _officecli_json(batch_output, "batch")
                validation_output = officecli.run(
                    "validate", str(result_path), "--json"
                )
                validation_result = _officecli_json(validation_output, "validate")

                if not result_path.is_file() or result_path.stat().st_size == 0:
                    raise OfficeCliFailure("officecli did not leave a DOCX result")
                result_sha256 = sha256(result_path.read_bytes()).hexdigest()
                if result_sha256 == source_sha256:
                    raise OfficeCliFailure("officecli result bytes did not change")

                openwebui.download(source_file_id, bearer, source_after_path)
                source_bytes_preserved = (
                    sha256(source_after_path.read_bytes()).hexdigest() == source_sha256
                )
                if not source_bytes_preserved:
                    raise OpenWebUiFailure(
                        "source file bytes changed during the request"
                    )

                native_file = openwebui.upload(result_path, request.output_name, bearer)
                openwebui.attach(native_chat_id, native_message_id, native_file, bearer)
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            if native_file and isinstance(native_file.get("id"), str):
                try:
                    openwebui.delete(native_file["id"], bearer)
                except OpenWebUiFailure:
                    pass
            raise _http_error(error) from error

        return ApplyResponse(
            source=f"officecli v{active_settings.expected_version}",
            source_file_id=source_file_id,
            result_file_id=native_file["id"],
            result_file=native_file,
            batch_result=batch_result,
            validation_result=validation_result,
            source_sha256=source_sha256,
            result_sha256=result_sha256,
            source_bytes_preserved=True,
            auto_resident_disabled=batch_output.auto_resident_disabled
            and validation_output.auto_resident_disabled,
            bounded_processes_completed=True,
        )

    @app.post(
        "/v1/officecli/documents/create",
        response_model=CreateResponse,
        operation_id="create_office_document",
        description=AUTHOR_WORKFLOW_TRIGGER + (
            "Create a new DOCX from the current chat request using official OfficeCLI create and batch, "
            "validate it, and attach the resulting DOCX to this assistant message. Use this only when the "
            "user asks for a new document rather than an edit of an attached DOCX. "
            "Use exact help for properties before this operation."
        ),
    )
    def create_office_document(
        request: CreateOfficeDocumentRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[
            str | None, Header(alias="X-OpenWebUI-Message-Id")
        ] = None,
    ) -> CreateResponse:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(
            chat_id, message_id
        )

        native_file: dict[str, Any] | None = None
        try:
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                result_path = Path(directory) / "created.docx"
                create_output = officecli.run(
                    "create", str(result_path), "--locale", "en-US", "--json"
                )
                create_result = _officecli_json(create_output, "create")
                batch_output = officecli.run(
                    "batch",
                    str(result_path),
                    "--stop-on-error",
                    "--json",
                    input_text=json.dumps(
                        request.commands, ensure_ascii=False, separators=(",", ":")
                    ),
                )
                batch_result = _officecli_json(batch_output, "batch")
                validation_output = officecli.run(
                    "validate", str(result_path), "--json"
                )
                validation_result = _officecli_json(validation_output, "validate")

                if not result_path.is_file() or result_path.stat().st_size == 0:
                    raise OfficeCliFailure("officecli did not leave a DOCX result")
                result_sha256 = sha256(result_path.read_bytes()).hexdigest()
                native_file = openwebui.upload(result_path, request.output_name, bearer)
                openwebui.attach(native_chat_id, native_message_id, native_file, bearer)
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            if native_file and isinstance(native_file.get("id"), str):
                try:
                    openwebui.delete(native_file["id"], bearer)
                except OpenWebUiFailure:
                    pass
            raise _http_error(error) from error

        return CreateResponse(
            source=f"officecli v{active_settings.expected_version}",
            result_file_id=native_file["id"],
            result_file=native_file,
            create_result=create_result,
            batch_result=batch_result,
            validation_result=validation_result,
            result_sha256=result_sha256,
            auto_resident_disabled=(
                create_output.auto_resident_disabled
                and batch_output.auto_resident_disabled
                and validation_output.auto_resident_disabled
            ),
            bounded_processes_completed=True,
        )

    @app.post(
        "/v1/officecli/spreadsheets/create",
        response_model=CreateResponse,
        operation_id="create_office_spreadsheet",
        description=AUTHOR_WORKFLOW_TRIGGER + (
            "Create, batch, validate, and attach a new XLSX from the chat request. "
            "The workbook starts with Sheet1; address a cell as /Sheet1/A1, not as "
            "/sheet[Sheet1]/cell[A1]. Continue changes with "
            "apply_office_spreadsheet_batch on the returned attachment."
        ),
    )
    def create_office_spreadsheet(
        request: CreateSpreadsheetRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[
            str | None, Header(alias="X-OpenWebUI-Message-Id")
        ] = None,
    ) -> CreateResponse:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(
            chat_id, message_id
        )
        native_file: dict[str, Any] | None = None
        try:
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                result_path = Path(directory) / "created.xlsx"
                create_output = officecli.run(
                    "create", str(result_path), "--locale", "en-US", "--json"
                )
                create_result = _officecli_json(create_output, "create")
                batch_output = officecli.run(
                    "batch",
                    str(result_path),
                    "--stop-on-error",
                    "--json",
                    input_text=json.dumps(
                        request.commands,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                )
                batch_result = _officecli_json(batch_output, "batch")
                validation_output = officecli.run(
                    "validate", str(result_path), "--json"
                )
                validation_result = _officecli_json(validation_output, "validate")
                if not result_path.is_file() or result_path.stat().st_size == 0:
                    raise OfficeCliFailure("officecli did not leave an XLSX result")
                result_sha256 = sha256(result_path.read_bytes()).hexdigest()
                native_file = openwebui.upload(
                    result_path,
                    request.output_name,
                    bearer,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                openwebui.attach(
                    native_chat_id,
                    native_message_id,
                    native_file,
                    bearer,
                    "updated.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            if native_file and isinstance(native_file.get("id"), str):
                try:
                    openwebui.delete(native_file["id"], bearer)
                except OpenWebUiFailure:
                    pass
            raise _http_error(error) from error
        return CreateResponse(
            source=f"officecli v{active_settings.expected_version}",
            result_file_id=native_file["id"],
            result_file=native_file,
            create_result=create_result,
            batch_result=batch_result,
            validation_result=validation_result,
            result_sha256=result_sha256,
            auto_resident_disabled=(
                create_output.auto_resident_disabled
                and batch_output.auto_resident_disabled
                and validation_output.auto_resident_disabled
            ),
            bounded_processes_completed=True,
        )

    @app.post(
        "/v1/officecli/spreadsheets/apply-batch",
        response_model=ApplyResponse,
        operation_id="apply_office_spreadsheet_batch",
        description=AUTHOR_WORKFLOW_TRIGGER + "Edit, validate, and attach the single nearest native XLSX attachment.",
    )
    def apply_office_spreadsheet_batch(
        request: ApplySpreadsheetBatchRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[
            str | None, Header(alias="X-OpenWebUI-Message-Id")
        ] = None,
    ) -> ApplyResponse:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(
            chat_id, message_id
        )
        native_file: dict[str, Any] | None = None
        try:
            source_file_id = (
                request.file_id
                or openwebui.resolve_nearest_xlsx_attachment(
                    native_chat_id, native_message_id, bearer
                )
            )
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                workspace = Path(directory)
                source = workspace / "source-input.xlsx"
                result = workspace / "result.xlsx"
                source_after = workspace / "source-after-check.xlsx"
                openwebui.download(source_file_id, bearer, source)
                source_sha256 = sha256(source.read_bytes()).hexdigest()
                result.write_bytes(source.read_bytes())
                batch_output = officecli.run(
                    "batch",
                    str(result),
                    "--stop-on-error",
                    "--json",
                    input_text=json.dumps(
                        request.commands, ensure_ascii=False, separators=(",", ":")
                    ),
                )
                batch_result = _officecli_json(batch_output, "batch")
                validation_output = officecli.run("validate", str(result), "--json")
                validation_result = _officecli_json(validation_output, "validate")
                if not result.is_file() or result.stat().st_size == 0:
                    raise OfficeCliFailure("officecli did not leave an XLSX result")
                result_sha256 = sha256(result.read_bytes()).hexdigest()
                if result_sha256 == source_sha256:
                    raise OfficeCliFailure("officecli result bytes did not change")
                openwebui.download(source_file_id, bearer, source_after)
                if sha256(source_after.read_bytes()).hexdigest() != source_sha256:
                    raise OpenWebUiFailure(
                        "source file bytes changed during the request"
                    )
                native_file = openwebui.upload(
                    result,
                    request.output_name,
                    bearer,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                openwebui.attach(
                    native_chat_id,
                    native_message_id,
                    native_file,
                    bearer,
                    "updated.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            if native_file and isinstance(native_file.get("id"), str):
                try:
                    openwebui.delete(native_file["id"], bearer)
                except OpenWebUiFailure:
                    pass
            raise _http_error(error) from error
        return ApplyResponse(
            source=f"officecli v{active_settings.expected_version}",
            source_file_id=source_file_id,
            result_file_id=native_file["id"],
            result_file=native_file,
            batch_result=batch_result,
            validation_result=validation_result,
            source_sha256=source_sha256,
            result_sha256=result_sha256,
            source_bytes_preserved=True,
            auto_resident_disabled=batch_output.auto_resident_disabled
            and validation_output.auto_resident_disabled,
            bounded_processes_completed=True,
        )

    @app.post(
        "/v1/officecli/presentations/inspect",
        response_model=InspectionResponse,
        operation_id="inspect_office_presentation",
        description=(
            "Inspect the single nearest native PPTX attachment with the official OfficeCLI "
            "query selector (shape, picture, chart, table, etc.) or get path with depth=0. "
            "Follow query pagination. Includes stable paths, current text, and formatting required "
            "for an existing-shape edit. Validate returns native findings even when the PPTX "
            "fails validation; explain those findings to the user before choosing a repair path."
        ),
    )
    def inspect_office_presentation(
        request: InspectPresentationRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[
            str | None, Header(alias="X-OpenWebUI-Message-Id")
        ] = None,
    ) -> InspectionResponse:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(chat_id, message_id)
        try:
            source_file_id = (
                request.file_id
                or openwebui.resolve_nearest_pptx_attachment(
                    native_chat_id, native_message_id, bearer
                )
            )
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                source = Path(directory) / "source.pptx"
                openwebui.download(source_file_id, bearer, source)
                payload = request.command_payload
                output = officecli.run(*object_arguments(str(source), payload))
                result = bounded_result(
                    _officecli_json(output, "validate", allow_failed_validation=True)
                    if payload.command == "validate" else _inspection_result(output, payload),
                    payload,
                )
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            raise _http_error(error) from error
        return InspectionResponse(
            source=f"officecli v{active_settings.expected_version}",
            file_id=source_file_id,
            officecli_result=result,
            officecli_result_sha256=output.content_sha256,
            auto_resident_disabled=output.auto_resident_disabled,
        )

    @app.post(
        "/v1/officecli/presentations/create",
        response_model=CreateResponse,
        operation_id="create_office_presentation",
        description=AUTHOR_WORKFLOW_TRIGGER + (
            "Create a blank PPTX only when there is no PPTX source or the user explicitly "
            "requests an independent presentation. An attached corporate template or previous "
            "version is a source for apply_office_presentation_batch, not this operation. "
            "Use official OfficeCLI create and batch, "
            "validate it, and attach the resulting PPTX to this assistant message. Add each new slide "
            "at the document root / before adding content under /slide[N]; /presentation is not a valid "
            "parent. Consult exact property help. A picture may use only the "
            "attachment://image source, which resolves exactly one native image attachment in this chat."
        ),
    )
    def create_office_presentation(
        request: CreatePresentationRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[
            str | None, Header(alias="X-OpenWebUI-Message-Id")
        ] = None,
    ) -> CreateResponse:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(chat_id, message_id)
        native_file: dict[str, Any] | None = None
        try:
            if (
                request.source_intent != "new_independent_presentation"
                and openwebui.has_nearest_pptx_attachment(
                    native_chat_id, native_message_id, bearer
                )
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "A PPTX is attached in this chat. Use apply_office_presentation_batch "
                        "to preserve its template and edit the latest version. Create a blank "
                        "presentation only if the user explicitly requested an independent file; "
                        "then set source_intent=new_independent_presentation."
                    ),
                )
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                result = Path(directory) / "created.pptx"
                commands = _materialize_presentation_images(
                    request.commands,
                    Path(directory),
                    openwebui,
                    native_chat_id,
                    native_message_id,
                    bearer,
                )
                create_output = officecli.run(
                    "create", str(result), "--locale", "en-US", "--json"
                )
                create_result = _officecli_json(create_output, "create")
                batch_output = officecli.run(
                    "batch",
                    str(result),
                    "--stop-on-error",
                    "--json",
                    input_text=json.dumps(
                        commands, ensure_ascii=False, separators=(",", ":")
                    ),
                )
                batch_result = _officecli_json(batch_output, "batch")
                validation_output = officecli.run("validate", str(result), "--json")
                validation_result = _officecli_json(validation_output, "validate")
                if not result.is_file() or result.stat().st_size == 0:
                    raise OfficeCliFailure("officecli did not leave a PPTX result")
                result_sha256 = sha256(result.read_bytes()).hexdigest()
                native_file = openwebui.upload(
                    result, request.output_name, bearer, PPTX_CONTENT_TYPE
                )
                openwebui.attach(
                    native_chat_id,
                    native_message_id,
                    native_file,
                    bearer,
                    "updated.pptx",
                    PPTX_CONTENT_TYPE,
                )
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            if native_file and isinstance(native_file.get("id"), str):
                try:
                    openwebui.delete(native_file["id"], bearer)
                except OpenWebUiFailure:
                    pass
            raise _http_error(error) from error
        return CreateResponse(
            source=f"officecli v{active_settings.expected_version}",
            result_file_id=native_file["id"],
            result_file=native_file,
            create_result=create_result,
            batch_result=batch_result,
            validation_result=validation_result,
            result_sha256=result_sha256,
            auto_resident_disabled=(
                create_output.auto_resident_disabled
                and batch_output.auto_resident_disabled
                and validation_output.auto_resident_disabled
            ),
            bounded_processes_completed=True,
        )

    @app.post(
        "/v1/officecli/presentations/apply-batch",
        response_model=ApplyResponse,
        operation_id="apply_office_presentation_batch",
        description=AUTHOR_WORKFLOW_TRIGGER + (
            "Edit a copy of the nearest native PPTX template or previous version, preserving "
            "unrequested slides, media, and editable objects. Validate and attach the result. "
            "If the source already fails OfficeCLI validation, no edit is published; "
            "explain the findings and offer a valid earlier source or repair of a copy. "
            "To add a slide in the source style, OfficeCLI batch can clone it with "
            "an add item using parent=/ and from=/slide[N]; inspect the copied shape paths "
            "before editing because shape IDs can change. "
            "Verify the published "
            "result before completion. A picture may use only "
            "attachment://image, which resolves exactly one native image attachment in this chat."
        ),
    )
    def apply_office_presentation_batch(
        request: ApplyPresentationBatchRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[
            str | None, Header(alias="X-OpenWebUI-Message-Id")
        ] = None,
    ) -> ApplyResponse:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(chat_id, message_id)
        native_file: dict[str, Any] | None = None
        try:
            source_file_id = (
                request.file_id
                or openwebui.resolve_nearest_pptx_attachment(
                    native_chat_id, native_message_id, bearer
                )
            )
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                workspace = Path(directory)
                source = workspace / "source-input.pptx"
                result = workspace / "result.pptx"
                source_after = workspace / "source-after-check.pptx"
                openwebui.download(source_file_id, bearer, source)
                source_sha256 = sha256(source.read_bytes()).hexdigest()
                source_validation = _officecli_json(
                    officecli.run("validate", str(source), "--json"),
                    "validate",
                    allow_failed_validation=True,
                )
                if source_validation["success"] is False:
                    raise HTTPException(
                        status_code=422,
                        detail=_invalid_pptx_source_detail(source_validation),
                    )
                result.write_bytes(source.read_bytes())
                commands = _materialize_presentation_images(
                    request.commands,
                    workspace,
                    openwebui,
                    native_chat_id,
                    native_message_id,
                    bearer,
                )
                batch_output = officecli.run(
                    "batch",
                    str(result),
                    "--stop-on-error",
                    "--json",
                    input_text=json.dumps(
                        commands, ensure_ascii=False, separators=(",", ":")
                    ),
                )
                batch_result = _officecli_json(batch_output, "batch")
                validation_output = officecli.run("validate", str(result), "--json")
                validation_result = _officecli_json(validation_output, "validate")
                if not result.is_file() or result.stat().st_size == 0:
                    raise OfficeCliFailure("officecli did not leave a PPTX result")
                result_sha256 = sha256(result.read_bytes()).hexdigest()
                if result_sha256 == source_sha256:
                    raise OfficeCliFailure("officecli result bytes did not change")
                openwebui.download(source_file_id, bearer, source_after)
                if sha256(source_after.read_bytes()).hexdigest() != source_sha256:
                    raise OpenWebUiFailure(
                        "source file bytes changed during the request"
                    )
                native_file = openwebui.upload(
                    result, request.output_name, bearer, PPTX_CONTENT_TYPE
                )
                openwebui.attach(
                    native_chat_id,
                    native_message_id,
                    native_file,
                    bearer,
                    "updated.pptx",
                    PPTX_CONTENT_TYPE,
                )
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            if native_file and isinstance(native_file.get("id"), str):
                try:
                    openwebui.delete(native_file["id"], bearer)
                except OpenWebUiFailure:
                    pass
            raise _http_error(error) from error
        return ApplyResponse(
            source=f"officecli v{active_settings.expected_version}",
            source_file_id=source_file_id,
            result_file_id=native_file["id"],
            result_file=native_file,
            batch_result=batch_result,
            validation_result=validation_result,
            source_sha256=source_sha256,
            result_sha256=result_sha256,
            source_bytes_preserved=True,
            auto_resident_disabled=batch_output.auto_resident_disabled
            and validation_output.auto_resident_disabled,
            bounded_processes_completed=True,
        )

    native_openapi = app.openapi

    def openapi_with_official_workflow():
        if app.openapi_schema is None:
            workflow = official_workflow()
            schema = native_openapi()
            operation = schema["paths"]["/v1/officecli/help"]["post"]
            operation["description"] += (
                "\n\nInstalled OfficeCLI workflow (applies to all Office tools):\n"
                + workflow.content
                + "\n\nOpen WebUI transport: CLI examples map to the named inspect/create/apply/render tools "
                "and their schemas; use native file_id instead of host paths. Each create/apply saves "
                "a copy and returns result_file_id/download_url; separate save/close is unnecessary."
            )
        return app.openapi_schema

    app.openapi = openapi_with_official_workflow
    return app


app = create_app()
