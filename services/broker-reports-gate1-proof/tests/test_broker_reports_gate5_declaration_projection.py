from __future__ import annotations

import ast
import copy
import inspect
from importlib import resources
import json

import pytest

from broker_reports_gate1 import (
    GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE,
    GATE5_DECLARATION_PROJECTION_FRAGMENT_SCHEMA_VERSION,
    GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION,
    GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE,
    Gate5DeclarationProjectionError,
    Gate5DeclarationProjectionRuntime,
    Gate5DeclarationProjectionRuntimeFactory,
)
from broker_reports_gate1 import gate5_declaration_projection as projection_module
from broker_reports_gate1.gate5_declaration_projection import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)


def test_agent_candidate_projects_expected_appendix8_fragment_deterministically() -> (
    None
):
    runtime = Gate5DeclarationProjectionRuntimeFactory.create()

    first = runtime.project(proof_input=_proof_input())
    replayed = Gate5DeclarationProjectionRuntimeFactory.create().project(
        proof_input=_proof_input()
    )

    assert first == replayed
    assert first["schema_version"] == (
        GATE5_DECLARATION_PROJECTION_FRAGMENT_SCHEMA_VERSION
    )
    assert first["status"] == "projected"
    assert first["target"] == {
        "path": "Файл/Документ/НДФЛ3/ДохОперЦБ",
        "element": "ДохОперЦБ",
        "occurrence": 1,
    }
    assert first["attributes"] == {
        "ВидОпер": "01",
        "ДохСовОпер": "100.00",
        "РасхРеалЦБ": "72.00",
        "РасхУмДохОпер": "72.00",
        "ПризУчетУбыт": "0",
    }
    assert first["validation"] == {
        "candidate": "passed",
        "input": "passed",
        "xsd_claim": "structurally_consistent_not_full_xml_validated",
    }
    assert len(first["provenance"]) == 5
    assert all(item["evidence_refs"] for item in first["provenance"])
    assert len(first["projection_binding"]["spec_sha256"]) == 64
    assert len(first["projection_binding"]["evidence_pack_sha256"]) == 64


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    (
        (
            lambda spec: spec["mappings"][0].update(
                source_concept="unknown_tax_model_concept"
            ),
            "gate5_declaration_projection_unknown_source_concept",
        ),
        (
            lambda spec: spec["mappings"].pop(),
            "gate5_declaration_projection_missing_required_mapping",
        ),
        (
            lambda spec: spec["target"].update(
                path="Файл/Документ/НДФЛ3/Несуществующий"
            ),
            "gate5_declaration_projection_invalid_target",
        ),
        (
            lambda spec: spec["mappings"][0]["transform"]["values"].update(
                organized_market_securities_outside_iis="99"
            ),
            "gate5_declaration_projection_unsupported_code",
        ),
        (
            lambda spec: spec["mappings"].append(
                {
                    **copy.deepcopy(spec["mappings"][0]),
                    "mapping_id": "conflicting-second-mapping",
                }
            ),
            "gate5_declaration_projection_conflicting_mapping",
        ),
        (
            lambda spec: spec["mappings"][0]["evidence_refs"].pop(),
            "gate5_declaration_projection_evidence_incomplete",
        ),
    ),
)
def test_invalid_candidate_fails_closed(mutate, expected_code: str) -> None:
    candidate = _resource_json(GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE)
    mutate(candidate)

    with pytest.raises(Gate5DeclarationProjectionError) as caught:
        Gate5DeclarationProjectionRuntimeFactory.create(candidate_spec=candidate)

    assert caught.value.code == expected_code


