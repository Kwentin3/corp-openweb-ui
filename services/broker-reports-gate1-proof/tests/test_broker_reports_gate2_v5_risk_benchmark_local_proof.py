from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402,E501
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_benchmark import (  # noqa: E402,E501
    V5_BASE_BENCHMARK_SHA256,
    V5_RISK_BENCHMARK_SHA256,
    Gate2FinancialSemanticV5BenchmarkError,
)
from broker_reports_gate1.gate2_financial_semantic_v5_local_proof import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2FinancialSemanticV5LocalProofFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)


V5_MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v5"
    / "manifest.json"
)
BASE_MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
MODULE_PATHS = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_benchmark.py",
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_local_proof.py",
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_local_proof_checks.py",
)
SNAPSHOT_AUTHORITY_KEY = b"synthetic-v5-local-authority-key-32"
CONTINUATION_KEY = b"synthetic-v5-local-continuation-key-32"


def _manifests():
    return (
        json.loads(V5_MANIFEST_PATH.read_text(encoding="utf-8")),
        json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8")),
    )


def _proof(v5_manifest=None, base_manifest=None):
    current_v5, current_base = _manifests()
    return Gate2FinancialSemanticV5LocalProofFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=current_v5 if v5_manifest is None else v5_manifest,
        base_manifest=(
            current_base if base_manifest is None else base_manifest
        ),
    )


def test_v5_benchmark_is_frozen_over_exact_twelve_family_base():
    manifest, base = _manifests()

    assert sha256_json(manifest) == V5_RISK_BENCHMARK_SHA256
    assert sha256_json(base) == V5_BASE_BENCHMARK_SHA256
    assert manifest["frozen"] is True
    assert manifest["contains_customer_data"] is False
    assert manifest["case_count"] == 12
    assert [item["case_id"] for item in manifest["cases"]] == [
        item["case_id"] for item in base["cases"]
    ]
    assert {
        feature
        for item in manifest["cases"]
        for feature in item["feature_families"]
    } == set(manifest["required_feature_families"])
    assert "literal" not in json.dumps(manifest)


def test_local_v5_proof_passes_all_acceptance_and_hard_gates():
    receipt = _proof()

    assert receipt["status"] == "passed"
    assert receipt["acceptance"] == {
        "local_v5_proof": "PASSED",
        "adjacent_equal": "UNCLASSIFIED_ONLY",
        "technical_preclose": "PASSED",
        "literal_loss": "ZERO",
        "query_gaps": "ZERO",
        "provider_calls": "ZERO",
    }
    assert all(receipt["checks"].values())
    assert receipt["hard_gates"] == {
        "unsafe_typed_total": 0,
        "invented_values_total": 0,
        "invalid_refs_total": 0,
        "wrong_roles_total": 0,
        "duplicate_bindings_total": 0,
        "cross_scope_bindings_total": 0,
        "literal_or_provenance_loss_total": 0,
        "ownership_gaps_total": 0,
        "query_gaps_total": 0,
    }


