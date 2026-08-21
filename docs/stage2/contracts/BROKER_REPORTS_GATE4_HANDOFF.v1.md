# Broker Reports Gate 4 -> Gate 5 Handoff v1

Status: `CURRENT SUPPORTING DOC`

Gate 4 status: `CLOSED`

Next allowed boundary: `GATE5_DESIGN`

Updated: 2026-08-21 (active ordinary-trade Fact v2 producer)

This is the short recovery document for a developer starting Gate 5. It does
not define gate numbering, financial types, roles or tax rules. Those meanings
remain with the current contracts linked below.

## Boundary in one view

```text
active ordinary-trade source semantics
-> exact qualified mapping + deterministic Source Observations/runtime records
-> Gate 4 Fact v2 compatibility adapter (no SQL)

historical deployment rollback
-> Gate 3 annotations
-> Gate 4 materializer + rebuildable SQL case view

both
-> exact Gate4FinancialCaseFactV2
-> deterministic Gate 5
```

Gate 4 answers: **what financial facts are currently present in the assembled
case?** It does not answer what those facts mean for taxation.

## Official input for Gate 5

For the active ordinary-trade route, create the fact producer only through:

```text
Gate4OrdinaryTradeCandidateRuntimeFactory(store, read_enabled).create()
```

It exposes `list_facts(context)` and is injected into the unchanged
`Gate5DeterministicSourceFactConsumptionRuntime` only by
`OrdinaryTradeCandidateRuntimeFactory.create`. It reads the current immutable
ordinary projection, not Canonical, Gate 3 or SQL.

For the retained historical deployment-rollback route, create the Gate 3-backed
case runtime only through:

```text
Gate4FinancialCaseRuntimeFactory(store, read_enabled).create()
```

Use its public methods:

```text
read_case(context)
list_facts(context)
get_fact(context, fact_id)
list_by_financial_type(context, financial_type)
list_by_asset(context, asset)
list_by_period(context, date_from, date_to)
```

`ArtifactAccessContext` remains the trusted OpenWebUI user/case/workspace
scope. Gate 5 must not supply those identities as separate query parameters.

Both ports return complete `Gate4FinancialCaseFactV2` payloads. Each fact
provides:

```text
fact_id
financial_type
typed roles with normalized value or explicit missing
status = role_complete | role_incomplete
provenance and exact upstream bindings
```

Gate 5 consumes typed role values. It may retain provenance for audit, but it
must not reinterpret `annotation_target` or role source targets as a document
grammar.

## Current, rebuild and completeness semantics

The SQL cache is a deletable implementation detail, not authority. The same
exact current upstream rebuilds the same logical facts, IDs, values and
provenance. On the historical route, if the selected Gate 3 sidecar, active
canonical version or current document set changes, old reads fail closed as
missing or stale until rebuild. On the active ordinary route, only a projection
bound to the exact active Canonical is readable; zero or multiple current
projections fail closed.

`CASE_COMPLETE_FOR_CURRENT_INPUT_SET` is a historical Gate 3/SQL-route status.
It means only that every readiness-visible
current document has a selected Gate 3 V2 sidecar and the cache exactly matches
that technical input set. It does not mean that every required document was
uploaded, Gate 3 found every financial fact, economic history is complete, or
the case is ready for a tax calculation.

## Explicit limitations

- Gate 3 annotations are sparse positive claims on the rollback route. The
  active ordinary compiler accounts for every non-empty data row after a
  matched header and every non-empty unknown-table row; titles and headers stay
  in Canonical/mapping evidence. Only `RUNTIME_READY` observations may produce facts;
  `RELEVANT_UNMAPPED` never reaches Gate 5.
- `role_incomplete` is a valid visible fact state; Gate 4 never guesses a
  missing required value.
- The Financial Case covers only the current input set known to the existing
  OpenWebUI/ArtifactStore case scope.
- G4.4 proved no current need for persisted semantic relations. The minimal
  relation set is empty and G4.5 is `NOT_APPLICABLE_WITHOUT_NEW_EVIDENCE`.

## Gate 5 must not cross upstream

Gate 5 must not read broker reports, parse `CanonicalArtifactV1`, consume Gate
3 targets or Source Observations directly, query physical Gate 4 SQL tables, repeat financial
classification or add broker adapters. If it needs any of those operations,
the upstream boundary has been bypassed or an explicit upstream gap must be
reported.

The Fact v2 field name `gate3_binding` is compatibility debt. On the active
ordinary route it binds the ordinary projection artifact and Canonical identity;
it does not authorize a Gate 3 read or prove Gate 3 execution.

Gate 5 starts with tax methodology over the prepared Financial Case. This
handoff does not design a tax DTO, dictionary, FIFO/cost-basis engine, tax
rules, declaration, FNS XML or PDF projection.

## Direct current contracts

1. [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) — sole current
   gate map and status authority.
2. [Gate 4 Financial Case Fact v2](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md)
   — exact fact meaning and schema.
3. [Gate 4 Case Assembly v1](./BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md) —
   whole-case and technical completeness semantics.
4. [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md)
   — official runtime, cache, rebuild and stale semantics.
5. [Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md)
   — semantic ceiling and Gate 2-5 responsibility map.
6. [Architecture Authorities](./BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md) —
   maintained implementation owners.

Read [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) only when the
historical rollback route or an upstream Gate 3 invariant must be audited. It
is not the active ordinary-trade entrypoint.
