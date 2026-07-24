from __future__ import annotations

import ast
import asyncio
import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.artifact_lifecycle import (  # noqa: E402
    lifecycle_for_visibility,
)
from broker_reports_gate1.artifact_models import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
    RetentionPolicy,
)
from broker_reports_gate1.artifact_store import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.gate2_financial_evidence_production_runtime import (  # noqa: E402
    FINANCIAL_CONTEXT_ARTIFACT_TYPE,
    FINANCIAL_INPUT_ARTIFACT_TYPE,
    FINANCIAL_RECEIPT_ARTIFACT_TYPE,
    FINANCIAL_RUN_ARTIFACT_TYPE,
    Gate2FinancialEvidenceProductionConfig,
    Gate2FinancialEvidenceProductionRuntimeError,
    Gate2FinancialEvidenceProductionRuntimeFactory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)


MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_production_runtime.py"
)
DOMAIN_PACKAGE_TYPE = "broker_reports_domain_extraction_package_v0"


class _MemoryStore:
    def __init__(self):
        self.records = {}

    def put_record(self, record):
        if record.artifact_id in self.records:
            raise AssertionError("duplicate artifact id")
        self.records[record.artifact_id] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def get_record_unchecked(self, artifact_id):
        value = self.records.get(artifact_id)
        return copy.deepcopy(value) if value is not None else None

    def read_payload(self, record):
        return copy.deepcopy(self.records[record.artifact_id].payload)


class _DecisionClient:
    def __init__(self):
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(kwargs)
        source_values = kwargs["package"]["llm_context_package"][
            "source_values"
        ]
        return Gate2StructuredModelResult(
            content={
                "decision": {
                    "disposition": "unclassified_financial_input",
                    "value_bindings": [
                        {
                            "role_id": item["allowed_roles"][0],
                            "source_value_ref": item["source_value_ref"],
                        }
                        for item in source_values
                    ],
                    "reason_code": "no_registry_type",
                }
            },
            execution_metadata=Gate2ProviderExecutionMetadata(
                provider_id="openai",
                provider_profile_id="openai_gpt",
                provider_profile_revision="test",
                adapter_id="openai_response_format",
                adapter_version="test",
                requested_model_id=kwargs["model_id"],
                structured_output_mode=(
                    "openwebui_response_format_json_schema"
                ),
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
            ),
        )


class _MissingMetadataDecisionClient(_DecisionClient):
    async def extract(self, **kwargs):
        result = await super().extract(**kwargs)
        return Gate2StructuredModelResult(content=result.content)


def _retention():
    return RetentionPolicy(
        mode="case",
        ttl_seconds=None,
        expires_at=None,
        explicit=True,
    )


def _context(user_id="user:a"):
    return ArtifactAccessContext(
        user_id=user_id,
        normalization_run_id="run:synthetic",
        case_id="case:synthetic",
        chat_id="chat:synthetic",
        workspace_model_id="workspace:synthetic",
        allow_private=True,
        require_source_available=True,
    )


def _domain_package():
    return {
        "schema_version": DOMAIN_PACKAGE_TYPE,
        "document_ref": "document:synthetic",
        "allowed_source_value_refs": [
            "value:label",
            "value:amount",
        ],
        "allowed_evidence_refs": ["evidence:table"],
        "coverage_expectation": {
            "selected_source_refs": ["source:selected:1"]
        },
        "source_unit": {
            "unit_kind": "table_row_window",
            "table_ref": "table:synthetic",
            "source_value_index": [
                {
                    "source_value_ref": "value:label",
                    "cell_ref": "cell:label",
                },
                {
                    "source_value_ref": "value:amount",
                    "cell_ref": "cell:amount",
                },
            ],
            "model_source_projection": {
                "segments": [
                    {
                        "source_value_ref": "value:label",
                        "value": "Synthetic total",
                        "page_ref": "page:1",
                    },
                    {
                        "source_value_ref": "value:amount",
                        "value": "120.50",
                        "page_ref": "page:1",
                    },
                ]
            },
            "private_values": [],
        },
    }


