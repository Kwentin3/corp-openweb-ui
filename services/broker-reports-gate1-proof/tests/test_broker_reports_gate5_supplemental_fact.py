from __future__ import annotations

import ast
import copy
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE,
    GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
    GATE5_SUPPLEMENTAL_FACT_RESULT_SCHEMA_VERSION,
    GATE5_SUPPLEMENTAL_FACT_SCHEMA_VERSION,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5SupplementalFactError,
    Gate5SupplementalFactRuntime,
    Gate5SupplementalFactRuntimeFactory,
    build_retention_policy,
)
from broker_reports_gate1 import gate5_supplemental_fact as supplemental_module
from broker_reports_gate1.artifact_models import ArtifactRecord, new_artifact_id
from broker_reports_gate1.gate5_supplemental_fact import FACTORY_REQUIRED, FORBIDDEN
from test_broker_reports_gate4_sql_materialization import _publish_document


def test_supplemental_fact_persists_across_reopen_without_mutating_financial_case(
    tmp_path: Path,
) -> None:
    config, store, context = _store_context(tmp_path)
    _publish_document(
        store=store,
        context=context,
        document_id="gate5-supplemental-document",
        financial_types=("SECURITY_DISPOSAL",),
        sidecar_artifact_id="g3-v2-gate5-supplemental",
        created_at="2026-08-09T11:00:00+00:00",
    )
    gate4 = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    gate4.rebuild_case(context=context)
    financial_case_before = gate4.list_by_financial_type(
        context=context,
        financial_type="SECURITY_DISPOSAL",
    )
    assert len(financial_case_before) == 1
    assert "acquisition_cost" not in {
        role["role"] for role in financial_case_before[0]["roles"]
    }

    supplemental_input = _supplemental_input()
    unchanged_input = copy.deepcopy(supplemental_input)
    runtime = _runtime(store)

    stored = runtime.put(
        supplemental_input=supplemental_input,
        context=context,
    )

    assert supplemental_input == unchanged_input
    assert stored["schema_version"] == GATE5_SUPPLEMENTAL_FACT_RESULT_SCHEMA_VERSION
    assert stored["status"] == "stored"
    assert stored["fact"] == {
        "schema_version": GATE5_SUPPLEMENTAL_FACT_SCHEMA_VERSION,
        "supplemental_fact_ref": stored["supplemental_fact_ref"],
        "requirement_ref": "acquisition-cost-required",
        "subject_ref": "security-disposal-1",
        "fact_key": "acquisition_cost",
        "value": {
            "kind": "money",
            "amount": "70000.00",
            "currency": "RUB",
        },
        "scope_binding": {
            "scope_kind": "case",
            "case_id": context.case_id,
            "normalization_run_id": context.normalization_run_id,
            "workspace_model_id": context.workspace_model_id,
        },
        "provenance": {
            "source_kind": "user_provided_supplemental",
            "provided_by": "authenticated_user",
            "gate4_derived": False,
            "captured_via": "gate5_supplemental_fact_boundary_v0",
        },
    }
    stored_record = store.get_record_unchecked(stored["supplemental_fact_ref"])
    assert stored_record is not None
    assert stored_record.visibility == "private_case"
    assert stored_record.storage_backend == "project_artifact_payload"
    assert stored_record.payload is None
    assert stored_record.payload_ref
    assert stored_record.user_id == context.user_id
    assert stored_record.case_id == context.case_id

    reopened_store = ArtifactStoreFactory(config).create()
    reopened_runtime = _runtime(reopened_store)
    read_back = reopened_runtime.get(
        supplemental_fact_ref=stored["supplemental_fact_ref"],
        context=context,
    )

    assert read_back["status"] == "found"
    assert read_back["supplemental_fact_ref"] == stored["supplemental_fact_ref"]
    assert read_back["fact"] == stored["fact"]

    financial_case_after = Gate4FinancialCaseRuntimeFactory(
        store=reopened_store,
        read_enabled=True,
    ).create().list_by_financial_type(
        context=context,
        financial_type="SECURITY_DISPOSAL",
    )
    assert financial_case_after == financial_case_before
    assert "acquisition_cost" not in {
        role["role"] for role in financial_case_after[0]["roles"]
    }


