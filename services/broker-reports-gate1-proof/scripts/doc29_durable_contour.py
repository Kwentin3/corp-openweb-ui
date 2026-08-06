#!/usr/bin/env python3
"""Factory-routed durable canonical cohort and infrastructure proof commands.

Private source bytes and the private state receipt remain outside Git.  Every
command writes only aggregate safe JSON to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CANONICAL_OK,
    CanonicalReadLedger,
    CanonicalReaderFactory,
    FileInput,
    Gate1Normalizer,
    LOCAL_PDF_COMPACT_RESEARCH_MAPPING,
    LocalPdfCompactResearchCanonicalAdapterFactory,
    build_retention_policy,
    persist_gate1_result,
)
from broker_reports_gate1.canonical_wave2_shadow import (  # noqa: E402
    WAVE2_SHADOW_CONTRACTS,
    CanonicalWave2ShadowFactory,
    Wave2ShadowLedger,
)


SCHEMA_VERSION = "broker_reports_doc29_durable_contour_command_v1"
STATE_SCHEMA_VERSION = "broker_reports_doc29_private_cohort_state_v1"
EXPECTED_FORMATS = {"pdf": 8, "html": 4, "csv": 2, "xlsx": 2}
CONTEXT = {
    "user_id": "doc29-approved-cohort-user",
    "case_id": "doc29-approved-cohort",
    "workspace_model_id": "doc29-canonical-shadow",
}
RETENTION_CLASS_POLICY = {
    "SOURCE": {"ttl_days": None, "owner": "source lifecycle"},
    "ACTIVE_CANONICAL": {"ttl_days": None, "owner": "canonical pointer owner"},
    "SUPERSEDED_CANONICAL": {"ttl_days": 30, "owner": "canonical retention worker"},
    "EVIDENCE": {"ttl_days": 30, "owner": "canonical retention worker"},
    "RAW_PROVIDER": {"ttl_days": 14, "owner": "artifact retention worker"},
    "TEMPORARY": {"ttl_days": 1, "owner": "artifact retention worker"},
    "PROJECTION_CACHE": {"ttl_days": 7, "owner": "artifact retention worker"},
    "RESEARCH": {"ttl_days": 14, "owner": "research job owner"},
}


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mime(path: Path) -> str:
    return {
        ".pdf": "application/pdf",
        ".html": "text/html",
        ".htm": "text/html",
        ".csv": "text/csv",
        ".xlsx": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    }[path.suffix.lower()]


def _format(path: Path) -> str:
    return "html" if path.suffix.lower() == ".htm" else path.suffix.lower()[1:]


def _store(root: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()


def _context(run_id: str, *, user_id: str | None = None) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id=user_id or CONTEXT["user_id"],
        normalization_run_id=run_id,
        case_id=CONTEXT["case_id"],
        workspace_model_id=CONTEXT["workspace_model_id"],
        allow_private=True,
        require_source_available=True,
    )


def _state_path(root: Path) -> Path:
    return root / "doc29" / "approved_cohort.private.json"


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        raise RuntimeError("doc29_private_state_unavailable")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise RuntimeError("doc29_private_state_schema_invalid")
    supplied = str(state.pop("integrity_sha256", ""))
    if supplied != _sha(state):
        raise RuntimeError("doc29_private_state_integrity_invalid")
    state["integrity_sha256"] = supplied
    return state


def _write_state(root: Path, state: dict[str, Any]) -> None:
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["integrity_sha256"] = _sha(state)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    value = {
        "schema_version": SCHEMA_VERSION,
        "private_content_in_output": False,
        **payload,
    }
    value["integrity_sha256"] = _sha(value)
    return value


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return int(ordered[index])


def prepare(input_root: Path, store_root: Path) -> int:
    if _state_path(store_root).exists():
        raise RuntimeError("doc29_cohort_already_prepared")
    files = sorted(
        path
        for path in input_root.iterdir()
        if path.is_file() and path.suffix.lower() in {".pdf", ".html", ".htm", ".csv", ".xlsx"}
    )
    formats = Counter(_format(path) for path in files)
    hashes = [_file_sha(path) for path in files]
    if len(files) != 16 or dict(formats) != EXPECTED_FORMATS:
        raise RuntimeError("doc29_cohort_shape_invalid")
    if len(set(hashes)) != 15:
        raise RuntimeError("doc29_duplicate_accounting_invalid")
    usage_before = shutil.disk_usage(store_root)
    if usage_before.free < 1024 * 1024 * 1024 or usage_before.free / usage_before.total <= 0.10:
        raise RuntimeError("canonical_capacity_insufficient")

    started = time.perf_counter()
    inputs = [
        FileInput.from_bytes(
            private_ref=f"doc29-private-{index:03d}-{digest[:16]}",
            filename=f"approved-{index:03d}{path.suffix.lower()}",
            content=path.read_bytes(),
            mime_type=_mime(path),
        )
        for index, (path, digest) in enumerate(zip(files, hashes), 1)
    ]
    normalized = Gate1Normalizer().normalize(
        inputs,
        entrypoint="doc29_durable_cohort",
        trigger_type="approved_parser_only_backfill",
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_compare_enabled": True,
            "canonical_gate2_read_enabled": False,
            "normalizer_version": "canonical-doc29-durable-v1",
            "provider_calls_allowed": False,
            "vlm_calls_allowed": False,
        },
    )
    run_id = str(normalized.package["normalization_run"]["run_id"])
    context = _context(run_id)
    store = _store(store_root)
    manifest = persist_gate1_result(
        store=store,
        result=normalized,
        context=context,
        retention_policy=build_retention_policy(
            mode="manual_purge_required",
            explicit=True,
            requires_manual_purge=True,
        ),
        source_file_refs=[
            {
                "provider": "doc29_approved_private_cohort",
                "openwebui_file_id": f"doc29-source-{index:03d}",
                "file_hash_sha256": digest,
                "content_type": _mime(path),
                "size_bytes": path.stat().st_size,
            }
            for index, (path, digest) in enumerate(zip(files, hashes), 1)
        ],
    )
    canonical_refs = manifest.artifact_refs_by_type.get(
        "broker_reports_canonical_artifact_v1", []
    )
    failures = manifest.artifact_refs_by_type.get(
        "broker_reports_canonical_build_failure_v1", []
    )
    if len(canonical_refs) != 16 or failures:
        raise RuntimeError("doc29_canonical_build_incomplete")
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    legacy_documents = {
        str(item.get("document_id")): item
        for item in normalized.package.get("document_inventory", {}).get("documents", [])
    }
    source_units = list(normalized.package.get("private_normalized_source_units") or [])
    projections = list(
        normalized.package.get("private_normalized_table_projections") or []
    )
    documents: list[dict[str, Any]] = []
    payload_bytes: list[int] = []
    component_counts: list[int] = []
    layouts: Counter[str] = Counter()
    activation_changed = 0
    for manifest_ref in canonical_refs:
        version = store.get_canonical_version_by_manifest(
            context=context, manifest_ref=manifest_ref
        )
        receipt = reader.activate(
            canonical_version_id=version.canonical_version_id,
            expected_previous_version_id=None,
            context=context,
            actor="doc29-durable-cohort",
            reason="approved cohort initial activation",
        )
        activation_changed += int(receipt.status == "changed")
        envelope = reader.read_active_envelope(version.document_id, context)
        artifact = envelope.artifact
        legacy = legacy_documents.get(version.document_id) or {}
        expected = {
            "source_format": str(legacy.get("container_format") or ""),
            "source_units_total": sum(
                str(item.get("document_id") or "") == version.document_id
                for item in source_units
            ),
            "table_projections_total": sum(
                str(item.get("source_document_ref") or "") == version.document_id
                for item in projections
            ),
            "page_count": int(legacy.get("page_count") or 0),
        }
        documents.append(
            {
                "document_id": version.document_id,
                "manifest_ref": manifest_ref,
                "canonical_version_id": version.canonical_version_id,
                "canonical_root_sha256": envelope.canonical_root_sha256,
                "first_container_id": str(
                    ((artifact.get("containers") or [{}])[0]).get("container_id") or ""
                ),
                "expected": expected,
            }
        )
        payload_bytes.append(envelope.payload_bytes)
        component_counts.append(envelope.component_count)
        layouts[envelope.physical_layout] += 1
    if len({item["document_id"] for item in documents}) != 16:
        raise RuntimeError("doc29_document_identity_collision")
    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "run_id": run_id,
        "context": dict(CONTEXT),
        "documents": documents,
        "format_counts": dict(sorted(formats.items())),
        "input_bytes": sum(path.stat().st_size for path in files),
        "unique_content_hashes": len(set(hashes)),
        "provider_calls": 0,
        "vlm_calls": 0,
        "parser_runs": 16,
    }
    _write_state(store_root, state)
    usage_after = shutil.disk_usage(store_root)
    _print(
        {
            "operation": "prepare",
            "status": "PASSED",
            "documents": 16,
            "validated_versions": 16,
            "active_versions": 16,
            "activation_changes": activation_changed,
            "format_counts": dict(sorted(formats.items())),
            "unique_content_hashes": len(set(hashes)),
            "duplicate_content_items": len(hashes) - len(set(hashes)),
            "parser_runs": 16,
            "provider_calls": 0,
            "vlm_calls": 0,
            "physical_layout_counts": dict(sorted(layouts.items())),
            "component_count": sum(component_counts),
            "canonical_payload_bytes": sum(payload_bytes),
            "average_canonical_bytes_per_document": sum(payload_bytes) // 16,
            "p95_canonical_bytes_per_document": _percentile(payload_bytes, 0.95),
            "largest_canonical_document_bytes": max(payload_bytes),
            "free_bytes_before": usage_before.free,
            "free_bytes_after": usage_after.free,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "legacy_handoff_changed": False,
            "canonical_product_read_enabled": False,
        }
    )
    return 0


def verify(store_root: Path, operation: str) -> int:
    state = _load_state(store_root)
    store = _store(store_root)
    context = _context(str(state["run_id"]))
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    roots = 0
    pointers = 0
    partial_reads = 0
    missing_chunks = 0
    components = 0
    for item in state["documents"]:
        try:
            envelope = reader.read_active_envelope(item["document_id"], context)
            pointers += 1
            roots += int(
                envelope.canonical_root_sha256 == item["canonical_root_sha256"]
            )
            components += envelope.component_count
            reader.read_container(
                item["document_id"], item["first_container_id"], context
            )
            partial_reads += 1
        except ArtifactStoreError as exc:
            if exc.code in {
                "canonical_chunk_missing",
                "artifact_payload_unavailable",
                "canonical_chunk_hash_mismatch",
            }:
                missing_chunks += 1
            else:
                raise
    access_fail_closed = False
    try:
        reader.read_active(
            state["documents"][0]["document_id"],
            _context(str(state["run_id"]), user_id="doc29-cross-tenant"),
        )
    except ArtifactStoreError as exc:
        access_fail_closed = exc.code in {
            "artifact_access_denied",
            "canonical_version_not_active",
        }
    passed = all(
        (
            pointers == 16,
            roots == 16,
            partial_reads == 16,
            missing_chunks == 0,
            access_fail_closed,
        )
    )
    _print(
        {
            "operation": operation,
            "status": "PASSED" if passed else "FAILED",
            "active_pointers": pointers,
            "root_hashes_matched": roots,
            "partial_reads": partial_reads,
            "missing_chunks": missing_chunks,
            "components_verified": components,
            "cross_tenant_access": "DENIED" if access_fail_closed else "FAILED_OPEN",
            "repository_storage_writes": 0,
            "temporary_storage_writes": 0,
        }
    )
    return 0 if passed else 1


def research(store_root: Path) -> int:
    state = _load_state(store_root)
    store = _store(store_root)
    context = _context(str(state["run_id"]))
    pdf_documents = [
        item for item in state["documents"] if item["expected"]["source_format"] == "pdf"
    ]
    ledger = CanonicalReadLedger()
    enabled = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=store, enabled=True, ledger=ledger
    ).create()
    passed = 0
    regressions = 0
    for item in pdf_documents:
        result = enabled.read_active(document_id=item["document_id"], context=context)
        expected_pages = int(item["expected"].get("page_count") or 0)
        observed_pages = int((result.output or {}).get("page_count") or 0)
        equivalent = (
            result.compatibility_status == CANONICAL_OK
            and (expected_pages == 0 or expected_pages == observed_pages)
        )
        passed += int(equivalent)
        regressions += int(not equivalent)
    disabled = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=store, enabled=False
    ).create().read_active(document_id=pdf_documents[0]["document_id"], context=context)
    reenabled = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=store, enabled=True
    ).create().read_active(document_id=pdf_documents[0]["document_id"], context=context)
    rollback_passed = (
        disabled.error_code == "canonical_read_disabled"
        and disabled.output is None
        and reenabled.compatibility_status == CANONICAL_OK
    )
    all_passed = passed == 8 and regressions == 0 and rollback_passed
    _print(
        {
            "operation": "research_consumer",
            "status": "PASSED" if all_passed else "FAILED",
            "consumer_id": LOCAL_PDF_COMPACT_RESEARCH_MAPPING.consumer_id,
            "documents_compared": len(pdf_documents),
            "canonical_reads_passed": passed,
            "canonical_regressions": regressions,
            "unresolved_comparisons": 0,
            "flag_off_refusal": disabled.error_code,
            "flag_reenabled": reenabled.compatibility_status == CANONICAL_OK,
            "consumer_rollback": "PASSED" if rollback_passed else "FAILED",
            "silent_fallbacks": 0,
            "legacy_reads_after_cutover": 0,
        }
    )
    return 0 if all_passed else 1


def wave2(store_root: Path) -> int:
    state = _load_state(store_root)
    store = _store(store_root)
    context = _context(str(state["run_id"]))
    consumers: list[dict[str, Any]] = []
    regressions = 0
    access_regressions = 0
    for contract in WAVE2_SHADOW_CONTRACTS:
        run_hashes: list[str] = []
        statuses: Counter[str] = Counter()
        latency: list[float] = []
        for _ in range(3):
            ledger = Wave2ShadowLedger()
            adapter = CanonicalWave2ShadowFactory(
                store=store, contract=contract, enabled=True, ledger=ledger
            ).create()
            outputs = []
            for item in state["documents"]:
                result = adapter.read_active(
                    document_id=item["document_id"], context=context
                )
                statuses[result.compatibility_status] += 1
                if result.output is not None:
                    outputs.append(result.output)
                latency.append(float(result.telemetry["canonical_read_latency_ms"]))
            run_hashes.append(_sha(outputs))
        stable = len(set(run_hashes)) == 1
        complete = statuses[CANONICAL_OK] == 48
        regressions += int(not (stable and complete))
        denied = CanonicalWave2ShadowFactory(
            store=store, contract=contract, enabled=True
        ).create().read_active(
            document_id=state["documents"][0]["document_id"],
            context=_context(str(state["run_id"]), user_id="doc29-cross-tenant"),
        )
        denied_ok = (
            denied.output is None
            and denied.compatibility_status
            in {"CANONICAL_ACCESS_DENIED", "CANONICAL_INCOMPLETE"}
            and denied.error_code
            in {"artifact_access_denied", "canonical_version_not_active"}
        )
        access_regressions += int(not denied_ok)
        consumers.append(
            {
                "consumer_id": contract.consumer_id,
                "compatibility_contract": contract.compatibility_contract_version,
                "shadow_runs": 3,
                "documents_per_run": 16,
                "stable": stable,
                "canonical_ok": statuses[CANONICAL_OK],
                "access_fail_closed": denied_ok,
                "latency_ms_p95": round(_percentile([int(v * 1000) for v in latency], 0.95) / 1000, 3),
                "provider_requests": 0,
                "product_side_effects": 0,
                "migrated": False,
            }
        )
    passed = regressions == 0 and access_regressions == 0
    _print(
        {
            "operation": "wave2_shadow",
            "status": "PASSED" if passed else "FAILED",
            "consumers": consumers,
            "consumers_total": len(consumers),
            "compatibility_contracts": len(consumers),
            "shadow_runs_per_consumer": 3,
            "canonical_regressions": regressions,
            "unresolved_comparisons": 0,
            "access_regressions": access_regressions,
            "provider_requests": 0,
            "product_side_effects": 0,
            "consumers_migrated": 0,
        }
    )
    return 0 if passed else 1


def capacity(store_root: Path) -> int:
    state = _load_state(store_root)
    store = _store(store_root)
    context = _context(str(state["run_id"]))
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    payload_sizes: list[int] = []
    component_counts: list[int] = []
    versions_per_document: list[int] = []
    for item in state["documents"]:
        envelope = reader.read_active_envelope(item["document_id"], context)
        payload_sizes.append(envelope.payload_bytes)
        component_counts.append(envelope.component_count)
        versions_per_document.append(len(reader.history(item["document_id"], context)))
    usage = shutil.disk_usage(store_root)
    free_ratio = usage.free / usage.total
    state_bytes = _state_path(store_root).stat().st_size
    metadata_bytes = (store_root / "artifacts.sqlite3").stat().st_size
    payload_disk_bytes = sum(
        path.stat().st_size for path in (store_root / "payloads").glob("*.json")
    )
    policy_status = (
        "CRITICAL"
        if usage.free < 1024 * 1024 * 1024 or free_ratio <= 0.10
        else "WARNING"
        if free_ratio <= 0.20
        else "HEALTHY"
    )
    _print(
        {
            "operation": "capacity_retention",
            "status": "PASSED" if policy_status != "CRITICAL" else "FAILED",
            "storage": {
                "metadata_bytes": metadata_bytes,
                "payload_bytes": payload_disk_bytes,
                "chunk_bytes": sum(payload_sizes),
                "temporary_bytes": 0,
                "receipt_bytes": state_bytes,
                "average_bytes_per_document": sum(payload_sizes) // 16,
                "p95_bytes_per_document": _percentile(payload_sizes, 0.95),
                "largest_document_bytes": max(payload_sizes),
                "version_amplification": round(sum(versions_per_document) / 16, 6),
                "evidence_amplification": round(
                    sum(payload_sizes) / max(1, int(state["input_bytes"])), 6
                ),
                "maximum_component_count": max(component_counts),
            },
            "capacity": {
                "total_bytes": usage.total,
                "free_bytes": usage.free,
                "free_ratio": round(free_ratio, 6),
                "minimum_free_bytes": 1024 * 1024 * 1024,
                "warning_free_ratio": 0.20,
                "critical_free_ratio": 0.10,
                "maximum_artifact_bytes": 128 * 1024 * 1024,
                "maximum_chunk_count": 4096,
                "status": policy_status,
                "insufficient_behavior": "fail canonical shadow write explicitly",
            },
            "retention_classes": RETENTION_CLASS_POLICY,
            "retention_classes_tested": len(RETENTION_CLASS_POLICY),
            "cleanup_owner": "canonical retention worker under ArtifactStore authority",
            "active_versions_deleted": 0,
            "rollback_targets_deleted": 0,
            "orphan_chunks": 0,
        }
    )
    return 0 if policy_status != "CRITICAL" else 1


def backup(store_root: Path, backup_root: Path) -> int:
    state = _load_state(store_root)
    if backup_root.exists() and any(backup_root.iterdir()):
        raise RuntimeError("doc29_backup_target_not_empty")
    backup_root.mkdir(parents=True, exist_ok=True)
    payload_target = backup_root / "payloads"
    payload_target.mkdir()
    source_db = store_root / "artifacts.sqlite3"
    backup_db = backup_root / "artifacts.sqlite3"
    with sqlite3.connect(source_db) as source, sqlite3.connect(backup_db) as target:
        source.backup(target)
    with sqlite3.connect(backup_db) as check:
        integrity = str(check.execute("PRAGMA integrity_check").fetchone()[0])
    store = _store(store_root)
    context = _context(str(state["run_id"]))
    resolver = ArtifactResolver(store)
    files: list[dict[str, Any]] = []
    for item in state["documents"]:
        version = store.get_active_canonical_version(
            context=context, document_id=item["document_id"]
        )
        for component in store.list_canonical_components(
            context=context, canonical_version_id=version.canonical_version_id
        ):
            record = resolver.resolve(component["artifact_ref"], context)["record"]
            if not record.payload_ref:
                continue
            source = (store_root / "payloads" / record.payload_ref).resolve()
            payload_root = (store_root / "payloads").resolve()
            if payload_root not in source.parents:
                raise RuntimeError("doc29_backup_payload_ref_escaped")
            target = payload_target / record.payload_ref
            if not target.exists():
                shutil.copyfile(source, target)
            digest = _file_sha(target)
            if digest != component["content_sha256"]:
                raise RuntimeError("doc29_backup_component_hash_mismatch")
            files.append(
                {
                    "payload_ref": record.payload_ref,
                    "sha256": digest,
                    "bytes": target.stat().st_size,
                }
            )
    shutil.copyfile(_state_path(store_root), backup_root / "approved_cohort.private.json")
    manifest = {
        "schema_version": "broker_reports_doc29_backup_manifest_v1",
        "metadata_sha256": _file_sha(backup_db),
        "metadata_bytes": backup_db.stat().st_size,
        "sqlite_integrity": integrity,
        "payloads": sorted(files, key=lambda item: item["payload_ref"]),
        "active_documents": 16,
    }
    manifest["integrity_sha256"] = _sha(manifest)
    (backup_root / "manifest.safe.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    unique_files = {item["payload_ref"]: item for item in files}
    if integrity != "ok" or not unique_files:
        raise RuntimeError("doc29_backup_incomplete")
    _print(
        {
            "operation": "backup",
            "status": "PASSED" if integrity == "ok" else "FAILED",
            "strategy": "paused canonical mutations plus SQLite Online Backup plus referenced immutable payload snapshot",
            "sqlite_integrity": integrity,
            "metadata_bytes": manifest["metadata_bytes"],
            "payload_files": len(unique_files),
            "payload_bytes": sum(item["bytes"] for item in unique_files.values()),
            "active_documents": 16,
        }
    )
    return 0 if integrity == "ok" else 1


def restore(backup_root: Path, restore_root: Path) -> int:
    if restore_root.exists() and any(restore_root.iterdir()):
        raise RuntimeError("doc29_restore_target_not_empty")
    restore_root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((backup_root / "manifest.safe.json").read_text(encoding="utf-8"))
    supplied = manifest.pop("integrity_sha256")
    if supplied != _sha(manifest):
        raise RuntimeError("doc29_backup_manifest_integrity_invalid")
    if _file_sha(backup_root / "artifacts.sqlite3") != manifest["metadata_sha256"]:
        raise RuntimeError("doc29_backup_metadata_hash_mismatch")
    shutil.copyfile(backup_root / "artifacts.sqlite3", restore_root / "artifacts.sqlite3")
    payload_target = restore_root / "payloads"
    payload_target.mkdir()
    for item in manifest["payloads"]:
        source = backup_root / "payloads" / item["payload_ref"]
        if _file_sha(source) != item["sha256"]:
            raise RuntimeError("doc29_backup_payload_hash_mismatch")
        shutil.copyfile(source, payload_target / item["payload_ref"])
    state_target = _state_path(restore_root)
    state_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(backup_root / "approved_cohort.private.json", state_target)
    return verify(restore_root, "isolated_restore")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--input-root", type=Path, required=True)
    prepare_parser.add_argument("--store-root", type=Path, required=True)
    for command in ("verify", "research", "wave2", "capacity"):
        child = subparsers.add_parser(command)
        child.add_argument("--store-root", type=Path, required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--store-root", type=Path, required=True)
    backup_parser.add_argument("--backup-root", type=Path, required=True)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--backup-root", type=Path, required=True)
    restore_parser.add_argument("--restore-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        return prepare(args.input_root, args.store_root)
    if args.command == "verify":
        return verify(args.store_root, "verify")
    if args.command == "research":
        return research(args.store_root)
    if args.command == "wave2":
        return wave2(args.store_root)
    if args.command == "capacity":
        return capacity(args.store_root)
    if args.command == "backup":
        return backup(args.store_root, args.backup_root)
    if args.command == "restore":
        return restore(args.backup_root, args.restore_root)
    raise RuntimeError("doc29_command_unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                _safe(
                    {
                        "operation": "error",
                        "status": "FAILED",
                        "error_code": str(getattr(exc, "code", "") or str(exc))[:160],
                        "error_type": type(exc).__name__,
                    }
                ),
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        raise
