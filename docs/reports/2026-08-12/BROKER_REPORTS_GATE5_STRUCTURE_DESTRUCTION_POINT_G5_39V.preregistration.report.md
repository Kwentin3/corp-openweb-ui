# G5.39V Financial Fact Structure Destruction-point Audit — preregistration

Status: `FROZEN_BEFORE_REPRESENTATION_CONTENT_REVIEW_AND_LLM_PROBES`
Date: `2026-08-12`
Mode: research only; no production implementation or CanonicalArtifact redesign.

## Question

For three reviewed broker-report facts, identify the first real transition from
rendered source to actual Gate 3 model context at which human-readable event
grouping is no longer recoverable without guessing or outside knowledge.

The audit does not author a relation heuristic or solve universal region
selection.

## Frozen product and research boundary

- Product entry HEAD: `02659a9b0bdfb2f19171d2a070a660af85119d59`.
- Product entry HEAD tree: `0a696522eb37eca13bb9224a41f7227823c8ce8c`.
- The product worktree was already dirty and remains outside experiments.
- The isolated research repository lives under ignored `local/` and will be
  removed after safe evidence is published.
- Diagnostic code may read private source/evidence and call the existing model
  client factory. It may not write product code, canonical artifacts, sidecars,
  databases, stage state, or provider configuration.

## Frozen corpus and facts

The source set is byte-identical to G5.39/G5.39R:

| Fact ID | Assignment | Source SHA-256 | Reviewed fact |
|---|---|---|---|
| `V_DEV_PURCHASE` | DEV | `25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67` | aggregate securities purchase with transaction charge |
| `V_HOLDOUT_DISPOSAL` | independent real holdout / positive control | `79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d` | row-local securities disposal transaction |
| `V_LARGE_DIVIDEND` | large real context pressure | `7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015` | dividend payment with withholding and accrual evidence |
| `V_NEGATIVE_AB` | synthetic diagnostic | `c66b97a950b07ac25d8716884369867078e0c5e4474f58dd822e0b3660e5f639` | two similar transactions with explicit positive grouping and forbidden mixed grouping |

Private reviewed oracle SHA-256:
`d76ade254cfe2c323e0ab73daf0fcf83d598034022e096dba6c86173a65e6c85`.

No source, fact, oracle refs, or representation is changed after a probe result
is observed. A material defect invalidates the affected trace and requires a
new version.

## Frozen stages

Each real fact is traced through:

1. `A_RENDERED_ORIGINAL`: exact rendered source page(s).
2. `B_EARLIEST_EXTRACTED`: earliest available text/layout/table atoms and
   geometry produced by the existing PDF evidence path.
3. `C_VISUAL_TABLE_PROJECTION`: actual validated pipeline table/structural
   projection, including headers, rows, cells and retained geometry where
   present.
4. `D_CANONICAL_ARTIFACT`: exact current/readable `CanonicalArtifactV1` for the
   same source where available; if a source lacks a current exact artifact,
   record `UNAVAILABLE` rather than synthesize one.
5. `E_ACTUAL_GATE3_CONTEXT`: exact model view built through
   `CanonicalReaderFactory -> Gate3ProjectionFactory ->
   Gate3StructuralChunkFactory`, and accepted-target role context through
   `Gate3RoleContextFactory` when an accepted target exists.

No theoretical prompt or hand-authored canonical reconstruction can substitute
for stages D/E.

## Recoverability adjudication

For every fact/stage, private forensic evidence records:

```text
grouping_recoverable = YES | NO | AMBIGUOUS | UNAVAILABLE
necessary_fragment
concrete_preserved_signals
concrete_lost_signals
whole_document_chars
bounded_fragment_chars
bounded_fraction
```

`YES` requires a competent reviewer to identify the same event grouping using
only that representation. Schema-field presence is insufficient. `NO` means
the reviewed member atoms cannot be joined without guessing or outside
knowledge. The destruction point is the first `YES -> NO` transition.

The reviewed oracle is unavailable to representation builders and LLM probes;
it is opened only by the evaluator after outputs are frozen and hashed.

## Blind clean LLM diagnostic

For each distributed real fact, one bounded representation immediately before
the candidate loss and one actual representation immediately after it are
probed. The row-local holdout is the positive control. The A/B fixture is the
cross-event negative.

Frozen profile:

```text
provider route: Gate2StructuredModelClientFactory.create
model: gpt-5.4-mini-2026-03-17
temperature: 0
retry: 0
repair: 0
best-of-N: false
answer merge: false
one representation: one call
whole large document: forbidden
```

Each call receives only its bounded representation, a closed response schema,
and this neutral task: propose at most one financial fact and bind every role
to exact visible ref/literal evidence; otherwise return `UNRESOLVED`. It does
not receive oracle refs, expected values, correct rows, broker identity, or a
broker template. Reviewed region selection is permitted but must not filter the
region down to oracle role atoms.

Output is frozen before oracle adjudication as:

```text
PROPOSED_CORRECT
PROPOSED_INCOMPLETE
PROPOSED_CROSS_EVENT
INVALID
UNRESOLVED
```

No failed semantic output is repaired or rerun. A pre-inference transport or
configuration failure may be separately attributed, but it does not become a
semantic result.

## Context constraint

- Every probe fragment is measured in exact characters and UTF-8 bytes; token
  usage comes from provider usage when available.
- `LARGE_REAL_001` whole-document model context is forbidden.
- The audit may use reviewed locations or current accepted semantic regions to
  isolate a candidate region, but it may not implement H4-style model
  navigation or a new retrieval mechanism.
- Existing structural map/ref lookup is audited read-only for feasibility.

## Hard stops

The audit stops rather than changing production if it would require:

- a T-Bank or broker-specific parser/template;
- CanonicalArtifact modification or republishing;
- Gate 3 owner/prompt/schema changes;
- a relation heuristic, graph, database or persistence surface;
- whole-large-document LLM context;
- retry, consensus, repair or answer merging;
- weaker exact-ref/literal validation.

## Allowed findings

```text
GATE3_CONTEXT_STRUCTURE_LOSS
CANONICAL_STRUCTURE_LOSS
EXTRACTION_STRUCTURE_LOSS
STRUCTURE_PRESERVED_LLM_GROUPING_UNRELIABLE
WHOLE_DOCUMENT_CONTEXT_REQUIRED
another equally precise evidence-backed finding
```

The table hypothesis verdict is diagnostic only: `SUPPORTED`, `PARTIAL`, or
`REJECTED`.

Even a proven destruction point authorizes only one next narrow research
question. It does not authorize implementation.
