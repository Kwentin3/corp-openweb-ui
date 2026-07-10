#!/usr/bin/env python3
"""Update the live Gate 1 Function and seed the managed passport Prompt."""

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
PASSPORT_CONTRACT_PATH = ROOT / "docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT_PROMPT.v0.md"
CLARIFICATION_CONTRACT_PATH = ROOT / "docs/stage2/contracts/BROKER_REPORTS_GATE1_METADATA_CLARIFICATION_PROMPT.v0.md"
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions/broker_reports_gate1_pipe_bundled.py"
FUNCTION_ID = "broker_reports_gate1_pipe"
PROMPT_ID = "broker_reports_document_metadata_passport_prompt_v0"
PROMPT_COMMAND = "broker_gate1_document_passport"
PROMPT_VERSION = "passport-v0-2026-07-08-implementation"
CLARIFICATION_PROMPT_ID = "broker_reports_gate1_clarification_prompt_v0"
CLARIFICATION_PROMPT_COMMAND = "broker_gate1_clarification_request"
CLARIFICATION_PROMPT_VERSION = "clarification-v0-2026-07-09-implementation"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from live_no_rag_source_intake_smoke import _base_url, _default_ssh_target, _read_env, _signin, _url
from broker_reports_gate1.document_passport import prompt_hash
from broker_reports_gate1.clarification import gate1_clarification_request_schema_hash


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
    prompt_content = _prompt_content_from_contract(
        PASSPORT_CONTRACT_PATH,
        "You are the Broker Reports Gate 1 document metadata passport classifier.",
    )
    clarification_prompt_content = _prompt_content_from_contract(
        CLARIFICATION_CONTRACT_PATH,
        "You are the Broker Reports Gate 1 metadata clarification question writer.",
    )
    passport_prompt_sha = prompt_hash(
        prompt_content,
        "broker_reports_document_metadata_passport_prompt_v0",
        "document_metadata_passport_v0",
    )
    clarification_prompt_sha = prompt_hash(
        clarification_prompt_content,
        "broker_reports_gate1_clarification_prompt_v0",
        "gate1_clarification_request_v0",
    )

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    bundle_source = BUNDLE_PATH.read_text(encoding="utf-8")
    bundle_sha = hashlib.sha256(bundle_source.encode("utf-8")).hexdigest()
    before = _get_function(session, base_url)
    before_sha = hashlib.sha256(str(before.get("content") or "").encode("utf-8")).hexdigest()
    _update_function(session, base_url, before, bundle_source)
    after = _get_function(session, base_url)
    live_sha = hashlib.sha256(str(after.get("content") or "").encode("utf-8")).hexdigest()
    if live_sha != bundle_sha:
        raise RuntimeError("live_function_bundle_hash_mismatch")

    prompt_summary = _seed_passport_prompt(
        ssh_target=ssh_target,
        prompt_content=prompt_content,
        prompt_command=args.prompt_command,
        prompt_version=args.prompt_version,
    )
    if prompt_summary.get("prompt_hash") != passport_prompt_sha:
        raise RuntimeError("managed_prompt_hash_mismatch")
    clarification_prompt_summary = _seed_clarification_prompt(
        ssh_target=ssh_target,
        prompt_content=clarification_prompt_content,
        prompt_command=CLARIFICATION_PROMPT_COMMAND,
        prompt_version=CLARIFICATION_PROMPT_VERSION,
    )
    if clarification_prompt_summary.get("prompt_hash") != clarification_prompt_sha:
        raise RuntimeError("managed_clarification_prompt_hash_mismatch")

    summary = {
        "status": "passed",
        "function": {
            "function_id": FUNCTION_ID,
            "updated": True,
            "previous_content_sha256": before_sha,
            "bundle_sha256": bundle_sha,
            "live_content_sha256": live_sha,
            "contains_document_passport": "DocumentPassportPromptResolverFactory" in str(after.get("content") or ""),
            "contains_metadata_clarification": "ClarificationPromptResolverFactory" in str(after.get("content") or ""),
        },
        "managed_prompt": prompt_summary,
        "managed_clarification_prompt": clarification_prompt_summary,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _prompt_content_from_contract(path: Path, marker: str) -> str:
    text = path.read_text(encoding="utf-8-sig")
    start = text.index(marker)
    fence_end = text.index("\n```", start)
    return text[start:fence_end].strip()


def _get_function(session: requests.Session, base_url: str) -> dict[str, Any]:
    response = session.get(_url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}"), timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("function_response_invalid")
    return data


def _update_function(
    session: requests.Session,
    base_url: str,
    function: dict[str, Any],
    content: str,
) -> None:
    payload = {
        "id": FUNCTION_ID,
        "name": function.get("name") or "Broker Reports Gate 1",
        "meta": function.get("meta") if isinstance(function.get("meta"), dict) else {},
        "content": content,
    }
    response = session.post(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/update"),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()


def _seed_passport_prompt(
    *,
    ssh_target: str,
    prompt_content: str,
    prompt_command: str,
    prompt_version: str,
) -> dict[str, Any]:
    meta = {
        "template_kind": "document_metadata_passport",
        "template_id": "broker_reports.document_metadata_passport.v0",
        "prompt_contract_id": "broker_reports_document_metadata_passport_prompt_v0",
        "input_contract": "broker_reports_llm_document_package_v0",
        "output_schema_version": "document_metadata_passport_v0",
        "gate": "gate1_5",
        "forbidden_tasks": [
            "source_fact_extraction",
            "tax_calculation",
            "declaration_generation",
            "xlsx_generation",
            "ocr_vlm",
            "knowledge_loading",
        ],
    }
    tags = ["broker-reports-gate1", "document-metadata-passport", "managed-prompt"]
    data = {"managed_by": "broker_reports_gate1_live_update", "updated_at_epoch": int(time.time())}
    prompt_sha = prompt_hash(
        prompt_content,
        "broker_reports_document_metadata_passport_prompt_v0",
        "document_metadata_passport_v0",
    )
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

conn = sqlite3.connect("/app/backend/data/webui.db")
conn.row_factory = sqlite3.Row
try:
    owner = conn.execute(
        "select id from user where role = 'admin' order by created_at asc limit 1"
    ).fetchone()
    if owner is None:
        owner = conn.execute("select id from user order by created_at asc limit 1").fetchone()
    if owner is None:
        raise RuntimeError("prompt_owner_missing")
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
                prompt_command,
                owner_id,
                "Broker Reports Document Metadata Passport",
                prompt_content,
                data_json,
                meta_json,
                prompt_version,
                tags_json,
                now,
                prompt_id,
            ),
        )
        action = "updated"
    else:
        conn.execute(
            """
            insert into prompt(
                id, command, user_id, name, content, data, meta, is_active,
                version_id, tags, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                prompt_command,
                owner_id,
                "Broker Reports Document Metadata Passport",
                prompt_content,
                data_json,
                meta_json,
                prompt_version,
                tags_json,
                now,
                now,
            ),
        )
        action = "created"
    conn.commit()
    row = conn.execute(
        "select id, command, version_id, tags, meta, length(content) as content_length from prompt where id = ?",
        (prompt_id,),
    ).fetchone()
    result = {
        "action": action,
        "prompt_ref": row["id"],
        "command": row["command"],
        "version": row["version_id"],
        "prompt_hash": prompt_hash_value,
        "content_length": row["content_length"],
        "tags": json.loads(row["tags"]),
        "output_schema_version": json.loads(row["meta"])["output_schema_version"],
        "template_id": json.loads(row["meta"])["template_id"],
    }
finally:
    conn.close()
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
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


def _seed_clarification_prompt(
    *,
    ssh_target: str,
    prompt_content: str,
    prompt_command: str,
    prompt_version: str,
) -> dict[str, Any]:
    meta = {
        "template_kind": "gate1_clarification_request",
        "template_id": "broker_reports.gate1_clarification_request.v0",
        "prompt_contract_id": "broker_reports_gate1_clarification_prompt_v0",
        "input_contract": "gate1_metadata_gap_report_v0",
        "output_schema_version": "gate1_clarification_request_v0",
        "output_schema_hash": gate1_clarification_request_schema_hash(),
        "gate": "gate1_5",
        "forbidden_tasks": [
            "source_fact_extraction",
            "tax_calculation",
            "declaration_generation",
            "xlsx_generation",
            "ocr_vlm",
            "knowledge_loading",
            "eligibility_decision",
        ],
    }
    tags = ["broker-reports-gate1", "metadata-clarification", "managed-prompt"]
    data = {"managed_by": "broker_reports_gate1_live_update", "updated_at_epoch": int(time.time())}
    prompt_sha = prompt_hash(
        prompt_content,
        "broker_reports_gate1_clarification_prompt_v0",
        "gate1_clarification_request_v0",
    )
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

conn = sqlite3.connect("/app/backend/data/webui.db")
conn.row_factory = sqlite3.Row
try:
    owner = conn.execute(
        "select id from user where role = 'admin' order by created_at asc limit 1"
    ).fetchone()
    if owner is None:
        owner = conn.execute("select id from user order by created_at asc limit 1").fetchone()
    if owner is None:
        raise RuntimeError("prompt_owner_missing")
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
                prompt_command,
                owner_id,
                "Broker Reports Gate 1 Metadata Clarification",
                prompt_content,
                data_json,
                meta_json,
                prompt_version,
                tags_json,
                now,
                prompt_id,
            ),
        )
        action = "updated"
    else:
        conn.execute(
            """
            insert into prompt(
                id, command, user_id, name, content, data, meta, is_active,
                version_id, tags, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                prompt_command,
                owner_id,
                "Broker Reports Gate 1 Metadata Clarification",
                prompt_content,
                data_json,
                meta_json,
                prompt_version,
                tags_json,
                now,
                now,
            ),
        )
        action = "created"
    conn.commit()
    row = conn.execute(
        "select id, command, version_id, tags, meta, length(content) as content_length from prompt where id = ?",
        (prompt_id,),
    ).fetchone()
    result = {
        "action": action,
        "prompt_ref": row["id"],
        "command": row["command"],
        "version": row["version_id"],
        "prompt_hash": prompt_hash_value,
        "content_length": row["content_length"],
        "tags": json.loads(row["tags"]),
        "output_schema_version": json.loads(row["meta"])["output_schema_version"],
        "output_schema_hash": json.loads(row["meta"])["output_schema_hash"],
        "template_id": json.loads(row["meta"])["template_id"],
    }
finally:
    conn.close()
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
'''
    replacements = {
        "__PROMPT_ID__": json.dumps(CLARIFICATION_PROMPT_ID, ensure_ascii=False),
        "__PROMPT_COMMAND__": json.dumps(prompt_command, ensure_ascii=False),
        "__PROMPT_VERSION__": json.dumps(prompt_version, ensure_ascii=False),
        "__PROMPT_CONTENT__": json.dumps(prompt_content, ensure_ascii=False),
        "__META_JSON__": json.dumps(json.dumps(meta, ensure_ascii=False), ensure_ascii=False),
        "__TAGS_JSON__": json.dumps(json.dumps(tags, ensure_ascii=False), ensure_ascii=False),
        "__DATA_JSON__": json.dumps(json.dumps(data, ensure_ascii=False), ensure_ascii=False),
        "__PROMPT_HASH__": json.dumps(prompt_sha, ensure_ascii=False),
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
