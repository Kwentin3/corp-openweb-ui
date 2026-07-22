#!/usr/bin/env python3
"""Remote half of the Broker Reports atomic stage release.

The local release driver copies this file and a validated release payload to a
restricted stage directory.  This program must run on the stage host as root.
It updates all maintained Function and managed Prompt rows in one SQLite
transaction while the OpenWebUI container is stopped. Any failure restores the
exact previous rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping


ROOT = Path("/opt/openwebui-prd0")
STAGING_ROOT = ROOT / ".broker-reports-release-staging"
ROLLBACK_ROOT = ROOT / ".broker-reports-rollbacks"
ENV_PATH = ROOT / ".env"
LOADER_PATH = ROOT / "deploy" / "openwebui-static" / "loader.js"
CONTAINER = "openwebui"
VOLUME = "openwebui_data"
STAGING_NAME_RE = re.compile(r"^broker-reports-[0-9a-f]{12}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_WORKLOAD_STATES = {"completed", "failed", "cancelled"}


class StageReleaseError(RuntimeError):
    pass


def _raise_release_signal(signum: int, _frame: Any) -> None:
    raise StageReleaseError(f"stage_release_interrupted_by_signal:{signum}")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StageReleaseError("stage_release_json_object_required")
    return value


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise StageReleaseError("stage_release_live_json_invalid") from exc
    if not isinstance(parsed, dict):
        raise StageReleaseError("stage_release_live_json_object_required")
    return parsed


def _run(
    args: list[str],
    *,
    check: bool = True,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )


def _validated_staging_dir(value: str) -> Path:
    path = Path(value)
    try:
        resolved = path.resolve(strict=True)
        root = STAGING_ROOT.resolve(strict=True)
    except OSError as exc:
        raise StageReleaseError("stage_release_staging_directory_missing") from exc
    if resolved.parent != root or not STAGING_NAME_RE.fullmatch(resolved.name):
        raise StageReleaseError("stage_release_staging_directory_invalid")
    return resolved


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != "broker_reports_atomic_stage_release_v2":
        raise StageReleaseError("stage_release_manifest_schema_invalid")
    release_id = str(manifest.get("release_id") or "")
    if not STAGING_NAME_RE.fullmatch(release_id):
        raise StageReleaseError("stage_release_manifest_release_id_invalid")
    supplied = str(manifest.get("manifest_sha256") or "")
    if not SHA256_RE.fullmatch(supplied):
        raise StageReleaseError("stage_release_manifest_digest_invalid")
    material = dict(manifest)
    material.pop("manifest_sha256", None)
    if _sha256_text(_canonical_json(material)) != supplied:
        raise StageReleaseError("stage_release_manifest_digest_mismatch")


def _validate_payload(staging_dir: Path, manifest: Mapping[str, Any]) -> None:
    if staging_dir.name != manifest.get("release_id"):
        raise StageReleaseError("stage_release_staging_release_id_mismatch")
    for item in manifest.get("functions", []):
        if not isinstance(item, dict):
            raise StageReleaseError("stage_release_function_contract_invalid")
        bundle_name = str(item.get("bundle_name") or "")
        if Path(bundle_name).name != bundle_name or not bundle_name.endswith(".py"):
            raise StageReleaseError("stage_release_bundle_name_invalid")
        path = staging_dir / bundle_name
        content = path.read_text(encoding="utf-8")
        if _sha256_text(content) != item.get("content_sha256"):
            raise StageReleaseError("stage_release_bundle_digest_mismatch")
        markers = item.get("required_markers") or []
        if not all(str(marker) in content for marker in markers):
            raise StageReleaseError("stage_release_bundle_markers_missing")
    prompts = manifest.get("managed_prompts") or []
    if not prompts or any(not isinstance(item, dict) for item in prompts):
        raise StageReleaseError("stage_release_prompt_contract_invalid")
    prompt_ids = [str(item.get("prompt_id") or "") for item in prompts]
    if len(prompt_ids) != len(set(prompt_ids)) or any(not item for item in prompt_ids):
        raise StageReleaseError("stage_release_prompt_set_invalid")
    for item in prompts:
        content = item.get("content")
        if (
            not isinstance(content, str)
            or not content.strip()
            or _sha256_text(content) != item.get("content_sha256")
            or not str(item.get("command") or "")
            or not str(item.get("version") or "")
            or not isinstance(item.get("meta"), dict)
        ):
            raise StageReleaseError("stage_release_prompt_contract_invalid")


def _volume_mount() -> Path:
    value = json.loads(_run(["docker", "volume", "inspect", VOLUME]).stdout)
    if not isinstance(value, list) or len(value) != 1:
        raise StageReleaseError("stage_release_volume_inspect_invalid")
    mountpoint = Path(str(value[0].get("Mountpoint") or ""))
    if not mountpoint.is_dir():
        raise StageReleaseError("stage_release_volume_mount_missing")
    return mountpoint


def _webui_db(data_root: Path) -> Path:
    path = data_root / "webui.db"
    if not path.is_file():
        raise StageReleaseError("stage_release_webui_db_missing")
    return path


def _function_rows(db_path: Path, function_ids: list[str]) -> dict[str, dict[str, Any]]:
    placeholders = ",".join("?" for _ in function_ids)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, content, meta, valves, type, is_active, is_global, updated_at "
            f"FROM function WHERE id IN ({placeholders}) ORDER BY id",
            tuple(function_ids),
        ).fetchall()
    finally:
        conn.close()
    result = {str(row["id"]): dict(row) for row in rows}
    if set(result) != set(function_ids):
        raise StageReleaseError("stage_release_function_set_missing")
    return result


def _prompt_rows(db_path: Path, prompt_ids: list[str]) -> dict[str, dict[str, Any]]:
    placeholders = ",".join("?" for _ in prompt_ids)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, command, version_id, is_active, content, meta, updated_at "
            f"FROM prompt WHERE id IN ({placeholders}) ORDER BY id",
            tuple(prompt_ids),
        ).fetchall()
    finally:
        conn.close()
    result = {str(row["id"]): dict(row) for row in rows}
    if set(result) != set(prompt_ids):
        raise StageReleaseError("stage_release_prompt_set_missing")
    return result


def _safe_function_state(
    rows: Mapping[str, Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    result = []
    for contract in manifest.get("functions", []):
        function_id = str(contract["function_id"])
        row = rows[function_id]
        meta = _json_object(row.get("meta"))
        release_meta = _json_object(meta.get("broker_reports_release"))
        valves = _json_object(row.get("valves"))
        expected_valves = _json_object(contract.get("valves"))
        result.append(
            {
                "function_id": function_id,
                "content_sha256": _sha256_text(str(row.get("content") or "")),
                "active": row.get("is_active") in (1, True),
                "global": row.get("is_global") in (1, True),
                "type": row.get("type"),
                "release_revision": release_meta.get("source_revision"),
                "release_manifest_sha256": release_meta.get("manifest_sha256"),
                "valves": {
                    key: valves.get(key) for key in sorted(expected_valves)
                },
            }
        )
    return result


def _action_state(db_path: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    action = _json_object(manifest.get("action"))
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, content, type, is_active, is_global FROM function WHERE id = ?",
            (action.get("action_id"),),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise StageReleaseError("stage_release_action_missing")
    return {
        "action_id": row["id"],
        "content_sha256": _sha256_text(str(row["content"] or "")),
        "type": row["type"],
        "active": row["is_active"] in (1, True),
        "global": row["is_global"] in (1, True),
    }


def _prompt_states(db_path: Path, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    prompts = manifest.get("managed_prompts") or []
    ids = [str(item["prompt_id"]) for item in prompts]
    placeholders = ",".join("?" for _ in ids)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, command, version_id, is_active, content, meta FROM prompt "
            f"WHERE id IN ({placeholders})",
            tuple(ids),
        ).fetchall()
    finally:
        conn.close()
    by_id = {str(row["id"]): row for row in rows}
    result = []
    for expected in prompts:
        prompt_id = str(expected["prompt_id"])
        row = by_id.get(prompt_id)
        if row is None:
            result.append({"prompt_id": prompt_id, "present": False})
            continue
        live_meta = _json_object(row["meta"])
        expected_meta = _json_object(expected.get("meta"))
        result.append(
            {
                "prompt_id": prompt_id,
                "present": True,
                "active": row["is_active"] in (1, True),
                "command": row["command"],
                "version": row["version_id"],
                "content_sha256": _sha256_text(str(row["content"] or "")),
                "metadata_match": all(
                    live_meta.get(key) == value
                    for key, value in expected_meta.items()
                ),
            }
        )
    return result


def _image_state() -> dict[str, Any]:
    container = json.loads(_run(["docker", "inspect", CONTAINER]).stdout)[0]
    image = json.loads(
        _run(["docker", "image", "inspect", str(container["Image"])]).stdout
    )[0]
    labels = image.get("Config", {}).get("Labels") or {}
    return {
        "configured_image": container.get("Config", {}).get("Image"),
        "image_id": container.get("Image"),
        "running": bool(container.get("State", {}).get("Running")),
        "restart_count": int(container.get("RestartCount") or 0),
        "source_revision": labels.get("org.opencontainers.image.revision"),
        "private_intake_contract": labels.get(
            "ai.alpha-soft.broker-reports-private-intake"
        ),
    }


def _fitz_version() -> str:
    code = "import fitz; print(fitz.__version__)"
    completed = _run(
        ["docker", "exec", CONTAINER, "python", "-c", code],
        timeout=60,
    )
    return completed.stdout.strip()


def _loader_state() -> dict[str, Any]:
    if not LOADER_PATH.is_file():
        raise StageReleaseError("stage_release_loader_missing")
    return {"content_sha256": _sha256_bytes(LOADER_PATH.read_bytes())}


def _database_counters(db_path: Path, data_root: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        result = {
            f"{table}_rows": int(
                conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
            for table in ("document", "file", "knowledge")
            if table in tables
        }
    finally:
        conn.close()
    vector_root = data_root / "vector_db"
    vector_files = 0
    vector_bytes = 0
    if vector_root.is_dir():
        for base, _dirs, names in os.walk(vector_root):
            for name in names:
                path = Path(base) / name
                vector_files += 1
                vector_bytes += path.stat().st_size
    result["vector_files"] = vector_files
    result["vector_bytes"] = vector_bytes
    return result


def _workload_state(data_root: Path) -> dict[str, Any]:
    db_path = data_root / "broker_reports_gate1" / "workloads.sqlite3"
    state_counts: dict[str, int] = {}
    if db_path.is_file():
        conn = sqlite3.connect(db_path)
        try:
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'workload_jobs'"
            ).fetchone()
            if table is not None:
                state_counts = {
                    str(state): int(count)
                    for state, count in conn.execute(
                        "SELECT state, COUNT(*) FROM workload_jobs GROUP BY state"
                    )
                }
        finally:
            conn.close()
    nonterminal = sum(
        count
        for state, count in state_counts.items()
        if state not in TERMINAL_WORKLOAD_STATES
    )
    temp_root = data_root / "broker_reports_gate1" / "workload-temp"
    temp_entries = (
        sum(1 for item in temp_root.iterdir() if item.name.startswith("brjob_"))
        if temp_root.is_dir()
        else 0
    )
    return {
        "state_counts": state_counts,
        "nonterminal_jobs": nonterminal,
        "owned_temp_entries": temp_entries,
    }


def _live_state(
    *,
    db_path: Path,
    data_root: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    function_ids = [str(item["function_id"]) for item in manifest["functions"]]
    rows = _function_rows(db_path, function_ids)
    return {
        "functions": _safe_function_state(rows, manifest),
        "action": _action_state(db_path, manifest),
        "managed_prompts": _prompt_states(db_path, manifest),
        "image": _image_state(),
        "loader": _loader_state(),
        "fitz_version": _fitz_version(),
        "workload": _workload_state(data_root),
        "counters": _database_counters(db_path, data_root),
    }


def _assert_static_contracts(state: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    expected_image = manifest["image"]
    image = state["image"]
    for key in (
        "configured_image",
        "image_id",
        "source_revision",
        "private_intake_contract",
    ):
        if image.get(key) != expected_image.get(key):
            raise StageReleaseError(f"stage_release_image_{key}_mismatch")
    if image.get("running") is not True or image.get("restart_count") != 0:
        raise StageReleaseError("stage_release_image_runtime_state_invalid")
    expected_action = manifest["action"]
    action = state["action"]
    if (
        action.get("action_id") != expected_action.get("action_id")
        or action.get("content_sha256") != expected_action.get("content_sha256")
        or action.get("type") != "action"
        or action.get("active") is not True
        or action.get("global") is not False
    ):
        raise StageReleaseError("stage_release_action_contract_mismatch")
    if state.get("loader") != manifest.get("loader"):
        raise StageReleaseError("stage_release_loader_contract_mismatch")
    if state.get("fitz_version") != manifest["runtime"]["fitz_version"]:
        raise StageReleaseError("stage_release_runtime_dependency_mismatch")


def _assert_prompt_set_present(
    state: Mapping[str, Any], manifest: Mapping[str, Any]
) -> None:
    expected_prompts = {
        str(item["prompt_id"]): item for item in manifest["managed_prompts"]
    }
    live_prompts = {str(item["prompt_id"]): item for item in state["managed_prompts"]}
    if set(live_prompts) != set(expected_prompts):
        raise StageReleaseError("stage_release_prompt_set_mismatch")
    if any(item.get("present") is not True for item in live_prompts.values()):
        raise StageReleaseError("stage_release_prompt_set_missing")


def _assert_prompt_contracts(
    state: Mapping[str, Any], manifest: Mapping[str, Any]
) -> None:
    _assert_prompt_set_present(state, manifest)
    expected_prompts = {
        str(item["prompt_id"]): item for item in manifest["managed_prompts"]
    }
    live_prompts = {str(item["prompt_id"]): item for item in state["managed_prompts"]}
    for prompt_id, expected in expected_prompts.items():
        live = live_prompts[prompt_id]
        if (
            live.get("present") is not True
            or live.get("active") is not True
            or live.get("command") != expected.get("command")
            or live.get("version") != expected.get("version")
            or live.get("content_sha256") != expected.get("content_sha256")
            or live.get("metadata_match") is not True
        ):
            raise StageReleaseError("stage_release_prompt_contract_mismatch")


def _assert_quiescent(state: Mapping[str, Any]) -> None:
    workload = state["workload"]
    if workload.get("nonterminal_jobs") != 0:
        raise StageReleaseError("stage_release_workload_not_quiescent")
    if workload.get("owned_temp_entries") != 0:
        raise StageReleaseError("stage_release_workload_temp_not_clean")


def _assert_candidate(state: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    expected = {str(item["function_id"]): item for item in manifest["functions"]}
    live = {str(item["function_id"]): item for item in state["functions"]}
    if set(live) != set(expected):
        raise StageReleaseError("stage_release_live_function_set_mismatch")
    for function_id, contract in expected.items():
        item = live[function_id]
        if (
            item.get("content_sha256") != contract.get("content_sha256")
            or item.get("active") is not True
            or item.get("global") is not False
            or item.get("type") != "pipe"
            or item.get("release_revision") != manifest.get("source_revision")
            or item.get("release_manifest_sha256")
            != manifest.get("manifest_sha256")
            or item.get("valves") != contract.get("valves")
        ):
            raise StageReleaseError(
                "stage_release_candidate_function_mismatch:" + function_id
            )
    _assert_prompt_contracts(state, manifest)


def _snapshot_function_rows(
    rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        function_id: {
            key: row.get(key)
            for key in (
                "content",
                "meta",
                "valves",
                "type",
                "is_active",
                "is_global",
                "updated_at",
            )
        }
        for function_id, row in rows.items()
    }


def _snapshot_prompt_rows(
    rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        prompt_id: {
            key: row.get(key)
            for key in (
                "command",
                "version_id",
                "is_active",
                "content",
                "meta",
                "updated_at",
            )
        }
        for prompt_id, row in rows.items()
    }


def _rollback_artifact(
    *,
    manifest: Mapping[str, Any],
    function_rows: Mapping[str, Mapping[str, Any]],
    prompt_rows: Mapping[str, Mapping[str, Any]],
    before_state: Mapping[str, Any],
) -> tuple[dict[str, Any], str, bool]:
    release_id = str(manifest["release_id"])
    rollback_dir = ROLLBACK_ROOT / release_id
    rollback_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(rollback_dir, 0o700)
    path = rollback_dir / "function_rows.rollback.json"
    value = {
        "schema_version": "broker_reports_atomic_stage_rollback_v2",
        "release_id": release_id,
        "source_revision": manifest["source_revision"],
        "manifest_sha256": manifest["manifest_sha256"],
        "previous_function_rows": _snapshot_function_rows(function_rows),
        "previous_prompt_rows": _snapshot_prompt_rows(prompt_rows),
        "previous_object_identities": {
            "functions": before_state["functions"],
            "action": before_state["action"],
            "image": before_state["image"],
            "loader": before_state["loader"],
            "managed_prompts": before_state["managed_prompts"],
        },
    }
    encoded = (_canonical_json(value) + "\n").encode("utf-8")
    created = False
    if path.exists():
        existing = path.read_bytes()
        existing_value = json.loads(existing)
        if (
            existing_value.get("release_id") != release_id
            or existing_value.get("source_revision") != manifest["source_revision"]
            or existing_value.get("manifest_sha256") != manifest["manifest_sha256"]
        ):
            raise StageReleaseError("stage_release_rollback_identity_conflict")
        value = existing_value
        encoded = existing
    else:
        fd, temp_name = tempfile.mkstemp(
            prefix=".function_rows.", suffix=".tmp", dir=rollback_dir
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
            created = True
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    os.chmod(path, 0o600)
    return value, _sha256_bytes(encoded), created


def _desired_rows(
    *,
    staging_dir: Path,
    manifest: Mapping[str, Any],
    current_rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    now = int(time.time())
    for contract in manifest["functions"]:
        function_id = str(contract["function_id"])
        current = current_rows[function_id]
        content = (staging_dir / str(contract["bundle_name"])).read_text(
            encoding="utf-8"
        )
        meta = _json_object(current.get("meta"))
        meta["broker_reports_release"] = {
            "schema_version": manifest["schema_version"],
            "source_revision": manifest["source_revision"],
            "manifest_sha256": manifest["manifest_sha256"],
            "bundle_sha256": contract["content_sha256"],
        }
        valves = {
            **_json_object(current.get("valves")),
            **_json_object(contract.get("valves")),
        }
        result[function_id] = {
            "content": content,
            "meta": _canonical_json(meta),
            "valves": _canonical_json(valves),
            "type": "pipe",
            "is_active": 1,
            "is_global": 0,
            "updated_at": now,
        }
    return result


def _desired_prompt_rows(
    *,
    manifest: Mapping[str, Any],
    current_rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    now = int(time.time())
    for contract in manifest["managed_prompts"]:
        prompt_id = str(contract["prompt_id"])
        current = current_rows[prompt_id]
        meta = {
            **_json_object(current.get("meta")),
            **_json_object(contract.get("meta")),
        }
        unchanged = (
            current.get("command") == contract.get("command")
            and current.get("version_id") == contract.get("version")
            and current.get("is_active") in (1, True)
            and current.get("content") == contract.get("content")
            and _json_object(current.get("meta")) == meta
        )
        result[prompt_id] = {
            "command": str(contract["command"]),
            "version_id": str(contract["version"]),
            "is_active": 1,
            "content": str(contract["content"]),
            "meta": (
                current.get("meta") if unchanged else _canonical_json(meta)
            ),
            "updated_at": current.get("updated_at") if unchanged else now,
        }
    return result


def _replace_release_rows(
    *,
    db_path: Path,
    replacement_function_rows: Mapping[str, Mapping[str, Any]],
    replacement_prompt_rows: Mapping[str, Mapping[str, Any]],
    expected_function_hashes: Mapping[str, str] | None,
    expected_prompt_hashes: Mapping[str, str] | None,
) -> None:
    conn = sqlite3.connect(db_path, timeout=60)
    try:
        conn.execute("PRAGMA busy_timeout = 60000")
        conn.execute("BEGIN IMMEDIATE")
        try:
            for function_id in sorted(replacement_function_rows):
                current = conn.execute(
                    "SELECT content FROM function WHERE id = ?", (function_id,)
                ).fetchone()
                if current is None:
                    raise StageReleaseError("stage_release_function_missing_during_write")
                if expected_function_hashes is not None:
                    current_hash = _sha256_text(str(current[0] or ""))
                    if current_hash != expected_function_hashes.get(function_id):
                        raise StageReleaseError(
                            "stage_release_function_changed_during_release:"
                            + function_id
                        )
            for prompt_id in sorted(replacement_prompt_rows):
                current = conn.execute(
                    "SELECT command, version_id, is_active, content, meta, updated_at "
                    "FROM prompt WHERE id = ?",
                    (prompt_id,),
                ).fetchone()
                if current is None:
                    raise StageReleaseError("stage_release_prompt_missing_during_write")
                if expected_prompt_hashes is not None:
                    current_hash = _prompt_row_hash(dict(zip(
                        (
                            "command",
                            "version_id",
                            "is_active",
                            "content",
                            "meta",
                            "updated_at",
                        ),
                        current,
                    )))
                    if current_hash != expected_prompt_hashes.get(prompt_id):
                        raise StageReleaseError(
                            "stage_release_prompt_changed_during_release:" + prompt_id
                        )
            for function_id in sorted(replacement_function_rows):
                row = replacement_function_rows[function_id]
                updated = conn.execute(
                    "UPDATE function SET content = ?, meta = ?, valves = ?, type = ?, "
                    "is_active = ?, is_global = ?, updated_at = ? WHERE id = ?",
                    (
                        row.get("content"),
                        row.get("meta"),
                        row.get("valves"),
                        row.get("type"),
                        row.get("is_active"),
                        row.get("is_global"),
                        row.get("updated_at"),
                        function_id,
                    ),
                )
                if updated.rowcount != 1:
                    raise StageReleaseError("stage_release_function_update_count_invalid")
            for prompt_id in sorted(replacement_prompt_rows):
                row = replacement_prompt_rows[prompt_id]
                updated = conn.execute(
                    "UPDATE prompt SET command = ?, version_id = ?, is_active = ?, "
                    "content = ?, meta = ?, updated_at = ? WHERE id = ?",
                    (
                        row.get("command"),
                        row.get("version_id"),
                        row.get("is_active"),
                        row.get("content"),
                        row.get("meta"),
                        row.get("updated_at"),
                        prompt_id,
                    ),
                )
                if updated.rowcount != 1:
                    raise StageReleaseError("stage_release_prompt_update_count_invalid")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.close()


def _content_hashes(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    return {
        function_id: _sha256_text(str(row.get("content") or ""))
        for function_id, row in rows.items()
    }


def _prompt_row_hash(row: Mapping[str, Any]) -> str:
    return _sha256_text(
        _canonical_json(
            {
                key: row.get(key)
                for key in (
                    "command",
                    "version_id",
                    "is_active",
                    "content",
                    "meta",
                    "updated_at",
                )
            }
        )
    )


def _prompt_hashes(
    rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    return {
        prompt_id: _prompt_row_hash(row)
        for prompt_id, row in rows.items()
    }


def _container_running() -> bool:
    completed = _run(
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER],
        check=False,
        timeout=30,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _stop_container() -> None:
    if _container_running():
        _run(["docker", "stop", "--time", "30", CONTAINER], timeout=90)
    if _container_running():
        raise StageReleaseError("stage_release_container_stop_failed")


def _start_container() -> None:
    if not _container_running():
        _run(["docker", "start", CONTAINER], timeout=90)


def _external_url() -> str:
    text = ENV_PATH.read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^OPENWEBUI_HOST=(.*)$", text)
    if not matches:
        raise StageReleaseError("stage_release_external_host_missing")
    host = matches[-1].strip().strip('"').strip("'")
    if not host:
        raise StageReleaseError("stage_release_external_host_missing")
    return host.rstrip("/") if host.startswith(("http://", "https://")) else "https://" + host.rstrip("/")


def _wait_healthy() -> None:
    external_url = _external_url()
    deadline = time.time() + 180
    last = "not_started"
    while time.time() < deadline:
        if not _container_running():
            last = "container_not_running"
            time.sleep(2)
            continue
        health = _run(
            [
                "docker",
                "exec",
                CONTAINER,
                "python",
                "-c",
                (
                    "import urllib.request;"
                    "r=urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=5);"
                    "assert r.status==200"
                ),
            ],
            check=False,
            timeout=20,
        )
        api_code = """\