def _table_domain_package():
    package = _domain_package()
    package["source_unit"]["model_source_projection"] = {
        "rows": [
            {
                "row_ref": "row:synthetic",
                "cells": [
                    {
                        "cell_ref": "cell:label",
                        "source_value_ref": "value:label",
                        "value": "Synthetic total",
                    },
                    {
                        "cell_ref": "cell:amount",
                        "source_value_ref": "value:amount",
                        "value": "120.50",
                    },
                ],
            }
        ]
    }
    return package


def _source_record(
    context,
    *,
    storage_backend="memory",
    payload=None,
):
    return ArtifactRecord(
        artifact_id="artifact:domain-package",
        artifact_type=DOMAIN_PACKAGE_TYPE,
        case_id=context.case_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        workspace_model_id=context.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        document_id="document:synthetic",
        source_file_ref={"source_deleted": False},
        visibility="private_case",
        storage_backend=storage_backend,
        retention_policy=_retention(),
        access_policy={
            "requires_user_id": True,
            "requires_case_or_chat": True,
        },
        validation_status="validated",
        lifecycle_status=lifecycle_for_visibility(
            visibility="private_case",
            validation_status="validated",
        ),
        payload=payload or _domain_package(),
    )


def _runtime(store, client):
    return Gate2FinancialEvidenceProductionRuntimeFactory(
        store=store,
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        model_client=client,
        config=Gate2FinancialEvidenceProductionConfig(
            model_id="gpt-test",
            provider_profile_id="openai_gpt",
            maximum_scopes=4,
        ),
    ).create()


def test_production_runtime_materializes_authoritative_table_row_values():
    context = _context()
    store = _MemoryStore()
    store.put_record(
        _source_record(context, payload=_table_domain_package())
    )
    client = _DecisionClient()

    result = asyncio.run(
        _runtime(store, client).run(
            domain_package_refs=("artifact:domain-package",),
            source_extraction_run_ref="artifact:domain-run",
            context=context,
            retention_policy=_retention(),
        )
    )

    assert result.status == "completed"
    assert len(client.calls) == 1
    source_values = {
        item["source_value_ref"]: item["literal_value"]
        for item in client.calls[0]["package"]["llm_context_package"][
            "source_values"
        ]
    }
    assert {
        key: source_values[key]
        for key in ("value:amount", "value:label")
    } == {
        "value:amount": "120.50",
        "value:label": "Synthetic total",
    }


def test_production_runtime_rejects_conflicting_table_row_literals():
    context = _context()
    store = _MemoryStore()
    package = _table_domain_package()
    package["source_unit"]["model_source_projection"]["rows"][0][
        "cells"
    ].append(
        {
            "cell_ref": "cell:amount:conflict",
            "source_value_ref": "value:amount",
            "value": "999.99",
        }
    )
    store.put_record(_source_record(context, payload=package))

    with pytest.raises(
        Gate2FinancialEvidenceProductionRuntimeError,
        match="financial_evidence_production_authoritative_value_conflict",
    ):
        asyncio.run(
            _runtime(store, _DecisionClient()).run(
                domain_package_refs=("artifact:domain-package",),
                source_extraction_run_ref="artifact:domain-run",
                context=context,
                retention_policy=_retention(),
            )
        )


