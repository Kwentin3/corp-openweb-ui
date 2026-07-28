from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_decision import (
    DECISION_SCHEMA_VERSION,
    UNCLASSIFIED_REASON_CODES,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_contract import (
    Gate2FinancialSemanticContractError,
    Gate2FinancialSemanticContractFactory,
)
from .gate2_financial_semantic_model_assets import (
    CONTEXT_V2_MODEL_ASSET_SCHEMA_VERSION,
    DECISION_REASON_CATALOG_ID,
    DECISION_REASON_CATALOG_INTEGRITY_SHA256,
    DECISION_REASON_CATALOG_VERSION,
    MANAGED_ASSET_FAMILY_ID,
    MANAGED_ASSET_FAMILY_MANIFEST_SHA256,
    MANAGED_ASSET_FAMILY_VERSION,
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
CONTEXT_V2_PACK_PROJECTION_IDENTITY = (
    "broker_reports_gate2_financial_semantic_projection_v2_candidate"
)
CONTEXT_V2_PACK_PROJECTION_VERSION = "2.0.0"
CONTEXT_V2_REASON_PROJECTION_IDENTITY = (
    "broker_reports_gate2_financial_decision_reason_projection_v1_candidate"
)
CONTEXT_V2_REASON_PROJECTION_VERSION = "1.0.0"
CONTEXT_V2_PACK_PROJECTION_FIELDS = (
    "input_type_id",
    "title",
    "definition",
    "semantic_class",
    "roles",
    "date_period_requirement",
    "currency_unit_requirement",
    "synonyms",
    "semantic_distinctions",
    "examples",
    "counterexamples",
    "ambiguity_guidance",
    "model_guidance",
    "compatible_source_families",
)
CONTEXT_V2_REASON_PROJECTION_FIELDS = (
    "code",
    "display_order",
    "human_title",
    "meaning",
    "use_when",
    "do_not_use_when",
    "contrast_with_neighbouring_reasons",
)
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


@dataclass(frozen=True)
class Gate2FinancialSemanticV2CandidateProjection:
    managed_asset_family: dict[str, Any]
    semantic_pack_identity: dict[str, str]
    semantic_pack_source_baseline: dict[str, Any]
    pack_projection: dict[str, Any]
    pack_projection_hash: str
    reason_catalog_identity: dict[str, str]
    reason_projection: dict[str, Any]
    reason_projection_hash: str
    decision_code_view: dict[str, Any]
    decision_code_contract_hash: str

    @property
    def type_cards(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(self.pack_projection["type_cards"]))

    @property
    def reason_cards(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(self.reason_projection["reasons"]))


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

    def create_context_v2_candidate(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        source_family_id: str,
    ) -> Gate2FinancialSemanticV2CandidateProjection:
        return _ContextV2CandidateProjectionRenderer(
            registry=registry
        ).render(source_family_id=source_family_id)


class _ContextV2CandidateProjectionRenderer:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def render(
        self,
        *,
        source_family_id: str,
    ) -> Gate2FinancialSemanticV2CandidateProjection:
        if not isinstance(source_family_id, str) or not source_family_id:
            _fail("financial_semantic_context_v2_source_family_invalid")
        try:
            semantic_contract = Gate2FinancialSemanticContractFactory(
                registry=self.registry
            ).create()
        except Gate2FinancialSemanticContractError as exc:
            raise Gate2FinancialSemanticV5ProjectionError(
                "financial_semantic_context_v2_pack_registry_invalid"
            ) from exc
        assets = load_gate2_financial_semantic_model_assets(
            profile="context_v2_candidate",
        )
        if (
            not isinstance(assets, dict)
            or assets.get("schema_version")
            != CONTEXT_V2_MODEL_ASSET_SCHEMA_VERSION
        ):
            _fail("financial_semantic_context_v2_assets_invalid")
        family = copy.deepcopy(assets.get("managed_asset_family"))
        pack = copy.deepcopy(assets.get("semantic_pack"))
        catalog = copy.deepcopy(assets.get("decision_reason_catalog"))
        if family != {
            "family_id": MANAGED_ASSET_FAMILY_ID,
            "manifest_sha256": MANAGED_ASSET_FAMILY_MANIFEST_SHA256,
            "runtime_activation": False,
            "semantic_version": MANAGED_ASSET_FAMILY_VERSION,
        }:
            _fail("financial_semantic_context_v2_family_invalid")
        if (
            not isinstance(pack, dict)
            or pack.get("pack_id") != PACK_ID
            or pack.get("semantic_version") != PACK_SEMANTIC_VERSION
            or pack.get("integrity_sha256") != PACK_INTEGRITY_SHA256
            or semantic_contract.identity_payload()
            != {
                "pack_id": PACK_ID,
                "semantic_version": PACK_SEMANTIC_VERSION,
                "integrity_sha256": PACK_INTEGRITY_SHA256,
            }
        ):
            _fail("financial_semantic_context_v2_pack_invalid")
        baseline = copy.deepcopy(pack.get("source_baseline"))
        if (
            not isinstance(baseline, dict)
            or baseline.get("registry_version")
            != self.registry.registry_version
            or baseline.get("registry_sha256")
            != self.registry.registry_hash
            or baseline.get("accepted_type_ids")
            != [
                item.input_type_id
                for item in semantic_contract.type_contracts
            ]
        ):
            _fail(
                "financial_semantic_context_v2_pack_registry_baseline_mismatch"
            )
        pack_items = pack.get("full_compact_snapshot")
        if not isinstance(pack_items, list) or not pack_items:
            _fail("financial_semantic_context_v2_pack_types_invalid")
        pack_by_id = {
            item.get("input_type_id"): item
            for item in pack_items
            if isinstance(item, dict)
        }
        if (
            len(pack_by_id) != len(pack_items)
            or None in pack_by_id
            or set(pack_by_id)
            != {
                item.input_type_id
                for item in semantic_contract.type_contracts
            }
        ):
            _fail("financial_semantic_context_v2_pack_types_invalid")
        available_type_ids = tuple(
            declaration.input_type_id
            for declaration in self.registry.declarations
            if declaration.lifecycle == "active"
            and source_family_id
            in declaration.compatible_source_families
        )
        selected_cards = []
        for input_type_id in available_type_ids:
            source = pack_by_id.get(input_type_id)
            if (
                not isinstance(source, dict)
                or source_family_id
                not in source.get("compatible_source_families", ())
            ):
                _fail(
                    "financial_semantic_context_v2_source_family_parity_invalid"
                )
            selected_cards.append(_project_v2_type_card(source))
        pack_projection = {
            "identity": CONTEXT_V2_PACK_PROJECTION_IDENTITY,
            "version": CONTEXT_V2_PACK_PROJECTION_VERSION,
            "source_family_id": source_family_id,
            "type_cards": selected_cards,
        }
        reason_projection = _project_v2_reason_catalog(catalog)
        decision_code_view = {
            "identity": DECISION_SCHEMA_VERSION,
            "unclassified_reason_codes": list(
                UNCLASSIFIED_REASON_CODES
            ),
        }
        reason_catalog_identity = {
            "catalog_id": DECISION_REASON_CATALOG_ID,
            "semantic_version": DECISION_REASON_CATALOG_VERSION,
            "integrity_sha256": (
                DECISION_REASON_CATALOG_INTEGRITY_SHA256
            ),
        }
        result = Gate2FinancialSemanticV2CandidateProjection(
            managed_asset_family=copy.deepcopy(family),
            semantic_pack_identity={
                "pack_id": PACK_ID,
                "semantic_version": PACK_SEMANTIC_VERSION,
                "integrity_sha256": PACK_INTEGRITY_SHA256,
            },
            semantic_pack_source_baseline=copy.deepcopy(baseline),
            pack_projection=copy.deepcopy(pack_projection),
            pack_projection_hash=_sha256_json(pack_projection),
            reason_catalog_identity=reason_catalog_identity,
            reason_projection=copy.deepcopy(reason_projection),
            reason_projection_hash=_sha256_json(reason_projection),
            decision_code_view=copy.deepcopy(decision_code_view),
            decision_code_contract_hash=_sha256_json(
                decision_code_view
            ),
        )
        _validate_v2_projection_result(
            result,
            available_type_ids=available_type_ids,
        )
        return result


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


def _project_v2_type_card(source: Any) -> dict[str, Any]:
    if (
        not isinstance(source, dict)
        or any(field not in source for field in CONTEXT_V2_PACK_PROJECTION_FIELDS)
    ):
        _fail("financial_semantic_context_v2_pack_type_invalid")
    roles = source["roles"]
    if (
        not isinstance(roles, dict)
        or set(roles) != {"required", "optional", "forbidden"}
        or not isinstance(roles["required"], list)
        or not roles["required"]
        or not isinstance(roles["optional"], list)
        or not isinstance(roles["forbidden"], list)
    ):
        _fail("financial_semantic_context_v2_pack_roles_invalid")
    for role in [*roles["required"], *roles["optional"]]:
        if (
            not isinstance(role, dict)
            or tuple(role)
            != (
                "role_id",
                "value_type",
                "cardinality",
                "source_ref_required",
            )
            or not isinstance(role["role_id"], str)
            or not role["role_id"]
            or not isinstance(role["value_type"], str)
            or not role["value_type"]
            or not isinstance(role["cardinality"], str)
            or not role["cardinality"]
            or not isinstance(role["source_ref_required"], bool)
        ):
            _fail("financial_semantic_context_v2_pack_role_invalid")
    if any(
        not isinstance(role, str) or not role
        for role in roles["forbidden"]
    ):
        _fail("financial_semantic_context_v2_pack_role_invalid")
    required_text = (
        "input_type_id",
        "title",
        "definition",
        "semantic_class",
        "date_period_requirement",
        "currency_unit_requirement",
        "model_guidance",
    )
    required_arrays = (
        "synonyms",
        "semantic_distinctions",
        "examples",
        "counterexamples",
        "ambiguity_guidance",
        "compatible_source_families",
    )
    if any(
        not isinstance(source[field], str) or not source[field]
        for field in required_text
    ) or any(
        not isinstance(source[field], list) or not source[field]
        for field in required_arrays
    ):
        _fail("financial_semantic_context_v2_pack_meaning_invalid")
    if any(
        not isinstance(item, str) or not item
        for field in (
            "synonyms",
            "examples",
            "counterexamples",
            "ambiguity_guidance",
            "compatible_source_families",
        )
        for item in source[field]
    ):
        _fail("financial_semantic_context_v2_pack_meaning_invalid")
    for distinction in source["semantic_distinctions"]:
        if (
            not isinstance(distinction, dict)
            or tuple(distinction) != ("against", "rule")
            or not isinstance(distinction["against"], str)
            or not distinction["against"]
            or not isinstance(distinction["rule"], str)
            or not distinction["rule"]
        ):
            _fail("financial_semantic_context_v2_pack_distinction_invalid")
    return {
        field: copy.deepcopy(source[field])
        for field in CONTEXT_V2_PACK_PROJECTION_FIELDS
    }


def _project_v2_reason_catalog(catalog: Any) -> dict[str, Any]:
    if (
        not isinstance(catalog, dict)
        or catalog.get("catalog_id") != DECISION_REASON_CATALOG_ID
        or catalog.get("semantic_version")
        != DECISION_REASON_CATALOG_VERSION
        or catalog.get("integrity_sha256")
        != DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or catalog.get("code_contract_version") != DECISION_SCHEMA_VERSION
        or catalog.get("runtime_activation") is not False
        or not isinstance(catalog.get("reasons"), list)
        or not catalog["reasons"]
    ):
        _fail("financial_semantic_context_v2_reason_catalog_invalid")
    reasons = []
    for item in catalog["reasons"]:
        if (
            not isinstance(item, dict)
            or any(
                field not in item
                for field in CONTEXT_V2_REASON_PROJECTION_FIELDS
            )
        ):
            _fail("financial_semantic_context_v2_reason_invalid")
        reason = {
            field: copy.deepcopy(item[field])
            for field in CONTEXT_V2_REASON_PROJECTION_FIELDS
        }
        contrasts = reason["contrast_with_neighbouring_reasons"]
        if (
            not isinstance(reason["code"], str)
            or not reason["code"]
            or not isinstance(reason["display_order"], int)
            or isinstance(reason["display_order"], bool)
            or reason["display_order"] < 1
            or any(
                not isinstance(reason[field], str) or not reason[field]
                for field in (
                    "human_title",
                    "meaning",
                    "use_when",
                    "do_not_use_when",
                )
            )
            or not isinstance(contrasts, list)
            or not contrasts
            or any(
                not isinstance(contrast, dict)
                or set(contrast) != {"reason_code", "distinction"}
                or not isinstance(contrast["reason_code"], str)
                or not contrast["reason_code"]
                or not isinstance(contrast["distinction"], str)
                or not contrast["distinction"]
                for contrast in contrasts
            )
        ):
            _fail("financial_semantic_context_v2_reason_invalid")
        reason["contrast_with_neighbouring_reasons"] = [
            {
                "reason_code": contrast["reason_code"],
                "distinction": contrast["distinction"],
            }
            for contrast in contrasts
        ]
        reasons.append(reason)
    reason_codes = [item["code"] for item in reasons]
    if (
        len(reason_codes) != len(set(reason_codes))
        or set(reason_codes) != set(UNCLASSIFIED_REASON_CODES)
        or [item["display_order"] for item in reasons]
        != list(range(1, len(reasons) + 1))
        or any(
            {
                item["reason_code"] for item in reason["contrast_with_neighbouring_reasons"]
            }
            != set(reason_codes) - {reason["code"]}
            for reason in reasons
        )
    ):
        _fail("financial_semantic_context_v2_reason_parity_invalid")
    return {
        "identity": CONTEXT_V2_REASON_PROJECTION_IDENTITY,
        "version": CONTEXT_V2_REASON_PROJECTION_VERSION,
        "reasons": reasons,
    }


def _validate_v2_projection_result(
    projection: Gate2FinancialSemanticV2CandidateProjection,
    *,
    available_type_ids: tuple[str, ...],
) -> None:
    if (
        tuple(projection.pack_projection)
        != ("identity", "version", "source_family_id", "type_cards")
        or projection.pack_projection["identity"]
        != CONTEXT_V2_PACK_PROJECTION_IDENTITY
        or projection.pack_projection["version"]
        != CONTEXT_V2_PACK_PROJECTION_VERSION
        or [
            item["input_type_id"]
            for item in projection.pack_projection["type_cards"]
        ]
        != list(available_type_ids)
        or projection.pack_projection_hash
        != _sha256_json(projection.pack_projection)
        or tuple(projection.reason_projection)
        != ("identity", "version", "reasons")
        or projection.reason_projection["identity"]
        != CONTEXT_V2_REASON_PROJECTION_IDENTITY
        or projection.reason_projection["version"]
        != CONTEXT_V2_REASON_PROJECTION_VERSION
        or projection.reason_projection_hash
        != _sha256_json(projection.reason_projection)
        or projection.decision_code_view
        != {
            "identity": DECISION_SCHEMA_VERSION,
            "unclassified_reason_codes": list(
                UNCLASSIFIED_REASON_CODES
            ),
        }
        or projection.decision_code_contract_hash
        != _sha256_json(projection.decision_code_view)
        or _contains_none(projection.pack_projection)
        or _contains_none(projection.reason_projection)
    ):
        _fail("financial_semantic_context_v2_projection_invalid")


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


def _contains_none(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            item is None or _contains_none(item)
            for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(
            item is None or _contains_none(item)
            for item in value
        )
    return False


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5ProjectionError(code)
