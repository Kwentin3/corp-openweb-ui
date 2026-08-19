from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from broker_reports_gate1 import (
    GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION,
    GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE_SHA256,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE_SHA256,
    GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V1_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID,
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_BEHAVIOR_ID,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION,
    GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID,
    GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT,
    GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
    GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
    GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
    GATE5_TRUSTED_METHODOLOGY_ID,
    GATE5_TRUSTED_METHODOLOGY_RESOURCE,
    GATE5_TRUSTED_METHODOLOGY_VERSION,
    GATE5_TYPED_BEHAVIOR_RESULT_SCHEMA_VERSION,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5PublishedTypedBehaviorError,
    Gate5PublishedTypedBehaviorRegistryFactory,
    Gate5PublishedTypedBehaviorRuntime,
    Gate5PublishedTypedBehaviorRuntimeFactory,
    Gate5RuntimeCapabilityContractFactory,
    Gate5RuntimeCapabilityContractV1Factory,
    Gate5RuntimeCapabilityError,
    Gate5RuntimeCapabilityResolverFactory,
    Gate5RuntimeCapabilityResolverV1Factory,
    Gate5TrustedMethodologyCalculationRuntimeFactory,
    build_retention_policy,
)
from broker_reports_gate1 import gate5_published_typed_behavior as typed_module
from broker_reports_gate1.gate5_published_typed_behavior import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
import test_broker_reports_gate4_sql_materialization as gate4_fixtures
import test_broker_reports_gate5_methodology_calculation as calculation_fixtures
import test_broker_reports_gate5_securities_disposal_tax_model as model_fixtures


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
CALCULATION_BEHAVIOR_REF = {
    "schema_version": GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
    "methodology_id": GATE5_TRUSTED_METHODOLOGY_ID,
    "methodology_version": GATE5_TRUSTED_METHODOLOGY_VERSION,
    "behavior_id": GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID,
}


def test_v1_contract_replaces_only_execute_family_and_v0_stays_exact() -> None:
    v0_raw = (PACKAGE_ROOT / GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE).read_bytes()
    v1_raw = (PACKAGE_ROOT / GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE).read_bytes()
    assert hashlib.sha256(v0_raw).hexdigest() == (
        GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE_SHA256
    )
    assert hashlib.sha256(v1_raw).hexdigest() == (
        GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE_SHA256
    )

    v0 = Gate5RuntimeCapabilityContractFactory.create()
    v1 = Gate5RuntimeCapabilityContractV1Factory.create()
    v0_ids = {item["capability_id"] for item in v0.snapshot()["capabilities"]}
    v1_ids = {item["capability_id"] for item in v1.snapshot()["capabilities"]}

    assert len(v0_ids) == len(v1_ids) == 5
    assert v0_ids - v1_ids == {"execute_published_calculation_behavior_v0"}
    assert v1_ids - v0_ids == {"execute_published_typed_behavior_v1"}
    assert len(v0.model_projection_bytes()) == 6775
    assert (
        v1.model_projection()["schema_version"]
        == GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V1_SCHEMA_VERSION
    )
    v1_projection = v1.model_projection_bytes()
    assert len(v1_projection) == 7461
    serialized_projection = v1_projection.decode("utf-8")
    assert "execute_published_typed_behavior_v1" in serialized_projection
    for forbidden in (
        "conformance",
        "gate5.trusted_calculation.v0",
        "gate5.operation_tax_model.v0",
        "Gate5",
        "RuntimeFactory",
        ".py",
        "filesystem",
    ):
        assert forbidden not in serialized_projection

    legacy = Gate5RuntimeCapabilityResolverFactory.create().resolve(
        _capability_ref(
            "execute_published_calculation_behavior_v0",
            schema_version=GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION,
        )
    )
    assert legacy.operations == ("calculate",)
    with pytest.raises(Gate5RuntimeCapabilityError) as unsupported:
        Gate5RuntimeCapabilityResolverFactory.create().resolve(
            _capability_ref(
                "execute_published_typed_behavior_v1",
                schema_version=GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION,
            )
        )
    assert getattr(unsupported.value, "code", None) == (
        "gate5_runtime_capability_unsupported"
    )


