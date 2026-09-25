"""Pinned OpenWebUI v0.9.6 overlay for a derived-media lifecycle.

It is intentionally a narrow integration owner: OpenWebUI remains owner of
Files, chat JSON, normalized chat_message rows, ChatFile links and Storage.
The STT Filter only asks this module to persist a derived audio file and, after
successful transcription, replace one source-video attachment with it.
"""

from __future__ import annotations

import asyncio
import copy
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from open_webui.internal.db import get_async_db_context
from open_webui.models.chat_messages import ChatMessage
from open_webui.models.chats import Chat, ChatFile
from open_webui.models.files import File, FileForm, Files
from open_webui.storage.provider import Storage


class MediaLifecycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class DerivedAudioFile:
    file_id: str
    filename: str
    mime_type: str
    size_bytes: int


async def persist_prepared_audio(*, user_id: str, source_file_id: str, filename: str, mime_type: str, audio_path: Path, source_sha256: str) -> DerivedAudioFile:
    """Create a normal OpenWebUI File; never persist media in the sidecar."""
    if not user_id or not audio_path.is_file() or not audio_path.stat().st_size:
        raise MediaLifecycleError("Derived audio is unavailable")
    source = await Files.get_file_by_id_and_user_id(source_file_id, user_id)
    if source is None:
        raise MediaLifecycleError("Source video is unavailable")
    file_id = str(uuid.uuid4())
    storage_name = f"{file_id}_{filename}"
    storage_path: str | None = None
    try:
        def store_audio() -> tuple[int, str, str]:
            with audio_path.open("rb") as audio:
                return Storage.upload_file_streaming(
                    audio, storage_name,
                    {"OpenWebUI-User-Id": user_id, "OpenWebUI-File-Id": file_id},
                )

        size_bytes, file_hash, storage_path = await asyncio.to_thread(store_audio)
        item = await Files.insert_new_file(
            user_id,
            FileForm(
                id=file_id,
                filename=filename,
                path=storage_path,
                data={
                    "stage2_media_lifecycle": {
                        "state": "prepared_audio_created_v1",
                        "source_file_id": source_file_id,
                        "source_sha256": source_sha256,
                    }
                },
                meta={
                    "name": filename,
                    "content_type": mime_type,
                    "size": size_bytes,
                    "file_hash": file_hash,
                },
            ),
        )
    except Exception as exc:
        try:
            if storage_path:
                await asyncio.to_thread(Storage.delete_file, storage_path)
        except Exception:
            pass
        raise MediaLifecycleError("Could not save normalized audio") from exc
    if item is None:
        try:
            await asyncio.to_thread(Storage.delete_file, storage_path)
        except Exception:
            pass
        raise MediaLifecycleError("Could not save normalized audio")
    return DerivedAudioFile(file_id=file_id, filename=filename, mime_type=mime_type, size_bytes=size_bytes)


