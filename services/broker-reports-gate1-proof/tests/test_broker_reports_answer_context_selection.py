from __future__ import annotations

import copy

import pytest

from broker_reports_gate1 import (
    AnswerContextSelectionError,
    AnswerContextSelectionFactory,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate2InputReadinessConfig,
    Gate2InputReadinessFactory,
    build_retention_policy,
    persist_gate1_result,
    validate_answer_context,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.gate2_domain_contracts import DOMAIN_RUN_SCHEMA_VERSION
from broker_reports_gate1.gate2_source_fact_stitching import (
    STITCH_RESULT_SCHEMA_VERSION,
)
from broker_reports_gate1.gate2_source_unit_segmentation import (
    DERIVED_SOURCE_UNIT_SCHEMA_VERSION,
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


def test_semantic_scope_selects_one_interpretation_and_keeps_source_as_provenance(
    tmp_path,
) -> None:
    normalized = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="answer-context-semantic-pdf",
                filename="answer_context_semantic.pdf",
                content=_pdf_bytes(
                    pages=[("text", ["Synthetic Broker Report", "Total 1,000 USD"])]
                ),
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
        user_id="answer-context-user",
        normalization_run_id=normalized.package["normalization_run"]["run_id"],
        case_id="answer-context-case",
        chat_id="answer-context-chat",
        workspace_model_id="answer-context-model",
        allow_private=True,
        require_source_available=True,
    )
    retention = build_retention_policy(mode="api_smoke")
    manifest = persist_gate1_result(
        store=store,
        result=normalized,
        context=context,
        retention_policy=retention,
        source_file_refs=[
            {
                "provider": "openwebui",
                "openwebui_file_id": "answer-context-source",
                "source_deleted": False,
            }
        ],
    )
    readiness = (
        Gate2InputReadinessFactory(
            store=store,
            config=Gate2InputReadinessConfig(
                allow_standalone_semantic_visual_projections=True
            ),
        )
        .create()
        .audit_and_build(
            domain_context_packet_ref=manifest.artifact_refs_by_type[
                "domain_context_packet_v0"
            ][0],
            context=context,
        )
    )
    semantic_package = next(
        package
        for package in readiness.packages
        if (package.get("upstream_source_representation") or {}).get(
            "source_representation_kind"
        )
        == "semantic_visual_logical_table"
    )

    derived_refs = ["art_answer_context_derived_a", "art_answer_context_derived_b"]
    for derived_ref in derived_refs:
        _put(
            store=store,
            context=context,
            retention=retention,
            artifact_id=derived_ref,
            artifact_type=DERIVED_SOURCE_UNIT_SCHEMA_VERSION,
            document_id=document["document_id"],
            visibility="private_case",
            storage_backend="project_artifact_payload",
            payload=copy.deepcopy(semantic_package),
        )
    extraction_run_ref = "art_answer_context_terminal_run"
    _put(
        store=store,
        context=context,
        retention=retention,
        artifact_id=extraction_run_ref,
        artifact_type=DOMAIN_RUN_SCHEMA_VERSION,
        document_id=None,
        visibility="safe_internal",
        storage_backend="project_artifact_store",
        payload={
            "schema_version": DOMAIN_RUN_SCHEMA_VERSION,
            "run_status": "completed",
            "derived_source_unit_refs": derived_refs,
            "domain_package_refs": [],
            "source_facts_refs": [],
        },
    )

    service = AnswerContextSelectionFactory(store=store).create()
    result = service.build_and_persist(
        extraction_run_ref=extraction_run_ref,
        context=context,
    )
    payload = service.resolve_for_answer(
        context_ref=result.context_ref,
        context=context,
    )

    assert result.selection_status == "passed"
    assert result.safe_summary["semantic_groups_total"] == 1
    assert result.safe_summary["duplicate_financial_fact_presentations_total"] == 0
    assert len(payload["evidence_groups"]) == 1
    group = payload["evidence_groups"][0]
    selected = [
        item
        for item in group["representations"]
        if item["interpretation_selection_role"] == "interpretation_bearing"
    ]
    assert len(selected) == 1
    assert selected[0]["representation_kind"] == "semantic_visual_logical_table"
    assert selected[0]["content"] == {
        "description": migrated.private_envelopes[0]["semantic_transcription"][
            "description"
        ],
        "rows": migrated.private_envelopes[0]["semantic_transcription"]["rows"],
    }
    provenance = [
        item
        for item in group["representations"]
        if item["interpretation_selection_role"] == "provenance_only"
    ]
    assert provenance
    assert all("content" not in item for item in provenance)
    assert any(item["artifact_refs"] for item in provenance)
    assert payload["selection_contract"]["answer_model_deduplication_required"] is False
    assert payload["knowledge_vector_guard"]["knowledge_rag_used"] is False

    tampered = copy.deepcopy(payload)
    tampered["evidence_groups"][0]["representations"].append(copy.deepcopy(selected[0]))
    tampered.pop("integrity_hash")
    tampered["integrity_hash"] = _integrity_hash(tampered)
    with pytest.raises(
        AnswerContextSelectionError,
        match="answer_context_interpretation_representation_count_invalid",
    ):
        validate_answer_context(tampered)

    wrong_context = ArtifactAccessContext(
        **{**context.__dict__, "user_id": "foreign-user"}
    )
    with pytest.raises(Exception, match="Artifact user context mismatch"):
        service.resolve_for_answer(
            context_ref=result.context_ref,
            context=wrong_context,
        )


def test_ordinary_scope_presents_only_stitch_owned_fact(tmp_path) -> None:
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="answer-context-user",
        normalization_run_id="answer-context-normalization",
        case_id="answer-context-case",
        chat_id="answer-context-chat",
        workspace_model_id="answer-context-model",
        allow_private=True,
        require_source_available=True,
    )
    retention = build_retention_policy(mode="api_smoke")
    unit = {
        "unit_id": "ordinary-unit",
        "document_ref": "ordinary-document",
        "page_refs": ["page-1"],
        "section_refs": [],
    }
    derived_ref = "art_answer_context_ordinary_derived"
    _put(
        store=store,
        context=context,
        retention=retention,
        artifact_id=derived_ref,
        artifact_type=DERIVED_SOURCE_UNIT_SCHEMA_VERSION,
        document_id="ordinary-document",
        visibility="private_case",
        storage_backend="project_artifact_payload",
        payload={"source_unit": copy.deepcopy(unit)},
    )
    package_refs = [
        "art_answer_context_package_owned",
        "art_answer_context_package_loser",
    ]
    fact_refs = ["art_answer_context_facts_owned", "art_answer_context_facts_loser"]
    fact_ids = ["sf_owned", "sf_unowned"]
    for package_ref in package_refs:
        _put(
            store=store,
            context=context,
            retention=retention,
            artifact_id=package_ref,
            artifact_type="broker_reports_domain_extraction_package_v0",
            document_id="ordinary-document",
            visibility="private_case",
            storage_backend="project_artifact_payload",
            payload={
                "document_ref": "ordinary-document",
                "source_unit": copy.deepcopy(unit),
            },
        )
    for package_ref, fact_ref, fact_id in zip(package_refs, fact_refs, fact_ids):
        _put(
            store=store,
            context=context,
            retention=retention,
            artifact_id=fact_ref,
            artifact_type="broker_reports_source_facts_v0",
            document_id="ordinary-document",
            visibility="private_case",
            storage_backend="project_artifact_payload",
            payload={
                "package_refs": [package_ref],
                "facts": [
                    {
                        "fact_id": fact_id,
                        "fact_type": "unknown_source_row",
                        "fact_subtype": "unknown",
                        "normalized_values": {"label": fact_id},
                        "source_location": {"page_ref": "page-1"},
                    }
                ],
            },
        )
    stitch_ref = "art_answer_context_stitch"
    _put(
        store=store,
        context=context,
        retention=retention,
        artifact_id=stitch_ref,
        artifact_type=STITCH_RESULT_SCHEMA_VERSION,
        document_id="ordinary-document",
        visibility="safe_internal",
        storage_backend="project_artifact_store",
        payload={
            "schema_version": STITCH_RESULT_SCHEMA_VERSION,
            "ownership_map": [
                {
                    "ownership_status": "unknown_source_row",
                    "owner_fact_id": "sf_owned",
                }
            ],
        },
    )
    extraction_run_ref = "art_answer_context_ordinary_run"
    _put(
        store=store,
        context=context,
        retention=retention,
        artifact_id=extraction_run_ref,
        artifact_type=DOMAIN_RUN_SCHEMA_VERSION,
        document_id=None,
        visibility="safe_internal",
        storage_backend="project_artifact_store",
        payload={
            "schema_version": DOMAIN_RUN_SCHEMA_VERSION,
            "run_status": "completed",
            "derived_source_unit_refs": [derived_ref],
            "domain_package_refs": package_refs,
            "source_facts_refs": fact_refs,
            "stitch_result_refs": [stitch_ref],
        },
    )

    service = AnswerContextSelectionFactory(store=store).create()
    result = service.build_and_persist(
        extraction_run_ref=extraction_run_ref,
        context=context,
    )
    payload = service.resolve_for_answer(
        context_ref=result.context_ref,
        context=context,
    )
    selected = [
        representation
        for group in payload["evidence_groups"]
        for representation in group["representations"]
        if representation["interpretation_selection_role"] == "interpretation_bearing"
    ]
    presented_ids = {
        fact["fact_id"]
        for representation in selected
        for fact in representation["content"].get("facts", [])
    }

    assert presented_ids == {"sf_owned"}


