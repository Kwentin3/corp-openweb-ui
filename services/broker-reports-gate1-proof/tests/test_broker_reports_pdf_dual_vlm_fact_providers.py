from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pdf_dual_vlm_fact_providers.py"


def _load_module():
    name = "pdf_dual_vlm_fact_providers_test"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PROVIDERS = _load_module()


class PdfDualVlmFactProviderFactoryTests(unittest.TestCase):
    def test_factory_returns_frozen_gemini_and_openai_adapters(self) -> None:
        transport = _FakeUrlOpen()
        bundle = PROVIDERS.PdfDualVlmFactProviderFactory(
            urlopen_fn=transport
        ).create_for_openwebui(_openwebui_request())

        self.assertEqual(
            PROVIDERS.DEFAULT_GEMINI_MODEL_ID,
            bundle.detector.config.model_id,
        )
        self.assertEqual(
            PROVIDERS.DEFAULT_GEMINI_MODEL_ID,
            bundle.gemini.config.model_id,
        )
        self.assertEqual(
            PROVIDERS.DEFAULT_OPENAI_MODEL_ID,
            bundle.openai.config.openai_model_id,
        )
        self.assertEqual("google_gemini", bundle.gemini.profile.profile_id)
        self.assertEqual("openai_gpt", bundle.openai.profile.profile_id)
        self.assertEqual(4_096, bundle.detector.config.maximum_output_tokens)
        self.assertEqual(16_384, bundle.gemini.config.maximum_output_tokens)
        self.assertEqual([], transport.requests)

    def test_factory_rejects_models_outside_research_allowlists(self) -> None:
        cases = (
            PROVIDERS.PdfDualVlmFactProviderConfig(
                gemini_model_id="models/gemini-not-allowlisted"
            ),
            PROVIDERS.PdfDualVlmFactProviderConfig(
                openai_model_id="gpt-not-allowlisted"
            ),
        )
        for config in cases:
            with (
                self.subTest(config=config),
                self.assertRaises(PROVIDERS.PdfDualVlmFactProviderError) as raised,
            ):
                PROVIDERS.PdfDualVlmFactProviderFactory(
                    config,
                    urlopen_fn=_FakeUrlOpen(),
                ).create_for_openwebui(_openwebui_request())
            self.assertEqual("provider_configuration", raised.exception.failure_class)

    def test_bundle_qualifies_both_exact_models_without_generation(self) -> None:
        transport = _FakeUrlOpen()
        bundle = PROVIDERS.PdfDualVlmFactProviderFactory(
            urlopen_fn=transport
        ).create_for_openwebui(_openwebui_request())

        result = bundle.qualify()

        self.assertEqual("qualified", result["detector"]["status"])
        self.assertEqual("qualified", result["gemini"]["status"])
        self.assertEqual("qualified", result["openai"]["status"])
        self.assertTrue(result["detector"]["exact_model_match"])
        self.assertTrue(result["gemini"]["exact_model_match"])
        self.assertTrue(result["openai"]["exact_model_match"])
        self.assertEqual(3, len(transport.requests))
        self.assertTrue(all(request.method == "GET" for request in transport.requests))
        self.assertFalse(result["openai"]["hidden_retry"])
        self.assertFalse(result["openai"]["provider_failover"])

    def test_factory_and_transport_anti_drift_anchors_are_enforced(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertIn(
            "PdfDualVlmFactProviderFactory.create_for_openwebui",
            PROVIDERS.FACTORY_REQUIRED,
        )
        self.assertIn("must not construct provider payloads", PROVIDERS.FORBIDDEN)
        self.assertNotIn("import requests", source)
        self.assertFalse(any(isinstance(node, ast.While) for node in ast.walk(tree)))

        constructor_owners = {
            node.func.id: _enclosing_function_name(tree, node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id
            in {
                "PdfGridExperimentProviderFactory",
                "OpenAIResponsesVisionAdapter",
            }
        }
        self.assertEqual(
            {
                "PdfGridExperimentProviderFactory": "create_for_openwebui",
                "OpenAIResponsesVisionAdapter": "create_for_openwebui",
            },
            constructor_owners,
        )


class OpenAIResponsesVisionAdapterTests(unittest.TestCase):
    def test_one_count_then_one_generate_uses_same_png_and_strict_schema(self) -> None:
        transport = _FakeUrlOpen()
        adapter = _bundle(transport).openai
        png = b"\x89PNG\r\n\x1a\nimmutable-crop"
        crop_hash = hashlib.sha256(png).hexdigest()
        model_view = {"task": "extract_financial_facts", "crop_sha256": crop_hash}
        schema = _fact_schema()

        counted = adapter.count_tokens(
            model_view=model_view,
            output_schema=schema,
            png_bytes=png,
            crop_sha256=crop_hash,
        )
        result = adapter.invoke(
            task_id="crop_1_openai",
            model_view=model_view,
            output_schema=schema,
            png_bytes=png,
            crop_sha256=crop_hash,
            attempt_number=1,
            attempt_lineage=[],
        )

        self.assertEqual(321, counted["total_tokens"])
        self.assertEqual({"facts": []}, result["json_output"])
        self.assertIsNone(result["attempt"]["terminal_failure_class"])
        self.assertEqual("completed", result["attempt"]["finish_reason"])
        self.assertEqual("parsed_object", result["attempt"]["parse_result"])
        self.assertFalse(result["attempt"]["hidden_retry"])
        self.assertFalse(result["attempt"]["provider_failover"])
        self.assertEqual(17, result["attempt"]["usage"]["cached_input_tokens"])
        self.assertEqual(5, result["attempt"]["usage"]["reasoning_tokens"])

        post_requests = [
            request for request in transport.requests if request.method == "POST"
        ]
        self.assertEqual(2, len(post_requests))
        self.assertEqual(
            ["/responses/input_tokens", "/responses"],
            [_request_path(request) for request in post_requests],
        )
        count_body, response_body = [
            json.loads(request.data.decode("utf-8")) for request in post_requests
        ]
        count_image = count_body["input"][0]["content"][1]
        response_image = response_body["input"][0]["content"][1]
        self.assertEqual(count_image, response_image)
        self.assertEqual("input_image", response_image["type"])
        self.assertEqual("high", response_image["detail"])
        self.assertEqual(
            "data:image/png;base64,iVBORw0KGgppbW11dGFibGUtY3JvcA==",
            response_image["image_url"],
        )
        self.assertEqual(schema, count_body["text"]["format"]["schema"])
        self.assertEqual(schema, response_body["text"]["format"]["schema"])
        self.assertTrue(response_body["text"]["format"]["strict"])
        self.assertEqual("json_schema", response_body["text"]["format"]["type"])
        self.assertEqual(0, response_body["temperature"])
        self.assertEqual(16_384, response_body["max_output_tokens"])
        self.assertIs(False, response_body["store"])
        self.assertNotIn("temperature", count_body)
        self.assertNotIn("store", count_body)

    def test_terminal_failures_never_retry_or_publish_json(self) -> None:
        cases = {
            "malformed": "parse_failure",
            "multiple_text": "parse_failure",
            "refusal": "provider_refusal",
            "incomplete": "provider_incomplete",
            "model_mismatch": "resolved_model_mismatch",
        }
        png = b"\x89PNG\r\n\x1a\nterminal-crop"
        crop_hash = hashlib.sha256(png).hexdigest()
        for mode, expected_failure in cases.items():
            with self.subTest(mode=mode):
                transport = _FakeUrlOpen(mode=mode)
                adapter = _bundle(transport).openai
                counted = adapter.count_tokens(
                    model_view={"task": "facts"},
                    output_schema=_fact_schema(),
                    png_bytes=png,
                    crop_sha256=crop_hash,
                )
                result = adapter.invoke(
                    task_id=f"crop_{mode}",
                    model_view={"task": "facts"},
                    output_schema=_fact_schema(),
                    png_bytes=png,
                    crop_sha256=crop_hash,
                    attempt_number=1,
                    attempt_lineage=[],
                )

                self.assertEqual(321, counted["input_tokens"])
                self.assertIsNone(result["json_output"])
                self.assertEqual(
                    expected_failure,
                    result["attempt"]["terminal_failure_class"],
                )
                self.assertFalse(result["attempt"]["hidden_retry"])
                self.assertFalse(result["attempt"]["provider_failover"])
                self.assertEqual(
                    1,
                    sum(
                        _request_path(request) == "/responses/input_tokens"
                        for request in transport.requests
                    ),
                )
                self.assertEqual(
                    1,
                    sum(
                        _request_path(request) == "/responses"
                        for request in transport.requests
                    ),
                )

    def test_crop_hash_and_attempt_policy_fail_before_network(self) -> None:
        transport = _FakeUrlOpen()
        adapter = _bundle(transport).openai
        png = b"crop"
        with self.assertRaises(PROVIDERS.PdfDualVlmFactProviderError) as crop_error:
            adapter.count_tokens(
                model_view={},
                output_schema=_fact_schema(),
                png_bytes=png,
                crop_sha256="0" * 64,
            )
        self.assertEqual("request_validation", crop_error.exception.failure_class)

        with self.assertRaises(PROVIDERS.PdfDualVlmFactProviderError) as attempt_error:
            adapter.invoke(
                task_id="bad_attempt",
                model_view={},
                output_schema=_fact_schema(),
                png_bytes=png,
                crop_sha256=hashlib.sha256(png).hexdigest(),
                attempt_number=2,
                attempt_lineage=["bad_attempt_a1"],
            )
        self.assertEqual("attempt_policy", attempt_error.exception.failure_class)
        self.assertEqual([], transport.requests)

    def test_count_budget_is_terminal_and_does_not_generate(self) -> None:
        transport = _FakeUrlOpen(input_tokens=25_000)
        adapter = _bundle(transport).openai
        png = b"crop"
        with self.assertRaises(PROVIDERS.PdfDualVlmFactProviderError) as raised:
            adapter.count_tokens(
                model_view={},
                output_schema=_fact_schema(),
                png_bytes=png,
                crop_sha256=hashlib.sha256(png).hexdigest(),
            )

        self.assertEqual("context_budget", raised.exception.failure_class)
        self.assertEqual(
            {
                "observed_total_tokens": 25_000,
                "maximum_counted_input_tokens": 24_000,
            },
            raised.exception.safe_details,
        )
        self.assertEqual(
            ["/responses/input_tokens"], [_request_path(r) for r in transport.requests]
        )


class _Response:
    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        self.status = status
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit: int) -> bytes:
        return self.payload[:limit]


class _FakeUrlOpen:
    def __init__(self, *, mode: str = "success", input_tokens: int = 321) -> None:
        self.mode = mode
        self.input_tokens = input_tokens
        self.requests: list[Any] = []

    def __call__(self, request, timeout: int):
        self.requests.append(request)
        self._assert_boundary_request(request, timeout)
        path = _request_path(request)
        if (
            request.method == "GET"
            and "generativelanguage.googleapis.com" in request.full_url
        ):
            return _Response(
                {
                    "name": PROVIDERS.DEFAULT_GEMINI_MODEL_ID,
                    "supportedGenerationMethods": ["generateContent", "countTokens"],
                    "inputTokenLimit": 1_048_576,
                    "outputTokenLimit": 65_536,
                }
            )
        if request.method == "GET" and path.startswith("/models/"):
            return _Response({"id": PROVIDERS.DEFAULT_OPENAI_MODEL_ID})
        if path == "/responses/input_tokens":
            return _Response(
                {
                    "object": "response.input_tokens",
                    "input_tokens": self.input_tokens,
                }
            )
        if path == "/responses":
            return _Response(self._openai_response())
        raise AssertionError(
            f"unexpected boundary request: {request.method} {request.full_url}"
        )

    @staticmethod
    def _assert_boundary_request(request, timeout: int) -> None:
        if timeout != 240:
            raise AssertionError("unexpected timeout")

    def _openai_response(self) -> dict[str, Any]:
        model = PROVIDERS.DEFAULT_OPENAI_MODEL_ID
        status = "completed"
        content: list[dict[str, Any]] = [
            {"type": "output_text", "text": '{"facts":[]}'},
        ]
        if self.mode == "malformed":
            content = [{"type": "output_text", "text": "not-json"}]
        elif self.mode == "multiple_text":
            content.append({"type": "output_text", "text": '{"facts":[]}'})
        elif self.mode == "refusal":
            content = [{"type": "refusal", "refusal": "cannot comply"}]
        elif self.mode == "incomplete":
            status = "incomplete"
        elif self.mode == "model_mismatch":
            model = "gpt-5.4-mini"
        return {
            "id": "resp_test_1",
            "object": "response",
            "status": status,
            "model": model,
            "output": [
                {
                    "type": "message",
                    "status": status,
                    "content": content,
                }
            ],
            "usage": {
                "input_tokens": 340,
                "input_tokens_details": {"cached_tokens": 17},
                "output_tokens": 21,
                "output_tokens_details": {"reasoning_tokens": 5},
                "total_tokens": 361,
            },
        }


def _bundle(transport: _FakeUrlOpen):
    return PROVIDERS.PdfDualVlmFactProviderFactory(
        urlopen_fn=transport
    ).create_for_openwebui(_openwebui_request())


def _openwebui_request() -> Any:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    OPENAI_API_BASE_URLS=[
                        "https://api.openai.com/v1",
                        "https://generativelanguage.googleapis.com/v1beta/openai",
                    ],
                    OPENAI_API_KEYS=["openai-secret", "gemini-secret"],
                    OPENAI_API_CONFIGS={
                        "0": {"enable": True},
                        "1": {"enable": True},
                    },
                )
            )
        )
    )


def _fact_schema() -> dict[str, Any]:
    return {
        "$id": "broker_reports_pdf_dual_vlm_fact_output_v1",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"fact_id": {"type": "string"}},
                    "required": ["fact_id"],
                },
            }
        },
        "required": ["facts"],
    }


def _request_path(request: Any) -> str:
    value = request.full_url.split("?", 1)[0]
    for marker in ("/v1beta/openai", "/v1"):
        if marker in value:
            return value.split(marker, 1)[1]
    return value


def _enclosing_function_name(tree: ast.AST, target: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            child is target for child in ast.walk(node)
        ):
            return node.name
    return None


if __name__ == "__main__":
    unittest.main()
