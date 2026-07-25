from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .gate2_financial_evidence_decision import (
    FinancialEvidenceValueCandidate,
)
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceAuthoritativeSourceValue,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json


SOURCE_CONTEXT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_evidence_source_context_v2"
)
SOURCE_CONTEXT_POLICY_VERSION = (
    "gate2_financial_evidence_bounded_source_context_v2"
)
MAX_CONTEXT_GROUPS = 32
MAX_CONTEXT_VALUES = 128
MAX_LITERAL_CHARS = 4096
MAX_VISIBLE_CONTEXT_CHARS = 160

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceSourceContextFactory.create is the only bounded "
    "Gate 1-to-successor semantic context projection entrypoint"
)
FORBIDDEN = (
    "The context projection must not expose document, row, cell, segment, "
    "path, provenance, graph, audit or expected-answer metadata; infer a "
    "financial type; call a model; or truncate authoritative source text"
)

_SAFE_ROLE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")


class Gate2FinancialEvidenceSourceContextError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialEvidenceVisibleValueContext:
    source_value_ref: str
    literal_value: str
    column_meaning: str
    visible_label: str
    association_group: str
    group_kind: str
    row_role: str
    section_role: str

    def typed_admission_identity_payload(self) -> dict[str, Any]:
        return {
            "source_value_ref": self.source_value_ref,
            "literal_value": self.literal_value,
            "header_label": (
                self.column_meaning or self.visible_label
            ),
            "association_group": self.association_group,
            "row_role": self.row_role,
            "section_role": self.section_role,
        }


@dataclass(frozen=True)
class Gate2FinancialEvidenceSourceContext:
    source_scope_ref: str
    groups: tuple[dict[str, Any], ...]
    source_values_total: int
    visible_source_values_total: int
    deterministic_reference_values_total: int
    integrity_hash: str

    def provider_groups(self) -> list[dict[str, Any]]:
        return copy.deepcopy(list(self.groups))

    def to_private_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SOURCE_CONTEXT_SCHEMA_VERSION,
            "policy_version": SOURCE_CONTEXT_POLICY_VERSION,
            "source_scope_ref": self.source_scope_ref,
            "groups": self.provider_groups(),
            "source_values_total": self.source_values_total,
            "visible_source_values_total": (
                self.visible_source_values_total
            ),
            "deterministic_reference_values_total": (
                self.deterministic_reference_values_total
            ),
            "contains_document_refs": False,
            "contains_source_locator_refs": False,
            "contains_provenance_graph": False,
            "contains_expected_answer": False,
            "provider_calls_total": 0,
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": SOURCE_CONTEXT_SCHEMA_VERSION,
            "policy_version": SOURCE_CONTEXT_POLICY_VERSION,
            "source_scope_ref_sha256": hashlib.sha256(
                self.source_scope_ref.encode("utf-8")
            ).hexdigest(),
            "groups_total": len(self.groups),
            "source_values_total": self.source_values_total,
            "visible_source_values_total": (
                self.visible_source_values_total
            ),
            "deterministic_reference_values_total": (
                self.deterministic_reference_values_total
            ),
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "contains_document_refs": False,
            "contains_source_locator_refs": False,
            "contains_provenance_graph": False,
            "contains_expected_answer": False,
            "provider_calls_total": 0,
            "integrity_hash": self.integrity_hash,
        }


