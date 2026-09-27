from __future__ import annotations

import json
import re
import subprocess
import sys
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
from .docx_normalization import normalize_known_noncanonical_docx
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
PPTX_TABLE_CELL_KEY = re.compile(r"r[1-9][0-9]*c[1-9][0-9]*")
PPTX_SLIDE_PATH = re.compile(r"^/slide\[([1-9][0-9]*)\](?:/|$)")


AUTHOR_WORKFLOW_TRIGGER = (
    "FIRST load_officecli_skill with the most specific official skill before creating or modifying "
    "this artifact, unless already loaded for it. Follow its content and visual delivery checks "
    "on result_file_id before reporting completion. "
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
    topic: str = Field(min_length=3, max_length=140, description=(
        "Installed CLI discovery: start with docx, xlsx, or pptx for the element catalog; "
        "then FORMAT ELEMENT or FORMAT VERB ELEMENT for exact properties and operations, "
        "e.g. xlsx picture, xlsx remove picture, docx table-cell, pptx chart. "
        "help lists all commands; FORMAT / lists document-level properties. Bare query/get/view/batch/validate/raw/raw-set returns command usage; FORMAT VERB lists its elements. Request only the needed topic."
    ))

    @field_validator("topic")
    @classmethod
    def official_help_topic(cls, value: str) -> str:
        help_arguments(value)
        return value


class GuidanceResponse(BaseModel):
    source: str
    command: list[str]
    content: str
    content_sha256: str
    auto_resident_disabled: bool


class InspectCommandPayload(ObjectReadPayload):
    mode: Literal["annotated", "outline", "text", "stats", "issues"] = "annotated"


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
    mode: Literal["outline", "text", "annotated", "stats", "issues"] = "outline"
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


class SpreadsheetCompositionSource(NativeXlsxReference):
    file_id: str = Field(min_length=1, max_length=128)
    target_sheet: str = Field(min_length=1, max_length=31)


class ComposeSpreadsheetsRequest(BaseModel):
    output_name: str = Field(min_length=6, max_length=120)
    sources: list[SpreadsheetCompositionSource] = Field(
        min_length=1, max_length=64,
        description="One native file_id and requested destination sheet name per source workbook. All sheets inside each source are stacked in their original order; no cell contents are needed here.",
    )
    require_all_attachments: bool = Field(
        default=True,
        description="Require every XLSX in the nearest user upload on this conversation branch. Generated assistant results do not replace the source set. Set false only when the user explicitly selects another source set or subset.",
    )

    @field_validator("output_name")
    @classmethod
    def plain_output_name(cls, value: str) -> str:
        if re.search(r"[/\\\x00-\x1f]", value) or not value.lower().endswith(".xlsx"):
            raise ValueError("output_name must be a plain .xlsx filename")
        return value

    @field_validator("sources")
    @classmethod
    def unique_sources_and_sheets(cls, value):
        if len({s.file_id for s in value}) != len(value):
            raise ValueError("Each source file must occur exactly once")
        if len({s.target_sheet.casefold() for s in value}) != len(value):
            raise ValueError("Destination sheet names must be unique")
        return value


class InspectPresentationCommandPayload(ObjectReadPayload):
    command: Literal["query", "get", "view", "validate", "raw"] = "query"
    mode: Literal["outline", "text", "annotated", "stats", "issues"] = "outline"
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
            "One ordered official OfficeCLI batch for the whole initial workbook (up to 256 items). "
            "A new XLSX already contains Sheet1. Reuse it by default; when the user "
            "requests a sheet name, rename it using the installed xlsx sheet help. "
            "Include new sheets, cell "
            "values, and cross-sheet formulas in this single batch. A failed batch rolls "
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
    commands: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=256,
        description=(
            "Ordered OfficeCLI batch items. For a minimal deck, first add a slide with parent /, "
            "type slide, and layout blank; then add its text shape under /slide[1]. Shape geometry "
            "must use explicit length units, for example x=2cm, y=7cm, width=29cm, height=3cm. Never use "
            "/presentation as the parent."
        ),
    )

    @field_validator("commands")
    @classmethod
    def translate_official_prop_alias(
        cls, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        normalized = _normalize_presentation_commands(value)
        _validate_presentation_create_order(normalized)
        return normalized

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
        if (
            command.get("command") == "set"
            and isinstance(command.get("path"), str)
            and "/table" in command["path"]
            and any(PPTX_TABLE_CELL_KEY.fullmatch(key) for key in props)
        ):
            raise ValueError(
                "PPTX table cells must be seeded in the table add command with the official "
                "data property; rNcN keys are not valid table set properties"
            )
    return normalized


def _validate_presentation_create_order(commands: list[dict[str, Any]]) -> None:
    """Reject a batch that would address a slide before that slide exists."""
    created_slides = 0
    for command in commands:
        if (
            command.get("command") == "add"
            and command.get("parent") == "/"
            and command.get("type") == "slide"
        ):
            created_slides += 1
            continue
        target = command.get("parent", command.get("path"))
        if not isinstance(target, str):
            continue
        match = PPTX_SLIDE_PATH.match(target)
        if match is not None and int(match.group(1)) > created_slides:
            raise ValueError(
                "PPTX create batch must add /slide[N] at the document root before adding "
                "content to that slide"
            )


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
    docx_normalization: dict[str, Any] | None = None

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


def _officecli_json(output: OfficeCliOutput, operation: str) -> Any:
    try:
        parsed = json.loads(output.text)
    except json.JSONDecodeError as error:
        raise OfficeCliFailure(f"officecli {operation} did not return JSON") from error
    if not isinstance(parsed, dict) or parsed.get("success") is not True:
        raise OfficeCliFailure(f"officecli {operation} reported failure")
    return parsed


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
    app = FastAPI(title="OfficeCLI OpenAPI proof", version="0.2.0")
    composition_slot = BoundedSemaphore(1)
    render_slot = BoundedSemaphore(1)

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
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "officecli_version": active_settings.expected_version}

    @app.post(
        "/v1/officecli/skills/load",
        response_model=GuidanceResponse,
        operation_id="load_officecli_skill",
        description=(
            "FIRST load the installed author's most specific skill before creating or modifying Word, Excel, or PowerPoint files. "
            "Omit skill for the official catalog; skill selects a guide and its reference manifest; path reads one bundled reference. "
            "Follow its help-first and delivery rules. Load one guide per artifact, once; do not stack or reload guides."
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
        return guidance_response_for(authorization, *help_arguments(request.topic))

    @app.post(
        "/v1/officecli/render", operation_id="render_office_file",
        response_class=Response,
        responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
        description=(
            "Run the installed author's screenshot renderer and return an image to your vision context through native OpenWebUI. "
            "Inspect one DOCX page or PPTX slide at a time; fix layout problems and re-render as the loaded skill requires. "
            "XLSX shows ONLY its active sheet; never claim all sheets were visually checked. "
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
                if request.format != "xlsx":
                    arguments.extend(["--page", str(request.page)])
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
            "official annotated output with table layout (view), or query/get for other native objects. "
            "Query selectors discover actual paths; get reads one path with bounded depth. Follow query pagination. When that message has "
            "multiple DOCX attachments, use an explicit file_id rather than guessing. For a fixed form, "
            "use only row and cell paths present in table_layout; do not infer extra rows."
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
                if payload.command == "view" and payload.mode == "annotated":
                    annotated_output = officecli.run("view", str(source), payload.mode, "--json")
                    table_layout_output = officecli.run("query", str(source), "table", "--json")
                    result = {
                        "annotated": _officecli_json(annotated_output, "view"),
                        "table_layout": _officecli_json(table_layout_output, "query"),
                    }
                    auto_resident_disabled = annotated_output.auto_resident_disabled and table_layout_output.auto_resident_disabled
                else:
                    annotated_output = officecli.run(*object_arguments(str(source), payload))
                    result = _officecli_json(annotated_output, payload.command)
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
            "Large cell results are withheld with an explicit notice, never silently truncated. "
            "Do not read all source cells into chat to combine workbooks."
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
                    arguments = ["view", str(source), payload.mode, "--json"]
                    if payload.range:
                        arguments.extend(["--range", payload.range])
                else:
                    if payload.range:
                        raise HTTPException(status_code=422, detail="range is only supported for view")
                    arguments = object_arguments(str(source), payload)
                output = officecli.run(*arguments)
                result = bounded_result(_officecli_json(output, payload.command), payload)
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
        "/v1/officecli/spreadsheets/compose",
        operation_id="compose_office_spreadsheets",
        description=AUTHOR_WORKFLOW_TRIGGER + (
            "Combine many native XLSX files into one workbook, one named destination sheet per source workbook. "
            "Stacks ALL daily sheets from each source in original order, preserving values, live formulas, "
            "dependencies, cached values, cell formatting, merged cells, and pictures. Original external links "
            "stay external and are reported; source errors are preserved, not invented or repaired. "
            "Use this source-backed operation for monthly consolidation instead of reading all cells or "
            "rewriting them into create commands. No inspect call is required merely to copy all data. "
            "Only file IDs and destination names are needed. Unsupported features fail before publication. "
            "Returns a compact verification receipt and attaches the workbook. For additional requested "
            "changes (e.g. remove pictures), inspect and apply to result_file_id, then verify the final result."
        ),
    )
    def compose_office_spreadsheets(
        request: ComposeSpreadsheetsRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[str | None, Header(alias="X-OpenWebUI-Message-Id")] = None,
    ) -> dict[str, Any]:
        bearer = authenticated_bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(chat_id, message_id)
        if not composition_slot.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="A workbook composition is already running. No files were changed; retry after it finishes.")
        native_file = None
        try:
            if request.require_all_attachments:
                attached = openwebui.resolve_nearest_xlsx_attachments(native_chat_id, native_message_id, bearer)
                expected = {f.file_id for f in attached}
                received = {s.file_id for s in request.sources}
                if expected != received:
                    raise HTTPException(status_code=422, detail={
                        "reason": "source_set_incomplete", "expected_count": len(expected),
                        "missing_file_ids": sorted(expected - received),
                        "unexpected_file_ids": sorted(received - expected),
                    })
            with TemporaryDirectory(prefix="officecli-compose-") as directory:
                workspace = Path(directory)
                plan = []
                source_hashes = {}
                total_bytes = 0
                for index, source in enumerate(request.sources):
                    path = workspace / f"source-{index:02}.xlsx"
                    openwebui.download(source.file_id, bearer, path)
                    total_bytes += path.stat().st_size
                    if total_bytes > 64 * 1024 * 1024:
                        raise HTTPException(status_code=422, detail="Combined source files exceed the 64 MiB processing limit")
                    source_hashes[source.file_id] = sha256(path.read_bytes()).hexdigest()
                    plan.append({"path": str(path), "target_sheet": source.target_sheet})
                result = workspace / "result.xlsx"
                plan_path = workspace / "plan.json"
                plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
                try:
                    completed = subprocess.run(
                        [sys.executable, "-m", "officecli_openapi_proof.xlsx_composition", str(plan_path), str(result)],
                        capture_output=True, text=True, encoding="utf-8", timeout=180, check=False,
                    )
                except subprocess.TimeoutExpired as error:
                    raise HTTPException(status_code=504, detail="Workbook composition exceeded 180 seconds; no result was published") from error
                if completed.returncode:
                    detail = json.loads(completed.stdout) if completed.stdout.strip().startswith("{") else {"reason": "composition_failed"}
                    raise HTTPException(status_code=422, detail=detail)
                receipt = json.loads(completed.stdout)
                if not result.is_file() or not receipt.get("verified"):
                    raise OfficeCliFailure("Composition did not produce a verified workbook")
                # Validate a copy: OfficeCLI may reconcile formula caches when opening/saving.
                audit = workspace / "validation.xlsx"
                audit.write_bytes(result.read_bytes())
                validation = _officecli_json(officecli.run("validate", str(audit), "--json"), "validate")
                source_after = workspace / "source-after-check.xlsx"
                for source in request.sources:
                    openwebui.download(source.file_id, bearer, source_after)
                    if sha256(source_after.read_bytes()).hexdigest() != source_hashes[source.file_id]:
                        raise OpenWebUiFailure("source file bytes changed during composition")
                result_hash = sha256(result.read_bytes()).hexdigest()
                native_file = openwebui.upload(result, request.output_name, bearer,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                openwebui.attach(native_chat_id, native_message_id, native_file, bearer,
                    request.output_name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except (OfficeCliFailure, OpenWebUiFailure, OSError) as error:
            if native_file and isinstance(native_file.get("id"), str):
                try:
                    openwebui.delete(native_file["id"], bearer)
                except OpenWebUiFailure:
                    pass
            raise _http_error(error) from error
        finally:
            composition_slot.release()
        return {"result_file_id": native_file["id"],
                "download_url": native_file_content_path(native_file["id"]),
                "result_sha256": result_hash,
                "receipt": receipt, "source_sha256": source_hashes,
                "validation_success": validation["success"],
                "source_bytes_preserved": True}

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
                normalization = normalize_known_noncanonical_docx(source_path, result_path)

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
            docx_normalization={
                "applied": normalization.applied,
                "changed_parts": list(normalization.changed_parts),
                "reordered_elements": normalization.reordered_elements,
                "removed_false_no_wrap": normalization.removed_false_no_wrap,
                "removed_vml_shapetype_type": normalization.removed_vml_shapetype_type,
            },
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
            "/sheet[Sheet1]/cell[A1]. Submit all initial work in one ordered "
            "batch. Reuse or rename the default sheet to satisfy the requested sheet names; "
            "add additional sheets only when requested. For follow-up edits or corrections, use "
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
            "for an existing-shape edit."
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
                result = bounded_result(_officecli_json(output, payload.command), payload)
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
            "Create a PPTX from the current chat request using official OfficeCLI create and batch, "
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
            "Edit, validate, and attach the single nearest native PPTX attachment. Verify the published "
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

    return app


app = create_app()
