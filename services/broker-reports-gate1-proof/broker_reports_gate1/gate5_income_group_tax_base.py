"""Calculate one complete stable income-group tax base without form projection."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any

from .gate5_tax_period_category_aggregation import (
    Gate5TaxPeriodCategoryAggregationRuntime,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
from .gate5_trusted_methodology import (
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthority,
    Gate5TrustedMethodologyAuthorityFactory,
    Gate5TrustedMethodologyError,
)


GATE5_INCOME_GROUP_TAX_BASE_BEHAVIOR_ID = (
    "securities_income_group_tax_base_v0"
)
GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_base_input_v0"
)
GATE5_INCOME_GROUP_TAX_BASE_INPUT_BINDING_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_base_input_binding_v0"
)
GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_base_completeness_v0"
)
GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_base_model_v0"
)

FACTORY_REQUIRED = (
    "Gate5IncomeGroupTaxBaseRuntimeFactory.create owns the calculation",
    "Gate5TrustedMethodologyAuthorityFactory.create owns methodology resolution",
    "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create owns category validation",
)
FORBIDDEN = (
    "raw Gate 4, operation models, ArtifactStore, SQL, source or provider reads",
    "implicit zero, inferred group completeness, silent reduction cap or fallback",
    "declaration section, line, XML, PDF, form code, rate or calculated tax",
    "caller-supplied formula, rule language, implementation, schema or LLM",
)

_INPUT_KEYS = {
    "schema_version",
    "category_tax_model",
    "taxpayer_status",
    "group_values",
    "completeness_evidence",
}
_GROUP_VALUE_KEYS = {
    "other_group_income",
    "other_group_allowable_expenses",
    "non_taxable_income",
    "tax_deductions",
}
_COMPLETENESS_KEYS = {
    "schema_version",
    "status",
    "coverage_kind",
    "input_binding_sha256",
    "provenance",
}
_MODEL_KEYS = {
    "schema_version",
    "status",
    "model_id",
    "model_kind",
    "calculation_scope",
    "methodology_binding",
    "input_snapshot",
    "total_income",
    "taxable_income",
    "accepted_expenses",
    "tax_base",
}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_AMOUNT = re.compile(r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Gate5IncomeGroupTaxBaseError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5IncomeGroupTaxBaseRuntimeFactory:
    @staticmethod
    def create() -> "Gate5IncomeGroupTaxBaseRuntime":
        return Gate5IncomeGroupTaxBaseRuntime(
            authority=Gate5TrustedMethodologyAuthorityFactory.create(),
            aggregation=Gate5TaxPeriodCategoryAggregationRuntimeFactory.create(),
        )


class Gate5IncomeGroupTaxBaseRuntime:
    def __init__(
        self,
        *,
        authority: Gate5TrustedMethodologyAuthority,
        aggregation: Gate5TaxPeriodCategoryAggregationRuntime,
    ) -> None:
        self._authority = authority
        self._aggregation = aggregation

    def describe_input(
        self,
        *,
        category_tax_model: dict[str, Any],
        taxpayer_status: dict[str, Any],
        group_values: dict[str, Any],
    ) -> dict[str, str]:
        """Return the exact binding that group-completeness evidence must attest."""
        snapshot = self._validated_input_snapshot(
            category_tax_model=category_tax_model,
            taxpayer_status=taxpayer_status,
            group_values=group_values,
        )
        return _input_binding(snapshot)

    def run(
        self,
        *,
        methodology_ref: dict[str, Any],
        behavior_input: dict[str, Any],
    ) -> dict[str, Any]:
        resolved = self._resolved_methodology(methodology_ref)
        validated = self._validated_behavior_input(behavior_input)
        _require_applicability(
            methodology=resolved["methodology"],
            input_snapshot=validated["input_snapshot"],
        )
        return _build_model(
            methodology=resolved["methodology"],
            authority_binding=resolved["authority_binding"],
            input_snapshot=validated["input_snapshot"],
            input_binding=validated["input_binding"],
            completeness=validated["completeness"],
        )

    def validate_model(
        self,
        *,
        methodology_ref: dict[str, Any],
        tax_base_model: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate a published result by deterministically rebuilding it."""
        resolved = self._resolved_methodology(methodology_ref)
        if not isinstance(tax_base_model, dict) or set(tax_base_model) != _MODEL_KEYS:
            _fail("gate5_income_group_tax_base_model_invalid")
        snapshot = tax_base_model.get("input_snapshot")
        calculation_scope = tax_base_model.get("calculation_scope")
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "category_tax_model",
            "taxpayer_status",
            "group_values",
        }:
            _fail("gate5_income_group_tax_base_model_invalid", "input_snapshot")
        if not isinstance(calculation_scope, dict):
            _fail("gate5_income_group_tax_base_model_invalid", "calculation_scope")
        behavior_input = {
            "schema_version": GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
            **copy.deepcopy(snapshot),
            "completeness_evidence": copy.deepcopy(
                calculation_scope.get("completeness_evidence")
            ),
        }
        validated = self._validated_behavior_input(behavior_input)
        _require_applicability(
            methodology=resolved["methodology"],
            input_snapshot=validated["input_snapshot"],
        )
        expected = _build_model(
            methodology=resolved["methodology"],
            authority_binding=resolved["authority_binding"],
            input_snapshot=validated["input_snapshot"],
            input_binding=validated["input_binding"],
            completeness=validated["completeness"],
        )
        if tax_base_model != expected:
            _fail("gate5_income_group_tax_base_model_mismatch")
        return copy.deepcopy(expected)

    def _resolved_methodology(
        self, methodology_ref: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            resolved = self._authority.resolve(methodology_ref)
        except Gate5TrustedMethodologyError as exc:
            raise Gate5IncomeGroupTaxBaseError(
                "gate5_income_group_tax_base_methodology_unavailable"
            ) from exc
        _validated_methodology(
            resolved["methodology"],
            authority_binding=resolved["authority_binding"],
        )
        return resolved

    def _validated_behavior_input(self, value: Any) -> dict[str, Any]:
        if (
            not isinstance(value, dict)
            or set(value) != _INPUT_KEYS
            or value.get("schema_version")
            != GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION
        ):
            _fail("gate5_income_group_tax_base_input_invalid")
        snapshot = self._validated_input_snapshot(
            category_tax_model=value.get("category_tax_model"),
            taxpayer_status=value.get("taxpayer_status"),
            group_values=value.get("group_values"),
        )
        binding = _input_binding(snapshot)
        completeness = _completeness(
            value.get("completeness_evidence"),
            input_binding_sha256=binding["input_binding_sha256"],
        )
        return {
            "input_snapshot": snapshot,
            "input_binding": binding,
            "completeness": completeness,
        }

    def _validated_input_snapshot(
        self,
        *,
        category_tax_model: Any,
        taxpayer_status: Any,
        group_values: Any,
    ) -> dict[str, Any]:
        try:
            category = self._aggregation.validate_category_model(
                tax_model=category_tax_model
            )
        except ValueError as exc:
            raise Gate5IncomeGroupTaxBaseError(
                "gate5_income_group_tax_base_category_model_invalid"
            ) from exc
        status = _tagged_scalar(
            taxpayer_status,
            field="taxpayer_status",
            input_channel="taxpayer_status",
            expected_source_kind="methodology_derived_result",
        )
        if not isinstance(group_values, dict) or set(group_values) != _GROUP_VALUE_KEYS:
            _fail("gate5_income_group_tax_base_group_values_invalid")
        values = {
            name: _tagged_money(group_values.get(name), field=name)
            for name in sorted(_GROUP_VALUE_KEYS)
        }
        currencies = {
            category["category_gross_income"]["value"]["currency"],
            category["allowable_expenses"]["value"]["currency"],
            *(item["value"]["currency"] for item in values.values()),
        }
        if len(currencies) != 1:
            _fail("gate5_income_group_tax_base_currency_mismatch")
        return {
            "category_tax_model": category,
            "taxpayer_status": status,
            "group_values": values,
        }


def _validated_methodology(
    value: Any,
    *,
    authority_binding: dict[str, Any],
) -> None:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "methodology_id",
            "methodology_version",
            "behavior",
            "legal_evidence",
        }
        or value.get("schema_version")
        != GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_SCHEMA_VERSION
        or value.get("methodology_id")
        != GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID
        or value.get("methodology_id") != authority_binding.get("methodology_id")
        or value.get("methodology_version")
        != authority_binding.get("methodology_version")
    ):
        _fail("gate5_income_group_tax_base_methodology_invalid")
    behavior = value.get("behavior")
    if (
        not isinstance(behavior, dict)
        or set(behavior)
        != {
            "behavior_id",
            "model_id",
            "input_contract_id",
            "output_contract_id",
            "applicability",
            "calculation_semantics",
            "required_evidence_refs",
        }
        or behavior.get("behavior_id") != GATE5_INCOME_GROUP_TAX_BASE_BEHAVIOR_ID
        or behavior.get("model_id") != "securities-income-group-tax-base"
        or behavior.get("input_contract_id")
        != GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION
        or behavior.get("output_contract_id")
        != GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION
        or not isinstance(behavior.get("required_evidence_refs"), list)
        or len(behavior["required_evidence_refs"]) != 1
        or not _identifier(behavior["required_evidence_refs"][0])
    ):
        _fail("gate5_income_group_tax_base_methodology_invalid")
    applicability = behavior.get("applicability")
    if (
        not isinstance(applicability, dict)
        or set(applicability)
        != {
            "tax_period",
            "taxpayer_status",
            "category",
            "currency",
            "income_group_semantic",
        }
        or not all(_identifier(item) for item in applicability.values())
    ):
        _fail("gate5_income_group_tax_base_methodology_invalid")
    semantics = behavior.get("calculation_semantics")
    if (
        not isinstance(semantics, dict)
        or set(semantics)
        != {
            "total_income",
            "taxable_income",
            "accepted_expenses",
            "tax_base",
            "reduction_guard",
        }
        or not all(isinstance(item, str) and item for item in semantics.values())
    ):
        _fail("gate5_income_group_tax_base_methodology_invalid")
    evidence = value.get("legal_evidence")
    if (
        not isinstance(evidence, list)
        or len(evidence) != 1
        or not isinstance(evidence[0], dict)
        or evidence[0].get("evidence_ref")
        != behavior["required_evidence_refs"][0]
        or evidence[0].get("authority_kind") != "tax_authority_primary"
        or evidence[0].get("capture_status")
        != "downloaded_official_bytes_verified"
        or evidence[0].get("effective_tax_period")
        != applicability["tax_period"]
        or not isinstance(evidence[0].get("source_url"), str)
        or not evidence[0]["source_url"].startswith("https://www.nalog.gov.ru/")
        or not isinstance(evidence[0].get("content_bytes"), int)
        or evidence[0]["content_bytes"] <= 0
        or not isinstance(evidence[0].get("content_sha256"), str)
        or _SHA256.fullmatch(evidence[0]["content_sha256"]) is None
    ):
        _fail("gate5_income_group_tax_base_methodology_evidence_invalid")


