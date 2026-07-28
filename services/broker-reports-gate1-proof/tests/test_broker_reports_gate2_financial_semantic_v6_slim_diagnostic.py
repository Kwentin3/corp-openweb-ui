from __future__ import annotations

import asyncio
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_execution_identity import (  # noqa: E402,E501
    V6_EXACT_MODEL_ID,
    V6_PROVIDER_PROFILE_ID,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_slim_diagnostic import (  # noqa: E402,E501
    V6_SLIM_DIAGNOSTIC_CONFIGURATIONS,
    Gate2FinancialSemanticV6SlimDiagnosticError,
    Gate2FinancialSemanticV6SlimDiagnosticFactory,
    financial_semantic_v6_slim_diagnostic_initial_receipt,
    run_financial_semantic_v6_slim_diagnostic,
)
from broker_reports_gate1.gate2_financial_semantic_v6_slim_diagnostic_report import (  # noqa: E402,E501
    Gate2FinancialSemanticV6SlimDiagnosticReportFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_stronger_candidate import (  # noqa: E402,E501
    V6_GOAL12_EXACT_MODEL_ID,
    V6_GOAL12_PROVIDER_PROFILE_ID,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE,
)


V6_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
)
V6_BASE_MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
SNAPSHOT_KEY = b"v6-slim-diagnostic-test-snapshot-key"
CONTINUATION_KEY = b"v6-slim-diagnostic-test-continuation-key"
REVISION = "a" * 40


@pytest.fixture(scope="module")
def fixture():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    return Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=json.loads(V6_MANIFEST_PATH.read_text(encoding="utf-8")),
        base_manifest=json.loads(
            V6_BASE_MANIFEST_PATH.read_text(encoding="utf-8")
        ),
    )


def _plan(fixture):
    return Gate2FinancialSemanticV6SlimDiagnosticFactory().create(
        fixture=fixture,
        repository_revision=REVISION,
    )


class _SlimFakeClient:
    def __init__(self, *, profile_id: str, outputs: dict[tuple[str, str], dict]):
        self.request_profile = (
            FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
        )
        self.profile_id = profile_id
        self.outputs = outputs
        self.local = 0
        self.submissions = 0
        self.responses = 0
        self.calls: list[tuple[str, str]] = []

    def qualification_lifecycle_snapshot(self):
        return {
            "local_invocations_total": self.local,
            "provider_submissions_total": self.submissions,
            "provider_responses_total": self.responses,
        }

    async def extract(
        self,
        *,
        prompt,
        package,
        model_id,
        response_format,
    ):
        del package, response_format
        self.local += 1
        self.submissions += 1
        self.responses += 1
        key = (model_id, prompt.packet_hash)
        self.calls.append(key)
        output = copy.deepcopy(self.outputs[key])
        metadata = Gate2ProviderExecutionMetadata(
            provider_id=self.profile_id.split("_")[0],
            provider_profile_id=self.profile_id,
            provider_profile_revision="test-v1",
            adapter_id="test_adapter",
            adapter_version="1.0",
            requested_model_id=model_id,
            structured_output_mode="test_strict_json_schema",
            response_format_type="json_schema",
            response_format_schema_mode="strict_json_schema",
            resolved_model_id=model_id,
            duration_ms=11,
            input_tokens=101,
            output_tokens=3,
            total_tokens=104,
            cached_input_tokens=0,
            reasoning_tokens=0,
            finish_reason="stop",
        )
        return Gate2StructuredModelResult(
            content=json.dumps(output, separators=(",", ":")),
            execution_metadata=metadata,
            economy_budget_receipt={
                "input_tokens": 101,
                "output_tokens": 3,
                "actual_cost_usd": "0.0007",
            },
        )


def _expected_outputs(plan):
    return {
        (cell.exact_model_id, cell.packet.slim_candidate.view_hash): (
            cell.expected_model_output
        )
        for cell in plan.cells
    }


def _clients(outputs):
    return {
        V6_PROVIDER_PROFILE_ID: _SlimFakeClient(
            profile_id=V6_PROVIDER_PROFILE_ID,
            outputs=outputs,
        ),
        V6_GOAL12_PROVIDER_PROFILE_ID: _SlimFakeClient(
            profile_id=V6_GOAL12_PROVIDER_PROFILE_ID,
            outputs=outputs,
        ),
    }


