from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from broker_reports_gate1.gate2_financial_domain_risk_benchmark import (
    evaluate_financial_domain_risk_benchmark,
    sealed_risk_benchmark_candidates,
    validate_risk_benchmark_result,
)
from broker_reports_gate1.gate2_financial_domain_risk_benchmark_contracts import (
    HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE,
    HARD_BLOCKER_INCOMPLETE_QUERY_RESPONSE,
    HARD_BLOCKER_INCORRECT_TYPED_TYPE,
    HARD_BLOCKER_INVALID_REF,
    HARD_BLOCKER_INVENTED_VALUE,
    HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS,
    HARD_BLOCKER_MISSING_TERMINAL_OWNER,
    HARD_BLOCKER_WRONG_ROLE,
    RISK_BENCHMARK_MANIFEST_SCHEMA_VERSION,
    Gate2FinancialDomainRiskBenchmarkError,
    deterministic_structural_disposition,
    sha256_json,
    validate_risk_benchmark_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_domain_risk_v1"
    / "manifest.json"
)
SEALED_RESULT_PATH = MANIFEST_PATH.with_name("sealed_result.safe.json")
BOUNDARY_MODULES = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_domain_risk_benchmark_contracts.py",
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_domain_risk_benchmark.py",
)


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _candidates(manifest: dict) -> dict:
    return copy.deepcopy(sealed_risk_benchmark_candidates(manifest))


def _result_case(report: dict, case_id: str) -> dict:
    return next(
        item for item in report["cases"] if item["case_id"] == case_id
    )


def _score_mutation(case_id: str, mutate) -> dict:
    manifest = _manifest()
    candidates = _candidates(manifest)
    mutate(candidates[case_id])
    return evaluate_financial_domain_risk_benchmark(
        manifest=manifest,
        candidates=candidates,
    )


def test_manifest_is_frozen_synthetic_versioned_and_hash_bound():
    manifest = validate_risk_benchmark_manifest(_manifest())

    assert manifest["schema_version"] == (
        RISK_BENCHMARK_MANIFEST_SCHEMA_VERSION
    )
    assert manifest["contains_customer_data"] is False
    assert manifest["frozen"] is True
    assert manifest["case_count"] == len(manifest["cases"]) == 6
    assert manifest["execution_policy"]["provider_calls"] == 0
    assert manifest["execution_policy"]["repair"] is False
    assert manifest["execution_policy"]["fallback"] is False
    assert manifest["execution_policy"][
        "exact_disposition_distribution_is_primary"
    ] is False


def test_sealed_control_proves_risk_first_metrics():
    manifest = _manifest()
    report = evaluate_financial_domain_risk_benchmark(
        manifest=manifest,
        candidates=_candidates(manifest),
    )
    validate_risk_benchmark_result(report)

    assert report["status"] == "PASSED"
    assert report["safety_gates"]["passed"] is True
    assert report["safety_gates"]["hard_blockers_total"] == 0
    assert set(report["safety_gates"]["counts"].values()) == {0}
    quality = report["quality_metrics"]
    assert quality["typed_reference_total"] == 2
    assert quality["typed_correct_total"] == 1
    assert quality["typed_recall"] == 0.5
    assert quality["candidate_typed_total"] == 1
    assert quality["classification_precision"] == 1.0
    assert quality["typed_to_unclassified_total"] == 1
    assert quality["safe_under_typing_total"] == 1
    assert quality["safe_under_typing_rate"] == 0.5
    assert quality["unclassified_total"] == 2
    assert quality["unclassified_rate"] == 0.666667
    assert quality["layout_noise_handling_rate"] == 1.0
    assert quality["deterministic_exact_total"] == 2
    assert quality["query_completeness_rate"] == 1.0
    assert report["disposition_observations"][
        "primary_acceptance_gate"
    ] is False
    assert report["disposition_observations"]["reference"] != (
        report["disposition_observations"]["candidate"]
    )


