# Broker Reports Managed Financial Domain Consumer Contract v1

Status: normative target contract; repository-defined, not live-activated

Contract version: `broker_reports_managed_financial_domain_contract_v1`

Machine-readable schema:
[`BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.schema.json`](./BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.schema.json)

## 1. Purpose and ownership

This contract defines the stable Gate 2 boundary consumed by Gate 3. Gate 2
owns financial record classification, immutable domain snapshots, source
coverage, provenance, deterministic filtering, pagination, and query
completeness. Gate 3 may describe and reason over records returned through this
boundary, but does not own their type identity, source lineage, or completeness
status.

The boundary is private-case data. The committed schema and examples contain no
customer values.

This Goal defines DTOs and semantics only. It does not:

- implement transport, persistence, or an OpenWebUI Tool;
- activate a production route;
- qualify a model or Semantic Pack;
- introduce tax, declaration, ledger, cost-basis, P/L, netting, or currency
  conversion methodology;
- promote the earlier research Fact Registry to production authority.

## 2. Version and compatibility

Every DTO has an exact `schema_version`. The contract family version is
`broker_reports_managed_financial_domain_contract_v1`.

An additive implementation change is compatible only when a v1 consumer can
continue validating and interpreting the response without ignoring a new
required meaning. A change to required fields, enum meaning, filter logic,
ordering, terminal ownership, completeness, or provenance requires a new
contract version.

Each snapshot pins one `semantic_pack_identity`, including the Pack schema
version, semantic version, canonical SHA-256, and managed asset reference. Goal
1 defines that identity seam; Goal 2 supplies and validates the Pack.

### 2.1 Canonical integrity material

Unless a more specific v1 rule is stated below, a canonical hash uses UTF-8
JSON without BOM, insignificant whitespace, or escaped non-ASCII
normalization, with object keys sorted lexicographically. Arrays retain their
normative order.

- `record_sha256` hashes the complete record with `record_sha256` omitted.
- `record_set_sha256` hashes the JSON array of
  `{record_id, record_sha256}` pairs sorted by `record_id`.
- `catalog_sha256`, `coverage_sha256`, and `lineage_sha256` hash their complete
  object with only the corresponding hash field omitted.
- `query_fingerprint` hashes the exact `domain_snapshot_id`,
  canonical `effective_filters`, projection, page limit, and order. It excludes
  `continuation_token`.

Changing any of this hash material is a contract-version change.

## 3. Domain ownership map

| Concern | Owner | Boundary rule |
| --- | --- | --- |
| normalized source evidence | Gate 1 | referenced, never silently copied or reinterpreted |
| type meaning and role meaning | versioned Semantic Pack | exact identity pinned by snapshot |
| classification and terminal ownership | Gate 2 | one terminal outcome per declared source ref |
| records, catalog, coverage, provenance | Managed Financial Domain | immutable snapshot and strict DTOs |
| authorization and private resolution | server-side domain service | fail closed before returning private values |
| tax and declaration methodology | Gate 3 or later approved methodology | outside this contract |

Gate 3 must not read the Artifact Store directly. It receives records and
provenance through the Managed Financial Domain boundary after server-side
access checks.

## 4. Contract entities

### 4.1 Financial record

`broker_reports_managed_financial_record_v1` is a typed, immutable record. It
contains:

- stable `record_id`;
- `input_type_id` whose meaning comes from the pinned Semantic Pack;
- source-bound role values;
- mechanically normalized document, period, and currency dimensions;
- `provenance_ref` and optionally expanded provenance;
- a canonical record hash.

Provider output is never a record by itself. A record exists only after
deterministic validation, terminal ownership, and materialization.

### 4.2 Unclassified record

`broker_reports_managed_financial_unclassified_record_v1` is first-class data,
not a discarded error and not a synthetic type. It preserves:

- every retained source value and source ref;
- document/period/currency dimensions that are mechanically available;
- bounded reason codes;
- provenance and a canonical record hash.

It has `record_kind=unclassified` and no `input_type_id`. A consumer may query
it independently or together with typed records. It must not be silently
upcast to a typed record.

### 4.3 Domain snapshot

