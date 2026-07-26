from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


FINANCIAL_DOMAIN_CONTRACT_VERSION = (
    "broker_reports_managed_financial_domain_contract_v1"
)
FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION = (
    "broker_reports_managed_financial_domain_snapshot_v1"
)
FINANCIAL_DOMAIN_CATALOG_SCHEMA_VERSION = (
    "broker_reports_managed_financial_domain_catalog_v1"
)
FINANCIAL_DOMAIN_COVERAGE_SCHEMA_VERSION = (
    "broker_reports_managed_financial_domain_coverage_v1"
)
FINANCIAL_DOMAIN_PROVENANCE_SCHEMA_VERSION = (
    "broker_reports_managed_financial_domain_provenance_v1"
)
FINANCIAL_DOMAIN_TYPED_RECORD_SCHEMA_VERSION = (
    "broker_reports_managed_financial_record_v1"
)
FINANCIAL_DOMAIN_UNCLASSIFIED_RECORD_SCHEMA_VERSION = (
    "broker_reports_managed_financial_unclassified_record_v1"
)
FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_domain_api_response_v1"
)
FINANCIAL_DOMAIN_QUERY_POLICY_VERSION = (
    "broker_reports_gate2_financial_domain_query_v2"
)

DEFAULT_QUERY_LIMIT = 25
MAXIMUM_QUERY_LIMIT = 200
CLASSIFICATION_STATUSES = frozenset(
    {
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }
)
QUERY_KINDS = frozenset(
    {
        "describe_domain",
        "query_typed_records",
        "query_unclassified_records",
        "get_coverage",
        "get_provenance",
    }
)
COMPLETENESS_STATUSES = frozenset(
    {"complete", "partial", "restricted", "blocked"}
)

_CURSOR_RE = re.compile(
    r"^findompage_(?P<offset>0|[1-9]\d*)_(?P<digest>[0-9a-f]{24})$"
)
_CURRENCY_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,31}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_FILTER_TEXT = 512


class Gate2FinancialDomainError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialDomainAccessContext:
    user_ref: str
    case_ref: str | None = None
    chat_ref: str | None = None
    workspace_ref: str | None = None
    source_available: bool = True

    def access_scope(self) -> "FinancialDomainAccessScope":
        values = (
            self.user_ref,
            self.case_ref,
            self.chat_ref,
            self.workspace_ref,
        )
        if (
            any(
                value is not None and not _bounded_text(value)
                for value in values
            )
            or not self.user_ref
            or (self.case_ref is None and self.chat_ref is None)
            or not isinstance(self.source_available, bool)
        ):
            fail("financial_domain_access_context_invalid")
        if not self.source_available:
            fail("financial_domain_source_unavailable")
        fingerprint = sha256_json(
            {
                "user_ref": self.user_ref,
                "case_ref": self.case_ref,
                "chat_ref": self.chat_ref,
                "workspace_ref": self.workspace_ref,
                "same_user_required": True,
                "same_case_or_chat_required": True,
                "same_workspace_required_when_present": True,
                "source_availability_required": True,
            }
        )
        return FinancialDomainAccessScope(
            access_scope_ref="findomaccess_" + fingerprint[:32],
            access_scope_fingerprint=fingerprint,
            same_workspace_required_when_present=True,
        )


@dataclass(frozen=True)
class FinancialDomainAccessScope:
    access_scope_ref: str
    access_scope_fingerprint: str
    same_workspace_required_when_present: bool = True

    def validate(self) -> None:
        if (
            not _bounded_text(self.access_scope_ref)
            or not _SHA256_RE.fullmatch(self.access_scope_fingerprint)
            or not isinstance(
                self.same_workspace_required_when_present,
                bool,
            )
        ):
            fail("financial_domain_access_scope_invalid")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "access_scope_ref": self.access_scope_ref,
            "access_scope_fingerprint": self.access_scope_fingerprint,
            "same_user_required": True,
            "same_case_or_chat_required": True,
            "same_workspace_required_when_present": (
                self.same_workspace_required_when_present
            ),
            "source_availability_required": True,
        }


