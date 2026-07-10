from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any


FACTORY_REQUIRED = (
    "Gate2DomainCandidateFinalizerFactory.create is the only production pre-validation domain finalizer entrypoint"
)
FORBIDDEN = (
    "The domain finalizer must not create facts, choose a fact type, invent values or refs, or hide uncovered model output"
)


@dataclass(frozen=True)
class Gate2DomainCandidateFinalizerConfig:
    fill_mechanical_header_values: bool = True


class Gate2DomainCandidateFinalizerFactory:
    def __init__(
        self, config: Gate2DomainCandidateFinalizerConfig | None = None
    ) -> None:
        self.config = config or Gate2DomainCandidateFinalizerConfig()

    def create(self) -> "Gate2DomainCandidateFinalizer":
        return Gate2DomainCandidateFinalizer(self.config)


class Gate2DomainCandidateFinalizer:
    def __init__(self, config: Gate2DomainCandidateFinalizerConfig) -> None:
        self.config = config

    def finalize(
        self, *, candidate: dict[str, Any], package: dict[str, Any]
    ) -> dict[str, Any]:
        finalized = copy.deepcopy(candidate)
        expected_audit = copy.deepcopy(
            _object(package.get("expected_candidate_audit"))
        )
        finalized.update(
            {
                "schema_version": "broker_reports_source_facts_v0",
                "source_facts_set_id": package.get("expected_source_facts_set_id"),
                "extraction_run_id": package.get("extraction_run_id"),
                "normalization_run_id": package.get("normalization_run_id"),
                "case_id": package.get("case_id"),
                "package_refs": [package.get("package_artifact_ref")],
                "document_refs": [package.get("document_ref")],
                "extraction_audit": expected_audit,
                "validation_ref": None,
                "validator_status": "pending",
                "created_at": package.get("created_at"),
            }
        )
        unit = _object(package.get("source_unit"))
        selected_refs = _string_list(
            _object(package.get("coverage_expectation")).get(
                "selected_source_refs"
            )
        )
        issue_policy = _issue_policy(package)
        for fact in _dict_list(finalized.get("facts")):
            source_ref = _fact_source_ref(
                fact=fact, selected_refs=selected_refs
            )
            if source_ref:
                _finalize_fact_provenance(
                    fact=fact,
                    source_ref=source_ref,
                    package=package,
                    unit=unit,
                )
                if self.config.fill_mechanical_header_values:
                    _fill_mechanical_values(
                        fact=fact, source_ref=source_ref, package=package
                    )
            _finalize_common_value_objects(fact)
            fact["fact_id"] = "pending"
            fact["document_ref"] = package.get("document_ref")
            fact["extraction_package_ref"] = package.get(
                "package_artifact_ref"
            )
            fact["source_unit_ref"] = unit.get("unit_id")
            fact["linked_issue_refs"] = copy.deepcopy(
                issue_policy["linked_issue_refs"]
            )
            fact["issue_impact"] = copy.deepcopy(issue_policy["issue_impact"])
            fact["extraction_audit"] = copy.deepcopy(expected_audit)
            fact["validator_status"] = "pending"
            fact["validation_ref"] = None
            fact_type = str(fact.get("fact_type") or "")
            downstream = _object(fact.get("downstream_use"))
            blocked = bool(issue_policy["issue_impact"]["blocks_fact_issue_refs"])
            downstream.update(
                {
                    "downstream_usable": False
                    if blocked
                    else bool(downstream.get("downstream_usable", True)),
                    "gate3_ledger_candidate": False,
                    "cross_document_consolidation_allowed": False,
                    "tax_calculation_allowed": False,
                    "declaration_mapping_allowed": False,
                    "restriction_codes": sorted(
                        set(_string_list(downstream.get("restriction_codes")))
                    ),
                }
            )
            fact["downstream_use"] = downstream
            if blocked:
                fact["completeness"] = "blocked"
            elif (
                issue_policy["issue_impact"][
                    "limits_confirmation_issue_refs"
                ]
                and fact.get("completeness") == "complete"
            ):
                fact["completeness"] = "partial"
            if fact_type == "unknown_source_row":
                fact["confidence"] = (
                    fact.get("confidence")
                    if fact.get("confidence") in {"low", "none"}
                    else "low"
                )
                fact["completeness"] = (
                    fact.get("completeness")
                    if fact.get("completeness") in {"uncertain", "blocked"}
                    else "uncertain"
                )

        facts = _dict_list(finalized.get("facts"))
        fact_covered = sorted(
            {
                ref
                for fact in facts
                for ref in _string_list(fact.get("evidence_refs"))
                if ref in set(selected_refs)
            }
        )
        model_coverage = _object(finalized.get("coverage"))
        no_fact_results = copy.deepcopy(
            _dict_list(model_coverage.get("no_fact_results"))
        )
        no_fact_refs = {
            str(item.get("source_ref") or "") for item in no_fact_results
        }
        accounted = set(fact_covered) | no_fact_refs
        expectation = _object(package.get("coverage_expectation"))
        finalized["coverage"] = {
            "unit_coverage_ref": expectation.get("coverage_ref"),
            "selected_source_refs": selected_refs,
            "fact_covered_refs": fact_covered,
            "no_fact_results": no_fact_results,
            "rejected_refs": [],
            "pending_refs": [],
            "coverage_status": (
                "complete" if accounted == set(selected_refs) else "partial"
            ),
        }
        finalized["issue_linkage_summary"] = {
            "package_issue_refs": copy.deepcopy(
                issue_policy["linked_issue_refs"]
            ),
            "fact_issue_links_total": sum(
                len(_string_list(fact.get("linked_issue_refs")))
                for fact in facts
            ),
            "unresolved_issue_refs": sorted(
                str(item.get("issue_ref"))
                for item in _dict_list(package.get("issue_context"))
                if item.get("status") == "unresolved" and item.get("issue_ref")
            ),
        }
        return finalized


