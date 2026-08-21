"""Bounded evidence-authority contract for active 2025 declaration inputs."""

from __future__ import annotations

import copy
from typing import Any


GATE5_EVIDENCE_DEMAND_CONTRACT_SCHEMA_VERSION = (
    "broker_reports_gate5_evidence_demand_contract_v2"
)
GATE5_EVIDENCE_DEMAND_CONTRACT_ID = "ru-3ndfl-2025-methodology-driven-evidence-demand"
GATE5_EVIDENCE_DEMAND_CONTRACT_VERSION = "2026.1-source-owner-boundary"

FACTORY_REQUIRED = (
    "Gate5EvidenceDemandContractAuthorityFactory.create is the sole bounded "
    "evidence-authority contract owner",
)
FORBIDDEN = (
    "universal fact ontology, broker-specific tax defaults, free-form LLM "
    "authority routing, inferred payer/issuer/location roles, source-to-tax "
    "classification or speculative future fact types",
)


class Gate5EvidenceDemandContractAuthorityFactory:
    @classmethod
    def create(cls) -> "Gate5EvidenceDemandContractAuthority":
        return Gate5EvidenceDemandContractAuthority()


class Gate5EvidenceDemandContractAuthority:
    def resolve(self) -> dict[str, Any]:
        contract = {
            "schema_version": GATE5_EVIDENCE_DEMAND_CONTRACT_SCHEMA_VERSION,
            "contract_id": GATE5_EVIDENCE_DEMAND_CONTRACT_ID,
            "contract_version": GATE5_EVIDENCE_DEMAND_CONTRACT_VERSION,
            "status": "PUBLISHED_BOUNDED_CONSUMER_CONTRACT",
            "scope": "active ru-3ndfl-2025 declaration-input methodology only",
            "fact_contracts": _fact_contracts(),
            "generic_ontology": False,
            "extract_without_named_consumer": False,
        }
        _validate_complete_contract(contract)
        return copy.deepcopy(contract)


