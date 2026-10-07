"""Offline checks of the installed STT artifact, not provider acceptance."""

import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import tempfile

from stage2_stt.config import OutputProfile
from stage2_stt.media_preparation import MediaPreparationError, prepare_video_audio


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=30)


def main():
    for line in Path("/app/requirements.lock").read_text().splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            assert importlib.metadata.version(name) == version, name

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for suffix in ("mp4", "m4a"):
            source = root / f"source.{suffix}"
            run("ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                "sine=frequency=440:duration=1", "-c:a", "aac", str(source))
            work = root / suffix
            work.mkdir()
            with source.open("rb") as stream:
                prepared = prepare_video_audio(
                    source_file=stream, source_filename=source.name,
                    output_profile=OutputProfile.MP3_HIGH_COMPAT, work_dir=work,
                )
            streams = json.loads(run("ffprobe", "-v", "error", "-show_streams",
                                     "-of", "json", str(prepared.audio_path)))["streams"]
            assert len(streams) == 1
            assert streams[0]["codec_name"] == "mp3"
            assert streams[0]["sample_rate"] == "16000"
            assert streams[0]["channels"] == 1
            assert 0.8 <= float(streams[0]["duration"]) <= 1.3
            data = prepared.audio_path.read_bytes()
            assert prepared.size_bytes == len(data) > 0
            assert prepared.sha256 == hashlib.sha256(data).hexdigest()
            assert prepared.filename == "source.mp3"
            assert not (work / "source-media").exists()

        silent = root / "silent.mp4"
        run("ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
            "color=black:size=16x16:duration=1", "-c:v", "mpeg4", str(silent))
        work = root / "silent"
        work.mkdir()
        with silent.open("rb") as stream:
            try:
                prepare_video_audio(source_file=stream, source_filename=silent.name,
                                    output_profile=OutputProfile.MP3_HIGH_COMPAT, work_dir=work)
            except MediaPreparationError as error:
                assert error.code == "source_has_no_audio_stream"
            else:
                raise AssertionError("Silent video must not be accepted as audio")
    print("Installed dependency lock, MP4/M4A -> MP3 and silent-video rejection passed; no provider calls")


if __name__ == "__main__":
    main()
