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

from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V2,
    Gate2OpenWebUIRequestBuilder,
)
from live_gate2_financial_successor_qualification_v2 import (  # noqa: E402
    EXACT_MODEL_ID,
    FACTORY_REQUIRED,
    FORBIDDEN,
    PROVIDER_PROFILE_ID,
    _runner,
    build_successor_qualification_fixture_v2,
    qualify_successor_model_v2,
    successor_preflight_cases_v2,
    successor_qualification_contract_identity_v2,
    write_safe_receipt_atomically,
)


MODULE_PATH = (
    SCRIPT_DIR / "live_gate2_financial_successor_qualification_v2.py"
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
        provider_profile_revision="qualification-v2-test",
        adapter_id="openai_response_format",
        adapter_version="qualification-v2-test",
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


def test_fixture_v2_reuses_frozen_manifest_and_local_q0_q1_proof():
    fixture = build_successor_qualification_fixture_v2()

    assert len(fixture.cases) == 12
    assert fixture.local_proof_receipt["status"] == "passed"
    assert fixture.local_proof_receipt["manifest"][
        "integrity_hash"
    ] == fixture.manifest_canonical_hash
    assert fixture.local_proof_receipt["q0_contract_tests"][
        "status"
    ] == "passed"
    assert fixture.local_proof_receipt[
        "q1_product_invariant_fixtures"
    ]["status"] == "passed"
    assert {
        item.expected_disposition for item in fixture.cases
    } == {
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }


def test_preflight_v2_dry_builds_exact_stack_without_provider_calls():
    fixture = build_successor_qualification_fixture_v2()
    cases = successor_preflight_cases_v2(
        fixture=fixture,
        model_id=EXACT_MODEL_ID,
    )

    assert len(cases) == 12
    assert sum(item["typed_branch_admitted"] for item in cases) == 4
    assert all(
        item["schema_dry_build"]["status"] == "passed"
        and item["schema_dry_build"]["estimated_input_tokens"] > 0
        and item["schema_dry_build"]["maximum_output_tokens"] > 0
        for item in cases
    )


def test_v2_request_profile_is_bounded_versioned_and_budgeted():
    fixture = build_successor_qualification_fixture_v2()
    case = fixture.cases[0]
    runner = _runner(
        fixture=fixture,
        model_client=_FixtureClient(
            (case.expected_model_output,)
        ),
        model_id=EXACT_MODEL_ID,
    )
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=(
            FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V2
        )
    ).build(
        prompt=runner.prompt,
        package=runner.model_input(
            scope=case.scope,
            source_context=case.source_context,
        ),
        model_id=EXACT_MODEL_ID,
        response_format=(
            case.scope.decision_contract.openai_response_format()
        ),
    )

    metadata = form_data["metadata"]["broker_reports_gate2"]
    assert metadata[
        "financial_evidence_successor_qualification_v2"
    ] is True
    assert metadata["synthetic_non_customer"] is True
    assert "source_scope_ref" not in metadata
    assert "source_scope_ref" not in form_data["messages"][1]["content"]
    assert "source_groups" in form_data["messages"][0]["content"]
    Gate2EconomyBudgetSessionFactory().create(
        request_profile=(
            FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V2
        )
    )


def test_v2_identity_pins_scope_context_prompt_projection_and_artifacts():
    fixture = build_successor_qualification_fixture_v2()
    first = successor_qualification_contract_identity_v2(
        fixture=fixture
    )
    second = successor_qualification_contract_identity_v2(
        fixture=fixture
    )

    assert first == second
    identity = first.to_dict()
    assert "deterministic_financial_scope_package_v2" in identity[
        "input_contract_version"
    ]
    assert "financial_evidence_source_context_v2" in identity[
        "input_contract_version"
    ]
    assert "successor_model_input_v3" in identity[
        "input_contract_version"
    ]
    assert fixture.manifest_canonical_hash in identity[
        "input_contract_version"
    ]
    assert "financial_evidence_provider_projection_v3" in identity[
        "output_contract_version"
    ]
    assert "financial_evidence_successor_prompt_v3" in identity[
        "prompt_version"
    ]
    assert "gate2_successor_artifact_family_v2" in identity[
        "canonical_validator_revision"
    ]


def test_fake_exact_model_qualifies_v2_and_all_product_invariants():
    fixture = build_successor_qualification_fixture_v2()
    client = _FixtureClient(
        case.expected_model_output for case in fixture.cases
    )
    checkpoints = []

    execution = asyncio.run(
        qualify_successor_model_v2(
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
    assert execution["provider_calls"] == 12
    assert execution["input_tokens"] == 1200
    assert execution["output_tokens"] == 240
    assert execution["actual_cost_usd"] == "0.0012"
    aggregate = execution["qualification"]["aggregate_metrics"]
    assert aggregate["cases_passed"] == 12
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
    assert proof["artifact_family"][
        "private_source_context_stored"
    ] is False
    assert len(checkpoints) == 14
    assert checkpoints[0]["provider_calls"] == 0
    assert checkpoints[-1]["execution_state"] == "terminal"


def test_v2_safe_execution_contains_no_raw_or_fixture_literals():
    fixture = build_successor_qualification_fixture_v2()
    execution = asyncio.run(
        qualify_successor_model_v2(
            model_client=_FixtureClient(
                case.expected_model_output for case in fixture.cases
            ),
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
    assert '"source_groups"' not in serialized


def test_v2_atomic_safe_receipt_is_utf8_without_bom(tmp_path):
    path = tmp_path / "qualification-v2.safe.json"
    payload = {"schema_version": "safe_v2_test", "status": "passed"}

    write_safe_receipt_atomically(path=path, payload=payload)

    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8")) == payload
    assert not list(tmp_path.glob(".*.tmp"))


def test_v2_factory_boundary_excludes_production_and_direct_transport():
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
