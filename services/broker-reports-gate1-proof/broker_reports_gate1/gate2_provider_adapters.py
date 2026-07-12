from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
    "Pipes and Gate 2 business runtimes must not build vendor payloads or call provider endpoints"
)
MAX_NATIVE_PROVIDER_RESPONSE_BYTES = 1_048_576


@dataclass(frozen=True)
class Gate2NativeProviderTransportConfig:
    anthropic_api_version: str = "2023-06-01"
    timeout_seconds: int = 180


@dataclass(frozen=True)
class Gate2OpenWebUIProviderConnection:
    base_url: str
    api_key: str = dataclass_field(repr=False)


class Gate2OpenWebUIProviderConnectionResolver:
    def __init__(self, request: Any) -> None:
        self.request = request

    def resolve(
        self,
        profile: Gate2ProviderProfile,
    ) -> Gate2OpenWebUIProviderConnection:
        config = getattr(
            getattr(getattr(self.request, "app", None), "state", None),
            "config",
            None,
        )
        urls = self._config_value(config, "OPENAI_API_BASE_URLS")
        keys = self._config_value(config, "OPENAI_API_KEYS")
        configs = self._config_value(config, "OPENAI_API_CONFIGS")
        if not isinstance(urls, list) or not isinstance(keys, list):
            raise self._blocked("OpenWebUI provider connection state is unavailable")
        matches: list[Gate2OpenWebUIProviderConnection] = []
        for index, raw_url in enumerate(urls):
            base_url = str(raw_url or "").strip().rstrip("/")
            if not self._matches_profile(profile, base_url):
                continue
            entry_config = configs.get(str(index), {}) if isinstance(configs, dict) else {}
            if isinstance(entry_config, dict) and entry_config.get("enable") is False:
                continue
            api_key = str(keys[index] if index < len(keys) else "").strip()
            if not api_key:
                raise self._blocked("OpenWebUI provider connection has no API key")
            matches.append(
                Gate2OpenWebUIProviderConnection(
                    base_url=base_url,
                    api_key=api_key,
                )
            )
        if len(matches) != 1:
            reason = "not found" if not matches else "ambiguous"
            raise self._blocked(f"OpenWebUI provider connection is {reason}")
        return matches[0]

    @staticmethod
    def _config_value(config: Any, name: str) -> Any:
        value = getattr(config, name, None)
        return getattr(value, "value", value)

    @staticmethod
    def _matches_profile(profile: Gate2ProviderProfile, base_url: str) -> bool:
        normalized = base_url.lower()
        return any(
            normalized.startswith(prefix.lower().rstrip("/"))
            for prefix in profile.connection_base_url_prefixes
        )

    @staticmethod
    def _blocked(message: str) -> Gate2SourceFactRuntimeError:
        return Gate2SourceFactRuntimeError(
            "gate2_provider_configuration_blocked",
            message,
            failure_class="provider_configuration",
        )


@dataclass(frozen=True)
class Gate2PreparedProviderRequest:
    form_data: dict[str, Any]
    canonical_schema_hash: str
    adapted_schema_hash: str
    schema_transform_count: int


class Gate2ProviderAdapter(Protocol):
    profile: Gate2ProviderProfile
    uses_openwebui_completion: bool

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

    def validate_transport_configuration(self) -> None:
        ...

    def invoke_native_once(self, form_data: dict[str, Any]) -> Any:
        ...


class Gate2ProviderAdapterFactory:
    def __init__(
        self,
        *,
        profile: Gate2ProviderProfile,
        capability_probe: bool = False,
        native_transport_config: Gate2NativeProviderTransportConfig | None = None,
        native_transport_resolver=None,
        provider_connection_resolver=None,
    ) -> None:
        self.profile = profile
        self.capability_probe = capability_probe
        self.native_transport_config = (
            native_transport_config or Gate2NativeProviderTransportConfig()
        )
        self.native_transport_resolver = native_transport_resolver
        self.provider_connection_resolver = provider_connection_resolver

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
            native_transport_config=self.native_transport_config,
            native_transport_resolver=self.native_transport_resolver,
            provider_connection_resolver=self.provider_connection_resolver,
        )


class _Gate2OpenWebUIProviderAdapter:
    uses_openwebui_completion = True

    def __init__(
        self,
        *,
        profile: Gate2ProviderProfile,
        capability_probe: bool,
        native_transport_config: Gate2NativeProviderTransportConfig,
        native_transport_resolver,
        provider_connection_resolver,
    ) -> None:
        self.profile = profile
        self.capability_probe = capability_probe
        self.native_transport_config = native_transport_config
        self.native_transport_resolver = native_transport_resolver
        self.provider_connection_resolver = provider_connection_resolver

    def validate_transport_configuration(self) -> None:
        return None

    def invoke_native_once(self, form_data: dict[str, Any]) -> Any:
        raise Gate2SourceFactRuntimeError(
            "gate2_model_transport_unsupported",
            "Provider adapter does not expose a native transport",
        )

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
            transport_type=self.profile.transport_type,
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
            transport_type=self.profile.transport_type,
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


