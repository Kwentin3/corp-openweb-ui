from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .gate2_economy_model_policy import (
    ECONOMY_WORKLOAD_CLASSES,
    Gate2EconomyModelPolicyFactory,
)
from .gate2_economy_workload_policy import (
    Gate2EconomyWorkloadPolicyFactory,
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
    "broker_reports_gate2_economy_workload_qualification_v2"
)
QUALIFICATION_EVIDENCE_REF = (
    "docs/reports/2026-07-25/"
    "BROKER_REPORTS_ECONOMY_V3_GOAL1_WORKLOAD_POLICY.report.md"
)

STATUS_SYNTHETIC_QUALIFIED = "synthetic_qualified"
STATUS_NOT_QUALIFIED = "not_qualified"
STATUS_PROVIDER_ROUTE_UNAVAILABLE = "provider_route_unavailable"
STATUS_PENDING_STAGE_DELIVERY = "pending_stage_delivery"
STATUS_NOT_IN_TARGET_MATRIX = "not_in_target_matrix"
STATUS_DIAGNOSTIC_NOT_SCHEDULED = "diagnostic_not_scheduled"
QUALIFICATION_STATUSES = (
    STATUS_SYNTHETIC_QUALIFIED,
    STATUS_NOT_QUALIFIED,
    STATUS_PROVIDER_ROUTE_UNAVAILABLE,
    STATUS_PENDING_STAGE_DELIVERY,
    STATUS_NOT_IN_TARGET_MATRIX,
    STATUS_DIAGNOSTIC_NOT_SCHEDULED,
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
    provider_route_revision: str
    workload_class: str
    contract_version: str
    input_contract_version: str
    output_contract_version: str
    prompt_version: str
    adapter_projection_revision: str
    canonical_validator_revision: str
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
            "provider_route_revision": self.provider_route_revision,
            "workload_class": self.workload_class,
            "contract_version": self.contract_version,
            "input_contract_version": self.input_contract_version,
            "output_contract_version": self.output_contract_version,
            "prompt_version": self.prompt_version,
            "adapter_projection_revision": (
                self.adapter_projection_revision
            ),
            "canonical_validator_revision": (
                self.canonical_validator_revision
            ),
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
    workload_policy_version: str
    workload_policy_hash: str
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
            "workload_policy_version": self.workload_policy_version,
            "workload_policy_hash": self.workload_policy_hash,
            "entries": [item.to_dict() for item in self.entries],
            "registry_hash": self.registry_hash,
        }


