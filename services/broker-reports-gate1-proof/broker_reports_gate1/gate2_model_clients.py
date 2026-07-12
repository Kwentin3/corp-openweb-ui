from __future__ import annotations

import hashlib
import inspect
import json
import time
from typing import Any, Callable

from .gate2_model_contracts import (
    PROVIDER_STATUS_APPROVED,
    PROVIDER_STATUS_PROBE_REQUIRED,
    Gate2ProviderProfile,
    Gate2ProviderExecutionMetadata,
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelResult,
    gate2_provider_profile,
)
from .gate2_model_requests import (
    SOURCE_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from .gate2_provider_adapters import (
    Gate2NativeProviderTransportConfig,
    Gate2ProviderAdapter,
    Gate2ProviderAdapterFactory,
    provider_error_code,
)


FACTORY_REQUIRED = (
    "Gate2StructuredModelClientFactory.create is the only production Gate 2 model client entrypoint"
)
FORBIDDEN = (
    "Pipes, control checks and smoke scripts must not call OpenWebUI completion functions or provider SDKs directly"
)


CompletionResolver = Callable[[str], Any]
NativeTransportResolver = Callable[[Gate2ProviderProfile, dict[str, Any]], Any]
MAX_PRIVATE_INVALID_RESPONSE_BYTES = 65_536
MAX_MODEL_CONTENT_BYTES = 524_288
MAX_MODEL_CONTENT_NODES = 20_000
MAX_MODEL_CONTENT_DEPTH = 64
MAX_MODEL_STRING_BYTES = 131_072


class Gate2StructuredModelClientFactory:
    def __init__(
        self,
        *,
        config: Gate2StructuredModelClientConfig,
        user: Any,
        request: Any,
        completion_resolver: CompletionResolver | None = None,
        native_transport_resolver: NativeTransportResolver | None = None,
        native_transport_config: Gate2NativeProviderTransportConfig | None = None,
    ) -> None:
        self.config = config
        self.user = user
        self.request = request
        self.completion_resolver = completion_resolver
        self.native_transport_resolver = native_transport_resolver
        self.native_transport_config = (
            native_transport_config or Gate2NativeProviderTransportConfig()
        )

    def create(self) -> "Gate2OpenWebUIStructuredModelClient":
        if self.config.transport != "openwebui":
            raise Gate2SourceFactRuntimeError(
                "gate2_model_transport_unsupported",
                "Unsupported Gate 2 model transport",
            )
        request_builder = Gate2OpenWebUIRequestBuilder(
            request_profile=self.config.request_profile
        )
        provider_profile = gate2_provider_profile(self.config.provider_profile_id)
        probe_allowed = (
            self.config.capability_probe
            and provider_profile.gate2_status == PROVIDER_STATUS_PROBE_REQUIRED
        )
        if provider_profile.gate2_status != PROVIDER_STATUS_APPROVED and not probe_allowed:
            raise Gate2SourceFactRuntimeError(
                "gate2_no_strict_structured_provider_available",
                "Selected provider is not approved for strict Gate 2 structured output",
            )
        provider_adapter = Gate2ProviderAdapterFactory(
            profile=provider_profile,
            capability_probe=self.config.capability_probe,
            native_transport_config=self.native_transport_config,
            native_transport_resolver=self.native_transport_resolver,
        ).create()
        return Gate2OpenWebUIStructuredModelClient(
            request_profile=self.config.request_profile,
            provider_profile=provider_profile,
            request_builder=request_builder,
            provider_adapter=provider_adapter,
            user=self.user,
            request=self.request,
            completion_resolver=self.completion_resolver,
        )


class Gate2OpenWebUIStructuredModelClient:
    def __init__(
        self,
        *,
        request_profile: str,
        provider_profile: Gate2ProviderProfile,
        request_builder: Gate2OpenWebUIRequestBuilder,
        provider_adapter: Gate2ProviderAdapter,
        user: Any,
        request: Any,
        completion_resolver: CompletionResolver | None,
    ) -> None:
        self.request_profile = request_profile
        self.provider_profile = provider_profile
        self.request_builder = request_builder
        self.provider_adapter = provider_adapter
        self.user = user
        self.request = request
        self.completion_resolver = (
            completion_resolver or self._resolve_openwebui_completion_dependencies
        )

    def execution_contract(self, model_id: str) -> Gate2ProviderExecutionMetadata:
        return self.provider_adapter.execution_contract(model_id)

    async def extract(self, *, prompt, package, model_id, response_format):
        user_id = self._validate_request_context()
        execution_contract = self.execution_contract(model_id)
        self.provider_adapter.validate_model(model_id)
        form_data = self.request_builder.build(
            prompt=prompt,
            package=package,
            model_id=model_id,
            response_format=response_format,
        )
        prepared_request = self.provider_adapter.prepare_form_data(
            form_data=form_data,
            response_format=response_format,
        )
        form_data = prepared_request.form_data
        started: float | None = None
        response_payload: dict[str, Any] | None = None
        try:
            if not self.provider_adapter.uses_openwebui_completion:
                self.provider_adapter.validate_transport_configuration()
                started = time.monotonic()
                response = self.provider_adapter.invoke_native_once(form_data)
            else:
                dependencies = self.completion_resolver(user_id)
                if inspect.isawaitable(dependencies):
                    dependencies = await dependencies
                completion_fn, user_model = dependencies
                if inspect.isawaitable(user_model):
                    user_model = await user_model
                if user_model is None:
                    raise Gate2SourceFactRuntimeError(
                        "gate2_model_unavailable",
                        self._user_unavailable_message(),
                    )
                started = time.monotonic()
                response = self._invoke_completion_once(
                    completion_fn=completion_fn,
                    form_data=form_data,
                    user_model=user_model,
                )
            if inspect.isawaitable(response):
                response = await response
            response_payload = self._response_payload(response)
            duration_ms = self._duration_ms(started)
            if "detail" in response_payload or "error" in response_payload:
                self._validate_model_content_budget(response_payload)
            execution_metadata = self.provider_adapter.execution_metadata(
                payload=response_payload,
                requested_model_id=model_id,
                duration_ms=duration_ms,
                prepared_request=prepared_request,
            )
            self.provider_adapter.validate_execution_metadata(execution_metadata)
            if "detail" in response_payload or "error" in response_payload:
                raise Gate2SourceFactRuntimeError(
                    provider_error_code(
                        response_payload,
                        source_profile=self.request_profile == SOURCE_REQUEST_PROFILE,
                    ),
                    self._provider_error_message(),
                    raw_output=response_payload,
                    execution_metadata=execution_metadata,
                    failure_class="provider_error_response",
                )
            content = self.provider_adapter.extract_content(response_payload)
            self._validate_model_content_budget(content)
        except Gate2SourceFactRuntimeError as exc:
            if exc.execution_metadata is None:
                metadata_payload = (
                    None
                    if exc.code == "gate2_model_response_budget_exceeded"
                    else response_payload
                )
                exc.execution_metadata = self.provider_adapter.execution_metadata(
                    payload=metadata_payload,
                    requested_model_id=model_id,
                    duration_ms=self._duration_ms(started),
                    prepared_request=prepared_request,
                )
            raise
        except Exception as exc:
            diagnostic_text = str(exc)
            diagnostic = {
                "error": {
                    "type": exc.__class__.__name__,
                    "message_length": len(diagnostic_text),
                    "message_sha256": hashlib.sha256(
                        diagnostic_text.encode("utf-8")
                    ).hexdigest(),
                }
            }
            raise Gate2SourceFactRuntimeError(
                "gate2_model_call_failed",
                exc.__class__.__name__,
                raw_output=diagnostic,
                execution_metadata=self.provider_adapter.execution_metadata(
                    payload=response_payload,
                    requested_model_id=model_id,
                    duration_ms=self._duration_ms(started),
                    prepared_request=prepared_request,
                ),
                failure_class=exc.__class__.__name__,
            ) from exc
        return Gate2StructuredModelResult(
            content=content,
            structured_output_mode=execution_contract.structured_output_mode,
            response_format_type=execution_contract.response_format_type,
            response_format_schema_mode=(
                execution_contract.response_format_schema_mode
            ),
            execution_metadata=execution_metadata,
        )

    def _validate_request_context(self) -> str:
        user_id = self._user_id(self.user)
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            if self.request is None:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_unavailable",
                    "OpenWebUI request object is required",
                )
            if not user_id:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_unavailable",
                    "Authenticated OpenWebUI user is required",
                )
            return user_id
        if self.request is None or not user_id:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_unavailable",
                "Authenticated OpenWebUI request is required",
            )
        return user_id

    def _invoke_completion_once(self, *, completion_fn, form_data, user_model):
        variants = (
            (
                (),
                {
                    "request": self.request,
                    "form_data": form_data,
                    "user": user_model,
                    "bypass_filter": True,
                    "bypass_system_prompt": True,
                },
            ),
            (
                (),
                {
                    "request": self.request,
                    "form_data": form_data,
                    "user": user_model,
                },
            ),
            ((self.request, form_data, user_model), {}),
        )
        try:
            signature = inspect.signature(completion_fn)
        except (TypeError, ValueError):
            args, kwargs = variants[0]
            return completion_fn(*args, **kwargs)
        for args, kwargs in variants:
            try:
                signature.bind(*args, **kwargs)
            except TypeError:
                continue
            return completion_fn(*args, **kwargs)
        raise TypeError("Unsupported OpenWebUI completion function signature")

    @staticmethod
    def _duration_ms(started: float | None) -> int | None:
        if started is None:
            return None
        return max(0, round((time.monotonic() - started) * 1000))

    def _resolve_openwebui_completion_dependencies(self, user_id: str):
        try:
            from open_webui.utils.chat import generate_chat_completion as completion_fn
        except Exception:
            from open_webui.main import generate_chat_completions as completion_fn
        from open_webui.models.users import Users

        return completion_fn, Users.get_user_by_id(user_id)

    def _response_payload(self, response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            return response
        body = getattr(response, "body", None)
        if isinstance(body, bytes):
            body_diagnostic = {
                "response_type": response.__class__.__name__,
                "body_length": len(body),
                "body_sha256": hashlib.sha256(body).hexdigest(),
            }
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_invalid_response",
                    self._invalid_body_message(),
                    raw_output=body_diagnostic,
                ) from exc
            if isinstance(payload, dict):
                return payload
            if (
                isinstance(payload, list)
                and len(payload) == 1
                and isinstance(payload[0], dict)
                and ("error" in payload[0] or "detail" in payload[0])
            ):
                return payload[0]
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                self._invalid_body_message(),
                raw_output=(
                    payload
                    if len(body) <= MAX_PRIVATE_INVALID_RESPONSE_BYTES
                    else {
                        **body_diagnostic,
                        "body_json_type": type(payload).__name__,
                    }
                ),
            )
        if isinstance(response, str):
            return {"content": response}
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            self._unsupported_response_message(),
            raw_output={"response_type": response.__class__.__name__},
        )

    @staticmethod
    def _validate_model_content_budget(content: Any) -> None:
        try:
            if isinstance(content, str):
                encoded = content.encode("utf-8")
            else:
                encoded = json.dumps(
                    content,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
        except (RecursionError, TypeError, ValueError) as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_response_budget_exceeded",
                "Model response cannot be bounded safely",
                raw_output={
                    "response_budget": {
                        "reason": "serialization_failed",
                        "content_type": content.__class__.__name__,
                    }
                },
                failure_class="response_budget",
            ) from exc
        digest = hashlib.sha256(encoded).hexdigest()
        if len(encoded) > MAX_MODEL_CONTENT_BYTES:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_response_budget_exceeded",
                "Model response exceeds the byte budget",
                raw_output={
                    "response_budget": {
                        "reason": "bytes",
                        "observed": len(encoded),
                        "allowed": MAX_MODEL_CONTENT_BYTES,
                        "content_sha256": digest,
                    }
                },
                failure_class="response_budget",
            )
        bounded_value = content
        if isinstance(content, str):
            try:
                bounded_value = json.loads(content)
            except RecursionError as exc:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_response_budget_exceeded",
                    "Model response exceeds the JSON nesting budget",
                    raw_output={
                        "response_budget": {
                            "reason": "json_nesting",
                            "bytes": len(encoded),
                            "content_sha256": digest,
                        }
                    },
                    failure_class="response_budget",
                ) from exc
            except ValueError:
                bounded_value = content
        nodes_total = 0
        max_depth = 0
        stack: list[tuple[Any, int]] = [(bounded_value, 1)]
        seen_containers: set[int] = set()
        while stack:
            value, depth = stack.pop()
            nodes_total += 1
            max_depth = max(max_depth, depth)
            if nodes_total > MAX_MODEL_CONTENT_NODES:
                reason = "nodes"
                observed = nodes_total
                allowed = MAX_MODEL_CONTENT_NODES
                break
            if depth > MAX_MODEL_CONTENT_DEPTH:
                reason = "depth"
                observed = depth
                allowed = MAX_MODEL_CONTENT_DEPTH
                break
            if isinstance(value, str) and len(value.encode("utf-8")) > MAX_MODEL_STRING_BYTES:
                reason = "string_bytes"
                observed = len(value.encode("utf-8"))
                allowed = MAX_MODEL_STRING_BYTES
                break
            if isinstance(value, dict):
                identity = id(value)
                if identity in seen_containers:
                    continue
                seen_containers.add(identity)
                for key, child in value.items():
                    if len(str(key).encode("utf-8")) > MAX_MODEL_STRING_BYTES:
                        reason = "key_bytes"
                        observed = len(str(key).encode("utf-8"))
                        allowed = MAX_MODEL_STRING_BYTES
                        break
                    stack.append((child, depth + 1))
                else:
                    continue
                break
            if isinstance(value, list):
                identity = id(value)
                if identity in seen_containers:
                    continue
                seen_containers.add(identity)
                stack.extend((child, depth + 1) for child in value)
        else:
            return
        raise Gate2SourceFactRuntimeError(
            "gate2_model_response_budget_exceeded",
            "Model response exceeds the structural budget",
            raw_output={
                "response_budget": {
                    "reason": reason,
                    "observed": observed,
                    "allowed": allowed,
                    "bytes": len(encoded),
                    "nodes": nodes_total,
                    "max_depth": max_depth,
                    "content_sha256": digest,
                }
            },
            failure_class="response_budget",
        )

    def _user_unavailable_message(self) -> str:
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            return "OpenWebUI user model is unavailable"
        return "OpenWebUI user is unavailable"

    def _invalid_body_message(self) -> str:
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            return "Completion response body is not JSON"
        return "Completion body is not JSON"

    def _unsupported_response_message(self) -> str:
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            return "Unsupported completion response shape"
        return "Unsupported completion response"

    def _provider_error_message(self) -> str:
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            return "Provider returned a typed error object"
        return "Provider returned a typed error"

    @staticmethod
    def _user_id(user: Any) -> str:
        if isinstance(user, dict):
            return str(user.get("id") or user.get("user_id") or "")
        return str(getattr(user, "id", "") or "")
