"""Execute only closed, published Gate 5 behavior/contract bindings."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import re
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate5_methodology_calculation import (
    GATE5_CALCULATION_RESULT_SCHEMA_VERSION,
    GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID,
)
from .gate5_income_group_tax_base import (
    GATE5_INCOME_GROUP_TAX_BASE_BEHAVIOR_ID,
    GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
    Gate5IncomeGroupTaxBaseRuntime,
    Gate5IncomeGroupTaxBaseRuntimeFactory,
)
from .gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID,
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_RESULT_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION,
    Gate5SecuritiesDisposalTaxModelRuntime,
    Gate5SecuritiesDisposalTaxModelRuntimeFactory,
)
from .gate5_tax_period_category_aggregation import (
    GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT,
    Gate5TaxPeriodCategoryAggregationRuntime,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
from .gate5_trusted_methodology import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION,
    GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
    GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER,
    GATE5_TRUSTED_METHODOLOGY_ID,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    GATE5_TRUSTED_METHODOLOGY_VERSION,
    Gate5TrustedMethodologyCalculationRuntime,
    Gate5TrustedMethodologyCalculationRuntimeFactory,
)


GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION = (
    "broker_reports_gate5_published_behavior_ref_v1"
)
GATE5_TYPED_BEHAVIOR_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_typed_behavior_result_v1"
)
GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_no_additional_behavior_input_v1"
)
GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID = "execute_published_typed_behavior_v1"
GATE5_PUBLISHED_TYPED_BEHAVIOR_BINDING_ID = "gate5.execute_published_typed_behavior.v1"

FACTORY_REQUIRED = (
    "Gate5PublishedTypedBehaviorRuntimeFactory.create is the sole typed executor",
    "Gate5TrustedMethodologyCalculationRuntimeFactory.create owns G5.7 execution",
    "Gate5SecuritiesDisposalTaxModelRuntimeFactory.create owns operation modeling",
    "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create owns member validation",
    "Gate5IncomeGroupTaxBaseRuntimeFactory.create owns income-group tax base",
)
FORBIDDEN = (
    "caller-supplied implementation, callable, module, path, code or schema contents",
    "dynamic import, eval, exec, plugin loading, fallback or nearest behavior match",
    "behavior execution without an exact static identity/input/output binding",
    "tax formulas, classification or operation-model reconstruction in this adapter",
)

_CALCULATION_IMPLEMENTATION_BINDING = "gate5.trusted_calculation.v0"
_OPERATION_MODEL_IMPLEMENTATION_BINDING = "gate5.operation_tax_model.v0"
_INCOME_GROUP_TAX_BASE_IMPLEMENTATION_BINDING = "gate5.income_group_tax_base.v0"
_BEHAVIOR_REF_KEYS = {
    "schema_version",
    "methodology_id",
    "methodology_version",
    "behavior_id",
}
_AUTHORITY_BINDING_KEYS = {
    "authority_owner",
    "methodology_id",
    "methodology_version",
    "resource_sha256",
    "projection_sha256",
}
_CALCULATION_RESULT_KEYS = {
    "schema_version",
    "status",
    "methodology_binding",
    "calculation_binding",
    "inputs",
    "outputs",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class Gate5PublishedTypedBehaviorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _PublishedTypedBehaviorBinding:
    methodology_id: str
    methodology_version: str
    behavior_id: str
    input_contract_id: str
    output_contract_id: str
    implementation_binding_id: str
    authority_owner: str


_PUBLISHED_TYPED_BEHAVIORS = {
    (
        GATE5_TRUSTED_METHODOLOGY_ID,
        GATE5_TRUSTED_METHODOLOGY_VERSION,
        GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID,
    ): _PublishedTypedBehaviorBinding(
        methodology_id=GATE5_TRUSTED_METHODOLOGY_ID,
        methodology_version=GATE5_TRUSTED_METHODOLOGY_VERSION,
        behavior_id=GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID,
        input_contract_id=GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION,
        output_contract_id=GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
        implementation_binding_id=_CALCULATION_IMPLEMENTATION_BINDING,
        authority_owner=GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER,
    ),
    (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
        GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID,
    ): _PublishedTypedBehaviorBinding(
        methodology_id=GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        methodology_version=GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
        behavior_id=GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID,
        input_contract_id=GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION,
        output_contract_id=GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT,
        implementation_binding_id=_OPERATION_MODEL_IMPLEMENTATION_BINDING,
        authority_owner=GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER,
    ),
    (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION,
        GATE5_INCOME_GROUP_TAX_BASE_BEHAVIOR_ID,
    ): _PublishedTypedBehaviorBinding(
        methodology_id=GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        methodology_version=(
            GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION
        ),
        behavior_id=GATE5_INCOME_GROUP_TAX_BASE_BEHAVIOR_ID,
        input_contract_id=GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
        output_contract_id=GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
        implementation_binding_id=_INCOME_GROUP_TAX_BASE_IMPLEMENTATION_BINDING,
        authority_owner=GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER,
    ),
}


class Gate5PublishedTypedBehaviorRegistryFactory:
    @staticmethod
    def create() -> "Gate5PublishedTypedBehaviorRegistry":
        return Gate5PublishedTypedBehaviorRegistry()


class Gate5PublishedTypedBehaviorRegistry:
    def resolve(self, behavior_ref: dict[str, Any]) -> _PublishedTypedBehaviorBinding:
        identity = _validated_behavior_ref(behavior_ref)
        binding = _PUBLISHED_TYPED_BEHAVIORS.get(identity)
        if binding is None:
            _fail("gate5_published_typed_behavior_unsupported")
        return binding

    def describe(self, behavior_ref: dict[str, Any]) -> dict[str, str]:
        binding = self.resolve(behavior_ref)
        return {
            "methodology_id": binding.methodology_id,
            "methodology_version": binding.methodology_version,
            "behavior_id": binding.behavior_id,
            "input_contract_id": binding.input_contract_id,
            "output_contract_id": binding.output_contract_id,
            "authority_owner": binding.authority_owner,
        }


class Gate5PublishedTypedBehaviorRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy

    def create(self) -> "Gate5PublishedTypedBehaviorRuntime":
        return Gate5PublishedTypedBehaviorRuntime(
            registry=Gate5PublishedTypedBehaviorRegistryFactory.create(),
            calculation_runtime=Gate5TrustedMethodologyCalculationRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create(),
            operation_runtime=Gate5SecuritiesDisposalTaxModelRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create(),
            aggregation_runtime=(
                Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
            ),
            income_group_runtime=Gate5IncomeGroupTaxBaseRuntimeFactory.create(),
        )


class Gate5PublishedTypedBehaviorRuntime:
    def __init__(
        self,
        *,
        registry: Gate5PublishedTypedBehaviorRegistry,
        calculation_runtime: Gate5TrustedMethodologyCalculationRuntime,
        operation_runtime: Gate5SecuritiesDisposalTaxModelRuntime,
        aggregation_runtime: Gate5TaxPeriodCategoryAggregationRuntime,
        income_group_runtime: Gate5IncomeGroupTaxBaseRuntime,
    ) -> None:
        self._registry = registry
        self._calculation_runtime = calculation_runtime
        self._operation_runtime = operation_runtime
        self._aggregation_runtime = aggregation_runtime
        self._income_group_runtime = income_group_runtime

    def execute(
        self,
        *,
        behavior_ref: dict[str, Any],
        input_contract_id: str,
        output_contract_id: str,
        behavior_input: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        binding = self._resolve_exact_contracts(
            behavior_ref=behavior_ref,
            input_contract_id=input_contract_id,
            output_contract_id=output_contract_id,
        )
        if not isinstance(context, ArtifactAccessContext):
            _fail("gate5_published_typed_behavior_context_invalid")
        methodology_ref = _methodology_ref(binding)

        if binding.implementation_binding_id == _CALCULATION_IMPLEMENTATION_BINDING:
            _validate_no_additional_input(behavior_input)
            raw_payload = self._calculation_runtime.calculate(
                methodology_ref=methodology_ref,
                context=context,
            )
        elif (
            binding.implementation_binding_id == _OPERATION_MODEL_IMPLEMENTATION_BINDING
        ):
            raw_result = self._operation_runtime.run_operation(
                methodology_ref=methodology_ref,
                resolved_inputs=behavior_input,
                context=context,
            )
            raw_payload = _operation_result_payload(raw_result)
        elif (
            binding.implementation_binding_id
            == _INCOME_GROUP_TAX_BASE_IMPLEMENTATION_BINDING
        ):
            raw_payload = self._income_group_runtime.run(
                methodology_ref=methodology_ref,
                behavior_input=behavior_input,
            )
        else:
            _fail("gate5_published_typed_behavior_binding_invalid")

        payload, artifact_binding = self._validated_registered_output(
            binding=binding,
            payload=raw_payload,
        )
        return {
            "schema_version": GATE5_TYPED_BEHAVIOR_RESULT_SCHEMA_VERSION,
            "status": "executed",
            "behavior_binding": {
                "methodology_id": binding.methodology_id,
                "methodology_version": binding.methodology_version,
                "behavior_id": binding.behavior_id,
                "input_contract_id": binding.input_contract_id,
                "output_contract_id": binding.output_contract_id,
            },
            "artifact_binding": artifact_binding,
            "provenance": {
                "retention": "exact_in_result_payload",
                "source_kinds": sorted(_source_kinds(payload)),
                "includes_methodology_derived_result": True,
            },
            "result_payload": payload,
        }

    def validate_registered_output(
        self,
        *,
        behavior_ref: dict[str, Any],
        input_contract_id: str,
        output_contract_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Expose deterministic output validation without publishing execution."""
        binding = self._resolve_exact_contracts(
            behavior_ref=behavior_ref,
            input_contract_id=input_contract_id,
            output_contract_id=output_contract_id,
        )
        validated, _artifact_binding = self._validated_registered_output(
            binding=binding,
            payload=payload,
        )
        return validated

    def _resolve_exact_contracts(
        self,
        *,
        behavior_ref: dict[str, Any],
        input_contract_id: str,
        output_contract_id: str,
    ) -> _PublishedTypedBehaviorBinding:
        binding = self._registry.resolve(behavior_ref)
        if not _identifier(input_contract_id):
            _fail("gate5_published_typed_behavior_input_contract_invalid")
        if not _identifier(output_contract_id):
            _fail("gate5_published_typed_behavior_output_contract_invalid")
        if input_contract_id != binding.input_contract_id:
            _fail("gate5_published_typed_behavior_input_contract_mismatch")
        if output_contract_id != binding.output_contract_id:
            _fail("gate5_published_typed_behavior_output_contract_mismatch")
        return binding

    def _validated_registered_output(
        self,
        *,
        binding: _PublishedTypedBehaviorBinding,
        payload: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if binding.implementation_binding_id == _CALCULATION_IMPLEMENTATION_BINDING:
            validated = _validated_calculation_payload(payload, binding=binding)
            artifact_binding = validated["authority_binding"]
        elif (
            binding.implementation_binding_id == _OPERATION_MODEL_IMPLEMENTATION_BINDING
        ):
            if not isinstance(payload, dict):
                _fail("gate5_published_typed_behavior_output_validation_failed")
            try:
                validated = self._aggregation_runtime.validate_operation_member(
                    tax_model=payload
                )
            except ValueError as exc:
                raise Gate5PublishedTypedBehaviorError(
                    "gate5_published_typed_behavior_output_validation_failed"
                ) from exc
            artifact_binding = validated.get("methodology_binding")
            if (
                not isinstance(artifact_binding, dict)
                or artifact_binding.get("methodology_id") != binding.methodology_id
                or artifact_binding.get("methodology_version")
                != binding.methodology_version
                or artifact_binding.get("behavior_id") != binding.behavior_id
            ):
                _fail("gate5_published_typed_behavior_output_validation_failed")
        elif (
            binding.implementation_binding_id
            == _INCOME_GROUP_TAX_BASE_IMPLEMENTATION_BINDING
        ):
            try:
                validated = self._income_group_runtime.validate_model(
                    methodology_ref=_methodology_ref(binding),
                    tax_base_model=payload,
                )
            except ValueError as exc:
                raise Gate5PublishedTypedBehaviorError(
                    "gate5_published_typed_behavior_output_validation_failed"
                ) from exc
            artifact_binding = validated.get("methodology_binding")
            if (
                not isinstance(artifact_binding, dict)
                or artifact_binding.get("methodology_id") != binding.methodology_id
                or artifact_binding.get("methodology_version")
                != binding.methodology_version
                or artifact_binding.get("behavior_id") != binding.behavior_id
            ):
                _fail("gate5_published_typed_behavior_output_validation_failed")
        else:
            _fail("gate5_published_typed_behavior_binding_invalid")
        source_kinds = _source_kinds(validated)
        if not source_kinds:
            _fail("gate5_published_typed_behavior_provenance_missing")
        return copy.deepcopy(validated), copy.deepcopy(artifact_binding)


def _validated_behavior_ref(value: Any) -> tuple[str, str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != _BEHAVIOR_REF_KEYS
        or value.get("schema_version") != GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION
        or not _identifier(value.get("methodology_id"))
        or not _identifier(value.get("methodology_version"))
        or not _identifier(value.get("behavior_id"))
    ):
        _fail("gate5_published_typed_behavior_ref_invalid")
    return (
        value["methodology_id"],
        value["methodology_version"],
        value["behavior_id"],
    )


def _methodology_ref(binding: _PublishedTypedBehaviorBinding) -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": binding.methodology_id,
        "methodology_version": binding.methodology_version,
    }