def _migration_for_document(*, document_ref: str, source_sha256: str):
    candidate = _candidate()
    manifest = candidate["manifest"]
    manifest.pop("manifest_hash")
    manifest["document_ref"] = document_ref
    manifest["pdf_sha256"] = source_sha256
    manifest["manifest_hash"] = sha256_json(manifest)
    runtime = (
        PdfDualVlmRuntimeFactory(PdfDualVlmRuntimeConfig(enabled=True))
        .create_with_providers(
            gemini=_Provider(
                [["Item", "Amount"], ["Cash", "1,000"], ["Total", "1,000"]]
            )
        )
        .run([candidate])
    )
    return (
        SemanticVisualTableMigrationFactory(
            SemanticVisualTableMigrationConfig(enabled=True)
        )
        .create()
        .migrate(
            decisions=runtime.private_decisions,
            provider_evidence=runtime.private_provider_evidence,
        )
    )


def _put(
    *,
    store,
    context,
    retention,
    artifact_id,
    artifact_type,
    document_id,
    visibility,
    storage_backend,
    payload,
) -> None:
    store.put_record(
        ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref=None,
            visibility=visibility,
            storage_backend=storage_backend,
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility=visibility, validation_status="validated"
            ),
            payload_kind=(
                "json_file"
                if storage_backend == "project_artifact_payload"
                else "inline_json"
            ),
            payload=payload,
            safe_metadata={},
        )
    )


def _integrity_hash(payload):
    import hashlib
    import json

    material = copy.deepcopy(payload)
    material.pop("integrity_hash", None)
    return hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
