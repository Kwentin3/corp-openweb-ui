from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Protocol

from .gate2_economy_model_policy import (
    WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
    Gate2EconomyModelPolicyFactory,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_semantic_v6_context_linter import (
    Gate2FinancialSemanticV6ContextV21SealedRequest,
)
from .gate2_financial_semantic_v6_qualification import (
    Gate2FinancialSemanticV6QualificationCase,
    Gate2FinancialSemanticV6QualificationFixture,
)
from .gate2_model_contracts import (
    Gate2ProviderProfile,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE,
)
from .gate2_provider_adapters import (
    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    Gate2ContextV21BudgetSmokeTransportContract,
    Gate2PreparedProviderRequest,
)


BUDGET_SMOKE_PLAN_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_1_budget_smoke_plan_v1"
)
BUDGET_SMOKE_PLAN_POLICY_VERSION = (
    "broker_reports_gate2_context_v2_1_three_provider_budget_smoke_v1"
)
BUDGET_SMOKE_MAXIMUM_OUTPUT_TOKENS = 640
BUDGET_SMOKE_MAXIMUM_PROVIDER_SUBMISSIONS = 12
GOAL12_HISTORICAL_GOOGLE_ADAPTER_VERSION = "1.5.0"
GOAL12_HISTORICAL_PLAN_INTEGRITY_HASH = (
    "9191197bdc947d6ba86db3169ba0d8c911ef88423d611e2c4424a9379167cbab"
)
BUDGET_SMOKE_OUTCOME_AUDIT_INTEGRITY_SHA256 = (
    "774acd03c95ddc2d898112b6b62e3bed54613cfeaac7f98689e7c05224d271ae"
)


def goal12_historical_provider_profile(
    profile_id: str,
) -> Gate2ProviderProfile:
    """Resolve the exact provider metadata sealed into closed GOAL 12."""

    profile = gate2_provider_profile(profile_id)
    if profile.profile_id == "google_gemini":
        return replace(
            profile,
            adapter_version=GOAL12_HISTORICAL_GOOGLE_ADAPTER_VERSION,
        )
    return profile


BUDGET_SMOKE_PROVIDER_MODELS = (
    ("openai_gpt", "gpt-5.4-nano-2026-03-17"),
    ("anthropic_claude", "claude-haiku-4-5-20251001"),
    ("google_gemini", "models/gemini-3.1-flash-lite"),
)
BUDGET_SMOKE_PROVIDER_MODEL_IDENTITIES = (
    (
        "openai_gpt",
        "dated_immutable_model_id",
        True,
        None,
    ),
    (
        "anthropic_claude",
        "dated_immutable_model_id",
        True,
        None,
    ),
    (
        "google_gemini",
        "stable_selector_not_immutable",
        False,
        "provider_inventory_has_no_dated_immutable_google_model_id",
    ),
)
BUDGET_SMOKE_CASES = (
    ("syn_successor_v2_unique_cash", "typed_safe_1"),
    ("syn_successor_v2_no_registry_type", "no_type_0"),
    (
        "syn_successor_v2_multiple_compatible",
        "ambiguous_type_2plus",
    ),
    (
        "syn_successor_v2_detail_vs_subtotal",
        "single_type_no_safe_record",
    ),
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory.create is "
    "the only GOAL 12 immutable model, parameter and slot-plan authority"
)
FORBIDDEN = (
    "The GOAL 12 plan must not call a provider, accept model aliases or "
    "runtime model/parameter overrides, retry, repair, fallback, activate "
    "Context V2.1 or admit a production model"
)

_REQUEST_PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REASONING_FIELDS = frozenset(
    {
        "reasoning",
        "reasoning_effort",
        "thinking",
        "thinking_config",
    }
)
_FORBIDDEN_REQUEST_FIELDS = frozenset(
    {
        "fallback",
        "functions",
        "plugins",
        "repair",
        "retry",
        "seed",
        "temperature",
        "tool_choice",
        "tools",
        "top_p",
        "web_search_options",
    }
)
_ZERO_EXECUTION_ACCOUNTING = {
    "planned_slots_total": BUDGET_SMOKE_MAXIMUM_PROVIDER_SUBMISSIONS,
    "maximum_provider_submissions_total": (
        BUDGET_SMOKE_MAXIMUM_PROVIDER_SUBMISSIONS
    ),
    "provider_submissions_total": 0,
    "provider_responses_total": 0,
    "retry_total": 0,
    "repair_total": 0,
    "fallback_total": 0,
}


class Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError(
    ValueError
):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21BudgetSmokeParameters:
    economy_policy_id: str
    economy_policy_version: str
    economy_policy_hash: str
    workload_class: str
    maximum_output_tokens: int
    reasoning_policy: str
    paid_tools_allowed: bool
    transport_policy: str
    model_aliases_allowed: bool = False
    runtime_model_override_allowed: bool = False
    runtime_parameter_override_allowed: bool = False
    retry_allowed: bool = False
    repair_allowed: bool = False
    fallback_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection:
    request_profile: str
    sealed_request: Gate2FinancialSemanticV6ContextV21SealedRequest
    prepared_request: Gate2PreparedProviderRequest
    transport_contract: Gate2ContextV21BudgetSmokeTransportContract


class Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjector(
    Protocol
):
    def __call__(
        self,
        *,
        case: Gate2FinancialSemanticV6QualificationCase,
        provider_profile: Gate2ProviderProfile,
        exact_model_id: str,
        request_profile: str,
        parameters: (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeParameters
        ),
    ) -> (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection
    ):
        ...


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot:
    ordinal: int
    slot_id: str
    provider_profile_id: str
    provider_profile_revision: str
    provider_id: str
    provider_adapter_id: str
    provider_adapter_version: str
    exact_model_id: str
    model_identity_kind: str
    immutable_model_id_proven: bool
    model_identity_caveat: str | None
    case_id: str
    taxonomy_state: str
    request_profile: str
    transport_policy: str
    parameters: (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeParameters
    )
    sealed_request_hash: str
    sealed_request_receipt_integrity_hash: str
    model_visible_request_hash: str
    canonical_schema_hash: str
    prepared_request_hash: str
    provider_visible_schema_hash: str
    transport_contract: dict[str, Any]
    transport_contract_hash: str
    expected_answer_hash: str
    maximum_provider_submissions: int
    retry_total: int
    repair_total: int
    fallback_total: int
    integrity_hash: str

    def integrity_payload(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "slot_id": self.slot_id,
            "provider_profile_id": self.provider_profile_id,
            "provider_profile_revision": (
                self.provider_profile_revision
            ),
            "provider_id": self.provider_id,
            "provider_adapter_id": self.provider_adapter_id,
            "provider_adapter_version": self.provider_adapter_version,
            "exact_model_id": self.exact_model_id,
            "model_identity_kind": self.model_identity_kind,
            "immutable_model_id_proven": (
                self.immutable_model_id_proven
            ),
            "model_identity_caveat": self.model_identity_caveat,
            "case_id": self.case_id,
            "taxonomy_state": self.taxonomy_state,
            "request_profile": self.request_profile,
            "transport_policy": self.transport_policy,
            "parameters": self.parameters.to_dict(),
            "sealed_request_hash": self.sealed_request_hash,
            "sealed_request_receipt_integrity_hash": (
                self.sealed_request_receipt_integrity_hash
            ),
            "model_visible_request_hash": (
                self.model_visible_request_hash
            ),
            "canonical_schema_hash": self.canonical_schema_hash,
            "prepared_request_hash": self.prepared_request_hash,
            "provider_visible_schema_hash": (
                self.provider_visible_schema_hash
            ),
            "transport_contract": copy.deepcopy(
                self.transport_contract
            ),
            "transport_contract_hash": self.transport_contract_hash,
            "expected_answer_hash": self.expected_answer_hash,
            "maximum_provider_submissions": (
                self.maximum_provider_submissions
            ),
            "retry_total": self.retry_total,
            "repair_total": self.repair_total,
            "fallback_total": self.fallback_total,
        }

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            **self.integrity_payload(),
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21BudgetSmokePlan:
    schema_version: str
    policy_version: str
    status: str
    frozen: bool
    active: bool
    transport_executed: bool
    request_profile: str
    transport_policy: str
    outcome_audit_integrity_sha256: str
    fixture_benchmark_hash: str
    local_proof_receipt_hash: str
    economy_policy_id: str
    economy_policy_version: str
    economy_policy_hash: str
    slots: tuple[
        Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot, ...
    ]
    execution_accounting: dict[str, int]
    production_admissions: tuple[str, ...]
    integrity_hash: str

    def integrity_payload(self) -> dict[str, Any]:
        provider_ledger: list[dict[str, Any]] = []
        for profile_id, _model_id in BUDGET_SMOKE_PROVIDER_MODELS:
            slot = next(
                item
                for item in self.slots
                if item.provider_profile_id == profile_id
            )
            provider_ledger.append(
                {
                    "provider_profile_id": slot.provider_profile_id,
                    "provider_profile_revision": (
                        slot.provider_profile_revision
                    ),
                    "provider_id": slot.provider_id,
                    "provider_adapter_id": slot.provider_adapter_id,
                    "provider_adapter_version": (
                        slot.provider_adapter_version
                    ),
                    "exact_model_id": slot.exact_model_id,
                    "model_identity_kind": slot.model_identity_kind,
                    "immutable_model_id_proven": (
                        slot.immutable_model_id_proven
                    ),
                    "model_identity_caveat": (
                        slot.model_identity_caveat
                    ),
                    "transport_contract": copy.deepcopy(
                        slot.transport_contract
                    ),
                    "transport_contract_hash": (
                        slot.transport_contract_hash
                    ),
                    "parameters": slot.parameters.to_dict(),
                }
            )
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "status": self.status,
            "frozen": self.frozen,
            "active": self.active,
            "transport_executed": self.transport_executed,
            "request_profile": self.request_profile,
            "transport_policy": self.transport_policy,
            "outcome_audit_integrity_sha256": (
                self.outcome_audit_integrity_sha256
            ),
            "fixture_benchmark_hash": self.fixture_benchmark_hash,
            "local_proof_receipt_hash": (
                self.local_proof_receipt_hash
            ),
            "economy_policy_id": self.economy_policy_id,
            "economy_policy_version": self.economy_policy_version,
            "economy_policy_hash": self.economy_policy_hash,
            "provider_model_parameter_ledger": provider_ledger,
            "provider_order": [
                item[0] for item in BUDGET_SMOKE_PROVIDER_MODELS
            ],
            "case_order": [item[0] for item in BUDGET_SMOKE_CASES],
            "slots": [item.to_safe_dict() for item in self.slots],
            "execution_accounting": copy.deepcopy(
                self.execution_accounting
            ),
            "production_admissions": list(self.production_admissions),
        }

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            **self.integrity_payload(),
            "integrity_hash": self.integrity_hash,
        }


class Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory:
    def __init__(
        self,
        *,
        request_profile: str,
        slot_projector: (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjector
        ),
        provider_profile_resolver: Callable[
            [str], Gate2ProviderProfile
        ] = gate2_provider_profile,
    ) -> None:
        if (
            not isinstance(request_profile, str)
            or request_profile
            != (
                FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
            )
            or _REQUEST_PROFILE_RE.fullmatch(request_profile) is None
            or not callable(slot_projector)
            or not callable(provider_profile_resolver)
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_plan_factory_invalid"
            )
        self.request_profile = request_profile
        self.slot_projector = slot_projector
        self.provider_profile_resolver = provider_profile_resolver

    def create(
        self,
        *,
        fixture: Gate2FinancialSemanticV6QualificationFixture,
        outcome_audit_manifest: dict[str, Any],
    ) -> Gate2FinancialSemanticV6ContextV21BudgetSmokePlan:
        audit_cases = _validated_plan_inputs(
            fixture=fixture,
            outcome_audit_manifest=outcome_audit_manifest,
        )
        economy_policy = Gate2EconomyModelPolicyFactory().create()
        workload = economy_policy.workload(
            WORKLOAD_GATE2_FINANCIAL_EVIDENCE
        )
        if (
            workload.maximum_output_tokens
            != BUDGET_SMOKE_MAXIMUM_OUTPUT_TOKENS
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_parameter_policy_drift"
            )
        semantic_cases = {
            item.case_id: item for item in fixture.semantic_cases
        }
        slots: list[
            Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot
        ] = []
        ordinal = 0
        for provider_profile_id, exact_model_id in (
            BUDGET_SMOKE_PROVIDER_MODELS
        ):
            profile = self.provider_profile_resolver(provider_profile_id)
            identity = {
                item[0]: item[1:]
                for item in BUDGET_SMOKE_PROVIDER_MODEL_IDENTITIES
            }.get(provider_profile_id)
            resolution = economy_policy.resolve_model_id(exact_model_id)
            declaration = economy_policy.model(exact_model_id)
            if (
                identity is None
                or resolution.alias_used
                or resolution.exact_model_id != exact_model_id
                or resolution.provider_profile_id
                != provider_profile_id
                or declaration.exact_model_id != exact_model_id
                or declaration.provider_profile_id
                != provider_profile_id
                or declaration.provider_id != profile.provider_id
                or WORKLOAD_GATE2_FINANCIAL_EVIDENCE
                not in declaration.workload_classes
                or declaration.paid_tools_allowed
            ):
                _fail(
                    "financial_semantic_v6_context_v2_1_"
                    "budget_smoke_model_ledger_invalid"
                )
            parameters = (
                Gate2FinancialSemanticV6ContextV21BudgetSmokeParameters(
                    economy_policy_id=economy_policy.policy_id,
                    economy_policy_version=economy_policy.policy_version,
                    economy_policy_hash=economy_policy.policy_hash,
                    workload_class=WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
                    maximum_output_tokens=(
                        BUDGET_SMOKE_MAXIMUM_OUTPUT_TOKENS
                    ),
                    reasoning_policy=declaration.reasoning_policy,
                    paid_tools_allowed=False,
                    transport_policy=(
                        CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
                    ),
                )
            )
            for case_id, taxonomy_state in BUDGET_SMOKE_CASES:
                ordinal += 1
                case = semantic_cases.get(case_id)
                audited_case = audit_cases.get(case_id)
                if (
                    case is None
                    or audited_case is None
                    or case.route != "semantic_model"
                    or audited_case.get("expected_route")
                    != "semantic_model"
                    or audited_case.get("taxonomy_state")
                    != taxonomy_state
                ):
                    _fail(
                        "financial_semantic_v6_context_v2_1_"
                        "budget_smoke_case_ledger_invalid"
                    )
                expected_answer = _expected_answer(
                    case=case,
                    audited_case=audited_case,
                )
                projection = self.slot_projector(
                    case=case,
                    provider_profile=profile,
                    exact_model_id=exact_model_id,
                    request_profile=self.request_profile,
                    parameters=parameters,
                )
                projection_hashes = _validated_projection_hashes(
                    projection=projection,
                    case=case,
                    provider_profile=profile,
                    exact_model_id=exact_model_id,
                    request_profile=self.request_profile,
                    parameters=parameters,
                    provider_profile_resolver=(
                        self.provider_profile_resolver
                    ),
                )
                draft = (
                    Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot(
                        ordinal=ordinal,
                        slot_id=f"{provider_profile_id}:{case_id}",
                        provider_profile_id=provider_profile_id,
                        provider_profile_revision=(
                            gate2_provider_profile_revision(profile)
                        ),
                        provider_id=profile.provider_id,
                        provider_adapter_id=profile.adapter_id,
                        provider_adapter_version=profile.adapter_version,
                        exact_model_id=exact_model_id,
                        model_identity_kind=identity[0],
                        immutable_model_id_proven=identity[1],
                        model_identity_caveat=identity[2],
                        case_id=case_id,
                        taxonomy_state=taxonomy_state,
                        request_profile=self.request_profile,
                        transport_policy=(
                            CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
                        ),
                        parameters=parameters,
                        expected_answer_hash=sha256_json(
                            _closed_json_copy(expected_answer)
                        ),
                        maximum_provider_submissions=1,
                        retry_total=0,
                        repair_total=0,
                        fallback_total=0,
                        integrity_hash="",
                        **projection_hashes,
                    )
                )
                slots.append(
                    replace(
                        draft,
                        integrity_hash=sha256_json(
                            draft.integrity_payload()
                        ),
                    )
                )
        local_proof = _closed_json_copy(fixture.local_proof_receipt)
        draft_plan = (
            Gate2FinancialSemanticV6ContextV21BudgetSmokePlan(
                schema_version=BUDGET_SMOKE_PLAN_SCHEMA_VERSION,
                policy_version=BUDGET_SMOKE_PLAN_POLICY_VERSION,
                status="frozen_preflight_not_executed",
                frozen=True,
                active=False,
                transport_executed=False,
                request_profile=self.request_profile,
                transport_policy=(
                    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
                ),
                outcome_audit_integrity_sha256=(
                    BUDGET_SMOKE_OUTCOME_AUDIT_INTEGRITY_SHA256
                ),
                fixture_benchmark_hash=fixture.benchmark_hash,
                local_proof_receipt_hash=sha256_json(local_proof),
                economy_policy_id=economy_policy.policy_id,
                economy_policy_version=economy_policy.policy_version,
                economy_policy_hash=economy_policy.policy_hash,
                slots=tuple(slots),
                execution_accounting=copy.deepcopy(
                    _ZERO_EXECUTION_ACCOUNTING
                ),
                production_admissions=(),
                integrity_hash="",
            )
        )
        plan = replace(
            draft_plan,
            integrity_hash=sha256_json(
                draft_plan.integrity_payload()
            ),
        )
        validate_financial_semantic_v6_context_v2_1_budget_smoke_plan(
            plan,
            provider_profile_resolver=self.provider_profile_resolver,
        )
        return plan


