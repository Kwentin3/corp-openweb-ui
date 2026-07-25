from __future__ import annotations

import ast
import asyncio
import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    Gate2DeterministicFinancialScopeFromGate1Factory,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    DECISION_SCHEMA_VERSION,
    DISPOSITIONS,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    FORBIDDEN_MODEL_INPUT_FIELDS,
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION,
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorError,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
    validate_financial_evidence_successor_model_input,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)
from test_broker_reports_gate2_deterministic_financial_scopes import (  # noqa: E402
    _gate1_package,
)


MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_successor.py"
)
MODEL_ID = "gpt-5.4-nano-2026-03-17"
PROVIDER_PROFILE_ID = "openai_gpt"


class _DecisionClient:
    def __init__(
        self,
        *,
        fallback_used: bool = False,
        repair_attempt_count: int = 0,
        metadata: Gate2ProviderExecutionMetadata | None = None,
        output=None,
    ):
        self.fallback_used = fallback_used
        self.repair_attempt_count = repair_attempt_count
        self.metadata = (
            _metadata() if metadata is None else metadata
        )
        self.output = output
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        content = self.output
        if content is None:
            content = {
                "decision": {
                    "disposition": "unclassified_financial_input",
                    "value_bindings": [
                        {
                            "role_id": item["allowed_roles"][0],
                            "source_value_ref": item[
                                "source_value_ref"
                            ],
                        }
                        for item in kwargs["package"]["source_values"]
                    ],
                    "reason_code": "no_registry_type",
                }
            }
        return Gate2StructuredModelResult(
            content=content,
            fallback_used=self.fallback_used,
            repair_attempt_count=self.repair_attempt_count,
            execution_metadata=self.metadata,
        )


class _MissingMetadataClient(_DecisionClient):
    async def extract(self, **kwargs):
        result = await super().extract(**kwargs)
        return Gate2StructuredModelResult(
            content=result.content,
            execution_metadata=None,
        )


def _metadata(
    *,
    model_id: str = MODEL_ID,
    provider_profile_id: str = PROVIDER_PROFILE_ID,
    response_format_type: str = "json_schema",
):
    return Gate2ProviderExecutionMetadata(
        provider_id="openai",
        provider_profile_id=provider_profile_id,
        provider_profile_revision="successor-test-v1",
        adapter_id="openai_response_format",
        adapter_version="successor-test-v1",
        requested_model_id=model_id,
        resolved_model_id=model_id,
        structured_output_mode=(
            "openwebui_response_format_json_schema"
        ),
        response_format_type=response_format_type,
        response_format_schema_mode="strict_json_schema",
    )


def _scope_and_registry():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    scope = Gate2DeterministicFinancialScopeFromGate1Factory(
        registry=registry
    ).create(gate1_packages=(_gate1_package(),)).scopes[0]
    return scope, registry


def _runner(registry, client):
    return Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=registry,
        model_client=client,
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
        ),
    ).create()


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def test_successor_runs_one_existing_decision_and_existing_materializer():
    scope, registry = _scope_and_registry()
    client = _DecisionClient()

    result = asyncio.run(
        _runner(registry, client).run(
            scope=scope,
            execution_ref="execution:successor:test",
            decision_validation_ref="validation:successor:test",
        )
    )

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model_id"] == MODEL_ID
    assert set(call["package"]) == {"eligible_types", "source_values"}
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["response_format"]["json_schema"]["schema"]["title"] == (
        DECISION_SCHEMA_VERSION
    )
    dispositions = {
        value
        for item in _walk_dicts(
            call["response_format"]["json_schema"]["schema"]
        )
        for value in item.get("enum", [])
        if value in DISPOSITIONS
    }
    assert dispositions == set(DISPOSITIONS)
    assert result.materialized_artifact["terminal_disposition"] == (
        "unclassified_financial_input"
    )
    assert result.materialized_artifact["coverage"][
        "candidate_refs_total"
    ] == len(scope.source_package.source_values)
    assert result.safe_summary["materializer"] == (
        "Gate2FinancialEvidenceMaterializerFactory"
    )
    assert result.safe_summary["source_model_calls_total"] == 0
    assert result.safe_summary["domain_model_calls_total"] == 0
    assert result.safe_summary["provider_calls_total"] == 1
    assert result.safe_summary["fallback_total"] == 0
    assert result.safe_summary["repair_attempts_total"] == 0
    assert result.economy_budget_receipt is None


