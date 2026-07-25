from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

from broker_reports_gate1.gate2_economy_model_policy import (
    ECONOMY_WORKLOAD_CLASSES,
    Gate2EconomyModelPolicyFactory,
)
from broker_reports_gate1.gate2_economy_qualification_policy import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    QUALIFICATION_RECEIPT_IDENTITY_FIELDS,
    Gate2EconomyQualificationContractIdentity,
    Gate2EconomyQualificationPolicyFactory,
)
from broker_reports_gate1.gate2_economy_workload_policy import (
    Gate2EconomyWorkloadPolicyFactory,
)


ROOT = Path(__file__).resolve().parents[1]
ACTION_PATH = (
    ROOT / "openwebui_actions" / "broker_reports_gate2_economy_qualification_action.py"
)


def _identity() -> Gate2EconomyQualificationContractIdentity:
    return Gate2EconomyQualificationContractIdentity(
        provider_route_revision="provider-route-exact-v1",
        input_contract_version="input-contract-v1",
        output_contract_version="output-contract-v1",
        prompt_version="prompt-v1",
        adapter_projection_revision="adapter-projection-v1",
        canonical_validator_revision="canonical-validator-v1",
    )


def _load_action_module():
    spec = importlib.util.spec_from_file_location(
        "broker_reports_gate2_economy_qualification_action_under_test",
        ACTION_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("qualification action import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_snapshot_is_exact_policy_1_4_qualification_only() -> None:
    policy = Gate2EconomyQualificationPolicyFactory().create()
    snapshot = policy.snapshot()
    model_policy = Gate2EconomyModelPolicyFactory().create()
    workload_policy = Gate2EconomyWorkloadPolicyFactory(
        model_policy=model_policy
    ).create()

    assert snapshot["scope"] == "qualification_only"
    assert snapshot["model_policy"]["policy_version"] == "1.4.0"
    assert snapshot["model_policy"]["policy_hash"] == model_policy.policy_hash
    assert snapshot["workload_policy"]["policy_hash"] == workload_policy.policy_hash
    assert len(snapshot["qualification_policy_hash"]) == 64
    assert snapshot["qualification_controls"] == {
        "receipt_identity_fields": list(QUALIFICATION_RECEIPT_IDENTITY_FIELDS),
        "fallback_calls_allowed": 0,
        "repair_attempts_allowed": 0,
        "paid_tools_allowed": False,
    }
    assert all(
        snapshot["workload_routes"][workload]["production_admissions"] == []
        for workload in ECONOMY_WORKLOAD_CLASSES
    )


@pytest.mark.parametrize(
    ("workload", "model_id", "provider", "reasoning"),
    (
        (
            "gate2_source",
            "models/gemini-3.1-flash-lite",
            "google_gemini",
            "minimal",
        ),
        (
            "gate2_domain",
            "models/gemini-3.5-flash-lite",
            "google_gemini",
            "minimal",
        ),
        (
            "gate2_financial_evidence",
            "claude-haiku-4-5-20251001",
            "anthropic_claude",
            "disabled",
        ),
        (
            "gate2_financial_checksum",
            "claude-haiku-4-5-20251001",
            "anthropic_claude",
            "disabled",
        ),
    ),
)
def test_authorization_is_exact_workload_model_route_and_receipt_identity(
    workload: str,
    model_id: str,
    provider: str,
    reasoning: str,
) -> None:
    policy = Gate2EconomyQualificationPolicyFactory().create()
    first = policy.authorize(
        workload_class=workload,
        exact_model_id=model_id,
        provider_profile_id=provider,
        receipt_identity=_identity(),
    ).safe_receipt()
    second = policy.authorize(
        workload_class=workload,
        exact_model_id=model_id,
        provider_profile_id=provider,
        receipt_identity=_identity(),
    ).safe_receipt()

    assert first == second
    assert first["workload_class"] == workload
    assert first["exact_model_id"] == model_id
    assert first["provider_profile_id"] == provider
    assert first["reasoning_policy"] == reasoning
    assert first["paid_tools_allowed"] is False
    assert first["fallback_calls_allowed"] == 0
    assert first["repair_attempts_allowed"] == 0
    assert set(first["receipt_identity"]) == set(QUALIFICATION_RECEIPT_IDENTITY_FIELDS)
    assert len(first["authorization_identity_sha256"]) == 64


@pytest.mark.parametrize(
    ("workload", "model_id", "provider"),
    (
        (
            "gate2_source",
            "gemini-3.1-flash-lite",
            "google_gemini",
        ),
        (
            "gate2_source",
            "gpt-5.4-nano-2026-03-17",
            "openai_gpt",
        ),
        (
            "gate2_source",
            "models/gemini-3.1-flash-lite",
            "openai_gpt",
        ),
    ),
)
def test_authorization_fails_closed_for_alias_workload_or_provider_drift(
    workload: str,
    model_id: str,
    provider: str,
) -> None:
    with pytest.raises(ValueError):
        Gate2EconomyQualificationPolicyFactory().create().authorize(
            workload_class=workload,
            exact_model_id=model_id,
            provider_profile_id=provider,
            receipt_identity=_identity(),
        )


def test_authorization_rejects_incomplete_receipt_identity() -> None:
    with pytest.raises(
        ValueError,
        match="Every workload-specific qualification identity",
    ):
        Gate2EconomyQualificationPolicyFactory().create().authorize(
            workload_class="gate2_source",
            exact_model_id="models/gemini-3.1-flash-lite",
            provider_profile_id="google_gemini",
            receipt_identity=Gate2EconomyQualificationContractIdentity(
                provider_route_revision="",
                input_contract_version="input-contract-v1",
                output_contract_version="output-contract-v1",
                prompt_version="prompt-v1",
                adapter_projection_revision="adapter-projection-v1",
                canonical_validator_revision="canonical-validator-v1",
            ),
        )


def test_action_is_closed_world_exact_snapshot_and_read_only() -> None:
    module = _load_action_module()
    expected = Gate2EconomyQualificationPolicyFactory().create().snapshot()
    action = module.Action()
    result = asyncio.run(
        action.action(
            {},
            __id__=module.ACTION_ID,
        )
    )
    source = ACTION_PATH.read_text(encoding="utf-8")

    assert module.POLICY_SNAPSHOT == expected
    assert result["broker_reports_gate2_economy_qualification_policy"] == expected
    assert "broker_reports_gate1" not in source
    assert "from open_webui" not in source
    assert "requests" not in source
    assert "http" not in source.lower()
    assert all(
        route["production_admissions"] == []
        for route in module.POLICY_SNAPSHOT["workload_routes"].values()
    )


def test_factory_and_forbidden_anti_drift_anchors_are_explicit() -> None:
    assert "only" in FACTORY_REQUIRED
    assert "must not" in FORBIDDEN