@dataclass(frozen=True)
class FinancialDomainQueryFilters:
    input_type_id: str | None = None
    normalization_run_ref: str | None = None
    document_ref: str | None = None
    period: str | None = None
    currency: str | None = None
    classification_status: str | None = None

    def normalized(self) -> "FinancialDomainQueryFilters":
        identifiers = (
            self.input_type_id,
            self.normalization_run_ref,
            self.document_ref,
        )
        if any(
            value is not None and not _bounded_text(value)
            for value in identifiers
        ):
            fail("financial_domain_query_filter_invalid")
        if (
            self.classification_status is not None
            and self.classification_status not in CLASSIFICATION_STATUSES
        ):
            fail("financial_domain_query_status_invalid")
        currency = self.currency
        if currency is not None:
            if not isinstance(currency, str):
                fail("financial_domain_query_currency_invalid")
            currency = currency.strip().upper()
            if not _CURRENCY_RE.fullmatch(currency):
                fail("financial_domain_query_currency_invalid")
        period = self.period
        if period is not None:
            if not isinstance(period, str):
                fail("financial_domain_query_filter_invalid")
            period = " ".join(period.split()).casefold()
            if not period or len(period) > _MAX_FILTER_TEXT:
                fail("financial_domain_query_filter_invalid")
        return FinancialDomainQueryFilters(
            input_type_id=self.input_type_id,
            normalization_run_ref=self.normalization_run_ref,
            document_ref=self.document_ref,
            period=period,
            currency=currency,
            classification_status=self.classification_status,
        )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "input_type_id": self.input_type_id,
            "normalization_run_ref": self.normalization_run_ref,
            "document_ref": self.document_ref,
            "period": self.period,
            "currency": self.currency,
            "classification_status": self.classification_status,
        }


def query_page(
    *,
    values: tuple[dict[str, Any], ...],
    snapshot_id: str,
    access_scope_fingerprint: str,
    expires_at: str | None,
    continuation_key: bytes,
    query_kind: str,
    filters: FinancialDomainQueryFilters,
    include_provenance: bool,
    limit: int,
    continuation: str | None,
) -> tuple[list[dict[str, Any]], int, int, str | None]:
    if query_kind not in QUERY_KINDS:
        fail("financial_domain_query_kind_invalid")
    if not isinstance(include_provenance, bool):
        fail("financial_domain_query_projection_invalid")
    _validate_continuation_key(continuation_key)
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit > MAXIMUM_QUERY_LIMIT
    ):
        fail("financial_domain_query_limit_invalid")
    fingerprint = query_fingerprint(
        snapshot_id=snapshot_id,
        query_kind=query_kind,
        filters=filters,
        include_provenance=include_provenance,
        limit=limit,
    )
    offset = _cursor_offset(
        continuation=continuation,
        snapshot_id=snapshot_id,
        access_scope_fingerprint=access_scope_fingerprint,
        expires_at=expires_at,
        continuation_key=continuation_key,
        query_fingerprint_value=fingerprint,
    )
    if offset > len(values):
        fail("financial_domain_query_continuation_invalid")
    page = [
        json.loads(canonical_json(item))
        for item in values[offset : offset + limit]
    ]
    returned_through = offset + len(page)
    next_continuation = (
        _cursor(
            offset=returned_through,
            snapshot_id=snapshot_id,
            access_scope_fingerprint=access_scope_fingerprint,
            expires_at=expires_at,
            continuation_key=continuation_key,
            query_fingerprint_value=fingerprint,
        )
        if returned_through < len(values)
        else None
    )
    return page, len(values), returned_through, next_continuation


def query_fingerprint(
    *,
    snapshot_id: str,
    query_kind: str,
    filters: FinancialDomainQueryFilters,
    include_provenance: bool,
    limit: int,
) -> str:
    return sha256_json(
        {
            "domain_snapshot_id": snapshot_id,
            "query_kind": query_kind,
            "effective_filters": filters.to_dict(),
            "projection": {
                "include_provenance": include_provenance,
            },
            "page_limit": limit,
            "order": "record_id_asc",
        }
    )


