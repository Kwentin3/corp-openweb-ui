from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest


LLM_CONTEXT_PACKAGE_SCHEMA_VERSION = "broker_reports_gate2_llm_context_package_v2"
LLM_CONTEXT_PACKAGE_POLICY_VERSION = "gate2_llm_context_compact_projection_v2"

FACTORY_REQUIRED = (
    "Gate2LlmContextPackageFactory.create is the only production LLM context projection entrypoint"
)
FORBIDDEN = (
    "Prompts and provider adapters must not rebuild or widen the compact LLM context package"
)


@dataclass(frozen=True)
class Gate2LlmContextBudget:
    max_source_refs: int = 40
    max_candidates: int = 64
    max_relations: int = 64
    max_context_chars: int = 48000
    max_header_depth: int = 8
    max_neighbor_rows: int = 2


class Gate2LlmContextPackageFactory:
    def __init__(self, budget: Gate2LlmContextBudget | None = None) -> None:
        self.budget = budget or Gate2LlmContextBudget()

    def create(self) -> "Gate2LlmContextPackageBuilder":
        return Gate2LlmContextPackageBuilder(self.budget)


class Gate2LlmContextPackageBuilder:
    def __init__(self, budget: Gate2LlmContextBudget) -> None:
        self.budget = budget

    def build(self, package: dict[str, Any]) -> dict[str, Any]:
        unit = _object(package.get("source_unit"))
        candidate_set = _object(package.get("source_value_candidate_set"))
        relation_set = _object(package.get("candidate_relation_set"))
        profile = _object(package.get("candidate_binding_profile"))
        target_refs = _strings(
            _object(package.get("coverage_expectation")).get("selected_source_refs")
        )
        target_set = set(target_refs)
        candidates = [
            _compact_candidate(item)
            for item in _dict_list(candidate_set.get("candidates"))
            if str(item.get("row_ref") or "") in target_set
        ]
        candidate_ids = {str(item.get("candidate_id") or "") for item in candidates}
        relations = [
            _compact_relation(item)
            for item in _dict_list(relation_set.get("relations"))
            if set(_strings(item.get("candidate_ids"))) <= candidate_ids
        ]
        issues = _material_issues(package, target_set)
        structural = _compact_structure(unit, target_set)
        context = {
            "schema_version": LLM_CONTEXT_PACKAGE_SCHEMA_VERSION,
            "package_policy_version": LLM_CONTEXT_PACKAGE_POLICY_VERSION,
            "identity": {
                "package_id": package.get("package_id"),
                "candidate_set_id": candidate_set.get("candidate_set_id"),
                "candidate_set_hash": candidate_set.get("candidate_set_hash"),
                "relation_set_id": relation_set.get("relation_set_id"),
                "relation_set_hash": relation_set.get("relation_set_hash"),
                "document_ref": package.get("document_ref"),
                "source_unit_ref": unit.get("unit_id"),
            },
            "target_source_refs": target_refs,
            "local_structure": structural,
            "domain_task": {
                "domain": package.get("extractor_domain"),
                "required_roles": _strings(profile.get("required_roles")),
                "required_role_groups": copy.deepcopy(
                    profile.get("required_role_groups") or []
                ),
                "optional_roles": _strings(profile.get("optional_roles")),
                "required_relation_kinds": _strings(
                    profile.get("required_relation_kinds")
                ),
                "role_cardinality": copy.deepcopy(
                    profile.get("role_cardinality") or {}
                ),
                "allowed_subtypes": _strings(profile.get("subtypes")),
                "valid_terminal_decisions": [
                    str(package.get("extractor_domain") or ""),
                    "unknown_source_row",
                    "no_fact",
                ],
                "ownership_policy": "every_target_ref_exactly_once",
            },
            "candidate_evidence": candidates,
            "candidate_relations": relations,
            "material_issues": issues,
            "response_contract": {
                "schema_version": "broker_reports_candidate_binding_output_v0",
                "strict_json_schema": True,
                "select_existing_candidate_ids_only": True,
                "select_existing_relation_ids_only": True,
                "each_semantic_role_at_most_once": True,
                "each_fact_field_path_at_most_once": True,
                "unknown_requires_no_bindings_and_uncertainty_code": True,
                "required_top_level_fields": [
                    "schema_version",
                    "package_id",
                    "candidate_set_id",
                    "candidate_set_hash",
                    "relation_set_id",
                    "relation_set_hash",
                    "binding_results",
                    "no_fact_results",
                ],
            },
        }
        budget = context_budget_metrics(context, self.budget)
        context["budget"] = budget
        context["context_hash"] = stable_digest(context, length=64)
        return context


