from __future__ import annotations

from dataclasses import replace

import pytest

from broker_reports_gate1.gate2_economy_model_policy import (
    ECONOMY_WORKLOAD_CLASSES,
    Gate2EconomyModelPolicyFactory,
)
from broker_reports_gate1.gate2_economy_workload_policy import (
    ECONOMY_WORKLOAD_ROUTES,
    FACTORY_REQUIRED,
    FORBIDDEN,
    EconomyWorkloadProductionAdmission,
    Gate2EconomyWorkloadPolicyError,
    Gate2EconomyWorkloadPolicyFactory,
)


def test_v3_candidate_matrix_is_exact_and_production_empty() -> None:
    policy = Gate2EconomyWorkloadPolicyFactory().create()

    assert policy.policy_version == "1.4.0"
    assert len(policy.policy_hash) == 64
    assert policy.route("gate2_source").target_candidate_ids == (
        "models/gemini-3.1-flash-lite",
        "models/gemini-3.5-flash-lite",
    )
    assert policy.route("gate2_domain").target_candidate_ids == (
        "models/gemini-3.1-flash-lite",
        "models/gemini-3.5-flash-lite",
    )
    assert policy.route(
        "gate2_financial_evidence"
    ).target_candidate_ids == (
        "claude-haiku-4-5-20251001",
    )
    assert policy.route(
        "gate2_financial_checksum"
    ).target_candidate_ids == (
        "claude-haiku-4-5-20251001",
        "gpt-5.4-nano-2026-03-17",
    )
    assert policy.route(
        "gate2_financial_evidence"
    ).diagnostic_candidate_exact_model_ids == (
        "models/gemini-3.1-flash-lite",
        "models/gemini-3.5-flash-lite",
    )
    for workload in ECONOMY_WORKLOAD_CLASSES:
        assert policy.production_allowlist(workload) == ()
        assert policy.provider_allowlist(workload) == {}


def test_qualification_requires_exact_id_and_correct_workload() -> None:
    model_policy = Gate2EconomyModelPolicyFactory().create()
    policy = Gate2EconomyWorkloadPolicyFactory(
        model_policy=model_policy
    ).create()

    exact = policy.assert_qualification_candidate(
        workload_class="gate2_source",
        model_id="models/gemini-3.1-flash-lite",
        model_policy=model_policy,
    )
    assert exact == "models/gemini-3.1-flash-lite"

    financial_exact = policy.assert_qualification_candidate(
        workload_class="gate2_financial_evidence",
        model_id="claude-haiku-4-5-20251001",
        model_policy=model_policy,
    )
    assert financial_exact == "claude-haiku-4-5-20251001"

    with pytest.raises(Gate2EconomyWorkloadPolicyError) as alias:
        policy.assert_qualification_candidate(
            workload_class="gate2_source",
            model_id="gemini-3.1-flash-lite",
            model_policy=model_policy,
        )
    assert (
        alias.value.code
        == "economy_workload_qualification_candidate_forbidden"
    )

    with pytest.raises(Gate2EconomyWorkloadPolicyError) as wrong_workload:
        policy.assert_qualification_candidate(
            workload_class="gate2_source",
            model_id="claude-haiku-4-5-20251001",
            model_policy=model_policy,
        )
    assert (
        wrong_workload.value.code
        == "economy_workload_qualification_candidate_forbidden"
    )

    with pytest.raises(
        Gate2EconomyWorkloadPolicyError
    ) as terminal_nano:
        policy.assert_qualification_candidate(
            workload_class="gate2_financial_evidence",
            model_id="gpt-5.4-nano-2026-03-17",
            model_policy=model_policy,
        )
    assert (
        terminal_nano.value.code
        == "economy_workload_qualification_candidate_forbidden"
    )


def test_runtime_config_can_only_narrow_production_admissions() -> None:
    model_policy = Gate2EconomyModelPolicyFactory().create()
    admission = EconomyWorkloadProductionAdmission(
        exact_model_id="models/gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
        qualification_receipt_sha256="a" * 64,
        actual_corpus_receipt_sha256="b" * 64,
        full_scope_receipt_sha256="c" * 64,
    )
    routes = tuple(
        replace(route, production_admissions=(admission,))
        if route.workload_class == "gate2_source"
        else route
        for route in ECONOMY_WORKLOAD_ROUTES
    )
    policy = Gate2EconomyWorkloadPolicyFactory(
        model_policy=model_policy,
        routes=routes,
    ).create()

    assert policy.narrow_runtime_allowlist(
        workload_class="gate2_source",
        requested_model_ids=("models/gemini-3.1-flash-lite",),
    ) == ("models/gemini-3.1-flash-lite",)

    with pytest.raises(Gate2EconomyWorkloadPolicyError) as expansion:
        policy.narrow_runtime_allowlist(
            workload_class="gate2_source",
            requested_model_ids=("models/gemini-3.5-flash-lite",),
        )
    assert (
        expansion.value.code
        == "economy_runtime_allowlist_expansion_forbidden"
    )


def test_production_admission_requires_all_three_receipts() -> None:
    invalid = EconomyWorkloadProductionAdmission(
        exact_model_id="claude-haiku-4-5-20251001",
        provider_profile_id="anthropic_claude",
        qualification_receipt_sha256="a" * 64,
        actual_corpus_receipt_sha256="",
        full_scope_receipt_sha256="c" * 64,
    )
    routes = tuple(
        replace(route, production_admissions=(invalid,))
        if route.workload_class == "gate2_financial_checksum"
        else route
        for route in ECONOMY_WORKLOAD_ROUTES
    )

    with pytest.raises(Gate2EconomyWorkloadPolicyError) as exc_info:
        Gate2EconomyWorkloadPolicyFactory(routes=routes).create()

    assert (
        exc_info.value.code
        == "economy_workload_production_receipt_invalid"
    )


def test_empty_route_override_is_rejected_instead_of_defaulted() -> None:
    with pytest.raises(Gate2EconomyWorkloadPolicyError) as exc_info:
        Gate2EconomyWorkloadPolicyFactory(routes=()).create()

    assert exc_info.value.code == "economy_workload_route_set_invalid"


def test_factory_and_forbidden_anchors_are_explicit() -> None:
    assert "only code-owned" in FACTORY_REQUIRED
    assert "must not activate" in FORBIDDEN
