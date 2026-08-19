from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from types import ModuleType
from types import SimpleNamespace

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
)
from broker_reports_gate1.gate3_ndfl_workflow import NdflWorkflowError
from openwebui_actions.broker_reports_gate1_pipe import Pipe


def test_native_chat_scope_is_recovered_only_through_owner_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeChats:
        @staticmethod
        async def get_chat_by_id_and_user_id(chat_id: str, user_id: str):
            assert (chat_id, user_id) == ("owned-chat", "user-a")
            return SimpleNamespace(chat={"models": ["broker-reports-ndfl"]})

    class FakeRequest:
        async def json(self):
            return {"metadata": {"chat_id": "owned-chat"}}

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    chats = ModuleType("open_webui.models.chats")
    chats.Chats = FakeChats
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.chats", chats)

    metadata = asyncio.run(
        Pipe()._server_attested_runtime_metadata(
            request=FakeRequest(),
            metadata={},
            user={"id": "user-a"},
        )
    )

    assert metadata == {
        "chat_id": "owned-chat",
        "model_id": "broker-reports-ndfl",
    }


def test_product_stage_is_disabled_by_default() -> None:
    pipe = Pipe()
    result = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            store=object(),
            context=_context("broker-reports-ndfl"),
            artifact_manifest=SimpleNamespace(artifact_refs_by_type={}),
            user={"id": "user"},
            request=object(),
            event_emitter=None,
        )
    )

    assert result == {
        "schema_version": "broker_reports_ndfl_gate3_product_run_v1",
        "enabled": False,
        "status": "disabled",
        "provider_calls_total": 0,
    }


def test_product_stage_rejects_base_pipe_identity_before_provider() -> None:
    pipe = Pipe()
    pipe.valves.ndfl_gate3_enabled = True

    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(
            pipe._maybe_run_ndfl_gate3(
                store=object(),
                context=_context("broker_reports_gate1_pipe"),
                artifact_manifest=SimpleNamespace(artifact_refs_by_type={}),
                user={"id": "user"},
                request=object(),
                event_emitter=None,
            )
        )

    assert failure.value.code == "ndfl_workspace_model_identity_required"


def test_human_residual_turn_reuses_one_validated_gate3_artifact() -> None:
    context = _context("broker-reports-ndfl")
    record = SimpleNamespace(
        artifact_id="annotations",
        artifact_type=GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
        user_id=context.user_id,
        normalization_run_id=context.normalization_run_id,
        case_id=context.case_id,
        chat_id=None,
        workspace_model_id=context.workspace_model_id,
        visibility="private_case",
        validation_status="validated",
        lifecycle_status="active",
        purge_status=None,
        expires_at=None,
        source_file_ref={"source_deleted": False},
        payload=None,
        payload_ref=None,
    )
    store = SimpleNamespace(
        list_by_run=lambda run_id: [record] if run_id == "run" else [],
        get_record_unchecked=lambda artifact_id: (
            record if artifact_id == "annotations" else None
        ),
    )

    assert Pipe._persisted_gate3_annotations_artifact_id(
        store=store,
        context=context,
    ) == "annotations"


def test_private_audit_is_exact_external_and_non_overwriting(tmp_path: Path) -> None:
    pipe = Pipe()
    pipe.valves.ndfl_gate3_private_audit_enabled = True
    pipe.valves.ndfl_gate3_private_audit_root = str(tmp_path)
    pipe.valves.ndfl_gate3_private_audit_id = "g3c5_product_test_001"
    envelope = SimpleNamespace(
        artifact={"private": "exact canonical"},
        document_id="document",
        canonical_version_id="version",
        canonical_version_number=1,
        version_status="ACTIVE",
        schema_version="canonical_artifact_v1",
        canonical_root_sha256="a" * 64,
        physical_layout="single_payload",
        component_count=1,
        payload_bytes=100,
    )
    attempt = SimpleNamespace(
        projection={"model_view": {"content": "exact fragment"}},
        dictionary={"labels": [{"meaning": "exact meaning"}]},
        dictionary_managed_binding={"dictionary_identity": {"version": "1"}},
        dictionary_markdown="exact dictionary",
        instruction="exact instruction",
        model_visible_request={"messages": []},
        final_provider_request={"messages": []},
        raw_provider_response={"raw": True},
        raw_model_output={"annotations": []},
        validated_output={"annotations": []},
        validation_status="validated",
        validation_error_code=None,
        execution_metadata={"provider": "test"},
        metrics={"calls": 1},
    )
    role_attempt = SimpleNamespace(
        facts=(),
        role_context={
            "schema_version": "broker_reports_gate3_role_context_v1",
            "accepted_target_aliases": [],
        },
        role_provenance={
            "schema_version": "broker_reports_gate3_role_provenance_v1",
            "facts": [],
        },
        role_pack={"roles": []},
        role_pack_markdown="exact role pack",
        instruction="exact role instruction",
        model_visible_request=None,
        final_provider_request=None,
        raw_provider_response=None,
        raw_model_output=None,
        validated_output={"annotations": []},
        execution_status="skipped_empty",
        validation_error_code=None,
        execution_metadata=None,
        metrics={"provider_called": False},
    )
    outcome = SimpleNamespace(
        chunk={"content": "exact fragment"},
        attempt=attempt,
        role_attempt=role_attempt,
    )
    execution = SimpleNamespace(
        canonical_artifact_ref="manifest",
        activation_receipt=None,
        canonical_before_gate3=envelope,
        canonical_after_gate3=envelope,
        gate3=SimpleNamespace(
            batch_result=SimpleNamespace(
                outcomes=(outcome,),
                merged_output={"annotations": []},
                metrics={
                    "financial_labeling_provider_calls": 1,
                    "role_labeling_provider_calls": 1,
                },
            ),
            annotations_payload={
                "schema_version": "broker_reports_financial_annotations_v2",
                "annotations": [],
            },
            annotations_artifact_id="annotations",
        ),
    )

    receipt = pipe._write_ndfl_private_audit([execution])
    exact_path = tmp_path / "g3c5_product_test_001" / "document_001.exact.json"
    exact = json.loads(exact_path.read_text(encoding="utf-8"))

    assert receipt["status"] == "saved"
    assert pipe._ndfl_provider_calls_total([execution]) == 2
    assert exact["attempts"][0]["projection"]["model_view"]["content"] == (
        "exact fragment"
    )
    assert exact["attempts"][0]["dictionary_markdown"] == "exact dictionary"
    assert exact["attempts"][0]["instruction"] == "exact instruction"
    assert exact["attempts"][0]["raw_model_output"] == {"annotations": []}
    assert exact["attempts"][0]["role_attempt"]["role_pack_markdown"] == (
        "exact role pack"
    )
    assert exact["attempts"][0]["role_attempt"]["role_context"] == {
        "schema_version": "broker_reports_gate3_role_context_v1",
        "accepted_target_aliases": [],
    }
    assert exact["attempts"][0]["role_attempt"]["role_provenance"] == {
        "schema_version": "broker_reports_gate3_role_provenance_v1",
        "facts": [],
    }
    assert exact["financial_annotations_v2"]["annotations"] == []
    with pytest.raises(NdflWorkflowError) as failure:
        pipe._write_ndfl_private_audit([execution])
    assert failure.value.code == "ndfl_private_audit_target_not_new"


def _context(workspace_model_id: str) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="user",
        normalization_run_id="run",
        case_id="case",
        workspace_model_id=workspace_model_id,
        allow_private=True,
    )
