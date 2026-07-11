from __future__ import annotations

import inspect
import json
from typing import Any, Callable

from .gate2_model_contracts import (
    PROVIDER_STATUS_APPROVED,
    Gate2ProviderProfile,
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelResult,
    gate2_provider_profile,
)
from .gate2_model_requests import (
    SOURCE_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)


FACTORY_REQUIRED = (
    "Gate2StructuredModelClientFactory.create is the only production Gate 2 model client entrypoint"
)
FORBIDDEN = (
    "Pipes, control checks and smoke scripts must not call OpenWebUI completion functions or provider SDKs directly"
)


CompletionResolver = Callable[[str], Any]


class Gate2StructuredModelClientFactory:
    def __init__(
        self,
        *,
        config: Gate2StructuredModelClientConfig,
        user: Any,
        request: Any,
        completion_resolver: CompletionResolver | None = None,
    ) -> None:
        self.config = config
        self.user = user
        self.request = request
        self.completion_resolver = completion_resolver

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
        if (
            not self.config.capability_probe
            and provider_profile.gate2_status != PROVIDER_STATUS_APPROVED
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_no_strict_structured_provider_available",
                "Selected provider is not approved for strict Gate 2 structured output",
            )
        return Gate2OpenWebUIStructuredModelClient(
            request_profile=self.config.request_profile,
            provider_profile=provider_profile,
            request_builder=request_builder,
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
        user: Any,
        request: Any,
        completion_resolver: CompletionResolver | None,
    ) -> None:
        self.request_profile = request_profile
        self.provider_profile = provider_profile
        self.request_builder = request_builder
        self.user = user
        self.request = request
        self.completion_resolver = (
            completion_resolver or self._resolve_openwebui_completion_dependencies
        )

    async def extract(self, *, prompt, package, model_id, response_format):
        user_id = self._validate_request_context()
        self._validate_strict_response_format(response_format)
        form_data = self.request_builder.build(
            prompt=prompt,
            package=package,
            model_id=model_id,
            response_format=response_format,
        )
        try:
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
            response = self._invoke_completion_once(
                completion_fn=completion_fn,
                form_data=form_data,
                user_model=user_model,
            )
            if inspect.isawaitable(response):
                response = await response
        except Gate2SourceFactRuntimeError:
            raise
        except Exception as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_call_failed",
                exc.__class__.__name__,
            ) from exc
        return Gate2StructuredModelResult(
            content=self._extract_completion_content(response)
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

    def _validate_strict_response_format(
        self, response_format: dict[str, Any]
    ) -> None:
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

    def _resolve_openwebui_completion_dependencies(self, user_id: str):
        try:
            from open_webui.utils.chat import generate_chat_completion as completion_fn
        except Exception:
            from open_webui.main import generate_chat_completions as completion_fn
        from open_webui.models.users import Users

        return completion_fn, Users.get_user_by_id(user_id)

    def _extract_completion_content(self, response: Any) -> Any:
        if isinstance(response, dict):
            return self._completion_dict_content(response)
        body = getattr(response, "body", None)
        if isinstance(body, bytes):
            try:
                return self._completion_dict_content(json.loads(body.decode("utf-8")))
            except (UnicodeDecodeError, ValueError) as exc:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_invalid_response",
                    self._invalid_body_message(),
                ) from exc
        if isinstance(response, str):
            return response
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            self._unsupported_response_message(),
        )

    def _completion_dict_content(self, payload: dict[str, Any]) -> Any:
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
        if "detail" in payload or "error" in payload:
            raise Gate2SourceFactRuntimeError(
                self._provider_error_code(payload),
                self._provider_error_message(),
                raw_output=payload,
            )
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            self._missing_content_message(),
        )

    def _provider_error_code(self, payload: dict[str, Any]) -> str:
        rendered = json.dumps(payload, ensure_ascii=True, sort_keys=True).lower()
        if "oneof" in rendered or "one_of" in rendered:
            return "gate2_model_schema_oneof_unsupported"
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            if "required" in rendered and "properties" in rendered:
                return "gate2_model_schema_required_properties_invalid"
            if (
                "additionalproperties" in rendered
                or "additional_properties" in rendered
            ):
                return "gate2_model_schema_additional_properties_invalid"
            if (
                "must have a 'type' key" in rendered
                or 'must have a \\"type\\" key' in rendered
            ):
                return "gate2_model_schema_type_key_missing"
            if "nullable" in rendered or "invalid nullable" in rendered:
                return "gate2_model_schema_nullable_type_invalid"
        if (
            "response_format" in rendered
            or "json_schema" in rendered
            or "schema" in rendered
        ):
            return "gate2_model_schema_response_format_rejected"
        context_markers = ("context_length", "too many tokens")
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            context_markers += ("maximum context",)
        if any(marker in rendered for marker in context_markers):
            return "gate2_model_context_budget_exceeded"
        quota_markers = (
            "insufficient_quota",
            "insufficient quota",
            "quota_exceeded",
            "quota exceeded",
            "exceeded your current quota",
            "billing hard limit",
        )
        if any(marker in rendered for marker in quota_markers):
            return "gate2_model_provider_quota_exceeded"
        provider_status_codes = self._provider_status_codes(payload)
        rate_limit_markers = (
            "rate_limit",
            "rate limit",
            "too many requests",
            "request limit exceeded",
        )
        if 429 in provider_status_codes or any(
            marker in rendered for marker in rate_limit_markers
        ):
            return "gate2_model_provider_rate_limited"
        if "model" in rendered and (
            "not found" in rendered or "unavailable" in rendered
        ):
            return "gate2_model_unavailable"
        if (
            "unauthorized" in rendered
            or "authentication" in rendered
            or "api key" in rendered
        ):
            return "gate2_model_provider_auth_failed"
        availability_markers = (
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
        if provider_status_codes & {500, 502, 503, 504} or any(
            marker in rendered for marker in availability_markers
        ):
            return "gate2_model_provider_unavailable"
        return "gate2_model_provider_error"

    @staticmethod
    def _provider_status_codes(payload: dict[str, Any]) -> set[int]:
        values: list[Any] = []
        for candidate in (
            payload,
            payload.get("error"),
            payload.get("detail"),
        ):
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
                continue
            if isinstance(value, str) and value.strip().isdigit():
                result.add(int(value.strip()))
        return result

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

    def _missing_content_message(self) -> str:
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            return "Completion response has no structured content"
        return "No structured completion content"

    def _provider_error_message(self) -> str:
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            return "Provider returned a typed error object"
        return "Provider returned a typed error"

    @staticmethod
    def _user_id(user: Any) -> str:
        if isinstance(user, dict):
            return str(user.get("id") or user.get("user_id") or "")
        return str(getattr(user, "id", "") or "")
