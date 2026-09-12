from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
import httpx
import pytest

from officecli_openapi_proof.app import _normalize_zero_dpi_page_setup, create_app
from officecli_openapi_proof.config import Settings
from officecli_openapi_proof.officecli import OfficeCliOutput, SubprocessOfficeCliExecutor
from officecli_openapi_proof.openwebui_client import (
    HttpOpenWebUiClient,
    OpenWebUiAmbiguousAttachment,
    OpenWebUiUnauthorized,
)


XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


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
        if arguments[0] == "create":
            Path(arguments[1]).write_bytes(b"new DOCX bytes")
            return office_output(*arguments, payload={"success": True, "data": {"operation": "create"}})
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
    upload_content_types: list[str] = field(default_factory=list)
    attachment_content_types: list[str] = field(default_factory=list)

    def verify_session(self, authorization: str) -> None:
        return None
    uploaded_bytes: bytes | None = None

    def resolve_nearest_docx_attachment(self, chat_id: str, message_id: str, authorization: str) -> str:
        self.calls.append(("resolve", (chat_id, message_id)))
        return "resolved-file-id"

    def resolve_nearest_xlsx_attachment(self, chat_id: str, message_id: str, authorization: str) -> str:
        self.calls.append(("resolve-xlsx", (chat_id, message_id)))
        return "resolved-xlsx-file-id"

    def resolve_nearest_pptx_attachment(self, chat_id: str, message_id: str, authorization: str) -> str:
        self.calls.append(("resolve-pptx", (chat_id, message_id)))
        return "resolved-pptx-file-id"

    def download(self, file_id: str, authorization: str, destination: Path) -> None:
        self.calls.append(("download", file_id))
        destination.write_bytes(self.source)

    def upload(
        self,
        source: Path,
        output_name: str,
        authorization: str,
        content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) -> dict[str, object]:
        self.calls.append(("upload", output_name))
        self.upload_content_types.append(content_type)
        self.uploaded_bytes = source.read_bytes()
        self.uploaded = {"id": "result-file-id", "filename": output_name}
        return self.uploaded

    def attach(
        self,
        chat_id: str,
        message_id: str,
        native_file: dict[str, object],
        authorization: str,
        fallback_name: str = "updated.docx",
        content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) -> None:
        self.calls.append(("attach", (chat_id, message_id, native_file)))
        self.attachment_content_types.append(content_type)

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


def test_invalid_explicit_file_id_does_not_fall_back_to_message_ancestry() -> None:
    files = RecordingOpenWebUi()
    client = TestClient(create_app(RecordingOfficeCli(), files, settings()))

    response = client.post(
        "/v1/officecli/documents/inspect",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat",
            "X-OpenWebUI-Message-Id": "assistant-now",
        },
        json={"file_id": "__UNKNOWN__", "command_payload": {"command": "view", "mode": "annotated"}},
    )

    assert response.status_code == 422
    assert files.calls == []


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
        "inspect_office_spreadsheet",
        "inspect_office_presentation",
        "apply_office_batch",
        "create_office_document",
        "create_office_spreadsheet",
        "apply_office_spreadsheet_batch",
        "create_office_presentation",
        "apply_office_presentation_batch",
    }
    assert "final execution operation" in schema["paths"]["/v1/officecli/documents/apply-batch"]["post"][
        "description"
    ]
    assert "bare verb" in schema["components"]["schemas"]["ApplyOfficeBatchRequest"]["properties"][
        "commands"
    ]["description"]


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


def test_help_exposes_official_markdown_creation_guidance() -> None:
    executor = RecordingOfficeCli()
    client = TestClient(create_app(executor, RecordingOpenWebUi(), settings()))

    response = client.post(
        "/v1/officecli/help",
        headers={"Authorization": "Bearer user-session"},
        json={"topic": "docx add markdown"},
    )

    assert response.status_code == 200
    assert executor.calls == [("help", "docx", "add", "markdown")]


@pytest.mark.parametrize(
    ("topic", "arguments"),
    [
        ("docx table-row", ("help", "docx", "table-row")),
        ("docx table-cell", ("help", "docx", "table-cell")),
    ],
)
def test_help_exposes_official_table_edit_guidance(topic: str, arguments: tuple[str, ...]) -> None:
    executor = RecordingOfficeCli()
    client = TestClient(create_app(executor, RecordingOpenWebUi(), settings()))

    response = client.post(
        "/v1/officecli/help",
        headers={"Authorization": "Bearer user-session"},
        json={"topic": topic},
    )

    assert response.status_code == 200
    assert executor.calls == [arguments]


