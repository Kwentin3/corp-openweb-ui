from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ProjectionFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    CONTEXT_V2_1_AGGREGATE_TARGET_BYTES,
    CONTEXT_V2_1_BLOCKS,
    CONTEXT_V2_1_FORBIDDEN_FIELDS,
    CONTEXT_V2_1_TASK,
    Gate2FinancialSemanticV6PacketError,
    Gate2FinancialSemanticV6PacketFactory,
    _ReadableCollisionGuard,
    _context_v2_1_differentiator_occurrences,
    _context_v2_1_mapping_receipt_payload_without_integrity,
    _context_v2_1_type_projection,
    _context_v2_candidate_and_receipt,
    _source_graph,
    validate_financial_semantic_v6_packet,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)


V6_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
)
V6_BASE_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
SNAPSHOT_KEY = b"v6-slim-view-test-snapshot-key-32"
CONTINUATION_KEY = b"v6-slim-view-test-continuation-key"
EXPECTED_CASE_BYTES = {
    "syn_successor_v2_unique_cash": 2645,
    "syn_successor_v2_unique_printed_total": 2643,
    "syn_successor_v2_multiple_compatible": 2624,
    "syn_successor_v2_no_registry_type": 2640,
    "syn_successor_v2_missing_discriminator": 2584,
    "syn_successor_v2_detail_vs_subtotal": 2584,
    "syn_successor_v2_adjacent_equal": 2580,
    "syn_successor_v2_adjacent_fx": 2624,
    "syn_successor_v2_optional_missing": 2643,
    "syn_successor_v2_forbidden_neighbour": 2644,
}
HISTORICAL_CONTEXT_V2_TOTAL_BYTES = 78_621
CURRENT_CASE_ACCEPTANCE_TARGET_BYTES = 4_500


@pytest.fixture(scope="module")
def v6_fixture():
    return Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=json.loads(V6_MANIFEST_PATH.read_text(encoding="utf-8")),
        base_manifest=json.loads(
            V6_BASE_MANIFEST_PATH.read_text(encoding="utf-8")
        ),
    )


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _json_bytes(value, *, sort_keys: bool = False) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=sort_keys,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value, *, sort_keys: bool = False) -> str:
    return hashlib.sha256(
        _json_bytes(value, sort_keys=sort_keys)
    ).hexdigest()


def _case(v6_fixture, case_id: str):
    return next(
        item
        for item in v6_fixture.semantic_cases
        if item.case_id == case_id
    )


def test_context_v2_1_has_exact_minimal_surface_and_literal_occurrence_parity(
    v6_fixture,
):
    literal_occurrences_total = 0
    duplicated_literal_cases = set()

    for case in v6_fixture.semantic_cases:
        assert case.evidence_bundle is not None
        candidate = case.packet.context_v2_candidate
        payload = candidate.payload
        expected_literals = [
            item.literal_value
            for item in case.evidence_bundle.source_values
            if item.value_type != "source_reference"
        ]
        observed_literals = [
            item["literal"]
            for item in _walk_dicts(payload["source"])
            if "literal" in item
        ]

        assert tuple(payload) == CONTEXT_V2_1_BLOCKS
        assert payload["task"] == CONTEXT_V2_1_TASK
        assert tuple(payload["source"]) == ("children",)
        assert observed_literals == expected_literals
        assert all(
            CONTEXT_V2_1_FORBIDDEN_FIELDS.isdisjoint(item)
            for item in _walk_dicts(payload)
        )
        assert all(
            item.get("kind") in {"table", "row", "text segment"}
            for item in _walk_dicts(payload["source"])
            if "kind" in item
        )
        assert len(payload["type_cards"]) == 2
        assert len(payload["unclassified_reasons"]) == 3
        assert candidate.active is False
        assert candidate.transport_eligible is False

        literal_occurrences_total += len(observed_literals)
        if len(observed_literals) != len(set(observed_literals)):
            duplicated_literal_cases.add(case.case_id)

    assert literal_occurrences_total == 45
    assert duplicated_literal_cases == {
        "syn_successor_v2_adjacent_equal",
        "syn_successor_v2_adjacent_fx",
    }


