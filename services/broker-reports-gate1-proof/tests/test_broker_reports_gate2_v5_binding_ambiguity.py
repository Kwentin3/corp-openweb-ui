from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402,E501
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402,E501
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_source_context import (  # noqa: E402,E501
    Gate2FinancialEvidenceSourceContextFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_ambiguity import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    V5_BINDING_AMBIGUITY_POLICY_VERSION,
    Gate2FinancialSemanticV5AmbiguityGuardFactory,
    Gate2StructuralBindingCandidate,
    structurally_equivalent_for_required_role,
)
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ProjectionFactory,
)
from broker_reports_gate1.gate2_successor_local_proof_v2 import (  # noqa: E402,E501
    _fixture_package,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
SOURCE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_ambiguity.py"
)


def _manifest_cases():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in manifest["cases"]}


def _case_candidates(case_id: str):
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = _fixture_package(
        copy.deepcopy(_manifest_cases()[case_id])
    )
    scope = Gate2DeterministicFinancialScopeFromGate1V2Factory(
        registry=registry
    ).create(gate1_packages=(fixture.payload,)).scopes[0]
    context = Gate2FinancialEvidenceSourceContextFactory().create(
        source_scope_ref=scope.source_package.source_scope_ref,
        source_values=scope.source_package.source_values,
        candidates=scope.decision_contract.package.candidates,
        gate1_packages=(fixture.payload,),
    )
    candidate_by_ref = {
        item.source_value_ref: item
        for item in scope.decision_contract.package.candidates
    }
    result = []
    for group_index, group in enumerate(context.provider_groups()):
        for value in group["values"]:
            candidate = candidate_by_ref[value["source_value_ref"]]
            result.append(
                Gate2StructuralBindingCandidate(
                    source_value_ref=candidate.source_value_ref,
                    association_unit_id=f"group:{group_index}",
                    value_type=candidate.value_type,
                    allowed_roles=candidate.allowed_roles,
                    authoritative_selector=None,
                    model_visible_association=None,
                )
            )
    return tuple(result)


def _guard(case_id: str, candidates=None):
    return Gate2FinancialSemanticV5AmbiguityGuardFactory().create(
        projection=Gate2FinancialSemanticV5ProjectionFactory().create(),
        candidates=candidates or _case_candidates(case_id),
    )


def test_adjacent_equal_typed_branches_are_unrepresentable():
    result = _guard("syn_successor_v2_adjacent_equal")

    assert result.available_type_cards == ()
    assert result.blocked_type_ids == (
        "cash_balance_snapshot_v1",
        "printed_financial_metric_v1",
    )
    assert result.blocked_required_roles == {
        "cash_balance_snapshot_v1": ("amount",),
        "printed_financial_metric_v1": ("amount",),
    }
    assert result.post_response_repair_allowed is False
    assert result.policy_version == V5_BINDING_AMBIGUITY_POLICY_VERSION
    assert len(result.policy_hash) == 64
    assert len(result.guard_input_hash) == 64


@pytest.mark.parametrize(
    "case_id",
    [
        "syn_successor_v2_multiple_compatible",
        "syn_successor_v2_adjacent_fx",
    ],
)
def test_other_same_unit_required_role_ambiguity_is_also_blocked(case_id):
    result = _guard(case_id)

    assert result.available_type_cards == ()
    assert all(
        roles == ("amount",)
        for roles in result.blocked_required_roles.values()
    )


def test_unique_required_bindings_leave_semantic_choice_to_model():
    result = _guard("syn_successor_v2_unique_cash")

    assert len(result.available_type_cards) == 2
    assert result.blocked_type_ids == ()
    assert result.blocked_required_roles == {}
    assert all(
        result.typed_branch_available(card["input_type_id"])
        for card in result.available_type_cards
    )
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not inspect literals" in FORBIDDEN


@pytest.mark.parametrize(
    "distinction_field",
    ["association_unit_id", "authoritative_selector", "model_visible_association"],
)
def test_authoritative_structural_distinction_preserves_typed_branch(
    distinction_field,
):
    candidates = list(_case_candidates("syn_successor_v2_adjacent_equal"))
    amount_indexes = [
        index
        for index, item in enumerate(candidates)
        if "amount" in item.allowed_roles
    ]
    assert len(amount_indexes) == 2
    index = amount_indexes[1]
    candidates[index] = replace(
        candidates[index],
        **{distinction_field: "distinct:selector"},
    )

    result = _guard(
        "syn_successor_v2_adjacent_equal",
        tuple(candidates),
    )
    assert len(result.available_type_cards) == 2
    assert result.blocked_type_ids == ()


@pytest.mark.parametrize(
    "role_id,value_type",
    [
        ("amount", "source_decimal"),
        ("date", "source_date"),
        ("currency", "source_currency"),
        ("quantity", "source_decimal"),
        ("price", "source_decimal"),
        ("instrument_identifier", "source_text"),
    ],
)
def test_equivalence_rule_is_role_and_value_type_generic(
    role_id,
    value_type,
):
    left = Gate2StructuralBindingCandidate(
        source_value_ref="value:left",
        association_unit_id="unit:one",
        value_type=value_type,
        allowed_roles=(role_id,),
    )
    right = Gate2StructuralBindingCandidate(
        source_value_ref="value:right",
        association_unit_id="unit:one",
        value_type=value_type,
        allowed_roles=(role_id,),
    )

    assert structurally_equivalent_for_required_role(
        role_id=role_id,
        left=left,
        right=right,
    )
    assert not structurally_equivalent_for_required_role(
        role_id=role_id,
        left=left,
        right=replace(
            right,
            authoritative_selector="selector:right",
        ),
    )


def test_ambiguity_guard_contains_no_type_specific_predicates_or_repair():
    source = SOURCE_PATH.read_text(encoding="utf-8").casefold()
    for forbidden in (
        "cash_balance_snapshot",
        "printed_financial_metric",
        "tax",
        "fee",
        "dividend",
        "commission",
        "expected_answer",
        "import re",
        "re.compile",
        "typed_to_unclassified",
    ):
        assert forbidden not in source
