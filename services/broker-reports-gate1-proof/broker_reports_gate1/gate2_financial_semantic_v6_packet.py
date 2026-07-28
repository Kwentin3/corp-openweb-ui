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
SLIM_VIEW_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_slim_view_candidate_v1"
)
SLIM_VIEW_POLICY_VERSION = (
    "broker_reports_gate2_llm_semantic_context_transition_v1"
)
SLIM_ALIAS_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_slim_alias_receipt_v1"
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
    "model-facing semantic-packet and non-active Slim candidate "
    "construction entrypoint"
)
FORBIDDEN = (
    "The active packet must contain exactly four model-visible blocks; a "
    "non-active Slim candidate must stay inside the same factory and must "
    "not expose source or type global IDs, Pack administration, runtime "
    "identities, repository paths, provider metadata, internal audit, "
    "provenance graphs, expected answers or duplicated semantic instructions"
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
    for index, option in enumerate(compilation.typed_options):
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
                "return_id": option.typed_option_id,
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
        or list(receipt.choice_aliases.values())
        != [option.typed_option_id for option in compilation.typed_options]
        or len(choices) != len(compilation.typed_options)
    ):
        _fail("financial_semantic_v6_slim_choice_alias_invalid")
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
    for rendered, option in zip(
        choices,
        compilation.typed_options,
        strict=True,
    ):
        choice_alias = rendered["alias"]
        expected_bindings = [
            f"{binding.role_id}={binding_alias_by_ref[binding.source_value_ref]}"
            for binding in option.role_bindings
        ]
        if (
            rendered["return_id"] != option.typed_option_id
            or rendered["type"] != type_alias_by_id[option.input_type_id]
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
