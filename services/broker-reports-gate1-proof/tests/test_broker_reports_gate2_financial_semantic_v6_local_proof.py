from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_benchmark import (  # noqa: E402,E501
    V6_BASE_BENCHMARK_SHA256,
    V6_BENCHMARK_SHA256,
    Gate2FinancialSemanticV6BenchmarkError,
)
from broker_reports_gate1.gate2_financial_semantic_v6_local_proof import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    V6_LOCAL_PROOF_POLICY_VERSION,
    V6_LOCAL_PROOF_RECEIPT_SCHEMA_VERSION,
    Gate2FinancialSemanticV6LocalProofFactory,
)


V6_MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
BASE_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
MODULE_PATHS = (
    ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_benchmark.py",
    ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_local_proof.py",
    ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_local_proof_checks.py",
)
SNAPSHOT_AUTHORITY_KEY = b"synthetic-v6-local-authority-key-32"
CONTINUATION_KEY = b"synthetic-v6-local-continuation-key-32"


def _manifests():
    return (
        json.loads(V6_MANIFEST_PATH.read_text(encoding="utf-8")),
        json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8")),
    )


def _proof(v6_manifest=None, base_manifest=None):
    current_v6, current_base = _manifests()
    return Gate2FinancialSemanticV6LocalProofFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=current_v6 if v6_manifest is None else v6_manifest,
        base_manifest=(current_base if base_manifest is None else base_manifest),
    )


def test_v6_benchmark_is_frozen_over_exact_twelve_family_base() -> None:
    manifest, base = _manifests()

    assert sha256_json(manifest) == V6_BENCHMARK_SHA256
    assert sha256_json(base) == V6_BASE_BENCHMARK_SHA256
    assert manifest["frozen"] is True
    assert manifest["contains_customer_data"] is False
    assert manifest["case_count"] == 12
    assert [item["case_id"] for item in manifest["cases"]] == [
        item["case_id"] for item in base["cases"]
    ]
    assert {
        feature for item in manifest["cases"] for feature in item["feature_families"]
    } == set(manifest["required_feature_families"])
    routes = [item["expected_route"] for item in manifest["cases"]]
    assert routes.count("semantic_model") == 10
    assert routes.count("technical_preclose") == 2


def test_v6_local_end_to_end_proof_passes_every_acceptance_gate() -> None:
    receipt = _proof()

    assert receipt["status"] == "passed"
    assert receipt["schema_version"].endswith("_v2")
    assert receipt["schema_version"] == V6_LOCAL_PROOF_RECEIPT_SCHEMA_VERSION
    assert receipt["policy_version"] == V6_LOCAL_PROOF_POLICY_VERSION
    assert receipt["acceptance"] == {
        "local_v6_proof": "PASSED",
        "typed_local_seam": "PASSED",
        "unclassified_local_seam": "PASSED",
        "openai_root_object_projection": "PASSED",
        "expansion": "PASSED",
        "validation": "PASSED",
        "materialization": "PASSED",
        "unclassified_value_loss": "ZERO",
        "validated_materialization_failures": "ZERO",
        "adjacent_equal_typed_options": "ZERO",
        "query_gaps": "ZERO",
        "provider_calls": "ZERO",
    }
    assert all(receipt["checks"].values())
    assert all(value == 0 for value in receipt["hard_gates"].values())
    assert receipt["routes"] == {
        "technical_cases_total": 2,
        "semantic_model_cases_total": 10,
        "model_choice_counts": {
            "typed_input": 4,
            "unclassified_financial_input": 6,
        },
        "local_seam_choice_counts": {
            "typed_input": 4,
            "unclassified_financial_input": 6,
        },
        "canonical_disposition_counts": {
            "typed_input": 4,
            "unclassified_financial_input": 6,
            "no_financial_input": 1,
            "unsupported": 1,
        },
    }
    assert receipt["quality"]["typed_precision_basis_points"] == 10_000
    assert receipt["quality"]["typed_recall_basis_points"] == 10_000
    assert receipt["integrity_sha256"] == sha256_json(
        {key: value for key, value in receipt.items() if key != "integrity_sha256"}
    )
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not call a provider" in FORBIDDEN


