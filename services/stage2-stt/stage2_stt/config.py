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


class InputAcceptMode(str, Enum):
    DECLARED = "declared"
    BROAD_FFMPEG_PROBE = "broad_ffmpeg_probe"


@dataclass(frozen=True)
class LemonfoxConfig:
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.lemonfox.ai"
    model: str | None = None
    language: str = "ru"
    enable_speaker_labels: bool = False
    enable_timestamps: bool = True
    max_direct_upload_mb: int = 400
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
    input_accept_mode: InputAcceptMode
    declared_input_extensions: tuple[str, ...]
    declared_input_mime_prefixes: tuple[str, ...]
    require_audio_stream: bool
    ffmpeg_probe_before_action: bool
    output_profile: OutputProfile
    fallback_output_profile: OutputProfile
    browser_max_input_mb: int
    browser_max_duration_minutes: int | None
    ffmpeg_asset_mode: str
    ffmpeg_core_base_url: str
    ffmpeg_package_version: str
    ffmpeg_core_version: str
    ffmpeg_util_version: str
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
    allow_stub_transcript: bool
    cancel_provider_if_supported: bool
    cancel_local_on_provider_no_cancel: bool
    provider_cancel_support: ProviderCancelSupport
    internal_api_key: str | None = field(default=None, repr=False)


def load_stt_config(env: Mapping[str, str | None] | None = None) -> SttConfig:
    source = os.environ if env is None else env
    lemonfox = LemonfoxConfig(
        api_key=_optional_str(source, "STAGE2_LEMONFOX_API_KEY"),
        base_url=_str(source, "STAGE2_LEMONFOX_BASE_URL", "https://api.lemonfox.ai"),
        model=_optional_str(source, "STAGE2_LEMONFOX_MODEL"),
        language=_str(source, "STAGE2_LEMONFOX_LANGUAGE", "ru"),
        enable_speaker_labels=_bool(source, "STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS", False),
        enable_timestamps=_bool(source, "STAGE2_LEMONFOX_ENABLE_TIMESTAMPS", True),
        max_direct_upload_mb=_int(source, "STAGE2_LEMONFOX_MAX_DIRECT_UPLOAD_MB", 400),
        max_url_upload_mb=_int(source, "STAGE2_LEMONFOX_MAX_URL_UPLOAD_MB", 1024),
        provider_max_duration_minutes=_optional_int(
            source, "STAGE2_LEMONFOX_PROVIDER_MAX_DURATION_MINUTES"
        ),
    )

    config = SttConfig(
        provider=_str(source, "STAGE2_STT_PROVIDER", "lemonfox"),
        provider_adapter=_str(source, "STAGE2_STT_PROVIDER_ADAPTER", "lemonfox"),
        lemonfox=lemonfox,
        input_accept_mode=_enum(
            source, "STAGE2_STT_INPUT_ACCEPT_MODE", InputAcceptMode, "broad_ffmpeg_probe"
        ),
        declared_input_extensions=_csv(
            source,
            "STAGE2_STT_DECLARED_INPUT_EXTENSIONS",
            "mp3,wav,m4a,webm,ogg,mp4,mov,mkv,avi,flac,aac",
        ),
        declared_input_mime_prefixes=_csv(
            source, "STAGE2_STT_DECLARED_INPUT_MIME_PREFIXES", "audio/,video/"
        ),
        require_audio_stream=_bool(source, "STAGE2_STT_REQUIRE_AUDIO_STREAM", True),
        ffmpeg_probe_before_action=_bool(
            source, "STAGE2_STT_FFMPEG_PROBE_BEFORE_ACTION", True
        ),
        output_profile=_enum(source, "STAGE2_STT_OUTPUT_PROFILE", OutputProfile, "mp3_high_compat"),
        fallback_output_profile=_enum(
            source, "STAGE2_STT_FALLBACK_OUTPUT_PROFILE", OutputProfile, "mp3_high_compat"
        ),
        browser_max_input_mb=_int(source, "STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB", 1024),
        browser_max_duration_minutes=_optional_int(
            source, "STAGE2_FFMPEG_BROWSER_MAX_DURATION_MINUTES"
        ),
        ffmpeg_asset_mode=_str(source, "STAGE2_FFMPEG_ASSET_MODE", "self_hosted"),
        ffmpeg_core_base_url=_str(
            source, "STAGE2_FFMPEG_CORE_BASE_URL", "/static/stage2-assets/ffmpeg/0.12.6/"
        ),
        ffmpeg_package_version=_str(source, "STAGE2_FFMPEG_PACKAGE_VERSION", "0.12.6"),
        ffmpeg_core_version=_str(source, "STAGE2_FFMPEG_CORE_VERSION", "0.12.6"),
        ffmpeg_util_version=_str(source, "STAGE2_FFMPEG_UTIL_VERSION", "0.12.1"),
        max_prepared_audio_mb=_int(source, "STAGE2_STT_MAX_PREPARED_AUDIO_MB", 400),
        direct_upload_warning_mb=_int(source, "STAGE2_STT_DIRECT_UPLOAD_WARNING_MB", 400),
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
        internal_api_key=_optional_str(source, "STAGE2_STT_INTERNAL_API_KEY"),
        allow_stub_transcript=_bool(source, "STAGE2_STT_ALLOW_STUB_TRANSCRIPT", False),
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
    if not config.declared_input_extensions:
        raise SttConfigError("STAGE2_STT_DECLARED_INPUT_EXTENSIONS must not be empty")
    if not config.declared_input_mime_prefixes:
        raise SttConfigError("STAGE2_STT_DECLARED_INPUT_MIME_PREFIXES must not be empty")
    if config.browser_max_input_mb <= 0:
        raise SttConfigError("STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB must be positive")
    if config.ffmpeg_asset_mode not in {"self_hosted", "cdn"}:
        raise SttConfigError("STAGE2_FFMPEG_ASSET_MODE must be one of: self_hosted, cdn")
    if not config.ffmpeg_core_base_url.startswith(("/", "http://", "https://")):
        raise SttConfigError("STAGE2_FFMPEG_CORE_BASE_URL must be an absolute path or HTTP URL")
    if not config.ffmpeg_package_version:
        raise SttConfigError("STAGE2_FFMPEG_PACKAGE_VERSION must not be empty")
    if not config.ffmpeg_core_version:
        raise SttConfigError("STAGE2_FFMPEG_CORE_VERSION must not be empty")
    if not config.ffmpeg_util_version:
        raise SttConfigError("STAGE2_FFMPEG_UTIL_VERSION must not be empty")
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


def _csv(env: Mapping[str, str | None], key: str, default: str) -> tuple[str, ...]:
    raw = _raw(env, key) or default
    return tuple(item.strip().lstrip(".").lower() for item in raw.split(",") if item.strip())


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
