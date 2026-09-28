#!/usr/bin/env python3
"""Activate or roll back the native Office-to-Terminal workflow in OpenWebUI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


TOOL_ID = "terminal_file_transfer"
SKILL_ID = "artifact-workflow"
FILTER_ID = "officecli_auto_attach_filter"
TERMINAL_ID = "office-linux"
PUBLIC_READ = {"principal_type": "user", "principal_id": "*", "permission": "read"}
BACKUP_VERSION = "office-linux-workflow-release-v1"

ROOT = Path(__file__).resolve().parents[2]
TOOL_SOURCE = ROOT / "deploy/openwebui-tools/terminal_file_transfer.py"
SKILL_SOURCE = ROOT / "deploy/openwebui-skills/artifact-workflow.md"
FILTER_SOURCE = ROOT / "deploy/openwebui-functions/officecli_auto_attach_filter.py"


class Api:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, payload: Any = None, allow_404: bool = False) -> Any:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                raw = response.read()
        except HTTPError as exc:
            if allow_404 and exc.code == 404:
                return None
            raise RuntimeError(f"OpenWebUI {method} {path} failed with HTTP {exc.code}") from exc
        return json.loads(raw) if raw else None


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_secret(path: Path) -> str:
    mode = stat.S_IMODE(path.stat().st_mode)
    if os.name != "nt" and mode & 0o077:
        raise ValueError(f"Secret file must not be group/world accessible: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"Secret file is empty: {path}")
    return value


def _read_connection(path: Path) -> dict[str, Any]:
    connection = json.loads(_read_secret(path))
    if not isinstance(connection, dict) or connection.get("id") != TERMINAL_ID:
        raise ValueError(f"Terminal connection must have id={TERMINAL_ID}")
    if connection.get("auth_type", "bearer") == "bearer" and not connection.get("key"):
        raise ValueError("Bearer Terminal connection requires a non-empty key")
    if connection.get("auth_type", "bearer") not in ("bearer", "session"):
        raise ValueError("Terminal connection must use bearer or session auth")
    url = connection.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError("Terminal connection requires an HTTP(S) URL")
    config = connection.get("config")
    if not isinstance(config, dict) or config.get("enable") is not True:
        raise ValueError("Terminal connection must be enabled")
    if not _has_public_read(config.get("access_grants")):
        raise ValueError("Terminal connection requires user:* read access")
    return connection


def _has_public_read(grants: Any) -> bool:
    return isinstance(grants, list) and any(
        isinstance(item, dict)
        and all(item.get(key) == value for key, value in PUBLIC_READ.items())
        for item in grants
    )


def _sources() -> dict[str, str]:
    return {
        "tool": TOOL_SOURCE.read_text(encoding="utf-8"),
        "skill": SKILL_SOURCE.read_text(encoding="utf-8"),
        "filter": FILTER_SOURCE.read_text(encoding="utf-8"),
    }


def _get_state(api: Api) -> dict[str, Any]:
    terminals = api.request("GET", "/api/v1/configs/terminal_servers")
    if not isinstance(terminals, dict) or not isinstance(terminals.get("TERMINAL_SERVER_CONNECTIONS"), list):
        raise RuntimeError("Invalid Terminal configuration response")
    tool = api.request("GET", f"/api/v1/tools/id/{TOOL_ID}", allow_404=True)
    skill = api.request("GET", f"/api/v1/skills/id/{SKILL_ID}", allow_404=True)
    function = api.request("GET", f"/api/v1/functions/id/{FILTER_ID}")
    valves = api.request("GET", f"/api/v1/functions/id/{FILTER_ID}/valves")
    if tool is not None and not isinstance(tool, dict):
        raise RuntimeError("Invalid Tool response")
    if skill is not None and not isinstance(skill, dict):
        raise RuntimeError("Invalid Skill response")
    if not isinstance(function, dict) or not isinstance(valves, dict):
        raise RuntimeError("Invalid Filter or Filter valves response")
    return {
        "tool": tool,
        "skill": skill,
        "filter": function,
        "filter_valves": valves,
        "terminal_connections": terminals["TERMINAL_SERVER_CONNECTIONS"],
    }


def _write_backup(path: Path, base_url: str, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(
            {"version": BACKUP_VERSION, "base_url": base_url.rstrip("/"), "state": state},
            handle,
            ensure_ascii=False,
            indent=2,
        )


def _upsert_terminal(api: Api, desired: dict[str, Any]) -> None:
    current = api.request("GET", "/api/v1/configs/terminal_servers")["TERMINAL_SERVER_CONNECTIONS"]
    updated = [item for item in current if item.get("id") != TERMINAL_ID]
    updated.append(desired)
    api.request("POST", "/api/v1/configs/terminal_servers", {"TERMINAL_SERVER_CONNECTIONS": updated})


def _tool_form(source: str) -> dict[str, Any]:
    return {
        "id": TOOL_ID,
        "name": "Terminal File Transfer",
        "content": source,
        "meta": {"description": "Transfer authorized chat files to the selected Terminal and publish verified results."},
        "access_grants": [PUBLIC_READ],
    }


def _skill_form(source: str) -> dict[str, Any]:
    return {
        "id": SKILL_ID,
        "name": "Artifact Workflow",
        "description": "Plan, resume, verify and publish multi-part file work without mutating sources.",
        "content": source,
        "is_active": True,
        "access_grants": [PUBLIC_READ],
    }


def _upsert_resource(api: Api, kind: str, resource_id: str, form: dict[str, Any], exists: bool) -> None:
    path = f"/api/v1/{kind}/id/{resource_id}/update" if exists else f"/api/v1/{kind}/create"
    api.request("POST", path, form)


def _update_filter(api: Api, previous: dict[str, Any], source: str, valves: dict[str, Any]) -> None:
    api.request(
        "POST",
        f"/api/v1/functions/id/{FILTER_ID}/update",
        {
            "id": FILTER_ID,
            "name": previous.get("name") or "OfficeCLI Auto Attach",
            "meta": previous.get("meta") if isinstance(previous.get("meta"), dict) else {},
            "content": source,
        },
    )
    api.request("POST", f"/api/v1/functions/id/{FILTER_ID}/valves/update", valves)


def _desired_valves(previous: Any) -> dict[str, Any]:
    valves = dict(previous) if isinstance(previous, dict) else {}
    valves.update(
        {
            "terminal_transfer_tool_id": TOOL_ID,
            "artifact_workflow_skill_id": SKILL_ID,
            "default_terminal_id": TERMINAL_ID,
        }
    )
    return valves


def apply(api: Api, connection: dict[str, Any], backup_path: Path) -> dict[str, Any]:
    sources = _sources()
    before = _get_state(api)
    _write_backup(backup_path, api.base_url, before)

    # Dependencies first; the global Filter switches the user route last.
    _upsert_terminal(api, connection)
    _upsert_resource(api, "tools", TOOL_ID, _tool_form(sources["tool"]), before["tool"] is not None)
    _upsert_resource(api, "skills", SKILL_ID, _skill_form(sources["skill"]), before["skill"] is not None)
    _update_filter(api, before["filter"], sources["filter"], _desired_valves(before["filter_valves"]))

    after = _get_state(api)
    _verify_active(after, sources)
    return {
        "status": "activated",
        "ids": {"filter": FILTER_ID, "tool": TOOL_ID, "skill": SKILL_ID, "terminal": TERMINAL_ID},
        "source_sha256": {key: _sha(value) for key, value in sources.items()},
        "backup_path": str(backup_path),
    }


def _verify_active(state: dict[str, Any], sources: dict[str, str]) -> None:
    if _sha(state["tool"].get("content", "")) != _sha(sources["tool"]):
        raise RuntimeError("Live Tool source hash mismatch")
    if not _has_public_read(state["tool"].get("access_grants")):
        raise RuntimeError("Live Tool is not readable by all users")
    if _sha(state["skill"].get("content", "")) != _sha(sources["skill"]):
        raise RuntimeError("Live Skill source hash mismatch")
    if not state["skill"].get("is_active") or not _has_public_read(state["skill"].get("access_grants")):
        raise RuntimeError("Live Skill is inactive or not readable by all users")
    if _sha(state["filter"].get("content", "")) != _sha(sources["filter"]):
        raise RuntimeError("Live Filter source hash mismatch")
    valves = state["filter_valves"]
    expected = {
        "terminal_transfer_tool_id": TOOL_ID,
        "artifact_workflow_skill_id": SKILL_ID,
        "default_terminal_id": TERMINAL_ID,
    }
    if not isinstance(valves, dict) or any(valves.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Live Filter valves do not select the released workflow")
    terminal = next((item for item in state["terminal_connections"] if item.get("id") == TERMINAL_ID), None)
    if not terminal or not terminal.get("config", {}).get("enable"):
        raise RuntimeError("Live system Terminal connection is missing or disabled")


def rollback(api: Api, backup_path: Path) -> dict[str, Any]:
    backup = json.loads(_read_secret(backup_path))
    if backup.get("version") != BACKUP_VERSION or backup.get("base_url") != api.base_url:
        raise ValueError("Rollback backup does not belong to this release target")
    before = backup.get("state")
    if not isinstance(before, dict):
        raise ValueError("Rollback backup state is invalid")
    if not isinstance(before.get("filter"), dict) or not isinstance(before.get("filter_valves"), dict):
        raise ValueError("Rollback Filter state is invalid")

    # Disable the global route first, then restore/remove its dependencies.
    _update_filter(api, before["filter"], before["filter"].get("content", ""), before["filter_valves"])
    _restore_resource(api, "tools", TOOL_ID, before.get("tool"))
    _restore_resource(api, "skills", SKILL_ID, before.get("skill"))
    current = api.request("GET", "/api/v1/configs/terminal_servers")["TERMINAL_SERVER_CONNECTIONS"]
    restored = [item for item in current if item.get("id") != TERMINAL_ID]
    old_terminal = next((item for item in before["terminal_connections"] if item.get("id") == TERMINAL_ID), None)
    if old_terminal is not None:
        restored.append(old_terminal)
    api.request("POST", "/api/v1/configs/terminal_servers", {"TERMINAL_SERVER_CONNECTIONS": restored})
    return {"status": "rolled_back", "ids": {"filter": FILTER_ID, "tool": TOOL_ID, "skill": SKILL_ID, "terminal": TERMINAL_ID}}


def _restore_resource(api: Api, kind: str, resource_id: str, previous: Any) -> None:
    current = api.request("GET", f"/api/v1/{kind}/id/{resource_id}", allow_404=True)
    if previous is None:
        if current is not None:
            api.request("DELETE", f"/api/v1/{kind}/id/{resource_id}/delete")
        return
    form = {key: previous[key] for key in (
        ("id", "name", "content", "meta", "access_grants")
        if kind == "tools"
        else ("id", "name", "description", "content", "is_active", "access_grants")
    ) if key in previous}
    _upsert_resource(api, kind, resource_id, form, current is not None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("apply", "rollback"))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--backup-file", type=Path, required=True)
    parser.add_argument("--terminal-connection-file", type=Path)
    args = parser.parse_args()
    api = Api(args.base_url, _read_secret(args.token_file))
    if args.action == "apply":
        if args.terminal_connection_file is None:
            parser.error("apply requires --terminal-connection-file")
        result = apply(api, _read_connection(args.terminal_connection_file), args.backup_file)
    else:
        result = rollback(api, args.backup_file)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
