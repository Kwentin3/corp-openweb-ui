from __future__ import annotations

import copy
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReadLedger,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    FROZEN_CONSUMER_SURFACES,
    Gate1ArtifactStoreCanonicalAdapterFactory,
    WAVE0_MAPPINGS,
    build_retention_policy,
)
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.canonical_consumer_migration import (
    CANONICAL_ACCESS_DENIED,
    CANONICAL_CONFLICT,
    CANONICAL_INCOMPLETE,
    CANONICAL_OK,
    CANONICAL_VERSION_UNSUPPORTED,
    classify_consumer_artifact,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
SOURCE_SHA256 = "a" * 64


def _context(run_id: str = "doc27-run") -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="doc27-user",
        normalization_run_id=run_id,
        case_id="doc27-case",
        workspace_model_id="doc27-workspace",
        allow_private=True,
        require_source_available=True,
    )


def _store(root: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()


def _source_record(
    *, context: ArtifactAccessContext, document_id: str
) -> ArtifactRecord:
    source_ref = (
        "art_doc27_source_"
        + document_id
        + "_"
        + context.normalization_run_id
    )
    source_file_ref = {
        "provider": "doc27-sealed-fixture",
        "openwebui_file_id": document_id,
        "file_hash_sha256": SOURCE_SHA256,
        "content_type": "application/pdf",
        "size_bytes": 64,
    }
    return ArtifactRecord(
        artifact_id=source_ref,
        artifact_type="source_file_ref_v0",
        case_id=context.case_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        workspace_model_id=context.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        document_id=document_id,
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
            "document_id": document_id,
            "source_file_ref": source_file_ref,
        },
        safe_metadata={"source_available": True},
    )


