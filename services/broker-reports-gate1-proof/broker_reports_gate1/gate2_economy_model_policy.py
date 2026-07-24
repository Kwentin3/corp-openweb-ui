from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable


FACTORY_REQUIRED = (
    "Gate2EconomyModelPolicyFactory.create is the only production economy "
    "model policy construction entrypoint"
)
FORBIDDEN = (
    "Runtime config, valves, diagnostics and tests must not extend the "
    "qualified economy allowlist or select non-economy models"
)

POLICY_ID = "broker_reports_economy_model_policy_v1"
POLICY_VERSION = "1.2.0"
POLICY_SCHEMA_VERSION = "broker_reports_economy_model_policy_v1"

MODEL_STATUS_QUALIFICATION_REQUIRED = "qualification_required"
MODEL_STATUS_QUALIFIED = "qualified"
MODEL_STATUS_NOT_QUALIFIED = "not_qualified"
MODEL_STATUS_UNAVAILABLE = "unavailable"
MODEL_STATUS_UNSUPPORTED_CONTRACT = "unsupported_contract"
MODEL_STATUSES = (
    MODEL_STATUS_QUALIFICATION_REQUIRED,
    MODEL_STATUS_QUALIFIED,
    MODEL_STATUS_NOT_QUALIFIED,
    MODEL_STATUS_UNAVAILABLE,
    MODEL_STATUS_UNSUPPORTED_CONTRACT,
)

MODEL_LIFECYCLE_CANDIDATE = "candidate"
MODEL_LIFECYCLE_ACTIVE = "active"
MODEL_LIFECYCLE_RETIRED = "retired"
MODEL_LIFECYCLES = (
    MODEL_LIFECYCLE_CANDIDATE,
    MODEL_LIFECYCLE_ACTIVE,
    MODEL_LIFECYCLE_RETIRED,
)

WORKLOAD_GATE2_SOURCE = "gate2_source"
WORKLOAD_GATE2_DOMAIN = "gate2_domain"
WORKLOAD_GATE2_FINANCIAL_EVIDENCE = "gate2_financial_evidence"
WORKLOAD_GATE2_FINANCIAL_CHECKSUM = "gate2_financial_checksum"
ECONOMY_WORKLOAD_CLASSES = (
    WORKLOAD_GATE2_SOURCE,
    WORKLOAD_GATE2_DOMAIN,
    WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
    WORKLOAD_GATE2_FINANCIAL_CHECKSUM,
)

REASONING_DISABLED = "disabled"
REASONING_MINIMAL = "minimal"
REASONING_POLICIES = (REASONING_DISABLED, REASONING_MINIMAL)


class Gate2EconomyModelPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EconomyModelCost:
    input_usd_per_million: str
    cached_input_usd_per_million: str | None
    output_usd_per_million: str
    pricing_basis: str = "standard_synchronous_text_tokens"

    def to_dict(self) -> dict[str, str | None]:
        return {
            "input_usd_per_million": self.input_usd_per_million,
            "cached_input_usd_per_million": self.cached_input_usd_per_million,
            "output_usd_per_million": self.output_usd_per_million,
            "pricing_basis": self.pricing_basis,
        }


