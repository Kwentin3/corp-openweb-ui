from __future__ import annotations

import ast
import copy
import hashlib
import inspect
from importlib import resources
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from broker_reports_gate1 import (
    GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE,
    GATE5_DECLARATION_PROJECTION_FRAGMENT_SCHEMA_VERSION,
    GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION,
    GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE,
    GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE_SHA256,
    GATE5_DECLARATION_PROJECTION_SECTION2_ID,
    GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE,
    GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE_SHA256,
    GATE5_DECLARATION_PROJECTION_SECTION2_VERSION,
    GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE,
    GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION,
    GATE5_DECLARATION_PROJECTION_V1_REF_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
    Gate5DeclarationProjectionError,
    Gate5DeclarationProjectionRuntime,
    Gate5DeclarationProjectionRuntimeFactory,
    Gate5DeclarationProjectionRuntimeV1Factory,
    Gate5IncomeGroupTaxBaseRuntimeFactory,
)
from broker_reports_gate1 import gate5_declaration_projection as projection_module
from broker_reports_gate1.gate5_declaration_projection import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
import test_broker_reports_gate5_income_group_tax_base as tax_base_fixtures


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"


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


def test_section2_projection_consumes_real_tax_model_without_recalculation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, category = tax_base_fixtures._complete_category(
        tmp_path, monkeypatch
    )
    tax_model_owner = Gate5IncomeGroupTaxBaseRuntimeFactory.create()
    status = tax_base_fixtures._tagged(
        "resident_individual", "taxpayer-status", "taxpayer_status"
    )
    values = tax_base_fixtures._group_values(
        other_income="10.00",
        other_expenses="4.00",
        non_taxable="5.00",
        deductions="3.00",
    )
    binding = tax_model_owner.describe_input(
        category_tax_model=category,
        taxpayer_status=status,
        group_values=values,
    )
    tax_model = tax_model_owner.run(
        methodology_ref=tax_base_fixtures._methodology_ref(),
        behavior_input=tax_base_fixtures._behavior_input(
            category=category,
            status=status,
            values=values,
            binding_sha256=binding["input_binding_sha256"],
        ),
    )
    runtime = Gate5DeclarationProjectionRuntimeV1Factory.create()

    first = runtime.project(
        projection_ref=_section2_projection_ref(),
        declaration_semantics=tax_model,
    )
    replayed = Gate5DeclarationProjectionRuntimeV1Factory.create().project(
        projection_ref=_section2_projection_ref(),
        declaration_semantics=tax_model,
    )

    assert first == replayed
    assert first["schema_version"] == (
        GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION
    )
    assert first["source_binding"]["input_contract"] == (
        GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION
    )
    assert first["fragment"] == {
        "element": "НалБаза",
        "attributes": {"ГрупДоход": "02"},
        "children": [
            {
                "element": "РасчНалБаза",
                "attributes": {
                    "СумДох": "160.00",
                    "СумДохНеНал": "5.00",
                    "СумДохНал": "155.00",
                    "СумНалВыч": "3.00",
                    "СумРасх": "104.00",
                    "НалБаза": "48.00",
                },
            }
        ],
    }
    assert "003" not in json.dumps(first["fragment"], ensure_ascii=False)
    assert first["validation"] == {
        "projection_definition": "passed",
        "upstream_tax_model": "owner_revalidated",
        "required_mappings": "passed",
        "xsd_claim": "partial_section2_fragment_not_full_xml_validated",
    }
    assert len(first["provenance"]) == 7
    assert all(
        set(item) == {"source", "rule", "target"}
        and item["source"]["trace"]
        and item["rule"]["evidence_refs"]
        for item in first["provenance"]
    )


def test_versioned_project_keeps_the_published_appendix8_artifact_executable() -> (
    None
):
    result = Gate5DeclarationProjectionRuntimeV1Factory.create().project(
        projection_ref={
            "schema_version": GATE5_DECLARATION_PROJECTION_V1_REF_SCHEMA_VERSION,
            "projection_id": "ru-3ndfl-2025-appendix8-securities-proof",
            "projection_version": "2026.0-proof",
        },
        declaration_semantics=_proof_input(),
    )

    assert result["schema_version"] == (
        GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION
    )
    assert result["fragment"] == {
        "element": "ДохОперЦБ",
        "attributes": {
            "ВидОпер": "01",
            "ДохСовОпер": "100.00",
            "РасхРеалЦБ": "72.00",
            "РасхУмДохОпер": "72.00",
            "ПризУчетУбыт": "0",
        },
        "children": [],
    }


