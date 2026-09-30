"""Observable transport behavior, independent of task-specific prompt recipes."""

from dataclasses import replace
import json
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from officecli_openapi_proof.app import create_app
from officecli_openapi_proof.discovery import ObjectReadPayload, bounded_result
from officecli_openapi_proof.officecli import SubprocessOfficeCliExecutor, OfficeCliFailure
from test_guidance_routes import RecordingOfficeCli, RecordingOpenWebUi, settings, office_output


HEADERS = {"Authorization": "Bearer synthetic", "X-OpenWebUI-Chat-Id": "chat",
           "X-OpenWebUI-Message-Id": "message"}


def test_workflow_uses_installed_tool_description_without_a_local_rewrite():
    official = "Installed author instructions, including a newly added capability."

    class ToolCatalog(RecordingOfficeCli):
        def run(self, *arguments, input_text=None):
            assert arguments == ("mcp",)
            assert json.loads(input_text)["method"] == "tools/list"
            return office_output(*arguments, payload={"result": {"tools": [
                {"name": "officecli", "description": official}]}})

    files = RecordingOpenWebUi()
    response = TestClient(create_app(ToolCatalog(), files, settings())).post(
        "/v1/officecli/help", headers=HEADERS, json={})
    assert response.status_code == 200, response.text
    assert response.json()["content"] == official
    assert files.calls == []

    client = TestClient(create_app(ToolCatalog(), files, settings()))
    schema = client.get("/openapi.json").json()
    descriptions = [operation.get("description", "") for path in schema["paths"].values()
                    for operation in path.values() if isinstance(operation, dict)]
    assert sum(description.count(official) for description in descriptions) == 1
    assert official in schema["paths"]["/v1/officecli/help"]["post"]["description"]
    assert "native file_id" in schema["paths"]["/v1/officecli/help"]["post"]["description"]
    assert files.calls == []


def test_schema_does_not_advertise_tools_without_the_official_workflow():
    class BrokenCatalog(RecordingOfficeCli):
        def run(self, *arguments, input_text=None):
            return office_output(*arguments, payload={"result": {"tools": []}})

    app = create_app(BrokenCatalog(), RecordingOpenWebUi(), settings())
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 502
    assert app.openapi_schema is None


def test_all_sheet_names_remain_recoverable_in_order():
    names = [f"Sheet {i}" for i in range(537)]
    native = {"success": True, "data": {"sheets": [{"name": name, "rows": 10} for name in names]}}
    offset, recovered = 0, []
    while offset is not None:
        result = bounded_result(native, ObjectReadPayload(command="view", offset=offset))
        recovered.extend(s["name"] for s in result["data"]["sheets"])
        offset = result["pagination"]["next_offset"]
    assert recovered == names
    assert native["data"]["sheets"] == [{"name": name, "rows": 10} for name in names]


@pytest.mark.parametrize("kind", ["documents", "spreadsheets", "presentations"])
def test_native_view_bounds_are_forwarded_for_each_format(kind):
    cli, files = RecordingOfficeCli(), RecordingOpenWebUi()
    response = TestClient(create_app(cli, files, settings())).post(
        f"/v1/officecli/{kind}/inspect", headers=HEADERS,
        json={"file_id": "source", "command_payload": {"command": "view",
            "mode": "annotated", "start": 2, "end": 4, "max_lines": 3}})
    assert response.status_code == 200, response.text
    assert cli.calls[0][2:] == ("annotated", "--json", "--start", "2", "--end", "4", "--max-lines", "3")
    assert files.calls == [("download", "source")]


def test_successful_process_preserves_stderr_without_corrupting_json():
    executor = SubprocessOfficeCliExecutor(replace(settings(), binary=sys.executable))
    result = executor.run("-c", "import sys; print('{\"success\":true}'); print('native warning',file=sys.stderr)")
    assert json.loads(result.text) == {"success": True}
    assert result.diagnostics == "native warning"


def test_failed_process_preserves_both_diagnostic_streams():
    executor = SubprocessOfficeCliExecutor(replace(settings(), binary=sys.executable))
    with pytest.raises(OfficeCliFailure) as error:
        executor.run("-c", "import sys; print('native result'); print('native error',file=sys.stderr);sys.exit(1)")
    assert "native result" in str(error.value) and "native error" in str(error.value)


def test_failed_native_validation_remains_readable_as_structured_findings(monkeypatch):
    payload = {"success": False, "warnings": [{"message": "[Semantic] Missing image relationship"}]}

    def failed_validation(command, **kwargs):
        assert command[1] == "validate"
        return subprocess.CompletedProcess(command, 1, json.dumps(payload), "")

    monkeypatch.setattr("officecli_openapi_proof.officecli.subprocess.run", failed_validation)
    executor = SubprocessOfficeCliExecutor(settings())

    result = executor.run("validate", "source.pptx", "--json")
    assert json.loads(result.text) == payload


def test_docx_apply_receives_exact_original_bytes_without_a_repair_pass():
    class InspectingCli(RecordingOfficeCli):
        def run(self, *arguments, input_text=None):
            if arguments[0] == "batch":
                from pathlib import Path
                assert Path(arguments[1]).read_bytes() == original
            return super().run(*arguments, input_text=input_text)

    original = b"source bytes are owned by the user"
    files = RecordingOpenWebUi(source=original)
    response = TestClient(create_app(InspectingCli(), files, settings())).post(
        "/v1/officecli/documents/apply-batch", headers=HEADERS,
        json={"file_id": "source", "output_name": "result.docx", "commands": [{"command": "set"}]})
    assert response.status_code == 200, response.text
    assert files.source == original
    assert files.uploaded_bytes == b"changed DOCX bytes"
