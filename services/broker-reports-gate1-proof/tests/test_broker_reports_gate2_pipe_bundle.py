from __future__ import annotations

import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
BUNDLE = ROOT / "openwebui_actions" / "broker_reports_gate2_source_fact_pipe_bundled.py"
DOMAIN_BUNDLE = ROOT / "openwebui_actions" / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
SOURCE_PIPE = ROOT / "openwebui_actions" / "broker_reports_gate2_source_fact_pipe.py"
DOMAIN_PIPE = ROOT / "openwebui_actions" / "broker_reports_gate2_domain_source_fact_pipe.py"

from build_openwebui_pipe_bundle import assert_gate2_bundle_contract
from live_case_group_gate2_table_typed_vertical_proof import (
    FUNCTION_ID as TABLE_PROOF_FUNCTION_ID,
    _run_chat as run_table_proof_chat,
    _safe_target,
)
import live_gate2_domain_synthetic_smoke as domain_smoke
from live_gate2_domain_synthetic_smoke import (
    FUNCTION_ID as DOMAIN_SMOKE_FUNCTION_ID,
    _run_domain_chat as run_domain_smoke_chat,
)
from live_gate2_synthetic_extraction_smoke import _synthetic_documents
from live_update_gate2_domain_function_and_prompts import (
    PROMPT_VERSION as DOMAIN_PROMPT_VERSION,
    _assert_prompt_readbacks,
)
from live_update_gate2_function_and_prompt import (
    PROMPT_VERSION as SOURCE_PROMPT_VERSION,
    _assert_prompt_readback,
)