@dataclass(frozen=True)
class EconomyModelDeclaration:
    provider_profile_id: str
    provider_id: str
    exact_model_id: str
    aliases: tuple[str, ...]
    model_family: str
    cost_class: str
    supported_modalities: tuple[str, ...]
    structured_output_mode: str
    workload_classes: tuple[str, ...]
    preference_order: int
    reasoning_policy: str
    paid_tools_allowed: bool
    fallback_eligible: bool
    lifecycle: str
    qualification_status: str
    qualification_receipt_identity: str | None
    availability_evidence: str
    cost: EconomyModelCost

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_profile_id": self.provider_profile_id,
            "provider_id": self.provider_id,
            "exact_model_id": self.exact_model_id,
            "aliases": list(self.aliases),
            "model_family": self.model_family,
            "cost_class": self.cost_class,
            "supported_modalities": list(self.supported_modalities),
            "structured_output_mode": self.structured_output_mode,
            "workload_classes": list(self.workload_classes),
            "preference_order": self.preference_order,
            "reasoning_policy": self.reasoning_policy,
            "paid_tools_allowed": self.paid_tools_allowed,
            "fallback_eligible": self.fallback_eligible,
            "lifecycle": self.lifecycle,
            "qualification_status": self.qualification_status,
            "qualification_receipt_identity": (
                self.qualification_receipt_identity
            ),
            "availability_evidence": self.availability_evidence,
            "cost": self.cost.to_dict(),
        }


@dataclass(frozen=True)
class EconomyWorkloadPolicy:
    workload_class: str
    maximum_estimated_input_tokens: int
    maximum_output_tokens: int
    maximum_provider_calls_per_operation: int
    maximum_fallback_calls_per_operation: int
    maximum_provider_calls_per_full_scope_run: int
    maximum_estimated_cost_usd_per_operation: str
    maximum_estimated_cost_usd_per_full_scope_run: str
    budget_measurement_basis: str
    reasoning_policy: str
    paid_tools_allowed: bool
    response_body_policy: str

    def to_dict(self) -> dict[str, object]:
        return {
            "workload_class": self.workload_class,
            "maximum_estimated_input_tokens": (
                self.maximum_estimated_input_tokens
            ),
            "maximum_output_tokens": self.maximum_output_tokens,
            "maximum_provider_calls_per_operation": (
                self.maximum_provider_calls_per_operation
            ),
            "maximum_fallback_calls_per_operation": (
                self.maximum_fallback_calls_per_operation
            ),
            "maximum_provider_calls_per_full_scope_run": (
                self.maximum_provider_calls_per_full_scope_run
            ),
            "maximum_estimated_cost_usd_per_operation": (
                self.maximum_estimated_cost_usd_per_operation
            ),
            "maximum_estimated_cost_usd_per_full_scope_run": (
                self.maximum_estimated_cost_usd_per_full_scope_run
            ),
            "budget_measurement_basis": self.budget_measurement_basis,
            "reasoning_policy": self.reasoning_policy,
            "paid_tools_allowed": self.paid_tools_allowed,
            "response_body_policy": self.response_body_policy,
        }


@dataclass(frozen=True)
class EconomyModelResolution:
    requested_model_id: str
    exact_model_id: str
    alias_used: bool
    provider_profile_id: str
    qualification_status: str


