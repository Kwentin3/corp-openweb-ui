from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_model_assets import (
    load_gate2_financial_semantic_model_assets,
)


FINANCIAL_SEMANTIC_RUNTIME_CONTRACT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_runtime_contract_v1"
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticContractFactory.create is the only runtime "
    "Pack-to-Registry validation and operational contract entrypoint"
)
FORBIDDEN = (
    "Validators and materializers must not branch on concrete type IDs, "
    "financial words, prompts, provider output or benchmark expectations"
)

_AGGREGATE_SEMANTICS_BY_CLASS = {
    "aggregate": "source_printed",
    "attribute": "not_aggregate",
    "event": "not_aggregate",
    "state": "not_aggregate",
}


class Gate2FinancialSemanticContractError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialSemanticRoleContract:
    role_id: str
    value_type: str
    cardinality: str
    source_ref_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "value_type": self.value_type,
            "cardinality": self.cardinality,
            "source_ref_required": self.source_ref_required,
        }


@dataclass(frozen=True)
class FinancialSemanticTypeContract:
    input_type_id: str
    title: str
    semantic_class: str
    lifecycle: str
    compatible_source_families: tuple[str, ...]
    required_roles: tuple[str, ...]
    optional_roles: tuple[str, ...]
    forbidden_roles: tuple[str, ...]
    role_contracts: tuple[FinancialSemanticRoleContract, ...]
    date_period_requirement: str
    currency_unit_requirement: str
    source_sign_policy: str
    identity_roles: tuple[str, ...]
    materialization_profile_id: str
    validation_profile_id: str
    context_projection_rule_id: str

    def role(self, role_id: str) -> FinancialSemanticRoleContract:
        for contract in self.role_contracts:
            if contract.role_id == role_id:
                return contract
        _fail("financial_semantic_role_unknown")

    def aggregate_semantics(self) -> str:
        result = _AGGREGATE_SEMANTICS_BY_CLASS.get(self.semantic_class)
        if result is None:
            _fail("financial_semantic_class_unsupported")
        return result


@dataclass(frozen=True)
class Gate2FinancialSemanticContractSnapshot:
    schema_version: str
    pack_id: str
    semantic_version: str
    integrity_sha256: str
    type_contracts: tuple[FinancialSemanticTypeContract, ...]

    def type_contract(
        self,
        input_type_id: str,
    ) -> FinancialSemanticTypeContract:
        for contract in self.type_contracts:
            if contract.input_type_id == input_type_id:
                return contract
        _fail("financial_semantic_type_not_in_pack")

    def identity_payload(self) -> dict[str, str]:
        return {
            "pack_id": self.pack_id,
            "semantic_version": self.semantic_version,
            "integrity_sha256": self.integrity_sha256,
        }


