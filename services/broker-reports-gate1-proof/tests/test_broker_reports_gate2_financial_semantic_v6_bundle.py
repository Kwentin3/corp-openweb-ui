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
    EVIDENCE_BUNDLE_POLICY_VERSION,
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2FinancialEvidenceBundleError,
    Gate2FinancialEvidenceBundleFactory,
    validate_financial_evidence_bundle,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"
MODULE_PATH = ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_bundle.py"


def _cases() -> dict[str, dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in payload["cases"]}


def _scope_and_fixture(
    case_id: str = "syn_successor_signed_literal",
):
    fixture = _fixture_package(copy.deepcopy(_cases()[case_id]))
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    scope = (
        Gate2DeterministicFinancialScopeFromGate1V2Factory(registry=registry)
        .create(gate1_packages=(fixture.payload,))
        .scopes[0]
    )
    return scope, fixture


def _bundle(case_id: str = "syn_successor_signed_literal"):
    scope, fixture = _scope_and_fixture(case_id)
    bundle = Gate2FinancialEvidenceBundleFactory().create(
        source_package=scope.source_package,
        gate1_packages=(fixture.payload,),
    )
    return bundle, scope, fixture


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def test_bundle_retains_every_authoritative_value_exactly_once():
    bundle, scope, fixture = _bundle()

    expected_refs = tuple(
        value.source_value_ref for value in scope.source_package.source_values
    )
    observed_refs = tuple(value.source_value_ref for value in bundle.source_values)
    association_refs = tuple(
        ref
        for association in bundle.source_associations
        for ref in association.source_value_refs
    )

    assert bundle.schema_version == EVIDENCE_BUNDLE_SCHEMA_VERSION
    assert bundle.policy_version == EVIDENCE_BUNDLE_POLICY_VERSION
    assert observed_refs == expected_refs
    assert bundle.retention_set == expected_refs
    assert sorted(association_refs) == sorted(expected_refs)
    assert len(association_refs) == len(set(association_refs))
    assert {
        value.source_value_ref: value.literal_value
        for value in bundle.source_values
        if value.value_type != "source_reference"
    } == fixture.selected_literals
    validate_financial_evidence_bundle(
        bundle=bundle,
        source_package=scope.source_package,
    )


def test_bundle_preserves_visible_associations_and_provenance():
    bundle, scope, _ = _bundle()

    table_association = next(
        item
        for item in bundle.source_associations
        if item.association_kind == "table_row"
    )
    deterministic_association = next(
        item
        for item in bundle.source_associations
        if item.association_kind == "deterministic_reference"
    )

    assert len(table_association.source_value_refs) == 4
    assert len(deterministic_association.source_value_refs) == 2
    assert (
        table_association.association_ref == deterministic_association.association_ref
    )
    assert set(scope.source_package.source_evidence_refs).issubset(
        bundle.provenance_refs
    )
    assert all(
        set(value.source_evidence_refs).issubset(bundle.provenance_refs)
        for value in scope.source_package.source_values
    )
    assert all(
        value.lineage.document_ref == bundle.document_ref
        for value in bundle.source_values
    )


def test_bundle_contains_no_financial_type_or_model_authority():
    bundle, _, _ = _bundle("syn_successor_multiple_hypotheses")
    payload = bundle.to_private_dict()
    forbidden_fields = {
        "input_type_id",
        "expected_answer",
        "model_output",
        "typed_decision",
        "role_bindings",
    }

    assert not {
        key for item in _walk_dicts(payload) for key in item if key in forbidden_fields
    }
    assert payload["retention_set"] == sorted(payload["retention_set"])
    assert "SemanticPack" not in MODULE_PATH.read_text(encoding="utf-8")


def test_bundle_is_deterministic_and_safe_summary_is_private():
    first, scope, fixture = _bundle("syn_successor_currency_date")
    second = Gate2FinancialEvidenceBundleFactory().create(
        source_package=scope.source_package,
        gate1_packages=(copy.deepcopy(fixture.payload),),
    )

    assert first == second
    summary = first.safe_summary()
    rendered = json.dumps(summary, sort_keys=True)
    assert summary["source_values_complete_and_exactly_once"] is True
    assert summary["unclassified_retention_code_owned"] is True
    assert summary["contains_source_literals"] is False
    assert summary["contains_source_value_refs"] is False
    assert summary["contains_financial_type_meaning"] is False
    assert summary["provider_calls_total"] == 0
    assert all(value.literal_value not in rendered for value in first.source_values)
    assert all(value.source_value_ref not in rendered for value in first.source_values)


def test_bundle_rejects_missing_or_drifted_visible_context():
    scope, fixture = _scope_and_fixture()
    missing = copy.deepcopy(fixture.payload)
    missing["source_unit"]["model_source_projection"]["rows"][0]["cells"] = missing[
        "source_unit"
    ]["model_source_projection"]["rows"][0]["cells"][1:]
    with pytest.raises(
        Gate2FinancialEvidenceBundleError,
        match="financial_evidence_bundle_visible_context_invalid",
    ):
        Gate2FinancialEvidenceBundleFactory().create(
            source_package=scope.source_package,
            gate1_packages=(missing,),
        )

    drifted = copy.deepcopy(fixture.payload)
    drifted["source_unit"]["model_source_projection"]["rows"][0]["cells"][0][
        "value"
    ] = "changed"
    with pytest.raises(
        Gate2FinancialEvidenceBundleError,
        match="financial_evidence_bundle_visible_context_invalid",
    ):
        Gate2FinancialEvidenceBundleFactory().create(
            source_package=scope.source_package,
            gate1_packages=(drifted,),
        )


def test_bundle_rejects_document_and_integrity_tampering():
    bundle, scope, fixture = _bundle()
    wrong_document = copy.deepcopy(fixture.payload)
    wrong_document["source_unit"]["document_ref"] = "document:other"
    with pytest.raises(
        Gate2FinancialEvidenceBundleError,
        match="financial_evidence_bundle_document_mismatch",
    ):
        Gate2FinancialEvidenceBundleFactory().create(
            source_package=scope.source_package,
            gate1_packages=(wrong_document,),
        )

    tampered = replace(
        bundle,
        retention_set=bundle.retention_set[:-1],
    )
    with pytest.raises(
        Gate2FinancialEvidenceBundleError,
        match="financial_evidence_bundle_source_coverage_invalid",
    ):
        validate_financial_evidence_bundle(
            bundle=tampered,
            source_package=scope.source_package,
        )

    tampered = replace(bundle, integrity_hash="0" * 64)
    with pytest.raises(
        Gate2FinancialEvidenceBundleError,
        match="financial_evidence_bundle_integrity_invalid",
    ):
        validate_financial_evidence_bundle(
            bundle=tampered,
            source_package=scope.source_package,
        )


def test_bundle_factory_and_no_semantic_inspection_are_anchored():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }

    assert "Gate2FinancialEvidenceBundleFactory.create" in FACTORY_REQUIRED
    assert "type IDs" in FORBIDDEN
    assert "re" not in imports
    assert not any(
        "semantic_pack" in module or "evidence_registry" in module
        for module in imported_modules
    )
    assert "if cash" not in source.lower()
    assert "if total" not in source.lower()
    assert "if tax" not in source.lower()
