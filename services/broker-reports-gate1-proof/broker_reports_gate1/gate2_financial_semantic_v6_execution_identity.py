from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_semantic_v6_choice import (
    Gate2FinancialSemanticV6ChoiceContract,
)
from .gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)


V6_EXECUTION_IDENTITY_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_execution_identity_v1"
)
V6_EXECUTION_IDENTITY_POLICY_VERSION = (
    "broker_reports_gate2_candidate_records_by_construction_v1"
)
V6_QUALIFICATION_REQUEST_PROFILE = "financial_semantic_v6_qualification_v1"
V6_EXACT_MODEL_ID = "gpt-5.4-nano-2026-03-17"
V6_PROVIDER_PROFILE_ID = "openai_gpt"
V6_RESPONSE_FORMAT_NAME = "broker_reports_gate2_financial_semantic_choice_v6"

FAILURE_CLASS_BY_STAGE = {
    "provider_execution_identity": "provider_metadata_defect",
    "provider_schema": "schema_defect",
    "model_decision": "model_decision_defect",
    "canonical_validation": "validator_defect",
    "materialization": "materializer_defect",
}

FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6ExecutionIdentityFactory.create is the only "
    "captured-provider-metadata admission boundary for V6 qualification"
)
FORBIDDEN = (
    "The V6 execution identity boundary must not conflate a canonical schema "
    "hash with a full response-format hash, infer missing provider metadata, "
    "repair an identity mismatch, call a provider, fallback or retry"
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_COST_RE = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")


class Gate2FinancialSemanticV6ExecutionIdentityError(ValueError):
    def __init__(self, code: str, *, failure_class: str) -> None:
        super().__init__(code)
        self.code = code
        self.failure_class = failure_class


@dataclass(frozen=True)
class Gate2FinancialSemanticV6CapturedExecution:
    request_profile: str
    response_format_hash: str
    execution_metadata: Gate2ProviderExecutionMetadata
    actual_cost_usd: str


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ExecutionIdentity:
    schema_version: str
    policy_version: str
    request_profile: str
    provider_id: str
    provider_profile_id: str
    provider_route_revision: str
    adapter_id: str
    adapter_version: str
    transport_type: str
    structured_output_mode: str
    response_format_type: str
    response_format_schema_mode: str
    response_format_hash: str
    canonical_request_schema_hash: str
    adapted_request_schema_hash: str
    schema_transform_count: int
    requested_model_id: str
    resolved_model_id: str
    provider_response_id: str
    duration_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    actual_cost_usd: str
    finish_reason: str | None
    provider_metadata_status: str
    integrity_hash: str

    def to_private_dict(self) -> dict[str, Any]:
        return {
            **_identity_payload_without_integrity(self),
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "request_profile": self.request_profile,
            "provider_profile_id": self.provider_profile_id,
            "provider_route_revision": self.provider_route_revision,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "transport_type": self.transport_type,
            "structured_output_mode": self.structured_output_mode,
            "response_format_type": self.response_format_type,
            "response_format_schema_mode": self.response_format_schema_mode,
            "response_format_hash": self.response_format_hash,
            "canonical_request_schema_hash": (self.canonical_request_schema_hash),
            "adapted_request_schema_hash": self.adapted_request_schema_hash,
            "schema_transform_count": self.schema_transform_count,
            "requested_model_id": self.requested_model_id,
            "resolved_model_id": self.resolved_model_id,
            "provider_response_id_hash": sha256_json(self.provider_response_id),
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "actual_cost_usd": self.actual_cost_usd,
            "provider_metadata_status": self.provider_metadata_status,
            "execution_identity_dry_proof": "PASSED",
            "false_provider_identity_rejection_total": 0,
            "provider_calls_total": 0,
            "integrity_hash": self.integrity_hash,
        }


class Gate2FinancialSemanticV6ExecutionIdentityFactory:
    def create(
        self,
        *,
        capture: Gate2FinancialSemanticV6CapturedExecution,
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    ) -> Gate2FinancialSemanticV6ExecutionIdentity:
        return self._build(
            capture=capture,
            choice_contract=choice_contract,
        )

    def _build(
        self,
        *,
        capture: Gate2FinancialSemanticV6CapturedExecution,
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    ) -> Gate2FinancialSemanticV6ExecutionIdentity:
        if not isinstance(
            capture,
            Gate2FinancialSemanticV6CapturedExecution,
        ):
            _provider_fail("financial_semantic_v6_execution_capture_invalid")
        if not isinstance(
            choice_contract,
            Gate2FinancialSemanticV6ChoiceContract,
        ):
            _schema_fail("financial_semantic_v6_choice_contract_invalid")
        profile = gate2_provider_profile(V6_PROVIDER_PROFILE_ID)
        expected_route_revision = gate2_provider_profile_revision(profile)
        expected_response_format = financial_semantic_v6_response_format(
            choice_contract
        )
        expected_response_format_hash = sha256_json(expected_response_format)
        metadata = capture.execution_metadata
        if not isinstance(metadata, Gate2ProviderExecutionMetadata):
            _provider_fail("financial_semantic_v6_provider_metadata_invalid")
        if (
            capture.request_profile != V6_QUALIFICATION_REQUEST_PROFILE
            or metadata.provider_id != profile.provider_id
            or metadata.provider_profile_id != profile.profile_id
            or metadata.provider_profile_revision != expected_route_revision
            or metadata.adapter_id != profile.adapter_id
            or metadata.adapter_version != profile.adapter_version
            or metadata.transport_type != profile.transport_type
            or metadata.structured_output_mode != profile.structured_output_mode
            or metadata.response_format_type != profile.response_format_type
            or metadata.response_format_schema_mode
            != profile.response_format_schema_mode
        ):
            _provider_fail("financial_semantic_v6_provider_execution_identity_mismatch")
        if (
            _HASH_RE.fullmatch(capture.response_format_hash) is None
            or capture.response_format_hash != expected_response_format_hash
            or metadata.canonical_request_schema_hash
            != choice_contract.choice_schema_hash
            or metadata.adapted_request_schema_hash
            != choice_contract.choice_schema_hash
            or metadata.schema_transform_count != 0
        ):
            _schema_fail("financial_semantic_v6_provider_schema_identity_mismatch")
        if (
            metadata.requested_model_id != V6_EXACT_MODEL_ID
            or metadata.resolved_model_id != V6_EXACT_MODEL_ID
        ):
            _provider_fail("financial_semantic_v6_provider_model_identity_mismatch")
        normalized_usage = _normalized_usage(metadata)
        normalized_cost = _normalized_cost(capture.actual_cost_usd)
        response_id = metadata.provider_response_id
        if not isinstance(response_id, str) or not response_id.strip():
            _provider_fail("financial_semantic_v6_provider_response_id_invalid")
        finish_reason = metadata.finish_reason
        if finish_reason is not None and (
            not isinstance(finish_reason, str) or not finish_reason.strip()
        ):
            _provider_fail("financial_semantic_v6_finish_reason_invalid")
        material = {
            "schema_version": V6_EXECUTION_IDENTITY_SCHEMA_VERSION,
            "policy_version": V6_EXECUTION_IDENTITY_POLICY_VERSION,
            "request_profile": capture.request_profile,
            "provider_id": metadata.provider_id,
            "provider_profile_id": metadata.provider_profile_id,
            "provider_route_revision": metadata.provider_profile_revision,
            "adapter_id": metadata.adapter_id,
            "adapter_version": metadata.adapter_version,
            "transport_type": metadata.transport_type,
            "structured_output_mode": metadata.structured_output_mode,
            "response_format_type": metadata.response_format_type,
            "response_format_schema_mode": (metadata.response_format_schema_mode),
            "response_format_hash": capture.response_format_hash,
            "canonical_request_schema_hash": (metadata.canonical_request_schema_hash),
            "adapted_request_schema_hash": (metadata.adapted_request_schema_hash),
            "schema_transform_count": metadata.schema_transform_count,
            "requested_model_id": metadata.requested_model_id,
            "resolved_model_id": metadata.resolved_model_id,
            "provider_response_id": response_id,
            "duration_ms": normalized_usage["duration_ms"],
            "input_tokens": normalized_usage["input_tokens"],
            "output_tokens": normalized_usage["output_tokens"],
            "total_tokens": normalized_usage["total_tokens"],
            "cached_input_tokens": normalized_usage["cached_input_tokens"],
            "reasoning_tokens": normalized_usage["reasoning_tokens"],
            "actual_cost_usd": normalized_cost,
            "finish_reason": finish_reason,
            "provider_metadata_status": "verified",
        }
        return Gate2FinancialSemanticV6ExecutionIdentity(
            schema_version=V6_EXECUTION_IDENTITY_SCHEMA_VERSION,
            policy_version=V6_EXECUTION_IDENTITY_POLICY_VERSION,
            request_profile=capture.request_profile,
            provider_id=metadata.provider_id,
            provider_profile_id=metadata.provider_profile_id,
            provider_route_revision=metadata.provider_profile_revision,
            adapter_id=metadata.adapter_id,
            adapter_version=metadata.adapter_version,
            transport_type=metadata.transport_type,
            structured_output_mode=metadata.structured_output_mode,
            response_format_type=metadata.response_format_type,
            response_format_schema_mode=(metadata.response_format_schema_mode),
            response_format_hash=capture.response_format_hash,
            canonical_request_schema_hash=(metadata.canonical_request_schema_hash),
            adapted_request_schema_hash=(metadata.adapted_request_schema_hash),
            schema_transform_count=metadata.schema_transform_count,
            requested_model_id=metadata.requested_model_id,
            resolved_model_id=metadata.resolved_model_id,
            provider_response_id=response_id,
            duration_ms=normalized_usage["duration_ms"],
            input_tokens=normalized_usage["input_tokens"],
            output_tokens=normalized_usage["output_tokens"],
            total_tokens=normalized_usage["total_tokens"],
            cached_input_tokens=normalized_usage["cached_input_tokens"],
            reasoning_tokens=normalized_usage["reasoning_tokens"],
            actual_cost_usd=normalized_cost,
            finish_reason=finish_reason,
            provider_metadata_status="verified",
            integrity_hash=sha256_json(material),
        )


def financial_semantic_v6_response_format(
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
) -> dict[str, Any]:
    if not isinstance(
        choice_contract,
        Gate2FinancialSemanticV6ChoiceContract,
    ):
        _schema_fail("financial_semantic_v6_choice_contract_invalid")
    schema = choice_contract.canonical_schema()
    if sha256_json(schema) != choice_contract.choice_schema_hash:
        _schema_fail("financial_semantic_v6_choice_schema_integrity_invalid")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": V6_RESPONSE_FORMAT_NAME,
            "strict": True,
            "schema": schema,
        },
    }


