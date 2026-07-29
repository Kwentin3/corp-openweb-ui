from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from collections import Counter
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
    CONTEXT_V2_1_AGGREGATE_TARGET_BYTES,
    CONTEXT_V2_1_BLOCKS,
    CONTEXT_V2_1_TASK,
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
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ProjectionFactory,
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
ACTIVE_PACKET_MINIFIED_SHA256_BASELINES = {
    "syn_successor_v2_unique_cash": (
        "8e36f80f2bcde76c54ac925d68c1d0689fb1cb7c532b742fcab0395ac9504c2e"
    ),
    "syn_successor_v2_unique_printed_total": (
        "8bbf5d44e81938470331c398877513a40f387c43294c63ab85500e9014b3101a"
    ),
    "syn_successor_v2_multiple_compatible": (
        "2185d47b0199586986ee846ba7090af14cc55e35b8418d3fda8c77eb396be571"
    ),
    "syn_successor_v2_no_registry_type": (
        "45afe499cfecedc3ee9d3504e2275b953a1241e26a5a954d0df5d879db029314"
    ),
    "syn_successor_v2_missing_discriminator": (
        "246c0eade02cfea33b6573c7d630c93a3b16cdae1c5966716804a57d528311be"
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "b2b11905259090a31dc0abbeffaa1e32e25a423705329fbe90a634e635bd3566"
    ),
    "syn_successor_v2_adjacent_equal": (
        "d0a6de192a59fb5a24bb59b74f60e28db1a9cf4c39faa10fb25b365e4d2b41bf"
    ),
    "syn_successor_v2_adjacent_fx": (
        "ec98eaabc2d80619b4d588c103994d0b1255299adcd34d03d63b17f1b5206164"
    ),
    "syn_successor_v2_optional_missing": (
        "1ef10407214aa4064570d8b9b591e5de3aaa3a5732d94d530147285c781a23e1"
    ),
    "syn_successor_v2_forbidden_neighbour": (
        "2e291d7fa01fec0be365eaa5be6783e58ae230f1e2d6a8d53ec677120e64ca74"
    ),
}
CONTEXT_V2_1_BASELINES = {
    "syn_successor_v2_unique_cash": (
        "9068537cd35e7ca5f503f5f167440b44ba79f240e442f4c8ede8742c7de8e714",
        2645,
    ),
    "syn_successor_v2_unique_printed_total": (
        "f80e669e56266b1778cc997c3da7f71bcdd279ae696c126a1024cf008802e54c",
        2643,
    ),
    "syn_successor_v2_multiple_compatible": (
        "4dd76de2e81a18d12af9c9a96702f975602fc1bece7ddaccc93aabef769984c2",
        2624,
    ),
    "syn_successor_v2_no_registry_type": (
        "8475b9ce840a4801b4792a347306a5ba85a40a8d10e08e9cfcd80d5b914b1007",
        2640,
    ),
    "syn_successor_v2_missing_discriminator": (
        "3c0fe72cea84a6156df49598cb3eef5765e0b40988a541cf60ee2e4a197d3f5c",
        2584,
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "bfbe343eff9f269cdbe87b677cd8a1657c75c4d7d4fb199c6edb83a79020eba0",
        2584,
    ),
    "syn_successor_v2_adjacent_equal": (
        "cb8c5630d6d19c8f386de5e6fe036f768a716d787fbee685dd952da5b03af595",
        2580,
    ),
    "syn_successor_v2_adjacent_fx": (
        "5a6d198b672a615464e03df9ec990c48e9b7cbc12e5a8bb1f25fa1108b326f7c",
        2624,
    ),
    "syn_successor_v2_optional_missing": (
        "4e1e9e5cbb071feb6812544b74c0f56ee8f748715d5bbe38dffde4a5fd65ece0",
        2643,
    ),
    "syn_successor_v2_forbidden_neighbour": (
        "e04c3f24b287dca1be398fcabcdc1ec4e637402a16f612969d7a6a58ff58a108",
        2644,
    ),
}
ZERO_CHOICE_CASE_IDS = {
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_detail_vs_subtotal",
    "syn_successor_v2_adjacent_equal",
    "syn_successor_v2_adjacent_fx",
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


def _primitive_leaf_entries(value, pointer: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            segment = str(key).replace("~", "~0").replace("/", "~1")
            yield from _primitive_leaf_entries(
                item,
                pointer + "/" + segment,
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _primitive_leaf_entries(
                item,
                pointer + "/" + str(index),
            )
    else:
        yield pointer, value


def _json_pointer_get(value, pointer: str):
    current = value
    for raw_segment in pointer.removeprefix("/").split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[segment]
        else:
            current = current[int(segment)]
    return current


def _minified_json_bytes(value, *, sort_keys: bool) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=sort_keys,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_minified(value, *, sort_keys: bool) -> str:
    return hashlib.sha256(_minified_json_bytes(value, sort_keys=sort_keys)).hexdigest()


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


def test_context_v2_preserves_all_frozen_active_packet_exact_bytes(v6_fixture):
    observed = {}

    for case in v6_fixture.semantic_cases:
        active_bytes = _minified_json_bytes(
            case.packet.payload,
            sort_keys=False,
        )
        observed[case.case_id] = hashlib.sha256(active_bytes).hexdigest()

    assert len(observed) == 10
    assert observed == ACTIVE_PACKET_MINIFIED_SHA256_BASELINES


def test_context_v2_1_is_deterministic_non_active_and_keeps_managed_surface(
    v6_fixture,
):
    observed_zero_choice_cases = set()
    provider_calls_total = 0
    aggregate_bytes = 0
    minimal_projection = (
        Gate2FinancialSemanticV5ProjectionFactory()
        .create_minimal_managed_projection()
    )

    for case in v6_fixture.semantic_cases:
        packet = case.packet
        candidate = packet.context_v2_candidate
        receipt = packet.context_v2_mapping_receipt
        assert case.evidence_bundle is not None
        assert case.compilation is not None

        rebuilt = Gate2FinancialSemanticV6PacketFactory(
            registry=v6_fixture.registry
        ).create(
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
        )

        assert candidate.active is False
        assert candidate.transport_eligible is False
        assert candidate.provider_calls_total == 0
        assert receipt.provider_calls_total == 0
        assert candidate == rebuilt.context_v2_candidate
        assert receipt == rebuilt.context_v2_mapping_receipt
        assert tuple(candidate.payload) == CONTEXT_V2_1_BLOCKS
        assert candidate.payload["task"] == CONTEXT_V2_1_TASK
        assert tuple(candidate.payload["source"]) == ("children",)
        assert candidate.payload["type_cards"] == (
            minimal_projection.payload["type_cards"]
        )
        assert candidate.payload["unclassified_reasons"] == (
            minimal_projection.payload["unclassified_reasons"]
        )
        assert candidate.view_hash == _sha256_minified(
            candidate.payload,
            sort_keys=False,
        )
        assert candidate.model_visible_utf8_bytes == len(
            _minified_json_bytes(candidate.payload, sort_keys=False)
        )
        assert (
            candidate.view_hash,
            candidate.model_visible_utf8_bytes,
        ) == CONTEXT_V2_1_BASELINES[case.case_id]
        assert candidate.model_visible_utf8_bytes <= len(
            _minified_json_bytes(packet.payload, sort_keys=False)
        )
        assert len(candidate.payload["type_cards"]) == 2
        assert len(receipt.type_mappings) == 2
        assert len(candidate.payload["unclassified_reasons"]) == 3

        if not case.compilation.typed_options:
            observed_zero_choice_cases.add(case.case_id)
            assert candidate.payload["choices"] == []
            assert len(candidate.payload["type_cards"]) == 2

        provider_calls_total += candidate.provider_calls_total
        provider_calls_total += receipt.provider_calls_total
        aggregate_bytes += candidate.model_visible_utf8_bytes

    assert observed_zero_choice_cases == ZERO_CHOICE_CASE_IDS
    assert aggregate_bytes == 26_211
    assert aggregate_bytes <= CONTEXT_V2_1_AGGREGATE_TARGET_BYTES
    assert provider_calls_total == 0


def test_context_v2_1_renders_each_frozen_semantic_literal_occurrence_once(
    v6_fixture,
):
    for case in v6_fixture.semantic_cases:
        assert case.evidence_bundle is not None
        expected_literals = Counter(
            item.literal_value
            for item in case.evidence_bundle.source_values
            if item.value_type != "source_reference"
        )
        rendered_literals = Counter(
            item["literal"]
            for item in _walk_dicts(case.packet.context_v2_candidate.payload["source"])
            if "literal" in item
        )

        assert rendered_literals == expected_literals


def test_context_v2_1_model_view_excludes_backend_identities_and_nulls(
    v6_fixture,
):
    forbidden_keys = {
        "association_ref",
        "bundle_id",
        "input_type_id",
        "integrity_hash",
        "package_ref",
        "source_ref",
        "source_value_ref",
        "storage_id",
        "typed_option_id",
    }

    for case in v6_fixture.semantic_cases:
        packet = case.packet
        bundle = case.evidence_bundle
        compilation = case.compilation
        assert bundle is not None
        assert compilation is not None
        payload = packet.context_v2_candidate.payload
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        assert _contains_none(payload) is False
        assert all(
            forbidden_keys.isdisjoint(item)
            for item in _walk_dicts(payload)
        )
        assert re.findall(
            r"\b[a-z][a-z0-9_]+_v\d+\b",
            serialized,
        ) == []
        assert re.findall(r"\b[0-9a-f]{64}\b", serialized) == []

        private_exact_values = {
            v6_fixture.registry.registry_id,
            v6_fixture.registry.registry_version,
            v6_fixture.registry.registry_hash,
            bundle.bundle_id,
            bundle.source_package_ref,
            bundle.source_package_integrity_hash,
            bundle.normalization_run_ref,
            bundle.document_ref,
            bundle.source_scope_ref,
            bundle.integrity_hash,
            compilation.evidence_bundle_id,
            compilation.evidence_bundle_integrity_hash,
            compilation.semantic_pack_id,
            compilation.semantic_pack_integrity_sha256,
            compilation.integrity_hash,
            packet.packet_hash,
            packet.evidence_bundle_integrity_hash,
            packet.candidate_compilation_integrity_hash,
            packet.semantic_projection_hash,
        }
        private_exact_values.update(bundle.provenance_refs)
        private_exact_values.update(bundle.retention_set)
        private_exact_values.update(
            declaration.input_type_id
            for declaration in v6_fixture.registry.declarations
        )
        for source in bundle.source_values:
            private_exact_values.update(
                {
                    source.source_value_ref,
                    source.source_ref,
                    source.association_ref,
                    *source.source_evidence_refs,
                    source.lineage.document_ref,
                    source.lineage.page_ref,
                    source.lineage.table_ref,
                    source.lineage.row_ref,
                    source.lineage.cell_ref,
                    source.lineage.text_segment_ref,
                }
            )
            if source.value_type == "source_reference":
                private_exact_values.add(source.literal_value)
        for option in compilation.typed_options:
            private_exact_values.update(
                {
                    option.typed_option_id,
                    option.input_type_id,
                }
            )

        assert all(
            value not in serialized
            for value in private_exact_values
            if isinstance(value, str) and value
        )


def test_context_v2_1_local_keys_have_consumers_and_restore_exact_options(
    v6_fixture,
):
    for case in v6_fixture.semantic_cases:
        candidate = case.packet.context_v2_candidate
        receipt = case.packet.context_v2_mapping_receipt
        assert case.compilation is not None

        assert [
            item["type_key"] for item in candidate.payload["type_cards"]
        ] == [item["type_key"] for item in receipt.type_mappings]
        assert [
            item["choice_key"] for item in candidate.payload["choices"]
        ] == [item["choice_key"] for item in receipt.choice_restoration]
        assert [
            (
                item["choice_key"],
                item["typed_option_id"],
                item["input_type_id"],
                tuple(
                    (binding["role_id"], binding["source_value_ref"])
                    for binding in item["role_bindings"]
                ),
            )
            for item in receipt.choice_restoration
        ] == [
            (
                f"choice_{index}",
                option.typed_option_id,
                option.input_type_id,
                tuple(
                    (binding.role_id, binding.source_value_ref)
                    for binding in option.role_bindings
                ),
            )
            for index, option in enumerate(
                case.compilation.typed_options,
                start=1,
            )
        ]
        source_keys = [
            (key, value)
            for item in _walk_dicts(candidate.payload["source"])
            for key, value in item.items()
            if key in {"value_key", "structure_key"}
        ]
        differentiator_targets = [
            (key, value)
            for choice in candidate.payload["choices"]
            for differentiator in choice.get("differentiators", ())
            for key, value in differentiator.items()
            if key in {"value_key", "structure_key"}
        ]
        assert source_keys == differentiator_targets == []
        assert receipt.binding_partition["visible_differentiators"] == []


def test_context_v2_1_receipt_pins_authorities_and_source_occurrences(
    v6_fixture,
):
    minimal_projection = (
        Gate2FinancialSemanticV5ProjectionFactory()
        .create_minimal_managed_projection()
    )
    for case in v6_fixture.semantic_cases:
        candidate = case.packet.context_v2_candidate
        receipt = case.packet.context_v2_mapping_receipt
        assert case.evidence_bundle is not None

        rows = receipt.source_mappings["occurrences"]
        expected_values = [
            item
            for item in case.evidence_bundle.source_values
            if item.value_type != "source_reference"
        ]
        assert len(rows) == len(expected_values)
        for row, value in zip(rows, expected_values, strict=True):
            rendered = _json_pointer_get(
                candidate.payload,
                row["json_pointer"],
            )
            assert rendered["literal"] == value.literal_value
            assert row["source_value_ref"] == value.source_value_ref
            assert row["source_ref"] == value.source_ref
            assert row["association_ref"] == value.association_ref
            assert row["source_evidence_refs"] == list(
                value.source_evidence_refs
            )

        receipt_material = receipt.to_private_dict()
        integrity_hash = receipt_material.pop("integrity_hash")
        assert integrity_hash == _sha256_minified(
            receipt_material,
            sort_keys=True,
        )
        assert receipt.identities["context_view_hash"] == candidate.view_hash
        assert receipt.identities["active_packet_hash"] == (case.packet.packet_hash)
        assert receipt.identities["minimal_projection_hash"] == (
            minimal_projection.projection_hash
        )
        assert receipt.identities[
            "minimal_projection_authority_audit_hash"
        ] == minimal_projection.authority_audit_hash


def test_context_v2_1_frozen_binding_accounting_oracle(v6_fixture):
    visible_differentiators_total = 0
    compiled_bindings_total = 0
    backend_only_bindings_total = 0

    for case in v6_fixture.semantic_cases:
        assert case.compilation is not None
        rows = case.packet.context_v2_mapping_receipt.binding_partition[
            "visible_differentiators"
        ]
        backend_rows = case.packet.context_v2_mapping_receipt.binding_partition[
            "backend_only_bindings"
        ]
        case_compiled_total = sum(
            len(option.role_bindings) for option in case.compilation.typed_options
        )

        assert len(rows) + len(backend_rows) == case_compiled_total
        compiled_bindings_total += case_compiled_total
        visible_differentiators_total += len(rows)
        backend_only_bindings_total += len(backend_rows)

    assert compiled_bindings_total == 59
    assert visible_differentiators_total == 0
    assert backend_only_bindings_total == 59


def test_context_v2_1_tampering_is_rejected_by_public_packet_validator(
    v6_fixture,
):
    case = v6_fixture.semantic_cases[0]
    packet = case.packet
    assert case.evidence_bundle is not None
    assert case.compilation is not None

    tampered_payload = copy.deepcopy(packet.context_v2_candidate.payload)
    tampered_payload["task"] = "tampered"
    tampered_candidate = replace(
        packet.context_v2_candidate,
        payload=tampered_payload,
        view_hash=_sha256_minified(tampered_payload, sort_keys=False),
        model_visible_utf8_bytes=len(
            _minified_json_bytes(tampered_payload, sort_keys=False)
        ),
    )
    tampered_packet = replace(
        packet,
        context_v2_candidate=tampered_candidate,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_integrity_invalid",
    ):
        validate_financial_semantic_v6_packet(
            packet=tampered_packet,
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=v6_fixture.registry,
        )

    tampered_restoration = (
        packet.context_v2_mapping_receipt.choice_restoration[:-1]
    )
    tampered_receipt = replace(
        packet.context_v2_mapping_receipt,
        choice_restoration=tampered_restoration,
    )
    receipt_material = tampered_receipt.to_private_dict()
    receipt_material.pop("integrity_hash")
    tampered_receipt = replace(
        tampered_receipt,
        integrity_hash=_sha256_minified(
            receipt_material,
            sort_keys=True,
        ),
    )
    tampered_packet = replace(
        packet,
        context_v2_mapping_receipt=tampered_receipt,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_v6_packet_integrity_invalid",
    ):
        validate_financial_semantic_v6_packet(
            packet=tampered_packet,
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=v6_fixture.registry,
        )
