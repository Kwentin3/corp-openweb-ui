from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "scripts"
    / "live_verify_broker_reports_stage2_delivery.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "live_verify_broker_reports_stage2_delivery",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("stage2_delivery_verifier_import_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Stage2DeliveryVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_module()

    def test_expected_contracts_cover_all_functions_prompts_and_providers(self):
        prompts = self.module.expected_prompt_contracts()

        self.assertEqual(len(self.module.FUNCTION_CONTRACTS), 1)
        self.assertEqual(len(prompts), 12)
        source_prompt = prompts[
            "broker_reports_gate2_source_fact_prompt_v0"
        ]
        self.assertEqual(
            source_prompt["meta"]["provider_output_schema_version"],
            "broker_reports_source_fact_selection_v3",
        )
        self.assertEqual(
            self.module.content_sha256(source_prompt["content"]),
            source_prompt["content_sha256"],
        )
        self.assertEqual(
            sorted(
                profile.profile_id
                for profile in self.module.GATE2_PROVIDER_PROFILES
            ),
            [
                "alibaba_qwen",
                "anthropic_claude",
                "deepseek",
                "google_gemini",
                "openai_gpt",
                "zai_glm",
            ],
        )

    def test_prompt_parity_is_based_on_persisted_content_hash(self):
        expected = next(iter(self.module.expected_prompt_contracts().values()))
        live = {
            "command": expected["command"],
            "version": expected["version"],
            "is_active": 1,
            "content_sha256": expected["content_sha256"],
            "content_length": 10,
            "meta": dict(expected["meta"]),
        }

        passed = self.module.evaluate_prompt_contract(expected, live)
        live["content_sha256"] = self.module.content_sha256("different")
        failed = self.module.evaluate_prompt_contract(expected, live)

        self.assertTrue(passed["passed"])
        self.assertFalse(failed["passed"])
        self.assertFalse(failed["checks"]["content_sha256_match"])

    def test_repository_smoke_and_pipe_routes_use_factory_boundary(self):
        checks = self.module.repository_factory_boundary_checks()

        self.assertTrue(all(checks.values()), checks)
        provider_checks = (
            self.module._provider_adapter_boundary_invariants()
        )
        self.assertTrue(all(provider_checks.values()), provider_checks)
        self.assertTrue(
            checks["production_python_has_no_paddle_or_local_ocr_import"]
        )

    def test_provider_boundary_ast_invariants_reject_product_bypasses(self):
        paths = self.module._PROVIDER_BOUNDARY_SOURCE_PATHS
        source_pipe = paths["source_pipe"].read_text(encoding="utf-8")
        domain_runtime = paths["domain_runtime"].read_text(encoding="utf-8")
        provider_adapters = paths["provider_adapters"].read_text(
            encoding="utf-8"
        )
        checks = self.module._provider_adapter_boundary_invariants(
            {
                "source_pipe": (
                    source_pipe
                    + "\nimport requests\n"
                    + "from broker_reports_gate1."
                    + "gate2_financial_semantic_v6_qualification "
                    + "import qualify_financial_semantic_v6\n"
                    + "from broker_reports_gate1.gate2_provider_adapters "
                    + "import Gate2OpenAIResponseFormatAdapter\n"
                    + "requests.post('https://api.openai.com/v1')\n"
                ),
                "domain_runtime": (
                    domain_runtime
                    + "\nclass Gate2OpenWebUIProviderConnectionResolver:\n"
                    + "    pass\n"
                ),
                "provider_adapters": (
                    provider_adapters
                    + "\nLEAKED_CONFIG_KEY = 'OPENAI_API_KEYS'\n"
                ),
            }
        )

        self.assertFalse(
            checks["provider_connection_resolver_is_single_authority"]
        )
        self.assertFalse(
            checks["product_domains_have_no_direct_provider_transport"]
        )
        self.assertFalse(
            checks["provider_secret_resolution_is_resolver_scoped"]
        )
        self.assertFalse(
            checks["qualification_modules_are_not_product_consumers"]
        )
        self.assertFalse(
            checks["historical_adapters_are_not_product_reachable"]
        )

    def test_provider_boundary_rejects_generated_bundle_drift(self):
        paths = self.module._PROVIDER_BOUNDARY_SOURCE_PATHS
        provider_source = paths["provider_adapters"].read_text(
            encoding="utf-8"
        )
        model_client_source = paths["model_clients"].read_text(
            encoding="utf-8"
        )
        drifted_bundle = repr(
            {
                "gate2_provider_adapters": provider_source + "\n# drift\n",
                "gate2_model_clients": model_client_source,
            }
        )
        checks = self.module._provider_adapter_boundary_invariants(
            bundle_overrides={
                "gate1_bundle": f"_BUNDLED_MODULES = {drifted_bundle}\n"
            }
        )

        self.assertFalse(
            checks["generated_bundles_preserve_provider_closed_world"]
        )

    def test_function_active_state_is_strict(self):
        contract = self.module.FUNCTION_CONTRACTS[0]
        content = contract.bundle_path.read_text(encoding="utf-8")

        for inactive_value in (False, 0, None, "false"):
            with self.subTest(inactive_value=inactive_value):
                result = self.module.evaluate_function_contract(
                    contract,
                    {"content": content, "is_active": inactive_value},
                )
                self.assertFalse(result["passed"])
                self.assertFalse(result["checks"]["active"])

        for active_value in (True, 1):
            with self.subTest(active_value=active_value):
                result = self.module.evaluate_function_contract(
                    contract,
                    {"content": content, "is_active": active_value},
                )
                self.assertTrue(result["passed"])
                self.assertTrue(result["checks"]["active"])

    def test_gate1_operational_state_requires_supported_table_intake_config(self):
        table_intake_valves = {
            "pdf_table_intake_enabled": True,
            "pdf_table_intake_provider_profile": "google_gemini",
            "pdf_table_intake_model_id": "models/gemini-3.5-flash",
            "pdf_table_intake_dpi": 150,
            "pdf_table_intake_maximum_pages": 64,
            "pdf_table_intake_maximum_candidates_per_page": 32,
            "pdf_table_intake_horizontal_padding_fraction": 0.08,
            "pdf_table_intake_vertical_padding_fraction": 0.08,
        }
        passed = self.module.evaluate_gate1_operational_state(
            valves=table_intake_valves,
            fitz_version=self.module.REQUIRED_FITZ_VERSION,
        )
        retired_enabled = self.module.evaluate_gate1_operational_state(
            valves={**table_intake_valves, "pdf_dual_vlm_enabled": True},
            fitz_version=self.module.REQUIRED_FITZ_VERSION,
        )
        wrong_runtime = self.module.evaluate_gate1_operational_state(
            valves=table_intake_valves,
            fitz_version="0.0.0",
        )

        self.assertTrue(passed["retired_table_valves_absent"])
        self.assertTrue(passed["fitz_version_match"])
        self.assertTrue(passed["table_intake_enabled"])
        self.assertTrue(passed["table_intake_provider_configured"])
        self.assertTrue(passed["table_intake_model_configured"])
        self.assertTrue(passed["table_intake_dpi_configured"])
        self.assertTrue(passed["table_intake_padding_configured"])
        self.assertTrue(passed["table_intake_bounds_configured"])
        self.assertFalse(retired_enabled["retired_table_valves_absent"])
        self.assertFalse(wrong_runtime["fitz_version_match"])

    def test_gate1_contract_has_current_pipeline_antidrift_markers(self):
        markers = set(self.module.FUNCTION_CONTRACTS[0].required_markers)

        self.assertIn(
            "Gate5DeclarationPreparationRuntimeFactory",
            markers,
        )
        self.assertIn(
            "broker_reports_current_pipeline_result_v1",
            markers,
        )
        self.assertIn("PdfTableLocatorProviderFactory", markers)

    def test_live_ssh_reads_require_strict_host_key_verification(self):
        with mock.patch.object(self.module.subprocess, "run") as run:
            run.return_value = mock.Mock(
                stdout='{"version": "1.26.5"}',
            )

            version = self.module._read_live_fitz_version("stage@example.invalid")

        command = run.call_args.args[0]
        self.assertEqual("1.26.5", version)
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertNotIn("StrictHostKeyChecking=no", command)

        with mock.patch.object(self.module.subprocess, "run") as run:
            run.return_value = mock.Mock(stdout="[]")

            prompts = self.module._read_live_prompt_state(
                ssh_target="stage@example.invalid",
                prompt_ids=["prompt-v0"],
            )

        command = run.call_args.args[0]
        remote_code = run.call_args.kwargs["input"]
        self.assertEqual({}, prompts)
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertNotIn("StrictHostKeyChecking=no", command)
        self.assertIn('"provider_output_schema_version"', remote_code)


if __name__ == "__main__":
    unittest.main()
