from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
from dataclasses import dataclass, field as dataclass_field, replace
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
    urlopen,
)

from .gate2_economy_budget import Gate2EconomyBudgetSessionFactory
from .gate2_model_contracts import (
    PROVIDER_STATUS_APPROVED,
    PROVIDER_STATUS_PROBE_REQUIRED,
    Gate2ProviderExecutionMetadata,
    Gate2ProviderProfile,
    Gate2SourceFactRuntimeError,
    gate2_model_qualification_status,
    gate2_provider_profile,
    gate2_provider_profile_revision,
    gate2_resolved_model_matches_requested,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)


FACTORY_REQUIRED = "Gate2ProviderAdapterFactory.create is the only production Gate 2 provider adapter entrypoint"
FORBIDDEN = "Pipes and Gate 2 business runtimes must not build vendor payloads or call provider endpoints"
MAX_NATIVE_PROVIDER_RESPONSE_BYTES = 1_048_576
GATE3_GEMINI_MAX_OUTPUT_TOKENS = 65_536
CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY = (
    "direct_exact_provider_http_via_openwebui_connection_v1"
)
CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_CONTRACT_SCHEMA_VERSION = (
    "gate2_context_v2_1_budget_smoke_transport_contract_v1"
)
CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE = "direct_provider_http"
CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION = (
    "broker_reports_gate2_context_v2_1_local_schema_projection_v1"
)
_CONTEXT_V2_1_BUDGET_SMOKE_BASE_PATHS = {
    "openai_gpt": ("/v1",),
    "anthropic_claude": ("/v1",),
    "google_gemini": ("/v1beta/openai",),
}
_CONTEXT_V2_1_BUDGET_SMOKE_CANONICAL_BASE_URLS = {
    "openai_gpt": "https://api.openai.com/v1",
    "anthropic_claude": "https://api.anthropic.com/v1",
    "google_gemini": ("https://generativelanguage.googleapis.com/v1beta/openai"),
}
_PROVIDER_EMBEDDED_SCHEMA_PATHS = {
    "openai_response_format": (
        "response_format",
        "json_schema",
        "schema",
    ),
    "gemini_response_format": (
        "response_format",
        "json_schema",
        "schema",
    ),
    "anthropic_native_messages": (
        "output_config",
        "format",
        "schema",
    ),
}


@dataclass(frozen=True)
class Gate2NativeProviderTransportConfig:
    anthropic_api_version: str = "2023-06-01"
    timeout_seconds: int = 180


@dataclass(frozen=True)
class Gate2OpenWebUIProviderConnection:
    base_url: str
    api_key: str = dataclass_field(repr=False)


