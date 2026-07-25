from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    LOCAL_PROOF_MANIFEST_SCHEMA_VERSION,
    LOCAL_PROOF_POLICY_VERSION,
    LOCAL_PROOF_RECEIPT_SCHEMA_VERSION,
    REQUIRED_FEATURES,
    Gate2SuccessorLocalProofError,
    Gate2SuccessorLocalProofFactory,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v1"
    / "manifest.json"
)
MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_successor_local_proof.py"
)


def _manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _receipt(manifest=None):
    return Gate2SuccessorLocalProofFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create()
    ).create(manifest=_manifest() if manifest is None else manifest)


def test_q0_contract_and_q1_fixture_proof_pass_without_provider_calls():
    receipt = _receipt()

    assert receipt["schema_version"] == (
        LOCAL_PROOF_RECEIPT_SCHEMA_VERSION
    )
    assert receipt["policy_version"] == LOCAL_PROOF_POLICY_VERSION
    assert receipt["status"] == "passed"
    assert receipt["q0_contract_tests"]["status"] == "passed"
    assert all(receipt["q0_contract_tests"]["checks"].values())
    assert receipt["q1_product_invariant_fixtures"]["status"] == (
        "passed"
    )
    assert all(
        receipt["q1_product_invariant_fixtures"]["checks"].values()
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


def test_all_four_dispositions_and_product_invariants_are_covered():
    receipt = _receipt()

    assert receipt["terminal_disposition_counts"] == {
        "typed_input": 7,
        "unclassified_financial_input": 2,
        "no_financial_input": 1,
        "unsupported": 1,
    }
    assert receipt["product_invariants"]["status"] == "passed"
    assert all(receipt["product_invariants"]["checks"].values())
    assert receipt["product_invariants"]["literal_loss_total"] == 0
    assert receipt["product_invariants"]["invented_values_total"] == 0
    assert receipt["product_invariants"]["duplicate_bindings_total"] == 0
    assert receipt["product_invariants"]["cross_scope_bindings_total"] == 0
    assert receipt["product_invariants"][
        "terminal_ownership_gap_total"
    ] == 0


def test_literal_coverage_and_forbidden_neighbour_are_exact():
    receipt = _receipt()
    coverage = receipt["coverage"]

    assert coverage["source_literals_total"] == 43
    assert coverage["source_literals_preserved_total"] == 43
    assert coverage["forbidden_neighbouring_refs_total"] == 4
    assert coverage["forbidden_neighbouring_refs_admitted_total"] == 0
    assert coverage["unaccounted_source_refs_total"] == 0
    assert coverage["selected_source_refs_total"] == 22
    assert coverage["deterministic_no_fact_refs_total"] == 11


def test_provider_schemas_are_strict_and_generated_without_transport():
    receipt = _receipt()
    schemas = receipt["provider_schema_generation"]

    assert schemas["strict_json_schema"] is True
    assert schemas["canonical_validator_replacement"] is False
    assert len(schemas["openai_schema_hashes"]) == 11
    assert len(schemas["gemini_schema_hashes"]) == 11
    assert receipt["execution_accounting"]["provider_calls_total"] == 0


def test_negative_cases_fail_closed_inside_proof():
    receipt = _receipt()

    assert receipt["negative_checks"] == {
        "out_of_package_binding_rejected": True,
        "model_system_field_rejected": True,
        "materialized_artifact_tamper_rejected": True,
        "context_tamper_rejected": True,
        "unknown_compatibility_schema_rejected": True,
    }


def test_proof_is_deterministic_and_safe_receipt_is_value_free():
    first = _receipt()
    second = _receipt()

    assert first == second
    serialized = json.dumps(first, ensure_ascii=False, sort_keys=True)
    for forbidden_literal in (
        "-123.4500",
        "999.99",
        "Neighbour cash",
        "Date | Operation | Amount | Currency",
    ):
        assert forbidden_literal not in serialized
    assert "raw_output" not in serialized


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    (
        (
            lambda payload: payload.update({"frozen": False}),
            "successor_local_proof_manifest_identity_invalid",
        ),
        (
            lambda payload: payload["execution_policy"].update(
                {"provider_calls": 1}
            ),
            "successor_local_proof_execution_policy_invalid",
        ),
        (
            lambda payload: payload.update({"required_features": []}),
            "successor_local_proof_required_features_invalid",
        ),
    ),
)
def test_manifest_policy_tampering_is_rejected(mutation, error_code):
    manifest = _manifest()
    mutation(manifest)

    with pytest.raises(Gate2SuccessorLocalProofError, match=error_code):
        _receipt(manifest)


def test_manifest_identity_and_factory_boundary_are_explicit():
    manifest = _manifest()
    assert manifest["schema_version"] == (
        LOCAL_PROOF_MANIFEST_SCHEMA_VERSION
    )
    assert tuple(manifest["required_features"]) == REQUIRED_FEATURES
    assert manifest["case_count"] == len(manifest["cases"]) == 11
    assert manifest["contains_customer_data"] is False
    assert "Gate2SuccessorLocalProofFactory.create" in FACTORY_REQUIRED
    assert "must not call providers" in FORBIDDEN

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not {
        module
        for module in modules
        if module.endswith("gate2_provider_adapters")
        or module.endswith("gate2_model_clients")
        or module.endswith("artifact_store")
        or module.endswith("gate2_domain_runtime")
        or module.endswith("gate2_source_fact_runtime")
    }


def test_manifest_literal_conflict_fails_closed():
    manifest = copy.deepcopy(_manifest())
    conflict = copy.deepcopy(manifest["cases"][0]["cells"][2])
    conflict["key"] = "amount_conflict"
    conflict["literal"] = ""
    manifest["cases"][0]["cells"].append(conflict)

    with pytest.raises(
        Gate2SuccessorLocalProofError,
        match="successor_local_proof_fixture_cell_invalid",
    ):
        _receipt(manifest)
