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
from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    TOKEN_ESTIMATOR_ID,
    estimate_gate2_request_input_tokens,
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
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (  # noqa: E402,E501
    financial_semantic_v6_canonical_request,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    SEMANTIC_PACKET_AMBIGUITY_RULE,
    SEMANTIC_PACKET_BLOCKS,
    SEMANTIC_PACKET_FORBIDDEN_FIELDS,
    SEMANTIC_PACKET_SCHEMA_VERSION,
    SEMANTIC_PACKET_TYPE_CARD_FIELDS,
    SLIM_ALIAS_RECEIPT_SCHEMA_VERSION,
    SLIM_VIEW_SCHEMA_VERSION,
    Gate2FinancialSemanticV6PacketError,
    Gate2FinancialSemanticV6PacketFactory,
    render_financial_semantic_v6_packet_private_exact,
    render_financial_semantic_v6_packet_repository_safe,
    render_financial_semantic_v6_slim_alias_receipt_private_exact,
    render_financial_semantic_v6_slim_candidate_private_exact,
    validate_financial_semantic_v6_packet,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"
V6_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
)
V6_BASE_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
SNAPSHOT_KEY = b"v6-slim-view-test-snapshot-key-32"
CONTINUATION_KEY = b"v6-slim-view-test-continuation-key"
ACTIVE_PACKET_BASELINES = {
    "syn_successor_v2_unique_cash": (
        "3bcb297a62bf17d74f032b4058dc4c4f3097f33de9f89626b194d4a1600b6851",
        9638,
    ),
    "syn_successor_v2_unique_printed_total": (
        "bf63a8bef84415ad2502f3403824eff71bcc386d6c5ea6bb839cdde9870a60c3",
        9905,
    ),
    "syn_successor_v2_multiple_compatible": (
        "82a22e646b96e3588172f3f52f281b4e17aace30842699870abe7933341d5865",
        4246,
    ),
    "syn_successor_v2_no_registry_type": (
        "871385de7814271f6eea35ea930be04c70f92ebc0f4c11d9d19d71f8848e25f5",
        9770,
    ),
    "syn_successor_v2_missing_discriminator": (
        "27ff112adfaec49dc6fe30e1ce0de0be127628ca79838c2b4f1171a7ad1fc775",
        9145,
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "ec252ed7652fd7348b3f618a381da0efdc2c494d36384e94dea79a014cab92c6",
        3822,
    ),
    "syn_successor_v2_adjacent_equal": (
        "9eae5bc8bd399fdb7404f1a3caa22d3d8d56a590d933f0d3c4bab3bdfa689621",
        3724,
    ),
    "syn_successor_v2_adjacent_fx": (
        "160bdefb600523800bbc26c08435af9149103025b0a144021b5dbaf902a607f9",
        4066,
    ),
    "syn_successor_v2_optional_missing": (
        "31a3fdfe2b56cc81fbdd672b16a5ed94c43116dcb8726199d5287e2eeaa15fb2",
        9779,
    ),
    "syn_successor_v2_forbidden_neighbour": (
        "8504e930fdaadecc5353a895ab03ec15a8f3aab6fe1fd0bb33accb778bc95dea",
        9875,
    ),
}


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


def _v6_fixture():
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


