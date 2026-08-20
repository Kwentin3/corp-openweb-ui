from __future__ import annotations

import inspect
from pathlib import Path

from broker_reports_gate1.gate5_real_tax_case_assembly import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate5RealTaxCaseAssemblyRuntime,
    Gate5RealTaxCaseAssemblyRuntimeFactory,
    _demand_terminal,
)

import test_broker_reports_gate5_deterministic_source_fact_consumption as source_fixtures


def test_demand_first_case_assembly_keeps_real_gaps_exact(tmp_path: Path) -> None:
    store, context = source_fixtures._case(
        tmp_path / "real-gap",
        include_purchases=False,
    )

    assembled = _runtime(store).assemble(
        source_fact_methodology_ref=source_fixtures._source_methodology_ref(),
        context=context,
        evidence_mode="REAL_EVIDENCE",
    )

    assert assembled["terminals"] == [
        "REAL_CASE_ASSEMBLY_PROVEN",
        "EXACT_EVIDENCE_GAPS_LOCALIZED",
    ]
    assert assembled["metrics"]["declaration_demands_total"] == 25
    assert assembled["metrics"]["MISSING_EVIDENCE"] == 4
    assert assembled["metrics"]["SOURCE_EVIDENCE_INSUFFICIENT"] == 3
    assert assembled["metrics"]["METHODOLOGY_UNRESOLVED"] == 2
    assert assembled["metrics"]["NOT_ACTIVATED_FOR_SUPPLIED_CASE"] == 16
    assert assembled["metrics"]["RESOLVED"] == 0
    assert assembled["metrics"]["invented_facts"] == 0
    assert assembled["metrics"]["invented_relations"] == 0
    assert assembled["metrics"]["active_demands_with_methodology_binding"] == 9
    assert assembled["metrics"]["gap_owner_classification_counts"] == {
        "EXTERNAL_AUTHORITATIVE_FACT_MISSING": 0,
        "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT": 0,
        "METHODOLOGY_RULE_MISSING": 2,
        "REAL_SOURCE_EVIDENCE_MISSING": 3,
        "USER_CASE_FACT_MISSING": 4,
    }
    active = [
        row
        for row in assembled["declaration_demands"]
        if row["terminal"] != "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
    ]
    assert len(active) == 9
    assert all(row["gap_owner_classification"] for row in active)
    assert assembled["declaration_input_methodology_binding"][
        "methodology_id"
    ] == "ru-3ndfl-2025-declaration-input-contract"
    assert assembled["multi_source_assembly"]["status"] == "PROVEN"
    assert assembled["reconciliation"] == "not_performed"
    securities = next(
        row
        for row in assembled["declaration_demands"]
        if row["demand"] == "obl_securities_and_derivatives_results"
    )
    assert securities["terminal"] == "SOURCE_EVIDENCE_INSUFFICIENT"
    assert securities["available_evidence"]["fact_ids"]
    assert securities["blocker"]["declaration_demand"] == securities["demand"]
    assert securities["blocker"]["required_fact"]
    assert securities["blocker"]["evidence_searched"]["source_fact_count"] > 0
    assert securities["blocker"]["why_supplied_evidence_is_insufficient"]
    assert securities["blocker"]["evidence_that_could_close"]
    for demand in {
        "obl_digital_financial_asset_and_right_results",
        "obl_investment_partnership_results",
    }:
        row = next(
            item for item in assembled["declaration_demands"] if item["demand"] == demand
        )
        assert row["terminal"] == "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
        assert row["available_evidence"]["fact_ids"] == []


def test_synthetic_control_is_separate_and_does_not_promote_declaration(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(tmp_path / "synthetic-control")

    assembled = _runtime(store).assemble(
        source_fact_methodology_ref=source_fixtures._source_methodology_ref(),
        context=context,
        evidence_mode="SYNTHETIC_CONTROL",
    )

    assert assembled["evidence_mode"] == "SYNTHETIC_CONTROL"
    assert assembled["terminals"][0] == "SYNTHETIC_CASE_ASSEMBLY_CONTROL"
    assert "REAL_CASE_ASSEMBLY_PROVEN" not in assembled["terminals"]
    securities = next(
        row
        for row in assembled["declaration_demands"]
        if row["demand"] == "obl_securities_and_derivatives_results"
    )
    assert securities["terminal"] == "AVAILABLE"
    assert assembled["metrics"]["fifo_calculations"] == 1
    assert assembled["metrics"]["tax_model_ready_calculations"] == 1
    assert assembled["metrics"]["RESOLVED"] == 0
    assert assembled["real_world_taxpayer_completeness_asserted"] is False
    assert assembled["persistence"] == "none_new"


def test_preserved_dividend_or_coupon_is_not_misreported_as_a_source_gap() -> None:
    source = {
        "financial_type_counts": {
            "DIVIDEND_INCOME": 1,
            "COUPON_INCOME": 1,
        },
        "blockers": [],
        "tax_model_ready_calculations": 0,
    }

    assert _demand_terminal(
        domain_id="taxable_income_by_source",
        obligation_ref="obl_foreign_source_taxable_income_and_foreign_tax",
        source=source,
    ) == "METHODOLOGY_UNRESOLVED"
    assert _demand_terminal(
        domain_id="income_group_tax_results",
        obligation_ref="obl_income_group_tax_base_results",
        source=source,
    ) == "METHODOLOGY_UNRESOLVED"


def test_case_assembly_factory_is_read_only_and_factory_backed() -> None:
    factory_source = inspect.getsource(Gate5RealTaxCaseAssemblyRuntimeFactory)
    runtime_source = inspect.getsource(Gate5RealTaxCaseAssemblyRuntime)
    assert "Gate5DeterministicSourceFactConsumptionRuntimeFactory" in factory_source
    assert "Gate5TrustedFullDeclarationDefinitionAuthorityFactory" in factory_source
    assert "Gate5FullDeclarationDefinitionAuthoringFactory" in factory_source
    assert "Gate5TrustedMethodologyAuthorityFactory" in factory_source
    assert ".assemble_available(" in runtime_source
    assert ".put(" not in runtime_source
    assert "direct SQL" in FORBIDDEN[0]
    assert "Gate5RealTaxCaseAssemblyRuntimeFactory.create" in FACTORY_REQUIRED[0]


def _runtime(store):
    return Gate5RealTaxCaseAssemblyRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