def _canonical_artifact(
    *, source_ref: str, normalizer_version: str
) -> dict:
    return CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version=normalizer_version)
    ).create().build(
        tenant_id="doc27-user",
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": SOURCE_SHA256,
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "pdf_text_layer_projection": {
                    "page_inventory": [{"page_number": 1}],
                    "line_inventory": [],
                },
            }
        ],
        source_units=[
            {
                "unit_ref": "doc27-table-unit",
                "source_location": {"page": 1, "line_start": 1},
                "text": "Header A Header B 1 2",
            },
            {
                "unit_ref": "doc27-text-unit",
                "source_location": {"page": 1, "line_start": 2},
                "text": "Visible sealed fixture text",
            },
        ],
        table_projections=[
            {
                "projection_status": "ready",
                "table_projection_id": "doc27-table",
                "source_unit_ref": "doc27-table-unit",
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


def _publish(
    root: Path,
    *,
    activate: bool = True,
    force_chunked: bool = False,
):
    store = _store(root)
    context = _context()
    document_id = "doc27-document"
    source = store.put_record(
        _source_record(context=context, document_id=document_id)
    )
    artifact = _canonical_artifact(
        source_ref=source.artifact_id,
        normalizer_version="doc27-consumer-v1",
    )
    published = CanonicalArtifactStoreFactory(
        store=store,
        config=(
            CanonicalStorageConfig(small_payload_max_bytes=1)
            if force_chunked
            else CanonicalStorageConfig()
        ),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
        compare_receipt=None,
    )
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    if activate:
        reader.activate(
            canonical_version_id=published.canonical_version_id,
            expected_previous_version_id=None,
            context=context,
            actor="doc27-test",
            reason="sealed Wave 0 fixture",
        )
    return store, context, document_id, artifact, published


def test_01_frozen_inventory_accounts_all_13_surviving_surfaces_once() -> None:
    assert len(FROZEN_CONSUMER_SURFACES) == 13
    assert len({item.consumer_id for item in FROZEN_CONSUMER_SURFACES}) == 13
    assert len({item.source_file for item in FROZEN_CONSUMER_SURFACES}) == 13
    assert all(item.consumer_class != "UNRESOLVED" for item in FROZEN_CONSUMER_SURFACES)
    assert sum(item.consumer_class == "WAVE_0_TEST" for item in FROZEN_CONSUMER_SURFACES) == 1
    assert sum(item.consumer_class == "WAVE_0_RESEARCH" for item in FROZEN_CONSUMER_SURFACES) == 0
    assert sum(item.consumer_class == "WAVE_1_INTERNAL_READ_ONLY" for item in FROZEN_CONSUMER_SURFACES) == 0
    assert sum(
        item.legacy_status
        == "DEPRECATED_FOR_CONSUMER_READ_RETAINED_FOR_REGRESSION"
        for item in FROZEN_CONSUMER_SURFACES
    ) == 1
    assert not any(
        item.consumer_class == "WAVE_3_PRIMARY_PRODUCT"
        and item.migration_wave.startswith("WAVE_0")
        for item in FROZEN_CONSUMER_SURFACES
    )
    for item in FROZEN_CONSUMER_SURFACES:
        assert (SERVICE_ROOT / item.source_file).is_file()


def test_02_wave0_mappings_are_explicit_versioned_and_consumer_specific() -> None:
    assert len(WAVE0_MAPPINGS) == 1
    assert len({item.feature_flag for item in WAVE0_MAPPINGS}) == 1
    assert all(item.feature_flag.startswith("CANONICAL_READ_") for item in WAVE0_MAPPINGS)
    assert all(item.canonical_contract_version == "canonical_artifact_v1" for item in WAVE0_MAPPINGS)
    versions = {
        item.consumer_id: (
            item.compatibility_adapter_version,
            item.output_contract_version,
        )
        for item in WAVE0_MAPPINGS
    }
    assert versions == {
        "gate1_artifact_store_test": (
            "gate1_artifact_store_canonical_adapter_v1",
            "gate1_artifact_store_compatibility_output_v1",
        )
    }
    assert all("read_active_envelope" in item.canonical_queries for item in WAVE0_MAPPINGS)


@pytest.mark.parametrize("force_chunked", (False, True))
def test_03_surviving_wave0_adapter_reads_single_and_chunked_active_artifacts(
    force_chunked: bool,
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        store, context, document_id, _, _ = _publish(
            Path(temp_dir), force_chunked=force_chunked
        )
        ledger = CanonicalReadLedger()
        result = Gate1ArtifactStoreCanonicalAdapterFactory(
            store=store, enabled=True, ledger=ledger
        ).create().read_active(document_id=document_id, context=context)
        assert result.compatibility_status == CANONICAL_OK
        assert result.error_code is None
        assert result.output
        assert result.output["documents_returned"] == 1
        assert result.output["tables_returned"] == 1
        assert result.output["provenance_available"] is True
        assert result.telemetry["canonical_read_attempts"] == 1
        assert result.telemetry["canonical_read_success"] == 1
        assert result.telemetry["canonical_read_blocked"] == 0
        assert result.telemetry["canonical_chunks_read"] >= 1
        assert len(result.telemetry["canonical_version_id_hash"]) == 64
        assert len(ledger.events) == 1


def test_04_flag_off_and_missing_active_are_explicit_without_fallback() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        store, context, document_id, _, _ = _publish(Path(temp_dir))
        ledger = CanonicalReadLedger()
        disabled = Gate1ArtifactStoreCanonicalAdapterFactory(
            store=store, enabled=False, ledger=ledger
        ).create().read_active(document_id=document_id, context=context)
        assert disabled.compatibility_status == CANONICAL_INCOMPLETE
        assert disabled.error_code == "canonical_read_disabled"
        assert disabled.output is None
        ledger.record_rollback(
            consumer_id=disabled.consumer_id,
            migration_wave=disabled.migration_wave,
        )
        assert sum(item["rollback_events"] for item in ledger.events) == 1

    with tempfile.TemporaryDirectory() as temp_dir:
        store, context, document_id, _, _ = _publish(
            Path(temp_dir), activate=False
        )
        missing = Gate1ArtifactStoreCanonicalAdapterFactory(
            store=store, enabled=True
        ).create().read_active(document_id=document_id, context=context)
        assert missing.compatibility_status == CANONICAL_INCOMPLETE
        assert missing.error_code == "canonical_version_not_active"
        assert missing.output is None


def test_05_access_is_fail_closed_and_emits_no_identity() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        store, _, document_id, _, _ = _publish(Path(temp_dir))
        other = ArtifactAccessContext(
            user_id="other-user",
            normalization_run_id="other-run",
            case_id="doc27-case",
            workspace_model_id="doc27-workspace",
            allow_private=True,
            require_source_available=True,
        )
        result = Gate1ArtifactStoreCanonicalAdapterFactory(
            store=store, enabled=True
        ).create().read_active(document_id=document_id, context=other)
        assert result.compatibility_status in {
            CANONICAL_ACCESS_DENIED,
            CANONICAL_INCOMPLETE,
        }
        assert result.output is None
        rendered = json.dumps(result.telemetry, sort_keys=True)
        assert "doc27-user" not in rendered
        assert "other-user" not in rendered
        assert "doc27-case" not in rendered


def test_06_schema_provenance_and_critical_conflict_classification() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, _, artifact, _ = _publish(Path(temp_dir))
        unsupported = copy.deepcopy(artifact)
        unsupported["schema_version"] = "canonical_artifact_v999"
        assert classify_consumer_artifact(unsupported) == (
            CANONICAL_VERSION_UNSUPPORTED,
            "canonical_schema_version_unsupported",
        )
        unresolved = copy.deepcopy(artifact)
        unresolved["nodes"][0]["source_refs"] = ["prov_missing"]
        assert classify_consumer_artifact(unresolved) == (
            CANONICAL_INCOMPLETE,
            "canonical_provenance_unresolved",
        )
        conflict = copy.deepcopy(artifact)
        conflict["issues"].append(
            {
                "issue_id": "issue-critical",
                "issue_type": "CONFLICT",
                "severity": "critical",
                "source_refs": [artifact["provenance"][0]["provenance_id"]],
                "evidence_refs": [],
                "summary": "terminally classified fixture conflict",
            }
        )
        assert classify_consumer_artifact(conflict) == (
            CANONICAL_CONFLICT,
            "canonical_critical_conflict",
        )


def test_07_active_pointer_cas_version_and_flag_rollbacks_are_independent() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store, context, document_id, _, first = _publish(root)
        run2_context = _context("doc27-run-2")
        source_ref = store.put_record(
            _source_record(context=run2_context, document_id=document_id)
        ).artifact_id
        second = CanonicalArtifactStoreFactory(store=store).create().put_candidate(
            artifact=_canonical_artifact(
                source_ref=source_ref,
                normalizer_version="doc27-consumer-v2",
            ),
            context=run2_context,
            retention_policy=build_retention_policy(mode="api_smoke"),
            compare_receipt=None,
        )
        reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
        with pytest.raises(ArtifactStoreError) as stale:
            reader.activate(
                canonical_version_id=second.canonical_version_id,
                expected_previous_version_id="canver_stale",
                context=run2_context,
                actor="doc27-test",
                reason="stale candidate rejection",
            )
        assert stale.value.code == "canonical_pointer_conflict"
        assert reader.read_active(document_id, context)["normalizer_version"] == "doc27-consumer-v1"
        reader.activate(
            canonical_version_id=second.canonical_version_id,
            expected_previous_version_id=first.canonical_version_id,
            context=run2_context,
            actor="doc27-test",
            reason="cohort promotion",
        )
        assert reader.read_active(document_id, context)["normalizer_version"] == "doc27-consumer-v2"
        disabled = Gate1ArtifactStoreCanonicalAdapterFactory(
            store=store, enabled=False
        ).create().read_active(document_id=document_id, context=context)
        assert disabled.error_code == "canonical_read_disabled"
        assert reader.read_active(document_id, context)["normalizer_version"] == "doc27-consumer-v2"
        reader.rollback(
            target_version_id=first.canonical_version_id,
            expected_current_version_id=second.canonical_version_id,
            context=context,
            actor="doc27-test",
            reason="cohort rollback",
        )
        assert reader.read_active(document_id, context)["normalizer_version"] == "doc27-consumer-v1"


def test_08_factory_and_closed_world_guards_are_declared() -> None:
    source = (
        SERVICE_ROOT / "broker_reports_gate1/canonical_consumer_migration.py"
    ).read_text(encoding="utf-8")
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
    assert "CanonicalReaderFactory(" in source
    assert "sqlite3" not in source
    assert "payload_root" not in source
    assert "legacy fallback" in source.lower()
    assert "openai" not in source.lower()
    assert "anthropic" not in source.lower()
    assert "gate3" not in source.lower()


def test_09_inventory_serialization_contains_no_unresolved_or_private_values() -> None:
    rendered = json.dumps(
        [asdict(item) for item in FROZEN_CONSUMER_SURFACES],
        ensure_ascii=True,
        sort_keys=True,
    )
    assert '"consumer_class": "UNRESOLVED"' not in rendered
    assert "raw provider payload" not in rendered.lower()
    assert "absolute_path" not in rendered
    assert "tenant_id" not in rendered
    assert str(REPO_ROOT).lower() not in rendered.lower()


def test_10_surviving_wave0_consumer_observable_shadow_has_no_regression() -> None:
    expected_common = {
        "documents_returned": 1,
        "tables_returned": 1,
        "provenance_available": True,
        "issues_total": 0,
        "conflicts_total": 0,
        "ambiguities_total": 0,
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        store, context, document_id, _, _ = _publish(Path(temp_dir))
        comparisons = []
        result = Gate1ArtifactStoreCanonicalAdapterFactory(
            store=store, enabled=True
        ).create().read_active(document_id=document_id, context=context)
        assert result.compatibility_status == CANONICAL_OK
        observed = {key: result.output[key] for key in expected_common}
        comparisons.append(
            {
                "consumer_id": result.consumer_id,
                "observable_behavior": (
                    "EQUIVALENT"
                    if observed == expected_common
                    else "CANONICAL_REGRESSION"
                ),
                "schema_difference": "EXPECTED_SCHEMA_DIFFERENCE",
            }
        )

    assert len(comparisons) == 1
    assert all(
        item["observable_behavior"] == "EQUIVALENT"
        for item in comparisons
    )
    assert not any(
        item["observable_behavior"] in {"AMBIGUOUS", "UNRESOLVED"}
        for item in comparisons
    )


def test_12_deleted_source_and_cross_tenant_candidate_activation_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store, context, document_id, _, first = _publish(root)
        run2_context = _context("doc27-run-deleted-candidate")
        source_ref = store.put_record(
            _source_record(context=run2_context, document_id=document_id)
        ).artifact_id
        second = CanonicalArtifactStoreFactory(store=store).create().put_candidate(
            artifact=_canonical_artifact(
                source_ref=source_ref,
                normalizer_version="doc27-deleted-candidate-v2",
            ),
            context=run2_context,
            retention_policy=build_retention_policy(mode="api_smoke"),
            compare_receipt=None,
        )
        reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
        other = ArtifactAccessContext(
            user_id="other-user",
            normalization_run_id="other-run",
            case_id=context.case_id,
            workspace_model_id=context.workspace_model_id,
            allow_private=True,
            require_source_available=True,
        )
        with pytest.raises(ArtifactStoreError) as cross_tenant:
            reader.activate(
                canonical_version_id=second.canonical_version_id,
                expected_previous_version_id=first.canonical_version_id,
                context=other,
                actor="doc27-test",
                reason="cross-tenant candidate rejection",
            )
        assert cross_tenant.value.code == "artifact_access_denied"
        assert (
            store.get_active_canonical_version(
                context=context,
                document_id=document_id,
            ).canonical_version_id
            == first.canonical_version_id
        )

        deleted_context = ArtifactAccessContext(
            user_id=context.user_id,
            normalization_run_id=context.normalization_run_id,
            case_id=context.case_id,
            workspace_model_id=context.workspace_model_id,
            source_file_id=document_id,
            allow_private=True,
            require_source_available=True,
        )
        store.mark_source_file_deleted(deleted_context)
        with pytest.raises(ArtifactStoreError) as deleted:
            reader.activate(
                canonical_version_id=second.canonical_version_id,
                expected_previous_version_id=first.canonical_version_id,
                context=run2_context,
                actor="doc27-test",
                reason="deleted-source candidate rejection",
            )
        assert deleted.value.code == "canonical_pointer_conflict"
        assert (
            store.get_canonical_version(
                context=run2_context,
                canonical_version_id=second.canonical_version_id,
            ).status
            != "ACTIVE"
        )
