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
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    FinancialEvidenceValueCandidate,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_typed_admission import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    TYPED_ADMISSION_POLICY_VERSION,
    TYPED_ADMISSION_SCHEMA_VERSION,
    Gate2FinancialEvidenceTypedAdmissionFactory,
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
BUNDLE_PATH = (
    ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
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
        "syn_successor_multiple_hypotheses",
        "syn_successor_explicit_unclassified",
        "syn_successor_missing_optional",
        "syn_successor_adjacent_equal",
        "syn_successor_adjacent_fx",
    ),
)
def test_all_structurally_compatible_types_reach_the_model(case_id):
    scope, _, _ = _scope(_cases()[case_id])

    admission = scope.package["typed_admission"]
    assert admission["candidate_type_ids"] == [
        CASH_TYPE,
        PRINTED_TYPE,
    ]
    assert admission["admitted_type_ids"] == [
        CASH_TYPE,
        PRINTED_TYPE,
    ]
    assert scope.decision_contract.eligible_type_ids == (
        CASH_TYPE,
        PRINTED_TYPE,
    )
    assert _dispositions(scope) == {
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }
    assert admission["filter_kind"] == "generic_structural"
    assert admission["semantic_selection_owner"] == "llm"
    assert admission["financial_language_predicates_total"] == 0
    assert admission["type_specific_admission_branches_total"] == 0


def test_semantically_ambiguous_scope_keeps_structural_typed_branches():
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

    validated = Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=scope.decision_contract
    ).create(raw)
    assert validated.decision.input_type_id == CASH_TYPE


@pytest.mark.parametrize(
    "visible_label",
    (
        "Cash",
        "Printed total",
        "Cash total",
        "Semantically unrelated heading",
    ),
)
def test_financial_words_do_not_change_structural_eligibility(
    visible_label,
):
    baseline, _, _ = _scope(_cases()["syn_successor_signed_literal"])
    case = copy.deepcopy(_cases()["syn_successor_signed_literal"])
    case["case_id"] = "syn_successor_semantic_label_invariance"
    case["cells"][0]["literal"] = visible_label

    scope, _, _ = _scope(case)

    assert scope.package["typed_admission"]["admitted_type_ids"] == [
        CASH_TYPE,
        PRINTED_TYPE,
    ]
    assert scope.package["typed_admission"]["admitted_type_ids"] == (
        baseline.package["typed_admission"]["admitted_type_ids"]
    )


def test_required_role_feasibility_is_generic_and_fail_closed():
    case = _cases()["syn_successor_signed_literal"]
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = _fixture_package(case)
    legacy = Gate2DeterministicFinancialScopeFromGate1Factory(
        registry=registry
    ).create(gate1_packages=(fixture.payload,)).scopes[0]
    candidates = tuple(
        FinancialEvidenceValueCandidate(
            source_value_ref=item.source_value_ref,
            source_ref=item.source_ref,
            value_type=item.value_type,
            allowed_roles=tuple(
                role for role in item.allowed_roles if role != "amount"
            ),
        )
        for item in legacy.decision_contract.package.candidates
    )

    result = Gate2FinancialEvidenceTypedAdmissionFactory(
        registry=registry
    ).create(
        source_scope_ref=legacy.source_package.source_scope_ref,
        source_family_id=legacy.source_package.source_family_id,
        source_values=legacy.source_package.source_values,
        candidates=candidates,
        gate1_packages=(fixture.payload,),
    )

    assert result.candidate_type_ids == (CASH_TYPE, PRINTED_TYPE)
    assert result.admitted_type_ids == ()
    assert result.infeasible_required_roles_total == 2
    assert result.reason_codes == (
        "no_structurally_eligible_types",
        "required_role_feasibility_excluded_types",
    )


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
    assert "only successor structural type-filter authority" in (
        FACTORY_REQUIRED
    )
    assert "must not inspect financial words" in FORBIDDEN
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
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "cash_balance_snapshot_v1",
        "printed_financial_metric_v1",
        "_CASH_SIGNAL_RE",
        "_PRINTED_SIGNAL_RE",
        "_PRINTED_ROW_ROLES",
        "_cash_signal",
        "_printed_signal",
        "row_role",
        "column_meaning",
        "visible_label",
        "re.compile",
    ):
        assert forbidden not in source
    bundle = BUNDLE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "_CASH_SIGNAL_RE",
        "_PRINTED_SIGNAL_RE",
        "_PRINTED_ROW_ROLES",
        "_cash_signal",
        "_printed_signal",
        "cash_positive_discriminator_not_proven",
        "printed_positive_discriminator_not_proven",
        "conflicting_positive_discriminators",
        "unique_positive_discriminator_proven",
    ):
        assert forbidden not in bundle
