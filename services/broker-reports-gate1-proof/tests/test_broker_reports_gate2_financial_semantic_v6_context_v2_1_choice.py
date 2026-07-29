from __future__ import annotations

import copy
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (  # noqa: E402,E501
    CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_POLICY_VERSION,
    CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_SCHEMA_VERSION,
    CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES,
    Gate2FinancialSemanticV6ChoiceError,
    _choice_schema,
    normalize_financial_semantic_v6_context_v2_1_choice,
    normalize_financial_semantic_v6_local_choice,
    validate_financial_semantic_v6_choice_contract,
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
SNAPSHOT_KEY = b"v6-context-v2-1-choice-test-snapshot-key"
CONTINUATION_KEY = b"v6-context-v2-1-choice-test-continuation-key"
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
HISTORICAL_LOCAL_CHOICE_SCHEMA_HASHES = {
    "adf7dbf67b563db7d82292fbacae541e204fbe1cb34cf1fca77d2fee8279eff4",
    "85282d67c857893808c1e6882037e710aa75bc3fb6a10e7bafdcf8e90fe4939a",
}
CONTEXT_V2_1_RESPONSE_SCHEMA_BASELINES = {
    0: (
        "bd17c1792c0b42e24c7639d4dc5614e1c961942245fca76a32a40566f8b5bb90",
        274,
    ),
    2: (
        "0b726d1b40ceefee44abc53cdf9d343c09c06457201841ac30d84cb1bd05efc4",
        416,
    ),
}
ZERO_CHOICE_CASE_IDS = {
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_detail_vs_subtotal",
    "syn_successor_v2_adjacent_equal",
    "syn_successor_v2_adjacent_fx",
}


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


def _case(v6_fixture, case_id: str):
    return next(
        item for item in v6_fixture.semantic_cases if item.case_id == case_id
    )


def _reseal_profile(profile, **changes):
    interim = replace(profile, **changes, integrity_hash="")
    material = asdict(interim)
    material.pop("integrity_hash")
    return replace(interim, integrity_hash=sha256_json(material))


def _reseal_receipt(receipt, restoration_rows):
    material = receipt.to_private_dict()
    material.pop("integrity_hash")
    material["choice_restoration"] = copy.deepcopy(list(restoration_rows))
    return replace(
        receipt,
        choice_restoration=tuple(copy.deepcopy(restoration_rows)),
        integrity_hash=sha256_json(material),
    )


def test_context_v2_1_response_profile_is_inactive_closed_and_versioned(
    v6_fixture,
):
    observed_active_hashes = {}
    observed_historical_hashes = set()
    zero_choice_cases = set()

    for case in v6_fixture.semantic_cases:
        contract = case.choice_contract
        packet = case.packet
        assert contract is not None
        assert packet is not None
        profile = contract.context_v2_1_response_profile
        observed_active_hashes[case.case_id] = contract.choice_schema_hash
        observed_historical_hashes.add(
            contract.local_candidate.response_schema_hash
        )

        assert profile.schema_version == (
            CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_SCHEMA_VERSION
        )
        assert profile.policy_version == (
            CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_POLICY_VERSION
        )
        assert profile.active is False
        assert profile.transport_eligible is False
        assert profile.provider_calls_total == 0
        assert profile.post_response_repair_allowed is False
        assert profile.packet_hash == packet.packet_hash
        assert profile.context_view_hash == packet.context_v2_candidate.view_hash
        assert profile.mapping_receipt_integrity_hash == (
            packet.context_v2_mapping_receipt.integrity_hash
        )
        assert profile.canonical_choice_schema_hash == (
            contract.choice_schema_hash
        )
        assert profile.response_schema_hash == sha256_json(
            profile.response_schema
        )
        response_schema_bytes = json.dumps(
            profile.response_schema,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=False,
        ).encode("utf-8")
        assert (
            profile.response_schema_hash,
            len(response_schema_bytes),
        ) == CONTEXT_V2_1_RESPONSE_SCHEMA_BASELINES[len(profile.choice_keys)]
        assert profile.choice_keys == tuple(
            item["choice_key"]
            for item in packet.context_v2_candidate.payload["choices"]
        )
        assert profile.unclassified_reason_codes == (
            CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES
        )

        variants = profile.response_schema["anyOf"]
        typed_variants = [
            item
            for item in variants
            if item["properties"]["choice"]["enum"] != ["unclassified"]
        ]
        if profile.choice_keys:
            assert len(typed_variants) == 1
            assert typed_variants[0]["properties"]["choice"]["enum"] == list(
                profile.choice_keys
            )
        else:
            zero_choice_cases.add(case.case_id)
            assert typed_variants == []
            assert len(variants) == 1
        assert variants[-1]["properties"]["reason"]["enum"] == list(
            CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES
        )
        assert all(item["additionalProperties"] is False for item in variants)
        serialized = json.dumps(
            profile.response_schema,
            ensure_ascii=False,
            sort_keys=True,
        )
        assert all(
            value not in serialized
            for value in (
                *contract.typed_option_ids,
                "source_value_ref",
                "input_type_id",
                "role_bindings",
                "provenance",
            )
        )

    assert observed_active_hashes == ACTIVE_CHOICE_SCHEMA_HASHES
    assert observed_historical_hashes == (
        HISTORICAL_LOCAL_CHOICE_SCHEMA_HASHES
    )
    assert zero_choice_cases == ZERO_CHOICE_CASE_IDS


def test_context_v2_1_choice_restores_only_through_exact_receipt_rows(
    v6_fixture,
):
    restored_total = 0

    for case in v6_fixture.semantic_cases:
        contract = case.choice_contract
        packet = case.packet
        assert contract is not None
        assert packet is not None
        for row in packet.context_v2_mapping_receipt.choice_restoration:
            normalized = normalize_financial_semantic_v6_context_v2_1_choice(
                model_output={"choice": row["choice_key"]},
                choice_contract=contract,
                packet=packet,
            )
            assert normalized == {
                "disposition": "typed_input",
                "typed_option_id": row["typed_option_id"],
            }
            restored_total += 1

    assert restored_total > 0


def test_context_v2_1_zero_choice_profile_rejects_typed_answer(v6_fixture):
    case = _case(v6_fixture, "syn_successor_v2_multiple_compatible")
    contract = case.choice_contract
    packet = case.packet
    assert contract is not None
    assert packet is not None
    assert contract.context_v2_1_response_profile.choice_keys == ()

    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_context_v2_1_choice_key_unknown",
    ):
        normalize_financial_semantic_v6_context_v2_1_choice(
            model_output={"choice": "choice_1"},
            choice_contract=contract,
            packet=packet,
        )


