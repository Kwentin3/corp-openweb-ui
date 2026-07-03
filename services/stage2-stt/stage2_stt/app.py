from __future__ import annotations

import json
import secrets
from uuid import uuid4

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import ValidationError

from stage2_stt.config import OutputProfile, SttConfigError, load_stt_config
from stage2_stt.contracts import (
    ArtifactAccessContextV1,
    MessageDocxExportRequestV1,
    MessageDocxExportResultV1,
    OpenWebUITranscriptionEnvelopeV1,
    PostProcessingRequestV1,
    PostProcessingResultV1,
    PostProcessingTemplateV1,
    PreparedAudioMetadataV1,
    PromptCatalogUserContextV1,
    SourceMediaMetadataV1,
    TranscriptResultV1,
    TranscriptionJobCreateResponseV1,
    TranscriptionJobV1,
    TranscriptionRuntimeCapabilitiesV1,
)
from stage2_stt.artifact_store import ArtifactStoreError, ArtifactStoreFactory
from stage2_stt.job_store import InMemoryTranscriptionJobStore, StoredTranscriptionJob
from stage2_stt.jobs import JobContext, create_transcription_job, request_cancel
from stage2_stt.lemonfox import LemonfoxProviderError
from stage2_stt.message_docx import MessageDocxExportError, MessageDocxExportService
from stage2_stt.post_processing import PostProcessingError, PostProcessingService
from stage2_stt.prompt_catalog import PromptCatalogError, PromptCatalogFactory
from stage2_stt.provider import SttProviderAdapterFactory
from stage2_stt.runtime import build_runtime_capabilities
from stage2_stt.storage import StorageModeError, resolve_storage_decision
from stage2_stt.transcript_store import TranscriptArtifactLinks, TranscriptStoreAdapter
from stage2_stt.validation import validate_prepared_audio