def _fact_contracts() -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []

    # Existing normalized source facts are checked before an upstream request.
    normalized = {
        "coupon_security_identity": [("COUPON_INCOME", ["asset"])],
        "coupon_income_date": [("COUPON_INCOME", ["date"])],
        "coupon_amount": [("COUPON_INCOME", ["amount"])],
        "coupon_currency": [("COUPON_INCOME", ["currency"])],
        "dividend_income_date": [("DIVIDEND_INCOME", ["date"])],
        "dividend_amount": [("DIVIDEND_INCOME", ["amount"])],
        "dividend_currency": [("DIVIDEND_INCOME", ["currency"])],
        "security_identity": [
            ("SECURITY_PURCHASE", ["asset"]),
            ("SECURITY_DISPOSAL", ["asset"]),
        ],
        "disposal_date": [("SECURITY_DISPOSAL", ["date"])],
        "source_amount": [
            ("SECURITY_DISPOSAL", ["amount"]),
            ("COUPON_INCOME", ["amount"]),
            ("DIVIDEND_INCOME", ["amount"]),
        ],
        "source_currency": [
            ("SECURITY_DISPOSAL", ["currency"]),
            ("COUPON_INCOME", ["currency"]),
            ("DIVIDEND_INCOME", ["currency"]),
        ],
        "income_or_expense_date": [
            ("SECURITY_DISPOSAL", ["date"]),
            ("COUPON_INCOME", ["date"]),
            ("DIVIDEND_INCOME", ["date"]),
            ("COMMISSION", ["date"]),
        ],
        "commission_source_assertion": [
            ("COMMISSION", []),
            ("COMMISSION_TOTAL", []),
        ],
    }
    for input_id, selectors in normalized.items():
        contracts.append(
            _contract(
                input_id,
                authority="SOURCE_DOCUMENT",
                scope="financial observation",
                granularity="per explicit source observation",
                cardinality=(
                    "at_least_one"
                    if input_id == "commission_source_assertion"
                    else "per applicable observation"
                ),
                selectors=selectors,
            )
        )

    # Filing and residency are factual case inputs, not broker-source guesses.
    user = {
        "declaration_instance_and_correction": (
            "filing_instance_identity",
            "declaration filing instance and correction number",
            "BLOCKS",
        ),
        "tax_period": ("tax_period", "declaration tax period", "BLOCKS"),
        "destination_tax_authority": (
            "filing_instance_identity",
            "destination tax authority selected for this filing",
            "BLOCKS",
        ),
        "authenticated_taxpayer_identity": (
            "taxpayer_identity_confirmed",
            "authenticated taxpayer identity for the declaration",
            "BLOCKS",
        ),
        "authenticated_signer_identity": (
            "signer_and_representation",
            "authenticated declaration signer identity",
            "BLOCKS",
        ),
        "signer_capacity": (
            "signer_and_representation",
            "signer capacity as self or representative",
            "BLOCKS",
        ),
        "representation_authority_when_representative": (
            "signer_and_representation",
            "representation authority when a representative signs",
            "CONDITIONAL",
        ),
        "authenticated_payment_reduction_or_refund_intent": (
            "budget_disposition",
            "authenticated settlement disposition intent",
            "CONDITIONAL",
        ),
        "budget_destination_facts": (
            "budget_disposition",
            "case-specific budget destination facts",
            "CONDITIONAL",
        ),
        "authenticated_presence_days_in_rf_for_12_consecutive_month_window": (
            "residency_evidence",
            "factual presence intervals used by the residency methodology",
            "BLOCKS",
        ),
        "article_207_exception_evidence": (
            "residency_evidence",
            "factual Article 207 exception evidence when applicable",
            "CONDITIONAL",
        ),
    }
    for input_id, (fact_key, meaning, effect) in user.items():
        contracts.append(
            _contract(
                input_id,
                meaning=meaning,
                authority="USER_CASE",
                scope="authenticated declaration case",
                granularity="one typed case assertion",
                cardinality="exactly_one_when_applicable",
                absence_effect=effect,
                fact_key=fact_key,
            )
        )

    # External references must retain their official-source identity and date.
    external = {
        "admitted_exchange_fact": "official market-admission fact for security and date",
        "market_quotation_fact": "official market-quotation fact for security and date",
        "cbr_official_rate_for_currency_and_date": "official CBR rate for exact currency and date",
        "cbr_rate_nominal": "official CBR rate nominal paired with the exact rate",
        "applicable_tax_treaty": "reviewed treaty authority for exact jurisdiction and period",
    }
    for input_id, meaning in external.items():
        contracts.append(
            _contract(
                input_id,
                meaning=meaning,
                authority="EXTERNAL_REFERENCE",
                scope="authority, jurisdiction and effective date",
                granularity="one exact authoritative reference fact",
                cardinality="exactly_one_per_lookup_key",
                absence_effect=(
                    "CONDITIONAL" if input_id == "applicable_tax_treaty" else "BLOCKS"
                ),
                fact_key=input_id,
            )
        )

    # These are outputs of existing methodology owners, never source literals.
    methodology_results = {
        "complete_income_group_settlement": "complete_income_group_settlement",
        "resident_status": "taxpayer_period_status",
        "income_source_jurisdiction": "income_source_jurisdiction",
        "organized_market_status": "organized_market_status",
        "documented_expense_status": "documented_expense_status",
        "actually_incurred_status": "actually_incurred_status",
        "direct_or_shared_expense_status": "direct_or_shared_expense_status",
    }
    for input_id, result_key in methodology_results.items():
        contracts.append(
            _contract(
                input_id,
                meaning=f"published methodology result: {input_id}",
                authority="MIXED",
                scope="published methodology result scope",
                granularity="one deterministic methodology result",
                cardinality="exactly_one_when_applicable",
                absence_effect=(
                    "CONDITIONAL"
                    if input_id == "complete_income_group_settlement"
                    else "BLOCKS"
                ),
                result_key=result_key,
            )
        )

    # These requests describe meaning only.  Gate 5 never reads Canonical or
    # chooses an extraction strategy; an upstream owner must accept or reject
    # the request against its published contracts.
    source_recovery = {
        "payer_organization_identity": (
            "explicit payer organization identity",
            "PAYER_ORGANIZATION_IDENTITY",
            ["Payer", "Paying organization", "Плательщик", "Организация-плательщик"],
            None,
            "BLOCKS",
        ),
        "payer_organization_jurisdiction": (
            "explicit jurisdiction of the payer organization",
            "PAYER_ORGANIZATION_JURISDICTION",
            [
                "Payer country",
                "Payer jurisdiction",
                "Country of payer",
                "Страна плательщика",
                "Юрисдикция плательщика",
            ],
            "EXTERNAL_REFERENCE",
            "BLOCKS",
        ),
        "realization_location_jurisdiction": (
            "explicit jurisdiction of realization, not a generic location",
            "REALIZATION_LOCATION_JURISDICTION",
            [
                "Realization jurisdiction",
                "Place of realization",
                "Place of sale",
                "Место реализации",
                "Юрисдикция реализации",
            ],
            None,
            "BLOCKS",
        ),
    }
    for input_id, (
        meaning,
        fact_type,
        labels,
        fallback,
        effect,
    ) in source_recovery.items():
        contracts.append(
            _contract(
                input_id,
                meaning=meaning,
                authority="MIXED" if fallback else "SOURCE_DOCUMENT",
                scope="supplied declaration case documents",
                granularity="per explicitly role-labelled source assertion",
                cardinality="at_least_one_when_applicable",
                absence_effect=effect,
                source_request={
                    "fact_type": fact_type,
                    "explicit_role_labels": labels,
                    "allowed_source_structures": [
                        "SAME_ATOM",
                        "SAME_TABLE_ROW",
                        "ADJACENT_TEXT_LINE",
                    ],
                    "source_ceiling": "EXPLICIT_ROLE_LITERAL_ONLY",
                },
                fallback=fallback,
            )
        )

    # The foreign-tax rule is conditional and inactive for the frozen case.
    # Keep its evidence authority explicit, but do not publish speculative fact
    # types until that consumer becomes active and its exact source ceiling is
    # reviewed.
    pending_source_contracts = {
        "foreign_income_kind_amount_and_year": "foreign income kind, amount and year evidence",
        "foreign_tax_amount_and_payment_date": "foreign tax amount and payment date evidence",
        "foreign_tax_authority_or_withholding_source_document": "foreign tax authority evidence or the broker statement that reports the withholding",
        "required_translation": "translation evidence for a foreign tax document",
    }
    for input_id, meaning in pending_source_contracts.items():
        contracts.append(
            _contract(
                input_id,
                meaning=meaning,
                authority="SOURCE_DOCUMENT",
                scope="conditional foreign-source declaration evidence",
                granularity="per explicit foreign-tax source assertion",
                cardinality="at_least_one_when_applicable",
                absence_effect="CONDITIONAL",
            )
        )

    return sorted(contracts, key=lambda item: item["required_input"])


