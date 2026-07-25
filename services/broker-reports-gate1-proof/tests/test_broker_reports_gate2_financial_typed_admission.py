from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION,
    DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2,
    Gate2DeterministicFinancialScope,
    Gate2DeterministicFinancialScopeFromGate1Factory,
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
    validate_deterministic_financial_scope_v2,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_typed_admission import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    TYPED_ADMISSION_POLICY_VERSION,
    TYPED_ADMISSION_SCHEMA_VERSION,
    Gate2FinancialEvidenceTypedAdmissionError,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
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
    / "gate2_financial_evidence_typed_admission.py"
)
CASH_TYPE = "cash_balance_snapshot_v1"
PRINTED_TYPE = "printed_financial_metric_v1"


def _cases() -> dict[str, dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in payload["cases"]}


def _scope(case: dict):
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = _fixture_package(case)
    result = Gate2DeterministicFinancialScopeFromGate1V2Factory(
        registry=registry
    ).create(gate1_packages=(fixture.payload,))
    assert len(result.scopes) == 1
    return result.scopes[0], registry, fixture


def _dispositions(scope) -> set[str]:
    result = set()

    def walk(value):
        if isinstance(value, dict):
            enum = value.get("enum")
            if isinstance(enum, list):
                result.update(
                    item
                    for item in enum
                    if item
                    in {
                        "typed_input",
                        "unclassified_financial_input",
                        "no_financial_input",
                        "unsupported",
                    }
                )
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(scope.decision_contract.canonical_schema())
    return result


@pytest.mark.parametrize(
    "case_id",
    (
        "syn_successor_signed_literal",
        "syn_successor_currency_date",
        "syn_successor_forbidden_neighbour",
    ),
)
def test_unique_cash_discriminator_admits_only_cash(case_id):
    scope, _, _ = _scope(_cases()[case_id])

    admission = scope.package["typed_admission"]
    assert admission["admitted_type_ids"] == [CASH_TYPE]
    assert scope.decision_contract.eligible_type_ids == (CASH_TYPE,)
    assert _dispositions(scope) == {
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }


@pytest.mark.parametrize(
    "case_id",
    (
        "syn_successor_multiple_hypotheses",
        "syn_successor_explicit_unclassified",
        "syn_successor_missing_optional",
        "syn_successor_adjacent_equal",
        "syn_successor_adjacent_fx",
    ),
)
def test_unproven_or_ambiguous_scope_has_no_typed_branch(case_id):
    scope, _, _ = _scope(_cases()[case_id])

    admission = scope.package["typed_admission"]
    assert admission["admitted_type_ids"] == []
    assert scope.decision_contract.eligible_type_ids == ()
    assert _dispositions(scope) == {
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }


def test_removed_typed_branch_is_rejected_by_canonical_contract():
    scope, _, fixture = _scope(
        _cases()["syn_successor_multiple_hypotheses"]
    )
    refs = fixture.selected_value_refs
    raw = {
        "decision": {
            "disposition": "typed_input",
            "input_type_id": CASH_TYPE,
            "value_bindings": {
                "amount": refs["amount_a"],
                "as_of_date": refs["date"],
                "statement_scope": next(
                    candidate.source_value_ref
                    for candidate in (
                        scope.decision_contract.package.candidates
                    )
                    if "statement_scope" in candidate.allowed_roles
                ),
                "balance_class": None,
                "currency": refs["currency"],
                "source_label": refs["label_a"],
                "unit": None,
            },
            "reason_code": "typed_supported",
        }
    }

    with pytest.raises(ValueError):
        Gate2FinancialEvidenceValidatedDecisionFactory(
            contract=scope.decision_contract
        ).create(raw)


def test_printed_total_positive_discriminator_admits_only_printed():
    case = copy.deepcopy(_cases()["syn_successor_signed_literal"])
    case["case_id"] = "syn_successor_printed_total_admission"
    case["cells"][0]["literal"] = "Printed total"

    scope, _, _ = _scope(case)

    assert scope.package["typed_admission"]["admitted_type_ids"] == [
        PRINTED_TYPE
    ]
    assert scope.decision_contract.eligible_type_ids == (PRINTED_TYPE,)


def test_conflicting_cash_and_total_discriminators_admit_no_type():
    case = copy.deepcopy(_cases()["syn_successor_signed_literal"])
    case["case_id"] = "syn_successor_conflicting_admission"
    case["cells"][0]["literal"] = "Cash total"

    scope, _, _ = _scope(case)

    admission = scope.package["typed_admission"]
    assert admission["admitted_type_ids"] == []
    assert "conflicting_positive_discriminators" in admission[
        "reason_codes"
    ]


def test_v2_identity_and_admission_integrity_are_revalidated():
    scope, _, _ = _scope(_cases()["syn_successor_signed_literal"])
    assert (
        scope.package["schema_version"]
        == DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2
    )
    tampered_package = copy.deepcopy(scope.package)
    tampered_package["typed_admission"]["reason_codes"].append(
        "tampered"
    )
    tampered_package.pop("integrity_hash")
    from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E501
        sha256_json,
    )

    tampered_package["integrity_hash"] = sha256_json(tampered_package)
    tampered = Gate2DeterministicFinancialScope(
        package=tampered_package,
        decision_contract=scope.decision_contract,
        source_package=scope.source_package,
        selected_source_refs=scope.selected_source_refs,
    )
    with pytest.raises(
        Gate2FinancialEvidenceTypedAdmissionError,
        match="typed_admission_integrity_invalid",
    ):
        validate_deterministic_financial_scope_v2(tampered)


def test_v1_scope_contract_remains_unchanged():
    case = _cases()["syn_successor_signed_literal"]
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = _fixture_package(case)

    scope = Gate2DeterministicFinancialScopeFromGate1Factory(
        registry=registry
    ).create(gate1_packages=(fixture.payload,)).scopes[0]

    assert (
        scope.package["schema_version"]
        == DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION
    )
    assert scope.decision_contract.eligible_type_ids == (
        CASH_TYPE,
        PRINTED_TYPE,
    )
    assert "typed_admission" not in scope.package


def test_v2_is_deterministic_and_safe_summary_is_value_free():
    case = _cases()["syn_successor_signed_literal"]
    first, _, first_fixture = _scope(case)
    second, _, _ = _scope(copy.deepcopy(case))

    assert first.package == second.package
    summary = first.package["typed_admission"].copy()
    summary.pop("source_scope_ref")
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    assert all(
        literal not in rendered
        for literal in first_fixture.selected_literals.values()
    )
    assert all(
        ref not in rendered
        for ref in first_fixture.selected_literals
    )
    assert summary["contains_source_literals"] is False
    assert summary["contains_source_value_refs"] is False
    assert summary["provider_calls_total"] == 0
    assert summary["post_response_conversion"] is False
    assert summary["schema_version"] == TYPED_ADMISSION_SCHEMA_VERSION
    assert summary["policy_version"] == TYPED_ADMISSION_POLICY_VERSION


def test_admission_factory_is_code_owned_and_has_no_provider_dependency():
    assert "only successor typed-branch admission authority" in (
        FACTORY_REQUIRED
    )
    assert "must not call a model" in FORBIDDEN
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not {
        name
        for name in imported_modules
        if "provider" in name
        or "model_client" in name
        or "production_runtime" in name
    }
