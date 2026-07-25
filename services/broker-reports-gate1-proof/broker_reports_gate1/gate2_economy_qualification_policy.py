from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

from .gate2_economy_model_policy import (
    ECONOMY_WORKLOAD_CLASSES,
    Gate2EconomyModelPolicyFactory,
    Gate2EconomyModelPolicySnapshot,
)
from .gate2_economy_provider_selection import (
    Gate2EconomyProviderSelectionFactory,
)
from .gate2_economy_workload_policy import (
    Gate2EconomyWorkloadPolicyFactory,
    Gate2EconomyWorkloadPolicySnapshot,
)


FACTORY_REQUIRED = (
    "Gate2EconomyQualificationPolicyFactory.create is the only "
    "qualification authorization policy entrypoint"
)
FORBIDDEN = (
    "Qualification authorization must not accept aliases, omit receipt "
    "identity fields, enable paid tools, fallback or repair, or activate "
    "a production workload allowlist"
)

QUALIFICATION_POLICY_SCHEMA_VERSION = (
    "broker_reports_gate2_economy_qualification_policy_v1"
)
QUALIFICATION_AUTHORIZATION_SCHEMA_VERSION = (
    "broker_reports_gate2_economy_qualification_authorization_v1"
)
QUALIFICATION_RECEIPT_IDENTITY_FIELDS = (
    "provider_route_revision",
    "input_contract_version",
    "output_contract_version",
    "prompt_version",
    "adapter_projection_revision",
    "canonical_validator_revision",
)


class Gate2EconomyQualificationPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Gate2EconomyQualificationContractIdentity:
    provider_route_revision: str
    input_contract_version: str
    output_contract_version: str
    prompt_version: str
    adapter_projection_revision: str
    canonical_validator_revision: str

    def to_dict(self) -> dict[str, str]:
        return {
            field: str(getattr(self, field))
            for field in QUALIFICATION_RECEIPT_IDENTITY_FIELDS
        }


@dataclass(frozen=True)
class Gate2EconomyQualificationAuthorization:
    workload_class: str
    exact_model_id: str
    provider_profile_id: str
    model_policy_version: str
    model_policy_hash: str
    workload_policy_version: str
    workload_policy_hash: str
    qualification_policy_hash: str
    reasoning_policy: str
    receipt_identity: Gate2EconomyQualificationContractIdentity
    authorization_identity_sha256: str

    def safe_receipt(self) -> dict[str, object]:
        return {
            "schema_version": QUALIFICATION_AUTHORIZATION_SCHEMA_VERSION,
            "workload_class": self.workload_class,
            "exact_model_id": self.exact_model_id,
            "provider_profile_id": self.provider_profile_id,
            "model_policy_version": self.model_policy_version,
            "model_policy_hash": self.model_policy_hash,
            "workload_policy_version": self.workload_policy_version,
            "workload_policy_hash": self.workload_policy_hash,
            "qualification_policy_hash": self.qualification_policy_hash,
            "reasoning_policy": self.reasoning_policy,
            "paid_tools_allowed": False,
            "fallback_calls_allowed": 0,
            "repair_attempts_allowed": 0,
            "receipt_identity": self.receipt_identity.to_dict(),
            "authorization_identity_sha256": (self.authorization_identity_sha256),
        }


class Gate2EconomyQualificationPolicyFactory:
    def __init__(
        self,
        *,
        model_policy: Gate2EconomyModelPolicySnapshot | None = None,
        workload_policy: Gate2EconomyWorkloadPolicySnapshot | None = None,
    ) -> None:
        self.model_policy = model_policy
        self.workload_policy = workload_policy

    def create(self) -> "Gate2EconomyQualificationPolicy":
        model_policy = self.model_policy or Gate2EconomyModelPolicyFactory().create()
        workload_policy = (
            self.workload_policy
            or Gate2EconomyWorkloadPolicyFactory(model_policy=model_policy).create()
        )
        if (
            workload_policy.model_policy_id != model_policy.policy_id
            or workload_policy.model_policy_version != model_policy.policy_version
            or workload_policy.model_policy_hash != model_policy.policy_hash
        ):
            _fail(
                "economy_qualification_policy_binding_mismatch",
                "Qualification requires an exactly bound workload and "
                "model policy pair",
            )
        production_admissions = {
            workload: workload_policy.production_allowlist(workload)
            for workload in ECONOMY_WORKLOAD_CLASSES
        }
        if any(production_admissions.values()):
            _fail(
                "economy_qualification_production_admission_not_empty",
                "Qualification-only policy requires empty production admissions",
            )
        material = _snapshot_material(
            model_policy=model_policy,
            workload_policy=workload_policy,
        )
        qualification_policy_hash = _sha256_json(material)
        return Gate2EconomyQualificationPolicy(
            model_policy=model_policy,
            workload_policy=workload_policy,
            qualification_policy_hash=qualification_policy_hash,
        )


