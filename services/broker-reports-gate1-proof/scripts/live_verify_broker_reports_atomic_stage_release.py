#!/usr/bin/env python3
"""Read-only terminal verifier for a Broker Reports atomic stage release."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_atomic_stage_release_contracts import (  # noqa: E402
    ACTION_ID,
    build_manifest,
    provider_policy_manifest,
)
from broker_reports_release_source import (  # noqa: E402
    LOADER_REPOSITORY_PATH,
    git_blob_bytes,
)
from broker_reports_gate1 import GATE2_PROVIDER_PROFILES  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _default_ssh_target,
    _read_env,
    _signin,
)
from live_verify_broker_reports_stage2_delivery import (  # noqa: E402
    _get_live_function,
    _get_live_function_valves,
    _read_live_prompt_state,
    evaluate_prompt_contract,
    expected_prompt_contracts,
    repository_factory_boundary_checks,
)


class AtomicStageVerificationError(RuntimeError):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def evaluate_function_release(
    *,
    expected: Mapping[str, Any],
    live_function: Mapping[str, Any] | None,
    live_valves: Mapping[str, Any] | None,
    source_revision: str,
    manifest_sha256: str,
    expected_active: bool,
) -> dict[str, Any]:
    live = dict(live_function or {})
    valves = dict(live_valves or {})
    meta = live.get("meta") if isinstance(live.get("meta"), dict) else {}
    release_meta = (
        meta.get("broker_reports_release")
        if isinstance(meta.get("broker_reports_release"), dict)
        else {}
    )
    content = str(live.get("content") or "")
    expected_valves = dict(expected.get("valves") or {})
    retired_valves = set(expected.get("retired_valve_keys") or [])
    projected_valves = {
        key: valves.get(key) for key in sorted(expected_valves)
    }
    checks = {
        "present": bool(live_function),
        "type_pipe": live.get("type") == "pipe",
        "activation_policy_preserve_existing": (
            expected.get("activation_policy") == "preserve_existing"
        ),
        "activation_preserved": (
            (
                live.get("is_active") is True
                or (
                    isinstance(live.get("is_active"), int)
                    and not isinstance(live.get("is_active"), bool)
                    and live.get("is_active") == 1
                )
            )
            is expected_active
        ),
        "not_global": live.get("is_global") is False
        or live.get("is_global") == 0,
        "content_sha256_match": bool(content)
        and _sha256_text(content) == expected.get("content_sha256"),
        "required_markers_present": all(
            str(marker) in content for marker in expected.get("required_markers", [])
        ),
        "release_revision_match": release_meta.get("source_revision")
        == source_revision,
        "release_manifest_match": release_meta.get("manifest_sha256")
        == manifest_sha256,
        "release_bundle_hash_match": release_meta.get("bundle_sha256")
        == expected.get("content_sha256"),
        "valves_match": projected_valves == expected_valves,
        "retired_valves_absent": all(key not in valves for key in retired_valves),
    }
    return {
        "function_id": expected.get("function_id"),
        "passed": all(checks.values()),
        "checks": checks,
        "repository_content_sha256": expected.get("content_sha256"),
        "live_content_sha256": _sha256_text(content) if content else None,
        "valves": valves,
        "expected_active": expected_active,
    }


def evaluate_action_release(
    *, expected: Mapping[str, Any], live: Mapping[str, Any] | None
) -> dict[str, Any]:
    value = dict(live or {})
    content = str(value.get("content") or "")
    checks = {
        "present": bool(live),
        "type_action": value.get("type") == "action",
        "active": value.get("is_active") is True
        or value.get("is_active") == 1,
        "not_global": value.get("is_global") is False
        or value.get("is_global") == 0,
        "content_sha256_match": bool(content)
        and _sha256_text(content) == expected.get("content_sha256"),
    }
    return {
        "action_id": expected.get("action_id"),
        "passed": all(checks.values()),
        "checks": checks,
        "repository_content_sha256": expected.get("content_sha256"),
        "live_content_sha256": _sha256_text(content) if content else None,
    }


def evaluate_remote_runtime(
    *,
    expected_manifest: Mapping[str, Any],
    runtime: Mapping[str, Any],
    rollback_identity_sha256: str | None,
) -> dict[str, bool]:
    expected_image = dict(expected_manifest.get("image") or {})
    image = dict(runtime.get("image") or {})
    workload = dict(runtime.get("workload") or {})
    previous_function_activation = dict(
        runtime.get("previous_function_activation") or {}
    )
    expected_function_ids = {
        str(item["function_id"])
        for item in expected_manifest.get("functions", [])
    }
    retired_function_ids = set(expected_manifest.get("retired_function_ids") or [])
    checks = {
        "image_identity_exact": all(
            image.get(key) == expected_image.get(key)
            for key in (
                "configured_image",
                "image_id",
                "source_revision",
                "private_intake_contract",
            )
        ),
        "image_running_clean": image.get("running") is True
        and image.get("restart_count") == 0,
        "loader_hash_exact": runtime.get("loader_sha256")
        == expected_manifest["loader"]["content_sha256"],
        "workload_quiescent": workload.get("release_blocking_jobs") == 0,
        "parked_reviews_safe": workload.get("unsafe_review_jobs") == 0,
        "workload_temp_clean": workload.get("owned_temp_entries") == 0,
        "release_staging_clean": runtime.get("release_staging_entries") == 0,
        "rollback_identity_exact": (
            rollback_identity_sha256 is None
            or runtime.get("rollback_identity_sha256")
            == rollback_identity_sha256
        ),
        "rollback_loader_hash_exact": (
            rollback_identity_sha256 is None
            or runtime.get("rollback_loader_hash_exact") is True
        ),
        "rollback_activation_snapshot_exact": (
            expected_function_ids <= set(previous_function_activation)
            and set(previous_function_activation)
            <= expected_function_ids | retired_function_ids
            and all(
                isinstance(value, bool)
                for value in previous_function_activation.values()
            )
        ),
    }
    return checks


def evaluate_route_activation(
    *,
    expected_manifest: Mapping[str, Any],
    gate1_valves: Mapping[str, Any],
) -> dict[str, bool]:
    runtime = dict(expected_manifest.get("runtime") or {})
    provider_policy = dict(expected_manifest.get("provider_policy") or {})
    document_ai = dict(provider_policy.get("pdf_document_ai_contract") or {})
    functions = list(expected_manifest.get("functions") or [])
    gate1_retired = set((functions[0] if functions else {}).get("retired_valve_keys") or [])
    return {
        "pdf_document_ai_fail_closed": (
            all(key not in gate1_valves for key in gate1_retired)
            and gate1_valves.get("canonical_gate2_write_enabled") is True
            and gate1_valves.get("canonical_gate2_read_enabled") is True
            and gate1_valves.get("ordinary_trade_candidate_enabled") is True
            and gate1_valves.get("ndfl_gate3_enabled") is False
            and gate1_valves.get(
                "pdf_document_ai_qualification_repository_head"
            )
            == expected_manifest.get("source_revision")
        ),
        "pdf_document_ai_contract_identity_exact": (
            document_ai.get("configured") is False
            and document_ai.get("adapter_status") == "static_ready"
            and document_ai.get("selected_engine") == "mistral_ocr"
            and document_ai.get("selected_adapter")
            == "mistral_serverless_ocr_adapter_v1"
            and document_ai.get("static_ready") is True
            and document_ai.get("live_qualified") is False
            and document_ai.get("composition_owner")
            == "PdfDocumentExtractorFactory"
            and document_ai.get("terminal_blockers")
            == {
                "unconfigured": "PDF_DOCUMENT_AI_NOT_CONFIGURED",
                "selected_unqualified": "PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED",
            }
            and runtime.get("pdf_document_ai_static_ready") is True
            and runtime.get("pdf_document_ai_live_qualified") is False
            and runtime.get("legacy_table_route_available") is False
        ),
    }


def _read_remote_runtime_state(
    *,
    ssh_target: str,
    release_id: str,
) -> dict[str, Any]:
    remote_code = r'''
import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path

RELEASE_ID = __RELEASE_ID__
ROOT = Path("/opt/openwebui-prd0")

def run(args):
    return subprocess.run(
        args, check=True, capture_output=True, text=True,
        encoding="utf-8", timeout=90).stdout

container = json.loads(run(["docker", "inspect", "openwebui"]))[0]
image = json.loads(run(["docker", "image", "inspect", container["Image"]]))[0]
labels = image.get("Config", {}).get("Labels") or {}
volume = json.loads(run(["docker", "volume", "inspect", "openwebui_data"]))[0]
data_root = Path(volume["Mountpoint"])
db_path = data_root / "webui.db"
with sqlite3.connect(db_path) as conn:
    tables = {
        str(row[0])
        for row in conn.execute("select name from sqlite_master where type='table'")
    }
    counters = {
        table + "_rows": int(conn.execute(
            'select count(*) from "' + table + '"').fetchone()[0])
        for table in ("document", "file", "knowledge") if table in tables
    }
workload_db = data_root / "broker_reports_gate1" / "workloads.sqlite3"
state_counts = {}
unsafe_review_jobs = 0
if workload_db.is_file():
    with sqlite3.connect(workload_db) as conn:
        if conn.execute(
            "select 1 from sqlite_master where type='table' and name='workload_jobs'"
        ).fetchone() is not None:
            state_counts = {
                str(state): int(count)
                for state, count in conn.execute(
                    "select state, count(*) from workload_jobs group by state")
            }
            unsafe_review_jobs = int(conn.execute(
                "select count(*) from workload_jobs "
                "where state='awaiting_review' and ("
                "worker_id is not null or lease_token is not null or "
                "provider_lease_token is not null or cleanup_status != 'cleaned'"
                ")").fetchone()[0])
terminal = {"completed", "failed", "cancelled"}
release_quiescent = {*terminal, "awaiting_review"}
nonterminal = sum(v for k, v in state_counts.items() if k not in terminal)
release_blocking = sum(
    v for k, v in state_counts.items() if k not in release_quiescent
) + unsafe_review_jobs
temp_root = data_root / "broker_reports_gate1" / "workload-temp"
temp_entries = (
    sum(1 for item in temp_root.iterdir() if item.name.startswith("brjob_"))
    if temp_root.is_dir() else 0
)
vector_root = data_root / "vector_db"
vector_files = 0
vector_bytes = 0
if vector_root.is_dir():
    for base, _dirs, names in os.walk(vector_root):
        for name in names:
            path = Path(base) / name
            vector_files += 1
            vector_bytes += path.stat().st_size
counters["vector_files"] = vector_files
counters["vector_bytes"] = vector_bytes
loader = ROOT / "deploy" / "openwebui-static" / "loader.js"
rollback = (
    ROOT / ".broker-reports-rollbacks" / RELEASE_ID
    / "function_rows.rollback.json"
)
rollback_loader = (
    ROOT / ".broker-reports-rollbacks" / RELEASE_ID
    / "loader.rollback.js"
)
rollback_value = (
    json.loads(rollback.read_text(encoding="utf-8"))
    if rollback.is_file() else {}
)
rollback_hash = (
    hashlib.sha256(rollback.read_bytes()).hexdigest()
    if rollback.is_file() else None
)
rollback_loader_hash_exact = bool(
    rollback_loader.is_file()
    and hashlib.sha256(rollback_loader.read_bytes()).hexdigest()
    == (rollback_value.get("previous_loader") or {}).get("content_sha256")
)
previous_function_activation = {
    str(function_id): row.get("is_active") in (1, True)
    for function_id, row in (
        rollback_value.get("previous_function_rows") or {}
    ).items()
    if isinstance(row, dict)
}
staging = ROOT / ".broker-reports-release-staging"
staging_entries = (
    sum(1 for item in staging.iterdir() if item.is_dir())
    if staging.is_dir() else 0
)
print(json.dumps({
    "image": {
        "configured_image": container.get("Config", {}).get("Image"),
        "image_id": container.get("Image"),
        "running": bool(container.get("State", {}).get("Running")),
        "restart_count": int(container.get("RestartCount") or 0),
        "source_revision": labels.get("org.opencontainers.image.revision"),
        "private_intake_contract": labels.get(
            "ai.alpha-soft.broker-reports-private-intake"),
    },
    "loader_sha256": hashlib.sha256(loader.read_bytes()).hexdigest(),
    "workload": {
        "state_counts": state_counts,
        "nonterminal_jobs": nonterminal,
        "release_blocking_jobs": release_blocking,
        "unsafe_review_jobs": unsafe_review_jobs,
        "owned_temp_entries": temp_entries,
    },
    "counters": counters,
    "rollback_identity_sha256": rollback_hash,
    "rollback_loader_hash_exact": rollback_loader_hash_exact,
    "previous_function_activation": previous_function_activation,
    "release_staging_entries": staging_entries,
}, ensure_ascii=False, sort_keys=True))
'''
    remote_code = remote_code.replace(
        "__RELEASE_ID__", json.dumps(release_id, ensure_ascii=False)
    )
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
            "python3",
            "-",
        ],
        cwd=ROOT,
        input=remote_code,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise AtomicStageVerificationError("atomic_stage_runtime_state_invalid")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--rollback-identity-sha256", default=None)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = (
        args.ssh_target
        or env.get("OPENWEBUI_SSH_TARGET")
        or _default_ssh_target(env)
    )
    manifest = build_manifest(
        source_revision=args.source_revision,
        prompt_contracts=expected_prompt_contracts(),
        provider_policy=provider_policy_manifest(GATE2_PROVIDER_PROFILES),
        loader_bytes=git_blob_bytes(
            root=ROOT,
            source_revision=args.source_revision,
            repository_path=LOADER_REPOSITORY_PATH,
        ),
    )
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    runtime = _read_remote_runtime_state(
        ssh_target=ssh_target,
        release_id=manifest["release_id"],
    )
    previous_function_activation = dict(
        runtime.get("previous_function_activation") or {}
    )
    function_checks = []
    for expected in manifest["functions"]:
        function_id = str(expected["function_id"])
        function_checks.append(
            evaluate_function_release(
                expected=expected,
                live_function=_get_live_function(session, base_url, function_id),
                live_valves=_get_live_function_valves(
                    session, base_url, function_id
                ),
                source_revision=args.source_revision,
                manifest_sha256=manifest["manifest_sha256"],
                expected_active=previous_function_activation.get(function_id),
            )
        )
    retired_function_checks = [
        {
            "function_id": function_id,
            "inactive": (
                (value := _get_live_function(session, base_url, function_id)) is None
                or value.get("is_active") in (False, 0, None)
            ),
        }
        for function_id in manifest.get("retired_function_ids") or []
    ]
    action_check = evaluate_action_release(
        expected=manifest["action"],
        live=_get_live_function(session, base_url, ACTION_ID),
    )
    expected_prompts = expected_prompt_contracts()
    live_prompts = _read_live_prompt_state(
        ssh_target=ssh_target,
        prompt_ids=sorted(expected_prompts),
    )
    prompt_checks = [
        evaluate_prompt_contract(expected_prompts[prompt_id], live_prompts.get(prompt_id))
        for prompt_id in sorted(expected_prompts)
    ]
    runtime_checks = evaluate_remote_runtime(
        expected_manifest=manifest,
        runtime=runtime,
        rollback_identity_sha256=args.rollback_identity_sha256,
    )
    factory_checks = repository_factory_boundary_checks()
    workload_valves = [
        {
            key: item["valves"].get(key)
            for key in (
                "workload_store_path",
                "workload_temp_root",
                "workload_lease_seconds",
                "workload_poll_interval_seconds",
                "workload_provider_budgets_json",
            )
        }
        for item in function_checks
    ]
    runtime_boundary = manifest["provider_policy"][
        "source_bound_table_contract"
    ]["runtime_boundary"]
    release_checks = {
        "all_function_bundles_exact": all(
            item["passed"] for item in function_checks
        ),
        "retired_functions_inactive": all(
            item["inactive"] for item in retired_function_checks
        ),
        "private_intake_action_exact": action_check["passed"],
        "all_managed_prompts_exact": all(item["passed"] for item in prompt_checks),
        "all_runtime_identities_exact": all(runtime_checks.values()),
        "repository_factory_boundary_passed": all(factory_checks.values()),
        "no_paddle_or_local_ocr_dependency": factory_checks[
            "production_python_has_no_paddle_or_local_ocr_import"
        ]
        and runtime_boundary["local_ocr_production_allowed"] is False
        and runtime_boundary["local_ocr_worker_pool_allowed"] is False,
        "knowledge_rag_vectorization_forbidden": runtime_boundary[
            "knowledge_rag_vectorization_allowed"
        ]
        is False
        and runtime_boundary[
            "native_openwebui_document_processing_allowed"
        ]
        is False,
        "single_workload_authority_configuration": all(
            item == workload_valves[0] for item in workload_valves[1:]
        ),
        **evaluate_route_activation(
            expected_manifest=manifest,
            gate1_valves=function_checks[0]["valves"],
        ),
        "legacy_table_route_unavailable": manifest["runtime"][
            "legacy_table_route_available"
        ] is False,
    }
    output = {
        "status": "passed" if all(release_checks.values()) else "failed",
        "schema_version": "broker_reports_atomic_stage_release_verification_v1",
        "release_id": manifest["release_id"],
        "source_revision": manifest["source_revision"],
        "manifest_sha256": manifest["manifest_sha256"],
        "checks": release_checks,
        "functions": function_checks,
        "retired_functions": retired_function_checks,
        "action": action_check,
        "managed_prompts": prompt_checks,
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "provider_policy": manifest["provider_policy"],
        "factory_boundary": factory_checks,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
