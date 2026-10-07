from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


SOURCE = Path(__file__).parents[3] / "deploy/openwebui-tools/office_workflow_release.py"
SPEC = importlib.util.spec_from_file_location("office_workflow_release", SOURCE)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def public_connection(key="terminal-secret"):
    return {
        "id": "office-linux",
        "name": "Office Linux",
        "url": "http://office-terminal.openwebui:8000",
        "path": "/openapi.json",
        "auth_type": "bearer",
        "key": key,
        "config": {"enable": True, "access_grants": [dict(MODULE.PUBLIC_READ)]},
    }


class FakeApi:
    def __init__(self):
        self.base_url = "http://openwebui:8080"
        self.calls = []
        self.tool = None
        self.skill = None
        self.filter = {"id": MODULE.FILTER_ID, "name": "OfficeCLI Auto Attach", "content": "old-filter", "meta": {"kept": True}}
        self.valves = {"target_model_ids": "gpt-6-sol", "kept": "value"}
        self.terminals = [{"id": "other", "name": "Other", "config": {"enable": True}}]

    def request(self, method, path, payload=None, allow_404=False):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if method == "GET":
            if path == "/api/v1/configs/terminal_servers":
                return {"TERMINAL_SERVER_CONNECTIONS": copy.deepcopy(self.terminals)}
            if path == f"/api/v1/tools/id/{MODULE.TOOL_ID}":
                return copy.deepcopy(self.tool)
            if path == f"/api/v1/skills/id/{MODULE.SKILL_ID}":
                return copy.deepcopy(self.skill)
            if path == f"/api/v1/functions/id/{MODULE.FILTER_ID}":
                return copy.deepcopy(self.filter)
            if path == f"/api/v1/functions/id/{MODULE.FILTER_ID}/valves":
                return copy.deepcopy(self.valves)
        if method == "POST" and path == "/api/v1/configs/terminal_servers":
            self.terminals = copy.deepcopy(payload["TERMINAL_SERVER_CONNECTIONS"])
            return {"TERMINAL_SERVER_CONNECTIONS": copy.deepcopy(self.terminals)}
        if method == "POST" and path in ("/api/v1/tools/create", f"/api/v1/tools/id/{MODULE.TOOL_ID}/update"):
            self.tool = copy.deepcopy(payload)
            return copy.deepcopy(self.tool)
        if method == "POST" and path in ("/api/v1/skills/create", f"/api/v1/skills/id/{MODULE.SKILL_ID}/update"):
            self.skill = copy.deepcopy(payload)
            return copy.deepcopy(self.skill)
        if method == "POST" and path == f"/api/v1/functions/id/{MODULE.FILTER_ID}/update":
            self.filter = {**self.filter, **copy.deepcopy(payload)}
            return copy.deepcopy(self.filter)
        if method == "POST" and path == f"/api/v1/functions/id/{MODULE.FILTER_ID}/valves/update":
            self.valves = copy.deepcopy(payload)
            return copy.deepcopy(self.valves)
        if method == "DELETE" and path == f"/api/v1/tools/id/{MODULE.TOOL_ID}/delete":
            self.tool = None
            return True
        if method == "DELETE" and path == f"/api/v1/skills/id/{MODULE.SKILL_ID}/delete":
            self.skill = None
            return True
        raise AssertionError((method, path, payload, allow_404))


def test_apply_orders_dependencies_before_filter_and_writes_secret_backup(tmp_path):
    api = FakeApi()
    backup = tmp_path / "rollback.json"

    receipt = MODULE.apply(api, public_connection(), backup)

    paths = [path for method, path, _ in api.calls if method == "POST"]
    assert paths.index("/api/v1/configs/terminal_servers") < paths.index("/api/v1/tools/create")
    assert paths.index("/api/v1/tools/create") < paths.index(f"/api/v1/functions/id/{MODULE.FILTER_ID}/update")
    assert paths.index("/api/v1/skills/create") < paths.index(f"/api/v1/functions/id/{MODULE.FILTER_ID}/update")
    assert [item["id"] for item in api.terminals] == ["other", "office-linux"]
    assert api.valves["kept"] == "value"
    assert api.valves["default_terminal_id"] == "office-linux"
    assert receipt["status"] == "activated"
    assert "terminal-secret" not in json.dumps(receipt)
    assert backup.exists()
    if MODULE.os.name != "nt":
        assert backup.stat().st_mode & 0o077 == 0
    saved = json.loads(backup.read_text(encoding="utf-8"))
    assert saved["state"]["terminal_connections"] == [{"id": "other", "name": "Other", "config": {"enable": True}}]


def test_rollback_disables_filter_first_and_preserves_concurrent_terminal(tmp_path):
    api = FakeApi()
    backup = tmp_path / "rollback.json"
    MODULE.apply(api, public_connection(), backup)
    api.terminals.append({"id": "concurrent", "config": {"enable": True}})
    api.calls.clear()

    receipt = MODULE.rollback(api, backup)

    mutations = [(method, path) for method, path, _ in api.calls if method != "GET"]
    assert mutations[0] == ("POST", f"/api/v1/functions/id/{MODULE.FILTER_ID}/update")
    assert api.filter["content"] == "old-filter"
    assert api.valves == {"target_model_ids": "gpt-6-sol", "kept": "value"}
    assert api.tool is None and api.skill is None
    assert [item["id"] for item in api.terminals] == ["other", "concurrent"]
    assert receipt["status"] == "rolled_back"


def test_existing_backup_refuses_second_apply_before_any_mutation(tmp_path):
    api = FakeApi()
    backup = tmp_path / "rollback.json"
    backup.write_text("already exists", encoding="utf-8")
    before = copy.deepcopy((api.tool, api.skill, api.filter, api.valves, api.terminals))

    with pytest.raises(FileExistsError):
        MODULE.apply(api, public_connection(), backup)

    assert (api.tool, api.skill, api.filter, api.valves, api.terminals) == before
    assert not any(method != "GET" for method, _, _ in api.calls)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda c: c.update(id="other"), "id=office-linux"),
        (lambda c: c.update(key=""), "non-empty key"),
        (lambda c: c.update(auth_type="none"), "bearer or session"),
        (lambda c: c["config"].update(enable=False), "must be enabled"),
        (lambda c: c["config"].update(access_grants=[]), r"user:\* read"),
    ],
)
def test_connection_validation_fails_closed(tmp_path, mutation, match):
    connection = public_connection()
    mutation(connection)
    path = tmp_path / "connection.json"
    path.write_text(json.dumps(connection), encoding="utf-8")
    if MODULE.os.name != "nt":
        path.chmod(0o600)
    with pytest.raises(ValueError, match=match):
        MODULE._read_connection(path)


def test_session_authenticated_orchestrator_connection_needs_no_shared_key(tmp_path):
    connection = public_connection(key="")
    connection["auth_type"] = "session"
    connection["config"].update({"server_type": "orchestrator", "policy_id": "office"})
    path = tmp_path / "connection.json"
    path.write_text(json.dumps(connection), encoding="utf-8")
    if MODULE.os.name != "nt":
        path.chmod(0o600)
    assert MODULE._read_connection(path)["config"]["policy_id"] == "office"