def validate_financial_semantic_v6_context_v2_1_budget_smoke_plan(
    plan: Any,
    *,
    provider_profile_resolver: Callable[
        [str], Gate2ProviderProfile
    ] = gate2_provider_profile,
) -> None:
    if (
        provider_profile_resolver is gate2_provider_profile
        and getattr(plan, "integrity_hash", None)
        == GOAL12_HISTORICAL_PLAN_INTEGRITY_HASH
    ):
        provider_profile_resolver = goal12_historical_provider_profile
    if (
        type(plan)
        is not Gate2FinancialSemanticV6ContextV21BudgetSmokePlan
        or plan.schema_version != BUDGET_SMOKE_PLAN_SCHEMA_VERSION
        or plan.policy_version != BUDGET_SMOKE_PLAN_POLICY_VERSION
        or plan.status != "frozen_preflight_not_executed"
        or plan.frozen is not True
        or plan.active is not False
        or plan.transport_executed is not False
        or plan.request_profile
        != (
            FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
        )
        or plan.transport_policy
        != CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
        or plan.outcome_audit_integrity_sha256
        != BUDGET_SMOKE_OUTCOME_AUDIT_INTEGRITY_SHA256
        or plan.execution_accounting != _ZERO_EXECUTION_ACCOUNTING
        or plan.production_admissions != ()
        or len(plan.slots)
        != BUDGET_SMOKE_MAXIMUM_PROVIDER_SUBMISSIONS
        or tuple(item.ordinal for item in plan.slots)
        != tuple(
            range(1, BUDGET_SMOKE_MAXIMUM_PROVIDER_SUBMISSIONS + 1)
        )
        or len({item.slot_id for item in plan.slots})
        != BUDGET_SMOKE_MAXIMUM_PROVIDER_SUBMISSIONS
        or plan.integrity_hash != sha256_json(plan.integrity_payload())
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_plan_integrity_invalid"
        )
    observed_pairs = tuple(
        (item.provider_profile_id, item.case_id) for item in plan.slots
    )
    expected_pairs = tuple(
        (provider_profile_id, case_id)
        for provider_profile_id, _model_id in BUDGET_SMOKE_PROVIDER_MODELS
        for case_id, _taxonomy in BUDGET_SMOKE_CASES
    )
    if observed_pairs != expected_pairs:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_plan_order_invalid"
        )
    expected_models = dict(BUDGET_SMOKE_PROVIDER_MODELS)
    expected_identities = {
        item[0]: item[1:]
        for item in BUDGET_SMOKE_PROVIDER_MODEL_IDENTITIES
    }
    expected_taxonomy = dict(BUDGET_SMOKE_CASES)
    for slot in plan.slots:
        provider_profile = provider_profile_resolver(
            slot.provider_profile_id
        )
        expected_identity = expected_identities.get(
            slot.provider_profile_id
        )
        if (
            type(slot)
            is not Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot
            or slot.exact_model_id
            != expected_models.get(slot.provider_profile_id)
            or expected_identity is None
            or (
                slot.model_identity_kind,
                slot.immutable_model_id_proven,
                slot.model_identity_caveat,
            )
            != expected_identity
            or slot.provider_profile_revision
            != gate2_provider_profile_revision(provider_profile)
            or slot.provider_id != provider_profile.provider_id
            or slot.provider_adapter_id != provider_profile.adapter_id
            or slot.provider_adapter_version
            != provider_profile.adapter_version
            or slot.taxonomy_state
            != expected_taxonomy.get(slot.case_id)
            or slot.request_profile != plan.request_profile
            or slot.transport_policy != plan.transport_policy
            or slot.parameters.transport_policy != plan.transport_policy
            or slot.parameters.economy_policy_hash
            != plan.economy_policy_hash
            or slot.parameters.maximum_output_tokens
            != BUDGET_SMOKE_MAXIMUM_OUTPUT_TOKENS
            or any(
                (
                    slot.parameters.model_aliases_allowed,
                    slot.parameters.runtime_model_override_allowed,
                    slot.parameters.runtime_parameter_override_allowed,
                    slot.parameters.retry_allowed,
                    slot.parameters.repair_allowed,
                    slot.parameters.fallback_allowed,
                )
            )
            or slot.maximum_provider_submissions != 1
            or slot.retry_total != 0
            or slot.repair_total != 0
            or slot.fallback_total != 0
            or slot.integrity_hash
            != sha256_json(slot.integrity_payload())
            or any(
                _SHA256_RE.fullmatch(value) is None
                for value in (
                    slot.provider_profile_revision,
                    slot.sealed_request_hash,
                    slot.sealed_request_receipt_integrity_hash,
                    slot.model_visible_request_hash,
                    slot.canonical_schema_hash,
                    slot.prepared_request_hash,
                    slot.provider_visible_schema_hash,
                    slot.transport_contract_hash,
                    slot.expected_answer_hash,
                )
            )
            or not isinstance(slot.transport_contract, dict)
            or slot.transport_contract.get("transport_policy")
            != plan.transport_policy
            or slot.transport_contract_hash
            != sha256_json(slot.transport_contract)
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_plan_slot_integrity_invalid"
            )


def financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
    *,
    plan: Any,
    slot: Any,
    provider_profile_resolver: Callable[
        [str], Gate2ProviderProfile
    ] = gate2_provider_profile,
) -> str:
    validate_financial_semantic_v6_context_v2_1_budget_smoke_plan(
        plan,
        provider_profile_resolver=provider_profile_resolver,
    )
    if (
        type(slot)
        is not Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot
        or slot not in plan.slots
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_operation_slot_invalid"
        )
    return f"{plan.integrity_hash}:{slot.integrity_hash}"


def resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer(
    *,
    plan: Any,
    slot: Any,
    fixture: Any,
    outcome_audit_manifest: Any,
    provider_profile_resolver: Callable[
        [str], Gate2ProviderProfile
    ] = gate2_provider_profile,
) -> dict[str, Any]:
    validate_financial_semantic_v6_context_v2_1_budget_smoke_plan(
        plan,
        provider_profile_resolver=provider_profile_resolver,
    )
    if (
        type(slot)
        is not Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot
        or slot not in plan.slots
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_expected_answer_slot_invalid"
        )
    audit_cases = _validated_plan_inputs(
        fixture=fixture,
        outcome_audit_manifest=outcome_audit_manifest,
    )
    semantic_cases = {
        item.case_id: item for item in fixture.semantic_cases
    }
    case = semantic_cases.get(slot.case_id)
    audited_case = audit_cases.get(slot.case_id)
    if (
        case is None
        or audited_case is None
        or audited_case.get("taxonomy_state") != slot.taxonomy_state
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_expected_answer_slot_invalid"
        )
    expected_answer = _expected_answer(
        case=case,
        audited_case=audited_case,
    )
    if sha256_json(expected_answer) != slot.expected_answer_hash:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_expected_answer_hash_invalid"
        )
    return _closed_json_copy(expected_answer)


