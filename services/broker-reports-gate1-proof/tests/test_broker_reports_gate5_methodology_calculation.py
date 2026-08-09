from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    GATE5_CALCULATION_METHODOLOGY_SCHEMA_VERSION,
    GATE5_CALCULATION_RESULT_SCHEMA_VERSION,
    GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID,
    GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE,
    GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5MethodologyCalculationError,
    Gate5MethodologyCalculationRuntime,
    Gate5MethodologyCalculationRuntimeFactory,
    Gate5SupplementalFactRuntimeFactory,
    build_retention_policy,
)
from broker_reports_gate1 import gate5_methodology_calculation as calculation_module
from broker_reports_gate1.gate5_methodology_calculation import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
import test_broker_reports_gate4_sql_materialization as gate4_fixtures


def test_methodology_selects_inputs_and_behavior_for_reproducible_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, store, context = _representative_case(tmp_path, monkeypatch)
    methodology = _methodology()
    gate4_before = _financial_case(store=store, context=context)
    assert _role_values(gate4_before[0])["amount"] == "100.00"
    acquisition = _put_money(
        store=store,
        context=context,
        requirement_ref="acquisition-cost-required",
        fact_key="acquisition_cost",
        amount="70.00",
    )
    transaction = _put_money(
        store=store,
        context=context,
        requirement_ref="transaction-expense-required",
        fact_key="transaction_expense",
        amount="2.00",
    )
    artifacts_before = _supplemental_refs(store, context)

    result = _runtime(store).calculate(
        methodology=methodology,
        context=context,
    )

    assert result["schema_version"] == GATE5_CALCULATION_RESULT_SCHEMA_VERSION
    assert result["status"] == "calculated"
    assert result["methodology_binding"] == {
        "methodology_id": "ru-ndfl-securities-proof",
        "methodology_version": "2026.0-experimental",
        "projection_sha256": _projection_sha256(methodology),
    }
    assert result["calculation_binding"] == {
        "calculation_id": "security-disposal-1-result",
        "rule_id": "experimental-security-disposal-net-result-v0",
        "behavior_id": GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID,
    }
    assert result["outputs"] == {
        "proceeds": _money("100.00"),
        "recognized_expense": _money("72.00"),
        "net_result": _money("28.00"),
    }
    inputs = {item["input_name"]: item for item in result["inputs"]}
    assert set(inputs) == {
        "proceeds",
        "acquisition_cost",
        "transaction_expense",
    }
    assert inputs["proceeds"]["value"] == _money("100.00")
    assert inputs["proceeds"]["requirement_refs"] == [
        "disposal-proceeds-required",
        "disposal-currency-required",
    ]
    assert [
        item["source"]["source_kind"] for item in inputs["proceeds"]["sources"]
    ] == ["financial_case", "financial_case"]
    assert {
        item["source"]["matches"][0]["fact_id"]
        for item in inputs["proceeds"]["sources"]
    } == {gate4_before[0]["fact_id"]}
    assert inputs["acquisition_cost"] == {
        "input_name": "acquisition_cost",
        "requirement_refs": ["acquisition-cost-required"],
        "value": _money("70.00"),
        "sources": [
            {
                "requirement_id": "acquisition-cost-required",
                "source": _supplemental_source(acquisition["fact"]),
            }
        ],
    }
    assert inputs["transaction_expense"] == {
        "input_name": "transaction_expense",
        "requirement_refs": ["transaction-expense-required"],
        "value": _money("2.00"),
        "sources": [
            {
                "requirement_id": "transaction-expense-required",
                "source": _supplemental_source(transaction["fact"]),
            }
        ],
    }
    assert _supplemental_refs(store, context) == artifacts_before
    assert _financial_case(store=store, context=context) == gate4_before

    reopened_store = ArtifactStoreFactory(config).create()
    reopened = _runtime(reopened_store).calculate(
        methodology=methodology,
        context=context,
    )
    assert reopened == result
    assert _financial_case(store=reopened_store, context=context) == gate4_before


