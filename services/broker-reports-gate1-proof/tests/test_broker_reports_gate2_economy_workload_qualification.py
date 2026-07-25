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
    STATUS_DIAGNOSTIC_NOT_SCHEDULED,
    STATUS_NOT_QUALIFIED,
    STATUS_PENDING_STAGE_DELIVERY,
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
    assert len(first.entries) == 16
    assert first.workload_policy_version == "1.4.0"
    assert len(first.workload_policy_hash) == 64
    assert all(item.customer_calls_total == 0 for item in first.entries)
    assert all(item.fallback_calls_total == 0 for item in first.entries)
    assert all(item.repair_attempts_total == 0 for item in first.entries)
    assert {
        (
            item.exact_model_id,
            item.provider_profile_id,
            item.workload_class,
        )
        for item in first.entries
    } == {
        (
            declaration.exact_model_id,
            declaration.provider_profile_id,
            workload.workload_class,
        )
        for declaration in policy.models
        for workload in policy.workloads
    }


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
    gemini_source = registry.status(
        exact_model_id="models/gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_source",
        contract_version="broker_reports_source_facts_v0",
    )
    gemini_checksum = registry.status(
        exact_model_id="models/gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_financial_checksum",
        contract_version=CONTRACT_GATE2_FINANCIAL_CHECKSUM,
    )

    assert gpt_financial.status == STATUS_SYNTHETIC_QUALIFIED
    assert gpt_checksum.status == STATUS_NOT_QUALIFIED
    assert haiku_checksum.status == STATUS_SYNTHETIC_QUALIFIED
    assert gemini_source.status == STATUS_PENDING_STAGE_DELIVERY
    assert gemini_checksum.status == STATUS_DIAGNOSTIC_NOT_SCHEDULED
    assert gemini_source.provider_route_revision == (
        "pending_stage_delivery_policy_1_4"
    )
    assert gemini_source.input_contract_version
    assert gemini_source.output_contract_version
    assert gemini_source.prompt_version
    assert gemini_source.adapter_projection_revision
    assert gemini_source.canonical_validator_revision


def test_synthetic_allowlists_do_not_expand_production_allowlists() -> None:
    evidence = Gate2EconomyWorkloadQualificationFactory().create()
    policy = Gate2EconomyModelPolicyFactory().create()

    assert evidence.synthetic_allowlist("gate2_financial_evidence") == (
        "gpt-5.4-nano-2026-03-17",
    )
    assert evidence.synthetic_allowlist("gate2_financial_checksum") == (
        "claude-haiku-4-5-20251001",
    )
    assert evidence.synthetic_allowlist("gate2_source") == ()
    assert evidence.synthetic_allowlist("gate2_domain") == ()
    for workload in ECONOMY_WORKLOAD_CLASSES:
        assert policy.qualified_allowlist(workload) == ()


def test_factory_and_forbidden_anti_drift_anchors_are_explicit() -> None:
    assert "only code-owned" in FACTORY_REQUIRED
    assert "must not activate" in FORBIDDEN
