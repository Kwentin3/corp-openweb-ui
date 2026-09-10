"""Exact financial-investment component for one supplied-case evidence set."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from .gate5_tax_period_category_aggregation import (
    Gate5TaxPeriodCategoryAggregationRuntime,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)


GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_financial_investment_results_input_v0"
)
GATE5_FINANCIAL_INVESTMENT_RESULTS_OPERATION_SET_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_financial_investment_results_input_v1"
)
GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION = (
    "broker_reports_gate5_financial_investment_results_component_v0"
)
GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPLETENESS_SCHEMA_VERSION = (
    "broker_reports_gate5_financial_investment_supplied_case_completeness_v0"
)
GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_OWNER = (
    "Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create.validate_component"
)
GATE5_FINANCIAL_INVESTMENT_RESULTS_DOMAIN_ID = "financial_investment_results"
GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_FAMILY = (
    "financial_investment_results"
)
GATE5_FINANCIAL_INVESTMENT_RESULTS_OBLIGATION_REFS = (
    "obl_securities_and_derivatives_results",
    "obl_digital_financial_asset_and_right_results",
    "obl_investment_partnership_results",
)

FACTORY_REQUIRED = (
    "Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create owns exact supplied-case assembly",
    "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create owns every category-model validation",
)
FORBIDDEN = (
    "real-world taxpayer absence or tax completeness assertion",
    "unvalidated category model, operation reimplementation or bounded-model promotion",
    "Gate 4, SQL, ArtifactStore, provider, LLM or direct source-document read",
    "generic registry, rules engine, PROJECT, XML/PDF or product activation",
)

_INPUT_KEYS = frozenset(
    {
        "schema_version",
        "scope_binding",
        "category_tax_models",
        "completeness_evidence",
    }
)
_OPERATION_SET_INPUT_KEYS = frozenset(
    {
        "schema_version",
        "scope_binding",
        "operation_set_result",
        "completeness_evidence",
    }
)
_OPERATION_SET_RESULT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "terminal",
        "route",
        "operation_set",
        "operation_results",
        "category_result",
        "taxpayer_binding",
        "blockers",
        "demands",
        "execution_constraints",
    }
)
_OPERATION_SET_KEYS = frozenset(
    {
        "schema_version",
        "case_binding",
        "disposal_fact_ids",
        "operation_refs",
        "source_fact_consumption_sha256",
        "disposal_fact_ids_sha256",
        "scope_binding",
        "current_fact_set_snapshot",
        "current_fact_set_sha256",
        "final_current_fact_set_sha256",
    }
)
_OPERATION_RESULT_KEYS = frozenset(
    {"operation_ref", "disposal_fact_id", "operation_result"}
)
_CURRENT_FACT_SET_KEYS = frozenset(
    {"schema_version", "status", "facts", "blockers"}
)
_CATEGORY_RESULT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "scope_binding",
        "known_values",
        "completeness",
        "category_tax_model",
    }
)
_COMPONENT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "component_id",
        "domain_id",
        "component_family",
        "root_coverage",
        "covered_obligation_refs",
        "scope_binding",
        "category_tax_models",
        "obligation_resolutions",
        "completeness_evidence",
        "input_snapshot",
    }
)
_SCOPE_KEYS = frozenset(
    {
        "schema_version",
        "scope_ref",
        "taxpayer_scope_ref",
        "tax_period",
        "authenticated_user_ref",
        "case_id",
        "normalization_run_ref",
        "scope_binding_sha256",
    }
)
_COMPLETENESS_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "coverage_kind",
        "scope_binding_sha256",
        "category_model_sha256s",
        "activated_obligation_refs",
        "not_activated_obligation_refs",
        "real_world_taxpayer_absence_asserted",
        "provenance",
    }
)
_PROVENANCE_KEYS = frozenset(
    {"source_kind", "source_ref", "input_channel", "real_user_fact"}
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECURITIES_OBLIGATION_REF = GATE5_FINANCIAL_INVESTMENT_RESULTS_OBLIGATION_REFS[0]
_OPERATION_SET_RESULT_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_tax_model_operation_set_result_v1"
)
_OPERATION_SET_TERMINAL = "ACTIVE_FACT_V2_OPERATION_SET_TO_CATEGORY_TAX_MODEL_PROVEN"
_OPERATION_SET_SCHEMA_VERSION = "broker_reports_ordinary_trade_operation_set_v1"
_CURRENT_FACT_SET_SCHEMA_VERSION = "broker_reports_gate4_ordinary_trade_current_fact_set_v1"
_OPERATION_SET_CONSTRAINTS = {
    "active": False,
    "shadow_only": True,
    "provider_calls": 0,
    "gate3_execution": False,
    "historical_sql_gate4_reads": False,
    "canonical_reads_downstream": False,
    "source_observation_reads_downstream": False,
    "declaration_projection": False,
    "invented_event_relations": 0,
}


class Gate5DeclarationFinancialInvestmentResultsError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5DeclarationFinancialInvestmentResultsRuntimeFactory:
    @staticmethod
    def create() -> "Gate5DeclarationFinancialInvestmentResultsRuntime":
        return Gate5DeclarationFinancialInvestmentResultsRuntime(
            category_runtime=Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
        )


class Gate5DeclarationFinancialInvestmentResultsRuntime:
    def __init__(
        self,
        *,
        category_runtime: Gate5TaxPeriodCategoryAggregationRuntime,
    ) -> None:
        self._category_runtime = category_runtime

    def create_component(self, *, component_input: dict[str, Any]) -> dict[str, Any]:
        validated = self._validated_input(component_input)
        category_hashes = [
            _canonical_sha256(model) for model in validated["category_models"]
        ]
        resolutions = []
        for obligation_ref in GATE5_FINANCIAL_INVESTMENT_RESULTS_OBLIGATION_REFS:
            activated = obligation_ref in validated["completeness"][
                "activated_obligation_refs"
            ]
            resolutions.append(
                {
                    "obligation_ref": obligation_ref,
                    "state": (
                        "RESOLVED"
                        if activated
                        else "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
                    ),
                    "category_model_sha256s": category_hashes if activated else [],
                    "real_world_absence_asserted": False,
                }
            )
        base = {
            "schema_version": (
                GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION
            ),
            "status": "complete_for_supplied_case",
            "domain_id": GATE5_FINANCIAL_INVESTMENT_RESULTS_DOMAIN_ID,
            "component_family": (
                GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_FAMILY
            ),
            "root_coverage": "exact_root_domain",
            "covered_obligation_refs": list(
                GATE5_FINANCIAL_INVESTMENT_RESULTS_OBLIGATION_REFS
            ),
            "scope_binding": copy.deepcopy(validated["scope"]),
            "category_tax_models": copy.deepcopy(validated["category_models"]),
            "obligation_resolutions": resolutions,
            "completeness_evidence": copy.deepcopy(validated["completeness"]),
            "input_snapshot": copy.deepcopy(component_input),
        }
        return {
            **base,
            "component_id": f"financial-investment-results:{_canonical_sha256(base)}",
        }

    def validate_component(
        self,
        *,
        component: dict[str, Any],
        scope_binding: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(component, dict) or set(component) != _COMPONENT_KEYS:
            _fail("gate5_financial_investment_component_invalid")
        expected = self.create_component(
            component_input=component.get("input_snapshot")
        )
        if component != expected:
            _fail("gate5_financial_investment_component_mismatch")
        if component["scope_binding"] != _validated_scope(scope_binding):
            _fail("gate5_financial_investment_scope_mismatch")
        return copy.deepcopy(component)

    def _validated_input(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            _fail("gate5_financial_investment_input_invalid")
        if value.get("schema_version") == GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION:
            return self._validated_input_v0(value)
        if (
            value.get("schema_version")
            == GATE5_FINANCIAL_INVESTMENT_RESULTS_OPERATION_SET_INPUT_SCHEMA_VERSION
        ):
            return self._validated_operation_set_input(value)
        _fail("gate5_financial_investment_input_invalid")

    def _validated_input_v0(self, value: dict[str, Any]) -> dict[str, Any]:
        if (
            set(value) != _INPUT_KEYS
            or value.get("schema_version")
            != GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION
        ):
            _fail("gate5_financial_investment_input_invalid")
        scope = _validated_scope(value.get("scope_binding"))
        raw_models = value.get("category_tax_models")
        if not isinstance(raw_models, list) or not raw_models:
            _fail("gate5_financial_investment_categories_invalid")
        models = []
        seen = set()
        for position, raw_model in enumerate(raw_models):
            try:
                model = self._category_runtime.validate_category_model(
                    tax_model=raw_model
                )
            except ValueError as exc:
                raise Gate5DeclarationFinancialInvestmentResultsError(
                    "gate5_financial_investment_category_invalid",
                    str(position),
                ) from exc
            calculation_scope = model["calculation_scope"]
            if (
                calculation_scope["taxpayer_scope_ref"]
                != scope["taxpayer_scope_ref"]
                or calculation_scope["tax_period"] != scope["tax_period"]
            ):
                _fail("gate5_financial_investment_category_scope_mismatch")
            model_sha256 = _canonical_sha256(model)
            if model_sha256 in seen:
                _fail("gate5_financial_investment_category_duplicate")
            seen.add(model_sha256)
            models.append(model)
        models.sort(key=_canonical_sha256)
        hashes = [_canonical_sha256(model) for model in models]
        completeness = value.get("completeness_evidence")
        not_activated = list(GATE5_FINANCIAL_INVESTMENT_RESULTS_OBLIGATION_REFS[1:])
        if (
            not isinstance(completeness, dict)
            or set(completeness) != _COMPLETENESS_KEYS
            or completeness.get("schema_version")
            != GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPLETENESS_SCHEMA_VERSION
            or completeness.get("status") != "asserted_complete_for_supplied_case"
            or completeness.get("coverage_kind")
            != "all_financial_investment_evidence_supplied_to_case"
            or completeness.get("scope_binding_sha256")
            != scope["scope_binding_sha256"]
            or completeness.get("category_model_sha256s") != hashes
            or completeness.get("activated_obligation_refs")
            != [_SECURITIES_OBLIGATION_REF]
            or completeness.get("not_activated_obligation_refs") != not_activated
            or completeness.get("real_world_taxpayer_absence_asserted") is not False
        ):
            _fail("gate5_financial_investment_completeness_invalid")
        validated_completeness = copy.deepcopy(completeness)
        validated_completeness["provenance"] = _provenance(
            completeness.get("provenance")
        )
        return {
            "scope": scope,
            "category_models": models,
            "completeness": validated_completeness,
        }

    def _validated_operation_set_input(self, value: dict[str, Any]) -> dict[str, Any]:
        if set(value) != _OPERATION_SET_INPUT_KEYS:
            _fail("gate5_financial_investment_operation_set_input_invalid")
        scope = _validated_scope(value.get("scope_binding"))
        category = self._validated_operation_set_result(
            value.get("operation_set_result"),
            scope=scope,
        )
        return self._validated_input_v0(
            {
                "schema_version": GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION,
                "scope_binding": scope,
                "category_tax_models": [category],
                "completeness_evidence": value.get("completeness_evidence"),
            }
        )

    def _validated_operation_set_result(
        self,
        value: Any,
        *,
        scope: dict[str, Any],
    ) -> dict[str, Any]:
        if (
            not isinstance(value, dict)
            or set(value) != _OPERATION_SET_RESULT_KEYS
            or value.get("schema_version") != _OPERATION_SET_RESULT_SCHEMA_VERSION
            or value.get("status") != "proven"
            or value.get("terminal") != _OPERATION_SET_TERMINAL
            or value.get("blockers") != []
            or value.get("demands") != []
            or value.get("execution_constraints") != _OPERATION_SET_CONSTRAINTS
        ):
            _fail("gate5_financial_investment_operation_set_invalid")
        operation_set = value.get("operation_set")
        if (
            not isinstance(operation_set, dict)
            or set(operation_set) != _OPERATION_SET_KEYS
            or operation_set.get("schema_version") != _OPERATION_SET_SCHEMA_VERSION
        ):
            _fail("gate5_financial_investment_operation_set_invalid")
        case_binding = operation_set.get("case_binding")
        if (
            not isinstance(case_binding, dict)
            or case_binding != {"scope_kind": "case", "scope_id": scope["case_id"]}
        ):
            _fail("gate5_financial_investment_operation_set_scope_mismatch")
        current_fact_set = operation_set.get("current_fact_set_snapshot")
        if (
            not isinstance(current_fact_set, dict)
            or set(current_fact_set) != _CURRENT_FACT_SET_KEYS
            or current_fact_set.get("schema_version") != _CURRENT_FACT_SET_SCHEMA_VERSION
            or current_fact_set.get("status") != "READY"
            or current_fact_set.get("blockers") != []
            or not isinstance(current_fact_set.get("facts"), list)
            or not current_fact_set["facts"]
            or _canonical_sha256(current_fact_set)
            != operation_set.get("current_fact_set_sha256")
            or operation_set.get("current_fact_set_sha256")
            != operation_set.get("final_current_fact_set_sha256")
        ):
            _fail("gate5_financial_investment_operation_set_current_fact_invalid")
        if any(
            not isinstance(fact, dict) or fact.get("case_binding") != case_binding
            for fact in current_fact_set["facts"]
        ):
            _fail("gate5_financial_investment_operation_set_scope_mismatch")
        snapshot_disposal_ids = sorted(
            fact.get("fact_id")
            for fact in current_fact_set["facts"]
            if isinstance(fact.get("fact_id"), str)
            and fact.get("financial_type") == "SECURITY_DISPOSAL"
        )
        taxpayer_binding = self._category_runtime.validate_operation_taxpayer_scope_binding(
            binding=value.get("taxpayer_binding")
        )
        if (
            taxpayer_binding is None
            or taxpayer_binding["taxpayer_scope_ref"] != scope["taxpayer_scope_ref"]
        ):
            _fail("gate5_financial_investment_operation_set_scope_mismatch")
        disposal_ids = operation_set.get("disposal_fact_ids")
        operation_refs = operation_set.get("operation_refs")
        if (
            not isinstance(disposal_ids, list)
            or not disposal_ids
            or disposal_ids != sorted(set(disposal_ids))
            or disposal_ids != snapshot_disposal_ids
            or not all(_identifier(item) for item in disposal_ids)
            or operation_refs != ["operation-" + item for item in disposal_ids]
            or operation_set.get("disposal_fact_ids_sha256")
            != _canonical_sha256(disposal_ids)
            or not isinstance(
                operation_set.get("source_fact_consumption_sha256"), str
            )
            or _SHA256.fullmatch(operation_set["source_fact_consumption_sha256"])
            is None
        ):
            _fail("gate5_financial_investment_operation_set_invalid")
        source_consumption_sha256 = operation_set["source_fact_consumption_sha256"]
        operation_results = value.get("operation_results")
        if (
            not isinstance(operation_results, list)
            or len(operation_results) != len(disposal_ids)
        ):
            _fail("gate5_financial_investment_operation_set_members_invalid")
        expected_members = []
        for disposal_fact_id, operation_ref, result in zip(
            disposal_ids, operation_refs, operation_results, strict=True
        ):
            if (
                not isinstance(result, dict)
                or set(result) != _OPERATION_RESULT_KEYS
                or result.get("disposal_fact_id") != disposal_fact_id
                or result.get("operation_ref") != operation_ref
                or not isinstance(result.get("operation_result"), dict)
            ):
                _fail("gate5_financial_investment_operation_set_members_invalid")
            operation_result = result["operation_result"]
            consumption = operation_result.get("source_fact_consumption")
            tax_model = operation_result.get("tax_model")
            if (
                not isinstance(consumption, dict)
                or _canonical_sha256(consumption) != source_consumption_sha256
                or consumption.get("case_binding") != case_binding
                or not isinstance(tax_model, dict)
            ):
                _fail("gate5_financial_investment_operation_set_members_invalid")
            try:
                model = self._category_runtime.validate_operation_member(
                    tax_model=tax_model
                )
            except ValueError as exc:
                raise Gate5DeclarationFinancialInvestmentResultsError(
                    "gate5_financial_investment_operation_set_members_invalid"
                ) from exc
            if (
                model["operation_scope"]["subject_ref"]
                != taxpayer_binding["operation_subject_ref"]
                or model["operation_scope"]["tax_period"].get("value")
                != scope["tax_period"]
            ):
                _fail("gate5_financial_investment_operation_set_scope_mismatch")
            expected_members.append(
                {
                    "operation_ref": operation_ref,
                    "source_scope_ref": scope["case_id"],
                    "operation_model_sha256": _canonical_sha256(model),
                }
            )
        category_result = value.get("category_result")
        scope_binding = operation_set.get("scope_binding")
        if (
            not isinstance(category_result, dict)
            or set(category_result) != _CATEGORY_RESULT_KEYS
            or category_result.get("status") != "complete"
            or category_result.get("scope_binding") != scope_binding
            or not isinstance(scope_binding, dict)
            or scope_binding.get("members") != expected_members
            or not isinstance(category_result.get("category_tax_model"), dict)
        ):
            _fail("gate5_financial_investment_operation_set_members_invalid")
        try:
            category = self._category_runtime.validate_category_model(
                tax_model=category_result["category_tax_model"]
            )
        except ValueError as exc:
            raise Gate5DeclarationFinancialInvestmentResultsError(
                "gate5_financial_investment_operation_set_category_invalid"
            ) from exc
        calculation_scope = category["calculation_scope"]
        if (
            calculation_scope.get("taxpayer_scope_ref")
            != scope["taxpayer_scope_ref"]
            or calculation_scope.get("tax_period") != scope["tax_period"]
            or category.get("member_operations") != expected_members
        ):
            _fail("gate5_financial_investment_operation_set_scope_mismatch")
        return category


def _provenance(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _PROVENANCE_KEYS
        or value.get("source_kind")
        not in {
            "synthetic_proof_evidence",
            "user_verified_fact",
            "current_fact_v2",
            "current_canonical_coverage",
        }
        or not _identifier(value.get("source_ref"))
        or value.get("input_channel")
        != "financial_investment_supplied_case_completeness"
        or not isinstance(value.get("real_user_fact"), bool)
        or (
            value["source_kind"] == "synthetic_proof_evidence"
            and value["real_user_fact"] is not False
        )
    ):
        _fail("gate5_financial_investment_provenance_invalid")
    return copy.deepcopy(value)


def _validated_scope(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _SCOPE_KEYS
        or not all(
            _identifier(value.get(key))
            for key in (
                "scope_ref",
                "taxpayer_scope_ref",
                "tax_period",
                "authenticated_user_ref",
                "case_id",
                "normalization_run_ref",
            )
        )
        or not isinstance(value.get("schema_version"), str)
        or _SHA256.fullmatch(value.get("scope_binding_sha256", "")) is None
    ):
        _fail("gate5_financial_investment_scope_invalid")
    base = {
        key: copy.deepcopy(value[key]) for key in value if key != "scope_binding_sha256"
    }
    if value["scope_binding_sha256"] != _canonical_sha256(base):
        _fail("gate5_financial_investment_scope_invalid")
    return copy.deepcopy(value)


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str, field: str = "") -> None:
    raise Gate5DeclarationFinancialInvestmentResultsError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPLETENESS_SCHEMA_VERSION",
    "GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_FAMILY",
    "GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_OWNER",
    "GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION",
    "GATE5_FINANCIAL_INVESTMENT_RESULTS_DOMAIN_ID",
    "GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION",
    "GATE5_FINANCIAL_INVESTMENT_RESULTS_OPERATION_SET_INPUT_SCHEMA_VERSION",
    "GATE5_FINANCIAL_INVESTMENT_RESULTS_OBLIGATION_REFS",
    "Gate5DeclarationFinancialInvestmentResultsError",
    "Gate5DeclarationFinancialInvestmentResultsRuntime",
    "Gate5DeclarationFinancialInvestmentResultsRuntimeFactory",
]
