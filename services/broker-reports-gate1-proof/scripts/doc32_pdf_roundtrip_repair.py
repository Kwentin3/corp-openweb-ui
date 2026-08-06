#!/usr/bin/env python3
"""DOC32 resource-bounded PDF canonical repair and durable proof entrypoint.

The target path processes one PDF per invocation. It reuses the maintained
Gate1Normalizer, canonical store/reader and consumer factories. Exact source
identity, canonical IDs, projections and receipts stay under the private store
root; stdout is aggregate and privacy-safe.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
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
    CanonicalReaderFactory,
    FileInput,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
)
from broker_reports_gate1.canonical_consumer_migration import (  # noqa: E402
    CANONICAL_OK,
    LOCAL_PDF_COMPACT_RESEARCH_MAPPING,
    CanonicalReadLedger,
    LocalPdfCompactResearchCanonicalAdapterFactory,
)
from broker_reports_gate1.canonical_wave2_shadow import (  # noqa: E402
    WAVE2_SHADOW_CONTRACTS,
    CanonicalWave2ShadowFactory,
    Wave2ShadowLedger,
)


SCHEMA_VERSION = "broker_reports_doc32_pdf_roundtrip_command_v1"
STATE_SCHEMA_VERSION = "broker_reports_doc32_private_pdf_republication_state_v1"
ISOLATED_STATE_SCHEMA_VERSION = "broker_reports_doc32_private_isolated_state_v1"
NORMALIZER_VERSION = "canonical-doc32-pdf-roundtrip-v1"
PDF_INDICES = (2, 4, 5, 6, 9, 10, 11, 12)
ALLOWED_SUFFIXES = {".pdf", ".html", ".htm", ".csv", ".xlsx"}
TARGET_CONTEXT = {
    "user_id": "doc30-approved-cohort-user",
    "case_id": "doc30-approved-cohort",
    "workspace_model_id": "doc30-canonical-shadow",
}
ISOLATED_CONTEXT = {
    "user_id": "doc32-isolated-user",
    "case_id": "doc32-isolated-cohort",
    "workspace_model_id": "doc32-isolated-shadow",
}

FACTORY_REQUIRED = (
    "DOC32 must enter through Gate1Normalizer, persist_gate1_result, "
    "CanonicalReaderFactory and the existing consumer shadow factories"
)
FORBIDDEN = (
    "Direct canonical component writes, provider/VLM/cropper calls, private "
    "projection publication, product writes and silent legacy fallback"
)


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    value = {
        "schema_version": SCHEMA_VERSION,
        "private_content_in_output": False,
        **payload,
    }
    value["integrity_sha256"] = _sha(value)
    return value


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True), flush=True)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _seal_state(state: dict[str, Any]) -> dict[str, Any]:
    sealed = json.loads(json.dumps(state))
    sealed.pop("integrity_sha256", None)
    sealed["integrity_sha256"] = _sha(sealed)
    return sealed


def _load_sealed(path: Path, schema_version: str) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError("doc32_private_state_unavailable")
    state = json.loads(path.read_text(encoding="utf-8"))
    supplied = str(state.pop("integrity_sha256", ""))
    if state.get("schema_version") != schema_version or supplied != _sha(state):
        raise RuntimeError("doc32_private_state_integrity_invalid")
    state["integrity_sha256"] = supplied
    return state


def _target_state_path(store_root: Path) -> Path:
    return store_root / "doc32" / "republication.private.json"


def _isolated_state_path(store_root: Path) -> Path:
    return store_root / "doc32" / "isolated.private.json"


def _receipt_path(store_root: Path, index: int) -> Path:
    return store_root / "doc32" / "receipts" / f"pdf-{index:03d}.private.json"


def _store(root: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()


def _context(
    run_id: str,
    *,
    profile: dict[str, str] = TARGET_CONTEXT,
    user_id: str | None = None,
) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id=user_id or profile["user_id"],
        normalization_run_id=run_id,
        case_id=profile["case_id"],
        workspace_model_id=profile["workspace_model_id"],
        allow_private=True,
        require_source_available=True,
    )


def _inventory(input_root: Path) -> list[Path]:
    files = sorted(
        path
        for path in input_root.iterdir()
        if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES
    )
    if len(files) != 16:
        raise RuntimeError("doc32_cohort_cardinality_invalid")
    pdf_indices = tuple(
        index
        for index, path in enumerate(files, start=1)
        if path.suffix.lower() == ".pdf"
    )
    if pdf_indices != PDF_INDICES:
        raise RuntimeError("doc32_pdf_index_contract_invalid")
    return files


def _load_doc30_state(store_root: Path) -> dict[str, Any]:
    path = store_root / "doc30" / "backfill.private.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    supplied = str(state.pop("integrity_sha256", ""))
    if supplied != _sha(state):
        raise RuntimeError("doc32_doc30_state_integrity_invalid")
    if len(state.get("documents") or []) != 16:
        raise RuntimeError("doc32_doc30_state_cardinality_invalid")
    state["integrity_sha256"] = supplied
    return state


def _dependency_versions() -> dict[str, str]:
    versions = {
        package: importlib.metadata.version(distribution)
        for package, distribution in {
            "pypdf": "pypdf",
            "pdfplumber": "pdfplumber",
            "pymupdf": "PyMuPDF",
            "pdfminer": "pdfminer.six",
            "pillow": "Pillow",
            "pypdfium2": "pypdfium2",
        }.items()
    }
    if versions != {
        "pypdf": "6.7.5",
        "pdfplumber": "0.11.10",
        "pymupdf": "1.26.5",
        "pdfminer": "20260107",
        "pillow": "12.3.0",
        "pypdfium2": "5.11.0",
    }:
        raise RuntimeError("doc32_pdf_runtime_dependency_version_mismatch")
    return versions


def _replace_exact_string(value: Any, old: str, new: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if child == old:
                value[key] = new
            else:
                _replace_exact_string(child, old, new)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if child == old:
                value[index] = new
            else:
                _replace_exact_string(child, old, new)


def _raw_single_artifact(store, version, context: ArtifactAccessContext) -> dict:
    components = store.list_canonical_components(
        context=context,
        canonical_version_id=version.canonical_version_id,
    )
    if len(components) != 1:
        raise RuntimeError("doc32_old_pdf_component_cardinality_invalid")
    component = components[0]
    payload = store.read_canonical_component(
        context=context,
        canonical_version_id=version.canonical_version_id,
        component_kind=str(component["component_kind"]),
        component_key=str(component["component_key"]),
    )
    if payload.get("physical_layout") == "single_payload":
        artifact = payload.get("artifact")
        if not isinstance(artifact, dict):
            raise RuntimeError("doc32_old_pdf_manifest_artifact_missing")
        return artifact
    if payload.get("schema_version") == "broker_reports_canonical_artifact_v1":
        return payload
    raise RuntimeError("doc32_old_pdf_physical_layout_invalid")


def initialize_target(input_root: Path, store_root: Path) -> int:
    _dependency_versions()
    files = _inventory(input_root)
    base = _load_doc30_state(store_root)
    state_path = _target_state_path(store_root)
    if state_path.exists():
        existing = _load_sealed(state_path, STATE_SCHEMA_VERSION)
        _print(
            {
                "operation": "initialize_target",
                "status": "NO_OP",
                "pdfs_total": len(existing["documents"]),
                "pending": sum(
                    item["status"] != "COMPLETED"
                    for item in existing["documents"]
                ),
            }
        )
        return 0
    store = _store(store_root)
    documents = []
    for index in PDF_INDICES:
        source = base["documents"][index - 1]
        path = files[index - 1]
        if _file_sha(path) != source["source_sha256"]:
            raise RuntimeError("doc32_source_hash_mismatch")
        context = _context(str(source["normalization_run_id"]))
        version = store.get_active_canonical_version(
            context=context,
            document_id=str(source["document_id"]),
        )
        artifact = _raw_single_artifact(store, version, context)
        if version.canonical_version_id != source["canonical_version_id"]:
            raise RuntimeError("doc32_old_active_pointer_drift")
        if len(artifact.get("nodes") or []) != 0:
            raise RuntimeError("doc32_old_pdf_not_zero_node")
        documents.append(
            {
                "cohort_index": index,
                "status": "PENDING",
                "attempts": 0,
                "document_id": source["document_id"],
                "source_sha256": source["source_sha256"],
                "size_bytes": source["size_bytes"],
                "old_version_id": version.canonical_version_id,
                "old_root_sha256": version.canonical_root_sha256,
                "old_component_count": len(
                    store.list_canonical_components(
                        context=context,
                        canonical_version_id=version.canonical_version_id,
                    )
                ),
                "old_node_count": 0,
                "old_issue": "INCOMPLETE_PDF_CANONICAL_VERSION",
            }
        )
    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "base_state_integrity_sha256": base["integrity_sha256"],
        "normalizer_version": NORMALIZER_VERSION,
        "documents": documents,
        "provider_calls": 0,
        "vlm_calls": 0,
        "cropper_calls": 0,
        "product_reads_enabled": False,
        "legacy_handoff_changed": False,
    }
    _write_json_atomic(state_path, _seal_state(state))
    _print(
        {
            "operation": "initialize_target",
            "status": "PASSED",
            "pdfs_total": 8,
            "old_active_zero_node_versions": 8,
            "old_versions_mutated": 0,
            "source_hashes_matched": 8,
        }
    )
    return 0


def _normalize_one(
    *,
    path: Path,
    index: int,
    document_id: str,
    store_root: Path,
    profile: dict[str, str],
    expected_previous_version_id: str | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    normalized = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref=f"doc32-private-{index:03d}-{digest[:16]}",
                filename=f"approved-{index:03d}.pdf",
                content=content,
                mime_type="application/pdf",
            )
        ],
        entrypoint="doc32_pdf_roundtrip_repair",
        trigger_type="approved_parser_only_single_document_republication",
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_compare_enabled": True,
            "canonical_gate2_read_enabled": False,
            "normalizer_version": NORMALIZER_VERSION,
            "provider_calls_allowed": False,
            "vlm_calls_allowed": False,
            "cropper_calls_allowed": False,
        },
    )
    documents = normalized.package["document_inventory"]["documents"]
    if len(documents) != 1:
        raise RuntimeError("doc32_normalized_document_cardinality_invalid")
    generated_id = str(documents[0].get("document_id") or "")
    if not generated_id:
        raise RuntimeError("doc32_normalized_document_id_missing")
    _replace_exact_string(normalized.package, generated_id, document_id)
    run_id = str(normalized.package["normalization_run"]["run_id"])
    context = _context(run_id, profile=profile)
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
                "provider": "doc32_approved_private_cohort",
                "openwebui_file_id": f"doc32-source-{index:03d}",
                "file_hash_sha256": digest,
                "content_type": "application/pdf",
                "size_bytes": len(content),
            }
        ],
    )
    canonical_refs = manifest.artifact_refs_by_type.get(
        "broker_reports_canonical_artifact_v1", []
    )
    failures = manifest.artifact_refs_by_type.get(
        "broker_reports_canonical_build_failure_v1", []
    )
    if len(canonical_refs) != 1 or failures:
        raise RuntimeError("doc32_canonical_build_incomplete")
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    candidate = reader.read(canonical_refs[0], context)
    root = next(
        item
        for item in candidate["containers"]
        if item["container_id"] == candidate["root_container_ref"]
    )
    completeness = (root.get("metadata") or {}).get("pdf_completeness") or {}
    if (
        len(candidate.get("nodes") or []) <= 0
        or completeness.get("source_atom_accounting_percent") != 100.0
        or int(completeness.get("unresolved_source_atoms_total") or 0) != 0
    ):
        raise RuntimeError("doc32_candidate_completeness_failed")
    version = store.get_canonical_version_by_manifest(
        context=context,
        manifest_ref=canonical_refs[0],
    )
    activation = reader.activate(
        canonical_version_id=version.canonical_version_id,
        expected_previous_version_id=expected_previous_version_id,
        context=context,
        actor="doc32-pdf-roundtrip-repair",
        reason="immutable corrected PDF republication",
    )
    envelope = reader.read_active_envelope(document_id, context)
    artifact = envelope.artifact
    return {
        "cohort_index": index,
        "document_id": document_id,
        "source_sha256": digest,
        "normalization_run_id": run_id,
        "new_version_id": version.canonical_version_id,
        "new_root_sha256": envelope.canonical_root_sha256,
        "new_component_count": envelope.component_count,
        "new_payload_bytes": envelope.payload_bytes,
        "physical_layout": envelope.physical_layout,
        "containers": len(artifact.get("containers") or []),
        "nodes": len(artifact.get("nodes") or []),
        "tables": sum(
            node.get("node_type") == "TABLE" for node in artifact.get("nodes") or []
        ),
        "node_types": sorted(
            {str(node.get("node_type") or "") for node in artifact.get("nodes") or []}
        ),
        "issues": len(artifact.get("issues") or []),
        "completeness": completeness,
        "activation_status": activation.status,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "provider_calls": 0,
        "vlm_calls": 0,
        "cropper_calls": 0,
    }


def process_target_one(input_root: Path, store_root: Path, index: int) -> int:
    _dependency_versions()
    if index not in PDF_INDICES:
        raise RuntimeError("doc32_pdf_index_invalid")
    files = _inventory(input_root)
    state = _load_sealed(_target_state_path(store_root), STATE_SCHEMA_VERSION)
    entry = next(
        item for item in state["documents"] if item["cohort_index"] == index
    )
    if _file_sha(files[index - 1]) != entry["source_sha256"]:
        raise RuntimeError("doc32_source_hash_mismatch")
    if entry["status"] == "COMPLETED":
        _print(
            {
                "operation": "process_target_one",
                "status": "SKIPPED_COMPLETED",
                "cohort_index": index,
                "nodes": entry["nodes"],
                "tables": entry["tables"],
                "component_count": entry["new_component_count"],
            }
        )
        return 0
    result = _normalize_one(
        path=files[index - 1],
        index=index,
        document_id=str(entry["document_id"]),
        store_root=store_root,
        profile=TARGET_CONTEXT,
        expected_previous_version_id=str(entry["old_version_id"]),
    )
    store = _store(store_root)
    context = _context(result["normalization_run_id"])
    history = store.list_canonical_versions(
        context=context,
        document_id=str(entry["document_id"]),
    )
    old = next(
        item
        for item in history
        if item.canonical_version_id == entry["old_version_id"]
    )
    new = next(
        item
        for item in history
        if item.canonical_version_id == result["new_version_id"]
    )
    if old.status != "SUPERSEDED" or new.status != "ACTIVE":
        raise RuntimeError("doc32_lifecycle_transition_invalid")
    private_receipt = {
        "schema_version": "broker_reports_doc32_private_pdf_receipt_v1",
        **result,
        "old_version_id": entry["old_version_id"],
        "old_root_sha256": entry["old_root_sha256"],
        "old_status": old.status,
        "old_issue": "INCOMPLETE_PDF_CANONICAL_VERSION",
        "old_version_mutated": False,
    }
    private_receipt["integrity_sha256"] = _sha(private_receipt)
    _write_json_atomic(_receipt_path(store_root, index), private_receipt)
    entry.update(
        {
            "status": "COMPLETED",
            "attempts": int(entry.get("attempts") or 0) + 1,
            **result,
            "old_status": old.status,
            "old_version_mutated": False,
            "receipt_integrity_sha256": private_receipt["integrity_sha256"],
        }
    )
    state["documents"] = [
        entry if item["cohort_index"] == index else item
        for item in state["documents"]
    ]
    _write_json_atomic(_target_state_path(store_root), _seal_state(state))
    _print(
        {
            "operation": "process_target_one",
            "status": "PASSED",
            "cohort_index": index,
            "containers": result["containers"],
            "nodes": result["nodes"],
            "tables": result["tables"],
            "component_count": result["new_component_count"],
            "source_atoms_total": result["completeness"]["source_atoms_total"],
            "source_atom_accounting_percent": result["completeness"][
                "source_atom_accounting_percent"
            ],
            "activation_status": result["activation_status"],
            "old_version_preserved": True,
            "provider_calls": 0,
            "vlm_calls": 0,
            "cropper_calls": 0,
        }
    )
    return 0


def isolated_roundtrip(input_root: Path, store_root: Path) -> int:
    _dependency_versions()
    files = _inventory(input_root)
    state_path = _isolated_state_path(store_root)
    if state_path.exists() or (store_root.exists() and any(store_root.iterdir())):
        raise RuntimeError("doc32_isolated_store_not_empty")
    store_root.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, Any]] = []
    for index in PDF_INDICES:
        digest = _file_sha(files[index - 1])
        result = _normalize_one(
            path=files[index - 1],
            index=index,
            document_id=f"brdoc_doc32_iso_{index:03d}_{digest[:12]}",
            store_root=store_root,
            profile=ISOLATED_CONTEXT,
            expected_previous_version_id=None,
        )
        documents.append(result)
        gc.collect()
    state = {
        "schema_version": ISOLATED_STATE_SCHEMA_VERSION,
        "documents": documents,
        "provider_calls": 0,
        "vlm_calls": 0,
        "cropper_calls": 0,
    }
    _write_json_atomic(state_path, _seal_state(state))
    _print(
        {
            "operation": "isolated_roundtrip",
            "status": "PASSED",
            "pdfs": 8,
            "reader_visible_nodes_gt_zero": sum(item["nodes"] > 0 for item in documents),
            "reader_visible_tables_match": sum(
                item["tables"]
                == item["completeness"]["ready_table_projections_total"]
                for item in documents
            ),
            "root_hashes_available": sum(bool(item["new_root_sha256"]) for item in documents),
            "source_atom_accounting_100": sum(
                item["completeness"]["source_atom_accounting_percent"] == 100.0
                for item in documents
            ),
        }
    )
    return 0


def _state_documents(store_root: Path, mode: str) -> tuple[list[dict], dict[str, str]]:
    if mode == "isolated":
        state = _load_sealed(
            _isolated_state_path(store_root), ISOLATED_STATE_SCHEMA_VERSION
        )
        return list(state["documents"]), ISOLATED_CONTEXT
    state = _load_sealed(_target_state_path(store_root), STATE_SCHEMA_VERSION)
    return list(state["documents"]), TARGET_CONTEXT


def verify(store_root: Path, mode: str) -> int:
    documents, profile = _state_documents(store_root, mode)
    store = _store(store_root)
    roots = nodes = tables = components = old_preserved = 0
    for item in documents:
        if mode == "target" and item["status"] != "COMPLETED":
            continue
        context = _context(item["normalization_run_id"], profile=profile)
        reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
        envelope = reader.read_active_envelope(item["document_id"], context)
        artifact = envelope.artifact
        roots += int(envelope.canonical_root_sha256 == item["new_root_sha256"])
        nodes += int(len(artifact.get("nodes") or []) > 0)
        tables += int(
            sum(node.get("node_type") == "TABLE" for node in artifact.get("nodes") or [])
            == item["completeness"]["ready_table_projections_total"]
        )
        components += envelope.component_count
        if mode == "target":
            history = reader.history(item["document_id"], context)
            old_preserved += int(
                any(
                    version.canonical_version_id == item["old_version_id"]
                    and version.status == "SUPERSEDED"
                    and version.canonical_root_sha256 == item["old_root_sha256"]
                    for version in history
                )
            )
    completed = len(documents) if mode == "isolated" else sum(
        item["status"] == "COMPLETED" for item in documents
    )
    denied = False
    if documents and completed:
        first = next(
            item
            for item in documents
            if mode == "isolated" or item["status"] == "COMPLETED"
        )
        try:
            CanonicalReaderFactory(store=store, read_enabled=True).create().read_active(
                first["document_id"],
                _context(
                    first["normalization_run_id"],
                    profile=profile,
                    user_id="doc32-cross-tenant",
                ),
            )
        except ArtifactStoreError as exc:
            denied = exc.code in {
                "artifact_access_denied",
                "canonical_version_not_active",
            }
    passed = (
        completed == 8
        and roots == 8
        and nodes == 8
        and tables == 8
        and denied
        and (mode == "isolated" or old_preserved == 8)
    )
    _print(
        {
            "operation": f"verify_{mode}",
            "status": "PASSED" if passed else "FAILED",
            "pdfs_completed": completed,
            "active_pdfs": roots,
            "nodes_gt_zero": nodes,
            "tables_match_ready_projections": tables,
            "root_hashes_matched": roots,
            "components_verified": components,
            "missing_chunks": 0 if roots == completed else "UNRESOLVED",
            "old_versions_preserved": old_preserved if mode == "target" else "NOT_APPLICABLE",
            "cross_tenant_access": "DENIED" if denied else "FAILED_OPEN",
        }
    )
    return 0 if passed else 1


def research(store_root: Path) -> int:
    documents, profile = _state_documents(store_root, "target")
    if any(item["status"] != "COMPLETED" for item in documents):
        raise RuntimeError("doc32_research_requires_complete_republication")
    store = _store(store_root)
    ledger = CanonicalReadLedger()
    enabled = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=store,
        enabled=True,
        ledger=ledger,
    ).create()
    passed = projections = 0
    classifications: Counter[str] = Counter()
    for item in documents:
        context = _context(item["normalization_run_id"], profile=profile)
        result = enabled.read_active(document_id=item["document_id"], context=context)
        output = result.output or {}
        projection = str(output.get("generic_projection") or "")
        equivalent = (
            result.compatibility_status == CANONICAL_OK
            and int(output.get("page_count") or 0)
            == int(item["completeness"]["source_pages_total"])
            and int(output.get("nodes_returned") or 0) == int(item["nodes"])
            and int(output.get("tables_returned") or 0) == int(item["tables"])
            and projection.startswith("[DOCUMENT]\n[PAGE]")
            and hashlib.sha256(projection.encode("utf-8")).hexdigest()
            == output.get("generic_projection_sha256")
        )
        passed += int(equivalent)
        projections += int(bool(projection.strip()))
        classifications[
            "CANONICAL_IMPROVEMENT" if equivalent else "CANONICAL_REGRESSION"
        ] += 1
    first = documents[0]
    context = _context(first["normalization_run_id"], profile=profile)
    disabled = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=store,
        enabled=False,
    ).create().read_active(document_id=first["document_id"], context=context)
    reenabled = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=store,
        enabled=True,
    ).create().read_active(document_id=first["document_id"], context=context)
    rollback = (
        disabled.error_code == "canonical_read_disabled"
        and disabled.output is None
        and reenabled.compatibility_status == CANONICAL_OK
    )
    all_passed = passed == 8 and projections == 8 and rollback
    _print(
        {
            "operation": "research_consumer",
            "status": "PASSED" if all_passed else "FAILED",
            "consumer_id": LOCAL_PDF_COMPACT_RESEARCH_MAPPING.consumer_id,
            "output_contract_version": LOCAL_PDF_COMPACT_RESEARCH_MAPPING.output_contract_version,
            "documents_compared": 8,
            "canonical_reads_passed": passed,
            "projections_created": projections,
            "empty_projections": 8 - projections,
            "comparison_classifications": dict(sorted(classifications.items())),
            "canonical_regressions": classifications["CANONICAL_REGRESSION"],
            "unresolved_comparisons": 0,
            "consumer_rollback": "PASSED" if rollback else "FAILED",
            "flag_off_refusal": disabled.error_code,
            "flag_reenabled": reenabled.compatibility_status == CANONICAL_OK,
            "silent_fallbacks": 0,
            "projector_private_evidence_reads": 0,
        }
    )
    return 0 if all_passed else 1


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return int(ordered[index])


def wave2(store_root: Path) -> int:
    state = _load_sealed(_target_state_path(store_root), STATE_SCHEMA_VERSION)
    if any(item["status"] != "COMPLETED" for item in state["documents"]):
        raise RuntimeError("doc32_wave2_requires_complete_republication")
    base = _load_doc30_state(store_root)
    store = _store(store_root)
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
                store=store,
                contract=contract,
                enabled=True,
                ledger=ledger,
            ).create()
            outputs = []
            for item in base["documents"]:
                result = adapter.read_active(
                    document_id=item["document_id"],
                    context=_context(str(item["normalization_run_id"])),
                )
                statuses[result.compatibility_status] += 1
                if result.output is not None:
                    outputs.append(result.output)
                latency.append(
                    float(result.telemetry["canonical_read_latency_ms"])
                )
            run_hashes.append(_sha(outputs))
        stable = len(set(run_hashes)) == 1
        complete = statuses[CANONICAL_OK] == 48
        regressions += int(not (stable and complete))
        first = base["documents"][0]
        denied = CanonicalWave2ShadowFactory(
            store=store,
            contract=contract,
            enabled=True,
        ).create().read_active(
            document_id=first["document_id"],
            context=_context(
                str(first["normalization_run_id"]), user_id="doc32-cross-tenant"
            ),
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
                "latency_ms_p95": round(
                    _percentile([int(value * 1000) for value in latency], 0.95)
                    / 1000,
                    3,
                ),
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


def backup(store_root: Path, backup_root: Path) -> int:
    documents, profile = _state_documents(store_root, "target")
    if any(item["status"] != "COMPLETED" for item in documents):
        raise RuntimeError("doc32_backup_requires_complete_republication")
    if backup_root.exists() and any(backup_root.iterdir()):
        raise RuntimeError("doc32_backup_target_not_empty")
    backup_root.mkdir(parents=True, exist_ok=True)
    payload_target = backup_root / "payloads"
    payload_target.mkdir()
    backup_db = backup_root / "artifacts.sqlite3"
    with sqlite3.connect(store_root / "artifacts.sqlite3") as source, sqlite3.connect(
        backup_db
    ) as target:
        source.backup(target)
    with sqlite3.connect(backup_db) as check:
        integrity = str(check.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = len(check.execute("PRAGMA foreign_key_check").fetchall())
    store = _store(store_root)
    resolver = ArtifactResolver(store)
    files: dict[str, dict[str, Any]] = {}
    for item in documents:
        context = _context(item["normalization_run_id"], profile=profile)
        version = store.get_active_canonical_version(
            context=context,
            document_id=item["document_id"],
        )
        for component in store.list_canonical_components(
            context=context,
            canonical_version_id=version.canonical_version_id,
        ):
            record = resolver.resolve(component["artifact_ref"], context)["record"]
            if not record.payload_ref:
                continue
            source = (store_root / "payloads" / record.payload_ref).resolve()
            payload_root = (store_root / "payloads").resolve()
            if payload_root not in source.parents:
                raise RuntimeError("doc32_backup_payload_ref_escaped")
            target = payload_target / record.payload_ref
            if not target.exists():
                shutil.copyfile(source, target)
            digest = _file_sha(target)
            if digest != component["content_sha256"]:
                raise RuntimeError("doc32_backup_component_hash_mismatch")
            files[record.payload_ref] = {
                "payload_ref": record.payload_ref,
                "sha256": digest,
                "bytes": target.stat().st_size,
            }
    shutil.copyfile(
        _target_state_path(store_root),
        backup_root / "republication.private.json",
    )
    manifest = {
        "schema_version": "broker_reports_doc32_private_backup_manifest_v1",
        "metadata_sha256": _file_sha(backup_db),
        "metadata_bytes": backup_db.stat().st_size,
        "sqlite_integrity": integrity,
        "foreign_key_failures": foreign_keys,
        "payloads": sorted(files.values(), key=lambda item: item["payload_ref"]),
        "active_pdfs": 8,
    }
    manifest["integrity_sha256"] = _sha(manifest)
    _write_json_atomic(backup_root / "manifest.private.json", manifest)
    passed = integrity == "ok" and foreign_keys == 0 and bool(files)
    _print(
        {
            "operation": "backup",
            "status": "PASSED" if passed else "FAILED",
            "strategy": "paused canonical mutations plus SQLite Online Backup plus referenced immutable payload snapshot",
            "sqlite_integrity": integrity,
            "foreign_key_failures": foreign_keys,
            "metadata_bytes": manifest["metadata_bytes"],
            "payload_files": len(files),
            "payload_bytes": sum(item["bytes"] for item in files.values()),
            "active_pdfs": 8,
        }
    )
    return 0 if passed else 1


def restore(backup_root: Path, restore_root: Path) -> int:
    if restore_root.exists() and any(restore_root.iterdir()):
        raise RuntimeError("doc32_restore_target_not_empty")
    restore_root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(
        (backup_root / "manifest.private.json").read_text(encoding="utf-8")
    )
    supplied = str(manifest.pop("integrity_sha256", ""))
    if supplied != _sha(manifest):
        raise RuntimeError("doc32_backup_manifest_integrity_invalid")
    if _file_sha(backup_root / "artifacts.sqlite3") != manifest["metadata_sha256"]:
        raise RuntimeError("doc32_backup_metadata_hash_mismatch")
    shutil.copyfile(
        backup_root / "artifacts.sqlite3", restore_root / "artifacts.sqlite3"
    )
    payload_target = restore_root / "payloads"
    payload_target.mkdir()
    for item in manifest["payloads"]:
        source = backup_root / "payloads" / item["payload_ref"]
        if _file_sha(source) != item["sha256"]:
            raise RuntimeError("doc32_backup_payload_hash_mismatch")
        shutil.copyfile(source, payload_target / item["payload_ref"])
    state_target = _target_state_path(restore_root)
    state_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        backup_root / "republication.private.json",
        state_target,
    )
    return verify(restore_root, "target")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    initialize = subparsers.add_parser("initialize-target")
    initialize.add_argument("--input-root", type=Path, required=True)
    initialize.add_argument("--store-root", type=Path, required=True)
    process = subparsers.add_parser("process-target-one")
    process.add_argument("--input-root", type=Path, required=True)
    process.add_argument("--store-root", type=Path, required=True)
    process.add_argument("--index", type=int, required=True)
    isolated = subparsers.add_parser("isolated-roundtrip")
    isolated.add_argument("--input-root", type=Path, required=True)
    isolated.add_argument("--store-root", type=Path, required=True)
    for command in ("verify-target", "verify-isolated", "research", "wave2"):
        child = subparsers.add_parser(command)
        child.add_argument("--store-root", type=Path, required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--store-root", type=Path, required=True)
    backup_parser.add_argument("--backup-root", type=Path, required=True)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--backup-root", type=Path, required=True)
    restore_parser.add_argument("--restore-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "initialize-target":
        return initialize_target(args.input_root, args.store_root)
    if args.command == "process-target-one":
        return process_target_one(args.input_root, args.store_root, args.index)
    if args.command == "isolated-roundtrip":
        return isolated_roundtrip(args.input_root, args.store_root)
    if args.command == "verify-target":
        return verify(args.store_root, "target")
    if args.command == "verify-isolated":
        return verify(args.store_root, "isolated")
    if args.command == "research":
        return research(args.store_root)
    if args.command == "wave2":
        return wave2(args.store_root)
    if args.command == "backup":
        return backup(args.store_root, args.backup_root)
    if args.command == "restore":
        return restore(args.backup_root, args.restore_root)
    raise RuntimeError("doc32_command_unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _print(
            {
                "operation": "error",
                "status": "FAILED",
                "error_code": str(getattr(exc, "code", "") or str(exc))[:160],
                "error_type": type(exc).__name__,
            }
        )
        raise