def test_all_three_reasons_are_preserved_only_by_v2_1_profile(v6_fixture):
    for case in v6_fixture.semantic_cases:
        contract = case.choice_contract
        packet = case.packet
        assert contract is not None
        assert packet is not None
        validator = Draft202012Validator(
            contract.context_v2_1_response_profile.response_schema
        )
        for reason in CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES:
            local = {"choice": "unclassified", "reason": reason}
            validator.validate(local)
            assert normalize_financial_semantic_v6_context_v2_1_choice(
                model_output=json.dumps(local),
                choice_contract=contract,
                packet=packet,
            ) == {
                "disposition": "unclassified_financial_input",
                "reason_code": reason,
            }

    case = _case(v6_fixture, "syn_successor_v2_unique_cash")
    contract = case.choice_contract
    packet = case.packet
    assert contract is not None
    assert packet is not None
    new_reason = "single_registry_type_no_safe_record"
    with pytest.raises(ValidationError):
        Draft202012Validator(contract.choice_schema).validate(
            {
                "disposition": "unclassified_financial_input",
                "reason_code": new_reason,
            }
        )
    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_local_choice_reason_invalid",
    ):
        normalize_financial_semantic_v6_local_choice(
            model_output={"choice": "unclassified", "reason": new_reason},
            choice_contract=contract,
            packet=packet,
        )


@pytest.mark.parametrize(
    ("model_output", "error_code"),
    [
        ({"choice": "choice_999"}, "key_unknown"),
        (
            {"choice": "choice_1", "reason": "no_registry_type"},
            "typed_shape_invalid",
        ),
        ({"choice": "choice_1", "answer": "free text"}, "typed_shape_invalid"),
        ({"choice": "unclassified"}, "unclassified_shape_invalid"),
        (
            {"choice": "unclassified", "reason": "free text"},
            "reason_invalid",
        ),
        ("choice_1", "json_invalid"),
        ('"choice_1"', "invalid"),
    ],
)
def test_context_v2_1_response_rejects_unknown_or_free_text(
    v6_fixture,
    model_output,
    error_code,
):
    case = _case(v6_fixture, "syn_successor_v2_unique_cash")
    assert case.choice_contract is not None
    assert case.packet is not None

    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match=f"financial_semantic_v6_context_v2_1_choice_{error_code}",
    ):
        normalize_financial_semantic_v6_context_v2_1_choice(
            model_output=model_output,
            choice_contract=case.choice_contract,
            packet=case.packet,
        )