def test_committed_safe_result_is_exact_deterministic_scorer_output():
    manifest = _manifest()
    first = evaluate_financial_domain_risk_benchmark(
        manifest=manifest,
        candidates=_candidates(manifest),
    )
    second = evaluate_financial_domain_risk_benchmark(
        manifest=manifest,
        candidates=_candidates(manifest),
    )
    committed = json.loads(
        SEALED_RESULT_PATH.read_text(encoding="utf-8")
    )

    assert first == second == committed
    validate_risk_benchmark_result(committed)


def test_safe_under_typing_is_not_unsafe_misclassification():
    report = evaluate_financial_domain_risk_benchmark(
        manifest=_manifest(),
        candidates=_candidates(_manifest()),
    )
    result = _result_case(report, "syn_risk_safe_under_typed")

    assert result["typed_to_unclassified"] is True
    assert result["safe_under_typing"] is True
    assert result["safety_passed"] is True
    assert result["hard_blocker_codes"] == []

    def unsafe_typed(candidate):
        candidate["disposition"] = "typed_input"
        candidate["input_type_id"] = "synthetic_wrong_type_v1"

    failed = _score_mutation(
        "syn_risk_unclassified_preserved",
        unsafe_typed,
    )
    unsafe = _result_case(
        failed,
        "syn_risk_unclassified_preserved",
    )
    assert HARD_BLOCKER_INCORRECT_TYPED_TYPE in unsafe[
        "hard_blocker_codes"
    ]
    assert failed["status"] == "FAILED"


@pytest.mark.parametrize(
    ("case_id", "mutate", "expected"),
    [
        (
            "syn_risk_typed_exact",
            lambda value: value.update(
                {"input_type_id": "synthetic_wrong_type_v1"}
            ),
            HARD_BLOCKER_INCORRECT_TYPED_TYPE,
        ),
        (
            "syn_risk_typed_exact",
            lambda value: value["retained_values"][0].update(
                {"literal_value": "invented"}
            ),
            HARD_BLOCKER_INVENTED_VALUE,
        ),
        (
            "syn_risk_typed_exact",
            lambda value: value["bindings"][0].update(
                {"source_value_ref": "value:synthetic:not-authorized"}
            ),
            HARD_BLOCKER_INVALID_REF,
        ),
        (
            "syn_risk_typed_exact",
            lambda value: value["bindings"][0].update(
                {"role_id": "synthetic_wrong_role"}
            ),
            HARD_BLOCKER_WRONG_ROLE,
        ),
        (
            "syn_risk_typed_exact",
            lambda value: value["bindings"][0].update(
                {"source_scope_ref": "scope:synthetic:foreign"}
            ),
            HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE,
        ),
        (
            "syn_risk_typed_exact",
            lambda value: value["retained_values"].pop(),
            HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS,
        ),
        (
            "syn_risk_typed_exact",
            lambda value: value.update({"terminal_owner_ids": []}),
            HARD_BLOCKER_MISSING_TERMINAL_OWNER,
        ),
        (
            "syn_risk_query_complete",
            lambda value: value.update(
                {
                    "query_result_complete": False,
                    "records_returned_through_page": 2,
                }
            ),
            HARD_BLOCKER_INCOMPLETE_QUERY_RESPONSE,
        ),
    ],
)
def test_every_product_hard_blocker_is_absolute(
    case_id: str,
    mutate,
    expected: str,
):
    report = _score_mutation(case_id, mutate)
    result = _result_case(report, case_id)

    assert report["status"] == "FAILED"
    assert report["safety_gates"]["passed"] is False
    assert expected in result["hard_blocker_codes"]
    assert report["safety_gates"]["counts"][expected] >= 1


def test_duplicate_binding_and_provenance_loss_are_not_hidden():
    def mutate(candidate):
        candidate["bindings"].append(
            copy.deepcopy(candidate["bindings"][0])
        )
        candidate["provenance_refs"] = []

    report = _score_mutation("syn_risk_typed_exact", mutate)
    result = _result_case(report, "syn_risk_typed_exact")

    assert HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE in result[
        "hard_blocker_codes"
    ]
    assert HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS in result[
        "hard_blocker_codes"
    ]


