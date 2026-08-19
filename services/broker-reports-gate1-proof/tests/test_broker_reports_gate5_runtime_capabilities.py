from __future__ import annotations

import ast
import copy
import hashlib
import inspect
from importlib import resources
import json

import pytest

from broker_reports_gate1 import (
    GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE_SHA256,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE_SHA256,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE_SHA256,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE,
    GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE_SHA256,
    GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V2_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V3_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_REF_V2_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_REF_V3_SCHEMA_VERSION,
    Gate5DeclarationProjectionError,
    Gate5DeclarationProjectionRuntimeFactory,
    Gate5DeclarationProjectionRuntimeV1Factory,
    Gate5RuntimeCapabilityContractFactory,
    Gate5RuntimeCapabilityContractV1Factory,
    Gate5RuntimeCapabilityContractV2Factory,
    Gate5RuntimeCapabilityContractV3Factory,
    Gate5RuntimeCapabilityError,
    Gate5RuntimeCapabilityResolverFactory,
    Gate5RuntimeCapabilityResolverV1Factory,
    Gate5RuntimeCapabilityResolverV2Factory,
    Gate5RuntimeCapabilityResolverV3Factory,
    Gate5SingleInputHumanLoopRuntimeFactory,
    Gate5SupplementalFactDiscoveryRuntimeFactory,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
    Gate5TaxPeriodCategoryAggregationRuntime,
    Gate5TrustedMethodologyCalculationRuntimeFactory,
)
from broker_reports_gate1 import gate5_runtime_capabilities as capability_module
from broker_reports_gate1.gate5_runtime_capabilities import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)


EXPECTED_BINDINGS = {
    "resolve_required_values_v0": (
        "gate5.resolve_required_values.v0",
        Gate5SupplementalFactDiscoveryRuntimeFactory,
        ("check",),
    ),
    "obtain_one_missing_money_input_v0": (
        "gate5.obtain_one_missing_money_input.v0",
        Gate5SingleInputHumanLoopRuntimeFactory,
        ("ask", "submit"),
    ),
    "execute_published_calculation_behavior_v0": (
        "gate5.execute_published_calculation_behavior.v0",
        Gate5TrustedMethodologyCalculationRuntimeFactory,
        ("calculate",),
    ),
    "project_validated_declaration_fragment_v0": (
        "gate5.project_validated_declaration_fragment.v0",
        Gate5DeclarationProjectionRuntimeFactory,
        ("project",),
    ),
    "aggregate_complete_category_scope_v0": (
        "gate5.aggregate_complete_category_scope.v0",
        Gate5TaxPeriodCategoryAggregationRuntimeFactory,
        ("describe_scope", "run"),
    ),
}


def test_contract_is_hash_pinned_closed_and_conformant_with_real_owners() -> None:
    raw = (
        resources.files("broker_reports_gate1")
        .joinpath(GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE)
        .read_bytes()
    )
    assert hashlib.sha256(raw).hexdigest() == (
        GATE5_RUNTIME_CAPABILITY_CONTRACT_RESOURCE_SHA256
    )

    contract = Gate5RuntimeCapabilityContractFactory.create()
    snapshot = contract.snapshot()
    resolver = Gate5RuntimeCapabilityResolverFactory.create()

    assert len(snapshot["capabilities"]) == 5
    assert {item["capability_id"] for item in snapshot["capabilities"]} == set(
        EXPECTED_BINDINGS
    )
    for capability_id, (
        binding_id,
        factory_owner,
        operations,
    ) in EXPECTED_BINDINGS.items():
        resolved = resolver.resolve(_ref(capability_id))
        assert resolved.binding_id == binding_id
        assert resolved.factory_owner is factory_owner
        assert resolved.operations == operations


def test_model_projection_is_compact_and_hides_runtime_binding_details() -> None:
    contract = Gate5RuntimeCapabilityContractFactory.create()
    projection = contract.model_projection()
    payload = contract.model_projection_bytes()

    assert projection["schema_version"] == (
        GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_SCHEMA_VERSION
    )
    assert len(payload) == 6775
    assert len(payload) < 7_000
    assert all("conformance" not in item for item in projection["capabilities"])
    serialized = json.dumps(projection, ensure_ascii=False)
    for forbidden in (
        "binding_id",
        "owner_contract",
        "Gate5",
        "RuntimeFactory",
        ".py",
    ):
        assert forbidden not in serialized


