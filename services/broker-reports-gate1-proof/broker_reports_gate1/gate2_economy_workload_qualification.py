from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .gate2_economy_model_policy import (
    ECONOMY_WORKLOAD_CLASSES,
    Gate2EconomyModelPolicyFactory,
)


FACTORY_REQUIRED = (
    "Gate2EconomyWorkloadQualificationFactory.create is the only "
    "code-owned workload qualification evidence registry entrypoint"
)
FORBIDDEN = (
    "Synthetic qualification evidence must not activate a production "
    "model, expand the runtime allowlist or erase a failed workload"
)
QUALIFICATION_REGISTRY_SCHEMA_VERSION = (
    "broker_reports_gate2_economy_workload_qualification_v1"
)
QUALIFICATION_EVIDENCE_REF = (
    "docs/reports/2026-07-24/"
    "BROKER_REPORTS_ECONOMY_REQUALIFICATION_V2.report.md"
)

STATUS_SYNTHETIC_QUALIFIED = "synthetic_qualified"
STATUS_NOT_QUALIFIED = "not_qualified"
STATUS_PROVIDER_ROUTE_UNAVAILABLE = "provider_route_unavailable"
STATUS_PENDING_STAGE_DELIVERY = "pending_stage_delivery"
QUALIFICATION_STATUSES = (
    STATUS_SYNTHETIC_QUALIFIED,
    STATUS_NOT_QUALIFIED,
    STATUS_PROVIDER_ROUTE_UNAVAILABLE,
    STATUS_PENDING_STAGE_DELIVERY,
)

CONTRACT_GATE2_SOURCE = "broker_reports_source_facts_v0"
CONTRACT_GATE2_DOMAIN = (
    "broker_reports_candidate_binding_output_v0+"
    "broker_reports_domain_source_facts_v0"
)
CONTRACT_GATE2_FINANCIAL_EVIDENCE = (
    "broker_reports_gate2_financial_evidence_decision_v1"
)
CONTRACT_GATE2_FINANCIAL_CHECKSUM = (
    "broker_reports_gate2_financial_context_checksum_v1"
)


class Gate2EconomyWorkloadQualificationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class EconomyWorkloadQualificationEvidence:
    exact_model_id: str
    provider_profile_id: str
    workload_class: str
    contract_version: str
    status: str
    terminal_code: str
    provider_calls_total: int
    fallback_calls_total: int = 0
    repair_attempts_total: int = 0
    customer_calls_total: int = 0
    evidence_ref: str = QUALIFICATION_EVIDENCE_REF

    def to_dict(self) -> dict[str, object]:
        return {
            "exact_model_id": self.exact_model_id,
            "provider_profile_id": self.provider_profile_id,
            "workload_class": self.workload_class,
            "contract_version": self.contract_version,
            "status": self.status,
            "terminal_code": self.terminal_code,
            "provider_calls_total": self.provider_calls_total,
            "fallback_calls_total": self.fallback_calls_total,
            "repair_attempts_total": self.repair_attempts_total,
            "customer_calls_total": self.customer_calls_total,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True)
class Gate2EconomyWorkloadQualificationSnapshot:
    schema_version: str
    policy_version: str
    policy_hash: str
    entries: tuple[EconomyWorkloadQualificationEvidence, ...]
    registry_hash: str

    def status(
        self,
        *,
        exact_model_id: str,
        provider_profile_id: str,
        workload_class: str,
        contract_version: str,
    ) -> EconomyWorkloadQualificationEvidence:
        matches = [
            item
            for item in self.entries
            if item.exact_model_id == exact_model_id
            and item.provider_profile_id == provider_profile_id
            and item.workload_class == workload_class
            and item.contract_version == contract_version
        ]
        if len(matches) != 1:
            raise Gate2EconomyWorkloadQualificationError(
                "economy_workload_qualification_subject_unknown"
            )
        return matches[0]

    def synthetic_allowlist(
        self,
        workload_class: str,
    ) -> tuple[str, ...]:
        if workload_class not in ECONOMY_WORKLOAD_CLASSES:
            raise Gate2EconomyWorkloadQualificationError(
                "economy_workload_qualification_workload_unknown"
            )
        return tuple(
            item.exact_model_id
            for item in self.entries
            if item.workload_class == workload_class
            and item.status == STATUS_SYNTHETIC_QUALIFIED
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
            "entries": [item.to_dict() for item in self.entries],
            "registry_hash": self.registry_hash,
        }


