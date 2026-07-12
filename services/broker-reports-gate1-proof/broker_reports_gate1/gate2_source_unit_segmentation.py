from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .gate2_domain_packages import (
    narrow_evidence_refs,
    narrow_source_unit_projection,
)
from .gate2_domain_routing import (
    FALLBACK_DOMAIN,
    ROUTE_SCHEMA_VERSION,
    validate_source_unit_domain_route,
)


SEGMENTATION_PLAN_SCHEMA_VERSION = "broker_reports_source_unit_segmentation_plan_v0"
DERIVED_SOURCE_UNIT_SCHEMA_VERSION = "broker_reports_derived_source_unit_v0"
SEGMENTATION_POLICY_VERSION = "gate2_source_unit_segmentation_v0"

FACTORY_REQUIRED = (
    "Gate2SourceUnitSegmenterFactory.create is the only production derived source-unit segmentation entrypoint"
)
FORBIDDEN = (
    "Pipes, scripts and models must not select private row ownership, mint provenance refs or silently discard parent coverage"
)


@dataclass(frozen=True)
class Gate2SourceUnitSegmenterConfig:
    table_max_selected_refs: int = 8
    text_max_selected_refs: int = 12


@dataclass(frozen=True)
class Gate2SourceUnitSegmentationResult:
    plan: dict[str, Any]
    derived_packages: list[dict[str, Any]]


class Gate2SourceUnitSegmenterFactory:
    def __init__(
        self, config: Gate2SourceUnitSegmenterConfig | None = None
    ) -> None:
        self.config = config or Gate2SourceUnitSegmenterConfig()

    def create(self) -> "Gate2SourceUnitSegmenter":
        if self.config.table_max_selected_refs <= 0:
            raise ValueError("gate2_table_segment_limit_invalid")
        if self.config.text_max_selected_refs <= 0:
            raise ValueError("gate2_text_segment_limit_invalid")
        return Gate2SourceUnitSegmenter(self.config)


