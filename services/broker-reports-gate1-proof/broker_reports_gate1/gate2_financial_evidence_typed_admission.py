from __future__ import annotations

import copy
import hashlib
import re
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
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_source_context import (
    FinancialEvidenceVisibleValueContext,
    financial_evidence_visible_value_contexts,
)


TYPED_ADMISSION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_typed_admission_v1"
)
TYPED_ADMISSION_POLICY_VERSION = (
    "gate2_financial_typed_admission_policy_v1"
)

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceTypedAdmissionFactory.create is the only "
    "successor typed-branch admission authority"
)
FORBIDDEN = (
    "Typed admission must not call a model, infer a default type, expose "
    "source literals in its receipt, admit conflicting hypotheses or repair "
    "a typed response after the model call"
)

_CASH_TYPE_ID = "cash_balance_snapshot_v1"
_PRINTED_TYPE_ID = "printed_financial_metric_v1"
_CASH_SIGNAL_RE = re.compile(
    r"(?:\bcash\b|денежн\w*\s+средств\w*|остат\w*\s+денежн\w*)",
    re.IGNORECASE,
)
_PRINTED_SIGNAL_RE = re.compile(
    r"(?:\btotal\b|\bsubtotal\b|\bsummary\b|итог\w*|всего|подытог\w*)",
    re.IGNORECASE,
)
_PRINTED_ROW_ROLES = frozenset(
    {
        "summary",
        "summary_row",
        "subtotal",
        "subtotal_row",
        "total",
        "total_row",
    }
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
    semantic_context_values_total: int
    association_groups_total: int
    amount_candidates_total: int
    date_candidates_total: int
    currency_candidates_total: int
    semantic_label_candidates_total: int
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
            "reason_codes": list(self.reason_codes),
            "evidence_identity_hash": self.evidence_identity_hash,
            "source_values_total": self.source_values_total,
            "semantic_context_values_total": (
                self.semantic_context_values_total
            ),
            "association_groups_total": self.association_groups_total,
            "amount_candidates_total": self.amount_candidates_total,
            "date_candidates_total": self.date_candidates_total,
            "currency_candidates_total": self.currency_candidates_total,
            "semantic_label_candidates_total": (
                self.semantic_label_candidates_total
            ),
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
            "reason_codes": list(self.reason_codes),
            "evidence_identity_hash": self.evidence_identity_hash,
            "source_values_total": self.source_values_total,
            "semantic_context_values_total": (
                self.semantic_context_values_total
            ),
            "association_groups_total": self.association_groups_total,
            "amount_candidates_total": self.amount_candidates_total,
            "date_candidates_total": self.date_candidates_total,
            "currency_candidates_total": self.currency_candidates_total,
            "semantic_label_candidates_total": (
                self.semantic_label_candidates_total
            ),
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
        candidate_type_ids = tuple(
            declaration.input_type_id
            for declaration in self.registry.declarations
            if declaration.lifecycle == "active"
            and source_family_id
            in declaration.compatible_source_families
        )
        contexts = financial_evidence_visible_value_contexts(
            packages=packages
        )
        values = {
            item.source_value_ref: item for item in source_values
        }
        candidate_by_ref = {
            item.source_value_ref: item for item in candidates
        }
        if set(values) != set(candidate_by_ref):
            _fail("typed_admission_candidate_identity_mismatch")
        semantic_contexts = tuple(
            contexts[ref]
            for ref in sorted(contexts)
            if ref in values
        )
        evidence_identity_hash = sha256_json(
            {
                "source_scope_ref": source_scope_ref,
                "source_family_id": source_family_id,
                "candidate_type_ids": list(candidate_type_ids),
                "contexts": [
                    item.typed_admission_identity_payload()
                    for item in semantic_contexts
                ],
                "routing_hints": [
                    copy.deepcopy(item)
                    for package in packages
                    for item in (
                        (package.get("typed_admission_routing_hints") or [])
                    )
                ],
            }
        )
        role_refs = _role_refs(candidates=candidates)
        amounts = role_refs.get("amount", ())
        dates = role_refs.get("as_of_date", ())
        currencies = role_refs.get("currency", ())
        semantic_labels = tuple(
            ref
            for ref in role_refs.get("source_label", ())
            if ref in contexts
        )
        reasons: set[str] = set()
        admitted_candidates: list[str] = []
        if not candidate_type_ids:
            reasons.add("source_family_has_no_registry_candidate")
        if len(amounts) != 1:
            reasons.add(
                "ambiguous_amount_candidates"
                if len(amounts) > 1
                else "required_amount_missing"
            )
        if len(dates) != 1:
            reasons.add(
                "ambiguous_date_candidates"
                if len(dates) > 1
                else "required_date_missing"
            )
        if len(currencies) != 1:
            reasons.add(
                "ambiguous_currency_candidates"
                if len(currencies) > 1
                else "required_currency_missing"
            )
        structural_roles_unique = (
            len(amounts) == 1
            and len(dates) == 1
            and len(currencies) == 1
        )
        cash_signal_refs = tuple(
            ref
            for ref in semantic_labels
            if _cash_signal(contexts[ref])
        )
        printed_signal_refs = tuple(
            ref
            for ref in contexts
            if _printed_signal(contexts[ref])
        )
        if (
            _CASH_TYPE_ID in candidate_type_ids
            and structural_roles_unique
            and len(cash_signal_refs) == 1
            and _same_association_group(
                refs=(
                    amounts[0],
                    dates[0],
                    currencies[0],
                    cash_signal_refs[0],
                ),
                contexts=contexts,
            )
        ):
            admitted_candidates.append(_CASH_TYPE_ID)
        elif _CASH_TYPE_ID in candidate_type_ids:
            reasons.add("cash_positive_discriminator_not_proven")
        if (
            _PRINTED_TYPE_ID in candidate_type_ids
            and structural_roles_unique
            and printed_signal_refs
            and _same_association_group(
                refs=(
                    amounts[0],
                    dates[0],
                    currencies[0],
                    printed_signal_refs[0],
                ),
                contexts=contexts,
            )
        ):
            admitted_candidates.append(_PRINTED_TYPE_ID)
        elif _PRINTED_TYPE_ID in candidate_type_ids:
            reasons.add("printed_positive_discriminator_not_proven")
        if len(admitted_candidates) > 1:
            admitted_type_ids: tuple[str, ...] = ()
            reasons.add("conflicting_positive_discriminators")
        elif len(admitted_candidates) == 1:
            admitted_type_ids = tuple(admitted_candidates)
            reasons.add(
                "unique_positive_discriminator_proven:"
                + admitted_type_ids[0]
            )
        else:
            admitted_type_ids = ()
            reasons.add("no_safe_typed_admission")
        association_groups = {
            item.association_group
            for item in semantic_contexts
            if item.association_group
        }
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
            "reason_codes": sorted(reasons),
            "evidence_identity_hash": evidence_identity_hash,
            "source_values_total": len(source_values),
            "semantic_context_values_total": len(semantic_contexts),
            "association_groups_total": len(association_groups),
            "amount_candidates_total": len(amounts),
            "date_candidates_total": len(dates),
            "currency_candidates_total": len(currencies),
            "semantic_label_candidates_total": len(semantic_labels),
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
            reason_codes=tuple(sorted(reasons)),
            evidence_identity_hash=evidence_identity_hash,
            source_values_total=len(source_values),
            semantic_context_values_total=len(semantic_contexts),
            association_groups_total=len(association_groups),
            amount_candidates_total=len(amounts),
            date_candidates_total=len(dates),
            currency_candidates_total=len(currencies),
            semantic_label_candidates_total=len(semantic_labels),
            integrity_hash=sha256_json(material),
        )
        validate_typed_admission(
            payload=result.to_dict(),
            registry=self.registry,
            source_scope_ref=source_scope_ref,
        )
        return result


