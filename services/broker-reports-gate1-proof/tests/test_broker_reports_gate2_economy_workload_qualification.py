from __future__ import annotations

from broker_reports_gate1.gate2_economy_model_policy import (
    ECONOMY_WORKLOAD_CLASSES,
    Gate2EconomyModelPolicyFactory,
)
from broker_reports_gate1.gate2_economy_workload_qualification import (
    CONTRACT_GATE2_FINANCIAL_CHECKSUM,
    CONTRACT_GATE2_FINANCIAL_EVIDENCE,
    FACTORY_REQUIRED,
    FORBIDDEN,
    STATUS_NOT_QUALIFIED,
    STATUS_PROVIDER_ROUTE_UNAVAILABLE,
    STATUS_SYNTHETIC_QUALIFIED,
    Gate2EconomyWorkloadQualificationFactory,
)


def test_registry_is_deterministic_and_bound_to_policy() -> None:
    first = Gate2EconomyWorkloadQualificationFactory().create()
    second = Gate2EconomyWorkloadQualificationFactory().create()
    policy = Gate2EconomyModelPolicyFactory().create()

    assert first == second
    assert first.policy_version == policy.policy_version
    assert first.policy_hash == policy.policy_hash
    assert len(first.registry_hash) == 64
    assert len(first.entries) == 12
    assert all(item.customer_calls_total == 0 for item in first.entries)
    assert all(item.fallback_calls_total == 0 for item in first.entries)
    assert all(item.repair_attempts_total == 0 for item in first.entries)


def test_status_is_exact_model_route_workload_and_contract_specific() -> None:
    registry = Gate2EconomyWorkloadQualificationFactory().create()

    gpt_financial = registry.status(
        exact_model_id="gpt-5.4-nano-2026-03-17",
        provider_profile_id="openai_gpt",
        workload_class="gate2_financial_evidence",
        contract_version=CONTRACT_GATE2_FINANCIAL_EVIDENCE,
    )
    gpt_checksum = registry.status(
        exact_model_id="gpt-5.4-nano-2026-03-17",
        provider_profile_id="openai_gpt",
        workload_class="gate2_financial_checksum",
        contract_version=CONTRACT_GATE2_FINANCIAL_CHECKSUM,
    )
    haiku_checksum = registry.status(
        exact_model_id="claude-haiku-4-5-20251001",
        provider_profile_id="anthropic_claude",
        workload_class="gate2_financial_checksum",
        contract_version=CONTRACT_GATE2_FINANCIAL_CHECKSUM,
    )
    gemini_financial = registry.status(
        exact_model_id="models/gemini-2.5-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_financial_evidence",
        contract_version=CONTRACT_GATE2_FINANCIAL_EVIDENCE,
    )

    assert gpt_financial.status == STATUS_SYNTHETIC_QUALIFIED
    assert gpt_checksum.status == STATUS_NOT_QUALIFIED
    assert haiku_checksum.status == STATUS_SYNTHETIC_QUALIFIED
    assert gemini_financial.status == STATUS_PROVIDER_ROUTE_UNAVAILABLE


def test_synthetic_allowlists_do_not_expand_production_allowlists() -> None:
    evidence = Gate2EconomyWorkloadQualificationFactory().create()
    policy = Gate2EconomyModelPolicyFactory().create()

    assert evidence.synthetic_allowlist("gate2_financial_evidence") == (
        "gpt-5.4-nano-2026-03-17",
    )
    assert evidence.synthetic_allowlist("gate2_financial_checksum") == (
        "claude-haiku-4-5-20251001",
    )
    assert set(evidence.synthetic_allowlist("gate2_source")) == {
        "claude-haiku-4-5-20251001"
    }
    for workload in ECONOMY_WORKLOAD_CLASSES:
        assert policy.qualified_allowlist(workload) == ()


def test_factory_and_forbidden_anti_drift_anchors_are_explicit() -> None:
    assert "only code-owned" in FACTORY_REQUIRED
    assert "must not activate" in FORBIDDEN
