from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .gate2_candidate_binding import Gate2CandidateBindingKernelFactory
from .gate2_domain_routing import (
    DOMAIN_ALLOWED_FACT_TYPES,
    DOMAIN_EXTRACTOR_IDS,
    FACT_DOMAIN_ORDER,
    ROUTE_SCHEMA_VERSION,
    validate_source_unit_domain_route,
)
from .gate2_llm_context import Gate2LlmContextPackageFactory, package_feasibility
from .source_provenance import reproduce_normalized_value


DOMAIN_PACKAGE_SCHEMA_VERSION = "broker_reports_domain_extraction_package_v0"
DOMAIN_PACKAGE_POLICY_VERSION = "gate2_domain_package_projection_v0"

FACTORY_REQUIRED = (
    "Gate2DomainPackageBuilderFactory.create is the only production domain package builder entrypoint"
)
FORBIDDEN = (
    "Pipes and prompts must not widen domain packages or add evidence, source-value or issue refs"
)


@dataclass(frozen=True)
class Gate2DomainPackageBuilderConfig:
    include_secondary_candidates: bool = True
    candidate_binding_enabled: bool = False


class Gate2DomainPackageBuilderFactory:
    def __init__(self, config: Gate2DomainPackageBuilderConfig | None = None) -> None:
        self.config = config or Gate2DomainPackageBuilderConfig()

    def create(self) -> "Gate2DomainPackageBuilder":
        return Gate2DomainPackageBuilder(self.config)


