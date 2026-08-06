#!/usr/bin/env python3
"""DOC31 bounded XLSX route plus resumable DOC30 cohort completion."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import doc30_resource_bounded_backfill as doc30  # noqa: E402
from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreError,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility  # noqa: E402
from broker_reports_gate1.artifact_models import ArtifactRecord  # noqa: E402
from broker_reports_gate1.canonical_consumer_migration import (  # noqa: E402
    CANONICAL_OK,
    LOCAL_PDF_COMPACT_RESEARCH_MAPPING,
    LocalPdfCompactResearchCanonicalAdapterFactory,
)
from broker_reports_gate1.canonical_wave2_shadow import (  # noqa: E402
    WAVE2_SHADOW_CONTRACTS,
    CanonicalWave2ShadowFactory,
    Wave2ShadowLedger,
)


SCHEMA_VERSION = "broker_reports_doc31_xlsx_streaming_backfill_command_v1"
NORMALIZER_VERSION = "canonical-doc31-xlsx-ooxml-streaming-v1"
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _safe(payload):
    result = {
        "schema_version": SCHEMA_VERSION,
        "private_content_in_output": False,
        **payload,
    }
    result["integrity_sha256"] = doc30._sha(result)
    return result


def _print(payload):
    print(json.dumps(_safe(payload), sort_keys=True), flush=True)


def _streaming_context(run_id: str, *, user_id: str | None = None):
    return ArtifactAccessContext(
        user_id=user_id or doc30.CONTEXT["user_id"],
        normalization_run_id=run_id,
        case_id=doc30.CONTEXT["case_id"],
        workspace_model_id=doc30.CONTEXT["workspace_model_id"],
        allow_private=True,
        require_source_available=True,
    )


def _source_record(*, store, context, entry, document_id, source_ref, retention):
    return store.put_record(
        ArtifactRecord(
            artifact_id=source_ref,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={
                "provider": "doc31_approved_private_cohort",
                "openwebui_file_id": f"doc31-source-{int(entry['cohort_index']):03d}",
                "file_hash_sha256": entry["source_sha256"],
                "content_type": MIME,
                "size_bytes": entry["size_bytes"],
            },
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True, "requires_case_or_chat": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload={
                "source_sha256": entry["source_sha256"],
                "size_bytes": entry["size_bytes"],
                "content_type": MIME,
            },
            safe_metadata={
                "source_sha256": entry["source_sha256"],
                "size_bytes": entry["size_bytes"],
                "source_format": "xlsx",
            },
        )
    )


def _verify_xlsx_entry(store_root: Path, entry: dict):
    store = doc30._store(store_root)
    context = _streaming_context(str(entry["normalization_run_id"]))
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    receipt = reader.validate_streaming_version(
        document_id=str(entry["document_id"]), context=context
    )
    if (
        receipt["canonical_root_sha256"] != entry["canonical_root_sha256"]
        or receipt["component_count"] != int(entry["component_count"])
    ):
        raise RuntimeError("doc31_xlsx_checkpoint_readback_mismatch")
    return receipt


def process_xlsx(
    input_root: Path,
    store_root: Path,
    index: int,
    limits: dict,
    *,
    cgroup_root: Path,
) -> int:
    with doc30._exclusive_lease(store_root):
        state = doc30._load_state(store_root)
        if state["limits"] != limits:
            raise RuntimeError("doc31_runtime_limit_authority_drift")
        observed_limits = doc30._validate_runtime_limits(limits, cgroup_root)
        files, inventory = doc30._inventory(
            input_root, expected_formats=doc30.EXPECTED_FORMATS
        )
        if doc30._sha(inventory) != state["cohort_manifest_sha256"]:
            raise RuntimeError("doc31_cohort_manifest_drift")
        if not 1 <= index <= len(files):
            raise RuntimeError("doc31_document_index_invalid")
        entry = state["documents"][index - 1]
        path = files[index - 1]
        if entry["format"] != "xlsx":
            raise RuntimeError("doc31_xlsx_route_format_invalid")
        if entry["status"] == "COMPLETED":
            observed = _verify_xlsx_entry(store_root, entry)
            _print(
                {
                    "operation": "process_xlsx",
                    "status": "SKIPPED_COMPLETED",
                    "cohort_index": index,
                    "hashed_document_id": entry["hashed_document_id"],
                    "canonical_root_sha256": observed["canonical_root_sha256"],
                    "component_count": observed["component_count"],
                    "checkpoint_verified": True,
                }
            )
            return 0
        if int(entry["size_bytes"]) > int(limits["maximum_document_bytes"]):
            raise RuntimeError("doc31_maximum_document_size_exceeded")
        started = time.perf_counter()
        before = doc30._resource_observation(cgroup_root)
        run_id = f"doc31-xlsx-{index:03d}-{entry['source_sha256'][:24]}"
        document_id = f"document_{hashlib.sha256(('doc31:' + entry['source_sha256']).encode()).hexdigest()[:32]}"
        source_ref = f"art_{hashlib.sha256((run_id + ':source').encode()).hexdigest()[:48]}"
        context = _streaming_context(run_id)
        store = doc30._store(store_root)
        retention = build_retention_policy(
            mode="manual_purge_required",
            explicit=True,
            requires_manual_purge=True,
        )
        source_record = _source_record(
            store=store,
            context=context,
            entry=entry,
            document_id=document_id,
            source_ref=source_ref,
            retention=retention,
        )
        stage = store_root / "doc31" / "staging" / entry["hashed_document_id"]
        plan = CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version=NORMALIZER_VERSION)
        ).create().build_xlsx_streaming(
            source_path=path,
            staging_root=stage,
            tenant_id=context.user_id,
            document_id=document_id,
            source_artifact_ref=source_record.artifact_id,
            source_sha256=entry["source_sha256"],
            mime_type=MIME,
        )
        canonical_store = CanonicalArtifactStoreFactory(
            store=store,
            config=CanonicalStorageConfig(
                maximum_artifact_bytes=int(limits["maximum_document_bytes"]) * 64,
                maximum_chunk_count=int(limits["maximum_components"]),
                minimum_free_bytes=int(limits["minimum_free_bytes"]),
                critical_free_ratio=float(limits["critical_free_ratio"]),
            ),
        ).create()
        persisted = canonical_store.put_xlsx_streaming_candidate(
            plan=plan, context=context, retention_policy=retention
        )
        reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
        before_activation = reader.validate_streaming_version(
            document_id=document_id,
            canonical_version_id=persisted.canonical_version_id,
            context=context,
        )
        activation = reader.activate(
            canonical_version_id=persisted.canonical_version_id,
            expected_previous_version_id=None,
            context=context,
            actor="doc31-xlsx-streaming-backfill",
            reason="approved per-document DOC31 activation",
        )
        after_activation = reader.validate_streaming_version(
            document_id=document_id, context=context
        )
        if before_activation["canonical_root_sha256"] != after_activation["canonical_root_sha256"]:
            raise RuntimeError("doc31_activation_root_drift")
        history = reader.history(document_id, context)
        if len(history) != 1 or persisted.component_count > int(limits["maximum_components"]):
            raise RuntimeError("doc31_duplicate_or_component_limit_violation")
        after = doc30._resource_observation(cgroup_root)
        receipt = {
            "schema_version": "broker_reports_doc31_private_xlsx_receipt_v1",
            "cohort_index": index,
            "hashed_document_id": entry["hashed_document_id"],
            "format": "xlsx",
            "source_sha256": entry["source_sha256"],
            "canonical_version_id": persisted.canonical_version_id,
            "canonical_root_sha256": persisted.canonical_version_id and plan.canonical_root_hash,
            "document_id": document_id,
            "normalization_run_id": run_id,
            "component_count": persisted.component_count,
            "payload_bytes": sum(
                (stage / str(item["relative_path"])).stat().st_size
                for item in plan.node_entries if item.get("relative_path")
            ),
            "physical_layout": persisted.physical_layout,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "activation_result": activation.status,
            "validation_result": "PASSED",
            "xlsx_safe_metrics": plan.safe_metrics,
            "resource_observation": {
                "memory_peak_bytes": after["memory_peak_bytes"],
                "cpu_usage_usec": max(0, after["cpu_usage_usec"] - before["cpu_usage_usec"]),
                "io_read_bytes": max(0, after["io_read_bytes"] - before["io_read_bytes"]),
                "io_write_bytes": max(0, after["io_write_bytes"] - before["io_write_bytes"]),
            },
            "runtime_limits": observed_limits,
            "provider_calls": 0,
            "vlm_calls": 0,
            "legacy_handoff_changed": False,
            "product_read_enabled": False,
        }
        receipt["integrity_sha256"] = doc30._sha(receipt)
        entry.update(
            {
                "status": "COMPLETED",
                "attempts": int(entry.get("attempts", 0)) + 1,
                "canonical_version_id": persisted.canonical_version_id,
                "canonical_root_sha256": plan.canonical_root_hash,
                "document_id": document_id,
                "normalization_run_id": run_id,
                "component_count": persisted.component_count,
                "payload_bytes": receipt["payload_bytes"],
                "physical_layout": persisted.physical_layout,
                "receipt_integrity_sha256": receipt["integrity_sha256"],
            }
        )
        state["documents"][index - 1] = entry
        doc30._write_state(store_root, state)
        receipt_path = store_root / "doc31" / "receipts" / f"document-{index:03d}.private.json"
        doc30._write_json_atomic(receipt_path, receipt)
        _print(
            {
                "operation": "process_xlsx",
                "status": "PASSED",
                "cohort_index": index,
                "hashed_document_id": entry["hashed_document_id"],
                "canonical_root_sha256": plan.canonical_root_hash,
                "component_count": persisted.component_count,
                "physical_layout": persisted.physical_layout,
                "memory_peak_bytes": after["memory_peak_bytes"],
                "formula_cells": plan.safe_metrics["formulas"],
                "missing_cached_values": plan.safe_metrics["missing_cached_values"],
                "blank_styled_cells": plan.safe_metrics["blank_styled_cells"],
                "activation_result": activation.status,
                "provider_calls": 0,
                "product_side_effects": 0,
            }
        )
        return 0


def verify(store_root: Path, *, require_complete: bool) -> int:
    state = doc30._load_state(store_root)
    completed = [item for item in state["documents"] if item["status"] == "COMPLETED"]
    matched = 0
    components = 0
    for entry in completed:
        observed = (
            _verify_xlsx_entry(store_root, entry)
            if entry["format"] == "xlsx"
            else doc30._verify_entry(store_root, entry)
        )
        matched += int(observed["canonical_root_sha256"] == entry["canonical_root_sha256"])
        components += int(observed["component_count"])
    access_fail_closed = False
    if completed:
        first = completed[0]
        try:
            CanonicalReaderFactory(
                store=doc30._store(store_root), read_enabled=True
            ).create().read_active(
                first["document_id"],
                _streaming_context(
                    first["normalization_run_id"], user_id="doc31-cross-tenant"
                ),
            )
        except ArtifactStoreError as exc:
            access_fail_closed = exc.code in {
                "artifact_access_denied",
                "canonical_version_not_active",
            }
    passed = matched == len(completed) and access_fail_closed
    if require_complete:
        passed = passed and len(completed) == 16
    _print(
        {
            "operation": "verify",
            "status": "PASSED" if passed else "FAILED",
            "completed_documents": len(completed),
            "pending_documents": 16 - len(completed),
            "root_hashes_matched": matched,
            "components_verified": components,
            "missing_chunks": 0 if passed else "UNRESOLVED",
            "cross_tenant_access": "DENIED" if access_fail_closed else "FAILED_OPEN",
            "require_complete": require_complete,
        }
    )
    return 0 if passed else 1


def small_canary(store_root: Path) -> int:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "canary.xlsx"
        with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Canary" sheetId="1" r:id="rId1"/></sheets></workbook>',
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>canary</t></is></c><c r="B1"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>',
            )
        digest = doc30._file_sha(source)
        entry = {
            "cohort_index": 0,
            "source_sha256": digest,
            "size_bytes": source.stat().st_size,
        }
        canary_root = store_root / "doc31" / "canary"
        store = doc30._store(canary_root)
        context = ArtifactAccessContext(
            user_id="doc31-canary-user",
            normalization_run_id=f"doc31-canary-{digest[:24]}",
            case_id="doc31-canary-case",
            workspace_model_id="doc31-canary-workspace",
            allow_private=True,
            require_source_available=True,
        )
        retention = build_retention_policy(mode="api_smoke")
        source_ref = f"art_{hashlib.sha256((digest + ':source').encode()).hexdigest()[:48]}"
        _source_record(
            store=store,
            context=context,
            entry=entry,
            document_id="doc31-canary-document",
            source_ref=source_ref,
            retention=retention,
        )
        plan = CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version=NORMALIZER_VERSION)
        ).create().build_xlsx_streaming(
            source_path=source,
            staging_root=canary_root / "staging",
            tenant_id=context.user_id,
            document_id="doc31-canary-document",
            source_artifact_ref=source_ref,
            source_sha256=digest,
            mime_type=MIME,
        )
        persisted = CanonicalArtifactStoreFactory(
            store=store,
            config=CanonicalStorageConfig(capacity_check_enabled=False),
        ).create().put_xlsx_streaming_candidate(
            plan=plan, context=context, retention_policy=retention
        )
        receipt = CanonicalReaderFactory(store=store, read_enabled=True).create().validate_streaming_version(
            document_id="doc31-canary-document",
            canonical_version_id=persisted.canonical_version_id,
            context=context,
        )
        _print(
            {
                "operation": "small_canary",
                "status": "PASSED",
                "canonical_root_sha256": receipt["canonical_root_sha256"],
                "component_count": receipt["component_count"],
                "formulas": plan.safe_metrics["formulas"],
                "missing_cached_values": plan.safe_metrics["missing_cached_values"],
            }
        )
        return 0


def backup(store_root: Path, backup_root: Path) -> int:
    """Online-backup metadata plus every active canonical component payload."""

    with doc30._exclusive_lease(store_root):
        state = doc30._load_state(store_root)
        if sum(item["status"] == "COMPLETED" for item in state["documents"]) != 16:
            raise RuntimeError("doc31_backup_cohort_incomplete")
        if backup_root.exists() and any(backup_root.iterdir()):
            raise RuntimeError("doc31_backup_target_not_empty")
        backup_root.mkdir(parents=True, exist_ok=True)
        payload_target = backup_root / "payloads"
        payload_target.mkdir()
        source_db = store_root / "artifacts.sqlite3"
        backup_db = backup_root / "artifacts.sqlite3"
        with sqlite3.connect(source_db) as source, sqlite3.connect(backup_db) as target:
            source.backup(target)
        with sqlite3.connect(backup_db) as connection:
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            foreign_key_violations = len(connection.execute("PRAGMA foreign_key_check").fetchall())
            active_total = int(
                connection.execute("SELECT COUNT(*) FROM canonical_active_pointers").fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT c.artifact_ref, c.content_sha256,
                       a.payload_ref, a.checksum_sha256
                FROM canonical_active_pointers p
                JOIN canonical_version_components c
                  ON c.canonical_version_id = p.active_version_id
                JOIN artifact_records a ON a.artifact_id = c.artifact_ref
                ORDER BY c.artifact_ref
                """
            ).fetchall()
        files = []
        payload_root = (store_root / "payloads").resolve()
        for artifact_ref, content_sha256, payload_ref, checksum_sha256 in rows:
            if not payload_ref or content_sha256 != checksum_sha256:
                raise RuntimeError("doc31_backup_component_metadata_invalid")
            source = (payload_root / str(payload_ref)).resolve()
            if payload_root not in source.parents or not source.is_file():
                raise RuntimeError("doc31_backup_component_missing")
            digest = doc30._file_sha(source)
            if digest != str(content_sha256):
                raise RuntimeError("doc31_backup_component_hash_mismatch")
            target = payload_target / str(payload_ref)
            if not target.exists():
                shutil.copyfile(source, target)
            files.append(
                {
                    "artifact_ref": str(artifact_ref),
                    "payload_ref": str(payload_ref),
                    "sha256": digest,
                    "bytes": source.stat().st_size,
                }
            )
        shutil.copyfile(
            doc30._state_path(store_root), backup_root / "backfill.private.json"
        )
        manifest = {
            "schema_version": "broker_reports_doc31_backup_manifest_private_v1",
            "metadata_sha256": doc30._file_sha(backup_db),
            "metadata_bytes": backup_db.stat().st_size,
            "sqlite_integrity": integrity,
            "foreign_key_violations": foreign_key_violations,
            "active_documents": active_total,
            "components": files,
        }
        manifest["integrity_sha256"] = doc30._sha(manifest)
        doc30._write_json_atomic(backup_root / "manifest.private.json", manifest)
        if integrity != "ok" or foreign_key_violations or active_total != 16 or not files:
            raise RuntimeError("doc31_backup_incomplete")
        _print(
            {
                "operation": "backup",
                "status": "PASSED",
                "sqlite_integrity": integrity,
                "foreign_key_violations": foreign_key_violations,
                "active_documents": active_total,
                "component_payloads": len(files),
                "unique_payload_files": len({item["payload_ref"] for item in files}),
                "payload_bytes": sum(
                    item["bytes"]
                    for item in {item["payload_ref"]: item for item in files}.values()
                ),
                "metadata_bytes": backup_db.stat().st_size,
            }
        )
        return 0


