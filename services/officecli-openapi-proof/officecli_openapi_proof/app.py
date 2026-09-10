from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from .config import Settings, load_settings
from .officecli import OfficeCliExecutor, OfficeCliFailure, OfficeCliOutput, SubprocessOfficeCliExecutor
from .openwebui_client import HttpOpenWebUiClient, OpenWebUiClient, OpenWebUiFailure


class SkillRequest(BaseModel):
    skill: Literal["word"]


class HelpRequest(BaseModel):
    topic: Literal["docx", "docx paragraph", "docx set paragraph", "docx view"]


class GuidanceResponse(BaseModel):
    source: str
    command: list[str]
    content: str
    content_sha256: str
    auto_resident_disabled: bool


class InspectCommandPayload(BaseModel):
    command: Literal["view"]
    mode: Literal["annotated"]


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
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9-]{1,128}", value):
            return value
        return None


class InspectOfficeDocumentRequest(NativeDocxReference):
    command_payload: InspectCommandPayload


class ApplyOfficeBatchRequest(NativeDocxReference):
    output_name: str = Field(min_length=6, max_length=120)
    commands: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=64,
        description=(
            "Official OfficeCLI batch items. Each item has a bare verb in command and its "
            "arguments as sibling fields, for example command=set with path and props. "
            "Obtain the exact command details from OfficeCLI help before calling."
        ),
    )

    @field_validator("output_name")
    @classmethod
    def output_name_is_a_plain_docx_name(cls, value: str) -> str:
        if Path(value).name != value or not value.lower().endswith(".docx"):
            raise ValueError("output_name must be a plain .docx filename")
        return value


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


HELP_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "docx": ("help", "docx"),
    "docx paragraph": ("help", "docx", "paragraph"),
    "docx set paragraph": ("help", "docx", "set", "paragraph"),
    "docx view": ("help", "docx", "view"),
}


def _officecli_json(output: OfficeCliOutput, operation: str) -> Any:
    try:
        parsed = json.loads(output.text)
    except json.JSONDecodeError as error:
        raise OfficeCliFailure(f"officecli {operation} did not return JSON") from error
    if not isinstance(parsed, dict) or parsed.get("success") is not True:
        raise OfficeCliFailure(f"officecli {operation} reported failure")
    return parsed


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer ") or len(authorization) <= len("Bearer "):
        raise HTTPException(status_code=401, detail="a forwarded OpenWebUI bearer session is required")
    return authorization


def _http_error(error: Exception) -> HTTPException:
    return HTTPException(status_code=502, detail=str(error))


def _native_chat_message_ids(chat_id: str | None, message_id: str | None) -> tuple[str, str]:
    if not chat_id or not message_id:
        raise HTTPException(status_code=400, detail="native chat and message ids are required")
    return chat_id, message_id


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

    def guidance_response_for(authorization: str | None, *arguments: str) -> GuidanceResponse:
        _bearer(authorization)
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
        description="Load the installed official OfficeCLI DOCX skill before planning DOCX work.",
    )
    def load_officecli_skill(
        request: SkillRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> GuidanceResponse:
        return guidance_response_for(authorization, "load_skill", request.skill)

    @app.post(
        "/v1/officecli/help",
        response_model=GuidanceResponse,
        operation_id="get_officecli_help",
        description="Read installed OfficeCLI help for an allowed DOCX topic; do not guess command syntax.",
    )
    def get_officecli_help(
        request: HelpRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> GuidanceResponse:
        return guidance_response_for(authorization, *HELP_ARGUMENTS[request.topic])

    @app.post(
        "/v1/officecli/documents/inspect",
        response_model=InspectionResponse,
        operation_id="inspect_office_document",
        description=(
            "Read the nearest DOCX attachment from the native current-message ancestry and return "
            "official annotated OfficeCLI output. Use its exact paragraph path to plan an edit."
        ),
    )
    def inspect_office_document(
        request: InspectOfficeDocumentRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[str | None, Header(alias="X-OpenWebUI-Message-Id")] = None,
    ) -> InspectionResponse:
        bearer = _bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(chat_id, message_id)
        try:
            source_file_id = request.file_id or openwebui.resolve_nearest_docx_attachment(
                native_chat_id, native_message_id, bearer
            )
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                source = Path(directory) / "source.docx"
                openwebui.download(source_file_id, bearer, source)
                output = officecli.run("view", str(source), request.command_payload.mode, "--json")
                result = _officecli_json(output, "view")
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
        description=(
            "Complete a requested DOCX edit after inspection: apply official OfficeCLI batch items to "
            "the nearest native DOCX attachment, validate it, and attach the resulting DOCX to this "
            "assistant message. Omit file_id rather than guessing it. This is the final execution "
            "operation; do not replace it with a textual explanation."
        ),
    )
    def apply_office_batch(
        request: ApplyOfficeBatchRequest,
        authorization: Annotated[str | None, Header()] = None,
        chat_id: Annotated[str | None, Header(alias="X-OpenWebUI-Chat-Id")] = None,
        message_id: Annotated[str | None, Header(alias="X-OpenWebUI-Message-Id")] = None,
    ) -> ApplyResponse:
        bearer = _bearer(authorization)
        native_chat_id, native_message_id = _native_chat_message_ids(chat_id, message_id)

        native_file: dict[str, Any] | None = None
        try:
            source_file_id = request.file_id or openwebui.resolve_nearest_docx_attachment(
                native_chat_id, native_message_id, bearer
            )
            with TemporaryDirectory(prefix="officecli-proof-") as directory:
                workspace = Path(directory)
                source = workspace / "source.docx"
                result = workspace / request.output_name
                source_after = workspace / "source-after.docx"
                openwebui.download(source_file_id, bearer, source)
                source_sha256 = sha256(source.read_bytes()).hexdigest()
                result.write_bytes(source.read_bytes())

                batch_output = officecli.run(
                    "batch",
                    str(result),
                    "--stop-on-error",
                    "--json",
                    input_text=json.dumps(request.commands, ensure_ascii=False, separators=(",", ":")),
                )
                batch_result = _officecli_json(batch_output, "batch")
                validation_output = officecli.run("validate", str(result), "--json")
                validation_result = _officecli_json(validation_output, "validate")

                if not result.is_file() or result.stat().st_size == 0:
                    raise OfficeCliFailure("officecli did not leave a DOCX result")
                result_sha256 = sha256(result.read_bytes()).hexdigest()
                if result_sha256 == source_sha256:
                    raise OfficeCliFailure("officecli result bytes did not change")

                openwebui.download(source_file_id, bearer, source_after)
                source_bytes_preserved = sha256(source_after.read_bytes()).hexdigest() == source_sha256
                if not source_bytes_preserved:
                    raise OpenWebUiFailure("source file bytes changed during the request")

                native_file = openwebui.upload(result, request.output_name, bearer)
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

    return app


app = create_app()
