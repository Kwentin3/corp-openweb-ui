from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .gate2_domain_contracts import DOMAIN_SOURCE_FACTS_SCHEMA_VERSION
from .gate2_domain_routing import FALLBACK_DOMAIN, ROUTE_SCHEMA_VERSION


STITCH_RESULT_SCHEMA_VERSION = "broker_reports_source_fact_stitch_result_v0"
STITCH_POLICY_VERSION = "gate2_source_fact_stitching_v0"

FACTORY_REQUIRED = (
    "Gate2SourceFactStitcherFactory.create is the only production domain fan-in and ownership entrypoint"
)
FORBIDDEN = (
    "Pipes, prompts and extractors must not merge domain facts, resolve conflicts or declare final coverage"
)


@dataclass(frozen=True)
class Gate2SourceFactStitcherConfig:
    allow_explicit_multi_fact_rules: bool = False


class Gate2SourceFactStitcherFactory:
    def __init__(self, config: Gate2SourceFactStitcherConfig | None = None) -> None:
        self.config = config or Gate2SourceFactStitcherConfig()

    def create(self) -> "Gate2SourceFactStitcher":
        if self.config.allow_explicit_multi_fact_rules:
            raise ValueError("gate2_stitch_multi_fact_rules_not_implemented")
        return Gate2SourceFactStitcher(self.config)