def test_unknown_behavior_and_missing_input_fail_without_result_or_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, store, context = _representative_case(tmp_path, monkeypatch)
    methodology = _methodology()
    _put_money(
        store=store,
        context=context,
        requirement_ref="acquisition-cost-required",
        fact_key="acquisition_cost",
        amount="70.00",
    )
    artifacts_before = _supplemental_refs(store, context)
    unsupported = copy.deepcopy(methodology)
    unsupported["calculation"]["behavior_id"] = "unknown-behavior-v1"

    with pytest.raises(Gate5MethodologyCalculationError) as unknown:
        _runtime(store).calculate(methodology=unsupported, context=context)
    assert unknown.value.code == "gate5_calculation_behavior_unsupported"
    assert _supplemental_refs(store, context) == artifacts_before

    with pytest.raises(Gate5MethodologyCalculationError) as missing:
        _runtime(store).calculate(methodology=methodology, context=context)
    assert missing.value.code == "gate5_calculation_inputs_not_satisfied"
    assert _supplemental_refs(store, context) == artifacts_before


def test_factory_and_module_keep_tax_behavior_bounded_and_read_only() -> None:
    factory_source = inspect.getsource(Gate5MethodologyCalculationRuntimeFactory)
    runtime_source = inspect.getsource(Gate5MethodologyCalculationRuntime)
    module_source = inspect.getsource(calculation_module)
    tree = ast.parse(module_source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert "Gate5MethodologyCalculationRuntimeFactory.create" in FACTORY_REQUIRED
    assert (
        "Gate5SupplementalFactDiscoveryRuntimeFactory.create" in (FACTORY_REQUIRED[1])
    )
    assert "executable methodology" in FORBIDDEN[1]
    assert "Gate5SupplementalFactDiscoveryRuntimeFactory(" in factory_source
    assert "self._discovery.check(" in runtime_source
    assert imports == {
        "__future__",
        "copy",
        "decimal",
        "hashlib",
        "json",
        "re",
        "typing",
        "artifact_models",
        "gate5_combined_requirement_check",
        "gate5_supplemental_fact_discovery",
    }
    for forbidden_path in (
        "Gate4FinancialCaseRuntimeFactory",
        "Gate5SupplementalFactRuntimeFactory",
        "ArtifactResolver",
        "ArtifactStoreFactory",
        "get_record_unchecked",
        "list_by_case_context",
        "sqlite3",
        "requests",
        "httpx",
        "model_client",
        "chat_completion",
    ):
        assert forbidden_path not in module_source
    for methodology_owned_literal in (
        '"SECURITY_DISPOSAL"',
        "acquisition-cost-required",
        "transaction-expense-required",
        "100.00",
        "70.00",
        "2.00",
    ):
        assert methodology_owned_literal not in module_source
    assert ".put(" not in runtime_source


def _representative_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ArtifactStoreConfig, object, ArtifactAccessContext]:
    monkeypatch.setitem(
        gate4_fixtures._FACT_SPEC_BY_TYPE,
        "SECURITY_DISPOSAL",
        (
            ("date", "11.02.2026"),
            ("asset", "ACME"),
            ("quantity", "1"),
            ("amount", "100,00"),
            ("currency", "RUB"),
            ("unit_price", "100,00"),
        ),
    )
    monkeypatch.setitem(
        gate4_fixtures._SOURCE_ROW_BY_TYPE,
        "SECURITY_DISPOSAL",
        "Продажа|11.02.2026|ACME|1|100,00|RUB|100,00",
    )
    config = ArtifactStoreConfig(
        mode="sqlite",
        sqlite_path=tmp_path / "artifacts.sqlite3",
        payload_root=tmp_path / "payloads",
    )
    store = ArtifactStoreFactory(config).create()
    context = ArtifactAccessContext(
        user_id="g5-calculation-user",
        normalization_run_id="g5-calculation-run-1",
        case_id="g5-calculation-case",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    gate4_fixtures._publish_document(
        store=store,
        context=context,
        document_id="gate5-calculation-document",
        financial_types=("SECURITY_DISPOSAL",),
        sidecar_artifact_id="g3-v2-gate5-calculation",
        created_at="2026-08-09T16:00:00+00:00",
    )
    Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    return config, store, context


def _methodology() -> dict:
    subject_ref = "security-disposal-1"
    return {
        "schema_version": GATE5_CALCULATION_METHODOLOGY_SCHEMA_VERSION,
        "methodology_id": "ru-ndfl-securities-proof",
        "methodology_version": "2026.0-experimental",
        "calculation": {
            "calculation_id": "security-disposal-1-result",
            "rule_id": "experimental-security-disposal-net-result-v0",
            "behavior_id": GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID,
            "input_bindings": {
                "proceeds": {
                    "amount_requirement_id": "disposal-proceeds-required",
                    "currency_requirement_id": "disposal-currency-required",
                },
                "acquisition_cost": {
                    "amount_requirement_id": "acquisition-cost-required",
                    "currency_requirement_id": "acquisition-cost-required",
                },
                "transaction_expense": {
                    "amount_requirement_id": "transaction-expense-required",
                    "currency_requirement_id": "transaction-expense-required",
                },
            },
        },
        "requirements": [
            _requirement(
                requirement_id="disposal-proceeds-required",
                value_key="amount",
                subject_ref=subject_ref,
            ),
            _requirement(
                requirement_id="disposal-currency-required",
                value_key="currency",
                subject_ref=subject_ref,
            ),
            _requirement(
                requirement_id="acquisition-cost-required",
                value_key="acquisition_cost",
                subject_ref=subject_ref,
            ),
            _requirement(
                requirement_id="transaction-expense-required",
                value_key="transaction_expense",
                subject_ref=subject_ref,
            ),
        ],
    }


def _requirement(
    *,
    requirement_id: str,
    value_key: str,
    subject_ref: str,
) -> dict[str, str]:
    return {
        "requirement_id": requirement_id,
        "financial_type": "SECURITY_DISPOSAL",
        "value_key": value_key,
        "subject_ref": subject_ref,
    }


def _put_money(
    *,
    store,
    context: ArtifactAccessContext,
    requirement_ref: str,
    fact_key: str,
    amount: str,
) -> dict:
    return (
        Gate5SupplementalFactRuntimeFactory(
            store=store,
            retention_policy=build_retention_policy(mode="synthetic_dev"),
        )
        .create()
        .put(
            supplemental_input={
                "schema_version": GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
                "requirement_ref": requirement_ref,
                "subject_ref": "security-disposal-1",
                "fact_key": fact_key,
                "value": _money(amount),
            },
            context=context,
        )
    )


def _runtime(store) -> Gate5MethodologyCalculationRuntime:
    return Gate5MethodologyCalculationRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _financial_case(*, store, context: ArtifactAccessContext) -> list[dict]:
    return (
        Gate4FinancialCaseRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .list_by_financial_type(
            context=context,
            financial_type="SECURITY_DISPOSAL",
        )
    )


def _supplemental_refs(store, context: ArtifactAccessContext) -> list[str]:
    return [
        record.artifact_id
        for record in store.list_by_case_context(context)
        if record.artifact_type == GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE
    ]


def _supplemental_source(fact: dict) -> dict:
    return {
        "source_kind": "supplemental_fact",
        "supplemental_fact_ref": fact["supplemental_fact_ref"],
        "value": copy.deepcopy(fact["value"]),
        "scope_binding": copy.deepcopy(fact["scope_binding"]),
        "provenance": copy.deepcopy(fact["provenance"]),
    }


def _role_values(fact: dict) -> dict[str, str]:
    return {
        role["role"]: role["value"]
        for role in fact["roles"]
        if role["status"] == "value"
    }


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


def _projection_sha256(value: dict) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
