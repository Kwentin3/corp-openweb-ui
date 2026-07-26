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
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402,E501
    DISPOSITIONS,
    TypedFinancialInputDecision,
    UnclassifiedFinancialInputDecision,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402,E501
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_source_context import (  # noqa: E402,E501
    Gate2FinancialEvidenceSourceContextFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_ambiguity import (  # noqa: E402,E501
    Gate2FinancialSemanticV5AmbiguityGuardFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_contract import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    V5_PROVIDER_DISPOSITIONS,
    Gate2FinancialSemanticV5ModelContractError,
    Gate2FinancialSemanticV5ModelContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_execution import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ExecutionContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV5DecisionPacketFactory,
    structural_binding_candidates_from_source_context,
)
from broker_reports_gate1.gate2_financial_semantic_v5_preclose import (  # noqa: E402,E501
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ProjectionFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402,E501
    _fixture_package,
    _model_output,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_contract.py"
)


def _cases():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in manifest["cases"]}


def _contract_bundle(case_id: str):
    case = copy.deepcopy(_cases()[case_id])
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = _fixture_package(case)
    scope = Gate2DeterministicFinancialScopeFromGate1V2Factory(
        registry=registry
    ).create(gate1_packages=(fixture.payload,)).scopes[0]
    context = Gate2FinancialEvidenceSourceContextFactory().create(
        source_scope_ref=scope.source_package.source_scope_ref,
        source_values=scope.source_package.source_values,
        candidates=scope.decision_contract.package.candidates,
        gate1_packages=(fixture.payload,),
    )
    candidates = structural_binding_candidates_from_source_context(
        source_context=context
    )
    projection = Gate2FinancialSemanticV5ProjectionFactory().create()
    ambiguity = Gate2FinancialSemanticV5AmbiguityGuardFactory().create(
        projection=projection,
        candidates=candidates,
    )
    preclose = Gate2FinancialSemanticV5PrecloseFactory().create(
        evidence=Gate2TechnicalPrecloseEvidence(
            source_support="supported",
            authoritative_layout_only=False,
            source_value_candidates_total=len(candidates),
            scope_valid=True,
        )
    )
    packet = Gate2FinancialSemanticV5DecisionPacketFactory().create(
        source_context=context,
        projection=projection,
        ambiguity=ambiguity,
        candidates=candidates,
        preclose=preclose,
    )
    execution = (
        Gate2FinancialSemanticV5ExecutionContractFactory().create()
    )
    model_contract = (
        Gate2FinancialSemanticV5ModelContractFactory().create(
            execution=execution,
            projection=projection,
            ambiguity=ambiguity,
            packet=packet,
            canonical_contract=scope.decision_contract,
        )
    )
    model_output = _model_output(
        case=case,
        scope=scope,
        selected_value_refs=fixture.selected_value_refs,
    )
    return (
        model_contract,
        execution,
        projection,
        ambiguity,
        packet,
        scope.decision_contract,
        model_output,
    )


def _schema_variants(model_contract):
    return model_contract.response_format["json_schema"]["schema"][
        "properties"
    ]["decision"]["anyOf"]


def _disposition(variant):
    return variant["properties"]["disposition"]["enum"][0]


def _validate(bundle, model_output):
    (
        model_contract,
        execution,
        projection,
        ambiguity,
        packet,
        canonical_contract,
        _expected_output,
    ) = bundle
    return model_contract.validate_and_adapt(
        model_output=model_output,
        execution=execution,
        projection=projection,
        ambiguity=ambiguity,
        packet=packet,
        canonical_contract=canonical_contract,
    )


def test_provider_contract_is_two_disposition_projection_of_canonical():
    bundle = _contract_bundle("syn_successor_v2_unique_cash")
    model_contract = bundle[0]
    variants = _schema_variants(model_contract)
    dispositions = {_disposition(item) for item in variants}
    canonical_variants = bundle[5].openai_response_format()[
        "json_schema"
    ]["schema"]["properties"]["decision"]["anyOf"]

    assert model_contract.provider_dispositions == (
        V5_PROVIDER_DISPOSITIONS
    )
    assert dispositions == set(V5_PROVIDER_DISPOSITIONS)
    assert all(item in canonical_variants for item in variants)
    assert model_contract.response_format["json_schema"]["strict"] is True
    assert DISPOSITIONS == (
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    )
    assert "no_financial_input" not in json.dumps(variants)
    assert "unsupported" not in json.dumps(variants)
    assert model_contract.safe_summary()[
        "canonical_gate2_dispositions_total"
    ] == 4
    assert model_contract.safe_summary()[
        "duplicate_decision_authorities_total"
    ] == 0
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not expose technical terminal branches" in FORBIDDEN


