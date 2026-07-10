#!/usr/bin/env python3
"""Install/update the Gate 2 Pipe Function and its OpenWebUI managed Prompt."""

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
    / "broker_reports_gate2_source_fact_pipe_bundled.py"
)
PROMPT_CONTRACT_PATH = (
    ROOT / "docs" / "stage2" / "contracts" / "BROKER_REPORTS_GATE2_SOURCE_FACT_PROMPT.v0.md"
)
FUNCTION_ID = "broker_reports_gate2_source_fact_pipe"
PROMPT_ID = "broker_reports_gate2_source_fact_prompt_v0"
PROMPT_COMMAND = "broker_gate2_source_facts_v0"
PROMPT_VERSION = "gate2-source-facts-v0-2026-07-10-implementation"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from live_no_rag_source_intake_smoke import (
    _base_url,
    _default_ssh_target,
    _read_env,
    _signin,
    _url,
)
from broker_reports_gate1 import gate2_prompt_hash, source_facts_schema_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--prompt-command", default=PROMPT_COMMAND)
    parser.add_argument("--prompt-version", default=PROMPT_VERSION)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    bundle_source = BUNDLE_PATH.read_text(encoding="utf-8")
    bundle_sha = hashlib.sha256(bundle_source.encode("utf-8")).hexdigest()
    prompt_content = _prompt_content_from_contract(
        PROMPT_CONTRACT_PATH,
        "You are the Broker Reports Gate 2 bounded source-fact extractor.",
    )

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    function_before = _get_function(session, base_url)
    action = "updated" if function_before is not None else "created"
    if function_before is None:
        _create_function(session, base_url, bundle_source)
    else:
        _update_function(session, base_url, function_before, bundle_source)
    function_after = _get_function(session, base_url)
    if function_after is None:
        raise RuntimeError("gate2_function_install_failed")
    live_sha = hashlib.sha256(str(function_after.get("content") or "").encode("utf-8")).hexdigest()
    if live_sha != bundle_sha:
        raise RuntimeError("gate2_function_bundle_hash_mismatch")
    if function_after.get("is_active") is False:
        _toggle_function(session, base_url)
        function_after = _get_function(session, base_url)
    if function_after is None or function_after.get("is_active") is False:
        raise RuntimeError("gate2_function_inactive")

    prompt_summary = _seed_prompt(
        ssh_target=ssh_target,
        prompt_content=prompt_content,
        prompt_command=args.prompt_command,
        prompt_version=args.prompt_version,
    )
    if prompt_summary.get("prompt_hash") != gate2_prompt_hash(prompt_content):
        raise RuntimeError("gate2_managed_prompt_hash_mismatch")
    if prompt_summary.get("output_schema_hash") != source_facts_schema_hash():
        raise RuntimeError("gate2_managed_prompt_schema_hash_mismatch")

    output = {
        "status": "passed",
        "function": {
            "action": action,
            "function_id": FUNCTION_ID,
            "active": function_after.get("is_active") is not False,
            "bundle_sha256": bundle_sha,
            "live_content_sha256": live_sha,
            "contains_runtime_factory": "Gate2SourceFactRuntimeFactory" in str(function_after.get("content") or ""),
            "contains_validator_factory": "Gate2SourceFactValidatorFactory" in str(function_after.get("content") or ""),
        },
        "managed_prompt": prompt_summary,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _prompt_content_from_contract(path: Path, marker: str) -> str:
    text = path.read_text(encoding="utf-8-sig")
    start = text.index(marker)
    fence_end = text.index("\n```", start)
    return text[start:fence_end].strip()


def _get_function(session: requests.Session, base_url: str) -> dict[str, Any] | None:
    response = session.get(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}"),
        timeout=30,
    )
    if response.status_code == 404:
        return None
    if response.status_code == 401:
        listed = session.get(_url(base_url, "/api/v1/functions/"), timeout=30)
        listed.raise_for_status()
        payload = listed.json()
        functions = payload if isinstance(payload, list) else []
        if not any(
            isinstance(item, dict) and item.get("id") == FUNCTION_ID
            for item in functions
        ):
            return None
    response.raise_for_status()
    value = response.json()
    return value if isinstance(value, dict) else None


def _create_function(session: requests.Session, base_url: str, content: str) -> None:
    response = session.post(
        _url(base_url, "/api/v1/functions/create"),
        json={
            "id": FUNCTION_ID,
            "name": "Broker Reports Gate 2 Source Facts",
            "meta": {"description": "Resolver-gated structured source-fact extraction"},
            "content": content,
        },
        timeout=60,
    )
    response.raise_for_status()


def _update_function(
    session: requests.Session,
    base_url: str,
    function: dict[str, Any],
    content: str,
) -> None:
    response = session.post(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/update"),
        json={
            "id": FUNCTION_ID,
            "name": function.get("name") or "Broker Reports Gate 2 Source Facts",
            "meta": function.get("meta") if isinstance(function.get("meta"), dict) else {},
            "content": content,
        },
        timeout=60,
    )
    response.raise_for_status()


def _toggle_function(session: requests.Session, base_url: str) -> None:
    response = session.post(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/toggle"),
        timeout=30,
    )
    response.raise_for_status()