async def replace_source_video_with_audio(*, user_id: str, chat_id: str | None, message_id: str | None, source_file_id: str, audio_file_id: str, transcript_hash: str | None) -> None:
    """Atomically switch all chat DB representations before source deletion.

    Storage deletion is necessarily post-commit.  Its retry receipt remains on
    the derived File, so a failed physical delete can be retried without ever
    restoring a dead attachment to the chat.
    """
    if not all((user_id, source_file_id, audio_file_id)):
        raise MediaLifecycleError("Media lifecycle context is incomplete")
    source_path: str | None = None
    try:
        async with get_async_db_context() as db:
            source = await db.get(File, source_file_id)
            audio = await db.get(File, audio_file_id)
            if not source or not audio:
                raise MediaLifecycleError("Media lifecycle record is unavailable")
            if source.user_id != user_id or audio.user_id != user_id:
                raise MediaLifecycleError("Media lifecycle access denied")
            source_links = (await db.execute(select(ChatFile).where(ChatFile.file_id == source_file_id))).scalars().all()
            if len(source_links) != 1:
                raise MediaLifecycleError("Source video has an unsafe attachment scope")
            source_link = source_links[0]
            resolved_chat_id = source_link.chat_id
            resolved_message_id = source_link.message_id
            # Function outlets run for the assistant response, but the source
            # media belongs to the preceding user message.  ``message_id`` is
            # therefore advisory only; the unique native ChatFile link is the
            # authoritative owner.  The chat id remains a useful scope guard.
            if chat_id and chat_id != resolved_chat_id:
                raise MediaLifecycleError("Source video has an unsafe attachment scope")
            chat = await db.get(Chat, resolved_chat_id)
            message = await db.get(ChatMessage, f"{resolved_chat_id}-{resolved_message_id}")
            if not chat or not message:
                raise MediaLifecycleError("Media lifecycle record is unavailable")
            if chat.user_id != user_id:
                raise MediaLifecycleError("Media lifecycle access denied")
            existing_audio_links = (await db.execute(select(ChatFile).where(ChatFile.chat_id == resolved_chat_id, ChatFile.file_id == audio_file_id))).scalars().all()
            if existing_audio_links:
                raise MediaLifecycleError("Derived audio is already attached")
            descriptor = _audio_descriptor(audio)
            history = copy.deepcopy(chat.chat or {})
            messages = (history.get("history") or {}).get("messages") or {}
            stored_message = messages.get(resolved_message_id)
            if not isinstance(stored_message, dict):
                raise MediaLifecycleError("Source message is unavailable")
            stored_message["files"] = _replace_exact_file(stored_message.get("files"), source_file_id, descriptor)
            message.files = _replace_exact_file(message.files, source_file_id, descriptor)
            lifecycle = dict(audio.data or {}).get("stage2_media_lifecycle") or {}
            lifecycle.update({"state": "chat_replaced_v1", "source_file_id": source_file_id, "source_storage_path": source.path, "transcript_hash": transcript_hash})
            audio.data = {**(audio.data or {}), "stage2_media_lifecycle": lifecycle}
            now = int(time.time())
            chat.chat = history
            chat.updated_at = now
            await db.execute(delete(ChatFile).where(ChatFile.id == source_links[0].id))
            db.add(ChatFile(id=str(uuid.uuid4()), user_id=user_id, chat_id=resolved_chat_id, message_id=resolved_message_id, file_id=audio_file_id, created_at=now, updated_at=now))
            source_path = source.path
            await db.delete(source)
            await db.commit()
    except MediaLifecycleError:
        raise
    except Exception as exc:
        raise MediaLifecycleError("Could not replace source video safely") from exc
    try:
        if source_path:
            await asyncio.to_thread(Storage.delete_file, source_path)
    except Exception:
        await Files.update_file_data_by_id(audio_file_id, {"stage2_media_lifecycle": {"state": "storage_cleanup_pending_v1", "source_file_id": source_file_id, "source_storage_path": source_path, "transcript_hash": transcript_hash}})


def _replace_exact_file(files: Any, source_file_id: str, replacement: dict) -> list[dict]:
    if not isinstance(files, list):
        raise MediaLifecycleError("Source attachment is unavailable")
    replaced = 0
    result: list[dict] = []
    for item in files:
        if _attachment_id(item) == source_file_id:
            result.append(copy.deepcopy(replacement))
            replaced += 1
        else:
            result.append(copy.deepcopy(item))
    if replaced != 1:
        raise MediaLifecycleError("Source attachment has an unsafe message scope")
    return result


def _attachment_id(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    nested = item.get("file")
    if isinstance(nested, dict) and nested.get("id"):
        return str(nested["id"])
    return str(item["id"]) if item.get("id") else None


def _audio_descriptor(audio: File) -> dict:
    meta = dict(audio.meta or {})
    return {"type": "file", "id": audio.id, "name": audio.filename, "content_type": meta.get("content_type"), "size": meta.get("size"), "file": {"id": audio.id, "filename": audio.filename, "meta": meta}}
