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
from broker_reports_gate1.gate5_tax_period_category_aggregation import (
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
import test_broker_reports_gate5_declaration_budget_outcome as budget_fixtures
import test_broker_reports_gate5_declaration_income_sources as source_fixtures
import test_broker_reports_gate5_declaration_scope_resolution as scope_fixtures
import test_broker_reports_gate5_declaration_tax_settlement as income_fixtures
import test_broker_reports_gate5_filing_and_party_identity as filing_fixtures
import test_broker_reports_gate5_resolved_declaration_package as package_fixtures
import test_broker_reports_ordinary_trade_tax_model_bridge as bridge_fixtures


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


def test_operation_set_input_v1_derives_one_existing_component_from_two_operations(
    tmp_path: Path,
) -> None:
    operation_set, scope = _proven_operation_set(tmp_path)

    component = Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
        component_input=_operation_set_input(operation_set, scope)
    )

    assert component["schema_version"] == (
        GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION
    )
    assert component["input_snapshot"]["schema_version"] == (
        "broker_reports_gate5_financial_investment_results_input_v1"
    )
    assert "category_tax_models" not in component["input_snapshot"]
    assert component["category_tax_models"] == [
        operation_set["category_result"]["category_tax_model"]
    ]
    assert len(operation_set["operation_results"]) == 2


def test_v0_input_remains_the_existing_component_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    value = _input(receipt["scope_binding"], tax_base["input_snapshot"]["category_tax_model"])

    component = Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
        component_input=value
    )

    assert component["schema_version"] == (
        GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION
    )
    assert component["input_snapshot"] == value


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("omitted", "gate5_financial_investment_operation_set_members_invalid"),
        ("extra", "gate5_financial_investment_operation_set_members_invalid"),
        ("foreign", "gate5_financial_investment_operation_set_scope_mismatch"),
        ("case", "gate5_financial_investment_operation_set_scope_mismatch"),
        ("scope", "gate5_financial_investment_operation_set_scope_mismatch"),
        (
            "consumption_hash",
            "gate5_financial_investment_operation_set_members_invalid",
        ),
        ("member", "gate5_financial_investment_operation_set_members_invalid"),
        ("demands", "gate5_financial_investment_operation_set_invalid"),
        (
            "current_not_ready",
            "gate5_financial_investment_operation_set_current_fact_invalid",
        ),
        ("raw_category", "gate5_financial_investment_operation_set_input_invalid"),
    ],
)
def test_operation_set_input_v1_rejects_unbound_or_incomplete_bridge_material(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    operation_set, scope = _proven_operation_set(tmp_path / mutation)
    value = _operation_set_input(operation_set, scope)
    receipt = value["operation_set_result"]
    if mutation == "omitted":
        receipt["operation_results"] = receipt["operation_results"][:-1]
    elif mutation == "extra":
        receipt["operation_results"].append(
            copy.deepcopy(receipt["operation_results"][0])
        )
    elif mutation == "foreign":
        receipt["taxpayer_binding"]["taxpayer_scope_ref"] = "foreign-taxpayer"
    elif mutation == "case":
        value["scope_binding"]["case_id"] = "foreign-case"
        value["scope_binding"] = _reseal_scope(value["scope_binding"])
    elif mutation == "scope":
        value["scope_binding"]["taxpayer_scope_ref"] = "foreign-taxpayer"
        value["scope_binding"] = _reseal_scope(value["scope_binding"])
    elif mutation == "consumption_hash":
        receipt["operation_set"]["source_fact_consumption_sha256"] = "0" * 64
    elif mutation == "member":
        receipt["category_result"]["scope_binding"]["members"] = []
    elif mutation == "demands":
        receipt["demands"] = [{"required_input": "forbidden-demand"}]
    elif mutation == "current_not_ready":
        receipt["operation_set"]["current_fact_set_snapshot"]["status"] = (
            "SOURCE_ROLE_INCOMPLETE"
        )
    else:
        value["category_tax_models"] = [
            copy.deepcopy(receipt["category_result"]["category_tax_model"])
        ]

    with pytest.raises(Gate5DeclarationFinancialInvestmentResultsError) as exc_info:
        Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
            component_input=value
        )
    assert exc_info.value.code == expected_code


def test_operation_set_input_v1_rejects_self_consistent_subset_of_snapshot_disposals(
    tmp_path: Path,
) -> None:
    operation_set, scope = _proven_operation_set(tmp_path)
    value = _operation_set_input(operation_set, scope)
    receipt = value["operation_set_result"]
    operation = receipt["operation_results"][0]
    category_runtime = Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
    category_scope = receipt["operation_set"]["scope_binding"]["scope"]
    members = [
        {
            "operation_ref": operation["operation_ref"],
            "source_scope_ref": scope["case_id"],
            "tax_model": copy.deepcopy(operation["operation_result"]["tax_model"]),
        }
    ]
    binding = category_runtime.describe_scope(scope=category_scope, members=members)
    completeness = copy.deepcopy(receipt["category_result"]["completeness"])
    completeness["scope_binding_sha256"] = binding["scope_binding_sha256"]
    receipt["category_result"] = category_runtime.run_tax_model(
        scope=category_scope,
        members=members,
        completeness_evidence=completeness,
    )
    receipt["operation_results"] = [operation]
    receipt["operation_set"]["disposal_fact_ids"] = [operation["disposal_fact_id"]]
    receipt["operation_set"]["operation_refs"] = [operation["operation_ref"]]
    receipt["operation_set"]["disposal_fact_ids_sha256"] = _sha256(
        receipt["operation_set"]["disposal_fact_ids"]
    )
    receipt["operation_set"]["scope_binding"] = binding

    with pytest.raises(Gate5DeclarationFinancialInvestmentResultsError) as exc_info:
        Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
            component_input=value
        )
    assert exc_info.value.code == "gate5_financial_investment_operation_set_invalid"


