"""Demand-first supplied-case assembly over current normalized evidence."""

from __future__ import annotations

import copy
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort
from .gate5_deterministic_source_fact_consumption import (
    Gate5DeterministicSourceFactConsumptionRuntime,
    Gate5DeterministicSourceFactConsumptionRuntimeFactory,
)
from .gate5_full_declaration_definition import (
    Gate5FullDeclarationDefinitionAuthoringFactory,
    Gate5TrustedFullDeclarationDefinitionAuthority,
    Gate5TrustedFullDeclarationDefinitionAuthorityFactory,
)
from .gate5_trusted_methodology import (
    GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
    GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthorityFactory,
)


GATE5_REAL_TAX_CASE_ASSEMBLY_SCHEMA_VERSION = (
    "broker_reports_gate5_real_tax_case_assembly_v0"
)
GATE5_DECLARATION_DEMAND_ROW_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_demand_case_row_v0"
)
GATE5_REAL_CASE_ASSEMBLY_TERMINAL = "REAL_CASE_ASSEMBLY_PROVEN"
GATE5_EXACT_EVIDENCE_GAPS_TERMINAL = "EXACT_EVIDENCE_GAPS_LOCALIZED"

FACTORY_REQUIRED = (
    "Gate5RealTaxCaseAssemblyRuntimeFactory.create composes "
    "Gate5DeterministicSourceFactConsumptionRuntimeFactory.create, "
    "Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create and "
    "Gate5FullDeclarationDefinitionAuthoringFactory.create; "
    "Gate5TrustedMethodologyAuthorityFactory.create owns the declaration-input "
    "methodology binding",
)
FORBIDDEN = (
    "direct SQL, source-document parsing, LLM fact selection, synthetic "
    "supplement in REAL_EVIDENCE mode, reconciliation, evidence graph, "
    "persisted financial-event relations or real-world taxpayer completeness",
    "default taxpayer, filing, jurisdiction, currency, expense or tax value",
)