def test_guidance_requires_the_forwarded_openwebui_session() -> None:
    executor = RecordingOfficeCli()
    client = TestClient(create_app(executor, RecordingOpenWebUi(), settings()))

    response = client.post("/v1/officecli/skills/load", json={"skill": "word"})

    assert response.status_code == 401
    assert executor.calls == []


def test_fake_bearer_cannot_reach_officecli_guidance_or_execution() -> None:
    class RejectingOpenWebUi(RecordingOpenWebUi):
        def verify_session(self, authorization: str) -> None:
            assert authorization == "Bearer fake-session"
            raise OpenWebUiUnauthorized("forwarded OpenWebUI session was rejected")

    executor = RecordingOfficeCli()
    files = RejectingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    guidance = client.post(
        "/v1/officecli/skills/load",
        headers={"Authorization": "Bearer fake-session"},
        json={"skill": "word"},
    )
    execution = client.post(
        "/v1/officecli/documents/apply-batch",
        headers={
            "Authorization": "Bearer fake-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={"output_name": "document-updated.docx", "commands": [{"command": "set"}]},
    )

    assert guidance.status_code == 401
    assert guidance.json() == {"detail": "forwarded OpenWebUI session was rejected"}
    assert execution.status_code == 401
    assert execution.json() == {"detail": "forwarded OpenWebUI session was rejected"}
    assert executor.calls == []
    assert files.calls == []


def test_inspect_downloads_native_file_and_only_runs_annotated_view() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/inspect",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={"command_payload": {"command": "view", "mode": "annotated"}},
    )

    assert response.status_code == 200
    assert response.json()["officecli_result"] == {"success": True, "data": {"operation": "view"}}
    assert response.json()["file_id"] == "resolved-file-id"
    assert files.calls == [("resolve", ("native-chat-id", "native-message-id")), ("download", "resolved-file-id")]
    assert executor.calls[0][0] == "view"
    assert executor.calls[0][2:] == ("annotated", "--json")


def test_inspect_spreadsheet_resolves_only_xlsx_and_runs_annotated_view() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/spreadsheets/inspect",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={"command_payload": {"command": "view", "mode": "annotated"}},
    )

    assert response.status_code == 200
    assert response.json()["file_id"] == "resolved-xlsx-file-id"
    assert files.calls == [
        ("resolve-xlsx", ("native-chat-id", "native-message-id")),
        ("download", "resolved-xlsx-file-id"),
    ]
    assert executor.calls[0][0] == "view"
    assert executor.calls[0][1].endswith("source.xlsx")
    assert executor.calls[0][2:] == ("annotated", "--json")


