"""Factory-backed bounded VLM contract for visual-table proposals.

Only one declared page image or one declared table-crop image crosses the
provider boundary.  Gemini and OpenAI are replaceable proposal providers; the
deterministic contract validator remains the sole promotion authority.  This
module does not claim Pipe/bundle, live-provider, or stage integration.
Acceptance is disabled until deterministic evidence origin is authenticated
by a future server-owned integration boundary.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from .architecture_policy import VISUAL_RECOVERY_PRODUCTION_PROVIDER_PROFILES
from .visual_table_vlm_contracts import (
    VISUAL_TABLE_ACCEPTANCE_STATUS,
    VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION,
    VISUAL_TABLE_RESULT_SCHEMA_VERSION,
    VISUAL_TABLE_TERMINAL_RESULTS,
    VISUAL_TABLE_VALIDATOR_VERSION,
    VisualTableContractConfig,
    VisualTableContractError,
    VisualTableProposalValidator,
    canonical_json_bytes,
    parse_visual_table_proposal,
    sha256_json,
    validate_visual_table_scope,
    visual_table_proposal_json_schema,
)


VISUAL_TABLE_RUNTIME_POLICY_VERSION = "broker_reports_visual_table_vlm_policy_v1"
VISUAL_TABLE_IMPLEMENTATION_STATUS = "contract_scaffold_not_runtime_integrated"
VISUAL_TABLE_PROMPT_ID = "broker_reports_visual_table_structured_transcription"
VISUAL_TABLE_PROMPT_VERSION = "v1"
VISUAL_TABLE_PROMPT_TEXT = (
    "Inspect only the supplied declared page or declared table crop. Return the "
    "strict JSON proposal schema. Transcribe visible source text literally; do "
    "not calculate, normalize, infer business meaning, or fill missing values. "
    "Represent every detected table region, ordered row and column, cell, merged "
    "span, header association, total/subtotal structural role, continuation "
    "evidence, uncertainty, omission, and source-region relationship. Every "
    "provided source_region_ref must be owned exactly once by a cell or omission. "
    "Set unsupported or unresolved explicitly when the bounded image cannot "
    "support a complete proposal. You are proposing evidence, never publishing "
    "a canonical table. Do not return confidence, agreement, commentary, markdown, "
    "or any property outside the schema."
)
VISUAL_TABLE_PROMPT_SHA256 = hashlib.sha256(
    VISUAL_TABLE_PROMPT_TEXT.encode("utf-8")
).hexdigest()

PRODUCTION_VISUAL_PROVIDER_PROFILE_IDS = frozenset({"google_gemini", "openai_gpt"})
if PRODUCTION_VISUAL_PROVIDER_PROFILE_IDS != (
    VISUAL_RECOVERY_PRODUCTION_PROVIDER_PROFILES
):
    raise RuntimeError("visual_table_provider_profiles_architecture_drift")

FACTORY_REQUIRED = (
    "VisualTableRecoveryFactory.create and VisualTableProviderAdapterFactory.create "
    "are the required candidate visual-table integration path; no deployed "
    "runtime integration is asserted"
)
FORBIDDEN = (
    "Callers must not invoke provider boundaries directly, upload a whole document, "
    "add a production provider beyond Gemini/OpenAI, trust confidence/agreement, "
    "or publish a model proposal as canonical"
)

_FACTORY_TOKEN = object()


class VisualTableProviderBoundaryError(RuntimeError):
    """Expected external completion failure at the irreversible network boundary."""

    def __init__(
        self,
        code: str = "visual_table_provider_boundary_failed",
        *,
        request: VisualProviderBoundaryRequest | None = None,
    ) -> None:
        self.code = code
        self.request = request
        super().__init__(code)


class VisualTableProviderRequestError(RuntimeError):
    """A local request was rejected before the external boundary was crossed."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class VisualTableRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VisualProviderProfile:
    profile_id: str
    provider_id: str
    adapter_id: str
    adapter_version: str
    model_id: str


@dataclass(frozen=True)
class VisualProviderBoundaryRequest:
    profile_id: str
    provider_id: str
    adapter_id: str
    adapter_version: str
    model_id: str
    request_ref: str
    image_sha256: str
    request_payload_sha256: str
    request_payload_bytes: int
    response_byte_limit: int
    wire_payload: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class VisualProviderCompletion:
    value: bytes | str | dict[str, Any] = field(repr=False)
    request: VisualProviderBoundaryRequest


