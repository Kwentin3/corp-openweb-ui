from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .gate2_financial_domain_catalog import Gate2FinancialDomainSnapshot
from .gate2_financial_domain_contracts import (
    DEFAULT_QUERY_LIMIT,
    FINANCIAL_DOMAIN_QUERY_POLICY_VERSION,
    FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION,
    FinancialDomainQueryFilters,
    fail,
    query_fingerprint,
    query_page,
    sha256_json,
    validate_financial_domain_query_response,
    validate_timestamp,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_contract import (
    Gate2FinancialSemanticContractFactory,
)
from .gate2_financial_semantic_model_assets import (
    load_gate2_financial_semantic_model_assets,
)


FACTORY_REQUIRED = (
    "Gate2FinancialDomainQueryFactory.create is the only server-authoritative "
    "financial domain query entrypoint"
)
FORBIDDEN = (
    "Gate 3 callers must not read ArtifactStore, source documents, Gate 1 "
    "payloads, provider output, Knowledge, RAG or filesystem state"
)
_FACTORY_TOKEN = object()


class Gate2FinancialDomainQueryFactory:
    def __init__(
        self,
        *,
        snapshot: Gate2FinancialDomainSnapshot,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        access_scope_fingerprint: str,
    ) -> None:
        self.snapshot = snapshot
        self.registry = registry
        self.access_scope_fingerprint = access_scope_fingerprint

    def create(self) -> "Gate2FinancialDomainQuery":
        self.snapshot.validate()
        semantic_contract = Gate2FinancialSemanticContractFactory(
            registry=self.registry
        ).create()
        pack = load_gate2_financial_semantic_model_assets()[
            "semantic_pack"
        ]
        semantic_pack_identity = {
            "pack_schema_version": str(pack["schema_version"]),
            "semantic_version": str(pack["semantic_version"]),
            "canonical_sha256": str(pack["integrity_sha256"]),
            "managed_asset_ref": str(pack["managed_asset_ref"]),
        }
        if (
            self.snapshot.registry_version
            != self.registry.registry_version
            or self.snapshot.registry_hash != self.registry.registry_hash
            or self.snapshot.semantic_pack_identity()
            != semantic_pack_identity
            or semantic_contract.integrity_sha256
            != semantic_pack_identity["canonical_sha256"]
        ):
            fail("financial_domain_snapshot_authority_mismatch")
        if (
            self.access_scope_fingerprint
            != self.snapshot.access_scope_fingerprint()
        ):
            fail("financial_domain_access_scope_mismatch")
        _ensure_not_expired(self.snapshot)
        return Gate2FinancialDomainQuery(
            snapshot=self.snapshot,
            access_scope_fingerprint=self.access_scope_fingerprint,
            _factory_token=_FACTORY_TOKEN,
        )


class Gate2FinancialDomainQuery:
    def __init__(
        self,
        *,
        snapshot: Gate2FinancialDomainSnapshot,
        access_scope_fingerprint: str,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            fail("financial_domain_query_factory_required")
        self.snapshot = snapshot
        self.access_scope_fingerprint = access_scope_fingerprint

    def describe_domain(
        self,
        *,
        limit: int = DEFAULT_QUERY_LIMIT,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_active()
        filters = FinancialDomainQueryFilters().normalized()
        return self._response(
            query_kind="describe_domain",
            values=list(
                self.snapshot.declared_scope()["declared_types"]
            ),
            filters=filters,
            include_provenance=False,
            limit=limit,
            continuation=continuation,
        )

    def query_typed_records(
        self,
        *,
        filters: FinancialDomainQueryFilters | None = None,
        include_provenance: bool = False,
        limit: int = DEFAULT_QUERY_LIMIT,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_active()
        normalized = _filters(filters)
        values = _filtered_records(
            records=self.snapshot.typed_records(),
            index=self.snapshot.record_index(),
            filters=normalized,
        )
        return self._response(
            query_kind="query_typed_records",
            values=_project_provenance(
                records=values,
                provenance=self.snapshot.provenance_records(),
                include=include_provenance,
            ),
            filters=normalized,
            include_provenance=include_provenance,
            limit=limit,
            continuation=continuation,
        )

    def query_unclassified_records(
        self,
        *,
        filters: FinancialDomainQueryFilters | None = None,
        include_provenance: bool = False,
        limit: int = DEFAULT_QUERY_LIMIT,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_active()
        normalized = _filters(filters)
        values = _filtered_records(
            records=self.snapshot.unclassified_records(),
            index=self.snapshot.record_index(),
            filters=normalized,
        )
        return self._response(
            query_kind="query_unclassified_records",
            values=_project_provenance(
                records=values,
                provenance=self.snapshot.provenance_records(),
                include=include_provenance,
            ),
            filters=normalized,
            include_provenance=include_provenance,
            limit=limit,
            continuation=continuation,
        )

    def get_coverage(
        self,
        *,
        filters: FinancialDomainQueryFilters | None = None,
        limit: int = DEFAULT_QUERY_LIMIT,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_active()
        normalized = _filters(filters)
        return self._response(
            query_kind="get_coverage",
            values=_filtered_index(
                self.snapshot.coverage_records(),
                normalized,
            ),
            filters=normalized,
            include_provenance=False,
            limit=limit,
            continuation=continuation,
        )

    def get_provenance(
        self,
        *,
        filters: FinancialDomainQueryFilters | None = None,
        limit: int = DEFAULT_QUERY_LIMIT,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_active()
        normalized = _filters(filters)
        matched_coverage = _filtered_index(
            self.snapshot.coverage_records(),
            normalized,
        )
        refs = {
            ref
            for item in matched_coverage
            for ref in item["provenance_refs"]
        }
        values = [
            item
            for item in self.snapshot.provenance_records()
            if item["provenance_ref"] in refs
        ]
        return self._response(
            query_kind="get_provenance",
            values=values,
            filters=normalized,
            include_provenance=True,
            limit=limit,
            continuation=continuation,
        )

    def _response(
        self,
        *,
        query_kind: str,
        values: list[dict[str, Any]],
        filters: FinancialDomainQueryFilters,
        include_provenance: bool,
        limit: int,
        continuation: str | None,
    ) -> dict[str, Any]:
        page, matched_count, returned_through, next_continuation = (
            query_page(
                values=tuple(values),
                snapshot_id=self.snapshot.snapshot_id,
                access_scope_fingerprint=(
                    self.access_scope_fingerprint
                ),
                expires_at=self.snapshot.expires_at(),
                query_kind=query_kind,
                filters=filters,
                include_provenance=include_provenance,
                limit=limit,
                continuation=continuation,
            )
        )
        coverage = self.snapshot.coverage_summary()
        final_page = next_continuation is None
        payload: dict[str, Any] = {
            "schema_version": FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION,
            "query_policy_version": (
                FINANCIAL_DOMAIN_QUERY_POLICY_VERSION
            ),
            "query_kind": query_kind,
            "domain_snapshot": self.snapshot.identity_payload(),
            "semantic_pack_identity": (
                self.snapshot.semantic_pack_identity()
            ),
            "declared_scope": self.snapshot.declared_scope(),
            "completeness_status": {
                "page_status": (
                    "complete_final_page"
                    if final_page
                    else "continued"
                ),
                "matching_records_total": matched_count,
                "records_returned_this_page": len(page),
                "records_returned_through_page": returned_through,
                "query_result_complete": final_page,
                "domain_coverage_status": coverage[
                    "coverage_status"
                ],
                "uncovered_source_refs_total": coverage[
                    "terminal_counts"
                ]["uncovered_source_refs_total"],
                "reason_codes": [],
                "source_data": self.snapshot.completeness_status,
            },
            "query_fingerprint": query_fingerprint(
                snapshot_id=self.snapshot.snapshot_id,
                query_kind=query_kind,
                filters=filters,
                include_provenance=include_provenance,
                limit=limit,
            ),
            "effective_filters": filters.to_dict(),
            "result_count": len(page),
            "limit": limit,
            "order": "record_id_asc",
            "provenance_included": include_provenance,
            "continuation": next_continuation,
            "coverage": coverage,
            "provenance_refs": _provenance_refs(page),
            "results": page,
        }
        payload["integrity_sha256"] = sha256_json(payload)
        validate_financial_domain_query_response(payload)
        return payload

    def _ensure_active(self) -> None:
        if (
            self.access_scope_fingerprint
            != self.snapshot.access_scope_fingerprint()
        ):
            fail("financial_domain_access_scope_mismatch")
        _ensure_not_expired(self.snapshot)


def _ensure_not_expired(
    snapshot: Gate2FinancialDomainSnapshot,
) -> None:
    expires_at = snapshot.expires_at()
    if expires_at is not None and validate_timestamp(
        expires_at,
        field="expires_at",
    ) <= datetime.now(timezone.utc):
        fail("financial_domain_snapshot_expired")


def _filters(
    filters: FinancialDomainQueryFilters | None,
) -> FinancialDomainQueryFilters:
    if filters is None:
        return FinancialDomainQueryFilters().normalized()
    if not isinstance(filters, FinancialDomainQueryFilters):
        fail("financial_domain_query_filter_invalid")
    return filters.normalized()


def _filtered_records(
    *,
    records: list[dict[str, Any]],
    index: list[dict[str, Any]],
    filters: FinancialDomainQueryFilters,
) -> list[dict[str, Any]]:
    records_by_id = {
        record["record_id"]: record for record in records
    }
    return [
        records_by_id[item["record_id"]]
        for item in _filtered_index(index, filters)
        if item["record_id"] in records_by_id
    ]


def _filtered_index(
    values: list[dict[str, Any]],
    filters: FinancialDomainQueryFilters,
) -> list[dict[str, Any]]:
    return [value for value in values if _matches(value, filters)]


def _matches(
    value: dict[str, Any],
    filters: FinancialDomainQueryFilters,
) -> bool:
    if (
        filters.input_type_id is not None
        and value.get("input_type_id") != filters.input_type_id
    ):
        return False
    if (
        filters.normalization_run_ref is not None
        and value.get("normalization_run_ref")
        != filters.normalization_run_ref
    ):
        return False
    if (
        filters.document_ref is not None
        and filters.document_ref not in value.get("document_refs", [])
    ):
        return False
    if (
        filters.classification_status is not None
        and value.get("classification_status")
        != filters.classification_status
    ):
        return False
    if (
        filters.period is not None
        and filters.period
        not in {
            str(item).casefold()
            for item in value.get("period_keys", [])
        }
    ):
        return False
    if (
        filters.currency is not None
        and filters.currency not in value.get("currency_keys", [])
    ):
        return False
    return True


def _project_provenance(
    *,
    records: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    include: bool,
) -> list[dict[str, Any]]:
    if not include:
        return records
    by_ref = {item["provenance_ref"]: item for item in provenance}
    result = []
    for record in records:
        projected = json.loads(json.dumps(record))
        projected["provenance"] = by_ref[record["provenance_ref"]]
        unsigned = dict(projected)
        unsigned.pop("record_sha256")
        projected["record_sha256"] = sha256_json(unsigned)
        result.append(projected)
    return result


def _provenance_refs(values: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            ref
            for item in values
            for ref in (
                [item["provenance_ref"]]
                if isinstance(item.get("provenance_ref"), str)
                else item.get("provenance_refs", [])
            )
        }
    )
