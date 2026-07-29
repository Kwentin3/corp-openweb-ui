from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import sys
from dataclasses import asdict, replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2SourceFactRuntimeError,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE,
    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_CONTRACT_SCHEMA_VERSION,
    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    MAX_NATIVE_PROVIDER_RESPONSE_BYTES,
    Gate2ContextV21BudgetSmokeTransportContract,
    Gate2NativeProviderTransportConfig,
    Gate2OpenWebUIProviderConnection,
    Gate2OpenWebUIProviderConnectionResolver,
    Gate2ProviderAdapterFactory,
    _extract_openai_content,
)


PROVIDER_CASES = (
    (
        "openai_gpt",
        "gpt-5.4-nano-2026-03-17",
        "https://api.openai.com/v1",
        "https://api.openai.com/v1/chat/completions",
        {
            "authorization": "Bearer",
            "content-type": "application/json",
        },
    ),
    (
        "anthropic_claude",
        "claude-haiku-4-5-20251001",
        "https://api.anthropic.com/v1",
        "https://api.anthropic.com/v1/messages",
        {
            "anthropic-version": "2023-06-01",
            "authorization": "x-api-key",
            "content-type": "application/json",
        },
    ),
    (
        "google_gemini",
        "models/gemini-3.1-flash-lite",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        (
            "https://generativelanguage.googleapis.com/"
            "v1beta/openai/chat/completions"
        ),
        {
            "authorization": "Bearer",
            "content-type": "application/json",
        },
    ),
)


class _FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.read_limits: list[int] = []

    def read(self, limit: int) -> bytes:
        self.read_limits.append(limit)
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


class _FakeOpener:
    def __init__(
        self,
        *,
        response: _FakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[object, int]] = []

    def open(self, request, *, timeout: int):
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _adapter(
    profile_id: str,
    *,
    native_transport_resolver=None,
    provider_connection_resolver=None,
    transport_config: Gate2NativeProviderTransportConfig | None = None,
):
    return Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile(profile_id),
        capability_probe=True,
        native_transport_resolver=native_transport_resolver,
        provider_connection_resolver=provider_connection_resolver,
        native_transport_config=transport_config,
    ).create()


def _response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "choice": {
                        "type": "string",
                        "enum": ["choice_0", "unclassified"],
                    },
                    "reason": {
                        "type": "string",
                        "enum": [
                            "no_type_0",
                            "single_type_no_safe_record",
                        ],
                    },
                },
                "required": ["choice", "reason"],
            },
        },
    }


def _budget_authorized_form_data(model_id: str, marker: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": "synthetic system"},
            {"role": "user", "content": "synthetic user"},
        ],
        "response_format": copy.deepcopy(_response_format()),
        "model": model_id,
        "stream": False,
        "max_tokens": 640,
        "reasoning_effort": "minimal",
        "metadata": {
            "broker_reports_gate2": {
                "economy_budget": {
                    "out_of_band_marker": marker,
                }
            }
        },
    }


def _wire_form_data(profile_id: str, model_id: str) -> dict:
    common = {
        "model": model_id,
        "messages": [{"role": "user", "content": "точный synthetic request"}],
    }
    if profile_id == "openai_gpt":
        return {
            **common,
            "stream": False,
            "max_completion_tokens": 640,
        }
    if profile_id == "google_gemini":
        return {
            **common,
            "stream": False,
            "max_tokens": 640,
        }
    return {
        **common,
        "max_tokens": 640,
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": {"type": "object"},
            }
        },
    }


def _connection_resolver(base_url: str, api_key: str = "unit-secret"):
    def resolve(_profile):
        return Gate2OpenWebUIProviderConnection(
            base_url=base_url,
            api_key=api_key,
        )

    return resolve


