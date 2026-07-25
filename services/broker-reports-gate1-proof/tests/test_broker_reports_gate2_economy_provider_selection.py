from __future__ import annotations

from dataclasses import replace

import pytest

from broker_reports_gate1.gate2_economy_model_policy import (
    WORKLOAD_GATE2_DOMAIN,
    WORKLOAD_GATE2_FINANCIAL_CHECKSUM,
    WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
    Gate2EconomyModelPolicyFactory,
)
from broker_reports_gate1.gate2_economy_provider_selection import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    SELECTION_RULE,
    Gate2EconomyProviderSelectionError,
    Gate2EconomyProviderSelectionFactory,
)
from broker_reports_gate1.gate2_economy_workload_policy import (
    ECONOMY_WORKLOAD_ROUTES,
    EconomyWorkloadProductionAdmission,
    Gate2EconomyWorkloadPolicyFactory,
)


def test_current_policy_fails_closed_before_provider_selection() -> None:
    selector = Gate2EconomyProviderSelectionFactory().create()

    with pytest.raises(Gate2EconomyProviderSelectionError) as exc_info:
        selector.select_runtime(workload_class=WORKLOAD_GATE2_DOMAIN)

    assert exc_info.value.code == "gate2_economy_no_qualified_model"


def test_runtime_selects_workload_primary_then_one_fixed_secondary() -> None:
    selector = _selector_with_production(
        WORKLOAD_GATE2_DOMAIN,
        (
            "models/gemini-3.1-flash-lite",
            "models/gemini-3.5-flash-lite",
        ),
    )

    selection = selector.select_runtime(
        workload_class=WORKLOAD_GATE2_DOMAIN
    )

    assert selection.primary.exact_model_id == (
        "models/gemini-3.1-flash-lite"
    )
    assert selection.primary.provider_profile_id == "google_gemini"
    assert selection.fallback is not None
    assert selection.fallback.exact_model_id == (
        "models/gemini-3.5-flash-lite"
    )
    assert selection.selection_rule == SELECTION_RULE
    assert selection.default_provider_calls == 1
    assert selection.maximum_fallback_calls == 1
    assert selection.multi_provider_consensus_calls == 0


def test_runtime_inputs_can_only_narrow_exact_workload_allowlist() -> None:
    selector = _selector_with_production(
        WORKLOAD_GATE2_DOMAIN,
        ("models/gemini-3.1-flash-lite",),
    )

    selection = selector.select_runtime(
        workload_class=WORKLOAD_GATE2_DOMAIN,
        requested_model_ids=("models/gemini-3.1-flash-lite",),
        requested_provider_profile_ids=("google_gemini",),
    )

    assert selection.primary.exact_model_id == (
        "models/gemini-3.1-flash-lite"
    )
    assert selection.fallback is None

    with pytest.raises(Gate2EconomyProviderSelectionError) as expansion:
        selector.select_runtime(
            workload_class=WORKLOAD_GATE2_DOMAIN,
            requested_model_ids=("models/gemini-3.5-flash-lite",),
        )
    assert (
        expansion.value.code
        == "economy_runtime_allowlist_expansion_forbidden"
    )

    with pytest.raises(Gate2EconomyProviderSelectionError) as provider:
        selector.select_runtime(
            workload_class=WORKLOAD_GATE2_DOMAIN,
            requested_provider_profile_ids=("anthropic_claude",),
        )
    assert (
        provider.value.code
        == "economy_runtime_provider_allowlist_expansion_forbidden"
    )


def test_checksum_selection_has_zero_fallback_by_policy() -> None:
    selector = _selector_with_production(
        WORKLOAD_GATE2_FINANCIAL_CHECKSUM,
        ("claude-haiku-4-5-20251001",),
    )

    selection = selector.select_runtime(
        workload_class=WORKLOAD_GATE2_FINANCIAL_CHECKSUM
    )

    assert selection.primary.exact_model_id == (
        "claude-haiku-4-5-20251001"
    )
    assert selection.fallback is None
    assert selection.maximum_fallback_calls == 0


