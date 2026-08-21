from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

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
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelClientFactory,
    Gate3NdflCaseReadinessFactory,
    NDFL_GATE3_HANDOFF_SCHEMA_VERSION,
    NDFL_WORKFLOW_STABLE_ID,
    NdflWorkflowError,
    NdflWorkflowFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.gate3_financial_annotations_persistence import (
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
)
from broker_reports_gate1.gate3_ndfl_workflow import FACTORY_REQUIRED, FORBIDDEN


MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE_ID = "google_gemini"
ALIAS_RE = re.compile(r"(?<!\\)\[(t[0-9]{3,})\]")


def test_handoff_is_active_identity_only_and_reader_backed(tmp_path: Path) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "handoff-document"
    canonical = _publish_canonical(
        store,
        context,
        document_id=document_id,
        revision=1,
        activate=True,
    )
    client, calls = _client(context)

    handoff = NdflWorkflowFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        model_id=MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
    ).create().decide_gate3(document_id=document_id, context=context)

    assert handoff.to_dict() == {
        "schema_version": NDFL_GATE3_HANDOFF_SCHEMA_VERSION,
        "workflow_id": NDFL_WORKFLOW_STABLE_ID,
        "decision": "RUN_GATE3",
        "document_id": document_id,
        "canonical_version_id": canonical.canonical_version_id,
    }
    assert set(handoff.to_dict()) == {
        "schema_version",
        "workflow_id",
        "decision",
        "document_id",
        "canonical_version_id",
    }
    assert calls == []