def _fact_source_ref(
    *, fact: dict[str, Any], selected_refs: list[str]
) -> str | None:
    selected = set(selected_refs)
    location = _object(fact.get("source_location"))
    for value in (
        location.get("row_ref"),
        *(_string_list(location.get("text_segment_refs"))),
        *(_string_list(fact.get("evidence_refs"))),
    ):
        if value is not None and str(value) in selected:
            return str(value)
    return selected_refs[0] if len(selected_refs) == 1 else None


def _finalize_fact_provenance(
    *,
    fact: dict[str, Any],
    source_ref: str,
    package: dict[str, Any],
    unit: dict[str, Any],
) -> None:
    projection = _object(unit.get("model_source_projection"))
    row = next(
        (
            item
            for item in _dict_list(projection.get("rows"))
            if str(item.get("row_ref") or "") == source_ref
        ),
        None,
    )
    segment = next(
        (
            item
            for item in _dict_list(projection.get("segments"))
            if str(item.get("text_segment_ref") or "") == source_ref
        ),
        None,
    )
    evidence: set[str] = {source_ref}
    if row is not None:
        row_provenance = next(
            (
                item
                for item in _dict_list(unit.get("row_provenance"))
                if str(item.get("row_ref") or "") == source_ref
            ),
            {},
        )
        cell_refs = sorted(
            str(item.get("cell_ref"))
            for item in _dict_list(row.get("cells"))
            if item.get("cell_ref")
        )
        location = {
            "private_slice_artifact_ref": unit.get(
                "private_slice_artifact_ref"
            ),
            "slice_ref": unit.get("slice_ref"),
            "source_granularity": "table_row",
            "page_ref": None,
            "section_ref": None,
            "table_ref": unit.get("table_ref"),
            "row_ref": source_ref,
            "row_range_ref": row_provenance.get("row_range_ref")
            or unit.get("row_range_ref"),
            "cell_refs": cell_refs,
            "text_segment_refs": [],
            "parser_ref": unit.get("parser_ref"),
            "source_checksum_ref": unit.get("source_checksum_ref"),
        }
    elif segment is not None:
        provenance = next(
            (
                item
                for item in _dict_list(unit.get("segment_provenance"))
                if str(item.get("text_segment_ref") or "") == source_ref
            ),
            {},
        )
        location = {
            "private_slice_artifact_ref": unit.get(
                "private_slice_artifact_ref"
            ),
            "slice_ref": unit.get("slice_ref"),
            "source_granularity": "text_segment",
            "page_ref": provenance.get("page_ref"),
            "section_ref": provenance.get("section_ref"),
            "table_ref": None,
            "row_ref": None,
            "row_range_ref": None,
            "cell_refs": [],
            "text_segment_refs": [source_ref],
            "parser_ref": unit.get("parser_ref"),
            "source_checksum_ref": unit.get("source_checksum_ref"),
        }
    else:
        return
    for field in (
        "page_ref",
        "section_ref",
        "table_ref",
        "row_ref",
        "row_range_ref",
        "parser_ref",
        "source_checksum_ref",
    ):
        if location.get(field):
            evidence.add(str(location[field]))
    evidence.update(_string_list(location.get("cell_refs")))
    evidence.update(_string_list(location.get("text_segment_refs")))
    allowed = set(_string_list(package.get("allowed_evidence_refs")))
    fact["source_location"] = location
    fact["evidence_refs"] = sorted(evidence & allowed)


