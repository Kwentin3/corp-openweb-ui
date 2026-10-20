"""Offline intake integration in the exact deployed OpenWebUI image.

Run a disposable container with no network, no production mounts or env, and
mount this script plus the candidate intake source read-only. Example:

docker run --rm --network none --read-only --memory 1g \
  --tmpfs /tmp:rw,nosuid,size=128m -e PYTHONPATH=/app/backend --entrypoint python \
  -v /absolute/verify_native_intake_runtime.py:/verify.py:ro \
  -v /absolute/stage2_media_intake.py:/intake.py:ro \
  <verified-current-webui-image-id> /verify.py --intake /intake.py

Native File models, SQLite sessions and LocalStorageProvider are real. Only the
HTTP preparation boundary is replaced with deterministic synthetic bytes; this
does not qualify FFmpeg, recognition quality, the browser or external providers.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid
from unittest.mock import patch


async def verify(intake_path: Path, root: Path) -> dict:
    assert not any(name.startswith("open_webui") for name in sys.modules)
    # Set these before importing native modules; never connect to an inherited DB.
    os.environ.update({
        "DATA_DIR": str(root / "data"),
        "DATABASE_URL": f"sqlite:///{root / 'intake.sqlite3'}",
        "UPLOAD_DIR": str(root / "uploads"),
        "STATIC_DIR": str(root / "static"),
        "CACHE_DIR": str(root / "cache"),
        "ENABLE_DB_MIGRATIONS": "false",
        "ENABLE_PERSISTENT_CONFIG": "false",
        "OFFLINE_MODE": "true",
        "WEBUI_SECRET_KEY": "offline-fixture-only-" * 4,
        "STORAGE_PROVIDER": "local",
        "DATABASE_POOL_SIZE": "2",
        "STAGE2_STT_INTERNAL_API_KEY": "offline-fixture-token",
        "STAGE2_STT_BASE_URL": "http://offline-preparation.invalid",
    })
    for name in ("data", "uploads", "static", "cache"):
        (root / name).mkdir()

    from open_webui.internal.db import async_engine, engine
    from open_webui.models.files import File, FileForm, Files
    from open_webui.storage.provider import LocalStorageProvider, Storage
    import httpx

    # The only schema used is the actual native File table. No production copy.
    File.__table__.create(bind=engine)
    assert isinstance(Storage, LocalStorageProvider)
    spec = importlib.util.spec_from_file_location("candidate_native_intake", intake_path)
    assert spec and spec.loader
    intake = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(intake)
    event = intake.Event()
    original = b"ID3synthetic-source-not-an-audio-quality-fixture" * 20
    prepared = b"ID3synthetic-prepared-not-an-audio-quality-fixture" * 3
    owner = "offline-owner"
    requests = []
    fail = False

    async def transport(request):
        assert request.method == "POST"
        assert str(request.url) == "http://offline-preparation.invalid/stage2-api/media/prepare"
        assert request.headers["authorization"] == "Bearer offline-fixture-token"
        body = await request.aread()
        assert original in body
        requests.append(request.url.path)
        if fail:
            return httpx.Response(422, json={"detail": {"code": "media_preparation_failed"}})
        return httpx.Response(200, content=prepared, headers={"content-type": "audio/mpeg"})

    native_client = httpx.AsyncClient

    def offline_client(*args, **kwargs):
        return native_client(*args, **kwargs, transport=httpx.MockTransport(transport))

    async def upload(name: str, data: dict | None = None):
        file_id = str(uuid.uuid4())
        size, digest, path = Storage.upload_file_streaming(
            io.BytesIO(original), f"{file_id}_{name}", {},
        )
        row = await Files.insert_new_file(owner, FileForm(
            id=file_id, filename=name, path=path, hash=digest,
            meta={"name": name, "content_type": "audio/mpeg", "size": size, "file_hash": digest},
            data=data or {"status": "pending"},
        ))
        assert row is not None
        return row

    passed = []
    try:
        with patch.object(intake.httpx, "AsyncClient", offline_client):
            for name in ("Запись.mp3", "prepared.mp3"):
                row = await upload(name)
                source = Path(row.path)
                assert await event.accept_upload(row.id, owner) is True
                pending = await Files.get_file_by_id(row.id)
                assert pending.data["status"] == "processing"
                assert source.read_bytes() == original
                await event.event({"subject": {"id": row.id}}, __event_name__="file.uploaded")
                complete = await Files.get_file_by_id(row.id)
                assert complete.id == row.id and complete.user_id == owner
                assert complete.filename == name
                assert complete.path != row.path and not source.exists()
                assert Path(complete.path).read_bytes() == prepared
                digest = hashlib.sha256(prepared).hexdigest()
                assert complete.hash == complete.meta["file_hash"] == digest
                assert complete.meta["content_type"] == "audio/mpeg"
                assert complete.meta["size"] == len(prepared)
                assert complete.data["status"] == "completed"
                assert complete.data["stage2_video_intake"]["state"] == "completed"
                before = complete.model_dump()
                count = len(requests)
                assert await event.accept_upload(row.id, owner) is True
                await event.event({"subject": {"id": row.id}}, __event_name__="file.uploaded")
                assert len(requests) == count
                assert (await Files.get_file_by_id(row.id)).model_dump() == before
            passed.append("MP3 same-ID replacement, collision-safe distinct path, source cleanup, native JSON/hash/meta persistence and repeated event no-op")

            row = await upload("failed.mp3")
            fail = True
            assert await event.accept_upload(row.id, owner) is True
            count = len(requests)
            await intake.prepare_uploaded_video(row.id)
            waiting = await Files.get_file_by_id(row.id)
            assert waiting.data["stage2_video_intake"]["state"] == "retry_wait"
            assert waiting.data["stage2_video_intake"]["attempt"] == 2
            assert len(requests) == count + 2
            # Advance only this durable due marker, without sleeping seven minutes.
            await intake._state(row.id, next_due=time.time() - 1)
            await intake.prepare_uploaded_video(row.id)
            failed = await Files.get_file_by_id(row.id)
            assert len(requests) == count + 3
            assert failed.data["status"] == "failed"
            assert failed.data["stage2_video_intake"]["state"] == "failed"
            assert failed.path == row.path and failed.hash == row.hash
            assert failed.meta == row.meta and Path(failed.path).read_bytes() == original
            assert "сохранён" in failed.data["error"]
            passed.append("three failed preparation attempts preserve original native path, bytes, hash and metadata")

            row = await upload("cached.mp3", {"status": "completed", "stage2_audio_context_filter": {
                "state": "transcribed-v1", "transcript": "offline cached transcript",
            }})
            before = row.model_dump()
            count = len(requests)
            assert await event.accept_upload(row.id, owner) is True
            await event.event({"subject": {"id": row.id}}, __event_name__="file.uploaded")
            assert (await Files.get_file_by_id(row.id)).model_dump() == before
            assert len(requests) == count
            passed.append("existing transcript cache leaves File and source unchanged without preparation")

            subject = {"subject": {"id": "candidate", "type": "function"}}
            await event.event(subject, __event_name__="function.enable_started", __id__="candidate")
            assert intake._sweeper is not None
            await event.event(subject, __event_name__="function.disable_started", __id__="candidate")
            assert intake._sweeper is None
            passed.append("native enable/disable lifecycle starts and cancels candidate reconciler")
        return {
            "passed": passed,
            "intake_sha256": hashlib.sha256(intake_path.read_bytes()).hexdigest(),
            "preparation_http_fixture_calls": len(requests),
            "scope": "actual candidate Function, native File SQLite and LocalStorage; synthetic HTTP preparation boundary only; no provider/browser/FFmpeg acceptance",
        }
    finally:
        await async_engine.dispose()
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake", type=Path, required=True)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="native-intake-offline-") as directory:
        receipt = asyncio.run(verify(arguments.intake.resolve(strict=True), Path(directory)))
    print(json.dumps(receipt, ensure_ascii=False))
