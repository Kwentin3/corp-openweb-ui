import asyncio

import httpx

from openwebui_actions.stage2_media_transcription_action import Action


def test_action_warning_formatter_hides_absent_warnings():
    action = Action()

    assert action._format_warnings([]) == ""


def test_action_warning_formatter_uses_human_storage_alias():
    action = Action()

    text = action._format_warnings(["prepared_audio_storage_transient"])

    assert "Warnings:" not in text
    assert "prepared_audio_storage_transient" not in text
    assert "аудиофайл, отправленный на транскрибацию, не сохраняется" in text


def test_action_warning_formatter_aliases_are_configurable():
    action = Action()
    action.valves.warning_aliases_json = (
        '{"prepared_audio_storage_transient":"Configured storage note"}'
    )

    text = action._format_warnings(["prepared_audio_storage_transient"])

    assert "Configured storage note" in text
    assert "аудиофайл, отправленный на транскрибацию" not in text


def test_action_warning_formatter_preserves_unknown_technical_warnings():
    action = Action()

    text = action._format_warnings(["provider_direct_upload_limit_warning"])

    assert "Технические предупреждения: provider_direct_upload_limit_warning" in text


def test_action_formats_safe_transcript_ref_without_raw_result_json():
    action = Action()

    text = action._format_transcript_ref("art_safe_reference")

    assert "Transcript reference: `art_safe_reference`" in text
    assert "{" not in text


def test_action_ignores_non_artifact_transcript_ref():
    action = Action()

    assert action._format_transcript_ref("job-123") == ""


def test_action_returns_backward_compatible_flat_transcript_with_safe_ref(monkeypatch, tmp_path):
    action = Action()
    action.valves.internal_api_key = "unit-token"
    action.valves.upload_root = str(tmp_path)
    upload_path = tmp_path / "file-1_sample.mp3"
    upload_path.write_bytes(b"fake-mp3")

    async def fake_call_sidecar(**kwargs):
        return {
            "result": {"text": "hello transcript"},
            "transcript_ref": "art_safe_reference",
            "warnings": [],
        }

    monkeypatch.setattr(action, "_call_sidecar", fake_call_sidecar)

    response = asyncio.run(
        action.action(
            {"files": [{"file": {"id": "file-1", "filename": "sample.mp3", "mime_type": "audio/mpeg"}}]},
            __user__={"id": "user-1"},
            __metadata__={"chat_id": "chat-1"},
        )
    )

    assert response["content"].startswith("Transcript:\n\nhello transcript")
    assert "Transcript reference: `art_safe_reference`" in response["content"]
    assert "{" not in response["content"]


def test_action_formats_speaker_segments_for_readable_raw_transcript(monkeypatch, tmp_path):
    action = Action()
    action.valves.internal_api_key = "unit-token"
    action.valves.upload_root = str(tmp_path)
    upload_path = tmp_path / "file-1_sample.mp3"
    upload_path.write_bytes(b"fake-mp3")

    async def fake_call_sidecar(**kwargs):
        return {
            "result": {
                "text": "flat fallback should not be used",
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "start_seconds": 0,
                        "end_seconds": 4.2,
                        "text": "Первый фрагмент.",
                    },
                    {
                        "speaker": "SPEAKER_00",
                        "start_seconds": 4.2,
                        "end_seconds": 8.0,
                        "text": "Продолжение.",
                    },
                    {
                        "speaker": "SPEAKER_01",
                        "start_seconds": 8.0,
                        "end_seconds": 12.0,
                        "text": "Ответ.",
                    },
                ],
            },
            "transcript_ref": "art_safe_reference",
            "warnings": [],
        }

    monkeypatch.setattr(action, "_call_sidecar", fake_call_sidecar)

    response = asyncio.run(
        action.action(
            {"files": [{"file": {"id": "file-1", "filename": "sample.mp3", "mime_type": "audio/mpeg"}}]},
            __user__={"id": "user-1"},
            __metadata__={"chat_id": "chat-1"},
        )
    )

    content = response["content"]
    assert content.startswith(
        "Transcript:\n\n[00:00-00:08] Спикер 1:\n"
        "Первый фрагмент. Продолжение."
    )
    assert "[00:08-00:12] Спикер 2:\nОтвет." in content
    assert "Transcript reference: `art_safe_reference`" in content
    assert "flat fallback should not be used" not in content
    assert "SPEAKER_00" not in content
    assert "SPEAKER_01" not in content
    assert "{" not in content


def test_action_transcript_formatter_uses_flat_fallback_without_speakers():
    action = Action()

    text = action._format_transcript_result(
        {
            "text": "plain transcript",
            "segments": [
                {
                    "start_seconds": 0,
                    "end_seconds": 5,
                    "text": "segment text",
                }
            ],
        }
    )

    assert text == "plain transcript"


