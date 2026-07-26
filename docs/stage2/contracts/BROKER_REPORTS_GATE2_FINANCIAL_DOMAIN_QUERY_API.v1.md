# Broker Reports Gate 2 Financial Domain Query API

Status: target contract.

Version: `1.0.0`.

Date: 2026-07-26.

## 1. Purpose

This contract implements the accepted
`broker_reports_managed_financial_domain_contract_v1` as a bounded,
server-authoritative interface for Gate 3.

Gate 3 consumes only an authorized immutable domain snapshot through this
query API. It does not read the Artifact Store, Source Packages, Gate 1
payloads, source documents, provider output, Knowledge/RAG, vectors, or
filesystem state.

The upstream catalog factory receives canonical materialized financial
artifacts and their authoritative Source Packages. It validates each pair
before publishing the snapshot. This server-side construction boundary is not
a Gate 3 data-access capability.

## 2. Preserved normative DTOs

The implementation emits the exact closed DTOs accepted in GOAL 1:

```text
broker_reports_managed_financial_record_v1
broker_reports_managed_financial_unclassified_record_v1
broker_reports_managed_financial_domain_snapshot_v1
broker_reports_managed_financial_domain_catalog_v1
broker_reports_managed_financial_domain_coverage_v1
broker_reports_managed_financial_domain_provenance_v1
```

Their field shapes, Pack binding, canonical hashes, terminal ownership,
catalog totals, coverage semantics, and provenance semantics are unchanged.
Runtime tests validate emitted instances against the normative JSON Schema:
`BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.schema.json`.

## 3. API extension version

GOAL 7 requires exact normalization-run and classification-status filters in
addition to the GOAL 1 v1 record filters. Filter logic is contract meaning,
so this change is explicit rather than a silent mutation:

```text
api_response=broker_reports_gate2_financial_domain_api_response_v1
query_policy=broker_reports_gate2_financial_domain_query_v2
```

The extension preserves the v1 entities and completeness rules. Its normalized
filter object adds:

```text
normalization_run_ref
classification_status
```

to exact type, document, period, and currency selection. Later transport work
may expose a separate exact v1 request/response adapter; it must not weaken or
reinterpret either contract.

## 4. Snapshot construction and authority

`Gate2FinancialDomainCatalogFactory.create` is the only canonical snapshot
construction entrypoint. It fails closed unless:

- the materialized-artifact and authoritative Source Package sets match
  exactly;
- every artifact passes the complete Pack-, Registry-, package-, value-,
  ownership-, provenance-, coverage-, ID-, and integrity validator;
- artifact IDs, source scopes, and terminal record IDs are unique;
- every declared source scope has exactly one of the four terminal outcomes;
- the snapshot carries the exact active Registry and managed Semantic Pack
  identities;
- created/expiry timestamps and the server-issued access scope are valid.

The immutable snapshot ID binds the artifacts, package integrity hashes,
Registry, Pack, access-scope fingerprint, and retention timestamps. The
snapshot binds its catalog and coverage refs plus the exact sorted record-set
hash.

`Gate2FinancialDomainQueryFactory.create` revalidates all snapshot content,
compares its Registry and Pack identities with current server authorities,
checks the trusted access-scope fingerprint, and rejects an expired snapshot.
Direct query-object construction fails.

## 5. Capabilities

The query object exposes exactly:

```text
describe_domain
query_typed_records
query_unclassified_records
get_coverage
get_provenance
```

`describe_domain` returns Pack-declared types and the full catalog, including
populated types and document/period/currency counts. Typed and unclassified
queries return the normative records. Coverage returns one terminal owner per
declared source scope together with normative aggregate coverage. Provenance
returns normative reference-only lineage DTOs.

## 6. Filters

Typed, unclassified, coverage, and provenance queries accept:

```text
input_type_id
normalization_run_ref
document_ref
period
currency
classification_status
```

Currency is normalized to uppercase. Period matching is case-insensitive
after whitespace normalization. Identifiers remain exact. Unknown status,
invalid currency, invalid type, oversized value, or a non-filter object fails
closed.

## 7. Response and completeness

Every response carries:

- query schema, policy, kind, fingerprint, effective filters, and exact order;
- the full normative immutable snapshot;
- full Semantic Pack identity;
- the normative catalog as declared scope;
- page result count, bounded limit, and optional continuation;
- cumulative result-set completeness;
- normative coverage;
- page provenance refs;
- results and response integrity hash.

Completeness retains the GOAL 1 separation:

```text
page_status=continued | complete_final_page
matching_records_total
records_returned_this_page
records_returned_through_page
query_result_complete
domain_coverage_status
uncovered_source_refs_total
source_data=complete | partial | restricted | blocked
```

`query_result_complete=true` is emitted only on the final page when the
cumulative returned count equals the exact filtered result count. Source-data
completeness remains independent of complete terminal coverage.

## 8. Bounded continuation

The default page limit is `25`; the GOAL 1 maximum remains `200`. Invalid
limits fail closed.

The query fingerprint binds the snapshot, query capability, all normalized
filters, provenance projection, page limit, and `record_id_asc` order. The
opaque continuation additionally binds:

- next record position;
- trusted access-scope fingerprint;
- snapshot expiry policy.

A token cannot be reused with another snapshot, capability, filter,
projection, limit, access scope, or retention identity. A continued page
always returns at least one result and makes positive cumulative progress.

## 9. Privacy and closed world

The catalog and query modules import no Artifact Store or resolver. The query
object receives only an immutable validated snapshot and its trusted access
fingerprint. It has no network, provider, filesystem, Knowledge/RAG,
embedding, or vectorization capability.

Typed and unclassified records intentionally return canonical private domain
values to the authorized server caller. Repository evidence uses synthetic
inputs only. Provenance responses contain references and hashes without
literal values. Safe reports and receipts contain only counts, hashes,
versions, repository paths, and synthetic identifiers.

## 10. Acceptance

```text
DOMAIN_CATALOG=QUERYABLE
TYPED_QUERY=COMPLETE_FOR_DECLARED_SCOPE
UNCLASSIFIED_QUERY=SUPPORTED
PROVENANCE_QUERY=SUPPORTED
DIRECT_GATE3_ARTIFACTSTORE_ACCESS=ZERO
```

Proof requires all four terminal outcomes, all declared filters, normative DTO
schema validation, access and expiry binding, bounded cumulative pagination,
cross-snapshot/filter/tamper rejection, response-integrity rejection,
authoritative package-forgery rejection, Pack/Registry authority rejection,
reference-only provenance, AST import checks, closed-world bundle loading,
deterministic bundle rebuild, focused and full tests, and privacy checks.