@dataclass(frozen=True)
class Gate2EconomyModelPolicySnapshot:
    policy_id: str
    policy_version: str
    policy_schema_version: str
    models: tuple[EconomyModelDeclaration, ...]
    workloads: tuple[EconomyWorkloadPolicy, ...]
    policy_hash: str

    def model(self, model_id: str) -> EconomyModelDeclaration:
        resolution = self.resolve_model_id(model_id)
        for declaration in self.models:
            if declaration.exact_model_id == resolution.exact_model_id:
                return declaration
        raise Gate2EconomyModelPolicyError(
            "economy_model_not_registered",
            "Requested model is not registered in the economy policy",
        )

    def workload(self, workload_class: str) -> EconomyWorkloadPolicy:
        for declaration in self.workloads:
            if declaration.workload_class == workload_class:
                return declaration
        raise Gate2EconomyModelPolicyError(
            "economy_workload_unknown",
            "Requested workload is not registered in the economy policy",
        )

    def resolve_model_id(self, model_id: str) -> EconomyModelResolution:
        requested = str(model_id or "").strip()
        for declaration in self.models:
            if requested == declaration.exact_model_id:
                return EconomyModelResolution(
                    requested_model_id=requested,
                    exact_model_id=declaration.exact_model_id,
                    alias_used=False,
                    provider_profile_id=declaration.provider_profile_id,
                    qualification_status=declaration.qualification_status,
                )
            if requested in declaration.aliases:
                return EconomyModelResolution(
                    requested_model_id=requested,
                    exact_model_id=declaration.exact_model_id,
                    alias_used=True,
                    provider_profile_id=declaration.provider_profile_id,
                    qualification_status=declaration.qualification_status,
                )
        raise Gate2EconomyModelPolicyError(
            "economy_model_not_registered",
            "Requested model is not registered in the economy policy",
        )

    def qualified_allowlist(
        self,
        workload_class: str,
    ) -> tuple[str, ...]:
        self.workload(workload_class)
        return tuple(
            declaration.exact_model_id
            for declaration in self.models
            if declaration.lifecycle == MODEL_LIFECYCLE_ACTIVE
            and declaration.qualification_status == MODEL_STATUS_QUALIFIED
            and workload_class in declaration.workload_classes
        )

    def assert_runtime_model_allowed(
        self,
        *,
        model_id: str,
        workload_class: str,
    ) -> EconomyModelResolution:
        resolution = self.resolve_model_id(model_id)
        declaration = self.model(resolution.exact_model_id)
        if workload_class not in declaration.workload_classes:
            raise Gate2EconomyModelPolicyError(
                "economy_model_workload_forbidden",
                "Economy model is not allowed for the requested workload",
            )
        if (
            declaration.lifecycle != MODEL_LIFECYCLE_ACTIVE
            or declaration.qualification_status != MODEL_STATUS_QUALIFIED
        ):
            raise Gate2EconomyModelPolicyError(
                "economy_model_not_qualified",
                "Economy model has no accepted qualification receipt",
            )
        return resolution

    def narrow_runtime_allowlist(
        self,
        *,
        workload_class: str,
        requested_model_ids: Iterable[str] | None,
    ) -> tuple[str, ...]:
        qualified = self.qualified_allowlist(workload_class)
        if requested_model_ids is None:
            return qualified
        requested = tuple(
            self.resolve_model_id(model_id).exact_model_id
            for model_id in requested_model_ids
        )
        if not set(requested).issubset(set(qualified)):
            raise Gate2EconomyModelPolicyError(
                "economy_runtime_allowlist_expansion_forbidden",
                "Runtime configuration may only narrow the qualified allowlist",
            )
        return tuple(
            model_id for model_id in qualified if model_id in set(requested)
        )

    def provider_allowlist(
        self,
        workload_class: str,
    ) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {}
        qualified = set(self.qualified_allowlist(workload_class))
        for declaration in self.models:
            if declaration.exact_model_id in qualified:
                result.setdefault(declaration.provider_profile_id, []).append(
                    declaration.exact_model_id
                )
        return {
            provider: tuple(model_ids)
            for provider, model_ids in sorted(result.items())
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_schema_version": self.policy_schema_version,
            "models": [item.to_dict() for item in self.models],
            "workloads": [item.to_dict() for item in self.workloads],
            "policy_hash": self.policy_hash,
        }


_ALL_GATE2_WORKLOADS = ECONOMY_WORKLOAD_CLASSES

