from __future__ import annotations

import pytest

from openwebui_filters.stage2_audio_context_filter import Filter


def _audio_attachment(file_id: str = "audio-1", filename: str = "call.wav") -> dict:
    return {
        "type": "file",
        "file": {
            "id": file_id,
            "filename": filename,
            "meta": {"name": filename, "content_type": "audio/wav", "size": 4},
        },
        "id": file_id,
        "name": filename,
        "content_type": "audio/wav",
        "size": 4,
    }


def _video_attachment(file_id: str = "video-1", filename: str = "call.mp4") -> dict:
    attachment = _audio_attachment(file_id, filename)
    attachment["content_type"] = "video/mp4"
    attachment["file"]["meta"]["content_type"] = "video/mp4"
    return attachment


@pytest.mark.asyncio
async def test_video_is_prepared_stored_as_native_audio_and_only_then_committed(monkeypatch):
    filter_ = Filter()
    filter_.valves.internal_api_key = "test-token"
    video = _video_attachment()
    body = {"messages": [{"role": "user", "content": ""}], "files": [video]}
    metadata = {"chat_id": "chat-1", "message_id": "message-1", "files": [video]}
    persisted, committed = [], []

    monkeypatch.setattr(filter_, "_read_native_upload", lambda *_: _async_value(b"video-bytes"))
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_was_transcribed", lambda *_: _async_value(False))
    monkeypatch.setattr(filter_, "_mark_transcribed", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_prepare_video", lambda **_: _async_value({"audio_bytes": b"mp3", "filename": "call.mp3", "mime_type": "audio/mpeg", "size_bytes": 3}))

    async def store(**kwargs):
        persisted.append(kwargs)
        return {"file_id": "audio-derived", "filename": "call.mp3", "mime_type": "audio/mpeg", "size_bytes": 3}

    async def sidecar(**kwargs):
        assert kwargs["audio_bytes"] == b"mp3"
        assert kwargs["filename"] == "call.mp3"
        return {"result": {"text": "transcript"}}

    async def commit(lifecycle):
        committed.append(lifecycle)

    monkeypatch.setattr(filter_, "_persist_prepared_audio", store)
    monkeypatch.setattr(filter_, "_call_sidecar", sidecar)
    monkeypatch.setattr(filter_, "_commit_video_lifecycle", commit)

    await filter_.inlet(body, __user__={"id": "user-1"}, __metadata__=metadata)
    assert persisted[0]["source_file_id"] == "video-1"
    assert metadata["_stage2_video_lifecycle"]["audio_file_id"] == "audio-derived"
    assert not committed
    body["messages"].append({"role": "assistant", "content": "summary"})
    await filter_.outlet(body, __metadata__=metadata)
    assert committed[0]["source_file_id"] == "video-1"
    assert committed[0]["audio_file_id"] == "audio-derived"


@pytest.mark.asyncio
async def test_inlet_transcribes_audio_injects_context_and_removes_only_audio_from_outbound_files(monkeypatch):
    audio = _audio_attachment()
    document = {"type": "file", "file": {"id": "pdf-1", "filename": "notes.pdf"}, "name": "notes.pdf", "content_type": "application/pdf"}
    body = {"messages": [{"role": "user", "content": "Что это за разговор?"}], "files": [audio, document]}
    metadata = {"chat_id": "chat-1", "message_id": "message-1", "files": [audio, document]}
    filter_ = Filter()
    filter_.valves.internal_api_key = "test-token"
    observed = {}
    statuses = []

    async def read_upload(file_id, user_id):
        assert (file_id, user_id) == ("audio-1", "user-1")
        return b"RIFF"

    async def call_sidecar(**kwargs):
        observed.update(kwargs)
        return {"result": {"text": "Клиент просит перенести встречу."}}

    async def emitter(event):
        statuses.append(event)

    monkeypatch.setattr(filter_, "_read_native_upload", read_upload)
    monkeypatch.setattr(filter_, "_call_sidecar", call_sidecar)
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_was_transcribed", lambda *_: _async_value(False))
    monkeypatch.setattr(filter_, "_mark_transcribed", lambda *_: _async_value(None))

    result = await filter_.inlet(body, __user__={"id": "user-1", "role": "user"}, __metadata__=metadata, __event_emitter__=emitter)

    assert result is body
    assert body["files"] == [document]
    assert metadata["files"] == [document]
    assert "Клиент просит перенести встречу." in body["messages"][-1]["content"]
    assert "Сформируй только краткое содержание транскрипции одним предложением." in body["messages"][-1]["content"]
    assert "предложи 2–3 уместных следующих шага" not in body["messages"][-1]["content"]
    assert observed["envelope"]["source_context"] == "openwebui"
    assert observed["audio_bytes"] == b"RIFF"
    assert statuses[-1]["data"]["done"] is True


@pytest.mark.asyncio
async def test_inlet_leaves_non_audio_attachments_for_native_file_processing(monkeypatch):
    filter_ = Filter()
    body = {"messages": [{"role": "user", "content": "Посмотри документ"}], "files": [{"type": "file", "file": {"id": "pdf-1", "filename": "notes.pdf"}, "name": "notes.pdf", "content_type": "application/pdf"}]}

    async def forbidden_sidecar(**kwargs):
        raise AssertionError("Non-audio must not invoke STT")

    monkeypatch.setattr(filter_, "_call_sidecar", forbidden_sidecar)
    result = await filter_.inlet(body, __metadata__={"files": body["files"]})

    assert result == body
    assert body["messages"][-1]["content"] == "Посмотри документ"


@pytest.mark.asyncio
async def test_inlet_removes_audio_from_outbound_files_when_sidecar_is_not_configured():
    audio = _audio_attachment()
    document = {"type": "file", "file": {"id": "pdf-1", "filename": "notes.pdf"}, "name": "notes.pdf", "content_type": "application/pdf"}
    body = {"messages": [{"role": "user", "content": "Расшифруй"}], "files": [audio, document]}
    metadata = {"files": [audio, document]}

    filter_ = Filter()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_was_transcribed", lambda *_: _async_value(False))

    await filter_.inlet(body, __user__={"id": "user-1"}, __metadata__=metadata)
    monkeypatch.undo()

    assert body["files"] == [document]
    assert metadata["files"] == [document]
    assert "Транскрибация сейчас не настроена" in body["messages"][-1]["content"]


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_inlet_does_not_retranscribe_files_from_an_earlier_message(monkeypatch):
    filter_ = Filter()
    body = {"messages": [{"role": "user", "content": "Продолжи анализ"}], "files": [_audio_attachment()]}

    async def forbidden_sidecar(**kwargs):
        raise AssertionError("Earlier-message audio must not be retranscribed")

    monkeypatch.setattr(filter_, "_call_sidecar", forbidden_sidecar)
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_was_transcribed", lambda *_: _async_value(True))

    await filter_.inlet(body, __user__={"id": "user-1"}, __metadata__={"chat_id": "chat-1", "message_id": "follow-up"})

    assert body["messages"][-1]["content"] == "Продолжи анализ"


@pytest.mark.asyncio
async def test_inlet_reuses_cached_transcript_without_sidecar_call(monkeypatch):
    filter_ = Filter()
    body = {"messages": [{"role": "user", "content": "Выдели ключевые фразы"}], "files": [_audio_attachment()]}
    metadata = {"files": body["files"]}

    async def forbidden_sidecar(**kwargs):
        raise AssertionError("Cached transcript must not invoke STT")

    monkeypatch.setattr(filter_, "_call_sidecar", forbidden_sidecar)
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value("Тестовая фраза."))
    monkeypatch.setattr(filter_, "_cached_display", lambda *_: _async_value("Тестовая фраза."))

    await filter_.inlet(body, __user__={"id": "user-1"}, __metadata__=metadata)

    assert body["files"] == []
    assert metadata["files"] == []
    assert "Тестовая фраза." in body["messages"][-1]["content"]
    assert metadata["_stage2_audio_transcript"] == "Тестовая фраза."

    body["messages"].append({"role": "assistant", "content": "Краткий ответ."})
    await filter_.outlet(body, __metadata__=metadata)

    assert "<!-- stage2_audio_transcript -->" not in body["messages"][-1]["content"]
    assert body["messages"][-1]["content"].endswith("Тестовая фраза.")


