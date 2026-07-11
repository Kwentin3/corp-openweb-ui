from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from .gate2_model_contracts import (
    PROVIDER_STATUS_APPROVED,
    PROVIDER_STATUS_PROBE_REQUIRED,
    Gate2ProviderExecutionMetadata,
    Gate2ProviderProfile,
    Gate2SourceFactRuntimeError,
    gate2_model_qualification_status,
    gate2_provider_profile_revision,
    gate2_resolved_model_matches_requested,
)


FACTORY_REQUIRED = (
    "Gate2ProviderAdapterFactory.create is the only production Gate 2 provider adapter entrypoint"
)
FORBIDDEN = (
    "Provider adapters must not call provider SDKs or HTTP endpoints; execution remains inside OpenWebUI"
)


@dataclass(frozen=True)
class Gate2PreparedProviderRequest:
    form_data: dict[str, Any]
    canonical_schema_hash: str
    adapted_schema_hash: str
    schema_transform_count: int


class Gate2ProviderAdapter(Protocol):
    profile: Gate2ProviderProfile

    def validate_model(self, model_id: str) -> None:
        ...

    def execution_contract(self, model_id: str) -> Gate2ProviderExecutionMetadata:
        ...

    def validate_execution_metadata(
        self,
        metadata: Gate2ProviderExecutionMetadata,
    ) -> None:
        ...

    def prepare_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest:
        ...

    def extract_content(self, payload: dict[str, Any]) -> Any:
        ...

    def execution_metadata(
        self,
        *,
        payload: dict[str, Any] | None,
        requested_model_id: str,
        duration_ms: int | None,
        prepared_request: Gate2PreparedProviderRequest,
    ) -> Gate2ProviderExecutionMetadata:
        ...


class Gate2ProviderAdapterFactory:
    def __init__(
        self,
        *,
        profile: Gate2ProviderProfile,
        capability_probe: bool = False,
    ) -> None:
        self.profile = profile
        self.capability_probe = capability_probe

    def create(self) -> Gate2ProviderAdapter:
        adapter_type = _PROVIDER_ADAPTER_TYPES.get(self.profile.adapter_id)
        if adapter_type is None:
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_adapter_unknown",
                "Gate 2 provider adapter is not registered",
            )
        return adapter_type(
            profile=self.profile,
            capability_probe=self.capability_probe,
        )


