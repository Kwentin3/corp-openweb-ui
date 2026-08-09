"""One methodology-selected deterministic calculation over satisfied G5 inputs."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate5_combined_requirement_check import (
    GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION,
)
from .gate5_supplemental_fact_discovery import (
    Gate5SupplementalFactDiscoveryRuntime,
    Gate5SupplementalFactDiscoveryRuntimeFactory,
)


GATE5_CALCULATION_METHODOLOGY_SCHEMA_VERSION = (
    "broker_reports_gate5_calculation_methodology_v0"
)
GATE5_CALCULATION_RESULT_SCHEMA_VERSION = "broker_reports_gate5_calculation_result_v0"
GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID = "security_disposal_net_result_v0"

FACTORY_REQUIRED = (
    "Gate5MethodologyCalculationRuntimeFactory.create",
    "Gate5SupplementalFactDiscoveryRuntimeFactory.create supplies satisfied inputs",
)
FORBIDDEN = (
    "direct Gate 4, ArtifactStore, SQL, source or provider reads",
    "LLM arithmetic, executable methodology, rules DSL or runtime code generation",
    "calculation fallback, inferred requirement binding or unsupported behavior execution",
    "Tax Engine, Tax Case, workflow, relation graph, registry, DB or persistence",
)

_METHODOLOGY_KEYS = frozenset(
    {
        "schema_version",
        "methodology_id",
        "methodology_version",
        "calculation",
        "requirements",
    }
)
_CALCULATION_KEYS = frozenset(
    {"calculation_id", "rule_id", "behavior_id", "input_bindings"}
)
_BINDING_KEYS = frozenset({"amount_requirement_id", "currency_requirement_id"})
_BEHAVIOR_INPUTS = frozenset({"proceeds", "acquisition_cost", "transaction_expense"})
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_INPUT_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MONEY = re.compile(r"^(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,2})?$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


class Gate5MethodologyCalculationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate5MethodologyCalculationRuntimeFactory:
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

    def create(self) -> "Gate5MethodologyCalculationRuntime":
        discovery = Gate5SupplementalFactDiscoveryRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            retention_policy=self._retention_policy,
        ).create()
        return Gate5MethodologyCalculationRuntime(discovery=discovery)


class Gate5MethodologyCalculationRuntime:
    def __init__(
        self,
        *,
        discovery: Gate5SupplementalFactDiscoveryRuntime,
    ) -> None:
        self._discovery = discovery

    def calculate(
        self,
        *,
        methodology: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        projection = _validated_methodology(methodology)
        calculation = projection["calculation"]
        _require_supported_behavior(calculation["behavior_id"])
        requirement_check = self._discovery.check(
            methodology={
                "schema_version": GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION,
                "requirements": copy.deepcopy(projection["requirements"]),
            },
            context=context,
        )
        if requirement_check["summary"]["missing"] != 0:
            raise Gate5MethodologyCalculationError(
                "gate5_calculation_inputs_not_satisfied"
            )
        requirements = {
            item["requirement_id"]: item for item in requirement_check["requirements"]
        }
        inputs = _resolve_behavior_inputs(
            bindings=calculation["input_bindings"],
            requirements=requirements,
        )
        outputs = _calculate_security_disposal_net_result(inputs)
        return {
            "schema_version": GATE5_CALCULATION_RESULT_SCHEMA_VERSION,
            "status": "calculated",
            "methodology_binding": {
                "methodology_id": projection["methodology_id"],
                "methodology_version": projection["methodology_version"],
                "projection_sha256": _projection_sha256(projection),
            },
            "calculation_binding": {
                "calculation_id": calculation["calculation_id"],
                "rule_id": calculation["rule_id"],
                "behavior_id": calculation["behavior_id"],
            },
            "inputs": [copy.deepcopy(inputs[name]) for name in sorted(inputs)],
            "outputs": outputs,
        }


def _validated_methodology(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _METHODOLOGY_KEYS
        or value.get("schema_version") != GATE5_CALCULATION_METHODOLOGY_SCHEMA_VERSION
        or not _is_identifier(value.get("methodology_id"))
        or not _is_identifier(value.get("methodology_version"))
        or not isinstance(value.get("requirements"), list)
        or not value["requirements"]
    ):
        raise Gate5MethodologyCalculationError("gate5_calculation_methodology_invalid")
    calculation = _validated_calculation(value.get("calculation"))
    projection = {
        "schema_version": value["schema_version"],
        "methodology_id": value["methodology_id"],
        "methodology_version": value["methodology_version"],
        "calculation": calculation,
        "requirements": copy.deepcopy(value["requirements"]),
    }
    try:
        _canonical_json(projection)
    except (RecursionError, TypeError, ValueError) as exc:
        raise Gate5MethodologyCalculationError(
            "gate5_calculation_methodology_invalid"
        ) from exc
    return projection


def _validated_calculation(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _CALCULATION_KEYS
        or not _is_identifier(value.get("calculation_id"))
        or not _is_identifier(value.get("rule_id"))
        or not _is_identifier(value.get("behavior_id"))
        or not isinstance(value.get("input_bindings"), dict)
        or not value["input_bindings"]
    ):
        raise Gate5MethodologyCalculationError("gate5_calculation_methodology_invalid")
    bindings: dict[str, dict[str, str]] = {}
    for input_name, raw_binding in value["input_bindings"].items():
        if (
            not isinstance(input_name, str)
            or _INPUT_NAME.fullmatch(input_name) is None
            or not isinstance(raw_binding, dict)
            or set(raw_binding) != _BINDING_KEYS
            or not _is_identifier(raw_binding.get("amount_requirement_id"))
            or not _is_identifier(raw_binding.get("currency_requirement_id"))
        ):
            raise Gate5MethodologyCalculationError(
                "gate5_calculation_methodology_invalid"
            )
        bindings[input_name] = {
            "amount_requirement_id": raw_binding["amount_requirement_id"],
            "currency_requirement_id": raw_binding["currency_requirement_id"],
        }
    return {
        "calculation_id": value["calculation_id"],
        "rule_id": value["rule_id"],
        "behavior_id": value["behavior_id"],
        "input_bindings": bindings,
    }


def _require_supported_behavior(behavior_id: str) -> None:
    if behavior_id != GATE5_SECURITY_DISPOSAL_NET_RESULT_BEHAVIOR_ID:
        raise Gate5MethodologyCalculationError("gate5_calculation_behavior_unsupported")


def _resolve_behavior_inputs(
    *,
    bindings: dict[str, dict[str, str]],
    requirements: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if set(bindings) != _BEHAVIOR_INPUTS:
        raise Gate5MethodologyCalculationError(
            "gate5_calculation_behavior_inputs_invalid"
        )
    return {
        input_name: _resolve_money_input(
            input_name=input_name,
            binding=bindings[input_name],
            requirements=requirements,
        )
        for input_name in sorted(bindings)
    }


def _resolve_money_input(
    *,
    input_name: str,
    binding: dict[str, str],
    requirements: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    amount_ref = binding["amount_requirement_id"]
    currency_ref = binding["currency_requirement_id"]
    amount_requirement = requirements.get(amount_ref)
    currency_requirement = requirements.get(currency_ref)
    if (
        not isinstance(amount_requirement, dict)
        or not isinstance(currency_requirement, dict)
        or amount_requirement.get("status") != "satisfied"
        or currency_requirement.get("status") != "satisfied"
        or amount_requirement.get("subject_ref")
        != currency_requirement.get("subject_ref")
    ):
        raise Gate5MethodologyCalculationError(
            "gate5_calculation_input_binding_invalid"
        )
    amount = _source_amount(amount_requirement)
    currency = _source_currency(currency_requirement)
    canonical_amount = _canonical_amount(amount)
    if not isinstance(currency, str) or _CURRENCY.fullmatch(currency) is None:
        raise Gate5MethodologyCalculationError("gate5_calculation_input_money_invalid")
    refs = list(dict.fromkeys((amount_ref, currency_ref)))
    return {
        "input_name": input_name,
        "requirement_refs": refs,
        "value": {
            "kind": "money",
            "amount": canonical_amount,
            "currency": currency,
        },
        "sources": [
            {
                "requirement_id": requirement_ref,
                "source": copy.deepcopy(requirements[requirement_ref]["source"]),
            }
            for requirement_ref in refs
        ],
    }


def _source_amount(requirement: dict[str, Any]) -> Any:
    source = requirement.get("source")
    if not isinstance(source, dict):
        raise Gate5MethodologyCalculationError("gate5_calculation_input_source_invalid")
    if source.get("source_kind") == "financial_case":
        return _one_financial_value(source)
    value = source.get("value")
    if (
        source.get("source_kind") != "supplemental_fact"
        or not isinstance(value, dict)
        or value.get("kind") != "money"
    ):
        raise Gate5MethodologyCalculationError("gate5_calculation_input_source_invalid")
    return value.get("amount")


def _source_currency(requirement: dict[str, Any]) -> Any:
    source = requirement.get("source")
    if not isinstance(source, dict):
        raise Gate5MethodologyCalculationError("gate5_calculation_input_source_invalid")
    if source.get("source_kind") == "financial_case":
        return _one_financial_value(source)
    value = source.get("value")
    if (
        source.get("source_kind") != "supplemental_fact"
        or not isinstance(value, dict)
        or value.get("kind") != "money"
    ):
        raise Gate5MethodologyCalculationError("gate5_calculation_input_source_invalid")
    return value.get("currency")


def _one_financial_value(source: dict[str, Any]) -> str:
    matches = source.get("matches")
    if (
        not isinstance(matches, list)
        or len(matches) != 1
        or not isinstance(matches[0], dict)
        or not isinstance(matches[0].get("value"), str)
    ):
        raise Gate5MethodologyCalculationError(
            "gate5_calculation_financial_value_not_scalar"
        )
    return matches[0]["value"]


def _canonical_amount(value: Any) -> str:
    if not isinstance(value, str) or _MONEY.fullmatch(value) is None:
        raise Gate5MethodologyCalculationError("gate5_calculation_input_money_invalid")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise Gate5MethodologyCalculationError(
            "gate5_calculation_input_money_invalid"
        ) from exc
    return f"{amount:.2f}"


def _calculate_security_disposal_net_result(
    inputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    currencies = {item["value"]["currency"] for item in inputs.values()}
    if len(currencies) != 1:
        raise Gate5MethodologyCalculationError(
            "gate5_calculation_input_currency_mismatch"
        )
    currency = next(iter(currencies))
    proceeds = Decimal(inputs["proceeds"]["value"]["amount"])
    acquisition_cost = Decimal(inputs["acquisition_cost"]["value"]["amount"])
    transaction_expense = Decimal(inputs["transaction_expense"]["value"]["amount"])
    recognized_expense = acquisition_cost + transaction_expense
    net_result = proceeds - recognized_expense
    return {
        "proceeds": _money_output(proceeds, currency),
        "recognized_expense": _money_output(recognized_expense, currency),
        "net_result": _money_output(net_result, currency),
    }


def _money_output(amount: Decimal, currency: str) -> dict[str, str]:
    return {
        "kind": "money",
        "amount": f"{amount:.2f}",
        "currency": currency,
    }


def _projection_sha256(projection: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(projection)).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _is_identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None