def test_production_runtime_single_writes_new_private_schema_and_context():
    context = _context()
    store = _MemoryStore()
    store.put_record(_source_record(context))
    client = _DecisionClient()

    result = asyncio.run(
        _runtime(store, client).run(
            domain_package_refs=("artifact:domain-package",),
            source_extraction_run_ref="artifact:domain-run",
            context=context,
            retention_policy=_retention(),
        )
    )

    assert result.status == "completed"
    assert len(client.calls) == 1
    assert result.safe_summary["write_policy"] == "new_schema_only"
    assert result.safe_summary["legacy_read_policy"] == "dual_read"
    assert result.safe_summary["uncovered_source_refs_total"] == 0
    assert result.safe_summary["duplicate_interpretations_total"] == 0
    written = [
        record
        for artifact_id, record in store.records.items()
        if artifact_id != "artifact:domain-package"
    ]
    assert {record.artifact_type for record in written} == {
        FINANCIAL_INPUT_ARTIFACT_TYPE,
        FINANCIAL_CONTEXT_ARTIFACT_TYPE,
        FINANCIAL_RECEIPT_ARTIFACT_TYPE,
        FINANCIAL_RUN_ARTIFACT_TYPE,
    }
    assert all(record.visibility == "private_case" for record in written)
    assert all(record.user_id == context.user_id for record in written)
    assert all(
        record.normalization_run_id == context.normalization_run_id
        for record in written
    )
    assert not any(
        record.artifact_type.endswith("_v0")
        for record in written
    )


def test_production_runtime_fails_closed_for_cross_tenant_package_ref():
    owner = _context("user:owner")
    caller = _context("user:caller")
    store = _MemoryStore()
    store.put_record(_source_record(owner))

    with pytest.raises(ArtifactStoreError) as rejected:
        asyncio.run(
            _runtime(store, _DecisionClient()).run(
                domain_package_refs=("artifact:domain-package",),
                source_extraction_run_ref="artifact:domain-run",
                context=caller,
                retention_policy=_retention(),
            )
        )

    assert rejected.value.code == "artifact_access_denied"
    assert len(store.records) == 1


def test_production_runtime_rejects_missing_provider_contract_without_writes():
    context = _context()
    store = _MemoryStore()
    store.put_record(_source_record(context))

    with pytest.raises(
        Gate2FinancialEvidenceProductionRuntimeError
    ) as rejected:
        asyncio.run(
            _runtime(store, _MissingMetadataDecisionClient()).run(
                domain_package_refs=("artifact:domain-package",),
                source_extraction_run_ref="artifact:domain-run",
                context=context,
                retention_policy=_retention(),
            )
        )

    assert rejected.value.code == (
        "financial_evidence_production_qualification_failed"
    )
    assert len(store.records) == 1


def test_production_runtime_persists_through_sqlite_store_factory(tmp_path):
    context = _context()
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    store.put_record(
        _source_record(
            context,
            storage_backend="project_artifact_payload",
        )
    )

    result = asyncio.run(
        _runtime(store, _DecisionClient()).run(
            domain_package_refs=("artifact:domain-package",),
            source_extraction_run_ref="artifact:domain-run",
            context=context,
            retention_policy=_retention(),
        )
    )

    records = store.list_by_run(context.normalization_run_id)
    assert result.status == "completed"
    assert {record.artifact_type for record in records} >= {
        DOMAIN_PACKAGE_TYPE,
        FINANCIAL_INPUT_ARTIFACT_TYPE,
        FINANCIAL_CONTEXT_ARTIFACT_TYPE,
        FINANCIAL_RECEIPT_ARTIFACT_TYPE,
        FINANCIAL_RUN_ARTIFACT_TYPE,
    }
    assert all(
        record.user_id == context.user_id for record in records
    )


def test_production_runtime_rejects_invalid_config_and_scope_budget():
    with pytest.raises(
        Gate2FinancialEvidenceProductionRuntimeError
    ) as rejected:
        Gate2FinancialEvidenceProductionRuntimeFactory(
            store=_MemoryStore(),
            registry=Gate2FinancialEvidenceRegistryFactory().create(),
            model_client=_DecisionClient(),
            config=Gate2FinancialEvidenceProductionConfig(
                model_id="",
                provider_profile_id="openai_gpt",
            ),
        ).create()

    assert rejected.value.code == (
        "financial_evidence_production_config_invalid"
    )


def test_production_runtime_has_no_direct_db_or_provider_bypass():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    }

    assert "sqlite3" not in imports
    assert not any(name.startswith("requests") for name in imports)
    assert "execute" not in calls
    assert "post" not in calls
    assert "extract" in calls
    assert "put_record" in calls
