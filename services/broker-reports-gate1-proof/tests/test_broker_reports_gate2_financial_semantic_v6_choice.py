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
    DISPOSITIONS,
    UNCLASSIFIED_REASON_CODES,
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
    FACTORY_REQUIRED,
    FORBIDDEN,
    SEMANTIC_CHOICE_OUTPUT_FIELDS,
    SEMANTIC_CHOICE_PROVIDER_DISPOSITIONS,
    SEMANTIC_CHOICE_SCHEMA_VERSION,
    Gate2FinancialSemanticV6ChoiceContractFactory,
    Gate2FinancialSemanticV6ChoiceError,
    validate_financial_semantic_v6_choice_contract,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV6PacketFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"
MODULE_PATH = ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_choice.py"


def _cases() -> dict[str, dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in payload["cases"]}


def _contract(
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
    contract = Gate2FinancialSemanticV6ChoiceContractFactory(registry=registry).create(
        packet=packet,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )
    return contract, packet, registry, scope, bundle, compilation


def _variants(contract):
    return contract.choice_schema["anyOf"]


def _disposition(variant):
    return variant["properties"]["disposition"]["enum"][0]


def test_choice_contract_has_only_two_minimal_provider_dispositions():
    contract, packet, registry, scope, bundle, compilation = _contract()
    variants = _variants(contract)

    assert contract.schema_version == SEMANTIC_CHOICE_SCHEMA_VERSION
    assert contract.provider_dispositions == (SEMANTIC_CHOICE_PROVIDER_DISPOSITIONS)
    assert contract.available_provider_dispositions == (
        SEMANTIC_CHOICE_PROVIDER_DISPOSITIONS
    )
    assert {_disposition(item) for item in variants} == set(
        SEMANTIC_CHOICE_PROVIDER_DISPOSITIONS
    )
    assert set(variants[0]["properties"]) == {
        "disposition",
        "typed_option_id",
    }
    assert set(variants[1]["properties"]) == {
        "disposition",
        "reason_code",
    }
    assert all(item["additionalProperties"] is False for item in variants)
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not return a type ID" in FORBIDDEN
    validate_financial_semantic_v6_choice_contract(
        contract=contract,
        packet=packet,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
        registry=registry,
    )


def test_typed_variant_exposes_only_opaque_packet_option_ids():
    contract, packet, _, _, _, _ = _contract()
    typed = next(
        item for item in _variants(contract) if _disposition(item) == "typed_input"
    )
    option_ids = tuple(typed["properties"]["typed_option_id"]["enum"])

    assert option_ids == tuple(
        item["option_id"] for item in packet.payload["typed_options"]
    )
    assert option_ids == contract.typed_option_ids
    assert all(item.startswith("financial-typed-option:") for item in option_ids)
    serialized = json.dumps(typed, sort_keys=True)
    assert "input_type_id" not in serialized
    assert "source_value_ref" not in serialized
    assert "role_bindings" not in serialized
    assert "literal_value" not in serialized
    assert "provenance" not in serialized
    assert "dimension" not in serialized


def test_unclassified_variant_uses_exact_bounded_canonical_reasons():
    contract, _, _, _, _, _ = _contract()
    unclassified = next(
        item
        for item in _variants(contract)
        if _disposition(item) == "unclassified_financial_input"
    )

    assert (
        tuple(unclassified["properties"]["reason_code"]["enum"])
        == UNCLASSIFIED_REASON_CODES
    )
    assert contract.unclassified_reason_codes == (UNCLASSIFIED_REASON_CODES)
    assert unclassified["required"] == [
        "disposition",
        "reason_code",
    ]


def test_adjacent_equal_has_unclassified_only_available_variant():
    contract, packet, _, _, _, compilation = _contract("syn_successor_adjacent_equal")

    assert compilation.typed_options == ()
    assert packet.payload["typed_options"] == []
    assert contract.provider_dispositions == (SEMANTIC_CHOICE_PROVIDER_DISPOSITIONS)
    assert contract.available_provider_dispositions == ("unclassified_financial_input",)
    assert [_disposition(item) for item in _variants(contract)] == [
        "unclassified_financial_input"
    ]
    assert contract.typed_option_ids == ()


def test_canonical_four_dispositions_remain_unchanged_and_technical_are_hidden():
    contract, _, _, _, _, _ = _contract()
    serialized = json.dumps(contract.choice_schema, sort_keys=True)

    assert DISPOSITIONS == (
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    )
    assert contract.canonical_gate2_dispositions == DISPOSITIONS
    assert "no_financial_input" not in serialized
    assert "unsupported" not in serialized
    summary = contract.safe_summary()
    assert summary["canonical_gate2_dispositions_total"] == 4
    assert summary["technical_preclose_model_dispositions_total"] == 0
    assert summary["model_source_refs_total"] == 0
    assert summary["model_role_bindings_total"] == 0
    assert set(summary["model_output_fields"]) == (SEMANTIC_CHOICE_OUTPUT_FIELDS)


def test_contract_is_deterministic_safe_and_rejects_tampering():
    contract, packet, registry, scope, bundle, compilation = _contract()
    second = Gate2FinancialSemanticV6ChoiceContractFactory(registry=registry).create(
        packet=packet,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )

    assert contract == second
    assert contract.choice_schema_hash == second.choice_schema_hash
    safe = json.dumps(contract.safe_summary(), sort_keys=True)
    assert all(option_id not in safe for option_id in contract.typed_option_ids)

    tampered = replace(contract, choice_schema_hash="0" * 64)
    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_choice_contract_integrity_invalid",
    ):
        validate_financial_semantic_v6_choice_contract(
            contract=tampered,
            packet=packet,
            evidence_bundle=bundle,
            source_package=scope.source_package,
            compilation=compilation,
            registry=registry,
        )


def test_choice_module_contains_no_type_specific_or_record_schema():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "cash_balance_snapshot_v1" not in source
    assert "printed_financial_metric_v1" not in source
    assert "value_bindings" not in source
    assert "source_value_ref" not in source
    assert "input_type_id" not in source
    assert "record_fields" not in source
