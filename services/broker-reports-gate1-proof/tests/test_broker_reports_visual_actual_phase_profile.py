from __future__ import annotations

import unittest

from scripts.profile_visual_actual_corpus import MetricBook, build_safe_report


class BrokerReportsVisualActualPhaseProfileTest(unittest.TestCase):
    def test_safe_projection_preserves_terminal_accounting(self):
        metrics = MetricBook()
        metrics.add("ocr.isolated_two_pass", 10.0)
        visual = {
            "status": "passed",
            "material_scope_accounting": {
                "material_visual_scopes_requiring_recovery": 10,
                "accepted_recovered_scopes": 10,
                "confirmed_empty_source_scopes": 1,
                "unresolved_visual_scopes": 0,
                "unsupported_visual_scopes": 0,
            },
            "canonical_region_accounting": {
                "tables_accepted": 17,
                "cells_accepted": 623,
            },
            "gate2_canonical_integration": {
                "gate2_validator_status": "passed",
                "gate2_errors": 0,
                "gate2_artifactstore_unchanged_after_handoff": True,
            },
            "provider_accounting": {"calls": 0},
        }
        report = build_safe_report(
            revision="test-revision",
            visual=visual,
            metrics=metrics,
            wall_seconds=20.0,
            peak_rss_bytes=4000,
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["terminal_outcome"]["accepted_scopes"], 10)
        self.assertEqual(report["terminal_outcome"]["confirmed_empty_scopes"], 1)
        self.assertEqual(report["terminal_outcome"]["gate2_errors"], 0)
        self.assertFalse(report["privacy"]["customer_values_in_output"])


if __name__ == "__main__":
    unittest.main()