class _Gate2OpenWebUIProviderAdapter:
    def __init__(
        self,
        *,
        profile: Gate2ProviderProfile,
        capability_probe: bool,
    ) -> None:
        self.profile = profile
        self.capability_probe = capability_probe

    def validate_model(self, model_id: str) -> None:
        status = gate2_model_qualification_status(self.profile, model_id)
        if status != PROVIDER_STATUS_APPROVED and not (
            status == PROVIDER_STATUS_PROBE_REQUIRED and self.capability_probe
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_no_strict_structured_provider_available",
                "Selected provider model is not approved for strict Gate 2 output",
            )

    def execution_contract(self, model_id: str) -> Gate2ProviderExecutionMetadata:
        return Gate2ProviderExecutionMetadata(
            provider_id=self.profile.provider_id,
            provider_profile_id=self.profile.profile_id,
            provider_profile_revision=gate2_provider_profile_revision(self.profile),
            adapter_id=self.profile.adapter_id,
            adapter_version=self.profile.adapter_version,
            requested_model_id=model_id,
            structured_output_mode=self.profile.structured_output_mode,
            response_format_type=self.profile.response_format_type,
            response_format_schema_mode=self.profile.response_format_schema_mode,
        )

    def validate_execution_metadata(
        self,
        metadata: Gate2ProviderExecutionMetadata,
    ) -> None:
        resolved_model_id = metadata.resolved_model_id
        if resolved_model_id is None:
            return
        if not gate2_resolved_model_matches_requested(
            metadata.requested_model_id,
            resolved_model_id,
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_resolved_model_mismatch",
                "Provider-reported model does not match the requested model",
                raw_output={
                    "requested_model_id": metadata.requested_model_id,
                    "resolved_model_id": resolved_model_id,
                },
                execution_metadata=metadata,
                failure_class="provider_model_mismatch",
            )

    def prepare_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest:
        canonical_json_schema = self._strict_schema(response_format)
        canonical_schema = canonical_json_schema["schema"]
        prepared = copy.deepcopy(form_data)
        adapted_response_format = copy.deepcopy(response_format)
        adapted_json_schema = self._strict_schema(adapted_response_format)
        schema_transform_count = self._adapt_schema(adapted_json_schema["schema"])
        prepared["response_format"] = adapted_response_format
        self._annotate(prepared)
        return Gate2PreparedProviderRequest(
            form_data=prepared,
            canonical_schema_hash=_schema_hash(canonical_schema),
            adapted_schema_hash=_schema_hash(adapted_json_schema["schema"]),
            schema_transform_count=schema_transform_count,
        )

    def extract_content(self, payload: dict[str, Any]) -> Any:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = (
                first.get("message")
                if isinstance(first.get("message"), dict)
                else {}
            )
            content = message.get("content")
            if isinstance(content, (str, dict)):
                return content
            if isinstance(first.get("text"), (str, dict)):
                return first["text"]
        for field in ("content", "response"):
            if isinstance(payload.get(field), (str, dict)):
                return payload[field]
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            "Provider response has no structured content",
            raw_output=payload,
        )

    def execution_metadata(
        self,
        *,
        payload: dict[str, Any] | None,
        requested_model_id: str,
        duration_ms: int | None,
        prepared_request: Gate2PreparedProviderRequest,
    ) -> Gate2ProviderExecutionMetadata:
        value = payload if isinstance(payload, dict) else {}
        usage = value.get("usage") if isinstance(value.get("usage"), dict) else {}
        choices = value.get("choices") if isinstance(value.get("choices"), list) else []
        first = choices[0] if choices and isinstance(choices[0], dict) else {}
        return Gate2ProviderExecutionMetadata(
            provider_id=self.profile.provider_id,
            provider_profile_id=self.profile.profile_id,
            provider_profile_revision=gate2_provider_profile_revision(self.profile),
            adapter_id=self.profile.adapter_id,
            adapter_version=self.profile.adapter_version,
            requested_model_id=requested_model_id,
            resolved_model_id=_optional_string(value.get("model")),
            provider_response_id=_optional_string(value.get("id")),
            structured_output_mode=self.profile.structured_output_mode,
            response_format_type=self.profile.response_format_type,
            response_format_schema_mode=self.profile.response_format_schema_mode,
            canonical_request_schema_hash=(
                prepared_request.canonical_schema_hash
            ),
            adapted_request_schema_hash=prepared_request.adapted_schema_hash,
            schema_transform_count=prepared_request.schema_transform_count,
            duration_ms=duration_ms,
            input_tokens=_optional_int(
                usage.get("prompt_tokens", usage.get("input_tokens"))
            ),
            output_tokens=_optional_int(
                usage.get("completion_tokens", usage.get("output_tokens"))
            ),
            total_tokens=_optional_int(usage.get("total_tokens")),
            finish_reason=_optional_string(first.get("finish_reason")),
        )

    def _adapt_schema(self, schema: dict[str, Any]) -> int:
        return 0

    def _annotate(self, form_data: dict[str, Any]) -> None:
        metadata = form_data.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            form_data["metadata"] = metadata
        gate2 = metadata.setdefault("broker_reports_gate2", {})
        if not isinstance(gate2, dict):
            gate2 = {}
            metadata["broker_reports_gate2"] = gate2
        gate2.update(
            {
                "provider_profile_id": self.profile.profile_id,
                "provider_adapter_id": self.profile.adapter_id,
                "provider_adapter_version": self.profile.adapter_version,
                "structured_output_mode": self.profile.structured_output_mode,
            }
        )

    @staticmethod
    def _strict_schema(response_format: dict[str, Any]) -> dict[str, Any]:
        json_schema = (
            response_format.get("json_schema")
            if isinstance(response_format, dict)
            else None
        )
        if (
            not isinstance(response_format, dict)
            or response_format.get("type") != "json_schema"
            or not isinstance(json_schema, dict)
            or json_schema.get("strict") is not True
            or not isinstance(json_schema.get("schema"), dict)
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_strict_structured_output_required",
                "Gate 2 requires provider-native strict JSON Schema output",
            )
        return json_schema


