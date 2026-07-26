from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
CONTRACT_DOCUMENT = (
    REPOSITORY_ROOT
    / "docs/stage2/contracts/BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md"
)
CONTRACT_SCHEMA = (
    REPOSITORY_ROOT
    / "docs/stage2/contracts/BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.schema.json"
)


def _schema() -> dict[str, Any]:
    return json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))


def test_managed_financial_domain_contract_is_versioned_and_not_live_activated() -> None:
    schema = _schema()
    document = CONTRACT_DOCUMENT.read_text(encoding="utf-8")

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:broker-reports:contracts:managed-financial-domain:v1"
    assert schema["x-contract-version"] == (
        "broker_reports_managed_financial_domain_contract_v1"
    )
    assert schema["x-runtime-activation"] is False
    assert "FINANCIAL_DOMAIN_CONTRACT: VERSIONED" in document
    assert "RUNTIME_ACTIVATION: FALSE" in document


def test_consumer_boundary_has_all_required_first_class_entities() -> None:
    schema = _schema()
    defs = schema["$defs"]
    root_refs = {item["$ref"] for item in schema["oneOf"]}

    assert root_refs == {
        "#/$defs/financialRecord",
        "#/$defs/unclassifiedRecord",
        "#/$defs/domainSnapshot",
        "#/$defs/domainCatalog",
        "#/$defs/domainCoverage",
        "#/$defs/domainProvenance",
        "#/$defs/queryRequest",
        "#/$defs/queryResponse",
    }
    assert defs["financialRecord"]["properties"]["record_kind"] == {
        "const": "typed"
    }
    assert defs["unclassifiedRecord"]["properties"]["record_kind"] == {
        "const": "unclassified"
    }
    assert "input_type_id" not in defs["unclassifiedRecord"]["properties"]
    assert defs["unclassifiedRecord"]["properties"]["source_values"]["minItems"] == 1


def test_typed_records_are_pack_bound_and_all_records_are_provenance_bound() -> None:
    defs = _schema()["$defs"]
    typed_required = set(defs["financialRecord"]["required"])
    unclassified_required = set(defs["unclassifiedRecord"]["required"])
    provenance_required = set(defs["domainProvenance"]["required"])

    assert {
        "semantic_pack_identity",
        "input_type_id",
        "role_values",
        "provenance_ref",
        "record_sha256",
    } <= typed_required
    assert {
        "semantic_pack_identity",
        "source_values",
        "reason_codes",
        "provenance_ref",
        "record_sha256",
    } <= unclassified_required
    assert {
        "document_refs",
        "source_scope_refs",
        "source_refs",
        "source_value_refs",
        "source_evidence_refs",
        "source_package_refs",
        "source_package_integrity_hashes",
        "lineage_sha256",
    } <= provenance_required
    assert defs["financialRecord"]["additionalProperties"] is False
    assert defs["unclassifiedRecord"]["additionalProperties"] is False
    assert defs["domainProvenance"]["additionalProperties"] is False


def test_catalog_distinguishes_declared_and_populated_types_and_coverage_is_terminal() -> None:
    defs = _schema()["$defs"]
    catalog_required = set(defs["domainCatalog"]["required"])
    coverage = defs["domainCoverage"]
    terminal_counts = set(defs["terminalCoverageCounts"]["required"])

    assert {
        "declared_types",
        "populated_types",
        "typed_records_total",
        "unclassified_records_total",
        "documents",
        "periods",
        "currencies",
    } <= catalog_required
    for field in ("declared_types", "populated_types", "documents", "periods", "currencies"):
        assert defs["domainCatalog"]["properties"][field]["uniqueItems"] is True
    assert coverage["properties"]["coverage_status"]["enum"] == [
        "complete",
        "partial",
        "blocked",
    ]
    assert {
        "typed_source_refs_total",
        "unclassified_source_refs_total",
        "no_financial_input_source_refs_total",
        "unsupported_source_refs_total",
        "uncovered_source_refs_total",
        "duplicate_terminal_ownership_total",
        "ownership_conflicts_total",
    } == terminal_counts
    complete_then = coverage["allOf"][0]["then"]["properties"]
    assert complete_then["terminal_ownership_complete"] == {"const": True}
    assert complete_then["uncovered_source_refs"] == {"maxItems": 0}


def test_query_filters_pagination_and_completeness_are_closed_and_deterministic() -> None:
    defs = _schema()["$defs"]
    filters = defs["queryFilters"]
    page = defs["pageRequest"]
    completeness = defs["queryCompleteness"]
    response = defs["queryResponse"]
    response_required = set(response["required"])

    assert set(filters["required"]) == {
        "record_kinds",
        "input_type_ids",
        "document_refs",
        "period_keys",
        "currency_keys",
    }
    assert filters["additionalProperties"] is False
    assert page["properties"]["limit"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 200,
    }
    assert page["properties"]["order"] == {"const": "record_id_asc"}
    assert response["properties"]["records"]["maxItems"] == 200
    assert response["properties"]["order"] == {"const": "record_id_asc"}
    assert {
        "semantic_pack_identity",
        "coverage_ref",
        "effective_filters",
        "page_limit",
        "query_fingerprint",
    } <= response_required
    assert completeness["properties"]["page_status"]["enum"] == [
        "continued",
        "complete_final_page",
        "blocked",
    ]

    outcomes = {
        condition["if"]["properties"]["page_status"]["const"]: condition["then"][
            "properties"
        ]["query_result_complete"]["const"]
        for condition in completeness["allOf"]
    }
    assert outcomes == {
        "continued": False,
        "complete_final_page": True,
        "blocked": False,
    }

    continued_then = response["allOf"][0]["then"]["properties"]
    assert continued_then["records"] == {"minItems": 1}
    assert continued_then["completeness"]["properties"][
        "records_returned_this_page"
    ] == {"minimum": 1}
    blocked_then = response["allOf"][2]["then"]["properties"]
    assert blocked_then["records"] == {"maxItems": 0}
    assert blocked_then["completeness"]["properties"][
        "records_returned_this_page"
    ] == {"const": 0}


def test_contract_forbids_gate3_tax_methodology_and_direct_artifact_store_reads() -> None:
    document = CONTRACT_DOCUMENT.read_text(encoding="utf-8")
    normalized_document = " ".join(document.split())

    assert "Gate 3 must not read the Artifact Store directly." in document
    assert "GATE3_TAX_METHODOLOGY: ZERO" in document
    assert "Free-text search, regex matching, implicit aliases, calculations" in (
        normalized_document
    )
    assert "query-result completeness and source-coverage completeness are independent" in (
        document.lower()
    )
    assert "Changing any of this hash material is a contract-version change." in document