def test_g57_behavior_has_v1_semantic_parity_and_retained_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, store, context = calculation_fixtures._representative_case(
        tmp_path,
        monkeypatch,
    )
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="acquisition-cost-required",
        fact_key="acquisition_cost",
        amount="70.00",
    )
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="transaction-expense-required",
        fact_key="transaction_expense",
        amount="2.00",
    )
    old_result = (
        Gate5TrustedMethodologyCalculationRuntimeFactory(
            store=store,
            read_enabled=True,
            retention_policy=_retention(),
        )
        .create()
        .calculate(methodology_ref=_calculation_methodology_ref(), context=context)
    )

    result = _typed_runtime(store).execute(
        behavior_ref=_calculation_behavior_ref(),
        input_contract_id=GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION,
        output_contract_id=GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
        behavior_input={
            "schema_version": GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION
        },
        context=context,
    )

    assert result["schema_version"] == GATE5_TYPED_BEHAVIOR_RESULT_SCHEMA_VERSION
    assert result["status"] == "executed"
    assert result["result_payload"] == old_result
    assert result["result_payload"]["calculation_result"]["outputs"] == {
        "proceeds": _money("100.00"),
        "recognized_expense": _money("72.00"),
        "net_result": _money("28.00"),
    }
    assert result["behavior_binding"] == {
        "methodology_id": GATE5_TRUSTED_METHODOLOGY_ID,
        "methodology_version": GATE5_TRUSTED_METHODOLOGY_VERSION,
        "behavior_id": GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID,
        "input_contract_id": (GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION),
        "output_contract_id": GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
    }
    assert result["artifact_binding"] == old_result["authority_binding"]
    assert result["provenance"] == {
        "retention": "exact_in_result_payload",
        "source_kinds": [
            "financial_case",
            "supplemental_fact",
            "user_provided_supplemental",
        ],
        "includes_methodology_derived_result": True,
    }


def test_public_typed_execute_produces_two_members_accepted_by_public_aggregate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    first, first_context = _execute_operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="a",
        gross="100.00",
        acquisition="70.00",
        fee="2.00",
    )
    second, second_context = _execute_operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="b",
        gross="50.00",
        acquisition="28.00",
        fee="2.00",
        fee_documented=False,
    )

    registry_binding = Gate5PublishedTypedBehaviorRegistryFactory.create().describe(
        _operation_behavior_ref()
    )
    assert registry_binding["output_contract_id"] == (
        GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
    )
    assert registry_binding["output_contract_id"] == (
        GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT
    )
    assert first["behavior_binding"]["output_contract_id"] == (
        GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT
    )

    members = [
        _member("operation-a", "case-a", first["result_payload"]),
        _member("operation-b", "case-b", second["result_payload"]),
    ]
    aggregate = (
        Gate5RuntimeCapabilityResolverV1Factory.create()
        .resolve(_capability_ref("aggregate_complete_category_scope_v0"))
        .create_runtime()
    )
    scope = _scope()
    binding = aggregate.describe_scope(scope=scope, members=members)
    complete = aggregate.run(
        scope=scope,
        members=members,
        completeness_evidence=_completeness(binding["scope_binding_sha256"]),
    )

    assert complete["status"] == "complete"
    assert complete["category_tax_model"]["category_gross_income"]["value"] == (
        _money("150.00")
    )
    assert complete["category_tax_model"]["related_expenses"]["value"] == (
        _money("102.00")
    )
    assert complete["category_tax_model"]["allowable_expenses"]["value"] == (
        _money("100.00")
    )
    assert {
        item
        for result in (first, second)
        for item in result["provenance"]["source_kinds"]
    } == {
            "financial_case",
            "methodology_derived",
            "methodology_derived_result",
            "proof_assumption",
        "supplemental_fact",
        "user_provided_supplemental",
    }
    assert calculation_fixtures._financial_case(store=store, context=first_context)
    assert calculation_fixtures._financial_case(store=store, context=second_context)


