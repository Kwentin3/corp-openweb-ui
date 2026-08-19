# Broker Reports Gate 5 Real Tax Case Assembly v0

Status: `CURRENT SUPPORTING CONTRACT`

Goal: `G5.40F`

Date: 2026-08-13

## Boundary

`Gate5RealTaxCaseAssemblyRuntimeFactory.create` is the sole demand-first case
assembly owner. It composes, without persistence:

- `Gate5DeterministicSourceFactConsumptionRuntimeFactory.create` for current
  normalized financial facts, independent FIFO groups and exact blockers;
- `Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create` for the
  published declaration-domain partition;
- `Gate5FullDeclarationDefinitionAuthoringFactory.create` for the exact
  hash-pinned reviewed obligation package and its official requirements.

It does not read source documents, Canonical, Gate 3 targets, SQL, or providers.
It adds no TaxCase table, workflow, registry, evidence graph or relation store.

## Consumer-first case

The runtime starts from all 25 reviewed declaration demands. For each demand it
retains:

```text
demand
required tax rule and official evidence refs
required evidence
available evidence
terminal
exact blocker, when present
```

Allowed demand terminals are:

- `AVAILABLE`;
- `MISSING_EVIDENCE`;
- `SOURCE_EVIDENCE_INSUFFICIENT`;
- `METHODOLOGY_UNRESOLVED`;
- `NOT_ACTIVATED_FOR_SUPPLIED_CASE`;
- `RESOLVED`.

An unresolved demand is never omitted. Each blocker identifies the declaration
demand, methodology/Definition binding, required fact, searched evidence,
insufficiency reason and evidence kind that could close it.

A demand terminal is not a global pipeline terminal. It blocks only that named
declaration demand and consumers that explicitly depend on it. Independent
deterministic calculations returned by the source-fact consumer remain in the
assembly even when another demand or group is unresolved.

## Knowledge origins

The case inventory keeps the five origins separate:

| Origin | Meaning | Authority in this boundary |
| --- | --- | --- |
| A | source / financial fact | Gate 4 case through the deterministic source-fact consumer |
| B | external reference fact | reviewed obligation package and official evidence binding |
| C | user / case fact | absent unless supplied through an existing authenticated owner |
| D | methodology-derived tax fact | only deterministic calculations actually returned by the source-fact consumer |
| E | declaration / filing context | absent unless supplied through an existing authenticated filing owner |

The G5.40F real replay supplies A and B. C and E remain explicit
`MISSING_EVIDENCE`; D is absent when no source group satisfies its inputs.
Neither a default taxpayer nor a synthetic filing context is permitted.

## Multi-source semantics

Case identity means only that the independently normalized evidence belongs to
the same authenticated case and tax-period task. It never means that rows from
different documents are the same financial event. Exact asset, currency,
date/order, type and methodology conditions are selection inputs; similarity,
proximity and model judgment are forbidden.

`REAL_EVIDENCE` and `SYNTHETIC_CONTROL` are distinct runtime modes. Synthetic
control can verify behavior but cannot emit `REAL_CASE_ASSEMBLY_PROVEN`.

## Completeness

This boundary owns only supplied-case accounting. It may assert that every
reviewed demand has been classified and every known blocker has been localized.
It cannot assert real-world taxpayer completeness, absence of other taxable
activity, declaration readiness or filing eligibility.

`RESOLVED` is permitted only with a complete evidence chain. Available source
facts that have not reached a complete declaration obligation remain
`AVAILABLE` or the corresponding precise blocker terminal.

## Non-goals

No provider or LLM decision, supplemental synthetic repair, global accounting
reconciliation, detail/aggregate deduplication, currency default, source
jurisdiction guess, persisted event relation, declaration activation, product
route, commit or publication is authorized by this contract.