class Gate2DomainPackageBuilder:
    def __init__(self, config: Gate2DomainPackageBuilderConfig) -> None:
        self.config = config

    def build(
        self,
        *,
        base_package: dict[str, Any],
        route: dict[str, Any],
        route_artifact_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        validate_source_unit_domain_route(route)
        if route.get("schema_version") != ROUTE_SCHEMA_VERSION:
            raise ValueError("gate2_domain_route_schema_mismatch")
        unit = _object(base_package.get("source_unit"))
        if route.get("source_unit_ref") != unit.get("unit_id"):
            raise ValueError("gate2_domain_package_route_scope_mismatch")

        entries = _dict_list(route.get("route_entries"))
        packages: list[dict[str, Any]] = []
        for domain in FACT_DOMAIN_ORDER:
            candidate_entries = [
                item
                for item in entries
                if item.get("route_kind") == "model_candidate"
                and domain in _string_list(item.get("candidate_domains"))
                and (
                    self.config.include_secondary_candidates
                    or item.get("primary_suggested_domain") == domain
                )
            ]
            if not candidate_entries:
                continue
            candidate_refs = [str(item["source_ref"]) for item in candidate_entries]
            narrowed_unit = narrow_source_unit_projection(unit, candidate_refs)
            allowed_evidence_refs = narrow_evidence_refs(
                narrowed_unit=narrowed_unit,
                candidate_refs=candidate_refs,
            )
            allowed_value_refs = sorted(
                {
                    str(item.get("source_value_ref"))
                    for item in _dict_list(narrowed_unit.get("source_value_index"))
                    if item.get("source_value_ref")
                }
            )
            deterministic_value_candidates = _deterministic_value_candidates(
                narrowed_unit,
                domain=domain,
            )
            package_id = f"sfdpkg_{stable_digest([base_package.get('extraction_run_id'), base_package.get('package_id'), route.get('route_id'), domain, candidate_refs], length=24)}"
            coverage_ref = f"dcoverage_{stable_digest([route.get('route_id'), domain, candidate_refs], length=24)}"
            package = {
                "schema_version": DOMAIN_PACKAGE_SCHEMA_VERSION,
                "package_mode": "domain_runtime_strict_json_schema",
                "package_id": package_id,
                "extraction_run_id": base_package.get("extraction_run_id"),
                "normalization_run_id": base_package.get("normalization_run_id"),
                "case_id": base_package.get("case_id"),
                "document_ref": base_package.get("document_ref"),
                "source_bucket_roles": copy.deepcopy(
                    base_package.get("source_bucket_roles") or []
                ),
                "document_context": copy.deepcopy(
                    base_package.get("document_context") or {}
                ),
                "source_unit": narrowed_unit,
                "base_package_id": base_package.get("package_id"),
                "base_package_artifact_ref": base_package.get(
                    "package_artifact_ref"
                ),
                "segmentation_plan_artifact_ref": base_package.get(
                    "segmentation_plan_artifact_ref"
                ),
                "segmentation": copy.deepcopy(
                    base_package.get("segmentation") or {}
                ),
                "domain_route_id": route.get("route_id"),
                "domain_route_artifact_ref": route_artifact_ref,
                "extractor_domain": domain,
                "extractor_id": DOMAIN_EXTRACTOR_IDS[domain],
                "candidate_source_refs": candidate_refs,
                "primary_candidate_refs": [
                    str(item["source_ref"])
                    for item in candidate_entries
                    if item.get("primary_suggested_domain") == domain
                ],
                "secondary_candidate_refs": [
                    str(item["source_ref"])
                    for item in candidate_entries
                    if item.get("primary_suggested_domain") != domain
                ],
                "allowed_fact_types": copy.deepcopy(
                    DOMAIN_ALLOWED_FACT_TYPES[domain]
                ),
                "allowed_evidence_refs": allowed_evidence_refs,
                "allowed_source_value_refs": allowed_value_refs,
                "deterministic_value_candidates": deterministic_value_candidates,
                "issue_context": copy.deepcopy(
                    base_package.get("issue_context") or []
                ),
                "allowed_issue_refs": sorted(
                    _string_list(base_package.get("allowed_issue_refs"))
                ),
                "forbidden_assumptions": sorted(
                    set(
                        _string_list(base_package.get("forbidden_assumptions"))
                        + [
                            "extractor_must_not_change_domain_route",
                            "extractor_must_not_assign_final_row_ownership",
                            "extractor_must_not_resolve_issues",
                            "extractor_must_not_consolidate_duplicates",
                            "extractor_must_not_calculate_tax_profit_or_loss",
                            "extractor_must_not_generate_declaration_or_xls",
                            "extractor_must_not_use_external_knowledge_or_rag",
                        ]
                    )
                ),
                "coverage_expectation": {
                    "coverage_ref": coverage_ref,
                    "selected_source_refs": candidate_refs,
                    "ignorable_header_refs": [],
                    "ignorable_blank_refs": [],
                    "layout_candidate_refs": [],
                    "mandatory_no_fact_results": [],
                    "fact_candidate_refs": candidate_refs,
                    "required_accounting_total": len(candidate_refs),
                    "coverage_policy_id": "gate2_domain_candidate_coverage_v0",
                },
                "prompt_contract": {
                    "prompt_contract_id": "broker_reports_domain_source_fact_prompt_v0",
                    "prompt_body_embedded": False,
                },
                "output_schema": {
                    "output_schema_id": "broker_reports.source_facts.schema.v0",
                    "output_schema_version": "broker_reports_source_facts_v0",
                    "domain_wrapper_schema_version": "broker_reports_domain_source_facts_v0",
                    "strict_json_schema_required": True,
                },
                "model_id": base_package.get("model_id"),
                "structured_output_policy": {
                    "required_mode": "json_schema",
                    "strict": True,
                    "fallback": "none",
                    "validator_is_final_authority": True,
                },
                "package_policy_version": DOMAIN_PACKAGE_POLICY_VERSION,
                "privacy_policy": copy.deepcopy(
                    base_package.get("privacy_policy") or {}
                ),
                "created_at": base_package.get("created_at"),
            }
            if self.config.candidate_binding_enabled:
                binding = Gate2CandidateBindingKernelFactory().create().build(package)
                package.update(
                    {
                        "candidate_binding_mode": "candidate_ids_and_semantic_roles_v0",
                        "source_value_candidate_set": binding["candidate_set"],
                        "candidate_relation_set": binding["relation_set"],
                        "candidate_binding_profile": binding["profile"],
                    }
                )
                package["output_schema"].update(
                    {
                        "model_output_schema_id": "broker_reports.candidate_binding_output.schema.v0",
                        "model_output_schema_version": "broker_reports_candidate_binding_output_v0",
                    }
                )
                package["package_feasibility"] = package_feasibility(package)
                package["llm_context_package"] = (
                    Gate2LlmContextPackageFactory().create().build(package)
                )
            validate_domain_extraction_package(package)
            packages.append(package)
        return packages


def validate_domain_extraction_package(package: dict[str, Any]) -> None:
    if package.get("schema_version") != DOMAIN_PACKAGE_SCHEMA_VERSION:
        raise ValueError("gate2_domain_package_schema_mismatch")
    domain = str(package.get("extractor_domain") or "")
    if domain not in DOMAIN_ALLOWED_FACT_TYPES:
        raise ValueError("gate2_domain_package_domain_invalid")
    if package.get("extractor_id") != DOMAIN_EXTRACTOR_IDS[domain]:
        raise ValueError("gate2_domain_package_extractor_mismatch")
    if _string_list(package.get("allowed_fact_types")) != DOMAIN_ALLOWED_FACT_TYPES[domain]:
        raise ValueError("gate2_domain_package_fact_types_mismatch")
    candidates = _string_list(package.get("candidate_source_refs"))
    expectation = _object(package.get("coverage_expectation"))
    if not candidates or candidates != _string_list(
        expectation.get("selected_source_refs")
    ):
        raise ValueError("gate2_domain_package_coverage_mismatch")
    allowed_evidence = set(_string_list(package.get("allowed_evidence_refs")))
    if not set(candidates) <= allowed_evidence:
        raise ValueError("gate2_domain_package_provenance_missing")
    unit = _object(package.get("source_unit"))
    projected_refs = {
        str(item.get("row_ref") or item.get("text_segment_ref") or "")
        for item in (
            _dict_list(_object(unit.get("model_source_projection")).get("rows"))
            + _dict_list(
                _object(unit.get("model_source_projection")).get("segments")
            )
        )
    }
    if projected_refs != set(candidates):
        raise ValueError("gate2_domain_package_projection_scope_mismatch")
    allowed_values = set(_string_list(package.get("allowed_source_value_refs")))
    indexed_values = {
        str(item.get("source_value_ref"))
        for item in _dict_list(unit.get("source_value_index"))
        if item.get("source_value_ref")
    }
    if allowed_values != indexed_values:
        raise ValueError("gate2_domain_package_value_ref_scope_mismatch")
    if package.get("candidate_binding_mode"):
        candidate_set = _object(package.get("source_value_candidate_set"))
        relation_set = _object(package.get("candidate_relation_set"))
        profile = _object(package.get("candidate_binding_profile"))
        if candidate_set.get("package_id") != package.get("package_id"):
            raise ValueError("candidate_binding_package_scope_mismatch")
        if relation_set.get("package_id") != package.get("package_id"):
            raise ValueError("candidate_binding_relation_package_scope_mismatch")
        if profile.get("domain") != domain:
            raise ValueError("candidate_binding_profile_domain_mismatch")


def narrow_source_unit_projection(
    unit: dict[str, Any], selected_refs: list[str]
) -> dict[str, Any]:
    """Return a private projection containing only the selected source refs.

    The helper is shared by deterministic source-unit segmentation and the
    domain package builder.  It never mints provenance: existing row, cell,
    segment, source-value and checksum refs are preserved while payload paths
    are rebased to the physically narrowed projection.
    """
    large_projection_fields = {
        "normalized_source_projection",
        "model_source_projection",
        "row_refs",
        "row_provenance",
        "cell_refs",
        "cell_value_refs",
        "cell_provenance",
        "source_value_refs",
        "source_value_index",
        "private_values",
        "text_segment_refs",
        "segment_provenance",
        "section_refs",
        "character_span_refs",
        "layout_word_refs",
        "layout_line_refs",
        "layout_bbox_refs",
        "pdf_layout_source_value_refs",
        "pdf_layout_source_value_index",
        "pdf_layout_coverage",
        "table_contributing_word_refs",
        "table_fallback_text_refs",
        "table_fallback_source_value_refs",
    }
    narrowed = {
        key: copy.deepcopy(value)
        for key, value in unit.items()
        if key not in large_projection_fields
    }
    candidate_set = set(selected_refs)
    model_projection = _object(unit.get("model_source_projection"))
    rows = [
        copy.deepcopy(item)
        for item in _dict_list(model_projection.get("rows"))
        if str(item.get("row_ref") or "") in candidate_set
    ]
    segments = [
        copy.deepcopy(item)
        for item in _dict_list(model_projection.get("segments"))
        if str(item.get("text_segment_ref") or "") in candidate_set
    ]
    if unit.get("unit_kind") in {"pdf_line_cluster", "pdf_table_candidate"}:
        narrowed["model_source_projection"] = {
            "schema_version": model_projection.get("schema_version"),
            "projection_kind": unit.get("unit_kind"),
            "segments": segments,
            "table_reconstruction_status": model_projection.get(
                "table_reconstruction_status"
            ),
            "semantic_table_truth_claimed": False,
        }
        layout_index_by_ref = {
            str(item.get("source_object_ref") or ""): item
            for item in _dict_list(unit.get("pdf_layout_source_value_index"))
            if item.get("source_object_ref")
        }
        text_parts: list[str] = []
        generic_index: list[dict[str, Any]] = []
        layout_index: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        offset = 0
        for segment in segments:
            source_ref = str(segment.get("text_segment_ref") or "")
            value = str(segment.get("value") or "")
            source_value_ref = str(segment.get("source_value_ref") or "")
            if source_ref not in candidate_set or not source_value_ref:
                continue
            start = offset
            text_parts.append(value)
            offset += len(value)
            original_index = copy.deepcopy(
                _object(layout_index_by_ref.get(source_ref))
            )
            rebased_path = {
                "kind": "text_span",
                "character_start": start,
                "character_end": offset,
            }
            generic_index.append(
                {
                    "source_value_ref": source_value_ref,
                    "text_segment_ref": source_ref,
                    "value_path": rebased_path,
                    "value_checksum_ref": original_index.get("value_checksum_ref"),
                }
            )
            original_index["value_path"] = {
                "kind": "pdf_unit_text_span",
                "character_start": start,
                "character_end": offset,
            }
            layout_index.append(original_index)
            provenance.append(
                {
                    "text_segment_ref": source_ref,
                    "page_ref": segment.get("page_ref"),
                    "segment_kind": segment.get("segment_kind"),
                    "source_value_ref": source_value_ref,
                    "character_start": start,
                    "character_end": offset,
                }
            )
        narrowed["normalized_source_projection"] = {"text": "".join(text_parts)}
        narrowed["source_value_index"] = generic_index
        narrowed["source_value_refs"] = [
            str(item.get("source_value_ref") or "") for item in generic_index
        ]
        narrowed["pdf_layout_source_value_index"] = layout_index
        narrowed["pdf_layout_source_value_refs"] = [
            str(item.get("source_value_ref") or "") for item in layout_index
        ]
        narrowed["segment_provenance"] = provenance
        narrowed["text_segment_refs"] = [
            str(item.get("text_segment_ref") or "") for item in segments
        ]
        narrowed["layout_word_refs"] = sorted(
            ref for ref in candidate_set if ref.startswith("pdfword_")
        )
        narrowed["layout_line_refs"] = sorted(
            ref for ref in candidate_set if ref.startswith("pdfline_")
        )
        parent_layout_coverage = _object(unit.get("pdf_layout_coverage"))
        narrowed["pdf_layout_coverage"] = {
            **copy.deepcopy(parent_layout_coverage),
            "selected_source_refs": list(selected_refs),
            "accounted_source_refs": list(selected_refs),
            "owned_word_refs": copy.deepcopy(narrowed["layout_word_refs"]),
            "owned_line_refs": copy.deepcopy(narrowed["layout_line_refs"]),
            "selected_total": len(selected_refs),
            "accounted_total": len(selected_refs),
            "duplicate_accounted_refs": [],
            "unaccounted_refs": [],
            "all_selected_refs_accounted": len(selected_refs)
            == len(set(selected_refs)),
        }
        narrowed["table_contributing_word_refs"] = sorted(
            set(_string_list(unit.get("table_contributing_word_refs")))
            & candidate_set
        )
        narrowed["table_fallback_text_refs"] = sorted(
            set(_string_list(unit.get("table_fallback_text_refs")))
            & candidate_set
        )
        narrowed["table_fallback_source_value_refs"] = sorted(
            {
                str(item.get("source_value_ref") or "")
                for item in layout_index
                if str(item.get("source_object_ref") or "")
                in set(narrowed["table_fallback_text_refs"])
            }
        )
        narrowed["row_provenance"] = []
        narrowed["row_refs"] = []
        narrowed["cell_provenance"] = []
        narrowed["cell_refs"] = []
        narrowed["cell_value_refs"] = []
        narrowed["section_refs"] = []
        narrowed["character_span_refs"] = []
    elif unit.get("unit_kind") == "table_row_window":
        narrowed["model_source_projection"] = {
            "schema_version": model_projection.get("schema_version"),
            "rows": rows,
        }
        selected_row_refs = {str(item.get("row_ref") or "") for item in rows}
        row_provenance = [
            copy.deepcopy(item)
            for item in _dict_list(unit.get("row_provenance"))
            if str(item.get("row_ref") or "") in selected_row_refs
        ]
        selected_cell_refs = {
            str(cell.get("cell_ref") or "")
            for row in rows
            for cell in _dict_list(row.get("cells"))
            if cell.get("cell_ref")
        }
        cell_provenance = [
            copy.deepcopy(item)
            for item in _dict_list(unit.get("cell_provenance"))
            if str(item.get("cell_ref") or "") in selected_cell_refs
        ]
        selected_cell_value_refs = {
            str(item.get("cell_value_ref") or item.get("source_value_ref"))
            for item in cell_provenance
            if item.get("cell_value_ref") or item.get("source_value_ref")
        }
        selected_source_value_refs = {
            ref
            for item in cell_provenance
            for ref in (
                _string_list(item.get("source_value_refs"))
                or _string_list([item.get("source_value_ref")])
            )
        }
        selected_source_value_refs.update(
            ref
            for row in rows
            for cell in _dict_list(row.get("cells"))
            for ref in (
                _string_list(cell.get("source_value_refs"))
                or _string_list([cell.get("source_value_ref")])
            )
        )
        row_index_by_ref = {
            str(row.get("row_ref") or ""): row_index
            for row_index, row in enumerate(rows)
        }
        column_index_by_cell_ref = {
            str(cell.get("cell_ref") or ""): column_index
            for row in rows
            for column_index, cell in enumerate(_dict_list(row.get("cells")))
        }
        row_ref_by_cell_ref = {
            str(cell.get("cell_ref") or ""): str(row.get("row_ref") or "")
            for row in rows
            for cell in _dict_list(row.get("cells"))
        }
        source_value_index = []
        for item in _dict_list(unit.get("source_value_index")):
            if str(item.get("source_value_ref") or "") not in selected_source_value_refs:
                continue
            copied = copy.deepcopy(item)
            value_path = _object(copied.get("value_path"))
            cell_ref = str(copied.get("cell_ref") or "")
            if value_path.get("kind") == "table_cell" and cell_ref:
                copied["value_path"] = {
                    "kind": "table_cell",
                    "row_index": row_index_by_ref[row_ref_by_cell_ref[cell_ref]],
                    "column_index": column_index_by_cell_ref[cell_ref],
                }
            source_value_index.append(copied)
        narrowed["normalized_source_projection"] = {
            "cells": [
                [cell.get("value") for cell in _dict_list(row.get("cells"))]
                for row in rows
            ]
        }
        selected_private_paths = {
            str(_object(item.get("value_path")).get("value_path_ref") or "")
            for item in source_value_index
            if _object(item.get("value_path")).get("value_path_ref")
        }
        selected_private_paths.update(
            str(item.get("normalized_private_value_path") or "")
            for item in cell_provenance
            if item.get("normalized_private_value_path")
        )
        narrowed["private_values"] = [
            copy.deepcopy(item)
            for item in _dict_list(unit.get("private_values"))
            if str(item.get("value_path_ref") or "") in selected_private_paths
        ]
        narrowed["row_refs"] = [str(item["row_ref"]) for item in row_provenance]
        narrowed["row_provenance"] = row_provenance
        narrowed["cell_provenance"] = cell_provenance
        narrowed["cell_refs"] = sorted(selected_cell_refs)
        narrowed["cell_value_refs"] = sorted(selected_cell_value_refs)
        narrowed["source_value_index"] = source_value_index
        narrowed["source_value_refs"] = [
            str(item["source_value_ref"])
            for item in source_value_index
            if item.get("source_value_ref")
        ]
        narrowed["segment_provenance"] = []
        narrowed["text_segment_refs"] = []
        narrowed["section_refs"] = []
        narrowed["character_span_refs"] = []
    else:
        narrowed["model_source_projection"] = {
            "schema_version": model_projection.get("schema_version"),
            "segments": segments,
        }
        selected_segment_refs = {
            str(item.get("text_segment_ref") or "") for item in segments
        }
        source_index_by_segment = {
            str(item.get("text_segment_ref") or ""): item
            for item in _dict_list(unit.get("source_value_index"))
        }
        segment_provenance_by_ref = {
            str(item.get("text_segment_ref") or ""): item
            for item in _dict_list(unit.get("segment_provenance"))
        }
        original_text = str(_object(unit.get("normalized_source_projection")).get("text") or "")
        new_text_parts: list[str] = []
        new_index: list[dict[str, Any]] = []
        new_provenance: list[dict[str, Any]] = []
        offset = 0
        for segment in segments:
            ref = str(segment.get("text_segment_ref") or "")
            old_index = _object(source_index_by_segment.get(ref))
            old_path = _object(old_index.get("value_path"))
            start = int(old_path.get("character_start") or 0)
            end = int(old_path.get("character_end") or 0)
            value = original_text[start:end]
            new_text_parts.append(value)
            copied_index = copy.deepcopy(old_index)
            copied_index["value_path"] = {
                "kind": "text_span",
                "character_start": offset,
                "character_end": offset + len(value),
            }
            new_index.append(copied_index)
            copied_provenance = copy.deepcopy(
                _object(segment_provenance_by_ref.get(ref))
            )
            copied_provenance["character_start"] = offset
            copied_provenance["character_end"] = offset + len(value)
            new_provenance.append(copied_provenance)
            offset += len(value)
        narrowed["normalized_source_projection"] = {
            "text": "".join(new_text_parts)
        }
        narrowed["segment_provenance"] = new_provenance
        narrowed["source_value_index"] = new_index
        narrowed["source_value_refs"] = [
            str(item["source_value_ref"])
            for item in new_index
            if item.get("source_value_ref")
        ]
        narrowed["text_segment_refs"] = sorted(selected_segment_refs)
        narrowed["section_refs"] = sorted(
            {
                str(item.get("section_ref"))
                for item in new_provenance
                if item.get("section_ref")
            }
        )
        narrowed["character_span_refs"] = sorted(
            {
                str(item.get("character_span_ref"))
                for item in new_provenance
                if item.get("character_span_ref")
            }
        )
        narrowed["row_provenance"] = []
        narrowed["row_refs"] = []
        narrowed["cell_provenance"] = []
        narrowed["cell_refs"] = []
        narrowed["cell_value_refs"] = []
    return narrowed


def narrow_evidence_refs(
    *, narrowed_unit: dict[str, Any], candidate_refs: list[str]
) -> list[str]:
    refs = set(candidate_refs)
    for field in (
        "unit_id",
        "slice_ref",
        "table_ref",
        "row_range_ref",
        "page_range_ref",
        "coverage_ref",
        "private_slice_artifact_ref",
        "table_projection_id",
        "table_projection_artifact_ref",
        "parser_ref",
        "source_checksum_ref",
        "layout_parser_ref",
        "layout_parser_config_ref",
        "pdf_layout_unit_checksum_ref",
        "table_candidate_ref",
        "table_strategy_ref",
        "table_bbox_ref",
    ):
        if narrowed_unit.get(field):
            refs.add(str(narrowed_unit[field]))
    for field in (
        "row_refs",
        "cell_refs",
        "text_segment_refs",
        "section_refs",
        "page_refs",
        "character_span_refs",
        "layout_word_refs",
        "layout_line_refs",
        "layout_bbox_refs",
        "pdf_layout_source_value_refs",
        "table_row_refs",
        "table_cell_refs",
        "table_contributing_word_refs",
        "table_fallback_text_refs",
        "table_fallback_source_value_refs",
    ):
        refs.update(_string_list(narrowed_unit.get(field)))
    return sorted(refs)


def _deterministic_value_candidates(
    unit: dict[str, Any], *, domain: str
) -> list[dict[str, str]]:
    projection = _object(unit.get("model_source_projection"))
    if not _dict_list(projection.get("rows")):
        return []
    pseudo_slice = copy.deepcopy(unit)
    normalized = _object(unit.get("normalized_source_projection"))
    pseudo_slice["cells"] = copy.deepcopy(normalized.get("cells") or [])
    header_mapping = {
        "date": ("date", "iso_date_exact"),
        "amount": ("amount", "decimal_dot"),
        "currency": ("currency", "currency_code_visible"),
        "quantity": ("quantity", "decimal_dot"),
        "instrument": ("identifier", "trimmed_text"),
    }
    result = []
    for row in _dict_list(projection.get("rows")):
        row_ref = str(row.get("row_ref") or "")
        for cell in _dict_list(row.get("cells")):
            mapping = header_mapping.get(str(cell.get("header_label") or ""))
            source_value_ref = str(cell.get("source_value_ref") or "")
            if not mapping or not row_ref or not source_value_ref:
                continue
            field, normalization_kind = mapping
            try:
                value = reproduce_normalized_value(
                    pseudo_slice, source_value_ref, normalization_kind
                )
            except ValueError:
                continue
            result.append(
                {
                    "source_ref": row_ref,
                    "field": field,
                    "source_value_ref": source_value_ref,
                    "normalized_value": value,
                    "normalization_kind": normalization_kind,
                    "policy_id": "exact_header_mechanical_value_candidate_v0",
                }
            )
    if domain == "cash_movement":
        for row in _dict_list(projection.get("rows")):
            row_ref = str(row.get("row_ref") or "")
            for cell in _dict_list(row.get("cells")):
                if (
                    str(cell.get("header_label") or "") != "unknown"
                    or "decimal_like" not in _string_list(cell.get("value_kind_hints"))
                ):
                    continue
                source_value_ref = str(cell.get("source_value_ref") or "")
                if not row_ref or not source_value_ref:
                    continue
                try:
                    value = reproduce_normalized_value(
                        pseudo_slice, source_value_ref, "decimal_dot"
                    )
                except ValueError:
                    continue
                result.append(
                    {
                        "source_ref": row_ref,
                        "field": "amount",
                        "source_value_ref": source_value_ref,
                        "normalized_value": value,
                        "normalization_kind": "decimal_dot",
                        "policy_id": "cash_movement_unknown_decimal_candidate_v0",
                    }
                )
    deduplicated = {
        (item["source_ref"], item["field"], item["source_value_ref"]): item
        for item in result
    }
    return [deduplicated[key] for key in sorted(deduplicated)]


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