def test_invalid_input_foreign_scope_and_missing_ref_fail_closed(
    tmp_path: Path,
) -> None:
    _config, store, context = _store_context(tmp_path)
    runtime = _runtime(store)
    invalid = _supplemental_input()
    invalid["case_id"] = "caller-controlled-case"
    records_before = _supplemental_records(store, context)

    with pytest.raises(Gate5SupplementalFactError) as invalid_error:
        runtime.put(supplemental_input=invalid, context=context)

    assert invalid_error.value.code == "gate5_supplemental_fact_input_invalid"
    assert _supplemental_records(store, context) == records_before == []

    stored = runtime.put(
        supplemental_input=_supplemental_input(),
        context=context,
    )
    supplemental_fact_ref = stored["supplemental_fact_ref"]
    for foreign_context in (
        replace(context, user_id="foreign-user"),
        replace(context, case_id="foreign-case"),
    ):
        with pytest.raises(ArtifactStoreError) as foreign_error:
            runtime.get(
                supplemental_fact_ref=supplemental_fact_ref,
                context=foreign_context,
            )
        assert foreign_error.value.code == "artifact_access_denied"

    missing_ref = "art_" + "A" * 32
    missing = runtime.get(
        supplemental_fact_ref=missing_ref,
        context=context,
    )
    assert missing == {
        "schema_version": GATE5_SUPPLEMENTAL_FACT_RESULT_SCHEMA_VERSION,
        "status": "missing",
        "supplemental_fact_ref": missing_ref,
        "fact": None,
    }

    wrong_type_ref = new_artifact_id()
    store.put_record(
        ArtifactRecord(
            artifact_id=wrong_type_ref,
            artifact_type="validation_result_v0",
            case_id=context.case_id,
            chat_id=None,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            retention_policy=build_retention_policy(mode="synthetic_dev"),
            access_policy={"scope": "case_private"},
            validation_status="validated",
            lifecycle_status="visible_safe",
            payload={"schema_version": "validation_result_v0"},
        )
    )
    with pytest.raises(Gate5SupplementalFactError) as wrong_type:
        runtime.get(
            supplemental_fact_ref=wrong_type_ref,
            context=context,
        )
    assert (
        wrong_type.value.code
        == "gate5_supplemental_fact_artifact_type_invalid"
    )


def test_factory_and_source_reuse_artifactstore_without_gate4_or_sql_mutation() -> None:
    factory_source = inspect.getsource(Gate5SupplementalFactRuntimeFactory.create)
    runtime_source = inspect.getsource(Gate5SupplementalFactRuntime)
    module_source = inspect.getsource(supplemental_module)
    tree = ast.parse(module_source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert "Gate5SupplementalFactRuntimeFactory.create" in FACTORY_REQUIRED
    assert "ArtifactStoreFactory.create" in FACTORY_REQUIRED[1]
    assert "ArtifactResolver.resolve" in FACTORY_REQUIRED[2]
    assert "caller-provided user, case, run or workspace identity" in FORBIDDEN
    assert "ArtifactResolver(self._store)" in factory_source
    assert ".put_record(" in runtime_source
    assert "._resolver.resolve(" in runtime_source
    assert imports == {
        "__future__",
        "copy",
        "re",
        "typing",
        "artifact_models",
        "artifact_resolver",
    }
    for forbidden_import_or_call in (
        "SqliteArtifactStoreAdapter(",
        "Gate4FinancialCaseRuntimeFactory(",
        "sqlite3.connect(",
        "CanonicalReader",
        "generate_chat_completion",
    ):
        assert forbidden_import_or_call not in runtime_source
    for representative_literal in (
        "SECURITY_DISPOSAL",
        "acquisition_cost",
        "70000.00",
    ):
        assert representative_literal not in module_source


def _store_context(
    tmp_path: Path,
) -> tuple[ArtifactStoreConfig, object, ArtifactAccessContext]:
    config = ArtifactStoreConfig(
        mode="sqlite",
        sqlite_path=tmp_path / "artifacts.sqlite3",
        payload_root=tmp_path / "payloads",
    )
    store = ArtifactStoreFactory(config).create()
    context = ArtifactAccessContext(
        user_id="g5-supplemental-user",
        normalization_run_id="g5-supplemental-run-1",
        case_id="g5-supplemental-case",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    return config, store, context


def _runtime(store) -> Gate5SupplementalFactRuntime:
    return Gate5SupplementalFactRuntimeFactory(
        store=store,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _supplemental_input() -> dict:
    return {
        "schema_version": GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
        "requirement_ref": "acquisition-cost-required",
        "subject_ref": "security-disposal-1",
        "fact_key": "acquisition_cost",
        "value": {
            "kind": "money",
            "amount": "70000.00",
            "currency": "RUB",
        },
    }


def _supplemental_records(store, context: ArtifactAccessContext) -> list:
    return [
        record
        for record in store.list_by_case_context(context)
        if record.artifact_type == GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE
    ]
