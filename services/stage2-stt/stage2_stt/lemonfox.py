from __future__ import annotations

from typing import Any

import httpx

from stage2_stt.config import ProviderCancelSupport, SttConfig
from stage2_stt.contracts import (
    ProviderErrorV1,
    SttProviderCapabilityProfileV1,
    TranscriptResultV1,
    TranscriptSegmentV1,
    TranscriptWordV1,
)


class LemonfoxProviderError(RuntimeError):
    def __init__(self, error: ProviderErrorV1) -> None:
        super().__init__(error.message)
        self.error = error


class LemonfoxSttAdapter:
    provider_id = "lemonfox"
    adapter_id = "lemonfox"

    def __init__(self, config: SttConfig) -> None:
        self.config = config

    def capabilities(self) -> SttProviderCapabilityProfileV1:
        supports_provider_cancel = _cancel_support_to_bool(self.config.provider_cancel_support)
        max_duration_seconds = None
        if self.config.lemonfox.provider_max_duration_minutes is not None:
            max_duration_seconds = self.config.lemonfox.provider_max_duration_minutes * 60

        return SttProviderCapabilityProfileV1(
            provider_id=self.provider_id,
            adapter_id=self.adapter_id,
            supported_input_profiles=[
                "mp3_high_compat",
                "opus_webm_compact",
                "opus_ogg_compact",
                "wav_pcm_safe",
            ],
            max_direct_upload_mb=self.config.lemonfox.max_direct_upload_mb,
            max_url_upload_mb=self.config.lemonfox.max_url_upload_mb,
            max_duration_seconds=max_duration_seconds,
            supports_url_upload=True,
            supports_provider_cancel=supports_provider_cancel,
            supports_callbacks=True,
            supports_timestamps=self.config.lemonfox.enable_timestamps,
            supports_word_timestamps=self.config.lemonfox.enable_timestamps,
            supports_speaker_labels=self.config.lemonfox.enable_speaker_labels,
            max_speakers=4,
            supported_languages=["russian", "ru"],
            response_formats=["json", "text", "srt", "verbose_json", "vtt"],
            retention_policy_notes=(
                "homepage_says_deleted_immediately_after_processing_needs_policy_review"
            ),
            cancel_strategy=_cancel_strategy(supports_provider_cancel),
            unknowns=[
                "exact_webm_opus_stage2_profile",
                "exact_ogg_opus_stage2_profile",
                "provider_max_duration",
                "provider_cancel_endpoint_or_job_id",
                "provider_error_taxonomy",
            ],
        )

    async def transcribe_bytes(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
        output_profile: str,
        live: bool = False,
    ) -> TranscriptResultV1:
        if not self.config.lemonfox.has_api_key:
            if live:
                raise LemonfoxProviderError(
                    ProviderErrorV1(
                        code="provider_auth_missing",
                        message="Lemonfox API key is required for live provider calls",
                        retryable=False,
                    )
                )
            return self._stub_result(output_profile)

        form = self._request_form()
        files = {"file": (filename, audio_bytes, mime_type)}
        headers = {"Authorization": f"Bearer {self.config.lemonfox.api_key}"}

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.config.lemonfox.base_url.rstrip('/')}/v1/audio/transcriptions",
                    data=form,
                    files=files,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise LemonfoxProviderError(
                ProviderErrorV1(
                    code="provider_network_error",
                    message="Lemonfox request failed before response",
                    retryable=True,
                )
            ) from exc

        if response.status_code >= 400:
            raise LemonfoxProviderError(self.normalize_error(response))

        payload = response.json()
        return self.normalize_transcript(payload, output_profile=output_profile)

    def _request_form(self) -> dict[str, Any]:
        form: dict[str, Any] = {"response_format": "verbose_json"}
        if self.config.lemonfox.model:
            form["model"] = self.config.lemonfox.model
        if self.config.lemonfox.language:
            form["language"] = self.config.lemonfox.language
        if self.config.lemonfox.enable_speaker_labels:
            form["speaker_labels"] = "true"
        if self.config.lemonfox.enable_timestamps:
            form["timestamp_granularities[]"] = "word"
        return form

    def normalize_transcript(self, payload: dict[str, Any], *, output_profile: str) -> TranscriptResultV1:
        segments = []
        for segment in payload.get("segments") or []:
            words = [
                TranscriptWordV1(
                    text=str(word.get("word") or word.get("text") or ""),
                    start_seconds=_optional_float(word.get("start")),
                    end_seconds=_optional_float(word.get("end")),
                    speaker=_optional_str(word.get("speaker")),
                )
                for word in segment.get("words") or []
            ]
            segments.append(
                TranscriptSegmentV1(
                    text=str(segment.get("text") or ""),
                    start_seconds=_optional_float(segment.get("start")),
                    end_seconds=_optional_float(segment.get("end")),
                    speaker=_optional_str(segment.get("speaker")),
                    words=words,
                )
            )

        return TranscriptResultV1(
            text=str(payload.get("text") or ""),
            language=_optional_str(payload.get("language")) or self.config.lemonfox.language,
            duration_seconds=_optional_float(payload.get("duration")),
            segments=segments,
            output_profile=output_profile,
            provider_id=self.provider_id,
            adapter_id=self.adapter_id,
        )

    def normalize_error(self, response: httpx.Response) -> ProviderErrorV1:
        provider_code = None
        message = "Lemonfox returned an error"
        try:
            payload = response.json()
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                provider_code = _optional_str(error.get("code") or error.get("type"))
                message = _optional_str(error.get("message")) or message
        except ValueError:
            pass

        return ProviderErrorV1(
            code="provider_error",
            message=message,
            retryable=response.status_code in {408, 409, 429, 500, 502, 503, 504},
            provider_status_code=response.status_code,
            provider_error_code=provider_code,
        )

    def _stub_result(self, output_profile: str) -> TranscriptResultV1:
        return TranscriptResultV1(
            text="",
            language=self.config.lemonfox.language,
            output_profile=output_profile,
            provider_id=self.provider_id,
            adapter_id=self.adapter_id,
            warnings=["lemonfox_api_key_absent_stub_result"],
        )


def _cancel_support_to_bool(value: ProviderCancelSupport) -> bool | None:
    if value is ProviderCancelSupport.TRUE:
        return True
    if value is ProviderCancelSupport.FALSE:
        return False
    return None


def _cancel_strategy(supports_provider_cancel: bool | None) -> str:
    if supports_provider_cancel is True:
        return "provider_cancel_if_supported"
    if supports_provider_cancel is False:
        return "local_cancel_ignore_late_result"
    return "local_cancel_until_provider_proof"


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
