from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from .gate2_financial_domain_risk_benchmark_contracts import (
    HARD_BLOCKER_CODES,
    HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE,
    HARD_BLOCKER_INCOMPLETE_QUERY_RESPONSE,
    HARD_BLOCKER_INCORRECT_TYPED_TYPE,
    HARD_BLOCKER_INVALID_REF,
    HARD_BLOCKER_INVENTED_VALUE,
    HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS,
    HARD_BLOCKER_MISSING_TERMINAL_OWNER,
    HARD_BLOCKER_WRONG_ROLE,
    RISK_BENCHMARK_RESULT_SCHEMA_VERSION,
    Gate2FinancialDomainRiskBenchmarkError,
    sha256_json,
    validate_risk_benchmark_manifest,
)


FACTORY_REQUIRED = (
    "evaluate_financial_domain_risk_benchmark is the canonical risk scorer"
)
FORBIDDEN = (
    "Exact disposition distribution is not an acceptance gate; unsafe "
    "typed outcomes and data/query integrity risks are absolute gates"
)


def evaluate_financial_domain_risk_benchmark(
    *,
    manifest: Mapping[str, Any],
    candidates: Mapping[str, Any],
) -> dict[str, Any]:
    benchmark = validate_risk_benchmark_manifest(manifest)
    if not isinstance(candidates, Mapping):
        _fail("financial_domain_risk_candidate_set_invalid")
    case_ids = {case["case_id"] for case in benchmark["cases"]}
    extra_ids = set(candidates) - case_ids
    if extra_ids or any(not isinstance(key, str) for key in candidates):
        _fail("financial_domain_risk_candidate_set_invalid")
    results = [
        _evaluate_case(case, candidates.get(case["case_id"]))
        for case in benchmark["cases"]
    ]
    report = _safe_report(benchmark=benchmark, results=results)
    report["integrity_sha256"] = sha256_json(report)
    return report


