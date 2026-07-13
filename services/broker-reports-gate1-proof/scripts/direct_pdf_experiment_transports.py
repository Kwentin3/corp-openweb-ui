from __future__ import annotations

import base64
import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

import requests


MAX_RESPONSE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class ProviderConnection:
    provider: str
    base_url: str
    api_key: str = field(repr=False)


@dataclass(frozen=True)
class ProviderSpec:
    provider: str
    model: str
    transport: str


PROVIDER_SPECS = (
    ProviderSpec("openai", "gpt-5.4-mini-2026-03-17", "openai_responses_input_file_inline_pdf"),
    ProviderSpec("google", "models/gemini-3.5-flash", "gemini_generate_content_inline_pdf"),
    ProviderSpec("anthropic", "claude-sonnet-5", "anthropic_messages_document_base64_pdf"),
)


class NativePdfTransport:
    def __init__(self, connection: ProviderConnection, *, timeout: int = 600) -> None:
        self.connection = connection
        self.timeout = timeout

    def qualify_models(self) -> dict[str, Any]:
        if self.connection.provider == "google":
            url = self.connection.base_url.removesuffix("/openai") + "/models"
            headers = {"x-goog-api-key": self.connection.api_key}
        elif self.connection.provider == "anthropic":
            url = self.connection.base_url + "/models"
            headers = {
                "x-api-key": self.connection.api_key,
                "anthropic-version": "2023-06-01",
            }
        else:
            url = self.connection.base_url + "/models"
            headers = {"Authorization": f"Bearer {self.connection.api_key}"}
        response = requests.get(url, headers=headers, timeout=60)
        payload = _response_json(response)
        ids = _model_ids(payload)
        return {
            "http_status": response.status_code,
            "response_bytes": len(response.content),
            "model_ids": ids,
            "response_hash": hashlib.sha256(response.content).hexdigest(),
        }

    def invoke(
        self,
        *,
        spec: ProviderSpec,
        pdf_bytes: bytes,
        filename: str,
        prompt: str,
        schema: dict[str, Any],
        schema_name: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if spec.provider != self.connection.provider:
            raise ValueError("provider_connection_mismatch")
        if spec.provider == "openai":
            return self._openai(spec, pdf_bytes, filename, prompt, schema, schema_name, max_output_tokens)
        if spec.provider == "google":
            return self._gemini(spec, pdf_bytes, prompt, schema, max_output_tokens)
        return self._anthropic(spec, pdf_bytes, prompt, schema, max_output_tokens)

    def invoke_plain_text(
        self,
        *,
        spec: ProviderSpec,
        pdf_bytes: bytes,
        filename: str,
        prompt: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if spec.provider != self.connection.provider:
            raise ValueError("provider_connection_mismatch")
        if spec.provider == "openai":
            return self._openai_plain(spec, pdf_bytes, filename, prompt, max_output_tokens)
        if spec.provider == "google":
            return self._gemini_plain(spec, pdf_bytes, prompt, max_output_tokens)
        return self._anthropic_plain(spec, pdf_bytes, prompt, max_output_tokens)

    def _openai(
        self,
        spec: ProviderSpec,
        pdf_bytes: bytes,
        filename: str,
        prompt: str,
        schema: dict[str, Any],
        schema_name: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        body = {
            "model": spec.model,
            "input": [{
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": filename,
                        "file_data": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii"),
                    },
                    {"type": "input_text", "text": prompt},
                ],
            }],
            "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
            "temperature": 0,
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        private, safe = self._post(
            self.connection.base_url + "/responses",
            {"Authorization": f"Bearer {self.connection.api_key}"},
            body,
            parser=_parse_openai,
        )
        safe.update(_schema_projection_metadata(schema, schema, 0))
        return private, safe

    def _gemini(
        self,
        spec: ProviderSpec,
        pdf_bytes: bytes,
        prompt: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        model = spec.model.removeprefix("models/")
        body = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(pdf_bytes).decode("ascii")}},
                    {"text": prompt},
                ],
            }],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        url = self.connection.base_url.removesuffix("/openai") + f"/models/{model}:generateContent"
        private, safe = self._post(url, {"x-goog-api-key": self.connection.api_key}, body, parser=_parse_gemini)
        safe.update(_schema_projection_metadata(schema, schema, 0))
        return private, safe

    def _anthropic(
        self,
        spec: ProviderSpec,
        pdf_bytes: bytes,
        prompt: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        adapted_schema = copy.deepcopy(schema)
        transform_count = _project_anthropic_schema(adapted_schema)
        body = {
            "model": spec.model,
            "max_tokens": max_output_tokens,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(pdf_bytes).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
            "output_config": {"format": {"type": "json_schema", "schema": adapted_schema}},
        }
        private, safe = self._post(
            self.connection.base_url + "/messages",
            {"x-api-key": self.connection.api_key, "anthropic-version": "2023-06-01"},
            body,
            parser=_parse_anthropic,
        )
        safe.update(_schema_projection_metadata(schema, adapted_schema, transform_count))
        return private, safe

    def _openai_plain(
        self,
        spec: ProviderSpec,
        pdf_bytes: bytes,
        filename: str,
        prompt: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        body = {
            "model": spec.model,
            "input": [{
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": filename,
                        "file_data": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii"),
                    },
                    {"type": "input_text", "text": prompt},
                ],
            }],
            "temperature": 0,
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        return self._post_plain(
            self.connection.base_url + "/responses",
            {"Authorization": f"Bearer {self.connection.api_key}"},
            body,
            provider="openai",
        )

    def _gemini_plain(
        self,
        spec: ProviderSpec,
        pdf_bytes: bytes,
        prompt: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        model = spec.model.removeprefix("models/")
        body = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(pdf_bytes).decode("ascii")}},
                    {"text": prompt},
                ],
            }],
            "generationConfig": {"temperature": 0, "maxOutputTokens": max_output_tokens},
        }
        return self._post_plain(
            self.connection.base_url.removesuffix("/openai") + f"/models/{model}:generateContent",
            {"x-goog-api-key": self.connection.api_key},
            body,
            provider="google",
        )

    def _anthropic_plain(
        self,
        spec: ProviderSpec,
        pdf_bytes: bytes,
        prompt: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        body = {
            "model": spec.model,
            "max_tokens": max_output_tokens,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(pdf_bytes).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        }
        return self._post_plain(
            self.connection.base_url + "/messages",
            {"x-api-key": self.connection.api_key, "anthropic-version": "2023-06-01"},
            body,
            provider="anthropic",
        )

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any], *, parser) -> tuple[dict[str, Any], dict[str, Any]]:
        started = time.perf_counter()
        response = requests.post(url, headers={**headers, "content-type": "application/json"}, json=body, timeout=self.timeout)
        duration = time.perf_counter() - started
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise RuntimeError("provider_response_budget_exceeded")
        payload = _response_json(response)
        parsed, parse_error = parser(payload) if response.ok else (None, None)
        usage = _usage(self.connection.provider, payload)
        safe = {
            "http_status": response.status_code,
            "provider_status": "passed" if response.ok and isinstance(parsed, dict) else "failed",
            "parse_error": parse_error,
            "duration_seconds": round(duration, 3),
            "response_bytes": len(response.content),
            "response_hash": hashlib.sha256(response.content).hexdigest(),
            "response_id": _response_id(payload),
            "resolved_model": str(payload.get("model") or "") if isinstance(payload, dict) else "",
            **usage,
        }
        if not response.ok:
            safe["failure_class"] = _failure_class(response.status_code, payload)
        private = {"request": body, "response": payload, "parsed": parsed}
        return private, safe

    def _post_plain(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        *,
        provider: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        started = time.perf_counter()
        response = requests.post(
            url,
            headers={**headers, "content-type": "application/json"},
            json=body,
            timeout=self.timeout,
        )
        duration = time.perf_counter() - started
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise RuntimeError("provider_response_budget_exceeded")
        payload = _response_json(response)
        text, parse_error = parse_plain_text_payload(provider, payload) if response.ok else (None, None)
        safe = {
            "http_status": response.status_code,
            "provider_status": "passed" if response.ok and isinstance(text, str) and bool(text.strip()) else "failed",
            "parse_error": parse_error,
            "duration_seconds": round(duration, 3),
            "response_bytes": len(response.content),
            "response_hash": hashlib.sha256(response.content).hexdigest(),
            "response_id": _response_id(payload),
            "resolved_model": str(payload.get("model") or "") if isinstance(payload, dict) else "",
            **_usage(provider, payload),
        }
        if not response.ok:
            safe["failure_class"] = _failure_class(response.status_code, payload)
        return {"request": body, "response": payload, "text": text}, safe


def connections_from_openwebui_config(config: dict[str, Any]) -> dict[str, ProviderConnection]:
    urls = config.get("OPENAI_API_BASE_URLS")
    keys = config.get("OPENAI_API_KEYS")
    entries = config.get("OPENAI_API_CONFIGS")
    if not isinstance(urls, list) or not isinstance(keys, list):
        raise ValueError("openwebui_connections_invalid")
    result: dict[str, ProviderConnection] = {}
    for index, raw_url in enumerate(urls):
        base_url = str(raw_url or "").rstrip("/")
        entry = entries.get(str(index), {}) if isinstance(entries, dict) else {}
        if isinstance(entry, dict) and entry.get("enable") is False:
            continue
        provider = _provider_for_url(base_url)
        key = str(keys[index] if index < len(keys) else "")
        if provider and key:
            if provider in result:
                raise ValueError(f"openwebui_connection_ambiguous_{provider}")
            result[provider] = ProviderConnection(provider, base_url, key)
    return result


def parse_provider_payload(provider: str, payload: dict[str, Any]) -> tuple[Any, str | None]:
    if provider == "openai":
        return _parse_openai(payload)
    if provider == "google":
        return _parse_gemini(payload)
    if provider == "anthropic":
        return _parse_anthropic(payload)
    return None, "provider_unknown"


def parse_plain_text_payload(provider: str, payload: dict[str, Any]) -> tuple[str | None, str | None]:
    texts: list[str] = []
    if provider == "openai":
        for item in payload.get("output") or []:
            for content in item.get("content") or [] if isinstance(item, dict) else []:
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    texts.append(content["text"])
    elif provider == "google":
        for candidate in payload.get("candidates") or []:
            content = candidate.get("content") if isinstance(candidate, dict) else {}
            for part in content.get("parts") or [] if isinstance(content, dict) else []:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part["text"])
    elif provider == "anthropic":
        texts = [
            item["text"]
            for item in payload.get("content") or []
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
        ]
    else:
        return None, "provider_unknown"
    if not texts or not any(value.strip() for value in texts):
        return None, "plain_text_block_missing"
    return "".join(texts), None


