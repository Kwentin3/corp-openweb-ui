from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
from tempfile import TemporaryDirectory
from typing import Protocol

from .config import Settings


class OfficeCliFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class OfficeCliOutput:
    command: tuple[str, ...]
    text: str
    content_sha256: str
    auto_resident_disabled: bool
    diagnostics: str = ""


class OfficeCliExecutor(Protocol):
    def run(self, *arguments: str, input_text: str | None = None) -> OfficeCliOutput: ...


class SubprocessOfficeCliExecutor:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(self, *arguments: str, input_text: str | None = None) -> OfficeCliOutput:
        command = (self._settings.binary, *arguments)
        environment = {
            **os.environ,
            "OFFICECLI_SKIP_UPDATE": "1",
            "OFFICECLI_NO_AUTO_RESIDENT": "1",
        }
        try:
            with TemporaryDirectory(prefix="officecli-runtime-") as runtime_directory, subprocess.Popen(
                command,
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                env={
                    **environment,
                    # Chromium's scoped profiles otherwise accumulate under HOME
                    # across nonresident calls and exhaust the bounded /tmp mount.
                    "XDG_CACHE_HOME": str(Path(runtime_directory) / "cache"),
                    "XDG_CONFIG_HOME": str(Path(runtime_directory) / "config"),
                    "TMPDIR": runtime_directory,
                    "TMP": runtime_directory,
                    "TEMP": runtime_directory,
                },
                start_new_session=os.name == "posix",
            ) as process:
                try:
                    stdout, stderr = process.communicate(input_text, timeout=self._settings.timeout_seconds)
                finally:
                    # Nonresident CLI calls own their browser descendants too.
                    # A timed-out leader alone does not stop Chromium or release PID slots.
                    if os.name == "posix":
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    elif process.poll() is None:
                        process.kill()
                    process.communicate()
                completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        except OSError as error:
            raise OfficeCliFailure("officecli executable is unavailable") from error
        except subprocess.TimeoutExpired as error:
            raise OfficeCliFailure("officecli guidance command timed out") from error

        if completed.returncode != 0:
            if arguments[0] == "validate":
                try:
                    validation = json.loads(completed.stdout)
                except json.JSONDecodeError:
                    validation = None
                if isinstance(validation, dict) and validation.get("success") is False:
                    return OfficeCliOutput(
                        command=command,
                        text=completed.stdout,
                        content_sha256=sha256(completed.stdout.encode("utf-8")).hexdigest(),
                        auto_resident_disabled=True,
                        diagnostics=completed.stderr.strip(),
                    )
            detail = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part) or "no output"
            raise OfficeCliFailure(f"officecli guidance command failed: {detail}")

        text = completed.stdout
        return OfficeCliOutput(
            command=command,
            text=text,
            content_sha256=sha256(text.encode("utf-8")).hexdigest(),
            auto_resident_disabled=True,
            diagnostics=completed.stderr.strip(),
        )
