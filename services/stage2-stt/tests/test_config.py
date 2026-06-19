import pytest

from stage2_stt.config import OutputProfile, SttConfigError, StorageMode, load_stt_config


def test_config_loads_defaults_without_lemonfox_key():
    config = load_stt_config({})

    assert config.provider == "lemonfox"
    assert config.provider_adapter == "lemonfox"
    assert config.lemonfox.has_api_key is False
    assert config.output_profile is OutputProfile.OPUS_WEBM_COMPACT
    assert config.fallback_output_profile is OutputProfile.MP3_HIGH_COMPAT
    assert config.browser_max_input_mb == 1024
    assert config.max_prepared_audio_mb == 100
    assert config.storage_mode is StorageMode.AUTO


def test_invalid_config_fails_fast():
    with pytest.raises(SttConfigError) as exc_info:
        load_stt_config({"STAGE2_STT_OUTPUT_PROFILE": "not-a-profile"})

    assert "STAGE2_STT_OUTPUT_PROFILE" in str(exc_info.value)
