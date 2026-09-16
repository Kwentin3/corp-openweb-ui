"""Server-side, temporary extraction of an audio stream from uploaded video.

This module deliberately owns no durable user file.  The OpenWebUI lifecycle
overlay imports the returned bytes into the native File store; temporary files
are removed before this function returns or raises.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from stage2_stt.config import OutputProfile
from stage2_stt.output_profiles import OUTPUT_PROFILE_DEFINITIONS


class MediaPreparationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PreparedMedia:
    filename: str
    mime_type: str
    output_profile: str
    audio_bytes: bytes
    sha256: str
    duration_seconds: float | None


def prepare_video_audio(*, source_bytes: bytes, source_filename: str, output_profile: OutputProfile) -> PreparedMedia:
    """Extract exactly the first audio stream with ffmpeg.

    No guessed codecs, fallback source upload, or persistence: a video without
    an audio stream fails closed and leaves its native source untouched.
    """
    if not source_bytes:
        raise MediaPreparationError("source_empty", "Source media is empty")

    definition = OUTPUT_PROFILE_DEFINITIONS[output_profile]
    with tempfile.TemporaryDirectory(prefix="stage2-media-") as temp_dir:
        source_path = Path(temp_dir) / _safe_name(source_filename, "source")
        output_path = Path(temp_dir) / f"audio.{definition.container}"
        source_path.write_bytes(source_bytes)
        duration = _probe_audio_duration(source_path)
        command = [
            "ffmpeg", "-nostdin", "-v", "error", "-i", str(source_path),
            "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", definition.codec,
        ]
        if definition.container == "mp3":
            command.extend(["-b:a", "64k"])
        command.extend(["-f", definition.container, "-y", str(output_path)])
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=300)
        except FileNotFoundError as exc:
            raise MediaPreparationError("ffmpeg_unavailable", "Media processor is unavailable") from exc
        except subprocess.TimeoutExpired as exc:
            raise MediaPreparationError("media_preparation_timeout", "Audio extraction timed out") from exc
        if completed.returncode != 0 or not output_path.is_file():
            raise MediaPreparationError("media_preparation_failed", "Audio track could not be extracted")
        audio_bytes = output_path.read_bytes()
        if not audio_bytes:
            raise MediaPreparationError("prepared_audio_empty", "Extracted audio is empty")
    return PreparedMedia(
        filename=f"{Path(_safe_name(source_filename, 'video')).stem}.mp3" if definition.container == "mp3" else f"{Path(_safe_name(source_filename, 'video')).stem}.{definition.container}",
        mime_type=definition.mime_type,
        output_profile=output_profile.value,
        audio_bytes=audio_bytes,
        sha256=hashlib.sha256(audio_bytes).hexdigest(),
        duration_seconds=duration,
    )


def _probe_audio_duration(source_path: Path) -> float | None:
    command = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of", "json", str(source_path)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    except FileNotFoundError as exc:
        raise MediaPreparationError("ffprobe_unavailable", "Media inspector is unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaPreparationError("media_probe_timeout", "Media inspection timed out") from exc
    if completed.returncode != 0:
        raise MediaPreparationError("source_has_no_audio_stream", "Video has no audio stream")
    try:
        streams = json.loads(completed.stdout).get("streams") or []
        raw = streams[0].get("duration") if streams else None
        return float(raw) if raw is not None else None
    except (IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _safe_name(name: str, fallback: str) -> str:
    candidate = Path(name or fallback).name
    return candidate or fallback
