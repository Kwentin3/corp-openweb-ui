from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .gate2_financial_evidence_materialization import (
    Gate2FinancialEvidenceSourcePackage,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v5_projection import (
    CONTEXT_V2_PACK_PROJECTION_IDENTITY,
    CONTEXT_V2_PACK_PROJECTION_VERSION,
    CONTEXT_V2_REASON_PROJECTION_IDENTITY,
    CONTEXT_V2_REASON_PROJECTION_VERSION,
    Gate2FinancialSemanticV2CandidateProjection,
    Gate2FinancialSemanticV5ProjectionFactory,
    Gate2FinancialSemanticV5ProjectionError,
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
SLIM_VIEW_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_slim_view_candidate_v2"
)
SLIM_VIEW_POLICY_VERSION = (
    "broker_reports_gate2_llm_semantic_context_local_choice_v1"
)
SLIM_ALIAS_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_slim_alias_receipt_v2"
)
LLM_SEMANTIC_CONTEXT_CONTRACT_IDENTITY = (
    "broker_reports_gate2_llm_semantic_context_v1"
)
SLIM_VIEW_BLOCKS = (
    "task",
    "source",
    "type_cards",
    "choices",
    "unclassified",
)
SLIM_VIEW_UNCLASSIFIED_REASONS = (
    "ambiguous_registry_type",
    "no_registry_type",
)
SEMANTIC_PACKET_TYPE_CARD_FIELDS = (
    "input_type_id",
    "short_meaning",
    "required_roles",
    "optional_roles",
    "key_semantic_distinctions",
    "ambiguity_rule",
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
    "model-facing semantic-packet, non-active Slim candidate and "
    "non-active Context V2 sidecar construction entrypoint"
)
FORBIDDEN = (
    "The active packet must contain exactly four model-visible blocks; a "
    "non-active Slim or Context V2 candidate must stay inside the same "
    "factory and must not activate a request route, expose source or type "
    "global IDs, Pack administration, repository paths, provider metadata, "
    "internal audit, provenance graphs, expected answers or duplicated "
    "semantic instructions"
)


