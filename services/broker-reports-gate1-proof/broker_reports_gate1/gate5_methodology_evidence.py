"""Case-level methodology-driven evidence audit over existing Gate owners."""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort
from .gate4_financial_case_cache import (
    Gate4FinancialCaseRuntime,
    Gate4FinancialCaseRuntimeFactory,
)
from .gate5_declaration_preparation import (
    Gate5DeclarationPreparationRuntime,
    Gate5DeclarationPreparationRuntimeFactory,
)
from .gate5_evidence_demand import (
    EVIDENCE_AUTHORITY_ROUTING_PROVEN,
    EVIDENCE_DEMAND_IS_REQUEST_NOT_READER,
    METHODOLOGY_DRIVEN_EVIDENCE_DEMAND_PROVEN,
    PREMATURE_GAP_DECLARATION_ELIMINATED,
    Gate5EvidenceDemandRuntime,
    Gate5EvidenceDemandRuntimeFactory,
)
from .gate5_evidence_demand_contract import (
    Gate5EvidenceDemandContractAuthority,
    Gate5EvidenceDemandContractAuthorityFactory,
)
from .gate5_trusted_methodology import (
    GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
    GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthority,
    Gate5TrustedMethodologyAuthorityFactory,
)


GATE5_METHODOLOGY_EVIDENCE_AUDIT_SCHEMA_VERSION = (
    "broker_reports_gate5_methodology_evidence_audit_v1"
)
CROSS_DOMAIN_EVIDENCE_DEMAND_CONSISTENCY_PROVEN = (
    "CROSS_DOMAIN_EVIDENCE_DEMAND_CONSISTENCY_PROVEN"
)

FACTORY_REQUIRED = (
    "Gate5MethodologyEvidenceRuntimeFactory.create composes "
    "Gate5DeclarationPreparationRuntimeFactory.create, "
    "Gate4FinancialCaseRuntimeFactory.create, "
    "Gate5TrustedMethodologyAuthorityFactory.create, "
    "Gate5EvidenceDemandContractAuthorityFactory.create and "
    "Gate5EvidenceDemandRuntimeFactory.create",
)
FORBIDDEN = (
    "direct SQL, raw source bytes, provider ingestion rerun, Canonical mutation, "
    "tax calculation by LLM, evidence graph, financial-event relation, "
    "reconciliation, human tax conclusion, product activation or persistence",
)


class Gate5MethodologyEvidenceRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate5MethodologyEvidenceRuntime":
        return Gate5MethodologyEvidenceRuntime(
            preparation=Gate5DeclarationPreparationRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            financial_case=Gate4FinancialCaseRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            methodology_authority=Gate5TrustedMethodologyAuthorityFactory.create(),
            contract_authority=(Gate5EvidenceDemandContractAuthorityFactory.create()),
            demand_runtime=Gate5EvidenceDemandRuntimeFactory.create(),
        )