def test_section2_projection_classification_is_versioned_evidence_not_runtime_code() -> (
    None
):
    spec = _resource_json(GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE)
    evidence = _resource_json(GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE)
    classification = evidence["classification_binding"]

    assert classification == {
        "income_group_semantic": "resident_securities_and_derivatives_non_iis",
        "income_group_code": "02",
        "income_type_code": "003",
        "income_type_projection_scope": "evidence_only_not_section2_target",
        "evidence_ref": "securities_income_group_02_type_003",
    }
    target_attributes = {
        field["attribute"]
        for node in evidence["target_contract"]["nodes"]
        for field in node["fields"]
    }
    assert target_attributes == {
        "ГрупДоход",
        "СумДох",
        "СумДохНеНал",
        "СумДохНал",
        "СумНалВыч",
        "СумРасх",
        "НалБаза",
    }
    assert all(
        mapping["source_concept"] != "income_type_code"
        for mapping in spec["mappings"]
    )
    module_source = inspect.getsource(projection_module)
    for declaration_literal in target_attributes | {"02", "003"}:
        assert f'"{declaration_literal}"' not in module_source


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        (
            lambda spec, _evidence: spec["mappings"].append(
                {
                    **copy.deepcopy(spec["mappings"][0]),
                    "mapping_id": "ambiguous-second-income-group-mapping",
                }
            ),
            "gate5_declaration_projection_conflicting_mapping",
        ),
        (
            lambda spec, _evidence: spec["mappings"].pop(),
            "gate5_declaration_projection_missing_required_mapping",
        ),
        (
            lambda spec, evidence: _mutate_classification_mapping(spec, evidence),
            "gate5_declaration_projection_classification_incompatible",
        ),
    ),
)
def test_section2_definition_ambiguity_or_incompatible_mapping_fails_closed(
    mutation,
    expected_code: str,
) -> None:
    spec = _resource_json(GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE)
    evidence = _resource_json(GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE)
    mutation(spec, evidence)

    with pytest.raises(Gate5DeclarationProjectionError) as caught:
        projection_module._validate_v1_projection(
            spec=spec,
            evidence=evidence,
            expected_identity=(
                GATE5_DECLARATION_PROJECTION_SECTION2_ID,
                GATE5_DECLARATION_PROJECTION_SECTION2_VERSION,
            ),
        )

    assert caught.value.code == expected_code


def test_section2_projection_rejects_unknown_artifact_and_tampered_upstream_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Gate5DeclarationProjectionRuntimeV1Factory.create()
    with pytest.raises(Gate5DeclarationProjectionError) as missing:
        runtime.project(
            projection_ref={
                **_section2_projection_ref(),
                "projection_version": "unpublished-version",
            },
            declaration_semantics={},
        )
    assert missing.value.code == "gate5_declaration_projection_artifact_unavailable"

    _store, _context, category = tax_base_fixtures._complete_category(
        tmp_path, monkeypatch
    )
    tax_model = tax_base_fixtures.Gate5IncomeGroupTaxBaseRuntimeFactory.create().run(
        methodology_ref=tax_base_fixtures._methodology_ref(),
        behavior_input=tax_base_fixtures._valid_input(category),
    )
    tax_model["tax_base"]["value"]["amount"] = "999.00"
    with pytest.raises(Gate5DeclarationProjectionError) as tampered:
        runtime.project(
            projection_ref=_section2_projection_ref(),
            declaration_semantics=tax_model,
        )
    assert tampered.value.code == (
        "gate5_declaration_projection_upstream_semantics_invalid"
    )


def test_section2_projection_resources_are_hash_pinned_and_closed_world(
    tmp_path: Path,
) -> None:
    for resource_name, expected_sha256 in (
        (
            GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE,
            GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE_SHA256,
        ),
        (
            GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE,
            GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE_SHA256,
        ),
    ):
        raw = (PACKAGE_ROOT / resource_name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected_sha256

    package_copy = tmp_path / "broker_reports_gate1"
    shutil.copytree(
        PACKAGE_ROOT,
        package_copy,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    script = """
from broker_reports_gate1 import Gate5DeclarationProjectionRuntimeV1Factory
r=Gate5DeclarationProjectionRuntimeV1Factory.create()
print(type(r).__name__)
"""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "Gate5DeclarationProjectionRuntimeV1"


def test_section2_projection_evidence_hash_drift_fails_in_closed_copy(
    tmp_path: Path,
) -> None:
    package_copy = tmp_path / "broker_reports_gate1"
    shutil.copytree(
        PACKAGE_ROOT,
        package_copy,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    resource = package_copy / GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE
    resource.write_bytes(resource.read_bytes().replace(b'"02"', b'"09"', 1))
    script = """
from broker_reports_gate1 import Gate5DeclarationProjectionRuntimeV1Factory
Gate5DeclarationProjectionRuntimeV1Factory.create()
"""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "gate5_declaration_projection_evidence_hash_mismatch" in completed.stderr


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


def _section2_projection_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_DECLARATION_PROJECTION_V1_REF_SCHEMA_VERSION,
        "projection_id": GATE5_DECLARATION_PROJECTION_SECTION2_ID,
        "projection_version": GATE5_DECLARATION_PROJECTION_SECTION2_VERSION,
    }


def _mutate_classification_mapping(spec: dict, evidence: dict) -> None:
    spec["mappings"][0]["transform"]["values"][
        "resident_securities_and_derivatives_non_iis"
    ] = "09"
    evidence["mapping_claims"][0]["transform"]["values"][
        "resident_securities_and_derivatives_non_iis"
    ] = "09"


def _resource_json(resource_name: str) -> dict:
    raw = resources.files("broker_reports_gate1").joinpath(resource_name).read_bytes()
    return json.loads(raw.decode("utf-8"))
