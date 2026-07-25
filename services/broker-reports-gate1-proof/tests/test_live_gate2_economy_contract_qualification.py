from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from live_gate2_economy_contract_qualification import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    _dry_build,
    _qualification_authorizations,
    _receipt_cost_total,
    _safe_error,
    build_checksum_qualification_fixture,
    build_financial_qualification_cases,
)
from broker_reports_gate1.gate2_financial_context_checksum import (  # noqa: E402
    Gate2FinancialContextChecksumComparatorFactory,
    safe_checksum_receipt,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_shadow_qualification import (  # noqa: E402
    Gate2FinancialEvidenceShadowDecisionRunnerFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
)


MODULE_PATH = SCRIPT_DIR / "live_gate2_economy_contract_qualification.py"


class _FakeClient:
    async def extract(self, **_kwargs):
        return Gate2StructuredModelResult(content={})


def test_financial_fixture_covers_exactly_four_canonical_dispositions() -> None:
    cases = build_financial_qualification_cases()

    assert [item.case_id for item in cases] == [
        "typed",
        "unclassified",
        "no_financial",
        "unsupported",
    ]
    assert {item.expected_disposition for item in cases} == {
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }
    assert all(item.source_package.source_values for item in cases)
    assert all(
        item.contract.canonical_schema()["additionalProperties"] is False
        for item in cases
    )


def test_checksum_fixture_seals_three_metrics_and_comparator_passes() -> None:
    contract, expected = build_checksum_qualification_fixture()
    rows = [
        {
            "metric_id": item.metric_id,
            "source_label": item.source_label,
            "value": item.normalized_value,
            "currency": item.currency,
            "unit": item.unit,
            "sign": item.sign,
            "period": item.period_literals[0],
            "context_entry_id": item.context_entry_id,
            "source_scope_ref": item.source_scope_ref,
            "source_value_ref": item.source_value_ref,
            "page_ref": item.page_ref,
        }
        for item in expected
    ]

    private = Gate2FinancialContextChecksumComparatorFactory().create(
        contract=contract,
        expected_metrics=expected,
        answer_rows=rows,
    )
    safe = safe_checksum_receipt(private)

    assert private["status"] == "passed"
    assert safe["metrics_passed_total"] == 3
    assert safe["metric_check_failure_counts"] == {}
    assert "private_metric_results" not in safe


@pytest.mark.parametrize(
    ("model_id", "provider_profile_id"),
    (
        ("gpt-5.4-nano-2026-03-17", "openai_gpt"),
        ("models/gemini-3.1-flash-lite", "google_gemini"),
        ("models/gemini-3.5-flash-lite", "google_gemini"),
    ),
)
def test_financial_candidates_pass_schema_only_dry_build(
    model_id: str,
    provider_profile_id: str,
) -> None:
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    runner = Gate2FinancialEvidenceShadowDecisionRunnerFactory(
        registry=registry,
        model_client=_FakeClient(),
        model_id=model_id,
        provider_profile_id=provider_profile_id,
    ).create()
    for case in build_financial_qualification_cases():
        receipt = _dry_build(
            request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE,
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            prompt=runner.prompt,
            package=runner.model_package(
                case.contract,
                case.source_package,
            ),
            response_format=case.contract.openai_response_format(),
        )
        assert receipt["status"] == "passed"
        assert receipt["estimated_input_tokens"] <= 3_072
        assert receipt["maximum_output_tokens"] == 640


@pytest.mark.parametrize(
    ("model_id", "provider_profile_id"),
    (
        ("claude-haiku-4-5-20251001", "anthropic_claude"),
        ("gpt-5.4-nano-2026-03-17", "openai_gpt"),
        ("models/gemini-3.1-flash-lite", "google_gemini"),
        ("models/gemini-3.5-flash-lite", "google_gemini"),
    ),
)
def test_checksum_candidates_pass_schema_only_dry_build(
    model_id: str,
    provider_profile_id: str,
) -> None:
    checksum, _ = build_checksum_qualification_fixture()
    receipt = _dry_build(
        request_profile=FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
        provider_profile_id=provider_profile_id,
        model_id=model_id,
        prompt=type(
            "Prompt",
            (),
            {
                "content": ("{{financial_context_checksum_package_json}}"),
                "prompt_ref": "code:test-checksum",
                "hash": "a" * 64,
            },
        )(),
        package=checksum.model_package(),
        response_format=checksum.openai_response_format(),
    )
    assert receipt["estimated_input_tokens"] <= 130_000
    assert receipt["maximum_output_tokens"] == 1_024


def test_safe_failure_and_cost_helpers_never_project_raw_output() -> None:
    error = Gate2SourceFactRuntimeError(
        "typed_failure",
        "private provider message",
        raw_output={"private": "must-not-project"},
    )

    safe = _safe_error(error)
    total = _receipt_cost_total(
        {
            "one": {
                "schema_version": ("broker_reports_gate2_economy_budget_v1"),
                "actual_cost_usd": "0.000100000",
            },
            "two": {
                "schema_version": ("broker_reports_gate2_economy_budget_v1"),
                "actual_cost_usd": "0.000200000",
            },
        }
    )

    assert safe == {
        "failure_code": "typed_failure",
        "failure_class": "Gate2SourceFactRuntimeError",
    }
    assert "must-not-project" not in str(safe)
    assert total == "0.000300000"


def test_live_harness_requires_exact_workload_policy_authorization() -> None:
    receipts = _qualification_authorizations(
        model_id="gpt-5.4-nano-2026-03-17",
        provider_profile_id="openai_gpt",
        workload_contracts=(
            (
                "gate2_financial_evidence",
                "broker_reports_gate2_financial_evidence_decision_v1",
            ),
        ),
    )

    assert len(receipts) == 1
    assert receipts[0]["workload_class"] == ("gate2_financial_evidence")
    assert receipts[0]["exact_model_id"] == ("gpt-5.4-nano-2026-03-17")
    assert receipts[0]["fallback_calls_allowed"] == 0
    assert receipts[0]["repair_attempts_allowed"] == 0
    assert set(receipts[0]["receipt_identity"]) == {
        "provider_route_revision",
        "input_contract_version",
        "output_contract_version",
        "prompt_version",
        "adapter_projection_revision",
        "canonical_validator_revision",
    }


def test_live_harness_rejects_alias_before_provider_call() -> None:
    with pytest.raises(ValueError):
        _qualification_authorizations(
            model_id="gpt-5.4-nano",
            provider_profile_id="openai_gpt",
            workload_contracts=(
                (
                    "gate2_financial_evidence",
                    "broker_reports_gate2_financial_evidence_decision_v1",
                ),
            ),
        )


def test_live_harness_is_factory_backed_and_has_no_vendor_sdk_bypass() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "only live model execution entrypoints" in FACTORY_REQUIRED
    assert "must not use customer data" in FORBIDDEN
    assert "Gate2StructuredModelClientFactory" in source
    assert "Gate2FinancialEvidenceShadowDecisionRunnerFactory" in source
    assert "Gate2FinancialContextChecksumRunnerFactory" in source
    assert not any(
        name.startswith(("openai", "anthropic", "google.generativeai"))
        for name in imported
    )
    assert "api.anthropic.com" not in source
