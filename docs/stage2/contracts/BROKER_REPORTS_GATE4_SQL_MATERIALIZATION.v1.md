# Broker Reports Gate 4 SQL Materialization v1

Status: `CURRENT_RUNTIME_CONTRACT`

Goal status: `G4.2_CLOSED`

Date: 2026-08-08

## Purpose

G4.2 is the first Gate 4 runtime slice. It mechanically projects current
validated Gate 3 role bindings into the G4.1 fact contract and stores a small
rebuildable SQL read cache:

```text
current FinancialAnnotationsV2
+ exact active CanonicalArtifactV1
+ trusted ArtifactAccessContext
-> Gate4FinancialCaseFactV1[]
-> same-ArtifactStore SQLite projection
-> ordinary code queries
```

The semantic source of truth remains the immutable Gate 3 sidecar, active
canonical version, published Role Pack and
[Gate4FinancialCaseFactV1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md).
The SQL rows do not define a new financial record type.

## Sole runtime entrypoints

| Concern | Owner |
| --- | --- |
| one exact sidecar materialization | `Gate4FinancialCaseMaterializerFactory.create` |
| composed exact-artifact rebuild and case-scoped queries | `Gate4FinancialCaseRuntimeFactory.create` |
| SQL read/cache adapter | `Gate4FinancialCaseSqlCacheFactory.create` |
| source role value | existing `Gate3RoleValueResolverFactory.create_from_active_canonical` |
| current sidecar selection | existing `Gate3NdflCaseReadinessFactory.create` |
| scope, artifact access and lifecycle | existing `ArtifactAccessContext`, `ArtifactResolver` and `ArtifactStore` |

Product, proof and future consumers must start from the composed runtime
factory. The materializer and cache factories remain the two bounded operation
owners used by that runtime; callers must not instantiate an alternative
reader, parser or SQLite connection path.

## Deterministic materialization

For each annotation, the materializer:

1. resolves the exact V2 sidecar through `ArtifactResolver` and its current
   persistence validator;
2. requires the sidecar's canonical version to remain active through the
   existing Gate 3 role resolver factory;
3. loads the exact sidecar-pinned Role Pack and uses its required/optional role
   order;
4. resolves only `bound` role literals and preserves `missing` without a
   default;
5. builds the closed G4.1 shape and its specified deterministic `fact_id`.

It does not inspect a PDF, HTML, CSV or XLSX source, does not know broker
columns and does not call a model.

### Normalization policy

Normalization is deliberately small and fail-closed:

- date accepts exact `YYYY-MM-DD` or exact `DD.MM.YYYY`, validates the calendar
  date and emits `YYYY-MM-DD`;
- quantity, unit price and amount accept an optional minus sign, digits and at
  most one dot or comma decimal separator, with no exponent or grouping; comma
  is mechanically changed to dot and scale is preserved;
- asset and currency trim only surrounding whitespace and otherwise preserve
  source text;
- any other source literal fails materialization; there is no guessed locale,
  grouping or financial default.

`source_literal`, target and optional `exact_text` remain exact provenance.
The normalized value is a separate deterministic projection.

## OpenWebUI-first persistence decision

No new database file, upstream OpenWebUI table, case registry, user model, ACL
or lifecycle service is introduced.

The cache factory accepts only the existing project
`SqliteArtifactStoreAdapter` and creates two versioned technical tables inside
that same SQLite file:

- `gate4_financial_case_cache_generation_v1` records the exact current
  sidecar/canonical generation per document, including zero-fact sidecars;
- `gate4_financial_case_fact_cache_v1` stores canonical fact JSON plus only the
  query projections required now: financial type, asset and date.

All SQL is owned by one internal repository created only inside a transaction
scoped from trusted `ArtifactAccessContext.user_id`, `case_id` and
`workspace_model_id`. Tenant/case identifiers are never accepted as query or
write parameters.

Three indexes follow the accepted reads only: case plus financial type, asset
and date. `fact_id` is the table primary key. There is no ORM, migration
framework, generic event store or query language.

## Reads

The composed runtime exposes explicit ordinary-code reads:

```text
list_facts(context)
list_by_financial_type(context, financial_type)
get_fact(context, fact_id)
list_by_asset(context, asset)
list_by_period(context, date_from, date_to)
```

Every query is case-scoped in SQL and returns the complete G4.1 fact JSON.
`asset` and `date` are SQL projections only when the corresponding role has
`status=value`; explicit `missing` remains present inside the fact and is not
redefined as a financial non-event.

## Rebuild and idempotency

`rebuild_artifact` requires one exact sidecar to be the current selected input
for its document, materializes it through the sole materializer, then replaces
only that document's case-scoped cache rows atomically. It never iterates or
assembles the case's other documents and never changes upstream artifacts.

```text
same exact sidecars + same active canonical + same G4.1 contract
-> same canonical fact JSON
-> same fact_id values
```

`clear_case_cache` removes only the authenticated case's projection. Repeating
`rebuild_artifact` for an exact input reconstructs the same facts without an
LLM or broker-format read. A cache with no stored generation is
`gate4_cache_missing`, not evidence that no financial facts exist. Case-scoped
reads cover only materialized current generations and make no multi-document
completeness claim; case assembly remains G4.3.

## Freshness and lifecycle

Before each read, the cache compares its document generations with the current
selection derived by `Gate3NdflCaseReadinessFactory.create`:

- a new selected sidecar makes the old cache `gate4_cache_stale`;
- a changed active canonical makes the old sidecar unavailable as current;
- a missing current V2 sidecar fails closed;
- rebuild rechecks the exact selection before and after replacement.

The generation records retain the exact sidecar and canonical IDs. Fact JSON
retains annotation index, canonical target and source bindings, preserving the
full G4.1 provenance chain.

SQLite triggers observe the existing ArtifactStore lifecycle columns. When a
referenced sidecar becomes expired, blocked, purge-pending, purged or
privacy-failed, its derived fact and generation rows are deleted. This does
not create a new retention policy; it follows the existing owner.

## Product and closed-world boundary

The two maintained modules and existing Gate 3 readiness module are embedded
in the generated `broker_reports_gate1_pipe` package bundle. They use Python
standard-library SQLite and the package's existing modules only. No workspace
path import, new dependency or environment variable is required.

G4.2 provides an internal factory/runtime slice. It does not add a new
OpenWebUI user action, REST API or second Workspace Model.

## Representative proof

Synthetic exact-canonical proof covers:

- `SECURITY_PURCHASE`;
- `SECURITY_DISPOSAL`;
- `DIVIDEND_INCOME`;
- `TRANSACTION_CHARGE`;
- `TAX_WITHHELD`.

It exercises type queries for all five, asset and period queries, fact lookup,
explicit required/optional missing, delete/rebuild equality, new-sidecar stale
handling, canonical-version stale handling and ArtifactStore case purge.

## Non-goals

G4.2 does not implement multi-document reconciliation, semantic deduplication,
cross-fact relations, commission/tax/trade links, FIFO, cost basis, tax logic,
conflict resolution, a relation LLM pass, Gate 5, declaration logic, graph DB,
RAG, embeddings or a generic query API.

Next allowed Goal: `G4.3 — multi-document case assembly`.
