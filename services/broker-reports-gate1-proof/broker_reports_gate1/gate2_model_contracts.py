from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

from .gate2_source_fact_contracts import Gate2ManagedPrompt


PROVIDER_STATUS_APPROVED = "approved"
PROVIDER_STATUS_PROBE_REQUIRED = "probe_required"
PROVIDER_STATUS_UNSUPPORTED = "unsupported"
PROVIDER_AVAILABILITY_AVAILABLE = "available"
PROVIDER_AVAILABILITY_UNAVAILABLE = "unavailable"
PROVIDER_AVAILABILITY_CONFIGURATION_BLOCKED = "configuration_blocked"
PROVIDER_SUITABILITY_RECOMMENDED = "recommended"
PROVIDER_SUITABILITY_ELIGIBLE = "eligible"
PROVIDER_SUITABILITY_NOT_RECOMMENDED = "not_recommended"


@dataclass(frozen=True)
class Gate2ProviderExecutionMetadata:
    provider_id: str
    provider_profile_id: str
    provider_profile_revision: str
    adapter_id: str
    adapter_version: str
    requested_model_id: str
    structured_output_mode: str
    response_format_type: str
    response_format_schema_mode: str | None
    transport_type: str = "openwebui_chat_completions"
    canonical_request_schema_hash: str | None = None
    adapted_request_schema_hash: str | None = None
    schema_transform_count: int = 0
    resolved_model_id: str | None = None
    provider_response_id: str | None = None
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "gate2_provider_execution_metadata_v1",
            "provider_id": self.provider_id,
            "provider_profile_id": self.provider_profile_id,
            "provider_profile_revision": self.provider_profile_revision,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "requested_model_id": self.requested_model_id,
            "resolved_model_id": self.resolved_model_id,
            "provider_response_id": self.provider_response_id,
            "structured_output_mode": self.structured_output_mode,
            "response_format_type": self.response_format_type,
            "response_format_schema_mode": self.response_format_schema_mode,
            "transport_type": self.transport_type,
            "canonical_request_schema_hash": self.canonical_request_schema_hash,
            "adapted_request_schema_hash": self.adapted_request_schema_hash,
            "schema_transform_count": self.schema_transform_count,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "finish_reason": self.finish_reason,
        }


class Gate2SourceFactRuntimeError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        raw_output: Any = None,
        execution_metadata: Gate2ProviderExecutionMetadata | None = None,
        failure_class: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.raw_output = raw_output
        self.execution_metadata = execution_metadata
        self.failure_class = failure_class


@dataclass(frozen=True)
class Gate2StructuredModelResult:
    content: Any
    structured_output_mode: str = "openwebui_response_format_json_schema"
    response_format_type: str = "json_schema"
    response_format_schema_mode: str | None = "strict_json_schema"
    fallback_used: bool = False
    repair_attempt_count: int = 0
    execution_metadata: Gate2ProviderExecutionMetadata | None = None