def test_plan_is_exact_six_cell_single_variable_diagnostic(fixture):
    plan = _plan(fixture)

    assert len(plan.cells) == 6
    assert tuple(cell.configuration_id for cell in plan.cells) == (
        "nano_slim",
        "nano_slim",
        "haiku_slim",
        "haiku_slim",
        "nano_slim_reversed",
        "nano_slim_reversed",
    )
    assert tuple(
        item["configuration_id"]
        for item in V6_SLIM_DIAGNOSTIC_CONFIGURATIONS
    ) == (
        "nano_slim",
        "haiku_slim",
        "nano_slim_reversed",
    )
    assert {cell.case_id for cell in plan.cells} == {
        "syn_successor_v2_unique_cash",
        "syn_successor_v2_no_registry_type",
    }
    assert {cell.exact_model_id for cell in plan.cells} == {
        V6_EXACT_MODEL_ID,
        V6_GOAL12_EXACT_MODEL_ID,
    }
    assert all(
        cell.linted_request.lint_receipt.status == "passed"
        and cell.linted_request.lint_receipt.provider_calls_total == 0
        for cell in plan.cells
    )
    normal_typed = plan.cells[0]
    reversed_typed = plan.cells[4]
    assert normal_typed.expected_model_output == {"choice": "B"}
    assert reversed_typed.expected_model_output == {"choice": "A"}
    assert normal_typed.expected_answer == reversed_typed.expected_answer
    assert normal_typed.packet.payload == reversed_typed.packet.payload
    assert normal_typed.packet.packet_hash == reversed_typed.packet.packet_hash
    assert normal_typed.choice_contract.choice_schema == (
        reversed_typed.choice_contract.choice_schema
    )
    assert (
        normal_typed.packet.slim_candidate.payload
        != reversed_typed.packet.slim_candidate.payload
    )
    assert plan.safe_summary()["provider_calls_total"] == 0


def test_runner_submits_exactly_six_and_preserves_transparent_evidence(fixture):
    plan = _plan(fixture)
    clients = _clients(_expected_outputs(plan))
    checkpoints: list[dict] = []

    receipt = asyncio.run(
        run_financial_semantic_v6_slim_diagnostic(
            plan=plan,
            model_clients=clients,
            safe_checkpoint=checkpoints.append,
        )
    )

    assert receipt["status"] == "passed"
    assert receipt["attempt_accounting"] == {
        "provider_submissions_planned_total": 6,
        "local_invocations_total": 6,
        "provider_submissions_total": 6,
        "provider_responses_total": 6,
        "fallback_total": 0,
        "repair_total": 0,
        "hidden_retry_total": 0,
    }
    assert len(clients[V6_PROVIDER_PROFILE_ID].calls) == 4
    assert len(clients[V6_GOAL12_PROVIDER_PROFILE_ID].calls) == 2
    assert receipt["acceptance"]["haiku_typed"] == "PASSED"
    assert receipt["acceptance"]["haiku_unclassified"] == "PASSED"
    assert receipt["acceptance"]["nano_diagnostic_status"] == (
        "NANO_SLIM_PASSED_ORDER_INVARIANT"
    )
    assert receipt["provider_metrics"] == {
        "actual_input_tokens_total": 606,
        "actual_output_tokens_total": 18,
        "actual_cost_usd": "0.0042",
        "latency_total_ms": 66,
        "latency_average_ms": 11,
        "latency_max_ms": 11,
        "calls_with_complete_metrics_total": 6,
    }
    assert len(checkpoints) == 8
    assert checkpoints[-1] == receipt
    assert all(
        item["technical_pipeline"]["status"] == "PASSED"
        and item["technical_pipeline"][
            "canonical_expansion_materialization"
        ]
        == "PASSED"
        and item["mechanical_comparison"]["all_fields_match"]
        for item in receipt["case_evidence"]
    )

    report = Gate2FinancialSemanticV6SlimDiagnosticReportFactory().render(
        safe_receipt_filename="goal4.receipt.safe.json",
        terminal_receipt=receipt,
    )
    assert report.count("#### 1. EXACT MODEL-VISIBLE INPUT") == 6
    assert (
        report.count("#### 2. EXACT ADAPTER-EXTRACTED MODEL OUTPUT")
        == 6
    )
    assert report.count("#### 3. NORMALIZED ANSWER") == 6
    assert report.count("#### 4. FROZEN EXPECTED ANSWER") == 6
    assert report.count("#### 5. ACTUAL PROVIDER METRICS") == 6
    assert "## Interpretation" in report
    assert report.index("## Primary evidence") < report.index(
        "## Interpretation"
    )
    assert "provider_response_id" not in report
    assert "reasoning_tokens" not in report
    assert "raw_provider_envelope" not in report


