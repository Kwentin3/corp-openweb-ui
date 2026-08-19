from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import gate5_declaration_semantic_input as module
from broker_reports_gate1.gate5_declaration_semantic_input import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_DECLARATION_SEMANTIC_BOUNDARY_VERDICT,
    GATE5_DECLARATION_SEMANTIC_INPUT_SCHEMA_VERSION,
    Gate5DeclarationSemanticInputError,
    Gate5DeclarationSemanticInputRuntimeFactory,
)
import test_broker_reports_gate5_declaration_budget_outcome as budget_fixtures
import test_broker_reports_gate5_declaration_financial_investment_results as financial_fixtures
import test_broker_reports_gate5_declaration_income_sources as source_fixtures
import test_broker_reports_gate5_declaration_scope_resolution as scope_fixtures
import test_broker_reports_gate5_declaration_tax_settlement as income_fixtures
import test_broker_reports_gate5_filing_and_party_identity as filing_fixtures
import test_broker_reports_gate5_resolved_declaration_package as package_fixtures


def test_complete_package_compiles_to_minimal_target_independent_semantic_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _complete_package(tmp_path, monkeypatch)
    runtime = Gate5DeclarationSemanticInputRuntimeFactory.create()

    first = runtime.compile(package=package)
    second = runtime.compile(package=copy.deepcopy(package))

    assert first == second
    assert first["schema_version"] == GATE5_DECLARATION_SEMANTIC_INPUT_SCHEMA_VERSION
    assert first["status"] == "DECLARATION_SEMANTIC_INPUT_READY"
    assert GATE5_DECLARATION_SEMANTIC_BOUNDARY_VERDICT == (
        "H2_MINIMAL_SEMANTIC_VIEW"
    )
    assert first["source_binding"]["package_sha256"] == package["package_sha256"]
    assert first["declaration_semantics"] == {
        "definition_id": package["definition_snapshot"]["definition_id"],
        "definition_version": package["definition_snapshot"]["definition_version"],
        "jurisdiction": "RU",
        "declaration_kind": "3-NDFL",
        "tax_period": "2025",
    }
    assert first["completeness"] == {
        "completeness_kind": "supplied_case_evidence_set",
        "real_world_taxpayer_completeness_asserted": False,
    }

    definition_domains = package["definition_snapshot"]["domains"]
    resolutions = package["requirement_resolutions"]
    assert [row["domain_id"] for row in first["domains"]] == [
        row["domain_id"] for row in definition_domains
    ]
    assert [row["semantic_meaning"] for row in first["domains"]] == [
        row["semantic_meaning"] for row in definition_domains
    ]
    assert [row["obligation_refs"] for row in first["domains"]] == [
        row["obligation_refs"] for row in definition_domains
    ]
    assert [row["state"] for row in first["domains"]] == [
        row["state"] for row in resolutions
    ]
    assert sum(row["state"] == "RESOLVED" for row in first["domains"]) == 5
    assert (
        sum(
            row["state"] == "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
            for row in first["domains"]
        )
        == 6
    )
    assert sum(len(row["obligation_refs"]) for row in first["domains"]) == 25
    assert sum(len(row["typed_components"]) for row in first["domains"]) == 5
    assert all(
        set(component)
        == {
            "source_component_contract_id",
            "source_component_sha256",
            "semantic_payload",
            "semantic_payload_sha256",
        }
        for row in first["domains"]
        for component in row["typed_components"]
    )
    assert runtime.validate_semantic_input(semantic_input=first) == first

    serialized = json.dumps(first, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in (
        "component_binding_sha256",
        "component_owner",
        "definition_component_availability",
        "diagnostics",
        '"input_snapshot"',
        '"methodology_binding"',
        '"provenance"',
        '"derivation"',
        '"scope_binding"',
        '"snapshot"',
        "electronic_format_version",
        '"knd"',
        '"order"',
        "xml_element",
        "pdf_field",
        "form_section",
        "form_line",
    ):
        assert forbidden not in serialized


def test_disposable_consumers_need_only_mapping_for_xml_and_pdf_pressure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantic_input = Gate5DeclarationSemanticInputRuntimeFactory.create().compile(
        package=_complete_package(tmp_path, monkeypatch)
    )

    xml_pressure = _representative_semantics(semantic_input)
    pdf_pressure = _representative_semantics(copy.deepcopy(semantic_input))

    assert xml_pressure == pdf_pressure
    assert xml_pressure == {
        "taxpayer_period_status": "resident_individual",
        "income_group_tax_base": {
            "kind": "money",
            "amount": "28.00",
            "currency": "RUB",
        },
        "tax_payable": {"kind": "money", "amount": "4.00", "currency": "RUB"},
        "declaration_disposition": "additional_payment",
        "financial_result_status": "complete",
        "conditional_state": "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
    }


def test_incomplete_package_and_semantic_tamper_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Gate5DeclarationSemanticInputRuntimeFactory.create()
    incomplete_path = tmp_path / "incomplete"
    complete_path = tmp_path / "complete"
    incomplete_path.mkdir()
    complete_path.mkdir()
    with pytest.raises(Gate5DeclarationSemanticInputError) as exc_info:
        runtime.compile(package=package_fixtures._package(incomplete_path, monkeypatch))
    assert exc_info.value.code == "gate5_declaration_semantic_source_package_incomplete"

    value = runtime.compile(package=_complete_package(complete_path, monkeypatch))
    changed = copy.deepcopy(value)
    _domain(changed, "declaration_budget_disposition")["typed_components"][0][
        "semantic_payload"
    ]["kind"] = "refund"
    with pytest.raises(Gate5DeclarationSemanticInputError) as exc_info:
        runtime.validate_semantic_input(semantic_input=changed)
    assert exc_info.value.code == "gate5_declaration_semantic_component_invalid"

    target_leak = copy.deepcopy(value)
    component = _domain(target_leak, "filing_and_party_identity")["typed_components"][0]
    component["semantic_payload"]["xml_element"] = "forbidden-target-locator"
    component["semantic_payload_sha256"] = _sha256(component["semantic_payload"])
    target_leak["semantic_input_sha256"] = _sha256(
        {
            key: item
            for key, item in target_leak.items()
            if key != "semantic_input_sha256"
        }
    )
    with pytest.raises(Gate5DeclarationSemanticInputError) as exc_info:
        runtime.validate_semantic_input(semantic_input=target_leak)
    assert exc_info.value.code == "gate5_declaration_semantic_target_leakage"


def test_factory_and_source_anchors_prevent_new_authority_or_lookup() -> None:
    source = inspect.getsource(module)
    compile_source = inspect.getsource(module.Gate5DeclarationSemanticInputRuntime.compile)
    factory_source = inspect.getsource(
        module.Gate5DeclarationSemanticInputRuntimeFactory
    )
    imports = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert len(FACTORY_REQUIRED) == 2
    assert FORBIDDEN
    assert "create_validation_only()" in factory_source
    assert "validate_package" in compile_source
    assert imports == {"__future__", "typing", "gate5_resolved_declaration_package"}
    for forbidden in (
        "Gate4FinancialCaseRuntimeFactory",
        "SqliteArtifactStoreAdapter",
        "ArtifactResolver",
        "read_case",
        "SELECT ",
        "openai",
    ):
        assert forbidden not in compile_source
    assert "component_owner" not in inspect.getsource(
        module.Gate5DeclarationSemanticInputRuntime.validate_semantic_input
    )


def _complete_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    store, context, operation, initial, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    income = income_fixtures._component(initial["scope_binding"], tax_base)
    sources = source_fixtures._component(initial["scope_binding"], income)
    receipt = scope_fixtures._runtime(store).resolve(
        definition_ref=package_fixtures._definition_ref(),
        scope=scope_fixtures._scope(context),
        typed_component_evidence=[
            package_fixtures._component(operation),
            source_fixtures._component_evidence(sources),
        ],
        assertion_refs=[],
        context=context,
    )
    filing = filing_fixtures._component(receipt["scope_binding"])
    budget = budget_fixtures._component(receipt["scope_binding"], filing, income)
    financial = financial_fixtures._component(
        receipt["scope_binding"],
        tax_base["input_snapshot"]["category_tax_model"],
    )
    return package_fixtures._runtime(store).assemble(
        definition_ref=package_fixtures._definition_ref(),
        scope_receipt=receipt,
        typed_component_snapshots=[
            package_fixtures._component(operation),
            filing_fixtures._component_evidence(filing),
            budget_fixtures._component_evidence(budget),
            income_fixtures._component_evidence(income),
            source_fixtures._component_evidence(sources),
            financial_fixtures._component_evidence(financial),
        ],
        context=context,
    )


def _representative_semantics(value: dict) -> dict:
    filing = _component(value, "filing_and_party_identity")
    income = _component(value, "income_group_tax_results")["group_results"][0]
    budget = _component(value, "declaration_budget_disposition")
    financial = _component(value, "financial_investment_results")
    not_activated = _domain(value, "deduction_claims")
    return {
        "taxpayer_period_status": filing["taxpayer"]["period_status"],
        "income_group_tax_base": income["tax_base"],
        "tax_payable": income["tax_payable"],
        "declaration_disposition": budget["kind"],
        "financial_result_status": financial["category_results"][0]["status"],
        "conditional_state": not_activated["state"],
    }


def _domain(value: dict, domain_id: str) -> dict:
    return next(row for row in value["domains"] if row["domain_id"] == domain_id)


def _component(value: dict, domain_id: str) -> dict:
    components = _domain(value, domain_id)["typed_components"]
    assert len(components) == 1
    return components[0]["semantic_payload"]


def _sha256(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