def _contract(
    input_id: str,
    *,
    meaning: str | None = None,
    authority: str,
    scope: str,
    granularity: str,
    cardinality: str,
    absence_effect: str = "BLOCKS",
    selectors: list[tuple[str, list[str]]] | None = None,
    source_request: dict[str, Any] | None = None,
    fallback: str | None = None,
    fact_key: str | None = None,
    result_key: str | None = None,
) -> dict[str, Any]:
    return {
        "required_input": input_id,
        "fact_meaning": meaning or f"explicit evidence for {input_id}",
        "fact_role": input_id,
        "preferred_authority": authority,
        "required_scope": scope,
        "granularity": granularity,
        "cardinality": cardinality,
        "absence_effect": absence_effect,
        "normalized_fact_contracts": [
            {"fact_type": fact_type, "required_roles": list(required_roles)}
            for fact_type, required_roles in (selectors or [])
        ],
        "source_fact_request": copy.deepcopy(source_request),
        "fallback_authority": fallback,
        "fact_key": fact_key,
        "methodology_result_key": result_key,
    }


def _validate_complete_contract(contract: dict[str, Any]) -> None:
    expected_inputs = {
        "actually_incurred_status",
        "admitted_exchange_fact",
        "applicable_tax_treaty",
        "article_207_exception_evidence",
        "authenticated_payment_reduction_or_refund_intent",
        "authenticated_presence_days_in_rf_for_12_consecutive_month_window",
        "authenticated_signer_identity",
        "authenticated_taxpayer_identity",
        "budget_destination_facts",
        "cbr_official_rate_for_currency_and_date",
        "cbr_rate_nominal",
        "commission_source_assertion",
        "complete_income_group_settlement",
        "coupon_amount",
        "coupon_currency",
        "coupon_income_date",
        "coupon_security_identity",
        "declaration_instance_and_correction",
        "destination_tax_authority",
        "direct_or_shared_expense_status",
        "disposal_date",
        "dividend_amount",
        "dividend_currency",
        "dividend_income_date",
        "documented_expense_status",
        "foreign_income_kind_amount_and_year",
        "foreign_tax_amount_and_payment_date",
        "foreign_tax_authority_or_withholding_source_document",
        "income_or_expense_date",
        "income_source_jurisdiction",
        "market_quotation_fact",
        "organized_market_status",
        "payer_organization_identity",
        "payer_organization_jurisdiction",
        "realization_location_jurisdiction",
        "representation_authority_when_representative",
        "required_translation",
        "resident_status",
        "security_identity",
        "signer_capacity",
        "source_amount",
        "source_currency",
        "tax_period",
    }
    observed = [item["required_input"] for item in contract["fact_contracts"]]
    if len(observed) != len(set(observed)) or set(observed) != expected_inputs:
        raise ValueError("gate5_evidence_demand_contract_input_coverage_invalid")


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_EVIDENCE_DEMAND_CONTRACT_ID",
    "GATE5_EVIDENCE_DEMAND_CONTRACT_SCHEMA_VERSION",
    "GATE5_EVIDENCE_DEMAND_CONTRACT_VERSION",
    "Gate5EvidenceDemandContractAuthority",
    "Gate5EvidenceDemandContractAuthorityFactory",
]