@pytest.mark.parametrize(
    ("behavior_ref", "input_contract_id", "output_contract_id", "expected"),
    (
        (
            {
                "schema_version": GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
                "methodology_id": (GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID),
                "methodology_version": (
                    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION
                ),
                "behavior_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_BEHAVIOR_ID,
            },
            GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION,
            GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
            "gate5_published_typed_behavior_unsupported",
        ),
        (
            CALCULATION_BEHAVIOR_REF,
            "caller_schema_v9",
            GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
            "gate5_published_typed_behavior_input_contract_mismatch",
        ),
        (
            CALCULATION_BEHAVIOR_REF,
            GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION,
            "caller_schema_v9",
            "gate5_published_typed_behavior_output_contract_mismatch",
        ),
        (
            CALCULATION_BEHAVIOR_REF,
            GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION,
            GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT,
            "gate5_published_typed_behavior_output_contract_mismatch",
        ),
        (
            CALCULATION_BEHAVIOR_REF,
            "arbitrary schema contents are not an identity",
            GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
            "gate5_published_typed_behavior_input_contract_invalid",
        ),
    ),
)
def test_unknown_behavior_and_contract_combinations_fail_before_owner_execution(
    tmp_path: Path,
    behavior_ref: dict,
    input_contract_id: str,
    output_contract_id: str,
    expected: str,
) -> None:
    store, context = _empty_store_and_context(tmp_path)

    with pytest.raises(Gate5PublishedTypedBehaviorError) as caught:
        _typed_runtime(store).execute(
            behavior_ref=behavior_ref,
            input_contract_id=input_contract_id,
            output_contract_id=output_contract_id,
            behavior_input={
                "schema_version": (GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION)
            },
            context=context,
        )

    assert caught.value.code == expected


def test_malformed_registered_output_and_missing_provenance_fail_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, store, context = calculation_fixtures._representative_case(
        tmp_path,
        monkeypatch,
    )
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="acquisition-cost-required",
        fact_key="acquisition_cost",
        amount="70.00",
    )
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="transaction-expense-required",
        fact_key="transaction_expense",
        amount="2.00",
    )
    runtime = _typed_runtime(store)
    executed = runtime.execute(
        behavior_ref=_calculation_behavior_ref(),
        input_contract_id=GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION,
        output_contract_id=GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
        behavior_input={
            "schema_version": GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION
        },
        context=context,
    )

    malformed = {**executed["result_payload"], "caller_extra": True}
    with pytest.raises(Gate5PublishedTypedBehaviorError) as malformed_error:
        runtime.validate_registered_output(
            behavior_ref=_calculation_behavior_ref(),
            input_contract_id=GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION,
            output_contract_id=GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
            payload=malformed,
        )
    assert malformed_error.value.code == (
        "gate5_published_typed_behavior_output_validation_failed"
    )

    without_provenance = copy.deepcopy(executed["result_payload"])
    _remove_key_recursively(without_provenance, "source_kind")
    with pytest.raises(Gate5PublishedTypedBehaviorError) as provenance_error:
        runtime.validate_registered_output(
            behavior_ref=_calculation_behavior_ref(),
            input_contract_id=GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION,
            output_contract_id=GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
            payload=without_provenance,
        )
    assert provenance_error.value.code == (
        "gate5_published_typed_behavior_provenance_missing"
    )


