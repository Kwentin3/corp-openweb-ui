from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .gate2_financial_semantic_model_assets import (
    PACK_ID,
    PACK_INTEGRITY_SHA256,
    PACK_SEMANTIC_VERSION,
    load_gate2_financial_semantic_model_assets,
)


V5_SEMANTIC_PROJECTION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_projection_v1"
)
V5_SEMANTIC_PROJECTION_VERSION = "1.0.0"
V5_SEMANTIC_PROJECTION_MAX_BYTES = 4096
V5_TYPE_CARD_FIELDS = frozenset(
    {
        "input_type_id",
        "short_meaning",
        "required_roles",
        "optional_roles",
        "key_semantic_distinctions",
        "examples",
        "counterexamples",
        "ambiguity_rule",
    }
)
V5_FORBIDDEN_TYPE_CARD_FIELDS = frozenset(
    {
        "lifecycle",
        "compatibility",
        "compatible_source_families",
        "persistence",
        "materialization_profile",
        "validation_profile",
        "context_projection_profile",
        "integrity_sha256",
        "tenant_overlay_policy",
        "gate3_methodology",
        "evidence_refs",
        "test_refs",
        "operational_contracts",
        "managed_asset_ref",
    }
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5ProjectionFactory.create is the only V5 "
    "model-facing Semantic Pack projection entrypoint"
)
FORBIDDEN = (
    "The projection must not invent or reinterpret type meaning, expose Pack "
    "administration, read runtime files, use network or RAG, or become a "
    "second semantic authority"
)


class Gate2FinancialSemanticV5ProjectionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV5Projection:
    payload: dict[str, Any]
    projection_hash: str
    canonical_bytes: int

    @property
    def type_cards(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(self.payload["type_cards"]))


# OWNER:
# Sole maintained model-facing Semantic Pack projection, shared with V6.
#
# REUSE:
# Call Gate2FinancialSemanticV5ProjectionFactory.create(...).
#
# MUST NOT:
# Do not copy a V6 projection or reinterpret Pack meaning here.
class Gate2FinancialSemanticV5ProjectionFactory:
    def create(self) -> Gate2FinancialSemanticV5Projection:
        assets = load_gate2_financial_semantic_model_assets()
        pack = copy.deepcopy(assets["semantic_pack"])
        _validate_pack_identity(pack)
        material = {
            "schema_version": V5_SEMANTIC_PROJECTION_SCHEMA_VERSION,
            "projection_version": V5_SEMANTIC_PROJECTION_VERSION,
            "semantic_pack_identity": {
                "pack_id": pack["pack_id"],
                "semantic_version": pack["semantic_version"],
                "integrity_sha256": pack["integrity_sha256"],
            },
            "type_cards": [
                _project_type_card(item)
                for item in pack["full_compact_snapshot"]
            ],
        }
        projection_hash = _sha256_json(material)
        payload = {
            **material,
            "projection_hash": projection_hash,
        }
        canonical_bytes = len(_canonical_json(payload))
        validate_financial_semantic_v5_projection(payload)
        return Gate2FinancialSemanticV5Projection(
            payload=copy.deepcopy(payload),
            projection_hash=projection_hash,
            canonical_bytes=canonical_bytes,
        )


def validate_financial_semantic_v5_projection(
    projection: dict[str, Any],
) -> None:
    assets = load_gate2_financial_semantic_model_assets()
    pack = copy.deepcopy(assets["semantic_pack"])
    _validate_pack_identity(pack)
    expected_material = {
        "schema_version": V5_SEMANTIC_PROJECTION_SCHEMA_VERSION,
        "projection_version": V5_SEMANTIC_PROJECTION_VERSION,
        "semantic_pack_identity": {
            "pack_id": pack["pack_id"],
            "semantic_version": pack["semantic_version"],
            "integrity_sha256": pack["integrity_sha256"],
        },
        "type_cards": [
            _project_type_card(item)
            for item in pack["full_compact_snapshot"]
        ],
    }
    if not isinstance(projection, dict) or set(projection) != {
        *expected_material,
        "projection_hash",
    }:
        _fail("financial_semantic_v5_projection_shape_invalid")
    supplied_hash = projection.get("projection_hash")
    if (
        supplied_hash != _sha256_json(expected_material)
        or {
            key: copy.deepcopy(projection[key])
            for key in expected_material
        }
        != expected_material
    ):
        _fail("financial_semantic_v5_projection_authority_mismatch")
    if len(_canonical_json(projection)) >= V5_SEMANTIC_PROJECTION_MAX_BYTES:
        _fail("financial_semantic_v5_projection_size_limit_exceeded")


