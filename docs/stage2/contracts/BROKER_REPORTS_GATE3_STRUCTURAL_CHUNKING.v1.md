# Broker Reports Gate 3 Structural Chunking v1

Status: `ACTIVE_IN_NDFL`

Goal: `G3.4B`

Runtime activation: `NDFL_ONLY_BY_G3.C5`

Persistence: `false`

Date: 2026-08-07

## 1. Purpose

This contract bounds the existing G3.2 model view without introducing a second
renderer, alias issuer or semantic selection path:

```text
CanonicalReaderFactory.create
-> Gate3ProjectionFactory exact internal render plan
-> Gate3StructuralChunkFactory.create
-> ordered Gate3StructuralChunkSetV1
```

One call consumes exactly one authenticated document and active canonical
version. It cannot combine documents.

## 2. Ownership

`Gate3ProjectionFactory` remains the sole owner of Markdown rendering and
temporary `target_alias -> canonical_target` identities. Its public
`Gate3ProjectionV1` bytes remain unchanged. The package-internal render plan
only exposes the exact already-rendered structural units needed by
`Gate3StructuralChunkFactory`; it does not mint aliases or render financial
content again.

`Gate3StructuralChunkFactory.create(document_id, context)` owns only:

- deterministic structural boundaries;
- the exact character budget;
- context-only repetition;
- ordered subset projection of existing target mappings;
- fail-closed coverage and order checks.

It owns no financial meaning, model execution, annotation merge or storage.

## 3. Budget

The v1 measure is exact Python `len(model_view.content)` characters. The
default bound is 60,000 characters per final chunk model view, including the
context/target wrapper and repeated structural context.

The budget is a deterministic pre-provider bound, not a token estimate. A
caller may narrow it through the factory constructor. No tokenizer/provider
infrastructure is part of v1.

If one indivisible row or non-table structural block plus its required context
exceeds the configured budget, construction raises
`gate3_structural_chunk_indivisible_unit_exceeds_budget`. It must not split the
unit, omit it or return a partial chunk set.

## 4. Algorithm

1. If the complete G3.2 projection fits, return one `whole_document` chunk with
   the exact original model view.
2. Otherwise traverse the exact G3.2 structural render plan in document order.
3. Keep a table whole when its final chunk view fits.
4. Split only an oversized table into the largest fitting contiguous groups of
   whole rendered rows.
5. Pack adjacent non-table nodes only inside the same natural container
   context. Do not cross a table boundary.
6. Carry alias-free sheet/page breaks and empty structural containers into the
   next target-bearing chunk as context-only structure. Do not turn them into
   independent working requests when a following target-bearing unit exists.
7. Preserve terminal alias-free structure in a bounded structural chunk only
   when there is no following target-bearing unit to carry it.
8. Fail closed if one structural unit cannot fit.

Data row overlap is always zero.

## 5. Context envelope

The context-only part may contain only structure already rendered by G3.2:

- ancestor document/page/sheet/section headings;
- structurally rendered page/sheet breaks and empty containers;
- table heading/title;
- generic Markdown column headings;
- the canonical table header row for chunks after the first;
- structurally attached table notes.

Every alias marker is stripped from repeated context. The original alias stays
visible in exactly one working chunk. Context-only repetition therefore cannot
create a second labelable target.

If Gate 2 does not structurally attach a heading/note to the container or table,
the chunker does not infer the relationship.

## 6. Identity and coverage

Each chunk contains:

- deterministic `chunk_id`;
- one-based ordinal;
- the same document/canonical-version binding as the source projection;
- backend-only container/node/row scope;
- one bounded Markdown `model_view`;
- an ordered subset of the exact G3.2 target mappings;
- exact size, target and context-overhead counts.

The terminal set proves:

```text
lost_targets = 0
duplicated_working_targets = 0
context_only_target_aliases = 0
data_row_overlap = 0
target_order_preserved = true
```

Target order is the visible target order of the original G3.2 projection.
Chunking does not change `Gate3CanonicalTargetV1`.

## 7. Empty cells

G3.4B does not remove aliases from display-empty canonical cells. G3.2 v1
currently requires every canonical cell to receive one alias, so changing this
would alter an existing target/addressability contract. The measured potential
saving remains a later optional review item; it is not the chunking architecture.

## 8. Forbidden behavior

The chunker must not:

- inspect dictionary labels or meanings;
- use financial/tax keyword rules;
- rank or filter rows semantically;
- call an LLM/provider, Tool, Skill, Knowledge, RAG or embeddings;
- read source files, parser payloads, private evidence or physical storage;
- create overlapping data windows;
- create a second renderer, alias grammar or target identity;
- persist chunks or annotations;
- batch, retry, merge or activate a product route.

## 9. Schema

The closed boundary schema is
[`Gate3StructuralChunkSetV1`](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNK_SET.v1.schema.json).
It reuses the existing `Gate3CanonicalTargetV1` reference and introduces no
ArtifactStore type.

## 10. Stop

G3.4B itself ends after deterministic construction, representative real-corpus
evidence and human review artifacts. The chunker performs zero provider calls;
G3.C5 consumes its output inside NDFL and delegates model execution to the
existing bounded-labeling owner.

The next allowed goal after human review is:

```text
G3.4C — Bounded Chunk Batch Labeling Live Reproof
```

G3.4C is not authorized or started by this contract.