class Gate2FinancialEvidenceSourceContextFactory:
    def create(
        self,
        *,
        source_scope_ref: str,
        source_values: tuple[
            FinancialEvidenceAuthoritativeSourceValue,
            ...,
        ],
        candidates: tuple[FinancialEvidenceValueCandidate, ...],
        gate1_packages: Iterable[dict[str, Any]],
    ) -> Gate2FinancialEvidenceSourceContext:
        packages = copy.deepcopy(tuple(gate1_packages))
        if (
            not source_scope_ref
            or not source_values
            or not candidates
            or not packages
        ):
            _fail("financial_source_context_input_invalid")
        if len(source_values) > MAX_CONTEXT_VALUES:
            _fail("financial_source_context_value_limit_exceeded")
        values = {
            item.source_value_ref: item for item in source_values
        }
        candidate_by_ref = {
            item.source_value_ref: item for item in candidates
        }
        if (
            len(values) != len(source_values)
            or len(candidate_by_ref) != len(candidates)
            or set(values) != set(candidate_by_ref)
        ):
            _fail("financial_source_context_value_identity_invalid")

        visible = financial_evidence_visible_value_contexts(
            packages=packages
        )
        visible = {
            ref: context
            for ref, context in visible.items()
            if ref in values
        }
        grouped: dict[
            tuple[str, str, str, str],
            list[dict[str, Any]],
        ] = {}
        deterministic_references: list[dict[str, Any]] = []
        for ref in sorted(values):
            value = values[ref]
            candidate = candidate_by_ref[ref]
            context = visible.get(ref)
            if value.value_type == "source_reference":
                deterministic_references.append(
                    _provider_value(
                        value=value,
                        candidate=candidate,
                        literal_value=None,
                        column_meaning=None,
                        visible_label=None,
                    )
                )
                continue
            if context is None:
                _fail("financial_source_context_visible_context_missing")
            if not context.association_group:
                _fail("financial_source_context_association_missing")
            if context.literal_value != value.literal_value:
                _fail("financial_source_context_literal_authority_mismatch")
            _bounded_literal(context.literal_value)
            column_meaning = _bounded_visible_context(
                context.column_meaning
            )
            visible_label = _bounded_visible_context(
                context.visible_label
            )
            row_role = _bounded_role(context.row_role)
            section_role = _bounded_role(context.section_role)
            key = (
                context.group_kind,
                context.association_group,
                row_role or "",
                section_role or "",
            )
            grouped.setdefault(key, []).append(
                _provider_value(
                    value=value,
                    candidate=candidate,
                    literal_value=context.literal_value,
                    column_meaning=column_meaning,
                    visible_label=visible_label,
                )
            )

        groups = [
            {
                "group_kind": group_kind,
                "row_role": row_role or None,
                "section_role": section_role or None,
                "values": sorted(
                    items,
                    key=lambda item: item["source_value_ref"],
                ),
            }
            for (
                group_kind,
                _association_group,
                row_role,
                section_role,
            ), items in sorted(grouped.items())
        ]
        if deterministic_references:
            groups.append(
                {
                    "group_kind": "deterministic_reference",
                    "row_role": None,
                    "section_role": None,
                    "values": sorted(
                        deterministic_references,
                        key=lambda item: item["source_value_ref"],
                    ),
                }
            )
        group_order = {
            "table_row": 0,
            "text_segment": 1,
            "deterministic_reference": 2,
        }
        groups.sort(
            key=lambda item: (
                group_order[item["group_kind"]],
                tuple(
                    value["source_value_ref"]
                    for value in item["values"]
                ),
            )
        )
        if not groups or len(groups) > MAX_CONTEXT_GROUPS:
            _fail("financial_source_context_group_limit_invalid")
        material = _private_material(
            source_scope_ref=source_scope_ref,
            groups=groups,
            source_values_total=len(source_values),
            visible_source_values_total=len(visible),
            deterministic_reference_values_total=len(
                deterministic_references
            ),
        )
        context = Gate2FinancialEvidenceSourceContext(
            source_scope_ref=source_scope_ref,
            groups=tuple(copy.deepcopy(groups)),
            source_values_total=len(source_values),
            visible_source_values_total=len(visible),
            deterministic_reference_values_total=len(
                deterministic_references
            ),
            integrity_hash=sha256_json(material),
        )
        validate_financial_evidence_source_context(
            context=context,
            source_scope_ref=source_scope_ref,
            source_values=source_values,
            candidates=candidates,
        )
        return context


