from __future__ import annotations

import copy

import pytest

from broker_reports_gate1 import (
    AnswerContextSelectionFactory,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
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
