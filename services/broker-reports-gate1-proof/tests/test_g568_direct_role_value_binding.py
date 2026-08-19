"""G5.68 structural boundary, replay accounting and regression guards."""

from __future__ import annotations

import inspect
from pathlib import Path

from broker_reports_gate1.gate3_llm_metadata_adapter import (
    GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    _direct_structural_relation,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]


def test_direct_relation_owner_uses_only_atomic_canonical_structure() -> None:
    source = inspect.getsource(_direct_structural_relation).lower()

    assert GATE3_LLM_METADATA_INSTRUCTION_VERSION == "1.2.0"
    assert GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION == (
        "broker_reports_metadata_context_policy_v4"
    )
    assert "same_atomic_address" in source
    assert "same_table_row" in source
    assert "table_header_lineage" in source
    assert "page" not in source
    assert "account" not in source
    assert "client" not in source
    assert "broker" not in source


def test_offline_qualification_has_no_provider_route_or_semantic_rule() -> None:
    source = (
        SERVICE_ROOT / "scripts" / "qualify_g568_direct_role_value_binding.py"
    ).read_text(encoding="utf-8").lower()

    assert "build_metadata_context_package(" in source
    assert "_direct_structural_relation(" in source
    assert "provider_calls\": 0" in source
    assert "client code" not in source
    assert "account number" not in source
    assert "requests" not in source


def test_clean_replay_qualification_reads_frozen_outputs_without_calling_provider() -> None:
    source = (
        SERVICE_ROOT / "scripts" / "qualify_g568_clean_replay.py"
    ).read_text(encoding="utf-8").lower()

    assert "validate_metadata_proposal(" in source
    assert "provider_calls_during_qualification\": 0" in source
    assert "manual_output_repair\": false" in source
    assert "requests" not in source
    assert "completion" not in source


def test_financial_regression_uses_gate4_factory_rebuild_boundary() -> None:
    source = (
        SERVICE_ROOT / "scripts" / "verify_g568_financial_regression.py"
    ).read_text(encoding="utf-8")

    assert "Gate4FinancialCaseRuntimeFactory(" in source
    assert ".create()" in source
    assert "runtime.rebuild_case(context=context)" in source
    assert 'EXPECTED = {"holdout_a": 39, "holdout_b": 129}' in source
