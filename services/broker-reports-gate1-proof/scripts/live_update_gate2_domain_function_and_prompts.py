#!/usr/bin/env python3
"""Install/update the Gate 2 domain Pipe and all managed domain Prompts."""

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
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
BUNDLE_PATH = (
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
)
PROMPT_CONTRACT_PATH = (
    ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_GATE2_SOURCE_FACT_PROMPT.v0.md"
)
FUNCTION_ID = "broker_reports_gate2_domain_source_fact_pipe"
PROMPT_VERSION = "gate2-domain-source-facts-v0-2026-07-10"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from live_no_rag_source_intake_smoke import (
    _base_url,
    _default_ssh_target,
    _read_env,
    _signin,
    _url,
)
from broker_reports_gate1 import (
    DOMAIN_ALLOWED_FACT_TYPES,
    gate2_prompt_hash,
    required_domain_prompt_identities,
    source_facts_schema_hash,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--prompt-version", default=PROMPT_VERSION)
    args = parser.parse_args()

    subprocess.run(
        [sys.executable, str(SERVICE_ROOT / "scripts" / "build_openwebui_pipe_bundle.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    bundle_source = BUNDLE_PATH.read_text(encoding="utf-8")
    bundle_sha = hashlib.sha256(bundle_source.encode("utf-8")).hexdigest()
    template = _domain_prompt_template(PROMPT_CONTRACT_PATH)
    prompt_rows = _render_prompt_rows(template, args.prompt_version)

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    before = _get_function(session, base_url)
    action = "updated" if before is not None else "created"
    if before is None:
        _create_function(session, base_url, bundle_source)
    else:
        _update_function(session, base_url, before, bundle_source)
    after = _get_function(session, base_url)
    if after is None:
        raise RuntimeError("gate2_domain_function_install_failed")
    live_sha = hashlib.sha256(str(after.get("content") or "").encode("utf-8")).hexdigest()
    if live_sha != bundle_sha:
        raise RuntimeError("gate2_domain_function_bundle_hash_mismatch")
    if after.get("is_active") is False:
        _toggle_function(session, base_url)
        after = _get_function(session, base_url)
    if after is None or after.get("is_active") is False:
        raise RuntimeError("gate2_domain_function_inactive")

    prompt_summary = _seed_prompts(
        ssh_target=ssh_target,
        prompt_rows=prompt_rows,
    )
    if len(prompt_summary) != len(DOMAIN_ALLOWED_FACT_TYPES):
        raise RuntimeError("gate2_domain_prompt_count_mismatch")
    expected_hashes = {item["prompt_id"]: item["prompt_hash"] for item in prompt_rows}
    for item in prompt_summary:
        if item.get("prompt_hash") != expected_hashes.get(str(item.get("prompt_ref"))):
            raise RuntimeError("gate2_domain_prompt_hash_mismatch")

    output = {
        "status": "passed",
        "function": {
            "action": action,
            "function_id": FUNCTION_ID,
            "active": True,
            "bundle_sha256": bundle_sha,
            "live_content_sha256": live_sha,
            "contains_domain_runtime_factory": "Gate2DomainSourceFactRuntimeFactory" in str(after.get("content") or ""),
            "contains_router_factory": "Gate2SourceUnitRouterFactory" in str(after.get("content") or ""),
            "contains_stitcher_factory": "Gate2SourceFactStitcherFactory" in str(after.get("content") or ""),
        },
        "managed_prompts": prompt_summary,
        "managed_prompts_total": len(prompt_summary),
        "output_schema_hash": source_facts_schema_hash(),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _domain_prompt_template(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    start_marker = "<!-- DOMAIN_PROMPT_TEMPLATE_BEGIN -->"
    end_marker = "<!-- DOMAIN_PROMPT_TEMPLATE_END -->"
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    template = text[start:end].strip()
    if "{{source_fact_package_json}}" not in template:
        raise RuntimeError("gate2_domain_prompt_package_marker_missing")
    return template


def _render_prompt_rows(template: str, prompt_version: str) -> list[dict[str, Any]]:
    rows = []
    for identity in required_domain_prompt_identities():
        domain = identity["domain"]
        allowed = DOMAIN_ALLOWED_FACT_TYPES[domain]
        content = template.replace("__EXTRACTOR_DOMAIN__", domain).replace(
            "__ALLOWED_FACT_TYPES_JSON__",
            json.dumps(allowed, ensure_ascii=False, separators=(",", ":")),
        )
        meta = {
            "template_kind": identity["template_kind"],
            "template_id": identity["template_id"],
            "prompt_contract_id": identity["prompt_contract_id"],
            "input_contract": "broker_reports_domain_extraction_package_v0",
            "output_schema_id": "broker_reports.source_facts.schema.v0",
            "output_schema_version": "broker_reports_source_facts_v0",
            "output_schema_hash": source_facts_schema_hash(),
            "extractor_domain": domain,
            "allowed_fact_types": allowed,
            "gate": "gate2",
            "structured_output_required": True,
            "customer_fallback": "none",
            "knowledge_rag_allowed": False,
            "vectorization_allowed": False,
        }
        rows.append(
            {
                "prompt_id": identity["prompt_id"],
                "prompt_command": identity["prompt_command"],
                "prompt_name": f"Broker Reports Gate 2 {domain} v0",
                "prompt_version": prompt_version,
                "prompt_content": content,
                "prompt_hash": gate2_prompt_hash(content),
                "meta": meta,
                "tags": [
                    "broker-reports-gate2-domain",
                    domain,
                    "structured-output",
                    "managed-prompt",
                ],
                "data": {
                    "managed_by": "broker_reports_gate2_domain_live_update",
                    "updated_at_epoch": int(time.time()),
                },
            }
        )
    return rows


def _get_function(session: requests.Session, base_url: str) -> dict[str, Any] | None:
    response = session.get(_url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}"), timeout=30)
    if response.status_code == 404:
        return None
    if response.status_code == 401:
        listed = session.get(_url(base_url, "/api/v1/functions/"), timeout=30)
        listed.raise_for_status()
        values = listed.json()
        for item in values if isinstance(values, list) else []:
            if isinstance(item, dict) and item.get("id") == FUNCTION_ID:
                return item
        return None
    response.raise_for_status()
    value = response.json()
    return value if isinstance(value, dict) else None


def _create_function(session: requests.Session, base_url: str, content: str) -> None:
    response = session.post(
        _url(base_url, "/api/v1/functions/create"),
        json={
            "id": FUNCTION_ID,
            "name": "Broker Reports Gate 2 Domain Source Facts",
            "meta": {"description": "Deterministic routing to narrow structured extractors"},
            "content": content,
        },
        timeout=60,
    )
    response.raise_for_status()


def _update_function(session: requests.Session, base_url: str, function: dict[str, Any], content: str) -> None:
    response = session.post(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/update"),
        json={
            "id": FUNCTION_ID,
            "name": function.get("name") or "Broker Reports Gate 2 Domain Source Facts",
            "meta": function.get("meta") if isinstance(function.get("meta"), dict) else {},
            "content": content,
        },
        timeout=60,
    )
    response.raise_for_status()


def _toggle_function(session: requests.Session, base_url: str) -> None:
    response = session.post(_url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/toggle"), timeout=30)
    response.raise_for_status()


def _seed_prompts(*, ssh_target: str, prompt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remote_code = r'''
import json
import sqlite3
import time

rows = json.loads(__PROMPT_ROWS_JSON__)
conn = sqlite3.connect("/app/backend/data/webui.db")
conn.row_factory = sqlite3.Row
result = []
try:
    owner = conn.execute(
        "select id from user where role = 'admin' order by created_at asc limit 1"
    ).fetchone()
    if owner is None:
        raise RuntimeError("gate2_domain_prompt_owner_missing")
    owner_id = str(owner["id"])
    now = int(time.time())
    for item in rows:
        prompt_id = item["prompt_id"]
        existing = conn.execute("select id from prompt where id = ?", (prompt_id,)).fetchone()
        values = (
            item["prompt_command"], owner_id, item["prompt_name"], item["prompt_content"],
            json.dumps(item["data"], ensure_ascii=False),
            json.dumps(item["meta"], ensure_ascii=False),
            item["prompt_version"],
            json.dumps(item["tags"], ensure_ascii=False),
        )
        if existing:
            conn.execute(
                """
                update prompt set command=?, user_id=?, name=?, content=?, data=?, meta=?,
                    is_active=1, version_id=?, tags=?, updated_at=? where id=?
                """,
                (*values, now, prompt_id),
            )
            action = "updated"
        else:
            conn.execute(
                """
                insert into prompt(id, command, user_id, name, content, data, meta,
                    is_active, version_id, tags, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (prompt_id, *values, now, now),
            )
            action = "created"
        result.append({
            "action": action,
            "prompt_ref": prompt_id,
            "command": item["prompt_command"],
            "domain": item["meta"]["extractor_domain"],
            "allowed_fact_types": item["meta"]["allowed_fact_types"],
            "prompt_hash": item["prompt_hash"],
            "content_length": len(item["prompt_content"]),
            "structured_output_required": True,
        })
    conn.commit()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
finally:
    conn.close()
'''
    remote_code = remote_code.replace(
        "__PROMPT_ROWS_JSON__",
        json.dumps(json.dumps(prompt_rows, ensure_ascii=False), ensure_ascii=False),
    )
    completed = subprocess.run(
        [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no",
            ssh_target,
            "docker", "exec", "-i", "openwebui", "python", "-",
        ],
        cwd=ROOT,
        input=remote_code,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    value = json.loads(completed.stdout)
    return value if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
