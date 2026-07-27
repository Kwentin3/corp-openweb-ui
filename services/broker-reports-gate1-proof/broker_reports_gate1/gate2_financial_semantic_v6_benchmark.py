from __future__ import annotations

from collections import Counter
from typing import Any

from .gate2_financial_evidence_materialization_contracts import sha256_json


V6_BENCHMARK_SCHEMA_VERSION = "broker_reports_gate2_financial_semantic_v6_benchmark_v1"
V6_BENCHMARK_ID = "gate2_financial_semantic_v6"
V6_BENCHMARK_SHA256 = "3688fe9d47534cc6f810550561460f1508acd095e798ea90c5998b55c63b0d33"
V6_BASE_BENCHMARK_SHA256 = (
    "430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66"
)

FACTORY_REQUIRED = (
    "validate_financial_semantic_v6_benchmark is the only frozen V6 "
    "benchmark identity entrypoint"
)
FORBIDDEN = (
    "The V6 benchmark contract must not infer technical routes, Typed "
    "Options or expected decisions from literals, labels or runtime rules"
)

_EXPECTED_EXECUTION_POLICY = {
    "provider_calls": 0,
    "hidden_retry": False,
    "repair": False,
    "fallback": False,
    "fixture_decisions_are_provider_outputs": False,
    "technical_cases_call_model": False,
    "runtime_activation": False,
    "persistence_writes": False,
}


class Gate2FinancialSemanticV6BenchmarkError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def validate_financial_semantic_v6_benchmark(
    *,
    manifest: Any,
    base_manifest: Any,
) -> None:
    if (
        not isinstance(manifest, dict)
        or not isinstance(base_manifest, dict)
        or sha256_json(manifest) != V6_BENCHMARK_SHA256
        or sha256_json(base_manifest) != V6_BASE_BENCHMARK_SHA256
        or manifest.get("schema_version") != V6_BENCHMARK_SCHEMA_VERSION
        or manifest.get("benchmark_id") != V6_BENCHMARK_ID
        or manifest.get("frozen") is not True
        or manifest.get("contains_customer_data") is not False
        or manifest.get("case_count") != 12
        or manifest.get("execution_policy") != _EXPECTED_EXECUTION_POLICY
        or (manifest.get("base_manifest") or {}).get("canonical_sha256")
        != V6_BASE_BENCHMARK_SHA256
        or base_manifest.get("case_count") != 12
        or len(manifest.get("cases") or []) != 12
        or len(base_manifest.get("cases") or []) != 12
    ):
        _fail("financial_semantic_v6_benchmark_identity_invalid")
    base_cases = {item.get("case_id"): item for item in base_manifest["cases"]}
    case_ids = [item.get("case_id") for item in manifest["cases"]]
    routes = Counter(item.get("expected_route") for item in manifest["cases"])
    required_families = {
        feature
        for item in manifest["cases"]
        for feature in item.get("feature_families") or []
    }
    if (
        len(base_cases) != 12
        or len(case_ids) != len(set(case_ids))
        or case_ids != [item.get("case_id") for item in base_manifest["cases"]]
        or set(manifest.get("required_feature_families") or []) != required_families
        or routes != Counter({"semantic_model": 10, "technical_preclose": 2})
    ):
        _fail("financial_semantic_v6_benchmark_cases_invalid")
    for item in manifest["cases"]:
        source = base_cases.get(item["case_id"])
        decision = (source or {}).get("decision") or {}
        technical = item["expected_route"] == "technical_preclose"
        expected_reason_code = (
            (
                "header_or_layout"
                if item["case_id"] == "syn_successor_v2_repeated_header"
                else "source_shape_unsupported"
            )
            if technical
            else decision.get("reason_code")
        )
        expected_fields = {
            "case_id",
            "feature_families",
            "expected_route",
            "expected_disposition",
            "expected_input_type_id",
            "expected_reason_code",
            "expected_typed_options",
            *(("technical_evidence",) if technical else ()),
        }
        if (
            source is None
            or set(item) != expected_fields
            or item["feature_families"] != source["features"]
            or item["expected_disposition"] != decision.get("disposition")
            or item["expected_input_type_id"] != decision.get("input_type_id")
            or item["expected_reason_code"] != expected_reason_code
            or (
                technical
                and (
                    item["case_id"]
                    not in {
                        "syn_successor_v2_repeated_header",
                        "syn_successor_v2_unsupported_shape",
                    }
                    or item["expected_disposition"]
                    not in {"no_financial_input", "unsupported"}
                    or item["expected_typed_options"] is not None
                    or not isinstance(item["technical_evidence"], dict)
                )
            )
            or (
                not technical
                and (
                    item["expected_disposition"]
                    not in {
                        "typed_input",
                        "unclassified_financial_input",
                    }
                    or item["expected_typed_options"] not in {0, 2}
                )
            )
        ):
            _fail("financial_semantic_v6_benchmark_case_invalid")
    adjacent = next(
        item
        for item in manifest["cases"]
        if item["case_id"] == "syn_successor_v2_adjacent_equal"
    )
    if (
        adjacent["expected_route"] != "semantic_model"
        or adjacent["expected_disposition"] != "unclassified_financial_input"
        or adjacent["expected_typed_options"] != 0
    ):
        _fail("financial_semantic_v6_benchmark_adjacent_equal_invalid")


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6BenchmarkError(code)
