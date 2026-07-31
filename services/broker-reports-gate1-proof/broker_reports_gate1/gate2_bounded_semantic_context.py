from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Iterable

from .gate2_financial_evidence_materialization_contracts import (
    Gate2FinancialEvidenceSourcePackage,
    sha256_json,
)
from .gate2_financial_evidence_source_package import (
    validate_source_package_integrity,
)


BOUNDED_SEMANTIC_CONTEXT_SCHEMA_VERSION = (
    "broker_reports_bounded_semantic_context_v1"
)
CONTEXT_SUFFICIENCY_SCHEMA_VERSION = (
    "broker_reports_context_sufficiency_decision_v1"
)

FACTORY_REQUIRED = (
    "Gate2BoundedSemanticContextFactory.create is the sole deterministic "
    "bounded-context builder subordinate to current_source_fact_orchestration"
)
FORBIDDEN = (
    "This factory must not import a Semantic Pack, accept or return a type, "
    "build a shortlist, call a model/provider, or create canonical facts"
)


class Gate2BoundedSemanticContextError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2BoundedSemanticContextConfig:
    maximum_neighbor_rows_each_side: int = 2
    maximum_parent_rows: int = 2
    maximum_group_labels: int = 4
    maximum_footnotes: int = 4
    maximum_section_depth: int = 6
    maximum_text_characters: int = 2_000
    maximum_request_characters: int = 24_000
    maximum_request_bytes: int = 32_000


@dataclass(frozen=True)
class Gate2BoundedSemanticContext:
    schema_version: str
    payload: dict[str, Any]
    present_facets: tuple[str, ...]
    source_package_integrity_hash: str
    source_binding_hash: str
    context_truncated: bool
    provider_calls_total: int
    integrity_hash: str

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "present_facets": list(self.present_facets),
            "source_package_integrity_hash": (
                self.source_package_integrity_hash
            ),
            "source_binding_hash": self.source_binding_hash,
            "context_truncated": self.context_truncated,
            "provider_calls_total": self.provider_calls_total,
            "contains_source_refs": False,
            "contains_canonical_type_ids": False,
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class Gate2ContextSufficiencyDecision:
    schema_version: str
    status: str
    required_facets: tuple[str, ...]
    satisfied_facets: tuple[str, ...]
    missing_facets: tuple[str, ...]
    triggered_disqualifiers: tuple[str, ...]
    context_integrity_hash: str
    source_binding_hash: str
    integrity_hash: str


