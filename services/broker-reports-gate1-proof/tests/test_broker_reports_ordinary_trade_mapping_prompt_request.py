from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from broker_reports_gate1.gate2_model_contracts import Gate2SourceFactRuntimeError
from broker_reports_gate1.gate2_model_requests import (
    ORDINARY_TRADE_MAPPING_ANSWER_REQUEST_PROFILE,
    ORDINARY_TRADE_MAPPING_PACKAGE_MARKER,
    ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.ordinary_trade_mapping_prompt import PROMPT_PLACEHOLDER


def _response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ordinary_trade_mapping_test",
            "strict": True,
            "schema": {"type": "object"},
        },
    }


def _prompt(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        prompt_ref="prompt-ordinary-trade",
        hash="a" * 64,
    )


def _mapping_package() -> dict:
    return {
        "phase": "map",
        "case": {"private_marker": "canonical-private-data"},
    }


def test_request_transport_marker_is_pinned_to_workspace_prompt_contract() -> None:
    assert ORDINARY_TRADE_MAPPING_PACKAGE_MARKER == PROMPT_PLACEHOLDER


def test_mapping_request_expands_exact_marker_once_without_user_package_copy() -> None:
    package = _mapping_package()
    request = Gate2OpenWebUIRequestBuilder(
        request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE
    ).build(
        prompt=_prompt(f"Instruction: {PROMPT_PLACEHOLDER}"),
        package=package,
        model_id="models/gemini-3.5-flash",
        response_format=_response_format(),
    )

    system_content = request["messages"][0]["content"]
    assert PROMPT_PLACEHOLDER not in json.dumps(request, ensure_ascii=False)
    assert json.dumps(
        package, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) in system_content
    assert json.loads(request["messages"][1]["content"]) == {
        "input": "embedded_in_system_prompt",
        "task": "map_ordinary_trade_semantic_roles",
    }


@pytest.mark.parametrize(
    "content",
    ["Instruction without a package marker", f"{PROMPT_PLACEHOLDER} {PROMPT_PLACEHOLDER}"],
)
def test_mapping_request_rejects_missing_or_duplicate_marker(content: str) -> None:
    with pytest.raises(Gate2SourceFactRuntimeError) as raised:
        Gate2OpenWebUIRequestBuilder(
            request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE
        ).build(
            prompt=_prompt(content),
            package=_mapping_package(),
            model_id="models/gemini-3.5-flash",
            response_format=_response_format(),
        )

    assert raised.value.code == "ordinary_trade_semantic_mapping_prompt_contract_mismatch"


def test_mapping_request_rejects_reserved_marker_in_untrusted_package() -> None:
    package = _mapping_package()
    package["case"]["untrusted_literal"] = PROMPT_PLACEHOLDER

    with pytest.raises(Gate2SourceFactRuntimeError) as raised:
        Gate2OpenWebUIRequestBuilder(
            request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE
        ).build(
            prompt=_prompt(f"Instruction: {PROMPT_PLACEHOLDER}"),
            package=package,
            model_id="models/gemini-3.5-flash",
            response_format=_response_format(),
        )

    assert raised.value.code == "ordinary_trade_semantic_mapping_prompt_contract_mismatch"


def test_answer_request_does_not_require_or_expand_mapping_marker() -> None:
    package = {"phase": "interpret_answer", "case": {"answer": "да"}}
    request = Gate2OpenWebUIRequestBuilder(
        request_profile=ORDINARY_TRADE_MAPPING_ANSWER_REQUEST_PROFILE
    ).build(
        prompt=_prompt("Interpret one answer."),
        package=package,
        model_id="models/gemini-3.5-flash",
        response_format=_response_format(),
    )

    assert request["messages"][0]["content"] == "Interpret one answer."
    assert json.loads(request["messages"][1]["content"]) == package
