from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_decision import (
    Gate2FinancialEvidenceDecisionContract,
    Gate2FinancialEvidenceDecisionError,
)
from .gate2_financial_evidence_materialization import (
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
    MATERIALIZATION_POLICY_VERSION,
    VALIDATED_DECISION_SCHEMA_VERSION,
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializationError,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceSourcePackage,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import (
    sha256_json,
    validate_dimension_requirements,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_contract import (
    FinancialSemanticTypeContract,
    Gate2FinancialSemanticContractError,
    Gate2FinancialSemanticContractFactory,
    Gate2FinancialSemanticContractSnapshot,
)
from .gate2_financial_semantic_v6_bundle import (
    Gate2FinancialEvidenceBundle,
    Gate2FinancialEvidenceBundleError,
    validate_financial_evidence_bundle,
)
from .gate2_financial_semantic_v6_canonical import (
    Gate2FinancialSemanticV6CanonicalDecisionContractFactory,
    Gate2FinancialSemanticV6CanonicalError,
)


TYPED_OPTION_SCHEMA_VERSION = "broker_reports_gate2_financial_typed_option_v1"
TYPED_OPTION_POLICY_VERSION = (
    "broker_reports_gate2_candidate_records_by_construction_v1"
)
STRUCTURAL_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_typed_option_structural_receipt_v1"
)
MATERIALIZABILITY_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_typed_option_materializability_receipt_v1"
)
TYPED_OPTION_ID_PREFIX = "financial-typed-option:"

FACTORY_REQUIRED = (
    "Gate2FinancialTypedOptionFactory.create is the only V6 fully "
    "materializable typed-option construction entrypoint"
)
FORBIDDEN = (
    "The typed-option factory must not inspect financial words or literals, "
    "branch on concrete type IDs, call a model, accept model-generated refs "
    "or roles, repair bindings or bypass the canonical validator/materializer"
)


class Gate2FinancialTypedOptionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialTypedOptionBinding:
    role_id: str
    source_value_ref: str


@dataclass(frozen=True)
class FinancialTypedOptionStructuralReceipt:
    schema_version: str
    semantic_pack_id: str
    semantic_pack_version: str
    semantic_pack_integrity_sha256: str
    registry_version: str
    registry_hash: str
    bundle_integrity_hash: str
    type_contract_hash: str
    bindings_hash: str
    association_identity_hash: str
    associations_total: int
    required_roles_total: int
    optional_roles_total: int
    bound_roles_total: int
    required_roles_complete: bool
    binding_refs_unique: bool
    status: str
    receipt_hash: str


@dataclass(frozen=True)
class FinancialTypedOptionMaterializabilityReceipt:
    schema_version: str
    validated_decision_schema_version: str
    decision_schema_hash: str
    materialization_schema_version: str
    materialization_policy_version: str
    semantic_pack_integrity_sha256: str
    registry_hash: str
    source_package_integrity_hash: str
    materialized_artifact_hash: str
    materialized_artifact_integrity_hash: str
    typed_input_integrity_hash: str
    typed_inputs_total: int
    unclassified_inputs_total: int
    provider_calls_total: int
    status: str
    receipt_hash: str


@dataclass(frozen=True)
class Gate2FinancialTypedOption:
    schema_version: str
    policy_version: str
    typed_option_id: str
    evidence_bundle_id: str
    evidence_bundle_integrity_hash: str
    input_type_id: str
    required_roles: tuple[str, ...]
    optional_roles: tuple[str, ...]
    role_bindings: tuple[FinancialTypedOptionBinding, ...]
    structural_compatibility_receipt: FinancialTypedOptionStructuralReceipt
    materializability_receipt: FinancialTypedOptionMaterializabilityReceipt
    integrity_hash: str

    def to_private_dict(self) -> dict[str, Any]:
        return {
            **_option_payload_without_integrity(self),
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "typed_option_id": self.typed_option_id,
            "evidence_bundle_id_sha256": hashlib.sha256(
                self.evidence_bundle_id.encode("utf-8")
            ).hexdigest(),
            "evidence_bundle_integrity_hash": (self.evidence_bundle_integrity_hash),
            "input_type_id": self.input_type_id,
            "required_roles_total": len(self.required_roles),
            "optional_roles_total": len(self.optional_roles),
            "bound_roles_total": len(self.role_bindings),
            "required_roles_complete": True,
            "model_generated_refs_total": 0,
            "model_generated_roles_total": 0,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "provider_calls_total": 0,
            "structural_receipt_hash": (
                self.structural_compatibility_receipt.receipt_hash
            ),
            "materializability_receipt_hash": (
                self.materializability_receipt.receipt_hash
            ),
            "integrity_hash": self.integrity_hash,
        }