class Gate2BoundedSemanticContextFactory:
    """Project source-bound context using structural relationships only."""

    def __init__(
        self,
        config: Gate2BoundedSemanticContextConfig | None = None,
    ) -> None:
        self.config = config or Gate2BoundedSemanticContextConfig()
        _validate_config(self.config)

    def create(
        self,
        *,
        source_package: Gate2FinancialEvidenceSourcePackage,
        selected_source_refs: Iterable[str],
        gate2_packages: Iterable[dict[str, Any]],
    ) -> Gate2BoundedSemanticContext:
        validate_source_package_integrity(source_package)
        selected = tuple(sorted({str(item) for item in selected_source_refs}))
        packages = tuple(copy.deepcopy(tuple(gate2_packages)))
        if not selected or not packages:
            _fail("bounded_context_source_boundary_empty")

        occurrences = _selected_ref_occurrences(packages, selected)
        if any(not items for items in occurrences.values()):
            _fail("bounded_context_source_unit_package_mismatch")
        if any(len(items) != 1 for items in occurrences.values()):
            _fail("bounded_context_selected_ref_not_unique")
        target_indexes = sorted(
            {items[0] for items in occurrences.values()}
        )
        target_packages = tuple(packages[index] for index in target_indexes)
        if any(
            package.get("document_ref") != source_package.document_ref
            for package in target_packages
        ):
            _fail("bounded_context_cross_document_source")

        document_context = _document_context(target_packages)
        target_rows = _target_rows(target_packages, selected)
        table_context = _table_context(target_packages, target_rows)
        section_context, section_truncated = _section_context(
            target_packages,
            config=self.config,
        )
        normalized_values = _normalized_values(source_package)
        visible_labels = _visible_labels(
            source_package=source_package,
            target_rows=target_rows,
            table_context=table_context,
        )
        target_unit = {
            "raw_cells": [
                copy.deepcopy(row["raw_cells"]) for row in target_rows
            ],
            "normalized_values": normalized_values,
            "visible_labels": visible_labels,
            "row_role": _single_nonempty(
                [str(row.get("row_role") or "") for row in target_rows]
            ),
            "row_ordinal": min(
                (int(row["row_ordinal"]) for row in target_rows),
                default=0,
            ),
        }
        local_context, local_truncated = _local_context(
            packages=packages,
            targets=target_packages,
            target_rows=target_rows,
            config=self.config,
        )
        restrictions = _quality_and_restrictions(
            target_packages,
            source_package=source_package,
        )
        payload = {
            "schema_version": BOUNDED_SEMANTIC_CONTEXT_SCHEMA_VERSION,
            "document_context": document_context,
            "section_context": section_context,
            "table_context": table_context,
            "target_unit": target_unit,
            "local_structural_context": local_context,
            "quality_and_restrictions": restrictions,
        }
        payload, text_truncated = _bound_text(payload, self.config)
        truncated = section_truncated or local_truncated or text_truncated
        if truncated:
            payload["quality_and_restrictions"]["context_truncated"] = True
        missing = _missing_standard_facets(payload)
        payload["quality_and_restrictions"]["missing_facets"] = missing
        payload, request_truncated = _bound_request(payload, self.config)
        truncated = truncated or request_truncated
        if request_truncated:
            payload["quality_and_restrictions"]["context_truncated"] = True
            payload["quality_and_restrictions"]["missing_facets"] = sorted(
                {
                    *payload["quality_and_restrictions"]["missing_facets"],
                    "request_budget",
                }
            )

        source_binding = {
            "source_package_integrity_hash": source_package.integrity_hash,
            "selected_source_refs_hash": sha256_json(list(selected)),
            "target_package_hashes": sorted(
                sha256_json(package) for package in target_packages
            ),
        }
        present_facets = _present_facets(payload)
        material = {
            "schema_version": BOUNDED_SEMANTIC_CONTEXT_SCHEMA_VERSION,
            "payload": payload,
            "present_facets": list(present_facets),
            "source_package_integrity_hash": source_package.integrity_hash,
            "source_binding_hash": sha256_json(source_binding),
            "context_truncated": truncated,
            "provider_calls_total": 0,
        }
        return Gate2BoundedSemanticContext(
            schema_version=BOUNDED_SEMANTIC_CONTEXT_SCHEMA_VERSION,
            payload=copy.deepcopy(payload),
            present_facets=present_facets,
            source_package_integrity_hash=source_package.integrity_hash,
            source_binding_hash=sha256_json(source_binding),
            context_truncated=truncated,
            provider_calls_total=0,
            integrity_hash=sha256_json(material),
        )

    def ablate(
        self,
        *,
        context: Gate2BoundedSemanticContext,
        variant: str,
    ) -> Gate2BoundedSemanticContext:
        """Create a deterministic model-visible context ablation A-F."""

        _validate_context(context)
        if variant == "full_bounded_context":
            return copy.deepcopy(context)
        allowed = {
            "values_only",
            "normalized_roles_only",
            "raw_headers_added",
            "section_and_table_added",
            "local_structural_context_added",
        }
        if variant not in allowed:
            _fail("bounded_context_ablation_variant_invalid")
        source = context.payload
        payload = copy.deepcopy(source)
        payload["document_context"] = {
            key: "" for key in source["document_context"]
        }
        payload["section_context"] = {
            "section_path": [],
            "table_title": "",
            "group_labels": [],
            "related_notes": [],
        }
        payload["table_context"] = {
            "raw_headers": [],
            "normalized_column_roles": [],
            "header_confidence": "",
            "table_quality": "",
        }
        normalized = [
            copy.deepcopy(item)
            for item in source["target_unit"]["normalized_values"]
            if item["value_type"] != "source_text"
        ]
        kept_literals = {item["literal_value"] for item in normalized}
        payload["target_unit"]["normalized_values"] = normalized
        payload["target_unit"]["raw_cells"] = [
            [value for value in row if value in kept_literals]
            for row in source["target_unit"]["raw_cells"]
        ]
        payload["target_unit"]["visible_labels"] = []
        payload["local_structural_context"] = {
            "parent_rows": [],
            "previous_rows": [],
            "next_rows": [],
            "linked_footnotes": [],
            "continuation": {},
            "selection_rules": copy.deepcopy(
                source["local_structural_context"]["selection_rules"]
            ),
            "excluded_target_rows_total": source[
                "local_structural_context"
            ]["excluded_target_rows_total"],
        }
        if variant in {
            "normalized_roles_only",
            "raw_headers_added",
            "section_and_table_added",
            "local_structural_context_added",
        }:
            payload["table_context"]["normalized_column_roles"] = copy.deepcopy(
                source["table_context"]["normalized_column_roles"]
            )
        if variant in {
            "raw_headers_added",
            "section_and_table_added",
            "local_structural_context_added",
        }:
            payload["table_context"] = copy.deepcopy(source["table_context"])
        if variant in {
            "section_and_table_added",
            "local_structural_context_added",
        }:
            payload["section_context"] = copy.deepcopy(source["section_context"])
        if variant == "local_structural_context_added":
            payload["local_structural_context"] = copy.deepcopy(
                source["local_structural_context"]
            )
        payload["quality_and_restrictions"]["context_ablation"] = variant
        payload["quality_and_restrictions"]["missing_facets"] = (
            _missing_standard_facets(payload)
        )
        facets = _present_facets(payload)
        material = {
            "schema_version": BOUNDED_SEMANTIC_CONTEXT_SCHEMA_VERSION,
            "payload": payload,
            "present_facets": list(facets),
            "source_package_integrity_hash": (
                context.source_package_integrity_hash
            ),
            "source_binding_hash": context.source_binding_hash,
            "context_truncated": context.context_truncated,
            "provider_calls_total": 0,
        }
        return Gate2BoundedSemanticContext(
            schema_version=BOUNDED_SEMANTIC_CONTEXT_SCHEMA_VERSION,
            payload=payload,
            present_facets=facets,
            source_package_integrity_hash=(
                context.source_package_integrity_hash
            ),
            source_binding_hash=context.source_binding_hash,
            context_truncated=context.context_truncated,
            provider_calls_total=0,
            integrity_hash=sha256_json(material),
        )


