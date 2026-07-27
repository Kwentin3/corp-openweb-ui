from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
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
from broker_reports_gate1.gate2_financial_semantic_v6_bundle import (  # noqa: E402
    Gate2FinancialEvidenceBundleFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_candidate_compiler import (  # noqa: E402,E501
    Gate2FinancialCandidateCompilerFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (  # noqa: E402,E501
    Gate2FinancialSemanticV6ChoiceContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_execution_identity import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FAILURE_CLASS_BY_STAGE,
    FORBIDDEN,
    V6_EXACT_MODEL_ID,
    V6_QUALIFICATION_REQUEST_PROFILE,
    V6_PROVIDER_PROFILE_ID,
    Gate2FinancialSemanticV6CapturedExecution,
    Gate2FinancialSemanticV6ExecutionIdentityError,
    Gate2FinancialSemanticV6ExecutionIdentityFactory,
    classify_financial_semantic_v6_qualification_failure,
    financial_semantic_v6_response_format,
    validate_financial_semantic_v6_execution_identity,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV6PacketFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    Gate2ProviderAdapterFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"
MODULE_PATH = (
    ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_execution_identity.py"
)


def _choice_contract():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    fixture = _fixture_package(copy.deepcopy(manifest["cases"][0]))
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    scope = (
        Gate2DeterministicFinancialScopeFromGate1V2Factory(registry=registry)
        .create(gate1_packages=(fixture.payload,))
        .scopes[0]
    )
    bundle = Gate2FinancialEvidenceBundleFactory().create(
        source_package=scope.source_package,
        gate1_packages=(fixture.payload,),
    )
    compilation = Gate2FinancialCandidateCompilerFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
    )
    packet = Gate2FinancialSemanticV6PacketFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )
    return Gate2FinancialSemanticV6ChoiceContractFactory(registry=registry).create(
        packet=packet,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )


def _captured_execution(choice_contract):
    profile = gate2_provider_profile(V6_PROVIDER_PROFILE_ID)
    response_format = financial_semantic_v6_response_format(choice_contract)
    prepared = Gate2ProviderAdapterFactory(
        profile=profile,
        capability_probe=True,
    ).create().prepare_form_data(
        form_data={
            "model": V6_EXACT_MODEL_ID,
            "messages": [{"role": "user", "content": "schema-projection"}],
            "response_format": response_format,
        },
        response_format=response_format,
    )
    metadata = Gate2ProviderExecutionMetadata(
        provider_id=profile.provider_id,
        provider_profile_id=profile.profile_id,
        provider_profile_revision=gate2_provider_profile_revision(profile),
        adapter_id=profile.adapter_id,
        adapter_version=profile.adapter_version,
        requested_model_id=V6_EXACT_MODEL_ID,
        resolved_model_id=V6_EXACT_MODEL_ID,
        provider_response_id="resp_synthetic_v6_exact",
        structured_output_mode=profile.structured_output_mode,
        response_format_type=profile.response_format_type,
        response_format_schema_mode=profile.response_format_schema_mode,
        transport_type=profile.transport_type,
        canonical_request_schema_hash=prepared.canonical_schema_hash,
        adapted_request_schema_hash=prepared.adapted_schema_hash,
        schema_transform_count=prepared.schema_transform_count,
        duration_ms=87,
        input_tokens=211,
        output_tokens=19,
        total_tokens=230,
        cached_input_tokens=None,
        reasoning_tokens=None,
        finish_reason="stop",
    )
    return Gate2FinancialSemanticV6CapturedExecution(
        request_profile=V6_QUALIFICATION_REQUEST_PROFILE,
        response_format_hash=sha256_json(response_format),
        execution_metadata=metadata,
        actual_cost_usd="0.000041",
    )


def test_synthetic_captured_execution_identity_dry_proof_passes() -> None:
    choice_contract = _choice_contract()
    capture = _captured_execution(choice_contract)
    identity = Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
        capture=capture,
        choice_contract=choice_contract,
    )

    assert identity.provider_metadata_status == "verified"
    assert identity.canonical_request_schema_hash == (
        choice_contract.choice_schema_hash
    )
    assert identity.adapted_request_schema_hash != (
        identity.canonical_request_schema_hash
    )
    assert identity.schema_transform_count == 1
    assert identity.response_format_hash != identity.canonical_request_schema_hash
    assert identity.cached_input_tokens == 0
    assert identity.reasoning_tokens == 0
    assert identity.total_tokens == identity.input_tokens + identity.output_tokens
    assert identity.actual_cost_usd == "0.000041"
    assert identity.safe_summary()["execution_identity_dry_proof"] == "PASSED"
    assert identity.safe_summary()["false_provider_identity_rejection_total"] == 0
    assert identity.safe_summary()["provider_calls_total"] == 0
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not conflate" in FORBIDDEN


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_profile_id", "wrong_profile"),
        ("provider_profile_revision", "0" * 64),
        ("adapter_version", "wrong"),
        ("transport_type", "wrong"),
        ("requested_model_id", "wrong-model"),
        ("resolved_model_id", "wrong-model"),
    ],
)
def test_real_provider_identity_mismatch_fails_closed(field, value) -> None:
    choice_contract = _choice_contract()
    capture = _captured_execution(choice_contract)
    capture = replace(
        capture,
        execution_metadata=replace(
            capture.execution_metadata,
            **{field: value},
        ),
    )

    with pytest.raises(
        Gate2FinancialSemanticV6ExecutionIdentityError,
    ) as failure:
        Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
            capture=capture,
            choice_contract=choice_contract,
        )
    assert failure.value.failure_class == "provider_metadata_defect"


