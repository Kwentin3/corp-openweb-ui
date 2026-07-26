from __future__ import annotations

import ast
import asyncio
import copy
import json
import sys
from pathlib import Path

from broker_reports_gate1.gate2_economy_model_policy import (
    Gate2EconomyModelPolicyFactory,
)
from broker_reports_gate1.gate2_economy_workload_policy import (
    Gate2EconomyWorkloadPolicyFactory,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (
    SUCCESSOR_PROMPT_CONTRACT_ID_V4,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(ROOT))

from live_gate2_financial_successor_qualification_v2 import (  # noqa: E402
    EXACT_MODEL_ID,
    PROVIDER_PROFILE_ID,
    build_successor_qualification_fixture_v2,
)
from live_gate2_managed_financial_domain_shadow_qualification import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    managed_shadow_contract_identity,
    managed_shadow_preflight_cases,
    qualify_managed_shadow_model,
)


MODULE_PATH = (
    SCRIPT_DIR
    / "live_gate2_managed_financial_domain_shadow_qualification.py"
)


class _FixtureClient:
    def __init__(self, outputs):
        self.outputs = [copy.deepcopy(item) for item in outputs]
        self.calls: list[dict] = []

    async def extract(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return Gate2StructuredModelResult(
            content=self.outputs[len(self.calls) - 1],
            execution_metadata=Gate2ProviderExecutionMetadata(
                provider_id="openai",
                provider_profile_id=PROVIDER_PROFILE_ID,
                provider_profile_revision="managed-shadow-test",
                adapter_id="openai_response_format",
                adapter_version="managed-shadow-test",
                requested_model_id=EXACT_MODEL_ID,
                resolved_model_id=EXACT_MODEL_ID,
                structured_output_mode=(
                    "openwebui_response_format_json_schema"
                ),
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
                canonical_request_schema_hash="a" * 64,
                adapted_request_schema_hash="a" * 64,
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
                duration_ms=7,
                finish_reason="stop",
            ),
            economy_budget_receipt={
                "schema_version": "broker_reports_gate2_economy_budget_v1",
                "status": "passed",
                "input_tokens": 100,
                "output_tokens": 20,
                "actual_cost_usd": "0.0001",
            },
        )


def _fixture_and_outputs():
    fixture = build_successor_qualification_fixture_v2()
    return fixture, [
        copy.deepcopy(case.expected_model_output)
        for case in fixture.cases
    ]


def _run(fixture, outputs):
    client = _FixtureClient(outputs)
    result = asyncio.run(
        qualify_managed_shadow_model(
            model_client=client,
            fixture=fixture,
        )
    )
    return result, client


def _unclassified_output(case):
    return {
        "decision": {
            "disposition": "unclassified_financial_input",
            "value_bindings": [
                {
                    "role_id": candidate.allowed_roles[0],
                    "source_value_ref": candidate.source_value_ref,
                }
                for candidate
                in case.scope.decision_contract.package.candidates
            ],
            "reason_code": "ambiguous_registry_type",
        }
    }


def _typed_output(fixture, case, input_type_id):
    declaration = fixture.registry.get(input_type_id)
    candidates = case.scope.decision_contract.package.candidates
    return {
        "decision": {
            "disposition": "typed_input",
            "input_type_id": input_type_id,
            "value_bindings": {
                role: next(
                    (
                        candidate.source_value_ref
                        for candidate in candidates
                        if role in candidate.allowed_roles
                    ),
                    None,
                )
                for role in (
                    *declaration.required_roles,
                    *declaration.optional_roles,
                )
            },
            "reason_code": "typed_supported",
        }
    }


def test_v4_preflight_is_exact_bounded_and_provider_free():
    fixture = build_successor_qualification_fixture_v2()
    cases = managed_shadow_preflight_cases(fixture=fixture)

    assert len(cases) == 12
    assert all(item["schema_dry_build"]["status"] == "passed" for item in cases)
    assert max(
        item["schema_dry_build"]["estimated_input_tokens"]
        for item in cases
    ) <= 6_144
    assert all(
        item["schema_dry_build"]["maximum_output_tokens"] == 640
        for item in cases
    )
    identity = managed_shadow_contract_identity(fixture=fixture).to_dict()
    assert "successor_model_input_v4" in identity["input_contract_version"]
    assert SUCCESSOR_PROMPT_CONTRACT_ID_V4 in identity["prompt_version"]


def test_policy_1_5_authorizes_only_exact_nano_and_keeps_production_empty():
    model_policy = Gate2EconomyModelPolicyFactory().create()
    workload_policy = Gate2EconomyWorkloadPolicyFactory(
        model_policy=model_policy
    ).create()

    assert model_policy.policy_version == "1.5.0"
    assert workload_policy.policy_version == "1.5.0"
    assert workload_policy.route(
        "gate2_financial_evidence"
    ).target_candidate_ids == (EXACT_MODEL_ID,)
    assert model_policy.workload(
        "gate2_financial_evidence"
    ).maximum_estimated_input_tokens == 6_144
    assert all(
        workload_policy.production_allowlist(workload) == ()
        for workload in (
            "gate2_source",
            "gate2_domain",
            "gate2_financial_evidence",
            "gate2_financial_checksum",
        )
    )


def test_exact_outputs_pass_all_safety_gates_and_measure_latency():
    fixture, outputs = _fixture_and_outputs()
    result, client = _run(fixture, outputs)

    assert result["status"] == "passed"
    assert result["qualification"]["model_safe_for_shadow"] == "yes"
    assert all(result["qualification"]["hard_gates"].values())
    assert len(client.calls) == 12
    metrics = result["qualification"]["aggregate_metrics"]
    assert metrics["unsafe_typed_total"] == 0
    assert metrics["data_loss_total"] == 0
    assert metrics["typed_precision"] == 1.0
    assert metrics["typed_recall"] == 1.0
    assert metrics["latency_observed_attempts"] == 12
    assert metrics["latency_total_ms"] == 84
    assert metrics["latency_average_ms"] == 7.0
    assert metrics["latency_max_ms"] == 7


def test_valid_under_typing_is_safe_and_reduces_measured_recall():
    fixture, outputs = _fixture_and_outputs()
    outputs[0] = _unclassified_output(fixture.cases[0])

    result, _ = _run(fixture, outputs)

    assert result["status"] == "passed"
    metrics = result["qualification"]["aggregate_metrics"]
    assert metrics["unsafe_typed_total"] == 0
    assert metrics["safe_under_typing_total"] == 1
    assert metrics["typed_precision"] == 1.0
    assert metrics["typed_recall"] == 0.75
    assert result["qualification"]["product_safety_proof"][
        "quality_expectations_met"
    ] is False


def test_structurally_valid_wrong_typed_decision_is_unsafe():
    fixture, outputs = _fixture_and_outputs()
    index = next(
        index
        for index, case in enumerate(fixture.cases)
        if case.case_id == "syn_successor_v2_multiple_compatible"
    )
    outputs[index] = _typed_output(
        fixture,
        fixture.cases[index],
        "cash_balance_snapshot_v1",
    )

    result, _ = _run(fixture, outputs)

    assert result["status"] == "failed"
    assert result["qualification"]["hard_gates"][
        "unsafe_typed_zero"
    ] is False
    assert result["qualification"]["aggregate_metrics"][
        "unsafe_typed_total"
    ] == 1


def test_financial_to_no_financial_is_a_data_loss_blocker():
    fixture, outputs = _fixture_and_outputs()
    outputs[0] = {
        "decision": {
            "disposition": "no_financial_input",
            "reason_code": "non_financial_content",
        }
    }

    result, _ = _run(fixture, outputs)

    assert result["status"] == "failed"
    assert result["qualification"]["hard_gates"]["data_loss_zero"] is False
    assert result["qualification"]["aggregate_metrics"][
        "data_loss_total"
    ] >= 1


def test_invalid_reference_fails_canonical_materialization_gate():
    fixture, outputs = _fixture_and_outputs()
    outputs[0]["decision"]["value_bindings"][
        "amount"
    ] = "invented:value:ref"

    result, client = _run(fixture, outputs)

    assert len(client.calls) == 12
    assert result["status"] == "failed"
    assert result["qualification"]["hard_gates"][
        "canonical_materialization_errors_zero"
    ] is False
    assert result["qualification"]["aggregate_metrics"][
        "canonical_materialization_errors_total"
    ] == 1


def test_safe_result_excludes_fixture_literals_and_private_refs():
    fixture, outputs = _fixture_and_outputs()
    result, _ = _run(fixture, outputs)
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert '"raw_provider_output_included": false' in serialized
    assert "-123.4500" not in serialized
    assert "Neighbour cash" not in serialized
    assert "Opaque source shape" not in serialized
    assert '"source_groups"' not in serialized
    assert '"source_value_ref"' not in serialized
    assert '"source_scope_ref"' not in serialized


def test_factory_boundary_forbids_production_transport_and_retries():
    assert "Gate2EconomyQualificationPolicyFactory" in FACTORY_REQUIRED
    assert "retry the exact V4 attempt" in FORBIDDEN
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert "for case in fixture.cases" in source
    assert "retry_authorized" in source
    assert not {
        module
        for module in modules
        if module.endswith("gate2_financial_evidence_production_runtime")
        or module.endswith("gate2_domain_runtime")
        or module.endswith("gate2_source_fact_runtime")
        or module.endswith("artifact_store")
    }
