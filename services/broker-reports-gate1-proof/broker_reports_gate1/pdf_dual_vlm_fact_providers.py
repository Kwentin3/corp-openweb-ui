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

from .gate2_model_contracts import (
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from .gate2_provider_adapters import (
    Gate2OpenWebUIProviderConnection,
    Gate2OpenWebUIProviderConnectionResolver,
)
from .pdf_grid_experiment_provider import (
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)


RUNTIME_STATUS = "maintained_product"
DEFAULT_GEMINI_MODEL_ID = "models/gemini-3.5-flash"
DEFAULT_OPENAI_MODEL_ID = "gpt-5.4-mini-2026-03-17"
GEMINI_MODEL_QUALIFICATION_ALLOWLIST = frozenset(
    {
        "models/gemini-3.1-flash-lite",
        DEFAULT_GEMINI_MODEL_ID,
    }
)
OPENAI_MODEL_QUALIFICATION_ALLOWLIST = frozenset(
    {
        DEFAULT_OPENAI_MODEL_ID,
        "gpt-5.6-luna",
        "gpt-5.6-sol",
    }
)
OPENAI_ADAPTER_VERSION = "openai_responses_png_fact_json_schema_v1"
OPENAI_SCHEMA_NAME = "broker_reports_pdf_dual_vlm_fact_output_v1"
MAX_OPENAI_RESPONSE_BYTES = 2 * 1024 * 1024

FACTORY_REQUIRED = (
    "PdfDualVlmFactProviderFactory.create_for_openwebui is the only live dual-VLM "
    "fact provider entrypoint"
)
FORBIDDEN = (
    "Dual-VLM benchmark orchestration must not construct provider payloads, resolve "
    "secrets, instantiate adapters, retry, or fail over providers"
)


class PdfDualVlmFactProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        failure_class: str,
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.failure_class = failure_class
        self.safe_details = copy.deepcopy(safe_details or {})
        super().__init__(code)


@dataclass(frozen=True)
class PdfDualVlmFactProviderConfig:
    gemini_model_id: str = DEFAULT_GEMINI_MODEL_ID
    openai_model_id: str = DEFAULT_OPENAI_MODEL_ID
    timeout_seconds: int = 240
    detection_maximum_output_tokens: int = 4_096
    extraction_maximum_output_tokens: int = 16_384
    maximum_counted_input_tokens: int = 24_000
    gemini_thinking_level: str = "minimal"
    openai_image_detail: str = "high"


@dataclass(frozen=True)
class PdfDualVlmFactProviderBundle:
    detector: Any
    gemini: Any
    openai: "OpenAIResponsesVisionAdapter"

    def qualify(self) -> dict[str, Any]:
        return {
            "detector": self.detector.qualify(),
            "gemini": self.gemini.qualify(),
            "openai": self.openai.qualify(),
        }


class PdfDualVlmFactProviderFactory:
    def __init__(
        self,
        config: PdfDualVlmFactProviderConfig | None = None,
        *,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        self.config = config or PdfDualVlmFactProviderConfig()
        self.urlopen_fn = urlopen_fn

    def create_for_openwebui(self, request: Any) -> PdfDualVlmFactProviderBundle:
        self._validate_config()
        detector = PdfGridExperimentProviderFactory(
            PdfGridProviderConfig(
                provider_profile="google_gemini",
                model_id=self.config.gemini_model_id,
                timeout_seconds=self.config.timeout_seconds,
                maximum_output_tokens=(self.config.detection_maximum_output_tokens),
                maximum_counted_input_tokens=(self.config.maximum_counted_input_tokens),
                thinking_level=self.config.gemini_thinking_level,
            ),
            urlopen_fn=self.urlopen_fn,
        ).create_for_openwebui(request)
        gemini = PdfGridExperimentProviderFactory(
            PdfGridProviderConfig(
                provider_profile="google_gemini",
                model_id=self.config.gemini_model_id,
                timeout_seconds=self.config.timeout_seconds,
                maximum_output_tokens=(self.config.extraction_maximum_output_tokens),
                maximum_counted_input_tokens=(self.config.maximum_counted_input_tokens),
                thinking_level=self.config.gemini_thinking_level,
            ),
            urlopen_fn=self.urlopen_fn,
        ).create_for_openwebui(request)

        openai_profile = gate2_provider_profile("openai_gpt")
        openai_connection = Gate2OpenWebUIProviderConnectionResolver(request).resolve(
            openai_profile
        )
        openai = OpenAIResponsesVisionAdapter(
            config=self.config,
            profile=openai_profile,
            connection=openai_connection,
            urlopen_fn=self.urlopen_fn,
        )
        return PdfDualVlmFactProviderBundle(
            detector=detector,
            gemini=gemini,
            openai=openai,
        )

    def _validate_config(self) -> None:
        if self.config.gemini_model_id not in GEMINI_MODEL_QUALIFICATION_ALLOWLIST:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_gemini_model_not_allowlisted",
                "provider_configuration",
            )
        if self.config.openai_model_id not in OPENAI_MODEL_QUALIFICATION_ALLOWLIST:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_model_not_allowlisted",
                "provider_configuration",
            )
        if self.config.openai_image_detail != "high":
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_image_detail_invalid",
                "provider_configuration",
            )
        if (
            self.config.timeout_seconds <= 0
            or self.config.detection_maximum_output_tokens <= 0
            or self.config.extraction_maximum_output_tokens <= 0
            or self.config.maximum_counted_input_tokens <= 0
        ):
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_provider_budget_invalid",
                "provider_configuration",
            )


