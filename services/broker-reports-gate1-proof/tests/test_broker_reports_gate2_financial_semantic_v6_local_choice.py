from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    estimate_gate2_request_input_tokens,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (  # noqa: E402,E501
    LOCAL_CHOICE_CANDIDATE_SCHEMA_VERSION,
    Gate2FinancialSemanticV6ChoiceContractFactory,
    Gate2FinancialSemanticV6ChoiceError,
    normalize_financial_semantic_v6_local_choice,
)
from broker_reports_gate1.gate2_financial_semantic_v6_expansion import (  # noqa: E402,E501
    Gate2FinancialSemanticV6DecisionExpansionFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (  # noqa: E402,E501
    financial_semantic_v6_canonical_request,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV6PacketError,
    Gate2FinancialSemanticV6PacketFactory,
    validate_financial_semantic_v6_packet,
)
from broker_reports_gate1.gate2_financial_semantic_v6_prompt import (  # noqa: E402,E501
    V6_SEMANTIC_SYSTEM_PROMPT,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_totality import (  # noqa: E402,E501
    Gate2FinancialSemanticV6TotalMaterializerFactory,
)


V6_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
)
V6_BASE_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
SNAPSHOT_KEY = b"v6-local-choice-test-snapshot-key"
CONTINUATION_KEY = b"v6-local-choice-test-continuation-key"
ACTIVE_CHOICE_SCHEMA_HASHES = {
    "syn_successor_v2_unique_cash": (
        "883381d22afd40c398e1c07040e4de456a4f14d8d4a0f3528e2f78b85664a45b"
    ),
    "syn_successor_v2_unique_printed_total": (
        "f86bb582b6289e9a80752c8e2a3b0a861a92cec438fd8becefda84fcd0ac1b32"
    ),
    "syn_successor_v2_multiple_compatible": (
        "36858a919a149f4b76ec61391ac68cce997cded103394d7966c079185b6cf88a"
    ),
    "syn_successor_v2_no_registry_type": (
        "10a54d609f1658982b18b12ed3a4ac1a8c0b39a3e35dcbfdf02af79abe728d7f"
    ),
    "syn_successor_v2_missing_discriminator": (
        "042d2cae2f9bb6113081654523b1aaec93fef359dd1cddadbe9d106919ef38ea"
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "36858a919a149f4b76ec61391ac68cce997cded103394d7966c079185b6cf88a"
    ),
    "syn_successor_v2_adjacent_equal": (
        "36858a919a149f4b76ec61391ac68cce997cded103394d7966c079185b6cf88a"
    ),
    "syn_successor_v2_adjacent_fx": (
        "36858a919a149f4b76ec61391ac68cce997cded103394d7966c079185b6cf88a"
    ),
    "syn_successor_v2_optional_missing": (
        "767a7d33ff91f7cbc215bc30621571d2148fe28eadddd5eb4e7a81a2df915d9a"
    ),
    "syn_successor_v2_forbidden_neighbour": (
        "ce787dff712b365c451082640038e6b353e3fae67f585557a026e1c26b65d226"
    ),
}


def _fixture():
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
    return _fixture()


def _contains_none(value) -> bool:
    if isinstance(value, dict):
        return any(
            item is None or _contains_none(item)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(item is None or _contains_none(item) for item in value)
    return False


def _model_visible_request(case) -> dict:
    candidate = case.choice_contract.local_candidate
    return {
        "messages": [
            {"role": "system", "content": V6_SEMANTIC_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    case.packet.slim_candidate.payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "semantic_choice",
                "strict": True,
                "schema": candidate.canonical_schema(),
            },
        },
    }


def test_local_candidate_full_model_view_has_zero_opaque_ids(v6_fixture):
    observed_choice_hashes = {}
    current_model_view_bytes = 0
    local_model_view_bytes = 0
    current_estimates = 0
    local_estimates = 0

    for case in v6_fixture.semantic_cases:
        packet = case.packet
        contract = case.choice_contract
        bundle = case.evidence_bundle
        compilation = case.compilation
        assert packet is not None
        assert contract is not None
        assert bundle is not None
        assert compilation is not None
        candidate = contract.local_candidate
        observed_choice_hashes[case.case_id] = contract.choice_schema_hash

        assert candidate.schema_version == (
            LOCAL_CHOICE_CANDIDATE_SCHEMA_VERSION
        )
        assert candidate.active is False
        assert candidate.provider_calls_total == 0
        assert candidate.post_response_repair_allowed is False
        assert candidate.choice_aliases == tuple(
            packet.slim_alias_receipt.choice_aliases
        )
        assert candidate.response_schema["title"] == "Semantic choice"
        assert _contains_none(candidate.response_schema) is False

        validator = Draft202012Validator(candidate.response_schema)
        for alias in candidate.choice_aliases:
            validator.validate({"choice": alias})
        for reason in candidate.unclassified_reason_codes:
            validator.validate(
                {"choice": "unclassified", "reason": reason}
            )

        model_view = _model_visible_request(case)
        current_request = financial_semantic_v6_canonical_request(
            packet=packet,
            choice_contract=contract,
        )
        current_projection = {
            "messages": current_request["messages"],
            "response_format": current_request["response_format"],
        }
        serialized = json.dumps(
            model_view,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        current_model_view_bytes += len(
            json.dumps(
                current_projection,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        local_model_view_bytes += len(
            json.dumps(
                model_view,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        current_estimates += estimate_gate2_request_input_tokens(
            current_request
        )
        local_estimates += estimate_gate2_request_input_tokens(model_view)
        opaque_values = {
            packet.packet_hash,
            packet.slim_candidate.view_hash,
            packet.slim_alias_receipt.integrity_hash,
            bundle.bundle_id,
            bundle.document_ref,
            bundle.normalization_run_ref,
            bundle.source_package_ref,
            bundle.source_scope_ref,
            *(
                item.source_value_ref
                for item in bundle.source_values
            ),
            *(
                item.association_ref
                for item in bundle.source_values
            ),
            *(
                item.input_type_id
                for item in compilation.typed_options
            ),
            *(
                item.typed_option_id
                for item in compilation.typed_options
            ),
        }
        assert all(value not in serialized for value in opaque_values)
        assert all(
            field not in serialized
            for field in (
                "return_id",
                "typed_option_id",
                "input_type_id",
                "source_value_ref",
                "association_ref",
            )
        )
        assert _contains_none(model_view) is False

    assert observed_choice_hashes == ACTIVE_CHOICE_SCHEMA_HASHES
    assert current_model_view_bytes == 89_220
    assert local_model_view_bytes == 26_404
    assert current_estimates == 22_950
    assert local_estimates == 7_247


def test_choice_order_permutation_rebuilds_exact_mapping(v6_fixture):
    case = next(
        item
        for item in v6_fixture.semantic_cases
        if item.case_id == "syn_successor_v2_unique_cash"
    )
    assert case.evidence_bundle is not None
    assert case.compilation is not None
    exact_ids = tuple(
        option.typed_option_id
        for option in case.compilation.typed_options
    )
    assert len(exact_ids) == 2
    reversed_ids = tuple(reversed(exact_ids))
    permuted_packet = Gate2FinancialSemanticV6PacketFactory(
        registry=v6_fixture.registry
    ).create(
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
        slim_choice_order=reversed_ids,
    )
    permuted_contract = Gate2FinancialSemanticV6ChoiceContractFactory(
        registry=v6_fixture.registry
    ).create(
        packet=permuted_packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
    )

    assert permuted_packet.payload == case.packet.payload
    assert permuted_packet.packet_hash == case.packet.packet_hash
    assert (
        permuted_packet.context_v2_candidate
        == case.packet.context_v2_candidate
    )
    assert (
        permuted_packet.context_v2_mapping_receipt
        == case.packet.context_v2_mapping_receipt
    )
    assert tuple(
        case.packet.slim_alias_receipt.choice_aliases.values()
    ) == exact_ids
    assert tuple(
        permuted_packet.slim_alias_receipt.choice_aliases.values()
    ) == reversed_ids
    assert [
        {
            "type": item["type"],
            "bindings": item["bindings"],
        }
        for item in permuted_packet.slim_candidate.payload["choices"]
    ] == [
        {
            "type": item["type"],
            "bindings": item["bindings"],
        }
        for item in reversed(
            case.packet.slim_candidate.payload["choices"]
        )
    ]
    assert normalize_financial_semantic_v6_local_choice(
        model_output={"choice": "A"},
        choice_contract=permuted_contract,
        packet=permuted_packet,
    ) == {
        "disposition": "typed_input",
        "typed_option_id": reversed_ids[0],
    }
    validate_financial_semantic_v6_packet(
        packet=permuted_packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
        registry=v6_fixture.registry,
    )

    for invalid_order in (
        (exact_ids[0], exact_ids[0]),
        (exact_ids[0], "unknown"),
        exact_ids[:1],
    ):
        with pytest.raises(
            Gate2FinancialSemanticV6PacketError,
            match="financial_semantic_v6_slim_choice_order_invalid",
        ):
            Gate2FinancialSemanticV6PacketFactory(
                registry=v6_fixture.registry
            ).create(
                evidence_bundle=case.evidence_bundle,
                source_package=case.scope.source_package,
                compilation=case.compilation,
                slim_choice_order=invalid_order,
            )


def test_local_choice_rejects_unknown_extra_duplicate_and_tampering(v6_fixture):
    case = next(
        item
        for item in v6_fixture.semantic_cases
        if item.case_id == "syn_successor_v2_unique_cash"
    )
    contract = case.choice_contract
    packet = case.packet

    invalid = (
        ({"choice": "unknown"}, "alias_unknown"),
        ({"choice": "A", "reason": "no_registry_type"}, "typed_shape_invalid"),
        (
            {"choice": "unclassified"},
            "unclassified_shape_invalid",
        ),
        (
            {"choice": "unclassified", "reason": "unknown"},
            "reason_invalid",
        ),
    )
    for model_output, code in invalid:
        with pytest.raises(
            Gate2FinancialSemanticV6ChoiceError,
            match=f"financial_semantic_v6_local_choice_{code}",
        ):
            normalize_financial_semantic_v6_local_choice(
                model_output=model_output,
                choice_contract=contract,
                packet=packet,
            )

    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_local_choice_duplicate_key",
    ):
        normalize_financial_semantic_v6_local_choice(
            model_output='{"choice":"A","choice":"B"}',
            choice_contract=contract,
            packet=packet,
        )

    tampered_candidate = replace(
        contract.local_candidate,
        response_schema_hash="0" * 64,
    )
    tampered_contract = replace(
        contract,
        local_candidate=tampered_candidate,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_local_choice_integrity_invalid",
    ):
        normalize_financial_semantic_v6_local_choice(
            model_output={"choice": "A"},
            choice_contract=tampered_contract,
            packet=packet,
        )

    aliases = list(packet.slim_alias_receipt.choice_aliases)
    exact_ids = list(packet.slim_alias_receipt.choice_aliases.values())
    swapped_receipt = replace(
        packet.slim_alias_receipt,
        choice_aliases=dict(zip(aliases, reversed(exact_ids), strict=True)),
    )
    swapped_packet = replace(
        packet,
        slim_alias_receipt=swapped_receipt,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_local_choice_integrity_invalid",
    ):
        normalize_financial_semantic_v6_local_choice(
            model_output={"choice": "A"},
            choice_contract=contract,
            packet=swapped_packet,
        )


def test_local_choice_expansion_and_materialization_match_current_path(
    v6_fixture,
):
    choices_total = 0

    for case in v6_fixture.semantic_cases:
        packet = case.packet
        contract = case.choice_contract
        bundle = case.evidence_bundle
        compilation = case.compilation
        assert packet is not None
        assert contract is not None
        assert bundle is not None
        assert compilation is not None
        expansion_factory = Gate2FinancialSemanticV6DecisionExpansionFactory(
            registry=v6_fixture.registry
        )
        local_outputs = [
            {"choice": alias}
            for alias in contract.local_candidate.choice_aliases
        ]
        local_outputs.extend(
            {
                "choice": "unclassified",
                "reason": reason,
            }
            for reason in contract.local_candidate.unclassified_reason_codes
        )

        for local_output in local_outputs:
            canonical_choice = normalize_financial_semantic_v6_local_choice(
                model_output=local_output,
                choice_contract=contract,
                packet=packet,
            )
            via_local = expansion_factory.create_from_local_candidate(
                model_output=local_output,
                choice_contract=contract,
                packet=packet,
                evidence_bundle=bundle,
                source_package=case.scope.source_package,
                compilation=compilation,
            )
            via_current = expansion_factory.create(
                model_output=canonical_choice,
                choice_contract=contract,
                packet=packet,
                evidence_bundle=bundle,
                source_package=case.scope.source_package,
                compilation=compilation,
            )
            assert via_local == via_current

            materializer = Gate2FinancialSemanticV6TotalMaterializerFactory(
                registry=v6_fixture.registry
            )
            materialized = materializer.create(
                expansion=via_local,
                model_output=canonical_choice,
                choice_contract=contract,
                packet=packet,
                evidence_bundle=bundle,
                source_package=case.scope.source_package,
                compilation=compilation,
            )
            materialized_current = materializer.create(
                expansion=via_current,
                model_output=canonical_choice,
                choice_contract=contract,
                packet=packet,
                evidence_bundle=bundle,
                source_package=case.scope.source_package,
                compilation=compilation,
            )
            assert materialized == materialized_current
            assert materialized.validated_but_unmaterializable is False
            assert materialized.materializer_totality_status == (
                "proven_for_expansion"
            )
            if canonical_choice["disposition"] == (
                "unclassified_financial_input"
            ):
                assert set(via_local.retained_source_value_refs) == set(
                    bundle.retention_set
                )
            choices_total += 1

    assert choices_total > len(v6_fixture.semantic_cases)