def _input_binding(snapshot: dict[str, Any]) -> dict[str, str]:
    category_sha256 = _canonical_sha256(snapshot["category_tax_model"])
    context_sha256 = _canonical_sha256(
        {
            "taxpayer_status": snapshot["taxpayer_status"],
            "group_values": snapshot["group_values"],
        }
    )
    identity = {
        "schema_version": GATE5_INCOME_GROUP_TAX_BASE_INPUT_BINDING_SCHEMA_VERSION,
        "category_tax_model_sha256": category_sha256,
        "group_context_sha256": context_sha256,
    }
    return {
        **identity,
        "input_binding_sha256": _canonical_sha256(identity),
    }


def _completeness(value: Any, *, input_binding_sha256: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _COMPLETENESS_KEYS
        or value.get("schema_version")
        != GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION
        or value.get("status") != "asserted_complete"
        or value.get("coverage_kind")
        != "all_income_and_reductions_in_stable_income_group"
        or value.get("input_binding_sha256") != input_binding_sha256
    ):
        _fail("gate5_income_group_tax_base_completeness_invalid")
    _provenance(
        value.get("provenance"),
        input_channel="income_group_completeness",
        expected_source_kind="user_verified_fact",
    )
    return copy.deepcopy(value)


def _require_applicability(
    *,
    methodology: dict[str, Any],
    input_snapshot: dict[str, Any],
) -> None:
    expected = methodology["behavior"]["applicability"]
    category = input_snapshot["category_tax_model"]
    actual = {
        "tax_period": category["calculation_scope"]["tax_period"],
        "taxpayer_status": input_snapshot["taxpayer_status"]["value"],
        "category": category["operation_category"]["value"],
        "currency": category["category_gross_income"]["value"]["currency"],
    }
    for name, expected_value in expected.items():
        if name == "income_group_semantic":
            continue
        if actual.get(name) != expected_value:
            _fail("gate5_income_group_tax_base_applicability_unsupported", name)