@pytest.mark.asyncio
async def test_inlet_uses_latest_audio_from_follow_up_metadata(monkeypatch):
    filter_ = Filter()
    filter_.valves.internal_api_key = "test-token"
    earlier_audio = _audio_attachment("audio-earlier", "earlier.wav")
    current_audio = _audio_attachment("audio-current", "current.wav")
    body = {
        "messages": [
            {"role": "user", "content": "Первое аудио"},
            {"role": "assistant", "content": "Первый ответ"},
            {"role": "user", "content": "Второе аудио"},
        ],
        "files": [],
    }
    metadata = {"files": [earlier_audio, current_audio]}

    async def read_upload(file_id, _user_id):
        assert file_id == "audio-current"
        return b"RIFF"

    async def call_sidecar(**kwargs):
        assert kwargs["filename"] == "current.wav"
        return {"result": {"text": "Текст второго аудио."}}

    monkeypatch.setattr(filter_, "_read_native_upload", read_upload)
    monkeypatch.setattr(filter_, "_call_sidecar", call_sidecar)
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_was_transcribed", lambda *_: _async_value(False))
    monkeypatch.setattr(filter_, "_mark_transcribed", lambda *_: _async_value(None))

    await filter_.inlet(body, __user__={"id": "user-1"}, __metadata__=metadata)

    assert [item["id"] for item in metadata["files"]] == ["audio-earlier"]
    assert "Текст второго аудио." in body["messages"][-1]["content"]
    assert body["messages"][0]["content"] == "Первое аудио"


