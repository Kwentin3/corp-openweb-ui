from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path

from fastapi.testclient import TestClient

from officecli_openapi_proof.app import create_app
from officecli_openapi_proof.config import Settings
from officecli_openapi_proof.officecli import OfficeCliOutput, SubprocessOfficeCliExecutor


def office_output(*arguments: str, payload: object | None = None) -> OfficeCliOutput:
    text = json.dumps(payload) if payload is not None else f"official {' '.join(arguments)} output"
    return OfficeCliOutput(
        command=("/usr/local/bin/officecli", *arguments),
        text=text,
        content_sha256=sha256(text.encode("utf-8")).hexdigest(),
        auto_resident_disabled=True,
    )


@dataclass
class RecordingOfficeCli:
    calls: list[tuple[str, ...]] = field(default_factory=list)
    inputs: list[str | None] = field(default_factory=list)
    batch_success: bool = True

    def run(self, *arguments: str, input_text: str | None = None) -> OfficeCliOutput:
        self.calls.append(arguments)
        self.inputs.append(input_text)
        if arguments[0] == "batch":
            Path(arguments[1]).write_bytes(b"changed DOCX bytes")
            return office_output(*arguments, payload={"success": self.batch_success, "data": {"edited": 1}})
        if arguments[0] in {"view", "validate"}:
            return office_output(*arguments, payload={"success": True, "data": {"operation": arguments[0]}})
        return office_output(*arguments)


@dataclass
class RecordingOpenWebUi:
    source: bytes = b"original DOCX bytes"
    calls: list[tuple[str, object]] = field(default_factory=list)
    uploaded: dict[str, object] | None = None

    def download(self, file_id: str, authorization: str, destination: Path) -> None:
        self.calls.append(("download", file_id))
        destination.write_bytes(self.source)

    def upload(self, source: Path, output_name: str, authorization: str) -> dict[str, object]:
        self.calls.append(("upload", output_name))
        assert source.read_bytes() == b"changed DOCX bytes"
        self.uploaded = {"id": "result-file-id", "filename": output_name}
        return self.uploaded

    def attach(
        self, chat_id: str, message_id: str, native_file: dict[str, object], authorization: str
    ) -> None:
        self.calls.append(("attach", (chat_id, message_id, native_file)))

    def delete(self, file_id: str, authorization: str) -> None:
        self.calls.append(("delete", file_id))


def test_load_word_skill_returns_official_executor_output() -> None:
    executor = RecordingOfficeCli()
    client = TestClient(create_app(executor, RecordingOpenWebUi(), settings()))

    response = client.post(
        "/v1/officecli/skills/load",
        headers={"Authorization": "Bearer user-session"},
        json={"skill": "word"},
    )

    assert response.status_code == 200
    assert response.json()["content"] == "official load_skill word output"
    assert executor.calls == [("load_skill", "word")]


def test_openapi_exposes_only_the_proof_operations() -> None:
    client = TestClient(create_app(RecordingOfficeCli(), RecordingOpenWebUi(), settings()))

    schema = client.get("/openapi.json").json()

    operations = {
        schema["paths"][path]["post"]["operationId"]
        for path in schema["paths"]
        if "post" in schema["paths"][path]
    }
    assert operations == {
        "load_officecli_skill",
        "get_officecli_help",
        "inspect_office_document",
        "apply_office_batch",
    }


def test_help_uses_only_a_whitelisted_official_topic() -> None:
    executor = RecordingOfficeCli()
    client = TestClient(create_app(executor, RecordingOpenWebUi(), settings()))

    response = client.post(
        "/v1/officecli/help",
        headers={"Authorization": "Bearer user-session"},
        json={"topic": "docx set paragraph"},
    )

    assert response.status_code == 200
    assert executor.calls == [("help", "docx", "set", "paragraph")]
    rejected = client.post(
        "/v1/officecli/help",
        headers={"Authorization": "Bearer user-session"},
        json={"topic": "docx; rm -rf /"},
    )
    assert rejected.status_code == 422
    assert executor.calls == [("help", "docx", "set", "paragraph")]


def test_guidance_requires_the_forwarded_openwebui_session() -> None:
    executor = RecordingOfficeCli()
    client = TestClient(create_app(executor, RecordingOpenWebUi(), settings()))

    response = client.post("/v1/officecli/skills/load", json={"skill": "word"})

    assert response.status_code == 401
    assert executor.calls == []


def test_inspect_downloads_native_file_and_only_runs_annotated_view() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/inspect",
        headers={"Authorization": "Bearer user-session"},
        json={"file_id": "source-file-id", "command_payload": {"command": "view", "mode": "annotated"}},
    )

    assert response.status_code == 200
    assert response.json()["officecli_result"] == {"success": True, "data": {"operation": "view"}}
    assert files.calls == [("download", "source-file-id")]
    assert executor.calls[0][0] == "view"
    assert executor.calls[0][2:] == ("annotated", "--json")


def test_apply_uses_native_file_result_and_preserves_source_bytes() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/apply-batch",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={
            "file_id": "source-file-id",
            "output_name": "document-updated.docx",
            "commands": [{"command": "set", "path": "/body/p[1]", "props": {"text": "updated"}}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result_file_id"] == "result-file-id"
    assert body["source_bytes_preserved"] is True
    assert body["bounded_processes_completed"] is True
    assert [call[0] for call in files.calls] == ["download", "download", "upload", "attach"]
    assert [call[0] for call in executor.calls] == ["batch", "validate"]
    assert executor.calls[0][0] == "batch"
    assert "--stop-on-error" in executor.calls[0]
    assert executor.inputs[0] == '[{"command":"set","path":"/body/p[1]","props":{"text":"updated"}}]'
    assert files.source == b"original DOCX bytes"


def test_apply_requires_native_chat_and_message_identifiers_before_side_effects() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/apply-batch",
        headers={"Authorization": "Bearer user-session"},
        json={"file_id": "source-file-id", "output_name": "document-updated.docx", "commands": [{"command": "set"}]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "native chat and message ids are required"
    assert executor.calls == []
    assert files.calls == []


def test_apply_stops_before_upload_when_officecli_reports_failure() -> None:
    executor = RecordingOfficeCli(batch_success=False)
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/apply-batch",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={"file_id": "source-file-id", "output_name": "document-updated.docx", "commands": [{"command": "set"}]},
    )

    assert response.status_code == 502
    assert [call[0] for call in files.calls] == ["download"]
    assert [call[0] for call in executor.calls] == ["batch"]


def test_subprocess_executor_disables_auto_resident_for_official_commands(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = "official skill"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        captured["shell"] = kwargs.get("shell", False)
        return Completed()

    monkeypatch.setattr("officecli_openapi_proof.officecli.subprocess.run", fake_run)
    executor = SubprocessOfficeCliExecutor(settings())

    result = executor.run("load_skill", "word")

    assert captured["command"] == ("/usr/local/bin/officecli", "load_skill", "word")
    assert captured["shell"] is False
    assert captured["environment"]["OFFICECLI_SKIP_UPDATE"] == "1"
    assert captured["environment"]["OFFICECLI_NO_AUTO_RESIDENT"] == "1"
    assert result.text == "official skill"


def settings() -> Settings:
    return Settings(
        binary="/usr/local/bin/officecli",
        timeout_seconds=30,
        expected_version="1.0.148",
        openwebui_base_url="http://openwebui:8080",
    )
