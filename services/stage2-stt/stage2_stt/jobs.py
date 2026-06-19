from __future__ import annotations

from dataclasses import dataclass

from stage2_stt.config import ProviderCancelSupport, SttConfig
from stage2_stt.contracts import (
    CancelStateV1,
    PreparedAudioMetadataV1,
    SourceMediaMetadataV1,
    SttProviderCapabilityProfileV1,
    TranscriptResultV1,
    TranscriptionJobV1,
)


@dataclass(frozen=True)
class JobContext:
    user_id: str | None = None
    workspace_id: str | None = None


def create_transcription_job(
    *,
    config: SttConfig,
    job_id: str,
    source_media: SourceMediaMetadataV1,
    prepared_audio: PreparedAudioMetadataV1,
    storage_available: bool,
    context: JobContext | None = None,
) -> TranscriptionJobV1:
    context = context or JobContext()
    return TranscriptionJobV1(
        job_id=job_id,
        user_id=context.user_id,
        workspace_id=context.workspace_id,
        status="queued",
        source_media=source_media,
        prepared_audio=prepared_audio,
        selected_output_profile=config.output_profile.value,
        provider_id=config.provider,
        adapter_id=config.provider_adapter,
        storage_mode=config.storage_mode.value,
        storage_available=storage_available,
        cancel_state=CancelStateV1(),
    )


def request_cancel(
    *,
    job: TranscriptionJobV1,
    config: SttConfig,
    capability: SttProviderCapabilityProfileV1,
) -> TranscriptionJobV1:
    if job.status in {"completed", "failed", "cancelled"}:
        return job

    if capability.supports_provider_cancel is True and config.cancel_provider_if_supported:
        return job.model_copy(
            update={
                "status": "cancel_requested",
                "cancel_state": CancelStateV1(
                    requested=True,
                    reason="provider_cancel_supported",
                    provider_cancel_attempted=True,
                    provider_cancel_supported=True,
                ),
            }
        )

    reason = _local_cancel_reason(config.provider_cancel_support)
    return job.model_copy(
        update={
            "status": "cancelled",
            "cancel_state": CancelStateV1(
                requested=True,
                reason=reason,
                provider_cancel_attempted=False,
                provider_cancel_supported=capability.supports_provider_cancel,
                late_provider_result_ignored=True,
            ),
        }
    )


def apply_provider_result(
    *,
    job: TranscriptionJobV1,
    result: TranscriptResultV1,
) -> TranscriptionJobV1:
    if job.status == "cancelled":
        return job.model_copy(
            update={
                "cancel_state": job.cancel_state.model_copy(
                    update={
                        "reason": "late_provider_result_ignored",
                        "late_provider_result_ignored": True,
                    }
                )
            }
        )
    return job.model_copy(update={"status": "completed"})


def _local_cancel_reason(config_value: ProviderCancelSupport) -> str:
    if config_value is ProviderCancelSupport.FALSE:
        return "provider_cancel_unsupported"
    return "provider_cancel_unknown"
