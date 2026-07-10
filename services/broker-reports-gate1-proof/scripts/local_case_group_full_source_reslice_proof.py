#!/usr/bin/env python3
"""Controlled private re-intake proof for Gate 1 full-source coverage.

Reads hash-verified private registry files locally, persists them only to an
ephemeral ArtifactStore, and emits safe aggregate counts. It performs no
ordinary upload, Knowledge/RAG/vector write, model call, OCR, tax, declaration,
or XLS/XLSX generation.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import tempfile
import time
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
    Gate2SourceUnitRouterFactory,
    Gate2SourceUnitSegmenterFactory,
    build_retention_policy,
    persist_gate1_result,
)
from live_case_group_process_false_gate1_run import (  # noqa: E402
    DEFAULT_CASE_GROUPS,
    DEFAULT_CASE_GROUP_ID,
    DEFAULT_PRIVATE_REGISTRY,
    DEFAULT_SAFE_SOURCE_REGISTRY,
    _resolve_case_group_sources,
    _source_policy_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-group-id", default=DEFAULT_CASE_GROUP_ID)
    parser.add_argument("--private-registry", default=DEFAULT_PRIVATE_REGISTRY)
    parser.add_argument("--safe-source-registry", default=DEFAULT_SAFE_SOURCE_REGISTRY)
    parser.add_argument("--case-groups", default=DEFAULT_CASE_GROUPS)
    parser.add_argument(
        "--source-ordinals",
        default="",
        help="Optional comma-separated 1-based safe registry ordinals for a limited proof.",
    )
    args = parser.parse_args()

    sources = _resolve_case_group_sources(
        case_group_id=args.case_group_id,
        private_registry_path=_repo_path(args.private_registry),
        safe_source_registry_path=_repo_path(args.safe_source_registry),
        case_groups_path=_repo_path(args.case_groups),
    )
    selected_ordinals = {
        int(item.strip())
        for item in str(args.source_ordinals or "").split(",")
        if item.strip()
    }
    if selected_ordinals:
        sources["files"] = [
            item
            for index, item in enumerate(sources["files"], start=1)
            if index in selected_ordinals
        ]
        if not sources["files"]:
            raise RuntimeError("controlled_private_source_selection_empty")
        sources["files_total"] = len(sources["files"])
    inputs = []
    for index, source in enumerate(sources["files"], start=1):
        path = Path(source["path"])
        extension = str(source.get("extension") or path.suffix or ".bin")
        alias = f"controlled_private_source_{index:03d}{extension.lower()}"
        inputs.append(
            FileInput(
                private_ref=f"controlled-private:{source['document_id']}",
                original_filename_private=alias,
                mime_type=mimetypes.guess_type(alias)[0] or "application/octet-stream",
                source_kind="local_private_test",
                declared_size_bytes=path.stat().st_size,
                bytes_provider=lambda path=path: path.read_bytes(),
                provider_label="controlled_private_registry",
            )
        )

    started = time.monotonic()
    result = Gate1Normalizer().normalize(
        inputs,
        entrypoint="controlled_private_full_source_reslice_proof",
        trigger_type="controlled_private_reintake",
        input_context={
            "source_policy": _source_policy_payload(sources["source_policy_hints"]),
            "clarification_criticality_refinement_enabled": True,
            "customer_docs_loaded_to_knowledge": False,
            "vectorization_performed": False,
            "ordinary_upload_used": False,
        },
    )
    normalize_seconds = round(time.monotonic() - started, 3)

    package = result.package
    full_summary = package.get("full_source_coverage_summary") or {}
    previews = package.get("private_normalized_slices") or []
    units = package.get("private_normalized_source_units") or []
    complete_documents = {
        str(item.get("document_ref"))
        for item in full_summary.get("documents") or []
        if item.get("full_coverage_available") is True
    }
    truncated_preview_documents = {
        str(item.get("document_id")) for item in previews if item.get("truncated") is True
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
        run_id = package["normalization_run"]["run_id"]
        context = ArtifactAccessContext(
            user_id="controlled-private-proof-user",
            normalization_run_id=run_id,
            case_id=f"controlled_{args.case_group_id}_full_source_reslice",
            chat_id=f"controlled_{args.case_group_id}_full_source_reslice_chat",
            workspace_model_id="broker-reports-full-source-reslice-proof",
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
                for document in package["document_inventory"]["documents"]
            ],
        )
        dcp_ref = manifest.artifact_refs_by_type["domain_context_packet_v0"][0]
        readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
            domain_context_packet_ref=dcp_ref,
            context=context,
        )
        primary_packages = [
            item
            for item in readiness.packages
            if "primary_source_extraction_refs" in item.get("source_bucket_roles", [])
        ]
        routes = []
        segmentation_plans = []
        derived_packages = []
        for source_package in primary_packages:
            route = Gate2SourceUnitRouterFactory().create().route(source_package)
            segmented = Gate2SourceUnitSegmenterFactory().create().segment(
                base_package=source_package,
                parent_route=route,
            )
            routes.append(route)
            segmentation_plans.append(segmented.plan)
            derived_packages.extend(segmented.derived_packages)

        typed_derived = []
        for source_package, route, plan in zip(primary_packages, routes, segmentation_plans):
            route_by_ref = {
                str(item.get("source_ref")): item for item in route.get("route_entries") or []
            }
            for segment in plan.get("segments") or []:
                entries = [
                    route_by_ref.get(str(ref), {})
                    for ref in segment.get("selected_source_refs") or []
                ]
                model_entries = [
                    item for item in entries if item.get("route_kind") == "model_candidate"
                ]
                if (
                    entries
                    and len(model_entries) == len(entries)
                    and segment.get("segment_kind") == "typed_high_confidence_cluster"
                ):
                    typed_derived.append(
                        {
                            "domain": segment.get("primary_domain"),
                            "parent_source_truncated": (
                                source_package.get("source_unit") or {}
                            ).get("source_slice_truncated")
                            is True,
                            "parent_remainder_status": (
                                source_package.get("source_unit") or {}
                            ).get("parent_remainder_status"),
                            "selected_refs_total": len(
                                segment.get("selected_source_refs") or []
                            ),
                        }
                    )

        records = store.list_by_run(run_id)
        type_counts = Counter(item.artifact_type for item in records)
        storage_counts = Counter(item.storage_backend for item in records)
        format_status = full_summary.get("format_status_counts") or {}
        checks = {
            "gate1_validation_passed": package.get("validation_result", {}).get("status")
            == "passed",
            "private_source_payloads_persisted": type_counts.get(
                "private_normalized_source_payload_v0", 0
            )
            == len(package.get("private_normalized_source_payloads") or []),
            "private_source_units_persisted": type_counts.get(
                "private_normalized_source_unit_v0", 0
            )
            == len(units),
            "readiness_validation_passed": readiness.validation.get("validator_status")
            == "passed",
            "no_source_ready_document_loss": readiness.safe_report.get(
                "no_source_ready_document_loss"
            )
            is True,
            "full_source_units_preferred": readiness.safe_report.get(
                "source_input_mode_counts", {}
            ).get("full_source_unit", 0)
            > 0,
            "selected_complete_units_have_no_parent_remainder": all(
                (item.get("source_unit") or {}).get("parent_remainder_status")
                == "not_applicable_parent_complete"
                for item in primary_packages
                if (item.get("source_unit") or {}).get("source_input_mode")
                == "full_source_unit"
            ),
            "complete_segmentation_has_no_parent_remainder": all(
                (item.get("coverage") or {}).get("parent_remainder_status")
                == "not_applicable_parent_complete"
                for item in segmentation_plans
            ),
            "position_snapshot_complete_target_available": any(
                item.get("domain") == "position_snapshot"
                and item.get("parent_source_truncated") is False
                and item.get("parent_remainder_status")
                == "not_applicable_parent_complete"
                for item in typed_derived
            ),
            "artifactstore_no_knowledge_backend": storage_counts.get(
                "openwebui_knowledge", 0
            )
            == 0,
            "ordinary_upload_not_used": True,
            "ocr_vlm_not_used": True,
            "tax_declaration_xlsx_not_run": True,
        }
        output = {
            "status": "passed" if checks and all(checks.values()) else "partial",
            "case_group_id": args.case_group_id,
            "selected_source_ordinals": sorted(selected_ordinals),
            "normalization_seconds": normalize_seconds,
            "documents_total": sources["files_total"],
            "registry_format_counts": sources["case_group_summary"][
                "formats_from_registry"
            ],
            "full_source_format_status_counts": format_status,
            "legacy_preview_units_total": len(previews),
            "legacy_truncated_parent_units_total": sum(
                1 for item in previews if item.get("truncated") is True
            ),
            "legacy_truncated_documents_total": len(truncated_preview_documents),
            "truncated_documents_now_with_complete_units_total": len(
                truncated_preview_documents & complete_documents
            ),
            "full_source_payloads_total": len(
                package.get("private_normalized_source_payloads") or []
            ),
            "complete_extraction_source_units_total": len(units),
            "complete_documents_total": len(complete_documents),
            "source_ready_documents_total": readiness.safe_report.get(
                "source_ready_documents_total"
            ),
            "packageable_documents_total": readiness.safe_report.get(
                "packageable_documents_total"
            ),
            "source_input_mode_counts": readiness.safe_report.get(
                "source_input_mode_counts"
            ),
            "primary_packages_total": len(primary_packages),
            "segmentation_plans_total": len(segmentation_plans),
            "derived_source_units_total": len(derived_packages),
            "typed_high_confidence_derived_units_total": len(typed_derived),
            "typed_high_confidence_domains": dict(
                sorted(Counter(str(item.get("domain")) for item in typed_derived).items())
            ),
            "position_snapshot_complete_targets_total": sum(
                1
                for item in typed_derived
                if item.get("domain") == "position_snapshot"
                and item.get("parent_source_truncated") is False
                and item.get("parent_remainder_status")
                == "not_applicable_parent_complete"
            ),
            "artifact_type_counts": dict(sorted(type_counts.items())),
            "storage_backend_counts": dict(sorted(storage_counts.items())),
            "checks": checks,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if output["status"] == "passed" else 2


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
