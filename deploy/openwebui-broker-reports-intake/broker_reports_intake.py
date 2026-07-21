"""OpenWebUI v0.9.6 adapters for server-authoritative Broker Reports intake."""

from __future__ import annotations

import asyncio
import hashlib
import io
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from open_webui.internal.db import get_async_session
from open_webui.models.chat_messages import ChatMessage
from open_webui.models.chats import Chat, ChatFile
from open_webui.models.files import File as OpenWebUIFile
from open_webui.storage.provider import Storage
from open_webui.utils.auth import get_verified_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.routers.broker_reports_intake_contract import (
    ACTION_ATTESTATION_KEY,
    INTAKE_SCHEMA_VERSION,
    PROCESS_NATIVE,
    PROTECTED_ACTION_ID,
    BrokerReportsIntakeService,
    IneligibleSource,
    IntakeActor,
    IntakeCleanupFailure,
    IntakeConflict,
    IntakeContractError,
    IntakePersistenceFailure,
    InvalidIntakeRequest,
    NativeProcessingForbidden,
    StoredSource,
    action_attestation,
    assert_native_processing_allowed as assert_contract_native_processing_allowed,
    resolve_receipts,
    validate_receipt,
)


router = APIRouter()

_CLIENT_PROCESSING_OVERRIDES = frozenset(
    {
        "collection_name",
        "knowledge_id",
        "process",
        "process_in_background",
    }
)
_MAX_ACTION_BODY_NODES = 4096
_MAX_ACTION_BODY_DEPTH = 8


def _as_stored_source(source: Any) -> StoredSource:
    return StoredSource(
        id=str(source.id),
        user_id=str(source.user_id),
        source_hash=source.hash,
        filename=str(source.filename),
        path=source.path,
        data=source.data if isinstance(source.data, Mapping) else {},
        meta=source.meta if isinstance(source.meta, Mapping) else {},
        created_at=int(source.created_at or 0),
        updated_at=int(source.updated_at or 0),
    )


class OpenWebUIIntakeRepository:
    """Feature-owned repository; every operation receives the request transaction."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_owned(self, source_id: str, owner_user_id: str) -> StoredSource | None:
        result = await self._db.execute(
            select(OpenWebUIFile).where(
                OpenWebUIFile.id == source_id,
                OpenWebUIFile.user_id == owner_user_id,
            )
        )
        source = result.scalars().first()
        return _as_stored_source(source) if source is not None else None

    async def create(self, source: StoredSource) -> bool:
        row = OpenWebUIFile(
            id=source.id,
            user_id=source.user_id,
            hash=source.source_hash,
            filename=source.filename,
            path=source.path,
            data=dict(source.data or {}),
            meta=dict(source.meta or {}),
            created_at=source.created_at,
            updated_at=source.updated_at,
        )
        self._db.add(row)
        try:
            await self._db.commit()
            return True
        except IntegrityError:
            await self._db.rollback()
            return False
        except Exception:
            await self._db.rollback()
            raise

    async def get_action_chat_source_ids(
        self,
        *,
        chat_id: str,
        response_message_id: str,
        owner_user_id: str,
    ) -> list[str]:
        """Resolve the exact assistant-parent attachment set from server state."""

        if not chat_id or not response_message_id:
            return []
        if len(chat_id) > 256 or len(response_message_id) > 256:
            raise IneligibleSource("Chat or message identity is invalid.")

        owned_chat = await self._db.scalar(
            select(Chat.id).where(
                Chat.id == chat_id,
                Chat.user_id == owner_user_id,
            )
        )
        if owned_chat is None:
            raise IneligibleSource("Action chat is not owned by the authenticated user.")

        parent_message_id = await self._db.scalar(
            select(ChatMessage.parent_id).where(
                ChatMessage.id == f"{chat_id}-{response_message_id}",
                ChatMessage.chat_id == chat_id,
                ChatMessage.user_id == owner_user_id,
                ChatMessage.role == "assistant",
            )
        )
        if not parent_message_id:
            return []

        result = await self._db.execute(
            select(ChatFile.file_id)
            .where(
                ChatFile.chat_id == chat_id,
                ChatFile.message_id == parent_message_id,
                ChatFile.user_id == owner_user_id,
            )
            .order_by(ChatFile.created_at.asc(), ChatFile.id.asc())
        )
        return [str(file_id) for file_id in result.scalars().all()]


class OpenWebUIIntakeStorage:
    async def store(
        self,
        payload: bytes,
        object_name: str,
        tags: Mapping[str, str],
    ) -> str:
        contents, path = await asyncio.to_thread(
            Storage.upload_file,
            io.BytesIO(payload),
            object_name,
            dict(tags),
        )
        if not isinstance(contents, bytes) or hashlib.sha256(contents).digest() != hashlib.sha256(
            payload
        ).digest():
            try:
                await asyncio.to_thread(Storage.delete_file, path)
            except Exception as error:
                raise IntakeCleanupFailure(
                    "Storage byte-integrity compensation failed."
                ) from error
            raise IntakePersistenceFailure(
                "Storage provider did not persist the exact intake bytes."
            )
        return str(path)

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(Storage.delete_file, path)


def build_broker_reports_intake_repository(db: AsyncSession) -> OpenWebUIIntakeRepository:
    """FACTORY_REQUIRED: canonical authenticated receipt repository adapter."""

    return OpenWebUIIntakeRepository(db)


def build_broker_reports_intake_storage() -> OpenWebUIIntakeStorage:
    """FACTORY_REQUIRED: canonical private-source storage adapter."""

    return OpenWebUIIntakeStorage()


def build_broker_reports_intake_service(db: AsyncSession) -> BrokerReportsIntakeService:
    """FACTORY_REQUIRED: sole production intake service construction path."""

    return BrokerReportsIntakeService(
        build_broker_reports_intake_repository(db),
        build_broker_reports_intake_storage(),
    )


def _error_status(error: IntakeContractError) -> int:
    if isinstance(error, InvalidIntakeRequest):
        return 400
    if isinstance(error, IntakeConflict):
        return 409
    if isinstance(error, IneligibleSource):
        return 422
    if isinstance(error, NativeProcessingForbidden):
        return 409
    if isinstance(error, (IntakePersistenceFailure, IntakeCleanupFailure)):
        return 500
    return 500


def _http_error(error: IntakeContractError) -> HTTPException:
    return HTTPException(
        status_code=_error_status(error),
        detail={"code": error.code, "message": str(error)},
    )


@router.post("/intake")
async def accept_private_source(
    request: Request,
    file: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Accept bytes without exposing any client-selectable native processing mode."""

    overrides = sorted(_CLIENT_PROCESSING_OVERRIDES.intersection(request.query_params.keys()))
    if overrides:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "broker_reports_client_processing_override_denied",
                "fields": overrides,
            },
        )

    payload = await file.read()
    try:
        result = await build_broker_reports_intake_service(db).accept(
            actor=IntakeActor(user_id=user.id),
            idempotency_key=idempotency_key,
            filename=file.filename or "",
            content_type=file.content_type,
            payload=payload,
        )
        response = result.public_dict()
        response["intake_schema_version"] = INTAKE_SCHEMA_VERSION
        response["process"] = PROCESS_NATIVE
        return response
    except IntakeContractError as error:
        raise _http_error(error) from error