def create_app() -> FastAPI:
    app = FastAPI(title="OpenWebUI Stage 2 STT Backend", version="0.1.0")
    job_store = InMemoryTranscriptionJobStore()

    @app.get(
        "/stage2-api/transcription/capabilities",
        response_model=TranscriptionRuntimeCapabilitiesV1,
    )
    def transcription_capabilities() -> TranscriptionRuntimeCapabilitiesV1:
        try:
            config = load_stt_config()
            return build_runtime_capabilities(config)
        except (SttConfigError, StorageModeError) as exc:
            raise HTTPException(
                status_code=500,
                detail={"code": "stage2_stt_config_invalid", "message": str(exc)},
            ) from exc

    @app.post(
        "/stage2-api/transcription/jobs",
        response_model=TranscriptionJobCreateResponseV1,
    )
    async def create_transcription_job_route(
        prepared_audio: UploadFile = File(...),
        envelope: str = Form(...),
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> TranscriptionJobCreateResponseV1:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        parsed_envelope = _parse_envelope(envelope)
        output_profile = _resolve_output_profile(parsed_envelope, config.output_profile)

        audio_bytes = await prepared_audio.read()
        mime_type = prepared_audio.content_type
        if mime_type is None and parsed_envelope.file is not None:
            mime_type = parsed_envelope.file.mime_type
        if not mime_type:
            mime_type = "application/octet-stream"

        adapter = SttProviderAdapterFactory(config).create()
        capability = adapter.capabilities()
        validation = validate_prepared_audio(
            config=config,
            capability=capability,
            output_profile=output_profile,
            mime_type=mime_type,
            size_bytes=len(audio_bytes),
        )
        if not validation.accepted:
            raise HTTPException(
                status_code=422,
                detail=validation.error.model_dump() if validation.error else None,
            )

        if not config.lemonfox.has_api_key and not config.allow_stub_transcript:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "provider_auth_missing",
                    "message": (
                        "Live STT job routes require STAGE2_LEMONFOX_API_KEY "
                        "or explicit STAGE2_STT_ALLOW_STUB_TRANSCRIPT=true for probe mode"
                    ),
                    "retryable": False,
                },
            )

        storage = resolve_storage_decision(config)
        job_id = f"stt-{uuid4().hex}"
        job = create_transcription_job(
            config=config,
            job_id=job_id,
            source_media=SourceMediaMetadataV1(
                file_name=prepared_audio.filename,
                mime_type=mime_type,
                size_bytes=len(audio_bytes),
                stored=False,
            ),
            prepared_audio=PreparedAudioMetadataV1(
                output_profile=output_profile.value,
                mime_type=mime_type,
                size_bytes=len(audio_bytes),
                retention_days=config.prepared_audio_retention_days,
            ),
            storage_available=storage.available,
            context=JobContext(
                user_id=parsed_envelope.user_id,
                workspace_id=parsed_envelope.workspace_id,
            ),
        ).model_copy(
            update={
                "status": "processing",
                "selected_output_profile": output_profile.value,
            }
        )
        job_store.put(StoredTranscriptionJob(job=job))

        try:
            transcript = await adapter.transcribe_bytes(
                audio_bytes=audio_bytes,
                filename=prepared_audio.filename or "prepared-audio",
                mime_type=mime_type,
                output_profile=output_profile.value,
                live=config.lemonfox.has_api_key,
            )
        except LemonfoxProviderError as exc:
            failed_job = job.model_copy(update={"status": "failed", "error": exc.error})
            job_store.put(StoredTranscriptionJob(job=failed_job))
            raise HTTPException(
                status_code=502,
                detail={"job_id": failed_job.job_id, **exc.error.model_dump()},
            ) from exc

        result = transcript.model_copy(
            update={
                "job_id": job.job_id,
                "warnings": list(dict.fromkeys([*validation.warnings, *transcript.warnings])),
            }
        )
        completed_job = job.model_copy(update={"status": "completed"})
        transcript_ref = None
        artifact_warnings: list[str] = []
        try:
            artifact_store = ArtifactStoreFactory(config).create()
            transcript_store = TranscriptStoreAdapter(store=artifact_store, config=config)
            transcript_ref = transcript_store.put_transcript(
                result,
                TranscriptArtifactLinks(job=completed_job, envelope=parsed_envelope),
            )
            result = transcript_store.get_transcript(
                transcript_ref,
                _access_context_from_envelope(parsed_envelope),
            )
        except ArtifactStoreError as exc:
            artifact_warnings.append(exc.code)

        job_store.put(StoredTranscriptionJob(job=completed_job, result=result))
        return TranscriptionJobCreateResponseV1(
            job=completed_job,
            result=result,
            transcript_ref=transcript_ref,
            warnings=list(
                dict.fromkeys(
                    [*storage.warnings, *validation.warnings, *result.warnings, *artifact_warnings]
                )
            ),
        )

    @app.get(
        "/stage2-api/transcription/jobs/{job_id}",
        response_model=TranscriptionJobV1,
    )
    def get_transcription_job_route(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> TranscriptionJobV1:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        record = _get_record_or_404(job_store, job_id)
        return record.job

    @app.get(
        "/stage2-api/transcription/jobs/{job_id}/result",
        response_model=TranscriptResultV1,
    )
    def get_transcription_result_route(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> TranscriptResultV1:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        record = _get_record_or_404(job_store, job_id)
        if record.result is None:
            raise HTTPException(
                status_code=409,
                detail={"code": "transcript_result_not_ready", "status": record.job.status},
            )
        return record.result

    @app.get(
        "/stage2-api/transcription/transcripts/{transcript_ref}",
        response_model=TranscriptResultV1,
    )
    def get_transcript_by_ref_route(
        transcript_ref: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
        chat_id: str | None = None,
        message_id: str | None = None,
        openwebui_file_id: str | None = None,
        tenant_id: str | None = None,
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> TranscriptResultV1:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        try:
            store = ArtifactStoreFactory(config).create()
            transcript_store = TranscriptStoreAdapter(store=store, config=config)
            return transcript_store.get_transcript(
                transcript_ref,
                ArtifactAccessContextV1(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    chat_id=chat_id,
                    message_id=message_id,
                    openwebui_file_id=openwebui_file_id,
                    tenant_id=tenant_id,
                ),
            )
        except ArtifactStoreError as exc:
            _raise_artifact_http_error(exc)

    @app.get(
        "/stage2-api/transcription/post-processing/templates",
        response_model=list[PostProcessingTemplateV1],
    )
    def list_post_processing_templates_route(
        user_id: str | None = None,
        user_role: str | None = None,
        user_groups: str | None = None,
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> list[PostProcessingTemplateV1]:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        try:
            return PromptCatalogFactory(config).create().list_templates(
                PromptCatalogUserContextV1(
                    user_id=user_id,
                    user_role=user_role,
                    user_groups=_parse_user_groups(user_groups),
                )
            )
        except PromptCatalogError as exc:
            _raise_prompt_catalog_http_error(exc)

    @app.get(
        "/stage2-api/transcription/post-processing/templates/{template_id}",
        response_model=PostProcessingTemplateV1,
    )
    def get_post_processing_template_route(
        template_id: str,
        user_id: str | None = None,
        user_role: str | None = None,
        user_groups: str | None = None,
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> PostProcessingTemplateV1:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        try:
            return PromptCatalogFactory(config).create().get_template(
                template_id,
                PromptCatalogUserContextV1(
                    user_id=user_id,
                    user_role=user_role,
                    user_groups=_parse_user_groups(user_groups),
                ),
            ).template
        except PromptCatalogError as exc:
            _raise_prompt_catalog_http_error(exc)

    @app.get(
        "/stage2-api/transcription/post-processing/templates/by-command/{command}",
        response_model=PostProcessingTemplateV1,
    )
    def resolve_post_processing_template_command_route(
        command: str,
        user_id: str | None = None,
        user_role: str | None = None,
        user_groups: str | None = None,
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> PostProcessingTemplateV1:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        try:
            return PromptCatalogFactory(config).create().resolve_command(
                command,
                PromptCatalogUserContextV1(
                    user_id=user_id,
                    user_role=user_role,
                    user_groups=_parse_user_groups(user_groups),
                ),
            ).template
        except PromptCatalogError as exc:
            _raise_prompt_catalog_http_error(exc)

    @app.post(
        "/stage2-api/transcription/post-processing/execute",
        response_model=PostProcessingResultV1,
    )
    async def execute_post_processing_route(
        request: PostProcessingRequestV1,
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> PostProcessingResultV1:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        try:
            return await PostProcessingService(config=config).execute(request)
        except ArtifactStoreError as exc:
            _raise_artifact_http_error(exc)
        except PromptCatalogError as exc:
            _raise_prompt_catalog_http_error(exc)
        except PostProcessingError as exc:
            _raise_post_processing_http_error(exc)

    @app.post(
        "/stage2-api/message-docx/exports",
        response_model=MessageDocxExportResultV1,
    )
    def export_message_docx_route(
        request: MessageDocxExportRequestV1,
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> MessageDocxExportResultV1:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        try:
            return MessageDocxExportService(config=config).export(request)
        except MessageDocxExportError as exc:
            _raise_message_docx_http_error(exc)

    @app.post(
        "/stage2-api/transcription/jobs/{job_id}/cancel",
        response_model=TranscriptionJobV1,
    )
    def cancel_transcription_job_route(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_stage2_internal_token: str | None = Header(default=None),
    ) -> TranscriptionJobV1:
        config = _load_config_or_500()
        _require_internal_auth(
            internal_api_key=config.internal_api_key,
            authorization=authorization,
            x_stage2_internal_token=x_stage2_internal_token,
        )
        record = _get_record_or_404(job_store, job_id)
        capability = SttProviderAdapterFactory(config).create().capabilities()
        updated = request_cancel(job=record.job, config=config, capability=capability)
        return job_store.update_job(updated).job

    return app


app = create_app()


def _load_config_or_500():
    try:
        return load_stt_config()
    except (SttConfigError, StorageModeError) as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "stage2_stt_config_invalid", "message": str(exc)},
        ) from exc


def _require_internal_auth(
    *,
    internal_api_key: str | None,
    authorization: str | None,
    x_stage2_internal_token: str | None,
) -> None:
    if not internal_api_key:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "stage2_stt_internal_auth_not_configured",
                "message": "STT job routes require server-side internal auth configuration",
            },
        )
    token = x_stage2_internal_token
    if token is None and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token or not secrets.compare_digest(token, internal_api_key):
        raise HTTPException(
            status_code=401,
            detail={"code": "stage2_stt_internal_auth_failed", "message": "Unauthorized"},
        )


def _parse_envelope(raw: str) -> OpenWebUITranscriptionEnvelopeV1:
    try:
        return OpenWebUITranscriptionEnvelopeV1.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_openwebui_envelope", "message": str(exc)},
        ) from exc


def _resolve_output_profile(
    envelope: OpenWebUITranscriptionEnvelopeV1,
    default_profile: OutputProfile,
) -> OutputProfile:
    raw_profile = envelope.selected_output_profile or default_profile.value
    try:
        return OutputProfile(raw_profile)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_output_profile", "message": raw_profile},
        ) from exc


def _get_record_or_404(
    job_store: InMemoryTranscriptionJobStore,
    job_id: str,
) -> StoredTranscriptionJob:
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "transcription_job_not_found", "job_id": job_id},
        )
    return record


