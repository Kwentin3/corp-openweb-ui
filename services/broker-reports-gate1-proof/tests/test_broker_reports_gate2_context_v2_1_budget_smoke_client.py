from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import sys
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2ContextV21BudgetSmokeModelResult,
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    Gate2OpenWebUIProviderConnection,
    Gate2PreparedProviderRequest,
    Gate2ProviderAdapterFactory,
)


MODEL_VISIBLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "choice": {
            "type": "string",
            "enum": ["unclassified"],
        },
        "reason": {
            "type": "string",
            "enum": ["no_registry_type"],
        },
    },
    "required": ["choice", "reason"],
}
MODEL_VISIBLE_REQUEST = {
    "messages": [
        {
            "role": "system",
            "content": (
                "Select exactly one governed Context V2.1 choice."
            ),
        },
        {
            "role": "user",
            "content": (
                '{"choices":[],"task":"select","type_cards":[]}'
            ),
        },
    ],
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "strict": True,
            "schema": MODEL_VISIBLE_SCHEMA,
        },
    },
}
EXPECTED_CHOICE = {
    "choice": "unclassified",
    "reason": "no_registry_type",
}
PROVIDER_SPECS = (
    (
        "openai_gpt",
        "gpt-5.4-nano-2026-03-17",
        "openwebui",
    ),
    (
        "google_gemini",
        "models/gemini-3.1-flash-lite",
        "openwebui",
    ),
    (
        "anthropic_claude",
        "claude-haiku-4-5-20251001",
        "native",
    ),
)
PROVIDER_BASE_URLS = {
    "openai_gpt": "https://api.openai.com/v1",
    "google_gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai"
    ),
    "anthropic_claude": "https://api.anthropic.com/v1",
}


class CompletionBoundary:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = copy.deepcopy(response)
        self.resolved_user_ids: list[str] = []
        self.calls: list[dict[str, Any]] = []

    def resolve(self, user_id: str):
        self.resolved_user_ids.append(user_id)
        return self.complete, SimpleNamespace(id=user_id, role="admin")

    def complete(
        self,
        *,
        request,
        form_data,
        user,
        bypass_filter=False,
        bypass_system_prompt=False,
    ):
        self.calls.append(
            {
                "request": request,
                "form_data": copy.deepcopy(form_data),
                "user": user,
                "bypass_filter": bypass_filter,
                "bypass_system_prompt": bypass_system_prompt,
            }
        )
        return copy.deepcopy(self.response)


class NativeTransportBoundary:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = copy.deepcopy(response)
        self.calls: list[dict[str, Any]] = []

    def resolve(self, profile, form_data):
        self.calls.append(
            {
                "profile_id": profile.profile_id,
                "form_data": copy.deepcopy(form_data),
            }
        )
        return copy.deepcopy(self.response)


class FailingHTTPBoundary:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def open(self, request, timeout):
        self.calls.append({"request": request, "timeout": timeout})
        raise self.error


def _provider_response(
    *,
    provider_profile_id: str,
    model_id: str,
    terminal: bool,
) -> dict[str, Any]:
    if provider_profile_id == "anthropic_claude":
        return {
            "id": "msg_budget_smoke_test",
            "model": model_id,
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        EXPECTED_CHOICE,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                }
            ],
            "stop_reason": "end_turn" if terminal else "max_tokens",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 12,
            },
        }
    return {
        "id": "chatcmpl_budget_smoke_test",
        "model": model_id,
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": copy.deepcopy(EXPECTED_CHOICE),
                },
                "finish_reason": "stop" if terminal else "length",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 12,
            "total_tokens": 112,
        },
    }