class Gate2ContextSufficiencyGuard:
    """Fail closed on Pack-projected requirements after model simulation."""

    def evaluate(
        self,
        *,
        context: Gate2BoundedSemanticContext,
        type_card: dict[str, Any],
        exact_option: dict[str, Any] | None,
        expected_source_package_integrity_hash: str,
    ) -> Gate2ContextSufficiencyDecision:
        _validate_context(context)
        required = tuple(
            sorted(set(type_card.get("required_context_facets") or []))
        )
        if not required:
            _fail("context_sufficiency_requirements_empty")
        if exact_option is not None and not exact_option.get("value_bindings"):
            _fail("context_sufficiency_exact_option_invalid")
        present = set(context.present_facets)
        satisfied = tuple(
            facet
            for facet in required
            if facet in present
        )
        missing = tuple(sorted(set(required) - set(satisfied)))
        quality = context.payload["quality_and_restrictions"]
        disqualifiers: list[str] = []
        if context.context_truncated or quality.get("context_truncated"):
            disqualifiers.append("context_truncated")
        if quality.get("financial_interpretation_allowed") is not True:
            disqualifiers.append("financial_interpretation_not_allowed")
        if (
            context.source_package_integrity_hash
            != expected_source_package_integrity_hash
        ):
            disqualifiers.append("source_package_binding_mismatch")
        if _has_blocking_issue(quality.get("unresolved_issues") or []):
            disqualifiers.append("unresolved_interpretation_issue")
        status = "SUFFICIENT" if not missing and not disqualifiers else "INSUFFICIENT"
        material = {
            "schema_version": CONTEXT_SUFFICIENCY_SCHEMA_VERSION,
            "status": status,
            "required_facets": list(required),
            "satisfied_facets": list(satisfied),
            "missing_facets": list(missing),
            "triggered_disqualifiers": sorted(set(disqualifiers)),
            "context_integrity_hash": context.integrity_hash,
            "source_binding_hash": context.source_binding_hash,
        }
        return Gate2ContextSufficiencyDecision(
            schema_version=CONTEXT_SUFFICIENCY_SCHEMA_VERSION,
            status=status,
            required_facets=required,
            satisfied_facets=satisfied,
            missing_facets=missing,
            triggered_disqualifiers=tuple(sorted(set(disqualifiers))),
            context_integrity_hash=context.integrity_hash,
            source_binding_hash=context.source_binding_hash,
            integrity_hash=sha256_json(material),
        )