def _seed_prompt(
    *,
    ssh_target: str,
    prompt_content: str,
    prompt_command: str,
    prompt_version: str,
) -> dict[str, Any]:
    meta = {
        "template_kind": "broker_reports_source_fact_extraction",
        "template_id": "broker_reports.source_fact_extraction.v0",
        "prompt_contract_id": "broker_reports_source_fact_prompt_v0",
        "input_contract": "broker_reports_source_fact_package_v0",
        "output_schema_id": "broker_reports.source_facts.schema.v0",
        "output_schema_version": "broker_reports_source_facts_v0",
        "output_schema_hash": source_facts_schema_hash(),
        "gate": "gate2",
        "structured_output_required": True,
        "forbidden_tasks": [
            "raw_file_parsing",
            "issue_resolution",
            "cross_document_deduplication",
            "profit_loss_calculation",
            "tax_calculation",
            "declaration_generation",
            "xlsx_generation",
            "ocr_vlm",
            "knowledge_loading",
        ],
    }
    tags = [
        "broker-reports-gate2",
        "source-fact-extraction",
        "structured-output",
        "managed-prompt",
    ]
    data = {
        "managed_by": "broker_reports_gate2_live_update",
        "updated_at_epoch": int(time.time()),
    }
    prompt_sha = gate2_prompt_hash(prompt_content)
    remote_code = r'''
import json
import sqlite3
import time

prompt_id = __PROMPT_ID__
prompt_command = __PROMPT_COMMAND__
prompt_version = __PROMPT_VERSION__
prompt_content = __PROMPT_CONTENT__
meta_json = __META_JSON__
tags_json = __TAGS_JSON__
data_json = __DATA_JSON__
prompt_hash_value = __PROMPT_HASH__
output_schema_hash = __OUTPUT_SCHEMA_HASH__

conn = sqlite3.connect("/app/backend/data/webui.db")
conn.row_factory = sqlite3.Row
try:
    owner = conn.execute(
        "select id from user where role = 'admin' order by created_at asc limit 1"
    ).fetchone()
    if owner is None:
        raise RuntimeError("gate2_prompt_owner_missing")
    owner_id = str(owner["id"])
    now = int(time.time())
    existing = conn.execute("select id from prompt where id = ?", (prompt_id,)).fetchone()
    if existing:
        conn.execute(
            """
            update prompt
            set command = ?, user_id = ?, name = ?, content = ?, data = ?, meta = ?,
                is_active = 1, version_id = ?, tags = ?, updated_at = ?
            where id = ?
            """,
            (
                prompt_command, owner_id, "Broker Reports Gate 2 Source Facts v0",
                prompt_content, data_json, meta_json, prompt_version, tags_json,
                now, prompt_id,
            ),
        )
        action = "updated"
    else:
        conn.execute(
            """
            insert into prompt(
                id, command, user_id, name, content, data, meta, is_active,
                version_id, tags, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                prompt_id, prompt_command, owner_id,
                "Broker Reports Gate 2 Source Facts v0", prompt_content,
                data_json, meta_json, prompt_version, tags_json, now, now,
            ),
        )
        action = "created"
    conn.commit()
    row = conn.execute(
        "select id, command, version_id, tags, meta, length(content) as content_length from prompt where id = ?",
        (prompt_id,),
    ).fetchone()
    print(json.dumps({
        "action": action,
        "prompt_ref": row["id"],
        "command": row["command"],
        "version": row["version_id"],
        "prompt_hash": prompt_hash_value,
        "content_length": row["content_length"],
        "tags": json.loads(row["tags"]),
        "template_id": json.loads(row["meta"])["template_id"],
        "output_schema_id": json.loads(row["meta"])["output_schema_id"],
        "output_schema_version": json.loads(row["meta"])["output_schema_version"],
        "output_schema_hash": output_schema_hash,
        "structured_output_required": json.loads(row["meta"])["structured_output_required"],
    }, ensure_ascii=False, sort_keys=True))
finally:
    conn.close()
'''
    replacements = {
        "__PROMPT_ID__": json.dumps(PROMPT_ID, ensure_ascii=False),
        "__PROMPT_COMMAND__": json.dumps(prompt_command, ensure_ascii=False),
        "__PROMPT_VERSION__": json.dumps(prompt_version, ensure_ascii=False),
        "__PROMPT_CONTENT__": json.dumps(prompt_content, ensure_ascii=False),
        "__META_JSON__": json.dumps(json.dumps(meta, ensure_ascii=False), ensure_ascii=False),
        "__TAGS_JSON__": json.dumps(json.dumps(tags, ensure_ascii=False), ensure_ascii=False),
        "__DATA_JSON__": json.dumps(json.dumps(data, ensure_ascii=False), ensure_ascii=False),
        "__PROMPT_HASH__": json.dumps(prompt_sha, ensure_ascii=False),
        "__OUTPUT_SCHEMA_HASH__": json.dumps(source_facts_schema_hash(), ensure_ascii=False),
    }
    for needle, replacement in replacements.items():
        remote_code = remote_code.replace(needle, replacement)
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=no",
            ssh_target,
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        cwd=ROOT,
        input=remote_code,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    return json.loads(completed.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
