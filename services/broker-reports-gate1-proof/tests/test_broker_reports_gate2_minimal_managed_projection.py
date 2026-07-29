from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import (  # noqa: E402
    gate2_financial_semantic_v5_projection as projection_module,
)
from broker_reports_gate1.gate2_financial_semantic_model_assets import (  # noqa: E402,E501
    CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256,
    MINIMAL_MANAGED_ASSET_FAMILY_VERSION,
    MINIMAL_MANAGED_PROJECTION_PROFILE_ID,
    MINIMAL_MANAGED_PROJECTION_PROFILE_VERSION,
    load_gate2_financial_semantic_model_assets,
)
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    MINIMAL_MANAGED_PROJECTION_MAX_BYTES,
    MINIMAL_MANAGED_REASON_CARD_FIELDS,
    MINIMAL_MANAGED_TYPE_CARD_FIELDS,
    Gate2FinancialSemanticV5ProjectionError,
    Gate2FinancialSemanticV5ProjectionFactory,
    validate_financial_semantic_minimal_managed_projection,
)


PACK_PATH = (
    ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
CATALOG_V2_PATH = (
    ROOT
    / "managed_assets"
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
)
MANIFEST_V3_PATH = (
    ROOT
    / "managed_assets"
    / "broker_reports_financial_domain_assets.v3.manifest.json"
)
PROJECTION_SOURCE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_projection.py"
)
RUNTIME_SOURCE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_model_assets.py"
)
MINIMAL_SURFACE_CONTRACT_PATH = (
    ROOT.parents[1]
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md"
)

EXPECTED_ACTIVE_ASSET_PAYLOAD_SHA256 = (
    "b80eed8b9a41fa039a9a8d961c972817ae840ce81d7c163de624b7d5a4ec123b"
)
EXPECTED_ACTIVE_PROJECTION_SHA256 = (
    "6d17d46089b91cfb197dcad12f89635c5879173b6f2175d3810e6dd968361256"
)
EXPECTED_MINIMAL_PROJECTION_SHA256 = (
    "fae235725094d45d82dfe0eee3fefd4268cf1cd6a2c0aa8a5a7392a4b75acca5"
)
EXPECTED_MINIMAL_AUDIT_SHA256 = (
    "fc3379890c73628c891f8b48fef25874f8bfb8551d93bcd682e78b6e9f374657"
)


def _canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_json(value) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _first_sentence(value: str) -> str:
    for index, character in enumerate(value):
        if character == "." and (
            index + 1 == len(value) or value[index + 1] == " "
        ):
            return value[: index + 1]
    raise AssertionError("fixture meaning lacks the contracted boundary")


def _profile_assets() -> dict:
    return load_gate2_financial_semantic_model_assets(
        profile="minimal_model_surface_v1_candidate"
    )


def _patch_pack_integrity(
    monkeypatch: pytest.MonkeyPatch,
    assets: dict,
) -> None:
    material = copy.deepcopy(assets["semantic_pack"])
    material.pop("integrity_sha256", None)
    canonical = _canonical_bytes(material)
    integrity = hashlib.sha256(canonical).hexdigest()
    assets["semantic_pack"]["integrity_sha256"] = integrity
    monkeypatch.setattr(
        projection_module,
        "PACK_INTEGRITY_SHA256",
        integrity,
    )
    monkeypatch.setattr(
        projection_module,
        "PACK_CANONICAL_SEMANTIC_BYTES",
        len(canonical),
    )


def _patch_catalog_integrity(
    monkeypatch: pytest.MonkeyPatch,
    assets: dict,
) -> None:
    material = copy.deepcopy(assets["decision_reason_catalog"])
    material.pop("integrity_sha256", None)
    canonical = _canonical_bytes(material)
    integrity = hashlib.sha256(canonical).hexdigest()
    assets["decision_reason_catalog"]["integrity_sha256"] = integrity
    monkeypatch.setattr(
        projection_module,
        "MINIMAL_MANAGED_DECISION_REASON_CATALOG_INTEGRITY_SHA256",
        integrity,
    )
    monkeypatch.setattr(
        projection_module,
        "MINIMAL_MANAGED_DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES",
        len(canonical),
    )


def _patch_loader(
    monkeypatch: pytest.MonkeyPatch,
    assets: dict,
) -> None:
    monkeypatch.setattr(
        projection_module,
        "load_gate2_financial_semantic_model_assets",
        lambda *, profile="active": copy.deepcopy(assets),
    )


