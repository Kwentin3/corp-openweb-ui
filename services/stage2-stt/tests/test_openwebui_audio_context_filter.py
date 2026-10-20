from __future__ import annotations

import copy
import sys
from types import ModuleType, SimpleNamespace

import httpx
import pytest

from openwebui_filters.stage2_audio_context_filter import Filter, DEFAULT_INITIAL_RESPONSE_INSTRUCTION


@pytest.mark.asyncio
async def test_follow_up_with_cached_historical_media_does_not_change_messages(monkeypatch):
    audio = _audio_attachment()
    messages = [{"role": "user", "content": "", "files": [audio]},
                {"role": "assistant", "content": "Saved full transcript."},
                {"role": "user", "content": "Create a meeting protocol."}]
    body = {"messages": messages, "files": [audio]}
    metadata = {"files": [audio]}
    before = copy.deepcopy(messages)
    filter_ = Filter()

    async def forbidden(*args, **kwargs):
        raise AssertionError("Historical audio must not enter STT or cache lookup")

    monkeypatch.setattr(filter_, "_cached_transcript", forbidden)
    monkeypatch.setattr(filter_, "_call_sidecar", forbidden)
    await filter_.inlet(body, __metadata__=metadata, __event_emitter__=forbidden)
    await filter_.outlet(body, __metadata__=metadata)
    assert messages == before
    assert body["files"] == metadata["files"] == []
    assert not any(k.startswith("_stage2") for k in metadata)


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", ["", "Create a meeting protocol."])
async def test_current_cached_upload_preserves_explicit_task_and_defaults_only_when_empty(monkeypatch, prompt):
    audio = _audio_attachment()
    body = {"messages": [{"role": "user", "content": prompt, "files": [audio]}], "files": [audio]}
    metadata = {}
    filter_ = Filter()
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value("Source transcript."))
    monkeypatch.setattr(filter_, "_cached_display", lambda *_: _async_value("Source transcript."))
    await filter_.inlet(body, __metadata__=metadata)
    assert body["messages"][-1]["content"].startswith(prompt)
    assert (DEFAULT_INITIAL_RESPONSE_INSTRUCTION in body["messages"][-1]["content"]) == (not prompt)
    body["messages"].append({"role": "assistant", "content": "Requested result."})
    await filter_.outlet(body, __metadata__=metadata)
    assert body["messages"][-1]["content"].startswith("Requested result." if prompt else "## ")
    assert body["messages"][-1]["content"].endswith("Source transcript.")


