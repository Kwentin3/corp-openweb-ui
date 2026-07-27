from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_contract import (
    FinancialSemanticRoleContract,
    FinancialSemanticTypeContract,
    Gate2FinancialSemanticContractError,
    Gate2FinancialSemanticContractFactory,
    Gate2FinancialSemanticContractSnapshot,
)
from .gate2_financial_semantic_v6_bundle import (
    FinancialEvidenceBundleSourceValue,
    Gate2FinancialEvidenceBundle,
    Gate2FinancialEvidenceBundleError,
    validate_financial_evidence_bundle,
)
from .gate2_financial_semantic_v6_typed_option import (
    Gate2FinancialTypedOption,
    Gate2FinancialTypedOptionError,
    Gate2FinancialTypedOptionFactory,
    validate_financial_typed_option,
)
from .gate2_financial_evidence_materialization import (
    Gate2FinancialEvidenceSourcePackage,
)


CANDIDATE_COMPILATION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_candidate_compilation_v1"
)
CANDIDATE_COMPILATION_POLICY_VERSION = (
    "broker_reports_gate2_candidate_records_by_construction_v1"
)

FACTORY_REQUIRED = (
    "Gate2FinancialCandidateCompilerFactory.create is the only V6 "
    "Evidence-Bundle-to-Typed-Options compilation entrypoint"
)
FORBIDDEN = (
    "The compiler must not inspect source literals or visible labels, use "
    "financial dictionaries, branch on concrete type IDs, call a model, "
    "repair ambiguity or emit an option that did not pass the canonical "
    "typed-option factory"
)

_CANDIDATE_LEVEL_OPTION_ERRORS = frozenset(
    {
        "financial_typed_option_binding_ref_duplicate",
        "financial_typed_option_cardinality_unrepresentable",
        "financial_typed_option_dimension_requirement_unsatisfied",
        "financial_typed_option_materialization_failed",
    }
)


class Gate2FinancialCandidateCompilerError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialCandidateCompilationBlock:
    association_ref: str
    input_type_id: str
    blocked_required_roles: tuple[str, ...]
    reason_code: str