`broker_reports_managed_financial_domain_snapshot_v1` is an immutable view of
one authorized case/run domain. It pins:

- source extraction and Gate 2 run identities;
- Semantic Pack identity;
- exact record-set count and hash;
- catalog and coverage refs;
- access-scope fingerprint;
- creation and retention timestamps.

Pagination is bound to one immutable snapshot. Mutating a snapshot in place is
forbidden; new materialization creates a new snapshot ID.

### 4.4 Domain catalog

`broker_reports_managed_financial_domain_catalog_v1` distinguishes:

- types declared by the pinned Pack;
- types populated in this snapshot;
- typed and unclassified record counts;
- covered documents, periods, and currencies.

An existing type with zero records remains visible in `declared_types` and is
absent from `populated_types`. This lets Gate 3 distinguish “type does not
exist” from “type exists but is not populated.”

Catalog arrays have unique keys and deterministic order:

- `declared_types` and `populated_types` by `input_type_id`;
- `documents`, `periods`, and `currencies` by `key`.

`records_total` equals `typed_records_total + unclassified_records_total`.
Every populated type is declared by the same pinned Pack, and the sum of
`populated_types.records_total` equals `typed_records_total`.

### 4.5 Coverage

`broker_reports_managed_financial_domain_coverage_v1` accounts for the exact
declared source-ref set with four terminal outcomes:

- `typed`;
- `unclassified`;
- `no_financial_input`;
- `unsupported`.

`terminal_ownership_complete=true` requires:

```text
declared_source_refs_total
  = typed_source_refs_total
  + unclassified_source_refs_total
  + no_financial_input_source_refs_total
  + unsupported_source_refs_total
```

and also requires zero uncovered refs, zero duplicate terminal ownership, and
zero ownership conflicts. `no_financial_input` and `unsupported` are coverage
outcomes, not financial records.

Coverage status is:

- `complete` — every declared ref has exactly one terminal owner;
- `partial` — bounded processing is honest but uncovered refs remain;
- `blocked` — the domain cannot safely expose a usable snapshot.

### 4.6 Provenance

`broker_reports_managed_financial_domain_provenance_v1` provides opaque,
server-resolvable lineage:

- document, source scope, source, source-value, and evidence refs;
- source package ref and integrity hash;
- lineage hash.

Refs do not expose filesystem layout, raw customer filenames, or authorization
credentials. Expanded provenance is returned only after the same access check
as the parent snapshot. Source deletion, expiry, scope mismatch, or failed
integrity checks fail closed.

## 5. Gate 3 consumer operations

The logical boundary exposes five capabilities. GOAL 7 may choose the
transport, but must preserve these DTOs and semantics:

1. resolve an authorized immutable snapshot;
2. read its catalog;
3. read its coverage;
4. query typed and/or unclassified records;
5. expand a returned `provenance_ref`.

The server, not Gate 3, resolves private artifacts and intersects authorization
with the requested snapshot.

## 6. Query request

`broker_reports_managed_financial_domain_query_request_v1` requires:

- exact `domain_snapshot_id`;
- filters;
- projection;
- deterministic page request.

Supported v1 filters are:

- `record_kinds`: `typed`, `unclassified`;
- exact `input_type_ids`;
- exact `document_refs`;
- exact `period_keys`;
- exact `currency_keys`.

Values within one filter are OR; populated filter groups are AND. Empty arrays
mean “no restriction.” `input_type_ids` can match only typed records. Free-text
search, regex matching, implicit aliases, calculations, and provider calls are
not part of v1.

Ordering is exactly `record_id_asc`. `limit` is from 1 through 200. The first
request uses `continuation_token=null`. A continued request must repeat the
same snapshot, filters, projection, limit, and order and supply only the
opaque token returned by the prior page.

`projection.include_provenance=true` requests expanded provenance. With
`false`, every record still returns `provenance_ref`, while expanded
`provenance` is `null`.

## 7. Query response and bounded pagination

`broker_reports_managed_financial_domain_query_response_v1` returns:

- the same immutable snapshot identity;
- the exact Semantic Pack identity and coverage ref pinned by that snapshot;
- a server-computed `query_fingerprint`;
- canonical `effective_filters` and the applied `page_limit`;
- records in exact `record_id_asc` order;
- page and result-set counts;
- coverage status;
- an optional next continuation token.