def test_context_v2_1_receipt_restores_all_choices_and_bindings_exactly(
    v6_fixture,
):
    choices_total = 0
    compiled_bindings_total = 0
    visible_bindings_total = 0
    backend_bindings_total = 0

    for case in v6_fixture.semantic_cases:
        assert case.compilation is not None
        candidate = case.packet.context_v2_candidate
        receipt = case.packet.context_v2_mapping_receipt
        expected_restoration = [
            {
                "choice_key": f"choice_{index}",
                "json_pointer": f"/choices/{index - 1}",
                "typed_option_id": option.typed_option_id,
                "input_type_id": option.input_type_id,
                "role_bindings": [
                    {
                        "role_id": binding.role_id,
                        "source_value_ref": binding.source_value_ref,
                    }
                    for binding in option.role_bindings
                ],
            }
            for index, option in enumerate(
                case.compilation.typed_options,
                start=1,
            )
        ]
        expected_bindings = Counter(
            (
                f"choice_{index}",
                binding.role_id,
                binding.source_value_ref,
            )
            for index, option in enumerate(
                case.compilation.typed_options,
                start=1,
            )
            for binding in option.role_bindings
        )
        visible_bindings = Counter(
            (
                item["choice_key"],
                item["role_id"],
                item["source_value_ref"],
            )
            for item in receipt.binding_partition[
                "visible_differentiators"
            ]
        )
        backend_bindings = Counter(
            (
                item["choice_key"],
                item["role_id"],
                item["source_value_ref"],
            )
            for item in receipt.binding_partition[
                "backend_only_bindings"
            ]
        )

        assert list(receipt.choice_restoration) == expected_restoration
        assert visible_bindings + backend_bindings == expected_bindings
        assert visible_bindings & backend_bindings == Counter()
        assert [
            item["choice_key"] for item in candidate.payload["choices"]
        ] == [
            item["choice_key"] for item in receipt.choice_restoration
        ]

        choices_total += len(candidate.payload["choices"])
        compiled_bindings_total += sum(expected_bindings.values())
        visible_bindings_total += sum(visible_bindings.values())
        backend_bindings_total += sum(backend_bindings.values())

    assert choices_total == 12
    assert compiled_bindings_total == 59
    assert visible_bindings_total == 0
    assert backend_bindings_total == 59


def test_context_v2_1_budget_is_exact_and_materially_below_historical_v2(
    v6_fixture,
):
    current_total = 0
    historical_total = 0
    projection_factory = Gate2FinancialSemanticV5ProjectionFactory()

    for case in v6_fixture.semantic_cases:
        assert case.evidence_bundle is not None
        assert case.compilation is not None
        candidate = case.packet.context_v2_candidate
        historical_projection = projection_factory.create_context_v2_candidate(
            registry=v6_fixture.registry,
            source_family_id=case.evidence_bundle.source_family_id,
        )
        historical_candidate, _ = _context_v2_candidate_and_receipt(
            evidence_bundle=case.evidence_bundle,
            compilation=case.compilation,
            registry=v6_fixture.registry,
            projection=historical_projection,
            active_payload=case.packet.payload,
            active_packet_hash=case.packet.packet_hash,
        )

        assert candidate.model_visible_utf8_bytes == (
            EXPECTED_CASE_BYTES[case.case_id]
        )
        assert (
            candidate.model_visible_utf8_bytes
            <= CURRENT_CASE_ACCEPTANCE_TARGET_BYTES
        )
        assert candidate.model_visible_utf8_bytes <= len(
            _json_bytes(case.packet.payload)
        )
        current_total += candidate.model_visible_utf8_bytes
        historical_total += historical_candidate.model_visible_utf8_bytes

    assert current_total == 26_211
    assert current_total <= CONTEXT_V2_1_AGGREGATE_TARGET_BYTES
    assert historical_total == HISTORICAL_CONTEXT_V2_TOTAL_BYTES
    assert historical_total - current_total == 52_410
    assert current_total * 100 < historical_total * 34


def test_current_packet_factory_does_not_call_historical_context_v2_builder(
    v6_fixture,
    monkeypatch,
):
    case = v6_fixture.semantic_cases[0]
    assert case.evidence_bundle is not None
    assert case.compilation is not None

    def _forbidden_legacy_call(*args, **kwargs):
        raise AssertionError("historical Context V2.0 builder was called")

    monkeypatch.setattr(
        Gate2FinancialSemanticV5ProjectionFactory,
        "create_context_v2_candidate",
        _forbidden_legacy_call,
    )
    rebuilt = Gate2FinancialSemanticV6PacketFactory(
        registry=v6_fixture.registry
    ).create(
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
    )

    assert rebuilt.context_v2_candidate == case.packet.context_v2_candidate
    assert rebuilt.context_v2_mapping_receipt == (
        case.packet.context_v2_mapping_receipt
    )


