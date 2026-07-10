from __future__ import annotations

import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "openwebui_actions" / "broker_reports_gate2_source_fact_pipe_bundled.py"
DOMAIN_BUNDLE = ROOT / "openwebui_actions" / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"


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
        self.assertIn("gate2_source_fact_validation", source)
        self.assertIn("gate2_source_fact_runtime", source)
        self.assertNotIn("sys.path.insert", source)
        self.assertNotIn("services/broker-reports-gate1-proof/broker_reports_gate1", source)

        module = load_bundle_module()
        bundled_package = sys.modules["broker_reports_gate1"]
        self.assertTrue(hasattr(bundled_package, "Gate2SourceFactRuntimeFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2ManagedPromptResolverFactory"))
        pipe = module.Pipe()
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
            "gate2_domain_routing",
            "gate2_domain_packages",
            "gate2_source_unit_segmentation",
            "gate2_domain_contracts",
            "gate2_source_fact_stitching",
            "gate2_domain_runtime",
        ):
            self.assertIn(module_name, source)
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


if __name__ == "__main__":
    unittest.main()