def _prepared_request_and_hash(
    *,
    provider_profile_id: str,
    model_id: str,
    operation_identity: str,
) -> tuple[Gate2PreparedProviderRequest, str]:
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=(
            FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
        )
    ).build_from_sealed_context_v2_1(
        model_visible_request=copy.deepcopy(MODEL_VISIBLE_REQUEST),
        model_id=model_id,
    )
    authorization = (
        Gate2EconomyBudgetSessionFactory()
        .create(
            request_profile=(
                FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
            )
        )
        .prepare_call(
            form_data=form_data,
            model_id=model_id,
            provider_profile_id=provider_profile_id,
            operation_identity=operation_identity,
        )
    )
    prepared_request = Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile(provider_profile_id),
        capability_probe=True,
    ).create().prepare_context_v2_1_budget_smoke_form_data(
        form_data=authorization.prepared_form_data,
        response_format=copy.deepcopy(
            MODEL_VISIBLE_REQUEST["response_format"]
        ),
    )
    encoded = json.dumps(
        asdict(prepared_request),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return prepared_request, hashlib.sha256(encoded).hexdigest()


def _client_and_boundaries(
    *,
    provider_profile_id: str,
    model_id: str,
    terminal: bool,
    request_profile: str = (
        FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
    ),
    economy_budget_enforcement: bool = True,
    direct_http: bool = False,
) -> tuple[
    Any,
    CompletionBoundary,
    NativeTransportBoundary,
]:
    response = _provider_response(
        provider_profile_id=provider_profile_id,
        model_id=model_id,
        terminal=terminal,
    )
    completion_boundary = CompletionBoundary(response)
    native_boundary = NativeTransportBoundary(response)
    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=request_profile,
            provider_profile_id=provider_profile_id,
            capability_probe=True,
            economy_budget_enforcement=economy_budget_enforcement,
        ),
        user=SimpleNamespace(id="context-v2-1-budget-smoke-test-user"),
        request=SimpleNamespace(),
        completion_resolver=completion_boundary.resolve,
        native_transport_resolver=(
            None if direct_http else native_boundary.resolve
        ),
        provider_connection_resolver=lambda _profile: (
            Gate2OpenWebUIProviderConnection(
                base_url=PROVIDER_BASE_URLS[_profile.profile_id],
                api_key="unit-test-key",
            )
        ),
    ).create()
    return client, completion_boundary, native_boundary


def _run_budget_smoke(
    *,
    client,
    model_id: str,
    operation_identity: str,
    expected_prepared_request_hash: str,
    transport_policy: str = (
        CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
    ),
    expected_transport_contract_hash: str | None = None,
):
    if expected_transport_contract_hash is None:
        expected_transport_contract_hash = (
            client.provider_adapter
            .context_v2_1_budget_smoke_transport_contract(
                transport_policy=transport_policy,
            )
            .integrity_hash
        )
    return asyncio.run(
        client.extract_context_v2_1_once(
            model_visible_request=copy.deepcopy(MODEL_VISIBLE_REQUEST),
            canonical_schema=copy.deepcopy(MODEL_VISIBLE_SCHEMA),
            model_id=model_id,
            operation_identity=operation_identity,
            expected_prepared_request_hash=(
                expected_prepared_request_hash
            ),
            transport_policy=transport_policy,
            expected_transport_contract_hash=(
                expected_transport_contract_hash
            ),
        )
    )