class VisualCompletionBoundary(Protocol):
    def complete(
        self, request: VisualProviderBoundaryRequest
    ) -> bytes | str | dict[str, Any]: ...


class VisualTableProviderAdapter(Protocol):
    profile: VisualProviderProfile

    def complete(
        self,
        *,
        request_ref: str,
        provider_context: dict[str, Any],
        image_bytes: bytes,
        image_mime_type: str,
        response_schema: dict[str, Any],
        max_output_tokens: int,
        maximum_request_bytes: int,
        maximum_response_bytes: int,
    ) -> VisualProviderCompletion: ...


def visual_provider_profile(profile_id: str, *, model_id: str) -> VisualProviderProfile:
    if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 255:
        raise VisualTableRuntimeError("visual_table_provider_model_id_invalid")
    definitions = {
        "google_gemini": {
            "provider_id": "google_gemini",
            "adapter_id": "google_gemini_interactions_json_schema",
            "adapter_version": "v1",
        },
        "openai_gpt": {
            "provider_id": "openai",
            "adapter_id": "openai_responses_json_schema",
            "adapter_version": "v1",
        },
    }
    definition = definitions.get(profile_id)
    if definition is None:
        raise VisualTableRuntimeError("visual_table_provider_profile_not_production")
    return VisualProviderProfile(
        profile_id=profile_id,
        provider_id=definition["provider_id"],
        adapter_id=definition["adapter_id"],
        adapter_version=definition["adapter_version"],
        model_id=model_id.strip(),
    )


class VisualTableProviderAdapterFactory:
    def __init__(self, *, boundary: VisualCompletionBoundary) -> None:
        if boundary is None:
            raise VisualTableRuntimeError("visual_table_provider_boundary_missing")
        self.boundary = boundary

    def create(self, *, profile_id: str, model_id: str) -> VisualTableProviderAdapter:
        profile = visual_provider_profile(profile_id, model_id=model_id)
        adapter_type = {
            "google_gemini": _GoogleGeminiVisualTableAdapter,
            "openai_gpt": _OpenAIVisualTableAdapter,
        }[profile.profile_id]
        return adapter_type(
            profile=profile,
            boundary=self.boundary,
            _factory_token=_FACTORY_TOKEN,
        )


class _BaseVisualTableAdapter:
    def __init__(
        self,
        *,
        profile: VisualProviderProfile,
        boundary: VisualCompletionBoundary,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise VisualTableRuntimeError("visual_table_provider_factory_required")
        self.profile = profile
        self.boundary = boundary

    def complete(
        self,
        *,
        request_ref: str,
        provider_context: dict[str, Any],
        image_bytes: bytes,
        image_mime_type: str,
        response_schema: dict[str, Any],
        max_output_tokens: int,
        maximum_request_bytes: int,
        maximum_response_bytes: int,
    ) -> VisualProviderCompletion:
        payload = self._wire_payload(
            request_ref=request_ref,
            provider_context=provider_context,
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
            response_schema=response_schema,
            max_output_tokens=max_output_tokens,
        )
        payload_bytes = canonical_json_bytes(payload)
        if len(payload_bytes) > maximum_request_bytes:
            raise VisualTableProviderRequestError(
                "visual_table_provider_request_budget_exceeded"
            )
        request = VisualProviderBoundaryRequest(
            profile_id=self.profile.profile_id,
            provider_id=self.profile.provider_id,
            adapter_id=self.profile.adapter_id,
            adapter_version=self.profile.adapter_version,
            model_id=self.profile.model_id,
            request_ref=request_ref,
            image_sha256=hashlib.sha256(image_bytes).hexdigest(),
            request_payload_sha256=hashlib.sha256(payload_bytes).hexdigest(),
            request_payload_bytes=len(payload_bytes),
            response_byte_limit=maximum_response_bytes,
            wire_payload=payload,
        )
        try:
            value = self.boundary.complete(request)
            return VisualProviderCompletion(value=value, request=request)
        except VisualTableProviderBoundaryError as exc:
            raise VisualTableProviderBoundaryError(
                exc.code,
                request=request,
            ) from exc
        except TimeoutError as exc:
            raise VisualTableProviderBoundaryError(
                "visual_table_provider_timeout",
                request=request,
            ) from exc
        except ConnectionError as exc:
            raise VisualTableProviderBoundaryError(
                "visual_table_provider_connection_failed",
                request=request,
            ) from exc
        except OSError as exc:
            raise VisualTableProviderBoundaryError(
                "visual_table_provider_io_failed",
                request=request,
            ) from exc
        except Exception as exc:
            raise VisualTableProviderBoundaryError(
                "visual_table_provider_boundary_failed",
                request=request,
            ) from exc

    def _wire_payload(
        self,
        *,
        request_ref: str,
        provider_context: dict[str, Any],
        image_bytes: bytes,
        image_mime_type: str,
        response_schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        raise NotImplementedError


class _GoogleGeminiVisualTableAdapter(_BaseVisualTableAdapter):
    def _wire_payload(
        self,
        *,
        request_ref: str,
        provider_context: dict[str, Any],
        image_bytes: bytes,
        image_mime_type: str,
        response_schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        prompt = _provider_prompt(request_ref, provider_context)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return {
            "model": self.profile.model_id,
            "store": False,
            "generation_config": {
                "max_output_tokens": max_output_tokens,
            },
            "input": [
                {
                    "type": "image",
                    "mime_type": image_mime_type,
                    "data": encoded,
                },
                {"type": "text", "text": prompt},
            ],
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": _wire_schema(
                    response_schema,
                    provider_profile_id=self.profile.profile_id,
                ),
            },
        }


class _OpenAIVisualTableAdapter(_BaseVisualTableAdapter):
    def _wire_payload(
        self,
        *,
        request_ref: str,
        provider_context: dict[str, Any],
        image_bytes: bytes,
        image_mime_type: str,
        response_schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        prompt = _provider_prompt(request_ref, provider_context)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return {
            "model": self.profile.model_id,
            "store": False,
            "max_output_tokens": max_output_tokens,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:{image_mime_type};base64,{encoded}",
                        },
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION,
                    "strict": True,
                    "schema": _wire_schema(
                        response_schema,
                        provider_profile_id=self.profile.profile_id,
                    ),
                }
            },
        }