@dataclass(frozen=True)
class Gate2ContextV21BudgetSmokeTransportContract:
    schema_version: str
    transport_policy: str
    actual_transport_type: str
    connection_configuration_source: str
    endpoint_url: str
    http_method: str
    semantic_headers: tuple[tuple[str, str], ...]
    timeout_seconds: int
    redirect_policy: str
    proxy_policy: str
    maximum_response_bytes: int
    retry_calls: int

    def safe_snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "transport_policy": self.transport_policy,
            "actual_transport_type": self.actual_transport_type,
            "connection_configuration_source": (self.connection_configuration_source),
            "endpoint_url": self.endpoint_url,
            "http_method": self.http_method,
            "semantic_headers": dict(self.semantic_headers),
            "timeout_seconds": self.timeout_seconds,
            "redirect_policy": self.redirect_policy,
            "proxy_policy": self.proxy_policy,
            "maximum_response_bytes": self.maximum_response_bytes,
            "retry_calls": self.retry_calls,
        }

    def canonical_json_bytes(self) -> bytes:
        return json.dumps(
            self.safe_snapshot(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    @property
    def integrity_hash(self) -> str:
        return hashlib.sha256(self.canonical_json_bytes()).hexdigest()


class _Gate2NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        return None


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
            entry_config = (
                configs.get(str(index), {}) if isinstance(configs, dict) else {}
            )
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

    def resolve_context_v2_1_budget_smoke(
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
        canonical = self.canonical_base_url(profile)
        allowed_configured_urls = {canonical, f"{canonical}/"}
        matches: list[Gate2OpenWebUIProviderConnection] = []
        for index, raw_url in enumerate(urls):
            if not isinstance(raw_url, str) or raw_url not in allowed_configured_urls:
                continue
            entry_config = (
                configs.get(str(index), {}) if isinstance(configs, dict) else {}
            )
            if isinstance(entry_config, dict) and entry_config.get("enable") is False:
                continue
            api_key = str(keys[index] if index < len(keys) else "").strip()
            if not api_key:
                raise self._blocked("OpenWebUI provider connection has no API key")
            matches.append(
                Gate2OpenWebUIProviderConnection(
                    base_url=canonical,
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
    def _matches_context_v2_1_budget_smoke_profile(
        profile: Gate2ProviderProfile,
        base_url: str,
    ) -> bool:
        if (
            not isinstance(base_url, str)
            or not base_url
            or base_url != base_url.strip().rstrip("/")
            or any(ord(character) < 32 for character in base_url)
        ):
            return False
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
        except ValueError:
            return False
        if (
            parsed.scheme.lower() != "https"
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or port not in {None, 443}
        ):
            return False
        approved_hosts = {
            approved.hostname.lower()
            for prefix in profile.connection_base_url_prefixes
            if (approved := urlsplit(prefix)).scheme.lower() == "https"
            and approved.hostname is not None
        }
        allowed_paths = _CONTEXT_V2_1_BUDGET_SMOKE_BASE_PATHS.get(
            profile.profile_id,
            (),
        )
        normalized_path = parsed.path.rstrip("/") or "/"
        return (
            parsed.hostname.lower() in approved_hosts
            and normalized_path in allowed_paths
        )

    @staticmethod
    def connection_is_valid(
        profile: Gate2ProviderProfile,
        connection: Gate2OpenWebUIProviderConnection,
    ) -> bool:
        return (
            isinstance(connection, Gate2OpenWebUIProviderConnection)
            and connection.base_url
            == _CONTEXT_V2_1_BUDGET_SMOKE_CANONICAL_BASE_URLS.get(profile.profile_id)
            and Gate2OpenWebUIProviderConnectionResolver._matches_context_v2_1_budget_smoke_profile(
                profile,
                connection.base_url,
            )
            and isinstance(connection.api_key, str)
            and bool(connection.api_key)
            and connection.api_key == connection.api_key.strip()
            and all(
                ord(character) >= 32 and ord(character) != 127
                for character in connection.api_key
            )
        )

    @staticmethod
    def canonical_base_url(profile: Gate2ProviderProfile) -> str:
        canonical = _CONTEXT_V2_1_BUDGET_SMOKE_CANONICAL_BASE_URLS.get(
            profile.profile_id
        )
        if (
            not isinstance(canonical, str)
            or not canonical
            or not Gate2OpenWebUIProviderConnectionResolver._matches_context_v2_1_budget_smoke_profile(
                profile,
                canonical,
            )
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                "Provider profile has no canonical direct base URL",
                failure_class="provider_configuration",
            )
        return canonical

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
    provider_visible_schema: dict[str, Any]
    provider_adapter_id: str
    canonical_schema_hash: str
    adapted_schema_hash: str
    schema_transform_count: int
    projection_policy_version: str | None = None

    def schema_binding_is_valid(self) -> bool:
        embedded_schema: Any = self.form_data
        schema_path = _PROVIDER_EMBEDDED_SCHEMA_PATHS.get(self.provider_adapter_id)
        if not isinstance(schema_path, tuple):
            return False
        for field in schema_path:
            if not isinstance(embedded_schema, dict):
                return False
            embedded_schema = embedded_schema.get(field)
        return (
            isinstance(self.provider_visible_schema, dict)
            and isinstance(embedded_schema, dict)
            and self.adapted_schema_hash
            == _schema_hash(self.provider_visible_schema)
            == _schema_hash(embedded_schema)
        )

    def canonical_schema_is_bound(
        self,
        canonical_schema: dict[str, Any],
    ) -> bool:
        if not isinstance(
            canonical_schema, dict
        ) or self.canonical_schema_hash != _schema_hash(canonical_schema):
            return False
        try:
            expected_projection_policy = _validate_semantic_enum_projection(
                canonical_schema=canonical_schema,
                provider_schema=self.provider_visible_schema,
            )
        except Gate2SourceFactRuntimeError:
            return False
        return self.projection_policy_version == expected_projection_policy

    def context_v2_1_contract_is_bound(
        self,
        *,
        canonical_schema: dict[str, Any],
        provider_profile: Gate2ProviderProfile,
        model_visible_request: dict[str, Any],
        local_projection_model_id: str,
    ) -> bool:
        try:
            authoritative_profile = gate2_provider_profile(provider_profile.profile_id)
        except (AttributeError, Gate2SourceFactRuntimeError):
            return False
        if (
            provider_profile != authoritative_profile
            or self.provider_adapter_id != authoritative_profile.adapter_id
            or self.projection_policy_version
            != CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION
            or not isinstance(model_visible_request, dict)
            or not isinstance(local_projection_model_id, str)
            or not local_projection_model_id
            or not self.canonical_schema_is_bound(canonical_schema)
        ):
            return False
        response_format = model_visible_request.get("response_format")
        model_visible_schema = (
            response_format.get("json_schema", {}).get("schema")
            if isinstance(response_format, dict)
            and isinstance(response_format.get("json_schema"), dict)
            else None
        )
        if model_visible_schema != canonical_schema:
            return False
        try:
            form_data = Gate2OpenWebUIRequestBuilder(
                request_profile=(
                    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE
                )
            ).build_from_sealed_context_v2_1(
                model_visible_request=model_visible_request,
                model_id=local_projection_model_id,
            )
            expected = (
                Gate2ProviderAdapterFactory(profile=authoritative_profile)
                .create()
                .prepare_form_data(
                    form_data=form_data,
                    response_format=response_format,
                )
            )
        except Gate2SourceFactRuntimeError:
            return False
        return self == expected

    def context_v2_1_budget_smoke_contract_is_bound(
        self,
        *,
        canonical_schema: dict[str, Any],
        provider_profile: Gate2ProviderProfile,
        model_visible_request: dict[str, Any],
        exact_model_id: str,
        operation_identity: str,
        provider_profile_resolver: Callable[
            [str], Gate2ProviderProfile
        ] = gate2_provider_profile,
    ) -> bool:
        try:
            authoritative_profile = provider_profile_resolver(
                provider_profile.profile_id
            )
        except (AttributeError, Gate2SourceFactRuntimeError):
            return False
        if (
            provider_profile != authoritative_profile
            or self.provider_adapter_id != authoritative_profile.adapter_id
            or self.projection_policy_version
            != CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION
            or not isinstance(model_visible_request, dict)
            or not isinstance(exact_model_id, str)
            or not exact_model_id
            or not isinstance(operation_identity, str)
            or not operation_identity
            or not self.canonical_schema_is_bound(canonical_schema)
        ):
            return False
        response_format = model_visible_request.get("response_format")
        model_visible_schema = (
            response_format.get("json_schema", {}).get("schema")
            if isinstance(response_format, dict)
            and isinstance(response_format.get("json_schema"), dict)
            else None
        )
        if model_visible_schema != canonical_schema:
            return False
        try:
            form_data = Gate2OpenWebUIRequestBuilder(
                request_profile=(
                    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
                )
            ).build_from_sealed_context_v2_1(
                model_visible_request=model_visible_request,
                model_id=exact_model_id,
            )
            authorization = (
                Gate2EconomyBudgetSessionFactory()
                .create(
                    request_profile=(
                        FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
                    )
                )
                .prepare_call(
                    form_data=form_data,
                    model_id=exact_model_id,
                    provider_profile_id=authoritative_profile.profile_id,
                    operation_identity=operation_identity,
                )
            )
            expected = (
                Gate2ProviderAdapterFactory(
                    profile=authoritative_profile,
                    capability_probe=True,
                )
                .create()
                .prepare_context_v2_1_budget_smoke_form_data(
                    form_data=authorization.prepared_form_data,
                    response_format=response_format,
                )
            )
        except Gate2SourceFactRuntimeError:
            return False
        return self == expected

    def validate_schema_binding(self) -> None:
        if not self.schema_binding_is_valid():
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_prepared_schema_binding_invalid",
                "Prepared request schema binding is invalid",
            )


class Gate2ProviderAdapter(Protocol):
    profile: Gate2ProviderProfile
    uses_openwebui_completion: bool

    def validate_model(self, model_id: str) -> None: ...

    def execution_contract(self, model_id: str) -> Gate2ProviderExecutionMetadata: ...

    def validate_execution_metadata(
        self,
        metadata: Gate2ProviderExecutionMetadata,
    ) -> None: ...

    def prepare_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest: ...

    def prepare_context_v2_1_budget_smoke_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest: ...

    def prepare_gate3_bounded_labeling_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest: ...

    def prepare_gate3_metadata_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest: ...

    def extract_content(self, payload: dict[str, Any]) -> Any: ...

    def extract_prepared_content(
        self,
        payload: dict[str, Any],
        *,
        prepared_request: Gate2PreparedProviderRequest,
    ) -> Any: ...

    def extract_context_v2_1_prepared_content(
        self,
        payload: dict[str, Any],
        *,
        prepared_request: Gate2PreparedProviderRequest,
        canonical_schema: dict[str, Any],
        model_visible_request: dict[str, Any],
        local_projection_model_id: str,
    ) -> Any: ...

    def extract_context_v2_1_budget_smoke_prepared_content(
        self,
        payload: dict[str, Any],
        *,
        prepared_request: Gate2PreparedProviderRequest,
        canonical_schema: dict[str, Any],
        model_visible_request: dict[str, Any],
        exact_model_id: str,
        operation_identity: str,
    ) -> Any: ...

    def execution_metadata(
        self,
        *,
        payload: dict[str, Any] | None,
        requested_model_id: str,
        duration_ms: int | None,
        prepared_request: Gate2PreparedProviderRequest,
    ) -> Gate2ProviderExecutionMetadata: ...

    def validate_transport_configuration(self) -> None: ...

    def invoke_native_once(self, form_data: dict[str, Any]) -> Any: ...

    def validate_context_v2_1_budget_smoke_transport_configuration(
        self,
        *,
        transport_policy: str,
    ) -> None: ...

    def context_v2_1_budget_smoke_transport_contract(
        self,
        *,
        transport_policy: str,
    ) -> Gate2ContextV21BudgetSmokeTransportContract: ...

    def invoke_context_v2_1_budget_smoke_once(
        self,
        *,
        form_data: dict[str, Any],
        transport_policy: str,
    ) -> Any: ...

    def context_v2_1_budget_smoke_execution_metadata(
        self,
        *,
        payload: dict[str, Any] | None,
        requested_model_id: str,
        duration_ms: int | None,
        prepared_request: Gate2PreparedProviderRequest,
        transport_contract: Gate2ContextV21BudgetSmokeTransportContract,
    ) -> Gate2ProviderExecutionMetadata: ...


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
        self._provider_connection: Gate2OpenWebUIProviderConnection | None = None
        self._context_v2_1_budget_smoke_provider_connection: (
            Gate2OpenWebUIProviderConnection | None
        ) = None

    def validate_transport_configuration(self) -> None:
        return None

    def invoke_native_once(self, form_data: dict[str, Any]) -> Any:
        raise Gate2SourceFactRuntimeError(
            "gate2_model_transport_unsupported",
            "Provider adapter does not expose a native transport",
        )

    def validate_context_v2_1_budget_smoke_transport_configuration(
        self,
        *,
        transport_policy: str,
    ) -> None:
        self._validate_context_v2_1_budget_smoke_transport_policy(transport_policy)
        self._validate_native_transport_timeout()
        self._validate_context_v2_1_budget_smoke_provider_configuration()
        if self.native_transport_resolver is None:
            self._resolve_context_v2_1_budget_smoke_provider_connection()

    def context_v2_1_budget_smoke_transport_contract(
        self,
        *,
        transport_policy: str,
    ) -> Gate2ContextV21BudgetSmokeTransportContract:
        self._validate_context_v2_1_budget_smoke_transport_policy(transport_policy)
        self._validate_native_transport_timeout()
        self._validate_context_v2_1_budget_smoke_provider_configuration()
        canonical_connection = Gate2OpenWebUIProviderConnection(
            base_url=(
                Gate2OpenWebUIProviderConnectionResolver.canonical_base_url(
                    self.profile
                )
            ),
            api_key="",
        )
        return Gate2ContextV21BudgetSmokeTransportContract(
            schema_version=(
                CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_CONTRACT_SCHEMA_VERSION
            ),
            transport_policy=transport_policy,
            actual_transport_type=(CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE),
            connection_configuration_source=(
                "openwebui_admin_connection_configuration_only"
            ),
            endpoint_url=(
                self._context_v2_1_budget_smoke_endpoint(canonical_connection)
            ),
            http_method="POST",
            semantic_headers=tuple(
                sorted(self._context_v2_1_budget_smoke_semantic_headers().items())
            ),
            timeout_seconds=self.native_transport_config.timeout_seconds,
            redirect_policy="deny_all",
            proxy_policy="ambient_proxies_disabled",
            maximum_response_bytes=MAX_NATIVE_PROVIDER_RESPONSE_BYTES,
            retry_calls=0,
        )

    def invoke_context_v2_1_budget_smoke_once(
        self,
        *,
        form_data: dict[str, Any],
        transport_policy: str,
    ) -> Any:
        self.validate_context_v2_1_budget_smoke_transport_configuration(
            transport_policy=transport_policy,
        )
        self._validate_context_v2_1_budget_smoke_wire_form_data(form_data)
        if self.native_transport_resolver is not None:
            return self.native_transport_resolver(self.profile, form_data)
        try:
            encoded_form_data = json.dumps(
                form_data,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Context V2.1 budget-smoke wire request is not JSON",
            ) from exc
        return asyncio.to_thread(
            self._post_context_v2_1_budget_smoke,
            encoded_form_data,
        )

    def context_v2_1_budget_smoke_execution_metadata(
        self,
        *,
        payload: dict[str, Any] | None,
        requested_model_id: str,
        duration_ms: int | None,
        prepared_request: Gate2PreparedProviderRequest,
        transport_contract: Gate2ContextV21BudgetSmokeTransportContract,
    ) -> Gate2ProviderExecutionMetadata:
        if (
            not isinstance(
                prepared_request,
                Gate2PreparedProviderRequest,
            )
            or not isinstance(
                transport_contract,
                Gate2ContextV21BudgetSmokeTransportContract,
            )
            or transport_contract
            != self.context_v2_1_budget_smoke_transport_contract(
                transport_policy=(CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY)
            )
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_transport_contract_mismatch",
                "Context V2.1 budget-smoke transport contract is not exact",
                failure_class="provider_configuration",
            )
        self._validate_context_v2_1_budget_smoke_wire_form_data(
            prepared_request.form_data
        )
        return replace(
            self.execution_metadata(
                payload=payload,
                requested_model_id=requested_model_id,
                duration_ms=duration_ms,
                prepared_request=prepared_request,
            ),
            transport_type=(CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE),
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
        projection_policy_version = _validate_semantic_enum_projection(
            canonical_schema=canonical_schema,
            provider_schema=adapted_json_schema["schema"],
        )
        prepared["response_format"] = adapted_response_format
        self._annotate(prepared)
        result = Gate2PreparedProviderRequest(
            form_data=prepared,
            provider_visible_schema=copy.deepcopy(adapted_json_schema["schema"]),
            provider_adapter_id=self.profile.adapter_id,
            canonical_schema_hash=_schema_hash(canonical_schema),
            adapted_schema_hash=_schema_hash(adapted_json_schema["schema"]),
            schema_transform_count=schema_transform_count,
            projection_policy_version=projection_policy_version,
        )
        result.validate_schema_binding()
        return result

    def prepare_context_v2_1_budget_smoke_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest:
        prepared_request = self.prepare_form_data(
            form_data=form_data,
            response_format=response_format,
        )
        provider_form_data = copy.deepcopy(prepared_request.form_data)
        provider_form_data.pop("metadata", None)
        self._project_context_v2_1_budget_smoke_wire_form_data(provider_form_data)
        self._validate_context_v2_1_budget_smoke_wire_form_data(provider_form_data)
        result = replace(
            prepared_request,
            form_data=provider_form_data,
        )
        result.validate_schema_binding()
        return result

    def prepare_gate3_bounded_labeling_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest:
        """Project one sealed Gate 3 request without model-visible metadata."""

        prepared_request = self.prepare_form_data(
            form_data=form_data,
            response_format=response_format,
        )
        provider_form_data = copy.deepcopy(prepared_request.form_data)
        provider_form_data.pop("metadata", None)
        messages = provider_form_data.get("messages")
        system = provider_form_data.get("system")
        if system is None:
            expected_keys = {"model", "messages", "stream", "response_format"}
            roles = ["system", "user", "user"]
            contents = (
                [item.get("content") for item in messages]
                if isinstance(messages, list)
                and all(isinstance(item, dict) for item in messages)
                else []
            )
        else:
            expected_keys = {
                "model",
                "max_tokens",
                "messages",
                "output_config",
                "system",
            }
            roles = ["user", "user"]
            contents = (
                [system, *[item.get("content") for item in messages]]
                if isinstance(system, str)
                and isinstance(messages, list)
                and all(isinstance(item, dict) for item in messages)
                else []
            )
        if (
            set(provider_form_data) != expected_keys
            or not isinstance(messages, list)
            or [item.get("role") for item in messages if isinstance(item, dict)]
            != roles
            or len(contents) != 3
            or any(not isinstance(content, str) or not content for content in contents)
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Gate 3 provider request contains unexpected model context",
            )
        result = replace(
            prepared_request,
            form_data=provider_form_data,
        )
        result.validate_schema_binding()
        return result

    def prepare_gate3_metadata_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest:
        """Project a sealed three-part metadata request without extra context."""

        prepared_request = self.prepare_form_data(
            form_data=form_data,
            response_format=response_format,
        )
        provider_form_data = copy.deepcopy(prepared_request.form_data)
        provider_form_data.pop("metadata", None)
        messages = provider_form_data.get("messages")
        system = provider_form_data.get("system")
        if system is None:
            expected_keys = {"model", "messages", "stream", "response_format"}
            roles = ["system", "user", "user"]
            contents = (
                [item.get("content") for item in messages]
                if isinstance(messages, list)
                and all(isinstance(item, dict) for item in messages)
                else []
            )
        else:
            expected_keys = {
                "model",
                "max_tokens",
                "messages",
                "output_config",
                "system",
            }
            roles = ["user", "user"]
            contents = (
                [system, *[item.get("content") for item in messages]]
                if isinstance(system, str)
                and isinstance(messages, list)
                and all(isinstance(item, dict) for item in messages)
                else []
            )
        if (
            set(provider_form_data) != expected_keys
            or not isinstance(messages, list)
            or [item.get("role") for item in messages if isinstance(item, dict)]
            != roles
            or len(contents) != 3
            or any(not isinstance(content, str) or not content for content in contents)
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Gate 3 metadata request contains unexpected model context",
            )
        result = replace(prepared_request, form_data=provider_form_data)
        result.validate_schema_binding()
        return result

    def extract_content(self, payload: dict[str, Any]) -> Any:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = (
                first.get("message") if isinstance(first.get("message"), dict) else {}
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

    def extract_prepared_content(
        self,
        payload: dict[str, Any],
        *,
        prepared_request: Gate2PreparedProviderRequest,
    ) -> Any:
        if not isinstance(prepared_request, Gate2PreparedProviderRequest):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Prepared provider request is required for extraction",
            )
        return self.extract_content(payload)

    def extract_context_v2_1_prepared_content(
        self,
        payload: dict[str, Any],
        *,
        prepared_request: Gate2PreparedProviderRequest,
        canonical_schema: dict[str, Any],
        model_visible_request: dict[str, Any],
        local_projection_model_id: str,
    ) -> Any:
        if not isinstance(
            prepared_request,
            Gate2PreparedProviderRequest,
        ) or not prepared_request.context_v2_1_contract_is_bound(
            canonical_schema=canonical_schema,
            provider_profile=self.profile,
            model_visible_request=model_visible_request,
            local_projection_model_id=local_projection_model_id,
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Context V2.1 prepared request is not exact",
            )
        _validate_context_v2_1_terminal_response(
            payload=payload,
            provider_adapter_id=self.profile.adapter_id,
        )
        return self.extract_prepared_content(
            payload,
            prepared_request=prepared_request,
        )

    def extract_context_v2_1_budget_smoke_prepared_content(
        self,
        payload: dict[str, Any],
        *,
        prepared_request: Gate2PreparedProviderRequest,
        canonical_schema: dict[str, Any],
        model_visible_request: dict[str, Any],
        exact_model_id: str,
        operation_identity: str,
    ) -> Any:
        if not isinstance(
            prepared_request,
            Gate2PreparedProviderRequest,
        ) or not prepared_request.context_v2_1_budget_smoke_contract_is_bound(
            canonical_schema=canonical_schema,
            provider_profile=self.profile,
            model_visible_request=model_visible_request,
            exact_model_id=exact_model_id,
            operation_identity=operation_identity,
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Context V2.1 budget-smoke prepared request is not exact",
            )
        _validate_context_v2_1_terminal_response(
            payload=payload,
            provider_adapter_id=self.profile.adapter_id,
        )
        return self.extract_prepared_content(
            payload,
            prepared_request=prepared_request,
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
        input_details = _usage_details(
            usage,
            "prompt_tokens_details",
            "input_tokens_details",
        )
        output_details = _usage_details(
            usage,
            "completion_tokens_details",
            "output_tokens_details",
        )
        input_tokens = _optional_int(
            usage.get("prompt_tokens", usage.get("input_tokens"))
        )
        output_tokens = _optional_int(
            usage.get("completion_tokens", usage.get("output_tokens"))
        )
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
            canonical_request_schema_hash=(prepared_request.canonical_schema_hash),
            adapted_request_schema_hash=prepared_request.adapted_schema_hash,
            schema_transform_count=prepared_request.schema_transform_count,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=_normalized_usage_total(
                reported_total=usage.get("total_tokens"),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            cached_input_tokens=_first_optional_int(
                input_details.get("cached_tokens"),
                usage.get("cached_input_tokens"),
                usage.get("cache_read_input_tokens"),
            ),
            reasoning_tokens=_first_optional_int(
                output_details.get("reasoning_tokens"),
                output_details.get("thinking_tokens"),
                usage.get("reasoning_tokens"),
                usage.get("thoughts_token_count"),
            ),
            finish_reason=_optional_string(first.get("finish_reason")),
        )

    @staticmethod
    def _validate_context_v2_1_budget_smoke_transport_policy(
        transport_policy: str,
    ) -> None:
        if transport_policy != CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_transport_policy_mismatch",
                "Context V2.1 budget-smoke transport policy is not exact",
                failure_class="provider_configuration",
            )

    def _validate_native_transport_timeout(self) -> None:
        timeout = self.native_transport_config.timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, int)
            or not 1 <= timeout <= 600
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                "Direct provider transport timeout is invalid",
                failure_class="provider_configuration",
            )

    def _validate_context_v2_1_budget_smoke_provider_configuration(
        self,
    ) -> None:
        return None

    def _project_context_v2_1_budget_smoke_wire_form_data(
        self,
        form_data: dict[str, Any],
    ) -> None:
        return None

    @staticmethod
    def _validate_context_v2_1_budget_smoke_wire_form_data(
        form_data: dict[str, Any],
    ) -> None:
        if not isinstance(form_data, dict) or not form_data or "metadata" in form_data:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Context V2.1 budget-smoke wire request is not exact",
            )

    def _post_context_v2_1_budget_smoke(
        self,
        encoded_form_data: bytes,
    ) -> dict[str, Any]:
        connection = self._resolve_context_v2_1_budget_smoke_provider_connection()
        request = Request(
            self._context_v2_1_budget_smoke_endpoint(connection),
            data=encoded_form_data,
            method="POST",
            headers=self._context_v2_1_budget_smoke_headers(connection),
        )
        opener = build_opener(
            ProxyHandler({}),
            _Gate2NoRedirectHandler(),
        )
        try:
            with opener.open(
                request,
                timeout=self.native_transport_config.timeout_seconds,
            ) as response:
                status_code = self._response_status_code(response)
                if not isinstance(status_code, int) or not 200 <= status_code < 300:
                    diagnostic = self._bounded_provider_body_diagnostic(response)
                    raise self._provider_http_failure(
                        status_code=status_code,
                        diagnostic=diagnostic,
                    )
                body = self._read_bounded_provider_body(response)
        except HTTPError as exc:
            try:
                diagnostic = self._bounded_provider_body_diagnostic(exc)
            finally:
                exc.close()
            raise self._provider_http_failure(
                status_code=exc.code,
                diagnostic=diagnostic,
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_provider_unavailable",
                "Direct provider transport is unavailable",
                raw_output={
                    "transport_error_type": exc.__class__.__name__,
                },
                failure_class="provider_transport",
            ) from exc
        return self._decode_provider_payload(body)

    def _context_v2_1_budget_smoke_endpoint(
        self,
        connection: Gate2OpenWebUIProviderConnection,
    ) -> str:
        return f"{connection.base_url}/chat/completions"

    @staticmethod
    def _context_v2_1_budget_smoke_headers(
        connection: Gate2OpenWebUIProviderConnection,
    ) -> dict[str, str]:
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {connection.api_key}",
        }

    @staticmethod
    def _context_v2_1_budget_smoke_semantic_headers() -> dict[str, str]:
        return {
            "content-type": "application/json",
            "authorization": "Bearer",
        }

    def _resolve_provider_connection(
        self,
    ) -> Gate2OpenWebUIProviderConnection:
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
        return self._provider_connection

    def _resolve_context_v2_1_budget_smoke_provider_connection(
        self,
    ) -> Gate2OpenWebUIProviderConnection:
        if self._context_v2_1_budget_smoke_provider_connection is not None:
            return self._context_v2_1_budget_smoke_provider_connection
        if self.provider_connection_resolver is None:
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                "OpenWebUI provider connection resolver is unavailable",
                failure_class="provider_configuration",
            )
        connection = self.provider_connection_resolver(self.profile)
        if not Gate2OpenWebUIProviderConnectionResolver.connection_is_valid(
            self.profile,
            connection,
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                (
                    "OpenWebUI provider connection resolver returned "
                    "a non-canonical GOAL 12 contract"
                ),
                failure_class="provider_configuration",
            )
        self._context_v2_1_budget_smoke_provider_connection = connection
        return self._context_v2_1_budget_smoke_provider_connection

    @staticmethod
    def _response_status_code(response: Any) -> int | None:
        status_code = getattr(response, "status", None)
        if isinstance(status_code, int) and not isinstance(status_code, bool):
            return status_code
        getcode = getattr(response, "getcode", None)
        if callable(getcode):
            status_code = getcode()
            if isinstance(status_code, int) and not isinstance(
                status_code,
                bool,
            ):
                return status_code
        return None

    @staticmethod
    def _read_bounded_provider_body(response: Any) -> bytes:
        body = response.read(MAX_NATIVE_PROVIDER_RESPONSE_BYTES + 1)
        if not isinstance(body, bytes):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Direct provider transport returned a non-byte response",
                failure_class="provider_response_invalid",
            )
        if len(body) > MAX_NATIVE_PROVIDER_RESPONSE_BYTES:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_response_budget_exceeded",
                "Direct provider response exceeds the byte budget",
                failure_class="response_budget",
            )
        return body

    @staticmethod
    def _bounded_provider_body_diagnostic(
        response: Any,
    ) -> dict[str, Any]:
        body = response.read(MAX_NATIVE_PROVIDER_RESPONSE_BYTES + 1)
        if not isinstance(body, bytes):
            return {
                "body_length": None,
                "body_sha256": None,
                "body_truncated": None,
                "body_type": body.__class__.__name__,
            }
        truncated = len(body) > MAX_NATIVE_PROVIDER_RESPONSE_BYTES
        bounded_body = body[:MAX_NATIVE_PROVIDER_RESPONSE_BYTES]
        return {
            "body_length": len(bounded_body),
            "body_sha256": hashlib.sha256(bounded_body).hexdigest(),
            "body_truncated": truncated,
        }

    @staticmethod
    def _decode_provider_payload(body: bytes) -> dict[str, Any]:
        diagnostic = {
            "body_length": len(body),
            "body_sha256": hashlib.sha256(body).hexdigest(),
        }
        try:
            payload = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_unique_provider_json_object,
                parse_constant=_reject_provider_json_constant,
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Direct provider transport returned invalid JSON",
                raw_output=diagnostic,
                failure_class="provider_response_invalid",
            ) from exc
        if not isinstance(payload, dict):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Direct provider transport returned a non-object response",
                raw_output=diagnostic,
                failure_class="provider_response_invalid",
            )
        if not _provider_i_json_is_valid(payload):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Direct provider transport returned non-I-JSON data",
                raw_output=diagnostic,
                failure_class="provider_response_invalid",
            )
        return payload

    @staticmethod
    def _provider_http_failure(
        *,
        status_code: int | None,
        diagnostic: dict[str, Any],
    ) -> Gate2SourceFactRuntimeError:
        redirect = isinstance(status_code, int) and 300 <= status_code < 400
        failure = Gate2SourceFactRuntimeError(
            (
                "gate2_model_provider_redirect_blocked"
                if redirect
                else "gate2_model_provider_http_error"
            ),
            (
                "Direct provider transport refused an HTTP redirect"
                if redirect
                else "Direct provider transport did not return HTTP 2xx"
            ),
            raw_output={
                "status_code": status_code,
                **diagnostic,
            },
            failure_class="provider_transport",
        )
        failure.provider_response_received = True
        return failure

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


