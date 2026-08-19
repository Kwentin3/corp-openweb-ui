from __future__ import annotations

import copy
import hashlib
import inspect
import json

import pytest

from broker_reports_gate1 import gate5_full_target_xml_projection as projection_module
from broker_reports_gate1.gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputRuntime,
    Gate5DeclarationSemanticInputRuntimeFactory,
)
from broker_reports_gate1.gate5_full_target_xml_projection import (
    Gate5FullTargetXmlProjectionError,
    Gate5FullTargetXmlProjectionRuntimeFactory,
)
import test_broker_reports_gate5_end_to_end_full_target_xml as e2e_fixtures


_PROJECTION_INPUT_SCHEMA = (
    "broker_reports_gate5_released_declaration_projection_input_v0"
)
_TARGET_MECHANICS_SCHEMA = "broker_reports_gate5_ru_3ndfl_2025_target_mechanics_v0"


@pytest.fixture(scope="module")
def complete_package(tmp_path_factory: pytest.TempPathFactory) -> dict:
    packages: list[dict] = []
    original_compile = Gate5DeclarationSemanticInputRuntime.compile

    def capture_package(self, *, package: dict) -> dict:
        packages.append(copy.deepcopy(package))
        return original_compile(self, package=package)

    Gate5DeclarationSemanticInputRuntime.compile = capture_package
    try:
        result, _ = e2e_fixtures._run(
            tmp_path_factory.mktemp("g539ag-complete-package"),
            e2e_fixtures._proof_input(),
        )
    finally:
        Gate5DeclarationSemanticInputRuntime.compile = original_compile

    assert result["status"] == "END_TO_END_FULL_TARGET_XML_VALID"
    assert len(packages) == 1
    return packages[0]


def test_ag_released_values_only_match_legacy_mappings_xsd_and_xml(
    complete_package: dict,
) -> None:
    case = _released_case(complete_package)
    projector = Gate5FullTargetXmlProjectionRuntimeFactory.create()

    legacy = projector.project(semantic_input=case["semantic_input"])
    consumer = projector.project_released(
        released_values=case["projection_input"],
        target_mechanics=case["target_mechanics"],
    )

    assert consumer["receipt"]["status"] == "CONSUMER_FIRST_TARGET_XML_VALID"
    assert consumer["receipt"]["blockers"] == []
    assert consumer["receipt"]["conformance_proof"] == legacy["receipt"][
        "conformance_proof"
    ]
    assert consumer["receipt"]["semantic_mapping_proof"][
        "mapping_occurrences_total"
    ] == 49
    assert _mapping_equivalence(consumer) == _mapping_equivalence(legacy)
    assert consumer["xml_bytes"] == legacy["xml_bytes"]
    assert consumer["receipt"]["xml_binding"] == legacy["receipt"]["xml_binding"]


def test_ag_projection_input_is_audit_tax_and_completeness_free(
    complete_package: dict,
) -> None:
    case = _released_case(complete_package)
    projection_input = case["projection_input"]

    assert set(projection_input) == {
        "schema_version",
        "status",
        "value_contract",
        "declaration_values",
        "semantic_value_sha256",
        "release_receipt_sha256",
        "projection_input_sha256",
    }
    serialized = json.dumps(projection_input, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "package",
        "semantic_input_sha256",
        "component_snapshots",
        "source_binding",
        "methodology",
        "obligation",
        "completeness",
        "calculation_evidence",
    ):
        assert forbidden not in serialized

    runtime_source = inspect.getsource(
        projection_module.Gate5FullTargetXmlProjectionRuntime.project_released
    )
    for forbidden_runtime_read in (
        "package",
        "Gate4",
        "Sql",
        "ArtifactStore",
        "obligation",
        "completeness",
        "TaxModel",
    ):
        assert forbidden_runtime_read not in runtime_source


def test_ag_missing_released_value_fails_closed_without_fallback(
    complete_package: dict,
) -> None:
    case = _released_case(complete_package)
    changed = copy.deepcopy(case["projection_input"])
    del changed["declaration_values"]["financial_investment_results"][0][
        "allowable_expenses"
    ]

    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlProjectionRuntimeFactory.create().project_released(
            released_values=changed,
            target_mechanics=case["target_mechanics"],
        )
    assert exc_info.value.code == "gate5_consumer_first_released_values_invalid"
    assert exc_info.value.field == (
        "gate5_declaration_value_candidate_required_value_missing"
    )


def test_ag_target_instance_mechanics_change_only_file_identity(
    complete_package: dict,
) -> None:
    case = _released_case(complete_package)
    projector = Gate5FullTargetXmlProjectionRuntimeFactory.create()
    first = projector.project_released(
        released_values=case["projection_input"],
        target_mechanics=case["target_mechanics"],
    )
    second_mechanics = _target_mechanics("synthetic-declaration-2025-second-file")
    second = projector.project_released(
        released_values=case["projection_input"],
        target_mechanics=second_mechanics,
    )

    assert first["receipt"]["released_value_binding"]["semantic_value_sha256"] == (
        second["receipt"]["released_value_binding"]["semantic_value_sha256"]
    )
    first_mappings = first["receipt"]["semantic_mapping_proof"]["mappings"]
    second_mappings = second["receipt"]["semantic_mapping_proof"]["mappings"]
    changed = [
        left["mapping_id"]
        for left, right in zip(first_mappings, second_mappings, strict=True)
        if left["target_value_sha256"] != right["target_value_sha256"]
    ]
    assert changed == ["file-id"]
    assert first["xml_bytes"] != second["xml_bytes"]
    assert first["receipt"]["conformance_proof"]["xsd_valid"] is True
    assert second["receipt"]["conformance_proof"]["xsd_valid"] is True


