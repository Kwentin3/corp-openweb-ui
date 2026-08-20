from __future__ import annotations

from pathlib import Path

from broker_reports_gate1.contracts import SUPPORTED_CONTRACTS
from openwebui_actions.broker_reports_gate1_pipe import Pipe

import test_broker_reports_gate5_declaration_preparation as preparation_fixtures
import test_broker_reports_gate5_deterministic_source_fact_consumption as source_fixtures


def test_current_pipe_continues_from_persisted_gate4_to_natural_gate5_terminal(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(tmp_path / "current-pipeline")
    preparation_fixtures._publish_metadata(store, context)

    result = Pipe()._run_ndfl_current_pipeline(store=store, context=context)

    assert result["schema_version"] == "broker_reports_current_pipeline_result_v1"
    assert result["status"] == "PREPARATION_INCOMPLETE"
    assert result["terminal"] == "REAL_EVIDENCE_GAPS_REMAIN"
    assert result["declaration_ready"] is False
    assert result["xml_created"] is False
    assert result["pdf_created"] is False
    assert result["legacy_fallback_used"] is False
    preparation = result["preparation"]
    assert preparation["replay"]["entrypoint"] == (
        "Gate5DeclarationPreparationRuntimeFactory.create"
    )
    assert preparation["metrics"]["source_facts_lost"] == 0
    assert preparation["metrics"]["invented_source_facts"] == 0
    assert preparation["metrics"]["calculated_values_without_methodology"] == 0
    assert not any(
        action["closure_type"] == "ADDITIONAL_DOCUMENT"
        and "obl_foreign_source_taxable_income_and_foreign_tax"
        in action["demand_refs"]
        for action in preparation["gap_closure"]["user_facing_required_actions"]
    )


def test_product_pipe_has_no_retired_runtime_valves_or_synthetic_xml_owner() -> None:
    valves = Pipe().valves
    for name in (
        "pdf_dual_vlm_enabled",
        "pdf_semantic_visual_table_downstream_enabled",
        "pdf_hybrid_shadow_enabled",
        "pdf_structural_repair_shadow_enabled",
        "pdf_vlm_guided_intake_shadow_enabled",
        "pdf_semantic_header_shadow_enabled",
        "ndfl_full_product_enabled",
        "ndfl_full_product_synthetic_only",
    ):
        assert not hasattr(valves, name)


def test_current_gate1_contract_does_not_advertise_retired_table_routes() -> None:
    retired_fragments = (
        "hybrid",
        "dual_vlm",
        "semantic_header",
        "structural_repair",
        "visual_table_review",
        "vlm_guided",
    )

    assert not any(
        fragment in contract
        for contract in SUPPORTED_CONTRACTS
        for fragment in retired_fragments
    )
    assert "broker_reports_pdf_table_locator_response_v1" in SUPPORTED_CONTRACTS
    assert "broker_reports_pdf_table_intake_run_v1" in SUPPORTED_CONTRACTS
