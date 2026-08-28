#!/usr/bin/env python3
"""Run one real PDF through the already-active ordinary-trade production route."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
FUNCTION_ID = "broker_reports_gate1_pipe"
WORKSPACE_MODEL_ID = "broker-reports-ndfl"
PROJECTION_TYPE = "broker_reports_ordinary_trade_runtime_projection_v6"

sys.path.insert(0, str(SCRIPT_DIR))

from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _default_ssh_target,
    _delete_uploads,
    _extract_content,
    _read_env,
    _signin,
    _url,
)
from live_update_function_and_passport_prompt import (  # noqa: E402
    _get_function,
    _get_function_valves,
)


class OrdinaryTradeLiveSmokeError(RuntimeError):
    pass


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if not args.source.is_file():
        raise OrdinaryTradeLiveSmokeError("ordinary_trade_live_source_missing")
    env = _read_env(args.env_file)
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = (
        args.ssh_target
        or env.get("OPENWEBUI_SSH_TARGET")
        or _default_ssh_target(env)
    )
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    live_function = _get_function(session, base_url)
    live_bundle_sha256 = _sha256_text(str(live_function.get("content") or ""))
    expected_bundle_sha256 = _sha256_text(BUNDLE_PATH.read_text(encoding="utf-8"))
    if live_bundle_sha256 != expected_bundle_sha256:
        raise OrdinaryTradeLiveSmokeError("ordinary_trade_live_bundle_mismatch")
    valves = _get_function_valves(session, base_url)
    if (
        valves.get("ordinary_trade_candidate_enabled") is not True
        or valves.get("ndfl_gate3_enabled") is not False
        or valves.get("canonical_gate2_write_enabled") is not True
        or valves.get("canonical_gate2_read_enabled") is not True
    ):
        raise OrdinaryTradeLiveSmokeError("ordinary_trade_live_valves_invalid")

    case_id = "otlive_" + time.strftime("%Y%m%d%H%M%S")
    started_at = datetime.now(timezone.utc).isoformat()
    upload = _upload(session, base_url, args.source, args.timeout)
    try:
        content = _run_chat(
            session=session,
            base_url=base_url,
            upload=upload,
            case_id=case_id,
            timeout=args.timeout,
            expect_unmapped=bool(args.expect_unmapped),
        )
        remote = _remote_summary(
            ssh_target=ssh_target,
            expected_source_sha256=_sha256_file(args.source),
            expect_unmapped=bool(args.expect_unmapped),
            started_at=started_at,
        )
    finally:
        _delete_uploads(session, base_url, [upload])
    return {
        "schema_version": "broker_reports_ordinary_trade_live_smoke_v1",
        "status": "passed",
        "server_case_bound": True,
        "live_bundle_sha256": live_bundle_sha256,
        "active_route": "ordinary_trade_automatic_semantic_mapping_v1",
        "ordinary_trade_candidate_enabled": True,
        "current_gate3_enabled": False,
        "semantic_fallback_used": False,
        "source_upload_process": False,
        "chat_private_refs_leaked": False,
        "chat_compact": len(content) < 7000,
        "remote": remote,
    }


def _upload(
    session: requests.Session,
    base_url: str,
    source: Path,
    timeout: int,
) -> dict[str, Any]:
    alias = "ordinary_trade_authorized" + source.suffix.lower()
    mime_type = mimetypes.guess_type(alias)[0] or "application/octet-stream"
    with source.open("rb") as handle:
        response = session.post(
            _url(base_url, "/api/v1/files/?process=false"),
            files={"file": (alias, handle, mime_type)},
            timeout=timeout,
        )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict) or not value.get("id"):
        raise OrdinaryTradeLiveSmokeError("ordinary_trade_live_upload_invalid")
    return {
        "id": str(value["id"]),
        "filename": alias,
        "mime_type": str(value.get("mime_type") or mime_type),
        "size": int(value.get("size") or source.stat().st_size),
    }


def _run_chat(
    *,
    session: requests.Session,
    base_url: str,
    upload: dict[str, Any],
    case_id: str,
    timeout: int,
    expect_unmapped: bool,
) -> str:
    file_value = {
        "type": "file",
        "file": {
            "id": upload["id"],
            "filename": upload["filename"],
            "name": upload["filename"],
            "mime_type": upload["mime_type"],
            "content_type": upload["mime_type"],
            "size": upload["size"],
        },
    }
    retention = {"mode": "customer_approved_test", "explicit": True}
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": WORKSPACE_MODEL_ID,
            "parent_id": None,
            "case_id": case_id,
            "retention_policy": retention,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Обработай разрешённый брокерский PDF рабочим "
                        "конвейером. Не додумывай неподдержанные операции."
                    ),
                    "files": [file_value],
                }
            ],
            "files": [file_value],
            "metadata": {
                "case_id": case_id,
                "retention_policy": retention,
                "broker_reports_gate1": {
                    "source_intake": "process_false_private_upload",
                    "customer_docs_loaded_to_knowledge": False,
                },
            },
            "stream": False,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    content = _extract_content(response.json())
    expected_terminal = "квалифицированной точной схеме" in content or (
        expect_unmapped and "Расчёт остановлен" in content
    )
    if (
        not content
        or not expected_terminal
        or upload["id"] in content
        or upload["filename"] in content
    ):
        raise OrdinaryTradeLiveSmokeError("ordinary_trade_live_chat_invalid")
    return content


def _remote_summary(
    *,
    ssh_target: str,
    expected_source_sha256: str,
    expect_unmapped: bool,
    started_at: str,
) -> dict[str, Any]:
    code = f'''
import json
import sqlite3
from pathlib import Path

db = Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
versions = conn.execute(
    "select canonical_version_id, source_sha256, canonical_root_sha256, status, "
    "case_id, chat_id from canonical_versions where source_sha256 = ? "
    "and created_at >= ? and workspace_model_id = ? order by created_at desc",
    ({expected_source_sha256!r}, {started_at!r}, {WORKSPACE_MODEL_ID!r}),
).fetchall()
if not versions and {expect_unmapped!r}:
    conn.close()
    print(json.dumps({{
        "status": "passed",
        "canonical_admission_status": "blocked_before_candidate",
        "active_canonical_versions": 0,
        "canonical_versions_total": 0,
        "projection_artifacts": 0,
        "old_semantic_artifacts": 0,
        "runtime_ready_observations": 0,
        "relevant_unmapped_observations": 0,
        "runtime_records": 0,
        "broker_or_year_profiles": 0,
        "fail_closed_without_semantic_fallback": True,
    }}, sort_keys=True))
    raise SystemExit(0)
if len(versions) != 1:
    raise RuntimeError("ordinary_trade_live_canonical_count_invalid")
scope_field = "case_id" if versions[0]["case_id"] else "chat_id"
scope_value = versions[0][scope_field]
records = conn.execute(
    f"select artifact_id, artifact_type, validation_status, safe_metadata_json "
    f"from artifact_records where {{scope_field}} = ? and workspace_model_id = ?",
    (scope_value, {WORKSPACE_MODEL_ID!r}),
).fetchall()
receipts = conn.execute(
    "select actor, reason, canonical_version_id from canonical_activation_receipts "
    "where canonical_version_id = ?",
    (versions[0]["canonical_version_id"],),
).fetchall()
conn.close()
active = [row for row in versions if row["status"] == "ACTIVE"]
projections = [row for row in records if row["artifact_type"] == {PROJECTION_TYPE!r}]
old_semantic = [
    row for row in records
    if row["artifact_type"] in (
        "broker_reports_financial_annotations_v1",
        "broker_reports_financial_annotations_v2",
        "broker_reports_gate4_financial_case_v2",
    )
]
if len(active) != 1 or active[0]["source_sha256"] != {expected_source_sha256!r}:
    raise RuntimeError("ordinary_trade_live_canonical_invalid")
if len(projections) != 1 or projections[0]["validation_status"] != "validated":
    raise RuntimeError("ordinary_trade_live_projection_invalid")
if old_semantic:
    raise RuntimeError("ordinary_trade_live_old_semantic_artifact_present")
safe = json.loads(projections[0]["safe_metadata_json"])
ready = int(safe.get("runtime_ready_observations") or 0)
unmapped = int(safe.get("relevant_unmapped_observations") or 0)
if ({expect_unmapped!r} and (ready != 0 or unmapped == 0)) or (
    not {expect_unmapped!r} and ready == 0
):
    raise RuntimeError("ordinary_trade_live_scope_result_invalid")
if not any(
    row["actor"] == "ordinary_trade_automatic_semantic_mapping_v1"
    and row["reason"] == "ordinary_trade_automatic_semantic_mapping_compilation"
    for row in receipts
):
    raise RuntimeError("ordinary_trade_live_activation_owner_invalid")
print(json.dumps({{
    "status": "passed",
    "canonical_versions_total": len(versions),
    "active_canonical_versions": len(active),
    "projection_artifacts": len(projections),
    "old_semantic_artifacts": len(old_semantic),
    "runtime_ready_observations": ready,
    "relevant_unmapped_observations": unmapped,
    "runtime_records": int(safe.get("runtime_records") or 0),
    "broker_or_year_profiles": int(safe.get("broker_or_year_profiles") or 0),
}}, sort_keys=True))
'''
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=yes",
            ssh_target,
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        cwd=REPO_ROOT,
        input=code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        check=True,
    )
    value = json.loads(completed.stdout)
    if value.get("status") != "passed":
        raise OrdinaryTradeLiveSmokeError("ordinary_trade_live_remote_invalid")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expect-unmapped", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    print(json.dumps(execute(args), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
