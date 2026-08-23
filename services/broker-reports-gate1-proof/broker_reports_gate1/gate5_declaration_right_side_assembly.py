"""Single right-side owner for Declaration component assembly."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .gate5_declaration_budget_outcome import (
    GATE5_DECLARATION_BUDGET_DISPOSITION_INPUT_SCHEMA_VERSION,
    Gate5DeclarationBudgetOutcomeRuntimeFactory,
)
from .gate5_declaration_filing_context import (
    GATE5_FILING_AND_PARTY_IDENTITY_INPUT_SCHEMA_VERSION,
    Gate5FilingAndPartyIdentityRuntimeFactory,
)
from .gate5_declaration_financial_investment_results import (
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPLETENESS_SCHEMA_VERSION,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION,
    Gate5DeclarationFinancialInvestmentResultsRuntimeFactory,
)
from .gate5_declaration_income_sources import (
    GATE5_TAXABLE_INCOME_SOURCE_INPUT_SCHEMA_VERSION,
    Gate5DeclarationIncomeSourcesRuntimeFactory,
)
from .gate5_declaration_tax_settlement import (
    GATE5_INCOME_GROUP_TAX_RESULTS_INPUT_SCHEMA_VERSION,
    Gate5DeclarationTaxSettlementRuntimeFactory,
)
from .gate5_income_group_tax_base import (
    GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
    Gate5IncomeGroupTaxBaseRuntimeFactory,
)
from .gate5_residency_evidence import (
    Gate5ResidencyEvidenceError,
    Gate5ResidencyEvidenceRuntimeFactory,
    gate5_residency_methodology_input,
)
from .gate5_trusted_methodology import (
    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)


FACTORY_REQUIRED = (
    "Gate5DeclarationRightSideAssemblyRuntimeFactory.create is the single owner "
    "for G5.35 and active-Category right-side component assembly",
)
FORBIDDEN = (
    "left-side Fact, Gate 3, Gate 4, SQL, Category construction or projection",
    "caller-supplied taxpayer status outside the residency evidence owner",
)


class Gate5DeclarationRightSideAssemblyError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5DeclarationRightSideAssemblyRuntimeFactory:
    @staticmethod
    def create() -> "Gate5DeclarationRightSideAssemblyRuntime":
        return Gate5DeclarationRightSideAssemblyRuntime()


class Gate5DeclarationRightSideAssemblyRuntime:
    def residency_classification(self, inputs: dict[str, Any]) -> dict[str, Any]:
        facts = _required(inputs, "residency_evidence")
        runtime = Gate5ResidencyEvidenceRuntimeFactory.create()
        try:
            evidence = runtime.normalize_human_answer(
                human_answer=_required(facts, "human_answer"),
                proposal=copy.deepcopy(_required(facts, "proposal")),
                source_ref=_required(facts, "source_ref"),
            )
            classification = runtime.classify(evidence=evidence)
        except Gate5ResidencyEvidenceError as exc:
            raise Gate5DeclarationRightSideAssemblyError(
                exc.code,
                exc.field or "residency_evidence",
            ) from exc
        if classification["status"] not in {"RESIDENT", "NON_RESIDENT"}:
            _fail(
                "gate5_declaration_right_side_residency_evidence_missing",
                "residency_evidence",
            )
        return classification

    def income_group_tax_base(
        self,
        *,
        category: dict[str, Any],
        residency: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        facts = _required(inputs, "income_group")
        if "taxpayer_status" in facts:
            _fail("gate5_e2e_direct_taxpayer_status_forbidden", "taxpayer_status")
        group_values = copy.deepcopy(_required(facts, "group_values"))
        taxpayer_status = gate5_residency_methodology_input(
            residency,
            input_channel="taxpayer_status",
        )
        runtime = Gate5IncomeGroupTaxBaseRuntimeFactory.create()
        binding = runtime.describe_input(
            category_tax_model=category,
            taxpayer_status=taxpayer_status,
            group_values=group_values,
        )
        evidence = {
            "schema_version": GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION,
            "status": "asserted_complete",
            "coverage_kind": "all_income_and_reductions_in_stable_income_group",
            "input_binding_sha256": binding["input_binding_sha256"],
            "provenance": copy.deepcopy(_required(facts, "completeness_provenance")),
        }
        supplied_hash = facts.get("completeness_input_binding_sha256")
        if supplied_hash is not None:
            evidence["input_binding_sha256"] = supplied_hash
        return runtime.run(
            methodology_ref={
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
                "methodology_version": (
                    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION
                ),
            },
            behavior_input={
                "schema_version": GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
                "category_tax_model": copy.deepcopy(category),
                "taxpayer_status": taxpayer_status,
                "group_values": group_values,
                "completeness_evidence": evidence,
            },
        )

    def settlement_component(
        self,
        *,
        inputs: dict[str, Any],
        scope_binding: dict[str, Any],
        tax_base: dict[str, Any],
    ) -> dict[str, Any]:
        facts = _required(inputs, "settlement")
        credits = _required(facts, "credits")
        model_hash = _sha(tax_base)
        values = {"income_group_model_sha256": model_hash}
        for name in (
            "withheld_at_source",
            "material_benefit_withheld",
            "trade_fee_credit",
            "fixed_advance_credit",
            "foreign_tax_credit",
            "patent_credit",
        ):
            values[name] = {
                "value": _money(_required(credits, name)),
                "provenance": _synthetic(
                    f"{_required(facts, 'evidence_ref_prefix')}-{name}",
                    "income_group_tax_settlement",
                ),
            }
        return Gate5DeclarationTaxSettlementRuntimeFactory.create().create_component(
            component_input={
                "schema_version": GATE5_INCOME_GROUP_TAX_RESULTS_INPUT_SCHEMA_VERSION,
                "methodology_ref": {
                    "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                    "methodology_id": GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
                    "methodology_version": (
                        GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION
                    ),
                },
                "scope_binding": copy.deepcopy(scope_binding),
                "income_group_tax_base_models": [copy.deepcopy(tax_base)],
                "settlement_facts": [values],
                "completeness_evidence": {
                    "schema_version": (
                        "broker_reports_gate5_income_group_results_completeness_v0"
                    ),
                    "status": "asserted_complete",
                    "coverage_kind": (
                        "all_applicable_income_groups_for_declaration_scope"
                    ),
                    "scope_binding_sha256": scope_binding["scope_binding_sha256"],
                    "income_group_model_sha256s": [model_hash],
                    "provenance": _synthetic(
                        _required(facts, "completeness_source_ref"),
                        "income_group_results_completeness",
                    ),
                },
            }
        )

    def income_source_component(
        self,
        *,
        inputs: dict[str, Any],
        scope_binding: dict[str, Any],
        settlement: dict[str, Any],
    ) -> dict[str, Any]:
        facts = _required(inputs, "taxable_income_source")
        try:
            result = settlement["group_results"][0]
            model = result["tax_base_model"]
        except (KeyError, IndexError) as exc:
            raise Gate5DeclarationRightSideAssemblyError(
                "gate5_declaration_right_side_fact_missing",
                "settlement.group_results",
            ) from exc
        source_ref = _required(facts, "source_ref")
        return Gate5DeclarationIncomeSourcesRuntimeFactory.create().create_component(
            component_input={
                "schema_version": GATE5_TAXABLE_INCOME_SOURCE_INPUT_SCHEMA_VERSION,
                "scope_binding": copy.deepcopy(scope_binding),
                "income_group_results_component": copy.deepcopy(settlement),
                "source_entries": [
                    {
                        "source_ref": source_ref,
                        "income_group_semantic": result["income_group_semantic"],
                        "jurisdiction_kind": _required(facts, "jurisdiction_kind"),
                        "jurisdiction_code": _required(facts, "jurisdiction_code"),
                        "income_kind": _required(facts, "income_kind"),
                        "source_party": copy.deepcopy(_required(facts, "source_party")),
                        "gross_income": copy.deepcopy(model["total_income"]["value"]),
                        "taxable_income": copy.deepcopy(
                            model["taxable_income"]["value"]
                        ),
                        "tax_agent": {
                            "status": "absent",
                            "withheld_tax": copy.deepcopy(
                                result["settlement_facts"]["withheld_at_source"][
                                    "value"
                                ]
                            ),
                        },
                        "foreign_tax": None,
                        "provenance": _synthetic(
                            source_ref,
                            "taxable_income_source",
                        ),
                    }
                ],
                "completeness_evidence": {
                    "schema_version": (
                        "broker_reports_gate5_taxable_income_source_completeness_v0"
                    ),
                    "status": "asserted_complete",
                    "coverage_kind": (
                        "all_taxable_income_sources_for_declaration_scope"
                    ),
                    "scope_binding_sha256": scope_binding["scope_binding_sha256"],
                    "income_group_results_component_id": settlement["component_id"],
                    "source_refs": [source_ref],
                    "provenance": _synthetic(
                        _required(facts, "completeness_source_ref"),
                        "taxable_income_source_completeness",
                    ),
                },
            }
        )

    def filing_component(
        self,
        *,
        inputs: dict[str, Any],
        scope_binding: dict[str, Any],
        residency: dict[str, Any],
    ) -> dict[str, Any]:
        facts = _required(inputs, "filing_and_party_identity")
        filing = copy.deepcopy(_required(facts, "filing_instance"))
        taxpayer = copy.deepcopy(_required(facts, "taxpayer"))
        signer = copy.deepcopy(_required(facts, "signer"))
        if "period_status" in taxpayer:
            _fail(
                "gate5_e2e_direct_taxpayer_status_forbidden",
                "taxpayer.period_status",
            )
        taxpayer["period_status"] = gate5_residency_methodology_input(
            residency,
            input_channel="taxpayer_status",
        )["value"]
        return Gate5FilingAndPartyIdentityRuntimeFactory.create().create_component(
            component_input={
                "schema_version": GATE5_FILING_AND_PARTY_IDENTITY_INPUT_SCHEMA_VERSION,
                "scope_binding": copy.deepcopy(scope_binding),
                "filing_instance": filing,
                "taxpayer": taxpayer,
                "signer": signer,
                "evidence": {
                    "schema_version": "broker_reports_gate5_synthetic_case_evidence_v0",
                    "status": "synthetic_proof_evidence",
                    "source_ref": _required(facts, "evidence_source_ref"),
                    "case_id": scope_binding["case_id"],
                    "tax_period": scope_binding["tax_period"],
                    "input_channel": "filing_and_party_identity",
                    "real_user_fact": False,
                },
            }
        )

    def budget_component(
        self,
        *,
        inputs: dict[str, Any],
        scope_binding: dict[str, Any],
        filing: dict[str, Any],
        settlement: dict[str, Any],
    ) -> dict[str, Any]:
        facts = _required(inputs, "budget_disposition")
        allocation = {
            key: _required(facts, key)
            for key in (
                "source_ref",
                "budget_allocation_ref",
                "kbk",
                "oktmo",
                "simplified_procedure_returned_or_credited_amount",
            )
        }
        return Gate5DeclarationBudgetOutcomeRuntimeFactory.create().create_component(
            component_input={
                "schema_version": GATE5_DECLARATION_BUDGET_DISPOSITION_INPUT_SCHEMA_VERSION,
                "scope_binding": copy.deepcopy(scope_binding),
                "filing_component": copy.deepcopy(filing),
                "income_group_results_component": copy.deepcopy(settlement),
                "allocation_evidence": {
                    "schema_version": "broker_reports_gate5_synthetic_case_evidence_v0",
                    "status": "synthetic_proof_evidence",
                    **copy.deepcopy(allocation),
                    "case_id": scope_binding["case_id"],
                    "tax_period": scope_binding["tax_period"],
                    "input_channel": "declaration_budget_disposition",
                    "real_user_fact": False,
                },
            }
        )

    def financial_component(
        self,
        *,
        inputs: dict[str, Any],
        scope_binding: dict[str, Any],
        category: dict[str, Any],
    ) -> dict[str, Any]:
        facts = _required(inputs, "financial_investment")
        return Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
            component_input={
                "schema_version": (
                    GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION
                ),
                "scope_binding": copy.deepcopy(scope_binding),
                "category_tax_models": [copy.deepcopy(category)],
                "completeness_evidence": {
                    "schema_version": (
                        GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPLETENESS_SCHEMA_VERSION
                    ),
                    "status": "asserted_complete_for_supplied_case",
                    "coverage_kind": (
                        "all_financial_investment_evidence_supplied_to_case"
                    ),
                    "scope_binding_sha256": scope_binding["scope_binding_sha256"],
                    "category_model_sha256s": [_sha(category)],
                    "activated_obligation_refs": copy.deepcopy(
                        _required(facts, "activated_obligation_refs")
                    ),
                    "not_activated_obligation_refs": copy.deepcopy(
                        _required(facts, "not_activated_obligation_refs")
                    ),
                    "real_world_taxpayer_absence_asserted": False,
                    "provenance": _synthetic(
                        _required(facts, "completeness_source_ref"),
                        "financial_investment_supplied_case_completeness",
                    ),
                },
            }
        )


def _required(value: Any, key: str) -> Any:
    if not isinstance(value, dict) or key not in value or value[key] is None:
        _fail("gate5_declaration_right_side_fact_missing", key)
    return value[key]


def _synthetic(source_ref: str, input_channel: str) -> dict[str, Any]:
    return {
        "source_kind": "synthetic_proof_evidence",
        "source_ref": source_ref,
        "input_channel": input_channel,
        "real_user_fact": False,
    }


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


def _sha(value: Any) -> str:
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
    raise Gate5DeclarationRightSideAssemblyError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "Gate5DeclarationRightSideAssemblyError",
    "Gate5DeclarationRightSideAssemblyRuntime",
    "Gate5DeclarationRightSideAssemblyRuntimeFactory",
]
