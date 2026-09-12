from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import httpx


class OpenWebUiFailure(RuntimeError):
    pass


class OpenWebUiUnauthorized(OpenWebUiFailure):
    """The forwarded OpenWebUI session was rejected by its native owner."""


class OpenWebUiAmbiguousAttachment(OpenWebUiFailure):
    """The current native message has more than one possible DOCX source."""


class OpenWebUiClient(Protocol):
    def verify_session(self, authorization: str) -> None: ...

    def resolve_nearest_docx_attachment(
        self, chat_id: str, message_id: str, authorization: str
    ) -> str: ...

    def resolve_nearest_xlsx_attachment(
        self, chat_id: str, message_id: str, authorization: str
    ) -> str: ...

    def resolve_nearest_pptx_attachment(
        self, chat_id: str, message_id: str, authorization: str
    ) -> str: ...

    def download(self, file_id: str, authorization: str, destination: Path) -> None: ...

    def upload(
        self, source: Path, output_name: str, authorization: str, content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ) -> dict[str, Any]: ...

    def attach(
        self, chat_id: str, message_id: str, native_file: dict[str, Any], authorization: str,
        fallback_name: str = "updated.docx", content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
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
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                raise OpenWebUiUnauthorized("forwarded OpenWebUI session was rejected") from error
            raise OpenWebUiFailure(f"OpenWebUI public API {method} {path} failed") from error
        except httpx.HTTPError as error:
            raise OpenWebUiFailure(f"OpenWebUI public API {method} {path} failed") from error

    def verify_session(self, authorization: str) -> None:
        """Delegate session authentication to the native OpenWebUI auth endpoint."""
        self._request("GET", "/api/v1/auths/", authorization)

    def download(self, file_id: str, authorization: str, destination: Path) -> None:
        response = self._request("GET", f"/api/v1/files/{file_id}/content", authorization)
        destination.write_bytes(response.content)

    def resolve_nearest_docx_attachment(
        self, chat_id: str, message_id: str, authorization: str
    ) -> str:
        return self._resolve_nearest_attachment(chat_id, message_id, authorization, ".docx")

    def resolve_nearest_xlsx_attachment(
        self, chat_id: str, message_id: str, authorization: str
    ) -> str:
        return self._resolve_nearest_attachment(chat_id, message_id, authorization, ".xlsx")

    def resolve_nearest_pptx_attachment(
        self, chat_id: str, message_id: str, authorization: str
    ) -> str:
        return self._resolve_nearest_attachment(chat_id, message_id, authorization, ".pptx")

    def _resolve_nearest_attachment(
        self, chat_id: str, message_id: str, authorization: str, suffix: str
    ) -> str:
        response = self._request("GET", f"/api/v1/chats/{chat_id}", authorization)
        try:
            chat_record = response.json()
            messages = chat_record["chat"]["history"]["messages"]
        except (KeyError, TypeError, ValueError) as error:
            raise OpenWebUiFailure("OpenWebUI chat did not contain native message history") from error
        if not isinstance(messages, dict):
            raise OpenWebUiFailure("OpenWebUI chat message history was not an object")

        visited: set[str] = set()
        current_id: str | None = message_id
        while current_id and current_id not in visited:
            visited.add(current_id)
            message = messages.get(current_id)
            if not isinstance(message, dict):
                break
            files = message.get("files", [])
            if isinstance(files, list):
                matching_file_ids: list[str] = []
                for native_file in files:
                    if not isinstance(native_file, dict):
                        continue
                    name = native_file.get("name") or native_file.get("filename") or ""
                    file_id = native_file.get("id") or native_file.get("url")
                    if isinstance(name, str) and name.lower().endswith(suffix) and isinstance(file_id, str):
                        if file_id not in matching_file_ids:
                            matching_file_ids.append(file_id)
                if len(matching_file_ids) == 1:
                    return matching_file_ids[0]
                if len(matching_file_ids) > 1:
                    raise OpenWebUiAmbiguousAttachment(
                        f"multiple {suffix[1:].upper()} attachments exist in the nearest native message; use an explicit file_id"
                    )
            parent_id = message.get("parentId")
            current_id = parent_id if isinstance(parent_id, str) else None

        raise OpenWebUiFailure(f"no {suffix[1:].upper()} attachment exists in the native message ancestry")

    def upload(
        self, source: Path, output_name: str, authorization: str, content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ) -> dict[str, Any]:
        with source.open("rb") as document:
            response = self._request(
                "POST",
                "/api/v1/files/?process=false",
                authorization,
                files={
                    "file": (
                        output_name,
                        document,
                        content_type,
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
        self, chat_id: str, message_id: str, native_file: dict[str, Any], authorization: str,
        fallback_name: str = "updated.docx", content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ) -> None:
        file_id = native_file.get("id")
        if not isinstance(file_id, str) or not file_id:
            raise OpenWebUiFailure("OpenWebUI upload did not return a native file id")

        metadata = native_file.get("meta")
        metadata = metadata if isinstance(metadata, dict) else {}
        filename = native_file.get("filename")
        filename = filename if isinstance(filename, str) and filename else fallback_name
        chat_file = {
            "type": "file",
            "file": native_file,
            "id": file_id,
            "url": file_id,
            "name": filename,
            "status": "uploaded",
            "size": metadata.get("size"),
            "content_type": metadata.get(
                "content_type",
                content_type,
            ),
        }
        event_path = f"/api/v1/chats/{chat_id}/messages/{message_id}/event"
        event_data = {"files": [chat_file]}
        # In the pinned OpenWebUI runtime, ``files`` persists the attachment in
        # the native message history, while ``chat:message:files`` updates the
        # active chat. Both are native events with distinct responsibilities.
        self._request("POST", event_path, authorization, json={"type": "files", "data": event_data})
        self._request(
            "POST",
            event_path,
            authorization,
            json={"type": "chat:message:files", "data": event_data},
        )

    def delete(self, file_id: str, authorization: str) -> None:
        self._request("DELETE", f"/api/v1/files/{file_id}", authorization)
