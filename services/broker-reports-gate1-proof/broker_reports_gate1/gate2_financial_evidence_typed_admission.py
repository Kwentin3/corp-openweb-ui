from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

from .gate2_financial_evidence_decision import (
    FinancialEvidenceValueCandidate,
)
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceAuthoritativeSourceValue,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    FinancialEvidenceInputTypeDeclaration,
    Gate2FinancialEvidenceRegistrySnapshot,
)


TYPED_ADMISSION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_typed_admission_v2"
)
TYPED_ADMISSION_POLICY_VERSION = (
    "gate2_financial_generic_structural_filter_v1"
)

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceTypedAdmissionFactory.create is the only "
    "successor structural type-filter authority"
)
FORBIDDEN = (
    "The structural filter must not inspect financial words, headings, "
    "labels or row roles, call a model, infer a semantic type, expose source "
    "literals in its receipt or repair a response after the model call"
)


class Gate2FinancialEvidenceTypedAdmissionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialEvidenceTypedAdmission:
    source_scope_ref: str
    registry_version: str
    registry_hash: str
    source_family_id: str
    candidate_type_ids: tuple[str, ...]
    admitted_type_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    evidence_identity_hash: str
    source_values_total: int
    candidate_values_total: int
    package_member_values_total: int
    required_roles_evaluated_total: int
    infeasible_required_roles_total: int
    integrity_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TYPED_ADMISSION_SCHEMA_VERSION,
            "policy_version": TYPED_ADMISSION_POLICY_VERSION,
            "source_scope_ref": self.source_scope_ref,
            "registry_version": self.registry_version,
            "registry_hash": self.registry_hash,
            "source_family_id": self.source_family_id,
            "candidate_type_ids": list(self.candidate_type_ids),
            "admitted_type_ids": list(self.admitted_type_ids),
            "typed_branch_available": bool(self.admitted_type_ids),
            "filter_kind": "generic_structural",
            "semantic_selection_owner": "llm",
            "reason_codes": list(self.reason_codes),
            "evidence_identity_hash": self.evidence_identity_hash,
            "source_values_total": self.source_values_total,
            "candidate_values_total": self.candidate_values_total,
            "package_member_values_total": (
                self.package_member_values_total
            ),
            "required_roles_evaluated_total": (
                self.required_roles_evaluated_total
            ),
            "infeasible_required_roles_total": (
                self.infeasible_required_roles_total
            ),
            "financial_language_predicates_total": 0,
            "type_specific_admission_branches_total": 0,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "provider_calls_total": 0,
            "post_response_conversion": False,
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": TYPED_ADMISSION_SCHEMA_VERSION,
            "policy_version": TYPED_ADMISSION_POLICY_VERSION,
            "source_scope_ref_sha256": hashlib.sha256(
                self.source_scope_ref.encode("utf-8")
            ).hexdigest(),
            "registry_version": self.registry_version,
            "registry_hash": self.registry_hash,
            "candidate_type_ids": list(self.candidate_type_ids),
            "admitted_type_ids": list(self.admitted_type_ids),
            "typed_branch_available": bool(self.admitted_type_ids),
            "filter_kind": "generic_structural",
            "semantic_selection_owner": "llm",
            "reason_codes": list(self.reason_codes),
            "evidence_identity_hash": self.evidence_identity_hash,
            "source_values_total": self.source_values_total,
            "candidate_values_total": self.candidate_values_total,
            "package_member_values_total": (
                self.package_member_values_total
            ),
            "required_roles_evaluated_total": (
                self.required_roles_evaluated_total
            ),
            "infeasible_required_roles_total": (
                self.infeasible_required_roles_total
            ),
            "financial_language_predicates_total": 0,
            "type_specific_admission_branches_total": 0,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "provider_calls_total": 0,
            "post_response_conversion": False,
            "integrity_hash": self.integrity_hash,
        }


