from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol


PRIVATE_INTAKE_BYTES_POLICY_VERSION = "broker_reports_private_intake_bytes_v1"

_SOURCE_ID_RE = re.compile(
    r"^br-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class PrivateIntakeBytesError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PrivateIntakeFileRecord:
    source_id: str
    user_id: str
    source_hash: str | None
    filename: str
    path: str | None
    data: Mapping[str, Any]
    meta: Mapping[str, Any]
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class PrivateIntakeVerifiedReceipt:
    source_id: str
    source_sha256: str
    size_bytes: int


class PrivateIntakeFileRepository(Protocol):
    async def get_owned(
        self, source_id: str, actor_user_id: str
    ) -> PrivateIntakeFileRecord | None: ...


class PrivateIntakeStorage(Protocol):
    async def read_bytes(self, path: str) -> bytes: ...


class PrivateIntakeReceiptValidator(Protocol):
    def validate(
        self, record: PrivateIntakeFileRecord, actor_user_id: str
    ) -> PrivateIntakeVerifiedReceipt: ...


class PrivateIntakeBytesResolverFactory:
    def __init__(
        self,
        *,
        repository: PrivateIntakeFileRepository,
        storage: PrivateIntakeStorage,
        receipt_validator: PrivateIntakeReceiptValidator,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.receipt_validator = receipt_validator

    def create(self) -> "PrivateIntakeBytesResolver":
        return PrivateIntakeBytesResolver(
            repository=self.repository,
            storage=self.storage,
            receipt_validator=self.receipt_validator,
        )


class PrivateIntakeBytesResolver:
    def __init__(
        self,
        *,
        repository: PrivateIntakeFileRepository,
        storage: PrivateIntakeStorage,
        receipt_validator: PrivateIntakeReceiptValidator,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.receipt_validator = receipt_validator

    async def resolve(self, *, source_id: str, actor_user_id: str) -> bytes:
        if not is_private_intake_source_id(source_id):
            raise PrivateIntakeBytesError("private_intake_source_id_invalid")
        actor = str(actor_user_id or "").strip()
        if not actor:
            raise PrivateIntakeBytesError("private_intake_actor_missing")

        try:
            record = await self.repository.get_owned(source_id, actor)
        except Exception as exc:
            raise PrivateIntakeBytesError(
                "private_intake_repository_unavailable"
            ) from exc
        if record is None:
            raise PrivateIntakeBytesError("private_intake_source_not_owned")
        if record.source_id != source_id or record.user_id != actor:
            raise PrivateIntakeBytesError("private_intake_source_scope_mismatch")
        try:
            receipt = self.receipt_validator.validate(record, actor)
        except PrivateIntakeBytesError:
            raise
        except Exception as exc:
            raise PrivateIntakeBytesError("private_intake_receipt_invalid") from exc
        if receipt.source_id != source_id:
            raise PrivateIntakeBytesError("private_intake_receipt_identity_mismatch")
        if not record.path:
            raise PrivateIntakeBytesError("private_intake_storage_path_missing")
        try:
            payload = await self.storage.read_bytes(record.path)
        except Exception as exc:
            raise PrivateIntakeBytesError("private_intake_storage_read_failed") from exc
        if not isinstance(payload, bytes) or not payload:
            raise PrivateIntakeBytesError("private_intake_storage_bytes_invalid")
        if len(payload) != receipt.size_bytes:
            raise PrivateIntakeBytesError("private_intake_storage_size_mismatch")
        if not hmac.compare_digest(
            hashlib.sha256(payload).hexdigest(), str(receipt.source_sha256 or "")
        ):
            raise PrivateIntakeBytesError("private_intake_storage_hash_mismatch")
        return payload


class OpenWebUIPrivateIntakeFileRepository:
    async def get_owned(
        self, source_id: str, actor_user_id: str
    ) -> PrivateIntakeFileRecord | None:
        from open_webui.models.files import Files

        row = await Files.get_file_by_id(source_id)
        if row is None or str(getattr(row, "user_id", "") or "") != actor_user_id:
            return None
        return PrivateIntakeFileRecord(
            source_id=str(getattr(row, "id", "") or ""),
            user_id=str(getattr(row, "user_id", "") or ""),
            source_hash=_optional_text(getattr(row, "hash", None)),
            filename=str(getattr(row, "filename", "") or ""),
            path=_optional_text(getattr(row, "path", None)),
            data=_mapping(getattr(row, "data", None)),
            meta=_mapping(getattr(row, "meta", None)),
            created_at=int(getattr(row, "created_at", 0) or 0),
            updated_at=int(getattr(row, "updated_at", 0) or 0),
        )


class OpenWebUIPrivateIntakeStorage:
    async def read_bytes(self, path: str) -> bytes:
        from open_webui.storage.provider import Storage

        resolved = await asyncio.to_thread(Storage.get_file, path)
        return await asyncio.to_thread(Path(str(resolved)).read_bytes)


class OpenWebUIPrivateIntakeReceiptValidator:
    def validate(
        self, record: PrivateIntakeFileRecord, actor_user_id: str
    ) -> PrivateIntakeVerifiedReceipt:
        from open_webui.routers.broker_reports_intake_contract import (
            StoredSource,
            validate_receipt,
        )

        verified = validate_receipt(
            StoredSource(
                id=record.source_id,
                user_id=record.user_id,
                source_hash=record.source_hash,
                filename=record.filename,
                path=record.path,
                data=record.data,
                meta=record.meta,
                created_at=record.created_at,
                updated_at=record.updated_at,
            ),
            actor_user_id,
        )
        return PrivateIntakeVerifiedReceipt(
            source_id=str(verified.source_id),
            source_sha256=str(verified.source_sha256),
            size_bytes=int(verified.size_bytes),
        )


class OpenWebUIPrivateIntakeBytesResolverFactory:
    def create(self) -> PrivateIntakeBytesResolver:
        return PrivateIntakeBytesResolverFactory(
            repository=OpenWebUIPrivateIntakeFileRepository(),
            storage=OpenWebUIPrivateIntakeStorage(),
            receipt_validator=OpenWebUIPrivateIntakeReceiptValidator(),
        ).create()


def is_private_intake_source_id(value: Any) -> bool:
    return bool(_SOURCE_ID_RE.fullmatch(str(value or "")))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
