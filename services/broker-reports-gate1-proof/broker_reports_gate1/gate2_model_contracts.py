from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .gate2_source_fact_contracts import Gate2ManagedPrompt


PROVIDER_STATUS_APPROVED = "approved"
PROVIDER_STATUS_PROBE_REQUIRED = "probe_required"
PROVIDER_STATUS_UNSUPPORTED = "unsupported"


class Gate2SourceFactRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, raw_output: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.raw_output = raw_output


@dataclass(frozen=True)
class Gate2StructuredModelResult:
    content: Any
    structured_output_mode: str = "openwebui_response_format_json_schema"
    response_format_type: str = "json_schema"
    response_format_schema_mode: str | None = "strict_json_schema"
    fallback_used: bool = False
    repair_attempt_count: int = 0


class Gate2StructuredModelClient(Protocol):
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
    ),
    Gate2ProviderProfile(
        profile_id="anthropic_claude",
        provider_id="anthropic",
        model_family="claude",
        documented_output_mode="strict_final_json_schema",
        supports_strict_final_json_schema=True,
        supports_strict_tool_input=True,
        supports_any_of=True,
        supports_const=True,
        supports_additional_properties_false=True,
        gate2_status=PROVIDER_STATUS_PROBE_REQUIRED,
    ),
    Gate2ProviderProfile(
        profile_id="google_gemini",
        provider_id="google",
        model_family="gemini",
        documented_output_mode="json_schema_subset",
        supports_strict_final_json_schema=True,
        supports_strict_tool_input=False,
        supports_any_of=True,
        supports_const=False,
        supports_additional_properties_false=True,
        gate2_status=PROVIDER_STATUS_PROBE_REQUIRED,
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


@dataclass(frozen=True)
class Gate2StructuredModelClientConfig:
    request_profile: str
    provider_profile_id: str = "openai_gpt"
    transport: str = "openwebui"
    capability_probe: bool = False
