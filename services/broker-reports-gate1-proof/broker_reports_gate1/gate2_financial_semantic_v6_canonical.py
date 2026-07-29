from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

from .gate2_financial_evidence_decision import (
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContract,
    Gate2FinancialEvidenceDecisionContractFactory,
    Gate2FinancialEvidenceDecisionError,
    UNCLASSIFIED_REASON_CODES,
    UnclassifiedFinancialInputDecision,
)
from .gate2_financial_evidence_materialization import (
    Gate2FinancialEvidenceSourcePackage,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_contract import (
    Gate2FinancialSemanticContractError,
    Gate2FinancialSemanticContractFactory,
)
from .gate2_financial_semantic_v6_bundle import (
    Gate2FinancialEvidenceBundle,
    Gate2FinancialEvidenceBundleError,
    validate_financial_evidence_bundle,
)


FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6CanonicalDecisionContractFactory.create is "
    "the only V6 Evidence-Bundle-to-canonical-decision-contract adapter"
)
FORBIDDEN = (
    "V6 callers must not construct canonical candidate roles independently, "
    "branch on concrete type IDs or accept provider-created refs or roles"
)


class Gate2FinancialSemanticV6CanonicalError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate2FinancialSemanticV6CanonicalDecisionContractFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        allowed_type_ids: tuple[str, ...],
    ) -> Gate2FinancialEvidenceDecisionContract:
        return self._create(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            allowed_type_ids=allowed_type_ids,
            context_v2_1_candidate=False,
        )

    def create_context_v2_1_candidate(
        self,
        *,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        allowed_type_ids: tuple[str, ...],
    ) -> Gate2FinancialEvidenceDecisionContract:
        return self._create(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            allowed_type_ids=allowed_type_ids,
            context_v2_1_candidate=True,
        )

    def _create(
        self,
        *,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        allowed_type_ids: tuple[str, ...],
        context_v2_1_candidate: bool,
    ) -> Gate2FinancialEvidenceDecisionContract:
        _validate_bundle(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
        )
        if (
            not isinstance(allowed_type_ids, tuple)
            or len(allowed_type_ids) != len(set(allowed_type_ids))
            or any(not isinstance(item, str) or not item for item in allowed_type_ids)
        ):
            _fail("financial_semantic_v6_canonical_types_invalid")
        semantic_contract = _semantic_contract(self.registry)
        compatible_type_ids = {
            item.input_type_id
            for item in semantic_contract.type_contracts
            if evidence_bundle.source_family_id in item.compatible_source_families
        }
        if not set(allowed_type_ids) <= compatible_type_ids:
            _fail("financial_semantic_v6_canonical_type_incompatible")

        roles_by_value_type: dict[str, set[str]] = {}
        for type_contract in semantic_contract.type_contracts:
            for role_contract in type_contract.role_contracts:
                roles_by_value_type.setdefault(
                    role_contract.value_type,
                    set(),
                ).add(role_contract.role_id)
        candidates = []
        for value in evidence_bundle.source_values:
            allowed_roles = tuple(
                sorted(roles_by_value_type.get(value.value_type, set()))
            )
            if not allowed_roles:
                _fail("financial_semantic_v6_canonical_role_missing")
            candidates.append(
                FinancialEvidenceValueCandidate(
                    source_value_ref=value.source_value_ref,
                    source_ref=value.source_ref,
                    value_type=value.value_type,
                    allowed_roles=allowed_roles,
                )
            )
        try:
            decision_factory = Gate2FinancialEvidenceDecisionContractFactory(
                registry=self.registry,
                package=FinancialEvidenceDecisionPackage(
                    source_scope_ref=evidence_bundle.source_scope_ref,
                    source_family_id=evidence_bundle.source_family_id,
                    candidates=tuple(candidates),
                    allowed_type_ids=tuple(sorted(allowed_type_ids)),
                ),
            )
            result = decision_factory.create()
            if context_v2_1_candidate:
                result = _context_v2_1_candidate_contract(result)
        except Gate2FinancialEvidenceDecisionError as exc:
            raise Gate2FinancialSemanticV6CanonicalError(
                "financial_semantic_v6_canonical_contract_invalid"
            ) from exc
        if result.eligible_type_ids != tuple(
            declaration.input_type_id
            for declaration in self.registry.declarations
            if declaration.input_type_id in set(allowed_type_ids)
            and evidence_bundle.source_family_id
            in declaration.compatible_source_families
        ):
            _fail("financial_semantic_v6_canonical_types_mismatch")
        return result


