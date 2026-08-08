from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from jsonschema import Draft202012Validator
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
    Gate3ChunkBatchLabelingFactory,
    Gate3RoleValueResolverFactory,
    Gate3StructuralChunkFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
MODEL_ID = "models/gemini-3.5-flash"
FACT_LABELS = [
    "SECURITY_PURCHASE",
    "SECURITY_DISPOSAL",
    "DIVIDEND_INCOME",
    "TRANSACTION_CHARGE",
    "TAX_WITHHELD",
]


def test_representative_facts_are_source_bound_and_mechanically_materialized(
    tmp_path: Path,
) -> None:
    store, context, document_id = _active_role_table(tmp_path)
    chunk = _single_chunk(store, context, document_id)
    aliases = _aliases_by_coordinate(chunk)
    client, captured = _client(
        label_response=_label_response(aliases),
        role_response=_role_response(aliases),
    )

    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert result.document_status == "complete"
    assert len(captured) == 2
    assert [
        request["response_format"]["json_schema"]["name"]
        for request in captured
    ] == [
        "broker_reports_gate3_labeling_response_v1",
        "broker_reports_gate3_role_labeling_response_v1",
    ]
    assert result.metrics["financial_labeling_provider_calls"] == 1
    assert result.metrics["role_labeling_provider_calls"] == 1
    assert result.metrics["role_labeling_skipped_empty_chunks"] == 0
    payload = result.merged_output
    assert payload is not None
    assert payload["schema_version"] == "broker_reports_financial_annotations_v2"
    assert [item["financial_label"] for item in payload["annotations"]] == (
        FACT_LABELS
    )
    assert "related_fact" not in json.dumps(payload, ensure_ascii=False)

    artifact = CanonicalReaderFactory(
        store=store, read_enabled=True
    ).create().read_active(document_id, context)
    resolver = Gate3RoleValueResolverFactory.create(canonical_artifact=artifact)
    materialized = {
        annotation["financial_label"]: {
            binding["role"]: resolver.resolve(binding)
            for binding in annotation["roles"]
        }
        for annotation in payload["annotations"]
    }
    assert materialized == {
        "SECURITY_PURCHASE": {
            "date": "2026-01-10",
            "asset": "ACME",
            "quantity": "10",
            "amount": "125.00",
            "currency": "USD",
            "unit_price": "12.50",
        },
        "SECURITY_DISPOSAL": {
            "date": "2026-02-11",
            "asset": "ACME",
            "quantity": "4",
            "amount": "60.00",
            "currency": "USD",
            "unit_price": "15.00",
        },
        "DIVIDEND_INCOME": {
            "date": "2026-03-12",
            "amount": "8.00",
            "currency": "USD",
            "asset": "ACME",
        },
        "TRANSACTION_CHARGE": {
            "date": "2026-02-11",
            "amount": "1.25",
            "currency": "USD",
            "asset": None,
        },
        "TAX_WITHHELD": {
            "date": "2026-03-12",
            "amount": "1.20",
            "currency": "USD",
            "asset": None,
        },
    }
    dividend_asset = next(
        binding
        for annotation in payload["annotations"]
        if annotation["financial_label"] == "DIVIDEND_INCOME"
        for binding in annotation["roles"]
        if binding["role"] == "asset"
    )
    assert dividend_asset["exact_text"] == "ACME"

    target_schema = json.loads(
        (
            REPO_ROOT
            / "docs/stage2/contracts/BROKER_REPORTS_GATE3_TARGET.v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    annotations_schema = json.loads(
        (
            REPO_ROOT
            / "docs/stage2/contracts/BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json"
        ).read_text(encoding="utf-8")
    )
    from referencing import Registry, Resource

    registry = Registry().with_resource(
        target_schema["$id"], Resource.from_contents(target_schema)
    )
    Draft202012Validator(annotations_schema, registry=registry).validate(payload)


def test_empty_pass1_skips_role_provider_call_and_emits_empty_v2(
    tmp_path: Path,
) -> None:
    store, context, document_id = _active_role_table(tmp_path)
    client, captured = _client(
        label_response={
            "schema_version": "broker_reports_gate3_labeling_response_v1",
            "annotations": [],
        },
        role_response=None,
    )

    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert len(captured) == 1
    assert result.document_status == "complete"
    assert result.metrics["role_labeling_provider_calls"] == 0
    assert result.metrics["role_labeling_skipped_empty_chunks"] == 1
    assert result.merged_output is not None
    assert result.merged_output["schema_version"] == (
        "broker_reports_financial_annotations_v2"
    )
    assert result.merged_output["annotations"] == []


def test_nonliteral_exact_text_fails_closed_without_repair(tmp_path: Path) -> None:
    store, context, document_id = _active_role_table(tmp_path)
    chunk = _single_chunk(store, context, document_id)
    aliases = _aliases_by_coordinate(chunk)
    response = _role_response(aliases)
    response["facts"][2]["roles"][3]["exact_text"] = "NORMALIZED-ACME"
    client, captured = _client(
        label_response=_label_response(aliases),
        role_response=response,
    )

    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert len(captured) == 2
    assert result.document_status == "incomplete"
    assert result.outcomes[0].terminal_status == "rejected"
    assert result.outcomes[0].failed_phase == "role_labeling"
    assert result.outcomes[0].error_code == (
        "gate3_role_exact_text_not_literal_substring"
    )
    assert result.metrics["role_labeling_provider_calls"] == 1
    assert result.merged_output is None


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            lambda response: response["facts"][0].update(fact_alias="f999"),
            "gate3_role_fact_set_mismatch",
        ),
        (
            lambda response: response["facts"][0].update(
                financial_label="TAX_WITHHELD"
            ),
            "gate3_role_fact_label_mismatch",
        ),
        (
            lambda response: response["facts"][0]["roles"][0].update(
                role="related_fact"
            ),
            "gate3_role_binding_not_allowed",
        ),
        (
            lambda response: response["facts"][0]["roles"].pop(),
            "gate3_role_cardinality_invalid",
        ),
        (
            lambda response: response["facts"][0]["roles"][0].update(
                target_alias="t999"
            ),
            "gate3_role_target_alias_unknown",
        ),
        (
            lambda response: response["facts"][0]["roles"][3].update(
                target_alias=response["_row_alias"]
            ),
            "gate3_role_target_text_ambiguous",
        ),
    ],
)
def test_unknown_fact_label_role_target_or_cardinality_fails_closed(
    tmp_path: Path,
    mutation,
    expected_code: str,
) -> None:
    store, context, document_id = _active_role_table(tmp_path)
    chunk = _single_chunk(store, context, document_id)
    aliases = _aliases_by_coordinate(chunk)
    response = _role_response(aliases)
    response["_row_alias"] = aliases[("row", 2)]
    mutation(response)
    response.pop("_row_alias", None)
    client, _captured = _client(
        label_response=_label_response(aliases),
        role_response=response,
    )

    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(document_id=document_id, context=context)
    )

    assert result.document_status == "incomplete"
    assert result.outcomes[0].failed_phase == "role_labeling"
    assert result.outcomes[0].error_code == expected_code
    assert result.merged_output is None