class Gate2StructuredModelClient(Protocol):
    def execution_contract(self, model_id: str) -> Gate2ProviderExecutionMetadata:
        ...

    async def extract(
        self,
        *,
        prompt: Gate2ManagedPrompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> Gate2StructuredModelResult:
        ...


@dataclass(frozen=True)
class Gate2ProviderProfile:
    profile_id: str
    provider_id: str
    model_family: str
    documented_output_mode: str
    supports_strict_final_json_schema: bool
    supports_strict_tool_input: bool
    supports_any_of: bool
    supports_const: bool
    supports_additional_properties_false: bool
    gate2_status: str
    adapter_id: str
    adapter_version: str
    structured_output_mode: str
    response_format_type: str
    response_format_schema_mode: str
    model_id_prefixes: tuple[str, ...]
    approved_model_ids: tuple[str, ...] = ()
    capability_status: str = PROVIDER_STATUS_UNSUPPORTED
    availability_status: str = PROVIDER_AVAILABILITY_UNAVAILABLE
    transport_type: str = "openwebui_chat_completions"
    transport_configuration: str | None = None
    extraction_suitability: str = PROVIDER_SUITABILITY_NOT_RECOMMENDED
    complex_fallback_suitability: str = PROVIDER_SUITABILITY_NOT_RECOMMENDED
    recommended_extraction_model_ids: tuple[str, ...] = ()
    recommended_fallback_model_ids: tuple[str, ...] = ()
    connection_base_url_prefixes: tuple[str, ...] = ()


GATE2_PROVIDER_PROFILES = (
    Gate2ProviderProfile(
        profile_id="openai_gpt",
        provider_id="openai",
        model_family="gpt",
        documented_output_mode="strict_final_json_schema",
        supports_strict_final_json_schema=True,
        supports_strict_tool_input=True,
        supports_any_of=True,
        supports_const=True,
        supports_additional_properties_false=True,
        gate2_status=PROVIDER_STATUS_APPROVED,
        adapter_id="openai_response_format",
        adapter_version="1.0.0",
        structured_output_mode="openwebui_response_format_json_schema",
        response_format_type="json_schema",
        response_format_schema_mode="strict_json_schema",
        model_id_prefixes=("gpt-",),
        approved_model_ids=("gpt-5.6-sol",),
        capability_status=PROVIDER_STATUS_APPROVED,
        availability_status=PROVIDER_AVAILABILITY_AVAILABLE,
        transport_type="openai_chat_completions_via_openwebui",
        transport_configuration="openwebui_openai_connection",
        extraction_suitability=PROVIDER_SUITABILITY_ELIGIBLE,
        complex_fallback_suitability=PROVIDER_SUITABILITY_RECOMMENDED,
        recommended_extraction_model_ids=("gpt-5.6-luna",),
        recommended_fallback_model_ids=("gpt-5.6-sol",),
        connection_base_url_prefixes=("https://api.openai.com",),
    ),
    Gate2ProviderProfile(
        profile_id="anthropic_claude",
        provider_id="anthropic",
        model_family="claude",
        documented_output_mode="anthropic_native_output_config_json_schema",
        supports_strict_final_json_schema=True,
        supports_strict_tool_input=True,
        supports_any_of=True,
        supports_const=True,
        supports_additional_properties_false=True,
        gate2_status=PROVIDER_STATUS_PROBE_REQUIRED,
        adapter_id="anthropic_native_messages",
        adapter_version="1.1.0",
        structured_output_mode="openwebui_anthropic_output_config_json_schema",
        response_format_type="json_schema",
        response_format_schema_mode="strict_json_schema",
        model_id_prefixes=("claude-",),
        capability_status=PROVIDER_STATUS_PROBE_REQUIRED,
        availability_status=PROVIDER_AVAILABILITY_AVAILABLE,
        transport_type="anthropic_messages_native_via_openwebui_pipe",
        transport_configuration="openwebui_provider_connection",
        extraction_suitability=PROVIDER_SUITABILITY_RECOMMENDED,
        complex_fallback_suitability=PROVIDER_SUITABILITY_RECOMMENDED,
        recommended_extraction_model_ids=("claude-haiku-4-5-20251001",),
        recommended_fallback_model_ids=("claude-sonnet-5",),
        connection_base_url_prefixes=("https://api.anthropic.com",),
    ),
    Gate2ProviderProfile(
        profile_id="google_gemini",
        provider_id="google",
        model_family="gemini",
        documented_output_mode="json_schema_structural_projection",
        supports_strict_final_json_schema=True,
        supports_strict_tool_input=False,
        supports_any_of=True,
        supports_const=False,
        supports_additional_properties_false=True,
        gate2_status=PROVIDER_STATUS_APPROVED,
        adapter_id="gemini_response_format",
        adapter_version="1.5.0",
        structured_output_mode="openwebui_response_format_json_schema",
        response_format_type="json_schema",
        response_format_schema_mode="strict_json_schema",
        model_id_prefixes=("models/gemini-",),
        approved_model_ids=("models/gemini-3.5-flash",),
        capability_status=PROVIDER_STATUS_APPROVED,
        availability_status=PROVIDER_AVAILABILITY_AVAILABLE,
        transport_type="gemini_openai_compatibility_via_openwebui",
        transport_configuration="openwebui_gemini_connection",
        extraction_suitability=PROVIDER_SUITABILITY_RECOMMENDED,
        complex_fallback_suitability=PROVIDER_SUITABILITY_ELIGIBLE,
        recommended_extraction_model_ids=("models/gemini-3.5-flash",),
        recommended_fallback_model_ids=("models/gemini-3.1-pro-preview",),
        connection_base_url_prefixes=(
            "https://generativelanguage.googleapis.com",
        ),
    ),
    Gate2ProviderProfile(
        profile_id="deepseek",
        provider_id="deepseek",
        model_family="deepseek",
        documented_output_mode="json_object",
        supports_strict_final_json_schema=False,
        supports_strict_tool_input=True,
        supports_any_of=True,
        supports_const=False,
        supports_additional_properties_false=True,
        gate2_status=PROVIDER_STATUS_UNSUPPORTED,
        adapter_id="openai_response_format",
        adapter_version="1.0.0",
        structured_output_mode="openwebui_response_format_json_schema",
        response_format_type="json_schema",
        response_format_schema_mode="strict_json_schema",
        model_id_prefixes=("deepseek-",),
    ),
    Gate2ProviderProfile(
        profile_id="zai_glm",
        provider_id="zai",
        model_family="glm",
        documented_output_mode="json_object",
        supports_strict_final_json_schema=False,
        supports_strict_tool_input=False,
        supports_any_of=False,
        supports_const=False,
        supports_additional_properties_false=False,
        gate2_status=PROVIDER_STATUS_UNSUPPORTED,
        adapter_id="openai_response_format",
        adapter_version="1.0.0",
        structured_output_mode="openwebui_response_format_json_schema",
        response_format_type="json_schema",
        response_format_schema_mode="strict_json_schema",
        model_id_prefixes=("glm-",),
    ),
    Gate2ProviderProfile(
        profile_id="alibaba_qwen",
        provider_id="alibaba_model_studio",
        model_family="qwen",
        documented_output_mode="json_object",
        supports_strict_final_json_schema=False,
        supports_strict_tool_input=False,
        supports_any_of=False,
        supports_const=False,
        supports_additional_properties_false=False,
        gate2_status=PROVIDER_STATUS_UNSUPPORTED,
        adapter_id="openai_response_format",
        adapter_version="1.0.0",
        structured_output_mode="openwebui_response_format_json_schema",
        response_format_type="json_schema",
        response_format_schema_mode="strict_json_schema",
        model_id_prefixes=("qwen-",),
    ),
)


_PROVIDER_PROFILE_ALIASES = {
    "gpt": "openai_gpt",
    "openai": "openai_gpt",
    "claude": "anthropic_claude",
    "anthropic": "anthropic_claude",
    "gemini": "google_gemini",
    "google": "google_gemini",
    "deepseek": "deepseek",
    "z.ai": "zai_glm",
    "zai": "zai_glm",
    "glm": "zai_glm",
    "qwen": "alibaba_qwen",
    "alibaba": "alibaba_qwen",
    "alibaba_model_studio": "alibaba_qwen",
}


def gate2_provider_profile(profile_id: str) -> Gate2ProviderProfile:
    normalized = str(profile_id or "").strip().lower()
    canonical = _PROVIDER_PROFILE_ALIASES.get(normalized, normalized)
    for profile in GATE2_PROVIDER_PROFILES:
        if profile.profile_id == canonical:
            return profile
    raise Gate2SourceFactRuntimeError(
        "gate2_provider_profile_unknown",
        "Unknown Gate 2 provider profile",
    )


def gate2_provider_profile_revision(profile: Gate2ProviderProfile) -> str:
    material = {
        "profile_id": profile.profile_id,
        "provider_id": profile.provider_id,
        "model_family": profile.model_family,
        "documented_output_mode": profile.documented_output_mode,
        "supports_strict_final_json_schema": profile.supports_strict_final_json_schema,
        "supports_strict_tool_input": profile.supports_strict_tool_input,
        "supports_any_of": profile.supports_any_of,
        "supports_const": profile.supports_const,
        "supports_additional_properties_false": profile.supports_additional_properties_false,
        "gate2_status": profile.gate2_status,
        "adapter_id": profile.adapter_id,
        "adapter_version": profile.adapter_version,
        "structured_output_mode": profile.structured_output_mode,
        "response_format_type": profile.response_format_type,
        "response_format_schema_mode": profile.response_format_schema_mode,
        "model_id_prefixes": list(profile.model_id_prefixes),
        "approved_model_ids": list(profile.approved_model_ids),
        "capability_status": profile.capability_status,
        "availability_status": profile.availability_status,
        "transport_type": profile.transport_type,
        "transport_configuration": profile.transport_configuration,
        "extraction_suitability": profile.extraction_suitability,
        "complex_fallback_suitability": profile.complex_fallback_suitability,
        "recommended_extraction_model_ids": list(
            profile.recommended_extraction_model_ids
        ),
        "recommended_fallback_model_ids": list(
            profile.recommended_fallback_model_ids
        ),
        "connection_base_url_prefixes": list(
            profile.connection_base_url_prefixes
        ),
    }
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()


def gate2_model_qualification_status(
    profile: Gate2ProviderProfile, model_id: str
) -> str:
    if profile.gate2_status == PROVIDER_STATUS_UNSUPPORTED:
        return PROVIDER_STATUS_UNSUPPORTED
    if profile.model_id_prefixes and not model_id.startswith(profile.model_id_prefixes):
        return PROVIDER_STATUS_UNSUPPORTED
    if profile.gate2_status == PROVIDER_STATUS_PROBE_REQUIRED:
        return PROVIDER_STATUS_PROBE_REQUIRED
    if profile.approved_model_ids and model_id not in profile.approved_model_ids:
        return PROVIDER_STATUS_PROBE_REQUIRED
    return PROVIDER_STATUS_APPROVED


def gate2_resolved_model_matches_requested(
    requested_model_id: str,
    resolved_model_id: str,
) -> bool:
    return resolved_model_id == requested_model_id or resolved_model_id.startswith(
        f"{requested_model_id}-"
    )


def gate2_model_execution_contract(
    model_client: Any, model_id: str
) -> Gate2ProviderExecutionMetadata:
    resolver = getattr(model_client, "execution_contract", None)
    if not callable(resolver):
        raise Gate2SourceFactRuntimeError(
            "gate2_provider_execution_contract_missing",
            "Structured model client must expose provider execution metadata",
        )
    value = resolver(model_id)
    if not isinstance(value, Gate2ProviderExecutionMetadata):
        raise Gate2SourceFactRuntimeError(
            "gate2_provider_execution_contract_invalid",
            "Structured model client returned invalid provider execution metadata",
        )
    return value


def gate2_provider_execution_safe_metadata(
    metadata: Gate2ProviderExecutionMetadata,
) -> dict[str, Any]:
    snapshot = metadata.snapshot()
    requested_model_id = _safe_execution_identifier(
        snapshot.get("requested_model_id"),
        max_length=256,
    )
    resolved_model_id = _safe_execution_identifier(
        snapshot.get("resolved_model_id"),
        max_length=256,
    )
    resolved_model_allowed = bool(
        requested_model_id
        and resolved_model_id
        and gate2_resolved_model_matches_requested(
            requested_model_id,
            resolved_model_id,
        )
    )
    snapshot["requested_model_id"] = requested_model_id
    snapshot["requested_model_id_redacted"] = bool(
        metadata.requested_model_id and requested_model_id is None
    )
    snapshot["resolved_model_id"] = (
        resolved_model_id if resolved_model_allowed else None
    )
    snapshot["resolved_model_id_redacted"] = bool(
        metadata.resolved_model_id and not resolved_model_allowed
    )
    snapshot["finish_reason"] = _safe_execution_identifier(
        snapshot.get("finish_reason"),
        max_length=64,
    )
    for field in (
        "canonical_request_schema_hash",
        "adapted_request_schema_hash",
    ):
        snapshot[field] = _safe_sha256(snapshot.get(field))
    transform_count = snapshot.get("schema_transform_count")
    snapshot["schema_transform_count"] = (
        transform_count
        if isinstance(transform_count, int)
        and not isinstance(transform_count, bool)
        and transform_count >= 0
        else None
    )
    for field in (
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ):
        value = snapshot.get(field)
        snapshot[field] = (
            value
            if isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
            else None
        )
    response_id = snapshot.pop("provider_response_id", None)
    snapshot["provider_response_id_present"] = bool(response_id)
    snapshot["provider_response_id_sha256"] = (
        hashlib.sha256(str(response_id).encode("utf-8")).hexdigest()
        if response_id
        else None
    )
    return snapshot


def gate2_provider_execution_summary(
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    call_status_counts: Counter[str] = Counter()
    error_code_counts: Counter[str] = Counter()
    failure_class_counts: Counter[str] = Counter()
    provider_profile_counts: Counter[str] = Counter()
    adapter_counts: Counter[str] = Counter()
    transport_type_counts: Counter[str] = Counter()
    requested_model_counts: Counter[str] = Counter()
    resolved_model_counts: Counter[str] = Counter()
    adapted_schema_hash_counts: Counter[str] = Counter()
    input_tokens_total = 0
    output_tokens_total = 0
    total_tokens_total = 0
    usage_reported_attempts = 0
    latency_values: list[int] = []
    schema_transform_total = 0
    for attempt in attempts:
        execution = attempt.get("provider_execution_safe")
        if not isinstance(execution, dict):
            execution = attempt.get("provider_execution")
        execution = execution if isinstance(execution, dict) else {}
        call_status_counts[str(attempt.get("model_call_status") or "unknown")] += 1
        if attempt.get("error_code"):
            error_code_counts[str(attempt["error_code"])] += 1
        if attempt.get("failure_class"):
            failure_class_counts[str(attempt["failure_class"])] += 1
        for counter, field in (
            (provider_profile_counts, "provider_profile_id"),
            (adapter_counts, "adapter_id"),
            (transport_type_counts, "transport_type"),
            (requested_model_counts, "requested_model_id"),
            (resolved_model_counts, "resolved_model_id"),
            (adapted_schema_hash_counts, "adapted_request_schema_hash"),
        ):
            if execution.get(field):
                counter[str(execution[field])] += 1
        token_values = [
            execution.get("input_tokens"),
            execution.get("output_tokens"),
            execution.get("total_tokens"),
        ]
        if any(isinstance(value, int) for value in token_values):
            usage_reported_attempts += 1
        if isinstance(token_values[0], int):
            input_tokens_total += token_values[0]
        if isinstance(token_values[1], int):
            output_tokens_total += token_values[1]
        if isinstance(token_values[2], int):
            total_tokens_total += token_values[2]
        if isinstance(execution.get("duration_ms"), int):
            latency_values.append(int(execution["duration_ms"]))
        if isinstance(execution.get("schema_transform_count"), int):
            schema_transform_total += int(execution["schema_transform_count"])
    return {
        "schema_version": "gate2_provider_execution_summary_v1",
        "attempts_total": len(attempts),
        "call_status_counts": dict(sorted(call_status_counts.items())),
        "error_code_counts": dict(sorted(error_code_counts.items())),
        "failure_class_counts": dict(sorted(failure_class_counts.items())),
        "provider_profile_counts": dict(sorted(provider_profile_counts.items())),
        "adapter_counts": dict(sorted(adapter_counts.items())),
        "transport_type_counts": dict(sorted(transport_type_counts.items())),
        "requested_model_counts": dict(sorted(requested_model_counts.items())),
        "resolved_model_counts": dict(sorted(resolved_model_counts.items())),
        "adapted_schema_hash_counts": dict(
            sorted(adapted_schema_hash_counts.items())
        ),
        "schema_transform_total": schema_transform_total,
        "usage_reported_attempts": usage_reported_attempts,
        "usage_unreported_attempts": len(attempts) - usage_reported_attempts,
        "input_tokens_total": input_tokens_total,
        "output_tokens_total": output_tokens_total,
        "total_tokens_total": total_tokens_total,
        "latency_observed_attempts": len(latency_values),
        "latency_total_ms": sum(latency_values),
        "latency_max_ms": max(latency_values) if latency_values else None,
    }


def _safe_execution_identifier(value: Any, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > max_length or not text.isascii():
        return None
    allowed_punctuation = "._:/-"
    if not all(character.isalnum() or character in allowed_punctuation for character in text):
        return None
    return text


def _safe_sha256(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if len(normalized) != 64:
        return None
    if not all(character in "0123456789abcdef" for character in normalized):
        return None
    return normalized


@dataclass(frozen=True)
class Gate2StructuredModelClientConfig:
    request_profile: str
    provider_profile_id: str = "openai_gpt"
    transport: str = "openwebui"
    capability_probe: bool = False
