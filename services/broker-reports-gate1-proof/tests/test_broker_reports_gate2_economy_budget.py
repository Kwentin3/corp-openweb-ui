from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace

import pytest

from broker_reports_gate1.gate2_economy_budget import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2EconomyBudgetSessionFactory,
    estimate_gate2_request_input_tokens,
)
from broker_reports_gate1.gate2_economy_model_policy import (
    Gate2EconomyModelPolicyFactory,
)
from broker_reports_gate1.gate2_model_clients import (
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
)
from broker_reports_gate1.gate2_model_requests import (
    FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
)
from broker_reports_gate1.gate2_provider_adapters import (
    Gate2OpenWebUIProviderConnection,
)


GEMINI_MODEL = "models/gemini-3.1-flash-lite"
HAIKU_MODEL = "claude-haiku-4-5-20251001"


def test_policy_cost_budgets_have_measured_basis_and_are_versioned() -> None:
    policy = Gate2EconomyModelPolicyFactory().create()

    assert policy.policy_version == "1.2.0"
    assert len(policy.policy_hash) == 64
    for workload in policy.workloads:
        assert workload.maximum_estimated_cost_usd_per_operation
        assert workload.maximum_estimated_cost_usd_per_full_scope_run
        assert "actual" in workload.budget_measurement_basis


def test_prepare_call_applies_output_reasoning_and_paid_tool_controls() -> None:
    session = _financial_session()

    authorization = session.prepare_call(
        form_data=_form_data(),
        model_id=GEMINI_MODEL,
        provider_profile_id="google_gemini",
        operation_identity="scope-1",
    )

    assert authorization.maximum_output_tokens == 640
    assert authorization.prepared_form_data["max_tokens"] == 640
    assert authorization.prepared_form_data["reasoning_effort"] == "minimal"
    assert "tools" not in authorization.prepared_form_data
    budget = authorization.prepared_form_data["metadata"][
        "broker_reports_gate2"
    ]["economy_budget"]
    assert budget["paid_tools_allowed"] is False
    assert budget["maximum_output_tokens"] == 640
    assert authorization.estimated_input_tokens == (
        estimate_gate2_request_input_tokens(
            authorization.prepared_form_data
        )
    )


def test_alias_is_resolved_to_exact_model_before_provider_call() -> None:
    session = _financial_session()

    authorization = session.prepare_call(
        form_data=_form_data(),
        model_id="gemini-3.1-flash-lite",
        provider_profile_id="google_gemini",
        operation_identity="alias-resolution",
    )

    assert authorization.requested_model_id == "gemini-3.1-flash-lite"
    assert authorization.exact_model_id == GEMINI_MODEL
    assert authorization.prepared_form_data["model"] == GEMINI_MODEL


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ({"tools": [{"type": "web_search"}]}, "gate2_economy_paid_tools_forbidden"),
        ({"max_tokens": 641}, "gate2_economy_output_token_budget_exceeded"),
        (
            {"reasoning_effort": "high"},
            "gate2_economy_reasoning_policy_forbidden",
        ),
    ],
)
def test_request_budget_escalation_is_rejected(
    mutation: dict,
    code: str,
) -> None:
    session = _financial_session()
    form_data = _form_data()
    form_data.update(mutation)

    with pytest.raises(Gate2SourceFactRuntimeError) as exc_info:
        session.prepare_call(
            form_data=form_data,
            model_id=GEMINI_MODEL,
            provider_profile_id="google_gemini",
            operation_identity="scope-1",
        )

    assert exc_info.value.code == code
    assert session._provider_calls_authorized_total == 0


