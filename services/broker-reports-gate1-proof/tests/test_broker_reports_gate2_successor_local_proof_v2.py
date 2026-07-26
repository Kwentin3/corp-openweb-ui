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
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    Gate2SuccessorLocalProofError,
)
from broker_reports_gate1.gate2_successor_local_proof_v2 import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    LOCAL_PROOF_V2_MANIFEST_SCHEMA_VERSION,
    LOCAL_PROOF_V2_POLICY_VERSION,
    LOCAL_PROOF_V2_RECEIPT_SCHEMA_VERSION,
    REQUIRED_FEATURES_V2,
    Gate2SuccessorLocalProofV2Error,
    Gate2SuccessorLocalProofV2Factory,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_successor_local_proof_v2.py"
)


def _manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _proof(manifest=None):
    return Gate2SuccessorLocalProofV2Factory(
        registry=Gate2FinancialEvidenceRegistryFactory().create()
    ).create(manifest=manifest or _manifest())


def test_frozen_benchmark_v2_passes_q0_q1_and_all_dispositions():
    manifest = _manifest()
    receipt = _proof(manifest)

    assert receipt["schema_version"] == (
        LOCAL_PROOF_V2_RECEIPT_SCHEMA_VERSION
    )
    assert receipt["policy_version"] == LOCAL_PROOF_V2_POLICY_VERSION
    assert receipt["status"] == "passed"
    assert receipt["manifest"] == {
        "schema_version": LOCAL_PROOF_V2_MANIFEST_SCHEMA_VERSION,
        "benchmark_id": "gate2_financial_successor_v2",
        "integrity_hash": sha256_json(manifest),
        "frozen": True,
        "contains_customer_data": False,
        "cases_total": 12,
    }
    assert receipt["q0_contract_tests"]["status"] == "passed"
    assert all(receipt["q0_contract_tests"]["checks"].values())
    assert receipt["q1_product_invariant_fixtures"]["status"] == (
        "passed"
    )
    assert tuple(
        receipt["q1_product_invariant_fixtures"]["checks"]
    ) == REQUIRED_FEATURES_V2
    assert all(
        receipt["q1_product_invariant_fixtures"]["checks"].values()
    )
    assert receipt["terminal_disposition_counts"] == {
        "typed_input": 4,
        "unclassified_financial_input": 6,
        "no_financial_input": 1,
        "unsupported": 1,
    }


def test_benchmark_v2_structural_filter_is_not_semantic_admission():
    receipt = _proof()

    admission = receipt["typed_admission"]
    assert admission["typed_available_scopes_total"] == 10
    assert admission["typed_absent_scopes_total"] == 2
    assert admission["overtyping_negative_tests_total"] == 6
    assert admission["overtyping_negative_tests_passed"] == 6
    assert admission["unsafe_typed_branches_total"] == 0
    assert admission["post_response_conversion_total"] == 0
    assert len(admission["admission_integrity_hashes"]) == 12


def test_benchmark_v2_preserves_literals_bindings_and_ownership():
    receipt = _proof()

    assert receipt["product_invariants"]["status"] == "passed"
    assert receipt["product_invariants"]["literal_loss_total"] == 0
    assert receipt["product_invariants"]["invented_values_total"] == 0
    assert receipt["product_invariants"]["duplicate_bindings_total"] == 0
    assert receipt["product_invariants"]["cross_scope_bindings_total"] == 0
    assert (
        receipt["product_invariants"][
            "terminal_ownership_gap_total"
        ]
        == 0
    )
    assert receipt["coverage"] == {
        "selected_source_refs_total": 24,
        "deterministic_no_fact_refs_total": 12,
        "source_literals_total": 47,
        "source_literals_preserved_total": 47,
        "forbidden_neighbouring_refs_total": 4,
        "forbidden_neighbouring_refs_admitted_total": 0,
        "unaccounted_source_refs_total": 0,
    }


def test_benchmark_v2_exact_contracts_and_hashes_are_deterministic():
    first = _proof()
    second = _proof(copy.deepcopy(_manifest()))

    assert first == second
    assert first["exact_contracts"] == {
        "scope_schema_version": (
            "broker_reports_gate2_deterministic_financial_scope_package_v2"
        ),
        "typed_admission_schema_version": (
            "broker_reports_gate2_financial_typed_admission_v2"
        ),
        "source_context_schema_version": (
            "broker_reports_gate2_financial_evidence_source_context_v2"
        ),
        "model_input_schema_version": (
            "broker_reports_gate2_financial_evidence_successor_model_input_v3"
        ),
        "prompt_contract_id": (
            "broker_reports_gate2_financial_evidence_successor_prompt_v3"
        ),
        "prompt_hash": (
            "30c823d2c509294d4634eac1a4084da9b95056b260bdd64e41d5a5598937d9ae"
        ),
        "provider_projection_schema_version": (
            "broker_reports_gate2_financial_evidence_provider_projection_v3"
        ),
    }
    assert len(first["exact_hashes"]["model_input_hashes"]) == 12
    assert (
        len(
            first["exact_hashes"][
                "provider_response_format_hashes"
            ]
        )
        == 12
    )
    assert (
        len(
            first["exact_hashes"][
                "source_context_integrity_hashes"
            ]
        )
        == 12
    )


def test_benchmark_v2_receipt_is_value_free_and_customer_free():
    manifest = _manifest()
    receipt = _proof(manifest)
    rendered = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    literals = [
        cell["literal"]
        for case in manifest["cases"]
        for key in ("cells", "neighbour_cells")
        for cell in case.get(key) or []
    ]

    assert manifest["contains_customer_data"] is False
    assert all(literal not in rendered for literal in literals)
    assert "source_value_ref" not in rendered
    assert "document:" not in rendered
    assert "row:" not in rendered


def test_benchmark_v2_has_zero_calls_repair_writes_and_activation():
    receipt = _proof()

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


def test_manifest_typed_expectation_cannot_bypass_role_completeness():
    manifest = _manifest()
    case = next(
        item
        for item in manifest["cases"]
        if item["case_id"] == "syn_successor_v2_multiple_compatible"
    )
    case["decision"] = {
        "disposition": "typed_input",
        "input_type_id": "cash_balance_snapshot_v1",
        "reason_code": "typed_supported",
        "bindings": {},
    }

    with pytest.raises(
        Gate2SuccessorLocalProofError,
        match="successor_local_proof_fixture_typed_roles_invalid",
    ):
        _proof(manifest)


def test_manifest_identity_and_feature_drift_fail_closed():
    wrong_schema = _manifest()
    wrong_schema["schema_version"] = "rewritten_v1"
    with pytest.raises(
        Gate2SuccessorLocalProofV2Error,
        match="successor_local_proof_v2_manifest_identity_invalid",
    ):
        _proof(wrong_schema)

    missing_feature = _manifest()
    next(
        item
        for item in missing_feature["cases"]
        if item["case_id"] == "syn_successor_v2_multiple_compatible"
    )["features"] = []
    with pytest.raises(
        Gate2SuccessorLocalProofV2Error,
        match="successor_local_proof_v2_feature_coverage_invalid",
    ):
        _proof(missing_feature)


def test_v2_proof_factory_has_no_provider_or_production_route():
    assert "only frozen synthetic" in FACTORY_REQUIRED
    assert "must not call a provider" in FORBIDDEN
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "_NoCallModelClient" in source
    assert not {
        module
        for module in imported_modules
        if "provider_adapters" in module
        or "model_clients" in module
        or "production_runtime" in module
        or "artifact_store" in module
    }