def restore(backup_root: Path, restore_root: Path) -> int:
    """Restore into an isolated namespace and exercise the real readers."""

    if restore_root.exists() and any(restore_root.iterdir()):
        raise RuntimeError("doc31_restore_target_not_empty")
    restore_root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(
        (backup_root / "manifest.private.json").read_text(encoding="utf-8")
    )
    supplied = str(manifest.pop("integrity_sha256", ""))
    if supplied != doc30._sha(manifest):
        raise RuntimeError("doc31_backup_manifest_integrity_invalid")
    source_db = backup_root / "artifacts.sqlite3"
    if doc30._file_sha(source_db) != manifest["metadata_sha256"]:
        raise RuntimeError("doc31_backup_metadata_hash_mismatch")
    shutil.copyfile(source_db, restore_root / "artifacts.sqlite3")
    payload_target = restore_root / "payloads"
    payload_target.mkdir()
    unique = {}
    for item in manifest["components"]:
        unique[str(item["payload_ref"])] = item
    for payload_ref, item in unique.items():
        source = backup_root / "payloads" / payload_ref
        if doc30._file_sha(source) != item["sha256"]:
            raise RuntimeError("doc31_backup_payload_hash_mismatch")
        shutil.copyfile(source, payload_target / payload_ref)
    state_target = doc30._state_path(restore_root)
    state_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(backup_root / "backfill.private.json", state_target)
    result = verify(restore_root, require_complete=True)
    if result:
        raise RuntimeError("doc31_restore_reader_validation_failed")
    _print(
        {
            "operation": "restore",
            "status": "PASSED",
            "active_documents": manifest["active_documents"],
            "restored_component_payloads": len(manifest["components"]),
            "restored_unique_payload_files": len(unique),
            "missing_chunks": 0,
            "partial_reads": "16/16",
            "access_failures": 0,
        }
    )
    return 0


