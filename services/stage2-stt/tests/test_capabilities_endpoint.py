from fastapi.testclient import TestClient

from stage2_stt.app import create_app


def test_runtime_capabilities_endpoint_works_without_lemonfox_key(monkeypatch):
    monkeypatch.delenv("STAGE2_LEMONFOX_API_KEY", raising=False)

    response = TestClient(create_app()).get("/stage2-api/transcription/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["input_accept_mode"] == "broad_ffmpeg_probe"
    assert body["declared_input_mime_prefixes"] == ["audio/", "video/"]
    assert body["declared_input_extensions"] == [
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
    ]
    assert body["ffmpeg_probe_required"] is True
    assert body["require_audio_stream"] is True
    assert body["selected_output_profile"] == "mp3_high_compat"
    assert body["fallback_output_profile"] == "mp3_high_compat"
    assert body["available_output_profiles"] == [
        "opus_webm_compact",
        "opus_ogg_compact",
        "mp3_high_compat",
        "wav_pcm_safe",
    ]
    assert body["max_browser_input_mb"] == 1024
    assert body["max_browser_duration_minutes"] is None
    assert body["max_prepared_audio_mb"] == 100
    assert body["provider_id"] == "lemonfox"
    assert body["adapter_id"] == "lemonfox"
    assert "lemonfox_api_key_absent_live_calls_disabled" in body["warnings"]


def test_runtime_capabilities_endpoint_does_not_expose_secrets(monkeypatch):
    secret_value = "unit-test-redacted-value"
    monkeypatch.setenv("STAGE2_LEMONFOX_API_KEY", secret_value)
    monkeypatch.setenv("STAGE2_STT_AUDIO_BUCKET", "private-audio-bucket")

    response = TestClient(create_app()).get("/stage2-api/transcription/capabilities")

    assert response.status_code == 200
    serialized = response.text
    assert secret_value not in serialized
    assert "STAGE2_LEMONFOX_API_KEY" not in serialized
    assert "private-audio-bucket" not in serialized
    assert "lemonfox_api_key_absent_live_calls_disabled" not in response.json()["warnings"]
