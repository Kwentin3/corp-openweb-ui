from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import broker_reports_gate1.gate3_bounded_labeling as bounded_labeling_module
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
    Gate3BoundedLabelingFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ARTIFACT_TYPES, ArtifactRecord
from broker_reports_gate1.gate3_bounded_labeling import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE3_LABELING_INSTRUCTION,
    GATE3_LABELING_INSTRUCTION_VERSION,
    GATE3_LABELING_RESPONSE_SCHEMA_SHA256,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
MODEL_ID = "models/gemini-3.5-flash"


def test_bounded_labeling_uses_exact_three_part_context_and_restores_alias(
    tmp_path: Path,
) -> None:
    store, context, document_id = _active_store(tmp_path)
    response = {
        "schema_version": "broker_reports_gate3_labeling_response_v1",
        "annotations": [
            {"target_alias": "t001", "financial_label": "DIVIDEND_INCOME"}
        ],
    }
    client, captured = _client(response)

    attempt = asyncio.run(
        Gate3BoundedLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert attempt.validation_status == "validated"
    assert attempt.validation_error_code is None
    assert attempt.dictionary_managed_binding == {
        "schema_version": (
            "broker_reports_gate3_financial_label_managed_binding_v1"
        ),
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": "1.0.0",
            "file_sha256": (
                "182e8d7f3604ad3d06d93c4d913df17979f21aeea669123d70c10be9d9652850"
            ),
            "model_view_sha256": hashlib.sha256(
                attempt.dictionary_markdown.encode("utf-8")
            ).hexdigest(),
        },
        "operator_surface": {
            "kind": "openwebui_skill",
            "stable_id": "broker-reports-financial-labels",
            "gui_path": "Workspace -> Skills -> Financial labels",
        },
        "exact_delivery": {
            "kind": "openwebui_workspace_tool",
            "stable_id": "broker_reports_financial_label_dictionary",
            "method": "load_financial_label_dictionary",
        },
        "runtime_loader": "Gate3FinancialLabelDictionaryFactory.create",
        "knowledge_rag_used": False,
    }
    assert attempt.validated_output == {
        "schema_version": "broker_reports_financial_annotations_v1",
        "canonical_binding": attempt.projection["canonical_binding"],
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": "1.0.0",
        },
        "instruction_identity": {
            "instruction_id": "broker-reports-bounded-semantic-labeling",
            "semantic_version": "1.0.1",
        },
        "model_identity": {"model_id": MODEL_ID},
        "annotations": [
            {
                "target": attempt.projection["target_mappings"][0][
                    "canonical_target"
                ],
                "financial_label": "DIVIDEND_INCOME",
            }
        ],
        "validation_status": "validated",
    }
    assert len(captured) == 1
    final_request = captured[0]
    assert set(final_request) == {"model", "messages", "stream", "response_format"}
    assert [item["role"] for item in final_request["messages"]] == [
        "system",
        "user",
        "user",
    ]
    assert [item["content"] for item in final_request["messages"]] == [
        GATE3_LABELING_INSTRUCTION,
        attempt.dictionary_markdown,
        attempt.projection["model_view"]["content"],
    ]
    assert sum(
        item["content"].count(attempt.dictionary_markdown)
        for item in final_request["messages"]
    ) == 1
    assert "metadata" not in final_request
    adapted_schema = final_request["response_format"]["json_schema"]["schema"]
    assert adapted_schema["properties"]["schema_version"] == {
        "enum": ["broker_reports_gate3_labeling_response_v1"]
    }
    canonical_schema = json.loads(
        (PACKAGE_ROOT / "gate3_labeling_response.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    canonical_alias = canonical_schema["$defs"]["annotation"]["properties"][
        "target_alias"
    ]
    adapted_alias = adapted_schema["$defs"]["annotation"]["properties"][
        "target_alias"
    ]
    assert canonical_alias["pattern"] == "^t[0-9]{3,}$"
    assert adapted_alias == {
        "type": "string",
        "description": canonical_alias["description"],
    }
    assert "enum" not in adapted_alias
    assert "для [t123] значение поля равно t123" in GATE3_LABELING_INSTRUCTION
    assert GATE3_LABELING_INSTRUCTION_VERSION == "1.0.1"
    assert attempt.metrics["dictionary_injection_count"] == 1
    assert attempt.metrics["meaningful_context_parts"] == 3
    assert client.qualification_lifecycle_snapshot() == {
        "local_invocations_total": 1,
        "provider_submissions_total": 1,
        "provider_responses_total": 1,
    }


def test_empty_sparse_response_is_a_valid_terminal_success(tmp_path: Path) -> None:
    store, context, document_id = _active_store(tmp_path)
    client, _captured = _client(
        {
            "schema_version": "broker_reports_gate3_labeling_response_v1",
            "annotations": [],
        }
    )

    attempt = asyncio.run(
        Gate3BoundedLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert attempt.validation_status == "validated"
    assert attempt.validated_output is not None
    assert attempt.validated_output["annotations"] == []


def test_completion_mutation_cannot_change_sealed_provider_audit(
    tmp_path: Path,
) -> None:
    store, context, document_id = _active_store(tmp_path)
    client, captured = _client(
        {
            "schema_version": "broker_reports_gate3_labeling_response_v1",
            "annotations": [],
        },
        mutate_submitted_request=True,
    )

    attempt = asyncio.run(
        Gate3BoundedLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert len(captured) == 1
    assert captured[0]["model"] == MODEL_ID
    assert attempt.final_provider_request == captured[0]
    assert attempt.validation_status == "validated"


@pytest.mark.parametrize(
    ("response", "error_code"),
    [
        (
            {
                "schema_version": "broker_reports_gate3_labeling_response_v1",
                "annotations": [
                    {
                        "target_alias": "t999",
                        "financial_label": "DIVIDEND_INCOME",
                    }
                ],
            },
            "gate3_labeling_alias_unknown",
        ),
        (
            {
                "schema_version": "broker_reports_gate3_labeling_response_v1",
                "annotations": [
                    {"target_alias": "t001", "financial_label": "NEW_LABEL"}
                ],
            },
            "gate3_labeling_label_unknown",
        ),
        (
            {
                "schema_version": "broker_reports_gate3_labeling_response_v1",
                "annotations": [],
                "reasoning": "not allowed",
            },
            "gate3_labeling_response_contract_invalid",
        ),
        (
            {
                "schema_version": "broker_reports_gate3_labeling_response_v1",
                "annotations": [
                    {
                        "target_alias": "t001",
                        "financial_label": "DIVIDEND_INCOME",
                        "node_id": "provider-invented-canonical-ref",
                    }
                ],
            },
            "gate3_labeling_response_contract_invalid",
        ),
        (
            {
                "schema_version": "broker_reports_gate3_labeling_response_v1",
                "annotations": [
                    {
                        "target_alias": "t001",
                        "financial_label": "DIVIDEND_INCOME",
                    },
                    {
                        "target_alias": "t001",
                        "financial_label": "DIVIDEND_INCOME",
                    },
                ],
            },
            "gate3_labeling_annotation_duplicate",
        ),
    ],
)
def test_invalid_model_output_is_visible_and_fail_closed(
    tmp_path: Path,
    response: dict,
    error_code: str,
) -> None:
    store, context, document_id = _active_store(tmp_path)
    client, captured = _client(response)

    attempt = asyncio.run(
        Gate3BoundedLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert attempt.validation_status == "rejected"
    assert attempt.validation_error_code == error_code
    assert attempt.validated_output is None
    assert isinstance(attempt.raw_model_output, str)
    assert json.loads(attempt.raw_model_output) == response
    assert len(captured) == 1
    assert client.qualification_lifecycle_snapshot()["provider_submissions_total"] == 1


@pytest.mark.parametrize(
    "raw_response",
    [
        "{",
        (
            '{"schema_version":"broker_reports_gate3_labeling_response_v1",'
            '"annotations":[],"annotations":[]}'
        ),
    ],
)
def test_malformed_or_duplicate_key_json_is_fail_closed(
    tmp_path: Path,
    raw_response: str,
) -> None:
    store, context, document_id = _active_store(tmp_path)
    client, _captured = _client(raw_response)

    attempt = asyncio.run(
        Gate3BoundedLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert attempt.validation_status == "rejected"
    assert (
        attempt.validation_error_code
        == "gate3_labeling_response_contract_invalid"
    )
    assert attempt.raw_model_output == raw_response
    assert attempt.validated_output is None


@pytest.mark.parametrize(
    "decorated_alias",
    ["[t001]", "`t001`", "target=t001", "alias: t001", "<t001>"],
)
def test_decorated_alias_is_rejected_without_repair(
    tmp_path: Path,
    decorated_alias: str,
) -> None:
    store, context, document_id = _active_store(tmp_path)
    client, captured = _client(
        {
            "schema_version": "broker_reports_gate3_labeling_response_v1",
            "annotations": [
                {
                    "target_alias": decorated_alias,
                    "financial_label": "DIVIDEND_INCOME",
                }
            ],
        }
    )

    attempt = asyncio.run(
        Gate3BoundedLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert attempt.validation_status == "rejected"
    assert (
        attempt.validation_error_code
        == "gate3_labeling_response_contract_invalid"
    )
    assert attempt.validated_output is None
    assert attempt.raw_model_output is not None
    assert len(captured) == 1


def test_response_schema_resource_is_exact_contract_copy() -> None:
    resource = PACKAGE_ROOT / "gate3_labeling_response.v1.schema.json"
    contract = (
        REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_GATE3_LABELING_RESPONSE.v1.schema.json"
    )
    assert resource.read_bytes() == contract.read_bytes()
    assert hashlib.sha256(resource.read_bytes()).hexdigest() == (
        GATE3_LABELING_RESPONSE_SCHEMA_SHA256
    )


def test_g34_factory_and_antidrift_boundaries_are_explicit() -> None:
    source = (PACKAGE_ROOT / "gate3_bounded_labeling.py").read_text(encoding="utf-8")
    document_source = inspect.getsource(Gate3BoundedLabelingFactory.create)
    chunk_source = inspect.getsource(
        Gate3BoundedLabelingFactory.create_from_chunk
    )
    core_source = inspect.getsource(
        Gate3BoundedLabelingFactory._create_from_projection
    )
    validator_source = inspect.getsource(
        bounded_labeling_module._validate_and_restore
    )
    assert "Gate3BoundedLabelingFactory.create/create_from_chunk" in FACTORY_REQUIRED
    assert "Gate3ProjectionFactory" in document_source
    assert "_projection_from_structural_chunk" in chunk_source
    assert "Gate3FinancialLabelDictionaryFactory" in core_source
    assert "label_gate3_once" in core_source
    assert "infer labels" in FORBIDDEN
    assert "retry" in FORBIDDEN
    for forbidden_repair in (
        ".strip(",
        ".replace(",
        "re.sub(",
        "re.search(",
        "normalize_alias",
        "repair_alias",
    ):
        assert forbidden_repair not in validator_source
    assert "broker_reports_financial_annotations_v1" in ARTIFACT_TYPES
    assert "ArtifactResolver" not in source
    for forbidden in (
        "FullSourceArtifactFactory",
        "ArtifactResolver",
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "gate3_financial_domain",
        "gate2_financial_evidence",
    ):
        assert f"import {forbidden}" not in source
        assert f"from .{forbidden}" not in source


def _client(
    response: dict | str,
    *,
    mutate_submitted_request: bool = False,
):
    captured: list[dict] = []

    def complete(*, form_data, **_kwargs):
        captured.append(json.loads(json.dumps(form_data, ensure_ascii=False)))
        if mutate_submitted_request:
            form_data.pop("model", None)
            form_data.pop("messages", None)
        return {
            "id": "gate3-local-seam-response",
            "model": MODEL_ID,
            "choices": [
                {
                    "message": {
                        "content": (
                            response
                            if isinstance(response, str)
                            else json.dumps(response, ensure_ascii=False)
                        )
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

    user = SimpleNamespace(id="gate3-user")
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


def _active_store(root: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="gate3-user",
        normalization_run_id="gate3-run",
        case_id="gate3-case",
        workspace_model_id="gate3-workspace",
        allow_private=True,
    )
    document_id = "gate3-bounded-labeling-document"
    source_ref = "gate3-bounded-labeling-source"
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
            source_file_ref={"openwebui_file_id": "gate3-source"},
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
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="gate3-labeling-test-v1")
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "csv",
            "sha256": hashlib.sha256(b"gate3-labeling").hexdigest(),
            "declared_mime_type": "text/csv",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "rows": [["Description"], ["Cash dividend paid"]],
                    "encoding": "utf-8",
                    "delimiter": ",",
                    "quotechar": '"',
                    "header_present": False,
                    "duplicate_headers": False,
                },
                "source_location": {"row_start": 1, "row_end": 2},
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
        actor="gate3-test",
        reason="inactive G3.4 local seam",
    )
    return store, context, document_id
