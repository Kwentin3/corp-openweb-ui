"""Prepare uploaded video before it can be attached to an ordinary chat.

The native File retains its ID. Its path and metadata become audio only after
FFmpeg returns a complete file. Retry state lives in File.data so a restart
does not leave a pending video behind.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path

import httpx
from sqlalchemy import select

from open_webui.internal.db import get_async_db_context
from open_webui.models.files import File
from open_webui.storage.provider import Storage

log = logging.getLogger(__name__)
RETRY_DELAY_SECONDS = 420
CHUNK_SIZE = 1024 * 1024
_lock = asyncio.Lock()
_sweeper: asyncio.Task | None = None


def _marker(row: File) -> dict:
    return dict((row.data or {}).get("stage2_video_intake") or {})


async def _state(file_id: str, **changes) -> None:
    async with get_async_db_context() as db:
        row = await db.get(File, file_id)
        if row is None:
            return
        marker = _marker(row)
        marker.update(changes)
        row.data = {**(row.data or {}), "status": "processing", "stage2_video_intake": marker}
        row.updated_at = int(time.time())
        await db.commit()


async def prepare_uploaded_video(file_id: str) -> None:
    """Run attempts 1 and 2 now; the third is resumed by the native sweeper."""
    async with _lock:
        await _process(file_id)


async def _process(file_id: str) -> None:
    async with get_async_db_context() as db:
        row = await db.get(File, file_id)
        if row is None:
            return
        marker = _marker(row)
        if not marker:
            marker = {"state": "pending", "attempt": 0, "source_path": row.path}
            row.data = {**(row.data or {}), "status": "processing", "stage2_video_intake": marker}
            await db.commit()
    if marker.get("state") == "cleanup_pending":
        await _cleanup_source(file_id, marker)
        return
    if marker.get("state") == "failed_cleanup_pending":
        await _finish_failure(file_id, marker)
        return
    if marker.get("state") in ("completed", "failed"):
        return
    due = marker.get("next_due")
    if due and float(due) > time.time():
        return
    attempts = int(marker.get("attempt") or 0)
    if attempts >= 2 and not due:
        # An interrupted second attempt still gets the promised delay.
        last_started = float(marker.get("last_started") or time.time())
        if last_started + RETRY_DELAY_SECONDS > time.time():
            await _state(file_id, next_due=last_started + RETRY_DELAY_SECONDS)
            return

    while attempts < 3:
        attempts += 1
        await _state(file_id, state="converting", attempt=attempts, last_started=time.time(), next_due=None)
        try:
            await _convert(file_id)
            return
        except Exception as exc:
            async with get_async_db_context() as db:
                row = await db.get(File, file_id)
                current = _marker(row) if row else {}
            if current.get("state") == "cleanup_pending":
                log.warning("Source deletion pending for %s: %s", file_id, exc)
                return
            log.warning("Video conversion attempt %s failed for %s: %s", attempts, file_id, exc)
            if attempts == 2:
                await _state(file_id, state="retry_wait", attempt=attempts, next_due=time.time() + RETRY_DELAY_SECONDS, error=str(exc)[:300])
                return
            if attempts == 3:
                await _state(file_id, state="failed_cleanup_pending", attempt=attempts, error=str(exc)[:300])
                await _finish_failure(file_id, {"error": str(exc)[:300]})
                return


async def _convert(file_id: str) -> None:
    async with get_async_db_context() as db:
        row = await db.get(File, file_id)
        if row is None or not row.path:
            raise RuntimeError("Source video is unavailable")
        source_path = row.path
        name = row.filename
        user_id = row.user_id
        mime = (row.meta or {}).get("content_type") or "video/mp4"
        size = (row.meta or {}).get("size")
    local_path = Path(await asyncio.to_thread(Storage.get_file, source_path))
    if not local_path.is_file():
        raise RuntimeError("Source video is unavailable")
    token = os.environ.get("STAGE2_STT_INTERNAL_API_KEY", "")
    if not token:
        raise RuntimeError("Media preparation service is not configured")
    envelope = {"source_context": "openwebui", "user_id": user_id, "file": {"file_id": file_id, "filename": name, "mime_type": mime, "size_bytes": size}, "selected_output_profile": "mp3_high_compat"}
    with tempfile.TemporaryDirectory(prefix="stage2-upload-audio-") as work:
        audio_path = Path(work) / "audio.mp3"
        async with httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=15.0)) as client:
            with local_path.open("rb") as source:
                async with client.stream(
                    "POST", "http://stage2-stt:8080/stage2-api/media/prepare",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"envelope": json.dumps(envelope)},
                    files={"source_media": (name, source, mime)},
                ) as response:
                    if response.is_error:
                        await response.aread()
                        raise RuntimeError(f"Media preparation returned HTTP {response.status_code}")
                    if not response.headers.get("content-type", "").startswith("audio/"):
                        raise RuntimeError("Media preparation returned no audio")
                    with audio_path.open("wb") as output:
                        async for chunk in response.aiter_bytes(CHUNK_SIZE):
                            output.write(chunk)
        if not audio_path.stat().st_size:
            raise RuntimeError("Media preparation returned empty audio")
        audio_name = f"{Path(name).stem}.mp3"
        storage_name = f"{file_id}_{audio_name}"
        def store() -> tuple[int, str, str]:
            with audio_path.open("rb") as audio:
                return Storage.upload_file_streaming(audio, storage_name, {"OpenWebUI-User-Id": user_id, "OpenWebUI-File-Id": file_id})
        audio_size, audio_hash, audio_storage_path = await asyncio.to_thread(store)
        try:
            async with get_async_db_context() as db:
                row = await db.get(File, file_id)
                if row is None or row.path != source_path:
                    raise RuntimeError("Source video changed during conversion")
                marker = _marker(row)
                marker.update({"state": "cleanup_pending", "source_path": source_path, "audio_path": audio_storage_path})
                row.path = audio_storage_path
                row.filename = audio_name
                row.hash = audio_hash
                row.meta = {**(row.meta or {}), "name": audio_name, "content_type": "audio/mpeg", "size": audio_size, "file_hash": audio_hash}
                row.data = {**(row.data or {}), "status": "processing", "stage2_video_intake": marker}
                row.updated_at = int(time.time())
                await db.commit()
        except Exception:
            async with get_async_db_context() as db:
                row = await db.get(File, file_id)
                committed = row is not None and row.path == audio_storage_path
            if not committed:
                await asyncio.to_thread(Storage.delete_file, audio_storage_path)
            raise
    await _cleanup_source(file_id, {"source_path": source_path})


async def _cleanup_source(file_id: str, marker: dict) -> None:
    source_path = marker.get("source_path")
    if source_path:
        await asyncio.to_thread(Storage.delete_file, source_path)
        if Path(Storage.get_file(source_path)).is_file():
            raise RuntimeError("Source video survived deletion")
    async with get_async_db_context() as db:
        row = await db.get(File, file_id)
        if row is None:
            return
        state = _marker(row)
        state.update({"state": "completed", "source_path": None})
        row.data = {**(row.data or {}), "status": "completed", "stage2_video_intake": state}
        row.updated_at = int(time.time())
        await db.commit()


async def _finish_failure(file_id: str, marker: dict) -> None:
    async with get_async_db_context() as db:
        row = await db.get(File, file_id)
        if row is None:
            return
        source_path = _marker(row).get("source_path") or row.path
    if source_path:
        await asyncio.to_thread(Storage.delete_file, source_path)
        if Path(Storage.get_file(source_path)).is_file():
            raise RuntimeError("Failed video survived deletion")
    async with get_async_db_context() as db:
        row = await db.get(File, file_id)
        if row is None:
            return
        state = _marker(row)
        state.update({"state": "failed", "source_path": None})
        row.path = None
        row.data = {**(row.data or {}), "status": "failed", "error": "Не удалось извлечь аудио из видео после трёх попыток; исходный файл удалён.", "stage2_video_intake": state}
        row.updated_at = int(time.time())
        await db.commit()


async def _sweep() -> None:
    while True:
        try:
            async with get_async_db_context() as db:
                rows = (await db.execute(select(File.id, File.data).where(File.data.is_not(None)))).all()
            for file_id, data in rows:
                marker = (data or {}).get("stage2_video_intake") if isinstance(data, dict) else None
                if not isinstance(marker, dict) or marker.get("state") in ("completed", "failed"):
                    continue
                if marker.get("next_due") and float(marker["next_due"]) > time.time():
                    continue
                async with _lock:
                    try:
                        await _process(file_id)
                    except Exception:
                        log.exception("Video intake reconciliation failed for %s", file_id)
        except Exception:
            log.exception("Video intake reconciliation failed")
        await asyncio.sleep(60)


def start_video_intake_reconciler() -> None:
    global _sweeper
    if _sweeper is None or _sweeper.done():
        _sweeper = asyncio.create_task(_sweep())