_EVIDENCE_MODES = {"REAL_EVIDENCE", "SYNTHETIC_CONTROL"}
_TERMINALS = {
    "AVAILABLE",
    "MISSING_EVIDENCE",
    "SOURCE_EVIDENCE_INSUFFICIENT",
    "METHODOLOGY_UNRESOLVED",
    "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
    "RESOLVED",
}
_SECURITY_TYPES = {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"}
_TAXABLE_INCOME_TYPES = {
    "COUPON_INCOME",
    "DIVIDEND_INCOME",
    "SECURITY_DISPOSAL",
}
_INCOME_TYPES_WITHOUT_PUBLISHED_METHOD = {
    "COUPON_INCOME",
    "DIVIDEND_INCOME",
    "INTEREST_INCOME",
    "SECURITIES_LENDING_INCOME",
}
_MANDATORY_MISSING_DOMAINS = {
    "filing_and_party_identity",
    "declaration_budget_disposition",
}


class Gate5RealTaxCaseAssemblyError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5RealTaxCaseAssemblyRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate5RealTaxCaseAssemblyRuntime":
        return Gate5RealTaxCaseAssemblyRuntime(
            source_runtime=(
                Gate5DeterministicSourceFactConsumptionRuntimeFactory(
                    store=self._store,
                    read_enabled=self._read_enabled,
                ).create()
            ),
            definition_authority=(
                Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create()
            ),
            obligation_package=(
                Gate5FullDeclarationDefinitionAuthoringFactory.create()
                .obligation_package()
            ),
            declaration_input_methodology=(
                Gate5TrustedMethodologyAuthorityFactory.create().resolve(
                    {
                        "schema_version": (
                            GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION
                        ),
                        "methodology_id": GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
                        "methodology_version": (
                            GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION
                        ),
                    }
                )
            ),
        )


class Gate5RealTaxCaseAssemblyRuntime:
    def __init__(
        self,
        *,
        source_runtime: Gate5DeterministicSourceFactConsumptionRuntime,
        definition_authority: Gate5TrustedFullDeclarationDefinitionAuthority,
        obligation_package: dict[str, Any],
        declaration_input_methodology: dict[str, Any],
    ) -> None:
        self._source_runtime = source_runtime
        self._definition_authority = definition_authority
        self._obligation_package = copy.deepcopy(obligation_package)
        self._declaration_input_methodology = copy.deepcopy(
            declaration_input_methodology
        )

    def assemble(
        self,
        *,
        source_fact_methodology_ref: dict[str, Any],
        context: ArtifactAccessContext,
        evidence_mode: str,
    ) -> dict[str, Any]:
        if evidence_mode not in _EVIDENCE_MODES:
            _fail("gate5_real_case_evidence_mode_invalid")
        source = self._source_runtime.assemble_available(
            methodology_ref=source_fact_methodology_ref,
            context=context,
        )
        publication = self._definition_authority.publication()
        contract = self._definition_authority.resolve_for_scope(
            publication["definition_id"],
            publication["definition_version"],
            publication["definition_sha256"],
        )
        definition = contract["definition"]
        package = self._validated_package(definition=definition)
        obligation_by_id = {
            item["obligation_id"]: item
            for item in package["reviewed_semantic_obligations"]
        }
        audit_by_domain = {
            item["domain_id"]: item
            for item in contract["applicability_audit"]["rows"]
        }
        rows: list[dict[str, Any]] = []
        for domain in definition["domains"]:
            audit = audit_by_domain[domain["domain_id"]]
            for obligation_ref in domain["obligation_refs"]:
                obligation = obligation_by_id[obligation_ref]
                terminal = _demand_terminal(
                    domain_id=domain["domain_id"],
                    obligation_ref=obligation_ref,
                    source=source,
                )
                row = _demand_row(
                    domain=domain,
                    audit=audit,
                    obligation=obligation,
                    terminal=terminal,
                    source=source,
                    publication=publication,
                )
                rows.append(row)
        rows.sort(key=lambda item: item["demand"])
        if len(rows) != 25 or set(item["terminal"] for item in rows) - _TERMINALS:
            _fail("gate5_real_case_demand_accounting_invalid")
        terminal_counts = {
            terminal: sum(item["terminal"] == terminal for item in rows)
            for terminal in sorted(_TERMINALS)
        }
        blockers = [
            copy.deepcopy(item["blocker"])
            for item in rows
            if item["blocker"] is not None
        ]
        methodology_demands = {
            item["demand"]
            for item in self._declaration_input_methodology["methodology"][
                "demand_bindings"
            ]
        }
        active_demands = {
            item["demand"]
            for item in rows
            if item["terminal"] != "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
        }
        if not active_demands.issubset(methodology_demands):
            _fail("gate5_real_case_methodology_demand_unmapped")
        case_terminals = (
            [GATE5_REAL_CASE_ASSEMBLY_TERMINAL]
            if evidence_mode == "REAL_EVIDENCE"
            else ["SYNTHETIC_CASE_ASSEMBLY_CONTROL"]
        )
        if blockers:
            case_terminals.append(GATE5_EXACT_EVIDENCE_GAPS_TERMINAL)
        return {
            "schema_version": GATE5_REAL_TAX_CASE_ASSEMBLY_SCHEMA_VERSION,
            "status": "assembled_for_supplied_case",
            "evidence_mode": evidence_mode,
            "terminals": case_terminals,
            "case_binding": copy.deepcopy(source["case_binding"]),
            "definition_binding": publication,
            "declaration_input_methodology_binding": copy.deepcopy(
                self._declaration_input_methodology["authority_binding"]
            ),
            "knowledge_origins": _knowledge_origins(
                source=source,
                package=package,
            ),
            "declaration_demands": rows,
            "blockers": blockers,
            "deterministic_calculations": copy.deepcopy(
                source["fifo_calculations"]
            ),
            "source_fact_assembly": source,
            "metrics": {
                "declaration_demands_total": len(rows),
                **terminal_counts,
                "source_documents": len(source["source_document_ids"]),
                "source_facts": source["facts_total"],
                "fifo_calculations": len(source["fifo_calculations"]),
                "tax_model_ready_calculations": source[
                    "tax_model_ready_calculations"
                ],
                "invented_facts": 0,
                "invented_relations": 0,
                "resolved_demands_with_complete_evidence_chain": all(
                    item["evidence_chain_complete"]
                    for item in rows
                    if item["terminal"] == "RESOLVED"
                ),
                "active_demands_with_methodology_binding": len(active_demands),
            },
            "multi_source_assembly": {
                "status": (
                    "PROVEN"
                    if len(source["source_document_ids"]) > 1
                    else "SINGLE_SOURCE_ONLY"
                ),
                "source_document_ids": copy.deepcopy(
                    source["source_document_ids"]
                ),
                "case_identity_semantics": (
                    "supplied evidence belongs to one authenticated case and "
                    "tax-period task; no event relatedness is implied"
                ),
            },
            "supplied_case_completeness_only": True,
            "real_world_taxpayer_completeness_asserted": False,
            "reconciliation": "not_performed",
            "invented_facts": 0,
            "invented_relations": 0,
            "stored_financial_event_relations": 0,
            "persistence": "none_new",
        }

    def _validated_package(self, *, definition: dict[str, Any]) -> dict[str, Any]:
        package = copy.deepcopy(self._obligation_package)
        binding = definition["obligation_package_binding"]
        if (
            package.get("package_id") != binding["package_id"]
            or package.get("package_version") != binding["package_version"]
            or len(package.get("reviewed_semantic_obligations", [])) != 25
        ):
            _fail("gate5_real_case_obligation_package_invalid")
        return package


def _demand_terminal(
    *,
    domain_id: str,
    obligation_ref: str,
    source: dict[str, Any],
) -> str:
    fact_types = source["financial_type_counts"]
    has_security = any(fact_types.get(item, 0) for item in _SECURITY_TYPES)
    has_taxable_income = any(fact_types.get(item, 0) for item in _TAXABLE_INCOME_TYPES)
    if domain_id in _MANDATORY_MISSING_DOMAINS:
        return "MISSING_EVIDENCE"
    if domain_id == "income_group_tax_results":
        if any(
            fact_types.get(item, 0)
            for item in _INCOME_TYPES_WITHOUT_PUBLISHED_METHOD
        ):
            return "METHODOLOGY_UNRESOLVED"
        return "SOURCE_EVIDENCE_INSUFFICIENT" if has_taxable_income else "MISSING_EVIDENCE"
    if domain_id == "taxable_income_by_source":
        return (
            "METHODOLOGY_UNRESOLVED"
            if has_taxable_income
            else "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
        )
    if domain_id == "financial_investment_results":
        if obligation_ref != "obl_securities_and_derivatives_results":
            return "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
        if not has_security:
            return "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
        security_blockers = [
            item
            for item in source["blockers"]
            if item.get("financial_type") in _SECURITY_TYPES
            or item.get("first_unresolved_disposal_fact_id")
        ]
        if security_blockers or not source["tax_model_ready_calculations"]:
            return "SOURCE_EVIDENCE_INSUFFICIENT"
        return "AVAILABLE"
    return "NOT_ACTIVATED_FOR_SUPPLIED_CASE"


def _demand_row(
    *,
    domain: dict[str, Any],
    audit: dict[str, Any],
    obligation: dict[str, Any],
    terminal: str,
    source: dict[str, Any],
    publication: dict[str, Any],
) -> dict[str, Any]:
    available = _available_evidence(
        domain_id=domain["domain_id"],
        obligation_ref=obligation["obligation_id"],
        source=source,
    )
    blocker = (
        None
        if terminal in {"AVAILABLE", "RESOLVED", "NOT_ACTIVATED_FOR_SUPPLIED_CASE"}
        else _demand_blocker(
            domain=domain,
            obligation=obligation,
            terminal=terminal,
            source=source,
            publication=publication,
        )
    )
    return {
        "schema_version": GATE5_DECLARATION_DEMAND_ROW_SCHEMA_VERSION,
        "demand": obligation["obligation_id"],
        "domain_id": domain["domain_id"],
        "required_tax_rule": {
            "definition_id": publication["definition_id"],
            "definition_version": publication["definition_version"],
            "applicability_policy": audit["policy"],
            "official_evidence_refs": copy.deepcopy(
                obligation["official_evidence_refs"]
            ),
        },
        "required_evidence": obligation["semantic_requirement"],
        "available_evidence": available,
        "terminal": terminal,
        "blocker": blocker,
        "evidence_chain_complete": terminal == "RESOLVED",
    }


def _available_evidence(
    *, domain_id: str, obligation_ref: str, source: dict[str, Any]
) -> dict[str, Any]:
    relevant_types: set[str] = set()
    if domain_id in {"income_group_tax_results", "taxable_income_by_source"}:
        relevant_types = _TAXABLE_INCOME_TYPES
    elif domain_id == "financial_investment_results":
        if obligation_ref == "obl_securities_and_derivatives_results":
            relevant_types = _SECURITY_TYPES | {
                "COMMISSION",
                "COMMISSION_TOTAL",
                "TRANSACTION_CHARGE",
                "TAX_WITHHELD",
                "TAX_WITHHELD_TOTAL",
            }
    fact_ids = sorted(
        fact_id
        for financial_type in relevant_types
        for fact_id in source["fact_ids_by_financial_type"].get(financial_type, [])
    )
    return {
        "knowledge_origin": "A_SOURCE_FINANCIAL_FACT",
        "fact_ids": fact_ids,
        "source_document_ids": copy.deepcopy(source["source_document_ids"]),
        "deterministic_calculation_count": (
            len(source["fifo_calculations"])
            if domain_id
            in {"income_group_tax_results", "financial_investment_results"}
            else 0
        ),
    }


def _demand_blocker(
    *,
    domain: dict[str, Any],
    obligation: dict[str, Any],
    terminal: str,
    source: dict[str, Any],
    publication: dict[str, Any],
) -> dict[str, Any]:
    domain_id = domain["domain_id"]
    reason, closing = _blocker_explanation(
        domain_id=domain_id,
        terminal=terminal,
        source=source,
    )
    return {
        "declaration_demand": obligation["obligation_id"],
        "methodology": {
            "declaration_definition_id": publication["definition_id"],
            "declaration_definition_version": publication["definition_version"],
            "source_fact_methodology_binding": copy.deepcopy(
                source["methodology_binding"]
            ),
        },
        "required_fact": obligation["semantic_requirement"],
        "evidence_searched": {
            "knowledge_origins": [
                "A_SOURCE_FINANCIAL_FACT",
                "B_EXTERNAL_REFERENCE_FACT",
                "C_USER_CASE_FACT",
                "D_METHODOLOGY_DERIVED_TAX_FACT",
                "E_DECLARATION_FILING_CONTEXT",
            ],
            "source_document_ids": copy.deepcopy(source["source_document_ids"]),
            "source_fact_count": source["facts_total"],
            "source_fact_blocker_reason_codes": sorted(
                {item["reason_code"] for item in source["blockers"]}
            ),
        },
        "terminal": terminal,
        "why_supplied_evidence_is_insufficient": reason,
        "evidence_that_could_close": closing,
    }


def _blocker_explanation(
    *, domain_id: str, terminal: str, source: dict[str, Any]
) -> tuple[str, str]:
    if domain_id == "filing_and_party_identity":
        return (
            "no authenticated taxpayer, period-status, signer or filing-instance fact was supplied",
            "authenticated user/case and filing-context evidence for the named obligation",
        )
    if domain_id == "declaration_budget_disposition":
        return (
            "no complete tax settlement or authenticated budget-disposition instruction exists",
            "a complete supported settlement plus authenticated payment/refund disposition evidence",
        )
    if domain_id == "taxable_income_by_source":
        return (
            "the published Article 208 and Article 232 input contract identifies the required payer, jurisdiction, treaty and foreign-tax evidence, but the typed evidence bridge or reviewed treaty detail is incomplete",
            "supply the exact factual inputs and close the declared contract or treaty-methodology gap; do not infer source or credit in the source adapter",
        )
    if domain_id in {"income_group_tax_results", "financial_investment_results"}:
        if terminal == "METHODOLOGY_UNRESOLVED":
            return (
                "dividend, coupon or other income observations are preserved and the published input contract names their rules, but the typed inputs or executable reviewed methodology needed for a complete 2025 income-group result remain unresolved",
                "supply the exact payer, currency, date, market and tax-agent facts and close the declared contract or methodology gap; do not infer them in the source adapter",
            )
        first = source["blockers"][0] if source["blockers"] else None
        reason = (
            "no complete tax-model-ready securities calculation can be assembled from the supplied facts"
            if first is None
            else f"source-fact assembly stops at {first['reason_code']}"
        )
        closing = (
            "the exact acquisition, date, instrument, currency or direct-expense evidence named by the source-fact blockers; then the existing tax-model and category factories can execute"
        )
        return reason, closing
    return (
        "required evidence was not supplied",
        "authoritative evidence satisfying the named declaration obligation",
    )


def _knowledge_origins(
    *, source: dict[str, Any], package: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        {
            "origin": "A_SOURCE_FINANCIAL_FACT",
            "status": "AVAILABLE" if source["facts_total"] else "MISSING_EVIDENCE",
            "count": source["facts_total"],
            "authority": "Gate4FinancialCaseRuntimeFactory.create",
        },
        {
            "origin": "B_EXTERNAL_REFERENCE_FACT",
            "status": "AVAILABLE",
            "count": len(package["official_evidence"]["sources"]),
            "authority": "Gate5FullDeclarationDefinitionAuthoringFactory.create",
        },
        {
            "origin": "C_USER_CASE_FACT",
            "status": "MISSING_EVIDENCE",
            "count": 0,
            "authority": "not_supplied",
        },
        {
            "origin": "D_METHODOLOGY_DERIVED_TAX_FACT",
            "status": "AVAILABLE" if source["fifo_calculations"] else "MISSING_EVIDENCE",
            "count": len(source["fifo_calculations"]),
            "authority": "Gate5DeterministicSourceFactConsumptionRuntimeFactory.create",
        },
        {
            "origin": "E_DECLARATION_FILING_CONTEXT",
            "status": "MISSING_EVIDENCE",
            "count": 0,
            "authority": "not_supplied",
        },
    ]


def _fail(code: str, field: str = "") -> None:
    raise Gate5RealTaxCaseAssemblyError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_DEMAND_ROW_SCHEMA_VERSION",
    "GATE5_EXACT_EVIDENCE_GAPS_TERMINAL",
    "GATE5_REAL_CASE_ASSEMBLY_TERMINAL",
    "GATE5_REAL_TAX_CASE_ASSEMBLY_SCHEMA_VERSION",
    "Gate5RealTaxCaseAssemblyError",
    "Gate5RealTaxCaseAssemblyRuntime",
    "Gate5RealTaxCaseAssemblyRuntimeFactory",
]
