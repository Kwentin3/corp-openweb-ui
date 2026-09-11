from __future__ import annotations

import copy
from pathlib import Path

import pytest

from broker_reports_gate1.gate5_declaration_financial_investment_results import (
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_OPERATION_SET_INPUT_SCHEMA_VERSION,
    Gate5DeclarationFinancialInvestmentResultsError,
    Gate5DeclarationFinancialInvestmentResultsRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_right_side_assembly import (
    Gate5DeclarationRightSideAssemblyRuntimeFactory,
)
from broker_reports_gate1.gate5_end_to_end_full_target_xml import (
    Gate5EndToEndSuppliedCaseAuthorityFactory,
)

import test_broker_reports_gate5_declaration_financial_investment_results as financial_fixtures


def test_right_side_builds_existing_financial_root_from_proven_operation_set(
    tmp_path: Path,
) -> None:
    operation_set, scope = financial_fixtures._proven_operation_set(tmp_path)

    component = _runtime().financial_operation_set_component(
        inputs=_inputs(),
        scope_binding=scope,
        operation_set_result=operation_set,
    )

    assert component["schema_version"] == (
        GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION
    )
    assert component["input_snapshot"]["schema_version"] == (
        GATE5_FINANCIAL_INVESTMENT_RESULTS_OPERATION_SET_INPUT_SCHEMA_VERSION
    )
    assert component["input_snapshot"]["operation_set_result"] == operation_set
    assert component["category_tax_models"] == [
        operation_set["category_result"]["category_tax_model"]
    ]
    assert (
        Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().validate_component(
            component=component,
            scope_binding=scope,
        )
        == component
    )


@pytest.mark.parametrize("kind", ["demand", "invalid"])
def test_right_side_rejects_non_proven_operation_set_receipts(
    tmp_path: Path, kind: str
) -> None:
    operation_set, scope = financial_fixtures._proven_operation_set(tmp_path / kind)
    if kind == "demand":
        operation_set["demands"] = [{"required_input": "unresolved"}]
    else:
        operation_set = {}

    with pytest.raises(Gate5DeclarationFinancialInvestmentResultsError) as exc_info:
        _runtime().financial_operation_set_component(
            inputs=_inputs(),
            scope_binding=scope,
            operation_set_result=operation_set,
        )

    assert exc_info.value.code == "gate5_financial_investment_operation_set_invalid"


def test_right_side_legacy_financial_component_remains_v0_compatible(
    tmp_path: Path,
) -> None:
    operation_set, scope = financial_fixtures._proven_operation_set(tmp_path)
    category = operation_set["category_result"]["category_tax_model"]

    component = _runtime().financial_component(
        inputs=_inputs(),
        scope_binding=scope,
        category=category,
    )

    assert component["input_snapshot"]["schema_version"] == (
        GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION
    )
    assert component["input_snapshot"]["category_tax_models"] == [category]
    assert "operation_set_result" not in component["input_snapshot"]
    assert (
        Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().validate_component(
            component=component,
            scope_binding=scope,
        )
        == component
    )


def _runtime():
    return Gate5DeclarationRightSideAssemblyRuntimeFactory.create()


def _inputs() -> dict:
    source = Gate5EndToEndSuppliedCaseAuthorityFactory.create().load()
    return {"financial_investment": copy.deepcopy(source["financial_investment"])}