@pytest.mark.parametrize("kind", ["refund_available", "balanced"])
def test_ag_unproven_budget_profiles_fail_closed(kind: str) -> None:
    values = {
        "budget_dispositions": [
            {
                "kind": kind,
                "kbk": "18210102010011000110",
                "oktmo": "45348000",
                "payable": _money("1.00"),
                "refundable": _money("0.00"),
            }
        ]
    }
    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        projection_module._consumer_source_root(
            declaration_values=values,
            target_mechanics=_target_mechanics("synthetic-file"),
        )
    assert exc_info.value.code == "gate5_consumer_first_projection_profile_unproven"
    assert exc_info.value.field == "budget_dispositions[0]"


def test_ag_unproven_multiple_allocations_fail_closed() -> None:
    row = {
        "kind": "additional_payment",
        "kbk": "18210102010011000110",
        "oktmo": "45348000",
        "payable": _money("1.00"),
        "refundable": _money("0.00"),
    }
    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        projection_module._consumer_source_root(
            declaration_values={"budget_dispositions": [row, copy.deepcopy(row)]},
            target_mechanics=_target_mechanics("synthetic-file"),
        )
    assert exc_info.value.code == "gate5_consumer_first_projection_profile_unproven"
    assert exc_info.value.field == "budget_dispositions"


def test_ag_consumer_definition_is_new_immutable_and_reuses_target_engine(
    complete_package: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _released_case(complete_package)
    legacy_definition = (
        projection_module.Gate5FullTargetXmlProjectionDefinitionAuthorityFactory
        .create()
        .resolve()
    )
    consumer_definition = (
        projection_module.Gate5ConsumerFirstXmlProjectionDefinitionAuthorityFactory
        .create()
        .resolve()
    )
    assert consumer_definition["projection_id"] == (
        "ru_3ndfl_2025_consumer_first_supplied_case"
    )
    assert consumer_definition["projection_version"] == (
        "2026-08-12.0-consumer-first-proof"
    )
    assert consumer_definition["input_contract"] == {
        "schema_version": _PROJECTION_INPUT_SCHEMA,
        "status": "DECLARATION_VALUES_RELEASED",
        "value_contract_id": "ru_3ndfl_2025_supplied_case_declaration_values",
        "value_contract_version": "2026-08-14.0-g545-bounded",
    }
    assert _tree_identity(consumer_definition["tree"]) == _tree_identity(
        legacy_definition["tree"]
    )
    assert consumer_definition["target"] == legacy_definition["target"]
    assert "required_domain_states" not in consumer_definition
    assert "semantic_coverage" not in consumer_definition

    original = projection_module._resource_bytes

    def changed_consumer_definition(name: str) -> bytes:
        value = original(name)
        if name == projection_module.GATE5_CONSUMER_FIRST_XML_PROJECTION_RESOURCE:
            return value + b" "
        return value

    monkeypatch.setattr(
        projection_module,
        "_resource_bytes",
        changed_consumer_definition,
    )
    legacy = Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
        semantic_input=case["semantic_input"]
    )
    assert legacy["receipt"]["status"] == "FULL_TARGET_XML_VALID"
    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlProjectionRuntimeFactory.create().project_released(
            released_values=case["projection_input"],
            target_mechanics=case["target_mechanics"],
        )
    assert exc_info.value.code == (
        "gate5_consumer_first_projection_definition_hash_mismatch"
    )


def _released_case(package: dict) -> dict:
    semantic_runtime = Gate5DeclarationSemanticInputRuntimeFactory.create()
    semantic_input = semantic_runtime.compile(package=package)
    candidate = semantic_runtime.compile_declaration_value_candidate(package=package)
    released = semantic_runtime.release_declaration_value_candidate(
        package=package,
        candidate=candidate,
    )
    projection_input = semantic_runtime.prepare_released_projection_input(
        package=package,
        released=released,
    )
    filing_domain = next(
        row
        for row in semantic_input["domains"]
        if row["domain_id"] == "filing_and_party_identity"
    )
    electronic_file_id = filing_domain["typed_components"][0]["semantic_payload"][
        "filing_instance"
    ]["declaration_instance_ref"]
    return {
        "semantic_input": semantic_input,
        "released": released,
        "projection_input": projection_input,
        "target_mechanics": _target_mechanics(electronic_file_id),
    }


def _target_mechanics(electronic_file_id: str) -> dict:
    base = {
        "schema_version": _TARGET_MECHANICS_SCHEMA,
        "status": "TARGET_MECHANICS_READY",
        "electronic_file_id": electronic_file_id,
    }
    return {**base, "target_mechanics_sha256": _sha256(base)}


def _mapping_equivalence(result: dict) -> list[dict]:
    return [
        {
            "mapping_id": item["mapping_id"],
            "target": item["target"],
            "target_value_sha256": item["target_value_sha256"],
        }
        for item in result["receipt"]["semantic_mapping_proof"]["mappings"]
    ]


def _tree_identity(node: dict) -> dict:
    return {
        "node_id": node["node_id"],
        "element": node["element"],
        "mapping_ids": [item["mapping_id"] for item in node["attributes"]]
        + (
            []
            if node.get("text_mapping") is None
            else [node["text_mapping"]["mapping_id"]]
        ),
        "children": [_tree_identity(child) for child in node["children"]],
    }


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


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