def test_context_v2_1_rejects_resealed_literal_and_receipt_reordering(
    v6_fixture,
):
    case = _case(v6_fixture, "syn_successor_v2_unique_cash")
    assert case.evidence_bundle is not None
    assert case.compilation is not None
    packet = case.packet

    payload = copy.deepcopy(packet.context_v2_candidate.payload)
    first_values = next(
        item["values"]
        for item in _walk_dicts(payload["source"])
        if "values" in item
    )
    first_values.pop(0)
    tampered_candidate = replace(
        packet.context_v2_candidate,
        payload=payload,
        view_hash=_sha256(payload),
        model_visible_utf8_bytes=len(_json_bytes(payload)),
    )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_integrity_invalid",
    ):
        validate_financial_semantic_v6_packet(
            packet=replace(
                packet,
                context_v2_candidate=tampered_candidate,
            ),
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=v6_fixture.registry,
        )

    restoration = copy.deepcopy(
        list(packet.context_v2_mapping_receipt.choice_restoration)
    )
    restoration[0]["role_bindings"].reverse()
    tampered_receipt = replace(
        packet.context_v2_mapping_receipt,
        choice_restoration=tuple(restoration),
    )
    tampered_receipt = replace(
        tampered_receipt,
        integrity_hash=_sha256(
            _context_v2_1_mapping_receipt_payload_without_integrity(
                tampered_receipt
            ),
            sort_keys=True,
        ),
    )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_integrity_invalid",
    ):
        validate_financial_semantic_v6_packet(
            packet=replace(
                packet,
                context_v2_mapping_receipt=tampered_receipt,
            ),
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=v6_fixture.registry,
        )


def test_same_title_differentiators_are_minimal_and_collisions_fail_closed(
    v6_fixture,
):
    case = _case(v6_fixture, "syn_successor_v2_unique_cash")
    assert case.evidence_bundle is not None
    assert case.compilation is not None
    first_option = case.compilation.typed_options[0]
    first_binding = first_option.role_bindings[0]
    alternative_ref = next(
        item.source_value_ref
        for item in case.evidence_bundle.source_values
        if item.value_type != "source_reference"
        and item.source_value_ref != first_binding.source_value_ref
    )
    second_option = replace(
        first_option,
        typed_option_id=first_option.typed_option_id + ":synthetic",
        role_bindings=(
            replace(first_binding, source_value_ref=alternative_ref),
            *first_option.role_bindings[1:],
        ),
    )
    synthetic_compilation = replace(
        case.compilation,
        typed_options=(first_option, second_option),
    )
    top_nodes, values_by_ref, _ = _source_graph(
        evidence_bundle=case.evidence_bundle,
        guard=_ReadableCollisionGuard(),
    )
    assert top_nodes
    occurrences = _context_v2_1_differentiator_occurrences(
        evidence_bundle=case.evidence_bundle,
        compilation=synthetic_compilation,
        choice_key_by_id={
            first_option.typed_option_id: "choice_1",
            second_option.typed_option_id: "choice_2",
        },
        title_by_type_id={first_option.input_type_id: "Same title"},
        guard=_ReadableCollisionGuard(),
        values_by_ref=values_by_ref,
    )

    assert [
        (item.choice_key, item.role_id, item.source_value_ref)
        for item in occurrences
    ] == [
        ("choice_1", first_binding.role_id, first_binding.source_value_ref),
        ("choice_2", first_binding.role_id, alternative_ref),
    ]

    projection = (
        Gate2FinancialSemanticV5ProjectionFactory()
        .create_minimal_managed_projection()
    )
    collided_payload = copy.deepcopy(projection.payload)
    collided_audit = copy.deepcopy(projection.authority_audit)
    collided_payload["type_cards"][1]["title"] = (
        collided_payload["type_cards"][0]["title"]
    )
    collided_audit["type_cards"][1]["title"] = (
        collided_audit["type_cards"][0]["title"]
    )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_context_v2_1_type_title_collision",
    ):
        _context_v2_1_type_projection(
            replace(
                projection,
                payload=collided_payload,
                authority_audit=collided_audit,
            )
        )


def test_context_v2_1_is_non_transport_and_provider_free(v6_fixture):
    assert sum(
        case.packet.context_v2_candidate.provider_calls_total
        + case.packet.context_v2_mapping_receipt.provider_calls_total
        for case in v6_fixture.semantic_cases
    ) == 0
    assert all(
        case.packet.context_v2_candidate.active is False
        and case.packet.context_v2_candidate.transport_eligible is False
        and case.packet.context_v2_candidate.safe_summary()[
            "response_profile_status"
        ]
        == "not_implemented"
        for case in v6_fixture.semantic_cases
    )