def validate_financial_evidence_source_context(
    *,
    context: Gate2FinancialEvidenceSourceContext,
    source_scope_ref: str,
    source_values: tuple[
        FinancialEvidenceAuthoritativeSourceValue,
        ...,
    ],
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
) -> None:
    if (
        not isinstance(context, Gate2FinancialEvidenceSourceContext)
        or context.source_scope_ref != source_scope_ref
        or context.source_values_total != len(source_values)
        or context.source_values_total != len(candidates)
        or not context.groups
        or len(context.groups) > MAX_CONTEXT_GROUPS
    ):
        _fail("financial_source_context_identity_invalid")
    material = _private_material(
        source_scope_ref=context.source_scope_ref,
        groups=context.provider_groups(),
        source_values_total=context.source_values_total,
        visible_source_values_total=(
            context.visible_source_values_total
        ),
        deterministic_reference_values_total=(
            context.deterministic_reference_values_total
        ),
    )
    if context.integrity_hash != sha256_json(material):
        _fail("financial_source_context_integrity_invalid")
    expected_values = {
        item.source_value_ref: item for item in source_values
    }
    expected_candidates = {
        item.source_value_ref: item for item in candidates
    }
    observed_refs: list[str] = []
    visible_total = 0
    deterministic_total = 0
    for group in context.groups:
        if not isinstance(group, dict) or set(group) != {
            "group_kind",
            "row_role",
            "section_role",
            "values",
        }:
            _fail("financial_source_context_group_shape_invalid")
        if group["group_kind"] not in {
            "table_row",
            "text_segment",
            "deterministic_reference",
        }:
            _fail("financial_source_context_group_kind_invalid")
        _validate_optional_role(group["row_role"])
        _validate_optional_role(group["section_role"])
        values = group["values"]
        if (
            not isinstance(values, list)
            or not values
            or values
            != sorted(
                values,
                key=lambda item: item.get("source_value_ref", ""),
            )
        ):
            _fail("financial_source_context_group_values_invalid")
        for item in values:
            _validate_provider_value(
                item=item,
                group_kind=group["group_kind"],
                expected_values=expected_values,
                expected_candidates=expected_candidates,
            )
            observed_refs.append(item["source_value_ref"])
            if group["group_kind"] == "deterministic_reference":
                deterministic_total += 1
            else:
                visible_total += 1
    if (
        sorted(observed_refs) != sorted(expected_values)
        or len(observed_refs) != len(set(observed_refs))
        or visible_total != context.visible_source_values_total
        or deterministic_total
        != context.deterministic_reference_values_total
        or visible_total + deterministic_total
        != context.source_values_total
    ):
        _fail("financial_source_context_coverage_invalid")


def financial_evidence_visible_value_contexts(
    *,
    packages: tuple[dict[str, Any], ...],
) -> dict[str, FinancialEvidenceVisibleValueContext]:
    result: dict[str, FinancialEvidenceVisibleValueContext] = {}
    for package in packages:
        unit = package.get("source_unit") or {}
        projection = unit.get("model_source_projection") or {}
        default_section_role = str(
            unit.get("section_role")
            or unit.get("section_kind")
            or ""
        )
        for row in projection.get("rows") or []:
            association_group = str(row.get("row_ref") or "")
            row_role = str(
                row.get("row_role")
                or row.get("row_kind")
                or ""
            )
            for cell in row.get("cells") or []:
                literal = cell.get("value")
                refs = cell.get("source_value_refs") or [
                    cell.get("source_value_ref")
                ]
                if not isinstance(literal, str) or not literal:
                    continue
                for ref in refs:
                    normalized_ref = str(ref or "")
                    if normalized_ref:
                        _insert_context(
                            result=result,
                            context=FinancialEvidenceVisibleValueContext(
                                source_value_ref=normalized_ref,
                                literal_value=literal,
                                column_meaning=str(
                                    cell.get("header_label") or ""
                                ),
                                visible_label="",
                                association_group=association_group,
                                group_kind="table_row",
                                row_role=row_role,
                                section_role=default_section_role,
                            ),
                        )
        for segment in projection.get("segments") or []:
            ref = str(segment.get("source_value_ref") or "")
            literal = segment.get("value")
            if not ref or not isinstance(literal, str) or not literal:
                continue
            _insert_context(
                result=result,
                context=FinancialEvidenceVisibleValueContext(
                    source_value_ref=ref,
                    literal_value=literal,
                    column_meaning="",
                    visible_label=str(
                        segment.get("visible_label")
                        or segment.get("label")
                        or ""
                    ),
                    association_group=str(
                        segment.get("text_segment_ref") or ref
                    ),
                    group_kind="text_segment",
                    row_role="",
                    section_role=str(
                        segment.get("section_role")
                        or default_section_role
                    ),
                ),
            )
    return result


