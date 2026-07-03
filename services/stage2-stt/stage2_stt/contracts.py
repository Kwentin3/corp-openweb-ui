from __future__ import annotations

from typing import Any, Literal

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


class OpenWebUIFileReferenceV1(Stage2Model):
    file_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)


class OpenWebUITranscriptionEnvelopeV1(Stage2Model):
    source_context: Literal["openwebui"]
    user_id: str | None = None
    user_email: str | None = None
    user_role: str | None = None
    user_groups: list[str] = Field(default_factory=list)
    chat_id: str | None = None
    message_id: str | None = None
    workspace_id: str | None = None
    file: OpenWebUIFileReferenceV1 | None = None
    selected_output_profile: str | None = None


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


class ArtifactScopeV1(Stage2Model):
    scope_id: str
    workspace_id: str | None = None
    user_id: str | None = None
    chat_id: str | None = None
    message_id: str | None = None
    openwebui_file_id: str | None = None
    stage2_job_id: str | None = None
    client_label: str | None = None
    project_label: str | None = None
    external_context_id: str | None = None
    tenant_id: str | None = None
    access_context_hash: str | None = None


class ArtifactAccessContextV1(Stage2Model):
    workspace_id: str | None = None
    user_id: str | None = None
    chat_id: str | None = None
    message_id: str | None = None
    openwebui_file_id: str | None = None
    tenant_id: str | None = None


class ArtifactRefV1(Stage2Model):
    artifact_ref: str
    artifact_type: Literal[
        "source_file",
        "prepared_audio",
        "stt_job",
        "transcript_result",
        "post_processing_result",
        "projection",
        "diagnostic_provider_payload",
    ]
    version: Literal["v1"] = "v1"
    artifact_scope: ArtifactScopeV1
    created_at: str
    expires_at: str | None = None


class ArtifactRecordV1(Stage2Model):
    artifact_ref: ArtifactRefV1
    parent_refs: list[str] = Field(default_factory=list)
    payload_kind: Literal["inline_json", "file_ref", "object_ref", "redacted", "external_ref"]
    payload_ref: str | None = None
    payload_inline: dict[str, Any] | None = None
    checksum_sha256: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    safe_metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    retention_class: str
    created_by: str | None = None


class ArtifactChainEdgeV1(Stage2Model):
    from_ref: str
    to_ref: str
    transform: Literal["normalize_audio", "transcribe", "project_transcript", "post_process"]
    created_at: str


class ArtifactChainV1(Stage2Model):
    chain_id: str
    root_ref: str
    latest_refs: list[str] | None = None
    edges: list[ArtifactChainEdgeV1] = Field(default_factory=list)


class TranscriptResultV1(Stage2Model):
    job_id: str | None = None
    transcript_ref: str | None = None
    text: str
    language: str | None = None
    duration_seconds: float | None = None
    segments: list[TranscriptSegmentV1] = Field(default_factory=list)
    output_profile: str
    provider_id: str
    adapter_id: str
    warnings: list[str] = Field(default_factory=list)
    safe_provider_metadata: dict[str, Any] = Field(default_factory=dict)
    transcript_hash: str | None = None
    artifact_scope: ArtifactScopeV1 | None = None
    source_links: dict[str, Any] = Field(default_factory=dict)
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
    input_accept_mode: Literal["declared", "broad_ffmpeg_probe"]
    declared_input_mime_prefixes: list[str]
    declared_input_extensions: list[str]
    ffmpeg_probe_required: bool
    require_audio_stream: bool
    selected_output_profile: str
    fallback_output_profile: str
    available_output_profiles: list[str]
    max_browser_input_mb: int
    max_browser_duration_minutes: int | None = None
    max_prepared_audio_mb: int
    max_duration_seconds: int | None = None
    storage_mode: Literal["auto", "s3", "none"]
    storage_available: bool
    artifact_store_mode: Literal["sqlite", "memory_test", "disabled"]
    artifact_store_available: bool
    provider_id: str
    adapter_id: str
    supports_provider_cancel: bool | None
    cancel_strategy: str
    supports_speaker_labels: bool
    supports_timestamps: bool
    warnings: list[str] = Field(default_factory=list)