def _validated_plan_inputs(
    *,
    fixture: Any,
    outcome_audit_manifest: Any,
) -> dict[str, dict[str, Any]]:
    if (
        type(fixture)
        is not Gate2FinancialSemanticV6QualificationFixture
        or not isinstance(fixture.benchmark_hash, str)
        or _SHA256_RE.fullmatch(fixture.benchmark_hash) is None
        or not isinstance(fixture.local_proof_receipt, dict)
        or not isinstance(outcome_audit_manifest, dict)
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_plan_input_invalid"
        )
    try:
        local_proof = _closed_json_copy(
            fixture.local_proof_receipt
        )
        frozen_audit = _closed_json_copy(outcome_audit_manifest)
    except (TypeError, ValueError) as exc:
        raise Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_outcome_audit_invalid"
        ) from exc
    local_proof_material = copy.deepcopy(local_proof)
    local_proof_integrity = local_proof_material.pop(
        "integrity_sha256",
        None,
    )
    if (
        local_proof.get("status") != "passed"
        or local_proof.get("execution_accounting", {}).get(
            "provider_calls_total"
        )
        != 0
        or not isinstance(local_proof_integrity, str)
        or _SHA256_RE.fullmatch(local_proof_integrity) is None
        or sha256_json(local_proof_material)
        != local_proof_integrity
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_plan_input_invalid"
        )
    integrity_material = copy.deepcopy(frozen_audit)
    supplied_integrity = integrity_material.pop(
        "integrity_sha256",
        None,
    )
    if (
        supplied_integrity
        != BUDGET_SMOKE_OUTCOME_AUDIT_INTEGRITY_SHA256
        or sha256_json(integrity_material)
        != BUDGET_SMOKE_OUTCOME_AUDIT_INTEGRITY_SHA256
        or frozen_audit.get("frozen") is not True
        or frozen_audit.get("status")
        != "frozen_corrected_expectations_not_executed"
        or frozen_audit.get("execution_policy", {}).get(
            "provider_calls"
        )
        != 0
        or not isinstance(frozen_audit.get("cases"), list)
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_outcome_audit_invalid"
        )
    audit_cases = {
        item.get("case_id"): item
        for item in frozen_audit["cases"]
        if isinstance(item, dict)
    }
    if set(dict(BUDGET_SMOKE_CASES)) - set(audit_cases):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_outcome_audit_invalid"
        )
    return audit_cases


