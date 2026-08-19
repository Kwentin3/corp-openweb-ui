from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import gate5_declaration_budget_outcome as module
from broker_reports_gate1.gate5_declaration_budget_outcome import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION,
    GATE5_DECLARATION_BUDGET_DISPOSITION_INPUT_SCHEMA_VERSION,
    Gate5DeclarationBudgetOutcomeError,
    Gate5DeclarationBudgetOutcomeRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
)
import test_broker_reports_gate5_declaration_tax_settlement as income_fixtures
import test_broker_reports_gate5_filing_and_party_identity as filing_fixtures
import test_broker_reports_gate5_resolved_declaration_package as package_fixtures


def test_exact_budget_disposition_uses_validated_dependency_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    filing = filing_fixtures._component(receipt["scope_binding"])
    income = income_fixtures._component(receipt["scope_binding"], tax_base)
    component = _component(receipt["scope_binding"], filing, income)

    disposition = component["disposition"]
    assert component["status"] == "complete"
    assert component["root_coverage"] == "exact_root_domain"
    assert disposition["kind"] == "additional_payment"
    assert disposition["calculated_tax"] == _money("4.00")
    assert disposition["credited_or_withheld_amount"] == _money("0.00")
    assert disposition["reduction_amount"] == _money("0.00")
    assert disposition["payment_or_additional_payment_amount"] == _money("4.00")
    assert disposition["refund_available_amount"] == _money("0.00")
    assert disposition["simplified_procedure_returned_or_credited_amount"] == (
        _money("0.00")
    )
    assert disposition["budget_allocations"] == [
        {
            "allocation_kind": "tax_payment",
            "destination_tax_authority_ref": "synthetic-tax-authority",
            "budget_allocation_ref": "g531-synthetic-budget-allocation",
            "kbk": "18210102030011000110",
            "oktmo": "45382000",
            "amount": _money("4.00"),
        }
    ]


def test_budget_replay_closes_third_component_and_exposes_financial_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, operation, receipt, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    filing = filing_fixtures._component(receipt["scope_binding"])
    income = income_fixtures._component(receipt["scope_binding"], tax_base)
    budget = _component(receipt["scope_binding"], filing, income)
    package = package_fixtures._runtime(store).assemble(
        definition_ref=package_fixtures._definition_ref(),
        scope_receipt=receipt,
        typed_component_snapshots=[
            package_fixtures._component(operation),
            filing_fixtures._component_evidence(filing),
            _component_evidence(budget),
            income_fixtures._component_evidence(income),
        ],
        context=context,
    )

    states = {
        row["domain_id"]: row["state"] for row in package["requirement_resolutions"]
    }
    assert states["filing_and_party_identity"] == "RESOLVED"
    assert states["declaration_budget_disposition"] == "RESOLVED"
    assert states["income_group_tax_results"] == "RESOLVED"
    assert package["completeness_receipt"]["first_blocker"] == {
        "domain_id": "financial_investment_results",
        "blocker_class": "component",
        "state": "REQUIRED_MISSING",
        "reason": "required_component_bounded_only",
    }
    assert package_fixtures._closed_runtime().validate_package(package=package) == (
        package
    )


def test_dependency_or_output_tamper_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    filing = filing_fixtures._component(receipt["scope_binding"])
    income = income_fixtures._component(receipt["scope_binding"], tax_base)
    value = _input(receipt["scope_binding"], filing, income)
    value["income_group_results_component"]["group_results"][0]["tax_payable"][
        "amount"
    ] = "5.00"
    with pytest.raises(Gate5DeclarationBudgetOutcomeError) as exc_info:
        Gate5DeclarationBudgetOutcomeRuntimeFactory.create().create_component(
            component_input=value
        )
    assert exc_info.value.code == "gate5_budget_disposition_dependency_invalid"

    runtime = Gate5DeclarationBudgetOutcomeRuntimeFactory.create()
    component = _component(receipt["scope_binding"], filing, income)
    component["disposition"]["payment_or_additional_payment_amount"]["amount"] = "5.00"
    with pytest.raises(Gate5DeclarationBudgetOutcomeError) as exc_info:
        runtime.validate_component(
            component=component,
            scope_binding=receipt["scope_binding"],
        )
    assert exc_info.value.code == "gate5_budget_disposition_component_mismatch"


def test_factory_source_has_no_second_business_read_path() -> None:
    source = inspect.getsource(module)
    imports = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert len(FACTORY_REQUIRED) == 3
    assert FORBIDDEN
    assert "Gate5FilingAndPartyIdentityRuntimeFactory.create" in source
    assert "Gate5DeclarationTaxSettlementRuntimeFactory.create" in source
    assert all("artifact_models" not in name for name in imports)
    assert all("gate4" not in name for name in imports)
    assert all("sqlite" not in name for name in imports)


def _component(scope_binding: dict, filing: dict, income: dict) -> dict:
    return Gate5DeclarationBudgetOutcomeRuntimeFactory.create().create_component(
        component_input=_input(scope_binding, filing, income)
    )


def _component_evidence(component: dict) -> dict:
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
        "component_contract_id": (
            GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION
        ),
        "component_sha256": _sha256(component),
        "payload": copy.deepcopy(component),
    }


def _input(scope_binding: dict, filing: dict, income: dict) -> dict:
    return {
        "schema_version": GATE5_DECLARATION_BUDGET_DISPOSITION_INPUT_SCHEMA_VERSION,
        "scope_binding": copy.deepcopy(scope_binding),
        "filing_component": copy.deepcopy(filing),
        "income_group_results_component": copy.deepcopy(income),
        "allocation_evidence": {
            "schema_version": "broker_reports_gate5_synthetic_case_evidence_v0",
            "status": "synthetic_proof_evidence",
            "source_ref": "g531-synthetic-budget-disposition",
            "budget_allocation_ref": "g531-synthetic-budget-allocation",
            "kbk": "18210102030011000110",
            "oktmo": "45382000",
            "simplified_procedure_returned_or_credited_amount": {
                "kind": "money",
                "amount": "0.00",
                "currency": "RUB",
            },
            "case_id": scope_binding["case_id"],
            "tax_period": scope_binding["tax_period"],
            "input_channel": "declaration_budget_disposition",
            "real_user_fact": False,
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