def package_feasibility(package: dict[str, Any]) -> dict[str, Any]:
    profile = _object(package.get("candidate_binding_profile"))
    candidates = _dict_list(
        _object(package.get("source_value_candidate_set")).get("candidates")
    )
    relations = _dict_list(
        _object(package.get("candidate_relation_set")).get("relations")
    )
    available_roles = sorted(
        {
            role
            for candidate in candidates
            for role in _strings(candidate.get("allowed_semantic_roles"))
        }
    )
    available_relation_kinds = sorted(
        {str(item.get("relation_kind") or "") for item in relations}
    )
    reasons: list[str] = []
    required_roles = _strings(profile.get("required_roles"))
    missing_roles = sorted(set(required_roles) - set(available_roles))
    if missing_roles:
        reasons.append("gate2_package_feasibility_required_roles_unavailable")
    unsatisfied_groups = [
        _strings(group)
        for group in profile.get("required_role_groups") or []
        if isinstance(group, list) and not set(_strings(group)) & set(available_roles)
    ]
    if unsatisfied_groups:
        reasons.append("gate2_package_feasibility_required_role_groups_unavailable")
    missing_relations = sorted(
        set(_strings(profile.get("required_relation_kinds")))
        - set(available_relation_kinds)
    )
    if missing_relations:
        reasons.append("gate2_package_feasibility_required_relations_unavailable")
    unbindable = sorted(
        str(item.get("candidate_id") or "")
        for item in candidates
        if not _strings(item.get("source_value_refs"))
        or not item.get("row_ref")
        or not _strings(item.get("safe_header_descriptors"))
    )
    if unbindable:
        reasons.append("gate2_package_feasibility_candidate_provenance_incomplete")
    return {
        "schema_version": "broker_reports_gate2_package_feasibility_v1",
        "status": "passed" if not reasons else "blocked",
        "reason_codes": sorted(set(reasons)),
        "available_roles": available_roles,
        "missing_required_roles": missing_roles,
        "unsatisfied_required_role_groups": unsatisfied_groups,
        "available_relation_kinds": available_relation_kinds,
        "missing_required_relation_kinds": missing_relations,
        "unbindable_candidate_ids": unbindable,
        "source_refs_bindable": not unbindable,
    }


def context_component_metrics(context: dict[str, Any]) -> dict[str, Any]:
    components = {
        "identity": context.get("identity") or {},
        "target_refs": context.get("target_source_refs") or [],
        "local_structure": context.get("local_structure") or {},
        "domain_task": context.get("domain_task") or {},
        "candidate_evidence": context.get("candidate_evidence") or [],
        "candidate_relations": context.get("candidate_relations") or [],
        "material_issues": context.get("material_issues") or [],
        "response_contract": context.get("response_contract") or {},
    }
    return {
        name: {
            "chars": len(_compact_json(value)),
            "estimated_tokens": (len(_compact_json(value)) + 3) // 4,
        }
        for name, value in components.items()
    }


def context_budget_metrics(
    context: dict[str, Any], budget: Gate2LlmContextBudget
) -> dict[str, Any]:
    chars = len(_compact_json(context))
    header_depth = max(
        (
            len(_strings(item.get("header_path")))
            for item in _dict_list(
                _object(context.get("local_structure")).get("headers")
            )
        ),
        default=0,
    )
    observed = {
        "source_refs": len(_strings(context.get("target_source_refs"))),
        "candidates": len(_dict_list(context.get("candidate_evidence"))),
        "relations": len(_dict_list(context.get("candidate_relations"))),
        "context_chars": chars,
        "header_depth": header_depth,
    }
    limits = {
        "source_refs": budget.max_source_refs,
        "candidates": budget.max_candidates,
        "relations": budget.max_relations,
        "context_chars": budget.max_context_chars,
        "header_depth": budget.max_header_depth,
        "neighbor_rows": budget.max_neighbor_rows,
    }
    exceeded = sorted(key for key in observed if observed[key] > limits[key])
    return {
        "status": "passed" if not exceeded else "blocked",
        "error_code": None
        if not exceeded
        else "gate2_llm_context_budget_exceeded_" + "_".join(exceeded),
        "observed": observed,
        "limits": limits,
        "silent_truncation_used": False,
    }


def safe_inspection(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": context.get("schema_version"),
        "context_hash": context.get("context_hash"),
        "domain": _object(context.get("domain_task")).get("domain"),
        "target_refs_total": len(_strings(context.get("target_source_refs"))),
        "structure": copy.deepcopy(context.get("local_structure") or {}),
        "candidates": [
            {
                "candidate_id": item.get("candidate_id"),
                "kind": item.get("kind"),
                "visible_label": item.get("visible_label"),
                "roles": item.get("allowed_roles") or [],
                "source_refs_total": len(_strings(item.get("source_value_refs"))),
            }
            for item in _dict_list(context.get("candidate_evidence"))
        ],
        "relations": copy.deepcopy(context.get("candidate_relations") or []),
        "required_roles": _object(context.get("domain_task")).get("required_roles")
        or [],
        "ownership_refs": copy.deepcopy(context.get("target_source_refs") or []),
        "material_issue_refs": [
            item.get("issue_ref") for item in _dict_list(context.get("material_issues"))
        ],
        "budget": copy.deepcopy(context.get("budget") or {}),
        "component_metrics": context_component_metrics(context),
    }


def detect_context_duplication(contexts: list[dict[str, Any]]) -> dict[str, Any]:
    component_names = (
        "local_structure",
        "candidate_evidence",
        "candidate_relations",
        "material_issues",
    )
    result: dict[str, Any] = {}
    for name in component_names:
        counts: dict[str, int] = {}
        for context in contexts:
            digest = hashlib.sha256(
                _compact_json(context.get(name) or {}).encode("utf-8")
            ).hexdigest()
            counts[digest] = counts.get(digest, 0) + 1
        result[name] = {
            "unique_total": len(counts),
            "sent_total": len(contexts),
            "repeated_sends_total": sum(max(0, count - 1) for count in counts.values()),
        }
    return result


def _compact_structure(unit: dict[str, Any], target_refs: set[str]) -> dict[str, Any]:
    projection = _object(unit.get("model_source_projection"))
    rows = [
        {
            "source_ref": item.get("row_ref"),
            "row_role": item.get("row_role") or item.get("row_kind"),
            "cells": [
                {
                    "label": cell.get("header_label"),
                    "value": cell.get("value"),
                    "source_value_ref": cell.get("source_value_ref"),
                }
                for cell in _dict_list(item.get("cells"))
            ],
        }
        for item in _dict_list(projection.get("rows"))
        if str(item.get("row_ref") or "") in target_refs
    ]
    segments = [
        {
            "source_ref": item.get("text_segment_ref"),
            "visible_text": item.get("value"),
        }
        for item in _dict_list(projection.get("segments"))
        if str(item.get("text_segment_ref") or "") in target_refs
    ]
    headers = [
        {
            "header_ref": item.get("header_ref"),
            "visible_label": item.get("normalized_label"),
            "header_path": _strings(
                item.get("header_path") or item.get("normalized_header_path")
            ),
        }
        for item in _dict_list(unit.get("normalized_header_descriptors"))
    ]
    return {
        "source_unit_kind": unit.get("unit_kind"),
        "source_input_mode": unit.get("source_input_mode"),
        "table_projection_ref": unit.get("table_projection_id"),
        "section_ref": unit.get("section_ref"),
        "headers": headers,
        "target_rows": rows,
        "target_segments": segments,
    }


def _compact_candidate(item: dict[str, Any]) -> dict[str, Any]:
    labels = _strings(item.get("safe_header_descriptors"))
    return {
        "candidate_id": item.get("candidate_id"),
        "kind": item.get("candidate_kind"),
        "visible_label": labels[0] if labels else "unknown",
        "normalized_value": item.get("normalized_value"),
        "normalization_kind": item.get("normalization_kind"),
        "source_value_refs": _strings(item.get("source_value_refs")),
        "row_ref": item.get("row_ref"),
        "column_ref": item.get("column_ref"),
        "header_refs": _strings(item.get("header_refs")),
        "allowed_roles": _strings(item.get("allowed_semantic_roles")),
        "allowed_fact_field_paths": _strings(item.get("allowed_fact_field_paths")),
        "ambiguity_group_ref": item.get("ambiguity_group_ref"),
    }


def _compact_relation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "relation_id": item.get("relation_id"),
        "kind": item.get("relation_kind"),
        "candidate_ids": _strings(item.get("candidate_ids")),
        "row_refs": _strings(item.get("row_refs")),
        "reason_codes": _strings(item.get("reason_codes")),
    }


def _material_issues(
    package: dict[str, Any], target_refs: set[str]
) -> list[dict[str, Any]]:
    result = []
    allowed = set(_strings(package.get("allowed_issue_refs")))
    for issue in _dict_list(package.get("issue_context")):
        affected = set(
            _strings(issue.get("source_refs"))
            + _strings(issue.get("affected_source_refs"))
            + _strings(issue.get("evidence_refs"))
        )
        package_material = (
            str(issue.get("issue_ref") or "") in allowed
            and str(issue.get("impact") or "")
            in {
                "limits_confirmation",
                "blocks_fact",
                "blocks_consolidation",
                "blocks_declaration",
            }
        )
        if not package_material and (not affected or not affected & target_refs):
            continue
        result.append(
            {
                "issue_ref": issue.get("issue_ref"),
                "code": issue.get("code"),
                "impact": issue.get("impact"),
                "status": issue.get("status"),
                "affected_target_refs": sorted(affected & target_refs),
            }
        )
    return result


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