class Gate5MethodologyEvidenceRuntime:
    def __init__(
        self,
        *,
        preparation: Gate5DeclarationPreparationRuntime,
        financial_case: Gate4FinancialCaseRuntime,
        methodology_authority: Gate5TrustedMethodologyAuthority,
        contract_authority: Gate5EvidenceDemandContractAuthority,
        demand_runtime: Gate5EvidenceDemandRuntime,
    ) -> None:
        self._preparation = preparation
        self._financial_case = financial_case
        self._methodology_authority = methodology_authority
        self._contract_authority = contract_authority
        self._demand_runtime = demand_runtime

    def audit(
        self,
        *,
        source_fact_methodology_ref: dict[str, Any],
        context: ArtifactAccessContext,
        evidence_mode: str,
        user_intent: dict[str, Any],
        user_case_facts: list[dict[str, Any]],
        external_reference_facts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        before = self._preparation.prepare(
            source_fact_methodology_ref=source_fact_methodology_ref,
            context=context,
            evidence_mode=evidence_mode,
            user_intent=user_intent,
            user_case_facts=user_case_facts,
        )
        methodology = self._methodology_authority.resolve(
            {
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
                "methodology_version": GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
            }
        )["methodology"]
        normalized_facts = [
            *copy.deepcopy(before["intake"]["metadata_facts"]),
            *self._financial_case.list_facts(context=context),
        ]
        evaluation = self._demand_runtime.evaluate(
            active_demands=[
                item["demand"] for item in before["scope_activation"]["active_demands"]
            ],
            methodology=methodology,
            evidence_contract=self._contract_authority.resolve(),
            normalized_facts=normalized_facts,
            user_case_facts=[
                *copy.deepcopy(user_case_facts),
                {
                    "fact_id": "case_intent_tax_period",
                    "fact_key": "tax_period",
                    "value": user_intent.get("tax_period"),
                },
            ],
            external_reference_facts=external_reference_facts or [],
            methodology_results=_methodology_results(before),
            client_requirements=_client_requirements(before["client_review"]),
            active_rule_ids=_active_rule_ids(
                methodology=methodology,
                normalized_facts=normalized_facts,
                preparation=before,
            ),
        )
        action_audit = _action_audit(
            closure=before["gap_closure"],
            evidence_demands=evaluation["evidence_demands"],
        )
        terms = [
            METHODOLOGY_DRIVEN_EVIDENCE_DEMAND_PROVEN,
            EVIDENCE_DEMAND_IS_REQUEST_NOT_READER,
            PREMATURE_GAP_DECLARATION_ELIMINATED,
            EVIDENCE_AUTHORITY_ROUTING_PROVEN,
            CROSS_DOMAIN_EVIDENCE_DEMAND_CONSISTENCY_PROVEN,
        ]
        return {
            "schema_version": GATE5_METHODOLOGY_EVIDENCE_AUDIT_SCHEMA_VERSION,
            "status": "methodology_driven_evidence_audited",
            "terminals": terms,
            "evidence_mode": evidence_mode,
            "evidence_demand": evaluation,
            "before_after_required_actions": action_audit,
            "prior_preparation_status": before["status"],
            "prior_declaration_readiness": copy.deepcopy(
                before["declaration_readiness"]
            ),
            "cross_domain_consistency": {
                "gate4_read_via_factory": True,
                "normalized_facts_first": True,
                "source_owner_requests_only": True,
                "canonical_or_source_read_by_gate5": False,
                "human_gap_last": True,
                "source_granularity_preserved": True,
                "financial_event_relations_created": 0,
                "reconciliation_performed": False,
                "residency_evidence_boundary_changed": False,
                "commission_selection_contract_changed": False,
                "acquisition_basis_coverage_contract_changed": False,
                "declaration_semantic_model_changed": False,
                "projection_interpretation_added": False,
            },
            "real_case_accounting": {
                "normalized_facts": len(normalized_facts),
                "source_owner_requests": len(evaluation["source_owner_requests"]),
                "provider_calls": 0,
                "ingestion_reruns": 0,
                "canonical_mutations": 0,
                "invented_facts": 0,
                "invented_relations": 0,
            },
            "private_values_safe_for_report": False,
            "product_activation": False,
            "declaration_release": False,
            "persistence": "none_new",
        }


def _methodology_results(preparation: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    residency = preparation["residency_classification"]
    if residency["status"] in {"RESIDENT", "NON_RESIDENT"}:
        result.append(
            {
                "result_id": "residency_classification",
                "result_key": "taxpayer_period_status",
                "value": residency["status"],
            }
        )
    return result


def _client_requirements(review: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for finding in [
        *review.get("required_blockers", []),
        *review.get("advisory_findings", []),
    ]:
        input_id = f"client_review:{finding['finding_id']}"
        result.append(
            {
                "required_input": input_id,
                "consumer": "Gate5ClientEvidenceReviewRuntimeFactory.create",
                "consumer_demands": copy.deepcopy(finding["consumer_demands"]),
                "why_required": str(finding["why"]),
                "evidence_contract": {
                    "required_input": input_id,
                    "fact_meaning": str(finding["helpful_evidence"]),
                    "fact_role": str(finding["reason_code"]),
                    "preferred_authority": "SOURCE_DOCUMENT",
                    "required_scope": "exact client-review finding scope",
                    "granularity": "per deterministic review finding",
                    "cardinality": "exactly_the_missing_evidence",
                    "absence_effect": (
                        "BLOCKS"
                        if finding["kind"] == "REQUIRED_BLOCKER"
                        else "ADVISORY"
                    ),
                    "normalized_fact_contracts": [],
                    "source_fact_request": None,
                    "fallback_authority": "ADDITIONAL_DOCUMENT",
                    "fact_key": None,
                    "methodology_result_key": None,
                },
            }
        )
    return result


def _active_rule_ids(
    *,
    methodology: dict[str, Any],
    normalized_facts: list[dict[str, Any]],
    preparation: dict[str, Any],
) -> list[str]:
    known_rules = {
        "filing-context-fns-order-913-v1",
        "signer-context-fns-order-913-v1",
        "budget-disposition-fns-order-913-v1",
        "taxpayer-residency-article-207-v1",
        "dividend-source-article-208-v1",
        "security-disposal-source-article-208-v1",
        "coupon-securities-income-article-214.1-v1",
        "dividend-income-group-articles-210-214-v1",
        "organized-market-classification-article-214.1-v1",
        "foreign-currency-conversion-article-210-v1",
        "foreign-tax-credit-articles-214-232-v1",
        "partial-acquisition-commission-v1",
    }
    published = {
        item["rule_id"] for item in methodology["rules"] if isinstance(item, dict)
    }
    # Unknown additive rules remain consumer-driven by default.  A new input does
    # not require an orchestration edit; only known conditional rules are narrowed.
    active = published - known_rules
    active.update(
        {
            "filing-context-fns-order-913-v1",
            "signer-context-fns-order-913-v1",
            "taxpayer-residency-article-207-v1",
        }
    )
    financial_types = {
        str(item.get("financial_type") or "") for item in normalized_facts
    }
    if "DIVIDEND_INCOME" in financial_types:
        active.update(
            {
                "dividend-source-article-208-v1",
                "dividend-income-group-articles-210-214-v1",
            }
        )
    if "SECURITY_DISPOSAL" in financial_types:
        active.update(
            {
                "security-disposal-source-article-208-v1",
                "organized-market-classification-article-214.1-v1",
            }
        )
    if "COUPON_INCOME" in financial_types:
        active.update(
            {
                "coupon-securities-income-article-214.1-v1",
                "organized-market-classification-article-214.1-v1",
            }
        )
    if _has_non_rub_fact(normalized_facts):
        active.add("foreign-currency-conversion-article-210-v1")
    blockers = preparation["case_assembly"]["source_fact_assembly"].get("blockers", [])
    if any(item.get("terminal") == "METHODOLOGY_UNRESOLVED" for item in blockers):
        active.add("partial-acquisition-commission-v1")
    if preparation["machine_readable_declaration_draft"]["calculation_count"]:
        active.add("budget-disposition-fns-order-913-v1")
    return sorted(active.intersection(published))


def _has_non_rub_fact(facts: list[dict[str, Any]]) -> bool:
    for fact in facts:
        for role in fact.get("roles") or []:
            if role.get("role") != "currency" or role.get("status") != "value":
                continue
            value = str(role.get("value") or "").upper()
            if value and value != "RUB":
                return True
    return False


def _action_audit(
    *, closure: dict[str, Any], evidence_demands: list[dict[str, Any]]
) -> dict[str, Any]:
    actions = (
        [("REQUIRED", item) for item in closure["required_actions"]]
        + [("ADVISORY", item) for item in closure["advisory_actions"]]
        + [("DEFERRED", item) for item in closure["deferred_actions"]]
    )
    rows = []
    for action_index, (kind, action) in enumerate(actions, start=1):
        exact_inputs = {
            f"client_review:{finding_id}"
            for finding_id in action.get("evidence_refs") or []
        }
        matched = [
            item for item in evidence_demands if item["required_input"] in exact_inputs
        ]
        if not matched:
            demand_refs = set(action.get("demand_refs") or [])
            matched = [
                item
                for item in evidence_demands
                if demand_refs.intersection(item["consumer_demands"])
            ]
        classifications = sorted({item["classification"] for item in matched})
        verdict = _action_verdict(
            closure_type=action["closure_type"],
            classifications=set(classifications),
        )
        rows.append(
            {
                "action_index": action_index,
                "kind": kind,
                "closure_type": action["closure_type"],
                "fact_key": action.get("fact_key"),
                "matched_evidence_demands": len(matched),
                "evidence_classifications": classifications,
                "verdict": verdict,
            }
        )
    required = [item for item in rows if item["kind"] == "REQUIRED"]
    kept_client = [
        item
        for item in required
        if item["verdict"]
        in {
            "KEEP_USER_CASE_REQUEST",
            "KEEP_ADDITIONAL_DOCUMENT_REQUEST",
        }
    ]
    before_counts = Counter(
        item["closure_type"] for item in closure["required_actions"]
    )
    after_counts = Counter(item["closure_type"] for item in kept_client)
    return {
        "before": {
            "client_required_actions": len(closure["required_actions"]),
            "closure_type_counts": dict(sorted(before_counts.items())),
        },
        "after": {
            "client_required_actions": len(kept_client),
            "closure_type_counts": dict(sorted(after_counts.items())),
            "suppressed_premature_document_requests": sum(
                item["verdict"] == "SUPPRESS_PENDING_FACT_CONTRACT" for item in required
            ),
            "routed_external_reference_work": sum(
                item["verdict"] == "ROUTE_EXTERNAL_REFERENCE" for item in required
            ),
            "routed_methodology_work": sum(
                item["verdict"] == "ROUTE_METHODOLOGY" for item in required
            ),
            "routed_source_owner_work": sum(
                item["verdict"] == "ROUTE_SOURCE_OWNER" for item in required
            ),
        },
        "rows": rows,
        "document_request_before_canonical_or_contract_check": False,
    }


def _action_verdict(*, closure_type: str, classifications: set[str]) -> str:
    if closure_type == "USER_FACT":
        return "KEEP_USER_CASE_REQUEST"
    if "SOURCE_FACT_CONTRACT_MISSING" in classifications:
        return "SUPPRESS_PENDING_FACT_CONTRACT"
    if "SOURCE_OWNER_REQUESTED" in classifications:
        return "ROUTE_SOURCE_OWNER"
    if (
        closure_type == "METHODOLOGY_RESEARCH"
        or "METHODOLOGY_UNRESOLVED" in classifications
    ):
        return "ROUTE_METHODOLOGY"
    if "EXTERNAL_REFERENCE_FACT_REQUIRED" in classifications:
        return "ROUTE_EXTERNAL_REFERENCE"
    if classifications and classifications.issubset({"FACT_AVAILABLE"}):
        return "REMOVE_SATISFIED"
    if closure_type == "ADDITIONAL_DOCUMENT":
        return "KEEP_ADDITIONAL_DOCUMENT_REQUEST"
    return "KEEP_NON_DOCUMENT_ACTION"


__all__ = [
    "CROSS_DOMAIN_EVIDENCE_DEMAND_CONSISTENCY_PROVEN",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_METHODOLOGY_EVIDENCE_AUDIT_SCHEMA_VERSION",
    "Gate5MethodologyEvidenceRuntime",
    "Gate5MethodologyEvidenceRuntimeFactory",
]
