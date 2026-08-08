#!/usr/bin/env python3
"""Read-only live proof for deterministic G3.6 NDFL case readiness."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    Gate3NdflCaseReadinessFactory,
)
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _atomic_write,
    _is_within,
    _json_bytes,
    _private_manifest,
)


FACTORY_REQUIRED = (
    "Gate3NdflCaseReadinessFactory.create is the only G3.6 readiness route; "
    "it derives state from access-controlled existing artifacts"
)
FORBIDDEN = (
    "The G3.6 proof must not write workflow state, call a provider, label or "
    "repair a document, mutate Gate 2, combine document contexts or run Gate 4"
)
DEFAULT_CONTEXT = {
    "user_id": "doc29-approved-cohort-user",
    "case_id": "doc29-approved-cohort",
    "workspace_model_id": "doc29-canonical-shadow",
    "normalization_run_id": "g3.6-derived-readiness-proof",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the explicitly authorized read-only G3.6 proof."
    )
    parser.add_argument("--execute-ndfl-case-readiness-proof", action="store_true")
    parser.add_argument(
        "--store-root",
        default=str(
            REPO_ROOT
            / "local"
            / "stage2"
            / "broker_reports_doc29_local_restore_2026-08-05"
        ),
    )
    parser.add_argument(
        "--private-evidence-dir",
        default=str(
            Path.home()
            / ".codex"
            / "private-evidence"
            / "broker-reports-g3.6-20260807-v1"
        ),
    )
    parser.add_argument(
        "--safe-receipt-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-07"
            / "BROKER_REPORTS_GATE3_NDFL_CASE_READINESS_G3_6.receipt.safe.json"
        ),
    )
    args = parser.parse_args()

    if not args.execute_ndfl_case_readiness_proof:
        raise SystemExit("explicit_execute_flag_required")
    store_root = Path(args.store_root).resolve()
    private_root = Path(args.private_evidence_dir).resolve()
    receipt_path = Path(args.safe_receipt_path).resolve()
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("artifact_store_unavailable")
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if private_root.exists() and any(private_root.iterdir()):
        raise SystemExit("private_evidence_directory_must_be_new_or_empty")
    if not _is_within(receipt_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if receipt_path.exists():
        raise SystemExit("safe_receipt_path_must_be_new")

    store_before = _store_tree_snapshot(store_root)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id=DEFAULT_CONTEXT["user_id"],
        case_id=DEFAULT_CONTEXT["case_id"],
        chat_id=None,
        workspace_model_id=DEFAULT_CONTEXT["workspace_model_id"],
        normalization_run_id=DEFAULT_CONTEXT["normalization_run_id"],
        allow_private=True,
    )
    factory = Gate3NdflCaseReadinessFactory(store=store, read_enabled=True)
    first = factory.create(context=context)
    second = factory.create(context=context)
    if first != second:
        raise SystemExit("readiness_not_deterministic")
    if first.get("state_persisted") is not False:
        raise SystemExit("readiness_state_was_persisted")

    denied_code = None
    try:
        factory.create(context=replace(context, allow_private=False))
    except ArtifactStoreError as exc:
        denied_code = exc.code
    if denied_code != "artifact_access_denied":
        raise SystemExit("readiness_private_access_not_fail_closed")
    foreign = factory.create(context=replace(context, user_id="g3.6-foreign-user"))
    if foreign["case_status"] != "empty" or foreign["documents"]:
        raise SystemExit("readiness_foreign_scope_disclosed")

    store_after = _store_tree_snapshot(store_root)
    if store_after != store_before:
        raise SystemExit("artifact_store_changed_during_readiness_proof")

    private_root.mkdir(parents=True, exist_ok=True)
    _atomic_write(
        private_root / "readiness_state.private.json",
        _json_bytes(first),
    )
    _atomic_write(
        private_root / "repeat_state.private.json",
        _json_bytes(second),
    )
    _atomic_write(
        private_root / "access_boundary.private.json",
        _json_bytes(
            {
                "private_access_denied_code": denied_code,
                "foreign_scope_state": foreign,
            }
        ),
    )
    _atomic_write(
        private_root / "store_before.private.json",
        _json_bytes(store_before),
    )
    _atomic_write(
        private_root / "store_after.private.json",
        _json_bytes(store_after),
    )

    summary = first["summary"]
    prepare = next(
        item
        for item in first["follow_up_actions"]
        if item["action_id"] == "PREPARE_DECLARATION"
    )
    receipt = {
        "schema_version": "broker_reports_gate3_ndfl_case_readiness_receipt_v1",
        "goal": "G3.6",
        "goal_status": "COMPLETED",
        "acceptance": "PASS",
        "state_derivation": "PASS",
        "state_source": first["state_source"],
        "state_persisted": first["state_persisted"],
        "deterministic_repeat": True,
        "access_control": "PASS",
        "private_access_denied_code": denied_code,
        "foreign_scope_non_disclosure": "PASS",
        "artifact_store_byte_unchanged": True,
        "artifact_store_tree_sha256": _snapshot_sha256(store_before),
        "case_status": first["case_status"],
        "documents_total": summary["documents_total"],
        "gate2_ready_documents": summary["gate2_ready_documents"],
        "gate3_ready_documents": summary["gate3_ready_documents"],
        "gate4_handoff_ready": summary["gate4_handoff_ready"],
        "follow_up_actions_total": len(first["follow_up_actions"]),
        "prepare_declaration_allowed": prepare["allowed"],
        "prepare_declaration_reason_code": prepare["reason_code"],
        "document_contexts_combined": False,
        "provider_calls": 0,
        "new_database": "NONE",
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "next_allowed_goal": "G3.7",
    }
    _atomic_write(receipt_path, _json_bytes(receipt))
    private_manifest = _private_manifest(private_root)
    private_manifest["schema_version"] = (
        "broker_reports_gate3_ndfl_case_readiness_private_manifest_v1"
    )
    private_manifest["goal"] = "G3.6"
    _atomic_write(
        private_root / "private_manifest.json",
        _json_bytes(private_manifest),
    )
    print(
        json.dumps(
            {
                "goal": "G3.6",
                "acceptance": "PASS",
                "case_status": first["case_status"],
                "documents_total": summary["documents_total"],
                "gate2_ready_documents": summary["gate2_ready_documents"],
                "gate3_ready_documents": summary["gate3_ready_documents"],
                "gate4_handoff_ready": summary["gate4_handoff_ready"],
                "store_unchanged": True,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def _store_tree_snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {
        str(path.relative_to(root)).replace("\\", "/"): {
            "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _snapshot_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