def validate_timestamp(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        fail(f"financial_domain_{field}_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"financial_domain_{field}_invalid")
    if parsed.tzinfo is None:
        fail(f"financial_domain_{field}_invalid")
    return parsed.astimezone(timezone.utc)


def validate_financial_domain_query_response(
    payload: dict[str, Any],
) -> None:
    expected_keys = {
        "schema_version",
        "query_policy_version",
        "query_kind",
        "domain_snapshot",
        "semantic_pack_identity",
        "declared_scope",
        "completeness_status",
        "query_fingerprint",
        "effective_filters",
        "result_count",
        "limit",
        "order",
        "provenance_included",
        "continuation",
        "coverage",
        "provenance_refs",
        "results",
        "integrity_sha256",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        fail("financial_domain_query_response_shape_invalid")
    if (
        payload["schema_version"] != FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION
        or payload["query_policy_version"]
        != FINANCIAL_DOMAIN_QUERY_POLICY_VERSION
        or payload["query_kind"] not in QUERY_KINDS
        or payload["order"] != "record_id_asc"
        or not _SHA256_RE.fullmatch(
            str(payload["query_fingerprint"])
        )
    ):
        fail("financial_domain_query_response_version_invalid")
    completeness = payload["completeness_status"]
    if (
        not isinstance(completeness, dict)
        or set(completeness)
        != {
            "page_status",
            "matching_records_total",
            "records_returned_this_page",
            "records_returned_through_page",
            "query_result_complete",
            "domain_coverage_status",
            "uncovered_source_refs_total",
            "reason_codes",
            "source_data",
        }
        or completeness["page_status"]
        not in {"continued", "complete_final_page", "blocked"}
        or completeness["domain_coverage_status"]
        not in {"complete", "partial", "blocked"}
        or completeness["source_data"] not in COMPLETENESS_STATUSES
        or not isinstance(completeness["query_result_complete"], bool)
        or not isinstance(completeness["reason_codes"], list)
    ):
        fail("financial_domain_query_response_completeness_invalid")
    result_count = payload["result_count"]
    results = payload["results"]
    matching = completeness["matching_records_total"]
    returned_page = completeness["records_returned_this_page"]
    returned_through = completeness["records_returned_through_page"]
    limit = payload["limit"]
    if (
        not isinstance(results, list)
        or isinstance(result_count, bool)
        or not isinstance(result_count, int)
        or result_count != len(results)
        or returned_page != result_count
        or any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (matching, returned_page, returned_through, limit)
        )
        or not 1 <= limit <= MAXIMUM_QUERY_LIMIT
        or not 0 <= result_count <= limit
        or not result_count <= returned_through <= matching
    ):
        fail("financial_domain_query_response_count_invalid")
    continuation = payload["continuation"]
    continued = completeness["page_status"] == "continued"
    if (
        continued
        and (
            result_count < 1
            or not isinstance(continuation, str)
            or _CURSOR_RE.fullmatch(continuation) is None
            or completeness["query_result_complete"]
        )
    ):
        fail("financial_domain_query_response_continuation_invalid")
    if (
        not continued
        and (
            continuation is not None
            or completeness["page_status"] != "complete_final_page"
            or not completeness["query_result_complete"]
            or returned_through != matching
        )
    ):
        fail("financial_domain_query_response_final_page_invalid")
    if (
        not isinstance(payload["provenance_refs"], list)
        or payload["provenance_refs"]
        != sorted(set(payload["provenance_refs"]))
        or not isinstance(payload["provenance_included"], bool)
    ):
        fail("financial_domain_query_response_provenance_invalid")
    claimed_integrity = payload["integrity_sha256"]
    unsigned = dict(payload)
    del unsigned["integrity_sha256"]
    if (
        not isinstance(claimed_integrity, str)
        or claimed_integrity != sha256_json(unsigned)
    ):
        fail("financial_domain_query_response_integrity_invalid")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def snapshot_authority_hmac(
    *,
    schema_version: str,
    snapshot_id: str,
    snapshot_seed_sha256: str,
    integrity_sha256: str,
    registry_version: str,
    registry_hash: str,
    completeness_status: str,
    authority_key: bytes,
) -> str:
    validate_snapshot_authority_key(authority_key)
    if (
        not _bounded_text(schema_version)
        or not _bounded_text(snapshot_id)
        or not _SHA256_RE.fullmatch(snapshot_seed_sha256)
        or not _SHA256_RE.fullmatch(integrity_sha256)
        or not _bounded_text(registry_version)
        or not _SHA256_RE.fullmatch(registry_hash)
        or completeness_status not in COMPLETENESS_STATUSES
    ):
        fail("financial_domain_snapshot_authority_material_invalid")
    material = canonical_json(
        {
            "schema_version": schema_version,
            "domain_snapshot_id": snapshot_id,
            "snapshot_seed_sha256": snapshot_seed_sha256,
            "integrity_sha256": integrity_sha256,
            "registry_version": registry_version,
            "registry_hash": registry_hash,
            "completeness_status": completeness_status,
        }
    ).encode("utf-8")
    return hmac.new(authority_key, material, hashlib.sha256).hexdigest()


def validate_snapshot_authority_key(value: Any) -> None:
    if not isinstance(value, bytes) or len(value) < 32:
        fail("financial_domain_snapshot_authority_key_invalid")


def verify_snapshot_authority_hmac(
    *,
    claimed_hmac: str,
    schema_version: str,
    snapshot_id: str,
    snapshot_seed_sha256: str,
    integrity_sha256: str,
    registry_version: str,
    registry_hash: str,
    completeness_status: str,
    authority_key: bytes,
) -> None:
    if not isinstance(claimed_hmac, str) or not _SHA256_RE.fullmatch(
        claimed_hmac
    ):
        fail("financial_domain_snapshot_authority_attestation_invalid")
    expected = snapshot_authority_hmac(
        schema_version=schema_version,
        snapshot_id=snapshot_id,
        snapshot_seed_sha256=snapshot_seed_sha256,
        integrity_sha256=integrity_sha256,
        registry_version=registry_version,
        registry_hash=registry_hash,
        completeness_status=completeness_status,
        authority_key=authority_key,
    )
    if not hmac.compare_digest(claimed_hmac, expected):
        fail("financial_domain_snapshot_authority_attestation_invalid")


def fail(code: str) -> None:
    raise Gate2FinancialDomainError(code)


def _cursor(
    *,
    offset: int,
    snapshot_id: str,
    access_scope_fingerprint: str,
    expires_at: str | None,
    continuation_key: bytes,
    query_fingerprint_value: str,
) -> str:
    material = canonical_json(
        {
            "domain_snapshot_id": snapshot_id,
            "query_fingerprint": query_fingerprint_value,
            "next_record_position": offset,
            "access_scope_fingerprint": access_scope_fingerprint,
            "expires_at": expires_at,
        }
    ).encode("utf-8")
    digest = hmac.new(
        continuation_key,
        material,
        hashlib.sha256,
    ).hexdigest()[:24]
    return f"findompage_{offset}_{digest}"


def _cursor_offset(
    *,
    continuation: str | None,
    snapshot_id: str,
    access_scope_fingerprint: str,
    expires_at: str | None,
    continuation_key: bytes,
    query_fingerprint_value: str,
) -> int:
    if continuation is None:
        return 0
    if not isinstance(continuation, str):
        fail("financial_domain_query_continuation_invalid")
    match = _CURSOR_RE.fullmatch(continuation)
    if match is None:
        fail("financial_domain_query_continuation_invalid")
    offset = int(match.group("offset"))
    if continuation != _cursor(
        offset=offset,
        snapshot_id=snapshot_id,
        access_scope_fingerprint=access_scope_fingerprint,
        expires_at=expires_at,
        continuation_key=continuation_key,
        query_fingerprint_value=query_fingerprint_value,
    ):
        fail("financial_domain_query_continuation_invalid")
    return offset


def _bounded_text(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= _MAX_FILTER_TEXT
    )


def _validate_continuation_key(value: Any) -> None:
    if not isinstance(value, bytes) or len(value) < 32:
        fail("financial_domain_continuation_key_invalid")
