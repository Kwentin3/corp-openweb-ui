from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from pathlib import Path

from broker_reports_gate1 import (
    GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION,
    GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5SupplementalFactDiscoveryRuntime,
    Gate5SupplementalFactDiscoveryRuntimeFactory,
    Gate5SupplementalFactRuntimeFactory,
    build_retention_policy,
)
from broker_reports_gate1 import (
    gate5_supplemental_fact_discovery as discovery_module,
)
from broker_reports_gate1.gate5_supplemental_fact_discovery import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
from test_broker_reports_gate4_sql_materialization import _publish_document


def test_reopened_runtime_discovers_same_run_fact_without_caller_refs(
    tmp_path: Path,
) -> None:
    config, store, context = _representative_case(tmp_path)
    gate4 = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    financial_case_before = gate4.list_by_financial_type(
        context=context,
        financial_type="SECURITY_DISPOSAL",
    )
    assert len(financial_case_before) == 1
    assert "acquisition_cost" not in {
        role["role"] for role in financial_case_before[0]["roles"]
    }
    methodology = _methodology()

    missing = _discovery_runtime(store).check(
        methodology=methodology,
        context=context,
    )

    assert missing["requirements"][0] == {
        "requirement_id": "acquisition-cost-required",
        "financial_type": "SECURITY_DISPOSAL",
        "value_key": "acquisition_cost",
        "subject_ref": "security-disposal-1",
        "status": "missing",
        "checks": {
            "financial_case": "partial",
            "supplemental_facts": "missing",
        },
        "source": None,
    }
    supplemental = _put_supplemental(
        store=store,
        context=context,
        amount="70000.00",
    )

    reopened_store = ArtifactStoreFactory(config).create()
    reopened_runtime = _discovery_runtime(reopened_store)
    satisfied = reopened_runtime.check(
        methodology=methodology,
        context=context,
    )

    assert satisfied["summary"] == {
        "requirements_total": 1,
        "satisfied": 1,
        "missing": 0,
    }
    requirement = satisfied["requirements"][0]
    assert requirement["status"] == "satisfied"
    assert requirement["checks"] == {
        "financial_case": "partial",
        "supplemental_facts": "found",
    }
    assert requirement["source"] == {
        "source_kind": "supplemental_fact",
        "supplemental_fact_ref": supplemental["supplemental_fact_ref"],
        "value": {
            "kind": "money",
            "amount": "70000.00",
            "currency": "RUB",
        },
        "scope_binding": supplemental["fact"]["scope_binding"],
        "provenance": {
            "source_kind": "user_provided_supplemental",
            "provided_by": "authenticated_user",
            "gate4_derived": False,
            "captured_via": "gate5_supplemental_fact_boundary_v0",
        },
    }
    financial_case_after = Gate4FinancialCaseRuntimeFactory(
        store=reopened_store,
        read_enabled=True,
    ).create().list_by_financial_type(
        context=context,
        financial_type="SECURITY_DISPOSAL",
    )
    assert financial_case_after == financial_case_before


def test_discovery_excludes_foreign_scope_and_other_run(tmp_path: Path) -> None:
    _config, store, context = _representative_case(tmp_path)
    _put_supplemental(
        store=store,
        context=replace(context, user_id="foreign-user"),
        amount="81000.00",
    )
    _put_supplemental(
        store=store,
        context=replace(context, case_id="foreign-case"),
        amount="82000.00",
    )
    _put_supplemental(
        store=store,
        context=replace(context, workspace_model_id="foreign-workspace"),
        amount="83000.00",
    )
    other_run = replace(context, normalization_run_id="g5-discovery-run-2")
    _put_supplemental(
        store=store,
        context=other_run,
        amount="84000.00",
    )
    _put_supplemental(
        store=store,
        context=context,
        amount="85000.00",
        subject_ref="security-disposal-other",
    )

    result = _discovery_runtime(ArtifactStoreFactory(_config).create()).check(
        methodology=_methodology(),
        context=context,
    )

    assert result["summary"] == {
        "requirements_total": 1,
        "satisfied": 0,
        "missing": 1,
    }
    assert result["requirements"][0]["status"] == "missing"
    assert result["requirements"][0]["source"] is None