@dataclass(frozen=True)
class Gate2FinancialCandidateCompilation:
    schema_version: str
    policy_version: str
    evidence_bundle_id: str
    evidence_bundle_integrity_hash: str
    semantic_pack_id: str
    semantic_pack_version: str
    semantic_pack_integrity_sha256: str
    typed_options: tuple[Gate2FinancialTypedOption, ...]
    blocked_bindings: tuple[FinancialCandidateCompilationBlock, ...]
    integrity_hash: str

    def to_private_dict(self) -> dict[str, Any]:
        return {
            **_compilation_payload_without_integrity(self),
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "evidence_bundle_id_sha256": hashlib.sha256(
                self.evidence_bundle_id.encode("utf-8")
            ).hexdigest(),
            "evidence_bundle_integrity_hash": (self.evidence_bundle_integrity_hash),
            "semantic_pack_id": self.semantic_pack_id,
            "semantic_pack_version": self.semantic_pack_version,
            "semantic_pack_integrity_sha256": (self.semantic_pack_integrity_sha256),
            "typed_options_total": len(self.typed_options),
            "blocked_bindings_total": len(self.blocked_bindings),
            "blocked_required_roles_total": sum(
                len(item.blocked_required_roles) for item in self.blocked_bindings
            ),
            "source_literals_inspected": False,
            "visible_labels_inspected": False,
            "financial_word_rules_total": 0,
            "type_specific_branches_total": 0,
            "provider_calls_total": 0,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class _BindingAttempt:
    role_bindings: dict[str, str | None] | None
    blocked_required_roles: tuple[str, ...]
    reason_code: str | None


class Gate2FinancialCandidateCompilerFactory:
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
    ) -> Gate2FinancialCandidateCompilation:
        return self._compile(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
        )

    def _compile(
        self,
        *,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
    ) -> Gate2FinancialCandidateCompilation:
        _validate_bundle(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
        )
        semantic_contract = _semantic_contract(self.registry)
        type_contracts = tuple(
            sorted(
                (
                    item
                    for item in semantic_contract.type_contracts
                    if evidence_bundle.source_family_id
                    in item.compatible_source_families
                ),
                key=lambda item: item.input_type_id,
            )
        )
        association_refs = tuple(
            sorted({value.association_ref for value in evidence_bundle.source_values})
        )
        values_by_association = {
            association_ref: tuple(
                value
                for value in evidence_bundle.source_values
                if value.association_ref == association_ref
            )
            for association_ref in association_refs
        }
        option_factory = Gate2FinancialTypedOptionFactory(registry=self.registry)
        options: list[Gate2FinancialTypedOption] = []
        blocks: list[FinancialCandidateCompilationBlock] = []
        for association_ref in association_refs:
            association_values = values_by_association[association_ref]
            for type_contract in type_contracts:
                attempt = _compile_bindings(
                    type_contract=type_contract,
                    values=association_values,
                )
                if attempt.role_bindings is None:
                    blocks.append(
                        FinancialCandidateCompilationBlock(
                            association_ref=association_ref,
                            input_type_id=type_contract.input_type_id,
                            blocked_required_roles=(attempt.blocked_required_roles),
                            reason_code=str(attempt.reason_code),
                        )
                    )
                    continue
                try:
                    option = option_factory.create(
                        evidence_bundle=evidence_bundle,
                        source_package=source_package,
                        input_type_id=type_contract.input_type_id,
                        role_bindings=attempt.role_bindings,
                    )
                except Gate2FinancialTypedOptionError as exc:
                    if exc.code not in _CANDIDATE_LEVEL_OPTION_ERRORS:
                        raise
                    blocks.append(
                        FinancialCandidateCompilationBlock(
                            association_ref=association_ref,
                            input_type_id=type_contract.input_type_id,
                            blocked_required_roles=(),
                            reason_code=exc.code,
                        )
                    )
                    continue
                options.append(option)

        ordered_options = tuple(sorted(options, key=lambda item: item.typed_option_id))
        option_ids = tuple(item.typed_option_id for item in ordered_options)
        if len(option_ids) != len(set(option_ids)):
            _fail("financial_candidate_compiler_option_duplicate")
        ordered_blocks = tuple(
            sorted(
                blocks,
                key=lambda item: (
                    item.association_ref,
                    item.input_type_id,
                    item.reason_code,
                    item.blocked_required_roles,
                ),
            )
        )
        material = {
            "schema_version": CANDIDATE_COMPILATION_SCHEMA_VERSION,
            "policy_version": CANDIDATE_COMPILATION_POLICY_VERSION,
            "evidence_bundle_id": evidence_bundle.bundle_id,
            "evidence_bundle_integrity_hash": evidence_bundle.integrity_hash,
            "semantic_pack_id": semantic_contract.pack_id,
            "semantic_pack_version": semantic_contract.semantic_version,
            "semantic_pack_integrity_sha256": (semantic_contract.integrity_sha256),
            "typed_options": [item.to_private_dict() for item in ordered_options],
            "blocked_bindings": [_block_payload(item) for item in ordered_blocks],
        }
        return Gate2FinancialCandidateCompilation(
            schema_version=CANDIDATE_COMPILATION_SCHEMA_VERSION,
            policy_version=CANDIDATE_COMPILATION_POLICY_VERSION,
            evidence_bundle_id=evidence_bundle.bundle_id,
            evidence_bundle_integrity_hash=evidence_bundle.integrity_hash,
            semantic_pack_id=semantic_contract.pack_id,
            semantic_pack_version=semantic_contract.semantic_version,
            semantic_pack_integrity_sha256=(semantic_contract.integrity_sha256),
            typed_options=ordered_options,
            blocked_bindings=ordered_blocks,
            integrity_hash=sha256_json(material),
        )


