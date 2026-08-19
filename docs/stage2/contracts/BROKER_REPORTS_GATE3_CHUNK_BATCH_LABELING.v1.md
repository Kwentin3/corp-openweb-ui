# Broker Reports Gate 3 Chunk Batch Labeling v1

Status: `ACTIVE_IN_NDFL`

Goal: `G3.4C`

Runtime activation: `NDFL_ONLY_BY_G3.C5`

Persistence: `false`

Date: 2026-08-07

Updated: 2026-08-08

## 1. Purpose

This contract proves the already-built Gate 3 MVP path over bounded structural
chunks:

```text
one active CanonicalArtifactV1
-> Gate3StructuralChunkFactory.create
-> for each preselected chunk, sequentially:
   Gate3BoundedLabelingFactory.create_from_chunk
   -> existing provider route and type validation
   if validated facts are non-empty:
      Gate3RoleLabelingFactory.create_from_chunk
      -> same provider route, aliases and chunk
      -> Role Pack validation and source binding
   else skip the role provider call
-> deterministic in-memory FinancialAnnotationsV2 merge
```

`Gate3ChunkBatchLabelingFactory.create` is the only batch/merge coordinator. It
does not own projection, chunking, financial type/role meaning, dictionary or
Role Pack rendering, instruction wording, provider adaptation or persistence.

## 2. Frozen inputs

G3.4C must not change:

- the G3.4B 60,000-character final-chunk budget;
- table-first/contiguous-whole-row boundaries;
- context envelope, alias grammar, target allocation or zero-overlap policy;
- published dictionary `broker-reports-financial-labels@1.0.0` and its nine
  labels;
- published Role Pack `broker-reports-financial-roles@1.0.0`;
- instruction `broker-reports-bounded-semantic-labeling@1.0.2`.

An observed defect is evidence. It is not repaired inside this proof.

## 3. Two bounded passes

Pass 1 receives exactly the same three meaningful model-visible parts:

1. exact task instruction;
2. exact full dictionary v1 rendering, once;
3. exact chunk `model_view.content`.

If pass 1 returns facts, pass 2 receives its instruction, the complete Role
Pack once, and one combined context containing all fact aliases plus the same
chunk. Thus a non-empty chunk creates exactly two semantic tasks and an empty
chunk exactly one. Operational resubmissions are bounded separately and are
never multiplied by the number of facts.
Execution is sequential. A provider task may make one bounded operational
resubmission only after `gate2_model_provider_unavailable` proves that no
semantic response exists. The resubmission must use the exact same sealed
prepared-request hash and stops at the first semantic response. There is no
semantic-response retry, repair, fallback, second model, broker-specific
prompt, concurrency controller, queue or scheduler.

The only provider route remains `Gate2StructuredModelClientFactory.create` and
its request builder/adapters. `Gate3BoundedLabelingFactory.create_from_chunk`
only adapts the exact chunk fields into the already validated G3.4 request
shape; it does not render or mint targets.

## 4. Validation and terminal outcomes

Pass 1 checks the closed response, exact schema version, known alias, published
label and duplicate pair. Pass 2 checks the exact pass-1 fact/label set,
allowed roles, cardinality, target aliases and literal `exact_text`, then
restores canonical targets. Persistence repeats these source-binding checks.

Each chunk has one terminal outcome:

- `validated`;
- `validated_with_local_rejections` when the chunk has a contract-valid V2
  output but one or more source-invalid role bindings were replaced with
  explicit `missing`;
- `rejected` for a returned but invalid proposal;
- `provider_failed` for a terminal provider-route failure.

Invalid output is never repaired into success. Processing may continue to the
next independently selected chunk. A structurally rejected or provider-failed
chunk makes the tested document result `incomplete`; a local role rejection
does not erase its contract-valid chunk output.

## 5. Selection and document status

The default selection is every chunk of one document. A proof may pass a
strictly increasing, duplicate-free, predeclared ordinal subset. Missing,
duplicate, reordered or foreign ordinals fail before provider execution.

Document statuses are:

- `complete`: every chunk was selected and has a contract-valid output,
  including `validated_with_local_rejections`;
- `incomplete`: at least one selected chunk was rejected or provider-failed;
- `representative_subset_validated`: every selected subset chunk validated,
  but the document is explicitly not claimed complete.

No request or merge may mix canonical bindings from different documents.

Every result also carries a machine-readable `semantic_scope`. A run without a
requested-label filter is `FULL`; a run with `requested_financial_labels` is
`DEMAND_SCOPED` even when the selected chunks happen to cover the whole
document. Thus `complete` proves successful selected-chunk execution, not that
a demand-filtered proposal is a full semantic snapshot. Publication behavior is
owned by [Demand-Scoped Recovery v1](./BROKER_REPORTS_GATE3_DEMAND_SCOPED_RECOVERY.v1.md).

Every result separately reports `source_fact_completeness_status`. It is
`incomplete` when any fact is role-incomplete, including an explicit model
`missing` or a locally rejected role binding. Chunk execution completeness and
source-fact completeness are intentionally independent: completeness is not
truth.

## 6. Merge

Merge concatenates only contract-valid V2 annotations in selected chunk order
and canonical target order, including facts with explicit missing roles. It
preserves exact dictionary, Role Pack, both
instructions, model and canonical identities. It does not:

- infer or correct a label;
- select a better proposal;
- join facts or create relationships;
- semantically deduplicate;
- turn an incomplete/subset result into a complete document claim.

The merged `FinancialAnnotationsV2` proposal remains in memory. ArtifactStore
registration and persistence belong only to the existing persistence owner.

## 7. Evidence and metrics

Exact customer-bearing canonical envelopes, chunks, instruction, dictionary,
final provider-visible inputs, raw provider outputs and validated outputs stay
outside Git. Repository evidence contains only privacy-safe aggregates and
hashes.

For each live request record chunk characters, working aliases, provider input,
output and total tokens when returned, duration, dictionary injection count,
terminal status and private evidence hash. Batch reports must distinguish peak
request context from total batch work. They must also distinguish unusable
chunks, role-incomplete facts, facts made incomplete by local rejection, and
rejected role bindings.

## 8. Forbidden behavior

The coordinator must not add persistence, ArtifactStore writers, another
workflow, RAG, semantic prefiltering, deterministic financial classification,
role/profile copies, per-fact calls, new labels, semantic retry/repair, provider
fallback, data overlap or Gate 4 behavior.

## 9. Stop

The current NDFL route consumes this coordinator; only the outer workflow may
pass a complete result to the existing persistence owner. Gate 4 remains a
separate, not-yet-designed stage.
