"""Expose the upstream lazy skill workflow without executing arbitrary CLI input."""

import pytest
from io import BytesIO
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from officecli_openapi_proof.app import create_app
from test_guidance_routes import RecordingOfficeCli, RecordingOpenWebUi, office_output, settings


HEADERS = {"Authorization": "Bearer session"}


@pytest.mark.parametrize("payload,args", [
    ({}, ("load_skill",)),
    ({"skill": "word-form"}, ("load_skill", "word-form")),
    ({"skill": "financial-model"}, ("load_skill", "financial-model")),
    ({"skill": "morph-ppt", "path": "reference/INDEX.md"},
     ("load_skill", "morph-ppt", "--path", "reference/INDEX.md")),
])
def test_catalog_specialized_guide_and_reference_are_official(payload, args):
    cli = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    response = TestClient(create_app(cli, files, settings())).post(
        "/v1/officecli/skills/load", headers=HEADERS, json=payload)
    assert response.status_code == 200
    assert response.json()["content"] == "official " + " ".join(args) + " output"
    assert cli.calls == [args]
    assert files.calls == []


@pytest.mark.parametrize("payload", [
    {"skill": "--help"}, {"skill": "word\n--path /etc/passwd"},
    {"skill": "word", "path": "../SKILL.md"},
    {"skill": "word", "path": "/etc/passwd"},
    {"skill": "word", "path": "reference/../SKILL.md"},
    {"skill": "word", "path": "reference\\SKILL.md"},
    {"path": "reference/INDEX.md"},
])
def test_invalid_skill_access_never_reaches_cli(payload):
    cli = RecordingOfficeCli()
    response = TestClient(create_app(cli, RecordingOpenWebUi(), settings())).post(
        "/v1/officecli/skills/load", headers=HEADERS, json=payload)
    assert response.status_code == 422
    assert cli.calls == []


@pytest.mark.parametrize("topic,args", [
    ("help", ("help",)), ("xlsx /", ("help", "xlsx", "/")),
    ("raw-set", ("raw-set", "--help")), ("load_skill", ("load_skill", "--help")),
    ("xlsx set /", ("help", "xlsx", "set", "/")),
    ("future-command", ("help", "future-command")),
])
def test_root_and_fallback_help_are_discoverable(topic, args):
    cli = RecordingOfficeCli()
    response = TestClient(create_app(cli, RecordingOpenWebUi(), settings())).post(
        "/v1/officecli/help", headers=HEADERS, json={"topic": topic})
    assert response.status_code == 200
    assert cli.calls == [args]


@pytest.mark.parametrize("kind", ["documents", "spreadsheets", "presentations"])
@pytest.mark.parametrize("payload,args", [
    ({"command": "view", "mode": "issues"}, ("view", "issues", "--json")),
    ({"command": "view", "mode": "stats"}, ("view", "stats", "--json")),
    ({"command": "validate"}, ("validate", "--json")),
])
def test_authors_readonly_delivery_checks_do_not_publish(kind, payload, args):
    cli = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    response = TestClient(create_app(cli, files, settings())).post(
        f"/v1/officecli/{kind}/inspect",
        headers={**HEADERS, "X-OpenWebUI-Chat-Id": "chat", "X-OpenWebUI-Message-Id": "message"},
        json={"file_id": "final-result", "command_payload": payload})
    assert response.status_code == 200
    assert response.json()["file_id"] == "final-result"
    assert response.json()["officecli_result"]["data"]["operation"] == args[0]
    assert cli.calls[0][0] == args[0]
    assert cli.calls[0][2:] == args[1:]
    assert files.calls == [("download", "final-result")]


def test_screenshot_returns_native_image_without_publishing_another_document():
    class ScreenshotCli(RecordingOfficeCli):
        def run(self, *args, input_text=None):
            if args[0] == "view":
                assert args[2] == "screenshot"
                assert args[-2:] == ("--page", "2")
                Image.new("RGB", (16, 16), "blue").save(Path(args[4]))
            return super().run(*args, input_text=input_text)

    files = RecordingOpenWebUi()
    response = TestClient(create_app(ScreenshotCli(), files, settings())).post(
        "/v1/officecli/render", headers=HEADERS,
        json={"file_id": "result-id", "format": "pptx", "page": 2})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    with Image.open(BytesIO(response.content)) as image:
        assert image.getpixel((0, 0)) == (0, 0, 255)
    assert files.calls == [("download", "result-id")]


