from __future__ import annotations

from stage2_stt.config import SttConfig
from stage2_stt.contracts import TranscriptionRuntimeCapabilitiesV1
from stage2_stt.output_profiles import available_output_profile_ids
from stage2_stt.provider import SttProviderAdapterFactory
from stage2_stt.storage import StorageHealthProbe, resolve_storage_decision


def build_runtime_capabilities(
    config: SttConfig,
    *,
    storage_health_probe: StorageHealthProbe | None = None,
) -> TranscriptionRuntimeCapabilitiesV1:
    adapter = SttProviderAdapterFactory(config).create()
    provider_capability = adapter.capabilities()
    storage = resolve_storage_decision(config, health_probe=storage_health_probe)

    warnings = list(storage.warnings)
    if not config.lemonfox.has_api_key:
        warnings.append("lemonfox_api_key_absent_live_calls_disabled")
    if provider_capability.max_duration_seconds is None:
        warnings.append("provider_max_duration_unknown")
    if provider_capability.supports_provider_cancel is None:
        warnings.append("provider_cancel_unknown_local_cancel_only")

    max_duration_seconds = provider_capability.max_duration_seconds
    if config.internal_max_duration_minutes is not None:
        internal_limit = config.internal_max_duration_minutes * 60
        max_duration_seconds = (
            internal_limit
            if max_duration_seconds is None
            else min(max_duration_seconds, internal_limit)
        )

    return TranscriptionRuntimeCapabilitiesV1(
        selected_output_profile=config.output_profile.value,
        available_output_profiles=available_output_profile_ids(),
        max_browser_input_mb=config.browser_max_input_mb,
        max_prepared_audio_mb=config.max_prepared_audio_mb,
        max_duration_seconds=max_duration_seconds,
        storage_mode=config.storage_mode.value,
        storage_available=storage.available,
        provider_id=provider_capability.provider_id,
        adapter_id=provider_capability.adapter_id,
        supports_provider_cancel=provider_capability.supports_provider_cancel,
        cancel_strategy=provider_capability.cancel_strategy,
        supports_speaker_labels=provider_capability.supports_speaker_labels,
        supports_timestamps=provider_capability.supports_timestamps,
        warnings=warnings,
    )