class Gate2OpenAIResponseFormatAdapter(_Gate2OpenWebUIProviderAdapter):
    pass


class Gate2GeminiResponseFormatAdapter(_Gate2OpenWebUIProviderAdapter):
    def _adapt_schema(self, schema: dict[str, Any]) -> int:
        return _project_gemini_structural_schema(schema)


_PROVIDER_ADAPTER_TYPES = {
    "openai_response_format": Gate2OpenAIResponseFormatAdapter,
    "gemini_response_format": Gate2GeminiResponseFormatAdapter,
}


_SCHEMA_MAP_KEYWORDS = (
    "$defs",
    "definitions",
    "dependentSchemas",
    "patternProperties",
    "properties",
)
_SCHEMA_SINGLE_KEYWORDS = (
    "additionalProperties",
    "contains",
    "contentSchema",
    "else",
    "if",
    "items",
    "not",
    "propertyNames",
    "then",
    "unevaluatedItems",
    "unevaluatedProperties",
)
_SCHEMA_ARRAY_KEYWORDS = (
    "allOf",
    "anyOf",
    "oneOf",
    "prefixItems",
)
_GEMINI_REMOVED_SCHEMA_KEYWORDS = (
    "$comment",
    "const",
    "default",
    "description",
    "enum",
    "examples",
    "format",
    "maxItems",
    "maxLength",
    "maximum",
    "minItems",
    "minLength",
    "minimum",
    "multipleOf",
    "pattern",
    "title",
    "uniqueItems",
)
_GEMINI_PRESERVED_ENUM_PROPERTIES = {
    "code_kind",
    "completeness",
    "confidence",
    "coverage_status",
    "fact_subtype",
    "fact_type",
    "identifier_type",
    "income_type_candidate",
    "fee_type_candidate",
    "fx_fact_kind",
    "movement_type_candidate",
    "operation_type_candidate",
    "position_kind_candidate",
    "precision",
    "reason_code",
    "source_granularity",
    "withholding_type_candidate",
    "validator_status",
}


def _project_gemini_structural_schema(
    schema: dict[str, Any],
    *,
    property_name: str | None = None,
) -> int:
    transform_count = 0
    if "const" in schema:
        constant = schema["const"]
        existing_enum = schema.get("enum")
        if existing_enum is not None and (
            not isinstance(existing_enum, list)
            or not any(_json_equal(constant, candidate) for candidate in existing_enum)
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_schema_adaptation_conflict",
                "Gemini schema adaptation found incompatible const and enum values",
            )
    for keyword in _GEMINI_REMOVED_SCHEMA_KEYWORDS:
        if (
            keyword == "enum"
            and property_name in _GEMINI_PRESERVED_ENUM_PROPERTIES
        ):
            continue
        if keyword in schema:
            schema.pop(keyword)
            transform_count += 1
    for keyword in _SCHEMA_MAP_KEYWORDS:
        child_map = schema.get(keyword)
        if isinstance(child_map, dict):
            for child_name, child in child_map.items():
                if isinstance(child, dict):
                    transform_count += _project_gemini_structural_schema(
                        child,
                        property_name=(
                            str(child_name)
                            if keyword == "properties"
                            else None
                        ),
                    )
    for keyword in _SCHEMA_SINGLE_KEYWORDS:
        child = schema.get(keyword)
        if isinstance(child, dict):
            transform_count += _project_gemini_structural_schema(
                child,
                property_name=property_name if keyword == "items" else None,
            )
        elif keyword == "items" and isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    transform_count += _project_gemini_structural_schema(
                        item,
                        property_name=property_name,
                    )
    for keyword in _SCHEMA_ARRAY_KEYWORDS:
        children = schema.get(keyword)
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    transform_count += _project_gemini_structural_schema(
                        child,
                        property_name=property_name,
                    )
    return transform_count


