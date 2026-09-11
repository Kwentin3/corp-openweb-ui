from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    binary: str
    timeout_seconds: int
    expected_version: str
    openwebui_base_url: str


def load_settings() -> Settings:
    timeout_raw = os.environ.get("OFFICECLI_PROOF_TIMEOUT_SECONDS", "30")
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as error:
        raise RuntimeError("OFFICECLI_PROOF_TIMEOUT_SECONDS must be an integer") from error
    if timeout_seconds < 1 or timeout_seconds > 120:
        raise RuntimeError("OFFICECLI_PROOF_TIMEOUT_SECONDS must be between 1 and 120")

    openwebui_base_url = os.environ.get("OPENWEBUI_BASE_URL", "")
    if openwebui_base_url:
        parsed = urlparse(openwebui_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise RuntimeError("OPENWEBUI_BASE_URL must be an absolute http(s) URL without credentials")

    return Settings(
        binary=os.environ.get("OFFICECLI_BINARY", "/usr/local/bin/officecli"),
        timeout_seconds=timeout_seconds,
        expected_version=os.environ.get("OFFICECLI_EXPECTED_VERSION", "1.0.148"),
        openwebui_base_url=openwebui_base_url.rstrip("/"),
    )
