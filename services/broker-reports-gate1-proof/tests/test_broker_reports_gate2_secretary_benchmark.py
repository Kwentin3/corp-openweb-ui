from __future__ import annotations

import copy
import json

import pytest

from broker_reports_gate1.gate2_secretary_benchmark import (
    FAILURE_DUPLICATE_BINDING,
    FAILURE_EXPECTED_VALUE,
    FAILURE_INVENTED_VALUE,
    FAILURE_INVALID_JSON,
    FAILURE_LITERAL_COPY,
    FAILURE_PROVIDER_REFUSAL,
    FAILURE_PROVIDER_SCHEMA_REJECTED,
    FAILURE_PROVIDER_TRUNCATION,
    FAILURE_SCHEMA_SHAPE,
    FAILURE_SOURCE_BINDING,
    MANIFEST_SCHEMA_VERSION,
    compare_secretary_response,
    load_secretary_benchmark_manifest,
    render_safe_benchmark_report,
)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return load_secretary_benchmark_manifest()


def _case(manifest: dict, case_id: str) -> dict:
    return next(case for case in manifest["cases"] if case["case_id"] == case_id)


def test_manifest_is_frozen_synthetic_and_covers_every_family(manifest: dict) -> None:
    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["contains_customer_data"] is False
    assert manifest["frozen"] is True
    assert len(manifest["cases"]) == manifest["case_count"] == 17
    assert {case["family"] for case in manifest["cases"]} == set(
        manifest["families"]
    )
    assert {case["workload"] for case in manifest["cases"]} == {
        "gate2_source",
        "gate2_domain",
        "gate2_financial_evidence",
        "gate2_financial_checksum",
    }


def test_sealed_expected_outputs_all_pass_the_deterministic_comparator(
    manifest: dict,
) -> None:
    results = [
        compare_secretary_response(case, copy.deepcopy(case["expected_output"]))
        for case in manifest["cases"]
    ]

    assert all(result.passed for result in results)
    assert all(result.failure_codes == () for result in results)


def test_literal_sign_and_decimal_precision_are_terminal_failures(
    manifest: dict,
) -> None:
    case = _case(manifest, "syn_literal_negative_decimal")
    candidate = copy.deepcopy(case["expected_output"])
    candidate["literal_value"] = "123.45"

    result = compare_secretary_response(case, candidate)

    assert result.passed is False
    assert FAILURE_LITERAL_COPY in result.failure_codes
    assert FAILURE_EXPECTED_VALUE in result.failure_codes
    assert FAILURE_INVENTED_VALUE in result.failure_codes


def test_wrong_equal_value_binding_is_detected(manifest: dict) -> None:
    case = _case(manifest, "syn_source_binding_equal_values")
    candidate = copy.deepcopy(case["expected_output"])
    candidate["selected_bindings"][0]["candidate_id"] = "syn_candidate_left"

    result = compare_secretary_response(case, candidate)

    assert result.passed is False
    assert FAILURE_SOURCE_BINDING in result.failure_codes
    assert FAILURE_INVENTED_VALUE in result.failure_codes


def test_duplicate_financial_binding_is_detected(manifest: dict) -> None:
    case = _case(manifest, "syn_financial_typed")
    candidate = copy.deepcopy(case["expected_output"])
    candidate["bindings"].append(copy.deepcopy(candidate["bindings"][0]))

    result = compare_secretary_response(case, candidate)

    assert result.passed is False
    assert FAILURE_DUPLICATE_BINDING in result.failure_codes
    assert FAILURE_SCHEMA_SHAPE in result.failure_codes


def test_extra_root_field_is_not_accepted_as_harmless_json(manifest: dict) -> None:
    case = _case(manifest, "syn_structured_exact_root")
    candidate = copy.deepcopy(case["expected_output"])
    candidate["commentary"] = "looks good"

    result = compare_secretary_response(case, candidate)

    assert result.passed is False
    assert FAILURE_SCHEMA_SHAPE in result.failure_codes
    assert FAILURE_INVENTED_VALUE in result.failure_codes


def test_transport_terminal_outcomes_are_preserved(manifest: dict) -> None:
    case = _case(manifest, "syn_checksum_exact")

    invalid = compare_secretary_response(case, '{"status":')
    refused = compare_secretary_response(
        case, case["expected_output"], provider_refused=True
    )
    truncated = compare_secretary_response(
        case, case["expected_output"], provider_truncated=True
    )
    rejected = compare_secretary_response(
        case, case["expected_output"], provider_schema_accepted=False
    )

    assert FAILURE_INVALID_JSON in invalid.failure_codes
    assert FAILURE_PROVIDER_REFUSAL in refused.failure_codes
    assert FAILURE_PROVIDER_TRUNCATION in truncated.failure_codes
    assert FAILURE_PROVIDER_SCHEMA_REJECTED in rejected.failure_codes
    assert not invalid.passed
    assert not refused.passed
    assert not truncated.passed
    assert not rejected.passed


def test_safe_report_is_deterministic_and_contains_no_raw_output(
    manifest: dict,
) -> None:
    results = [
        compare_secretary_response(case, json.dumps(case["expected_output"]))
        for case in reversed(manifest["cases"])
    ]

    first = render_safe_benchmark_report(
        benchmark_id=manifest["benchmark_id"],
        model_id="exact-model-id",
        provider_route="existing-provider-route",
        contract_version="contract-v1",
        results=results,
    )
    second = render_safe_benchmark_report(
        benchmark_id=manifest["benchmark_id"],
        model_id="exact-model-id",
        provider_route="existing-provider-route",
        contract_version="contract-v1",
        results=reversed(results),
    )

    assert first == second
    assert first["status"] == "passed"
    assert first["passed_case_count"] == manifest["case_count"]
    assert first["raw_provider_output_included"] is False
    assert first["customer_data_included"] is False
    assert first["aggregate_metrics"]["provider_schema_acceptance_rate"] == 1.0
    assert first["aggregate_metrics"]["canonical_acceptance_rate"] == 1.0
    assert first["aggregate_metrics"]["exact_value_accuracy"] == 1.0
    assert first["aggregate_metrics"]["source_binding_accuracy"] == 1.0
    assert first["aggregate_metrics"]["correct_disposition_rate"] == 1.0
    assert first["aggregate_metrics"]["latency_ms_total"] is None
    assert first["aggregate_metrics"]["input_tokens_total"] is None
    assert "expected_output" not in json.dumps(first)
    assert [item["case_id"] for item in first["cases"]] == sorted(
        item["case_id"] for item in first["cases"]
    )