class Gate2EconomyQualificationPolicy:
    def __init__(
        self,
        *,
        model_policy: Gate2EconomyModelPolicySnapshot,
        workload_policy: Gate2EconomyWorkloadPolicySnapshot,
        qualification_policy_hash: str,
    ) -> None:
        self.model_policy = model_policy
        self.workload_policy = workload_policy
        self.qualification_policy_hash = qualification_policy_hash

    def snapshot(self) -> dict[str, object]:
        return {
            **_snapshot_material(
                model_policy=self.model_policy,
                workload_policy=self.workload_policy,
            ),
            "qualification_policy_hash": self.qualification_policy_hash,
        }

    def authorize(
        self,
        *,
        workload_class: str,
        exact_model_id: str,
        provider_profile_id: str,
        receipt_identity: Gate2EconomyQualificationContractIdentity,
    ) -> Gate2EconomyQualificationAuthorization:
        identity = receipt_identity.to_dict()
        if set(identity) != set(QUALIFICATION_RECEIPT_IDENTITY_FIELDS) or any(
            not isinstance(value, str) or not value.strip()
            for value in identity.values()
        ):
            _fail(
                "economy_qualification_receipt_identity_incomplete",
                "Every workload-specific qualification identity field is required",
            )
        selection = (
            Gate2EconomyProviderSelectionFactory(
                policy=self.model_policy,
                workload_policy=self.workload_policy,
            )
            .create()
            .select_qualification_candidate(
                workload_class=workload_class,
                model_id=exact_model_id,
                provider_profile_id=provider_profile_id,
            )
        )
        if (
            selection.primary.exact_model_id != exact_model_id
            or selection.primary.provider_profile_id != provider_profile_id
            or selection.fallback is not None
        ):
            _fail(
                "economy_qualification_selection_invalid",
                "Qualification selection must contain one exact candidate "
                "and no fallback",
            )
        declaration = self.model_policy.model(exact_model_id)
        material = {
            "schema_version": QUALIFICATION_AUTHORIZATION_SCHEMA_VERSION,
            "workload_class": workload_class,
            "exact_model_id": exact_model_id,
            "provider_profile_id": provider_profile_id,
            "model_policy_version": self.model_policy.policy_version,
            "model_policy_hash": self.model_policy.policy_hash,
            "workload_policy_version": self.workload_policy.policy_version,
            "workload_policy_hash": self.workload_policy.policy_hash,
            "qualification_policy_hash": self.qualification_policy_hash,
            "reasoning_policy": declaration.reasoning_policy,
            "paid_tools_allowed": False,
            "fallback_calls_allowed": 0,
            "repair_attempts_allowed": 0,
            "receipt_identity": identity,
        }
        return Gate2EconomyQualificationAuthorization(
            workload_class=workload_class,
            exact_model_id=exact_model_id,
            provider_profile_id=provider_profile_id,
            model_policy_version=self.model_policy.policy_version,
            model_policy_hash=self.model_policy.policy_hash,
            workload_policy_version=self.workload_policy.policy_version,
            workload_policy_hash=self.workload_policy.policy_hash,
            qualification_policy_hash=self.qualification_policy_hash,
            reasoning_policy=declaration.reasoning_policy,
            receipt_identity=receipt_identity,
            authorization_identity_sha256=_sha256_json(material),
        )


def _snapshot_material(
    *,
    model_policy: Gate2EconomyModelPolicySnapshot,
    workload_policy: Gate2EconomyWorkloadPolicySnapshot,
) -> dict[str, object]:
    return {
        "schema_version": QUALIFICATION_POLICY_SCHEMA_VERSION,
        "scope": "qualification_only",
        "model_policy": {
            "policy_id": model_policy.policy_id,
            "policy_version": model_policy.policy_version,
            "policy_schema_version": model_policy.policy_schema_version,
            "policy_hash": model_policy.policy_hash,
        },
        "workload_policy": {
            "policy_id": workload_policy.policy_id,
            "policy_version": workload_policy.policy_version,
            "policy_schema_version": (workload_policy.policy_schema_version),
            "policy_hash": workload_policy.policy_hash,
        },
        "model_controls": {
            declaration.exact_model_id: {
                "provider_profile_id": declaration.provider_profile_id,
                "reasoning_policy": declaration.reasoning_policy,
                "paid_tools_allowed": declaration.paid_tools_allowed,
            }
            for declaration in model_policy.models
        },
        "workload_routes": {
            route.workload_class: {
                "qualification_candidate_exact_model_ids": list(
                    route.qualification_candidate_ids
                ),
                "production_admissions": list(route.production_model_ids),
            }
            for route in workload_policy.routes
        },
        "qualification_controls": {
            "receipt_identity_fields": list(QUALIFICATION_RECEIPT_IDENTITY_FIELDS),
            "fallback_calls_allowed": 0,
            "repair_attempts_allowed": 0,
            "paid_tools_allowed": False,
        },
    }


def _sha256_json(value: Mapping[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str, message: str) -> None:
    raise Gate2EconomyQualificationPolicyError(code, message)
