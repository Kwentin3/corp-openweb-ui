from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import re
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
    Gate3ChunkBatchLabelingError,
    Gate3ChunkBatchLabelingFactory,
    Gate3StructuralChunkFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ARTIFACT_TYPES, ArtifactRecord
from broker_reports_gate1.gate3_chunk_batch_labeling import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)


ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "models/gemini-3.5-flash"
ALIAS_RE = re.compile(r"(?<!\\)\[(t[0-9]{3,})\]")


def test_full_document_batch_is_sequential_and_merges_in_target_order(
    tmp_path: Path,
) -> None:
    store, context, document_id = _active_large_csv(tmp_path)
    chunk_set = Gate3StructuralChunkFactory(
        store=store,
        read_enabled=True,
    ).create(document_id=document_id, context=context)
    assert len(chunk_set["chunks"]) >= 3
    client, captured = _client()

    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert result.selection_mode == "full_document"
    assert result.document_status == "complete"
    assert len(captured) == len(chunk_set["chunks"])
    assert result.metrics["chunks_validated"] == len(chunk_set["chunks"])
    assert result.metrics["chunks_rejected"] == 0
    assert result.metrics["chunks_provider_failed"] == 0
    assert result.merged_output is not None
    expected_targets = [
        chunk["target_mappings"][0]["canonical_target"]
        for chunk in chunk_set["chunks"]
    ]
    assert [
        annotation["target"]
        for annotation in result.merged_output["annotations"]
    ] == expected_targets
    assert result.metrics["input_tokens_total"] == 100 * len(captured)
    for request in captured:
        assert len(request["messages"]) == 3
        schema = request["response_format"]["json_schema"]["schema"]
        assert schema["properties"]["schema_version"] == {
            "enum": ["broker_reports_gate3_labeling_response_v1"]
        }


def test_rejected_chunk_is_visible_and_document_is_incomplete_without_retry(
    tmp_path: Path,
) -> None:
    store, context, document_id = _active_large_csv(tmp_path)
    chunk_set = Gate3StructuralChunkFactory(
        store=store,
        read_enabled=True,
    ).create(document_id=document_id, context=context)
    client, captured = _client(invalid_call=2)

    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert len(captured) == len(chunk_set["chunks"])
    assert result.document_status == "incomplete"
    assert result.metrics["chunks_rejected"] == 1
    assert result.metrics["chunks_validated"] == len(chunk_set["chunks"]) - 1
    rejected = [
        outcome
        for outcome in result.outcomes
        if outcome.terminal_status == "rejected"
    ]
    assert len(rejected) == 1
    assert rejected[0].error_code == "gate3_labeling_response_contract_invalid"
    assert rejected[0].attempt is not None
    assert rejected[0].attempt.raw_model_output
    assert result.merged_output is not None
    assert len(result.merged_output["annotations"]) == len(captured) - 1


def test_predeclared_subset_is_never_reported_as_complete_document(
    tmp_path: Path,
) -> None:
    store, context, document_id = _active_large_csv(tmp_path)
    chunk_set = Gate3StructuralChunkFactory(
        store=store,
        read_enabled=True,
    ).create(document_id=document_id, context=context)
    selected = (1, len(chunk_set["chunks"]))
    client, captured = _client()

    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(
            document_id=document_id,
            context=context,
            chunk_ordinals=selected,
        )
    )

    assert result.selected_chunk_ordinals == selected
    assert result.selection_mode == "representative_subset"
    assert result.document_status == "representative_subset_validated"
    assert len(captured) == 2
    assert {
        outcome.chunk["canonical_binding"]["document_id"]
        for outcome in result.outcomes
    } == {document_id}


@pytest.mark.parametrize("selection", [(), (2, 1), (1, 1), (999,)])
def test_invalid_selection_fails_before_provider(
    tmp_path: Path,
    selection: tuple[int, ...],
) -> None:
    store, context, document_id = _active_large_csv(tmp_path)
    client, captured = _client()

    with pytest.raises(Gate3ChunkBatchLabelingError) as failure:
        asyncio.run(
            Gate3ChunkBatchLabelingFactory(
                store=store,
                read_enabled=True,
                model_client=client,
                model_id=MODEL_ID,
            ).create(
                document_id=document_id,
                context=context,
                chunk_ordinals=selection,
            )
        )

    assert failure.value.code == "gate3_chunk_batch_selection_invalid"
    assert captured == []


