from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path

import pytest

from stage2_stt.config import OutputProfile
from stage2_stt.media_preparation import MediaPreparationError, prepare_video_audio


def test_prepare_video_audio_extracts_only_first_audio_track(monkeypatch, tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(command, 0, '{"streams":[{"duration":"12.5"}]}', "")
        Path(command[-1]).write_bytes(b"prepared-mp3")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("stage2_stt.media_preparation.subprocess.run", run)

    result = prepare_video_audio(source_file=BytesIO(b"video"), source_filename="call.mp4", output_profile=OutputProfile.MP3_HIGH_COMPAT, work_dir=tmp_path)

    assert result.filename == "call.mp3"
    assert result.mime_type == "audio/mpeg"
    assert result.audio_path.read_bytes() == b"prepared-mp3"
    assert result.size_bytes == len(b"prepared-mp3")
    assert not (tmp_path / "source-media").exists()
    assert result.duration_seconds == 12.5
    assert ["-map", "0:a:0"] == calls[1][calls[1].index("-map"):calls[1].index("-map") + 2]
    assert "-vn" in calls[1]


def test_prepare_video_audio_fails_closed_when_video_has_no_audio(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "stage2_stt.media_preparation.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "no stream"),
    )

    with pytest.raises(MediaPreparationError, match="Video has no audio stream") as raised:
        prepare_video_audio(source_file=BytesIO(b"video"), source_filename="silent.mp4", output_profile=OutputProfile.MP3_HIGH_COMPAT, work_dir=tmp_path)

    assert raised.value.code == "source_has_no_audio_stream"


def test_prepare_video_audio_never_requests_entire_large_source(monkeypatch, tmp_path):
    class BoundedReader(BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024
            return super().read(size)

    def run(command, **kwargs):
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(command, 0, '{"streams":[{}]}', "")
        Path(command[-1]).write_bytes(b"mp3")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("stage2_stt.media_preparation.subprocess.run", run)
    source = BoundedReader(b"v" * (3 * 1024 * 1024 + 1))
    result = prepare_video_audio(source_file=source, source_filename="large.mp4", output_profile=OutputProfile.MP3_HIGH_COMPAT, work_dir=tmp_path)

    assert result.size_bytes == 3
    assert not (tmp_path / "source-media").exists()
