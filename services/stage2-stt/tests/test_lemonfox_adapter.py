from stage2_stt.config import load_stt_config
from stage2_stt.lemonfox import LemonfoxSttAdapter


def test_lemonfox_adapter_capability_profile_exists():
    adapter = LemonfoxSttAdapter(load_stt_config({}))

    capability = adapter.capabilities()

    assert capability.provider_id == "lemonfox"
    assert capability.adapter_id == "lemonfox"
    assert capability.max_direct_upload_mb == 100
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


def test_lemonfox_request_form_enables_speaker_labels_and_verbose_json():
    adapter = LemonfoxSttAdapter(
        load_stt_config({"STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS": "true"})
    )

    form = adapter._request_form()

    assert form["response_format"] == "verbose_json"
    assert form["speaker_labels"] == "true"
    assert form["timestamp_granularities[]"] == "word"


def test_lemonfox_normalizes_speaker_labels_without_raw_payload_leak():
    marker = "raw-lemonfox-marker-should-not-survive"
    adapter = LemonfoxSttAdapter(
        load_stt_config({"STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS": "true"})
    )

    result = adapter.normalize_transcript(
        {
            "text": "A hello. B hi.",
            "raw_marker": marker,
            "segments": [
                {
                    "text": "A hello.",
                    "start": 0,
                    "end": 1,
                    "speaker": "speaker_0",
                    "words": [
                        {"word": "A", "start": 0, "end": 0.1, "speaker": "speaker_0"},
                        {"word": "hello", "start": 0.1, "end": 1, "speaker": "speaker_0"},
                    ],
                },
                {
                    "text": "B hi.",
                    "start": 1,
                    "end": 2,
                    "speaker": "speaker_1",
                    "words": [
                        {"word": "B", "start": 1, "end": 1.1, "speaker": "speaker_1"},
                        {"word": "hi", "start": 1.1, "end": 2, "speaker": "speaker_1"},
                    ],
                },
            ],
        },
        output_profile="mp3_high_compat",
    )

    assert {segment.speaker for segment in result.segments} == {"speaker_0", "speaker_1"}
    assert result.segments[0].words[0].speaker == "speaker_0"
    assert marker not in result.model_dump_json()