class Gate2FinancialTypedOptionFactory:
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
        input_type_id: str,
        role_bindings: dict[str, str | None],
    ) -> Gate2FinancialTypedOption:
        _validate_bundle_authority(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
        )
        semantic_contract = _semantic_contract(self.registry)
        type_contract = _exact_type_contract(
            semantic_contract=semantic_contract,
            input_type_id=input_type_id,
            source_family_id=evidence_bundle.source_family_id,
        )
        normalized_bindings = _normalize_bindings(
            evidence_bundle=evidence_bundle,
            type_contract=type_contract,
            role_bindings=role_bindings,
        )
        structural_receipt = _structural_receipt(
            evidence_bundle=evidence_bundle,
            registry=self.registry,
            semantic_contract=semantic_contract,
            type_contract=type_contract,
            bindings=normalized_bindings,
        )
        materializability_receipt = _materializability_receipt(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            registry=self.registry,
            semantic_contract=semantic_contract,
            type_contract=type_contract,
            bindings=normalized_bindings,
            structural_receipt=structural_receipt,
        )
        identity_material = _option_identity_material(
            evidence_bundle=evidence_bundle,
            input_type_id=type_contract.input_type_id,
            required_roles=type_contract.required_roles,
            optional_roles=type_contract.optional_roles,
            bindings=normalized_bindings,
            structural_receipt=structural_receipt,
            materializability_receipt=materializability_receipt,
        )
        typed_option_id = TYPED_OPTION_ID_PREFIX + sha256_json(identity_material)[:32]
        payload = {
            **identity_material,
            "typed_option_id": typed_option_id,
        }
        option = Gate2FinancialTypedOption(
            schema_version=TYPED_OPTION_SCHEMA_VERSION,
            policy_version=TYPED_OPTION_POLICY_VERSION,
            typed_option_id=typed_option_id,
            evidence_bundle_id=evidence_bundle.bundle_id,
            evidence_bundle_integrity_hash=(evidence_bundle.integrity_hash),
            input_type_id=type_contract.input_type_id,
            required_roles=type_contract.required_roles,
            optional_roles=type_contract.optional_roles,
            role_bindings=normalized_bindings,
            structural_compatibility_receipt=structural_receipt,
            materializability_receipt=materializability_receipt,
            integrity_hash=sha256_json(payload),
        )
        validate_financial_typed_option(
            option=option,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            registry=self.registry,
        )
        return option


