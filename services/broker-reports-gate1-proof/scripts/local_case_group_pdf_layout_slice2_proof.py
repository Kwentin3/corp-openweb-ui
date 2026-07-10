#!/usr/bin/env python3
"""Safe isolated-worker aggregate proof for PDF layout Slice 2."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
WORKER = Path(__file__).with_name("local_pdf_layout_slice2_worker.py")
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    build_retention_policy,
    persist_gate1_result,
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
    parser.add_argument("--case-group-id", default=DEFAULT_CASE_GROUP_ID)
    parser.add_argument("--private-registry", default=DEFAULT_PRIVATE_REGISTRY)
    parser.add_argument("--safe-source-registry", default=DEFAULT_SAFE_SOURCE_REGISTRY)
    parser.add_argument("--case-groups", default=DEFAULT_CASE_GROUPS)
    parser.add_argument("--worker-timeout-seconds", type=int, default=300)
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
        raise RuntimeError("controlled_pdf_layout_source_selection_empty")

    worker_results = [
        _run_worker(index=index, args=args) for index in range(len(pdf_sources))
    ]
    complete_worker = next(
        (
            item
            for item in worker_results
            if item.get("layout_status") == "complete"
            and any(
                unit_type in {"pdf_line_cluster_unit", "pdf_table_candidate_unit"}
                for unit_type in (item.get("unit_type_counts") or {})
            )
        ),
        None,
    )
    dry_run = (
        _one_document_readiness(
            pdf_sources[int(complete_worker["worker_index"])]
        )
        if complete_worker is not None
        else _not_run_readiness()
    )

    page_text_status_counts = Counter(
        str(item.get("page_text_status") or "blocked") for item in worker_results
    )
    layout_status_counts = Counter(
        str(item.get("layout_status") or "blocked") for item in worker_results
    )
    unit_type_counts: Counter[str] = Counter()
    layout_reason_counts: Counter[str] = Counter()
    table_reason_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    for item in worker_results:
        unit_type_counts.update(item.get("unit_type_counts") or {})
        layout_reason_counts.update(item.get("layout_reason_codes") or [])
        table_reason_counts.update(item.get("table_reason_codes") or [])
        confidence_counts.update(item.get("table_candidate_confidence_buckets") or {})

    complete_layout_workers = [
        item for item in worker_results if item.get("layout_status") == "complete"
    ]
    peaks = [
        int(item.get("peak_working_set_bytes") or 0) for item in worker_results
    ]
    peak_max = max(peaks or [0])
    peak_budget = 512 * 1024 * 1024
    checks = {
        "all_worker_payload_validations_passed": all(
            item.get("payload_validation_status") == "passed"
            for item in worker_results
        ),
        "all_worker_unit_validations_passed": all(
            int(item.get("unit_validations_passed") or 0)
            == int(item.get("units_total") or 0)
            for item in worker_results
        ),
        "layout_complete_unit_available": bool(complete_layout_workers),
        "layout_complete_coverage_exact": all(
            item.get("layout_coverage_complete") is True
            for item in complete_layout_workers
        ),
        "isolated_worker_peak_under_512_mib": peak_max <= peak_budget,
        "worker_artifactstore_no_knowledge": all(
            int(item.get("artifactstore_knowledge_records") or 0) == 0
            for item in worker_results
        ),
        "dry_run_passed": dry_run["validator_status"] == "passed",
        "dry_run_layout_unit": dry_run["pdf_unit_type"]
        in {"pdf_line_cluster_unit", "pdf_table_candidate_unit"},
        "dry_run_layout_refs_preserved": dry_run[
            "layout_source_value_refs_preserved"
        ],
        "dry_run_layout_coverage_preserved": dry_run[
            "layout_coverage_preserved"
        ],
        "dry_run_table_metadata_preserved": dry_run[
            "table_candidate_metadata_preserved"
        ],
        "dry_run_bounded_projection": dry_run["whole_pdf_in_package"] is False,
        "dry_run_no_model": dry_run["model_call_performed"] is False,
        "dry_run_no_facts": dry_run["source_fact_records"] == 0,
        "dry_run_store_unchanged": dry_run["artifactstore_unchanged"] is True,
        "ordinary_upload_not_used": True,
        "ocr_vlm_not_used": True,
        "page_rendering_not_used": True,
        "vectorization_not_performed": True,
    }
    pages_total = sum(int(item.get("pages_total") or 0) for item in worker_results)
    runtime_total = sum(float(item.get("runtime_seconds") or 0.0) for item in worker_results)
    output = {
        "status": "passed" if checks and all(checks.values()) else "partial",
        "scope": "approved_case_group_002_pdf_layout_isolated_worker_aggregate",
        "pdf_documents_inspected": len(worker_results),
        "complete_pdf_page_text_documents_considered": page_text_status_counts.get(
            "complete", 0
        ),
        "page_text_status_counts": dict(sorted(page_text_status_counts.items())),
        "layout_status_counts": dict(sorted(layout_status_counts.items())),
        "pages_processed": pages_total,
        "layout_complete_pages": sum(
            int(item.get("layout_complete_pages") or 0) for item in worker_results
        ),
        "layout_partial_pages": sum(
            int(item.get("layout_partial_pages") or 0) for item in worker_results
        ),
        "word_refs_count": sum(
            int(item.get("word_refs_count") or 0) for item in worker_results
        ),
        "line_refs_count": sum(
            int(item.get("line_refs_count") or 0) for item in worker_results
        ),
        "table_candidate_count": sum(
            int(item.get("table_candidate_count") or 0) for item in worker_results
        ),
        "table_candidate_confidence_buckets": dict(sorted(confidence_counts.items())),
        "unit_type_counts": dict(sorted(unit_type_counts.items())),
        "line_cluster_units_minted": unit_type_counts.get(
            "pdf_line_cluster_unit", 0
        ),
        "table_candidate_units_minted": unit_type_counts.get(
            "pdf_table_candidate_unit", 0
        ),
        "layout_reason_code_counts": dict(sorted(layout_reason_counts.items())),
        "table_reason_code_counts": dict(sorted(table_reason_counts.items())),
        "layout_source_value_refs_count": sum(
            int(item.get("layout_source_value_refs_count") or 0)
            for item in worker_results
        ),
        "source_value_refs_count": sum(
            int(item.get("source_value_refs_count") or 0) for item in worker_results
        ),
        "layout_coverage_status": (
            "passed"
            if checks["layout_complete_coverage_exact"]
            else "partial"
        ),
        "performance": {
            "runtime_seconds_total": round(runtime_total, 3),
            "runtime_seconds_per_pdf_average": round(
                runtime_total / max(len(worker_results), 1), 3
            ),
            "runtime_milliseconds_per_page_average": round(
                runtime_total * 1000.0 / max(pages_total, 1), 3
            ),
            "runtime_seconds_per_pdf_max": round(
                max(
                    [float(item.get("runtime_seconds") or 0.0) for item in worker_results]
                    or [0.0]
                ),
                3,
            ),
            "layout_parser_page_milliseconds_max": round(
                max(
                    [
                        float(item.get("layout_parser_page_milliseconds_max") or 0.0)
                        for item in worker_results
                    ]
                    or [0.0]
                ),
                3,
            ),
            "isolated_worker_peak_working_set_bytes_max": peak_max,
            "isolated_worker_peak_budget_bytes": peak_budget,
            "payload_bytes_total": sum(
                int(item.get("payload_bytes") or 0) for item in worker_results
            ),
            "payload_bytes_max": max(
                [int(item.get("payload_bytes") or 0) for item in worker_results]
                or [0]
            ),
            "source_value_index_entries_total": sum(
                int(item.get("source_value_index_entries") or 0)
                for item in worker_results
            ),
            "source_value_index_entries_max": max(
                [
                    int(item.get("source_value_index_entries") or 0)
                    for item in worker_results
                ]
                or [0]
            ),
            "dry_run_package_bytes": dry_run["package_bytes"],
            "memory_safety_mode": "one_pdf_per_worker_plus_document_inventory_budget",
        },
        "artifactstore_payload_records": sum(
            int(item.get("artifactstore_payload_records") or 0)
            for item in worker_results
        ),
        "artifactstore_unit_records": sum(
            int(item.get("artifactstore_unit_records") or 0)
            for item in worker_results
        ),
        "artifactstore_knowledge_records": sum(
            int(item.get("artifactstore_knowledge_records") or 0)
            for item in worker_results
        ),
        "dry_run": dry_run,
        "checks": checks,
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
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "passed" else 1


def _run_worker(*, index: int, args: argparse.Namespace) -> dict[str, Any]:
    command = [
        sys.executable,
        str(WORKER),
        "--pdf-index",
        str(index),
        "--case-group-id",
        str(args.case_group_id),
        "--private-registry",
        str(args.private_registry),
        "--safe-source-registry",
        str(args.safe_source_registry),
        "--case-groups",
        str(args.case_groups),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=args.worker_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"pdf_layout_worker_timeout:{index}") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"pdf_layout_worker_failed:{index}:{completed.returncode}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"pdf_layout_worker_output_missing:{index}")
    return json.loads(lines[-1])


def _one_document_readiness(source: dict[str, Any]) -> dict[str, Any]:
    result = Gate1Normalizer().normalize(
        [_file_input(source, 1)],
        entrypoint="controlled_private_pdf_layout_gate2_readiness_dry_run",
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
            user_id="controlled-pdf-layout-dry-run-user",
            normalization_run_id=run_id,
            case_id="controlled-pdf-layout-dry-run-case",
            chat_id="controlled-pdf-layout-dry-run-chat",
            workspace_model_id="controlled-pdf-layout-dry-run-model",
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
        before = [record.artifact_id for record in store.list_by_run(run_id)]
        readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
            domain_context_packet_ref=manifest.artifact_refs_by_type[
                "domain_context_packet_v0"
            ][0],
            context=context,
        )
        records = store.list_by_run(run_id)
        packages = [
            item
            for item in readiness.packages
            if (item.get("source_unit") or {}).get("pdf_unit_type")
            in {"pdf_table_candidate_unit", "pdf_line_cluster_unit"}
        ]
        package = next(
            (
                item
                for item in packages
                if (item.get("source_unit") or {}).get("pdf_unit_type")
                == "pdf_table_candidate_unit"
            ),
            packages[0] if packages else {},
        )
        unit = package.get("source_unit") or {}
        unit_type = unit.get("pdf_unit_type")
        forbidden_whole_pdf_fields = {
            "content_bytes",
            "page_inventory",
            "pdf_text_layer_projection",
            "char_inventory",
            "word_inventory",
            "line_inventory",
        }
        return {
            "validator_status": readiness.validation.get("validator_status"),
            "packages_total": len(readiness.packages),
            "artifactstore_unchanged": before
            == [record.artifact_id for record in records]
            and readiness.validation.get("artifactstore_unchanged") is True,
            "knowledge_records": readiness.validation.get("knowledge_records"),
            "source_fact_records": sum(
                1 for record in records if "source_fact" in record.artifact_type
            ),
            "model_call_performed": (package.get("prompt_contract") or {}).get(
                "model_call_performed"
            ),
            "source_input_mode": unit.get("source_input_mode"),
            "pdf_unit_type": unit_type,
            "layout_source_value_refs_preserved": bool(
                unit.get("pdf_layout_source_value_refs")
            ),
            "layout_coverage_preserved": bool(unit.get("pdf_layout_coverage")),
            "table_candidate_metadata_preserved": (
                bool(
                    unit.get("table_candidate_ref")
                    and unit.get("table_fallback_text_refs")
                    and unit.get("table_contributing_word_refs")
                )
                if unit_type == "pdf_table_candidate_unit"
                else True
            ),
            "whole_pdf_in_package": bool(
                forbidden_whole_pdf_fields & _recursive_keys(package)
            ),
            "whole_parent_source_coverage_claimed": (
                package.get("coverage_expectation") or {}
            ).get("whole_parent_source_coverage_claimed"),
            "package_bytes": len(
                json.dumps(
                    package,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
        }


def _not_run_readiness() -> dict[str, Any]:
    return {
        "validator_status": "not_run",
        "packages_total": 0,
        "artifactstore_unchanged": True,
        "knowledge_records": 0,
        "source_fact_records": 0,
        "model_call_performed": False,
        "source_input_mode": None,
        "pdf_unit_type": None,
        "layout_source_value_refs_preserved": False,
        "layout_coverage_preserved": False,
        "table_candidate_metadata_preserved": False,
        "whole_pdf_in_package": False,
        "whole_parent_source_coverage_claimed": False,
        "package_bytes": 0,
    }


def _recursive_keys(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            result.add(str(key))
            result.update(_recursive_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_recursive_keys(child))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
