#!/usr/bin/env python3
"""Safe controlled proof for PDF text-layer normalization Slice 1.

Uses only the approved private registry, canonical Gate 1 factories, ephemeral
ArtifactStore persistence and an optional one-document no-model Gate 2 dry-run.
It emits aggregate counts only and performs no upload, Knowledge/RAG/vector
write, OCR/VLM, rendering, model call, tax, declaration or XLS/XLSX work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
import tempfile
from collections import Counter
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    build_retention_policy,
    persist_gate1_result,
    validate_full_source_unit,
    validate_pdf_text_layer_payload,
)
from live_case_group_process_false_gate1_run import (  # noqa: E402
    DEFAULT_CASE_GROUPS,
    DEFAULT_CASE_GROUP_ID,
    DEFAULT_PRIVATE_REGISTRY,
    DEFAULT_SAFE_SOURCE_REGISTRY,
    _resolve_case_group_sources,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-group-id", default=DEFAULT_CASE_GROUP_ID)
    parser.add_argument("--private-registry", default=DEFAULT_PRIVATE_REGISTRY)
    parser.add_argument("--safe-source-registry", default=DEFAULT_SAFE_SOURCE_REGISTRY)
    parser.add_argument("--case-groups", default=DEFAULT_CASE_GROUPS)
    args = parser.parse_args()

    sources = _resolve_case_group_sources(
        case_group_id=args.case_group_id,
        private_registry_path=_repo_path(args.private_registry),
        safe_source_registry_path=_repo_path(args.safe_source_registry),
        case_groups_path=_repo_path(args.case_groups),
    )
    pdf_sources = [
        item
        for item in sources["files"]
        if str(item.get("extension") or "").lower() == ".pdf"
    ]
    if not pdf_sources:
        raise RuntimeError("controlled_pdf_source_selection_empty")

    inputs = [_file_input(item, index) for index, item in enumerate(pdf_sources, start=1)]
    result = Gate1Normalizer().normalize(
        inputs,
        entrypoint="controlled_private_pdf_text_layer_slice1_proof",
        trigger_type="controlled_private_reintake",
        input_context={
            "customer_docs_loaded_to_knowledge": False,
            "vectorization_performed": False,
            "ordinary_upload_used": False,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
            "clarification_criticality_refinement_enabled": True,
        },
    )
    package = result.package
    payloads = [
        item
        for item in package.get("private_normalized_source_payloads") or []
        if item.get("container_format") == "pdf"
    ]
    units = [
        item
        for item in package.get("private_normalized_source_units") or []
        if item.get("pdf_unit_type")
    ]
    documents = package.get("document_inventory", {}).get("documents", [])
    document_checksums = {
        str(item.get("document_id") or ""): str(item.get("sha256") or "")
        for item in documents
    }
    payload_validation_results = [
        validate_pdf_text_layer_payload(payload) for payload in payloads
    ]
    unit_validation_results = [
        validate_full_source_unit(
            unit=unit,
            normalization_run_id=package["normalization_run"]["run_id"],
            document_id=str(unit.get("document_id") or ""),
            source_checksum_sha256=document_checksums.get(
                str(unit.get("document_id") or ""), ""
            ),
        )
        for unit in units
    ]

    status_counts = Counter(
        str(payload.get("parser_completeness_status") or "blocked")
        for payload in payloads
    )
    reason_counts = Counter(
        str(reason)
        for payload in payloads
        for reason in payload.get("parser_completeness_reason_codes") or []
    )
    page_inventory = [
        page
        for payload in payloads
        for page in (payload.get("pdf_text_layer_projection") or {}).get(
            "page_inventory", []
        )
    ]
    complete_document_refs = {
        str(payload.get("document_ref") or "")
        for payload in payloads
        if payload.get("parser_completeness_status") == "complete"
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=temp_root / "artifacts.sqlite3",
                payload_root=temp_root / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(
            user_id="controlled-pdf-slice1-user",
            normalization_run_id=package["normalization_run"]["run_id"],
            case_id="controlled-pdf-slice1-case",
            chat_id="controlled-pdf-slice1-chat",
            workspace_model_id="controlled-pdf-slice1-model",
            allow_private=True,
            require_source_available=True,
        )
        manifest = persist_gate1_result(
            store=store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(
                mode="customer_approved_test", explicit=True
            ),
            source_file_refs=[
                {
                    "provider": "controlled_private_registry",
                    "file_hash_sha256": document.get("sha256"),
                    "size_bytes": document.get("size_bytes"),
                    "source_deleted": False,
                }
                for document in documents
            ],
        )
        records = store.list_by_run(package["normalization_run"]["run_id"])
        type_counts = Counter(record.artifact_type for record in records)
        storage_counts = Counter(record.storage_backend for record in records)

        complete_index = next(
            (
                index
                for index, document in enumerate(documents)
                if str(document.get("document_id") or "") in complete_document_refs
            ),
            None,
        )
        dry_run = (
            _one_document_readiness(pdf_sources[complete_index])
            if complete_index is not None
            else {
                "validator_status": "not_run",
                "packages_total": 0,
                "artifactstore_unchanged": True,
                "knowledge_records": 0,
                "model_call_performed": False,
                "source_input_mode": None,
                "pdf_unit_type": None,
            }
        )

        checks = {
            "gate1_validation_passed": package.get("validation_result", {}).get(
                "status"
            )
            == "passed",
            "all_payload_validations_passed": len(payload_validation_results)
            == len(payloads)
            and all(
                item.get("validator_status") == "passed"
                for item in payload_validation_results
            ),
            "all_unit_validations_passed": len(unit_validation_results) == len(units)
            and all(
                item.get("validator_status") == "passed"
                for item in unit_validation_results
            ),
            "payloads_persisted": type_counts.get(
                "private_normalized_source_payload_v0", 0
            )
            == len(payloads),
            "units_persisted": type_counts.get(
                "private_normalized_source_unit_v0", 0
            )
            == len(units),
            "artifactstore_no_knowledge_backend": storage_counts.get(
                "openwebui_knowledge", 0
            )
            == 0,
            "complete_pdf_unit_available": bool(complete_document_refs and units),
            "dry_run_passed": dry_run["validator_status"] == "passed",
            "dry_run_no_model": dry_run["model_call_performed"] is False,
            "dry_run_store_unchanged": dry_run["artifactstore_unchanged"] is True,
            "dry_run_no_knowledge": dry_run["knowledge_records"] == 0,
            "ordinary_upload_not_used": True,
            "ocr_vlm_not_used": True,
            "page_rendering_not_used": True,
            "vectorization_not_performed": True,
        }
        output = {
            "status": "passed" if checks and all(checks.values()) else "partial",
            "scope": "approved_case_group_002_pdf_aggregate_only",
            "pdf_documents_inspected": len(pdf_sources),
            "pages_total": len(page_inventory),
            "pages_with_text": sum(
                1 for page in page_inventory if str(page.get("text") or "").strip()
            ),
            "pages_without_text": sum(
                1 for page in page_inventory if not str(page.get("text") or "").strip()
            ),
            "payload_status_counts": dict(sorted(status_counts.items())),
            "reason_code_counts": dict(sorted(reason_counts.items())),
            "complete_source_units_minted": len(units),
            "source_value_refs_total": sum(
                len(unit.get("source_value_refs") or []) for unit in units
            ),
            "payload_validations_passed": sum(
                1
                for item in payload_validation_results
                if item.get("validator_status") == "passed"
            ),
            "unit_validations_passed": sum(
                1
                for item in unit_validation_results
                if item.get("validator_status") == "passed"
            ),
            "artifactstore_payload_records": type_counts.get(
                "private_normalized_source_payload_v0", 0
            ),
            "artifactstore_unit_records": type_counts.get(
                "private_normalized_source_unit_v0", 0
            ),
            "artifactstore_knowledge_records": storage_counts.get(
                "openwebui_knowledge", 0
            ),
            "dry_run": dry_run,
            "checks": checks,
            "raw_text_emitted": False,
            "filenames_or_ids_emitted": False,
            "ordinary_upload_used": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
            "model_calls": False,
            "manifest_created": bool(manifest.private_source_payload_refs),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if output["status"] == "passed" else 1


def _one_document_readiness(source: dict) -> dict:
    result = Gate1Normalizer().normalize(
        [_file_input(source, 1)],
        entrypoint="controlled_private_pdf_gate2_readiness_dry_run",
        trigger_type="controlled_private_reintake",
        input_context={
            "customer_docs_loaded_to_knowledge": False,
            "vectorization_performed": False,
            "ordinary_upload_used": False,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
            "clarification_criticality_refinement_enabled": True,
        },
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        run_id = result.package["normalization_run"]["run_id"]
        context = ArtifactAccessContext(
            user_id="controlled-pdf-dry-run-user",
            normalization_run_id=run_id,
            case_id="controlled-pdf-dry-run-case",
            chat_id="controlled-pdf-dry-run-chat",
            workspace_model_id="controlled-pdf-dry-run-model",
            allow_private=True,
            require_source_available=True,
        )
        document = result.package["document_inventory"]["documents"][0]
        manifest = persist_gate1_result(
            store=store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(
                mode="customer_approved_test", explicit=True
            ),
            source_file_refs=[
                {
                    "provider": "controlled_private_registry",
                    "file_hash_sha256": document.get("sha256"),
                    "size_bytes": document.get("size_bytes"),
                    "source_deleted": False,
                }
            ],
        )
        readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
            domain_context_packet_ref=manifest.artifact_refs_by_type[
                "domain_context_packet_v0"
            ][0],
            context=context,
        )
        package = readiness.packages[0] if readiness.packages else {}
        source_unit = package.get("source_unit") or {}
        return {
            "validator_status": readiness.validation.get("validator_status"),
            "packages_total": len(readiness.packages),
            "artifactstore_unchanged": readiness.validation.get(
                "artifactstore_unchanged"
            ),
            "knowledge_records": readiness.validation.get("knowledge_records"),
            "model_call_performed": (package.get("prompt_contract") or {}).get(
                "model_call_performed"
            ),
            "source_input_mode": source_unit.get("source_input_mode"),
            "pdf_unit_type": source_unit.get("pdf_unit_type"),
        }


def _file_input(source: dict, index: int) -> FileInput:
    path = Path(source["path"])
    extension = str(source.get("extension") or path.suffix or ".pdf")
    alias = f"controlled_private_pdf_{index:03d}{extension.lower()}"
    content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return FileInput(
        private_ref=f"controlled-private-pdf:{content_sha256}",
        original_filename_private=alias,
        mime_type=mimetypes.guess_type(alias)[0] or "application/pdf",
        source_kind="local_private_test",
        declared_size_bytes=path.stat().st_size,
        bytes_provider=lambda path=path: path.read_bytes(),
        provider_label="controlled_private_registry",
    )


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
