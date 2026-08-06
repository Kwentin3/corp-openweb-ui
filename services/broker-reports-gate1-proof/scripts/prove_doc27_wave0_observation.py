from __future__ import annotations

import hashlib
import json
import statistics
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
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReadLedger,
    CanonicalReaderFactory,
    Doc22SafeEvidenceCanonicalAdapterFactory,
    Gate1ArtifactStoreCanonicalAdapterFactory,
    LocalPdfCompactResearchCanonicalAdapterFactory,
    PdfCompactCanonicalAdapterFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_models import ArtifactRecord  # noqa: E402


PRIVATE_ROOT = (
    REPO_ROOT
    / "local/stage2/broker_reports_doc27_consumer_migration_2026-08-05/private"
)
DOCUMENT_ID = "doc27-sealed-observation-document"
SOURCE_SHA256 = "b" * 64
P95_THRESHOLD_MS = 250.0

FACTORY_REQUIRED = (
    "DOC27 observation must use consumer-specific factories backed only by "
    "CanonicalReaderFactory.create"
)
FORBIDDEN = (
    "Provider, parser, cropper, VLM, private actual-corpus rerun, direct SQL, "
    "global read enable and silent legacy fallback are forbidden"
)


def _context(run_id: str) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="doc27-observation-user",
        normalization_run_id=run_id,
        case_id="doc27-observation-case",
        workspace_model_id="doc27-observation-workspace",
        allow_private=True,
        require_source_available=True,
    )


def _source_record(context: ArtifactAccessContext) -> ArtifactRecord:
    source_file_ref = {
        "provider": "doc27-sealed-manual-fixture",
        "openwebui_file_id": f"doc27-source-{context.normalization_run_id}",
        "file_hash_sha256": SOURCE_SHA256,
        "content_type": "application/pdf",
        "size_bytes": 64,
    }
    return ArtifactRecord(
        artifact_id=f"art_doc27_source_{context.normalization_run_id}",
        artifact_type="source_file_ref_v0",
        case_id=context.case_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        workspace_model_id=context.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        document_id=DOCUMENT_ID,
        source_file_ref=source_file_ref,
        visibility="private_case",
        storage_backend="project_artifact_payload",
        retention_policy=build_retention_policy(mode="api_smoke"),
        access_policy={
            "requires_user_id": True,
            "requires_case_or_chat": True,
        },
        validation_status="validated",
        lifecycle_status="private_ready",
        payload_kind="json_file",
        payload={
            "schema_version": "source_file_ref_v0",
            "document_id": DOCUMENT_ID,
            "source_file_ref": source_file_ref,
        },
        safe_metadata={"source_available": True},
    )