class Gate2FinancialEvidenceTypedAdmissionFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        source_scope_ref: str,
        source_family_id: str,
        source_values: tuple[
            FinancialEvidenceAuthoritativeSourceValue,
            ...,
        ],
        candidates: tuple[FinancialEvidenceValueCandidate, ...],
        gate1_packages: Iterable[dict[str, Any]],
    ) -> Gate2FinancialEvidenceTypedAdmission:
        packages = tuple(copy.deepcopy(tuple(gate1_packages)))
        if (
            not source_scope_ref
            or not source_family_id
            or not source_values
            or not candidates
            or not packages
        ):
            _fail("typed_admission_input_invalid")
        candidate_type_ids = _candidate_type_ids(
            registry=self.registry,
            source_family_id=source_family_id,
        )
        package_member_values_total = _validate_package_membership(
            source_values=source_values,
            candidates=candidates,
            packages=packages,
        )
        (
            admitted_type_ids,
            required_roles_evaluated_total,
            infeasible_required_roles_total,
        ) = _structurally_eligible_type_ids(
            registry=self.registry,
            source_family_id=source_family_id,
            candidates=candidates,
        )
        reason_codes = _reason_codes(
            candidate_type_ids=candidate_type_ids,
            admitted_type_ids=admitted_type_ids,
            infeasible_required_roles_total=(
                infeasible_required_roles_total
            ),
        )
        evidence_identity_hash = sha256_json(
            {
                "source_scope_ref": source_scope_ref,
                "source_family_id": source_family_id,
                "candidate_type_ids": list(candidate_type_ids),
                "admitted_type_ids": list(admitted_type_ids),
                "candidate_shapes": [
                    {
                        "source_value_ref": item.source_value_ref,
                        "source_ref": item.source_ref,
                        "value_type": item.value_type,
                        "allowed_roles": list(item.allowed_roles),
                    }
                    for item in candidates
                ],
                "package_member_values_total": (
                    package_member_values_total
                ),
            }
        )
        material = {
            "schema_version": TYPED_ADMISSION_SCHEMA_VERSION,
            "policy_version": TYPED_ADMISSION_POLICY_VERSION,
            "source_scope_ref": source_scope_ref,
            "registry_version": self.registry.registry_version,
            "registry_hash": self.registry.registry_hash,
            "source_family_id": source_family_id,
            "candidate_type_ids": list(candidate_type_ids),
            "admitted_type_ids": list(admitted_type_ids),
            "typed_branch_available": bool(admitted_type_ids),
            "filter_kind": "generic_structural",
            "semantic_selection_owner": "llm",
            "reason_codes": list(reason_codes),
            "evidence_identity_hash": evidence_identity_hash,
            "source_values_total": len(source_values),
            "candidate_values_total": len(candidates),
            "package_member_values_total": package_member_values_total,
            "required_roles_evaluated_total": (
                required_roles_evaluated_total
            ),
            "infeasible_required_roles_total": (
                infeasible_required_roles_total
            ),
            "financial_language_predicates_total": 0,
            "type_specific_admission_branches_total": 0,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "provider_calls_total": 0,
            "post_response_conversion": False,
        }
        result = Gate2FinancialEvidenceTypedAdmission(
            source_scope_ref=source_scope_ref,
            registry_version=self.registry.registry_version,
            registry_hash=self.registry.registry_hash,
            source_family_id=source_family_id,
            candidate_type_ids=candidate_type_ids,
            admitted_type_ids=admitted_type_ids,
            reason_codes=reason_codes,
            evidence_identity_hash=evidence_identity_hash,
            source_values_total=len(source_values),
            candidate_values_total=len(candidates),
            package_member_values_total=package_member_values_total,
            required_roles_evaluated_total=(
                required_roles_evaluated_total
            ),
            infeasible_required_roles_total=(
                infeasible_required_roles_total
            ),
            integrity_hash=sha256_json(material),
        )
        validate_typed_admission(
            payload=result.to_dict(),
            registry=self.registry,
            source_scope_ref=source_scope_ref,
            candidates=candidates,
        )
        return result


def validate_typed_admission(
    *,
    payload: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    source_scope_ref: str,
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
) -> None:
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != TYPED_ADMISSION_SCHEMA_VERSION
        or payload.get("policy_version")
        != TYPED_ADMISSION_POLICY_VERSION
        or payload.get("source_scope_ref") != source_scope_ref
        or payload.get("registry_version") != registry.registry_version
        or payload.get("registry_hash") != registry.registry_hash
    ):
        _fail("typed_admission_identity_invalid")
    material = copy.deepcopy(payload)
    integrity_hash = material.pop("integrity_hash", None)
    if integrity_hash != sha256_json(material):
        _fail("typed_admission_integrity_invalid")
    candidate_type_ids = payload.get("candidate_type_ids")
    admitted_type_ids = payload.get("admitted_type_ids")
    active_ids = set(registry.provider_type_enum())
    expected_candidate_type_ids = list(
        _candidate_type_ids(
            registry=registry,
            source_family_id=str(payload.get("source_family_id") or ""),
        )
    )
    (
        expected_admitted_type_ids,
        required_roles_evaluated_total,
        infeasible_required_roles_total,
    ) = _structurally_eligible_type_ids(
        registry=registry,
        source_family_id=str(payload.get("source_family_id") or ""),
        candidates=candidates,
    )
    if (
        not isinstance(candidate_type_ids, list)
        or candidate_type_ids != sorted(set(candidate_type_ids))
        or candidate_type_ids != expected_candidate_type_ids
        or not set(candidate_type_ids) <= active_ids
        or not isinstance(admitted_type_ids, list)
        or admitted_type_ids != sorted(set(admitted_type_ids))
        or admitted_type_ids != list(expected_admitted_type_ids)
        or not set(admitted_type_ids) <= set(candidate_type_ids)
        or payload.get("typed_branch_available")
        is not bool(admitted_type_ids)
    ):
        _fail("typed_admission_types_invalid")
    if (
        not isinstance(payload.get("reason_codes"), list)
        or not payload["reason_codes"]
        or payload["reason_codes"]
        != sorted(set(payload["reason_codes"]))
        or payload["reason_codes"]
        != list(
            _reason_codes(
                candidate_type_ids=tuple(candidate_type_ids),
                admitted_type_ids=tuple(admitted_type_ids),
                infeasible_required_roles_total=(
                    infeasible_required_roles_total
                ),
            )
        )
        or payload.get("filter_kind") != "generic_structural"
        or payload.get("semantic_selection_owner") != "llm"
        or payload.get("financial_language_predicates_total") != 0
        or payload.get("type_specific_admission_branches_total") != 0
        or payload.get("contains_source_literals") is not False
        or payload.get("contains_source_value_refs") is not False
        or payload.get("provider_calls_total") != 0
        or payload.get("post_response_conversion") is not False
    ):
        _fail("typed_admission_policy_invalid")
    for field in (
        "source_values_total",
        "candidate_values_total",
        "package_member_values_total",
        "required_roles_evaluated_total",
        "infeasible_required_roles_total",
    ):
        value = payload.get(field)
        if not isinstance(value, int) or value < 0:
            _fail("typed_admission_count_invalid")
    if (
        payload.get("candidate_values_total") != len(candidates)
        or payload.get("required_roles_evaluated_total")
        != required_roles_evaluated_total
        or payload.get("infeasible_required_roles_total")
        != infeasible_required_roles_total
    ):
        _fail("typed_admission_structural_counts_invalid")
    if (
        not isinstance(payload.get("evidence_identity_hash"), str)
        or len(payload["evidence_identity_hash"]) != 64
    ):
        _fail("typed_admission_evidence_identity_invalid")


