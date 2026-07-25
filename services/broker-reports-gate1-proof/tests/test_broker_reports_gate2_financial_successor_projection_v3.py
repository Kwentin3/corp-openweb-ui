from __future__ import annotations

import ast
import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_source_context import (  # noqa: E402
    Gate2FinancialEvidenceSourceContextFactory,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (  # noqa: E402
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2,
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3,
    SUCCESSOR_PROMPT_CONTRACT_ID,
    SUCCESSOR_PROMPT_CONTRACT_ID_V3,
    SUCCESSOR_RESULT_SCHEMA_VERSION_V3,
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorError,
    Gate2FinancialEvidenceSuccessorPromptFactory,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
    validate_financial_evidence_successor_model_input_v3,
)
from broker_reports_gate1.gate2_financial_evidence_successor_projection import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION,
    SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION,
    Gate2FinancialEvidenceSuccessorProviderProjection,
    Gate2FinancialEvidenceSuccessorProviderProjectionError,
    Gate2FinancialEvidenceSuccessorProviderProjectionFactory,
    validate_successor_provider_projection,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v1"
    / "manifest.json"
)
PROJECTION_MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_successor_projection.py"
)
MODEL_ID = "gpt-5.4-nano-2026-03-17"
PROVIDER_PROFILE_ID = "openai_gpt"
PROMPT_V2_HASH = (
    "1362c50190bc7859d74b300e5e1fad037cf7ad4939f9946f3c43e4b88930e5fc"
)
PROMPT_V3_HASH = (
    "30c823d2c509294d4634eac1a4084da9b95056b260bdd64e41d5a5598937d9ae"
)


class _DecisionClient:
    def __init__(self):
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        bindings = [
            {
                "role_id": value["allowed_roles"][0],
                "source_value_ref": value["source_value_ref"],
            }
            for group in kwargs["package"]["source_groups"]
            for value in group["values"]
        ]
        return Gate2StructuredModelResult(
            content={
                "decision": {
                    "disposition": "unclassified_financial_input",
                    "value_bindings": bindings,
                    "reason_code": "ambiguous_registry_type",
                }
            },
            execution_metadata=Gate2ProviderExecutionMetadata(
                provider_id="openai",
                provider_profile_id=PROVIDER_PROFILE_ID,
                provider_profile_revision="projection-v3-test",
                adapter_id="openai_response_format",
                adapter_version="projection-v3-test",
                requested_model_id=MODEL_ID,
                resolved_model_id=MODEL_ID,
                structured_output_mode=(
                    "openwebui_response_format_json_schema"
                ),
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
            ),
        )


def _cases() -> dict[str, dict]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in manifest["cases"]}


def _scope_context(case_id: str):
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = _fixture_package(copy.deepcopy(_cases()[case_id]))
    scope = Gate2DeterministicFinancialScopeFromGate1V2Factory(
        registry=registry
    ).create(gate1_packages=(fixture.payload,)).scopes[0]
    context = Gate2FinancialEvidenceSourceContextFactory().create(
        source_scope_ref=scope.source_package.source_scope_ref,
        source_values=scope.source_package.source_values,
        candidates=scope.decision_contract.package.candidates,
        gate1_packages=(fixture.payload,),
    )
    return scope, context, registry


def _runner(registry, client=None, *, version=None, prompt_id=None):
    return Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=registry,
        model_client=client or _DecisionClient(),
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
            model_input_schema_version=(
                version or SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
            ),
            prompt_contract_id=(
                prompt_id or SUCCESSOR_PROMPT_CONTRACT_ID_V3
            ),
        ),
    ).create()


def _variants(response_format):
    return response_format["json_schema"]["schema"]["properties"][
        "decision"
    ]["anyOf"]


def _disposition(variant):
    return variant["properties"]["disposition"]["enum"][0]


def test_prompt_v3_is_generic_and_v2_identity_stays_frozen():
    v2 = Gate2FinancialEvidenceSuccessorPromptFactory().create()
    v3 = Gate2FinancialEvidenceSuccessorPromptFactory().create(
        prompt_contract_id=SUCCESSOR_PROMPT_CONTRACT_ID_V3
    )

    assert v2.prompt_ref == "code:" + SUCCESSOR_PROMPT_CONTRACT_ID
    assert v2.hash == PROMPT_V2_HASH
    assert v3.prompt_ref == "code:" + SUCCESSOR_PROMPT_CONTRACT_ID_V3
    assert v3.hash == PROMPT_V3_HASH
    assert "normal safe outcome" in v3.content
    assert "Code-owned typed admission" in v3.content
    assert "not an instruction to choose it" in v3.content
    assert "counterexamples" in v3.content
    assert "cash_balance_snapshot_v1" not in v3.content
    assert "printed_financial_metric_v1" not in v3.content
    assert "equal literals" not in v3.content
    assert "adjacent" not in v3.content


def test_model_input_v3_adds_only_registry_counterexamples():
    scope, context, registry = _scope_context(
        "syn_successor_signed_literal"
    )
    runner = _runner(registry)

    model_input = runner.model_input(
        scope=scope,
        source_context=context,
    )

    assert set(model_input) == {"eligible_types", "source_groups"}
    assert len(model_input["eligible_types"]) == 1
    projected = model_input["eligible_types"][0]
    declaration = registry.get(projected["input_type_id"])
    assert projected["counterexamples"] == list(
        declaration.counterexamples
    )
    assert "expected_answer" not in json.dumps(model_input)
    assert model_input["source_groups"] == context.provider_groups()