ECONOMY_MODEL_DECLARATIONS = (
    EconomyModelDeclaration(
        provider_profile_id="openai_gpt",
        provider_id="openai",
        exact_model_id="gpt-5-nano-2025-08-07",
        aliases=("gpt-5-nano",),
        model_family="nano",
        cost_class="economy",
        supported_modalities=("text",),
        structured_output_mode="openwebui_response_format_json_schema",
        workload_classes=_ALL_GATE2_WORKLOADS,
        preference_order=0,
        reasoning_policy=REASONING_MINIMAL,
        paid_tools_allowed=False,
        fallback_eligible=True,
        lifecycle=MODEL_LIFECYCLE_CANDIDATE,
        qualification_status=MODEL_STATUS_UNAVAILABLE,
        qualification_receipt_identity=None,
        availability_evidence="stage_models_endpoint_unavailable_2026-07-24",
        cost=EconomyModelCost("0.05", "0.005", "0.40"),
    ),
    EconomyModelDeclaration(
        provider_profile_id="openai_gpt",
        provider_id="openai",
        exact_model_id="gpt-5.4-nano-2026-03-17",
        aliases=("gpt-5.4-nano",),
        model_family="nano",
        cost_class="economy",
        supported_modalities=("text",),
        structured_output_mode="openwebui_response_format_json_schema",
        workload_classes=_ALL_GATE2_WORKLOADS,
        preference_order=1,
        reasoning_policy=REASONING_MINIMAL,
        paid_tools_allowed=False,
        fallback_eligible=True,
        lifecycle=MODEL_LIFECYCLE_CANDIDATE,
        qualification_status=MODEL_STATUS_UNAVAILABLE,
        qualification_receipt_identity=None,
        availability_evidence="stage_models_endpoint_unavailable_2026-07-24",
        cost=EconomyModelCost("0.20", "0.02", "1.25"),
    ),
    EconomyModelDeclaration(
        provider_profile_id="google_gemini",
        provider_id="google",
        exact_model_id="models/gemini-3.1-flash-lite",
        aliases=("gemini-3.1-flash-lite",),
        model_family="flash_lite",
        cost_class="economy",
        supported_modalities=("text",),
        structured_output_mode="openwebui_response_format_json_schema",
        workload_classes=_ALL_GATE2_WORKLOADS,
        preference_order=2,
        reasoning_policy=REASONING_MINIMAL,
        paid_tools_allowed=False,
        fallback_eligible=True,
        lifecycle=MODEL_LIFECYCLE_CANDIDATE,
        qualification_status=MODEL_STATUS_NOT_QUALIFIED,
        qualification_receipt_identity=None,
        availability_evidence=(
            "stage_financial_contract_failed_"
            "financial_evidence_decision_unclassified_shape_invalid_"
            "2026-07-24"
        ),
        cost=EconomyModelCost("0.25", "0.025", "1.50"),
    ),
    EconomyModelDeclaration(
        provider_profile_id="google_gemini",
        provider_id="google",
        exact_model_id="models/gemini-3.5-flash-lite",
        aliases=("gemini-3.5-flash-lite",),
        model_family="flash_lite",
        cost_class="economy",
        supported_modalities=("text",),
        structured_output_mode="openwebui_response_format_json_schema",
        workload_classes=_ALL_GATE2_WORKLOADS,
        preference_order=3,
        reasoning_policy=REASONING_MINIMAL,
        paid_tools_allowed=False,
        fallback_eligible=True,
        lifecycle=MODEL_LIFECYCLE_CANDIDATE,
        qualification_status=MODEL_STATUS_UNSUPPORTED_CONTRACT,
        qualification_receipt_identity=None,
        availability_evidence=(
            "stage_source_contract_passed_but_financial_qualification_"
            "route_unavailable_2026-07-24"
        ),
        cost=EconomyModelCost("0.30", "0.03", "2.50"),
    ),
    EconomyModelDeclaration(
        provider_profile_id="anthropic_claude",
        provider_id="anthropic",
        exact_model_id="claude-haiku-4-5-20251001",
        aliases=("claude-haiku-4-5",),
        model_family="haiku",
        cost_class="economy",
        supported_modalities=("text",),
        structured_output_mode=(
            "openwebui_anthropic_output_config_json_schema"
        ),
        workload_classes=_ALL_GATE2_WORKLOADS,
        preference_order=4,
        reasoning_policy=REASONING_DISABLED,
        paid_tools_allowed=False,
        fallback_eligible=True,
        lifecycle=MODEL_LIFECYCLE_CANDIDATE,
        qualification_status=MODEL_STATUS_UNSUPPORTED_CONTRACT,
        qualification_receipt_identity=None,
        availability_evidence=(
            "stage_financial_contract_rejected_"
            "gate2_model_schema_response_format_rejected_2026-07-24"
        ),
        cost=EconomyModelCost("1.00", "0.10", "5.00"),
    ),
)