def classify_financial_semantic_v6_qualification_failure(stage: str) -> str:
    failure_class = FAILURE_CLASS_BY_STAGE.get(stage)
    if failure_class is None:
        raise Gate2FinancialSemanticV6ExecutionIdentityError(
            "financial_semantic_v6_qualification_stage_unknown",
            failure_class="harness_contract_defect",
        )
    return failure_class


def validate_financial_semantic_v6_execution_identity(
    *,
    identity: Gate2FinancialSemanticV6ExecutionIdentity,
    capture: Gate2FinancialSemanticV6CapturedExecution,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
) -> None:
    if not isinstance(
        identity,
        Gate2FinancialSemanticV6ExecutionIdentity,
    ):
        _provider_fail("financial_semantic_v6_execution_identity_invalid")
    expected = Gate2FinancialSemanticV6ExecutionIdentityFactory()._build(
        capture=capture,
        choice_contract=choice_contract,
    )
    if identity != expected:
        _provider_fail("financial_semantic_v6_execution_identity_tampered")


def _normalized_usage(
    metadata: Gate2ProviderExecutionMetadata,
) -> dict[str, int]:
    values = {
        "duration_ms": metadata.duration_ms,
        "input_tokens": metadata.input_tokens,
        "output_tokens": metadata.output_tokens,
        "total_tokens": metadata.total_tokens,
        "cached_input_tokens": (
            0 if metadata.cached_input_tokens is None else metadata.cached_input_tokens
        ),
        "reasoning_tokens": (
            0 if metadata.reasoning_tokens is None else metadata.reasoning_tokens
        ),
    }
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in values.values()
    ):
        _provider_fail("financial_semantic_v6_provider_usage_invalid")
    if (
        values["total_tokens"] != values["input_tokens"] + values["output_tokens"]
        or values["cached_input_tokens"] > values["input_tokens"]
        or values["reasoning_tokens"] > values["output_tokens"]
    ):
        _provider_fail("financial_semantic_v6_provider_usage_inconsistent")
    return values


def _normalized_cost(value: Any) -> str:
    if not isinstance(value, str) or _COST_RE.fullmatch(value) is None:
        _provider_fail("financial_semantic_v6_provider_cost_invalid")
    try:
        cost = Decimal(value)
    except InvalidOperation:
        _provider_fail("financial_semantic_v6_provider_cost_invalid")
    if not cost.is_finite() or cost < 0:
        _provider_fail("financial_semantic_v6_provider_cost_invalid")
    return format(cost, "f")


def _identity_payload_without_integrity(
    identity: Gate2FinancialSemanticV6ExecutionIdentity,
) -> dict[str, Any]:
    payload = copy.deepcopy(identity.__dict__)
    payload.pop("integrity_hash", None)
    return payload


def _provider_fail(code: str) -> None:
    raise Gate2FinancialSemanticV6ExecutionIdentityError(
        code,
        failure_class="provider_metadata_defect",
    )


def _schema_fail(code: str) -> None:
    raise Gate2FinancialSemanticV6ExecutionIdentityError(
        code,
        failure_class="schema_defect",
    )
