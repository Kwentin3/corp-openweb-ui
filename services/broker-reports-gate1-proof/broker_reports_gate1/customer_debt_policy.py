from __future__ import annotations

from typing import Any


SBER_BROKER_PROFILE_IMPLEMENTATION = "actual_corpus_proven"
SBER_BROKER_PROFILE_GENERALIZATION = "awaiting_customer_positive_holdout"
SBER_BROKER_PROFILE_RELEASE = "gated"
SBER_BROKER_PROFILE_VALVE = "broker_pdf_neutral_table_profile_v1_enabled"

SBER_OPEN_DEBT_PROOF_SCOPES = frozenset(
    {
        "actual_customer_approved_source_evidence_pool_v1",
        "deterministic_test_fixture",
        "future_positive_holdout_validation_v1",
    }
)

FORBIDDEN = (
    "The Sber neutral-table profile must not be enabled without an exact "
    "maintained private proof scope while the customer holdout debt is open"
)


class CustomerDebtPolicyError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def sber_broker_profile_enabled(input_context: dict[str, Any] | None) -> bool:
    """Authorize the frozen profile only inside an explicit debt-proof scope."""

    context = input_context if isinstance(input_context, dict) else {}
    if context.get(SBER_BROKER_PROFILE_VALVE) is not True:
        return False
    proof_scope = str(context.get("proof_scope") or "")
    if proof_scope not in SBER_OPEN_DEBT_PROOF_SCOPES:
        raise CustomerDebtPolicyError("sber_broker_profile_proof_scope_denied")
    return True
