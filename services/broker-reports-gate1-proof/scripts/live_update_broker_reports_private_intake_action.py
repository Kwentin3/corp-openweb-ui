#!/usr/bin/env python3
"""Install and read back the protected Broker Reports private-intake Action."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
ACTION_ID = "broker_reports_private_intake_action"
ACTION_PATH = (
    ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "openwebui_actions"
    / "broker_reports_private_intake_action.py"
)

sys.path.insert(0, str(SCRIPT_DIR))

from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    source = ACTION_PATH.read_text(encoding="utf-8")
    source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin_when_ready(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    existing = _get_action(session, base_url)
    previous_sha256 = _content_sha256(existing) if existing else None
    payload = {
        "id": ACTION_ID,
        "name": "Broker Reports Private Intake",
        "content": source,
        "meta": {
            "description": (
                "Server-verified handoff for receipt-backed Broker Reports sources."
            )
        },
    }
    if existing is None:
        response = session.post(
            _url(base_url, "/api/v1/functions/create"),
            json=payload,
            timeout=60,
        )
        operation = "created"
    else:
        response = session.post(
            _url(base_url, f"/api/v1/functions/id/{ACTION_ID}/update"),
            json=payload,
            timeout=60,
        )
        operation = "updated"
    response.raise_for_status()

    live = _require_action(session, base_url)
    if not bool(live.get("is_active")):
        response = session.post(
            _url(base_url, f"/api/v1/functions/id/{ACTION_ID}/toggle"),
            timeout=30,
        )
        response.raise_for_status()
        live = _require_action(session, base_url)
    if bool(live.get("is_global")):
        response = session.post(
            _url(base_url, f"/api/v1/functions/id/{ACTION_ID}/toggle/global"),
            timeout=30,
        )
        response.raise_for_status()
        live = _require_action(session, base_url)

    live_sha256 = _content_sha256(live)
    manifest = _manifest(live)
    checks = {
        "content_hash_exact": live_sha256 == source_sha256,
        "function_type_action": live.get("type") == "action",
        "active": live.get("is_active") is True,
        "not_global": live.get("is_global") is False,
        "manifest_version_v2": manifest.get("version") == "2.0.0",
        "closed_world_contract_import": (
            "open_webui.routers.broker_reports_intake_contract"
            in str(live.get("content") or "")
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"private_intake_action_readback_failed:{checks}")

    receipt = {
        "status": "passed",
        "action_id": ACTION_ID,
        "operation": operation,
        "previous_content_sha256": previous_sha256,
        "repository_content_sha256": source_sha256,
        "live_content_sha256": live_sha256,
        "source_revision": _source_revision(),
        "checks": checks,
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _get_action(
    session: requests.Session, base_url: str
) -> dict[str, Any] | None:
    response = session.get(
        _url(base_url, f"/api/v1/functions/id/{ACTION_ID}"), timeout=30
    )
    if response.status_code == 401:
        # OpenWebUI v0.9.6 uses 401 for a missing Function.  Authentication is
        # already proven by the successful admin sign-in and Function list.
        probe = session.get(_url(base_url, "/api/v1/functions/"), timeout=30)
        probe.raise_for_status()
        return None
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("private_intake_action_response_invalid")
    return data


def _signin_when_ready(
    session: requests.Session, base_url: str, env: dict[str, str]
) -> str:
    deadline = time.time() + 120
    while True:
        try:
            return _signin(session, base_url, env)
        except requests.HTTPError as error:
            status_code = error.response.status_code if error.response is not None else 0
            if status_code not in {404, 502, 503} or time.time() >= deadline:
                raise
        except requests.RequestException:
            if time.time() >= deadline:
                raise
        time.sleep(2)


def _require_action(session: requests.Session, base_url: str) -> dict[str, Any]:
    action = _get_action(session, base_url)
    if action is None:
        raise RuntimeError("private_intake_action_missing_after_update")
    return action


def _content_sha256(action: dict[str, Any]) -> str:
    return hashlib.sha256(str(action.get("content") or "").encode("utf-8")).hexdigest()


def _manifest(action: dict[str, Any]) -> dict[str, Any]:
    meta = action.get("meta") if isinstance(action.get("meta"), dict) else {}
    manifest = meta.get("manifest") if isinstance(meta.get("manifest"), dict) else {}
    return manifest


def _source_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    return completed.stdout.strip()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "code": str(exc)[:200],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise
