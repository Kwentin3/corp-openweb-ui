from __future__ import annotations

import base64
import copy
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .gate2_model_contracts import gate2_provider_profile, gate2_provider_profile_revision
from .gate2_provider_adapters import (
    Gate2OpenWebUIProviderConnection,
    Gate2OpenWebUIProviderConnectionResolver,
)
from .pdf_hybrid_contracts import (
    PDF_PROVIDER_ATTEMPT_SCHEMA,
    canonical_json_bytes,
    sha256_json,
    validate_binding_output_shape,
)


PDF_HYBRID_PROVIDER_ADAPTER_VERSION = "gemini_native_image_json_schema_v2_calibrated"
MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024
FACTORY_REQUIRED = (
    "PdfHybridProviderFactory.create_for_openwebui is the only live hybrid provider entrypoint"
)
FORBIDDEN = (
    "The hybrid business pipeline must not construct Gemini payloads, resolve secrets, retry, "
    "or fail over providers"
)


class PdfHybridProviderError(RuntimeError):
    def __init__(self, code: str, failure_class: str) -> None:
        self.code = code
        self.failure_class = failure_class
        super().__init__(code)


@dataclass(frozen=True)
class PdfHybridProviderConfig:
    provider_profile: str = "google_gemini"
    model_id: str = "models/gemini-3.5-flash"
    timeout_seconds: int = 240
    maximum_output_tokens: int = 16_384
    thinking_level: str = "minimal"


class PdfHybridProviderFactory:
    def __init__(
        self,
        config: PdfHybridProviderConfig | None = None,
        *,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        self.config = config or PdfHybridProviderConfig()
        self.urlopen_fn = urlopen_fn

    def create_for_openwebui(self, request: Any) -> "GeminiHybridProviderAdapter":
        profile = gate2_provider_profile(self.config.provider_profile)
        if profile.profile_id != "google_gemini":
            raise PdfHybridProviderError(
                "pdf_hybrid_provider_profile_not_supported", "provider_configuration"
            )
        if self.config.model_id not in profile.approved_model_ids:
            raise PdfHybridProviderError(
                "pdf_hybrid_model_not_approved", "provider_configuration"
            )
        connection = Gate2OpenWebUIProviderConnectionResolver(request).resolve(profile)
        return GeminiHybridProviderAdapter(
            self.config, profile, connection, urlopen_fn=self.urlopen_fn
        )

    def create_with_connection(
        self,
        connection: Gate2OpenWebUIProviderConnection,
    ) -> "GeminiHybridProviderAdapter":
        profile = gate2_provider_profile(self.config.provider_profile)
        if profile.profile_id != "google_gemini":
            raise PdfHybridProviderError(
                "pdf_hybrid_provider_profile_not_supported", "provider_configuration"
            )
        return GeminiHybridProviderAdapter(
            self.config, profile, connection, urlopen_fn=self.urlopen_fn
        )


class GeminiHybridProviderAdapter:
    def __init__(
        self,
        config: PdfHybridProviderConfig,
        profile: Any,
        connection: Gate2OpenWebUIProviderConnection,
        *,
        urlopen_fn: Callable[..., Any],
    ) -> None:
        self.config = config
        self.profile = profile
        self.connection = connection
        self.urlopen_fn = urlopen_fn

    def qualify(self) -> dict[str, Any]:
        model = self.config.model_id.removeprefix("models/")
        url = self._base_url() + f"/models/{model}"
        status, body = self._request("GET", url, None)
        payload = self._decode_json(body)
        resolved = str(payload.get("name") or "")
        supported = set(str(item) for item in payload.get("supportedGenerationMethods") or [])
        passed = (
            status == 200
            and resolved == self.config.model_id
            and "generateContent" in supported
            and int(payload.get("outputTokenLimit") or 0) >= self.config.maximum_output_tokens
        )
        return {
            "status": "qualified" if passed else "blocked",
            "provider_profile": self.profile.profile_id,
            "provider_profile_revision": gate2_provider_profile_revision(self.profile),
            "requested_model_id": self.config.model_id,
            "resolved_model_id": resolved,
            "exact_model_match": resolved == self.config.model_id,
            "image_input_supported": "generateContent" in supported,
            "structured_output_supported": self.profile.supports_strict_final_json_schema,
            "response_budget_supported": int(payload.get("outputTokenLimit") or 0)
            >= self.config.maximum_output_tokens,
            "maximum_output_tokens": int(payload.get("outputTokenLimit") or 0),
            "maximum_input_tokens": int(payload.get("inputTokenLimit") or 0),
            "http_status": status,
            "response_hash": hashlib.sha256(body).hexdigest(),
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_failover": False,
        }

    def count_tokens(
        self,
        *,
        evidence_package: dict[str, Any],
        png_bytes: bytes,
    ) -> dict[str, Any]:
        crop = evidence_package.get("crop_identity") or {}
        if hashlib.sha256(png_bytes).hexdigest() != crop.get("crop_sha256"):
            raise PdfHybridProviderError(
                "pdf_hybrid_provider_crop_hash_mismatch", "request_validation"
            )
        body, canonical_schema_hash, adapted_schema_hash, transform_count = (
            self._generate_body(evidence_package=evidence_package, png_bytes=png_bytes)
        )
        model = self.config.model_id.removeprefix("models/")
        url = self._base_url() + f"/models/{model}:countTokens"
        request_body = {
            "generateContentRequest": {
                "model": self.config.model_id,
                **body,
            }
        }
        status, response_body = self._request("POST", url, request_body)
        payload = self._decode_json(response_body)
        if status < 200 or status >= 300:
            raise PdfHybridProviderError(
                "pdf_hybrid_provider_count_tokens_failed", _http_failure_class(status)
            )
        total = payload.get("totalTokens")
        if not isinstance(total, int) or total < 0:
            raise PdfHybridProviderError(
                "pdf_hybrid_provider_count_tokens_invalid", "provider_invalid_json"
            )
        return {
            "total_tokens": total,
            "prompt_tokens_details": copy.deepcopy(
                payload.get("promptTokensDetails") or []
            ),
            "http_status": status,
            "response_hash": hashlib.sha256(response_body).hexdigest(),
            "request_hash": sha256_json(request_body),
            "canonical_schema_hash": canonical_schema_hash,
            "adapted_schema_hash": adapted_schema_hash,
            "schema_transform_count": transform_count,
            "model_requested": self.config.model_id,
            "transport_identity": "gemini_count_tokens_generate_content_request",
        }

    def invoke(
        self,
        *,
        evidence_package: dict[str, Any],
        png_bytes: bytes,
        attempt_number: int,
        attempt_lineage: list[str],
    ) -> dict[str, Any]:
        if attempt_number not in {1, 2} or len(attempt_lineage) >= attempt_number:
            raise PdfHybridProviderError(
                "pdf_hybrid_attempt_lineage_invalid", "attempt_policy"
            )
        crop = evidence_package.get("crop_identity") or {}
        if hashlib.sha256(png_bytes).hexdigest() != crop.get("crop_sha256"):
            raise PdfHybridProviderError(
                "pdf_hybrid_provider_crop_hash_mismatch", "request_validation"
            )
        body, canonical_schema_hash, adapted_schema_hash, transform_count = (
            self._generate_body(evidence_package=evidence_package, png_bytes=png_bytes)
        )
        package_id = str(evidence_package.get("package_id") or "")
        task_id = "pdfhybridtask_" + package_id.removeprefix("pdfhybridpkg_")
        attempt_id = f"{task_id}_a{attempt_number}"
        started_at = _utc_now()
        started = time.perf_counter()
        failure_class = None
        status = None
        response_body = b""
        payload: dict[str, Any] = {}
        binding: Any = None
        parse_result = "not_parsed"
        validation_result = "not_validated"
        try:
            model = self.config.model_id.removeprefix("models/")
            url = self._base_url() + f"/models/{model}:generateContent"
            status, response_body = self._request("POST", url, body)
            if len(response_body) > MAX_PROVIDER_RESPONSE_BYTES:
                raise PdfHybridProviderError(
                    "pdf_hybrid_provider_response_budget_exceeded", "response_budget"
                )
            payload = self._decode_json(response_body)
            if status < 200 or status >= 300:
                failure_class = _http_failure_class(status)
            else:
                text = _gemini_text(payload)
                try:
                    binding = json.loads(text)
                    parse_result = "parsed"
                except (TypeError, ValueError):
                    parse_result = "invalid_json"
                    failure_class = "parse_failure"
                if parse_result == "parsed":
                    shape_errors = validate_binding_output_shape(binding)
                    validation_result = "passed" if not shape_errors else "failed"
                    if shape_errors:
                        failure_class = "contract_validation"
        except PdfHybridProviderError as exc:
            failure_class = exc.failure_class
            if not response_body:
                response_body = canonical_json_bytes({"error_code": exc.code})
        duration_ms = round((time.perf_counter() - started) * 1000)
        usage = payload.get("usageMetadata") if isinstance(payload.get("usageMetadata"), dict) else {}
        candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
        finish_reason = (
            str(candidates[0].get("finishReason") or "")
            if candidates and isinstance(candidates[0], dict)
            else None
        )
        if finish_reason in {"MAX_TOKENS", "MAX_OUTPUT_TOKENS"}:
            failure_class = "response_budget"
            validation_result = "failed"
        resolved = str(payload.get("modelVersion") or "")
        if resolved and not resolved.startswith("models/"):
            resolved = "models/" + resolved
        if resolved and resolved != self.config.model_id:
            failure_class = "resolved_model_mismatch"
            validation_result = "failed"
        attempt = {
            "schema_version": PDF_PROVIDER_ATTEMPT_SCHEMA,
            "same_evidence_task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_number": attempt_number,
            "attempt_lineage": list(attempt_lineage),
            "provider": "google",
            "provider_profile": self.profile.profile_id,
            "provider_profile_revision": gate2_provider_profile_revision(self.profile),
            "model_requested": self.config.model_id,
            "model_resolved": resolved or None,
            "adapter_identity": PDF_HYBRID_PROVIDER_ADAPTER_VERSION,
            "transport_identity": "gemini_generate_content_native_image",
            "package_hash": evidence_package.get("package_hash"),
            "crop_hash": crop.get("crop_sha256"),
            "canonical_schema_hash": canonical_schema_hash,
            "adapted_schema_hash": adapted_schema_hash,
            "schema_transform_count": transform_count,
            "started_at": started_at,
            "ended_at": _utc_now(),
            "duration_ms": duration_ms,
            "http_status": status,
            "provider_response_id": payload.get("responseId"),
            "usage": {
                "input_tokens": usage.get("promptTokenCount"),
                "output_tokens": usage.get("candidatesTokenCount"),
                "total_tokens": usage.get("totalTokenCount"),
            },
            "finish_reason": finish_reason,
            "thinking_level": self.config.thinking_level,
            "raw_private_response_ref": None,
            "parse_result": parse_result,
            "validation_result": validation_result,
            "terminal_failure_class": failure_class,
            "hidden_retry": False,
            "provider_failover": False,
        }
        return {
            "attempt": attempt,
            "binding_output": (
                binding
                if isinstance(binding, dict)
                and validation_result == "passed"
                and failure_class is None
                else None
            ),
            "raw_private_response": payload,
            "response_bytes": len(response_body),
            "response_hash": hashlib.sha256(response_body).hexdigest(),
        }

    def _generate_body(
        self,
        *,
        evidence_package: dict[str, Any],
        png_bytes: bytes,
    ) -> tuple[dict[str, Any], str, str, int]:
        schema = copy.deepcopy(evidence_package.get("output_schema") or {})
        adapted_schema, transform_count = _project_gemini_schema(schema)
        canonical_schema_hash = sha256_json(schema)
        adapted_schema_hash = sha256_json(adapted_schema)
        model_view = evidence_package.get("model_facing") or {}
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                model_view,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(png_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "candidateCount": 1,
                "maxOutputTokens": self.config.maximum_output_tokens,
                "thinkingConfig": {"thinkingLevel": self.config.thinking_level},
                "responseMimeType": "application/json",
                "responseJsonSchema": adapted_schema,
            },
        }
        return body, canonical_schema_hash, adapted_schema_hash, transform_count

    def _request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None,
    ) -> tuple[int, bytes]:
        request = Request(
            url,
            data=canonical_json_bytes(body) if body is not None else None,
            method=method,
            headers={
                "content-type": "application/json",
                "x-goog-api-key": self.connection.api_key,
            },
        )
        try:
            with self.urlopen_fn(request, timeout=self.config.timeout_seconds) as response:
                return int(response.status), response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            return int(exc.code), exc.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        except (TimeoutError, URLError) as exc:
            raise PdfHybridProviderError(
                "pdf_hybrid_provider_transport_failed", "timeout_or_transport"
            ) from exc

    def _base_url(self) -> str:
        base = self.connection.base_url.rstrip("/")
        if base.endswith("/openai"):
            base = base[: -len("/openai")]
        return base

    @staticmethod
    def _decode_json(body: bytes) -> dict[str, Any]:
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise PdfHybridProviderError(
                "pdf_hybrid_provider_invalid_json", "provider_invalid_json"
            ) from exc
        if not isinstance(value, dict):
            raise PdfHybridProviderError(
                "pdf_hybrid_provider_response_not_object", "provider_invalid_json"
            )
        return value