def test_preclose_and_provider_routing_are_exact_and_no_call():
    receipt = _proof()
    by_case = {
        item["case_id"]: item for item in receipt["case_receipts"]
    }

    assert receipt["routes"] == {
        "technical_cases_total": 2,
        "semantic_model_cases_total": 10,
        "preclose_status_counts": {
            "model_required": 10,
            "no_financial_input": 1,
            "unsupported": 1,
        },
        "provider_disposition_counts": {
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
    assert by_case["syn_successor_v2_repeated_header"]["route"] == (
        "technical_preclose"
    )
    assert by_case["syn_successor_v2_unsupported_shape"]["route"] == (
        "technical_preclose"
    )
    assert by_case["syn_successor_v2_adjacent_equal"][
        "available_type_cards"
    ] == 0
    assert by_case["syn_successor_v2_adjacent_equal"][
        "disposition"
    ] == "unclassified_financial_input"
    assert all(
        item["provider_calls_total"] == 0
        for item in receipt["case_receipts"]
    )
    assert all(
        by_case[case_id]["packet_hash"] is None
        for case_id in (
            "syn_successor_v2_repeated_header",
            "syn_successor_v2_unsupported_shape",
        )
    )


def test_quality_metrics_include_compact_context_and_safe_under_typing():
    quality = _proof()["quality"]

    assert quality["typed_precision_basis_points"] == 10000
    assert quality["typed_recall_basis_points"] == 10000
    assert quality["safe_under_typed_total"] == 0
    assert quality["safe_under_typed_rate_basis_points"] == 0
    assert quality["unclassified_provider_cases_total"] == 6
    assert quality["unclassified_provider_rate_basis_points"] == 6000
    assert quality["model_context_bytes_total"] > 0
    assert quality["model_context_bytes_max"] > 0
    assert quality["estimated_tokens_total"] > 0
    assert quality["estimated_tokens_max"] > 0
    assert quality["projection_canonical_bytes"] < 4096
    assert (
        quality["projection_canonical_bytes"] * 2
        < quality["full_pack_canonical_bytes"]
    )
    assert quality["projection_of_full_pack_basis_points"] < 5000


def test_materialization_persistence_catalog_and_queries_are_complete():
    domain = _proof()["domain"]

    assert domain["typed_records_total"] == 4
    assert domain["unclassified_records_total"] == 6
    assert domain["coverage_records_total"] == 12
    assert domain["provenance_records_total"] == 12
    assert domain["declared_types_total"] == 2
    assert domain["query_gaps_total"] == 0
    assert domain["coverage_gaps_total"] == 0
    assert domain["provenance_gaps_total"] == 0
    assert len(domain["snapshot_integrity_sha256"]) == 64
    assert len(domain["serialized_snapshot_sha256"]) == 64


def test_negative_fail_closed_checks_cover_every_new_boundary():
    assert _proof()["negative_checks"] == {
        "invalid_preclose_rejected": True,
        "packet_identity_tamper_rejected": True,
        "ambiguous_typed_rejected": True,
        "invalid_ref_rejected": True,
        "wrong_role_rejected": True,
        "duplicate_binding_rejected": True,
        "technical_model_branch_rejected": True,
        "materialized_artifact_tamper_rejected": True,
        "persistence_tamper_rejected": True,
        "query_gap_rejected": True,
    }


def test_local_v5_receipt_is_deterministic_and_repository_safe():
    manifest, base = _manifests()
    first = _proof(manifest, base)
    second = _proof(copy.deepcopy(manifest), copy.deepcopy(base))
    rendered = json.dumps(first, ensure_ascii=False, sort_keys=True)
    private_values = {
        cell["literal"]
        for case in base["cases"]
        for field in ("cells", "neighbour_cells")
        for cell in case.get(field) or []
    }

    assert first == second
    assert first["integrity_sha256"] == sha256_json(
        {
            key: value
            for key, value in first.items()
            if key != "integrity_sha256"
        }
    )
    assert all(value not in rendered for value in private_values)
    assert '"source_value_ref":' not in rendered
    assert '"literal_value":' not in rendered
    assert "exact_canonical_request_object" not in rendered
    assert "normalized_canonical_model_decision" not in rendered
    assert SNAPSHOT_AUTHORITY_KEY.decode("ascii") not in rendered
    assert CONTINUATION_KEY.decode("ascii") not in rendered


def test_execution_accounting_and_closed_world_are_zero():
    receipt = _proof()
    sources = [
        path.read_text(encoding="utf-8") for path in MODULE_PATHS
    ]
    source = "\n".join(sources)
    imported_modules = set()
    for current in sources:
        tree = ast.parse(current)
        imported_modules.update(
            str(node.module or "")
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )

    assert receipt["execution_accounting"] == {
        "provider_calls_total": 0,
        "source_model_calls_total": 0,
        "domain_model_calls_total": 0,
        "financial_model_calls_total": 0,
        "fallback_total": 0,
        "repair_attempts_total": 0,
        "hidden_retry_total": 0,
        "persistence_writes_total": 0,
        "production_route_activations_total": 0,
    }
    assert "frozen V5 risk benchmark" in FACTORY_REQUIRED
    assert "must not call a provider" in FORBIDDEN
    assert ".extract(" not in source
    assert ".write_" not in source
    assert "open(" not in source
    assert not {
        module
        for module in imported_modules
        if "provider_adapters" in module
        or "model_clients" in module
        or "production_runtime" in module
        or "artifact_store" in module
    }


@pytest.mark.parametrize("target", ("v5", "base"))
def test_manifest_drift_fails_closed(target):
    manifest, base = _manifests()
    if target == "v5":
        manifest["execution_policy"]["provider_calls"] = 1
    else:
        base["case_count"] = 11

    with pytest.raises(
        Gate2FinancialSemanticV5BenchmarkError
    ) as exc:
        _proof(manifest, base)
    assert exc.value.code == (
        "financial_semantic_v5_benchmark_identity_invalid"
    )
