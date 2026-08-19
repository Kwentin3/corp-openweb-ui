"""Target-independent Declaration Semantics between Gate 5 and Projection."""

from __future__ import annotations

import copy
from typing import Any


INCOME_GROUP_DECLARATION_SEMANTICS_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_base_model_v0"
)
FACTORY_REQUIRED = (
    "DeclarationSemanticsIncomeGroupRuntimeFactory.create owns the Tax Model "
    "to target-independent declaration-semantics handoff"
)
FORBIDDEN = (
    "target paths, XML/PDF fields, serialization, provider calls, source reads "
    "or recalculation of Tax Model values"
)


class DeclarationSemanticsIncomeGroupError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DeclarationSemanticsIncomeGroupRuntimeFactory:
    @classmethod
    def create(cls) -> "DeclarationSemanticsIncomeGroupRuntime":
        # Lazy resolution avoids the retained TaxPeriod -> legacy Projection
        # compatibility import while keeping Tax Model ownership out of Projection.
        from .gate5_income_group_tax_base import (
            GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
            Gate5IncomeGroupTaxBaseError,
            Gate5IncomeGroupTaxBaseRuntimeFactory,
        )
        from .gate5_trusted_methodology import (
            GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        )

        if (
            GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION
            != INCOME_GROUP_DECLARATION_SEMANTICS_INPUT_SCHEMA_VERSION
        ):
            raise DeclarationSemanticsIncomeGroupError(
                "gate5_declaration_projection_input_contract_incompatible"
            )
        return DeclarationSemanticsIncomeGroupRuntime(
            tax_model_owner=Gate5IncomeGroupTaxBaseRuntimeFactory.create(),
            tax_model_error=Gate5IncomeGroupTaxBaseError,
            methodology_ref_schema_version=(
                GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION
            ),
        )


class DeclarationSemanticsIncomeGroupRuntime:
    def __init__(
        self,
        *,
        tax_model_owner: Any,
        tax_model_error: type[ValueError],
        methodology_ref_schema_version: str,
    ) -> None:
        self._tax_model_owner = tax_model_owner
        self._tax_model_error = tax_model_error
        self._methodology_ref_schema_version = methodology_ref_schema_version

    def validate_projection_input(
        self,
        *,
        declaration_semantics: dict[str, Any],
        input_contract: dict[str, Any],
    ) -> dict[str, Any]:
        value = declaration_semantics
        if not isinstance(value, dict):
            self._fail_invalid()
        methodology_binding = value.get("methodology_binding")
        if not isinstance(methodology_binding, dict):
            self._fail_invalid()
        methodology_id = methodology_binding.get("methodology_id")
        methodology_version = methodology_binding.get("methodology_version")
        if not _nonempty(methodology_id) or not _nonempty(methodology_version):
            self._fail_invalid()
        try:
            validated = self._tax_model_owner.validate_model(
                methodology_ref={
                    "schema_version": self._methodology_ref_schema_version,
                    "methodology_id": methodology_id,
                    "methodology_version": methodology_version,
                },
                tax_base_model=value,
            )
        except self._tax_model_error as exc:
            raise DeclarationSemanticsIncomeGroupError(
                "gate5_declaration_projection_upstream_semantics_invalid"
            ) from exc
        scope = validated["calculation_scope"]
        if (
            validated["schema_version"] != input_contract.get("schema_version")
            or validated["model_kind"] != input_contract.get("model_kind")
            or scope["income_group_semantic"]
            != input_contract.get("income_group_semantic")
        ):
            raise DeclarationSemanticsIncomeGroupError(
                "gate5_declaration_projection_input_contract_incompatible"
            )
        group_values = validated["input_snapshot"]["group_values"]
        values = {
            "income_group_semantic": scope["income_group_semantic"],
            "total_income": copy.deepcopy(validated["total_income"]["value"]),
            "non_taxable_income": copy.deepcopy(
                group_values["non_taxable_income"]["value"]
            ),
            "taxable_income": copy.deepcopy(validated["taxable_income"]["value"]),
            "tax_deductions": copy.deepcopy(
                group_values["tax_deductions"]["value"]
            ),
            "accepted_expenses": copy.deepcopy(
                validated["accepted_expenses"]["value"]
            ),
            "tax_base": copy.deepcopy(validated["tax_base"]["value"]),
        }
        traces = {
            "income_group_semantic": {
                "source_kind": "methodology_applicability",
                "methodology_binding": copy.deepcopy(
                    validated["methodology_binding"]
                ),
            },
            "total_income": copy.deepcopy(validated["total_income"]["derivation"]),
            "non_taxable_income": copy.deepcopy(
                group_values["non_taxable_income"]["provenance"]
            ),
            "taxable_income": copy.deepcopy(
                validated["taxable_income"]["derivation"]
            ),
            "tax_deductions": copy.deepcopy(
                group_values["tax_deductions"]["provenance"]
            ),
            "accepted_expenses": copy.deepcopy(
                validated["accepted_expenses"]["derivation"]
            ),
            "tax_base": copy.deepcopy(validated["tax_base"]["derivation"]),
        }
        return {
            "values": values,
            "traces": traces,
            "validated_model": validated,
        }

    @staticmethod
    def _fail_invalid() -> None:
        raise DeclarationSemanticsIncomeGroupError(
            "gate5_declaration_projection_upstream_semantics_invalid"
        )


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "INCOME_GROUP_DECLARATION_SEMANTICS_INPUT_SCHEMA_VERSION",
    "DeclarationSemanticsIncomeGroupError",
    "DeclarationSemanticsIncomeGroupRuntime",
    "DeclarationSemanticsIncomeGroupRuntimeFactory",
]