def test_context_v2_1_response_rejects_duplicate_and_orphan_choices(
    v6_fixture,
):
    case = _case(v6_fixture, "syn_successor_v2_unique_cash")
    contract = case.choice_contract
    packet = case.packet
    assert contract is not None
    assert packet is not None

    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_context_v2_1_choice_duplicate_key",
    ):
        normalize_financial_semantic_v6_context_v2_1_choice(
            model_output='{"choice":"choice_1","choice":"choice_2"}',
            choice_contract=contract,
            packet=packet,
        )

    orphan_receipt = _reseal_receipt(
        packet.context_v2_mapping_receipt,
        packet.context_v2_mapping_receipt.choice_restoration[:-1],
    )
    orphan_profile = _reseal_profile(
        contract.context_v2_1_response_profile,
        mapping_receipt_integrity_hash=orphan_receipt.integrity_hash,
    )
    orphan_contract = replace(
        contract,
        context_v2_1_response_profile=orphan_profile,
    )
    orphan_packet = replace(
        packet,
        context_v2_mapping_receipt=orphan_receipt,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_context_v2_1_choice_integrity_invalid",
    ):
        normalize_financial_semantic_v6_context_v2_1_choice(
            model_output={"choice": "choice_1"},
            choice_contract=orphan_contract,
            packet=orphan_packet,
        )


def test_context_v2_1_response_rejects_coordinated_option_id_tamper(
    v6_fixture,
):
    case = _case(v6_fixture, "syn_successor_v2_unique_cash")
    contract = case.choice_contract
    packet = case.packet
    assert contract is not None
    assert packet is not None

    forged_option_ids = (
        "forged_option",
        *contract.typed_option_ids[1:],
    )
    forged_choice_schema = _choice_schema(forged_option_ids)
    forged_choice_schema_hash = sha256_json(forged_choice_schema)
    forged_rows = copy.deepcopy(
        list(packet.context_v2_mapping_receipt.choice_restoration)
    )
    forged_rows[0]["typed_option_id"] = forged_option_ids[0]
    forged_receipt = _reseal_receipt(
        packet.context_v2_mapping_receipt,
        forged_rows,
    )
    forged_profile = _reseal_profile(
        contract.context_v2_1_response_profile,
        mapping_receipt_integrity_hash=forged_receipt.integrity_hash,
        canonical_choice_schema_hash=forged_choice_schema_hash,
    )
    forged_contract = replace(
        contract,
        choice_schema=forged_choice_schema,
        choice_schema_hash=forged_choice_schema_hash,
        typed_option_ids=forged_option_ids,
        context_v2_1_response_profile=forged_profile,
    )
    forged_packet = replace(
        packet,
        context_v2_mapping_receipt=forged_receipt,
    )

    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_context_v2_1_choice_integrity_invalid",
    ):
        normalize_financial_semantic_v6_context_v2_1_choice(
            model_output={"choice": "choice_1"},
            choice_contract=forged_contract,
            packet=forged_packet,
        )


def test_context_v2_1_profile_tampering_fails_full_choice_authority(
    v6_fixture,
):
    case = _case(v6_fixture, "syn_successor_v2_unique_cash")
    contract = case.choice_contract
    packet = case.packet
    assert contract is not None
    assert packet is not None
    assert case.evidence_bundle is not None
    assert case.compilation is not None

    tampered_profile = replace(
        contract.context_v2_1_response_profile,
        response_schema_hash="0" * 64,
    )
    tampered_contract = replace(
        contract,
        context_v2_1_response_profile=tampered_profile,
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_choice_contract_integrity_invalid",
    ):
        validate_financial_semantic_v6_choice_contract(
            contract=tampered_contract,
            packet=packet,
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=v6_fixture.registry,
        )

    exact_profile = contract.context_v2_1_response_profile
    reordered_schema = copy.deepcopy(exact_profile.response_schema)
    first_variant = reordered_schema["anyOf"][0]
    reordered_schema["anyOf"][0] = {
        "additionalProperties": first_variant["additionalProperties"],
        "type": first_variant["type"],
        "properties": first_variant["properties"],
        "required": first_variant["required"],
    }
    assert reordered_schema == exact_profile.response_schema
    assert json.dumps(
        reordered_schema,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    ) != json.dumps(
        exact_profile.response_schema,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    )
    reordered_contract = replace(
        contract,
        context_v2_1_response_profile=replace(
            exact_profile,
            response_schema=reordered_schema,
        ),
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ChoiceError,
        match="financial_semantic_v6_choice_contract_integrity_invalid",
    ):
        validate_financial_semantic_v6_choice_contract(
            contract=reordered_contract,
            packet=packet,
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=v6_fixture.registry,
        )