def validate_bounded_semantic_context(
    context: Gate2BoundedSemanticContext,
) -> None:
    _validate_context(context)


def _document_context(packages: tuple[dict[str, Any], ...]) -> dict[str, str]:
    contexts = [package.get("document_context") or {} for package in packages]
    passports = [context.get("passport") or {} for context in contexts]
    return {
        "document_type": _first(
            [
                *(item.get("document_type") for item in contexts),
                *(item.get("document_kind_candidate") for item in passports),
            ]
        ),
        "document_role": _first(item.get("document_role") for item in contexts),
        "document_title": _first(item.get("document_title") for item in contexts),
        "issuer_role": _first(item.get("issuer_role") for item in contexts),
        "reporting_period": _first(
            item.get("reporting_period") for item in contexts
        ),
        "statement_scope": _first(
            item.get("statement_scope") for item in contexts
        ),
        "account_type": _first(item.get("account_type") for item in contexts),
        "language": _first(item.get("language") for item in contexts),
    }


def _section_context(
    packages: tuple[dict[str, Any], ...],
    *,
    config: Gate2BoundedSemanticContextConfig,
) -> tuple[dict[str, Any], bool]:
    units = [package.get("source_unit") or {} for package in packages]
    paths = [
        str(label)
        for unit in units
        for label in unit.get("safe_section_labels") or []
        if label
    ]
    group_labels = [
        str(value)
        for unit in units
        for value in unit.get("group_labels") or []
        if value
    ]
    related_notes = [
        str(value)
        for unit in units
        for value in unit.get("related_notes") or []
        if value
    ]
    truncated = (
        len(paths) > config.maximum_section_depth
        or len(group_labels) > config.maximum_group_labels
        or len(related_notes) > config.maximum_footnotes
    )
    return ({
        "section_path": paths[: config.maximum_section_depth],
        "table_title": _first(unit.get("table_title") for unit in units),
        "group_labels": group_labels[: config.maximum_group_labels],
        "related_notes": related_notes[: config.maximum_footnotes],
    }, truncated)