def test_v2_corrects_only_aggregate_cardinality_and_v1_stays_exact() -> None:
    package = resources.files("broker_reports_gate1")
    v1_raw = package.joinpath(
        GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE
    ).read_bytes()
    v2_raw = package.joinpath(
        GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE
    ).read_bytes()
    assert hashlib.sha256(v1_raw).hexdigest() == (
        GATE5_RUNTIME_CAPABILITY_CONTRACT_V1_RESOURCE_SHA256
    )
    assert hashlib.sha256(v2_raw).hexdigest() == (
        GATE5_RUNTIME_CAPABILITY_CONTRACT_V2_RESOURCE_SHA256
    )

    v1 = Gate5RuntimeCapabilityContractV1Factory.create().snapshot()
    v2_contract = Gate5RuntimeCapabilityContractV2Factory.create()
    v2 = v2_contract.snapshot()
    v1_by_id = {item["capability_id"]: item for item in v1["capabilities"]}
    v2_by_id = {item["capability_id"]: item for item in v2["capabilities"]}

    assert (
        set(v2_by_id)
        == set(v1_by_id)
        == set(EXPECTED_BINDINGS) - {"execute_published_calculation_behavior_v0"}
        | {"execute_published_typed_behavior_v1"}
    )
    for capability_id in set(v1_by_id) - {"aggregate_complete_category_scope_v0"}:
        assert v2_by_id[capability_id] == v1_by_id[capability_id]

    v1_aggregate = copy.deepcopy(v1_by_id["aggregate_complete_category_scope_v0"])
    v2_aggregate = copy.deepcopy(v2_by_id["aggregate_complete_category_scope_v0"])
    assert "at_least_two_complete_operation_models" in v1_aggregate["preconditions"]
    assert "at_least_one_complete_operation_model" in v2_aggregate["preconditions"]
    assert "empty_operation_member_set" in v2_aggregate["failure_conditions"]
    assert "singleton" not in json.dumps(v2_aggregate, ensure_ascii=False).lower()

    v2_aggregate["meaning"] = v1_aggregate["meaning"]
    v2_aggregate["preconditions"] = v1_aggregate["preconditions"]
    v2_aggregate["failure_conditions"] = v1_aggregate["failure_conditions"]
    assert v2_aggregate == v1_aggregate
    assert v2_contract.model_projection()["schema_version"] == (
        GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V2_SCHEMA_VERSION
    )

    resolved = Gate5RuntimeCapabilityResolverV2Factory.create().resolve(
        {
            "schema_version": GATE5_RUNTIME_CAPABILITY_REF_V2_SCHEMA_VERSION,
            "capability_id": "aggregate_complete_category_scope_v0",
        }
    )
    assert resolved.factory_owner is Gate5TaxPeriodCategoryAggregationRuntimeFactory
    assert resolved.operations == ("describe_scope", "run")
    assert isinstance(
        resolved.create_runtime(), Gate5TaxPeriodCategoryAggregationRuntime
    )
    with pytest.raises(Gate5RuntimeCapabilityError) as caught:
        Gate5RuntimeCapabilityResolverV1Factory.create().resolve(
            {
                "schema_version": GATE5_RUNTIME_CAPABILITY_REF_V2_SCHEMA_VERSION,
                "capability_id": "aggregate_complete_category_scope_v0",
            }
        )
    assert caught.value.code == "gate5_runtime_capability_ref_invalid"
    assert GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION != (
        GATE5_RUNTIME_CAPABILITY_REF_V2_SCHEMA_VERSION
    )