# OWNER:
# Provider-specific OpenAI schema projection, response and usage interpretation.
#
# REUSE:
# Obtain this adapter through Gate2ProviderAdapterFactory.create(...).
#
# MUST NOT:
# Consumers must not parse or normalize OpenAI provider payloads.
class Gate2OpenAIResponseFormatAdapter(_Gate2OpenWebUIProviderAdapter):
    def _project_context_v2_1_budget_smoke_wire_form_data(
        self,
        form_data: dict[str, Any],
    ) -> None:
        maximum_output_tokens = form_data.get("max_tokens")
        if (
            "max_completion_tokens" in form_data
            or isinstance(maximum_output_tokens, bool)
            or not isinstance(maximum_output_tokens, int)
            or maximum_output_tokens <= 0
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "OpenAI direct output-token budget is not exact",
            )
        form_data.pop("max_tokens")
        form_data["max_completion_tokens"] = maximum_output_tokens

    def prepare_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest:
        prepared_request = super().prepare_form_data(
            form_data=form_data,
            response_format=response_format,
        )
        if prepared_request.schema_transform_count != 1:
            return prepared_request
        prepared_form_data = copy.deepcopy(prepared_request.form_data)
        json_schema = self._strict_schema(prepared_form_data["response_format"])
        json_schema.setdefault(
            "name",
            _OPENAI_ROOT_OBJECT_ENVELOPE_KEY,
        )
        result = Gate2PreparedProviderRequest(
            form_data=prepared_form_data,
            provider_visible_schema=copy.deepcopy(
                prepared_request.provider_visible_schema
            ),
            provider_adapter_id=(prepared_request.provider_adapter_id),
            canonical_schema_hash=(prepared_request.canonical_schema_hash),
            adapted_schema_hash=prepared_request.adapted_schema_hash,
            schema_transform_count=(prepared_request.schema_transform_count),
            projection_policy_version=(prepared_request.projection_policy_version),
        )
        result.validate_schema_binding()
        return result

    def _adapt_schema(self, schema: dict[str, Any]) -> int:
        return _project_openai_root_object_schema(schema)

    def extract_content(self, payload: dict[str, Any]) -> Any:
        content = super().extract_content(payload)
        if isinstance(content, str):
            try:
                decoded = json.loads(content)
            except ValueError:
                return content
            normalized = _unwrap_openai_root_object_content(decoded)
            return content if normalized is decoded else normalized
        return _unwrap_openai_root_object_content(content)

    def extract_prepared_content(
        self,
        payload: dict[str, Any],
        *,
        prepared_request: Gate2PreparedProviderRequest,
    ) -> Any:
        if not isinstance(prepared_request, Gate2PreparedProviderRequest):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Prepared provider request is required for extraction",
            )
        prepared_request.validate_schema_binding()
        content = super().extract_content(payload)
        return _extract_openai_content(
            content,
            envelope_required=(
                _openai_root_object_envelope_required(
                    prepared_request.provider_visible_schema
                )
            ),
            require_i_json=False,
        )

    def extract_context_v2_1_budget_smoke_prepared_content(
        self,
        payload: dict[str, Any],
        *,
        prepared_request: Gate2PreparedProviderRequest,
        canonical_schema: dict[str, Any],
        model_visible_request: dict[str, Any],
        exact_model_id: str,
        operation_identity: str,
    ) -> Any:
        if not isinstance(
            prepared_request,
            Gate2PreparedProviderRequest,
        ) or not prepared_request.context_v2_1_budget_smoke_contract_is_bound(
            canonical_schema=canonical_schema,
            provider_profile=self.profile,
            model_visible_request=model_visible_request,
            exact_model_id=exact_model_id,
            operation_identity=operation_identity,
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Context V2.1 budget-smoke prepared request is not exact",
            )
        _validate_context_v2_1_terminal_response(
            payload=payload,
            provider_adapter_id=self.profile.adapter_id,
        )
        content = super().extract_content(payload)
        return _extract_openai_content(
            content,
            envelope_required=(
                _openai_root_object_envelope_required(
                    prepared_request.provider_visible_schema
                )
            ),
            require_i_json=True,
        )


