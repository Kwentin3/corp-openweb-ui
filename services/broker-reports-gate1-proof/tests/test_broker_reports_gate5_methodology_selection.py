from __future__ import annotations

import ast
import copy
import inspect
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    GATE5_METHODOLOGY_REQUIREMENTS_SCHEMA_VERSION,
    GATE5_METHODOLOGY_SELECTION_RESULT_SCHEMA_VERSION,
    Gate4FinancialCaseRuntimeFactory,
    Gate5MethodologySelectionError,
    Gate5MethodologySelectionRuntime,
    Gate5MethodologySelectionRuntimeFactory,
)
from broker_reports_gate1 import gate5_methodology_selection as selection_module
from broker_reports_gate1.gate5_methodology_selection import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
from test_broker_reports_gate4_sql_materialization import (
    _publish_document,
    _store_context,
)


def test_external_methodology_changes_gate4_selection_without_scenario_code(
    tmp_path: Path,
) -> None:
    store, context = _representative_case(tmp_path)
    runtime = Gate5MethodologySelectionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    minimal = _methodology(
        _requirement(
            "disposal",
            "SECURITY_DISPOSAL",
            "date",
            "asset",
            "quantity",
            "amount",
            "currency",
        ),
        _requirement(
            "acquisition",
            "SECURITY_PURCHASE",
            "date",
            "asset",
            "quantity",
            "amount",
            "currency",
        ),
    )
    unchanged = copy.deepcopy(minimal)

    selected = runtime.select(methodology=minimal, context=context)

    assert minimal == unchanged
    assert selected["schema_version"] == (
        GATE5_METHODOLOGY_SELECTION_RESULT_SCHEMA_VERSION
    )
    assert selected["summary"] == {
        "requirements_total": 2,
        "found": 2,
        "partial": 0,
        "missing": 0,
    }
    assert [item["requirement_id"] for item in selected["requirements"]] == [
        "disposal",
        "acquisition",
    ]
    disposal = selected["requirements"][0]
    assert disposal["status"] == "found"
    assert disposal["matches"][0]["values"] == {
        "date": "2026-02-11",
        "asset": "ACME",
        "quantity": "4",
        "amount": "60.00",
        "currency": "USD",
    }
    assert disposal["matches"][0]["missing_roles"] == []

    with_charge = _methodology(
        *minimal["requirements"],
        _requirement(
            "direct_charge",
            "TRANSACTION_CHARGE",
            "date",
            "amount",
            "currency",
        ),
    )
    extended = runtime.select(methodology=with_charge, context=context)

    assert extended["requirements"][:2] == selected["requirements"]
    assert extended["summary"] == {
        "requirements_total": 3,
        "found": 2,
        "partial": 0,
        "missing": 1,
    }
    assert extended["requirements"][2] == {
        "requirement_id": "direct_charge",
        "financial_type": "TRANSACTION_CHARGE",
        "roles": ["date", "amount", "currency"],
        "status": "missing",
        "matches": [],
    }

    amount_only = _methodology(
        _requirement(
            "disposal_amount",
            "SECURITY_DISPOSAL",
            "amount",
            "currency",
        )
    )
    narrowed = runtime.select(methodology=amount_only, context=context)
    assert narrowed["requirements"][0]["matches"][0]["values"] == {
        "amount": "60.00",
        "currency": "USD",
    }


def test_closed_requirement_contract_fails_before_selection(
    tmp_path: Path,
) -> None:
    store, context = _store_context(tmp_path)
    runtime = Gate5MethodologySelectionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    duplicate = _methodology(
        _requirement("same", "SECURITY_DISPOSAL", "amount"),
        _requirement("same", "SECURITY_PURCHASE", "amount"),
    )

    with pytest.raises(Gate5MethodologySelectionError) as exc_info:
        runtime.select(methodology=duplicate, context=context)

    assert exc_info.value.code == "gate5_methodology_requirement_id_duplicate"


def test_factory_and_source_keep_gate4_boundary_and_tax_meaning_outside() -> None:
    factory_source = inspect.getsource(
        Gate5MethodologySelectionRuntimeFactory.create
    )
    runtime_source = inspect.getsource(Gate5MethodologySelectionRuntime)
    module_source = inspect.getsource(selection_module)
    imports = {
        node.module
        for node in ast.walk(ast.parse(module_source))
        if isinstance(node, ast.ImportFrom)
    }

    assert "Gate5MethodologySelectionRuntimeFactory.create" in FACTORY_REQUIRED
    assert "Gate4FinancialCaseRuntimeFactory.create" in FACTORY_REQUIRED
    assert "tax-scenario fact requirements" in FORBIDDEN
    assert "Gate4FinancialCaseRuntimeFactory(" in factory_source
    assert ".create()" in factory_source
    assert ".list_by_financial_type(" in runtime_source
    assert imports == {
        "__future__",
        "typing",
        "artifact_models",
        "gate4_financial_case_cache",
    }
    for forbidden_read in (
        "read_case(",
        "list_facts(",
        "get_fact(",
        "CanonicalReader",
        "ArtifactResolver",
        "sqlite3",
    ):
        assert forbidden_read not in runtime_source
    for tax_specific_type in (
        "SECURITY_PURCHASE",
        "SECURITY_DISPOSAL",
        "DIVIDEND_INCOME",
        "COUPON_INCOME",
        "INTEREST_INCOME",
        "SECURITIES_LENDING_INCOME",
        "ACCRUED_COUPON_COMPONENT",
        "TRANSACTION_CHARGE",
        "TAX_WITHHELD",
    ):
        assert tax_specific_type not in runtime_source


def _representative_case(tmp_path: Path):
    store, context = _store_context(tmp_path)
    _publish_document(
        store=store,
        context=context,
        document_id="gate5-selection-document",
        financial_types=("SECURITY_PURCHASE", "SECURITY_DISPOSAL"),
        sidecar_artifact_id="g3-v2-gate5-selection",
        created_at="2026-08-09T10:00:00+00:00",
    )
    Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    return store, context


def _methodology(*requirements: dict) -> dict:
    return {
        "schema_version": GATE5_METHODOLOGY_REQUIREMENTS_SCHEMA_VERSION,
        "requirements": list(requirements),
    }


def _requirement(
    requirement_id: str,
    financial_type: str,
    *roles: str,
) -> dict:
    return {
        "requirement_id": requirement_id,
        "financial_type": financial_type,
        "roles": list(roles),
    }