def validate_typed_admission(
    *,
    payload: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    source_scope_ref: str,
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
    expected_candidate_type_ids = [
        declaration.input_type_id
        for declaration in registry.declarations
        if declaration.lifecycle == "active"
        and payload.get("source_family_id")
        in declaration.compatible_source_families
    ]
    if (
        not isinstance(candidate_type_ids, list)
        or candidate_type_ids != sorted(set(candidate_type_ids))
        or candidate_type_ids != expected_candidate_type_ids
        or not set(candidate_type_ids) <= active_ids
        or not isinstance(admitted_type_ids, list)
        or admitted_type_ids != sorted(set(admitted_type_ids))
        or len(admitted_type_ids) > 1
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
        or payload.get("contains_source_literals") is not False
        or payload.get("contains_source_value_refs") is not False
        or payload.get("provider_calls_total") != 0
        or payload.get("post_response_conversion") is not False
    ):
        _fail("typed_admission_policy_invalid")
    reason_codes = payload["reason_codes"]
    if admitted_type_ids:
        expected_reason = (
            "unique_positive_discriminator_proven:"
            + admitted_type_ids[0]
        )
        if (
            expected_reason not in reason_codes
            or "no_safe_typed_admission" in reason_codes
            or "conflicting_positive_discriminators" in reason_codes
        ):
            _fail("typed_admission_positive_proof_invalid")
    elif not {
        "no_safe_typed_admission",
        "conflicting_positive_discriminators",
    } & set(reason_codes):
        _fail("typed_admission_negative_proof_invalid")
    for field in (
        "source_values_total",
        "semantic_context_values_total",
        "association_groups_total",
        "amount_candidates_total",
        "date_candidates_total",
        "currency_candidates_total",
        "semantic_label_candidates_total",
    ):
        value = payload.get(field)
        if not isinstance(value, int) or value < 0:
            _fail("typed_admission_count_invalid")
    if (
        not isinstance(payload.get("evidence_identity_hash"), str)
        or len(payload["evidence_identity_hash"]) != 64
    ):
        _fail("typed_admission_evidence_identity_invalid")


def _role_refs(
    *,
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
) -> dict[str, tuple[str, ...]]:
    roles: dict[str, list[str]] = {}
    for candidate in candidates:
        for role_id in candidate.allowed_roles:
            roles.setdefault(role_id, []).append(candidate.source_value_ref)
    return {
        role_id: tuple(sorted(refs))
        for role_id, refs in sorted(roles.items())
    }


def _cash_signal(
    context: FinancialEvidenceVisibleValueContext,
) -> bool:
    return bool(
        _CASH_SIGNAL_RE.search(context.literal_value)
        or _CASH_SIGNAL_RE.search(context.column_meaning)
        or _CASH_SIGNAL_RE.search(context.visible_label)
    )


def _printed_signal(
    context: FinancialEvidenceVisibleValueContext,
) -> bool:
    return bool(
        context.row_role.strip().lower() in _PRINTED_ROW_ROLES
        or _PRINTED_SIGNAL_RE.search(context.literal_value)
        or _PRINTED_SIGNAL_RE.search(context.column_meaning)
        or _PRINTED_SIGNAL_RE.search(context.visible_label)
    )


def _same_association_group(
    *,
    refs: tuple[str, ...],
    contexts: dict[str, FinancialEvidenceVisibleValueContext],
) -> bool:
    groups = {
        contexts[ref].association_group
        for ref in refs
        if ref in contexts and contexts[ref].association_group
    }
    return len(groups) == 1 and all(ref in contexts for ref in refs)


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceTypedAdmissionError(code)