def test_invalid_or_unsupported_input_produces_no_fragment() -> None:
    runtime = Gate5DeclarationProjectionRuntimeFactory.create()
    missing = _proof_input()
    missing.pop("allowable_expenses")
    with pytest.raises(Gate5DeclarationProjectionError) as missing_error:
        runtime.project(proof_input=missing)
    assert missing_error.value.code == "gate5_declaration_projection_input_invalid"

    unsupported = _proof_input()
    unsupported["operation_category"] = "unreviewed_category"
    with pytest.raises(Gate5DeclarationProjectionError) as enum_error:
        runtime.project(proof_input=unsupported)
    assert enum_error.value.code == (
        "gate5_declaration_projection_input_value_unsupported"
    )

    wrong_currency = _proof_input()
    wrong_currency["operation_category_gross_income"]["currency"] = "USD"
    with pytest.raises(Gate5DeclarationProjectionError) as currency_error:
        runtime.project(proof_input=wrong_currency)
    assert currency_error.value.code == (
        "gate5_declaration_projection_input_value_unsupported"
    )


def test_evidence_pack_is_closed_and_binds_all_official_source_families() -> None:
    evidence = _resource_json(GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE)

    assert evidence["declaration"] == {
        "jurisdiction": "RU",
        "tax_period": "2025",
        "form": "3-NDFL",
        "knd": "1151020",
        "order": "FNS_ED-7-11/913@_2025-10-20",
        "electronic_format_version": "5.20",
        "xsd": "NO_NDFL3_1_033_00_05_20_01.xsd",
    }
    assert {item["source_ref"] for item in evidence["sources"]} == {
        "fns_form_pdf",
        "fns_filling_procedure_docx",
        "fns_electronic_format_docx",
        "fns_xsd_5_20_01",
    }
    assert all(
        item["authority_kind"] == "tax_authority_primary"
        for item in evidence["sources"]
    )
    assert all(len(item["sha256"]) == 64 for item in evidence["sources"])
    assert evidence["target_contract"]["min_occurs"] == 0
    assert evidence["target_contract"]["max_occurs"] == "unbounded"
    assert {item["attribute"] for item in evidence["target_contract"]["fields"]} == {
        "ВидОпер",
        "ДохСовОпер",
        "РасхРеалЦБ",
        "РасхУмДохОпер",
        "ПризУчетУбыт",
    }


def test_projector_has_no_representative_mapping_or_external_runtime_path() -> None:
    factory_source = inspect.getsource(Gate5DeclarationProjectionRuntimeFactory)
    projector_source = inspect.getsource(Gate5DeclarationProjectionRuntime.project)
    module_source = inspect.getsource(projection_module)
    tree = ast.parse(module_source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "Gate5DeclarationProjectionRuntimeFactory.create" in FACTORY_REQUIRED[0]
    assert "Gate5DeclarationProjectionRuntime(" in factory_source
    assert "resources.files" not in projector_source
    for literal in (
        "Файл/Документ/НДФЛ3/ДохОперЦБ",
        "ВидОпер",
        "ДохСовОпер",
        "РасхРеалЦБ",
        "РасхУмДохОпер",
        "ПризУчетУбыт",
        "organized_market_securities_outside_iis",
    ):
        assert literal not in module_source
        assert literal not in projector_source
    assert imported_modules.isdisjoint({"openai", "requests", "httpx", "sqlite3"})
    for forbidden in (
        "Gate4FinancialCaseRuntimeFactory",
        "Gate5ExternalEvidenceRuntimeFactory",
        "Gate5MethodologyCalculationRuntimeFactory",
        "ArtifactStore",
        "CanonicalReader",
    ):
        assert forbidden not in module_source
    assert "best-effort" in FORBIDDEN[2]


def _proof_input() -> dict:
    return {
        "schema_version": GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION,
        "operation_category": "organized_market_securities_outside_iis",
        "operation_category_gross_income": {
            "amount": "100.00",
            "currency": "RUB",
        },
        "related_expenses": {"amount": "72.00", "currency": "RUB"},
        "allowable_expenses": {"amount": "72.00", "currency": "RUB"},
        "loss_treatment": "none",
    }


def _resource_json(resource_name: str) -> dict:
    raw = resources.files("broker_reports_gate1").joinpath(resource_name).read_bytes()
    return json.loads(raw.decode("utf-8"))