def _hash_prepared_request(prepared_request) -> str:
    return hashlib.sha256(
        json.dumps(
            asdict(prepared_request),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    "profile_id,model_id,_base_url,_endpoint,_headers",
    PROVIDER_CASES,
)
def test_goal12_projection_removes_local_metadata_and_binds_vendor_output_cap(
    profile_id,
    model_id,
    _base_url,
    _endpoint,
    _headers,
):
    adapter = _adapter(profile_id)
    first_input = _budget_authorized_form_data(model_id, "first")
    second_input = _budget_authorized_form_data(model_id, "second")

    first = adapter.prepare_context_v2_1_budget_smoke_form_data(
        form_data=first_input,
        response_format=_response_format(),
    )
    second = adapter.prepare_context_v2_1_budget_smoke_form_data(
        form_data=second_input,
        response_format=_response_format(),
    )

    assert "metadata" not in first.form_data
    assert first == second
    assert _hash_prepared_request(first) == _hash_prepared_request(second)
    assert first_input["metadata"]["broker_reports_gate2"]
    if profile_id == "openai_gpt":
        assert first.form_data["max_completion_tokens"] == 640
        assert "max_tokens" not in first.form_data
    else:
        assert first.form_data["max_tokens"] == 640
        assert "max_completion_tokens" not in first.form_data


@pytest.mark.parametrize(
    "profile_id,model_id,_base_url,_endpoint,_headers",
    PROVIDER_CASES,
)
def test_goal12_native_resolver_receives_exact_form_once_under_exact_policy(
    profile_id,
    model_id,
    _base_url,
    _endpoint,
    _headers,
):
    calls = []

    def native_resolver(profile, form_data):
        calls.append((profile, form_data))
        return {"terminal": True}

    adapter = _adapter(
        profile_id,
        native_transport_resolver=native_resolver,
    )
    form_data = _wire_form_data(profile_id, model_id)

    with pytest.raises(Gate2SourceFactRuntimeError) as mismatch:
        adapter.invoke_context_v2_1_budget_smoke_once(
            form_data=form_data,
            transport_policy="wrong-policy",
        )
    assert mismatch.value.code == "gate2_model_transport_policy_mismatch"
    assert calls == []

    result = adapter.invoke_context_v2_1_budget_smoke_once(
        form_data=form_data,
        transport_policy=CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    )

    assert result == {"terminal": True}
    assert len(calls) == 1
    assert calls[0][0] == gate2_provider_profile(profile_id)
    assert calls[0][1] is form_data


@pytest.mark.parametrize(
    "profile_id,model_id,_base_url,_endpoint,_headers",
    PROVIDER_CASES,
)
def test_goal12_native_resolver_rejects_local_metadata_before_boundary(
    profile_id,
    model_id,
    _base_url,
    _endpoint,
    _headers,
):
    calls = []
    adapter = _adapter(
        profile_id,
        native_transport_resolver=lambda profile, form: calls.append(
            (profile, form)
        ),
    )
    form_data = _wire_form_data(profile_id, model_id)
    form_data["metadata"] = {"broker_reports_gate2": {}}

    with pytest.raises(Gate2SourceFactRuntimeError) as invalid:
        adapter.invoke_context_v2_1_budget_smoke_once(
            form_data=form_data,
            transport_policy=CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
        )

    assert invalid.value.code == "gate2_model_request_invalid"
    assert calls == []


@pytest.mark.parametrize(
    "profile_id,_model_id,_base_url,endpoint,semantic_headers",
    PROVIDER_CASES,
)
def test_goal12_transport_contract_is_offline_hashable_and_secret_free(
    profile_id,
    _model_id,
    _base_url,
    endpoint,
    semantic_headers,
):
    adapter = _adapter(profile_id)

    contract = adapter.context_v2_1_budget_smoke_transport_contract(
        transport_policy=CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    )
    snapshot = contract.safe_snapshot()

    assert isinstance(contract, Gate2ContextV21BudgetSmokeTransportContract)
    assert hash(contract)
    assert contract.schema_version == (
        CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_CONTRACT_SCHEMA_VERSION
    )
    assert contract.actual_transport_type == (
        CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE
    )
    assert contract.actual_transport_type == "direct_provider_http"
    assert contract.endpoint_url == endpoint
    assert contract.http_method == "POST"
    assert dict(contract.semantic_headers) == semantic_headers
    assert contract.redirect_policy == "deny_all"
    assert contract.proxy_policy == "ambient_proxies_disabled"
    assert contract.maximum_response_bytes == MAX_NATIVE_PROVIDER_RESPONSE_BYTES
    assert contract.retry_calls == 0
    assert contract.transport_policy == (
        CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
    )
    assert contract.connection_configuration_source == (
        "openwebui_admin_connection_configuration_only"
    )
    assert contract.integrity_hash == hashlib.sha256(
        contract.canonical_json_bytes()
    ).hexdigest()
    assert len(contract.integrity_hash) == 64
    assert "api_key" not in json.dumps(snapshot, sort_keys=True)
    assert "secret" not in json.dumps(snapshot, sort_keys=True)
    assert gate2_provider_profile(profile_id).transport_type != (
        contract.actual_transport_type
    )


def test_goal12_execution_metadata_binds_direct_transport_contract():
    adapter = _adapter("openai_gpt")
    model_id = "gpt-5.4-nano-2026-03-17"
    prepared_request = adapter.prepare_context_v2_1_budget_smoke_form_data(
        form_data=_budget_authorized_form_data(model_id, "out-of-band"),
        response_format=_response_format(),
    )
    contract = adapter.context_v2_1_budget_smoke_transport_contract(
        transport_policy=CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    )
    payload = {
        "id": "provider-response",
        "model": model_id,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": "{}"},
            }
        ],
    }

    metadata = adapter.context_v2_1_budget_smoke_execution_metadata(
        payload=payload,
        requested_model_id=model_id,
        duration_ms=5,
        prepared_request=prepared_request,
        transport_contract=contract,
    )

    assert metadata.transport_type == "direct_provider_http"
    assert metadata.resolved_model_id == model_id
    with pytest.raises(Gate2SourceFactRuntimeError) as mismatch:
        adapter.context_v2_1_budget_smoke_execution_metadata(
            payload=payload,
            requested_model_id=model_id,
            duration_ms=5,
            prepared_request=prepared_request,
            transport_contract=replace(contract, retry_calls=1),
        )
    assert mismatch.value.code == "gate2_model_transport_contract_mismatch"


