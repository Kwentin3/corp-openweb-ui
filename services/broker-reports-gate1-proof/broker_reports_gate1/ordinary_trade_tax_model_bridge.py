"""Inactive composition from current ordinary Fact v2 to category Tax Model."""

from __future__ import annotations

import copy
import re
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate5_deterministic_source_fact_consumption import (
    Gate5DeterministicSourceFactConsumptionError,
    gate5_source_fact_acquisition_commission_fact_ids,
)
from .gate5_securities_disposal_tax_model import (
    Gate5SecuritiesDisposalTaxModelError,
    Gate5SecuritiesDisposalTaxModelRuntime,
    Gate5SecuritiesDisposalTaxModelRuntimeFactory,
)
from .gate5_tax_period_category_aggregation import (
    Gate5TaxPeriodCategoryAggregationError,
    Gate5TaxPeriodCategoryAggregationRuntime,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
from .ordinary_trade_candidate_runtime import OrdinaryTradeCandidateRuntimeFactory


ORDINARY_TRADE_TAX_MODEL_BRIDGE_RESULT_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_tax_model_bridge_result_v0"
)
ORDINARY_TRADE_TAXPAYER_BINDING_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_taxpayer_binding_v0"
)
ACTIVE_FACT_V2_TO_CATEGORY_TAX_MODEL_PROVEN = (
    "ACTIVE_FACT_V2_TO_CATEGORY_TAX_MODEL_PROVEN"
)
BOUNDED_TAX_MODEL_BRIDGE_BLOCKERS_PROVEN = "BOUNDED_TAX_MODEL_BRIDGE_BLOCKERS_PROVEN"

FACTORY_REQUIRED = (
    "OrdinaryTradeTaxModelBridgeRuntimeFactory.create composes "
    "OrdinaryTradeCandidateRuntimeFactory.create, "
    "Gate5SecuritiesDisposalTaxModelRuntimeFactory."
    "create_current_source_fact_operation and "
    "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create"
)
FORBIDDEN = (
    "production activation, Canonical or Source Observation reads, Gate 3, "
    "historical SQL-backed Gate 4, provider or LLM calls, declaration projection, "
    "copied FIFO, Tax Model or category aggregation logic"
)

_INPUT_OWNER = {
    "operation_kind": "REAL_SOURCE_EVIDENCE_MISSING",
    "organized_market_status": "EXTERNAL_AUTHORITATIVE_FACT_MISSING",
    "iis_status": "USER_CASE_FACT_MISSING",
    "tax_period": "USER_CASE_FACT_MISSING",
    "residency": "USER_CASE_FACT_MISSING",
    "exemption_applicability": "USER_CASE_FACT_MISSING",
    "loss_treatment": "METHODOLOGY_RULE_MISSING",
}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class OrdinaryTradeTaxModelBridgeRuntimeFactory:
    """Build one proof-only route while preserving every current domain owner."""

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

    def create(self) -> "OrdinaryTradeTaxModelBridgeRuntime":
        source_fact_consumption = OrdinaryTradeCandidateRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        operation_tax_model = Gate5SecuritiesDisposalTaxModelRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            retention_policy=self._retention_policy,
        ).create_current_source_fact_operation(
            source_fact_consumption=source_fact_consumption
        )
        return OrdinaryTradeTaxModelBridgeRuntime(
            operation_tax_model=operation_tax_model,
            category_aggregation=(
                Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
            ),
        )