def _fill_mechanical_values(
    *, fact: dict[str, Any], source_ref: str, package: dict[str, Any]
) -> None:
    normalized = _object(fact.get("normalized_values"))
    original = _object(fact.get("original_value_refs"))
    for field in (
        "date",
        "amount",
        "currency",
        "quantity",
        "rate",
        "converted_amount",
        "identifier",
        "label",
    ):
        normalized.setdefault(field, None)
        original.setdefault(field, [])
    candidates_by_field: dict[str, list[dict[str, Any]]] = {}
    for item in _dict_list(package.get("deterministic_value_candidates")):
        if str(item.get("source_ref") or "") != source_ref:
            continue
        candidates_by_field.setdefault(str(item.get("field") or ""), []).append(
            item
        )
    for field, candidates in candidates_by_field.items():
        if len(candidates) != 1 or field not in normalized:
            continue
        item = candidates[0]
        refs = _string_list(original.get(field))
        value = normalized.get(field)
        if not refs and value is None:
            original[field] = [str(item["source_value_ref"])]
            normalized[field] = str(item["normalized_value"])
        elif not refs and str(value) == str(item["normalized_value"]):
            original[field] = [str(item["source_value_ref"])]
        elif refs == [str(item["source_value_ref"])] and value is None:
            normalized[field] = str(item["normalized_value"])
    fact["normalized_values"] = normalized
    fact["original_value_refs"] = original


def _finalize_common_value_objects(fact: dict[str, Any]) -> None:
    normalized = _object(fact.get("normalized_values"))
    original = _object(fact.get("original_value_refs"))
    mappings = {
        "date": (
            "date",
            {
                "value": normalized.get("date"),
                "role": "source_visible_date",
                "precision": "day",
                "original_value_refs": _string_list(original.get("date")),
            },
        ),
        "amount": (
            "amount",
            {
                "value_decimal": normalized.get("amount"),
                "amount_role": "source_visible_amount",
                "currency": normalized.get("currency"),
                "original_value_refs": _string_list(original.get("amount")),
            },
        ),
        "currency": (
            "currency",
            {
                "code": normalized.get("currency"),
                "code_kind": "iso_4217_visible",
                "original_value_refs": _string_list(original.get("currency")),
            },
        ),
        "quantity": (
            "quantity",
            {
                "value_decimal": normalized.get("quantity"),
                "unit": "source_visible_units",
                "original_value_refs": _string_list(original.get("quantity")),
            },
        ),
    }
    for normalized_field, (object_field, value) in mappings.items():
        fact[object_field] = value if normalized.get(normalized_field) is not None else None
    if normalized.get("identifier") is None:
        fact["instrument"] = None
    else:
        fact["instrument"] = {
            "safe_label": None,
            "safe_label_ref": None,
            "identifiers": [
                {
                    "identifier_type": "unknown_visible_identifier",
                    "identifier_value": normalized.get("identifier"),
                    "original_value_refs": _string_list(
                        original.get("identifier")
                    ),
                }
            ],
        }


def _issue_policy(package: dict[str, Any]) -> dict[str, Any]:
    impact = {
        "warning_issue_refs": [],
        "limits_confirmation_issue_refs": [],
        "blocks_fact_issue_refs": [],
        "blocks_consolidation_issue_refs": [],
        "blocks_declaration_issue_refs": [],
        "forbidden_assumption_codes": sorted(
            _string_list(package.get("forbidden_assumptions"))
        ),
    }
    mapping = {
        "warning": "warning_issue_refs",
        "limits_confirmation": "limits_confirmation_issue_refs",
        "blocks_fact": "blocks_fact_issue_refs",
        "blocks_consolidation": "blocks_consolidation_issue_refs",
        "blocks_declaration": "blocks_declaration_issue_refs",
    }
    for item in _dict_list(package.get("issue_context")):
        key = mapping.get(str(item.get("impact") or ""))
        if key and item.get("issue_ref"):
            impact[key].append(str(item["issue_ref"]))
    for key in mapping.values():
        impact[key] = sorted(set(impact[key]))
    return {
        "linked_issue_refs": sorted(
            _string_list(package.get("allowed_issue_refs"))
        ),
        "issue_impact": impact,
    }


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
