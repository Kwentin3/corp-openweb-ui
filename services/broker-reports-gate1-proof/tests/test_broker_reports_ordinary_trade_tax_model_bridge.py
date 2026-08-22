from __future__ import annotations

import copy
import inspect
from pathlib import Path

import pytest

from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.canonical_store import CanonicalReader
from broker_reports_gate1.gate4_financial_case_cache import (
    Gate4FinancialCaseRuntimeFactory,
)
from broker_reports_gate1.gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_projection import (
    Gate5DeclarationProjectionRuntime,
)
from broker_reports_gate1.gate5_tax_period_category_aggregation import (
    GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
    GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_trusted_methodology import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthorityFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.ordinary_trade_tax_model_bridge import (
    ACTIVE_FACT_V2_TO_CATEGORY_TAX_MODEL_PROVEN,
    BOUNDED_TAX_MODEL_BRIDGE_BLOCKERS_PROVEN,
    FACTORY_REQUIRED,
    FORBIDDEN,
    OrdinaryTradeTaxModelBridgeRuntimeFactory,
)
from broker_reports_gate1 import ordinary_trade_tax_model_bridge as bridge_module

import test_broker_reports_gate5_securities_disposal_tax_model as tax_fixtures
import test_broker_reports_ordinary_trade_production_candidate as ordinary_fixtures


def test_current_fact_v2_reaches_operation_and_category_models_deterministically(
    tmp_path: Path,
) -> None:
    store, context, facts = _case(tmp_path / "positive")
    disposal_fact_id = _fact_id(facts, "SECURITY_DISPOSAL")
    purchase_fact_id = _fact_id(facts, "SECURITY_PURCHASE")
    purchase_fact = next(item for item in facts if item["fact_id"] == purchase_fact_id)
    disposal_fact = next(item for item in facts if item["fact_id"] == disposal_fact_id)
    charge_facts = [
        item for item in facts if item["financial_type"] == "TRANSACTION_CHARGE"
    ]
    assert (
        _role_value(purchase_fact, "quantity"),
        _role_value(purchase_fact, "amount"),
    ) == (
        "10",
        "100.00",
    )
    assert (
        _role_value(disposal_fact, "quantity"),
        _role_value(disposal_fact, "amount"),
    ) == (
        "4",
        "60.00",
    )
    assert sorted(_role_value(item, "amount") for item in charge_facts) == [
        "0.25",
        "0.50",
        "1.00",
        "2.00",
    ]
    resolved_inputs = _resolved_inputs()
    del resolved_inputs["expense_evidence"]["transaction_expense"]["documented"]
    runtime = _runtime(store)

    incomplete = _run(
        runtime,
        context=context,
        disposal_fact_id=disposal_fact_id,
        resolved_inputs=resolved_inputs,
        completeness_evidence=None,
    )
    binding = incomplete["category_result"]["scope_binding"]
    completeness = _completeness(binding["scope_binding_sha256"])
    first = _run(
        runtime,
        context=context,
        disposal_fact_id=disposal_fact_id,
        resolved_inputs=resolved_inputs,
        completeness_evidence=completeness,
    )
    second = _run(
        runtime,
        context=context,
        disposal_fact_id=disposal_fact_id,
        resolved_inputs=resolved_inputs,
        completeness_evidence=completeness,
    )

    assert incomplete["status"] == "blocked"
    assert incomplete["terminal"] == BOUNDED_TAX_MODEL_BRIDGE_BLOCKERS_PROVEN
    assert incomplete["blockers"] == [
        {
            "schema_version": "broker_reports_tax_model_bridge_blocker_v0",
            "reason_code": "gate5_tax_period_completeness_evidence_absent",
            "required_input": "tax_period_scope_completeness",
            "gap_owner_classification": "USER_CASE_FACT_MISSING",
            "owner": "Gate5TaxPeriodCategoryAggregationRuntime",
            "blocking_scope": "taxpayer_category_period_scope",
        }
    ]
    assert first == second
    assert first["status"] == "proven"
    assert first["terminal"] == ACTIVE_FACT_V2_TO_CATEGORY_TAX_MODEL_PROVEN
    assert first["blockers"] == []
    assert first["execution_constraints"] == {
        "active": False,
        "shadow_only": True,
        "provider_calls": 0,
        "gate3_execution": False,
        "historical_sql_gate4_reads": False,
        "canonical_reads_downstream": False,
        "source_observation_reads_downstream": False,
        "declaration_projection": False,
        "invented_event_relations": 0,
    }

    consumed = first["operation_result"]["source_fact_consumption"]
    assert consumed["case_binding"] == {
        "scope_kind": "case",
        "scope_id": context.case_id,
    }
    assert consumed["securities"][0]["disposal_fact_id"] == disposal_fact_id
    assert consumed["securities"][0]["recognized_acquisition_cost"]["fifo_inputs"] == [
        {
            "acquisition_fact_id": purchase_fact_id,
            "acquisition_date": "2025-01-10",
            "consumed_quantity": "4",
            "recognized_cost": _money("40.00"),
        }
    ]
    assert consumed["securities"][0]["gross_income"]["value"] == _money("60.00")
    assert consumed["securities"][0]["direct_transaction_expense"]["value"] == (
        _money("3.00")
    )
    assert len(consumed["assertions"]["commissions"]["detail"]) == 4

    operation = first["operation_result"]["tax_model"]
    sources = {
        source["fact_id"]
        for section in (
            operation["gross_income"]["sources"],
            operation["related_expenses"]["components"][0]["sources"],
            operation["related_expenses"]["components"][1]["sources"],
        )
        for source in section
    }
    assert {purchase_fact_id, disposal_fact_id}.issubset(sources)
    facts_by_id = {item["fact_id"]: item for item in facts}
    for section in (
        operation["gross_income"]["sources"],
        *(
            component["sources"]
            for component in operation["related_expenses"]["components"]
        ),
    ):
        for source in section:
            fact = facts_by_id[source["fact_id"]]
            assert source["gate3_binding"] == fact["gate3_binding"]
            assert source["annotation_target"] == fact["annotation_target"]
            assert source["gate3_binding"]["canonical_binding"]["canonical_version_id"]
    assert operation["gross_income"]["value"] == _money("60.00")
    assert operation["related_expenses"]["total"] == _money("43.00")
    assert operation["allowable_expenses"]["total"] == _money("40.00")
    assert first["demands"] == [
        {
            "schema_version": "broker_reports_tax_model_bridge_demand_v0",
            "required_input": "transaction_expense.documented",
            "gap_owner_classification": "REAL_SOURCE_EVIDENCE_MISSING",
            "owner": "Gate5SecuritiesDisposalTaxModelRuntime",
            "blocking_scope": "expense_allowability_only",
            "category_model_blocked": False,
        }
    ]

    category_result = first["category_result"]
    assert category_result["status"] == "complete"
    assert set(category_result) == {
        "schema_version",
        "status",
        "scope_binding",
        "known_values",
        "completeness",
        "category_tax_model",
    }
    member = category_result["category_tax_model"]["member_operations"][0]
    assert (
        member["operation_model_sha256"]
        == binding["members"][0]["operation_model_sha256"]
    )
    assert category_result["category_tax_model"]["category_gross_income"][
        "value"
    ] == _money("60.00")
    assert category_result["category_tax_model"]["related_expenses"]["value"] == (
        _money("43.00")
    )
    assert category_result["category_tax_model"]["allowable_expenses"]["value"] == (
        _money("40.00")
    )


@pytest.mark.parametrize(
    ("sides", "expected_code"),
    [
        (("Покупка",), "gate5_source_fact_disposal_missing"),
        (("Продажа",), "gate5_source_fact_acquisition_missing"),
    ],
)
def test_incomplete_acquisition_or_disposal_stops_at_source_owner(
    tmp_path: Path,
    sides: tuple[str, ...],
    expected_code: str,
) -> None:
    rows = (_HEADERS, *(_row(side=side) for side in sides))
    store, context, facts = _case(tmp_path / expected_code, rows=rows)
    disposal_ids = [
        item["fact_id"]
        for item in facts
        if item["financial_type"] == "SECURITY_DISPOSAL"
    ]
    result = _run(
        _runtime(store),
        context=context,
        disposal_fact_id=disposal_ids[0] if disposal_ids else "g4fact_missing",
        resolved_inputs=_resolved_inputs(),
        completeness_evidence=None,
    )

    assert result["terminal"] == BOUNDED_TAX_MODEL_BRIDGE_BLOCKERS_PROVEN
    assert result["operation_result"] is None
    assert result["category_result"] is None
    assert result["blockers"][0]["reason_code"] == expected_code
    assert result["blockers"][0]["gap_owner_classification"] == (
        "REAL_SOURCE_EVIDENCE_MISSING"
    )


def test_missing_external_applicability_and_stale_scope_are_typed(
    tmp_path: Path,
) -> None:
    store, context, facts = _case(tmp_path / "negative-inputs")
    disposal_fact_id = _fact_id(facts, "SECURITY_DISPOSAL")
    missing_market = _resolved_inputs()
    del missing_market["operation_properties"]["organized_market_status"]

    missing = _run(
        _runtime(store),
        context=context,
        disposal_fact_id=disposal_fact_id,
        resolved_inputs=missing_market,
        completeness_evidence=None,
    )
    stale = _run(
        _runtime(store),
        context=context,
        disposal_fact_id=disposal_fact_id,
        resolved_inputs=_resolved_inputs(),
        completeness_evidence=_completeness("0" * 64),
    )

    assert missing["blockers"][0] == {
        "schema_version": "broker_reports_tax_model_bridge_blocker_v0",
        "reason_code": "gate5_tax_model_classification_prerequisite_missing",
        "required_input": "organized_market_status",
        "gap_owner_classification": "EXTERNAL_AUTHORITATIVE_FACT_MISSING",
        "owner": "Gate5SecuritiesDisposalTaxModelRuntime",
        "blocking_scope": "single_disposal_operation_tax_model",
    }
    assert stale["blockers"][0]["reason_code"] == (
        "gate5_tax_period_completeness_binding_mismatch"
    )
    assert stale["blockers"][0]["gap_owner_classification"] == (
        "USER_CASE_FACT_MISSING"
    )
    assert stale["operation_result"]["tax_model"]["status"] == "complete"
    assert stale["category_result"] is None


@pytest.mark.parametrize(
    ("section", "field", "owner_classification"),
    [
        ("operation_properties", "operation_kind", "REAL_SOURCE_EVIDENCE_MISSING"),
        (
            "operation_properties",
            "organized_market_status",
            "EXTERNAL_AUTHORITATIVE_FACT_MISSING",
        ),
        ("operation_properties", "iis_status", "USER_CASE_FACT_MISSING"),
        ("tax_context", "tax_period", "USER_CASE_FACT_MISSING"),
        ("tax_context", "residency", "USER_CASE_FACT_MISSING"),
        ("tax_context", "exemption_applicability", "USER_CASE_FACT_MISSING"),
        ("tax_context", "loss_treatment", "METHODOLOGY_RULE_MISSING"),
    ],
)
def test_each_required_non_source_input_stops_at_its_primary_owner(
    tmp_path: Path,
    section: str,
    field: str,
    owner_classification: str,
) -> None:
    store, context, facts = _case(tmp_path / field)
    resolved_inputs = _resolved_inputs()
    del resolved_inputs[section][field]

    result = _run(
        _runtime(store),
        context=context,
        disposal_fact_id=_fact_id(facts, "SECURITY_DISPOSAL"),
        resolved_inputs=resolved_inputs,
        completeness_evidence=None,
    )

    assert result["terminal"] == BOUNDED_TAX_MODEL_BRIDGE_BLOCKERS_PROVEN
    assert result["blockers"][0]["gap_owner_classification"] == (owner_classification)
    assert result["operation_result"] is None
    assert result["category_result"] is None


def test_misbound_disposal_fact_identity_stops_as_pipeline_defect(
    tmp_path: Path,
) -> None:
    store, context, _facts = _case(tmp_path / "misbound-fact")

    result = _run(
        _runtime(store),
        context=context,
        disposal_fact_id="g4fact_00000000000000000000000000000000",
        resolved_inputs=_resolved_inputs(),
        completeness_evidence=None,
    )

    assert result["blockers"][0]["reason_code"] == (
        "gate5_source_fact_disposal_selection_invalid"
    )
    assert result["blockers"][0]["gap_owner_classification"] == (
        "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"
    )
    assert result["operation_result"] is None
    assert result["category_result"] is None


def test_current_methodology_does_not_require_income_source_or_source_party() -> None:
    resolved = Gate5TrustedMethodologyAuthorityFactory.create().resolve(
        _operation_methodology_ref()
    )
    methodology = resolved["methodology"]
    required_values = methodology["behavior"]["applicability_rule"]["required_values"]
    requirement_keys = {item["value_key"] for item in methodology["requirements"]}

    assert "income_source" not in required_values
    assert "source_party" not in required_values
    assert "income_source" not in requirement_keys
    assert "source_party" not in requirement_keys


def test_bridge_factory_traps_historical_and_declaration_fallbacks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, facts = _case(tmp_path / "fallback-traps")
    disposal_fact_id = _fact_id(facts, "SECURITY_DISPOSAL")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden fallback executed")

    monkeypatch.setattr(Gate4FinancialCaseRuntimeFactory, "create", forbidden)
    monkeypatch.setattr(CanonicalReader, "read_active_envelope", forbidden)
    monkeypatch.setattr(Gate5DeclarationProjectionRuntime, "project", forbidden)

    result = _run(
        _runtime(store),
        context=context,
        disposal_fact_id=disposal_fact_id,
        resolved_inputs=_resolved_inputs(),
        completeness_evidence=None,
    )

    assert result["operation_result"]["status"] == "modeled"
    assert result["category_result"]["status"] == "incomplete_scope"
    assert "OrdinaryTradeTaxModelBridgeRuntimeFactory.create" in FACTORY_REQUIRED
    assert "historical SQL-backed Gate 4" in FORBIDDEN
    source = inspect.getsource(bridge_module)
    for forbidden_name in (
        "CanonicalReaderFactory",
        "Gate4FinancialCaseRuntimeFactory",
        "Gate3",
        "sqlite3",
        "requests",
        "httpx",
        "model_client",
        "chat_completion",
    ):
        assert forbidden_name not in source
    assert "def _operation_tax_model" not in source
    assert "def _category_tax_model" not in source


_HEADERS = tuple(
    item["header_literal"] for item in ordinary_fixtures._QUALIFIED_MAPPING["columns"]
)


def _row(*, side: str) -> tuple[str, ...]:
    purchase = side == "Покупка"
    values = {
        "trade_date": "10.01.2025 10:00:00" if purchase else "11.02.2025 10:00:00",
        "settlement_date": "13.01.2025" if purchase else "13.02.2025",
        "trade_time": "10:00:00",
        "asset_name": "ACME",
        "security_code": "RU0000000000",
        "currency": "RUB",
        "side": side,
        "quantity": "10" if purchase else "4",
        "unit_price": "10.00" if purchase else "15.00",
        "gross_amount": "100.00" if purchase else "60.00",
        "accrued_interest": "0",
        "broker_commission": "0.50" if purchase else "1.00",
        "exchange_commission": "0.25" if purchase else "2.00",
        "trade_id": "trade-purchase" if purchase else "trade-disposal",
        "comment": "",
        "status": "Исполнена",
    }
    return tuple(values[role] for role in ordinary_fixtures._ROLES)


def _case(tmp_path: Path, *, rows: tuple | None = None):
    store, context, document_id, _mapping = ordinary_fixtures._case(
        tmp_path,
        rows=rows or (_HEADERS, _row(side="Покупка"), _row(side="Продажа")),
    )
    OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().compile_and_save(
        document_id=document_id,
        context=context,
    )
    facts = (
        Gate4OrdinaryTradeCandidateRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .list_facts(context=context)
    )
    return store, context, facts


def _runtime(store):
    return OrdinaryTradeTaxModelBridgeRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _run(
    runtime,
    *,
    context,
    disposal_fact_id: str,
    resolved_inputs: dict,
    completeness_evidence: dict | None,
):
    return runtime.run(
        operation_methodology_ref=_operation_methodology_ref(),
        source_fact_methodology_ref=_source_methodology_ref(),
        resolved_inputs=resolved_inputs,
        disposal_fact_id=disposal_fact_id,
        operation_ref="operation-control-2025",
        source_scope_ref=context.case_id,
        category_scope=_category_scope(),
        completeness_evidence=completeness_evidence,
        context=context,
    )


def _resolved_inputs() -> dict:
    result = copy.deepcopy(tax_fixtures._resolved_inputs())
    result["scope"] = {}
    return result


def _source_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    }


def _operation_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION
        ),
    }


def _category_scope() -> dict[str, str]:
    return {
        "schema_version": GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
        "scope_ref": "control-2025-organized-securities",
        "taxpayer_scope_ref": "synthetic-taxpayer-control",
        "tax_period": "2025",
        "operation_category": "organized_market_securities_outside_iis",
    }


def _completeness(scope_binding_sha256: str) -> dict:
    return {
        "schema_version": GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
        "status": "asserted_complete",
        "coverage_kind": "all_operations_in_taxpayer_category_period_scope",
        "scope_binding_sha256": scope_binding_sha256,
        "provenance": {
            "source_kind": "user_verified_fact",
            "source_ref": "synthetic-user-complete-control-2025",
            "input_channel": "tax_period_scope_completeness",
        },
    }


def _fact_id(facts: list[dict], financial_type: str) -> str:
    return next(
        item["fact_id"] for item in facts if item["financial_type"] == financial_type
    )


def _role_value(fact: dict, role: str) -> str:
    return next(item["value"] for item in fact["roles"] if item["role"] == role)


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}