class Gate2AnthropicNativeMessagesAdapter(_Gate2OpenWebUIProviderAdapter):
    uses_openwebui_completion = False

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._provider_connection: Gate2OpenWebUIProviderConnection | None = None

    def prepare_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest:
        json_schema = self._strict_schema(response_format)
        schema = copy.deepcopy(json_schema["schema"])
        transform_count = _project_anthropic_structural_schema(schema)
        messages = form_data.get("messages")
        if not isinstance(messages, list):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Anthropic native transport requires messages",
            )
        system_parts: list[str] = []
        native_messages: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message, dict):
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_request_invalid",
                    "Anthropic native transport received an invalid message",
                )
            role = message.get("role")
            content = message.get("content")
            if not isinstance(content, str) or role not in {"system", "user", "assistant"}:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_request_invalid",
                    "Anthropic native transport requires text messages",
                )
            if role == "system":
                system_parts.append(content)
            else:
                native_messages.append({"role": role, "content": content})
        if not native_messages:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Anthropic native transport requires a user message",
            )
        prepared = {
            "model": form_data.get("model"),
            "max_tokens": 32768,
            "messages": native_messages,
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": schema,
                }
            },
        }
        if system_parts:
            prepared["system"] = "\n\n".join(system_parts)
        return Gate2PreparedProviderRequest(
            form_data=prepared,
            canonical_schema_hash=_schema_hash(json_schema["schema"]),
            adapted_schema_hash=_schema_hash(schema),
            schema_transform_count=transform_count,
        )

    def extract_content(self, payload: dict[str, Any]) -> Any:
        blocks = payload.get("content") if isinstance(payload, dict) else None
        text_blocks = [
            block.get("text")
            for block in blocks or []
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        if len(text_blocks) == 1:
            return text_blocks[0]
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            "Anthropic response must contain exactly one structured text block",
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
        return Gate2ProviderExecutionMetadata(
            provider_id=self.profile.provider_id,
            provider_profile_id=self.profile.profile_id,
            provider_profile_revision=gate2_provider_profile_revision(self.profile),
            adapter_id=self.profile.adapter_id,
            adapter_version=self.profile.adapter_version,
            requested_model_id=requested_model_id,
            structured_output_mode=self.profile.structured_output_mode,
            response_format_type=self.profile.response_format_type,
            response_format_schema_mode=self.profile.response_format_schema_mode,
            transport_type=self.profile.transport_type,
            canonical_request_schema_hash=prepared_request.canonical_schema_hash,
            adapted_request_schema_hash=prepared_request.adapted_schema_hash,
            schema_transform_count=prepared_request.schema_transform_count,
            resolved_model_id=_optional_string(value.get("model")),
            provider_response_id=_optional_string(value.get("id")),
            duration_ms=duration_ms,
            input_tokens=_optional_int(usage.get("input_tokens")),
            output_tokens=_optional_int(usage.get("output_tokens")),
            total_tokens=_optional_int(usage.get("total_tokens")),
            finish_reason=_optional_string(value.get("stop_reason")),
        )

    def validate_transport_configuration(self) -> None:
        self._resolve_provider_connection()
        if self.native_transport_config.anthropic_api_version != "2023-06-01":
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                "Unsupported Anthropic API version",
                failure_class="provider_configuration",
            )
        timeout = self.native_transport_config.timeout_seconds
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 600:
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                "Anthropic native transport timeout is invalid",
                failure_class="provider_configuration",
            )

    def invoke_native_once(self, form_data: dict[str, Any]) -> Any:
        if self.native_transport_resolver is not None:
            return self.native_transport_resolver(self.profile, form_data)
        return asyncio.to_thread(self._post_messages, form_data)

    def _post_messages(self, form_data: dict[str, Any]) -> dict[str, Any]:
        connection = self._resolve_provider_connection()
        encoded = json.dumps(
            form_data,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            f"{connection.base_url}/messages",
            data=encoded,
            method="POST",
            headers={
                "content-type": "application/json",
                "x-api-key": connection.api_key,
                "anthropic-version": self.native_transport_config.anthropic_api_version,
            },
        )
        try:
            with urlopen(
                request,
                timeout=self.native_transport_config.timeout_seconds,
            ) as response:
                body = response.read(MAX_NATIVE_PROVIDER_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            body = exc.read(MAX_NATIVE_PROVIDER_RESPONSE_BYTES + 1)
            if len(body) > MAX_NATIVE_PROVIDER_RESPONSE_BYTES:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_response_budget_exceeded",
                    "Anthropic error response exceeds the byte budget",
                    failure_class="response_budget",
                ) from exc
            payload = self._decode_payload(body)
            payload.setdefault("status_code", exc.code)
            return payload
        except URLError as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_provider_unavailable",
                "Anthropic native transport is unavailable",
                raw_output={"transport_error_type": exc.__class__.__name__},
                failure_class="provider_transport",
            ) from exc
        if len(body) > MAX_NATIVE_PROVIDER_RESPONSE_BYTES:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_response_budget_exceeded",
                "Anthropic response exceeds the byte budget",
                failure_class="response_budget",
            )
        return self._decode_payload(body)

    def _resolve_provider_connection(self) -> Gate2OpenWebUIProviderConnection:
        if self._provider_connection is not None:
            return self._provider_connection
        if self.provider_connection_resolver is None:
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                "OpenWebUI provider connection resolver is unavailable",
                failure_class="provider_configuration",
            )
        connection = self.provider_connection_resolver(self.profile)
        if not isinstance(connection, Gate2OpenWebUIProviderConnection):
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                "OpenWebUI provider connection resolver returned an invalid contract",
                failure_class="provider_configuration",
            )
        self._provider_connection = connection
        return connection

    @staticmethod
    def _decode_payload(body: bytes) -> dict[str, Any]:
        diagnostic = {
            "body_length": len(body),
            "body_sha256": hashlib.sha256(body).hexdigest(),
        }
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Anthropic native transport returned invalid JSON",
                raw_output=diagnostic,
            ) from exc
        if not isinstance(payload, dict):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Anthropic native transport returned a non-object response",
                raw_output=diagnostic,
            )
        return payload


