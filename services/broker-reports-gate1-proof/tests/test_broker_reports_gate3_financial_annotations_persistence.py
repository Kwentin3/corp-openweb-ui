from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

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
    Gate3FinancialAnnotationsPersistenceError,
    Gate3FinancialAnnotationsPersistenceFactory,
    Gate3StructuralChunkFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord, ArtifactStoreError
from broker_reports_gate1.gate3_financial_annotations_persistence import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
    GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
)


MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE_ID = "google_gemini"


def test_save_read_access_binding_and_retention(tmp_path: Path) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    result = _complete_result(store, context, document_id)

    stored = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    assert stored.artifact_type == GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
    assert stored.visibility == "private_case"
    assert stored.storage_backend == "project_artifact_payload"
    assert stored.validation_status == "validated"
    assert stored.safe_metadata == {
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "document_completion_status": "complete",
        "annotations_total": 1,
    }
    payload = service.read(artifact_id=stored.artifact_id, context=context)
    assert payload == result["merged_output"]
    assert payload["canonical_binding"]["canonical_version_id"] == (
        canonical.canonical_version_id
    )
    version = store.get_active_canonical_version(
        context=context, document_id=document_id
    )
    manifest = store.get_record_unchecked(version.manifest_ref)
    assert manifest is not None
    assert stored.retention_policy == manifest.retention_policy

    denied = copy.deepcopy(context)
    object.__setattr__(denied, "user_id", "different-user")
    with pytest.raises(ArtifactStoreError) as failure:
        service.read(artifact_id=stored.artifact_id, context=denied)
    assert failure.value.code == "artifact_access_denied"


def test_sidecar_is_immutable_and_relabel_does_not_mutate_gate2(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    canonical_before = reader.read_active_envelope(document_id, context)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    first_result = _complete_result(store, context, document_id)
    first = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=first_result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    second_result = copy.deepcopy(first_result)
    second_result["merged_output"]["annotations"][0][
        "financial_label"
    ] = "TAX_WITHHELD"
    second = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=second_result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    assert first.artifact_id != second.artifact_id
    assert service.read(artifact_id=first.artifact_id, context=context) == (
        first_result["merged_output"]
    )
    assert service.read(artifact_id=second.artifact_id, context=context) == (
        second_result["merged_output"]
    )
    mutated = copy.deepcopy(first)
    mutated.payload = copy.deepcopy(second_result["merged_output"])
    with pytest.raises(ArtifactStoreError) as immutable:
        store.put_record(mutated)
    assert immutable.value.code == "artifact_immutable"
    canonical_after = reader.read_active_envelope(document_id, context)
    assert canonical_after.canonical_version_id == canonical_before.canonical_version_id
    assert canonical_after.canonical_root_sha256 == canonical_before.canonical_root_sha256


def test_historical_v1_sidecar_remains_readable(tmp_path: Path) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    current = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=_complete_result(store, context, document_id),
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    current_payload = service.read(
        artifact_id=current.artifact_id,
        context=context,
    )
    historical_payload = {
        key: copy.deepcopy(value)
        for key, value in current_payload.items()
        if key not in {"role_pack_identity", "role_instruction_identity"}
    }
    historical_payload["schema_version"] = (
        GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
    )
    historical_payload["annotations"] = [
        {
            "target": copy.deepcopy(annotation["target"]),
            "financial_label": annotation["financial_label"],
        }
        for annotation in current_payload["annotations"]
    ]
    historical = copy.deepcopy(current)
    historical.artifact_id = "historical-financial-annotations-v1"
    historical.artifact_type = (
        GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
    )
    historical.payload = historical_payload
    historical.safe_metadata = copy.deepcopy(current.safe_metadata)
    stored = store.put_record(historical)

    assert service.read(artifact_id=stored.artifact_id, context=context) == (
        historical_payload
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            lambda value: value.update(document_status="incomplete"),
            "gate3_annotations_document_result_incomplete",
        ),
        (
            lambda value: value["merged_output"]["canonical_binding"].update(
                canonical_version_id="wrong-version"
            ),
            "gate3_annotations_canonical_binding_mismatch",
        ),
        (
            lambda value: value["merged_output"]["dictionary_identity"].update(
                dictionary_id="second-dictionary"
            ),
            "gate3_annotations_dictionary_identity_mismatch",
        ),
        (
            lambda value: value["merged_output"]["role_pack_identity"].update(
                role_pack_id="second-role-pack"
            ),
            "gate3_annotations_role_pack_identity_mismatch",
        ),
        (
            lambda value: value["merged_output"]["instruction_identity"].update(
                semantic_version="9.9.9"
            ),
            "gate3_annotations_payload_contract_invalid",
        ),
        (
            lambda value: value["merged_output"]["model_identity"].update(
                model_id="unapproved-model"
            ),
            "gate3_annotations_model_identity_mismatch",
        ),
        (
            lambda value: value["merged_output"]["annotations"][0].update(
                target={"kind": "node", "node_id": "missing-node"}
            ),
            "gate3_annotations_target_unknown",
        ),
        (
            lambda value: value["merged_output"]["annotations"][0]["roles"][
                1
            ].update(target={"kind": "node", "node_id": "missing-node"}),
            "gate3_annotations_role_target_unknown",
        ),
        (
            lambda value: value["merged_output"]["annotations"][0]["roles"][
                1
            ].update(exact_text="12,00"),
            "gate3_role_exact_text_not_literal_substring",
        ),
        (
            lambda value: value["merged_output"]["annotations"][0][
                "roles"
            ].pop(),
            "gate3_annotations_role_cardinality_invalid",
        ),
    ],
)
def test_incomplete_or_misbound_result_fails_closed(
    tmp_path: Path, mutation, expected_code: str
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    result = _complete_result(store, context, document_id)
    mutation(result)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()

    with pytest.raises(Gate3FinancialAnnotationsPersistenceError) as failure:
        service.save(
            document_id=document_id,
            context=context,
            validated_document_result=result,
            provider_profile_id=PROVIDER_PROFILE_ID,
        )
    assert failure.value.code == expected_code


def test_existing_case_purge_removes_sidecar_payload(tmp_path: Path) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    stored = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=_complete_result(store, context, document_id),
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    purge = store.purge_case(context)
    assert stored.artifact_id in purge.artifact_ids
    with pytest.raises(ArtifactStoreError) as failure:
        service.read(artifact_id=stored.artifact_id, context=context)
    assert failure.value.code == "artifact_purged"


def test_factory_and_no_second_store_guards() -> None:
    assert "Gate3FinancialAnnotationsPersistenceFactory.create" in FACTORY_REQUIRED
    assert "ArtifactStore" in FACTORY_REQUIRED
    assert "incomplete" in FORBIDDEN
    source = (
        Path(__file__).resolve().parents[1]
        / "broker_reports_gate1"
        / "gate3_financial_annotations_persistence.py"
    ).read_text(encoding="utf-8")
    assert "import sqlite" not in source
    assert "ArtifactStoreFactory(" not in source
    assert "ArtifactResolver" in source


def _setup(tmp_path: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="g3-persistence-user",
        normalization_run_id="g3-persistence-run",
        case_id="g3-persistence-case",
        workspace_model_id="g3-persistence-workspace",
        allow_private=True,
    )
    document_id = "g3-persistence-document"
    retention = build_retention_policy(mode="api_smoke")
    source_ref = "g3-persistence-source"
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
            source_file_ref={"openwebui_file_id": "synthetic-file"},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload={"synthetic": True},
        )
    )
    normalizer = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="g3-persistence-test-v1")
    ).create()
    artifact = normalizer.build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "html_text",
            "sha256": hashlib.sha256(b"g3-persistence").hexdigest(),
            "declared_mime_type": "text/html",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "blocks": [
                        {
                            "kind": "text",
                            "text": "Broker fee 12.00",
                            "source_location": {"block_index": 1},
                        }
                    ]
                }
            }
        ],
        source_units=[],
        table_projections=[],
    )
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
        expected_previous_version_id=None,
        context=context,
        actor="g3-persistence-test",
        reason="G3.5 persistence test",
    )
    return store, context, document_id, canonical


