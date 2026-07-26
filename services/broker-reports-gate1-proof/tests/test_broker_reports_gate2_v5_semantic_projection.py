from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_semantic_model_assets import (  # noqa: E402
    PACK_GIT_BLOB_SHA256,
    PACK_INTEGRITY_SHA256,
)
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    V5_FORBIDDEN_TYPE_CARD_FIELDS,
    V5_SEMANTIC_PROJECTION_MAX_BYTES,
    V5_TYPE_CARD_FIELDS,
    Gate2FinancialSemanticV5ProjectionError,
    Gate2FinancialSemanticV5ProjectionFactory,
    validate_financial_semantic_v5_projection,
)


PACK_PATH = (
    ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
PROJECTION_SOURCE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_projection.py"
)


def _portable_bytes(path: Path) -> bytes:
    return (
        path.read_bytes()
        .decode("utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )


def _canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def test_v5_projection_is_exact_deterministic_and_under_limit():
    first = Gate2FinancialSemanticV5ProjectionFactory().create()
    second = Gate2FinancialSemanticV5ProjectionFactory().create()

    assert first == second
    assert first.projection_hash == first.payload["projection_hash"]
    assert first.canonical_bytes == len(_canonical_bytes(first.payload))
    assert first.canonical_bytes < V5_SEMANTIC_PROJECTION_MAX_BYTES
    assert len(first.type_cards) == 2
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not invent or reinterpret" in FORBIDDEN


def test_v5_type_cards_are_traceable_subsets_of_full_pack():
    pack_bytes = _portable_bytes(PACK_PATH)
    pack = json.loads(pack_bytes)
    projection = Gate2FinancialSemanticV5ProjectionFactory().create()
    source_by_id = {
        item["input_type_id"]: item
        for item in pack["full_compact_snapshot"]
    }

    assert hashlib.sha256(pack_bytes).hexdigest() == PACK_GIT_BLOB_SHA256
    assert pack["integrity_sha256"] == PACK_INTEGRITY_SHA256
    assert set(source_by_id) == {
        item["input_type_id"] for item in projection.type_cards
    }
    for card in projection.type_cards:
        source = source_by_id[card["input_type_id"]]
        assert set(card) == V5_TYPE_CARD_FIELDS
        assert not V5_FORBIDDEN_TYPE_CARD_FIELDS.intersection(card)
        assert card["short_meaning"] == source["definition"]
        assert card["required_roles"] == [
            {
                "role_id": item["role_id"],
                "value_type": item["value_type"],
            }
            for item in source["roles"]["required"]
        ]
        assert card["optional_roles"] == [
            {
                "role_id": item["role_id"],
                "value_type": item["value_type"],
            }
            for item in source["roles"]["optional"]
        ]
        assert card["key_semantic_distinctions"] == (
            source["semantic_distinctions"][:2]
        )
        assert card["examples"] == source["examples"][:2]
        assert card["counterexamples"] == source["counterexamples"][:2]
        assert card["ambiguity_rule"] == " ".join(
            source["ambiguity_guidance"]
        )
        assert len(card["examples"]) <= 2
        assert len(card["counterexamples"]) <= 2


def test_v5_projection_exposes_no_administrative_fields():
    projection = Gate2FinancialSemanticV5ProjectionFactory().create()
    serialized = json.dumps(
        projection.payload,
        ensure_ascii=False,
        sort_keys=True,
    )
    for forbidden in (
        "lifecycle",
        "compatibility",
        "persistence",
        "materialization_profile",
        "validation_profile",
        "context_projection_profile",
        "tenant_overlay_policy",
        "gate3_methodology",
        "evidence_refs",
        "test_refs",
        "operational_contracts",
        "managed_asset_ref",
    ):
        assert forbidden not in serialized


def test_v5_projection_tampering_fails_closed():
    projection = Gate2FinancialSemanticV5ProjectionFactory().create()
    tampered = copy.deepcopy(projection.payload)
    tampered["type_cards"][0]["short_meaning"] = "invented"
    with pytest.raises(
        Gate2FinancialSemanticV5ProjectionError,
        match="financial_semantic_v5_projection_authority_mismatch",
    ):
        validate_financial_semantic_v5_projection(tampered)

    rehashed = copy.deepcopy(tampered)
    material = {
        key: value
        for key, value in rehashed.items()
        if key != "projection_hash"
    }
    rehashed["projection_hash"] = hashlib.sha256(
        _canonical_bytes(material)
    ).hexdigest()
    with pytest.raises(
        Gate2FinancialSemanticV5ProjectionError,
        match="financial_semantic_v5_projection_authority_mismatch",
    ):
        validate_financial_semantic_v5_projection(rehashed)


def test_v5_projection_compiler_contains_no_type_specific_semantics():
    source = PROJECTION_SOURCE_PATH.read_text(encoding="utf-8").casefold()
    for forbidden in (
        "cash_balance_snapshot",
        "printed_financial_metric",
        "tax",
        "fee",
        "dividend",
        "commission",
    ):
        assert forbidden not in source
