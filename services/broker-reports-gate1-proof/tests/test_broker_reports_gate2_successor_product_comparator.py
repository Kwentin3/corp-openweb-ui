from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    Gate2DeterministicFinancialScopeFromGate1Factory,
)
from broker_reports_gate1.gate2_financial_context import (  # noqa: E402
    Gate2FinancialContextProjectionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_successor_product_comparator import (  # noqa: E402
    COMPARATOR_CLASSIFICATIONS,
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2SuccessorProductComparatorFactory,
    Gate2SuccessorProductExpectation,
    Gate2SuccessorScopeObservation,
)
from test_broker_reports_gate2_deterministic_financial_scopes import (  # noqa: E402
    _gate1_package,
)


MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_successor_product_comparator.py"
)


def _registry():
    return Gate2FinancialEvidenceRegistryFactory().create()


def _scope():
    registry = _registry()
    return (
        registry,
        Gate2DeterministicFinancialScopeFromGate1Factory(
            registry=registry
        )
        .create(gate1_packages=(_gate1_package(),))
        .scopes[0],
    )


def _unclassified_output(scope, *, drop_last: bool = False):
    bindings = [
        {
            "role_id": item.allowed_roles[0],
            "source_value_ref": item.source_value_ref,
        }
        for item in scope.decision_contract.package.candidates
    ]
    if drop_last:
        bindings.pop()
    return {
        "decision": {
            "disposition": "unclassified_financial_input",
            "value_bindings": bindings,
            "reason_code": "no_registry_type",
        }
    }


def _no_financial_output():
    return {
        "decision": {
            "disposition": "no_financial_input",
            "reason_code": "non_financial_content",
        }
    }


def _typed_printed_metric_output(scope):
    candidate_by_role = {
        role: item.source_value_ref
        for item in scope.decision_contract.package.candidates
        for role in item.allowed_roles
    }
    return {
        "decision": {
            "disposition": "typed_input",
            "input_type_id": "printed_financial_metric_v1",
            "value_bindings": {
                "amount": candidate_by_role["amount"],
                "printed_label_evidence_ref": candidate_by_role[
                    "printed_label_evidence_ref"
                ],
                "statement_scope": candidate_by_role["statement_scope"],
                "as_of_date": candidate_by_role["as_of_date"],
                "currency": candidate_by_role["currency"],
                "period": None,
                "source_label": candidate_by_role["source_label"],
                "unit": None,
            },
            "reason_code": "typed_supported",
        }
    }


def _artifact(
    registry,
    scope,
    model_output,
    *,
    execution_ref: str = "execution:synthetic",
    validation_ref: str = "validation:synthetic",
):
    validated = Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=scope.decision_contract
    ).create(model_output)
    return (
        Gate2FinancialEvidenceMaterializerFactory(
            registry=registry,
            source_package=scope.source_package,
            execution_metadata=FinancialEvidenceExecutionMetadata(
                execution_ref=execution_ref,
                decision_validation_ref=validation_ref,
            ),
        )
        .create()
        .materialize(validated_decision=validated)
    )


def _context(registry, scope, artifact):
    return Gate2FinancialContextProjectionFactory(
        registry=registry
    ).create(
        materialized_artifacts=(artifact,),
        source_packages=(scope.source_package,),
    )


def _observation(
    scope,
    model_output,
    artifact,
    *,
    expectation=None,
):
    return Gate2SuccessorScopeObservation(
        source_scope_ref=scope.source_package.source_scope_ref,
        model_output=model_output,
        materialized_artifact=artifact,
        execution_ref="execution:synthetic",
        decision_validation_ref="validation:synthetic",
        expectation=expectation,
    )


def _compare(registry, scope, observation, context):
    return Gate2SuccessorProductComparatorFactory(
        registry=registry
    ).create().compare(
        authorized_scopes=(scope,),
        observations=(observation,),
        final_context=context,
    )


