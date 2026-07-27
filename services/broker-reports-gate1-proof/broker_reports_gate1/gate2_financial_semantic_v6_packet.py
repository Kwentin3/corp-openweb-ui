from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_materialization import (
    Gate2FinancialEvidenceSourcePackage,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v5_projection import (
    Gate2FinancialSemanticV5ProjectionFactory,
)
from .gate2_financial_semantic_v6_bundle import (
    FinancialEvidenceBundleSourceValue,
    Gate2FinancialEvidenceBundle,
)
from .gate2_financial_semantic_v6_candidate_compiler import (
    Gate2FinancialCandidateCompilation,
    Gate2FinancialCandidateCompilerError,
    validate_financial_candidate_compilation,
)


SEMANTIC_PACKET_SCHEMA_VERSION = "broker_reports_gate2_financial_semantic_packet_v6"
SEMANTIC_PACKET_POLICY_VERSION = (
    "broker_reports_gate2_candidate_records_by_construction_v1"
)
SEMANTIC_PACKET_BLOCKS = (
    "task",
    "source_context",
    "available_type_cards",
    "typed_options",
)
SEMANTIC_PACKET_OPERATION = "select_prebound_typed_option_or_unclassified"
SEMANTIC_PACKET_AMBIGUITY_RULE = (
    "Select a typed option only when the visible source uniquely supports "
    "its complete prebound record; otherwise select unclassified."
)
SEMANTIC_PACKET_FORBIDDEN_FIELDS = frozenset(
    {
        "audit",
        "expected_answer",
        "full_administrative_pack",
        "gate3_methodology",
        "internal_audit",
        "managed_asset_ref",
        "model_id",
        "path",
        "prompt_ref",
        "provider_metadata",
        "provenance",
        "provenance_graph",
        "repository_path",
        "semantic_pack_identity",
        "skill_identity",
        "tool_identity",
    }
)

FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6PacketFactory.create is the only V6 "
    "model-facing semantic-packet construction entrypoint"
)
FORBIDDEN = (
    "The packet must contain exactly four model-visible blocks and must not "
    "expose Pack administration, runtime identities, repository paths, "
    "provider metadata, internal audit, provenance graphs, expected answers "
    "or duplicated semantic instructions"
)


class Gate2FinancialSemanticV6PacketError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6Packet:
    schema_version: str
    policy_version: str
    payload: dict[str, Any]
    packet_hash: str
    evidence_bundle_integrity_hash: str
    candidate_compilation_integrity_hash: str
    semantic_projection_hash: str


