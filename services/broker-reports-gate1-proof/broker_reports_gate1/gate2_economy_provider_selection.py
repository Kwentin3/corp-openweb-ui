from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .gate2_economy_model_policy import (
    EconomyModelDeclaration,
    Gate2EconomyModelPolicyFactory,
    Gate2EconomyModelPolicySnapshot,
)
from .gate2_economy_workload_policy import (
    Gate2EconomyWorkloadPolicyFactory,
    Gate2EconomyWorkloadPolicySnapshot,
)


FACTORY_REQUIRED = (
    "Gate2EconomyProviderSelectionFactory.create is the only production "
    "Gate 2 economy provider selection entrypoint"
)
FORBIDDEN = (
    "Runtime selection must not accept unqualified models, expand the "
    "policy allowlist, call providers concurrently, or escalate model tier"
)
SELECTION_SCHEMA_VERSION = "broker_reports_gate2_economy_provider_selection_v2"
SELECTION_RULE = "cheapest_workload_qualified_primary_then_secondary"


class Gate2EconomyProviderSelectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Gate2EconomyProviderBinding:
    provider_profile_id: str
    exact_model_id: str
    estimated_maximum_operation_cost_usd: str

    def to_dict(self) -> dict[str, str]:
        return {
            "provider_profile_id": self.provider_profile_id,
            "exact_model_id": self.exact_model_id,
            "estimated_maximum_operation_cost_usd": (
                self.estimated_maximum_operation_cost_usd
            ),
        }


@dataclass(frozen=True)
class Gate2EconomyProviderSelection:
    workload_class: str
    policy_id: str
    policy_version: str
    policy_hash: str
    model_policy_id: str
    model_policy_version: str
    model_policy_hash: str
    primary: Gate2EconomyProviderBinding
    fallback: Gate2EconomyProviderBinding | None
    selection_rule: str = SELECTION_RULE
    default_provider_calls: int = 1
    maximum_fallback_calls: int = 1
    multi_provider_consensus_calls: int = 0

    def safe_receipt(self) -> dict[str, object]:
        return {
            "schema_version": SELECTION_SCHEMA_VERSION,
            "workload_class": self.workload_class,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
            "model_policy_id": self.model_policy_id,
            "model_policy_version": self.model_policy_version,
            "model_policy_hash": self.model_policy_hash,
            "selection_rule": self.selection_rule,
            "primary": self.primary.to_dict(),
            "fallback": (
                None if self.fallback is None else self.fallback.to_dict()
            ),
            "default_provider_calls": self.default_provider_calls,
            "maximum_fallback_calls": self.maximum_fallback_calls,
            "multi_provider_consensus_calls": (
                self.multi_provider_consensus_calls
            ),
        }


class Gate2EconomyProviderSelectionFactory:
    def __init__(
        self,
        *,
        policy: Gate2EconomyModelPolicySnapshot | None = None,
        workload_policy: Gate2EconomyWorkloadPolicySnapshot | None = None,
    ) -> None:
        self.policy = policy
        self.workload_policy = workload_policy

    def create(self) -> "Gate2EconomyProviderSelector":
        model_policy = (
            self.policy or Gate2EconomyModelPolicyFactory().create()
        )
        workload_policy = (
            self.workload_policy
            or Gate2EconomyWorkloadPolicyFactory(
                model_policy=model_policy
            ).create()
        )
        if (
            workload_policy.model_policy_id != model_policy.policy_id
            or workload_policy.model_policy_version
            != model_policy.policy_version
            or workload_policy.model_policy_hash != model_policy.policy_hash
        ):
            raise Gate2EconomyProviderSelectionError(
                "economy_provider_selection_policy_binding_mismatch",
                "Provider selection requires an exactly bound workload "
                "and model policy pair",
            )
        return Gate2EconomyProviderSelector(
            policy=model_policy,
            workload_policy=workload_policy,
        )


