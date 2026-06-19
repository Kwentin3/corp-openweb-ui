from __future__ import annotations

from typing import Protocol

from stage2_stt.config import SttConfig, SttConfigError
from stage2_stt.contracts import SttProviderCapabilityProfileV1, TranscriptResultV1
from stage2_stt.lemonfox import LemonfoxSttAdapter


class SttProviderAdapter(Protocol):
    provider_id: str
    adapter_id: str

    def capabilities(self) -> SttProviderCapabilityProfileV1:
        ...

    async def transcribe_bytes(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
        output_profile: str,
        live: bool = False,
    ) -> TranscriptResultV1:
        ...


class SttProviderAdapterFactory:
    def __init__(self, config: SttConfig) -> None:
        self.config = config

    def create(self) -> SttProviderAdapter:
        if self.config.provider == "lemonfox" and self.config.provider_adapter == "lemonfox":
            return LemonfoxSttAdapter(self.config)
        raise SttConfigError("No STT provider adapter registered for selected config")
