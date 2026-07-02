import pytest

from stage2_stt.config import (
    InputAcceptMode,
    OutputProfile,
    PostProcessingExecutorMode,
    PromptCatalogMode,
    SttConfigError,
    StorageMode,
    load_stt_config,
)


def test_config_loads_defaults_without_lemonfox_key():
    config = load_stt_config({})

    assert config.provider == "lemonfox"
    assert config.provider_adapter == "lemonfox"
    assert config.lemonfox.has_api_key is False
    assert config.input_accept_mode is InputAcceptMode.BROAD_FFMPEG_PROBE
    assert config.declared_input_extensions == (
        "mp3",
        "wav",
        "m4a",
        "webm",
        "ogg",
        "mp4",
        "mov",
        "mkv",
        "avi",
        "flac",
        "aac",
    )
    assert config.declared_input_mime_prefixes == ("audio/", "video/")
    assert config.require_audio_stream is True
    assert config.ffmpeg_probe_before_action is True
    assert config.output_profile is OutputProfile.MP3_HIGH_COMPAT
    assert config.fallback_output_profile is OutputProfile.MP3_HIGH_COMPAT
    assert config.browser_max_input_mb == 1024
    assert config.max_prepared_audio_mb == 100
    assert config.storage_mode is StorageMode.AUTO
    assert config.artifact_store_mode.value == "disabled"
    assert config.artifact_transcript_ttl_days == 14
    assert config.artifact_prepared_audio_ttl_hours == 24
    assert config.diagnostic_provider_payload_enabled is False
    assert config.prompt_catalog_mode is PromptCatalogMode.DISABLED
    assert config.postprocessing_executor_mode is PostProcessingExecutorMode.DISABLED
    assert config.postprocessing_max_transcript_chars == 60000


def test_invalid_config_fails_fast():
    with pytest.raises(SttConfigError) as exc_info:
        load_stt_config({"STAGE2_STT_OUTPUT_PROFILE": "not-a-profile"})

    assert "STAGE2_STT_OUTPUT_PROFILE" in str(exc_info.value)


def test_sqlite_artifact_store_requires_explicit_path():
    with pytest.raises(SttConfigError) as exc_info:
        load_stt_config({"STAGE2_STT_ARTIFACT_STORE_MODE": "sqlite"})

    assert "STAGE2_STT_ARTIFACT_STORE_PATH" in str(exc_info.value)


def test_openwebui_sqlite_prompt_catalog_requires_explicit_db_path():
    with pytest.raises(SttConfigError) as exc_info:
        load_stt_config({"STAGE2_STT_PROMPT_CATALOG_MODE": "openwebui_sqlite"})

    assert "STAGE2_STT_OPENWEBUI_PROMPT_DB_PATH" in str(exc_info.value)


def test_openai_postprocessing_executor_requires_complete_server_side_config():
    with pytest.raises(SttConfigError) as exc_info:
        load_stt_config({"STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE": "openai_compatible"})

    assert "STAGE2_STT_POSTPROCESSING_OPENAI_BASE_URL" in str(exc_info.value)


def test_openai_postprocessing_base_url_falls_back_to_primary_openai_base_url():
    config = load_stt_config(
        {
            "STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE": "openai_compatible",
            "OPENAI_API_BASE_URL": "https://api.openai.com/v1",
            "STAGE2_STT_POSTPROCESSING_OPENAI_API_KEY": "unit-key",
            "STAGE2_STT_POSTPROCESSING_OPENAI_MODEL": "unit-model",
        }
    )

    assert config.postprocessing_openai_base_url == "https://api.openai.com/v1"


def test_openai_postprocessing_api_key_falls_back_to_primary_openai_api_key():
    config = load_stt_config(
        {
            "STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE": "openai_compatible",
            "STAGE2_STT_POSTPROCESSING_OPENAI_BASE_URL": "https://api.openai.com/v1",
            "OPENAI_API_KEY": "unit-primary-key",
            "STAGE2_STT_POSTPROCESSING_OPENAI_MODEL": "unit-model",
        }
    )

    assert config.postprocessing_openai_api_key == "unit-primary-key"


def test_gate_1_2_rejects_diagnostic_provider_payload_storage():
    with pytest.raises(SttConfigError) as exc_info:
        load_stt_config({"STAGE2_STT_DIAGNOSTIC_PROVIDER_PAYLOAD_ENABLED": "true"})

    assert "STAGE2_STT_DIAGNOSTIC_PROVIDER_PAYLOAD_ENABLED" in str(exc_info.value)
