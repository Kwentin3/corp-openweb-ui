"""Publish and resolve the small closed Gate 5 runtime capability contract."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
import re
from typing import Any

from .gate5_declaration_projection import (
    Gate5DeclarationProjectionRuntime,
    Gate5DeclarationProjectionRuntimeFactory,
    Gate5DeclarationProjectionRuntimeV1,
    Gate5DeclarationProjectionRuntimeV1Factory,
)
from .gate5_published_typed_behavior import (
    GATE5_PUBLISHED_TYPED_BEHAVIOR_BINDING_ID,
    Gate5PublishedTypedBehaviorRuntime,
    Gate5PublishedTypedBehaviorRuntimeFactory,
)
from .gate5_single_input_human_loop import (
    Gate5SingleInputHumanLoopRuntime,
    Gate5SingleInputHumanLoopRuntimeFactory,
)
from .gate5_supplemental_fact_discovery import (
    Gate5SupplementalFactDiscoveryRuntime,
    Gate5SupplementalFactDiscoveryRuntimeFactory,
)
from .gate5_tax_period_category_aggregation import (
    Gate5TaxPeriodCategoryAggregationRuntime,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
from .gate5_trusted_methodology import (
    Gate5TrustedMethodologyCalculationRuntime,
    Gate5TrustedMethodologyCalculationRuntimeFactory,
)


GATE5_RUNTIME_CAPABILITY_CONTRACT_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_contract_v0"
)
GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_ref_v0"
)
GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_model_projection_v0"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE = "gate5_runtime_capability_contract.v0.json"
GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE_SHA256 = (
    "61fc352ae0e77e92cc1f06fb71fbbf5c2c79e6123bc40b8c930140ead774c8e8"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_contract_v1"
)
GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_ref_v1"
)
GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V1_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_model_projection_v1"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE = (
    "gate5_runtime_capability_contract.v1.json"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE_SHA256 = (
    "e5134005e3715e70249f14dd1918ce4d110e70bb6eba1304ccbd9204c1531e8f"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_contract_v2"
)
GATE5_RUNTIME_CAPABILITY_REF_V2_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_ref_v2"
)
GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V2_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_model_projection_v2"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE = (
    "gate5_runtime_capability_contract.v2.json"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE_SHA256 = (
    "f35ca4cb5ef8a218b3eab0e287c76b69aeb687ad1741d6196ff6889d547209cc"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_contract_v3"
)
GATE5_RUNTIME_CAPABILITY_REF_V3_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_ref_v3"
)
GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V3_SCHEMA_VERSION = (
    "broker_reports_gate5_runtime_capability_model_projection_v3"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE = (
    "gate5_runtime_capability_contract.v3.json"
)
GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE_SHA256 = (
    "34d3796054fc780b4c4937caf101b87224a64ed58b857ac9404a5c0b3438f438"
)

FACTORY_REQUIRED = (
    "Gate5RuntimeCapabilityContractFactory.create preserves the exact v0 contract",
    "Gate5RuntimeCapabilityContractV1Factory.create loads the additive v1 contract",
    "Gate5RuntimeCapabilityContractV2Factory.create loads the cardinality-corrected v2 contract",
    "Gate5RuntimeCapabilityContractV3Factory.create replaces only the PROJECT "
    "member with its registered versioned-projection contract",
    "each versioned resolver accepts only its exact capability reference version",
    "every resolved binding delegates to an existing reviewed Gate5 runtime factory",
)
FORBIDDEN = (
    "Python module, class, function, path or dependency names in the model projection",
    "dynamic imports, callable loading, fallback or guessing for unknown capabilities",
    "tax formulas, declaration fields or scenario control flow in the capability contract",
    "generic workflow engine, rules DSL, plugin system, service registry or product activation",
)

_CONTRACT_KEYS = {
    "schema_version",
    "contract_id",
    "contract_version",
    "status",
    "capability_ref_schema_version",
    "capabilities",
}
_CAPABILITY_KEYS = {
    "capability_id",
    "execution_phase",
    "meaning",
    "inputs",
    "preconditions",
    "output",
    "failure_conditions",
    "provenance_classes",
    "supported_value_kinds",
    "implementation_status",
    "conformance",
}
_INPUT_KEYS = {"name", "contract", "required"}
_OUTPUT_KEYS = {"contract", "guarantees"}
_CONFORMANCE_KEYS = {"binding_id", "owner_contract"}
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")


class Gate5RuntimeCapabilityError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


@dataclass(frozen=True)
class _RuntimeBinding:
    binding_id: str
    factory_owner: type[Any]
    runtime_owner: type[Any]
    construction: str
    required_dependencies: tuple[str, ...]
    optional_dependencies: tuple[str, ...]
    operations: tuple[str, ...]


_RUNTIME_BINDINGS = {
    "resolve_required_values_v0": _RuntimeBinding(
        binding_id="gate5.resolve_required_values.v0",
        factory_owner=Gate5SupplementalFactDiscoveryRuntimeFactory,
        runtime_owner=Gate5SupplementalFactDiscoveryRuntime,
        construction="instance_factory",
        required_dependencies=("store", "read_enabled", "retention_policy"),
        optional_dependencies=(),
        operations=("check",),
    ),
    "obtain_one_missing_money_input_v0": _RuntimeBinding(
        binding_id="gate5.obtain_one_missing_money_input.v0",
        factory_owner=Gate5SingleInputHumanLoopRuntimeFactory,
        runtime_owner=Gate5SingleInputHumanLoopRuntime,
        construction="instance_factory",
        required_dependencies=(
            "store",
            "read_enabled",
            "retention_policy",
            "model_client",
            "model_id",
        ),
        optional_dependencies=(),
        operations=("ask", "submit"),
    ),
    "execute_published_calculation_behavior_v0": _RuntimeBinding(
        binding_id="gate5.execute_published_calculation_behavior.v0",
        factory_owner=Gate5TrustedMethodologyCalculationRuntimeFactory,
        runtime_owner=Gate5TrustedMethodologyCalculationRuntime,
        construction="instance_factory",
        required_dependencies=("store", "read_enabled", "retention_policy"),
        optional_dependencies=(),
        operations=("calculate",),
    ),
    "project_validated_declaration_fragment_v0": _RuntimeBinding(
        binding_id="gate5.project_validated_declaration_fragment.v0",
        factory_owner=Gate5DeclarationProjectionRuntimeFactory,
        runtime_owner=Gate5DeclarationProjectionRuntime,
        construction="static_factory",
        required_dependencies=(),
        optional_dependencies=(),
        operations=("project",),
    ),
    "aggregate_complete_category_scope_v0": _RuntimeBinding(
        binding_id="gate5.aggregate_complete_category_scope.v0",
        factory_owner=Gate5TaxPeriodCategoryAggregationRuntimeFactory,
        runtime_owner=Gate5TaxPeriodCategoryAggregationRuntime,
        construction="static_factory",
        required_dependencies=(),
        optional_dependencies=(),
        operations=("describe_scope", "run"),
    ),
}

_RUNTIME_BINDINGS_V1 = {
    capability_id: binding
    for capability_id, binding in _RUNTIME_BINDINGS.items()
    if capability_id != "execute_published_calculation_behavior_v0"
}
_RUNTIME_BINDINGS_V1["execute_published_typed_behavior_v1"] = _RuntimeBinding(
    binding_id=GATE5_PUBLISHED_TYPED_BEHAVIOR_BINDING_ID,
    factory_owner=Gate5PublishedTypedBehaviorRuntimeFactory,
    runtime_owner=Gate5PublishedTypedBehaviorRuntime,
    construction="instance_factory",
    required_dependencies=("store", "read_enabled", "retention_policy"),
    optional_dependencies=(),
    operations=("execute",),
)
_RUNTIME_BINDINGS_V2 = dict(_RUNTIME_BINDINGS_V1)
_RUNTIME_BINDINGS_V3 = {
    capability_id: binding
    for capability_id, binding in _RUNTIME_BINDINGS_V2.items()
    if capability_id != "project_validated_declaration_fragment_v0"
}
_RUNTIME_BINDINGS_V3["project_validated_declaration_fragment_v1"] = _RuntimeBinding(
    binding_id="gate5.project_validated_declaration_fragment.v1",
    factory_owner=Gate5DeclarationProjectionRuntimeV1Factory,
    runtime_owner=Gate5DeclarationProjectionRuntimeV1,
    construction="static_factory",
    required_dependencies=(),
    optional_dependencies=(),
    operations=("project",),
)


@dataclass(frozen=True)
class Gate5ResolvedRuntimeCapability:
    capability_id: str
    binding_id: str
    operations: tuple[str, ...]
    _binding: _RuntimeBinding

    @property
    def factory_owner(self) -> type[Any]:
        return self._binding.factory_owner

    @property
    def runtime_owner(self) -> type[Any]:
        return self._binding.runtime_owner

    def create_runtime(self, **dependencies: Any) -> Any:
        supplied = set(dependencies)
        required = set(self._binding.required_dependencies)
        allowed = required | set(self._binding.optional_dependencies)
        if supplied - allowed or required - supplied:
            _fail("gate5_runtime_capability_dependencies_invalid")
        if self._binding.construction == "instance_factory":
            runtime = self._binding.factory_owner(**dependencies).create()
        elif self._binding.construction == "static_factory":
            runtime = self._binding.factory_owner.create(**dependencies)
        else:
            _fail("gate5_runtime_capability_contract_drift")
        if not isinstance(runtime, self._binding.runtime_owner):
            _fail("gate5_runtime_capability_contract_drift")
        for operation in self.operations:
            if not callable(getattr(runtime, operation, None)):
                _fail("gate5_runtime_capability_contract_drift")
        return runtime


class Gate5RuntimeCapabilityContractFactory:
    @staticmethod
    def create() -> "Gate5RuntimeCapabilityContract":
        try:
            raw = (
                resources.files(__package__)
                .joinpath(GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE)
                .read_bytes()
            )
        except (FileNotFoundError, OSError) as exc:
            raise Gate5RuntimeCapabilityError(
                "gate5_runtime_capability_contract_unavailable"
            ) from exc
        if hashlib.sha256(raw).hexdigest() != (
            GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE_SHA256
        ):
            _fail("gate5_runtime_capability_contract_hash_mismatch")
        try:
            snapshot: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5RuntimeCapabilityError(
                "gate5_runtime_capability_contract_json_invalid"
            ) from exc
        _validate_contract(snapshot)
        _validate_runtime_conformance(snapshot)
        return Gate5RuntimeCapabilityContract(snapshot=copy.deepcopy(snapshot))


class Gate5RuntimeCapabilityContractV1Factory:
    @staticmethod
    def create() -> "Gate5RuntimeCapabilityContract":
        try:
            raw = (
                resources.files(__package__)
                .joinpath(GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE)
                .read_bytes()
            )
        except (FileNotFoundError, OSError) as exc:
            raise Gate5RuntimeCapabilityError(
                "gate5_runtime_capability_contract_unavailable"
            ) from exc
        if hashlib.sha256(raw).hexdigest() != (
            GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE_SHA256
        ):
            _fail("gate5_runtime_capability_contract_hash_mismatch")
        try:
            snapshot: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5RuntimeCapabilityError(
                "gate5_runtime_capability_contract_json_invalid"
            ) from exc
        _validate_contract(
            snapshot,
            contract_schema_version=(
                GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_SCHEMA_VERSION
            ),
            capability_ref_schema_version=(
                GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION
            ),
        )
        _validate_runtime_conformance(snapshot, bindings=_RUNTIME_BINDINGS_V1)
        return Gate5RuntimeCapabilityContract(
            snapshot=copy.deepcopy(snapshot),
            model_projection_schema_version=(
                GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V1_SCHEMA_VERSION
            ),
        )


class Gate5RuntimeCapabilityContractV2Factory:
    @staticmethod
    def create() -> "Gate5RuntimeCapabilityContract":
        try:
            raw = (
                resources.files(__package__)
                .joinpath(GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE)
                .read_bytes()
            )
        except (FileNotFoundError, OSError) as exc:
            raise Gate5RuntimeCapabilityError(
                "gate5_runtime_capability_contract_unavailable"
            ) from exc
        if hashlib.sha256(raw).hexdigest() != (
            GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE_SHA256
        ):
            _fail("gate5_runtime_capability_contract_hash_mismatch")
        try:
            snapshot: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5RuntimeCapabilityError(
                "gate5_runtime_capability_contract_json_invalid"
            ) from exc
        _validate_contract(
            snapshot,
            contract_schema_version=(
                GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_SCHEMA_VERSION
            ),
            capability_ref_schema_version=(
                GATE5_RUNTIME_CAPABILITY_REF_V2_SCHEMA_VERSION
            ),
        )
        _validate_runtime_conformance(snapshot, bindings=_RUNTIME_BINDINGS_V2)
        return Gate5RuntimeCapabilityContract(
            snapshot=copy.deepcopy(snapshot),
            model_projection_schema_version=(
                GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V2_SCHEMA_VERSION
            ),
        )


class Gate5RuntimeCapabilityContractV3Factory:
    @staticmethod
    def create() -> "Gate5RuntimeCapabilityContract":
        try:
            raw = (
                resources.files(__package__)
                .joinpath(GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE)
                .read_bytes()
            )
        except (FileNotFoundError, OSError) as exc:
            raise Gate5RuntimeCapabilityError(
                "gate5_runtime_capability_contract_unavailable"
            ) from exc
        if hashlib.sha256(raw).hexdigest() != (
            GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE_SHA256
        ):
            _fail("gate5_runtime_capability_contract_hash_mismatch")
        try:
            snapshot: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5RuntimeCapabilityError(
                "gate5_runtime_capability_contract_json_invalid"
            ) from exc
        _validate_contract(
            snapshot,
            contract_schema_version=(
                GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_SCHEMA_VERSION
            ),
            capability_ref_schema_version=(
                GATE5_RUNTIME_CAPABILITY_REF_V3_SCHEMA_VERSION
            ),
        )
        _validate_runtime_conformance(snapshot, bindings=_RUNTIME_BINDINGS_V3)
        return Gate5RuntimeCapabilityContract(
            snapshot=copy.deepcopy(snapshot),
            model_projection_schema_version=(
                GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V3_SCHEMA_VERSION
            ),
        )


class Gate5RuntimeCapabilityContract:
    def __init__(
        self,
        *,
        snapshot: dict[str, Any],
        model_projection_schema_version: str = (
            GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_SCHEMA_VERSION
        ),
    ) -> None:
        self._snapshot = snapshot
        self._model_projection_schema_version = model_projection_schema_version

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._snapshot)

    def model_projection(self) -> dict[str, Any]:
        capabilities = []
        for capability in self._snapshot["capabilities"]:
            capabilities.append(
                {
                    key: copy.deepcopy(value)
                    for key, value in capability.items()
                    if key != "conformance"
                }
            )
        return {
            "schema_version": self._model_projection_schema_version,
            "contract_id": self._snapshot["contract_id"],
            "contract_version": self._snapshot["contract_version"],
            "status": self._snapshot["status"],
            "capability_ref_schema_version": self._snapshot[
                "capability_ref_schema_version"
            ],
            "capabilities": capabilities,
        }

    def model_projection_bytes(self) -> bytes:
        return _canonical_json(self.model_projection())


class Gate5RuntimeCapabilityResolverFactory:
    @staticmethod
    def create() -> "Gate5RuntimeCapabilityResolver":
        return Gate5RuntimeCapabilityResolver(
            contract=Gate5RuntimeCapabilityContractFactory.create()
        )


class Gate5RuntimeCapabilityResolverV1Factory:
    @staticmethod
    def create() -> "Gate5RuntimeCapabilityResolver":
        return Gate5RuntimeCapabilityResolver(
            contract=Gate5RuntimeCapabilityContractV1Factory.create(),
            bindings=_RUNTIME_BINDINGS_V1,
            capability_ref_schema_version=(
                GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION
            ),
        )


class Gate5RuntimeCapabilityResolverV2Factory:
    @staticmethod
    def create() -> "Gate5RuntimeCapabilityResolver":
        return Gate5RuntimeCapabilityResolver(
            contract=Gate5RuntimeCapabilityContractV2Factory.create(),
            bindings=_RUNTIME_BINDINGS_V2,
            capability_ref_schema_version=(
                GATE5_RUNTIME_CAPABILITY_REF_V2_SCHEMA_VERSION
            ),
        )


class Gate5RuntimeCapabilityResolverV3Factory:
    @staticmethod
    def create() -> "Gate5RuntimeCapabilityResolver":
        return Gate5RuntimeCapabilityResolver(
            contract=Gate5RuntimeCapabilityContractV3Factory.create(),
            bindings=_RUNTIME_BINDINGS_V3,
            capability_ref_schema_version=(
                GATE5_RUNTIME_CAPABILITY_REF_V3_SCHEMA_VERSION
            ),
        )


class Gate5RuntimeCapabilityResolver:
    def __init__(
        self,
        *,
        contract: Gate5RuntimeCapabilityContract,
        bindings: dict[str, _RuntimeBinding] | None = None,
        capability_ref_schema_version: str = (
            GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION
        ),
    ) -> None:
        self._contract = contract
        self._bindings = _RUNTIME_BINDINGS if bindings is None else bindings
        self._capability_ref_schema_version = capability_ref_schema_version

    def resolve(self, capability_ref: dict[str, Any]) -> Gate5ResolvedRuntimeCapability:
        capability_id = _validated_reference(
            capability_ref,
            capability_ref_schema_version=self._capability_ref_schema_version,
        )
        binding = self._bindings.get(capability_id)
        if binding is None:
            _fail("gate5_runtime_capability_unsupported")
        return Gate5ResolvedRuntimeCapability(
            capability_id=capability_id,
            binding_id=binding.binding_id,
            operations=binding.operations,
            _binding=binding,
        )

    def model_projection(self) -> dict[str, Any]:
        return self._contract.model_projection()


def _validate_contract(
    value: Any,
    *,
    contract_schema_version: str = GATE5_RUNTIME_CAPABILITY_CONTRACT_SCHEMA_VERSION,
    capability_ref_schema_version: str = GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION,
) -> None:
    if not isinstance(value, dict) or set(value) != _CONTRACT_KEYS:
        _fail("gate5_runtime_capability_contract_invalid")
    if (
        value.get("schema_version") != contract_schema_version
        or value.get("capability_ref_schema_version") != capability_ref_schema_version
        or value.get("status") != "inactive_proof"
        or not _identifier(value.get("contract_id"))
        or not _clean(value.get("contract_version"), maximum=64)
    ):
        _fail("gate5_runtime_capability_contract_invalid")
    capabilities = value.get("capabilities")
    if not isinstance(capabilities, list) or not 4 <= len(capabilities) <= 7:
        _fail("gate5_runtime_capability_contract_invalid")
    capability_ids: set[str] = set()
    for capability in capabilities:
        _validate_capability(capability)
        capability_id = capability["capability_id"]
        if capability_id in capability_ids:
            _fail("gate5_runtime_capability_contract_invalid")
        capability_ids.add(capability_id)


def _validate_capability(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != _CAPABILITY_KEYS:
        _fail("gate5_runtime_capability_contract_invalid")
    if (
        not _identifier(value.get("capability_id"))
        or value.get("execution_phase") not in {"authoring_time", "case_time"}
        or not _clean(value.get("meaning"), maximum=512)
        or value.get("implementation_status") != "proven"
    ):
        _fail("gate5_runtime_capability_contract_invalid")
    inputs = value.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        _fail("gate5_runtime_capability_contract_invalid")
    input_names: set[str] = set()
    for item in inputs:
        if (
            not isinstance(item, dict)
            or set(item) != _INPUT_KEYS
            or not _identifier(item.get("name"))
            or not _identifier(item.get("contract"))
            or not isinstance(item.get("required"), bool)
            or item["name"] in input_names
        ):
            _fail("gate5_runtime_capability_contract_invalid")
        input_names.add(item["name"])
    output = value.get("output")
    if (
        not isinstance(output, dict)
        or set(output) != _OUTPUT_KEYS
        or not _identifier(output.get("contract"))
    ):
        _fail("gate5_runtime_capability_contract_invalid")
    _closed_identifier_list(output.get("guarantees"))
    for field in (
        "preconditions",
        "failure_conditions",
        "provenance_classes",
        "supported_value_kinds",
    ):
        _closed_identifier_list(value.get(field))
    conformance = value.get("conformance")
    if (
        not isinstance(conformance, dict)
        or set(conformance) != _CONFORMANCE_KEYS
        or not _identifier(conformance.get("binding_id"))
        or not _identifier(conformance.get("owner_contract"))
    ):
        _fail("gate5_runtime_capability_contract_invalid")


def _validate_runtime_conformance(
    snapshot: dict[str, Any],
    *,
    bindings: dict[str, _RuntimeBinding] | None = None,
) -> None:
    runtime_bindings = _RUNTIME_BINDINGS if bindings is None else bindings
    capabilities = {item["capability_id"]: item for item in snapshot["capabilities"]}
    if set(capabilities) != set(runtime_bindings):
        _fail("gate5_runtime_capability_contract_drift")
    for capability_id, binding in runtime_bindings.items():
        if capabilities[capability_id]["conformance"]["binding_id"] != (
            binding.binding_id
        ):
            _fail("gate5_runtime_capability_contract_drift")
        if (
            binding.construction not in {"instance_factory", "static_factory"}
            or not callable(getattr(binding.factory_owner, "create", None))
            or not binding.operations
        ):
            _fail("gate5_runtime_capability_contract_drift")
        for operation in binding.operations:
            if not callable(getattr(binding.runtime_owner, operation, None)):
                _fail("gate5_runtime_capability_contract_drift")


def _validated_reference(
    value: Any,
    *,
    capability_ref_schema_version: str = (GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION),
) -> str:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "capability_id"}
        or value.get("schema_version") != capability_ref_schema_version
        or not _identifier(value.get("capability_id"))
    ):
        _fail("gate5_runtime_capability_ref_invalid")
    return value["capability_id"]


def _closed_identifier_list(value: Any) -> None:
    if (
        not isinstance(value, list)
        or not value
        or len(value) != len(set(value))
        or any(not _identifier(item) for item in value)
    ):
        _fail("gate5_runtime_capability_contract_invalid")


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _clean(value: Any, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= maximum
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _fail(code: str) -> None:
    raise Gate5RuntimeCapabilityError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE_SHA256",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE_SHA256",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE_SHA256",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE_SHA256",
    "GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V1_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V2_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V3_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_REF_V2_SCHEMA_VERSION",
    "GATE5_RUNTIME_CAPABILITY_REF_V3_SCHEMA_VERSION",
    "Gate5ResolvedRuntimeCapability",
    "Gate5RuntimeCapabilityContract",
    "Gate5RuntimeCapabilityContractFactory",
    "Gate5RuntimeCapabilityContractV1Factory",
    "Gate5RuntimeCapabilityContractV2Factory",
    "Gate5RuntimeCapabilityContractV3Factory",
    "Gate5RuntimeCapabilityError",
    "Gate5RuntimeCapabilityResolver",
    "Gate5RuntimeCapabilityResolverFactory",
    "Gate5RuntimeCapabilityResolverV1Factory",
    "Gate5RuntimeCapabilityResolverV2Factory",
    "Gate5RuntimeCapabilityResolverV3Factory",
]