def test_public_execute_signature_cannot_accept_implementation_or_schema_code() -> None:
    signature = inspect.signature(Gate5PublishedTypedBehaviorRuntime.execute)
    assert set(signature.parameters) == {
        "self",
        "behavior_ref",
        "input_contract_id",
        "output_contract_id",
        "behavior_input",
        "context",
    }
    assert all(
        parameter.kind is not inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    assert any("Factory.create" in item for item in FACTORY_REQUIRED)
    assert any("dynamic import" in item for item in FORBIDDEN)

    source = inspect.getsource(typed_module)
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "importlib" not in imported
    assert not {"importlib.util", "importlib.machinery"} & imported_from
    assert not {"eval", "exec", "__import__"} & calls
    for forbidden in (
        "import_module(",
        "entry_points(",
        "implementation_ref",
        "callable_ref",
        "fallback_behavior",
    ):
        assert forbidden not in source


def test_artifact_hash_drift_fails_through_v1_before_case_reads(
    tmp_path: Path,
) -> None:
    package_copy = tmp_path / "broker_reports_gate1"
    shutil.copytree(
        PACKAGE_ROOT,
        package_copy,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    resource = package_copy / GATE5_TRUSTED_METHODOLOGY_RESOURCE
    resource.write_bytes(
        resource.read_bytes().replace(
            b"experimental-security-disposal-net-result-v0",
            b"unapproved-security-disposal-net-result-v0",
            1,
        )
    )
    script = """
from pathlib import Path
from broker_reports_gate1 import (
    ArtifactAccessContext, ArtifactStoreConfig, ArtifactStoreFactory,
    GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION as I,
    GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION as B,
    GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION as R,
    GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID as X,
    GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION as O,
    GATE5_TRUSTED_METHODOLOGY_ID as M,
    GATE5_TRUSTED_METHODOLOGY_VERSION as V,
    Gate5RuntimeCapabilityResolverV1Factory, build_retention_policy,
)
store=ArtifactStoreFactory(ArtifactStoreConfig(mode='sqlite', sqlite_path=Path('a.sqlite3'), payload_root=Path('payloads'))).create()
context=ArtifactAccessContext(user_id='u', normalization_run_id='r', case_id='c', workspace_model_id='broker-reports-ndfl', allow_private=True)
runtime=Gate5RuntimeCapabilityResolverV1Factory.create().resolve({'schema_version':R,'capability_id':'execute_published_typed_behavior_v1'}).create_runtime(store=store,read_enabled=True,retention_policy=build_retention_policy(mode='synthetic_dev'))
runtime.execute(behavior_ref={'schema_version':B,'methodology_id':M,'methodology_version':V,'behavior_id':X},input_contract_id=I,output_contract_id=O,behavior_input={'schema_version':I},context=context)
"""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "gate5_trusted_methodology_resource_hash_mismatch" in completed.stderr


def test_versioned_contracts_registry_and_g523_payload_are_closed_world_in_package_copy(
    tmp_path: Path,
) -> None:
    package_copy = tmp_path / "broker_reports_gate1"
    shutil.copytree(
        PACKAGE_ROOT,
        package_copy,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    script = """
import hashlib
from broker_reports_gate1 import Gate5RuntimeCapabilityContractV1Factory, Gate5RuntimeCapabilityContractV2Factory, Gate5PublishedTypedBehaviorRegistryFactory
from broker_reports_gate1.gate5_declaration_authoring_language import Gate5DeclarationAuthoringLanguageV2Factory
contract=Gate5RuntimeCapabilityContractV1Factory.create().snapshot()
contract_v2=Gate5RuntimeCapabilityContractV2Factory.create().snapshot()
registry=Gate5PublishedTypedBehaviorRegistryFactory.create()
print(len(contract['capabilities']))
print(len(contract_v2['capabilities']))
print(registry.describe({'schema_version':'broker_reports_gate5_published_behavior_ref_v1','methodology_id':'ru-ndfl-securities-proof','methodology_version':'2026.0-experimental','behavior_id':'security_disposal_net_result_v0'})['output_contract_id'])
print(hashlib.sha256(Gate5DeclarationAuthoringLanguageV2Factory.create_g523_replay().model_payload_bytes()).hexdigest())
"""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "5",
        "5",
        GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
        "62fde21f4bc75d32deebf3ac9c650b4506d5f269d3392c6ba97c3af3695a7a9d",
    ]


def _typed_runtime(store) -> Gate5PublishedTypedBehaviorRuntime:
    resolved = Gate5RuntimeCapabilityResolverV1Factory.create().resolve(
        _capability_ref("execute_published_typed_behavior_v1")
    )
    assert resolved.factory_owner is Gate5PublishedTypedBehaviorRuntimeFactory
    assert resolved.operations == ("execute",)
    return resolved.create_runtime(
        store=store,
        read_enabled=True,
        retention_policy=_retention(),
    )


def _execute_operation_model(
    *,
    store,
    monkeypatch: pytest.MonkeyPatch,
    ref: str,
    gross: str,
    acquisition: str,
    fee: str,
    fee_documented: bool = True,
) -> tuple[dict, ArtifactAccessContext]:
    gross_source = gross.replace(".", ",")
    monkeypatch.setitem(
        gate4_fixtures._FACT_SPEC_BY_TYPE,
        "SECURITY_DISPOSAL",
        (
            ("date", "11.02.2025"),
            ("asset", f"ASSET-{ref.upper()}"),
            ("quantity", "1"),
            ("amount", gross_source),
            ("currency", "RUB"),
            ("unit_price", gross_source),
        ),
    )
    monkeypatch.setitem(
        gate4_fixtures._SOURCE_ROW_BY_TYPE,
        "SECURITY_DISPOSAL",
        f"Продажа|11.02.2025|ASSET-{ref.upper()}|1|{gross_source}|RUB|{gross_source}",
    )
    context = ArtifactAccessContext(
        user_id="g5-typed-user",
        normalization_run_id=f"g5-typed-run-{ref}",
        case_id=f"g5-typed-case-{ref}",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    gate4_fixtures._publish_document(
        store=store,
        context=context,
        document_id=f"g5-typed-document-{ref}",
        financial_types=("SECURITY_DISPOSAL",),
        sidecar_artifact_id=f"g3-v2-g5-typed-{ref}",
        created_at="2026-08-10T10:00:00+00:00",
    )
    Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="acquisition-cost-required",
        fact_key="acquisition_cost",
        amount=acquisition,
    )
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="transaction-expense-required",
        fact_key="transaction_expense",
        amount=fee,
    )
    behavior_input = model_fixtures._resolved_inputs()
    behavior_input["scope"] = {}
    behavior_input["expense_evidence"]["transaction_expense"]["documented"]["value"] = (
        fee_documented
    )
    result = _typed_runtime(store).execute(
        behavior_ref=_operation_behavior_ref(),
        input_contract_id=GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION,
        output_contract_id=GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT,
        behavior_input=behavior_input,
        context=context,
    )
    assert result["result_payload"]["schema_version"] == (
        GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT
    )
    return result, context


def _empty_store_and_context(tmp_path: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "empty.sqlite3",
            payload_root=tmp_path / "empty-payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="g5-typed-user",
        normalization_run_id="g5-typed-empty-run",
        case_id="g5-typed-empty-case",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    return store, context


def _capability_ref(
    capability_id: str,
    *,
    schema_version: str = GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION,
) -> dict[str, str]:
    return {"schema_version": schema_version, "capability_id": capability_id}


def _calculation_behavior_ref() -> dict[str, str]:
    return copy.deepcopy(CALCULATION_BEHAVIOR_REF)


def _operation_behavior_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION
        ),
        "behavior_id": GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID,
    }


