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

        self.assertEqual(len(self.module.FUNCTION_CONTRACTS), 3)
        self.assertEqual(len(prompts), 12)
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

    def test_gate1_operational_state_requires_disabled_shadow_and_exact_fitz(self):
        passed = self.module.evaluate_gate1_operational_state(
            valves={},
            fitz_version=self.module.REQUIRED_FITZ_VERSION,
        )
        enabled = self.module.evaluate_gate1_operational_state(
            valves={"pdf_structural_repair_shadow_enabled": True},
            fitz_version=self.module.REQUIRED_FITZ_VERSION,
        )
        guided_enabled = self.module.evaluate_gate1_operational_state(
            valves={"pdf_vlm_guided_intake_shadow_enabled": True},
            fitz_version=self.module.REQUIRED_FITZ_VERSION,
        )
        page_allowlisted = self.module.evaluate_gate1_operational_state(
            valves={
                "pdf_vlm_guided_intake_shadow_page_allowlist": "page_1"
            },
            fitz_version=self.module.REQUIRED_FITZ_VERSION,
        )
        semantic_enabled = self.module.evaluate_gate1_operational_state(
            valves={"pdf_semantic_header_shadow_enabled": True},
            fitz_version=self.module.REQUIRED_FITZ_VERSION,
        )
        wrong_runtime = self.module.evaluate_gate1_operational_state(
            valves={"pdf_structural_repair_shadow_enabled": False},
            fitz_version="0.0.0",
        )

        self.assertTrue(passed["structural_shadow_disabled"])
        self.assertTrue(passed["guided_intake_shadow_disabled"])
        self.assertTrue(passed["guided_page_allowlist_empty"])
        self.assertTrue(passed["semantic_header_shadow_disabled"])
        self.assertTrue(passed["fitz_version_match"])
        self.assertFalse(enabled["structural_shadow_disabled"])
        self.assertFalse(guided_enabled["guided_intake_shadow_disabled"])
        self.assertFalse(page_allowlisted["guided_page_allowlist_empty"])
        self.assertFalse(semantic_enabled["semantic_header_shadow_disabled"])
        self.assertFalse(wrong_runtime["fitz_version_match"])

    def test_gate1_contract_has_continuation_antidrift_markers(self):
        markers = set(self.module.FUNCTION_CONTRACTS[0].required_markers)

        self.assertIn(
            "broker_reports_pdf_structural_repair_continuation_result_v1",
            markers,
        )
        self.assertIn(
            "broker_reports_pdf_continuation_materialization_v1",
            markers,
        )
        self.assertIn("run_continuation_group", markers)

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
        self.assertEqual({}, prompts)
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertNotIn("StrictHostKeyChecking=no", command)


if __name__ == "__main__":
    unittest.main()