def _openai_root_object_envelope_required(
    provider_schema: dict[str, Any],
) -> bool:
    properties = provider_schema.get("properties")
    return (
        provider_schema.get("type") == "object"
        and provider_schema.get("additionalProperties") is False
        and isinstance(properties, dict)
        and set(properties) == {_OPENAI_ROOT_OBJECT_ENVELOPE_KEY}
        and isinstance(
            properties.get(_OPENAI_ROOT_OBJECT_ENVELOPE_KEY),
            dict,
        )
        and provider_schema.get("required") == [_OPENAI_ROOT_OBJECT_ENVELOPE_KEY]
    )


def _extract_openai_content(
    content: Any,
    *,
    envelope_required: bool | None,
    require_i_json: bool,
) -> Any:
    decoded = content
    if isinstance(content, str):
        try:
            kwargs = {
                "object_pairs_hook": _unique_provider_json_object,
            }
            if require_i_json:
                kwargs["parse_constant"] = _reject_provider_json_constant
            decoded = json.loads(content, **kwargs)
        except _DuplicateProviderJsonKeyError as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Provider response contains duplicate JSON keys",
                failure_class="provider_response_invalid",
            ) from exc
        except _NonFiniteProviderJsonConstantError as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Provider response contains a non-finite JSON number",
                failure_class="provider_response_invalid",
            ) from exc
        except ValueError:
            return content
    if require_i_json and not _provider_i_json_is_valid(decoded):
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            "Provider response contains non-I-JSON data",
            failure_class="provider_response_invalid",
        )
    normalized = _unwrap_openai_root_object_content(decoded)
    if envelope_required is True and normalized is decoded:
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            "OpenAI response is missing its required root envelope",
            failure_class="provider_response_invalid",
        )
    if normalized is not decoded:
        return normalized
    return content if isinstance(content, str) else decoded


