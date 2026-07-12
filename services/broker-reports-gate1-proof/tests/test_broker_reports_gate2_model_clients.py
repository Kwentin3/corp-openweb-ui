from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODEL_MODULE_PATHS = (
    ROOT / "broker_reports_gate1" / "gate2_model_contracts.py",
    ROOT / "broker_reports_gate1" / "gate2_model_requests.py",
    ROOT / "broker_reports_gate1" / "gate2_provider_adapters.py",
    ROOT / "broker_reports_gate1" / "gate2_model_clients.py",
)

from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    MAX_MODEL_CONTENT_BYTES,
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    GATE2_PROVIDER_PROFILES,
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelResult,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    DOMAIN_REQUEST_PROFILE,
    GATE2_REQUEST_PROFILES,
    SOURCE_REQUEST_PROFILE,
)
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    FACTORY_REQUIRED as PROVIDER_FACTORY_REQUIRED,
    FORBIDDEN as PROVIDER_FORBIDDEN,
    Gate2GeminiResponseFormatAdapter,
    Gate2AnthropicNativeMessagesAdapter,
    Gate2NativeProviderTransportConfig,
    Gate2OpenWebUIProviderConnection,
    Gate2OpenWebUIProviderConnectionResolver,
    Gate2OpenAIResponseFormatAdapter,
)
from broker_reports_gate1.gate2_source_fact_contracts import (  # noqa: E402
    Gate2ManagedPrompt,
    Gate2PromptError,
    gate2_prompt_hash,
)


EXPECTED_PROVIDER_STATUSES = {
    "openai_gpt": "approved",
    "anthropic_claude": "probe_required",
    "google_gemini": "approved",
    "deepseek": "unsupported",
    "zai_glm": "unsupported",
    "alibaba_qwen": "unsupported",
}

DEFAULT_MODEL_ID = "gpt-5.6-sol"

_DEFAULT_RESPONSE_FORMAT = object()


class CompletionBoundary:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.resolved_user_ids: list[str] = []
        self.calls: list[dict[str, Any]] = []

    def resolve(self, user_id: str):
        self.resolved_user_ids.append(user_id)
        return self.complete, SimpleNamespace(id=user_id, role="admin")

    def complete(
        self,
        *,
        request,
        form_data,
        user,
        bypass_filter=False,
        bypass_system_prompt=False,
    ):
        self.calls.append(
            {
                "request": request,
                "form_data": copy.deepcopy(form_data),
                "user": user,
                "bypass_filter": bypass_filter,
                "bypass_system_prompt": bypass_system_prompt,
            }
        )
        return copy.deepcopy(self.response)


class NativeTransportBoundary:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def resolve(self, profile, form_data):
        self.calls.append(
            {
                "profile_id": profile.profile_id,
                "form_data": copy.deepcopy(form_data),
            }
        )
        return copy.deepcopy(self.response)


