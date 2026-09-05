from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


OPENWEBUI_FILE_BYTES_POLICY_VERSION = "broker_reports_openwebui_file_bytes_v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class OpenWebUIFileBytesError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OpenWebUIOwnedFile:
    file_id: str
    user_id: str
    filename: str
    content_type: str
    payload: bytes
    sha256: str


class OpenWebUIFileBytesResolverFactory:
    """Sole composition point for authenticated OpenWebUI file reads."""

    FACTORY_REQUIRED = (
        "OpenWebUIFileBytesResolverFactory.create is the only production source-byte "
        "composition point"
    )

    @staticmethod
    def create() -> "OpenWebUIFileBytesResolver":
        return OpenWebUIFileBytesResolver()


class OpenWebUIFileBytesResolver:
    async def resolve(
        self,
        *,
        file_id: str,
        actor_user_id: str,
    ) -> OpenWebUIOwnedFile:
        source_id = str(file_id or "").strip()
        actor = str(actor_user_id or "").strip()
        if not source_id:
            raise OpenWebUIFileBytesError("openwebui_file_id_missing")
        if not actor:
            raise OpenWebUIFileBytesError("openwebui_file_actor_missing")
        try:
            from open_webui.models.files import Files
            from open_webui.storage.provider import Storage
        except ImportError as exc:
            raise OpenWebUIFileBytesError(
                "openwebui_file_boundary_unavailable"
            ) from exc

        try:
            row = await Files.get_file_by_id(source_id)
        except Exception as exc:
            raise OpenWebUIFileBytesError("openwebui_file_lookup_failed") from exc
        if row is None or str(getattr(row, "user_id", "") or "") != actor:
            raise OpenWebUIFileBytesError("openwebui_file_not_owned")

        row_id = str(getattr(row, "id", "") or "")
        row_path = str(getattr(row, "path", "") or "")
        filename = str(getattr(row, "filename", "") or "")
        meta = getattr(row, "meta", None)
        meta = meta if isinstance(meta, dict) else {}
        if row_id != source_id or not row_path or not filename:
            raise OpenWebUIFileBytesError("openwebui_file_record_invalid")
        try:
            resolved_path = await asyncio.to_thread(Storage.get_file, row_path)
            payload = await asyncio.to_thread(Path(str(resolved_path)).read_bytes)
        except Exception as exc:
            raise OpenWebUIFileBytesError("openwebui_file_storage_read_failed") from exc
        if not payload:
            raise OpenWebUIFileBytesError("openwebui_file_bytes_empty")

        observed_sha256 = hashlib.sha256(payload).hexdigest()
        stored_hash = str(getattr(row, "hash", "") or "").lower()
        if _SHA256_RE.fullmatch(stored_hash) and stored_hash != observed_sha256:
            raise OpenWebUIFileBytesError("openwebui_file_hash_mismatch")
        declared_size = meta.get("size")
        if type(declared_size) is int and declared_size != len(payload):
            raise OpenWebUIFileBytesError("openwebui_file_size_mismatch")

        return OpenWebUIOwnedFile(
            file_id=source_id,
            user_id=actor,
            filename=filename,
            content_type=str(meta.get("content_type") or "application/octet-stream"),
            payload=payload,
            sha256=observed_sha256,
        )
