from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import httpx


class OpenWebUiFailure(RuntimeError):
    pass


class OpenWebUiClient(Protocol):
    def download(self, file_id: str, authorization: str, destination: Path) -> None: ...

    def upload(self, source: Path, output_name: str, authorization: str) -> dict[str, Any]: ...

    def attach(
        self, chat_id: str, message_id: str, native_file: dict[str, Any], authorization: str
    ) -> None: ...

    def delete(self, file_id: str, authorization: str) -> None: ...


class HttpOpenWebUiClient:
    """Public, caller-authorized OpenWebUI Files and chat-event API adapter."""

    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    def _headers(self, authorization: str) -> dict[str, str]:
        return {"Authorization": authorization}

    def _request(self, method: str, path: str, authorization: str, **kwargs: Any) -> httpx.Response:
        if not self._base_url:
            raise OpenWebUiFailure("OPENWEBUI_BASE_URL is required for document operations")
        try:
            response = httpx.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers(authorization),
                timeout=self._timeout_seconds,
                follow_redirects=False,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError as error:
            raise OpenWebUiFailure(f"OpenWebUI public API {method} {path} failed") from error

    def download(self, file_id: str, authorization: str, destination: Path) -> None:
        response = self._request("GET", f"/api/v1/files/{file_id}/content", authorization)
        destination.write_bytes(response.content)

    def upload(self, source: Path, output_name: str, authorization: str) -> dict[str, Any]:
        with source.open("rb") as document:
            response = self._request(
                "POST",
                "/api/v1/files/?process=false",
                authorization,
                files={
                    "file": (
                        output_name,
                        document,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        try:
            native_file = response.json()
        except ValueError as error:
            raise OpenWebUiFailure("OpenWebUI upload returned invalid JSON") from error
        if not isinstance(native_file, dict) or not isinstance(native_file.get("id"), str):
            raise OpenWebUiFailure("OpenWebUI upload did not return a native file id")
        return native_file

    def attach(
        self, chat_id: str, message_id: str, native_file: dict[str, Any], authorization: str
    ) -> None:
        self._request(
            "POST",
            f"/api/v1/chats/{chat_id}/messages/{message_id}/event",
            authorization,
            json={"type": "files", "data": {"files": [native_file]}},
        )

    def delete(self, file_id: str, authorization: str) -> None:
        self._request("DELETE", f"/api/v1/files/{file_id}", authorization)
