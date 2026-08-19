#!/usr/bin/env python3
"""Qualify and activate the G5.80 Gate 2 addressability repair in a copied store."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    FileInput,
    Gate1BoundedGraphConfig,
    Gate1BoundedGraphFactory,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
)


DOCUMENT_ID = "brdoc_001_7cfd297786cc"
NORMALIZATION_RUN_ID = "normrun_b5c1922880533908"
PROBLEM_PAGES = (16, 19, 24, 25, 26, 27)
VISUAL_QUALIFICATION = {
    16: {"primary_table_rows": 42, "source_record_rows": 40},
    19: {"primary_table_rows": 45, "source_record_rows": 44},
    24: {"primary_table_rows": 34, "source_record_rows": 33},
    25: {"primary_table_rows": 36, "source_record_rows": 36},
    26: {"primary_table_rows": 36, "source_record_rows": 35},
    27: {
        "primary_table_rows": 28,
        "source_record_rows": 27,
        "secondary_structured_rows": 8,
    },
}
BASE_CONTEXT = {
    "user_id": "g540e-private-user",
    "case_id": "g540e-real-source-contract",
    "chat_id": None,
    "workspace_model_id": "g540e-private-model",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-on-copied-store", action="store_true")
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--private-evidence-dir", required=True)
    parser.add_argument("--safe-receipt-path", required=True)
    parser.add_argument("--source-pdf", required=True)
    args = parser.parse_args()
    if not args.execute_on_copied_store:
        raise SystemExit("explicit_copied_store_execution_required")

    store_root = Path(args.store_root).resolve()
    private_root = Path(args.private_evidence_dir).resolve()
    safe_path = Path(args.safe_receipt_path).resolve()
    source_path = Path(args.source_pdf).resolve()
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("copied_store_unavailable")
    if not source_path.is_file():
        raise SystemExit("source_pdf_unavailable")
    if _is_within(store_root, REPO_ROOT.resolve()):
        raise SystemExit("proof_store_must_be_outside_repository")
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if not _is_within(safe_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    private_root.mkdir(parents=True, exist_ok=True)
    if safe_path.exists():
        raise SystemExit("safe_receipt_path_must_be_new")

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    source_context = ArtifactAccessContext(
        **BASE_CONTEXT,
        normalization_run_id=NORMALIZATION_RUN_ID,
        allow_private=True,
    )
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    before = reader.read_active_envelope(DOCUMENT_ID, source_context)
    records = [
        record
        for record in store.list_by_case_context(source_context)
        if record.document_id == DOCUMENT_ID
    ]
    old_units = [
        store.read_payload(record)
        for record in records
        if record.artifact_type == "private_normalized_source_unit_v0"
    ]
    persisted_projections = [
        store.read_payload(record)
        for record in records
        if record.artifact_type
        == "broker_reports_normalized_table_projection_v0"
    ]
    file_input = FileInput.from_bytes(
        private_ref="g580-row-addressability-source-copy",
        filename=source_path.name,
        content=source_path.read_bytes(),
        mime_type="application/pdf",
    )
    normalizer = Gate1Normalizer()
    qualification_run_id = normalizer.plan_run_id([file_input])
    if qualification_run_id == NORMALIZATION_RUN_ID:
        raise SystemExit("g580_qualification_run_must_be_distinct")
    candidate_context = ArtifactAccessContext(
        **BASE_CONTEXT,
        normalization_run_id=qualification_run_id,
        allow_private=True,
        require_source_available=True,
    )
    retention = build_retention_policy(mode="customer_approved_test", explicit=True)
    source_file_refs = (
        {
            "provider": "g580_private_development_qualification",
            "openwebui_file_id": "g580-large-real-001-source-copy",
            "content_type": "application/pdf",
            "size_bytes": source_path.stat().st_size,
            "source_deleted": False,
        },
    )
    bounded_graph = Gate1BoundedGraphFactory(
        Gate1BoundedGraphConfig(
            store=store,
            context=candidate_context,
            retention_policy=retention,
            source_file_refs=source_file_refs,
        )
    ).create(normalization_run_id=qualification_run_id)
    normalized = normalizer.normalize(
        [file_input],
        input_context={
            "canonical_gate2_write_enabled": False,
            "clarification_criticality_refinement_enabled": True,
        },
        entrypoint="g580_development_qualification",
        trigger_type="offline_private_proof",
        bounded_graph=bounded_graph,
    )
    persisted_gate1 = persist_gate1_result(
        store=store,
        result=normalized,
        context=candidate_context,
        retention_policy=retention,
        source_file_refs=list(source_file_refs),
    )
    package = normalized.package
    document = next(
        item
        for item in package["document_inventory"]["documents"]
        if item.get("document_id") == DOCUMENT_ID
    )
    payloads = [
        item
        for item in package["private_normalized_source_payloads"]
        if item.get("document_ref") == DOCUMENT_ID
    ]
    units = [
        item
        for item in package["private_normalized_source_units"]
        if item.get("document_id") == DOCUMENT_ID
    ]
    rebuilt_projections = [
        item
        for item in package["private_normalized_table_projections"]
        if item.get("source_document_ref") == DOCUMENT_ID
    ]
    old_units_by_ref = {
        str(unit.get("unit_ref") or ""): unit for unit in old_units
    }
    units_by_ref = {str(unit.get("unit_ref") or ""): unit for unit in units}
    qualification = {
        str(page): _qualify_page(
            page=page,
            before=before.artifact,
            persisted_units_by_ref=old_units_by_ref,
            rebuilt_units_by_ref=units_by_ref,
            persisted_projections=persisted_projections,
            rebuilt_projections=rebuilt_projections,
        )
        for page in PROBLEM_PAGES
    }
    if any(not item["addressability_repaired"] for item in qualification.values()):
        raise SystemExit("g580_six_page_addressability_not_repaired")

    source_artifact_ref = persisted_gate1.artifact_refs_by_type[
        "source_file_ref_v0"
    ][0]
    candidate = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="g580-row-addressability-v1")
    ).create().build(
        tenant_id=candidate_context.user_id,
        artifact_version=before.canonical_version_number + 1,
        document=document,
        source_artifact_ref=source_artifact_ref,
        source_payloads=payloads,
        source_units=units,
        table_projections=rebuilt_projections,
    )
    source_record = ArtifactResolver(store).resolve_record(
        source_artifact_ref, candidate_context
    )
    canonical_store = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(
            minimum_free_bytes=128 * 1024 * 1024,
            critical_free_ratio=0.01,
        ),
    ).create()
    persisted = canonical_store.put_candidate(
        artifact=candidate,
        context=candidate_context,
        retention_policy=source_record.retention_policy,
        compare_receipt=None,
    )
    activation = reader.activate(
        canonical_version_id=persisted.canonical_version_id,
        expected_previous_version_id=before.canonical_version_id,
        context=candidate_context,
        actor="g580-development-qualification",
        reason="broker-neutral merged structural row addressability repair",
    )
    after = reader.read_active_envelope(DOCUMENT_ID, candidate_context)
    after_pages = _canonical_page_summary(after.artifact)
    for page in PROBLEM_PAGES:
        expected = qualification[str(page)]["rebuilt_projection_rows"]
        actual = after_pages.get(page, {}).get("table_rows", [])
        if actual != expected:
            raise SystemExit(f"g580_canonical_page_{page}_row_mismatch")

    private = {
        "schema_version": "broker_reports_g580_gate2_addressability_private_v1",
        "goal": "G5.80",
        "document_id": DOCUMENT_ID,
        "before": {
            "canonical_version_id": before.canonical_version_id,
            "canonical_root_sha256": before.canonical_root_sha256,
            "page_summary": _canonical_page_summary(before.artifact),
        },
        "first_divergence": {
            "owner": "NormalizedTableProjectionFactory.create",
            "reason_code": "pdf_table_geometry_column_structure_insufficient",
            "defect": "minimum row cell count rejected a valid merged structural row",
            "repair": "require at least one multi-column row while preserving every row",
        },
        "visual_qualification": VISUAL_QUALIFICATION,
        "six_page_qualification": qualification,
        "rebuilt_projection_safe_summary": package["table_projection_summary"],
        "after": {
            "canonical_version_id": after.canonical_version_id,
            "canonical_root_sha256": after.canonical_root_sha256,
            "page_summary": after_pages,
        },
        "activation": _jsonable(activation),
        "provider_calls": 0,
        "manual_financial_facts_created": 0,
        "production_visual_dependency": False,
        "proof_store_capacity_policy": "isolated_copy_low_disk_ratio_override",
    }
    private_path = private_root / "gate2-addressability.private.json"
    _write_json(private_path, private)
    safe = {
        "schema_version": "broker_reports_g580_gate2_addressability_safe_v1",
        "goal": "G5.80",
        "document_id": DOCUMENT_ID,
        "pages_qualified": len(PROBLEM_PAGES),
        "first_divergence_owner": "NormalizedTableProjectionFactory.create",
        "first_divergence_reason": "pdf_table_geometry_column_structure_insufficient",
        "persisted_blocked_projection_counts": Counter(
            item["persisted_projection_status"] for item in qualification.values()
        ),
        "rebuilt_ready_pages": sum(
            item["addressability_repaired"] for item in qualification.values()
        ),
        "canonical_before_coarse_text_pages": sum(
            item["before_coarse_text_only"] for item in qualification.values()
        ),
        "canonical_after_table_pages": sum(
            bool(after_pages.get(page, {}).get("table_rows"))
            for page in PROBLEM_PAGES
        ),
        "canonical_version_changed": (
            before.canonical_version_id != after.canonical_version_id
        ),
        "private_evidence_sha256": _file_sha256(private_path),
        "provider_calls": 0,
        "manual_financial_facts_created": 0,
        "broker_specific_rules_added": 0,
        "production_visual_dependency": False,
        "proof_store_capacity_policy": "isolated_copy_low_disk_ratio_override",
    }
    safe["persisted_blocked_projection_counts"] = dict(
        safe["persisted_blocked_projection_counts"]
    )
    _write_json(safe_path, safe)
    print(json.dumps(safe, sort_keys=True))
    return 0


def _qualify_page(
    *,
    page: int,
    before: dict[str, Any],
    persisted_units_by_ref: dict[str, dict[str, Any]],
    rebuilt_units_by_ref: dict[str, dict[str, Any]],
    persisted_projections: list[dict[str, Any]],
    rebuilt_projections: list[dict[str, Any]],
) -> dict[str, Any]:
    persisted = _page_projections(
        page, persisted_units_by_ref, persisted_projections
    )
    rebuilt = _page_projections(page, rebuilt_units_by_ref, rebuilt_projections)
    rebuilt_rows = [int(item.get("row_count") or 0) for item in rebuilt]
    before_page = _canonical_page_summary(before).get(page, {})
    expected_primary = VISUAL_QUALIFICATION[page]["primary_table_rows"]
    return {
        "visual_source_record_rows": VISUAL_QUALIFICATION[page][
            "source_record_rows"
        ],
        "before_node_types": before_page.get("node_types", {}),
        "before_coarse_text_only": (
            before_page.get("node_types", {}).get("TEXT", 0) > 0
            and before_page.get("node_types", {}).get("TABLE", 0) == 0
        ),
        "persisted_projection_status": ",".join(
            str(item.get("table_candidate_status") or "") for item in persisted
        ),
        "persisted_projection_reasons": sorted(
            {
                str(reason)
                for item in persisted
                for reason in item.get("reconstruction_reason_codes") or []
            }
        ),
        "rebuilt_projection_statuses": [
            str(item.get("table_candidate_status") or "") for item in rebuilt
        ],
        "rebuilt_projection_rows": rebuilt_rows,
        "rebuilt_projection_columns": [
            int(item.get("column_count") or 0) for item in rebuilt
        ],
        "addressability_repaired": (
            bool(rebuilt_rows)
            and rebuilt_rows[0] == expected_primary
            and all(
                item.get("projection_status") == "ready"
                and item.get("validator_status") == "passed"
                for item in rebuilt
            )
        ),
    }


def _page_projections(
    page: int,
    units_by_ref: dict[str, dict[str, Any]],
    projections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        item
        for item in projections
        if int(
            (
                units_by_ref.get(str(item.get("source_unit_ref") or ""), {}).get(
                    "source_location"
                )
                or {}
            ).get("page")
            or 0
        )
        == page
    ]


def _canonical_page_summary(artifact: dict[str, Any]) -> dict[int, dict[str, Any]]:
    page_by_container = {
        str(item.get("container_id") or ""): int(
            (item.get("metadata") or {}).get("page_number") or 0
        )
        for item in artifact.get("containers") or []
        if item.get("container_type") == "PAGE"
    }
    result: dict[int, dict[str, Any]] = {}
    for node in artifact.get("nodes") or []:
        page = page_by_container.get(str(node.get("container_ref") or ""), 0)
        if page <= 0:
            continue
        item = result.setdefault(page, {"node_types": {}, "table_rows": []})
        node_type = str(node.get("node_type") or "")
        item["node_types"][node_type] = item["node_types"].get(node_type, 0) + 1
        if node_type == "TABLE":
            item["table_rows"].append(len((node.get("content") or {}).get("rows") or []))
    for item in result.values():
        item["table_rows"].sort(reverse=True)
    return result


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dict__"):
        return {key: _jsonable(item) for key, item in vars(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