@pytest.mark.parametrize(
    "profile_id,_model_id,base_url,endpoint,_headers",
    PROVIDER_CASES,
)
def test_goal12_direct_http_posts_exact_body_once_without_redirect_handler(
    profile_id,
    _model_id,
    base_url,
    endpoint,
    _headers,
):
    response = _FakeResponse(b'{"terminal":true}')
    opener = _FakeOpener(response=response)
    adapter = _adapter(
        profile_id,
        provider_connection_resolver=_connection_resolver(base_url),
    )
    form_data = _wire_form_data(profile_id, _model_id)

    with patch(
        "broker_reports_gate1.gate2_provider_adapters.build_opener",
        return_value=opener,
    ) as build:
        result = asyncio.run(
            adapter.invoke_context_v2_1_budget_smoke_once(
                form_data=form_data,
                transport_policy=(
                    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
                ),
            )
        )

    assert result == {"terminal": True}
    assert len(opener.calls) == 1
    request, timeout = opener.calls[0]
    assert request.full_url == endpoint
    assert request.get_method() == "POST"
    assert json.loads(request.data.decode("utf-8")) == form_data
    assert timeout == 180
    assert response.read_limits == [MAX_NATIVE_PROVIDER_RESPONSE_BYTES + 1]
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["content-type"] == "application/json"
    if profile_id == "anthropic_claude":
        assert headers["x-api-key"] == "unit-secret"
        assert headers["anthropic-version"] == "2023-06-01"
    else:
        assert headers["authorization"] == "Bearer unit-secret"
    assert build.call_count == 1
    proxy_handler, redirect_handler = build.call_args.args
    assert proxy_handler.proxies == {}
    assert (
        redirect_handler.redirect_request(
            None,
            None,
            302,
            "redirect",
            {},
            "https://attacker.invalid",
        )
        is None
    )


@pytest.mark.parametrize(
    "profile_id,model_id,base_url,_endpoint,_headers",
    PROVIDER_CASES,
)
def test_goal12_success_response_is_capped_before_json_decode(
    profile_id,
    model_id,
    base_url,
    _endpoint,
    _headers,
):
    response = _FakeResponse(
        b"x" * (MAX_NATIVE_PROVIDER_RESPONSE_BYTES + 1)
    )
    opener = _FakeOpener(response=response)
    adapter = _adapter(
        profile_id,
        provider_connection_resolver=_connection_resolver(base_url),
    )

    with patch(
        "broker_reports_gate1.gate2_provider_adapters.build_opener",
        return_value=opener,
    ):
        with pytest.raises(Gate2SourceFactRuntimeError) as exceeded:
            asyncio.run(
                adapter.invoke_context_v2_1_budget_smoke_once(
                    form_data=_wire_form_data(profile_id, model_id),
                    transport_policy=(
                        CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
                    ),
                )
            )

    assert exceeded.value.code == "gate2_model_response_budget_exceeded"
    assert exceeded.value.failure_class == "response_budget"
    assert len(opener.calls) == 1


