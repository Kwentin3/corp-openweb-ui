from __future__ import annotations

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
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    TypedFinancialInputDecision,
    UnclassifiedFinancialInputDecision,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_bundle import (  # noqa: E402
    Gate2FinancialEvidenceBundleFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_candidate_compiler import (  # noqa: E402,E501
    Gate2FinancialCandidateCompilerFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (  # noqa: E402,E501
    Gate2FinancialSemanticV6ChoiceContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_expansion import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    DECISION_EXPANSION_SCHEMA_VERSION,
    Gate2FinancialSemanticV6DecisionExpansionFactory,
    Gate2FinancialSemanticV6ExpansionError,
    validate_financial_semantic_v6_expanded_decision,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV6PacketFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"
EXPANSION_MODULE_PATH = (
    ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_expansion.py"
)
TYPED_OPTION_MODULE_PATH = (
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
    compilation = Gate2FinancialCandidateCompilerFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
    )
    packet = Gate2FinancialSemanticV6PacketFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )
    choice_contract = Gate2FinancialSemanticV6ChoiceContractFactory(
        registry=registry
    ).create(
        packet=packet,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )
    return (
        registry,
        scope,
        bundle,
        compilation,
        packet,
        choice_contract,
    )


def _expand(authorities, model_output):
    registry, scope, bundle, compilation, packet, contract = authorities
    return Gate2FinancialSemanticV6DecisionExpansionFactory(registry=registry).create(
        model_output=model_output,
        choice_contract=contract,
        packet=packet,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )


def test_typed_choice_expands_only_from_exact_option():
    authorities = _authorities()
    compilation = authorities[3]
    option = compilation.typed_options[0]
    expansion = _expand(
        authorities,
        {
            "disposition": "typed_input",
            "typed_option_id": option.typed_option_id,
        },
    )

    assert expansion.schema_version == DECISION_EXPANSION_SCHEMA_VERSION
    assert expansion.disposition == "typed_input"
    assert expansion.selected_typed_option_id == option.typed_option_id
    assert isinstance(
        expansion.validated_decision.decision,
        TypedFinancialInputDecision,
    )
    decision = expansion.validated_decision.decision
    assert decision.input_type_id == option.input_type_id
    assert [
        (item.role_id, item.source_value_ref) for item in decision.value_bindings
    ] == [(item.role_id, item.source_value_ref) for item in option.role_bindings]
    assert expansion.retained_source_value_refs == tuple(
        item.source_value_ref for item in option.role_bindings
    )
    assert expansion.post_response_repair_allowed is False
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not accept model-provided type IDs" in FORBIDDEN


@pytest.mark.parametrize(
    "case_id",
    [
        "syn_successor_signed_literal",
        "syn_successor_adjacent_equal",
    ],
)
def test_unclassified_choice_retains_every_bundle_value_exactly_once(
    case_id,
):
    authorities = _authorities(case_id)
    bundle = authorities[2]
    expansion = _expand(
        authorities,
        {
            "disposition": "unclassified_financial_input",
            "reason_code": "ambiguous_registry_type",
        },
    )

    assert expansion.disposition == ("unclassified_financial_input")
    assert expansion.selected_typed_option_id is None
    assert isinstance(
        expansion.validated_decision.decision,
        UnclassifiedFinancialInputDecision,
    )
    refs = tuple(
        item.source_value_ref
        for item in expansion.validated_decision.decision.value_bindings
    )
    assert refs == bundle.retention_set
    assert expansion.retained_source_value_refs == bundle.retention_set
    assert len(refs) == len(set(refs)) == len(bundle.source_values)


def test_unknown_or_tampered_option_fails_closed_without_repair():
    authorities = _authorities()
    for typed_option_id in (
        "financial-typed-option:unknown",
        authorities[3].typed_options[0].typed_option_id + "tampered",
    ):
        with pytest.raises(
            Gate2FinancialSemanticV6ExpansionError,
            match="financial_semantic_v6_expansion_option_unknown",
        ):
            _expand(
                authorities,
                {
                    "disposition": "typed_input",
                    "typed_option_id": typed_option_id,
                },
            )


@pytest.mark.parametrize(
    "model_output,error_code",
    [
        (
            {
                "disposition": "typed_input",
                "typed_option_id": "x",
                "reason_code": "ambiguous_registry_type",
            },
            "financial_semantic_v6_expansion_typed_shape_invalid",
        ),
        (
            {
                "disposition": "unclassified_financial_input",
                "reason_code": "free_form",
            },
            "financial_semantic_v6_expansion_reason_invalid",
        ),
        (
            {
                "disposition": "no_financial_input",
                "reason_code": "header_or_layout",
            },
            "financial_semantic_v6_expansion_disposition_invalid",
        ),
    ],
)
def test_nonminimal_and_technical_outputs_are_rejected(
    model_output,
    error_code,
):
    with pytest.raises(
        Gate2FinancialSemanticV6ExpansionError,
        match=error_code,
    ):
        _expand(_authorities(), model_output)


def test_duplicate_json_keys_are_rejected():
    option_id = _authorities()[3].typed_options[0].typed_option_id
    model_output = (
        '{"disposition":"typed_input",'
        '"disposition":"unclassified_financial_input",'
        f'"typed_option_id":"{option_id}"'
        "}"
    )

    with pytest.raises(
        Gate2FinancialSemanticV6ExpansionError,
        match="financial_semantic_v6_expansion_duplicate_key",
    ):
        _expand(_authorities(), model_output)


def test_expansion_is_deterministic_safe_and_tamper_evident():
    authorities = _authorities()
    model_output = {
        "disposition": "unclassified_financial_input",
        "reason_code": "no_registry_type",
    }
    first = _expand(authorities, model_output)
    second = _expand(
        authorities,
        json.dumps(model_output, sort_keys=True),
    )

    assert first == second
    safe = json.dumps(first.safe_summary(), sort_keys=True)
    assert all(ref not in safe for ref in first.retained_source_value_refs)
    assert first.safe_summary()["model_source_refs_total"] == 0
    assert first.safe_summary()["model_role_bindings_total"] == 0

    tampered = replace(first, integrity_hash="0" * 64)
    registry, scope, bundle, compilation, packet, contract = authorities
    with pytest.raises(
        Gate2FinancialSemanticV6ExpansionError,
        match="financial_semantic_v6_expansion_integrity_invalid",
    ):
        validate_financial_semantic_v6_expanded_decision(
            expansion=tampered,
            model_output=model_output,
            choice_contract=contract,
            packet=packet,
            evidence_bundle=bundle,
            source_package=scope.source_package,
            compilation=compilation,
            registry=registry,
        )


def test_typed_option_and_expansion_share_canonical_adapter_factory():
    typed_source = TYPED_OPTION_MODULE_PATH.read_text(encoding="utf-8")
    expansion_source = EXPANSION_MODULE_PATH.read_text(encoding="utf-8")

    factory_name = "Gate2FinancialSemanticV6CanonicalDecisionContractFactory"
    assert factory_name in typed_source
    assert factory_name in expansion_source
    assert "FinancialEvidenceValueCandidate" not in typed_source
    assert "typed_to_unclassified" not in expansion_source
    assert "except" in expansion_source
    assert "return _unclassified" not in expansion_source
