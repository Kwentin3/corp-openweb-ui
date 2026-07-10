#!/usr/bin/env python3
"""Internal one-document worker for the Slice 2 aggregate proof.

Only safe counters/statuses are emitted. The worker process boundary releases
all pdfminer/pdfplumber caches and private inventories after each document.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate1Normalizer,
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
from local_case_group_pdf_text_layer_slice1_proof import (  # noqa: E402
    _file_input,
    _repo_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-index", required=True, type=int)
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
    if args.pdf_index < 0 or args.pdf_index >= len(pdf_sources):
        raise RuntimeError("controlled_pdf_layout_worker_index_invalid")
    source = pdf_sources[args.pdf_index]
    started = time.perf_counter()
    result = Gate1Normalizer().normalize(
        [_file_input(source, args.pdf_index + 1)],
        entrypoint="controlled_private_pdf_layout_slice2_worker",
        trigger_type="controlled_private_reintake",
        input_context={
            "customer_docs_loaded_to_knowledge": False,
            "vectorization_performed": False,
            "ordinary_upload_used": False,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
            "clarification_criticality_refinement_enabled": True,
            "pdf_layout_slice2_enabled": True,
        },
    )
    runtime_seconds = time.perf_counter() - started
    package = result.package
    payload = next(
        item
        for item in package.get("private_normalized_source_payloads") or []
        if item.get("container_format") == "pdf"
    )
    units = [
        item
        for item in package.get("private_normalized_source_units") or []
        if item.get("pdf_unit_type")
    ]
    document = package["document_inventory"]["documents"][0]
    projection = payload.get("pdf_text_layer_projection") or {}
    pages = projection.get("page_inventory") or []
    candidates = projection.get("table_candidate_inventory") or []
    payload_validation = validate_pdf_text_layer_payload(payload)
    unit_validations = [
        validate_full_source_unit(
            unit=unit,
            normalization_run_id=package["normalization_run"]["run_id"],
            document_id=str(unit.get("document_id") or ""),
            source_checksum_sha256=str(document.get("sha256") or ""),
        )
        for unit in units
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(
            user_id="controlled-pdf-layout-worker-user",
            normalization_run_id=package["normalization_run"]["run_id"],
            case_id="controlled-pdf-layout-worker-case",
            chat_id="controlled-pdf-layout-worker-chat",
            workspace_model_id="controlled-pdf-layout-worker-model",
            allow_private=True,
            require_source_available=True,
        )
        persist_gate1_result(
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
        records = store.list_by_run(package["normalization_run"]["run_id"])
        type_counts = Counter(record.artifact_type for record in records)
        storage_counts = Counter(record.storage_backend for record in records)

    memory = _process_memory()
    output = {
        "status": (
            "passed"
            if payload_validation.get("validator_status") == "passed"
            and all(
                item.get("validator_status") == "passed" for item in unit_validations
            )
            else "partial"
        ),
        "worker_index": args.pdf_index,
        "gate1_validation_status": package.get("validation_result", {}).get("status"),
        "page_text_status": payload.get("parser_completeness_status"),
        "page_text_reason_codes": sorted(
            str(item) for item in payload.get("parser_completeness_reason_codes") or []
        ),
        "layout_status": payload.get("layout_projection_status"),
        "layout_reason_codes": sorted(
            str(item) for item in projection.get("layout_reason_codes") or []
        ),
        "table_reason_codes": sorted(
            {
                str(reason)
                for page in pages
                for reason in page.get("table_reason_codes") or []
            }
        ),
        "pages_total": len(pages),
        "layout_complete_pages": sum(
            1 for page in pages if page.get("layout_projection_status") == "complete"
        ),
        "layout_partial_pages": sum(
            1 for page in pages if page.get("layout_projection_status") != "complete"
        ),
        "word_refs_count": len(projection.get("word_inventory") or []),
        "line_refs_count": len(projection.get("line_inventory") or []),
        "table_candidate_count": len(candidates),
        "table_candidate_confidence_buckets": dict(
            sorted(
                Counter(
                    str(item.get("confidence_bucket") or "unknown")
                    for item in candidates
                ).items()
            )
        ),
        "unit_type_counts": dict(
            sorted(
                Counter(str(unit.get("pdf_unit_type") or "unknown") for unit in units).items()
            )
        ),
        "layout_source_value_refs_count": sum(
            len(unit.get("pdf_layout_source_value_refs") or []) for unit in units
        ),
        "source_value_refs_count": sum(
            len(unit.get("source_value_refs") or []) for unit in units
        ),
        "layout_coverage_complete": (
            (projection.get("layout_coverage") or {}).get(
                "all_selected_refs_accounted"
            )
            is True
            if payload.get("layout_projection_status") == "complete"
            else False
        ),
        "payload_validation_status": payload_validation.get("validator_status"),
        "unit_validations_passed": sum(
            1
            for item in unit_validations
            if item.get("validator_status") == "passed"
        ),
        "units_total": len(units),
        "artifactstore_payload_records": type_counts.get(
            "private_normalized_source_payload_v0", 0
        ),
        "artifactstore_unit_records": type_counts.get(
            "private_normalized_source_unit_v0", 0
        ),
        "artifactstore_knowledge_records": storage_counts.get(
            "openwebui_knowledge", 0
        ),
        "runtime_seconds": round(runtime_seconds, 3),
        "runtime_milliseconds_per_page": round(
            runtime_seconds * 1000.0 / max(len(pages), 1), 3
        ),
        "layout_parser_page_milliseconds_max": round(
            max(
                [float(page.get("layout_elapsed_milliseconds") or 0.0) for page in pages]
                or [0.0]
            ),
            3,
        ),
        "payload_bytes": len(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ),
        "source_value_index_entries": len(payload.get("source_value_index") or []),
        "peak_working_set_bytes": memory.get("peak_working_set_bytes"),
        "private_usage_bytes": memory.get("private_usage_bytes"),
        "raw_text_emitted": False,
        "filenames_ids_or_paths_emitted": False,
        "ordinary_upload_used": False,
        "knowledge_rag_used": False,
        "vectorization_performed": False,
        "ocr_vlm_used": False,
        "page_rendering_used_for_extraction": False,
        "model_calls": False,
        "source_facts_created": False,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def _process_memory() -> dict[str, int | None]:
    if sys.platform != "win32":
        return {"peak_working_set_bytes": None, "private_usage_bytes": None}
    counters = _ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    process = ctypes.windll.kernel32.GetCurrentProcess()
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCountersEx),
        wintypes.DWORD,
    ]
    get_memory.restype = wintypes.BOOL
    succeeded = get_memory(
        process, ctypes.byref(counters), counters.cb
    )
    if not succeeded:
        return {"peak_working_set_bytes": None, "private_usage_bytes": None}
    return {
        "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
        "private_usage_bytes": int(counters.PrivateUsage),
    }


if __name__ == "__main__":
    raise SystemExit(main())
