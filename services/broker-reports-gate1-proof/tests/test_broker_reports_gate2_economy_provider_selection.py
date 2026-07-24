from __future__ import annotations

from dataclasses import replace

import pytest

from broker_reports_gate1.gate2_economy_model_policy import (
    MODEL_LIFECYCLE_ACTIVE,
    MODEL_STATUS_QUALIFIED,
    WORKLOAD_GATE2_DOMAIN,
    WORKLOAD_GATE2_FINANCIAL_CHECKSUM,
    Gate2EconomyModelPolicyFactory,
)
from broker_reports_gate1.gate2_economy_provider_selection import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    SELECTION_RULE,
    Gate2EconomyProviderSelectionError,
    Gate2EconomyProviderSelectionFactory,
)


def test_current_policy_fails_closed_before_provider_selection() -> None:
    selector = Gate2EconomyProviderSelectionFactory().create()

    with pytest.raises(Gate2EconomyProviderSelectionError) as exc_info:
        selector.select_runtime(workload_class=WORKLOAD_GATE2_DOMAIN)

    assert exc_info.value.code == "gate2_economy_no_qualified_model"


def test_runtime_selects_cheapest_qualified_then_one_fixed_fallback() -> None:
    selector = Gate2EconomyProviderSelectionFactory(
        policy=_policy_with_qualified_models(0, 1, 2)
    ).create()

    selection = selector.select_runtime(
        workload_class=WORKLOAD_GATE2_DOMAIN
    )

    assert selection.primary.exact_model_id == "gpt-5-nano-2025-08-07"
    assert selection.primary.provider_profile_id == "openai_gpt"
    assert selection.fallback is not None
    assert selection.fallback.exact_model_id == (
        "gpt-5.4-nano-2026-03-17"
    )
    assert selection.selection_rule == SELECTION_RULE
    assert selection.default_provider_calls == 1
    assert selection.maximum_fallback_calls == 1
    assert selection.multi_provider_consensus_calls == 0


def test_runtime_model_and_provider_inputs_can_only_narrow_allowlist() -> None:
    selector = Gate2EconomyProviderSelectionFactory(
        policy=_policy_with_qualified_models(0, 2)
    ).create()

    selection = selector.select_runtime(
        workload_class=WORKLOAD_GATE2_DOMAIN,
        requested_model_ids=("gemini-3.1-flash-lite",),
        requested_provider_profile_ids=("google_gemini",),
    )

    assert selection.primary.exact_model_id == (
        "models/gemini-3.1-flash-lite"
    )
    assert selection.fallback is None

    with pytest.raises(Gate2EconomyProviderSelectionError) as exc_info:
        selector.select_runtime(
            workload_class=WORKLOAD_GATE2_DOMAIN,
            requested_provider_profile_ids=("anthropic_claude",),
        )
    assert (
        exc_info.value.code
        == "economy_runtime_provider_allowlist_expansion_forbidden"
    )


def test_checksum_selection_has_no_fallback_even_with_two_models() -> None:
    selector = Gate2EconomyProviderSelectionFactory(
        policy=_policy_with_qualified_models(0, 1)
    ).create()

    selection = selector.select_runtime(
        workload_class=WORKLOAD_GATE2_FINANCIAL_CHECKSUM
    )

    assert selection.fallback is None
    assert selection.maximum_fallback_calls == 0


def test_qualification_route_accepts_only_registered_economy_candidate() -> None:
    selector = Gate2EconomyProviderSelectionFactory().create()

    selection = selector.select_qualification_candidate(
        workload_class=WORKLOAD_GATE2_DOMAIN,
        model_id="gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
    )

    assert selection.primary.exact_model_id == (
        "models/gemini-3.1-flash-lite"
    )
    assert selection.fallback is None

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
            model_id="gemini-3.1-flash-lite",
            provider_profile_id="openai_gpt",
        )
    assert mismatch.value.code == "economy_qualification_candidate_forbidden"


def test_selection_receipt_is_safe_and_policy_bound() -> None:
    selection = Gate2EconomyProviderSelectionFactory(
        policy=_policy_with_qualified_models(0)
    ).create().select_runtime(workload_class=WORKLOAD_GATE2_DOMAIN)

    receipt = selection.safe_receipt()

    assert receipt["policy_id"] == selection.policy_id
    assert receipt["policy_version"] == selection.policy_version
    assert receipt["policy_hash"] == selection.policy_hash
    assert receipt["primary"]["exact_model_id"] == (
        "gpt-5-nano-2025-08-07"
    )
    assert "customer" not in str(receipt).lower()


def test_factory_and_forbidden_anti_drift_anchors_are_explicit() -> None:
    assert "only production" in FACTORY_REQUIRED
    assert "must not accept unqualified models" in FORBIDDEN


def _policy_with_qualified_models(*indexes: int):
    policy = Gate2EconomyModelPolicyFactory().create()
    qualified = set(indexes)
    return replace(
        policy,
        models=tuple(
            replace(
                declaration,
                lifecycle=MODEL_LIFECYCLE_ACTIVE,
                qualification_status=MODEL_STATUS_QUALIFIED,
                qualification_receipt_identity=(
                    f"receipt:test:{index}"
                ),
            )
            if index in qualified
            else declaration
            for index, declaration in enumerate(policy.models)
        ),
    )
