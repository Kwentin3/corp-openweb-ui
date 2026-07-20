#!/usr/bin/env python3
"""Run the synthetic restricted-scope proof inside the stage container."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
PROOF_PATH = SCRIPT_DIR / "prove_restricted_scope_stage_smoke.py"

sys.path.insert(0, str(SCRIPT_DIR))

from live_no_rag_source_intake_smoke import _default_ssh_target, _read_env


SNAPSHOT_CODE = r'''
import json
import os
import sqlite3
from pathlib import Path

def count(conn, table):
    try:
        return int(conn.execute(f"select count(*) from {table}").fetchone()[0])
    except Exception:
        return 0

def tree(path):
    root = Path(path)
    if not root.exists():
        return {"files": 0, "directories": 0, "bytes": 0}
    files = directories = size = 0
    for current, dirs, names in os.walk(root):
        directories += len(dirs)
        for name in names:
            files += 1
            try:
                size += (Path(current) / name).stat().st_size
            except OSError:
                pass
    return {"files": files, "directories": directories, "bytes": size}

db = {"files": 0, "documents": 0, "knowledge": 0}
try:
    with sqlite3.connect("/app/backend/data/webui.db") as conn:
        db = {
            "files": count(conn, "file"),
            "documents": count(conn, "document"),
            "knowledge": count(conn, "knowledge"),
        }
except Exception:
    pass

artifact_records = 0
artifact_db = Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
if artifact_db.exists():
    try:
        with sqlite3.connect(artifact_db) as conn:
            artifact_records = count(conn, "artifact_records")
    except Exception:
        pass

print(json.dumps({
    "db": db,
    "vector": tree("/app/backend/data/vector_db"),
    "artifact_records": artifact_records,
}, sort_keys=True))
'''


def _remote_python(ssh_target: str, code: str, *, timeout: int) -> str:
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
        input=code.encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "restricted_scope_stage_command_failed:"
            + completed.stderr.decode("utf-8", errors="replace").strip()[-2000:]
        )
    return completed.stdout.decode("utf-8", errors="strict")


def _snapshot(ssh_target: str) -> dict[str, Any]:
    value = json.loads(_remote_python(ssh_target, SNAPSHOT_CODE, timeout=45))
    if not isinstance(value, dict):
        raise RuntimeError("restricted_scope_stage_snapshot_invalid")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--ssh-target", default=None)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    ssh_target = (
        args.ssh_target
        or env.get("OPENWEBUI_SSH_TARGET")
        or _default_ssh_target(env)
    )
    bundle = BUNDLE_PATH.read_text(encoding="utf-8")
    bundle_sha = hashlib.sha256(bundle.encode("utf-8")).hexdigest()
    proof = PROOF_PATH.read_text(encoding="utf-8")
    proof = proof.replace("from __future__ import annotations\n\n", "", 1)
    proof = proof.replace("__REPOSITORY_BUNDLE_SHA256__", bundle_sha)
    remote_code = bundle + "\n" + proof

    before = _snapshot(ssh_target)
    proof_output = json.loads(_remote_python(ssh_target, remote_code, timeout=240))
    after = _snapshot(ssh_target)
    persistent_state_unchanged = before == after
    if proof_output.get("status") != "passed":
        raise RuntimeError("restricted_scope_stage_proof_failed")
    if not persistent_state_unchanged:
        raise RuntimeError("restricted_scope_stage_persistent_state_changed")

    output = {
        "schema_version": "broker_reports_restricted_scope_live_stage_smoke_safe_v1",
        "status": "passed",
        "proof": proof_output,
        "stage_execution": {
            "execution_mode": "ephemeral_synthetic_repository_bundle_in_stage_container",
            "repository_bundle_sha256": bundle_sha,
            "customer_documents_used": False,
            "persistent_db_vector_and_artifact_counts_unchanged": True,
            "repository_live_bundle_parity_verified_separately": True,
        },
        "privacy": {
            "customer_values_included": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