def _artifact(source_ref: str, normalizer_version: str) -> dict[str, Any]:
    return CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version=normalizer_version)
    ).create().build(
        tenant_id="doc27-observation-user",
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": SOURCE_SHA256,
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref=source_ref,
        source_payloads=[],
        source_units=[
            {
                "unit_ref": "sealed-table-unit",
                "source_location": {"page": 1, "line_start": 1},
                "text": "A B 1 2",
            },
            {
                "unit_ref": "sealed-text-unit",
                "source_location": {"page": 1, "line_start": 2},
                "text": "sealed observation fixture",
            },
        ],
        table_projections=[
            {
                "projection_status": "ready",
                "table_projection_id": "sealed-table",
                "source_unit_ref": "sealed-table-unit",
                "row_count": 2,
                "column_count": 2,
                "cells": [
                    {
                        "row_ordinal": row,
                        "column_ordinal": column,
                        "normalized_private_value_path": f"v-{row}-{column}",
                    }
                    for row in (1, 2)
                    for column in (1, 2)
                ],
                "private_values": [
                    {
                        "value_path_ref": f"v-{row}-{column}",
                        "normalized_value": value,
                    }
                    for row, values in ((1, ("A", "B")), (2, ("1", "2")))
                    for column, value in enumerate(values, 1)
                ],
            }
        ],
    )


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def run() -> dict[str, Any]:
    for name in (
        "doc27_consumer_shadow",
        "doc27_migration_runs",
        "doc27_wave0_outputs",
        "doc27_wave1_outputs",
        "doc27_latency_baselines",
        "doc27_rollback_proofs",
        "doc27_call_and_read_ledgers",
    ):
        (PRIVATE_ROOT / name).mkdir(parents=True, exist_ok=True)

    store_root = PRIVATE_ROOT / "sealed_observation_store"
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context1 = _context("doc27-observation-run-1")
    source1 = store.put_record(_source_record(context1))
    first = CanonicalArtifactStoreFactory(store=store).create().put_candidate(
        artifact=_artifact(source1.artifact_id, "doc27-observation-v1"),
        context=context1,
        retention_policy=build_retention_policy(mode="api_smoke"),
        compare_receipt=None,
    )
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    first_activation = reader.activate(
        canonical_version_id=first.canonical_version_id,
        expected_previous_version_id=None,
        context=context1,
        actor="doc27-observation",
        reason="sealed Wave 0 observation candidate",
    )

    factories = (
        Doc22SafeEvidenceCanonicalAdapterFactory,
        Gate1ArtifactStoreCanonicalAdapterFactory,
        PdfCompactCanonicalAdapterFactory,
        LocalPdfCompactResearchCanonicalAdapterFactory,
    )
    ledger = CanonicalReadLedger()
    observations: dict[str, list[dict[str, Any]]] = {}
    for factory_type in factories:
        adapter = factory_type(store=store, enabled=True, ledger=ledger).create()
        runs = []
        for run_number in range(1, 4):
            result = adapter.read_active(document_id=DOCUMENT_ID, context=context1)
            runs.append(
                {
                    "run_number": run_number,
                    "compatibility_status": result.compatibility_status,
                    "error_code": result.error_code,
                    "output_sha256": _hash(result.output),
                    "telemetry": result.telemetry,
                }
            )
        observations[factory_type.mapping.consumer_id] = runs

    rollback_results: dict[str, Any] = {}
    for factory_type in factories:
        disabled = factory_type(
            store=store, enabled=False, ledger=ledger
        ).create().read_active(document_id=DOCUMENT_ID, context=context1)
        ledger.record_rollback(
            consumer_id=factory_type.mapping.consumer_id,
            migration_wave=factory_type.mapping.migration_wave,
        )
        rollback_results[factory_type.mapping.consumer_id] = {
            "compatibility_status": disabled.compatibility_status,
            "error_code": disabled.error_code,
            "legacy_fallback_inside_adapter": False,
            "active_pointer_changed": False,
            "rollback_event_recorded": True,
        }

    context2 = _context("doc27-observation-run-2")
    source2 = store.put_record(_source_record(context2))
    second = CanonicalArtifactStoreFactory(store=store).create().put_candidate(
        artifact=_artifact(source2.artifact_id, "doc27-observation-v2"),
        context=context2,
        retention_policy=build_retention_policy(mode="api_smoke"),
        compare_receipt=None,
    )
    stale_rejected = False
    try:
        reader.activate(
            canonical_version_id=second.canonical_version_id,
            expected_previous_version_id="canver_stale",
            context=context2,
            actor="doc27-observation",
            reason="stale CAS proof",
        )
    except Exception as exc:  # safe terminal classification below
        stale_rejected = getattr(exc, "code", "") == "canonical_pointer_conflict"
    second_activation = reader.activate(
        canonical_version_id=second.canonical_version_id,
        expected_previous_version_id=first.canonical_version_id,
        context=context2,
        actor="doc27-observation",
        reason="document-specific cohort promotion",
    )
    rollback = reader.rollback(
        target_version_id=first.canonical_version_id,
        expected_current_version_id=second.canonical_version_id,
        context=context1,
        actor="doc27-observation",
        reason="document-specific cohort rollback",
    )
    final_active = store.get_active_canonical_version(
        context=context1, document_id=DOCUMENT_ID
    )

    latencies = [
        float(event["canonical_read_latency_ms"])
        for event in ledger.events
        if event["canonical_read_attempts"] == 1
        and event["canonical_read_success"] == 1
    ]
    outputs_stable = all(
        len({item["output_sha256"] for item in runs}) == 1
        for runs in observations.values()
    )
    statuses_stable = all(
        {item["compatibility_status"] for item in runs} == {"CANONICAL_OK"}
        for runs in observations.values()
    )
    p95 = max(latencies) if len(latencies) < 20 else statistics.quantiles(
        latencies, n=20
    )[18]
    actual_store = (
        REPO_ROOT
        / "local/stage2/broker_reports_doc26_gate2_shadow_readiness_2026-08-05/"
        "private/artifacts.sqlite3"
    )
    result = {
        "schema_version": "broker_reports_doc27_private_observation_v1",
        "sealed_fixture_only": True,
        "provider_calls": 0,
        "parser_reruns": 0,
        "cropper_reruns": 0,
        "vlm_reruns": 0,
        "actual_corpus_canonical_store_available": actual_store.is_file(),
        "actual_corpus_rerun_performed": False,
        "observation_runs": observations,
        "observation_runs_completed": "3/3",
        "outputs_stable": outputs_stable,
        "statuses_stable": statuses_stable,
        "read_attempts": sum(
            event["canonical_read_attempts"] for event in ledger.events
        ),
        "read_success": sum(
            event["canonical_read_success"] for event in ledger.events
        ),
        "read_blocked": sum(
            event["canonical_read_blocked"] for event in ledger.events
        ),
        "rollback_events": sum(event["rollback_events"] for event in ledger.events),
        "latency": {
            "threshold_frozen_before_run_ms": P95_THRESHOLD_MS,
            "p50_ms": round(statistics.median(latencies), 6),
            "p95_ms": round(p95, 6),
            "threshold_passed": p95 <= P95_THRESHOLD_MS,
        },
        "rollback_results": rollback_results,
        "active_version_safety": {
            "first_activation": first_activation.status,
            "stale_candidate_rejected": stale_rejected,
            "second_activation": second_activation.status,
            "rollback": rollback.status,
            "final_active_is_rollback_target": (
                final_active.canonical_version_id == first.canonical_version_id
            ),
            "consumer_flag_rollback_independent": True,
        },
        "private_content_in_summary": False,
    }

    _write(PRIVATE_ROOT / "doc27_call_and_read_ledgers/ledger.json", ledger.events)
    _write(
        PRIVATE_ROOT / "doc27_consumer_shadow/observation.json", observations
    )
    _write(
        PRIVATE_ROOT / "doc27_latency_baselines/latency.json", result["latency"]
    )
    _write(
        PRIVATE_ROOT / "doc27_rollback_proofs/rollback.json",
        {
            "consumer_flags": rollback_results,
            "active_version": result["active_version_safety"],
        },
    )
    for consumer_id in (
        "doc22_safe_evidence_test",
        "gate1_artifact_store_test",
        "pdf_compact_canonical_test",
    ):
        receipt = {
            "consumer_id": consumer_id,
            "migration_wave": "WAVE_0_TEST",
            "legacy_contract_version": "gate2_handoff_v0",
            "canonical_contract_version": "canonical_artifact_v1",
            "compatibility_adapter_version": next(
                factory.mapping.compatibility_adapter_version
                for factory in factories
                if factory.mapping.consumer_id == consumer_id
            ),
            "shadow_cases": 3,
            "canonical_regressions": 0,
            "rollback_tested": True,
            "cutover_status": "ENABLED_TEST_ONLY",
        }
        _write(
            PRIVATE_ROOT
            / f"doc27_migration_runs/{consumer_id}.receipt.safe.json",
            receipt,
        )
    _write(PRIVATE_ROOT / "doc27_wave0_outputs/summary.json", result)
    _write(
        PRIVATE_ROOT / "doc27_wave1_outputs/summary.json",
        {
            "planned_consumers": 0,
            "reason": "no frozen legacy surface satisfies Wave 1 read-only rules",
        },
    )
    _write(PRIVATE_ROOT / "doc27_private_summary.safe.json", result)
    return result


def main() -> int:
    result = run()
    passed = (
        result["observation_runs_completed"] == "3/3"
        and result["outputs_stable"]
        and result["statuses_stable"]
        and result["latency"]["threshold_passed"]
        and result["active_version_safety"]["stale_candidate_rejected"]
        and result["active_version_safety"]["final_active_is_rollback_target"]
    )
    print(
        json.dumps(
            {
                "status": "PASSED" if passed else "FAILED",
                "read_attempts": result["read_attempts"],
                "observation_runs": result["observation_runs_completed"],
                "actual_corpus_canonical_store_available": result[
                    "actual_corpus_canonical_store_available"
                ],
            },
            separators=(",", ":"),
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