class Gate2FinancialSemanticV6PacketError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6SlimViewCandidate:
    schema_version: str
    policy_version: str
    active: bool
    payload: dict[str, Any]
    view_hash: str
    model_visible_utf8_bytes: int
    provider_calls_total: int

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "active": self.active,
            "view_hash": self.view_hash,
            "model_visible_utf8_bytes": self.model_visible_utf8_bytes,
            "source_values_total": _count_slim_values(self.payload),
            "structural_nodes_total": _count_slim_structural_nodes(self.payload),
            "choices_total": len(self.payload.get("choices", ())),
            "provider_calls_total": self.provider_calls_total,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6SlimAliasReceipt:
    schema_version: str
    policy_version: str
    context_contract_identity: str
    active_packet_hash: str
    slim_view_hash: str
    value_aliases: dict[str, str]
    structural_aliases: dict[str, dict[str, Any]]
    type_aliases: dict[str, str]
    choice_aliases: dict[str, str]
    evidence_only_source_refs: tuple[str, ...]
    evidence_only_aliases: dict[str, str]
    choice_role_bindings: dict[str, list[dict[str, str]]]
    provider_calls_total: int
    integrity_hash: str

    def to_private_dict(self) -> dict[str, Any]:
        return {
            **_slim_alias_receipt_payload_without_integrity(self),
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "context_contract_identity": self.context_contract_identity,
            "active_packet_hash": self.active_packet_hash,
            "slim_view_hash": self.slim_view_hash,
            "value_aliases_total": len(self.value_aliases),
            "structural_aliases_total": len(self.structural_aliases),
            "type_aliases_total": len(self.type_aliases),
            "choice_aliases_total": len(self.choice_aliases),
            "evidence_only_source_refs_total": len(
                self.evidence_only_source_refs
            ),
            "provider_calls_total": self.provider_calls_total,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6Packet:
    schema_version: str
    policy_version: str
    payload: dict[str, Any]
    packet_hash: str
    evidence_bundle_integrity_hash: str
    candidate_compilation_integrity_hash: str
    semantic_projection_hash: str
    slim_candidate: Gate2FinancialSemanticV6SlimViewCandidate
    slim_alias_receipt: Gate2FinancialSemanticV6SlimAliasReceipt
    context_v2_candidate: Gate2FinancialSemanticV6ContextV2Candidate
    context_v2_mapping_receipt: (
        Gate2FinancialSemanticV6ContextV2MappingReceipt
    )


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
        slim_choice_order: tuple[str, ...] | None = None,
    ) -> Gate2FinancialSemanticV6Packet:
        return self._build(
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            slim_choice_order=slim_choice_order,
        )

    def _build(
        self,
        *,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
        slim_choice_order: tuple[str, ...] | None = None,
    ) -> Gate2FinancialSemanticV6Packet:
        _validate_compilation(
            compilation=compilation,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            registry=self.registry,
        )
        projection_factory = Gate2FinancialSemanticV5ProjectionFactory()
        projection = projection_factory.create()
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
                _compact_type_card(cards_by_type[input_type_id])
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
                _compact_type_card(cards_by_type[input_type_id])
                for input_type_id in available_type_ids
            ],
        )
        packet_hash = sha256_json(payload)
        slim_candidate, slim_alias_receipt = _slim_candidate_and_receipt(
            evidence_bundle=evidence_bundle,
            compilation=compilation,
            active_payload=payload,
            active_packet_hash=packet_hash,
            slim_choice_order=slim_choice_order,
        )
        try:
            context_v2_projection = (
                projection_factory.create_context_v2_candidate(
                    registry=self.registry,
                    source_family_id=evidence_bundle.source_family_id,
                )
            )
        except (
            Gate2FinancialSemanticV5ProjectionError,
            RuntimeError,
        ) as exc:
            code = getattr(exc, "code", str(exc))
            raise Gate2FinancialSemanticV6PacketError(code) from exc
        (
            context_v2_candidate,
            context_v2_mapping_receipt,
        ) = _context_v2_candidate_and_receipt(
            evidence_bundle=evidence_bundle,
            compilation=compilation,
            registry=self.registry,
            projection=context_v2_projection,
            active_payload=payload,
            active_packet_hash=packet_hash,
        )
        return Gate2FinancialSemanticV6Packet(
            schema_version=SEMANTIC_PACKET_SCHEMA_VERSION,
            policy_version=SEMANTIC_PACKET_POLICY_VERSION,
            payload=copy.deepcopy(payload),
            packet_hash=packet_hash,
            evidence_bundle_integrity_hash=evidence_bundle.integrity_hash,
            candidate_compilation_integrity_hash=(compilation.integrity_hash),
            semantic_projection_hash=projection.projection_hash,
            slim_candidate=slim_candidate,
            slim_alias_receipt=slim_alias_receipt,
            context_v2_candidate=context_v2_candidate,
            context_v2_mapping_receipt=context_v2_mapping_receipt,
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
    try:
        slim_choice_order = tuple(
            packet.slim_alias_receipt.choice_aliases.values()
        )
    except AttributeError:
        _fail("financial_semantic_v6_packet_integrity_invalid")
    expected = Gate2FinancialSemanticV6PacketFactory(registry=registry)._build(
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        slim_choice_order=slim_choice_order,
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


def render_financial_semantic_v6_slim_candidate_private_exact(
    *,
    packet: Gate2FinancialSemanticV6Packet,
) -> str:
    _validate_packet_shape(packet)
    return json.dumps(
        packet.slim_candidate.payload,
        ensure_ascii=False,
        sort_keys=False,
        indent=2,
        allow_nan=False,
    )


def render_financial_semantic_v6_slim_alias_receipt_private_exact(
    *,
    packet: Gate2FinancialSemanticV6Packet,
) -> str:
    _validate_packet_shape(packet)
    return json.dumps(
        packet.slim_alias_receipt.to_private_dict(),
        ensure_ascii=False,
        sort_keys=False,
        indent=2,
        allow_nan=False,
    )


def render_financial_semantic_v6_context_v2_candidate_private_exact(
    *,
    packet: Gate2FinancialSemanticV6Packet,
) -> str:
    _validate_packet_shape(packet)
    return json.dumps(
        packet.context_v2_candidate.payload,
        ensure_ascii=False,
        sort_keys=False,
        indent=2,
        allow_nan=False,
    )


def render_financial_semantic_v6_context_v2_mapping_receipt_private_exact(
    *,
    packet: Gate2FinancialSemanticV6Packet,
) -> str:
    _validate_packet_shape(packet)
    return json.dumps(
        packet.context_v2_mapping_receipt.to_private_dict(),
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
        "non_active_slim_candidate": packet.slim_candidate.safe_summary(),
        "private_slim_alias_receipt": packet.slim_alias_receipt.safe_summary(),
        "non_active_context_v2_candidate": (
            packet.context_v2_candidate.safe_summary()
        ),
        "private_context_v2_mapping_receipt": (
            packet.context_v2_mapping_receipt.safe_summary()
        ),
    }
    return json.dumps(
        safe_payload,
        ensure_ascii=False,
        sort_keys=False,
        indent=2,
        allow_nan=False,
    )


def _slim_candidate_and_receipt(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    active_payload: dict[str, Any],
    active_packet_hash: str,
    slim_choice_order: tuple[str, ...] | None,
) -> tuple[
    Gate2FinancialSemanticV6SlimViewCandidate,
    Gate2FinancialSemanticV6SlimAliasReceipt,
]:
    (
        source,
        value_aliases,
        structural_aliases,
        evidence_only_source_refs,
        evidence_only_aliases,
    ) = _slim_source_and_aliases(evidence_bundle)
    value_alias_by_ref = {
        source_value_ref: alias
        for alias, source_value_ref in value_aliases.items()
    }
    type_aliases = {
        f"T{index}": card["input_type_id"]
        for index, card in enumerate(
            active_payload["available_type_cards"],
            start=1,
        )
    }
    type_alias_by_id = {
        input_type_id: alias
        for alias, input_type_id in type_aliases.items()
    }
    type_cards = [
        _slim_type_card(
            card=card,
            alias=type_alias_by_id[card["input_type_id"]],
            type_alias_by_id=type_alias_by_id,
        )
        for card in active_payload["available_type_cards"]
    ]

    choice_aliases: dict[str, str] = {}
    choice_role_bindings: dict[str, list[dict[str, str]]] = {}
    choices: list[dict[str, Any]] = []
    binding_alias_by_ref = {
        **value_alias_by_ref,
        **{
            source_value_ref: alias
            for source_value_ref, alias in evidence_only_aliases.items()
        },
    }
    options_by_id = {
        option.typed_option_id: option
        for option in compilation.typed_options
    }
    canonical_choice_order = tuple(options_by_id)
    exact_choice_order = (
        canonical_choice_order
        if slim_choice_order is None
        else slim_choice_order
    )
    if (
        not isinstance(exact_choice_order, tuple)
        or len(exact_choice_order) != len(canonical_choice_order)
        or len(exact_choice_order) != len(set(exact_choice_order))
        or set(exact_choice_order) != set(canonical_choice_order)
    ):
        _fail("financial_semantic_v6_slim_choice_order_invalid")
    ordered_options = tuple(
        options_by_id[typed_option_id]
        for typed_option_id in exact_choice_order
    )
    for index, option in enumerate(ordered_options):
        choice_alias = _choice_alias(index)
        choice_aliases[choice_alias] = option.typed_option_id
        exact_bindings = [
            {
                "role_id": binding.role_id,
                "source_value_ref": binding.source_value_ref,
            }
            for binding in option.role_bindings
        ]
        choice_role_bindings[choice_alias] = exact_bindings
        try:
            rendered_bindings = [
                (
                    f"{binding.role_id}="
                    f"{binding_alias_by_ref[binding.source_value_ref]}"
                )
                for binding in option.role_bindings
            ]
            type_alias = type_alias_by_id[option.input_type_id]
        except KeyError as exc:
            raise Gate2FinancialSemanticV6PacketError(
                "financial_semantic_v6_slim_alias_mapping_invalid"
            ) from exc
        choices.append(
            {
                "alias": choice_alias,
                "type": type_alias,
                "bindings": rendered_bindings,
            }
        )

    payload = {
        "task": SEMANTIC_PACKET_AMBIGUITY_RULE,
        "source": source,
        "type_cards": type_cards,
        "choices": choices,
        "unclassified": list(SLIM_VIEW_UNCLASSIFIED_REASONS),
    }
    view_hash = sha256_json(payload)
    candidate = Gate2FinancialSemanticV6SlimViewCandidate(
        schema_version=SLIM_VIEW_SCHEMA_VERSION,
        policy_version=SLIM_VIEW_POLICY_VERSION,
        active=False,
        payload=copy.deepcopy(payload),
        view_hash=view_hash,
        model_visible_utf8_bytes=len(_compact_json_bytes(payload)),
        provider_calls_total=0,
    )
    receipt_payload = {
        "schema_version": SLIM_ALIAS_RECEIPT_SCHEMA_VERSION,
        "policy_version": SLIM_VIEW_POLICY_VERSION,
        "context_contract_identity": (
            LLM_SEMANTIC_CONTEXT_CONTRACT_IDENTITY
        ),
        "active_packet_hash": active_packet_hash,
        "slim_view_hash": view_hash,
        "value_aliases": copy.deepcopy(value_aliases),
        "structural_aliases": copy.deepcopy(structural_aliases),
        "type_aliases": copy.deepcopy(type_aliases),
        "choice_aliases": copy.deepcopy(choice_aliases),
        "evidence_only_source_refs": list(evidence_only_source_refs),
        "evidence_only_aliases": copy.deepcopy(evidence_only_aliases),
        "choice_role_bindings": copy.deepcopy(choice_role_bindings),
        "provider_calls_total": 0,
    }
    receipt = Gate2FinancialSemanticV6SlimAliasReceipt(
        schema_version=SLIM_ALIAS_RECEIPT_SCHEMA_VERSION,
        policy_version=SLIM_VIEW_POLICY_VERSION,
        context_contract_identity=(
            LLM_SEMANTIC_CONTEXT_CONTRACT_IDENTITY
        ),
        active_packet_hash=active_packet_hash,
        slim_view_hash=view_hash,
        value_aliases=copy.deepcopy(value_aliases),
        structural_aliases=copy.deepcopy(structural_aliases),
        type_aliases=copy.deepcopy(type_aliases),
        choice_aliases=copy.deepcopy(choice_aliases),
        evidence_only_source_refs=evidence_only_source_refs,
        evidence_only_aliases=copy.deepcopy(evidence_only_aliases),
        choice_role_bindings=copy.deepcopy(choice_role_bindings),
        provider_calls_total=0,
        integrity_hash=sha256_json(receipt_payload),
    )
    _validate_slim_candidate_material(
        candidate=candidate,
        receipt=receipt,
        evidence_bundle=evidence_bundle,
        compilation=compilation,
    )
    return candidate, receipt


def _slim_source_and_aliases(
    evidence_bundle: Gate2FinancialEvidenceBundle,
) -> tuple[
    dict[str, Any],
    dict[str, str],
    dict[str, dict[str, Any]],
    tuple[str, ...],
    dict[str, str],
]:
    semantic_values = tuple(
        value
        for value in evidence_bundle.source_values
        if value.value_type != "source_reference"
    )
    reference_values = tuple(
        value
        for value in evidence_bundle.source_values
        if value.value_type == "source_reference"
    )
    value_aliases = {
        f"v{index}": value.source_value_ref
        for index, value in enumerate(semantic_values, start=1)
    }
    value_alias_by_ref = {
        source_value_ref: alias
        for alias, source_value_ref in value_aliases.items()
    }

    document_children: list[dict[str, Any]] = []
    structural_aliases: dict[str, dict[str, Any]] = {}
    exact_ref_aliases: dict[str, list[str]] = {}
    table_nodes: dict[str, dict[str, Any]] = {}
    row_nodes: dict[tuple[Any, ...], dict[str, Any]] = {}
    segment_nodes: dict[tuple[Any, ...], dict[str, Any]] = {}
    generic_nodes: dict[tuple[Any, ...], dict[str, Any]] = {}
    counters = {"table": 0, "row": 0, "segment": 0, "group": 0}

    def next_alias(kind: str) -> str:
        counters[kind] += 1
        prefix = {
            "table": "t",
            "row": "r",
            "segment": "seg",
            "group": "g",
        }[kind]
        return f"{prefix}{counters[kind]}"

    def register_structural_alias(
        *,
        alias: str,
        kind: str,
        value: FinancialEvidenceBundleSourceValue,
    ) -> None:
        entry = {
            "kind": kind,
            "association_ref": (
                None if kind == "table" else value.association_ref
            ),
            "page_ref": value.lineage.page_ref,
            "table_ref": value.lineage.table_ref,
            "row_ref": (
                value.lineage.row_ref
                if kind in {"row", "evidence group"}
                else None
            ),
            "cell_ref": (
                value.lineage.cell_ref
                if kind == "evidence group"
                else None
            ),
            "text_segment_ref": (
                value.lineage.text_segment_ref
                if kind in {"text segment", "evidence group"}
                else None
            ),
        }
        structural_aliases[alias] = entry
        for ref in (
            entry["association_ref"],
            entry["table_ref"],
            entry["row_ref"],
            entry["text_segment_ref"],
        ):
            if ref:
                aliases = exact_ref_aliases.setdefault(ref, [])
                if alias not in aliases:
                    aliases.append(alias)

    def ensure_table(
        value: FinancialEvidenceBundleSourceValue,
    ) -> dict[str, Any] | None:
        table_ref = value.lineage.table_ref
        if not table_ref:
            return None
        node = table_nodes.get(table_ref)
        if node is None:
            alias = next_alias("table")
            node = {
                "alias": alias,
                "kind": "table",
                "children": [],
            }
            table_nodes[table_ref] = node
            document_children.append(node)
            register_structural_alias(
                alias=alias,
                kind="table",
                value=value,
            )
        return node

    def add_visible_roles(
        node: dict[str, Any],
        value: FinancialEvidenceBundleSourceValue,
    ) -> None:
        if value.section_role is not None:
            node["section_role"] = value.section_role
        if value.row_role is not None:
            node["row_role"] = value.row_role

    for value in semantic_values:
        if value.association_kind == "table_row":
            parent = ensure_table(value)
            row_key = (
                value.association_ref,
                value.lineage.row_ref,
                value.lineage.table_ref,
                value.section_role,
                value.row_role,
            )
            node = row_nodes.get(row_key)
            if node is None:
                alias = next_alias("row")
                node = {
                    "alias": alias,
                    "kind": "row",
                    "values": [],
                }
                add_visible_roles(node, value)
                row_nodes[row_key] = node
                if parent is None:
                    document_children.append(node)
                else:
                    parent["children"].append(node)
                register_structural_alias(
                    alias=alias,
                    kind="row",
                    value=value,
                )
        elif value.association_kind == "text_segment":
            segment_key = (
                value.association_ref,
                value.lineage.text_segment_ref,
                value.section_role,
                value.row_role,
            )
            node = segment_nodes.get(segment_key)
            if node is None:
                alias = next_alias("segment")
                node = {
                    "alias": alias,
                    "kind": "text segment",
                    "values": [],
                }
                add_visible_roles(node, value)
                segment_nodes[segment_key] = node
                document_children.append(node)
                register_structural_alias(
                    alias=alias,
                    kind="text segment",
                    value=value,
                )
        else:
            _fail("financial_semantic_v6_slim_structure_invalid")
        node["values"].append(
            _slim_source_value(
                value=value,
                alias=value_alias_by_ref[value.source_value_ref],
            )
        )

    def reference_target_alias(
        value: FinancialEvidenceBundleSourceValue,
    ) -> str:
        candidates = list(exact_ref_aliases.get(value.association_ref, ()))
        for lineage_ref in (
            value.lineage.text_segment_ref,
            value.lineage.row_ref,
            value.lineage.table_ref,
        ):
            if not lineage_ref:
                continue
            lineage_candidates = list(
                exact_ref_aliases.get(lineage_ref, ())
            )
            if not candidates:
                candidates = lineage_candidates
                continue
            narrowed = [
                alias for alias in candidates if alias in lineage_candidates
            ]
            if narrowed:
                candidates = narrowed
        leaf_candidates = [
            alias
            for alias in candidates
            if structural_aliases[alias]["kind"] in {"row", "text segment"}
        ]
        if len(leaf_candidates) == 1:
            return leaf_candidates[0]
        if len(candidates) == 1:
            return candidates[0]

        generic_key = (
            value.association_ref,
            value.lineage.page_ref,
            value.lineage.table_ref,
            value.lineage.row_ref,
            value.lineage.text_segment_ref,
        )
        generic = generic_nodes.get(generic_key)
        if generic is None:
            alias = next_alias("group")
            generic = {
                "alias": alias,
                "kind": "evidence group",
            }
            generic_nodes[generic_key] = generic
            document_children.append(generic)
            register_structural_alias(
                alias=alias,
                kind="evidence group",
                value=value,
            )
        return str(generic["alias"])

    evidence_only_aliases = {
        value.source_value_ref: reference_target_alias(value)
        for value in reference_values
    }
    document: dict[str, Any] = {}
    if document_children:
        document["children"] = document_children
    return (
        {"document": document},
        value_aliases,
        structural_aliases,
        tuple(value.source_value_ref for value in reference_values),
        evidence_only_aliases,
    )


def _slim_source_value(
    *,
    value: FinancialEvidenceBundleSourceValue,
    alias: str,
) -> dict[str, str]:
    meaning = (
        value.column_meaning
        or value.visible_label
        or _readable_identifier(value.value_type)
    )
    rendered = {
        "alias": alias,
        "meaning": meaning,
        "value": value.literal_value,
        "type": _readable_identifier(value.value_type),
    }
    if value.visible_label is not None and value.visible_label != meaning:
        rendered["label"] = value.visible_label
    return rendered


def _slim_type_card(
    *,
    card: dict[str, Any],
    alias: str,
    type_alias_by_id: dict[str, str],
) -> dict[str, Any]:
    distinctions = [
        {
            "against": type_alias_by_id.get(
                item["against"],
                _readable_identifier(item["against"]),
            ),
            "rule": item["rule"],
        }
        for item in card["key_semantic_distinctions"]
    ]
    return {
        "alias": alias,
        "meaning": card["short_meaning"],
        "distinctions": distinctions,
        "unclassified_when": card["ambiguity_rule"],
    }


def _choice_alias(index: int) -> str:
    if not isinstance(index, int) or index < 0:
        _fail("financial_semantic_v6_slim_choice_alias_invalid")
    result = ""
    remaining = index
    while True:
        result = chr(ord("A") + (remaining % 26)) + result
        remaining = remaining // 26 - 1
        if remaining < 0:
            return result


def _readable_identifier(value: str) -> str:
    raw = value.removeprefix("source_")
    return raw.replace("_", " ")


def _compact_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _slim_alias_receipt_payload_without_integrity(
    receipt: Gate2FinancialSemanticV6SlimAliasReceipt,
) -> dict[str, Any]:
    return {
        "schema_version": receipt.schema_version,
        "policy_version": receipt.policy_version,
        "context_contract_identity": receipt.context_contract_identity,
        "active_packet_hash": receipt.active_packet_hash,
        "slim_view_hash": receipt.slim_view_hash,
        "value_aliases": copy.deepcopy(receipt.value_aliases),
        "structural_aliases": copy.deepcopy(receipt.structural_aliases),
        "type_aliases": copy.deepcopy(receipt.type_aliases),
        "choice_aliases": copy.deepcopy(receipt.choice_aliases),
        "evidence_only_source_refs": list(
            receipt.evidence_only_source_refs
        ),
        "evidence_only_aliases": copy.deepcopy(
            receipt.evidence_only_aliases
        ),
        "choice_role_bindings": copy.deepcopy(
            receipt.choice_role_bindings
        ),
        "provider_calls_total": receipt.provider_calls_total,
    }


def _validate_slim_candidate_material(
    *,
    candidate: Gate2FinancialSemanticV6SlimViewCandidate,
    receipt: Gate2FinancialSemanticV6SlimAliasReceipt,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
) -> None:
    if (
        tuple(candidate.payload) != SLIM_VIEW_BLOCKS
        or candidate.payload["task"] != SEMANTIC_PACKET_AMBIGUITY_RULE
        or candidate.payload["unclassified"]
        != list(SLIM_VIEW_UNCLASSIFIED_REASONS)
        or any(item is None for item in _walk_values(candidate.payload))
    ):
        _fail("financial_semantic_v6_slim_payload_invalid")
    forbidden_keys = {
        "association_ref",
        "input_type_id",
        "option_id",
        "return_id",
        "source_value_ref",
        "typed_option_id",
    }
    if any(
        forbidden_keys.intersection(item)
        for item in _walk_dicts(candidate.payload)
    ):
        _fail("financial_semantic_v6_slim_forbidden_field")

    values_by_ref = {
        value.source_value_ref: value
        for value in evidence_bundle.source_values
    }
    rendered_values = {
        item["alias"]: item
        for item in _walk_dicts(candidate.payload["source"])
        if "value" in item
    }
    semantic_refs = {
        value.source_value_ref
        for value in evidence_bundle.source_values
        if value.value_type != "source_reference"
    }
    reference_refs = tuple(
        value.source_value_ref
        for value in evidence_bundle.source_values
        if value.value_type == "source_reference"
    )
    if (
        set(receipt.value_aliases.values()) != semantic_refs
        or len(receipt.value_aliases) != len(semantic_refs)
        or set(rendered_values) != set(receipt.value_aliases)
        or receipt.evidence_only_source_refs != reference_refs
        or set(receipt.evidence_only_aliases) != set(reference_refs)
    ):
        _fail("financial_semantic_v6_slim_value_coverage_invalid")
    for alias, source_value_ref in receipt.value_aliases.items():
        source = values_by_ref[source_value_ref]
        rendered = rendered_values[alias]
        if (
            rendered["value"] != source.literal_value
            or rendered["type"] != _readable_identifier(source.value_type)
            or rendered["meaning"]
            != (
                source.column_meaning
                or source.visible_label
                or _readable_identifier(source.value_type)
            )
            or rendered.get("label")
            != (
                source.visible_label
                if source.visible_label is not None
                and source.visible_label != rendered["meaning"]
                else None
            )
        ):
            _fail("financial_semantic_v6_slim_literal_invalid")

    structural_nodes = {
        item["alias"]: item
        for item in _walk_dicts(candidate.payload["source"])
        if item.get("kind")
        in {"table", "row", "text segment", "evidence group"}
    }
    if set(structural_nodes) != set(receipt.structural_aliases):
        _fail("financial_semantic_v6_slim_structure_invalid")
    if any(
        alias not in structural_nodes
        for alias in receipt.evidence_only_aliases.values()
    ):
        _fail("financial_semantic_v6_slim_reference_alias_invalid")

    type_cards = candidate.payload["type_cards"]
    if (
        [item["alias"] for item in type_cards]
        != list(receipt.type_aliases)
        or set(receipt.type_aliases.values())
        != {option.input_type_id for option in compilation.typed_options}
    ):
        _fail("financial_semantic_v6_slim_type_alias_invalid")
    choices = candidate.payload["choices"]
    if (
        [item["alias"] for item in choices]
        != list(receipt.choice_aliases)
        or set(receipt.choice_aliases.values())
        != {option.typed_option_id for option in compilation.typed_options}
        or len(receipt.choice_aliases)
        != len(compilation.typed_options)
        or len(choices) != len(compilation.typed_options)
    ):
        _fail("financial_semantic_v6_slim_choice_alias_invalid")
    options_by_id = {
        option.typed_option_id: option
        for option in compilation.typed_options
    }
    binding_alias_by_ref = {
        **{
            source_value_ref: alias
            for alias, source_value_ref in receipt.value_aliases.items()
        },
        **receipt.evidence_only_aliases,
    }
    type_alias_by_id = {
        input_type_id: alias
        for alias, input_type_id in receipt.type_aliases.items()
    }
    for rendered in choices:
        choice_alias = rendered["alias"]
        option = options_by_id[receipt.choice_aliases[choice_alias]]
        expected_bindings = [
            f"{binding.role_id}={binding_alias_by_ref[binding.source_value_ref]}"
            for binding in option.role_bindings
        ]
        if (
            rendered["type"] != type_alias_by_id[option.input_type_id]
            or rendered["bindings"] != expected_bindings
            or receipt.choice_role_bindings[choice_alias]
            != [
                {
                    "role_id": binding.role_id,
                    "source_value_ref": binding.source_value_ref,
                }
                for binding in option.role_bindings
            ]
        ):
            _fail("financial_semantic_v6_slim_binding_invalid")

    serialized = json.dumps(
        candidate.payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    forbidden_exact_values = {
        evidence_bundle.bundle_id,
        evidence_bundle.document_ref,
        evidence_bundle.normalization_run_ref,
        evidence_bundle.source_package_ref,
        evidence_bundle.source_scope_ref,
        *(
            value.source_value_ref
            for value in evidence_bundle.source_values
        ),
        *(
            value.association_ref
            for value in evidence_bundle.source_values
        ),
        *(receipt.type_aliases.values()),
        *(receipt.choice_aliases.values()),
    }
    if any(value and value in serialized for value in forbidden_exact_values):
        _fail("financial_semantic_v6_slim_opaque_identity_visible")
    _validate_slim_candidate_integrity(
        active_packet_hash=receipt.active_packet_hash,
        candidate=candidate,
        receipt=receipt,
    )


def _validate_slim_candidate_integrity(
    *,
    active_packet_hash: str,
    candidate: Gate2FinancialSemanticV6SlimViewCandidate,
    receipt: Gate2FinancialSemanticV6SlimAliasReceipt,
) -> None:
    if (
        not isinstance(candidate, Gate2FinancialSemanticV6SlimViewCandidate)
        or candidate.schema_version != SLIM_VIEW_SCHEMA_VERSION
        or candidate.policy_version != SLIM_VIEW_POLICY_VERSION
        or candidate.active is not False
        or not isinstance(candidate.payload, dict)
        or tuple(candidate.payload) != SLIM_VIEW_BLOCKS
        or candidate.view_hash != sha256_json(candidate.payload)
        or candidate.model_visible_utf8_bytes
        != len(_compact_json_bytes(candidate.payload))
        or candidate.provider_calls_total != 0
        or not isinstance(receipt, Gate2FinancialSemanticV6SlimAliasReceipt)
        or receipt.schema_version != SLIM_ALIAS_RECEIPT_SCHEMA_VERSION
        or receipt.policy_version != SLIM_VIEW_POLICY_VERSION
        or receipt.context_contract_identity
        != LLM_SEMANTIC_CONTEXT_CONTRACT_IDENTITY
        or receipt.active_packet_hash != active_packet_hash
        or receipt.slim_view_hash != candidate.view_hash
        or receipt.provider_calls_total != 0
        or receipt.integrity_hash
        != sha256_json(
            _slim_alias_receipt_payload_without_integrity(receipt)
        )
    ):
        _fail("financial_semantic_v6_slim_integrity_invalid")


def _count_slim_values(payload: dict[str, Any]) -> int:
    return sum(
        1
        for item in _walk_dicts(payload.get("source", {}))
        if "value" in item
    )


def _count_slim_structural_nodes(payload: dict[str, Any]) -> int:
    return sum(
        1
        for item in _walk_dicts(payload.get("source", {}))
        if item.get("kind")
        in {"table", "row", "text segment", "evidence group"}
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


def _compact_type_card(card: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(card, dict) or any(
        field not in card for field in SEMANTIC_PACKET_TYPE_CARD_FIELDS
    ):
        _fail("financial_semantic_v6_packet_type_card_invalid")
    return {
        field: copy.deepcopy(card[field]) for field in SEMANTIC_PACKET_TYPE_CARD_FIELDS
    }


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
    try:
        _validate_slim_candidate_integrity(
            active_packet_hash=packet.packet_hash,
            candidate=packet.slim_candidate,
            receipt=packet.slim_alias_receipt,
        )
    except Gate2FinancialSemanticV6PacketError as exc:
        raise Gate2FinancialSemanticV6PacketError(
            "financial_semantic_v6_packet_render_input_invalid"
        ) from exc
    _validate_context_v2_sidecar_integrity(packet)


def _validate_context_v2_sidecar_integrity(
    packet: Gate2FinancialSemanticV6Packet,
) -> None:
    candidate = packet.context_v2_candidate
    receipt = packet.context_v2_mapping_receipt
    if (
        not isinstance(
            candidate,
            Gate2FinancialSemanticV6ContextV2Candidate,
        )
        or candidate.schema_version
        != CONTEXT_V2_CANDIDATE_SCHEMA_VERSION
        or candidate.policy_version != CONTEXT_V2_POLICY_VERSION
        or candidate.active is not False
        or candidate.provider_calls_total != 0
        or candidate.view_hash != _model_hash(candidate.payload)
        or candidate.model_visible_utf8_bytes
        != len(_model_json_bytes(candidate.payload))
        or not isinstance(
            receipt,
            Gate2FinancialSemanticV6ContextV2MappingReceipt,
        )
        or receipt.schema_version
        != CONTEXT_V2_MAPPING_RECEIPT_SCHEMA_VERSION
        or receipt.policy_version != CONTEXT_V2_POLICY_VERSION
        or receipt.provider_calls_total != 0
        or receipt.identities.get("active_packet_hash")
        != packet.packet_hash
        or receipt.identities.get("context_view_hash")
        != candidate.view_hash
        or receipt.integrity_hash
        != _integrity_hash(
            _mapping_receipt_payload_without_integrity(receipt)
        )
    ):
        _fail("financial_semantic_v6_packet_render_input_invalid")


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _walk_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield item
            yield from _walk_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield item
            yield from _walk_values(item)


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6PacketError(code)

CONTEXT_V2_CONTRACT_IDENTITY = (
    "broker_reports_gate2_llm_semantic_context_v2"
)
CONTEXT_V2_CONTRACT_VERSION = "2.0.0"
CONTEXT_V2_CANDIDATE_SCHEMA_VERSION = (
    "broker_reports_gate2_llm_semantic_context_v2_candidate"
)
CONTEXT_V2_POLICY_VERSION = (
    "broker_reports_gate2_managed_semantic_decision_context_v2"
)
CONTEXT_V2_MAPPING_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_llm_semantic_context_v2_mapping_receipt_v1"
)
CONTEXT_V2_TYPE_SET_SNAPSHOT_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_type_set_snapshot_v1"
)
CONTEXT_V2_TASK = (
    "Select a typed option only when the visible source uniquely supports "
    "its complete prebound record; otherwise select unclassified."
)
CONTEXT_V2_BLOCKS = (
    "task",
    "source",
    "type_cards",
    "choices",
    "unclassified_reasons",
)
CONTEXT_V2_BLOCKS_WITH_SHARED = (
    "task",
    "source",
    "type_cards",
    "choices",
    "shared_relationships",
    "unclassified_reasons",
)
CONTEXT_V2_AUTHORITY_KINDS = frozenset(
    {
        "packet_task",
        "evidence_bundle",
        "type_set_snapshot",
        "semantic_pack_projection",
        "candidate_compilation",
        "reason_catalog_projection",
        "decision_code_contract",
    }
)
CONTEXT_V2_LOCATION_BY_KIND = {
    "table": "the only visible table",
    "row": "the only visible row",
    "text_segment": "the only visible text segment",
    "evidence_group": "the only visible evidence group",
}
CONTEXT_V2_MODEL_KIND = {
    "table": "table",
    "row": "row",
    "text_segment": "text segment",
    "evidence_group": "evidence group",
}
CONTEXT_V2_ACTIVE_PACKET_IDENTITY = (
    "broker_reports_gate2_financial_semantic_packet_v6"
)
_MACHINE_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_VERSION_SUFFIX_RE = re.compile(r"_v[0-9]+$")
@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV2Candidate:
    schema_version: str
    policy_version: str
    active: bool
    payload: dict[str, Any]
    view_hash: str
    model_visible_utf8_bytes: int
    provider_calls_total: int

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "active": self.active,
            "view_hash": self.view_hash,
            "model_visible_utf8_bytes": self.model_visible_utf8_bytes,
            "source_values_total": sum(
                1
                for item in _walk_dicts(self.payload["source"])
                if "literal" in item
            ),
            "type_cards_total": len(self.payload["type_cards"]),
            "choices_total": len(self.payload["choices"]),
            "relationships_total": sum(
                1
                for item in _walk_dicts(self.payload)
                if "role" in item
                and any(
                    key in item
                    for key in ("value_key", "structure_key", "location")
                )
            ),
            "provider_calls_total": self.provider_calls_total,
            "contains_source_literals": False,
            "contains_global_refs": False,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV2MappingReceipt:
    schema_version: str
    policy_version: str
    identities: dict[str, Any]
    scope: dict[str, Any]
    visible_field_sources: tuple[dict[str, Any], ...]
    local_mappings: dict[str, Any]
    binding_partition: dict[str, Any]
    presentation_order: dict[str, Any]
    provider_calls_total: int
    integrity_hash: str

    def to_private_dict(self) -> dict[str, Any]:
        return {
            **_mapping_receipt_payload_without_integrity(self),
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "context_contract_identity": self.identities[
                "context_contract_identity"
            ],
            "active_packet_hash": self.identities["active_packet_hash"],
            "context_view_hash": self.identities["context_view_hash"],
            "visible_fields_total": len(self.visible_field_sources),
            "value_keys_total": len(
                self.local_mappings["value_keys"]
            ),
            "structure_keys_total": len(
                self.local_mappings["structure_keys"]
            ),
            "type_keys_total": len(
                self.local_mappings["type_keys"]
            ),
            "choice_keys_total": len(
                self.local_mappings["choice_keys"]
            ),
            "evidence_reference_targets_total": len(
                self.local_mappings["evidence_reference_targets"]
            ),
            "visible_relationships_total": len(
                self.binding_partition["visible_relationships"]
            ),
            "backend_only_bindings_total": len(
                self.binding_partition["backend_only_bindings"]
            ),
            "provider_calls_total": self.provider_calls_total,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "integrity_hash": self.integrity_hash,
        }


@dataclass
class _ValueNode:
    source: FinancialEvidenceBundleSourceValue
    source_index: int
    meaning: str
    meaning_authority_pointer: str
    value_type: str
    label: str | None
    value_key: str | None = None
    json_pointer: str | None = None


@dataclass
class _StructureNode:
    kind: str
    source_index: int
    node_identity: dict[str, Any]
    section_role: str | None = None
    row_role: str | None = None
    values: list[_ValueNode] = field(default_factory=list)
    children: list[_StructureNode] = field(default_factory=list)
    structure_key: str | None = None
    json_pointer: str | None = None


@dataclass
class _BindingOccurrence:
    choice_index: int
    binding_index: int
    choice_key: str
    role_id: str
    source_value_ref: str
    classification: str
    readable_role: str
    target_kind: str
    target_object: _ValueNode | _StructureNode | None
    target: str | None = None


@dataclass
class _RelationshipGroup:
    relationship: dict[str, Any]
    occurrences: list[_BindingOccurrence]


class _ReadableCollisionGuard:
    def __init__(self) -> None:
        self._exact_by_rendered: dict[tuple[str, str], str] = {}

    def add(self, *, namespace: str, exact: str, rendered: str) -> None:
        key = (namespace, rendered)
        previous = self._exact_by_rendered.get(key)
        if previous is not None and previous != exact:
            _fail("financial_semantic_context_v2_readable_projection_collision")
        self._exact_by_rendered[key] = exact


def _context_v2_candidate_and_receipt(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    projection: Gate2FinancialSemanticV2CandidateProjection,
    active_payload: dict[str, Any],
    active_packet_hash: str,
) -> tuple[
    Gate2FinancialSemanticV6ContextV2Candidate,
    Gate2FinancialSemanticV6ContextV2MappingReceipt,
]:
    candidate, receipt = _derive_context_v2_candidate_and_receipt(
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        registry=registry,
        projection=projection,
        active_payload=active_payload,
        active_packet_hash=active_packet_hash,
    )
    validate_financial_semantic_context_v2_material(
        candidate=candidate,
        receipt=receipt,
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        registry=registry,
        projection=projection,
        active_payload=active_payload,
        active_packet_hash=active_packet_hash,
    )
    return candidate, receipt


def _derive_context_v2_candidate_and_receipt(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    projection: Gate2FinancialSemanticV2CandidateProjection,
    active_payload: dict[str, Any],
    active_packet_hash: str,
) -> tuple[
    Gate2FinancialSemanticV6ContextV2Candidate,
    Gate2FinancialSemanticV6ContextV2MappingReceipt,
]:
    guard = _ReadableCollisionGuard()
    type_set_snapshot, compiler_observed_type_ids = _type_set_snapshot(
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        registry=registry,
        projection=projection,
    )
    type_cards_by_id = {
        item["input_type_id"]: item
        for item in projection.pack_projection["type_cards"]
    }
    type_key_by_id = {
        input_type_id: f"type_{index}"
        for index, input_type_id in enumerate(
            type_set_snapshot["available_type_ids"],
            start=1,
        )
    }
    choice_key_by_id = {
        option.typed_option_id: f"choice_{index}"
        for index, option in enumerate(compilation.typed_options, start=1)
    }
    top_nodes, values_by_ref, nodes_by_ref = _source_graph(
        evidence_bundle=evidence_bundle,
        guard=guard,
    )
    (
        occurrences,
        backend_only_bindings,
        necessary_reference_refs,
    ) = _binding_occurrences(
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        type_cards_by_id=type_cards_by_id,
        choice_key_by_id=choice_key_by_id,
        guard=guard,
        values_by_ref=values_by_ref,
    )
    reference_target_by_ref = _resolve_necessary_references(
        evidence_bundle=evidence_bundle,
        necessary_reference_refs=necessary_reference_refs,
        top_nodes=top_nodes,
        nodes_by_ref=nodes_by_ref,
    )
    _bind_occurrence_targets(
        occurrences=occurrences,
        values_by_ref=values_by_ref,
        reference_target_by_ref=reference_target_by_ref,
    )
    _assign_local_source_keys(top_nodes=top_nodes, occurrences=occurrences)
    _finish_occurrence_targets(occurrences)
    shared, local_by_choice = _factor_relationships(
        occurrences=occurrences,
        choices_total=len(compilation.typed_options),
    )
    source_payload, source_field_sources, value_mappings, structure_mappings = (
        _render_source(top_nodes)
    )
    (
        type_card_payload,
        type_field_sources,
        type_mappings,
    ) = _render_type_cards(
        projection=projection,
        type_set_snapshot=type_set_snapshot,
        type_key_by_id=type_key_by_id,
        guard=guard,
    )
    (
        choice_payload,
        choice_field_sources,
        choice_mappings,
        local_relationship_rows,
    ) = _render_choices(
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        projection=projection,
        type_key_by_id=type_key_by_id,
        choice_key_by_id=choice_key_by_id,
        local_by_choice=local_by_choice,
    )
    (
        shared_payload,
        shared_field_sources,
        shared_relationship_rows,
    ) = _render_shared_relationships(shared)
    (
        reason_payload,
        reason_field_sources,
    ) = _render_reason_cards(projection)
    payload: dict[str, Any] = {
        "task": CONTEXT_V2_TASK,
        "source": source_payload,
        "type_cards": type_card_payload,
        "choices": choice_payload,
    }
    if shared_payload:
        payload["shared_relationships"] = shared_payload
    payload["unclassified_reasons"] = reason_payload
    view_hash = _model_hash(payload)
    candidate = Gate2FinancialSemanticV6ContextV2Candidate(
        schema_version=CONTEXT_V2_CANDIDATE_SCHEMA_VERSION,
        policy_version=CONTEXT_V2_POLICY_VERSION,
        active=False,
        payload=copy.deepcopy(payload),
        view_hash=view_hash,
        model_visible_utf8_bytes=len(_model_json_bytes(payload)),
        provider_calls_total=0,
    )
    task_field_source = {
        "/task": (
            "packet_task",
            "/ambiguity_rule",
        )
    }
    field_source_index = {
        **task_field_source,
        **source_field_sources,
        **type_field_sources,
        **choice_field_sources,
        **shared_field_sources,
        **reason_field_sources,
    }
    authority_views = {
        "packet_task": active_payload["task"],
        "evidence_bundle": evidence_bundle.to_private_dict(),
        "type_set_snapshot": type_set_snapshot,
        "semantic_pack_projection": projection.pack_projection,
        "candidate_compilation": compilation.to_private_dict(),
        "reason_catalog_projection": projection.reason_projection,
        "decision_code_contract": projection.decision_code_view,
    }
    visible_field_sources = _visible_field_source_rows(
        payload=payload,
        field_source_index=field_source_index,
        authority_views=authority_views,
    )
    evidence_reference_targets = _evidence_reference_target_rows(
        evidence_bundle=evidence_bundle,
        necessary_reference_refs=necessary_reference_refs,
        reference_target_by_ref=reference_target_by_ref,
    )
    visible_relationship_rows = [
        *local_relationship_rows,
        *shared_relationship_rows,
    ]
    _validate_binding_partition(
        compilation=compilation,
        choice_key_by_id=choice_key_by_id,
        visible_relationship_rows=visible_relationship_rows,
        backend_only_bindings=backend_only_bindings,
    )
    presentation_arrays = {
        "value_keys": [
            item["value_key"] for item in value_mappings
        ],
        "structure_keys": [
            item["structure_key"] for item in structure_mappings
        ],
        "type_keys": [
            item["type_key"] for item in type_mappings
        ],
        "choice_keys": [
            item["choice_key"] for item in choice_mappings
        ],
        "reason_codes": [item["code"] for item in reason_payload],
    }
    presentation_order = {
        **copy.deepcopy(presentation_arrays),
        "presentation_identity": _integrity_hash(presentation_arrays),
        "permutation_identity": _integrity_hash(
            [
                item["typed_option_id"]
                for item in choice_mappings
            ]
        ),
    }
    identities = _receipt_identities(
        registry=registry,
        projection=projection,
        active_packet_hash=active_packet_hash,
        context_view_hash=view_hash,
    )
    scope = {
        "evidence_bundle_id": evidence_bundle.bundle_id,
        "evidence_bundle_integrity_hash": evidence_bundle.integrity_hash,
        "source_scope_ref": evidence_bundle.source_scope_ref,
        "candidate_compilation_integrity_hash": compilation.integrity_hash,
        "type_set_snapshot": copy.deepcopy(type_set_snapshot),
        "compiler_observed_type_ids": list(
            compiler_observed_type_ids
        ),
        "type_set_parity": True,
    }
    local_mappings = {
        "value_keys": value_mappings,
        "structure_keys": structure_mappings,
        "evidence_reference_targets": evidence_reference_targets,
        "type_keys": type_mappings,
        "choice_keys": choice_mappings,
    }
    binding_partition = {
        "visible_relationships": visible_relationship_rows,
        "backend_only_bindings": backend_only_bindings,
    }
    receipt_material = {
        "schema_version": CONTEXT_V2_MAPPING_RECEIPT_SCHEMA_VERSION,
        "policy_version": CONTEXT_V2_POLICY_VERSION,
        "identities": identities,
        "scope": scope,
        "visible_field_sources": visible_field_sources,
        "local_mappings": local_mappings,
        "binding_partition": binding_partition,
        "presentation_order": presentation_order,
        "provider_calls_total": 0,
    }
    receipt = Gate2FinancialSemanticV6ContextV2MappingReceipt(
        schema_version=CONTEXT_V2_MAPPING_RECEIPT_SCHEMA_VERSION,
        policy_version=CONTEXT_V2_POLICY_VERSION,
        identities=copy.deepcopy(identities),
        scope=copy.deepcopy(scope),
        visible_field_sources=tuple(
            copy.deepcopy(visible_field_sources)
        ),
        local_mappings=copy.deepcopy(local_mappings),
        binding_partition=copy.deepcopy(binding_partition),
        presentation_order=copy.deepcopy(presentation_order),
        provider_calls_total=0,
        integrity_hash=_integrity_hash(receipt_material),
    )
    return candidate, receipt


def _type_set_snapshot(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    projection: Gate2FinancialSemanticV2CandidateProjection,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    baseline = projection.semantic_pack_source_baseline
    pack_registry_parity = (
        baseline.get("registry_version") == registry.registry_version
        and baseline.get("registry_sha256") == registry.registry_hash
        and baseline.get("accepted_type_ids")
        == [item.input_type_id for item in registry.declarations]
    )
    if not pack_registry_parity:
        _fail("financial_semantic_context_v2_pack_registry_parity_invalid")
    cards = projection.pack_projection.get("type_cards")
    if not isinstance(cards, list):
        _fail("financial_semantic_context_v2_type_set_invalid")
    available_type_ids = tuple(
        declaration.input_type_id
        for declaration in registry.declarations
        if declaration.lifecycle == "active"
        and evidence_bundle.source_family_id
        in declaration.compatible_source_families
    )
    projected_type_ids = tuple(
        item.get("input_type_id")
        for item in cards
        if isinstance(item, dict)
    )
    if projected_type_ids != available_type_ids:
        _fail("financial_semantic_context_v2_type_set_invalid")
    observed: list[str] = []
    for input_type_id in (
        *(
            option.input_type_id
            for option in compilation.typed_options
        ),
        *(
            block.input_type_id
            for block in compilation.blocked_bindings
        ),
    ):
        if input_type_id not in observed:
            observed.append(input_type_id)
    if (
        len(observed) != len(available_type_ids)
        or set(observed) != set(available_type_ids)
    ):
        _fail("financial_semantic_context_v2_compiler_type_set_mismatch")
    material = {
        "schema_version": CONTEXT_V2_TYPE_SET_SNAPSHOT_SCHEMA_VERSION,
        "source_family_id": evidence_bundle.source_family_id,
        "registry_identity": registry.registry_id,
        "registry_version": registry.registry_version,
        "registry_hash": registry.registry_hash,
        "semantic_pack_identity": projection.semantic_pack_identity[
            "pack_id"
        ],
        "semantic_pack_version": projection.semantic_pack_identity[
            "semantic_version"
        ],
        "semantic_pack_integrity_sha256": (
            projection.semantic_pack_identity["integrity_sha256"]
        ),
        "pack_registry_baseline_parity": True,
        "available_type_ids": list(available_type_ids),
    }
    snapshot = {
        **material,
        "integrity_hash": _integrity_hash(material),
    }
    return snapshot, tuple(observed)


def _validate_local_mappings(
    *,
    candidate: Gate2FinancialSemanticV6ContextV2Candidate,
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    projection: Gate2FinancialSemanticV2CandidateProjection,
) -> None:
    mappings = receipt.local_mappings
    if tuple(mappings) != (
        "value_keys",
        "structure_keys",
        "evidence_reference_targets",
        "type_keys",
        "choice_keys",
    ):
        _fail("financial_semantic_context_v2_local_mapping_invalid")
    value_rows = mappings["value_keys"]
    structure_rows = mappings["structure_keys"]
    reference_rows = mappings["evidence_reference_targets"]
    type_rows = mappings["type_keys"]
    choice_rows = mappings["choice_keys"]
    _validate_mapping_key_sequence(
        rows=value_rows,
        key="value_key",
        prefix="value_",
    )
    _validate_mapping_key_sequence(
        rows=structure_rows,
        key="structure_key",
        prefix="structure_",
    )
    _validate_mapping_key_sequence(
        rows=type_rows,
        key="type_key",
        prefix="type_",
    )
    _validate_mapping_key_sequence(
        rows=choice_rows,
        key="choice_key",
        prefix="choice_",
    )
    source_by_ref = {
        item.source_value_ref: item
        for item in evidence_bundle.source_values
    }
    for row in value_rows:
        if tuple(row) != (
            "value_key",
            "json_pointer",
            "source_value_ref",
        ):
            _fail("financial_semantic_context_v2_value_mapping_invalid")
        source = source_by_ref.get(row["source_value_ref"])
        try:
            rendered = _json_pointer_get(
                candidate.payload,
                row["json_pointer"],
            )
        except (KeyError, IndexError, TypeError):
            _fail("financial_semantic_context_v2_value_mapping_invalid")
        if (
            source is None
            or source.value_type == "source_reference"
            or not isinstance(rendered, dict)
            or rendered.get("value_key") != row["value_key"]
            or rendered.get("literal") != source.literal_value
        ):
            _fail("financial_semantic_context_v2_value_mapping_invalid")
    for row in structure_rows:
        if tuple(row) != (
            "structure_key",
            "json_pointer",
            "node_identity",
        ):
            _fail("financial_semantic_context_v2_structure_mapping_invalid")
        try:
            rendered = _json_pointer_get(
                candidate.payload,
                row["json_pointer"],
            )
        except (KeyError, IndexError, TypeError):
            _fail("financial_semantic_context_v2_structure_mapping_invalid")
        if (
            not isinstance(rendered, dict)
            or rendered.get("structure_key") != row["structure_key"]
            or not _valid_node_identity(row["node_identity"])
        ):
            _fail("financial_semantic_context_v2_structure_mapping_invalid")
    pack_cards = projection.pack_projection["type_cards"]
    if len(type_rows) != len(pack_cards):
        _fail("financial_semantic_context_v2_type_mapping_invalid")
    for index, (row, private_card) in enumerate(
        zip(type_rows, pack_cards, strict=True)
    ):
        if tuple(row) != (
            "type_key",
            "json_pointer",
            "input_type_id",
        ):
            _fail("financial_semantic_context_v2_type_mapping_invalid")
        try:
            card = _json_pointer_get(
                candidate.payload,
                row["json_pointer"],
            )
        except (KeyError, IndexError, TypeError):
            _fail("financial_semantic_context_v2_type_mapping_invalid")
        if (
            row["json_pointer"] != f"/type_cards/{index}"
            or row["input_type_id"] != private_card["input_type_id"]
            or not isinstance(card, dict)
            or card.get("type_key") != row["type_key"]
            or card.get("title") != private_card["title"]
        ):
            _fail("financial_semantic_context_v2_type_mapping_invalid")
    if len(choice_rows) != len(compilation.typed_options):
        _fail("financial_semantic_context_v2_choice_mapping_invalid")
    for index, (row, option) in enumerate(
        zip(choice_rows, compilation.typed_options, strict=True)
    ):
        if tuple(row) != (
            "choice_key",
            "json_pointer",
            "typed_option_id",
            "association_ref",
            "type_key",
        ):
            _fail("financial_semantic_context_v2_choice_mapping_invalid")
        try:
            choice = _json_pointer_get(
                candidate.payload,
                row["json_pointer"],
            )
        except (KeyError, IndexError, TypeError):
            _fail("financial_semantic_context_v2_choice_mapping_invalid")
        association_refs = {
            source_by_ref[binding.source_value_ref].association_ref
            for binding in option.role_bindings
            if binding.source_value_ref in source_by_ref
        }
        if (
            row["json_pointer"] != f"/choices/{index}"
            or row["typed_option_id"] != option.typed_option_id
            or len(association_refs) != 1
            or row["association_ref"] != next(iter(association_refs))
            or not isinstance(choice, dict)
            or choice.get("choice_key") != row["choice_key"]
            or choice.get("type_key") != row["type_key"]
        ):
            _fail("financial_semantic_context_v2_choice_mapping_invalid")
    _validate_relationship_rows(
        candidate=candidate,
        receipt=receipt,
        source_by_ref=source_by_ref,
    )
    _validate_reference_rows(
        receipt=receipt,
        reference_rows=reference_rows,
        evidence_bundle=evidence_bundle,
    )
    _validate_local_key_usage(candidate=candidate, receipt=receipt)


def _validate_mapping_key_sequence(
    *,
    rows: list[dict[str, Any]],
    key: str,
    prefix: str,
) -> None:
    if (
        not isinstance(rows, list)
        or [item.get(key) for item in rows]
        != [
            prefix + str(index)
            for index in range(1, len(rows) + 1)
        ]
        or len({item.get("json_pointer") for item in rows}) != len(rows)
    ):
        _fail("financial_semantic_context_v2_local_key_invalid")


def _valid_node_identity(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    expected = {
        "table": ("kind", "table_ref"),
        "row": (
            "kind",
            "association_ref",
            "row_ref",
            "table_ref",
            "section_role",
            "row_role",
        ),
        "text_segment": (
            "kind",
            "association_ref",
            "text_segment_ref",
            "section_role",
            "row_role",
        ),
        "evidence_group": (
            "kind",
            "association_ref",
            "page_ref",
            "table_ref",
            "row_ref",
            "text_segment_ref",
        ),
    }
    kind = value.get("kind")
    return kind in expected and tuple(value) == expected[kind]


def _validate_relationship_rows(
    *,
    candidate: Gate2FinancialSemanticV6ContextV2Candidate,
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
    source_by_ref: dict[str, FinancialEvidenceBundleSourceValue],
) -> None:
    rows = receipt.binding_partition.get("visible_relationships")
    backend = receipt.binding_partition.get("backend_only_bindings")
    if (
        tuple(receipt.binding_partition)
        != ("visible_relationships", "backend_only_bindings")
        or not isinstance(rows, list)
        or not isinstance(backend, list)
    ):
        _fail("financial_semantic_context_v2_binding_partition_invalid")
    expected_pointers: list[str] = []
    for choice_index, choice in enumerate(candidate.payload["choices"]):
        for index in range(len(choice.get("relationships", ()))):
            expected_pointers.append(
                f"/choices/{choice_index}/relationships/{index}"
            )
    for index in range(
        len(candidate.payload.get("shared_relationships", ()))
    ):
        expected_pointers.append(f"/shared_relationships/{index}")
    if [item.get("json_pointer") for item in rows] != expected_pointers:
        _fail("financial_semantic_context_v2_relationship_order_invalid")
    choice_keys = [
        item["choice_key"]
        for item in candidate.payload["choices"]
    ]
    for row in rows:
        if tuple(row) != (
            "json_pointer",
            "classification",
            "sharing",
            "covered_bindings",
        ):
            _fail("financial_semantic_context_v2_relationship_mapping_invalid")
        try:
            relationship = _json_pointer_get(
                candidate.payload,
                row["json_pointer"],
            )
        except (KeyError, IndexError, TypeError):
            _fail(
                "financial_semantic_context_v2_relationship_mapping_invalid"
            )
        covered = row["covered_bindings"]
        if (
            not isinstance(relationship, dict)
            or row["classification"]
            not in {"semantic_value", "evidence_predicate"}
            or row["sharing"] not in {"shared", "choice_specific"}
            or not isinstance(covered, list)
            or not covered
        ):
            _fail(
                "financial_semantic_context_v2_relationship_mapping_invalid"
            )
        covered_choices: list[str] = []
        for binding in covered:
            if tuple(binding) != (
                "choice_key",
                "role_id",
                "source_value_ref",
            ):
                _fail(
                    "financial_semantic_context_v2_relationship_mapping_invalid"
                )
            source = source_by_ref.get(binding["source_value_ref"])
            if source is None:
                _fail(
                    "financial_semantic_context_v2_relationship_mapping_invalid"
                )
            expected_class = (
                "evidence_predicate"
                if source.value_type == "source_reference"
                else "semantic_value"
            )
            if expected_class != row["classification"]:
                _fail(
                    "financial_semantic_context_v2_relationship_mapping_invalid"
                )
            if binding["choice_key"] not in covered_choices:
                covered_choices.append(binding["choice_key"])
        if row["sharing"] == "shared":
            applies_to = relationship.get("applies_to", choice_keys)
            if len(covered_choices) < 2 or covered_choices != applies_to:
                _fail(
                    "financial_semantic_context_v2_relationship_sharing_invalid"
                )
        else:
            pointer_choice_index = int(
                row["json_pointer"].split("/")[2]
            )
            if covered_choices != [choice_keys[pointer_choice_index]]:
                _fail(
                    "financial_semantic_context_v2_relationship_sharing_invalid"
                )
    for item in backend:
        if tuple(item) != (
            "choice_key",
            "role_id",
            "source_value_ref",
        ):
            _fail("financial_semantic_context_v2_binding_partition_invalid")


def _validate_reference_rows(
    *,
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
    reference_rows: list[dict[str, str]],
    evidence_bundle: Gate2FinancialEvidenceBundle,
) -> None:
    necessary_refs: list[str] = []
    for row in receipt.binding_partition["visible_relationships"]:
        if row["classification"] != "evidence_predicate":
            continue
        for binding in row["covered_bindings"]:
            exact_ref = binding["source_value_ref"]
            if exact_ref not in necessary_refs:
                necessary_refs.append(exact_ref)
    canonical = [
        item.source_value_ref
        for item in evidence_bundle.source_values
        if item.source_value_ref in set(necessary_refs)
    ]
    if [item.get("source_value_ref") for item in reference_rows] != canonical:
        _fail("financial_semantic_context_v2_reference_mapping_invalid")
    for row in reference_rows:
        if (
            tuple(row) != ("source_value_ref", "target_kind", "target")
            or row["target_kind"] not in {"structure_key", "location"}
            or not isinstance(row["target"], str)
            or not row["target"]
        ):
            _fail("financial_semantic_context_v2_reference_mapping_invalid")


def _validate_local_key_usage(
    *,
    candidate: Gate2FinancialSemanticV6ContextV2Candidate,
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
) -> None:
    mappings = receipt.local_mappings
    value_keys = {item["value_key"] for item in mappings["value_keys"]}
    structure_keys = {
        item["structure_key"] for item in mappings["structure_keys"]
    }
    type_keys = {item["type_key"] for item in mappings["type_keys"]}
    choice_keys = {item["choice_key"] for item in mappings["choice_keys"]}
    consumed_values: set[str] = set()
    consumed_structures: set[str] = set()
    for item in _walk_dicts(candidate.payload):
        if "role" in item:
            if "value_key" in item:
                consumed_values.add(item["value_key"])
            if "structure_key" in item:
                consumed_structures.add(item["structure_key"])
            if "applies_to" in item and not set(item["applies_to"]).issubset(
                choice_keys
            ):
                _fail("financial_semantic_context_v2_local_key_invalid")
    if consumed_values != value_keys or consumed_structures != structure_keys:
        _fail("financial_semantic_context_v2_local_key_invalid")
    if {
        item["type_key"] for item in candidate.payload["type_cards"]
    } != type_keys:
        _fail("financial_semantic_context_v2_local_key_invalid")
    if {
        item["choice_key"] for item in candidate.payload["choices"]
    } != choice_keys:
        _fail("financial_semantic_context_v2_local_key_invalid")
    if not all(
        item["type_key"] in type_keys
        for item in candidate.payload["choices"]
    ):
        _fail("financial_semantic_context_v2_local_key_invalid")


def _validate_presentation_order(
    *,
    candidate: Gate2FinancialSemanticV6ContextV2Candidate,
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
) -> None:
    mappings = receipt.local_mappings
    arrays = {
        "value_keys": [item["value_key"] for item in mappings["value_keys"]],
        "structure_keys": [
            item["structure_key"] for item in mappings["structure_keys"]
        ],
        "type_keys": [item["type_key"] for item in mappings["type_keys"]],
        "choice_keys": [
            item["choice_key"] for item in mappings["choice_keys"]
        ],
        "reason_codes": [
            item["code"]
            for item in candidate.payload["unclassified_reasons"]
        ],
    }
    expected = {
        **arrays,
        "presentation_identity": _integrity_hash(arrays),
        "permutation_identity": _integrity_hash(
            [
                item["typed_option_id"]
                for item in mappings["choice_keys"]
            ]
        ),
    }
    if receipt.presentation_order != expected:
        _fail("financial_semantic_context_v2_presentation_invalid")


def _primitive_leaf_entries(
    value: Any,
    pointer: str = "",
):
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


def _json_pointer_get(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = value
    for raw_segment in pointer[1:].split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[segment]
        elif isinstance(current, list):
            if not segment.isdecimal():
                raise KeyError(pointer)
            current = current[int(segment)]
        else:
            raise TypeError(pointer)
    return current


def _contains_none(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return any(
            _contains_none(key) or _contains_none(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_none(item) for item in value)
    return False


def _model_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _integrity_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _model_hash(value: Any) -> str:
    return hashlib.sha256(_model_json_bytes(value)).hexdigest()


def _integrity_hash(value: Any) -> str:
    return hashlib.sha256(_integrity_json_bytes(value)).hexdigest()

def _validate_scope(
    *,
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    projection: Gate2FinancialSemanticV2CandidateProjection,
) -> None:
    type_set_snapshot, observed = _type_set_snapshot(
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        registry=registry,
        projection=projection,
    )
    expected = {
        "evidence_bundle_id": evidence_bundle.bundle_id,
        "evidence_bundle_integrity_hash": evidence_bundle.integrity_hash,
        "source_scope_ref": evidence_bundle.source_scope_ref,
        "candidate_compilation_integrity_hash": compilation.integrity_hash,
        "type_set_snapshot": type_set_snapshot,
        "compiler_observed_type_ids": list(observed),
        "type_set_parity": True,
    }
    if receipt.scope != expected:
        _fail("financial_semantic_context_v2_scope_invalid")


def _validate_visible_field_sources(
    *,
    candidate: Gate2FinancialSemanticV6ContextV2Candidate,
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    projection: Gate2FinancialSemanticV2CandidateProjection,
    active_payload: dict[str, Any],
) -> None:
    leaves = dict(_primitive_leaf_entries(candidate.payload))
    for pointer in ("/type_cards", "/choices"):
        if _json_pointer_get(candidate.payload, pointer) == []:
            leaves[pointer] = []
    rows = list(receipt.visible_field_sources)
    pointers = [item.get("json_pointer") for item in rows]
    if (
        pointers != sorted(leaves)
        or len(pointers) != len(set(pointers))
        or set(pointers) != set(leaves)
    ):
        _fail("financial_semantic_context_v2_field_mapping_incomplete")
    authority_views = {
        "packet_task": active_payload["task"],
        "evidence_bundle": evidence_bundle.to_private_dict(),
        "type_set_snapshot": receipt.scope["type_set_snapshot"],
        "semantic_pack_projection": projection.pack_projection,
        "candidate_compilation": compilation.to_private_dict(),
        "reason_catalog_projection": projection.reason_projection,
        "decision_code_contract": projection.decision_code_view,
    }
    for row in rows:
        if (
            not isinstance(row, dict)
            or tuple(row)
            != (
                "json_pointer",
                "authority_kind",
                "authority_pointer",
                "field_content_hash",
            )
            or row["authority_kind"] not in CONTEXT_V2_AUTHORITY_KINDS
            or row["authority_kind"] not in authority_views
            or not isinstance(row["authority_pointer"], str)
            or row["field_content_hash"]
            != _integrity_hash(leaves[row["json_pointer"]])
        ):
            _fail("financial_semantic_context_v2_field_mapping_invalid")
        try:
            _json_pointer_get(
                authority_views[row["authority_kind"]],
                row["authority_pointer"],
            )
        except (KeyError, IndexError, TypeError):
            _fail(
                "financial_semantic_context_v2_authority_pointer_invalid"
            )



def _visible_field_source_rows(
    *,
    payload: dict[str, Any],
    field_source_index: dict[str, tuple[str, str]],
    authority_views: dict[str, Any],
) -> list[dict[str, Any]]:
    leaves = dict(_primitive_leaf_entries(payload))
    for required_empty_pointer in ("/type_cards", "/choices"):
        try:
            value = _json_pointer_get(payload, required_empty_pointer)
        except (KeyError, IndexError, TypeError):
            continue
        if value == []:
            leaves[required_empty_pointer] = value
    if set(leaves) != set(field_source_index):
        _fail("financial_semantic_context_v2_field_mapping_incomplete")
    rows: list[dict[str, Any]] = []
    for pointer in sorted(leaves):
        source = field_source_index[pointer]
        if (
            not isinstance(source, tuple)
            or len(source) != 2
            or source[0] not in CONTEXT_V2_AUTHORITY_KINDS
            or source[0] not in authority_views
            or not isinstance(source[1], str)
        ):
            _fail("financial_semantic_context_v2_authority_mapping_invalid")
        try:
            _json_pointer_get(authority_views[source[0]], source[1])
        except (KeyError, IndexError, TypeError):
            _fail("financial_semantic_context_v2_authority_pointer_invalid")
        rows.append(
            {
                "json_pointer": pointer,
                "authority_kind": source[0],
                "authority_pointer": source[1],
                "field_content_hash": _integrity_hash(leaves[pointer]),
            }
        )
    return rows


def _evidence_reference_target_rows(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    necessary_reference_refs: tuple[str, ...],
    reference_target_by_ref: dict[str, _StructureNode],
) -> list[dict[str, str]]:
    canonical_references = [
        item.source_value_ref
        for item in evidence_bundle.source_values
        if item.value_type == "source_reference"
        and item.source_value_ref in set(necessary_reference_refs)
    ]
    if canonical_references != list(necessary_reference_refs):
        _fail("financial_semantic_context_v2_reference_order_invalid")
    result: list[dict[str, str]] = []
    for source_value_ref in necessary_reference_refs:
        target = reference_target_by_ref.get(source_value_ref)
        if target is None:
            _fail("financial_semantic_context_v2_reference_target_missing")
        if target.structure_key is not None:
            target_kind = "structure_key"
            target_value = target.structure_key
        else:
            target_kind = "location"
            target_value = CONTEXT_V2_LOCATION_BY_KIND.get(target.kind)
            if target_value is None:
                _fail(
                    "financial_semantic_context_v2_reference_target_invalid"
                )
        result.append(
            {
                "source_value_ref": source_value_ref,
                "target_kind": target_kind,
                "target": target_value,
            }
        )
    return result


def _validate_binding_partition(
    *,
    compilation: Gate2FinancialCandidateCompilation,
    choice_key_by_id: dict[str, str],
    visible_relationship_rows: list[dict[str, Any]],
    backend_only_bindings: list[dict[str, str]],
) -> None:
    expected = Counter(
        (
            choice_key_by_id[option.typed_option_id],
            binding.role_id,
            binding.source_value_ref,
        )
        for option in compilation.typed_options
        for binding in option.role_bindings
    )
    visible = Counter(
        (
            item["choice_key"],
            item["role_id"],
            item["source_value_ref"],
        )
        for row in visible_relationship_rows
        for item in row["covered_bindings"]
    )
    backend = Counter(
        (
            item["choice_key"],
            item["role_id"],
            item["source_value_ref"],
        )
        for item in backend_only_bindings
    )
    if visible & backend or visible + backend != expected:
        _fail("financial_semantic_context_v2_binding_partition_invalid")


def _receipt_identities(
    *,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    projection: Gate2FinancialSemanticV2CandidateProjection,
    active_packet_hash: str,
    context_view_hash: str,
) -> dict[str, Any]:
    family = projection.managed_asset_family
    pack = projection.semantic_pack_identity
    catalog = projection.reason_catalog_identity
    return {
        "context_contract_identity": CONTEXT_V2_CONTRACT_IDENTITY,
        "context_contract_version": CONTEXT_V2_CONTRACT_VERSION,
        "active_packet_identity": CONTEXT_V2_ACTIVE_PACKET_IDENTITY,
        "active_packet_hash": active_packet_hash,
        "context_view_hash": context_view_hash,
        "managed_asset_family_identity": family["family_id"],
        "managed_asset_family_version": family["semantic_version"],
        "managed_asset_family_manifest_sha256": (
            family["manifest_sha256"]
        ),
        "registry_identity": registry.registry_id,
        "registry_version": registry.registry_version,
        "registry_hash": registry.registry_hash,
        "semantic_pack_identity": pack["pack_id"],
        "semantic_pack_version": pack["semantic_version"],
        "semantic_pack_integrity_sha256": pack["integrity_sha256"],
        "semantic_pack_projection_identity": (
            CONTEXT_V2_PACK_PROJECTION_IDENTITY
        ),
        "semantic_pack_projection_version": (
            CONTEXT_V2_PACK_PROJECTION_VERSION
        ),
        "semantic_pack_projection_hash": projection.pack_projection_hash,
        "reason_catalog_identity": catalog["catalog_id"],
        "reason_catalog_version": catalog["semantic_version"],
        "reason_catalog_integrity_sha256": catalog["integrity_sha256"],
        "reason_projection_identity": (
            CONTEXT_V2_REASON_PROJECTION_IDENTITY
        ),
        "reason_projection_version": (
            CONTEXT_V2_REASON_PROJECTION_VERSION
        ),
        "reason_projection_hash": projection.reason_projection_hash,
        "decision_code_contract_identity": (
            projection.decision_code_view["identity"]
        ),
        "decision_code_contract_hash": (
            projection.decision_code_contract_hash
        ),
    }


def _mapping_receipt_payload_without_integrity(
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
) -> dict[str, Any]:
    return {
        "schema_version": receipt.schema_version,
        "policy_version": receipt.policy_version,
        "identities": copy.deepcopy(receipt.identities),
        "scope": copy.deepcopy(receipt.scope),
        "visible_field_sources": [
            copy.deepcopy(item)
            for item in receipt.visible_field_sources
        ],
        "local_mappings": copy.deepcopy(receipt.local_mappings),
        "binding_partition": copy.deepcopy(receipt.binding_partition),
        "presentation_order": copy.deepcopy(receipt.presentation_order),
        "provider_calls_total": receipt.provider_calls_total,
    }


def validate_financial_semantic_context_v2_material(
    *,
    candidate: Gate2FinancialSemanticV6ContextV2Candidate,
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    projection: Gate2FinancialSemanticV2CandidateProjection,
    active_payload: dict[str, Any],
    active_packet_hash: str,
) -> None:
    if (
        not isinstance(
            candidate,
            Gate2FinancialSemanticV6ContextV2Candidate,
        )
        or not isinstance(
            receipt,
            Gate2FinancialSemanticV6ContextV2MappingReceipt,
        )
        or candidate.schema_version
        != CONTEXT_V2_CANDIDATE_SCHEMA_VERSION
        or candidate.policy_version != CONTEXT_V2_POLICY_VERSION
        or candidate.active is not False
        or candidate.provider_calls_total != 0
        or receipt.schema_version
        != CONTEXT_V2_MAPPING_RECEIPT_SCHEMA_VERSION
        or receipt.policy_version != CONTEXT_V2_POLICY_VERSION
        or receipt.provider_calls_total != 0
    ):
        _fail("financial_semantic_context_v2_material_invalid")
    expected_blocks = (
        CONTEXT_V2_BLOCKS_WITH_SHARED
        if candidate.payload.get("shared_relationships")
        else CONTEXT_V2_BLOCKS
    )
    if tuple(candidate.payload) != expected_blocks:
        _fail("financial_semantic_context_v2_shape_invalid")
    if _contains_none(candidate.payload):
        _fail("financial_semantic_context_v2_null_field_forbidden")
    if (
        candidate.view_hash != _model_hash(candidate.payload)
        or candidate.model_visible_utf8_bytes
        != len(_model_json_bytes(candidate.payload))
        or active_packet_hash != _integrity_hash(active_payload)
    ):
        _fail("financial_semantic_context_v2_hash_invalid")
    receipt_payload = _mapping_receipt_payload_without_integrity(receipt)
    if receipt.integrity_hash != _integrity_hash(receipt_payload):
        _fail("financial_semantic_context_v2_receipt_integrity_invalid")
    expected_identities = _receipt_identities(
        registry=registry,
        projection=projection,
        active_packet_hash=active_packet_hash,
        context_view_hash=candidate.view_hash,
    )
    if receipt.identities != expected_identities:
        _fail("financial_semantic_context_v2_identity_invalid")
    _validate_scope(
        receipt=receipt,
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        registry=registry,
        projection=projection,
    )
    expected_candidate, expected_receipt = (
        _derive_context_v2_candidate_and_receipt(
            evidence_bundle=evidence_bundle,
            compilation=compilation,
            registry=registry,
            projection=projection,
            active_payload=active_payload,
            active_packet_hash=active_packet_hash,
        )
    )
    if candidate != expected_candidate:
        _fail("financial_semantic_context_v2_candidate_material_invalid")
    if receipt != expected_receipt:
        _fail("financial_semantic_context_v2_receipt_material_invalid")
    _validate_visible_field_sources(
        candidate=candidate,
        receipt=receipt,
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        projection=projection,
        active_payload=active_payload,
    )
    _validate_local_mappings(
        candidate=candidate,
        receipt=receipt,
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        projection=projection,
    )
    choice_key_by_id = {
        row["typed_option_id"]: row["choice_key"]
        for row in receipt.local_mappings["choice_keys"]
    }
    _validate_binding_partition(
        compilation=compilation,
        choice_key_by_id=choice_key_by_id,
        visible_relationship_rows=receipt.binding_partition[
            "visible_relationships"
        ],
        backend_only_bindings=receipt.binding_partition[
            "backend_only_bindings"
        ],
    )
    _validate_presentation_order(
        candidate=candidate,
        receipt=receipt,
    )
    _validate_literal_occurrence_coverage(
        candidate=candidate,
        receipt=receipt,
        evidence_bundle=evidence_bundle,
    )


def _validate_literal_occurrence_coverage(
    *,
    candidate: Gate2FinancialSemanticV6ContextV2Candidate,
    receipt: Gate2FinancialSemanticV6ContextV2MappingReceipt,
    evidence_bundle: Gate2FinancialEvidenceBundle,
) -> None:
    expected_by_authority_pointer = {
        f"/source_values/{index}/literal_value": item.literal_value
        for index, item in enumerate(evidence_bundle.source_values)
        if item.value_type != "source_reference"
    }
    field_source_by_pointer = {
        item["json_pointer"]: item
        for item in receipt.visible_field_sources
    }
    observed_by_authority_pointer: dict[str, Any] = {}
    for pointer, literal in _primitive_leaf_entries(
        candidate.payload["source"],
        pointer="/source",
    ):
        if pointer.rsplit("/", 1)[-1] != "literal":
            continue
        field_source = field_source_by_pointer.get(pointer)
        if (
            not isinstance(field_source, dict)
            or field_source.get("authority_kind") != "evidence_bundle"
            or not isinstance(field_source.get("authority_pointer"), str)
            or field_source["authority_pointer"]
            in observed_by_authority_pointer
        ):
            _fail("financial_semantic_context_v2_literal_coverage_invalid")
        observed_by_authority_pointer[
            field_source["authority_pointer"]
        ] = literal
    if observed_by_authority_pointer != expected_by_authority_pointer:
        _fail("financial_semantic_context_v2_literal_coverage_invalid")


def _render_choices(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    projection: Gate2FinancialSemanticV2CandidateProjection,
    type_key_by_id: dict[str, str],
    choice_key_by_id: dict[str, str],
    local_by_choice: dict[str, list[_RelationshipGroup]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, tuple[str, str]],
    list[dict[str, str]],
    list[dict[str, Any]],
]:
    source_by_ref = {
        item.source_value_ref: item
        for item in evidence_bundle.source_values
    }
    card_index_by_id = {
        item["input_type_id"]: index
        for index, item in enumerate(
            projection.pack_projection["type_cards"]
        )
    }
    field_sources: dict[str, tuple[str, str]] = {}
    mappings: list[dict[str, str]] = []
    relationship_rows: list[dict[str, Any]] = []
    choices: list[dict[str, Any]] = []
    for choice_index, option in enumerate(compilation.typed_options):
        choice_key = choice_key_by_id[option.typed_option_id]
        type_key = type_key_by_id.get(option.input_type_id)
        card_index = card_index_by_id.get(option.input_type_id)
        if type_key is None or card_index is None:
            _fail("financial_semantic_context_v2_choice_type_invalid")
        card = projection.pack_projection["type_cards"][card_index]
        pointer = f"/choices/{choice_index}"
        option_pointer = f"/typed_options/{choice_index}"
        choice: dict[str, Any] = {
            "choice_key": choice_key,
            "label": card["title"],
            "type_key": type_key,
        }
        field_sources[pointer + "/choice_key"] = (
            "candidate_compilation",
            option_pointer + "/typed_option_id",
        )
        field_sources[pointer + "/label"] = (
            "semantic_pack_projection",
            f"/type_cards/{card_index}/title",
        )
        field_sources[pointer + "/type_key"] = (
            "candidate_compilation",
            option_pointer + "/input_type_id",
        )
        groups = local_by_choice.get(choice_key, [])
        if groups:
            rendered_relationships: list[dict[str, Any]] = []
            for relationship_index, group in enumerate(groups):
                relationship_pointer = (
                    pointer + f"/relationships/{relationship_index}"
                )
                rendered_relationships.append(
                    copy.deepcopy(group.relationship)
                )
                field_sources.update(
                    _relationship_field_sources(
                        group=group,
                        output_pointer=relationship_pointer,
                        shared=False,
                    )
                )
                relationship_rows.append(
                    _relationship_receipt_row(
                        group=group,
                        json_pointer=relationship_pointer,
                        sharing="choice_specific",
                    )
                )
            choice["relationships"] = rendered_relationships
        association_refs = {
            source_by_ref[binding.source_value_ref].association_ref
            for binding in option.role_bindings
            if binding.source_value_ref in source_by_ref
        }
        if len(association_refs) != 1:
            _fail("financial_semantic_context_v2_choice_association_invalid")
        choices.append(choice)
        mappings.append(
            {
                "choice_key": choice_key,
                "json_pointer": pointer,
                "typed_option_id": option.typed_option_id,
                "association_ref": next(iter(association_refs)),
                "type_key": type_key,
            }
        )
    if not choices:
        field_sources["/choices"] = (
            "candidate_compilation",
            "/typed_options",
        )
    return choices, field_sources, mappings, relationship_rows


def _render_shared_relationships(
    shared: list[_RelationshipGroup],
) -> tuple[
    list[dict[str, Any]],
    dict[str, tuple[str, str]],
    list[dict[str, Any]],
]:
    payload: list[dict[str, Any]] = []
    field_sources: dict[str, tuple[str, str]] = {}
    rows: list[dict[str, Any]] = []
    for index, group in enumerate(shared):
        pointer = f"/shared_relationships/{index}"
        payload.append(copy.deepcopy(group.relationship))
        field_sources.update(
            _relationship_field_sources(
                group=group,
                output_pointer=pointer,
                shared=True,
            )
        )
        rows.append(
            _relationship_receipt_row(
                group=group,
                json_pointer=pointer,
                sharing="shared",
            )
        )
    return payload, field_sources, rows


def _relationship_field_sources(
    *,
    group: _RelationshipGroup,
    output_pointer: str,
    shared: bool,
) -> dict[str, tuple[str, str]]:
    if not group.occurrences:
        _fail("financial_semantic_context_v2_relationship_invalid")
    first = group.occurrences[0]
    authority_base = (
        "/typed_options"
        if shared
        else (
            f"/typed_options/{first.choice_index}"
            f"/role_bindings/{first.binding_index}"
        )
    )
    result = {
        output_pointer + "/role": (
            "candidate_compilation",
            authority_base
            if shared
            else authority_base + "/role_id",
        ),
        output_pointer + "/" + first.target_kind: (
            "candidate_compilation",
            authority_base
            if shared
            else authority_base + "/source_value_ref",
        ),
    }
    if "applies_to" in group.relationship:
        for index in range(len(group.relationship["applies_to"])):
            result[
                output_pointer + f"/applies_to/{index}"
            ] = (
                "candidate_compilation",
                "/typed_options",
            )
    return result


def _relationship_receipt_row(
    *,
    group: _RelationshipGroup,
    json_pointer: str,
    sharing: str,
) -> dict[str, Any]:
    return {
        "json_pointer": json_pointer,
        "classification": _relationship_classification(group),
        "sharing": sharing,
        "covered_bindings": [
            {
                "choice_key": occurrence.choice_key,
                "role_id": occurrence.role_id,
                "source_value_ref": occurrence.source_value_ref,
            }
            for occurrence in group.occurrences
        ],
    }


def _relationship_classification(
    group: _RelationshipGroup,
) -> str:
    values = {
        occurrence.classification
        for occurrence in group.occurrences
    }
    if len(values) != 1:
        _fail("financial_semantic_context_v2_relationship_class_invalid")
    value = next(iter(values))
    if value not in {"semantic_value", "evidence_predicate"}:
        _fail("financial_semantic_context_v2_relationship_class_invalid")
    return value


def _render_reason_cards(
    projection: Gate2FinancialSemanticV2CandidateProjection,
) -> tuple[
    list[dict[str, Any]],
    dict[str, tuple[str, str]],
]:
    reasons = projection.reason_projection["reasons"]
    field_sources: dict[str, tuple[str, str]] = {}
    payload: list[dict[str, Any]] = []
    for reason_index, reason in enumerate(reasons):
        pointer = f"/unclassified_reasons/{reason_index}"
        source_pointer = f"/reasons/{reason_index}"
        card = {
            "code": reason["code"],
            "title": reason["human_title"],
            "meaning": reason["meaning"],
            "use_when": reason["use_when"],
            "do_not_use_when": reason["do_not_use_when"],
            "contrasts": [
                {
                    "against_reason_code": item["reason_code"],
                    "distinction": item["distinction"],
                }
                for item in reason[
                    "contrast_with_neighbouring_reasons"
                ]
            ],
        }
        for output_field, source_field in (
            ("code", "code"),
            ("title", "human_title"),
            ("meaning", "meaning"),
            ("use_when", "use_when"),
            ("do_not_use_when", "do_not_use_when"),
        ):
            field_sources[pointer + "/" + output_field] = (
                "reason_catalog_projection",
                source_pointer + "/" + source_field,
            )
        for contrast_index in range(len(card["contrasts"])):
            output_base = pointer + f"/contrasts/{contrast_index}"
            source_base = (
                source_pointer
                + "/contrast_with_neighbouring_reasons/"
                + str(contrast_index)
            )
            field_sources[
                output_base + "/against_reason_code"
            ] = (
                "reason_catalog_projection",
                source_base + "/reason_code",
            )
            field_sources[output_base + "/distinction"] = (
                "reason_catalog_projection",
                source_base + "/distinction",
            )
        payload.append(card)
    expected_codes = projection.decision_code_view.get(
        "unclassified_reason_codes"
    )
    if (
        not isinstance(expected_codes, list)
        or set(item["code"] for item in payload) != set(expected_codes)
        or len(payload) != len(expected_codes)
    ):
        _fail("financial_semantic_context_v2_reason_code_parity_invalid")
    contrasts_by_code = {
        item["code"]: {
            contrast["against_reason_code"]
            for contrast in item["contrasts"]
        }
        for item in payload
    }
    for code in expected_codes:
        if contrasts_by_code.get(code) != set(expected_codes) - {code}:
            _fail(
                "financial_semantic_context_v2_reason_contrast_invalid"
            )
    return payload, field_sources


def _render_type_cards(
    *,
    projection: Gate2FinancialSemanticV2CandidateProjection,
    type_set_snapshot: dict[str, Any],
    type_key_by_id: dict[str, str],
    guard: _ReadableCollisionGuard,
) -> tuple[
    list[dict[str, Any]],
    dict[str, tuple[str, str]],
    list[dict[str, str]],
]:
    cards = projection.pack_projection["type_cards"]
    available_type_ids = type_set_snapshot["available_type_ids"]
    if [item["input_type_id"] for item in cards] != available_type_ids:
        _fail("financial_semantic_context_v2_type_set_invalid")
    field_sources: dict[str, tuple[str, str]] = {}
    mappings: list[dict[str, str]] = []
    rendered_cards: list[dict[str, Any]] = []
    direct_contrasts: set[tuple[str, str]] = set()
    for card_index, card in enumerate(cards):
        input_type_id = card["input_type_id"]
        type_key = type_key_by_id[input_type_id]
        pointer = f"/type_cards/{card_index}"
        pack_pointer = f"/type_cards/{card_index}"
        rendered: dict[str, Any] = {
            "type_key": type_key,
            "title": card["title"],
            "meaning": card["definition"],
            "semantic_class": card["semantic_class"],
        }
        field_sources[pointer + "/type_key"] = (
            "type_set_snapshot",
            f"/available_type_ids/{card_index}",
        )
        field_sources[pointer + "/title"] = (
            "semantic_pack_projection",
            pack_pointer + "/title",
        )
        field_sources[pointer + "/meaning"] = (
            "semantic_pack_projection",
            pack_pointer + "/definition",
        )
        field_sources[pointer + "/semantic_class"] = (
            "semantic_pack_projection",
            pack_pointer + "/semantic_class",
        )
        roles = card["roles"]
        required = _render_evidence_requirements(
            roles=roles["required"],
            output_pointer=pointer + "/required_evidence",
            authority_pointer=pack_pointer + "/roles/required",
            field_sources=field_sources,
            guard=guard,
        )
        if not required:
            _fail("financial_semantic_context_v2_required_evidence_empty")
        rendered["required_evidence"] = required
        optional = _render_evidence_requirements(
            roles=roles["optional"],
            output_pointer=pointer + "/optional_evidence",
            authority_pointer=pack_pointer + "/roles/optional",
            field_sources=field_sources,
            guard=guard,
        )
        if optional:
            rendered["optional_evidence"] = optional
        conditional: list[str] = []
        for output_index, exact_field in enumerate(
            (
                "date_period_requirement",
                "currency_unit_requirement",
            )
        ):
            exact = card[exact_field]
            readable = _context_v2_readable_identifier(
                exact,
                namespace="conditional_requirement",
                guard=guard,
            )
            conditional.append(readable)
            field_sources[
                pointer
                + f"/conditional_requirements/{output_index}"
            ] = (
                "semantic_pack_projection",
                pack_pointer + "/" + exact_field,
            )
        rendered["conditional_requirements"] = conditional
        forbidden: list[str] = []
        for role_index, role_id in enumerate(roles["forbidden"]):
            forbidden.append(
                _context_v2_readable_identifier(
                    role_id,
                    namespace="role",
                    guard=guard,
                )
            )
            field_sources[
                pointer + f"/forbidden_evidence/{role_index}"
            ] = (
                "semantic_pack_projection",
                pack_pointer + f"/roles/forbidden/{role_index}",
            )
        if forbidden:
            rendered["forbidden_evidence"] = forbidden
        rendered["synonyms"] = list(card["synonyms"])
        for index in range(len(card["synonyms"])):
            field_sources[pointer + f"/synonyms/{index}"] = (
                "semantic_pack_projection",
                pack_pointer + f"/synonyms/{index}",
            )
        distinctions: list[dict[str, str]] = []
        for distinction_index, distinction in enumerate(
            card["semantic_distinctions"]
        ):
            against = distinction["against"]
            distinction_pointer = (
                pack_pointer
                + f"/semantic_distinctions/{distinction_index}"
            )
            if against in type_key_by_id:
                target_field = "against_type_key"
                target = type_key_by_id[against]
                direct_contrasts.add((input_type_id, against))
            else:
                target_field = "against_concept"
                target = _readable_external_concept(
                    against,
                    guard=guard,
                )
            output = {
                target_field: target,
                "rule": distinction["rule"],
            }
            distinctions.append(output)
            field_sources[
                pointer
                + f"/distinctions/{distinction_index}/{target_field}"
            ] = (
                "semantic_pack_projection",
                distinction_pointer + "/against",
            )
            field_sources[
                pointer
                + f"/distinctions/{distinction_index}/rule"
            ] = (
                "semantic_pack_projection",
                distinction_pointer + "/rule",
            )
        rendered["distinctions"] = distinctions
        for output_field, source_field in (
            ("examples", "examples"),
            ("counterexamples", "counterexamples"),
            ("unclassified_when", "ambiguity_guidance"),
        ):
            values = list(card[source_field])
            if not values:
                _fail("financial_semantic_context_v2_type_card_invalid")
            rendered[output_field] = values
            for index in range(len(values)):
                field_sources[pointer + f"/{output_field}/{index}"] = (
                    "semantic_pack_projection",
                    pack_pointer + f"/{source_field}/{index}",
                )
        rendered["model_guidance"] = card["model_guidance"]
        field_sources[pointer + "/model_guidance"] = (
            "semantic_pack_projection",
            pack_pointer + "/model_guidance",
        )
        rendered_cards.append(rendered)
        mappings.append(
            {
                "type_key": type_key,
                "json_pointer": pointer,
                "input_type_id": input_type_id,
            }
        )
    if not rendered_cards:
        field_sources["/type_cards"] = (
            "type_set_snapshot",
            "/available_type_ids",
        )
    for index, left in enumerate(available_type_ids):
        for right in available_type_ids[index + 1 :]:
            if (
                (left, right) not in direct_contrasts
                and (right, left) not in direct_contrasts
            ):
                _fail(
                    "financial_semantic_context_v2_direct_contrast_missing"
                )
    return rendered_cards, field_sources, mappings


def _render_evidence_requirements(
    *,
    roles: list[dict[str, Any]],
    output_pointer: str,
    authority_pointer: str,
    field_sources: dict[str, tuple[str, str]],
    guard: _ReadableCollisionGuard,
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for role_index, role in enumerate(roles):
        role_pointer = f"{authority_pointer}/{role_index}"
        pointer = f"{output_pointer}/{role_index}"
        readable_role = _readable_role(
            role["role_id"],
            source_reference=(
                role["value_type"] == "source_reference"
            ),
            guard=guard,
        )
        readable_type = _readable_value_type(
            role["value_type"],
            guard=guard,
        )
        readable_cardinality = _context_v2_readable_identifier(
            role["cardinality"],
            namespace="cardinality",
            guard=guard,
        )
        result.append(
            {
                "role": readable_role,
                "value_type": readable_type,
                "cardinality": readable_cardinality,
            }
        )
        for output_field, source_field in (
            ("role", "role_id"),
            ("value_type", "value_type"),
            ("cardinality", "cardinality"),
        ):
            field_sources[pointer + "/" + output_field] = (
                "semantic_pack_projection",
                role_pointer + "/" + source_field,
            )
    return result


def _context_v2_readable_identifier(
    exact: str,
    *,
    namespace: str,
    guard: _ReadableCollisionGuard,
) -> str:
    rendered = _separator_words(exact)
    guard.add(namespace=namespace, exact=exact, rendered=rendered)
    return rendered


def _readable_external_concept(
    exact: str,
    *,
    guard: _ReadableCollisionGuard,
) -> str:
    without_version = _VERSION_SUFFIX_RE.sub("", exact)
    rendered = _separator_words(without_version)
    guard.add(
        namespace="external_distinction_target",
        exact=exact,
        rendered=rendered,
    )
    return rendered


def _render_source(
    top_nodes: list[_StructureNode],
) -> tuple[
    dict[str, Any],
    dict[str, tuple[str, str]],
    list[dict[str, str]],
    list[dict[str, Any]],
]:
    if not top_nodes:
        _fail("financial_semantic_context_v2_visible_hierarchy_empty")
    field_sources: dict[str, tuple[str, str]] = {}
    value_mappings: list[dict[str, str]] = []
    structure_mappings: list[dict[str, Any]] = []

    def render_value(
        value: _ValueNode,
        pointer: str,
    ) -> dict[str, Any]:
        value.json_pointer = pointer
        source_base = f"/source_values/{value.source_index}"
        result: dict[str, Any] = {}
        if value.value_key is not None:
            result["value_key"] = value.value_key
            field_sources[pointer + "/value_key"] = (
                "evidence_bundle",
                source_base + "/source_value_ref",
            )
            value_mappings.append(
                {
                    "value_key": value.value_key,
                    "json_pointer": pointer,
                    "source_value_ref": value.source.source_value_ref,
                }
            )
        result["meaning"] = value.meaning
        field_sources[pointer + "/meaning"] = (
            "evidence_bundle",
            value.meaning_authority_pointer,
        )
        result["literal"] = value.source.literal_value
        field_sources[pointer + "/literal"] = (
            "evidence_bundle",
            source_base + "/literal_value",
        )
        result["value_type"] = value.value_type
        field_sources[pointer + "/value_type"] = (
            "evidence_bundle",
            source_base + "/value_type",
        )
        if value.label is not None:
            result["label"] = value.label
            field_sources[pointer + "/label"] = (
                "evidence_bundle",
                source_base + "/visible_context/visible_label",
            )
        return result

    def render_node(
        node: _StructureNode,
        pointer: str,
    ) -> dict[str, Any]:
        node.json_pointer = pointer
        source_base = f"/source_values/{node.source_index}"
        result: dict[str, Any] = {}
        if node.structure_key is not None:
            result["structure_key"] = node.structure_key
            field_sources[pointer + "/structure_key"] = (
                "evidence_bundle",
                source_base,
            )
            structure_mappings.append(
                {
                    "structure_key": node.structure_key,
                    "json_pointer": pointer,
                    "node_identity": copy.deepcopy(node.node_identity),
                }
            )
        result["kind"] = CONTEXT_V2_MODEL_KIND[node.kind]
        if node.kind == "table":
            kind_pointer = source_base + "/lineage/table_ref"
        elif node.kind == "evidence_group":
            kind_pointer = source_base
        else:
            kind_pointer = source_base + "/association_kind"
        field_sources[pointer + "/kind"] = (
            "evidence_bundle",
            kind_pointer,
        )
        if node.kind == "table":
            if not node.children:
                _fail("financial_semantic_context_v2_source_structure_invalid")
            result["children"] = [
                render_node(
                    child,
                    pointer + f"/children/{index}",
                )
                for index, child in enumerate(node.children)
            ]
        elif node.kind in {"row", "text_segment"}:
            if node.section_role is not None:
                result["section_role"] = node.section_role
                field_sources[pointer + "/section_role"] = (
                    "evidence_bundle",
                    source_base + "/visible_context/section_role",
                )
            if node.row_role is not None:
                result["row_role"] = node.row_role
                field_sources[pointer + "/row_role"] = (
                    "evidence_bundle",
                    source_base + "/visible_context/row_role",
                )
            if not node.values:
                _fail("financial_semantic_context_v2_source_structure_invalid")
            result["values"] = [
                render_value(
                    value,
                    pointer + f"/values/{index}",
                )
                for index, value in enumerate(node.values)
            ]
        elif node.kind != "evidence_group":
            _fail("financial_semantic_context_v2_source_structure_invalid")
        return result

    children = [
        render_node(node, f"/source/document/children/{index}")
        for index, node in enumerate(top_nodes)
    ]
    return (
        {"document": {"children": children}},
        field_sources,
        value_mappings,
        structure_mappings,
    )



def _bind_occurrence_targets(
    *,
    occurrences: list[_BindingOccurrence],
    values_by_ref: dict[str, _ValueNode],
    reference_target_by_ref: dict[str, _StructureNode],
) -> None:
    for occurrence in occurrences:
        if occurrence.classification == "semantic_value":
            target = values_by_ref.get(occurrence.source_value_ref)
            if target is None:
                _fail("financial_semantic_context_v2_binding_target_invalid")
            occurrence.target_object = target
            occurrence.target_kind = "value_key"
        elif occurrence.classification == "evidence_predicate":
            target = reference_target_by_ref.get(
                occurrence.source_value_ref
            )
            if target is None:
                _fail("financial_semantic_context_v2_reference_target_missing")
            occurrence.target_object = target
        else:
            _fail("financial_semantic_context_v2_binding_class_invalid")


def _assign_local_source_keys(
    *,
    top_nodes: list[_StructureNode],
    occurrences: list[_BindingOccurrence],
) -> None:
    nodes = list(_walk_structure_nodes(top_nodes))
    if not nodes:
        _fail("financial_semantic_context_v2_visible_hierarchy_empty")
    kind_counts = Counter(item.kind for item in nodes)
    inbound_node_ids = {
        id(occurrence.target_object)
        for occurrence in occurrences
        if isinstance(occurrence.target_object, _StructureNode)
    }
    inbound_value_ids = {
        id(occurrence.target_object)
        for occurrence in occurrences
        if isinstance(occurrence.target_object, _ValueNode)
    }
    structure_ordinal = 0
    value_ordinal = 0
    for node in nodes:
        if (
            id(node) in inbound_node_ids
            and kind_counts[node.kind] != 1
        ):
            structure_ordinal += 1
            node.structure_key = f"structure_{structure_ordinal}"
        for value in node.values:
            if id(value) in inbound_value_ids:
                value_ordinal += 1
                value.value_key = f"value_{value_ordinal}"


def _finish_occurrence_targets(
    occurrences: list[_BindingOccurrence],
) -> None:
    node_kind_counts = Counter(
        target.kind
        for target in {
            id(item.target_object): item.target_object
            for item in occurrences
            if isinstance(item.target_object, _StructureNode)
        }.values()
    )
    for occurrence in occurrences:
        target = occurrence.target_object
        if isinstance(target, _ValueNode):
            if target.value_key is None:
                _fail("financial_semantic_context_v2_value_key_missing")
            occurrence.target_kind = "value_key"
            occurrence.target = target.value_key
        elif isinstance(target, _StructureNode):
            if target.structure_key is not None:
                occurrence.target_kind = "structure_key"
                occurrence.target = target.structure_key
            else:
                location = CONTEXT_V2_LOCATION_BY_KIND.get(target.kind)
                if location is None or node_kind_counts[target.kind] != 1:
                    _fail(
                        "financial_semantic_context_v2_structure_key_missing"
                    )
                occurrence.target_kind = "location"
                occurrence.target = location
        else:
            _fail("financial_semantic_context_v2_binding_target_invalid")


def _factor_relationships(
    *,
    occurrences: list[_BindingOccurrence],
    choices_total: int,
) -> tuple[
    list[_RelationshipGroup],
    dict[str, list[_RelationshipGroup]],
]:
    grouped: dict[tuple[str, str, str], list[_BindingOccurrence]] = {}
    order: list[tuple[str, str, str]] = []
    for occurrence in occurrences:
        if occurrence.target is None:
            _fail("financial_semantic_context_v2_relationship_invalid")
        signature = (
            occurrence.readable_role,
            occurrence.target_kind,
            occurrence.target,
        )
        if signature not in grouped:
            grouped[signature] = []
            order.append(signature)
        grouped[signature].append(occurrence)
    shared: list[_RelationshipGroup] = []
    local_by_choice: dict[str, list[_RelationshipGroup]] = {}
    for signature in order:
        members = grouped[signature]
        choice_keys: list[str] = []
        for member in members:
            if member.choice_key not in choice_keys:
                choice_keys.append(member.choice_key)
        relationship = _relationship_payload(members[0])
        group = _RelationshipGroup(
            relationship=relationship,
            occurrences=members,
        )
        if len(choice_keys) >= 2:
            if len(choice_keys) != choices_total:
                relationship["applies_to"] = choice_keys
            shared.append(group)
        elif len(choice_keys) == 1:
            local_by_choice.setdefault(choice_keys[0], []).append(group)
        else:
            _fail("financial_semantic_context_v2_relationship_invalid")
    return shared, local_by_choice


def _relationship_payload(
    occurrence: _BindingOccurrence,
) -> dict[str, Any]:
    if occurrence.target is None or occurrence.target_kind not in {
        "value_key",
        "structure_key",
        "location",
    }:
        _fail("financial_semantic_context_v2_relationship_invalid")
    return {
        "role": occurrence.readable_role,
        occurrence.target_kind: occurrence.target,
    }


def _walk_structure_nodes(
    top_nodes: list[_StructureNode],
):
    for node in top_nodes:
        yield node
        yield from _walk_structure_nodes(node.children)


def _binding_occurrences(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
    type_cards_by_id: dict[str, dict[str, Any]],
    choice_key_by_id: dict[str, str],
    guard: _ReadableCollisionGuard,
    values_by_ref: dict[str, _ValueNode],
) -> tuple[
    list[_BindingOccurrence],
    list[dict[str, str]],
    tuple[str, ...],
]:
    source_by_ref = {
        item.source_value_ref: item
        for item in evidence_bundle.source_values
    }
    occurrences: list[_BindingOccurrence] = []
    backend_only: list[dict[str, str]] = []
    necessary_reference_set: set[str] = set()
    for choice_index, option in enumerate(compilation.typed_options):
        choice_key = choice_key_by_id.get(option.typed_option_id)
        card = type_cards_by_id.get(option.input_type_id)
        if choice_key is None or not isinstance(card, dict):
            _fail("financial_semantic_context_v2_choice_type_invalid")
        roles = card.get("roles")
        if not isinstance(roles, dict):
            _fail("financial_semantic_context_v2_pack_roles_invalid")
        declared: dict[str, tuple[str, dict[str, Any]]] = {}
        for requirement_kind in ("required", "optional"):
            values = roles.get(requirement_kind)
            if not isinstance(values, list):
                _fail("financial_semantic_context_v2_pack_roles_invalid")
            for role in values:
                if (
                    not isinstance(role, dict)
                    or not isinstance(role.get("role_id"), str)
                    or role["role_id"] in declared
                ):
                    _fail("financial_semantic_context_v2_pack_roles_invalid")
                declared[role["role_id"]] = (requirement_kind, role)
        for binding_index, binding in enumerate(option.role_bindings):
            declaration = declared.get(binding.role_id)
            source = source_by_ref.get(binding.source_value_ref)
            if declaration is None or source is None:
                _fail("financial_semantic_context_v2_binding_invalid")
            requirement_kind, role = declaration
            if role.get("value_type") != source.value_type:
                _fail("financial_semantic_context_v2_binding_type_invalid")
            if source.value_type == "source_reference":
                visible = requirement_kind == "required"
                classification = "evidence_predicate"
                target_object: _ValueNode | _StructureNode | None = None
                target_kind = "pending"
            else:
                visible = True
                classification = "semantic_value"
                target_object = values_by_ref.get(source.source_value_ref)
                target_kind = "value_key"
                if target_object is None:
                    _fail("financial_semantic_context_v2_binding_target_invalid")
            if not visible:
                backend_only.append(
                    {
                        "choice_key": choice_key,
                        "role_id": binding.role_id,
                        "source_value_ref": binding.source_value_ref,
                    }
                )
                continue
            readable_role = _readable_role(
                binding.role_id,
                source_reference=(
                    source.value_type == "source_reference"
                ),
                guard=guard,
            )
            if source.value_type == "source_reference":
                necessary_reference_set.add(source.source_value_ref)
            occurrences.append(
                _BindingOccurrence(
                    choice_index=choice_index,
                    binding_index=binding_index,
                    choice_key=choice_key,
                    role_id=binding.role_id,
                    source_value_ref=binding.source_value_ref,
                    classification=classification,
                    readable_role=readable_role,
                    target_kind=target_kind,
                    target_object=target_object,
                )
            )
    necessary_reference_refs = tuple(
        value.source_value_ref
        for value in evidence_bundle.source_values
        if value.source_value_ref in necessary_reference_set
    )
    return occurrences, backend_only, necessary_reference_refs


def _readable_role(
    role_id: str,
    *,
    source_reference: bool,
    guard: _ReadableCollisionGuard,
) -> str:
    rendered = _separator_words(role_id)
    if source_reference and rendered.endswith(" ref"):
        rendered = rendered[: -len(" ref")]
    guard.add(
        namespace="role",
        exact=role_id,
        rendered=rendered,
    )
    return rendered


def _resolve_necessary_references(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    necessary_reference_refs: tuple[str, ...],
    top_nodes: list[_StructureNode],
    nodes_by_ref: dict[str, list[_StructureNode]],
) -> dict[str, _StructureNode]:
    reference_by_ref = {
        item.source_value_ref: item
        for item in evidence_bundle.source_values
        if item.value_type == "source_reference"
    }
    fallback_by_identity: dict[tuple[Any, ...], _StructureNode] = {}

    def register(node: _StructureNode, *refs: str | None) -> None:
        for exact_ref in refs:
            if exact_ref is None:
                continue
            candidates = nodes_by_ref.setdefault(exact_ref, [])
            if all(item is not node for item in candidates):
                candidates.append(node)

    result: dict[str, _StructureNode] = {}
    for source_value_ref in necessary_reference_refs:
        source = reference_by_ref.get(source_value_ref)
        if source is None:
            _fail("financial_semantic_context_v2_reference_invalid")
        candidates = list(nodes_by_ref.get(source.association_ref, ()))
        for exact_ref in (
            source.lineage.text_segment_ref,
            source.lineage.row_ref,
            source.lineage.table_ref,
        ):
            if exact_ref is None:
                continue
            lineage_candidates = list(nodes_by_ref.get(exact_ref, ()))
            if not candidates:
                candidates = lineage_candidates
                continue
            intersection = [
                item
                for item in candidates
                if any(item is other for other in lineage_candidates)
            ]
            if intersection:
                candidates = intersection
        preferred = [
            item
            for item in candidates
            if item.kind in {"row", "text_segment"}
        ]
        selected: _StructureNode | None = None
        if len(preferred) == 1:
            selected = preferred[0]
        elif len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            identity = (
                source.association_ref,
                source.lineage.page_ref,
                source.lineage.table_ref,
                source.lineage.row_ref,
                source.lineage.text_segment_ref,
            )
            selected = fallback_by_identity.get(identity)
            if selected is None:
                selected = _StructureNode(
                    kind="evidence_group",
                    source_index=next(
                        index
                        for index, value in enumerate(
                            evidence_bundle.source_values
                        )
                        if value is source
                    ),
                    node_identity={
                        "kind": "evidence_group",
                        "association_ref": source.association_ref,
                        "page_ref": source.lineage.page_ref,
                        "table_ref": source.lineage.table_ref,
                        "row_ref": source.lineage.row_ref,
                        "text_segment_ref": (
                            source.lineage.text_segment_ref
                        ),
                    },
                )
                fallback_by_identity[identity] = selected
                top_nodes.append(selected)
                register(
                    selected,
                    source.association_ref,
                    source.lineage.table_ref,
                    source.lineage.row_ref,
                    source.lineage.text_segment_ref,
                )
        result[source_value_ref] = selected
    return result


def _source_graph(
    *,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    guard: _ReadableCollisionGuard,
) -> tuple[
    list[_StructureNode],
    dict[str, _ValueNode],
    dict[str, list[_StructureNode]],
]:
    top_nodes: list[_StructureNode] = []
    values_by_ref: dict[str, _ValueNode] = {}
    nodes_by_ref: dict[str, list[_StructureNode]] = {}
    table_nodes: dict[str, _StructureNode] = {}
    row_nodes: dict[tuple[Any, ...], _StructureNode] = {}
    segment_nodes: dict[tuple[Any, ...], _StructureNode] = {}

    def register(node: _StructureNode, *refs: str | None) -> None:
        for exact_ref in refs:
            if exact_ref is None:
                continue
            candidates = nodes_by_ref.setdefault(exact_ref, [])
            if all(item is not node for item in candidates):
                candidates.append(node)

    for source_index, source in enumerate(evidence_bundle.source_values):
        if source.value_type == "source_reference":
            continue
        if source.source_value_ref in values_by_ref:
            _fail("financial_semantic_context_v2_source_value_duplicate")
        meaning, meaning_pointer = _source_value_meaning(
            source=source,
            source_index=source_index,
            guard=guard,
        )
        rendered_type = _readable_value_type(
            source.value_type,
            guard=guard,
        )
        label = (
            source.visible_label
            if source.visible_label
            and source.visible_label not in {meaning, source.literal_value}
            else None
        )
        value_node = _ValueNode(
            source=source,
            source_index=source_index,
            meaning=meaning,
            meaning_authority_pointer=meaning_pointer,
            value_type=rendered_type,
            label=label,
        )
        values_by_ref[source.source_value_ref] = value_node
        if source.association_kind == "table_row":
            row_key = (
                source.association_ref,
                source.lineage.row_ref,
                source.lineage.table_ref,
                source.section_role,
                source.row_role,
            )
            row = row_nodes.get(row_key)
            if row is None:
                row = _StructureNode(
                    kind="row",
                    source_index=source_index,
                    node_identity={
                        "kind": "row",
                        "association_ref": source.association_ref,
                        "row_ref": source.lineage.row_ref,
                        "table_ref": source.lineage.table_ref,
                        "section_role": source.section_role,
                        "row_role": source.row_role,
                    },
                    section_role=_readable_metadata(
                        source.section_role,
                        namespace="section_role",
                        guard=guard,
                    ),
                    row_role=_readable_metadata(
                        source.row_role,
                        namespace="row_role",
                        guard=guard,
                    ),
                )
                row_nodes[row_key] = row
                if source.lineage.table_ref is not None:
                    table = table_nodes.get(source.lineage.table_ref)
                    if table is None:
                        table = _StructureNode(
                            kind="table",
                            source_index=source_index,
                            node_identity={
                                "kind": "table",
                                "table_ref": source.lineage.table_ref,
                            },
                        )
                        table_nodes[source.lineage.table_ref] = table
                        top_nodes.append(table)
                        register(table, source.lineage.table_ref)
                    table.children.append(row)
                else:
                    top_nodes.append(row)
                register(
                    row,
                    source.association_ref,
                    source.lineage.table_ref,
                    source.lineage.row_ref,
                )
            row.values.append(value_node)
        elif source.association_kind == "text_segment":
            segment_key = (
                source.association_ref,
                source.lineage.text_segment_ref,
                source.section_role,
                source.row_role,
            )
            segment = segment_nodes.get(segment_key)
            if segment is None:
                segment = _StructureNode(
                    kind="text_segment",
                    source_index=source_index,
                    node_identity={
                        "kind": "text_segment",
                        "association_ref": source.association_ref,
                        "text_segment_ref": (
                            source.lineage.text_segment_ref
                        ),
                        "section_role": source.section_role,
                        "row_role": source.row_role,
                    },
                    section_role=_readable_metadata(
                        source.section_role,
                        namespace="section_role",
                        guard=guard,
                    ),
                    row_role=_readable_metadata(
                        source.row_role,
                        namespace="row_role",
                        guard=guard,
                    ),
                )
                segment_nodes[segment_key] = segment
                top_nodes.append(segment)
                register(
                    segment,
                    source.association_ref,
                    source.lineage.text_segment_ref,
                )
            segment.values.append(value_node)
        else:
            _fail("financial_semantic_context_v2_source_structure_invalid")
    return top_nodes, values_by_ref, nodes_by_ref


def _source_value_meaning(
    *,
    source: FinancialEvidenceBundleSourceValue,
    source_index: int,
    guard: _ReadableCollisionGuard,
) -> tuple[str, str]:
    base = f"/source_values/{source_index}"
    candidates: list[tuple[str | None, str]] = []
    rendered_column = _readable_metadata(
        source.column_meaning,
        namespace="column_meaning",
        guard=guard,
    )
    candidates.append(
        (
            rendered_column,
            base + "/visible_context/column_meaning",
        )
    )
    candidates.append(
        (
            source.visible_label,
            base + "/visible_context/visible_label",
        )
    )
    candidates.append(
        (
            _readable_value_type(source.value_type, guard=guard),
            base + "/value_type",
        )
    )
    for candidate, pointer in candidates:
        if candidate and candidate != source.literal_value:
            return candidate, pointer
    _fail("financial_semantic_context_v2_meaning_unavailable")


def _readable_metadata(
    value: str | None,
    *,
    namespace: str,
    guard: _ReadableCollisionGuard,
) -> str | None:
    if value is None:
        return None
    if _MACHINE_IDENTIFIER_RE.fullmatch(value):
        rendered = _separator_words(value)
        guard.add(namespace=namespace, exact=value, rendered=rendered)
        return rendered
    return value


def _readable_value_type(
    value: str,
    *,
    guard: _ReadableCollisionGuard,
) -> str:
    exact = value
    if value.startswith("source_"):
        value = value[len("source_") :]
    rendered = _separator_words(value)
    guard.add(namespace="value_type", exact=exact, rendered=rendered)
    return rendered


def _separator_words(value: str) -> str:
    return re.sub(r"[_-]+", " ", value)
