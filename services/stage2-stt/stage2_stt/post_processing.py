from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx

from stage2_stt.artifact_store import (
    ArtifactStoreAdapter,
    ArtifactStoreError,
    ArtifactStoreFactory,
    new_artifact_ref,
)
from stage2_stt.config import PostProcessingExecutorMode, SttConfig
from stage2_stt.contracts import (
    ArtifactRecordV1,
    PostProcessingRequestV1,
    PostProcessingResultV1,
    PromptCatalogUserContextV1,
    TranscriptResultV1,
)
from stage2_stt.prompt_catalog import PromptCatalogError, PromptCatalogFactory
from stage2_stt.transcript_store import TranscriptStoreAdapter


FACTORY_REQUIRED = "PostProcessingExecutorFactory.create is the only production executor entrypoint"
FORBIDDEN = "Route handlers must not call OpenAI-compatible post-processing directly"


class PostProcessingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class PostProcessingExecutorAdapter(Protocol):
    async def execute(self, rendered_prompt: str) -> str:
        ...


class PostProcessingExecutorFactory:
    def __init__(self, config: SttConfig) -> None:
        self.config = config

    def create(self) -> PostProcessingExecutorAdapter:
        if self.config.postprocessing_executor_mode is PostProcessingExecutorMode.OPENAI_COMPATIBLE:
            return OpenAICompatiblePostProcessingExecutorAdapter(self.config)
        return DisabledPostProcessingExecutorAdapter()


class DisabledPostProcessingExecutorAdapter:
    async def execute(self, rendered_prompt: str) -> str:
        raise PostProcessingError(
            "postprocessing_executor_unavailable",
            "Post-processing executor is disabled",
        )


class OpenAICompatiblePostProcessingExecutorAdapter:
    def __init__(self, config: SttConfig) -> None:
        self.config = config

    async def execute(self, rendered_prompt: str) -> str:
        base_url = (self.config.postprocessing_openai_base_url or "").rstrip("/")
        api_key = self.config.postprocessing_openai_api_key or ""
        model = self.config.postprocessing_openai_model or ""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": rendered_prompt}],
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise PostProcessingError(
                "postprocessing_execution_failed",
                "OpenAI-compatible post-processing request failed",
            ) from exc
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PostProcessingError(
                "postprocessing_execution_failed",
                "OpenAI-compatible post-processing response was invalid",
            ) from exc
        normalized = str(text or "").strip()
        if not normalized:
            raise PostProcessingError(
                "postprocessing_execution_failed",
                "OpenAI-compatible post-processing response was empty",
            )
        return normalized