def test_nano_first_choice_bias_is_diagnostic_not_acceptance_failure(fixture):
    plan = _plan(fixture)
    outputs = _expected_outputs(plan)
    for cell in plan.cells:
        if cell.provider_profile_id == V6_PROVIDER_PROFILE_ID:
            outputs[
                (cell.exact_model_id, cell.packet.slim_candidate.view_hash)
            ] = {"choice": "A"}
    clients = _clients(outputs)

    receipt = asyncio.run(
        run_financial_semantic_v6_slim_diagnostic(
            plan=plan,
            model_clients=clients,
        )
    )

    assert receipt["status"] == "passed"
    assert receipt["acceptance"]["haiku_typed"] == "PASSED"
    assert receipt["acceptance"]["haiku_unclassified"] == "PASSED"
    assert receipt["acceptance"]["nano_diagnostic_status"] == (
        "NANO_FIRST_OPTION_BIAS"
    )
    assert receipt["acceptance"]["nano_slim_typed"] == (
        "FAILED_WITH_EXACT_EVIDENCE"
    )
    assert receipt["acceptance"]["full_benchmark"] == "NOT_RUN"
    assert receipt["model_qualification_performed"] is False
    assert receipt["production_admissions_total"] == 0


def test_haiku_semantic_miss_fails_goal4_acceptance_without_retry(fixture):
    plan = _plan(fixture)
    outputs = _expected_outputs(plan)
    haiku_typed = next(
        cell
        for cell in plan.cells
        if cell.configuration_id == "haiku_slim"
        and cell.smoke_role == "typed"
    )
    outputs[
        (
            haiku_typed.exact_model_id,
            haiku_typed.packet.slim_candidate.view_hash,
        )
    ] = {"choice": "A"}

    receipt = asyncio.run(
        run_financial_semantic_v6_slim_diagnostic(
            plan=plan,
            model_clients=_clients(outputs),
        )
    )

    assert receipt["status"] == "failed"
    assert receipt["acceptance"]["haiku_typed"] == (
        "FAILED_WITH_EXACT_EVIDENCE"
    )
    assert receipt["attempt_accounting"]["provider_submissions_total"] == 6
    assert receipt["attempt_accounting"]["hidden_retry_total"] == 0
    assert receipt["scope"]["full_benchmark_run"] is False


def test_initial_receipt_and_nonfresh_client_fail_closed(fixture):
    plan = _plan(fixture)
    initial = financial_semantic_v6_slim_diagnostic_initial_receipt(
        plan=plan
    )
    assert initial["execution_state"] == "in_progress"
    assert initial["cases_executed"] == 0
    assert initial["attempt_accounting"][
        "provider_submissions_total"
    ] == 0

    clients = _clients(_expected_outputs(plan))
    clients[V6_PROVIDER_PROFILE_ID].local = 1
    with pytest.raises(
        Gate2FinancialSemanticV6SlimDiagnosticError,
        match="financial_semantic_v6_slim_diagnostic_client_not_fresh",
    ):
        asyncio.run(
            run_financial_semantic_v6_slim_diagnostic(
                plan=plan,
                model_clients=clients,
            )
        )


def test_live_script_uses_factories_once_and_exposes_bounded_help():
    script_path = (
        ROOT
        / "scripts"
        / "live_gate2_financial_semantic_v6_slim_diagnostic.py"
    )
    source = script_path.read_text(encoding="utf-8")
    assert "Gate2FinancialSemanticV6SlimDiagnosticFactory" in source
    assert "run_financial_semantic_v6_slim_diagnostic(" in source
    assert "_model_client(" in source
    assert source.count("_model_client(") == 2
    assert "generate_chat_completion" not in source
    assert "OpenAI(" not in source
    assert "Anthropic(" not in source
    assert "--resume" not in source

    completed = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert "--preflight-only" in completed.stdout
    assert "--execute-six-submission-diagnostic" in completed.stdout
