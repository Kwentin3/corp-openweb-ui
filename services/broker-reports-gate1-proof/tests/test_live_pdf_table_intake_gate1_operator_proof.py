from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "services" / "broker-reports-gate1-proof" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from live_pdf_table_intake_gate1_operator_proof import (  # noqa: E402
    _create_native_chat,
    _delete_chat,
    _run_chat,
)


class _Response:
    def __init__(self, value, status_code: int = 200):
        self._value = value
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")

    def json(self):
        return self._value


class _Session:
    def __init__(self):
        self.posts = []
        self.deletes = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if url.endswith("/api/v1/chats/new"):
            return _Response({"id": "chat-attested"})
        return _Response({"choices": [{"message": {"content": "completed"}}]})

    def delete(self, url, **kwargs):
        self.deletes.append((url, kwargs))
        return _Response({}, status_code=204)


def _uploads():
    return [
        {
            "id": "file-safe",
            "filename": "synthetic.pdf",
            "mime_type": "application/pdf",
            "size": 123,
        }
    ]


def test_operator_uses_server_attested_chat_context_and_terminal_response():
    session = _Session()
    native_chat = _create_native_chat(
        session,
        "https://example.invalid",
        workspace_model_id="broker-reports-ndfl",
        uploads=_uploads(),
    )

    content = _run_chat(
        session,
        "https://example.invalid",
        workspace_model_id="broker-reports-ndfl",
        case_id=native_chat["chat_id"],
        uploads=_uploads(),
        native_chat=native_chat,
        timeout=30,
    )

    assert content == "completed"
    assert native_chat["chat_id"] == "chat-attested"
    completion = session.posts[-1][1]["json"]
    assert completion["parent_id"] == native_chat["user_message_id"]
    assert completion["metadata"]["chat_id"] == "chat-attested"
    assert completion["metadata"]["session_id"] == "chat-attested"
    assert completion["metadata"]["message_id"] == (
        native_chat["assistant_message_id"]
    )
    assert completion["stream"] is False


def test_operator_deletes_the_exact_temporary_chat():
    session = _Session()

    _delete_chat(session, "https://example.invalid", "chat-attested")

    assert session.deletes == [
        ("https://example.invalid/api/v1/chats/chat-attested", {"timeout": 30})
    ]