def test_model_input_v3_counterexample_drift_fails_closed():
    scope, context, registry = _scope_context(
        "syn_successor_signed_literal"
    )
    model_input = _runner(registry).model_input(
        scope=scope,
        source_context=context,
    )
    model_input["eligible_types"][0]["counterexamples"] = [
        "fixture says typed"
    ]

    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match="financial_evidence_successor_counterexamples_invalid",
    ):
        validate_financial_evidence_successor_model_input_v3(
            model_input=model_input,
            scope=scope,
            registry=registry,
            source_context=context,
        )


def test_provider_projection_is_unclassified_first_and_semantic_only():
    scope, _, _ = _scope_context("syn_successor_signed_literal")
    canonical = scope.decision_contract.openai_response_format()

    projection = (
        Gate2FinancialEvidenceSuccessorProviderProjectionFactory().create(
            contract=scope.decision_contract
        )
    )

    assert projection.disposition_order == (
        "unclassified_financial_input",
        "typed_input",
        "no_financial_input",
        "unsupported",
    )
    assert projection.typed_type_ids == (
        "cash_balance_snapshot_v1",
    )
    assert sorted(
        sha256_json(item) for item in _variants(canonical)
    ) == sorted(
        sha256_json(item)
        for item in _variants(projection.response_format)
    )
    summary = projection.safe_summary()
    assert summary["schema_version"] == (
        SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
    )
    assert summary["policy_version"] == (
        SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION
    )
    assert summary["canonical_semantics_changed"] is False
    assert summary["provider_calls_total"] == 0


def test_ambiguous_scope_provider_schema_has_no_typed_variant():
    scope, _, _ = _scope_context(
        "syn_successor_multiple_hypotheses"
    )

    projection = (
        Gate2FinancialEvidenceSuccessorProviderProjectionFactory().create(
            contract=scope.decision_contract
        )
    )

    assert projection.disposition_order == (
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    )
    assert projection.typed_type_ids == ()
    assert {
        _disposition(item)
        for item in _variants(projection.response_format)
    } == {
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }


def test_projection_tamper_cannot_change_canonical_branch():
    scope, _, _ = _scope_context("syn_successor_signed_literal")
    projection = (
        Gate2FinancialEvidenceSuccessorProviderProjectionFactory().create(
            contract=scope.decision_contract
        )
    )
    response_format = copy.deepcopy(projection.response_format)
    _variants(response_format)[0]["properties"]["reason_code"]["enum"] = [
        "tampered"
    ]
    tampered = Gate2FinancialEvidenceSuccessorProviderProjection(
        response_format=response_format,
        response_format_hash=sha256_json(response_format),
        disposition_order=projection.disposition_order,
        typed_type_ids=projection.typed_type_ids,
    )

    with pytest.raises(
        Gate2FinancialEvidenceSuccessorProviderProjectionError,
        match="successor_provider_projection_branch_semantics_changed",
    ):
        validate_successor_provider_projection(
            projection=tampered,
            contract=scope.decision_contract,
        )


def test_v3_runner_uses_exact_prompt_input_and_provider_projection():
    scope, context, registry = _scope_context(
        "syn_successor_signed_literal"
    )
    client = _DecisionClient()
    runner = _runner(registry, client)

    result = asyncio.run(
        runner.run(
            scope=scope,
            source_context=context,
            execution_ref="execution:projection-v3:test",
            decision_validation_ref="validation:projection-v3:test",
        )
    )

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["prompt"].prompt_ref == (
        "code:" + SUCCESSOR_PROMPT_CONTRACT_ID_V3
    )
    assert "source_groups" in call["package"]
    assert [_disposition(item) for item in _variants(
        call["response_format"]
    )][0] == "unclassified_financial_input"
    assert result.safe_summary["schema_version"] == (
        SUCCESSOR_RESULT_SCHEMA_VERSION_V3
    )
    assert result.safe_summary["model_input_schema_version"] == (
        SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
    )
    assert result.safe_summary["provider_projection_schema_version"] == (
        SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
    )
    assert result.safe_summary["fallback_total"] == 0
    assert result.safe_summary["repair_attempts_total"] == 0


def test_prompt_and_model_input_versions_cannot_be_mixed():
    _, _, registry = _scope_context("syn_successor_signed_literal")
    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match="financial_evidence_successor_config_invalid",
    ):
        _runner(
            registry,
            version=SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2,
            prompt_id=SUCCESSOR_PROMPT_CONTRACT_ID_V3,
        )


def test_projection_factory_has_no_provider_or_validator_bypass():
    assert "only successor response-format projection" in FACTORY_REQUIRED
    assert "must not add a decision branch" in FORBIDDEN
    tree = ast.parse(PROJECTION_MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not {
        module
        for module in imported_modules
        if "provider_adapters" in module
        or "model_clients" in module
        or "production_runtime" in module
        or "materialization_validation" in module
    }