ECONOMY_WORKLOAD_POLICIES = (
    EconomyWorkloadPolicy(
        workload_class=WORKLOAD_GATE2_SOURCE,
        maximum_estimated_input_tokens=12_000,
        maximum_output_tokens=4_096,
        maximum_provider_calls_per_operation=1,
        maximum_fallback_calls_per_operation=1,
        maximum_provider_calls_per_full_scope_run=64,
        maximum_estimated_cost_usd_per_operation="0.064960",
        maximum_estimated_cost_usd_per_full_scope_run="2.078720",
        budget_measurement_basis=(
            "existing_actual_corpus_gate2_12000_input_bound;"
            "4096_bounded_schema_output;64_call_run;"
            "worst_allowed_haiku_price"
        ),
        reasoning_policy=REASONING_DISABLED,
        paid_tools_allowed=False,
        response_body_policy="strict_contract_json_only",
    ),
    EconomyWorkloadPolicy(
        workload_class=WORKLOAD_GATE2_DOMAIN,
        maximum_estimated_input_tokens=12_000,
        maximum_output_tokens=4_096,
        maximum_provider_calls_per_operation=1,
        maximum_fallback_calls_per_operation=1,
        maximum_provider_calls_per_full_scope_run=64,
        maximum_estimated_cost_usd_per_operation="0.064960",
        maximum_estimated_cost_usd_per_full_scope_run="2.078720",
        budget_measurement_basis=(
            "existing_actual_corpus_gate2_12000_input_bound;"
            "4096_bounded_schema_output;64_call_run;"
            "worst_allowed_haiku_price"
        ),
        reasoning_policy=REASONING_DISABLED,
        paid_tools_allowed=False,
        response_body_policy="strict_contract_json_only",
    ),
    EconomyWorkloadPolicy(
        workload_class=WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
        maximum_estimated_input_tokens=3_072,
        maximum_output_tokens=640,
        maximum_provider_calls_per_operation=1,
        maximum_fallback_calls_per_operation=1,
        maximum_provider_calls_per_full_scope_run=64,
        maximum_estimated_cost_usd_per_operation="0.012544",
        maximum_estimated_cost_usd_per_full_scope_run="0.401408",
        budget_measurement_basis=(
            "actual_corpus_max_input_2666_output_506;"
            "caps_3072_input_640_output;64_total_calls;"
            "worst_allowed_haiku_price"
        ),
        reasoning_policy=REASONING_DISABLED,
        paid_tools_allowed=False,
        response_body_policy="strict_contract_json_only",
    ),
    EconomyWorkloadPolicy(
        workload_class=WORKLOAD_GATE2_FINANCIAL_CHECKSUM,
        maximum_estimated_input_tokens=130_000,
        maximum_output_tokens=1_024,
        maximum_provider_calls_per_operation=1,
        maximum_fallback_calls_per_operation=0,
        maximum_provider_calls_per_full_scope_run=1,
        maximum_estimated_cost_usd_per_operation="0.135120",
        maximum_estimated_cost_usd_per_full_scope_run="0.135120",
        budget_measurement_basis=(
            "actual_corpus_input_117555_output_783;"
            "caps_130000_input_1024_output;one_total_call;"
            "worst_allowed_haiku_price"
        ),
        reasoning_policy=REASONING_DISABLED,
        paid_tools_allowed=False,
        response_body_policy="strict_contract_json_only",
    ),
)


