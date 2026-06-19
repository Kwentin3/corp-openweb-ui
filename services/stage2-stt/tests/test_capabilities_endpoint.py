from fastapi.testclient import TestClient

from stage2_stt.app import create_app


def test_runtime_capabilities_endpoint_works_without_lemonfox_key(monkeypatch):
    monkeypatch.delenv("STAGE2_LEMONFOX_API_KEY", raising=False)

    response = TestClient(create_app()).get("/stage2-api/transcription/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["selected_output_profile"] == "opus_webm_compact"
    assert body["available_output_profiles"] == [
        "opus_webm_compact",
        "opus_ogg_compact",
        "mp3_high_compat",
        "wav_pcm_safe",
    ]
    assert body["max_browser_input_mb"] == 1024
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