_GEMINI_SCHEMA_KEYS = {
    "$id",
    "$defs",
    "$ref",
    "$anchor",
    "type",
    "format",
    "title",
    "description",
    "enum",
    "items",
    "prefixItems",
    "minItems",
    "minimum",
    "maximum",
    "anyOf",
    "oneOf",
    "properties",
    "additionalProperties",
    "required",
    "propertyOrdering",
}


def _project_gemini_schema(value: dict[str, Any]) -> tuple[dict[str, Any], int]:
    result = copy.deepcopy(value)
    transforms = 0

    def walk(node: Any) -> None:
        nonlocal transforms
        if isinstance(node, dict):
            for key in list(node):
                if key not in _GEMINI_SCHEMA_KEYS:
                    node.pop(key)
                    transforms += 1
            properties = node.get("properties")
            if isinstance(properties, dict):
                for child in properties.values():
                    walk(child)
            definitions = node.get("$defs")
            if isinstance(definitions, dict):
                for child in definitions.values():
                    walk(child)
            for key in ("items", "additionalProperties"):
                child = node.get(key)
                if isinstance(child, dict):
                    walk(child)
            for key in ("prefixItems", "anyOf", "oneOf"):
                children = node.get(key)
                if isinstance(children, list):
                    for child in children:
                        walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(result)
    return result, transforms


def _gemini_text(payload: dict[str, Any]) -> str:
    texts = []
    for candidate in payload.get("candidates") or []:
        content = candidate.get("content") if isinstance(candidate, dict) else {}
        for part in content.get("parts") or [] if isinstance(content, dict) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    if len(texts) != 1:
        raise PdfHybridProviderError(
            "pdf_hybrid_provider_structured_text_count_invalid", "parse_failure"
        )
    return texts[0]


def _http_failure_class(status: int) -> str:
    if status == 429:
        return "rate_limit"
    if status in {408, 504}:
        return "timeout"
    if status in {401, 403}:
        return "provider_authentication"
    if status >= 500:
        return "provider_server"
    return "provider_http"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