@dataclass(frozen=True)
class VisualTableRecoveryConfig:
    profile_id: str
    model_id: str
    contract: VisualTableContractConfig = VisualTableContractConfig()


class VisualTableRecoveryFactory:
    def __init__(
        self,
        *,
        adapter_factory: VisualTableProviderAdapterFactory,
        config: VisualTableRecoveryConfig,
    ) -> None:
        self.adapter_factory = adapter_factory
        self.config = config

    def create(self) -> "VisualTableRecoveryRuntime":
        budgets = (
            self.config.contract.maximum_image_bytes,
            self.config.contract.maximum_image_dimension,
            self.config.contract.maximum_image_pixels,
            self.config.contract.maximum_request_bytes,
            self.config.contract.maximum_response_bytes,
            self.config.contract.maximum_output_tokens,
            self.config.contract.maximum_tables,
            self.config.contract.maximum_rows_per_table,
            self.config.contract.maximum_columns_per_table,
            self.config.contract.maximum_cells,
            self.config.contract.maximum_source_regions,
            self.config.contract.maximum_annotations,
            self.config.contract.maximum_refs_per_item,
            self.config.contract.maximum_identifier_chars,
            self.config.contract.maximum_source_text_chars,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in budgets
        ):
            raise VisualTableRuntimeError("visual_table_contract_budget_invalid")
        adapter = self.adapter_factory.create(
            profile_id=self.config.profile_id,
            model_id=self.config.model_id,
        )
        return VisualTableRecoveryRuntime(
            adapter=adapter,
            contract=self.config.contract,
            _factory_token=_FACTORY_TOKEN,
        )


