from __future__ import annotations

import unittest

from scripts.audit_retention_run_scope import run_audit


class BrokerReportsRetentionRunScopeAuditTest(unittest.TestCase):
    def test_real_store_expiry_closes_context_and_concurrency_contract(self):
        report = run_audit(unrelated_records=25)

        self.assertTrue(
            report["run_scoped_expiry"]["unrelated_records_unchanged"]
        )
        self.assertEqual(
            report["run_scoped_expiry"][
                "unrelated_records_examined_by_result_materialization"
            ],
            0,
        )
        self.assertTrue(
            report["run_scoped_expiry"]["sql_shape_run_predicate_present"]
        )
        self.assertTrue(report["run_scoped_expiry"]["empty_run_scope_denied"])
        self.assertTrue(report["run_scoped_expiry"]["context_bound_api"])
        self.assertTrue(
            report["run_scoped_expiry"]["case_or_tenant_predicate_present"]
        )
        self.assertTrue(report["repeated_expiry"]["strict_idempotence"])
        self.assertTrue(
            report["concurrent_expiry"]["terminal_state_correct"]
        )
        self.assertTrue(
            report["partial_cleanup_failure"]["exception_propagated"]
        )
        self.assertFalse(
            report["partial_cleanup_failure"]["false_terminal_success"]
        )
        self.assertTrue(
            report["partial_cleanup_failure"][
                "record_left_recoverably_purge_pending"
            ]
        )
        self.assertTrue(
            report["partial_cleanup_failure"][
                "same_context_retry_completed"
            ]
        )
        self.assertEqual(
            report["concurrent_expiry"]["result_cardinalities"],
            [0, 20],
        )
        self.assertEqual(report["status"], "passed")


if __name__ == "__main__":
    unittest.main()
