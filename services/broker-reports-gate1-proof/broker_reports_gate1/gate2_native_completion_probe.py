"""Temporary, source-free native OpenWebUI completion diagnostic."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .gate2_model_clients import Gate2StructuredModelClientFactory
from .gate2_model_contracts import (
    GATE2_COMPLETION_ACCESS_MODE_ORDINARY_USER,
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
)
from .gate2_model_requests import (
    PRIVATE_NATIVE_COMPLETION_PROBE_PACKAGE_MARKER,
    PRIVATE_NATIVE_COMPLETION_PROBE_REQUEST_PROFILE,
)
from .gate2_source_fact_contracts import Gate2ManagedPrompt


FACTORY_REQUIRED = (
    "Gate2NativeCompletionProbeFactory.create is the only private native "
    "completion diagnostic constructor"
)
FORBIDDEN = (
    "The diagnostic must not accept documents, Canonical data, artifacts, "
    "chat state or a direct provider client"
)

_SCHEMA_VERSION = "private_native_completion_probe_v1"
_SUCCESS = "NATIVE_BRIDGE_PROBE_READY"
_MODEL_ROUTE_UNAVAILABLE = "NATIVE_BRIDGE_PROBE_MODEL_ROUTE_UNAVAILABLE"
_REQUEST_REJECTED = "NATIVE_BRIDGE_PROBE_REQUEST_REJECTED"
_RESPONSE_INVALID = "NATIVE_BRIDGE_PROBE_RESPONSE_INVALID"
_CALL_FAILED = "NATIVE_BRIDGE_PROBE_CALL_FAILED"


class Gate2NativeCompletionProbeFactory:
    def create(
        self,
        *,
        request: Any,
        user: Any,
        provider_profile_id: str,
        model_id: str,
        completion_resolver: Any,
    ) -> "Gate2NativeCompletionProbe":
        return Gate2NativeCompletionProbe(
            request=request,
            user=user,
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            completion_resolver=completion_resolver,
        )


class Gate2NativeCompletionProbe:
    def __init__(
        self,
        *,
        request: Any,
        user: Any,
        provider_profile_id: str,
        model_id: str,
        completion_resolver: Any,
    ) -> None:
        self.request = request
        self.user = user
        self.provider_profile_id = provider_profile_id
        self.model_id = model_id
        self.completion_resolver = completion_resolver

    async def execute(self) -> str:
        try:
            client = Gate2StructuredModelClientFactory(
                config=Gate2StructuredModelClientConfig(
                    request_profile=PRIVATE_NATIVE_COMPLETION_PROBE_REQUEST_PROFILE,
                    provider_profile_id=self.provider_profile_id,
                    capability_probe=False,
                    economy_budget_enforcement=False,
                    completion_access_mode=GATE2_COMPLETION_ACCESS_MODE_ORDINARY_USER,
                ),
                user=self.user,
                request=self.request,
                completion_resolver=self.completion_resolver,
            ).create()
            result = await client.extract(
                prompt=_prompt(),
                package={"schema_version": _SCHEMA_VERSION},
                model_id=self.model_id,
                response_format=_response_format(),
            )
        except Gate2SourceFactRuntimeError as exc:
            return _failure_terminal(exc.code)
        except Exception:
            return _CALL_FAILED
        return _SUCCESS if _response_is_valid(result.content) else _RESPONSE_INVALID


def _prompt() -> Gate2ManagedPrompt:
    content = (
        "Return exactly one JSON object with status equal to ok. "
        + PRIVATE_NATIVE_COMPLETION_PROBE_PACKAGE_MARKER
    )
    return Gate2ManagedPrompt(
        prompt_ref="private_native_completion_probe",
        command=None,
        version="v1",
        content=content,
        hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        source="code_bound_diagnostic",
        template_id="private_native_completion_probe",
        template_kind="diagnostic",
        prompt_contract_id=_SCHEMA_VERSION,
        input_schema_version=_SCHEMA_VERSION,
        output_schema_id=_SCHEMA_VERSION,
        output_schema_version="v1",
        tags=(),
        safe_metadata={},
    )


def _response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": _SCHEMA_VERSION,
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"status": {"type": "string", "enum": ["ok"]}},
                "required": ["status"],
            },
        },
    }


def _response_is_valid(content: Any) -> bool:
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            return False
    return content == {"status": "ok"}


def _failure_terminal(code: Any) -> str:
    value = str(code or "")
    if value in {
        "gate2_model_unavailable",
        "gate2_no_strict_structured_provider_available",
    }:
        return _MODEL_ROUTE_UNAVAILABLE
    if value in {
        "gate2_model_reasoning_control_rejected",
        "gate2_model_schema_oneof_unsupported",
        "gate2_model_provider_error",
        "private_native_completion_probe_request_invalid",
    }:
        return _REQUEST_REJECTED
    if value in {
        "gate2_model_invalid_response",
        "gate2_model_response_budget_exceeded",
    }:
        return _RESPONSE_INVALID
    return _CALL_FAILED