import urllib.error
import urllib.request
request = urllib.request.Request(
    'http://127.0.0.1:8080/api/v1/auths/signin',
    data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
try:
    urllib.request.urlopen(request, timeout=5)
except urllib.error.HTTPError as error:
    assert error.code in {400, 401, 422}
"""
        api = _run(
            ["docker", "exec", CONTAINER, "python", "-c", api_code],
            check=False,
            timeout=20,
        )
        ingress_code = """\
import sys
import urllib.error
import urllib.request
request = urllib.request.Request(
    sys.argv[1] + '/api/v1/auths/signin',
    data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
try:
    urllib.request.urlopen(request, timeout=5)
except urllib.error.HTTPError as error:
    assert error.code in {400, 401, 422}
"""
        ingress = _run(
            ["python3", "-c", ingress_code, external_url],
            check=False,
            timeout=20,
        )
        if health.returncode == api.returncode == ingress.returncode == 0:
            return
        last = "application_or_ingress_not_ready"
        time.sleep(2)
    raise StageReleaseError("stage_release_health_timeout:" + last)


def _restore_after_failure(
    *,
    db_path: Path,
    rollback_function_rows: Mapping[str, Mapping[str, Any]],
    rollback_prompt_rows: Mapping[str, Mapping[str, Any]],
) -> None:
    _stop_container()
    _replace_release_rows(
        db_path=db_path,
        replacement_function_rows=rollback_function_rows,
        replacement_prompt_rows=rollback_prompt_rows,
        expected_function_hashes=None,
        expected_prompt_hashes=None,
    )
    _start_container()
    _wait_healthy()


def execute(*, staging_dir: Path, apply: bool, prove_rollback: bool) -> dict[str, Any]:
    manifest = _read_json(staging_dir / "manifest.json")
    _validate_manifest(manifest)
    _validate_payload(staging_dir, manifest)
    data_root = _volume_mount()
    db_path = _webui_db(data_root)
    function_ids = [str(item["function_id"]) for item in manifest["functions"]]
    prompt_ids = [str(item["prompt_id"]) for item in manifest["managed_prompts"]]
    current_function_rows = _function_rows(db_path, function_ids)
    current_prompt_rows = _prompt_rows(db_path, prompt_ids)
    before = _live_state(db_path=db_path, data_root=data_root, manifest=manifest)
    _assert_static_contracts(before, manifest)
    _assert_prompt_set_present(before, manifest)
    _assert_quiescent(before)
    if not all(
        item.get("active") is True
        and item.get("global") is False
        and item.get("type") == "pipe"
        for item in before["functions"]
    ):
        raise StageReleaseError("stage_release_existing_function_state_invalid")
    desired_rows = _desired_rows(
        staging_dir=staging_dir,
        manifest=manifest,
        current_rows=current_function_rows,
    )
    desired_prompt_rows = _desired_prompt_rows(
        manifest=manifest,
        current_rows=current_prompt_rows,
    )
    desired_hashes = _content_hashes(desired_rows)
    before_hashes = _content_hashes(current_function_rows)
    desired_prompt_hashes = _prompt_hashes(desired_prompt_rows)
    before_prompt_hashes = _prompt_hashes(current_prompt_rows)
    plan = {
        function_id: {
            "before_sha256": before_hashes[function_id],
            "candidate_sha256": desired_hashes[function_id],
            "change_required": before_hashes[function_id] != desired_hashes[function_id],
        }
        for function_id in function_ids
    }
    prompt_plan = {
        prompt_id: {
            "before_sha256": before_prompt_hashes[prompt_id],
            "candidate_sha256": desired_prompt_hashes[prompt_id],
            "change_required": (
                before_prompt_hashes[prompt_id]
                != desired_prompt_hashes[prompt_id]
            ),
        }
        for prompt_id in prompt_ids
    }
    if not apply:
        return {
            "status": "validated",
            "applied": False,
            "schema_version": manifest["schema_version"],
            "release_id": manifest["release_id"],
            "source_revision": manifest["source_revision"],
            "manifest_sha256": manifest["manifest_sha256"],
            "plan": plan,
            "managed_prompt_plan": prompt_plan,
            "static_contracts": {
                "image": before["image"],
                "action": before["action"],
                "loader": before["loader"],
                "managed_prompts": before["managed_prompts"],
                "fitz_version": before["fitz_version"],
            },
            "workload": before["workload"],
            "counters": before["counters"],
            "staging_removed": True,
        }

    rollback, rollback_identity, rollback_created = _rollback_artifact(
        manifest=manifest,
        function_rows=current_function_rows,
        prompt_rows=current_prompt_rows,
        before_state=before,
    )
    rollback_rows = _json_object(rollback.get("previous_function_rows"))
    rollback_prompt_rows = _json_object(rollback.get("previous_prompt_rows"))
    if not rollback_prompt_rows:
        raise StageReleaseError("stage_release_prompt_rollback_missing")
    modified = False
    health_checks = 0
    rollback_proof = {
        "requested": bool(prove_rollback),
        "previous_state_restored": False,
        "candidate_state_restored": False,
    }
    try:
        _stop_container()
        _replace_release_rows(
            db_path=db_path,
            replacement_function_rows=desired_rows,
            replacement_prompt_rows=desired_prompt_rows,
            expected_function_hashes=before_hashes,
            expected_prompt_hashes=before_prompt_hashes,
        )
        modified = True
        _start_container()
        _wait_healthy()
        health_checks += 1
        candidate = _live_state(db_path=db_path, data_root=data_root, manifest=manifest)
        _assert_static_contracts(candidate, manifest)
        _assert_candidate(candidate, manifest)
        _assert_quiescent(candidate)
        if prove_rollback:
            _stop_container()
            _replace_release_rows(
                db_path=db_path,
                replacement_function_rows=rollback_rows,
                replacement_prompt_rows=rollback_prompt_rows,
                expected_function_hashes=desired_hashes,
                expected_prompt_hashes=desired_prompt_hashes,
            )
            _start_container()
            _wait_healthy()
            health_checks += 1
            restored_rows = _function_rows(db_path, function_ids)
            restored_prompt_rows = _prompt_rows(db_path, prompt_ids)
            if (
                _snapshot_function_rows(restored_rows) != rollback_rows
                or _snapshot_prompt_rows(restored_prompt_rows)
                != rollback_prompt_rows
            ):
                raise StageReleaseError("stage_release_rollback_rehearsal_mismatch")
            restored = _live_state(
                db_path=db_path, data_root=data_root, manifest=manifest
            )
            _assert_static_contracts(restored, manifest)
            _assert_prompt_set_present(restored, manifest)
            _assert_quiescent(restored)
            rollback_proof["previous_state_restored"] = True

            _stop_container()
            _replace_release_rows(
                db_path=db_path,
                replacement_function_rows=desired_rows,
                replacement_prompt_rows=desired_prompt_rows,
                expected_function_hashes=before_hashes,
                expected_prompt_hashes=before_prompt_hashes,
            )
            _start_container()
            _wait_healthy()
            health_checks += 1
            candidate = _live_state(
                db_path=db_path, data_root=data_root, manifest=manifest
            )
            _assert_static_contracts(candidate, manifest)
            _assert_candidate(candidate, manifest)
            _assert_quiescent(candidate)
            rollback_proof["candidate_state_restored"] = True
        if candidate["counters"] != before["counters"]:
            raise StageReleaseError("stage_release_repository_sink_delta_detected")
    except BaseException:
        if modified:
            _restore_after_failure(
                db_path=db_path,
                rollback_function_rows=rollback_rows,
                rollback_prompt_rows=rollback_prompt_rows,
            )
        elif not _container_running():
            _start_container()
            _wait_healthy()
        raise

    return {
        "status": "passed",
        "applied": True,
        "schema_version": manifest["schema_version"],
        "release_id": manifest["release_id"],
        "source_revision": manifest["source_revision"],
        "manifest_sha256": manifest["manifest_sha256"],
        "rollback_identity_sha256": rollback_identity,
        "rollback_artifact_created": rollback_created,
        "rollback_proof": rollback_proof,
        "health_checks_passed": health_checks,
        "plan": plan,
        "managed_prompt_plan": prompt_plan,
        "functions": candidate["functions"],
        "action": candidate["action"],
        "image": candidate["image"],
        "loader": candidate["loader"],
        "managed_prompts": candidate["managed_prompts"],
        "provider_policy": manifest["provider_policy"],
        "runtime": manifest["runtime"],
        "workload": candidate["workload"],
        "counters_before": before["counters"],
        "counters_after": candidate["counters"],
        "fitz_version": candidate["fitz_version"],
        "staging_removed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--prove-rollback", action="store_true")
    args = parser.parse_args()
    if args.prove_rollback and not args.apply:
        raise StageReleaseError("stage_release_rollback_proof_requires_apply")
    signal.signal(signal.SIGTERM, _raise_release_signal)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, _raise_release_signal)
    staging_dir = _validated_staging_dir(args.staging_dir)
    try:
        receipt = execute(
            staging_dir=staging_dir,
            apply=bool(args.apply),
            prove_rollback=bool(args.prove_rollback),
        )
    finally:
        resolved = staging_dir.resolve(strict=False)
        root = STAGING_ROOT.resolve(strict=True)
        if resolved.parent != root or not STAGING_NAME_RE.fullmatch(resolved.name):
            raise StageReleaseError("stage_release_cleanup_target_invalid")
        if resolved.exists():
            shutil.rmtree(resolved)
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


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
