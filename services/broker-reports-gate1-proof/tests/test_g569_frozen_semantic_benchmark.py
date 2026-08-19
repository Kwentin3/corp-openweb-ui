"""G5.69 benchmark-only freeze, factory route and terminal accounting guards."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import SimpleNamespace


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PREPARE = SERVICE_ROOT / "scripts" / "prepare_g569_frozen_semantic_benchmark.py"
LIVE = SERVICE_ROOT / "scripts" / "live_g569_frozen_semantic_benchmark.py"
QUALIFY = SERVICE_ROOT / "scripts" / "qualify_g569_semantic_repeatability.py"
FINANCIAL = SERVICE_ROOT / "scripts" / "verify_g569_financial_regression.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G569 = _load(LIVE, "g569_live")


def test_freeze_selects_two_cases_and_one_comparison_before_results() -> None:
    source = PREPARE.read_text(encoding="utf-8")

    assert '("case_f", "holdout_a", "KNOWN_CLIENT_CODE_ACCOUNT_FAILURE")' in source
    assert '("case_c", "pdf_002", "CLEAN_G568_CONTROL")' in source
    assert 'COMPARISON = ("anthropic_claude", "claude-opus-5")' in source
    assert '"selected_before_any_g569_semantic_result": True' in source
    assert '"semantic_provider_calls": 0' in source
    assert "Gate3LlmMetadataAdapterFactory" not in source


def test_live_benchmark_uses_factory_route_and_fixed_independent_schedule() -> None:
    source = LIVE.read_text(encoding="utf-8")

    assert "Gate3LlmMetadataAdapterFactory(" in source
    assert "Gate2StructuredModelClientFactory(" in source
    assert 'range(1, freeze["runs_per_case_per_model"] + 1)' in source
    assert "g569_exactly_one_submission_required" in source
    assert '"retries": 0' in source
    assert '"best_of_n": False' in source
    assert '"voting": False' in source
    assert '"result_selection": False' in source
    assert "temperature" not in inspect.getsource(G569.main).lower()


def test_safe_run_preserves_transport_vs_semantic_terminal() -> None:
    semantic = G569._safe_run(
        {
            "case_id": "case_f",
            "alias": "holdout_a",
            "run_ordinal": 1,
            "semantic_result": True,
            "transport_failure": False,
            "model_visible_request_sha256": "a" * 64,
            "validation_status": "rejected",
            "validation_error_code": "relation_invalid",
            "metrics": {"input_tokens": 1, "duration_ms": 2},
            "error": None,
        }
    )
    transport = G569._safe_run(
        {
            "case_id": "case_f",
            "alias": "holdout_a",
            "run_ordinal": 2,
            "semantic_result": False,
            "transport_failure": True,
            "model_visible_request_sha256": "a" * 64,
            "validation_status": "not_reached",
            "validation_error_code": None,
            "metrics": None,
            "error": {"type": "Timeout", "code": None, "failure_class": None},
        }
    )

    assert semantic["semantic_result"] is True
    assert semantic["transport_failure"] is False
    assert semantic["validation_status"] == "rejected"
    assert transport["semantic_result"] is False
    assert transport["transport_failure"] is True
    assert transport["error_type"] == "Timeout"


def test_private_run_rejects_request_fingerprint_drift() -> None:
    attempt = SimpleNamespace(
        model_visible_request={"messages": []},
        validation_status="validated",
        validation_error_code=None,
        final_provider_request={},
        raw_provider_response={},
        raw_model_output={},
        validated_output={},
        execution_metadata={},
        metrics={},
    )

    try:
        G569._private_run(
            case={"case_id": "case_f", "alias": "holdout_a"},
            run_ordinal=1,
            attempt=attempt,
            error=None,
            expected_request_sha256="0" * 64,
        )
    except SystemExit as exc:
        assert "g569_runtime_request_drift" in str(exc)
    else:
        raise AssertionError("request drift must terminate the benchmark")


def test_qualification_is_offline_and_preserves_all_result_classes() -> None:
    source = QUALIFY.read_text(encoding="utf-8")

    assert "validate_metadata_proposal(" in source
    assert '"provider_calls_during_qualification": 0' in source
    assert '"wrong_value_boundary"' in source
    assert '"structural_rejections"' in source
    assert '"invented_literals"' in source
    assert '"invalid_provenance"' in source
    assert '"duplicates"' in source
    assert "requests" not in source


def test_g569_financial_check_reuses_gate4_factory_boundary() -> None:
    source = FINANCIAL.read_text(encoding="utf-8")

    assert "Gate4FinancialCaseRuntimeFactory(" in source
    assert "runtime.rebuild_case(context=context)" in source
    assert "from verify_g568_financial_regression import" in source
    assert '"goal": "G5.69"' in source