@pytest.mark.asyncio
async def test_native_current_message_metadata_overrides_aggregate_and_inline_files(monkeypatch):
    module = ModuleType("open_webui.models.chats")
    current = _audio_attachment("current")
    async def read_metadata(chat_id, message_id, field):
        assert (chat_id, message_id, field) == ("chat", "current-user-message", "files")
        return [current]
    module.Chats = SimpleNamespace(get_message_metadata=read_metadata)
    ids = ModuleType("open_webui.utils.chat_id")
    ids.is_saved_chat_id = lambda chat_id: chat_id == "chat"
    monkeypatch.setitem(sys.modules, "open_webui.models.chats", module)
    monkeypatch.setitem(sys.modules, "open_webui.utils.chat_id", ids)
    body = {"messages": [{"role": "user", "content": "", "files": [_audio_attachment("old")]}]}
    assert await Filter()._current_message_files(body, {"chat_id": "chat", "user_message_id": "current-user-message"}) == [current]


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
@pytest.mark.parametrize("mime_type", ["video/mp4", "audio/x-m4a"])
async def test_unprepared_media_fails_without_storage_or_provider_work(monkeypatch, mime_type):
    filter_ = Filter()
    filter_.valves.internal_api_key = "test-token"
    video = _video_attachment()
    video["content_type"] = mime_type
    video["file"]["meta"]["content_type"] = mime_type
    body = {"messages": [{"role": "user", "content": "", "files": [video]}], "files": [video]}
    metadata = {"chat_id": "chat-1", "message_id": "message-1", "files": [video]}
    original_attachment = copy.deepcopy(video)
    statuses = []
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_was_transcribed", lambda *_: _async_value(False))
    async def forbidden(*args, **kwargs):
        raise AssertionError("Unprepared media must not read/replace files or invoke STT")

    async def emit(event):
        statuses.append(event)

    monkeypatch.setattr(filter_, "_native_upload_path", forbidden)
    monkeypatch.setattr(filter_, "_call_sidecar", forbidden)
    monkeypatch.setattr(filter_, "_mark_transcribed", forbidden)

    await filter_.inlet(body, __user__={"id": "user-1"}, __metadata__=metadata, __event_emitter__=emit)
    assert body["files"] == []
    assert metadata["files"] == []
    assert video == original_attachment
    assert "Подготовка медиа не завершена" in body["messages"][-1]["content"]
    assert metadata["_stage2_audio_transcript"] is None
    assert statuses[-1]["data"]["done"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("task", ["title_generation", "tags_generation", "follow_up_generation", "query_generation"])
async def test_auxiliary_tasks_leave_media_and_transcript_metadata_untouched(monkeypatch, task):
    filter_ = Filter()
    body = {"messages": [{"role": "user", "content": ""}], "files": [_video_attachment()]}
    metadata = {"task": task, "files": body["files"], "_stage2_audio_transcript": "saved"}
    before = copy.deepcopy((body, metadata))

    async def forbidden(*args, **kwargs):
        raise AssertionError("Auxiliary task must not read files, emit statuses or invoke STT")

    monkeypatch.setattr(filter_, "_cached_transcript", forbidden)
    monkeypatch.setattr(filter_, "_call_sidecar", forbidden)
    await filter_.inlet(body, __metadata__=metadata, __event_emitter__=forbidden)
    await filter_.outlet(body, __metadata__=metadata)
    assert (body, metadata) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("mime_type", ["audio/mpeg", "audio/wav", "audio/webm; codecs=opus", "audio/ogg"])
async def test_inlet_transcribes_audio_injects_context_and_removes_only_audio_from_outbound_files(monkeypatch, tmp_path, mime_type):
    audio = _audio_attachment()
    audio["content_type"] = mime_type
    audio["file"]["meta"]["content_type"] = mime_type
    document = {"type": "file", "file": {"id": "pdf-1", "filename": "notes.pdf"}, "name": "notes.pdf", "content_type": "application/pdf"}
    body = {"messages": [{"role": "user", "content": "Что это за разговор?", "files": [audio, document]}], "files": [audio, document]}
    metadata = {"chat_id": "chat-1", "message_id": "message-1", "files": [audio, document]}
    filter_ = Filter()
    filter_.valves.internal_api_key = "test-token"
    observed = {}
    statuses = []
    source = tmp_path / "audio.wav"
    source.write_bytes(b"RIFF")

    async def read_upload(file_id, user_id):
        assert (file_id, user_id) == ("audio-1", "user-1")
        return source

    async def call_sidecar(**kwargs):
        observed.update(kwargs)
        return {"result": {"text": "Клиент просит перенести встречу."}}

    async def emitter(event):
        statuses.append(event)

    monkeypatch.setattr(filter_, "_native_upload_path", read_upload)
    monkeypatch.setattr(filter_, "_call_sidecar", call_sidecar)
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_was_transcribed", lambda *_: _async_value(False))
    monkeypatch.setattr(filter_, "_mark_transcribed", lambda *_: _async_value(None))

    result = await filter_.inlet(body, __user__={"id": "user-1", "role": "user"}, __metadata__=metadata, __event_emitter__=emitter)

    assert result is body
    assert body["files"] == [document]
    assert metadata["files"] == [document]
    assert "Клиент просит перенести встречу." in body["messages"][-1]["content"]
    assert "Сформируй только краткое содержание транскрипции одним предложением." not in body["messages"][-1]["content"]
    assert "предложи 2–3 уместных следующих шага" not in body["messages"][-1]["content"]
    assert observed["envelope"]["source_context"] == "openwebui"
    assert observed["audio_path"] == source
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
@pytest.mark.parametrize(
    "status,code,expected",
    [
        (422, "prepared_audio_too_large", "превышает допустимый размер"),
        (422, "provider_direct_upload_limit_exceeded", "превышает допустимый размер"),
        (422, "source_has_no_audio_stream", "Видеофайл не содержит аудиодорожки"),
        (422, "invalid_audio_format", "Проверьте формат и повторите попытку"),
        (401, None, "Проверьте формат и повторите попытку"),
        (503, "prepared_audio_too_large", "временно недоступен. Повторите попытку позже"),
        (None, None, "Не удалось обработать аудио. Повторите попытку позже"),
    ],
)
async def test_stt_rejection_reaches_ui_and_model_without_losing_reason(
    monkeypatch, status, code, expected
):
    audio = _audio_attachment(filename="call.mp3")
    audio["content_type"] = audio["file"]["meta"]["content_type"] = "audio/mpeg"
    document = {"type": "file", "file": {"id": "pdf-1", "filename": "notes.pdf"},
                "name": "notes.pdf", "content_type": "application/pdf"}
    prompt = "Summarize the recording in English."
    body = {"messages": [{"role": "user", "content": prompt, "files": [audio, document]}],
            "files": [audio, document]}
    metadata = {"files": [audio, document]}
    original_attachment = copy.deepcopy(audio)
    statuses = []
    filter_ = Filter()
    filter_.valves.internal_api_key = "test-token"
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_was_transcribed", lambda *_: _async_value(False))
    monkeypatch.setattr(filter_, "_native_upload_path", lambda *_: _async_value("unused.mp3"))

    async def reject(**kwargs):
        request = httpx.Request("POST", "http://stage2-stt:8080/stage2-api/transcription/jobs")
        if status is None:
            raise httpx.ConnectError("PRIVATE transport details", request=request)
        response = httpx.Response(status, request=request, json={
            "detail": {"code": code, "message": "PRIVATE provider details", "retryable": False}
        })
        response.raise_for_status()

    async def emit(event):
        statuses.append(event)

    async def forbid_transcript_save(*args, **kwargs):
        raise AssertionError("A rejected recording must not be saved as transcribed")

    monkeypatch.setattr(filter_, "_call_sidecar", reject)
    monkeypatch.setattr(filter_, "_mark_transcribed", forbid_transcript_save)
    await filter_.inlet(body, __user__={"id": "user-1"}, __metadata__=metadata,
                        __event_emitter__=emit)

    ui_message = statuses[-1]["data"]["description"]
    model_content = body["messages"][-1]["content"]
    assert expected in ui_message
    assert ui_message in model_content
    assert model_content.startswith(prompt)
    assert "Транскрибация не выполнена" in model_content
    assert "PRIVATE" not in model_content
    assert statuses[-1]["data"]["done"] is True
    assert metadata["_stage2_audio_transcript"] is None
    assert body["files"] == metadata["files"] == [document]
    assert audio == original_attachment
    assert body["messages"][-1]["files"] == [audio, document]
    if status == 422 and code in {"prepared_audio_too_large", "provider_direct_upload_limit_exceeded"}:
        assert "Разделите запись на части" in ui_message
        assert "Повторная отправка того же файла не поможет" in ui_message
        assert "Транскрипция не получена" in ui_message
        assert "Проверьте формат" not in ui_message
        assert "Повторите попытку" not in ui_message
        assert "100" not in ui_message


@pytest.mark.asyncio
async def test_inlet_removes_audio_from_outbound_files_when_sidecar_is_not_configured():
    audio = _audio_attachment()
    document = {"type": "file", "file": {"id": "pdf-1", "filename": "notes.pdf"}, "name": "notes.pdf", "content_type": "application/pdf"}
    body = {"messages": [{"role": "user", "content": "Расшифруй", "files": [audio, document]}], "files": [audio, document]}
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
    body = {"messages": [{"role": "user", "content": "Выдели ключевые фразы", "files": [_audio_attachment()]}], "files": [_audio_attachment()]}
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
async def test_inlet_uses_current_message_audio_despite_aggregate_order(monkeypatch, tmp_path):
    filter_ = Filter()
    filter_.valves.internal_api_key = "test-token"
    earlier_audio = _audio_attachment("audio-earlier", "earlier.wav")
    current_audio = _audio_attachment("audio-current", "current.wav")
    body = {
        "messages": [
            {"role": "user", "content": "Первое аудио"},
            {"role": "assistant", "content": "Первый ответ"},
            {"role": "user", "content": "Второе аудио", "files": [current_audio]},
        ],
        "files": [],
    }
    metadata = {"files": [current_audio, earlier_audio]}
    source = tmp_path / "current.wav"
    source.write_bytes(b"RIFF")

    async def read_upload(file_id, _user_id):
        assert file_id == "audio-current"
        return source

    async def call_sidecar(**kwargs):
        assert kwargs["filename"] == "current.wav"
        return {"result": {"text": "Текст второго аудио."}}

    monkeypatch.setattr(filter_, "_native_upload_path", read_upload)
    monkeypatch.setattr(filter_, "_call_sidecar", call_sidecar)
    monkeypatch.setattr(filter_, "_cached_transcript", lambda *_: _async_value(None))
    monkeypatch.setattr(filter_, "_was_transcribed", lambda *_: _async_value(False))
    monkeypatch.setattr(filter_, "_mark_transcribed", lambda *_: _async_value(None))

    await filter_.inlet(body, __user__={"id": "user-1"}, __metadata__=metadata)

    assert metadata["files"] == []
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


@pytest.mark.asyncio
async def test_outlet_projects_transcript_into_native_output_without_mutating_original():
    # Same structured shape returned by the actual 0.11.4 ordinary-chat run.
    original = [{"type": "message", "id": "msg-1", "status": "completed", "role": "assistant",
                 "content": [{"type": "output_text", "text": "Summary.",
                              "annotations": [{"type": "url_citation", "start_index": 0, "end_index": 7}]}]}]
    before = copy.deepcopy(original)
    message = {"role": "assistant", "content": "Summary.", "output": original}
    body = {"messages": [message]}
    metadata = {"_stage2_audio_transcript": "Exact transcript.",
                "_stage2_audio_display": "[00:00-00:14] Speaker 1:\nExact transcript."}
    await Filter().outlet(body, __metadata__=metadata)
    visible = "".join(part["text"] for item in message["output"] for part in item["content"])
    assert visible == message["content"]
    assert "## Полная транскрипция\n\n[00:00-00:14] Speaker 1:\nExact transcript." in visible
    assert message["output"][0]["content"][1] == before[0]["content"][0]
    assert message["output"][0]["id"] == "msg-1"
    assert original == before  # Native output_changed must see a different value.
    result_before = copy.deepcopy(body)
    await Filter().outlet(body, __metadata__=metadata)
    assert body == result_before


@pytest.mark.asyncio
async def test_outlet_preserves_native_tool_and_reasoning_output_between_text_messages():
    original = [
        {"type": "message", "id": "first", "role": "assistant", "content": [{"type": "output_text", "text": "First."}]},
        {"type": "reasoning", "id": "reason", "summary": [{"type": "summary_text", "text": "Reasoning."}]},
        {"type": "function_call", "id": "call", "name": "example", "arguments": "{}", "status": "completed"},
        {"type": "message", "id": "last", "role": "assistant", "content": [{"type": "output_text", "text": "Last."}]},
    ]
    before = copy.deepcopy(original)
    message = {"role": "assistant", "content": "First.Last.", "output": original}
    await Filter().outlet({"messages": [message]}, __metadata__={"_stage2_audio_transcript": "Transcript."})
    projected = message["output"]
    assert projected[1:3] == before[1:3]
    assert projected[0]["content"][1] == before[0]["content"][0]
    assert projected[-1]["content"][0] == before[-1]["content"][0]
    assert projected[0]["content"][0]["text"] == "## Краткое содержание\n\n"
    assert projected[-1]["content"][-1]["text"].endswith("## Полная транскрипция\n\nTranscript.")
    assert original == before


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
