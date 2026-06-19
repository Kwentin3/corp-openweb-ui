from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from stage2_stt.config import StorageMode, SttConfig


class StorageModeError(RuntimeError):
    """Raised when selected storage mode cannot be satisfied."""


class StorageHealthProbe(Protocol):
    def is_available(self, config: SttConfig) -> bool:
        ...


@dataclass(frozen=True)
class StaticStorageHealthProbe:
    available: bool

    def is_available(self, config: SttConfig) -> bool:
        return self.available


@dataclass(frozen=True)
class StorageDecision:
    mode: str
    configured: bool
    available: bool
    persistent_prepared_audio: bool
    store_source_media: bool
    warnings: list[str]


def resolve_storage_decision(
    config: SttConfig,
    health_probe: StorageHealthProbe | None = None,
) -> StorageDecision:
    configured = bool(config.audio_bucket)
    warnings: list[str] = []

    if config.storage_mode is StorageMode.NONE:
        return StorageDecision(
            mode="none",
            configured=configured,
            available=False,
            persistent_prepared_audio=False,
            store_source_media=False,
            warnings=["prepared_audio_storage_disabled"],
        )

    available = False
    if configured:
        if health_probe is not None:
            available = health_probe.is_available(config)
        elif config.require_storage_health:
            available = False
            warnings.append("storage_health_probe_missing")
        else:
            available = True
            warnings.append("storage_health_not_verified")

    if config.storage_mode is StorageMode.S3 and not available:
        raise StorageModeError("STAGE2_STT_STORAGE_MODE=s3 requires configured healthy storage")

    if config.storage_mode is StorageMode.AUTO and not available:
        warnings.append("prepared_audio_storage_transient")

    return StorageDecision(
        mode=config.storage_mode.value,
        configured=configured,
        available=available,
        persistent_prepared_audio=available and config.store_prepared_audio,
        store_source_media=available and config.store_source_media,
        warnings=warnings,
    )


def generate_prepared_audio_object_key(prefix: str, job_id: str) -> str:
    normalized_prefix = prefix.strip("/")
    safe_job_id = re.sub(r"[^A-Za-z0-9_.-]", "-", job_id).strip(".-")
    if not safe_job_id:
        raise ValueError("job_id must contain at least one safe character")
    return f"{normalized_prefix}/{safe_job_id}/prepared-audio"
