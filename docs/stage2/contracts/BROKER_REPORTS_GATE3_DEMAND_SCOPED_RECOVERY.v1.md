# Broker Reports Gate 3 Demand-Scoped Recovery v1

Status: `CURRENT SUPPORTING CONTRACT`

Goals: `G5.55`, `G5.56`

Owner: `Gate3FinancialAnnotationsPersistenceFactory.create`

## Purpose

This contract refines publication semantics for the existing immutable
`FinancialAnnotationsV2` sidecar. It adds no store, merge framework, source
reader or economic identity.

```text
RECOVERY DELTA != FULL SEMANTIC SNAPSHOT
absence_from_delta != source_negation
```

The batch result carries one exact `semantic_scope`:

- `publication_mode = FULL` with no requested labels; or
- `publication_mode = DEMAND_SCOPED` with a non-empty sorted set of requested
  published labels, the document identity and selected structural chunks.

`complete` continues to describe successful processing of the selected
chunks. It does not upgrade `DEMAND_SCOPED` to `FULL`, even when one chunk is
the whole document.

## Operations

`save` admits only a `FULL` all-chunk result and retains the existing immutable
replacement semantics.

`save_recovery` admits only a successfully validated `DEMAND_SCOPED` result,
an explicit current base sidecar and one demand request identity. It publishes:

```text
current validated full view + recovery delta -> next validated full view
```

The persisted sidecar remains a complete current view for ordinary Gate 4
consumption. Safe metadata and the returned receipt distinguish the operation
as `DEMAND_SCOPED` and record its base, demand, requested meanings and aggregate
add/supersede/preserve/conflict/delete counts.

## Same-source assertion identity

The baseline recovery identity is:

```text
canonical document/version + canonical target + financial label
```

It is source-assertion identity, not economic-transaction identity. No event
relation, proximity rule, FIFO rule or cross-target matching is introduced.

One narrow Canonical-refinement case also proves the same source assertion:

```text
same canonical document/version
+ same financial label
+ one table_cell anchor and one table_row anchor
+ same table node_id and row
+ every bound role target remains inside that same table row
```

This is structural row ownership already present in Canonical, not similarity
or economic matching. Runtime does not compare dates, assets, quantities,
amounts, currencies, unit prices, literals, visual pixels or ordinary spatial
overlap. Cell-to-cell, row-to-row and different-row targets are not collapsed
by this refinement rule. A visual source audit may qualify the invariant but
is not a production dependency.

For one exact assertion:

- identical role bindings are unchanged;
- a proposal may supersede an existing assertion only when every existing
  bound role is identical, no bound role becomes missing, and at least one
  missing role becomes bound;
- when the narrow row-ownership proof above holds, a compatible `table_row`
  proposal supersedes its `table_cell` anchor even if role completeness is
  unchanged; the row anchor owns the full source assertion;
- a different bound value/target, a regression, duplicate assertion or
  ambiguous base fails closed.

A different canonical target with the same label is added unless the narrow
row-ownership proof applies. Conflicting complete role bindings remain a
conflict even when row ownership proves that the anchors refer to one source
assertion; no second assertion is published and no existing assertion is
mutated.

## Non-destructive invariant

Demand recovery has no delete operation:

- unrelated existing facts are copied unchanged;
- facts absent from the delta are copied unchanged;
- an empty validated delta publishes the identical full view with zero
  deletions;
- stale base, authority mismatch or canonical-version mismatch fails before
  an ArtifactStore write.

Therefore every successful recovery has:

```text
UNRELATED_VALIDATED_FACT_LOSS = 0
deleted_total = 0
```

Removal belongs only to a separately authoritative full-scope reevaluation.
G5.55 defines no general removal policy.

## Downstream

Gate 4 keeps selecting the latest validated V2 sidecar and receives its full
current semantic view. Gate 5 keeps consuming only the resulting Gate 4 facts.
Neither consumer reads or merges the recovery delta.

## Forbidden

No second fact store, mutable overwrite, event log, version graph, generic
conflict resolver, identity graph, economic identity, Gate 5 Canonical read,
provider retry, semantic repair or full-rich-Canonical cost optimization is
allowed here.
