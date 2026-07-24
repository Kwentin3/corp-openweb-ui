from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Iterable

from .gate2_economy_model_policy import (
    REASONING_DISABLED,
    REASONING_MINIMAL,
    WORKLOAD_GATE2_DOMAIN,
    WORKLOAD_GATE2_FINANCIAL_CHECKSUM,
    WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
    WORKLOAD_GATE2_SOURCE,
    EconomyModelDeclaration,
    EconomyWorkloadPolicy,
    Gate2EconomyModelPolicyError,
    Gate2EconomyModelPolicyFactory,
    Gate2EconomyModelPolicySnapshot,
)
from .gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    Gate2SourceFactRuntimeError,
)
from .gate2_model_requests import (
    DOMAIN_REQUEST_PROFILE,
    FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
    SOURCE_REQUEST_PROFILE,
)


FACTORY_REQUIRED = (
    "Gate2EconomyBudgetSessionFactory.create is the only production Gate 2 "
    "economy budget-session construction entrypoint"
)
FORBIDDEN = (
    "Provider callers, workload config, valves and test harnesses must not "
    "bypass economy token, call, reasoning, tool or cost authorization"
)

BUDGET_SCHEMA_VERSION = "broker_reports_gate2_economy_budget_v1"
TOKEN_ESTIMATOR_ID = "compact_request_utf8_bytes_div_4_plus_64_v1"
_TOKEN_ESTIMATOR_OVERHEAD = 64
_USD_QUANTUM = Decimal("0.000000001")
_TOOL_FIELDS = frozenset(
    {
        "tools",
        "tool_choice",
        "functions",
        "function_call",
        "web_search_options",
        "search",
        "plugins",
    }
)
_REASONING_FIELDS = frozenset(
    {
        "reasoning",
        "reasoning_effort",
        "thinking",
        "thinking_config",
    }
)

_WORKLOAD_BY_REQUEST_PROFILE = {
    SOURCE_REQUEST_PROFILE: WORKLOAD_GATE2_SOURCE,
    DOMAIN_REQUEST_PROFILE: WORKLOAD_GATE2_DOMAIN,
    FINANCIAL_EVIDENCE_REQUEST_PROFILE: (
        WORKLOAD_GATE2_FINANCIAL_EVIDENCE
    ),
    FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE: (
        WORKLOAD_GATE2_FINANCIAL_CHECKSUM
    ),
}


@dataclass(frozen=True)
class Gate2EconomyCallAuthorization:
    workload_class: str
    requested_model_id: str
    exact_model_id: str
    provider_profile_id: str
    operation_identity_sha256: str
    fallback_call: bool
    estimated_input_tokens: int
    maximum_output_tokens: int
    estimated_cost_usd: str
    provider_calls_authorized_total: int
    fallback_calls_authorized_total: int
    prepared_form_data: dict[str, Any]


class Gate2EconomyBudgetSessionFactory:
    def __init__(
        self,
        *,
        policy: Gate2EconomyModelPolicySnapshot | None = None,
    ) -> None:
        self.policy = policy or Gate2EconomyModelPolicyFactory().create()

    def create(
        self,
        *,
        request_profile: str,
    ) -> "Gate2EconomyBudgetSession":
        workload_class = _WORKLOAD_BY_REQUEST_PROFILE.get(request_profile)
        if workload_class is None:
            _fail(
                "gate2_economy_budget_request_profile_unknown",
                "Request profile has no economy workload budget",
            )
        return Gate2EconomyBudgetSession(
            policy=self.policy,
            workload=self.policy.workload(workload_class),
        )


