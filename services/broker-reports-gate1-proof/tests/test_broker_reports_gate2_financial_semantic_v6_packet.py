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
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_bundle import (  # noqa: E402
    Gate2FinancialEvidenceBundleFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_candidate_compiler import (  # noqa: E402,E501
    Gate2FinancialCandidateCompilerFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    SEMANTIC_PACKET_AMBIGUITY_RULE,
    SEMANTIC_PACKET_BLOCKS,
    SEMANTIC_PACKET_FORBIDDEN_FIELDS,
    SEMANTIC_PACKET_SCHEMA_VERSION,
    Gate2FinancialSemanticV6PacketError,
    Gate2FinancialSemanticV6PacketFactory,
    render_financial_semantic_v6_packet_private_exact,
    render_financial_semantic_v6_packet_repository_safe,
    validate_financial_semantic_v6_packet,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"


def _cases() -> dict[str, dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in payload["cases"]}


def _packet(
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
    return packet, registry, scope, bundle, compilation


def test_packet_has_exactly_four_model_visible_blocks():
    packet, registry, scope, bundle, compilation = _packet()

    assert packet.schema_version == SEMANTIC_PACKET_SCHEMA_VERSION
    assert tuple(packet.payload) == SEMANTIC_PACKET_BLOCKS
    assert len(packet.payload) == 4
    assert packet.payload["task"] == {
        "semantic_operation": ("select_prebound_typed_option_or_unclassified"),
        "ambiguity_rule": SEMANTIC_PACKET_AMBIGUITY_RULE,
    }
    assert len(packet.payload["available_type_cards"]) == 2
    assert len(packet.payload["typed_options"]) == 2
    assert len(packet.packet_hash) == 64
    assert "Factory.create" in FACTORY_REQUIRED
    assert "exactly four model-visible blocks" in FORBIDDEN
    validate_financial_semantic_v6_packet(
        packet=packet,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
        registry=registry,
    )


def test_packet_preserves_exact_visible_source_context_and_associations():
    packet, _, _, bundle, _ = _packet("syn_successor_currency_date")
    source_context = packet.payload["source_context"]

    assert [item["source_value_ref"] for item in source_context["source_values"]] == [
        item.source_value_ref for item in bundle.source_values
    ]
    assert [item["source_value"] for item in source_context["source_values"]] == [
        item.literal_value for item in bundle.source_values
    ]
    assert all(
        set(item["visible_context"])
        == {
            "section_role",
            "row_role",
            "column_meaning",
            "visible_label",
        }
        for item in source_context["source_values"]
    )
    assert [item["source_value_refs"] for item in source_context["associations"]] == [
        list(item.source_value_refs) for item in bundle.source_associations
    ]
    assert all(
        "association linking" in item["human_summary"]
        for item in source_context["associations"]
    )


def test_typed_options_are_human_readable_prebound_records():
    packet, _, _, bundle, compilation = _packet()
    values_by_ref = {item.source_value_ref: item for item in bundle.source_values}

    assert {item["option_id"] for item in packet.payload["typed_options"]} == {
        item.typed_option_id for item in compilation.typed_options
    }
    for rendered, option in zip(
        packet.payload["typed_options"],
        compilation.typed_options,
        strict=True,
    ):
        assert rendered["option_id"] == option.typed_option_id
        assert rendered["input_type_id"] == option.input_type_id
        assert [item["role_id"] for item in rendered["prebound_role_values"]] == [
            item.role_id for item in option.role_bindings
        ]
        for item in rendered["prebound_role_values"]:
            source = values_by_ref[item["source_value_ref"]]
            assert item["source_value"] == source.literal_value
            assert item["value_type"] == source.value_type
            assert item["role_id"] in item["human_summary"]


def test_adjacent_equal_keeps_context_and_has_no_typed_surface():
    packet, _, _, bundle, compilation = _packet("syn_successor_adjacent_equal")

    assert bundle.source_values
    assert compilation.typed_options == ()
    assert packet.payload["source_context"]["source_values"]
    assert packet.payload["available_type_cards"] == []
    assert packet.payload["typed_options"] == []


def test_packet_excludes_administration_and_duplicate_guidance():
    packet, _, _, _, _ = _packet()
    serialized = json.dumps(
        packet.payload,
        ensure_ascii=False,
        sort_keys=True,
    )

    assert all(
        f'"{field}"' not in serialized for field in SEMANTIC_PACKET_FORBIDDEN_FIELDS
    )
    assert serialized.count(SEMANTIC_PACKET_AMBIGUITY_RULE) == 1
    non_cards = {
        "source_context": packet.payload["source_context"],
        "typed_options": packet.payload["typed_options"],
    }
    non_cards_json = json.dumps(non_cards, ensure_ascii=False)
    for field in (
        "short_meaning",
        "key_semantic_distinctions",
        "examples",
        "counterexamples",
    ):
        assert field not in non_cards_json


def test_private_exact_and_repository_safe_renderers_are_separated():
    packet, _, _, bundle, _ = _packet()

    private = render_financial_semantic_v6_packet_private_exact(packet=packet)
    safe = render_financial_semantic_v6_packet_repository_safe(packet=packet)
    safe_payload = json.loads(safe)

    assert json.loads(private) == packet.payload
    assert tuple(safe_payload["model_visible_blocks"]) == (SEMANTIC_PACKET_BLOCKS)
    assert all(
        item.source_value_ref in private and item.source_value_ref not in safe
        for item in bundle.source_values
    )
    assert all(
        item.literal_value in private and item.literal_value not in safe
        for item in bundle.source_values
    )
    assert "value_type_counts" in safe
    assert "source_values_total" in safe


def test_packet_validator_and_renderers_reject_tampering():
    packet, registry, scope, bundle, compilation = _packet()
    tampered = replace(packet, packet_hash="0" * 64)

    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_integrity_invalid",
    ):
        validate_financial_semantic_v6_packet(
            packet=tampered,
            evidence_bundle=bundle,
            source_package=scope.source_package,
            compilation=compilation,
            registry=registry,
        )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_render_input_invalid",
    ):
        render_financial_semantic_v6_packet_private_exact(packet=tampered)