def test_input_budget_blocks_before_provider_authorization() -> None:
    session = _financial_session()
    form_data = _form_data()
    form_data["messages"][0]["content"] = "x" * 20_000

    with pytest.raises(Gate2SourceFactRuntimeError) as exc_info:
        session.prepare_call(
            form_data=form_data,
            model_id=GEMINI_MODEL,
            provider_profile_id="google_gemini",
            operation_identity="oversized-scope",
        )

    assert exc_info.value.code == "gate2_economy_input_token_budget_exceeded"
    assert session._provider_calls_authorized_total == 0
    safe = exc_info.value.raw_output["economy_budget_receipt"]
    assert safe["status"] == "blocked"
    assert safe["customer_content_in_receipt"] is False
    assert "x" * 100 not in str(safe)


def test_default_and_fallback_call_budgets_are_enforced() -> None:
    session = _financial_session()
    common = {
        "form_data": _form_data(),
        "model_id": GEMINI_MODEL,
        "provider_profile_id": "google_gemini",
        "operation_identity": "scope-call-budget",
    }
    session.prepare_call(**common)
    with pytest.raises(Gate2SourceFactRuntimeError) as duplicate:
        session.prepare_call(**common)
    assert duplicate.value.code == "gate2_economy_provider_call_budget_exceeded"

    session.prepare_call(**common, fallback_call=True)
    with pytest.raises(Gate2SourceFactRuntimeError) as second_fallback:
        session.prepare_call(**common, fallback_call=True)
    assert (
        second_fallback.value.code
        == "gate2_economy_fallback_call_budget_exceeded"
    )


def test_full_scope_preflight_uses_measured_39_call_aggregate() -> None:
    session = _financial_session()
    measured_inputs = (1_181,) * 38 + (2_655,)

    receipt = session.preflight_full_scope(
        model_id=GEMINI_MODEL,
        provider_profile_id="google_gemini",
        default_call_input_tokens=measured_inputs,
    )

    assert sum(measured_inputs) == 47_533
    assert receipt["status"] == "authorized"
    assert receipt["planned_operations_total"] == 39
    assert receipt["planned_provider_calls_total"] == 39
    assert receipt["planned_fallback_calls_total"] == 0
    assert receipt["estimated_input_tokens_total"] == 47_533
    assert receipt["estimated_cost_usd"] == "0.049323250"
    assert receipt["customer_content_in_receipt"] is False
    assert len(receipt["integrity_hash"]) == 64


def test_full_scope_preflight_rejects_calls_before_execution() -> None:
    session = _financial_session()

    with pytest.raises(Gate2SourceFactRuntimeError) as exc_info:
        session.preflight_full_scope(
            model_id=GEMINI_MODEL,
            provider_profile_id="google_gemini",
            default_call_input_tokens=(1_000,) * 65,
        )

    assert (
        exc_info.value.code
        == "gate2_economy_full_scope_call_budget_exceeded"
    )
    assert session._provider_calls_authorized_total == 0


def test_checksum_preflight_uses_measured_actual_corpus_size() -> None:
    session = Gate2EconomyBudgetSessionFactory().create(
        request_profile=FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
    )

    receipt = session.preflight_full_scope(
        model_id=HAIKU_MODEL,
        provider_profile_id="anthropic_claude",
        default_call_input_tokens=(117_555,),
    )

    assert receipt["planned_provider_calls_total"] == 1
    assert receipt["estimated_input_tokens_total"] == 117_555
    assert receipt["maximum_output_tokens_per_call"] == 1_024
    assert receipt["estimated_cost_usd"] == "0.122675000"
    assert receipt["budget_status"] == "within_budget"