def _table_context(
    packages: tuple[dict[str, Any], ...],
    target_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    units = [package.get("source_unit") or {} for package in packages]
    raw_headers: list[str] = []
    for row in target_rows:
        for header in row["raw_headers"]:
            if header not in raw_headers:
                raw_headers.append(header)
    roles: list[str] = []
    for unit in units:
        for item in unit.get("normalized_header_descriptors") or []:
            role = str(item.get("normalized_label") or "")
            if role and role not in roles:
                roles.append(role)
    qualities = [unit.get("table_quality") or {} for unit in units]
    return {
        "raw_headers": raw_headers,
        "normalized_column_roles": roles,
        "header_confidence": _first(
            item.get("header_confidence") for item in qualities
        ),
        "table_quality": _first(
            item.get("reconstruction_quality") for item in qualities
        ),
    }


def _target_rows(
    packages: tuple[dict[str, Any], ...],
    selected: tuple[str, ...],
) -> list[dict[str, Any]]:
    selected_set = set(selected)
    rows: list[dict[str, Any]] = []
    for package in packages:
        unit = package.get("source_unit") or {}
        ordinals = {
            str(item.get("row_ref")): int(item.get("row_ordinal") or 0)
            for item in unit.get("row_provenance") or []
        }
        for row in (unit.get("model_source_projection") or {}).get("rows") or []:
            row_ref = str(row.get("row_ref") or "")
            if row_ref not in selected_set:
                continue
            cells = row.get("cells") or []
            rows.append(
                {
                    "row_ref": row_ref,
                    "row_ordinal": ordinals.get(row_ref, 0),
                    "row_role": str(
                        row.get("row_role") or row.get("row_kind") or ""
                    ),
                    "raw_cells": [str(cell.get("value") or "") for cell in cells],
                    "raw_headers": [
                        str(cell.get("header_label") or "") for cell in cells
                    ],
                }
            )
    if not rows:
        _fail("bounded_context_target_row_missing")
    return sorted(rows, key=lambda item: (item["row_ordinal"], item["row_ref"]))


def _normalized_values(
    source_package: Gate2FinancialEvidenceSourcePackage,
) -> list[dict[str, str]]:
    return [
        {
            "local_value_key": f"v{index:02d}",
            "value_type": value.value_type,
            "literal_value": value.literal_value,
        }
        for index, value in enumerate(
            (
                item
                for item in source_package.source_values
                if item.value_type != "source_reference"
            ),
            start=1,
        )
    ]


def _visible_labels(
    *,
    source_package: Gate2FinancialEvidenceSourcePackage,
    target_rows: list[dict[str, Any]],
    table_context: dict[str, Any],
) -> list[str]:
    meaningful_header = any(
        _meaningful_header(item) for item in table_context["raw_headers"]
    ) and bool(table_context["normalized_column_roles"])
    if not meaningful_header:
        return []
    literals = {
        item.literal_value
        for item in source_package.source_values
        if item.value_type == "source_text"
    }
    return [
        value
        for row in target_rows
        for value in row["raw_cells"]
        if value in literals
    ]


def _local_context(
    *,
    packages: tuple[dict[str, Any], ...],
    targets: tuple[dict[str, Any], ...],
    target_rows: list[dict[str, Any]],
    config: Gate2BoundedSemanticContextConfig,
) -> tuple[dict[str, Any], bool]:
    target_document = targets[0].get("document_ref")
    target_tables = {
        str((package.get("source_unit") or {}).get("table_ref") or "")
        for package in targets
    }
    structural_rows: list[dict[str, Any]] = []
    for package in packages:
        unit = package.get("source_unit") or {}
        if (
            package.get("document_ref") != target_document
            or str(unit.get("table_ref") or "") not in target_tables
        ):
            continue
        ordinals = {
            str(item.get("row_ref")): int(item.get("row_ordinal") or 0)
            for item in unit.get("row_provenance") or []
        }
        for row in (unit.get("model_source_projection") or {}).get("rows") or []:
            structural_rows.append(
                {
                    "row_ref": str(row.get("row_ref") or ""),
                    "row_ordinal": ordinals.get(str(row.get("row_ref") or ""), 0),
                    "row_role": str(
                        row.get("row_role") or row.get("row_kind") or ""
                    ),
                    "raw_cells": [
                        str(cell.get("value") or "")
                        for cell in row.get("cells") or []
                    ],
                }
            )
    unique = {
        item["row_ref"]: item for item in structural_rows if item["row_ref"]
    }
    ordered = sorted(unique.values(), key=lambda item: (item["row_ordinal"], item["row_ref"]))
    target_refs = {item["row_ref"] for item in target_rows}
    target_ordinals = [item["row_ordinal"] for item in target_rows]
    low = min(target_ordinals)
    high = max(target_ordinals)
    previous = [item for item in ordered if item["row_ordinal"] < low]
    following = [item for item in ordered if item["row_ordinal"] > high]
    previous_selected = previous[-config.maximum_neighbor_rows_each_side :]
    next_selected = following[: config.maximum_neighbor_rows_each_side]
    truncated = (
        len(previous) > len(previous_selected)
        or len(following) > len(next_selected)
    )
    units = [package.get("source_unit") or {} for package in targets]
    parent_rows = [
        copy.deepcopy(item)
        for unit in units
        for item in unit.get("parent_rows") or []
    ]
    footnotes = [
        copy.deepcopy(item)
        for unit in units
        for item in unit.get("linked_footnotes") or []
    ]
    if len(parent_rows) > config.maximum_parent_rows:
        truncated = True
    if len(footnotes) > config.maximum_footnotes:
        truncated = True
    continuation = next(
        (
            copy.deepcopy(unit.get("continuation"))
            for unit in units
            if unit.get("continuation")
        ),
        {},
    )
    return (
        {
            "parent_rows": parent_rows[: config.maximum_parent_rows],
            "previous_rows": [_public_row(item) for item in previous_selected],
            "next_rows": [_public_row(item) for item in next_selected],
            "linked_footnotes": footnotes[: config.maximum_footnotes],
            "continuation": continuation,
            "selection_rules": [
                "same_document",
                "same_table_identity",
                "contiguous_row_ordinal",
                "explicit_parent_footnote_or_continuation_only",
            ],
            "excluded_target_rows_total": len(target_refs),
        },
        truncated,
    )


def _quality_and_restrictions(
    packages: tuple[dict[str, Any], ...],
    *,
    source_package: Gate2FinancialEvidenceSourcePackage,
) -> dict[str, Any]:
    units = [package.get("source_unit") or {} for package in packages]
    issues = [
        {
            key: copy.deepcopy(issue.get(key))
            for key in (
                "issue_type",
                "status",
                "affected_stage",
                "impact",
                "blocked_stages",
                "stages_that_may_continue",
            )
            if issue.get(key) is not None
        }
        for package in packages
        for issue in package.get("issue_context") or []
        if issue.get("status") == "unresolved"
    ]
    contexts = [package.get("document_context") or {} for package in packages]
    return {
        "source_input_mode": _first(
            unit.get("source_input_mode") for unit in units
        ),
        "source_representation": _first(
            (unit.get("upstream_source_representation") or {}).get(
                "source_representation_kind"
            )
            for unit in units
        ),
        "context_truncated": False,
        "missing_facets": [],
        "unresolved_issues": issues,
        "financial_interpretation_allowed": all(
            context.get("financial_interpretation_allowed") is True
            for context in contexts
        ),
        "source_package_completeness": source_package.completeness,
        "source_package_restrictions": list(source_package.restriction_codes),
    }


def _present_facets(payload: dict[str, Any]) -> tuple[str, ...]:
    document = payload["document_context"]
    section = payload["section_context"]
    table = payload["table_context"]
    target = payload["target_unit"]
    quality = payload["quality_and_restrictions"]
    types = {
        item["value_type"] for item in target["normalized_values"]
    }
    facets: set[str] = set()
    if "source_decimal" in types or "source_integer" in types:
        facets.add("amount")
    if "source_date" in types:
        facets.update({"as_of_date", "date_or_period"})
    if "source_period" in types:
        facets.update({"period", "date_or_period"})
    if {"source_currency", "source_unit"} & types:
        facets.add("currency_or_unit")
    if document.get("statement_scope"):
        facets.update({"statement_scope", "reporting_scope"})
    if target.get("visible_labels"):
        facets.update(
            {"balance_class", "printed_label_evidence_ref", "source_label"}
        )
    if any(_meaningful_header(item) for item in table.get("raw_headers") or []):
        facets.add("raw_headers")
    if table.get("normalized_column_roles"):
        facets.add("normalized_column_roles")
    if section.get("section_path"):
        facets.add("section_path")
    if section.get("table_title"):
        facets.add("table_title")
    if section.get("group_labels"):
        facets.add("group_labels")
    if quality.get("financial_interpretation_allowed") is True:
        facets.add("financial_interpretation_allowed")
    return tuple(sorted(facets))


def _missing_standard_facets(payload: dict[str, Any]) -> list[str]:
    checks = {
        "document_type": payload["document_context"].get("document_type"),
        "document_role": payload["document_context"].get("document_role"),
        "document_title": payload["document_context"].get("document_title"),
        "issuer_role": payload["document_context"].get("issuer_role"),
        "reporting_period": payload["document_context"].get("reporting_period"),
        "account_type": payload["document_context"].get("account_type"),
        "language": payload["document_context"].get("language"),
        "section_path": payload["section_context"].get("section_path"),
        "table_title": payload["section_context"].get("table_title"),
        "group_labels": payload["section_context"].get("group_labels"),
        "raw_headers": any(
            _meaningful_header(item)
            for item in payload["table_context"].get("raw_headers") or []
        ),
        "normalized_column_roles": payload["table_context"].get(
            "normalized_column_roles"
        ),
    }
    return sorted(key for key, value in checks.items() if not value)


def _selected_ref_occurrences(
    packages: tuple[dict[str, Any], ...],
    selected: tuple[str, ...],
) -> dict[str, list[int]]:
    result = {ref: [] for ref in selected}
    for index, package in enumerate(packages):
        row_refs = set((package.get("source_unit") or {}).get("row_refs") or [])
        for ref in selected:
            if ref in row_refs:
                result[ref].append(index)
    return result


def _has_blocking_issue(issues: list[dict[str, Any]]) -> bool:
    return any(
        "source_fact_extraction" in (item.get("blocked_stages") or [])
        or item.get("impact") == "blocks_source_fact_extraction"
        for item in issues
    )


def _validate_context(context: Gate2BoundedSemanticContext) -> None:
    material = {
        "schema_version": context.schema_version,
        "payload": context.payload,
        "present_facets": list(context.present_facets),
        "source_package_integrity_hash": context.source_package_integrity_hash,
        "source_binding_hash": context.source_binding_hash,
        "context_truncated": context.context_truncated,
        "provider_calls_total": context.provider_calls_total,
    }
    if (
        context.schema_version != BOUNDED_SEMANTIC_CONTEXT_SCHEMA_VERSION
        or context.payload.get("schema_version")
        != BOUNDED_SEMANTIC_CONTEXT_SCHEMA_VERSION
        or context.provider_calls_total != 0
        or context.integrity_hash != sha256_json(material)
        or context.present_facets != _present_facets(context.payload)
    ):
        _fail("bounded_context_integrity_invalid")


def _bound_text(
    payload: dict[str, Any],
    config: Gate2BoundedSemanticContextConfig,
) -> tuple[dict[str, Any], bool]:
    truncated = False

    structural_keys = {
        "schema_version",
        "value_type",
        "local_value_key",
        "source_input_mode",
        "context_ablation",
    }

    def visit(value: Any, *, key: str = "") -> Any:
        nonlocal truncated
        if isinstance(value, dict):
            return {
                item_key: visit(item, key=item_key)
                for item_key, item in value.items()
            }
        if isinstance(value, list):
            return [visit(item, key=key) for item in value]
        if (
            isinstance(value, str)
            and key not in structural_keys
            and len(value) > config.maximum_text_characters
        ):
            truncated = True
            return value[: config.maximum_text_characters]
        return value

    return visit(copy.deepcopy(payload)), truncated


def _bound_request(
    payload: dict[str, Any],
    config: Gate2BoundedSemanticContextConfig,
) -> tuple[dict[str, Any], bool]:
    result = copy.deepcopy(payload)
    if _within_request_budget(result, config):
        return result, False
    local = result["local_structural_context"]
    local["previous_rows"] = []
    local["next_rows"] = []
    local["parent_rows"] = []
    local["linked_footnotes"] = []
    if _within_request_budget(result, config):
        return result, True
    result["section_context"]["related_notes"] = []
    result["section_context"]["group_labels"] = []
    result["target_unit"]["visible_labels"] = []
    result["target_unit"]["raw_cells"] = []
    if _within_request_budget(result, config):
        return result, True
    _fail("bounded_context_request_budget_too_small")


def _within_request_budget(
    payload: dict[str, Any],
    config: Gate2BoundedSemanticContextConfig,
) -> bool:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        len(encoded) <= config.maximum_request_characters
        and len(encoded.encode("utf-8")) <= config.maximum_request_bytes
    )


def _validate_config(config: Gate2BoundedSemanticContextConfig) -> None:
    values = (
        config.maximum_neighbor_rows_each_side,
        config.maximum_parent_rows,
        config.maximum_group_labels,
        config.maximum_footnotes,
        config.maximum_section_depth,
        config.maximum_text_characters,
        config.maximum_request_characters,
        config.maximum_request_bytes,
    )
    if any(not isinstance(value, int) or value <= 0 for value in values):
        _fail("bounded_context_budget_invalid")


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_cells": copy.deepcopy(row["raw_cells"]),
        "row_role": row["row_role"],
        "row_ordinal": row["row_ordinal"],
    }


def _meaningful_header(value: Any) -> bool:
    normalized = str(value or "").strip().casefold()
    return bool(normalized) and normalized not in {"unknown", "none", "null"} and not normalized.startswith(
        ("safe_column_", "safe_text_")
    )


def _first(values: Iterable[Any]) -> str:
    return next((str(value) for value in values if value not in {None, ""}), "")


def _single_nonempty(values: Iterable[str]) -> str:
    items = sorted({item for item in values if item})
    return items[0] if len(items) == 1 else ""


def _fail(code: str) -> None:
    raise Gate2BoundedSemanticContextError(code)