def test_module_projects_and_reuses_authority_without_financial_rules():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "Gate2FinancialEvidenceValidatedDecisionFactory" in source
    assert "canonical_contract.openai_response_format()" in source
    assert "_typed_variant_schema" not in source
    assert "cash_balance_snapshot_v1" not in source
    assert "printed_financial_metric_v1" not in source
    assert "role_id ==" not in source


def test_typed_and_unclassified_use_existing_canonical_validator():
    typed_bundle = _contract_bundle(
        "syn_successor_v2_unique_cash"
    )
    typed = _validate(typed_bundle, typed_bundle[-1])
    assert isinstance(typed.decision, TypedFinancialInputDecision)
    assert typed.decision_schema_hash == (
        typed_bundle[5].canonical_schema_hash()
    )

    unclassified_bundle = _contract_bundle(
        "syn_successor_v2_multiple_compatible"
    )
    unclassified = _validate(
        unclassified_bundle,
        unclassified_bundle[-1],
    )
    assert isinstance(
        unclassified.decision,
        UnclassifiedFinancialInputDecision,
    )
    assert unclassified.decision_schema_hash == (
        unclassified_bundle[5].canonical_schema_hash()
    )


def test_ambiguity_block_removes_typed_schema_and_rejects_typed_output():
    bundle = _contract_bundle("syn_successor_v2_adjacent_equal")
    model_contract = bundle[0]
    variants = _schema_variants(model_contract)
    canonical_typed = next(
        item
        for item in bundle[5].openai_response_format()["json_schema"][
            "schema"
        ]["properties"]["decision"]["anyOf"]
        if _disposition(item) == "typed_input"
    )
    typed_output = {
        "decision": {
            key: (
                value["enum"][0]
                if isinstance(value, dict)
                and isinstance(value.get("enum"), list)
                and len(value["enum"]) == 1
                else None
            )
            for key, value in canonical_typed["properties"].items()
        }
    }
    typed_output["decision"]["value_bindings"] = {}
    for role_id, property_schema in canonical_typed["properties"][
        "value_bindings"
    ]["properties"].items():
        values = property_schema.get("enum")
        typed_output["decision"]["value_bindings"][role_id] = (
            values[0] if values else None
        )

    assert model_contract.typed_type_ids == ()
    assert {_disposition(item) for item in variants} == {
        "unclassified_financial_input"
    }
    with pytest.raises(
        Gate2FinancialSemanticV5ModelContractError
    ) as exc:
        _validate(bundle, typed_output)
    assert exc.value.code == (
        "financial_semantic_v5_typed_branch_prohibited"
    )


def test_technical_terminal_model_outputs_are_rejected():
    bundle = _contract_bundle("syn_successor_v2_unique_cash")
    for model_output in (
        {
            "decision": {
                "disposition": "no_financial_input",
                "reason_code": "header_or_layout",
            }
        },
        {
            "decision": {
                "disposition": "unsupported",
                "reason_code": "source_shape_unsupported",
            }
        },
    ):
        with pytest.raises(
            Gate2FinancialSemanticV5ModelContractError
        ) as exc:
            _validate(bundle, model_output)
        assert exc.value.code == (
            "financial_semantic_v5_technical_branch_prohibited"
        )


@pytest.mark.parametrize(
    "tamper",
    (
        "prompt",
        "projection",
        "packet",
        "ambiguity_policy",
        "ambiguity_input",
        "response_schema",
    ),
)
def test_validator_rejects_every_exact_identity_mismatch(tamper):
    bundle = list(
        _contract_bundle("syn_successor_v2_unique_cash")
    )
    if tamper == "prompt":
        bundle[1] = replace(
            bundle[1],
            prompt=replace(bundle[1].prompt, hash="0" * 64),
        )
    elif tamper == "projection":
        bundle[2] = replace(bundle[2], projection_hash="0" * 64)
    elif tamper == "packet":
        bundle[4] = replace(bundle[4], packet_hash="0" * 64)
    elif tamper == "ambiguity_policy":
        bundle[3] = replace(bundle[3], policy_hash="0" * 64)
    elif tamper == "ambiguity_input":
        bundle[3] = replace(bundle[3], guard_input_hash="0" * 64)
    else:
        response_format = copy.deepcopy(bundle[0].response_format)
        response_format["json_schema"]["name"] = "tampered"
        bundle[0] = replace(
            bundle[0],
            response_format=response_format,
        )

    with pytest.raises(
        Gate2FinancialSemanticV5ModelContractError
    ):
        _validate(tuple(bundle), bundle[-1])


def test_safe_summary_contains_no_source_refs_or_literals():
    bundle = _contract_bundle("syn_successor_v2_unique_cash")
    model_contract = bundle[0]
    summary = model_contract.safe_summary()
    serialized = json.dumps(summary, sort_keys=True)

    assert model_contract.prompt_ref not in serialized
    assert "source_value_ref" not in serialized
    assert "literal_value" not in serialized
    assert summary["technical_terminal_model_branches_total"] == 0
    assert summary["provider_calls_total"] == 0