def _validate_context_v2_1_terminal_response(
    *,
    payload: dict[str, Any],
    provider_adapter_id: str,
) -> None:
    if provider_adapter_id in {
        "openai_response_format",
        "gemini_response_format",
    }:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if (
            not isinstance(choices, list)
            or len(choices) != 1
            or not isinstance(choices[0], dict)
            or choices[0].get("finish_reason") != "stop"
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_response_not_terminal",
                "Context V2.1 requires one terminal provider choice",
                raw_output=payload,
                failure_class="provider_response_invalid",
            )
        return
    if (
        provider_adapter_id != "anthropic_native_messages"
        or not isinstance(payload, dict)
        or payload.get("stop_reason") != "end_turn"
    ):
        raise Gate2SourceFactRuntimeError(
            "gate2_model_response_not_terminal",
            "Context V2.1 requires a terminal provider response",
            raw_output=payload,
            failure_class="provider_response_invalid",
        )


class Gate2GeminiResponseFormatAdapter(_Gate2OpenWebUIProviderAdapter):
    def prepare_gate3_bounded_labeling_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest:
        """Keep the contract-owned bare-alias description model-visible."""

        prepared_request = super().prepare_gate3_bounded_labeling_form_data(
            form_data=form_data,
            response_format=response_format,
        )
        canonical_schema = self._strict_schema(response_format)["schema"]
        provider_schema = copy.deepcopy(prepared_request.provider_visible_schema)
        restored_keywords = _project_gate3_alias_description(
            canonical_schema=canonical_schema,
            provider_schema=provider_schema,
        )
        prepared_form_data = copy.deepcopy(prepared_request.form_data)
        provider_wrapper = self._strict_schema(prepared_form_data["response_format"])
        provider_wrapper["schema"] = copy.deepcopy(provider_schema)
        prepared_form_data["max_tokens"] = GATE3_GEMINI_MAX_OUTPUT_TOKENS
        result = replace(
            prepared_request,
            form_data=prepared_form_data,
            provider_visible_schema=provider_schema,
            adapted_schema_hash=_schema_hash(provider_schema),
            schema_transform_count=(
                prepared_request.schema_transform_count - restored_keywords
            ),
        )
        result.validate_schema_binding()
        return result

    def _adapt_schema(self, schema: dict[str, Any]) -> int:
        return _project_gemini_structural_schema(schema)