def test_all_v6_components_and_financial_domain_are_exercised() -> None:
    receipt = _proof()
    semantic = [
        item for item in receipt["case_receipts"] if item["route"] == "semantic_model"
    ]
    technical = [
        item
        for item in receipt["case_receipts"]
        if item["route"] == "technical_preclose"
    ]

    assert len(semantic) == 10
    assert len(technical) == 2
    assert all(
        item["evidence_bundle_integrity_hash"]
        and item["candidate_compilation_integrity_hash"]
        and item["packet_hash"]
        and item["choice_schema_hash"]
        and item["expansion_integrity_hash"]
        and item["canonical_request_schema_hash"] == item["choice_schema_hash"]
        and item["adapted_request_schema_hash"]
        != item["canonical_request_schema_hash"]
        and item["schema_transform_count"] == 1
        and item["inverse_normalization_exact"] is True
        and item["materialized_artifact_hash"]
        for item in semantic
    )
    assert all(
        item["evidence_bundle_integrity_hash"] is None
        and item["packet_hash"] is None
        and item["provider_calls_total"] == 0
        for item in technical
    )
    assert receipt["domain"]["query_gaps_total"] == 0
    assert receipt["domain"]["provenance_gaps_total"] == 0
    assert receipt["checks"]["persistence_roundtrip"] is True
    assert receipt["checks"]["domain_catalog_validated"] is True


def test_expected_routing_and_adjacent_equal_option_stop_are_exact() -> None:
    receipt = _proof()
    cases = {item["case_id"]: item for item in receipt["case_receipts"]}

    assert cases["syn_successor_v2_repeated_header"]["route"] == ("technical_preclose")
    assert cases["syn_successor_v2_repeated_header"]["disposition"] == (
        "no_financial_input"
    )
    assert cases["syn_successor_v2_unsupported_shape"]["route"] == (
        "technical_preclose"
    )
    assert cases["syn_successor_v2_unsupported_shape"]["disposition"] == ("unsupported")
    adjacent = cases["syn_successor_v2_adjacent_equal"]
    assert adjacent["route"] == "semantic_model"
    assert adjacent["typed_options_total"] == 0
    assert adjacent["disposition"] == "unclassified_financial_input"
    assert all(
        item["route"] == "semantic_model"
        for case_id, item in cases.items()
        if case_id
        not in {
            "syn_successor_v2_repeated_header",
            "syn_successor_v2_unsupported_shape",
        }
    )


def test_negative_checks_all_fail_closed_at_terminal_boundaries() -> None:
    receipt = _proof()

    assert receipt["negative_checks"] == {
        "invalid_preclose_rejected": True,
        "packet_identity_tamper_rejected": True,
        "adjacent_equal_typed_rejected": True,
        "nonminimal_choice_rejected": True,
        "technical_model_branch_rejected": True,
        "expansion_tamper_rejected": True,
        "unclassified_retention_tamper_rejected": True,
        "materialized_artifact_tamper_rejected": True,
        "persistence_tamper_rejected": True,
        "query_gap_rejected": True,
    }


def test_local_proof_is_deterministic_and_repository_safe() -> None:
    first = _proof()
    second = _proof()
    rendered = json.dumps(first, ensure_ascii=False, sort_keys=True)
    _, base = _manifests()

    assert first == second
    private_values = {
        cell["literal"] for case in base["cases"] for cell in case.get("cells", [])
    }
    assert all(value not in rendered for value in private_values)
    assert SNAPSHOT_AUTHORITY_KEY.decode("ascii") not in rendered
    assert CONTINUATION_KEY.decode("ascii") not in rendered
    assert "source_value_ref" not in rendered
    assert "literal_value" not in rendered
    assert first["execution_accounting"] == {
        "provider_calls_total": 0,
        "provider_responses_total": 0,
        "technical_case_provider_calls_total": 0,
        "semantic_fixture_choices_total": 10,
        "simulated_provider_shaped_responses_total": 10,
        "openai_projection_cases_total": 10,
        "fallback_total": 0,
        "repair_attempts_total": 0,
        "hidden_retry_total": 0,
        "persistence_writes_total": 0,
        "production_route_activations_total": 0,
    }


@pytest.mark.parametrize("target", ["manifest", "base"])
def test_frozen_benchmark_or_base_tamper_fails_closed(target) -> None:
    manifest, base = _manifests()
    if target == "manifest":
        manifest = copy.deepcopy(manifest)
        manifest["cases"][0]["expected_typed_options"] = 0
    else:
        base = copy.deepcopy(base)
        base["cases"][0]["cells"][0]["literal"] = "tampered"

    with pytest.raises(
        Gate2FinancialSemanticV6BenchmarkError,
        match="financial_semantic_v6_benchmark_identity_invalid",
    ):
        _proof(v6_manifest=manifest, base_manifest=base)


def test_goal10_modules_have_no_provider_or_persistence_write_route() -> None:
    for path in MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        assert "requests." not in source
        assert "httpx." not in source
        assert "aiohttp." not in source
        assert ".write_text(" not in source
        assert ".write_bytes(" not in source
        assert "fallback_used" not in source
        assert "repair_attempt_count" not in source
        assert "repair_decision(" not in source
    local_proof_source = MODULE_PATHS[1].read_text(encoding="utf-8")
    assert "Gate2ProviderAdapterFactory(" in local_proof_source
    assert "Gate2OpenAIResponseFormatAdapter(" not in local_proof_source
