# Broker Reports Gate 4 Case Assembly v1

Status: `CURRENT_RUNTIME_CONTRACT`

Goal status: `G4.3_CLOSED`

Date: 2026-08-08

## Purpose

G4.3 lifts the existing G4.2 exact-sidecar materialization path to the current
case level:

```text
all documents visible to current case readiness
-> every eligible current FinancialAnnotationsV2 sidecar
-> existing G4.2 materializer per exact sidecar
-> one case-scoped Gate4FinancialCaseFactV1 set
```

Assembly is deterministic ordinary code. It does not reopen source formats,
call an LLM or decide whether facts from different documents represent the
same economic event.

## Owners and entrypoints

| Concern | Sole owner |
| --- | --- |
| current case document/readiness set | existing `Gate3NdflCaseReadinessFactory.create` |
| one exact sidecar to facts | existing `Gate4FinancialCaseMaterializerFactory.create` |
| whole-case rebuild and current read | existing composed `Gate4FinancialCaseRuntimeFactory.create` |
| case SQL replacement and queries | existing `Gate4FinancialCaseSqlCacheFactory.create` |
| access, case identity and lifecycle | existing `ArtifactAccessContext`, `ArtifactResolver` and `ArtifactStore` |

The composed runtime adds only:

```text
rebuild_case(context)
read_case(context)
```

It does not introduce a second materializer, registry, orchestrator or storage
adapter.

## Current case source set

The source set is derived on every operation from Gate 3 NDFL readiness. Each
readiness-visible document is represented in deterministic `document_id`
order as either:

```text
CURRENT_GATE3_V2
NOT_READY
```

`CURRENT_GATE3_V2` requires the existing readiness owner to select a validated
readable V2 sidecar bound to the exact active canonical version. The source
entry retains:

- `document_id`;
- active canonical version ID, when available;
- selected FinancialAnnotations artifact ID, when available;
- the existing Gate 3 reason codes.

`NOT_READY` is explicit. It is not silently dropped from the completeness
decision and does not contribute guessed facts.

No second case or document registry is persisted.

## Case assembly

`rebuild_case` performs one bounded sequence:

1. derive the current case source set;
2. sort exact eligible bindings by `document_id`;
3. materialize each exact sidecar through the G4.2 materializer;
4. validate every materialization against the captured source binding;
5. replace the authenticated case cache in one SQL transaction;
6. re-read the source set and fail closed if it changed;
7. return the current case facts and technical completeness.

All materialization happens before the SQL replacement boundary. A failed
sidecar cannot create a partly replaced case generation. Existing cache rows
may remain physically present after such a failure, but exact-generation reads
will reject them as stale.

## Technical completeness

The read result uses exactly two states:

```text
CASE_COMPLETE_FOR_CURRENT_INPUT_SET
CASE_INCOMPLETE
```

`CASE_COMPLETE_FOR_CURRENT_INPUT_SET` means only:

- the readiness-visible source set is non-empty;
- every visible document has a current selected V2 sidecar;
- the cache generations exactly match those selected sidecar/canonical
  identities.

`CASE_INCOMPLETE` means the current source set is empty or at least one visible
document is `NOT_READY`. Available current facts may still be returned, but the
status stays incomplete and the source entry shows the missing/stale reason.

Neither state claims:

- that the user uploaded every economically necessary document;
- that Gate 3 found every financial fact;
- that the economic history is complete;
- that reconciliation, tax calculation or declaration preparation is ready.

Completeness is derived on each read and is not stored as a new semantic fact.

## SQL and read boundary

G4.3 adds no SQL table or index. It reuses the two G4.2 tables:

- `gate4_financial_case_cache_generation_v1`;
- `gate4_financial_case_fact_cache_v1`.

The existing repository gains an atomic whole-case replacement over the same
authenticated user/case/workspace-model scope. Public fact queries require the
stored generation set to equal the complete current eligible binding set; a
new or replaced current sidecar therefore makes the old query result stale
until case rebuild.

`read_case` returns:

- technical completeness status;
- current Gate 3 case status;
- the derived per-document source set;
- one deterministic tuple of complete G4.1 fact payloads.

The SQL projection remains deletable and owns no financial meaning.

## Rebuild and ordering

For unchanged exact upstream inputs:

```text
clear derived cache
-> rebuild_case
-> identical fact IDs, values and provenance
```

Read order is deterministic. Source publication or discovery order cannot
change the logical fact set. Facts from different sidecars retain their own
G4.1 identity and provenance.

## Upstream change and lifecycle

- a newly selected current document adds a binding, so old case reads fail
  `gate4_cache_stale` until rebuild;
- a replaced active canonical or selected sidecar changes the exact binding,
  so old facts cannot remain current;
- an inaccessible, expired or otherwise non-ready document is reported by the
  existing readiness semantics;
- existing ArtifactStore lifecycle triggers remove derived rows for a sidecar
  that leaves the active lifecycle.

There is no dependency graph. Exact source-set and generation equality is the
freshness mechanism.

## Provenance and duplicate-like facts

Every returned fact remains the unchanged G4.1 payload. Its trace is:

```text
case context
-> fact_id
-> FinancialAnnotationsV2 artifact + annotation index
-> exact canonical binding
-> canonical target/source literal
-> source document custody
```

Assembly never compares fact values across documents. Two dividends with the
same date, amount, currency and asset but different exact sidecars remain two
facts with separate IDs and provenance.

## OpenWebUI-first and closed world

G4.3 reuses the current OpenWebUI Function extension bundle and project-local
ArtifactStore integration. It adds no upstream OpenWebUI table, model, API,
case registry, ACL, lifecycle, environment variable or dependency. Runtime
imports remain inside the existing closed bundled package plus Python standard
library.

## Non-goals

G4.3 does not implement deduplication, reconciliation, similarity matching,
duplicate detection semantics, relations, commission/tax/trade linking,
conflict resolution, LLM calls, broker-specific parsing, FIFO, cost basis, tax
logic, Gate 5, graph storage, RAG or embeddings.

Next allowed Goal: `G4.4 — минимальный домен связей`.