# OWNER:
# Provider-specific Anthropic request, response and usage interpretation.
#
# REUSE:
# Obtain this adapter through Gate2ProviderAdapterFactory.create(...).
#
# MUST NOT:
# Consumers must not build or parse Anthropic native payloads.
class Gate2AnthropicNativeMessagesAdapter(_Gate2OpenWebUIProviderAdapter):
    uses_openwebui_completion = False

    def prepare_form_data(
        self,
        *,
        form_data: dict[str, Any],
        response_format: dict[str, Any],
    ) -> Gate2PreparedProviderRequest:
        json_schema = self._strict_schema(response_format)
        schema = copy.deepcopy(json_schema["schema"])
        transform_count = _project_anthropic_structural_schema(schema)
        projection_policy_version = _validate_semantic_enum_projection(
            canonical_schema=json_schema["schema"],
            provider_schema=schema,
        )
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
            if not isinstance(content, str) or role not in {
                "system",
                "user",
                "assistant",
            }:
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
        maximum_output_tokens = form_data.get("max_tokens", 32768)
        if (
            isinstance(maximum_output_tokens, bool)
            or not isinstance(maximum_output_tokens, int)
            or maximum_output_tokens <= 0
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Anthropic output-token budget is invalid",
            )
        prepared = {
            "model": form_data.get("model"),
            "max_tokens": maximum_output_tokens,
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
        result = Gate2PreparedProviderRequest(
            form_data=prepared,
            provider_visible_schema=copy.deepcopy(schema),
            provider_adapter_id=self.profile.adapter_id,
            canonical_schema_hash=_schema_hash(json_schema["schema"]),
            adapted_schema_hash=_schema_hash(schema),
            schema_transform_count=transform_count,
            projection_policy_version=projection_policy_version,
        )
        result.validate_schema_binding()
        return result

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
        output_details = _usage_details(
            usage,
            "output_tokens_details",
            "completion_tokens_details",
        )
        input_tokens = _optional_int(usage.get("input_tokens"))
        output_tokens = _optional_int(usage.get("output_tokens"))
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
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=_normalized_usage_total(
                reported_total=usage.get("total_tokens"),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            cached_input_tokens=_first_optional_int(
                usage.get("cache_read_input_tokens"),
                usage.get("cached_input_tokens"),
            ),
            reasoning_tokens=_first_optional_int(
                output_details.get("thinking_tokens"),
                output_details.get("reasoning_tokens"),
                usage.get("reasoning_tokens"),
            ),
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
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, int)
            or not 1 <= timeout <= 600
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                "Anthropic native transport timeout is invalid",
                failure_class="provider_configuration",
            )

    def _validate_context_v2_1_budget_smoke_provider_configuration(
        self,
    ) -> None:
        if self.native_transport_config.anthropic_api_version != "2023-06-01":
            raise Gate2SourceFactRuntimeError(
                "gate2_provider_configuration_blocked",
                "Unsupported Anthropic API version",
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
                "anthropic-version": (
                    self.native_transport_config.anthropic_api_version
                ),
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
            payload = self._decode_native_messages_payload(body)
            payload.setdefault("status_code", exc.code)
            return payload
        except URLError as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_provider_unavailable",
                "Anthropic native transport is unavailable",
                raw_output={
                    "transport_error_type": exc.__class__.__name__,
                },
                failure_class="provider_transport",
            ) from exc
        if len(body) > MAX_NATIVE_PROVIDER_RESPONSE_BYTES:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_response_budget_exceeded",
                "Anthropic response exceeds the byte budget",
                failure_class="response_budget",
            )
        return self._decode_native_messages_payload(body)

    @staticmethod
    def _decode_native_messages_payload(body: bytes) -> dict[str, Any]:
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
                failure_class="provider_response_invalid",
            ) from exc
        if not isinstance(payload, dict):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Anthropic native transport returned a non-object response",
                raw_output=diagnostic,
                failure_class="provider_response_invalid",
            )
        return payload

    def _context_v2_1_budget_smoke_endpoint(
        self,
        connection: Gate2OpenWebUIProviderConnection,
    ) -> str:
        return f"{connection.base_url}/messages"

    def _context_v2_1_budget_smoke_headers(
        self,
        connection: Gate2OpenWebUIProviderConnection,
    ) -> dict[str, str]:
        return {
            "content-type": "application/json",
            "x-api-key": connection.api_key,
            "anthropic-version": (self.native_transport_config.anthropic_api_version),
        }

    def _context_v2_1_budget_smoke_semantic_headers(
        self,
    ) -> dict[str, str]:
        return {
            "content-type": "application/json",
            "authorization": "x-api-key",
            "anthropic-version": (self.native_transport_config.anthropic_api_version),
        }