class Gate2FinancialSemanticContractFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(self) -> Gate2FinancialSemanticContractSnapshot:
        assets = load_gate2_financial_semantic_model_assets()
        pack = copy.deepcopy(assets.get("semantic_pack"))
        if not isinstance(pack, dict) or set(pack) != {
            "schema_version",
            "pack_id",
            "semantic_version",
            "managed_asset_ref",
            "consumer_contract_version",
            "integrity_sha256",
            "full_compact_snapshot",
        }:
            _fail("financial_semantic_pack_projection_invalid")
        items = pack["full_compact_snapshot"]
        if not isinstance(items, list) or not items:
            _fail("financial_semantic_pack_types_missing")
        contracts = tuple(self._type_contract(item) for item in items)
        type_ids = tuple(item.input_type_id for item in contracts)
        active_registry_ids = tuple(
            declaration.input_type_id
            for declaration in self.registry.declarations
            if declaration.lifecycle == "active"
        )
        if (
            len(type_ids) != len(set(type_ids))
            or set(type_ids) != set(active_registry_ids)
        ):
            _fail("financial_semantic_pack_registry_membership_mismatch")
        for contract in contracts:
            self._validate_registry_projection(contract)
        return Gate2FinancialSemanticContractSnapshot(
            schema_version=(
                FINANCIAL_SEMANTIC_RUNTIME_CONTRACT_SCHEMA_VERSION
            ),
            pack_id=str(pack["pack_id"]),
            semantic_version=str(pack["semantic_version"]),
            integrity_sha256=str(pack["integrity_sha256"]),
            type_contracts=contracts,
        )

    def _type_contract(
        self,
        item: Any,
    ) -> FinancialSemanticTypeContract:
        if not isinstance(item, dict):
            _fail("financial_semantic_pack_type_invalid")
        roles = item.get("roles")
        lifecycle = item.get("lifecycle")
        operational = item.get("operational_contracts")
        if (
            not isinstance(roles, dict)
            or set(roles) != {"required", "optional", "forbidden"}
            or not isinstance(lifecycle, dict)
            or not isinstance(operational, dict)
        ):
            _fail("financial_semantic_pack_type_contract_invalid")
        required = _roles(roles["required"])
        optional = _roles(roles["optional"])
        forbidden = roles["forbidden"]
        identity_roles = item.get("identity_roles")
        if (
            not isinstance(forbidden, list)
            or any(not isinstance(value, str) for value in forbidden)
            or not isinstance(identity_roles, list)
            or any(not isinstance(value, str) for value in identity_roles)
        ):
            _fail("financial_semantic_pack_role_contract_invalid")
        return FinancialSemanticTypeContract(
            input_type_id=str(item.get("input_type_id") or ""),
            title=str(item.get("title") or ""),
            semantic_class=str(item.get("semantic_class") or ""),
            lifecycle=str(lifecycle.get("status") or ""),
            compatible_source_families=tuple(
                item.get("compatible_source_families") or ()
            ),
            required_roles=tuple(role.role_id for role in required),
            optional_roles=tuple(role.role_id for role in optional),
            forbidden_roles=tuple(forbidden),
            role_contracts=(*required, *optional),
            date_period_requirement=str(
                item.get("date_period_requirement") or ""
            ),
            currency_unit_requirement=str(
                item.get("currency_unit_requirement") or ""
            ),
            source_sign_policy=str(item.get("source_sign_policy") or ""),
            identity_roles=tuple(identity_roles),
            materialization_profile_id=str(
                operational.get("materialization_profile_id") or ""
            ),
            validation_profile_id=str(
                operational.get("validation_profile_id") or ""
            ),
            context_projection_rule_id=str(
                operational.get("context_projection_rule_id") or ""
            ),
        )

    def _validate_registry_projection(
        self,
        contract: FinancialSemanticTypeContract,
    ) -> None:
        declaration = self.registry.get(contract.input_type_id)
        registry_roles = tuple(
            {
                "role_id": role.role_id,
                "value_type": role.value_type,
                "cardinality": role.cardinality,
                "source_ref_required": role.source_ref_required,
            }
            for role in declaration.role_specs
        )
        if (
            contract.lifecycle != "active"
            or contract.title != declaration.title
            or contract.semantic_class != declaration.semantic_class
            or contract.compatible_source_families
            != declaration.compatible_source_families
            or contract.required_roles != declaration.required_roles
            or contract.optional_roles != declaration.optional_roles
            or contract.forbidden_roles != declaration.forbidden_roles
            or tuple(
                role.to_dict() for role in contract.role_contracts
            )
            != registry_roles
            or contract.date_period_requirement
            != declaration.date_period_requirement
            or contract.currency_unit_requirement
            != declaration.currency_unit_requirement
            or contract.source_sign_policy
            != declaration.source_sign_policy
            or contract.identity_roles
            != declaration.identity_policy.identity_roles
            or declaration.identity_policy.include_source_scope is not True
            or declaration.identity_policy.include_source_evidence_refs
            is not True
            or contract.materialization_profile_id
            != declaration.materialization_profile_id
            or contract.validation_profile_id
            != declaration.validation_profile_id
            or contract.context_projection_rule_id
            != declaration.context_projection_rule_id
        ):
            _fail("financial_semantic_pack_registry_contract_mismatch")


def _roles(value: Any) -> tuple[FinancialSemanticRoleContract, ...]:
    if not isinstance(value, list):
        _fail("financial_semantic_pack_roles_invalid")
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "role_id",
            "value_type",
            "cardinality",
            "source_ref_required",
        }:
            _fail("financial_semantic_pack_role_invalid")
        result.append(
            FinancialSemanticRoleContract(
                role_id=str(item["role_id"]),
                value_type=str(item["value_type"]),
                cardinality=str(item["cardinality"]),
                source_ref_required=item["source_ref_required"] is True,
            )
        )
    if (
        any(not item.role_id for item in result)
        or len(result) != len({item.role_id for item in result})
    ):
        _fail("financial_semantic_pack_roles_invalid")
    return tuple(result)


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticContractError(code)
