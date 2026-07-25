from __future__ import annotations

import ast
import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from live_gate2_source_economy_qualification import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    PROVIDER_PROFILE_ID,
    SOURCE_QUALIFICATION_OUTPUT_SCHEMA_VERSION,
    SOURCE_QUALIFICATION_REQUEST_PROFILE,
    build_source_qualification_fixture,
    parse_source_qualification_output,
    qualify_source_model,
    source_qualification_contract_identity,
)
from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    Gate2OpenWebUIRequestBuilder,
)


MODULE_PATH = SCRIPT_DIR / "live_gate2_source_economy_qualification.py"
GEMINI_MODEL = "models/gemini-3.1-flash-lite"


class _FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    async def extract(self, **_kwargs):
        self.calls += 1
        profile = gate2_provider_profile(PROVIDER_PROFILE_ID)
        return Gate2StructuredModelResult(
            content=copy.deepcopy(self.content),
            fallback_used=False,
            repair_attempt_count=0,
            execution_metadata=Gate2ProviderExecutionMetadata(
                provider_id="google",
                provider_profile_id=PROVIDER_PROFILE_ID,
                provider_profile_revision=(gate2_provider_profile_revision(profile)),
                adapter_id=profile.adapter_id,
                adapter_version=profile.adapter_version,
                requested_model_id=GEMINI_MODEL,
                resolved_model_id=GEMINI_MODEL,
                structured_output_mode=("openwebui_response_format_json_schema"),
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
                canonical_request_schema_hash="a" * 64,
                adapted_request_schema_hash="b" * 64,
                schema_transform_count=2,
                duration_ms=10,
                input_tokens=400,
                output_tokens=120,
                total_tokens=520,
                reasoning_tokens=20,
                finish_reason="stop",
            ),
            economy_budget_receipt={
                "schema_version": ("broker_reports_gate2_economy_budget_v1"),
                "status": "passed",
                "input_tokens": 400,
                "output_tokens": 120,
                "actual_cost_usd": "0.000280000",
            },
        )


def _expected_root():
    fixture = build_source_qualification_fixture()
    return {
        str(case["case_id"]): copy.deepcopy(case["expected_output"])
        for case in fixture.cases
    }


def test_fixture_is_frozen_source_only_and_does_not_send_expected_output() -> None:
    fixture = build_source_qualification_fixture()
    rendered = json.dumps(
        fixture.package,
        ensure_ascii=False,
        sort_keys=True,
    )

    assert len(fixture.cases) == 5
    assert all(case["workload"] == "gate2_source" for case in fixture.cases)
    assert len(fixture.manifest_hash) == 64
    assert fixture.package["llm_context_package"]["contains_customer_data"] is False
    assert "expected_output" not in rendered
    assert "allowed_literal_values" not in rendered
    assert all(
        case["source_ref"].startswith("syn:")
        for case in fixture.package["llm_context_package"]["cases"]
    )


def test_request_profile_is_strict_synthetic_and_budget_controlled() -> None:
    fixture = build_source_qualification_fixture()
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=SOURCE_QUALIFICATION_REQUEST_PROFILE
    ).build(
        prompt=fixture.prompt,
        package=fixture.package,
        model_id=GEMINI_MODEL,
        response_format=fixture.response_format,
    )
    authorization = (
        Gate2EconomyBudgetSessionFactory()
        .create(request_profile=SOURCE_QUALIFICATION_REQUEST_PROFILE)
        .prepare_call(
            form_data=form_data,
            model_id=GEMINI_MODEL,
            provider_profile_id=PROVIDER_PROFILE_ID,
            operation_identity="source-qualification-test",
        )
    )

    assert form_data["stream"] is False
    assert form_data["response_format"]["type"] == "json_schema"
    assert form_data["metadata"]["broker_reports_gate2"]["source_qualification"] is True
    assert (
        form_data["metadata"]["broker_reports_gate2"]["synthetic_non_customer"] is True
    )
    assert (
        "qualify_broker_reports_source_secretary_v1"
        in (form_data["messages"][1]["content"])
    )
    assert (
        "extract_broker_reports_source_facts_v0"
        not in (form_data["messages"][1]["content"])
    )
    assert authorization.prepared_form_data["reasoning_effort"] == "minimal"
    assert authorization.prepared_form_data["max_tokens"] == 4096
    assert "tools" not in authorization.prepared_form_data


def test_output_parser_rejects_trailing_prose_and_extra_cases() -> None:
    case_ids = tuple(_expected_root())

    with pytest.raises(
        ValueError,
        match="source_qualification_strict_json_required",
    ):
        parse_source_qualification_output(
            json.dumps(_expected_root()) + "\nDone.",
            case_ids=case_ids,
        )

    extra = _expected_root()
    extra["invented"] = {}
    with pytest.raises(
        ValueError,
        match="source_qualification_output_shape_invalid",
    ):
        parse_source_qualification_output(
            extra,
            case_ids=case_ids,
        )


def test_terminal_qualification_uses_one_call_and_safe_comparator() -> None:
    fixture = build_source_qualification_fixture()
    client = _FakeClient(_expected_root())

    result = asyncio.run(
        qualify_source_model(
            model_client=client,
            model_id=GEMINI_MODEL,
            fixture=fixture,
        )
    )

    assert client.calls == 1
    assert result["status"] == "passed"
    assert all(result["checks"].values())
    assert result["benchmark_safe_report"]["passed_case_count"] == 5
    assert result["benchmark_safe_report"]["failure_counts"] == {}
    assert (
        result["benchmark_safe_report"]["aggregate_metrics"]["invented_value_count"]
        == 0
    )
    assert result["raw_provider_output_included"] is False
    assert "expected_output" not in json.dumps(result)


def test_contract_identity_uses_current_provider_and_comparator_revisions() -> None:
    fixture = build_source_qualification_fixture()
    identity = source_qualification_contract_identity(
        manifest_hash=fixture.manifest_hash
    )
    values = identity.to_dict()

    assert values["provider_route_revision"] == (
        gate2_provider_profile_revision(gate2_provider_profile(PROVIDER_PROFILE_ID))
    )
    assert fixture.manifest_hash in values["input_contract_version"]
    assert values["output_contract_version"] == (
        SOURCE_QUALIFICATION_OUTPUT_SCHEMA_VERSION
    )
    assert "pending_stage_delivery" not in json.dumps(values)
    assert all(values.values())


def test_harness_is_factory_backed_and_has_no_vendor_sdk_bypass() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "only source qualification" in FACTORY_REQUIRED
    assert "must not use customer data" in FORBIDDEN
    assert "Gate2EconomyQualificationPolicyFactory" in source
    assert "_model_client" in source
    assert "compare_secretary_response" in source
    assert not any(
        name.startswith(("openai", "anthropic", "google.generativeai"))
        for name in imported
    )
    assert "api.anthropic.com" not in source