_PROVIDER_ADAPTER_TYPES = {
    "openai_response_format": Gate2OpenAIResponseFormatAdapter,
    "gemini_response_format": Gate2GeminiResponseFormatAdapter,
    "anthropic_native_messages": Gate2AnthropicNativeMessagesAdapter,
}


_OPENAI_ROOT_OBJECT_ENVELOPE_KEY = "broker_reports_gate2_choice"
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
    "candidate_id",
    "code_kind",
    "choice",
    "completeness",
    "confidence",
    "coverage_status",
    "decision_kind",
    "disposition",
    "fact_subtype",
    "fact_type",
    "fact_field_path",
    "identifier_type",
    "income_type_candidate",
    "fee_type_candidate",
    "fx_fact_kind",
    "movement_type_candidate",
    "normalized_value",
    "operation_type_candidate",
    "position_kind_candidate",
    "precision",
    "reason",
    "reason_code",
    "schema_version",
    "semantic_role",
    "source_granularity",
    "source_ref",
    "status",
    "subtype_candidate",
    "withholding_type_candidate",
    "validator_status",
}

_REQUIRED_SEMANTIC_ENUM_PROPERTIES = frozenset({"choice", "reason"})


class _DuplicateProviderJsonKeyError(ValueError):
    pass


class _NonFiniteProviderJsonConstantError(ValueError):
    pass