def test_workflow_runs_existing_gate3_and_persists_exact_sidecar(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "workflow-document"
    canonical = _publish_canonical(
        store,
        context,
        document_id=document_id,
        revision=1,
        activate=True,
    )
    active_before = store.get_active_canonical_version(
        context=context,
        document_id=document_id,
    )
    client, calls = _client(context)
    workflow = NdflWorkflowFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        model_id=MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()

    execution = asyncio.run(
        workflow.run_gate3(document_id=document_id, context=context)
    )

    assert len(calls) == 2
    assert execution.batch_result.document_status == "complete"
    assert execution.annotations_payload["canonical_binding"] == {
        "document_id": document_id,
        "canonical_version_id": canonical.canonical_version_id,
    }
    record = store.get_record_unchecked(execution.annotations_artifact_id)
    assert record is not None
    assert record.artifact_type == GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
    active_after = store.get_active_canonical_version(
        context=context,
        document_id=document_id,
    )
    assert active_after == active_before


def test_incomplete_document_reports_safe_failed_phase_without_persistence(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "incomplete-workflow-document"
    _publish_canonical(
        store,
        context,
        document_id=document_id,
        revision=1,
        activate=True,
    )
    client, calls = _client(context, pass1_unknown_alias=True)
    workflow = NdflWorkflowFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        model_id=MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()

    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(workflow.run_gate3(document_id=document_id, context=context))

    assert failure.value.code == "ndfl_gate3_document_incomplete"
    assert failure.value.safe_details == {
        "document_status": "incomplete",
        "selection_mode": "full_document",
        "chunks_total": 1,
        "chunks_validated": 0,
        "chunks_rejected": 1,
        "chunks_provider_failed": 0,
        "failed_outcomes": [
            {
                "chunk_ordinal": 1,
                "terminal_status": "rejected",
                "failed_phase": "financial_labeling",
                "error_code": "gate3_labeling_alias_unknown",
            }
        ],
    }
    assert len(calls) == 1
    assert not any(
        record.artifact_type == GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
        for record in store.list_by_case_context(context)
    )


def test_incomplete_role_response_reports_only_safe_shape_diagnostics(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "incomplete-role-workflow-document"
    _publish_canonical(
        store,
        context,
        document_id=document_id,
        revision=1,
        activate=True,
    )
    client, calls = _client(context, role_top_level_invalid=True)
    workflow = NdflWorkflowFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        model_id=MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()

    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(workflow.run_gate3(document_id=document_id, context=context))

    outcome = failure.value.safe_details["failed_outcomes"][0]
    diagnostics = outcome["role_response_diagnostics"]
    assert outcome["failed_phase"] == "role_labeling"
    assert outcome["error_code"] == "gate3_role_response_contract_invalid"
    assert diagnostics == {
        "raw_model_output_chars": len(
            json.dumps({"unexpected": []}, ensure_ascii=False)
        ),
        "raw_output_kind": "string",
        "raw_output_json_decodable": True,
        "raw_output_top_level_contract_match": False,
        "raw_output_schema_version_match": False,
        "raw_output_facts_list": False,
        "raw_output_facts_total": None,
        "raw_output_fact_shape_contract_match": False,
        "provider_finish_reason": "stop",
        "requested_max_tokens": 65_536,
        "provider_input_tokens": 100,
        "provider_output_tokens": 20,
        "provider_duration_ms": diagnostics["provider_duration_ms"],
    }
    assert len(calls) == 2


def test_product_path_activates_exact_candidate_then_preserves_gate2(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "product-path-document"
    candidate = _publish_canonical(
        store,
        context,
        document_id=document_id,
        revision=1,
        activate=False,
    )
    client, calls = _client(context)
    workflow = NdflWorkflowFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        model_id=MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()

    execution = asyncio.run(
        workflow.run_product_path(
            canonical_artifact_ref=candidate.artifact_ref,
            context=context,
        )
    )

    assert len(calls) == 2
    assert execution.activation_receipt is not None
    assert execution.activation_receipt.actor == NDFL_WORKFLOW_STABLE_ID
    assert execution.activation_receipt.canonical_version_id == (
        candidate.canonical_version_id
    )
    assert execution.canonical_before_gate3.document_id == document_id
    assert execution.canonical_before_gate3.version_status == "ACTIVE"
    assert execution.canonical_after_gate3 == execution.canonical_before_gate3
    assert execution.gate3.annotations_payload["canonical_binding"] == {
        "document_id": document_id,
        "canonical_version_id": candidate.canonical_version_id,
    }


def test_product_path_requires_ndfl_workspace_identity(tmp_path: Path) -> None:
    store, context = _store_and_context(tmp_path)
    candidate = _publish_canonical(
        store,
        context,
        document_id="wrong-model-document",
        revision=1,
        activate=False,
    )
    client, _calls = _client(context)
    workflow = NdflWorkflowFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        model_id=MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()

    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(
            workflow.run_product_path(
                canonical_artifact_ref=candidate.artifact_ref,
                context=replace(context, workspace_model_id="broker_reports_gate1_pipe"),
            )
        )

    assert failure.value.code == "ndfl_workspace_model_identity_required"


def test_version_b_requires_new_gate3_result(tmp_path: Path) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "versioned-document"
    first = _publish_canonical(
        store,
        context,
        document_id=document_id,
        revision=1,
        activate=True,
    )
    client, _calls = _client(context)
    workflow = NdflWorkflowFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        model_id=MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()
    first_execution = asyncio.run(
        workflow.run_gate3(document_id=document_id, context=context)
    )
    next_context = replace(context, normalization_run_id="ndfl-run-2")
    second = _publish_canonical(
        store,
        next_context,
        document_id=document_id,
        revision=2,
        activate=True,
        expected_previous_version_id=first.canonical_version_id,
    )

    next_handoff = workflow.decide_gate3(
        document_id=document_id,
        context=context,
    )
    state = Gate3NdflCaseReadinessFactory(
        store=store,
        read_enabled=True,
    ).create(context=context)
    document = state["documents"][0]

    assert next_handoff.canonical_version_id == second.canonical_version_id
    assert first_execution.handoff.canonical_version_id == first.canonical_version_id
    assert document["gate2_ready"] is True
    assert document["gate3_ready"] is False
    assert document["stale_annotation_candidates_total"] == 1
    assert document["reason_codes"] == [
        "GATE3_ANNOTATIONS_MISSING",
        "GATE3_ANNOTATIONS_STALE",
    ]


def test_version_change_during_labeling_fails_before_sidecar(
    tmp_path: Path,
) -> None:
    store, context = _store_and_context(tmp_path)
    document_id = "racing-document"
    first = _publish_canonical(
        store,
        context,
        document_id=document_id,
        revision=1,
        activate=True,
    )
    next_context = replace(context, normalization_run_id="ndfl-run-race-2")
    second = _publish_canonical(
        store,
        next_context,
        document_id=document_id,
        revision=2,
        activate=False,
    )

    def activate_second() -> None:
        CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
            canonical_version_id=second.canonical_version_id,
            expected_previous_version_id=first.canonical_version_id,
            context=next_context,
            actor="ndfl-workflow-race-test",
            reason="prove fail-closed version handoff",
        )

    client, calls = _client(context, before_response=activate_second)
    workflow = NdflWorkflowFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        model_id=MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()

    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(workflow.run_gate3(document_id=document_id, context=context))

    assert failure.value.code == "ndfl_gate3_canonical_changed_during_labeling"
    assert len(calls) == 1
    records = store.list_by_case_context(context)
    assert not any(
        record.artifact_type == GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
        for record in records
    )


def test_workflow_is_thin_factory_route_without_gate2_or_name_coupling() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "broker_reports_gate1" / "gate3_ndfl_workflow.py").read_text(
        encoding="utf-8"
    )
    assert "NdflWorkflowFactory.create" in FACTORY_REQUIRED
    assert "display name" in FORBIDDEN
    assert "CanonicalReaderFactory" in source
    assert "Gate3ChunkBatchLabelingFactory" in source
    assert "Gate3FinancialAnnotationsPersistenceFactory" in source
    assert "put_record(" not in source
    assert "ArtifactStoreFactory" not in source
    assert "gate2_handoff" not in source
    assert "openwebui_actions" not in source
    assert "asyncio.gather" not in source
    assert source.lower().count("retry") == 1
    for gate2_owner in (
        "gate2_handoff.py",
        "canonical_artifact.py",
        "canonical_store.py",
    ):
        owner_source = (root / "broker_reports_gate1" / gate2_owner).read_text(
            encoding="utf-8"
        )
        assert "gate3_ndfl_workflow" not in owner_source
        assert "NdflWorkflowFactory" not in owner_source


def _store_and_context(tmp_path: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="ndfl-user",
        normalization_run_id="ndfl-run-1",
        case_id="ndfl-case",
        workspace_model_id=NDFL_WORKFLOW_STABLE_ID,
        allow_private=True,
    )
    return store, context


def _publish_canonical(
    store,
    context: ArtifactAccessContext,
    *,
    document_id: str,
    revision: int,
    activate: bool,
    expected_previous_version_id: str | None = None,
):
    source_ref = f"source-{document_id}-{revision}"
    store.put_record(
        ArtifactRecord(
            artifact_id=source_ref,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={"openwebui_file_id": source_ref},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=build_retention_policy(mode="api_smoke"),
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload={"synthetic_fixture": True, "revision": revision},
        )
    )
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version=f"ndfl-workflow-v{revision}")
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=revision,
        document={
            "container_format": "html_text",
            "sha256": hashlib.sha256(
                f"{document_id}-{revision}".encode("utf-8")
            ).hexdigest(),
            "declared_mime_type": "text/html",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "blocks": [
                        {
                            "kind": "heading",
                            "level": 1,
                            "text": "Broker statement",
                            "source_location": {"block_index": 1},
                        },
                        {
                            "kind": "text",
                            "text": f"Dividend income revision {revision}",
                            "source_location": {"block_index": 2},
                        },
                    ]
                },
                "source_location": {"block_start": 1, "block_end": 2},
            }
        ],
        source_units=[],
        table_projections=[],
    )
    persisted = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
        compare_receipt=None,
    )
    if activate:
        CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
            canonical_version_id=persisted.canonical_version_id,
            expected_previous_version_id=expected_previous_version_id,
            context=context,
            actor="ndfl-workflow-test",
            reason="prove exact Gate 2 to Gate 3 handoff",
        )
    return persisted


