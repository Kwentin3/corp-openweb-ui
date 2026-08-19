from __future__ import annotations

from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = SERVICE_ROOT / "broker_reports_gate1"
CONTRACTS = SERVICE_ROOT.parents[1] / "docs" / "stage2" / "contracts"


def test_gate5_does_not_promote_structural_proximity_to_financial_relation() -> None:
    tax_model = (PACKAGE / "gate5_securities_disposal_tax_model.py").read_text(
        encoding="utf-8"
    )
    end_to_end = (PACKAGE / "gate5_end_to_end_full_target_xml.py").read_text(
        encoding="utf-8"
    )

    assert not (PACKAGE / "gate5_related_securities_events.py").exists()
    assert "run_operation_from_related_events" not in tax_model
    assert "related_financial_case" not in tax_model
    assert "run_operation_from_related_events" not in end_to_end


def test_gate4_current_fact_contract_carries_semantic_authority_identity() -> None:
    materializer = (
        PACKAGE / "gate4_financial_case_materialization.py"
    ).read_text(encoding="utf-8")
    schema = (
        SERVICE_ROOT.parents[1]
        / "docs"
        / "stage2"
        / "contracts"
        / "BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.schema.json"
    )

    assert schema.exists()
    assert '"semantic_kind": "normalized_source_fact"' in materializer
    assert '"semantic_binding"' in materializer
    assert 'payload.get("dictionary_identity")' in materializer
    assert 'payload.get("role_pack_identity")' in materializer


def test_g540d_contract_does_not_turn_partial_commission_into_relation_requirement() -> None:
    source_boundary = (
        CONTRACTS / "BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md"
    ).read_text(encoding="utf-8")
    consumer = (
        CONTRACTS
        / "BROKER_REPORTS_GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION.v0.md"
    ).read_text(encoding="utf-8")

    assert "nor establishes that an\neconomic relation is required" in (
        source_boundary
    )
    assert "Partial acquisition commission and currency conversion are\n`METHODOLOGY_UNRESOLVED`" in consumer
    assert "No purchase-to-sale event, relation" in consumer
