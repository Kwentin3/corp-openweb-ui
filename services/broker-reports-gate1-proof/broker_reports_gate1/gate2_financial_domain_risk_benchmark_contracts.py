from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping


RISK_BENCHMARK_MANIFEST_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_domain_risk_benchmark_manifest_v1"
)
RISK_BENCHMARK_POLICY_VERSION = (
    "broker_reports_gate2_financial_domain_risk_policy_v1"
)
RISK_BENCHMARK_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_domain_risk_benchmark_result_v1"
)

HARD_BLOCKER_INCORRECT_TYPED_TYPE = "incorrect_typed_type"
HARD_BLOCKER_INVENTED_VALUE = "invented_value"
HARD_BLOCKER_INVALID_REF = "invalid_ref"
HARD_BLOCKER_WRONG_ROLE = "wrong_role"
HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE = (
    "duplicate_or_cross_scope_binding"
)
HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS = (
    "literal_or_provenance_loss"
)
HARD_BLOCKER_MISSING_TERMINAL_OWNER = "missing_terminal_owner"
HARD_BLOCKER_INCOMPLETE_QUERY_RESPONSE = (
    "incomplete_query_response"
)

HARD_BLOCKER_CODES = (
    HARD_BLOCKER_INCORRECT_TYPED_TYPE,
    HARD_BLOCKER_INVENTED_VALUE,
    HARD_BLOCKER_INVALID_REF,
    HARD_BLOCKER_WRONG_ROLE,
    HARD_BLOCKER_DUPLICATE_OR_CROSS_SCOPE,
    HARD_BLOCKER_LITERAL_OR_PROVENANCE_LOSS,
    HARD_BLOCKER_MISSING_TERMINAL_OWNER,
    HARD_BLOCKER_INCOMPLETE_QUERY_RESPONSE,
)
QUALITY_METRIC_IDS = (
    "safe_under_typing",
    "typed_recall",
    "unclassified_rate",
    "layout_noise_handling",
    "classification_precision",
)
DISPOSITIONS = frozenset(
    {
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }
)
EVALUATION_KINDS = frozenset({"decision", "query"})
EVALUATION_ROUTES = frozenset(
    {"semantic_model", "deterministic_structural", "domain_query"}
)
STRUCTURAL_LAYOUT_ROLES = frozenset(
    {
        "empty",
        "layout_footer",
        "layout_header",
        "page_number",
        "separator",
    }
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_TEXT = 4096


class Gate2FinancialDomainRiskBenchmarkError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def validate_risk_benchmark_manifest(
    value: Any,
) -> dict[str, Any]:
    manifest = copy.deepcopy(value)
    _require_keys(
        manifest,
        {
            "schema_version",
            "risk_policy_version",
            "benchmark_id",
            "corpus_role",
            "contains_customer_data",
            "frozen",
            "case_count",
            "hard_blockers",
            "quality_metrics",
            "execution_policy",
            "cases",
            "manifest_integrity_sha256",
        },
        "financial_domain_risk_manifest_shape_invalid",
    )
    if (
        manifest["schema_version"]
        != RISK_BENCHMARK_MANIFEST_SCHEMA_VERSION
        or manifest["risk_policy_version"]
        != RISK_BENCHMARK_POLICY_VERSION
        or not _bounded_text(manifest["benchmark_id"])
        or not _bounded_text(manifest["corpus_role"])
        or manifest["contains_customer_data"] is not False
        or manifest["frozen"] is not True
        or manifest["hard_blockers"] != list(HARD_BLOCKER_CODES)
        or manifest["quality_metrics"] != list(QUALITY_METRIC_IDS)
    ):
        _fail("financial_domain_risk_manifest_policy_invalid")
    _validate_execution_policy(manifest["execution_policy"])
    cases = manifest["cases"]
    if (
        not isinstance(cases, list)
        or isinstance(manifest["case_count"], bool)
        or not isinstance(manifest["case_count"], int)
        or manifest["case_count"] != len(cases)
        or not cases
    ):
        _fail("financial_domain_risk_manifest_case_count_invalid")
    case_ids = []
    for case in cases:
        _validate_case(case)
        case_ids.append(case["case_id"])
    if len(case_ids) != len(set(case_ids)):
        _fail("financial_domain_risk_manifest_case_ids_invalid")
    claimed_hash = manifest["manifest_integrity_sha256"]
    unsigned = dict(manifest)
    del unsigned["manifest_integrity_sha256"]
    if (
        not isinstance(claimed_hash, str)
        or not _SHA256_RE.fullmatch(claimed_hash)
        or claimed_hash != sha256_json(unsigned)
    ):
        _fail("financial_domain_risk_manifest_integrity_invalid")
    return manifest


def deterministic_structural_disposition(
    *,
    source_supported: bool,
    structural_role: str,
    financial_value_candidates_total: int,
) -> str | None:
    if (
        not isinstance(source_supported, bool)
        or not _bounded_text(structural_role)
        or isinstance(financial_value_candidates_total, bool)
        or not isinstance(financial_value_candidates_total, int)
        or financial_value_candidates_total < 0
    ):
        _fail("financial_domain_risk_structural_evidence_invalid")
    if not source_supported:
        return "unsupported"
    if (
        structural_role in STRUCTURAL_LAYOUT_ROLES
        and financial_value_candidates_total == 0
    ):
        return "no_financial_input"
    return None


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _validate_execution_policy(value: Any) -> None:
    expected = {
        "provider_calls": 0,
        "customer_calls": 0,
        "repair": False,
        "fallback": False,
        "raw_output_in_safe_report": False,
        "exact_disposition_distribution_is_primary": False,
    }
    if value != expected:
        _fail("financial_domain_risk_execution_policy_invalid")


def _validate_case(case: Any) -> None:
    _require_keys(
        case,
        {
            "case_id",
            "evaluation_kind",
            "evaluation_route",
            "layout_noise",
            "source_scope_ref",
            "structural_evidence",
            "reference",
            "sealed_candidate",
        },
        "financial_domain_risk_case_shape_invalid",
    )
    if (
        not _bounded_text(case["case_id"])
        or case["evaluation_kind"] not in EVALUATION_KINDS
        or case["evaluation_route"] not in EVALUATION_ROUTES
        or not isinstance(case["layout_noise"], bool)
        or not _bounded_text(case["source_scope_ref"])
    ):
        _fail("financial_domain_risk_case_identity_invalid")
    if case["evaluation_kind"] == "decision":
        _validate_decision_case(case)
    else:
        _validate_query_case(case)


def _validate_decision_case(case: Mapping[str, Any]) -> None:
    if case["evaluation_route"] == "domain_query":
        _fail("financial_domain_risk_case_route_invalid")
    _validate_decision_reference(case["reference"])
    _validate_decision_candidate(case["sealed_candidate"])
    structural = case["structural_evidence"]
    if case["evaluation_route"] == "deterministic_structural":
        _require_keys(
            structural,
            {
                "source_supported",
                "structural_role",
                "financial_value_candidates_total",
            },
            "financial_domain_risk_structural_evidence_invalid",
        )
        deterministic = deterministic_structural_disposition(**structural)
        if (
            deterministic is None
            or deterministic != case["reference"]["disposition"]
        ):
            _fail("financial_domain_risk_deterministic_case_invalid")
    elif structural is not None:
        _fail("financial_domain_risk_semantic_case_structure_invalid")


def _validate_query_case(case: Mapping[str, Any]) -> None:
    if (
        case["evaluation_route"] != "domain_query"
        or case["layout_noise"]
        or case["structural_evidence"] is not None
    ):
        _fail("financial_domain_risk_query_case_route_invalid")
    reference = case["reference"]
    _require_keys(
        reference,
        {"matching_record_ids", "provenance_refs"},
        "financial_domain_risk_query_reference_invalid",
    )
    _string_list(
        reference["matching_record_ids"],
        unique=True,
        code="financial_domain_risk_query_reference_invalid",
    )
    _string_list(
        reference["provenance_refs"],
        unique=True,
        code="financial_domain_risk_query_reference_invalid",
    )
    candidate = case["sealed_candidate"]
    _require_keys(
        candidate,
        {
            "matching_records_total",
            "records_returned_through_page",
            "query_result_complete",
            "result_record_ids",
            "provenance_refs",
        },
        "financial_domain_risk_query_candidate_invalid",
    )
    for field in (
        "matching_records_total",
        "records_returned_through_page",
    ):
        if (
            isinstance(candidate[field], bool)
            or not isinstance(candidate[field], int)
            or candidate[field] < 0
        ):
            _fail("financial_domain_risk_query_candidate_invalid")
    if not isinstance(candidate["query_result_complete"], bool):
        _fail("financial_domain_risk_query_candidate_invalid")
    _string_list(
        candidate["result_record_ids"],
        unique=False,
        code="financial_domain_risk_query_candidate_invalid",
    )
    _string_list(
        candidate["provenance_refs"],
        unique=False,
        code="financial_domain_risk_query_candidate_invalid",
    )


def _validate_decision_reference(value: Any) -> None:
    _require_keys(
        value,
        {
            "disposition",
            "input_type_id",
            "bindings",
            "source_values",
            "provenance_refs",
            "terminal_owner_ids",
        },
        "financial_domain_risk_decision_reference_invalid",
    )
    _validate_disposition_and_type(value)
    _validate_bindings(value["bindings"])
    _validate_source_values(value["source_values"])
    _string_list(
        value["provenance_refs"],
        unique=True,
        code="financial_domain_risk_decision_reference_invalid",
    )
    _string_list(
        value["terminal_owner_ids"],
        unique=True,
        code="financial_domain_risk_decision_reference_invalid",
    )
    if len(value["terminal_owner_ids"]) != 1:
        _fail("financial_domain_risk_decision_reference_invalid")


def _validate_decision_candidate(value: Any) -> None:
    _require_keys(
        value,
        {
            "disposition",
            "input_type_id",
            "bindings",
            "terminal_owner_ids",
            "retained_values",
            "provenance_refs",
        },
        "financial_domain_risk_decision_candidate_invalid",
    )
    _validate_disposition_and_type(value)
    _validate_bindings(value["bindings"])
    _validate_source_values(value["retained_values"])
    _string_list(
        value["terminal_owner_ids"],
        unique=False,
        code="financial_domain_risk_decision_candidate_invalid",
    )
    _string_list(
        value["provenance_refs"],
        unique=False,
        code="financial_domain_risk_decision_candidate_invalid",
    )


def _validate_disposition_and_type(value: Mapping[str, Any]) -> None:
    disposition = value["disposition"]
    input_type_id = value["input_type_id"]
    if disposition not in DISPOSITIONS:
        _fail("financial_domain_risk_disposition_invalid")
    if disposition == "typed_input":
        if not _bounded_text(input_type_id):
            _fail("financial_domain_risk_input_type_invalid")
    elif input_type_id is not None:
        _fail("financial_domain_risk_input_type_invalid")


def _validate_bindings(value: Any) -> None:
    if not isinstance(value, list):
        _fail("financial_domain_risk_bindings_invalid")
    for binding in value:
        _require_keys(
            binding,
            {"role_id", "source_value_ref", "source_scope_ref"},
            "financial_domain_risk_bindings_invalid",
        )
        if any(not _bounded_text(item) for item in binding.values()):
            _fail("financial_domain_risk_bindings_invalid")


def _validate_source_values(value: Any) -> None:
    if not isinstance(value, list):
        _fail("financial_domain_risk_values_invalid")
    for item in value:
        _require_keys(
            item,
            {"source_value_ref", "literal_value"},
            "financial_domain_risk_values_invalid",
        )
        if (
            not _bounded_text(item["source_value_ref"])
            or not isinstance(item["literal_value"], str)
            or len(item["literal_value"]) > _MAX_TEXT
        ):
            _fail("financial_domain_risk_values_invalid")


def _string_list(value: Any, *, unique: bool, code: str) -> None:
    if (
        not isinstance(value, list)
        or any(not _bounded_text(item) for item in value)
        or (unique and len(value) != len(set(value)))
    ):
        _fail(code)


def _require_keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(code)


def _bounded_text(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= _MAX_TEXT
    )


def _fail(code: str) -> None:
    raise Gate2FinancialDomainRiskBenchmarkError(code)
