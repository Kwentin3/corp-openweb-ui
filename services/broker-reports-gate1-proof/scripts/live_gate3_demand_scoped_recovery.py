#!/usr/bin/env python3
"""Replay one frozen demand result through non-destructive Gate 3 recovery."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    Gate3FinancialAnnotationsPersistenceError,
    Gate3FinancialAnnotationsPersistenceFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5DeterministicSourceFactConsumptionRuntimeFactory,
)
from broker_reports_gate1.gate5_trusted_methodology import (  # noqa: E402
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-store-root", type=Path, required=True)
    parser.add_argument("--provider-result", type=Path, required=True)
    parser.add_argument("--prior-downstream-result", type=Path, required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    parser.add_argument("--expect-source-lineage-conflict", action="store_true")
    args = parser.parse_args()

    source_store = args.source_store_root.resolve()
    output_root = args.private_output_root.resolve()
    working_store = output_root / "working-store"
    if output_root.exists():
        raise SystemExit("private_output_root_must_be_new")
    if not (source_store / "artifacts.sqlite3").is_file():
        raise SystemExit("source_store_missing")
    source_db_before = _sha256(source_store / "artifacts.sqlite3")
    shutil.copytree(source_store, working_store)

    prior = _read_json(args.prior_downstream_result)
    provider = _read_json(args.provider_result)
    old_sidecar_id = _required_text(prior, "old_sidecar_artifact_id")
    destructive_sidecar_id = _required_text(prior, "new_sidecar_artifact_id")
    with sqlite3.connect(working_store / "artifacts.sqlite3") as connection:
        cursor = connection.execute(
            """
            UPDATE artifact_records
               SET validation_status = 'blocked', lifecycle_status = 'blocked'
             WHERE artifact_id = ?
            """,
            (destructive_sidecar_id,),
        )
        if cursor.rowcount != 1:
            raise SystemExit("destructive_proof_sidecar_not_found")
        connection.commit()

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=working_store / "artifacts.sqlite3",
            payload_root=working_store / "payloads",
        )
    ).create()
    old_record = store.get_record_unchecked(old_sidecar_id)
    if old_record is None or not old_record.document_id:
        raise SystemExit("old_full_sidecar_not_found")
    context = ArtifactAccessContext(
        user_id=old_record.user_id,
        normalization_run_id=old_record.normalization_run_id,
        case_id=old_record.case_id,
        chat_id=old_record.chat_id,
        workspace_model_id=old_record.workspace_model_id,
        allow_private=True,
    )
    frozen = provider.get("result")
    if not isinstance(frozen, dict):
        raise SystemExit("provider_result_invalid")
    annotations = (frozen.get("merged_output") or {}).get("annotations")
    if (
        not isinstance(annotations, list)
        or len(annotations) != 5
        or {item.get("financial_label") for item in annotations}
        != {"SECURITY_PURCHASE"}
    ):
        raise SystemExit("frozen_purchase_delta_invalid")
    selected = list(frozen.get("selected_chunk_ordinals") or [])
    document_result = {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "semantic_scope": {
            "publication_mode": "DEMAND_SCOPED",
            "document_id": old_record.document_id,
            "requested_financial_labels": ["SECURITY_PURCHASE"],
            "requested_roles": [
                "amount",
                "asset",
                "currency",
                "date",
                "quantity",
                "unit_price",
            ],
            "selected_chunk_ordinals": selected,
        },
        "selected_chunk_ordinals": selected,
        "selection_mode": frozen.get("selection_mode"),
        "document_status": frozen.get("document_status"),
        "metrics": copy.deepcopy(frozen.get("metrics")),
        "merged_output": copy.deepcopy(frozen.get("merged_output")),
    }
    persistence = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    base_payload = persistence.read(
        artifact_id=old_sidecar_id,
        context=context,
    )
    base_purchase_targets = {
        json.dumps(item["target"], sort_keys=True)
        for item in base_payload["annotations"]
        if item["financial_label"] == "SECURITY_PURCHASE"
    }
    delta_purchase_targets = {
        json.dumps(item["target"], sort_keys=True) for item in annotations
    }
    exact_purchase_target_overlap = len(base_purchase_targets & delta_purchase_targets)
    records_before_recovery = len(store.list_by_run(context.normalization_run_id))
    recovery_error = None
    recovered = None
    try:
        recovered = persistence.save_recovery(
            document_id=old_record.document_id,
            context=context,
            validated_document_result=document_result,
            provider_profile_id=str(old_record.safe_metadata["provider_profile_id"]),
            base_annotations_artifact_id=old_sidecar_id,
            demand_request_id="g554_security_purchase_recovery",
        )
    except Gate3FinancialAnnotationsPersistenceError as exc:
        recovery_error = exc.code
        if (
            not args.expect_source_lineage_conflict
            or exc.code != "gate3_annotations_recovery_conflict"
        ):
            raise
    if args.expect_source_lineage_conflict and recovered is not None:
        raise SystemExit("source_lineage_conflict_expected")
    records_after_recovery = len(store.list_by_run(context.normalization_run_id))
    payload = (
        base_payload
        if recovered is None
        else persistence.read(
            artifact_id=recovered.record.artifact_id,
            context=context,
        )
    )
    semantic_counts = Counter(
        item["financial_label"] for item in payload["annotations"]
    )
    gate4 = (
        Gate4FinancialCaseRuntimeFactory(store=store, read_enabled=True)
        .create()
        .rebuild_case(context=context)
    )
    document_facts = [
        fact
        for fact in gate4.facts
        if fact["gate3_binding"]["canonical_binding"]["document_id"]
        == old_record.document_id
    ]
    gate5 = (
        Gate5DeterministicSourceFactConsumptionRuntimeFactory(
            store=store, read_enabled=True
        )
        .create()
        .assess(
            methodology_ref={
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
                "methodology_version": (
                    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION
                ),
            },
            context=context,
        )
    )
    replay_check = {
        "annotations": len(payload["annotations"]),
        "purchases": semantic_counts["SECURITY_PURCHASE"],
        "commission_charge": (
            semantic_counts["COMMISSION"] + semantic_counts["TRANSACTION_CHARGE"]
        ),
        "gate4_document_facts": len(document_facts),
        "gate5_security_facts": gate5["security_fact_counts"]["total"],
        "deleted": 0 if recovered is None else recovered.receipt["deleted_total"],
    }
    expected_replay = (
        {
            "annotations": 21,
            "purchases": 5,
            "commission_charge": 16,
            "gate4_document_facts": 21,
            "gate5_security_facts": 48,
            "deleted": 0,
        }
        if args.expect_source_lineage_conflict
        else {
            "annotations": 26,
            "purchases": 10,
            "commission_charge": 16,
            "gate4_document_facts": 26,
            "gate5_security_facts": 53,
            "deleted": 0,
        }
    )
    if replay_check != expected_replay or exact_purchase_target_overlap != 0:
        print(json.dumps(replay_check, sort_keys=True), file=sys.stderr)
        raise SystemExit("non_destructive_replay_failed")
    if (
        args.expect_source_lineage_conflict
        and records_after_recovery != records_before_recovery
    ):
        raise SystemExit("conflicting_recovery_persisted_artifact")
    private_result = {
        "schema_version": (
            "broker_reports_g556_private_replay_v1"
            if args.expect_source_lineage_conflict
            else "broker_reports_g555_private_replay_v1"
        ),
        "recovery_receipt": None if recovered is None else recovered.receipt,
        "recovery_error": recovery_error,
        "semantic_counts": dict(sorted(semantic_counts.items())),
        "gate4_document_facts": document_facts,
        "gate5_assessment": gate5,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "result.private.json").write_text(
        json.dumps(private_result, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    safe = {
        "schema_version": (
            "broker_reports_g556_replay_receipt_v1"
            if args.expect_source_lineage_conflict
            else "broker_reports_g555_replay_receipt_v1"
        ),
        "source_store_unchanged": (
            _sha256(source_store / "artifacts.sqlite3") == source_db_before
        ),
        "provider_calls": 0,
        "provider_result_sha256": _sha256(args.provider_result),
        "annotations_before": 21,
        "demand_annotations": 5,
        "annotations_after": len(payload["annotations"]),
        "purchases_after": semantic_counts["SECURITY_PURCHASE"],
        "base_purchase_targets": len(base_purchase_targets),
        "exact_purchase_target_overlap": exact_purchase_target_overlap,
        "unrelated_commission_charge_after": (
            semantic_counts["COMMISSION"] + semantic_counts["TRANSACTION_CHARGE"]
        ),
        "gate4_document_facts_after": len(document_facts),
        "gate5_security_facts_after": gate5["security_fact_counts"]["total"],
        "recovery_error": recovery_error,
        "artifact_records_written_by_recovery": (
            records_after_recovery - records_before_recovery
        ),
        "added_total": None if recovered is None else recovered.receipt["added_total"],
        "superseded_total": (
            None if recovered is None else recovered.receipt["superseded_total"]
        ),
        "unchanged_recovered_total": (
            None
            if recovered is None
            else recovered.receipt["unchanged_recovered_total"]
        ),
        "preserved_unrelated_total": (
            16 if recovered is None else recovered.receipt["preserved_unrelated_total"]
        ),
        "deleted_total": 0 if recovered is None else recovered.receipt["deleted_total"],
        "gate4_status": gate4.status,
        "gate5_terminals": gate5["terminals"],
        "stored_financial_event_relations": gate5["stored_financial_event_relations"],
    }
    (output_root / "receipt.safe.json").write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("json_object_required")
    return value


def _required_text(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise SystemExit(f"{key}_required")
    return item


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
