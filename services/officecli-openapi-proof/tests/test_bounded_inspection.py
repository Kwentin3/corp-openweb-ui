"""Native source reads must not expand a large workbook into the model context."""

from fastapi.testclient import TestClient

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


def test_large_output_is_explicitly_withheld_not_presented_as_complete():
    class LargeResult(RecordingOfficeCli):
        def run(self, *arguments, input_text=None):
            return office_output(*arguments, payload={"success": True, "data": "private-value" * 5000})

    response = TestClient(create_app(LargeResult(), RecordingOpenWebUi(), settings())).post(
        ROUTE, headers=HEADERS,
        json={"file_id": "source-id", "command_payload": {"mode": "annotated"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "source-id"
    assert data["officecli_result"]["content_included"] is False
    assert data["officecli_result"]["reason"] == "inspection_exceeds_context_budget"
    assert "private-value" not in response.text
    assert len(response.content) < 1500


def test_unscoped_text_is_rejected_before_cli_execution():
    executor = RecordingOfficeCli()
    response = TestClient(create_app(executor, RecordingOpenWebUi(), settings())).post(
        ROUTE, headers=HEADERS, json={"command_payload": {"mode": "text"}}
    )
    assert response.status_code == 422
    assert executor.calls == []
