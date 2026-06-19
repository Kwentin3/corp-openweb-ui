from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class SttConfigError(ValueError):
    """Raised when Stage 2 STT env config is invalid."""


class OutputProfile(str, Enum):
    OPUS_WEBM_COMPACT = "opus_webm_compact"
    OPUS_OGG_COMPACT = "opus_ogg_compact"
    MP3_HIGH_COMPAT = "mp3_high_compat"
    WAV_PCM_SAFE = "wav_pcm_safe"


class StorageMode(str, Enum):
    AUTO = "auto"
    S3 = "s3"
    NONE = "none"


class PreparedAudioTooLargeBehavior(str, Enum):
    FAIL = "fail"
    USE_URL_UPLOAD_IF_SUPPORTED = "use_url_upload_if_supported"
    USE_OBJECT_STORAGE_PROVIDER_PATH = "use_object_storage_provider_path"


class ProviderCancelSupport(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LemonfoxConfig:
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.lemonfox.ai"
    model: str | None = None
    language: str = "ru"
    enable_speaker_labels: bool = False
    enable_timestamps: bool = True
    max_direct_upload_mb: int = 100
    max_url_upload_mb: int = 1024
    provider_max_duration_minutes: int | None = None

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class SttConfig:
    provider: str
    provider_adapter: str
    lemonfox: LemonfoxConfig
    output_profile: OutputProfile
    fallback_output_profile: OutputProfile
    browser_max_input_mb: int
    browser_max_duration_minutes: int | None
    max_prepared_audio_mb: int
    direct_upload_warning_mb: int
    on_prepared_audio_too_large: PreparedAudioTooLargeBehavior
    internal_max_duration_minutes: int | None
    storage_mode: StorageMode
    require_storage_health: bool
    audio_bucket: str | None
    audio_prefix: str
    store_prepared_audio: bool
    store_source_media: bool
    prepared_audio_retention_days: int | None
    transcript_retention_days: int | None
    cancel_provider_if_supported: bool
    cancel_local_on_provider_no_cancel: bool
    provider_cancel_support: ProviderCancelSupport


def load_stt_config(env: Mapping[str, str | None] | None = None) -> SttConfig:
    source = os.environ if env is None else env
    lemonfox = LemonfoxConfig(
        api_key=_optional_str(source, "STAGE2_LEMONFOX_API_KEY"),
        base_url=_str(source, "STAGE2_LEMONFOX_BASE_URL", "https://api.lemonfox.ai"),
        model=_optional_str(source, "STAGE2_LEMONFOX_MODEL"),
        language=_str(source, "STAGE2_LEMONFOX_LANGUAGE", "ru"),
        enable_speaker_labels=_bool(source, "STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS", False),
        enable_timestamps=_bool(source, "STAGE2_LEMONFOX_ENABLE_TIMESTAMPS", True),
        max_direct_upload_mb=_int(source, "STAGE2_LEMONFOX_MAX_DIRECT_UPLOAD_MB", 100),
        max_url_upload_mb=_int(source, "STAGE2_LEMONFOX_MAX_URL_UPLOAD_MB", 1024),
        provider_max_duration_minutes=_optional_int(
            source, "STAGE2_LEMONFOX_PROVIDER_MAX_DURATION_MINUTES"
        ),
    )

    config = SttConfig(
        provider=_str(source, "STAGE2_STT_PROVIDER", "lemonfox"),
        provider_adapter=_str(source, "STAGE2_STT_PROVIDER_ADAPTER", "lemonfox"),
        lemonfox=lemonfox,
        output_profile=_enum(source, "STAGE2_STT_OUTPUT_PROFILE", OutputProfile, "opus_webm_compact"),
        fallback_output_profile=_enum(
            source, "STAGE2_STT_FALLBACK_OUTPUT_PROFILE", OutputProfile, "mp3_high_compat"
        ),
        browser_max_input_mb=_int(source, "STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB", 1024),
        browser_max_duration_minutes=_optional_int(
            source, "STAGE2_FFMPEG_BROWSER_MAX_DURATION_MINUTES"
        ),
        max_prepared_audio_mb=_int(source, "STAGE2_STT_MAX_PREPARED_AUDIO_MB", 100),
        direct_upload_warning_mb=_int(source, "STAGE2_STT_DIRECT_UPLOAD_WARNING_MB", 100),
        on_prepared_audio_too_large=_enum(
            source,
            "STAGE2_STT_ON_PREPARED_AUDIO_TOO_LARGE",
            PreparedAudioTooLargeBehavior,
            "fail",
        ),
        internal_max_duration_minutes=_optional_int(
            source, "STAGE2_STT_INTERNAL_MAX_DURATION_MINUTES"
        ),
        storage_mode=_enum(source, "STAGE2_STT_STORAGE_MODE", StorageMode, "auto"),
        require_storage_health=_bool(source, "STAGE2_STT_REQUIRE_STORAGE_HEALTH", False),
        audio_bucket=_optional_str(source, "STAGE2_STT_AUDIO_BUCKET"),
        audio_prefix=_str(source, "STAGE2_STT_AUDIO_PREFIX", "stage2/stt/prepared-audio/"),
        store_prepared_audio=_bool(source, "STAGE2_STT_STORE_PREPARED_AUDIO", True),
        store_source_media=_bool(source, "STAGE2_STT_STORE_SOURCE_MEDIA", False),
        prepared_audio_retention_days=_optional_int(
            source, "STAGE2_STT_PREPARED_AUDIO_RETENTION_DAYS"
        ),
        transcript_retention_days=_optional_int(source, "STAGE2_STT_TRANSCRIPT_RETENTION_DAYS"),
        cancel_provider_if_supported=_bool(
            source, "STAGE2_STT_CANCEL_PROVIDER_IF_SUPPORTED", True
        ),
        cancel_local_on_provider_no_cancel=_bool(
            source, "STAGE2_STT_CANCEL_LOCAL_ON_PROVIDER_NO_CANCEL", True
        ),
        provider_cancel_support=_enum(
            source, "STAGE2_STT_PROVIDER_CANCEL_SUPPORT", ProviderCancelSupport, "unknown"
        ),
    )
    _validate_config(config)
    return config


def redact_secret(value: str | None) -> str | None:
    if not value:
        return None
    return "[redacted]"


def _validate_config(config: SttConfig) -> None:
    if config.provider != "lemonfox":
        raise SttConfigError("Unsupported STAGE2_STT_PROVIDER value")
    if config.provider_adapter != "lemonfox":
        raise SttConfigError("Unsupported STAGE2_STT_PROVIDER_ADAPTER value")
    if config.browser_max_input_mb <= 0:
        raise SttConfigError("STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB must be positive")
    if config.max_prepared_audio_mb <= 0:
        raise SttConfigError("STAGE2_STT_MAX_PREPARED_AUDIO_MB must be positive")
    if config.direct_upload_warning_mb <= 0:
        raise SttConfigError("STAGE2_STT_DIRECT_UPLOAD_WARNING_MB must be positive")
    if config.lemonfox.max_direct_upload_mb <= 0:
        raise SttConfigError("STAGE2_LEMONFOX_MAX_DIRECT_UPLOAD_MB must be positive")
    if config.lemonfox.max_url_upload_mb <= 0:
        raise SttConfigError("STAGE2_LEMONFOX_MAX_URL_UPLOAD_MB must be positive")
    if not config.lemonfox.base_url.startswith(("http://", "https://")):
        raise SttConfigError("STAGE2_LEMONFOX_BASE_URL must be an HTTP URL")
    if config.storage_mode is StorageMode.NONE and config.store_source_media:
        raise SttConfigError("STAGE2_STT_STORE_SOURCE_MEDIA cannot be true when storage mode is none")


def _raw(env: Mapping[str, str | None], key: str) -> str | None:
    value = env.get(key)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped if stripped else None


def _str(env: Mapping[str, str | None], key: str, default: str) -> str:
    return _raw(env, key) or default


def _optional_str(env: Mapping[str, str | None], key: str) -> str | None:
    return _raw(env, key)


def _int(env: Mapping[str, str | None], key: str, default: int) -> int:
    raw = _raw(env, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SttConfigError(f"{key} must be an integer") from exc


def _optional_int(env: Mapping[str, str | None], key: str) -> int | None:
    raw = _raw(env, key)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise SttConfigError(f"{key} must be an integer") from exc


def _bool(env: Mapping[str, str | None], key: str, default: bool) -> bool:
    raw = _raw(env, key)
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise SttConfigError(f"{key} must be a boolean")


def _enum(
    env: Mapping[str, str | None],
    key: str,
    enum_type: type[Enum],
    default: str,
):
    raw = _raw(env, key) or default
    try:
        return enum_type(raw)
    except ValueError as exc:
        allowed = ", ".join(str(item.value) for item in enum_type)
        raise SttConfigError(f"{key} must be one of: {allowed}") from exc