@pytest.mark.parametrize(
    ("provider_profile_id", "model_id", "transport"),
    PROVIDER_SPECS,
)
def test_budget_smoke_client_submits_each_exact_prepared_request_once(
    provider_profile_id: str,
    model_id: str,
    transport: str,
) -> None:
    operation_identity = f"goal12-test:{provider_profile_id}:success"
    expected_prepared, expected_hash = _prepared_request_and_hash(
        provider_profile_id=provider_profile_id,
        model_id=model_id,
        operation_identity=operation_identity,
    )
    client, completion_boundary, native_boundary = (
        _client_and_boundaries(
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            terminal=True,
        )
    )

    result = _run_budget_smoke(
        client=client,
        model_id=model_id,
        operation_identity=operation_identity,
        expected_prepared_request_hash=expected_hash,
    )

    assert isinstance(result, Gate2ContextV21BudgetSmokeModelResult)
    assert result.prepared_request_hash == expected_hash
    assert result.prepared_request == expected_prepared
    assert result.raw_provider_response == _provider_response(
        provider_profile_id=provider_profile_id,
        model_id=model_id,
        terminal=True,
    )
    assert result.execution_metadata.requested_model_id == model_id
    assert result.execution_metadata.resolved_model_id == model_id
    assert result.execution_metadata.transport_type == "direct_provider_http"
    assert result.economy_budget_receipt["status"] == "passed"
    assert result.economy_budget_receipt["fallback_call"] is False
    assert client.qualification_lifecycle_snapshot() == {
        "local_invocations_total": 1,
        "provider_submissions_total": 1,
        "provider_responses_total": 1,
    }
    assert completion_boundary.calls == []
    assert completion_boundary.resolved_user_ids == []
    assert len(native_boundary.calls) == 1
    actual_form_data = native_boundary.calls[0]["form_data"]
    if transport == "native":
        assert result.adapter_extracted_output == json.dumps(
            EXPECTED_CHOICE,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    else:
        assert result.adapter_extracted_output == EXPECTED_CHOICE
    assert actual_form_data == result.prepared_request.form_data


def test_post_extraction_failure_preserves_exact_output_and_raw_response() -> None:
    provider_profile_id = "openai_gpt"
    model_id = "gpt-5.4-nano-2026-03-17"
    operation_identity = "goal12-test:openai:post-extraction-failure"
    _prepared, expected_hash = _prepared_request_and_hash(
        provider_profile_id=provider_profile_id,
        model_id=model_id,
        operation_identity=operation_identity,
    )
    client, completion_boundary, native_boundary = (
        _client_and_boundaries(
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            terminal=True,
        )
    )
    exact_output = {
        "choice": "unclassified",
        "reason": "x" * 131_073,
    }
    raw_response = _provider_response(
        provider_profile_id=provider_profile_id,
        model_id=model_id,
        terminal=True,
    )
    raw_response["choices"][0]["message"]["content"] = copy.deepcopy(
        exact_output
    )
    native_boundary.response = copy.deepcopy(raw_response)

    with pytest.raises(
        Gate2SourceFactRuntimeError,
        match="structural budget",
    ) as failure:
        _run_budget_smoke(
            client=client,
            model_id=model_id,
            operation_identity=operation_identity,
            expected_prepared_request_hash=expected_hash,
        )

    assert failure.value.code == "gate2_model_response_budget_exceeded"
    assert failure.value.failure_class == "response_budget"
    assert failure.value.adapter_extracted_output == exact_output
    assert failure.value.raw_provider_response == raw_response
    assert failure.value.economy_budget_receipt["call_count"] == 1
    assert client.qualification_lifecycle_snapshot() == {
        "local_invocations_total": 1,
        "provider_submissions_total": 1,
        "provider_responses_total": 1,
    }
    assert completion_boundary.calls == []
    assert completion_boundary.resolved_user_ids == []
    assert len(native_boundary.calls) == 1


@pytest.mark.parametrize(
    ("provider_profile_id", "model_id", "_transport"),
    PROVIDER_SPECS,
)
def test_budget_smoke_client_requires_one_terminal_provider_response(
    provider_profile_id: str,
    model_id: str,
    _transport: str,
) -> None:
    operation_identity = f"goal12-test:{provider_profile_id}:nonterminal"
    _prepared, expected_hash = _prepared_request_and_hash(
        provider_profile_id=provider_profile_id,
        model_id=model_id,
        operation_identity=operation_identity,
    )
    client, completion_boundary, native_boundary = (
        _client_and_boundaries(
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            terminal=False,
        )
    )

    with pytest.raises(
        Gate2SourceFactRuntimeError,
        match="terminal provider",
    ) as failure:
        _run_budget_smoke(
            client=client,
            model_id=model_id,
            operation_identity=operation_identity,
            expected_prepared_request_hash=expected_hash,
        )

    assert failure.value.code == "gate2_model_response_not_terminal"
    assert getattr(failure.value, "adapter_extracted_output", None) is None
    assert client.qualification_lifecycle_snapshot() == {
        "local_invocations_total": 1,
        "provider_submissions_total": 1,
        "provider_responses_total": 1,
    }
    assert len(completion_boundary.calls) + len(native_boundary.calls) == 1


@pytest.mark.parametrize(
    ("provider_profile_id", "model_id", "_transport"),
    PROVIDER_SPECS,
)
def test_wrong_frozen_plan_hash_stops_before_provider_transport(
    provider_profile_id: str,
    model_id: str,
    _transport: str,
) -> None:
    operation_identity = f"goal12-test:{provider_profile_id}:wrong-hash"
    client, completion_boundary, native_boundary = (
        _client_and_boundaries(
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            terminal=True,
        )
    )

    with pytest.raises(
        Gate2SourceFactRuntimeError,
        match="frozen plan",
    ) as failure:
        _run_budget_smoke(
            client=client,
            model_id=model_id,
            operation_identity=operation_identity,
            expected_prepared_request_hash="0" * 64,
        )

    assert failure.value.code == "gate2_model_request_plan_mismatch"
    assert getattr(failure.value, "adapter_extracted_output", None) is None
    assert client.qualification_lifecycle_snapshot() == {
        "local_invocations_total": 1,
        "provider_submissions_total": 0,
        "provider_responses_total": 0,
    }
    assert completion_boundary.calls == []
    assert completion_boundary.resolved_user_ids == []
    assert native_boundary.calls == []


@pytest.mark.parametrize(
    ("transport_policy", "expected_transport_contract_hash"),
    (
        ("forbidden_transport_policy", "0" * 64),
        (
            CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
            "0" * 64,
        ),
    ),
)
def test_wrong_transport_policy_or_hash_stops_before_provider_transport(
    transport_policy: str,
    expected_transport_contract_hash: str,
) -> None:
    provider_profile_id = "openai_gpt"
    model_id = "gpt-5.4-nano-2026-03-17"
    operation_identity = "goal12-test:openai:wrong-transport"
    _prepared, expected_hash = _prepared_request_and_hash(
        provider_profile_id=provider_profile_id,
        model_id=model_id,
        operation_identity=operation_identity,
    )
    client, completion_boundary, native_boundary = (
        _client_and_boundaries(
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            terminal=True,
        )
    )

    with pytest.raises(
        Gate2SourceFactRuntimeError,
        match="transport",
    ) as failure:
        _run_budget_smoke(
            client=client,
            model_id=model_id,
            operation_identity=operation_identity,
            expected_prepared_request_hash=expected_hash,
            transport_policy=transport_policy,
            expected_transport_contract_hash=(
                expected_transport_contract_hash
            ),
        )

    assert failure.value.code == "gate2_model_transport_plan_mismatch"
    assert client.qualification_lifecycle_snapshot() == {
        "local_invocations_total": 1,
        "provider_submissions_total": 0,
        "provider_responses_total": 0,
    }
    assert completion_boundary.calls == []
    assert completion_boundary.resolved_user_ids == []
    assert native_boundary.calls == []


def test_local_proof_profile_cannot_call_budget_smoke_client_seam() -> None:
    provider_profile_id = "openai_gpt"
    model_id = "gpt-5.4-nano-2026-03-17"
    client, completion_boundary, native_boundary = (
        _client_and_boundaries(
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            terminal=True,
            request_profile=(
                FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE
            ),
            economy_budget_enforcement=False,
        )
    )

    with pytest.raises(
        Gate2SourceFactRuntimeError,
        match="governed client profile",
    ) as failure:
        _run_budget_smoke(
            client=client,
            model_id=model_id,
            operation_identity="goal12-test:local-proof:forbidden",
            expected_prepared_request_hash="0" * 64,
        )

    assert failure.value.code == "gate2_model_request_profile_mismatch"
    assert client.qualification_lifecycle_snapshot() == {
        "local_invocations_total": 0,
        "provider_submissions_total": 0,
        "provider_responses_total": 0,
    }
    assert completion_boundary.calls == []
    assert completion_boundary.resolved_user_ids == []
    assert native_boundary.calls == []


@pytest.mark.parametrize(
    (
        "failure_code",
        "transport_error_type",
        "terminal_response_received",
        "expected_responses_total",
    ),
    (
        ("gate2_model_provider_http_error", None, True, 1),
        ("gate2_model_provider_unavailable", "TimeoutError", False, 0),
        ("gate2_model_provider_unavailable", "gaierror", False, 0),
        (
            "gate2_model_provider_unavailable",
            "ConnectionRefusedError",
            False,
            0,
        ),
    ),
)
def test_direct_transport_failure_accounts_only_received_http_response(
    failure_code: str,
    transport_error_type: str | None,
    terminal_response_received: bool,
    expected_responses_total: int,
) -> None:
    provider_profile_id = "openai_gpt"
    model_id = "gpt-5.4-nano-2026-03-17"
    operation_identity = (
        "goal12-test:openai:http-response-accounting:"
        f"{int(terminal_response_received)}"
    )
    _prepared, expected_hash = _prepared_request_and_hash(
        provider_profile_id=provider_profile_id,
        model_id=model_id,
        operation_identity=operation_identity,
    )
    client, completion_boundary, native_boundary = (
        _client_and_boundaries(
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            terminal=True,
            direct_http=True,
        )
    )
    if terminal_response_received:
        transport_error = HTTPError(
            (
                "https://api.openai.com/v1/chat/completions"
            ),
            429,
            "rate limited",
            {},
            BytesIO(b"bounded-http-error"),
        )
    elif transport_error_type == "gaierror":
        transport_error = URLError("dns resolution failed")
    elif transport_error_type == "TimeoutError":
        transport_error = TimeoutError("provider timeout")
    else:
        transport_error = ConnectionRefusedError(
            "provider connection refused"
        )
    http_boundary = FailingHTTPBoundary(transport_error)

    with patch(
        "broker_reports_gate1.gate2_provider_adapters.build_opener",
        return_value=http_boundary,
    ):
        with pytest.raises(Gate2SourceFactRuntimeError) as observed:
            _run_budget_smoke(
                client=client,
                model_id=model_id,
                operation_identity=operation_identity,
                expected_prepared_request_hash=expected_hash,
            )

    assert observed.value.code == failure_code
    assert (
        getattr(
            observed.value,
            "provider_response_received",
            False,
        )
        is terminal_response_received
    )
    assert client.qualification_lifecycle_snapshot() == {
        "local_invocations_total": 1,
        "provider_submissions_total": 1,
        "provider_responses_total": expected_responses_total,
    }
    assert completion_boundary.calls == []
    assert completion_boundary.resolved_user_ids == []
    assert native_boundary.calls == []
    assert len(http_boundary.calls) == 1