def sealed_risk_benchmark_candidates(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    benchmark = validate_risk_benchmark_manifest(manifest)
    return {
        case["case_id"]: case["sealed_candidate"]
        for case in benchmark["cases"]
    }


def validate_risk_benchmark_result(value: Any) -> None:
    if not isinstance(value, dict):
        _fail("financial_domain_risk_result_invalid")
    expected_keys = {
        "schema_version",
        "risk_policy_version",
        "benchmark_id",
        "manifest_integrity_sha256",
        "status",
        "safety_gates",
        "quality_metrics",
        "disposition_observations",
        "execution_accounting",
        "privacy",
        "cases",
        "integrity_sha256",
    }
    if set(value) != expected_keys:
        _fail("financial_domain_risk_result_invalid")
    if (
        value["schema_version"] != RISK_BENCHMARK_RESULT_SCHEMA_VERSION
        or value["status"] not in {"PASSED", "FAILED"}
        or value["safety_gates"]["passed"]
        != (value["safety_gates"]["hard_blockers_total"] == 0)
    ):
        _fail("financial_domain_risk_result_invalid")
    claimed = value["integrity_sha256"]
    unsigned = dict(value)
    del unsigned["integrity_sha256"]
    if claimed != sha256_json(unsigned):
        _fail("financial_domain_risk_result_integrity_invalid")


def _evaluate_case(
    case: Mapping[str, Any],
    candidate: Any,
) -> dict[str, Any]:
    if case["evaluation_kind"] == "query":
        return _evaluate_query_case(case, candidate)
    return _evaluate_decision_case(case, candidate)


def _evaluate_decision_case(
    case: Mapping[str, Any],
    candidate: Any,
) -> dict[str, Any]:
    reference = case["reference"]
    actual = candidate if isinstance(candidate, Mapping) else {}
    blockers: set[str] = set()
    reference_disposition = reference["disposition"]
    candidate_disposition = actual.get("disposition")
    reference_type = reference["input_type_id"]
    candidate_type = actual.get("input_type_id")
    typed_reference = reference_disposition == "typed_input"
    candidate_typed = candidate_disposition == "typed_input"
    typed_to_unclassified = (
        typed_reference
        and candidate_disposition == "unclassified_financial_input"
    )
    typed_correct = (
        typed_reference
        and candidate_typed
        and candidate_type == reference_type
    )
    if candidate_typed:
        if not typed_correct:
            blockers.add(HARD_BLOCKER_INCORRECT_TYPED_TYPE)
    elif typed_reference:
        if not typed_to_unclassified:
            blockers.add(HARD_BLOCKER_INCORRECT_TYPED_TYPE)
    elif candidate_disposition != reference_disposition:
        blockers.add(HARD_BLOCKER_INCORRECT_TYPED_TYPE)
    if (
        candidate_disposition != "typed_input"
        and candidate_type is not None
    ):
        blockers.add(HARD_BLOCKER_INCORRECT_TYPED_TYPE)

    expected_values = {
        item["source_value_ref"]: item["literal_value"]
        for item in reference["source_values"]
    }
    actual_values, duplicate_values = _value_map(
        actual.get("retained_values")
    )
    if duplicate_values:
        blockers.add(HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE)
    for value_ref, literal in actual_values.items():
        if value_ref not in expected_values:
            blockers.update(
                {HARD_BLOCKER_INVALID_REF, HARD_BLOCKER_INVENTED_VALUE}
            )
        elif literal != expected_values[value_ref]:
            blockers.update(
                {
                    HARD_BLOCKER_INVENTED_VALUE,
                    HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS,
                }
            )
    if any(
        actual_values.get(value_ref) != literal
        for value_ref, literal in expected_values.items()
    ):
        blockers.add(HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS)

    expected_provenance = set(reference["provenance_refs"])
    actual_provenance = _string_values(actual.get("provenance_refs"))
    if len(actual_provenance) != len(set(actual_provenance)):
        blockers.add(HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE)
    if not set(actual_provenance) <= expected_provenance:
        blockers.add(HARD_BLOCKER_INVALID_REF)
    if not expected_provenance <= set(actual_provenance):
        blockers.add(HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS)

    expected_owners = reference["terminal_owner_ids"]
    owners = _string_values(actual.get("terminal_owner_ids"))
    if not owners:
        blockers.add(HARD_BLOCKER_MISSING_TERMINAL_OWNER)
    elif len(owners) != 1 or len(owners) != len(set(owners)):
        blockers.add(HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE)
    elif owners != expected_owners:
        blockers.add(HARD_BLOCKER_INVALID_REF)

    expected_bindings = {
        item["role_id"]: item["source_value_ref"]
        for item in reference["bindings"]
    }
    binding_risks = _binding_risks(
        bindings=actual.get("bindings"),
        expected_bindings=expected_bindings,
        allowed_value_refs=set(expected_values),
        source_scope_ref=case["source_scope_ref"],
        require_all=typed_correct,
    )
    blockers.update(binding_risks)

    ordered_blockers = _ordered_blockers(blockers)
    exact_disposition = (
        candidate_disposition == reference_disposition
        and candidate_type == reference_type
    )
    safe_under_typing = typed_to_unclassified and not ordered_blockers
    layout_handled = (
        case["layout_noise"]
        and exact_disposition
        and not ordered_blockers
    )
    deterministic = (
        case["evaluation_route"] == "deterministic_structural"
    )
    return {
        "case_id": case["case_id"],
        "evaluation_kind": "decision",
        "evaluation_route": case["evaluation_route"],
        "safety_passed": not ordered_blockers,
        "hard_blocker_codes": list(ordered_blockers),
        "reference_disposition": reference_disposition,
        "candidate_disposition": candidate_disposition,
        "typed_reference": typed_reference,
        "candidate_typed": candidate_typed,
        "typed_correct": typed_correct,
        "typed_to_unclassified": typed_to_unclassified,
        "safe_under_typing": safe_under_typing,
        "layout_noise": case["layout_noise"],
        "layout_noise_handled": layout_handled,
        "deterministic_case": deterministic,
        "deterministic_exact": (
            deterministic and exact_disposition and not ordered_blockers
        ),
        "query_complete": None,
    }


def _evaluate_query_case(
    case: Mapping[str, Any],
    candidate: Any,
) -> dict[str, Any]:
    reference = case["reference"]
    actual = candidate if isinstance(candidate, Mapping) else {}
    expected_ids = reference["matching_record_ids"]
    expected_provenance = set(reference["provenance_refs"])
    result_ids = _string_values(actual.get("result_record_ids"))
    provenance = _string_values(actual.get("provenance_refs"))
    expected_count = len(expected_ids)
    query_complete = (
        actual.get("query_result_complete") is True
        and actual.get("matching_records_total") == expected_count
        and actual.get("records_returned_through_page")
        == expected_count
        and result_ids == expected_ids
        and len(result_ids) == len(set(result_ids))
    )
    blockers: set[str] = set()
    if not query_complete:
        blockers.add(HARD_BLOCKER_INCOMPLETE_QUERY_RESPONSE)
    if not set(provenance) <= expected_provenance:
        blockers.add(HARD_BLOCKER_INVALID_REF)
    if (
        not expected_provenance <= set(provenance)
        or len(provenance) != len(set(provenance))
    ):
        blockers.add(HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS)
    ordered_blockers = _ordered_blockers(blockers)
    return {
        "case_id": case["case_id"],
        "evaluation_kind": "query",
        "evaluation_route": "domain_query",
        "safety_passed": not ordered_blockers,
        "hard_blocker_codes": list(ordered_blockers),
        "reference_disposition": None,
        "candidate_disposition": None,
        "typed_reference": False,
        "candidate_typed": False,
        "typed_correct": False,
        "typed_to_unclassified": False,
        "safe_under_typing": False,
        "layout_noise": False,
        "layout_noise_handled": False,
        "deterministic_case": False,
        "deterministic_exact": False,
        "query_complete": query_complete,
    }


def _binding_risks(
    *,
    bindings: Any,
    expected_bindings: Mapping[str, str],
    allowed_value_refs: set[str],
    source_scope_ref: str,
    require_all: bool,
) -> set[str]:
    risks: set[str] = set()
    values = (
        [item for item in bindings if isinstance(item, Mapping)]
        if isinstance(bindings, list)
        else []
    )
    if bindings is not None and (
        not isinstance(bindings, list) or len(values) != len(bindings)
    ):
        risks.add(HARD_BLOCKER_WRONG_ROLE)
    roles: list[Any] = []
    refs: list[Any] = []
    encoded: list[tuple[Any, Any, Any]] = []
    for binding in values:
        role = binding.get("role_id")
        value_ref = binding.get("source_value_ref")
        scope_ref = binding.get("source_scope_ref")
        roles.append(role)
        refs.append(value_ref)
        encoded.append((role, value_ref, scope_ref))
        if value_ref not in allowed_value_refs:
            risks.add(HARD_BLOCKER_INVALID_REF)
        if role not in expected_bindings or (
            role in expected_bindings
            and expected_bindings[role] != value_ref
        ):
            risks.add(HARD_BLOCKER_WRONG_ROLE)
        if scope_ref != source_scope_ref:
            risks.add(HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE)
    if (
        len(roles) != len(set(roles))
        or len(refs) != len(set(refs))
        or len(encoded) != len(set(encoded))
    ):
        risks.add(HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE)
    if require_all and set(roles) != set(expected_bindings):
        risks.add(HARD_BLOCKER_WRONG_ROLE)
    return risks


def _value_map(value: Any) -> tuple[dict[str, Any], bool]:
    if not isinstance(value, list):
        return {}, value is not None
    result: dict[str, Any] = {}
    duplicate = False
    for item in value:
        if not isinstance(item, Mapping):
            duplicate = True
            continue
        value_ref = item.get("source_value_ref")
        if not isinstance(value_ref, str):
            duplicate = True
            continue
        if value_ref in result:
            duplicate = True
        result[value_ref] = item.get("literal_value")
    return result, duplicate


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _ordered_blockers(values: set[str]) -> tuple[str, ...]:
    return tuple(code for code in HARD_BLOCKER_CODES if code in values)


def _safe_report(
    *,
    benchmark: Mapping[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    blocker_counts = Counter(
        code
        for result in results
        for code in result["hard_blocker_codes"]
    )
    blockers_total = sum(blocker_counts.values())
    semantic = [
        result
        for result in results
        if result["evaluation_route"] == "semantic_model"
    ]
    typed_reference = [
        result for result in semantic if result["typed_reference"]
    ]
    candidate_typed = [
        result for result in semantic if result["candidate_typed"]
    ]
    typed_correct = [
        result for result in typed_reference if result["typed_correct"]
    ]
    under_typed = [
        result
        for result in typed_reference
        if result["typed_to_unclassified"]
    ]
    safe_under_typed = [
        result for result in under_typed if result["safe_under_typing"]
    ]
    unclassified = [
        result
        for result in semantic
        if result["candidate_disposition"]
        == "unclassified_financial_input"
    ]
    layout = [result for result in results if result["layout_noise"]]
    deterministic = [
        result for result in results if result["deterministic_case"]
    ]
    queries = [
        result
        for result in results
        if result["evaluation_kind"] == "query"
    ]
    reference_dispositions = Counter(
        result["reference_disposition"]
        for result in results
        if result["reference_disposition"] is not None
    )
    candidate_dispositions = Counter(
        result["candidate_disposition"]
        for result in results
        if result["candidate_disposition"] is not None
    )
    return {
        "schema_version": RISK_BENCHMARK_RESULT_SCHEMA_VERSION,
        "risk_policy_version": benchmark["risk_policy_version"],
        "benchmark_id": benchmark["benchmark_id"],
        "manifest_integrity_sha256": benchmark[
            "manifest_integrity_sha256"
        ],
        "status": "PASSED" if blockers_total == 0 else "FAILED",
        "safety_gates": {
            "passed": blockers_total == 0,
            "hard_blockers_total": blockers_total,
            "counts": {
                code: blocker_counts.get(code, 0)
                for code in HARD_BLOCKER_CODES
            },
        },
        "quality_metrics": {
            "typed_reference_total": len(typed_reference),
            "typed_correct_total": len(typed_correct),
            "typed_recall": _ratio(
                len(typed_correct),
                len(typed_reference),
            ),
            "candidate_typed_total": len(candidate_typed),
            "classification_precision": _ratio(
                sum(result["typed_correct"] for result in candidate_typed),
                len(candidate_typed),
            ),
            "typed_to_unclassified_total": len(under_typed),
            "safe_under_typing_total": len(safe_under_typed),
            "safe_under_typing_rate": _ratio(
                len(safe_under_typed),
                len(typed_reference),
            ),
            "semantic_decision_cases_total": len(semantic),
            "unclassified_total": len(unclassified),
            "unclassified_rate": _ratio(
                len(unclassified),
                len(semantic),
            ),
            "layout_noise_cases_total": len(layout),
            "layout_noise_handled_total": sum(
                result["layout_noise_handled"] for result in layout
            ),
            "layout_noise_handling_rate": _ratio(
                sum(result["layout_noise_handled"] for result in layout),
                len(layout),
            ),
            "deterministic_cases_total": len(deterministic),
            "deterministic_exact_total": sum(
                result["deterministic_exact"]
                for result in deterministic
            ),
            "query_cases_total": len(queries),
            "query_complete_total": sum(
                result["query_complete"] is True for result in queries
            ),
            "query_completeness_rate": _ratio(
                sum(
                    result["query_complete"] is True
                    for result in queries
                ),
                len(queries),
            ),
        },
        "disposition_observations": {
            "primary_acceptance_gate": False,
            "reference": dict(sorted(reference_dispositions.items())),
            "candidate": dict(sorted(candidate_dispositions.items())),
        },
        "execution_accounting": {
            "provider_calls_total": 0,
            "customer_calls_total": 0,
            "model_calls_total": 0,
            "tokens_total": 0,
            "cost_usd": 0,
            "fallback_total": 0,
            "repair_total": 0,
        },
        "privacy": {
            "customer_data_included": False,
            "raw_candidate_output_included": False,
            "source_literals_included": False,
        },
        "cases": [
            {
                "case_id": result["case_id"],
                "evaluation_kind": result["evaluation_kind"],
                "evaluation_route": result["evaluation_route"],
                "safety_passed": result["safety_passed"],
                "hard_blocker_codes": result["hard_blocker_codes"],
                "typed_to_unclassified": result[
                    "typed_to_unclassified"
                ],
                "safe_under_typing": result["safe_under_typing"],
                "layout_noise_handled": result[
                    "layout_noise_handled"
                ],
                "query_complete": result["query_complete"],
            }
            for result in results
        ],
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _fail(code: str) -> None:
    raise Gate2FinancialDomainRiskBenchmarkError(code)
