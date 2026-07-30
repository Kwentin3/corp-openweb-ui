from __future__ import annotations

import ast
import copy
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

import pytest

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (
    Gate2FinancialSemanticV6DecisionEvidenceError,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2SourceFactRuntimeError,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

import build_type_first_zero_call_e2e_evidence as E2E  # noqa: E402


@pytest.fixture(scope="module")
def e2e_result() -> dict[str, Any]:
    return E2E.build_type_first_zero_call_e2e_evidence()


def test_real_compiler_zero_one_and_multiple_option_fixtures_are_proven(
    e2e_result,
) -> None:
    assert e2e_result[
        "real_compiler_fixture_matching_complete_options"
    ] == {
        "zero": 0,
        "one": 1,
        "multiple": 2,
    }
    summaries = {
        item["case_id"]: item for item in e2e_result["success_cases"]
    }
    assert summaries["goal17_true_singleton_zero_options"][
        "matching_complete_options_total"
    ] == 0
    assert summaries["goal17_true_singleton_one_option"][
        "matching_complete_options_total"
    ] == 1
    assert summaries["goal17_true_singleton_multiple_options"][
        "matching_complete_options_total"
    ] == 2
    assert summaries["goal17_true_singleton_one_option"][
        "decision_disposition"
    ] == "typed_input"
    assert summaries["goal17_true_singleton_multiple_options"][
        "reason_code"
    ] == "single_registry_type_no_safe_record"


def test_type_first_prepared_request_and_schema_drift_fail_closed() -> None:
    authorities = E2E._build_authorities("one")
    prepared = authorities.prepared_request

    provider_schema = copy.deepcopy(prepared.provider_visible_schema)
    provider_schema["additionalProperties"] = True
    with pytest.raises(Gate2SourceFactRuntimeError) as schema_exc:
        replace(
            prepared,
            provider_visible_schema=provider_schema,
        ).validate_schema_binding()
    assert (
        schema_exc.value.code
        == "gate2_provider_prepared_schema_binding_invalid"
    )

    canonical_drift = replace(
        prepared,
        canonical_schema_hash="0" * 64,
    )
    case = next(
        item
        for item in E2E.SUCCESS_CASES
        if item.case_id == "goal17_true_singleton_one_option"
    )
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError
    ) as prepared_exc:
        E2E._run_success_case(
            replace(
                authorities,
                prepared_request=canonical_drift,
            ),
            case,
        )
    assert prepared_exc.value.code == (
        "financial_semantic_v6_type_first_prepared_request_mismatch"
    )


def test_success_chain_is_terminal_exact_and_zero_call(
    e2e_result,
) -> None:
    counts = e2e_result["counts"]
    assert counts["success_cases_total"] == 10
    assert counts[
        "success_evidence_serialize_restore_replay_total"
    ] == 10
    assert counts["simulated_terminal_envelopes_total"] == 10
    assert counts[
        "simulated_terminal_envelopes_per_success_case"
    ] == 1
    assert counts["canonical_decisions_total"] == 10
    assert counts["materialized_records_total"] == 10
    assert counts["financial_domain_snapshots_total"] == 10
    assert all(
        item["terminal_envelopes_total"] == 1
        and item["provider_calls_total"] == 0
        and item["replay_status"] == "EXACT"
        for item in e2e_result["success_cases"]
    )
    assert e2e_result["execution_accounting"] == {
        "maximum_provider_calls_per_operation": 1,
        "maximum_fallback_calls_per_operation": 0,
        "provider_calls_authorized_total": 0,
        "fallback_calls_authorized_total": 0,
        "provider_submissions_total": 0,
        "provider_calls_total": 0,
        "provider_responses_total": 0,
        "transport_invocations_total": 0,
        "simulated_terminal_envelopes_total": 10,
        "repair_total": 0,
        "semantic_repair_total": 0,
        "fallback_total": 0,
        "retry_total": 0,
    }
    assert e2e_result["runtime_activation"] is False
    assert e2e_result["production_admission"] is False


def test_semantic_false_sets_are_measured_without_repair(
    e2e_result,
) -> None:
    summaries = {
        item["case_id"]: item for item in e2e_result["success_cases"]
    }
    assert summaries["goal17_false_empty"]["qualification_counters"][
        "false_empty_total"
    ] == 1
    assert summaries["goal17_false_empty"]["qualification_counters"][
        "safe_under_typing_total"
    ] == 1
    assert summaries["goal17_false_singleton"][
        "qualification_counters"
    ]["false_singleton_total"] == 1
    assert summaries["goal17_false_singleton"][
        "qualification_counters"
    ]["false_singleton_typed_total"] == 1
    true_empty_false_singleton = summaries[
        "goal17_false_singleton_from_true_empty"
    ]["qualification_counters"]
    assert true_empty_false_singleton["false_singleton_total"] == 1
    assert true_empty_false_singleton["false_superset_total"] == 1
    assert true_empty_false_singleton["false_singleton_typed_total"] == 1
    assert true_empty_false_singleton["unsafe_typed_total"] == 1
    assert summaries["goal17_false_superset"][
        "qualification_counters"
    ]["false_superset_total"] == 1
    assert summaries["goal17_wrong_singleton"][
        "qualification_counters"
    ]["wrong_singleton_type_total"] == 1
    assert summaries["goal17_wrong_singleton"][
        "qualification_counters"
    ]["unsafe_typed_total"] == 1