class Gate2SourceFactStitcher:
    def __init__(self, config: Gate2SourceFactStitcherConfig) -> None:
        self.config = config

    def stitch(
        self,
        *,
        extraction_run_id: str,
        route_ref: str,
        route: dict[str, Any],
        accepted_domain_outputs: list[dict[str, Any]],
        rejected_domain_outputs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if route.get("schema_version") != ROUTE_SCHEMA_VERSION:
            raise ValueError("gate2_stitch_route_schema_mismatch")
        rejected_domain_outputs = rejected_domain_outputs or []
        selected_refs = [str(item) for item in route.get("selected_source_refs") or []]
        route_entries = {
            str(item.get("source_ref") or ""): item
            for item in route.get("route_entries") or []
            if isinstance(item, dict) and item.get("source_ref")
        }
        if set(route_entries) != set(selected_refs):
            raise ValueError("gate2_stitch_route_coverage_mismatch")

        typed_claims: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        unknown_claims: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        no_fact_claims: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        accepted_refs_by_domain: defaultdict[str, list[str]] = defaultdict(list)
        issue_fact_linkage: list[dict[str, str]] = []
        fact_ids: set[str] = set()
        duplicate_fact_ids: set[str] = set()

        for output in accepted_domain_outputs:
            if output.get("wrapper_schema_version") not in {
                None,
                DOMAIN_SOURCE_FACTS_SCHEMA_VERSION,
            }:
                raise ValueError("gate2_stitch_domain_wrapper_schema_mismatch")
            if output.get("validator_status") != "passed":
                raise ValueError("gate2_stitch_unvalidated_output_forbidden")
            domain = str(output.get("extractor_domain") or "")
            source_facts_ref = str(output.get("source_facts_ref") or "")
            source_facts = _object(output.get("source_facts"))
            if not domain or not source_facts_ref:
                raise ValueError("gate2_stitch_domain_output_scope_missing")
            accepted_refs_by_domain[domain].append(source_facts_ref)
            for fact in _dict_list(source_facts.get("facts")):
                fact_id = str(fact.get("fact_id") or "")
                if fact_id in fact_ids:
                    duplicate_fact_ids.add(fact_id)
                fact_ids.add(fact_id)
                covered_refs = sorted(
                    set(_string_list(fact.get("evidence_refs"))) & set(selected_refs)
                )
                claim = {
                    "domain": domain,
                    "fact_id": fact_id,
                    "fact_type": fact.get("fact_type"),
                    "source_facts_ref": source_facts_ref,
                    "validation_ref": output.get("validation_ref"),
                }
                for source_ref in covered_refs:
                    if fact.get("fact_type") == FALLBACK_DOMAIN:
                        unknown_claims[source_ref].append(claim)
                    else:
                        typed_claims[source_ref].append(claim)
                for issue_ref in _string_list(fact.get("linked_issue_refs")):
                    issue_fact_linkage.append(
                        {
                            "issue_ref": issue_ref,
                            "fact_id": fact_id,
                            "source_facts_ref": source_facts_ref,
                            "domain": domain,
                        }
                    )
            for item in _dict_list(
                _object(source_facts.get("coverage")).get("no_fact_results")
            ):
                source_ref = str(item.get("source_ref") or "")
                if source_ref:
                    no_fact_claims[source_ref].append(
                        {
                            "domain": domain,
                            "reason_code": str(item.get("reason_code") or ""),
                            "source_facts_ref": source_facts_ref,
                        }
                    )

        ownership_map: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        unknown_refs: list[str] = []
        no_fact_results: list[dict[str, str]] = []
        uncovered_refs: list[str] = []
        for source_ref in selected_refs:
            route_entry = route_entries[source_ref]
            deterministic_no_fact = route_entry.get("route_kind") == "deterministic_no_fact"
            typed = typed_claims[source_ref]
            unknown = unknown_claims[source_ref]
            no_fact = no_fact_claims[source_ref]
            if deterministic_no_fact:
                reason = str((_string_list(route_entry.get("reason_codes")) or ["layout_only"])[0])
                no_fact_results.append(
                    {"source_ref": source_ref, "reason_code": reason}
                )
                ownership_map.append(
                    {
                        "source_ref": source_ref,
                        "ownership_status": "deterministic_no_fact",
                        "owner_domain": None,
                        "owner_fact_id": None,
                        "claim_domains": [],
                        "reason_codes": [reason],
                    }
                )
            elif len(typed) > 1:
                conflicts.append(
                    {
                        "source_ref": source_ref,
                        "conflict_code": "multiple_typed_domain_claims",
                        "claim_domains": sorted(
                            {str(item["domain"]) for item in typed}
                        ),
                        "claim_fact_ids": sorted(
                            {str(item["fact_id"]) for item in typed}
                        ),
                        "multi_fact_rule_id": route_entry.get("multi_fact_rule_id"),
                    }
                )
                ownership_map.append(
                    {
                        "source_ref": source_ref,
                        "ownership_status": "conflict",
                        "owner_domain": None,
                        "owner_fact_id": None,
                        "claim_domains": sorted(
                            {str(item["domain"]) for item in typed}
                        ),
                        "reason_codes": ["multiple_typed_domain_claims"],
                    }
                )
            elif len(typed) == 1:
                claim = typed[0]
                ownership_map.append(
                    {
                        "source_ref": source_ref,
                        "ownership_status": "accepted_fact",
                        "owner_domain": claim["domain"],
                        "owner_fact_id": claim["fact_id"],
                        "claim_domains": sorted(
                            {str(item["domain"]) for item in typed + unknown}
                        ),
                        "reason_codes": ["single_validator_passed_typed_claim"],
                    }
                )
            elif unknown:
                unknown_refs.append(source_ref)
                chosen = sorted(
                    unknown,
                    key=lambda item: (
                        str(item["domain"]) != FALLBACK_DOMAIN,
                        str(item["domain"]),
                        str(item["fact_id"]),
                    ),
                )[0]
                ownership_map.append(
                    {
                        "source_ref": source_ref,
                        "ownership_status": "unknown_source_row",
                        "owner_domain": FALLBACK_DOMAIN,
                        "owner_fact_id": chosen["fact_id"],
                        "claim_domains": sorted(
                            {str(item["domain"]) for item in unknown}
                        ),
                        "reason_codes": ["unknown_claim_preserves_coverage"],
                    }
                )
            elif no_fact:
                chosen = sorted(
                    no_fact,
                    key=lambda item: (
                        str(item["domain"]),
                        str(item["reason_code"]),
                    ),
                )[0]
                no_fact_results.append(
                    {
                        "source_ref": source_ref,
                        "reason_code": chosen["reason_code"],
                    }
                )
                ownership_map.append(
                    {
                        "source_ref": source_ref,
                        "ownership_status": "model_no_fact",
                        "owner_domain": None,
                        "owner_fact_id": None,
                        "claim_domains": sorted(
                            {str(item["domain"]) for item in no_fact}
                        ),
                        "reason_codes": [chosen["reason_code"]],
                    }
                )
            else:
                uncovered_refs.append(source_ref)
                ownership_map.append(
                    {
                        "source_ref": source_ref,
                        "ownership_status": "uncovered",
                        "owner_domain": None,
                        "owner_fact_id": None,
                        "claim_domains": [],
                        "reason_codes": ["no_validator_passed_claim_or_no_fact"],
                    }
                )

        if duplicate_fact_ids:
            conflicts.append(
                {
                    "source_ref": None,
                    "conflict_code": "duplicate_fact_ids",
                    "claim_domains": [],
                    "claim_fact_ids": sorted(duplicate_fact_ids),
                    "multi_fact_rule_id": None,
                }
            )
        rejected_candidate_refs = [
            {
                "domain": str(item.get("extractor_domain") or ""),
                "domain_package_ref": item.get("domain_package_ref"),
                "validation_ref": item.get("validation_ref"),
                "candidate_source_refs": sorted(
                    _string_list(item.get("candidate_source_refs"))
                ),
                "error_codes": sorted(_string_list(item.get("error_codes"))),
            }
            for item in rejected_domain_outputs
        ]
        coverage_status = (
            "conflicted"
            if conflicts
            else "partial"
            if uncovered_refs
            else "complete"
        )
        result = {
            "schema_version": STITCH_RESULT_SCHEMA_VERSION,
            "stitch_result_id": f"sfstitch_{stable_digest([extraction_run_id, route.get('route_id'), sorted(fact_ids), coverage_status], length=24)}",
            "extraction_run_id": extraction_run_id,
            "normalization_run_id": route.get("normalization_run_id"),
            "case_id": route.get("case_id"),
            "document_ref": route.get("document_ref"),
            "source_unit_ref": route.get("source_unit_ref"),
            "route_ref": route_ref,
            "routing_policy_version": route.get("routing_policy_version"),
            "stitch_policy_version": STITCH_POLICY_VERSION,
            "accepted_fact_refs_by_domain": {
                domain: sorted(set(refs))
                for domain, refs in sorted(accepted_refs_by_domain.items())
            },
            "rejected_candidate_refs": rejected_candidate_refs,
            "ownership_map": ownership_map,
            "conflicts": conflicts,
            "unknown_source_row_refs": unknown_refs,
            "no_fact_results": no_fact_results,
            "uncovered_refs": uncovered_refs,
            "issue_fact_linkage": sorted(
                issue_fact_linkage,
                key=lambda item: (
                    item["issue_ref"], item["fact_id"], item["domain"]
                ),
            ),
            "coverage": {
                "selected_total": len(selected_refs),
                "accepted_fact_owned_total": sum(
                    1
                    for item in ownership_map
                    if item["ownership_status"] == "accepted_fact"
                ),
                "unknown_total": len(unknown_refs),
                "no_fact_total": len(no_fact_results),
                "conflict_total": len(
                    [item for item in conflicts if item.get("source_ref")]
                ),
                "uncovered_total": len(uncovered_refs),
                "coverage_status": coverage_status,
                "all_selected_refs_accounted": not uncovered_refs,
                "conflict_free": not conflicts,
            },
            "issue_refs": sorted(_string_list(route.get("issue_refs"))),
            "downstream_restrictions": {
                "gate3_handoff_allowed": coverage_status == "complete",
                "cross_document_consolidation_allowed": False,
                "tax_calculation_allowed": False,
                "declaration_mapping_allowed": False,
                "xls_xlsx_generation_allowed": False,
                "restriction_codes": [
                    "stitch_result_is_not_tax_calculation",
                    "stitch_result_is_not_duplicate_consolidation",
                    "stitch_result_is_not_declaration_readiness",
                ],
            },
        }
        validate_source_fact_stitch_result(result)
        return result


def validate_source_fact_stitch_result(result: dict[str, Any]) -> None:
    if result.get("schema_version") != STITCH_RESULT_SCHEMA_VERSION:
        raise ValueError("gate2_stitch_schema_mismatch")
    coverage = _object(result.get("coverage"))
    ownership = _dict_list(result.get("ownership_map"))
    if len(ownership) != int(coverage.get("selected_total") or 0):
        raise ValueError("gate2_stitch_coverage_count_mismatch")
    refs = [str(item.get("source_ref") or "") for item in ownership]
    if len(refs) != len(set(refs)):
        raise ValueError("gate2_stitch_duplicate_ownership_ref")
    actual_status = (
        "conflicted"
        if result.get("conflicts")
        else "partial"
        if result.get("uncovered_refs")
        else "complete"
    )
    if coverage.get("coverage_status") != actual_status:
        raise ValueError("gate2_stitch_coverage_status_mismatch")
    restrictions = _object(result.get("downstream_restrictions"))
    for field in (
        "cross_document_consolidation_allowed",
        "tax_calculation_allowed",
        "declaration_mapping_allowed",
        "xls_xlsx_generation_allowed",
    ):
        if restrictions.get(field) is not False:
            raise ValueError("gate2_stitch_downstream_boundary_forbidden")


def render_domain_compact_russian_summary(
    *,
    stitch_results: list[dict[str, Any]],
    accepted_domains: dict[str, int],
    rejected_packages: int,
    bounded_units: int = 0,
    pending_parent_remainders: int = 0,
) -> str:
    selected = sum(
        int(_object(item.get("coverage")).get("selected_total") or 0)
        for item in stitch_results
    )
    conflicts = sum(len(_dict_list(item.get("conflicts"))) for item in stitch_results)
    uncovered = sum(len(_string_list(item.get("uncovered_refs"))) for item in stitch_results)
    unknown = sum(
        len(_string_list(item.get("unknown_source_row_refs")))
        for item in stitch_results
    )
    domains = ", ".join(
        f"{domain}: {count}" for domain, count in sorted(accepted_domains.items())
    ) or "нет"
    return (
        "Gate 2: доменная структурированная экстракция завершена. "
        f"Принятые наборы по доменам — {domains}. "
        f"Отклонено пакетов: {rejected_packages}. "
        f"Покрытие: {selected} refs; conflicts={conflicts}, unknown={unknown}, uncovered={uncovered}. "
        f"Полностью покрыто выбранных ограниченных фрагментов: {bounded_units}. "
        f"Неполных остатков исходных срезов ожидают повторной подготовки: {pending_parent_remainders}. "
        "Расчёт налогов, декларация и XLS/XLSX не выполнялись."
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