def test_model_input_contains_only_registry_and_package_value_authority():
    scope, registry = _scope_and_registry()
    model_input = _runner(
        registry,
        _DecisionClient(),
    ).model_input(scope=scope)

    assert [
        item["input_type_id"] for item in model_input["eligible_types"]
    ] == list(scope.decision_contract.eligible_type_ids)
    assert [
        item["source_value_ref"] for item in model_input["source_values"]
    ] == [
        item.source_value_ref
        for item in scope.source_package.source_values
    ]
    assert [
        item["literal_value"] for item in model_input["source_values"]
    ] == [
        item.literal_value for item in scope.source_package.source_values
    ]
    assert not {
        key
        for item in _walk_dicts(model_input)
        for key in item
        if key in FORBIDDEN_MODEL_INPUT_FIELDS
    }
    assert all(
        set(item)
        == {
            "source_value_ref",
            "value_type",
            "literal_value",
            "allowed_roles",
        }
        for item in model_input["source_values"]
    )
    assert SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION not in str(model_input)


def test_model_input_is_deterministic_and_validator_rejects_system_fields():
    scope, registry = _scope_and_registry()
    runner = _runner(registry, _DecisionClient())
    first = runner.model_input(scope=scope)
    second = runner.model_input(scope=scope)
    assert first == second

    tampered = copy.deepcopy(first)
    tampered["source_values"][0]["lineage"] = {
        "document_ref": "forbidden"
    }
    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match=(
            "financial_evidence_successor_model_system_field_forbidden"
        ),
    ):
        validate_financial_evidence_successor_model_input(
            model_input=tampered,
            scope=scope,
            registry=registry,
        )


@pytest.mark.parametrize(
    ("client", "error_code"),
    (
        (
            _DecisionClient(fallback_used=True),
            "financial_evidence_successor_fallback_forbidden",
        ),
        (
            _DecisionClient(repair_attempt_count=1),
            "financial_evidence_successor_repair_forbidden",
        ),
        (
            _MissingMetadataClient(),
            "financial_evidence_successor_execution_metadata_missing",
        ),
        (
            _DecisionClient(
                metadata=_metadata(model_id="another-model")
            ),
            "financial_evidence_successor_execution_contract_invalid",
        ),
        (
            _DecisionClient(
                metadata=_metadata(response_format_type="json_object")
            ),
            "financial_evidence_successor_execution_contract_invalid",
        ),
    ),
)
def test_successor_fails_closed_on_transport_contract_drift(
    client,
    error_code,
):
    scope, registry = _scope_and_registry()
    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match=error_code,
    ):
        asyncio.run(
            _runner(registry, client).run(
                scope=scope,
                execution_ref="execution:successor:test",
                decision_validation_ref="validation:successor:test",
            )
        )


def test_out_of_package_ref_and_model_system_field_are_canonical_rejected():
    scope, registry = _scope_and_registry()
    outside = _DecisionClient(
        output={
            "decision": {
                "disposition": "unclassified_financial_input",
                "value_bindings": [
                    {
                        "role_id": "amount",
                        "source_value_ref": "value:outside:scope",
                    }
                ],
                "reason_code": "no_registry_type",
            }
        }
    )
    with pytest.raises(Gate2FinancialEvidenceSuccessorError):
        asyncio.run(
            _runner(registry, outside).run(
                scope=scope,
                execution_ref="execution:successor:test",
                decision_validation_ref="validation:successor:test",
            )
        )

    system_field = _DecisionClient(
        output={
            "decision": {
                "disposition": "no_financial_input",
                "reason_code": "non_financial_content",
                "audit": {"created_by": "model"},
            }
        }
    )
    with pytest.raises(Gate2FinancialEvidenceSuccessorError):
        asyncio.run(
            _runner(registry, system_field).run(
                scope=scope,
                execution_ref="execution:successor:test",
                decision_validation_ref="validation:successor:test",
            )
        )


def test_factory_boundary_has_no_source_domain_or_second_contract_import():
    assert (
        "Gate2FinancialEvidenceSuccessorRunnerFactory.create"
        in FACTORY_REQUIRED
    )
    assert "must not invoke source/domain models" in FORBIDDEN
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not {
        module
        for module in modules
        if module.endswith("gate2_source_fact_runtime")
        or module.endswith("gate2_domain_runtime")
        or module.endswith("gate2_candidate_binding_runtime")
        or module.endswith("gate2_financial_evidence_production_runtime")
    }
