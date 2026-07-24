from __future__ import annotations

from dataclasses import replace

import pytest

from broker_reports_gate1.gate2_economy_model_policy import (
    ECONOMY_MODEL_DECLARATIONS,
    ECONOMY_WORKLOAD_CLASSES,
    ECONOMY_WORKLOAD_POLICIES,
    FACTORY_REQUIRED,
    FORBIDDEN,
    MODEL_LIFECYCLE_ACTIVE,
    MODEL_STATUS_NOT_QUALIFIED,
    MODEL_STATUS_QUALIFIED,
    MODEL_STATUS_UNAVAILABLE,
    MODEL_STATUS_UNSUPPORTED_CONTRACT,
    POLICY_ID,
    EconomyModelDeclaration,
    Gate2EconomyModelPolicyError,
    Gate2EconomyModelPolicyFactory,
    validate_economy_model_policy_inputs,
)


def test_factory_is_pure_deterministic_and_has_no_qualified_models_before_receipts() -> None:
    first = Gate2EconomyModelPolicyFactory().create()
    second = Gate2EconomyModelPolicyFactory().create()

    assert first == second
    assert first.policy_id == POLICY_ID
    assert len(first.policy_hash) == 64
    assert first.to_dict() == second.to_dict()
    assert set(item.workload_class for item in first.workloads) == set(
        ECONOMY_WORKLOAD_CLASSES
    )
    for workload_class in ECONOMY_WORKLOAD_CLASSES:
        assert first.qualified_allowlist(workload_class) == ()
        assert first.provider_allowlist(workload_class) == {}


def test_live_qualification_statuses_are_explicit_and_fail_closed() -> None:
    policy = Gate2EconomyModelPolicyFactory().create()

    assert policy.model(
        "gpt-5-nano-2025-08-07"
    ).qualification_status == MODEL_STATUS_UNAVAILABLE
    assert policy.model(
        "gpt-5.4-nano-2026-03-17"
    ).qualification_status == MODEL_STATUS_UNAVAILABLE
    assert policy.model(
        "models/gemini-3.1-flash-lite"
    ).qualification_status == MODEL_STATUS_NOT_QUALIFIED
    assert policy.model(
        "models/gemini-3.5-flash-lite"
    ).qualification_status == MODEL_STATUS_UNSUPPORTED_CONTRACT
    assert policy.model(
        "claude-haiku-4-5-20251001"
    ).qualification_status == MODEL_STATUS_UNSUPPORTED_CONTRACT


@pytest.mark.parametrize(
    ("alias", "exact"),
    [
        ("gpt-5-nano", "gpt-5-nano-2025-08-07"),
        ("gpt-5.4-nano", "gpt-5.4-nano-2026-03-17"),
        (
            "gemini-3.1-flash-lite",
            "models/gemini-3.1-flash-lite",
        ),
        (
            "gemini-3.5-flash-lite",
            "models/gemini-3.5-flash-lite",
        ),
        ("claude-haiku-4-5", "claude-haiku-4-5-20251001"),
    ],
)
def test_aliases_resolve_to_exact_ids(alias: str, exact: str) -> None:
    policy = Gate2EconomyModelPolicyFactory().create()

    resolution = policy.resolve_model_id(alias)

    assert resolution.alias_used is True
    assert resolution.requested_model_id == alias
    assert resolution.exact_model_id == exact


@pytest.mark.parametrize(
    "model_id",
    [
        "gpt-5.6-sol",
        "gpt-5.6-luna",
        "gpt-5.4-mini-2026-03-17",
        "models/gemini-3.5-flash",
        "models/gemini-3.1-pro-preview",
        "claude-sonnet-5",
        "claude-opus-4-8",
    ],
)
def test_expensive_or_non_economy_model_is_not_registered(model_id: str) -> None:
    policy = Gate2EconomyModelPolicyFactory().create()

    with pytest.raises(
        Gate2EconomyModelPolicyError,
        match="not registered",
    ) as exc_info:
        policy.resolve_model_id(model_id)

    assert exc_info.value.code == "economy_model_not_registered"


def test_unqualified_candidate_cannot_be_selected_by_runtime() -> None:
    policy = Gate2EconomyModelPolicyFactory().create()

    with pytest.raises(Gate2EconomyModelPolicyError) as exc_info:
        policy.assert_runtime_model_allowed(
            model_id="models/gemini-3.1-flash-lite",
            workload_class="gate2_financial_evidence",
        )

    assert exc_info.value.code == "economy_model_not_qualified"


def test_runtime_override_cannot_expand_empty_qualified_allowlist() -> None:
    policy = Gate2EconomyModelPolicyFactory().create()

    with pytest.raises(Gate2EconomyModelPolicyError) as exc_info:
        policy.narrow_runtime_allowlist(
            workload_class="gate2_domain",
            requested_model_ids=("models/gemini-3.1-flash-lite",),
        )

    assert (
        exc_info.value.code
        == "economy_runtime_allowlist_expansion_forbidden"
    )


def test_active_model_requires_qualified_status_and_receipt() -> None:
    invalid = _replace_first(
        lifecycle=MODEL_LIFECYCLE_ACTIVE,
        qualification_status=MODEL_STATUS_QUALIFIED,
        qualification_receipt_identity=None,
    )

    with pytest.raises(Gate2EconomyModelPolicyError) as exc_info:
        validate_economy_model_policy_inputs(
            invalid,
            ECONOMY_WORKLOAD_POLICIES,
        )

    assert exc_info.value.code == "economy_policy_qualification_receipt_missing"


@pytest.mark.parametrize(
    "expensive_id",
    [
        "gpt-5.6-sol",
        "models/gemini-3.5-flash",
        "claude-sonnet-5",
    ],
)
def test_policy_validation_rejects_expensive_family(
    expensive_id: str,
) -> None:
    invalid = _replace_first(exact_model_id=expensive_id, aliases=())

    with pytest.raises(Gate2EconomyModelPolicyError) as exc_info:
        validate_economy_model_policy_inputs(
            invalid,
            ECONOMY_WORKLOAD_POLICIES,
        )

    assert exc_info.value.code == "economy_policy_model_family_forbidden"


def test_policy_validation_rejects_paid_tools_and_multi_call_default() -> None:
    paid_tools = _replace_first(paid_tools_allowed=True)
    with pytest.raises(Gate2EconomyModelPolicyError) as model_exc:
        validate_economy_model_policy_inputs(
            paid_tools,
            ECONOMY_WORKLOAD_POLICIES,
        )
    assert model_exc.value.code == "economy_policy_paid_tools_forbidden"

    invalid_workloads = (
        replace(
            ECONOMY_WORKLOAD_POLICIES[0],
            maximum_provider_calls_per_operation=2,
        ),
        *ECONOMY_WORKLOAD_POLICIES[1:],
    )
    with pytest.raises(Gate2EconomyModelPolicyError) as workload_exc:
        validate_economy_model_policy_inputs(
            ECONOMY_MODEL_DECLARATIONS,
            invalid_workloads,
        )
    assert workload_exc.value.code == "economy_policy_default_calls_invalid"


def test_factory_and_forbidden_anti_drift_anchors_are_explicit() -> None:
    assert "only production" in FACTORY_REQUIRED
    assert "must not extend" in FORBIDDEN


def _replace_first(**changes) -> tuple[EconomyModelDeclaration, ...]:
    return (
        replace(ECONOMY_MODEL_DECLARATIONS[0], **changes),
        *ECONOMY_MODEL_DECLARATIONS[1:],
    )
