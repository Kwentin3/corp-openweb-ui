from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from .gate2_economy_model_policy import (
    ECONOMY_WORKLOAD_CLASSES,
    V3_ALLOWED_EXACT_MODEL_IDS,
    WORKLOAD_GATE2_DOMAIN,
    WORKLOAD_GATE2_FINANCIAL_CHECKSUM,
    WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
    WORKLOAD_GATE2_SOURCE,
    Gate2EconomyModelPolicyFactory,
    Gate2EconomyModelPolicySnapshot,
)


FACTORY_REQUIRED = (
    "Gate2EconomyWorkloadPolicyFactory.create is the only code-owned "
    "workload candidate and production admission policy entrypoint"
)
FORBIDDEN = (
    "General model status, aliases, runtime config and another workload "
    "receipt must not activate or expand a production workload allowlist"
)

POLICY_ID = "broker_reports_gate2_economy_workload_policy_v2"
POLICY_VERSION = "1.5.0"
POLICY_SCHEMA_VERSION = "broker_reports_gate2_economy_workload_policy_v2"


class Gate2EconomyWorkloadPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EconomyWorkloadProductionAdmission:
    exact_model_id: str
    provider_profile_id: str
    qualification_receipt_sha256: str
    actual_corpus_receipt_sha256: str
    full_scope_receipt_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "exact_model_id": self.exact_model_id,
            "provider_profile_id": self.provider_profile_id,
            "qualification_receipt_sha256": (
                self.qualification_receipt_sha256
            ),
            "actual_corpus_receipt_sha256": (
                self.actual_corpus_receipt_sha256
            ),
            "full_scope_receipt_sha256": self.full_scope_receipt_sha256,
        }


@dataclass(frozen=True)
class EconomyWorkloadRoutePolicy:
    workload_class: str
    primary_candidate_exact_model_id: str
    secondary_candidate_exact_model_id: str | None
    maximum_fallback_calls_per_operation: int
    diagnostic_candidate_exact_model_ids: tuple[str, ...] = ()
    production_admissions: tuple[
        EconomyWorkloadProductionAdmission, ...
    ] = ()

    @property
    def target_candidate_ids(self) -> tuple[str, ...]:
        return (
            (self.primary_candidate_exact_model_id,)
            if self.secondary_candidate_exact_model_id is None
            else (
                self.primary_candidate_exact_model_id,
                self.secondary_candidate_exact_model_id,
            )
        )

    @property
    def qualification_candidate_ids(self) -> tuple[str, ...]:
        return (
            *self.target_candidate_ids,
            *self.diagnostic_candidate_exact_model_ids,
        )

    @property
    def production_model_ids(self) -> tuple[str, ...]:
        return tuple(
            item.exact_model_id for item in self.production_admissions
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "workload_class": self.workload_class,
            "primary_candidate_exact_model_id": (
                self.primary_candidate_exact_model_id
            ),
            "secondary_candidate_exact_model_id": (
                self.secondary_candidate_exact_model_id
            ),
            "maximum_fallback_calls_per_operation": (
                self.maximum_fallback_calls_per_operation
            ),
            "diagnostic_candidate_exact_model_ids": list(
                self.diagnostic_candidate_exact_model_ids
            ),
            "production_admissions": [
                item.to_dict() for item in self.production_admissions
            ],
        }


