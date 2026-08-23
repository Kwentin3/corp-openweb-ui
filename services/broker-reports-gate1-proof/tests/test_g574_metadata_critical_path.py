from __future__ import annotations

from pathlib import Path

from broker_reports_gate1.gate3_metadata_source_facts import (
    Gate3MetadataSourceFactRuntimeFactory,
)
from broker_reports_gate1.gate4_financial_case_cache import (
    FACTORY_REQUIRED as GATE4_FACTORY_REQUIRED,
    FORBIDDEN as GATE4_FORBIDDEN,
    Gate4FinancialCaseRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_preparation import (
    FACTORY_REQUIRED as PREPARATION_FACTORY_REQUIRED,
    Gate5DeclarationPreparationRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_USER_INTENT_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_evidence_intake import (
    FACTORY_REQUIRED as INTAKE_FACTORY_REQUIRED,
)
from broker_reports_gate1.gate5_human_gap_closure import (
    gate5_case_taxpayer_scope_ref,
)

import test_broker_reports_gate5_deterministic_source_fact_consumption as source_fixtures


_BASE_METADATA = {
    "broker": "Broker: Example Securities LLC",
    "party": "Client Name: Test Person",
    "account": "Account Number: A-123",
    "contract": "Генеральное соглашение: CONTRACT-7",
    "document_date": "Дата формирования отчета: 31.12.2025",
    "period": "Statement Period: 01.01.2025 - 31.12.2025",
}

_SCENARIOS = {
    "correct": {},
    "wrong_account": {"account": "Account Number: CLIENT-CODE-999"},
    "missing_account": {"account": None},
    "wrong_contract": {"contract": "Генеральное соглашение: WRONG-CONTRACT"},
    "wrong_broker": {"broker": "Broker: Wrong Broker LLC"},
    "wrong_period": {"period": "Statement Period: 01.01.2024 - 31.12.2024"},
    "missing_period": {"period": None},
    "multiple_periods": {
        "period": "Statement Period: 01.01.2024 - 31.12.2024",
        "additional_period": "Statement Period: 01.01.2025 - 31.12.2025",
    },
    "name_mismatch": {"party": "Client Name: Other Person"},
}


def test_low_criticality_metadata_cannot_drop_or_change_financial_results(
    tmp_path: Path,
) -> None:
    results = {
        scenario: _run_scenario(tmp_path / scenario, overrides)
        for scenario, overrides in _SCENARIOS.items()
    }
    baseline = results["correct"]

    for scenario, result in results.items():
        assert (
            result["financial_fingerprint"] == baseline["financial_fingerprint"]
        ), scenario
        assert (
            result["financial_facts_total"] == baseline["financial_facts_total"]
        ), scenario
        assert result["source_facts_total"] == baseline["source_facts_total"], scenario
        assert (
            result["calculation_count"] == baseline["calculation_count"] == 1
        ), scenario
        assert result["active_demands"] == baseline["active_demands"], scenario
        assert result["tax_period"] == baseline["tax_period"] == "2025", scenario
        assert result["preparation_status"] == baseline["preparation_status"], scenario
        assert result["identity_confirmation_required"] is True, scenario

    assert _values(results["correct"], "ACCOUNT_IDENTIFIER") == ["A-123"]
    assert _values(results["wrong_account"], "ACCOUNT_IDENTIFIER") == [
        "CLIENT-CODE-999"
    ]
    assert _values(results["missing_account"], "ACCOUNT_IDENTIFIER") == []
    assert _values(results["wrong_contract"], "ACCOUNT_CONTRACT_IDENTIFIER") == [
        "WRONG-CONTRACT"
    ]
    assert _values(results["wrong_broker"], "BROKER_LEGAL_NAME") == ["Wrong Broker LLC"]
    assert _period_values(results["wrong_period"]) == [("2024-01-01", "2024-12-31")]
    assert _period_values(results["missing_period"]) == []
    assert _period_values(results["multiple_periods"]) == [
        ("2024-01-01", "2024-12-31"),
        ("2025-01-01", "2025-12-31"),
    ]
    assert _values(results["name_mismatch"], "PARTY_NAME") == ["Other Person"]


def test_metadata_counterfactual_uses_canonical_factories_and_no_financial_authority() -> (
    None
):
    assert "Gate4FinancialCaseRuntimeFactory.create" in GATE4_FACTORY_REQUIRED
    assert "tax logic" in GATE4_FORBIDDEN
    assert "Gate3MetadataSourceFactRuntimeFactory.create" in INTAKE_FACTORY_REQUIRED[0]
    assert "Gate5EvidenceIntakeRuntimeFactory.create" in PREPARATION_FACTORY_REQUIRED[0]
    assert "metadata" not in Gate4FinancialCaseRuntimeFactory.__module__.split(".")[-1]


def _run_scenario(root: Path, overrides: dict[str, str | None]) -> dict:
    store, context = source_fixtures._case(root)
    metadata = {**_BASE_METADATA, **overrides}
    rows = [
        "Отчет брокера",
        *(value for value in metadata.values() if value is not None),
        "Commission|1.00|RUB",
    ]
    source_fixtures._publish(
        store,
        context,
        document_id="metadata",
        source_rows=tuple(rows),
        fact_specs=(
            (
                "COMMISSION",
                (
                    ("amount", "1.00"),
                    ("currency", "RUB"),
                    ("date", None),
                    ("asset", None),
                ),
            ),
        ),
        target_indexes=(len(rows) - 1,),
    )
    Gate4FinancialCaseRuntimeFactory(
        store=store, read_enabled=True
    ).create().rebuild_case(context=context)
    metadata_collection = (
        Gate3MetadataSourceFactRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .collect(context=context)
    )
    prepared = (
        Gate5DeclarationPreparationRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .prepare(
            source_fact_methodology_ref=source_fixtures._source_methodology_ref(),
            context=context,
            evidence_mode="SYNTHETIC_CONTROL",
            user_intent={
                "schema_version": GATE5_USER_INTENT_SCHEMA_VERSION,
                "form": "3-NDFL",
                "tax_period": "2025",
                "task": "prepare_tax_declaration",
                "domains": ["broker_securities_income"],
            },
            taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(context),
            user_case_facts=[],
        )
    )
    case = prepared["case_assembly"]
    source = case["source_fact_assembly"]
    draft = prepared["machine_readable_declaration_draft"]
    identity_action = next(
        item
        for item in prepared["gap_closure"]["required_actions"]
        if item.get("fact_key") == "taxpayer_identity_confirmed"
    )
    return {
        "metadata_facts": metadata_collection["metadata_facts"],
        "financial_facts_total": sum(
            prepared["intake"]["financial_fact_counts"].values()
        ),
        "source_facts_total": case["metrics"]["source_facts"],
        "calculation_count": draft["calculation_count"],
        "active_demands": sorted(
            item["demand"] for item in prepared["scope_activation"]["active_demands"]
        ),
        "tax_period": prepared["scope_activation"]["user_intent"]["tax_period"],
        "preparation_status": prepared["status"],
        "identity_confirmation_required": bool(identity_action["evidence_refs"]),
        "financial_fingerprint": {
            "intake_type_counts": prepared["intake"]["financial_fact_counts"],
            "source_type_counts": source["financial_type_counts"],
            "source_document_ids": source["source_document_ids"],
            "security_fact_counts": source["security_fact_counts"],
            "calculation_values": [
                {
                    "asset": item["asset"],
                    "gross_income": item["gross_income"]["value"],
                    "recognized_acquisition_cost": item["recognized_acquisition_cost"][
                        "value"
                    ],
                    "fifo_consumed_quantities": [
                        row["consumed_quantity"]
                        for row in item["recognized_acquisition_cost"]["fifo_inputs"]
                    ],
                    "fifo_recognized_costs": [
                        row["recognized_cost"]
                        for row in item["recognized_acquisition_cost"]["fifo_inputs"]
                    ],
                    "direct_transaction_expense": item["direct_transaction_expense"][
                        "value"
                    ],
                    "tax_model_input_status": item["tax_model_input_status"],
                }
                for item in draft["deterministic_calculations"]
            ],
        },
    }


def _values(result: dict, fact_type: str) -> list[str]:
    return sorted(
        item["value"]["normalized"]
        for item in result["metadata_facts"]
        if item["fact_type"] == fact_type
    )


def _period_values(result: dict) -> list[tuple[str, str]]:
    return sorted(
        (item["value"]["start"], item["value"]["end"])
        for item in result["metadata_facts"]
        if item["fact_type"] == "STATEMENT_PERIOD"
    )