def _access_context_from_envelope(
    envelope: OpenWebUITranscriptionEnvelopeV1,
) -> ArtifactAccessContextV1:
    return ArtifactAccessContextV1(
        workspace_id=envelope.workspace_id,
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        message_id=envelope.message_id,
        openwebui_file_id=envelope.file.file_id if envelope.file is not None else None,
    )


def _raise_artifact_http_error(exc: ArtifactStoreError) -> None:
    status_by_code = {
        "artifact_not_found": 404,
        "artifact_expired": 410,
        "artifact_access_denied": 403,
        "artifact_scope_unverified": 403,
        "artifact_payload_unavailable": 500,
        "artifact_store_unavailable": 503,
    }
    raise HTTPException(
        status_code=status_by_code.get(exc.code, 500),
        detail={"code": exc.code, "message": exc.message},
    )


def _parse_user_groups(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _raise_prompt_catalog_http_error(exc: PromptCatalogError) -> None:
    status_by_code = {
        "prompt_not_found": 404,
        "prompt_access_denied": 403,
        "prompt_catalog_unavailable": 503,
    }
    raise HTTPException(
        status_code=status_by_code.get(exc.code, 500),
        detail={"code": exc.code, "message": exc.message},
    )


def _raise_post_processing_http_error(exc: PostProcessingError) -> None:
    status_by_code = {
        "postprocessing_executor_unavailable": 503,
        "postprocessing_execution_failed": 502,
        "transcript_too_long_single_pass": 413,
        "speakers_required": 422,
        "artifact_scope_unverified": 403,
    }
    raise HTTPException(
        status_code=status_by_code.get(exc.code, 500),
        detail={"code": exc.code, "message": exc.message},
    )


def _raise_message_docx_http_error(exc: MessageDocxExportError) -> None:
    status_by_code = {
        "message_docx_unsupported_role": 422,
        "message_docx_empty_message": 422,
        "message_docx_streaming_message": 409,
        "message_docx_message_too_large": 413,
        "message_docx_generation_failed": 500,
        "message_docx_no_safe_source": 422,
        "message_docx_access_denied": 403,
        "message_docx_no_leak_check_failed": 422,
    }
    raise HTTPException(
        status_code=status_by_code.get(exc.code, 500),
        detail={"code": exc.code, "message": exc.message},
    )