class PostProcessingService:
    def __init__(
        self,
        *,
        config: SttConfig,
        artifact_store: ArtifactStoreAdapter | None = None,
        executor: PostProcessingExecutorAdapter | None = None,
    ) -> None:
        self.config = config
        self.artifact_store = artifact_store or ArtifactStoreFactory(config).create()
        self.executor = executor or PostProcessingExecutorFactory(config).create()

    async def execute(self, request: PostProcessingRequestV1) -> PostProcessingResultV1:
        transcript_store = TranscriptStoreAdapter(store=self.artifact_store, config=self.config)
        try:
            transcript = transcript_store.get_transcript(
                request.transcript_ref,
                request.artifact_context,
            )
        except ArtifactStoreError:
            raise

        try:
            resolved_template = PromptCatalogFactory(self.config).create().get_template(
                request.template_id,
                request.user_context,
            )
        except PromptCatalogError:
            raise

        projection = build_transcript_projection(transcript)
        if len(projection.prompt_input) > self.config.postprocessing_max_transcript_chars:
            raise PostProcessingError(
                "transcript_too_long_single_pass",
                "Transcript is too long for Gate 4 single-pass post-processing",
            )
        if resolved_template.template.requires_speakers and not projection.has_speakers:
            raise PostProcessingError(
                "speakers_required",
                "Selected post-processing template requires speaker labels",
            )

        rendered_prompt = render_prompt_body(
            resolved_template.prompt_body,
            projection,
        )
        processed_text = await self.executor.execute(rendered_prompt)
        result = PostProcessingResultV1(
            transcript_ref=request.transcript_ref,
            template_id=resolved_template.template.template_id,
            command=resolved_template.template.command,
            label=resolved_template.template.label,
            openwebui_prompt_id=resolved_template.template.openwebui_prompt_id,
            prompt_version=resolved_template.template.prompt_version,
            prompt_body_hash=resolved_template.template.prompt_body_hash,
            transcript_hash=transcript.transcript_hash,
            text=processed_text,
            warnings=[],
            artifact_scope=transcript.artifact_scope,
        )
        return self._store_result(result)

    def _store_result(self, result: PostProcessingResultV1) -> PostProcessingResultV1:
        if result.artifact_scope is None:
            raise PostProcessingError(
                "artifact_scope_unverified",
                "Post-processing result cannot be stored without artifact scope",
            )
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=self.config.artifact_transformation_ttl_days)
        ).isoformat()
        ref = new_artifact_ref(
            artifact_type="post_processing_result",
            artifact_scope=result.artifact_scope,
            expires_at=expires_at,
        )
        stored = result.model_copy(update={"result_ref": ref.artifact_ref})
        self.artifact_store.put_artifact(
            ArtifactRecordV1(
                artifact_ref=ref,
                parent_refs=[result.transcript_ref],
                payload_kind="inline_json",
                payload_inline=stored.model_dump(mode="json"),
                checksum_sha256=hashlib.sha256(stored.text.encode("utf-8")).hexdigest(),
                size_bytes=len(stored.text.encode("utf-8")),
                safe_metadata={
                    "template_id": stored.template_id,
                    "command": stored.command,
                    "openwebui_prompt_id": stored.openwebui_prompt_id,
                    "prompt_version": stored.prompt_version,
                    "prompt_body_hash": stored.prompt_body_hash,
                    "transcript_hash": stored.transcript_hash,
                },
                retention_class="post_processing_result",
                created_by="stage2-stt",
            )
        )
        self.artifact_store.link_artifacts(result.transcript_ref, ref.artifact_ref, "post_process")
        return stored


class TranscriptProjection:
    def __init__(self, *, prompt_input: str, plain_text: str, speaker_text: str, has_speakers: bool) -> None:
        self.prompt_input = prompt_input
        self.plain_text = plain_text
        self.speaker_text = speaker_text
        self.has_speakers = has_speakers


def build_transcript_projection(transcript: TranscriptResultV1) -> TranscriptProjection:
    plain_text = transcript.text.strip()
    speaker_lines: list[str] = []
    has_speakers = False
    for segment in transcript.segments:
        speaker = segment.speaker or "speaker_unknown"
        if segment.speaker:
            has_speakers = True
        prefix_parts = []
        if segment.start_seconds is not None:
            prefix_parts.append(_format_seconds(segment.start_seconds))
        if segment.end_seconds is not None:
            prefix_parts.append(_format_seconds(segment.end_seconds))
        timing = f"[{'-'.join(prefix_parts)}] " if prefix_parts else ""
        speaker_lines.append(f"{timing}{speaker}: {segment.text}".strip())
    speaker_text = "\n".join(speaker_lines).strip()
    prompt_input = speaker_text or plain_text
    return TranscriptProjection(
        prompt_input=prompt_input,
        plain_text=plain_text,
        speaker_text=speaker_text,
        has_speakers=has_speakers,
    )


def render_prompt_body(prompt_body: str, projection: TranscriptProjection) -> str:
    body = str(prompt_body or "").strip()
    replacements = {
        "{{TRANSCRIPT_TEXT}}": projection.plain_text,
        "{{TRANSCRIPT_WITH_SPEAKERS}}": projection.speaker_text or projection.plain_text,
    }
    rendered = body
    replaced = False
    for marker, value in replacements.items():
        if marker in rendered:
            rendered = rendered.replace(marker, value)
            replaced = True
    if replaced:
        return rendered
    return f"{rendered}\n\nTranscript:\n{projection.prompt_input}".strip()


def _format_seconds(value: float) -> str:
    total = max(0, int(value))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