class Gate2EconomyWorkloadQualificationFactory:
    def create(self) -> Gate2EconomyWorkloadQualificationSnapshot:
        policy = Gate2EconomyModelPolicyFactory().create()
        workload_policy = Gate2EconomyWorkloadPolicyFactory(
            model_policy=policy
        ).create()
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
            "workload_policy_version": workload_policy.policy_version,
            "workload_policy_hash": workload_policy.policy_hash,
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
            workload_policy_version=workload_policy.policy_version,
            workload_policy_hash=workload_policy.policy_hash,
            entries=entries,
            registry_hash=registry_hash,
        )

    @staticmethod
    def _validate(
        entries: tuple[EconomyWorkloadQualificationEvidence, ...],
    ) -> None:
        policy = Gate2EconomyModelPolicyFactory().create()
        workload_policy = Gate2EconomyWorkloadPolicyFactory(
            model_policy=policy
        ).create()
        identities = [
            (
                item.exact_model_id,
                item.provider_profile_id,
                item.provider_route_revision,
                item.workload_class,
                item.contract_version,
                item.input_contract_version,
                item.output_contract_version,
                item.prompt_version,
                item.adapter_projection_revision,
                item.canonical_validator_revision,
            )
            for item in entries
        ]
        if len(identities) != len(set(identities)):
            raise Gate2EconomyWorkloadQualificationError(
                "economy_workload_qualification_subject_duplicate"
            )
        expected_subjects = {
            (
                declaration.exact_model_id,
                declaration.provider_profile_id,
                workload.workload_class,
            )
            for declaration in policy.models
            for workload in policy.workloads
        }
        actual_subjects = {
            (
                item.exact_model_id,
                item.provider_profile_id,
                item.workload_class,
            )
            for item in entries
        }
        if actual_subjects != expected_subjects:
            raise Gate2EconomyWorkloadQualificationError(
                "economy_workload_qualification_subject_set_incomplete"
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
                or not item.provider_route_revision
                or not item.input_contract_version
                or not item.output_contract_version
                or not item.prompt_version
                or not item.adapter_projection_revision
                or not item.canonical_validator_revision
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
            qualification_candidates = set(
                workload_policy.qualification_candidate_ids(
                    item.workload_class
                )
            )
            if (
                item.status == STATUS_NOT_IN_TARGET_MATRIX
                and item.exact_model_id in qualification_candidates
            ):
                raise Gate2EconomyWorkloadQualificationError(
                    "economy_workload_qualification_target_status_invalid"
                )
            if (
                item.status == STATUS_DIAGNOSTIC_NOT_SCHEDULED
                and item.exact_model_id
                not in set(
                    workload_policy.route(
                        item.workload_class
                    ).diagnostic_candidate_exact_model_ids
                )
            ):
                raise Gate2EconomyWorkloadQualificationError(
                    "economy_workload_qualification_diagnostic_status_invalid"
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
    identity = _contract_identity(
        workload_class=workload_class,
        provider_profile_id=provider_profile_id,
        status=status,
    )
    return EconomyWorkloadQualificationEvidence(
        exact_model_id=exact_model_id,
        provider_profile_id=provider_profile_id,
        provider_route_revision=identity["provider_route_revision"],
        workload_class=workload_class,
        contract_version=contract_version,
        input_contract_version=identity["input_contract_version"],
        output_contract_version=identity["output_contract_version"],
        prompt_version=identity["prompt_version"],
        adapter_projection_revision=identity[
            "adapter_projection_revision"
        ],
        canonical_validator_revision=identity[
            "canonical_validator_revision"
        ],
        status=status,
        terminal_code=terminal_code,
        provider_calls_total=provider_calls_total,
    )


def _contract_identity(
    *,
    workload_class: str,
    provider_profile_id: str,
    status: str,
) -> dict[str, str]:
    contracts = {
        "gate2_source": (
            "broker_reports_gate2_source_fact_package_v0",
            CONTRACT_GATE2_SOURCE,
            "broker_reports_gate2_source_fact_prompt_v0",
            "source_fact_canonical_validator_v0",
        ),
        "gate2_domain": (
            "broker_reports_domain_extraction_package_v0",
            CONTRACT_GATE2_DOMAIN,
            "broker_reports_gate2_domain_prompt_v0",
            "domain_source_fact_canonical_validator_v0",
        ),
        "gate2_financial_evidence": (
            "broker_reports_gate2_financial_evidence_source_package_v1",
            CONTRACT_GATE2_FINANCIAL_EVIDENCE,
            "gate2_financial_evidence_shadow_prompt_v1",
            (
                "sha256:"
                "747d83552f394f4bd56249820e9630adc97a4d2435da60cbd9b2b376685eb5be"
            ),
        ),
        "gate2_financial_checksum": (
            "broker_reports_gate2_financial_context_v1",
            CONTRACT_GATE2_FINANCIAL_CHECKSUM,
            "gate2_financial_context_checksum_prompt_v1",
            (
                "sha256:"
                "561caa46ca51fc538a849df7eff6e2a97419c1e3fb700c7e90d055a258b0bcb9"
            ),
        ),
    }
    input_contract, output_contract, prompt, validator = contracts[
        workload_class
    ]
    adapters = {
        "openai_gpt": "gate2_openai_response_format_adapter_v1",
        "google_gemini": "gate2_gemini_schema_projection_v1",
        "anthropic_claude": "gate2_anthropic_structural_projection_v1",
    }
    provider_route_revision = (
        "not_applicable"
        if status == STATUS_NOT_IN_TARGET_MATRIX
        else (
            "pending_stage_delivery_policy_1_4"
            if status == STATUS_PENDING_STAGE_DELIVERY
            else (
                "maintained_route_not_exercised_policy_1_4"
                if status == STATUS_DIAGNOSTIC_NOT_SCHEDULED
                else "openwebui_0.9.6_maintained_route_2026-07-24"
            )
        )
    )
    return {
        "provider_route_revision": provider_route_revision,
        "input_contract_version": input_contract,
        "output_contract_version": output_contract,
        "prompt_version": prompt,
        "adapter_projection_revision": adapters[provider_profile_id],
        "canonical_validator_revision": validator,
    }


WORKLOAD_QUALIFICATION_EVIDENCE = (
    _entry(
        exact_model_id="gpt-5.4-nano-2026-03-17",
        provider_profile_id="openai_gpt",
        workload_class="gate2_source",
        contract_version=CONTRACT_GATE2_SOURCE,
        status=STATUS_NOT_IN_TARGET_MATRIX,
        terminal_code="gpt_nano_not_selected_for_source",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="gpt-5.4-nano-2026-03-17",
        provider_profile_id="openai_gpt",
        workload_class="gate2_domain",
        contract_version=CONTRACT_GATE2_DOMAIN,
        status=STATUS_NOT_IN_TARGET_MATRIX,
        terminal_code="gpt_nano_not_selected_for_domain",
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
        exact_model_id="models/gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_source",
        contract_version=CONTRACT_GATE2_SOURCE,
        status=STATUS_PENDING_STAGE_DELIVERY,
        terminal_code="formal_source_replay_required_after_policy_delivery",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="models/gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_domain",
        contract_version=CONTRACT_GATE2_DOMAIN,
        status=STATUS_PENDING_STAGE_DELIVERY,
        terminal_code="formal_domain_replay_required_after_policy_delivery",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="models/gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_financial_evidence",
        contract_version=CONTRACT_GATE2_FINANCIAL_EVIDENCE,
        status=STATUS_NOT_QUALIFIED,
        terminal_code=(
            "financial_evidence_decision_unclassified_shape_invalid"
        ),
        provider_calls_total=1,
    ),
    _entry(
        exact_model_id="models/gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_financial_checksum",
        contract_version=CONTRACT_GATE2_FINANCIAL_CHECKSUM,
        status=STATUS_DIAGNOSTIC_NOT_SCHEDULED,
        terminal_code="gemini_checksum_optional_later_not_active",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="models/gemini-3.5-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_source",
        contract_version=CONTRACT_GATE2_SOURCE,
        status=STATUS_PENDING_STAGE_DELIVERY,
        terminal_code="formal_source_replay_required_after_policy_delivery",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="models/gemini-3.5-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_domain",
        contract_version=CONTRACT_GATE2_DOMAIN,
        status=STATUS_PENDING_STAGE_DELIVERY,
        terminal_code="formal_domain_replay_required_after_policy_delivery",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="models/gemini-3.5-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_financial_evidence",
        contract_version=CONTRACT_GATE2_FINANCIAL_EVIDENCE,
        status=STATUS_PENDING_STAGE_DELIVERY,
        terminal_code="financial_qualification_route_pending_delivery",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="models/gemini-3.5-flash-lite",
        provider_profile_id="google_gemini",
        workload_class="gate2_financial_checksum",
        contract_version=CONTRACT_GATE2_FINANCIAL_CHECKSUM,
        status=STATUS_DIAGNOSTIC_NOT_SCHEDULED,
        terminal_code="gemini_checksum_optional_later_not_active",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="claude-haiku-4-5-20251001",
        provider_profile_id="anthropic_claude",
        workload_class="gate2_source",
        contract_version=CONTRACT_GATE2_SOURCE,
        status=STATUS_NOT_IN_TARGET_MATRIX,
        terminal_code="haiku_not_selected_for_source",
        provider_calls_total=0,
    ),
    _entry(
        exact_model_id="claude-haiku-4-5-20251001",
        provider_profile_id="anthropic_claude",
        workload_class="gate2_domain",
        contract_version=CONTRACT_GATE2_DOMAIN,
        status=STATUS_NOT_IN_TARGET_MATRIX,
        terminal_code="haiku_not_selected_for_domain",
        provider_calls_total=0,
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