class Gate2FinancialSemanticV6PacketFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6Packet:
        return self._build(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )

    def _build(
        self,
        *,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6Packet:
        _validate_compilation(
            compilation=compilation,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            registry=self.registry,
        )
        projection = Gate2FinancialSemanticV5ProjectionFactory().create()
        pack_identity = projection.payload["semantic_pack_identity"]
        if pack_identity != {
            "pack_id": compilation.semantic_pack_id,
            "semantic_version": compilation.semantic_pack_version,
            "integrity_sha256": (compilation.semantic_pack_integrity_sha256),
        }:
            _fail("financial_semantic_v6_packet_pack_identity_mismatch")

        cards_by_type = {
            item["input_type_id"]: item for item in projection.payload["type_cards"]
        }
        available_type_ids = tuple(
            sorted({option.input_type_id for option in compilation.typed_options})
        )
        if any(
            input_type_id not in cards_by_type for input_type_id in available_type_ids
        ):
            _fail("financial_semantic_v6_packet_type_card_missing")
        payload = {
            "task": {
                "semantic_operation": SEMANTIC_PACKET_OPERATION,
                "ambiguity_rule": SEMANTIC_PACKET_AMBIGUITY_RULE,
            },
            "source_context": _source_context(evidence_bundle),
            "available_type_cards": [
                copy.deepcopy(cards_by_type[input_type_id])
                for input_type_id in available_type_ids
            ],
            "typed_options": _typed_options(
                evidence_bundle=evidence_bundle,
                compilation=compilation,
            ),
        }
        _validate_payload(
            payload=payload,
            evidence_bundle=evidence_bundle,
            compilation=compilation,
            expected_cards=[
                cards_by_type[input_type_id] for input_type_id in available_type_ids
            ],
        )
        return Gate2FinancialSemanticV6Packet(
            schema_version=SEMANTIC_PACKET_SCHEMA_VERSION,
            policy_version=SEMANTIC_PACKET_POLICY_VERSION,
            payload=copy.deepcopy(payload),
            packet_hash=sha256_json(payload),
            evidence_bundle_integrity_hash=evidence_bundle.integrity_hash,
            candidate_compilation_integrity_hash=(compilation.integrity_hash),
            semantic_projection_hash=projection.projection_hash,
        )


def validate_financial_semantic_v6_packet(
    *,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(packet, Gate2FinancialSemanticV6Packet):
        _fail("financial_semantic_v6_packet_invalid")
    expected = Gate2FinancialSemanticV6PacketFactory(registry=registry)._build(
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
    )
    if packet != expected:
        _fail("financial_semantic_v6_packet_integrity_invalid")


def render_financial_semantic_v6_packet_private_exact(
    *,
    packet: Gate2FinancialSemanticV6Packet,
) -> str:
    _validate_packet_shape(packet)
    return json.dumps(
        packet.payload,
        ensure_ascii=False,
        sort_keys=False,
        indent=2,
        allow_nan=False,
    )


def render_financial_semantic_v6_packet_repository_safe(
    *,
    packet: Gate2FinancialSemanticV6Packet,
) -> str:
    _validate_packet_shape(packet)
    source_context = packet.payload["source_context"]
    value_type_counts = Counter(
        item["value_type"] for item in source_context["source_values"]
    )
    association_kind_counts = Counter(
        item["association_kind"] for item in source_context["associations"]
    )
    safe_payload = {
        "schema_version": packet.schema_version,
        "policy_version": packet.policy_version,
        "packet_hash": packet.packet_hash,
        "model_visible_blocks": {
            "task": copy.deepcopy(packet.payload["task"]),
            "source_context": {
                "source_values_total": len(source_context["source_values"]),
                "associations_total": len(source_context["associations"]),
                "value_type_counts": dict(sorted(value_type_counts.items())),
                "association_kind_counts": dict(
                    sorted(association_kind_counts.items())
                ),
                "column_meanings_present_total": sum(
                    item["visible_context"]["column_meaning"] is not None
                    for item in source_context["source_values"]
                ),
                "visible_labels_present_total": sum(
                    item["visible_context"]["visible_label"] is not None
                    for item in source_context["source_values"]
                ),
            },
            "available_type_cards": [
                {
                    "input_type_id": item["input_type_id"],
                    "required_roles": [
                        role["role_id"] for role in item["required_roles"]
                    ],
                    "optional_roles": [
                        role["role_id"] for role in item["optional_roles"]
                    ],
                }
                for item in packet.payload["available_type_cards"]
            ],
            "typed_options": [
                {
                    "option_id": item["option_id"],
                    "input_type_id": item["input_type_id"],
                    "bound_roles": [
                        binding["role_id"] for binding in item["prebound_role_values"]
                    ],
                }
                for item in packet.payload["typed_options"]
            ],
        },
    }
    return json.dumps(
        safe_payload,
        ensure_ascii=False,
        sort_keys=False,
        indent=2,
        allow_nan=False,
    )


def _source_context(
    evidence_bundle: Gate2FinancialEvidenceBundle,
) -> dict[str, Any]:
    values = [
        {
            "source_value_ref": value.source_value_ref,
            "value_type": value.value_type,
            "source_value": value.literal_value,
            "association_ref": value.association_ref,
            "association_kind": value.association_kind,
            "visible_context": _visible_context(value),
        }
        for value in evidence_bundle.source_values
    ]
    associations = [
        {
            "association_ref": item.association_ref,
            "association_kind": item.association_kind,
            "source_value_refs": list(item.source_value_refs),
            "human_summary": _association_summary(
                association_kind=item.association_kind,
                members_total=len(item.source_value_refs),
            ),
        }
        for item in evidence_bundle.source_associations
    ]
    return {
        "source_values": values,
        "associations": associations,
    }


def _visible_context(
    value: FinancialEvidenceBundleSourceValue,
) -> dict[str, str | None]:
    return {
        "section_role": value.section_role,
        "row_role": value.row_role,
        "column_meaning": value.column_meaning,
        "visible_label": value.visible_label,
    }


def _association_summary(
    *,
    association_kind: str,
    members_total: int,
) -> str:
    readable_kind = association_kind.replace("_", " ")
    noun = "source value" if members_total == 1 else "source values"
    return f"{readable_kind} association linking {members_total} {noun}"


def _typed_options(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
) -> list[dict[str, Any]]:
    values_by_ref = {
        value.source_value_ref: value for value in evidence_bundle.source_values
    }
    result = []
    for option in compilation.typed_options:
        prebound = []
        for binding in option.role_bindings:
            value = values_by_ref[binding.source_value_ref]
            prebound.append(
                {
                    "role_id": binding.role_id,
                    "source_value_ref": value.source_value_ref,
                    "value_type": value.value_type,
                    "source_value": value.literal_value,
                    "visible_context": _visible_context(value),
                    "human_summary": (
                        f"{binding.role_id} is prebound to {value.literal_value}"
                    ),
                }
            )
        result.append(
            {
                "option_id": option.typed_option_id,
                "input_type_id": option.input_type_id,
                "prebound_role_values": prebound,
            }
        )
    return result


def _validate_payload(
    *,
    payload: Any,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    expected_cards: list[dict[str, Any]],
) -> None:
    if not isinstance(payload, dict) or tuple(payload) != (SEMANTIC_PACKET_BLOCKS):
        _fail("financial_semantic_v6_packet_blocks_invalid")
    forbidden = {
        key
        for item in _walk_dicts(payload)
        for key in item
        if key in SEMANTIC_PACKET_FORBIDDEN_FIELDS
    }
    if forbidden:
        _fail("financial_semantic_v6_packet_forbidden_field")
    if payload["task"] != {
        "semantic_operation": SEMANTIC_PACKET_OPERATION,
        "ambiguity_rule": SEMANTIC_PACKET_AMBIGUITY_RULE,
    }:
        _fail("financial_semantic_v6_packet_task_invalid")
    if payload["available_type_cards"] != copy.deepcopy(expected_cards):
        _fail("financial_semantic_v6_packet_type_cards_invalid")

    source_context = payload["source_context"]
    if (
        not isinstance(source_context, dict)
        or set(source_context) != {"source_values", "associations"}
        or source_context != _source_context(evidence_bundle)
    ):
        _fail("financial_semantic_v6_packet_source_context_invalid")
    expected_options = _typed_options(
        evidence_bundle=evidence_bundle,
        compilation=compilation,
    )
    if payload["typed_options"] != expected_options:
        _fail("financial_semantic_v6_packet_options_invalid")
    option_type_ids = {item["input_type_id"] for item in payload["typed_options"]}
    card_type_ids = {item["input_type_id"] for item in payload["available_type_cards"]}
    if option_type_ids != card_type_ids:
        _fail("financial_semantic_v6_packet_option_card_mismatch")

    guidance_fields = {
        "short_meaning",
        "key_semantic_distinctions",
        "examples",
        "counterexamples",
    }
    non_card_blocks = {
        "source_context": payload["source_context"],
        "typed_options": payload["typed_options"],
    }
    if any(guidance_fields.intersection(item) for item in _walk_dicts(non_card_blocks)):
        _fail("financial_semantic_v6_packet_guidance_duplicated")
    ambiguity_rules = [
        item["ambiguity_rule"] for item in payload["available_type_cards"]
    ]
    if SEMANTIC_PACKET_AMBIGUITY_RULE in ambiguity_rules or any(
        SEMANTIC_PACKET_AMBIGUITY_RULE in value for value in ambiguity_rules
    ):
        _fail("financial_semantic_v6_packet_guidance_duplicated")


def _validate_compilation(
    *,
    compilation: Gate2FinancialCandidateCompilation,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    try:
        validate_financial_candidate_compilation(
            compilation=compilation,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            registry=registry,
        )
    except Gate2FinancialCandidateCompilerError as exc:
        raise Gate2FinancialSemanticV6PacketError(
            "financial_semantic_v6_packet_compilation_invalid"
        ) from exc


def _validate_packet_shape(
    packet: Any,
) -> None:
    if (
        not isinstance(packet, Gate2FinancialSemanticV6Packet)
        or packet.schema_version != SEMANTIC_PACKET_SCHEMA_VERSION
        or packet.policy_version != SEMANTIC_PACKET_POLICY_VERSION
        or not isinstance(packet.payload, dict)
        or tuple(packet.payload) != SEMANTIC_PACKET_BLOCKS
        or packet.packet_hash != sha256_json(packet.payload)
    ):
        _fail("financial_semantic_v6_packet_render_input_invalid")
    forbidden = {
        key
        for item in _walk_dicts(packet.payload)
        for key in item
        if key in SEMANTIC_PACKET_FORBIDDEN_FIELDS
    }
    if forbidden:
        _fail("financial_semantic_v6_packet_render_input_invalid")


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6PacketError(code)