def _validate_no_additional_input(value: Any) -> None:
    if value != {"schema_version": GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION}:
        _fail("gate5_published_typed_behavior_input_validation_failed")


def _operation_result_payload(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "status", "tax_model"}
        or value.get("schema_version")
        != GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_RESULT_SCHEMA_VERSION
        or value.get("status") != "modeled"
        or not isinstance(value.get("tax_model"), dict)
    ):
        _fail("gate5_published_typed_behavior_output_validation_failed")
    return value["tax_model"]


def _validated_calculation_payload(
    value: Any,
    *,
    binding: _PublishedTypedBehaviorBinding,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value)
        != {"schema_version", "status", "authority_binding", "calculation_result"}
        or value.get("schema_version")
        != GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION
        or value.get("status") != "calculated"
    ):
        _fail("gate5_published_typed_behavior_output_validation_failed")
    authority = value.get("authority_binding")
    calculation = value.get("calculation_result")
    if (
        not isinstance(authority, dict)
        or set(authority) != _AUTHORITY_BINDING_KEYS
        or authority.get("authority_owner") != binding.authority_owner
        or authority.get("methodology_id") != binding.methodology_id
        or authority.get("methodology_version") != binding.methodology_version
        or not _sha256(authority.get("resource_sha256"))
        or not _sha256(authority.get("projection_sha256"))
        or not isinstance(calculation, dict)
        or set(calculation) != _CALCULATION_RESULT_KEYS
        or calculation.get("schema_version") != GATE5_CALCULATION_RESULT_SCHEMA_VERSION
        or calculation.get("status") != "calculated"
        or not isinstance(calculation.get("inputs"), list)
        or not calculation["inputs"]
        or not isinstance(calculation.get("outputs"), dict)
        or not calculation["outputs"]
    ):
        _fail("gate5_published_typed_behavior_output_validation_failed")
    methodology_binding = calculation.get("methodology_binding")
    calculation_binding = calculation.get("calculation_binding")
    if (
        not isinstance(methodology_binding, dict)
        or methodology_binding
        != {
            "methodology_id": binding.methodology_id,
            "methodology_version": binding.methodology_version,
            "projection_sha256": authority["projection_sha256"],
        }
        or not isinstance(calculation_binding, dict)
        or calculation_binding.get("behavior_id") != binding.behavior_id
    ):
        _fail("gate5_published_typed_behavior_output_validation_failed")
    return copy.deepcopy(value)


def _source_kinds(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        source_kind = value.get("source_kind")
        if isinstance(source_kind, str):
            result.add(source_kind)
        for item in value.values():
            result.update(_source_kinds(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_source_kinds(item))
    return result


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _fail(code: str) -> None:
    raise Gate5PublishedTypedBehaviorError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_NO_ADDITIONAL_BEHAVIOR_INPUT_SCHEMA_VERSION",
    "GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION",
    "GATE5_PUBLISHED_TYPED_BEHAVIOR_BINDING_ID",
    "GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID",
    "GATE5_TYPED_BEHAVIOR_RESULT_SCHEMA_VERSION",
    "Gate5PublishedTypedBehaviorError",
    "Gate5PublishedTypedBehaviorRegistry",
    "Gate5PublishedTypedBehaviorRegistryFactory",
    "Gate5PublishedTypedBehaviorRuntime",
    "Gate5PublishedTypedBehaviorRuntimeFactory",
]
