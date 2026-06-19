from __future__ import annotations

from dataclasses import dataclass

from stage2_stt.config import OutputProfile


@dataclass(frozen=True)
class OutputProfileDefinition:
    id: OutputProfile
    mime_type: str
    container: str
    codec: str


OUTPUT_PROFILE_DEFINITIONS: dict[OutputProfile, OutputProfileDefinition] = {
    OutputProfile.OPUS_WEBM_COMPACT: OutputProfileDefinition(
        id=OutputProfile.OPUS_WEBM_COMPACT,
        mime_type="audio/webm;codecs=opus",
        container="webm",
        codec="opus",
    ),
    OutputProfile.OPUS_OGG_COMPACT: OutputProfileDefinition(
        id=OutputProfile.OPUS_OGG_COMPACT,
        mime_type="audio/ogg;codecs=opus",
        container="ogg",
        codec="opus",
    ),
    OutputProfile.MP3_HIGH_COMPAT: OutputProfileDefinition(
        id=OutputProfile.MP3_HIGH_COMPAT,
        mime_type="audio/mpeg",
        container="mp3",
        codec="libmp3lame",
    ),
    OutputProfile.WAV_PCM_SAFE: OutputProfileDefinition(
        id=OutputProfile.WAV_PCM_SAFE,
        mime_type="audio/wav",
        container="wav",
        codec="pcm_s16le",
    ),
}


def available_output_profile_ids() -> list[str]:
    return [profile.value for profile in OutputProfile]


def expected_mime_type(profile: OutputProfile) -> str:
    return OUTPUT_PROFILE_DEFINITIONS[profile].mime_type