def test_minimal_projection_is_exact_deterministic_and_model_only() -> None:
    factory = Gate2FinancialSemanticV5ProjectionFactory()
    active_before = factory.create()
    first = factory.create_minimal_managed_projection()
    second = factory.create_minimal_managed_projection()
    active_after = factory.create()
    active_assets = load_gate2_financial_semantic_model_assets()

    assert first == second
    assert active_after == active_before
    assert active_before.projection_hash == EXPECTED_ACTIVE_PROJECTION_SHA256
    assert active_before.canonical_bytes == 3591
    assert _sha256_json(active_assets) == EXPECTED_ACTIVE_ASSET_PAYLOAD_SHA256
    assert CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256 == (
        "99be5272ebab4e69e2533391f381bd27682496148f760e1e4a171f9e7162cdad"
    )
    assert first.profile_id == MINIMAL_MANAGED_PROJECTION_PROFILE_ID
    assert first.semantic_version == MINIMAL_MANAGED_PROJECTION_PROFILE_VERSION
    assert first.runtime_activation is False
    assert first.projection_hash == EXPECTED_MINIMAL_PROJECTION_SHA256
    assert first.authority_audit_hash == EXPECTED_MINIMAL_AUDIT_SHA256
    assert first.canonical_bytes == 2102
    assert first.canonical_bytes < MINIMAL_MANAGED_PROJECTION_MAX_BYTES
    assert tuple(first.payload) == (
        "type_cards",
        "unclassified_reasons",
    )
    assert len(first.type_cards) == 2
    assert len(first.reason_cards) == 3

    serialized = json.dumps(
        first.payload,
        ensure_ascii=False,
        sort_keys=True,
    )
    for forbidden in (
        '"input_type_id"',
        '"semantic_version"',
        '"integrity_sha256"',
        '"profile_id"',
        '"roles"',
        '"synonyms"',
        '"examples"',
        '"counterexamples"',
        '"meaning"',
        '"selection_boundary"',
        '"contrast_with_neighbouring_reasons"',
    ):
        assert forbidden not in serialized


def test_minimal_projection_maps_exact_full_pack_and_catalog_v2() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_V2_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_V3_PATH.read_text(encoding="utf-8"))
    assets = _profile_assets()
    projection = (
        Gate2FinancialSemanticV5ProjectionFactory()
        .create_minimal_managed_projection()
    )

    assert assets["semantic_pack"] == pack
    assert assets["decision_reason_catalog"] == catalog
    assert assets["managed_asset_family"] == {
        "family_id": manifest["family_id"],
        "semantic_version": MINIMAL_MANAGED_ASSET_FAMILY_VERSION,
        "manifest_sha256": manifest["manifest_sha256"],
        "runtime_activation": False,
    }
    assert assets["projection_profile"] == manifest["composition"][
        "minimal_projection_profile"
    ]
    assert assets["projection_profile"]["response_profile_status"] == (
        "not_implemented"
    )
    assert assets["projection_profile"]["transport_eligible"] is False

    pack_items = pack["full_compact_snapshot"]
    for index, (card, audit_card, source) in enumerate(
        zip(
            projection.type_cards,
            projection.authority_audit["type_cards"],
            pack_items,
            strict=True,
        ),
        start=1,
    ):
        competitor_index = 1 if index == 1 else 0
        competitor = pack_items[competitor_index]
        distinctions = [
            item
            for item in source["semantic_distinctions"]
            if item["against"] == competitor["input_type_id"]
        ]
        assert tuple(card) == MINIMAL_MANAGED_TYPE_CARD_FIELDS
        assert card == {
            "type_key": f"type_{index}",
            "title": source["title"],
            "definition": source["definition"],
            "positive_signal": source["examples"][0],
            "negative_signal": source["counterexamples"][0],
            "nearest_competitor": {
                "type_key": f"type_{competitor_index + 1}",
                "distinction": distinctions[0]["rule"],
            },
        }
        assert audit_card["input_type_id"] == source["input_type_id"]
        assert audit_card["nearest_competitor"]["input_type_id"] == (
            competitor["input_type_id"]
        )

    assert list(projection.reason_cards) == [
        {
            "code": item["code"],
            "title": item["human_title"],
            "use_when": _first_sentence(item["meaning"]),
        }
        for item in catalog["reasons"]
    ]
    assert all(
        tuple(item) == MINIMAL_MANAGED_REASON_CARD_FIELDS
        for item in projection.reason_cards
    )


def test_minimal_reason_cards_match_governing_contract_rows() -> None:
    projection = (
        Gate2FinancialSemanticV5ProjectionFactory()
        .create_minimal_managed_projection()
    )
    contract = MINIMAL_SURFACE_CONTRACT_PATH.read_text(encoding="utf-8")

    for card in projection.reason_cards:
        assert (
            f"| `{card['code']}` | `{card['use_when']}` |"
            in contract
        )
    assert (
        "one plausible type but no safe record” outcome remains"
        not in contract
    )


