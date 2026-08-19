from __future__ import annotations

import ast
import base64
import copy
import hashlib
import inspect
import json
from pathlib import Path

from lxml import etree
import pytest

from broker_reports_gate1 import gate5_full_target_xml_projection as module
from broker_reports_gate1.gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputRuntimeFactory,
)
from broker_reports_gate1.gate5_full_target_xml_projection import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_FULL_TARGET_XML_PROJECTION_RESOURCE,
    GATE5_FULL_TARGET_XML_PROJECTION_SHA256,
    GATE5_FULL_TARGET_XML_STATUS,
    GATE5_FULL_TARGET_XML_XSD_SHA256,
    Gate5FullTargetXmlConformanceValidator,
    Gate5FullTargetXmlProjectionDefinitionAuthorityFactory,
    Gate5FullTargetXmlProjectionError,
    Gate5FullTargetXmlProjectionRuntimeFactory,
)
import test_broker_reports_gate5_declaration_semantic_input as semantic_fixtures


def test_full_target_projection_is_complete_deterministic_and_officially_valid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantic_input = _semantic_input(tmp_path, monkeypatch)

    first = Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
        semantic_input=semantic_input
    )
    second = Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
        semantic_input=copy.deepcopy(semantic_input)
    )

    assert first["xml_bytes"] == second["xml_bytes"]
    assert first["receipt"] == second["receipt"]
    receipt = first["receipt"]
    assert receipt["status"] == GATE5_FULL_TARGET_XML_STATUS
    assert receipt["blockers"] == []
    assert receipt["projection_definition_binding"] == {
        "projection_id": "ru_3ndfl_2025_full_target_supplied_case",
        "projection_version": "2026-08-11.0-proof",
        "projection_definition_sha256": GATE5_FULL_TARGET_XML_PROJECTION_SHA256,
    }
    assert receipt["semantic_input_binding"] == {
        "semantic_input_sha256": semantic_input["semantic_input_sha256"],
        "definition_sha256": semantic_input["source_binding"]["definition_sha256"],
        "package_sha256": semantic_input["source_binding"]["package_sha256"],
    }
    assert receipt["xml_binding"]["xml_sha256"] == hashlib.sha256(
        first["xml_bytes"]
    ).hexdigest()
    assert receipt["xml_binding"]["xml_bytes"] == len(first["xml_bytes"])
    assert receipt["semantic_mapping_proof"]["status"] == "passed"
    assert receipt["semantic_mapping_proof"]["mapping_occurrences_total"] == 49
    assert receipt["semantic_mapping_proof"]["mapping_ids_total"] == 49
    assert receipt["semantic_mapping_proof"]["projected_obligations_total"] == 8
    assert (
        receipt["semantic_mapping_proof"][
            "non_projected_terminal_obligations_total"
        ]
        == 17
    )
    assert len(receipt["semantic_mapping_proof"]["coverage"]) == 25
    assert all(
        row["status"] == "passed"
        for row in receipt["semantic_mapping_proof"]["coverage"]
    )
    assert receipt["conformance_proof"] == {
        "status": "passed",
        "validator": "lxml.etree.XMLSchema",
        "xsd_name": "NO_NDFL3_1_033_00_05_20_01.xsd",
        "xsd_sha256": GATE5_FULL_TARGET_XML_XSD_SHA256,
        "schematron": None,
        "xml_well_formed": True,
        "xsd_valid": True,
    }
    assert receipt["receipt_sha256"] == _sha256(
        {key: item for key, item in receipt.items() if key != "receipt_sha256"}
    )

    tree = etree.fromstring(first["xml_bytes"])
    assert tree.tag == "Файл"
    assert len(tree.xpath("/Файл/Документ")) == 1
    assert len(tree.xpath("/Файл/Документ/СвНП/НПФЛ3/ФИОФЛ")) == 1
    assert len(tree.xpath("/Файл/Документ/СвНП/НПФЛ3/ИННФЛ")) == 1
    assert len(tree.xpath("/Файл/Документ/Подписант")) == 1
    assert len(tree.xpath("/Файл/Документ/НДФЛ3/СумНалПу/СумНалПуИскл227")) == 1
    assert len(tree.xpath("/Файл/Документ/НДФЛ3/НалБаза/РасчНалБаза")) == 1
    assert len(tree.xpath("/Файл/Документ/НДФЛ3/НалБаза/РасчНалПУ")) == 1
    assert len(tree.xpath("/Файл/Документ/НДФЛ3/ДоходИстРФ/ИстЮЛ")) == 1
    assert len(tree.xpath("/Файл/Документ/НДФЛ3/ДохОперЦБ")) == 1
    for not_activated in (
        "ЗаявРаспДС",
        "ДоходИстИно",
        "ДоходПредпр",
        "ПрофНалВыч",
        "ДоходОсвПрев",
        "ВычСтандСоц",
        "ИмущНалВычПр",
        "ИмущНалВычНов",
        "ДохПродОНИ",
        "ВычСоцИнв219",
    ):
        assert tree.xpath(f"/Файл/Документ/НДФЛ3/{not_activated}") == []


