from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import load_settings
from .officecli import OfficeCliExecutor, OfficeCliFailure, SubprocessOfficeCliExecutor


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


HELP_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "docx": ("help", "docx"),
    "docx paragraph": ("help", "docx", "paragraph"),
    "docx set paragraph": ("help", "docx", "set", "paragraph"),
    "docx view": ("help", "docx", "view"),
}


def create_app(executor: OfficeCliExecutor | None = None) -> FastAPI:
    settings = load_settings()
    officecli = executor or SubprocessOfficeCliExecutor(settings)
    app = FastAPI(title="OfficeCLI OpenAPI proof", version="0.1.0")

    def response_for(*arguments: str) -> GuidanceResponse:
        try:
            output = officecli.run(*arguments)
        except OfficeCliFailure as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return GuidanceResponse(
            source=f"officecli v{settings.expected_version}",
            command=list(output.command),
            content=output.text,
            content_sha256=output.content_sha256,
            auto_resident_disabled=output.auto_resident_disabled,
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "officecli_version": settings.expected_version}

    @app.post(
        "/v1/officecli/skills/load",
        response_model=GuidanceResponse,
        operation_id="load_officecli_skill",
    )
    def load_officecli_skill(request: SkillRequest) -> GuidanceResponse:
        return response_for("load_skill", request.skill)

    @app.post(
        "/v1/officecli/help",
        response_model=GuidanceResponse,
        operation_id="get_officecli_help",
    )
    def get_officecli_help(request: HelpRequest) -> GuidanceResponse:
        return response_for(*HELP_ARGUMENTS[request.topic])

    return app


app = create_app()