def test_batch_owner_has_no_parallel_or_semantic_runtime() -> None:
    source = (
        ROOT / "broker_reports_gate1" / "gate3_chunk_batch_labeling.py"
    ).read_text(encoding="utf-8")
    create_source = inspect.getsource(Gate3ChunkBatchLabelingFactory.create)
    assert "Gate3ChunkBatchLabelingFactory.create" in FACTORY_REQUIRED
    assert "Gate3StructuralChunkFactory" in create_source
    assert "create_from_chunk" in create_source
    assert "for chunk in selected" in create_source
    assert "await labeling.create_from_chunk" in create_source
    assert "retry" in FORBIDDEN
    assert "concurrently" in FORBIDDEN
    assert "broker_reports_gate3_chunk_batch_labeling_result_v1" not in ARTIFACT_TYPES
    for forbidden in (
        "asyncio.gather",
        "create_task",
        "ThreadPool",
        "ProcessPool",
        "Gate3FinancialLabelDictionaryFactory",
        "GATE3_LABELING_INSTRUCTION",
        "put_record",
        "openai",
        "anthropic",
        "requests",
        "httpx",
    ):
        assert forbidden not in source


def test_live_repo_subset_is_selected_by_structure_only() -> None:
    script_path = ROOT / "scripts" / "live_gate3_chunk_batch_labeling.py"
    spec = importlib.util.spec_from_file_location("g34c_live_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    chunks = [
        _selection_chunk(1, "whole_table", "whole"),
        *[_selection_chunk(ordinal, "table_rows", "short") for ordinal in range(2, 5)],
        *[_selection_chunk(ordinal, "table_rows", "largest") for ordinal in range(5, 11)],
    ]

    assert module._representative_repo_ordinals({"chunks": chunks}) == (
        1,
        5,
        8,
        9,
        10,
    )
    source = script_path.read_text(encoding="utf-8")
    assert "Gate3ChunkBatchLabelingFactory" in source
    assert "Gate3BoundedLabelingFactory" not in source
    assert "one_attempt_completion" in source
    assert "retry" in module.FORBIDDEN


def _selection_chunk(ordinal: int, kind: str, node_ref: str) -> dict:
    return {
        "ordinal": ordinal,
        "structural_kind": kind,
        "structural_scope": {"node_refs": [node_ref]},
    }


def _client(*, invalid_call: int | None = None):
    captured: list[dict] = []

    def complete(*, form_data, **_kwargs):
        captured.append(json.loads(json.dumps(form_data, ensure_ascii=False)))
        call = len(captured)
        alias = ALIAS_RE.search(form_data["messages"][-1]["content"])
        assert alias is not None
        response = {
            "schema_version": (
                "wrong-schema"
                if invalid_call == call
                else "broker_reports_gate3_labeling_response_v1"
            ),
            "annotations": [
                {
                    "target_alias": alias.group(1),
                    "financial_label": "DIVIDEND_INCOME",
                }
            ],
        }
        return {
            "id": f"gate3-batch-response-{call}",
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

    user = SimpleNamespace(id="gate3-batch-user")
    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id="google_gemini",
        ),
        user=user,
        request=SimpleNamespace(),
        completion_resolver=lambda _user_id: (complete, user),
    ).create()
    return client, captured


def _active_large_csv(root: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="gate3-batch-user",
        normalization_run_id="gate3-batch-run",
        case_id="gate3-batch-case",
        workspace_model_id="gate3-batch-workspace",
        allow_private=True,
    )
    document_id = "gate3-chunk-batch-document"
    source_ref = "gate3-chunk-batch-source"
    retention = build_retention_policy(mode="api_smoke")
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
            source_file_ref={"openwebui_file_id": "gate3-batch-source"},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload={"synthetic_fixture": True},
        )
    )
    rows = [["Description", "Amount"]] + [
        [f"synthetic-row-{index}-" + ("x" * 900), str(index)]
        for index in range(1, 181)
    ]
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="gate3-batch-test-v1")
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "csv",
            "sha256": hashlib.sha256(b"gate3-chunk-batch").hexdigest(),
            "declared_mime_type": "text/csv",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "rows": rows,
                    "encoding": "utf-8",
                    "delimiter": ",",
                    "quotechar": '"',
                    "header_present": True,
                    "duplicate_headers": False,
                },
                "source_location": {"row_start": 1, "row_end": len(rows)},
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
        retention_policy=retention,
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=persisted.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="gate3-batch-test",
        reason="inactive G3.4C local seam",
    )
    return store, context, document_id
