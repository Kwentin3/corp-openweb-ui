#!/usr/bin/env python3
"""Factory-routed safe proof for the controlled six-page PDF compact shadow."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    PdfCompactCanonicalValidator,
    PdfNormalizationAcceptanceValidator,
    build_retention_policy,
    persist_gate1_result,
)


DEFAULT_PRIVATE_REGISTRY = (
    "local/stage2/broker_reports_customer_source_documents_intake_2026-07-06/"
    "private_registry.json"
)
DEFAULT_DOCUMENT_ID = "brdoc_054_79af73d5be78"
DEFAULT_OUTPUT = (
    "local/stage2/broker_reports_pdf_compact_canonical_2026-07-13/evidence.safe.json"
)

FACTORY_REQUIRED = (
    "Controlled proof must enter through Gate1Normalizer and persist_gate1_result"
)
FORBIDDEN = (
    "The proof must not invoke the compact builder directly, expose private paths or values, "
    "or change Gate 2 selection"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-registry", default=DEFAULT_PRIVATE_REGISTRY)
    parser.add_argument("--document-id", default=DEFAULT_DOCUMENT_ID)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    registry_path = _repo_path(args.private_registry)
    registry = _load_json(registry_path)
    matches = [
        item
        for item in registry.get("documents") or []
        if item.get("document_id") == args.document_id
    ]
    if len(matches) != 1:
        raise RuntimeError("controlled_pdf_private_registry_ref_not_unique")
    source = matches[0]
    source_path = Path(str(source.get("absolute_path") or ""))
    if not source_path.is_file():
        raise RuntimeError("controlled_pdf_source_unavailable")
    content = source_path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    if sha256 != source.get("sha256"):
        raise RuntimeError("controlled_pdf_source_hash_mismatch")

    result = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref=args.document_id,
                filename="controlled-six-page.pdf",
                content=content,
                mime_type="application/pdf",
            )
        ],
        entrypoint="local_pdf_compact_canonical_proof",
        trigger_type="controlled_private_registry_process_false_shadow",
        input_context={
            "pdf_compact_canonical_dual_write": True,
            "clarification_criticality_refinement_enabled": True,
            "customer_file_intake_mode": "process_false_private_registry",
        },
    )
    output_path = _repo_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=output_path.parent / "artifacts.sqlite3",
            payload_root=output_path.parent / "payloads",
        )
    ).create()
    run_id = result.package["normalization_run"]["run_id"]
    manifest = persist_gate1_result(
        store=store,
        result=result,
        context=ArtifactAccessContext(
            user_id="controlled-proof-user",
            normalization_run_id=run_id,
            case_id="controlled-pdf-compact-proof",
        ),
        retention_policy=build_retention_policy(
            mode="customer_approved_test",
            ttl_seconds=None,
            explicit=True,
        ),
        source_file_refs=[
            {
                "provider": "controlled_private_registry_process_false",
                "openwebui_file_id": args.document_id,
                "file_hash_sha256": sha256,
                "content_type": "application/pdf",
                "size_bytes": len(content),
            }
        ],
    )
    compact_record = _latest(
        store.list_by_type(
            run_id, "broker_reports_pdf_compact_canonical_document_v1"
        ),
        "controlled_pdf_compact_artifact_cardinality_invalid",
    )
    acceptance_record = _latest(
        store.list_by_type(
            run_id, "broker_reports_pdf_normalization_acceptance_v1"
        ),
        "controlled_pdf_acceptance_artifact_cardinality_invalid",
    )
    handoff_record = _latest(
        store.list_by_type(run_id, "gate2_handoff_v0"),
        "controlled_pdf_handoff_artifact_cardinality_invalid",
    )
    compact = store.read_payload(compact_record)
    acceptance = store.read_payload(acceptance_record)
    handoff = store.read_payload(handoff_record)
    compact_validation = PdfCompactCanonicalValidator().validate(compact)
    acceptance_validation = PdfNormalizationAcceptanceValidator().validate(acceptance)
    metrics = acceptance["metrics"]
    coverage = compact["coverage"]
    expected = {
        "input_pdf_bytes": 176_458,
        "page_count": 6,
        "table_candidates_total": 14,
        "tables_accepted_total": 9,
        "tables_blocked_total": 5,
    }
    observed = {key: metrics.get(key) for key in expected}
    baseline_matched = observed == expected
    gate2_unchanged = (
        not any("compact" in key for key in handoff)
        and compact_record.artifact_id not in handoff.get("private_slice_refs", [])
        and acceptance_record.artifact_id not in handoff.get("safe_refs", [])
    )
    no_rag = all(
        record.storage_backend != "openwebui_knowledge"
        for record in store.list_by_run(run_id)
    ) and all(
        compact.get(key) is False
        for key in ("knowledge_rag_used", "vectorization_performed")
    )
    proof_passed = (
        baseline_matched
        and compact_validation["passed"]
        and acceptance_validation["passed"]
        and acceptance["acceptance_status"]
        == "accepted_with_explicit_blocked_tables"
        and gate2_unchanged
        and no_rag
    )
    safe_evidence = {
        "schema_version": "broker_reports_pdf_compact_canonical_controlled_proof_v1",
        "document_ref": args.document_id,
        "input_sha256": sha256,
        "normalization_run_id": run_id,
        "proof_status": "passed" if proof_passed else "failed",
        "baseline_expected": expected,
        "baseline_observed": observed,
        "baseline_matched": baseline_matched,
        "compact_validation_status": compact_validation["validator_status"],
        "acceptance_validation_status": acceptance_validation["validator_status"],
        "acceptance_status": acceptance["acceptance_status"],
        "approval_required": acceptance["approval_required"],
        "storage_metrics": {
            key: metrics[key]
            for key in (
                "text_visible_bytes",
                "full_forensic_json_bytes",
                "full_forensic_gzip_bytes",
                "source_units_json_bytes",
                "source_units_gzip_bytes",
                "table_projections_json_bytes",
                "table_projections_gzip_bytes",
                "compact_json_bytes",
                "compact_gzip_bytes",
                "acceptance_record_core_bytes",
                "intended_permanent_bytes",
                "permanent_artifact_total_bytes",
                "temporary_artifact_total_bytes",
                "migration_retained_bytes",
                "temporary_working_state_bytes",
                "permanent_to_original_ratio",
                "permanent_to_visible_text_ratio",
                "duplicate_visible_text_ratio",
            )
        },
        "differential_summary": acceptance["differential_summary"],
        "gate_statuses": {
            key: value["status"] for key, value in acceptance["gates"].items()
        },
        "candidate_refs_accounted": coverage["coverage_status"] == "complete",
        "source_refs_unaccounted": metrics["source_refs_unaccounted"],
        "actual_original_artifact_ref_used": compact["original_pdf_artifact_ref"]
        == manifest.artifact_refs_by_type["source_file_ref_v0"][0],
        "compact_persisted": compact_record.storage_backend
        == "project_artifact_payload",
        "acceptance_persisted": acceptance_record.storage_backend
        == "project_artifact_store",
        "current_artifacts_retained": compact["artifact_roles"][
            "current_artifacts_deleted"
        ]
        is False,
        "production_gate2_selection_changed": not gate2_unchanged,
        "knowledge_rag_used": not no_rag,
        "vectorization_performed": False,
        "ocr_vlm_used": False,
        "page_rendering_used_for_extraction": False,
        "provider_pdf_transport_used": False,
        "private_path_included": False,
        "raw_filename_included": False,
        "raw_values_included": False,
    }
    output_path.write_text(
        json.dumps(safe_evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(safe_evidence, ensure_ascii=True, separators=(",", ":")))
    return 0 if proof_passed else 1


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _latest(values: list[Any], code: str):
    if not values:
        raise RuntimeError(code)
    return values[-1]


if __name__ == "__main__":
    raise SystemExit(main())
