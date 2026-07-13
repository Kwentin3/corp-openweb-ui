from __future__ import annotations

import base64
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
from .pdf_hybrid_contracts import canonical_json_bytes, sha256_json


PDF_CSV_PROVIDER_ADAPTER_VERSION = "gemini_native_table_crop_text_v1"
MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024
FACTORY_REQUIRED = (
    "PdfCsvExperimentProviderFactory.create_for_openwebui is the only live CSV experiment provider entrypoint"
)
FORBIDDEN = (
    "CSV experiment orchestration must not construct provider payloads, resolve secrets, retry, or fail over providers"
)


class PdfCsvProviderError(RuntimeError):
    def __init__(self, code: str, failure_class: str) -> None:
        self.code = code
        self.failure_class = failure_class
        super().__init__(code)


@dataclass(frozen=True)
class PdfCsvProviderConfig:
    provider_profile: str = "google_gemini"
    model_id: str = "models/gemini-3.5-flash"
    timeout_seconds: int = 240
    maximum_output_tokens: int = 8192
    maximum_counted_input_tokens: int = 24_000
    thinking_level: str = "minimal"


class PdfCsvExperimentProviderFactory:
    def __init__(
        self,
        config: PdfCsvProviderConfig | None = None,
        *,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        self.config = config or PdfCsvProviderConfig()
        self.urlopen_fn = urlopen_fn

    def create_for_openwebui(self, request: Any) -> "GeminiCsvExperimentAdapter":
        profile = gate2_provider_profile(self.config.provider_profile)
        if profile.profile_id != "google_gemini":
            raise PdfCsvProviderError(
                "pdf_csv_provider_profile_not_supported", "provider_configuration"
            )
        if self.config.model_id not in profile.approved_model_ids:
            raise PdfCsvProviderError(
                "pdf_csv_model_not_approved", "provider_configuration"
            )
        connection = Gate2OpenWebUIProviderConnectionResolver(request).resolve(profile)
        return GeminiCsvExperimentAdapter(
            self.config,
            profile,
            connection,
            urlopen_fn=self.urlopen_fn,
        )

    def create_with_connection(
        self,
        connection: Gate2OpenWebUIProviderConnection,
    ) -> "GeminiCsvExperimentAdapter":
        profile = gate2_provider_profile(self.config.provider_profile)
        return GeminiCsvExperimentAdapter(
            self.config,
            profile,
            connection,
            urlopen_fn=self.urlopen_fn,
        )


class GeminiCsvExperimentAdapter:
    def __init__(
        self,
        config: PdfCsvProviderConfig,
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
        status, body = self._request("GET", self._base_url() + f"/models/{model}", None)
        payload = self._decode_json(body)
        resolved = str(payload.get("name") or "")
        supported = set(str(item) for item in payload.get("supportedGenerationMethods") or [])
        passed = (
            status == 200
            and resolved == self.config.model_id
            and "generateContent" in supported
            and int(payload.get("outputTokenLimit") or 0) >= self.config.maximum_output_tokens
            and int(payload.get("inputTokenLimit") or 0)
            >= self.config.maximum_counted_input_tokens
        )
        return {
            "status": "qualified" if passed else "blocked",
            "provider_profile": self.profile.profile_id,
            "provider_profile_revision": gate2_provider_profile_revision(self.profile),
            "requested_model_id": self.config.model_id,
            "resolved_model_id": resolved,
            "exact_model_match": resolved == self.config.model_id,
            "image_input_supported": "generateContent" in supported,
            "plain_text_output_supported": "generateContent" in supported,
            "maximum_output_tokens": int(payload.get("outputTokenLimit") or 0),
            "maximum_input_tokens": int(payload.get("inputTokenLimit") or 0),
            "http_status": status,
            "response_hash": hashlib.sha256(body).hexdigest(),
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_retry": False,
            "provider_failover": False,
        }

    def count_tokens(
        self,
        *,
        prompt: str,
        png_bytes: bytes,
        crop_sha256: str,
    ) -> dict[str, Any]:
        self._validate_crop(png_bytes, crop_sha256)
        body = self._generate_body(prompt=prompt, png_bytes=png_bytes)
        model = self.config.model_id.removeprefix("models/")
        request_body = {
            "generateContentRequest": {"model": self.config.model_id, **body}
        }
        status, response_body = self._request(
            "POST",
            self._base_url() + f"/models/{model}:countTokens",
            request_body,
        )
        payload = self._decode_json(response_body)
        total = payload.get("totalTokens")
        if status < 200 or status >= 300:
            raise PdfCsvProviderError(
                "pdf_csv_provider_count_tokens_failed", _http_failure_class(status)
            )
        if not isinstance(total, int) or total < 0:
            raise PdfCsvProviderError(
                "pdf_csv_provider_count_tokens_invalid", "provider_invalid_json"
            )
        if total > self.config.maximum_counted_input_tokens:
            raise PdfCsvProviderError(
                "pdf_csv_provider_counted_input_budget_exceeded", "context_budget"
            )
        return {
            "total_tokens": total,
            "prompt_tokens_details": payload.get("promptTokensDetails") or [],
            "http_status": status,
            "request_hash": sha256_json(request_body),
            "response_hash": hashlib.sha256(response_body).hexdigest(),
            "model_requested": self.config.model_id,
            "transport_identity": "gemini_count_tokens_generate_content_request",
            "within_hard_guard": True,
        }

    def invoke(
        self,
        *,
        task_id: str,
        prompt: str,
        png_bytes: bytes,
        crop_sha256: str,
        attempt_number: int,
        attempt_lineage: list[str],
    ) -> dict[str, Any]:
        if attempt_number not in {1, 2} or len(attempt_lineage) != attempt_number - 1:
            raise PdfCsvProviderError(
                "pdf_csv_attempt_lineage_invalid", "attempt_policy"
            )
        self._validate_crop(png_bytes, crop_sha256)
        body = self._generate_body(prompt=prompt, png_bytes=png_bytes)
        model = self.config.model_id.removeprefix("models/")
        attempt_id = f"{task_id}_a{attempt_number}"
        started_at = _utc_now()
        started = time.perf_counter()
        status: int | None = None
        response_body = b""
        payload: dict[str, Any] = {}
        failure_class: str | None = None
        text: str | None = None
        try:
            status, response_body = self._request(
                "POST",
                self._base_url() + f"/models/{model}:generateContent",
                body,
            )
            if len(response_body) > MAX_PROVIDER_RESPONSE_BYTES:
                raise PdfCsvProviderError(
                    "pdf_csv_provider_response_budget_exceeded", "response_budget"
                )
            payload = self._decode_json(response_body)
            if status < 200 or status >= 300:
                failure_class = _http_failure_class(status)
            else:
                text = _gemini_text(payload)
        except PdfCsvProviderError as exc:
            failure_class = exc.failure_class
            if not response_body:
                response_body = canonical_json_bytes({"error_code": exc.code})
        candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
        finish_reason = (
            str(candidates[0].get("finishReason") or "")
            if candidates and isinstance(candidates[0], dict)
            else None
        )
        if finish_reason != "STOP":
            failure_class = "response_budget" if finish_reason in {
                "MAX_TOKENS",
                "MAX_OUTPUT_TOKENS",
            } else (failure_class or "provider_non_terminal")
        usage = payload.get("usageMetadata") if isinstance(payload.get("usageMetadata"), dict) else {}
        resolved = str(payload.get("modelVersion") or "")
        if resolved and not resolved.startswith("models/"):
            resolved = "models/" + resolved
        if resolved and resolved != self.config.model_id:
            failure_class = "resolved_model_mismatch"
        visible = text.encode("utf-8") if isinstance(text, str) else b""
        attempt = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_number": attempt_number,
            "attempt_lineage": list(attempt_lineage),
            "provider": "google",
            "provider_profile": self.profile.profile_id,
            "provider_profile_revision": gate2_provider_profile_revision(self.profile),
            "model_requested": self.config.model_id,
            "model_resolved": resolved or None,
            "adapter_identity": PDF_CSV_PROVIDER_ADAPTER_VERSION,
            "transport_identity": "gemini_generate_content_native_table_crop_text",
            "request_hash": sha256_json(body),
            "crop_sha256": crop_sha256,
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "started_at": started_at,
            "ended_at": _utc_now(),
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "http_status": status,
            "provider_response_id": payload.get("responseId"),
            "usage": {
                "input_tokens": usage.get("promptTokenCount"),
                "output_tokens": usage.get("candidatesTokenCount"),
                "total_tokens": usage.get("totalTokenCount"),
            },
            "finish_reason": finish_reason,
            "thinking_level": self.config.thinking_level,
            "terminal_failure_class": failure_class,
            "hidden_retry": False,
            "provider_failover": False,
        }
        return {
            "attempt": attempt,
            "text": text if failure_class is None else None,
            "raw_private_response": payload,
            "response_bytes": len(response_body),
            "response_hash": hashlib.sha256(response_body).hexdigest(),
            "visible_output_bytes": len(visible),
            "visible_output_hash": hashlib.sha256(visible).hexdigest() if visible else None,
        }

    def _generate_body(self, *, prompt: str, png_bytes: bytes) -> dict[str, Any]:
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
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
                "responseMimeType": "text/plain",
            },
        }

    @staticmethod
    def _validate_crop(png_bytes: bytes, crop_sha256: str) -> None:
        if hashlib.sha256(png_bytes).hexdigest() != crop_sha256:
            raise PdfCsvProviderError(
                "pdf_csv_provider_crop_hash_mismatch", "request_validation"
            )

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
            raise PdfCsvProviderError(
                "pdf_csv_provider_transport_failed", "timeout_or_transport"
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
            raise PdfCsvProviderError(
                "pdf_csv_provider_invalid_json", "provider_invalid_json"
            ) from exc
        if not isinstance(value, dict):
            raise PdfCsvProviderError(
                "pdf_csv_provider_response_not_object", "provider_invalid_json"
            )
        return value


def _gemini_text(payload: dict[str, Any]) -> str:
    texts = []
    for candidate in payload.get("candidates") or []:
        content = candidate.get("content") if isinstance(candidate, dict) else {}
        for part in content.get("parts") or [] if isinstance(content, dict) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    if len(texts) != 1:
        raise PdfCsvProviderError(
            "pdf_csv_provider_text_count_invalid", "parse_failure"
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