@router.get("/intake/{source_id}/receipt")
async def get_private_source_receipt(
    source_id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    repository = build_broker_reports_intake_repository(db)
    source = await repository.get_owned(source_id, user.id)
    if source is None:
        raise _http_error(IneligibleSource("Receipt-backed source was not found."))
    try:
        return validate_receipt(source, user.id).public_dict()
    except IntakeContractError as error:
        raise _http_error(error) from error


def assert_native_processing_allowed(source: Any) -> None:
    """FORBIDDEN choke-point guard imported by retrieval single and batch paths."""

    try:
        assert_contract_native_processing_allowed(source)
    except IntakeContractError as error:
        raise _http_error(error) from error


def _file_id_from_candidate(candidate: Any) -> str:
    if not isinstance(candidate, Mapping):
        return ""
    nested = candidate.get("file")
    source = {**candidate, **nested} if isinstance(nested, Mapping) else candidate
    source_id = source.get("id") or source.get("file_id")
    if source_id:
        return str(source_id)
    for key in ("url", "path", "href"):
        value = str(source.get(key) or "")
        marker = "/api/v1/files/"
        if marker in value:
            return value.split(marker, 1)[1].split("/", 1)[0].split("?", 1)[0].strip()
    return ""


def _collect_action_source_ids(form_data: Mapping[str, Any]) -> list[str]:
    stack: list[tuple[Any, int]] = [(form_data, 0)]
    source_ids: list[str] = []
    seen: set[str] = set()
    visited = 0

    while stack:
        value, depth = stack.pop()
        visited += 1
        if visited > _MAX_ACTION_BODY_NODES:
            raise IneligibleSource("Action body exceeds the bounded intake-reference graph.")
        if depth > _MAX_ACTION_BODY_DEPTH:
            raise IneligibleSource("Action file references exceed the bounded nesting depth.")

        if isinstance(value, Mapping):
            for key, child in value.items():
                if key == ACTION_ATTESTATION_KEY:
                    continue
                if key == "files":
                    candidates = child if isinstance(child, list) else [child]
                    for candidate in candidates:
                        source_id = _file_id_from_candidate(candidate)
                        if source_id and source_id not in seen:
                            seen.add(source_id)
                            source_ids.append(source_id)
                    continue
                if key in {"content", "text"}:
                    continue
                if isinstance(child, (Mapping, list)):
                    stack.append((child, depth + 1))
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, (Mapping, list)):
                    stack.append((child, depth + 1))

    return source_ids


async def guard_protected_action_form(
    action_id: str,
    form_data: dict[str, Any],
    *,
    user: Any,
    db: AsyncSession,
) -> None:
    """Replace client claims with DB-backed attestation before Action invocation."""

    base_action_id = action_id.split(".", 1)[0]
    if base_action_id != PROTECTED_ACTION_ID:
        return

    # A direct client may submit this key, so it is removed before any checks and
    # replaced only with a server-generated value after receipt verification.
    form_data.pop(ACTION_ATTESTATION_KEY, None)
    try:
        repository = build_broker_reports_intake_repository(db)
        source_ids = _collect_action_source_ids(form_data)
        if not source_ids:
            # OpenWebUI v0.9.6 Chat.svelte omits message.files from Action POST.
            # Resolve the persisted assistant-parent chat_file relation instead
            # of trusting a client reconstruction.  This is reload-safe.
            source_ids = await repository.get_action_chat_source_ids(
                chat_id=str(form_data.get("chat_id") or ""),
                response_message_id=str(form_data.get("id") or ""),
                owner_user_id=user.id,
            )
        receipts = await resolve_receipts(
            source_ids,
            actor=IntakeActor(user_id=user.id),
            repository=repository,
        )
        form_data[ACTION_ATTESTATION_KEY] = action_attestation(receipts)
    except IntakeContractError as error:
        raise _http_error(error) from error
