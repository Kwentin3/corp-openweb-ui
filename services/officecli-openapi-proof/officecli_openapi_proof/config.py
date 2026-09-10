from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    binary: str
    timeout_seconds: int
    expected_version: str


def load_settings() -> Settings:
    timeout_raw = os.environ.get("OFFICECLI_PROOF_TIMEOUT_SECONDS", "30")
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as error:
        raise RuntimeError("OFFICECLI_PROOF_TIMEOUT_SECONDS must be an integer") from error
    if timeout_seconds < 1 or timeout_seconds > 120:
        raise RuntimeError("OFFICECLI_PROOF_TIMEOUT_SECONDS must be between 1 and 120")

    return Settings(
        binary=os.environ.get("OFFICECLI_BINARY", "/usr/local/bin/officecli"),
        timeout_seconds=timeout_seconds,
        expected_version=os.environ.get("OFFICECLI_EXPECTED_VERSION", "1.0.148"),
    )
