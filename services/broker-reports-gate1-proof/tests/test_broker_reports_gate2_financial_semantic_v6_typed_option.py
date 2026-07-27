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
from broker_reports_gate1.gate2_financial_semantic_v6_typed_option import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    MATERIALIZABILITY_RECEIPT_SCHEMA_VERSION,
    STRUCTURAL_RECEIPT_SCHEMA_VERSION,
    TYPED_OPTION_SCHEMA_VERSION,
    Gate2FinancialTypedOptionError,
    Gate2FinancialTypedOptionFactory,
    validate_financial_typed_option,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"
MODULE_PATH = (
    ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_typed_option.py"
)


def _cases() -> dict[str, dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in payload["cases"]}


def _authorities(
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
    return registry, scope, bundle, fixture


def _reference(bundle, suffix: str) -> str:
    return next(
        value.source_value_ref
        for value in bundle.source_values
        if value.source_value_ref.endswith(suffix)
    )


def _cash_bindings(bundle, fixture):
    return {
        "amount": fixture.selected_value_refs["amount"],
        "as_of_date": fixture.selected_value_refs["date"],
        "statement_scope": _reference(
            bundle,
            "statement-scope",
        ),
        "balance_class": None,
        "currency": fixture.selected_value_refs.get("currency"),
        "source_label": fixture.selected_value_refs.get("label"),
        "unit": None,
    }


def _option(
    case_id: str = "syn_successor_signed_literal",
):
    registry, scope, bundle, fixture = _authorities(case_id)
    option = Gate2FinancialTypedOptionFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
        input_type_id="cash_balance_snapshot_v1",
        role_bindings=_cash_bindings(bundle, fixture),
    )
    return option, registry, scope, bundle, fixture


def test_option_is_prebound_and_fully_materializable():
    option, registry, scope, bundle, _ = _option()

    assert option.schema_version == TYPED_OPTION_SCHEMA_VERSION
    assert option.evidence_bundle_id == bundle.bundle_id
    assert option.input_type_id == "cash_balance_snapshot_v1"
    assert set(option.required_roles) <= {item.role_id for item in option.role_bindings}
    assert option.structural_compatibility_receipt.schema_version == (
        STRUCTURAL_RECEIPT_SCHEMA_VERSION
    )
    assert option.structural_compatibility_receipt.status == "compatible"
    assert option.structural_compatibility_receipt.associations_total == 1
    assert len(option.structural_compatibility_receipt.type_contract_hash) == 64
    assert (
        option.materializability_receipt.schema_version
        == MATERIALIZABILITY_RECEIPT_SCHEMA_VERSION
    )
    assert option.materializability_receipt.status == "materializable"
    assert option.materializability_receipt.typed_inputs_total == 1
    assert option.materializability_receipt.unclassified_inputs_total == 0
    assert option.materializability_receipt.provider_calls_total == 0
    validate_financial_typed_option(
        option=option,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        registry=registry,
    )


def test_option_is_deterministic_and_safe_summary_hides_bindings():
    first, registry, scope, bundle, fixture = _option("syn_successor_currency_date")
    second = Gate2FinancialTypedOptionFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
        input_type_id="cash_balance_snapshot_v1",
        role_bindings=_cash_bindings(bundle, fixture),
    )

    assert first == second
    summary = first.safe_summary()
    rendered = json.dumps(summary, sort_keys=True)
    assert summary["required_roles_complete"] is True
    assert summary["model_generated_refs_total"] == 0
    assert summary["model_generated_roles_total"] == 0
    assert summary["contains_source_literals"] is False
    assert summary["contains_source_value_refs"] is False
    assert summary["provider_calls_total"] == 0
    assert all(
        binding.source_value_ref not in rendered for binding in first.role_bindings
    )


