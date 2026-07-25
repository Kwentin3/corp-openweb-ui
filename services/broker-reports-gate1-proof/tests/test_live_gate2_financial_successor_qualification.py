from __future__ import annotations

import ast
import asyncio
import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (  # noqa: E402
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorPromptFactory,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
)
from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from live_gate2_financial_successor_qualification import (  # noqa: E402
    EXACT_MODEL_ID,
    FACTORY_REQUIRED,
    FORBIDDEN,
    PROVIDER_PROFILE_ID,
    _actual_model_output,
    build_successor_qualification_fixture,
    qualify_successor_model,
    successor_preflight_cases,
    successor_qualification_contract_identity,
    write_safe_receipt_atomically,
)


MODULE_PATH = (
    SCRIPT_DIR / "live_gate2_financial_successor_qualification.py"
)


class _FixtureClient:
    def __init__(self, outputs):
        self.outputs = [copy.deepcopy(item) for item in outputs]
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        output = self.outputs[len(self.calls) - 1]
        return Gate2StructuredModelResult(
            content=output,
            execution_metadata=_metadata(),
            economy_budget_receipt={
                "schema_version": (
                    "broker_reports_gate2_economy_budget_v1"
                ),
                "status": "passed",
                "input_tokens": 100,
                "output_tokens": 20,
                "actual_cost_usd": "0.0001",
            },
        )


def _metadata():
    return Gate2ProviderExecutionMetadata(
        provider_id="openai",
        provider_profile_id=PROVIDER_PROFILE_ID,
        provider_profile_revision="qualification-test-v1",
        adapter_id="openai_response_format",
        adapter_version="qualification-test-v1",
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
        finish_reason="stop",
    )


def test_fixture_reuses_frozen_successor_manifest_and_local_proof():
    fixture = build_successor_qualification_fixture()

    assert len(fixture.cases) == 11
    assert fixture.local_proof_receipt["status"] == "passed"
    assert fixture.local_proof_receipt["manifest"][
        "integrity_hash"
    ] == fixture.manifest_canonical_hash
    assert {
        item.expected_disposition for item in fixture.cases
    } == {
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }


def test_preflight_dry_builds_all_strict_schemas_without_calls():
    fixture = build_successor_qualification_fixture()
    cases = successor_preflight_cases(
        fixture=fixture,
        model_id=EXACT_MODEL_ID,
    )

    assert len(cases) == 11
    assert all(
        item["schema_dry_build"]["status"] == "passed"
        and item["schema_dry_build"]["estimated_input_tokens"] > 0
        and item["schema_dry_build"]["maximum_output_tokens"] > 0
        for item in cases
    )


def test_successor_qualification_request_profile_is_bounded_and_budgeted():
    fixture = build_successor_qualification_fixture()
    case = fixture.cases[0]
    runner = Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=fixture.registry,
        model_client=_FixtureClient(
            (case.expected_model_output,)
        ),
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=EXACT_MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
        ),
    ).create()
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=(
            FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE
        )
    ).build(
        prompt=Gate2FinancialEvidenceSuccessorPromptFactory().create(),
        package=runner.model_input(scope=case.scope),
        model_id=EXACT_MODEL_ID,
        response_format=(
            case.scope.decision_contract.openai_response_format()
        ),
    )

    metadata = form_data["metadata"]["broker_reports_gate2"]
    assert metadata["financial_evidence_successor_qualification"] is True
    assert metadata["synthetic_non_customer"] is True
    assert "source_scope_ref" not in metadata
    assert "source_scope_ref" not in form_data["messages"][1]["content"]
    Gate2EconomyBudgetSessionFactory().create(
        request_profile=(
            FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE
        )
    )


def test_qualification_identity_pins_every_required_successor_layer():
    fixture = build_successor_qualification_fixture()
    first = successor_qualification_contract_identity(fixture=fixture)
    second = successor_qualification_contract_identity(fixture=fixture)

    assert first == second
    identity = first.to_dict()
    assert fixture.registry.registry_hash in identity[
        "input_contract_version"
    ]
    assert fixture.manifest_canonical_hash in identity[
        "input_contract_version"
    ]
    assert "broker_reports_gate2_financial_evidence_decision_v1" in (
        identity["output_contract_version"]
    )
    assert "broker_reports_gate2_financial_evidence_successor_prompt_v1" in (
        identity["prompt_version"]
    )
    assert "gate2_successor_product_invariants_v1" in identity[
        "canonical_validator_revision"
    ]


