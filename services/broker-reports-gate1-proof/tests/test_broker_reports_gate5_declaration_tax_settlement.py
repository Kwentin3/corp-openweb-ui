from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import gate5_declaration_tax_settlement as module
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_declaration_tax_settlement import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_RESULTS_INPUT_SCHEMA_VERSION,
    Gate5DeclarationTaxSettlementError,
    Gate5DeclarationTaxSettlementRuntimeFactory,
)
from broker_reports_gate1.gate5_income_group_tax_base import (
    GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
    Gate5IncomeGroupTaxBaseRuntimeFactory,
)
from broker_reports_gate1.gate5_tax_period_category_aggregation import (
    GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
    GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
from broker_reports_gate1.gate5_trusted_methodology import (
    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
import test_broker_reports_gate5_filing_and_party_identity as filing_fixtures
import test_broker_reports_gate5_resolved_declaration_package as package_fixtures


def test_exact_income_group_component_pairs_base_and_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = _proof_models(
        tmp_path, monkeypatch
    )
    component = _component(receipt["scope_binding"], tax_base)

    result = component["group_results"][0]
    assert component["status"] == "complete"
    assert component["root_coverage"] == "exact_root_domain"
    assert result["tax_base_model"] == tax_base
    assert result["tax_base_model"]["tax_base"]["value"] == _money("28.00")
    assert result["calculated_tax"] == _money("4.00")
    assert result["tax_payable"] == _money("4.00")
    assert result["tax_refundable"] == _money("0.00")
    assert result["derivation"]["unrounded_tax"] == "3.64"
    assert {
        fact["provenance"]["source_kind"]
        for fact in result["settlement_facts"].values()
    } == {"synthetic_proof_evidence"}


def test_2025_securities_base_above_five_million_stays_in_two_band_schedule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = _proof_models(
        tmp_path, monkeypatch
    )
    high_base = copy.deepcopy(tax_base)
    high_base["tax_base"]["value"]["amount"] = "10000000.00"
    methodology = (
        module.Gate5TrustedMethodologyAuthorityFactory.create()
        .resolve(
            {
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
                "methodology_version": (
                    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION
                ),
            }
        )["methodology"]
    )

    result = module._group_result(
        model=high_base,
        facts=_input(receipt["scope_binding"], tax_base)["settlement_facts"][0],
        methodology=methodology,
        methodology_binding={"projection_sha256": "0" * 64},
    )

    assert result["calculated_tax"] == _money("1452000.00")
    assert result["derivation"]["rate_band"]["marginal_rate"] == "0.15"
    assert result["derivation"]["rate_band"]["upper_bound_inclusive"] is None


def test_superseded_five_band_resource_remains_resolvable_by_exact_version() -> None:
    resolved = module.Gate5TrustedMethodologyAuthorityFactory.create().resolve(
        {
            "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
            "methodology_id": GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
            "methodology_version": "2026.3-experimental",
        }
    )

    assert resolved["methodology"]["methodology_version"] == "2026.3-experimental"
    assert len(resolved["methodology"]["behavior"]["rate_schedule"]) == 5


def test_prerequisite_replay_closes_income_results_but_keeps_budget_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, operation, receipt, tax_base = _proof_models(tmp_path, monkeypatch)
    filing = filing_fixtures._component(receipt["scope_binding"])
    results = _component(receipt["scope_binding"], tax_base)
    package = package_fixtures._runtime(store).assemble(
        definition_ref=package_fixtures._definition_ref(),
        scope_receipt=receipt,
        typed_component_snapshots=[
            package_fixtures._component(operation),
            filing_fixtures._component_evidence(filing),
            _component_evidence(results),
        ],
        context=context,
    )

    states = {
        row["domain_id"]: row["state"] for row in package["requirement_resolutions"]
    }
    assert states["filing_and_party_identity"] == "RESOLVED"
    assert states["income_group_tax_results"] == "RESOLVED"
    assert package["completeness_receipt"]["first_blocker"] == {
        "domain_id": "declaration_budget_disposition",
        "blocker_class": "component",
        "state": "REQUIRED_MISSING",
        "reason": "required_component_missing",
    }
    assert package_fixtures._closed_runtime().validate_package(package=package) == (
        package
    )


def test_missing_completeness_or_unpublished_methodology_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = _proof_models(
        tmp_path, monkeypatch
    )
    value = _input(receipt["scope_binding"], tax_base)
    value["completeness_evidence"]["income_group_model_sha256s"] = []
    with pytest.raises(Gate5DeclarationTaxSettlementError) as exc_info:
        Gate5DeclarationTaxSettlementRuntimeFactory.create().create_component(
            component_input=value
        )
    assert exc_info.value.code == "gate5_income_group_results_completeness_invalid"

    value = _input(receipt["scope_binding"], tax_base)
    value["methodology_ref"]["methodology_version"] = "missing"
    with pytest.raises(Gate5DeclarationTaxSettlementError) as exc_info:
        Gate5DeclarationTaxSettlementRuntimeFactory.create().create_component(
            component_input=value
        )
    assert exc_info.value.code == "gate5_income_group_results_methodology_unavailable"


def test_output_tamper_fails_deterministic_rebuild(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = _proof_models(
        tmp_path, monkeypatch
    )
    runtime = Gate5DeclarationTaxSettlementRuntimeFactory.create()
    component = _component(receipt["scope_binding"], tax_base)
    component["group_results"][0]["calculated_tax"]["amount"] = "3.00"

    with pytest.raises(Gate5DeclarationTaxSettlementError) as exc_info:
        runtime.validate_component(
            component=component,
            scope_binding=receipt["scope_binding"],
        )
    assert exc_info.value.code == "gate5_income_group_results_component_mismatch"


def test_factory_source_has_no_hidden_runtime_authority() -> None:
    source = inspect.getsource(module)
    imported_modules = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert len(FACTORY_REQUIRED) == 3
    assert FORBIDDEN
    assert "Gate5IncomeGroupTaxBaseRuntimeFactory.create" in source
    assert "Gate5TrustedMethodologyAuthorityFactory.create" in source
    assert all("artifact_models" not in name for name in imported_modules)
    assert all("gate4" not in name for name in imported_modules)
    assert all("sqlite" not in name for name in imported_modules)
    assert all("openai" not in name for name in imported_modules)
    assert "float(" not in source


def _proof_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store, context, operation, receipt = package_fixtures._scope_case(
        tmp_path, monkeypatch
    )
    category_runtime = Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
    category_scope = {
        "schema_version": GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
        "scope_ref": "g531-synthetic-category",
        "taxpayer_scope_ref": receipt["scope_binding"]["taxpayer_scope_ref"],
        "tax_period": receipt["scope_binding"]["tax_period"],
        "operation_category": "organized_market_securities_outside_iis",
    }
    members = [
        {
            "operation_ref": "g531-synthetic-operation",
            "source_scope_ref": context.case_id,
            "tax_model": copy.deepcopy(operation),
        }
    ]
    category_binding = category_runtime.describe_scope(
        scope=category_scope,
        members=members,
    )
    category = category_runtime.run(
        scope=category_scope,
        members=members,
        completeness_evidence={
            "schema_version": GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
            "status": "asserted_complete",
            "coverage_kind": "all_operations_in_taxpayer_category_period_scope",
            "scope_binding_sha256": category_binding["scope_binding_sha256"],
            "provenance": {
                "source_kind": "user_verified_fact",
                "source_ref": "g531-synthetic-category-complete",
                "input_channel": "tax_period_scope_completeness",
            },
        },
    )["category_tax_model"]
    base_runtime = Gate5IncomeGroupTaxBaseRuntimeFactory.create()
    status = _tagged_scalar(
        "resident_individual", "g531-synthetic-taxpayer-status", "taxpayer_status"
    )
    group_values = {
        name: _tagged_money("0.00", f"g531-synthetic-{name}")
        for name in (
            "other_group_income",
            "other_group_allowable_expenses",
            "non_taxable_income",
            "tax_deductions",
        )
    }
    input_binding = base_runtime.describe_input(
        category_tax_model=category,
        taxpayer_status=status,
        group_values=group_values,
    )
    tax_base = base_runtime.run(
        methodology_ref={
            "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
            "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
            "methodology_version": (
                GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION
            ),
        },
        behavior_input={
            "schema_version": GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
            "category_tax_model": category,
            "taxpayer_status": status,
            "group_values": group_values,
            "completeness_evidence": {
                "schema_version": GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION,
                "status": "asserted_complete",
                "coverage_kind": "all_income_and_reductions_in_stable_income_group",
                "input_binding_sha256": input_binding["input_binding_sha256"],
                "provenance": {
                    "source_kind": "user_verified_fact",
                    "source_ref": "g531-synthetic-income-group-complete",
                    "input_channel": "income_group_completeness",
                },
            },
        },
    )
    return store, context, operation, receipt, tax_base


def _component(scope_binding: dict, tax_base: dict) -> dict:
    return Gate5DeclarationTaxSettlementRuntimeFactory.create().create_component(
        component_input=_input(scope_binding, tax_base)
    )


def _component_evidence(component: dict) -> dict:
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
        "component_contract_id": GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION,
        "component_sha256": _sha256(component),
        "payload": copy.deepcopy(component),
    }


def _input(scope_binding: dict, tax_base: dict) -> dict:
    model_hash = _sha256(tax_base)
    settlement = {"income_group_model_sha256": model_hash}
    for name in (
        "withheld_at_source",
        "material_benefit_withheld",
        "trade_fee_credit",
        "fixed_advance_credit",
        "foreign_tax_credit",
        "patent_credit",
    ):
        settlement[name] = {
            "value": _money("0.00"),
            "provenance": {
                "source_kind": "synthetic_proof_evidence",
                "source_ref": f"g531-synthetic-{name}",
                "input_channel": "income_group_tax_settlement",
                "real_user_fact": False,
            },
        }
    return {
        "schema_version": GATE5_INCOME_GROUP_TAX_RESULTS_INPUT_SCHEMA_VERSION,
        "methodology_ref": {
            "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
            "methodology_id": GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
            "methodology_version": GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION,
        },
        "scope_binding": copy.deepcopy(scope_binding),
        "income_group_tax_base_models": [copy.deepcopy(tax_base)],
        "settlement_facts": [settlement],
        "completeness_evidence": {
            "schema_version": "broker_reports_gate5_income_group_results_completeness_v0",
            "status": "asserted_complete",
            "coverage_kind": "all_applicable_income_groups_for_declaration_scope",
            "scope_binding_sha256": scope_binding["scope_binding_sha256"],
            "income_group_model_sha256s": [model_hash],
            "provenance": {
                "source_kind": "synthetic_proof_evidence",
                "source_ref": "g531-synthetic-all-income-groups-complete",
                "input_channel": "income_group_results_completeness",
                "real_user_fact": False,
            },
        },
    }


def _tagged_money(amount: str, source_ref: str) -> dict:
    return {
        "value": _money(amount),
        "provenance": {
            "source_kind": "user_verified_fact",
            "source_ref": source_ref,
            "input_channel": "income_group_tax_base",
        },
    }


def _tagged_scalar(value: str, source_ref: str, input_channel: str) -> dict:
    return {
        "value": value,
        "provenance": {
            "source_kind": "methodology_derived_result",
            "source_ref": f"residency-classification:{source_ref}",
            "input_channel": input_channel,
        },
    }


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


def _sha256(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
