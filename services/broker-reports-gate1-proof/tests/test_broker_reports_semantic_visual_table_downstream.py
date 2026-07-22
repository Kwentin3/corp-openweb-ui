from __future__ import annotations

import copy

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate2InputReadinessConfig,
    Gate2InputReadinessFactory,
    build_retention_policy,
    persist_gate1_result,
)
from broker_reports_gate1.pdf_dual_vlm_runtime import (
    PdfDualVlmRuntimeConfig,
    PdfDualVlmRuntimeFactory,
    sha256_json,
)
from broker_reports_gate1.semantic_visual_table_migration import (
    SemanticVisualTableMigrationConfig,
    SemanticVisualTableMigrationFactory,
)
from tests.test_broker_reports_pdf_text_layer_slice1 import _pdf_bytes
from tests.test_broker_reports_semantic_visual_table_materialization import (
    _Provider,
    _candidate,
)


def test_semantic_projection_requires_explicit_gate2_boundary_and_preserves_source_units(
    tmp_path,
) -> None:
    pdf_bytes = _pdf_bytes(
        pages=[
            (
                "text",
                [
                    "Synthetic Broker Report",
                    "Cash 1,000 USD",
                    "Total 1,000 USD",
                ],
            )
        ]
    )
    normalized = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="semantic-downstream-pdf",
                filename="semantic_downstream.pdf",
                content=pdf_bytes,
                mime_type="application/pdf",
            )
        ],
        input_context={
            "clarification_criticality_refinement_enabled": True,
            "pdf_layout_slice2_enabled": False,
        },
    )
    document = normalized.package["document_inventory"]["documents"][0]
    migrated = _migration_for_document(
        document_ref=document["document_id"],
        source_sha256=document["sha256"],
    )
    normalized.package["semantic_visual_table_migration"] = (
        migrated.safe_summary
    )
    normalized.package["private_semantic_visual_table_envelopes"] = (
        migrated.private_envelopes
    )
    normalized.package["private_semantic_visual_table_projections"] = (
        migrated.gate2_projections
    )

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="semantic-downstream-user",
        normalization_run_id=normalized.package["normalization_run"]["run_id"],
        case_id="semantic-downstream-case",
        chat_id="semantic-downstream-chat",
        workspace_model_id="semantic-downstream-model",
        allow_private=True,
        require_source_available=True,
    )
    manifest = persist_gate1_result(
        store=store,
        result=normalized,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
    )
    dcp_ref = manifest.artifact_refs_by_type["domain_context_packet_v0"][0]

    artifact_types = {record.artifact_type for record in store.list_by_run(
        context.normalization_run_id
    )}
    assert "private_normalized_source_unit_v0" in artifact_types
    assert "broker_reports_semantic_visual_table_envelope_v1" in artifact_types
    assert "broker_reports_normalized_table_projection_v0" in artifact_types
    assert "broker_reports_semantic_visual_table_migration_policy_v1" in artifact_types

    default_readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
        domain_context_packet_ref=dcp_ref,
        context=context,
    )
    assert default_readiness.validation["validator_status"] == "passed"
    assert default_readiness.validation["slice_audit"][
        "semantic_visual_projections_selected_total"
    ] == 0
    assert not _semantic_packages(default_readiness.packages)

    enabled_readiness = Gate2InputReadinessFactory(
        store=store,
        config=Gate2InputReadinessConfig(
            allow_standalone_semantic_visual_projections=True
        ),
    ).create().audit_and_build(
        domain_context_packet_ref=dcp_ref,
        context=context,
    )
    assert enabled_readiness.validation["validator_status"] == "passed"
    assert enabled_readiness.validation["slice_audit"][
        "semantic_visual_projections_selected_total"
    ] == 1, {
        key: enabled_readiness.validation["slice_audit"].get(key)
        for key in (
            "table_projections_total",
            "table_projections_eligible_total",
            "table_projection_full_validation_total",
            "table_projections_unselected_total",
            "selected_scope_counts",
            "unselected_scope_reason_counts",
            "standalone_semantic_visual_projections_allowed",
        )
    }
    assert len(_semantic_packages(enabled_readiness.packages)) == 1
    assert len(enabled_readiness.packages) > len(default_readiness.packages)


def test_duplicate_semantic_projection_identity_fails_closed(tmp_path) -> None:
    normalized = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="semantic-duplicate-pdf",
                filename="semantic_duplicate.pdf",
                content=_pdf_bytes(pages=[("text", ["Amount 10 USD"])]),
                mime_type="application/pdf",
            )
        ],
        input_context={"pdf_layout_slice2_enabled": False},
    )
    document = normalized.package["document_inventory"]["documents"][0]
    migrated = _migration_for_document(
        document_ref=document["document_id"],
        source_sha256=document["sha256"],
    )
    normalized.package["semantic_visual_table_migration"] = migrated.safe_summary
    normalized.package["private_semantic_visual_table_envelopes"] = (
        migrated.private_envelopes
    )
    normalized.package["private_semantic_visual_table_projections"] = [
        copy.deepcopy(migrated.gate2_projections[0]),
        copy.deepcopy(migrated.gate2_projections[0]),
    ]
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "duplicates.sqlite3",
            payload_root=tmp_path / "duplicate-payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="semantic-duplicate-user",
        normalization_run_id=normalized.package["normalization_run"]["run_id"],
        case_id="semantic-duplicate-case",
        chat_id="semantic-duplicate-chat",
        workspace_model_id="semantic-duplicate-model",
        allow_private=True,
        require_source_available=True,
    )

    try:
        persist_gate1_result(
            store=store,
            result=normalized,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
        )
    except ValueError as exc:
        assert str(exc) == "duplicate_table_projection_identity"
    else:
        raise AssertionError("duplicate semantic projection was persisted")
    assert store.list_by_run(context.normalization_run_id) == []


def _migration_for_document(*, document_ref: str, source_sha256: str):
    candidate = _candidate()
    manifest = candidate["manifest"]
    manifest.pop("manifest_hash")
    manifest["document_ref"] = document_ref
    manifest["pdf_sha256"] = source_sha256
    manifest["manifest_hash"] = sha256_json(manifest)
    runtime = PdfDualVlmRuntimeFactory(
        PdfDualVlmRuntimeConfig(enabled=True)
    ).create_with_providers(
        gemini=_Provider(
            [["Item", "Amount"], ["Cash", "1,000"], ["Total", "1,000"]]
        )
    ).run([candidate])
    return SemanticVisualTableMigrationFactory(
        SemanticVisualTableMigrationConfig(enabled=True)
    ).create().migrate(
        decisions=runtime.private_decisions,
        provider_evidence=runtime.private_provider_evidence,
    )


def _semantic_packages(packages):
    return [
        package
        for package in packages
        if (package.get("upstream_source_representation") or {}).get(
            "source_representation_kind"
        )
        == "semantic_visual_logical_table"
    ]