def test_v3_replaces_only_project_member_and_keeps_five_capability_families() -> None:
    raw = (
        resources.files("broker_reports_gate1")
        .joinpath(GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE)
        .read_bytes()
    )
    assert hashlib.sha256(raw).hexdigest() == (
        GATE5_RUNTIME_CAPABILITY_CONTRACT_V3_RESOURCE_SHA256
    )
    v2 = Gate5RuntimeCapabilityContractV2Factory.create().snapshot()
    v3_contract = Gate5RuntimeCapabilityContractV3Factory.create()
    v3 = v3_contract.snapshot()
    v2_by_id = {item["capability_id"]: item for item in v2["capabilities"]}
    v3_by_id = {item["capability_id"]: item for item in v3["capabilities"]}

    unchanged = set(v2_by_id) - {"project_validated_declaration_fragment_v0"}
    assert len(v3_by_id) == len(v2_by_id) == 5
    assert set(v3_by_id) == unchanged | {
        "project_validated_declaration_fragment_v1"
    }
    assert all(v3_by_id[item] == v2_by_id[item] for item in unchanged)
    project = v3_by_id["project_validated_declaration_fragment_v1"]
    assert project["inputs"] == [
        {
            "name": "projection_ref",
            "contract": "broker_reports_gate5_declaration_projection_ref_v1",
            "required": True,
        },
        {
            "name": "declaration_semantics",
            "contract": "registered_projection_input",
            "required": True,
        },
    ]
    assert project["output"]["contract"] == (
        "broker_reports_gate5_declaration_projection_fragment_v1"
    )
    assert v3_contract.model_projection()["schema_version"] == (
        GATE5_RUNTIME_CAPABILITY_MODEL_PROJECTION_V3_SCHEMA_VERSION
    )

    resolved = Gate5RuntimeCapabilityResolverV3Factory.create().resolve(
        {
            "schema_version": GATE5_RUNTIME_CAPABILITY_REF_V3_SCHEMA_VERSION,
            "capability_id": "project_validated_declaration_fragment_v1",
        }
    )
    assert resolved.factory_owner is Gate5DeclarationProjectionRuntimeV1Factory
    assert resolved.operations == ("project",)
    assert resolved.create_runtime().__class__.__name__ == (
        "Gate5DeclarationProjectionRuntimeV1"
    )
    with pytest.raises(Gate5RuntimeCapabilityError) as stale:
        Gate5RuntimeCapabilityResolverV2Factory.create().resolve(
            {
                "schema_version": GATE5_RUNTIME_CAPABILITY_REF_V3_SCHEMA_VERSION,
                "capability_id": "project_validated_declaration_fragment_v1",
            }
        )
    assert stale.value.code == "gate5_runtime_capability_ref_invalid"


@pytest.mark.parametrize(
    "capability_ref",
    (
        {"schema_version": GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION},
        {
            "schema_version": GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION,
            "capability_id": "project_validated_declaration_fragment_v0",
            "function_name": "project",
        },
        {
            "schema_version": "unsupported",
            "capability_id": "project_validated_declaration_fragment_v0",
        },
    ),
)
def test_invalid_resolution_parameters_fail_before_binding(
    capability_ref: dict,
) -> None:
    resolver = Gate5RuntimeCapabilityResolverFactory.create()

    with pytest.raises(Gate5RuntimeCapabilityError) as caught:
        resolver.resolve(capability_ref)

    assert caught.value.code == "gate5_runtime_capability_ref_invalid"


def test_unknown_capability_fails_closed_without_guessing() -> None:
    resolver = Gate5RuntimeCapabilityResolverFactory.create()

    with pytest.raises(Gate5RuntimeCapabilityError) as caught:
        resolver.resolve(_ref("calculate_3ndfl_2025"))

    assert caught.value.code == "gate5_runtime_capability_unsupported"


def test_resolved_runtime_rejects_internal_dependency_parameters_before_owner() -> None:
    resolved = Gate5RuntimeCapabilityResolverFactory.create().resolve(
        _ref("project_validated_declaration_fragment_v0")
    )

    with pytest.raises(Gate5RuntimeCapabilityError) as caught:
        resolved.create_runtime(candidate_spec={})

    assert caught.value.code == "gate5_runtime_capability_dependencies_invalid"


def test_resolved_owner_executes_and_preserves_existing_missing_precondition_error() -> (
    None
):
    resolved = Gate5RuntimeCapabilityResolverFactory.create().resolve(
        _ref("project_validated_declaration_fragment_v0")
    )
    runtime = resolved.create_runtime()

    result = runtime.project(proof_input=_projection_input())
    assert result["status"] == "projected"
    assert result["validation"]["xsd_claim"] == (
        "structurally_consistent_not_full_xml_validated"
    )

    missing = _projection_input()
    missing.pop("allowable_expenses")
    with pytest.raises(Gate5DeclarationProjectionError) as caught:
        runtime.project(proof_input=missing)
    assert caught.value.code == "gate5_declaration_projection_input_invalid"


def test_resolver_has_antidrift_anchors_and_no_dynamic_loading() -> None:
    assert any("Factory.create" in item for item in FACTORY_REQUIRED)
    assert any("unknown capabilities" in item for item in FORBIDDEN)

    source = inspect.getsource(capability_module)
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "importlib" not in imports
    assert "importlib.util" not in imports
    assert "importlib.util" not in imported_from
    assert "importlib.machinery" not in imported_from
    assert "import_module(" not in source
    assert "__import__(" not in source


def _ref(capability_id: str) -> dict[str, str]:
    return {
        "schema_version": GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION,
        "capability_id": capability_id,
    }


def _projection_input() -> dict:
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
