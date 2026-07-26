from __future__ import annotations

from typing import Any

from .gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)


V5_RISK_BENCHMARK_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v5_benchmark_v1"
)
V5_RISK_BENCHMARK_ID = "gate2_financial_semantic_v5"
V5_RISK_BENCHMARK_SHA256 = (
    "9e9c8006b71b7758981b46597d09c3e45ad60bdc80063263be0c3abecbd66fe7"
)
V5_BASE_BENCHMARK_SHA256 = (
    "430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66"
)
FACTORY_REQUIRED = (
    "validate_financial_semantic_v5_benchmark is the only frozen V5 "
    "benchmark identity entrypoint"
)
FORBIDDEN = (
    "The V5 benchmark contract must not infer technical or semantic "
    "outcomes from literals, labels or runtime financial rules"
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


class Gate2FinancialSemanticV5BenchmarkError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def validate_financial_semantic_v5_benchmark(
    *,
    manifest: Any,
    base_manifest: Any,
) -> None:
    if (
        not isinstance(manifest, dict)
        or not isinstance(base_manifest, dict)
        or sha256_json(manifest) != V5_RISK_BENCHMARK_SHA256
        or sha256_json(base_manifest) != V5_BASE_BENCHMARK_SHA256
        or manifest.get("schema_version")
        != V5_RISK_BENCHMARK_SCHEMA_VERSION
        or manifest.get("benchmark_id") != V5_RISK_BENCHMARK_ID
        or manifest.get("frozen") is not True
        or manifest.get("contains_customer_data") is not False
        or manifest.get("case_count") != 12
        or manifest.get("execution_policy")
        != _EXPECTED_EXECUTION_POLICY
        or (manifest.get("base_manifest") or {}).get(
            "canonical_sha256"
        )
        != V5_BASE_BENCHMARK_SHA256
        or base_manifest.get("case_count") != 12
        or len(manifest.get("cases") or []) != 12
        or len(base_manifest.get("cases") or []) != 12
    ):
        _fail("financial_semantic_v5_benchmark_identity_invalid")
    base_cases = {
        item.get("case_id"): item for item in base_manifest["cases"]
    }
    case_ids = [item.get("case_id") for item in manifest["cases"]]
    if (
        len(base_cases) != 12
        or len(case_ids) != len(set(case_ids))
        or case_ids != [
            item.get("case_id") for item in base_manifest["cases"]
        ]
        or set(manifest.get("required_feature_families") or [])
        != {
            feature
            for item in manifest["cases"]
            for feature in item.get("feature_families") or []
        }
    ):
        _fail("financial_semantic_v5_benchmark_cases_invalid")
    for item in manifest["cases"]:
        source = base_cases.get(item["case_id"])
        decision = (source or {}).get("decision") or {}
        technical = item["expected_route"] == "technical_preclose"
        expected_fields = {
            "case_id",
            "feature_families",
            "expected_route",
            "expected_disposition",
            "expected_input_type_id",
            "expected_available_type_cards",
            *(("technical_evidence",) if technical else ()),
        }
        if (
            source is None
            or set(item) != expected_fields
            or item["feature_families"] != source["features"]
            or item["expected_route"]
            not in {"technical_preclose", "semantic_model"}
            or item["expected_disposition"]
            != decision.get("disposition")
            or item["expected_input_type_id"]
            != decision.get("input_type_id")
            or (
                technical
                and (
                    item["expected_disposition"]
                    not in {"no_financial_input", "unsupported"}
                    or item["expected_available_type_cards"] is not None
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
                    or item["expected_available_type_cards"]
                    not in {0, 2}
                )
            )
        ):
            _fail("financial_semantic_v5_benchmark_case_invalid")


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5BenchmarkError(code)
