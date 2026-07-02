from stage2_stt.config import load_stt_config
from stage2_stt.lemonfox import LemonfoxSttAdapter


def test_lemonfox_adapter_capability_profile_exists():
    adapter = LemonfoxSttAdapter(load_stt_config({}))

    capability = adapter.capabilities()

    assert capability.provider_id == "lemonfox"
    assert capability.adapter_id == "lemonfox"
    assert capability.max_direct_upload_mb == 400
    assert capability.max_url_upload_mb == 1024
    assert "mp3_high_compat" in capability.supported_input_profiles
    assert "opus_webm_compact" in capability.supported_input_profiles
    assert capability.supports_timestamps is True
    assert capability.supports_provider_cancel is None
    assert capability.cancel_strategy == "local_cancel_until_provider_proof"


def test_lemonfox_normalizes_verbose_json_response():
    adapter = LemonfoxSttAdapter(load_stt_config({}))

    result = adapter.normalize_transcript(
        {
            "text": "hello",
            "language": "ru",
            "duration": 1.5,
            "segments": [
                {
                    "text": "hello",
                    "start": 0,
                    "end": 1.5,
                    "words": [{"word": "hello", "start": 0, "end": 1.5}],
                }
            ],
        },
        output_profile="mp3_high_compat",
    )

    assert result.text == "hello"
    assert result.language == "ru"
    assert result.duration_seconds == 1.5
    assert result.segments[0].words[0].text == "hello"
    assert result.provider_id == "lemonfox"
