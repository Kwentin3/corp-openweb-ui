"""Bounded-memory extraction of the first audio track from uploaded video."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

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
    audio_path: Path
    size_bytes: int
    sha256: str
    duration_seconds: float | None


COPY_CHUNK_SIZE = 1024 * 1024


def prepare_video_audio(*, source_file: BinaryIO, source_filename: str, output_profile: OutputProfile, work_dir: Path) -> PreparedMedia:
    """Copy in bounded chunks, then let FFmpeg read and write on disk."""
    definition = OUTPUT_PROFILE_DEFINITIONS[output_profile]
    source_path = work_dir / "source-media"
    output_path = work_dir / f"audio.{definition.container}"
    with source_path.open("wb") as destination:
        shutil.copyfileobj(source_file, destination, length=COPY_CHUNK_SIZE)
    if not source_path.stat().st_size:
        raise MediaPreparationError("source_empty", "Source media is empty")
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
    source_path.unlink()
    size_bytes = output_path.stat().st_size
    if not size_bytes:
        raise MediaPreparationError("prepared_audio_empty", "Extracted audio is empty")
    return PreparedMedia(
        filename=f"{Path(_safe_name(source_filename, 'video')).stem}.{definition.container}",
        mime_type=definition.mime_type,
        output_profile=output_profile.value,
        audio_path=output_path,
        size_bytes=size_bytes,
        sha256=_sha256_file(output_path),
        duration_seconds=duration,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(COPY_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
