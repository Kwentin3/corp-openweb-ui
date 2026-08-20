"""Deterministic evidence-coverage findings in the client's interest."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort
from .gate5_deterministic_source_fact_consumption import (
    GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_SCHEMA_VERSION,
    Gate5DeterministicSourceFactConsumptionRuntime,
    Gate5DeterministicSourceFactConsumptionRuntimeFactory,
)
from .gate5_evidence_demand import GATE5_GAP_OWNER_CLASSIFICATIONS


GATE5_CLIENT_EVIDENCE_REVIEW_SCHEMA_VERSION = (
    "broker_reports_gate5_client_evidence_review_v0"
)
GATE5_CLIENT_EVIDENCE_FINDING_SCHEMA_VERSION = (
    "broker_reports_gate5_client_evidence_finding_v0"
)
GATE5_CLIENT_EVIDENCE_REVIEW_TERMINAL = "CLIENT_EVIDENCE_REVIEW_PROVEN"

FACTORY_REQUIRED = (
    "Gate5ClientEvidenceReviewRuntimeFactory.create composes "
    "Gate5DeterministicSourceFactConsumptionRuntimeFactory.create",
)
FORBIDDEN = (
    "stored transaction relations, proximity matching, LLM transaction review, "
    "commission allocation, reconciliation, inferred basis, generic risk engine "
    "or tax calculation",
)

_INCOME_TYPES = {
    "COUPON_INCOME",
    "DIVIDEND_INCOME",
    "INTEREST_INCOME",
    "SECURITIES_LENDING_INCOME",
    "SECURITY_DISPOSAL",
}


class Gate5ClientEvidenceReviewError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Gate5ClientEvidenceReviewRuntimeFactory:
    def __init__(self, *, store: ArtifactStorePort, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate5ClientEvidenceReviewRuntime":
        return Gate5ClientEvidenceReviewRuntime(
            source_runtime=Gate5DeterministicSourceFactConsumptionRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create()
        )


class Gate5ClientEvidenceReviewRuntime:
    def __init__(
        self, *, source_runtime: Gate5DeterministicSourceFactConsumptionRuntime
    ) -> None:
        self._source_runtime = source_runtime

    def review(
        self,
        *,
        methodology_ref: dict[str, Any] | None = None,
        context: ArtifactAccessContext | None = None,
        source_assembly: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if source_assembly is None:
            if methodology_ref is None or context is None:
                _fail("gate5_client_review_source_required")
            source_assembly = self._source_runtime.assemble_available(
                methodology_ref=methodology_ref,
                context=context,
            )
        source = _validated_source(source_assembly)
        findings = [_source_blocker_finding(item) for item in source["blockers"]]
        advisory = _withholding_advisory(source)
        if advisory is not None:
            findings.append(advisory)
        findings.sort(
            key=lambda item: (
                0 if item["kind"] == "REQUIRED_BLOCKER" else 1,
                item["reason_code"],
                item["finding_id"],
            )
        )
        required = [
            copy.deepcopy(item)
            for item in findings
            if item["kind"] == "REQUIRED_BLOCKER"
        ]
        advisories = [
            copy.deepcopy(item)
            for item in findings
            if item["kind"] == "ADVISORY_FINDING"
        ]
        coverage_rows = [_coverage_row(item) for item in source["security_groups"]]
        return {
            "schema_version": GATE5_CLIENT_EVIDENCE_REVIEW_SCHEMA_VERSION,
            "status": "reviewed",
            "terminals": [GATE5_CLIENT_EVIDENCE_REVIEW_TERMINAL],
            "coverage": coverage_rows,
            "required_blockers": required,
            "advisory_findings": advisories,
            "llm_adapter_input": {
                "schema_version": "broker_reports_gate5_client_finding_adapter_input_v0",
                "required": [_llm_finding(item) for item in required],
                "advisory": [_llm_finding(item) for item in advisories],
                "raw_transactions_supplied": False,
                "calculation_authority": False,
            },
            "metrics": {
                "coverage_groups": len(coverage_rows),
                "required_blockers": len(required),
                "advisory_findings": len(advisories),
                "invented_facts": 0,
                "invented_relations": 0,
            },
            "commission_sanity": {
                "mode": source["assertions"]["commissions"]["mode"],
                "detail_count": len(source["assertions"]["commissions"]["detail"]),
                "aggregate_count": len(
                    source["assertions"]["commissions"]["aggregate"]
                ),
                "reconciliation": "not_performed",
            },
            "withheld_tax_sanity": {
                "mode": source["assertions"]["withheld_tax"]["mode"],
                "detail_count": len(source["assertions"]["withheld_tax"]["detail"]),
                "aggregate_count": len(
                    source["assertions"]["withheld_tax"]["aggregate"]
                ),
                "reconciliation": "not_performed",
            },
            "stored_transaction_relations": 0,
            "reconciliation": "not_performed",
        }


def _validated_source(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version")
        != GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_SCHEMA_VERSION
        or not isinstance(value.get("security_groups"), list)
        or not isinstance(value.get("blockers"), list)
        or not isinstance(value.get("assertions"), dict)
    ):
        _fail("gate5_client_review_source_invalid")
    return copy.deepcopy(value)


def _source_blocker_finding(blocker: dict[str, Any]) -> dict[str, Any]:
    quantitative = {
        key: blocker[key]
        for key in (
            "required_quantity",
            "available_prior_quantity",
            "minimum_missing_quantity",
        )
        if key in blocker
    }
    coverage = copy.deepcopy(blocker.get("acquisition_basis_coverage"))
    is_acquisition_gap = (
        isinstance(coverage, dict)
        and coverage.get("concept") == "ACQUISITION_BASIS_COVERAGE_GAP"
        and coverage.get("coverage_status") == "GAP"
    )
    routing = _blocker_routing(blocker, is_acquisition_gap=is_acquisition_gap)
    if routing["gap_owner_classification"] not in GATE5_GAP_OWNER_CLASSIFICATIONS:
        _fail("gate5_client_review_gap_owner_classification_invalid")
    base = {
        "schema_version": GATE5_CLIENT_EVIDENCE_FINDING_SCHEMA_VERSION,
        "kind": "REQUIRED_BLOCKER",
        "priority": "HIGH",
        "reason_code": str(blocker.get("reason_code") or "unknown"),
        "consumer_demands": [
            "obl_securities_and_derivatives_results",
            "obl_income_group_tax_base_results",
        ],
        "subject": {
            key: blocker[key]
            for key in ("asset", "currency", "disposal_date")
            if key in blocker
        },
        "quantitative_gap": quantitative,
        "acquisition_basis_coverage": coverage,
        "evidence_searched": copy.deepcopy(blocker.get("evidence_searched") or {}),
        "why": str(blocker.get("why_insufficient") or blocker.get("reason_code")),
        "helpful_evidence": str(blocker.get("closing_evidence") or ""),
        "closure_type": routing["closure_type"],
        "gap_owner_classification": routing["gap_owner_classification"],
        "routing": routing,
        "client_benefit_rationale": (
            "Closing the quantified acquisition-basis coverage gap may support "
            "documented acquisition costs. This review does not treat uncovered "
            "quantity as zero-cost disposal and does not make a gross-proceeds "
            "tax conclusion."
            if is_acquisition_gap
            else "Closing this exact source-evidence gap supplies an input required "
            "by the current deterministic methodology without deciding its tax "
            "effect in the review layer."
        ),
        "required_for_current_methodology": (
            blocker.get("current_methodology_blocking_decision") == "BLOCKED"
            if is_acquisition_gap
            else True
        ),
        "blocking_authority": blocker.get("current_methodology_blocking_authority"),
        "tax_conclusion": "NOT_MADE",
    }
    return {**base, "finding_id": "g5finding_" + _sha256(base)[:32]}


def _blocker_routing(
    blocker: dict[str, Any], *, is_acquisition_gap: bool
) -> dict[str, Any]:
    reason = blocker.get("reason_code")
    if reason == "gate5_source_fact_required_role_missing":
        return {
            "ownership_state": "SOURCE_HAS_IT_ROLE_BINDING_LOST",
            "route": "UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW",
            "owner": (
                "Gate3EvidenceDemandPortFactory.create -> "
                "Gate4FinancialCaseMaterializerFactory.create"
            ),
            "closure_type": "EXISTING_EVIDENCE",
            "gap_owner_classification": "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
            "user_or_additional_document_allowed": False,
        }
    if reason == "gate5_source_fact_decimal_invalid":
        return {
            "ownership_state": "SOURCE_HAS_IT_NORMALIZATION_FAILED",
            "route": "NORMALIZATION_OWNER_REVIEW",
            "owner": "Gate4FinancialCaseMaterializerFactory.create",
            "closure_type": "EXISTING_EVIDENCE",
            "gap_owner_classification": "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
            "user_or_additional_document_allowed": False,
        }
    if blocker.get("terminal") == "METHODOLOGY_UNRESOLVED":
        return {
            "ownership_state": "METHODOLOGY_UNRESOLVED",
            "route": "METHODOLOGY_RESEARCH",
            "owner": "Gate5TrustedMethodologyAuthorityFactory.create",
            "closure_type": "METHODOLOGY_RESEARCH",
            "gap_owner_classification": "METHODOLOGY_RULE_MISSING",
            "user_or_additional_document_allowed": False,
        }
    if reason == "gate5_source_fact_currency_invalid":
        return {
            "ownership_state": "EXTERNAL_AUTHORITY_REQUIRED",
            "route": "EXTERNAL_AUTHORITY_REVIEW",
            "owner": "authoritative_external_reference_owner",
            "closure_type": "EXTERNAL_AUTHORITY",
            "gap_owner_classification": "EXTERNAL_AUTHORITATIVE_FACT_MISSING",
            "user_or_additional_document_allowed": False,
        }
    if is_acquisition_gap or reason == "gate5_source_fact_direct_expense_missing":
        return {
            "ownership_state": "SOURCE_ABSENT_WITHIN_SUPPLIED_EVIDENCE_HORIZON",
            "route": "EVIDENCE_HORIZON_EXTERNAL_DEMAND",
            "owner": "Gate5HumanGapClosureRuntimeFactory.create",
            "closure_type": "ADDITIONAL_DOCUMENT",
            "gap_owner_classification": "REAL_SOURCE_EVIDENCE_MISSING",
            "user_or_additional_document_allowed": True,
        }
    return {
        "ownership_state": "OWNER_UNRESOLVED",
        "route": "OWNER_UNRESOLVED",
        "owner": "OWNER_UNRESOLVED",
        "closure_type": "OWNER_UNRESOLVED",
        "gap_owner_classification": "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
        "user_or_additional_document_allowed": False,
    }


def _withholding_advisory(source: dict[str, Any]) -> dict[str, Any] | None:
    has_income = any(
        source["financial_type_counts"].get(financial_type, 0)
        for financial_type in _INCOME_TYPES
    )
    withheld = source["assertions"]["withheld_tax"]
    incomplete = sum(
        item.get("status") == "role_incomplete"
        for item in [*withheld["detail"], *withheld["aggregate"]]
    )
    if not has_income or (withheld["detail"] or withheld["aggregate"]) and not incomplete:
        return None
    reason = (
        "withholding_evidence_absent"
        if not withheld["detail"] and not withheld["aggregate"]
        else "withholding_evidence_incomplete"
    )
    base = {
        "schema_version": GATE5_CLIENT_EVIDENCE_FINDING_SCHEMA_VERSION,
        "kind": "ADVISORY_FINDING",
        "priority": "MEDIUM",
        "reason_code": reason,
        "consumer_demands": [
            "obl_russian_source_taxable_income",
            "obl_foreign_source_taxable_income_and_foreign_tax",
        ],
        "subject": {},
        "quantitative_gap": {},
        "acquisition_basis_coverage": None,
        "evidence_searched": {
            "detail_withheld_facts": len(withheld["detail"]),
            "aggregate_withheld_facts": len(withheld["aggregate"]),
            "role_incomplete_facts": incomplete,
        },
        "why": reason,
        "helpful_evidence": (
            "a tax-agent certificate or broker document that explicitly states "
            "withheld tax, currency, period and applicable income context"
        ),
        "closure_type": "ADDITIONAL_DOCUMENT",
        "gap_owner_classification": "REAL_SOURCE_EVIDENCE_MISSING",
        "client_benefit_rationale": (
            "Authoritative withholding evidence may support credit for tax already "
            "paid or prevent an avoidable overstatement of tax payable."
        ),
        "required_for_current_methodology": False,
        "blocking_authority": None,
        "tax_conclusion": "NOT_MADE",
    }
    return {**base, "finding_id": "g5finding_" + _sha256(base)[:32]}


def _coverage_row(group: dict[str, Any]) -> dict[str, Any]:
    blocker = group.get("blocker") or {}
    acquisition_coverage = blocker.get("acquisition_basis_coverage") or {}
    return {
        "asset": group["asset"],
        "currency": group["currency"],
        "status": group["status"],
        "purchase_fact_count": len(group["purchase_fact_ids"]),
        "disposal_fact_count": len(group["disposal_fact_ids"]),
        "resolved_disposals": group["resolved_disposals"],
        "first_required_quantity": blocker.get("required_quantity"),
        "first_supported_prior_quantity": blocker.get("available_prior_quantity"),
        "first_minimum_gap_quantity": blocker.get("minimum_missing_quantity"),
        "acquisition_basis_coverage": copy.deepcopy(
            acquisition_coverage if acquisition_coverage else None
        ),
        "source_document_count": len(group["source_document_ids"]),
        "stored_relations": 0,
    }


def _llm_finding(item: dict[str, Any]) -> dict[str, Any]:
    result = {
        "finding_id": item["finding_id"],
        "kind": item["kind"],
        "priority": item["priority"],
        "reason_code": item["reason_code"],
        "gap_owner_classification": item["gap_owner_classification"],
        "subject": copy.deepcopy(item["subject"]),
        "quantitative_gap": copy.deepcopy(item["quantitative_gap"]),
        "acquisition_basis_coverage": copy.deepcopy(
            item["acquisition_basis_coverage"]
        ),
        "why": item["why"],
        "helpful_evidence": item["helpful_evidence"],
        "client_benefit_rationale": item["client_benefit_rationale"],
        "required_for_current_methodology": item[
            "required_for_current_methodology"
        ],
        "blocking_authority": item["blocking_authority"],
        "tax_conclusion": item["tax_conclusion"],
    }
    if "routing" in item:
        result["routing"] = copy.deepcopy(item["routing"])
    return result


def _sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fail(code: str) -> None:
    raise Gate5ClientEvidenceReviewError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_CLIENT_EVIDENCE_FINDING_SCHEMA_VERSION",
    "GATE5_CLIENT_EVIDENCE_REVIEW_SCHEMA_VERSION",
    "GATE5_CLIENT_EVIDENCE_REVIEW_TERMINAL",
    "Gate5ClientEvidenceReviewError",
    "Gate5ClientEvidenceReviewRuntime",
    "Gate5ClientEvidenceReviewRuntimeFactory",
]