def _private_material(
    *,
    source_scope_ref: str,
    groups: list[dict[str, Any]],
    source_values_total: int,
    visible_source_values_total: int,
    deterministic_reference_values_total: int,
) -> dict[str, Any]:
    return {
        "schema_version": SOURCE_CONTEXT_SCHEMA_VERSION,
        "policy_version": SOURCE_CONTEXT_POLICY_VERSION,
        "source_scope_ref": source_scope_ref,
        "groups": copy.deepcopy(groups),
        "source_values_total": source_values_total,
        "visible_source_values_total": visible_source_values_total,
        "deterministic_reference_values_total": (
            deterministic_reference_values_total
        ),
        "contains_document_refs": False,
        "contains_source_locator_refs": False,
        "contains_provenance_graph": False,
        "contains_expected_answer": False,
        "provider_calls_total": 0,
    }


def _provider_value(
    *,
    value: FinancialEvidenceAuthoritativeSourceValue,
    candidate: FinancialEvidenceValueCandidate,
    literal_value: str | None,
    column_meaning: str | None,
    visible_label: str | None,
) -> dict[str, Any]:
    return {
        "source_value_ref": value.source_value_ref,
        "value_type": value.value_type,
        "literal_value": literal_value,
        "allowed_roles": list(candidate.allowed_roles),
        "column_meaning": column_meaning,
        "visible_label": visible_label,
    }


def _validate_provider_value(
    *,
    item: dict[str, Any],
    group_kind: str,
    expected_values: dict[
        str,
        FinancialEvidenceAuthoritativeSourceValue,
    ],
    expected_candidates: dict[str, FinancialEvidenceValueCandidate],
) -> None:
    if not isinstance(item, dict) or set(item) != {
        "source_value_ref",
        "value_type",
        "literal_value",
        "allowed_roles",
        "column_meaning",
        "visible_label",
    }:
        _fail("financial_source_context_value_shape_invalid")
    ref = str(item["source_value_ref"])
    value = expected_values.get(ref)
    candidate = expected_candidates.get(ref)
    if (
        value is None
        or candidate is None
        or item["value_type"] != value.value_type
        or item["allowed_roles"] != list(candidate.allowed_roles)
    ):
        _fail("financial_source_context_value_projection_invalid")
    if group_kind == "deterministic_reference":
        if (
            value.value_type != "source_reference"
            or item["literal_value"] is not None
            or item["column_meaning"] is not None
            or item["visible_label"] is not None
        ):
            _fail("financial_source_context_reference_projection_invalid")
        return
    if (
        value.value_type == "source_reference"
        or item["literal_value"] != value.literal_value
        or not isinstance(item["literal_value"], str)
    ):
        _fail("financial_source_context_literal_projection_invalid")
    _bounded_literal(item["literal_value"])
    _validate_optional_visible_context(item["column_meaning"])
    _validate_optional_visible_context(item["visible_label"])


def _insert_context(
    *,
    result: dict[str, FinancialEvidenceVisibleValueContext],
    context: FinancialEvidenceVisibleValueContext,
) -> None:
    previous = result.get(context.source_value_ref)
    if previous is not None and previous != context:
        _fail("financial_source_context_source_context_conflict")
    result[context.source_value_ref] = context


def _bounded_literal(value: str) -> None:
    if not value or len(value) > MAX_LITERAL_CHARS:
        _fail("financial_source_context_literal_limit_invalid")


def _bounded_visible_context(value: str) -> str | None:
    if not value:
        return None
    if len(value) > MAX_VISIBLE_CONTEXT_CHARS:
        _fail("financial_source_context_visible_context_limit_exceeded")
    return value


def _validate_optional_visible_context(value: Any) -> None:
    if value is not None and (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_VISIBLE_CONTEXT_CHARS
    ):
        _fail("financial_source_context_visible_context_invalid")


def _bounded_role(value: str) -> str | None:
    if not value:
        return None
    if not _SAFE_ROLE_RE.fullmatch(value):
        _fail("financial_source_context_role_invalid")
    return value


def _validate_optional_role(value: Any) -> None:
    if value is not None and (
        not isinstance(value, str)
        or not _SAFE_ROLE_RE.fullmatch(value)
    ):
        _fail("financial_source_context_role_invalid")


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceSourceContextError(code)
