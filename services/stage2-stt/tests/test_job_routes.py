import json

from fastapi.testclient import TestClient

from stage2_stt.app import create_app


INTERNAL_TOKEN = "unit-test-internal-token"


def _clear_provider_env(monkeypatch):
    monkeypatch.delenv("STAGE2_LEMONFOX_API_KEY", raising=False)
    monkeypatch.delenv("STAGE2_STT_INTERNAL_API_KEY", raising=False)
    monkeypatch.delenv("STAGE2_STT_ALLOW_STUB_TRANSCRIPT", raising=False)
    monkeypatch.delenv("STAGE2_STT_OUTPUT_PROFILE", raising=False)
    monkeypatch.delenv("STAGE2_STT_STORAGE_MODE", raising=False)
    monkeypatch.delenv("STAGE2_STT_AUDIO_BUCKET", raising=False)


def _enable_internal_stub(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("STAGE2_STT_INTERNAL_API_KEY", INTERNAL_TOKEN)
    monkeypatch.setenv("STAGE2_STT_ALLOW_STUB_TRANSCRIPT", "true")
    monkeypatch.setenv("STAGE2_STT_OUTPUT_PROFILE", "mp3_high_compat")


def _envelope() -> str:
    return json.dumps(
        {
            "source_context": "openwebui",
            "user_id": "user-1",
            "user_email": "user@example.test",
            "user_role": "user",
            "user_groups": ["stage2-stt"],
            "chat_id": "chat-1",
            "message_id": "message-1",
            "file": {
                "file_id": "file-1",
                "filename": "sample.mp3",
                "mime_type": "audio/mpeg",
                "size_bytes": 9,
            },
            "selected_output_profile": "mp3_high_compat",
        }
    )


def _post_job(client: TestClient, *, token: str = INTERNAL_TOKEN, content_type: str = "audio/mpeg"):
    return client.post(
        "/stage2-api/transcription/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"envelope": _envelope()},
        files={"prepared_audio": ("sample.mp3", b"fake-mp3", content_type)},
    )


def test_job_routes_are_disabled_without_internal_auth_config(monkeypatch):
    _clear_provider_env(monkeypatch)
    client = TestClient(create_app())

    response = _post_job(client)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "stage2_stt_internal_auth_not_configured"


def test_job_routes_reject_wrong_internal_token(monkeypatch):
    _enable_internal_stub(monkeypatch)
    client = TestClient(create_app())

    response = _post_job(client, token="wrong-token")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "stage2_stt_internal_auth_failed"


def test_job_route_requires_key_unless_stub_mode_is_explicit(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("STAGE2_STT_INTERNAL_API_KEY", INTERNAL_TOKEN)
    client = TestClient(create_app())

    response = _post_job(client)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "provider_auth_missing"


def test_job_route_rejects_prepared_audio_mime_mismatch(monkeypatch):
    _enable_internal_stub(monkeypatch)
    client = TestClient(create_app())

    response = _post_job(client, content_type="video/mp4")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_input_format"


def test_job_route_creates_completed_stub_job_and_exposes_result(monkeypatch):
    _enable_internal_stub(monkeypatch)
    client = TestClient(create_app())

    response = _post_job(client)

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["status"] == "completed"
    assert body["job"]["user_id"] == "user-1"
    assert body["job"]["selected_output_profile"] == "mp3_high_compat"
    assert body["job"]["provider_id"] == "lemonfox"
    assert body["result"]["job_id"] == body["job"]["job_id"]
    assert body["result"]["provider_id"] == "lemonfox"
    assert "lemonfox_api_key_absent_stub_result" in body["result"]["warnings"]

    result_response = client.get(
        f"/stage2-api/transcription/jobs/{body['job']['job_id']}/result",
        headers={"X-Stage2-Internal-Token": INTERNAL_TOKEN},
    )

    assert result_response.status_code == 200
    assert result_response.json()["job_id"] == body["job"]["job_id"]


def test_job_route_records_openwebui_selected_output_profile(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("STAGE2_STT_INTERNAL_API_KEY", INTERNAL_TOKEN)
    monkeypatch.setenv("STAGE2_STT_ALLOW_STUB_TRANSCRIPT", "true")
    client = TestClient(create_app())

    response = _post_job(client)

    assert response.status_code == 200
    assert response.json()["job"]["selected_output_profile"] == "mp3_high_compat"
    assert response.json()["job"]["prepared_audio"]["output_profile"] == "mp3_high_compat"


def test_cancel_completed_job_is_terminal_noop(monkeypatch):
    _enable_internal_stub(monkeypatch)
    client = TestClient(create_app())
    created = _post_job(client).json()

    response = client.post(
        f"/stage2-api/transcription/jobs/{created['job']['job_id']}/cancel",
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["cancel_state"]["requested"] is False
