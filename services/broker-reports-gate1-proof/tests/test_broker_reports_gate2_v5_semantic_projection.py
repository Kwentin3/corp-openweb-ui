from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_model_assets import (  # noqa: E402
    PACK_GIT_BLOB_SHA256,
    PACK_INTEGRITY_SHA256,
)
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    CONTEXT_V2_PACK_PROJECTION_FIELDS,
    CONTEXT_V2_PACK_PROJECTION_IDENTITY,
    CONTEXT_V2_PACK_PROJECTION_VERSION,
    CONTEXT_V2_REASON_PROJECTION_FIELDS,
    CONTEXT_V2_REASON_PROJECTION_IDENTITY,
    CONTEXT_V2_REASON_PROJECTION_VERSION,
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
REASON_CATALOG_PATH = (
    ROOT
    / "managed_assets"
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v1.json"
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


def test_context_v2_projections_are_exact_closed_world_and_non_active():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    factory = Gate2FinancialSemanticV5ProjectionFactory()
    active_before = factory.create()
    candidate = factory.create_context_v2_candidate(
        registry=registry,
        source_family_id="broker_reports_normalized_table_projection_v0",
    )
    active_after = factory.create()
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(REASON_CATALOG_PATH.read_text(encoding="utf-8"))

    assert active_after == active_before
    assert active_before.projection_hash == (
        "6d17d46089b91cfb197dcad12f89635c5879173b6f2175d3810e6dd968361256"
    )
    assert active_before.canonical_bytes == 3591
    assert tuple(active_after.payload) == (
        "schema_version",
        "projection_version",
        "semantic_pack_identity",
        "type_cards",
        "projection_hash",
    )
    assert candidate.managed_asset_family == {
        "family_id": "broker_reports_gate2_financial_domain_assets",
        "manifest_sha256": (
            "4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d"
        ),
        "runtime_activation": False,
        "semantic_version": "1.1.0",
    }
    assert candidate.semantic_pack_identity == {
        "pack_id": pack["pack_id"],
        "semantic_version": pack["semantic_version"],
        "integrity_sha256": pack["integrity_sha256"],
    }
    assert candidate.semantic_pack_source_baseline == {
        "accepted_type_ids": [
            "cash_balance_snapshot_v1",
            "printed_financial_metric_v1",
        ],
        "deferred_candidate_ids": [
            "credit_loss_allowance_movement_v1",
            "credit_loss_allowance_snapshot_v1",
            "equity_balance_snapshot_v1",
            "lease_liability_snapshot_v1",
            "lease_payment_schedule_item_v1",
            "lease_right_of_use_asset_snapshot_v1",
            "payable_balance_snapshot_v1",
            "receivable_balance_snapshot_v1",
            "regulated_asset_balance_snapshot_v1",
            "security_inventory_balance_snapshot_v1",
        ],
        "legacy_python_status": (
            "current_runtime_migration_source_not_target_authority"
        ),
        "registry_sha256": registry.registry_hash,
        "registry_version": registry.registry_version,
    }

    expected_pack_projection = {
        "identity": CONTEXT_V2_PACK_PROJECTION_IDENTITY,
        "version": CONTEXT_V2_PACK_PROJECTION_VERSION,
        "source_family_id": (
            "broker_reports_normalized_table_projection_v0"
        ),
        "type_cards": [
            {
                field: copy.deepcopy(item[field])
                for field in CONTEXT_V2_PACK_PROJECTION_FIELDS
            }
            for item in pack["full_compact_snapshot"]
        ],
    }
    expected_reason_projection = {
        "identity": CONTEXT_V2_REASON_PROJECTION_IDENTITY,
        "version": CONTEXT_V2_REASON_PROJECTION_VERSION,
        "reasons": [
            {
                field: copy.deepcopy(item[field])
                for field in CONTEXT_V2_REASON_PROJECTION_FIELDS
            }
            for item in catalog["reasons"]
        ],
    }
    assert candidate.pack_projection == expected_pack_projection
    assert candidate.reason_projection == expected_reason_projection
    assert candidate.pack_projection_hash == hashlib.sha256(
        _canonical_bytes(expected_pack_projection)
    ).hexdigest()
    assert candidate.reason_projection_hash == hashlib.sha256(
        _canonical_bytes(expected_reason_projection)
    ).hexdigest()
    assert candidate.pack_projection_hash == (
        "08c59bac807e27980c6902d282a0e000f1ceb81d14d761ff0c8c249b4f2f988f"
    )
    assert candidate.reason_projection_hash == (
        "817c1f555b8d97c1547483815b7266efa0777ec272190b87e2bc500e97955071"
    )
    assert candidate.decision_code_view == {
        "identity": "broker_reports_gate2_financial_evidence_decision_v1",
        "unclassified_reason_codes": [
            "ambiguous_registry_type",
            "no_registry_type",
        ],
    }
    assert candidate.decision_code_contract_hash == (
        "e9d7ce23c0c73c1d2907755c1495688dc64d7d3a02135c1fdb16316f184866af"
    )
