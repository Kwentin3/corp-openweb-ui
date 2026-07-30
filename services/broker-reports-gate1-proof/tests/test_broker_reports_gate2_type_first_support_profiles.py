from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from broker_reports_gate1.gate2_economy_budget import (
    TYPE_FIRST_ONE_CALL_NO_FALLBACK_POLICY_VERSION,
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2SourceFactRuntimeError,
)
from broker_reports_gate1.gate2_model_requests import (
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE,
    GATE2_REQUEST_PROFILES,
    Gate2OpenWebUIRequestBuilder,
)


GEMINI_MODEL = "models/gemini-3.1-flash-lite"


def test_type_first_request_profile_is_exact_sealed_only_and_inactive() -> None:
    assert (
        FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
        == "financial_semantic_v6_type_first_local_proof_v1"
    )
    assert (
        FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
        not in GATE2_REQUEST_PROFILES
    )
    builder = Gate2OpenWebUIRequestBuilder(
        request_profile=(
            FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
        )
    )

    with pytest.raises(Gate2SourceFactRuntimeError) as exc_info:
        builder.build(
            prompt=None,
            package={},
            model_id=GEMINI_MODEL,
            response_format={},
        )

    assert (
        exc_info.value.code
        == "gate2_model_request_sealed_context_required"
    )

    with pytest.raises(Gate2SourceFactRuntimeError) as invalid_exc:
        builder.build_from_sealed_type_first(
            sealed_request=_sealed_request(),  # type: ignore[arg-type]
            model_id=GEMINI_MODEL,
        )
    assert (
        invalid_exc.value.code
        == "gate2_model_request_sealed_context_required"
    )


def test_type_first_economy_is_one_call_no_fallback_without_policy_drift() -> None:
    factory = Gate2EconomyBudgetSessionFactory()
    historical = factory.create(
        request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE
    )
    type_first = factory.create(
        request_profile=(
            FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
        )
    )

    assert type_first.workload.workload_class == historical.workload.workload_class
    assert type_first.workload.maximum_provider_calls_per_operation == 1
    assert type_first.workload.maximum_fallback_calls_per_operation == 0
    assert historical.workload.maximum_fallback_calls_per_operation == 1
    assert (
        factory.policy.workload(historical.workload.workload_class)
        .maximum_fallback_calls_per_operation
        == 1
    )
    zero_call_receipt = type_first.type_first_accounting_receipt()
    assert zero_call_receipt["provider_calls_authorized_total"] == 0
    assert zero_call_receipt["fallback_calls_authorized_total"] == 0
    assert zero_call_receipt["authorized_operations_total"] == 0
    assert zero_call_receipt["estimated_cost_authorized_usd"] == "0.000000000"

    authorization = type_first.prepare_call(
        form_data=_form_data(),
        model_id=GEMINI_MODEL,
        provider_profile_id="google_gemini",
        operation_identity="type-first-one-call",
    )
    assert authorization.provider_calls_authorized_total == 1
    assert authorization.fallback_calls_authorized_total == 0

    with pytest.raises(Gate2SourceFactRuntimeError) as call_exc:
        type_first.prepare_call(
            form_data=_form_data(),
            model_id=GEMINI_MODEL,
            provider_profile_id="google_gemini",
            operation_identity="type-first-one-call",
        )
    assert call_exc.value.code == "gate2_economy_provider_call_budget_exceeded"

    fallback_session = factory.create(
        request_profile=(
            FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
        )
    )
    with pytest.raises(Gate2SourceFactRuntimeError) as fallback_exc:
        fallback_session.prepare_call(
            form_data=_form_data(),
            model_id=GEMINI_MODEL,
            provider_profile_id="google_gemini",
            operation_identity="type-first-no-fallback",
            fallback_call=True,
        )
    assert (
        fallback_exc.value.code
        == "gate2_economy_fallback_call_budget_exceeded"
    )
    assert fallback_session._provider_calls_authorized_total == 0
    assert fallback_session._fallback_calls_authorized_total == 0


def test_type_first_qualification_declaration_is_frozen_and_non_executable() -> None:
    from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_budget_smoke import (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator,
    )

    declaration = (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator
        .type_first_profile_declaration()
    )
    payload = declaration.to_dict()

    assert (
        payload["schema_version"]
        == "broker_reports_gate2_type_first_qualification_profile_v1"
    )
    assert payload["profile_identities"]["request"] == (
        FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
    )
    assert payload["profile_identities"]["economy"] == (
        TYPE_FIRST_ONE_CALL_NO_FALLBACK_POLICY_VERSION
    )
    assert payload["active"] is False
    assert payload["transport_eligible"] is False
    assert payload["execute_slot_allowed"] is False
    assert payload["provider_calls_authorized_total"] == 0
    assert payload["provider_submissions_total"] == 0
    assert payload["provider_responses_total"] == 0
    assert payload["hard_gates"] == {
        "unsafe_typed_total": 0,
        "false_singleton_typed_total": 0,
        "wrong_singleton_type_total": 0,
        "invalid_response_total": 0,
    }
    assert len(declaration.integrity_sha256) == 64
    assert declaration.integrity_sha256 == (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator
        .type_first_profile_declaration()
        .integrity_sha256
    )
    assert not hasattr(
        Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator,
        "execute_type_first_slot",
    )
    with pytest.raises(FrozenInstanceError):
        declaration.active = True  # type: ignore[misc]


def _sealed_request() -> dict:
    return {
        "messages": [
            {"role": "system", "content": "bounded synthetic system"},
            {
                "role": "user",
                "content": (
                    '{"task":"classify","source":[],"type_cards":[]}'
                ),
            },
        ],
        "response_format": _response_format(),
    }


def _form_data() -> dict:
    return {
        "model": GEMINI_MODEL,
        "messages": [
            {"role": "system", "content": "bounded synthetic system"},
            {"role": "user", "content": "return contract json"},
        ],
        "response_format": _response_format(),
        "metadata": {"broker_reports_gate2": {}},
    }


def _response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "broker_reports_gate2_type_first",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "plausible_types": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": ["plausible_types"],
                "additionalProperties": False,
            },
        },
    }