def test_product_invariants_pass_without_legacy_graph_exactness():
    registry, scope = _scope()
    output = _unclassified_output(scope)
    artifact = _artifact(registry, scope, output)
    receipt = _compare(
        registry,
        scope,
        _observation(scope, output, artifact),
        _context(registry, scope, artifact),
    )

    assert receipt["status"] == "passed"
    assert all(receipt["checks"].values())
    assert receipt["mismatch_paths"] == []
    assert receipt["metrics"] == {
        "affected_source_refs_total": 0,
        "affected_source_ref_events_total": 0,
        "literal_loss_total": 0,
        "terminal_ownership_gap_total": 0,
        "invented_values_total": 0,
        "duplicate_bindings_total": 0,
        "cross_scope_bindings_total": 0,
        "actual_data_loss_detected": False,
    }
    assert receipt["comparison_boundary"][
        "exact_equality_applied_to"
    ] == [
        "deterministic_materialized_artifacts",
        "deterministic_final_context",
    ]
    assert "legacy_candidate_graph" in receipt["comparison_boundary"][
        "exact_equality_not_applied_to"
    ]
    assert receipt["comparison_boundary"][
        "legacy_benchmark_rewritten"
    ] is False
    encoded = str(receipt)
    assert "120.50" not in encoded
    assert "row:income" not in encoded
    assert scope.source_package.package_ref not in encoded


def test_acceptable_product_alternative_is_visible_but_non_blocking():
    registry, scope = _scope()
    output = _no_financial_output()
    artifact = _artifact(registry, scope, output)
    expectation = Gate2SuccessorProductExpectation(
        expected_disposition="unsupported",
        acceptable_alternative_dispositions=(
            "no_financial_input",
        ),
    )
    receipt = _compare(
        registry,
        scope,
        _observation(
            scope,
            output,
            artifact,
            expectation=expectation,
        ),
        _context(registry, scope, artifact),
    )

    assert receipt["status"] == "passed"
    assert receipt["checks"]["product_expectations_met"] is True
    assert receipt["mismatch_paths"] == [
        "$.scopes[0].decision.disposition"
    ]
    assert receipt["mismatches"][0] == {
        "path": "$.scopes[0].decision.disposition",
        "failure_layer": "semantic",
        "classification": "acceptable_alternative",
        "reason_code": "accepted_equivalent_disposition",
        "affected_source_refs_total": 1,
        "literal_loss_total": 0,
        "terminal_ownership_gap_total": 0,
        "blocking": False,
    }


def test_typed_registry_outcome_is_eligible_and_role_compatible():
    registry, scope = _scope()
    output = _typed_printed_metric_output(scope)
    artifact = _artifact(registry, scope, output)
    expectation = Gate2SuccessorProductExpectation(
        expected_disposition="typed_input",
        expected_input_type_id="printed_financial_metric_v1",
    )
    receipt = _compare(
        registry,
        scope,
        _observation(
            scope,
            output,
            artifact,
            expectation=expectation,
        ),
        _context(registry, scope, artifact),
    )

    assert receipt["status"] == "passed"
    assert receipt["checks"]["eligible_registry_types"]
    assert receipt["checks"]["role_compatibility"]
    assert receipt["checks"]["exact_package_ref_membership"]
    assert receipt["mismatch_paths"] == []


def test_unclassified_value_loss_is_explicit_actual_data_loss():
    registry, scope = _scope()
    output = _unclassified_output(scope, drop_last=True)
    receipt = _compare(
        registry,
        scope,
        _observation(scope, output, {}),
        {},
    )

    assert receipt["status"] == "failed"
    assert (
        receipt["checks"]["unclassified_value_preservation"] is False
    )
    assert (
        receipt["checks"]["deterministic_materialization_exact"] is False
    )
    assert receipt["metrics"]["literal_loss_total"] == 1
    assert receipt["metrics"]["actual_data_loss_detected"] is True
    assert receipt["classification_counts"]["actual_data_loss"] >= 1
    assert receipt["mismatches"][0]["failure_layer"] == "semantic"
    assert receipt["mismatches"][0]["path"] == (
        "$.scopes[0].decision.value_bindings"
    )


def test_materialized_literal_tampering_is_detected_without_value_leak():
    registry, scope = _scope()
    output = _unclassified_output(scope)
    artifact = _artifact(registry, scope, output)
    tampered = copy.deepcopy(artifact)
    tampered["unclassified_inputs"][0]["source_values"][0][
        "literal_value"
    ] = "999.00"
    receipt = _compare(
        registry,
        scope,
        _observation(scope, output, tampered),
        _context(registry, scope, artifact),
    )

    assert receipt["status"] == "failed"
    assert receipt["checks"]["literal_preservation"] is False
    assert (
        receipt["checks"]["deterministic_materialization_exact"] is False
    )
    assert receipt["metrics"]["literal_loss_total"] == 1
    assert receipt["mismatches"][0]["path"] == (
        "$.scopes[0].materialized_artifact"
    )
    assert receipt["mismatches"][0]["classification"] == (
        "actual_data_loss"
    )
    assert "999.00" not in str(receipt)
    assert "120.50" not in str(receipt)