def test_fake_exact_model_qualifies_all_cases_and_product_invariants():
    fixture = build_successor_qualification_fixture()
    client = _FixtureClient(
        case.expected_model_output for case in fixture.cases
    )
    checkpoints = []

    execution = asyncio.run(
        qualify_successor_model(
            model_client=client,
            model_id=EXACT_MODEL_ID,
            fixture=fixture,
            checkpoint=lambda value: checkpoints.append(
                copy.deepcopy(value)
            ),
        )
    )

    assert execution["status"] == "passed"
    assert execution["execution_state"] == "terminal"
    assert execution["provider_calls"] == 11
    assert execution["input_tokens"] == 1100
    assert execution["output_tokens"] == 220
    assert execution["actual_cost_usd"] == "0.0011"
    aggregate = execution["qualification"]["aggregate_metrics"]
    assert aggregate["cases_passed"] == 11
    assert aggregate["cases_failed"] == 0
    assert aggregate["four_dispositions_passed"] is True
    assert aggregate["canonical_validation_passed"] is True
    assert aggregate["fallback_total"] == 0
    assert aggregate["repair_attempts_total"] == 0
    proof = execution["qualification"]["product_proof"]
    assert proof["status"] == "passed"
    assert all(proof["checks"].values())
    assert proof["comparator"]["metrics"]["literal_loss_total"] == 0
    assert proof["artifact_family"]["production_write_admitted"] is False
    assert len(checkpoints) == 13
    assert checkpoints[0]["provider_calls"] == 0
    assert checkpoints[-1]["execution_state"] == "terminal"


def test_actual_model_output_is_reconstructed_from_validated_decision():
    fixture = build_successor_qualification_fixture()
    case = fixture.cases[0]
    result = asyncio.run(
        Gate2FinancialEvidenceSuccessorRunnerFactory(
            registry=fixture.registry,
            model_client=_FixtureClient(
                (case.expected_model_output,)
            ),
            config=Gate2FinancialEvidenceSuccessorConfig(
                model_id=EXACT_MODEL_ID,
                provider_profile_id=PROVIDER_PROFILE_ID,
            ),
        )
        .create()
        .run(
            scope=case.scope,
            execution_ref="execution:reconstruction:test",
            decision_validation_ref="validation:reconstruction:test",
        )
    )

    assert _actual_model_output(
        result=result,
        registry=fixture.registry,
    ) == case.expected_model_output


def test_safe_execution_receipt_contains_no_raw_or_fixture_literals():
    fixture = build_successor_qualification_fixture()
    client = _FixtureClient(
        case.expected_model_output for case in fixture.cases
    )
    execution = asyncio.run(
        qualify_successor_model(
            model_client=client,
            model_id=EXACT_MODEL_ID,
            fixture=fixture,
        )
    )
    serialized = json.dumps(
        execution,
        ensure_ascii=False,
        sort_keys=True,
    )

    assert '"raw_provider_output_included": false' in serialized
    assert "-123.4500" not in serialized
    assert "Neighbour cash" not in serialized
    assert "Opaque source shape" not in serialized
    assert "expected_model_output" not in serialized


def test_atomic_safe_receipt_is_utf8_without_bom(tmp_path):
    path = tmp_path / "qualification.safe.json"
    payload = {"schema_version": "safe_test_v1", "status": "passed"}

    write_safe_receipt_atomically(path=path, payload=payload)

    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8")) == payload
    assert not list(tmp_path.glob(".*.tmp"))


def test_factory_boundary_excludes_production_runtime_and_direct_transport():
    assert "Gate2FinancialEvidenceSuccessorRunnerFactory" in (
        FACTORY_REQUIRED
    )
    assert "must not use customer data" in FORBIDDEN
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not {
        module
        for module in modules
        if module.endswith("gate2_financial_evidence_production_runtime")
        or module.endswith("gate2_domain_runtime")
        or module.endswith("gate2_source_fact_runtime")
        or module.endswith("artifact_store")
    }