@pytest.mark.asyncio
async def test_outlet_places_summary_before_exact_transcript_once():
    filter_ = Filter()
    body = {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "Это телефонограмма."}]}
    metadata = {"_stage2_audio_transcript": "Перезвоните мне после обеда."}

    result = await filter_.outlet(body, __metadata__=metadata)

    assert result is body
    assert body["messages"][-1]["content"].startswith("## Краткое содержание\n\nЭто телефонограмма.")
    assert "## Полная транскрипция\n\nПерезвоните мне после обеда." in body["messages"][-1]["content"]
    assert "<!-- stage2_audio_transcript -->" not in body["messages"][-1]["content"]
    assert "_stage2_audio_transcript" not in metadata


def test_transcript_display_groups_actual_speaker_segments_and_keeps_known_timestamps():
    filter_ = Filter()
    response = {
        "result": {
            "text": "ignored plain text",
            "segments": [
                {"speaker": "speaker_0", "text": "Добрый день.", "start": 1, "end": 3},
                {"speaker": "speaker_0", "text": "У меня вопрос.", "start": 3, "end": 5},
                {"speaker": "speaker_1", "text": "Слушаю вас.", "start": 5, "end": 6},
            ],
        }
    }

    display = filter_._format_transcript(response)

    assert "[00:01-00:05] Спикер 1:\nДобрый день. У меня вопрос." in display
    assert "[00:05-00:06] Спикер 2:\nСлушаю вас." in display
    assert "ignored plain text" not in display


def test_transcript_display_uses_segment_breaks_without_inventing_speakers():
    filter_ = Filter()
    response = {
        "result": {
            "text": "Первый фрагмент. Второй фрагмент.",
            "segments": [
                {"text": "Первый фрагмент."},
                {"text": "Второй фрагмент."},
            ],
        }
    }

    display = filter_._format_transcript(response)

    assert display == "Первый фрагмент.\n\nВторой фрагмент."
    assert "Спикер" not in display