class Gate2SourceUnitSegmenter:
    def __init__(self, config: Gate2SourceUnitSegmenterConfig) -> None:
        self.config = config

    def segment(
        self, *, base_package: dict[str, Any], parent_route: dict[str, Any]
    ) -> Gate2SourceUnitSegmentationResult:
        validate_source_unit_domain_route(parent_route)
        if parent_route.get("schema_version") != ROUTE_SCHEMA_VERSION:
            raise ValueError("gate2_segmentation_route_schema_mismatch")
        unit = _object(base_package.get("source_unit"))
        if parent_route.get("source_unit_ref") != unit.get("unit_id"):
            raise ValueError("gate2_segmentation_route_scope_mismatch")

        selected_refs = _string_list(parent_route.get("selected_source_refs"))
        entries = _dict_list(parent_route.get("route_entries"))
        if [str(item.get("source_ref") or "") for item in entries] != selected_refs:
            raise ValueError("gate2_segmentation_parent_coverage_mismatch")

        groups = self._groups(unit=unit, entries=entries)
        derived_packages: list[dict[str, Any]] = []
        safe_segments: list[dict[str, Any]] = []
        for index, group in enumerate(groups):
            segment_ref = f"sfsegment_{stable_digest([base_package.get('package_id'), unit.get('unit_id'), index, group['selected_refs'], SEGMENTATION_POLICY_VERSION], length=24)}"
            derived = _build_derived_package(
                base_package=base_package,
                parent_route=parent_route,
                segment_ref=segment_ref,
                group=group,
            )
            derived_packages.append(derived)
            safe_segments.append(
                {
                    "segment_ref": segment_ref,
                    "derived_source_unit_ref": _object(
                        derived.get("source_unit")
                    ).get("unit_id"),
                    "selected_source_refs": copy.deepcopy(group["selected_refs"]),
                    "selected_total": len(group["selected_refs"]),
                    "segment_kind": group["segment_kind"],
                    "candidate_domains": copy.deepcopy(group["candidate_domains"]),
                    "primary_domain": group["primary_domain"],
                    "confidence": group["confidence"],
                    "execution_disposition": "available_derived_unit",
                    "issue_refs_total": len(
                        _string_list(derived.get("allowed_issue_refs"))
                    ),
                }
            )

        parent_truncated = unit.get("source_slice_truncated") is True
        plan_id = f"sfsegplan_{stable_digest([base_package.get('extraction_run_id'), base_package.get('package_id'), unit.get('unit_id'), selected_refs, SEGMENTATION_POLICY_VERSION], length=24)}"
        plan = {
            "schema_version": SEGMENTATION_PLAN_SCHEMA_VERSION,
            "plan_id": plan_id,
            "segmentation_policy_version": SEGMENTATION_POLICY_VERSION,
            "extraction_run_id": base_package.get("extraction_run_id"),
            "normalization_run_id": base_package.get("normalization_run_id"),
            "case_id": base_package.get("case_id"),
            "document_ref": base_package.get("document_ref"),
            "parent_package_id": base_package.get("package_id"),
            "parent_source_unit_ref": unit.get("unit_id"),
            "source_checksum_ref": unit.get("source_checksum_ref"),
            "slice_payload_checksum_ref": unit.get("slice_payload_checksum_ref"),
            "parent_source_slice_truncated": parent_truncated,
            "parent_projection_scope": (
                "bounded_truncated_parent_projection"
                if parent_truncated
                else "complete_parent_projection"
            ),
            "segments": safe_segments,
            "coverage": {
                "parent_selected_source_refs": selected_refs,
                "parent_selected_total": len(selected_refs),
                "derived_accounted_total": sum(
                    len(item["selected_refs"]) for item in groups
                ),
                "selected_for_extraction_total": 0,
                "deferred_derived_units_total": len(groups),
                "duplicate_source_refs": [],
                "unaccounted_source_refs": [],
                "all_parent_selected_refs_partitioned": True,
                "parent_remainder_status": (
                    "pending_gate1_reslice"
                    if parent_truncated
                    else "not_applicable_parent_complete"
                ),
            },
            "privacy_policy": {
                "raw_values_in_plan": False,
                "raw_filenames_in_plan": False,
                "raw_file_ids_in_plan": False,
                "private_paths_in_plan": False,
                "chat_text_in_plan": False,
                "knowledge_rag_used": False,
                "vectorization_performed": False,
            },
        }
        validate_source_unit_segmentation(plan, derived_packages)
        return Gate2SourceUnitSegmentationResult(
            plan=plan, derived_packages=derived_packages
        )

    def _groups(
        self, *, unit: dict[str, Any], entries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        segment_by_ref = {
            str(item.get("text_segment_ref") or ""): item
            for item in _dict_list(unit.get("segment_provenance"))
        }
        max_refs = (
            self.config.table_max_selected_refs
            if unit.get("unit_kind") == "table_row_window"
            else self.config.text_max_selected_refs
        )
        groups: list[dict[str, Any]] = []
        current: list[dict[str, Any]] = []
        current_key: tuple[Any, ...] | None = None
        for entry in entries:
            key = _segment_key(entry, segment_by_ref)
            if current and (key != current_key or len(current) >= max_refs):
                groups.append(_describe_group(current))
                current = []
            current.append(entry)
            current_key = key
        if current:
            groups.append(_describe_group(current))
        return groups


def mark_segmentation_selection(
    plan: dict[str, Any], selected_segment_refs: list[str]
) -> dict[str, Any]:
    updated = copy.deepcopy(plan)
    selected = set(selected_segment_refs)
    known = {
        str(item.get("segment_ref") or "")
        for item in _dict_list(updated.get("segments"))
    }
    if not selected <= known:
        raise ValueError("gate2_segmentation_selection_unknown")
    selected_count = 0
    deferred_count = 0
    for item in _dict_list(updated.get("segments")):
        if str(item.get("segment_ref") or "") in selected:
            item["execution_disposition"] = "selected_for_extraction"
            selected_count += 1
        else:
            item["execution_disposition"] = "deferred_derived_unit"
            deferred_count += 1
    coverage = _object(updated.get("coverage"))
    coverage["selected_for_extraction_total"] = selected_count
    coverage["deferred_derived_units_total"] = deferred_count
    updated["coverage"] = coverage
    validate_source_unit_segmentation(updated, None)
    return updated


def validate_source_unit_segmentation(
    plan: dict[str, Any], derived_packages: list[dict[str, Any]] | None
) -> None:
    if plan.get("schema_version") != SEGMENTATION_PLAN_SCHEMA_VERSION:
        raise ValueError("gate2_segmentation_plan_schema_mismatch")
    segments = _dict_list(plan.get("segments"))
    coverage = _object(plan.get("coverage"))
    parent_refs = _string_list(coverage.get("parent_selected_source_refs"))
    derived_refs = [
        str(ref)
        for item in segments
        for ref in _string_list(item.get("selected_source_refs"))
    ]
    if derived_refs != parent_refs:
        raise ValueError("gate2_segmentation_ordered_coverage_mismatch")
    if len(derived_refs) != len(set(derived_refs)):
        raise ValueError("gate2_segmentation_duplicate_source_ref")
    if int(coverage.get("derived_accounted_total") or 0) != len(parent_refs):
        raise ValueError("gate2_segmentation_coverage_count_mismatch")
    if coverage.get("all_parent_selected_refs_partitioned") is not True:
        raise ValueError("gate2_segmentation_parent_coverage_incomplete")
    privacy = _object(plan.get("privacy_policy"))
    if any(privacy.get(key) is not False for key in privacy):
        raise ValueError("gate2_segmentation_privacy_guard_failed")
    if derived_packages is not None:
        if len(segments) != len(derived_packages):
            raise ValueError("gate2_segmentation_derived_count_mismatch")
        for segment, package in zip(segments, derived_packages):
            unit = _object(package.get("source_unit"))
            if package.get("schema_version") != DERIVED_SOURCE_UNIT_SCHEMA_VERSION:
                raise ValueError("gate2_derived_source_unit_schema_mismatch")
            if unit.get("unit_id") != segment.get("derived_source_unit_ref"):
                raise ValueError("gate2_derived_source_unit_ref_mismatch")
            if _string_list(
                _object(package.get("coverage_expectation")).get(
                    "selected_source_refs"
                )
            ) != _string_list(segment.get("selected_source_refs")):
                raise ValueError("gate2_derived_source_unit_coverage_mismatch")
            if unit.get("source_slice_truncated") is not False:
                raise ValueError("gate2_derived_source_unit_silently_truncated")
            if (
                unit.get("source_checksum_ref") != plan.get("source_checksum_ref")
                or unit.get("slice_payload_checksum_ref")
                != plan.get("slice_payload_checksum_ref")
            ):
                raise ValueError("gate2_derived_source_unit_checksum_ref_mismatch")


def _build_derived_package(
    *,
    base_package: dict[str, Any],
    parent_route: dict[str, Any],
    segment_ref: str,
    group: dict[str, Any],
) -> dict[str, Any]:
    selected_refs = _string_list(group.get("selected_refs"))
    parent_unit = _object(base_package.get("source_unit"))
    unit = narrow_source_unit_projection(parent_unit, selected_refs)
    derived_unit_ref = f"sfunit_{stable_digest([parent_unit.get('unit_id'), segment_ref, selected_refs], length=24)}"
    parent_truncated = parent_unit.get("source_slice_truncated") is True
    coverage_ref = f"sfsegcoverage_{stable_digest([segment_ref, selected_refs], length=24)}"
    unit.update(
        {
            "unit_id": derived_unit_ref,
            "parent_source_unit_ref": parent_unit.get("unit_id"),
            "segment_ref": segment_ref,
            "derived_source_unit_schema_version": DERIVED_SOURCE_UNIT_SCHEMA_VERSION,
            "segmentation_policy_version": SEGMENTATION_POLICY_VERSION,
            "parent_source_slice_truncated": parent_truncated,
            "source_slice_truncated": False,
            "coverage_scope": "complete_within_parent_projection",
            "parent_remainder_status": (
                "pending_gate1_reslice"
                if parent_truncated
                else "not_applicable_parent_complete"
            ),
            "coverage_ref": coverage_ref,
            "derived_projection_checksum_ref": f"derivedpayload_{stable_digest([parent_unit.get('slice_payload_checksum_ref'), selected_refs], length=24)}",
            "safe_segment_signals": {
                "segment_kind": group.get("segment_kind"),
                "uniform_primary_domain": group.get("primary_domain"),
                "confidence": group.get("confidence"),
                "candidate_domains": copy.deepcopy(
                    group.get("candidate_domains") or []
                ),
                "signal_policy": "parent_route_contiguous_cluster_v0",
            },
        }
    )
    allowed_evidence_refs = narrow_evidence_refs(
        narrowed_unit=unit, candidate_refs=selected_refs
    )
    allowed_source_value_refs = sorted(
        {
            str(item.get("source_value_ref"))
            for item in _dict_list(unit.get("source_value_index"))
            if item.get("source_value_ref")
        }
    )
    issue_context = _narrow_issue_context(
        _dict_list(base_package.get("issue_context")),
        set(allowed_evidence_refs),
    )
    mandatory_by_ref = {
        str(item.get("source_ref") or ""): copy.deepcopy(item)
        for item in _dict_list(
            _object(base_package.get("coverage_expectation")).get(
                "mandatory_no_fact_results"
            )
        )
    }
    mandatory_no_fact = [
        mandatory_by_ref[ref] for ref in selected_refs if ref in mandatory_by_ref
    ]
    route_entries = {
        str(item.get("source_ref") or ""): item
        for item in _dict_list(parent_route.get("route_entries"))
    }
    fact_candidates = [
        ref
        for ref in selected_refs
        if _object(route_entries.get(ref)).get("route_kind") == "model_candidate"
    ]
    large_scope_fields = {
        "source_unit",
        "allowed_evidence_refs",
        "allowed_source_value_refs",
        "issue_context",
        "allowed_issue_refs",
        "coverage_expectation",
        "segmentation",
    }
    package = {
        key: copy.deepcopy(value)
        for key, value in base_package.items()
        if key not in large_scope_fields
    }
    package.update(
        {
            "schema_version": DERIVED_SOURCE_UNIT_SCHEMA_VERSION,
            "package_mode": "gate2_resolver_gated_derived_source_unit",
            "package_id": f"sfsegpkg_{stable_digest([base_package.get('package_id'), segment_ref, selected_refs], length=24)}",
            "parent_package_id": base_package.get("package_id"),
            "source_unit": unit,
            "allowed_evidence_refs": allowed_evidence_refs,
            "allowed_source_value_refs": allowed_source_value_refs,
            "issue_context": issue_context,
            "allowed_issue_refs": sorted(
                str(item.get("issue_ref"))
                for item in issue_context
                if item.get("issue_ref")
            ),
            "coverage_expectation": {
                "coverage_ref": coverage_ref,
                "selected_source_refs": selected_refs,
                "ignorable_header_refs": [
                    ref
                    for ref in selected_refs
                    if _object(mandatory_by_ref.get(ref)).get("reason_code")
                    == "header_row"
                ],
                "ignorable_blank_refs": [
                    ref
                    for ref in selected_refs
                    if _object(mandatory_by_ref.get(ref)).get("reason_code")
                    == "blank_row"
                ],
                "layout_candidate_refs": [
                    ref
                    for ref in selected_refs
                    if _object(mandatory_by_ref.get(ref)).get("reason_code")
                    == "layout_only"
                ],
                "mandatory_no_fact_results": mandatory_no_fact,
                "fact_candidate_refs": fact_candidates,
                "required_accounting_total": len(selected_refs),
                "coverage_policy_id": "gate2_segmented_source_unit_coverage_v0",
                "parent_coverage_ref": _object(
                    base_package.get("coverage_expectation")
                ).get("coverage_ref"),
            },
            "segmentation": {
                "segment_ref": segment_ref,
                "parent_source_unit_ref": parent_unit.get("unit_id"),
                "segment_kind": group.get("segment_kind"),
                "candidate_domains": copy.deepcopy(
                    group.get("candidate_domains") or []
                ),
                "confidence": group.get("confidence"),
                "parent_remainder_status": unit.get("parent_remainder_status"),
            },
        }
    )
    return package


def _segment_key(
    entry: dict[str, Any], _segment_by_ref: dict[str, dict[str, Any]]
) -> tuple[Any, ...]:
    route_kind = str(entry.get("route_kind") or "")
    primary = str(entry.get("primary_suggested_domain") or "")
    confidence = str(entry.get("confidence") or "")
    # The parent source unit is already the hard structural boundary. Splitting
    # again by section_ref turns whole-document PDF runs into hundreds of tiny
    # model calls without adding ownership safety.
    if route_kind == "deterministic_no_fact":
        reason = tuple(_string_list(entry.get("reason_codes")))
        return route_kind, reason
    if primary == FALLBACK_DOMAIN:
        return route_kind, FALLBACK_DOMAIN, confidence
    if confidence == "high" and primary and primary != FALLBACK_DOMAIN:
        return route_kind, primary, confidence
    return route_kind, "mixed_or_low_confidence"


def _describe_group(entries: list[dict[str, Any]]) -> dict[str, Any]:
    selected_refs = [str(item.get("source_ref") or "") for item in entries]
    candidate_domains = sorted(
        {
            domain
            for item in entries
            for domain in _string_list(item.get("candidate_domains"))
        }
    )
    primary_domains = {
        str(item.get("primary_suggested_domain") or "")
        for item in entries
        if item.get("primary_suggested_domain")
    }
    confidences = {
        str(item.get("confidence") or "low") for item in entries
    }
    model_entries = [
        item for item in entries if item.get("route_kind") == "model_candidate"
    ]
    typed_high = (
        bool(model_entries)
        and len(model_entries) == len(entries)
        and len(primary_domains) == 1
        and FALLBACK_DOMAIN not in primary_domains
        and confidences == {"high"}
        and candidate_domains == sorted(primary_domains)
    )
    if typed_high:
        segment_kind = "typed_high_confidence_cluster"
    elif not model_entries:
        segment_kind = "deterministic_no_fact_cluster"
    elif primary_domains == {FALLBACK_DOMAIN}:
        segment_kind = "unknown_coverage_cluster"
    else:
        segment_kind = "deferred_mixed_or_low_confidence_cluster"
    return {
        "selected_refs": selected_refs,
        "segment_kind": segment_kind,
        "candidate_domains": candidate_domains,
        "primary_domain": (
            next(iter(primary_domains)) if len(primary_domains) == 1 else None
        ),
        "confidence": next(iter(confidences)) if len(confidences) == 1 else "mixed",
    }


def _narrow_issue_context(
    issue_context: list[dict[str, Any]], allowed_evidence_refs: set[str]
) -> list[dict[str, Any]]:
    result = []
    for issue in issue_context:
        evidence = set(_string_list(issue.get("evidence_refs")))
        if issue.get("scope") == "source_unit" and not (
            evidence & allowed_evidence_refs
        ):
            continue
        copied = copy.deepcopy(issue)
        if evidence:
            copied["evidence_refs"] = sorted(evidence & allowed_evidence_refs)
        result.append(copied)
    return result


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value or [] if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _string_list(value: Any) -> list[str]:
    return (
        [str(item) for item in value or [] if item is not None and str(item)]
        if isinstance(value, list)
        else []
    )
