"""Previously hidden objects must be discoverable without publishing an edit."""

import pytest
from fastapi.testclient import TestClient

from officecli_openapi_proof.app import create_app
from officecli_openapi_proof.discovery import ObjectReadPayload, bounded_result
from test_guidance_routes import RecordingOfficeCli, RecordingOpenWebUi, office_output, settings

HEADERS = {"Authorization": "Bearer session", "X-OpenWebUI-Chat-Id": "chat",
           "X-OpenWebUI-Message-Id": "message"}


@pytest.mark.parametrize("topic,arguments", [
    ("xlsx picture", ("help", "xlsx", "picture")),
    ("xlsx workbook", ("help", "xlsx", "workbook")),
    ("xlsx remove picture", ("help", "xlsx", "remove", "picture")),
    ("docx abstractNum", ("help", "docx", "abstractNum")),
    ("pptx set connector", ("help", "pptx", "set", "connector")),
    ("xlsx query", ("help", "xlsx", "query")),
    ("query", ("query", "--help")),
    ("get", ("get", "--help")),
    ("xlsx view", ("view", "--help")),
])
def test_help_delegates_discovery_to_installed_cli(topic, arguments):
    executor = RecordingOfficeCli()
    response = TestClient(create_app(executor, RecordingOpenWebUi(), settings())).post(
        "/v1/officecli/help", headers=HEADERS, json={"topic": topic})
    assert response.status_code == 200
    assert executor.calls == [arguments]
    assert response.json()["content"] == executor.run(*arguments).text


@pytest.mark.parametrize("topic", ["xlsx --version", "xlsx picture /tmp/out", "xlsx;remove", "xlsx\npicture", "get /etc/passwd", "xlsx picture --save", "xlsx  picture"])
def test_help_cannot_become_execution_or_file_access(topic):
    executor = RecordingOfficeCli()
    response = TestClient(create_app(executor, RecordingOpenWebUi(), settings())).post(
        "/v1/officecli/help", headers=HEADERS, json={"topic": topic})
    assert response.status_code == 422
    assert executor.calls == []


class PictureInventory(RecordingOfficeCli):
    def run(self, *arguments, input_text=None):
        self.calls.append(arguments)
        return office_output(*arguments, payload={"success": True, "data": {
            "matches": 37, "results": [{"path": f"/ActualSheet/picture[{i}]",
                "type": "picture", "format": {"name": f"Image {i}"}}
                for i in range(1, 38)]}})


@pytest.mark.parametrize("kind", ["documents", "spreadsheets", "presentations"])
def test_query_reads_all_object_paths_in_honest_pages_without_upload(kind):
    executor = PictureInventory()
    files = RecordingOpenWebUi()
    client = TestClient(create_app(executor, files, settings()))
    paths = []
    offset = 0
    while offset is not None:
        response = client.post(f"/v1/officecli/{kind}/inspect", headers=HEADERS,
            json={"file_id": "source", "command_payload": {
                "command": "query", "selector": "picture", "limit": 10, "offset": offset}})
        assert response.status_code == 200
        result = response.json()["officecli_result"]
        assert result["data"]["matches"] == 37
        assert result["pagination"]["total"] == 37
        assert result["pagination"]["complete"] is False
        paths.extend(node["path"] for node in result["data"]["results"])
        offset = result["pagination"]["next_offset"]
    assert paths == [f"/ActualSheet/picture[{i}]" for i in range(1, 38)]
    assert all(call[0] == "query" and call[2:] == ("picture", "--json") for call in executor.calls)
    assert all(call == ("download", "source") for call in files.calls)


@pytest.mark.parametrize("kind", ["documents", "spreadsheets", "presentations"])
def test_get_reads_actual_node_at_requested_depth(kind):
    class NodeOutput(RecordingOfficeCli):
        def run(self, *arguments, input_text=None):
            self.calls.append(arguments)
            return office_output(*arguments, payload={"success": True, "data": {"path": "/"}})

    executor = NodeOutput()
    files = RecordingOpenWebUi()
    response = TestClient(create_app(executor, files, settings())).post(
        f"/v1/officecli/{kind}/inspect", headers=HEADERS, json={"file_id": "result-id",
            "command_payload": {"command": "get", "path": "/", "depth": 0}})
    assert response.status_code == 200
    assert executor.calls[0][0] == "get"
    assert executor.calls[0][2:] == ("/", "--depth", "0", "--json")
    assert files.calls == [("download", "result-id")]


@pytest.mark.parametrize("payload", [
    {"command": "remove", "path": "/"}, {"command": "query"},
    {"command": "get", "path": "--save"}, {"command": "get", "path": "/", "depth": 3},
    {"command": "query", "selector": "picture", "limit": 101},
])
def test_invalid_inspections_have_no_side_effects(payload):
    executor = RecordingOfficeCli()
    files = RecordingOpenWebUi()
    response = TestClient(create_app(executor, files, settings())).post(
        "/v1/officecli/spreadsheets/inspect", headers=HEADERS, json={"command_payload": payload})
    assert response.status_code == 422
    assert executor.calls == files.calls == []


def test_openapi_exposes_discovery_in_native_tool_context():
    schema = TestClient(create_app(RecordingOfficeCli(), RecordingOpenWebUi(), settings())).get("/openapi.json").json()
    help_topic = schema["components"]["schemas"]["HelpRequest"]["properties"]["topic"]
    assert "enum" not in help_topic
    assert "FORMAT VERB ELEMENT" in help_topic["description"]
    for name in ["InspectCommandPayload", "InspectSpreadsheetCommandPayload", "InspectPresentationCommandPayload"]:
        props = schema["components"]["schemas"][name]["properties"]
        assert {"query", "get"} <= set(props["command"]["enum"])
        assert "selector" in props and "path" in props and "offset" in props


def test_large_query_pages_keep_whole_nodes_and_report_remaining_results():
    nodes = [{"path": f"/body/p[{i}]", "text": "x" * 4000} for i in range(1, 11)]
    payload = ObjectReadPayload(command="query", selector="paragraph")
    result = bounded_result({"success": True, "data": {"matches": 10, "results": nodes}}, payload)
    assert result["data"]["matches"] == 10
    assert result["data"]["results"] == nodes[:3]
    assert result["pagination"]["next_offset"] == 3
    assert result["pagination"]["complete"] is False


def test_empty_inventory_is_distinct_from_withheld_content():
    payload = ObjectReadPayload(command="query", selector="picture")
    empty = bounded_result({"success": True, "data": {"matches": 0, "results": []}}, payload)
    assert empty["pagination"]["complete"] is True
    assert empty["pagination"]["total"] == 0
    withheld = bounded_result({"success": True, "data": {"matches": 1,
        "results": [{"path": "/body/p[1]", "text": "x" * 20000}]}}, payload)
    assert withheld["content_included"] is False
    assert "data" not in withheld
    assert "narrower query selector" in withheld["next_action"]