def test_missing_observation_measures_terminal_ownership_gap():
    registry, scope = _scope()
    receipt = Gate2SuccessorProductComparatorFactory(
        registry=registry
    ).create().compare(
        authorized_scopes=(scope,),
        observations=(),
        final_context={},
    )

    assert receipt["status"] == "failed"
    assert receipt["checks"]["terminal_ownership_complete"] is False
    assert receipt["checks"]["final_context_integrity_exact"] is False
    assert receipt["metrics"]["terminal_ownership_gap_total"] == 1
    assert receipt["metrics"]["actual_data_loss_detected"] is True
    assert receipt["mismatch_paths"] == [
        "$.scopes[0].terminal_ownership",
        "$.final_context",
    ]


def test_out_of_package_model_ref_is_classified_model_wrong():
    registry, scope = _scope()
    output = _unclassified_output(scope)
    output["decision"]["value_bindings"][0][
        "source_value_ref"
    ] = "value:outside:scope"
    observation = Gate2SuccessorScopeObservation(
        source_scope_ref=scope.source_package.source_scope_ref,
        model_output=output,
        materialized_artifact={},
        execution_ref="execution:synthetic",
        decision_validation_ref="validation:synthetic",
    )
    receipt = Gate2SuccessorProductComparatorFactory(
        registry=registry
    ).create().compare(
        authorized_scopes=(scope,),
        observations=(observation,),
        final_context={},
    )

    assert receipt["status"] == "failed"
    assert receipt["classification_counts"]["model_wrong"] == 1
    assert receipt["checks"]["invented_values_zero"] is False
    assert receipt["metrics"]["invented_values_total"] == 1
    assert receipt["mismatches"][0]["failure_layer"] == "canonical"
    assert receipt["mismatches"][0]["path"] == "$.scopes[0].decision"
    assert "value:outside:scope" not in str(receipt)


def test_duplicate_model_binding_is_counted_even_when_canonical_rejects():
    registry, scope = _scope()
    output = _unclassified_output(scope)
    output["decision"]["value_bindings"].append(
        copy.deepcopy(output["decision"]["value_bindings"][0])
    )
    observation = Gate2SuccessorScopeObservation(
        source_scope_ref=scope.source_package.source_scope_ref,
        model_output=output,
        materialized_artifact={},
        execution_ref="execution:synthetic",
        decision_validation_ref="validation:synthetic",
    )
    receipt = Gate2SuccessorProductComparatorFactory(
        registry=registry
    ).create().compare(
        authorized_scopes=(scope,),
        observations=(observation,),
        final_context={},
    )

    assert receipt["status"] == "failed"
    assert receipt["checks"]["duplicate_bindings_zero"] is False
    assert receipt["metrics"]["duplicate_bindings_total"] == 1
    assert receipt["classification_counts"]["model_wrong"] == 1


def test_wrong_final_context_is_a_deterministic_context_failure():
    registry, scope = _scope()
    output = _unclassified_output(scope)
    artifact = _artifact(registry, scope, output)
    receipt = _compare(
        registry,
        scope,
        _observation(scope, output, artifact),
        {},
    )

    assert receipt["status"] == "failed"
    assert receipt["checks"]["final_context_integrity_exact"] is False
    assert receipt["mismatch_paths"] == ["$.final_context"]
    assert receipt["mismatches"][0]["failure_layer"] == "context"
    assert receipt["mismatches"][0]["classification"] == "contract_gap"


def test_comparator_factory_boundary_and_no_legacy_runtime_imports():
    assert "Gate2SuccessorProductComparatorFactory.create" in FACTORY_REQUIRED
    assert "exact legacy candidate" in FORBIDDEN
    assert COMPARATOR_CLASSIFICATIONS == (
        "model_wrong",
        "acceptable_alternative",
        "comparator_defect",
        "contract_gap",
        "actual_data_loss",
        "unknown",
    )
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not {
        module
        for module in modules
        if module.endswith("gate2_source_fact_selection")
        or module.endswith("gate2_candidate_binding")
        or module.endswith("gate2_domain_runtime")
        or module.endswith("gate2_source_fact_runtime")
    }
