from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .gate2_financial_domain_contracts import (
    sha256_json,
    validate_financial_domain_query_response,
)
from .gate2_financial_domain_query import Gate2FinancialDomainQuery


GATE3_FINANCIAL_DOMAIN_CONTEXT_SCHEMA_VERSION = (
    "broker_reports_gate3_financial_domain_context_v1"
)
GATE3_FINANCIAL_DOMAIN_CONTEXT_POLICY_VERSION = (
    "broker_reports_gate3_financial_domain_context_policy_v1"
)
FACTORY_REQUIRED = (
    "Gate3FinancialDomainContextFactory.create is the only Gate 3 "
    "financial-domain context consumer entrypoint"
)
FORBIDDEN = (
    "The Gate 3 financial-domain consumer must not read ArtifactStore, "
    "source documents, Gate 1 payloads, provider output, Knowledge, RAG "
    "or filesystem state"
)
_FACTORY_TOKEN = object()
_DEFAULT_PAGE_LIMIT = 100


class Gate3FinancialDomainContextError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# OWNER:
# Sole Gate 3 consumer boundary for the Financial Domain Query API.
#
# REUSE:
# Call Gate3FinancialDomainContextFactory.create(...).
#
# MUST NOT:
# Gate 3 must not read Gate 1, storage, provider output or raw records.
class Gate3FinancialDomainContextFactory:
    def __init__(
        self,
        *,
        query: Gate2FinancialDomainQuery,
        page_limit: int = _DEFAULT_PAGE_LIMIT,
    ) -> None:
        if type(query) is not Gate2FinancialDomainQuery:
            _fail("gate3_financial_domain_query_authority_invalid")
        if (
            not isinstance(page_limit, int)
            or isinstance(page_limit, bool)
            or page_limit < 1
            or page_limit > _DEFAULT_PAGE_LIMIT
        ):
            _fail("gate3_financial_domain_page_limit_invalid")
        self._query = query
        self._page_limit = page_limit

    def create(self) -> "Gate3FinancialDomainContextConsumer":
        return Gate3FinancialDomainContextConsumer(
            query=self._query,
            page_limit=self._page_limit,
            _factory_token=_FACTORY_TOKEN,
        )


