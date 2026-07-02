import asyncio

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
