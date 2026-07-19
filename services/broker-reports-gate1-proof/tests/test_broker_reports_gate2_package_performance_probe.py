from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from profile_gate2_package_preparation import (  # noqa: E402
    prepare_synthetic,
    run_measurement,
)

from broker_reports_gate1.gate2_input_readiness import (  # noqa: E402
    FACTORY_REQUIRED as GATE2_FACTORY_REQUIRED,
    FORBIDDEN as GATE2_FORBIDDEN,
)


@unittest.skipUnless(
    importlib.util.find_spec("psutil") is not None,
    "performance probe requires optional psutil instrumentation",
)
class BrokerReportsGate2PackagePerformanceProbeTest(unittest.TestCase):
    def test_probe_measures_canonical_package_path_without_provider_or_persistence(self):
        prepared = prepare_synthetic("csv", documents=1, csv_rows=3)
        try:
            measurement = run_measurement(
                prepared,
                mode="instrumented",
                cache_state="first_process",
            )
        finally:
            prepared.cleanup()

        self.assertEqual(measurement["result"]["validator_status"], "passed")
        self.assertEqual(measurement["result"]["packages_total"], 1)
        self.assertEqual(measurement["result"]["packages_passed"], 1)
        self.assertTrue(measurement["result"]["artifactstore_unchanged"])
        self.assertEqual(
            measurement["provider_attribution"]["provider_client_or_transport_calls"],
            0,
        )
        self.assertEqual(
            measurement["provider_attribution"]["packages_claiming_model_call"],
            0,
        )
        self.assertEqual(
            measurement["persistence_serialization"]["package_persistence_calls"],
            0,
        )
        self.assertGreater(
            measurement["resolver_store_profile"]["payload_reads_total"], 0
        )
        self.assertGreater(measurement["sqlite_profile"]["queries_total"], 0)
        outcomes = measurement["phase_profile"]["candidate_outcomes"]
        self.assertEqual(outcomes["package_candidates_enumerated"], 1)
        self.assertEqual(outcomes["packages_built"], 1)
        self.assertEqual(outcomes["candidates_not_built"], 0)

        rendered = json.dumps(measurement, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("synthetic-0.csv", rendered)
        self.assertNotIn("2026-01-01", rendered)
        self.assertNotIn("private_path", rendered)

    def test_probe_retains_factory_antidrift_anchors(self):
        self.assertIn("Gate2InputReadinessFactory.create", GATE2_FACTORY_REQUIRED)
        self.assertIn("must not read ArtifactStore payloads", GATE2_FORBIDDEN)

    def test_narrow_probe_times_discovery_without_line_tracing(self):
        prepared = prepare_synthetic("csv", documents=1, csv_rows=3)
        try:
            measurement = run_measurement(
                prepared,
                mode="narrow",
                cache_state="warm_os_cache",
            )
        finally:
            prepared.cleanup()

        self.assertEqual(measurement["result"]["validator_status"], "passed")
        private_phase = measurement["function_profile"][
            "phase.private_artifact_discovery_validation"
        ]
        self.assertEqual(private_phase["calls"], 1)
        self.assertGreater(private_phase["inclusive_wall_seconds"], 0)
        self.assertEqual(
            measurement["provider_attribution"]["provider_client_or_transport_calls"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