def test_at_least_fifteen_adversarial_cases_fail_closed_and_replay(
    e2e_result,
) -> None:
    counts = e2e_result["counts"]
    assert counts["semantic_adversarial_cases_total"] == 5
    assert counts["parser_adversarial_cases_total"] == 12
    assert counts["request_sealing_adversarial_cases_total"] == 1
    assert counts["binding_drift_adversarial_cases_total"] == 1
    assert counts["pack_projection_drift_adversarial_cases_total"] == 1
    assert counts[
        "exact_option_restoration_adversarial_cases_total"
    ] == 1
    assert counts["adversarial_cases_total"] == 21
    assert counts[
        "technical_failure_serialize_restore_replay_total"
    ] == 16
    assert counts["invalid_responses_total"] == 12

    observed_codes = {
        item["exact_error_code"]
        for item in e2e_result["technical_failure_cases"]
    }
    assert {
        "unknown_type_key",
        "duplicate_type_key",
        "out_of_order_type_keys",
        "malformed_json",
        "duplicate_response_field",
        "backend_type_id_forbidden",
        "source_hash_drift",
        "mapping_receipt_mismatch",
        "pack_projection_drift",
        "exact_code_owned_typed_option_mismatch",
    } <= observed_codes
    assert all(
        item["replay_status"] == "EXACT_TECHNICAL_FAILURE"
        and item["invalid_response_total"]
        == int(item["failure_stage"] == "response_parser")
        and item["canonical_decision_total"] == 0
        and item["materialized_record_total"] == 0
        and item["financial_domain_snapshot_total"] == 0
        and item["provider_calls_total"] == 0
        for item in e2e_result["technical_failure_cases"]
    )
    assert (
        e2e_result["binding_drift_error_code"]
        == "mapping_receipt_mismatch"
    )
    assert (
        e2e_result["exact_option_restoration_error_code"]
        == "exact_code_owned_typed_option_mismatch"
    )


def test_returned_aggregate_is_integrity_bound_and_privacy_safe(
    e2e_result,
) -> None:
    material = {
        key: copy.deepcopy(value)
        for key, value in e2e_result.items()
        if key != "integrity_sha256"
    }
    assert e2e_result["integrity_sha256"] == sha256_json(material)
    assert e2e_result["privacy"] == {
        "private_evidence_returned": False,
        "raw_envelopes_returned": False,
        "source_literals_returned": False,
        "source_refs_returned": False,
    }
    forbidden_keys = {
        "exact_private_invalid_input",
        "exact_prepared_request",
        "exact_sealed_request",
        "literal_value",
        "materialized_artifact",
        "simulated_provider_envelope",
        "source_value_ref",
    }
    assert not any(
        forbidden_keys.intersection(item)
        for item in _walk_dicts(e2e_result)
    )
    serialized = json.dumps(
        e2e_result,
        ensure_ascii=False,
        sort_keys=True,
    )
    assert "simulated:" not in serialized
    assert "type-first-local-simulator-v1" not in serialized


def test_support_runner_has_no_transport_or_provider_invocation_callsite():
    source = (
        SCRIPTS_ROOT / "build_type_first_zero_call_e2e_evidence.py"
    ).read_text(encoding="utf-8")
    forbidden_methods = {
        "invoke_native_once",
        "invoke_context_v2_1_budget_smoke_once",
    }
    forbidden_roots = {"requests", "httpx", "socket"}
    violations = []
    for call in (
        node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)
    ):
        if isinstance(call.func, ast.Name) and call.func.id == "urlopen":
            violations.append((call.lineno, call.func.id))
            continue
        if not isinstance(call.func, ast.Attribute):
            continue
        if call.func.attr in forbidden_methods:
            violations.append((call.lineno, call.func.attr))
            continue
        root = call.func.value
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in forbidden_roots:
            violations.append((call.lineno, root.id))
    assert violations == []


def test_goal17_report_and_safe_receipt_are_current(e2e_result) -> None:
    assert e2e_result["repository_authorities"]["hash_boundary"] == (
        E2E.REPOSITORY_AUTHORITY_HASH_BOUNDARY
    )
    assert E2E.SAFE_RECEIPT_PATH.read_text(encoding="utf-8") == (
        E2E.serialize_type_first_zero_call_safe_receipt(e2e_result)
    )
    assert E2E.REPORT_PATH.read_text(encoding="utf-8") == (
        E2E.render_type_first_goal17_report(e2e_result)
    )


def test_goal17_contract_self_integrity_is_recomputed_fail_closed(
    tmp_path: Path,
) -> None:
    contract = json.loads(E2E.CONTRACT_PATH.read_text(encoding="utf-8"))
    expected = contract["integrity_sha256"]
    assert E2E._load_contract_integrity(E2E.CONTRACT_PATH) == expected

    contract["status"]["provider_calls_total"] = 1
    tampered_path = tmp_path / "tampered-contract.json"
    tampered_path.write_text(
        json.dumps(contract, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(
        E2E.TypeFirstZeroCallE2EError,
        match="contract_integrity_mismatch",
    ):
        E2E._load_contract_integrity(tampered_path)


def test_repository_authority_hash_boundary_is_cross_platform(
    tmp_path: Path,
) -> None:
    lf_path = tmp_path / "lf.py"
    crlf_path = tmp_path / "crlf.py"
    invalid_path = tmp_path / "invalid.py"
    lf_path.write_bytes(b"first\nsecond\n")
    crlf_path.write_bytes(b"first\r\nsecond\r\n")
    invalid_path.write_bytes(b"first\rsecond\n")

    assert E2E._sha256_repository_file(
        lf_path
    ) == E2E._sha256_repository_file(crlf_path)
    with pytest.raises(
        E2E.TypeFirstZeroCallE2EError,
        match="repository_authority_line_endings_invalid",
    ):
        E2E._sha256_repository_file(invalid_path)


def _walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)
