from __future__ import annotations

import unittest

from scripts.benchmark_gate2_controlled import build_safe_report


def _run(*, mode: str, cache_state: str, wall: float) -> dict:
    phases = (
        {
            "preconditions": 0.5,
            "scope_readiness_reconciliation": 30.0,
            "package_enumeration_construction_validation": 20.0,
            "safe_report_rendering": 1.0,
        }
        if mode == "instrumented"
        else {}
    )
    return {
        "measurement_mode": mode,
        "cache_state": cache_state,
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
        "resource_profile": {
            "wall_seconds": wall,
            "cpu_user_seconds": wall - 1,
            "cpu_system_seconds": 1,
            "rss_peak_sampled_bytes": 4000,
            "rss_incremental_peak_bytes": 3000,
            "disk_read_bytes": 2000,
            "disk_write_bytes": 100,
        },
        "phase_profile": {
            "phases": phases,
            "candidate_outcomes": {"package_candidates_enumerated": 924},
        },
        "function_profile": {"resolver.resolve": {"calls": 933}},
        "resolver_store_profile": {
            "payload_reads_total": 933,
            "payload_bytes_read": 1500,
            "duplicate_payload_reads_total": 0,
        },
        "sqlite_profile": {"queries_total": 935},
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
            "slice_audit": {
                "pdf_parent_full_validation_total": 45,
                "pdf_parent_validation_cache_hit_total": 532,
            },
        },
    }


class BrokerReportsGate2ControlledBenchmarkTest(unittest.TestCase):
    def test_safe_report_classifies_instrumentation_without_false_regression(self):
        cold = [_run(mode="baseline", cache_state="first_process", wall=value) for value in (52.0, 53.0, 54.0)]
        warm = [_run(mode="baseline", cache_state="warm_os_cache", wall=value) for value in (51.0, 52.0, 53.0)]
        instrumented = [_run(mode="instrumented", cache_state="warm_os_cache", wall=value) for value in (108.0, 110.0, 112.0)]
        reference = {
            "gate2_reproof": {
                "after": {"wall_seconds": 53.146799, "packages_total": 681},
                "performance_threshold_ratio": 1.25,
            }
        }

        report = build_safe_report(
            revision="test-revision",
            cold_runs=cold,
            warm_runs=warm,
            instrumented_runs=instrumented,
            prewarm_receipts=[
                {"bytes": 1500, "wall_seconds": 0.1} for _ in range(6)
            ],
            reference=reference,
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(
            report["reference_comparison"]["performance_status"],
            "no_regression_measurement_noise",
        )
        self.assertEqual(
            report["largest_instrumented_phase"],
            "scope_readiness_reconciliation",
        )
        self.assertEqual(report["terminal_outcome"]["packages_passed"], 681)
        self.assertEqual(report["operation_counts"]["sqlite_queries"], 935)
        self.assertTrue(report["privacy"]["artifactstore_unchanged"])


if __name__ == "__main__":
    unittest.main()