@dataclass(frozen=True)
class Gate2EconomyWorkloadPolicySnapshot:
    policy_id: str
    policy_version: str
    policy_schema_version: str
    model_policy_id: str
    model_policy_version: str
    model_policy_hash: str
    routes: tuple[EconomyWorkloadRoutePolicy, ...]
    policy_hash: str

    def route(self, workload_class: str) -> EconomyWorkloadRoutePolicy:
        for route in self.routes:
            if route.workload_class == workload_class:
                return route
        raise Gate2EconomyWorkloadPolicyError(
            "economy_workload_route_unknown",
            "The requested Gate 2 workload route is not registered",
        )

    def qualification_candidate_ids(
        self,
        workload_class: str,
    ) -> tuple[str, ...]:
        return self.route(workload_class).qualification_candidate_ids

    def assert_qualification_candidate(
        self,
        *,
        workload_class: str,
        model_id: str,
        model_policy: Gate2EconomyModelPolicySnapshot,
    ) -> str:
        requested = str(model_id or "").strip()
        try:
            resolution = model_policy.resolve_model_id(requested)
        except ValueError as exc:
            raise Gate2EconomyWorkloadPolicyError(
                getattr(exc, "code", "economy_model_not_registered"),
                str(exc),
            ) from exc
        if (
            resolution.alias_used
            or requested != resolution.exact_model_id
            or resolution.exact_model_id
            not in self.qualification_candidate_ids(workload_class)
        ):
            raise Gate2EconomyWorkloadPolicyError(
                "economy_workload_qualification_candidate_forbidden",
                "Qualification requires an exact model ID in the "
                "code-owned workload candidate matrix",
            )
        return resolution.exact_model_id

    def production_allowlist(
        self,
        workload_class: str,
    ) -> tuple[str, ...]:
        return self.route(workload_class).production_model_ids

    def narrow_runtime_allowlist(
        self,
        *,
        workload_class: str,
        requested_model_ids: Iterable[str] | None,
    ) -> tuple[str, ...]:
        allowed = self.production_allowlist(workload_class)
        if requested_model_ids is None:
            return allowed
        requested = tuple(
            dict.fromkeys(
                str(model_id or "").strip()
                for model_id in requested_model_ids
            )
        )
        if (
            not requested
            or any(not model_id for model_id in requested)
            or not set(requested).issubset(set(allowed))
        ):
            raise Gate2EconomyWorkloadPolicyError(
                "economy_runtime_allowlist_expansion_forbidden",
                "Runtime configuration may only narrow the exact workload "
                "production allowlist",
            )
        return tuple(
            model_id for model_id in allowed if model_id in set(requested)
        )

    def provider_allowlist(
        self,
        workload_class: str,
    ) -> dict[str, tuple[str, ...]]:
        route = self.route(workload_class)
        result: dict[str, list[str]] = {}
        for admission in route.production_admissions:
            result.setdefault(admission.provider_profile_id, []).append(
                admission.exact_model_id
            )
        return {
            provider: tuple(model_ids)
            for provider, model_ids in sorted(result.items())
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_schema_version": self.policy_schema_version,
            "model_policy_id": self.model_policy_id,
            "model_policy_version": self.model_policy_version,
            "model_policy_hash": self.model_policy_hash,
            "routes": [item.to_dict() for item in self.routes],
            "policy_hash": self.policy_hash,
        }


ECONOMY_WORKLOAD_ROUTES = (
    EconomyWorkloadRoutePolicy(
        workload_class=WORKLOAD_GATE2_SOURCE,
        primary_candidate_exact_model_id=(
            "models/gemini-3.1-flash-lite"
        ),
        secondary_candidate_exact_model_id=(
            "models/gemini-3.5-flash-lite"
        ),
        maximum_fallback_calls_per_operation=1,
    ),
    EconomyWorkloadRoutePolicy(
        workload_class=WORKLOAD_GATE2_DOMAIN,
        primary_candidate_exact_model_id=(
            "models/gemini-3.1-flash-lite"
        ),
        secondary_candidate_exact_model_id=(
            "models/gemini-3.5-flash-lite"
        ),
        maximum_fallback_calls_per_operation=1,
    ),
    EconomyWorkloadRoutePolicy(
        workload_class=WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
        primary_candidate_exact_model_id=(
            "gpt-5.4-nano-2026-03-17"
        ),
        secondary_candidate_exact_model_id=None,
        maximum_fallback_calls_per_operation=1,
        diagnostic_candidate_exact_model_ids=(
            "models/gemini-3.1-flash-lite",
            "models/gemini-3.5-flash-lite",
        ),
    ),
    EconomyWorkloadRoutePolicy(
        workload_class=WORKLOAD_GATE2_FINANCIAL_CHECKSUM,
        primary_candidate_exact_model_id=(
            "claude-haiku-4-5-20251001"
        ),
        secondary_candidate_exact_model_id=(
            "gpt-5.4-nano-2026-03-17"
        ),
        maximum_fallback_calls_per_operation=0,
        diagnostic_candidate_exact_model_ids=(
            "models/gemini-3.1-flash-lite",
            "models/gemini-3.5-flash-lite",
        ),
    ),
)


