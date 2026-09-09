from __future__ import annotations

from types import SimpleNamespace

import pytest

from broker_reports_gate1.gate2_model_contracts import (
    Gate2SourceFactRuntimeError,
    require_strict_json_schema_response,
)


_ERROR_CODE = "ordinary_trade_mapping_strict_output_required"
_ERROR_MESSAGE = "Semantic mapping requires one strict output without repair"


def _strict_response(**overrides):
    response = {
        "structured_output_mode": "openwebui_response_format_json_schema",
        "response_format_type": "json_schema",
        "response_format_schema_mode": "strict_json_schema",
        "fallback_used": False,
        "repair_attempt_count": 0,
        "execution_metadata": {"provider": "test"},
    }
    response.update(overrides)
    return SimpleNamespace(**response)


def test_strict_mapping_response_contract_accepts_one_unrepaired_json_schema_response():
    assert require_strict_json_schema_response(
        _strict_response(),
        error_code=_ERROR_CODE,
        error_message=_ERROR_MESSAGE,
    ) is None


@pytest.mark.parametrize(
    "response",
    [
        None,
        _strict_response(
            structured_output_mode="openwebui_anthropic_output_config_json_schema"
        ),
        _strict_response(response_format_type="json_object"),
        _strict_response(fallback_used=True),
        _strict_response(repair_attempt_count=1),
        _strict_response(response_format_schema_mode="json_object"),
        _strict_response(execution_metadata=None),
    ],
)
def test_strict_mapping_response_contract_rejects_non_strict_provider_results(response):
    with pytest.raises(Gate2SourceFactRuntimeError) as rejected:
        require_strict_json_schema_response(
            response,
            error_code=_ERROR_CODE,
            error_message=_ERROR_MESSAGE,
        )

    assert rejected.value.code == _ERROR_CODE
    assert rejected.value.message == _ERROR_MESSAGE
