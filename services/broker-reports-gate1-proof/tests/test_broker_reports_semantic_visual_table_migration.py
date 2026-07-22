from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.gate2_table_packages import (
    Gate2TablePackageFactory,
    validate_gate2_table_package,
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


def test_accepted_numeric_semantic_table_reaches_gate2_without_review() -> None:
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
    package = Gate2TablePackageFactory().create().build(
        projection=result.gate2_projections[0], case_id="semantic-migration"
    )
    assert validate_gate2_table_package(
        package, result.gate2_projections[0]
    )["passed"] is True
    assert package["upstream_source_representation"][
        "source_representation_kind"
    ] == "semantic_visual_logical_table"


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


def test_gate1_action_routes_decisions_through_migration_factory() -> None:
    runtime = _runtime_result(
        [["Item", "Amount"], ["Cash", "1,000"], ["Total", "1,000"]]
    )
    dual_vlm = {
        "private_decisions": runtime.private_decisions,
        "private_provider_evidence": runtime.private_provider_evidence,
    }
    pipe = Pipe()

    disabled = pipe._maybe_migrate_pdf_semantic_tables(dual_vlm=dual_vlm)
    assert disabled["safe_summary"]["status"] == "disabled"
    assert disabled["private_envelopes"] == []
    assert disabled["gate2_projections"] == []

    pipe.valves.pdf_semantic_visual_table_downstream_enabled = True
    enabled = pipe._maybe_migrate_pdf_semantic_tables(dual_vlm=dual_vlm)
    assert enabled["safe_summary"]["accepted_for_gate2_total"] == 1
    assert len(enabled["private_envelopes"]) == 1
    assert len(enabled["gate2_projections"]) == 1


def _migrate(runtime):
    return SemanticVisualTableMigrationFactory(
        SemanticVisualTableMigrationConfig(enabled=True)
    ).create().migrate(
        decisions=runtime.private_decisions,
        provider_evidence=runtime.private_provider_evidence,
    )
