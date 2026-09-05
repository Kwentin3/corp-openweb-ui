from __future__ import annotations

import json
from pathlib import Path
import sys


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

import live_cleanup_gate3_legacy_routes as cleanup  # noqa: E402


def test_cleanup_allowlist_is_exact_and_preserves_ndfl_base() -> None:
    assert cleanup.LEGACY_FUNCTIONS_TO_DISABLE == {
        "broker_reports_gate1_normalizer_action": ("proof_only_global_gate1_stub"),
        "broker_reports_private_intake_action": "retired_custom_intake_action",
        "broker_reports_gate2_source_fact_pipe": ("legacy_user_selectable_gate2_pipe"),
        "broker_reports_gate2_domain_source_fact_pipe": (
            "legacy_user_selectable_gate2_domain_pipe"
        ),
    }
    assert "broker_reports_gate1_pipe" not in cleanup.LEGACY_FUNCTIONS_TO_DISABLE
    assert cleanup.NDFL_OPENWEBUI_BASE_PIPE_ID in cleanup.REQUIRED_ACTIVE_FUNCTIONS
    assert (
        "broker_reports_private_intake_action" not in cleanup.REQUIRED_ACTIVE_FUNCTIONS
    )


def test_function_state_evaluator_uses_id_type_and_flags_not_name() -> None:
    record = {
        "id": "broker_reports_gate2_source_fact_pipe",
        "name": "renamed display",
        "type": "pipe",
        "is_active": False,
        "is_global": False,
    }
    check = cleanup.evaluate_function_state(
        record,
        stable_id="broker_reports_gate2_source_fact_pipe",
        expected_type="pipe",
        expected_active=False,
        expected_global=False,
    )
    assert check["passed"] is True


def test_cleanup_uses_toggle_only_and_never_deletes_history() -> None:
    source = (SCRIPT_ROOT / "live_cleanup_gate3_legacy_routes.py").read_text(
        encoding="utf-8"
    )
    assert "/api/v1/functions/id/{stable_id}/toggle" in source
    assert "/delete" not in source
    assert "get_by_name" not in source
    assert "find_function_by_name" not in source
    assert '"deleted_records": 0' in source
    assert '"provider_calls": 0' in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source


def test_product_orchestrator_delegates_to_existing_owners_only() -> None:
    source = (
        SERVICE_ROOT / "broker_reports_gate1" / "gate3_ndfl_workflow.py"
    ).read_text(encoding="utf-8")
    for owner in (
        "CanonicalReaderFactory",
        "Gate3ChunkBatchLabelingFactory",
        "Gate3FinancialAnnotationsPersistenceFactory",
    ):
        assert owner in source
    chunk_source = (
        SERVICE_ROOT / "broker_reports_gate1" / "gate3_bounded_labeling.py"
    ).read_text(encoding="utf-8")
    assert "Gate3FinancialLabelDictionaryFactory" in chunk_source
    for bypass in (
        ".get_record(",
        ".get_record_unchecked(",
        ".put_record(",
        ".put_records_atomic(",
        "gate2_financial_semantic_pack",
    ):
        assert bypass not in source


def test_current_label_definitions_are_not_copied_into_python_or_prompts() -> None:
    dictionary = json.loads(
        (
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate3_financial_label_dictionary.v2.json"
        ).read_text(encoding="utf-8")
    )
    normative_phrases = {
        phrase
        for label in dictionary["labels"]
        for phrase in [
            label["meaning"],
            *label["apply_when"],
            *label["do_not_apply_when"],
        ]
    }
    inspected = [
        *sorted((SERVICE_ROOT / "broker_reports_gate1").glob("*.py")),
        *sorted((SERVICE_ROOT / "managed_assets" / "prompts").glob("*")),
    ]
    for path in inspected:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert not {phrase for phrase in normative_phrases if phrase in text}, path