def _build_model(
    *,
    methodology: dict[str, Any],
    authority_binding: dict[str, Any],
    input_snapshot: dict[str, Any],
    input_binding: dict[str, str],
    completeness: dict[str, Any],
) -> dict[str, Any]:
    category = input_snapshot["category_tax_model"]
    values = input_snapshot["group_values"]
    currency = category["category_gross_income"]["value"]["currency"]
    category_income = _decimal(
        category["category_gross_income"]["value"]["amount"]
    )
    other_income = _decimal(values["other_group_income"]["value"]["amount"])
    non_taxable = _decimal(values["non_taxable_income"]["value"]["amount"])
    category_expenses = _decimal(
        category["allowable_expenses"]["value"]["amount"]
    )
    other_expenses = _decimal(
        values["other_group_allowable_expenses"]["value"]["amount"]
    )
    deductions = _decimal(values["tax_deductions"]["value"]["amount"])

    total_income = category_income + other_income
    if non_taxable > total_income:
        _fail("gate5_income_group_tax_base_non_taxable_exceeds_income")
    taxable_income = total_income - non_taxable
    accepted_expenses = category_expenses + other_expenses
    if deductions + accepted_expenses > taxable_income:
        _fail("gate5_income_group_tax_base_reductions_exceed_taxable_income")
    tax_base = taxable_income - deductions - accepted_expenses
    behavior = methodology["behavior"]

    def derived(
        amount: Decimal,
        semantic_id: str,
        input_refs: list[str],
    ) -> dict[str, Any]:
        return {
            "value": _money(amount, currency),
            "derivation": {
                "source_kind": "methodology_derived",
                "semantic_id": semantic_id,
                "definition": behavior["calculation_semantics"][semantic_id],
                "input_refs": input_refs,
                "methodology_projection_sha256": authority_binding[
                    "projection_sha256"
                ],
            },
        }

    return {
        "schema_version": GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
        "status": "complete",
        "model_id": behavior["model_id"],
        "model_kind": "stable_income_group_tax_base",
        "calculation_scope": {
            "taxpayer_scope_ref": category["calculation_scope"][
                "taxpayer_scope_ref"
            ],
            "tax_period": category["calculation_scope"]["tax_period"],
            "operation_category": category["operation_category"]["value"],
            "income_group_semantic": behavior["applicability"][
                "income_group_semantic"
            ],
            "input_binding": copy.deepcopy(input_binding),
            "completeness_evidence": copy.deepcopy(completeness),
        },
        "methodology_binding": {
            **copy.deepcopy(authority_binding),
            "behavior_id": behavior["behavior_id"],
        },
        "input_snapshot": copy.deepcopy(input_snapshot),
        "total_income": derived(
            total_income,
            "total_income",
            ["category_tax_model.category_gross_income", "other_group_income"],
        ),
        "taxable_income": derived(
            taxable_income,
            "taxable_income",
            ["total_income", "non_taxable_income"],
        ),
        "accepted_expenses": derived(
            accepted_expenses,
            "accepted_expenses",
            [
                "category_tax_model.allowable_expenses",
                "other_group_allowable_expenses",
            ],
        ),
        "tax_base": derived(
            tax_base,
            "tax_base",
            ["taxable_income", "tax_deductions", "accepted_expenses"],
        ),
    }