def test_mapping_and_xsd_conformance_proofs_are_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
        semantic_input=_semantic_input(tmp_path, monkeypatch)
    )
    definition = (
        Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create().resolve()
    )
    xsd_bytes = _official_xsd_bytes()
    invalid_xml = result["xml_bytes"].replace(
        b'VersForm="5.20"', b'VersForm="5.21"'
    )
    if invalid_xml == result["xml_bytes"]:
        invalid_xml = result["xml_bytes"].replace(
            "ВерсФорм=\"5.20\"".encode("windows-1251"),
            "ВерсФорм=\"5.21\"".encode("windows-1251"),
        )

    assert result["receipt"]["semantic_mapping_proof"]["status"] == "passed"
    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlConformanceValidator(xsd_bytes=xsd_bytes).validate(
            xml_bytes=invalid_xml,
            definition=definition,
        )
    assert exc_info.value.code == "gate5_full_target_xml_xsd_invalid"


def test_unmapped_changed_semantics_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = _semantic_input(tmp_path, monkeypatch)
    filing = _component(value, "filing_and_party_identity")
    filing["taxpayer"]["period_status"] = "unsupported_period_status"
    _rehash(value, "filing_and_party_identity")

    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
            semantic_input=value
        )
    assert exc_info.value.code == "gate5_full_target_projection_enum_unmapped"


def test_missing_semantic_value_fails_without_projector_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = _semantic_input(tmp_path, monkeypatch)
    del _component(value, "filing_and_party_identity")["taxpayer"]["inn"]
    _rehash(value, "filing_and_party_identity")

    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
            semantic_input=value
        )
    assert exc_info.value.code == "gate5_full_target_projection_source_value_missing"


def test_non_integral_target_tax_amount_fails_without_rounding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = _semantic_input(tmp_path, monkeypatch)
    budget = _component(value, "declaration_budget_disposition")
    budget["budget_allocations"][0]["amount"]["amount"] = "4.50"
    _rehash(value, "declaration_budget_disposition")

    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
            semantic_input=value
        )
    assert exc_info.value.code == "gate5_full_target_projection_money_not_integral"


def test_changed_domain_profile_cannot_silently_omit_an_activated_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = _semantic_input(tmp_path, monkeypatch)
    domain = _domain(value, "financial_investment_results")
    domain["state"] = "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
    domain["typed_components"] = []
    value["semantic_input_sha256"] = _sha256(
        {key: item for key, item in value.items() if key != "semantic_input_sha256"}
    )

    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
            semantic_input=value
        )
    assert exc_info.value.code == "gate5_full_target_projection_domain_profile_mismatch"


