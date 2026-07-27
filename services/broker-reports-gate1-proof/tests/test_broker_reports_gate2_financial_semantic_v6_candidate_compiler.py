from __future__ import annotations

import ast
import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_bundle import (  # noqa: E402
    Gate2FinancialEvidenceBundleFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_candidate_compiler import (  # noqa: E402,E501
    CANDIDATE_COMPILATION_SCHEMA_VERSION,
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2FinancialCandidateCompilerError,
    Gate2FinancialCandidateCompilerFactory,
    validate_financial_candidate_compilation,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"
MODULE_PATH = (
    ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_candidate_compiler.py"
)


def _cases() -> dict[str, dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in payload["cases"]}


def _compilation(
    case_id: str = "syn_successor_signed_literal",
):
    fixture = _fixture_package(copy.deepcopy(_cases()[case_id]))
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    scope = (
        Gate2DeterministicFinancialScopeFromGate1V2Factory(registry=registry)
        .create(gate1_packages=(fixture.payload,))
        .scopes[0]
    )
    bundle = Gate2FinancialEvidenceBundleFactory().create(
        source_package=scope.source_package,
        gate1_packages=(fixture.payload,),
    )
    compilation = Gate2FinancialCandidateCompilerFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
    )
    return compilation, registry, scope, bundle


def test_unique_record_compiles_only_materializable_typed_options():
    compilation, registry, scope, bundle = _compilation()

    assert compilation.schema_version == CANDIDATE_COMPILATION_SCHEMA_VERSION
    assert compilation.evidence_bundle_id == bundle.bundle_id
    assert len(compilation.typed_options) == 2
    assert len({item.typed_option_id for item in compilation.typed_options}) == 2
    assert all(
        item.materializability_receipt.status == "materializable"
        for item in compilation.typed_options
    )
    assert compilation.blocked_bindings == ()
    validate_financial_candidate_compilation(
        compilation=compilation,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        registry=registry,
    )


def test_adjacent_equal_has_bundle_and_zero_typed_options():
    compilation, _, _, bundle = _compilation("syn_successor_adjacent_equal")

    assert bundle.source_values
    assert compilation.typed_options == ()
    assert len(compilation.blocked_bindings) == 2
    assert all(
        item.blocked_required_roles == ("amount",)
        for item in compilation.blocked_bindings
    )
    assert all(
        item.reason_code == "candidate_compiler_required_binding_ambiguous"
        for item in compilation.blocked_bindings
    )


@pytest.mark.parametrize(
    "case_id",
    [
        "syn_successor_detail_vs_subtotal",
        "syn_successor_adjacent_fx",
        "syn_successor_multiple_hypotheses",
    ],
)
def test_other_equal_required_candidates_are_not_guessed(case_id):
    compilation, _, _, _ = _compilation(case_id)

    assert compilation.typed_options == ()
    assert all(
        "amount" in item.blocked_required_roles for item in compilation.blocked_bindings
    )


def test_compilation_is_deterministic_and_safe_summary_hides_private_refs():
    first, registry, scope, bundle = _compilation("syn_successor_currency_date")
    second = Gate2FinancialCandidateCompilerFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
    )

    assert first == second
    summary = first.safe_summary()
    rendered = json.dumps(summary, sort_keys=True)
    assert summary["typed_options_total"] == 2
    assert summary["source_literals_inspected"] is False
    assert summary["visible_labels_inspected"] is False
    assert summary["financial_word_rules_total"] == 0
    assert summary["type_specific_branches_total"] == 0
    assert summary["provider_calls_total"] == 0
    assert all(value.source_value_ref not in rendered for value in bundle.source_values)


def test_compilation_validator_rejects_tampering():
    compilation, registry, scope, bundle = _compilation()
    tampered = replace(compilation, integrity_hash="0" * 64)

    with pytest.raises(
        Gate2FinancialCandidateCompilerError,
        match="financial_candidate_compilation_integrity_invalid",
    ):
        validate_financial_candidate_compilation(
            compilation=tampered,
            evidence_bundle=bundle,
            source_package=scope.source_package,
            registry=registry,
        )


def test_compiler_has_no_type_specific_or_literal_inspection():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }

    assert "Gate2FinancialCandidateCompilerFactory.create" in FACTORY_REQUIRED
    assert "concrete type IDs" in FORBIDDEN
    assert "re" not in imports
    assert "cash_balance_snapshot_v1" not in source
    assert "printed_financial_metric_v1" not in source
    assert "literal_value" not in attributes
    assert "visible_label" not in attributes
    assert "if cash" not in source.casefold()
    assert "if total" not in source.casefold()
    assert "if tax" not in source.casefold()