def _expected_answer(
    *,
    case: Gate2FinancialSemanticV6QualificationCase,
    audited_case: dict[str, Any],
) -> dict[str, Any]:
    if audited_case.get("expected_disposition") == "typed_input":
        compilation = case.compilation
        expected = case.expected_model_choice
        matching_options = tuple(
            item
            for item in getattr(compilation, "typed_options", ())
            if item.typed_option_id == expected.get("typed_option_id")
        )
        if (
            expected.get("disposition") != "typed_input"
            or len(matching_options) != 1
            or matching_options[0].input_type_id
            != audited_case.get("expected_input_type_id")
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_expected_answer_invalid"
            )
        return _closed_json_copy(expected)
    if (
        audited_case.get("expected_disposition")
        != "unclassified_financial_input"
        or not isinstance(
            audited_case.get("expected_reason_code"),
            str,
        )
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_expected_answer_invalid"
        )
    return {
        "disposition": "unclassified_financial_input",
        "reason_code": audited_case["expected_reason_code"],
    }


def _validated_projection_hashes(
    *,
    projection: Any,
    case: Gate2FinancialSemanticV6QualificationCase,
    provider_profile: Gate2ProviderProfile,
    exact_model_id: str,
    request_profile: str,
    parameters: (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeParameters
    ),
    provider_profile_resolver: Callable[
        [str], Gate2ProviderProfile
    ] = gate2_provider_profile,
) -> dict[str, Any]:
    if (
        type(projection)
        is not Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection
        or projection.request_profile != request_profile
        or type(projection.sealed_request)
        is not Gate2FinancialSemanticV6ContextV21SealedRequest
        or type(projection.prepared_request)
        is not Gate2PreparedProviderRequest
        or type(projection.transport_contract)
        is not Gate2ContextV21BudgetSmokeTransportContract
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_projection_invalid"
        )
    sealed_request = projection.sealed_request
    receipt = sealed_request.sealed_request_receipt
    prepared = projection.prepared_request
    transport_contract = projection.transport_contract
    response_profile = getattr(
        case.choice_contract,
        "context_v2_1_response_profile",
        None,
    )
    canonical_schema = (
        response_profile.canonical_schema()
        if response_profile is not None
        else None
    )
    try:
        model_visible_request = _closed_json_copy(
            sealed_request.model_visible_request
        )
        sealed_payload = _closed_json_copy(asdict(sealed_request))
        prepared_payload = _closed_json_copy(asdict(prepared))
        prepared_form_data = _closed_json_copy(prepared.form_data)
        provider_visible_schema = _closed_json_copy(
            prepared.provider_visible_schema
        )
        transport_contract_snapshot = _closed_json_copy(
            transport_contract.safe_snapshot()
        )
        canonical_schema = _closed_json_copy(canonical_schema)
    except (TypeError, ValueError) as exc:
        raise Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_projection_not_closed"
        ) from exc
    messages = model_visible_request.get("messages")
    response_format = model_visible_request.get("response_format")
    json_schema = (
        response_format.get("json_schema")
        if isinstance(response_format, dict)
        else None
    )
    if (
        sealed_request.active is not False
        or sealed_request.transport_eligible is not False
        or response_profile.active is not False
        or response_profile.transport_eligible is not False
        or set(model_visible_request)
        != {"messages", "response_format"}
        or not isinstance(messages, list)
        or len(messages) != 2
        or any(
            not isinstance(item, dict)
            or set(item) != {"role", "content"}
            or not isinstance(item.get("content"), str)
            for item in messages
        )
        or messages[0].get("role") != "system"
        or messages[1].get("role") != "user"
        or not isinstance(json_schema, dict)
        or response_format.get("type") != "json_schema"
        or json_schema.get("strict") is not True
        or json_schema.get("schema") != canonical_schema
        or sealed_request.response_format != response_format
        or receipt.status != "passed"
        or receipt.provider_calls_total != 0
        or receipt.model_visible_request_hash
        != _model_json_hash(sealed_request.model_visible_request)
        or receipt.response_format_hash
        != _model_json_hash(sealed_request.response_format)
        or receipt.integrity_hash
        != sha256_json(receipt.integrity_payload())
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_sealed_request_invalid"
        )
    if (
        not prepared.schema_binding_is_valid()
        or not prepared.canonical_schema_is_bound(canonical_schema)
        or prepared.provider_adapter_id
        != provider_profile.adapter_id
        or not prepared.context_v2_1_budget_smoke_contract_is_bound(
            canonical_schema=canonical_schema,
            provider_profile=provider_profile,
            model_visible_request=model_visible_request,
            exact_model_id=exact_model_id,
            operation_identity=(
                "broker-reports-goal12-preflight:"
                f"{provider_profile.profile_id}:{case.case_id}"
            ),
            provider_profile_resolver=provider_profile_resolver,
        )
        or prepared_form_data.get("model") != exact_model_id
        or transport_contract.transport_policy
        != parameters.transport_policy
        or transport_contract.integrity_hash
        != sha256_json(transport_contract_snapshot)
        or set(prepared_form_data) & _FORBIDDEN_REQUEST_FIELDS
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_prepared_request_invalid"
        )
    if parameters.reasoning_policy == "minimal":
        if prepared_form_data.get("reasoning_effort") != "minimal":
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_parameter_projection_invalid"
            )
    elif set(prepared_form_data) & _REASONING_FIELDS:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_parameter_projection_invalid"
        )
    if provider_profile.adapter_id == "anthropic_native_messages":
        if (
            set(prepared_form_data)
            != {
                "model",
                "max_tokens",
                "messages",
                "output_config",
                "system",
            }
            or prepared_form_data.get("system")
            != messages[0]["content"]
            or prepared_form_data.get("messages")
            != [messages[1]]
            or prepared_form_data.get("max_tokens")
            != parameters.maximum_output_tokens
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_message_projection_invalid"
            )
    else:
        expected_fields = {
            "model",
            "messages",
            "response_format",
            "stream",
        }
        maximum_output_field = (
            "max_completion_tokens"
            if provider_profile.adapter_id == "openai_response_format"
            else "max_tokens"
        )
        expected_fields.add(maximum_output_field)
        if parameters.reasoning_policy == "minimal":
            expected_fields.add("reasoning_effort")
        if (
            set(prepared_form_data) != expected_fields
            or prepared_form_data.get("stream") is not False
            or prepared_form_data.get("messages") != messages
            or prepared_form_data.get(maximum_output_field)
            != parameters.maximum_output_tokens
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_wire_request_invalid"
            )
    return {
        "sealed_request_hash": sha256_json(sealed_payload),
        "sealed_request_receipt_integrity_hash": (
            receipt.integrity_hash
        ),
        "model_visible_request_hash": (
            receipt.model_visible_request_hash
        ),
        "canonical_schema_hash": sha256_json(canonical_schema),
        "prepared_request_hash": sha256_json(prepared_payload),
        "provider_visible_schema_hash": sha256_json(
            provider_visible_schema
        ),
        "transport_contract": transport_contract_snapshot,
        "transport_contract_hash": transport_contract.integrity_hash,
    }


def _closed_json_copy(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )


def _model_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError(code)
