"""Native source reads must not expand a large workbook into the model context."""

from fastapi.testclient import TestClient
import json

from officecli_openapi_proof.app import create_app
from test_guidance_routes import RecordingOfficeCli, RecordingOpenWebUi, office_output, settings


HEADERS = {
    "Authorization": "Bearer user-session",
    "X-OpenWebUI-Chat-Id": "native-chat",
    "X-OpenWebUI-Message-Id": "assistant-now",
}
ROUTE = "/v1/officecli/spreadsheets/inspect"


def test_default_is_native_outline_and_retains_source_identity():
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    response = TestClient(create_app(executor, files, settings())).post(
        ROUTE, headers=HEADERS, json={"file_id": "source-id"}
    )
    assert response.status_code == 200
    assert response.json()["file_id"] == "source-id"
    assert executor.calls[0][2:] == ("outline", "--json")
    assert files.calls == [("download", "source-id")]


def test_range_is_passed_to_native_cli_without_reading_whole_workbook():
    executor = RecordingOfficeCli()
    response = TestClient(create_app(executor, RecordingOpenWebUi(), settings())).post(
        ROUTE, headers=HEADERS,
        json={"command_payload": {"mode": "text", "range": "Jan 26!A2:F12"}},
    )
    assert response.status_code == 200
    assert executor.calls[0][2:] == ("text", "--json", "--range", "Jan 26!A2:F12")


def test_large_output_is_recoverable_without_publishing_or_losing_content():
    class LargeResult(RecordingOfficeCli):
        def run(self, *arguments, input_text=None):
            return office_output(*arguments, payload={"success": True, "data": "private-value" * 5000})

    files = RecordingOpenWebUi()
    client = TestClient(create_app(LargeResult(), files, settings()))
    offset, parts = 0, []
    while offset is not None:
        response = client.post(ROUTE, headers=HEADERS, json={"file_id": "source-id",
            "command_payload": {"mode": "annotated", "text_offset": offset}})
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == "source-id"
        result = data["officecli_result"]
        assert result["encoding"] == "json-fragment"
        assert result["pagination"]["complete"] is False
        assert len(result["content"]) <= 12000
        parts.append(result["content"])
        offset = result["pagination"]["next_text_offset"]
    assert json.loads("".join(parts)) == {"success": True, "data": "private-value" * 5000}
    assert all(call == ("download", "source-id") for call in files.calls)


def test_unscoped_text_is_rejected_before_cli_execution():
    executor = RecordingOfficeCli()
    response = TestClient(create_app(executor, RecordingOpenWebUi(), settings())).post(
        ROUTE, headers=HEADERS, json={"command_payload": {"mode": "text"}}
    )
    assert response.status_code == 422
    assert executor.calls == []