def _tagged_scalar(
    value: Any,
    *,
    field: str,
    input_channel: str,
    expected_source_kind: str,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"value", "provenance"}
        or not _identifier(value.get("value"))
    ):
        _fail("gate5_income_group_tax_base_fact_invalid", field)
    _provenance(
        value.get("provenance"),
        input_channel=input_channel,
        expected_source_kind=expected_source_kind,
    )
    if not value["provenance"]["source_ref"].startswith(
        "residency-classification:"
    ):
        _fail("gate5_income_group_tax_base_residency_classification_required")
    return copy.deepcopy(value)


def _tagged_money(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"value", "provenance"}:
        _fail("gate5_income_group_tax_base_fact_invalid", field)
    _money_value(value.get("value"), field=field)
    _provenance(
        value.get("provenance"),
        input_channel="income_group_tax_base",
        expected_source_kind="user_verified_fact",
    )
    return copy.deepcopy(value)


def _money_value(value: Any, *, field: str) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != {"kind", "amount", "currency"}
        or value.get("kind") != "money"
        or not isinstance(value.get("amount"), str)
        or _AMOUNT.fullmatch(value["amount"]) is None
        or not isinstance(value.get("currency"), str)
        or _CURRENCY.fullmatch(value["currency"]) is None
    ):
        _fail("gate5_income_group_tax_base_money_invalid", field)
    return value


def _provenance(
    value: Any, *, input_channel: str, expected_source_kind: str
) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"source_kind", "source_ref", "input_channel"}
        or value.get("source_kind") != expected_source_kind
        or not _identifier(value.get("source_ref"))
        or value.get("input_channel") != input_channel
    ):
        _fail("gate5_income_group_tax_base_provenance_invalid")


def _money(amount: Decimal, currency: str) -> dict[str, str]:
    return {"kind": "money", "amount": f"{amount:.2f}", "currency": currency}


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise Gate5IncomeGroupTaxBaseError(
            "gate5_income_group_tax_base_money_invalid"
        ) from exc


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _canonical_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, TypeError, ValueError) as exc:
        raise Gate5IncomeGroupTaxBaseError(
            "gate5_income_group_tax_base_input_invalid"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _fail(code: str, field: str = "") -> None:
    raise Gate5IncomeGroupTaxBaseError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_INCOME_GROUP_TAX_BASE_BEHAVIOR_ID",
    "GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION",
    "GATE5_INCOME_GROUP_TAX_BASE_INPUT_BINDING_SCHEMA_VERSION",
    "GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION",
    "GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION",
    "Gate5IncomeGroupTaxBaseError",
    "Gate5IncomeGroupTaxBaseRuntime",
    "Gate5IncomeGroupTaxBaseRuntimeFactory",
]
