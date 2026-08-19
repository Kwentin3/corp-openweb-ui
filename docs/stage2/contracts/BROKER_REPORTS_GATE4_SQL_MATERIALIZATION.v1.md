# Broker Reports Gate 4 SQL Materialization v1

Status: `CURRENT_RUNTIME_CONTRACT`

Goal status: `G4.2_CLOSED`

Downstream boundary status: `G4.6_CLOSED — NO_NEW_READ_LAYER_REQUIRED`

Gate 4 status: `CLOSED_BY_G4.7`

Date: 2026-08-08

## Purpose

G4.2 is the first Gate 4 runtime slice. It mechanically projects current
validated Gate 3 role bindings into the G4.1 fact contract and stores a small
rebuildable SQL read cache:

```text
current FinancialAnnotationsV2
+ exact active CanonicalArtifactV1
+ trusted ArtifactAccessContext
-> Gate4FinancialCaseFactV2[]
-> same-ArtifactStore SQLite projection
-> ordinary code queries
```

The semantic source of truth remains the immutable Gate 3 sidecar, active
canonical version, published Role Pack and
[Gate4FinancialCaseFactV2](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md).
The SQL rows do not define a new financial record type.

G4.6 audited the implemented read surface and found no missing downstream
operation. The existing factory-composed runtime is the official Gate 4 read
boundary; G4.6 adds no Read Model, Repository, Service, DTO family or query
abstraction.

The physical SQL cache remains a rebuildable, non-authoritative projection;
it is not a second Gate 4 read owner.

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

For downstream reads the official entrypoint is exactly:

```text
Gate4FinancialCaseRuntimeFactory(store, read_enabled).create()
```

The caller supplies only the trusted `ArtifactAccessContext` plus the explicit
query value required by the selected method. User, case and workspace scope are
never accepted as parallel query parameters.

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

Normalization is deliberately small and source-preserving:

- a valid exact `YYYY-MM-DD` or exact `DD.MM.YYYY` calendar date emits
  `YYYY-MM-DD`; any other non-empty date literal remains unchanged;
- quantity, unit price and amount normalize plain dot/comma decimals plus
  unambiguous space-grouped, comma-grouped/dot-decimal and
  dot-grouped/comma-decimal forms; any other non-empty literal remains
  unchanged;
- asset and currency trim only surrounding whitespace and otherwise preserve
  source text;
- no locale, currency or financial default is guessed. A downstream consumer
  must reject a preserved literal that is not valid for its own contract.

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
read_case(context)
list_facts(context)
list_by_financial_type(context, financial_type)
get_fact(context, fact_id)
list_by_asset(context, asset)
list_by_period(context, date_from, date_to)
```

Every query is case-scoped in SQL and returns the complete G4.1 fact JSON.
`asset` is projected when its corresponding role has `status=value`. `date` is
projected only when that role contains a valid exact ISO calendar date; partial
or unrecognized date literals remain authoritative only inside `fact_json` and
cannot enter period queries. Explicit `missing` remains present inside the fact
and is not redefined as a financial non-event.

`read_case` returns the current technical assembly together with all current
facts and source readiness. Each returned fact retains `fact_id`,
`financial_type`, ordered typed roles, `role_complete | role_incomplete`, exact
annotation/canonical bindings and role source bindings. G4.6 introduces no
second provenance view and never filters incomplete facts implicitly.

Every public read delegates to the existing cache owner. That owner compares
the stored complete generation with the current Gate 3 readiness source set
before reading and repeats the source-set check after reading. A missing or
stale cache therefore fails closed through the existing error semantics rather
than being returned as the current Financial Case.

## Rebuild and idempotency

`rebuild_artifact` requires one exact sidecar to be the current selected input
for its document, materializes it through the sole materializer, then replaces
only that document's case-scoped cache rows atomically. It never iterates or
assembles the case's other documents and never changes upstream artifacts.
G4.3 adds whole-case orchestration without changing this G4.2 operation.

```text
same exact sidecars + same active canonical + same G4.1 contract
-> same canonical fact JSON
-> same fact_id values
```

`clear_case_cache` removes only the authenticated case's projection. Repeating
`rebuild_artifact` for an exact input reconstructs the same facts without an
LLM or broker-format read. A cache with no stored generation is
`gate4_cache_missing`, not evidence that no financial facts exist. Case-scoped
reads now require exact equality with the current eligible generation set.
Whole-case rebuild, derived completeness and the source-set result belong to
[Gate 4 Case Assembly v1](./BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md).

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

G4.2 provides an internal factory/runtime slice. G4.3 reuses this same bundled
slice and adds no second materializer or storage surface. Neither adds a new
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

G4.6 adds an executable downstream-consumer proof over the same real
factory-composed runtime and same-store SQLite cache. The consumer uses only
`read_case`, the five explicit query operations and returned G4.1 fields. Its
source contains no Gate 3, Canonical Reader, SQLite adapter/table or
broker-parser dependency. Because the consumer contract mentions no table,
column or index, the two physical cache tables may be replaced behind the
runtime without changing that consumer contract.

G4.7 reuses this proof as the representative whole-Gate integration: three
current documents, all five required financial types, typed role values,
complete/incomplete status, provenance, delete/rebuild equality and stale
fail-closed behavior all pass through this same production boundary. No new
runtime operation is needed for closure.

## Non-goals

G4.2 does not implement multi-document assembly or reconciliation, semantic
deduplication, cross-fact relations, commission/tax/trade links, FIFO, cost
basis, tax logic, conflict resolution, a relation LLM pass, Gate 5,
declaration logic, graph DB, RAG, embeddings or a generic query API. G4.3 now
owns assembly only and preserves every separate fact.

G4.6 additionally does not add a Read Model facade, Repository, Service,
relation operation, filter DSL, public REST/GraphQL surface or second freshness
engine. G4.4's minimal relation set remains empty.

Gate 4 is closed by G4.7. Next allowed boundary: `GATE5_DESIGN` through
[Gate 4 -> Gate 5 Handoff v1](./BROKER_REPORTS_GATE4_HANDOFF.v1.md).
