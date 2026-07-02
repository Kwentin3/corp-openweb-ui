from stage2_stt.browser_config import build_browser_normalization_config
from stage2_stt.config import load_stt_config


def test_browser_config_is_built_from_validated_stt_config():
    config = load_stt_config(
        {
            "STAGE2_STT_OUTPUT_PROFILE": "mp3_high_compat",
            "STAGE2_FFMPEG_BROWSER_MAX_INPUT_MB": "2048",
            "STAGE2_STT_MAX_PREPARED_AUDIO_MB": "100",
            "STAGE2_FFMPEG_CORE_BASE_URL": "/static/stage2-assets/ffmpeg/0.12.6/",
        }
    )

    browser_config = build_browser_normalization_config(config)

    assert browser_config["generated_from_env"] is True
    assert browser_config["selected_output_profile"] == "mp3_high_compat"
    assert browser_config["max_browser_input_mb"] == 2048
    assert browser_config["max_prepared_audio_mb"] == 100
    assert browser_config["ffmpeg_core_base_url"] == "/static/stage2-assets/ffmpeg/0.12.6"
    assert (
        browser_config["ffmpeg_script_url"]
        == "/static/stage2-assets/ffmpeg/0.12.6/ffmpeg.js"
    )