def test_execution_receipt_accounts_usage_cost_and_no_customer_content() -> None:
    session = _financial_session()
    authorization = session.prepare_call(
        form_data=_form_data(),
        model_id=GEMINI_MODEL,
        provider_profile_id="google_gemini",
        operation_identity="private/customer/scope/identity",
    )

    receipt = session.finalize_call(
        authorization=authorization,
        execution_metadata=_execution(
            provider_id="google",
            provider_profile_id="google_gemini",
            requested_model_id=GEMINI_MODEL,
            resolved_model_id=GEMINI_MODEL,
            input_tokens=1_200,
            output_tokens=200,
            cached_input_tokens=100,
            reasoning_tokens=20,
        ),
    )

    assert receipt["input_tokens"] == 1_200
    assert receipt["output_tokens"] == 200
    assert receipt["cached_input_tokens"] == 100
    assert receipt["reasoning_tokens"] == 20
    assert receipt["call_count"] == 1
    assert receipt["actual_cost_usd"] == "0.000577500"
    assert receipt["budget_status"] == "within_budget"
    assert receipt["paid_tools_used"] == 0
    assert receipt["customer_content_in_receipt"] is False
    assert "private/customer" not in str(receipt)


def test_missing_usage_and_disabled_reasoning_fail_closed() -> None:
    session = _financial_session()
    authorization = session.prepare_call(
        form_data=_form_data(),
        model_id=GEMINI_MODEL,
        provider_profile_id="google_gemini",
        operation_identity="missing-usage",
    )
    with pytest.raises(Gate2SourceFactRuntimeError) as usage_missing:
        session.finalize_call(
            authorization=authorization,
            execution_metadata=_execution(
                provider_id="google",
                provider_profile_id="google_gemini",
                requested_model_id=GEMINI_MODEL,
                resolved_model_id=GEMINI_MODEL,
                input_tokens=None,
                output_tokens=None,
            ),
        )
    assert (
        usage_missing.value.code
        == "gate2_economy_usage_accounting_missing"
    )

    haiku = _financial_session()
    haiku_authorization = haiku.prepare_call(
        form_data=_form_data(),
        model_id=HAIKU_MODEL,
        provider_profile_id="anthropic_claude",
        operation_identity="reasoning-disabled",
    )
    with pytest.raises(Gate2SourceFactRuntimeError) as reasoning:
        haiku.finalize_call(
            authorization=haiku_authorization,
            execution_metadata=_execution(
                provider_id="anthropic",
                provider_profile_id="anthropic_claude",
                requested_model_id=HAIKU_MODEL,
                resolved_model_id=HAIKU_MODEL,
                input_tokens=1_000,
                output_tokens=100,
                reasoning_tokens=1,
            ),
        )
    assert reasoning.value.code == "gate2_economy_reasoning_budget_exceeded"


def test_resolved_model_identity_is_required_for_budget_receipt() -> None:
    session = _financial_session()
    authorization = session.prepare_call(
        form_data=_form_data(),
        model_id=GEMINI_MODEL,
        provider_profile_id="google_gemini",
        operation_identity="resolved-model-required",
    )

    with pytest.raises(Gate2SourceFactRuntimeError) as exc_info:
        session.finalize_call(
            authorization=authorization,
            execution_metadata=_execution(resolved_model_id=None),
        )

    assert exc_info.value.code == "gate2_economy_resolved_model_missing"


def test_canonical_model_client_enforces_budget_and_returns_safe_receipt() -> None:
    calls: list[dict] = []

    def completion(
        *,
        request,
        form_data,
        user,
        bypass_filter,
        bypass_system_prompt,
    ):
        calls.append(copy.deepcopy(form_data))
        return {
            "id": "economy-call-1",
            "model": GEMINI_MODEL,
            "usage": {
                "prompt_tokens": 900,
                "completion_tokens": 120,
                "total_tokens": 1_020,
                "prompt_tokens_details": {"cached_tokens": 100},
                "completion_tokens_details": {"reasoning_tokens": 10},
            },
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": {"disposition": "no_financial_input"}},
                }
            ],
        }

    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE,
            provider_profile_id="google_gemini",
            economy_budget_enforcement=True,
        ),
        user=SimpleNamespace(id="user-1"),
        request=object(),
        completion_resolver=lambda _user_id: (
            completion,
            SimpleNamespace(id="user-1"),
        ),
    ).create()
    prompt = SimpleNamespace(
        content="{{financial_evidence_package_json}}",
        prompt_ref="code:test",
        hash="a" * 64,
    )

    result = asyncio.run(
        client.extract(
            prompt=prompt,
            package={
                "llm_context_package": {"scope": "synthetic"},
                "source_scope_ref": "synthetic:scope",
            },
            model_id=GEMINI_MODEL,
            response_format=_response_format(),
        )
    )

    assert len(calls) == 1
    assert calls[0]["max_tokens"] == 640
    assert calls[0]["reasoning_effort"] == "minimal"
    assert "tools" not in calls[0]
    assert result.economy_budget_receipt["input_tokens"] == 900
    assert result.economy_budget_receipt["output_tokens"] == 120
    assert result.economy_budget_receipt["cached_input_tokens"] == 100
    assert result.economy_budget_receipt["reasoning_tokens"] == 10
    assert result.economy_budget_receipt["customer_content_in_receipt"] is False