@pytest.fixture(scope="module")
def v6_fixture():
    return _v6_fixture()


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _contains_none(value) -> bool:
    if isinstance(value, dict):
        return any(
            item is None or _contains_none(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(item is None or _contains_none(item) for item in value)
    return False


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
    assert all(
        tuple(card) == SEMANTIC_PACKET_TYPE_CARD_FIELDS
        for card in packet.payload["available_type_cards"]
    )
    assert all(
        "examples" not in card and "counterexamples" not in card
        for card in packet.payload["available_type_cards"]
    )
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
    assert safe_payload["non_active_slim_candidate"]["active"] is False
    assert safe_payload["non_active_slim_candidate"]["provider_calls_total"] == 0
    assert (
        safe_payload["private_slim_alias_receipt"]["provider_calls_total"] == 0
    )


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


def test_slim_candidate_preserves_all_frozen_active_packet_bytes(v6_fixture):
    observed = {}

    for case in v6_fixture.semantic_cases:
        packet = case.packet
        active_bytes = len(
            json.dumps(
                packet.payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        observed[case.case_id] = (packet.packet_hash, active_bytes)
        assert packet.slim_candidate.schema_version == SLIM_VIEW_SCHEMA_VERSION
        assert packet.slim_candidate.active is False
        assert packet.slim_candidate.provider_calls_total == 0
        assert (
            packet.slim_alias_receipt.schema_version
            == SLIM_ALIAS_RECEIPT_SCHEMA_VERSION
        )
        assert packet.slim_alias_receipt.active_packet_hash == packet.packet_hash
        assert packet.slim_alias_receipt.provider_calls_total == 0

    assert observed == ACTIVE_PACKET_BASELINES


def test_slim_candidate_has_exact_literal_and_alias_totality(v6_fixture):
    for case in v6_fixture.semantic_cases:
        packet = case.packet
        bundle = case.evidence_bundle
        compilation = case.compilation
        candidate = packet.slim_candidate
        receipt = packet.slim_alias_receipt
        assert bundle is not None
        assert compilation is not None

        semantic_values = {
            item.source_value_ref: item
            for item in bundle.source_values
            if item.value_type != "source_reference"
        }
        reference_values = {
            item.source_value_ref
            for item in bundle.source_values
            if item.value_type == "source_reference"
        }
        rendered_values = {
            item["alias"]: item
            for item in _walk_dicts(candidate.payload["source"])
            if "value" in item
        }
        parent_by_value_alias = {
            value["alias"]: node
            for node in _walk_dicts(candidate.payload["source"])
            if "values" in node
            for value in node["values"]
        }

        assert _contains_none(candidate.payload) is False
        assert set(receipt.value_aliases.values()) == set(semantic_values)
        assert set(rendered_values) == set(receipt.value_aliases)
        assert set(receipt.evidence_only_source_refs) == reference_values
        assert set(receipt.evidence_only_aliases) == reference_values
        assert set(receipt.evidence_only_aliases.values()).issubset(
            receipt.structural_aliases
        )

        for alias, source_value_ref in receipt.value_aliases.items():
            source = semantic_values[source_value_ref]
            rendered = rendered_values[alias]
            parent = parent_by_value_alias[alias]
            assert rendered["value"] == source.literal_value
            assert rendered["type"] == source.value_type.removeprefix(
                "source_"
            ).replace("_", " ")
            assert parent.get("row_role") == source.row_role
            assert parent.get("section_role") == source.section_role
            if source.visible_label is not None:
                assert source.visible_label in {
                    rendered["meaning"],
                    rendered.get("label"),
                }
            if source.column_meaning is not None:
                assert rendered["meaning"] == source.column_meaning

        serialized = json.dumps(
            candidate.payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        forbidden_exact = {
            bundle.bundle_id,
            bundle.document_ref,
            bundle.normalization_run_ref,
            bundle.source_package_ref,
            bundle.source_scope_ref,
            *(item.source_value_ref for item in bundle.source_values),
            *(item.association_ref for item in bundle.source_values),
            *(item.input_type_id for item in compilation.typed_options),
        }
        assert all(item not in serialized for item in forbidden_exact)
        assert [item["alias"] for item in candidate.payload["choices"]] == list(
            receipt.choice_aliases
        )
        assert set(receipt.choice_aliases.values()) == {
            item.typed_option_id for item in compilation.typed_options
        }
        assert all(
            item.typed_option_id not in serialized
            for item in compilation.typed_options
        )


def test_slim_candidate_bindings_resolve_to_exact_compiled_options(v6_fixture):
    for case in v6_fixture.semantic_cases:
        packet = case.packet
        compilation = case.compilation
        assert compilation is not None
        receipt = packet.slim_alias_receipt
        type_id_by_alias = receipt.type_aliases

        for rendered, option in zip(
            packet.slim_candidate.payload["choices"],
            compilation.typed_options,
            strict=True,
        ):
            rendered_bindings = [
                {
                    "role_id": raw.split("=", 1)[0],
                    "target_alias": raw.split("=", 1)[1],
                }
                for raw in rendered["bindings"]
            ]
            exact_bindings = [
                {
                    "role_id": item.role_id,
                    "source_value_ref": item.source_value_ref,
                }
                for item in option.role_bindings
            ]
            assert receipt.choice_aliases[rendered["alias"]] == (
                option.typed_option_id
            )
            assert type_id_by_alias[rendered["type"]] == option.input_type_id
            assert receipt.choice_role_bindings[rendered["alias"]] == (
                exact_bindings
            )
            assert [item["role_id"] for item in rendered_bindings] == [
                item["role_id"] for item in exact_bindings
            ]
            for displayed, exact in zip(
                rendered_bindings,
                exact_bindings,
                strict=True,
            ):
                semantic_alias = next(
                    (
                        alias
                        for alias, source_value_ref in (
                            receipt.value_aliases.items()
                        )
                        if source_value_ref == exact["source_value_ref"]
                    ),
                    None,
                )
                expected_target = (
                    semantic_alias
                    or receipt.evidence_only_aliases[
                        exact["source_value_ref"]
                    ]
                )
                assert displayed["target_alias"] == expected_target


def test_slim_candidate_is_deterministic_and_non_active(v6_fixture):
    for case in v6_fixture.semantic_cases:
        assert case.evidence_bundle is not None
        assert case.compilation is not None
        rebuilt = Gate2FinancialSemanticV6PacketFactory(
            registry=v6_fixture.registry
        ).create(
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
        )
        assert rebuilt.payload == case.packet.payload
        assert rebuilt.packet_hash == case.packet.packet_hash
        assert rebuilt.slim_candidate == case.packet.slim_candidate
        assert rebuilt.slim_alias_receipt == case.packet.slim_alias_receipt

    assert sum(
        case.packet.slim_candidate.model_visible_utf8_bytes
        for case in v6_fixture.semantic_cases
    ) == 18_098
    assert sum(
        ACTIVE_PACKET_BASELINES[case.case_id][1]
        for case in v6_fixture.semantic_cases
    ) == 73_970


def test_slim_size_projection_changes_only_the_non_active_user_view(v6_fixture):
    current_estimates = []
    slim_estimates = []

    for case in v6_fixture.semantic_cases:
        current_request = financial_semantic_v6_canonical_request(
            packet=case.packet,
            choice_contract=case.choice_contract,
        )
        candidate_request = copy.deepcopy(current_request)
        candidate_request["messages"][1]["content"] = json.dumps(
            case.packet.slim_candidate.payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        assert json.loads(current_request["messages"][1]["content"]) == (
            case.packet.payload
        )
        assert json.loads(current_request["messages"][1]["content"]) != (
            case.packet.slim_candidate.payload
        )
        assert candidate_request["messages"][0] == (
            current_request["messages"][0]
        )
        assert candidate_request["response_format"] == (
            current_request["response_format"]
        )
        assert candidate_request["model"] == current_request["model"]
        assert candidate_request["messages"][1] != (
            current_request["messages"][1]
        )
        current_estimates.append(
            estimate_gate2_request_input_tokens(current_request)
        )
        slim_estimates.append(
            estimate_gate2_request_input_tokens(candidate_request)
        )

    assert TOKEN_ESTIMATOR_ID == (
        "compact_request_utf8_bytes_div_4_plus_64_v1"
    )
    assert sum(current_estimates) == 22_950
    assert sum(slim_estimates) == 7_941


def test_slim_private_renderers_and_tampering_fail_closed():
    packet, registry, scope, bundle, compilation = _packet()
    candidate_json = render_financial_semantic_v6_slim_candidate_private_exact(
        packet=packet
    )
    receipt_json = (
        render_financial_semantic_v6_slim_alias_receipt_private_exact(
            packet=packet
        )
    )

    assert json.loads(candidate_json) == packet.slim_candidate.payload
    assert json.loads(receipt_json) == (
        packet.slim_alias_receipt.to_private_dict()
    )
    assert all(
        item.source_value_ref not in candidate_json
        and item.source_value_ref in receipt_json
        for item in bundle.source_values
    )

    tampered_payload = copy.deepcopy(packet.slim_candidate.payload)
    tampered_payload["task"] = "tampered"
    tampered_candidate = replace(
        packet.slim_candidate,
        payload=tampered_payload,
    )
    tampered_packet = replace(packet, slim_candidate=tampered_candidate)
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_integrity_invalid",
    ):
        validate_financial_semantic_v6_packet(
            packet=tampered_packet,
            evidence_bundle=bundle,
            source_package=scope.source_package,
            compilation=compilation,
            registry=registry,
        )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_render_input_invalid",
    ):
        render_financial_semantic_v6_slim_candidate_private_exact(
            packet=tampered_packet
        )

    tampered_receipt = replace(
        packet.slim_alias_receipt,
        integrity_hash="0" * 64,
    )
    tampered_packet = replace(
        packet,
        slim_alias_receipt=tampered_receipt,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_integrity_invalid",
    ):
        validate_financial_semantic_v6_packet(
            packet=tampered_packet,
            evidence_bundle=bundle,
            source_package=scope.source_package,
            compilation=compilation,
            registry=registry,
        )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_render_input_invalid",
    ):
        render_financial_semantic_v6_slim_alias_receipt_private_exact(
            packet=tampered_packet
        )

    malformed_receipt = replace(
        packet.slim_alias_receipt,
        choice_aliases=[],
    )
    malformed_packet = replace(
        packet,
        slim_alias_receipt=malformed_receipt,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_integrity_invalid",
    ):
        validate_financial_semantic_v6_packet(
            packet=malformed_packet,
            evidence_bundle=bundle,
            source_package=scope.source_package,
            compilation=compilation,
            registry=registry,
        )