class Gate2EconomyModelPolicyFactory:
    def create(self) -> Gate2EconomyModelPolicySnapshot:
        validate_economy_model_policy_inputs(
            ECONOMY_MODEL_DECLARATIONS,
            ECONOMY_WORKLOAD_POLICIES,
        )
        material = _policy_material(
            ECONOMY_MODEL_DECLARATIONS,
            ECONOMY_WORKLOAD_POLICIES,
        )
        policy_hash = hashlib.sha256(
            json.dumps(
                material,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return Gate2EconomyModelPolicySnapshot(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            policy_schema_version=POLICY_SCHEMA_VERSION,
            models=ECONOMY_MODEL_DECLARATIONS,
            workloads=ECONOMY_WORKLOAD_POLICIES,
            policy_hash=policy_hash,
        )


def validate_economy_model_policy_inputs(
    models: tuple[EconomyModelDeclaration, ...],
    workloads: tuple[EconomyWorkloadPolicy, ...],
) -> None:
    if not models:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_models_empty",
            "Economy policy must declare at least one model candidate",
        )
    exact_ids = [item.exact_model_id for item in models]
    if len(exact_ids) != len(set(exact_ids)):
        raise Gate2EconomyModelPolicyError(
            "economy_policy_duplicate_model_id",
            "Economy policy contains duplicate exact model IDs",
        )
    preference_order = [item.preference_order for item in models]
    if sorted(preference_order) != list(range(len(models))):
        raise Gate2EconomyModelPolicyError(
            "economy_policy_preference_order_invalid",
            "Economy model preference order must be unique and gapless",
        )
    aliases: set[str] = set()
    for item in models:
        _validate_model_declaration(item)
        for alias in item.aliases:
            if (
                not alias
                or alias in aliases
                or alias in exact_ids
                or alias == item.exact_model_id
            ):
                raise Gate2EconomyModelPolicyError(
                    "economy_policy_alias_invalid",
                    "Economy policy contains a conflicting model alias",
                )
            aliases.add(alias)

    workload_ids = [item.workload_class for item in workloads]
    if (
        len(workload_ids) != len(set(workload_ids))
        or set(workload_ids) != set(ECONOMY_WORKLOAD_CLASSES)
    ):
        raise Gate2EconomyModelPolicyError(
            "economy_policy_workload_set_invalid",
            "Economy policy must define each Gate 2 workload exactly once",
        )
    for item in workloads:
        _validate_workload_policy(item)


def _validate_model_declaration(item: EconomyModelDeclaration) -> None:
    family_valid = (
        item.provider_profile_id == "openai_gpt"
        and item.provider_id == "openai"
        and item.model_family == "nano"
        and "-nano-" in item.exact_model_id
    ) or (
        item.provider_profile_id == "google_gemini"
        and item.provider_id == "google"
        and item.model_family == "flash_lite"
        and "flash-lite" in item.exact_model_id
    ) or (
        item.provider_profile_id == "anthropic_claude"
        and item.provider_id == "anthropic"
        and item.model_family == "haiku"
        and "haiku" in item.exact_model_id
    )
    if not family_valid:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_model_family_forbidden",
            "Only Nano, Flash-Lite and Haiku exact model IDs are allowed",
        )
    if item.cost_class != "economy":
        raise Gate2EconomyModelPolicyError(
            "economy_policy_cost_class_forbidden",
            "Economy policy cannot contain a non-economy model",
        )
    if item.supported_modalities != ("text",):
        raise Gate2EconomyModelPolicyError(
            "economy_policy_modality_invalid",
            "Gate 2 economy policy permits text contract input only",
        )
    if set(item.workload_classes) != set(ECONOMY_WORKLOAD_CLASSES):
        raise Gate2EconomyModelPolicyError(
            "economy_policy_model_workloads_invalid",
            "Each economy candidate must declare the supported Gate 2 workloads",
        )
    if item.reasoning_policy not in REASONING_POLICIES:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_reasoning_invalid",
            "Economy reasoning must be disabled or minimal",
        )
    if item.paid_tools_allowed:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_paid_tools_forbidden",
            "Paid tools are forbidden for Gate 2 economy models",
        )
    if (
        item.lifecycle not in MODEL_LIFECYCLES
        or item.qualification_status not in MODEL_STATUSES
    ):
        raise Gate2EconomyModelPolicyError(
            "economy_policy_lifecycle_invalid",
            "Economy model lifecycle or qualification status is invalid",
        )
    if item.lifecycle == MODEL_LIFECYCLE_ACTIVE:
        if item.qualification_status != MODEL_STATUS_QUALIFIED:
            raise Gate2EconomyModelPolicyError(
                "economy_policy_active_model_not_qualified",
                "Active economy model must be qualified",
            )
        if not _is_sha256(item.qualification_receipt_identity):
            raise Gate2EconomyModelPolicyError(
                "economy_policy_qualification_receipt_missing",
                "Active economy model must bind a qualification receipt",
            )
    elif item.qualification_status == MODEL_STATUS_QUALIFIED:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_qualified_model_not_active",
            "Qualified economy model must have active lifecycle",
        )
    elif item.qualification_receipt_identity is not None:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_unqualified_receipt_forbidden",
            "Unqualified economy model cannot bind a qualification receipt",
        )
    for value in (
        item.cost.input_usd_per_million,
        item.cost.output_usd_per_million,
    ):
        try:
            if Decimal(value) <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            raise Gate2EconomyModelPolicyError(
                "economy_policy_cost_invalid",
                "Economy model token pricing must be positive decimal text",
            ) from None