class OrdinaryTradeTaxModelBridgeRuntime:
    def __init__(
        self,
        *,
        operation_tax_model: Gate5SecuritiesDisposalTaxModelRuntime,
        category_aggregation: Gate5TaxPeriodCategoryAggregationRuntime,
    ) -> None:
        self._operation_tax_model = operation_tax_model
        self._category_aggregation = category_aggregation

    def run(
        self,
        *,
        operation_methodology_ref: dict[str, Any],
        source_fact_methodology_ref: dict[str, Any],
        resolved_inputs: dict[str, Any],
        disposal_fact_id: str,
        operation_ref: str,
        source_scope_ref: str,
        category_scope: dict[str, Any],
        taxpayer_binding: dict[str, Any] | None,
        completeness_evidence: dict[str, Any] | None,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        operation_result: dict[str, Any] | None = None
        category_result: dict[str, Any] | None = None
        validated_taxpayer_binding: dict[str, Any] | None = None
        try:
            operation_result = (
                self._operation_tax_model.run_operation_from_current_source_facts(
                    methodology_ref=operation_methodology_ref,
                    source_fact_methodology_ref=source_fact_methodology_ref,
                    resolved_inputs=resolved_inputs,
                    disposal_fact_id=disposal_fact_id,
                    context=context,
                )
            )
            case_binding = operation_result["source_fact_consumption"]["case_binding"]
            if case_binding != {
                "scope_kind": "case",
                "scope_id": source_scope_ref,
            }:
                return _blocked(
                    reason_code=(
                        "gate5_tax_model_bridge_source_scope_case_binding_mismatch"
                    ),
                    field="source_scope_ref",
                    owner_classification="INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
                    owner="OrdinaryTradeTaxModelBridgeRuntime",
                    operation_result=operation_result,
                    category_result=category_result,
                    taxpayer_binding=validated_taxpayer_binding,
                    disposal_fact_id=disposal_fact_id,
                    context=context,
                )
            if taxpayer_binding is None:
                return _blocked(
                    reason_code="gate5_tax_model_bridge_taxpayer_binding_missing",
                    field="taxpayer_binding",
                    owner_classification="USER_CASE_FACT_MISSING",
                    owner="OrdinaryTradeTaxModelBridgeRuntime",
                    operation_result=operation_result,
                    category_result=category_result,
                    taxpayer_binding=validated_taxpayer_binding,
                    disposal_fact_id=disposal_fact_id,
                    context=context,
                )
            validated_taxpayer_binding = validate_ordinary_trade_taxpayer_binding(
                taxpayer_binding
            )
            if validated_taxpayer_binding is None:
                return _blocked(
                    reason_code="gate5_tax_model_bridge_taxpayer_binding_invalid",
                    field="taxpayer_binding",
                    owner_classification="INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
                    owner="OrdinaryTradeTaxModelBridgeRuntime",
                    operation_result=operation_result,
                    category_result=category_result,
                    taxpayer_binding=validated_taxpayer_binding,
                    disposal_fact_id=disposal_fact_id,
                    context=context,
                )
            subject_ref = operation_result["tax_model"]["operation_scope"][
                "subject_ref"
            ]
            if validated_taxpayer_binding["operation_subject_ref"] != subject_ref:
                return _blocked(
                    reason_code=(
                        "gate5_tax_model_bridge_operation_subject_binding_mismatch"
                    ),
                    field="taxpayer_binding.operation_subject_ref",
                    owner_classification="INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
                    owner="OrdinaryTradeTaxModelBridgeRuntime",
                    operation_result=operation_result,
                    category_result=category_result,
                    taxpayer_binding=validated_taxpayer_binding,
                    disposal_fact_id=disposal_fact_id,
                    context=context,
                )
            taxpayer_scope_ref = (
                category_scope.get("taxpayer_scope_ref")
                if isinstance(category_scope, dict)
                else None
            )
            if taxpayer_scope_ref != validated_taxpayer_binding["taxpayer_scope_ref"]:
                return _blocked(
                    reason_code=(
                        "gate5_tax_model_bridge_taxpayer_scope_binding_mismatch"
                    ),
                    field="category_scope.taxpayer_scope_ref",
                    owner_classification="USER_CASE_FACT_MISSING",
                    owner="OrdinaryTradeTaxModelBridgeRuntime",
                    operation_result=operation_result,
                    category_result=category_result,
                    taxpayer_binding=validated_taxpayer_binding,
                    disposal_fact_id=disposal_fact_id,
                    context=context,
                )
            category_result = self._category_aggregation.run_tax_model(
                scope=category_scope,
                members=[
                    {
                        "operation_ref": operation_ref,
                        "source_scope_ref": case_binding["scope_id"],
                        "tax_model": operation_result["tax_model"],
                    }
                ],
                completeness_evidence=completeness_evidence,
            )
        except Gate5DeterministicSourceFactConsumptionError as exc:
            return _blocked(
                reason_code=exc.code,
                field=exc.field,
                owner_classification=_source_fact_owner(exc.code),
                owner="Gate5DeterministicSourceFactConsumptionRuntime",
                operation_result=operation_result,
                category_result=category_result,
                taxpayer_binding=validated_taxpayer_binding,
                disposal_fact_id=disposal_fact_id,
                context=context,
            )
        except Gate5SecuritiesDisposalTaxModelError as exc:
            return _blocked(
                reason_code=exc.code,
                field=exc.field,
                owner_classification=_tax_model_owner(exc.code, exc.field),
                owner="Gate5SecuritiesDisposalTaxModelRuntime",
                operation_result=operation_result,
                category_result=category_result,
                taxpayer_binding=validated_taxpayer_binding,
                disposal_fact_id=disposal_fact_id,
                context=context,
            )
        except Gate5TaxPeriodCategoryAggregationError as exc:
            return _blocked(
                reason_code=exc.code,
                field=exc.field,
                owner_classification=_category_owner(exc.code),
                owner="Gate5TaxPeriodCategoryAggregationRuntime",
                operation_result=operation_result,
                category_result=category_result,
                taxpayer_binding=validated_taxpayer_binding,
                disposal_fact_id=disposal_fact_id,
                context=context,
            )

        if category_result["status"] != "complete":
            return _blocked(
                reason_code="gate5_tax_period_completeness_evidence_absent",
                field="tax_period_scope_completeness",
                owner_classification="USER_CASE_FACT_MISSING",
                owner="Gate5TaxPeriodCategoryAggregationRuntime",
                operation_result=operation_result,
                category_result=category_result,
                taxpayer_binding=validated_taxpayer_binding,
                disposal_fact_id=disposal_fact_id,
                context=context,
            )

        return _result(
            status="proven",
            terminal=ACTIVE_FACT_V2_TO_CATEGORY_TAX_MODEL_PROVEN,
            blockers=[],
            demands=_expense_demands(
                operation_result,
                disposal_fact_id=disposal_fact_id,
                context=context,
            ),
            operation_result=operation_result,
            category_result=category_result,
            taxpayer_binding=validated_taxpayer_binding,
        )


def _blocked(
    *,
    reason_code: str,
    field: str,
    owner_classification: str,
    owner: str,
    operation_result: dict[str, Any] | None,
    category_result: dict[str, Any] | None,
    taxpayer_binding: dict[str, Any] | None,
    disposal_fact_id: str,
    context: ArtifactAccessContext,
) -> dict[str, Any]:
    required_input = field or reason_code
    blocker = {
        "schema_version": "broker_reports_tax_model_bridge_blocker_v0",
        "reason_code": reason_code,
        "required_input": required_input,
        "gap_owner_classification": owner_classification,
        "owner": owner,
        "blocking_scope": _blocking_scope(owner),
    }
    demands = (
        []
        if operation_result is None
        else _expense_demands(
            operation_result,
            disposal_fact_id=disposal_fact_id,
            context=context,
        )
    )
    return _result(
        status="blocked",
        terminal=BOUNDED_TAX_MODEL_BRIDGE_BLOCKERS_PROVEN,
        blockers=[blocker],
        demands=demands,
        operation_result=operation_result,
        category_result=category_result,
        taxpayer_binding=taxpayer_binding,
    )


def _result(
    *,
    status: str,
    terminal: str,
    blockers: list[dict[str, Any]],
    demands: list[dict[str, Any]],
    operation_result: dict[str, Any] | None,
    category_result: dict[str, Any] | None,
    taxpayer_binding: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": ORDINARY_TRADE_TAX_MODEL_BRIDGE_RESULT_SCHEMA_VERSION,
        "status": status,
        "terminal": terminal,
        "route": [
            "OrdinaryTradeCandidateRuntimeFactory.create",
            "Gate5SecuritiesDisposalTaxModelRuntime."
            "run_operation_from_current_source_facts",
            "Gate5TaxPeriodCategoryAggregationRuntime.run_tax_model",
        ],
        "operation_result": copy.deepcopy(operation_result),
        "category_result": copy.deepcopy(category_result),
        "taxpayer_binding": copy.deepcopy(taxpayer_binding),
        "blockers": copy.deepcopy(blockers),
        "demands": copy.deepcopy(demands),
        "execution_constraints": {
            "active": False,
            "shadow_only": True,
            "provider_calls": 0,
            "gate3_execution": False,
            "historical_sql_gate4_reads": False,
            "canonical_reads_downstream": False,
            "source_observation_reads_downstream": False,
            "declaration_projection": False,
            "invented_event_relations": 0,
        },
    }


def _expense_demands(
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
    acquisition_commission_fact_ids = gate5_source_fact_acquisition_commission_fact_ids(
        source,
        disposal_fact_id=disposal_fact_id,
        context=context,
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


def validate_ordinary_trade_taxpayer_binding(
    value: Any,
) -> dict[str, Any] | None:
    """Validate the bridge-owned operation-to-taxpayer identity binding."""
    provenance = value.get("provenance") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "operation_subject_ref",
            "taxpayer_scope_ref",
            "provenance",
        }
        or value.get("schema_version") != ORDINARY_TRADE_TAXPAYER_BINDING_SCHEMA_VERSION
        or not _identifier(value.get("operation_subject_ref"))
        or not _identifier(value.get("taxpayer_scope_ref"))
        or not isinstance(provenance, dict)
        or set(provenance) != {"source_kind", "source_ref", "input_channel"}
        or provenance.get("source_kind") != "user_verified_fact"
        or not _identifier(provenance.get("source_ref"))
        or provenance.get("input_channel") != "operation_taxpayer_binding"
    ):
        return None
    return copy.deepcopy(value)


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _source_fact_owner(code: str) -> str:
    if code in {
        "gate5_source_fact_acquisition_missing",
        "gate5_source_fact_disposal_missing",
        "gate5_source_fact_direct_expense_missing",
        "gate5_source_fact_acquisition_quantity_insufficient",
    }:
        return "REAL_SOURCE_EVIDENCE_MISSING"
    if "methodology_unresolved" in code:
        return "METHODOLOGY_RULE_MISSING"
    if "legal_interpretation_required" in code:
        return "LEGAL_INTERPRETATION_REQUIRED"
    return "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"


def _tax_model_owner(code: str, field: str) -> str:
    if code == "gate5_tax_model_classification_prerequisite_missing":
        return _INPUT_OWNER.get(field, "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT")
    if code in {
        "gate5_tax_model_relatedness_missing",
        "gate5_tax_model_inputs_not_satisfied",
    }:
        return "REAL_SOURCE_EVIDENCE_MISSING"
    if code == "gate5_tax_model_residency_classification_required":
        return "USER_CASE_FACT_MISSING"
    if code in {
        "gate5_tax_model_loss_treatment_missing",
        "gate5_tax_model_loss_treatment_unsupported",
    }:
        return "METHODOLOGY_RULE_MISSING"
    if code in {
        "gate5_tax_model_methodology_invalid",
        "gate5_tax_model_methodology_evidence_invalid",
        "gate5_tax_model_behavior_unsupported",
    }:
        return "METHODOLOGY_RULE_MISSING"
    return "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"


def _category_owner(code: str) -> str:
    if code in {
        "gate5_tax_period_completeness_evidence_invalid",
        "gate5_tax_period_completeness_binding_mismatch",
    }:
        return "USER_CASE_FACT_MISSING"
    if "methodology" in code:
        return "METHODOLOGY_RULE_MISSING"
    return "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"


def _blocking_scope(owner: str) -> str:
    if owner == "Gate5DeterministicSourceFactConsumptionRuntime":
        return "current_fact_v2_consumption"
    if owner == "Gate5SecuritiesDisposalTaxModelRuntime":
        return "single_disposal_operation_tax_model"
    if owner == "OrdinaryTradeTaxModelBridgeRuntime":
        return "bridge_identity_binding"
    return "taxpayer_category_period_scope"


__all__ = [
    "ACTIVE_FACT_V2_TO_CATEGORY_TAX_MODEL_PROVEN",
    "BOUNDED_TAX_MODEL_BRIDGE_BLOCKERS_PROVEN",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ORDINARY_TRADE_TAX_MODEL_BRIDGE_RESULT_SCHEMA_VERSION",
    "ORDINARY_TRADE_TAXPAYER_BINDING_SCHEMA_VERSION",
    "OrdinaryTradeTaxModelBridgeRuntime",
    "OrdinaryTradeTaxModelBridgeRuntimeFactory",
    "validate_ordinary_trade_taxpayer_binding",
]