class OpenAIResponsesVisionAdapter:
    def __init__(
        self,
        *,
        config: PdfDualVlmFactProviderConfig,
        profile: Any,
        connection: Gate2OpenWebUIProviderConnection,
        urlopen_fn: Callable[..., Any],
    ) -> None:
        self.config = config
        self.profile = profile
        self.connection = connection
        self.urlopen_fn = urlopen_fn

    def qualify(self) -> dict[str, Any]:
        status, body = self._request(
            "GET",
            self._base_url() + f"/models/{self.config.openai_model_id}",
            None,
        )
        payload = self._decode_json(body)
        resolved = str(payload.get("id") or "")
        passed = (
            status == 200
            and resolved == self.config.openai_model_id
            and self.profile.supports_strict_final_json_schema
        )
        return {
            "status": "qualified" if passed else "blocked",
            "provider_profile": self.profile.profile_id,
            "provider_profile_revision": gate2_provider_profile_revision(self.profile),
            "requested_model_id": self.config.openai_model_id,
            "resolved_model_id": resolved,
            "exact_model_match": resolved == self.config.openai_model_id,
            "image_input_supported": (
                self.config.openai_model_id in OPENAI_MODEL_QUALIFICATION_ALLOWLIST
            ),
            "structured_output_supported": (
                self.profile.supports_strict_final_json_schema
            ),
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
        model_view: dict[str, Any],
        output_schema: dict[str, Any],
        png_bytes: bytes,
        crop_sha256: str,
    ) -> dict[str, Any]:
        self._validate_crop(png_bytes, crop_sha256)
        response_body = self._response_body(
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
        )
        count_body = {
            "model": response_body["model"],
            "input": response_body["input"],
            "text": response_body["text"],
        }
        status, body = self._request(
            "POST",
            self._base_url() + "/responses/input_tokens",
            count_body,
        )
        if len(body) > MAX_OPENAI_RESPONSE_BYTES:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_count_response_budget_exceeded",
                "response_budget",
            )
        payload = self._decode_json(body)
        input_tokens = payload.get("input_tokens")
        if status < 200 or status >= 300:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_count_tokens_failed",
                _http_failure_class(status),
            )
        if not isinstance(input_tokens, int) or input_tokens < 0:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_count_tokens_invalid",
                "provider_invalid_json",
            )
        if input_tokens > self.config.maximum_counted_input_tokens:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_counted_input_budget_exceeded",
                "context_budget",
                safe_details={
                    "observed_total_tokens": input_tokens,
                    "maximum_counted_input_tokens": (
                        self.config.maximum_counted_input_tokens
                    ),
                },
            )
        schema_hash = _sha256_json(output_schema)
        return {
            "total_tokens": input_tokens,
            "input_tokens": input_tokens,
            "http_status": status,
            "request_hash": _sha256_json(count_body),
            "response_hash": hashlib.sha256(body).hexdigest(),
            "canonical_schema_hash": schema_hash,
            "adapted_schema_hash": schema_hash,
            "schema_transform_count": 0,
            "model_requested": self.config.openai_model_id,
            "transport_identity": "openai_responses_input_tokens_png_json_schema",
            "within_hard_guard": True,
        }

    def invoke(
        self,
        *,
        task_id: str,
        model_view: dict[str, Any],
        output_schema: dict[str, Any],
        png_bytes: bytes,
        crop_sha256: str,
        attempt_number: int,
        attempt_lineage: list[str],
    ) -> dict[str, Any]:
        if attempt_number != 1 or attempt_lineage:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_attempt_lineage_invalid",
                "attempt_policy",
            )
        self._validate_crop(png_bytes, crop_sha256)
        response_body = self._response_body(
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
        )
        started_at = _utc_now()
        started = time.perf_counter()
        status: int | None = None
        response_bytes = b""
        payload: dict[str, Any] = {}
        failure_class: str | None = None
        text: str | None = None
        value: dict[str, Any] | None = None
        parse_result = "not_parsed"
        try:
            status, response_bytes = self._request(
                "POST", self._base_url() + "/responses", response_body
            )
            if len(response_bytes) > MAX_OPENAI_RESPONSE_BYTES:
                raise PdfDualVlmFactProviderError(
                    "pdf_dual_vlm_openai_response_budget_exceeded",
                    "response_budget",
                )
            payload = self._decode_json(response_bytes)
            if status < 200 or status >= 300:
                failure_class = _http_failure_class(status)
            elif payload.get("error") is not None:
                failure_class = "provider_error_response"
            elif str(payload.get("status") or "") != "completed":
                failure_class = (
                    "provider_incomplete"
                    if payload.get("status") == "incomplete"
                    else "provider_non_terminal"
                )
            elif _has_refusal(payload):
                failure_class = "provider_refusal"
            else:
                texts = _openai_output_texts(payload)
                if len(texts) != 1:
                    parse_result = "structured_text_block_count_invalid"
                    failure_class = "parse_failure"
                else:
                    text = texts[0]
                    try:
                        parsed = json.loads(text)
                    except (TypeError, ValueError):
                        parse_result = "invalid_json"
                        failure_class = "parse_failure"
                    else:
                        if isinstance(parsed, dict):
                            value = parsed
                            parse_result = "parsed_object"
                        else:
                            parse_result = "parsed_non_object"
                            failure_class = "parse_failure"
        except PdfDualVlmFactProviderError as exc:
            failure_class = exc.failure_class
            if not response_bytes:
                response_bytes = _canonical_json_bytes({"error_code": exc.code})

        resolved = str(payload.get("model") or "")
        if (resolved and resolved != self.config.openai_model_id) or (
            failure_class is None and not resolved
        ):
            failure_class = "resolved_model_mismatch"
            value = None
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        input_details = (
            usage.get("input_tokens_details")
            if isinstance(usage.get("input_tokens_details"), dict)
            else {}
        )
        output_details = (
            usage.get("output_tokens_details")
            if isinstance(usage.get("output_tokens_details"), dict)
            else {}
        )
        visible = text.encode("utf-8") if isinstance(text, str) else b""
        schema_hash = _sha256_json(output_schema)
        attempt = {
            "task_id": task_id,
            "attempt_id": f"{task_id}_a1",
            "attempt_number": 1,
            "attempt_lineage": [],
            "provider": "openai",
            "provider_profile": self.profile.profile_id,
            "provider_profile_revision": gate2_provider_profile_revision(self.profile),
            "model_requested": self.config.openai_model_id,
            "model_resolved": resolved or None,
            "adapter_identity": OPENAI_ADAPTER_VERSION,
            "transport_identity": "openai_responses_native_png_json_schema",
            "request_hash": _sha256_json(response_body),
            "crop_sha256": crop_sha256,
            "model_view_hash": _sha256_json(model_view),
            "canonical_schema_hash": schema_hash,
            "adapted_schema_hash": schema_hash,
            "schema_transform_count": 0,
            "started_at": started_at,
            "ended_at": _utc_now(),
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "http_status": status,
            "provider_response_id": payload.get("id"),
            "usage": {
                "input_tokens": usage.get("input_tokens"),
                "cached_input_tokens": input_details.get("cached_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "reasoning_tokens": output_details.get("reasoning_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
            "finish_reason": payload.get("status"),
            "parse_result": parse_result,
            "terminal_failure_class": failure_class,
            "hidden_retry": False,
            "provider_failover": False,
        }
        return {
            "attempt": attempt,
            "json_output": value if failure_class is None else None,
            "text": text,
            "raw_private_response": payload,
            "response_bytes": len(response_bytes),
            "response_hash": hashlib.sha256(response_bytes).hexdigest(),
            "visible_output_bytes": len(visible),
            "visible_output_hash": (
                hashlib.sha256(visible).hexdigest() if visible else None
            ),
        }

    def _response_body(
        self,
        *,
        model_view: dict[str, Any],
        output_schema: dict[str, Any],
        png_bytes: bytes,
    ) -> dict[str, Any]:
        return {
            "model": self.config.openai_model_id,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                model_view,
                                ensure_ascii=False,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": "data:image/png;base64,"
                            + base64.b64encode(png_bytes).decode("ascii"),
                            "detail": self.config.openai_image_detail,
                        },
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": OPENAI_SCHEMA_NAME,
                    "strict": True,
                    "schema": copy.deepcopy(output_schema),
                }
            },
            "temperature": 0,
            "max_output_tokens": self.config.extraction_maximum_output_tokens,
            "store": False,
        }

    @staticmethod
    def _validate_crop(png_bytes: bytes, crop_sha256: str) -> None:
        if hashlib.sha256(png_bytes).hexdigest() != crop_sha256:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_crop_hash_mismatch",
                "request_validation",
            )

    def _request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None,
    ) -> tuple[int, bytes]:
        request = Request(
            url,
            data=_canonical_json_bytes(body) if body is not None else None,
            method=method,
            headers={
                "authorization": f"Bearer {self.connection.api_key}",
                "content-type": "application/json",
            },
        )
        try:
            with self.urlopen_fn(
                request, timeout=self.config.timeout_seconds
            ) as response:
                return int(response.status), response.read(
                    MAX_OPENAI_RESPONSE_BYTES + 1
                )
        except HTTPError as exc:
            return int(exc.code), exc.read(MAX_OPENAI_RESPONSE_BYTES + 1)
        except (TimeoutError, URLError) as exc:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_transport_failed",
                "timeout_or_transport",
            ) from exc

    def _base_url(self) -> str:
        return self.connection.base_url.rstrip("/")

    @staticmethod
    def _decode_json(body: bytes) -> dict[str, Any]:
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_invalid_json",
                "provider_invalid_json",
            ) from exc
        if not isinstance(value, dict):
            raise PdfDualVlmFactProviderError(
                "pdf_dual_vlm_openai_response_not_object",
                "provider_invalid_json",
            )
        return value


def _openai_output_texts(payload: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if (
                isinstance(content, dict)
                and content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ):
                texts.append(content["text"])
    return texts


def _has_refusal(payload: dict[str, Any]) -> bool:
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal" or content.get("refusal"):
                return True
    return False


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


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