def test_anthropic_native_projection_uses_workload_output_cap() -> None:
    calls: list[dict] = []

    def native_transport(_profile, form_data):
        calls.append(copy.deepcopy(form_data))
        return {
            "id": "anthropic-economy-call",
            "model": HAIKU_MODEL,
            "content": [
                {
                    "type": "text",
                    "text": '{"disposition":"no_financial_input"}',
                }
            ],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 800,
                "output_tokens": 90,
                "cache_read_input_tokens": 50,
            },
        }

    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE,
            provider_profile_id="anthropic_claude",
            economy_budget_enforcement=True,
        ),
        user=SimpleNamespace(id="user-1"),
        request=object(),
        native_transport_resolver=native_transport,
        provider_connection_resolver=lambda _profile: (
            Gate2OpenWebUIProviderConnection(
                base_url="https://api.anthropic.com/v1",
                api_key="not-exposed",
            )
        ),
    ).create()

    result = asyncio.run(
        client.extract(
            prompt=SimpleNamespace(
                content="{{financial_evidence_package_json}}",
                prompt_ref="code:test",
                hash="a" * 64,
            ),
            package={
                "llm_context_package": {"scope": "synthetic"},
                "source_scope_ref": "synthetic:scope",
            },
            model_id=HAIKU_MODEL,
            response_format=_response_format(),
        )
    )

    assert len(calls) == 1
    assert calls[0]["max_tokens"] == 640
    assert "reasoning_effort" not in calls[0]
    assert "tools" not in calls[0]
    assert result.economy_budget_receipt["cached_input_tokens"] == 50
    assert result.economy_budget_receipt["reasoning_tokens"] is None


def test_factory_and_forbidden_anchors_are_explicit() -> None:
    assert "only production" in FACTORY_REQUIRED
    assert "must not bypass" in FORBIDDEN


def _financial_session():
    return Gate2EconomyBudgetSessionFactory().create(
        request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE,
    )


def _form_data() -> dict:
    return {
        "model": GEMINI_MODEL,
        "messages": [
            {"role": "system", "content": "bounded synthetic contract"},
            {"role": "user", "content": "return contract json"},
        ],
        "stream": False,
        "response_format": _response_format(),
        "metadata": {"broker_reports_gate2": {}},
    }


def _response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "synthetic_budget_contract",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "disposition": {"type": "string"},
                },
                "required": ["disposition"],
                "additionalProperties": False,
            },
        },
    }


def _execution(**changes) -> Gate2ProviderExecutionMetadata:
    values = {
        "provider_id": "google",
        "provider_profile_id": "google_gemini",
        "provider_profile_revision": "b" * 64,
        "adapter_id": "gemini_response_format",
        "adapter_version": "1.5.0",
        "requested_model_id": GEMINI_MODEL,
        "resolved_model_id": GEMINI_MODEL,
        "structured_output_mode": "openwebui_response_format_json_schema",
        "response_format_type": "json_schema",
        "response_format_schema_mode": "strict_json_schema",
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
    }
    values.update(changes)
    return Gate2ProviderExecutionMetadata(**values)
