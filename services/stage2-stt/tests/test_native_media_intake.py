"""Exercise the Event function with native DB/storage interfaces and real files.

OpenWebUI is hosted separately from the STT package. Its database boundary is
represented by committed row copies; HTTP uses httpx's transport boundary.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import pytest


@pytest.fixture
def intake(monkeypatch, tmp_path):
    rows = {}

    class Column:
        def __eq__(self, other):
            return other

    class NativeFile(SimpleNamespace):
        id = Column()
        path = Column()

    class Query:
        def where(self, path):
            self.path = path
            return self

    class Session:
        def __init__(self):
            self.loaded = {}

        async def get(self, model, file_id):
            if file_id not in rows:
                return None
            return self.loaded.setdefault(file_id, copy.deepcopy(rows[file_id]))

        async def commit(self):
            if getattr(environment, "fail_path_commit", False) and any(
                row.path != rows[file_id].path for file_id, row in self.loaded.items()
            ):
                raise RuntimeError("Native path commit failed")
            rows.update(copy.deepcopy(self.loaded))

        async def execute(self, query):
            claimed = [row.id for row in rows.values() if row.path == query.path]
            return SimpleNamespace(first=lambda: (claimed[0],) if claimed else None)

    @asynccontextmanager
    async def database():
        yield Session()

    class LocalStorage:
        @staticmethod
        def get_file(path):
            return path

        @staticmethod
        def upload_file_streaming(source, name, tags):
            target = tmp_path / name
            digest = hashlib.sha256()
            size = 0
            with target.open("xb") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            return size, digest.hexdigest(), str(target)

        @staticmethod
        def delete_file(path):
            if environment.fail_delete and path == environment.source:
                raise OSError("Source deletion temporarily failed")
            if path == environment.source:
                assert rows["audio-1"].path != path, "Original deleted before native path commit"
            Path(path).unlink(missing_ok=True)

    async def owned_file(file_id, user_id):
        row = rows.get(file_id)
        return copy.deepcopy(row) if row and row.user_id == user_id else None

    async def file_by_id(file_id):
        return copy.deepcopy(rows.get(file_id))

    def module(name, **values):
        stub = ModuleType(name)
        stub.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, stub)

    module("sqlalchemy", select=lambda *columns: Query())
    module("open_webui.internal.db", get_async_db_context=database)
    module("open_webui.models.files", File=NativeFile, Files=SimpleNamespace(
        get_file_by_id_and_user_id=owned_file, get_file_by_id=file_by_id,
    ))
    module("open_webui.storage.provider", Storage=LocalStorage(), LocalStorageProvider=LocalStorage)
    module("open_webui.routers.files", _is_text_file=lambda path: False)
    source = Path(__file__).resolve().parents[3] / "deploy/openwebui-functions/stage2_media_intake.py"
    spec = importlib.util.spec_from_file_location("native_media_intake_under_test", source)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    monkeypatch.setenv("STAGE2_STT_INTERNAL_API_KEY", "internal-test-key")
    monkeypatch.setenv("STAGE2_STT_BASE_URL", "http://preparation.test")
    environment = SimpleNamespace(module=loaded, rows=rows, fail_delete=False, source=None)

    def upload(name="call.mp3", mime="audio/mpeg", data=None, metadata=None):
        path = tmp_path / f"audio-1_{name}"
        path.write_bytes(b"original audio bytes")
        environment.source = str(path)
        rows["audio-1"] = NativeFile(
            id="audio-1", user_id="owner", filename=name, path=str(path),
            data=data or {}, hash="original-hash", updated_at=0,
            meta={"content_type": mime, "size": path.stat().st_size, **(metadata or {})},
        )
        return path

    requests = []
    async def prepare(request):
        requests.append(request)
        body = await request.aread()
        assert b"original audio bytes" in body
        assert b'"selected_output_profile": "mp3_high_compat"' in body
        assert request.headers["authorization"] == "Bearer internal-test-key"
        return httpx.Response(200, content=b"prepared MP3 bytes", headers={"content-type": "audio/mpeg"})

    client = httpx.AsyncClient
    monkeypatch.setattr(loaded.httpx, "AsyncClient", lambda **kwargs: client(
        transport=httpx.MockTransport(prepare), **kwargs,
    ))
    environment.upload = upload
    environment.requests = requests
    return environment


@pytest.mark.asyncio
@pytest.mark.parametrize("name,mime", [
    ("call.mp3", "audio/mpeg"), ("prepared.mp3", "audio/mpeg"),
    ("call.mp3", "application/octet-stream"), ("call.wav", "audio/wav"),
    ("call.mp4", "video/mp4"),
])
async def test_upload_prepares_same_native_file_and_repeated_hook_is_idempotent(intake, name, mime):
    original = intake.upload(name, mime, metadata={
        "data": {"stage2_video_intake": {"state": "completed", "attempt": 1}},
    })
    event = intake.module.Event()
    assert await event.accept_upload("audio-1", "owner") is True
    assert intake.rows["audio-1"].data["status"] == "processing"
    await event.event({"subject": {"id": "audio-1"}}, __event_name__="file.uploaded")
    row = intake.rows["audio-1"]
    assert row.id == "audio-1"
    assert row.filename == f"{Path(name).stem}.mp3"
    assert row.path != str(original)
    assert not original.exists()
    assert Path(row.path).read_bytes() == b"prepared MP3 bytes"
    assert row.hash == row.meta["file_hash"] == hashlib.sha256(b"prepared MP3 bytes").hexdigest()
    assert row.meta["size"] == len(b"prepared MP3 bytes")
    assert row.data["status"] == row.data["stage2_video_intake"]["state"] == "completed"
    assert row.data["stage2_video_intake"]["attempt"] == 1
    before = copy.deepcopy(row)
    assert await event.accept_upload("audio-1", "owner") is True
    await event.event({"subject": {"id": "audio-1"}}, __event_name__="file.uploaded")
    assert vars(intake.rows["audio-1"]) == vars(before)
    assert len(intake.requests) == 1


@pytest.mark.asyncio
async def test_existing_retry_hook_does_not_reset_attempt_or_due_time(intake):
    marker = {"state": "retry_wait", "attempt": 2, "next_due": 9999999999}
    intake.upload(data={"status": "processing", "stage2_video_intake": marker})
    before = copy.deepcopy(intake.rows["audio-1"])
    assert await intake.module.Event().accept_upload("audio-1", "owner")
    assert vars(intake.rows["audio-1"]) == vars(before)


@pytest.mark.asyncio
async def test_legacy_mp3_bypass_is_prepared_but_cached_transcript_is_preserved(intake):
    intake.upload(data={"status": "completed", "stage2_video_intake": {"state": "completed", "attempt": 0}})
    assert await intake.module.Event().accept_upload("audio-1", "owner")
    assert intake.rows["audio-1"].data["stage2_video_intake"]["state"] == "pending"
    cached = {"state": "transcribed-v1", "transcript": "Saved words."}
    intake.rows["audio-1"].data = {"status": "completed", "stage2_audio_context_filter": cached}
    assert await intake.module.Event().accept_upload("audio-1", "owner")
    assert intake.rows["audio-1"].data == {"status": "completed", "stage2_audio_context_filter": cached}


@pytest.mark.asyncio
async def test_failed_native_commit_preserves_source_and_removes_uncommitted_output(intake):
    source = intake.upload()
    await intake.module.Event().accept_upload("audio-1", "owner")
    intake.fail_path_commit = True
    await intake.module.prepare_uploaded_video("audio-1")
    marker = intake.rows["audio-1"].data["stage2_video_intake"]
    assert marker["state"] == "retry_wait" and marker["attempt"] == 2
    assert source.read_bytes() == b"original audio bytes"
    assert intake.rows["audio-1"].path == str(source)
    assert not (source.parent / "audio-1_prepared.mp3").exists()
    marker["next_due"] = 1
    await intake.module.prepare_uploaded_video("audio-1")
    row = intake.rows["audio-1"]
    assert row.data["stage2_video_intake"]["state"] == row.data["status"] == "failed"
    assert row.data["stage2_video_intake"]["attempt"] == 3
    assert "исходный файл сохранён" in row.data["error"]
    assert row.path == str(source) and source.read_bytes() == b"original audio bytes"


@pytest.mark.asyncio
async def test_source_cleanup_resumes_without_second_conversion(intake):
    source = intake.upload()
    await intake.module.Event().accept_upload("audio-1", "owner")
    intake.fail_delete = True
    await intake.module.prepare_uploaded_video("audio-1")
    row = intake.rows["audio-1"]
    assert row.data["stage2_video_intake"]["state"] == "cleanup_pending"
    assert source.exists() and Path(row.path).read_bytes() == b"prepared MP3 bytes"
    intake.fail_delete = False
    await intake.module.prepare_uploaded_video("audio-1")
    assert not source.exists()
    assert intake.rows["audio-1"].data["status"] == "completed"
    assert len(intake.requests) == 1


@pytest.mark.asyncio
async def test_cleanup_never_deletes_current_native_blob(intake):
    source = intake.upload()
    with pytest.raises(RuntimeError, match="current blob"):
        await intake.module._cleanup_source("audio-1", {"source_path": str(source)})
    assert source.read_bytes() == b"original audio bytes"


@pytest.mark.asyncio
async def test_interrupted_uncommitted_output_is_recovered_before_retry(intake):
    source = intake.upload()
    await intake.module.Event().accept_upload("audio-1", "owner")
    orphan = source.parent / "audio-1_prepared.mp3"
    orphan.write_bytes(b"interrupted output")
    await intake.module.prepare_uploaded_video("audio-1")
    row = intake.rows["audio-1"]
    assert row.data["status"] == "completed"
    assert Path(row.path).read_bytes() == b"prepared MP3 bytes"
    assert not source.exists()


@pytest.mark.asyncio
async def test_output_claimed_by_another_native_file_is_preserved(intake):
    source = intake.upload()
    await intake.module.Event().accept_upload("audio-1", "owner")
    target = source.parent / "audio-1_prepared.mp3"
    target.write_bytes(b"another native file")
    intake.rows["another-file"] = SimpleNamespace(id="another-file", path=str(target))
    await intake.module.prepare_uploaded_video("audio-1")
    assert source.read_bytes() == b"original audio bytes"
    assert target.read_bytes() == b"another native file"
    assert intake.rows["audio-1"].data["stage2_video_intake"]["state"] == "retry_wait"


@pytest.mark.asyncio
async def test_only_owned_chat_media_is_accepted(intake):
    intake.upload()
    with pytest.raises(RuntimeError, match="unavailable"):
        await intake.module.Event().accept_upload("audio-1", "another-user")
    for context in ({"knowledge_id": "collection"}, {"channel_id": "channel"}):
        intake.rows["audio-1"].meta["data"] = context
        assert await intake.module.Event().accept_upload("audio-1", "owner") is False
    intake.rows["audio-1"].meta = {"content_type": "application/pdf"}
    intake.rows["audio-1"].filename = "notes.pdf"
    assert await intake.module.Event().accept_upload("audio-1", "owner") is False
    assert not intake.requests