class BrokerReportsGate2ModelClientsTest(unittest.TestCase):
    def test_registry_and_default_capability_matrix_are_explicit_and_fail_closed(self):
        self.assertEqual(
            {profile.profile_id: profile.gate2_status for profile in GATE2_PROVIDER_PROFILES},
            EXPECTED_PROVIDER_STATUSES,
        )
        self.assertEqual(
            GATE2_REQUEST_PROFILES,
            (SOURCE_REQUEST_PROFILE, DOMAIN_REQUEST_PROFILE),
        )
        self.assertEqual(gate2_provider_profile("gpt").profile_id, "openai_gpt")
        self.assertEqual(
            gate2_provider_profile("gpt").approved_model_ids,
            ("gpt-5.6-sol",),
        )
        self.assertEqual(gate2_provider_profile("anthropic").profile_id, "anthropic_claude")
        self.assertEqual(
            gate2_provider_profile("anthropic").capability_status,
            "probe_required",
        )
        self.assertEqual(
            gate2_provider_profile("anthropic").availability_status,
            "available",
        )
        self.assertEqual(
            gate2_provider_profile("anthropic").transport_type,
            "anthropic_messages_native_via_openwebui_pipe",
        )
        self.assertEqual(gate2_provider_profile("google").profile_id, "google_gemini")
        self.assertEqual(
            gate2_provider_profile("google").approved_model_ids,
            ("models/gemini-3.5-flash",),
        )
        self.assertEqual(gate2_provider_profile("z.ai").profile_id, "zai_glm")
        self.assertEqual(gate2_provider_profile("alibaba").profile_id, "alibaba_qwen")

        for provider_profile_id, expected_status in EXPECTED_PROVIDER_STATUSES.items():
            for request_profile in GATE2_REQUEST_PROFILES:
                with self.subTest(
                    provider_profile_id=provider_profile_id,
                    request_profile=request_profile,
                ):
                    boundary = CompletionBoundary({"content": {"ok": True}})
                    factory = self._factory(
                        request_profile=request_profile,
                        provider_profile_id=provider_profile_id,
                        boundary=boundary,
                    )
                    if expected_status == "approved":
                        client = factory.create()
                        self.assertEqual(client.provider_profile.profile_id, provider_profile_id)
                        self.assertEqual(client.request_profile, request_profile)
                    else:
                        with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
                            factory.create()
                        self.assertEqual(
                            rejected.exception.code,
                            "gate2_no_strict_structured_provider_available",
                        )
                    self.assertEqual(boundary.resolved_user_ids, [])
                    self.assertEqual(boundary.calls, [])

        with self.assertRaises(Gate2SourceFactRuntimeError) as unknown:
            gate2_provider_profile("unknown-provider")
        self.assertEqual(unknown.exception.code, "gate2_provider_profile_unknown")

    def test_capability_probe_runs_one_controlled_strict_call_only_for_qualifiable_profiles(self):
        for provider_profile_id, provider_status in EXPECTED_PROVIDER_STATUSES.items():
            for request_profile in GATE2_REQUEST_PROFILES:
                with self.subTest(
                    provider_profile_id=provider_profile_id,
                    request_profile=request_profile,
                ):
                    expected_content = {
                        "provider_profile_id": provider_profile_id,
                        "request_profile": request_profile,
                    }
                    boundary = CompletionBoundary({"content": expected_content})
                    native_boundary = NativeTransportBoundary(
                        {
                            "id": "msg_test",
                            "model": "claude-haiku-4-5-20251001",
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(expected_content),
                                }
                            ],
                            "stop_reason": "end_turn",
                            "usage": {"input_tokens": 10, "output_tokens": 5},
                        }
                    )
                    factory = self._factory(
                        request_profile=request_profile,
                        provider_profile_id=provider_profile_id,
                        boundary=boundary,
                        capability_probe=True,
                        native_transport_resolver=native_boundary.resolve,
                        native_transport_config=Gate2NativeProviderTransportConfig(),
                    )
                    if provider_status == "unsupported":
                        with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
                            factory.create()
                        self.assertEqual(
                            rejected.exception.code,
                            "gate2_no_strict_structured_provider_available",
                        )
                        self.assertEqual(boundary.resolved_user_ids, [])
                        self.assertEqual(boundary.calls, [])
                        continue
                    client = factory.create()

                    model_id = (
                        "models/gemini-3.5-flash"
                        if provider_profile_id == "google_gemini"
                        else (
                            "claude-haiku-4-5-20251001"
                            if provider_profile_id == "anthropic_claude"
                            else DEFAULT_MODEL_ID
                        )
                    )
                    result = self._extract(
                        client,
                        prompt=self._prompt(request_profile),
                        package=self._package(request_profile),
                        model_id=model_id,
                    )

                    self.assertIsInstance(result, Gate2StructuredModelResult)
                    self.assertEqual(
                        json.loads(result.content)
                        if provider_profile_id == "anthropic_claude"
                        else result.content,
                        expected_content,
                    )
                    self.assertEqual(result.response_format_type, "json_schema")
                    self.assertEqual(result.response_format_schema_mode, "strict_json_schema")
                    self.assertFalse(result.fallback_used)
                    if provider_profile_id == "anthropic_claude":
                        self.assertEqual(boundary.resolved_user_ids, [])
                        self.assertEqual(boundary.calls, [])
                        self.assertEqual(len(native_boundary.calls), 1)
                        native_form = native_boundary.calls[0]["form_data"]
                        self.assertNotIn("response_format", native_form)
                        self.assertEqual(
                            native_form["output_config"]["format"]["type"],
                            "json_schema",
                        )
                        self.assertEqual(
                            result.execution_metadata.transport_type,
                            "anthropic_messages_native_via_openwebui_pipe",
                        )
                    else:
                        self.assertEqual(boundary.resolved_user_ids, ["model-client-user"])
                        self.assertEqual(len(boundary.calls), 1)
                        self.assertEqual(
                            boundary.calls[0]["form_data"]["response_format"],
                            self._response_format(),
                        )
                        self.assertEqual(native_boundary.calls, [])

    def test_anthropic_native_transport_is_configuration_blocked_before_call(self):
        self.request = object()
        native_boundary = NativeTransportBoundary({"unexpected": True})
        client = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            provider_profile_id="anthropic_claude",
            boundary=CompletionBoundary({"unexpected": True}),
            capability_probe=True,
            native_transport_resolver=native_boundary.resolve,
        ).create()

        with self.assertRaises(Gate2SourceFactRuntimeError) as blocked:
            self._extract(
                client,
                prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
                package=self._package(DOMAIN_REQUEST_PROFILE),
                model_id="claude-haiku-4-5-20251001",
            )

        self.assertEqual(blocked.exception.code, "gate2_provider_configuration_blocked")
        self.assertEqual(blocked.exception.failure_class, "provider_configuration")
        self.assertEqual(native_boundary.calls, [])

    def test_openwebui_connection_resolver_uses_enabled_admin_connection_without_exposing_key(self):
        connection = Gate2OpenWebUIProviderConnectionResolver(self.request).resolve(
            gate2_provider_profile("anthropic")
        )

        self.assertEqual(connection.base_url, "https://api.anthropic.com/v1")
        self.assertEqual(connection.api_key, "unit-anthropic-key")
        self.assertNotIn("unit-anthropic-key", repr(connection))

    def test_openwebui_connection_resolver_fails_closed_for_ambiguous_connections(self):
        config = self.request.app.state.config
        config.OPENAI_API_BASE_URLS.append("https://api.anthropic.com/v1")
        config.OPENAI_API_KEYS.append("second-unit-key")
        config.OPENAI_API_CONFIGS["1"] = {"enable": True}

        with self.assertRaises(Gate2SourceFactRuntimeError) as blocked:
            Gate2OpenWebUIProviderConnectionResolver(self.request).resolve(
                gate2_provider_profile("anthropic")
            )

        self.assertEqual(blocked.exception.code, "gate2_provider_configuration_blocked")
        self.assertEqual(blocked.exception.failure_class, "provider_configuration")

    def test_source_v0_request_and_result_are_observable_without_schema_rewrite(self):
        response_format = self._response_format()
        original_response_format = copy.deepcopy(response_format)
        prompt = self._prompt(SOURCE_REQUEST_PROFILE)
        package = self._package(SOURCE_REQUEST_PROFILE)
        boundary = CompletionBoundary(
            {
                "id": "provider-request-1",
                "model": DEFAULT_MODEL_ID,
                "usage": {
                    "prompt_tokens": 101,
                    "completion_tokens": 17,
                    "total_tokens": 118,
                },
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": {"accepted": True}},
                    }
                ],
            }
        )
        client = self._factory(
            request_profile=SOURCE_REQUEST_PROFILE,
            boundary=boundary,
        ).create()

        result = self._extract(
            client,
            prompt=prompt,
            package=package,
            response_format=response_format,
        )

        self.assertEqual(result.content, {"accepted": True})
        self.assertFalse(result.fallback_used)
        self.assertIsNotNone(result.execution_metadata)
        self.assertEqual(result.execution_metadata.provider_id, "openai")
        self.assertEqual(result.execution_metadata.provider_profile_id, "openai_gpt")
        self.assertEqual(result.execution_metadata.adapter_id, "openai_response_format")
        self.assertEqual(result.execution_metadata.requested_model_id, DEFAULT_MODEL_ID)
        self.assertEqual(result.execution_metadata.resolved_model_id, DEFAULT_MODEL_ID)
        self.assertEqual(result.execution_metadata.provider_response_id, "provider-request-1")
        self.assertEqual(result.execution_metadata.input_tokens, 101)
        self.assertEqual(result.execution_metadata.output_tokens, 17)
        self.assertEqual(result.execution_metadata.total_tokens, 118)
        self.assertEqual(result.execution_metadata.finish_reason, "stop")
        self.assertEqual(result.execution_metadata.schema_transform_count, 0)
        self.assertEqual(
            result.execution_metadata.canonical_request_schema_hash,
            result.execution_metadata.adapted_request_schema_hash,
        )
        self.assertGreaterEqual(result.execution_metadata.duration_ms, 0)
        self.assertEqual(response_format, original_response_format)
        self.assertEqual(boundary.resolved_user_ids, ["model-client-user"])
        self.assertEqual(len(boundary.calls), 1)
        call = boundary.calls[0]
        self.assertIs(call["request"], self.request)
        self.assertTrue(call["bypass_filter"])
        self.assertTrue(call["bypass_system_prompt"])
        form_data = call["form_data"]
        self.assertEqual(form_data["model"], DEFAULT_MODEL_ID)
        self.assertFalse(form_data["stream"])
        self.assertEqual(form_data["response_format"], original_response_format)
        self.assertEqual([item["role"] for item in form_data["messages"]], ["system", "user"])
        self.assertNotIn("{{source_fact_package_json}}", form_data["messages"][0]["content"])
        self.assertIn(
            json.dumps(package, ensure_ascii=False, sort_keys=True),
            form_data["messages"][0]["content"],
        )
        user_request = json.loads(form_data["messages"][1]["content"])
        self.assertEqual(user_request["task"], "extract_broker_reports_source_facts_v0")
        self.assertEqual(user_request["package_ref"], package["package_artifact_ref"])
        self.assertNotIn("private_source_marker", form_data["messages"][1]["content"])
        self.assertEqual(
            form_data["metadata"],
            {
                "broker_reports_gate2": {
                    "source_fact_extraction": True,
                    "structured_output_mode": "openwebui_response_format_json_schema",
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "output_schema_id": prompt.output_schema_id,
                    "output_schema_version": prompt.output_schema_version,
                    "output_schema_hash": package["output_schema"]["output_schema_hash"],
                    "package_ref": package["package_artifact_ref"],
                    "provider_profile_id": "openai_gpt",
                    "provider_adapter_id": "openai_response_format",
                    "provider_adapter_version": "1.0.0",
                }
            },
        )

    def test_domain_v0_preserves_legacy_and_candidate_binding_semantics(self):
        for candidate_binding, expected_task in (
            (False, "extract_broker_reports_domain_source_facts_v0"),
            (True, "select_broker_reports_candidate_bindings_v0"),
        ):
            with self.subTest(candidate_binding=candidate_binding):
                package = self._package(
                    DOMAIN_REQUEST_PROFILE,
                    candidate_binding=candidate_binding,
                )
                prompt = self._prompt(DOMAIN_REQUEST_PROFILE)
                boundary = CompletionBoundary({"response": {"accepted": True}})
                client = self._factory(
                    request_profile=DOMAIN_REQUEST_PROFILE,
                    boundary=boundary,
                ).create()

                result = self._extract(client, prompt=prompt, package=package)

                self.assertEqual(result.content, {"accepted": True})
                self.assertEqual(len(boundary.calls), 1)
                form_data = boundary.calls[0]["form_data"]
                user_request = json.loads(form_data["messages"][1]["content"])
                self.assertEqual(user_request["task"], expected_task)
                self.assertEqual(user_request["extractor_domain"], "income")
                self.assertEqual(user_request["package_ref"], "pkg_domain")
                self.assertEqual(user_request["allowed_fact_types"], ["income"])
                if candidate_binding:
                    self.assertIn("candidate ids", user_request["instruction"])
                    self.assertIn("relation ids", user_request["instruction"])
                else:
                    self.assertIn("source_facts_v0", user_request["instruction"])
                self.assertEqual(
                    form_data["metadata"]["broker_reports_gate2"],
                    {
                        "domain_source_fact_extraction": True,
                        "candidate_binding_enabled": candidate_binding,
                        "extractor_domain": "income",
                        "structured_output_mode": "openwebui_response_format_json_schema",
                        "prompt_ref": prompt.prompt_ref,
                        "prompt_hash": prompt.hash,
                        "package_ref": "pkg_domain",
                        "knowledge_rag_used": False,
                        "vectorization_performed": False,
                        "provider_profile_id": "openai_gpt",
                        "provider_adapter_id": "openai_response_format",
                        "provider_adapter_version": "1.0.0",
                    },
                )

    def test_gemini_approved_live_model_uses_its_profile_adapter_without_probe(self):
        response_format = self._response_format()
        response_format["json_schema"]["schema"]["properties"] = {
            "schema_version": {
                "type": "string",
                "const": "broker_reports_source_facts_v0",
                "default": {"const": "annotation-not-schema"},
                "description": "canonical guidance",
            },
            "completeness": {
                "type": "string",
                "enum": ["complete", "partial"],
            },
            "amount": {
                "type": "string",
                "enum": ["25.00"],
            },
            "movement_type_candidate": {
                "type": "string",
                "enum": ["deposit", "withdrawal"],
            },
        }
        response_format["json_schema"]["schema"]["required"] = [
            "schema_version",
            "completeness",
            "amount",
            "movement_type_candidate",
        ]
        canonical_response_format = copy.deepcopy(response_format)
        boundary = CompletionBoundary(
            {
                "id": "gemini-request-1",
                "model": "models/gemini-3.5-flash",
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 5,
                    "total_tokens": 25,
                },
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": {"accepted": True}},
                    }
                ],
            }
        )
        client = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            provider_profile_id="google_gemini",
            boundary=boundary,
        ).create()

        result = self._extract(
            client,
            prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
            package=self._package(DOMAIN_REQUEST_PROFILE),
            model_id="models/gemini-3.5-flash",
            response_format=response_format,
        )

        self.assertIsInstance(client.provider_adapter, Gate2GeminiResponseFormatAdapter)
        self.assertEqual(len(boundary.calls), 1)
        sent_response_format = boundary.calls[0]["form_data"]["response_format"]
        sent_schema_version = sent_response_format["json_schema"]["schema"][
            "properties"
        ]["schema_version"]
        self.assertNotIn("const", sent_schema_version)
        self.assertNotIn("enum", sent_schema_version)
        self.assertNotIn("default", sent_schema_version)
        self.assertNotIn("description", sent_schema_version)
        sent_properties = sent_response_format["json_schema"]["schema"][
            "properties"
        ]
        self.assertEqual(
            sent_properties["completeness"]["enum"],
            ["complete", "partial"],
        )
        self.assertNotIn("enum", sent_properties["amount"])
        self.assertEqual(
            sent_properties["movement_type_candidate"]["enum"],
            ["deposit", "withdrawal"],
        )
        self.assertEqual(response_format, canonical_response_format)
        self.assertEqual(result.execution_metadata.provider_id, "google")
        self.assertEqual(result.execution_metadata.provider_profile_id, "google_gemini")
        self.assertEqual(result.execution_metadata.adapter_id, "gemini_response_format")
        self.assertEqual(result.execution_metadata.adapter_version, "1.5.0")
        self.assertEqual(result.execution_metadata.schema_transform_count, 4)
        self.assertEqual(
            len(result.execution_metadata.canonical_request_schema_hash),
            64,
        )
        self.assertEqual(
            len(result.execution_metadata.adapted_request_schema_hash),
            64,
        )
        self.assertNotEqual(
            result.execution_metadata.canonical_request_schema_hash,
            result.execution_metadata.adapted_request_schema_hash,
        )
        self.assertEqual(
            result.execution_metadata.resolved_model_id,
            "models/gemini-3.5-flash",
        )

        unqualified = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            provider_profile_id="google_gemini",
            boundary=boundary,
        ).create()
        unqualified_contract = unqualified.execution_contract(
            "models/gemini-unproven"
        )
        self.assertEqual(
            unqualified_contract.provider_profile_id,
            "google_gemini",
        )
        self.assertEqual(
            unqualified_contract.requested_model_id,
            "models/gemini-unproven",
        )
        with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
            self._extract(
                unqualified,
                prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
                package=self._package(DOMAIN_REQUEST_PROFILE),
                model_id="models/gemini-unproven",
            )
        self.assertEqual(
            rejected.exception.code,
            "gate2_no_strict_structured_provider_available",
        )
        self.assertEqual(len(boundary.calls), 1)

    def test_gemini_schema_adaptation_conflict_fails_before_provider_call(self):
        response_format = self._response_format()
        response_format["json_schema"]["schema"]["properties"] = {
            "schema_version": {
                "type": "string",
                "const": "v0",
                "enum": ["v1"],
            }
        }
        boundary = CompletionBoundary({"content": {"unexpected": True}})
        client = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            provider_profile_id="google_gemini",
            boundary=boundary,
        ).create()

        with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
            self._extract(
                client,
                prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
                package=self._package(DOMAIN_REQUEST_PROFILE),
                model_id="models/gemini-3.5-flash",
                response_format=response_format,
            )

        self.assertEqual(
            rejected.exception.code,
            "gate2_provider_schema_adaptation_conflict",
        )
        self.assertEqual(boundary.resolved_user_ids, [])
        self.assertEqual(boundary.calls, [])

    def test_provider_profile_cannot_be_mismatched_with_another_vendor_model(self):
        boundary = CompletionBoundary({"content": {"unexpected": True}})
        client = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            provider_profile_id="openai_gpt",
            boundary=boundary,
        ).create()

        with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
            self._extract(
                client,
                prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
                package=self._package(DOMAIN_REQUEST_PROFILE),
                model_id="claude-sonnet-5",
            )

        self.assertEqual(
            rejected.exception.code,
            "gate2_no_strict_structured_provider_available",
        )
        self.assertEqual(boundary.resolved_user_ids, [])
        self.assertEqual(boundary.calls, [])

        probe_client = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            provider_profile_id="openai_gpt",
            boundary=boundary,
            capability_probe=True,
        ).create()
        with self.assertRaises(Gate2SourceFactRuntimeError) as probe_rejected:
            self._extract(
                probe_client,
                prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
                package=self._package(DOMAIN_REQUEST_PROFILE),
                model_id="models/gemini-3.5-flash",
            )
        self.assertEqual(
            probe_rejected.exception.code,
            "gate2_no_strict_structured_provider_available",
        )
        self.assertEqual(boundary.resolved_user_ids, [])
        self.assertEqual(boundary.calls, [])

    def test_provider_reported_model_mismatch_fails_after_one_call(self):
        boundary = CompletionBoundary(
            {
                "id": "provider-response-mismatch",
                "model": "gpt-5.6-terra",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": {"unexpected": True}},
                    }
                ],
            }
        )
        client = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            provider_profile_id="openai_gpt",
            boundary=boundary,
        ).create()

        with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
            self._extract(
                client,
                prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
                package=self._package(DOMAIN_REQUEST_PROFILE),
            )

        self.assertEqual(
            rejected.exception.code,
            "gate2_provider_resolved_model_mismatch",
        )
        self.assertEqual(
            rejected.exception.failure_class,
            "provider_model_mismatch",
        )
        self.assertEqual(
            rejected.exception.execution_metadata.requested_model_id,
            DEFAULT_MODEL_ID,
        )
        self.assertEqual(
            rejected.exception.execution_metadata.resolved_model_id,
            "gpt-5.6-terra",
        )
        self.assertEqual(len(boundary.calls), 1)

    def test_oversized_model_content_fails_before_runtime_persistence(self):
        oversized = "x" * (MAX_MODEL_CONTENT_BYTES + 1)
        boundary = CompletionBoundary(
            {
                "id": "provider-response-oversized",
                "model": DEFAULT_MODEL_ID,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": oversized},
                    }
                ],
            }
        )
        client = self._factory(
            request_profile=SOURCE_REQUEST_PROFILE,
            boundary=boundary,
        ).create()

        with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
            self._extract(
                client,
                prompt=self._prompt(SOURCE_REQUEST_PROFILE),
                package=self._package(SOURCE_REQUEST_PROFILE),
            )

        self.assertEqual(
            rejected.exception.code,
            "gate2_model_response_budget_exceeded",
        )
        self.assertEqual(rejected.exception.failure_class, "response_budget")
        budget = rejected.exception.raw_output["response_budget"]
        self.assertEqual(budget["reason"], "bytes")
        self.assertEqual(budget["allowed"], MAX_MODEL_CONTENT_BYTES)
        self.assertEqual(budget["observed"], len(oversized))
        self.assertEqual(len(budget["content_sha256"]), 64)
        self.assertNotIn(oversized[:1024], str(rejected.exception.raw_output))
        self.assertEqual(len(boundary.calls), 1)

    def test_oversized_provider_error_fails_with_bounded_diagnostic(self):
        oversized = "provider-private-error-" + (
            "x" * (MAX_MODEL_CONTENT_BYTES + 1)
        )
        boundary = CompletionBoundary(
            {
                "id": "provider-response-oversized-error",
                "model": DEFAULT_MODEL_ID,
                "error": {"message": oversized},
            }
        )
        client = self._factory(
            request_profile=SOURCE_REQUEST_PROFILE,
            boundary=boundary,
        ).create()

        with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
            self._extract(
                client,
                prompt=self._prompt(SOURCE_REQUEST_PROFILE),
                package=self._package(SOURCE_REQUEST_PROFILE),
            )

        self.assertEqual(
            rejected.exception.code,
            "gate2_model_response_budget_exceeded",
        )
        self.assertEqual(rejected.exception.failure_class, "response_budget")
        budget = rejected.exception.raw_output["response_budget"]
        self.assertEqual(budget["reason"], "bytes")
        self.assertGreater(budget["observed"], MAX_MODEL_CONTENT_BYTES)
        self.assertEqual(budget["allowed"], MAX_MODEL_CONTENT_BYTES)
        self.assertEqual(len(budget["content_sha256"]), 64)
        self.assertNotIn(oversized[:1024], str(rejected.exception.raw_output))
        self.assertEqual(
            rejected.exception.execution_metadata.requested_model_id,
            DEFAULT_MODEL_ID,
        )
        self.assertIsNone(
            rejected.exception.execution_metadata.provider_response_id
        )
        self.assertIsNone(rejected.exception.execution_metadata.resolved_model_id)
        self.assertEqual(len(boundary.calls), 1)

    def test_completion_signature_selection_calls_external_boundary_exactly_once(self):
        signatures: list[tuple[str, Any, list[dict[str, Any]]]] = []

        full_calls: list[dict[str, Any]] = []

        def full(
            *, request, form_data, user, bypass_filter, bypass_system_prompt
        ):
            full_calls.append(
                {
                    "request": request,
                    "form_data": form_data,
                    "user": user,
                    "bypass_filter": bypass_filter,
                    "bypass_system_prompt": bypass_system_prompt,
                }
            )
            return {"content": "full"}

        signatures.append(("full", full, full_calls))

        keyword_calls: list[dict[str, Any]] = []

        def keyword_only(*, request, form_data, user):
            keyword_calls.append(
                {"request": request, "form_data": form_data, "user": user}
            )
            return {"content": "keyword_only"}

        signatures.append(("keyword_only", keyword_only, keyword_calls))

        positional_calls: list[dict[str, Any]] = []

        def positional_only(request, form_data, user, /):
            positional_calls.append(
                {"request": request, "form_data": form_data, "user": user}
            )
            return {"content": "positional_only"}

        signatures.append(("positional_only", positional_only, positional_calls))

        for expected, completion_fn, calls in signatures:
            with self.subTest(signature=expected):
                resolver_calls: list[str] = []

                def resolver(user_id: str):
                    resolver_calls.append(user_id)
                    return completion_fn, SimpleNamespace(id=user_id)

                client = self._factory(
                    request_profile=SOURCE_REQUEST_PROFILE,
                    completion_resolver=resolver,
                ).create()
                result = self._extract(
                    client,
                    prompt=self._prompt(SOURCE_REQUEST_PROFILE),
                    package=self._package(SOURCE_REQUEST_PROFILE),
                )
                self.assertEqual(result.content, expected)
                self.assertEqual(resolver_calls, ["model-client-user"])
                self.assertEqual(len(calls), 1)

        provider_calls: list[dict[str, Any]] = []

        def provider_internal_type_error(
            *, request, form_data, user, bypass_filter, bypass_system_prompt
        ):
            provider_calls.append({"form_data": form_data})
            raise TypeError("provider failed after invocation")

        def resolver(user_id: str):
            return provider_internal_type_error, SimpleNamespace(id=user_id)

        client = self._factory(
            request_profile=SOURCE_REQUEST_PROFILE,
            completion_resolver=resolver,
        ).create()
        with self.assertRaises(Gate2SourceFactRuntimeError) as failed:
            self._extract(
                client,
                prompt=self._prompt(SOURCE_REQUEST_PROFILE),
                package=self._package(SOURCE_REQUEST_PROFILE),
            )
        self.assertEqual(failed.exception.code, "gate2_model_call_failed")
        self.assertEqual(failed.exception.message, "TypeError")
        self.assertEqual(failed.exception.failure_class, "TypeError")
        self.assertEqual(
            failed.exception.raw_output,
            {
                "error": {
                    "type": "TypeError",
                    "message_length": len("provider failed after invocation"),
                    "message_sha256": hashlib.sha256(
                        b"provider failed after invocation"
                    ).hexdigest(),
                }
            },
        )
        self.assertEqual(len(provider_calls), 1)

        unavailable_calls: list[dict[str, Any]] = []

        def unavailable_provider(*, request, form_data, user):
            unavailable_calls.append({"form_data": form_data})
            raise Exception("model not found")

        client = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            completion_resolver=lambda user_id: (
                unavailable_provider,
                SimpleNamespace(id=user_id),
            ),
        ).create()
        with self.assertRaises(Gate2SourceFactRuntimeError) as unavailable:
            self._extract(
                client,
                prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
                package=self._package(DOMAIN_REQUEST_PROFILE),
            )
        self.assertEqual(unavailable.exception.code, "gate2_model_call_failed")
        self.assertEqual(unavailable.exception.failure_class, "Exception")
        self.assertEqual(len(unavailable_calls), 1)

    def test_async_dependencies_user_and_completion_are_supported_once(self):
        calls: list[dict[str, Any]] = []

        async def user_model(user_id: str):
            return SimpleNamespace(id=user_id)

        async def completion(
            *, request, form_data, user, bypass_filter, bypass_system_prompt
        ):
            calls.append({"form_data": form_data, "user": user})
            return {"content": {"async": True}}

        async def resolver(user_id: str):
            return completion, user_model(user_id)

        client = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            completion_resolver=resolver,
        ).create()
        result = self._extract(
            client,
            prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
            package=self._package(DOMAIN_REQUEST_PROFILE),
        )
        self.assertEqual(result.content, {"async": True})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["user"].id, "model-client-user")

    def test_completion_response_shapes_have_terminal_observable_results(self):
        body_response = SimpleNamespace(
            body=json.dumps({"content": {"shape": "body"}}).encode("utf-8")
        )
        cases = (
            (
                "choices_message_string",
                {"choices": [{"message": {"content": "message"}}]},
                "message",
            ),
            (
                "choices_message_object",
                {"choices": [{"message": {"content": {"shape": "message"}}}]},
                {"shape": "message"},
            ),
            ("choices_text", {"choices": [{"text": "text"}]}, "text"),
            ("top_content", {"content": {"shape": "content"}}, {"shape": "content"}),
            ("top_response", {"response": {"shape": "response"}}, {"shape": "response"}),
            ("body", body_response, {"shape": "body"}),
            ("plain_string", "plain", "plain"),
        )
        for name, response, expected in cases:
            with self.subTest(name=name):
                boundary = CompletionBoundary(response)
                client = self._factory(
                    request_profile=SOURCE_REQUEST_PROFILE,
                    boundary=boundary,
                ).create()
                result = self._extract(
                    client,
                    prompt=self._prompt(SOURCE_REQUEST_PROFILE),
                    package=self._package(SOURCE_REQUEST_PROFILE),
                )
                self.assertEqual(result.content, expected)
                self.assertEqual(len(boundary.calls), 1)

        invalid_cases = (
            ("missing_content", {}, "gate2_model_invalid_response"),
            (
                "invalid_body",
                SimpleNamespace(body=b"not-json"),
                "gate2_model_invalid_response",
            ),
            ("unsupported_shape", object(), "gate2_model_invalid_response"),
            (
                "json_list_body",
                SimpleNamespace(body=b'[{"type":"schema"}]'),
                "gate2_model_invalid_response",
            ),
        )
        for name, response, expected_code in invalid_cases:
            with self.subTest(name=name):
                boundary = CompletionBoundary(response)
                client = self._factory(
                    request_profile=SOURCE_REQUEST_PROFILE,
                    boundary=boundary,
                ).create()
                with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
                    self._extract(
                        client,
                        prompt=self._prompt(SOURCE_REQUEST_PROFILE),
                        package=self._package(SOURCE_REQUEST_PROFILE),
                    )
                self.assertEqual(rejected.exception.code, expected_code)
                if name == "invalid_body":
                    self.assertEqual(
                        rejected.exception.raw_output,
                        {
                            "response_type": "SimpleNamespace",
                            "body_length": len(b"not-json"),
                            "body_sha256": hashlib.sha256(b"not-json").hexdigest(),
                        },
                    )
                elif name == "unsupported_shape":
                    self.assertEqual(
                        rejected.exception.raw_output,
                        {"response_type": "object"},
                    )
                elif name == "json_list_body":
                    self.assertEqual(
                        rejected.exception.raw_output,
                        [{"type": "schema"}],
                    )
                self.assertEqual(len(boundary.calls), 1)

        list_error = SimpleNamespace(
            body=json.dumps(
                [{"error": {"code": 400, "message": "schema too complex"}}]
            ).encode("utf-8")
        )
        boundary = CompletionBoundary(list_error)
        client = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            boundary=boundary,
        ).create()
        with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
            self._extract(
                client,
                prompt=self._prompt(DOMAIN_REQUEST_PROFILE),
                package=self._package(DOMAIN_REQUEST_PROFILE),
            )
        self.assertEqual(
            rejected.exception.code,
            "gate2_model_schema_response_format_rejected",
        )
        self.assertEqual(
            rejected.exception.raw_output,
            {"error": {"code": 400, "message": "schema too complex"}},
        )

    def test_provider_error_taxonomy_is_typed_private_and_never_retried(self):
        common_cases = (
            ("oneOf is unsupported", "gate2_model_schema_oneof_unsupported"),
            ("response_format json_schema rejected", "gate2_model_schema_response_format_rejected"),
            ("too many tokens", "gate2_model_context_budget_exceeded"),
            (
                "insufficient_quota exceeded your current quota",
                "gate2_model_provider_quota_exceeded",
            ),
            ("rate limit exceeded", "gate2_model_provider_rate_limited"),
            ("model not found", "gate2_model_unavailable"),
            ("authentication api key failed", "gate2_model_provider_auth_failed"),
            (
                "provider service temporarily unavailable",
                "gate2_model_provider_unavailable",
            ),
            ("upstream provider failed", "gate2_model_provider_error"),
        )
        for request_profile in GATE2_REQUEST_PROFILES:
            for signal, expected_code in common_cases:
                with self.subTest(request_profile=request_profile, signal=signal):
                    payload = {"error": {"message": signal}}
                    boundary = CompletionBoundary(payload)
                    client = self._factory(
                        request_profile=request_profile,
                        boundary=boundary,
                    ).create()
                    with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
                        self._extract(
                            client,
                            prompt=self._prompt(request_profile),
                            package=self._package(request_profile),
                        )
                    self.assertEqual(rejected.exception.code, expected_code)
                    self.assertEqual(rejected.exception.raw_output, payload)
                    self.assertNotIn(signal, rejected.exception.message)
                    self.assertEqual(len(boundary.calls), 1)

        structured_status_cases = (
            (
                {"error": {"status": 429, "message": "request rejected"}},
                "gate2_model_provider_rate_limited",
            ),
            (
                {"error": {"code": "503", "message": "request rejected"}},
                "gate2_model_provider_unavailable",
            ),
            (
                {
                    "error": {
                        "status": 429,
                        "code": "insufficient_quota",
                        "message": "billing hard limit",
                    }
                },
                "gate2_model_provider_quota_exceeded",
            ),
        )
        for request_profile in GATE2_REQUEST_PROFILES:
            for payload, expected_code in structured_status_cases:
                with self.subTest(
                    request_profile=request_profile,
                    structured_status=payload,
                ):
                    boundary = CompletionBoundary(payload)
                    client = self._factory(
                        request_profile=request_profile,
                        boundary=boundary,
                    ).create()
                    with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
                        self._extract(
                            client,
                            prompt=self._prompt(request_profile),
                            package=self._package(request_profile),
                        )
                    self.assertEqual(rejected.exception.code, expected_code)
                    self.assertEqual(rejected.exception.raw_output, payload)
                    self.assertEqual(len(boundary.calls), 1)

        source_only_cases = (
            (
                "required must list all properties",
                "gate2_model_schema_required_properties_invalid",
            ),
            (
                "additionalProperties must be false",
                "gate2_model_schema_additional_properties_invalid",
            ),
            (
                "must have a 'type' key",
                "gate2_model_schema_type_key_missing",
            ),
            ("invalid nullable", "gate2_model_schema_nullable_type_invalid"),
            ("maximum context exceeded", "gate2_model_context_budget_exceeded"),
        )
        for signal, expected_code in source_only_cases:
            with self.subTest(request_profile=SOURCE_REQUEST_PROFILE, signal=signal):
                payload = {"detail": signal}
                boundary = CompletionBoundary(payload)
                client = self._factory(
                    request_profile=SOURCE_REQUEST_PROFILE,
                    boundary=boundary,
                ).create()
                with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
                    self._extract(
                        client,
                        prompt=self._prompt(SOURCE_REQUEST_PROFILE),
                        package=self._package(SOURCE_REQUEST_PROFILE),
                    )
                self.assertEqual(rejected.exception.code, expected_code)
                self.assertEqual(rejected.exception.raw_output, payload)
                self.assertEqual(len(boundary.calls), 1)

    def test_invalid_context_prompt_schema_and_factory_config_stop_before_completion(self):
        invalid_formats = (
            None,
            {},
            {"type": "json_object"},
            {"type": "json_schema", "json_schema": {"strict": False, "schema": {}}},
            {"type": "json_schema", "json_schema": {"strict": True}},
            {"type": "json_schema", "json_schema": {"strict": True, "schema": []}},
        )
        for invalid_format in invalid_formats:
            with self.subTest(invalid_format=invalid_format):
                boundary = CompletionBoundary({"content": {"unexpected": True}})
                client = self._factory(
                    request_profile=SOURCE_REQUEST_PROFILE,
                    boundary=boundary,
                ).create()
                with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
                    self._extract(
                        client,
                        prompt=self._prompt(SOURCE_REQUEST_PROFILE),
                        package=self._package(SOURCE_REQUEST_PROFILE),
                        response_format=invalid_format,
                    )
                self.assertEqual(
                    rejected.exception.code,
                    "gate2_strict_structured_output_required",
                )
                self.assertEqual(boundary.resolved_user_ids, [])
                self.assertEqual(boundary.calls, [])

        for request_profile in GATE2_REQUEST_PROFILES:
            for user, request in (({}, self.request), (self.user, None)):
                with self.subTest(
                    request_profile=request_profile,
                    user=user,
                    request_present=request is not None,
                ):
                    boundary = CompletionBoundary({"content": {"unexpected": True}})
                    client = Gate2StructuredModelClientFactory(
                        config=Gate2StructuredModelClientConfig(
                            request_profile=request_profile
                        ),
                        user=user,
                        request=request,
                        completion_resolver=boundary.resolve,
                    ).create()
                    with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
                        self._extract(
                            client,
                            prompt=self._prompt(request_profile),
                            package=self._package(request_profile),
                        )
                    self.assertEqual(rejected.exception.code, "gate2_model_unavailable")
                    self.assertEqual(boundary.resolved_user_ids, [])
                    self.assertEqual(boundary.calls, [])

        for request_profile, expected_code in (
            (SOURCE_REQUEST_PROFILE, "gate2_prompt_contract_mismatch"),
            (DOMAIN_REQUEST_PROFILE, "gate2_domain_prompt_contract_mismatch"),
        ):
            with self.subTest(request_profile=request_profile, invalid_prompt=True):
                boundary = CompletionBoundary({"content": {"unexpected": True}})
                client = self._factory(
                    request_profile=request_profile,
                    boundary=boundary,
                ).create()
                with self.assertRaises(Gate2PromptError) as rejected:
                    self._extract(
                        client,
                        prompt=self._prompt(request_profile, marker=False),
                        package=self._package(request_profile),
                    )
                self.assertEqual(rejected.exception.code, expected_code)
                self.assertEqual(boundary.resolved_user_ids, [])
                self.assertEqual(boundary.calls, [])

        invalid_factory_cases = (
            (
                Gate2StructuredModelClientConfig(
                    request_profile=SOURCE_REQUEST_PROFILE,
                    transport="provider_sdk",
                ),
                "gate2_model_transport_unsupported",
            ),
            (
                Gate2StructuredModelClientConfig(request_profile="unknown_v0"),
                "gate2_model_request_profile_unknown",
            ),
            (
                Gate2StructuredModelClientConfig(
                    request_profile=SOURCE_REQUEST_PROFILE,
                    provider_profile_id="unknown-provider",
                ),
                "gate2_provider_profile_unknown",
            ),
        )
        for config, expected_code in invalid_factory_cases:
            with self.subTest(config=config):
                boundary = CompletionBoundary({"content": {"unexpected": True}})
                with self.assertRaises(Gate2SourceFactRuntimeError) as rejected:
                    Gate2StructuredModelClientFactory(
                        config=config,
                        user=self.user,
                        request=self.request,
                        completion_resolver=boundary.resolve,
                    ).create()
                self.assertEqual(rejected.exception.code, expected_code)
                self.assertEqual(boundary.resolved_user_ids, [])
                self.assertEqual(boundary.calls, [])

    def test_factory_antidrift_contract_is_explicit(self):
        self.assertIn("Gate2StructuredModelClientFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not call OpenWebUI completion functions", FORBIDDEN)
        self.assertIn("provider SDKs directly", FORBIDDEN)
        self.assertIn("Gate2ProviderAdapterFactory.create", PROVIDER_FACTORY_REQUIRED)
        self.assertIn("business runtimes must not build vendor payloads", PROVIDER_FORBIDDEN)
        self.assertIsInstance(
            self._factory(
                request_profile=SOURCE_REQUEST_PROFILE,
                boundary=CompletionBoundary({"content": {"ok": True}}),
            ).create().provider_adapter,
            Gate2OpenAIResponseFormatAdapter,
        )
        anthropic = self._factory(
            request_profile=DOMAIN_REQUEST_PROFILE,
            provider_profile_id="anthropic_claude",
            capability_probe=True,
            boundary=CompletionBoundary({"content": {"ok": True}}),
        ).create()
        self.assertIsInstance(
            anthropic.provider_adapter,
            Gate2AnthropicNativeMessagesAdapter,
        )

    def test_model_factory_modules_are_closed_world_safe(self):
        allowed_top_level_modules = {
            "__future__",
            "asyncio",
            "collections",
            "copy",
            "dataclasses",
            "hashlib",
            "inspect",
            "json",
            "time",
            "typing",
            "urllib",
        }
        for path in MODEL_MODULE_PATHS:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source)
                for node in tree.body:
                    if isinstance(node, ast.Import):
                        self.assertTrue(
                            all(
                                alias.name.split(".", 1)[0]
                                in allowed_top_level_modules
                                for alias in node.names
                            )
                        )
                    elif isinstance(node, ast.ImportFrom):
                        if node.level == 0:
                            self.assertIn(
                                str(node.module or "").split(".", 1)[0],
                                allowed_top_level_modules,
                            )
                self.assertNotIn("sys.path.insert", source)
                self.assertNotIn("Path(__file__)", source)
                self.assertNotIn("process.cwd", source)
                self.assertNotIn("import requests", source)
                self.assertNotIn("from requests", source)
                self.assertNotIn("import httpx", source)
                self.assertNotIn("from httpx", source)

    def setUp(self) -> None:
        self.user = {"id": "model-client-user", "role": "admin"}
        self.request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    config=SimpleNamespace(
                        OPENAI_API_BASE_URLS=["https://api.anthropic.com/v1"],
                        OPENAI_API_KEYS=["unit-anthropic-key"],
                        OPENAI_API_CONFIGS={"0": {"enable": True}},
                    )
                )
            )
        )

    def _factory(
        self,
        *,
        request_profile: str,
        provider_profile_id: str = "openai_gpt",
        boundary: CompletionBoundary | None = None,
        completion_resolver=None,
        capability_probe: bool = False,
        native_transport_resolver=None,
        native_transport_config: Gate2NativeProviderTransportConfig | None = None,
        provider_connection_resolver=None,
    ) -> Gate2StructuredModelClientFactory:
        resolver = completion_resolver or (boundary.resolve if boundary else None)
        return Gate2StructuredModelClientFactory(
            config=Gate2StructuredModelClientConfig(
                request_profile=request_profile,
                provider_profile_id=provider_profile_id,
                capability_probe=capability_probe,
            ),
            user=self.user,
            request=self.request,
            completion_resolver=resolver,
            native_transport_resolver=native_transport_resolver,
            native_transport_config=native_transport_config,
            provider_connection_resolver=provider_connection_resolver,
        )

    def _extract(
        self,
        client,
        *,
        prompt: Gate2ManagedPrompt,
        package: dict[str, Any],
        response_format: Any = _DEFAULT_RESPONSE_FORMAT,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> Gate2StructuredModelResult:
        actual_response_format = (
            self._response_format()
            if response_format is _DEFAULT_RESPONSE_FORMAT
            else response_format
        )
        return asyncio.run(
            client.extract(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=actual_response_format,
            )
        )

    def _prompt(
        self, request_profile: str, *, marker: bool = True
    ) -> Gate2ManagedPrompt:
        marker_text = "{{source_fact_package_json}}" if marker else "missing marker"
        content = f"Managed {request_profile} prompt before {marker_text} after."
        return Gate2ManagedPrompt(
            prompt_ref=f"prompt_{request_profile}_test",
            command=f"broker_gate2_{request_profile}_test",
            version="test-v1",
            content=content,
            hash=gate2_prompt_hash(content),
            source="test_boundary",
            template_id=f"broker_reports.{request_profile}.test",
            template_kind=f"broker_reports_{request_profile}",
            prompt_contract_id="broker_reports_source_fact_prompt_v0",
            input_schema_version="broker_reports_source_fact_package_v0",
            output_schema_id="broker_reports.source_facts.schema.v0",
            output_schema_version="broker_reports_source_facts_v0",
            tags=("broker-reports-gate2", "structured-output"),
            safe_metadata={"request_profile": request_profile},
        )

    def _package(
        self,
        request_profile: str,
        *,
        candidate_binding: bool = False,
    ) -> dict[str, Any]:
        if request_profile == SOURCE_REQUEST_PROFILE:
            return {
                "package_artifact_ref": "pkg_source",
                "output_schema": {"output_schema_hash": "schema-hash-source"},
                "private_source_marker": "private_source_marker",
            }
        package = {
            "package_artifact_ref": "pkg_domain",
            "extractor_domain": "income",
            "allowed_fact_types": ["income"],
            "output_schema": {"output_schema_hash": "schema-hash-domain"},
        }
        if candidate_binding:
            package["candidate_binding_mode"] = "candidate_ids_and_semantic_roles_v0"
        return package

    @staticmethod
    def _response_format() -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "broker_reports_source_facts_v0",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        }


if __name__ == "__main__":
    unittest.main()