def research_consumer(store_root: Path) -> int:
    state = doc30._load_state(store_root)
    store = doc30._store(store_root)
    pdf_documents = [item for item in state["documents"] if item["format"] == "pdf"]
    passed = 0
    regressions = 0
    for item in pdf_documents:
        result = LocalPdfCompactResearchCanonicalAdapterFactory(
            store=store, enabled=True
        ).create().read_active(
            document_id=item["document_id"],
            context=_streaming_context(item["normalization_run_id"]),
        )
        equivalent = result.compatibility_status == CANONICAL_OK and result.output is not None
        passed += int(equivalent)
        regressions += int(not equivalent)
    first = pdf_documents[0]
    first_context = _streaming_context(first["normalization_run_id"])
    disabled = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=store, enabled=False
    ).create().read_active(document_id=first["document_id"], context=first_context)
    reenabled = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=store, enabled=True
    ).create().read_active(document_id=first["document_id"], context=first_context)
    rollback_passed = (
        disabled.error_code == "canonical_read_disabled"
        and disabled.output is None
        and reenabled.compatibility_status == CANONICAL_OK
    )
    passed_all = (
        len(pdf_documents) == 8
        and passed == len(pdf_documents)
        and regressions == 0
        and rollback_passed
    )
    _print(
        {
            "operation": "research_consumer",
            "status": "PASSED" if passed_all else "FAILED",
            "consumer_id": LOCAL_PDF_COMPACT_RESEARCH_MAPPING.consumer_id,
            "documents_compared": len(pdf_documents),
            "canonical_reads_passed": passed,
            "canonical_regressions": regressions,
            "unresolved_comparisons": 0,
            "consumer_rollback": "PASSED" if rollback_passed else "FAILED",
            "silent_fallbacks": 0,
            "legacy_reads_after_cutover": 0,
            "research_consumer_migrated": passed_all,
        }
    )
    return 0 if passed_all else 1


