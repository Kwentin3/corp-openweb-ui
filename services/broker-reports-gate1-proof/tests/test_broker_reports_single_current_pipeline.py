from __future__ import annotations

from pathlib import Path

import pytest

from broker_reports_gate1.contracts import SUPPORTED_CONTRACTS
from broker_reports_gate1.gate3_ndfl_workflow import NdflWorkflowError
from openwebui_actions.broker_reports_gate1_pipe import Pipe

import test_broker_reports_gate5_declaration_preparation as preparation_fixtures
import test_broker_reports_gate5_deterministic_source_fact_consumption as source_fixtures


def test_current_pipe_fails_closed_without_trusted_taxpayer_scope_binding(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(tmp_path / "current-pipeline")
    preparation_fixtures._publish_metadata(store, context)
    source_fixtures._gate4(store).clear_case_cache(context=context)

    with pytest.raises(NdflWorkflowError) as missing_binding:
        Pipe()._run_ndfl_current_pipeline(store=store, context=context)

    assert missing_binding.value.args == (
        "ndfl_trusted_taxpayer_scope_binding_required",
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
    assert "broker_reports_pdf_table_locator_response_v2" in SUPPORTED_CONTRACTS
    assert "broker_reports_pdf_table_intake_run_v1" in SUPPORTED_CONTRACTS
