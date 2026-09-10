"""Shared, storage-free derivation of unresolved operation-set demands."""

from __future__ import annotations

from typing import Any

from .artifact_models import ArtifactAccessContext
from .gate5_deterministic_source_fact_consumption import (
    gate5_source_fact_acquisition_commission_fact_ids,
)


def derive_operation_set_demands(
    *, operation_results: list[dict[str, Any]], context: ArtifactAccessContext
) -> list[dict[str, Any]]:
    demands: list[dict[str, Any]] = []
    for item in operation_results:
        demands.extend(
            derive_operation_expense_demands(
                item["operation_result"],
                disposal_fact_id=item["disposal_fact_id"],
                context=context,
            )
        )
    return demands


def derive_operation_expense_demands(
    operation_result: dict[str, Any],
    *,
    disposal_fact_id: str,
    context: ArtifactAccessContext,
) -> list[dict[str, Any]]:
    demands = []
    tax_model = operation_result["tax_model"]
    decisions = tax_model.get("allowable_expenses", {}).get("decisions", [])
    for decision in decisions:
        for flag in decision.get("failed_prerequisites", []):
            demands.append(
                {
                    "schema_version": "broker_reports_tax_model_bridge_demand_v0",
                    "required_input": f"{decision['component_id']}.{flag}",
                    "gap_owner_classification": "REAL_SOURCE_EVIDENCE_MISSING",
                    "owner": "Gate5SecuritiesDisposalTaxModelRuntime",
                    "blocking_scope": "expense_allowability_only",
                    "category_model_blocked": False,
                }
            )
    source = operation_result["source_fact_consumption"]
    capability_map = source.get("capability_map", {})
    acquisition_commission_fact_ids = (
        gate5_source_fact_acquisition_commission_fact_ids(
            source,
            disposal_fact_id=disposal_fact_id,
            context=context,
        )
    )
    if (
        acquisition_commission_fact_ids
        and capability_map.get("partial_acquisition_commission")
        == "LEGAL_INTERPRETATION_REQUIRED"
    ):
        demands.append(
            {
                "schema_version": "broker_reports_tax_model_bridge_demand_v0",
                "required_input": "partial_acquisition_commission_allocation",
                "gap_owner_classification": "LEGAL_INTERPRETATION_REQUIRED",
                "owner": "Gate5DeterministicSourceFactConsumptionRuntime",
                "blocking_scope": "expense_allowability_only",
                "category_model_blocked": False,
            }
        )
    return demands


def derive_operation_set_demands_from_sealed_scope(
    *, operation_results: list[dict[str, Any]], scope_binding: dict[str, Any]
) -> list[dict[str, Any]]:
    return derive_operation_set_demands(
        operation_results=operation_results,
        context=ArtifactAccessContext(
            user_id=scope_binding["authenticated_user_ref"],
            normalization_run_id=scope_binding["normalization_run_ref"],
            case_id=scope_binding["case_id"],
            allow_private=True,
        ),
    )


__all__ = [
    "derive_operation_expense_demands",
    "derive_operation_set_demands",
    "derive_operation_set_demands_from_sealed_scope",
]
