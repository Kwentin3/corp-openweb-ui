from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    Gate3FinancialAnnotationsPersistenceFactory,
    Gate3NdflCaseReadinessFactory,
    Gate3StructuralChunkFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord, ArtifactStoreError
from broker_reports_gate1.gate3_financial_annotations_persistence import (
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
)
from broker_reports_gate1.gate3_ndfl_case_readiness import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)


MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE_ID = "google_gemini"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_GATE3_NDFL_CASE_READINESS.v1.schema.json"
)


def test_empty_case_is_deterministic_and_gate4_fails_closed(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    factory = Gate3NdflCaseReadinessFactory(store=store, read_enabled=True)

    first = factory.create(context=context)
    second = factory.create(context=context)

    assert first == second
    assert first["case_status"] == "empty"
    assert first["summary"] == {
        "documents_total": 0,
        "gate2_ready_documents": 0,
        "gate3_ready_documents": 0,
        "gate4_handoff_ready": False,
    }
    assert _action(first, "PREPARE_DECLARATION") == {
        "action_id": "PREPARE_DECLARATION",
        "allowed": False,
        "reason_code": "GATE3_CASE_NOT_READY",
    }
    _validator().validate(first)


@pytest.mark.parametrize("documents_total", [1, 3])
def test_one_or_many_complete_documents_are_ready(
    tmp_path: Path, documents_total: int
) -> None:
    store, context = _store_and_context(tmp_path)
    for index in range(documents_total):
        document_id = f"document-{index}"
        _publish_canonical(store, context, document_id, revision=1)
        _save_annotations(
            store,
            context,
            document_id,
            annotations_total=0 if index == documents_total - 1 else 1,
        )

    state = Gate3NdflCaseReadinessFactory(
        store=store, read_enabled=True
    ).create(context=context)

    assert state["case_status"] == "ready_for_gate4_handoff"
    assert state["summary"] == {
        "documents_total": documents_total,
        "gate2_ready_documents": documents_total,
        "gate3_ready_documents": documents_total,
        "gate4_handoff_ready": True,
    }
    assert _action(state, "PREPARE_DECLARATION")["allowed"] is True
    assert state["documents"][-1]["annotations_total"] == 0
    _validator().validate(state)


def test_partial_case_and_gate2_ready_gate3_missing_are_explicit(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    _publish_canonical(store, context, "ready-document", revision=1)
    _save_annotations(store, context, "ready-document")
    _publish_canonical(store, context, "missing-document", revision=1)

    state = Gate3NdflCaseReadinessFactory(
        store=store, read_enabled=True
    ).create(context=context)

    assert state["case_status"] == "gate3_incomplete"
    assert state["summary"] == {
        "documents_total": 2,
        "gate2_ready_documents": 2,
        "gate3_ready_documents": 1,
        "gate4_handoff_ready": False,
    }
    missing = next(
        item
        for item in state["documents"]
        if item["document_id"] == "missing-document"
    )
    assert missing["reason_codes"] == ["GATE3_ANNOTATIONS_MISSING"]
    assert _action(state, "PROCESS_REMAINING_DOCUMENT")["allowed"] is True
    assert _action(state, "PREPARE_DECLARATION")["allowed"] is False


def test_noncanonical_document_and_incomplete_sidecar_fail_closed(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "unprocessed-document"
    _put_source(store, context, document_id, revision=1)
    store.put_record(
        ArtifactRecord(
            artifact_id="blocked-annotations",
            artifact_type=GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=None,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=build_retention_policy(mode="api_smoke"),
            access_policy={"requires_user_id": True},
            validation_status="blocked",
            lifecycle_status="blocked",
            payload={"incomplete": True},
        )
    )

    state = Gate3NdflCaseReadinessFactory(
        store=store, read_enabled=True
    ).create(context=context)
    document = state["documents"][0]

    assert state["case_status"] == "gate2_incomplete"
    assert document["gate2_ready"] is False
    assert document["gate3_ready"] is False
    assert document["incomplete_annotation_candidates_total"] == 1
    assert document["reason_codes"] == [
        "GATE2_CANONICAL_MISSING",
        "GATE3_ANNOTATIONS_INCOMPLETE",
    ]


def test_new_canonical_version_makes_old_annotations_stale(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "reprocessed-document"
    first = _publish_canonical(store, context, document_id, revision=1)
    _save_annotations(store, context, document_id)
    next_context = replace(context, normalization_run_id="case-run-2")
    second = _publish_canonical(
        store,
        next_context,
        document_id,
        revision=2,
        expected_previous_version_id=first.canonical_version_id,
    )

    state = Gate3NdflCaseReadinessFactory(
        store=store, read_enabled=True
    ).create(context=context)
    document = state["documents"][0]

    assert document["current_canonical_version_id"] == second.canonical_version_id
    assert document["gate2_ready"] is True
    assert document["gate3_ready"] is False
    assert document["stale_annotation_candidates_total"] == 1
    assert document["reason_codes"] == [
        "GATE3_ANNOTATIONS_MISSING",
        "GATE3_ANNOTATIONS_STALE",
    ]


def test_relabel_is_side_by_side_and_latest_current_sidecar_is_selected(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "relabel-document"
    _publish_canonical(store, context, document_id, revision=1)
    first = _save_annotations(store, context, document_id)
    second = _save_annotations(store, context, document_id, financial_label="TAX_WITHHELD")
    expected = max((first, second), key=lambda record: (record.created_at, record.artifact_id))

    state = Gate3NdflCaseReadinessFactory(
        store=store, read_enabled=True
    ).create(context=context)
    document = state["documents"][0]

    assert document["gate3_ready"] is True
    assert document["annotation_candidates_total"] == 2
    assert document["selected_annotations_artifact_id"] == expected.artifact_id


def test_access_scope_and_no_persisted_or_model_owned_state(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    _publish_canonical(store, context, "private-document", revision=1)
    _save_annotations(store, context, "private-document")
    factory = Gate3NdflCaseReadinessFactory(store=store, read_enabled=True)

    with pytest.raises(ArtifactStoreError) as denied:
        factory.create(context=replace(context, allow_private=False))
    assert denied.value.code == "artifact_access_denied"

    foreign = factory.create(context=replace(context, user_id="foreign-user"))
    assert foreign["case_status"] == "empty"
    assert foreign["documents"] == []

    source = (
        Path(__file__).resolve().parents[1]
        / "broker_reports_gate1"
        / "gate3_ndfl_case_readiness.py"
    ).read_text(encoding="utf-8")
    assert "Gate3NdflCaseReadinessFactory.create" in FACTORY_REQUIRED
    assert "must not persist" in FORBIDDEN
    assert "list_by_case_context" in (
        Path(__file__).resolve().parents[1]
        / "broker_reports_gate1"
        / "artifact_resolver.py"
    ).read_text(encoding="utf-8")
    assert "put_record(" not in source
    assert "import sqlite" not in source
    assert "model_client" not in source
    assert "provider_adapter" not in source


def _store_and_context(tmp_path: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="case-user",
        normalization_run_id="case-run-1",
        case_id="ndfl-case",
        workspace_model_id="broker-reports-workspace",
        allow_private=True,
    )
    return store, context


def _put_source(store, context, document_id: str, revision: int) -> str:
    source_ref = f"source-{document_id}-{revision}"
    store.put_record(
        ArtifactRecord(
            artifact_id=source_ref,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=None,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={"openwebui_file_id": f"synthetic-{document_id}"},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=build_retention_policy(mode="api_smoke"),
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload={"synthetic": True, "revision": revision},
        )
    )
    return source_ref


def _publish_canonical(
    store,
    context,
    document_id: str,
    *,
    revision: int,
    expected_previous_version_id: str | None = None,
):
    source_ref = _put_source(store, context, document_id, revision)
    content = f"Broker fee {revision}.00 for {document_id}"
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version=f"g3-readiness-test-v{revision}")
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=revision,
        document={
            "container_format": "html_text",
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "declared_mime_type": "text/html",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "blocks": [
                        {
                            "kind": "text",
                            "text": content,
                            "source_location": {"block_index": 1},
                        }
                    ]
                }
            }
        ],
        source_units=[],
        table_projections=[],
    )
    retention = build_retention_policy(mode="api_smoke")
    canonical = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=canonical.canonical_version_id,
        expected_previous_version_id=expected_previous_version_id,
        context=context,
        actor="g3-readiness-test",
        reason="G3.6 readiness test",
    )
    return canonical


def _save_annotations(
    store,
    context,
    document_id: str,
    *,
    annotations_total: int = 1,
    financial_label: str = "TRANSACTION_CHARGE",
):
    chunk_set = Gate3StructuralChunkFactory(
        store=store, read_enabled=True
    ).create(document_id=document_id, context=context)
    ordinals = [int(chunk["ordinal"]) for chunk in chunk_set["chunks"]]
    target = copy.deepcopy(
        chunk_set["chunks"][0]["target_mappings"][0]["canonical_target"]
    )
    annotations = (
        [{"target": target, "financial_label": financial_label}]
        if annotations_total
        else []
    )
    result = {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "selected_chunk_ordinals": ordinals,
        "selection_mode": "full_document",
        "document_status": "complete",
        "metrics": {
            "chunks_total": len(ordinals),
            "chunks_validated": len(ordinals),
            "chunks_rejected": 0,
            "chunks_provider_failed": 0,
            "annotations_validated": len(annotations),
        },
        "merged_output": {
            "schema_version": "broker_reports_financial_annotations_v1",
            "canonical_binding": copy.deepcopy(chunk_set["canonical_binding"]),
            "dictionary_identity": {
                "dictionary_id": "broker-reports-financial-labels",
                "semantic_version": "1.0.0",
            },
            "instruction_identity": {
                "instruction_id": "broker-reports-bounded-semantic-labeling",
                "semantic_version": "1.0.1",
            },
            "model_identity": {"model_id": MODEL_ID},
            "annotations": annotations,
            "validation_status": "validated",
        },
    }
    return Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create().save(
        document_id=document_id,
        context=context,
        validated_document_result=result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )


def _action(state: dict, action_id: str) -> dict:
    return next(
        item for item in state["follow_up_actions"] if item["action_id"] == action_id
    )


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)