def test_operation_set_input_v1_rebuilds_category_from_unchanged_operation_models(
    tmp_path: Path,
) -> None:
    operation_set, scope = _proven_operation_set(tmp_path)
    value = _operation_set_input(operation_set, scope)
    category_result = value["operation_set_result"]["category_result"]
    for aggregate in (
        category_result["known_values"]["gross_income"],
        category_result["category_tax_model"]["category_gross_income"],
    ):
        aggregate["value"]["amount"] = "121.00"
        aggregate["derivation"]["contributions"][0]["value"]["amount"] = "61.00"

    with pytest.raises(Gate5DeclarationFinancialInvestmentResultsError) as exc_info:
        Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
            component_input=value
        )

    assert exc_info.value.code == "gate5_financial_investment_operation_set_category_invalid"


def test_operation_set_input_v1_rejects_resealed_scope_binding_without_scope(
    tmp_path: Path,
) -> None:
    operation_set, scope = _proven_operation_set(tmp_path)
    value = _operation_set_input(operation_set, scope)
    scope_binding = value["operation_set_result"]["operation_set"]["scope_binding"]
    scope_binding.pop("scope")
    scope_binding["scope_binding_sha256"] = _sha256(
        {
            key: item
            for key, item in scope_binding.items()
            if key != "scope_binding_sha256"
        }
    )
    value["operation_set_result"]["category_result"]["scope_binding"] = (
        copy.deepcopy(scope_binding)
    )

    with pytest.raises(Gate5DeclarationFinancialInvestmentResultsError) as exc_info:
        Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
            component_input=value
        )

    assert exc_info.value.code == "gate5_financial_investment_operation_set_members_invalid"


def test_operation_set_input_v1_rejects_erased_real_acquisition_commission_demand(
    tmp_path: Path,
) -> None:
    store, context, _facts = bridge_fixtures._case(
        tmp_path,
        rows=bridge_fixtures._two_disposal_rows(),
    )
    runtime = bridge_fixtures._runtime(store)
    preflight = bridge_fixtures._run_operation_set(
        runtime,
        context=context,
        completeness_evidence=None,
    )
    operation_set = bridge_fixtures._run_operation_set(
        runtime,
        context=context,
        completeness_evidence=bridge_fixtures._completeness(
            preflight["operation_set"]["scope_binding"]["scope_binding_sha256"]
        ),
    )
    assert operation_set["demands"]
    assert operation_set["demands"][0]["required_input"] == (
        "partial_acquisition_commission_allocation"
    )
    value = _operation_set_input(operation_set, _operation_set_scope(context))
    value["operation_set_result"]["demands"] = []

    with pytest.raises(Gate5DeclarationFinancialInvestmentResultsError) as exc_info:
        Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
            component_input=value
        )

    assert exc_info.value.code == "gate5_financial_investment_operation_set_invalid"


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


def _proven_operation_set(tmp_path: Path) -> tuple[dict, dict]:
    rows = list(bridge_fixtures._two_disposal_rows())
    for position in (1, 3):
        rows[position] = bridge_fixtures._with_roles(
            rows[position],
            broker_commission="",
            exchange_commission="",
        )
    store, context, _facts = bridge_fixtures._case(
        tmp_path,
        rows=tuple(rows),
    )
    runtime = bridge_fixtures._runtime(store)
    preflight = bridge_fixtures._run_operation_set(
        runtime,
        context=context,
        completeness_evidence=None,
    )
    completed = bridge_fixtures._run_operation_set(
        runtime,
        context=context,
        completeness_evidence=bridge_fixtures._completeness(
            preflight["operation_set"]["scope_binding"]["scope_binding_sha256"]
        ),
    )
    assert completed["status"] == "proven"
    assert completed["demands"] == []
    return completed, _operation_set_scope(context)


def _operation_set_scope(context) -> dict:
    return _reseal_scope(
        {
            "schema_version": "broker_reports_gate5_supplied_case_scope_v0",
            "scope_ref": "financial-investment-operation-set-2025",
            "taxpayer_scope_ref": "synthetic-taxpayer-control",
            "tax_period": "2025",
            "authenticated_user_ref": context.user_id,
            "case_id": context.case_id,
            "normalization_run_ref": context.normalization_run_id,
        }
    )


def _operation_set_input(operation_set: dict, scope: dict) -> dict:
    category = operation_set["category_result"]["category_tax_model"]
    return {
        "schema_version": "broker_reports_gate5_financial_investment_results_input_v1",
        "scope_binding": copy.deepcopy(scope),
        "operation_set_result": copy.deepcopy(operation_set),
        "completeness_evidence": copy.deepcopy(_input(scope, category)["completeness_evidence"]),
    }


def _reseal_scope(scope: dict) -> dict:
    base = {key: copy.deepcopy(value) for key, value in scope.items() if key != "scope_binding_sha256"}
    return {**base, "scope_binding_sha256": _sha256(base)}


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
