# Broker Reports Gate 3 Chunk Batch Labeling v1

Status: `ACTIVE_IN_NDFL`

Goal: `G3.4C`

Runtime activation: `NDFL_ONLY_BY_G3.C5`

Persistence: `false`

Date: 2026-08-07

## 1. Purpose

This contract proves the already-built Gate 3 MVP path over bounded structural
chunks:

```text
one active CanonicalArtifactV1
-> Gate3StructuralChunkFactory.create
-> for each preselected chunk, sequentially:
   Gate3BoundedLabelingFactory.create_from_chunk
   -> existing provider route
   -> existing deterministic validation
-> deterministic in-memory annotation merge
```

`Gate3ChunkBatchLabelingFactory.create` is the only batch/merge coordinator. It
does not own projection, chunking, financial meaning, dictionary rendering,
instruction wording, provider adaptation or persistence.

## 2. Frozen inputs

G3.4C must not change:

- the G3.4B 60,000-character final-chunk budget;
- table-first/contiguous-whole-row boundaries;
- context envelope, alias grammar, target allocation or zero-overlap policy;
- published dictionary `broker-reports-financial-labels@1.0.0` and its nine
  labels;
- instruction `broker-reports-bounded-semantic-labeling@1.0.0`.

An observed defect is evidence. It is not repaired inside this proof.

## 3. One-attempt execution

Each selected chunk receives exactly the same three meaningful model-visible
parts:

1. exact task instruction;
2. exact full dictionary v1 rendering, once;
3. exact chunk `model_view.content`.

One chunk permits at most one provider submission. Execution is sequential.
There is no retry, repair, fallback, second model, broker-specific prompt,
concurrency controller, queue or scheduler.

The only provider route remains `Gate2StructuredModelClientFactory.create` and
its request builder/adapters. `Gate3BoundedLabelingFactory.create_from_chunk`
only adapts the exact chunk fields into the already validated G3.4 request
shape; it does not render or mint targets.

## 4. Validation and terminal outcomes

The existing G3.4 validator checks the closed response, exact schema version,
known alias, published label and duplicate pair, then restores the existing
canonical target in backend memory.

Each chunk has one terminal outcome:

- `validated`;
- `rejected` for a returned but invalid proposal;
- `provider_failed` for a terminal provider-route failure.

Invalid output is never repaired into success. Processing may continue to the
next independently selected chunk, but any rejection/failure makes the tested
document result `incomplete`.

## 5. Selection and document status

The default selection is every chunk of one document. A proof may pass a
strictly increasing, duplicate-free, predeclared ordinal subset. Missing,
duplicate, reordered or foreign ordinals fail before provider execution.

Document statuses are:

- `complete`: every chunk was selected and validated;
- `incomplete`: at least one selected chunk was rejected or provider-failed;
- `representative_subset_validated`: every selected subset chunk validated,
  but the document is explicitly not claimed complete.

No request or merge may mix canonical bindings from different documents.

## 6. Merge

Merge concatenates only validated annotations in selected chunk order and
canonical target order. It preserves exact dictionary, instruction, model and
canonical identities. It does not:

- infer or correct a label;
- select a better proposal;
- join facts or create relationships;
- semantically deduplicate;
- turn an incomplete/subset result into a complete document claim.

The merged `FinancialAnnotationsV1` proposal remains in memory. ArtifactStore
registration and persistence belong only to a separately authorized G3.5.

## 7. Evidence and metrics

Exact customer-bearing canonical envelopes, chunks, instruction, dictionary,
final provider-visible inputs, raw provider outputs and validated outputs stay
outside Git. Repository evidence contains only privacy-safe aggregates and
hashes.

For each live request record chunk characters, working aliases, provider input,
output and total tokens when returned, duration, dictionary injection count,
terminal status and private evidence hash. Batch reports must distinguish peak
request context from total batch work.

## 8. Forbidden behavior

G3.4C must not add persistence, ArtifactStore writers, workflow, OpenWebUI
product integration, RAG, semantic prefiltering, deterministic financial
classification, new labels, dictionary/instruction variants, retry/repair,
provider fallback, data overlap or Gate 4 behavior.

## 9. Stop

G3.4C itself ends after the bounded live proof, deterministic merge,
privacy-safe evidence and human review material. G3.C5 now consumes that exact
coordinator inside NDFL; only the outer workflow may pass a complete result to
the existing G3.5 persistence owner. There is no next Gate 3 GOAL.
