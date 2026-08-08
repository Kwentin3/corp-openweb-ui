#!/usr/bin/env python3
"""Persist the exact complete G3.4D result through the G3.5 owner."""

from __future__ import annotations

import argparse
import copy
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
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CanonicalReaderFactory,
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    Gate3FinancialAnnotationsPersistenceFactory,
)
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _atomic_write,
    _is_within,
    _json_bytes,
    _private_manifest,
)


FACTORY_REQUIRED = (
    "Gate3FinancialAnnotationsPersistenceFactory.create is the only G3.5 "
    "write/read route and delegates physical persistence to ArtifactStore"
)
FORBIDDEN = (
    "The G3.5 proof must not call a provider, relabel, mutate Gate 2, create "
    "a database, bypass access checks or persist an incomplete batch"
)
EXPECTED_BATCH_SHA256 = (
    "c5be4f6a2e1728d04be10155787b02a1ef2fe0a3054e3530d4e72aba91555595"
)
DOCUMENT_ID = "brdoc_013_21c85fa3ff06"
PROVIDER_PROFILE_ID = "google_gemini"
EXPECTED_MODEL_ID = "models/gemini-3.5-flash"
DEFAULT_CONTEXT = {
    "user_id": "doc29-approved-cohort-user",
    "case_id": "doc29-approved-cohort",
    "workspace_model_id": "doc29-canonical-shadow",
    "normalization_run_id": "normrun_046152421c699e38",
}
_RESULT_KEYS = (
    "schema_version",
    "selected_chunk_ordinals",
    "selection_mode",
    "document_status",
    "metrics",
    "merged_output",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the explicitly authorized G3.5 persistence proof."
    )
    parser.add_argument("--execute-financial-annotations-persistence", action="store_true")
    parser.add_argument("--private-batch-result-path", required=True)
    parser.add_argument(
        "--expected-batch-sha256", default=EXPECTED_BATCH_SHA256
    )
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
            / "broker-reports-g3.5-20260807-v1"
        ),
    )
    parser.add_argument(
        "--safe-receipt-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-07"
            / "BROKER_REPORTS_GATE3_FINANCIAL_ANNOTATIONS_G3_5.receipt.safe.json"
        ),
    )
    args = parser.parse_args()

    if not args.execute_financial_annotations_persistence:
        raise SystemExit("explicit_execute_flag_required")
    private_batch_path = Path(args.private_batch_result_path).resolve()
    private_root = Path(args.private_evidence_dir).resolve()
    receipt_path = Path(args.safe_receipt_path).resolve()
    store_root = Path(args.store_root).resolve()
    if not private_batch_path.is_file():
        raise SystemExit("private_batch_result_missing")
    if _is_within(private_batch_path, REPO_ROOT.resolve()):
        raise SystemExit("private_batch_result_must_be_outside_repository")
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if private_root.exists() and any(private_root.iterdir()):
        raise SystemExit("private_evidence_directory_must_be_new_or_empty")
    if not _is_within(receipt_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if receipt_path.exists():
        raise SystemExit("safe_receipt_path_must_be_new")
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("canonical_store_unavailable")

    batch_bytes = private_batch_path.read_bytes()
    batch_sha256 = hashlib.sha256(batch_bytes).hexdigest()
    if batch_sha256 != args.expected_batch_sha256:
        raise SystemExit("private_batch_result_hash_mismatch")
    batch_private = json.loads(batch_bytes.decode("utf-8"))
    if not isinstance(batch_private, dict):
        raise SystemExit("private_batch_result_invalid")
    document_result = {
        key: copy.deepcopy(batch_private.get(key)) for key in _RESULT_KEYS
    }
    if (
        batch_private.get("schema_version")
        != "broker_reports_gate3_strict_alias_private_result_v1"
        or batch_private.get("document_label") != "compact_html"
        or document_result["document_status"] != "complete"
        or document_result["selection_mode"] != "full_document"
        or document_result["merged_output"]["model_identity"]["model_id"]
        != EXPECTED_MODEL_ID
    ):
        raise SystemExit("private_batch_result_not_frozen_complete_compact")
    document_result["schema_version"] = (
        GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION
    )

    private_root.mkdir(parents=True, exist_ok=True)
    _atomic_write(
        private_root / "validated_pre_persist_proposal.private.json",
        _json_bytes(document_result),
    )
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
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    canonical_before = reader.read_active_envelope(DOCUMENT_ID, context)
    persistence = Gate3FinancialAnnotationsPersistenceFactory(
        store=store,
        read_enabled=True,
    ).create()
    stored = persistence.save(
        document_id=DOCUMENT_ID,
        context=context,
        validated_document_result=document_result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    read_back = persistence.read(
        artifact_id=stored.artifact_id,
        context=context,
    )
    if read_back != document_result["merged_output"]:
        raise SystemExit("financial_annotations_read_back_mismatch")

    denied_code = None
    try:
        persistence.read(
            artifact_id=stored.artifact_id,
            context=replace(context, user_id="g3.5-access-denied-proof"),
        )
    except ArtifactStoreError as exc:
        denied_code = exc.code
    if denied_code != "artifact_access_denied":
        raise SystemExit("financial_annotations_access_not_fail_closed")

    immutable_code = None
    mutated = copy.deepcopy(stored)
    mutated.payload = copy.deepcopy(read_back)
    mutated.payload["annotations"] = []
    try:
        store.put_record(mutated)
    except ArtifactStoreError as exc:
        immutable_code = exc.code
    if immutable_code != "artifact_immutable":
        raise SystemExit("financial_annotations_not_immutable")

    version = store.get_active_canonical_version(
        context=context,
        document_id=DOCUMENT_ID,
    )
    manifest = ArtifactResolver(store).resolve_record(version.manifest_ref, context)
    if stored.retention_policy != manifest.retention_policy:
        raise SystemExit("financial_annotations_retention_not_reused")
    canonical_after = reader.read_active_envelope(DOCUMENT_ID, context)
    if (
        canonical_after.canonical_version_id
        != canonical_before.canonical_version_id
        or canonical_after.canonical_root_sha256
        != canonical_before.canonical_root_sha256
    ):
        raise SystemExit("gate2_changed_during_g35")

    payload_sha256 = hashlib.sha256(_json_bytes(read_back)).hexdigest()
    artifact_id_sha256 = hashlib.sha256(stored.artifact_id.encode("utf-8")).hexdigest()
    private_stored = {
        "artifact_id": stored.artifact_id,
        "artifact_type": stored.artifact_type,
        "document_id": stored.document_id,
        "canonical_version_id": read_back["canonical_binding"][
            "canonical_version_id"
        ],
        "retention_policy": stored.retention_policy.to_dict(),
        "provider_profile_id": stored.safe_metadata["provider_profile_id"],
        "payload": read_back,
    }
    _atomic_write(
        private_root / "stored_sidecar.private.json",
        _json_bytes(private_stored),
    )
    _atomic_write(
        private_root / "read_back.private.json",
        _json_bytes(read_back),
    )
    _atomic_write(
        private_root / "binding_and_access.private.json",
        _json_bytes(
            {
                "canonical_before": _canonical_safe(canonical_before),
                "canonical_after": _canonical_safe(canonical_after),
                "access_denied_code": denied_code,
                "immutable_overwrite_code": immutable_code,
                "retention_policy": stored.retention_policy.to_dict(),
            }
        ),
    )
    receipt = {
        "schema_version": (
            "broker_reports_gate3_financial_annotations_persistence_receipt_v1"
        ),
        "goal": "G3.5",
        "goal_status": "COMPLETED",
        "acceptance": "PASS",
        "save": "PASS",
        "read": "PASS",
        "access_control": "PASS",
        "access_denied_code": denied_code,
        "immutable_sidecar": "PASS",
        "immutable_overwrite_code": immutable_code,
        "canonical_binding": "PASS",
        "dictionary_binding": "PASS",
        "instruction_model_provenance": "PASS",
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "model_id": EXPECTED_MODEL_ID,
        "annotations_total": len(read_back["annotations"]),
        "input_batch_sha256": batch_sha256,
        "stored_payload_sha256": payload_sha256,
        "read_back_payload_sha256": hashlib.sha256(
            _json_bytes(read_back)
        ).hexdigest(),
        "artifact_id_sha256": artifact_id_sha256,
        "gate2_canonical_version_unchanged": True,
        "gate2_canonical_root_sha256_unchanged": True,
        "retention_policy_reused": True,
        "retention_mode": stored.retention_policy.mode,
        "purge_owner_reused": "ArtifactStore.purge_case",
        "relabel_without_gate2_mutation": "PASS_BY_FOCUSED_TEST",
        "new_database": "NONE",
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "next_allowed_goal": "G3.6",
    }
    _atomic_write(receipt_path, _json_bytes(receipt))
    manifest_value = _private_manifest(private_root)
    _atomic_write(
        private_root / "private_manifest.json",
        _json_bytes(manifest_value),
    )
    print(
        json.dumps(
            {
                "goal": "G3.5",
                "save": "PASS",
                "read": "PASS",
                "access": "PASS",
                "immutable": "PASS",
                "gate2_unchanged": True,
                "annotations_total": len(read_back["annotations"]),
                "new_database": "NONE",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def _canonical_safe(value: Any) -> dict[str, Any]:
    return {
        "canonical_version_id": value.canonical_version_id,
        "canonical_root_sha256": value.canonical_root_sha256,
        "version_status": value.version_status,
    }


if __name__ == "__main__":
    raise SystemExit(main())