def test_role_response_schema_resource_is_exact_contract_copy() -> None:
    package = (
        SERVICE_ROOT
        / "broker_reports_gate1/gate3_role_labeling_response.v1.schema.json"
    )
    contract = (
        REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_GATE3_ROLE_LABELING_RESPONSE.v1.schema.json"
    )
    assert package.read_bytes() == contract.read_bytes()


def _single_chunk(store, context, document_id: str) -> dict:
    chunk_set = Gate3StructuralChunkFactory(
        store=store, read_enabled=True
    ).create(document_id=document_id, context=context)
    assert len(chunk_set["chunks"]) == 1
    return chunk_set["chunks"][0]


def _aliases_by_coordinate(chunk: dict) -> dict[tuple, str]:
    result = {}
    for mapping in chunk["target_mappings"]:
        target = mapping["canonical_target"]
        if target["kind"] == "table_row":
            key = ("row", target["row"])
        elif target["kind"] == "table_cell":
            key = ("cell", target["row"], target["column"])
        else:
            continue
        result[key] = mapping["target_alias"]
    return result


def _label_response(aliases: dict[tuple, str]) -> dict:
    return {
        "schema_version": "broker_reports_gate3_labeling_response_v1",
        "annotations": [
            {"target_alias": aliases[("row", row)], "financial_label": label}
            for row, label in enumerate(FACT_LABELS, start=2)
        ],
    }