class Gate2EconomyBudgetSession:
    def __init__(
        self,
        *,
        policy: Gate2EconomyModelPolicySnapshot,
        workload: EconomyWorkloadPolicy,
    ) -> None:
        self.policy = policy
        self.workload = workload
        self._operation_call_counts: dict[str, int] = {}
        self._operation_fallback_counts: dict[str, int] = {}
        self._operation_estimated_costs: dict[str, Decimal] = {}
        self._provider_calls_authorized_total = 0
        self._fallback_calls_authorized_total = 0
        self._estimated_cost_authorized_total = Decimal("0")

    def prepare_call(
        self,
        *,
        form_data: dict[str, Any],
        model_id: str,
        provider_profile_id: str,
        operation_identity: str,
        fallback_call: bool = False,
    ) -> Gate2EconomyCallAuthorization:
        declaration = self._model_declaration(
            model_id=model_id,
            provider_profile_id=provider_profile_id,
        )
        operation_hash = _identity_hash(operation_identity)
        operation_calls = self._operation_call_counts.get(operation_hash, 0)
        fallback_calls = self._operation_fallback_counts.get(
            operation_hash,
            0,
        )
        default_calls = operation_calls - fallback_calls
        if fallback_call:
            if (
                fallback_calls
                >= self.workload.maximum_fallback_calls_per_operation
            ):
                self._block(
                    "gate2_economy_fallback_call_budget_exceeded",
                    "Economy fallback-call budget is exhausted",
                    operation_hash=operation_hash,
                )
        elif (
            default_calls
            >= self.workload.maximum_provider_calls_per_operation
        ):
            self._block(
                "gate2_economy_provider_call_budget_exceeded",
                "Economy default provider-call budget is exhausted",
                operation_hash=operation_hash,
            )
        if (
            self._provider_calls_authorized_total
            >= self.workload.maximum_provider_calls_per_full_scope_run
        ):
            self._block(
                "gate2_economy_full_scope_call_budget_exceeded",
                "Economy full-scope provider-call budget is exhausted",
                operation_hash=operation_hash,
            )

        prepared = self._apply_request_controls(
            form_data=form_data,
            declaration=declaration,
        )
        estimated_input_tokens = estimate_gate2_request_input_tokens(prepared)
        if (
            estimated_input_tokens
            > self.workload.maximum_estimated_input_tokens
        ):
            self._block(
                "gate2_economy_input_token_budget_exceeded",
                "Estimated economy input exceeds the workload budget",
                operation_hash=operation_hash,
                observed=estimated_input_tokens,
                allowed=self.workload.maximum_estimated_input_tokens,
            )
        estimated_cost = estimate_model_cost_usd(
            declaration=declaration,
            input_tokens=estimated_input_tokens,
            output_tokens=self.workload.maximum_output_tokens,
        )
        projected_operation_cost = (
            self._operation_estimated_costs.get(
                operation_hash,
                Decimal("0"),
            )
            + estimated_cost
        )
        if projected_operation_cost > Decimal(
            self.workload.maximum_estimated_cost_usd_per_operation
        ):
            self._block(
                "gate2_economy_operation_cost_budget_exceeded",
                "Estimated economy operation cost exceeds the budget",
                operation_hash=operation_hash,
                observed=_usd_text(projected_operation_cost),
                allowed=(
                    self.workload
                    .maximum_estimated_cost_usd_per_operation
                ),
            )
        projected_full_cost = (
            self._estimated_cost_authorized_total + estimated_cost
        )
        if projected_full_cost > Decimal(
            self.workload.maximum_estimated_cost_usd_per_full_scope_run
        ):
            self._block(
                "gate2_economy_full_scope_cost_budget_exceeded",
                "Estimated economy full-scope cost exceeds the budget",
                operation_hash=operation_hash,
                observed=_usd_text(projected_full_cost),
                allowed=(
                    self.workload
                    .maximum_estimated_cost_usd_per_full_scope_run
                ),
            )

        self._operation_call_counts[operation_hash] = operation_calls + 1
        self._operation_fallback_counts[operation_hash] = (
            fallback_calls + int(fallback_call)
        )
        self._operation_estimated_costs[operation_hash] = (
            projected_operation_cost
        )
        self._provider_calls_authorized_total += 1
        self._fallback_calls_authorized_total += int(fallback_call)
        self._estimated_cost_authorized_total = projected_full_cost
        return Gate2EconomyCallAuthorization(
            workload_class=self.workload.workload_class,
            requested_model_id=model_id,
            exact_model_id=declaration.exact_model_id,
            provider_profile_id=declaration.provider_profile_id,
            operation_identity_sha256=operation_hash,
            fallback_call=fallback_call,
            estimated_input_tokens=estimated_input_tokens,
            maximum_output_tokens=self.workload.maximum_output_tokens,
            estimated_cost_usd=_usd_text(estimated_cost),
            provider_calls_authorized_total=(
                self._provider_calls_authorized_total
            ),
            fallback_calls_authorized_total=(
                self._fallback_calls_authorized_total
            ),
            prepared_form_data=prepared,
        )

    def finalize_call(
        self,
        *,
        authorization: Gate2EconomyCallAuthorization,
        execution_metadata: Gate2ProviderExecutionMetadata,
    ) -> dict[str, Any]:
        declaration = self._model_declaration(
            model_id=authorization.exact_model_id,
            provider_profile_id=authorization.provider_profile_id,
        )
        if execution_metadata.provider_id != declaration.provider_id:
            self._block(
                "gate2_economy_execution_provider_mismatch",
                "Provider execution identity does not match economy policy",
                operation_hash=authorization.operation_identity_sha256,
            )
        if execution_metadata.resolved_model_id is None:
            self._block(
                "gate2_economy_resolved_model_missing",
                "Provider did not report the resolved economy model",
                operation_hash=authorization.operation_identity_sha256,
            )
        try:
            resolved = self.policy.resolve_model_id(
                execution_metadata.resolved_model_id
            )
        except Gate2EconomyModelPolicyError:
            self._block(
                "gate2_economy_resolved_model_forbidden",
                "Provider resolved outside the economy policy",
                operation_hash=authorization.operation_identity_sha256,
            )
        if resolved.exact_model_id != declaration.exact_model_id:
            self._block(
                "gate2_economy_resolved_model_mismatch",
                "Provider resolved a different economy model",
                operation_hash=authorization.operation_identity_sha256,
            )
        input_tokens = _required_usage(
            execution_metadata.input_tokens,
            "input_tokens",
        )
        output_tokens = _required_usage(
            execution_metadata.output_tokens,
            "output_tokens",
        )
        cached_input_tokens = _optional_usage(
            execution_metadata.cached_input_tokens,
            "cached_input_tokens",
        )
        reasoning_tokens = _optional_usage(
            execution_metadata.reasoning_tokens,
            "reasoning_tokens",
        )
        if input_tokens > self.workload.maximum_estimated_input_tokens:
            self._block(
                "gate2_economy_actual_input_token_budget_exceeded",
                "Reported economy input exceeds the workload budget",
                operation_hash=authorization.operation_identity_sha256,
                observed=input_tokens,
                allowed=self.workload.maximum_estimated_input_tokens,
            )
        if output_tokens > self.workload.maximum_output_tokens:
            self._block(
                "gate2_economy_output_token_budget_exceeded",
                "Reported economy output exceeds the workload budget",
                operation_hash=authorization.operation_identity_sha256,
                observed=output_tokens,
                allowed=self.workload.maximum_output_tokens,
            )
        if (
            cached_input_tokens is not None
            and cached_input_tokens > input_tokens
        ):
            self._block(
                "gate2_economy_cached_token_accounting_invalid",
                "Cached input tokens exceed reported input tokens",
                operation_hash=authorization.operation_identity_sha256,
            )
        if reasoning_tokens is not None and reasoning_tokens > output_tokens:
            self._block(
                "gate2_economy_reasoning_token_accounting_invalid",
                "Reasoning tokens exceed reported output tokens",
                operation_hash=authorization.operation_identity_sha256,
            )
        if (
            declaration.reasoning_policy == REASONING_DISABLED
            and reasoning_tokens not in {None, 0}
        ):
            self._block(
                "gate2_economy_reasoning_budget_exceeded",
                "Reasoning tokens are forbidden for this economy model",
                operation_hash=authorization.operation_identity_sha256,
                observed=reasoning_tokens,
                allowed=0,
            )
        actual_cost = estimate_model_cost_usd(
            declaration=declaration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens or 0,
        )
        receipt = {
            "schema_version": BUDGET_SCHEMA_VERSION,
            "status": "passed",
            "budget_status": "within_budget",
            "policy_id": self.policy.policy_id,
            "policy_version": self.policy.policy_version,
            "policy_hash": self.policy.policy_hash,
            "workload_class": self.workload.workload_class,
            "provider_id": execution_metadata.provider_id,
            "provider_profile_id": declaration.provider_profile_id,
            "requested_model_id": authorization.requested_model_id,
            "exact_model_id": declaration.exact_model_id,
            "resolved_model_id": execution_metadata.resolved_model_id,
            "operation_identity_sha256": (
                authorization.operation_identity_sha256
            ),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_input_tokens": cached_input_tokens,
            "reasoning_tokens": reasoning_tokens,
            "call_count": 1,
            "fallback_call": authorization.fallback_call,
            "provider_calls_authorized_total": (
                authorization.provider_calls_authorized_total
            ),
            "fallback_calls_authorized_total": (
                authorization.fallback_calls_authorized_total
            ),
            "estimated_input_tokens": (
                authorization.estimated_input_tokens
            ),
            "maximum_input_tokens": (
                self.workload.maximum_estimated_input_tokens
            ),
            "maximum_output_tokens": self.workload.maximum_output_tokens,
            "estimated_cost_usd": authorization.estimated_cost_usd,
            "actual_cost_usd": _usd_text(actual_cost),
            "maximum_estimated_cost_usd_per_operation": (
                self.workload.maximum_estimated_cost_usd_per_operation
            ),
            "maximum_estimated_cost_usd_per_full_scope_run": (
                self.workload
                .maximum_estimated_cost_usd_per_full_scope_run
            ),
            "reasoning_policy": declaration.reasoning_policy,
            "paid_tools_used": 0,
            "response_body_policy": self.workload.response_body_policy,
            "customer_content_in_receipt": False,
        }
        receipt["integrity_hash"] = _hash_json(receipt)
        return receipt

    def preflight_full_scope(
        self,
        *,
        model_id: str,
        provider_profile_id: str,
        default_call_input_tokens: Iterable[int],
        fallback_call_input_tokens: Iterable[int] = (),
    ) -> dict[str, Any]:
        declaration = self._model_declaration(
            model_id=model_id,
            provider_profile_id=provider_profile_id,
        )
        default_inputs = tuple(default_call_input_tokens)
        fallback_inputs = tuple(fallback_call_input_tokens)
        _validate_input_estimates(default_inputs + fallback_inputs)
        if len(fallback_inputs) > len(default_inputs):
            self._block(
                "gate2_economy_full_scope_fallback_plan_invalid",
                "Planned fallback calls exceed planned operations",
            )
        if (
            len(default_inputs) + len(fallback_inputs)
            > self.workload.maximum_provider_calls_per_full_scope_run
        ):
            self._block(
                "gate2_economy_full_scope_call_budget_exceeded",
                "Planned economy calls exceed the full-scope budget",
                observed=len(default_inputs) + len(fallback_inputs),
                allowed=(
                    self.workload
                    .maximum_provider_calls_per_full_scope_run
                ),
            )
        if fallback_inputs and (
            self.workload.maximum_fallback_calls_per_operation == 0
        ):
            self._block(
                "gate2_economy_fallback_call_budget_exceeded",
                "Fallback calls are forbidden for this workload",
            )
        observed_max = max(default_inputs + fallback_inputs, default=0)
        if observed_max > self.workload.maximum_estimated_input_tokens:
            self._block(
                "gate2_economy_input_token_budget_exceeded",
                "Planned economy input exceeds the workload budget",
                observed=observed_max,
                allowed=self.workload.maximum_estimated_input_tokens,
            )
        estimated_cost = sum(
            (
                estimate_model_cost_usd(
                    declaration=declaration,
                    input_tokens=input_tokens,
                    output_tokens=self.workload.maximum_output_tokens,
                )
                for input_tokens in default_inputs + fallback_inputs
            ),
            Decimal("0"),
        )
        maximum_cost = Decimal(
            self.workload.maximum_estimated_cost_usd_per_full_scope_run
        )
        if estimated_cost > maximum_cost:
            self._block(
                "gate2_economy_full_scope_cost_budget_exceeded",
                "Planned economy cost exceeds the full-scope budget",
                observed=_usd_text(estimated_cost),
                allowed=_usd_text(maximum_cost),
            )
        receipt = {
            "schema_version": BUDGET_SCHEMA_VERSION,
            "receipt_type": "full_scope_preflight",
            "status": "authorized",
            "budget_status": "within_budget",
            "policy_id": self.policy.policy_id,
            "policy_version": self.policy.policy_version,
            "policy_hash": self.policy.policy_hash,
            "workload_class": self.workload.workload_class,
            "provider_profile_id": declaration.provider_profile_id,
            "requested_model_id": model_id,
            "exact_model_id": declaration.exact_model_id,
            "planned_operations_total": len(default_inputs),
            "planned_provider_calls_total": (
                len(default_inputs) + len(fallback_inputs)
            ),
            "planned_fallback_calls_total": len(fallback_inputs),
            "estimated_input_tokens_total": sum(
                default_inputs + fallback_inputs
            ),
            "estimated_input_tokens_max": observed_max,
            "maximum_output_tokens_per_call": (
                self.workload.maximum_output_tokens
            ),
            "estimated_cost_usd": _usd_text(estimated_cost),
            "maximum_estimated_cost_usd_per_full_scope_run": (
                self.workload
                .maximum_estimated_cost_usd_per_full_scope_run
            ),
            "reasoning_policy": declaration.reasoning_policy,
            "paid_tools_planned": 0,
            "customer_content_in_receipt": False,
        }
        receipt["integrity_hash"] = _hash_json(receipt)
        return receipt

    def _model_declaration(
        self,
        *,
        model_id: str,
        provider_profile_id: str,
    ) -> EconomyModelDeclaration:
        declaration = self.policy.model(model_id)
        if declaration.provider_profile_id != provider_profile_id:
            _fail(
                "gate2_economy_budget_provider_model_mismatch",
                "Economy model does not belong to the selected provider",
            )
        if self.workload.workload_class not in declaration.workload_classes:
            _fail(
                "gate2_economy_model_workload_forbidden",
                "Economy model is not budgeted for this workload",
            )
        return declaration

    def _apply_request_controls(
        self,
        *,
        form_data: dict[str, Any],
        declaration: EconomyModelDeclaration,
    ) -> dict[str, Any]:
        if not isinstance(form_data, dict):
            _fail(
                "gate2_economy_request_invalid",
                "Economy request must be an object",
            )
        prepared = copy.deepcopy(form_data)
        prepared["model"] = declaration.exact_model_id
        for field in _TOOL_FIELDS:
            if (
                field in prepared
                and prepared[field] is not None
                and prepared[field] is not False
            ):
                if not (
                    field in {"tools", "functions", "plugins"}
                    and prepared[field] == []
                ):
                    _fail(
                        "gate2_economy_paid_tools_forbidden",
                        "Tools and search are forbidden for Gate 2 economy calls",
                    )
            prepared.pop(field, None)
        existing_output_cap = prepared.get("max_tokens")
        if existing_output_cap is not None:
            if (
                isinstance(existing_output_cap, bool)
                or not isinstance(existing_output_cap, int)
                or existing_output_cap <= 0
                or existing_output_cap > self.workload.maximum_output_tokens
            ):
                _fail(
                    "gate2_economy_output_token_budget_exceeded",
                    "Requested output-token cap exceeds the economy budget",
                )
        prepared["max_tokens"] = min(
            int(existing_output_cap)
            if existing_output_cap is not None
            else self.workload.maximum_output_tokens,
            self.workload.maximum_output_tokens,
        )
        for field in _REASONING_FIELDS:
            if field in prepared:
                if (
                    declaration.reasoning_policy != REASONING_MINIMAL
                    or field != "reasoning_effort"
                    or prepared[field] != "minimal"
                ):
                    _fail(
                        "gate2_economy_reasoning_policy_forbidden",
                        "Requested reasoning exceeds the economy policy",
                    )
        if declaration.reasoning_policy == REASONING_MINIMAL:
            prepared["reasoning_effort"] = "minimal"
        elif declaration.reasoning_policy == REASONING_DISABLED:
            for field in _REASONING_FIELDS:
                prepared.pop(field, None)
        metadata = prepared.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            _fail(
                "gate2_economy_request_metadata_invalid",
                "Economy request metadata must be an object",
            )
        gate2 = metadata.setdefault("broker_reports_gate2", {})
        if not isinstance(gate2, dict):
            _fail(
                "gate2_economy_request_metadata_invalid",
                "Gate 2 request metadata must be an object",
            )
        gate2["economy_budget"] = {
            "schema_version": BUDGET_SCHEMA_VERSION,
            "policy_id": self.policy.policy_id,
            "policy_version": self.policy.policy_version,
            "policy_hash": self.policy.policy_hash,
            "workload_class": self.workload.workload_class,
            "maximum_output_tokens": self.workload.maximum_output_tokens,
            "reasoning_policy": declaration.reasoning_policy,
            "paid_tools_allowed": False,
        }
        return prepared

    def _block(
        self,
        code: str,
        message: str,
        *,
        operation_hash: str | None = None,
        observed: Any = None,
        allowed: Any = None,
    ) -> None:
        receipt = {
            "schema_version": BUDGET_SCHEMA_VERSION,
            "status": "blocked",
            "budget_status": code,
            "policy_id": self.policy.policy_id,
            "policy_version": self.policy.policy_version,
            "policy_hash": self.policy.policy_hash,
            "workload_class": self.workload.workload_class,
            "operation_identity_sha256": operation_hash,
            "observed": observed,
            "allowed": allowed,
            "provider_calls_authorized_total": (
                self._provider_calls_authorized_total
            ),
            "fallback_calls_authorized_total": (
                self._fallback_calls_authorized_total
            ),
            "customer_content_in_receipt": False,
        }
        receipt["integrity_hash"] = _hash_json(receipt)
        _fail(code, message, receipt=receipt)