def test_option_rejects_missing_external_and_incompatible_bindings():
    registry, scope, bundle, fixture = _authorities()
    factory = Gate2FinancialTypedOptionFactory(registry=registry)

    missing = _cash_bindings(bundle, fixture)
    missing["amount"] = None
    with pytest.raises(
        Gate2FinancialTypedOptionError,
        match="financial_typed_option_required_role_missing",
    ):
        factory.create(
            evidence_bundle=bundle,
            source_package=scope.source_package,
            input_type_id="cash_balance_snapshot_v1",
            role_bindings=missing,
        )

    external = _cash_bindings(bundle, fixture)
    external["amount"] = "value:outside:bundle"
    with pytest.raises(
        Gate2FinancialTypedOptionError,
        match="financial_typed_option_binding_outside_bundle",
    ):
        factory.create(
            evidence_bundle=bundle,
            source_package=scope.source_package,
            input_type_id="cash_balance_snapshot_v1",
            role_bindings=external,
        )

    incompatible = _cash_bindings(bundle, fixture)
    incompatible["amount"] = fixture.selected_value_refs["date"]
    with pytest.raises(
        Gate2FinancialTypedOptionError,
        match="financial_typed_option_binding_incompatible",
    ):
        factory.create(
            evidence_bundle=bundle,
            source_package=scope.source_package,
            input_type_id="cash_balance_snapshot_v1",
            role_bindings=incompatible,
        )


def test_option_rejects_duplicate_refs_and_unknown_pack_type():
    registry, scope, bundle, fixture = _authorities()
    factory = Gate2FinancialTypedOptionFactory(registry=registry)
    bindings = {
        "amount": fixture.selected_value_refs["amount"],
        "printed_label_evidence_ref": _reference(
            bundle,
            "statement-scope",
        ),
        "statement_scope": _reference(
            bundle,
            "statement-scope",
        ),
        "as_of_date": fixture.selected_value_refs["date"],
        "currency": fixture.selected_value_refs["currency"],
        "period": None,
        "source_label": fixture.selected_value_refs["label"],
        "unit": None,
    }
    with pytest.raises(
        Gate2FinancialTypedOptionError,
        match="financial_typed_option_binding_ref_duplicate",
    ):
        factory.create(
            evidence_bundle=bundle,
            source_package=scope.source_package,
            input_type_id="printed_financial_metric_v1",
            role_bindings=bindings,
        )

    with pytest.raises(
        Gate2FinancialTypedOptionError,
        match="financial_typed_option_type_not_in_pack",
    ):
        factory.create(
            evidence_bundle=bundle,
            source_package=scope.source_package,
            input_type_id="unknown_type_v1",
            role_bindings={},
        )


def test_option_rejects_tampered_receipt_and_integrity():
    option, registry, scope, bundle, _ = _option()
    tampered_receipt = replace(
        option.structural_compatibility_receipt,
        status="tampered",
    )
    tampered = replace(
        option,
        structural_compatibility_receipt=tampered_receipt,
    )
    with pytest.raises(
        Gate2FinancialTypedOptionError,
        match="financial_typed_option_structural_receipt_invalid",
    ):
        validate_financial_typed_option(
            option=tampered,
            evidence_bundle=bundle,
            source_package=scope.source_package,
            registry=registry,
        )

    tampered = replace(option, integrity_hash="0" * 64)
    with pytest.raises(
        Gate2FinancialTypedOptionError,
        match="financial_typed_option_integrity_invalid",
    ):
        validate_financial_typed_option(
            option=tampered,
            evidence_bundle=bundle,
            source_package=scope.source_package,
            registry=registry,
        )


def test_option_module_has_no_type_specific_financial_semantics():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "Gate2FinancialTypedOptionFactory.create" in FACTORY_REQUIRED
    assert "concrete type IDs" in FORBIDDEN
    assert "re" not in imports
    assert "cash_balance_snapshot_v1" not in source
    assert "printed_financial_metric_v1" not in source
    assert "if cash" not in source.lower()
    assert "if total" not in source.lower()
    assert "if tax" not in source.lower()
