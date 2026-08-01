#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from broker_reports_gate1.artifact_models import ArtifactAccessContext, ArtifactRecord
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.managed_document_contracts import (
    ManagedDocumentContractValidator,
)
from broker_reports_gate1.managed_document_llm_view import (
    LLM_DOCUMENT_VIEW_ARTIFACT_TYPE,
    LLM_DOCUMENT_VIEW_RECEIPT_ARTIFACT_TYPE,
    ManagedDocumentLlmViewFactory,
    inactive_doc3_artifact_type_scope,
)
from broker_reports_gate1.managed_document_llm_view_parity import (
    build_llm_view_only_checklist,
    build_managed_document_only_checklist,
    compare_view_checklists,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json"
)
DEFAULT_COVERAGE_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "BROKER_REPORTS_DOC1_TO_DOC3_VIEW_COVERAGE.v1.json"
)
FIXED_CREATED_AT = "2026-08-01T00:00:00Z"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inactive deterministic Managed Document to LLM View proof runner."
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=("render", "managed-checklist", "view-checklist", "compare"),
    )
    parser.add_argument("--managed-document", type=Path)
    parser.add_argument("--llm-view", type=Path)
    parser.add_argument("--managed-checklist", type=Path)
    parser.add_argument("--view-checklist", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE_PATH)
    parser.add_argument("--safe-id", default="private_document")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "render":
        document_path = _required_file(args.managed_document, "--managed-document")
        schema = _read_json(_required_file(args.schema, "--schema"))
        coverage = _read_json(_required_file(args.coverage, "--coverage"))
        document = ManagedDocumentContractValidator(schema).parse_json(
            document_path.read_bytes()
        ).payload
        result = ManagedDocumentLlmViewFactory().create(schema, coverage).render(
            document
        )
        _write_json(args.output_dir / "managed_document.private.json", document)
        _write_text(
            args.output_dir / "llm_document_view.private.txt", result.view_text
        )
        _write_json(
            args.output_dir / "llm_document_view_receipt.private.json",
            result.receipt,
        )
        with inactive_doc3_artifact_type_scope():
            readback_total = _persist_render_outputs(
                args.output_dir,
                document=document,
                view_text=result.view_text,
                receipt=result.receipt,
            )
        _print_safe(
            {
                "mode": "render",
                "safe_id": args.safe_id,
                "status": "PASSED",
                "output_view_sha256": result.receipt["output_view_sha256"],
                "output_bytes": result.receipt["output_bytes"],
                "output_lines": result.receipt["output_lines"],
                "reference_tokens_total": result.receipt[
                    "reference_tokens_total"
                ],
                "blocks_rendered_total": result.receipt["coverage"][
                    "blocks_rendered_total"
                ],
                "artifact_store_readback_total": readback_total,
                "provider_calls_total": 0,
                "product_route_connected": False,
            }
        )
        return 0

    if args.mode == "managed-checklist":
        document_path = _required_file(args.managed_document, "--managed-document")
        schema = _read_json(_required_file(args.schema, "--schema"))
        document = ManagedDocumentContractValidator(schema).parse_json(
            document_path.read_bytes()
        ).payload
        checklist = build_managed_document_only_checklist(document)
        _write_json(
            args.output_dir / "managed_document_checklist.private.json", checklist
        )
        _print_safe(_checklist_summary(args.safe_id, checklist))
        return 0

    if args.mode == "view-checklist":
        view_path = _required_file(args.llm_view, "--llm-view")
        checklist = build_llm_view_only_checklist(view_path.read_bytes())
        _write_json(args.output_dir / "llm_view_checklist.private.json", checklist)
        _print_safe(_checklist_summary(args.safe_id, checklist))
        return 0

    managed = _read_json(
        _required_file(args.managed_checklist, "--managed-checklist")
    )
    view = _read_json(_required_file(args.view_checklist, "--view-checklist"))
    comparison = compare_view_checklists(managed, view)
    _write_json(
        args.output_dir / "view_parity_comparison.private.json", comparison
    )
    _print_safe(
        {
            "mode": "compare",
            "safe_id": args.safe_id,
            "full_parity": comparison["full_parity"],
            "critical_mismatches_total": comparison[
                "critical_mismatches_total"
            ],
            "noncritical_findings_total": comparison[
                "noncritical_findings_total"
            ],
        }
    )
    return 0 if comparison["critical_mismatches_total"] == 0 else 3


def _persist_render_outputs(
    output_dir: Path,
    *,
    document: dict[str, Any],
    view_text: str,
    receipt: dict[str, Any],
) -> int:
    store_root = output_dir / "artifact_store"
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    document_hash = receipt["input_managed_document_sha256"]
    document_id = document["document_id"]
    normalization_run_id = "norm_doc3_" + document_hash[:24]
    case_id = "case_doc3_" + document_hash[:24]
    user_id = "user_doc3_offline"
    retention = build_retention_policy(mode="manual_purge_required", explicit=True)
    payloads: list[tuple[str, Any, dict[str, Any]]] = [
        (
            LLM_DOCUMENT_VIEW_ARTIFACT_TYPE,
            view_text,
            {
                "view_sha256": receipt["output_view_sha256"],
                "view_bytes": receipt["output_bytes"],
                "reference_tokens_total": receipt["reference_tokens_total"],
            },
        ),
        (
            LLM_DOCUMENT_VIEW_RECEIPT_ARTIFACT_TYPE,
            receipt,
            {
                "status": "PASSED",
                "blocks_rendered_total": receipt["coverage"][
                    "blocks_rendered_total"
                ],
            },
        ),
    ]
    artifact_ids: list[str] = []
    for artifact_type, payload, safe_metadata in payloads:
        artifact_id = "art_doc3_" + _sha256(
            f"{document_hash}|{artifact_type}"
        )[:32]
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
                    "managed_document_sha256": document_hash,
                    "source_deleted": False,
                },
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=retention,
                access_policy={"scope": "case_private", "offline_doc3_only": True},
                validation_status="validated",
                lifecycle_status="private_ready",
                payload=payload,
                safe_metadata=safe_metadata,
                created_at=FIXED_CREATED_AT,
                updated_at=FIXED_CREATED_AT,
            )
        )
        artifact_ids.append(stored.artifact_id)
    context = ArtifactAccessContext(
        user_id=user_id,
        normalization_run_id=normalization_run_id,
        case_id=case_id,
        allow_private=True,
        require_source_available=True,
    )
    resolver = ArtifactResolver(store)
    for artifact_id, (_, payload, _) in zip(artifact_ids, payloads, strict=True):
        if resolver.resolve(artifact_id, context)["payload"] != payload:
            raise RuntimeError("llm_document_view_artifact_readback_mismatch")
    return len(artifact_ids)


def _checklist_summary(safe_id: str, checklist: dict[str, Any]) -> dict[str, Any]:
    inventory = checklist["inventory"]
    return {
        "mode": checklist["pass"].lower().replace("_", "-"),
        "safe_id": safe_id,
        "terminal_status": checklist["terminal_status"],
        "blocks_total": inventory["blocks_total"],
        "tables_total": inventory["tables_total"],
        "unknown_blocks_total": inventory["unknown_blocks_total"],
        "visual_blocks_total": inventory["visual_blocks_total"],
        "losses_total": inventory["losses_total"],
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
        raise ValueError("llm_document_view_json_object_required")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _print_safe(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
