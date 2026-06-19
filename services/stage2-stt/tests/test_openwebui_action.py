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
