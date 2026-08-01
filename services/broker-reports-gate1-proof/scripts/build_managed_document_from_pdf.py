#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.artifact_models import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactRecord,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver  # noqa: E402
from broker_reports_gate1.artifact_retention import build_retention_policy  # noqa: E402
from broker_reports_gate1.artifact_store import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.managed_document_parity import (  # noqa: E402
    build_artifact_only_checklist,
    build_pdf_only_checklist,
    compare_parity_checklists,
)
from broker_reports_gate1.managed_pdf_document import (  # noqa: E402
    MANAGED_DOCUMENT_ARTIFACT_TYPE,
    MANAGED_DOCUMENT_BUILD_TRACE_ARTIFACT_TYPE,
    MANAGED_DOCUMENT_COVERAGE_ARTIFACT_TYPE,
    SOURCE_OBSERVATION_ARTIFACT_TYPE,
    ManagedPdfBuildResult,
    ManagedPdfDocumentFactory,
    inactive_doc2_artifact_type_scope,
)


DEFAULT_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json"
)
FIXED_CREATED_AT = "2026-08-01T00:00:00Z"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inactive deterministic PDF to Managed Document v1 proof runner."
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=("build", "pdf-checklist", "artifact-checklist", "compare"),
    )
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--managed-document", type=Path)
    parser.add_argument("--pdf-checklist", type=Path)
    parser.add_argument("--artifact-checklist", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "build":
        pdf_path = _required_file(args.pdf, "--pdf")
        schema = _read_json(_required_file(args.schema, "--schema"))
        result = ManagedPdfDocumentFactory().create(schema).build(pdf_path.read_bytes())
        _write_build_outputs(args.output_dir, result)
        with inactive_doc2_artifact_type_scope():
            persisted = _persist_private_outputs(args.output_dir, result)
        _print_safe(
            {
                "mode": "build",
                "status": result.status,
                "document_id": result.source_observation_inventory["document_id"],
                "source_checksum_sha256": result.source_observation_inventory[
                    "source_checksum_sha256"
                ],
                "managed_document_written": result.managed_document is not None,
                "coverage_counters": result.coverage_receipt["counters"],
                "artifact_store_readback_total": persisted,
                "provider_calls_total": 0,
                "product_route_connected": False,
            }
        )
        return 0 if result.status != "BLOCKED" else 2

    if args.mode == "pdf-checklist":
        pdf_path = _required_file(args.pdf, "--pdf")
        checklist = build_pdf_only_checklist(pdf_path.read_bytes())
        _write_json(args.output_dir / "pdf_checklist.private.json", checklist)
        _print_safe(_checklist_summary(checklist))
        return 0 if checklist["terminal_status"] != "BLOCKED" else 2

    if args.mode == "artifact-checklist":
        document_path = _required_file(args.managed_document, "--managed-document")
        checklist = build_artifact_only_checklist(_read_json(document_path))
        _write_json(args.output_dir / "artifact_checklist.private.json", checklist)
        _print_safe(_checklist_summary(checklist))
        return 0

    pdf_checklist = _read_json(_required_file(args.pdf_checklist, "--pdf-checklist"))
    artifact_checklist = _read_json(
        _required_file(args.artifact_checklist, "--artifact-checklist")
    )
    comparison = compare_parity_checklists(pdf_checklist, artifact_checklist)
    _write_json(args.output_dir / "parity_comparison.private.json", comparison)
    _print_safe(
        {
            "mode": "compare",
            "document_id": comparison["document_id"],
            "source_checksum_sha256": comparison["source_checksum_sha256"],
            "critical_mismatches_total": comparison["critical_mismatches_total"],
            "noncritical_mismatches_total": comparison["noncritical_mismatches_total"],
            "full_parity": comparison["full_parity"],
        }
    )
    return 0 if comparison["critical_mismatches_total"] == 0 else 3


def _write_build_outputs(output_dir: Path, result: ManagedPdfBuildResult) -> None:
    if result.managed_document is not None:
        _write_json(
            output_dir / "managed_document.private.json",
            result.managed_document.payload,
        )
    _write_json(
        output_dir / "source_observation_inventory.private.json",
        result.source_observation_inventory,
    )
    _write_json(
        output_dir / "coverage_receipt.private.json",
        result.coverage_receipt,
    )
    _write_json(output_dir / "build_trace.private.json", result.build_trace)


def _persist_private_outputs(output_dir: Path, result: ManagedPdfBuildResult) -> int:
    store_root = output_dir / "artifact_store"
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    document_id = result.source_observation_inventory["document_id"]
    source_sha256 = result.source_observation_inventory["source_checksum_sha256"]
    normalization_run_id = "norm_doc2_" + source_sha256[:24]
    case_id = "case_doc2_" + source_sha256[:24]
    user_id = "user_doc2_offline"
    retention = build_retention_policy(mode="manual_purge_required", explicit=True)
    payloads = [
        (
            SOURCE_OBSERVATION_ARTIFACT_TYPE,
            result.source_observation_inventory,
            {
                "observations_total": result.source_observation_inventory[
                    "observations_total"
                ]
            },
        ),
        (
            MANAGED_DOCUMENT_COVERAGE_ARTIFACT_TYPE,
            result.coverage_receipt,
            dict(result.coverage_receipt["counters"]),
        ),
        (
            MANAGED_DOCUMENT_BUILD_TRACE_ARTIFACT_TYPE,
            result.build_trace,
            {"status": result.status, "provider_calls_total": 0},
        ),
    ]
    if result.managed_document is not None:
        payloads.insert(
            0,
            (
                MANAGED_DOCUMENT_ARTIFACT_TYPE,
                result.managed_document.payload,
                {
                    "quality_status": result.managed_document.payload["quality"][
                        "status"
                    ],
                    "blocks_total": len(result.managed_document.payload["blocks"]),
                },
            ),
        )
    stored_ids = []
    for artifact_type, payload, safe_metadata in payloads:
        artifact_id = (
            "art_doc2_" + _sha256_text(f"{source_sha256}|{artifact_type}")[:32]
        )
        stored = store.put_record(
            ArtifactRecord(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                case_id=case_id,
                chat_id=None,
                user_id=user_id,
                normalization_run_id=normalization_run_id,
                document_id=document_id,
                source_file_ref={
                    "checksum_sha256": source_sha256,
                    "source_deleted": False,
                },
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=retention,
                access_policy={"scope": "case_private", "offline_doc2_only": True},
                validation_status="validated",
                lifecycle_status="private_ready",
                payload=payload,
                safe_metadata=safe_metadata,
                created_at=FIXED_CREATED_AT,
                updated_at=FIXED_CREATED_AT,
            )
        )
        stored_ids.append(stored.artifact_id)
    context = ArtifactAccessContext(
        user_id=user_id,
        normalization_run_id=normalization_run_id,
        case_id=case_id,
        allow_private=True,
        require_source_available=True,
    )
    resolver = ArtifactResolver(store)
    for artifact_id, (_, payload, _) in zip(stored_ids, payloads, strict=True):
        if resolver.resolve(artifact_id, context)["payload"] != payload:
            raise RuntimeError("managed_document_artifact_readback_mismatch")
    return len(stored_ids)


def _checklist_summary(checklist: dict[str, Any]) -> dict[str, Any]:
    summary = checklist.get("summary") or {}
    return {
        "mode": str(checklist["pass"]).lower().replace("_", "-"),
        "document_id": checklist["document_id"],
        "source_checksum_sha256": checklist["source_checksum_sha256"],
        "terminal_status": checklist["terminal_status"],
        "page_boundaries_total": summary.get("page_boundaries_total"),
        "table_regions_total": summary.get("table_regions_total"),
        "validated_tables_total": summary.get("validated_tables_total"),
        "visuals_total": summary.get("visuals_total"),
    }


def _required_file(value: Path | None, option: str) -> Path:
    if value is None:
        raise SystemExit(f"{option} is required for this mode")
    resolved = value.resolve()
    if not resolved.is_file():
        raise SystemExit(f"{option} does not identify a readable file")
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("managed_document_json_object_required")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _print_safe(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