def test_action_lists_postprocessing_templates_without_prompt_body(monkeypatch):
    action = Action()
    action.valves.internal_api_key = "unit-token"

    async def fake_templates(**kwargs):
        return [
            {
                "template_id": "stage2.stt.summary.v1",
                "command": "stt-summary",
                "label": "Краткий пересказ",
                "prompt_body_hash": "h" * 64,
            }
        ]

    monkeypatch.setattr(action, "_call_sidecar_templates", fake_templates)

    response = asyncio.run(
        action.action(
            {"stage2_stt": {"operation": "list_postprocessing_templates"}},
            __user__={"id": "user-1", "role": "user"},
        )
    )

    assert response["content"] == ""
    assert response["stage2_stt_templates"][0]["template_id"] == "stage2.stt.summary.v1"
    assert "TRANSCRIPT_WITH_SPEAKERS" not in str(response)


def test_action_executes_postprocessing_with_artifact_context(monkeypatch):
    action = Action()
    action.valves.internal_api_key = "unit-token"
    captured = {}

    async def fake_postprocessing(**kwargs):
        captured.update(kwargs)
        return {
            "label": "Краткий пересказ",
            "text": "Processed result",
            "result_ref": "art_processed_reference",
        }

    monkeypatch.setattr(action, "_call_sidecar_postprocessing", fake_postprocessing)

    response = asyncio.run(
        action.action(
            {
                "chat_id": "chat-1",
                "stage2_stt": {
                    "operation": "execute_postprocessing",
                    "transcript_ref": "art_transcript_reference",
                    "template_id": "stage2.stt.summary.v1",
                    "openwebui_file_id": "file-1",
                },
            },
            __user__={"id": "user-1", "role": "user", "groups": ["group-1"]},
            __metadata__={"chat_id": "chat-1"},
        )
    )

    assert response["content"].startswith("Краткий пересказ\n\nProcessed result")
    assert "Post-processing result reference: `art_processed_reference`" in response["content"]
    assert captured["transcript_ref"] == "art_transcript_reference"
    assert captured["template_id"] == "stage2.stt.summary.v1"
    assert captured["user"]["id"] == "user-1"


def test_action_exports_message_docx_without_chat_content(monkeypatch):
    action = Action()
    action.valves.internal_api_key = "unit-token"
    captured = {}

    async def fake_docx(**kwargs):
        captured.update(kwargs)
        return {
            "schema_version": "MessageDocxExportResultV1",
            "export_id": "docx-1",
            "filename": "message.docx",
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "size_bytes": 12,
            "checksum_sha256": "a" * 64,
            "delivery": "base64",
            "download_payload_base64": "ZmFrZQ==",
            "download_url": None,
            "file_id": None,
            "warnings": [],
        }

    monkeypatch.setattr(action, "_call_sidecar_message_docx", fake_docx)

    response = asyncio.run(
        action.action(
            {
                "stage2_message_docx": {
                    "operation": "export_message_docx",
                    "request": {
                        "schema_version": "MessageDocxExportRequestV1",
                        "request_id": "req-1",
                        "chat_id": "chat-1",
                        "message_id": "msg-1",
                        "message_role": "assistant",
                        "message_text": "Selected assistant message.",
                        "message_markdown": "Selected assistant message.",
                        "message_html": None,
                        "source": "dom",
                        "safe_metadata": {
                            "chat_title": "Unit Chat",
                            "model_name": "unit-model",
                            "message_timestamp": None,
                            "source_url_path": "/c/chat-1",
                            "result_ref": None,
                        },
                        "options": {
                            "include_chat_title": True,
                            "include_model_name": True,
                            "include_timestamp": True,
                            "formatting_profile": "simple_mvp",
                        },
                    },
                }
            },
            __user__={"id": "user-1", "role": "user"},
            __metadata__={"chat_id": "chat-1"},
        )
    )

    assert response["content"] == ""
    assert response["stage2_message_docx_export"]["delivery"] == "base64"
    assert captured["token"] == "unit-token"
    assert captured["request"]["message_id"] == "msg-1"
    assert "stage2-stt:8080" not in str(response)


def test_action_maps_message_docx_sidecar_error_without_internal_url(monkeypatch):
    action = Action()
    action.valves.internal_api_key = "unit-token"

    async def fake_docx(**kwargs):
        request = httpx.Request("POST", "http://stage2-stt:8080/stage2-api/message-docx/exports")
        response = httpx.Response(
            413,
            request=request,
            json={
                "detail": {
                    "code": "message_docx_message_too_large",
                    "message": "Selected assistant message exceeds the configured DOCX export limit",
                }
            },
        )
        raise httpx.HTTPStatusError("failed", request=request, response=response)

    monkeypatch.setattr(action, "_call_sidecar_message_docx", fake_docx)

    response = asyncio.run(
        action.action(
            {
                "stage2_message_docx": {
                    "operation": "export_message_docx",
                    "request": {"schema_version": "MessageDocxExportRequestV1"},
                }
            },
            __user__={"id": "user-1", "role": "user"},
        )
    )

    assert response["content"] == ""
    assert response["stage2_message_docx_error"]["code"] == "message_docx_message_too_large"
    assert "stage2-stt:8080" not in str(response)
