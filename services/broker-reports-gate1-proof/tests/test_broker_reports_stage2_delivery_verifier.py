from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
