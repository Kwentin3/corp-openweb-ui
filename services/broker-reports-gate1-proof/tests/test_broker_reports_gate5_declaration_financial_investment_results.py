from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    gate5_declaration_financial_investment_results as module,
)
from broker_reports_gate1.gate5_declaration_financial_investment_results import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPLETENESS_SCHEMA_VERSION,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION,
    Gate5DeclarationFinancialInvestmentResultsError,
    Gate5DeclarationFinancialInvestmentResultsRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
)
import test_broker_reports_gate5_declaration_budget_outcome as budget_fixtures
import test_broker_reports_gate5_declaration_income_sources as source_fixtures
import test_broker_reports_gate5_declaration_scope_resolution as scope_fixtures
import test_broker_reports_gate5_declaration_tax_settlement as income_fixtures
import test_broker_reports_gate5_filing_and_party_identity as filing_fixtures
import test_broker_reports_gate5_resolved_declaration_package as package_fixtures


def test_exact_component_resolves_only_activated_supplied_case_obligation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    category = tax_base["input_snapshot"]["category_tax_model"]

    component = _component(receipt["scope_binding"], category)

    assert component["status"] == "complete_for_supplied_case"
    assert component["root_coverage"] == "exact_root_domain"
    assert component["covered_obligation_refs"] == [
        "obl_securities_and_derivatives_results",
        "obl_digital_financial_asset_and_right_results",
        "obl_investment_partnership_results",
    ]
    assert [row["state"] for row in component["obligation_resolutions"]] == [
        "RESOLVED",
        "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
        "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
    ]
    assert all(
        row["real_world_absence_asserted"] is False
        for row in component["obligation_resolutions"]
    )
    assert (
        component["completeness_evidence"][
            "real_world_taxpayer_absence_asserted"
        ]
        is False
    )


def test_full_receipt_driven_replay_completes_supplied_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, operation, initial, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    income = income_fixtures._component(initial["scope_binding"], tax_base)
    sources = source_fixtures._component(initial["scope_binding"], income)
    receipt = scope_fixtures._runtime(store).resolve(
        definition_ref=package_fixtures._definition_ref(),
        scope=scope_fixtures._scope(context),
        typed_component_evidence=[
            package_fixtures._component(operation),
            source_fixtures._component_evidence(sources),
        ],
        assertion_refs=[],
        context=context,
    )
    filing = filing_fixtures._component(receipt["scope_binding"])
    budget = budget_fixtures._component(receipt["scope_binding"], filing, income)
    category = tax_base["input_snapshot"]["category_tax_model"]
    financial = _component(receipt["scope_binding"], category)

    package = package_fixtures._runtime(store).assemble(
        definition_ref=package_fixtures._definition_ref(),
        scope_receipt=receipt,
        typed_component_snapshots=[
            package_fixtures._component(operation),
            filing_fixtures._component_evidence(filing),
            budget_fixtures._component_evidence(budget),
            income_fixtures._component_evidence(income),
            source_fixtures._component_evidence(sources),
            _component_evidence(financial),
        ],
        context=context,
    )

    states = {
        row["domain_id"]: row["state"] for row in package["requirement_resolutions"]
    }
    assert package["status"] == "DECLARATION_COMPLETE_FOR_SUPPLIED_CASE"
    assert package["completeness_receipt"]["blockers"] == []
    assert package["completeness_receipt"]["first_blocker"] is None
    assert package["completeness_receipt"]["completeness_kind"] == (
        "supplied_case_evidence_set"
    )
    assert (
        package["completeness_receipt"][
            "real_world_taxpayer_completeness_asserted"
        ]
        is False
    )
    assert sum(state == "RESOLVED" for state in states.values()) == 5
    assert (
        sum(
            state == "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
            for state in states.values()
        )
        == 6
    )
    assert (
        package_fixtures._closed_runtime().validate_package(package=package)
        == package
    )


def test_completeness_or_category_tamper_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    category = tax_base["input_snapshot"]["category_tax_model"]
    value = _input(receipt["scope_binding"], category)
    value["completeness_evidence"]["real_world_taxpayer_absence_asserted"] = True
    with pytest.raises(Gate5DeclarationFinancialInvestmentResultsError) as exc_info:
        Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
            component_input=value
        )
    assert exc_info.value.code == "gate5_financial_investment_completeness_invalid"

    component = _component(receipt["scope_binding"], category)
    component["category_tax_models"][0]["status"] = "incomplete"
    with pytest.raises(Gate5DeclarationFinancialInvestmentResultsError) as exc_info:
        Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().validate_component(
            component=component,
            scope_binding=receipt["scope_binding"],
        )
    assert exc_info.value.code == "gate5_financial_investment_component_mismatch"


def test_factory_source_reuses_category_owner_and_has_no_hidden_authority() -> None:
    source = inspect.getsource(module)
    imports = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert len(FACTORY_REQUIRED) == 2
    assert FORBIDDEN
    assert "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()" in source
    assert all("artifact_models" not in name for name in imports)
    assert all("gate4" not in name for name in imports)
    assert all("sqlite" not in name for name in imports)
    assert all("openai" not in name for name in imports)


def _component(scope_binding: dict, category: dict) -> dict:
    return Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
        component_input=_input(scope_binding, category)
    )


def _component_evidence(component: dict) -> dict:
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
        "component_contract_id": (
            GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION
        ),
        "component_sha256": _sha256(component),
        "payload": copy.deepcopy(component),
    }


def _input(scope_binding: dict, category: dict) -> dict:
    category_hash = _sha256(category)
    return {
        "schema_version": GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION,
        "scope_binding": copy.deepcopy(scope_binding),
        "category_tax_models": [copy.deepcopy(category)],
        "completeness_evidence": {
            "schema_version": (
                GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPLETENESS_SCHEMA_VERSION
            ),
            "status": "asserted_complete_for_supplied_case",
            "coverage_kind": "all_financial_investment_evidence_supplied_to_case",
            "scope_binding_sha256": scope_binding["scope_binding_sha256"],
            "category_model_sha256s": [category_hash],
            "activated_obligation_refs": [
                "obl_securities_and_derivatives_results"
            ],
            "not_activated_obligation_refs": [
                "obl_digital_financial_asset_and_right_results",
                "obl_investment_partnership_results",
            ],
            "real_world_taxpayer_absence_asserted": False,
            "provenance": {
                "source_kind": "synthetic_proof_evidence",
                "source_ref": "g532-synthetic-financial-supplied-case-complete",
                "input_channel": (
                    "financial_investment_supplied_case_completeness"
                ),
                "real_user_fact": False,
            },
        },
    }


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