def _role_response(aliases: dict[tuple, str]) -> dict:
    def bound(role: str, row: int, column: int, exact_text: str | None = None):
        value = {
            "role": role,
            "status": "bound",
            "target_alias": aliases[("cell", row, column)],
        }
        if exact_text is not None:
            value["exact_text"] = exact_text
        return value

    return {
        "schema_version": "broker_reports_gate3_role_labeling_response_v1",
        "facts": [
            {
                "fact_alias": "f001",
                "financial_label": "SECURITY_PURCHASE",
                "roles": [
                    bound("date", 2, 2),
                    bound("asset", 2, 4),
                    bound("quantity", 2, 5),
                    bound("amount", 2, 7),
                    bound("currency", 2, 8),
                    bound("unit_price", 2, 6),
                ],
            },
            {
                "fact_alias": "f002",
                "financial_label": "SECURITY_DISPOSAL",
                "roles": [
                    bound("date", 3, 2),
                    bound("asset", 3, 4),
                    bound("quantity", 3, 5),
                    bound("amount", 3, 7),
                    bound("currency", 3, 8),
                    bound("unit_price", 3, 6),
                ],
            },
            {
                "fact_alias": "f003",
                "financial_label": "DIVIDEND_INCOME",
                "roles": [
                    bound("date", 4, 2),
                    bound("amount", 4, 7),
                    bound("currency", 4, 8),
                    bound("asset", 4, 3, "ACME"),
                ],
            },
            {
                "fact_alias": "f004",
                "financial_label": "TRANSACTION_CHARGE",
                "roles": [
                    bound("date", 5, 2),
                    bound("amount", 5, 7),
                    bound("currency", 5, 8),
                    {"role": "asset", "status": "missing"},
                ],
            },
            {
                "fact_alias": "f005",
                "financial_label": "TAX_WITHHELD",
                "roles": [
                    bound("date", 6, 2),
                    bound("amount", 6, 7),
                    bound("currency", 6, 8),
                    {"role": "asset", "status": "missing"},
                ],
            },
        ],
    }


def _client(*, label_response: dict, role_response: dict | None):
    captured: list[dict] = []

    def complete(*, form_data, **_kwargs):
        captured.append(json.loads(json.dumps(form_data, ensure_ascii=False)))
        name = form_data["response_format"]["json_schema"]["name"]
        if name == "broker_reports_gate3_labeling_response_v1":
            response = label_response
        else:
            assert name == "broker_reports_gate3_role_labeling_response_v1"
            assert role_response is not None
            response = role_response
        return {
            "id": f"gate3-role-response-{len(captured)}",
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

    user = SimpleNamespace(id="gate3-role-user")
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


def _active_role_table(root: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="gate3-role-user",
        normalization_run_id="gate3-role-run",
        case_id="gate3-role-case",
        workspace_model_id="gate3-role-workspace",
        allow_private=True,
    )
    document_id = "gate3-role-document"
    source_ref = "gate3-role-source"
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
            source_file_ref={"openwebui_file_id": "gate3-role-source"},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload={"synthetic_fixture": True},
        )
    )
    rows = [
        [
            "Type",
            "Date",
            "Description",
            "Asset",
            "Quantity",
            "Unit Price",
            "Amount",
            "Currency",
        ],
        ["BUY", "2026-01-10", "Trade", "ACME", "10", "12.50", "125.00", "USD"],
        ["SELL", "2026-02-11", "Trade", "ACME", "4", "15.00", "60.00", "USD"],
        [
            "DIVIDEND",
            "2026-03-12",
            "Cash Dividend ACME Class A",
            "",
            "",
            "",
            "8.00",
            "USD",
        ],
        ["FEE", "2026-02-11", "Commission", "", "", "", "1.25", "USD"],
        ["TAX", "2026-03-12", "Withholding Tax", "", "", "", "1.20", "USD"],
    ]
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="gate3-role-test-v1")
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "csv",
            "sha256": hashlib.sha256(b"gate3-role-table").hexdigest(),
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
        actor="gate3-role-test",
        reason="role-labeling synthetic seam",
    )
    return store, context, document_id