@pytest.mark.parametrize(
    "body",
    (
        b"not-json",
        b'{"model":"first","model":"second"}',
        b'{"usage":{"input_tokens":NaN}}',
        b'{"usage":{"input_tokens":1e10000}}',
        b'{"value":"\\ud800"}',
        b"[]",
    ),
)
def test_goal12_success_invalid_or_duplicate_json_fails_closed(body):
    response = _FakeResponse(body)
    opener = _FakeOpener(response=response)
    adapter = _adapter(
        "openai_gpt",
        provider_connection_resolver=_connection_resolver(
            "https://api.openai.com/v1"
        ),
    )

    with patch(
        "broker_reports_gate1.gate2_provider_adapters.build_opener",
        return_value=opener,
    ):
        with pytest.raises(Gate2SourceFactRuntimeError) as invalid:
            asyncio.run(
                adapter.invoke_context_v2_1_budget_smoke_once(
                    form_data=_wire_form_data(
                        "openai_gpt",
                        "gpt-5.4-nano-2026-03-17",
                    ),
                    transport_policy=(
                        CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
                    ),
                )
            )

    assert invalid.value.code == "gate2_model_invalid_response"
    assert invalid.value.failure_class == "provider_response_invalid"
    assert invalid.value.raw_output == {
        "body_length": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
    }


@pytest.mark.parametrize(
    "content",
    (
        '{"broker_reports_gate2_choice":{"choice":NaN}}',
        '{"broker_reports_gate2_choice":{"choice":1e10000}}',
        '{"broker_reports_gate2_choice":{"choice":"\\ud800"}}',
    ),
)
def test_goal12_openai_inner_content_rejects_non_i_json(
    content,
) -> None:
    with pytest.raises(Gate2SourceFactRuntimeError) as invalid:
        _extract_openai_content(
            content,
            envelope_required=True,
            require_i_json=True,
        )

    assert invalid.value.code == "gate2_model_invalid_response"
    assert invalid.value.failure_class == "provider_response_invalid"
    assert isinstance(
        _extract_openai_content(
            content,
            envelope_required=True,
            require_i_json=False,
        ),
        dict,
    )


@pytest.mark.parametrize("status_code", (302, 401, 403, 429, 502))
def test_goal12_non_2xx_non_json_is_infrastructure_failure_without_follow(
    status_code,
):
    body = f"non-json-http-{status_code}".encode("ascii")
    error = HTTPError(
        "https://api.openai.com/v1/chat/completions",
        status_code,
        "provider error",
        {"location": "https://attacker.invalid"},
        BytesIO(body),
    )
    opener = _FakeOpener(error=error)
    adapter = _adapter(
        "openai_gpt",
        provider_connection_resolver=_connection_resolver(
            "https://api.openai.com/v1",
            "credential-must-not-forward",
        ),
    )

    with patch(
        "broker_reports_gate1.gate2_provider_adapters.build_opener",
        return_value=opener,
    ) as build:
        with pytest.raises(Gate2SourceFactRuntimeError) as failed:
            asyncio.run(
                adapter.invoke_context_v2_1_budget_smoke_once(
                    form_data=_wire_form_data(
                        "openai_gpt",
                        "gpt-5.4-nano-2026-03-17",
                    ),
                    transport_policy=(
                        CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
                    ),
                )
            )

    expected_code = (
        "gate2_model_provider_redirect_blocked"
        if 300 <= status_code < 400
        else "gate2_model_provider_http_error"
    )
    assert failed.value.code == expected_code
    assert failed.value.failure_class == "provider_transport"
    assert failed.value.provider_response_received is True
    assert failed.value.raw_output == {
        "status_code": status_code,
        "body_length": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_truncated": False,
    }
    assert len(opener.calls) == 1
    assert build.call_count == 1
    assert "attacker.invalid" not in repr(failed.value.raw_output)
    assert "credential-must-not-forward" not in repr(
        failed.value.raw_output
    )


@pytest.mark.parametrize(
    "hostile_url",
    (
        "http://api.openai.com/v1",
        "https://api.openai.com.evil.invalid/v1",
        "https://user@api.openai.com/v1",
        "https://api.openai.com:443/v1",
        "https://api.openai.com:444/v1",
        "HTTPS://API.OPENAI.COM/v1",
        "https://api.openai.com/v1?target=evil",
        "https://api.openai.com/v1#fragment",
        "https://api.openai.com/v1/chat/completions",
        "https://api.openai.com/%76%31",
    ),
)
def test_goal12_connection_validation_rejects_hostile_origins(hostile_url):
    adapter = _adapter(
        "openai_gpt",
        provider_connection_resolver=_connection_resolver(hostile_url),
    )

    with pytest.raises(Gate2SourceFactRuntimeError) as blocked:
        adapter.validate_context_v2_1_budget_smoke_transport_configuration(
            transport_policy=CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
        )

    assert blocked.value.code == "gate2_provider_configuration_blocked"
    assert blocked.value.failure_class == "provider_configuration"