class Gate2EconomyWorkloadPolicyFactory:
    def __init__(
        self,
        *,
        model_policy: Gate2EconomyModelPolicySnapshot | None = None,
        routes: tuple[EconomyWorkloadRoutePolicy, ...] | None = None,
    ) -> None:
        self.model_policy = model_policy
        self.routes = routes

    def create(self) -> Gate2EconomyWorkloadPolicySnapshot:
        model_policy = (
            self.model_policy or Gate2EconomyModelPolicyFactory().create()
        )
        routes = (
            self.routes
            if self.routes is not None
            else ECONOMY_WORKLOAD_ROUTES
        )
        validate_economy_workload_policy_inputs(
            model_policy=model_policy,
            routes=routes,
        )
        material = {
            "policy_id": POLICY_ID,
            "policy_version": POLICY_VERSION,
            "policy_schema_version": POLICY_SCHEMA_VERSION,
            "model_policy_id": model_policy.policy_id,
            "model_policy_version": model_policy.policy_version,
            "model_policy_hash": model_policy.policy_hash,
            "routes": [item.to_dict() for item in routes],
        }
        policy_hash = hashlib.sha256(
            json.dumps(
                material,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return Gate2EconomyWorkloadPolicySnapshot(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            policy_schema_version=POLICY_SCHEMA_VERSION,
            model_policy_id=model_policy.policy_id,
            model_policy_version=model_policy.policy_version,
            model_policy_hash=model_policy.policy_hash,
            routes=routes,
            policy_hash=policy_hash,
        )


def validate_economy_workload_policy_inputs(
    *,
    model_policy: Gate2EconomyModelPolicySnapshot,
    routes: tuple[EconomyWorkloadRoutePolicy, ...],
) -> None:
    if model_policy.policy_version != POLICY_VERSION:
        raise Gate2EconomyWorkloadPolicyError(
            "economy_workload_model_policy_version_mismatch",
            "Workload and model policy versions must be identical",
        )
    workload_ids = [route.workload_class for route in routes]
    if (
        len(workload_ids) != len(set(workload_ids))
        or set(workload_ids) != set(ECONOMY_WORKLOAD_CLASSES)
    ):
        raise Gate2EconomyWorkloadPolicyError(
            "economy_workload_route_set_invalid",
            "Each Gate 2 workload route must be declared exactly once",
        )
    registered_exact_ids = {
        declaration.exact_model_id for declaration in model_policy.models
    }
    if registered_exact_ids != set(V3_ALLOWED_EXACT_MODEL_IDS):
        raise Gate2EconomyWorkloadPolicyError(
            "economy_workload_model_set_invalid",
            "The workload policy must bind exactly the four v3 models",
        )
    for route in routes:
        candidate_ids = route.qualification_candidate_ids
        target_candidate_ids = route.target_candidate_ids
        if (
            len(candidate_ids) != len(set(candidate_ids))
            or not set(candidate_ids).issubset(registered_exact_ids)
            or route.maximum_fallback_calls_per_operation not in {0, 1}
        ):
            raise Gate2EconomyWorkloadPolicyError(
                "economy_workload_candidate_route_invalid",
                "Workload candidates or fallback policy are invalid",
            )
        expected_provider_ids = {
            model_id: model_policy.model(model_id).provider_profile_id
            for model_id in candidate_ids
        }
        production_ids = route.production_model_ids
        if (
            len(production_ids) != len(set(production_ids))
            or not set(production_ids).issubset(
                set(target_candidate_ids)
            )
            or production_ids
            != tuple(
                model_id
                for model_id in target_candidate_ids
                if model_id in set(production_ids)
            )
            or len(production_ids)
            > 1 + route.maximum_fallback_calls_per_operation
        ):
            raise Gate2EconomyWorkloadPolicyError(
                "economy_workload_production_admission_invalid",
                "Production admissions must preserve candidate order and "
                "the workload fallback bound",
            )
        for admission in route.production_admissions:
            if (
                admission.provider_profile_id
                != expected_provider_ids[admission.exact_model_id]
                or not _is_sha256(admission.qualification_receipt_sha256)
                or not _is_sha256(admission.actual_corpus_receipt_sha256)
                or not _is_sha256(admission.full_scope_receipt_sha256)
            ):
                raise Gate2EconomyWorkloadPolicyError(
                    "economy_workload_production_receipt_invalid",
                    "Production admission requires exact provider and "
                    "qualification, actual-corpus and full-scope receipts",
                )


def _is_sha256(value: str) -> bool:
    return (
        len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