class _Gate2FinancialSemanticV6ContextV21DecisionContract(
    Gate2FinancialEvidenceDecisionContract
):
    def canonical_schema(self) -> dict[str, Any]:
        schema = super().canonical_schema()
        variants = (
            schema.get("properties", {})
            .get("decision", {})
            .get("anyOf")
        )
        matches = []
        if isinstance(variants, list):
            for variant in variants:
                properties = (
                    variant.get("properties")
                    if isinstance(variant, dict)
                    else None
                )
                if (
                    isinstance(properties, dict)
                    and properties.get("disposition", {}).get("enum")
                    == ["unclassified_financial_input"]
                ):
                    matches.append(properties)
        if len(matches) != 1:
            _fail("financial_semantic_v6_context_v2_1_contract_invalid")
        reason_schema = matches[0].get("reason_code")
        if (
            not isinstance(reason_schema, dict)
            or reason_schema.get("enum")
            != list(UNCLASSIFIED_REASON_CODES)
        ):
            _fail("financial_semantic_v6_context_v2_1_contract_invalid")
        reason_schema["enum"] = list(_context_v2_1_reason_codes())
        return schema

    def _parse_unclassified(
        self,
        decision: dict[str, Any],
    ) -> UnclassifiedFinancialInputDecision:
        reason_code = (
            decision.get("reason_code")
            if isinstance(decision, dict)
            else None
        )
        if reason_code != "single_registry_type_no_safe_record":
            return super()._parse_unclassified(decision)
        structural_probe = copy.deepcopy(decision)
        structural_probe["reason_code"] = UNCLASSIFIED_REASON_CODES[0]
        validated = super()._parse_unclassified(structural_probe)
        return replace(validated, reason_code=reason_code)


def _context_v2_1_candidate_contract(
    base: Gate2FinancialEvidenceDecisionContract,
) -> Gate2FinancialEvidenceDecisionContract:
    if _context_v2_1_reason_codes() != (
        "no_registry_type",
        "single_registry_type_no_safe_record",
        "ambiguous_registry_type",
    ):
        _fail("financial_semantic_v6_context_v2_1_contract_invalid")
    return _Gate2FinancialSemanticV6ContextV21DecisionContract(
        registry=base.registry,
        package=base.package,
        eligible_type_ids=base.eligible_type_ids,
    )


def _context_v2_1_reason_codes() -> tuple[str, ...]:
    from .gate2_financial_semantic_v6_choice import (
        CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES,
    )

    return CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES


def _validate_bundle(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
) -> None:
    try:
        validate_financial_evidence_bundle(
            bundle=evidence_bundle,
            source_package=source_package,
        )
    except Gate2FinancialEvidenceBundleError as exc:
        raise Gate2FinancialSemanticV6CanonicalError(
            "financial_semantic_v6_canonical_bundle_invalid"
        ) from exc


def _semantic_contract(
    registry: Gate2FinancialEvidenceRegistrySnapshot,
):
    try:
        return Gate2FinancialSemanticContractFactory(registry=registry).create()
    except (
        AttributeError,
        Gate2FinancialSemanticContractError,
    ) as exc:
        raise Gate2FinancialSemanticV6CanonicalError(
            "financial_semantic_v6_canonical_pack_invalid"
        ) from exc


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6CanonicalError(code)