class VisualTableRecoveryRuntime:
    def __init__(
        self,
        *,
        adapter: VisualTableProviderAdapter,
        contract: VisualTableContractConfig,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise VisualTableRuntimeError("visual_table_recovery_factory_required")
        self.adapter = adapter
        self.contract = contract
        self.validator = VisualTableProposalValidator(contract)

    def recover(
        self,
        *,
        scope: Any,
        image_bytes: bytes,
    ) -> dict[str, Any]:
        """Execute one bounded request and terminate with an allowed result."""

        scope_errors = validate_visual_table_scope(
            scope,
            image_bytes=image_bytes,
            config=self.contract,
        )
        request_ref = _request_ref(scope) if not scope_errors else ""
        if scope_errors:
            return self._result(
                scope=scope,
                image_bytes=image_bytes,
                request_ref=request_ref,
                terminal_result="unresolved_visual_scope",
                reason_codes=scope_errors,
                provider_calls=0,
            )

        response_schema = visual_table_proposal_json_schema(self.contract)
        provider_context = {
            "request_ref": request_ref,
            "scope_kind": scope["scope_kind"],
            "source_regions": [
                {
                    "source_region_ref": item["source_region_ref"],
                    "normalized_bbox": copy.deepcopy(item["normalized_bbox"]),
                    "material": item["material"],
                }
                for item in scope["source_region_inventory"]
            ],
        }
        try:
            completion = self.adapter.complete(
                request_ref=request_ref,
                provider_context=provider_context,
                image_bytes=image_bytes,
                image_mime_type=scope["image_mime_type"],
                response_schema=response_schema,
                max_output_tokens=self.contract.maximum_output_tokens,
                maximum_request_bytes=self.contract.maximum_request_bytes,
                maximum_response_bytes=self.contract.maximum_response_bytes,
            )
        except VisualTableProviderRequestError as exc:
            return self._result(
                scope=scope,
                image_bytes=image_bytes,
                request_ref=request_ref,
                terminal_result="unresolved_visual_scope",
                reason_codes=[exc.code],
                provider_calls=0,
            )
        except VisualTableProviderBoundaryError as exc:
            request = exc.request
            return self._result(
                scope=scope,
                image_bytes=image_bytes,
                request_ref=request_ref,
                terminal_result="unresolved_visual_scope",
                reason_codes=[exc.code],
                provider_calls=1,
                provider_request_payload_sha256=(
                    request.request_payload_sha256 if request else None
                ),
                provider_request_payload_bytes=(
                    request.request_payload_bytes if request else None
                ),
                provider_response_byte_limit=(
                    request.response_byte_limit if request else None
                ),
            )

        provider_value = completion.value
        request = completion.request
        try:
            proposal, raw_bytes = parse_visual_table_proposal(
                provider_value,
                config=self.contract,
            )
        except VisualTableContractError as exc:
            response_hash, response_size = _untrusted_response_fingerprint(
                provider_value
            )
            return self._result(
                scope=scope,
                image_bytes=image_bytes,
                request_ref=request_ref,
                terminal_result="malformed_provider_output",
                reason_codes=[exc.code],
                provider_calls=1,
                provider_response_sha256=response_hash,
                provider_response_bytes=response_size,
                provider_request_payload_sha256=request.request_payload_sha256,
                provider_request_payload_bytes=request.request_payload_bytes,
                provider_response_byte_limit=request.response_byte_limit,
            )

        outcome = self.validator.validate(
            proposal=proposal,
            scope=scope,
            request_ref=request_ref,
        )
        return self._result(
            scope=scope,
            image_bytes=image_bytes,
            request_ref=request_ref,
            terminal_result=outcome.terminal_result,
            reason_codes=list(outcome.reason_codes),
            provider_calls=1,
            provider_response_sha256=hashlib.sha256(raw_bytes).hexdigest(),
            provider_response_bytes=len(raw_bytes),
            provider_request_payload_sha256=request.request_payload_sha256,
            provider_request_payload_bytes=request.request_payload_bytes,
            provider_response_byte_limit=request.response_byte_limit,
            proposal=outcome.proposal,
            proposal_sha256=outcome.proposal_sha256,
        )

    def _result(
        self,
        *,
        scope: Any,
        image_bytes: Any,
        request_ref: str,
        terminal_result: str,
        reason_codes: list[str],
        provider_calls: int,
        provider_response_sha256: str | None = None,
        provider_response_bytes: int | None = None,
        provider_request_payload_sha256: str | None = None,
        provider_request_payload_bytes: int | None = None,
        provider_response_byte_limit: int | None = None,
        proposal: dict[str, Any] | None = None,
        proposal_sha256: str | None = None,
    ) -> dict[str, Any]:
        if terminal_result not in VISUAL_TABLE_TERMINAL_RESULTS:
            raise AssertionError("visual_table_terminal_result_internal_invalid")
        safe_scope = scope if isinstance(scope, dict) else {}
        actual_image_sha256 = (
            hashlib.sha256(image_bytes).hexdigest()
            if isinstance(image_bytes, bytes)
            else None
        )
        lineage = {
            "source_ref": safe_scope.get("source_ref"),
            "document_ref": safe_scope.get("document_ref"),
            "page_number": safe_scope.get("page_number"),
            "region_ref": safe_scope.get("region_ref"),
            "scope_kind": safe_scope.get("scope_kind"),
            "declared_region_bbox": copy.deepcopy(
                safe_scope.get("declared_region_bbox")
            ),
            "image_sha256": actual_image_sha256,
            "declared_image_sha256": safe_scope.get("image_sha256"),
            "renderer_version": safe_scope.get("renderer_version"),
            "source_region_inventory_sha256": _optional_json_sha256(
                safe_scope.get("source_region_inventory")
            ),
            "source_regions_total": (
                len(safe_scope["source_region_inventory"])
                if isinstance(safe_scope.get("source_region_inventory"), list)
                else None
            ),
        }
        result = {
            "schema_version": VISUAL_TABLE_RESULT_SCHEMA_VERSION,
            "policy_version": VISUAL_TABLE_RUNTIME_POLICY_VERSION,
            "implementation_status": VISUAL_TABLE_IMPLEMENTATION_STATUS,
            "acceptance_status": VISUAL_TABLE_ACCEPTANCE_STATUS,
            "production_integration_claimed": False,
            "request_ref": request_ref,
            "lineage": lineage,
            "provider": {
                "provider_id": self.adapter.profile.provider_id,
                "provider_profile_id": self.adapter.profile.profile_id,
                "adapter_id": self.adapter.profile.adapter_id,
                "adapter_version": self.adapter.profile.adapter_version,
                "model_id": self.adapter.profile.model_id,
            },
            "prompt": {
                "prompt_id": VISUAL_TABLE_PROMPT_ID,
                "prompt_version": VISUAL_TABLE_PROMPT_VERSION,
                "prompt_sha256": VISUAL_TABLE_PROMPT_SHA256,
            },
            "output_schema_version": VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION,
            "validator_version": VISUAL_TABLE_VALIDATOR_VERSION,
            "terminal_result": terminal_result,
            "reason_codes": sorted(set(reason_codes)),
            "provider_calls": provider_calls,
            "whole_document_uploads": 0,
            "declared_scope_only": True,
            "provider_response_sha256": provider_response_sha256,
            "provider_response_bytes": provider_response_bytes,
            "provider_request_payload_sha256": provider_request_payload_sha256,
            "provider_request_payload_bytes": provider_request_payload_bytes,
            "provider_response_byte_limit": provider_response_byte_limit,
            "proposal_sha256": proposal_sha256,
            "validated_proposal": copy.deepcopy(proposal),
            "provider_confidence_used_as_authority": False,
            "provider_agreement_used_as_authority": False,
            "model_canonical_authority": False,
            "canonical_promotion_performed": False,
        }
        result["result_sha256"] = sha256_json(result)
        return result


def _provider_prompt(request_ref: str, provider_context: dict[str, Any]) -> str:
    context = json.dumps(
        provider_context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"{VISUAL_TABLE_PROMPT_TEXT}\n"
        f"request_ref={request_ref}\n"
        f"bounded_context={context}"
    )


def _wire_schema(
    response_schema: dict[str, Any],
    *,
    provider_profile_id: str,
) -> dict[str, Any]:
    schema = copy.deepcopy(response_schema)
    schema.pop("$id", None)
    if provider_profile_id == "google_gemini":
        schema = _without_unsupported_gemini_schema_keywords(schema)
    return schema


def _without_unsupported_gemini_schema_keywords(value: Any) -> Any:
    """Keep the Gemini Interactions documented JSON-Schema subset.

    String length and pattern constraints remain enforced by the deterministic
    local parser.  They are removed only from the provider-facing schema because
    Gemini does not document them as supported structured-output keywords.
    """

    if isinstance(value, dict):
        return {
            key: _without_unsupported_gemini_schema_keywords(item)
            for key, item in value.items()
            if key not in {"minLength", "maxLength", "pattern"}
        }
    if isinstance(value, list):
        return [_without_unsupported_gemini_schema_keywords(item) for item in value]
    return value


def _request_ref(scope: dict[str, Any]) -> str:
    identity = {
        "scope": scope,
        "prompt_id": VISUAL_TABLE_PROMPT_ID,
        "prompt_version": VISUAL_TABLE_PROMPT_VERSION,
        "prompt_sha256": VISUAL_TABLE_PROMPT_SHA256,
        "output_schema_version": VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION,
        "validator_version": VISUAL_TABLE_VALIDATOR_VERSION,
    }
    return f"visualvlmreq_{sha256_json(identity)[:32]}"


def _untrusted_response_fingerprint(
    value: Any,
) -> tuple[str | None, int | None]:
    try:
        if isinstance(value, bytes):
            payload = value
        elif isinstance(value, str):
            payload = value.encode("utf-8")
        else:
            payload = canonical_json_bytes(value)
    except VisualTableContractError:
        return None, None
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _optional_json_sha256(value: Any) -> str | None:
    try:
        return sha256_json(value)
    except VisualTableContractError:
        return None