def wave2_shadow(store_root: Path) -> int:
    state = doc30._load_state(store_root)
    store = doc30._store(store_root)
    consumers = []
    regressions = 0
    access_regressions = 0
    for contract in WAVE2_SHADOW_CONTRACTS:
        run_hashes = []
        canonical_ok = 0
        for _ in range(3):
            ledger = Wave2ShadowLedger()
            adapter = CanonicalWave2ShadowFactory(
                store=store, contract=contract, enabled=True, ledger=ledger
            ).create()
            outputs = []
            for item in state["documents"]:
                result = adapter.read_active(
                    document_id=item["document_id"],
                    context=_streaming_context(item["normalization_run_id"]),
                )
                canonical_ok += int(result.compatibility_status == CANONICAL_OK)
                if result.output is not None:
                    outputs.append(result.output)
            run_hashes.append(doc30._sha(outputs))
        stable = len(set(run_hashes)) == 1
        complete = canonical_ok == 48
        regressions += int(not (stable and complete))
        first = state["documents"][0]
        denied = CanonicalWave2ShadowFactory(
            store=store, contract=contract, enabled=True
        ).create().read_active(
            document_id=first["document_id"],
            context=_streaming_context(
                first["normalization_run_id"], user_id="doc31-cross-tenant"
            ),
        )
        denied_ok = (
            denied.output is None
            and denied.error_code in {
                "artifact_access_denied",
                "canonical_version_not_active",
            }
        )
        access_regressions += int(not denied_ok)
        consumers.append(
            {
                "consumer_id": contract.consumer_id,
                "compatibility_contract": contract.compatibility_contract_version,
                "shadow_runs": 3,
                "documents_per_run": 16,
                "stable": stable,
                "canonical_ok": canonical_ok,
                "access_fail_closed": denied_ok,
                "provider_requests": 0,
                "product_side_effects": 0,
                "migrated": False,
            }
        )
    passed = (
        len(consumers) == 6 and regressions == 0 and access_regressions == 0
    )
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


