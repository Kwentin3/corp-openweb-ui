# Broker Reports PDF Source-Bound Table Normalization v2

Status: `PROPOSED / INACTIVE`

This candidate contract records the intended owner boundary for Issue #317. It
does not supersede v1, activate a product route, or authorize imports from the
current Pipe, Canonical normalizer, actions, or generated bundles.

## Scope of this slice

`LogicalRowTableFactory` is the candidate sole owner of logical table identity,
ordered rows, logical columns, source-bound title/header retention, and
cross-page continuation. In this inactive slice it consumes only the existing
normalized PDF text-layer projection and publishes only its existing recovery
result.

The owner does not decide financial meaning, create source values, mutate
Canonical, publish facts, or call a provider. `NormalizedTableProjection` and
Canonical integration remain outside this slice.

## Source authority

FullSource parser words and geometry remain authoritative. Every retained
title, header, body entry, and continuation fragment must point to those exact
source refs. A title or header cannot be discarded merely to make two fragments
geometrically compatible.

Exact word accounting is necessary but does not by itself prove table identity.
Every source word must still have exactly one table-entry or paragraph owner.

## Fragment-local continuation rule

A right fragment may join one previous logical table only when all of the
following are true:

1. its page immediately follows the predecessor page;
2. the predecessor reaches the page bottom and the right fragment starts at
   the next page top under the configured source-geometry thresholds;
3. the fragments have compatible width and multi-column alignment;
4. the first fragment supplies a complete stable leading header stack with
   body support;
5. a right-side stable header stack, when present, repeats that full stack;
6. the predecessor is unique;
7. the right fragment has no new source-bound title.

A headerless fragment is a continuation candidate, not proof on its own. A
repeated header is retained as provenance but does not override a new title.
A new source-bound title is a hard table boundary even when grid and header are
otherwise identical.

Header evidence is structural and covers every leading header row, not the
first text row. Existing row roles, proven header coalescence, column evidence,
and body support may prove the stack. If a text-only fragment can be either a
header stack or body data and no source-bound header-presence evidence exists,
this inactive slice must not guess. It remains separate and `PARTIAL` with
`logical_table_continuation_header_ambiguous`. Exact header-present/header-
absent refs are deferred to the source-bound scope slice; they are required
before such a fragment can join autonomously.

For a chain of three or more pages, the first fragment remains the stable header
authority. Each adjacent pair must independently satisfy the page-edge and grid
conditions.

## Fail-closed terminals

- One compatible predecessor: join the fragment.
- No compatible predecessor: keep a separate logical table.
- More than one compatible predecessor: keep a separate table, emit
  `logical_table_continuation_ambiguous`, and publish `PARTIAL` completeness.
- Header presence cannot be distinguished from text-only body rows: keep the
  fragment, emit `logical_table_continuation_header_ambiguous`, and publish
  `PARTIAL` completeness.

Ambiguity must not be silently resolved by iteration order, text deletion, or a
fallback continuation writer.

## Invariants

- This owner remains inactive until a separate controlled-cutover PR changes
  the current architecture authority and product graph.
- The active neutral grouping and mechanical continuation linker are unchanged
  by this slice.
- No broker, year, filename, language, or header dictionary participates.
- No model-authored text, cells, values, table identity, or facts are accepted.
- `LogicalRowTableFactory` makes the continuation decision; a later projection
  adapter may only carry that decision.
- Canonical must not repair or reinterpret this result.
- Any unresolved continuation is `PARTIAL` and therefore cannot support atomic
  fact publication.

## Focused controls

The inactive owner must prove at least:

- an adjacent, structurally proven headerless next-page fragment joins its
  unique predecessor;
- same-grid tables with a distinct source-bound title remain separate even
  when the column header repeats;
- the complete stable multi-row header stack participates in the decision;
- a text-only fragment without header-presence evidence is retained with an
  inspectable `PARTIAL` terminal rather than silently joined or discarded;
- a three-page edge-continuous chain becomes one logical table;
- multiple compatible predecessors produce an inspectable `PARTIAL` result;
- exact title/header source refs and total word ownership are preserved.

These controls are owner evidence only. They are not product activation,
full-document Canonical proof, financial-role proof, or release acceptance.