def test_managed_wording_is_not_copied_into_python_sources() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_V2_PATH.read_text(encoding="utf-8"))
    python_sources = (
        PROJECTION_SOURCE_PATH.read_text(encoding="utf-8")
        + "\n"
        + RUNTIME_SOURCE_PATH.read_text(encoding="utf-8")
    )
    managed_wording = [
        value
        for item in pack["full_compact_snapshot"]
        for value in (
            item["title"],
            item["definition"],
            item["examples"][0],
            item["counterexamples"][0],
            *[
                distinction["rule"]
                for distinction in item["semantic_distinctions"]
            ],
        )
    ]
    managed_wording.extend(
        value
        for item in catalog["reasons"]
        for value in (
            item["human_title"],
            item["meaning"],
        )
    )

    assert all(value not in python_sources for value in managed_wording)


def test_tamper_and_self_rehash_fail_authority_reconstruction() -> None:
    projection = (
        Gate2FinancialSemanticV5ProjectionFactory()
        .create_minimal_managed_projection()
    )
    tampered = copy.deepcopy(projection.payload)
    tampered["type_cards"][0]["definition"] = "invented"

    with pytest.raises(
        Gate2FinancialSemanticV5ProjectionError,
        match="financial_semantic_minimal_managed_authority_mismatch",
    ):
        validate_financial_semantic_minimal_managed_projection(
            payload=tampered,
            projection_hash=_sha256_json(tampered),
        )


@pytest.mark.parametrize("visible_type_count", [1, 3])
def test_minimal_projection_rejects_non_two_type_pack(
    monkeypatch: pytest.MonkeyPatch,
    visible_type_count: int,
) -> None:
    assets = _profile_assets()
    if visible_type_count == 1:
        assets["semantic_pack"]["full_compact_snapshot"].pop()
    else:
        extra = copy.deepcopy(
            assets["semantic_pack"]["full_compact_snapshot"][0]
        )
        extra["input_type_id"] = "synthetic_extra_type_v1"
        assets["semantic_pack"]["full_compact_snapshot"].append(extra)
    _patch_pack_integrity(monkeypatch, assets)
    _patch_loader(monkeypatch, assets)

    with pytest.raises(
        Gate2FinancialSemanticV5ProjectionError,
        match="financial_semantic_minimal_managed_pack_invalid",
    ):
        (
            Gate2FinancialSemanticV5ProjectionFactory()
            .create_minimal_managed_projection()
        )


@pytest.mark.parametrize("field", ["examples", "counterexamples"])
def test_minimal_projection_rejects_missing_primary_signal(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    assets = _profile_assets()
    assets["semantic_pack"]["full_compact_snapshot"][0][field] = []
    _patch_pack_integrity(monkeypatch, assets)
    _patch_loader(monkeypatch, assets)

    with pytest.raises(
        Gate2FinancialSemanticV5ProjectionError,
        match="financial_semantic_minimal_managed_type_meaning_invalid",
    ):
        (
            Gate2FinancialSemanticV5ProjectionFactory()
            .create_minimal_managed_projection()
        )


@pytest.mark.parametrize("duplicate", [False, True])
def test_minimal_projection_rejects_missing_or_duplicate_direct_rule(
    monkeypatch: pytest.MonkeyPatch,
    duplicate: bool,
) -> None:
    assets = _profile_assets()
    first, second = assets["semantic_pack"]["full_compact_snapshot"]
    matches = [
        item
        for item in first["semantic_distinctions"]
        if item["against"] == second["input_type_id"]
    ]
    if duplicate:
        first["semantic_distinctions"].append(copy.deepcopy(matches[0]))
    else:
        first["semantic_distinctions"] = [
            item
            for item in first["semantic_distinctions"]
            if item["against"] != second["input_type_id"]
        ]
    _patch_pack_integrity(monkeypatch, assets)
    _patch_loader(monkeypatch, assets)

    with pytest.raises(
        Gate2FinancialSemanticV5ProjectionError,
        match="financial_semantic_minimal_managed_distinction_invalid",
    ):
        (
            Gate2FinancialSemanticV5ProjectionFactory()
            .create_minimal_managed_projection()
        )


def test_minimal_projection_rejects_unclosed_reason_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets = _profile_assets()
    assets["decision_reason_catalog"]["reasons"][0]["meaning"] = (
        "A managed sentence without the contracted full stop boundary"
    )
    _patch_catalog_integrity(monkeypatch, assets)
    _patch_loader(monkeypatch, assets)

    with pytest.raises(
        Gate2FinancialSemanticV5ProjectionError,
        match="financial_semantic_minimal_managed_sentence_invalid",
    ):
        (
            Gate2FinancialSemanticV5ProjectionFactory()
            .create_minimal_managed_projection()
        )