The token is opaque, integrity protected, and bound to:

- snapshot ID;
- query fingerprint;
- next record position;
- access scope;
- expiry policy.

A token mismatch, replay under another access scope, expired token, missing
snapshot, or mutated snapshot returns a terminal error; the service must not
restart from page 1 or return a best-effort subset.

Every record in a response must carry the same `domain_snapshot_id` and
`semantic_pack_identity` as the response. Echoed filters are sorted and
deduplicated. They are the exact server-applied filters, not an untrusted copy
of request input.

## 8. Completeness semantics

Query-result completeness and source-coverage completeness are independent:

| Field | Meaning |
| --- | --- |
| `page_status=continued` | more matching records exist; token must be non-null |
| `page_status=complete_final_page` | no matching record remains; token is null |
| `query_result_complete=true` | final page reached and `records_returned_through_page == matching_records_total` |
| `domain_coverage_status=complete` | every declared source ref has one terminal owner |
| `domain_coverage_status=partial` | query may be complete over materialized records while source coverage is incomplete |
| `domain_coverage_status=blocked` | records must not be presented as a usable complete domain |

A page with `page_status=continued` is bounded and valid, but is not a complete
query result. It must contain at least one record and make positive progress:
`records_returned_this_page >= 1`. Gate 3 must follow tokens until
`query_result_complete=true` or treat the query as incomplete.

A response with `page_status=blocked` is terminal and fail-closed:

- `records` is empty;
- `records_returned_this_page=0`;
- `next_continuation_token=null`;
- `query_result_complete=false`;
- at least one stable reason code is present.

An empty final result is complete only when all of these hold:

- `matching_records_total=0`;
- `records_returned_this_page=0`;
- `records_returned_through_page=0`;
- `next_continuation_token=null`;
- `query_result_complete=true`.

No implementation may silently omit a matching authorized record because of
an internal cap. If the server cannot continue safely it returns
`page_status=blocked`, a stable reason code, `query_result_complete=false`, and
no records claimed as a complete result.

## 9. Access and privacy

Before resolving any snapshot, page, record, or provenance, the server checks
the current user, case/chat, workspace, retention horizon, and source
availability. Authorization is never accepted from client-supplied scope
fields alone.

Responses containing record values are private. Safe reports may contain only
schema identities, hashes, aggregate counts, statuses, and synthetic examples.
Knowledge/RAG/vector storage is outside this boundary and cannot be used as
domain authority.

## 10. Fail-closed invariants

An implementation of v1 is invalid if any of the following is possible:

- a typed record is not bound to the snapshot Pack identity and source refs;
- an unclassified value is discarded or silently typed;
- a declared source ref has no visible terminal coverage state;
- one ref has multiple terminal owners;
- a query cap silently removes matching records;
- a continued page returns no record or makes no progress;
- a blocked response returns partial records;
- a continuation token changes query semantics or snapshot;
- `query_result_complete=true` is emitted before the final page;
- provenance can resolve outside the authorized snapshot scope;
- current live/stage identity is inferred from stale receipts;
- Gate 3 tax methodology is embedded in the domain DTOs.

## 11. Implementation slices and deferred work

This contract deliberately separates later work:

1. GOAL 2 supplies the versioned Semantic Pack.
2. GOALs 3–6 remove managed-asset and Python semantic drift.
3. GOALs 7–8 implement the tool/API and persistence/indexes.
4. GOALs 9–13 prove migration, Gate 3 parity, and full-scope completeness.
5. GOAL 14 performs controlled production admission and release.

The contract is versioned and explicit now; runtime activation remains false
until the later release acceptance is satisfied.

## 12. Normative status

```text
FINANCIAL_DOMAIN_CONTRACT: VERSIONED
GATE3_CONSUMER_BOUNDARY: EXPLICIT
QUERY_COMPLETENESS: DEFINED
UNCLASSIFIED: FIRST_CLASS_DATA
RUNTIME_ACTIVATION: FALSE
GATE3_TAX_METHODOLOGY: ZERO
```