def _complete_result(store, context, document_id: str) -> dict:
    chunk_set = Gate3StructuralChunkFactory(
        store=store, read_enabled=True
    ).create(document_id=document_id, context=context)
    ordinals = [int(chunk["ordinal"]) for chunk in chunk_set["chunks"]]
    target = copy.deepcopy(
        chunk_set["chunks"][0]["target_mappings"][0]["canonical_target"]
    )
    payload = {
        "schema_version": "broker_reports_financial_annotations_v2",
        "canonical_binding": copy.deepcopy(chunk_set["canonical_binding"]),
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": "1.0.0",
        },
        "role_pack_identity": {
            "role_pack_id": "broker-reports-financial-roles",
            "semantic_version": "1.0.0",
        },
        "instruction_identity": {
            "instruction_id": "broker-reports-bounded-semantic-labeling",
            "semantic_version": "1.0.1",
        },
        "role_instruction_identity": {
            "instruction_id": "broker-reports-source-bound-role-labeling",
            "semantic_version": "1.0.0",
        },
        "model_identity": {"model_id": MODEL_ID},
        "annotations": [
            {
                "target": target,
                "financial_label": "TRANSACTION_CHARGE",
                "roles": [
                    {"role": "date", "status": "missing"},
                    {
                        "role": "amount",
                        "status": "bound",
                        "target": copy.deepcopy(target),
                        "exact_text": "12.00",
                    },
                    {"role": "currency", "status": "missing"},
                    {"role": "asset", "status": "missing"},
                ],
            }
        ],
        "validation_status": "validated",
    }
    return {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "selected_chunk_ordinals": ordinals,
        "selection_mode": "full_document",
        "document_status": "complete",
        "metrics": {
            "chunks_total": len(ordinals),
            "chunks_validated": len(ordinals),
            "chunks_rejected": 0,
            "chunks_provider_failed": 0,
            "annotations_validated": 1,
        },
        "merged_output": payload,
    }
