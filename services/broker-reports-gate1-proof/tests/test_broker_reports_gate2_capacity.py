from __future__ import annotations

import unittest

from scripts.measure_gate2_capacity import build_safe_report


def _run(*, wall: float) -> dict:
    return {
        "workload": {
            "workload_fingerprint": "safe-workload-fingerprint",
            "run_label": "safe-run-label",
        },
        "input_inventory": {"records_total": 100, "payload_bytes": 1000},
        "runtime": {
            "python": "3.11.9",
            "sqlite": "3.45.1",
            "platform": "test-platform",
            "logical_cpus": 8,
            "physical_memory_bytes": 32_000,
            "storage_location": "isolated_test",
        },
        "resource_profile": {"wall_seconds": wall},
        "provider_attribution": {"provider_client_or_transport_calls": 0},
        "result": {
            "validator_status": "passed",
            "errors_count": 0,
            "warnings_count": 0,
            "packages_total": 681,
            "packages_passed": 681,
            "source_ready_refs_total": 75,
            "packageable_documents_total": 75,
            "artifactstore_unchanged": True,
        },
    }


class BrokerReportsGate2CapacityTest(unittest.TestCase):
    def test_report_preserves_terminal_outcome_and_computes_capacity_ratios(self):
        runs = [
            _run(wall=value) for value in (50.0, 95.0, 97.0)
        ]
        one = {
            "group_wall_seconds": 50.0,
            "worker_wall_seconds": [50.0],
            "worker_failures": 0,
            "database_lock_errors": 0,
            "artifactstore_unchanged": True,
        }
        two = {
            "group_wall_seconds": 98.0,
            "worker_wall_seconds": [95.0, 97.0],
            "worker_failures": 0,
            "database_lock_errors": 0,
            "artifactstore_unchanged": True,
        }

        report = build_safe_report(
            revision="test-revision",
            one=one,
            two=two,
            runs=runs,
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(
            report["comparison"]["per_worker_wall_degradation_ratio"], 1.92
        )
        self.assertEqual(
            report["comparison"]["aggregate_throughput_ratio_vs_one_worker"],
            1.020408,
        )
        self.assertTrue(
            report["comparison"]["two_worker_terminal_correctness_preserved"]
        )
        self.assertEqual(report["terminal_outcome"]["packages_passed"], 681)


if __name__ == "__main__":
    unittest.main()