_PROVIDER_ADAPTER_TYPES = {
    "openai_response_format": Gate2OpenAIResponseFormatAdapter,
    "gemini_response_format": Gate2GeminiResponseFormatAdapter,
    "anthropic_native_messages": Gate2AnthropicNativeMessagesAdapter,
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
_ANTHROPIC_REMOVED_SCHEMA_KEYWORDS = (
    "default",
    "examples",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "maxItems",
    "maxLength",
    "maxProperties",
    "maximum",
    "minItems",
    "minLength",
    "minProperties",
    "minimum",
    "multipleOf",
    "pattern",
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


def _project_anthropic_structural_schema(schema: dict[str, Any]) -> int:
    transform_count = 0
    collapsed = _collapse_anthropic_const_object_union(schema)
    if collapsed is not None:
        schema.clear()
        schema.update(collapsed)
        transform_count += 1
    for keyword in _ANTHROPIC_REMOVED_SCHEMA_KEYWORDS:
        if keyword in schema:
            schema.pop(keyword)
            transform_count += 1
    for keyword in _SCHEMA_MAP_KEYWORDS:
        child_map = schema.get(keyword)
        if isinstance(child_map, dict):
            for child in child_map.values():
                if isinstance(child, dict):
                    transform_count += _project_anthropic_structural_schema(child)
    for keyword in _SCHEMA_SINGLE_KEYWORDS:
        child = schema.get(keyword)
        if isinstance(child, dict):
            transform_count += _project_anthropic_structural_schema(child)
        elif keyword == "items" and isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    transform_count += _project_anthropic_structural_schema(item)
    for keyword in _SCHEMA_ARRAY_KEYWORDS:
        children = schema.get(keyword)
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    transform_count += _project_anthropic_structural_schema(child)
    return transform_count


def _collapse_anthropic_const_object_union(
    schema: dict[str, Any],
) -> dict[str, Any] | None:
    variants = schema.get("anyOf")
    if not isinstance(variants, list) or len(variants) < 2:
        return None
    property_names: tuple[str, ...] | None = None
    required: tuple[str, ...] | None = None
    merged_values: dict[str, list[Any]] = {}
    property_types: dict[str, Any] = {}
    for variant in variants:
        if (
            not isinstance(variant, dict)
            or variant.get("type") != "object"
            or variant.get("additionalProperties") is not False
            or not isinstance(variant.get("properties"), dict)
            or not isinstance(variant.get("required"), list)
        ):
            return None
        properties = variant["properties"]
        current_names = tuple(properties.keys())
        current_required = tuple(str(item) for item in variant["required"])
        if property_names is None:
            property_names = current_names
            required = current_required
        elif current_names != property_names or current_required != required:
            return None
        for name, property_schema in properties.items():
            if (
                not isinstance(property_schema, dict)
                or "const" not in property_schema
                or set(property_schema) - {"type", "const", "description"}
            ):
                return None
            property_type = property_schema.get("type")
            if name in property_types and property_types[name] != property_type:
                return None
            property_types[name] = property_type
            values = merged_values.setdefault(name, [])
            value = copy.deepcopy(property_schema["const"])
            if not any(_json_equal(value, existing) for existing in values):
                values.append(value)
    if property_names is None or required is None:
        return None
    return {
        "type": "object",
        "properties": {
            name: {
                **({"type": property_types[name]} if property_types[name] else {}),
                "enum": merged_values[name],
            }
            for name in property_names
        },
        "required": list(required),
        "additionalProperties": False,
    }


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
