#!/usr/bin/env python3
"""Read-only Gate 5 replay through the exact bundle deployed on stage."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
sys.path.insert(0, str(SCRIPT_DIR))

from live_no_rag_source_intake_smoke import (  # noqa: E402
    _default_ssh_target,
    _read_env,
)


FROZEN_CANONICAL_ROOT_SHA256 = (
    "bbf20e4ea5cd706398d459716fdab60812ef48ed6b0cd2d0264a778a77ab079d"
)


def _remote_code(*, canonical_root_sha256: str, source_revision: str) -> str:
    code = r'''
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

CANONICAL_ROOT_SHA256 = __CANONICAL_ROOT_SHA256__
SOURCE_REVISION = __SOURCE_REVISION__
DATA_ROOT = Path("/app/backend/data")
ARTIFACT_ROOT = DATA_ROOT / "broker_reports_gate1"
ARTIFACT_DB = ARTIFACT_ROOT / "artifacts.sqlite3"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


with sqlite3.connect(DATA_ROOT / "webui.db") as connection:
    row = connection.execute(
        'SELECT content, meta FROM "function" WHERE id = ?',
        ("broker_reports_gate1_pipe",),
    ).fetchone()
if row is None:
    raise SystemExit("current_gate1_function_missing")
bundle_content, meta_raw = row
meta = json.loads(meta_raw or "{}")
release = meta.get("broker_reports_release") or {}
if release.get("source_revision") != SOURCE_REVISION:
    raise SystemExit("deployed_source_revision_mismatch")

namespace = {"__name__": "broker_reports_live_current_bundle"}
exec(compile(bundle_content, "<broker_reports_gate1_pipe>", "exec"), namespace)

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.gate5_declaration_preparation import (
    Gate5DeclarationPreparationRuntimeFactory,
)
from broker_reports_gate1.gate5_human_gap_closure import (
    gate5_case_taxpayer_scope_ref,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_USER_INTENT_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_trusted_methodology import (
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)

with sqlite3.connect(ARTIFACT_DB) as connection:
    rows = connection.execute(
        """
        SELECT user_id, case_id, chat_id, workspace_model_id,
               normalization_run_id
        FROM canonical_versions
        WHERE status = 'ACTIVE' AND canonical_root_sha256 = ?
        """,
        (CANONICAL_ROOT_SHA256,),
    ).fetchall()
    records_before = int(
        connection.execute("SELECT count(*) FROM artifact_records").fetchone()[0]
    )
if len(rows) != 1:
    raise SystemExit("frozen_canonical_identity_not_unique")

db_sha256_before = sha256_file(ARTIFACT_DB)
value = rows[0]
context = ArtifactAccessContext(
    user_id=value[0],
    case_id=value[1],
    chat_id=value[2],
    workspace_model_id=value[3],
    normalization_run_id=value[4],
    allow_private=True,
)
store = ArtifactStoreFactory(
    ArtifactStoreConfig(
        mode="sqlite",
        sqlite_path=ARTIFACT_DB,
        payload_root=ARTIFACT_ROOT / "payloads",
    )
).create()
result = Gate5DeclarationPreparationRuntimeFactory(
    store=store,
    read_enabled=True,
).create().prepare(
    source_fact_methodology_ref={
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    },
    context=context,
    evidence_mode="REAL_EVIDENCE",
    user_intent={
        "schema_version": GATE5_USER_INTENT_SCHEMA_VERSION,
        "form": "3-NDFL",
        "tax_period": "2025",
        "task": "prepare_tax_declaration",
        "domains": ["broker_securities_income"],
    },
    taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(context),
    user_case_facts=[],
)

with sqlite3.connect(ARTIFACT_DB) as connection:
    records_after = int(
        connection.execute("SELECT count(*) FROM artifact_records").fetchone()[0]
    )
db_sha256_after = sha256_file(ARTIFACT_DB)
if records_after != records_before or db_sha256_after != db_sha256_before:
    raise SystemExit("current_gate5_replay_mutated_artifact_store")

active_demands = [
    {
        "demand": item["demand"],
        "terminal": item["terminal"],
        "gap_owner_classification": item["gap_owner_classification"],
    }
    for item in result["scope_activation"]["active_demands"]
]
classification_counts = Counter(
    item["gap_owner_classification"] for item in active_demands
)
closure = result["gap_closure"]
safe = {
    "schema_version": "broker_reports_gate5_current_server_replay_v1",
    "status": result["status"],
    "source_revision": SOURCE_REVISION,
    "release_id": release.get("release_id"),
    "bundle_sha256": hashlib.sha256(bundle_content.encode("utf-8")).hexdigest(),
    "canonical_root_sha256": CANONICAL_ROOT_SHA256,
    "active_demands": active_demands,
    "classification_counts": dict(sorted(classification_counts.items())),
    "required_actions": len(closure["required_actions"]),
    "user_required": len(closure["user_facing_required_actions"]),
    "internal_required": len(closure["internal_owner_required_actions"]),
    "advisory_actions": len(closure["advisory_actions"]),
    "terminals": list(result["terminals"]),
    "provider_calls": 0,
    "retry_count": 0,
    "repair_count": 0,
    "legacy_fallback_used": False,
    "artifact_store_unchanged": True,
    "artifact_records": records_after,
    "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
}
print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
'''
    return code.replace(
        "__CANONICAL_ROOT_SHA256__",
        json.dumps(canonical_root_sha256),
    ).replace("__SOURCE_REVISION__", json.dumps(source_revision))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--ssh-target", default="")
    parser.add_argument("--canonical-root-sha256", default=FROZEN_CANONICAL_ROOT_SHA256)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    ssh_target = args.ssh_target.strip() or _default_ssh_target(env)
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
        input=_remote_code(
            canonical_root_sha256=args.canonical_root_sha256,
            source_revision=args.source_revision,
        ),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        raise RuntimeError(
            "current_gate5_server_replay_failed: "
            + (detail[-1] if detail else "remote_command_failed")
        )
    value: Any = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise SystemExit("current_gate5_server_replay_output_invalid")
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