def test_factory_uses_case_catalog_then_unchanged_g5_4_boundary() -> None:
    factory_source = inspect.getsource(
        Gate5SupplementalFactDiscoveryRuntimeFactory.create
    )
    runtime_source = inspect.getsource(Gate5SupplementalFactDiscoveryRuntime)
    module_source = inspect.getsource(discovery_module)
    parameters = inspect.signature(
        Gate5SupplementalFactDiscoveryRuntime.check
    ).parameters
    tree = ast.parse(module_source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert tuple(parameters) == ("self", "methodology", "context")
    assert "Gate5SupplementalFactDiscoveryRuntimeFactory.create" in FACTORY_REQUIRED
    assert "ArtifactResolver.catalog_case" in FACTORY_REQUIRED[1]
    assert "Gate5CombinedRequirementCheckRuntimeFactory.create" in FACTORY_REQUIRED[2]
    assert "caller-provided supplemental refs or scope identity" in FORBIDDEN
    assert "ArtifactResolver(self._store)" in factory_source
    assert "Gate5CombinedRequirementCheckRuntimeFactory(" in factory_source
    assert "self._resolver.catalog_case(context)" in runtime_source
    assert "self._combined.check(" in runtime_source
    assert "supplemental_fact_refs=" in runtime_source
    assert imports == {
        "__future__",
        "typing",
        "artifact_models",
        "artifact_resolver",
        "gate5_combined_requirement_check",
        "gate5_supplemental_fact",
    }
    for forbidden_path in (
        "self._store",
        "put_record(",
        "get_record_unchecked(",
        "read_payload(",
        "list_by_case_context(",
        "sqlite3",
    ):
        assert forbidden_path not in runtime_source
    for representative_literal in (
        "SECURITY_DISPOSAL",
        "acquisition_cost",
        "70000.00",
    ):
        assert representative_literal not in module_source


def _representative_case(
    tmp_path: Path,
) -> tuple[ArtifactStoreConfig, object, ArtifactAccessContext]:
    config = ArtifactStoreConfig(
        mode="sqlite",
        sqlite_path=tmp_path / "artifacts.sqlite3",
        payload_root=tmp_path / "payloads",
    )
    store = ArtifactStoreFactory(config).create()
    context = ArtifactAccessContext(
        user_id="g5-discovery-user",
        normalization_run_id="g5-discovery-run-1",
        case_id="g5-discovery-case",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    _publish_document(
        store=store,
        context=context,
        document_id="gate5-discovery-document",
        financial_types=("SECURITY_DISPOSAL",),
        sidecar_artifact_id="g3-v2-gate5-discovery",
        created_at="2026-08-09T13:00:00+00:00",
    )
    Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    return config, store, context


def _discovery_runtime(store) -> Gate5SupplementalFactDiscoveryRuntime:
    return Gate5SupplementalFactDiscoveryRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _supplemental_runtime(store):
    return Gate5SupplementalFactRuntimeFactory(
        store=store,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _methodology() -> dict:
    return {
        "schema_version": GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION,
        "requirements": [
            {
                "requirement_id": "acquisition-cost-required",
                "financial_type": "SECURITY_DISPOSAL",
                "value_key": "acquisition_cost",
                "subject_ref": "security-disposal-1",
            }
        ],
    }


def _put_supplemental(
    *,
    store,
    context: ArtifactAccessContext,
    amount: str,
    subject_ref: str = "security-disposal-1",
) -> dict:
    return _supplemental_runtime(store).put(
        supplemental_input={
            "schema_version": GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
            "requirement_ref": "acquisition-cost-required",
            "subject_ref": subject_ref,
            "fact_key": "acquisition_cost",
            "value": {
                "kind": "money",
                "amount": amount,
                "currency": "RUB",
            },
        },
        context=context,
    )