def _validate_workload_policy(item: EconomyWorkloadPolicy) -> None:
    integer_values = (
        item.maximum_estimated_input_tokens,
        item.maximum_output_tokens,
        item.maximum_provider_calls_per_operation,
        item.maximum_provider_calls_per_full_scope_run,
    )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in integer_values
    ):
        raise Gate2EconomyModelPolicyError(
            "economy_policy_workload_budget_invalid",
            "Economy workload budgets must be positive integers",
        )
    if item.maximum_provider_calls_per_operation != 1:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_default_calls_invalid",
            "Economy workload default provider calls must equal one",
        )
    if item.maximum_fallback_calls_per_operation not in {0, 1}:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_fallback_calls_invalid",
            "Economy fallback calls must be zero or one",
        )
    for value in (
        item.maximum_estimated_cost_usd_per_operation,
        item.maximum_estimated_cost_usd_per_full_scope_run,
    ):
        try:
            if Decimal(value) <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            raise Gate2EconomyModelPolicyError(
                "economy_policy_workload_cost_budget_invalid",
                "Economy workload cost budgets must be positive decimal text",
            ) from None
    if not item.budget_measurement_basis.strip():
        raise Gate2EconomyModelPolicyError(
            "economy_policy_workload_measurement_basis_missing",
            "Economy workload budgets require a measured basis",
        )
    if item.reasoning_policy not in REASONING_POLICIES:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_workload_reasoning_invalid",
            "Economy workload reasoning must be disabled or minimal",
        )
    if item.paid_tools_allowed:
        raise Gate2EconomyModelPolicyError(
            "economy_policy_workload_paid_tools_forbidden",
            "Paid tools are forbidden for Gate 2 workloads",
        )
    if item.response_body_policy != "strict_contract_json_only":
        raise Gate2EconomyModelPolicyError(
            "economy_policy_response_body_invalid",
            "Economy workload output must be strict contract JSON only",
        )


def _policy_material(
    models: tuple[EconomyModelDeclaration, ...],
    workloads: tuple[EconomyWorkloadPolicy, ...],
) -> dict[str, object]:
    return {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "policy_schema_version": POLICY_SCHEMA_VERSION,
        "models": [item.to_dict() for item in models],
        "workloads": [item.to_dict() for item in workloads],
    }


def _is_sha256(value: str | None) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
