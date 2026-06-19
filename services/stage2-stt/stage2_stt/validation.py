from __future__ import annotations

from dataclasses import dataclass, field

from stage2_stt.config import OutputProfile, PreparedAudioTooLargeBehavior, SttConfig
from stage2_stt.contracts import ProviderErrorV1, SttProviderCapabilityProfileV1
from stage2_stt.output_profiles import expected_mime_type

BYTES_PER_MB = 1024 * 1024


@dataclass(frozen=True)
class PreparedAudioValidationResult:
    accepted: bool
    warnings: list[str] = field(default_factory=list)
    error: ProviderErrorV1 | None = None


def validate_prepared_audio(
    *,
    config: SttConfig,
    capability: SttProviderCapabilityProfileV1,
    output_profile: OutputProfile,
    mime_type: str,
    size_bytes: int,
) -> PreparedAudioValidationResult:
    warnings: list[str] = []
    expected_mime = expected_mime_type(output_profile)
    if mime_type != expected_mime:
        return _reject("unsupported_input_format", "Prepared audio MIME does not match output profile")

    if output_profile.value not in capability.supported_input_profiles:
        return _reject("unsupported_input_format", "Selected output profile is not supported by provider")

    direct_limit_bytes = config.lemonfox.max_direct_upload_mb * BYTES_PER_MB
    max_prepared_audio_bytes = config.max_prepared_audio_mb * BYTES_PER_MB
    warning_bytes = config.direct_upload_warning_mb * BYTES_PER_MB

    if size_bytes >= warning_bytes:
        warnings.append("provider_direct_upload_limit_warning")

    if size_bytes > max_prepared_audio_bytes:
        if config.on_prepared_audio_too_large is PreparedAudioTooLargeBehavior.FAIL:
            return _reject("prepared_audio_too_large", "Prepared audio exceeds configured size limit")
        if not capability.supports_url_upload:
            return _reject("storage_required_for_large_audio", "Large audio fallback requires storage URL support")

    if size_bytes > direct_limit_bytes:
        return _reject(
            "provider_direct_upload_limit_exceeded",
            "Prepared audio exceeds provider direct upload limit",
        )

    return PreparedAudioValidationResult(accepted=True, warnings=warnings)


def _reject(code: str, message: str) -> PreparedAudioValidationResult:
    return PreparedAudioValidationResult(
        accepted=False,
        error=ProviderErrorV1(code=code, message=message, retryable=False),
    )