@pytest.mark.parametrize(
    "profile_id,_model_id,base_url,_endpoint,_headers",
    PROVIDER_CASES,
)
def test_openwebui_connection_resolver_accepts_only_canonical_provider_base(
    profile_id,
    _model_id,
    base_url,
    _endpoint,
    _headers,
):
    config = SimpleNamespace(
        OPENAI_API_BASE_URLS=[f"{base_url}/"],
        OPENAI_API_KEYS=["unit-secret"],
        OPENAI_API_CONFIGS={"0": {"enable": True}},
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(config=config),
        )
    )

    connection = (
        Gate2OpenWebUIProviderConnectionResolver(request)
        .resolve_context_v2_1_budget_smoke(
            gate2_provider_profile(profile_id)
        )
    )

    assert connection.base_url == base_url
    assert connection.api_key == "unit-secret"
    assert "unit-secret" not in repr(connection)


@pytest.mark.parametrize(
    "configured_base",
    (
        " https://api.openai.com/v1",
        "https://api.openai.com/v1 ",
        "https://api.openai.com/v1//",
    ),
)
def test_goal12_connection_resolver_does_not_silently_normalize_base(
    configured_base,
):
    config = SimpleNamespace(
        OPENAI_API_BASE_URLS=[configured_base],
        OPENAI_API_KEYS=["unit-secret"],
        OPENAI_API_CONFIGS={"0": {"enable": True}},
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(config=config),
        )
    )

    with pytest.raises(Gate2SourceFactRuntimeError) as blocked:
        (
            Gate2OpenWebUIProviderConnectionResolver(request)
            .resolve_context_v2_1_budget_smoke(
                gate2_provider_profile("openai_gpt")
            )
        )

    assert blocked.value.code == "gate2_provider_configuration_blocked"


def test_non_goal12_connection_resolution_preserves_existing_prefix_semantics():
    custom_base_url = "https://api.anthropic.com/v1/custom-proxy"
    config = SimpleNamespace(
        OPENAI_API_BASE_URLS=[custom_base_url],
        OPENAI_API_KEYS=["unit-secret"],
        OPENAI_API_CONFIGS={"0": {"enable": True}},
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(config=config),
        )
    )
    resolver = Gate2OpenWebUIProviderConnectionResolver(request)
    connection = resolver.resolve(
        gate2_provider_profile("anthropic_claude")
    )
    adapter = _adapter(
        "anthropic_claude",
        provider_connection_resolver=resolver.resolve,
    )

    adapter.validate_transport_configuration()

    assert connection.base_url == custom_base_url
    assert adapter._resolve_provider_connection().base_url == custom_base_url
    with pytest.raises(Gate2SourceFactRuntimeError) as blocked:
        adapter.validate_context_v2_1_budget_smoke_transport_configuration(
            transport_policy=CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
        )
    assert blocked.value.code == "gate2_provider_configuration_blocked"


def test_goal12_transport_configuration_fails_before_any_boundary():
    calls = []
    invalid_timeout = _adapter(
        "openai_gpt",
        native_transport_resolver=lambda profile, form: calls.append(
            (profile, form)
        ),
        transport_config=Gate2NativeProviderTransportConfig(
            timeout_seconds=0
        ),
    )

    with pytest.raises(Gate2SourceFactRuntimeError) as timeout:
        invalid_timeout.invoke_context_v2_1_budget_smoke_once(
            form_data=_wire_form_data(
                "openai_gpt",
                "gpt-5.4-nano-2026-03-17",
            ),
            transport_policy=CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
        )
    assert timeout.value.code == "gate2_provider_configuration_blocked"
    assert calls == []

    no_connection = _adapter("openai_gpt")
    with pytest.raises(Gate2SourceFactRuntimeError) as connection:
        no_connection.invoke_context_v2_1_budget_smoke_once(
            form_data=_wire_form_data(
                "openai_gpt",
                "gpt-5.4-nano-2026-03-17",
            ),
            transport_policy=CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
        )
    assert connection.value.code == "gate2_provider_configuration_blocked"

    invalid_anthropic_version = _adapter(
        "anthropic_claude",
        native_transport_resolver=lambda profile, form: calls.append(
            (profile, form)
        ),
        transport_config=Gate2NativeProviderTransportConfig(
            anthropic_api_version="2024-01-01"
        ),
    )
    with pytest.raises(Gate2SourceFactRuntimeError) as version:
        invalid_anthropic_version.invoke_context_v2_1_budget_smoke_once(
            form_data=_wire_form_data(
                "anthropic_claude",
                "claude-haiku-4-5-20251001",
            ),
            transport_policy=CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
        )
    assert version.value.code == "gate2_provider_configuration_blocked"
    assert calls == []