def test_qualification_route_requires_exact_workload_candidate() -> None:
    selector = Gate2EconomyProviderSelectionFactory().create()

    selection = selector.select_qualification_candidate(
        workload_class=WORKLOAD_GATE2_DOMAIN,
        model_id="models/gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
    )

    assert selection.primary.exact_model_id == (
        "models/gemini-3.1-flash-lite"
    )
    assert selection.fallback is None

    financial = selector.select_qualification_candidate(
        workload_class=WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
        model_id="claude-haiku-4-5-20251001",
        provider_profile_id="anthropic_claude",
    )
    assert financial.primary.exact_model_id == (
        "claude-haiku-4-5-20251001"
    )
    assert financial.fallback is None

    with pytest.raises(
        Gate2EconomyProviderSelectionError
    ) as terminal_nano:
        selector.select_qualification_candidate(
            workload_class=WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
            model_id="gpt-5.4-nano-2026-03-17",
            provider_profile_id="openai_gpt",
        )
    assert (
        terminal_nano.value.code
        == "economy_workload_qualification_candidate_forbidden"
    )

    with pytest.raises(Gate2EconomyProviderSelectionError) as alias:
        selector.select_qualification_candidate(
            workload_class=WORKLOAD_GATE2_DOMAIN,
            model_id="gemini-3.1-flash-lite",
            provider_profile_id="google_gemini",
        )
    assert (
        alias.value.code
        == "economy_workload_qualification_candidate_forbidden"
    )

    with pytest.raises(Gate2EconomyProviderSelectionError) as expensive:
        selector.select_qualification_candidate(
            workload_class=WORKLOAD_GATE2_DOMAIN,
            model_id="models/gemini-3.5-flash",
            provider_profile_id="google_gemini",
        )
    assert expensive.value.code == "economy_model_not_registered"

    with pytest.raises(Gate2EconomyProviderSelectionError) as mismatch:
        selector.select_qualification_candidate(
            workload_class=WORKLOAD_GATE2_DOMAIN,
            model_id="models/gemini-3.1-flash-lite",
            provider_profile_id="openai_gpt",
        )
    assert mismatch.value.code == "economy_qualification_candidate_forbidden"


def test_selection_receipt_is_safe_and_bound_to_both_policies() -> None:
    selector = _selector_with_production(
        WORKLOAD_GATE2_DOMAIN,
        ("models/gemini-3.1-flash-lite",),
    )
    selection = selector.select_runtime(
        workload_class=WORKLOAD_GATE2_DOMAIN
    )

    receipt = selection.safe_receipt()

    assert receipt["policy_id"] == selection.policy_id
    assert receipt["policy_hash"] == selection.policy_hash
    assert receipt["model_policy_id"] == selection.model_policy_id
    assert receipt["model_policy_hash"] == selection.model_policy_hash
    assert receipt["primary"]["exact_model_id"] == (
        "models/gemini-3.1-flash-lite"
    )
    assert "customer" not in str(receipt).lower()


def test_factory_and_forbidden_anti_drift_anchors_are_explicit() -> None:
    assert "only production" in FACTORY_REQUIRED
    assert "must not accept unqualified models" in FORBIDDEN


def _selector_with_production(
    workload_class: str,
    model_ids: tuple[str, ...],
):
    model_policy = Gate2EconomyModelPolicyFactory().create()
    admissions = tuple(
        EconomyWorkloadProductionAdmission(
            exact_model_id=model_id,
            provider_profile_id=(
                model_policy.model(model_id).provider_profile_id
            ),
            qualification_receipt_sha256=(
                f"{index + 1:x}" * 64
            )[:64],
            actual_corpus_receipt_sha256=(
                f"{index + 5:x}" * 64
            )[:64],
            full_scope_receipt_sha256=(
                f"{index + 9:x}" * 64
            )[:64],
        )
        for index, model_id in enumerate(model_ids)
    )
    routes = tuple(
        replace(route, production_admissions=admissions)
        if route.workload_class == workload_class
        else route
        for route in ECONOMY_WORKLOAD_ROUTES
    )
    workload_policy = Gate2EconomyWorkloadPolicyFactory(
        model_policy=model_policy,
        routes=routes,
    ).create()
    return Gate2EconomyProviderSelectionFactory(
        policy=model_policy,
        workload_policy=workload_policy,
    ).create()
