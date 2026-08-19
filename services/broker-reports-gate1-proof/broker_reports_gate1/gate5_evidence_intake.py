"""Gate 5 evidence intake over strict metadata and Financial Case contracts."""

from __future__ import annotations

import copy
from typing import Any, Iterable

from .artifact_models import ArtifactAccessContext, ArtifactStorePort
from .gate3_metadata_source_facts import (
    GATE3_METADATA_SOURCE_FACT_COLLECTION_SCHEMA_VERSION,
    Gate3MetadataSourceFactRuntime,
    Gate3MetadataSourceFactRuntimeFactory,
)
from .gate4_financial_case_cache import (
    Gate4FinancialCaseRuntime,
    Gate4FinancialCaseRuntimeFactory,
)


GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION = "broker_reports_gate5_evidence_intake_v1"
GATE5_EVIDENCE_INTAKE_TERMINAL = "EVIDENCE_INTAKE_CONTRACT_PROVEN"

FACTORY_REQUIRED = (
    "Gate5EvidenceIntakeRuntimeFactory.create composes "
    "Gate3MetadataSourceFactRuntimeFactory.create and "
    "Gate4FinancialCaseRuntimeFactory.create",
)
FORBIDDEN = (
    "source parsing, financial or tax classification, metadata defaults, "
    "income-source or residency inference, reconciliation, relations or persistence",
)

_FINANCIAL_CATEGORIES = {
    "SECURITY_FACT": {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"},
    "INCOME_FACT": {
        "COUPON_INCOME",
        "DIVIDEND_INCOME",
        "INTEREST_INCOME",
        "SECURITIES_LENDING_INCOME",
    },
    "COMMISSION_FACT": {"COMMISSION", "TRANSACTION_CHARGE"},
    "WITHHELD_TAX_FACT": {"TAX_WITHHELD"},
    "SOURCE_TOTAL": {"COMMISSION_TOTAL", "TAX_WITHHELD_TOTAL"},
}


class Gate5EvidenceIntakeError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Gate5EvidenceIntakeRuntimeFactory:
    def __init__(self, *, store: ArtifactStorePort, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate5EvidenceIntakeRuntime":
        return Gate5EvidenceIntakeRuntime(
            metadata_runtime=Gate3MetadataSourceFactRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            financial_case=Gate4FinancialCaseRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
        )


class Gate5EvidenceIntakeRuntime:
    def __init__(
        self,
        *,
        metadata_runtime: Gate3MetadataSourceFactRuntime,
        financial_case: Gate4FinancialCaseRuntime,
    ) -> None:
        self._metadata_runtime = metadata_runtime
        self._financial_case = financial_case

    def collect(self, *, context: ArtifactAccessContext) -> dict[str, Any]:
        metadata = self._metadata_runtime.collect(context=context)
        if (
            metadata.get("schema_version")
            != GATE3_METADATA_SOURCE_FACT_COLLECTION_SCHEMA_VERSION
        ):
            raise Gate5EvidenceIntakeError("gate5_evidence_metadata_contract_invalid")
        financial_facts = self._financial_case.list_facts(context=context)
        financial_type_counts = {
            financial_type: sum(
                fact["financial_type"] == financial_type for fact in financial_facts
            )
            for financial_type in sorted(
                {fact["financial_type"] for fact in financial_facts}
            )
        }
        return {
            "schema_version": GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION,
            "status": "typed_evidence_available",
            "terminals": [GATE5_EVIDENCE_INTAKE_TERMINAL],
            "metadata_contract": {
                "schema_version": metadata["schema_version"],
                "terminals": copy.deepcopy(metadata["terminals"]),
            },
            "documents": copy.deepcopy(metadata["documents"]),
            "metadata_facts": copy.deepcopy(metadata["metadata_facts"]),
            "financial_fact_counts": financial_type_counts,
            "coverage": {
                **copy.deepcopy(metadata["coverage"]),
                "financial_category_counts": {
                    category: sum(
                        financial_type_counts.get(financial_type, 0)
                        for financial_type in types
                    )
                    for category, types in _FINANCIAL_CATEGORIES.items()
                },
                "lost_upstream": 0,
                "invented_relations": 0,
            },
            "tax_meaning_assigned": False,
            "broker_country_to_income_source_inferred": False,
            "broker_country_to_taxpayer_residency_inferred": False,
            "reconciliation": "not_performed",
            "persistence": "none_new",
        }

    @staticmethod
    def query(
        intake: dict[str, Any], *, fact_types: Iterable[str]
    ) -> list[dict[str, Any]]:
        requested = set(fact_types)
        return [
            copy.deepcopy(fact)
            for fact in intake.get("metadata_facts", [])
            if fact.get("fact_type") in requested
        ]


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION",
    "GATE5_EVIDENCE_INTAKE_TERMINAL",
    "Gate5EvidenceIntakeError",
    "Gate5EvidenceIntakeRuntime",
    "Gate5EvidenceIntakeRuntimeFactory",
]