def test_inspect_presentation_resolves_only_pptx_and_runs_outline_view() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/presentations/inspect",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={"command_payload": {"command": "view", "mode": "outline"}},
    )

    assert response.status_code == 200
    assert response.json()["file_id"] == "resolved-pptx-file-id"
    assert files.calls == [
        ("resolve-pptx", ("native-chat-id", "native-message-id")),
        ("download", "resolved-pptx-file-id"),
    ]
    assert executor.calls[0][1].endswith("source.pptx")
    assert executor.calls[0][2:] == ("outline", "--json")


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
            "output_name": "document-updated.docx",
            "commands": [{"command": "set", "path": "/body/p[1]", "props": {"text": "updated"}}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result_file_id"] == "result-file-id"
    assert body["source_bytes_preserved"] is True
    assert body["bounded_processes_completed"] is True
    assert body["source_file_id"] == "resolved-file-id"
    assert [call[0] for call in files.calls] == ["resolve", "download", "download", "upload", "attach"]
    assert [call[0] for call in executor.calls] == ["batch", "validate"]
    assert executor.calls[0][0] == "batch"
    assert "--stop-on-error" in executor.calls[0]
    assert executor.inputs[0] == '[{"command":"set","path":"/body/p[1]","props":{"text":"updated"}}]'
    assert files.source == b"original DOCX bytes"
    assert files.uploaded_bytes == b"changed DOCX bytes"


def test_apply_keeps_internal_paths_distinct_from_output_name() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi(source=b"source DOCX bytes")
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/apply-batch",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={
            "output_name": "source-after.docx",
            "commands": [{"command": "set", "path": "/body/p[1]", "props": {"text": "updated"}}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert files.uploaded == {"id": "result-file-id", "filename": "source-after.docx"}
    assert files.uploaded_bytes == b"changed DOCX bytes"
    assert files.uploaded_bytes != files.source
    assert body["result_sha256"] == sha256(files.uploaded_bytes).hexdigest()
    assert body["source_sha256"] == sha256(files.source).hexdigest()
    assert body["source_bytes_preserved"] is True


def test_apply_requires_native_chat_and_message_identifiers_before_side_effects() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/apply-batch",
        headers={"Authorization": "Bearer user-session"},
        json={"output_name": "document-updated.docx", "commands": [{"command": "set"}]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "native chat and message ids are required"
    assert executor.calls == []
    assert files.calls == []


def test_create_uses_official_create_batch_validate_and_native_attachment() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/create",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "assistant-now",
        },
        json={
            "output_name": "commercial-proposal.docx",
            "commands": [
                {
                    "command": "add",
                    "parent": "/body",
                    "type": "markdown",
                    "props": {"markdown": "# Commercial proposal\\n\\n- Scope"},
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result_file_id"] == "result-file-id"
    assert body["bounded_processes_completed"] is True
    assert [call[0] for call in executor.calls] == ["create", "batch", "validate"]
    assert executor.calls[0][2:] == ("--locale", "en-US", "--json")
    assert executor.inputs[1] == json.dumps(
        [
            {
                "command": "add",
                "parent": "/body",
                "type": "markdown",
                "props": {"markdown": "# Commercial proposal\\n\\n- Scope"},
            }
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert [call[0] for call in files.calls] == ["upload", "attach"]
    assert files.uploaded_bytes == b"changed DOCX bytes"


def test_create_spreadsheet_uses_official_create_batch_validate_and_xlsx_mime() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/spreadsheets/create",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "assistant-now",
        },
        json={
            "output_name": "commercial-calculation.xlsx",
            "commands": [
                {
                    "command": "set",
                    "sheet": "Sheet1",
                    "range": "A1",
                    "props": {"value": "Amount"},
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["result_file_id"] == "result-file-id"
    assert response.json()["bounded_processes_completed"] is True
    assert [call[0] for call in executor.calls] == ["create", "batch", "validate"]
    assert executor.calls[0][1].endswith("created.xlsx")
    assert executor.inputs[1] == json.dumps(
        [
            {
                "command": "set",
                "sheet": "Sheet1",
                "range": "A1",
                "props": {"value": "Amount"},
            }
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert [call[0] for call in files.calls] == ["upload", "attach"]
    assert files.upload_content_types == [XLSX_CONTENT_TYPE]
    assert files.attachment_content_types == [XLSX_CONTENT_TYPE]


def test_create_spreadsheet_removes_untouched_default_sheet() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/spreadsheets/create",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "assistant-now",
        },
        json={
            "output_name": "commercial-calculation.xlsx",
            "commands": [
                {
                    "command": "add",
                    "parent": "/",
                    "type": "sheet",
                    "props": {"name": "Data"},
                },
                {
                    "command": "add",
                    "parent": "/",
                    "type": "sheet",
                    "props": {"name": "Summary"},
                },
                {
                    "command": "set",
                    "sheet": "Data",
                    "range": "A1",
                    "props": {"value": "Amount"},
                },
            ],
        },
    )

    assert response.status_code == 200
    assert executor.inputs[1] == json.dumps(
        [
            {
                "command": "add",
                "parent": "/",
                "type": "sheet",
                "props": {"name": "Data"},
            },
            {
                "command": "add",
                "parent": "/",
                "type": "sheet",
                "props": {"name": "Summary"},
            },
            {
                "command": "set",
                "sheet": "Data",
                "range": "A1",
                "props": {"value": "Amount"},
            },
            {"command": "remove", "path": "/Sheet1"},
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def test_create_presentation_uses_official_create_batch_validate_and_pptx_mime() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/presentations/create",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={
            "output_name": "commercial-proposal.pptx",
            "commands": [
                {"command": "add", "parent": "/", "type": "slide", "props": {"layout": "blank"}},
            ],
        },
    )

    assert response.status_code == 200
    assert [call[0] for call in executor.calls] == ["create", "batch", "validate"]
    assert executor.calls[0][1].endswith("created.pptx")
    assert files.upload_content_types == [PPTX_CONTENT_TYPE]
    assert files.attachment_content_types == [PPTX_CONTENT_TYPE]


def test_apply_spreadsheet_uses_xlsx_ancestry_preserves_source_and_attaches_xlsx() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi(source=b"original XLSX bytes")
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/spreadsheets/apply-batch",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={
            "output_name": "commercial-calculation-updated.xlsx",
            "commands": [
                {
                    "command": "set",
                    "sheet": "Sheet1",
                    "range": "B2",
                    "props": {"value": 350},
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_file_id"] == "resolved-xlsx-file-id"
    assert body["source_bytes_preserved"] is True
    assert body["bounded_processes_completed"] is True
    assert [call[0] for call in files.calls] == [
        "resolve-xlsx",
        "download",
        "download",
        "upload",
        "attach",
    ]
    assert [call[0] for call in executor.calls] == ["batch", "validate"]
    assert executor.calls[0][1].endswith("result.xlsx")
    assert files.source == b"original XLSX bytes"
    assert files.uploaded_bytes is not None
    assert files.uploaded_bytes != files.source
    assert files.upload_content_types == [XLSX_CONTENT_TYPE]
    assert files.attachment_content_types == [XLSX_CONTENT_TYPE]


def test_apply_presentation_uses_pptx_ancestry_preserves_source_and_attaches_pptx() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi(source=b"original PPTX bytes")
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/presentations/apply-batch",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={
            "output_name": "commercial-proposal-updated.pptx",
            "commands": [
                {
                    "command": "set",
                    "path": "/slide[1]/shape[1]",
                    "props": {"text": "Updated"},
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["source_file_id"] == "resolved-pptx-file-id"
    assert response.json()["source_bytes_preserved"] is True
    assert [call[0] for call in files.calls] == [
        "resolve-pptx",
        "download",
        "download",
        "upload",
        "attach",
    ]
    assert executor.calls[0][1].endswith("result.pptx")
    assert files.upload_content_types == [PPTX_CONTENT_TYPE]
    assert files.attachment_content_types == [PPTX_CONTENT_TYPE]


def test_normalize_zero_dpi_page_setup_only_changes_private_xlsx_copy(tmp_path) -> None:
    workbook = tmp_path / "office-generated.xlsx"
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet><pageSetup horizontalDpi="0" verticalDpi="0"/></worksheet>',
        )
        archive.writestr("xl/worksheets/sheet2.xml", "<worksheet/>")

    assert _normalize_zero_dpi_page_setup(workbook) is True

    with ZipFile(workbook) as archive:
        assert archive.read("xl/worksheets/sheet1.xml") == (
            b'<worksheet><pageSetup horizontalDpi="600" verticalDpi="600"/></worksheet>'
        )
        assert archive.read("xl/worksheets/sheet2.xml") == b"<worksheet/>"


def test_normalize_zero_dpi_page_setup_leaves_normal_workbook_untouched(tmp_path) -> None:
    workbook = tmp_path / "already-valid.xlsx"
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet><pageSetup horizontalDpi="600" verticalDpi="600"/></worksheet>',
        )

    original = workbook.read_bytes()
    assert _normalize_zero_dpi_page_setup(workbook) is False
    assert workbook.read_bytes() == original


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/v1/officecli/spreadsheets/create",
            {"output_name": "not-a-workbook.docx", "commands": [{"command": "set"}]},
        ),
        (
            "/v1/officecli/spreadsheets/apply-batch",
            {"output_name": "not-a-workbook.docx", "commands": [{"command": "set"}]},
        ),
    ],
)
def test_spreadsheet_operations_reject_non_xlsx_output_before_side_effects(
    path: str, payload: dict[str, object]
) -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        path,
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json=payload,
    )

    assert response.status_code == 422
    assert "plain .xlsx filename" in response.text
    assert executor.calls == []
    assert files.calls == []


def test_create_translates_official_help_prop_spelling_before_batch_execution() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/create",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "assistant-now",
        },
        json={
            "output_name": "commercial-proposal.docx",
            "commands": [
                {
                    "command": "add",
                    "parent": "/body",
                    "type": "paragraph",
                    "prop": {"text": "Commercial proposal"},
                }
            ],
        },
    )

    assert response.status_code == 200
    assert executor.inputs[1] == json.dumps(
        [
            {
                "command": "add",
                "parent": "/body",
                "type": "paragraph",
                "props": {"text": "Commercial proposal"},
            }
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def test_create_rejects_ambiguous_prop_and_props_before_creating_a_document() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/create",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "assistant-now",
        },
        json={
            "output_name": "commercial-proposal.docx",
            "commands": [
                {
                    "command": "add",
                    "parent": "/body",
                    "type": "paragraph",
                    "prop": {"text": "singular"},
                    "props": {"text": "plural"},
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "either prop or props" in response.text
    assert executor.calls == []
    assert files.calls == []


def test_create_requires_native_chat_and_message_identifiers_before_side_effects() -> None:
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))

    response = client.post(
        "/v1/officecli/documents/create",
        headers={"Authorization": "Bearer user-session"},
        json={"output_name": "commercial-proposal.docx", "commands": [{"command": "add"}]},
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
        json={"output_name": "document-updated.docx", "commands": [{"command": "set"}]},
    )

    assert response.status_code == 502
    assert [call[0] for call in files.calls] == ["resolve", "download"]
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


def test_http_client_resolves_docx_from_the_native_message_ancestry(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "chat": {
                    "history": {
                        "messages": {
                            "assistant-now": {"parentId": "user-followup", "files": []},
                            "user-followup": {"parentId": "assistant-prior", "files": []},
                            "assistant-prior": {
                                "parentId": "user-source",
                                "files": [{"id": "result-file-id", "name": "first-edit.docx"}],
                            },
                            "user-source": {
                                "parentId": None,
                                "files": [{"id": "source-file-id", "name": "source.docx"}],
                            },
                        }
                    }
                }
            }

    def request(method, url, **kwargs):
        assert method == "GET"
        assert url == "http://openwebui:8080/api/v1/chats/native-chat-id"
        assert kwargs["headers"] == {"Authorization": "Bearer user-session"}
        return Response()

    monkeypatch.setattr("officecli_openapi_proof.openwebui_client.httpx.request", request)
    client = HttpOpenWebUiClient("http://openwebui:8080", 30)

    result = client.resolve_nearest_docx_attachment(
        "native-chat-id", "assistant-now", "Bearer user-session"
    )

    assert result == "result-file-id"


def test_http_client_resolves_xlsx_from_native_ancestry_without_selecting_docx(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "chat": {
                    "history": {
                        "messages": {
                            "assistant-now": {"parentId": "user-followup", "files": []},
                            "user-followup": {
                                "parentId": "assistant-prior",
                                "files": [{"id": "word-file-id", "name": "proposal.docx"}],
                            },
                            "assistant-prior": {
                                "parentId": None,
                                "files": [{"id": "workbook-file-id", "name": "budget.xlsx"}],
                            },
                        }
                    }
                }
            }

    def request(method, url, **kwargs):
        assert method == "GET"
        assert url == "http://openwebui:8080/api/v1/chats/native-chat-id"
        assert kwargs["headers"] == {"Authorization": "Bearer user-session"}
        return Response()

    monkeypatch.setattr("officecli_openapi_proof.openwebui_client.httpx.request", request)
    client = HttpOpenWebUiClient("http://openwebui:8080", 30)

    result = client.resolve_nearest_xlsx_attachment(
        "native-chat-id", "assistant-now", "Bearer user-session"
    )

    assert result == "workbook-file-id"


def test_http_client_rejects_multiple_docx_attachments_in_nearest_native_message(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "chat": {
                    "history": {
                        "messages": {
                            "assistant-now": {
                                "parentId": None,
                                "files": [
                                    {"id": "first-file-id", "name": "first.docx"},
                                    {"id": "second-file-id", "name": "second.docx"},
                                ],
                            }
                        }
                    }
                }
            }

    def request(method, url, **kwargs):
        assert method == "GET"
        assert url == "http://openwebui:8080/api/v1/chats/native-chat-id"
        assert kwargs["headers"] == {"Authorization": "Bearer user-session"}
        return Response()

    monkeypatch.setattr("officecli_openapi_proof.openwebui_client.httpx.request", request)
    client = HttpOpenWebUiClient("http://openwebui:8080", 30)

    with pytest.raises(OpenWebUiAmbiguousAttachment, match="multiple DOCX attachments"):
        client.resolve_nearest_docx_attachment("native-chat-id", "assistant-now", "Bearer user-session")


def test_inspect_returns_422_before_download_when_docx_source_is_ambiguous() -> None:
    class AmbiguousFiles(RecordingOpenWebUi):
        def resolve_nearest_docx_attachment(self, chat_id: str, message_id: str, authorization: str) -> str:
            self.calls.append(("resolve", (chat_id, message_id)))
            raise OpenWebUiAmbiguousAttachment("multiple DOCX attachments exist in the nearest native message; use an explicit file_id")

    files = AmbiguousFiles()
    client = TestClient(create_app(RecordingOfficeCli(), files, settings()))

    response = client.post(
        "/v1/officecli/documents/inspect",
        headers={
            "Authorization": "Bearer user-session",
            "X-OpenWebUI-Chat-Id": "native-chat-id",
            "X-OpenWebUI-Message-Id": "native-message-id",
        },
        json={"command_payload": {"command": "view", "mode": "annotated"}},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "multiple DOCX attachments exist in the nearest native message; use an explicit file_id"
    assert files.calls == [("resolve", ("native-chat-id", "native-message-id"))]


def test_http_client_uses_native_openwebui_session_endpoint_and_rejects_fake_bearer(monkeypatch) -> None:
    requested: list[tuple[str, str, dict[str, object]]] = []

    def request(method, url, **kwargs):
        requested.append((method, url, kwargs))
        response = httpx.Response(401, request=httpx.Request(method, url))
        raise httpx.HTTPStatusError("Unauthorized", request=response.request, response=response)

    monkeypatch.setattr("officecli_openapi_proof.openwebui_client.httpx.request", request)
    client = HttpOpenWebUiClient("http://openwebui:8080", 30)

    with pytest.raises(OpenWebUiUnauthorized):
        client.verify_session("Bearer fake-session")

    assert requested == [
        (
            "GET",
            "http://openwebui:8080/api/v1/auths/",
            {
                "headers": {"Authorization": "Bearer fake-session"},
                "timeout": 30,
                "follow_redirects": False,
            },
        )
    ]


def test_http_client_attaches_a_native_chat_file_reference(monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

    def request(method, url, **kwargs):
        captured.append({"method": method, "url": url, **kwargs})
        return Response()

    monkeypatch.setattr("officecli_openapi_proof.openwebui_client.httpx.request", request)
    client = HttpOpenWebUiClient("http://openwebui:8080", 30)

    client.attach(
        "native-chat-id",
        "assistant-now",
        {
            "id": "result-file-id",
            "filename": "updated.docx",
            "meta": {
                "size": 123,
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            },
        },
        "Bearer user-session",
    )

    assert [request["method"] for request in captured] == ["POST", "POST"]
    assert [request["url"] for request in captured] == [
        "http://openwebui:8080/api/v1/chats/native-chat-id/messages/assistant-now/event",
        "http://openwebui:8080/api/v1/chats/native-chat-id/messages/assistant-now/event",
    ]
    assert [request["headers"] for request in captured] == [
        {"Authorization": "Bearer user-session"},
        {"Authorization": "Bearer user-session"},
    ]
    expected_data = {
        "data": {
            "files": [
                {
                    "type": "file",
                    "file": {
                        "id": "result-file-id",
                        "filename": "updated.docx",
                        "meta": {
                            "size": 123,
                            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        },
                    },
                    "id": "result-file-id",
                    "url": "result-file-id",
                    "name": "updated.docx",
                    "status": "uploaded",
                    "size": 123,
                    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }
            ]
        },
    }
    assert captured[0]["json"] == {"type": "files", **expected_data}
    assert captured[1]["json"] == {"type": "chat:message:files", **expected_data}


def settings() -> Settings:
    return Settings(
        binary="/usr/local/bin/officecli",
        timeout_seconds=30,
        expected_version="1.0.148",
        openwebui_base_url="http://openwebui:8080",
    )
