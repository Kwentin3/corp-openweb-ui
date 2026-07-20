from __future__ import annotations

import unittest

from scripts.prove_restricted_scope_stage_smoke import build_proof


class BrokerReportsRestrictedScopeStageSmokeTest(unittest.TestCase):
    def test_synthetic_restricted_scope_contour_is_terminal_and_provider_free(self):
        proof = build_proof()

        self.assertEqual(proof["status"], "passed")
        self.assertTrue(all(proof["checks"].values()))
        self.assertEqual(proof["accounting"]["archive_containers"], 1)
        self.assertEqual(proof["accounting"]["promoted_members"], 1)
        self.assertEqual(proof["accounting"]["fns_typed_packages"], 1)
        self.assertEqual(proof["accounting"]["provider_calls"], 0)
        self.assertFalse(
            proof["operational_valves"][
                "broker_pdf_neutral_table_profile_v1_enabled"
            ]
        )
        self.assertFalse(proof["privacy"]["knowledge_rag_used"])
        self.assertFalse(proof["privacy"]["vectorization_performed"])


if __name__ == "__main__":
    unittest.main()