def test_definition_and_xsd_resources_are_exact_hash_pins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition_bytes = module._resource_bytes(
        GATE5_FULL_TARGET_XML_PROJECTION_RESOURCE
    )
    assert hashlib.sha256(definition_bytes).hexdigest() == (
        GATE5_FULL_TARGET_XML_PROJECTION_SHA256
    )
    assert hashlib.sha256(_official_xsd_bytes()).hexdigest() == (
        GATE5_FULL_TARGET_XML_XSD_SHA256
    )

    original = module._resource_bytes

    def changed_definition(name: str) -> bytes:
        value = original(name)
        return value + b" " if name == GATE5_FULL_TARGET_XML_PROJECTION_RESOURCE else value

    monkeypatch.setattr(module, "_resource_bytes", changed_definition)
    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create().resolve()
    assert exc_info.value.code == (
        "gate5_full_target_projection_definition_hash_mismatch"
    )


def test_xsd_resource_tamper_fails_before_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = module._resource_bytes
    definition = (
        Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create().resolve()
    )
    xsd_resource = definition["target"]["xsd_resource"]

    def changed_xsd(name: str) -> bytes:
        value = original(name)
        if name != xsd_resource:
            return value
        return base64.b64encode(base64.b64decode(b"".join(value.split())) + b"x")

    monkeypatch.setattr(module, "_resource_bytes", changed_xsd)
    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlProjectionRuntimeFactory.create()
    assert exc_info.value.code == "gate5_full_target_xsd_hash_mismatch"


def test_factory_closed_world_and_target_rules_live_only_in_definition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantic_input = _semantic_input(tmp_path, monkeypatch)
    outside = tmp_path / "outside-repository-cwd"
    outside.mkdir()
    monkeypatch.chdir(outside)

    result = Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
        semantic_input=semantic_input
    )
    assert result["receipt"]["status"] == GATE5_FULL_TARGET_XML_STATUS

    source = inspect.getsource(module)
    factory_source = inspect.getsource(
        module.Gate5FullTargetXmlProjectionRuntimeFactory
    )
    runtime_source = inspect.getsource(module.Gate5FullTargetXmlProjectionRuntime)
    imports = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert len(FACTORY_REQUIRED) == 3
    assert FORBIDDEN
    assert "Gate5DeclarationSemanticInputRuntimeFactory.create()" in factory_source
    assert "Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create()" in (
        factory_source
    )
    assert "projector.project" in runtime_source
    assert runtime_source.index("projector.project") < runtime_source.index(
        "serializer.serialize"
    ) < runtime_source.index("validator.validate")
    assert imports == {
        "__future__",
        "datetime",
        "decimal",
        "importlib",
        "lxml",
        "typing",
        "gate5_declaration_semantic_input",
    }
    for target_rule in (
        "1151020",
        "5.20",
        "organized_market_securities_outside_iis",
        "securities_disposal",
        "resident_individual",
        "windows-1251",
        "Gate5DeclarationProjectionRuntimeFactory",
    ):
        assert target_rule not in source
    for forbidden_runtime_dependency in (
        "Gate4FinancialCaseRuntimeFactory",
        "SqliteArtifactStoreAdapter",
        "ArtifactStore",
        "requests",
        "openai",
        "SELECT ",
    ):
        assert forbidden_runtime_dependency not in runtime_source


def _semantic_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    package = semantic_fixtures._complete_package(tmp_path, monkeypatch)
    return Gate5DeclarationSemanticInputRuntimeFactory.create().compile(
        package=package
    )


def _domain(value: dict, domain_id: str) -> dict:
    return next(row for row in value["domains"] if row["domain_id"] == domain_id)


def _component(value: dict, domain_id: str) -> dict:
    return _domain(value, domain_id)["typed_components"][0]["semantic_payload"]


def _rehash(value: dict, domain_id: str) -> None:
    component = _domain(value, domain_id)["typed_components"][0]
    component["semantic_payload_sha256"] = _sha256(component["semantic_payload"])
    value["semantic_input_sha256"] = _sha256(
        {key: item for key, item in value.items() if key != "semantic_input_sha256"}
    )


def _official_xsd_bytes() -> bytes:
    definition = (
        Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create().resolve()
    )
    return base64.b64decode(
        b"".join(module._resource_bytes(definition["target"]["xsd_resource"]).split())
    )


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