def _provider_for_url(url: str) -> str | None:
    lowered = url.lower()
    if lowered.startswith("https://api.openai.com"):
        return "openai"
    if lowered.startswith("https://api.anthropic.com"):
        return "anthropic"
    if lowered.startswith("https://generativelanguage.googleapis.com"):
        return "google"
    return None


def _response_json(response: requests.Response) -> dict[str, Any]:
    try:
        value = response.json()
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _parse_openai(payload: dict[str, Any]) -> tuple[Any, str | None]:
    texts = []
    for item in payload.get("output") or []:
        for content in item.get("content") or [] if isinstance(item, dict) else []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                texts.append(content["text"])
    return _parse_single_text(texts)


def _parse_gemini(payload: dict[str, Any]) -> tuple[Any, str | None]:
    texts = []
    for candidate in payload.get("candidates") or []:
        content = candidate.get("content") if isinstance(candidate, dict) else {}
        for part in content.get("parts") or [] if isinstance(content, dict) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    if not texts:
        return None, "structured_text_block_count_invalid"
    try:
        return json.loads("".join(texts)), None
    except ValueError as exc:
        return None, type(exc).__name__


def _parse_anthropic(payload: dict[str, Any]) -> tuple[Any, str | None]:
    texts = [item["text"] for item in payload.get("content") or [] if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)]
    return _parse_single_text(texts)


