from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import gate5_declaration_income_sources as module
from broker_reports_gate1.gate5_declaration_income_sources import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
    GATE5_TAXABLE_INCOME_SOURCE_INPUT_SCHEMA_VERSION,
    Gate5DeclarationIncomeSourcesError,
    Gate5DeclarationIncomeSourcesRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
)
import test_broker_reports_gate5_declaration_budget_outcome as budget_fixtures
import test_broker_reports_gate5_declaration_scope_resolution as scope_fixtures
import test_broker_reports_gate5_declaration_tax_settlement as income_fixtures
import test_broker_reports_gate5_filing_and_party_identity as filing_fixtures
import test_broker_reports_gate5_resolved_declaration_package as package_fixtures


def test_exact_source_component_accounts_validated_income_groups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    income = income_fixtures._component(receipt["scope_binding"], tax_base)
    component = _component(receipt["scope_binding"], income)

    assert component["status"] == "complete"
    assert component["root_coverage"] == "exact_root_domain"
    assert component["covered_obligation_refs"] == [
        "obl_russian_source_taxable_income",
        "obl_foreign_source_taxable_income_and_foreign_tax",
    ]
    assert component["source_entries"][0]["jurisdiction_kind"] == "russian_source"
    assert component["source_entries"][0]["foreign_tax"] is None
    assert component["obligation_resolutions"] == [
        {
            "obligation_ref": "obl_russian_source_taxable_income",
            "state": "RESOLVED",
            "real_world_absence_asserted": False,
        },
        {
            "obligation_ref": "obl_foreign_source_taxable_income_and_foreign_tax",
            "state": "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
            "real_world_absence_asserted": False,
        },
    ]
    assert component["completeness_evidence"]["provenance"]["real_user_fact"] is False


def test_source_replay_closes_component_and_exposes_financial_component_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, operation, initial, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    income = income_fixtures._component(initial["scope_binding"], tax_base)
    sources = _component(initial["scope_binding"], income)
    receipt = scope_fixtures._runtime(store).resolve(
        definition_ref=package_fixtures._definition_ref(),
        scope=scope_fixtures._scope(context),
        typed_component_evidence=[
            package_fixtures._component(operation),
            _component_evidence(sources),
        ],
        assertion_refs=[],
        context=context,
    )
    filing = filing_fixtures._component(receipt["scope_binding"])
    budget = budget_fixtures._component(receipt["scope_binding"], filing, income)
    package = package_fixtures._runtime(store).assemble(
        definition_ref=package_fixtures._definition_ref(),
        scope_receipt=receipt,
        typed_component_snapshots=[
            package_fixtures._component(operation),
            filing_fixtures._component_evidence(filing),
            budget_fixtures._component_evidence(budget),
            income_fixtures._component_evidence(income),
            _component_evidence(sources),
        ],
        context=context,
    )

    states = {
        row["domain_id"]: row["state"] for row in package["requirement_resolutions"]
    }
    assert states["refundable_amount_disposal"] == (
        "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
    )
    assert states["taxable_income_by_source"] == "RESOLVED"
    assert package["completeness_receipt"]["first_blocker"] == {
        "domain_id": "financial_investment_results",
        "blocker_class": "component",
        "state": "REQUIRED_MISSING",
        "reason": "required_component_bounded_only",
    }
    assert receipt["human_residual"] is None
    assert (
        package_fixtures._closed_runtime().validate_package(package=package) == package
    )


def test_incomplete_accounting_or_tamper_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    income = income_fixtures._component(receipt["scope_binding"], tax_base)
    value = _input(receipt["scope_binding"], income)
    value["source_entries"][0]["gross_income"]["amount"] = "99.00"
    with pytest.raises(Gate5DeclarationIncomeSourcesError) as exc_info:
        Gate5DeclarationIncomeSourcesRuntimeFactory.create().create_component(
            component_input=value
        )
    assert exc_info.value.code == "gate5_income_sources_value_mismatch"

    runtime = Gate5DeclarationIncomeSourcesRuntimeFactory.create()
    component = _component(receipt["scope_binding"], income)
    component["source_entries"][0]["income_kind"] = "interest"
    with pytest.raises(Gate5DeclarationIncomeSourcesError) as exc_info:
        runtime.validate_component(
            component=component, scope_binding=receipt["scope_binding"]
        )
    assert exc_info.value.code == "gate5_income_sources_component_mismatch"


def test_factory_source_has_no_generic_or_hidden_authority() -> None:
    source = inspect.getsource(module)
    imports = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert len(FACTORY_REQUIRED) == 2
    assert FORBIDDEN
    assert "Gate5DeclarationTaxSettlementRuntimeFactory.create" in source
    assert all("artifact_models" not in name for name in imports)
    assert all("gate4" not in name for name in imports)
    assert all("sqlite" not in name for name in imports)
    assert all("openai" not in name for name in imports)


def _component(scope_binding: dict, income: dict) -> dict:
    return Gate5DeclarationIncomeSourcesRuntimeFactory.create().create_component(
        component_input=_input(scope_binding, income)
    )


def _component_evidence(component: dict) -> dict:
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
        "component_contract_id": GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
        "component_sha256": _sha256(component),
        "payload": copy.deepcopy(component),
    }


def _input(scope_binding: dict, income: dict) -> dict:
    result = income["group_results"][0]
    model = result["tax_base_model"]
    source_ref = "g531-synthetic-russian-securities-source"
    return {
        "schema_version": GATE5_TAXABLE_INCOME_SOURCE_INPUT_SCHEMA_VERSION,
        "scope_binding": copy.deepcopy(scope_binding),
        "income_group_results_component": copy.deepcopy(income),
        "source_entries": [
            {
                "source_ref": source_ref,
                "income_group_semantic": result["income_group_semantic"],
                "jurisdiction_kind": "russian_source",
                "jurisdiction_code": "RU",
                "income_kind": "securities_disposal",
                "source_party": {
                    "party_kind": "organization",
                    "display_name": "АО Тестовый брокер",
                    "inn": "9900000000",
                    "kpp": "990001001",
                    "oktmo": "45382000",
                },
                "gross_income": copy.deepcopy(model["total_income"]["value"]),
                "taxable_income": copy.deepcopy(model["taxable_income"]["value"]),
                "tax_agent": {
                    "status": "absent",
                    "withheld_tax": copy.deepcopy(
                        result["settlement_facts"]["withheld_at_source"]["value"]
                    ),
                },
                "foreign_tax": None,
                "provenance": _provenance(source_ref, "taxable_income_source"),
            }
        ],
        "completeness_evidence": {
            "schema_version": "broker_reports_gate5_taxable_income_source_completeness_v0",
            "status": "asserted_complete",
            "coverage_kind": "all_taxable_income_sources_for_declaration_scope",
            "scope_binding_sha256": scope_binding["scope_binding_sha256"],
            "income_group_results_component_id": income["component_id"],
            "source_refs": [source_ref],
            "provenance": _provenance(
                "g531-synthetic-taxable-source-completeness",
                "taxable_income_source_completeness",
            ),
        },
    }


def _provenance(source_ref: str, input_channel: str) -> dict:
    return {
        "source_kind": "synthetic_proof_evidence",
        "source_ref": source_ref,
        "input_channel": input_channel,
        "real_user_fact": False,
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
