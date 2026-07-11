#!/usr/bin/env python3
"""Safe aggregate table-projection preflight for approved case_group_002 sources."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).with_name("local_table_projection_worker.py")
sys.path.insert(0, str(SERVICE_ROOT))

from live_case_group_process_false_gate1_run import (  # noqa: E402
    DEFAULT_CASE_GROUPS,
    DEFAULT_CASE_GROUP_ID,
    DEFAULT_PRIVATE_REGISTRY,
    DEFAULT_SAFE_SOURCE_REGISTRY,
    _resolve_case_group_sources,
)
from local_case_group_pdf_text_layer_slice1_proof import _repo_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-group-id", default=DEFAULT_CASE_GROUP_ID)
    parser.add_argument("--private-registry", default=DEFAULT_PRIVATE_REGISTRY)
    parser.add_argument("--safe-source-registry", default=DEFAULT_SAFE_SOURCE_REGISTRY)
    parser.add_argument("--case-groups", default=DEFAULT_CASE_GROUPS)
    parser.add_argument("--worker-timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    sources = _resolve_case_group_sources(
        case_group_id=args.case_group_id,
        private_registry_path=_repo_path(args.private_registry),
        safe_source_registry_path=_repo_path(args.safe_source_registry),
        case_groups_path=_repo_path(args.case_groups),
    )
    results = [_run_worker(index, args) for index in range(len(sources["files"]))]
    quality = Counter()
    for item in results:
        quality.update(item.get("quality_counts") or {})
    output = {
        "status": "passed"
        if all(item.get("normalization_validation_status") == "passed" for item in results)
        and sum(int(item.get("unaccounted_refs_total") or 0) for item in results) == 0
        and sum(int(item.get("duplicate_refs_total") or 0) for item in results) == 0
        and sum(int(item.get("artifactstore_knowledge_records") or 0) for item in results) == 0
        else "partial",
        "scope": "approved_case_group_002_table_projection_preflight",
        "documents_inspected": len(results),
        "documents_with_table_projections": sum(
            1 for item in results if int(item.get("table_projections_created") or 0) > 0
        ),
        "documents_partial_or_blocked": sum(
            1
            for item in results
            if (item.get("quality_counts") or {}).get("blocked")
            or item.get("normalization_validation_status") != "passed"
            or int(item.get("gate2_no_model_packages_blocked_total") or 0) > 0
        ),
        "formats": dict(sorted(Counter(str(item.get("source_format") or "unknown") for item in results).items())),
        "pdf_table_candidates_found": _sum(results, "pdf_table_candidates_found"),
        "table_projections_created": _sum(results, "table_projections_created"),
        "native_table_projections_created": _sum(results, "native_table_projections_created"),
        "pdf_table_projections_created": _sum(results, "pdf_table_projections_created"),
        "quality_counts": dict(sorted(quality.items())),
        "rows_total": _sum(results, "rows_total"),
        "cells_total": _sum(results, "cells_total"),
        "source_value_refs_total": _sum(results, "source_value_refs_total"),
        "fallback_refs_total": _sum(results, "fallback_refs_total"),
        "unaccounted_refs_total": _sum(results, "unaccounted_refs_total"),
        "duplicate_refs_total": _sum(results, "duplicate_refs_total"),
        "gate2_no_model_packages_total": _sum(results, "gate2_no_model_packages_total"),
        "gate2_no_model_packages_blocked_total": _sum(
            results, "gate2_no_model_packages_blocked_total"
        ),
        "model_calls_total": 0,
        "source_facts_persisted_total": 0,
        "projection_artifact_records_total": _sum(results, "projection_artifact_records_total"),
        "artifactstore_knowledge_records": _sum(results, "artifactstore_knowledge_records"),
        "performance": {
            "runtime_seconds_total": round(sum(float(item.get("runtime_seconds") or 0.0) for item in results), 3),
            "runtime_seconds_max": round(max([float(item.get("runtime_seconds") or 0.0) for item in results] or [0.0]), 3),
            "table_projection_runtime_seconds_total": round(
                sum(
                    float(item.get("table_projection_runtime_seconds") or 0.0)
                    for item in results
                ),
                3,
            ),
            "table_projection_runtime_seconds_max": round(
                max(
                    [
                        float(
                            item.get("table_projection_runtime_seconds_max")
                            or 0.0
                        )
                        for item in results
                    ]
                    or [0.0]
                ),
                3,
            ),
            "payload_size_bytes_total": _sum(results, "payload_size_bytes_total"),
            "payload_size_bytes_max": max([int(item.get("payload_size_bytes_max") or 0) for item in results] or [0]),
        },
        "guards": {
            "ordinary_upload_used": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
            "model_call_performed": False,
            "source_facts_persisted": False,
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "passed" else 1


def _run_worker(index: int, args: argparse.Namespace) -> dict:
    command = [
        sys.executable,
        str(WORKER),
        "--source-index",
        str(index),
        "--case-group-id",
        args.case_group_id,
        "--private-registry",
        args.private_registry,
        "--safe-source-registry",
        args.safe_source_registry,
        "--case-groups",
        args.case_groups,
    ]
    completed = subprocess.run(
        command,
        cwd=SERVICE_ROOT.parents[1],
        check=True,
        capture_output=True,
        timeout=args.worker_timeout_seconds,
    )
    return json.loads(completed.stdout.decode("utf-8"))


def _sum(results: list[dict], field: str) -> int:
    return sum(int(item.get(field) or 0) for item in results)


if __name__ == "__main__":
    raise SystemExit(main())