def _reject_provider_json_constant(value: str) -> None:
    raise _NonFiniteProviderJsonConstantError(value)


def _unique_provider_json_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateProviderJsonKeyError(key)
        result[key] = value
    return result


def _provider_i_json_is_valid(value: Any) -> bool:
    pending = [value]
    while pending:
        current = pending.pop()
        if current is None or isinstance(current, (bool, int)):
            continue
        if isinstance(current, float):
            if not math.isfinite(current):
                return False
            continue
        if isinstance(current, str):
            try:
                current.encode("utf-8")
            except UnicodeEncodeError:
                return False
            continue
        if isinstance(current, list):
            pending.extend(current)
            continue
        if isinstance(current, dict):
            for key, nested in current.items():
                if not isinstance(key, str):
                    return False
                try:
                    key.encode("utf-8")
                except UnicodeEncodeError:
                    return False
                pending.append(nested)
            continue
        return False
    return True


def _project_openai_root_object_schema(schema: dict[str, Any]) -> int:
    if schema.get("type") == "object":
        return 0
    variants = schema.get("anyOf")
    if not isinstance(variants, list) or not variants:
        return 0
    canonical = copy.deepcopy(schema)
    nested = {
        key: value
        for key, value in canonical.items()
        if key not in {"$schema", "title"}
    }
    projected = {
        key: canonical[key] for key in ("$schema", "title") if key in canonical
    }
    projected.update(
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                _OPENAI_ROOT_OBJECT_ENVELOPE_KEY: nested,
            },
            "required": [_OPENAI_ROOT_OBJECT_ENVELOPE_KEY],
        }
    )
    schema.clear()
    schema.update(projected)
    return 1


def _unwrap_openai_root_object_content(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {_OPENAI_ROOT_OBJECT_ENVELOPE_KEY}:
        return value[_OPENAI_ROOT_OBJECT_ENVELOPE_KEY]
    return value


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
        if existing_enum is None and property_name in _GEMINI_PRESERVED_ENUM_PROPERTIES:
            schema["enum"] = [copy.deepcopy(constant)]
    for keyword in _GEMINI_REMOVED_SCHEMA_KEYWORDS:
        if keyword == "enum" and property_name in _GEMINI_PRESERVED_ENUM_PROPERTIES:
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
                            str(child_name) if keyword == "properties" else None
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


def _project_gate3_alias_description(
    *,
    canonical_schema: dict[str, Any],
    provider_schema: dict[str, Any],
) -> int:
    """Project wording from the canonical schema; never redefine the grammar."""

    candidate_paths = (
        ("$defs", "annotation", "properties", "target_alias"),
        ("$defs", "roleBinding", "properties", "target_alias"),
        ("$defs", "classification", "properties", "assertion_id"),
    )
    path = next(
        (
            candidate
            for candidate in candidate_paths
            if _schema_value_at_path(canonical_schema, candidate) is not None
        ),
        None,
    )
    if path is None:
        raise Gate2SourceFactRuntimeError(
            "gate2_model_request_invalid",
            "Gate 3 bare-alias schema projection is not exact",
        )
    canonical_alias: Any = canonical_schema
    provider_alias: Any = provider_schema
    for field in path:
        canonical_alias = (
            canonical_alias.get(field) if isinstance(canonical_alias, dict) else None
        )
        provider_alias = (
            provider_alias.get(field) if isinstance(provider_alias, dict) else None
        )
    description = (
        canonical_alias.get("description")
        if isinstance(canonical_alias, dict)
        else None
    )
    if (
        not isinstance(description, str)
        or not description
        or not isinstance(canonical_alias.get("pattern"), str)
        or canonical_alias.get("type") != "string"
        or not isinstance(provider_alias, dict)
        or provider_alias.get("type") != "string"
        or "enum" in provider_alias
    ):
        raise Gate2SourceFactRuntimeError(
            "gate2_model_request_invalid",
            "Gate 3 bare-alias schema projection is not exact",
        )
    changed = provider_alias.get("description") != description
    provider_alias["description"] = description
    return int(changed)


def _schema_value_at_path(schema: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = schema
    for field in path:
        value = value.get(field) if isinstance(value, dict) else None
    return value


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


def _validate_semantic_enum_projection(
    *,
    canonical_schema: dict[str, Any],
    provider_schema: dict[str, Any],
) -> str | None:
    canonical = _semantic_enums(canonical_schema)
    if not canonical:
        return None
    projected = _semantic_enums(provider_schema)
    if projected != canonical:
        raise Gate2SourceFactRuntimeError(
            "gate2_provider_schema_semantic_enum_removed",
            "Provider schema projection removed a required semantic enum",
        )
    return CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION


def _semantic_enums(value: Any) -> dict[str, tuple[tuple[Any, ...], ...]]:
    found: dict[str, list[tuple[Any, ...]]] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                for name, schema in properties.items():
                    if (
                        name in _REQUIRED_SEMANTIC_ENUM_PROPERTIES
                        and isinstance(schema, dict)
                        and isinstance(schema.get("enum"), list)
                    ):
                        found.setdefault(name, []).append(
                            tuple(copy.deepcopy(schema["enum"]))
                        )
                    visit(schema)
            for key, child in node.items():
                if key != "properties":
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return {
        name: tuple(
            sorted(
                values,
                key=lambda item: json.dumps(
                    item,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
            )
        )
        for name, values in sorted(found.items())
    }


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
    if "reasoning_effort" in rendered or "thinking_config" in rendered:
        return "gate2_model_reasoning_control_rejected"
    if "oneof" in rendered or "one_of" in rendered:
        return "gate2_model_schema_oneof_unsupported"
    if source_profile:
        if "required" in rendered and "properties" in rendered:
            return "gate2_model_schema_required_properties_invalid"
        if "additionalproperties" in rendered or "additional_properties" in rendered:
            return "gate2_model_schema_additional_properties_invalid"
        if (
            "must have a 'type' key" in rendered
            or 'must have a \\"type\\" key' in rendered
        ):
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
    if "model" in rendered and (
        "not found" in rendered or "unavailable" in rendered or "404" in rendered
    ):
        return "gate2_model_unavailable"
    if (
        "unauthorized" in rendered
        or "authentication" in rendered
        or "api key" in rendered
    ):
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


def _first_optional_int(*values: Any) -> int | None:
    for value in values:
        parsed = _optional_int(value)
        if parsed is not None:
            return parsed
    return None


def _normalized_usage_total(
    *,
    reported_total: Any,
    input_tokens: int | None,
    output_tokens: int | None,
) -> int | None:
    total_tokens = _optional_int(reported_total)
    if total_tokens is not None:
        return total_tokens
    if (
        reported_total is None
        and input_tokens is not None
        and output_tokens is not None
    ):
        return input_tokens + output_tokens
    return None


def _usage_details(
    usage: dict[str, Any],
    *field_names: str,
) -> dict[str, Any]:
    for field_name in field_names:
        value = usage.get(field_name)
        if isinstance(value, dict):
            return value
    return {}
