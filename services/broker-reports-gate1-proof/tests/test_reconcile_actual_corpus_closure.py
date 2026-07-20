from __future__ import annotations

import json
import unittest

from scripts.reconcile_actual_corpus_closure import (
    DEFAULT_BROKER,
    DEFAULT_DEBT,
    DEFAULT_FNS,
    DEFAULT_GATE1,
    DEFAULT_GATE2_CURRENT,
    DEFAULT_GATE2_PREVIOUS,
    DEFAULT_VISUAL,
    _load,
    build_closure,
    render_report,
)


class ReconcileActualCorpusClosureTest(unittest.TestCase):
    def test_actual_safe_evidence_reconciles_without_unexplained_errors(self):
        proof = build_closure(
            gate1=_load(DEFAULT_GATE1),
            gate2_previous=_load(DEFAULT_GATE2_PREVIOUS),
            gate2_current=_load(DEFAULT_GATE2_CURRENT),
            fns=_load(DEFAULT_FNS),
            visual=_load(DEFAULT_VISUAL),
            broker=_load(DEFAULT_BROKER),
            debt=_load(DEFAULT_DEBT),
        )

        reconciliation = proof["readiness_error_reconciliation"]
        self.assertEqual(proof["status"], "COMPLETED")
        self.assertEqual(reconciliation["historical_errors_total"], 29)
        self.assertEqual(reconciliation["current_gate2_validator_errors"], 0)
        self.assertEqual(reconciliation["unexplained_error_count"], 0)
        self.assertEqual(
            {
                item["taxonomy"]
                for item in reconciliation["historical_resolution_rows"]
            },
            {"resolved_contract_defect", "resolved_missing_representation"},
        )
        self.assertEqual(
            {
                item["taxonomy"]
                for item in reconciliation["remaining_program_blockers"]
            },
            {"external_customer_acceptance_debt"},
        )
        self.assertEqual(
            {
                item["taxonomy"]
                for item in reconciliation["resolved_program_blockers"]
            },
            {"resolved_implementation_defect", "resolved_unsupported_profile"},
        )
        self.assertTrue(
            all(
                item["safe_error_id"].startswith("safeerr_")
                and item["terminal_state"]
                and item["next_action"]
                for group in (
                    "historical_resolution_rows",
                    "remaining_program_blockers",
                    "accounted_non_errors",
                )
                for item in reconciliation[group]
            )
        )
        self.assertEqual(
            proof["actual_corpus_accounting"]["gate2_packages"], 681
        )
        self.assertEqual(
            proof["actual_corpus_accounting"]["visual_accepted_recovered_scopes"],
            10,
        )
        self.assertEqual(
            proof["actual_corpus_accounting"]["visual_confirmed_empty_source_scopes"],
            1,
        )
        self.assertEqual(
            proof["actual_corpus_accounting"]["visual_unresolved_scopes"],
            0,
        )
        self.assertEqual(
            proof["actual_corpus_accounting"]["visual_gate2_packages"],
            17,
        )
        self.assertEqual(
            next(
                item["status"]
                for item in proof["workflow_readiness_matrix"]
                if item["workflow"] == "same_family_sber_profile_generalization"
            ),
            "externally_blocked",
        )

        rendered = json.dumps(proof, ensure_ascii=False, sort_keys=True)
        for forbidden in ("normrun_", "brdoc_", "srcunit_", "artifact_ref"):
            self.assertNotIn(forbidden, rendered)
        report = render_report(proof)
        self.assertIn("Program status: **COMPLETED**", report)
        self.assertIn("14/14", report)
        self.assertIn("10/10", report)
        self.assertIn("17 canonical regions", report)


if __name__ == "__main__":
    unittest.main()