class TranscriptionJobCreateResponseV1(Stage2Model):
    job: TranscriptionJobV1
    result: TranscriptResultV1 | None = None
    transcript_ref: str | None = None
    warnings: list[str] = Field(default_factory=list)


class PromptCatalogUserContextV1(Stage2Model):
    user_id: str | None = None
    user_role: str | None = None
    user_groups: list[str] = Field(default_factory=list)


class PostProcessingTemplateV1(Stage2Model):
    template_id: str
    command: str
    label: str
    openwebui_prompt_id: str
    prompt_version: str | None = None
    prompt_body_hash: str
    tags: list[str] = Field(default_factory=list)
    requires_speakers: bool = False
    chunkable: bool = False
    access_grants: list[str] = Field(default_factory=list)


class PostProcessingRequestV1(Stage2Model):
    transcript_ref: str
    template_id: str
    user_context: PromptCatalogUserContextV1
    artifact_context: ArtifactAccessContextV1


class PostProcessingPromptDraftRequestV1(Stage2Model):
    transcript_ref: str
    template_id: str
    user_context: PromptCatalogUserContextV1
    artifact_context: ArtifactAccessContextV1


class PostProcessingPromptDraftV1(Stage2Model):
    transcript_ref: str
    template_id: str
    command: str
    label: str
    openwebui_prompt_id: str
    prompt_version: str | None = None
    prompt_body_hash: str
    transcript_hash: str | None = None
    prompt_text: str
    warnings: list[str] = Field(default_factory=list)
    artifact_scope: ArtifactScopeV1 | None = None


class PostProcessingResultV1(Stage2Model):
    result_ref: str | None = None
    transcript_ref: str
    template_id: str
    command: str
    label: str
    openwebui_prompt_id: str
    prompt_version: str | None = None
    prompt_body_hash: str
    transcript_hash: str | None = None
    text: str
    warnings: list[str] = Field(default_factory=list)
    artifact_scope: ArtifactScopeV1 | None = None


MessageDocxSourceV1 = Literal["openwebui_chat_api", "dom", "action_body", "artifact"]
MessageDocxDeliveryV1 = Literal["base64", "download_url", "openwebui_file_id"]
MessageDocxFormattingProfileV1 = Literal["simple_mvp"]


class MessageDocxSafeMetadataV1(Stage2Model):
    chat_title: str | None = None
    model_name: str | None = None
    message_timestamp: str | None = None
    source_url_path: str | None = None
    result_ref: str | None = None


class MessageDocxExportOptionsV1(Stage2Model):
    include_chat_title: bool = True
    include_model_name: bool = True
    include_timestamp: bool = True
    formatting_profile: MessageDocxFormattingProfileV1 = "simple_mvp"


class MessageDocxExportRequestV1(Stage2Model):
    schema_version: Literal["MessageDocxExportRequestV1"] = "MessageDocxExportRequestV1"
    request_id: str
    chat_id: str | None = None
    message_id: str | None = None
    message_role: Literal["assistant", "user", "system", "unknown"]
    message_text: str
    message_markdown: str | None = None
    message_html: str | None = None
    source: MessageDocxSourceV1
    safe_metadata: MessageDocxSafeMetadataV1 = Field(default_factory=MessageDocxSafeMetadataV1)
    options: MessageDocxExportOptionsV1 = Field(default_factory=MessageDocxExportOptionsV1)


class MessageDocxExportResultV1(Stage2Model):
    schema_version: Literal["MessageDocxExportResultV1"] = "MessageDocxExportResultV1"
    export_id: str
    filename: str
    content_type: Literal[
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    size_bytes: int = Field(ge=0)
    checksum_sha256: str
    delivery: MessageDocxDeliveryV1
    download_payload_base64: str | None = None
    download_url: str | None = None
    file_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
