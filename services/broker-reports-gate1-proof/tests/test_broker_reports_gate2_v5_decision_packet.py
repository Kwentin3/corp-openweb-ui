from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402,E501
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
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
from broker_reports_gate1.gate2_financial_semantic_v5_execution import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ExecutionContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_packet import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    V5_DECISION_PACKET_BLOCKS,
    V5_FORBIDDEN_PACKET_FIELDS,
    Gate2FinancialSemanticV5DecisionPacketFactory,
    render_financial_semantic_v5_packet_private,
    render_financial_semantic_v5_packet_safe,
    structural_binding_candidates_from_source_context,
)
from broker_reports_gate1.gate2_financial_semantic_v5_preclose import (  # noqa: E402,E501
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ProjectionFactory,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_successor_local_proof_v2 import (  # noqa: E402,E501
    _fixture_package,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)


def _cases():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in manifest["cases"]}


def _packet(case_id: str):
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = _fixture_package(copy.deepcopy(_cases()[case_id]))
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
    return packet, context, candidates, ambiguity


def _strict_response_format():
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "v5_packet_test",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["decision"],
                "properties": {"decision": {"type": "string"}},
            },
        },
    }


def test_v5_packet_has_exactly_four_model_visible_blocks():
    packet, _context, _candidates, _ambiguity = _packet(
        "syn_successor_v2_unique_cash"
    )

    assert tuple(packet.payload) == V5_DECISION_PACKET_BLOCKS
    assert len(packet.payload) == 4
    assert packet.payload["task"] == {
        "operation": "classify_financial_evidence",
        "decision_rule": "managed_prompt_only",
    }
    assert len(packet.payload["available_types"]) == 2
    assert len(packet.packet_hash) == 64
    assert len(packet.source_context_hash) == 64
    assert len(packet.semantic_projection_hash) == 64
    assert len(packet.ambiguity_policy_hash) == 64
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not expose administration" in FORBIDDEN


def test_v5_packet_preserves_exact_source_context_and_binding_coverage():
    packet, context, candidates, _ambiguity = _packet(
        "syn_successor_v2_unique_cash"
    )
    fragment = packet.payload["source_fragment"]
    context_values = [
        value
        for group in context.provider_groups()
        for value in group["values"]
    ]

    assert [item["source_value_ref"] for item in fragment["values"]] == [
        item["source_value_ref"] for item in context_values
    ]
    assert [item["literal_value"] for item in fragment["values"]] == [
        item["literal_value"] for item in context_values
    ]
    assert {
        ref
        for refs in packet.payload["binding_options"].values()
        for ref in refs
    } == {item.source_value_ref for item in candidates}
    assert fragment["row_role"] == "fact_candidate"
    assert fragment["section_role"] is None


def test_v5_packet_exposes_no_forbidden_fields_or_duplicate_meanings():
    packet, _context, _candidates, _ambiguity = _packet(
        "syn_successor_v2_unique_cash"
    )
    serialized = json.dumps(
        packet.payload,
        ensure_ascii=False,
        sort_keys=True,
    )
    assert all(
        f'"{field}"' not in serialized
        for field in V5_FORBIDDEN_PACKET_FIELDS
    )
    non_types = {
        key: value
        for key, value in packet.payload.items()
        if key != "available_types"
    }
    non_types_json = json.dumps(non_types, ensure_ascii=False)
    for semantic_field in (
        "short_meaning",
        "key_semantic_distinctions",
        "examples",
        "counterexamples",
        "ambiguity_rule",
    ):
        assert semantic_field not in non_types_json


def test_adjacent_equal_packet_has_unclassified_only_semantic_surface():
    packet, _context, _candidates, ambiguity = _packet(
        "syn_successor_v2_adjacent_equal"
    )

    assert ambiguity.available_type_cards == ()
    assert packet.payload["available_types"] == []
    assert len(packet.payload["binding_options"]["amount"]) == 2
    assert len(packet.payload["source_fragment"]["values"]) == 7


def test_v5_packet_builds_through_actual_three_component_request_route():
    packet, _context, _candidates, _ambiguity = _packet(
        "syn_successor_v2_unique_cash"
    )
    execution = (
        Gate2FinancialSemanticV5ExecutionContractFactory().create()
    )
    request = Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE
    ).build(
        prompt=execution.prompt,
        package=packet.payload,
        model_id="synthetic-v5",
        response_format=_strict_response_format(),
    )

    assert len(request["messages"]) == 1
    assert "tools" not in request
    system_content = request["messages"][0]["content"]
    assert execution.decision_packet_marker not in system_content
    assert json.dumps(
        packet.payload,
        ensure_ascii=False,
        sort_keys=True,
    ) in system_content


def test_private_and_repository_safe_debug_renderers_are_separated():
    packet, _context, candidates, _ambiguity = _packet(
        "syn_successor_v2_unique_cash"
    )
    branches = ("typed_input", "unclassified_financial_input")
    private = render_financial_semantic_v5_packet_private(
        packet=packet,
        available_response_branches=branches,
    )
    safe = render_financial_semantic_v5_packet_safe(
        packet=packet,
        available_response_branches=branches,
    )
    private_values = packet.payload["source_fragment"]["values"]
    private_literals = {
        str(item["literal_value"])
        for item in private_values
        if item["literal_value"] is not None
    }
    private_refs = {item.source_value_ref for item in candidates}

    assert all(title in private for title in (
        "TASK",
        "SOURCE FRAGMENT",
        "TYPE CARDS",
        "BINDING OPTIONS",
        "AVAILABLE RESPONSE BRANCHES",
    ))
    assert all(ref in private for ref in private_refs)
    assert all(literal in private for literal in private_literals)
    assert not any(ref in safe for ref in private_refs)
    assert not any(literal in safe for literal in private_literals)
    assert "values_total" in safe
    assert "value_type_counts" in safe