def _project_type_card(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        _fail("financial_semantic_v5_pack_type_invalid")
    roles = source.get("roles")
    if not isinstance(roles, dict):
        _fail("financial_semantic_v5_pack_roles_invalid")
    required = _project_roles(roles.get("required"))
    optional = _project_roles(roles.get("optional"))
    distinctions = source.get("semantic_distinctions")
    examples = source.get("examples")
    counterexamples = source.get("counterexamples")
    ambiguity = source.get("ambiguity_guidance")
    if (
        not isinstance(source.get("input_type_id"), str)
        or not isinstance(source.get("definition"), str)
        or not isinstance(distinctions, list)
        or not distinctions
        or not isinstance(examples, list)
        or not examples
        or not isinstance(counterexamples, list)
        or not counterexamples
        or not isinstance(ambiguity, list)
        or not ambiguity
        or any(not isinstance(item, str) or not item for item in ambiguity)
    ):
        _fail("financial_semantic_v5_pack_meaning_invalid")
    selected_distinctions = copy.deepcopy(distinctions[:2])
    if any(
        not isinstance(item, dict)
        or set(item) != {"against", "rule"}
        or not isinstance(item["against"], str)
        or not item["against"]
        or not isinstance(item["rule"], str)
        or not item["rule"]
        for item in selected_distinctions
    ):
        _fail("financial_semantic_v5_pack_distinction_invalid")
    selected_examples = copy.deepcopy(examples[:2])
    selected_counterexamples = copy.deepcopy(counterexamples[:2])
    if any(
        not isinstance(item, str) or not item
        for item in [*selected_examples, *selected_counterexamples]
    ):
        _fail("financial_semantic_v5_pack_example_invalid")
    card = {
        "input_type_id": source["input_type_id"],
        "short_meaning": source["definition"],
        "required_roles": required,
        "optional_roles": optional,
        "key_semantic_distinctions": selected_distinctions,
        "examples": selected_examples,
        "counterexamples": selected_counterexamples,
        "ambiguity_rule": " ".join(ambiguity),
    }
    if (
        set(card) != V5_TYPE_CARD_FIELDS
        or V5_FORBIDDEN_TYPE_CARD_FIELDS.intersection(card)
    ):
        _fail("financial_semantic_v5_type_card_shape_invalid")
    return card


def _project_roles(source: Any) -> list[dict[str, str]]:
    if not isinstance(source, list):
        _fail("financial_semantic_v5_pack_roles_invalid")
    result = []
    for item in source:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("role_id"), str)
            or not item["role_id"]
            or not isinstance(item.get("value_type"), str)
            or not item["value_type"]
        ):
            _fail("financial_semantic_v5_pack_role_invalid")
        result.append(
            {
                "role_id": item["role_id"],
                "value_type": item["value_type"],
            }
        )
    if not result or len(result) != len(
        {item["role_id"] for item in result}
    ):
        _fail("financial_semantic_v5_pack_roles_invalid")
    return result


def _validate_pack_identity(pack: Any) -> None:
    if (
        not isinstance(pack, dict)
        or pack.get("pack_id") != PACK_ID
        or pack.get("semantic_version") != PACK_SEMANTIC_VERSION
        or pack.get("integrity_sha256") != PACK_INTEGRITY_SHA256
        or not isinstance(pack.get("full_compact_snapshot"), list)
        or not pack["full_compact_snapshot"]
    ):
        _fail("financial_semantic_v5_pack_identity_invalid")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5ProjectionError(code)
