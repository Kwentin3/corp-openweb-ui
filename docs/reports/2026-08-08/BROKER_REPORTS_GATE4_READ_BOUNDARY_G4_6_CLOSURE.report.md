# Broker Reports — G4.6 Minimal Financial Case Read Boundary Closure

Date: `2026-08-08`

Goal status: `G4.6_CLOSED`

## Result

```text
NO_NEW_READ_LAYER_REQUIRED
OFFICIAL_GATE4_READ_BOUNDARY = Gate4FinancialCaseRuntimeFactory.create
```

Audit found no downstream read gap. The existing factory-composed
`Gate4FinancialCaseRuntime` already provides one small current-case boundary,
keeps physical SQLite details internal and preserves the complete
`Gate4FinancialCaseFactV1` contract. G4.6 therefore adds no runtime method,
Read Model, Repository, Service, DTO or storage abstraction.

## Authority and evidence reviewed

- [Pipeline Gates v1](../../stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md);
- [Gate 4 Financial Case Fact v1](../../stage2/contracts/BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md);
- [Gate 4 SQL Materialization v1](../../stage2/contracts/BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md);
- [Gate 4 Case Assembly v1](../../stage2/contracts/BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md);
- [architecture authorities map](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md);
- production `gate4_financial_case_cache.py`, its public package exports,
  generated bundle route and focused integration tests;
- [G4.4 relation-necessity result](BROKER_REPORTS_GATE4_RELATION_NECESSITY_G4_4.report.md).

The audit started from a clean current `main`. Baseline focused tests passed
before edits. No provider, LLM or customer corpus pipeline was called.

## Audit matrix

| Downstream need | Already available | Current boundary | Real gap |
| --- | --- | --- | --- |
| read current case | yes | `Gate4FinancialCaseRuntime.read_case(context)` | none |
| get fact by ID | yes | `get_fact(context, fact_id)` | none |
| get facts by financial type | yes | `list_by_financial_type(context, financial_type)` | none |
| get facts by asset | yes | `list_by_asset(context, asset)` | none |
| get facts by date/period | yes | `list_by_period(context, date_from, date_to)` | none |
| read fact type and identity | yes | complete G4.1 fact JSON | none |
| read typed roles | yes | ordered `roles[]` with normalized value and source binding | none |
| see complete/incomplete state | yes | `status = role_complete | role_incomplete` | none |
| trace provenance | yes | annotation target plus Gate 3 artifact/annotation/canonical binding and role source bindings | none |
| reject missing/stale case cache | yes | existing pre/post source-generation checks | none |

No required operation needs a new public method.

## Official boundary

Consumers create the existing runtime through:

```text
Gate4FinancialCaseRuntimeFactory(store, read_enabled).create()
```

They then use only:

```text
read_case(context)
list_facts(context)
get_fact(context, fact_id)
list_by_financial_type(context, financial_type)
list_by_asset(context, asset)
list_by_period(context, date_from, date_to)
```

`ArtifactAccessContext` remains the sole origin of authenticated user, case and
workspace scope. A consumer cannot supply those identifiers as independent
query filters.

The SQL adapter, repository, table names, columns and indexes are not part of
this boundary. The cache remains rebuildable and non-authoritative.

## Fact visibility

Each returned fact remains the current closed G4.1 shape. Downstream can read:

```text
fact_id
financial_type
roles[]
status
annotation_target
gate3_binding
```

Bound roles retain normalized values and exact source bindings. Missing roles
remain explicit; a fact with a missing required role remains
`role_incomplete`. The read boundary neither drops it nor invents a default.

The provenance chain stays available without a second model:

```text
fact_id
-> Gate 3 sidecar + annotation index
-> canonical version + canonical target
-> source document custody
```

## Current and stale semantics

Every read reuses the existing freshness owner:

1. derive the current source set through Gate 3 readiness;
2. compare the complete cached generation with the expected bindings;
3. execute a tenant/case-scoped read inside the existing transaction wrapper;
4. re-check the current source set after the read.

Missing generation returns `gate4_cache_missing`. Changed sidecar, canonical or
current document set returns `gate4_cache_stale`. G4.6 adds no alternate path or
second freshness engine.

## Representative consumer proof

The executable proof uses the production factory, real same-ArtifactStore
SQLite cache and a three-document synthetic case. Through the official runtime
only, the downstream portion:

- reads the current case;
- reads purchases, disposals, dividends, transaction charges and withheld tax;
- queries by asset and period;
- looks up one fact by `fact_id`;
- observes type, roles, status, identity and provenance;
- reads a cached required-missing role back as `role_incomplete`.

The consumer function source is guarded against `CanonicalReader`, Gate 3,
SQLite, physical Gate 4 table names and broker-parser dependencies. Core
runtime, materializer, cache, freshness and tenant logic are not mocked.

## SQL replacement proof

The proof consumer names only factory/runtime methods and G4.1 fields. It does
not import or reference:

```text
gate4_financial_case_fact_cache_v1
gate4_financial_case_cache_generation_v1
SQLite connection/repository implementation
```

Therefore a later internal cache-schema replacement can preserve the same
consumer contract. No migration was needed or performed for G4.6.

## KISS review

- Existing runtime solves every required read: yes.
- New public methods: zero.
- New runtime classes/factories/DTOs: zero.
- New query framework or filter DSL: zero.
- New financial semantics: zero.
- Relation operations after G4.4: zero.
- Duplicated freshness/access logic: zero.

## Explicit non-goals

No relation layer, relation query, deduplication, reconciliation, conflict
engine, graph, query DSL, REST/GraphQL API, ORM, storage framework, provider,
LLM, broker-specific parser, FIFO, cost basis, tax rule or Gate 5 behavior was
added.

## Validation

- focused G4.1/G4.2/G4.6 and pipeline guards: `31 passed`;
- relevant canonical/Gate 3/Gate 4 regression suite: `226 passed`;
- generated OpenWebUI Function bundle parity: passed with no generated diff;
- Ruff correctness checks for changed tests: passed;
- local Markdown links, Cyrillic, changed-content secret-like scan and
  `git diff --check`: passed.

The first local regression attempt used the default Windows temp root on drive
C and was rejected by the existing canonical capacity preflight because that
drive's free-space ratio was below policy. No policy or fixture was weakened.
The same suite passed with explicit PowerShell `TEMP/TMP` and pytest base temp
on drive D.

## Closure

```text
G4.6_CLOSED
NO_NEW_READ_LAYER_REQUIRED
NEXT_ALLOWED_GOAL = G4.7_REPRESENTATIVE_INTEGRATION_PROOF
```