def estimate_gate2_request_input_tokens(form_data: dict[str, Any]) -> int:
    projection = {
        "messages": form_data.get("messages"),
        "response_format": form_data.get("response_format"),
    }
    encoded = json.dumps(
        projection,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return max(
        1,
        (len(encoded) + 3) // 4 + _TOKEN_ESTIMATOR_OVERHEAD,
    )


def estimate_model_cost_usd(
    *,
    declaration: EconomyModelDeclaration,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> Decimal:
    _validate_usage_integer(input_tokens, "input_tokens")
    _validate_usage_integer(output_tokens, "output_tokens")
    _validate_usage_integer(cached_input_tokens, "cached_input_tokens")
    if cached_input_tokens > input_tokens:
        _fail(
            "gate2_economy_cached_token_accounting_invalid",
            "Cached input tokens exceed input tokens",
        )
    try:
        input_rate = Decimal(declaration.cost.input_usd_per_million)
        output_rate = Decimal(declaration.cost.output_usd_per_million)
        cached_rate = (
            Decimal(declaration.cost.cached_input_usd_per_million)
            if declaration.cost.cached_input_usd_per_million is not None
            else input_rate
        )
    except (InvalidOperation, ValueError) as exc:
        raise Gate2SourceFactRuntimeError(
            "gate2_economy_cost_policy_invalid",
            "Economy model price cannot be parsed",
            failure_class="economy_budget",
        ) from exc
    uncached_tokens = input_tokens - cached_input_tokens
    return (
        (
            Decimal(uncached_tokens) * input_rate
            + Decimal(cached_input_tokens) * cached_rate
            + Decimal(output_tokens) * output_rate
        )
        / Decimal(1_000_000)
    ).quantize(_USD_QUANTUM, rounding=ROUND_CEILING)


def _validate_input_estimates(values: tuple[int, ...]) -> None:
    for value in values:
        _validate_usage_integer(value, "estimated_input_tokens")


def _required_usage(value: Any, field: str) -> int:
    if value is None:
        _fail(
            "gate2_economy_usage_accounting_missing",
            f"Provider did not report required {field}",
        )
    return _validate_usage_integer(value, field)


def _optional_usage(value: Any, field: str) -> int | None:
    if value is None:
        return None
    return _validate_usage_integer(value, field)


def _validate_usage_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(
            "gate2_economy_usage_accounting_invalid",
            f"Provider reported invalid {field}",
        )
    return value


def _identity_hash(value: str) -> str:
    text = str(value or "")
    if not text:
        _fail(
            "gate2_economy_operation_identity_missing",
            "Economy operation identity is required",
        )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _usd_text(value: Decimal) -> str:
    return format(
        value.quantize(_USD_QUANTUM, rounding=ROUND_CEILING),
        "f",
    )


def _hash_json(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _fail(
    code: str,
    message: str,
    *,
    receipt: dict[str, Any] | None = None,
) -> None:
    raise Gate2SourceFactRuntimeError(
        code,
        message,
        raw_output=(
            {"economy_budget_receipt": receipt}
            if receipt is not None
            else None
        ),
        failure_class="economy_budget",
    )
