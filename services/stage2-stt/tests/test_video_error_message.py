from __future__ import annotations

import httpx

from openwebui_filters.stage2_audio_context_filter import Filter
from stage2_stt.contracts import OpenWebUITranscriptionEnvelopeV1


def test_sidecar_error_explains_video_without_audio_track():
    request = httpx.Request("POST", "http://stage2-stt:8080/stage2-api/media/prepare")
    response = httpx.Response(
        422,
        request=request,
        json={"detail": {"code": "source_has_no_audio_stream"}},
    )

    message = Filter()._format_sidecar_error(
        httpx.HTTPStatusError("unprocessable", request=request, response=response)
    )

    assert "аудиодорожки" in message


def test_sidecar_envelope_excludes_filter_only_video_state():
    envelope = Filter()._build_envelope(
        {"id": "user-1", "groups": []},
        {"chat_id": "chat-1", "message_id": "message-1"},
        {
            "file_id": "video-1",
            "filename": "recording.mp4",
            "mime_type": "video/mp4",
            "size_bytes": 42,
            "is_video": True,
        },
    )

    parsed = OpenWebUITranscriptionEnvelopeV1.model_validate(envelope)

    assert parsed.file is not None
    assert parsed.file.file_id == "video-1"
