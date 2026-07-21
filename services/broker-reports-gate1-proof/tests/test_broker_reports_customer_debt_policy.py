from __future__ import annotations

import unittest

from broker_reports_gate1 import Gate1Normalizer
from broker_reports_gate1.customer_debt_policy import (
    SBER_BROKER_PROFILE_GENERALIZATION,
    SBER_BROKER_PROFILE_IMPLEMENTATION,
    SBER_BROKER_PROFILE_RELEASE,
    SBER_BROKER_PROFILE_VALVE,
    SBER_OPEN_DEBT_PROOF_SCOPES,
    CustomerDebtPolicyError,
    sber_broker_profile_enabled,
)


class BrokerReportsCustomerDebtPolicyTest(unittest.TestCase):
    def test_required_external_statuses_remain_independent(self) -> None:
        self.assertEqual(SBER_BROKER_PROFILE_IMPLEMENTATION, "actual_corpus_proven")
        self.assertEqual(
            SBER_BROKER_PROFILE_GENERALIZATION,
            "awaiting_customer_positive_holdout",
        )
        self.assertEqual(SBER_BROKER_PROFILE_RELEASE, "gated")

    def test_profile_is_default_off_and_requires_exact_proof_scope(self) -> None:
        self.assertFalse(sber_broker_profile_enabled({}))
        self.assertFalse(
            sber_broker_profile_enabled({SBER_BROKER_PROFILE_VALVE: False})
        )
        for proof_scope in (None, "", "production", "client_requested"):
            with self.assertRaisesRegex(
                CustomerDebtPolicyError,
                "sber_broker_profile_proof_scope_denied",
            ):
                sber_broker_profile_enabled(
                    {
                        SBER_BROKER_PROFILE_VALVE: True,
                        "proof_scope": proof_scope,
                    }
                )

    def test_every_maintained_private_scope_is_explicitly_authorized(self) -> None:
        self.assertEqual(
            SBER_OPEN_DEBT_PROOF_SCOPES,
            frozenset(
                {
                    "actual_customer_approved_source_evidence_pool_v1",
                    "deterministic_test_fixture",
                    "future_positive_holdout_validation_v1",
                }
            ),
        )
        for proof_scope in SBER_OPEN_DEBT_PROOF_SCOPES:
            self.assertTrue(
                sber_broker_profile_enabled(
                    {
                        SBER_BROKER_PROFILE_VALVE: True,
                        "proof_scope": proof_scope,
                    }
                )
            )

    def test_normalizer_denies_client_shaped_enablement_before_processing(self) -> None:
        with self.assertRaisesRegex(
            CustomerDebtPolicyError,
            "sber_broker_profile_proof_scope_denied",
        ):
            Gate1Normalizer().normalize(
                [],
                input_context={
                    SBER_BROKER_PROFILE_VALVE: True,
                    "proof_scope": "ordinary_runtime_request",
                },
            )


if __name__ == "__main__":
    unittest.main()
