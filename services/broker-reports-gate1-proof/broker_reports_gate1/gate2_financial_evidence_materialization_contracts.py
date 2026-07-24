from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .gate2_financial_evidence_decision import FinancialEvidenceDecision


FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION = (
    "broker_reports_financial_evidence_inputs_v1"
)
SOURCE_PACKAGE_SCHEMA_VERSION = (
    "broker_reports_financial_evidence_source_package_v1"
)
VALIDATED_DECISION_SCHEMA_VERSION = (
    "broker_reports_financial_evidence_validated_decision_v1"
)
MATERIALIZATION_POLICY_VERSION = (
    "broker_reports_financial_evidence_materialization_v1"
)

COMPLETENESS_VALUES = frozenset(
    {"blocked", "complete", "partial", "restricted"}
)
IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_:.\\/-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TEMPORAL_ROLES = frozenset(
    {"as_of_date", "event_date", "period", "period_end", "period_start"}
)
MEASUREMENT_ROLES = frozenset({"currency", "unit"})
MAX_LITERAL_LENGTH = 20_000


class Gate2FinancialEvidenceMaterializationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialEvidenceSourceLineage:
    document_ref: str
    page_ref: str | None = None
    table_ref: str | None = None
    row_ref: str | None = None
    cell_ref: str | None = None
    text_segment_ref: str | None = None


@dataclass(frozen=True)
class FinancialEvidenceAuthoritativeSourceValue:
    source_value_ref: str
    source_ref: str
    value_type: str
    literal_value: str
    source_evidence_refs: tuple[str, ...]
    lineage: FinancialEvidenceSourceLineage


@dataclass(frozen=True)
class Gate2FinancialEvidenceSourcePackage:
    schema_version: str
    package_ref: str
    normalization_run_ref: str
    document_ref: str
    source_scope_ref: str
    source_family_id: str
    source_values: tuple[FinancialEvidenceAuthoritativeSourceValue, ...]
    source_evidence_refs: tuple[str, ...]
    completeness: str
    restriction_codes: tuple[str, ...]
    issue_refs: tuple[str, ...]
    integrity_hash: str


@dataclass(frozen=True)
class FinancialEvidenceExecutionMetadata:
    execution_ref: str
    decision_validation_ref: str


@dataclass(frozen=True)
class FinancialEvidenceValidatedDecision:
    schema_version: str
    decision_schema_version: str
    decision_schema_hash: str
    registry_version: str
    registry_hash: str
    source_scope_ref: str
    source_family_id: str
    candidate_refs: tuple[str, ...]
    candidate_authority_hash: str
    decision: FinancialEvidenceDecision


def source_value_payload(
    value: FinancialEvidenceAuthoritativeSourceValue,
) -> dict[str, Any]:
    return {
        "source_value_ref": value.source_value_ref,
        "source_ref": value.source_ref,
        "value_type": value.value_type,
        "literal_value": value.literal_value,
        "source_evidence_refs": list(value.source_evidence_refs),
        "lineage": asdict(value.lineage),
    }


def normalize_comparison_value(
    *,
    literal_value: str,
    value_type: str,
) -> str:
    if value_type == "source_decimal":
        try:
            number = Decimal(literal_value)
        except InvalidOperation:
            fail("financial_evidence_decimal_invalid")
        if not number.is_finite():
            fail("financial_evidence_decimal_invalid")
        if number == 0:
            return "0"
        return format(number.normalize(), "f")
    if value_type == "source_integer":
        try:
            return str(int(literal_value))
        except ValueError:
            fail("financial_evidence_integer_invalid")
    if value_type == "source_date":
        try:
            return date.fromisoformat(literal_value).isoformat()
        except ValueError:
            fail("financial_evidence_date_invalid")
    normalized = " ".join(
        unicodedata.normalize("NFKC", literal_value).split()
    )
    if value_type == "source_currency":
        return normalized.upper()
    if value_type in {
        "source_period",
        "source_reference",
        "source_text",
        "source_unit",
    }:
        return normalized.casefold()
    fail("financial_evidence_value_type_invalid")


def source_sign(*, literal_value: str, value_type: str) -> str:
    if value_type not in {"source_decimal", "source_integer"}:
        return "not_applicable"
    number = Decimal(literal_value)
    if number < 0:
        return "negative"
    if number > 0:
        return "positive"
    return "zero"


def role_projection(
    values: list[dict[str, Any]],
    roles: frozenset[str],
) -> dict[str, str]:
    return {
        item["role_id"]: item["normalized_comparison_value"]
        for item in values
        if item["role_id"] in roles
    }


def evidence_refs(
    values: list[dict[str, Any]],
    package_refs: tuple[str, ...],
) -> list[str]:
    return sorted(
        set(package_refs).union(
            *(set(item["source_evidence_refs"]) for item in values)
        )
    )


def unique_lineage(
    values: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_hash = {
        sha256_json(item["lineage"]): item["lineage"] for item in values
    }
    return [by_hash[key] for key in sorted(by_hash)]


def sorted_identifiers(
    values: tuple[str, ...],
    *,
    field: str,
    required: bool = False,
) -> tuple[str, ...]:
    if required and not values:
        fail(f"financial_evidence_{field}_missing")
    if len(values) != len(set(values)):
        fail(f"financial_evidence_{field}_duplicate")
    for value in values:
        identifier(value, field)
    return tuple(sorted(values))


def identifier(value: Any, field: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 240
        or not IDENTIFIER_RE.fullmatch(value)
    ):
        fail(f"financial_evidence_{field}_invalid")


def sha256_json(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fail(code: str) -> None:
    raise Gate2FinancialEvidenceMaterializationError(code)
