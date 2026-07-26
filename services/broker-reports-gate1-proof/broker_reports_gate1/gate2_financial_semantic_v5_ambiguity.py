from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .gate2_financial_semantic_v5_projection import (
    Gate2FinancialSemanticV5Projection,
    validate_financial_semantic_v5_projection,
)


V5_BINDING_AMBIGUITY_SCHEMA_VERSION = (
    "broker_reports_gate2_binding_ambiguity_guard_v1"
)
V5_BINDING_AMBIGUITY_POLICY_VERSION = (
    "broker_reports_gate2_generic_binding_ambiguity_policy_v1"
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5AmbiguityGuardFactory.create is the only V5 "
    "typed-branch ambiguity guard entrypoint"
)
FORBIDDEN = (
    "The guard must not inspect literals, labels, financial meanings, type-"
    "specific predicates or expected outcomes, and must not repair a typed "
    "response after the model call"
)


class Gate2FinancialSemanticV5AmbiguityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2StructuralBindingCandidate:
    source_value_ref: str
    association_unit_id: str
    value_type: str
    allowed_roles: tuple[str, ...]
    authoritative_selector: str | None = None
    model_visible_association: str | None = None


@dataclass(frozen=True)
class Gate2FinancialSemanticV5AmbiguityResult:
    schema_version: str
    policy_version: str
    policy_hash: str
    guard_input_hash: str
    available_type_cards: tuple[dict[str, Any], ...]
    blocked_type_ids: tuple[str, ...]
    blocked_required_roles: dict[str, tuple[str, ...]]
    post_response_repair_allowed: bool

    def typed_branch_available(self, input_type_id: str) -> bool:
        return any(
            card["input_type_id"] == input_type_id
            for card in self.available_type_cards
        )


class Gate2FinancialSemanticV5AmbiguityGuardFactory:
    def create(
        self,
        *,
        projection: Gate2FinancialSemanticV5Projection,
        candidates: tuple[Gate2StructuralBindingCandidate, ...],
    ) -> Gate2FinancialSemanticV5AmbiguityResult:
        _validate_inputs(projection=projection, candidates=candidates)
        available = []
        blocked: dict[str, tuple[str, ...]] = {}
        for card in projection.type_cards:
            ambiguous_roles = tuple(
                role["role_id"]
                for role in card["required_roles"]
                if _required_role_is_ambiguous(
                    role_id=role["role_id"],
                    value_type=role["value_type"],
                    candidates=candidates,
                )
            )
            if ambiguous_roles:
                blocked[card["input_type_id"]] = ambiguous_roles
            else:
                available.append(copy.deepcopy(card))
        return Gate2FinancialSemanticV5AmbiguityResult(
            schema_version=V5_BINDING_AMBIGUITY_SCHEMA_VERSION,
            policy_version=V5_BINDING_AMBIGUITY_POLICY_VERSION,
            policy_hash=_policy_hash(),
            guard_input_hash=_sha256_json(
                {
                    "projection_hash": projection.projection_hash,
                    "candidates": [
                        asdict(item)
                        for item in sorted(
                            candidates,
                            key=lambda item: item.source_value_ref,
                        )
                    ],
                }
            ),
            available_type_cards=tuple(available),
            blocked_type_ids=tuple(sorted(blocked)),
            blocked_required_roles={
                key: blocked[key] for key in sorted(blocked)
            },
            post_response_repair_allowed=False,
        )


def structurally_equivalent_for_required_role(
    *,
    role_id: str,
    left: Gate2StructuralBindingCandidate,
    right: Gate2StructuralBindingCandidate,
) -> bool:
    _validate_candidate(left)
    _validate_candidate(right)
    if (
        not isinstance(role_id, str)
        or not role_id
        or left.source_value_ref == right.source_value_ref
    ):
        return False
    if (
        role_id not in left.allowed_roles
        or role_id not in right.allowed_roles
        or left.association_unit_id != right.association_unit_id
        or left.value_type != right.value_type
    ):
        return False
    selector_distinguishes = (
        left.authoritative_selector
        != right.authoritative_selector
    )
    visible_association_distinguishes = (
        left.model_visible_association
        != right.model_visible_association
    )
    return not (
        selector_distinguishes or visible_association_distinguishes
    )


def _required_role_is_ambiguous(
    *,
    role_id: str,
    value_type: str,
    candidates: tuple[Gate2StructuralBindingCandidate, ...],
) -> bool:
    eligible = [
        item
        for item in candidates
        if role_id in item.allowed_roles and item.value_type == value_type
    ]
    if not eligible:
        _fail("financial_semantic_v5_required_role_candidate_missing")
    return any(
        structurally_equivalent_for_required_role(
            role_id=role_id,
            left=eligible[left_index],
            right=eligible[right_index],
        )
        for left_index in range(len(eligible))
        for right_index in range(left_index + 1, len(eligible))
    )


def _validate_inputs(
    *,
    projection: Any,
    candidates: Any,
) -> None:
    if not isinstance(projection, Gate2FinancialSemanticV5Projection):
        _fail("financial_semantic_v5_ambiguity_projection_invalid")
    validate_financial_semantic_v5_projection(projection.payload)
    if (
        not isinstance(candidates, tuple)
        or not candidates
        or len(candidates) > 64
    ):
        _fail("financial_semantic_v5_ambiguity_candidates_invalid")
    for item in candidates:
        _validate_candidate(item)
    refs = [item.source_value_ref for item in candidates]
    if len(refs) != len(set(refs)):
        _fail("financial_semantic_v5_ambiguity_candidate_duplicate")


def _validate_candidate(candidate: Any) -> None:
    if (
        not isinstance(candidate, Gate2StructuralBindingCandidate)
        or not isinstance(candidate.source_value_ref, str)
        or not candidate.source_value_ref
        or not isinstance(candidate.association_unit_id, str)
        or not candidate.association_unit_id
        or not isinstance(candidate.value_type, str)
        or not candidate.value_type
        or not isinstance(candidate.allowed_roles, tuple)
        or not candidate.allowed_roles
        or any(
            not isinstance(role, str) or not role
            for role in candidate.allowed_roles
        )
        or len(candidate.allowed_roles) != len(set(candidate.allowed_roles))
        or candidate.authoritative_selector is not None
        and (
            not isinstance(candidate.authoritative_selector, str)
            or not candidate.authoritative_selector
        )
        or candidate.model_visible_association is not None
        and (
            not isinstance(candidate.model_visible_association, str)
            or not candidate.model_visible_association
        )
    ):
        _fail("financial_semantic_v5_ambiguity_candidate_invalid")


def _policy_hash() -> str:
    return _sha256_json(
        {
            "schema_version": V5_BINDING_AMBIGUITY_SCHEMA_VERSION,
            "policy_version": V5_BINDING_AMBIGUITY_POLICY_VERSION,
            "equivalence_dimensions": [
                "same_association_unit",
                "same_value_type",
                "same_required_role_feasibility",
                "no_distinct_authoritative_selector",
                "no_distinct_model_visible_association",
            ],
            "typed_branch_action": "remove_before_model_call",
            "post_response_repair_allowed": False,
        }
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5AmbiguityError(code)