def validate_financial_candidate_compilation(
    *,
    compilation: Gate2FinancialCandidateCompilation,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(compilation, Gate2FinancialCandidateCompilation):
        _fail("financial_candidate_compilation_invalid")
    expected = Gate2FinancialCandidateCompilerFactory(registry=registry)._compile(
        evidence_bundle=evidence_bundle,
        source_package=source_package,
    )
    if compilation != expected:
        _fail("financial_candidate_compilation_integrity_invalid")
    for option in compilation.typed_options:
        validate_financial_typed_option(
            option=option,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            registry=registry,
        )


def _compile_bindings(
    *,
    type_contract: FinancialSemanticTypeContract,
    values: tuple[FinancialEvidenceBundleSourceValue, ...],
) -> _BindingAttempt:
    role_contracts = {item.role_id: item for item in type_contract.role_contracts}
    for role_id in type_contract.required_roles:
        if role_contracts[role_id].cardinality != "one":
            return _BindingAttempt(
                role_bindings=None,
                blocked_required_roles=(role_id,),
                reason_code="candidate_compiler_cardinality_unrepresentable",
            )
    for role_id in type_contract.optional_roles:
        if role_contracts[role_id].cardinality != "zero_or_one":
            return _BindingAttempt(
                role_bindings=None,
                blocked_required_roles=(),
                reason_code="candidate_compiler_cardinality_unrepresentable",
            )

    bindings: dict[str, str | None] = {
        role_id: None
        for role_id in (
            *type_contract.required_roles,
            *type_contract.optional_roles,
        )
    }
    blocked: list[str] = []
    required_selections: dict[str, FinancialEvidenceBundleSourceValue] = {}
    for role_id in type_contract.required_roles:
        selection = _required_selection(
            role_contract=role_contracts[role_id],
            values=values,
        )
        if selection is None:
            blocked.append(role_id)
        else:
            required_selections[role_id] = selection

    selected_refs = [value.source_value_ref for value in required_selections.values()]
    duplicate_refs = {ref for ref in selected_refs if selected_refs.count(ref) > 1}
    if duplicate_refs:
        blocked.extend(
            role_id
            for role_id, value in required_selections.items()
            if value.source_value_ref in duplicate_refs
        )
    if blocked:
        return _BindingAttempt(
            role_bindings=None,
            blocked_required_roles=tuple(sorted(set(blocked))),
            reason_code="candidate_compiler_required_binding_ambiguous",
        )
    for role_id, value in required_selections.items():
        bindings[role_id] = value.source_value_ref

    used_refs = set(selected_refs)
    optional_proposals: dict[
        str,
        list[tuple[str, int]],
    ] = {}
    optional_roles_by_type: dict[str, int] = {}
    for role_id in type_contract.optional_roles:
        value_type = role_contracts[role_id].value_type
        optional_roles_by_type[value_type] = (
            optional_roles_by_type.get(value_type, 0) + 1
        )
    for role_id in type_contract.optional_roles:
        role_contract = role_contracts[role_id]
        candidates = tuple(
            value
            for value in values
            if value.value_type == role_contract.value_type
            and value.source_value_ref not in used_refs
        )
        proposal = _optional_selection(
            role_contract=role_contract,
            candidates=candidates,
            same_type_roles=optional_roles_by_type[role_contract.value_type],
        )
        if proposal is None:
            continue
        value, score = proposal
        optional_proposals.setdefault(value.source_value_ref, []).append(
            (role_id, score)
        )
    for source_value_ref, proposals in optional_proposals.items():
        if len(proposals) == 1:
            bindings[proposals[0][0]] = source_value_ref
            continue
        highest = max(score for _, score in proposals)
        winners = [role_id for role_id, score in proposals if score == highest]
        if highest > 0 and len(winners) == 1:
            bindings[winners[0]] = source_value_ref
    return _BindingAttempt(
        role_bindings=bindings,
        blocked_required_roles=(),
        reason_code=None,
    )


def _required_selection(
    *,
    role_contract: FinancialSemanticRoleContract,
    values: tuple[FinancialEvidenceBundleSourceValue, ...],
) -> FinancialEvidenceBundleSourceValue | None:
    candidates = tuple(
        value for value in values if value.value_type == role_contract.value_type
    )
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return None
    scores = tuple(
        (
            _structural_selector_score(
                role_id=role_contract.role_id,
                value=value,
            ),
            value,
        )
        for value in candidates
    )
    highest = max(score for score, _ in scores)
    winners = tuple(value for score, value in scores if score == highest)
    if highest <= 0 or len(winners) != 1:
        return None
    return winners[0]


def _optional_selection(
    *,
    role_contract: FinancialSemanticRoleContract,
    candidates: tuple[FinancialEvidenceBundleSourceValue, ...],
    same_type_roles: int,
) -> tuple[FinancialEvidenceBundleSourceValue, int] | None:
    if not candidates:
        return None
    scored = tuple(
        (
            _structural_selector_score(
                role_id=role_contract.role_id,
                value=value,
            ),
            value,
        )
        for value in candidates
    )
    highest = max(score for score, _ in scored)
    winners = tuple(value for score, value in scored if score == highest)
    if len(winners) != 1:
        return None
    if highest <= 0 and (len(candidates) != 1 or same_type_roles != 1):
        return None
    return winners[0], highest


def _structural_selector_score(
    *,
    role_id: str,
    value: FinancialEvidenceBundleSourceValue,
) -> int:
    selector = _authoritative_selector(value)
    if selector is None:
        return 0
    return len(
        set(_identifier_tokens(role_id)).intersection(_identifier_tokens(selector))
    )


def _authoritative_selector(
    value: FinancialEvidenceBundleSourceValue,
) -> str | None:
    if value.association_kind == "deterministic_reference":
        return value.source_value_ref.rsplit(":", maxsplit=1)[-1]
    return value.column_meaning


def _identifier_tokens(value: str) -> tuple[str, ...]:
    normalized = "".join(
        character.casefold() if character.isalnum() else " " for character in value
    )
    return tuple(part for part in normalized.split() if part)


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
        raise Gate2FinancialCandidateCompilerError(
            "financial_candidate_compiler_evidence_bundle_invalid"
        ) from exc


def _semantic_contract(
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> Gate2FinancialSemanticContractSnapshot:
    try:
        return Gate2FinancialSemanticContractFactory(registry=registry).create()
    except (
        AttributeError,
        Gate2FinancialSemanticContractError,
    ) as exc:
        raise Gate2FinancialCandidateCompilerError(
            "financial_candidate_compiler_semantic_pack_invalid"
        ) from exc


def _compilation_payload_without_integrity(
    compilation: Gate2FinancialCandidateCompilation,
) -> dict[str, Any]:
    return {
        "schema_version": compilation.schema_version,
        "policy_version": compilation.policy_version,
        "evidence_bundle_id": compilation.evidence_bundle_id,
        "evidence_bundle_integrity_hash": (compilation.evidence_bundle_integrity_hash),
        "semantic_pack_id": compilation.semantic_pack_id,
        "semantic_pack_version": compilation.semantic_pack_version,
        "semantic_pack_integrity_sha256": (compilation.semantic_pack_integrity_sha256),
        "typed_options": [item.to_private_dict() for item in compilation.typed_options],
        "blocked_bindings": [
            _block_payload(item) for item in compilation.blocked_bindings
        ],
    }


def _block_payload(
    block: FinancialCandidateCompilationBlock,
) -> dict[str, Any]:
    return {
        "association_ref": block.association_ref,
        "input_type_id": block.input_type_id,
        "blocked_required_roles": list(block.blocked_required_roles),
        "reason_code": block.reason_code,
    }


def _fail(code: str) -> None:
    raise Gate2FinancialCandidateCompilerError(code)
