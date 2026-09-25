#!/usr/bin/env python3
"""One-time, restartable migration of legacy video Files after a volume backup.

Run while OpenWebUI is stopped. The Stage 2 sidecar must remain running. Every
decision is scoped to the native File, ChatFile, ChatMessage, and Chat rows.
"""

from __future__ import annotations

import asyncio
import copy
import json
import time
from pathlib import Path

from sqlalchemy import delete, select, text

from open_webui.internal.db import get_async_db_context
from open_webui.models.chat_messages import ChatMessage
from open_webui.models.chats import Chat, ChatFile
from open_webui.models.files import File
from open_webui.services.stage2_media_lifecycle import _attachment_id, _audio_descriptor
from open_webui.services.stage2_video_intake import prepare_uploaded_video
from open_webui.storage.provider import Storage

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".mpeg", ".mpg"}

def _replace(files, file_id: str, replacement: dict | None) -> list:
    if not isinstance(files, list):
        raise RuntimeError("Missing native attachment list")
    matches = sum(_attachment_id(item) == file_id for item in files)
    if matches != 1:
        raise RuntimeError(f"Expected exactly one attachment, found {matches}")
    return [copy.deepcopy(replacement if _attachment_id(item) == file_id else item)
            for item in files if replacement is not None or _attachment_id(item) != file_id]


async def _scope(file_id: str) -> tuple[str, dict | None]:
    async with get_async_db_context() as db:
        file = await db.get(File, file_id)
        if file is None:
            return "gone", None
        links = (await db.execute(select(ChatFile).where(ChatFile.file_id == file_id))).scalars().all()
        if len(links) > 1:
            raise RuntimeError("Video has more than one native chat link")
        mentions = (await db.execute(text("SELECT COUNT(*) FROM chat WHERE chat LIKE :pattern"), {"pattern": f"%{file_id}%"})).scalar_one()
        if not links:
            if mentions:
                raise RuntimeError("Unlinked video is still mentioned by a chat")
            return "orphan", None
        link = links[0]
        chat = await db.get(Chat, link.chat_id)
        message = await db.get(ChatMessage, f"{link.chat_id}-{link.message_id}")
        if chat is None and message is None and not mentions:
            return "dangling", {"link_id": link.id}
        if chat is None or message is None or chat.user_id != file.user_id or link.user_id != file.user_id:
            raise RuntimeError("Video has an inconsistent chat owner")
        history = (chat.chat or {}).get("history") or {}
        stored = (history.get("messages") or {}).get(link.message_id)
        if not isinstance(stored, dict):
            raise RuntimeError("Video's native history message is missing")
        _replace(stored.get("files"), file_id, {})
        _replace(message.files, file_id, {})
        return "chat", {"chat_id": link.chat_id, "message_id": link.message_id, "link_id": link.id}


async def _delete_orphan(file_id: str, scope: str) -> None:
    async with get_async_db_context() as db:
        file = await db.get(File, file_id)
        if file is None:
            return
        path = file.path
    if path:
        await asyncio.to_thread(Storage.delete_file, path)
        # Local Storage.delete_file warns instead of raising for missing files.
        local = Path(Storage.get_file(path))
        if local.is_file():
            raise RuntimeError("Video blob survived deletion")
    async with get_async_db_context() as db:
        file = await db.get(File, file_id)
        if file is None:
            return
        links = (await db.execute(select(ChatFile).where(ChatFile.file_id == file_id))).scalars().all()
        if scope == "orphan" and links:
            raise RuntimeError("Orphan gained a chat link")
        if scope == "dangling":
            if len(links) != 1 or await db.get(Chat, links[0].chat_id) is not None:
                raise RuntimeError("Dangling link scope changed")
            await db.delete(links[0])
        await db.delete(file)
        await db.commit()


async def _mark_chat_pending(file_id: str) -> None:
    async with get_async_db_context() as db:
        file = await db.get(File, file_id)
        if file is None:
            raise RuntimeError("Video vanished before conversion")
        file.data = {**(file.data or {}), "legacy_media_backfill": "pending"}
        await db.commit()


async def _finish_chat(file_id: str, scope: dict, *, success: bool) -> None:
    async with get_async_db_context() as db:
        file = await db.get(File, file_id)
        chat = await db.get(Chat, scope["chat_id"])
        message = await db.get(ChatMessage, f'{scope["chat_id"]}-{scope["message_id"]}')
        link = await db.get(ChatFile, scope["link_id"])
        if not all((file, chat, message, link)) or link.file_id != file_id:
            raise RuntimeError("Native attachment scope changed during migration")
        if chat.user_id != file.user_id or link.user_id != file.user_id:
            raise RuntimeError("Native attachment ownership changed")
        history = copy.deepcopy(chat.chat or {})
        stored = (history.get("history") or {}).get("messages", {}).get(scope["message_id"])
        if not isinstance(stored, dict):
            raise RuntimeError("History message vanished during migration")
        replacement = _audio_descriptor(file) if success else None
        stored["files"] = _replace(stored.get("files"), file_id, replacement)
        message.files = _replace(message.files, file_id, replacement)
        chat.chat = history
        chat.updated_at = int(time.time())
        if success:
            file.data = {**(file.data or {}), "legacy_media_backfill": "completed"}
        else:
            await db.delete(link)
            await db.delete(file)
        await db.commit()


async def _migrate(file_id: str) -> dict:
    scope, relation = await _scope(file_id)
    if scope == "gone":
        return {"file_id": file_id, "result": "already_gone"}
    if scope in ("orphan", "dangling"):
        await _delete_orphan(file_id, scope)
        return {"file_id": file_id, "result": f"deleted_{scope}"}
    assert relation is not None
    await _mark_chat_pending(file_id)
    while True:
        async with get_async_db_context() as db:
            file = await db.get(File, file_id)
            marker = (file.data or {}).get("stage2_video_intake") or {}
            mime = (file.meta or {}).get("content_type") or ""
        if marker.get("state") == "completed" and mime.startswith("audio/"):
            await _finish_chat(file_id, relation, success=True)
            return {"file_id": file_id, "result": "audio_attached"}
        if marker.get("state") == "failed":
            await _finish_chat(file_id, relation, success=False)
            return {"file_id": file_id, "result": "failed_video_removed"}
        due = marker.get("next_due")
        if due and float(due) > time.time():
            await asyncio.sleep(min(float(due) - time.time(), 60))
        else:
            await prepare_uploaded_video(file_id)


async def main() -> None:
    async with get_async_db_context() as db:
        rows = (await db.execute(select(File.id, File.meta, File.data))).all()
    ids = [id for id, meta, data in rows if
           str((meta or {}).get("content_type") or "").startswith("video/") or
           (data or {}).get("legacy_media_backfill") == "pending"]
    print(json.dumps({"legacy_video_count": len(ids)}), flush=True)
    tasks = [asyncio.create_task(_migrate(file_id)) for file_id in ids]
    for task in asyncio.as_completed(tasks):
        result = await task
        print(json.dumps(result), flush=True)
    async with get_async_db_context() as db:
        paths = (await db.execute(select(File.path).where(File.path.is_not(None)))).scalars().all()
    referenced = {Path(path).name for path in paths}
    upload_dir = Path("/app/backend/data/uploads")
    orphan_count = 0
    orphan_bytes = 0
    for path in upload_dir.iterdir():
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS and path.name not in referenced:
            size = path.stat().st_size
            path.unlink()
            orphan_count += 1
            orphan_bytes += size
    print(json.dumps({"unreferenced_video_blobs_deleted": orphan_count, "bytes": orphan_bytes}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