def test_terminal_owner_must_be_the_exact_reference_owner():
    def mutate(candidate):
        candidate["terminal_owner_ids"] = ["owner:synthetic:foreign"]

    report = _score_mutation("syn_risk_typed_exact", mutate)
    result = _result_case(report, "syn_risk_typed_exact")

    assert HARD_BLOCKER_INVALID_REF in result["hard_blocker_codes"]
    assert HARD_BLOCKER_MISSING_TERMINAL_OWNER not in result[
        "hard_blocker_codes"
    ]


def test_query_requires_exact_order_count_completion_and_provenance():
    def mutate(candidate):
        candidate["result_record_ids"].reverse()
        candidate["provenance_refs"].pop()

    report = _score_mutation("syn_risk_query_complete", mutate)
    result = _result_case(report, "syn_risk_query_complete")

    assert result["query_complete"] is False
    assert HARD_BLOCKER_INCOMPLETE_QUERY_RESPONSE in result[
        "hard_blocker_codes"
    ]
    assert HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS in result[
        "hard_blocker_codes"
    ]
    assert report["quality_metrics"]["query_completeness_rate"] == 0.0


def test_structural_preclose_uses_only_closed_nonsemantic_evidence():
    assert deterministic_structural_disposition(
        source_supported=False,
        structural_role="opaque_projection",
        financial_value_candidates_total=3,
    ) == "unsupported"
    assert deterministic_structural_disposition(
        source_supported=True,
        structural_role="layout_header",
        financial_value_candidates_total=0,
    ) == "no_financial_input"
    assert (
        deterministic_structural_disposition(
            source_supported=True,
            structural_role="layout_header",
            financial_value_candidates_total=1,
        )
        is None
    )
    assert (
        deterministic_structural_disposition(
            source_supported=True,
            structural_role="semantic_row",
            financial_value_candidates_total=0,
        )
        is None
    )


def test_manifest_rejects_structural_case_that_needs_semantics():
    manifest = _manifest()
    case = next(
        item
        for item in manifest["cases"]
        if item["case_id"] == "syn_risk_layout_header"
    )
    case["structural_evidence"]["financial_value_candidates_total"] = 1
    unsigned = dict(manifest)
    unsigned.pop("manifest_integrity_sha256")
    manifest["manifest_integrity_sha256"] = sha256_json(unsigned)

    with pytest.raises(
        Gate2FinancialDomainRiskBenchmarkError,
        match="financial_domain_risk_deterministic_case_invalid",
    ):
        validate_risk_benchmark_manifest(manifest)


def test_safe_result_contains_only_aggregate_risk_evidence():
    report = evaluate_financial_domain_risk_benchmark(
        manifest=_manifest(),
        candidates=_candidates(_manifest()),
    )
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert "1250.00" not in encoded
    assert "77,005" not in encoded
    assert "value:synthetic:" not in encoded
    assert report["privacy"]["customer_data_included"] is False
    assert report["privacy"]["raw_candidate_output_included"] is False
    assert report["execution_accounting"]["provider_calls_total"] == 0
    assert report["execution_accounting"]["fallback_total"] == 0
    assert report["execution_accounting"]["repair_total"] == 0


def test_result_integrity_and_candidate_set_fail_closed():
    manifest = _manifest()
    candidates = _candidates(manifest)
    report = evaluate_financial_domain_risk_benchmark(
        manifest=manifest,
        candidates=candidates,
    )
    report["quality_metrics"]["typed_recall"] = 1.0
    with pytest.raises(
        Gate2FinancialDomainRiskBenchmarkError,
        match="financial_domain_risk_result_integrity_invalid",
    ):
        validate_risk_benchmark_result(report)

    candidates["extra_case"] = {}
    with pytest.raises(
        Gate2FinancialDomainRiskBenchmarkError,
        match="financial_domain_risk_candidate_set_invalid",
    ):
        evaluate_financial_domain_risk_benchmark(
            manifest=manifest,
            candidates=candidates,
        )


def test_target_python_has_no_pack_type_or_financial_language_classifier():
    forbidden_type_ids = {
        "cash_balance_snapshot_v1",
        "printed_financial_metric_v1",
    }
    for path in BOUNDARY_MODULES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        strings = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        }
        assert not forbidden_type_ids & strings
        assert "ArtifactStore" not in source
        assert "ArtifactResolver" not in source
