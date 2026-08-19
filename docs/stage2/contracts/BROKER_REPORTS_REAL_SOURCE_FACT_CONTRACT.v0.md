# Broker Reports Real Source-Fact Contract v0

Status: `CURRENT SUPPORTING CONTRACT`

Goal: `G5.40E`

Date: 2026-08-13

## Boundary

The bounded real-source path is:

```text
source bytes
-> existing full-source and table owners
-> CanonicalArtifactV1
-> Gate3StructuralChunkFactory
-> one frozen Gate 3 semantic/role proposal
-> FinancialAnnotationsV2
-> Gate4FinancialCaseFactV2
-> deterministic Gate 5 assessment/consumer
```

Every transition is factory-routed. Provider output remains a proposal. No
source reader, broker dictionary, relation graph, reconciliation layer, RAG,
embedding path, or post-provider repair is added.

## Source preservation

- A ready table projection bound to a parser unit replaces that unit once.
- A ready source-bound visual projection without a parser-unit alias survives
  as a standalone canonical table; parser text remains independently present.
- Logical zero-based projection coordinates are accepted without treating the
  first row as a header unless the source projection declares a header.
- PDF layout accounting covers the complete bounded document inventory.
- Page and heading context may share a structural chunk; it must not force one
  chunk per page or duplicate/drop target aliases.
- A non-empty source value is never discarded merely because Gate 4 cannot
  promote it to a tax-ready ISO date or decimal. Gate 4 preserves the exact
  `source_literal`; only unambiguous date/number formatting is normalized.
- The SQL cache indexes only a valid ISO calendar date. Other source date
  literals remain in the immutable fact JSON and cannot enter period queries.

## Currency and context

Currency is source-authored evidence. ISO literals remain ISO literals; a
symbol remains a symbol. Report, account, broker, locale, or security-name
context does not authorize symbol-to-ISO conversion. Gate 5 rejects non-ISO
currency when a tax input requires ISO currency.

Commission is direct disposal expense only when charge and disposal targets
share the same canonical table node and one-based row. Page, proximity, date,
asset, literal equality, coarse table node, and ordinary text-node equality are
insufficient. No purchase-to-sale or charge-to-disposal relation is persisted.

## Deterministic sufficiency

`Gate5DeterministicSourceFactConsumptionRuntime.assess` preserves commission
and withheld-tax detail/aggregate assertions independently and returns a
per-fact sufficiency result for purchases/disposals. It never drops incomplete
facts to make FIFO appear complete.

`run` performs FIFO only when the whole selected case has complete, valid
source facts and sufficient acquisition quantity. Missing roles, partial dates,
non-ISO currency, invalid quantities, insufficient prior lots, and unresolved
same-date ordering fail closed. Partial acquisition commission and currency
conversion remain `METHODOLOGY_UNRESOLVED`.

## Terminal meaning

`UPSTREAM_SOURCE_FACT_LOSS_ELIMINATED` means that the bounded corpus has no
lost or duplicated Gate 3 target aliases and every validated annotation reaches
Gate 4 with exact canonical and source-literal provenance. It does not mean
that each source contains a complete tax history.

`REAL_SOURCE_CONTRACT_PARTIALLY_PROVEN` is permitted only for explicit
source-authority gaps. It must name those gaps and must not disguise parser,
table, chunking, currency-context, or Gate 4 materialization loss.

## Non-goals

No product activation, declaration filing-context inference, currency mapping,
commission allocation, aggregate reconciliation, generic event ontology,
graph, broker-specific adapter framework, commit, push, or PR is authorized by
this contract.
