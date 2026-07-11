#!/usr/bin/env python3
"""Process one approved case-group source and print safe table aggregates only."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate1Normalizer,
    Gate2TablePackageFactory,
    build_retention_policy,
    persist_gate1_result,
    validate_gate2_table_package,
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
    parser.add_argument("--source-index", type=int, required=True)
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
    source = sources["files"][args.source_index]
    started = time.perf_counter()
    normalizer = Gate1Normalizer()
    result = normalizer.normalize(
        [_file_input(source, args.source_index + 1)],
        input_context={
            "clarification_criticality_refinement_enabled": True,
            "pdf_layout_slice2_enabled": True,
        },
    )
    projections = result.package.get("private_normalized_table_projections") or []
    packages = []
    package_blocked = 0
    for projection in projections:
        if projection.get("projection_status") != "ready":
            continue
        try:
            package = Gate2TablePackageFactory().create().build(
                projection=projection,
                case_id="approved_case_group_002_table_preflight",
            )
        except ValueError as exc:
            if str(exc) in {
                "gate2_table_package_row_budget_exceeded",
                "gate2_table_projection_not_ready",
                "gate2_table_projection_quality_not_eligible",
                "gate2_table_projection_coverage_not_eligible",
            }:
                package_blocked += 1
                continue
            raise
        validate_gate2_table_package(package, projection)
        packages.append(package)
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
            user_id="approved-table-preflight",
            normalization_run_id=run_id,
            case_id="approved-case-group-002-table-preflight",
            chat_id="approved-table-preflight-chat",
            workspace_model_id="approved-table-preflight-model",
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
        )
        records = store.list_by_run(run_id)
        projection_records = manifest.artifact_refs_by_type.get(
            "broker_reports_normalized_table_projection_v0", []
        )
        knowledge_records = sum(
            1 for record in records if record.storage_backend == "openwebui_knowledge"
        )
    payload_sizes = [
        len(json.dumps(item, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        for item in projections
    ]
    output = {
        "source_index": args.source_index,
        "source_format": source.get("container_format"),
        "normalization_validation_status": result.package["validation_result"]["status"],
        "pdf_table_candidates_found": sum(
            int(item.get("pdf_table_candidates_total") or 0)
            for item in result.package["full_source_coverage_summary"].get("documents") or []
        ),
        "table_projections_created": len(projections),
        "native_table_projections_created": sum(
            1 for item in projections if item.get("source_format") != "pdf"
        ),
        "pdf_table_projections_created": sum(
            1 for item in projections if item.get("source_format") == "pdf"
        ),
        "quality_counts": _counts(
            str(item.get("reconstruction_quality") or "blocked")
            for item in projections
        ),
        "rows_total": sum(int(item.get("row_count") or 0) for item in projections),
        "cells_total": sum(int(item.get("cell_count") or 0) for item in projections),
        "source_value_refs_total": sum(
            len(item.get("source_value_refs") or []) for item in projections
        ),
        "fallback_refs_total": sum(
            len((item.get("coverage") or {}).get("fallback_text_refs") or [])
            for item in projections
        ),
        "unaccounted_refs_total": sum(
            len((item.get("coverage") or {}).get("unaccounted_refs") or [])
            for item in projections
        ),
        "duplicate_refs_total": sum(
            len((item.get("coverage") or {}).get("duplicate_accounted_refs") or [])
            for item in projections
        ),
        "gate2_no_model_packages_total": len(packages),
        "gate2_no_model_packages_blocked_total": package_blocked,
        "model_calls_total": 0,
        "source_facts_persisted_total": 0,
        "projection_artifact_records_total": len(projection_records),
        "artifactstore_knowledge_records": knowledge_records,
        "payload_size_bytes_total": sum(payload_sizes),
        "payload_size_bytes_max": max(payload_sizes or [0]),
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "table_projection_runtime_seconds": getattr(
            normalizer, "last_table_projection_runtime_seconds", 0.0
        ),
        "table_projection_runtime_seconds_max": getattr(
            normalizer, "last_table_projection_runtime_seconds_max", 0.0
        ),
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


def _counts(values) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


if __name__ == "__main__":
    raise SystemExit(main())