def _calculation_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": "broker_reports_gate5_trusted_methodology_ref_v0",
        "methodology_id": GATE5_TRUSTED_METHODOLOGY_ID,
        "methodology_version": GATE5_TRUSTED_METHODOLOGY_VERSION,
    }


def _scope() -> dict[str, str]:
    return {
        "schema_version": GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
        "scope_ref": "taxpayer-proof-2025-organized-securities",
        "taxpayer_scope_ref": "taxpayer-proof-1",
        "tax_period": "2025",
        "operation_category": "organized_market_securities_outside_iis",
    }


def _member(operation_ref: str, source_scope_ref: str, tax_model: dict) -> dict:
    return {
        "operation_ref": operation_ref,
        "source_scope_ref": source_scope_ref,
        "tax_model": copy.deepcopy(tax_model),
    }


def _completeness(scope_binding_sha256: str) -> dict:
    return {
        "schema_version": GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
        "status": "asserted_complete",
        "coverage_kind": "all_operations_in_taxpayer_category_period_scope",
        "scope_binding_sha256": scope_binding_sha256,
        "provenance": {
            "source_kind": "user_verified_fact",
            "source_ref": "user-confirmed-complete-2025-securities-scope",
            "input_channel": "tax_period_scope_completeness",
        },
    }


def _retention():
    return build_retention_policy(mode="synthetic_dev")


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


def _remove_key_recursively(value, key: str) -> None:
    if isinstance(value, dict):
        value.pop(key, None)
        for item in value.values():
            _remove_key_recursively(item, key)
    elif isinstance(value, list):
        for item in value:
            _remove_key_recursively(item, key)