def validate_financial_typed_option(
    *,
    option: Gate2FinancialTypedOption,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    _validate_bundle_authority(
        evidence_bundle=evidence_bundle,
        source_package=source_package,
    )
    if (
        not isinstance(option, Gate2FinancialTypedOption)
        or option.schema_version != TYPED_OPTION_SCHEMA_VERSION
        or option.policy_version != TYPED_OPTION_POLICY_VERSION
        or option.evidence_bundle_id != evidence_bundle.bundle_id
        or option.evidence_bundle_integrity_hash != evidence_bundle.integrity_hash
    ):
        _fail("financial_typed_option_identity_invalid")
    semantic_contract = _semantic_contract(registry)
    type_contract = _exact_type_contract(
        semantic_contract=semantic_contract,
        input_type_id=option.input_type_id,
        source_family_id=evidence_bundle.source_family_id,
    )
    raw_bindings: dict[str, str | None] = {
        role_id: None
        for role_id in (
            *type_contract.required_roles,
            *type_contract.optional_roles,
        )
    }
    for binding in option.role_bindings:
        if (
            not isinstance(binding, FinancialTypedOptionBinding)
            or binding.role_id not in raw_bindings
            or raw_bindings[binding.role_id] is not None
        ):
            _fail("financial_typed_option_bindings_invalid")
        raw_bindings[binding.role_id] = binding.source_value_ref
    normalized_bindings = _normalize_bindings(
        evidence_bundle=evidence_bundle,
        type_contract=type_contract,
        role_bindings=raw_bindings,
    )
    if (
        option.required_roles != type_contract.required_roles
        or option.optional_roles != type_contract.optional_roles
        or option.role_bindings != normalized_bindings
    ):
        _fail("financial_typed_option_roles_invalid")
    structural_receipt = _structural_receipt(
        evidence_bundle=evidence_bundle,
        registry=registry,
        semantic_contract=semantic_contract,
        type_contract=type_contract,
        bindings=normalized_bindings,
    )
    if option.structural_compatibility_receipt != structural_receipt:
        _fail("financial_typed_option_structural_receipt_invalid")
    materializability_receipt = _materializability_receipt(
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        registry=registry,
        semantic_contract=semantic_contract,
        type_contract=type_contract,
        bindings=normalized_bindings,
        structural_receipt=structural_receipt,
    )
    if option.materializability_receipt != materializability_receipt:
        _fail("financial_typed_option_materializability_receipt_invalid")
    identity_material = _option_identity_material(
        evidence_bundle=evidence_bundle,
        input_type_id=type_contract.input_type_id,
        required_roles=type_contract.required_roles,
        optional_roles=type_contract.optional_roles,
        bindings=normalized_bindings,
        structural_receipt=structural_receipt,
        materializability_receipt=materializability_receipt,
    )
    expected_option_id = TYPED_OPTION_ID_PREFIX + sha256_json(identity_material)[:32]
    payload = {
        **identity_material,
        "typed_option_id": expected_option_id,
    }
    if (
        option.typed_option_id != expected_option_id
        or option.integrity_hash != sha256_json(payload)
    ):
        _fail("financial_typed_option_integrity_invalid")


def _validate_bundle_authority(
    *,
    evidence_bundle: Any,
    source_package: Any,
) -> None:
    try:
        validate_financial_evidence_bundle(
            bundle=evidence_bundle,
            source_package=source_package,
        )
    except Gate2FinancialEvidenceBundleError as exc:
        raise Gate2FinancialTypedOptionError(
            "financial_typed_option_evidence_bundle_invalid"
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
        raise Gate2FinancialTypedOptionError(
            "financial_typed_option_semantic_pack_invalid"
        ) from exc


def _exact_type_contract(
    *,
    semantic_contract: Gate2FinancialSemanticContractSnapshot,
    input_type_id: Any,
    source_family_id: str,
) -> FinancialSemanticTypeContract:
    if not isinstance(input_type_id, str) or not input_type_id:
        _fail("financial_typed_option_type_invalid")
    try:
        result = semantic_contract.type_contract(input_type_id)
    except Gate2FinancialSemanticContractError as exc:
        raise Gate2FinancialTypedOptionError(
            "financial_typed_option_type_not_in_pack"
        ) from exc
    if source_family_id not in result.compatible_source_families:
        _fail("financial_typed_option_source_family_incompatible")
    return result


def _normalize_bindings(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    type_contract: FinancialSemanticTypeContract,
    role_bindings: Any,
) -> tuple[FinancialTypedOptionBinding, ...]:
    expected_roles = {
        *type_contract.required_roles,
        *type_contract.optional_roles,
    }
    if not isinstance(role_bindings, dict) or set(role_bindings) != expected_roles:
        _fail("financial_typed_option_role_set_invalid")
    role_contracts = {item.role_id: item for item in type_contract.role_contracts}
    values = {item.source_value_ref: item for item in evidence_bundle.source_values}
    result: list[FinancialTypedOptionBinding] = []
    seen_refs: set[str] = set()
    for role_id in sorted(expected_roles):
        source_value_ref = role_bindings[role_id]
        role_contract = role_contracts[role_id]
        expected_cardinality = (
            "one" if role_id in type_contract.required_roles else "zero_or_one"
        )
        if role_contract.cardinality != expected_cardinality:
            _fail("financial_typed_option_cardinality_unrepresentable")
        if source_value_ref is None:
            if role_id in type_contract.required_roles:
                _fail("financial_typed_option_required_role_missing")
            continue
        if not isinstance(source_value_ref, str):
            _fail("financial_typed_option_binding_ref_invalid")
        value = values.get(source_value_ref)
        if value is None:
            _fail("financial_typed_option_binding_outside_bundle")
        if value.value_type != role_contract.value_type:
            _fail("financial_typed_option_binding_incompatible")
        if role_contract.source_ref_required and not value.source_ref:
            _fail("financial_typed_option_source_ref_missing")
        if source_value_ref in seen_refs:
            _fail("financial_typed_option_binding_ref_duplicate")
        seen_refs.add(source_value_ref)
        result.append(
            FinancialTypedOptionBinding(
                role_id=role_id,
                source_value_ref=source_value_ref,
            )
        )
    bound_roles = {item.role_id for item in result}
    required_identity_roles = set(type_contract.identity_roles).intersection(
        type_contract.required_roles
    )
    if not required_identity_roles <= bound_roles:
        _fail("financial_typed_option_identity_role_missing")
    association_refs = {
        values[item.source_value_ref].association_ref for item in result
    }
    if len(association_refs) != 1:
        _fail("financial_typed_option_association_ambiguous")
    try:
        validate_dimension_requirements(
            date_period_requirement=(type_contract.date_period_requirement),
            currency_unit_requirement=(type_contract.currency_unit_requirement),
            bound_roles=bound_roles,
        )
    except Gate2FinancialEvidenceMaterializationError as exc:
        raise Gate2FinancialTypedOptionError(
            "financial_typed_option_dimension_requirement_unsatisfied"
        ) from exc
    return tuple(result)


def _structural_receipt(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    semantic_contract: Gate2FinancialSemanticContractSnapshot,
    type_contract: FinancialSemanticTypeContract,
    bindings: tuple[FinancialTypedOptionBinding, ...],
) -> FinancialTypedOptionStructuralReceipt:
    values = {item.source_value_ref: item for item in evidence_bundle.source_values}
    association_refs = tuple(
        sorted({values[item.source_value_ref].association_ref for item in bindings})
    )
    bindings_hash = sha256_json([_binding_payload(item) for item in bindings])
    material = {
        "schema_version": STRUCTURAL_RECEIPT_SCHEMA_VERSION,
        "semantic_pack_id": semantic_contract.pack_id,
        "semantic_pack_version": semantic_contract.semantic_version,
        "semantic_pack_integrity_sha256": (semantic_contract.integrity_sha256),
        "registry_version": registry.registry_version,
        "registry_hash": registry.registry_hash,
        "bundle_integrity_hash": evidence_bundle.integrity_hash,
        "type_contract_hash": sha256_json(_type_contract_payload(type_contract)),
        "bindings_hash": bindings_hash,
        "association_identity_hash": sha256_json(list(association_refs)),
        "associations_total": len(association_refs),
        "required_roles_total": len(type_contract.required_roles),
        "optional_roles_total": len(type_contract.optional_roles),
        "bound_roles_total": len(bindings),
        "required_roles_complete": True,
        "binding_refs_unique": True,
        "status": "compatible",
    }
    return FinancialTypedOptionStructuralReceipt(
        **material,
        receipt_hash=sha256_json(material),
    )


def _materializability_receipt(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    semantic_contract: Gate2FinancialSemanticContractSnapshot,
    type_contract: FinancialSemanticTypeContract,
    bindings: tuple[FinancialTypedOptionBinding, ...],
    structural_receipt: FinancialTypedOptionStructuralReceipt,
) -> FinancialTypedOptionMaterializabilityReceipt:
    contract = _canonical_decision_contract(
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        registry=registry,
        input_type_id=type_contract.input_type_id,
    )
    binding_map: dict[str, str | None] = {
        role_id: None
        for role_id in (
            *type_contract.required_roles,
            *type_contract.optional_roles,
        )
    }
    for binding in bindings:
        binding_map[binding.role_id] = binding.source_value_ref
    canonical_decision = {
        "decision": {
            "disposition": "typed_input",
            "input_type_id": type_contract.input_type_id,
            "value_bindings": binding_map,
            "reason_code": "typed_supported",
        }
    }
    proof_seed = sha256_json(
        {
            "bundle_integrity_hash": evidence_bundle.integrity_hash,
            "input_type_id": type_contract.input_type_id,
            "bindings_hash": structural_receipt.bindings_hash,
            "semantic_pack_integrity_sha256": (semantic_contract.integrity_sha256),
        }
    )[:24]
    execution_metadata = FinancialEvidenceExecutionMetadata(
        execution_ref=f"execution:typed-option-proof:{proof_seed}",
        decision_validation_ref=(f"validation:typed-option-proof:{proof_seed}"),
    )
    try:
        validated = Gate2FinancialEvidenceValidatedDecisionFactory(
            contract=contract
        ).create(canonical_decision)
        artifact = (
            Gate2FinancialEvidenceMaterializerFactory(
                registry=registry,
                source_package=source_package,
                execution_metadata=execution_metadata,
            )
            .create()
            .materialize(validated_decision=validated)
        )
    except (
        Gate2FinancialEvidenceDecisionError,
        Gate2FinancialEvidenceMaterializationError,
    ) as exc:
        raise Gate2FinancialTypedOptionError(
            "financial_typed_option_materialization_failed"
        ) from exc
    typed_inputs = artifact.get("typed_inputs")
    unclassified_inputs = artifact.get("unclassified_inputs")
    if (
        artifact.get("terminal_disposition") != "typed_input"
        or not isinstance(typed_inputs, list)
        or len(typed_inputs) != 1
        or not isinstance(unclassified_inputs, list)
        or unclassified_inputs
    ):
        _fail("financial_typed_option_materialization_result_invalid")
    typed_input = typed_inputs[0]
    material = {
        "schema_version": (MATERIALIZABILITY_RECEIPT_SCHEMA_VERSION),
        "validated_decision_schema_version": (VALIDATED_DECISION_SCHEMA_VERSION),
        "decision_schema_hash": contract.canonical_schema_hash(),
        "materialization_schema_version": (FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION),
        "materialization_policy_version": (MATERIALIZATION_POLICY_VERSION),
        "semantic_pack_integrity_sha256": (semantic_contract.integrity_sha256),
        "registry_hash": registry.registry_hash,
        "source_package_integrity_hash": source_package.integrity_hash,
        "materialized_artifact_hash": sha256_json(artifact),
        "materialized_artifact_integrity_hash": artifact["integrity_hash"],
        "typed_input_integrity_hash": typed_input["integrity_hash"],
        "typed_inputs_total": 1,
        "unclassified_inputs_total": 0,
        "provider_calls_total": 0,
        "status": "materializable",
    }
    return FinancialTypedOptionMaterializabilityReceipt(
        **material,
        receipt_hash=sha256_json(material),
    )


def _canonical_decision_contract(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    input_type_id: str,
) -> Gate2FinancialEvidenceDecisionContract:
    try:
        return Gate2FinancialSemanticV6CanonicalDecisionContractFactory(
            registry=registry,
        ).create(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            allowed_type_ids=(input_type_id,),
        )
    except Gate2FinancialSemanticV6CanonicalError as exc:
        raise Gate2FinancialTypedOptionError(
            "financial_typed_option_canonical_adapter_invalid"
        ) from exc


def _option_identity_material(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    input_type_id: str,
    required_roles: tuple[str, ...],
    optional_roles: tuple[str, ...],
    bindings: tuple[FinancialTypedOptionBinding, ...],
    structural_receipt: FinancialTypedOptionStructuralReceipt,
    materializability_receipt: (FinancialTypedOptionMaterializabilityReceipt),
) -> dict[str, Any]:
    return {
        "schema_version": TYPED_OPTION_SCHEMA_VERSION,
        "policy_version": TYPED_OPTION_POLICY_VERSION,
        "evidence_bundle_id": evidence_bundle.bundle_id,
        "evidence_bundle_integrity_hash": (evidence_bundle.integrity_hash),
        "input_type_id": input_type_id,
        "required_roles": list(required_roles),
        "optional_roles": list(optional_roles),
        "role_bindings": [_binding_payload(item) for item in bindings],
        "structural_compatibility_receipt": (
            _structural_receipt_payload(structural_receipt)
        ),
        "materializability_receipt": (
            _materializability_receipt_payload(materializability_receipt)
        ),
    }


def _option_payload_without_integrity(
    option: Gate2FinancialTypedOption,
) -> dict[str, Any]:
    return {
        "schema_version": option.schema_version,
        "policy_version": option.policy_version,
        "typed_option_id": option.typed_option_id,
        "evidence_bundle_id": option.evidence_bundle_id,
        "evidence_bundle_integrity_hash": (option.evidence_bundle_integrity_hash),
        "input_type_id": option.input_type_id,
        "required_roles": list(option.required_roles),
        "optional_roles": list(option.optional_roles),
        "role_bindings": [_binding_payload(item) for item in option.role_bindings],
        "structural_compatibility_receipt": (
            _structural_receipt_payload(option.structural_compatibility_receipt)
        ),
        "materializability_receipt": (
            _materializability_receipt_payload(option.materializability_receipt)
        ),
    }


def _binding_payload(
    binding: FinancialTypedOptionBinding,
) -> dict[str, str]:
    return {
        "role_id": binding.role_id,
        "source_value_ref": binding.source_value_ref,
    }


def _structural_receipt_payload(
    receipt: FinancialTypedOptionStructuralReceipt,
) -> dict[str, Any]:
    return {
        "schema_version": receipt.schema_version,
        "semantic_pack_id": receipt.semantic_pack_id,
        "semantic_pack_version": receipt.semantic_pack_version,
        "semantic_pack_integrity_sha256": (receipt.semantic_pack_integrity_sha256),
        "registry_version": receipt.registry_version,
        "registry_hash": receipt.registry_hash,
        "bundle_integrity_hash": receipt.bundle_integrity_hash,
        "type_contract_hash": receipt.type_contract_hash,
        "bindings_hash": receipt.bindings_hash,
        "association_identity_hash": (receipt.association_identity_hash),
        "associations_total": receipt.associations_total,
        "required_roles_total": receipt.required_roles_total,
        "optional_roles_total": receipt.optional_roles_total,
        "bound_roles_total": receipt.bound_roles_total,
        "required_roles_complete": receipt.required_roles_complete,
        "binding_refs_unique": receipt.binding_refs_unique,
        "status": receipt.status,
        "receipt_hash": receipt.receipt_hash,
    }


def _materializability_receipt_payload(
    receipt: FinancialTypedOptionMaterializabilityReceipt,
) -> dict[str, Any]:
    return {
        "schema_version": receipt.schema_version,
        "validated_decision_schema_version": (
            receipt.validated_decision_schema_version
        ),
        "decision_schema_hash": receipt.decision_schema_hash,
        "materialization_schema_version": (receipt.materialization_schema_version),
        "materialization_policy_version": (receipt.materialization_policy_version),
        "semantic_pack_integrity_sha256": (receipt.semantic_pack_integrity_sha256),
        "registry_hash": receipt.registry_hash,
        "source_package_integrity_hash": (receipt.source_package_integrity_hash),
        "materialized_artifact_hash": (receipt.materialized_artifact_hash),
        "materialized_artifact_integrity_hash": (
            receipt.materialized_artifact_integrity_hash
        ),
        "typed_input_integrity_hash": (receipt.typed_input_integrity_hash),
        "typed_inputs_total": receipt.typed_inputs_total,
        "unclassified_inputs_total": (receipt.unclassified_inputs_total),
        "provider_calls_total": receipt.provider_calls_total,
        "status": receipt.status,
        "receipt_hash": receipt.receipt_hash,
    }


def _type_contract_payload(
    type_contract: FinancialSemanticTypeContract,
) -> dict[str, Any]:
    return {
        "input_type_id": type_contract.input_type_id,
        "compatible_source_families": list(type_contract.compatible_source_families),
        "required_roles": list(type_contract.required_roles),
        "optional_roles": list(type_contract.optional_roles),
        "role_contracts": [item.to_dict() for item in type_contract.role_contracts],
        "date_period_requirement": (type_contract.date_period_requirement),
        "currency_unit_requirement": (type_contract.currency_unit_requirement),
        "identity_roles": list(type_contract.identity_roles),
        "materialization_profile_id": (type_contract.materialization_profile_id),
        "validation_profile_id": (type_contract.validation_profile_id),
    }


def _fail(code: str) -> None:
    raise Gate2FinancialTypedOptionError(code)