class Gate2EconomyWorkloadQualificationFactory:
    def create(self) -> Gate2EconomyWorkloadQualificationSnapshot:
        policy = Gate2EconomyModelPolicyFactory().create()
        entries = tuple(
            sorted(
                WORKLOAD_QUALIFICATION_EVIDENCE,
                key=lambda item: (
                    item.exact_model_id,
                    item.provider_profile_id,
                    item.workload_class,
                    item.contract_version,
                ),
            )
        )
        self._validate(entries)
        material = {
            "schema_version": QUALIFICATION_REGISTRY_SCHEMA_VERSION,
            "policy_version": policy.policy_version,
            "policy_hash": policy.policy_hash,
            "entries": [item.to_dict() for item in entries],
        }
        registry_hash = hashlib.sha256(
            json.dumps(
                material,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return Gate2EconomyWorkloadQualificationSnapshot(
            schema_version=QUALIFICATION_REGISTRY_SCHEMA_VERSION,
            policy_version=policy.policy_version,
            policy_hash=policy.policy_hash,
            entries=entries,
            registry_hash=registry_hash,
        )

    @staticmethod
    def _validate(
        entries: tuple[EconomyWorkloadQualificationEvidence, ...],
    ) -> None:
        policy = Gate2EconomyModelPolicyFactory().create()
        identities = [
            (
                item.exact_model_id,
                item.provider_profile_id,
                item.workload_class,
                item.contract_version,
            )
            for item in entries
        ]
        if len(identities) != len(set(identities)):
            raise Gate2EconomyWorkloadQualificationError(
                "economy_workload_qualification_subject_duplicate"
            )
        for item in entries:
            try:
                declaration = policy.model(item.exact_model_id)
                policy.workload(item.workload_class)
            except ValueError as exc:
                raise Gate2EconomyWorkloadQualificationError(
                    "economy_workload_qualification_policy_mismatch"
                ) from exc
            if (
                declaration.provider_profile_id
                != item.provider_profile_id
                or item.workload_class
                not in declaration.workload_classes
                or item.status not in QUALIFICATION_STATUSES
                or not item.contract_version
                or not item.terminal_code
                or item.provider_calls_total < 0
                or item.fallback_calls_total != 0
                or item.repair_attempts_total != 0
                or item.customer_calls_total != 0
                or item.evidence_ref != QUALIFICATION_EVIDENCE_REF
            ):
                raise Gate2EconomyWorkloadQualificationError(
                    "economy_workload_qualification_evidence_invalid"
                )


def _entry(
    *,
    exact_model_id: str,
    provider_profile_id: str,
    workload_class: str,
    contract_version: str,
    status: str,
    terminal_code: str,
    provider_calls_total: int,
) -> EconomyWorkloadQualificationEvidence:
    return EconomyWorkloadQualificationEvidence(
        exact_model_id=exact_model_id,
        provider_profile_id=provider_profile_id,
        workload_class=workload_class,
        contract_version=contract_version,
        status=status,
        terminal_code=terminal_code,
        provider_calls_total=provider_calls_total,
    )


WORKLOAD_QUALIFICATION_EVIDENCE = (
    _entry(
        exact_model_id="gpt-5.4-nano-2026-03-17",
        provider_profile_id="openai_gpt",
        workload_class="gate2_source",
        contract_version=CONTRACT_GATE2_SOURCE,
        status=STATUS_PENDING_STAGE_DELIVERY,
        terminal_code="reasoning_policy_fix_not_released_to_stage",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="gpt-5.4-nano-2026-03-17",
        provider_profile_id="openai_gpt",
        workload_class="gate2_domain",
        contract_version=CONTRACT_GATE2_DOMAIN,
        status=STATUS_PENDING_STAGE_DELIVERY,
        terminal_code="reasoning_policy_fix_not_released_to_stage",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="gpt-5.4-nano-2026-03-17",
        provider_profile_id="openai_gpt",
        workload_class="gate2_financial_evidence",
        contract_version=CONTRACT_GATE2_FINANCIAL_EVIDENCE,
        status=STATUS_SYNTHETIC_QUALIFIED,
        terminal_code="four_dispositions_4_of_4",
        provider_calls_total=4,
    ),
    _entry(
        exact_model_id="gpt-5.4-nano-2026-03-17",
        provider_profile_id="openai_gpt",
        workload_class="gate2_financial_checksum",
        contract_version=CONTRACT_GATE2_FINANCIAL_CHECKSUM,
        status=STATUS_NOT_QUALIFIED,
        terminal_code="financial_context_checksum_dimension_mismatch",
        provider_calls_total=1,
    ),
    _entry(
        exact_model_id="models/gemini-2.5-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_source",
        contract_version=CONTRACT_GATE2_SOURCE,
        status=STATUS_PENDING_STAGE_DELIVERY,
        terminal_code="candidate_not_registered_in_stage_policy",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="models/gemini-2.5-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_domain",
        contract_version=CONTRACT_GATE2_DOMAIN,
        status=STATUS_PENDING_STAGE_DELIVERY,
        terminal_code="candidate_not_registered_in_stage_policy",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="models/gemini-2.5-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_financial_evidence",
        contract_version=CONTRACT_GATE2_FINANCIAL_EVIDENCE,
        status=STATUS_PROVIDER_ROUTE_UNAVAILABLE,
        terminal_code="gate2_model_unavailable_http_404",
        provider_calls_total=4,
    ),
    _entry(
        exact_model_id="models/gemini-2.5-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_financial_checksum",
        contract_version=CONTRACT_GATE2_FINANCIAL_CHECKSUM,
        status=STATUS_PROVIDER_ROUTE_UNAVAILABLE,
        terminal_code="gate2_model_unavailable_http_404",
        provider_calls_total=1,
    ),
    _entry(
        exact_model_id="claude-haiku-4-5-20251001",
        provider_profile_id="anthropic_claude",
        workload_class="gate2_source",
        contract_version=CONTRACT_GATE2_SOURCE,
        status=STATUS_SYNTHETIC_QUALIFIED,
        terminal_code="income_source_contract_passed",
        provider_calls_total=1,
    ),
    _entry(
        exact_model_id="claude-haiku-4-5-20251001",
        provider_profile_id="anthropic_claude",
        workload_class="gate2_domain",
        contract_version=CONTRACT_GATE2_DOMAIN,
        status=STATUS_SYNTHETIC_QUALIFIED,
        terminal_code="income_domain_candidate_binding_passed",
        provider_calls_total=1,
    ),
    _entry(
        exact_model_id="claude-haiku-4-5-20251001",
        provider_profile_id="anthropic_claude",
        workload_class="gate2_financial_evidence",
        contract_version=CONTRACT_GATE2_FINANCIAL_EVIDENCE,
        status=STATUS_NOT_QUALIFIED,
        terminal_code=(
            "typed_schema_rejected_and_unsupported_disposition_mismatch"
        ),
        provider_calls_total=4,
    ),
    _entry(
        exact_model_id="claude-haiku-4-5-20251001",
        provider_profile_id="anthropic_claude",
        workload_class="gate2_financial_checksum",
        contract_version=CONTRACT_GATE2_FINANCIAL_CHECKSUM,
        status=STATUS_SYNTHETIC_QUALIFIED,
        terminal_code="financial_context_checksum_3_of_3",
        provider_calls_total=1,
    ),
)