def _parse_single_text(texts: list[str]) -> tuple[Any, str | None]:
    if len(texts) != 1:
        return None, "structured_text_block_count_invalid"
    try:
        return json.loads(texts[0]), None
    except ValueError as exc:
        return None, type(exc).__name__


def _usage(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    if provider == "google":
        usage = payload.get("usageMetadata") if isinstance(payload.get("usageMetadata"), dict) else {}
        return {
            "input_tokens": usage.get("promptTokenCount"),
            "output_tokens": usage.get("candidatesTokenCount"),
            "total_tokens": usage.get("totalTokenCount"),
        }
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    return {
        "input_tokens": usage.get("input_tokens", usage.get("prompt_tokens")),
        "output_tokens": usage.get("output_tokens", usage.get("completion_tokens")),
        "total_tokens": usage.get("total_tokens"),
    }


def _response_id(payload: dict[str, Any]) -> str:
    value = payload.get("id") or payload.get("responseId")
    return str(value or "")[:200]


def _failure_class(status: int, payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, ensure_ascii=True).lower()
    if status in {401, 403}:
        return "provider_auth_failed"
    if status == 429:
        return "provider_rate_limited"
    if "model" in rendered and ("not found" in rendered or "not exist" in rendered):
        return "model_unavailable"
    if "schema" in rendered or "output_config" in rendered or "responsejsonschema" in rendered:
        return "structured_output_rejected"
    if "pdf" in rendered or "document" in rendered or "mime" in rendered:
        return "native_pdf_rejected"
    return "provider_error"


def _model_ids(payload: dict[str, Any]) -> list[str]:
    rows = payload.get("data") if isinstance(payload.get("data"), list) else payload.get("models")
    result = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        value = row.get("id") or row.get("name")
        if value:
            result.append(str(value))
    return sorted(set(result))


_ANTHROPIC_UNSUPPORTED_SCHEMA_KEYWORDS = {
    "default", "examples", "exclusiveMaximum", "exclusiveMinimum", "maxItems", "maxLength",
    "maxProperties", "maximum", "minItems", "minLength", "minProperties", "minimum", "multipleOf",
    "pattern", "uniqueItems",
}


def _project_anthropic_schema(value: Any) -> int:
    if isinstance(value, list):
        return sum(_project_anthropic_schema(item) for item in value)
    if not isinstance(value, dict):
        return 0
    removed = 0
    for key in tuple(value):
        if key in _ANTHROPIC_UNSUPPORTED_SCHEMA_KEYWORDS:
            value.pop(key)
            removed += 1
    return removed + sum(_project_anthropic_schema(item) for item in value.values())


def _schema_projection_metadata(canonical: dict[str, Any], adapted: dict[str, Any], transform_count: int) -> dict[str, Any]:
    return {
        "canonical_schema_sha256": _hash_schema(canonical),
        "adapted_schema_sha256": _hash_schema(adapted),
        "schema_transform_count": transform_count,
    }


def _hash_schema(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()
