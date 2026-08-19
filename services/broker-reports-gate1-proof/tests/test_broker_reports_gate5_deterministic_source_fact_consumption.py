from __future__ import annotations

import ast
from dataclasses import replace
import inspect
from pathlib import Path

import pytest

from broker_reports_gate1 import build_retention_policy
from broker_reports_gate1.gate4_financial_case_cache import (
    Gate4FinancialCaseRuntimeFactory,
)
from broker_reports_gate1.gate5_deterministic_source_fact_consumption import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_ACQUISITION_BASIS_COVERAGE_CONTRACT_TERMINAL,
    GATE5_COMMISSION_EVIDENCE_COVERAGE_SCHEMA_VERSION,
    GATE5_COMMISSION_SELECTION_CONTRACT_TERMINAL,
    GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_RESULT_SCHEMA_VERSION,
    GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_TERMINAL,
    GATE5_FIFO_WITHOUT_STORED_EVENT_TERMINAL,
    GATE5_SOURCE_GRANULARITY_TERMINAL,
    Gate5DeterministicSourceFactConsumptionError,
    Gate5DeterministicSourceFactConsumptionRuntime,
    Gate5DeterministicSourceFactConsumptionRuntimeFactory,
)
from broker_reports_gate1 import (
    gate5_deterministic_source_fact_consumption as consumption_module,
)
from broker_reports_gate1.gate5_securities_disposal_tax_model import (
    Gate5SecuritiesDisposalTaxModelRuntimeFactory,
)
from broker_reports_gate1.gate5_client_evidence_review import (
    Gate5ClientEvidenceReviewRuntimeFactory,
)
from broker_reports_gate1.gate5_trusted_methodology import (
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
import test_broker_reports_gate4_sql_materialization as gate4_fixtures
import test_broker_reports_gate5_securities_disposal_tax_model as tax_model_fixtures


def test_fifo_source_facts_reach_existing_declaration_model_without_event_relation(
    tmp_path: Path,
) -> None:
    store, context = _case(tmp_path)
    gate4_before = _gate4(store).list_facts(context=context)

    consumed = _consumer(store).run(
        methodology_ref=_source_methodology_ref(),
        context=context,
    )

    assert consumed["schema_version"] == (
        GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_RESULT_SCHEMA_VERSION
    )
    assert consumed["terminals"] == [
        GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_TERMINAL,
        GATE5_FIFO_WITHOUT_STORED_EVENT_TERMINAL,
        GATE5_SOURCE_GRANULARITY_TERMINAL,
    ]
    disposal = consumed["securities"][0]
    assert disposal["gross_income"]["value"] == _money("360.00")
    assert disposal["recognized_acquisition_cost"]["value"] == _money("140.00")
    assert disposal["acquisition_basis_coverage"] == {
        "schema_version": "broker_reports_gate5_acquisition_basis_coverage_v0",
        "concept": "ACQUISITION_BASIS_COVERAGE_GAP",
        "coverage_status": "COMPLETE",
        "disposed_quantity": "12",
        "supported_acquisition_basis_quantity": "12",
        "uncovered_quantity": "0",
        "interpretation": "quantity_level_source_evidence_coverage_only",
        "financial_event_relation_asserted": False,
        "synthetic_zero_cost_assigned": False,
        "tax_conclusion": "NOT_MADE",
        "terminals": [GATE5_ACQUISITION_BASIS_COVERAGE_CONTRACT_TERMINAL],
    }
    assert [
        item["consumed_quantity"]
        for item in disposal["recognized_acquisition_cost"]["fifo_inputs"]
    ] == ["10", "2"]
    assert [
        item["recognized_cost"]
        for item in disposal["recognized_acquisition_cost"]["fifo_inputs"]
    ] == [_money("100.00"), _money("40.00")]
    assert disposal["direct_transaction_expense"]["value"] == _money("5.00")
    assert disposal["direct_transaction_expense"]["source_context"] == (
        "SAME_SOURCE_TRANSACTION_ROW"
    )
    assert disposal["direct_transaction_expense"]["tax_deductibility_status"] == (
        "NOT_EVALUATED"
    )

    commissions = consumed["assertions"]["commissions"]
    assert commissions["mode"] == "hybrid"
    assert sorted(
        item["values"]["amount"]
        for item in commissions["detail"]
        if item["financial_type"] == "COMMISSION"
    ) == ["10.00", "15.00"]
    assert [item["values"]["amount"] for item in commissions["aggregate"]] == ["40.00"]
    assert commissions["reconciliation"] == "not_performed"
    withheld = consumed["assertions"]["withheld_tax"]
    assert withheld["mode"] == "hybrid"
    assert [item["values"]["amount"] for item in withheld["detail"]] == ["4.00"]
    assert [item["values"]["amount"] for item in withheld["aggregate"]] == ["7.00"]
    assert withheld["reconciliation"] == "not_performed"
    assert consumed["capability_map"]["partial_acquisition_commission"] == (
        "METHODOLOGY_UNRESOLVED"
    )

    all_keys = _keys(consumed)
    assert {
        "purchase_sale_relation",
        "financial_event",
        "financial_event_id",
        "reconciled_operation",
    }.isdisjoint(all_keys)

    projected = _tax_model(store).run_from_current_source_facts(
        methodology_ref=_tax_methodology_ref(),
        source_fact_methodology_ref=_source_methodology_ref(),
        resolved_inputs=tax_model_fixtures._resolved_inputs(),
        disposal_fact_id=disposal["disposal_fact_id"],
        context=context,
    )
    assert projected["status"] == "projected"
    assert projected["tax_model"]["category_gross_income"]["value"] == _money("360.00")
    assert projected["tax_model"]["allowable_expenses"]["total"] == _money("145.00")
    assert projected["declaration_semantics"]["operation_category_gross_income"] == {
        "amount": "360.00",
        "currency": "RUB",
    }
    assert projected["declaration_semantics"]["allowable_expenses"] == {
        "amount": "145.00",
        "currency": "RUB",
    }
    assert _gate4(store).list_facts(context=context) == gate4_before

    assessed = _consumer(store).assess(
        methodology_ref=_source_methodology_ref(),
        context=context,
    )
    assert assessed["security_tax_input_status"] == "READY_FOR_FIFO"
    assert assessed["security_fact_counts"] == {
        "total": 3,
        "ready": 3,
        "source_evidence_insufficient": 0,
    }
    assert assessed["assertions"]["commissions"]["mode"] == "hybrid"
    assert assessed["assertions"]["withheld_tax"]["mode"] == "hybrid"
    assert assessed["stored_financial_event_relations"] == 0


def test_tax_adjustment_remains_visible_in_gate4_but_outside_tax_formula(
    tmp_path: Path,
) -> None:
    store, context = _case(tmp_path, include_tax_adjustment=True)
    gate4_facts = _gate4(store).list_facts(context=context)
    adjustments = [
        fact for fact in gate4_facts if fact["financial_type"] == "TAX_ADJUSTMENT"
    ]
    assert len(adjustments) == 1
    assert adjustments[0]["semantic_kind"] == "normalized_source_fact"

    consumed = _consumer(store).run(
        methodology_ref=_source_methodology_ref(),
        context=context,
    )

    withheld = consumed["assertions"]["withheld_tax"]
    assert [item["values"]["amount"] for item in withheld["detail"]] == ["4.00"]
    assert [item["values"]["amount"] for item in withheld["aggregate"]] == ["7.00"]
    assert "TAX_ADJUSTMENT" not in str(withheld)
    assert "tax_adjustment" not in consumed
    assert _gate4(store).list_facts(context=context) == gate4_facts


def test_assertion_modes_preserve_detail_and_aggregate_independently(
    tmp_path: Path,
) -> None:
    detail_store, detail_context = _case(
        tmp_path / "detail",
        include_commission_total=False,
        include_withheld_total=False,
    )
    detail = _consumer(detail_store).run(
        methodology_ref=_source_methodology_ref(), context=detail_context
    )
    assert detail["assertions"]["commissions"]["mode"] == "detail"
    assert detail["assertions"]["withheld_tax"]["mode"] == "detail"

    aggregate_store, aggregate_context = _case(
        tmp_path / "aggregate",
        include_commission_detail=False,
        include_withheld_detail=False,
    )
    aggregate = _consumer(aggregate_store).run(
        methodology_ref=_source_methodology_ref(), context=aggregate_context
    )
    assert aggregate["assertions"]["commissions"]["mode"] == "hybrid"
    assert {
        item["financial_type"]
        for item in aggregate["assertions"]["commissions"]["detail"]
    } == {"TRANSACTION_CHARGE"}
    assert aggregate["assertions"]["withheld_tax"]["mode"] == "aggregate"


def test_commission_details_selected_when_exact_coverage_is_proven(
    tmp_path: Path,
) -> None:
    store, context = _case(
        tmp_path / "commission-detail",
        include_direct_charge=False,
        include_commission_total=False,
    )
    assembled = _consumer(store).assemble_available(
        methodology_ref=_source_methodology_ref(), context=context
    )
    selection = _consumer(store).select_commission_evidence(
        source_assembly=assembled,
        coverage=_commission_coverage(
            assembled, detail_status="PROVEN_COMPLETE", aggregate_status="ABSENT"
        ),
    )

    assert selection["status"] == "SELECTED"
    assert selection["selected_representation"] == "DETAIL"
    assert selection["selected_value"] == _money("25.00")
    assert selection["terminals"] == [GATE5_COMMISSION_SELECTION_CONTRACT_TERMINAL]
    assert selection["tax_eligibility_status"] == "NOT_EVALUATED"


def test_commission_aggregate_selected_when_it_is_the_only_proven_representation(
    tmp_path: Path,
) -> None:
    store, context = _case(
        tmp_path / "commission-aggregate",
        include_direct_charge=False,
        include_commission_detail=False,
    )
    assembled = _consumer(store).assemble_available(
        methodology_ref=_source_methodology_ref(), context=context
    )
    selection = _consumer(store).select_commission_evidence(
        source_assembly=assembled,
        coverage=_commission_coverage(
            assembled, detail_status="ABSENT", aggregate_status="PROVEN_MATCHING"
        ),
    )

    assert selection["status"] == "SELECTED"
    assert selection["selected_representation"] == "AGGREGATE"
    assert selection["selected_value"] == _money("40.00")


def test_commission_hybrid_preserves_both_and_selects_details_without_comparison(
    tmp_path: Path,
) -> None:
    store, context = _case(tmp_path / "commission-hybrid", include_direct_charge=False)
    assembled = _consumer(store).assemble_available(
        methodology_ref=_source_methodology_ref(), context=context
    )
    selection = _consumer(store).select_commission_evidence(
        source_assembly=assembled,
        coverage=_commission_coverage(
            assembled,
            detail_status="PROVEN_COMPLETE",
            aggregate_status="PROVEN_MATCHING",
        ),
    )

    aggregate_id = assembled["assertions"]["commissions"]["aggregate"][0]["fact_id"]
    assert selection["selected_representation"] == "DETAIL"
    assert selection["selected_value"] == _money("25.00")
    assert aggregate_id in selection["unselected_preserved_fact_ids"]
    assert selection["source_assertions_preserved"] is True
    assert selection["double_counted_fact_ids"] == []
    assert selection["detail_aggregate_value_comparison_performed"] is False
    assert selection["reconciliation"] == "not_performed"


def test_commission_uncertain_detail_coverage_falls_back_to_matching_aggregate(
    tmp_path: Path,
) -> None:
    store, context = _case(tmp_path / "commission-fallback", include_direct_charge=False)
    assembled = _consumer(store).assemble_available(
        methodology_ref=_source_methodology_ref(), context=context
    )
    selection = _consumer(store).select_commission_evidence(
        source_assembly=assembled,
        coverage=_commission_coverage(
            assembled, detail_status="UNPROVEN", aggregate_status="PROVEN_MATCHING"
        ),
    )

    assert selection["status"] == "SELECTED"
    assert selection["selected_representation"] == "AGGREGATE"
    assert selection["selected_value"] == _money("40.00")


def test_commission_selection_fails_closed_without_any_proven_representation(
    tmp_path: Path,
) -> None:
    store, context = _case(
        tmp_path / "commission-fail-closed",
        include_direct_charge=False,
        include_commission_total=False,
    )
    assembled = _consumer(store).assemble_available(
        methodology_ref=_source_methodology_ref(), context=context
    )
    selection = _consumer(store).select_commission_evidence(
        source_assembly=assembled,
        coverage=_commission_coverage(
            assembled, detail_status="UNPROVEN", aggregate_status="ABSENT"
        ),
    )

    assert selection["status"] == "FAIL_CLOSED"
    assert selection["selected_representation"] is None
    assert selection["selected_value"] is None
    assert selection["selected_fact_ids"] == []
    assert selection["tax_eligibility_status"] == "NOT_EVALUATED"


def test_available_assembly_resolves_independent_group_and_localizes_other_gap(
    tmp_path: Path,
) -> None:
    store, context = _case(tmp_path / "available-assembly")
    _publish(
        store,
        context,
        document_id="unmatched-disposal",
        source_rows=("Sale|02.03.2025|BETA|7|210.00|RUB",),
        fact_specs=(
            (
                "SECURITY_DISPOSAL",
                _security_roles(
                    "02.03.2025", "7", "210.00", "RUB", asset="BETA"
                ),
            ),
        ),
    )
    _gate4(store).rebuild_case(context=context)

    assembled = _consumer(store).assemble_available(
        methodology_ref=_source_methodology_ref(),
        context=context,
    )

    groups = {item["asset"]: item for item in assembled["security_groups"]}
    assert groups["ACME"]["status"] == "RESOLVED"
    assert groups["ACME"]["multi_source"] is True
    assert groups["ACME"]["resolved_disposals"] == 1
    assert groups["BETA"]["status"] == "MISSING_EVIDENCE"
    assert groups["BETA"]["resolved_disposals"] == 0
    blocker = groups["BETA"]["blocker"]
    assert blocker["reason_code"] == (
        "gate5_source_fact_acquisition_quantity_insufficient"
    )
    assert blocker["required_quantity"] == "7"
    assert blocker["available_prior_quantity"] == "0"
    assert blocker["minimum_missing_quantity"] == "7"
    assert blocker["acquisition_basis_coverage"]["concept"] == (
        "ACQUISITION_BASIS_COVERAGE_GAP"
    )
    assert blocker["acquisition_basis_coverage"]["uncovered_quantity"] == "7"
    assert blocker["acquisition_basis_coverage"]["tax_conclusion"] == "NOT_MADE"
    assert blocker["current_methodology_blocking_decision"] == "BLOCKED"
    assert len(assembled["fifo_calculations"]) == 1
    assert assembled["tax_model_ready_calculations"] == 1
    assert assembled["invented_facts"] == 0
    assert assembled["invented_relations"] == 0
    assert assembled["reconciliation"] == "not_performed"


def test_acquisition_basis_coverage_gap_is_quantified_without_zero_cost_inference(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path / "basis-gap")
    _publish(
        store,
        context,
        document_id="basis-70",
        source_rows=("Purchase|01.01.2025|ACME|70|700.00|RUB",),
        fact_specs=(("SECURITY_PURCHASE", _security_roles("01.01.2025", "70", "700.00")),),
        purchase_date="01.01.2025",
    )
    _publish(
        store,
        context,
        document_id="disposal-100",
        source_rows=("Sale|01.03.2025|ACME|100|1000.00|RUB",),
        fact_specs=(("SECURITY_DISPOSAL", _security_roles("01.03.2025", "100", "1000.00")),),
    )
    _gate4(store).rebuild_case(context=context)

    assembled = _consumer(store).assemble_available(
        methodology_ref=_source_methodology_ref(), context=context
    )
    blocker = assembled["security_groups"][0]["blocker"]
    coverage = blocker["acquisition_basis_coverage"]

    assert coverage["coverage_status"] == "GAP"
    assert coverage["disposed_quantity"] == "100"
    assert coverage["supported_acquisition_basis_quantity"] == "70"
    assert coverage["uncovered_quantity"] == "30"
    assert coverage["financial_event_relation_asserted"] is False
    assert coverage["synthetic_zero_cost_assigned"] is False
    assert coverage["tax_conclusion"] == "NOT_MADE"
    assert assembled["fifo_calculations"] == []
    assert assembled["invented_relations"] == 0
    review = Gate5ClientEvidenceReviewRuntimeFactory(
        store=store, read_enabled=True
    ).create().review(source_assembly=assembled)
    finding = review["required_blockers"][0]
    assert finding["acquisition_basis_coverage"] == coverage
    assert finding["required_for_current_methodology"] is True
    assert finding["blocking_authority"] == (
        "article-214.1-fifo-acquisition-cost-proof-v0"
    )
    assert finding["tax_conclusion"] == "NOT_MADE"
    assert "does not make a gross-proceeds tax conclusion" in finding[
        "client_benefit_rationale"
    ]


def test_one_lot_covers_ten_disposals_without_persisted_pair_relations(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path / "one-lot-many-sales")
    _publish(
        store,
        context,
        document_id="lot-100",
        source_rows=("Purchase|01.01.2025|ACME|100|1000.00|RUB",),
        fact_specs=(("SECURITY_PURCHASE", _security_roles("01.01.2025", "100", "1000.00")),),
        purchase_date="01.01.2025",
    )
    for index in range(10):
        _publish(
            store,
            context,
            document_id=f"sale-{index + 1}",
            source_rows=("Sale|01.03.2025|ACME|10|120.00|RUB|Charge|1.00",),
            fact_specs=(
                ("SECURITY_DISPOSAL", _security_roles("01.03.2025", "10", "120.00")),
                (
                    "TRANSACTION_CHARGE",
                    (("date", "01.03.2025"), ("amount", "1.00"), ("currency", "RUB"), ("asset", "ACME")),
                ),
            ),
            target_indexes=(0, 0),
            same_table_row=True,
        )
    _gate4(store).rebuild_case(context=context)

    assembled = _consumer(store).assemble_available(
        methodology_ref=_source_methodology_ref(), context=context
    )

    assert len(assembled["fifo_calculations"]) == 10
    assert all(
        item["acquisition_basis_coverage"]["coverage_status"] == "COMPLETE"
        for item in assembled["fifo_calculations"]
    )
    assert assembled["stored_financial_event_relations"] == 0
    assert assembled["invented_relations"] == 0
    assert "financial_event_relations" not in assembled


def test_same_row_charge_is_source_context_not_an_automatic_tax_deduction(
    tmp_path: Path,
) -> None:
    store, context = _case(tmp_path / "charge-boundary")
    consumed = _consumer(store).run(
        methodology_ref=_source_methodology_ref(), context=context
    )
    disposal = consumed["securities"][0]
    inputs = tax_model_fixtures._resolved_inputs()
    inputs["expense_evidence"]["transaction_expense"]["documented"]["value"] = False

    projected = _tax_model(store).run_from_current_source_facts(
        methodology_ref=_tax_methodology_ref(),
        source_fact_methodology_ref=_source_methodology_ref(),
        resolved_inputs=inputs,
        disposal_fact_id=disposal["disposal_fact_id"],
        context=context,
    )

    assert disposal["direct_transaction_expense"]["tax_deductibility_status"] == (
        "NOT_EVALUATED"
    )
    decisions = {
        item["component_id"]: item
        for item in projected["tax_model"]["allowable_expenses"]["decisions"]
    }
    assert decisions["transaction_expense"]["status"] == "not_allowed_unproven"
    assert projected["tax_model"]["allowable_expenses"]["total"] == _money("140.00")


def test_missing_exact_disposal_charge_fails_closed_at_tax_model_boundary(
    tmp_path: Path,
) -> None:
    store, context = _case(tmp_path, include_direct_charge=False)
    consumed = _consumer(store).run(
        methodology_ref=_source_methodology_ref(), context=context
    )
    disposal = consumed["securities"][0]
    assert disposal["direct_transaction_expense"] == {
        "status": "missing",
        "reason": "no_same_source_transaction_row_charge",
        "source_context": "SAME_SOURCE_TRANSACTION_ROW",
        "source_semantic": "TRANSACTION_CHARGE_EVIDENCE",
        "tax_deductibility_status": "NOT_EVALUATED",
    }

    with pytest.raises(Gate5DeterministicSourceFactConsumptionError) as caught:
        _tax_model(store).run_from_current_source_facts(
            methodology_ref=_tax_methodology_ref(),
            source_fact_methodology_ref=_source_methodology_ref(),
            resolved_inputs=tax_model_fixtures._resolved_inputs(),
            disposal_fact_id=disposal["disposal_fact_id"],
            context=context,
        )
    assert caught.value.code == "gate5_source_fact_direct_expense_missing"


def test_same_date_different_unit_cost_fifo_fails_closed(
    tmp_path: Path,
) -> None:
    store, context = _case(tmp_path, second_purchase_date="01.01.2025")

    with pytest.raises(Gate5DeterministicSourceFactConsumptionError) as caught:
        _consumer(store).run(
            methodology_ref=_source_methodology_ref(),
            context=context,
        )
    assert caught.value.code == (
        "gate5_source_fact_same_date_fifo_methodology_unresolved"
    )


def test_direct_charge_requires_same_explicit_source_transaction_row() -> None:
    binding = {"canonical_binding": {"document_id": "d", "version": "v1"}}

    def fact(target):
        return {"gate3_binding": binding, "annotation_target": target}

    assert consumption_module._same_source_transaction_row(
        fact({"kind": "table_row", "node_id": "table", "row": 7}),
        fact({"kind": "table_cell", "node_id": "table", "row": 7, "column": 4}),
    )
    assert not consumption_module._same_source_transaction_row(
        fact({"kind": "node", "node_id": "atomic-source-line"}),
        fact({"kind": "node", "node_id": "atomic-source-line"}),
    )
    assert not consumption_module._same_source_transaction_row(
        fact({"kind": "table_cell", "node_id": "table", "row": 6, "column": 4}),
        fact({"kind": "table_cell", "node_id": "table", "row": 7, "column": 4}),
    )
    assert not consumption_module._same_source_transaction_row(
        fact({"kind": "node", "node_id": "table"}),
        fact({"kind": "table_row", "node_id": "table", "row": 7}),
    )


def test_missing_acquisition_fact_and_quantity_fail_closed(tmp_path: Path) -> None:
    missing_store, missing_context = _case(
        tmp_path / "missing-fact",
        include_purchases=False,
    )
    with pytest.raises(Gate5DeterministicSourceFactConsumptionError) as missing:
        _consumer(missing_store).run(
            methodology_ref=_source_methodology_ref(),
            context=missing_context,
        )
    assert missing.value.code == "gate5_source_fact_acquisition_missing"

    quantity_store, quantity_context = _case(
        tmp_path / "missing-quantity",
        second_purchase_quantity=None,
    )
    with pytest.raises(Gate5DeterministicSourceFactConsumptionError) as quantity:
        _consumer(quantity_store).run(
            methodology_ref=_source_methodology_ref(),
            context=quantity_context,
        )
    assert quantity.value.code == "gate5_source_fact_required_role_missing"
    assert quantity.value.field.endswith(":quantity")


def test_source_currency_symbol_is_preserved_then_rejected_without_mapping(
    tmp_path: Path,
) -> None:
    store, context = _case(
        tmp_path,
        source_currency="$",
        include_direct_charge=False,
        include_commission_detail=False,
        include_commission_total=False,
        include_withheld_detail=False,
        include_withheld_total=False,
    )
    facts = _gate4(store).list_facts(context=context)
    source_currency_values = {
        role["value"]
        for fact in facts
        for role in fact["roles"]
        if role["role"] == "currency" and role["status"] == "value"
    }
    assert source_currency_values == {"$"}

    with pytest.raises(Gate5DeterministicSourceFactConsumptionError) as caught:
        _consumer(store).run(
            methodology_ref=_source_methodology_ref(),
            context=context,
        )
    assert caught.value.code == "gate5_source_fact_currency_invalid"


def test_factory_route_is_closed_world_and_read_only() -> None:
    module_source = inspect.getsource(consumption_module)
    factory_source = inspect.getsource(
        Gate5DeterministicSourceFactConsumptionRuntimeFactory
    )
    runtime_source = inspect.getsource(Gate5DeterministicSourceFactConsumptionRuntime)
    imports = set()
    for node in ast.walk(ast.parse(module_source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert "Gate4FinancialCaseRuntimeFactory.create" in FACTORY_REQUIRED[0]
    assert "reconciliation" in FORBIDDEN[0]
    assert "Gate4FinancialCaseRuntimeFactory(" in factory_source
    assert "Gate5TrustedMethodologyAuthorityFactory.create()" in factory_source
    assert "self._financial_case.list_facts(context=context)" in runtime_source
    assert ".put(" not in runtime_source
    assert imports == {
        "__future__",
        "artifact_models",
        "copy",
        "datetime",
        "decimal",
        "gate4_financial_case_cache",
        "gate4_financial_case_materialization",
        "gate5_trusted_methodology",
        "re",
        "typing",
    }
    for forbidden in (
        "sqlite3",
        "requests",
        "httpx",
        "model_client",
        "chat_completion",
        "CanonicalReaderFactory",
        "Gate3Financial",
        "ArtifactStoreFactory",
    ):
        assert forbidden not in module_source


def _case(
    root: Path,
    *,
    second_purchase_date: str = "01.02.2025",
    second_purchase_quantity: str | None = "10",
    include_purchases: bool = True,
    include_direct_charge: bool = True,
    include_commission_detail: bool = True,
    include_commission_total: bool = True,
    include_withheld_detail: bool = True,
    include_withheld_total: bool = True,
    source_currency: str = "RUB",
    include_tax_adjustment: bool = False,
):
    root.mkdir(parents=True, exist_ok=True)
    store, context = gate4_fixtures._store_context(root)
    if include_purchases:
        _publish(
            store,
            context,
            document_id="purchase-a",
            source_rows=(
                f"Purchase|01.01.2025|ACME|10|100.00|{source_currency}",
            ),
            fact_specs=(
                (
                    "SECURITY_PURCHASE",
                    _security_roles(
                        "01.01.2025", "10", "100.00", source_currency
                    ),
                ),
            ),
            purchase_date="01.01.2025",
        )
        quantity_text = (
            "" if second_purchase_quantity is None else second_purchase_quantity
        )
        _publish(
            store,
            context,
            document_id="purchase-b",
            source_rows=(
                f"Purchase|{second_purchase_date}|ACME|{quantity_text}|200.00|{source_currency}",
            ),
            fact_specs=(
                (
                    "SECURITY_PURCHASE",
                    _security_roles(
                        second_purchase_date,
                        second_purchase_quantity,
                        "200.00",
                        source_currency,
                    ),
                ),
            ),
            purchase_date=second_purchase_date,
        )
    disposal_specs = [
        (
            "SECURITY_DISPOSAL",
            _security_roles("01.03.2025", "12", "360.00", source_currency),
        )
    ]
    if include_direct_charge:
        disposal_specs.append(
            (
                "TRANSACTION_CHARGE",
                (
                    ("date", "01.03.2025"),
                    ("amount", "5.00"),
                    ("currency", source_currency),
                    ("asset", "ACME"),
                ),
            )
        )
    _publish(
        store,
        context,
        document_id="disposal",
        source_rows=(
            f"Sale|01.03.2025|ACME|12|360.00|{source_currency}|Charge|5.00",
        ),
        fact_specs=tuple(disposal_specs),
        target_indexes=tuple(0 for _ in disposal_specs),
        same_table_row=True,
    )

    assertions = []
    rows = []
    if include_commission_detail:
        rows.extend(("Commission|10.00|RUB", "Commission|15.00|RUB"))
        assertions.extend(
            (
                (
                    "COMMISSION",
                    (
                        ("amount", "10.00"),
                        ("currency", "RUB"),
                        ("date", None),
                        ("asset", None),
                    ),
                ),
                (
                    "COMMISSION",
                    (
                        ("amount", "15.00"),
                        ("currency", "RUB"),
                        ("date", None),
                        ("asset", None),
                    ),
                ),
            )
        )
    if include_commission_total:
        rows.append("Commission total|40.00|RUB")
        assertions.append(
            (
                "COMMISSION_TOTAL",
                (
                    ("amount", "40.00"),
                    ("currency", "RUB"),
                    ("date", None),
                    ("asset", None),
                ),
            )
        )
    if include_withheld_detail:
        rows.append("Tax withheld|02.03.2025|4.00|RUB")
        assertions.append(
            (
                "TAX_WITHHELD",
                (
                    ("date", "02.03.2025"),
                    ("amount", "4.00"),
                    ("currency", "RUB"),
                    ("asset", None),
                ),
            )
        )
    if include_withheld_total:
        rows.append("Tax withheld total|7.00|RUB")
        assertions.append(
            (
                "TAX_WITHHELD_TOTAL",
                (
                    ("amount", "7.00"),
                    ("currency", "RUB"),
                    ("date", None),
                    ("asset", None),
                ),
            )
        )
    if assertions:
        _publish(
            store,
            context,
            document_id="assertions",
            source_rows=tuple(rows),
            fact_specs=tuple(assertions),
        )
    if include_tax_adjustment:
        document_id = "tax-adjustment"
        document_context = replace(
            context,
            normalization_run_id="g591-tax-adjustment-v1",
        )
        canonical = gate4_fixtures._activate_canonical(
            store=store,
            context=document_context,
            document_id=document_id,
            artifact_version=1,
            expected_previous_version_id=None,
            source_rows=("Tax adjustment|02.03.2025|3.00|RUB",),
        )
        gate4_fixtures._persist_sidecar(
            store=store,
            context=document_context,
            document_id=document_id,
            canonical_version_id=canonical.canonical_version_id,
            artifact_id="g591-sidecar-tax-adjustment",
            created_at="2026-08-17T12:00:00+00:00",
            fact_specs=(
                (
                    "TAX_ADJUSTMENT",
                    (
                        ("date", "02.03.2025"),
                        ("amount", "3.00"),
                        ("currency", "RUB"),
                        ("source_wording", "Tax adjustment"),
                        ("asset", None),
                    ),
                ),
            ),
            semantic_version="2.1.0",
            role_pack_semantic_version="3.1.0",
        )
    _gate4(store).rebuild_case(context=context)
    return store, context


def _publish(
    store,
    context,
    *,
    document_id: str,
    source_rows: tuple[str, ...],
    fact_specs: tuple,
    purchase_date: str | None = None,
    target_indexes: tuple[int, ...] | None = None,
    same_table_row: bool = False,
) -> None:
    document_context = replace(
        context,
        normalization_run_id=f"g540d-{document_id}-v1",
    )
    canonical = gate4_fixtures._activate_canonical(
        store=store,
        context=document_context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        source_rows=source_rows,
        table_rows=(tuple(source_rows[0].split("|")),) if same_table_row else None,
    )
    gate4_fixtures._persist_sidecar(
        store=store,
        context=document_context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id=f"g540d-sidecar-{document_id}",
        created_at="2026-08-13T00:00:00+00:00",
        purchase_date=purchase_date,
        fact_specs=fact_specs,
        semantic_version="2.0.0",
        target_indexes=target_indexes,
        target_rows=(tuple(1 for _ in fact_specs) if same_table_row else None),
    )


def _security_roles(
    date: str,
    quantity: str | None,
    amount: str,
    currency: str = "RUB",
    *,
    asset: str = "ACME",
) -> tuple:
    return (
        ("date", date),
        ("asset", asset),
        ("quantity", quantity),
        ("amount", amount),
        ("currency", currency),
        ("unit_price", None),
    )


def _gate4(store):
    return Gate4FinancialCaseRuntimeFactory(store=store, read_enabled=True).create()


def _consumer(store):
    return Gate5DeterministicSourceFactConsumptionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()


def _tax_model(store):
    return Gate5SecuritiesDisposalTaxModelRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _commission_coverage(assembled, *, detail_status: str, aggregate_status: str):
    assertions = assembled["assertions"]["commissions"]
    detail_ids = sorted(
        item["fact_id"]
        for item in assertions["detail"]
        if item["financial_type"] == "COMMISSION"
    )
    aggregate_ids = [item["fact_id"] for item in assertions["aggregate"]]
    return {
        "schema_version": GATE5_COMMISSION_EVIDENCE_COVERAGE_SCHEMA_VERSION,
        "required_scope_ref": "commission-scope-2025",
        "currency": "RUB",
        "eligible_detail_fact_ids": (
            detail_ids if detail_status == "PROVEN_COMPLETE" else []
        ),
        "detail_coverage_status": detail_status,
        "aggregate_fact_id": (
            aggregate_ids[0] if aggregate_status == "PROVEN_MATCHING" else None
        ),
        "aggregate_scope_status": aggregate_status,
        "source_structure_evidence_refs": (
            ["explicit-source-coverage"]
            if detail_status.startswith("PROVEN")
            or aggregate_status.startswith("PROVEN")
            else []
        ),
    }


def _source_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    }


def _tax_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION
        ),
    }


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()
