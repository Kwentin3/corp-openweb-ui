from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_source_context import (
    Gate2FinancialEvidenceSourceContext,
)
from .gate2_financial_semantic_v5_ambiguity import (
    Gate2FinancialSemanticV5AmbiguityGuardFactory,
    Gate2FinancialSemanticV5AmbiguityResult,
    Gate2StructuralBindingCandidate,
)
from .gate2_financial_semantic_v5_preclose import (
    Gate2TechnicalPrecloseResult,
)
from .gate2_financial_semantic_v5_projection import (
    Gate2FinancialSemanticV5Projection,
)


V5_DECISION_PACKET_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_decision_packet_v5"
)
V5_DECISION_PACKET_BLOCKS = (
    "task",
    "source_fragment",
    "available_types",
    "binding_options",
)
V5_TASK_OPERATION = "classify_financial_evidence"
V5_TASK_DECISION_RULE = "managed_prompt_only"
V5_FORBIDDEN_PACKET_FIELDS = frozenset(
    {
        "audit",
        "document_id",
        "document_ref",
        "expected_answer",
        "file_id",
        "filename",
        "gate3_methodology",
        "internal_audit",
        "managed_assets",
        "model_id",
        "pack_administration",
        "path",
        "prompt_ref",
        "provider_metadata",
        "provenance",
        "provenance_graph",
        "repository_path",
        "semantic_pack_identity",
        "skill_identity",
        "source_scope_ref",
        "tool_identity",
    }
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5DecisionPacketFactory.create is the only V5 "
    "model-facing decision-packet entrypoint"
)
FORBIDDEN = (
    "The packet must not expose administration, paths, provenance graphs, "
    "expected answers, provider metadata or duplicate semantic guidance, and "
    "the repository-safe renderer must not expose refs or literals"
)


class Gate2FinancialSemanticV5PacketError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV5DecisionPacket:
    schema_version: str
    payload: dict[str, Any]
    packet_hash: str
    source_context_hash: str
    semantic_projection_hash: str
    ambiguity_policy_hash: str
    ambiguity_input_hash: str
    technical_evidence_hash: str


class Gate2FinancialSemanticV5DecisionPacketFactory:
    def create(
        self,
        *,
        source_context: Gate2FinancialEvidenceSourceContext,
        projection: Gate2FinancialSemanticV5Projection,
        ambiguity: Gate2FinancialSemanticV5AmbiguityResult,
        candidates: tuple[Gate2StructuralBindingCandidate, ...],
        preclose: Gate2TechnicalPrecloseResult,
    ) -> Gate2FinancialSemanticV5DecisionPacket:
        _validate_inputs(
            source_context=source_context,
            projection=projection,
            ambiguity=ambiguity,
            candidates=candidates,
            preclose=preclose,
        )
        source_fragment = _source_fragment(
            source_context=source_context,
            candidates=candidates,
        )
        binding_options: dict[str, list[str]] = {}
        for candidate in candidates:
            for role_id in candidate.allowed_roles:
                binding_options.setdefault(role_id, []).append(
                    candidate.source_value_ref
                )
        binding_options = {
            role_id: sorted(set(binding_options[role_id]))
            for role_id in sorted(binding_options)
        }
        payload = {
            "task": {
                "operation": V5_TASK_OPERATION,
                "decision_rule": V5_TASK_DECISION_RULE,
            },
            "source_fragment": source_fragment,
            "available_types": [
                copy.deepcopy(item)
                for item in ambiguity.available_type_cards
            ],
            "binding_options": binding_options,
        }
        _validate_payload(
            payload=payload,
            source_context=source_context,
            candidates=candidates,
            ambiguity=ambiguity,
        )
        return Gate2FinancialSemanticV5DecisionPacket(
            schema_version=V5_DECISION_PACKET_SCHEMA_VERSION,
            payload=copy.deepcopy(payload),
            packet_hash=_sha256_json(payload),
            source_context_hash=source_context.integrity_hash,
            semantic_projection_hash=projection.projection_hash,
            ambiguity_policy_hash=ambiguity.policy_hash,
            ambiguity_input_hash=ambiguity.guard_input_hash,
            technical_evidence_hash=preclose.technical_evidence_hash,
        )


def structural_binding_candidates_from_source_context(
    *,
    source_context: Gate2FinancialEvidenceSourceContext,
    authoritative_selectors: dict[str, str] | None = None,
    model_visible_associations: dict[str, str] | None = None,
) -> tuple[Gate2StructuralBindingCandidate, ...]:
    if not isinstance(
        source_context,
        Gate2FinancialEvidenceSourceContext,
    ):
        _fail("financial_semantic_v5_packet_source_context_invalid")
    selectors = authoritative_selectors or {}
    associations = model_visible_associations or {}
    groups = source_context.provider_groups()
    all_refs = {
        value["source_value_ref"]
        for group in groups
        for value in group["values"]
    }
    if (
        any(
            not isinstance(key, str)
            or key not in all_refs
            or not isinstance(value, str)
            or not value
            for mapping in (selectors, associations)
            for key, value in mapping.items()
        )
        or set(selectors).difference(all_refs)
        or set(associations).difference(all_refs)
    ):
        _fail("financial_semantic_v5_packet_association_invalid")
    result = []
    for group_index, group in enumerate(groups):
        for value in group["values"]:
            ref = value["source_value_ref"]
            result.append(
                Gate2StructuralBindingCandidate(
                    source_value_ref=ref,
                    association_unit_id=f"group:{group_index}",
                    value_type=value["value_type"],
                    allowed_roles=tuple(value["allowed_roles"]),
                    authoritative_selector=selectors.get(ref),
                    model_visible_association=associations.get(ref),
                )
            )
    if len(result) != source_context.source_values_total:
        _fail("financial_semantic_v5_packet_source_coverage_invalid")
    return tuple(result)


def render_financial_semantic_v5_packet_private(
    *,
    packet: Gate2FinancialSemanticV5DecisionPacket,
    available_response_branches: tuple[str, ...],
) -> str:
    _validate_render_inputs(
        packet=packet,
        available_response_branches=available_response_branches,
    )
    sections = [
        ("TASK", packet.payload["task"]),
        ("SOURCE FRAGMENT", packet.payload["source_fragment"]),
        ("TYPE CARDS", packet.payload["available_types"]),
        ("BINDING OPTIONS", packet.payload["binding_options"]),
        ("AVAILABLE RESPONSE BRANCHES", list(available_response_branches)),
    ]
    return "\n\n".join(
        title
        + "\n"
        + json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        for title, value in sections
    )


def render_financial_semantic_v5_packet_safe(
    *,
    packet: Gate2FinancialSemanticV5DecisionPacket,
    available_response_branches: tuple[str, ...],
) -> str:
    _validate_render_inputs(
        packet=packet,
        available_response_branches=available_response_branches,
    )
    fragment = packet.payload["source_fragment"]
    type_counts = Counter(
        item["value_type"] for item in fragment["values"]
    )
    cards = [
        {
            "input_type_id": card["input_type_id"],
            "required_roles": [
                item["role_id"] for item in card["required_roles"]
            ],
            "optional_roles": [
                item["role_id"] for item in card["optional_roles"]
            ],
        }
        for card in packet.payload["available_types"]
    ]
    safe_sections = [
        ("TASK", packet.payload["task"]),
        (
            "SOURCE FRAGMENT",
            {
                "section_role": fragment["section_role"],
                "row_role": fragment["row_role"],
                "values_total": len(fragment["values"]),
                "value_type_counts": {
                    key: type_counts[key] for key in sorted(type_counts)
                },
                "visible_labels_total": len(
                    fragment["visible_labels"]
                ),
                "column_meanings_total": len(
                    fragment["column_meanings"]
                ),
            },
        ),
        ("TYPE CARDS", cards),
        (
            "BINDING OPTIONS",
            {
                role_id: len(refs)
                for role_id, refs in packet.payload[
                    "binding_options"
                ].items()
            },
        ),
        ("AVAILABLE RESPONSE BRANCHES", list(available_response_branches)),
    ]
    return "\n\n".join(
        title
        + "\n"
        + json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        for title, value in safe_sections
    )


def _source_fragment(
    *,
    source_context: Gate2FinancialEvidenceSourceContext,
    candidates: tuple[Gate2StructuralBindingCandidate, ...],
) -> dict[str, Any]:
    groups = source_context.provider_groups()
    by_ref = {item.source_value_ref: item for item in candidates}
    row_roles = sorted(
        {
            group["row_role"]
            for group in groups
            if group["row_role"] is not None
        }
    )
    section_roles = sorted(
        {
            group["section_role"]
            for group in groups
            if group["section_role"] is not None
        }
    )
    if len(row_roles) > 1 or len(section_roles) > 1:
        _fail("financial_semantic_v5_packet_fragment_scope_ambiguous")
    values = []
    visible_labels = []
    column_meanings = []
    for group_index, group in enumerate(groups):
        for value in group["values"]:
            ref = value["source_value_ref"]
            candidate = by_ref.get(ref)
            if (
                candidate is None
                or candidate.association_unit_id != f"group:{group_index}"
                or candidate.value_type != value["value_type"]
                or candidate.allowed_roles
                != tuple(value["allowed_roles"])
            ):
                _fail(
                    "financial_semantic_v5_packet_candidate_context_mismatch"
                )
            values.append(
                {
                    "source_value_ref": ref,
                    "value_type": value["value_type"],
                    "literal_value": value["literal_value"],
                    "association_unit_index": group_index,
                }
            )
            if value["visible_label"] is not None:
                visible_labels.append(
                    {
                        "source_value_ref": ref,
                        "text": value["visible_label"],
                    }
                )
            if value["column_meaning"] is not None:
                column_meanings.append(
                    {
                        "source_value_ref": ref,
                        "text": value["column_meaning"],
                    }
                )
    return {
        "section_role": section_roles[0] if section_roles else None,
        "row_role": row_roles[0] if row_roles else None,
        "visible_labels": visible_labels,
        "column_meanings": column_meanings,
        "values": values,
    }


