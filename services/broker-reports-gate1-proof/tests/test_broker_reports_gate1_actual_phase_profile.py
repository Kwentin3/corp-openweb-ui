from __future__ import annotations

import unittest

from scripts.profile_gate1_actual_corpus import MetricBook, build_safe_report


class BrokerReportsGate1ActualPhaseProfileTest(unittest.TestCase):
    def test_safe_report_contains_only_aggregate_phase_and_storage_evidence(self):
        metrics = MetricBook()
        metrics.add("full_source_build.pdf", 12.5)
        metrics.add("full_source_build.pdf", 7.5)
        proof = {
            "proof_status": "passed",
            "actual_execution": {
                "top_level_inputs_total": 56,
                "document_sources_total": 104,
                "logical_documents_total": 80,
                "archive_containers_total": 24,
                "archive_promoted_members_total": 48,
                "zero_silent_loss_status": "passed",
                "terminal_status_counts": {"complete": 26, "review_required": 78},
            },
            "performance": {
                "gate1_normalization_wall_seconds": 100.0,
                "actual_proof_wall_seconds": 120.0,
            },
            "automated_checks": {"knowledge_rag_absent": True},
        }
        report = build_safe_report(
            revision="test-revision",
            proof=proof,
            metrics=metrics,
            total_wall_seconds=121.0,
            peak_rss_bytes=7000,
            storage={"records_total": 10, "payload_bytes_total": 1000},
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(
            report["inclusive_phase_profile"]["full_source_build.pdf"]["calls"],
            2,
        )
        self.assertEqual(
            report["inclusive_phase_profile"]["full_source_build.pdf"][
                "inclusive_wall_seconds"
            ],
            20.0,
        )
        self.assertTrue(
            report["interpretation_guards"][
                "inclusive_nested_times_must_not_be_summed"
            ]
        )
        self.assertFalse(report["privacy"]["customer_values_in_output"])


if __name__ == "__main__":
    unittest.main()