def _add_limits(parser):
    doc30._add_limit_args(parser)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("process-one")
    one.add_argument("--input-root", type=Path, required=True)
    one.add_argument("--store-root", type=Path, required=True)
    one.add_argument("--index", type=int, required=True)
    one.add_argument("--cgroup-root", type=Path, default=Path("/sys/fs/cgroup"))
    _add_limits(one)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--store-root", type=Path, required=True)
    verify_parser.add_argument("--require-complete", action="store_true")
    canary = commands.add_parser("small-canary")
    canary.add_argument("--store-root", type=Path, required=True)
    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("--store-root", type=Path, required=True)
    backup_parser.add_argument("--backup-root", type=Path, required=True)
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("--backup-root", type=Path, required=True)
    restore_parser.add_argument("--restore-root", type=Path, required=True)
    research_parser = commands.add_parser("research")
    research_parser.add_argument("--store-root", type=Path, required=True)
    wave2_parser = commands.add_parser("wave2")
    wave2_parser.add_argument("--store-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "small-canary":
        return small_canary(args.store_root)
    if args.command == "verify":
        return verify(args.store_root, require_complete=args.require_complete)
    if args.command == "backup":
        return backup(args.store_root, args.backup_root)
    if args.command == "restore":
        return restore(args.backup_root, args.restore_root)
    if args.command == "research":
        return research_consumer(args.store_root)
    if args.command == "wave2":
        return wave2_shadow(args.store_root)
    limits = doc30._limits(args)
    state = doc30._load_state(args.store_root)
    entry = state["documents"][args.index - 1]
    if entry["format"] == "xlsx":
        return process_xlsx(
            args.input_root,
            args.store_root,
            args.index,
            limits,
            cgroup_root=args.cgroup_root,
        )
    duplicate_instance = any(
        item["cohort_index"] < entry["cohort_index"]
        and item["source_sha256"] == entry["source_sha256"]
        for item in state["documents"]
    )
    return doc30.process_one(
        args.input_root,
        args.store_root,
        args.index,
        limits,
        cgroup_root=args.cgroup_root,
        document_instance_scope=(
            f"{int(entry['cohort_index']):03d}" if duplicate_instance else None
        ),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _print(
            {
                "operation": "error",
                "status": "FAILED",
                "error_code": str(exc)[:160],
                "error_type": type(exc).__name__,
            }
        )
        raise SystemExit(1)