def _validate_inputs(
    *,
    source_context: Any,
    projection: Any,
    ambiguity: Any,
    candidates: Any,
    preclose: Any,
) -> None:
    if (
        not isinstance(
            source_context,
            Gate2FinancialEvidenceSourceContext,
        )
        or not isinstance(
            projection,
            Gate2FinancialSemanticV5Projection,
        )
        or not isinstance(
            ambiguity,
            Gate2FinancialSemanticV5AmbiguityResult,
        )
        or not isinstance(candidates, tuple)
        or not candidates
        or not isinstance(preclose, Gate2TechnicalPrecloseResult)
        or preclose.status != "model_required"
        or preclose.provider_call_required is not True
        or preclose.canonical_decision is not None
    ):
        _fail("financial_semantic_v5_packet_inputs_invalid")
    expected_ambiguity = (
        Gate2FinancialSemanticV5AmbiguityGuardFactory().create(
            projection=projection,
            candidates=candidates,
        )
    )
    if ambiguity != expected_ambiguity:
        _fail("financial_semantic_v5_packet_ambiguity_mismatch")


def _validate_payload(
    *,
    payload: Any,
    source_context: Gate2FinancialEvidenceSourceContext,
    candidates: tuple[Gate2StructuralBindingCandidate, ...],
    ambiguity: Gate2FinancialSemanticV5AmbiguityResult,
) -> None:
    if not isinstance(payload, dict) or tuple(payload) != (
        V5_DECISION_PACKET_BLOCKS
    ):
        _fail("financial_semantic_v5_packet_blocks_invalid")
    forbidden = {
        key
        for item in _walk_dicts(payload)
        for key in item
        if key in V5_FORBIDDEN_PACKET_FIELDS
    }
    if forbidden:
        _fail("financial_semantic_v5_packet_forbidden_field")
    if payload["task"] != {
        "operation": V5_TASK_OPERATION,
        "decision_rule": V5_TASK_DECISION_RULE,
    }:
        _fail("financial_semantic_v5_packet_task_invalid")
    if payload["available_types"] != [
        copy.deepcopy(item) for item in ambiguity.available_type_cards
    ]:
        _fail("financial_semantic_v5_packet_type_projection_invalid")
    refs = [
        item["source_value_ref"]
        for item in payload["source_fragment"]["values"]
    ]
    expected_refs = [item.source_value_ref for item in candidates]
    binding_refs = {
        ref
        for options in payload["binding_options"].values()
        for ref in options
    }
    if (
        len(refs) != source_context.source_values_total
        or refs != expected_refs
        or len(refs) != len(set(refs))
        or binding_refs != set(expected_refs)
    ):
        _fail("financial_semantic_v5_packet_source_coverage_invalid")
    non_type_blocks = {
        key: value
        for key, value in payload.items()
        if key != "available_types"
    }
    if any(
        key
        in {
            "short_meaning",
            "key_semantic_distinctions",
            "examples",
            "counterexamples",
            "ambiguity_rule",
        }
        for item in _walk_dicts(non_type_blocks)
        for key in item
    ):
        _fail("financial_semantic_v5_packet_duplicate_semantic_guidance")


def _validate_render_inputs(
    *,
    packet: Any,
    available_response_branches: Any,
) -> None:
    if (
        not isinstance(packet, Gate2FinancialSemanticV5DecisionPacket)
        or not isinstance(available_response_branches, tuple)
        or not available_response_branches
        or any(
            not isinstance(item, str) or not item
            for item in available_response_branches
        )
        or len(available_response_branches)
        != len(set(available_response_branches))
    ):
        _fail("financial_semantic_v5_packet_render_input_invalid")


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5PacketError(code)