def test_missing_screenshot_is_not_a_success_and_releases_the_slot():
    files = RecordingOpenWebUi()
    client = TestClient(create_app(RecordingOfficeCli(), files, settings()))
    for _ in range(2):
        response = client.post("/v1/officecli/render", headers=HEADERS,
            json={"file_id": "result-id", "format": "docx"})
        assert response.status_code == 502
        assert "not visually verified" in response.json()["detail"]
    assert files.calls == [("download", "result-id")] * 2


def test_xlsx_page_is_not_falsely_treated_as_a_sheet_selector():
    files = RecordingOpenWebUi()
    cli = RecordingOfficeCli()
    response = TestClient(create_app(cli, files, settings())).post(
        "/v1/officecli/render", headers=HEADERS,
        json={"file_id": "result-id", "format": "xlsx", "page": 2})
    assert response.status_code == 422
    assert files.calls == cli.calls == []


@pytest.mark.parametrize("kind", ["documents", "spreadsheets", "presentations"])
def test_raw_reads_the_official_part_without_publishing(kind):
    class RawCli(RecordingOfficeCli):
        def run(self, *args, input_text=None):
            self.calls.append(args)
            return office_output(*args, payload={"success": True, "data": {"xml": "<root/>"}})

    cli = RawCli()
    files = RecordingOpenWebUi()
    response = TestClient(create_app(cli, files, settings())).post(
        f"/v1/officecli/{kind}/inspect",
        headers={**HEADERS, "X-OpenWebUI-Chat-Id": "chat", "X-OpenWebUI-Message-Id": "message"},
        json={"file_id": "source", "command_payload": {"command": "raw", "path": "/document"}})
    assert response.status_code == 200
    assert response.json()["officecli_result"]["data"]["xml"] == "<root/>"
    assert cli.calls[0][0] == "raw"
    assert cli.calls[0][2:] == ("/document", "--json")
    assert files.calls == [("download", "source")]


def test_each_mutating_tool_carries_the_upstream_imperative_trigger():
    schema = create_app(RecordingOfficeCli(), RecordingOpenWebUi(), settings()).openapi()
    operations = {op["operationId"]: op for path in schema["paths"].values()
                  for op in path.values() if isinstance(op, dict) and "operationId" in op}
    for name in ("compose_office_spreadsheets", "apply_office_batch", "create_office_document",
                 "create_office_spreadsheet", "apply_office_spreadsheet_batch",
                 "create_office_presentation", "apply_office_presentation_batch"):
        description = operations[name]["description"]
        assert description.startswith("FIRST load_officecli_skill")
        assert "unless already loaded for it" in description
        assert "visual delivery checks" in description
        assert "This is the final execution" not in description


@pytest.mark.parametrize("kind", ["documents", "spreadsheets", "presentations"])
@pytest.mark.parametrize("operation", ["create", "apply-batch"])
def test_published_result_provides_native_download_for_its_actual_attachment(kind, operation):
    files = RecordingOpenWebUi()
    payload = {"output_name": "result." + {"documents": "docx", "spreadsheets": "xlsx", "presentations": "pptx"}[kind],
               "commands": [{"command": "set", "path": "/", "props": {"title": "review"}}]}
    response = TestClient(create_app(RecordingOfficeCli(), files, settings())).post(
        f"/v1/officecli/{kind}/{operation}",
        headers={**HEADERS, "X-OpenWebUI-Chat-Id": "chat", "X-OpenWebUI-Message-Id": "message"},
        json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["result_file_id"] == files.uploaded["id"]
    assert result["download_url"] == f"/api/v1/files/{files.uploaded['id']}/content"
    assert files.uploaded_bytes == b"changed DOCX bytes"