def load_bundle_module():
    for name in list(sys.modules):
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
            del sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        "broker_reports_gate2_source_fact_pipe_bundled_under_test",
        BUNDLE,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not create Gate 2 bundle import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_domain_bundle_module():
    for name in list(sys.modules):
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
            del sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        "broker_reports_gate2_domain_source_fact_pipe_bundled_under_test",
        DOMAIN_BUNDLE,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not create Gate 2 domain bundle import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrokerReportsGate2PipeBundleTest(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
                del sys.modules[name]

    def test_gate2_bundle_is_closed_world_and_missing_ref_terminates_safely(self):
        source = BUNDLE.read_text(encoding="utf-8")
        self.assertIn("_BUNDLED_MODULES", source)
        self.assertIn("gate2_source_fact_contracts", source)
        self.assertIn("gate2_model_contracts", source)
        self.assertIn("gate2_model_requests", source)
        self.assertIn("gate2_provider_adapters", source)
        self.assertIn("gate2_model_clients", source)
        self.assertIn("gate2_source_fact_validation", source)
        self.assertIn("gate2_source_fact_runtime", source)
        self.assertNotIn("sys.path.insert", source)
        self.assertNotIn("services/broker-reports-gate1-proof/broker_reports_gate1", source)

        module = load_bundle_module()
        bundled_package = sys.modules["broker_reports_gate1"]
        self.assertTrue(hasattr(bundled_package, "Gate2SourceFactRuntimeFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2ManagedPromptResolverFactory"))
        self.assertTrue(
            hasattr(bundled_package, "Gate2StructuredModelClientFactory")
        )
        self.assertTrue(
            hasattr(bundled_package, "Gate2ProviderAdapterFactory")
        )
        self.assertTrue(
            hasattr(bundled_package, "Gate2ProviderExecutionMetadata")
        )
        self.assertEqual(len(bundled_package.GATE2_PROVIDER_PROFILES), 6)
        pipe = module.Pipe()
        self.assertEqual(pipe.valves.provider_profile_id, "openai_gpt")
        events = []

        async def emitter(event):
            events.append(event)

        content = asyncio.run(
            pipe.pipe(
                {"messages": [{"role": "user", "content": "Извлеки исходные факты"}]},
                __user__={"id": "gate2-bundle-user", "role": "admin"},
                __metadata__={},
                __event_emitter__=emitter,
            )
        )

        self.assertEqual(
            content,
            "Gate 2 не запущен: нужен авторизованный пользователь и безопасный DCP ref.",
        )
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["data"]["done"])

    def test_gate2_domain_bundle_is_closed_world_and_is_the_narrow_customer_path(self):
        source = DOMAIN_BUNDLE.read_text(encoding="utf-8")
        for module_name in (
            "gate2_model_contracts",
            "gate2_model_requests",
            "gate2_provider_adapters",
            "gate2_model_clients",
            "gate2_candidate_binding",
            "gate2_candidate_binding_runtime",
            "gate2_domain_routing",
            "gate2_domain_packages",
            "gate2_source_unit_segmentation",
            "gate2_domain_contracts",
            "gate2_source_fact_stitching",
            "gate2_domain_runtime",
        ):
            self.assertIn(module_name, source)
        self.assertIn("prefer_table_projections", source)
        self.assertNotIn("sys.path.insert", source)
        module = load_domain_bundle_module()
        bundled_package = sys.modules["broker_reports_gate1"]
        self.assertTrue(
            hasattr(bundled_package, "Gate2DomainSourceFactRuntimeFactory")
        )
        self.assertTrue(
            hasattr(bundled_package, "Gate2SourceFactStitcherFactory")
        )
        pipe = module.Pipe()
        self.assertEqual(pipe.valves.default_document_batch_limit, 1)
        self.assertEqual(pipe.valves.default_source_unit_limit, 1)
        self.assertTrue(pipe.valves.segmentation_enabled)
        self.assertFalse(pipe.valves.prefer_table_projections)
        self.assertFalse(pipe.valves.candidate_binding_enabled)
        self.assertTrue(
            hasattr(bundled_package, "Gate2CandidateBindingKernelFactory")
        )
        self.assertTrue(
            hasattr(bundled_package, "Gate2CandidateBindingRuntimeFactory")
        )
        self.assertTrue(
            hasattr(bundled_package, "Gate2StructuredModelClientFactory")
        )
        self.assertTrue(
            hasattr(bundled_package, "Gate2ProviderAdapterFactory")
        )
        self.assertEqual(pipe.valves.provider_profile_id, "openai_gpt")
        self.assertEqual(pipe.valves.default_source_segment_limit, 1)
        content = asyncio.run(
            pipe.pipe(
                {"messages": [{"role": "user", "content": "Извлеки доменные факты"}]},
                __user__={"id": "gate2-domain-bundle-user", "role": "admin"},
                __metadata__={},
            )
        )
        self.assertEqual(
            content,
            "Gate 2 не запущен: нужен авторизованный пользователь и безопасный DCP ref.",
        )

    def test_gate2_pipes_have_one_factory_backed_provider_route(self):
        for pipe_path in (SOURCE_PIPE, DOMAIN_PIPE):
            source = pipe_path.read_text(encoding="utf-8")
            self.assertIn("Gate2StructuredModelClientFactory(", source)
            self.assertIn(".create()", source)
            self.assertNotIn("generate_chat_completion", source)
            self.assertNotIn("_completion_dict_content", source)
            self.assertNotIn("_provider_error_code", source)
            self.assertNotIn("class OpenWebUIGate2", source)

        module = load_domain_bundle_module()
        order = module._BUNDLED_MODULE_ORDER
        self.assertLess(
            order.index("gate2_source_fact_contracts"),
            order.index("gate2_model_contracts"),
        )
        self.assertLess(
            order.index("gate2_model_contracts"),
            order.index("gate2_model_requests"),
        )
        self.assertLess(
            order.index("gate2_model_requests"),
            order.index("gate2_provider_adapters"),
        )
        self.assertLess(
            order.index("gate2_provider_adapters"),
            order.index("gate2_model_clients"),
        )
        self.assertLess(
            order.index("gate2_model_clients"),
            order.index("gate2_source_fact_runtime"),
        )
        clients_module = sys.modules["broker_reports_gate1.gate2_model_clients"]
        self.assertIn(
            "Gate2StructuredModelClientFactory.create",
            clients_module.FACTORY_REQUIRED,
        )
        self.assertIn("must not call OpenWebUI", clients_module.FORBIDDEN)
        adapters_module = sys.modules[
            "broker_reports_gate1.gate2_provider_adapters"
        ]
        self.assertIn(
            "Gate2ProviderAdapterFactory.create",
            adapters_module.FACTORY_REQUIRED,
        )
        self.assertIn("business runtimes must not build vendor payloads", adapters_module.FORBIDDEN)

    def test_update_acceptance_fails_closed_on_bundle_or_prompt_readback_drift(self):
        self.assertEqual(SOURCE_PROMPT_VERSION, "2026-07-11-provider-factory-v0")
        self.assertEqual(
            DOMAIN_PROMPT_VERSION,
            "2026-07-11-candidate-binding-provider-factory-v0",
        )
        source_bundle = BUNDLE.read_text(encoding="utf-8")
        domain_bundle = DOMAIN_BUNDLE.read_text(encoding="utf-8")
        assert_gate2_bundle_contract(
            source_bundle,
            runtime_factory="Gate2SourceFactRuntimeFactory",
        )
        assert_gate2_bundle_contract(
            domain_bundle,
            runtime_factory="Gate2DomainSourceFactRuntimeFactory",
        )

        missing_anchor = source_bundle.replace(
            "Gate2StructuredModelClientFactory.create is the only production "
            "Gate 2 model client entrypoint",
            "missing model-client factory anchor",
            1,
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "gate2_bundle_contract_missing:model_client_factory_anchor",
        ):
            assert_gate2_bundle_contract(
                missing_anchor,
                runtime_factory="Gate2SourceFactRuntimeFactory",
            )

        direct_bypass = domain_bundle + "\ngenerate_chat_completion()\n"
        with self.assertRaisesRegex(
            RuntimeError,
            "gate2_bundle_contract_forbidden:direct_openwebui_completion",
        ):
            assert_gate2_bundle_contract(
                direct_bypass,
                runtime_factory="Gate2DomainSourceFactRuntimeFactory",
            )

        direct_anthropic_bypass = domain_bundle + "\napi.anthropic.com/v1/messages\n"
        with self.assertRaisesRegex(
            RuntimeError,
            "gate2_bundle_contract_forbidden:direct_anthropic_endpoint",
        ):
            assert_gate2_bundle_contract(
                direct_anthropic_bypass,
                runtime_factory="Gate2DomainSourceFactRuntimeFactory",
            )

        prompt_hash = "a" * 64
        content_hash = "e" * 64
        schema_hash = "b" * 64
        source_readback = {
            "prompt_hash": prompt_hash,
            "prompt_hash_matches_expected": True,
            "content_sha256": content_hash,
            "output_schema_hash": schema_hash,
            "structured_output_required": True,
        }
        _assert_prompt_readback(
            source_readback,
            expected_prompt_hash=prompt_hash,
            expected_content_hash=content_hash,
            expected_schema_hash=schema_hash,
        )
        self_asserted = dict(source_readback)
        self_asserted["prompt_hash_matches_expected"] = False
        with self.assertRaisesRegex(
            RuntimeError,
            "gate2_managed_prompt_readback_mismatch",
        ):
            _assert_prompt_readback(
                self_asserted,
                expected_prompt_hash=prompt_hash,
                expected_content_hash=content_hash,
                expected_schema_hash=schema_hash,
            )
        content_drift = dict(source_readback)
        content_drift["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeError,
            "gate2_managed_prompt_content_readback_mismatch",
        ):
            _assert_prompt_readback(
                content_drift,
                expected_prompt_hash=prompt_hash,
                expected_content_hash=content_hash,
                expected_schema_hash=schema_hash,
            )

        expected_hashes = {"prompt_cash": prompt_hash, "prompt_income": "c" * 64}
        expected_content_hashes = {
            "prompt_cash": content_hash,
            "prompt_income": "f" * 64,
        }
        domain_readbacks = [
            {
                "prompt_ref": prompt_ref,
                "prompt_hash": expected,
                "prompt_hash_matches_expected": True,
                "content_sha256": expected_content_hashes[prompt_ref],
                "output_schema_hash": schema_hash,
                "structured_output_required": True,
            }
            for prompt_ref, expected in expected_hashes.items()
        ]
        _assert_prompt_readbacks(
            domain_readbacks,
            expected_hashes=expected_hashes,
            expected_content_hashes=expected_content_hashes,
            expected_schema_hash=schema_hash,
        )
        domain_readbacks[1]["prompt_hash"] = "d" * 64
        with self.assertRaisesRegex(
            RuntimeError,
            "gate2_domain_prompt_hash_mismatch",
        ):
            _assert_prompt_readbacks(
                domain_readbacks,
                expected_hashes=expected_hashes,
                expected_content_hashes=expected_content_hashes,
                expected_schema_hash=schema_hash,
            )

    def test_candidate_binding_live_proofs_forward_profile_through_function_route(self):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"content": "safe terminal content"}

        class Session:
            def __init__(self):
                self.calls = []

            def post(self, url, *, json, timeout):
                self.calls.append({"url": url, "json": json, "timeout": timeout})
                return Response()

        table_session = Session()
        table_content = run_table_proof_chat(
            session=table_session,
            base_url="https://example.invalid",
            dcp_ref="dcp_safe_test",
            model_id="provider-model-test",
            target={
                "document_batch_start": 0,
                "source_unit_start": 0,
                "source_segment_start": 0,
                "domain": "cash_movement",
            },
            candidate_binding_enabled=True,
            provider_profile_id="deepseek",
            max_repair_attempts=0,
            timeout=30,
        )
        self.assertEqual(table_content, "safe terminal content")
        self.assertEqual(len(table_session.calls), 1)
        table_body = table_session.calls[0]["json"]
        self.assertEqual(table_body["model"], TABLE_PROOF_FUNCTION_ID)
        self.assertEqual(
            table_body["broker_reports_gate2_domain"]["provider_profile_id"],
            "deepseek",
        )
        self.assertTrue(
            table_body["broker_reports_gate2_domain"]["candidate_binding_enabled"]
        )
        self.assertEqual(
            _safe_target(
                {
                    "domain": "cash_movement",
                    "headers": ["private source header"],
                    "selected_refs_total": 1,
                }
            ),
            {"domain": "cash_movement", "selected_refs_total": 1},
        )

        domain_session = Session()
        domain_content = run_domain_smoke_chat(
            session=domain_session,
            base_url="https://example.invalid",
            dcp_ref="dcp_safe_test",
            model_id="provider-model-test",
            candidate_binding_enabled=True,
            provider_capability_probe=True,
            provider_profile_id="anthropic_claude",
            domain="cash_movement",
            timeout=30,
        )
        self.assertEqual(domain_content, "safe terminal content")
        self.assertEqual(len(domain_session.calls), 1)
        domain_body = domain_session.calls[0]["json"]
        self.assertEqual(domain_body["model"], DOMAIN_SMOKE_FUNCTION_ID)
        self.assertEqual(
            domain_body["broker_reports_gate2_domain"]["provider_profile_id"],
            "anthropic_claude",
        )
        self.assertTrue(
            domain_body["broker_reports_gate2_domain"]["candidate_binding_enabled"]
        )
        self.assertTrue(
            domain_body["broker_reports_gate2_domain"]["provider_capability_probe"]
        )
        self.assertEqual(
            domain_body["broker_reports_gate2_domain"]["run_mode"],
            "provider_qualification",
        )
        self.assertEqual(
            domain_body["broker_reports_gate2_domain"]["domain_allowlist"],
            ["cash_movement"],
        )
        bounded_documents = _synthetic_documents("cash_movement")
        self.assertEqual(len(bounded_documents), 1)
        self.assertIn(b"cash_deposit", bounded_documents[0][1])

    def test_domain_smoke_purges_seeded_case_when_chat_raises(self):
        case_id = "synthetic_gate2_domain_20260712010101"
        events = []

        def seed_case(**_kwargs):
            events.append("seed")
            return {"domain_context_packet_ref": "dcp_safe_test"}

        def fail_chat(**_kwargs):
            events.append("chat")
            raise RuntimeError("synthetic_chat_failure")

        def purge_case(**_kwargs):
            events.append("purge")
            return {"performed": True, "purged_records_total": 1}

        argv = [
            "live_gate2_domain_synthetic_smoke.py",
            "--env-file",
            "ignored.env",
            "--base-url",
            "https://example.invalid",
            "--ssh-target",
            "synthetic-host",
            "--model-id",
            "provider-model-test",
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(domain_smoke, "_read_env", return_value={}),
            mock.patch.object(domain_smoke, "_signin", return_value="token"),
            mock.patch.object(
                domain_smoke,
                "_current_user",
                return_value={"id": "synthetic-user"},
            ),
            mock.patch.object(
                domain_smoke.time,
                "strftime",
                return_value="20260712010101",
            ),
            mock.patch.object(domain_smoke, "_runtime_snapshot", return_value={}),
            mock.patch.object(
                domain_smoke,
                "_seed_synthetic_gate1",
                side_effect=seed_case,
            ),
            mock.patch.object(
                domain_smoke,
                "_run_domain_chat",
                side_effect=fail_chat,
            ),
            mock.patch.object(
                domain_smoke,
                "_purge_case",
                side_effect=purge_case,
            ) as purge,
            mock.patch.object(domain_smoke, "_audit_case") as audit,
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic_chat_failure"):
                domain_smoke.main()

        self.assertEqual(events, ["seed", "chat", "purge"])
        purge.assert_called_once_with(
            ssh_target="synthetic-host",
            case_id=case_id,
        )
        audit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