class Gate2EconomyProviderSelector:
    def __init__(
        self,
        *,
        policy: Gate2EconomyModelPolicySnapshot,
        workload_policy: Gate2EconomyWorkloadPolicySnapshot,
    ) -> None:
        self.policy = policy
        self.workload_policy = workload_policy

    def select_runtime(
        self,
        *,
        workload_class: str,
        requested_model_ids: Iterable[str] | None = None,
        requested_provider_profile_ids: Iterable[str] | None = None,
    ) -> Gate2EconomyProviderSelection:
        try:
            allowed_model_ids = self.workload_policy.narrow_runtime_allowlist(
                workload_class=workload_class,
                requested_model_ids=requested_model_ids,
            )
        except ValueError as exc:
            raise Gate2EconomyProviderSelectionError(
                getattr(
                    exc,
                    "code",
                    "economy_provider_selection_model_allowlist_invalid",
                ),
                str(exc),
            ) from exc
        provider_ids = _normalized(requested_provider_profile_ids)
        qualified_provider_ids = set(
            self.workload_policy.provider_allowlist(workload_class)
        )
        if provider_ids is not None and not set(provider_ids).issubset(
            qualified_provider_ids
        ):
            raise Gate2EconomyProviderSelectionError(
                "economy_runtime_provider_allowlist_expansion_forbidden",
                "Runtime provider configuration may only narrow the "
                "qualified economy allowlist",
            )
        declarations = [
            self.policy.model(model_id)
            for model_id in allowed_model_ids
            if provider_ids is None
            or self.policy.model(model_id).provider_profile_id
            in set(provider_ids)
        ]
        if not declarations:
            raise Gate2EconomyProviderSelectionError(
                "gate2_economy_no_qualified_model",
                "No qualified economy model is available for the workload",
            )
        route_order = self.workload_policy.production_allowlist(
            workload_class
        )
        ordered = sorted(
            declarations,
            key=lambda item: route_order.index(item.exact_model_id),
        )
        primary = self._binding(ordered[0], workload_class)
        fallback_declaration = next(
            (item for item in ordered[1:] if item.fallback_eligible),
            None,
        )
        return self._selection(
            workload_class=workload_class,
            primary=primary,
            fallback=(
                None
                if fallback_declaration is None
                else self._binding(fallback_declaration, workload_class)
            ),
        )

    def select_qualification_candidate(
        self,
        *,
        workload_class: str,
        model_id: str,
        provider_profile_id: str,
    ) -> Gate2EconomyProviderSelection:
        try:
            exact_model_id = (
                self.workload_policy.assert_qualification_candidate(
                    workload_class=workload_class,
                    model_id=model_id,
                    model_policy=self.policy,
                )
            )
            declaration = self.policy.model(exact_model_id)
            workload = self.policy.workload(workload_class)
        except ValueError as exc:
            raise Gate2EconomyProviderSelectionError(
                getattr(
                    exc,
                    "code",
                    "economy_qualification_candidate_invalid",
                ),
                str(exc),
            ) from exc
        if (
            declaration.provider_profile_id != provider_profile_id
            or workload.workload_class not in declaration.workload_classes
        ):
            raise Gate2EconomyProviderSelectionError(
                "economy_qualification_candidate_forbidden",
                "Qualification candidate does not match the code-owned "
                "economy policy",
            )
        return self._selection(
            workload_class=workload_class,
            primary=self._binding(declaration, workload_class),
            fallback=None,
        )

    def _selection(
        self,
        *,
        workload_class: str,
        primary: Gate2EconomyProviderBinding,
        fallback: Gate2EconomyProviderBinding | None,
    ) -> Gate2EconomyProviderSelection:
        workload = self.policy.workload(workload_class)
        maximum_fallback_calls = min(
            1,
            workload.maximum_fallback_calls_per_operation,
            self.workload_policy.route(
                workload_class
            ).maximum_fallback_calls_per_operation,
        )
        return Gate2EconomyProviderSelection(
            workload_class=workload_class,
            policy_id=self.workload_policy.policy_id,
            policy_version=self.workload_policy.policy_version,
            policy_hash=self.workload_policy.policy_hash,
            model_policy_id=self.policy.policy_id,
            model_policy_version=self.policy.policy_version,
            model_policy_hash=self.policy.policy_hash,
            primary=primary,
            fallback=fallback if maximum_fallback_calls else None,
            maximum_fallback_calls=maximum_fallback_calls,
        )

    def _binding(
        self,
        declaration: EconomyModelDeclaration,
        workload_class: str,
    ) -> Gate2EconomyProviderBinding:
        return Gate2EconomyProviderBinding(
            provider_profile_id=declaration.provider_profile_id,
            exact_model_id=declaration.exact_model_id,
            estimated_maximum_operation_cost_usd=_decimal_text(
                self._maximum_operation_cost(
                    declaration,
                    workload_class,
                )
            ),
        )

    def _maximum_operation_cost(
        self,
        declaration: EconomyModelDeclaration,
        workload_class: str,
    ) -> Decimal:
        workload = self.policy.workload(workload_class)
        return (
            Decimal(workload.maximum_estimated_input_tokens)
            * Decimal(declaration.cost.input_usd_per_million)
            + Decimal(workload.maximum_output_tokens)
            * Decimal(declaration.cost.output_usd_per_million)
        ) / Decimal(1_000_000)


def _normalized(values: Iterable[str] | None) -> tuple[str, ...] | None:
    if values is None:
        return None
    normalized = tuple(
        dict.fromkeys(str(value or "").strip() for value in values)
    )
    if not normalized or any(not value for value in normalized):
        raise Gate2EconomyProviderSelectionError(
            "economy_runtime_provider_allowlist_invalid",
            "Runtime provider allowlist contains an empty value",
        )
    return normalized


def _decimal_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001")), "f")