def _client(
    context: ArtifactAccessContext,
    *,
    before_response=None,
    pass1_unknown_alias: bool = False,
    role_top_level_invalid: bool = False,
):
    captured: list[dict] = []

    def complete(*, form_data, **_kwargs):
        captured.append(json.loads(json.dumps(form_data, ensure_ascii=False)))
        alias = ALIAS_RE.search(form_data["messages"][-1]["content"])
        assert alias is not None
        name = form_data["response_format"]["json_schema"]["name"]
        if name == "broker_reports_gate3_labeling_response_v1":
            if before_response is not None:
                before_response()
            response = {
                "schema_version": name,
                "annotations": [
                    {
                        "target_alias": (
                            "t999999" if pass1_unknown_alias else alias.group(1)
                        ),
                        "financial_label": "DIVIDEND_INCOME",
                    }
                ],
            }
        else:
            assert name == "broker_reports_gate3_role_labeling_response_v1"
            response = {
                "schema_version": name,
                "facts": [
                    {
                        "fact_alias": "f001",
                        "financial_label": "DIVIDEND_INCOME",
                        "roles": [
                            {
                                "role": role,
                                "status": "bound",
                                "target_alias": alias.group(1),
                            }
                            for role in ("date", "amount", "currency")
                        ]
                        + [{"role": "asset", "status": "missing"}],
                    }
                ],
            }
            if role_top_level_invalid:
                response = {"unexpected": []}
        return {
            "id": f"ndfl-response-{len(captured)}",
            "model": MODEL_ID,
            "choices": [
                {
                    "message": {
                        "content": json.dumps(response, ensure_ascii=False)
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
        }

    user = SimpleNamespace(id=context.user_id)
    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=PROVIDER_PROFILE_ID,
        ),
        user=user,
        request=SimpleNamespace(),
        completion_resolver=lambda _user_id: (complete, user),
    ).create()
    return client, captured
