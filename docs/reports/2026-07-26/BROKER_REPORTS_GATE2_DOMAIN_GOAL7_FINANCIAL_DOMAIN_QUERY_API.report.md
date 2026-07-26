# Broker Reports Gate 2 Domain — GOAL 7 Financial Domain Query API

Date: 2026-07-26.

Status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`.

Base revision: `e9cbe896d9f87085fdd527d83a82bbc521b9b899`.

Branch:
`codex/broker-reports-gate2-domain-goal7-query-api`.

## 1. Objective

Implement server-authoritative managed financial-domain interfaces for Gate 3:

- describe the domain;
- query typed records;
- query unclassified records;
- read coverage;
- read provenance.

Target contract:
[`BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md`](../../stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md).

## 2. Normative consumer DTOs

The runtime emits the exact closed GOAL 1 DTOs:

```text
broker_reports_managed_financial_record_v1
broker_reports_managed_financial_unclassified_record_v1
broker_reports_managed_financial_domain_snapshot_v1
broker_reports_managed_financial_domain_catalog_v1
broker_reports_managed_financial_domain_coverage_v1
broker_reports_managed_financial_domain_provenance_v1
```

Synthetic runtime instances of snapshot, catalog, coverage, typed record,
unclassified record, and provenance pass the accepted GOAL 1 JSON Schema.
Catalog output distinguishes all Pack-declared types from populated types and
reports typed/unclassified totals plus document, period, and currency counts.

The initial local implementation used simplified new DTOs. Pre-PR contract
review rejected that drift. The accepted implementation instead preserves the
normative entities, cumulative pagination completeness, access scope, and
retention semantics.

## 3. Explicit query extension

GOAL 7 adds normalization-run and classification-status filters beyond the
GOAL 1 v1 filter set. Because filter meaning is contract meaning, this is
versioned explicitly:

```text
api_response=broker_reports_gate2_financial_domain_api_response_v1
query_policy=broker_reports_gate2_financial_domain_query_v2
```

The effective filter set is:

```text
input_type_id
normalization_run_ref
document_ref
period
currency
classification_status
```

All values are exact after bounded normalization. Period is whitespace- and
case-normalized; currency is uppercased. Invalid status, currency, limit,
continuation, or filter object fails closed.

## 4. Canonical snapshot and catalog

`Gate2FinancialDomainCatalogFactory.create`:

- validates the exact artifact/Source Package set;
- reruns the full authoritative package-binding validator for every artifact;
- rejects duplicate artifact, source-scope, and terminal IDs;
- builds one terminal owner for every declared source scope;
- builds normative typed/unclassified records, provenance, coverage, catalog,
  and immutable snapshot;
- binds the exact Registry and managed Semantic Pack identities;
- binds access-scope fingerprint and retention timestamps;
- hashes every record, record set, provenance lineage, catalog, coverage, and
  complete internal snapshot material.

Snapshot validation separately checks closed DTO shapes, all hashes,
cross-entity identities, record indexes, catalog counts, populated type
counts, provenance ownership, and four-disposition coverage accounting. A
self-consistently rehashed count drift is rejected.

## 5. Query completeness and continuation

Every response contains:

- full immutable snapshot identity;
- full Semantic Pack identity;
- catalog as declared scope;
- effective filters and query fingerprint;
- page count, exact matching count, and cumulative returned count;
- bounded limit and continuation;
- normative coverage;
- provenance refs;
- result and response integrity.

A response is `continued` only when it returns at least one result and makes
positive cumulative progress. `query_result_complete=true` appears only on
the final page when cumulative returned count equals exact matching count.

The query fingerprint binds snapshot, capability, filters, provenance
projection, limit, and `record_id_asc` order. The opaque continuation also
binds next position, access-scope fingerprint, and snapshot expiry identity.
Cross-snapshot, cross-filter, changed-limit, and tampered continuations fail
closed.

## 6. Server authority and privacy

`Gate2FinancialDomainQueryFactory.create`:

- revalidates the entire snapshot;
- compares Registry and Pack identities with current server authorities;
- recomputes the access scope from current user, case-or-chat, workspace, and
  source-availability context;
- rejects source-unavailable or mismatched current context;
- requires a server-held HMAC continuation key of at least 32 bytes;
- rejects an expired snapshot;
- is the only valid query construction route.

Direct query construction is rejected. Domain modules import neither
Artifact Store nor Artifact Resolver. Gate 3 receives only the validated
snapshot-backed API. No provider, filesystem, network, Knowledge/RAG,
embedding, or vectorization route exists.

Fresh review of remote head `1e19b111e53dab0d50b14d3645d30ff5fafb105c`
returned `CHANGES_REQUIRED` for two authority defects. The first version
accepted a scalar access fingerprint also visible in the response, so a
caller could echo it without proving current server context. Its continuation
digest was unkeyed SHA-256 over response-derivable inputs, so a caller could
compute another offset. The corrected factory derives access only from current
server context, rejects unavailable source state, and authenticates every
continuation with a server-held HMAC key. Negative tests reject foreign/echoed
context, source unavailability, a short key, a wrong-key token, and the former
unkeyed token construction.

Typed and unclassified responses contain private domain values by design and
require the server boundary. Provenance responses contain refs and hashes, not
literal values. Repository tests use synthetic inputs only.

## 7. Closed-world module boundaries

The implementation is split into:

1. contracts and bounded pagination;
2. normative DTO projection;
3. snapshot/catalog factory;
4. cross-entity validation;
5. query service.

The official Gate 2 domain bundle installs these modules in dependency order.
Two rebuilds were byte-exact:

```text
bundle_sha256=ad384fd722d91f47e5148d3831c035021d4a3c3e54ae2af1f76b92e6762aa618
bundle_rebuild=exact
```

## 8. Verification

Explicit PowerShell test cwd:
`services/broker-reports-gate1-proof`; test ENV: none.

- focused API tests: `20 passed in 2.03s`;
- broad financial regression set: `245 passed in 8.21s`;
- domain bundle/architecture/contract set after module split:
  `48 passed in 9.13s`;
- full Broker Reports suite:
  `1582 passed, 20 skipped, 5 unchanged warnings in 145.89s`;
- repository privacy guard: `3 passed in 0.79s`;
- two official bundle rebuilds: exact;
- targeted Ruff: passed;
- targeted compileall: passed;
- `git diff --check`: passed;
- provider/customer/model calls: 0;
- tokens/cost: 0 / USD 0;
- fallback/repair: 0 / 0;
- stage/production mutations: 0 / 0.

## 9. Explicitly unchanged

This GOAL does not:

- activate a live or production route;
- persist a live domain snapshot;
- modify Semantic Pack, Skill, Prompt, or managed asset bytes;
- call a provider or customer corpus;
- add Gate 3 methodology;
- change production admissions, workload budgets, fallback, or repair;
- claim GOAL 8 benchmark or GOAL 9 local-domain proof.

## 10. Acceptance

```text
DOMAIN_CATALOG=QUERYABLE
TYPED_QUERY=COMPLETE_FOR_DECLARED_SCOPE
UNCLASSIFIED_QUERY=SUPPORTED
PROVENANCE_QUERY=SUPPORTED
DIRECT_GATE3_ARTIFACTSTORE_ACCESS=ZERO
```

Authoring status:
`IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`.

Next permitted goal:
`GOAL_8_AFTER_GOAL_7_REVIEW_ACCEPTANCE_MERGE_AND_CLEANUP`.

## 11. Safe receipt

Repository-safe receipt:
[`BROKER_REPORTS_GATE2_DOMAIN_GOAL7_FINANCIAL_DOMAIN_QUERY_API.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL7_FINANCIAL_DOMAIN_QUERY_API.receipt.safe.json).

The receipt records exact staged Git-blob SHA-256 values and the accepted
bundle hash. It contains no customer/private values, raw provider output,
secrets, private paths, or live-stage claim.

Exact staged receipt Git-blob SHA-256:

`bc7212bd99254c055ee0ba3a4942940487d155bbb1da5a1a30baf7d089c11b65`.