def _candidate_type_ids(
    *,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    source_family_id: str,
) -> tuple[str, ...]:
    return tuple(
        declaration.input_type_id
        for declaration in registry.declarations
        if declaration.lifecycle == "active"
        and source_family_id in declaration.compatible_source_families
    )


def _structurally_eligible_type_ids(
    *,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    source_family_id: str,
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
) -> tuple[tuple[str, ...], int, int]:
    eligible: list[str] = []
    required_roles_evaluated_total = 0
    infeasible_required_roles_total = 0
    for declaration in registry.declarations:
        if (
            declaration.lifecycle != "active"
            or source_family_id
            not in declaration.compatible_source_families
        ):
            continue
        missing = _infeasible_required_roles(
            declaration=declaration,
            candidates=candidates,
        )
        required_roles_evaluated_total += len(
            declaration.required_roles
        )
        infeasible_required_roles_total += len(missing)
        if not missing:
            eligible.append(declaration.input_type_id)
    return (
        tuple(eligible),
        required_roles_evaluated_total,
        infeasible_required_roles_total,
    )


def _infeasible_required_roles(
    *,
    declaration: FinancialEvidenceInputTypeDeclaration,
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
) -> tuple[str, ...]:
    specs = {item.role_id: item for item in declaration.role_specs}
    return tuple(
        role_id
        for role_id in declaration.required_roles
        if not any(
            role_id in candidate.allowed_roles
            and candidate.value_type == specs[role_id].value_type
            for candidate in candidates
        )
    )


def _reason_codes(
    *,
    candidate_type_ids: tuple[str, ...],
    admitted_type_ids: tuple[str, ...],
    infeasible_required_roles_total: int,
) -> tuple[str, ...]:
    reasons: set[str] = set()
    if not candidate_type_ids:
        reasons.add("source_family_has_no_registry_candidate")
    if infeasible_required_roles_total:
        reasons.add("required_role_feasibility_excluded_types")
    reasons.add(
        "structurally_eligible_types_available"
        if admitted_type_ids
        else "no_structurally_eligible_types"
    )
    return tuple(sorted(reasons))


def _validate_package_membership(
    *,
    source_values: tuple[
        FinancialEvidenceAuthoritativeSourceValue,
        ...,
    ],
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
    packages: tuple[dict[str, Any], ...],
) -> int:
    values = {
        item.source_value_ref: item for item in source_values
    }
    candidate_by_ref = {
        item.source_value_ref: item for item in candidates
    }
    if (
        len(values) != len(source_values)
        or len(candidate_by_ref) != len(candidates)
        or set(values) != set(candidate_by_ref)
    ):
        _fail("typed_admission_candidate_identity_mismatch")
    package_value_refs = {
        str(ref)
        for package in packages
        for ref in package.get("allowed_source_value_refs") or []
        if ref
    }
    package_evidence_refs = {
        str(ref)
        for package in packages
        for ref in package.get("allowed_evidence_refs") or []
        if ref
    }
    for ref, value in values.items():
        candidate = candidate_by_ref[ref]
        if (
            candidate.source_ref != value.source_ref
            or candidate.value_type != value.value_type
        ):
            _fail("typed_admission_candidate_shape_mismatch")
        if value.value_type == "source_reference":
            if value.source_ref not in package_evidence_refs:
                _fail("typed_admission_reference_membership_invalid")
        elif ref not in package_value_refs:
            _fail("typed_admission_value_membership_invalid")
    return len(values)


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceTypedAdmissionError(code)
