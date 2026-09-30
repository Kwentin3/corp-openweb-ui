from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
import subprocess
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
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                input=input_text,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=self._settings.timeout_seconds,
            )
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