def _schema_hash(schema: dict[str, Any]) -> str:
    rendered = json.dumps(
        schema,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _json_equal(left: Any, right: Any) -> bool:
    return json.dumps(
        left,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ) == json.dumps(
        right,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def provider_error_code(payload: dict[str, Any], *, source_profile: bool) -> str:
    rendered = json.dumps(payload, ensure_ascii=True, sort_keys=True).lower()
    if "oneof" in rendered or "one_of" in rendered:
        return "gate2_model_schema_oneof_unsupported"
    if source_profile:
        if "required" in rendered and "properties" in rendered:
            return "gate2_model_schema_required_properties_invalid"
        if "additionalproperties" in rendered or "additional_properties" in rendered:
            return "gate2_model_schema_additional_properties_invalid"
        if "must have a 'type' key" in rendered or 'must have a \\"type\\" key' in rendered:
            return "gate2_model_schema_type_key_missing"
        if "nullable" in rendered or "invalid nullable" in rendered:
            return "gate2_model_schema_nullable_type_invalid"
    if any(
        marker in rendered
        for marker in ("response_format", "output_config", "json_schema", "schema")
    ):
        return "gate2_model_schema_response_format_rejected"
    context_markers = ("context_length", "too many tokens")
    if source_profile:
        context_markers += ("maximum context",)
    if any(marker in rendered for marker in context_markers):
        return "gate2_model_context_budget_exceeded"
    if any(
        marker in rendered
        for marker in (
            "insufficient_quota",
            "insufficient quota",
            "quota_exceeded",
            "quota exceeded",
            "exceeded your current quota",
            "billing hard limit",
        )
    ):
        return "gate2_model_provider_quota_exceeded"
    status_codes = _provider_status_codes(payload)
    if 429 in status_codes or any(
        marker in rendered
        for marker in (
            "rate_limit",
            "rate limit",
            "too many requests",
            "request limit exceeded",
        )
    ):
        return "gate2_model_provider_rate_limited"
    if "model" in rendered and ("not found" in rendered or "unavailable" in rendered):
        return "gate2_model_unavailable"
    if "unauthorized" in rendered or "authentication" in rendered or "api key" in rendered:
        return "gate2_model_provider_auth_failed"
    if status_codes & {500, 502, 503, 504} or any(
        marker in rendered
        for marker in (
            "service unavailable",
            "provider unavailable",
            "temporarily unavailable",
            "upstream unavailable",
            "bad gateway",
            "gateway timeout",
            "provider timeout",
            "overloaded",
            "capacity unavailable",
        )
    ):
        return "gate2_model_provider_unavailable"
    return "gate2_model_provider_error"


def _provider_status_codes(payload: dict[str, Any]) -> set[int]:
    values: list[Any] = []
    for candidate in (payload, payload.get("error"), payload.get("detail")):
        if not isinstance(candidate, dict):
            continue
        for key in ("status", "status_code", "http_status", "code"):
            values.append(candidate.get(key))
    result: set[int] = set()
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            result.add(value)
        elif isinstance(value, str) and value.strip().isdigit():
            result.add(int(value.strip()))
    return result


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text and len(text) <= 512 and text.isprintable() else None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None
