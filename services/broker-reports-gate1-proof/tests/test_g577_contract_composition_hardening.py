from __future__ import annotations

from pathlib import Path

from broker_reports_gate1.gate5_declaration_preparation import (
    Gate5DeclarationPreparationRuntimeFactory,
)

import test_broker_reports_gate5_declaration_preparation as preparation_fixtures
import test_broker_reports_gate5_deterministic_source_fact_consumption as source_fixtures


_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_filing_actions_and_action_order_do_not_suppress_calculation(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(
        tmp_path / "stage-aware-filing",
        include_purchases=False,
    )
    preparation_fixtures._publish_metadata(store, context)
    runtime = Gate5DeclarationPreparationRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    source_fixtures._publish(
        store,
        context,
        document_id="earlier-acquisition",
        source_rows=("Purchase|01.01.2025|ACME|12|120.00|RUB",),
        fact_specs=(
            (
                "SECURITY_PURCHASE",
                source_fixtures._security_roles(
                    "01.01.2025", "12", "120.00", "RUB"
                ),
            ),
        ),
        purchase_date="01.01.2025",
    )
    source_fixtures._gate4(store).rebuild_case(context=context)

    result = runtime.prepare(
        **preparation_fixtures._prepare_args(context, "SYNTHETIC_CONTROL", [])
    )
    actions = result["gap_closure"]["required_actions"]

    assert result["machine_readable_declaration_draft"]["calculation_count"] == 1
    assert actions[0]["closure_type"] == "USER_FACT"
    assert any(
        item.get("fact_key") == "signer_and_representation" for item in actions
    )
    assert any(item.get("fact_key") == "filing_instance_identity" for item in actions)
    assert result["target_release"]["status"] == (
        "AWAITING_SEALED_DECLARATION_SEMANTIC_INPUT"
    )


def test_navigation_authorities_freeze_stage_aware_composition() -> None:
    pipeline = (
        _REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md"
    ).read_text(encoding="utf-8")
    authorities = (
        _REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md"
    ).read_text(encoding="utf-8")
    preparation = (
        _REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_GATE5_DECLARATION_PREPARATION.v0.md"
    ).read_text(encoding="utf-8")

    for anchor in (
        "REQUIREMENT_NOT_GLOBAL_BLOCKER = FROZEN",
        "CLOSURE_ORDER_NOT_DEPENDENCY_ORDER = FROZEN",
        "BLOCKER_SCOPE_REQUIRED = NAMED_CONSUMER + EARLIEST_STAGE + MINIMAL_UNIT",
        "EVIDENCE_HORIZON_ACQUISITION_BASIS_GAP",
        "UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW",
        "NORMALIZATION_OWNER_REVIEW",
        "COLD_AGENT_ANTI_DRIFT_10_OF_10",
    ):
        assert anchor in pipeline
    assert pipeline.count("### Cold-agent composition exam") == 1
    assert "A downstream report or action ordering cannot promote" in pipeline
    source_role_row = next(
        line
        for line in pipeline.splitlines()
        if "source fact exists, required role missing" in line
    )
    decimal_row = next(
        line
        for line in pipeline.splitlines()
        if "source value exists, decimal normalization fails" in line
    )
    assert "Gate 3 -> Gate 4 source-fact production owners" in source_role_row
    assert "do not ask the user" in source_role_row
    assert "Gate4FinancialCaseMaterializerFactory.create" in decimal_row
    assert "never ask the user" in decimal_row
    evidence_horizon = pipeline.split("### Evidence horizon and calculation granularity", 1)[1]
    assert "not by itself a broken" in evidence_horizon
    assert "parser defect or source defect" in evidence_horizon
    assert "Pipeline Gates current architecture map" in authorities
    assert "dated report, receipt or research history" in authorities
    assert "not a computation dependency graph" in preparation
