from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.gate2_table_packages import (
    Gate2TablePackageFactory,
)
from broker_reports_gate1.semantic_visual_table_migration import (
    GOAL5_QUALIFICATION_GATE_HASH,
    SemanticVisualTableMigrationConfig,
    SemanticVisualTableMigrationError,
    SemanticVisualTableMigrationFactory,
)
from tests.test_broker_reports_semantic_visual_table_materialization import (
    _runtime_result,
)
from openwebui_actions.broker_reports_gate1_pipe import Pipe


def test_historical_numeric_semantic_table_cannot_enter_current_gate2() -> None:
    runtime = _runtime_result(
        [["Item", "Amount"], ["Cash", "$ 1,000"], ["Total", "1,000"]]
    )
    result = _migrate(runtime)

    assert result.safe_summary["accepted_for_gate2_total"] == 1
    assert result.safe_summary[
        "mandatory_human_review_for_accepted_profile"
    ] is False
    assert result.safe_summary["qualification_gate_hash"] == (
        GOAL5_QUALIFICATION_GATE_HASH
    )
    assert len(result.private_envelopes) == 1
    assert len(result.gate2_projections) == 1
    with pytest.raises(
        ValueError,
        match="gate2_pdf_canonical_boundary_unsupported",
    ):
        Gate2TablePackageFactory().create().build(
            projection=result.gate2_projections[0], case_id="semantic-migration"
        )


def test_financial_profile_accepts_one_wide_source_row_but_still_requires_amount() -> None:
    accepted = _runtime_result(
        [["Trade", "2022-06-06", "Asset", "7", "5559.50", "RUB"]]
    )
    accepted_result = _migrate(accepted)
    assert accepted_result.safe_summary["accepted_for_gate2_total"] == 1
    assert accepted_result.gate2_projections[0]["row_count"] == 1
    assert accepted_result.gate2_projections[0]["column_count"] == 6

    rejected = _runtime_result(
        [["Trade", "Date", "Asset", "Quantity", "Currency"]]
    )
    rejected_result = _migrate(rejected)
    assert rejected_result.safe_summary["accepted_for_gate2_total"] == 0
    assert rejected_result.safe_summary["dispositions"][0]["reason_codes"] == [
        "accepted_profile_visible_amount_missing"
    ]


def test_prose_and_visual_uncertainty_remain_fail_closed() -> None:
    runtime = _runtime_result(
        [
            ["Standard", "Summary"],
            [
                "Accounting update",
                "Long narrative guidance without a source-visible amount.",
            ],
        ]
    )
    runtime.private_decisions[0]["semantic_transcription"][
        "description"
    ] = "A long-form prose grid."
    runtime.private_provider_evidence[0]["parsed_semantic_response"][
        "description"
    ] = "A long-form prose grid."

    result = _migrate(runtime)

    assert result.safe_summary["accepted_for_gate2_total"] == 0
    assert result.safe_summary["review_required_or_unsupported_total"] == 1
    assert result.private_envelopes == []
    assert result.gate2_projections == []


def test_legacy_decision_is_retained_without_ambiguous_auto_upgrade() -> None:
    runtime = _runtime_result([["Item", "Amount"], ["Cash", "1,000"]])
    legacy = copy.deepcopy(runtime.private_decisions[0])
    legacy["schema_version"] = "broker_reports_pdf_dual_vlm_decision_v1"

    result = SemanticVisualTableMigrationFactory(
        SemanticVisualTableMigrationConfig(enabled=True)
    ).create().migrate(decisions=[legacy], provider_evidence=[])

    assert result.safe_summary["legacy_artifacts_auto_migrated_total"] == 0
    assert result.safe_summary["accepted_for_gate2_total"] == 0
    assert result.safe_summary["dispositions"][0]["disposition"] == (
        "legacy_retained_under_original_contract"
    )

    minimal_legacy = {"schema_version": "legacy_geometry_v0", "proposal": {}}
    minimal_result = SemanticVisualTableMigrationFactory(
        SemanticVisualTableMigrationConfig(enabled=True)
    ).create().migrate(decisions=[minimal_legacy], provider_evidence=[])
    assert minimal_result.safe_summary["accepted_for_gate2_total"] == 0
    assert minimal_result.safe_summary["legacy_artifacts_auto_migrated_total"] == 0


def test_duplicate_source_scope_and_qualification_drift_fail_closed() -> None:
    runtime = _runtime_result([["Item", "Amount"], ["Cash", "1,000"]])
    duplicate = copy.deepcopy(runtime.private_decisions[0])
    duplicate["decision_id"] = "different_decision_id"
    with pytest.raises(
        SemanticVisualTableMigrationError,
        match="semantic_visual_table_migration_duplicate_source_scope",
    ):
        SemanticVisualTableMigrationFactory(
            SemanticVisualTableMigrationConfig(enabled=True)
        ).create().migrate(
            decisions=[runtime.private_decisions[0], duplicate],
            provider_evidence=runtime.private_provider_evidence,
        )

    with pytest.raises(
        SemanticVisualTableMigrationError,
        match="semantic_visual_table_migration_config_invalid",
    ):
        SemanticVisualTableMigrationFactory(
            SemanticVisualTableMigrationConfig(
                enabled=True, qualification_gate_hash="0" * 64
            )
        ).create()

    with pytest.raises(
        SemanticVisualTableMigrationError,
        match="semantic_visual_table_migration_materialization_failed",
    ):
        SemanticVisualTableMigrationFactory(
            SemanticVisualTableMigrationConfig(enabled=True)
        ).create().migrate(
            decisions=runtime.private_decisions,
            provider_evidence=[],
        )


def test_disabled_boundary_changes_no_source_family() -> None:
    result = SemanticVisualTableMigrationFactory().create().migrate(
        decisions=[], provider_evidence=[]
    )

    assert result.safe_summary["status"] == "disabled"
    assert result.safe_summary["other_source_families_changed"] is False
    assert result.private_envelopes == []
    assert result.gate2_projections == []


def test_gate1_action_has_no_semantic_migration_runtime_route() -> None:
    pipe = Pipe()

    assert not hasattr(pipe, "_maybe_migrate_pdf_semantic_tables")
    assert not hasattr(
        pipe.valves,
        "pdf_semantic_visual_table_downstream_enabled",
    )


def _migrate(runtime):
    return SemanticVisualTableMigrationFactory(
        SemanticVisualTableMigrationConfig(enabled=True)
    ).create().migrate(
        decisions=runtime.private_decisions,
        provider_evidence=runtime.private_provider_evidence,
    )