def test_request_profile_mismatch_fails_as_provider_metadata_defect() -> None:
    choice_contract = _choice_contract()
    capture = replace(
        _captured_execution(choice_contract),
        request_profile="financial_semantic_v5",
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ExecutionIdentityError,
        match="financial_semantic_v6_provider_execution_identity_mismatch",
    ) as failure:
        Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
            capture=capture,
            choice_contract=choice_contract,
        )
    assert failure.value.failure_class == "provider_metadata_defect"


@pytest.mark.parametrize(
    "capture_transform",
    [
        lambda item: replace(item, response_format_hash="0" * 64),
        lambda item: replace(
            item,
            execution_metadata=replace(
                item.execution_metadata,
                canonical_request_schema_hash="0" * 64,
            ),
        ),
        lambda item: replace(
            item,
            execution_metadata=replace(
                item.execution_metadata,
                adapted_request_schema_hash="0" * 64,
            ),
        ),
        lambda item: replace(
            item,
            execution_metadata=replace(
                item.execution_metadata,
                schema_transform_count=0,
            ),
        ),
    ],
)
def test_response_format_or_schema_mismatch_is_schema_defect(
    capture_transform,
) -> None:
    choice_contract = _choice_contract()
    capture = capture_transform(_captured_execution(choice_contract))
    with pytest.raises(
        Gate2FinancialSemanticV6ExecutionIdentityError,
    ) as failure:
        Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
            capture=capture,
            choice_contract=choice_contract,
        )
    assert failure.value.failure_class == "schema_defect"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("duration_ms", -1),
        ("input_tokens", True),
        ("total_tokens", 229),
        ("cached_input_tokens", 212),
        ("reasoning_tokens", 20),
    ],
)
def test_invalid_provider_usage_metadata_fails_closed(field, value) -> None:
    choice_contract = _choice_contract()
    capture = _captured_execution(choice_contract)
    capture = replace(
        capture,
        execution_metadata=replace(
            capture.execution_metadata,
            **{field: value},
        ),
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ExecutionIdentityError,
    ) as failure:
        Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
            capture=capture,
            choice_contract=choice_contract,
        )
    assert failure.value.failure_class == "provider_metadata_defect"


@pytest.mark.parametrize("cost", ["-0.01", "NaN", 0.01])
def test_invalid_provider_cost_metadata_fails_closed(cost) -> None:
    choice_contract = _choice_contract()
    capture = replace(
        _captured_execution(choice_contract),
        actual_cost_usd=cost,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ExecutionIdentityError,
        match="financial_semantic_v6_provider_cost_invalid",
    ) as failure:
        Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
            capture=capture,
            choice_contract=choice_contract,
        )
    assert failure.value.failure_class == "provider_metadata_defect"


def test_harness_failure_classes_are_exhaustive_and_distinct() -> None:
    expected = {
        "provider_execution_identity": "provider_metadata_defect",
        "provider_schema": "schema_defect",
        "model_decision": "model_decision_defect",
        "canonical_validation": "validator_defect",
        "materialization": "materializer_defect",
    }
    assert FAILURE_CLASS_BY_STAGE == expected
    assert len(set(expected.values())) == len(expected)
    assert {
        stage: classify_financial_semantic_v6_qualification_failure(stage)
        for stage in expected
    } == expected


def test_identity_is_deterministic_tamper_evident_and_safe() -> None:
    choice_contract = _choice_contract()
    capture = _captured_execution(choice_contract)
    first = Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
        capture=capture,
        choice_contract=choice_contract,
    )
    second = Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
        capture=capture,
        choice_contract=choice_contract,
    )
    assert first == second
    assert capture.execution_metadata.provider_response_id not in json.dumps(
        first.safe_summary(),
        sort_keys=True,
    )

    tampered = replace(first, total_tokens=999)
    with pytest.raises(
        Gate2FinancialSemanticV6ExecutionIdentityError,
        match="financial_semantic_v6_execution_identity_tampered",
    ):
        validate_financial_semantic_v6_execution_identity(
            identity=tampered,
            capture=capture,
            choice_contract=choice_contract,
        )


def test_module_has_no_provider_call_fallback_retry_or_identity_inference() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "requests." not in source
    assert "httpx." not in source
    assert "aiohttp." not in source
    assert "provider_calls_total" in source
    assert '"fallback"' not in source.casefold()
    assert '"retry"' not in source.casefold()
    assert "getattr(" not in source
