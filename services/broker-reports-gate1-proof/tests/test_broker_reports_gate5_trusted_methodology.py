from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from broker_reports_gate1 import (
    GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
    GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
    GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
    GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER,
    GATE5_TRUSTED_METHODOLOGY_ID,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    GATE5_TRUSTED_METHODOLOGY_RESOURCE,
    GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256,
    GATE5_TRUSTED_METHODOLOGY_VERSION,
    ArtifactStoreFactory,
    Gate5MethodologyCalculationError,
    Gate5TrustedMethodologyAuthorityFactory,
    Gate5TrustedMethodologyCalculationRuntimeFactory,
    Gate5TrustedMethodologyError,
    build_retention_policy,
)
from broker_reports_gate1 import gate5_methodology_calculation as calculation_module
from broker_reports_gate1 import gate5_trusted_methodology as trusted_module
from broker_reports_gate1.gate5_trusted_methodology import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE,
    GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE_SHA256,
)
import test_broker_reports_gate5_methodology_calculation as calculation_fixtures


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
RESOURCE = PACKAGE_ROOT / GATE5_TRUSTED_METHODOLOGY_RESOURCE


def test_trusted_repository_methodology_replays_g57_with_exact_authority_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, store, context = calculation_fixtures._representative_case(
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
    methodology_ref = _methodology_ref()
    gate4_before = calculation_fixtures._financial_case(
        store=store,
        context=context,
    )
    artifacts_before = calculation_fixtures._supplemental_refs(store, context)
    resolved = Gate5TrustedMethodologyAuthorityFactory.create().resolve(methodology_ref)

    result = _runtime(store).calculate(
        methodology_ref=methodology_ref,
        context=context,
    )

    assert result == {
        "schema_version": GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
        "status": "calculated",
        "authority_binding": resolved["authority_binding"],
        "calculation_result": result["calculation_result"],
    }
    assert result["authority_binding"] == {
        "authority_owner": GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER,
        "methodology_id": GATE5_TRUSTED_METHODOLOGY_ID,
        "methodology_version": GATE5_TRUSTED_METHODOLOGY_VERSION,
        "resource_sha256": GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256,
        "projection_sha256": _projection_sha256(resolved["methodology"]),
    }
    calculation_result = result["calculation_result"]
    assert calculation_result["methodology_binding"] == {
        "methodology_id": GATE5_TRUSTED_METHODOLOGY_ID,
        "methodology_version": GATE5_TRUSTED_METHODOLOGY_VERSION,
        "projection_sha256": result["authority_binding"]["projection_sha256"],
    }
    assert calculation_result["outputs"] == {
        "proceeds": _money("100.00"),
        "recognized_expense": _money("72.00"),
        "net_result": _money("28.00"),
    }
    assert calculation_fixtures._supplemental_refs(store, context) == (artifacts_before)
    assert (
        calculation_fixtures._financial_case(
            store=store,
            context=context,
        )
        == gate4_before
    )

    resolved["methodology"]["calculation"]["rule_id"] = "caller-mutated-copy"
    reopened_store = ArtifactStoreFactory(config).create()
    reopened = _runtime(reopened_store).calculate(
        methodology_ref=methodology_ref,
        context=context,
    )
    assert reopened == result


def test_arbitrary_payload_and_missing_identity_fail_before_calculation_or_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, store, context = calculation_fixtures._representative_case(
        tmp_path,
        monkeypatch,
    )
    artifacts_before = calculation_fixtures._supplemental_refs(store, context)
    caller_payload = {
        **_methodology_ref(),
        "methodology": calculation_fixtures._methodology(),
    }

    with pytest.raises(Gate5TrustedMethodologyError) as arbitrary:
        _runtime(store).calculate(
            methodology_ref=caller_payload,
            context=context,
        )
    assert arbitrary.value.code == "gate5_trusted_methodology_ref_invalid"

    missing = _methodology_ref()
    missing["methodology_version"] = "not-published"
    with pytest.raises(Gate5TrustedMethodologyError) as unpublished:
        _runtime(store).calculate(
            methodology_ref=missing,
            context=context,
        )
    assert unpublished.value.code == "gate5_trusted_methodology_not_published"
    assert calculation_fixtures._supplemental_refs(store, context) == (artifacts_before)


def test_hash_pinned_package_resource_fails_closed_after_content_tampering(
    tmp_path: Path,
) -> None:
    package_copy = tmp_path / "broker_reports_gate1"
    shutil.copytree(
        PACKAGE_ROOT,
        package_copy,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    command = [
        sys.executable,
        "-B",
        "-c",
        (
            "from broker_reports_gate1 import "
            "GATE5_TRUSTED_METHODOLOGY_ID as I, "
            "GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION as S, "
            "GATE5_TRUSTED_METHODOLOGY_VERSION as V, "
            "Gate5TrustedMethodologyAuthorityFactory as F; "
            "r=F.create().resolve({'schema_version':S,'methodology_id':I,"
            "'methodology_version':V}); print(r['authority_binding']['resource_sha256'])"
        ),
    ]
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    first = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256

    copied_resource = package_copy / GATE5_TRUSTED_METHODOLOGY_RESOURCE
    raw = copied_resource.read_bytes()
    copied_resource.write_bytes(
        raw.replace(
            b"experimental-security-disposal-net-result-v0",
            b"unapproved-security-disposal-net-result-v0",
            1,
        )
    )
    tampered = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert tampered.returncode != 0
    assert "gate5_trusted_methodology_resource_hash_mismatch" in tampered.stderr
    assert hashlib.sha256(RESOURCE.read_bytes()).hexdigest() == (
        GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256
    )


def test_g57_unknown_behavior_failure_propagates_through_trusted_runtime(
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
    artifacts_before = calculation_fixtures._supplemental_refs(store, context)
    monkeypatch.setattr(
        calculation_module,
        "GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID",
        "behavior-disabled-for-proof",
    )

    with pytest.raises(Gate5MethodologyCalculationError) as unsupported:
        _runtime(store).calculate(
            methodology_ref=_methodology_ref(),
            context=context,
        )
    assert unsupported.value.code == "gate5_calculation_behavior_unsupported"
    assert calculation_fixtures._supplemental_refs(store, context) == (artifacts_before)


def test_declaration_input_methodology_is_closed_versioned_and_authority_bound() -> None:
    resolved = Gate5TrustedMethodologyAuthorityFactory.create().resolve(
        {
            "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
            "methodology_id": GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
            "methodology_version": GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
        }
    )
    methodology = resolved["methodology"]
    rules = methodology["rules"]
    authority_refs = {
        item["evidence_ref"] for item in methodology["legal_evidence"]
    }

    assert methodology["status"] == "PUBLISHED_CURRENT_AUTHORITY"
    assert methodology["scope"] == {
        "tax_period": "2025",
        "jurisdiction": "RU",
        "scenario": "mandatory_common_filing_plus_observed_broker_securities_income",
    }
    assert len(rules) == 13
    assert len({item["rule_id"] for item in rules}) == len(rules)
    assert {
        "filing-context-fns-order-913-v1",
        "declarant-category-fns-order-913-v1",
        "signer-context-fns-order-913-v1",
        "budget-disposition-fns-order-913-v1",
        "taxpayer-residency-article-207-v1",
        "dividend-source-article-208-v1",
        "security-disposal-source-article-208-v1",
        "coupon-securities-income-article-214.1-v1",
        "dividend-income-group-articles-210-214-v1",
        "organized-market-classification-article-214.1-v1",
        "foreign-currency-conversion-article-210-v1",
        "foreign-tax-credit-articles-214-232-v3",
        "partial-acquisition-commission-v1",
    } == {item["rule_id"] for item in rules}
    rule_ids = {item["rule_id"] for item in rules}
    assert all(
        set(item["rule_ids"]).issubset(rule_ids)
        for item in methodology["demand_bindings"]
    )
    assert all(item["required_inputs"] for item in rules)
    assert all(set(item["authority_refs"]).issubset(authority_refs) for item in rules)
    assert all(
        item["operation"]
        in {
            "COMPARE",
            "CLASSIFY",
            "SELECT",
            "VALIDATE",
            "LOOKUP_MULTIPLY_DIVIDE",
            "VERIFY_COMPARE_APPLY_RULE",
            "NONE",
        }
        for item in rules
    )
    assert {
        item["rule_id"]
        for item in rules
        if item["insufficient_inputs"] == "METHODOLOGY_UNRESOLVED"
    } == {
        "security-disposal-source-article-208-v1",
    }
    assert {
        item["rule_id"]
        for item in rules
        if item["insufficient_inputs"] == "LEGAL_INTERPRETATION_REQUIRED"
    } == {
        "foreign-currency-conversion-article-210-v1",
        "partial-acquisition-commission-v1",
    }
    assert next(
        item
        for item in rules
        if item["rule_id"] == "foreign-tax-credit-articles-214-232-v3"
    )["insufficient_inputs"] == "EXTERNAL_AUTHORITATIVE_FACT_MISSING"
    demand_bindings = methodology["demand_bindings"]
    assert len(demand_bindings) == 9
    assert {item["demand"] for item in demand_bindings} == {
        "obl_filing_instance_identity",
        "obl_taxpayer_identity_and_period_status",
        "obl_signer_and_representation_authority",
        "obl_declaration_budget_disposition",
        "obl_russian_source_taxable_income",
        "obl_foreign_source_taxable_income_and_foreign_tax",
        "obl_securities_and_derivatives_results",
        "obl_income_group_tax_base_results",
        "obl_income_group_tax_settlement_results",
    }
    rule_ids = {item["rule_id"] for item in rules}
    assert all(
        set(item["rule_ids"]).issubset(rule_ids) and item["owner"].endswith(".create")
        for item in demand_bindings
    )
    assert resolved["authority_binding"]["resource_sha256"] == (
        trusted_module.GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE_SHA256
    )


def test_ordinary_trade_product_methodology_requires_exact_source_assertions() -> None:
    authority = Gate5TrustedMethodologyAuthorityFactory.create()
    assertions = {
        "admitted_exchange_fact": "ADMITTED",
        "market_quotation_fact": "AVAILABLE",
        "iis_status_assertion": "OUTSIDE_IIS",
        "exemption_source_assertion": "NONE",
        "payer_organization_jurisdiction": "RU",
        "realization_location_jurisdiction": "RU",
    }

    resolved = authority.resolve_ordinary_trade_declaration_product(
        source_assertions=assertions,
        tax_period="2025",
    )

    assert resolved["operation_applicability"] == {
        "organized_market_status": "organized_market",
        "iis_status": "outside_iis",
        "exemption_applicability": "not_applicable",
    }
    assert resolved["income_source_jurisdiction"] == "russian_source"
    assert resolved["kbk"] == "18210102030011000110"
    assert resolved["authority_binding"]["resource_sha256"] == (
        GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE_SHA256
    )
    resource = PACKAGE_ROOT / GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE
    assert hashlib.sha256(resource.read_bytes()).hexdigest() == (
        GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE_SHA256
    )

    with pytest.raises(Gate5TrustedMethodologyError) as rejected:
        authority.resolve_ordinary_trade_declaration_product(
            source_assertions={**assertions, "iis_status_assertion": "IIS"},
            tax_period="2025",
        )
    assert rejected.value.code == (
        "gate5_ordinary_trade_product_source_evidence_unresolved"
    )
    assert rejected.value.gap_owner_classification == (
        "REAL_SOURCE_EVIDENCE_MISSING"
    )


def test_factory_route_is_read_only_and_caller_cannot_supply_methodology_bytes() -> (
    None
):
    module_source = inspect.getsource(trusted_module)
    factory_source = inspect.getsource(
        trusted_module.Gate5TrustedMethodologyCalculationRuntimeFactory
    )
    runtime_source = inspect.getsource(
        trusted_module.Gate5TrustedMethodologyCalculationRuntime
    )
    tree = ast.parse(module_source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert "Gate5TrustedMethodologyAuthorityFactory.create" in FACTORY_REQUIRED[0]
    assert "Gate5MethodologyCalculationRuntimeFactory.create" in FACTORY_REQUIRED[1]
    assert "caller-supplied methodology contents" in FORBIDDEN[0]
    assert "resources.files(__package__)" in module_source
    assert "Gate5TrustedMethodologyAuthorityFactory.create()" in factory_source
    assert "Gate5MethodologyCalculationRuntimeFactory(" in factory_source
    assert "self._authority.resolve(methodology_ref)" in runtime_source
    assert "self._calculator.calculate(" in runtime_source
    assert 'methodology=resolved["methodology"]' in runtime_source
    assert (
        "methodology"
        not in inspect.signature(
            trusted_module.Gate5TrustedMethodologyCalculationRuntime.calculate
        ).parameters
    )
    assert imports == {
        "__future__",
        "copy",
        "dataclasses",
        "hashlib",
        "importlib",
        "json",
        "typing",
        "artifact_models",
        "gate5_methodology_calculation",
    }
    for forbidden_path in (
        "Gate4FinancialCaseRuntimeFactory",
        "Gate5SupplementalFactRuntimeFactory",
        "Gate5SupplementalFactDiscoveryRuntimeFactory",
        "ArtifactStoreFactory",
        "ArtifactResolver",
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
        "security_disposal_net_result_v0",
        "100.00",
        "70.00",
        "2.00",
    ):
        assert methodology_owned_literal not in module_source
    assert ".put(" not in runtime_source


def _runtime(store):
    return Gate5TrustedMethodologyCalculationRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_TRUSTED_METHODOLOGY_ID,
        "methodology_version": GATE5_TRUSTED_METHODOLOGY_VERSION,
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
