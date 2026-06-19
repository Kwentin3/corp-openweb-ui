from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal[
    "queued",
    "preprocessing",
    "uploading",
    "processing",
    "completed",
    "failed",
    "cancel_requested",
    "cancelled",
]

CancelReason = Literal[
    "cancelled_by_user",
    "provider_cancel_supported",
    "provider_cancel_unsupported",
    "provider_cancel_unknown",
    "cancelled_locally_provider_continues",
    "late_provider_result_ignored",
]


class Stage2Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ProviderErrorV1(Stage2Model):
    code: str
    message: str
    retryable: bool = False
    provider_status_code: int | None = None
    provider_error_code: str | None = None


class SourceMediaMetadataV1(Stage2Model):
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    stored: bool = False
    object_key: str | None = None


class PreparedAudioMetadataV1(Stage2Model):
    output_profile: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    object_key: str | None = None
    retention_days: int | None = Field(default=None, ge=0)


class CancelStateV1(Stage2Model):
    requested: bool = False
    reason: CancelReason | None = None
    provider_cancel_attempted: bool = False
    provider_cancel_supported: bool | None = None
    late_provider_result_ignored: bool = False


class TranscriptionJobV1(Stage2Model):
    job_id: str
    user_id: str | None = None
    workspace_id: str | None = None
    status: JobStatus
    source_media: SourceMediaMetadataV1
    prepared_audio: PreparedAudioMetadataV1
    selected_output_profile: str
    provider_id: str
    adapter_id: str
    storage_mode: Literal["auto", "s3", "none"]
    storage_available: bool
    cancel_state: CancelStateV1
    error: ProviderErrorV1 | None = None


class TranscriptWordV1(Stage2Model):
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    speaker: str | None = None


class TranscriptSegmentV1(Stage2Model):
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    speaker: str | None = None
    words: list[TranscriptWordV1] = Field(default_factory=list)


class TranscriptResultV1(Stage2Model):
    job_id: str | None = None
    text: str
    language: str | None = None
    duration_seconds: float | None = None
    segments: list[TranscriptSegmentV1] = Field(default_factory=list)
    output_profile: str
    provider_id: str
    adapter_id: str
    warnings: list[str] = Field(default_factory=list)
    internal_provider_response_ref: str | None = None


class UsageEventV1(Stage2Model):
    event_id: str | None = None
    user_id: str | None = None
    workspace_id: str | None = None
    provider_id: str
    adapter_id: str
    model: str | None = None
    upload_bytes: int = Field(default=0, ge=0)
    preprocessing_units: float | None = None
    stt_billable_units: float | None = None
    estimated_cost: float | None = None
    correlation_id: str | None = None


class PolicyDecisionV1(Stage2Model):
    allowed: bool
    action: str
    user_id: str | None = None
    workspace_id: str | None = None
    data_class: str | None = None
    provider_class: str | None = None
    output_profile: str | None = None
    adapter_id: str | None = None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SttProviderCapabilityProfileV1(Stage2Model):
    provider_id: str
    adapter_id: str
    supported_input_profiles: list[str]
    max_direct_upload_mb: int
    max_url_upload_mb: int | None = None
    max_duration_seconds: int | None = None
    supports_url_upload: bool
    supports_provider_cancel: bool | None
    supports_callbacks: bool
    supports_timestamps: bool
    supports_word_timestamps: bool
    supports_speaker_labels: bool
    max_speakers: int | None = None
    supported_languages: list[str] = Field(default_factory=list)
    response_formats: list[str] = Field(default_factory=list)
    retention_policy_notes: str | None = None
    cancel_strategy: str
    unknowns: list[str] = Field(default_factory=list)


class TranscriptionRuntimeCapabilitiesV1(Stage2Model):
    selected_output_profile: str
    available_output_profiles: list[str]
    max_browser_input_mb: int
    max_prepared_audio_mb: int
    max_duration_seconds: int | None = None
    storage_mode: Literal["auto", "s3", "none"]
    storage_available: bool
    provider_id: str
    adapter_id: str
    supports_provider_cancel: bool | None
    cancel_strategy: str
    supports_speaker_labels: bool
    supports_timestamps: bool
    warnings: list[str] = Field(default_factory=list)