class Gate3FinancialDomainContextConsumer:
    def __init__(
        self,
        *,
        query: Gate2FinancialDomainQuery,
        page_limit: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            _fail("gate3_financial_domain_consumer_factory_required")
        self._query = query
        self._page_limit = page_limit

    def build_context(self) -> dict[str, Any]:
        catalog = self._read_all(
            query_kind="describe_domain",
            call=self._query.describe_domain,
        )
        typed = self._read_all(
            query_kind="query_typed_records",
            call=self._query.query_typed_records,
            include_provenance=True,
        )
        unclassified = self._read_all(
            query_kind="query_unclassified_records",
            call=self._query.query_unclassified_records,
            include_provenance=True,
        )
        coverage = self._read_all(
            query_kind="get_coverage",
            call=self._query.get_coverage,
        )
        provenance = self._read_all(
            query_kind="get_provenance",
            call=self._query.get_provenance,
        )
        responses = (
            catalog,
            typed,
            unclassified,
            coverage,
            provenance,
        )
        self._validate_common_authority(responses)
        self._validate_exact_parity(
            catalog=catalog,
            typed=typed,
            unclassified=unclassified,
            coverage=coverage,
            provenance=provenance,
        )
        payload = {
            "schema_version": (GATE3_FINANCIAL_DOMAIN_CONTEXT_SCHEMA_VERSION),
            "policy_version": (GATE3_FINANCIAL_DOMAIN_CONTEXT_POLICY_VERSION),
            "domain_snapshot": catalog["domain_snapshot"],
            "semantic_pack_identity": catalog["semantic_pack_identity"],
            "declared_scope": catalog["declared_scope"],
            "coverage": coverage["coverage"],
            "typed_records": typed["results"],
            "unclassified_records": unclassified["results"],
            "coverage_records": coverage["results"],
            "provenance_records": provenance["results"],
            "query_receipts": {
                item["query_kind"]: {
                    "query_fingerprint": item["query_fingerprint"],
                    "matching_records_total": item["matching_records_total"],
                    "page_integrity_sha256": item["page_integrity_sha256"],
                }
                for item in responses
            },
            "proof": {
                "gate3_domain_only": "passed",
                "catalog_exact": True,
                "query_parity": "exact",
                "provenance_complete": True,
                "source_llm_calls_total": 0,
                "domain_llm_calls_total": 0,
            },
        }
        payload["integrity_sha256"] = sha256_json(payload)
        return payload

    def _read_all(
        self,
        *,
        query_kind: str,
        call: Callable[..., dict[str, Any]],
        include_provenance: bool = False,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        page_hashes: list[str] = []
        continuation: str | None = None
        seen_continuations: set[str] = set()
        authority: dict[str, Any] | None = None
        query_fingerprint: str | None = None
        matching_records_total: int | None = None
        while True:
            arguments: dict[str, Any] = {
                "limit": self._page_limit,
                "continuation": continuation,
            }
            if query_kind in {
                "query_typed_records",
                "query_unclassified_records",
            }:
                arguments["include_provenance"] = include_provenance
            response = call(**arguments)
            validate_financial_domain_query_response(response)
            if response["query_kind"] != query_kind:
                _fail("gate3_financial_domain_query_kind_mismatch")
            current_authority = _query_authority(response)
            if authority is None:
                authority = current_authority
                query_fingerprint = response["query_fingerprint"]
                matching_records_total = response["completeness_status"][
                    "matching_records_total"
                ]
            elif (
                current_authority != authority
                or response["query_fingerprint"] != query_fingerprint
                or response["completeness_status"]["matching_records_total"]
                != matching_records_total
            ):
                _fail("gate3_financial_domain_page_authority_drift")
            results.extend(response["results"])
            page_hashes.append(response["integrity_sha256"])
            continuation = response["continuation"]
            if continuation is None:
                if not response["completeness_status"]["query_result_complete"]:
                    _fail("gate3_financial_domain_query_incomplete")
                break
            if continuation in seen_continuations:
                _fail("gate3_financial_domain_continuation_cycle")
            seen_continuations.add(continuation)
        if len(results) != matching_records_total:
            _fail("gate3_financial_domain_query_count_mismatch")
        if len({sha256_json(item) for item in results}) != len(results):
            _fail("gate3_financial_domain_query_duplicate")
        return {
            **(authority or {}),
            "query_kind": query_kind,
            "query_fingerprint": query_fingerprint,
            "matching_records_total": matching_records_total,
            "page_integrity_sha256": page_hashes,
            "results": results,
        }

    @staticmethod
    def _validate_common_authority(
        responses: tuple[dict[str, Any], ...],
    ) -> None:
        authority = _query_authority(responses[0])
        if any(_query_authority(response) != authority for response in responses[1:]):
            _fail("gate3_financial_domain_query_authority_drift")

    @staticmethod
    def _validate_exact_parity(
        *,
        catalog: dict[str, Any],
        typed: dict[str, Any],
        unclassified: dict[str, Any],
        coverage: dict[str, Any],
        provenance: dict[str, Any],
    ) -> None:
        declared = catalog["declared_scope"]
        coverage_summary = coverage["coverage"]
        records = [*typed["results"], *unclassified["results"]]
        if (
            catalog["results"] != declared["declared_types"]
            or len(typed["results"]) != declared["typed_records_total"]
            or len(unclassified["results"]) != declared["unclassified_records_total"]
            or len(records) != declared["records_total"]
            or len(coverage["results"])
            != coverage_summary["declared_source_refs_total"]
        ):
            _fail("gate3_financial_domain_catalog_parity_invalid")
        terminal = coverage_summary["terminal_counts"]
        if (
            coverage_summary["coverage_status"] != "complete"
            or not coverage_summary["terminal_ownership_complete"]
            or terminal["uncovered_source_refs_total"] != 0
            or terminal["duplicate_terminal_ownership_total"] != 0
            or terminal["ownership_conflicts_total"] != 0
            or not all(item["scope_accounted"] for item in coverage["results"])
        ):
            _fail("gate3_financial_domain_coverage_incomplete")
        provenance_refs = {item["provenance_ref"] for item in provenance["results"]}
        required_provenance_refs = {item["provenance_ref"] for item in records} | {
            ref for item in coverage["results"] for ref in item["provenance_refs"]
        }
        if (
            not required_provenance_refs
            or not required_provenance_refs.issubset(provenance_refs)
            or any(
                item["provenance"]["provenance_ref"] != item["provenance_ref"]
                for item in records
            )
        ):
            _fail("gate3_financial_domain_provenance_incomplete")


def _query_authority(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain_snapshot": response["domain_snapshot"],
        "semantic_pack_identity": response["semantic_pack_identity"],
        "declared_scope": response["declared_scope"],
        "coverage": response["coverage"],
    }


def _fail(code: str) -> None:
    raise Gate3FinancialDomainContextError(code)
